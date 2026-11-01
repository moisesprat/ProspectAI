"""The one place that decides what counts as a mention of a ticker and what a ticker looks like.

Shared by the Reddit tool (its per-ticker post counter), the Serper counter in
``utils.market_records`` (``symbol_mention_counts``) and the pick check in the same module.
The same matcher that grounds a pick also counts it, so a symbol can never be published
on a count the grounding check would not have accepted (review CR-01, WR-01, WR-02).

Matching rules (``symbol_pattern``):

- A dollar cashtag matches in any case: ``$NVDA``, ``$nvda``.
- A bare symbol matches only as written (upper case) and only as a whole word, so
  ``AAA`` does not match inside ``AAAB`` or ``BAAA``, and the word "nvda" is not a mention.
- A share-class symbol such as ``BRK.B`` matches with a dot or a dash (``BRK.B``,
  ``BRK-B``). Each literal part is escaped exactly once; the Reddit tool used to escape
  the dot and then escape the result again, so a dotted ticker could never match (WR-01).
- With ``guard_ambiguous`` on, a symbol that is also an ordinary word or abbreviation
  counts only in an explicit form: a cashtag, or an exchange-qualified form such as
  ``NASDAQ: ON`` or ``(NYSE: F)``. Every one-letter symbol and the ``AMBIGUOUS_SYMBOLS``
  stoplist are ambiguous. That is what stops "A strong quarter", "IT spending", "ALL
  eyes", "U.S." and "F-150" from counting as mentions of A, IT, ALL, U and F (WR-02).
  The Reddit tool leaves the guard off: its posts are short, and its stoplist rule is
  not part of that change.

``is_valid_ticker`` is the format gate every pick passes before it can reach tool
arguments, an SSE ``tool_input``, an error field path or retry feedback: 1 to 5 upper-case
letters with an optional single dot or dash share-class letter. It is a format check,
not proof that the symbol is a listed company; that stays Phase 4 (CORR-06).

This module imports nothing from the other utils modules.
"""
import re
from typing import Any, FrozenSet, Tuple

_TICKER_FORMAT = re.compile(r"[A-Z]{1,5}(?:[.-][A-Z])?")
_SHARE_CLASS = re.compile(r"([A-Z]+)[.-]([A-Z])")

EXPLICIT_EXCHANGES: Tuple[str, ...] = (
    "NYSE", "NASDAQ", "NYSEARCA", "NYSEAMERICAN", "AMEX", "CBOE", "OTC",
)

# Symbols of two or more letters that are also ordinary words or abbreviations. Symbols
# that real prose writes in capitals for the company (GS, KO, MU, GE, BA, CAT) stay out:
# tests/test_ticker_matching.py pins them as unambiguous.
AMBIGUOUS_SYMBOLS: FrozenSet[str] = frozenset({
    "IT", "ON", "ALL", "NOW", "NET", "APP", "ARE", "SO", "ET", "ES", "ED", "LOW", "WELL",
    "PR", "AR", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "IF", "IN", "IS", "ME", "NO",
    "OF", "OR", "UP", "US", "WE", "ANY", "CAN", "FOR", "NEW", "ONE", "OUT", "RUN", "SEE",
    "TWO",
})

_EXCHANGE_ALTERNATION = "|".join(sorted(EXPLICIT_EXCHANGES, key=len, reverse=True))


def is_valid_ticker(value: Any) -> bool:
    """True only for a str that fully matches the ticker format (the caller strips and upper-cases first)."""
    return isinstance(value, str) and _TICKER_FORMAT.fullmatch(value) is not None


def is_ambiguous(symbol: str) -> bool:
    """True for every one-character symbol and every stoplist member."""
    return len(symbol) == 1 or symbol in AMBIGUOUS_SYMBOLS


def _core(symbol: str) -> str:
    """Regex for the symbol itself: each literal part escaped once, the share-class separator a dot or a dash."""
    share = _SHARE_CLASS.fullmatch(symbol)
    if share:
        return re.escape(share.group(1)) + "[.-]" + re.escape(share.group(2))
    return re.escape(symbol)


def symbol_pattern(symbol: str, *, guard_ambiguous: bool) -> "re.Pattern[str]":
    """Compiled whole-symbol pattern for an already normalised (stripped, upper-case) symbol."""
    core = _core(symbol)
    alternatives = [r"\$(?i:" + core + ")"]
    if guard_ambiguous and is_ambiguous(symbol):
        alternatives.append(r"(?<!\w)(?i:" + _EXCHANGE_ALTERNATION + r")\s*:\s*" + core)
    else:
        alternatives.append(r"(?<!\w)" + core)
    return re.compile("(?:" + "|".join(alternatives) + r")(?!\w)")
