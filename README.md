# ProspectAI - Multi-Agent Investment Analysis System

## Overview

ProspectAI is a sophisticated multi-agent investment analysis system built on the CrewAI framework. It leverages four specialized AI agents to provide comprehensive investment recommendations through a systematic analysis workflow. The system supports both OpenAI and local Ollama models for flexibility and cost control.

## Features

- **🤖 Multi-Agent System**: Specialized AI agents for different aspects of investment analysis
- **🦙 Dual Model Support**: Choose between OpenAI and Ollama local models
- **📊 Real Reddit Integration**: Live Reddit sentiment analysis for trending stocks
- **🏭 Sector Analysis**: Analyze 5 major sectors (Technology, Healthcare, Finance, Energy, Consumer)
- **⚡ Command-Line Interface**: Easy-to-use CLI with flexible configuration
- **🔒 Environment-Based Config**: Secure configuration management
- **📈 Structured Output**: Consistent, machine-readable analysis results
- **🚀 CrewAI Framework**: Professional multi-agent orchestration

## Architecture

The system consists of four specialized agents working in sequence:

### Market Analyst Agent 📊
- **Purpose**: Entry point of the investment pipeline
- **Function**: Analyzes Reddit discussions to identify trending stocks
- **Data Sources**: Real Reddit API integration (r/investing, r/stocks, r/wallstreetbets, etc.)
- **Output**: Top 5 candidate stocks with sentiment scores and relevance metrics
- **Sectors**: Technology, Healthcare, Finance, Energy, Consumer
- **Features**: Live sentiment analysis, mention counting, relevance scoring

### 2. Technical Analyst Agent
- **Role**: Technical Analysis Specialist
- **Responsibility**: Performs technical analysis using various indicators and chart patterns
- **Output**: Technical analysis report with calculated indicators

### 3. Fundamental Analyst Agent
- **Role**: Fundamental Analysis Specialist
- **Responsibility**: Analyzes financial statements and company fundamentals
- **Output**: Comprehensive fundamental analysis with valuation metrics

### 4. Investor Strategic Agent
- **Role**: Investment Strategy Specialist
- **Responsibility**: Provides final investment recommendations and portfolio strategy
- **Output**: Investment recommendations with risk-reward assessment

## Project Structure

```
ProspectAI/
├── agents/                    # AI agent implementations
│   ├── __init__.py           # Agent package initialization
│   ├── base_agent.py         # Abstract base class for all agents
│   ├── market_analyst_agent.py    # Reddit sentiment analysis agent
│   ├── technical_analyst_agent.py # Technical analysis agent
│   ├── fundamental_analyst_agent.py # Fundamental analysis agent
│   └── investor_strategic_agent.py # Investment strategy agent
├── config/                   # Configuration management
│   ├── __init__.py           # Config package initialization
│   └── config.py             # Centralized configuration class
├── data/                     # Data storage and management
│   └── __init__.py           # Data package initialization
├── tests/                    # Test suite and utilities
│   ├── __init__.py           # Tests package initialization
│   ├── test_skeleton.py      # Basic functionality tests
│   ├── test_reddit_output.py # Reddit API integration tests
│   └── run_help.py           # Command-line help utility
├── utils/                    # Utility functions and helpers
│   └── __init__.py           # Utils package initialization
├── main.py                   # Main application entry point
├── prospect_ai_crew.py       # CrewAI workflow orchestration
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create from .env.example)
├── .env.example             # Environment variables template
├── .gitignore               # Git ignore patterns
├── REDDIT_API_SETUP.md      # Reddit API configuration guide
└── README.md                 # This file
```

## Installation

### Prerequisites
- Python 3.9+
- Ollama (for local models)
- Reddit API credentials (for Market Analyst Agent)

### 1. Clone and Setup
```bash
git clone <your-repo-url>
cd ProspectAI
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Reddit API Setup (Required for Market Analyst)
1. **Create Reddit App**: Visit [Reddit App Preferences](https://www.reddit.com/prefs/apps)
2. **Get Credentials**: Create a "script" app and note your Client ID and Secret
3. **Configure Environment**: Copy `env.example` to `.env` and add your Reddit credentials
4. **Test**: Run `python main.py --sector Technology` to verify Reddit integration

📖 **Detailed Setup**: See [REDDIT_API_SETUP.md](REDDIT_API_SETUP.md) for complete instructions.

### Option 2: Ollama Setup (Local Models)

1. **Install Ollama**
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

2. **Start Ollama service**
   ```bash
   ollama serve
   ```

3. **Pull a model**
   ```bash
   ollama pull llama3.2:3b
   # or any other model like: llama3.2:8b, mistral:7b, codellama:7b
   ```

4. **Run with Ollama**
   ```bash
   python main.py --ollama --model llama3.2:3b
   ```

## Usage

### Basic Usage

```bash
# Analyze Technology sector with OpenAI (default)
python main.py

# Analyze specific sector with OpenAI
python main.py --sector Healthcare
python main.py --sector Finance
python main.py --sector Energy
python main.py --sector Consumer

# Use Ollama local models
python main.py --ollama --sector Technology
python main.py --ollama --model llama3:latest --sector Healthcare

# Use remote Ollama server
python main.py --ollama --url http://192.168.1.100:11434 --sector Finance
```

### Testing

```bash
# Test basic functionality
python tests/test_skeleton.py

# Test with Ollama
python tests/test_skeleton.py --ollama --model llama3:latest

# Test Reddit API integration
python tests/test_reddit_output.py

# Test specific sector
python tests/test_reddit_output.py Technology
python tests/test_reddit_output.py Healthcare

# Get help and usage information
python tests/run_help.py
```

## Configuration

### Environment Variables

Create a `.env` file based on `env.example`:

```bash
# Model Provider Configuration
MODEL_PROVIDER=openai  # or "ollama"

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4

# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

### Popular Ollama Models

- **llama3.2:3b** - Fast, lightweight (default)
- **llama3.2:8b** - Good balance of speed/quality
- **llama3.2:70b** - High quality, slower
- **mistral:7b** - Good for analysis tasks
- **codellama:7b** - Good for code-related tasks
- **neural-chat:7b** - Good for conversation

## Development Workflow

### Phase 1: Skeleton (Current)
- ✅ Basic project structure
- ✅ Agent class definitions
- ✅ Crew orchestration framework
- ✅ Configuration framework
- ✅ Dual model support (OpenAI + Ollama)
- ✅ Command-line interface
- ✅ Testing framework

### Phase 2: Market Analyst Implementation ✅
- ✅ Real Reddit API integration (no more simulation!)
- ✅ Sector-based stock identification
- ✅ Live sentiment analysis from Reddit posts
- ✅ Top 5 stock selection algorithm
- ✅ Structured output format
- ✅ Integration with CrewAI workflow
- ✅ Comprehensive Reddit API setup guide

### Phase 3: Technical Analysis
- [ ] Price data collection
- [ ] Technical indicator calculations
- [ ] Chart pattern recognition

### Phase 4: Fundamental Analysis
- [ ] Financial data integration
- [ ] Valuation metrics calculation
- [ ] Company fundamental assessment

### Phase 5: Integration & Testing
- [ ] End-to-end workflow testing
- [ ] Performance optimization
- [ ] User interface development

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure you're using the virtual environment where packages are installed
2. **Ollama connection**: Verify Ollama is running with `ollama serve`
3. **Model not found**: Pull the model first with `ollama pull <model-name>`
4. **API key errors**: Check your `.env` file and API key validity

### Getting Help

- Run `python run_help.py` for usage examples
- Check the test script: `python test_skeleton.py`
- Verify your Python environment and package installation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]

## Acknowledgments

- Built on the [CrewAI](https://github.com/joaomdmoura/crewAI) framework
- Inspired by modern multi-agent AI systems
- Community contributions welcome
