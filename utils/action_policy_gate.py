"""
Action Policy Gate — deterministic filter for Critic output.

Encodes the entry_zone_status x risk_profile -> allowed-actions table that the
Draft Strategist's STEP 3 already follows (see config/tasks.yaml), as data the
Flow can evaluate. A Critic instruction that orders an action outside the
allowed set for a position's entry_zone_status/risk_profile is dropped before
it reaches the Final Strategist -- this is exactly the failure mode where a
Critic revision_directive (or per_ticker_critiques instruction) ordered
WAIT-FOR-ENTRY at entry_zone_status=CURRENT_ENTRY (where LONG-BUY is the
mandatory default for both profiles) and the Final Strategist obeyed it.

CriticOutput carries the same kind of actionable instruction through two
channels: `revision_directives` (free-text list) and `per_ticker_critiques`
(structured, severity-tagged items whose `instruction` field is the same
"[TICKER]: [change] because [reason]" format). The Final Strategist prompt
treats per_ticker_critiques as independently authoritative ("address every
CRITICAL and MAJOR critique"), so both channels must be filtered -- cleaning
only revision_directives leaves the identical bad instruction reaching the
Final Strategist via per_ticker_critiques. `filter_directives()` covers the
first channel, `filter_critiques()` covers the second.

This gate is intentionally narrow: it encodes only the ONE genuine semantic
invariant in the pipeline (CURRENT_ENTRY excludes WAIT-FOR-ENTRY -- "wait for
entry" is a contradiction in terms when price is already in the actionable
zone, not a risk-policy preference). Every other combination the gate used to
restrict (e.g. LONG-BUY at BELOW_ZONE) was a defensible-but-debatable risk
stance, not a logical necessity, and has been opened up to the Strategist's
own reasoning as of change reasoning-depth-action-selection -- see that
change's design.md for the full "which restrictions are real invariants vs.
risk judgment in disguise" analysis. Loosening the gate does not loosen the
*valid action set*: PositionRecommendation.action stays a closed
Literal["LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"] in
schemas/agent_outputs.py regardless of what this table allows.
"""

import re
from typing import Dict, List, NamedTuple, Optional, Tuple

VALID_ACTIONS = ("LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID")

# entry_zone_status x risk_profile -> allowed actions.
#   CURRENT_ENTRY:  WAIT-FOR-ENTRY is never valid here -- price is already in
#                   the actionable zone, so "waiting for entry" is a semantic
#                   contradiction, not a risk-policy preference. This is the
#                   one true invariant the gate enforces.
#   PULLBACK_ENTRY: no restriction -- always was fully open (all 4 actions),
#                   left entirely to the Strategist/Critic's own reasoning.
#   BELOW_ZONE:     no restriction -- previously excluded LONG-BUY ("don't buy
#                   into a potential breakdown"), but that is a risk stance a
#                   real analyst could reasonably override, not a logical
#                   necessity, so it is now open to the Strategist's judgment
#                   like PULLBACK_ENTRY already was.
ACTION_POLICY_TABLE: Dict[Tuple[Optional[str], str], frozenset] = {
    ("CURRENT_ENTRY", "conservative"):  frozenset({"LONG-BUY", "MONITOR", "AVOID"}),
    ("CURRENT_ENTRY", "aggressive"):    frozenset({"LONG-BUY", "MONITOR", "AVOID"}),
    ("PULLBACK_ENTRY", "conservative"): frozenset({"WAIT-FOR-ENTRY", "LONG-BUY", "MONITOR", "AVOID"}),
    ("PULLBACK_ENTRY", "aggressive"):   frozenset({"LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"}),
    ("BELOW_ZONE", "conservative"):     frozenset({"LONG-BUY", "MONITOR", "AVOID"}),
    ("BELOW_ZONE", "aggressive"):       frozenset({"LONG-BUY", "MONITOR", "AVOID"}),
}


class RejectedDirective(NamedTuple):
    ticker: str
    rejected_action: str
    directive: str
    reason: str


# Matches a leading ticker label like "AAPL:", "AAPL -", "$AAPL:".
_TICKER_PREFIX = re.compile(r"^\s*\$?([A-Z]{1,6})\s*[:\-]")
_ACTION_PATTERN = re.compile(
    r"\b(LONG-BUY|WAIT-FOR-ENTRY|MONITOR|AVOID)\b", re.IGNORECASE
)
# Preferred: an action word immediately preceded by "to" (as in "change
# action from OLD to NEW"). This avoids false positives from an action word
# used as an ordinary verb elsewhere in the sentence -- e.g. "...re-enter on
# pullback; monitor for price to exit zone" contains "monitor" as a verb, not
# as the requested action, and must not be picked up as one.
_ACTION_TO_PATTERN = re.compile(
    r"\bto\s+(LONG-BUY|WAIT-FOR-ENTRY|MONITOR|AVOID)\b", re.IGNORECASE
)


def resolve_allowed_actions(entry_zone_status: Optional[str], risk_profile: str) -> frozenset:
    """Return the allowed-action set for a given entry_zone_status/risk_profile.

    Unknown or missing entry_zone_status resolves permissively (all valid
    actions allowed) -- the gate only blocks combinations it has positive
    knowledge are illegal, it never blocks on missing data.
    """
    key = (entry_zone_status, risk_profile)
    return ACTION_POLICY_TABLE.get(key, frozenset(VALID_ACTIONS))


def parse_directive(directive: str) -> Optional[Tuple[str, str]]:
    """Best-effort extraction of (ticker, requested_action) from a free-text
    Critic revision directive, e.g. "AAPL: change action to WAIT-FOR-ENTRY --
    wait for a better price." Returns None when the directive does not appear
    to target a specific action for a specific ticker (rationale-only or
    non-action concerns) -- such directives are not evaluated by the gate.

    Prefers the LAST "to <ACTION>" match (directives are routinely phrased
    "change action FROM <old> TO <new>", so this is the action being
    requested, not the one being replaced). Falls back to the last bare
    action-word match only if no "to <ACTION>" phrasing is present -- a bare
    scan for any of the four action words is too permissive on its own, since
    e.g. "monitor" also appears as an ordinary verb ("re-enter on pullback;
    monitor for price to exit zone") and must not be mistaken for the
    requested action.
    """
    ticker_match = _TICKER_PREFIX.match(directive)
    if not ticker_match:
        return None
    to_matches = list(_ACTION_TO_PATTERN.finditer(directive))
    if to_matches:
        requested = to_matches[-1]
    else:
        action_matches = list(_ACTION_PATTERN.finditer(directive))
        if not action_matches:
            return None
        requested = action_matches[-1]
    return ticker_match.group(1).upper(), requested.group(1).upper().replace(" ", "")


def filter_directives(
    directives: List[str],
    position_context: Dict[str, Dict[str, Optional[str]]],
) -> Tuple[List[str], List[RejectedDirective]]:
    """Filter revision_directives against the action-policy table.

    `position_context` maps ticker -> {"entry_zone_status": ..., "risk_profile": ...}.
    Returns (kept_directives, rejected). Directives that do not target a
    specific action, or whose ticker is not found in `position_context`, are
    always kept (passed through unfiltered).
    """
    kept: List[str] = []
    rejected: List[RejectedDirective] = []

    for directive in directives:
        parsed = parse_directive(directive)
        if parsed is None:
            kept.append(directive)
            continue

        ticker, requested_action = parsed
        ctx = position_context.get(ticker)
        if ctx is None:
            kept.append(directive)
            continue

        entry_zone_status = ctx.get("entry_zone_status")
        risk_profile = ctx.get("risk_profile") or "conservative"
        allowed = resolve_allowed_actions(entry_zone_status, risk_profile)

        if requested_action not in allowed:
            rejected.append(RejectedDirective(
                ticker=ticker,
                rejected_action=requested_action,
                directive=directive,
                reason=(
                    f"{requested_action} not allowed for entry_zone_status="
                    f"{entry_zone_status!r} risk_profile={risk_profile!r} "
                    f"(allowed: {sorted(allowed)})"
                ),
            ))
        else:
            kept.append(directive)

    return kept, rejected


def filter_critiques(
    critiques: List[Dict[str, str]],
    position_context: Dict[str, Dict[str, Optional[str]]],
) -> Tuple[List[Dict[str, str]], List[RejectedDirective]]:
    """Filter per_ticker_critiques against the action-policy table.

    Each item in `critiques` is a dict shaped like CritiqueItem
    (ticker/severity/issue_type/finding/instruction) -- see
    ProspectAIFlow._gated_slim_critique(). The `instruction` field is parsed
    the same way as a revision_directive (it uses the same "[TICKER]: [change]
    because [reason]" format per config/tasks.yaml's STEP 4). An item whose
    instruction requests a disallowed action is dropped entirely -- a finding
    whose corrective instruction is itself invalid is not useful information
    to forward, and dropping it (rather than keeping a neutered `finding`)
    keeps this channel's behavior consistent with `filter_directives()`.

    `position_context` maps ticker -> {"entry_zone_status": ..., "risk_profile": ...}.
    Returns (kept_critiques, rejected). Items whose `instruction` does not
    target a specific action, or whose ticker is not found in
    `position_context`, are always kept (passed through unfiltered).
    """
    kept: List[Dict[str, str]] = []
    rejected: List[RejectedDirective] = []

    for item in critiques:
        instruction = item.get("instruction", "")
        parsed = parse_directive(instruction)
        if parsed is None:
            kept.append(item)
            continue

        ticker, requested_action = parsed
        ctx = position_context.get(ticker)
        if ctx is None:
            kept.append(item)
            continue

        entry_zone_status = ctx.get("entry_zone_status")
        risk_profile = ctx.get("risk_profile") or "conservative"
        allowed = resolve_allowed_actions(entry_zone_status, risk_profile)

        if requested_action not in allowed:
            rejected.append(RejectedDirective(
                ticker=ticker,
                rejected_action=requested_action,
                directive=instruction,
                reason=(
                    f"{requested_action} not allowed for entry_zone_status="
                    f"{entry_zone_status!r} risk_profile={risk_profile!r} "
                    f"(allowed: {sorted(allowed)})"
                ),
            ))
        else:
            kept.append(item)

    return kept, rejected
