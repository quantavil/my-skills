#!/usr/bin/env python3
"""Pull an app's private data from a rooted emulator and decode it to JSON.

Usage: capture_state.py PACKAGE OUT_DIR [--serial emulator-5556]

Writes OUT_DIR/raw/<package>/... (exact files) and OUT_DIR/state.json:
  prefs      shared_prefs XML as {file: {key: value}} (Flutter keys keep their "flutter." prefix)
  sqlite     every SQLite database: {db: {table: {"schema": sql, "rows": [...]}}}
  firestore  Firestore offline cache: cached documents, pending writes and overlays
  files      every other file with its size (Hive, Isar, ObjectBox, JSON blobs...)
"""

from __future__ import annotations

import argparse
import io
import json
import sqlite3
import struct
import sys
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from adbutil import Adb  # noqa: E402

MAX_ROWS = 5000
SQLITE_MAGIC = b"SQLite format 3\x00"


# ---------------------------------------------------------------- protobuf --

def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("truncated varint")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7
        if shift > 70:
            raise ValueError("varint too long")


def fields(buf: bytes) -> list[tuple[int, int, object]]:
    """Decode one protobuf message level into (field, wire_type, raw value)."""
    out, pos = [], 0
    while pos < len(buf):
        key, pos = _varint(buf, pos)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _varint(buf, pos)
        elif wire == 1:
            value, pos = buf[pos:pos + 8], pos + 8
        elif wire == 2:
            size, pos = _varint(buf, pos)
            value, pos = buf[pos:pos + size], pos + size
        elif wire == 5:
            value, pos = buf[pos:pos + 4], pos + 4
        else:
            raise ValueError(f"unsupported wire type {wire}")
        if pos > len(buf):
            raise ValueError("truncated field")
        out.append((number, wire, value))
    return out


def _signed64(value: int) -> int:
    return value - (1 << 64) if value >= 1 << 63 else value


def _timestamp(buf: bytes) -> dict:
    parts = {n: v for n, _, v in fields(buf)}
    return {"seconds": _signed64(parts.get(1, 0)), "nanos": parts.get(2, 0)}


def _map_entries(entries: list[bytes]) -> dict:
    result = {}
    for entry in entries:
        parts = {n: v for n, _, v in fields(entry)}
        result[parts.get(1, b"").decode(errors="replace")] = decode_value(parts.get(2, b""))
    return result


def decode_value(buf: bytes):
    """google.firestore.v1.Value → plain JSON value."""
    for number, _, raw in fields(buf):
        if number == 1:
            return bool(raw)
        if number == 2:
            return _signed64(raw)
        if number == 3:
            return struct.unpack("<d", raw)[0]
        if number == 5:
            return {"$ref": raw.decode(errors="replace")}
        if number == 6:
            return _map_entries([v for n, _, v in fields(raw) if n == 1])
        if number == 8:
            parts = {n: struct.unpack("<d", v)[0] for n, _, v in fields(raw)}
            return {"$geo": [parts.get(1, 0.0), parts.get(2, 0.0)]}
        if number == 9:
            return [decode_value(v) for n, _, v in fields(raw) if n == 1]
        if number == 10:
            return {"$time": _timestamp(raw)}
        if number == 11:
            return None
        if number == 17:
            return raw.decode(errors="replace")
        if number == 18:
            return {"$bytes": raw.hex()}
    return None


def decode_document(buf: bytes) -> dict:
    """google.firestore.v1.Document."""
    doc: dict = {"path": "", "fields": {}}
    entries = []
    for number, _, raw in fields(buf):
        if number == 1:
            doc["path"] = raw.decode(errors="replace").split("/documents/", 1)[-1]
        elif number == 2:
            entries.append(raw)
        elif number == 4:
            doc["updated"] = _timestamp(raw)
    doc["fields"] = _map_entries(entries)
    return doc


def decode_maybe_document(buf: bytes) -> dict:
    """firestore.client.MaybeDocument (remote_documents.contents)."""
    for number, _, raw in fields(buf):
        if number == 2:
            return decode_document(raw)
        if number in (1, 3):
            name = {n: v for n, _, v in fields(raw)}.get(1, b"").decode(errors="replace")
            return {"path": name.split("/documents/", 1)[-1], "deleted": number == 1}
    return {}


def decode_write(buf: bytes) -> dict:
    """google.firestore.v1.Write (a pending local change)."""
    for number, _, raw in fields(buf):
        if number == 1:
            return {"op": "set", **decode_document(raw)}
        if number == 2:
            return {"op": "delete", "path": raw.decode(errors="replace").split("/documents/", 1)[-1]}
    return {"op": "other"}


def decode_write_batch(buf: bytes) -> list[dict]:
    """firestore.client.WriteBatch (mutations.mutations)."""
    return [decode_write(raw) for number, _, raw in fields(buf) if number in (2, 4)]


def firestore_from_db(db: sqlite3.Connection) -> dict:
    tables = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
    out: dict = {"documents": [], "pending_writes": [], "overlays": []}
    if "remote_documents" in tables:
        for (blob,) in db.execute("select contents from remote_documents"):
            out["documents"].append(_safe(decode_maybe_document, blob))
    if "mutations" in tables:
        for (blob,) in db.execute("select mutations from mutations"):
            out["pending_writes"].extend(_safe(decode_write_batch, blob, []))
    if "document_overlays" in tables:
        for (blob,) in db.execute("select overlay_mutation from document_overlays"):
            out["overlays"].append(_safe(decode_write, blob))
    out["documents"].sort(key=lambda d: d.get("path", ""))
    return out


def _safe(fn, blob, default=None):
    try:
        return fn(bytes(blob))
    except (ValueError, struct.error) as error:
        return default if default is not None else {"decode_error": str(error), "hex": bytes(blob)[:64].hex()}


# ------------------------------------------------------------------ files --

def _cell(value):
    if isinstance(value, bytes):
        return {"$blob": len(value), "hex": value[:32].hex()}
    return value


def dump_sqlite(path: Path) -> tuple[dict, dict | None]:
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        tables = {}
        for name, sql in db.execute("select name, sql from sqlite_master where type='table'"):
            if name.startswith("sqlite_") or name == "android_metadata":
                continue
            cursor = db.execute(f'select * from "{name}" limit {MAX_ROWS + 1}')
            columns = [c[0] for c in cursor.description]
            rows = [dict(zip(columns, map(_cell, row))) for row in cursor]
            tables[name] = {"schema": sql, "rows": rows[:MAX_ROWS]}
            if len(rows) > MAX_ROWS:
                tables[name]["truncated"] = True
                print(f"warning: {path.name}.{name} has more than {MAX_ROWS} rows; truncated", file=sys.stderr)
        firestore = firestore_from_db(db) if path.name.startswith("firestore.") else None
        return tables, firestore
    finally:
        db.close()


def parse_prefs(path: Path) -> dict:
    values = {}
    for item in ET.parse(path).getroot():
        name = item.get("name", "")
        if item.tag == "string":
            values[name] = item.text or ""
        elif item.tag == "set":
            values[name] = sorted(child.text or "" for child in item)
        elif item.tag == "boolean":
            values[name] = item.get("value") == "true"
        elif item.tag in ("int", "long"):
            values[name] = int(item.get("value", "0"))
        elif item.tag == "float":
            values[name] = float(item.get("value", "0"))
    return values


def decode_tree(root: Path) -> dict:
    state: dict = {"prefs": {}, "sqlite": {}, "firestore": {}, "files": {}}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = str(path.relative_to(root))
        if path.suffix in (".db-wal", ".db-shm") or rel.endswith(("-wal", "-shm", "-journal")):
            continue
        if path.parent.name == "shared_prefs" and path.suffix == ".xml":
            try:
                state["prefs"][path.name] = parse_prefs(path)
                continue
            except ET.ParseError:
                pass
        with path.open("rb") as handle:
            head = handle.read(16)
        if head == SQLITE_MAGIC:
            try:
                tables, firestore = dump_sqlite(path)
                state["sqlite"][rel] = tables
                if firestore:
                    state["firestore"][rel] = firestore
                continue
            except sqlite3.DatabaseError as error:
                state["files"][rel] = {"size": path.stat().st_size, "error": str(error)}
                continue
        state["files"][rel] = {"size": path.stat().st_size}
    return state


# ------------------------------------------------------------------- pull --

def stable_tar(fetch, fingerprint, attempts: int = 4) -> bytes:
    """One pull when the app's files did not change during it, else retry.

    `fingerprint()` is a cheap listing of (mtime, size, name); equal before and after a pull
    means no write landed in between. Without a usable fingerprint, fall back to pulling
    twice until the two copies are byte-identical.
    """
    if not fingerprint():
        previous = fetch()
        for _ in range(attempts - 1):
            current = fetch()
            if current == previous:
                return current
            previous = current
        print("warning: app data kept changing during the pull; the copy may be inconsistent", file=sys.stderr)
        return previous
    for _ in range(attempts):
        before = fingerprint()
        data = fetch()
        if fingerprint() == before:
            return data
    print("warning: app data kept changing during the pull; the copy may be inconsistent", file=sys.stderr)
    return data


def pull(adb: Adb, package: str, dest: Path) -> Path:
    adb.app_uid(package)
    command = adb.root_command(f"tar -C /data/data -cf - {package}")
    listing = f"find /data/data/{package} -type f -exec stat -c '%Y %s %n' {{}} +"
    data = stable_tar(lambda: adb.run("exec-out", command, binary=True, timeout=300),
                      lambda: adb.root_shell(listing, check=False).strip())
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        archive.extractall(dest, filter="data")
    return dest / package


def capture(adb: Adb, package: str, out: Path) -> dict:
    root = pull(adb, package, out / "raw")
    state = decode_tree(root)
    (out / "state.json").write_text(json.dumps(state, indent=1, ensure_ascii=False, default=str) + "\n")
    return state


def summary(state: dict) -> str:
    lines = []
    for name, values in state["prefs"].items():
        lines.append(f"prefs  {name}: {len(values)} keys")
    for name, tables in state["sqlite"].items():
        counts = ", ".join(f"{t}={len(v['rows'])}" for t, v in tables.items())
        lines.append(f"sqlite {name}: {counts}")
    for name, fs in state["firestore"].items():
        lines.append(
            f"firestore {name}: {len(fs['documents'])} docs, "
            f"{len(fs['pending_writes'])} pending writes, {len(fs['overlays'])} overlays"
        )
    lines.append(f"other files: {len(state['files'])}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("package")
    parser.add_argument("out", type=Path)
    parser.add_argument("--serial", default="emulator-5556")
    args = parser.parse_args()
    state = capture(Adb(args.serial), args.package, args.out)
    print(summary(state))
    print(f"→ {args.out / 'state.json'}")


if __name__ == "__main__":
    main()
