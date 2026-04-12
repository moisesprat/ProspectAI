#!/usr/bin/env bash
# =============================================================================
# ProspectAI — Release & Deploy Script
#
# Steps:
#   1. Bumps patch version in pyproject.toml and prospectai-backend/serve.py
#   2. Cleans dist/
#   3. Builds wheel + sdist
#   4. Uploads to PyPI via twine
#   5. Deploys new image to Modal
#
# Usage:
#   ./scripts/deploy.sh              # auto-bump patch (e.g. 1.5.7 → 1.5.8)
#   ./scripts/deploy.sh 1.6.0        # explicit version
#   ./scripts/deploy.sh --skip-pypi  # redeploy Modal only (version already on PyPI)
#
# Requirements:
#   pip install build twine
#   modal token set  (already authenticated)
#   PyPI token in ~/.pypirc or TWINE_PASSWORD env var
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_SERVE="$REPO_ROOT/../prospectai-backend/serve.py"
PYPROJECT="$REPO_ROOT/pyproject.toml"
DIST_DIR="$REPO_ROOT/dist"

# Resolve python3 / pip3
PYTHON=$(command -v python3 || command -v python)
PIP=$(command -v pip3 || command -v pip)

SKIP_PYPI=false
EXPLICIT_VERSION=""

for arg in "$@"; do
  if [[ "$arg" == "--skip-pypi" ]]; then
    SKIP_PYPI=true
  elif [[ "$arg" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    EXPLICIT_VERSION="$arg"
  fi
done

# ── 1. Resolve version ────────────────────────────────────────────────────────
# Use python3 to extract version — avoids macOS sed/grep parsing edge cases
CURRENT_VERSION=$("$PYTHON" -c "
import re, sys
content = open('$PYPROJECT').read()
m = re.search(r'^version\s*=\s*\"([^\"]+)\"', content, re.MULTILINE)
print(m.group(1) if m else sys.exit('ERROR: version not found in pyproject.toml'))
")

if [[ -n "$EXPLICIT_VERSION" ]]; then
  NEW_VERSION="$EXPLICIT_VERSION"
else
  # Auto-bump patch using python arithmetic (avoids IFS/read issues on macOS)
  NEW_VERSION=$("$PYTHON" -c "
v = '$CURRENT_VERSION'.split('.')
v[2] = str(int(v[2]) + 1)
print('.'.join(v))
")
fi

echo "==> Version: $CURRENT_VERSION → $NEW_VERSION"

# ── 2. Update pyproject.toml ──────────────────────────────────────────────────
sed -i '' "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" "$PYPROJECT"
echo "    pyproject.toml updated"

# ── 3. Update serve.py (pip_install line) ─────────────────────────────────────
if [[ -f "$BACKEND_SERVE" ]]; then
  sed -i '' "s/prospectai==$CURRENT_VERSION/prospectai==$NEW_VERSION/" "$BACKEND_SERVE"
  echo "    prospectai-backend/serve.py updated"
else
  echo "    WARNING: $BACKEND_SERVE not found — skipping serve.py update"
fi

# ── 4. Clean dist/ ────────────────────────────────────────────────────────────
echo "==> Cleaning dist/"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# ── 5. Build ──────────────────────────────────────────────────────────────────
echo "==> Building wheel + sdist"
cd "$REPO_ROOT"
"$PYTHON" -m build

# ── 6. Upload to PyPI ─────────────────────────────────────────────────────────
if [[ "$SKIP_PYPI" == false ]]; then
  echo "==> Uploading to PyPI"
  "$PYTHON" -m twine upload dist/*
  echo "    Uploaded prospectai==$NEW_VERSION to PyPI"

  echo "==> Waiting 15s for PyPI to propagate..."
  sleep 15
else
  echo "==> Skipping PyPI upload (--skip-pypi)"
fi

# ── 7. Deploy to Modal ────────────────────────────────────────────────────────
echo "==> Deploying to Modal"
cd "$REPO_ROOT/../prospectai-backend"
modal deploy serve.py
echo "    Modal deploy complete"

echo ""
echo "Done. prospectai==$NEW_VERSION is live."
