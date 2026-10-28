"""Tests for the deploy.sh --skip-pypi recovery path (review CR-01, gap closure 01-13).

Each test builds a sandbox under tmp_path: bare local origins, a ProspectAI and a
prospectai-backend clone on main, and a harness directory with fake `uv`, `modal`
and `sleep` first on PATH. It then runs the real scripts/deploy.sh and the real
prospectai-backend/scripts/check_pin.py, copied into the sandbox, end to end.
PyPI and the deployed /api/version are faked inside the check_pin process, with a
fake clock so waits end instantly (tests/deploy_fakes.py). HOME, TMPDIR and the
git config are the sandbox's, and TWINE_*, MODAL_*, PYPI_* and GIT_* variables are
scrubbed, so nothing reaches the network, PyPI, Modal, the operator's credentials
or the real repositories.

The module is skipped without the sibling prospectai-backend checkout, which is
the ProspectAI CI case. It runs locally and inside the deploy.sh preflight, which
runs the whole ProspectAI suite before any release and refuses on failure. Per
D-30 that preflight is its enforcing gate, the same principle as D-23.
"""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SH = REPO_ROOT / "scripts" / "deploy.sh"
CHECK_PIN = REPO_ROOT.parent / "prospectai-backend" / "scripts" / "check_pin.py"
FAKES = Path(__file__).resolve().parent / "deploy_fakes.py"

pytestmark = pytest.mark.skipif(
    not CHECK_PIN.is_file(),
    reason="sibling prospectai-backend/scripts/check_pin.py not found "
    "(ProspectAI CI has no backend checkout); the deploy.sh preflight enforces this module (D-30)",
)

DONE = "Done. prospectai==1.0.1 is live and verified."
HINT_A = "is on PyPI but not verified in production"
HINT_B = "scripts/deploy.sh --skip-pypi"
REFUSE_PIN = "REFUSING: pin preflight failed"


def _pin_line(version):
    return "prospectai" + "==" + version


def _write(path, text, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    if mode is not None:
        path.chmod(mode)


def _wrapper(tool):
    return '#!/bin/sh\nexec "$DEPLOY_HARNESS_PY" -I "$DEPLOY_HARNESS_TOOLS" %s "$@"\n' % tool


README = (
    "# prospectai\n\n"
    "**Current release: v1.0.0**\n\n"
    "## Release Notes\n\n"
    "### Unreleased — Harness release\n"
    "- A user-facing note for the harness release.\n\n"
    "### v1.0.0 — Initial\n"
    "- First release.\n\n"
    "## License\n\nMIT\n"
)


class Sandbox:
    def __init__(self, root, pin_version):
        self.root = root
        self.pa = root / "ProspectAI"
        self.be = root / "prospectai-backend"
        self.control = root / "harness" / "control"
        self.bin = root / "harness" / "bin"
        self.home = root / "home"
        self.tmp = root / "tmp"
        self.env = self._env()
        self._build(pin_version)

    # ── construction ─────────────────────────────────────────────────────────
    def _env(self):
        env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("TWINE_", "MODAL_", "PYPI_", "GIT_"))
        }
        identity = {"NAME": "Harness", "EMAIL": "harness@example.invalid"}
        env.update(
            HOME=str(self.home),
            TMPDIR=str(self.tmp),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=str(self.home / ".gitconfig"),
            GIT_AUTHOR_NAME=identity["NAME"],
            GIT_AUTHOR_EMAIL=identity["EMAIL"],
            GIT_COMMITTER_NAME=identity["NAME"],
            GIT_COMMITTER_EMAIL=identity["EMAIL"],
            DEPLOY_HARNESS_CONTROL=str(self.control),
            DEPLOY_HARNESS_PY=sys.executable,
            DEPLOY_HARNESS_TOOLS=str(FAKES),
            PROSPECTAI_BACKEND_URL="http://deploy-harness.invalid",
            PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
        )
        return env

    def git(self, repo, *args):
        return subprocess.run(
            ["git", "-C", str(repo), *args], env=self.env, capture_output=True, text=True, check=True
        ).stdout

    def _build(self, pin_version):
        exe = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
        for directory in (self.home, self.tmp, self.control / "pypi"):
            directory.mkdir(parents=True, exist_ok=True)
        _write(self.home / ".pypirc", "")
        _write(self.home / ".gitconfig", "")
        _write(self.bin / "uv", _wrapper("uv"), exe)
        _write(self.bin / "modal", _wrapper("modal"), exe)
        _write(self.bin / "sleep", "#!/bin/sh\nexit 0\n", exe)
        for resolved in ("uv", "modal"):
            assert Path(shutil.which(resolved, path=self.env["PATH"])).parent == self.bin
        for version in {"1.0.0", pin_version}:
            _write(self.control / "pypi" / version, "")
        _write(self.control / "api_version.json", '{"version": "1.0.0", "prospectai": "1.0.0", "backend_sha": "base"}')

        # ProspectAI
        _write(self.pa / "scripts" / "deploy.sh", DEPLOY_SH.read_text(), exe)
        _write(self.pa / "pyproject.toml", '[project]\nname = "prospectai"\nversion = "1.0.0"\n')
        _write(self.pa / "README.md", README)
        _write(self.pa / "requirements.txt", "# placeholder lock\n")
        _write(self.pa / ".gitignore", "dist/\n")
        # prospectai-backend
        pin = _pin_line(pin_version)
        _write(self.be / "scripts" / "check_pin.py", CHECK_PIN.read_text(), exe)
        _write(
            self.be / "scripts" / "lock.sh",
            '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "${BASH_SOURCE[0]}")/.."\n'
            'exec "$DEPLOY_HARNESS_PY" -I "$DEPLOY_HARNESS_TOOLS" lock "$@"\n',
            exe,
        )
        _write(self.be / "requirements-serve.txt", pin + "\n")
        _write(self.be / "requirements-serve.lock", pin + "\n    # via -r requirements-serve.txt\n")
        _write(self.be / "requirements-dev.txt", "-c requirements-serve.lock\n")
        _write(self.be / "serve.py", "# placeholder Modal entrypoint\n")

        for name, work in (("ProspectAI", self.pa), ("prospectai-backend", self.be)):
            origin = self.root / "origins" / (name + ".git")
            origin.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(origin)], env=self.env, check=True)
            self.git(work, "init", "-q", "-b", "main")
            self.git(work, "add", "-A")
            self.git(work, "commit", "-q", "-m", "baseline")
            self.git(work, "remote", "add", "origin", str(origin))
            self.git(work, "push", "-q", "-u", "origin", "main")

    # ── running and observing ────────────────────────────────────────────────
    def run(self, *args):
        return subprocess.run(
            ["bash", str(self.pa / "scripts" / "deploy.sh"), *args],
            cwd=self.pa,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def pin(self):
        text = (self.be / "requirements-serve.txt").read_text()
        return text.split("==")[1].split()[0]

    def lock_pin(self):
        for line in (self.be / "requirements-serve.lock").read_text().splitlines():
            if line.startswith("prospectai=="):
                return line.split("==")[1].strip()
        return None

    def pyproject_version(self):
        for line in (self.pa / "pyproject.toml").read_text().splitlines():
            if line.startswith("version"):
                return line.split('"')[1]

    def events(self):
        log = self.control / "events.log"
        return log.read_text().splitlines() if log.exists() else []

    def set_knob(self, name, value):
        (self.control / name).write_text(str(value))

    def publish(self, version):
        (self.control / "pypi" / version).write_text("")

    def ahead(self, repo):
        return int(self.git(repo, "rev-list", "--count", "origin/main..HEAD").strip())

    def subject(self, repo):
        return self.git(repo, "log", "-1", "--format=%s").strip()

    def porcelain(self, repo):
        return self.git(repo, "status", "--porcelain")

    def api_version(self):
        import json

        return json.loads((self.control / "api_version.json").read_text())["prospectai"]

    def snapshot(self):
        return (
            self.pin(),
            self.lock_pin(),
            self.pyproject_version(),
            self.porcelain(self.pa),
            self.porcelain(self.be),
            self.events(),
        )


@pytest.fixture
def sandbox(tmp_path):
    def make(pin_version="1.0.0"):
        return Sandbox(tmp_path, pin_version)

    return make


def _out(proc):
    return "\n--- stdout ---\n%s\n--- stderr ---\n%s" % (proc.stdout, proc.stderr)


def _release_commits_made(sb):
    assert sb.subject(sb.pa) == "chore: release prospectai v1.0.1"
    assert sb.subject(sb.be) == "chore: pin prospectai==1.0.1"
    assert sb.ahead(sb.pa) == 1 and sb.ahead(sb.be) == 1
    assert sb.porcelain(sb.pa) == "" and sb.porcelain(sb.be) == ""


# ── the normal release still works ───────────────────────────────────────────

def test_release_happy_path(sandbox):
    sb = sandbox()
    proc = sb.run()
    assert proc.returncode == 0, _out(proc)
    assert DONE in proc.stdout, _out(proc)
    assert (sb.pin(), sb.lock_pin(), sb.pyproject_version()) == ("1.0.1", "1.0.1", "1.0.1")
    _release_commits_made(sb)
    assert sb.events().count("twine upload 1.0.1") == 1
    assert sb.api_version() == "1.0.1"


# ── every post-upload failure row recovers with --skip-pypi ──────────────────

ROWS = [
    pytest.param(
        {"upload_publishes": 0}, "PyPI did not show prospectai 1.0.1", ("1.0.0", "1.0.0"), True,
        id="pypi-wait-timeout",
    ),
    pytest.param(
        {"lock_failures": 5}, "lock compile failed after 5 attempts", ("1.0.1", "1.0.0"), False,
        id="lock-compile-failure",
    ),
    pytest.param(
        {"modal_failures": 1}, "fake modal: simulated deploy failure", ("1.0.1", "1.0.1"), False,
        id="modal-deploy-failure",
    ),
    pytest.param(
        {"modal_stale": 1}, "SMOKE FAILED", ("1.0.1", "1.0.1"), False,
        id="smoke-failure",
    ),
]


@pytest.mark.parametrize("knobs, marker, state, publish_first", ROWS)
def test_skip_pypi_recovers_after_post_upload_failure(sandbox, knobs, marker, state, publish_first):
    sb = sandbox()
    for name, value in knobs.items():
        sb.set_knob(name, value)

    first = sb.run()
    assert first.returncode != 0, _out(first)
    assert marker in first.stdout + first.stderr, _out(first)
    assert HINT_A in first.stderr and HINT_B in first.stderr, _out(first)
    assert (sb.pin(), sb.lock_pin()) == state
    assert sb.pyproject_version() == "1.0.1"
    assert sb.ahead(sb.pa) == 0 and sb.ahead(sb.be) == 0

    if publish_first:
        sb.publish("1.0.1")

    before = sb.snapshot()
    preflight = sb.run("--preflight-only", "--skip-pypi")
    assert preflight.returncode == 0, _out(preflight)
    assert any(line.startswith("PREFLIGHT OK") for line in preflight.stdout.splitlines()), _out(preflight)
    assert sb.snapshot() == before

    recovery = sb.run("--skip-pypi")
    assert recovery.returncode == 0, _out(recovery)
    assert DONE in recovery.stdout, _out(recovery)
    _release_commits_made(sb)
    assert sb.api_version() == "1.0.1"
    events = sb.events()
    assert events.count("twine upload 1.0.1") == 1
    assert events.count("uv build 1.0.1") == 1


# ── --preflight-only names the recovery mode ─────────────────────────────────

def test_skip_pypi_preflight_only_reports_recovery_mode(sandbox):
    sb = sandbox()
    sb.set_knob("modal_failures", 1)
    first = sb.run()
    assert first.returncode != 0, _out(first)
    before = sb.snapshot()

    proc = sb.run("--preflight-only", "--skip-pypi")
    assert proc.returncode == 0, _out(proc)
    assert "PREFLIGHT OK (--skip-pypi)" in proc.stdout, _out(proc)
    assert sb.snapshot() == before


# ── a version that is not on PyPI is refused before anything is touched ──────

def test_skip_pypi_refuses_version_not_on_pypi(sandbox):
    sb = sandbox()
    (sb.pa / "pyproject.toml").write_text('[project]\nname = "prospectai"\nversion = "1.0.1"\n')
    before = sb.snapshot()

    proc = sb.run("--skip-pypi")
    assert proc.returncode != 0, _out(proc)
    assert "--skip-pypi only deploys a version that is already on PyPI" in proc.stderr, _out(proc)
    assert HINT_A not in proc.stderr and HINT_B not in proc.stderr, _out(proc)
    assert (sb.pin(), sb.lock_pin()) == ("1.0.0", "1.0.0")
    assert sb.snapshot() == before
    assert not [e for e in sb.events() if e.startswith(("lock", "modal"))]
    assert sb.ahead(sb.pa) == 0 and sb.ahead(sb.be) == 0


# ── normal releases keep the full pre-upload preflight (D-11) ────────────────

def test_normal_preflight_still_requires_pin_equals_pyproject(sandbox):
    sb = sandbox(pin_version="0.9.9")
    proc = sb.run("--preflight-only")
    assert proc.returncode != 0, _out(proc)
    assert REFUSE_PIN in proc.stderr, _out(proc)


# ── a flaky PyPI wait completes in one run (review WR-02) ────────────────────

def test_transient_pypi_errors_during_wait_do_not_abort_release(sandbox):
    sb = sandbox()
    sb.set_knob("transient_after_upload", 3)

    proc = sb.run()
    assert proc.returncode == 0, _out(proc)
    assert DONE in proc.stdout, _out(proc)
    assert "PIN CHECK WAIT" in proc.stderr, _out(proc)
    _release_commits_made(sb)
    assert sb.events().count("twine upload 1.0.1") == 1
