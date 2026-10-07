"""Fetch a public MyAnimeList anime history into one file; query only the evidence an AI needs."""
import argparse
from collections import Counter, defaultdict
import contextlib
from datetime import datetime, timezone
import itertools
import json
import math
import os
from pathlib import Path
import re
from statistics import fmean
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

SOURCE = "mal"
DUBS_URL = "https://raw.githubusercontent.com/MAL-Dubs/MAL-Dubs/main/data/dubInfo.json"
DUB_LABELS = ("subbed", "dubbed", "incomplete")
LISTS = ("watching", "completed", "plan_to_watch", "dropped", "on_hold")
MAL_STATUS_MAP = {1: "watching", 2: "completed", 3: "on_hold", 4: "dropped", 6: "plan_to_watch"}
NSFW_GENRES = frozenset({"hentai", "erotica", "ecchi"})
NSFW_KEYWORDS = ("hentai", "erotica", "ecchi", "mild nudity")
RATING_NSFW_RE = re.compile(r"(?:^|[\s/:(,-])(rx|r\+|r-?18\+?|18\+)(?:[\s/:(,)-]|$)")


def _extract_genres(raw_genres):
    """Normalize raw genre elements (strings or dicts) into clean genre strings."""
    if isinstance(raw_genres, (str, dict)):
        raw_genres = [raw_genres]
    extracted = []
    for g in raw_genres or []:
        name = g.get("name") if isinstance(g, dict) else g
        if isinstance(name, str) and name.strip():
            extracted.append(name.strip())
    return extracted


def is_nsfw(item):
    """Determine whether an entry or media item is adult / NSFW."""
    if not isinstance(item, dict):
        return False
    media = item.get("media") if isinstance(item.get("media"), dict) else item
    for key in ("is_adult", "is_nsfw"):
        val = item.get(key) or media.get(key)
        if val in (True, 1) or str(val).strip().casefold() in ("true", "1", "yes"):
            return True
    for key in ("anime_mpaa_rating_string", "rating", "age_rating"):
        val = str(item.get(key) or media.get(key) or "").strip().casefold()
        if RATING_NSFW_RE.search(val) or any(k in val for k in NSFW_KEYWORDS):
            return True
    genres = _extract_genres(media.get("genres") or item.get("genres"))
    return any(g.casefold() in NSFW_GENRES for g in genres)


def http_json(url):
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "myanimelist-skill/4.0",
    })
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as response:
                result = json.load(response)
        except HTTPError as exc:
            if (exc.code == 429 or 500 <= exc.code < 600) and attempt < 2:
                try:
                    delay = float(exc.headers.get("Retry-After", 2 ** attempt))
                except (TypeError, ValueError):
                    delay = 2 ** attempt
                exc.close()
                if not math.isfinite(delay) or delay > 60:
                    raise RuntimeError("API rate limit: retry later (wait exceeds 60s).") from exc
                time.sleep(max(0, delay))
                continue
            hint = " Access denied or Cloudflare blocked this network." if exc.code == 403 else ""
            exc.close()
            raise RuntimeError(f"API HTTP {exc.code}.{hint}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"API connection failed: {exc}") from exc
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("API returned an invalid JSON response.") from exc
        return result


def fetch(username):
    entries = {}
    while True:
        params = urlencode({"status": 7, "offset": len(entries)})
        url = f"https://myanimelist.net/animelist/{quote(username, safe='')}/load.json?{params}"
        page = http_json(url)
        if not isinstance(page, list):
            raise RuntimeError("MAL returned an invalid list response; check username and privacy.")
        for e in page:
            media_id = e["anime_id"]
            if media_id in entries:
                raise RuntimeError("MAL pagination returned duplicate anime; retry the fetch.")
            if e["status"] not in MAL_STATUS_MAP:
                raise RuntimeError("MAL returned an unknown list status.")
            anime_season = e.get("anime_season")
            season_year = anime_season.get("year") if isinstance(anime_season, dict) else None
            avg_score = None
            if e.get("anime_score_val"):
                with contextlib.suppress(ValueError, TypeError):
                    val = round(float(e["anime_score_val"]) * 10, 2)
                    if val > 0:
                        avg_score = val
            genres = _extract_genres(e.get("genres"))
            entries[media_id] = {
                "status": MAL_STATUS_MAP[e["status"]],
                "score100": (int(e["score"]) * 10) if e.get("score") else 0,
                "progress": e.get("num_watched_episodes", 0),
                "updatedAt": e.get("updated_at"),
                "media": {"id": media_id, "title": {"romaji": e["anime_title"],
                           "english": e.get("anime_title_eng")},
                          "genres": genres,
                          "format": e.get("anime_media_type_string"),
                          "seasonYear": season_year,
                          "episodes": e.get("anime_num_episodes") or None,
                          "averageScore": avg_score,
                          "is_adult": is_nsfw(e)}}
        if not page:
            break
        time.sleep(1)
    return {"source": SOURCE, "user": {"name": username},
            "fetched_at": datetime.now(timezone.utc).isoformat(), "entries": list(entries.values())}


def summarize(entries):
    watched = [e for e in entries if e.get("status") != "plan_to_watch"
               and (e.get("status") == "completed" or (e.get("progress") or 0) > 0)]
    rated = [e for e in watched if (e.get("score100") or 0) > 0]

    def mean(items):
        scores = [e["score100"] for e in items if (e.get("score100") or 0) > 0]
        return round(fmean(scores), 2) if scores else None

    def groups(field):
        buckets = defaultdict(list)
        for e in watched:
            media = e.get("media") if isinstance(e.get("media"), dict) else {}
            if field == "formats":
                fmt = media.get("format")
                names = [str(fmt)] if fmt else []
            else:
                names = _extract_genres(media.get("genres") or e.get("genres"))
            for name in set(names):
                buckets[name].append(e)
        rows = [{"name": name, "watched_count": len(items),
                 "rated_count": sum(1 for e in items if (e.get("score100") or 0) > 0),
                 "mean_score100": mean(items)} for name, items in buckets.items()]
        return sorted(rows, key=lambda r: (-r["watched_count"],
                                           -(r["mean_score100"] or 0), r["name"]))[:10]

    counts = {status: 0 for status in LISTS}
    counts.update(Counter(e.get("status") for e in entries if e.get("status") in counts))
    return {
        "total_entries": len(entries),
        "counts": dict(sorted(counts.items())),
        "watched_count": len(watched), "rated_watched_count": len(rated),
        "mean_score100": mean(watched),
        "nsfw_count": sum(1 for e in entries if is_nsfw(e)),
        "genres": groups("genres"), "formats": groups("formats"),
    }


def pack(data):
    entries = data["entries"]
    genres = sorted(set(itertools.chain.from_iterable(
        _extract_genres(e.get("media", {}).get("genres")) for e in entries
    )))
    gids = {g: i for i, g in enumerate(genres)}
    columns = ["id", "title", "aliases", "user_score100", "community_score100",
               "episodes", "format", "year", "genres", "is_adult", "updated_at", "progress"]
    lists = defaultdict(list)
    for e in sorted(entries, key=lambda e: e["media"]["id"]):
        m = e["media"]
        titles = [str(t) for t in m["title"].values() if t]
        title = titles[0] if titles else str(m["id"])
        aliases = list(dict.fromkeys(t for t in titles if t != title))
        m_genres = _extract_genres(m.get("genres"))
        row = [
            m["id"], title, aliases, e.get("score100") or None, m.get("averageScore") or None,
            m.get("episodes") or None,
            m.get("format"), m.get("seasonYear"),
            sorted({gids[g] for g in m_genres if g in gids}),
            1 if is_nsfw(e) else 0,
            e.get("updatedAt")]
        # Completed entries almost always have progress == episodes; omitting
        # the redundant trailing value keeps rows short. select() restores it.
        if not (e["status"] == "completed" and e.get("progress") == m.get("episodes")):
            row.append(e.get("progress"))
        lists[e["status"]].append(row)
    lists_dict = {status: lists[status] for status in LISTS}
    summary = summarize(entries)
    user_val = data.get("user")
    user_name = user_val.get("name") if isinstance(user_val, dict) else (user_val or "")
    return {"source": data.get("source", SOURCE), "user": user_name,
            "fetched_at": data.get("fetched_at"),
            "columns": columns, "legend": {"genres": genres},
            "summary": summary, "lists": lists_dict}


def enrich_dubs(document, dataset=None):
    dataset = http_json(DUBS_URL) if dataset is None else dataset
    if not isinstance(dataset, dict) or any(
            not isinstance(dataset.get(key), list) or
            any(type(i) is not int or i <= 0 for i in dataset[key])
            for key in ("dubbed", "incomplete")):
        raise RuntimeError("Invalid MAL-Dubs dataset.")
    dubbed, incomplete = set(dataset["dubbed"]), set(dataset["incomplete"])
    columns = document["columns"]
    # progress stays last so completed rows can omit its redundant trailing value.
    first_enrichment = "english_dub" not in columns
    if first_enrichment:
        columns.insert(columns.index("progress"), "english_dub")
    id_index, dub_index = columns.index("id"), columns.index("english_dub")
    counts = Counter()
    for rows in document["lists"].values():
        for row in rows:
            mal_id = row[id_index]
            code = 2 if mal_id in incomplete else 1 if mal_id in dubbed else 0
            if first_enrichment:
                row.insert(dub_index, code)
            else:
                row[dub_index] = code
            counts[DUB_LABELS[code]] += 1
    document["legend"]["english_dub"] = list(DUB_LABELS)
    document["summary"]["english_dub_counts"] = {label: counts[label] for label in DUB_LABELS}
    document["dub_source"] = {
        "url": DUBS_URL, "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    return document


def select(document, status=None, search=None, genre=None, media_id=None,
           sort="title", offset=0, limit=20, dub=None):
    matches = []
    dub_legend = document.get("legend", {}).get("english_dub", list(DUB_LABELS))
    genre_legend = document.get("legend", {}).get("genres", [])
    columns = document.get("columns", [])
    id_index = columns.index("id") if "id" in columns else None
    dub_index = columns.index("english_dub") if "english_dub" in columns else None
    dub_code = DUB_LABELS.index(dub) if (dub and dub in DUB_LABELS) else None
    search_lower = search.casefold() if search else None
    genre_lower = genre.casefold() if genre else None

    for name, rows in document.get("lists", {}).items():
        if status and name != status:
            continue
        for row in rows:
            if media_id is not None and id_index is not None and len(row) > id_index and row[id_index] != media_id:
                continue
            if dub_code is not None and dub_index is not None and len(row) > dub_index and row[dub_index] != dub_code:
                continue

            e = dict(zip(columns, row))
            # Completed rows omit progress when it equals episodes; restore it.
            e.setdefault("progress", e.get("episodes"))
            e["status"] = name
            raw_dub = e.get("english_dub")
            if isinstance(raw_dub, int) and 0 <= raw_dub < len(dub_legend):
                e["english_dub"] = dub_legend[raw_dub]
            else:
                e["english_dub"] = raw_dub or "subbed"
            if dub and e["english_dub"] != dub:
                continue
            e["genres"] = [
                genre_legend[i] if isinstance(i, int) and 0 <= i < len(genre_legend) else str(i)
                for i in e.get("genres", [])
            ]
            if "is_adult" in e and e["is_adult"] is not None:
                e["is_adult"] = bool(e["is_adult"])
            else:
                e["is_adult"] = is_nsfw(e)

            if media_id is not None and e.get("id") != media_id:
                continue
            if search_lower:
                all_titles = itertools.chain([e.get("title")], e.get("aliases") or [])
                if not any(t and search_lower in str(t).casefold() for t in all_titles):
                    continue
            if genre_lower:
                if not any(g and genre_lower == str(g).casefold() for g in e["genres"]):
                    continue
            matches.append(e)

    def sort_metric(val):
        if val is None:
            return float("-inf")
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            with contextlib.suppress(ValueError):
                return float(val)
            with contextlib.suppress(ValueError):
                return datetime.fromisoformat(val).timestamp()
        return float("-inf")

    if sort == "title":
        matches.sort(key=lambda e: ((e.get("title") or "").casefold(), e.get("id") or 0))
    elif sort in ("score", "community", "updated"):
        field = {"score": "user_score100", "community": "community_score100", "updated": "updated_at"}[sort]
        matches.sort(key=lambda e: (-sort_metric(e.get(field)), (e.get("title") or "").casefold(), e.get("id") or 0))
    else:
        raise ValueError(f"Invalid sort parameter: {sort}")

    safe_offset = max(0, int(offset))
    safe_limit = max(0, int(limit))
    returned = matches[safe_offset:safe_offset + safe_limit]
    result = {"source": document.get("source", SOURCE), "user": document.get("user"), "fetched_at": document.get("fetched_at"),
            "matched": len(matches), "offset": safe_offset, "returned": len(returned),
            "truncated": safe_offset + safe_limit < len(matches), "entries": returned}
    if "dub_source" in document:
        result["dub_source"] = document["dub_source"]
    return result


def save(document, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".anime-", suffix=".tmp", delete=False) as out:
            temporary = Path(out.name)
            json.dump(document, out, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            with contextlib.suppress(OSError):
                temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    fetching = commands.add_parser("fetch", help="fetch a public MAL list into one compact JSON file")
    fetching.add_argument("username")
    fetching.add_argument("--output", type=Path, required=True)
    fetching.add_argument("--dubs", action="store_true", help="add MAL-Dubs English dub labels")
    enriching = commands.add_parser("enrich", help="update MAL-Dubs labels in the existing file")
    enriching.add_argument("file", type=Path)
    reading = commands.add_parser("read", help="read summary or bounded entries without network access")
    reading.add_argument("file", type=Path)
    reading.add_argument("--summary", action="store_true")
    reading.add_argument("--status", choices=list(LISTS))
    reading.add_argument("--search")
    reading.add_argument("--genre")
    reading.add_argument("--dub", choices=DUB_LABELS)
    reading.add_argument("--id", type=int, dest="media_id")
    reading.add_argument("--sort", choices=("title", "score", "community", "updated"), default="title")
    reading.add_argument("--offset", type=int, default=0)
    reading.add_argument("--limit", type=int, default=20, help="1–100 entries; default 20")
    args = parser.parse_args()
    if args.command == "fetch" and not args.username.strip():
        parser.error("username must not be blank")
    if args.command == "read":
        if not 1 <= args.limit <= 100 or args.offset < 0:
            parser.error("limit must be 1–100 and offset must be nonnegative")
    try:
        if args.command == "fetch":
            data = fetch(args.username.strip())
            document = pack(data)
            if args.dubs:
                enrich_dubs(document)
            save(document, args.output)
            result = {"file": str(args.output.resolve()), "bytes": args.output.stat().st_size,
                       "source": SOURCE, "user": document["user"], "fetched_at": document["fetched_at"],
                       "summary": document["summary"]}
        else:
            document = json.loads(args.file.read_text(encoding="utf-8"))
            if args.command == "enrich":
                enrich_dubs(document)
                save(document, args.file)
                result = {"file": str(args.file.resolve()), "english_dub_counts": document["summary"]["english_dub_counts"],
                          "dub_source": document["dub_source"]}
            elif args.summary:
                result = {k: document[k] for k in ("source", "user", "fetched_at", "summary") if k in document}
                if "dub_source" in document:
                    result["dub_source"] = document["dub_source"]
                if "summary" in result and isinstance(result["summary"], dict) and "nsfw_count" not in result["summary"]:
                    columns = document.get("columns", [])
                    if "is_adult" in columns:
                        a_idx = columns.index("is_adult")
                        result["summary"]["nsfw_count"] = sum(
                            1 for rows in document.get("lists", {}).values()
                            for r in rows if len(r) > a_idx and r[a_idx]
                        )
                    else:
                        g_legend = document.get("legend", {}).get("genres", [])
                        g_idx = columns.index("genres") if "genres" in columns else None
                        count = 0
                        for rows in document.get("lists", {}).values():
                            for r in rows:
                                raw_g = r[g_idx] if g_idx is not None and len(r) > g_idx else []
                                names = [g_legend[i] for i in raw_g if isinstance(i, int) and 0 <= i < len(g_legend)]
                                if any(n.casefold() in NSFW_GENRES for n in names):
                                    count += 1
                        result["summary"]["nsfw_count"] = count
            else:
                result = select(document, status=args.status, search=args.search, genre=args.genre,
                                media_id=args.media_id, sort=args.sort,
                                offset=args.offset, limit=args.limit, dub=args.dub)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    except (RuntimeError, OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
