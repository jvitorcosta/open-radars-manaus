import json
import os
import urllib.error

import autoplace
import sources

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)["elements"]


def bearing_gap(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def test_snap_split_carriageway_picks_the_side_of_sentido():
    ways = load("ways_split.json")
    lat, lon = -3.080068, -60.0200     # between the two carriageways
    west = autoplace.snap(lat, lon, ways, 270)
    assert abs(west[0] - -3.080000) < 1e-5 and bearing_gap(west[2], 270) <= 10
    east = autoplace.snap(lat, lon, ways, 90)
    assert abs(east[0] - -3.080136) < 1e-5 and bearing_gap(east[2], 90) <= 10


def test_snap_twoway_takes_the_direction_nearest_sentido():
    ways = load("ways_twoway.json")    # runs north-east / south-west
    lat, lon, h = autoplace.snap(-3.0795, -60.0190, ways, 270)
    assert bearing_gap(h, 225) <= 3
    lat, lon, h = autoplace.snap(-3.0795, -60.0190, ways, 0)
    assert bearing_gap(h, 45) <= 3


def test_snap_unknown_sentido_on_twoway_has_no_heading():
    ways = load("ways_twoway.json")
    lat, lon, h = autoplace.snap(-3.0795, -60.0190, ways, None)
    assert h is None and lat is not None


def test_snap_unknown_sentido_on_oneway_keeps_its_heading():
    lat, lon, h = autoplace.snap(-3.080000, -60.0200, load("ways_split.json"), None)
    assert bearing_gap(h, 270) <= 3


def test_snap_no_ways_returns_none():
    assert autoplace.snap(-3.08, -60.02, [], 90) is None
    # a one-way running the wrong way for sentido leaves no candidate
    assert autoplace.snap(-3.08, -60.02, load("ways_split.json")[:1], 90) is None


def test_fetch_ways_keeps_matching_names_nearby(monkeypatch):
    elements = load("ways_split.json") + [
        {"type": "way", "id": 9, "tags": {"name": "Rua das Flores", "highway": "residential"},
         "geometry": [{"lat": -3.08, "lon": -60.02}, {"lat": -3.081, "lon": -60.02}]},
        {"type": "way", "id": 10, "tags": {"name": "Avenida Djalma Batista", "highway": "primary"},
         "geometry": [{"lat": -3.2, "lon": -60.1}, {"lat": -3.201, "lon": -60.1}]}]
    monkeypatch.setattr(autoplace, "road_network", lambda: elements)
    ways = autoplace.fetch_ways(-3.08, -60.02, "Avenida Djalma Batista")
    assert [w["id"] for w in ways] == [1001, 1002]


def test_street_of():
    assert autoplace.street_of("Avenida Djalma Batista, nº 900 – Chapada, sentido Leste") == "Avenida Djalma Batista"
    assert autoplace.street_of("Av. do Turismo/Av. Thales Loureiro - Ponta Negra, sentido norte") == "Av. do Turismo"


def test_geocode_adds_viewbox_and_spaces_requests(monkeypatch):
    urls, sleeps = [], []
    monkeypatch.setattr(autoplace.time, "sleep", sleeps.append)
    monkeypatch.setattr(autoplace, "_last_geocode", [autoplace.time.time()])
    monkeypatch.setattr(autoplace, "http_req",
                        lambda url, **kw: (urls.append(url), (200, b'[{"lat": "-3.1", "lon": "-60.0"}]'))[1])
    item = {"address": "Avenida Djalma Batista, nº 900 – Chapada, sentido Leste"}
    assert autoplace.geocode(item) == (-3.1, -60.0)
    assert "viewbox=-60.15%2C-2.90%2C-59.80%2C-3.25" in urls[0] and "bounded=1" in urls[0]
    assert sleeps and 0 < sleeps[0] <= 1.1


def test_autoplace_survives_network_failure(monkeypatch):
    def boom(*a, **kw):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(autoplace, "http_req", boom)
    monkeypatch.setattr(autoplace.time, "sleep", lambda s: None)
    monkeypatch.setattr(autoplace, "_last_geocode", [0.0])
    out = autoplace.autoplace({"address": "Avenida Djalma Batista, sentido Leste", "heading": 90})
    assert (out["lat"], out["lon"]) == autoplace.CENTRE
    assert out["heading"] is None and out["guess"] is True


def test_autoplace_keeps_geocoded_spot_when_ways_fail(monkeypatch):
    monkeypatch.setattr(autoplace, "geocode", lambda item: (-3.08, -60.02))

    def boom(*a, **kw):
        raise urllib.error.URLError("down")

    monkeypatch.setattr(autoplace, "fetch_ways", boom)
    out = autoplace.autoplace({"address": "Avenida Djalma Batista", "heading": 90})
    assert (out["lat"], out["lon"], out["heading"], out["guess"]) == (-3.08, -60.02, None, True)


def test_autoplace_uses_snap_when_found(monkeypatch):
    monkeypatch.setattr(autoplace, "geocode", lambda item: (-3.08, -60.02))
    monkeypatch.setattr(autoplace, "fetch_ways", lambda lat, lon, street: ["way"])
    monkeypatch.setattr(autoplace, "snap", lambda lat, lon, ways, want: (-3.0801, -60.0201, 270))
    item = {"address": "Avenida Djalma Batista, sentido Oeste", "heading": 270, "label": "x"}
    out = autoplace.autoplace(item)
    assert (out["lat"], out["lon"], out["heading"], out["guess"]) == (-3.0801, -60.0201, 270, True)
    assert out["label"] == "x"


def test_geocode_survives_an_unexpected_nominatim_shape(monkeypatch):
    monkeypatch.setattr(autoplace.time, "sleep", lambda s: None)
    item = {"address": "Avenida Teste, nº 1 – Centro"}
    for body in (b'{"error": "rate limited"}', b'[{"nolat": 1}]', b'[null]', b'"text"', b'[[]]'):
        monkeypatch.setattr(autoplace, "http_req", lambda url, body=body: (200, body))
        assert autoplace.geocode(item) is None
        out = autoplace.autoplace(item)
        assert out["guess"] is True and (out["lat"], out["lon"]) == autoplace.CENTRE
