"""Repository hygiene guards (SEC-05): the local Open WebUI secret is never tracked."""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRET_PATH = ".webui_secret_key"


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
