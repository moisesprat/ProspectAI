#!/usr/bin/env python3
"""
Test skeleton for ProspectAI - Tests basic functionality and imports
"""

import os
import sys
import argparse

# Add parent directory to path for imports - more reliable method
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from dotenv import load_dotenv
from agents import BaseAgent, MarketAnalystAgent, TechnicalAnalystAgent, FundamentalAnalystAgent, InvestorStrategicAgent
from prospect_ai_crew import ProspectAICrew

def test_imports():
    """Test that all required modules can be imported"""
    print("🧪 Testing imports...")
    
    try:
        from agents import BaseAgent, MarketAnalystAgent, TechnicalAnalystAgent, FundamentalAnalystAgent, InvestorStrategicAgent
        print("✅ All agent classes imported successfully")
        
        from prospect_ai_crew import ProspectAICrew
        print("✅ ProspectAICrew imported successfully")
        
        from config.config import Config
        print("✅ Config imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_agent_creation():
    """Test that agents can be created"""
    print("\n🧪 Testing agent creation...")
    
    try:
        from agents import MarketAnalystAgent, TechnicalAnalystAgent, FundamentalAnalystAgent, InvestorStrategicAgent
        
        # Test Market Analyst Agent
        market_agent = MarketAnalystAgent()
        print("✅ Market Analyst Agent created successfully")
        
        # Test Technical Analyst Agent
        technical_agent = TechnicalAnalystAgent()
        print("✅ Technical Analyst Agent created successfully")
        
        # Test Fundamental Analyst Agent
        fundamental_agent = FundamentalAnalystAgent()
        print("✅ Fundamental Analyst Agent created successfully")
        
        # Test Investor Strategic Agent
        investor_agent = InvestorStrategicAgent()
        print("✅ Investor Strategic Agent created successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent creation error: {e}")
        return False

def test_crew_creation():
    """Test that ProspectAI crew can be created"""
    print("\n🧪 Testing crew creation...")
    
    try:
        from prospect_ai_crew import ProspectAICrew
        
        crew = ProspectAICrew()
        print("✅ ProspectAI Crew created successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Crew creation error: {e}")
        return False

def test_config():
    """Test configuration loading"""
    print("\n🧪 Testing configuration...")
    
    try:
        from config.config import Config
        
        config = Config()
        print("✅ Configuration loaded successfully")
        
        # Test some config values
        print(f"   Model Provider: {config.MODEL_PROVIDER}")
        print(f"   OpenAI Model: {config.OPENAI_MODEL}")
        print(f"   Ollama Model: {config.OLLAMA_MODEL}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description="Test ProspectAI functionality")
    parser.add_argument("--ollama", action="store_true", help="Test with Ollama configuration")
    parser.add_argument("--model", type=str, default="llama3.2:3b", help="Ollama model to test")
    
    args = parser.parse_args()
    
    print("🚀 ProspectAI Test Suite")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    # Set test configuration
    if args.ollama:
        os.environ["MODEL_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = args.model
        print(f"🦙 Testing with Ollama model: {args.model}")
    else:
        os.environ["MODEL_PROVIDER"] = "openai"
        print("🤖 Testing with OpenAI configuration")
    
    # Run tests
    tests = [
        test_imports,
        test_agent_creation,
        test_crew_creation,
        test_config
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! ProspectAI is ready to use.")
        print("\n🚀 Next steps:")
        if args.ollama:
            print("   - Test with: python main.py --ollama --sector Technology")
            print("   - Try other models: python main.py --ollama --model llama3.2:8b")
        else:
            print("   - Test with: python main.py --sector Technology")
            print("   - Try Ollama: python main.py --ollama --sector Healthcare")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("   - Ensure virtual environment is activated")
        print("   - Check if all dependencies are installed")
        print("   - Verify configuration in .env file")

if __name__ == "__main__":
    main()
