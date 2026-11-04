"""Host tests for the ids, retirement and applying the review map (no network)."""
import pytest

import radarlist as rl


def mk(n, source="car", lat=-3.1, limit=60, kind="speed", label="A"):
    return {"id": "mao-%04d" % n, "kind": kind, "lat": lat, "lon": -60.0, "heading": 90, "limit": limit,
            "label": label, "source": source, "checked": "2026-11-01"}


def item(**kw):
    d = {"kind": "speed", "lat": -3.2, "lon": -60.1, "heading": 180, "limit": 50, "label": "Nova",
         "source": "survey", "confirmed": True}
    d.update(kw)
    return d


@pytest.fixture
def files(tmp_path):
    csv_path, retired = tmp_path / "radars.csv", tmp_path / "retired.txt"
    csv_path.write_bytes(rl.rows_text([mk(1), mk(2, source="immu")]).encode("utf-8"))
    retired.write_text("# id,date,reason\nmao-0005,2026-10-01,gone\n\n", encoding="utf-8")
    return str(csv_path), str(retired)


def test_read_retired_skips_comments_and_blanks(files):
    assert rl.read_retired(files[1]) == {"mao-0005": "2026-10-01,gone"}


def test_next_id_skips_retired():
    assert rl.next_id([mk(1), mk(2)], {"mao-0005": "2026-10-01,gone"}) == "mao-0006"


def test_next_id_empty():
    assert rl.next_id([], {}) == "mao-0001"


def test_check_ids_flags_silent_removal():
    errs = rl.check_ids([mk(1)], {}, {"mao-0001", "mao-0003"})
    assert errs == ["mao-0003 was removed: add it to data/retired.txt"]


def test_check_ids_flags_resurrection():
    errs = rl.check_ids([mk(1), mk(3)], {"mao-0003": "2026-10-01,gone"}, {"mao-0001"})
    assert errs == ["mao-0003 is retired and can't come back"]


def test_check_ids_ok_when_retired_properly():
    assert rl.check_ids([mk(1)], {"mao-0003": "2026-10-01,gone"}, {"mao-0001", "mao-0003"}) == []


def test_apply_appends_with_next_id(files):
    assert rl.apply_placed(files[0], files[1], [item()], today="2026-11-04") == (1, 0)
    rows = rl.read_rows(files[0])
    new = rows[-1]
    assert new["id"] == "mao-0006" and new["source"] == "survey" and new["checked"] == "2026-11-04"
    assert new["heading"] == 180 and new["limit"] == 50 and len(rows) == 3


def test_apply_updates_by_id_and_keeps_source(files):
    moved = item(id="mao-0002", lat=-3.1002, lon=-60.0, heading=91, limit=40, label="Movida", source="survey")
    assert rl.apply_placed(files[0], files[1], [moved], today="2026-11-04") == (0, 1)
    row = [r for r in rl.read_rows(files[0]) if r["id"] == "mao-0002"][0]
    assert row["lat"] == -3.1002 and row["limit"] == 40 and row["heading"] == 91
    assert row["label"] == "Movida" and row["checked"] == "2026-11-04" and row["source"] == "immu"
    assert len(rl.read_rows(files[0])) == 2


def _refused(files, items, match):
    before = open(files[0], "rb").read()
    with pytest.raises(ValueError, match=match):
        rl.apply_placed(files[0], files[1], items, today="2026-11-04")
    assert open(files[0], "rb").read() == before


def test_apply_refuses_unconfirmed(files):
    _refused(files, [item(), item(confirmed=False)], "confirmed")


def test_apply_refuses_unknown_id(files):
    _refused(files, [item(), item(id="mao-0009")], "unknown")


def test_apply_refuses_retired_id(files):
    _refused(files, [item(id="mao-0005")], "retired")


def test_apply_refuses_an_invalid_result(files):
    bad = item()
    del bad["heading"]
    _refused(files, [bad], "heading")


def test_apply_strips_quotes_from_labels(files):
    rl.apply_placed(files[0], files[1], [item(label='  Av. "Brasil",  Centro ')], today="2026-11-04")
    assert rl.read_rows(files[0])[-1]["label"] == "Av. Brasil Centro"
