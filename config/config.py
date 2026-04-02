import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

# Global default model id (any provider); used with MODEL_PROVIDER=anthropic|ollama
GLOBAL_MODEL_ENV = "MODEL"

# Optional per-agent overrides; if set, they override MODEL for that agent only.
AGENT_MODEL_ENV_KEYS: Dict[str, str] = {
    "market_analyst": "AGENT_MARKET_ANALYST_MODEL",
    "technical_analyst": "AGENT_TECHNICAL_ANALYST_MODEL",
    "fundamental_analyst": "AGENT_FUNDAMENTAL_ANALYST_MODEL",
    "investor_strategic": "AGENT_INVESTOR_STRATEGIC_MODEL",
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
    """Configuration class for ProspectAI"""

    @property
    def ANTHROPIC_API_KEY(self):
        return os.getenv("ANTHROPIC_API_KEY")

    @property
    def ANTHROPIC_MODEL(self):
        return os.getenv("ANTHROPIC_MODEL")

    @property
    def OLLAMA_BASE_URL(self):
        return os.getenv("OLLAMA_BASE_URL")

    @property
    def OLLAMA_MODEL(self):
        return os.getenv("OLLAMA_MODEL")

    def default_model_id(self) -> Optional[str]:
        """
        Global default model id: MODEL first, then legacy provider-specific env vars.
        """
        model = os.getenv(GLOBAL_MODEL_ENV)
        if model and model.strip():
            return _strip_optional_provider_prefix(model)

        if os.getenv("MODEL_PROVIDER", "anthropic") == "ollama":
            fallback = os.getenv("OLLAMA_MODEL")
            return fallback.strip() if fallback and fallback.strip() else None

        fallback = os.getenv("ANTHROPIC_MODEL")
        return fallback.strip() if fallback and fallback.strip() else None

    def model_id_for_agent(self, agent_key: str) -> Optional[str]:
        """
        Resolve model for one agent.
        AGENT_*_MODEL overrides global MODEL.
        """
        env_key = AGENT_MODEL_ENV_KEYS.get(agent_key)
        if env_key:
            per = os.getenv(env_key)
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
