"""Per-process cache of parsed YAML config files (phase 5, DEBT-04, D-07).

Scope, and why it differs from utils/yfinance_cache.py: that cache is per run, because it
holds market data that must never leak from one visitor's run into the next (CORR-08). This
one is per process, which is safe only because of what it holds. The values are the parsed
contents of ``agents.yaml`` and ``tasks.yaml``, which are immutable inputs shared by every run
in a warm container. Nothing run-bound is ever cached here: no Agent, no tool instance, no
tracker getter, no ``TaskFactory._phase_config`` (DEPL-03, CORR-08).

Rules that keep it safe:

* The key is (resolved path, st_mtime_ns, st_size), so an edited file is read again.
* Every caller gets its own ``copy.deepcopy``, so one loader mutating its data is never
  seen by another loader.
* Parse errors are not cached. ``lru_cache`` stores only returned values, so a malformed
  file raises again on the next load.
* ``clear_yaml_cache()`` drops everything; ``AgentConfigLoader.reload_config`` calls it.
"""
from __future__ import annotations

import copy
import functools
import os
from pathlib import Path

import yaml


@functools.lru_cache(maxsize=16)
def _parse(path: str, mtime_ns: int, size: int) -> object:
    """Parse one file. ``mtime_ns`` and ``size`` are cache-key parts, not read here."""
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_yaml(path: str | os.PathLike) -> object:
    """The parsed YAML at ``path`` as a private deep copy.

    FileNotFoundError propagates from ``os.stat``; YAML errors propagate from the parse.
    """
    st = os.stat(path)
    return copy.deepcopy(_parse(str(Path(path).resolve()), st.st_mtime_ns, st.st_size))


def clear_yaml_cache() -> None:
    """Forget every parsed file (tests, and ``AgentConfigLoader.reload_config``)."""
    _parse.cache_clear()
