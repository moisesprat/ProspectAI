"""Single-definition pins for shared constants, lists and the validation-warnings build (phase 5, DEBT-03).

The duplicates the architecture review found were resolved earlier; these tests keep them
resolved. They scan tracked package code, excluding tests/, scripts/ and the root conftest.py.

Two copies are deliberate and outside this engine-only pin:

* The backend's ``AGENT_NAMES`` ("Market Analyst", ...) is a separate copy for the SSE UI
  (research Open Question 6). It is pinned from the backend side by
  ``test_backend_agent_names_match_engine`` in ``prospectai-backend/tests/test_sse_contract.py``
  (plan 05-04).
* ``validation_warnings`` stays published in both the report (``structured["validation_warnings"]``)
  and the top-level result, by contract (Open Question 2); both writes sit in ``run_analysis``.
"""

import ast
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_EXEMPT_DIRS = ("tests/", "scripts/")
_EXEMPT_FILES = frozenset({"conftest.py"})

# name -> the one module that may assign it at module level
_ONE_HOME = {
    "_QUALITY_SCORE": "utils/scoring_constants.py",
    "_GROWTH_SCORE": "utils/scoring_constants.py",
    "ATR_RATIO_HIGH": "utils/scoring_constants.py",
    "ATR_RATIO_LOW": "utils/scoring_constants.py",
    "_AGENT_NAMES": "prospect_ai_flow.py",
    "PHASES": "prospect_ai_flow.py",
    "PHASE_OUTPUT_MODELS": "utils/task_factory.py",
    "SECTOR_TICKERS": "utils/sector_universe.py",
    "SECTOR_ALIASES": "utils/sector_universe.py",
}


@pytest.fixture(scope="module", autouse=True)
def _require_git_checkout():
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"], cwd=REPO_ROOT, capture_output=True, text=True,
        )
    except FileNotFoundError:
        pytest.skip("git is not available")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        pytest.skip("repo root is not a git checkout")


def _package_trees():
    """(repo-relative path, parsed AST) for every tracked package .py file."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "*.py"], cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert listing.returncode == 0
    trees = []
    for rel in listing.stdout.split("\0"):
        if not rel or rel in _EXEMPT_FILES or rel.startswith(_EXEMPT_DIRS):
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        trees.append((rel, ast.parse(path.read_text(encoding="utf-8"), filename=rel)))
    return trees


def _target_names(node):
    """Names a module-level Assign or AnnAssign binds."""
    if isinstance(node, ast.Assign):
        return [t.id for t in node.targets if isinstance(t, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    return []


def test_shared_names_have_one_home():
    found = {name: [] for name in _ONE_HOME}
    for rel, tree in _package_trees():
        for node in tree.body:
            for name in _target_names(node):
                if name in found:
                    found[name].append(f"{rel}:{node.lineno}")
    problems = []
    for name, sites in found.items():
        home = _ONE_HOME[name]
        if len(sites) != 1 or not sites[0].startswith(f"{home}:"):
            problems.append(f"{name} must be assigned once, in {home}; found {sites}")
    assert not problems, "; ".join(problems)


def test_net_appears_once_in_technology():
    from utils.sector_universe import SECTOR_TICKERS

    assert SECTOR_TICKERS["Technology"].count("NET") == 1


def _writes_validation_warnings(target):
    """'name' for a bare validation_warnings target, 'subscript' for x["validation_warnings"], else None."""
    if isinstance(target, ast.Name) and target.id == "validation_warnings":
        return "name"
    if (
        isinstance(target, ast.Subscript)
        and isinstance(target.slice, ast.Constant)
        and target.slice.value == "validation_warnings"
    ):
        return "subscript"
    return None


class _WarningsWrites(ast.NodeVisitor):
    """Collects every write to validation_warnings with the innermost enclosing function."""

    def __init__(self, rel):
        self.rel = rel
        self.scope = ["<module>"]
        self.plain, self.other, self.subscript = [], [], []

    def _scoped(self, node):
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _scoped

    def _write(self, node, targets):
        for target in targets:
            kind = _writes_validation_warnings(target)
            site = (f"{self.rel}:{node.lineno}", self.scope[-1])
            if kind == "name":
                (self.plain if isinstance(node, ast.Assign) else self.other).append(site)
            elif kind == "subscript":
                self.subscript.append(site)

    def visit_Assign(self, node):
        self._write(node, node.targets)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self._write(node, [node.target])
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._write(node, [node.target])
        self.generic_visit(node)


def test_validation_warnings_built_in_one_place():
    plain, other, subscript = [], [], []
    for rel, tree in _package_trees():
        visitor = _WarningsWrites(rel)
        visitor.visit(tree)
        plain += visitor.plain
        other += visitor.other
        subscript += visitor.subscript

    everywhere = plain + other + subscript
    stray = [s for s in everywhere if not (s[0].startswith("prospect_ai_flow.py:") and s[1] == "run_analysis")]
    assert not stray, f"validation_warnings written outside ProspectAIFlow.run_analysis: {stray}"
    assert len(plain) == 1, f"validation_warnings must be built by exactly one plain assignment: {plain}"
    assert len(subscript) == 1, f'structured["validation_warnings"] must be written once: {subscript}'
