"""Tests for rejecting LLM-selected tickers before phases 2 and 3 (phase 4 CORR-06, operator decision narrowing D-03, D-04)."""
import pytest

from tests.test_llm_role_audit import (  # noqa: F401  (flow is a fixture)
    MARKET_PHASE, SERPER_TOOL, StubTool, _organic, flow, market_tools, mkt_entry,
    mkt_payload, narrative_result, run_market, run_technical, tech_entry, tech_narrative_entry,
    tech_payload, tech_tools, wire_tools,
)
from utils.market_records import build_market_corpus


def _drop_records(caplog, reason):
    return [r for r in caplog.records
            if r.levelname == "WARNING" and f"pick dropped ({reason})" in r.getMessage()]


@pytest.mark.parametrize("sector,etf,stock", [
    ("Financials", "XLF", "JPM"),
    ("Consumer Discretionary", "XLY", "AMZN"),
])
def test_excluded_etf_alias_sector_drops_the_etf_and_only_the_stock_reaches_technical(
        flow, caplog, sector, etf, stock):
    """The two SPA sector names: the benchmark ETF is dropped as excluded_etf before phase 2."""
    flow.state.sector = sector
    serper = _organic(f"{stock} beats estimates", f"{etf} and {stock} lead the sector", f"Sector rally, {etf} up")
    tools = {**market_tools(serper=serper), **tech_tools({"technical_analysis": [tech_entry(stock)]})}
    wire_tools(flow, tools, phase=MARKET_PHASE)

    with caplog.at_level("WARNING"):
        run_market(flow, narrative_result(mkt_payload(mkt_entry(etf), mkt_entry(stock))))

    assert [c.ticker for c in flow.state.market_output.candidate_stocks] == [stock]
    dropped = _drop_records(caplog, "excluded_etf")
    assert len(dropped) == 1
    assert dropped[0].getMessage() == f"market_analysis: pick dropped (excluded_etf): {etf!r}"

    run_technical(flow, narrative_result(tech_payload(tech_narrative_entry(stock))))
    tool = tools["calculate_technical_indicators"]
    assert len(tool.calls) == 1
    assert tool.calls[0]["tickers_json"] == f'["{stock}"]'


def test_alias_sector_universe_is_not_remapped():
    """Aliases only fix the ETF filter: the unavailable-path universe stays empty (WR-03 stays open)."""
    assert build_market_corpus(None, "Financials")["universe"] == []
    assert build_market_corpus(None, "Consumer Discretionary")["universe"] == []
