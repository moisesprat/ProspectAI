#!/usr/bin/env bash
# =============================================================================
# ProspectAI — Release & Deploy Script
#
# Steps:
#   1. Bumps patch version in pyproject.toml and prospectai-backend/serve.py
#   2. Updates README.md version badge and release notes (last 5 entries, auto-generated from git log)
#   3. Cleans dist/
#   4. Builds wheel + sdist
#   5. Uploads to PyPI via twine
#   6. Deploys new image to Modal
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
README="$REPO_ROOT/README.md"
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

# ── 3b. Update README.md (version badge + release notes) ─────────────────────
if [[ -f "$README" ]]; then
  "$PYTHON" - "$README" "$NEW_VERSION" "$CURRENT_VERSION" <<'PYEOF'
import re, subprocess, sys

readme_path  = sys.argv[1]
new_version  = sys.argv[2]
prev_version = sys.argv[3]

# ── Collect commits made since the previous version bump ─────────────────────
log_lines = subprocess.run(
    ["git", "log", "--oneline"],
    capture_output=True, text=True, check=True
).stdout.strip().splitlines()

# Find the line that bumped pyproject.toml to prev_version
bump_idx = next(
    (i for i, l in enumerate(log_lines) if prev_version in l),
    None
)
# Everything before that index = new work going into new_version
new_commits = log_lines[:bump_idx] if bump_idx else log_lines[:10]

# Filter out pure meta-commits; strip conventional-commit prefixes
SKIP = re.compile(r'bump version|chore:|Co-Authored|^Merge ', re.IGNORECASE)
PREFIX = re.compile(r'^(feat|fix|refactor|chore|docs|test|style|perf|build):\s*', re.IGNORECASE)
bullets = []
title_candidate = None
for line in new_commits:
    msg = line.split(" ", 1)[1] if " " in line else line
    if SKIP.search(msg):
        continue
    clean = PREFIX.sub("", msg).strip()
    if title_candidate is None:
        title_candidate = clean
    bullets.append(f"- {clean}")

if not bullets:
    bullets = ["- Maintenance and stability improvements"]
title = (title_candidate or "Maintenance release")[:60]
new_entry = f"### v{new_version} — {title}\n" + "\n".join(bullets)

# ── Rewrite README ────────────────────────────────────────────────────────────
content = open(readme_path).read()

# Update version badge
content = content.replace(
    f"**Current release: v{prev_version}**",
    f"**Current release: v{new_version}**",
)

# Find the Release Notes section (between "## Release Notes\n\n" and the next "## ")
rn = re.search(r'(## Release Notes\n\n)(.*?)(\n## )', content, re.DOTALL)
if rn:
    body = rn.group(2).rstrip()
    existing = [e.strip() for e in re.split(r'(?=### v)', body) if e.strip()]
    # New entry + 4 existing = 5 total
    kept = "\n\n".join([new_entry] + existing[:4])
    content = (
        content[:rn.start()]
        + rn.group(1) + kept + "\n"
        + rn.group(3)
        + content[rn.end():]
    )
else:
    print("WARNING: '## Release Notes' section not found — skipping notes update",
          file=sys.stderr)

open(readme_path, "w").write(content)
print(f"    README.md updated — v{new_version} release notes prepended, last 5 kept")
PYEOF
else
  echo "    WARNING: $README not found — skipping README update"
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
