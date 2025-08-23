#!/usr/bin/env python3
"""
Debug script for Reddit tool - Investigate sector-specific data fetching
"""

import os
import sys

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
from utils.reddit_analysis_tool import RedditAnalysisTool

def debug_reddit_tool():
    """Debug the Reddit tool to see what's happening with different sectors"""
    
    # Load environment variables
    load_dotenv()
    
    print("🔍 DEBUGGING REDDIT TOOL")
    print("=" * 50)
    
    # Check Reddit credentials
    reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
    reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    
    if not reddit_client_id or not reddit_client_secret:
        print("❌ Reddit API credentials not configured!")
        return
    
    print("✅ Reddit API credentials found")
    
    # Create Reddit tool
    reddit_tool = RedditAnalysisTool()
    
    # Test sectors
    sectors = ["Technology", "Finance", "Healthcare"]
    
    for sector in sectors:
        print(f"\n{'='*20} DEBUGGING {sector.upper()} SECTOR {'='*20}")
        
        try:
            # Test the main analysis function
            print(f"🔍 Analyzing {sector} sector...")
            result = reddit_tool._analyze_sector_sentiment(sector)
            
            print(f"📊 RESULT:")
            print(f"   Sector: {result['sector']}")
            print(f"   Stocks found: {len(result['candidate_stocks'])}")
            
            if result['candidate_stocks']:
                print(f"   Top stocks:")
                for i, stock in enumerate(result['candidate_stocks'][:3], 1):
                    print(f"     {i}. {stock['ticker']} - {stock['mention_count']} mentions, sentiment: {stock['average_sentiment']:.3f}")
            else:
                print("   ⚠️  No stocks found!")
            
            print(f"   Summary: {result['summary'][:100]}...")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            print(f"   Error type: {type(e).__name__}")

if __name__ == "__main__":
    debug_reddit_tool()
