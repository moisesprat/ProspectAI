#!/usr/bin/env python3
"""
Technical Analysis Tool - Calculates technical indicators using the ta package
"""

import os
import sys
from typing import Dict, Any, List
import pandas as pd
from datetime import datetime
import yfinance as yf

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from crewai.tools import BaseTool

class TechnicalAnalysisTool(BaseTool):
    """Single tool for calculating comprehensive technical indicators using the ta package"""
    
    name: str = "calculate_technical_indicators"
    description: str = """Calculate comprehensive technical indicators for a stock using the ta package.
    
    Args:
        ticker: Stock ticker symbol to analyze
        period: Analysis period (e.g., '1y', '6mo', '3mo')
        
    Returns:
        Dictionary containing all technical indicators and analysis"""
    
    # Default values as class variables
    default_period: str = "1y"
    default_interval: str = "1d"
    
    def __init__(self):
        super().__init__()
    
    def _run(self, ticker: str, period: str = "1y") -> Dict[str, Any]:
        """Calculate comprehensive technical indicators for a stock"""
        try:
            # Get stock data
            stock_data = self._get_stock_data(ticker, period)
            if "error" in stock_data:
                return stock_data
            
            # Calculate all technical indicators
            indicators = self._calculate_all_indicators(stock_data)
            
            return {
                "ticker": ticker,
                "analysis_period": period,
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "stock_data": stock_data,
                "technical_indicators": indicators
            }
            
        except Exception as e:
            return {"error": f"Error in technical analysis for {ticker}: {str(e)}"}
    
    def _get_stock_data(self, ticker: str, period: str) -> Dict[str, Any]:
        """Fetch historical stock data"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=self.default_interval)
            
            if hist.empty:
                return {"error": f"No data found for {ticker}"}
            
            # Convert to dictionary format
            data = {
                "ticker": ticker,
                "period": period,
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
            return {"error": f"Error fetching data for {ticker}: {str(e)}"}
    
    def _calculate_all_indicators(self, stock_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate all technical indicators using the ta package"""
        try:
            # Get the actual stock data for calculations
            ticker = stock_data['ticker']
            stock = yf.Ticker(ticker)
            hist = stock.history(period=stock_data['period'], interval=self.default_interval)
            
            if hist.empty:
                return {"error": "No historical data available for calculations"}
            
            # Import ta package
            try:
                import ta
            except ImportError:
                return {"error": "ta package not installed. Please install with: pip install ta"}
            
            # Calculate momentum indicators
            momentum = self._calculate_momentum_indicators(hist, ta)
            
            # Calculate trend indicators
            trend = self._calculate_trend_indicators(hist, ta)
            
            # Calculate volatility indicators
            volatility = self._calculate_volatility_indicators(hist, ta)
            
            # Calculate volume indicators
            volume = self._calculate_volume_indicators(hist, ta)
            
            return {
                "momentum": momentum,
                "trend": trend,
                "volatility": volatility,
                "volume": volume
            }
            
        except Exception as e:
            return {"error": f"Error calculating indicators: {str(e)}"}
    
    def _calculate_momentum_indicators(self, hist: pd.DataFrame, ta) -> Dict[str, Any]:
        """Calculate momentum indicators"""
        try:
            # RSI
            rsi = ta.momentum.RSIIndicator(hist['Close']).rsi()
            
            # MACD
            macd = ta.trend.MACD(hist['Close'])
            macd_line = macd.macd()
            macd_signal = macd.macd_signal()
            macd_histogram = macd.macd_diff()
            
            # Stochastic
            stoch = ta.momentum.StochasticOscillator(hist['High'], hist['Low'], hist['Close'])
            stoch_k = stoch.stoch()
            stoch_d = stoch.stoch_signal()
            
            # Williams %R
            williams_r = ta.momentum.WilliamsRIndicator(hist['High'], hist['Low'], hist['Close']).williams_r()
            
            # CCI
            cci = ta.trend.CCIIndicator(hist['High'], hist['Low'], hist['Close']).cci()
            
            return {
                "rsi": {
                    "current": float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None,
                    "status": self._get_rsi_status(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None,
                    "description": "Relative Strength Index - measures speed and magnitude of price changes"
                },
                "macd": {
                    "macd_line": float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None,
                    "signal_line": float(macd_signal.iloc[-1]) if not pd.isna(macd_signal.iloc[-1]) else None,
                    "histogram": float(macd_histogram.iloc[-1]) if not pd.isna(macd_histogram.iloc[-1]) else None,
                    "status": self._get_macd_status(macd_line.iloc[-1], macd_signal.iloc[-1], macd_histogram.iloc[-1]),
                    "description": "Moving Average Convergence Divergence - trend following momentum indicator"
                },
                "stochastic": {
                    "k_percent": float(stoch_k.iloc[-1]) if not pd.isna(stoch_k.iloc[-1]) else None,
                    "d_percent": float(stoch_d.iloc[-1]) if not pd.isna(stoch_d.iloc[-1]) else None,
                    "status": self._get_stochastic_status(stoch_k.iloc[-1], stoch_d.iloc[-1]),
                    "description": "Stochastic Oscillator - momentum indicator comparing closing price to price range"
                },
                "williams_r": {
                    "current": float(williams_r.iloc[-1]) if not pd.isna(williams_r.iloc[-1]) else None,
                    "status": self._get_williams_r_status(williams_r.iloc[-1]) if not pd.isna(williams_r.iloc[-1]) else None,
                    "description": "Williams %R - momentum indicator measuring overbought/oversold levels"
                },
                "cci": {
                    "current": float(cci.iloc[-1]) if not pd.isna(cci.iloc[-1]) else None,
                    "status": self._get_cci_status(cci.iloc[-1]) if not pd.isna(cci.iloc[-1]) else None,
                    "description": "Commodity Channel Index - measures variation from average price"
                }
            }
            
        except Exception as e:
            return {"error": f"Error calculating momentum indicators: {str(e)}"}
    
    def _calculate_trend_indicators(self, hist: pd.DataFrame, ta) -> Dict[str, Any]:
        """Calculate trend indicators"""
        try:
            # Moving Averages
            sma_20 = ta.trend.SMAIndicator(hist['Close'], window=20).sma_indicator()
            sma_50 = ta.trend.SMAIndicator(hist['Close'], window=50).sma_indicator()
            sma_200 = ta.trend.SMAIndicator(hist['Close'], window=200).sma_indicator()
            
            # EMA
            ema_12 = ta.trend.EMAIndicator(hist['Close'], window=12).ema_indicator()
            ema_26 = ta.trend.EMAIndicator(hist['Close'], window=26).ema_indicator()
            
            # ADX
            adx = ta.trend.ADXIndicator(hist['High'], hist['Low'], hist['Close']).adx()
            
            # Parabolic SAR
            psar = ta.trend.PSARIndicator(hist['High'], hist['Low'], hist['Close']).psar()
            
            return {
                "moving_averages": {
                    "sma_20": float(sma_20.iloc[-1]) if not pd.isna(sma_20.iloc[-1]) else None,
                    "sma_50": float(sma_50.iloc[-1]) if not pd.isna(sma_50.iloc[-1]) else None,
                    "sma_200": float(sma_200.iloc[-1]) if not pd.isna(sma_200.iloc[-1]) else None,
                    "status": self._get_ma_status(sma_20.iloc[-1], sma_50.iloc[-1], sma_200.iloc[-1]),
                    "description": "Simple Moving Averages - trend identification and support/resistance levels"
                },
                "exponential_moving_averages": {
                    "ema_12": float(ema_12.iloc[-1]) if not pd.isna(ema_12.iloc[-1]) else None,
                    "ema_26": float(ema_26.iloc[-1]) if not pd.isna(ema_26.iloc[-1]) else None,
                    "status": self._get_ema_status(ema_12.iloc[-1], ema_26.iloc[-1]),
                    "description": "Exponential Moving Averages - weighted moving averages for trend analysis"
                },
                "adx": {
                    "current": float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else None,
                    "status": self._get_adx_status(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else None,
                    "description": "Average Directional Index - measures trend strength"
                },
                "parabolic_sar": {
                    "current": float(psar.iloc[-1]) if not pd.isna(psar.iloc[-1]) else None,
                    "status": self._get_psar_status(hist['Close'].iloc[-1], psar.iloc[-1]),
                    "description": "Parabolic SAR - trend following indicator and stop-loss tool"
                }
            }
            
        except Exception as e:
            return {"error": f"Error calculating trend indicators: {str(e)}"}
    
    def _calculate_volatility_indicators(self, hist: pd.DataFrame, ta) -> Dict[str, Any]:
        """Calculate volatility indicators"""
        try:
            # Bollinger Bands
            bb = ta.volatility.BollingerBands(hist['Close'])
            bb_upper = bb.bollinger_hband()
            bb_middle = bb.bollinger_mavg()
            bb_lower = bb.bollinger_lband()
            bb_width = bb.bollinger_wband()
            
            # ATR
            atr = ta.volatility.AverageTrueRange(hist['High'], hist['Low'], hist['Close']).average_true_range()
            
            # Standard Deviation
            std_dev = hist['Close'].std()
            
            return {
                "bollinger_bands": {
                    "upper_band": float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else None,
                    "middle_band": float(bb_middle.iloc[-1]) if not pd.isna(bb_middle.iloc[-1]) else None,
                    "lower_band": float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else None,
                    "bandwidth": float(bb_width.iloc[-1]) if not pd.isna(bb_width.iloc[-1]) else None,
                    "status": self._get_bollinger_status(hist['Close'].iloc[-1], bb_upper.iloc[-1], bb_lower.iloc[-1]),
                    "description": "Bollinger Bands - volatility indicator showing price channels"
                },
                "atr": {
                    "current": float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else None,
                    "status": self._get_atr_status(atr.iloc[-1]),
                    "description": "Average True Range - measures market volatility"
                },
                "standard_deviation": {
                    "current": float(std_dev),
                    "description": "Standard deviation of closing prices - volatility measure"
                }
            }
            
        except Exception as e:
            return {"error": f"Error calculating volatility indicators: {str(e)}"}
    
    def _calculate_volume_indicators(self, hist: pd.DataFrame, ta) -> Dict[str, Any]:
        """Calculate volume indicators"""
        try:
            # Volume SMA
            volume_sma = ta.volume.VolumeSMAIndicator(hist['Close'], hist['Volume']).volume_sma()
            
            # On Balance Volume
            obv = ta.volume.OnBalanceVolumeIndicator(hist['Close'], hist['Volume']).on_balance_volume()
            
            # Volume Weighted Average Price
            vwap = ta.volume.VolumeWeightedAveragePrice(hist['High'], hist['Low'], hist['Close'], hist['Volume']).volume_weighted_average_price()
            
            return {
                "volume_sma": {
                    "current": float(volume_sma.iloc[-1]) if not pd.isna(volume_sma.iloc[-1]) else None,
                    "description": "Volume Simple Moving Average - average volume over time"
                },
                "obv": {
                    "current": float(obv.iloc[-1]) if not pd.isna(obv.iloc[-1]) else None,
                    "description": "On Balance Volume - cumulative volume indicator"
                },
                "vwap": {
                    "current": float(vwap.iloc[-1]) if not pd.isna(vwap.iloc[-1]) else None,
                    "description": "Volume Weighted Average Price - price weighted by volume"
                }
            }
            
        except Exception as e:
            return {"error": f"Error calculating volume indicators: {str(e)}"}
    
    # Status interpretation methods
    def _get_rsi_status(self, rsi: float) -> str:
        """Get RSI status"""
        if pd.isna(rsi):
            return "Insufficient Data"
        if rsi > 70:
            return "Overbought"
        elif rsi < 30:
            return "Oversold"
        else:
            return "Neutral"
    
    def _get_macd_status(self, macd_line: float, signal_line: float, histogram: float) -> str:
        """Get MACD status"""
        if pd.isna(macd_line) or pd.isna(signal_line):
            return "Insufficient Data"
        
        if macd_line > signal_line and histogram > 0:
            return "Bullish"
        elif macd_line < signal_line and histogram < 0:
            return "Bearish"
        else:
            return "Mixed"
    
    def _get_stochastic_status(self, k: float, d: float) -> str:
        """Get Stochastic status"""
        if pd.isna(k) or pd.isna(d):
            return "Insufficient Data"
        
        if k > 80 and d > 80:
            return "Overbought"
        elif k < 20 and d < 20:
            return "Oversold"
        else:
            return "Neutral"
    
    def _get_williams_r_status(self, williams_r: float) -> str:
        """Get Williams %R status"""
        if pd.isna(williams_r):
            return "Insufficient Data"
        if williams_r < -80:
            return "Oversold"
        elif williams_r > -20:
            return "Overbought"
        else:
            return "Neutral"
    
    def _get_cci_status(self, cci: float) -> str:
        """Get CCI status"""
        if pd.isna(cci):
            return "Insufficient Data"
        if cci > 100:
            return "Overbought"
        elif cci < -100:
            return "Oversold"
        else:
            return "Neutral"
    
    def _get_ma_status(self, sma_20: float, sma_50: float, sma_200: float) -> str:
        """Get Moving Average status"""
        if pd.isna(sma_20) or pd.isna(sma_50) or pd.isna(sma_200):
            return "Insufficient Data"
        
        if sma_20 > sma_50 > sma_200:
            return "Strong Uptrend"
        elif sma_20 < sma_50 < sma_200:
            return "Strong Downtrend"
        elif sma_20 > sma_50:
            return "Uptrend"
        elif sma_20 < sma_50:
            return "Downtrend"
        else:
            return "Sideways"
    
    def _get_ema_status(self, ema_12: float, ema_26: float) -> str:
        """Get EMA status"""
        if pd.isna(ema_12) or pd.isna(ema_26):
            return "Insufficient Data"
        
        if ema_12 > ema_26:
            return "Bullish"
        else:
            return "Bearish"
    
    def _get_adx_status(self, adx: float) -> str:
        """Get ADX status"""
        if pd.isna(adx):
            return "Insufficient Data"
        if adx > 25:
            return "Strong Trend"
        elif adx > 20:
            return "Moderate Trend"
        else:
            return "Weak Trend"
    
    def _get_psar_status(self, current_price: float, psar: float) -> str:
        """Get Parabolic SAR status"""
        if pd.isna(psar):
            return "Insufficient Data"
        
        if current_price > psar:
            return "Bullish"
        else:
            return "Bearish"
    
    def _get_bollinger_status(self, current_price: float, upper: float, lower: float) -> str:
        """Get Bollinger Bands status"""
        if pd.isna(upper) or pd.isna(lower):
            return "Insufficient Data"
        
        if current_price > upper:
            return "Overbought"
        elif current_price < lower:
            return "Oversold"
        else:
            return "Normal Range"
    
    def _get_atr_status(self, atr: float) -> str:
        """Get ATR status"""
        if pd.isna(atr):
            return "Insufficient Data"
        
        # This is a simplified ATR status - you could make it more sophisticated
        return "Normal Volatility"
