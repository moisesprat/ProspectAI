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


class PatientSerperDevTool(SerperDevTool):
    """Drop-in replacement for SerperDevTool with 4xx fail-fast / 429-5xx retry semantics."""

    def _make_api_request(self, search_query: str, search_type: str) -> Dict[str, Any]:
        attempt = 0
        while True:
            try:
                return super()._make_api_request(search_query, search_type)
            except requests.exceptions.RequestException as e:
                response = getattr(e, "response", None)
                status: Optional[int] = response.status_code if response is not None else None
                body = (
                    response.content.decode("utf-8", errors="replace")
                    if response is not None else str(e)
                )
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
                logger.warning(
                    "Serper request failed with retryable status %s (attempt %d/%d); retrying in %.1fs",
                    status, attempt, MAX_RETRIES, backoff,
                )
                time.sleep(backoff)
