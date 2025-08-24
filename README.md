# ProspectAI - Multi-Agent Investment Analysis System

## Overview

ProspectAI is a sophisticated multi-agent investment analysis system built on the CrewAI framework. It leverages four specialized AI agents to provide comprehensive investment recommendations through a systematic analysis workflow. The system supports both OpenAI and local Ollama models for flexibility and cost control.

**🎉 First Official Release - v1.0.0**

## Features

- **🤖 Multi-Agent System**: Specialized AI agents for different aspects of investment analysis
- **🦙 Dual Model Support**: Choose between OpenAI and Ollama local models
- **📊 Real Reddit Integration**: Live Reddit sentiment analysis for trending stocks (top 5 per sector)
- **🏭 Sector Analysis**: Analyze 5 major sectors (Technology, Healthcare, Finance, Energy, Consumer)
- **⚡ Command-Line Interface**: Easy-to-use CLI with flexible configuration
- **🔒 Environment-Based Config**: Secure configuration management
- **📈 Structured Output**: Consistent, machine-readable analysis results
- **🚀 CrewAI Framework**: Professional multi-agent orchestration
- **📄 PDF Report Generation**: Professional investment reports with decision support tools

## Architecture

The system consists of four specialized agents working in sequence:

### Market Analyst Agent 📊
- **Purpose**: Entry point of the investment pipeline
- **Function**: Analyzes Reddit discussions to identify trending stocks
- **Data Sources**: Real Reddit API integration (r/investing, r/stocks, r/wallstreetbets, etc.)
- **Output**: Top 5 candidate stocks with sentiment scores and relevance metrics (configurable limit)
- **Sectors**: Technology, Healthcare, Finance, Energy, Consumer
- **Features**: Live sentiment analysis, mention counting, relevance scoring, Reddit post analysis
- **Stock Selection**: Automatically selects the top 5 most relevant stocks based on mention frequency and sentiment scores

### Technical Analyst Agent 📈
- **Role**: Technical Analysis Specialist
- **Responsibility**: Performs technical analysis using various indicators and chart patterns
- **Output**: Technical analysis report with calculated indicators and momentum analysis
- **Features**: 13+ technical indicators, momentum scoring, risk assessment

### Fundamental Analyst Agent 🏢
- **Role**: Fundamental Analysis Specialist
- **Responsibility**: Analyzes financial statements and company fundamentals
- **Output**: Comprehensive fundamental analysis with valuation metrics
- **Features**: Financial ratio analysis, growth projections, competitive positioning

### Investor Strategic Agent 🎯
- **Role**: Investment Strategy Specialist
- **Responsibility**: Provides final investment recommendations and portfolio strategy
- **Output**: Investment recommendations with risk-reward assessment and portfolio allocation
- **Features**: Portfolio strategy, risk assessment, action planning, monitoring schedules

## Example Output

Here's an example of the comprehensive investment analysis output from ProspectAI (showing a sample with 3 stocks, but the system analyzes up to 5 stocks per sector):

```json
{
  "sector": "Technology",
  "report_date": "August 24, 2025",
  "analysis_date": "2025-08-24 01:06:06",
  "overall_assessment": "The Technology sector presents exceptional investment opportunities with a strong bullish outlook driven by AI advancements, robust technical momentum, and positive social sentiment. The combination of strong fundamentals, technical indicators, and market sentiment suggests continued upward trajectory for leading tech stocks.",
  "key_highlights": [
    "Strong technical momentum across leading tech stocks with average scores of 6/10",
    "Reddit sentiment analysis shows bullish outlook for AI-focused companies",
    "Technical indicators suggest continued upward trend with low volatility",
    "Portfolio allocation should favor growth stocks with strong fundamentals",
    "Risk-adjusted returns favor overweighting Technology sector",
    "AI and cloud computing leaders show strongest momentum signals"
  ],
  "portfolio_allocation_summary": "Recommended allocation: 40% growth stocks (NVDA, META), 30% established tech (GOOGL, AAPL), 20% emerging tech, 10% defensive positions. Focus on companies with strong technical momentum and positive social sentiment. Consider options strategies for enhanced returns on high-conviction positions.",
  "stock_analyses": [
    {
      "ticker": "NVDA",
      "market_analyst_data": {
        "mention_count": 10,
        "average_sentiment": 0.589,
        "relevance_score": 0.378,
        "reddit_rationale": "Strong bullish sentiment driven by AI product launches and analyst upgrades"
      },
      "technical_score": {
        "percentage": 71.43,
        "grade": "B (Buy)",
        "recommendation": "Buy"
      },
      "momentum_analysis": {
        "momentum_score": 6,
        "risk_level": "Low",
        "trend_strength": "Strong",
        "key_signals": ["Bullish momentum", "Support level identified"]
      },
      "investment_recommendation": "Strong buy recommendation for NVDA based on positive technical momentum, strong Reddit sentiment, and AI leadership position. Consider accumulating on pullbacks to support levels. Recommended position size: 5-8% of portfolio."
    },
    {
      "ticker": "META",
      "market_analyst_data": {
        "mention_count": 17,
        "average_sentiment": 0.32,
        "relevance_score": 0.366,
        "reddit_rationale": "Mixed sentiment due to regulatory concerns but strong technical setup"
      },
      "technical_score": {
        "percentage": 71.43,
        "grade": "B (Buy)",
        "recommendation": "Buy"
      },
      "momentum_analysis": {
        "momentum_score": 6,
        "risk_level": "Low",
        "trend_strength": "Strong",
        "key_signals": ["Bullish momentum", "Resistance level identified"]
      },
      "investment_recommendation": "Cautious buy for META. Strong technical indicators offset regulatory concerns. Monitor regulatory developments and consider position sizing based on risk tolerance. Recommended position size: 3-5% of portfolio."
    },
    {
      "ticker": "GOOGL",
      "market_analyst_data": {
        "mention_count": 3,
        "average_sentiment": 0.719,
        "relevance_score": 0.362,
        "reddit_rationale": "Very positive sentiment around AI and cloud services"
      },
      "technical_score": {
        "percentage": 85.0,
        "grade": "A (Strong Buy)",
        "recommendation": "Strong Buy"
      },
      "momentum_analysis": {
        "momentum_score": 8,
        "risk_level": "Low",
        "trend_strength": "Very Strong",
        "key_signals": ["Strong bullish momentum", "Breakout pattern"]
      },
      "investment_recommendation": "Strong buy for GOOGL with highest technical score and momentum. Excellent risk-reward profile with strong fundamentals. Recommended position size: 8-10% of portfolio."
    }
  ],
  "overall_recommendation": "The Technology sector warrants increased allocation with focus on AI and cloud computing leaders. Maintain diversified exposure while overweighting stocks with strong technical momentum and positive social sentiment. Consider using covered calls on existing positions to generate additional income.",
  "action_items": [
    "Increase Technology sector allocation to 25-30% of portfolio",
    "Initiate positions in GOOGL (8-10%), NVDA (5-8%), and META (3-5%)",
    "Set stop-loss orders at identified support levels",
    "Monitor regulatory developments for META and other social media stocks",
    "Consider options strategies for enhanced returns on high-conviction positions",
    "Rebalance portfolio monthly to maintain target allocations",
    "Implement dollar-cost averaging for new positions"
  ],
  "portfolio_adjustments": "Rebalance portfolio to overweight Technology sector. Reduce exposure to defensive sectors and increase growth allocation. Consider using covered calls on existing tech positions to generate additional income. Maintain 10% cash for opportunistic entries.",
  "overall_risk_level": "Medium",
  "risk_factors": [
    "Market volatility and potential tech sector corrections",
    "Regulatory risks for social media and AI companies",
    "Geopolitical tensions affecting semiconductor supply chains",
    "Interest rate sensitivity of growth stocks",
    "AI bubble concerns and valuation risks",
    "Earnings volatility in high-growth tech companies"
  ],
  "risk_mitigation_strategies": "Implement dollar-cost averaging for new positions, maintain stop-loss orders, diversify across subsectors, and consider hedging strategies. Regular portfolio rebalancing and position sizing based on risk tolerance. Use options for downside protection.",
  "analysis_methodology": "This analysis combines Reddit sentiment analysis, comprehensive technical indicators (13+ indicators), LLM-generated momentum analysis, and fundamental considerations. Data sources include Reddit API, Yahoo Finance, and proprietary technical analysis algorithms. Risk assessment incorporates multiple factors including volatility, correlation, and market conditions.",
  "data_sources": [
    "Reddit API for social sentiment analysis",
    "Yahoo Finance for stock price data and technical indicators",
    "Proprietary technical analysis algorithms",
    "LLM analysis for momentum and risk assessment",
    "Market analyst insights and Reddit community sentiment",
    "Real-time market data and news sentiment analysis"
  ]
}
```

### Command-Line Output Example

When you run ProspectAI, you'll see real-time output like this:

```bash
$ python main.py --sector Technology

🤖 ProspectAI - Multi-Agent Investment Analysis System
====================================================

🔍 MARKET ANALYST AGENT: Analyzing Reddit sentiment for Technology sector...
📊 Fetching Reddit posts from r/investing, r/stocks, r/wallstreetbets...
📈 Analyzing sentiment for 15+ stock mentions...
🎯 Top 5 trending stocks identified:
   • NVDA: 10 mentions, sentiment: 0.589, relevance: 0.378
   • META: 17 mentions, sentiment: 0.32, relevance: 0.366
   • GOOGL: 3 mentions, sentiment: 0.719, relevance: 0.362
   • AAPL: 8 mentions, sentiment: 0.45, relevance: 0.35
   • TSLA: 12 mentions, sentiment: 0.28, relevance: 0.34

🔧 TECHNICAL ANALYST AGENT: Performing technical analysis...
📊 Calculating 13+ technical indicators for each stock...
📈 Momentum analysis and risk assessment...
✅ Technical analysis completed for 5 stocks

🏢 FUNDAMENTAL ANALYST AGENT: Analyzing company fundamentals...
📊 Financial ratios and valuation metrics...
📈 Growth projections and competitive analysis...
✅ Fundamental analysis completed

🎯 INVESTOR STRATEGIC AGENT: Generating investment strategy...
📊 Portfolio allocation recommendations...
⚖️ Risk-reward assessment...
📋 Action plan and monitoring schedule...
✅ Investment strategy completed

📄 GENERATING PROFESSIONAL PDF REPORT...
✅ Enhanced investment report generated: enhanced_investment_report_Technology_20250824_012804.pdf

🎉 ANALYSIS COMPLETE! 
📁 Results saved to: enhanced_investment_report_Technology_20250824_012804.pdf
📊 Summary: Technology sector shows strong bullish momentum with 3 buy recommendations
```

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
│   ├── test_enhanced_pdf_generation.py # PDF generation tests
│   └── run_help.py           # Command-line help utility
├── utils/                    # Utility functions and helpers
│   ├── __init__.py           # Utils package initialization
│   ├── enhanced_pdf_generator.py # Professional PDF report generator
│   ├── pdf_generator.py      # Basic PDF generator
│   ├── reddit_analysis_tool.py # Reddit sentiment analysis tools
│   └── technical_analysis_tool.py # Technical analysis utilities
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

# Test PDF generation
python tests/test_enhanced_pdf_generation.py

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

### Phase 3: Technical Analysis ✅
- ✅ Price data collection
- ✅ Technical indicator calculations (13+ indicators)
- ✅ Chart pattern recognition
- ✅ Momentum analysis and scoring
- ✅ Risk assessment algorithms

### Phase 4: Fundamental Analysis ✅
- ✅ Financial data integration
- ✅ Valuation metrics calculation
- ✅ Company fundamental assessment
- ✅ Growth projections and competitive analysis

### Phase 5: Investment Strategy ✅
- ✅ Portfolio allocation recommendations
- ✅ Risk-reward assessment
- ✅ Action planning and monitoring schedules
- ✅ Decision support tools and matrices

### Phase 6: PDF Generation ✅
- ✅ Professional investment report generation
- ✅ Decision support dashboards
- ✅ Portfolio allocation charts
- ✅ Risk-reward matrices
- ✅ Action plans and monitoring schedules

## Roadmap - Next Product Iterations

### v1.1 - Enhanced Market Analysis
- **Improved market analysis capabilities** to obtain data from financial news APIs more reliable for investors
- Integration with Bloomberg, Reuters, and other financial news sources
- Real-time market sentiment analysis from multiple sources
- Enhanced sector rotation analysis

### v1.2 - Agent Improvements
- **Improved version of Fundamental Analyst and Investor Strategist Agents**
- Enhanced financial modeling capabilities
- More sophisticated valuation algorithms
- Advanced portfolio optimization algorithms

### v1.3 - Investment Strategy PDFs
- **Ability to create investment strategy in PDF**
- Professional report templates
- Interactive decision support tools
- Portfolio visualization and charts

### v1.4 - Advanced Risk Management
- **Inclusion of more complex risk-rewards tools to improve the recommendations**
- Monte Carlo simulations for portfolio scenarios
- Advanced risk metrics (VaR, CVaR, Sharpe ratios)
- Dynamic risk adjustment based on market conditions
- Options and derivatives analysis

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
