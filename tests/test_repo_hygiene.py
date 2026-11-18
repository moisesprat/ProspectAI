"""Repository hygiene guards.

SEC-05: the local Open WebUI secret is never tracked.
D-05 (phase 3.1): the removed Reddit source and its client library do not creep back.
DEBT-01, D-02 (phase 5): the removed legacy crew module and class do not return.
"""

import re
import subprocess
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRET_PATH = ".webui_secret_key"

# D-05: files that record the past stay as they are. README.md is checked only above its
# release-notes heading; this file names the term it forbids.
_HISTORY_FILES = frozenset({
    "VERSION.md",
    "architecture-review.md",
    "architecture-review-2.md",
    "tests/test_repo_hygiene.py",
})
_HISTORY_DIRS = ("openspec/changes/archive/",)
_README = "README.md"
_README_HISTORY_HEADING = "## Release Notes"
_REMOVED_SOURCE = re.compile(r"reddit|\bpraw\b", re.IGNORECASE)
_REMOVED_CREW = re.compile(r"ProspectAICrew|prospect_ai_crew")
_REMOVED_CREW_MODULE = "prospect_ai_crew"


def _git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module", autouse=True)
def _require_git_checkout():
    try:
        probe = _git("rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        pytest.skip("git is not available")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        pytest.skip("repo root is not a git checkout")


def test_webui_secret_key_is_not_tracked():
    result = _git("ls-files", SECRET_PATH)
    assert result.returncode == 0
    assert result.stdout.strip() == "", f"{SECRET_PATH} is tracked by git"


def test_webui_secret_key_is_ignored():
    # check-ignore matches by pattern, so this holds even when the file does not exist.
    result = _git("check-ignore", "-q", SECRET_PATH)
    assert result.returncode == 0, f"{SECRET_PATH} is not covered by .gitignore"


def _offenders(pattern):
    """Tracked files outside the history allow-list whose text matches `pattern`."""
    listing = _git("ls-files", "-z")
    assert listing.returncode == 0
    offenders = []
    for rel in listing.stdout.split("\0"):
        if not rel or rel in _HISTORY_FILES or rel.startswith(_HISTORY_DIRS):
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if rel == _README:
            text = text.split(_README_HISTORY_HEADING)[0]
        if pattern.search(text):
            offenders.append(rel)
    return offenders


def test_no_reddit_source_left():
    """No tracked file outside the history allow-list mentions the removed source (D-05)."""
    offenders = _offenders(_REMOVED_SOURCE)
    assert not offenders, f"removed source still mentioned in: {sorted(offenders)}"


def test_no_legacy_crew_module_left():
    """The legacy crew class and module do not return (DEBT-01, D-02)."""
    offenders = _offenders(_REMOVED_CREW)
    assert not offenders, f"removed legacy crew still mentioned in: {sorted(offenders)}"
    assert not (REPO_ROOT / f"{_REMOVED_CREW_MODULE}.py").exists(), "root crew module is back"
    with open(REPO_ROOT / "pyproject.toml", "rb") as fh:
        py_modules = tomllib.load(fh)["tool"]["setuptools"]["py-modules"]
    assert _REMOVED_CREW_MODULE not in py_modules, f"py-modules lists the crew module: {py_modules}"
