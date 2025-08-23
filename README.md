# ProspectAI - Multi-Agent Investment Analysis System

## Overview

ProspectAI is a sophisticated multi-agent investment analysis system built on the CrewAI framework. It leverages four specialized AI agents to provide comprehensive investment recommendations through a systematic analysis workflow. The system supports both OpenAI and local Ollama models for flexibility and cost control.

## Features

- **Multi-Agent Architecture**: Four specialized AI agents working in sequence
- **Dual Model Support**: OpenAI API or local Ollama models
- **Command-Line Interface**: Easy switching between model providers
- **Comprehensive Analysis**: Market, technical, fundamental, and strategic analysis
- **Flexible Configuration**: Environment-based configuration with command-line overrides

## Architecture

The system consists of four specialized agents working in sequence:

### 1. Market Analyst Agent
- **Role**: Market Research Specialist
- **Responsibility**: Identifies potential investment opportunities based on market trends and criteria
- **Output**: List of screened stocks with initial market assessment

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
├── agents/                 # Agent implementations
│   ├── __init__.py
│   ├── base_agent.py      # Base agent class
│   ├── market_analyst_agent.py
│   ├── technical_analyst_agent.py
│   ├── fundamental_analyst_agent.py
│   └── investor_strategic_agent.py
├── config/                 # Configuration files
│   ├── __init__.py
│   └── config.py          # Main configuration
├── data/                   # Data storage and processing
│   └── __init__.py
├── utils/                  # Utility functions
│   └── __init__.py
├── prospect_ai_crew.py     # Main crew orchestrator
├── main.py                 # Application entry point
├── test_skeleton.py        # Test script
├── run_help.py            # Help and usage guide
├── requirements.txt        # Python dependencies
├── env.example            # Environment variables template
├── .gitignore             # Git ignore file
└── README.md              # This file
```

## Installation

### Prerequisites

- Python 3.9+ (3.12+ recommended)
- pip package manager
- Git (for cloning)

### Option 1: OpenAI Setup (Default)

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd ProspectAI
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp env.example .env
   # Edit .env and add your OpenAI API key
   ```

5. **Run the application**
   ```bash
   python main.py
   ```

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

### Command-Line Options

```bash
# Use OpenAI (default)
python main.py

# Use Ollama with default model (llama3.2:3b)
python main.py --ollama

# Use specific Ollama model
python main.py --ollama --model llama3.2:8b

# Use remote Ollama instance
python main.py --ollama --url http://192.168.1.100:11434 --model mistral:7b
```

### Testing

```bash
# Test with OpenAI
python test_skeleton.py

# Test with Ollama
python test_skeleton.py --ollama --model llama3.2:3b
```

### Help

```bash
python run_help.py
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

### Phase 2: Market Analyst Implementation
- [ ] Market data source integration
- [ ] Stock screening algorithms
- [ ] Market trend analysis

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
