"""Offline tests for the Ditto scripts. Run: python3 -I -m unittest discover -s tests"""

import sqlite3
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import adbutil  # noqa: E402
import capture_state  # noqa: E402
import diff  # noqa: E402
import experiment  # noqa: E402
import inventory  # noqa: E402
import parity  # noqa: E402


def varint(value: int) -> bytes:
    value &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def field(number: int, payload) -> bytes:
    if isinstance(payload, int):
        return varint(number << 3) + varint(payload)
    if isinstance(payload, float):
        return varint(number << 3 | 1) + struct.pack("<d", payload)
    data = payload.encode() if isinstance(payload, str) else payload
    return varint(number << 3 | 2) + varint(len(data)) + data


def entry(key: str, value: bytes) -> bytes:
    return field(2, field(1, key) + field(2, value))


DOC_NAME = "projects/p/databases/(default)/documents/users/u1/sleeps/s1"
DOCUMENT = (
    field(1, DOC_NAME)
    + entry("type", field(17, "nap"))
    + entry("minutes", field(2, 80))
    + entry("offset", field(2, -5))
    + entry("ratio", field(3, 0.5))
    + entry("done", field(1, 1))
    + entry("start", field(10, field(1, 1_727_760_000) + field(2, 5)))
    + entry("tags", field(9, field(1, field(17, "a")) + field(1, field(17, "b"))))
    + entry("meta", field(6, field(1, field(1, "k") + field(2, field(11, 0)))))
)


class FirestoreDecodeTest(unittest.TestCase):
    def test_document_values(self):
        doc = capture_state.decode_maybe_document(field(2, DOCUMENT))
        self.assertEqual(doc["path"], "users/u1/sleeps/s1")
        self.assertEqual(doc["fields"], {
            "type": "nap", "minutes": 80, "offset": -5, "ratio": 0.5, "done": True,
            "start": {"$time": {"seconds": 1_727_760_000, "nanos": 5}},
            "tags": ["a", "b"], "meta": {"k": None},
        })

    def test_deleted_document(self):
        doc = capture_state.decode_maybe_document(field(1, field(1, DOC_NAME)))
        self.assertEqual(doc, {"path": "users/u1/sleeps/s1", "deleted": True})

    def test_pending_writes_and_overlays_from_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "firestore.%5BDEFAULT%5D.p.%28default%29"
            db = sqlite3.connect(path)
            db.execute("create table remote_documents (path text, contents blob)")
            db.execute("create table mutations (uid text, batch_id int, mutations blob)")
            db.execute("create table document_overlays (uid text, overlay_mutation blob)")
            db.execute("insert into remote_documents values ('x', ?)", (field(2, DOCUMENT),))
            batch = field(1, 7) + field(2, field(1, DOCUMENT)) + field(2, field(2, DOC_NAME))
            db.execute("insert into mutations values ('u', 7, ?)", (batch,))
            db.execute("insert into document_overlays values ('u', ?)", (field(1, DOCUMENT),))
            db.commit()
            db.close()
            tables, firestore = capture_state.dump_sqlite(path)
        self.assertEqual([d["path"] for d in firestore["documents"]], ["users/u1/sleeps/s1"])
        self.assertEqual([w["op"] for w in firestore["pending_writes"]], ["set", "delete"])
        self.assertEqual(firestore["overlays"][0]["fields"]["minutes"], 80)
        self.assertEqual(tables["mutations"]["rows"][0]["mutations"]["$blob"], len(batch))

    def test_garbage_blob_is_reported_not_raised(self):
        self.assertIn("decode_error", capture_state._safe(capture_state.decode_maybe_document, b"\x0a\xff"))


class TreeDecodeTest(unittest.TestCase):
    def test_prefs_sqlite_and_other_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "shared_prefs").mkdir()
            (root / "shared_prefs/FlutterSharedPreferences.xml").write_text(
                "<map><string name='flutter.name'>Mia</string><boolean name='flutter.metric' value='true'/>"
                "<long name='flutter.birth' value='1727740800000'/><float name='flutter.w' value='3.5'/>"
                "<set name='flutter.s'><string>b</string><string>a</string></set></map>")
            (root / "databases").mkdir()
            db = sqlite3.connect(root / "databases/app.db")
            db.execute("create table sleep (id int, start int, kind text)")
            db.execute("insert into sleep values (1, 100, 'nap')")
            db.commit()
            db.close()
            (root / "app_flutter").mkdir()
            (root / "app_flutter/box.hive").write_bytes(b"\x00" * 10)
            state = capture_state.decode_tree(root)
        self.assertEqual(state["prefs"]["FlutterSharedPreferences.xml"], {
            "flutter.name": "Mia", "flutter.metric": True, "flutter.birth": 1727740800000,
            "flutter.w": 3.5, "flutter.s": ["a", "b"]})
        self.assertEqual(state["sqlite"]["databases/app.db"]["sleep"]["rows"], [{"id": 1, "start": 100, "kind": "nap"}])
        self.assertEqual(state["files"], {"app_flutter/box.hive": {"size": 10}})


class ExperimentTest(unittest.TestCase):
    def test_visible_texts_reading_order_and_dedup(self):
        xml = """<hierarchy>
          <node text="" content-desc="Next nap&#10;10:30" bounds="[0,400][500,500]"/>
          <node text="Home" content-desc="" bounds="[0,100][200,150]"/>
          <node text="Stats" content-desc="" bounds="[300,100][500,150]"/>
          <node text="Home" content-desc="" bounds="[0,900][200,950]"/>
          <node text="Wifi signal full." package="com.android.systemui" bounds="[0,0][50,20]"/>
        </hierarchy>"""
        self.assertEqual(experiment.visible_texts(xml), ["Home", "Stats", "Next nap\n10:30"])


class DiffNotesTest(unittest.TestCase):
    def test_equal_notes_pass_and_float_noise_is_ignored(self):
        self.assertEqual(diff.compare_notes({"a": "10:30", "b": 0.1 + 0.2}, {"a": "10:30", "b": 0.3}), [])

    def test_none_on_both_sides_is_a_failure(self):
        self.assertEqual(len(diff.compare_notes({"a": None}, {"a": None})), 1)

    def test_empty_original_notes_fail(self):
        self.assertTrue(diff.compare_notes({}, {}))

    def test_missing_and_different_values_fail(self):
        problems = diff.compare_notes({"a": "1", "b": "2"}, {"a": "9", "c": "3"})
        self.assertEqual(len(problems), 3)

    def test_repeated_step_names_do_not_collapse(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("01-home", "02-home", "03-stats"):
                (Path(tmp) / name).mkdir()
            self.assertEqual(list(diff.steps(Path(tmp))), ["home", "home#2", "stats"])


class NoteTest(unittest.TestCase):
    def test_none_note_raises_unless_allowed(self):
        lab = experiment.Lab.__new__(experiment.Lab)
        lab.notes, lab.out = {}, Path(tempfile.mkdtemp())
        lab.texts = lambda: ["Home"]
        with self.assertRaises(ValueError):
            lab.note("next_nap", None)
        lab.note("next_nap", None, allow_none=True)
        self.assertEqual(lab.notes, {"next_nap": None})


class StablePullTest(unittest.TestCase):
    def test_returns_when_two_pulls_match(self):
        pulls = iter([b"a", b"b", b"b"])
        self.assertEqual(capture_state.stable_tar(lambda: next(pulls)), b"b")

    def test_gives_up_with_last_copy(self):
        pulls = iter([b"1", b"2", b"3", b"4"])
        self.assertEqual(capture_state.stable_tar(lambda: next(pulls)), b"4")


class ParityTest(unittest.TestCase):
    def make_trace(self, root: Path, name: str, original: dict, clone: dict) -> None:
        for label, notes in (("original", original), ("clone", clone)):
            folder = root / name / label
            (folder / "01-home").mkdir(parents=True)
            (folder / "notes.json").write_text(__import__("json").dumps(notes))

    def test_counts_and_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_trace(root, "nap_ok", {"next": "10:30"}, {"next": "10:30"})
            self.make_trace(root, "nap_bad", {"next": "10:30"}, {"next": "11:00"})
            self.make_trace(root, "nap_none", {"next": None}, {"next": None})
            results = parity.collect(root, 2.0)
            features = {"Next nap": {"present": True, "experiments": ["nap_ok", "nap_bad"]},
                        "Widgets": {"present": False}}
            count = parity.totals(results, features)
            text = parity.render(results, features, count)
        self.assertEqual((count["behaviour_ok"], count["behaviour_total"]), (1, 3))
        self.assertEqual((count["breadth_ok"], count["breadth_total"]), (1, 2))
        self.assertIn("| Next nap | nap_ok, nap_bad | 1/2 match |", text)
        self.assertIn("| Widgets | - | missing |", text)

    def test_regression_is_reported(self):
        self.assertEqual(parity.regressions({"behaviour_ok": 3, "visual_ok": 5, "breadth_ok": 2},
                                            {"behaviour_ok": 4, "visual_ok": 5, "breadth_ok": 2}),
                         ["behaviour_ok: 4 -> 3"])


class RootCommandTest(unittest.TestCase):
    def test_su_wraps_and_quotes_command(self):
        adb = adbutil.Adb.__new__(adbutil.Adb)
        adb.via_su = True
        self.assertEqual(adb.root_command("cd /data/data/x && tar -cf - 'a b'"),
                         "su -c 'cd /data/data/x && tar -cf - '\"'\"'a b'\"'\"''")
        adb.via_su = False
        self.assertEqual(adb.root_command("date 0101"), "date 0101")


class InventoryTest(unittest.TestCase):
    def test_ui_strings_filter_code_and_keep_text(self):
        kept = inventory.ui_strings([
            "Start nap", "Next nap", "When is your baby’s next nap?", "_privateField", "package:x/y.dart",
            "getScrollPhysics", "a=b; c", "Start nap", "Профіль дитини",
        ])
        self.assertEqual(kept, ["Next nap", "Start nap", "When is your baby’s next nap?", "Профіль дитини"])

    def test_printable_runs_split_on_invalid_bytes(self):
        runs = inventory.printable_runs(b"\x01Start nap\xb4LogActivity\x00Statisztik\xc3\xa1k\x02")
        self.assertIn("Start nap", runs)
        self.assertIn("LogActivity", runs)
        self.assertIn("Statisztikák", runs)

    def test_dex_string_table(self):
        strings = [b"Lcom/app/SleepActivity;", b"hello"]
        data = bytearray(b"dex\n035\x00" + b"\x00" * 0x68)
        offsets = []
        table_at = len(data)
        data += b"\x00" * (4 * len(strings))
        for value in strings:
            offsets.append(len(data))
            data += bytes([len(value)]) + value + b"\x00"
        for index, offset in enumerate(offsets):
            data[table_at + 4 * index: table_at + 4 * index + 4] = offset.to_bytes(4, "little")
        data[0x38:0x3C] = len(strings).to_bytes(4, "little")
        data[0x3C:0x40] = table_at.to_bytes(4, "little")
        self.assertEqual(inventory.dex_strings(bytes(data)), ["Lcom/app/SleepActivity;", "hello"])

    def test_dex_constants_become_ui_text_candidates(self):
        kept = inventory.ui_strings(["Lcom/app/A;", "Start the nap timer", "Tap here to add a feeding"])
        self.assertEqual(kept, ["Start the nap timer", "Tap here to add a feeding"])

    def test_manifest_widgets_and_deep_links(self):
        manifest = """<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.x">
          <uses-permission android:name="android.permission.VIBRATE"/>
          <application>
            <activity android:name=".Main"><intent-filter>
              <data android:scheme="app" android:host="widget"/></intent-filter></activity>
            <receiver android:name=".W"><meta-data android:name="android.appwidget.provider"/></receiver>
          </application></manifest>"""
        with tempfile.NamedTemporaryFile("w", suffix=".xml") as handle:
            handle.write(manifest)
            handle.flush()
            info = inventory.parse_manifest(Path(handle.name))
        self.assertEqual(info["package"], "com.x")
        self.assertEqual(info["deep_links"], ["app://widget"])
        self.assertEqual(info["widgets"], [".W"])
        self.assertEqual(info["permissions"], ["android.permission.VIBRATE"])


if __name__ == "__main__":
    unittest.main()
