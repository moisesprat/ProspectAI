#!/usr/bin/env python3
"""
Technical Analysis Tool - Calculates comprehensive technical indicators for stocks
"""

import os
import sys
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# Pydantic models for tool arguments
class StockInput(BaseModel):
    ticker: str = Field(description="Stock ticker symbol to analyze")

class TechnicalIndicatorsInput(BaseModel):
    ticker: str = Field(description="Stock ticker symbol")
    period: str = Field(description="Analysis period (e.g., '1y', '6mo', '3mo')", default="1y")

# Tool classes that inherit from BaseTool
class CalculateTechnicalIndicatorsTool(BaseTool):
    name: str = "calculate_technical_indicators"
    description: str = """Calculate comprehensive technical indicators for a stock.
    
    Args:
        ticker: Stock ticker symbol to analyze
        period: Analysis period (e.g., '1y', '6mo', '3mo')
        
    Returns:
        Dictionary containing all technical indicators and analysis"""
    
    def _run(self, ticker: str, period: str = "1y") -> Dict[str, Any]:
        # Create a temporary instance to access the methods
        tech_tool = TechnicalAnalysisTool()
        return tech_tool._calculate_comprehensive_indicators(ticker, period)

class GetStockDataTool(BaseTool):
    name: str = "get_stock_data"
    description: str = """Fetch historical stock data for analysis.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Historical price data for the stock"""
    
    def _run(self, ticker: str) -> Dict[str, Any]:
        # Create a temporary instance to access the methods
        tech_tool = TechnicalAnalysisTool()
        return tech_tool._get_stock_data(ticker)

class CalculateMomentumIndicatorsTool(BaseTool):
    name: str = "calculate_momentum_indicators"
    description: str = """Calculate momentum-based technical indicators.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Momentum indicators including RSI, MACD, Stochastic, etc."""
    
    def _run(self, ticker: str) -> Dict[str, Any]:
        # Create a temporary instance to access the methods
        tech_tool = TechnicalAnalysisTool()
        return tech_tool._calculate_momentum_indicators(ticker)

class CalculateTrendIndicatorsTool(BaseTool):
    name: str = "calculate_trend_indicators"
    description: str = """Calculate trend-based technical indicators.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Trend indicators including moving averages, ADX, etc."""
    
    def _run(self, ticker: str) -> Dict[str, Any]:
        # Create a temporary instance to access the methods
        tech_tool = TechnicalAnalysisTool()
        return tech_tool._calculate_trend_indicators(ticker)

class CalculateVolatilityIndicatorsTool(BaseTool):
    name: str = "calculate_volatility_indicators"
    description: str = """Calculate volatility-based technical indicators.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Volatility indicators including Bollinger Bands, ATR, etc."""
    
    def _run(self, ticker: str) -> Dict[str, Any]:
        # Create a temporary instance to access the methods
        tech_tool = TechnicalAnalysisTool()
        return tech_tool._calculate_volatility_indicators(ticker)

class TechnicalAnalysisTool:
    """Tool for calculating comprehensive technical indicators"""
    
    def __init__(self):
        self.default_period = "1y"
        self.default_interval = "1d"
    
    def get_tools(self) -> List[BaseTool]:
        """Get all technical analysis tools"""
        return [
            CalculateTechnicalIndicatorsTool(),
            GetStockDataTool(),
            CalculateMomentumIndicatorsTool(),
            CalculateTrendIndicatorsTool(),
            CalculateVolatilityIndicatorsTool()
        ]
    

    
    def _get_stock_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch historical stock data"""
        try:
            # Get stock data
            stock = yf.Ticker(ticker)
            hist = stock.history(period=self.default_period, interval=self.default_interval)
            
            if hist.empty:
                return {
                    "error": f"No data found for {ticker}",
                    "ticker": ticker
                }
            
            # Convert to dictionary format
            data = {
                "ticker": ticker,
                "period": self.default_period,
                "data_points": len(hist),
                "start_date": hist.index[0].strftime("%Y-%m-%d"),
                "end_date": hist.index[-1].strftime("%Y-%m-%d"),
                "current_price": float(hist['Close'].iloc[-1]),
                "price_change": float(hist['Close'].iloc[-1] - hist['Close'].iloc[-2]),
                "price_change_pct": float(((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100),
                "high": float(hist['High'].max()),
                "low": float(hist['Low'].min()),
                "volume": int(hist['Volume'].iloc[-1]),
                "avg_volume": int(hist['Volume'].mean())
            }
            
            return data
            
        except Exception as e:
            return {
                "error": f"Error fetching data for {ticker}: {str(e)}",
                "ticker": ticker
            }
    
    def _calculate_momentum_indicators(self, ticker: str) -> Dict[str, Any]:
        """Calculate momentum indicators"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=self.default_period, interval=self.default_interval)
            
            if hist.empty:
                return {"error": f"No data found for {ticker}"}
            
            close_prices = hist['Close'].values
            
            # RSI (Relative Strength Index)
            rsi = self._calculate_rsi(close_prices)
            
            # MACD (Moving Average Convergence Divergence)
            macd_data = self._calculate_macd(close_prices)
            
            # Stochastic Oscillator
            stoch_data = self._calculate_stochastic(hist)
            
            # Williams %R
            williams_r = self._calculate_williams_r(hist)
            
            # CCI (Commodity Channel Index)
            cci = self._calculate_cci(hist)
            
            return {
                "ticker": ticker,
                "momentum_indicators": {
                    "rsi": {
                        "current": float(rsi[-1]) if len(rsi) > 0 else None,
                        "status": self._get_rsi_status(rsi[-1]) if len(rsi) > 0 else None,
                        "description": "Relative Strength Index - measures speed and magnitude of price changes"
                    },
                    "macd": {
                        "macd_line": float(macd_data['macd'][-1]) if len(macd_data['macd']) > 0 else None,
                        "signal_line": float(macd_data['signal'][-1]) if len(macd_data['signal']) > 0 else None,
                        "histogram": float(macd_data['histogram'][-1]) if len(macd_data['histogram']) > 0 else None,
                        "status": self._get_macd_status(macd_data),
                        "description": "Moving Average Convergence Divergence - trend following momentum indicator"
                    },
                    "stochastic": {
                        "k_percent": float(stoch_data['k'][-1]) if len(stoch_data['k']) > 0 else None,
                        "d_percent": float(stoch_data['d'][-1]) if len(stoch_data['d']) > 0 else None,
                        "status": self._get_stochastic_status(stoch_data),
                        "description": "Stochastic Oscillator - momentum indicator comparing closing price to price range"
                    },
                    "williams_r": {
                        "current": float(williams_r[-1]) if len(williams_r) > 0 else None,
                        "status": self._get_williams_r_status(williams_r[-1]) if len(williams_r) > 0 else None,
                        "description": "Williams %R - momentum indicator measuring overbought/oversold levels"
                    },
                    "cci": {
                        "current": float(cci[-1]) if len(cci) > 0 else None,
                        "status": self._get_cci_status(cci[-1]) if len(cci) > 0 else None,
                        "description": "Commodity Channel Index - measures variation from average price"
                    }
                }
            }
            
        except Exception as e:
            return {"error": f"Error calculating momentum indicators for {ticker}: {str(e)}"}
    
    def _calculate_trend_indicators(self, ticker: str) -> Dict[str, Any]:
        """Calculate trend indicators"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=self.default_period, interval=self.default_interval)
            
            if hist.empty:
                return {"error": f"No data found for {ticker}"}
            
            close_prices = hist['Close'].values
            
            # Moving Averages
            sma_20 = self._calculate_sma(close_prices, 20)
            sma_50 = self._calculate_sma(close_prices, 50)
            sma_200 = self._calculate_sma(close_prices, 200)
            
            # EMA (Exponential Moving Average)
            ema_12 = self._calculate_ema(close_prices, 12)
            ema_26 = self._calculate_ema(close_prices, 26)
            
            # ADX (Average Directional Index)
            adx = self._calculate_adx(hist)
            
            # Parabolic SAR
            psar = self._calculate_parabolic_sar(hist)
            
            return {
                "ticker": ticker,
                "trend_indicators": {
                    "moving_averages": {
                        "sma_20": float(sma_20[-1]) if len(sma_20) > 0 else None,
                        "sma_50": float(sma_50[-1]) if len(sma_50) > 0 else None,
                        "sma_200": float(sma_200[-1]) if len(sma_200) > 0 else None,
                        "status": self._get_ma_status(sma_20, sma_50, sma_200),
                        "description": "Simple Moving Averages - trend identification and support/resistance levels"
                    },
                    "exponential_moving_averages": {
                        "ema_12": float(ema_12[-1]) if len(ema_12) > 0 else None,
                        "ema_26": float(ema_26[-1]) if len(ema_26) > 0 else None,
                        "status": self._get_ema_status(ema_12, ema_26),
                        "description": "Exponential Moving Averages - weighted moving averages for trend analysis"
                    },
                    "adx": {
                        "current": float(adx[-1]) if len(adx) > 0 else None,
                        "status": self._get_adx_status(adx[-1]) if len(adx) > 0 else None,
                        "description": "Average Directional Index - measures trend strength"
                    },
                    "parabolic_sar": {
                        "current": float(psar[-1]) if len(psar) > 0 else None,
                        "status": self._get_psar_status(hist, psar),
                        "description": "Parabolic SAR - trend following indicator and stop-loss tool"
                    }
                }
            }
            
        except Exception as e:
            return {"error": f"Error calculating trend indicators for {ticker}: {str(e)}"}
    
    def _calculate_volatility_indicators(self, ticker: str) -> Dict[str, Any]:
        """Calculate volatility indicators"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=self.default_period, interval=self.default_interval)
            
            if hist.empty:
                return {"error": f"No data found for {ticker}"}
            
            # Bollinger Bands
            bb_data = self._calculate_bollinger_bands(hist)
            
            # ATR (Average True Range)
            atr = self._calculate_atr(hist)
            
            # Standard Deviation
            std_dev = self._calculate_standard_deviation(hist['Close'])
            
            # Volatility Ratio
            volatility_ratio = self._calculate_volatility_ratio(hist)
            
            return {
                "ticker": ticker,
                "volatility_indicators": {
                    "bollinger_bands": {
                        "upper_band": float(bb_data['upper'][-1]) if len(bb_data['upper']) > 0 else None,
                        "middle_band": float(bb_data['middle'][-1]) if len(bb_data['middle']) > 0 else None,
                        "lower_band": float(bb_data['lower'][-1]) if len(bb_data['lower']) > 0 else None,
                        "bandwidth": float(bb_data['bandwidth'][-1]) if len(bb_data['bandwidth']) > 0 else None,
                        "status": self._get_bollinger_status(hist, bb_data),
                        "description": "Bollinger Bands - volatility indicator showing price channels"
                    },
                    "atr": {
                        "current": float(atr[-1]) if len(atr) > 0 else None,
                        "status": self._get_atr_status(atr),
                        "description": "Average True Range - measures market volatility"
                    },
                    "standard_deviation": {
                        "current": float(std_dev),
                        "description": "Standard deviation of closing prices - volatility measure"
                    },
                    "volatility_ratio": {
                        "current": float(volatility_ratio),
                        "status": self._get_volatility_status(volatility_ratio),
                        "description": "Ratio of current volatility to historical average"
                    }
                }
            }
            
        except Exception as e:
            return {"error": f"Error calculating volatility indicators for {ticker}: {str(e)}"}
    
    def _calculate_comprehensive_indicators(self, ticker: str, period: str = "1y") -> Dict[str, Any]:
        """Calculate all technical indicators comprehensively"""
        try:
            # Get basic stock data
            stock_data = self._get_stock_data(ticker)
            if "error" in stock_data:
                return stock_data
            
            # Calculate all indicator categories
            momentum = self._calculate_momentum_indicators(ticker)
            trend = self._calculate_trend_indicators(ticker)
            volatility = self._calculate_volatility_indicators(ticker)
            
            # Combine all data
            comprehensive_analysis = {
                "ticker": ticker,
                "analysis_period": period,
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "stock_data": stock_data,
                "technical_indicators": {
                    "momentum": momentum.get("momentum_indicators", {}),
                    "trend": trend.get("trend_indicators", {}),
                    "volatility": volatility.get("volatility_indicators", {})
                },
                "overall_technical_score": self._calculate_overall_technical_score(momentum, trend, volatility),
                "technical_summary": self._generate_technical_summary(momentum, trend, volatility, stock_data)
            }
            
            return comprehensive_analysis
            
        except Exception as e:
            return {"error": f"Error in comprehensive technical analysis for {ticker}: {str(e)}"}
    
    # Helper methods for calculating individual indicators
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return np.array([])
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.convolve(gains, np.ones(period)/period, mode='valid')
        avg_losses = np.convolve(losses, np.ones(period)/period, mode='valid')
        
        rs = avg_gains / (avg_losses + 1e-10)  # Avoid division by zero
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, np.ndarray]:
        """Calculate MACD"""
        if len(prices) < slow:
            return {"macd": np.array([]), "signal": np.array([]), "histogram": np.array([])}
        
        ema_fast = self._calculate_ema(prices, fast)
        ema_slow = self._calculate_ema(prices, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self._calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return np.array([])
        
        return np.convolve(prices, np.ones(period)/period, mode='valid')
    
    def _calculate_ema(self, prices: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return np.array([])
        
        alpha = 2 / (period + 1)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _calculate_stochastic(self, hist: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict[str, np.ndarray]:
        """Calculate Stochastic Oscillator"""
        if len(hist) < k_period:
            return {"k": np.array([]), "d": np.array([])}
        
        high = hist['High'].values
        low = hist['Low'].values
        close = hist['Close'].values
        
        k_percent = np.zeros(len(hist))
        for i in range(k_period-1, len(hist)):
            highest_high = np.max(high[i-k_period+1:i+1])
            lowest_low = np.min(low[i-k_period+1:i+1])
            k_percent[i] = 100 * (close[i] - lowest_low) / (highest_high - lowest_low + 1e-10)
        
        d_percent = self._calculate_sma(k_percent, d_period)
        
        return {"k": k_percent, "d": d_percent}
    
    def _calculate_williams_r(self, hist: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calculate Williams %R"""
        if len(hist) < period:
            return np.array([])
        
        high = hist['High'].values
        low = hist['Low'].values
        close = hist['Close'].values
        
        williams_r = np.zeros(len(hist))
        for i in range(period-1, len(hist)):
            highest_high = np.max(high[i-period+1:i+1])
            lowest_low = np.min(low[i-period+1:i+1])
            williams_r[i] = -100 * (highest_high - close[i]) / (highest_high - lowest_low + 1e-10)
        
        return williams_r
    
    def _calculate_cci(self, hist: pd.DataFrame, period: int = 20) -> np.ndarray:
        """Calculate Commodity Channel Index"""
        if len(hist) < period:
            return np.array([])
        
        high = hist['High'].values
        low = hist['Low'].values
        close = hist['Close'].values
        
        typical_price = (high + low + close) / 3
        sma_tp = self._calculate_sma(typical_price, period)
        
        cci = np.zeros(len(hist))
        for i in range(period-1, len(hist)):
            mean_deviation = np.mean(np.abs(typical_price[i-period+1:i+1] - sma_tp[i-period+1]))
            cci[i] = (typical_price[i] - sma_tp[i-period+1]) / (0.015 * mean_deviation + 1e-10)
        
        return cci
    
    def _calculate_adx(self, hist: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calculate Average Directional Index"""
        if len(hist) < period:
            return np.array([])
        
        high = hist['High'].values
        low = hist['Low'].values
        close = hist['Close'].values
        
        # Simplified ADX calculation
        adx = np.zeros(len(hist))
        for i in range(1, len(hist)):
            tr = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
            adx[i] = tr / (high[i] - low[i] + 1e-10) * 100
        
        return adx
    
    def _calculate_parabolic_sar(self, hist: pd.DataFrame, acceleration: float = 0.02, maximum: float = 0.2) -> np.ndarray:
        """Calculate Parabolic SAR"""
        if len(hist) < 2:
            return np.array([])
        
        high = hist['High'].values
        low = hist['Low'].values
        
        psar = np.zeros(len(hist))
        psar[0] = low[0]
        
        for i in range(1, len(hist)):
            if high[i] > high[i-1]:
                psar[i] = psar[i-1] + acceleration * (high[i] - psar[i-1])
            else:
                psar[i] = psar[i-1] - acceleration * (psar[i-1] - low[i])
        
        return psar
    
    def _calculate_bollinger_bands(self, hist: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Dict[str, np.ndarray]:
        """Calculate Bollinger Bands"""
        if len(hist) < period:
            return {"upper": np.array([]), "middle": np.array([]), "lower": np.array([]), "bandwidth": np.array([])}
        
        close = hist['Close'].values
        sma = self._calculate_sma(close, period)
        
        upper = np.zeros(len(hist))
        lower = np.zeros(len(hist))
        bandwidth = np.zeros(len(hist))
        
        for i in range(period-1, len(hist)):
            std = np.std(close[i-period+1:i+1])
            upper[i] = sma[i-period+1] + (std_dev * std)
            lower[i] = sma[i-period+1] - (std_dev * std)
            bandwidth[i] = (upper[i] - lower[i]) / sma[i-period+1]
        
        return {
            "upper": upper,
            "middle": sma,
            "lower": lower,
            "bandwidth": bandwidth
        }
    
    def _calculate_atr(self, hist: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Calculate Average True Range"""
        if len(hist) < period:
            return np.array([])
        
        high = hist['High'].values
        low = hist['Low'].values
        close = hist['Close'].values
        
        tr = np.zeros(len(hist))
        for i in range(1, len(hist)):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        
        atr = self._calculate_sma(tr, period)
        return atr
    
    def _calculate_standard_deviation(self, prices: pd.Series) -> float:
        """Calculate standard deviation of prices"""
        return float(prices.std())
    
    def _calculate_volatility_ratio(self, hist: pd.DataFrame) -> float:
        """Calculate volatility ratio (current vs historical)"""
        if len(hist) < 20:
            return 1.0
        
        recent_vol = hist['Close'].tail(5).std()
        historical_vol = hist['Close'].tail(20).std()
        
        return float(recent_vol / (historical_vol + 1e-10))
    
    # Status interpretation methods
    def _get_rsi_status(self, rsi: float) -> str:
        """Get RSI status"""
        if rsi > 70:
            return "Overbought"
        elif rsi < 30:
            return "Oversold"
        else:
            return "Neutral"
    
    def _get_macd_status(self, macd_data: Dict[str, np.ndarray]) -> str:
        """Get MACD status"""
        if len(macd_data['macd']) == 0 or len(macd_data['signal']) == 0:
            return "Insufficient Data"
        
        macd_line = macd_data['macd'][-1]
        signal_line = macd_data['signal'][-1]
        histogram = macd_data['histogram'][-1]
        
        if macd_line > signal_line and histogram > 0:
            return "Bullish"
        elif macd_line < signal_line and histogram < 0:
            return "Bearish"
        else:
            return "Mixed"
    
    def _get_stochastic_status(self, stoch_data: Dict[str, np.ndarray]) -> str:
        """Get Stochastic status"""
        if len(stoch_data['k']) == 0:
            return "Insufficient Data"
        
        k = stoch_data['k'][-1]
        d = stoch_data['d'][-1]
        
        if k > 80 and d > 80:
            return "Overbought"
        elif k < 20 and d < 20:
            return "Oversold"
        else:
            return "Neutral"
    
    def _get_williams_r_status(self, williams_r: float) -> str:
        """Get Williams %R status"""
        if williams_r < -80:
            return "Oversold"
        elif williams_r > -20:
            return "Overbought"
        else:
            return "Neutral"
    
    def _get_cci_status(self, cci: float) -> str:
        """Get CCI status"""
        if cci > 100:
            return "Overbought"
        elif cci < -100:
            return "Oversold"
        else:
            return "Neutral"
    
    def _get_ma_status(self, sma_20: np.ndarray, sma_50: np.ndarray, sma_200: np.ndarray) -> str:
        """Get Moving Average status"""
        if len(sma_20) == 0 or len(sma_50) == 0 or len(sma_200) == 0:
            return "Insufficient Data"
        
        current_price = sma_20[-1]
        ma_20 = sma_20[-1]
        ma_50 = sma_50[-1]
        ma_200 = sma_200[-1]
        
        if current_price > ma_20 > ma_50 > ma_200:
            return "Strong Uptrend"
        elif current_price < ma_20 < ma_50 < ma_200:
            return "Strong Downtrend"
        elif current_price > ma_20 and ma_20 > ma_50:
            return "Uptrend"
        elif current_price < ma_20 and ma_20 < ma_50:
            return "Downtrend"
        else:
            return "Sideways"
    
    def _get_ema_status(self, ema_12: np.ndarray, ema_26: np.ndarray) -> str:
        """Get EMA status"""
        if len(ema_12) == 0 or len(ema_26) == 0:
            return "Insufficient Data"
        
        if ema_12[-1] > ema_26[-1]:
            return "Bullish"
        else:
            return "Bearish"
    
    def _get_adx_status(self, adx: float) -> str:
        """Get ADX status"""
        if adx > 25:
            return "Strong Trend"
        elif adx > 20:
            return "Moderate Trend"
        else:
            return "Weak Trend"
    
    def _get_psar_status(self, hist: pd.DataFrame, psar: np.ndarray) -> str:
        """Get Parabolic SAR status"""
        if len(psar) == 0:
            return "Insufficient Data"
        
        current_price = hist['Close'].iloc[-1]
        current_psar = psar[-1]
        
        if current_price > current_psar:
            return "Bullish"
        else:
            return "Bearish"
    
    def _get_bollinger_status(self, hist: pd.DataFrame, bb_data: Dict[str, np.ndarray]) -> str:
        """Get Bollinger Bands status"""
        if len(bb_data['upper']) == 0:
            return "Insufficient Data"
        
        current_price = hist['Close'].iloc[-1]
        upper = bb_data['upper'][-1]
        lower = bb_data['lower'][-1]
        
        if current_price > upper:
            return "Overbought"
        elif current_price < lower:
            return "Oversold"
        else:
            return "Normal Range"
    
    def _get_atr_status(self, atr: np.ndarray) -> str:
        """Get ATR status"""
        if len(atr) == 0:
            return "Insufficient Data"
        
        current_atr = atr[-1]
        avg_atr = np.mean(atr)
        
        if current_atr > avg_atr * 1.5:
            return "High Volatility"
        elif current_atr < avg_atr * 0.5:
            return "Low Volatility"
        else:
            return "Normal Volatility"
    
    def _get_volatility_status(self, ratio: float) -> str:
        """Get volatility status"""
        if ratio > 1.5:
            return "High Volatility"
        elif ratio < 0.5:
            return "Low Volatility"
        else:
            return "Normal Volatility"
    
    def _calculate_overall_technical_score(self, momentum: Dict, trend: Dict, volatility: Dict) -> Dict[str, Any]:
        """Calculate overall technical score"""
        try:
            # Extract key indicators for scoring
            momentum_data = momentum.get("momentum_indicators", {})
            trend_data = trend.get("trend_indicators", {})
            volatility_data = volatility.get("volatility_indicators", {})
            
            score = 0
            max_score = 0
            details = {}
            
            # RSI scoring
            if momentum_data.get("rsi", {}).get("current"):
                rsi = momentum_data["rsi"]["current"]
                if 30 <= rsi <= 70:
                    score += 20
                    details["rsi"] = "Neutral (20 points)"
                elif rsi < 30:
                    score += 15
                    details["rsi"] = "Oversold (15 points)"
                else:
                    score += 10
                    details["rsi"] = "Overbought (10 points)"
                max_score += 20
            
            # MACD scoring
            if momentum_data.get("macd", {}).get("status"):
                macd_status = momentum_data["macd"]["status"]
                if macd_status == "Bullish":
                    score += 20
                    details["macd"] = "Bullish (20 points)"
                elif macd_status == "Bearish":
                    score += 5
                    details["macd"] = "Bearish (5 points)"
                else:
                    score += 10
                    details["macd"] = "Mixed (10 points)"
                max_score += 20
            
            # Moving Average scoring
            if trend_data.get("moving_averages", {}).get("status"):
                ma_status = trend_data["moving_averages"]["status"]
                if "Uptrend" in ma_status:
                    score += 25
                    details["moving_averages"] = f"{ma_status} (25 points)"
                elif "Downtrend" in ma_status:
                    score += 5
                    details["moving_averages"] = f"{ma_status} (5 points)"
                else:
                    score += 15
                    details["moving_averages"] = f"{ma_status} (15 points)"
                max_score += 25
            
            # Bollinger Bands scoring
            if volatility_data.get("bollinger_bands", {}).get("status"):
                bb_status = volatility_data["bollinger_bands"]["status"]
                if bb_status == "Normal Range":
                    score += 15
                    details["bollinger_bands"] = "Normal Range (15 points)"
                elif bb_status == "Oversold":
                    score += 20
                    details["bollinger_bands"] = "Oversold (20 points)"
                else:
                    score += 5
                    details["bollinger_bands"] = "Overbought (5 points)"
                max_score += 20
            
            # Overall trend scoring
            if trend_data.get("exponential_moving_averages", {}).get("status"):
                ema_status = trend_data["exponential_moving_averages"]["status"]
                if ema_status == "Bullish":
                    score += 20
                    details["ema"] = "Bullish (20 points)"
                else:
                    score += 5
                    details["ema"] = "Bearish (5 points)"
                max_score += 20
            
            # Calculate percentage and grade
            percentage = (score / max_score * 100) if max_score > 0 else 0
            
            if percentage >= 80:
                grade = "A (Strong Buy)"
                recommendation = "Strong Buy"
            elif percentage >= 60:
                grade = "B (Buy)"
                recommendation = "Buy"
            elif percentage >= 40:
                grade = "C (Hold)"
                recommendation = "Hold"
            elif percentage >= 20:
                grade = "D (Sell)"
                recommendation = "Sell"
            else:
                grade = "F (Strong Sell)"
                recommendation = "Strong Sell"
            
            return {
                "total_score": score,
                "max_possible_score": max_score,
                "percentage": round(percentage, 2),
                "grade": grade,
                "recommendation": recommendation,
                "score_details": details
            }
            
        except Exception as e:
            return {
                "error": f"Error calculating technical score: {str(e)}",
                "total_score": 0,
                "max_possible_score": 100,
                "percentage": 0,
                "grade": "N/A",
                "recommendation": "Insufficient Data"
            }
    
    def _generate_technical_summary(self, momentum: Dict, trend: Dict, volatility: Dict, stock_data: Dict) -> str:
        """Generate a brief technical summary"""
        try:
            summary_parts = []
            
            # Stock performance
            if stock_data.get("price_change_pct"):
                change_pct = stock_data["price_change_pct"]
                if change_pct > 0:
                    summary_parts.append(f"Stock is up {change_pct:.2f}% today")
                else:
                    summary_parts.append(f"Stock is down {abs(change_pct):.2f}% today")
            
            # Key indicators
            if momentum.get("momentum_indicators", {}).get("rsi", {}).get("status"):
                summary_parts.append(f"RSI: {momentum['momentum_indicators']['rsi']['status']}")
            
            if momentum.get("momentum_indicators", {}).get("macd", {}).get("status"):
                summary_parts.append(f"MACD: {momentum['momentum_indicators']['macd']['status']}")
            
            if trend.get("trend_indicators", {}).get("moving_averages", {}).get("status"):
                summary_parts.append(f"Trend: {trend['trend_indicators']['moving_averages']['status']}")
            
            if volatility.get("volatility_indicators", {}).get("bollinger_bands", {}).get("status"):
                summary_parts.append(f"Volatility: {volatility['volatility_indicators']['bollinger_bands']['status']}")
            
            return " | ".join(summary_parts) if summary_parts else "Insufficient data for technical summary"
            
        except Exception as e:
            return f"Error generating technical summary: {str(e)}"
