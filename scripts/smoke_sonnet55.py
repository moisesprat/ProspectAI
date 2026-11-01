"""Live smoke of the Claude Sonnet 5.5 request shape (plan 02-25, M4; MODEL-01).

Purpose: prove, before anything is released, that the two Sonnet 5.5 agents
(investor_strategic for the draft and final steps, and critic) are accepted by the
Messages API exactly as agents.yaml configures them. The offline request-shape tests
pin what the package sends; only a live call shows what Sonnet 5.5 accepts. Open
question this settles: does Sonnet 5.5 accept crewai 1.12.2's ``output_format`` plus
the structured-outputs beta header together with adaptive thinking and
``output_config.effort`` (or with thinking off, sent as ``between_tools``)?

Cases
-----
  S1  one structured ``acall`` on the draft_strategy phase LLM, as configured.
  S2  one structured ``acall`` on the critique_review phase LLM, as configured.
      Each uses the LLM TaskFactory builds from agents.yaml, no tools, a one-line
      benign prompt. A case PASSES only if the status is 200, the answer parses and
      the stop reason is neither ``refusal`` nor ``max_tokens``.
Diagnostics, run only when S1 or S2 failed with a 400 (so a pass costs two calls):
  S3  a plain-text call (no structured output) on the failing case's LLM: tells whether
      the configured thinking mode is accepted without structured output.
  S4  a fresh LLM for the same model and max_tokens with thinking off (sent as
      ``between_tools``), asked for a structured answer: tells whether the thinking-off
      value plus structured output is accepted.
A failure whose status is not 400 (access, rate limit, server error, a refusal or an
unparsed answer) is not a request-shape result; no diagnostics are spent on it.

Cost: two small calls (a few cents); four if one case failed. Run by a human with their
own key; never by CI (the offline tests mock the transport).

Usage, from ProspectAI/:

    ANTHROPIC_API_KEY=... .venv/bin/python scripts/smoke_sonnet55.py
    ANTHROPIC_API_KEY=... .venv/bin/python scripts/smoke_sonnet55.py --yaml-models

The key is read from the environment or ProspectAI/.env. By default the resolved model
ids honour MODEL / AGENT_*_MODEL and are printed first; ``--yaml-models`` ignores those
variables (and restores them afterwards) so the check runs on the agents.yaml models.

Output is limited to: the resolved model ids, per case the model, thinking mode, PASS or
FAIL, exception class, the shape sent (thinking type, effort, whether output_format was
sent, tool_choice type), status, content block types, stop reason and token counts, then
one ``SMOKE VERDICT:`` line and, for a request-shape failure, one ``FALLBACK:`` line.
Keys, headers, prompts and response text are never printed.

Exit code: 0 on ``SMOKE VERDICT: PASS``, 1 otherwise.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

_SCRIPTS = Path(__file__).resolve().parent
ROOT = _SCRIPTS.parent
for _path in (str(ROOT), str(_SCRIPTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import httpx

import smoke_haiku55 as _haiku
from agents.caching_llm import make_caching_llm
from config.config import Config
from prospect_ai_crew import TaskFactory

_Record = _haiku._Record
_install_recorder = _haiku._install_recorder
_env_without_models = _haiku._env_without_models
SmokeAnswer = _haiku.SmokeAnswer

_PHASES = (
    "market_analysis", "technical_analysis", "fundamental_analysis",
    "draft_strategy", "critique_review", "final_strategy",
)
# (label, phase, the agents.yaml agent whose thinking mode the phase uses)
_REQUIRED = (
    ("S1", "draft_strategy", "investor_strategic"),
    ("S2", "critique_review", "critic"),
)
_BAD_STOP_REASONS = ("refusal", "max_tokens")
_PROMPT = "Answer with ticker AAPL and a one-line note."


class _ShapeRecord(_Record):
    """The response facts of ``_Record`` plus the non-sensitive shape of the request."""

    def __init__(self) -> None:
        super().__init__()
        self.thinking_type: Optional[str] = None
        self.effort: Optional[str] = None
        self.structured: bool = False
        self.tool_choice: Optional[str] = None


class _ShapeInner(httpx.AsyncBaseTransport):
    """Notes the request shape (never its text) and forwards to the real transport.

    It sits inside the sibling's recording transport, which applies the LLM's own
    interceptor first, so the shape recorded here is the body actually sent.
    """

    def __init__(self, inner: httpx.AsyncBaseTransport, record: _ShapeRecord) -> None:
        self._inner = inner
        self._record = record

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        try:
            body = json.loads(request.content)
        except (httpx.RequestNotRead, ValueError):
            body = None
        if isinstance(body, dict):
            thinking = body.get("thinking")
            self._record.thinking_type = thinking.get("type") if isinstance(thinking, dict) else None
            config = body.get("output_config")
            self._record.effort = config.get("effort") if isinstance(config, dict) else None
            self._record.structured = "output_format" in body
            choice = body.get("tool_choice")
            self._record.tool_choice = choice.get("type") if isinstance(choice, dict) else None
        return await self._inner.handle_async_request(request)


class _Case:
    def __init__(self, label: str, phase: str, agent: str, llm: Any, structured: bool) -> None:
        self.label = label
        self.phase = phase
        self.agent = agent
        self.llm = llm
        self.structured = structured
        self.record = _ShapeRecord()
        self.passed = False
        self.error: Optional[str] = None


def _report(case: _Case) -> None:
    llm, rec = case.llm, case.record
    head = (
        f"[{case.label}] {case.phase} model={llm.model} "
        f"thinking={getattr(llm, '_thinking_mode', '?')}: {'PASS' if case.passed else 'FAIL'}"
    )
    if case.error:
        head += f" error={case.error}"
    print(head)
    print(
        f"    sent: thinking={rec.thinking_type or '-'} effort={rec.effort or '-'} "
        f"output_format={'yes' if rec.structured else 'no'} tool_choice={rec.tool_choice or '-'} | "
        f"status={rec.status} blocks={','.join(rec.block_types) or '-'} "
        f"stop_reason={rec.stop_reason} "
        f"tokens_in={rec.input_tokens} tokens_out={rec.output_tokens}"
    )


async def _run_case(case: _Case, inner: httpx.AsyncBaseTransport) -> _Case:
    record = case.record
    _install_recorder(case.llm, _ShapeInner(inner, record), record)
    # The sibling stubs the started and failed events; without a started event crewai's
    # event bus prints a fixed warning on every completed call, so stub that one too.
    case.llm._emit_call_completed_event = lambda **_kw: None
    logging.disable(logging.ERROR)  # crewai logs str(exc), which can carry response text
    try:
        result = await case.llm.acall(
            [{"role": "user", "content": _PROMPT}],
            response_model=SmokeAnswer if case.structured else None,
        )
        answered = isinstance(result, SmokeAnswer) if case.structured else isinstance(result, str)
        case.passed = (
            record.status == 200 and answered and record.stop_reason not in _BAD_STOP_REASONS
        )
        if not case.passed:
            case.error = "Refusal" if record.stop_reason == "refusal" else "NoAnswer"
    except Exception as exc:  # report the class only: messages may echo response text
        case.error = type(exc).__name__
        if record.status is None:
            record.status = getattr(exc, "status_code", None)
    finally:
        logging.disable(logging.NOTSET)
    _report(case)
    return case


def _thinking_of(factory: TaskFactory, phase: str) -> str:
    return getattr(factory._phase_config[phase]["agent"].llm, "_thinking_mode", "?")


async def _run_all(factory: TaskFactory, inner: httpx.AsyncBaseTransport) -> int:
    required: List[_Case] = []
    for label, phase, agent in _REQUIRED:
        llm = factory._phase_config[phase]["agent"].llm
        required.append(await _run_case(_Case(label, phase, agent, llm, structured=True), inner))

    failed = [c for c in required if not c.passed]
    if not failed:
        print("SMOKE VERDICT: PASS")
        return 0

    shape_failures = [c for c in failed if c.record.status == 400]
    if not shape_failures:
        print("SMOKE VERDICT: FAIL")
        for case in failed:
            print(
                f"{case.label} ({case.phase}): status={case.record.status} "
                f"stop_reason={case.record.stop_reason} error={case.error}"
            )
        print(
            "This is not a request-shape result (access, rate limit, server error, a refusal "
            "or an unparsed answer): fix access or retry once; no code change."
        )
        return 1

    target = shape_failures[0]
    s3 = await _run_case(
        _Case("S3", target.phase, target.agent, target.llm, structured=False), inner
    )
    fresh = make_caching_llm(
        f"anthropic/{target.llm.model}",
        thinking="off",
        api_key=getattr(target.llm, "api_key", None),
        max_tokens=target.llm.max_tokens,
    )
    s4 = await _run_case(_Case("S4", target.phase, target.agent, fresh, structured=True), inner)

    print("SMOKE VERDICT: FAIL")
    print(
        f"S3 configured thinking, plain text ({target.phase}): "
        f"{'PASS' if s3.passed else 'FAIL'} status={s3.record.status}"
    )
    print(
        f"S4 thinking off, structured output ({target.phase}): "
        f"{'PASS' if s4.passed else 'FAIL'} status={s4.record.status}"
    )
    agents = [c.agent for c in shape_failures]
    names = " and ".join(agents)
    already_off = all(_thinking_of(factory, c.phase) == "off" for c in shape_failures)
    if s4.passed and not already_off:
        print(
            f"FALLBACK: thinking off is accepted (S4 passed): set thinking to \"off\" for {names} "
            "in agents.yaml (the capability table sends it as between_tools), then re-run once."
        )
    elif s4.passed:
        print(
            f"FALLBACK: none is available, thinking is already off for {names} and the shape "
            "was accepted on retry (S4 passed): re-run once; if it fails again the release "
            "must not go ahead."
        )
    else:
        print(
            "FALLBACK: none is available (S4 failed: structured output is rejected even with "
            "thinking off): the release must not go ahead; the structured-output parameter "
            "needs a different translation and that is a new plan."
        )
    return 1


def run_smoke(transport: Optional[httpx.AsyncBaseTransport] = None, *, yaml_models: bool = False) -> int:
    """Run the smoke. ``transport`` replaces the network (offline tests)."""
    if yaml_models:
        with _env_without_models():
            factory = TaskFactory(config=Config())
    else:
        factory = TaskFactory(config=Config())
    ids = " ".join(f"{phase}={factory._phase_config[phase]['agent'].llm.model}" for phase in _PHASES)
    print(f"Resolved models: {ids}")
    inner = transport if transport is not None else httpx.AsyncHTTPTransport()
    return asyncio.run(_run_all(factory, inner))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live smoke of the Sonnet 5.5 request shape (two calls, four on a failure)."
    )
    parser.add_argument(
        "--yaml-models", action="store_true",
        help="ignore MODEL / AGENT_*_MODEL and use the agents.yaml models",
    )
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("Set ANTHROPIC_API_KEY (environment or .env) first.")

    sys.exit(run_smoke(yaml_models=args.yaml_models))


if __name__ == "__main__":
    main()
