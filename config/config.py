import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(".env")
if _env_path.exists():
    load_dotenv(_env_path)

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

    # Data Sources Configuration
    MARKET_DATA_SOURCES = [
        "yahoo_finance",
        "alpha_vantage",
        "finnhub"
    ]

    # Technical Analysis Parameters
    TECHNICAL_INDICATORS = [
        "SMA", "EMA", "RSI", "MACD", "BB", "ATR"
    ]

    # Fundamental Analysis Parameters
    FUNDAMENTAL_METRICS = [
        "P/E", "P/B", "ROE", "ROA", "Debt/Equity", "Current Ratio"
    ]

    # Risk Assessment Parameters
    RISK_LEVELS = ["Low", "Medium", "High"]
    REWARD_LEVELS = ["Low", "Medium", "High"]

    # Output Configuration
    OUTPUT_FORMAT = "json"
    REPORT_TEMPLATE = "comprehensive"
