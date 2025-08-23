import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration class for ProspectAI"""
    
    @property
    def MODEL_PROVIDER(self):
        """Get model provider from environment"""
        return os.getenv("MODEL_PROVIDER", "openai")
    
    @property
    def OPENAI_API_KEY(self):
        """Get OpenAI API key from environment"""
        return os.getenv("OPENAI_API_KEY")
    
    @property
    def OPENAI_MODEL(self):
        """Get OpenAI model from environment"""
        return os.getenv("OPENAI_MODEL", "gpt-4")
    
    @property
    def OLLAMA_BASE_URL(self):
        """Get Ollama base URL from environment"""
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    @property
    def OLLAMA_MODEL(self):
        """Get Ollama model from environment"""
        return os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    
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
