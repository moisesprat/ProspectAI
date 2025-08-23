#!/usr/bin/env python3
"""
Debug script for tool arguments - Test what arguments are actually passed to tools
"""

import os
import sys

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils.reddit_analysis_tool import RedditAnalysisTool

def test_tool_args():
    """Test tool arguments to see what's happening"""
    
    print("🔍 DEBUGGING TOOL ARGUMENTS")
    print("=" * 50)
    
    # Create Reddit tool
    reddit_tool = RedditAnalysisTool()
    analyze_tool = reddit_tool.analyze_sector_sentiment_tool()
    
    print(f"Tool name: {analyze_tool.name}")
    print(f"Tool description: {analyze_tool.description}")
    print(f"Tool args_schema: {analyze_tool.args_schema}")
    
    # Test with different argument formats
    print("\n🧪 TESTING DIFFERENT ARGUMENT FORMATS:")
    print("-" * 40)
    
    # Test 1: Simple string
    print("\n1. Testing with simple string:")
    try:
        result = analyze_tool._run("Technology")
        print(f"✅ Success with 'Technology': {type(result)}")
    except Exception as e:
        print(f"❌ Failed with 'Technology': {str(e)}")
    
    # Test 2: Dict with sector key
    print("\n2. Testing with dict {'sector': 'Technology'}:")
    try:
        result = analyze_tool._run({"sector": "Technology"})
        print(f"✅ Success with {{'sector': 'Technology'}}: {type(result)}")
    except Exception as e:
        print(f"❌ Failed with {{'sector': 'Technology'}}: {str(e)}")
    
    # Test 3: Complex dict (what CrewAI seems to be sending)
    print("\n3. Testing with complex dict:")
    try:
        result = analyze_tool._run({"sector": {"description": "Technology", "type": "str"}})
        print(f"✅ Success with complex dict: {type(result)}")
    except Exception as e:
        print(f"❌ Failed with complex dict: {str(e)}")
    
    # Test 4: Direct function call
    print("\n4. Testing direct function call:")
    try:
        result = reddit_tool._analyze_sector_sentiment("Technology")
        print(f"✅ Success with direct call: {type(result)}")
    except Exception as e:
        print(f"❌ Failed with direct call: {str(e)}")

if __name__ == "__main__":
    test_tool_args()
