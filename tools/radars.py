"""Manaus radar list tools: fetch, check, place, validate, geojson, release.

Ported from car-cyberdeck's tools/cameras.py (MIT, same author). Run from the repo root:
python tools/radars.py <command>.
"""
import argparse
import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error

import autoplace
import geojson
import laps
import mapsvg
import marks
import radarlist
from radarlist import CSV_PATH, GEOJSON_PATH, KINDS, RETIRED_PATH, ROOT
from sources import diff, fetch_immu, fetch_osm

TEMPLATE = os.path.join(ROOT, "tools", "review_map.html")
PLACE_HTML = os.path.join(ROOT, "build", "review_map.html")
DIST = os.path.join(ROOT, "dist")
MAP_SVG = os.path.join(ROOT, "docs", "map.svg")
MAP_OSM = os.path.join(ROOT, "build", "map-osm.json")
LISTS_DIR = os.path.join(ROOT, "tools", "lists")
APPLY_CMD = "python tools/radars.py place --apply caminho/para/placed.json"
VERSION_RE = r"\d{4}\.(0[1-9]|1[0-2])\.\d+"

# --- the review page -----------------------------------------------------------------------------


def write_place_page(items, out=None, apply_cmd=APPLY_CMD):
    """The page, its hint naming the command that takes its placed.json (`apply_cmd`)."""
    out = out or PLACE_HTML
    template = open(TEMPLATE, encoding="utf-8").read().replace("__APPLY__", apply_cmd)
    data = json.dumps(items, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(template.replace("__ITEMS__", data))
    return out


def serve(directory, page, port=8765):
    """Serves build/ on 127.0.0.1 so the page loads over http with a Referer (OSM refuses tiles without one)."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    handler.log_message = lambda *a, **k: None
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    print("open http://127.0.0.1:%d/%s  (Ctrl+C stops the server)" % (srv.server_address[1], page))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


# --- git -----------------------------------------------------------------------------------------


def _git(*args):
    """(returncode, stdout) of a git command run in the repo; (1, "") when git is missing."""
    try:
        p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    except OSError:
        return 1, ""
    return p.returncode, p.stdout


def _csv_at(ref):
    """The text of data/radars.csv at a git ref, or None when the ref or the file doesn't exist."""
    code, out = _git("show", "%s:data/radars.csv" % ref)
    return out if code == 0 else None


def _ids_of(text):
    return {line.split(",")[0] for line in text.splitlines()[1:] if line.strip()}


# --- fetch and check -----------------------------------------------------------------------------


def _show(it):
    where = "" if it.get("lat") is None else "  (%.5f, %.5f)" % (it["lat"], it["lon"])
    lim = "" if it.get("limit") is None else " %s km/h" % it["limit"]
    d = it.get("sentido") or ("" if it.get("heading") is None else "%d deg" % it["heading"])
    return "  [%s%s] %s -> %s%s" % (it["kind"], lim, it["label"], d or "?", where)


def collect():
    items, problems = [], []
    for name, fn in (("IMMU", fetch_immu), ("OpenStreetMap", fetch_osm)):
        try:
            items += fn()
        except (urllib.error.URLError, OSError, ValueError) as e:
            problems.append("%s: %s" % (name, getattr(e, "reason", e)))
    return items, problems


def cmd_fetch(_a):
    items, problems = collect()
    for p in problems:
        print("radars: could not read " + p, file=sys.stderr)
    if problems:
        return 2
    rows = radarlist.read_rows(CSV_PATH)
    new, gone = diff(items, rows)
    counts = [sum(1 for i in items if i["kind"] == k) for k in KINDS]
    print("%d points online (%d speed, %d bump, %d redlight); %d in data/radars.csv" % (len(items), *counts, len(rows)))
    print("new (%d):" % len(new))
    for it in new:
        print(_show(it))
    print("gone (%d):" % len(gone))
    for r in gone:
        print("  %s [%s] %s" % (r["id"], r["kind"], r["label"]))
    unknown = [r for r in rows if r["kind"] != "redlight" and r["limit"] is None]
    if unknown:
        print("limit unknown (%d): %s" % (len(unknown), ", ".join(r["id"] for r in unknown)))
    return 1 if (new or gone) else 0


def cmd_check(a):
    code = cmd_fetch(a)
    print({0: "check: the list is up to date", 1: "check: the list needs attention"}.get(code, "check: failed"))
    return code


# --- place ---------------------------------------------------------------------------------------


def _existing_items(rows):
    return [dict(r, confirmed=True, existing=True) for r in rows]


def cmd_place(a):
    if a.apply:
        with open(a.apply, encoding="utf-8") as fh:
            placed = json.load(fh)
        try:
            added, updated = radarlist.apply_placed(CSV_PATH, RETIRED_PATH, placed)
        except ValueError as e:
            print("radars: %s" % e, file=sys.stderr)
            return 1
        write_geojson()
        print("added %d, updated %d" % (added, updated))
        return 0
    rows = radarlist.read_rows(CSV_PATH)
    if a.src in ("file", "laps"):
        if not a.file:
            print("radars: --from %s needs --file %s" % (a.src, "items.json" if a.src == "file" else "activity.json"),
                  file=sys.stderr)
            return 2
        with open(a.file, encoding="utf-8") as fh:
            new = json.load(fh)
        if a.src == "laps":
            new = laps.marks_from_laps(new)
            if not new:
                print("no Lap presses in %s (only the lap that ends at Stop)" % a.file)
                return 0
    elif a.src == "marks":
        repo = marks.repo_name(a.repo)
        if not repo:
            print("radars: --from marks needs --repo owner/name (or MARKS_REPO)", file=sys.stderr)
            return 2
        try:
            new = marks.fetch_marks(repo, marks.token())
        except (urllib.error.URLError, OSError, ValueError) as e:
            print("radars: could not read the marks in %s: %s" % (repo, getattr(e, "reason", e)), file=sys.stderr)
            return 2
        if not new:
            print("no open marks in %s" % repo)
            return 0
    else:
        try:
            items = fetch_immu() if a.src == "immu" else fetch_osm()
        except (urllib.error.URLError, OSError, ValueError) as e:
            print("radars: could not read %s: %s" % (a.src, getattr(e, "reason", e)), file=sys.stderr)
            return 2
        new, _ = diff(items, rows)
    if new:
        print("placing %d new points (about a second each)..." % len(new), file=sys.stderr)
    placed = []
    for n, it in enumerate(new, 1):
        if it.get("lat") is None:
            print("[%d/%d] %s" % (n, len(new), it.get("label", "")), file=sys.stderr)
            it = autoplace.autoplace(it)
        placed.append(it)
    new = placed
    items = _existing_items(rows) + new
    if not items:
        print("nothing to review")
        return 0
    out = write_place_page(items)
    print("wrote %s (%d points, %d new, %d at a crossing, %d with a heading): open it, check each pin, press save, "
          "then run: %s" % (os.path.relpath(out, ROOT), len(items), len(new),
                            sum(1 for i in new if i.get("how") == "crossing"),
                            sum(1 for i in items if i.get("heading") is not None), APPLY_CMD))
    if not a.no_serve:
        serve(os.path.dirname(out), os.path.basename(out))
    return 0


# --- validate and geojson ------------------------------------------------------------------------


def _listed():
    """Addresses in the transcribed official lists (tools/lists/immu-*.csv), for the map's legend."""
    n = 0
    for path in sorted(glob.glob(os.path.join(LISTS_DIR, "immu-*.csv"))):
        with open(path, encoding="utf-8") as fh:
            n += max(0, sum(1 for line in fh if line.strip()) - 1)
    return n


def _map_svg(rows, base=None):
    """docs/map.svg for rows, with this base map or else the one already in the file; None without either."""
    if base is None:
        if not os.path.isfile(MAP_SVG):
            return None
        with open(MAP_SVG, encoding="utf-8", newline="") as fh:
            base = mapsvg.base_of(fh.read())
        if base is None:
            return None
    return mapsvg.build(rows, base, _listed())


MAP_AREAS = ('nwr["natural"="water"]', 'nwr["waterway"="riverbank"]', 'nwr["leisure"="park"]',
             'nwr["leisure"="nature_reserve"]', 'nwr["landuse"="forest"]', 'nwr["natural"="wood"]',
             'nwr["aeroway"="aerodrome"]')
MAP_MAX_SPAN = 5.0   # square degrees: leaves out the Amazon's own polygon, kept are the Rio Negro's


def _osm_base(rows):
    """The base map from OpenStreetMap: roads (build/roads.json), then water, green areas, the airport
    and neighbourhood names (build/map-osm.json, kept as long as the roads)."""
    try:
        if time.time() - os.path.getmtime(MAP_OSM) < autoplace.ROADS_MAX_AGE:
            with open(MAP_OSM, encoding="utf-8") as fh:
                cached = json.load(fh)
            return _base_from(rows, cached["areas"], cached["places"])
    except (OSError, ValueError, KeyError):
        pass
    areas, places = _fetch_map_osm()
    os.makedirs(os.path.dirname(MAP_OSM), exist_ok=True)
    with open(MAP_OSM, "w", encoding="utf-8") as fh:
        json.dump({"areas": areas, "places": places}, fh)
    return _base_from(rows, areas, places)


def _base_from(rows, areas, places):
    groups = {"water": [], "green": [], "aero": []}
    for e in areas:
        t = e.get("tags", {})
        if t.get("natural") == "water" or t.get("waterway") == "riverbank":
            groups["water"].append(e)
        elif t.get("aeroway") == "aerodrome":
            groups["aero"].append(e)
        else:
            groups["green"].append(e)
    keep_out = [mapsvg.xy(r["lat"], r["lon"]) for r in rows]
    return mapsvg.base_markup(autoplace.road_network(), groups["water"], groups["green"], groups["aero"],
                              places, keep_out)


def _fetch_map_osm():
    """Water, green areas and the airport (ways, and relations whole: they are clipped while drawing),
    and the neighbourhood names, in the map's box."""
    box = "(%g,%g,%g,%g)" % (mapsvg.SOUTH, mapsvg.WEST, mapsvg.NORTH, mapsvg.EAST)
    union = "".join(a.replace("nwr", "way") + box + ";" for a in MAP_AREAS)
    ways = autoplace._overpass("[out:json][timeout:180];(%s);out geom;" % union, timeout=200)
    union = "".join(a.replace("nwr", "relation") + box + ";" for a in MAP_AREAS)
    rels = autoplace._overpass("[out:json][timeout:180];(%s);out ids bb;" % union, timeout=200)
    keep = [str(r["id"]) for r in rels if r.get("bounds") and
            (r["bounds"]["maxlat"] - r["bounds"]["minlat"]) * (r["bounds"]["maxlon"] - r["bounds"]["minlon"])
            < MAP_MAX_SPAN]
    if keep:
        ways += autoplace._overpass("[out:json][timeout:180];relation(id:%s);out geom;" % ",".join(keep),
                                    timeout=200)
    places = [{"name": e["tags"]["name"], "lat": e["lat"], "lon": e["lon"]} for e in autoplace._overpass(
        '[out:json][timeout:60];node["place"="suburb"]%s;out;' % box, timeout=90) if e.get("tags", {}).get("name")]
    return ways, places


def _write_map(svg):
    os.makedirs(os.path.dirname(MAP_SVG), exist_ok=True)
    with open(MAP_SVG, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(svg)


def write_geojson():
    """data/radars.geojson and docs/map.svg, both from data/radars.csv."""
    rows = radarlist.read_rows(CSV_PATH)
    with open(GEOJSON_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(geojson.build(rows))
    svg = _map_svg(rows)
    if svg is not None:
        _write_map(svg)


def cmd_geojson(_a):
    write_geojson()
    print("wrote data/radars.geojson and docs/map.svg")
    return 0


def cmd_map(a):
    """Redraw docs/map.svg; --base also redraws its base map from OpenStreetMap."""
    rows = radarlist.read_rows(CSV_PATH)
    svg = _map_svg(rows, _osm_base(rows) if a.base else None)
    if svg is None:
        print("radars: docs/map.svg has no base map yet: run python tools/radars.py map --base", file=sys.stderr)
        return 1
    _write_map(svg)
    print("wrote docs/map.svg")
    return 0


def cmd_validate(a):
    if not os.path.isfile(CSV_PATH):
        print("error: data/radars.csv is missing")
        return 1
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        text = fh.read()
    errors, warnings = radarlist.validate(text)
    if not errors:       # the rest reads the rows, which only parse once the list is valid
        base = _csv_at(a.base) if a.base else None
        if a.base and base is None:
            print("warning: could not read data/radars.csv at %s; removed ids not checked" % a.base)
        errors += radarlist.check_ids(radarlist.read_rows(CSV_PATH), radarlist.read_retired(RETIRED_PATH),
                                      _ids_of(base) if base else set())
        if not geojson.matches(CSV_PATH, GEOJSON_PATH):
            errors.append("data/radars.geojson is out of date: run python tools/radars.py geojson")
        svg = _map_svg(radarlist.read_rows(CSV_PATH))
        if svg is not None:
            with open(MAP_SVG, encoding="utf-8", newline="") as fh:
                if fh.read() != svg:
                    errors.append("docs/map.svg is out of date: run python tools/radars.py geojson")
    for w in warnings:
        print("warning: " + w)
    for e in errors:
        print("error: " + e)
    return 1 if errors else 0


# --- release -------------------------------------------------------------------------------------


def _by_id(text):
    return {line.split(",")[0]: line for line in text.splitlines()[1:] if line.strip()}


def changelog(prev_text, now_text):
    """Added, changed and removed ids (sorted) between two texts of radars.csv; everything is added without prev."""
    old, new = _by_id(prev_text or ""), _by_id(now_text)
    return (sorted(set(new) - set(old)), sorted(i for i in new if i in old and new[i] != old[i]),
            sorted(set(old) - set(new)))


def cmd_release(a):
    v = a.version
    if re.fullmatch(VERSION_RE, v, re.A) is None:
        print("radars: version must look like 2026.11.1 (YYYY.MM.N)", file=sys.stderr)
        return 1
    code, out = _git("status", "--porcelain")
    if code != 0 or out.strip():
        print("radars: the working tree must be clean (commit or stash first)", file=sys.stderr)
        return 1
    if _git("rev-parse", "-q", "--verify", "refs/tags/" + v)[0] == 0:
        print("radars: tag %s already exists" % v, file=sys.stderr)
        return 1
    if cmd_validate(argparse.Namespace(base=None)) != 0:
        print("radars: validate failed, no release", file=sys.stderr)
        return 1
    os.makedirs(DIST, exist_ok=True)
    shutil.copyfile(CSV_PATH, os.path.join(DIST, "radars.csv"))
    shutil.copyfile(GEOJSON_PATH, os.path.join(DIST, "radars.geojson"))
    code, tag = _git("describe", "--tags", "--abbrev=0")
    prev = _csv_at(tag.strip()) if code == 0 else None
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        added, changed, removed = changelog(prev, fh.read())
    print("wrote dist/radars.csv and dist/radars.geojson (previous release: %s)" % (tag.strip() if prev else "none"))
    print("\nChangelog lines to fill in:")
    for title, ids in (("Adicionados / Added", added), ("Alterados / Changed", changed),
                       ("Removidos / Removed", removed)):
        print("%s: %s" % (title, ", ".join(ids) or "-"))
    print("Dados: ODbL 1.0 · © OpenStreetMap contributors")
    print("\nThen run, yourself:")
    print("  git tag %s" % v)
    print("  git push origin %s" % v)
    print("  gh release create %s dist/radars.csv dist/radars.geojson --notes-file <notes.md>" % v)
    return 0


def cmd_marks_close(a):
    repo = marks.repo_name(a.repo)
    if not repo:
        print("radars: marks-close needs --repo owner/name (or MARKS_REPO)", file=sys.stderr)
        return 2
    try:
        n = marks.close_all(repo, marks.token())
    except (urllib.error.URLError, OSError, ValueError) as e:
        print("radars: could not close the marks in %s: %s" % (repo, getattr(e, "reason", e)), file=sys.stderr)
        return 2
    print("closed %d mark%s in %s" % (n, "" if n == 1 else "s", repo))
    return 0


# --- command line --------------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=cmd_fetch)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    p = sub.add_parser("place")
    p.add_argument("--from", dest="src", choices=("immu", "osm", "file", "marks", "laps"), default="immu")
    p.add_argument("--file", metavar="items.json",
                   help="with --from file: a JSON list of items; with --from laps: an activity's laps and track")
    p.add_argument("--repo", metavar="OWNER/NAME", help="with --from marks: the private marks repo (or MARKS_REPO)")
    p.add_argument("--apply", metavar="placed.json")
    p.add_argument("--no-serve", action="store_true", help="only write the page, do not start the local server")
    p.set_defaults(fn=cmd_place)
    p = sub.add_parser("validate")
    p.add_argument("--base", metavar="REF", help="git ref to compare ids with: removed ids must be in retired.txt")
    p.set_defaults(fn=cmd_validate)
    sub.add_parser("geojson").set_defaults(fn=cmd_geojson)
    p = sub.add_parser("map", help="redraw docs/map.svg (--base: its base map too, from OpenStreetMap)")
    p.add_argument("--base", action="store_true")
    p.set_defaults(fn=cmd_map)
    p = sub.add_parser("marks-close", help="close the car marks' issues once their points are applied")
    p.add_argument("--repo", metavar="OWNER/NAME", help="the private marks repo (or MARKS_REPO)")
    p.set_defaults(fn=cmd_marks_close)
    p = sub.add_parser("release")
    p.add_argument("version", metavar="VERSION", help="YYYY.MM.N")
    p.set_defaults(fn=cmd_release)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
