"""Flow-owned, bounded schema retry for one pipeline phase (STALL-04; D-11, D-12).

Why the Flow owns the retry. crewai 1.12.2 does not retry "up to max_iter".
A pydantic ValidationError raised inside the LLM call makes
``Agent._check_execution_error`` re-run the whole task up to
``max_retry_limit`` (default 2) with no feedback, and that counter lives on the
Agent for its whole lifetime, so the draft and final phases (one shared agent)
draw on one budget. ``Task.guardrail`` cannot help: the error is raised before
a guardrail sees any output. TaskFactory therefore sets ``max_retry_limit = 0``
on every agent, and this module counts attempts per phase instead.

Contract:

- ``MAX_SCHEMA_RETRIES = 2``: at most 3 attempts per phase, inside the
  requirement's "at most 3 retries". Every retry re-runs a 20-60 s LLM call, so
  the smaller number protects the p95 < 300 s target.
- Each retry gets feedback: the failing field paths and, for closed sets, the
  allowed values. Nothing else about the previous answer is repeated.
- Only schema failures are retried (a pydantic ValidationError, directly or in
  the exception chain, or a PhaseOutputError). Every other exception, such as
  an API outage or MissingToolCallError, propagates at once.
- When the budget runs out the phase fails with PhaseSchemaError. There is no
  deterministic fallback: an exhausted phase never publishes a substitute (D-12).
- D-11: enum fields have no case normaliser in the schema, so a case or
  whitespace variant is a validation error that spends this budget.
- Security: PhaseSchemaError and PhaseOutputError messages carry the phase, the
  attempt count and dotted field paths only, never input values or raw model
  output, and stay within 400 characters. They reach the public SSE error event.
"""
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple, Type, TypeVar, cast

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

_M = TypeVar("_M", bound=BaseModel)

MAX_SCHEMA_RETRIES = 2

_MESSAGE_CAP = 400
_FEEDBACK_MAX_LINES = 10
_FEEDBACK_LINE_CAP = 200
_FEEDBACK_HEADING = (
    "Your previous answer failed validation. "
    "Fix exactly these fields and keep everything else:"
)


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _join_fields(head: str, fields: Sequence[str]) -> str:
    """head + comma-joined fields, cut so the whole message is at most 400 chars."""
    joined = ", ".join(fields)
    return head + _cap(joined, max(0, _MESSAGE_CAP - len(head)))


class PhaseOutputError(RuntimeError):
    """A phase result could not be parsed or failed a coverage check.

    ``fields`` are dotted field paths; ``errors`` optionally carries pydantic-style
    entries (``loc``, ``msg``, ``ctx``) used to build retry feedback. The message
    never contains raw model output.
    """

    def __init__(
        self,
        message: str,
        fields: Optional[Sequence[str]] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.fields: List[str] = list(fields or [])
        self.errors: Optional[List[Dict[str, Any]]] = errors
        super().__init__(_cap(message, _MESSAGE_CAP))


class PhaseSchemaError(RuntimeError):
    """A phase still failed schema validation after its retry budget (D-12)."""

    def __init__(self, phase: str, fields: Sequence[str], attempts: int) -> None:
        self.phase = phase
        self.fields: List[str] = list(fields)
        self.attempts = attempts
        noun = "attempt" if attempts == 1 else "attempts"
        head = f"{phase}: output failed schema validation after {attempts} {noun}; fields: "
        super().__init__(_join_fields(head, self.fields))


def _path(loc: Any) -> str:
    if isinstance(loc, (tuple, list)):
        return ".".join(str(p) for p in loc) or "(root)"
    return str(loc) or "(root)"


def field_paths(exc: ValidationError) -> List[str]:
    """Dotted ``loc`` of every error, in order, without duplicates."""
    return _unique(_path(e.get("loc", ())) for e in exc.errors())


def _unique(items) -> List[str]:
    seen: Dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)


def _sanitized(errors: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep loc, msg and the allowed-values hint; drop the input value and url."""
    out = []
    for e in errors:
        ctx = e.get("ctx") or {}
        entry: Dict[str, Any] = {"loc": tuple(e.get("loc", ())), "msg": str(e.get("msg", ""))}
        if isinstance(ctx, dict) and "expected" in ctx:
            entry["ctx"] = {"expected": ctx["expected"]}
        out.append(entry)
    return out


def feedback_from(errors: Sequence[Dict[str, Any]]) -> str:
    """Retry feedback: one line per failing field with the allowed values when known.

    At most 10 lines, each at most 200 characters. pydantic ``msg`` does not
    contain the offending input value.
    """
    lines = [_FEEDBACK_HEADING]
    for e in list(errors)[:_FEEDBACK_MAX_LINES]:
        msg = str(e.get("msg", "")).strip()
        line = f"- {_path(e.get('loc', ()))}: {msg}"
        ctx = e.get("ctx")
        expected = ctx.get("expected") if isinstance(ctx, dict) else None
        if expected and str(expected) not in msg:
            line += f" (allowed: {expected})"
        lines.append(_cap(line, _FEEDBACK_LINE_CAP))
    return "\n".join(lines)


def extract_model(result: Any, model_cls: Type[_M], phase: str) -> _M:
    """Validated model from a crew result.

    Uses ``tasks_output[0].pydantic`` when crewai set it, else parses ``result.raw``.
    A parse or validation failure becomes PhaseOutputError with field paths only.
    """
    tasks = getattr(result, "tasks_output", None)
    pydantic_model = tasks[0].pydantic if tasks else None
    if pydantic_model is not None:
        return cast(_M, pydantic_model)
    raw = getattr(result, "raw", None) or ""
    try:
        return model_cls.model_validate_json(raw)
    except ValidationError as exc:
        fields = field_paths(exc)
        head = f"{phase}: output failed schema validation; fields: "
        raise PhaseOutputError(_join_fields(head, fields), fields, _sanitized(exc.errors())) from exc


def _find_validation_error(exc: BaseException) -> Optional[ValidationError]:
    """The ValidationError in ``exc``'s __cause__/__context__ chain, if any."""
    seen = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, ValidationError):
            return current
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return None


async def run_phase(
    *,
    phase: str,
    build_task: Callable[[str], Any],
    kickoff: Callable[[Any], Awaitable[Any]],
    model_cls: Type[_M],
    validate: Optional[Callable[[_M], None]] = None,
    max_retries: int = MAX_SCHEMA_RETRIES,
    tracker: Any = None,
) -> Tuple[Any, _M]:
    """Run one phase with at most ``max_retries`` schema retries; return ``(result, model)``.

    ``build_task(feedback)`` builds a fresh task per attempt ("" on the first).
    ``kickoff(task)`` runs it. ``validate(model)`` may raise PhaseOutputError for
    checks the schema cannot express. Attempts are counted here, per call, so one
    phase never spends another phase's budget.
    """
    feedback = ""
    attempts = 0
    while True:
        attempts += 1
        task = build_task(feedback)
        failure: BaseException
        try:
            result = await kickoff(task)
            model = extract_model(result, model_cls, phase)
            if validate is not None:
                validate(model)
        except PhaseOutputError as exc:
            failure = exc
            fields = exc.fields
            errors = exc.errors or [
                {"loc": f, "msg": "does not satisfy the output contract"} for f in fields
            ]
        except Exception as exc:
            validation_error = _find_validation_error(exc)
            if validation_error is None:
                raise
            failure = exc
            fields = field_paths(validation_error)
            errors = _sanitized(validation_error.errors())
        else:
            if tracker is not None:
                tracker.record_phase_attempts(phase, attempts)
            return result, model

        if attempts > max_retries:
            raise PhaseSchemaError(phase, fields, attempts) from failure
        logger.warning(
            "%s: schema validation failed on attempt %d of %d; retrying with feedback; fields: %s",
            phase, attempts, max_retries + 1, _cap(", ".join(fields), _MESSAGE_CAP),
        )
        feedback = feedback_from(errors)
