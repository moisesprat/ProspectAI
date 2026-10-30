"""
PatientSerperDevTool — retry-classification wrapper around crewai_tools'
SerperDevTool.

The upstream SerperDevTool (crewai_tools.tools.serper_dev_tool) makes exactly
one HTTP request per call and raises immediately on any error -- it has no
retry logic of its own. Any "retried Nx" behavior observed in production comes
from the calling LLM agent re-invoking the tool, not from anything inside the
tool. That means a 400 (a malformed/rejected request) gets retried identically
every time with zero chance of succeeding, burning latency for nothing, while
a transient 429/5xx is abandoned on the first failure instead of being retried
where a retry could plausibly help.

This wrapper fixes both: 4xx fails fast (no retry, response body logged so the
next failure is diagnosable) and only 429/5xx (and network-level errors with no
response, e.g. timeouts) are retried, up to MAX_RETRIES times with backoff.

Stall rule (phase 2, plan 02-08, D-13, STALL-02): the total backoff wait is capped
by RETRY_BUDGET_SECONDS, measured with time.monotonic from the first attempt. If
the next backoff would pass the remaining budget the tool re-raises the last error
instead of sleeping, so a Serper outage cannot stall a phase. The sleeps that
remain are blocking but bounded; the Flow calls this tool through
asyncio.to_thread, so they never run on the event loop.
"""

import logging
import time
from typing import Any, Dict, Optional

import requests
from crewai_tools import SerperDevTool

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 2
BACKOFF_BASE_SECONDS = 1.0
RETRY_BUDGET_SECONDS = 3.0
_LOGGED_BODY_CHARS = 300


class PatientSerperDevTool(SerperDevTool):
    """
    Drop-in replacement for SerperDevTool with 4xx fail-fast / 429-5xx retry semantics.

    Retries are bounded twice: at most MAX_RETRIES retries, and a total backoff wait
    of at most RETRY_BUDGET_SECONDS (D-13). A backoff that would pass the remaining
    budget is not slept; the last error is raised instead.
    """

    def _make_api_request(self, search_query: str, search_type: str) -> Dict[str, Any]:
        attempt = 0
        started = time.monotonic()
        while True:
            try:
                return super()._make_api_request(search_query, search_type)
            except requests.exceptions.RequestException as e:
                response = getattr(e, "response", None)
                status: Optional[int] = response.status_code if response is not None else None
                body = (
                    response.content.decode("utf-8", errors="replace")
                    if response is not None else str(e)
                )[:_LOGGED_BODY_CHARS]
                # A response with no status code (connection error, timeout) is
                # treated as transient, same as a 5xx -- worth retrying.
                is_retryable = status is None or status in RETRYABLE_STATUS_CODES

                if not is_retryable:
                    logger.error(
                        "Serper request failed with non-retryable status %s -- not retrying. Response: %s",
                        status, body,
                    )
                    raise

                attempt += 1
                if attempt > MAX_RETRIES:
                    logger.error(
                        "Serper request failed with status %s after %d retries. Response: %s",
                        status, MAX_RETRIES, body,
                    )
                    raise

                backoff = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                remaining = RETRY_BUDGET_SECONDS - (time.monotonic() - started)
                if backoff > remaining:
                    logger.warning(
                        "Serper retry budget of %.1fs spent (status %s, attempt %d/%d); "
                        "not waiting %.1fs, giving up",
                        RETRY_BUDGET_SECONDS, status, attempt, MAX_RETRIES, backoff,
                    )
                    raise
                logger.warning(
                    "Serper request failed with retryable status %s (attempt %d/%d); retrying in %.1fs",
                    status, attempt, MAX_RETRIES, backoff,
                )
                time.sleep(backoff)
