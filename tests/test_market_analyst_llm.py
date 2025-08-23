#!/usr/bin/env python3
"""
Test Market Analyst Agent LLM Reasoning - Focus on testing LLM-generated rationales
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
from agents.market_analyst_agent import MarketAnalystAgent
from config.config import Config

def test_market_analyst_llm():
    """Test the Market Analyst Agent's LLM reasoning capabilities"""
    
    print("🧠 TESTING MARKET ANALYST AGENT LLM REASONING")
    print("=" * 60)
    print("This test focuses on validating LLM-generated rationales")
    print("=" * 60)
    
    # Load environment variables
    load_dotenv()
    
    # Check Reddit credentials
    reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    
    if not reddit_client_id or not reddit_client_secret:
        print("❌ Reddit API credentials not found!")
        print("Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in your .env file")
        return
    
    print("✅ Reddit API credentials found")
    
    # Check LLM configuration
    config = Config()
    print(f"🤖 LLM Provider: {config.MODEL_PROVIDER}")
    if config.MODEL_PROVIDER == "ollama":
        print(f"🦙 Ollama Model: {config.OLLAMA_MODEL}")
        print(f"🌐 Ollama URL: {config.OLLAMA_BASE_URL}")
        
        # Test Ollama connection
        try:
            import requests
            response = requests.get(f"{config.OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                print("✅ Ollama connection successful")
            else:
                print(f"⚠️  Ollama connection issue: {response.status_code}")
        except Exception as e:
            print(f"❌ Ollama connection failed: {str(e)}")
            return
    else:
        print(f"🔑 OpenAI Model: {config.OPENAI_MODEL}")
    
    # Create Market Analyst Agent
    print("\n🔧 Creating Market Analyst Agent...")
    market_agent = MarketAnalystAgent()
    
    # Test with Technology sector (most likely to have data)
    sector = "Technology"
    print(f"\n{'='*20} TESTING {sector.upper()} SECTOR {'='*20}")
    
    try:
        # Execute the agent's task
        print(f"📊 Executing market analysis for {sector} sector...")
        result = market_agent.execute_task(sector)
        
        # Display the raw output
        print(f"\n📋 RAW OUTPUT FROM MARKET ANALYST AGENT:")
        print("-" * 50)
        print(json.dumps(result, indent=2))
        
        # Focus on LLM-generated content validation
        print(f"\n🧠 LLM CONTENT VALIDATION:")
        print("-" * 50)
        
        # Check if we have candidate stocks
        stocks = result.get('candidate_stocks', [])
        if not stocks:
            print("❌ No candidate stocks found - cannot validate LLM content")
            return
        
        print(f"✅ Found {len(stocks)} candidate stocks")
        
        # Validate each stock's rationale
        for i, stock in enumerate(stocks, 1):
            ticker = stock.get('ticker', 'UNKNOWN')
            rationale = stock.get('rationale', '')
            
            print(f"\n📊 Stock {i}: {ticker}")
            print(f"   💭 Rationale: {rationale[:150]}...")
            
            # Check rationale quality
            if len(rationale.strip()) < 50:
                print(f"   ❌ Rationale too short ({len(rationale.strip())} chars)")
            else:
                print(f"   ✅ Rationale length: {len(rationale.strip())} chars")
            
            # Check for placeholder text
            placeholder_indicators = [
                "[LLM analysis would go here]",
                "LLM analysis would go here",
                "sentiment analysis would go here",
                "placeholder",
                "TODO"
            ]
            
            has_placeholder = False
            for indicator in placeholder_indicators:
                if indicator.lower() in rationale.lower():
                    print(f"   ❌ Contains placeholder: '{indicator}'")
                    has_placeholder = True
                    break
            
            if not has_placeholder:
                print(f"   ✅ No placeholder text detected")
            
            # Check if rationale looks like real analysis
            if "reddit" in rationale.lower() or "sentiment" in rationale.lower() or "discussion" in rationale.lower():
                print(f"   ✅ Contains relevant analysis keywords")
            else:
                print(f"   ⚠️  May not contain relevant analysis content")
        
        # Validate summary
        summary = result.get('summary', '')
        print(f"\n📝 SUMMARY VALIDATION:")
        print(f"   Summary: {summary[:200]}...")
        
        if len(summary.strip()) < 100:
            print(f"   ❌ Summary too short ({len(summary.strip())} chars)")
        else:
            print(f"   ✅ Summary length: {len(summary.strip())} chars")
        
        # Overall assessment
        print(f"\n🎯 OVERALL LLM ASSESSMENT:")
        print("-" * 50)
        
        total_stocks = len(stocks)
        valid_rationales = sum(1 for stock in stocks if len(stock.get('rationale', '').strip()) >= 50)
        no_placeholders = sum(1 for stock in stocks if not any(indicator.lower() in stock.get('rationale', '').lower() for indicator in placeholder_indicators))
        
        print(f"   Total stocks: {total_stocks}")
        print(f"   Valid rationales: {valid_rationales}/{total_stocks}")
        print(f"   No placeholders: {no_placeholders}/{total_stocks}")
        
        if valid_rationales == total_stocks and no_placeholders == total_stocks:
            print("   🎉 EXCELLENT: All rationales are properly LLM-generated!")
        elif valid_rationales >= total_stocks * 0.8 and no_placeholders >= total_stocks * 0.8:
            print("   ✅ GOOD: Most rationales are properly LLM-generated")
        else:
            print("   ❌ NEEDS IMPROVEMENT: Many rationales are not properly LLM-generated")
        
    except Exception as e:
        print(f"❌ Error testing {sector} sector: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_market_analyst_llm()
