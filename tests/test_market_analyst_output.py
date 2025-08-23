#!/usr/bin/env python3
"""
Test Market Analyst Agent Output - Validate the exact output format for downstream agents
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

def test_market_analyst_output():
    """Test the Market Analyst Agent to see its exact output format"""
    
    print("🧪 TESTING MARKET ANALYST AGENT OUTPUT")
    print("=" * 60)
    print("This test shows exactly what downstream agents will receive")
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
    else:
        print(f"🔑 OpenAI Model: {config.OPENAI_MODEL}")
    
    # Create Market Analyst Agent
    print("\n🔧 Creating Market Analyst Agent...")
    market_agent = MarketAnalystAgent()
    
    # Test with different sectors
    test_sectors = ["Technology", "Finance", "Healthcare"]
    
    for sector in test_sectors:
        print(f"\n{'='*20} TESTING {sector.upper()} SECTOR {'='*20}")
        
        try:
            # Execute the agent's task
            print(f"📊 Executing market analysis for {sector} sector...")
            result = market_agent.execute_task(sector)
            
            # Display the raw output
            print(f"\n📋 RAW OUTPUT FROM MARKET ANALYST AGENT:")
            print("-" * 50)
            print(json.dumps(result, indent=2))
            
            # Validate the output schema
            print(f"\n🔍 VALIDATING OUTPUT SCHEMA:")
            print("-" * 50)
            validation_result = validate_output_schema(result, sector)
            
            if validation_result["is_valid"]:
                print("✅ Output schema is VALID")
                print(f"✅ Sector: {result.get('sector', 'MISSING')}")
                print(f"✅ Candidate stocks: {len(result.get('candidate_stocks', []))}")
                print(f"✅ Summary: {len(result.get('summary', ''))} characters")
                
                # Show what downstream agents will receive
                print(f"\n📤 WHAT DOWNSTREAM AGENTS WILL RECEIVE:")
                print("-" * 50)
                show_downstream_data(result)
                
                # Validate LLM-generated content
                print(f"\n🧠 VALIDATING LLM-GENERATED CONTENT:")
                print("-" * 50)
                llm_validation = validate_llm_content(result)
                if llm_validation["is_valid"]:
                    print("✅ LLM content is VALID")
                else:
                    print("❌ LLM content issues:")
                    for issue in llm_validation["issues"]:
                        print(f"  - {issue}")
                
            else:
                print("❌ Output schema is INVALID")
                for error in validation_result["errors"]:
                    print(f"  - {error}")
            
        except Exception as e:
            print(f"❌ Error testing {sector} sector: {str(e)}")
            import traceback
            traceback.print_exc()

def validate_output_schema(output: Dict[str, Any], expected_sector: str) -> Dict[str, Any]:
    """Validate that the output matches the expected schema"""
    
    errors = []
    
    # Check required top-level keys
    required_keys = ["sector", "candidate_stocks", "summary"]
    for key in required_keys:
        if key not in output:
            errors.append(f"Missing required key: {key}")
    
    # Validate sector
    if "sector" in output:
        if output["sector"] != expected_sector:
            errors.append(f"Sector mismatch: expected '{expected_sector}', got '{output['sector']}'")
    
    # Validate candidate_stocks
    if "candidate_stocks" in output:
        if not isinstance(output["candidate_stocks"], list):
            errors.append("candidate_stocks must be a list")
        else:
            # Validate each stock entry
            for i, stock in enumerate(output["candidate_stocks"]):
                stock_errors = validate_stock_entry(stock, i)
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

def validate_stock_entry(stock: Dict[str, Any], index: int) -> list:
    """Validate a single stock entry"""
    
    errors = []
    
    # Check required stock keys
    required_stock_keys = ["ticker", "mention_count", "average_sentiment", "relevance_score", "rationale"]
    for key in required_stock_keys:
        if key not in stock:
            errors.append(f"Stock {index}: Missing required key: {key}")
    
    # Validate ticker
    if "ticker" in stock:
        if not isinstance(stock["ticker"], str) or len(stock["ticker"].strip()) == 0:
            errors.append(f"Stock {index}: ticker must be a non-empty string")
    
    # Validate mention_count
    if "mention_count" in stock:
        if not isinstance(stock["mention_count"], int) or stock["mention_count"] < 0:
            errors.append(f"Stock {index}: mention_count must be a non-negative integer")
    
    # Validate average_sentiment
    if "average_sentiment" in stock:
        if not isinstance(stock["average_sentiment"], (int, float)):
            errors.append(f"Stock {index}: average_sentiment must be a number")
        elif stock["average_sentiment"] < -1.0 or stock["average_sentiment"] > 1.0:
            errors.append(f"Stock {index}: average_sentiment must be between -1.0 and 1.0")
    
    # Validate relevance_score
    if "relevance_score" in stock:
        if not isinstance(stock["relevance_score"], (int, float)):
            errors.append(f"Stock {index}: relevance_score must be a number")
        elif stock["relevance_score"] < 0.0 or stock["relevance_score"] > 1.0:
            errors.append(f"Stock {index}: relevance_score must be between 0.0 and 1.0")
    
    # Validate rationale
    if "rationale" in stock:
        if not isinstance(stock["rationale"], str) or len(stock["rationale"].strip()) == 0:
            errors.append(f"Stock {index}: rationale must be a non-empty string")
    
    return errors

def validate_llm_content(output: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that the content appears to be LLM-generated"""
    
    issues = []
    
    # Check if rationales look like LLM-generated content
    stocks = output.get('candidate_stocks', [])
    for i, stock in enumerate(stocks):
        rationale = stock.get('rationale', '')
        
        # Check for placeholder text that suggests LLM didn't work
        placeholder_indicators = [
            "[LLM analysis would go here]",
            "LLM analysis would go here",
            "sentiment analysis would go here",
            "placeholder",
            "TODO"
        ]
        
        for indicator in placeholder_indicators:
            if indicator.lower() in rationale.lower():
                issues.append(f"Stock {i+1} ({stock.get('ticker', 'UNKNOWN')}): Rationale contains placeholder text '{indicator}'")
                break
        
        # Check if rationale is too generic
        if len(rationale.strip()) < 50:
            issues.append(f"Stock {i+1} ({stock.get('ticker', 'UNKNOWN')}): Rationale is too short ({len(rationale.strip())} chars) - may not be LLM-generated")
    
    # Check summary for LLM-generated content
    summary = output.get('summary', '')
    if len(summary.strip()) < 100:
        issues.append(f"Summary is too short ({len(summary.strip())} chars) - may not be LLM-generated")
    
    return {
        "is_valid": len(issues) == 0,
        "issues": issues
    }

def show_downstream_data(output: Dict[str, Any]):
    """Show what downstream agents will receive in a clear format"""
    
    print(f"📊 SECTOR: {output.get('sector', 'MISSING')}")
    print(f"📝 SUMMARY: {output.get('summary', 'MISSING')}")
    
    stocks = output.get('candidate_stocks', [])
    print(f"\n🏢 CANDIDATE STOCKS ({len(stocks)} found):")
    
    for i, stock in enumerate(stocks, 1):
        print(f"\n  {i}. {stock.get('ticker', 'MISSING')}")
        print(f"     📈 Mentions: {stock.get('mention_count', 'MISSING')}")
        print(f"     😊 Sentiment: {stock.get('average_sentiment', 'MISSING')}")
        print(f"     ⭐ Relevance: {stock.get('relevance_score', 'MISSING')}")
        print(f"     💭 Rationale: {stock.get('rationale', 'MISSING')[:100]}...")
    
    # Show data types for downstream agents
    print(f"\n🔧 DATA TYPES FOR DOWNSTREAM AGENTS:")
    print(f"  - sector: {type(output.get('sector')).__name__}")
    print(f"  - candidate_stocks: {type(output.get('candidate_stocks')).__name__} with {len(stocks)} items")
    print(f"  - summary: {type(output.get('summary')).__name__}")
    
    if stocks:
        print(f"  - First stock ticker: {type(stocks[0].get('ticker')).__name__}")
        print(f"  - First stock mention_count: {type(stocks[0].get('mention_count')).__name__}")
        print(f"  - First stock average_sentiment: {type(stocks[0].get('average_sentiment')).__name__}")

if __name__ == "__main__":
    test_market_analyst_output()
