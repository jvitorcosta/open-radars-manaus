"""Manaus radar list tools: fetch, check, place, validate, geojson, release.

Ported from car-cyberdeck's tools/cameras.py (MIT, same author). Run from the repo root:
python tools/radars.py <command>.
"""
import argparse
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error

import autoplace
import geojson
import radarlist
from radarlist import CSV_PATH, GEOJSON_PATH, KINDS, RETIRED_PATH, ROOT
from sources import diff, fetch_immu, fetch_osm

TEMPLATE = os.path.join(ROOT, "tools", "review_map.html")
PLACE_HTML = os.path.join(ROOT, "build", "review_map.html")
DIST = os.path.join(ROOT, "dist")
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
    if a.src == "file":
        if not a.file:
            print("radars: --from file needs --file items.json", file=sys.stderr)
            return 2
        with open(a.file, encoding="utf-8") as fh:
            new = json.load(fh)
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


def write_geojson():
    with open(GEOJSON_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(geojson.build(radarlist.read_rows(CSV_PATH)))


def cmd_geojson(_a):
    write_geojson()
    print("wrote data/radars.geojson")
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


# --- command line --------------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(fn=cmd_fetch)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    p = sub.add_parser("place")
    p.add_argument("--from", dest="src", choices=("immu", "osm", "file"), default="immu")
    p.add_argument("--file", metavar="items.json", help="with --from file: a JSON list of items")
    p.add_argument("--apply", metavar="placed.json")
    p.add_argument("--no-serve", action="store_true", help="only write the page, do not start the local server")
    p.set_defaults(fn=cmd_place)
    p = sub.add_parser("validate")
    p.add_argument("--base", metavar="REF", help="git ref to compare ids with: removed ids must be in retired.txt")
    p.set_defaults(fn=cmd_validate)
    sub.add_parser("geojson").set_defaults(fn=cmd_geojson)
    p = sub.add_parser("release")
    p.add_argument("version", metavar="VERSION", help="YYYY.MM.N")
    p.set_defaults(fn=cmd_release)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
