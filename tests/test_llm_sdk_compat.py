"""Guards the anthropic SDK range (hotfix 01-12) and the crewai internals MODEL-01 relies on.

Incident: prospectai 1.9.3 shipped with anthropic 2.3.0 because our own range
(`anthropic>=2.3,<3`) never consulted crewai's declared extra (`anthropic~=0.73.0`).
crewai's Anthropic provider then failed every analysis against the 2.x SDK.
`test_installed_anthropic_satisfies_crewai_extra` keeps the two ranges aligned.

MODEL-01 (Claude Haiku 5.5) depends on two crewai internals that a crewai bump could
change silently: the native structured-output allow-list that agents/caching_llm.py
extends, and the `thinking` / `interceptor` constructor hooks. Both are guarded here.
The package sends no sampling parameters after D-02, so the old
"messages.create accepts temperature" check is gone; tests/test_llm_request_shape.py
owns the request-shape contract.

All checks run offline against the installed (locked) environment.
"""
import importlib.metadata as metadata
import inspect

from packaging.requirements import Requirement


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


def test_native_allow_list_patched():
    """MODEL-01: crewai only keeps real tools on the native structured-output path
    for ids in its allow-list. agents.caching_llm appends the 5.5 models at import."""
    from crewai.llms.providers.anthropic import completion

    import agents.caching_llm  # noqa: F401  (the import applies the patch)

    allow_list = completion.NATIVE_STRUCTURED_OUTPUT_MODELS
    assert isinstance(allow_list, tuple) and all(isinstance(m, str) for m in allow_list)
    assert completion._supports_native_structured_outputs("claude-haiku-5-5")
    assert completion._supports_native_structured_outputs("claude-sonnet-5-5")
    assert completion._supports_native_structured_outputs("claude-sonnet-5-5-20261101")
    assert not completion._supports_native_structured_outputs("claude-sonnet-5")


def test_crewai_hooks_present():
    """MODEL-01: thinking and the effort interceptor ride on two crewai hooks."""
    from crewai.llms.hooks.base import BaseInterceptor
    from crewai.llms.providers.anthropic.completion import AnthropicCompletion

    params = inspect.signature(AnthropicCompletion.__init__).parameters
    assert "thinking" in params, "AnthropicCompletion no longer accepts thinking"
    assert "interceptor" in params, "AnthropicCompletion no longer accepts interceptor"
    assert hasattr(BaseInterceptor, "aon_outbound")
