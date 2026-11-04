"""Host tests for tools/geojson.py (no network). Run: python -m pytest -q"""
import json

import geojson as gj


def row(n=1, kind="speed", lat=-3.1, lon=-60.0, heading=90, limit=60, label="A", source="car",
        checked="2026-11-03"):
    return {"id": "mao-%04d" % n, "kind": kind, "lat": lat, "lon": lon, "heading": heading,
            "limit": limit, "label": label, "source": source, "checked": checked}


def test_geojson_point_is_lon_lat():
    doc = json.loads(gj.build([row(lat=-3.1, lon=-60.0)]))
    feature = doc["features"][0]
    assert feature["geometry"] == {"type": "Point", "coordinates": [-60.0, -3.1]}
    assert feature["properties"] == {"id": "mao-0001", "kind": "speed", "heading": 90, "limit": 60,
                                     "label": "A", "source": "car", "checked": "2026-11-03"}


def test_geojson_limit_null_for_redlight():
    doc = json.loads(gj.build([row(kind="redlight", limit=None)]))
    assert doc["features"][0]["properties"]["limit"] is None


def test_geojson_keeps_accents():
    text = gj.build([row(label="Tarumã · Centro")])
    assert "Tarumã" in text


def test_geojson_is_stable():
    rows = [row(n=2), row(n=1, kind="bump", limit=None)]
    assert gj.build(rows) == gj.build(rows)
    assert [f["properties"]["id"] for f in json.loads(gj.build(rows))["features"]] == ["mao-0001", "mao-0002"]


def test_geojson_empty_list():
    doc = json.loads(gj.build([]))
    assert doc["type"] == "FeatureCollection"
    assert doc["features"] == []
