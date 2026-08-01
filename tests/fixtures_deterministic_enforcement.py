"""
Regression fixtures for change deterministic-enforcement-v1-9-1.

Each fixture reproduces a concrete production failure so the corresponding
enforcement mechanism (PortfolioBoundsValidator, ActionPolicyGate, the Flow's
allocator re-invocation) has a fixed, real-world regression test to run against.
"""

# ── Fixture 1.1 ──────────────────────────────────────────────────────────────
# Final Strategist changed WAIT-FOR-ENTRY (draft) -> LONG-BUY (final) but never
# called allocate_portfolio: allocation_pct/trade_setup are hand-written by the
# LLM, and the entry zone is fabricated (does not match the Technical Analyst's
# entry_zone_low/high for this ticker).
DRAFT_OUTPUT_SKIPPED_ALLOCATOR = {
    "sector": "Energy",
    "risk_profile": "conservative",
    "positions": [
        {
            "ticker": "XOM",
            "action": "WAIT-FOR-ENTRY",
            "composite_score": 68.0,
            "allocation_pct": 12.0,
            "current_price": 118.0,
            "trade_setup": {
                "direction": "LONG-BUY",
                "entry_zone_low": 114.0,
                "entry_zone_high": 116.5,
                "stop_loss": 110.58,
                "take_profit": 122.55,
            },
            "scaled_entry_setups": None,
            "rationale": "Awaiting pullback to entry zone before committing capital.",
            "monitoring_triggers": ["Price retraces to 116.50"],
            "review_frequency": "WEEKLY",
        },
    ],
    "deployed_pct": 0.0,
    "reserved_pct": 12.0,
    "cash_reserve_pct": 88.0,
    "overall_strategy": "Conservative Energy allocation, awaiting XOM pullback.",
    "risk_level": "Medium",
}

FINAL_OUTPUT_SKIPPED_ALLOCATOR = {
    "sector": "Energy",
    "risk_profile": "conservative",
    "positions": [
        {
            "ticker": "XOM",
            "action": "LONG-BUY",
            "composite_score": 68.0,
            # Hand-written by the LLM -- never produced by allocate_portfolio.
            "allocation_pct": 22.0,
            "current_price": 118.0,
            "trade_setup": {
                "direction": "LONG-BUY",
                # Fabricated: does not match the Technical Analyst's entry zone
                # (114.0-116.5) or any stop_multiplier/rr_ratio formula.
                "entry_zone_low": 117.0,
                "entry_zone_high": 119.0,
                "stop_loss": 112.0,
                "take_profit": 130.0,
            },
            "scaled_entry_setups": None,
            "rationale": "Critic confirmed bullish signal; upgrading to LONG-BUY now.",
            "monitoring_triggers": ["RSI crosses above 75"],
            "review_frequency": "WEEKLY",
        },
    ],
    "deployed_pct": 22.0,
    "reserved_pct": 0.0,
    "cash_reserve_pct": 78.0,
    "overall_strategy": "Upgraded XOM to LONG-BUY per Critic review.",
    "risk_level": "Medium",
}

# Technical Analyst's real entry zone for XOM, as it should be used by the
# Flow's own allocate_portfolio re-invocation (not the fabricated one above).
XOM_TECHNICAL_CONTEXT = {
    "ticker": "XOM",
    "entry_zone_low": 114.0,
    "entry_zone_high": 116.5,
    "current_price": 118.0,
}


# ── Fixture 1.2 ──────────────────────────────────────────────────────────────
# Published Energy-sector output: a 25% position under a 15% conservative cap,
# stops at 5.0-5.4% (vs the 3% conservative cap), round-number setups, and an
# unattributed reserved_pct that contradicts the prose ("no capital earmarked"
# while reserved_pct=10.0).
PUBLISHED_ENERGY_OUTPUT_BOUNDS_VIOLATION = {
    "sector": "Energy",
    "risk_profile": "conservative",
    "positions": [
        {
            "ticker": "CVX",
            "action": "LONG-BUY",
            "composite_score": 79.0,
            "allocation_pct": 25.0,  # exceeds conservative 15% cap
            "current_price": 160.0,
            "trade_setup": {
                "direction": "LONG-BUY",
                "entry_zone_low": 155.0,
                "entry_zone_high": 158.0,
                "stop_loss": 147.0,   # (155-147)/155 = 5.16% > 3% conservative cap
                "take_profit": 180.0,  # round-number, not formula-derived
            },
            "scaled_entry_setups": None,
            "rationale": "High-conviction CVX position given refining margins.",
            "monitoring_triggers": ["Price closes below 150"],
            "review_frequency": "WEEKLY",
        },
        {
            "ticker": "SLB",
            "action": "WAIT-FOR-ENTRY",
            "composite_score": 61.0,
            "allocation_pct": 0.0,
            "current_price": 45.0,
            "trade_setup": {
                "direction": "LONG-BUY",
                "entry_zone_low": 42.0,
                "entry_zone_high": 43.5,
                "stop_loss": 39.9,
                "take_profit": 52.35,
            },
            "scaled_entry_setups": None,
            # Prose contradicts the aggregate reserved_pct below: says nothing
            # was earmarked, yet reserved_pct=10.0 at the portfolio level.
            "rationale": "No capital earmarked for SLB at this time.",
            "monitoring_triggers": ["Price retraces to 43.50"],
            "review_frequency": "WEEKLY",
        },
    ],
    "deployed_pct": 25.0,
    "reserved_pct": 10.0,  # not attributed to any specific WAIT-FOR-ENTRY entry
    "cash_reserve_pct": 65.0,
    "overall_strategy": "Concentrated CVX position with SLB on watch.",
    "risk_level": "High",
}


# ── Fixture 1.3 ──────────────────────────────────────────────────────────────
# v1.9.0 TRENDING-regime edge case: SMA20 sits essentially on top of
# current_price and ATR is ~0, which (before the minimum-width clamp in
# utils/technical_interpretation_tool.py) produced a zero-width entry zone.
ZERO_WIDTH_TRENDING_RAW_INDICATORS = {
    "ticker": "NVDA",
    "current_price": 200.00,
    "sma_20": 199.98,
    "sma_50": 190.0,
    "sma_200": 150.0,
    "adx": 30.0,       # strong_uptrend requires adx > 25
    "atr": 0.0,        # degenerate ATR -> no width contribution
    "rsi": 62.0,
    "macd_signal": "Bullish",
    "stochastic_status": "Neutral",
}


# ── Fixture 1.4 ──────────────────────────────────────────────────────────────
# Critic revision_directives entry that contradicts the action-policy table:
# ordering WAIT-FOR-ENTRY for a position whose entry_zone_status=CURRENT_ENTRY
# (where LONG-BUY is the mandatory default for both profiles).
CRITIC_OUTPUT_POLICY_VIOLATING_DIRECTIVE = {
    "sector": "Technology",
    "risk_profile": "conservative",
    "draft_assessment": "Draft is largely sound but AAPL entry timing is debatable given current price action.",
    "per_ticker_critiques": [
        {
            "ticker": "AAPL",
            "severity": "MINOR",
            "issue_type": "ENTRY_TIMING",
            "finding": "AAPL is trading at the top of its recent range with elevated short-term risk.",
            "instruction": "Consider waiting for a better entry price before committing full capital.",
        },
    ],
    "portfolio_level_issues": [],
    "revision_directives": [
        "AAPL: change action to WAIT-FOR-ENTRY -- wait for a better price before committing capital.",
    ],
    "approved_positions": ["MSFT"],
}

AAPL_POSITION_CONTEXT = {
    "ticker": "AAPL",
    "entry_zone_status": "CURRENT_ENTRY",
    "risk_profile": "conservative",
}


# ── Fixture: critic-evidence-grounded-review regression ─────────────────────
# Reproduces, verbatim, the Critic's inverted-CURRENT_ENTRY-rule finding from
# logs/deterministic-enforcement-v1-9-1/run4_technology_aggressive.log: a
# correct draft LONG-BUY at entry_zone_status=CURRENT_ENTRY gets ordered
# downgraded to WAIT-FOR-ENTRY through BOTH revision_directives AND
# per_ticker_critiques -- the ActionPolicyGate must drop it from both
# channels, not just one.
CRITIC_OUTPUT_INVERTED_CURRENT_ENTRY_BUG = {
    "sector": "Technology",
    "risk_profile": "aggressive",
    "draft_assessment": "Multiple positions trigger LONG-BUY while priced at entry_zone_status=CURRENT_ENTRY.",
    "per_ticker_critiques": [
        {
            "ticker": "NVDA",
            "severity": "CRITICAL",
            "issue_type": "PRICE_IN_ZONE_WAIT",
            "finding": (
                "NVDA entry_zone_status=CURRENT_ENTRY with current_price=200.75 within "
                "entry_zone (199.23-202.28). Draft action is LONG-BUY, but aggressive "
                "profile requires WAIT-FOR-ENTRY when price is already in the entry "
                "zone at CURRENT_ENTRY status."
            ),
            "instruction": (
                "NVDA: Change action from LONG-BUY to WAIT-FOR-ENTRY because "
                "entry_zone_status=CURRENT_ENTRY and current_price=200.75 is already "
                "within the entry zone (199.23-202.28). Aggressive profile requires "
                "pullback confirmation before entry; monitor for price to exit zone "
                "and re-enter on pullback."
            ),
        },
    ],
    "portfolio_level_issues": [
        "Entry zone status violation: NVDA has entry_zone_status=CURRENT_ENTRY but "
        "action=LONG-BUY. Aggressive profile requires WAIT-FOR-ENTRY when price is "
        "at CURRENT_ENTRY.",
    ],
    "revision_directives": [
        "NVDA: Change action from LONG-BUY to WAIT-FOR-ENTRY because "
        "entry_zone_status=CURRENT_ENTRY and current_price=200.75 is within the "
        "entry zone (199.23-202.28). Aggressive profile requires pullback "
        "confirmation; monitor for exit and re-entry.",
    ],
    "approved_positions": [],
}

NVDA_CURRENT_ENTRY_CONTEXT = {
    "ticker": "NVDA",
    "entry_zone_status": "CURRENT_ENTRY",
    "risk_profile": "aggressive",
}
