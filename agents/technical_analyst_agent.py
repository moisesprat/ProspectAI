#!/usr/bin/env python3
"""
Technical Analyst Agent - Analyzes technical indicators and generates momentum analysis
"""

import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from agents.base_agent import BaseAgent
from utils.technical_analysis_tool import TechnicalAnalysisTool
from config.config import Config
from crewai import Agent

class TechnicalAnalystAgent(BaseAgent):
    """Technical Analyst Agent that analyzes stock momentum using technical indicators"""
    
    def __init__(self):
        super().__init__(
            name="Technical Analyst Agent",
            role="Technical momentum analyst specializing in chart patterns and indicators",
            goal="Analyze technical indicators to assess stock momentum and provide comprehensive technical analysis for investment decisions",
            backstory="""You are an expert technical analyst with over 15 years of experience in 
            analyzing stock market momentum using advanced technical indicators. You excel at interpreting 
            RSI, MACD, moving averages, Bollinger Bands, and other technical tools to identify trend 
            strength, momentum shifts, and potential entry/exit points. Your analysis combines quantitative 
            data with market psychology to provide actionable insights for traders and investors."""
        )
        
        # Initialize technical analysis tools
        self.technical_tools = TechnicalAnalysisTool()
        
        # Get LLM for reasoning
        self.llm = self._get_llm()
    
    def create_agent(self) -> Agent:
        """Create and return a CrewAI Agent instance"""
        from crewai import Agent
        
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            tools=self.technical_tools.get_tools(),
            verbose=True,
            allow_delegation=False
        )
    
    def execute_task(self, market_analyst_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute technical analysis task based on Market Analyst output
        
        Args:
            market_analyst_output: Output from Market Analyst Agent containing candidate stocks
            
        Returns:
            Dictionary with technical analysis for each stock including momentum analysis
        """
        try:
            print(f"🔧 Technical Analyst Agent: Starting technical analysis for {len(market_analyst_output.get('candidate_stocks', []))} stocks")
            
            # Extract candidate stocks from Market Analyst output
            candidate_stocks = market_analyst_output.get('candidate_stocks', [])
            sector = market_analyst_output.get('sector', 'Unknown')
            
            if not candidate_stocks:
                return {
                    "sector": sector,
                    "technical_analysis": [],
                    "summary": f"No stocks to analyze for {sector} sector",
                    "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            
            # Analyze each stock technically
            technical_analyses = []
            
            for stock in candidate_stocks:
                ticker = stock.get('ticker')
                if not ticker:
                    continue
                
                print(f"📊 Analyzing technical indicators for {ticker}...")
                
                # Get comprehensive technical analysis using tools
                technical_data = self._get_comprehensive_technical_analysis(ticker)
                
                if "error" in technical_data:
                    print(f"⚠️  Error analyzing {ticker}: {technical_data['error']}")
                    continue
                
                # Generate LLM-based momentum analysis
                momentum_analysis = self._generate_momentum_analysis(ticker, technical_data, stock)
                
                # Combine technical data with momentum analysis
                stock_analysis = {
                    "ticker": ticker,
                    "market_analyst_data": {
                        "mention_count": stock.get('mention_count'),
                        "average_sentiment": stock.get('average_sentiment'),
                        "relevance_score": stock.get('relevance_score'),
                        "reddit_rationale": stock.get('rationale')
                    },
                    "technical_indicators": technical_data.get('technical_indicators', {}),
                    "technical_score": technical_data.get('overall_technical_score', {}),
                    "momentum_analysis": momentum_analysis,
                    "analysis_date": technical_data.get('analysis_date')
                }
                
                technical_analyses.append(stock_analysis)
                print(f"✅ Completed technical analysis for {ticker}")
            
            # Generate comprehensive technical summary using LLM
            technical_summary = self._generate_technical_summary(technical_analyses, sector)
            
            return {
                "sector": sector,
                "technical_analysis": technical_analyses,
                "summary": technical_summary,
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_stocks_analyzed": len(technical_analyses)
            }
            
        except Exception as e:
            print(f"❌ Error in technical analysis: {str(e)}")
            return {
                "sector": market_analyst_output.get('sector', 'Unknown'),
                "technical_analysis": [],
                "summary": f"Error in technical analysis: {str(e)}",
                "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    
    def _get_comprehensive_technical_analysis(self, ticker: str) -> Dict[str, Any]:
        """Get comprehensive technical analysis using tools"""
        try:
            # Use the technical analysis tool to calculate all indicators
            technical_data = self.technical_tools._calculate_comprehensive_indicators(ticker)
            return technical_data
            
        except Exception as e:
            print(f"⚠️  Error getting technical analysis for {ticker}: {str(e)}")
            return {"error": f"Failed to get technical analysis: {str(e)}"}
    
    def _generate_momentum_analysis(self, ticker: str, technical_data: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive momentum analysis using LLM reasoning
        
        Args:
            ticker: Stock ticker
            technical_data: Technical indicators and data
            market_data: Market analyst data including Reddit rationale
            
        Returns:
            Dictionary with momentum analysis
        """
        try:
            # Extract key technical indicators for LLM analysis
            momentum_indicators = technical_data.get('technical_indicators', {}).get('momentum', {})
            trend_indicators = technical_data.get('technical_indicators', {}).get('trend', {})
            volatility_indicators = technical_data.get('technical_indicators', {}).get('volatility', {})
            stock_data = technical_data.get('stock_data', {})
            technical_score = technical_data.get('overall_technical_score', {})
            
            # Create comprehensive prompt for LLM analysis
            prompt = f"""You are a senior technical analyst analyzing the momentum of {ticker} stock.

## TECHNICAL INDICATORS DATA:

### Momentum Indicators:
- RSI: {momentum_indicators.get('rsi', {}).get('current', 'N/A')} ({momentum_indicators.get('rsi', {}).get('status', 'N/A')})
- MACD: {momentum_indicators.get('macd', {}).get('status', 'N/A')} (MACD Line: {momentum_indicators.get('macd', {}).get('macd_line', 'N/A')}, Signal: {momentum_indicators.get('macd', {}).get('signal_line', 'N/A')})
- Stochastic: {momentum_indicators.get('stochastic', {}).get('status', 'N/A')} (K%: {momentum_indicators.get('stochastic', {}).get('k_percent', 'N/A')}, D%: {momentum_indicators.get('d_percent', 'N/A')})
- Williams %R: {momentum_indicators.get('williams_r', {}).get('current', 'N/A')} ({momentum_indicators.get('williams_r', {}).get('status', 'N/A')})
- CCI: {momentum_indicators.get('cci', {}).get('current', 'N/A')} ({momentum_indicators.get('cci', {}).get('status', 'N/A')})

### Trend Indicators:
- Moving Averages: {trend_indicators.get('moving_averages', {}).get('status', 'N/A')}
  * SMA 20: {trend_indicators.get('moving_averages', {}).get('sma_20', 'N/A')}
  * SMA 50: {trend_indicators.get('moving_averages', {}).get('sma_50', 'N/A')}
  * SMA 200: {trend_indicators.get('moving_averages', {}).get('sma_200', 'N/A')}
- EMA Status: {trend_indicators.get('exponential_moving_averages', {}).get('status', 'N/A')}
- ADX: {trend_indicators.get('adx', {}).get('current', 'N/A')} ({trend_indicators.get('adx', {}).get('status', 'N/A')})
- Parabolic SAR: {trend_indicators.get('parabolic_sar', {}).get('status', 'N/A')}

### Volatility Indicators:
- Bollinger Bands: {volatility_indicators.get('bollinger_bands', {}).get('status', 'N/A')}
  * Upper: {volatility_indicators.get('bollinger_bands', {}).get('upper_band', 'N/A')}
  * Middle: {volatility_indicators.get('bollinger_bands', {}).get('middle_band', 'N/A')}
  * Lower: {volatility_indicators.get('bollinger_bands', {}).get('lower_band', 'N/A')}
- ATR: {volatility_indicators.get('atr', {}).get('current', 'N/A')} ({volatility_indicators.get('atr', {}).get('status', 'N/A')})
- Volatility Ratio: {volatility_indicators.get('volatility_ratio', {}).get('current', 'N/A')} ({volatility_indicators.get('volatility_ratio', {}).get('status', 'N/A')})

### Stock Performance:
- Current Price: {stock_data.get('current_price', 'N/A')}
- Price Change: {stock_data.get('price_change_pct', 'N/A')}%
- Volume: {stock_data.get('volume', 'N/A')} (Avg: {stock_data.get('avg_volume', 'N/A')})

### Technical Score:
- Overall Score: {technical_score.get('percentage', 'N/A')}% ({technical_score.get('grade', 'N/A')})
- Recommendation: {technical_score.get('recommendation', 'N/A')}

### Market Sentiment Context:
Reddit Sentiment: {market_data.get('average_sentiment', 'N/A')} (Mentions: {market_data.get('mention_count', 'N/A')})

## YOUR TASK:
Analyze the momentum of {ticker} based on the technical indicators above. Provide a comprehensive momentum analysis that includes:

1. **Momentum Assessment**: Overall momentum strength and direction
2. **Trend Analysis**: Current trend status and strength
3. **Volatility Context**: Volatility implications for trading
4. **Key Signals**: Most important technical signals (bullish/bearish)
5. **Risk Assessment**: Technical risk factors and support/resistance levels
6. **Trading Implications**: What this means for traders and investors
7. **Momentum Score**: Your own momentum rating (1-10 scale)

Format your response as a structured analysis with clear sections. Be specific about what the indicators are telling us and provide actionable insights.

## MOMENTUM ANALYSIS:"""

            # Generate momentum analysis using LLM
            response = self.llm.invoke(prompt)
            momentum_text = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the response
            momentum_text = momentum_text.strip()
            if momentum_text.startswith("## MOMENTUM ANALYSIS:"):
                momentum_text = momentum_text[22:].strip()
            
            # Extract key insights programmatically
            momentum_score = self._extract_momentum_score(momentum_text)
            key_signals = self._extract_key_signals(momentum_text)
            risk_level = self._assess_technical_risk(technical_data)
            
            return {
                "comprehensive_analysis": momentum_text,
                "momentum_score": momentum_score,
                "key_signals": key_signals,
                "risk_level": risk_level,
                "trend_strength": self._assess_trend_strength(trend_indicators),
                "volatility_implications": self._assess_volatility_implications(volatility_indicators),
                "support_resistance": self._identify_support_resistance(technical_data)
            }
            
        except Exception as e:
            print(f"⚠️  Error generating momentum analysis for {ticker}: {str(e)}")
            return {
                "comprehensive_analysis": f"Error generating momentum analysis: {str(e)}",
                "momentum_score": 5,
                "key_signals": ["Analysis failed"],
                "risk_level": "Unknown",
                "trend_strength": "Unknown",
                "volatility_implications": "Unknown",
                "support_resistance": {"support": "Unknown", "resistance": "Unknown"}
            }
    
    def _generate_technical_summary(self, technical_analyses: List[Dict[str, Any]], sector: str) -> str:
        """Generate comprehensive technical summary for the sector using LLM"""
        try:
            if not technical_analyses:
                return f"No technical analysis available for {sector} sector"
            
            # Prepare summary data
            summary_data = []
            for analysis in technical_analyses:
                ticker = analysis.get('ticker', 'Unknown')
                momentum_score = analysis.get('momentum_analysis', {}).get('momentum_score', 5)
                technical_score = analysis.get('technical_score', {}).get('percentage', 0)
                trend_strength = analysis.get('momentum_analysis', {}).get('trend_strength', 'Unknown')
                
                summary_data.append({
                    "ticker": ticker,
                    "momentum_score": momentum_score,
                    "technical_score": technical_score,
                    "trend_strength": trend_strength
                })
            
            # Sort by momentum score
            summary_data.sort(key=lambda x: x.get('momentum_score', 0), reverse=True)
            
            # Create prompt for sector summary
            prompt = f"""You are a senior technical analyst providing a comprehensive sector summary for {sector}.

## TECHNICAL ANALYSIS SUMMARY DATA:

{chr(10).join([f"- {item['ticker']}: Momentum Score {item['momentum_score']}/10, Technical Score {item['technical_score']}%, Trend: {item['trend_strength']}" for item in summary_data])}

## YOUR TASK:
Provide a comprehensive technical analysis summary for the {sector} sector that includes:

1. **Overall Sector Momentum**: Aggregate momentum assessment across all stocks
2. **Top Momentum Leaders**: Stocks with strongest technical momentum
3. **Sector Trend Analysis**: Overall trend direction and strength
4. **Technical Opportunities**: Stocks showing favorable technical setups
5. **Risk Factors**: Technical risks and concerns across the sector
6. **Investment Implications**: What this means for sector allocation
7. **Key Technical Themes**: Common technical patterns or signals

Format your response as a structured sector summary with clear sections. Focus on actionable insights for portfolio managers and traders.

## SECTOR TECHNICAL SUMMARY:"""

            # Generate summary using LLM
            response = self.llm.invoke(prompt)
            summary_text = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the response
            summary_text = summary_text.strip()
            if summary_text.startswith("## SECTOR TECHNICAL SUMMARY:"):
                summary_text = summary_text[30:].strip()
            
            return summary_text
            
        except Exception as e:
            print(f"⚠️  Error generating technical summary: {str(e)}")
            return f"Error generating technical summary: {str(e)}"
    
    # Helper methods for extracting insights
    def _extract_momentum_score(self, analysis_text: str) -> int:
        """Extract momentum score from analysis text"""
        try:
            # Look for momentum score patterns
            import re
            patterns = [
                r'momentum.*?(\d+)/10',
                r'momentum.*?(\d+)',
                r'score.*?(\d+)/10',
                r'rating.*?(\d+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, analysis_text.lower())
                if match:
                    score = int(match.group(1))
                    if 1 <= score <= 10:
                        return score
            
            # Default score based on text sentiment
            if any(word in analysis_text.lower() for word in ['strong', 'bullish', 'positive', 'excellent']):
                return 8
            elif any(word in analysis_text.lower() for word in ['weak', 'bearish', 'negative', 'poor']):
                return 3
            else:
                return 5
                
        except Exception:
            return 5
    
    def _extract_key_signals(self, analysis_text: str) -> List[str]:
        """Extract key technical signals from analysis text"""
        try:
            signals = []
            
            # Look for common signal patterns
            if 'bullish' in analysis_text.lower():
                signals.append("Bullish momentum")
            if 'bearish' in analysis_text.lower():
                signals.append("Bearish momentum")
            if 'overbought' in analysis_text.lower():
                signals.append("Overbought conditions")
            if 'oversold' in analysis_text.lower():
                signals.append("Oversold conditions")
            if 'trend reversal' in analysis_text.lower():
                signals.append("Potential trend reversal")
            if 'breakout' in analysis_text.lower():
                signals.append("Breakout pattern")
            if 'support' in analysis_text.lower():
                signals.append("Support level identified")
            if 'resistance' in analysis_text.lower():
                signals.append("Resistance level identified")
            
            return signals if signals else ["Mixed signals"]
            
        except Exception:
            return ["Analysis incomplete"]
    
    def _assess_technical_risk(self, technical_data: Dict[str, Any]) -> str:
        """Assess technical risk level"""
        try:
            # Extract risk indicators
            rsi = technical_data.get('technical_indicators', {}).get('momentum', {}).get('rsi', {}).get('current')
            bb_status = technical_data.get('technical_indicators', {}).get('volatility', {}).get('bollinger_bands', {}).get('status')
            volatility_ratio = technical_data.get('technical_indicators', {}).get('volatility', {}).get('volatility_ratio', {}).get('current')
            
            risk_factors = 0
            
            # RSI risk
            if rsi and (rsi > 80 or rsi < 20):
                risk_factors += 1
            
            # Bollinger Bands risk
            if bb_status in ['Overbought', 'Oversold']:
                risk_factors += 1
            
            # Volatility risk
            if volatility_ratio and volatility_ratio > 1.5:
                risk_factors += 1
            
            # Determine risk level
            if risk_factors >= 2:
                return "High"
            elif risk_factors == 1:
                return "Medium"
            else:
                return "Low"
                
        except Exception:
            return "Unknown"
    
    def _assess_trend_strength(self, trend_indicators: Dict[str, Any]) -> str:
        """Assess trend strength based on indicators"""
        try:
            ma_status = trend_indicators.get('moving_averages', {}).get('status', '')
            adx_status = trend_indicators.get('adx', {}).get('status', '')
            
            if 'Strong' in ma_status and adx_status == 'Strong Trend':
                return "Very Strong"
            elif 'Strong' in ma_status or adx_status == 'Strong Trend':
                return "Strong"
            elif 'Moderate' in adx_status:
                return "Moderate"
            else:
                return "Weak"
                
        except Exception:
            return "Unknown"
    
    def _assess_volatility_implications(self, volatility_indicators: Dict[str, Any]) -> str:
        """Assess volatility implications for trading"""
        try:
            bb_status = volatility_indicators.get('bollinger_bands', {}).get('status', '')
            atr_status = volatility_indicators.get('atr', {}).get('status', '')
            volatility_ratio = volatility_indicators.get('volatility_ratio', {}).get('current', 1.0)
            
            if bb_status == 'Normal Range' and atr_status == 'Normal Volatility' and volatility_ratio <= 1.2:
                return "Stable trading conditions"
            elif volatility_ratio > 1.5:
                return "High volatility - increased risk/reward"
            elif bb_status in ['Overbought', 'Oversold']:
                return "Extreme volatility - potential reversal"
            else:
                return "Moderate volatility"
                
        except Exception:
            return "Unknown"
    
    def _identify_support_resistance(self, technical_data: Dict[str, Any]) -> Dict[str, str]:
        """Identify key support and resistance levels"""
        try:
            stock_data = technical_data.get('stock_data', {})
            bb_data = technical_data.get('technical_indicators', {}).get('volatility', {}).get('bollinger_bands', {})
            ma_data = technical_data.get('technical_indicators', {}).get('trend', {}).get('moving_averages', {})
            
            support_levels = []
            resistance_levels = []
            
            # Bollinger Bands
            if bb_data.get('lower_band'):
                support_levels.append(f"BB Lower: {bb_data['lower_band']:.2f}")
            if bb_data.get('upper_band'):
                resistance_levels.append(f"BB Upper: {bb_data['upper_band']:.2f}")
            
            # Moving Averages
            if ma_data.get('sma_20'):
                support_levels.append(f"SMA 20: {ma_data['sma_20']:.2f}")
            if ma_data.get('sma_50'):
                support_levels.append(f"SMA 50: {ma_data['sma_50']:.2f}")
            
            return {
                "support": " | ".join(support_levels) if support_levels else "Not identified",
                "resistance": " | ".join(resistance_levels) if resistance_levels else "Not identified"
            }
            
        except Exception:
            return {"support": "Unknown", "resistance": "Unknown"}
