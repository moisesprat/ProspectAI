"""Live smoke of the Claude Haiku 5.5 request shape (MODEL-01; RESEARCH A2/A3).

Purpose: settle two assumptions the offline tests cannot, before a release burns
a version number:

  A2  Haiku 5.5 accepts ``output_format`` (structured outputs) together with a
      real tool and thinking disabled.
  A3  Haiku 5.5 accepts adaptive thinking with ``output_config.effort = low``
      together with ``output_format``.

Since plan 02-25 the draft, critic and final steps run claude-sonnet-5-5 (agents.yaml), so
case B below runs the draft_strategy phase and follows agents.yaml, i.e. Sonnet 5.5;
scripts/smoke_sonnet55.py is the dedicated Sonnet 5.5 check (both Sonnet agents, with a
named fallback). The Haiku 5.5 adaptive-plus-effort shape is still pinned offline by the
environment-rollback test in tests/test_llm_request_shape.py.

Cost: two small calls (cents). This script is run by a human with their own key;
it is never run by CI and the offline test mocks the transport.

Usage, from ProspectAI/:

    ANTHROPIC_API_KEY=... .venv/bin/python scripts/smoke_haiku55.py
    ANTHROPIC_API_KEY=... .venv/bin/python scripts/smoke_haiku55.py --yaml-models

By default the resolved model ids honour MODEL / AGENT_*_MODEL from the
environment and are printed first. ``--yaml-models`` ignores those variables so
the check runs on the agents.yaml defaults.

Output is limited to: model, PASS/FAIL, HTTP status or exception class, content
block types, stop reason and token counts. Keys, headers and response text are
never printed.

Exit code: 0 when both cases pass, 1 otherwise.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx
from anthropic import AsyncAnthropic
from pydantic import BaseModel

from config.config import AGENT_MODEL_ENV_KEYS, GLOBAL_MODEL_ENV, Config
from prospect_ai_crew import TaskFactory

_TOOL_NAME = "get_ticker_note"
_REAL_TOOL = {
    "type": "function",
    "function": {
        "name": _TOOL_NAME,
        "description": "Return a short note about a stock ticker.",
        "parameters": {
            "type": "object",
            "properties": {"ticker": {"type": "string"}},
            "required": ["ticker"],
        },
    },
}


class SmokeAnswer(BaseModel):
    ticker: str
    note: str


class _Record:
    """Non-sensitive facts about the last response: never the response text."""

    def __init__(self) -> None:
        self.status: Optional[int] = None
        self.block_types: List[str] = []
        self.tool_names: List[str] = []
        self.stop_reason: Optional[str] = None
        self.input_tokens: Optional[int] = None
        self.output_tokens: Optional[int] = None


class _RecordingTransport(httpx.AsyncBaseTransport):
    """Applies the LLM's own interceptor, forwards to ``inner``, records the shape."""

    def __init__(self, inner: httpx.AsyncBaseTransport, llm: Any, record: _Record) -> None:
        self._inner = inner
        self._llm = llm
        self._record = record

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        interceptor = getattr(self._llm, "interceptor", None)
        if interceptor is not None:
            request = await interceptor.aon_outbound(request)
        response = await self._inner.handle_async_request(request)
        await response.aread()
        self._record.status = response.status_code
        try:
            body = json.loads(response.content)
        except ValueError:
            body = None
        if isinstance(body, dict):
            blocks = body.get("content")
            if isinstance(blocks, list):
                self._record.block_types = [
                    str(b.get("type")) for b in blocks if isinstance(b, dict)
                ]
                self._record.tool_names = [
                    str(b.get("name")) for b in blocks
                    if isinstance(b, dict) and b.get("type") == "tool_use"
                ]
            self._record.stop_reason = body.get("stop_reason")
            usage = body.get("usage")
            if isinstance(usage, dict):
                self._record.input_tokens = usage.get("input_tokens")
                self._record.output_tokens = usage.get("output_tokens")
        return response


def _install_recorder(llm: Any, inner: httpx.AsyncBaseTransport, record: _Record) -> None:
    """Swap the LLM's async client for one that records the response shape.

    One retry-free client per case, so a failing request costs exactly one call.
    """
    params = llm._get_client_params()
    params["max_retries"] = 0
    params["http_client"] = httpx.AsyncClient(
        transport=_RecordingTransport(inner, llm, record), timeout=params.get("timeout")
    )
    llm.async_client = AsyncAnthropic(**params)
    # crewai prints the raw API error (response text, possibly echoed input) to the
    # console through its event bus; this script reports the exception class only.
    llm._emit_call_started_event = lambda **_kw: None
    llm._emit_call_failed_event = lambda **_kw: None


@contextlib.contextmanager
def _env_without_models() -> Iterator[None]:
    names = [GLOBAL_MODEL_ENV, "ANTHROPIC_MODEL", *AGENT_MODEL_ENV_KEYS.values()]
    saved: Dict[str, str] = {n: os.environ.pop(n) for n in names if n in os.environ}
    try:
        yield
    finally:
        os.environ.update(saved)


def _report(label: str, phase: str, llm: Any, passed: bool, record: _Record, error: Optional[str]) -> None:
    thinking = getattr(llm, "_thinking_mode", "?")
    head = f"[{label}] {phase} model={llm.model} thinking={thinking}: {'PASS' if passed else 'FAIL'}"
    if error:
        head += f" error={error}"
    print(head)
    print(
        f"    status={record.status} blocks={','.join(record.block_types) or '-'} "
        f"stop_reason={record.stop_reason} "
        f"tokens_in={record.input_tokens} tokens_out={record.output_tokens}"
    )


async def _run_case(
    label: str,
    phase: str,
    factory: TaskFactory,
    inner: httpx.AsyncBaseTransport,
    *,
    with_tool: bool,
    prompt: str,
) -> bool:
    llm = factory._phase_config[phase]["agent"].llm
    record = _Record()
    _install_recorder(llm, inner, record)
    error: Optional[str] = None
    passed = False
    logging.disable(logging.ERROR)  # crewai logs str(exc), which can carry response text
    try:
        result = await llm.acall(
            [{"role": "user", "content": prompt}],
            tools=[_REAL_TOOL] if with_tool else None,
            response_model=SmokeAnswer,
        )
        ok_status = record.status == 200
        parsed = isinstance(result, SmokeAnswer)
        called_tool = _TOOL_NAME in record.tool_names
        passed = ok_status and (parsed or (with_tool and called_tool))
        if not passed:
            error = "NoParsedAnswer"
    except Exception as exc:  # report the class only: messages may echo response text
        error = type(exc).__name__
        if record.status is None:
            record.status = getattr(exc, "status_code", None)
    finally:
        logging.disable(logging.NOTSET)
    _report(label, phase, llm, passed, record, error)
    return passed


async def _run_cases(factory: TaskFactory, inner: httpx.AsyncBaseTransport) -> int:
    a = await _run_case(
        "A", "market_analysis", factory, inner, with_tool=True,
        prompt=f"Call the {_TOOL_NAME} tool for ticker AAPL, then answer with a ticker and a one-line note.",
    )
    # Case B follows agents.yaml: draft_strategy is Sonnet 5.5 since plan 02-25
    # (see scripts/smoke_sonnet55.py for the dedicated Sonnet check).
    b = await _run_case(
        "B", "draft_strategy", factory, inner, with_tool=False,
        prompt="Answer with ticker AAPL and a one-line note.",
    )
    return 0 if (a and b) else 1


def run_smoke(transport: Optional[httpx.AsyncBaseTransport] = None, *, yaml_models: bool = False) -> int:
    """Run both live cases. ``transport`` replaces the network (offline tests)."""
    if yaml_models:
        with _env_without_models():
            factory = TaskFactory(config=Config())
    else:
        factory = TaskFactory(config=Config())
    ids = {
        phase: factory._phase_config[phase]["agent"].llm.model
        for phase in ("market_analysis", "draft_strategy")
    }
    print(f"Resolved models: market_analysis={ids['market_analysis']} draft_strategy={ids['draft_strategy']}")
    inner = transport if transport is not None else httpx.AsyncHTTPTransport()
    return asyncio.run(_run_cases(factory, inner))


def main() -> None:
    parser = argparse.ArgumentParser(description="Live smoke of the Haiku 5.5 request shape (two calls).")
    parser.add_argument(
        "--yaml-models", action="store_true",
        help="ignore MODEL / AGENT_*_MODEL and use the agents.yaml defaults",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY (environment or .env) first.")

    sys.exit(run_smoke(yaml_models=args.yaml_models))


if __name__ == "__main__":
    main()
