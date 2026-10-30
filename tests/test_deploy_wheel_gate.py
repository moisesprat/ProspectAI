"""Tests for the pre-upload backend gate in deploy.sh (review WR-01, decision D-05).

A normal release resolves the backend's requirements with the pin set to the
freshly built local wheel, installs that set into a fresh venv and runs the
backend offline suite against it, after `uv build` and `twine check` and before
`twine upload`. A failing gate uploads nothing, restores pyproject.toml and
README.md, removes dist/ and exits non-zero.

The sandbox is the one from test_deploy_recovery.py (fake uv, modal, sleep; real
deploy.sh and check_pin.py), extended by deploy_fakes.py with a gate-aware
`uv pip compile`, venv and pytest. Like that module, this one is skipped without
the sibling prospectai-backend checkout (the ProspectAI CI case) and is enforced
by the deploy.sh preflight (D-30).
"""
import pytest

from tests.test_deploy_recovery import CHECK_PIN, DONE, HINT_A, Sandbox, _out

pytestmark = pytest.mark.skipif(
    not CHECK_PIN.is_file(),
    reason="sibling prospectai-backend/scripts/check_pin.py not found "
    "(ProspectAI CI has no backend checkout); the deploy.sh preflight enforces this module (D-30)",
)

NOTHING_UPLOADED = "nothing was uploaded"


@pytest.fixture
def sandbox(tmp_path):
    def make(pin_version="1.0.0"):
        return Sandbox(tmp_path, pin_version)

    return make


def _committed(sb, repo, path):
    return sb.git(repo, "show", "HEAD:" + path)


def test_gate_runs_before_upload(sandbox):
    sb = sandbox()
    proc = sb.run()
    assert proc.returncode == 0, _out(proc)
    assert DONE in proc.stdout, _out(proc)
    assert "Pre-upload backend gate" in proc.stdout, _out(proc)

    events = sb.events()
    for step in ("uv build 1.0.1", "wheelgate compile 1.0.1", "wheelgate sync 1.0.1", "wheelgate suite", "twine upload 1.0.1"):
        assert step in events, _out(proc) + "\n" + "\n".join(events)
    assert (
        events.index("uv build 1.0.1")
        < events.index("wheelgate compile 1.0.1")
        < events.index("wheelgate sync 1.0.1")
        < events.index("wheelgate suite")
        < events.index("twine upload 1.0.1")
    )
    assert events.count("twine upload 1.0.1") == 1


@pytest.mark.parametrize("failure", ["compile", "suite"])
def test_gate_failure_uploads_nothing(sandbox, failure):
    """test_compile_failure_uploads_nothing / test_suite_failure_uploads_nothing."""
    sb = sandbox()
    readme_before = (sb.pa / "README.md").read_text()
    pyproject_before = (sb.pa / "pyproject.toml").read_text()
    sb.set_knob("wheel_gate_failure", failure)

    proc = sb.run()
    assert proc.returncode != 0, _out(proc)
    assert NOTHING_UPLOADED in proc.stderr, _out(proc)
    assert HINT_A not in proc.stderr, _out(proc)
    assert not [e for e in sb.events() if e.startswith("twine upload")], sb.events()
    assert not [e for e in sb.events() if e.startswith(("lock", "modal"))], sb.events()
    assert any(e.startswith("wheelgate %s fail" % failure) for e in sb.events()), sb.events()

    assert (sb.pa / "pyproject.toml").read_text() == pyproject_before
    assert (sb.pa / "README.md").read_text() == readme_before
    assert sb.porcelain(sb.pa) == ""
    assert sb.porcelain(sb.be) == ""
    assert not (sb.pa / "dist").exists()
    assert sb.ahead(sb.pa) == 0 and sb.ahead(sb.be) == 0
    assert (sb.pin(), sb.lock_pin(), sb.pyproject_version()) == ("1.0.0", "1.0.0", "1.0.0")

    # The next run starts clean: with the failure cleared, the same tree releases.
    sb.set_knob("wheel_gate_failure", 0)
    again = sb.run()
    assert again.returncode == 0, _out(again)
    assert DONE in again.stdout, _out(again)


def test_skip_pypi_does_not_run_gate(sandbox):
    sb = sandbox()
    sb.set_knob("modal_failures", 1)
    first = sb.run()
    assert first.returncode != 0, _out(first)
    gate_events_first = [e for e in sb.events() if e.startswith("wheelgate")]
    assert gate_events_first  # the normal release ran the gate once

    # A failing gate must not matter on recovery: it is never invoked.
    sb.set_knob("wheel_gate_failure", "suite")
    recovery = sb.run("--skip-pypi")
    assert recovery.returncode == 0, _out(recovery)
    assert "Pre-upload backend gate" not in recovery.stdout, _out(recovery)
    assert [e for e in sb.events() if e.startswith("wheelgate")] == gate_events_first


def test_preflight_only_does_not_run_gate(sandbox):
    sb = sandbox()
    proc = sb.run("--preflight-only")
    assert proc.returncode == 0, _out(proc)
    assert "Pre-upload backend gate" not in proc.stdout, _out(proc)
    assert not [e for e in sb.events() if e.startswith("wheelgate")]
