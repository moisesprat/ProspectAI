#!/usr/bin/env python3
"""
Help script showing all available command-line options for ProspectAI
"""

def show_help():
    """Display help information for all ProspectAI commands"""
    
    print("🚀 ProspectAI - Multi-Agent Investment Analysis System")
    print("=" * 60)
    print()
    
    print("📋 Available Commands:")
    print()
    
    print("1️⃣  Main Application (main.py):")
    print("   python main.py                           # Use OpenAI (default)")
    print("   python main.py --ollama                  # Use Ollama with default model")
    print("   python main.py --ollama --model llama3.2:8b")
    print("   python main.py --ollama --url http://192.168.1.100:11434")
    print()
    
    print("2️⃣  Testing (test_skeleton.py):")
    print("   python test_skeleton.py                  # Test with OpenAI")
    print("   python test_skeleton.py --ollama         # Test with Ollama")
    print("   python test_skeleton.py --ollama --model llama3.2:8b")
    print()
    
    print("3️⃣  Utility Scripts:")
    print("   python switch_to_ollama.py               # Switch to Ollama mode")
    print()
    
    print("🔧 Command-Line Options:")
    print()
    print("   --ollama          Use Ollama local models instead of OpenAI")
    print("   --model MODEL     Specify Ollama model (default: llama3.2:3b)")
    print("   --url URL         Specify Ollama base URL (default: localhost:11434)")
    print()
    
    print("🦙 Popular Ollama Models:")
    print("   llama3.2:3b      # Fast, lightweight (default)")
    print("   llama3.2:8b      # Good balance of speed/quality")
    print("   llama3.2:70b     # High quality, slower")
    print("   mistral:7b       # Good for analysis tasks")
    print("   codellama:7b     # Good for code-related tasks")
    print("   neural-chat:7b   # Good for conversation")
    print()
    
    print("📝 Quick Start Examples:")
    print()
    print("   # Test with OpenAI:")
    print("   python test_skeleton.py")
    print()
    print("   # Test with Ollama:")
    print("   python test_skeleton.py --ollama")
    print()
    print("   # Run analysis with Ollama:")
    print("   python main.py --ollama --model llama3.2:8b")
    print()
    
    print("⚠️  Prerequisites:")
    print("   - For OpenAI: Set OPENAI_API_KEY in .env file")
    print("   - For Ollama: Install and start Ollama service")
    print("   - For Ollama: Pull desired model (e.g., ollama pull llama3.2:3b)")

if __name__ == "__main__":
    show_help()
