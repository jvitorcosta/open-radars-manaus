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


def matches(csv_path=CSV_PATH, geojson_path=GEOJSON_PATH):
    """True when the committed GeoJSON is exactly what build() gives for the committed CSV."""
    if not os.path.isfile(geojson_path):
        return False
    with open(geojson_path, encoding="utf-8", newline="") as fh:
        return fh.read() == build(read_rows(csv_path))
