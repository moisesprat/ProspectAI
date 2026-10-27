#!/usr/bin/env bash
# =============================================================================
# ProspectAI — Release & Deploy Script (the single deploy path)
#
# Steps:
#   0. Gates: both repos on `main` == origin/main, clean trees, both offline
#      suites green in fresh venvs built from their locks, and
#      pin == pyproject == PyPI == lock (prospectai-backend/scripts/check_pin.py)
#   1. Bumps the version in pyproject.toml (the only version source)
#   2. Updates the README.md version badge and releases the hand-written
#      "### Unreleased — <title>" notes as the new version (preflight refuses
#      when they are missing)
#   3. Builds wheel + sdist, uploads to PyPI via twine, polls PyPI until live
#   4. Rewrites the prospectai pin in prospectai-backend/requirements-serve.txt,
#      recompiles requirements-serve.lock and re-runs check_pin
#   5. Deploys to Modal with BACKEND_SHA / DEPLOYED_AT baked into the image
#   6. Polls the live /api/version and fails unless it reports the pin and the
#      baked backend_sha
#   7. Only then creates one local commit per repo. It never pushes.
#
# Usage:
#   ./scripts/deploy.sh                  # auto-bump patch (e.g. 1.5.7 -> 1.5.8)
#   ./scripts/deploy.sh 1.6.0            # explicit version
#   ./scripts/deploy.sh --skip-pypi      # recover: deploy the version already in
#                                        # pyproject.toml / on PyPI, no bump
#   ./scripts/deploy.sh --preflight-only # run every gate, change nothing
#   ./scripts/deploy.sh --preflight-only --allow-dirty      # skip clean-tree gate
#   ./scripts/deploy.sh --preflight-only --allow-off-main   # skip branch gate
#   ./scripts/deploy.sh -h | --help
#
# Requirements:
#   uv (https://docs.astral.sh/uv/), an authenticated modal CLI
#   (`modal token set`), and a PyPI token in ~/.pypirc or TWINE_PASSWORD for twine.
#
# Policies:
#   - A raw `modal deploy serve.py` bypasses every check here and shows
#     `backend_sha: unknown` in /api/version. Do not use it (D-10).
#   - The private backend repo has no required CI; its gate is this preflight,
#     which runs the backend offline suite from the backend lock (D-23).
#   - On success the script makes one commit per repo and never pushes. The
#     operator publishes `main` afterwards (D-25).
#   - Releases run only when both repos are on `main` and identical to
#     `origin/main`, meaning merged, CI-checked code. --allow-off-main exists
#     only for preflight development, and is rejected without --preflight-only
#     (D-27). --allow-dirty is likewise preflight-only.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_ROOT="$(cd "$REPO_ROOT/../prospectai-backend" 2>/dev/null && pwd)" || {
  echo "ERROR: prospectai-backend not found next to $REPO_ROOT" >&2
  exit 1
}
PYPROJECT="$REPO_ROOT/pyproject.toml"
README="$REPO_ROOT/README.md"
DIST_DIR="$REPO_ROOT/dist"
BACKEND_URL="${PROSPECTAI_BACKEND_URL:-https://moisesprat--prospectai-backend-fastapi-app.modal.run}"
LOCK_DIR="${TMPDIR:-/tmp}/prospectai-deploy.lock"

# Resolve python3 (used only for tiny one-off text edits and version math)
PYTHON=$(command -v python3 || command -v python) || {
  echo "ERROR: python3 not found" >&2
  exit 1
}

SKIP_PYPI=false
PREFLIGHT_ONLY=false
ALLOW_DIRTY=false
ALLOW_OFF_MAIN=false
EXPLICIT_VERSION=""
LOCK_HELD=0
TMP_VENVS=""
UPLOADED=0
NEW_VERSION=""

log() { echo "==> $*"; }
die() { echo "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Usage: scripts/deploy.sh [X.Y.Z] [--skip-pypi] [--preflight-only]
                         [--allow-dirty] [--allow-off-main] [-h|--help]

  X.Y.Z             explicit release version (default: auto-bump the patch)
  --skip-pypi       deploy the version already in pyproject.toml / on PyPI
                    (recovery after a failed post-upload step); no bump
  --preflight-only  run every gate and exit; changes nothing
  --allow-dirty     skip the clean-tree gate (only valid with --preflight-only)
  --allow-off-main  skip the main == origin/main gate (only valid with
                    --preflight-only)
  -h, --help        show this help
USAGE
}

# ── Argument parsing (before any side effect) ────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --skip-pypi)      SKIP_PYPI=true ;;
    --preflight-only) PREFLIGHT_ONLY=true ;;
    --allow-dirty)    ALLOW_DIRTY=true ;;
    --allow-off-main) ALLOW_OFF_MAIN=true ;;
    -h|--help)        usage; exit 0 ;;
    *)
      if [[ "$arg" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        EXPLICIT_VERSION="$arg"
      else
        echo "ERROR: unknown argument: $arg" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

if [[ "$ALLOW_DIRTY" == true && "$PREFLIGHT_ONLY" != true ]]; then
  echo "ERROR: --allow-dirty is only valid with --preflight-only" >&2
  exit 2
fi
if [[ "$ALLOW_OFF_MAIN" == true && "$PREFLIGHT_ONLY" != true ]]; then
  echo "ERROR: --allow-off-main is only valid with --preflight-only" >&2
  exit 2
fi
if [[ "$SKIP_PYPI" == true && -n "$EXPLICIT_VERSION" ]]; then
  echo "ERROR: --skip-pypi deploys the version already in pyproject.toml; do not pass X.Y.Z" >&2
  exit 2
fi

# ── Concurrency guard + cleanup trap ─────────────────────────────────────────
cleanup() {
  local rc=$?
  if [[ -n "$TMP_VENVS" && -d "$TMP_VENVS" ]]; then rm -rf "$TMP_VENVS"; fi
  if [[ "$LOCK_HELD" == 1 ]]; then rmdir "$LOCK_DIR" 2>/dev/null || true; fi
  if [[ $rc -ne 0 && "$UPLOADED" == 1 ]]; then
    echo "" >&2
    echo "prospectai $NEW_VERSION is on PyPI but not verified in production; no commits were made. Fix the cause, then run: scripts/deploy.sh --skip-pypi" >&2
  fi
  return $rc
}
trap cleanup EXIT

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  die "another deploy.sh is running (remove $LOCK_DIR if stale)"
fi
LOCK_HELD=1

# ── Tree gates ───────────────────────────────────────────────────────────────
# Release only merged, CI-checked code: each repo on main and equal to
# origin/main after a fetch (D-27). The messages name branches only and never
# suggest a command that writes to a remote.
require_main_up_to_date() {
  local repo branch counts ahead behind
  for repo in "$REPO_ROOT" "$BACKEND_ROOT"; do
    branch=$(git -C "$repo" branch --show-current)
    if [[ "$branch" != "main" ]]; then
      die "REFUSING: $repo is on '$branch', not on main — merge its Phase 1 PR, then switch to main and fast-forward (D-27)"
    fi
    git -C "$repo" fetch --quiet origin main || die "REFUSING: cannot fetch origin/main for $repo"
    if [[ "$(git -C "$repo" rev-parse HEAD)" != "$(git -C "$repo" rev-parse origin/main)" ]]; then
      counts=$(git -C "$repo" rev-list --left-right --count HEAD...origin/main)
      ahead=${counts%%[[:space:]]*}
      behind=${counts##*[[:space:]]}
      die "REFUSING: $repo main differs from origin/main ($ahead ahead, $behind behind) — release only what is on origin/main (D-27)"
    fi
  done
}

# Dirty paths that are not on the allow list. In --skip-pypi mode the four
# files deploy.sh itself rewrites may be dirty (recovery after a failed
# post-upload step); everything else still refuses.
dirty_paths() {
  local repo="$1" allowed="$2" line path out=""
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    path="${line:3}"
    if [[ "$SKIP_PYPI" == true && " $allowed " == *" $path "* ]]; then continue; fi
    out+="$line"$'\n'
  done < <(git -C "$repo" status --porcelain)
  printf '%s' "$out"
}

require_clean_trees() {
  local pa be
  pa=$(dirty_paths "$REPO_ROOT" "pyproject.toml README.md")
  if [[ -n "$pa" ]]; then
    die "REFUSING: $REPO_ROOT has uncommitted changes:"$'\n'"$pa"
  fi
  be=$(dirty_paths "$BACKEND_ROOT" "requirements-serve.txt requirements-serve.lock")
  if [[ -n "$be" ]]; then
    die "REFUSING: $BACKEND_ROOT has uncommitted changes:"$'\n'"$be"
  fi
}

if [[ "$ALLOW_OFF_MAIN" != true ]]; then require_main_up_to_date; fi
if [[ "$ALLOW_DIRTY" != true ]]; then require_clean_trees; fi

# Credential presence is tested only; neither the file nor the variable is ever
# printed, and shell tracing is never enabled.
require_release_tools() {
  command -v modal >/dev/null 2>&1 || die "modal CLI not found — uv tool install modal && modal token set"
  if [[ "$SKIP_PYPI" != true ]]; then
    uv tool run twine --version >/dev/null 2>&1 || die "twine not available via 'uv tool run twine' — check uv and network"
    if [[ ! -f "$HOME/.pypirc" && -z "${TWINE_PASSWORD:-}" ]]; then
      die "PyPI credentials not configured (~/.pypirc or TWINE_PASSWORD)"
    fi
  fi
}
if [[ "$PREFLIGHT_ONLY" != true ]]; then
  command -v uv >/dev/null 2>&1 || die "uv not found — install from https://docs.astral.sh/uv/"
  require_release_tools
fi

# ── Resolve version ──────────────────────────────────────────────────────────
# python3 extracts the version — avoids macOS sed/grep parsing edge cases
CURRENT_VERSION=$("$PYTHON" -c "
import re, sys
content = open(sys.argv[1]).read()
m = re.search(r'^version\s*=\s*\"([^\"]+)\"', content, re.MULTILINE)
print(m.group(1) if m else sys.exit('ERROR: version not found in pyproject.toml'))
" "$PYPROJECT")

if [[ "$SKIP_PYPI" == true ]]; then
  NEW_VERSION="$CURRENT_VERSION"
elif [[ -n "$EXPLICIT_VERSION" ]]; then
  NEW_VERSION="$EXPLICIT_VERSION"
else
  # Auto-bump patch using python arithmetic (avoids IFS/read issues on macOS)
  NEW_VERSION=$("$PYTHON" -c "
import sys
v = sys.argv[1].split('.')
v[2] = str(int(v[2]) + 1)
print('.'.join(v))
" "$CURRENT_VERSION")
fi

if [[ "$SKIP_PYPI" != true ]]; then
  "$PYTHON" -c "
import sys
cur, new = (tuple(int(p) for p in v.split('.')) for v in sys.argv[1:3])
sys.exit(0 if new > cur else 1)
" "$CURRENT_VERSION" "$NEW_VERSION" || die "REFUSING: new version $NEW_VERSION is not greater than current $CURRENT_VERSION"
fi

log "Version: $CURRENT_VERSION → $NEW_VERSION"

# Release notes are written by hand, for ProspectAI users, under a
# "### Unreleased — <title>" entry at the top of README.md's "## Release Notes"
# section. They are never generated from commit subjects, which are written for
# developers and leaked plan ids and decision codes into the public changelog
# (v1.9.3). check_release_notes gates the release on that entry; update_readme
# renames it to the new version at release time.
check_release_notes() {
  "$PYTHON" - "$README" <<'PYEOF'
import re, sys
content = open(sys.argv[1]).read()
rn = re.search(r'## Release Notes\n\n(.*?)(?:\n## |\Z)', content, re.DOTALL)
if not rn:
    sys.exit("README.md has no '## Release Notes' section")
first = rn.group(1).lstrip()
m = re.match(r'### Unreleased — (\S.*)\n((?:- \S.*\n?)+)', first)
if not m:
    sys.exit("README.md release notes must start with '### Unreleased — <title>' "
             "followed by at least one '- ' bullet written for users")
PYEOF
}

# ── Preflight: offline suites from the locks, then the pin check ─────────────
CHECK_PIN=()

build_preflight_venvs() {
  command -v uv >/dev/null 2>&1 || die "uv not found — install from https://docs.astral.sh/uv/"
  TMP_VENVS=$(mktemp -d)
  log "Building preflight venvs from the locks"
  uv venv --quiet --python 3.11 "$TMP_VENVS/pa"
  uv pip sync --quiet --python "$TMP_VENVS/pa/bin/python" "$REPO_ROOT/requirements.txt"
  uv venv --quiet --python 3.11 "$TMP_VENVS/be"
  uv pip sync --quiet --python "$TMP_VENVS/be/bin/python" "$BACKEND_ROOT/requirements-serve.lock"
  uv pip install --quiet --python "$TMP_VENVS/be/bin/python" -r "$BACKEND_ROOT/requirements-dev.txt"
  CHECK_PIN=("$TMP_VENVS/be/bin/python" "$BACKEND_ROOT/scripts/check_pin.py")
}

run_offline_suites() {
  log "ProspectAI offline suite"
  (cd "$REPO_ROOT" && CREWAI_TRACING_ENABLED=false "$TMP_VENVS/pa/bin/python" -m pytest --disable-socket --allow-unix-socket -q) \
    || die "REFUSING: ProspectAI offline suite failed (D-23)"
  log "prospectai-backend offline suite"
  (cd "$BACKEND_ROOT" && CREWAI_TRACING_ENABLED=false "$TMP_VENVS/be/bin/python" -m pytest --disable-socket --allow-unix-socket -q tests) \
    || die "REFUSING: prospectai-backend offline suite failed (D-23)"
}

build_preflight_venvs
run_offline_suites

log "Pin preflight (pin = pyproject = PyPI = lock)"
"${CHECK_PIN[@]}" --pyproject "$PYPROJECT" || die "REFUSING: pin preflight failed"
if [[ "$SKIP_PYPI" != true ]]; then
  "${CHECK_PIN[@]}" --unpublished "$NEW_VERSION" || die "REFUSING: pin preflight failed"
  log "Release notes preflight (README '### Unreleased — <title>')"
  check_release_notes || die "REFUSING: write the user-facing release notes first"
fi

if [[ "$PREFLIGHT_ONLY" == true ]]; then
  msg="PREFLIGHT OK: prospectai $CURRENT_VERSION (pin = pyproject = PyPI = lock); next release would be $NEW_VERSION; both offline suites green"
  if [[ "$ALLOW_OFF_MAIN" == true ]]; then msg+="; branch gate SKIPPED (--allow-off-main)"; fi
  echo "$msg"
  exit 0
fi

# ── Release path ─────────────────────────────────────────────────────────────
# Each step dies with a clear message. Until the smoke test passes, no commit is
# made, so a failure after the upload is recovered with `--skip-pypi`.

# Rewrite exactly one line of a file with a regex; exit 1 unless exactly one
# line matched, so a rewrite can never be a silent no-op.
rewrite_one_line() {
  "$PYTHON" - "$@" <<'PYEOF'
import re, sys
path, pattern, replacement = sys.argv[1], sys.argv[2], sys.argv[3]
content = open(path).read()
new, n = re.subn(pattern, lambda m: replacement, content, flags=re.MULTILINE)
if n != 1:
    sys.exit(f"ERROR: expected exactly one line matching {pattern!r} in {path}, found {n}")
open(path, "w").write(new)
PYEOF
}

update_readme() {
  "$PYTHON" - "$README" "$NEW_VERSION" "$CURRENT_VERSION" <<'PYEOF'
import re, sys

readme_path  = sys.argv[1]
new_version  = sys.argv[2]
prev_version = sys.argv[3]

content = open(readme_path).read()

content = content.replace(
    f"**Current release: v{prev_version}**",
    f"**Current release: v{new_version}**",
)

rn = re.search(r'(## Release Notes\n\n)(.*?)(\n## )', content, re.DOTALL)
if not rn:
    sys.exit("ERROR: '## Release Notes' section not found")
body = rn.group(2).rstrip()
entries = [e.strip() for e in re.split(r'(?=^### )', body, flags=re.MULTILINE) if e.strip()]
if not entries or not entries[0].startswith("### Unreleased — "):
    sys.exit("ERROR: the first release-notes entry is not '### Unreleased — <title>'")
entries[0] = entries[0].replace("### Unreleased — ", f"### v{new_version} — ", 1)
# The released entry + 4 earlier ones = 5 total
kept = "\n\n".join(entries[:5])
content = content[:rn.start()] + rn.group(1) + kept + "\n" + rn.group(3) + content[rn.end():]

open(readme_path, "w").write(content)
print(f"    README.md updated — Unreleased notes released as v{new_version}, last 5 kept")
PYEOF
}

if [[ "$SKIP_PYPI" != true ]]; then
  log "Bumping pyproject.toml to $NEW_VERSION"
  rewrite_one_line "$PYPROJECT" "^version = \"$CURRENT_VERSION\"\$" "version = \"$NEW_VERSION\""
  [[ -f "$README" ]] && update_readme

  log "Building wheel + sdist"
  rm -rf "$DIST_DIR"
  (cd "$REPO_ROOT" && uv build --out-dir "$DIST_DIR")
  uv tool run twine check "$DIST_DIR"/*

  log "Uploading to PyPI"
  uv tool run twine upload "$DIST_DIR"/*
  UPLOADED=1
  echo "    Uploaded prospectai==$NEW_VERSION to PyPI"

  log "Waiting for PyPI to serve $NEW_VERSION"
  "${CHECK_PIN[@]}" --wait-pypi "$NEW_VERSION" --timeout 600 \
    || die "PyPI did not show prospectai $NEW_VERSION within 600 s"
else
  log "Skipping PyPI upload (--skip-pypi): deploying published $NEW_VERSION"
  UPLOADED=1
fi

log "Rewriting backend pin to prospectai==$NEW_VERSION"
rewrite_one_line "$BACKEND_ROOT/requirements-serve.txt" '^prospectai==[0-9]+\.[0-9]+\.[0-9]+$' "prospectai==$NEW_VERSION"

log "Recompiling backend lock (lock.sh --refresh-package prospectai)"
lock_ok=false
for attempt in 1 2 3 4 5; do
  if bash "$BACKEND_ROOT/scripts/lock.sh" --refresh-package prospectai --quiet; then
    lock_ok=true
    break
  fi
  echo "    lock compile attempt $attempt/5 failed — the simple index can lag the JSON API" >&2
  if [[ $attempt -lt 5 ]]; then sleep 30; fi
done
[[ "$lock_ok" == true ]] || die "lock compile failed after 5 attempts"

log "Post-bump pin check"
"${CHECK_PIN[@]}" --pyproject "$PYPROJECT" || die "pin check failed after the bump"

# BACKEND_SHA names the backend source commit the image is built from. The pin
# and lock edits are this script's own and are committed after the smoke test,
# so they are excluded from the dirty test (D-25).
BACKEND_SHA=$(git -C "$BACKEND_ROOT" rev-parse --short HEAD)
if [[ -n "$(git -C "$BACKEND_ROOT" status --porcelain -- . ':!requirements-serve.txt' ':!requirements-serve.lock')" ]]; then
  BACKEND_SHA="$BACKEND_SHA-dirty"
fi
DEPLOYED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
export BACKEND_SHA DEPLOYED_AT

log "Deploying to Modal (backend $BACKEND_SHA)"
(cd "$BACKEND_ROOT" && modal deploy serve.py)

log "Smoke test: $BACKEND_URL/api/version"
"${CHECK_PIN[@]}" --deployed-url "$BACKEND_URL" --expect-sha "$BACKEND_SHA" --timeout 300 \
  || die "SMOKE FAILED: deployed /api/version does not report prospectai $NEW_VERSION / backend_sha $BACKEND_SHA — no commits made"

# ── Commits (D-25): only after a passing smoke test; never pushes ────────────
log "Creating local release commits"
if ! git -C "$REPO_ROOT" diff --quiet HEAD -- pyproject.toml README.md; then
  git -C "$REPO_ROOT" add pyproject.toml README.md
  git -C "$REPO_ROOT" commit -m "chore: release prospectai v$NEW_VERSION" \
    -m "Published to PyPI; deployed to Modal at $DEPLOYED_AT (backend $BACKEND_SHA)."
fi
if ! git -C "$BACKEND_ROOT" diff --quiet HEAD -- requirements-serve.txt requirements-serve.lock; then
  git -C "$BACKEND_ROOT" add requirements-serve.txt requirements-serve.lock
  git -C "$BACKEND_ROOT" commit -m "chore: pin prospectai==$NEW_VERSION" \
    -m "Deployed to Modal at $DEPLOYED_AT; /api/version smoke passed." \
    -m "backend_sha $BACKEND_SHA in /api/version is this commit's parent: the image was built from that source plus the pin and lock change recorded here."
fi
UPLOADED=0

echo ""
echo "Done. prospectai==$NEW_VERSION is live and verified. Local commits created on main in ProspectAI and prospectai-backend — publish main in both repos when ready; the next deploy.sh run refuses until origin/main has them (D-27)."
