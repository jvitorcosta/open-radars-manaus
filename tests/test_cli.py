import json
import os
import subprocess

import pytest

import autoplace
import geojson
import radars
import radarlist

ROW1 = "mao-0001,speed,-3.100000,-60.020000,90,60,Av. Teste · Centro,immu,2026-01-01"
ROW2 = "mao-0002,bump,-3.110000,-60.030000,180,,Rua Dois · Praca,survey,2026-01-01"
ROW3 = "mao-0003,redlight,-3.120000,-60.040000,0,,Rua Tres · Dom Pedro,osm,2026-01-01"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def csv_text(*rows):
    return radarlist.HEADER + "\n" + "".join(r + "\n" for r in rows)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A scratch data tree; the CLI is pointed at it, so the real repo is never touched."""
    monkeypatch.setattr(radars, "ROOT", str(tmp_path))
    monkeypatch.setattr(radars, "CSV_PATH", str(tmp_path / "data" / "radars.csv"))
    monkeypatch.setattr(radars, "RETIRED_PATH", str(tmp_path / "data" / "retired.txt"))
    monkeypatch.setattr(radars, "GEOJSON_PATH", str(tmp_path / "data" / "radars.geojson"))
    monkeypatch.setattr(radars, "PLACE_HTML", str(tmp_path / "build" / "review_map.html"))
    monkeypatch.setattr(radars, "DIST", str(tmp_path / "dist"))
    monkeypatch.setattr(radars, "README_PATH", str(tmp_path / "README.md"))
    write(radars.RETIRED_PATH, "# id,date,reason\n")
    return tmp_path


def set_list(repo, *rows):
    write(radars.CSV_PATH, csv_text(*rows))
    write(radars.GEOJSON_PATH, geojson.build(radarlist.read_rows(radars.CSV_PATH)))


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def git_init(repo):
    git(repo, "init", "-q")
    for k, v in (("user.name", "Test"), ("user.email", "test@example.com"), ("commit.gpgsign", "false"),
                 ("tag.gpgsign", "false"), ("core.autocrlf", "false")):
        git(repo, "config", k, v)


def commit(repo, msg):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


def page_items(repo):
    text = open(radars.PLACE_HTML, encoding="utf-8").read()
    start = text.index("var ITEMS = ") + len("var ITEMS = ")
    return json.loads(text[start:text.index(";\nvar map", start)])


def test_place_page_embeds_items(repo, monkeypatch):
    set_list(repo, ROW1)
    items = [{"kind": "speed", "label": "A <b>&</b>", "lat": -3.1, "lon": -60.0, "heading": 10, "source": "car"}]
    write(str(repo / "items.json"), json.dumps(items))
    assert radars.main(["place", "--from", "file", "--file", str(repo / "items.json"), "--no-serve"]) == 0
    text = open(radars.PLACE_HTML, encoding="utf-8").read()
    assert "__ITEMS__" not in text and "__APPLY__" not in text
    assert "python tools/radars.py place --apply caminho/para/placed.json" in text
    assert "<b>&</b>" not in text            # < > & are escaped inside the embedded JSON
    got = page_items(repo)
    assert [i["label"] for i in got] == ["Av. Teste · Centro", "A <b>&</b>"]


def test_place_page_marks_existing_and_guesses(repo, monkeypatch):
    set_list(repo, ROW1)
    immu = [{"kind": "speed", "address": "Rua Nova, nº 1 – Centro", "label": "Rua Nova · Centro", "limit": 40,
             "source": "immu", "sentido": "Leste", "heading": 90}]
    monkeypatch.setattr(radars, "fetch_immu", lambda: immu)
    monkeypatch.setattr(autoplace, "autoplace", lambda it: dict(it, lat=-3.2, lon=-60.1, guess=True))
    assert radars.main(["place", "--from", "immu", "--no-serve"]) == 0
    text = open(radars.PLACE_HTML, encoding="utf-8").read()
    assert '"existing": true' in text and '"guess": true' in text
    got = page_items(repo)
    old = [i for i in got if i.get("existing")]
    assert len(old) == 1 and old[0]["id"] == "mao-0001" and old[0]["confirmed"] is True
    assert [i["label"] for i in got if i.get("guess")] == ["Rua Nova · Centro"]


def test_apply_rewrites_geojson(repo, capsys):
    set_list(repo, ROW1)
    placed = [{"kind": "bump", "lat": -3.15, "lon": -60.05, "heading": 45, "limit": None, "label": "Rua X · Y",
               "source": "survey", "confirmed": True},
              {"id": "mao-0001", "kind": "speed", "lat": -3.101, "lon": -60.021, "heading": 90, "limit": 50,
               "label": "Av. Teste · Centro", "source": "immu", "confirmed": True}]
    write(str(repo / "placed.json"), json.dumps(placed))
    assert radars.main(["place", "--apply", str(repo / "placed.json")]) == 0
    assert "added 1, updated 1" in capsys.readouterr().out
    rows = radarlist.read_rows(radars.CSV_PATH)
    assert [r["id"] for r in rows] == ["mao-0001", "mao-0002"]
    assert geojson.matches(radars.CSV_PATH, radars.GEOJSON_PATH)
    assert "-3.15" in open(radars.GEOJSON_PATH, encoding="utf-8").read()


def test_apply_refuses_unconfirmed_and_leaves_files(repo, capsys):
    set_list(repo, ROW1)
    before = open(radars.CSV_PATH, encoding="utf-8").read()
    write(str(repo / "placed.json"), json.dumps([{"kind": "bump", "lat": -3.15, "lon": -60.05, "heading": 1}]))
    assert radars.main(["place", "--apply", str(repo / "placed.json")]) == 1
    assert open(radars.CSV_PATH, encoding="utf-8").read() == before


def test_validate_cli_exit_codes(repo, capsys):
    set_list(repo, ROW1, ROW2)
    assert radars.main(["validate"]) == 0
    write(radars.CSV_PATH, csv_text(ROW1, ROW2.replace(",180,", ",,")))
    assert radars.main(["validate"]) == 1
    assert "error:" in capsys.readouterr().out
    set_list(repo, ROW1)
    write(radars.GEOJSON_PATH, "{}\n")      # a stale GeoJSON is an error too
    assert radars.main(["validate"]) == 1


def test_geojson_rebuilds_the_readme_map_and_validate_checks_it(repo, capsys):
    set_list(repo, ROW1)
    write(radars.README_PATH, "\n".join(["# t", geojson.MAP_START, geojson.MAP_END, ""]))
    assert radars.main(["validate"]) == 1
    assert "README map is out of date" in capsys.readouterr().out
    assert radars.main(["geojson"]) == 0
    with open(radars.README_PATH, encoding="utf-8") as fh:
        assert "```geojson" in fh.read()
    assert radars.main(["validate"]) == 0


def test_validate_base_catches_silent_removal(repo, capsys):
    git_init(repo)
    set_list(repo, ROW1, ROW2)
    commit(repo, "two rows")
    set_list(repo, ROW1)
    commit(repo, "drop one")
    assert radars.main(["validate"]) == 0
    assert radars.main(["validate", "--base", "HEAD~1"]) == 1
    assert "mao-0002 was removed" in capsys.readouterr().out
    write(radars.RETIRED_PATH, "# id,date,reason\nmao-0002,2026-02-01,gone\n")
    assert radars.main(["validate", "--base", "HEAD~1"]) == 0
    assert radars.main(["validate", "--base", "no-such-ref"]) == 0     # nothing to compare with


def test_release_refuses_bad_version_and_dirty_tree(repo, capsys):
    git_init(repo)
    set_list(repo, ROW1)
    commit(repo, "one row")
    for bad in ("1.0", "2026.13.1", "2026.1.1", "v2026.01.1"):
        assert radars.main(["release", bad]) == 1
    write(str(repo / "stray.txt"), "x")
    assert radars.main(["release", "2026.11.1"]) == 1
    assert "clean" in capsys.readouterr().err
    os.remove(str(repo / "stray.txt"))
    git(repo, "tag", "2026.11.1")
    assert radars.main(["release", "2026.11.1"]) == 1      # the tag exists
    assert not os.path.exists(radars.DIST)


def test_release_changelog_lists_added_changed_removed(repo, capsys):
    git_init(repo)
    set_list(repo, ROW1, ROW2)
    commit(repo, "first")
    git(repo, "tag", "2026.10.1")
    set_list(repo, ROW1.replace(",60,", ",50,"), ROW3)
    commit(repo, "second")
    capsys.readouterr()
    assert radars.main(["release", "2026.11.1"]) == 0
    out = capsys.readouterr().out
    assert "Adicionados / Added: mao-0003" in out
    assert "Alterados / Changed: mao-0001" in out
    assert "Removidos / Removed: mao-0002" in out
    assert "git tag 2026.11.1" in out and "git push origin 2026.11.1" in out
    assert "gh release create 2026.11.1 dist/radars.csv dist/radars.geojson --notes-file" in out
    assert os.path.isfile(str(repo / "dist" / "radars.csv")) and os.path.isfile(str(repo / "dist" / "radars.geojson"))
    assert "2026.11.1" not in git(repo, "tag", "--list")     # it runs none of them


def test_release_without_a_tag_adds_everything(repo, capsys):
    git_init(repo)
    set_list(repo, ROW1, ROW2)
    commit(repo, "first")
    capsys.readouterr()
    assert radars.main(["release", "2026.11.1"]) == 0
    out = capsys.readouterr().out
    assert "Adicionados / Added: mao-0001, mao-0002" in out
    assert "Removidos / Removed: -" in out


def test_review_map_field_edit_confirms_only_existing_points():
    text = open(radars.TEMPLATE, encoding="utf-8").read()
    body = text[text.index("function edited(i)"):text.index("function setConfirmed")]
    assert "if (ITEMS[i].existing) setConfirmed(i, true)" in body    # a field edit confirms only points already in the list
    assert body.count("setConfirmed") == 1
    # a guess is confirmed by a drag, a map click or the checkbox
    assert "setConfirmed(i, true); edited(i)" in text and "setConfirmed(selected, true);" in text
    assert "it.guess && !it.confirmed ? ORANGE" in text


def test_place_prints_progress_per_item(repo, monkeypatch, capsys):
    set_list(repo, ROW1)
    items = [{"kind": "speed", "label": "A", "source": "car", "lat": None, "lon": None},
             {"kind": "speed", "label": "B", "source": "car", "lat": None, "lon": None}]
    write(str(repo / "items.json"), json.dumps(items))
    monkeypatch.setattr(autoplace, "autoplace", lambda it: dict(it, lat=-3.2, lon=-60.1, guess=True))
    assert radars.main(["place", "--from", "file", "--file", str(repo / "items.json"), "--no-serve"]) == 0
    err = capsys.readouterr().err
    assert "[1/2] A" in err and "[2/2] B" in err


def test_validate_base_warns_when_base_csv_unreadable(repo, capsys):
    git_init(repo)
    set_list(repo, ROW1)
    commit(repo, "one")
    capsys.readouterr()
    assert radars.main(["validate", "--base", "no-such-ref"]) == 0
    assert "warning: could not read data/radars.csv at no-such-ref; removed ids not checked" in capsys.readouterr().out


def test_release_notes_stub_names_the_data_licence(repo, capsys):
    git_init(repo)
    set_list(repo, ROW1)
    commit(repo, "first")
    capsys.readouterr()
    assert radars.main(["release", "2026.11.1"]) == 0
    assert "Dados: ODbL 1.0 · © OpenStreetMap contributors" in capsys.readouterr().out
