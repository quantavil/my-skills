"""Offline regression checks: python -m unittest discover -s scripts -v."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPT = Path(__file__).with_name("myanimelist.py")


def raw_entry(anime_id, status=2, score=8, progress=12):
    return {"anime_id": anime_id, "anime_title": f"Title {anime_id}", "status": status,
            "score": score, "num_watched_episodes": progress, "genres": [],
            "anime_score_val": 7.5, "anime_media_type_string": "TV"}


def entry(media_id, status="completed", score100=80, progress=12, episodes=12):
    return {"status": status,
            "score100": score100, "progress": progress,
            "media": {"id": media_id, "title": {"romaji": f"Anime {media_id}"},
                      "genres": ["Drama"], "format": "TV", "episodes": episodes}}


class MyAnimeListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = None
        if SCRIPT.exists():
            spec = importlib.util.spec_from_file_location("myanimelist", SCRIPT)
            cls.api = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.api)

    def setUp(self):
        self.assertIsNotNone(self.api, "MyAnimeList script has not been implemented")

    def test_planned_and_unrated_titles_do_not_bias_taste(self):
        summary = self.api.summarize([entry(1), entry(2, score100=0),
                                      entry(3, "plan_to_watch", 100, 0),
                                      entry(4, "dropped", 20, 3)])
        self.assertEqual(summary["watched_count"], 3)
        self.assertEqual(summary["rated_watched_count"], 2)
        self.assertEqual(summary["mean_score100"], 50)
        self.assertEqual(summary["genres"][0]["watched_count"], 3)
        self.assertEqual(summary["genres"][0]["mean_score100"], 50)
        self.assertEqual(summary["counts"]["plan_to_watch"], 1)

    def test_empty_history_has_no_invented_ratings(self):
        summary = self.api.summarize([])
        self.assertIsNone(summary["mean_score100"])
        self.assertEqual(summary["genres"], [])
        self.assertEqual(summary["total_entries"], 0)

    def test_mal_pagination_and_native_scores_are_preserved(self):
        pages = [[raw_entry(i) for i in range(300)], [raw_entry(300)], []]
        with patch.object(self.api, "urlopen", side_effect=[
                io.BytesIO(json.dumps(p).encode()) for p in pages]), \
                patch.object(self.api.time, "sleep"):
            source = self.api.fetch("viewer")
        self.assertEqual(source["source"], "mal")
        self.assertEqual(len(source["entries"]), 301)
        self.assertNotIn("raw", source)
        document = self.api.pack(source)
        row = self.api.select(document, limit=1)["entries"][0]
        self.assertEqual(row["user_score100"], 80)
        self.assertEqual(row["community_score100"], 75)

    def test_repeated_mal_page_fails_instead_of_looping(self):
        page = [raw_entry(i) for i in range(300)]
        with patch.object(self.api, "urlopen", side_effect=[
                io.BytesIO(json.dumps(page).encode()), io.BytesIO(json.dumps(page).encode())]), \
                patch.object(self.api.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "duplicate|repeat"):
                self.api.fetch("viewer")

    def test_mal_short_pages_do_not_silently_truncate_the_list(self):
        pages = [[raw_entry(1)], [raw_entry(2)], []]
        with patch.object(self.api, "urlopen", side_effect=[
                io.BytesIO(json.dumps(p).encode()) for p in pages]), \
                patch.object(self.api.time, "sleep"):
            self.assertEqual(len(self.api.fetch("viewer")["entries"]), 2)

    def test_unknown_mal_status_fails_loudly(self):
        with patch.object(self.api, "urlopen", return_value=io.BytesIO(json.dumps([raw_entry(1, status=99)]).encode())), \
                patch.object(self.api.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "unknown list status"):
                self.api.fetch("viewer")

    def test_invalid_mal_response_fails_loudly(self):
        with patch.object(self.api, "urlopen", return_value=io.BytesIO(b'{"not":"a list"}')):
            with self.assertRaisesRegex(RuntimeError, "invalid list response"):
                self.api.fetch("viewer")

    def test_rate_limit_is_retried(self):
        limited = HTTPError("https://myanimelist.net/", 429, "limited",
                            {"Retry-After": "0"}, io.BytesIO(b"{}"))
        response = io.BytesIO(b"[]")
        with patch.object(self.api, "urlopen", side_effect=[limited, response]), \
                patch.object(self.api.time, "sleep"):
            self.assertEqual(self.api.http_json("https://myanimelist.net/"), [])

    def test_cloudflare_failure_is_actionable(self):
        denied = HTTPError("https://myanimelist.net/", 403, "Forbidden", {},
                           io.BytesIO(b"<html>Cloudflare</html>"))
        with patch.object(self.api, "urlopen", side_effect=denied):
            with self.assertRaisesRegex(RuntimeError, "403"):
                self.api.http_json("https://myanimelist.net/")

    def test_malformed_api_json_produces_actionable_error(self):
        with patch.object(self.api, "urlopen", return_value=io.BytesIO(b"<html>not json</html>")):
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                self.api.http_json("https://myanimelist.net/")

    def test_single_file_keeps_all_statuses(self):
        entries = [entry(1), entry(2, "plan_to_watch", 0, 0), entry(3, "watching")]
        entries[0]["media"].update(averageScore=75)
        source = {"source": "mal", "user": {"name": "viewer"},
                  "fetched_at": "2026-10-05T00:00:00+00:00", "entries": entries}
        document = self.api.pack(source)
        rows = self.api.select(document, limit=20)["entries"]
        self.assertEqual(len(rows), 3)
        self.assertEqual(document["summary"]["counts"]["plan_to_watch"], 1)
        self.assertEqual(document["summary"]["counts"]["watching"], 1)
        first = next(e for e in rows if e["id"] == 1)
        self.assertEqual(first["user_score100"], 80)
        self.assertEqual(first["community_score100"], 75)
        self.assertNotIn("_raw", document)

    def test_bounded_queries_search_all_title_aliases(self):
        entries = [entry(1), entry(2, "plan_to_watch", 0, 0), entry(3, "plan_to_watch", 0, 0)]
        entries[1]["media"]["title"]["english"] = "Space Story"
        data = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                              "fetched_at": "now", "entries": entries})
        result = self.api.select(data, status="plan_to_watch", search="space", limit=1)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["entries"][0]["id"], 2)
        result = self.api.select(data, status="plan_to_watch", genre="Drama", limit=1)
        self.assertEqual(result["matched"], 2)
        self.assertEqual(len(result["entries"]), 1)
        self.assertTrue(result["truncated"])
        res_id = self.api.select(data, media_id=2)
        self.assertEqual(res_id["matched"], 1)
        self.assertEqual(res_id["entries"][0]["id"], 2)

    def test_dub_enrichment_uses_mal_ids(self):
        entries = [entry(i) for i in (9253, 8, 999999)]
        document = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                                  "fetched_at": "now", "entries": entries})
        self.api.enrich_dubs(document, {"dubbed": [9253], "incomplete": [8], "_license": "example"})
        rows = {e["id"]: e for e in self.api.select(document)["entries"]}
        self.assertEqual([rows[i]["english_dub"] for i in (9253, 8, 999999)],
                         ["dubbed", "incomplete", "subbed"])
        result = self.api.select(document, dub="dubbed")
        self.assertEqual([e["id"] for e in result["entries"]], [9253])
        # Re-enriching with a new dataset updates labels without duplicating the column.
        self.api.enrich_dubs(document, {"dubbed": [], "incomplete": [9253]})
        self.assertEqual(document["columns"].count("english_dub"), 1)
        rows = {e["id"]: e for e in self.api.select(document)["entries"]}
        self.assertEqual(rows[9253]["english_dub"], "incomplete")

    def test_invalid_dub_dataset_does_not_mutate_snapshot(self):
        document = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                                  "fetched_at": "now", "entries": []})
        before = json.dumps(document)
        with self.assertRaisesRegex(RuntimeError, "dataset"):
            self.api.enrich_dubs(document, {"dubbed": ["9253"], "incomplete": []})
        self.assertEqual(json.dumps(document), before)

    def test_completed_rows_omit_redundant_progress_and_select_restores_it(self):
        done = entry(1)
        watching = entry(2, "watching", 70, 5)
        partial = entry(3, "completed", 60, 0)
        document = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                                  "fetched_at": "now", "entries": [done, watching, partial]})
        packed = {r[0]: r for v in document["lists"].values() for r in v}
        self.assertEqual(len(packed[1]), len(document["columns"]) - 1)
        self.assertEqual(len(packed[2]), len(document["columns"]))
        self.assertEqual(len(packed[3]), len(document["columns"]))
        rows = {e["id"]: e for e in self.api.select(document, limit=20)["entries"]}
        self.assertEqual(rows[1]["progress"], 12)
        self.assertEqual(rows[2]["progress"], 5)
        self.assertEqual(rows[3]["progress"], 0)
        self.api.enrich_dubs(document, {"dubbed": [1, 2, 3], "incomplete": []})
        self.assertEqual(document["columns"][-2:], ["english_dub", "progress"])
        rows = {e["id"]: e for e in self.api.select(document, limit=20)["entries"]}
        self.assertEqual((rows[1]["progress"], rows[1]["english_dub"]), (12, "dubbed"))
        self.assertEqual((rows[2]["progress"], rows[2]["english_dub"]), (5, "dubbed"))
        self.assertEqual((rows[3]["progress"], rows[3]["english_dub"]), (0, "dubbed"))
        before = json.dumps(document)
        self.api.enrich_dubs(document, {"dubbed": [1, 2, 3], "incomplete": []})
        after = json.loads(json.dumps(document))
        before_doc = json.loads(before)
        self.assertEqual({k: v for k, v in after["dub_source"].items() if k != "checked_at"},
                         {k: v for k, v in before_doc["dub_source"].items() if k != "checked_at"})
        after["dub_source"] = before_doc["dub_source"]
        self.assertEqual(after, before_doc)

    def test_cli_writes_one_file_and_failed_refresh_preserves_it(self):
        source = {"source": "mal", "user": {"name": "viewer"},
                  "fetched_at": "now", "entries": [entry(1)]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mal.json"
            args = ["myanimelist.py", "fetch", "viewer", "--output", str(path)]
            with patch("sys.argv", args), patch.object(self.api, "fetch", return_value=source), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(self.api.main(), 0)
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["mal.json"])
            before = path.read_bytes()
            with patch("sys.argv", args), patch.object(self.api, "fetch", side_effect=RuntimeError("blocked")), \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(self.api.main(), 1)
            self.assertEqual(path.read_bytes(), before)

    def test_interrupted_atomic_replacement_keeps_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mal.json"
            path.write_text('{"previous":true}\n')
            with patch.object(self.api.os, "replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    self.api.save({"new": True}, path)
            self.assertEqual(path.read_text(), '{"previous":true}\n')
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["mal.json"])

    def test_summary_cli_does_not_expose_rows(self):
        document = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                                  "fetched_at": "now", "entries": [entry(1)]})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mal.json"
            self.api.save(document, path)
            output = io.StringIO()
            with patch("sys.argv", ["myanimelist.py", "read", str(path), "--summary"]), \
                    redirect_stdout(output):
                self.assertEqual(self.api.main(), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["summary"]["total_entries"], 1)
            self.assertNotIn("lists", result)

    def test_sorting_handles_score_community_and_updated_formats(self):
        e1 = entry(1, score100=70)
        e1["updatedAt"] = 1600000000
        e1["media"]["averageScore"] = 60
        e2 = entry(2, score100=90)
        e2["updatedAt"] = "2026-10-05T00:00:00+00:00"
        e2["media"]["averageScore"] = 85
        e3 = entry(3, score100=None)
        e3["updatedAt"] = None
        e3["media"]["averageScore"] = None
        document = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                                  "fetched_at": "now", "entries": [e1, e2, e3]})
        by_score = [e["id"] for e in self.api.select(document, sort="score")["entries"]]
        self.assertEqual(by_score, [2, 1, 3])
        by_comm = [e["id"] for e in self.api.select(document, sort="community")["entries"]]
        self.assertEqual(by_comm, [2, 1, 3])
        by_updated = [e["id"] for e in self.api.select(document, sort="updated")["entries"]]
        self.assertEqual(by_updated, [2, 1, 3])

    def test_is_nsfw_detection_accuracy(self):
        # Genres
        self.assertTrue(self.api.is_nsfw({"media": {"genres": ["Hentai"]}}))
        self.assertTrue(self.api.is_nsfw({"media": {"genres": ["erotica"]}}))
        self.assertTrue(self.api.is_nsfw({"media": {"genres": ["Ecchi"]}}))
        self.assertTrue(self.api.is_nsfw({"media": {"genres": [{"name": "Hentai"}]}}))
        self.assertTrue(self.api.is_nsfw({"genres": [{"name": "Ecchi", "id": 9}]}))
        # Ratings
        self.assertTrue(self.api.is_nsfw({"rating": "Rx - Hentai"}))
        self.assertTrue(self.api.is_nsfw({"rating": "Rx"}))
        self.assertTrue(self.api.is_nsfw({"rating": "Rated R+"}))
        self.assertTrue(self.api.is_nsfw({"rating": "Rating: Rx"}))
        self.assertTrue(self.api.is_nsfw({"rating": "Mild Nudity"}))
        self.assertTrue(self.api.is_nsfw({"anime_mpaa_rating_string": "R+ - Mild Nudity"}))
        self.assertTrue(self.api.is_nsfw({"age_rating": "18+"}))
        self.assertTrue(self.api.is_nsfw({"rating": "R18+"}))
        self.assertTrue(self.api.is_nsfw({"rating": "R-18"}))
        # Boolean flags
        self.assertTrue(self.api.is_nsfw({"is_adult": True}))
        self.assertTrue(self.api.is_nsfw({"media": {"is_adult": 1}}))
        self.assertTrue(self.api.is_nsfw({"is_nsfw": True}))
        self.assertTrue(self.api.is_nsfw({"media": {"is_adult": "true"}}))
        self.assertTrue(self.api.is_nsfw({"is_nsfw": "1"}))
        # SFW and negative cases
        self.assertFalse(self.api.is_nsfw({"media": {"genres": ["Action", "Drama"]}}))
        self.assertFalse(self.api.is_nsfw({"rating": "R - 17+ (violence & profanity)"}))
        self.assertFalse(self.api.is_nsfw({"rating": "PG-13"}))
        self.assertFalse(self.api.is_nsfw({"rating": "G"}))
        self.assertFalse(self.api.is_nsfw({"is_adult": False}))
        self.assertFalse(self.api.is_nsfw({"is_adult": "false"}))
        self.assertFalse(self.api.is_nsfw({}))
        self.assertFalse(self.api.is_nsfw(None))

    def test_summary_and_packing_nsfw_support(self):
        e1 = entry(1)  # Drama (SFW)
        e2 = entry(2)
        e2["media"]["genres"] = ["Hentai"]
        e3 = entry(3)
        e3["media"]["genres"] = ["Ecchi", "Comedy"]
        e4 = entry(4)
        e4["media"]["genres"] = ["Action"]
        e4["media"]["is_adult"] = True

        summary = self.api.summarize([e1, e2, e3, e4])
        self.assertEqual(summary["nsfw_count"], 3)
        self.assertEqual(summary["total_entries"], 4)

        doc = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                             "fetched_at": "now", "entries": [e1, e2, e3, e4]})
        self.assertIn("is_adult", doc["columns"])
        rows = self.api.select(doc)["entries"]
        adult_map = {r["id"]: r["is_adult"] for r in rows}
        self.assertEqual(adult_map, {1: False, 2: True, 3: True, 4: True})

    def test_nsfw_and_sfw_included_by_default(self):
        e_sfw = entry(1)  # Drama
        e_nsfw1 = entry(2)
        e_nsfw1["media"]["genres"] = ["Hentai"]
        e_nsfw2 = entry(3)
        e_nsfw2["media"]["genres"] = ["Erotica"]
        doc = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                             "fetched_at": "now", "entries": [e_sfw, e_nsfw1, e_nsfw2]})

        # Always on by default: returns all entries including adult/NSFW
        res = self.api.select(doc)
        self.assertEqual(res["matched"], 3)
        self.assertEqual([e["id"] for e in res["entries"]], [1, 2, 3])
        self.assertFalse(res["entries"][0]["is_adult"])
        self.assertTrue(res["entries"][1]["is_adult"])
        self.assertTrue(res["entries"][2]["is_adult"])

    def test_fetch_captures_adult_content_and_encodes_url(self):
        raw_adult = {"anime_id": 101, "anime_title": "Adult OVA", "status": 2,
                     "score": 9, "num_watched_episodes": 2, "genres": [{"name": "Hentai"}],
                     "anime_mpaa_rating_string": "Rx - Hentai", "anime_media_type_string": "OVA"}
        pages = [[raw_adult], []]
        requested_urls = []

        def fake_urlopen(req, timeout=30):
            requested_urls.append(req.full_url)
            p = pages.pop(0)
            return io.BytesIO(json.dumps(p).encode())

        with patch.object(self.api, "urlopen", side_effect=fake_urlopen), \
                patch.object(self.api.time, "sleep"):
            data = self.api.fetch("special user")

        self.assertEqual(len(data["entries"]), 1)
        entry_item = data["entries"][0]
        self.assertTrue(entry_item["media"]["is_adult"])
        self.assertEqual(entry_item["media"]["genres"], ["Hentai"])
        # Check URL properly quoted username and encoded parameters
        self.assertIn("special%20user", requested_urls[0])
        self.assertIn("status=7", requested_urls[0])
        self.assertIn("offset=0", requested_urls[0])

    def test_summarize_formats_does_not_leak_genres_when_format_is_none(self):
        # Format is None, genres has Comedy and Sci-Fi. Formats must be empty, not leak genres!
        e = {"status": "completed", "score100": 80, "progress": 12,
             "media": {"id": 1, "format": None, "genres": ["Comedy", "Sci-Fi"]}}
        summary = self.api.summarize([e])
        self.assertEqual(summary["formats"], [])
        self.assertEqual(len(summary["genres"]), 2)
        self.assertEqual({g["name"] for g in summary["genres"]}, {"Comedy", "Sci-Fi"})

    def test_summarize_and_pack_handle_dict_genres(self):
        # MAL API / raw objects often have dict genres like [{"id": 4, "name": "Comedy"}]
        e = {"status": "completed", "score100": 90, "progress": 12,
             "media": {"id": 1, "title": {"romaji": "Test Anime"}, "format": "TV",
                       "genres": [{"id": 4, "name": "Comedy"}]}}
        summary = self.api.summarize([e])
        self.assertEqual(summary["genres"][0]["name"], "Comedy")
        self.assertEqual(summary["genres"][0]["mean_score100"], 90.0)

        packed = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                                "fetched_at": "now", "entries": [e]})
        self.assertEqual(packed["legend"]["genres"], ["Comedy"])
        # Genre index in row should point to 0 ("Comedy")
        row = packed["lists"]["completed"][0]
        self.assertEqual(row[8], [0])

    def test_legacy_summary_calculates_missing_nsfw_count(self):
        # A legacy snapshot that doesn't have "nsfw_count" in summary
        doc = {
            "source": "mal",
            "user": "viewer",
            "fetched_at": "2026-01-01T00:00:00Z",
            "columns": ["id", "title", "aliases", "user_score100", "community_score100",
                        "episodes", "format", "year", "genres", "updated_at", "progress"],
            "legend": {"genres": ["Drama", "Ecchi"]},
            "summary": {"total_entries": 2, "watched_count": 2},
            "lists": {
                "completed": [
                    [1, "Normal Anime", [], 80, 75, 12, "TV", 2020, [0], None],
                    [2, "Spicy Anime", [], 70, 70, 12, "TV", 2021, [1], None],
                ]
            }
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.json"
            self.api.save(doc, path)
            out = io.StringIO()
            with patch("sys.argv", ["myanimelist.py", "read", str(path), "--summary"]), \
                    redirect_stdout(out):
                self.assertEqual(self.api.main(), 0)
            res = json.loads(out.getvalue())
            self.assertEqual(res["summary"]["nsfw_count"], 1)

    def test_select_safe_offset(self):
        e1 = entry(1)
        e2 = entry(2)
        doc = self.api.pack({"source": "mal", "user": {"name": "viewer"},
                             "fetched_at": "now", "entries": [e1, e2]})
        # Negative offset should be clamped to 0
        res = self.api.select(doc, offset=-10, limit=2)
        self.assertEqual(res["offset"], 0)
        self.assertEqual(len(res["entries"]), 2)


if __name__ == "__main__":
    unittest.main()
