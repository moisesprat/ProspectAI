#!/usr/bin/env python3
"""
ProspectAI - Help and Usage Guide
"""

def print_help():
    """Print comprehensive help information"""
    
    print("🚀 ProspectAI - Multi-Agent Investment Analysis System")
    print("=" * 60)
    print()
    
    print("📋 AVAILABLE COMMANDS:")
    print()
    
    print("1️⃣  MAIN APPLICATION:")
    print("   python main.py [options]")
    print("   - Default: Uses OpenAI with Technology sector")
    print("   - Options: --ollama, --model, --url, --sector")
    print()
    
    print("2️⃣  TESTING:")
    print("   python tests/test_skeleton.py [options]")
    print("   - Tests basic functionality and imports")
    print("   - Options: --ollama, --model")
    print()
    
    print("3️⃣  REDDIT API SETUP:")
    print("   - Required for Market Analyst Agent")
    print("   - See REDDIT_API_SETUP.md for detailed instructions")
    print("   - Quick setup: Create Reddit app at https://www.reddit.com/prefs/apps")
    print()
    
    print("🔧 CONFIGURATION OPTIONS:")
    print()
    
    print("📊 MODEL PROVIDERS:")
    print("   --ollama                    Use Ollama local models")
    print("   --model MODEL_NAME         Specify Ollama model (default: llama3.2:3b)")
    print("   --url OLLAMA_URL          Custom Ollama server URL")
    print()
    
    print("🏭 SECTOR ANALYSIS:")
    print("   --sector SECTOR            Analyze specific sector")
    print("   Available sectors: Technology, Healthcare, Finance, Energy, Consumer")
    print()
    
    print("📝 USAGE EXAMPLES:")
    print()
    
    print("🔴 OpenAI (Default):")
    print("   python main.py                           # Technology sector with OpenAI")
    print("   python main.py --sector Healthcare      # Healthcare sector with OpenAI")
    print()
    
    print("🦙 Ollama (Local):")
    print("   python main.py --ollama                 # Technology sector with Ollama")
    print("   python main.py --ollama --sector Finance # Finance sector with Ollama")
    print("   python main.py --ollama --model llama3:latest --sector Energy")
    print()
    
    print("🌐 Remote Ollama:")
    print("   python main.py --ollama --url http://192.168.1.100:11434 --sector Consumer")
    print()
    
    print("🧪 TESTING EXAMPLES:")
    print("   python tests/test_skeleton.py                  # Test with OpenAI")
    print("   python tests/test_skeleton.py --ollama        # Test with Ollama")
    print("   python tests/test_skeleton.py --ollama --model llama3:latest")
    print()
    
    print("📊 REDDIT API TESTING:")
    print("   python tests/test_reddit_output.py             # Test all sectors")
    print("   python tests/test_reddit_output.py Technology  # Test specific sector")
    print("   python tests/test_reddit_output.py Healthcare  # Test specific sector")
    print()
    
    print("❓ HELP AND UTILITIES:")
    print("   python tests/run_help.py                      # This help file")
    print()
    
    print("⚙️  ENVIRONMENT VARIABLES:")
    print("   MODEL_PROVIDER            openai or ollama")
    print("   OPENAI_API_KEY           Your OpenAI API key")
    print("   OPENAI_MODEL             OpenAI model name")
    print("   OLLAMA_BASE_URL          Ollama server URL")
    print("   OLLAMA_MODEL             Ollama model name")
    print("   REDDIT_CLIENT_ID         Reddit API client ID")
    print("   REDDIT_CLIENT_SECRET     Reddit API client secret")
    print()
    
    print("📚 AVAILABLE OLLAMA MODELS:")
    print("   llama3:latest            Meta's Llama 3 (recommended)")
    print("   llama3.2:3b              Llama 3.2 3B parameter model")
    print("   llama3.2:8b              Llama 3.2 8B parameter model")
    print("   llama3.2:70b             Llama 3.2 70B parameter model")
    print("   mistral:7b               Mistral 7B model")
    print("   codellama:7b             Code-optimized Llama model")
    print()
    
    print("🔍 TROUBLESHOOTING:")
    print("   - Import errors: Ensure virtual environment is activated")
    print("   - Ollama errors: Check if Ollama is running (ollama serve)")
    print("   - Reddit errors: Verify API credentials in .env file")
    print("   - Rate limits: Reddit API allows 1000 requests per 10 minutes")
    print()
    
    print("📖 DOCUMENTATION:")
    print("   README.md                 Main project documentation")
    print("   REDDIT_API_SETUP.md      Reddit API configuration guide")
    print("   env.example              Environment variables template")
    print()
    
    print("🎯 NEXT STEPS:")
    print("   1. Set up Reddit API credentials (see REDDIT_API_SETUP.md)")
    print("   2. Test with: python main.py --sector Technology")
    print("   3. Try Ollama: python main.py --ollama --sector Healthcare")
    print("   4. Explore other sectors and models")
    print()
    
    print("=" * 60)
    print("💡 Tip: Use --help with any command for detailed options")
    print("   Example: python main.py --help")

if __name__ == "__main__":
    print_help()
