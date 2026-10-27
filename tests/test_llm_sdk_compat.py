"""Guards the anthropic SDK against drifting out of crewai's supported range (hotfix 01-12).

Incident: prospectai 1.9.3 shipped with anthropic 2.3.0 because our own range
(`anthropic>=2.3,<3`) never consulted crewai's declared extra (`anthropic~=0.73.0`).
crewai's Anthropic provider passes `temperature` to messages.create, which 2.x
removed, so every analysis failed with
"AsyncMessages.create() got an unexpected keyword argument 'temperature'".

Both checks run offline against the installed (locked) environment.
"""
import importlib.metadata as metadata
import inspect

from packaging.requirements import Requirement

import anthropic
from anthropic.resources.messages import AsyncMessages, Messages


def _crewai_anthropic_requirement() -> Requirement:
    """The `anthropic` requirement crewai attaches to its `anthropic` extra."""
    found = []
    for raw in metadata.requires("crewai") or []:
        req = Requirement(raw)
        if req.name.lower() != "anthropic" or req.marker is None:
            continue
        if req.marker.evaluate({"extra": "anthropic"}) and not req.marker.evaluate({"extra": ""}):
            found.append(req)
    assert found, "crewai no longer declares an anthropic extra; update this guard"
    assert len(found) == 1, f"ambiguous crewai anthropic extra requirements: {found}"
    return found[0]


def test_installed_anthropic_satisfies_crewai_extra():
    req = _crewai_anthropic_requirement()
    installed = metadata.version("anthropic")
    assert req.specifier.contains(installed, prereleases=True), (
        f"anthropic {installed} is outside crewai's supported range '{req.specifier}'. "
        "Keep pyproject.toml's anthropic range aligned with crewai's anthropic extra, "
        "then re-run `bash scripts/lock.sh`."
    )


def test_messages_create_accepts_temperature():
    for cls in (AsyncMessages, Messages):
        params = inspect.signature(cls.create).parameters
        assert "temperature" in params, (
            f"{cls.__name__}.create() has no 'temperature' parameter in anthropic "
            f"{anthropic.__version__}; crewai's Anthropic provider passes it on every call."
        )
