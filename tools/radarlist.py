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
    if text.startswith("\ufeff"):
        return ["file must be UTF-8 without BOM"], []
    errors, warnings = [], []
    today = datetime.date.fromisoformat(today) if today else datetime.date.today()
    lines = text.split("\n")
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
        else:   # a malformed id stays out of seen/prev, or it would flag every row after it
            if pid in seen:
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


# --- ids, retirement and applying the review map -------------------------------------------------


def read_retired(path=RETIRED_PATH):
    """id -> "date,reason". Skips # lines and blanks."""
    retired = {}
    if not os.path.isfile(path):
        return retired
    with open(path, encoding="utf-8", newline="") as fh:
        for line in fh.read().splitlines():
            if line.strip() == "" or line.startswith("#"):
                continue
            rid, _, rest = line.partition(",")
            retired[rid] = rest
    return retired


def check_ids(rows, retired, base_ids):
    """Errors for ids that vanished without being retired, and retired ids that came back."""
    have = {r["id"] for r in rows}
    errors = ["%s was removed: add it to data/retired.txt" % i for i in sorted(base_ids - have - set(retired))]
    errors += ["%s is retired and can't come back" % i for i in sorted(have & set(retired))]
    return errors


def next_id(rows, retired):
    """mao-%04d of 1 + the highest number among rows and retired ids (never reuses a retired id)."""
    nums = [int(i[4:]) for i in [r["id"] for r in rows] + list(retired)]
    return "mao-%04d" % (max(nums, default=0) + 1)


def _clean_label(label):
    return " ".join(str(label).replace(",", " ").replace('"', "").split())


def apply_placed(csv_path, retired_path, placed, today=None):
    """Applies the confirmed items of the review map. Returns (added, updated).

    Raises ValueError, leaving the file untouched, if an item is not confirmed, an id is unknown or
    retired, or the result fails validate.
    """
    today = today or datetime.date.today().isoformat()
    rows = read_rows(csv_path)
    retired = read_retired(retired_path)
    by_id = {r["id"]: r for r in rows}
    added = updated = 0
    for it in placed:
        if it.get("confirmed") is not True:
            raise ValueError("item is not confirmed: %r" % (it,))
        iid = it.get("id")
        if iid is not None and iid in retired:
            raise ValueError("%s is retired and can't come back" % iid)
        if iid is not None and iid not in by_id:
            raise ValueError("unknown id %s" % iid)
        try:
            fields = {"kind": it.get("kind"), "lat": float(it.get("lat")), "lon": float(it.get("lon")),
                      "heading": it.get("heading"),
                      "limit": int(it["limit"]) if it.get("limit") not in (None, "") else None,
                      "label": _clean_label(it.get("label", "")), "checked": today}
        except (TypeError, ValueError) as e:
            raise ValueError("bad item %r: %s" % (it, e))
        if iid is not None:
            by_id[iid].update(fields)
            updated += 1
        else:
            row = dict(fields, id=next_id(rows, retired), source=it.get("source"))
            rows.append(row)
            by_id[row["id"]] = row
            added += 1
    text = rows_text(rows)
    errors = validate(text, today)[0]
    if errors:
        raise ValueError("the result is invalid: " + "; ".join(errors))
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return added, updated
