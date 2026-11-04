"""The Manaus radar list (data/radars.csv): its schema, the validation rules and reading/writing rows.

The rules start from car-cyberdeck's tools/cameras.py (MIT, same author), without the device limits.
"""
import csv
import datetime
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(ROOT, "data", "radars.csv")
RETIRED_PATH = os.path.join(ROOT, "data", "retired.txt")
GEOJSON_PATH = os.path.join(ROOT, "data", "radars.geojson")

HEADER = "id,kind,lat,lon,heading,limit,label,source,checked"
KINDS = ("speed", "bump", "redlight")
SOURCES = ("immu", "osm", "survey", "car", "community")
BBOX_S, BBOX_W, BBOX_N, BBOX_E = -3.25, -60.15, -2.90, -59.80
MAX_LABEL = 27      # a label over this many UTF-8 bytes is cut by small displays: a warning only

# --- validation ----------------------------------------------------------------------------------


def _degrees_ok(s, max_deg):
    # re.A: ASCII digits only (Unicode digits match \d, and float() takes them)
    return re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)", s, re.A) is not None and abs(float(s)) <= max_deg


def _uint_ok(s, lo, hi):
    """ASCII digits only (str.isdigit() takes "²" and "٦٠"), lo..hi."""
    return re.fullmatch(r"\d+", s, re.A) is not None and lo <= int(s) <= hi


def _date_ok(s):
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s, re.A) is None:
        return None
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def validate(text, today=None):
    """Returns (errors, warnings). Messages about a row start with 'line N:'."""
    if "\r" in text:
        return ["line endings must be LF"], []
    errors, warnings = [], []
    today = datetime.date.fromisoformat(today) if today else datetime.date.today()
    lines = text.lstrip("﻿").split("\n")
    while len(lines) > 1 and lines[-1] == "":
        lines.pop()
    if lines[0] != HEADER:
        return ["line 1: header must be exactly " + HEADER], warnings
    seen = set()
    prev = None
    for no, line in enumerate(lines[1:], start=2):
        f = line.split(",")
        if len(f) != 9:
            errors.append("line %d: %d columns, need 9 (a comma in a label is not allowed)" % (no, len(f)))
            continue
        pid, kind, lat, lon, head, limit, label, source, checked = f
        if re.fullmatch(r"mao-\d{4}", pid, re.A) is None:
            errors.append("line %d: id must look like mao-0001" % no)
        elif pid in seen:
            errors.append("line %d: duplicate id %s" % (no, pid))
        elif prev is not None and pid < prev:
            errors.append("line %d: rows must be sorted by id (%s after %s)" % (no, pid, prev))
        seen.add(pid)
        prev = pid if prev is None or pid > prev else prev
        if kind not in KINDS:
            errors.append("line %d: kind must be speed, bump or redlight" % no)
        lat_ok, lon_ok = _degrees_ok(lat, 90), _degrees_ok(lon, 180)
        if not lat_ok:
            errors.append("line %d: lat out of range" % no)
        if not lon_ok:
            errors.append("line %d: lon out of range" % no)
        if lat_ok and lon_ok and not (BBOX_S <= float(lat) <= BBOX_N and BBOX_W <= float(lon) <= BBOX_E):
            errors.append("line %d: (lat, lon) is outside Manaus (%.2f..%.2f, %.2f..%.2f)"
                          % (no, BBOX_S, BBOX_N, BBOX_W, BBOX_E))
        if not _uint_ok(head, 0, 359):
            errors.append("line %d: heading is required, 0..359 (a radar without a direction would alert both lanes)" % no)
        if limit != "":
            if kind == "redlight":
                errors.append("line %d: a redlight has no limit" % no)
            elif not _uint_ok(limit, 1, 199):
                errors.append("line %d: limit must be empty or 1..199" % no)
        if '"' in line:   # no CSV quoting: other tools would read a quote as one and re-split the row
            errors.append('line %d: a " is not allowed (like commas, quotes stay out of labels)' % no)
        if len(label.encode("utf-8")) > MAX_LABEL:
            warnings.append("line %d: label is %d bytes, small displays show the first %d"
                            % (no, len(label.encode("utf-8")), MAX_LABEL))
        if source not in SOURCES:
            errors.append("line %d: source must be one of %s" % (no, ", ".join(SOURCES)))
        day = _date_ok(checked)
        if day is None:
            errors.append("line %d: checked is required, a date as YYYY-MM-DD" % no)
        elif day > today:
            errors.append("line %d: checked %s is in the future" % (no, checked))
    return errors, warnings


# --- the list on disk ----------------------------------------------------------------------------


def read_rows(path=CSV_PATH):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [{"id": r["id"], "kind": r["kind"], "lat": float(r["lat"]), "lon": float(r["lon"]),
             "heading": int(r["heading"]), "limit": int(r["limit"]) if r["limit"] else None,
             "label": r["label"], "source": r["source"], "checked": r["checked"]} for r in rows]


def rows_text(rows):
    lines = [HEADER]
    for r in sorted(rows, key=lambda r: r["id"]):
        lines.append(",".join([r["id"], r["kind"], "%.6f" % r["lat"], "%.6f" % r["lon"], str(r["heading"]),
                               "" if r["limit"] is None else str(r["limit"]), r["label"], r["source"], r["checked"]]))
    return "\n".join(lines) + "\n"
