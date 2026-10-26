#!/usr/bin/env bash
# =============================================================================
# ProspectAI — Lock compile
#
# Compiles pyproject.toml (+ dev and legacy extras) and constraints.txt into the
# fully pinned requirements.txt. Developers and CI run this same command; CI
# re-runs it and fails on `git diff` if requirements.txt was stale or hand-edited.
#
# Usage:
#   bash scripts/lock.sh                      # regenerate requirements.txt
#   bash scripts/lock.sh --upgrade-package X  # extra uv args pass through
#
# Requirements: uv (https://docs.astral.sh/uv/)
# =============================================================================
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

uv pip compile pyproject.toml --extra dev --extra legacy --universal --python-version 3.11 -c constraints.txt --custom-compile-command "bash scripts/lock.sh" -o requirements.txt "$@"
