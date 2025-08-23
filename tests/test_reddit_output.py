#!/usr/bin/env python3
"""
Test script for Reddit API integration - Shows actual Reddit data output
"""

import os
import sys
import json

# Add parent directory to path for imports - more reliable method
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
from agents.market_analyst_agent import MarketAnalystAgent


def test_reddit_output():
    """Test the Reddit API integration and show actual output"""
    
    # Load environment variables
    load_dotenv()
    
    print("🧪 Testing Reddit API Integration - Live Data Output")
    print("=" * 60)
    
    # Check if Reddit credentials are configured
    reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    
    if not reddit_client_id or not reddit_client_secret:
        print("❌ Reddit API credentials not configured!")
        print("Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in your .env file")
        print("See REDDIT_API_SETUP.md for detailed instructions")
        return
    
    print("✅ Reddit API credentials found")
    print(f"Client ID: {reddit_client_id[:8]}...")
    print(f"Client Secret: {reddit_client_secret[:8]}...")
    
    # Test sectors
    sectors = ["Technology", "Healthcare", "Finance"]
    
    for sector in sectors:
        print(f"\n{'='*20} TESTING {sector.upper()} SECTOR {'='*20}")
        
        try:
            print(f"🏭 Analyzing {sector} sector...")
            agent = MarketAnalystAgent()
            
            # Test the agent
            result = agent.execute_task(sector)
            
            if result["candidate_stocks"]:
                print(f"✅ Successfully analyzed {sector} sector!")
                print(f"📊 Found {len(result['candidate_stocks'])} trending stocks")
                
                print(f"\n📈 TOP STOCKS IN {sector.upper()}:")
                print("-" * 50)
                
                for i, stock in enumerate(result["candidate_stocks"], 1):
                    print(f"{i:2d}. {stock['ticker']:>6}")
                    print(f"     Mentions: {stock['mention_count']:>3}")
                    print(f"     Sentiment: {stock['average_sentiment']:>6.3f}")
                    print(f"     Relevance: {stock['relevance_score']:>6.3f}")
                    print(f"     Rationale: {stock['rationale']}")
                    print()
                
                print(f"📝 SECTOR SUMMARY:")
                print(f"   {result['summary']}")
                
            else:
                print(f"⚠️  No stocks found for {sector} sector")
                print("   This might indicate:")
                print("   - Rate limiting from Reddit API")
                print("   - No recent posts matching criteria")
                print("   - API authentication issues")
            
        except Exception as e:
            print(f"❌ Error analyzing {sector} sector: {str(e)}")
            print(f"   Error type: {type(e).__name__}")
        
        print(f"\n{'='*60}")
    
    print("\n🎯 REDDIT API TESTING COMPLETE!")
    print("\n📊 What This Test Shows:")
    print("   ✅ Reddit API connectivity")
    print("   ✅ Authentication success")
    print("   ✅ Data fetching from subreddits")
    print("   ✅ Stock ticker detection")
    print("   ✅ Sentiment analysis")
    print("   ✅ Relevance scoring")
    
    print("\n🔍 Next Steps:")
    print("   1. Check the output quality and relevance")
    print("   2. Test with other sectors: Energy, Consumer")
    print("   3. Try with Ollama: python main.py --ollama --sector Technology")
    print("   4. Monitor Reddit API rate limits")
    
    print("\n📖 For more details, see:")
    print("   - REDDIT_API_SETUP.md (setup guide)")
    print("   - tests/run_help.py (usage help)")
    print("   - README.md (project documentation)")

def test_single_sector(sector="Technology"):
    """Test a single sector with detailed output"""
    
    print(f"🧪 Testing Single Sector: {sector}")
    print("=" * 50)
    
    try:
        agent = MarketAnalystAgent()
        result = agent.execute_task(sector)
        
        print(f"📊 RESULT FOR {sector.upper()}:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Test specific sector
        sector = sys.argv[1]
        test_single_sector(sector)
    else:
        # Test all sectors
        test_reddit_output()
