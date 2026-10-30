"""
Shared fake monotonic clock for budget and backoff tests (plan 02-08, D-13).

``FakeClock`` stands in for the ``time`` module inside a tool module: patch the
module's ``time`` attribute with an instance (``patch("utils.x.time", clock)``)
and ``time.monotonic()`` / ``time.sleep()`` then advance a virtual ``now``
instead of the wall clock. ``sleep`` never blocks, so a tool that would wait
60 s on a real clock finishes instantly and the test reads the elapsed fake
time from ``clock.now``.

The same pattern as ``tests/deploy_fakes.py`` ``_Clock``, extended with the
request side: ``get_side_effect`` builds a ``requests.get`` replacement that
advances the clock by a latency per call, honours the ``timeout`` argument the
way a real socket would (a call slower than its timeout costs exactly the
timeout and raises ``requests.exceptions.Timeout``), and records every call's
``timeout`` and its position relative to the sleeps (``events``).

Reused by plan 02-16's loop-thread test.
"""

from typing import Any, Callable, List, Tuple, Union

import requests


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now: float = start
        self.sleeps: List[float] = []
        self.timeouts: List[Any] = []
        # Ordered ("get", url) / ("sleep", seconds) entries.
        self.events: List[Tuple[str, Any]] = []

    # -- the slice of the ``time`` module the tools use ---------------------

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.events.append(("sleep", seconds))
        self.now += seconds

    # -- request side -------------------------------------------------------

    @property
    def request_count(self) -> int:
        return sum(1 for kind, _ in self.events if kind == "get")

    def get_side_effect(
        self,
        response: Union[Any, List[Any], Callable[[int, str], Any]],
        latency: float = 0.0,
    ) -> Callable[..., Any]:
        """
        Build a ``requests.get`` replacement.

        ``response`` is one response object (returned every call), a list
        (one entry per call, the last repeated), or a callable
        ``(call_index, url) -> response``. An entry that is an Exception
        instance is raised instead of returned. ``latency`` is the fake
        seconds each call costs.
        """

        def _get(url: str, params: Any = None, headers: Any = None, timeout: Any = None, **_: Any) -> Any:
            index = self.request_count
            self.events.append(("get", url))
            self.timeouts.append(timeout)

            if timeout is not None and latency > timeout:
                self.now += timeout
                raise requests.exceptions.Timeout("read timed out")
            self.now += latency

            if callable(response):
                item = response(index, url)
            elif isinstance(response, list):
                item = response[min(index, len(response) - 1)]
            else:
                item = response
            if isinstance(item, Exception):
                raise item
            return item

        return _get
