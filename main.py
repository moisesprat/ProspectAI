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


def _global_model_configured() -> bool:
    """MODEL preferred; legacy provider-specific model vars are fallback."""
    if os.getenv("MODEL", "").strip():
        return True
    if os.getenv("MODEL_PROVIDER", "anthropic") == "ollama":
        return bool(os.getenv("OLLAMA_MODEL", "").strip())
    return bool(os.getenv("ANTHROPIC_MODEL", "").strip())


def load_and_validate_env():
    """Load .env if present (local dev), otherwise rely on environment variables (Modal, CI)."""
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)

    missing = []

    provider = os.getenv("MODEL_PROVIDER", "anthropic")
    if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")

    # Market data — at least one source required
    has_reddit = os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")
    has_serper = os.getenv("SERPER_API_KEY")
    if not has_reddit and not has_serper:
        missing.append("REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET  (or SERPER_API_KEY)")

    # Provider-specific required vars
    if provider == "ollama":
        if not os.getenv("OLLAMA_BASE_URL"):
            missing.append("OLLAMA_BASE_URL")

    if not _global_model_configured():
        missing.append("MODEL (or legacy ANTHROPIC_MODEL / OLLAMA_MODEL)")

    if missing:
        print("Error: the following required environment variables are not set:")
        print()
        for key in missing:
            print(f"  - {key}")
        print()
        print("Set them in .env (local) or via Modal secrets (Modal deployment).")
        sys.exit(1)


def _get_version() -> str:
    try:
        from importlib.metadata import version
        return version("prospectai")
    except Exception:
        pass
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return "unknown"
    try:
        pyproject = Path(__file__).parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return "unknown"


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="prospectai",
        description="ProspectAI - Multi-Agent Investment Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands / Options:
  --sector SECTOR    Sector to analyze. Choices: Technology (default), Healthcare,
                     Finance, Energy, Consumer
  --model MODEL      Override the global MODEL env var for this run (raw model id,
                     e.g. claude-opus-4-6 or qwen3.5:9b)
  --ollama           Switch provider to Ollama (local inference)
  --url URL          Ollama base URL; overrides OLLAMA_BASE_URL in .env
  --version          Show version and exit
  --help / -h        Show this help message and exit

Examples:
  prospectai                                   # Anthropic, Technology sector (default)
  prospectai --sector Healthcare               # Analyze Healthcare sector
  prospectai --model claude-opus-4-6          # Override global MODEL
  prospectai --ollama --model qwen3.5:9b      # Use local Ollama model
  prospectai --ollama --url http://localhost:11434 --sector Finance
  prospectai --version                         # Print version
        """
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"ProspectAI {_get_version()}"
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
        help="Override global MODEL for this run (raw model id)"
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
    env_path = Path(".env")
    if env_path.exists():
        load_dotenv(env_path)

    args = parse_arguments()

    # Apply CLI overrides to env before validation
    if args.ollama:
        os.environ["MODEL_PROVIDER"] = "ollama"
    elif not os.getenv("MODEL_PROVIDER"):
        os.environ["MODEL_PROVIDER"] = "anthropic"
    if args.model:
        os.environ["MODEL"] = args.model.strip()
    if args.url:
        os.environ["OLLAMA_BASE_URL"] = args.url

    load_and_validate_env()

    # Set MODEL for CrewAI env fallback as provider/model_id.
    raw_model = (
        os.getenv("MODEL")
        or (
            os.getenv("OLLAMA_MODEL")
            if os.getenv("MODEL_PROVIDER", "anthropic") == "ollama"
            else os.getenv("ANTHROPIC_MODEL")
        )
        or ""
    ).strip()
    if "/" in raw_model:
        raw_model = raw_model.split("/", 1)[1].strip()
    provider = os.getenv("MODEL_PROVIDER", "anthropic")
    os.environ["MODEL"] = f"{provider}/{raw_model}"

    from prospect_ai_crew import ProspectAICrew

    if provider == "ollama":
        print(f"MODEL_PROVIDER=ollama | global model id: {raw_model} @ {os.getenv('OLLAMA_BASE_URL')}")
    else:
        print(f"MODEL_PROVIDER=anthropic | global model id: {raw_model}")

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
