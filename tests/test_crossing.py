import urllib.error

import pytest

import autoplace
import sources

LAT0, LON0 = -3.1, -60.0
M_LON, M_LAT = 111157.0, 110574.0   # metres per degree near 3.1 S


def node(nid, lat, lon):
    return nid, {"lat": lat, "lon": lon}


def way(wid, name, nodes, oneway=None):
    tags = {"highway": "secondary", "name": name}
    if oneway:
        tags["oneway"] = oneway
    return {"type": "way", "id": wid, "tags": tags,
            "nodes": [n for n, _ in nodes], "geometry": [g for _, g in nodes]}


N2 = node(2, LAT0, LON0)
TWO_WAY = [
    way(1, "Avenida Alfa Beta", [node(1, LAT0, -60.001), N2, node(3, LAT0, -59.999)]),
    way(2, "Rua Gama Delta", [node(4, -3.101, LON0), N2, node(5, -3.099, LON0)]),
    way(3, "Rua Sem Saida", [node(6, -3.105, -60.01), node(7, -3.106, -60.01)]),
]

N12, N22 = node(12, LAT0, LON0), node(22, -3.1002, LON0)
DUAL = [
    way(11, "Avenida Epsilon Eta", [node(11, LAT0, -60.001), N12, node(13, LAT0, -59.999)], oneway="yes"),
    way(21, "Avenida Epsilon Eta", [node(23, -3.1002, -59.999), N22, node(21, -3.1002, -60.001)], oneway="yes"),
    way(31, "Rua Zeta Teta", [node(31, -3.102, LON0), N22, N12, node(32, -3.098, LON0)]),
]


def near(a, b, metres=2.0):
    return abs(a[0] - b[0]) * M_LAT <= metres and abs(a[1] - b[1]) * M_LON <= metres


def test_crossing_two_way_east_sits_before_the_junction():
    lat, lon, h = autoplace.at_crossing(TWO_WAY, "Avenida Alfa Beta", "Rua Gama Delta", 90)
    assert near((lat, lon), (LAT0, LON0 - 15 / M_LON))
    assert h == 90


def test_crossing_two_way_west_sits_on_the_other_side():
    lat, lon, h = autoplace.at_crossing(TWO_WAY, "Avenida Alfa Beta", "Rua Gama Delta", 270)
    assert near((lat, lon), (LAT0, LON0 + 15 / M_LON))
    assert h == 270


def test_crossing_without_sentido_is_the_junction_with_no_heading():
    assert autoplace.at_crossing(TWO_WAY, "Avenida Alfa Beta", "Rua Gama Delta", None) == (LAT0, LON0, None)


def test_crossing_dual_carriageway_takes_the_first_junction_reached():
    lat, lon, h = autoplace.at_crossing(DUAL, "Rua Zeta Teta", "Avenida Epsilon Eta", 0)
    assert near((lat, lon), (-3.1002 - 15 / M_LAT, LON0))
    assert h == 0


def test_crossing_dual_carriageway_takes_the_carriageway_of_sentido():
    lat, lon, h = autoplace.at_crossing(DUAL, "Avenida Epsilon Eta", "Rua Zeta Teta", 270)
    assert near((lat, lon), (-3.1002, LON0 + 15 / M_LON))
    assert h == 270
    lat, lon, h = autoplace.at_crossing(DUAL, "Avenida Epsilon Eta", "Rua Zeta Teta", 90)
    assert near((lat, lon), (LAT0, LON0 - 15 / M_LON))
    assert h == 90


def test_crossing_of_roads_that_never_meet_is_none():
    assert autoplace.at_crossing(TWO_WAY, "Avenida Alfa Beta", "Rua Sem Saida", 90) is None


def test_crossing_of_roads_that_nearly_meet_is_where_they_come_closest():
    gap = [way(1, "Avenida Alfa Beta", [node(1, LAT0, -60.001), N2, node(3, LAT0, -59.999)]),
           way(2, "Rua Gama Delta", [node(4, -3.101, LON0), node(5, LAT0 - 20 / M_LAT, LON0)])]
    assert autoplace.at_crossing(gap, "Avenida Alfa Beta", "Rua Gama Delta", None) == (LAT0, LON0, None)
    far = [gap[0], way(2, "Rua Gama Delta", [node(4, -3.101, LON0), node(5, LAT0 - 60 / M_LAT, LON0)])]
    assert autoplace.at_crossing(far, "Avenida Alfa Beta", "Rua Gama Delta", None) is None


def test_crossing_prefers_the_road_with_the_whole_name():
    beco = way(9, "Beco Gama Delta", [node(8, LAT0, -60.0005), node(9, -3.101, -60.0005)])
    beco["nodes"][0] = 1                                        # meets the avenue at its first node
    lat, lon, _ = autoplace.at_crossing(TWO_WAY + [beco], "Avenida Alfa Beta", "Rua Gama Delta", None)
    assert (lat, lon) == (LAT0, LON0)


def test_crossing_reads_old_spellings():
    assert autoplace.at_crossing(TWO_WAY, "Avenida Alfa Beta", "Rua Gamma Dellta", None) == (LAT0, LON0, None)
    assert autoplace._named({"tags": {"name": "Avenida Coronel Cyrilo Neves"}}, "Avenida Coronel Cyrillo Neves")


def test_crossing_takes_a_sentido_that_is_only_roughly_right():
    lat, lon, h = autoplace.at_crossing(TWO_WAY, "Avenida Alfa Beta", "Rua Gama Delta", 30)
    assert h == 90 and near((lat, lon), (LAT0, LON0 - 15 / M_LON))


def test_autoplace_prefers_the_crossing(monkeypatch):
    monkeypatch.setattr(autoplace, "fetch_crossing_ways", lambda s, c: TWO_WAY)
    monkeypatch.setattr(autoplace, "geocode", lambda it: pytest.fail("no geocoding when the crossing is found"))
    it = autoplace.autoplace({"kind": "redlight", "address": "x", "street": "Avenida Alfa Beta",
                              "cross": "Rua Gama Delta", "heading": 90})
    assert it["guess"] is True and it["heading"] == 90 and near((it["lat"], it["lon"]), (LAT0, LON0 - 15 / M_LON))
    assert it["how"] == "crossing"


def test_autoplace_falls_back_when_the_crossing_fails(monkeypatch):
    def boom(s, c):
        raise urllib.error.URLError("down")
    monkeypatch.setattr(autoplace, "fetch_crossing_ways", boom)
    monkeypatch.setattr(autoplace, "geocode", lambda it: None)
    it = autoplace.autoplace({"kind": "redlight", "address": "Avenida X – Centro", "street": "Avenida X",
                              "cross": "Rua Y", "heading": 90})
    assert (it["lat"], it["lon"]) == autoplace.CENTRE and it["heading"] is None and it["how"] == "none"


def test_road_network_is_read_from_the_cache(tmp_path, monkeypatch):
    cache = tmp_path / "roads.json"
    cache.write_text('[{"type": "way", "id": 1, "tags": {"name": "Rua X"}, "nodes": [], "geometry": []}]',
                     encoding="utf-8")
    monkeypatch.setattr(autoplace, "ROADS_PATH", str(cache))
    monkeypatch.setattr(autoplace, "_roads", [])
    monkeypatch.setattr(autoplace, "_overpass", lambda *a, **k: pytest.fail("no download while the cache is fresh"))
    assert [w["id"] for w in autoplace.road_network()] == [1]


def test_announced_lists_read():
    items = sources.announced_items()
    assert len(items) == 37
    assert {i["source"] for i in items} == {"immu"}
    tefe = [i for i in items if i["street"] == "Avenida Tefé" and i["cross"] == "Avenida Borba"]
    assert [i["heading"] for i in tefe] == [90, 270]
    assert len({i["label"] for i in items}) == len(items)      # same crossing, two directions: two labels
    bump = next(i for i in items if i["kind"] == "bump" and i["cross"] == "Travessa Doutor Alfredo da Mata")
    assert bump["limit"] == 40 and bump["label"] == "Av. São Jorge/Tv. Dr. Alfredo da Mata · São Jorge"
    assert all(i["kind"] in ("speed", "bump", "redlight") for i in items)


def test_immu_page_crossings_get_a_cross():
    it = {"address": "Avenida Codajás/Avenida Marquês da Silveira – Petrópolis, sentido Oeste"}
    assert sources.crossing_of(it["address"]) == ("Avenida Codajás", "Avenida Marquês da Silveira")
    assert sources.crossing_of("Avenida Professor Nilton Lins, nº 900 – Flores, sentido Leste") == (
        "Avenida Professor Nilton Lins", "")


def test_two_directions_at_one_spot_are_two_radars():
    a = {"kind": "redlight", "lat": LAT0, "lon": LON0, "heading": 90, "label": "A · X", "source": "immu"}
    b = dict(a, heading=270)
    assert not sources.matches(a, b)
    assert sources.matches(a, dict(a, heading=100))
