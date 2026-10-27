Run the ProspectAI release pipeline. Arguments passed by the user: $ARGUMENTS

`scripts/deploy.sh` is the single deploy path. This command only runs it.

1. From the ProspectAI repo root, recommend `./scripts/deploy.sh --preflight-only` first. It runs every gate and changes nothing.
2. Run `./scripts/deploy.sh $ARGUMENTS` (arguments: optional `X.Y.Z`, `--skip-pypi`, `--preflight-only`).
3. Report the script output verbatim.

Prerequisites: `uv`; the `modal` CLI authenticated via `modal token set`; a PyPI token in `~/.pypirc` (or `TWINE_PASSWORD`); and both ProspectAI and prospectai-backend on `main`, identical to `origin/main`, with their PRs merged. The script refuses otherwise.

Rules:
- Never edit versions, pins, locks or `serve.py` by hand. A raw `modal deploy` bypasses every check.
- If the script fails after the PyPI upload, follow the recovery line it prints (`./scripts/deploy.sh --skip-pypi`).
- The script creates local commits in both repos and never pushes. Pushing is the user's decision.
