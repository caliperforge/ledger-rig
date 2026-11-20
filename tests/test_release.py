import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
WORKFLOW = ROOT / ".github/workflows/release.yml"
RELEASE_ONLY = "steps.tag.outputs.release == 'true'"


def _steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]["release"]["steps"]


def test_changelog_leads_with_the_project_version():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    lines = (ROOT / "CHANGELOG.md").read_text().splitlines()
    headings = [line for line in lines if line.startswith("## ")]
    assert headings[0] == f"## {version}"


def test_publish_and_v0_run_only_on_a_release_tag():
    steps = _steps()
    (tag,) = [step for step in steps if step.get("id") == "tag"]
    assert r"^v[0-9]+\.[0-9]+\.[0-9]+$" in tag["run"]
    (publish,) = [step for step in steps if "pypi-publish" in step.get("uses", "")]
    (move,) = [step for step in steps if "refs/tags/v0" in step.get("run", "")]
    assert publish["if"] == RELEASE_ONLY
    assert move["if"] == RELEASE_ONLY


def test_release_holds_no_secrets():
    assert "secrets." not in WORKFLOW.read_text()
