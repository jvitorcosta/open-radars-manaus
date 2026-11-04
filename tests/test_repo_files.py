import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORMS = {
    "informar-radar.yml": ["novo-ponto", "precisa-verificar"],
    "algo-errado.yml": ["correção"],
}


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def test_issue_forms_parse():
    # no PyYAML here, so a minimal line check: top-level keys and the label list
    for name, labels in FORMS.items():
        text = read(".github", "ISSUE_TEMPLATE", name)
        lines = text.splitlines()
        assert any(re.match(r"name: \S", ln) for ln in lines), name
        assert "body:" in lines, name
        assert re.search(r"^\s+- type: (dropdown|input|textarea|checkboxes)", text, re.M), name
        m = re.search(r"^labels: \[(.*)\]$", text, re.M)
        assert m, name
        assert [s.strip() for s in m.group(1).split(",")] == labels, name
    config = read(".github", "ISSUE_TEMPLATE", "config.yml")
    assert "blank_issues_enabled: false" in config.splitlines()


def test_ci_job_is_named_ci():
    text = read(".github", "workflows", "ci.yml")
    assert re.search(r"^jobs:\n  ci:$", text, re.M)


def test_readme_is_portuguese_first():
    text = read("README.md")
    assert "Contribuições são bem-vindas" in text
    assert text.index("Contribuições são bem-vindas") < text.index("## English")


def test_no_personal_paths():
    forbidden = ["Obsidian", "D:\\", "C:\\Users", "joaovpro17"]
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                             check=True).stdout.splitlines()
    me = os.path.basename(__file__)
    for rel in tracked:
        # testdata holds a public IMMU page with IMMU's own contact address
        if rel.startswith("tests/testdata/") or os.path.basename(rel) == me:
            continue
        try:
            text = read(*rel.split("/"))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for bad in forbidden:
            assert bad not in text, f"{rel} contains {bad}"
