#!/usr/bin/env python3
"""
Test script to verify ProspectAI skeleton is working
"""

import os
import argparse
from dotenv import load_dotenv

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Test ProspectAI skeleton with different model providers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_skeleton.py                    # Test with OpenAI (default)
  python test_skeleton.py --ollama           # Test with Ollama
  python test_skeleton.py --ollama --model llama3.2:8b  # Test with specific model
        """
    )
    
    parser.add_argument(
        "--ollama", 
        action="store_true",
        help="Test with Ollama local models instead of OpenAI"
    )
    
    parser.add_argument(
        "--model", 
        type=str,
        default="llama3.2:3b",
        help="Ollama model to use for testing (default: llama3.2:3b)"
    )
    
    return parser.parse_args()

def test_imports():
    """Test that all modules can be imported successfully"""
    try:
        from agents import BaseAgent, MarketAnalystAgent, TechnicalAnalystAgent, FundamentalAnalystAgent, InvestorStrategicAgent
        from prospect_ai_crew import ProspectAICrew
        from config.config import Config
        print("✅ All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_agent_creation():
    """Test that agents can be created"""
    try:
        from agents import MarketAnalystAgent, TechnicalAnalystAgent, FundamentalAnalystAgent, InvestorStrategicAgent
        market_agent = MarketAnalystAgent()
        technical_agent = TechnicalAnalystAgent()
        fundamental_agent = FundamentalAnalystAgent()
        strategic_agent = InvestorStrategicAgent()
        print("✅ All agents created successfully!")
        return True
    except Exception as e:
        print(f"❌ Agent creation error: {e}")
        return False

def test_crew_creation():
    """Test that the crew can be created"""
    try:
        from prospect_ai_crew import ProspectAICrew
        crew = ProspectAICrew()
        print("✅ Crew created successfully!")
        return True
    except Exception as e:
        print(f"❌ Crew creation error: {e}")
        return False

def main():
    """Run all tests"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Load environment variables
    load_dotenv()
    
    # Set model provider based on command line arguments
    if args.ollama:
        os.environ["MODEL_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = args.model
        print(f"🦙 Testing with Ollama model: {args.model}")
    else:
        os.environ["MODEL_PROVIDER"] = "openai"
        print("🤖 Testing with OpenAI model")
    
    print("🧪 Testing ProspectAI Skeleton...")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Agent Creation Test", test_agent_creation),
        ("Crew Creation Test", test_crew_creation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"🔍 Running {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed!")
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! ProspectAI skeleton is working correctly.")
        print("Next steps:")
        if args.ollama:
            print("1. Ensure Ollama is running: ollama serve")
            print("2. Pull your model: ollama pull " + args.model)
            print("3. Run the main application: python main.py --ollama --model " + args.model)
        else:
            print("1. Set up your OpenAI API key in .env file")
            print("2. Start implementing the Market Analyst Agent")
            print("3. Run the main application: python main.py")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    main()
