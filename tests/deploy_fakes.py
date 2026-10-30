"""
Offline stand-ins for the release tools, used only by test_deploy_recovery.py
(review CR-01, gap closure 01-13).

This is a stdlib-only script, never imported by pytest. The sandbox's shell
wrappers run it as:

    "$DEPLOY_HARNESS_PY" -I "$DEPLOY_HARNESS_TOOLS" <tool> <args...>

so the real scripts/deploy.sh and the real prospectai-backend/scripts/check_pin.py
run end to end with no network, no PyPI, no Modal and no operator credentials.

Environment contract:
    DEPLOY_HARNESS_CONTROL   the control directory (below)
    DEPLOY_HARNESS_PY        the interpreter that runs this file
    DEPLOY_HARNESS_TOOLS     this file's path
    PROSPECTAI_BACKEND_URL   the fake backend URL deploy.sh smoke-tests

Control directory contract:
    pypi/<X.Y.Z>             exists when that version is "published"
    integer knob files, absent meaning the default:
        upload_publishes     (default 1) 0 = twine upload does not publish
        transient_after_upload  (0) PyPI probe failures armed by the upload
        pypi_transient_remaining (0) PyPI probes that still raise URLError
        lock_failures        (0) lock compiles that still fail
        modal_failures       (0) modal deploys that still fail
        modal_stale          (0) modal deploys that exit 0 but change nothing
    text knob file (plan 02-04, pre-upload backend gate):
        wheel_gate_failure   "compile" or "suite" makes that gate step fail;
                             absent or "0" = the gate passes
    events.log               append-only, one line per event
    api_version.json         what the "deployed" backend reports

Tools:
    uv           venv / pip compile / pip sync / pip install / build / tool run twine
    modal        deploy serve.py
    lock         the fake lock.sh compile (cwd is the backend root)
    venv-python  the preflight venv interpreter: fake pytest, the installed-version
                 probe (-c), and check_pin.py run with urlopen and the clock
                 replaced inside its process

Every unexpected call exits 97, so a deploy.sh change that starts using a new
tool fails loudly instead of silently reaching a real one.
"""

import io
import json
import os
import re
import runpy
import sys
import urllib.error
import urllib.request

CONTROL = os.environ.get("DEPLOY_HARNESS_CONTROL", "")


def _path(name):
    return os.path.join(CONTROL, name)


def _knob(name, default=0):
    try:
        with open(_path(name)) as handle:
            return int(handle.read().strip())
    except (OSError, ValueError):
        return default


def _text_knob(name, default=""):
    try:
        with open(_path(name)) as handle:
            return handle.read().strip() or default
    except OSError:
        return default


def _set_knob(name, value):
    with open(_path(name), "w") as handle:
        handle.write(str(value))


def _log(line):
    with open(_path("events.log"), "a") as handle:
        handle.write(line + "\n")


def _published(version):
    return os.path.exists(_path(os.path.join("pypi", version)))


def _unexpected(what, args):
    sys.stderr.write("deploy_fakes: unexpected %s call: %s\n" % (what, " ".join(args)))
    return 97


def _pyproject_version(directory):
    with open(os.path.join(directory, "pyproject.toml")) as handle:
        match = re.search(r'^version\s*=\s*"([^"]+)"', handle.read(), re.MULTILINE)
    return match.group(1)


def _requirement_version(path):
    with open(path) as handle:
        for line in handle:
            match = re.match(r"^prospectai==(\d+\.\d+\.\d+)\s*$", line.strip())
            if match:
                return match.group(1)
    return None


# ── uv ───────────────────────────────────────────────────────────────────────

_VENV_WRAPPER = (
    '#!/bin/sh\n'
    'DEPLOY_HARNESS_VENV="$(cd "$(dirname "$0")/.." && pwd)" '
    'exec "$DEPLOY_HARNESS_PY" -I "$DEPLOY_HARNESS_TOOLS" venv-python "$@"\n'
)


def _lock_version(path):
    """The prospectai version a compiled lock pins, or None."""
    try:
        return _requirement_version(path)
    except OSError:
        return None


def _gate_compile(args):
    """Fake `uv pip compile` for the pre-upload backend gate.

    Resolves prospectai only from --find-links, like the real gate: the wheel for
    the pinned version must be in that directory, otherwise there is no solution.
    """
    requirements = args[2]
    version = _requirement_version(requirements)
    out = args[args.index("-o") + 1] if "-o" in args else None
    find_links = args[args.index("--find-links") + 1] if "--find-links" in args else None
    if version is None or out is None or find_links is None:
        return _unexpected("uv", ["pip", "compile"] + args[2:])
    wheel = os.path.join(find_links, "prospectai-%s-py3-none-any.whl" % version)
    if _text_knob("wheel_gate_failure") == "compile" or not os.path.exists(wheel):
        _log("wheelgate compile fail %s" % version)
        sys.stderr.write("fake uv: No solution found when resolving dependencies (prospectai %s)\n" % version)
        return 1
    with open(out, "w") as handle:
        handle.write("prospectai==%s\n    # via -r requirements-serve.txt\n" % version)
    _log("wheelgate compile %s" % version)
    return 0


def tool_uv(args):
    if args[:1] == ["venv"]:
        target = args[-1]
        os.makedirs(os.path.join(target, "bin"), exist_ok=True)
        python = os.path.join(target, "bin", "python")
        with open(python, "w") as handle:
            handle.write(_VENV_WRAPPER)
        os.chmod(python, 0o755)
        return 0
    if args[:2] == ["pip", "compile"]:
        return _gate_compile(args)
    if args[:2] == ["pip", "sync"]:
        # Record which prospectai a venv received, for the version probe.
        python = args[args.index("--python") + 1] if "--python" in args else None
        version = _lock_version(args[-1])
        if python and version:
            venv = os.path.dirname(os.path.dirname(python))
            with open(os.path.join(venv, "installed_prospectai"), "w") as handle:
                handle.write(version)
            if os.path.basename(os.path.dirname(venv)) == "wheelgate":
                _log("wheelgate sync %s" % version)
        return 0
    if args[:2] == ["pip", "install"]:
        return 0
    if args[:1] == ["build"] and "--out-dir" in args:
        out_dir = args[args.index("--out-dir") + 1]
        version = _pyproject_version(os.getcwd())
        os.makedirs(out_dir, exist_ok=True)
        for name in ("prospectai-%s-py3-none-any.whl" % version, "prospectai-%s.tar.gz" % version):
            with open(os.path.join(out_dir, name), "w") as handle:
                handle.write("fake distribution\n")
        _log("uv build %s" % version)
        return 0
    if args[:3] in (["tool", "run", "twine"],):
        rest = args[3:]
        if rest[:1] == ["--version"] or rest[:1] == ["check"]:
            return 0
        if rest[:1] == ["upload"]:
            versions = set()
            for name in rest[1:]:
                match = re.search(r"prospectai-(\d+\.\d+\.\d+)", os.path.basename(name))
                if match:
                    versions.add(match.group(1))
            if len(versions) != 1:
                sys.stderr.write("deploy_fakes: twine upload needs one prospectai version, got %r\n" % sorted(versions))
                return 97
            version = versions.pop()
            _log("twine upload %s" % version)
            if _knob("upload_publishes", 1):
                os.makedirs(_path("pypi"), exist_ok=True)
                open(_path(os.path.join("pypi", version)), "w").close()
            _set_knob("pypi_transient_remaining", _knob("transient_after_upload"))
            return 0
    return _unexpected("uv", args)


# ── modal ────────────────────────────────────────────────────────────────────

def tool_modal(args):
    if args != ["deploy", "serve.py"]:
        return _unexpected("modal", args)
    if _knob("modal_failures") > 0:
        _set_knob("modal_failures", _knob("modal_failures") - 1)
        sys.stderr.write("fake modal: simulated deploy failure\n")
        _log("modal deploy fail")
        return 1
    version = _requirement_version("requirements-serve.lock")
    if version is None:
        sys.stderr.write("fake modal: requirements-serve.lock has no prospectai pin\n")
        return 1
    if _knob("modal_stale") > 0:
        _set_knob("modal_stale", _knob("modal_stale") - 1)
        _log("modal deploy stale %s" % version)
        return 0
    with open(_path("api_version.json"), "w") as handle:
        json.dump({"version": version, "prospectai": version, "backend_sha": os.environ.get("BACKEND_SHA")}, handle)
    _log("modal deploy ok %s" % version)
    return 0


# ── lock ─────────────────────────────────────────────────────────────────────

def tool_lock(args):
    version = _requirement_version("requirements-serve.txt")
    if version is None:
        sys.stderr.write("fake lock: requirements-serve.txt has no prospectai pin\n")
        return 1
    failing = _knob("lock_failures") > 0
    if failing:
        _set_knob("lock_failures", _knob("lock_failures") - 1)
    # The simple index lags the JSON API: an unpublished pin cannot resolve.
    if failing or not _published(version):
        _log("lock fail %s" % version)
        sys.stderr.write("fake lock: No solution found when resolving dependencies (prospectai %s)\n" % version)
        return 1
    with open("requirements-serve.lock", "w") as handle:
        handle.write("prospectai==%s\n    # via -r requirements-serve.txt\n" % version)
    _log("lock ok %s" % version)
    return 0


# ── venv-python ──────────────────────────────────────────────────────────────

class _Response(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def _fake_urlopen(url, data=None, timeout=None, **kwargs):
    url = getattr(url, "full_url", url)
    pypi = re.match(r"^https://pypi\.org/pypi/prospectai/(\d+\.\d+\.\d+)/json$", url)
    if pypi:
        if _knob("pypi_transient_remaining") > 0:
            _set_knob("pypi_transient_remaining", _knob("pypi_transient_remaining") - 1)
            raise urllib.error.URLError("simulated transient PyPI failure")
        if _published(pypi.group(1)):
            return _Response(b"{}")
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
    backend = os.environ.get("PROSPECTAI_BACKEND_URL", "").rstrip("/")
    if backend and url == backend + "/api/version":
        try:
            with open(_path("api_version.json"), "rb") as handle:
                return _Response(handle.read())
        except OSError:
            raise urllib.error.URLError("backend not deployed")
    raise urllib.error.URLError("network disabled in deploy harness")


def tool_venv_python(args):
    venv = os.environ.get("DEPLOY_HARNESS_VENV", "")
    if args[:1] == ["-c"]:
        # importlib.metadata.version("prospectai") probe in the gate venv
        try:
            with open(os.path.join(venv, "installed_prospectai")) as handle:
                print(handle.read().strip())
            return 0
        except OSError:
            sys.stderr.write("fake venv: prospectai is not installed\n")
            return 1
    if args[:2] == ["-m", "pytest"]:
        if os.path.basename(os.path.dirname(venv)) == "wheelgate":
            if _text_knob("wheel_gate_failure") == "suite":
                _log("wheelgate suite fail")
                print("fake suite: FAILED")
                return 1
            _log("wheelgate suite")
        print("fake suite: passed")
        return 0
    if args and args[0].endswith("check_pin.py"):
        clock = _Clock()
        urllib.request.urlopen = _fake_urlopen
        import time
        time.monotonic = clock.monotonic
        time.sleep = clock.sleep
        sys.argv = [args[0]] + args[1:]
        try:
            runpy.run_path(args[0], run_name="__main__")
        except SystemExit as exc:
            return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        return 0
    return _unexpected("venv-python", args)


TOOLS = {
    "uv": tool_uv,
    "modal": tool_modal,
    "lock": tool_lock,
    "venv-python": tool_venv_python,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in TOOLS:
        return _unexpected("tool", argv[1:])
    if not CONTROL:
        sys.stderr.write("deploy_fakes: DEPLOY_HARNESS_CONTROL is not set\n")
        return 97
    return TOOLS[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
