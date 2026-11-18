from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
PHASES = ["1", "2", "3", "4a", "4b", "5", "6", "7", "8", "9", "10a", "11a", "11b"]
EXPECTS = {"2": "fail", "3": "fail", "5": "nocrash", "10a": "fail"}


def _rows() -> list[list[str]]:
    lines = (ROOT / "docs/keychain-runbook.md").read_text().splitlines()
    table = [line for line in lines if line.startswith("|")]
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in table[2:]]


def _legs() -> list[dict]:
    workflow = (ROOT / ".github/workflows/keychain-runbook.yml").read_text()
    return yaml.safe_load(workflow)["jobs"]["phase"]["strategy"]["matrix"]["include"]


def test_docs_list_the_runbook_phases():
    assert [row[0] for row in _rows()] == PHASES


def test_every_rig_row_has_a_leg_and_every_leg_a_rig_row():
    rig = [row for row in _rows() if row[2] == "runs on the rig"]
    assert [leg["phase"] for leg in _legs()] == [row[0] for row in rig]
    assert all(row[3].split(":")[0] == f"phase {row[0]}" for row in rig)


def test_legs_expect_what_the_runbook_expects():
    for leg in _legs():
        assert leg["expect"] == EXPECTS.get(leg["phase"], "pass")


def test_every_expectation_has_a_case_arm():
    workflow = (ROOT / ".github/workflows/keychain-runbook.yml").read_text()
    steps = yaml.safe_load(workflow)["jobs"]["phase"]["steps"]
    (run,) = [step["run"] for step in steps if "EXPECT" in step.get("env", {})]
    for leg in _legs():
        assert f"{leg['expect']}:" in run


def test_every_manual_row_has_a_reason():
    rows = _rows()
    assert all(row[2] in ("runs on the rig", "stays manual") for row in rows)
    assert all(row[3] for row in rows if row[2] == "stays manual")
