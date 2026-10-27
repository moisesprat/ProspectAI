"""
Per-tool-call timing for pipeline tools (STALL-01).

``instrument_tool`` wraps a tool instance's ``_run`` so every call is recorded
on the ExecutionTracker with the tool's phase, duration, outcome and output
size.

The phase is bound to the tool INSTANCE (a closure constant), not to a
ContextVar. crewai runs tools through ``run_in_executor``, which drops the
caller's context, so a ContextVar reads ``None`` inside ``_run`` and would
misattribute (or lose) calls from the concurrently running technical_analysis
and fundamental_analysis phases. Each tool instance belongs to exactly one
phase in TaskFactory, so the instance binding is exact.

Timing is public data (SSE, R2 report JSON, SPA). Only the phase, tool name,
duration, ok flag, exception CLASS NAME and output character count are ever
recorded or logged; never exception messages, tool arguments or tool output,
because request errors can embed URLs carrying API keys.
"""

import logging
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_MARKER = "_prospectai_timed_phase"


def instrument_tool(tool: Any, phase: str, get_tracker: Callable[[], Optional[Any]]) -> Any:
    """Wrap ``tool._run`` in place so each call is recorded under ``phase``.

    ``get_tracker`` is called at invocation time because the tracker is created
    later, inside ``run_analysis``. It may return None (nothing is recorded).
    Idempotent: an already-instrumented tool is returned unchanged.
    """
    if getattr(tool, _MARKER, None) is not None:
        return tool

    original = tool._run
    tool_name = tool.name

    def timed(*args: Any, **kwargs: Any) -> Any:
        tracker = get_tracker()
        t0 = time.perf_counter()
        ok = True
        error: Optional[str] = None
        output_chars: Optional[int] = None
        logger.info("tool_start phase=%s tool=%s", phase, tool_name)
        try:
            result = original(*args, **kwargs)
            output_chars = len(str(result))
            return result
        except BaseException as exc:  # record the class name, then re-raise unchanged
            ok = False
            error = type(exc).__name__
            raise
        finally:
            t1 = time.perf_counter()
            if tracker is not None:
                tracker.record_tool_call(phase, tool_name, t0, t1, ok, error, output_chars)
            logger.info(
                "tool_end phase=%s tool=%s elapsed=%.3f ok=%s", phase, tool_name, t1 - t0, ok
            )

    object.__setattr__(tool, "_run", timed)
    object.__setattr__(tool, _MARKER, phase)
    return tool
