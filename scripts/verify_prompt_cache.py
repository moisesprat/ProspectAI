"""Verify Anthropic prompt caching end-to-end by reading the RAW response.

Runs two back-to-back calls through `AnthropicCachingCompletion` and prints
Anthropic's authoritative `cache_creation_input_tokens` and
`cache_read_input_tokens` from each response. On the first call you should
see creation_tokens > 0; on the second, read_tokens > 0.

Usage:
    python3 scripts/verify_prompt_cache.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from agents.caching_llm import AnthropicCachingCompletion

if not os.getenv("ANTHROPIC_API_KEY"):
    raise SystemExit("Set ANTHROPIC_API_KEY in .env first.")


# Long enough to cross 1024-token Sonnet threshold (≈5000 chars)
LONG_CONTEXT = (
    "You are a financial analyst. Reference data follows.\n\n"
    + "FACT: " * 1500
    + "\n\nUse the facts above to answer concisely."
)


def make_messages(question: str) -> list[dict]:
    return [
        {"role": "system", "content": LONG_CONTEXT},
        {"role": "user", "content": question},
    ]


def call_and_print(llm: AnthropicCachingCompletion, label: str, question: str) -> None:
    formatted, system = llm._format_messages_for_anthropic(make_messages(question))
    print(f"\n=== {label} ===")
    print(f"system is wrapped (list): {isinstance(system, list)}")
    if isinstance(system, list):
        print(f"  system[0].cache_control: {system[0].get('cache_control')}")

    # Drop into the underlying Anthropic SDK client directly to read raw usage.
    response = llm.client.messages.create(
        model=llm.model,
        max_tokens=100,
        system=system,
        messages=formatted,
    )
    u = response.usage
    print(f"  input_tokens:                  {u.input_tokens}")
    print(f"  output_tokens:                 {u.output_tokens}")
    print(f"  cache_creation_input_tokens:   {getattr(u, 'cache_creation_input_tokens', 'MISSING')}")
    print(f"  cache_read_input_tokens:       {getattr(u, 'cache_read_input_tokens', 'MISSING')}")


def main() -> None:
    llm = AnthropicCachingCompletion(
        model="claude-sonnet-4-5",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        max_tokens=200,
    )
    call_and_print(llm, "CALL 1 (expect cache_creation > 0)", "Summarize the facts in one sentence.")
    call_and_print(llm, "CALL 2 (expect cache_read > 0)", "Now list three facts.")


if __name__ == "__main__":
    main()
