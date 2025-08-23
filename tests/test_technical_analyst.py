#!/usr/bin/env python3
"""
Test Technical Analyst Agent - Validate technical analysis and LLM momentum generation
"""

import os
import sys
import json
from typing import Dict, Any

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
from agents.technical_analyst_agent import TechnicalAnalystAgent
from config.config import Config

def test_technical_analyst():
    """Test the Technical Analyst Agent with sample Market Analyst output"""
    
    print("🔧 TESTING TECHNICAL ANALYST AGENT")
    print("=" * 60)
    print("This test validates technical analysis and LLM momentum generation")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Check LLM configuration
    config = Config()
    print(f"🤖 LLM Provider: {config.MODEL_PROVIDER}")
    if config.MODEL_PROVIDER == "ollama":
        print(f"🦙 Ollama Model: {config.OLLAMA_MODEL}")
    else:
        print(f"🔑 OpenAI Model: {config.OPENAI_MODEL}")
    
    # Create Technical Analyst Agent
    print("\n🔧 Creating Technical Analyst Agent...")
    technical_agent = TechnicalAnalystAgent()
    
    # Sample Market Analyst output (based on real output from previous test)
    sample_market_output = {
        "sector": "Technology",
        "candidate_stocks": [
            {
                "ticker": "NVDA",
                "mention_count": 10,
                "average_sentiment": 0.589,
                "relevance_score": 0.378,
                "rationale": "### Rationale for NVDA Reddit Sentiment Analysis\n\n#### 1. Key Themes and Topics\nThe discussions surrounding Nvidia (NVDA) on Reddit primarily revolve around:\n- **Product Launches and Innovations**: The announcement of the **Spectrum-XGS Ethernet** highlights Nvidia's commitment to enhancing its offerings for data centers and AI applications. This product is positioned as a significant advancement for AI super-factories.\n- **Market Reactions**: The immediate positive market reaction, with NVDA shares rising by 1.7%, indicates investor optimism regarding new product launches.\n- **Analyst Insights**: Analysts are actively discussing Nvidia's growth potential, particularly in the AI sector, with notable mentions of increased price targets based on demand forecasts.\n- **Supply Chain Issues**: Concerns are raised regarding Nvidia's decision to halt work on the H20 AI chip, which could impact future product availability and market positioning.\n\n#### 2. User Sentiment and Perceptions\nThe overall sentiment among Reddit users appears to be **bullish**, particularly in response to the new product launch and positive analyst commentary. The upvotes on posts discussing the Spectrum-XGS and analyst insights reflect a general optimism about Nvidia's growth trajectory in the AI and data center markets. However, there is a **bearish undertone** regarding supply chain disruptions, particularly related to the H20 AI chip, which could temper some of the enthusiasm.\n\n#### 3. Specific Concerns or Excitement Points\n- **Excitement Points**:\n  - The launch of the **Spectrum-XGS Ethernet** is seen as a significant advancement, with users expressing excitement about its implications for AI and data center investments.\n  - Analyst C.J. Muse's remarks about the \"seemingly insatiable\" demand for AI compute and the raised price target from $200 to $240 have generated positive discussions and reinforced bullish sentiment.\n\n- **Concerns**:\n  - The decision to halt work on the H20 AI chip raises concerns about Nvidia's ability to meet future demand and maintain its competitive edge in the AI market. This could lead to potential delays in product rollouts and affect investor confidence.\n\n#### 4. Market Sentiment Indicators\n- The number of upvotes on posts discussing the Spectrum-XGS (18 and 17 upvotes) and the analyst's positive outlook (35 upvotes) indicates strong community support and enthusiasm for Nvidia's strategic direction.\n- The post regarding the halt on the H20 AI chip received 57 upvotes, suggesting that this issue is garnering significant attention and concern among users, which could impact overall sentiment if not addressed.\n\n#### 5. Potential Catalysts or Events Driving Discussion\n- **Product Launches**: The introduction of new technologies like the Spectrum-XGS Ethernet is a key catalyst driving positive sentiment and discussions about Nvidia's future.\n- **Analyst Upgrades**: Positive analyst reports and increased price targets serve as catalysts for bullish sentiment, encouraging discussions about Nvidia's growth potential.\n- **Supply Chain Developments**: The halt on the H20 AI chip production is a critical event that could influence market perceptions and investor confidence, making it a focal point for ongoing discussions.\n\n### Conclusion\nIn summary, Reddit sentiment regarding Nvidia (NVDA) is predominantly bullish, driven by excitement over new product launches and positive analyst forecasts. However, concerns about supply chain issues, particularly related to the H20 AI chip, introduce a note of caution. Analysts should monitor these discussions closely, as they reflect real-time user insights and perceptions that could influence market dynamics."
            },
            {
                "ticker": "META",
                "mention_count": 17,
                "average_sentiment": 0.32,
                "relevance_score": 0.366,
                "rationale": "### Rationale for Reddit Sentiment Analysis on META\n\n#### 1. Key Themes and Topics Discussed\nReddit users are primarily discussing the following themes related to META:\n- **Regulatory Challenges**: The warning from FTC Chair Andrew Ferguson regarding compliance with EU and UK digital laws and its potential conflict with U.S. privacy laws is a significant concern. This highlights the regulatory landscape that META operates within and the implications for its business practices.\n- **AI Hiring and Investment**: The news about META freezing AI hiring after a spending spree indicates a shift in strategy, which has sparked discussions about the company's future direction in AI development and its impact on innovation.\n- **Market Performance and Stock Sentiment**: The broader context of tech stock sell-offs, including META's position within this trend, is a recurring topic. Users are analyzing how these market dynamics affect META's stock performance and investor sentiment.\n\n#### 2. User Sentiment and Perceptions\nThe sentiment among Reddit users appears to be **bearish** overall, with several posts reflecting concerns about META's regulatory challenges and the implications of its hiring freeze. The discussions indicate a cautious outlook on the company's ability to navigate these challenges effectively. However, there are also elements of **neutral** sentiment, particularly in discussions about the broader tech market and its volatility.\n\n#### 3. Specific Concerns or Excitement Points Mentioned\n- **Concerns**:\n  - The potential conflict between compliance with international laws and U.S. privacy standards raises fears about legal repercussions and operational challenges for META.\n  - The hiring freeze in AI could signal a slowdown in innovation and growth, which may worry investors about META's competitive edge in the tech sector.\n  \n- **Excitement Points**:\n  - Some users express curiosity about how the hiring freeze will affect META's market performance, indicating a level of engagement and interest in the company's strategic decisions.\n\n#### 4. Market Sentiment Indicators from the Community\n- **Upvotes and Engagement**: The post about the AI hiring freeze received a high number of upvotes (349), indicating significant interest and concern among users. The number of comments (81) also suggests active engagement and discussion, reflecting a community that is closely monitoring META's developments.\n- **Comparative Sentiment**: The post regarding regulatory challenges received fewer upvotes (85) but still highlights a critical issue that could impact investor confidence. The contrast in engagement levels may suggest that users are more focused on immediate operational changes (like hiring) than on regulatory concerns.\n\n#### 5. Potential Catalysts or Events Driving Discussion\n- **Regulatory Developments**: Ongoing discussions about data privacy laws and their implications for tech companies are likely to continue influencing sentiment around META.\n- **Company Strategy Changes**: The decision to freeze AI hiring could be a pivotal moment for META, prompting further analysis of its long-term strategy and market positioning.\n- **Market Volatility**: The overall sell-off in tech stocks is a significant backdrop that could amplify concerns about META's performance and lead to increased scrutiny from investors.\n\n### Conclusion\nThe sentiment surrounding META on Reddit is predominantly bearish, driven by concerns over regulatory challenges and strategic shifts in hiring practices. While there is engagement and discussion about these topics, the overall tone reflects caution among investors. Analysts should monitor these discussions closely, as they provide valuable insights into community sentiment and potential market reactions to META's decisions and external pressures."
            }
        ],
        "summary": "### Technology Sector Summary\n\n#### 1. Overall Market Sentiment for the Sector\nThe overall sentiment within the Technology sector on Reddit is bullish. This positive outlook is reflected in the discussions surrounding key stocks, indicating a general confidence among retail investors regarding the sector's growth potential and resilience.\n\n#### 2. Key Themes Driving Reddit Discussions\nSeveral themes have emerged from the Reddit discussions within the Technology sector:\n\n- **Artificial Intelligence (AI) and Machine Learning**: The ongoing advancements in AI technologies are a significant focus, particularly surrounding NVIDIA (NVDA), which is recognized for its leadership in AI hardware and software solutions.\n  \n- **Social Media and Digital Advertising**: Meta Platforms (META) continues to be a topic of interest, with discussions centered on its evolving advertising strategies and the impact of regulatory changes on its business model.\n\n- **Search and Cloud Services**: Alphabet Inc. (GOOGL) is frequently mentioned in the context of its cloud computing services and innovations in search algorithms, which are seen as critical to maintaining its competitive edge.\n\n#### 3. Notable Trends or Patterns\n- **Diverse Sentiment Across Stocks**: While the overall sentiment is bullish, individual stock sentiments vary significantly. GOOGL has the highest sentiment score (0.719), indicating strong positive sentiment, while META has a lower score (0.320), suggesting mixed feelings among investors about its future prospects.\n  \n- **Increased Engagement**: The number of mentions for each stock indicates heightened engagement from retail investors, particularly for META, which has the highest number of mentions (17). This suggests that investors are actively discussing and analyzing its performance and potential.\n\n#### 4. Potential Market Implications\nThe bullish sentiment in the Technology sector could lead to increased investment flows into tech stocks, particularly those with strong fundamentals and growth prospects. Stocks like GOOGL may attract more institutional interest due to their positive sentiment and robust performance metrics. Conversely, the mixed sentiment surrounding META could indicate caution among investors, potentially leading to volatility in its stock price.\n\n#### 5. Summary of Top Performing Stocks\n- **NVIDIA (NVDA)**: 10 mentions, sentiment score of 0.589. Investors are optimistic about NVDA's role in AI and gaming, although the sentiment is not as strong as GOOGL.\n  \n- **Meta Platforms (META)**: 17 mentions, sentiment score of 0.320. Despite high engagement, the lower sentiment score suggests concerns about its advertising revenue and regulatory challenges.\n  \n- **Alphabet Inc. (GOOGL)**: 3 mentions, sentiment score of 0.719. GOOGL stands out with the highest sentiment, reflecting confidence in its cloud services and search capabilities.\n\n### Conclusion\nThe Technology sector is currently experiencing a bullish sentiment on Reddit, driven by discussions around AI, social media dynamics, and cloud services. While GOOGL is viewed favorably, investors should remain cautious about META's mixed sentiment. Overall, the sector's positive outlook may present opportunities for investment, particularly in stocks demonstrating strong growth potential and positive investor sentiment."
    }
    
    print(f"\n📊 Sample Market Analyst Output:")
    print(f"  - Sector: {sample_market_output['sector']}")
    print(f"  - Stocks: {len(sample_market_output['candidate_stocks'])}")
    print(f"  - Summary: {len(sample_market_output['summary'])} characters")
    
    # Test Technical Analyst Agent
    print(f"\n{'='*20} TESTING TECHNICAL ANALYSIS {'='*20}")
    
    try:
        # Execute technical analysis task
        print(f"🔧 Executing technical analysis task...")
        result = technical_agent.execute_task(sample_market_output)
        
        # Display the results
        print(f"\n📋 TECHNICAL ANALYSIS RESULTS:")
        print("-" * 50)
        print(json.dumps(result, indent=2))
        
        # Validate the output
        print(f"\n🔍 VALIDATING TECHNICAL ANALYSIS OUTPUT:")
        print("-" * 50)
        validation_result = validate_technical_analysis_output(result)
        
        if validation_result["is_valid"]:
            print("✅ Technical analysis output is VALID")
            print(f"✅ Sector: {result.get('sector', 'MISSING')}")
            print(f"✅ Stocks analyzed: {result.get('total_stocks_analyzed', 'MISSING')}")
            print(f"✅ Summary: {len(result.get('summary', ''))} characters")
            
            # Show detailed analysis for each stock
            show_stock_analysis_details(result)
            
        else:
            print("❌ Technical analysis output is INVALID")
            for error in validation_result["errors"]:
                print(f"  - {error}")
        
    except Exception as e:
        print(f"❌ Error testing Technical Analyst Agent: {str(e)}")
        import traceback
        traceback.print_exc()

def validate_technical_analysis_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the technical analysis output structure"""
    
    errors = []
    
    # Check required top-level keys
    required_keys = ["sector", "technical_analysis", "summary", "analysis_date", "total_stocks_analyzed"]
    for key in required_keys:
        if key not in output:
            errors.append(f"Missing required key: {key}")
    
    # Validate technical_analysis list
    if "technical_analysis" in output:
        if not isinstance(output["technical_analysis"], list):
            errors.append("technical_analysis must be a list")
        else:
            # Validate each stock analysis
            for i, analysis in enumerate(output["technical_analysis"]):
                stock_errors = validate_stock_analysis(analysis, i)
                errors.extend(stock_errors)
    
    # Validate summary
    if "summary" in output:
        if not isinstance(output["summary"], str):
            errors.append("summary must be a string")
        elif len(output["summary"].strip()) == 0:
            errors.append("summary cannot be empty")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }

def validate_stock_analysis(analysis: Dict[str, Any], index: int) -> list:
    """Validate individual stock analysis"""
    
    errors = []
    
    # Check required stock analysis keys
    required_keys = ["ticker", "market_analyst_data", "technical_indicators", "technical_score", "momentum_analysis"]
    for key in required_keys:
        if key not in analysis:
            errors.append(f"Stock {index}: Missing required key: {key}")
    
    # Validate market analyst data
    if "market_analyst_data" in analysis:
        market_data = analysis["market_analyst_data"]
        market_keys = ["mention_count", "average_sentiment", "relevance_score", "reddit_rationale"]
        for key in market_keys:
            if key not in market_data:
                errors.append(f"Stock {index}: Missing market data key: {key}")
    
    # Validate momentum analysis
    if "momentum_analysis" in analysis:
        momentum_data = analysis["momentum_analysis"]
        momentum_keys = ["comprehensive_analysis", "momentum_score", "key_signals", "risk_level"]
        for key in momentum_keys:
            if key not in momentum_data:
                errors.append(f"Stock {index}: Missing momentum analysis key: {key}")
    
    return errors

def show_stock_analysis_details(output: Dict[str, Any]):
    """Show detailed analysis for each stock"""
    
    print(f"\n📊 DETAILED STOCK ANALYSIS:")
    print("-" * 50)
    
    stocks = output.get('technical_analysis', [])
    for i, stock in enumerate(stocks, 1):
        ticker = stock.get('ticker', 'Unknown')
        print(f"\n  {i}. {ticker}")
        
        # Market analyst data
        market_data = stock.get('market_analyst_data', {})
        print(f"     📈 Market Data:")
        print(f"        - Mentions: {market_data.get('mention_count', 'N/A')}")
        print(f"        - Sentiment: {market_data.get('average_sentiment', 'N/A')}")
        print(f"        - Relevance: {market_data.get('relevance_score', 'N/A')}")
        
        # Technical indicators summary
        technical_indicators = stock.get('technical_indicators', {})
        print(f"     🔧 Technical Indicators:")
        print(f"        - Momentum: {len(technical_indicators.get('momentum', {}))} indicators")
        print(f"        - Trend: {len(technical_indicators.get('trend', {}))} indicators")
        print(f"        - Volatility: {len(technical_indicators.get('volatility', {}))} indicators")
        
        # Technical score
        technical_score = stock.get('technical_score', {})
        print(f"     ⭐ Technical Score:")
        print(f"        - Score: {technical_score.get('percentage', 'N/A')}%")
        print(f"        - Grade: {technical_score.get('grade', 'N/A')}")
        print(f"        - Recommendation: {technical_score.get('recommendation', 'N/A')}")
        
        # Momentum analysis
        momentum = stock.get('momentum_analysis', {})
        print(f"     🚀 Momentum Analysis:")
        print(f"        - Momentum Score: {momentum.get('momentum_score', 'N/A')}/10")
        print(f"        - Risk Level: {momentum.get('risk_level', 'N/A')}")
        print(f"        - Trend Strength: {momentum.get('trend_strength', 'N/A')}")
        print(f"        - Key Signals: {', '.join(momentum.get('key_signals', []))}")
        
        # Support/Resistance
        support_resistance = momentum.get('support_resistance', {})
        print(f"     📍 Support/Resistance:")
        print(f"        - Support: {support_resistance.get('support', 'N/A')}")
        print(f"        - Resistance: {support_resistance.get('resistance', 'N/A')}")
    
    # Show sector summary
    print(f"\n📝 SECTOR TECHNICAL SUMMARY:")
    print("-" * 50)
    summary = output.get('summary', '')
    if len(summary) > 200:
        print(f"   {summary[:200]}...")
    else:
        print(f"   {summary}")

if __name__ == "__main__":
    test_technical_analyst()
