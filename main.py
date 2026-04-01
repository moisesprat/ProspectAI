#!/usr/bin/env python3
"""
ProspectAI - Multi-Agent Investment Analysis System
Main entry point for the application
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv


def load_and_validate_env():
    """Load .env and validate all required keys are present."""
    env_path = Path(".env")
    if not env_path.exists():
        print("Error: .env file not found.")
        print("Copy env.example to .env and fill in your values:")
        print()
        print("  cp env.example .env")
        sys.exit(1)

    load_dotenv(env_path)

    missing = []

    # Anthropic is always required
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not os.getenv("ANTHROPIC_MODEL"):
        missing.append("ANTHROPIC_MODEL")

    # Market data — at least one source required
    has_reddit = os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")
    has_serper = os.getenv("SERPER_API_KEY")
    if not has_reddit and not has_serper:
        missing.append("REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET  (or SERPER_API_KEY)")

    # Ollama keys required only when --ollama flag is active
    if os.getenv("MODEL_PROVIDER") == "ollama":
        if not os.getenv("OLLAMA_BASE_URL"):
            missing.append("OLLAMA_BASE_URL")
        if not os.getenv("OLLAMA_MODEL"):
            missing.append("OLLAMA_MODEL")

    if missing:
        print("Error: the following required keys are missing from your .env file:")
        print()
        for key in missing:
            print(f"  - {key}")
        print()
        print("See env.example for reference.")
        sys.exit(1)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="ProspectAI - Multi-Agent Investment Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                           # Anthropic (default)
  python main.py --model claude-opus-4-6  # Override Claude model
  python main.py --ollama                  # Use local Ollama model
  python main.py --sector Healthcare       # Analyze Healthcare sector
        """
    )

    parser.add_argument(
        "--ollama",
        action="store_true",
        help="Use local Ollama model instead of Anthropic"
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the model from .env (Anthropic or Ollama)"
    )

    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Ollama base URL (overrides OLLAMA_BASE_URL in .env)"
    )

    parser.add_argument(
        "--sector",
        type=str,
        default="Technology",
        choices=["Technology", "Healthcare", "Finance", "Energy", "Consumer"],
        help="Sector to analyze (default: Technology)"
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    # Apply CLI overrides to env before validation
    if args.ollama:
        os.environ["MODEL_PROVIDER"] = "ollama"
    if args.model:
        key = "OLLAMA_MODEL" if args.ollama else "ANTHROPIC_MODEL"
        os.environ[key] = args.model
    if args.url:
        os.environ["OLLAMA_BASE_URL"] = args.url

    load_and_validate_env()

    from prospect_ai_crew import ProspectAICrew

    if args.ollama:
        print(f"Using Ollama model: {os.getenv('OLLAMA_MODEL')} @ {os.getenv('OLLAMA_BASE_URL')}")
    else:
        print(f"Using Anthropic model: {os.getenv('ANTHROPIC_MODEL')}")

    print(f"Analyzing sector: {args.sector}")
    print("Initializing ProspectAI...")
    prospect_ai = ProspectAICrew()

    market_criteria = {
        "sector": args.sector,
        "market_cap_range": {"min": 1000000000, "max": 100000000000},
        "risk_tolerance": "Medium",
        "investment_horizon": "Long-term",
        "geographic_focus": "US"
    }

    try:
        print("Starting investment analysis workflow...")
        result = prospect_ai.run_analysis(market_criteria)
        print("Analysis completed successfully!")
        print("Results:")
        print(result["summary"])
    except Exception as e:
        print(f"Error during analysis: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
