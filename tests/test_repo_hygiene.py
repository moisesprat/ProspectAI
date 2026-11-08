"""Repository hygiene guards.

SEC-05: the local Open WebUI secret is never tracked.
D-05 (phase 3.1): the removed Reddit source and its client library do not creep back.
"""

import re
import subprocess
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


def test_no_reddit_source_left():
    """No tracked file outside the history allow-list mentions the removed source (D-05)."""
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
        if _REMOVED_SOURCE.search(text):
            offenders.append(rel)
    assert not offenders, f"removed source still mentioned in: {sorted(offenders)}"
