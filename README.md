# ProspectAI - Multi-Agent Investment Analysis System

## Overview

ProspectAI is a sophisticated multi-agent investment analysis system built on the CrewAI framework. It leverages four specialized AI agents to provide comprehensive investment recommendations through a systematic analysis workflow.

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
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## Installation

1. **Clone or create the project directory**
   ```bash
   cd ProspectAI
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your OpenAI API key
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

## Configuration

The system can be customized through the `config/config.py` file:

- **Market Data Sources**: Configure data sources for market information
- **Technical Indicators**: Define which technical indicators to calculate
- **Fundamental Metrics**: Specify financial metrics for analysis
- **Risk Assessment**: Customize risk and reward evaluation criteria

## Development Workflow

### Phase 1: Skeleton (Current)
- ✅ Basic project structure
- ✅ Agent class definitions
- ✅ Crew orchestration framework
- ✅ Configuration framework

### Phase 2: Market Analyst Implementation
- [ ] Market data source integration
- [ ] Stock screening algorithms
- [ ] Market trend analysis

### Phase 3: Technical Analyst Implementation
- [ ] Price data collection
- [ ] Technical indicator calculations
- [ ] Chart pattern recognition

### Phase 4: Fundamental Analyst Implementation
- [ ] Financial data integration
- [ ] Valuation metric calculations
- [ ] Industry comparison analysis

### Phase 5: Investment Strategist Implementation
- [ ] Risk-reward assessment
- [ ] Portfolio allocation logic
- [ ] Final recommendation generation

## Usage

### Basic Usage
```python
from prospect_ai_crew import ProspectAICrew

# Initialize the system
prospect_ai = ProspectAICrew()

# Define market criteria
market_criteria = {
    "sectors": ["Technology", "Healthcare"],
    "market_cap_range": {"min": 1000000000, "max": 100000000000},
    "risk_tolerance": "Medium"
}

# Run analysis
result = prospect_ai.run_analysis(market_criteria)
```

### Customizing Agents
Each agent can be customized by extending the base classes and implementing the required methods:

```python
from agents.base_agent import BaseAgent

class CustomAgent(BaseAgent):
    def create_agent(self):
        # Custom agent creation logic
        pass
    
    def execute_task(self, input_data):
        # Custom task execution logic
        pass
```

## Dependencies

- **CrewAI**: Multi-agent orchestration framework
- **LangChain**: LLM integration and tools
- **OpenAI**: Language model API
- **Pandas/Numpy**: Data processing and analysis
- **YFinance**: Financial data access
- **Plotly**: Data visualization

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: OpenAI model to use (default: gpt-4)

## Contributing

This is a skeleton implementation. To contribute:

1. Implement the TODO sections in each agent
2. Add proper error handling and validation
3. Implement data source integrations
4. Add comprehensive testing
5. Enhance the configuration system

## License

This project is for educational and development purposes.

## Next Steps

1. **Set up your OpenAI API key** in the `.env` file
2. **Test the basic skeleton** by running `python main.py`
3. **Implement the Market Analyst Agent** first
4. **Iteratively develop** each agent with proper testing
5. **Add data source integrations** for real market data
6. **Enhance the analysis algorithms** based on your requirements

## Support

For questions or issues, please refer to the CrewAI documentation and ensure all dependencies are properly installed.
