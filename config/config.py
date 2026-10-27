import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

# Global default model id (any provider); used with MODEL_PROVIDER=anthropic|ollama
GLOBAL_MODEL_ENV = "MODEL"

# Optional per-agent overrides; if set, they override MODEL for that agent only.
AGENT_MODEL_ENV_KEYS: Dict[str, str] = {
    "market_analyst":      "AGENT_MARKET_ANALYST_MODEL",
    "technical_analyst":   "AGENT_TECHNICAL_ANALYST_MODEL",
    "fundamental_analyst": "AGENT_FUNDAMENTAL_ANALYST_MODEL",
    "investor_strategic":  "AGENT_INVESTOR_STRATEGIC_MODEL",
    "critic":              "AGENT_CRITIC_MODEL",
}

_env_path = Path(".env")
if _env_path.exists():
    load_dotenv(_env_path)

def _strip_optional_provider_prefix(model_value: str) -> str:
    """Accept MODEL as raw id or provider/id; always return raw id."""
    model_value = model_value.strip()
    if "/" in model_value:
        return model_value.split("/", 1)[1].strip()
    return model_value


class Config:
    """Configuration class for ProspectAI.

    Model selection is an explicit input (DEPL-03): the process environment is
    snapshotted once, at construction, and never written back. Explicit
    ``model`` / ``provider`` / ``ollama_base_url`` win over the snapshot, so two
    runs in one warm process cannot inherit each other's choices.
    """

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
    ):
        self._explicit_model = (
            _strip_optional_provider_prefix(model) if model and model.strip() else None
        )
        self._explicit_provider = provider.strip() if provider and provider.strip() else None
        self._explicit_ollama_base_url = ollama_base_url or None

        # Env snapshot (read once). ANTHROPIC_API_KEY stays a lazy read: secrets are
        # never copied into the instance.
        self._env_model = os.getenv(GLOBAL_MODEL_ENV)
        self._env_anthropic_model = os.getenv("ANTHROPIC_MODEL")
        self._env_ollama_model = os.getenv("OLLAMA_MODEL")
        self._env_provider = os.getenv("MODEL_PROVIDER")
        self._env_ollama_base_url = os.getenv("OLLAMA_BASE_URL")
        self._env_agent_models: Dict[str, Optional[str]] = {
            key: os.getenv(env_key) for key, env_key in AGENT_MODEL_ENV_KEYS.items()
        }

    @property
    def ANTHROPIC_API_KEY(self):
        return os.getenv("ANTHROPIC_API_KEY")

    @property
    def provider(self) -> str:
        return self._explicit_provider or self._env_provider or "anthropic"

    @property
    def ANTHROPIC_MODEL(self):
        return self._env_anthropic_model

    @property
    def OLLAMA_BASE_URL(self):
        return self._explicit_ollama_base_url or self._env_ollama_base_url

    @property
    def OLLAMA_MODEL(self):
        return self._env_ollama_model

    def default_model_id(self) -> Optional[str]:
        """
        Global default model id: explicit model, then MODEL, then legacy
        provider-specific env vars (all from the construction-time snapshot).
        """
        if self._explicit_model:
            return self._explicit_model

        model = self._env_model
        if model and model.strip():
            return _strip_optional_provider_prefix(model)

        if self.provider == "ollama":
            fallback = self._env_ollama_model
            return fallback.strip() if fallback and fallback.strip() else None

        fallback = self._env_anthropic_model
        return fallback.strip() if fallback and fallback.strip() else None

    def model_id_for_agent(self, agent_key: str) -> Optional[str]:
        """
        Resolve model for one agent.
        AGENT_*_MODEL overrides global MODEL.
        """
        per = self._env_agent_models.get(agent_key)
        if per and per.strip():
            return _strip_optional_provider_prefix(per)

        return self.default_model_id()

    @property
    def effective_default_model_id(self) -> Optional[str]:
        return self.default_model_id()

    # Data Sources Configuration
    MARKET_DATA_SOURCES = [
        "yahoo_finance",
        "alpha_vantage",
        "finnhub",
    ]

    # Technical Analysis Parameters
    TECHNICAL_INDICATORS = [
        "SMA",
        "EMA",
        "RSI",
        "MACD",
        "BB",
        "ATR",
    ]

    # Fundamental Analysis Parameters
    FUNDAMENTAL_METRICS = [
        "P/E",
        "P/B",
        "ROE",
        "ROA",
        "Debt/Equity",
        "Current Ratio",
    ]

    # Risk Assessment Parameters
    RISK_LEVELS = ["Low", "Medium", "High"]
    REWARD_LEVELS = ["Low", "Medium", "High"]

    # Output Configuration
    OUTPUT_FORMAT = "json"
    REPORT_TEMPLATE = "comprehensive"
