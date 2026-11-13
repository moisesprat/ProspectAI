"""
Opt-in probe: do today's Yahoo sector and industry labels still match SECTOR_MEMBERSHIP?

Operator check, not part of the package (``scripts/`` is outside the wheel's packages) and not
run by the test suite against the network. It makes free, read-only Yahoo calls: for every
curated ticker of the selected sectors it reads today's sector and industry through
``utils.yfinance_cache.get_info`` and classifies them with ``utils.sector_membership.classify``
against ``utils.sector_universe.SECTOR_MEMBERSHIP`` (phase 4.1 D-01, assumption A9: a renamed
Yahoo label would make every non-curated pick of a sector ``not_in_sector``). Run it before
editing the map and before a release that ships it:

    python scripts/probe_sector_labels.py                      # all nine sectors
    python scripts/probe_sector_labels.py --sectors Finance,Semiconductors

Output: one summary line per sector (member, not_in_sector, unchecked and error counts), one
line per not_in_sector ticker with its labels (repr-escaped, cut to 40 characters), one line per
failed lookup (ticker and exception class name only, never the message).

Exit codes: 0 every selected sector has at least half of its labelled curated tickers as
members; 1 a sector with labelled curated tickers has fewer members than half of them (its label
was probably renamed); 2 unknown sector name (no lookup is made). A labelled ticker is one whose
lookup answered at least one non-empty sector or industry string. Known curated exceptions that
the map alone would drop (FIS under Finance; AMZN, TSLA and APP under Technology; SMCI under
Semiconductors) are listed as not_in_sector lines but fail nothing while the sector stays at or
above half; the curated short-circuit (D-03) keeps them in a real run.
"""

import argparse
import contextvars
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import yfinance_cache
from utils.sector_membership import FIELD_CHARS, classify
from utils.sector_universe import SECTOR_ALIASES, SECTOR_MEMBERSHIP, SECTOR_TICKERS, canonical_sector

UNKNOWN_SECTOR_MESSAGE = "unknown sector name; pass package names or the aliases: " + ", ".join(
    [*SECTOR_MEMBERSHIP, *SECTOR_ALIASES]
)


def _label(value: object) -> Optional[str]:
    """A label for display: a non-empty str cut to ``FIELD_CHARS``, else None."""
    if isinstance(value, str) and value.strip():
        return value.strip()[:FIELD_CHARS]
    return None


def _probe_one(canonical: str, ticker: str, fetch: Callable[[str], Any]) -> Dict[str, Any]:
    """Fetch and classify one curated ticker. Never raises."""
    try:
        info = fetch(ticker)
    except Exception as exc:
        return {"ticker": ticker, "error": type(exc).__name__}
    info = info if isinstance(info, dict) else {}
    sector, industry = _label(info.get("sector")), _label(info.get("industry"))
    return {
        "ticker": ticker,
        "sector": sector,
        "industry": industry,
        "verdict": classify(canonical, sector, industry),
    }


def probe(
    sectors: List[str],
    fetch: Optional[Callable[[str], Any]] = None,
    workers: int = 8,
) -> Dict[str, List[Dict[str, Any]]]:
    """Look up every curated ticker of ``sectors`` (package names); return results per sector.

    Each result is ``{"ticker", "sector", "industry", "verdict"}`` or ``{"ticker", "error"}``
    (exception class name). Starts a fresh yfinance run cache; each fetch runs in its own copy
    of the current context so the cache is shared with the worker threads.
    """
    yfinance_cache.clear()
    fetch = fetch or yfinance_cache.get_info
    jobs: List[Tuple[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="label-probe") as pool:
        for canonical in sectors:
            for ticker in SECTOR_TICKERS.get(canonical, []):
                future = pool.submit(contextvars.copy_context().run, _probe_one, canonical, ticker, fetch)
                jobs.append((canonical, future))
    results: Dict[str, List[Dict[str, Any]]] = {canonical: [] for canonical in sectors}
    for canonical, future in jobs:
        results[canonical].append(future.result())
    return results


def summarize(results: Dict[str, List[Dict[str, Any]]]) -> Tuple[List[str], int]:
    """Output lines and exit code (0 or 1) for ``probe`` results."""
    lines: List[str] = []
    failing: List[str] = []
    for canonical, entries in results.items():
        counts = {"member": 0, "not_in_sector": 0, "unchecked": 0}
        errors = 0
        labelled = 0
        for entry in entries:
            if "error" in entry:
                errors += 1
                continue
            counts[entry["verdict"]] += 1
            if entry["sector"] is not None or entry["industry"] is not None:
                labelled += 1
        below_half = labelled > 0 and 2 * counts["member"] < labelled
        if below_half:
            failing.append(canonical)
        lines.append(
            f"{canonical}: member {counts['member']}, not_in_sector {counts['not_in_sector']}, "
            f"unchecked {counts['unchecked']}, error {errors} "
            f"(labelled {labelled}){' FAIL: fewer than half are members' if below_half else ''}"
        )
        for entry in entries:
            if "error" in entry:
                lines.append(f"  {canonical}: lookup failed {entry['ticker']!r}; error {entry['error']}")
            elif entry["verdict"] == "not_in_sector":
                lines.append(
                    f"  {canonical}: not_in_sector {entry['ticker']!r}; "
                    f"yfinance sector {entry['sector']!r}, industry {entry['industry']!r}"
                )
    return lines, 1 if failing else 0


def main(argv: Optional[List[str]] = None, fetch: Optional[Callable[[str], Any]] = None) -> int:
    parser = argparse.ArgumentParser(description="Probe today's Yahoo labels against SECTOR_MEMBERSHIP.")
    parser.add_argument(
        "--sectors", default=",".join(SECTOR_MEMBERSHIP),
        help="comma list of package sector names or the aliases (default: all)",
    )
    args = parser.parse_args(argv)
    sectors: List[str] = []
    for name in (part.strip() for part in args.sectors.split(",") if part.strip()):
        canonical = canonical_sector(name)
        if canonical not in SECTOR_MEMBERSHIP:
            print(UNKNOWN_SECTOR_MESSAGE)
            return 2
        if canonical not in sectors:
            sectors.append(canonical)
    if not sectors:
        print(UNKNOWN_SECTOR_MESSAGE)
        return 2
    lines, code = summarize(probe(sectors, fetch=fetch))
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
