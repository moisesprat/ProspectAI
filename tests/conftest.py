import pytest
from utils import yfinance_cache


@pytest.fixture(autouse=True)
def _clear_yfinance_cache():
    """Ensure the module-level yfinance cache is empty before every test."""
    yfinance_cache.clear()
