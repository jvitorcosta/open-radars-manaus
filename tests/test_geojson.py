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


def test_map_block_is_a_geojson_fence():
    block = gj.map_block([row(n=2, kind="redlight", limit=None), row(n=1)])
    assert block.startswith("```geojson\n") and block.endswith("\n```\n")
    doc = json.loads(block[len("```geojson\n"):-len("```\n")])
    assert [f["properties"]["id"] for f in doc["features"]] == ["mao-0001", "mao-0002"]
    assert doc["features"][0]["properties"] == {"id": "mao-0001", "kind": "speed", "label": "A", "limit": 60}
    assert doc["features"][0]["geometry"]["coordinates"] == [-60.0, -3.1]


def test_with_map_replaces_only_between_the_markers():
    readme = "intro\n%s\nold map\n%s\nrest\n" % (gj.MAP_START, gj.MAP_END)
    new = gj.with_map(readme, [row()])
    assert new.startswith("intro\n" + gj.MAP_START + "\n```geojson\n")
    assert new.endswith("```\n" + gj.MAP_END + "\nrest\n")
    assert "old map" not in new
    assert gj.with_map(new, [row()]) == new
    assert gj.with_map("no markers here\n", [row()]) is None
