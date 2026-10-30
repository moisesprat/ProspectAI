"""Tests for ActionPolicyGate (change deterministic-enforcement-v1-9-1)."""

import pytest

from utils.action_policy_gate import (
    ACTION_POLICY_TABLE,
    FUNDAMENTALS_UNKNOWN_ROW,
    eligible_actions,
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


# ── FUNDAMENTALS_UNKNOWN row (D-08) ──────────────────────────────────────────

_ALL_ACTIONS = frozenset({"LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"})
_ZONE_KEYS = [k for k in ACTION_POLICY_TABLE if k[0] != FUNDAMENTALS_UNKNOWN_ROW]
_PROFILES = ("conservative", "aggressive")


def test_table_has_fundamentals_unknown_row():
    for profile in _PROFILES:
        assert ACTION_POLICY_TABLE[(FUNDAMENTALS_UNKNOWN_ROW, profile)] == frozenset({"MONITOR", "AVOID"})


def test_six_zone_rows_remain():
    assert len(_ZONE_KEYS) == 6


@pytest.mark.parametrize("zone,profile", _ZONE_KEYS)
def test_resolve_with_unknown_fundamentals(zone, profile):
    zone_row = ACTION_POLICY_TABLE[(zone, profile)]
    unknown_row = ACTION_POLICY_TABLE[(FUNDAMENTALS_UNKNOWN_ROW, profile)]
    resolved = resolve_allowed_actions(zone, profile, fundamentals_status="UNKNOWN")
    assert resolved == zone_row & unknown_row
    assert resolved <= {"MONITOR", "AVOID"}
    assert {"MONITOR", "AVOID"} <= resolved
    # None and AVAILABLE leave the zone row unchanged.
    assert resolve_allowed_actions(zone, profile, fundamentals_status=None) == zone_row
    assert resolve_allowed_actions(zone, profile, fundamentals_status="AVAILABLE") == zone_row


@pytest.mark.parametrize("profile", _PROFILES)
def test_unknown_zone_with_unknown_fundamentals_is_exactly_the_row(profile):
    assert resolve_allowed_actions(None, profile, fundamentals_status="UNKNOWN") == frozenset({"MONITOR", "AVOID"})


def test_unrecognised_profile_uses_conservative_row_for_unknown_fundamentals():
    assert resolve_allowed_actions("PULLBACK_ENTRY", "mystery", fundamentals_status="UNKNOWN") == frozenset(
        {"MONITOR", "AVOID"}
    )


def test_parse_directive_extracts_from_to_phrasing():
    parsed = parse_directive("XYZ: change action from MONITOR to WAIT-FOR-ENTRY because price dipped.")
    assert parsed == ("XYZ", "WAIT-FOR-ENTRY")


_UNKNOWN_CTX = {"XYZ": {"entry_zone_status": "PULLBACK_ENTRY", "risk_profile": "aggressive",
                        "fundamentals_status": "UNKNOWN"}}


@pytest.mark.parametrize("action", ["LONG-BUY", "WAIT-FOR-ENTRY"])
def test_filter_directives_drops_buy_for_unknown_fundamentals(action):
    directives = [f"XYZ: change action to {action} because momentum improved."]
    kept, rejected = filter_directives(directives, _UNKNOWN_CTX)
    assert kept == []
    assert len(rejected) == 1
    assert FUNDAMENTALS_UNKNOWN_ROW in rejected[0].reason


def test_filter_directives_keeps_avoid_for_unknown_fundamentals():
    directives = ["XYZ: change action to AVOID because fundamentals are unreadable."]
    kept, rejected = filter_directives(directives, _UNKNOWN_CTX)
    assert kept == directives
    assert rejected == []


@pytest.mark.parametrize("action,dropped", [("LONG-BUY", True), ("WAIT-FOR-ENTRY", True), ("AVOID", False)])
def test_filter_critiques_for_unknown_fundamentals(action, dropped):
    item = {"ticker": "XYZ", "severity": "MAJOR", "issue_type": "X", "finding": "f",
            "instruction": f"XYZ: change action to {action} because reasons."}
    kept, rejected = filter_critiques([item], _UNKNOWN_CTX)
    if dropped:
        assert kept == []
        assert FUNDAMENTALS_UNKNOWN_ROW in rejected[0].reason
    else:
        assert kept == [item]
        assert rejected == []


def test_filter_without_fundamentals_status_key_is_unchanged():
    ctx = {"XYZ": {"entry_zone_status": "PULLBACK_ENTRY", "risk_profile": "aggressive"}}
    directives = ["XYZ: change action to LONG-BUY because momentum improved."]
    kept, rejected = filter_directives(directives, ctx)
    assert kept == directives and rejected == []


# ── eligible_actions (built on the table) ────────────────────────────────────

@pytest.mark.parametrize("zone,profile", _ZONE_KEYS)
def test_eligible_built_on_table(zone, profile):
    assert eligible_actions(zone, profile, fundamentals_status="UNKNOWN") == resolve_allowed_actions(
        zone, profile, fundamentals_status="UNKNOWN"
    )
    zone_row = ACTION_POLICY_TABLE[(zone, profile)]
    assert eligible_actions(zone, profile) == zone_row
    assert eligible_actions(zone, profile, fundamentals_status="AVAILABLE", price_data_error=None) == zone_row


@pytest.mark.parametrize("zone,profile", _ZONE_KEYS)
def test_eligible_price_data_error(zone, profile):
    assert eligible_actions(zone, profile, price_data_error="no data") == frozenset({"MONITOR", "AVOID"})


def test_eligible_empty_price_error_is_not_an_error():
    assert eligible_actions("PULLBACK_ENTRY", "aggressive", price_data_error="") == ACTION_POLICY_TABLE[
        ("PULLBACK_ENTRY", "aggressive")
    ]


def test_eligible_missing_zone_is_permissive():
    assert eligible_actions(None, "conservative", fundamentals_status="AVAILABLE") == _ALL_ACTIONS
    assert eligible_actions(None, "conservative") == _ALL_ACTIONS
