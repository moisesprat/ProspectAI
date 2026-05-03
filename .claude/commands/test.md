Run the ProspectAI test suite. Arguments passed by the user: $ARGUMENTS

---

## Step 1 — Parse arguments

From `$ARGUMENTS`:
- If a token matches `tests/test_*.py` or `test_*.py`, that is the **target file** — run only that file.
- If `-k <pattern>` is present, pass `-k <pattern>` to pytest to filter by test name.
- If `--coverage` or `-c` is present, add coverage reporting.
- If no arguments are given, run the full suite.

Print: `==> ProspectAI test suite`
Print the resolved command before running it, e.g. `Running: pytest tests/ -v --tb=short --durations=5`

---

## Step 2 — Run tests

Run pytest with these flags:
- `-v` — verbose, one line per test
- `--tb=short` — compact tracebacks (full stack on failure is noisy)
- `--durations=5` — show the 5 slowest tests at the end
- If `--coverage` was requested: add `--cov=. --cov-report=term-missing --cov-omit=tests/*,.venv/*`
- If a target file was given: replace `tests/` with that path
- If `-k <pattern>` was given: append `-k <pattern>`

Capture the full output.

---

## Step 3 — Print a structured summary

After the run completes, print a summary block:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RESULTS
  Passed : <n>
  Failed : <n>
  Skipped: <n>
  Time   : <elapsed>s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If **all tests passed**: print `All tests passed.`

If **any tests failed**:
- Print `The following tests failed:`
- List each failing test name (from the `FAILED` lines in pytest output) as a bullet
- Print `Run /test <test_file> to re-run a single file, or /test -k <name> to filter by name.`

If **slowest tests** are shown by `--durations=5`, include them:
```
  Slowest tests:
  <duration>s  <test_name>
  ...
```

---

## Step 4 — Coverage (if requested)

If `--coverage` was requested, after the summary print the coverage table from pytest-cov output as-is, then print the overall coverage percentage on its own line:
```
Coverage: <pct>%
```

If `pytest-cov` is not installed, print: `Coverage reporting requires pytest-cov. Install with: pip install pytest-cov`
