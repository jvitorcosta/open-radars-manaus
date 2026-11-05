import json

import marks
import radars

ISSUE = {"number": 7, "title": "Mark 2026-11-05 14:32:10",
         "body": "lat: -3.115885\nlon: -60.015568\nheading: 90\nkmh: 42\ntime: 2026-11-05T18:32:10Z\n\n"
                 "https://www.google.com/maps?q=-3.115885,-60.015568"}


def test_parse_issue_reads_the_decks_lines():
    it = marks.parse_issue(ISSUE)
    assert (it["lat"], it["lon"], it["heading"]) == (-3.115885, -60.015568, 90)
    assert it["source"] == "car" and it["guess"] is True and it["issue"] == 7
    assert "2026-11-05 14:32:10" in it["address"] and "#7" in it["address"]


def test_parse_issue_without_a_position_is_skipped():
    assert marks.parse_issue({"number": 1, "title": "hello", "body": "just a note"}) is None
    assert marks.parse_issue({"number": 2, "title": "Mark", "body": None}) is None


class FakeGitHub:
    def __init__(self, issues):
        self.issues, self.calls = issues, []

    def __call__(self, url, data=None, headers=None, timeout=30, method=None):
        self.calls.append((method or ("POST" if data else "GET"), url, headers))
        if method == "PATCH":
            return 200, b"{}"
        return 200, json.dumps(self.issues).encode()


def test_fetch_marks_skips_pull_requests_and_sends_the_token():
    gh = FakeGitHub([ISSUE, dict(ISSUE, number=8, pull_request={})])
    items = marks.fetch_marks("me/radar-marks", "tok", req=gh)
    assert [i["issue"] for i in items] == [7]
    method, url, headers = gh.calls[0]
    assert url.startswith("https://api.github.com/repos/me/radar-marks/issues?") and "state=open" in url
    assert headers["Authorization"] == "Bearer tok"


def test_close_all_patches_each_open_issue():
    gh = FakeGitHub([ISSUE, dict(ISSUE, number=9)])
    assert marks.close_all("me/radar-marks", "tok", req=gh) == 2
    assert [u for m, u, _ in gh.calls if m == "PATCH"] == [
        "https://api.github.com/repos/me/radar-marks/issues/7", "https://api.github.com/repos/me/radar-marks/issues/9"]


def test_place_from_marks_needs_a_repo(monkeypatch, capsys):
    monkeypatch.delenv("MARKS_REPO", raising=False)
    assert radars.main(["place", "--from", "marks", "--no-serve"]) == 2
    assert "--repo" in capsys.readouterr().err


def test_place_from_marks_writes_the_review_map(monkeypatch, tmp_path):
    monkeypatch.setattr(radars.os.path, "relpath", lambda p, start=None: p)   # tmp_path may be on another drive
    monkeypatch.setattr(marks, "token", lambda: "tok")
    monkeypatch.setattr(marks, "fetch_marks", lambda repo, tok: [marks.parse_issue(ISSUE)])
    out = tmp_path / "review_map.html"
    monkeypatch.setattr(radars, "PLACE_HTML", str(out))
    monkeypatch.setattr(radars.autoplace, "autoplace", lambda it: (_ for _ in ()).throw(AssertionError("no guessing")))
    assert radars.main(["place", "--from", "marks", "--repo", "me/radar-marks", "--no-serve"]) == 0
    assert "-60.015568" in out.read_text(encoding="utf-8")
