"""Camera spots marked from the car: the CarDeck posts each one as an issue in a private GitHub repo
(the owner's, MARKS_REPO; never this public one, so no driving trail is published). Each issue body
holds 'lat:', 'lon:', 'heading:', 'kmh:' and 'time:' lines.

`place --from marks` reads the open issues into the review map; `marks-close` closes them once the
points are applied. The token comes from GH_TOKEN / GITHUB_TOKEN or `gh auth token`.
"""
import json
import os
import re
import subprocess
import urllib.parse

from sources import http_req

API = "https://api.github.com"


def repo_name(arg=None):
    """The marks repo ('owner/name'): --repo, else MARKS_REPO. None when neither is set."""
    return arg or os.environ.get("MARKS_REPO") or None


def token():
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if t:
        return t
    try:
        p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=15)
        return p.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _headers(tok):
    h = {"Accept": "application/vnd.github+json"}
    if tok:
        h["Authorization"] = "Bearer " + tok
    return h


def parse_issue(issue):
    """A mark issue as a review-map item (a guess at the car's position), None when its body has no
    position."""
    fields = dict(re.findall(r"^(lat|lon|heading|kmh|time):\s*(\S+)\s*$", issue.get("body") or "", re.M))
    try:
        lat, lon = float(fields["lat"]), float(fields["lon"])
    except (KeyError, ValueError):
        return None
    try:
        heading = int(float(fields.get("heading", ""))) % 360
    except ValueError:
        heading = None
    when = issue.get("title", "").replace("Mark ", "", 1)
    return {"kind": "speed", "lat": lat, "lon": lon, "heading": heading, "limit": None,
            "label": "", "source": "car", "guess": True, "how": "car",
            "address": "marked from the car %s (issue #%s)" % (when, issue.get("number")),
            "issue": issue.get("number")}


def open_issues(repo, tok=None, req=http_req):
    """The open issues of the marks repo, oldest first (pull requests left out)."""
    out, page = [], 1
    while True:
        q = urllib.parse.urlencode({"state": "open", "per_page": 100, "page": page,
                                    "sort": "created", "direction": "asc"})
        _, body = req("%s/repos/%s/issues?%s" % (API, repo, q), headers=_headers(tok))
        batch = json.loads(body)
        out += [i for i in batch if "pull_request" not in i]
        if len(batch) < 100:
            return out
        page += 1


def fetch_marks(repo, tok=None, req=http_req):
    return [it for it in (parse_issue(i) for i in open_issues(repo, tok, req)) if it]


def close_all(repo, tok, req=http_req):
    """Closes every open mark issue; returns how many."""
    n = 0
    for i in open_issues(repo, tok, req):
        req("%s/repos/%s/issues/%d" % (API, repo, i["number"]), headers=_headers(tok),
            data=json.dumps({"state": "closed", "state_reason": "completed"}).encode(), method="PATCH")
        n += 1
    return n
