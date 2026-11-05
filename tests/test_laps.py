import json

import laps
import radars

# A drive north along a meridian (~11 m a point), then east; Lap pressed at points 5 and 12.
NORTH = [[-3.1200 + 0.0001 * k, -60.0200] for k in range(10)]
EAST = [[NORTH[-1][0], -60.0200 + 0.0001 * k] for k in range(1, 10)]
DRIVE = {"activity": 42, "latlng": NORTH + EAST, "time": [4 * k for k in range(19)],
         "laps": [{"start_index": 0, "end_index": 5}, {"start_index": 6, "end_index": 12},
                  {"start_index": 13, "end_index": 18}]}


def test_each_press_is_a_mark_and_the_stop_lap_is_not():
    marks = laps.marks_from_laps(DRIVE)
    assert [(m["lat"], m["lon"]) for m in marks] == [tuple(DRIVE["latlng"][5]), tuple(DRIVE["latlng"][12])]
    assert all(m["source"] == "car" and m["how"] == "car" and m["guess"] for m in marks)
    assert marks[0]["address"] == "Lap 1 at 0:20 of activity 42"


def test_heading_follows_the_track_into_the_press():
    north, east = laps.marks_from_laps(DRIVE)
    assert north["heading"] == 0
    assert east["heading"] == 90


def test_heading_needs_some_distance_behind():
    assert laps.heading_at(NORTH, 1) is None          # 11 m back is under BACK_M
    assert laps.heading_at(NORTH, 2) == 0


def test_a_drive_without_presses_has_no_marks():
    assert laps.marks_from_laps(dict(DRIVE, laps=[{"start_index": 0, "end_index": 18}])) == []
    assert laps.marks_from_laps(dict(DRIVE, laps=[{"end_index": 99}, {"end_index": 18}])) == []


def test_place_from_laps_writes_the_review_map(monkeypatch, tmp_path):
    monkeypatch.setattr(radars.os.path, "relpath", lambda p, start=None: p)   # tmp_path may be on another drive
    src = tmp_path / "drive.json"
    src.write_text(json.dumps(DRIVE), encoding="utf-8")
    out = tmp_path / "review_map.html"
    monkeypatch.setattr(radars, "PLACE_HTML", str(out))
    monkeypatch.setattr(radars.autoplace, "autoplace", lambda it: (_ for _ in ()).throw(AssertionError("no guessing")))
    assert radars.main(["place", "--from", "laps", "--file", str(src), "--no-serve"]) == 0
    assert "Lap 2 at 0:48 of activity 42" in out.read_text(encoding="utf-8")
