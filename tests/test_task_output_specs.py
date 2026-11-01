"""Prompt output specs validated against their Pydantic models (TEST-01, CORR-01, D-11)."""

import copy
import types
from typing import Annotated, List, Literal, Optional, Union, get_args, get_origin

import pytest
import yaml
from pydantic import BaseModel

from config.task_config_loader import TaskConfigLoader, allowed_values_text, literal_fields

TASK_KEYS = [
    "market_analysis",
    "technical_analysis",
    "fundamental_analysis",
    "draft_strategy",
    "critique_review",
    "final_strategy",
]

RENDER_KWARGS = {"sector": "Technology", "today": "2026-04-29", "risk_profile": "conservative"}


def _phase_output_models():
    from prospect_ai_crew import PHASE_OUTPUT_MODELS

    return PHASE_OUTPUT_MODELS


def _declared_examples():
    """Tasks whose tasks.yaml entry declares output_example (all six since plan 02-18)."""
    loader = TaskConfigLoader()
    return [k for k in TASK_KEYS if "output_example" in loader.get_task_config(k)]


# ── Walkers (schema vs example) ────────────────────────────────────────────────

def _unwrap(annotation):
    """Strip Annotated and Optional so a field's real type is visible."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _unwrap(get_args(annotation)[0])
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        return _unwrap(args[0]) if len(args) == 1 else annotation
    return annotation


def _child_model(annotation):
    """The nested BaseModel a field holds (directly or as list items), else None."""
    annotation = _unwrap(annotation)
    if get_origin(annotation) in (list, List):
        annotation = _unwrap(get_args(annotation)[0])
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _items(value):
    return value if isinstance(value, list) else [value]


def check_example_keys(example, model, path="$"):
    """Every key is a field of `model`, recursively. AssertionError names the path."""
    assert isinstance(example, dict), f"{path}: expected an object, got {type(example).__name__}"
    for key, value in example.items():
        assert key in model.model_fields, f"{path}.{key} is not a field of {model.__name__}"
        child = _child_model(model.model_fields[key].annotation)
        if child is not None and value is not None:
            for i, item in enumerate(_items(value)):
                check_example_keys(item, child, f"{path}.{key}[{i}]")


def check_required_fields(example, model, path="$"):
    """Every required field of `model` is present in the example, recursively."""
    for name, field in model.model_fields.items():
        if field.is_required():
            assert name in example, f"{path}.{name} is required by {model.__name__} but missing"
        child = _child_model(field.annotation)
        if child is not None and example.get(name) is not None:
            for i, item in enumerate(_items(example[name])):
                check_required_fields(item, child, f"{path}.{name}[{i}]")


def render_task(task_key, loader=None):
    loader = loader or TaskConfigLoader()
    return loader.render(task_key, output_model=_phase_output_models()[task_key], **RENDER_KWARGS)


# ── Example vs schema ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("task", _declared_examples())
def test_examples_validate(task):
    example = TaskConfigLoader().get_task_config(task)["output_example"]
    _phase_output_models()[task].model_validate(example)


@pytest.mark.parametrize("task", _declared_examples())
def test_example_keys_are_model_fields(task):
    example = TaskConfigLoader().get_task_config(task)["output_example"]
    check_example_keys(example, _phase_output_models()[task])


@pytest.mark.parametrize("task", _declared_examples())
def test_required_fields_present(task):
    example = TaskConfigLoader().get_task_config(task)["output_example"]
    check_required_fields(example, _phase_output_models()[task])


def test_at_least_the_fundamental_task_declares_an_example():
    assert "fundamental_analysis" in _declared_examples()


# ── Rendering ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("task", _declared_examples())
def test_prompt_lists_allowed_values(task):
    model = _phase_output_models()[task]
    description = render_task(task)["description"]
    for path, values in literal_fields(model):
        for value in values:
            assert f'"{value}"' in description, f"{task}: {path} value {value!r} missing from the prompt"


@pytest.mark.parametrize("task", _declared_examples())
def test_prompt_embeds_the_example_as_json(task):
    loader = TaskConfigLoader()
    example = loader.get_task_config(task)["output_example"]
    first_key = next(iter(example))
    assert f'"{first_key}"' in render_task(task, loader)["description"]


def test_render_all_tasks():
    """All six tasks render with sector, today and risk_profile (catches a stray `$`)."""
    for task in TASK_KEYS:
        out = render_task(task)
        assert out["description"].strip() and out["expected_output"].strip()
        assert "$sector" not in out["description"] and "$output_example" not in out["description"]


def test_tasks_without_examples_render_as_before():
    loader = TaskConfigLoader()
    for task in TASK_KEYS:
        if task in _declared_examples():
            continue
        assert render_task(task, loader) == loader.render(task, **RENDER_KWARGS)


# ── Allowed values (loader helper) ─────────────────────────────────────────────

class _Leaf(BaseModel):
    kind: Literal["a", "b"]
    note: str = ""


class _Spec(BaseModel):
    action: Optional[Literal["GO", "STOP"]] = None
    leaves: List[_Leaf]
    sizes: Annotated[Literal["S", "M"], "meta"] = "S"


def test_literal_fields_walks_optional_lists_and_nested_models():
    found = dict(literal_fields(_Spec))
    assert found == {
        "action": ("GO", "STOP"),
        "leaves[].kind": ("a", "b"),
        "sizes": ("S", "M"),
    }


def test_allowed_values_text_one_line_per_literal_field():
    assert allowed_values_text(_Spec).splitlines() == [
        'action: "GO" | "STOP"',
        'leaves[].kind: "a" | "b"',
        'sizes: "S" | "M"',
    ]


def test_allowed_values_text_without_literals_is_none_marker():
    class Plain(BaseModel):
        x: str

    assert allowed_values_text(Plain) == "(none)"


def test_real_action_model_lists_the_four_actions():
    from schemas.agent_outputs import InvestorStrategicOutput

    text = allowed_values_text(InvestorStrategicOutput)
    for action in ("LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID"):
        assert f'"{action}"' in text


# ── Template safety ────────────────────────────────────────────────────────────

def _loader_with(tmp_path, mutate):
    """A TaskConfigLoader over a tmp copy of tasks.yaml edited by `mutate(tasks_dict)`."""
    data = copy.deepcopy(TaskConfigLoader().config_data)
    mutate(data["tasks"])
    path = tmp_path / "tasks.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return TaskConfigLoader(str(path))


def test_dollar_in_example_is_not_retemplated(tmp_path):
    def mutate(tasks):
        tasks["fundamental_analysis"]["output_example"]["summary"] = "Costs $sector and $$ and ${today}"

    loader = _loader_with(tmp_path, mutate)
    description = render_task("fundamental_analysis", loader)["description"]
    assert "Costs $sector and $$ and ${today}" in description


def test_output_example_placeholder_without_example_names_the_task(tmp_path):
    def mutate(tasks):
        tasks["fundamental_analysis"].pop("output_example")

    loader = _loader_with(tmp_path, mutate)
    with pytest.raises(KeyError) as info:
        render_task("fundamental_analysis", loader)
    assert "fundamental_analysis" in str(info.value)
    assert "output_example" in str(info.value)


# ── Drift ──────────────────────────────────────────────────────────────────────

def test_drift_is_caught(tmp_path):
    """Renaming key_risks to risk_factors in the prompt's example fails the key check."""
    def mutate(tasks):
        for entry in tasks["fundamental_analysis"]["output_example"]["analyses"]:
            entry["risk_factors"] = entry.pop("key_risks")

    loader = _loader_with(tmp_path, mutate)
    example = loader.get_task_config("fundamental_analysis")["output_example"]
    model = _phase_output_models()["fundamental_analysis"]
    with pytest.raises(AssertionError, match="risk_factors"):
        check_example_keys(example, model)
    with pytest.raises(AssertionError, match="key_risks"):
        check_required_fields(example, model)


def test_dropping_a_required_field_is_caught(tmp_path):
    def mutate(tasks):
        tasks["fundamental_analysis"]["output_example"].pop("summary")

    loader = _loader_with(tmp_path, mutate)
    example = loader.get_task_config("fundamental_analysis")["output_example"]
    with pytest.raises(AssertionError, match="summary"):
        check_required_fields(example, _phase_output_models()["fundamental_analysis"])


# ── Task wiring ────────────────────────────────────────────────────────────────

@pytest.fixture
def real_factory(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "dummy-serper")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "dummy-id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "dummy-secret")
    from prospect_ai_crew import TaskFactory

    return TaskFactory()


@pytest.mark.parametrize("phase", TASK_KEYS)
def test_output_models_match_tasks(real_factory, phase):
    task = real_factory.build_task(phase, "Technology", "2026-04-29")
    assert task.output_pydantic is _phase_output_models()[phase]


def test_phase_output_models_cover_the_six_phases():
    assert set(_phase_output_models()) == set(TASK_KEYS)


# ── Fundamental prompt (narrative-only role, D-06, CORR-10) ────────────────────

def test_fundamental_prompt_is_narrative_only():
    description = render_task("fundamental_analysis")["description"]
    for forbidden in (
        "fetch_fundamental_data",
        "grade_fundamental_data",
        "stock_analyses",
        "raw_fundamentals",
        "sector_fundamental_summary",
    ):
        assert forbidden not in description, f"fundamental prompt still mentions {forbidden}"
    assert "data_status" in description
    for wanted in ("key_strengths", "key_risks", "investment_thesis"):
        assert wanted in description


def test_fundamental_expected_output_matches_the_narrative_shape():
    expected = render_task("fundamental_analysis")["expected_output"]
    assert "analyses" in expected and "summary" in expected
    assert "stock_analyses" not in expected and "raw_fundamentals" not in expected


def test_fundamental_agent_text_has_no_tool_calls():
    agent = yaml.safe_load(open(TaskConfigLoader().config_path.parent / "agents.yaml", encoding="utf-8"))
    cfg = agent["agents"]["fundamental_analyst"]
    text = f"{cfg['goal']} {cfg['backstory']}"
    for forbidden in ("tool call", "fetch_fundamental", "grade_fundamental", "call it first", "TWO batch"):
        assert forbidden not in text, f"fundamental_analyst text still says {forbidden!r}"
    assert cfg.get("thinking", "off") == "off"


# ── Technical prompt (narrative-only role, D-14, CORR-10, plan 02-15) ──────────

def test_technical_declares_an_example_and_lists_the_four_signals():
    assert "technical_analysis" in _declared_examples()
    description = render_task("technical_analysis")["description"]
    for value in ("BULLISH", "BEARISH", "MIXED", "NEUTRAL"):
        assert f'"{value}"' in description


def test_technical_prompt_is_narrative_only():
    description = render_task("technical_analysis")["description"]
    for forbidden in (
        "calculate_technical_indicators",
        "interpret_technical_indicators",
        "stock_analyses",
        "raw_indicators",
        "sector_technical_summary",
        "trend_strength: one of",
        "Copy these numbers",
    ):
        assert forbidden not in description, f"technical prompt still mentions {forbidden}"
    for wanted in ("overall_signal", "key_signals", "comprehensive_analysis", "investment_recommendation",
                   "no_data"):
        assert wanted in description


def test_technical_example_has_no_number_or_label_fields():
    example = TaskConfigLoader().get_task_config("technical_analysis")["output_example"]
    for entry in example["analyses"]:
        assert set(entry) == {"ticker", "overall_signal", "key_signals",
                              "comprehensive_analysis", "investment_recommendation"}


def test_technical_expected_output_matches_the_narrative_shape():
    expected = render_task("technical_analysis")["expected_output"]
    assert "analyses" in expected and "summary" in expected
    assert "stock_analyses" not in expected and "sector_technical_summary" not in expected


def test_technical_agent_text_has_no_tool_calls():
    agent = yaml.safe_load(open(TaskConfigLoader().config_path.parent / "agents.yaml", encoding="utf-8"))
    cfg = agent["agents"]["technical_analyst"]
    text = f"{cfg['goal']} {cfg['backstory']}"
    for forbidden in ("calculate_technical_indicators", "call it first", "batch call", "Python dict"):
        assert forbidden not in text, f"technical_analyst text still says {forbidden!r}"
    assert cfg.get("thinking", "off") == "off"


# ── Market prompt (narrative-only role, D-14, CORR-10, plan 02-16) ─────────────

def test_market_declares_an_example():
    assert "market_analysis" in _declared_examples()


def test_market_prompt_is_narrative_only():
    description = render_task("market_analysis")["description"]
    for forbidden in (
        "analyze_sector_reddit_sentiment",
        "search_internet",
        "SerperDevTool",
        "STEP 1",
        "data_source",
        "analysis_timestamp",
        "fallback_required",
        "mention_count = 0",
        "relevance_score = 0.5",
        "assign a float",
        "candidate_stocks[]",
    ):
        assert forbidden not in description, f"market prompt still mentions {forbidden}"
    for wanted in ("Market Data (collected by the pipeline)", "candidates", "rationale", "summary",
                   "untrusted", "ETF"):
        assert wanted in description


def test_market_example_tickers_are_neutral_placeholders():
    """CR-01: the example's tickers were the ones the model copied into a report (change 02-23)."""
    from utils.reddit_sentiment_tool import RedditSentimentTool
    from utils.ticker_matching import is_valid_ticker

    example = TaskConfigLoader().get_task_config("market_analysis")["output_example"]
    tickers = [entry["ticker"] for entry in example["candidates"]]
    universe = {t for tickers_ in RedditSentimentTool.SECTOR_TICKERS.values() for t in tickers_}
    commonly_copied = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA"}
    assert tickers and not commonly_copied & set(tickers)
    assert not universe & set(tickers)
    assert all(is_valid_ticker(t) for t in tickers)
    text = " ".join(entry["rationale"] for entry in example["candidates"]) + " " + example["summary"]
    for name in ("Apple", "Microsoft", "iPhone", "Azure", "Copilot", "Nvidia"):
        assert name not in text, f"market example still names {name}"


def test_market_prompt_states_the_grounding_rule():
    description = render_task("market_analysis")["description"]
    for wanted in ("ticker symbol itself", "is discarded", "Do not copy the example",
                   "Market Data (collected by the pipeline)", "candidates", "rationale", "summary",
                   "untrusted", "ETF"):
        assert wanted in description, f"market prompt lacks {wanted!r}"
    for forbidden in ("analyze_sector_reddit_sentiment", "SerperDevTool", "STEP 1", "data_source",
                      "analysis_timestamp", "fallback_required", "mention_count = 0"):
        assert forbidden not in description


def test_market_example_has_no_number_or_flag_fields():
    example = TaskConfigLoader().get_task_config("market_analysis")["output_example"]
    assert set(example) == {"candidates", "summary"}
    for entry in example["candidates"]:
        assert set(entry) == {"ticker", "rationale"}
    assert len(example["candidates"]) <= 5


def test_market_expected_output_matches_the_narrative_shape():
    expected = render_task("market_analysis")["expected_output"]
    assert "candidates" in expected and "summary" in expected
    for forbidden in ("candidate_stocks", "mention_count", "average_sentiment", "data_source", "analysis_timestamp"):
        assert forbidden not in expected


def test_market_agent_text_has_no_tool_calls_and_keeps_the_ticker_rule():
    agent = yaml.safe_load(open(TaskConfigLoader().config_path.parent / "agents.yaml", encoding="utf-8"))
    cfg = agent["agents"]["market_analyst"]
    text = f"{cfg['goal']} {cfg['backstory']}"
    for forbidden in ("When you need a tool", "call it first", "analysis_timestamp", "data_source",
                      "Python dict", "mention_count", "average_sentiment"):
        assert forbidden not in text, f"market_analyst text still says {forbidden!r}"
    assert "Never invent ticker symbols" in text
    assert cfg.get("thinking", "off") == "off"


# ── Draft prompt (action and narrative only, D-14, CORR-10, plan 02-17) ────────

def test_draft_declares_an_example_and_lists_the_actions_and_frequencies():
    assert "draft_strategy" in _declared_examples()
    description = render_task("draft_strategy")["description"]
    for value in ("LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID", "DAILY", "WEEKLY", "MONTHLY"):
        assert f'"{value}"' in description


def test_draft_prompt_is_narrative_only_and_keeps_the_reasoning_guidance():
    description = render_task("draft_strategy")["description"]
    for forbidden in (
        "compute_composite_scores",
        "allocate_portfolio",
        "STEP 4",
        "Copy ALL",
        "scaled_entry_setups",
        "from the tool result",
        "trade_setup(obj",
        "deployed_pct: float",
        "risk_level: str",
        "price_data_error",
    ):
        assert forbidden not in description, f"draft prompt still mentions {forbidden}"
    for wanted in (
        "RISK PROFILE: conservative",                      # the disposition text is kept
        "no pre-set resolution",                           # the open-reasoning guidance is kept
        "RSI < 50",                                        # the monitoring-trigger rules are kept
        "Price falls/retraces to entry_zone_high of $X.XX",
        "Scores and eligible actions (computed by the pipeline)",
        "eligible_actions",
        "CURRENT_ENTRY",
        "fundamentals_unknown",
        "excluded",
        "monitoring_triggers",
        "review_frequency",
        "overall_strategy",
    ):
        assert wanted in description, f"draft prompt lost {wanted!r}"


def test_draft_prompt_covers_the_no_sentiment_path():
    """02-16 decision A: on the Serper path sentiment is 'no data' and the score is renormalised."""
    description = render_task("draft_strategy")["description"]
    assert '"no data"' in description and "sentiment: no data" in description
    assert "rescaled" in description
    assert "never use a default number" in description.lower().replace("\n", " ") or "default number" in description


def test_draft_example_has_no_number_or_grade_fields():
    example = TaskConfigLoader().get_task_config("draft_strategy")["output_example"]
    assert set(example) == {"positions", "overall_strategy"}
    for entry in example["positions"]:
        assert set(entry) == {"ticker", "action", "rationale", "monitoring_triggers", "review_frequency"}


def test_draft_expected_output_matches_the_narrative_shape():
    expected = render_task("draft_strategy")["expected_output"]
    assert "positions" in expected and "overall_strategy" in expected
    for forbidden in ("allocation_pct", "trade_setup", "deployed_pct", "risk_level", "total_allocated_pct"):
        assert forbidden not in expected


def test_investor_agent_text_has_no_tool_calls_and_no_number_copying():
    agent = yaml.safe_load(open(TaskConfigLoader().config_path.parent / "agents.yaml", encoding="utf-8"))
    cfg = agent["agents"]["investor_strategic"]
    text = f"{cfg['goal']} {cfg['backstory']}"
    for forbidden in ("When you need a tool", "call it first", "Python dict", "compute_composite_scores",
                      "allocate_portfolio", "copy a numeric", "copy it verbatim", "verbatim"):
        assert forbidden not in text, f"investor_strategic text still says {forbidden!r}"
    # One text serves the draft and the final prompt: both write no number, so it never asks for one.
    assert "never compute, copy or invent one" in " ".join(text.split())
    assert "Valid actions: LONG-BUY, WAIT-FOR-ENTRY, MONITOR, AVOID" in text
    assert cfg["thinking"] == "low" and cfg["max_tokens"] == 16000


# ── All six tasks declare a validated example (TEST-01, plan 02-18) ────────────

def test_all_tasks_declare_output_example():
    assert _declared_examples() == TASK_KEYS


def test_every_prompt_embeds_its_example_and_lists_every_allowed_value():
    for task in TASK_KEYS:
        description = render_task(task)["description"]
        assert "$output_example" not in description and "$allowed_values" not in description
        example = TaskConfigLoader().get_task_config(task)["output_example"]
        assert f'"{next(iter(example))}"' in description, task
        for path, values in literal_fields(_phase_output_models()[task]):
            for value in values:
                assert f'"{value}"' in description, f"{task}: {path} value {value!r} missing from the prompt"


# ── Critique prompt (reasoning only, compliant by design, D-14, D-15, plan 02-18) ──

def test_critique_prompt_lists_severity_and_profile_values_and_keeps_the_checklist():
    description = render_task("critique_review")["description"]
    for value in ("CRITICAL", "MAJOR", "MINOR", "conservative", "aggressive"):
        assert f'"{value}"' in description
    for forbidden in ("Python dict", "pure Python dict"):
        assert forbidden not in description, f"critique prompt still says {forbidden!r}"
    for wanted in (
        "RISK PROFILE: conservative",
        "SENTIMENT AVAILABILITY",
        "PRICE_IN_ZONE_WAIT",
        "COMMON INVERSION TO AVOID",
        "VAGUE_RATIONALE",
        "revision_directives",
        "approved_positions",
        "A completely clean draft is a valid outcome",
        "Output JSON only",
    ):
        assert wanted in description, f"critique prompt lost {wanted!r}"


def test_critique_example_has_every_critic_field_and_a_finding_per_severity_style():
    example = TaskConfigLoader().get_task_config("critique_review")["output_example"]
    from schemas.agent_outputs import CriticOutput

    assert set(example) == set(CriticOutput.model_fields)
    for item in example["per_ticker_critiques"]:
        assert set(item) == {"ticker", "severity", "issue_type", "finding", "instruction"}
    assert example["per_ticker_critiques"], "the example must show a finding, not only the empty list"


def test_critique_expected_output_names_json():
    expected = render_task("critique_review")["expected_output"]
    assert "Python dict" not in expected and "JSON" in expected


# ── Final prompt (action and narrative only, D-14, CORR-10, plan 02-18) ────────

def test_final_declares_an_example_and_lists_the_actions_and_frequencies():
    assert "final_strategy" in _declared_examples()
    description = render_task("final_strategy")["description"]
    for value in ("LONG-BUY", "WAIT-FOR-ENTRY", "MONITOR", "AVOID", "DAILY", "WEEKLY", "MONTHLY"):
        assert f'"{value}"' in description


def test_final_prompt_is_narrative_only_and_keeps_the_critic_handling():
    description = render_task("final_strategy")["description"]
    for forbidden in (
        "placeholders",
        "verbatim",
        "allocate_portfolio",
        "composite_score(float)",
        "allocation_pct(float)",
        "trade_setup(obj",
        "deployed_pct: float",
        "risk_level: str",
        "STEP 4",
        "Copy the draft",
        "numeric fields must",
    ):
        assert forbidden not in description, f"final prompt still mentions {forbidden}"
    flat = " ".join(description.split())
    for wanted in (
        "RISK PROFILE: conservative",
        "counter-argument",                                 # STEP 1 kept
        "every CRITICAL and MAJOR critique MUST be explicitly addressed",
        "Scores and eligible actions (computed by the pipeline)",
        "eligible_actions",
        "RSI < 50",                                         # the trigger rules are kept
        "monitoring_triggers",
        "review_frequency",
        "overall_strategy",
        "recomputed after you answer",                      # the numbers are the Flow's
        "write none",
        "replaced by MONITOR",                              # the clamp is stated
    ):
        assert wanted in flat, f"final prompt lost {wanted!r}"


def test_final_example_is_the_narrative_shape_and_has_no_number_fields():
    example = TaskConfigLoader().get_task_config("final_strategy")["output_example"]
    assert set(example) == {"positions", "overall_strategy"}
    for entry in example["positions"]:
        assert set(entry) == {"ticker", "action", "rationale", "monitoring_triggers", "review_frequency"}


def test_final_expected_output_matches_the_narrative_shape():
    expected = render_task("final_strategy")["expected_output"]
    assert "positions" in expected and "overall_strategy" in expected
    for forbidden in ("allocation_pct", "trade_setup", "deployed_pct", "risk_level", "total_allocated_pct",
                      "scaled_entry_setups", "current_price"):
        assert forbidden not in expected


def test_critic_agent_text_asks_for_json_and_no_number_copying():
    agent = yaml.safe_load(open(TaskConfigLoader().config_path.parent / "agents.yaml", encoding="utf-8"))
    cfg = agent["agents"]["critic"]
    text = f"{cfg['goal']} {cfg['backstory']}"
    assert "Python dict" not in text and "JSON" in text
    assert cfg["thinking"] == "low" and cfg["max_tokens"] == 16000
