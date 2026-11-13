"""Offline tests for scripts/probe_sector_labels.py (phase 4.1, D-01, assumption A9)."""
import importlib.util
from pathlib import Path

import pytest

from utils.sector_universe import SECTOR_MEMBERSHIP, SECTOR_TICKERS

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "probe_sector_labels.py"


@pytest.fixture
def probe_mod():
    spec = importlib.util.spec_from_file_location("probe_sector_labels", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _member_labels(canonical):
    sectors, industries = SECTOR_MEMBERSHIP[canonical]
    if sectors:
        return {"sector": sorted(sectors)[0], "industry": "Whatever"}
    return {"sector": "Technology", "industry": sorted(industries)[0]}


def _fetch_members(table=None):
    """fetch answering each curated ticker with its sector's accepted labels; ``table`` overrides."""
    owner = {t: s for s, tickers in SECTOR_TICKERS.items() for t in tickers}

    def fetch(ticker):
        if table and ticker in table:
            answer = table[ticker]
            if isinstance(answer, BaseException):
                raise answer
            return answer
        return _member_labels(owner[ticker])

    return fetch


def test_probe_passes_when_curated_labels_match(probe_mod, capsys):
    code = probe_mod.main(["--sectors", "Finance,Semiconductors"], fetch=_fetch_members())
    out = capsys.readouterr().out
    assert code == 0
    assert out.count("member ") == 2
    assert out.splitlines()[0].startswith("Finance: member ")
    assert any(line.startswith("Semiconductors: member ") for line in out.splitlines())


def test_probe_fails_when_a_sector_label_is_renamed(probe_mod, capsys):
    renamed = {t: {"sector": "Financials", "industry": "Banks"} for t in SECTOR_TICKERS["Finance"]}
    code = probe_mod.main(["--sectors", "Financials,Energy"], fetch=_fetch_members(renamed))
    out = capsys.readouterr().out
    assert code == 1
    assert "Finance: member 0" in out and "FAIL" in out
    assert "Energy: member" in out and "Energy: member 0" not in out


def test_probe_reports_lookup_errors_by_class_only(probe_mod, capsys):
    assert "FIS" in SECTOR_TICKERS["Finance"]
    first = SECTOR_TICKERS["Finance"][0]
    table = {
        first: ConnectionError("token=SECRET-MARKER"),
        "FIS": {"sector": "Technology", "industry": "Information Technology Services"},
    }
    code = probe_mod.main(["--sectors", "Finance"], fetch=_fetch_members(table))
    out = capsys.readouterr().out
    assert code == 0
    assert f"{first!r}" in out and "ConnectionError" in out
    assert "SECRET-MARKER" not in out
    assert "not_in_sector 'FIS'" in out and "Information Technology Services" in out


def test_probe_rejects_an_unknown_sector(probe_mod, capsys):
    def fetch(ticker):
        raise AssertionError("no lookup may run")

    code = probe_mod.main(["--sectors", "Finance,Basket Weaving"], fetch=fetch)
    out = capsys.readouterr().out
    assert code == 2
    assert out.strip() == probe_mod.UNKNOWN_SECTOR_MESSAGE
    assert "Basket Weaving" not in out
