"""The GeoJSON export of the radar list (data/radars.geojson), built from the rows of data/radars.csv.

The output is the same bytes for the same rows, so a check can compare the committed file with a fresh build.
"""
import json
import os

from radarlist import CSV_PATH, GEOJSON_PATH, read_rows

NOT_PROPERTIES = ("lat", "lon")   # the position is the geometry, every other column is a property


def build(rows):
    """A FeatureCollection with one Point per row, in id order. Coordinates are [lon, lat]."""
    features = []
    for r in sorted(rows, key=lambda r: r["id"]):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(r["lon"], 6), round(r["lat"], 6)]},
            "properties": {k: v for k, v in r.items() if k not in NOT_PROPERTIES},
        })
    return json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=1) + "\n"


# The README's map: GitHub draws a ```geojson block as an interactive map. It sits between these markers
# and is rebuilt from the rows like the GeoJSON file, with one feature per line and a pin colour per kind.
MAP_START, MAP_END = "<!-- map:start -->", "<!-- map:end -->"
MAP_COLOURS = {"speed": "#c0392b", "bump": "#e67e22", "redlight": "#7d3c98"}
MAP_PROPERTIES = ("id", "kind", "label", "limit")


def map_block(rows):
    """The fenced ```geojson block for the README: the points with id, kind, label, limit and pin colour."""
    lines = []
    for r in sorted(rows, key=lambda r: r["id"]):
        props = {k: r[k] for k in MAP_PROPERTIES}
        props["marker-color"] = MAP_COLOURS[r["kind"]]
        lines.append(json.dumps({"type": "Feature", "properties": props, "geometry": {
            "type": "Point", "coordinates": [round(r["lon"], 6), round(r["lat"], 6)]}}, ensure_ascii=False))
    return ("```geojson\n" + '{"type": "FeatureCollection", "features": [\n' + ",\n".join(lines)
            + "\n]}\n```\n")


def with_map(readme, rows):
    """The README text with its map rebuilt from rows, or None when it has no map markers."""
    start, end = readme.find(MAP_START), readme.find(MAP_END)
    if start < 0 or end < start:
        return None
    return readme[:start + len(MAP_START)] + "\n" + map_block(rows) + readme[end:]


def matches(csv_path=CSV_PATH, geojson_path=GEOJSON_PATH):
    """True when the committed GeoJSON is exactly what build() gives for the committed CSV."""
    if not os.path.isfile(geojson_path):
        return False
    with open(geojson_path, encoding="utf-8", newline="") as fh:
        return fh.read() == build(read_rows(csv_path))
