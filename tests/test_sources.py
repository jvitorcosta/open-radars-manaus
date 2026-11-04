"""Host tests for tools/sources.py (no network). Run: python -m pytest tests/test_sources.py"""
import os

import sources as src

HERE = os.path.dirname(os.path.abspath(__file__))


def test_parse_immu_lists():
    html = open(os.path.join(HERE, "testdata", "immu_inforadar.html"), encoding="utf-8").read()
    items = src.parse_immu(html)
    by = {}
    for it in items:
        by.setdefault(it["kind"], []).append(it)
    assert len(by["speed"]) == 13 and len(by["bump"]) == 2 and len(by["redlight"]) == 5
    assert all(it["sentido"] for it in items)
    first = by["speed"][0]
    assert first["sentido"] == "Oeste" and first["heading"] == 270 and first["source"] == "immu"
    assert "Santos Dumont" in first["address"]
    assert "," not in first["label"] and "·" in first["label"]


def test_survey_rows_are_speed_60():
    s = src.survey_items()
    assert len(s) == 7
    assert all(i["kind"] == "speed" and i["limit"] == 60 and i["source"] == "survey" for i in s)


def test_parse_overpass():
    data = {"elements": [{"type": "node", "id": 7, "lat": -3.05, "lon": -60.01, "tags": {"maxspeed": "60", "name": "Radar X"}},
                         {"type": "node", "id": 8, "lat": -3.06, "lon": -60.02, "tags": {}}]}
    items = src.parse_overpass(data)
    assert items[0]["limit"] == 60 and items[0]["lat"] == -3.05 and items[0]["source"] == "osm"
    assert items[1]["limit"] is None


def test_match_by_distance():
    row = {"kind": "speed", "lat": -3.100000, "lon": -60.000000, "label": "Totally different"}
    near = {"kind": "speed", "lat": -3.100300, "lon": -60.0, "label": "Other words"}   # ~33 m
    far = {"kind": "speed", "lat": -3.101000, "lon": -60.0, "label": "Other words"}    # ~111 m
    assert src.matches(near, row)
    assert not src.matches(far, row)


def test_match_by_label_words():
    row = {"kind": "speed", "lat": -3.1, "lon": -60.0, "label": "Av. Torquato Tapajós · Flores"}
    it = {"kind": "speed", "label": "Avenida Torquato Tapajós · Flores"}
    assert src.matches(it, row)
    assert not src.matches({"kind": "speed", "label": "Av. Autaz Mirim · Coroado"}, row)


def test_diff_new_and_gone():
    rows = [{"id": "mao-0001", "kind": "speed", "lat": -3.1, "lon": -60.0, "label": "Av. Torquato Tapajós · Flores", "source": "immu"},
            {"id": "mao-0002", "kind": "speed", "lat": -3.2, "lon": -60.0, "label": "Av. Autaz Mirim · Coroado", "source": "immu"},
            {"id": "mao-0003", "kind": "speed", "lat": -3.3, "lon": -60.0, "label": "Mine", "source": "car"}]
    items = [{"kind": "speed", "label": "Av. Torquato Tapajós · Flores"}, {"kind": "speed", "label": "Av. Codajás · Petrópolis"}]
    new, gone = src.diff(items, rows)
    assert [i["label"] for i in new] == ["Av. Codajás · Petrópolis"]
    assert [r["id"] for r in gone] == ["mao-0002"]        # car-sourced rows are never "gone"


def test_diff_never_drops_community_rows():
    rows = [{"id": "mao-0001", "kind": "speed", "lat": -3.1, "lon": -60.0, "label": "Av. Torquato Tapajós · Flores", "source": "community"},
            {"id": "mao-0002", "kind": "speed", "lat": -3.2, "lon": -60.0, "label": "Av. Autaz Mirim · Coroado", "source": "immu"}]
    new, gone = src.diff([], rows)
    assert new == []
    assert [r["id"] for r in gone] == ["mao-0002"]        # community rows are never "gone"


def _pair(label_a, label_b, heading):
    return src.matches({"kind": "speed", "label": label_a, "heading": heading},
                       {"kind": "speed", "lat": -3.1, "lon": -60.0, "label": label_b, "heading": heading})


def test_same_street_other_district_is_another_camera():
    assert not _pair("Av. Torquato Tapajós · Da Paz", "Av. Torquato Tapajós · Flores", 180)
    assert not _pair("Av. Autaz Mirim · Coroado", "Av. Autaz Mirim · Zumbi dos Palmares", 180)
    assert not _pair("Av. Codajás/Av. Marquês da Silveira · Petrópolis",
                     "Av. Codajás/Av. Marquês da Silveira · São Francisco", 270)
    assert _pair("Av. Torquato Tapajós · Flores", "Av. Torquato Tapajós · Flores", 180)


def test_heading_tolerance():
    def m(h_item, h_row):
        return src.matches({"kind": "speed", "label": "Av. Torquato Tapajós · Flores", "heading": h_item},
                           {"kind": "speed", "lat": -3.1, "lon": -60.0, "label": "Av. Torquato Tapajós · Flores", "heading": h_row})
    assert m(270, 255)
    assert m(10, 350)
    assert not m(90, 270)


def test_user_agent_has_no_personal_address():
    assert "@" not in src.USER_AGENT and "github.com" in src.USER_AGENT
    assert "open-radars-manaus" in src.USER_AGENT
