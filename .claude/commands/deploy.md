You are running the ProspectAI release and deploy pipeline. Follow every step in order. Arguments passed by the user: $ARGUMENTS

---

## Step 1 — Parse arguments

From `$ARGUMENTS`:
- If a token matches `^\d+\.\d+\.\d+$`, that is the **explicit version** to use.
- If `--skip-pypi` is present, set **skip_pypi = true**.
- If no explicit version is provided, you will auto-bump the patch (step 3).

---

## Step 2 — Read current version

Read `pyproject.toml`. Extract the value from the line matching:
```
version = "<current_version>"
```

---

## Step 3 — Resolve new version

- If an explicit version was provided, use it.
- Otherwise, split the current version on `.`, increment the third segment by 1, and rejoin. Example: `1.5.11` → `1.5.12`.

Print: `==> Version: <current> → <new>`

---

## Step 4 — Update `pyproject.toml`

Replace the exact line:
```
version = "<current_version>"
```
with:
```
version = "<new_version>"
```

---

## Step 5 — Update `../prospectai-backend/serve.py`

Check if the file `../prospectai-backend/serve.py` exists relative to the repo root.
- If it exists: replace all occurrences of `prospectai==<current_version>` with `prospectai==<new_version>`.
- If it does not exist: print `WARNING: ../prospectai-backend/serve.py not found — skipping` and continue.

---

## Step 6 — Update `README.md`

### 6a — Version badge
Replace:
```
**Current release: v<current_version>**
```
with:
```
**Current release: v<new_version>**
```

### 6b — Release notes entry

Run `git log --oneline` to get the full commit history.

Find the index of the first line that contains `<current_version>` — that is the previous version-bump commit. All lines **before** that index are the new commits going into `<new_version>`.

Filter those commits:
- Skip any line whose message matches (case-insensitive): `bump version`, `chore:`, `Co-Authored`, or starts with `Merge `.
- Strip conventional-commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`, `style:`, `perf:`, `build:` (with optional space).

From the filtered list:
- The **first** cleaned message becomes the release title (truncated to 60 chars).
- All cleaned messages become bullet points: `- <message>`.
- If no commits survive filtering, use bullet `- Maintenance and stability improvements` and title `Maintenance release`.

Build the new entry:
```
### v<new_version> — <title>
- <bullet 1>
- <bullet 2>
...
```

In `README.md`, find the `## Release Notes` section (between `## Release Notes\n\n` and the next `## `). Prepend the new entry and keep at most **4** existing entries (5 total). Rewrite that section.

---

## Step 7 — Clean `dist/`

Delete the `dist/` directory and recreate it empty.

---

## Step 8 — Build

From the repo root, run:
```
python -m build
```

Wait for it to complete successfully before continuing.

---

## Step 9 — Upload to PyPI

**Skip this step if skip_pypi = true** (print `==> Skipping PyPI upload (--skip-pypi)` and go to step 10).

Run:
```
python -m twine upload dist/*
```

After success, print `Uploaded prospectai==<new_version> to PyPI`.

Then wait **15 seconds** for PyPI to propagate before continuing.

---

## Step 10 — Deploy to Modal

Change directory to `../prospectai-backend` (relative to repo root) and run:
```
modal deploy serve.py
```

Wait for it to complete.

---

## Step 11 — Done

Print:
```
Done. prospectai==<new_version> is live.
```
