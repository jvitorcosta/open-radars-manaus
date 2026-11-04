"""Host tests for tools/radarlist.py (no network). Run: python -m pytest -q"""
import os

import radarlist as rl

HDR = "id,kind,lat,lon,heading,limit,label,source,checked\n"
HERE = os.path.dirname(os.path.abspath(__file__))
GOOD = os.path.join(HERE, "testdata", "good.csv")


def errors(body, today=None):
    return rl.validate(HDR + body, today)[0]


def row(n=1, kind="speed", lat="-3.1", lon="-60.0", head="90", limit="60", label="A", source="car",
        checked="2026-11-03"):
    return "mao-%04d,%s,%s,%s,%s,%s,%s,%s,%s\n" % (n, kind, lat, lon, head, limit, label, source, checked)


def test_validate_accepts_a_good_list():
    body = ("mao-0001,speed,-3.100000,-60.000000,270,60,Bench speed,car,2026-11-03\n"
            "mao-0003,redlight,-3.090000,-60.020000,180,,Bench light,car,2026-11-03\n")
    assert errors(body) == []


def test_validate_rejects_missing_heading():
    errs = errors(row(head=""))
    assert errs and "line 2" in errs[0] and "heading" in errs[0]


def test_validate_rejects_redlight_limit():
    errs = errors(row(kind="redlight", limit="60"))
    assert errs and "limit" in errs[0]


def test_validate_warns_on_long_label():
    errs, warns = rl.validate(HDR + row(label="ã" * 20))
    assert errs == [] and warns and "27" in warns[0]


def test_validate_rejects_unicode_digits():
    assert errors(row(head="²"))
    assert errors(row(head="٩٠"))
    assert errors(row(limit="٦٠"))
    assert errors(row(lat="-٣.1"))


def test_validate_rejects_quote_in_label():
    errs = errors(row(label='Av. "X"'))
    assert errs and "line 2" in errs[0] and '"' in errs[0]


def test_validate_rejects_bad_header_columns():
    assert rl.validate("id,kind\n")[0]
    assert errors("mao-0001,speed,-3.1,-60.0,90,60,A,B,car,2026-11-03\n")   # 10 columns
    assert errors(row(kind="boat"))
    assert errors(row(lat="-93.1"))
    assert errors(row(head="360"))
    assert errors(row(limit="200"))


def test_validate_has_no_device_limits():
    body = "".join(row(i, label="x" * 20) for i in range(1, 201))
    assert errors(body) == []


def test_validate_rejects_point_outside_manaus():
    errs = errors(row(lon="59.97"))
    assert any("outside Manaus" in e for e in errs)
    errs = errors(row(lon="-59.97"))
    assert errs == []
    assert any("outside Manaus" in e for e in errors(row(lat="-3.30")))


def test_validate_rejects_crlf():
    text = (HDR + row()).replace("\n", "\r\n")
    assert rl.validate(text)[0] == ["line endings must be LF"]


def test_validate_requires_checked():
    assert any("checked" in e for e in errors(row(checked="")))
    assert any("checked" in e for e in errors(row(checked="2026-13-01")))
    assert errors(row(checked="2026-11-04"), today="2026-11-04") == []
    assert any("future" in e for e in errors(row(checked="2026-11-05"), today="2026-11-04"))


def test_validate_rejects_bad_id_and_duplicates():
    assert any("id" in e for e in errors("mao-12,speed,-3.1,-60.0,90,60,A,car,2026-11-03\n"))
    assert any("id" in e for e in errors("abc-0001,speed,-3.1,-60.0,90,60,A,car,2026-11-03\n"))
    assert any("duplicate" in e for e in errors(row(1) + row(1)))


def test_validate_rejects_unsorted_rows():
    assert any("sorted" in e for e in errors(row(2) + row(1)))
    assert errors(row(1) + row(2)) == []


def test_validate_rejects_unknown_source():
    assert any("source" in e for e in errors(row(source="immu-survey")))
    for ok in rl.SOURCES:
        assert errors(row(source=ok)) == []


def test_rows_text_round_trips():
    text = open(GOOD, encoding="utf-8", newline="").read()
    assert rl.validate(text)[0] == []
    assert rl.rows_text(rl.read_rows(GOOD)) == text


def test_validate_bad_id_does_not_poison_sorting():
    # a malformed high-sorting id must not make the valid rows after it look unsorted
    errs = errors(row(1) + "zzz,speed,-3.1,-60.0,90,60,A,car,2026-11-03\n" + row(2))
    assert any("id must look like" in e for e in errs)
    assert not any("sorted" in e for e in errs)


def test_validate_rejects_a_bom():
    errs = rl.validate("﻿" + HDR + row(1))[0]
    assert errs == ["file must be UTF-8 without BOM"]
