#!/usr/bin/env python3
"""
ProspectAI - Multi-Agent Investment Analysis System
Main entry point for the application
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from prospect_ai_crew import ProspectAICrew

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="ProspectAI - Multi-Agent Investment Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # Use OpenAI (default)
  python main.py --ollama                  # Use Ollama with default model
  python main.py --ollama --model llama3.2:8b  # Use specific Ollama model
  python main.py --ollama --url http://192.168.1.100:11434  # Use remote Ollama
        """
    )
    
    parser.add_argument(
        "--ollama", 
        action="store_true",
        help="Use Ollama local models instead of OpenAI"
    )
    
    parser.add_argument(
        "--model", 
        type=str,
        default="llama3.2:3b",
        help="Ollama model to use (default: llama3.2:3b)"
    )
    
    parser.add_argument(
        "--url", 
        type=str,
        default="http://localhost:11434",
        help="Ollama base URL (default: http://localhost:11434)"
    )
    
    return parser.parse_args()

def main():
    """Main function to run ProspectAI analysis"""
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Load environment variables
    load_dotenv()
    
    # Set model provider based on command line arguments
    if args.ollama:
        os.environ["MODEL_PROVIDER"] = "ollama"
        os.environ["OLLAMA_MODEL"] = args.model
        os.environ["OLLAMA_BASE_URL"] = args.url
        print(f"🦙 Using Ollama model: {args.model}")
        print(f"📍 Ollama URL: {args.url}")
    else:
        os.environ["MODEL_PROVIDER"] = "openai"
        # Check for required OpenAI environment variables
        if not os.getenv("OPENAI_API_KEY"):
            print("Error: OPENAI_API_KEY environment variable is required")
            print("Please set your OpenAI API key in a .env file")
            sys.exit(1)
        print("🤖 Using OpenAI model")
    
    # Initialize ProspectAI
    print("🚀 Initializing ProspectAI...")
    prospect_ai = ProspectAICrew()
    
    # Define market criteria (example)
    market_criteria = {
        "sectors": ["Technology", "Healthcare", "Finance"],
        "market_cap_range": {"min": 1000000000, "max": 100000000000},  # 1B to 100B
        "risk_tolerance": "Medium",
        "investment_horizon": "Long-term",
        "geographic_focus": "US"
    }
    
    try:
        # Run the analysis
        print("📊 Starting investment analysis workflow...")
        result = prospect_ai.run_analysis(market_criteria)
        
        # Display results
        print("✅ Analysis completed successfully!")
        print("📈 Results:")
        print(result["summary"])
        
    except Exception as e:
        print(f"❌ Error during analysis: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
