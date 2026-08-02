"""Tests for ActionPolicyGate (change deterministic-enforcement-v1-9-1)."""

import pytest

from utils.action_policy_gate import (
    ACTION_POLICY_TABLE,
    filter_critiques,
    filter_directives,
    parse_directive,
    resolve_allowed_actions,
)


# ── Table resolution ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("entry_zone_status,risk_profile", list(ACTION_POLICY_TABLE.keys()))
def test_table_resolves_a_nonempty_action_set(entry_zone_status, risk_profile):
    allowed = resolve_allowed_actions(entry_zone_status, risk_profile)
    assert allowed
    assert allowed <= {"LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"}


def test_current_entry_excludes_wait_for_entry_for_both_profiles():
    assert "WAIT-FOR-ENTRY" not in resolve_allowed_actions("CURRENT_ENTRY", "conservative")
    assert "WAIT-FOR-ENTRY" not in resolve_allowed_actions("CURRENT_ENTRY", "aggressive")
    assert "LONG-BUY" in resolve_allowed_actions("CURRENT_ENTRY", "conservative")
    assert "LONG-BUY" in resolve_allowed_actions("CURRENT_ENTRY", "aggressive")


def test_below_zone_permits_long_buy_but_excludes_wait_for_entry_for_both_profiles():
    # BELOW_ZONE excluding LONG-BUY was a risk-policy stance, not a logical
    # necessity (change reasoning-depth-action-selection) -- opened up to the
    # Strategist's own judgment. WAIT-FOR-ENTRY stays excluded: its semantics
    # ("wait for price to fall into the zone from above") don't apply below
    # the zone.
    for profile in ("conservative", "aggressive"):
        allowed = resolve_allowed_actions("BELOW_ZONE", profile)
        assert "LONG-BUY" in allowed
        assert "WAIT-FOR-ENTRY" not in allowed


def test_pullback_entry_permits_long_buy_under_aggressive():
    assert "LONG-BUY" in resolve_allowed_actions("PULLBACK_ENTRY", "aggressive")


def test_unknown_entry_zone_status_resolves_permissively():
    allowed = resolve_allowed_actions(None, "conservative")
    assert allowed == {"LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"}


# ── Directive parsing ────────────────────────────────────────────────────────

def test_parse_directive_extracts_ticker_and_action():
    assert parse_directive("AAPL: change action to WAIT-FOR-ENTRY -- price too high.") == ("AAPL", "WAIT-FOR-ENTRY")


def test_parse_directive_returns_none_for_non_action_directive():
    assert parse_directive("Tighten the rationale wording across all positions for clarity.") is None


# ── filter_directives ────────────────────────────────────────────────────────

def test_directive_ordering_wait_for_entry_at_current_entry_is_dropped():
    directives = ["AAPL: change action to WAIT-FOR-ENTRY -- wait for a better price."]
    context = {"AAPL": {"entry_zone_status": "CURRENT_ENTRY", "risk_profile": "conservative"}}

    kept, rejected = filter_directives(directives, context)

    assert kept == []
    assert len(rejected) == 1
    assert rejected[0].ticker == "AAPL"
    assert rejected[0].rejected_action == "WAIT-FOR-ENTRY"


def test_directive_ordering_a_permitted_action_passes_through():
    directives = ["NVDA: change action to LONG-BUY -- bullish momentum confirmed."]
    context = {"NVDA": {"entry_zone_status": "PULLBACK_ENTRY", "risk_profile": "aggressive"}}

    kept, rejected = filter_directives(directives, context)

    assert kept == directives
    assert rejected == []


def test_non_action_directive_passes_through_unfiltered():
    directives = ["Tighten the rationale wording across all positions for clarity."]
    kept, rejected = filter_directives(directives, {})

    assert kept == directives
    assert rejected == []


def test_directive_for_unknown_ticker_passes_through():
    directives = ["ZZZZ: change action to WAIT-FOR-ENTRY."]
    kept, rejected = filter_directives(directives, {})

    assert kept == directives
    assert rejected == []


# ── filter_critiques ─────────────────────────────────────────────────────────
# Regression fixture: the exact NVDA finding/instruction reproduced live in
# logs/deterministic-enforcement-v1-9-1/run4_technology_aggressive.log, where
# the Critic inverted the CURRENT_ENTRY rule and ordered a correct LONG-BUY
# downgraded to WAIT-FOR-ENTRY.
_NVDA_INVERTED_CRITIQUE = {
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
}
_NVDA_CONTEXT = {"NVDA": {"entry_zone_status": "CURRENT_ENTRY", "risk_profile": "aggressive"}}


def test_critique_ordering_wait_for_entry_at_current_entry_is_dropped():
    kept, rejected = filter_critiques([_NVDA_INVERTED_CRITIQUE], _NVDA_CONTEXT)

    assert kept == []
    assert len(rejected) == 1
    assert rejected[0].ticker == "NVDA"
    assert rejected[0].rejected_action == "WAIT-FOR-ENTRY"


def test_critique_ordering_a_permitted_action_passes_through():
    critique = {
        "ticker": "NVDA",
        "severity": "MAJOR",
        "issue_type": "ACTION_PROFILE_MISMATCH",
        "finding": "NVDA entry_zone_status=PULLBACK_ENTRY with bullish momentum confirmed.",
        "instruction": "NVDA: change action to LONG-BUY -- bullish momentum confirmed.",
    }
    context = {"NVDA": {"entry_zone_status": "PULLBACK_ENTRY", "risk_profile": "aggressive"}}

    kept, rejected = filter_critiques([critique], context)

    assert kept == [critique]
    assert rejected == []


def test_non_action_critique_passes_through_unfiltered():
    critique = {
        "ticker": "AAPL",
        "severity": "MINOR",
        "issue_type": "VAGUE_RATIONALE",
        "finding": "Rationale does not cite a specific number for the valuation claim.",
        "instruction": "AAPL: cite the specific P/E value supporting the valuation claim.",
    }
    kept, rejected = filter_critiques([critique], {})

    assert kept == [critique]
    assert rejected == []


def test_critique_for_unknown_ticker_passes_through():
    critique = {
        "ticker": "ZZZZ",
        "severity": "CRITICAL",
        "issue_type": "PRICE_IN_ZONE_WAIT",
        "finding": "ZZZZ finding text long enough to satisfy schema constraints here.",
        "instruction": "ZZZZ: change action to WAIT-FOR-ENTRY.",
    }
    kept, rejected = filter_critiques([critique], {})

    assert kept == [critique]
    assert rejected == []


def test_filter_critiques_preserves_order_of_kept_items():
    approved = {
        "ticker": "MSFT", "severity": "MINOR", "issue_type": "VAGUE_RATIONALE",
        "finding": "Rationale lacks a specific RSI value to support the claim made.",
        "instruction": "MSFT: cite the specific RSI value.",
    }
    kept, _ = filter_critiques([_NVDA_INVERTED_CRITIQUE, approved], {**_NVDA_CONTEXT})

    assert kept == [approved]
