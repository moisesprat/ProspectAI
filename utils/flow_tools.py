"""Flow-side tool calls: off the event loop, with a synthetic SSE step (STALL-02, D-16).

When a phase's tools move from the LLM into the Flow (CORR-10), two things the
crewai agent loop used to provide must be rebuilt here.

Off the event loop (STALL-02). The tools do blocking network I/O (yfinance,
Serper, Reddit). Called directly from an ``async`` Flow method they would stall
the loop that also streams SSE heartbeats and runs the parallel technical phase.
``call_tool`` therefore runs ``tool._run`` through ``asyncio.to_thread``. It is
given the same instrumented tool instance the TaskFactory holds, so
``utils.tool_timing.instrument_tool`` still records the call on the tracker.

A visible step (D-16). The SPA shows a phase's tool calls as ``agent_step``
events built from a step object with ``tool``, ``tool_input`` and ``log``
(backend ``app.py``). crewai produces those objects for agent tool calls; for a
Flow-owned call ``call_tool`` emits an equivalent one through the Flow's step
callback just before the call. The Flow emits ``agent_start`` before the first
step and one ``task_complete`` after the phase.

Security: ``tool_input`` reaches the public SSE stream. It is the JSON of the
call's keyword arguments cut to 400 characters. Flow tool arguments are ticker
lists and tool output JSON, never secrets. A callback failure is logged by
exception class name only and never stops the phase.
"""
import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

TOOL_INPUT_CAP = 400


def _tool_input(kwargs: dict) -> str:
    return json.dumps(kwargs, default=str)[:TOOL_INPUT_CAP]


async def call_tool(
    tool: Any,
    *,
    phase_index: int,
    step_callback: Optional[Callable[[int, Any], None]],
    thought: str,
    **kwargs: Any,
) -> Any:
    """Emit a synthetic step for ``tool``, then run ``tool._run(**kwargs)`` off the loop."""
    if step_callback is not None:
        step = SimpleNamespace(tool=tool.name, tool_input=_tool_input(kwargs), log=thought)
        try:
            step_callback(phase_index, step)
        except Exception as exc:
            logger.warning("step callback failed for tool %s: %s", tool.name, type(exc).__name__)
    return await asyncio.to_thread(tool._run, **kwargs)
