# ProspectAI - Multi-Agent Investment Analysis System

## Overview

ProspectAI is a multi-agent investment analysis system built on the CrewAI framework. It leverages four specialized AI agents to provide comprehensive investment recommendations through a systematic analysis workflow. The system supports both OpenAI and local Ollama models for flexibility and cost control.

**🎉 First Official Release - v1.0.0**

### ⚠️ Important Disclaimer

**ProspectAI is built for educational purposes to help developers get initiated in Agentic AI development.** 

**🚨 INVESTMENT WARNING: This tool should NOT be used as an investment tool without proper knowledge of the investment domain. The analysis provided is for educational demonstration of AI capabilities and should not be considered as financial advice. Always consult with qualified financial professionals before making investment decisions.**

## Features

- **🤖 Multi-Agent System**: Specialized AI agents for different aspects of investment analysis
- **🦙 Dual Model Support**: Choose between OpenAI and Ollama local models
- **📊 Real Reddit Integration**: Live Reddit sentiment analysis for trending stocks (top 5 per sector)
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

ProspectAI generates comprehensive investment analysis through a multi-agent workflow. The final output comes from the Investor Strategic Agent, which synthesizes all previous analysis into actionable investment recommendations. Here's the actual final output from the complete application:

```
### Final Investment Recommendations for the Technology Sector

Based on the comprehensive analysis of selected technology stocks, the following investment recommendations are made, including risk-reward profiles, suggested portfolio allocations, and actionable insights.

#### 1. **Nvidia Corporation (NVDA)**
- **Recommendation:** Buy
- **Risk-Reward Profile:** High growth potential with moderate risk. The high P/E ratio indicates potential overvaluation, but strong fundamentals and market leadership in AI and GPU technology support future growth.
- **Portfolio Allocation:** 20%
- **Actionable Insight:** Consider entering a position on any pullbacks to the $160-$170 range to capitalize on long-term growth in AI and gaming sectors.

#### 2. **Meta Platforms, Inc. (META)**
- **Recommendation:** Buy
- **Risk-Reward Profile:** Moderate risk with solid growth prospects. The reasonable P/E ratio and strong cash flow provide a buffer against market volatility.
- **Portfolio Allocation:** 25%
- **Actionable Insight:** Accumulate shares gradually, especially if the stock dips below $700, to take advantage of its strong advertising revenue and potential in the metaverse.

#### 3. **Alphabet Inc. (GOOGL)**
- **Recommendation:** Buy
- **Risk-Reward Profile:** Moderate risk with stable growth. The low debt levels and strong cash flow support continued investment in innovation, despite a slightly overvalued stock.
- **Portfolio Allocation:** 20%
- **Actionable Insight:** Look for entry points around $200-$205, as Alphabet continues to dominate the online advertising space and expand its cloud services.

#### 4. **Amazon.com, Inc. (AMZN)**
- **Recommendation:** Buy
- **Risk-Reward Profile:** High risk due to high P/E ratio and low operating margins, but significant growth potential in e-commerce and AWS. The aggressive growth strategy may lead to volatility.
- **Portfolio Allocation:** 15%
- **Actionable Insight:** Consider dollar-cost averaging into the position, especially if the stock retraces to the $210-$220 range, to mitigate risk while benefiting from long-term growth.

#### 5. **Salesforce, Inc. (CRM)**
- **Recommendation:** Buy
- **Risk-Reward Profile:** Moderate risk with potential for growth. The solid gross margin indicates pricing power, but the low operating margin suggests ongoing investment in growth may limit short-term profitability.
- **Portfolio Allocation:** 20%
- **Actionable Insight:** Look for opportunities to buy on dips, particularly if the stock approaches the $230 mark, as Salesforce continues to expand its market share in CRM solutions.

### Overall Portfolio Strategy
- **Total Allocation:** 100%
- **Diversification:** The portfolio is diversified across various technology sub-sectors, including AI (Nvidia), social media and advertising (Meta), search and cloud services (Alphabet), e-commerce and cloud computing (Amazon), and CRM solutions (Salesforce).
- **Risk Management:** Regularly review the portfolio and adjust allocations based on market conditions and individual stock performance. Consider setting stop-loss orders to protect against significant downturns.

### Conclusion
The technology sector presents strong investment opportunities with a favorable risk-reward profile. The recommended stocks are well-positioned for growth, supported by solid fundamentals and positive technical indicators. Investors should consider these recommendations as part of a diversified investment strategy to capitalize on the ongoing advancements in technology.
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

🎉 ANALYSIS COMPLETE! 
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
│   └── run_help.py           # Command-line help utility
├── utils/                    # Utility functions and helpers
│   ├── __init__.py           # Utils package initialization
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



### v1.3 - Advanced Risk Management
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

This project is licensed under the **MIT License** - the most permissive and business-friendly open source license available.

```
MIT License

Copyright (c) 2025 ProspectAI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### What MIT License Means for You:

✅ **Use freely** - Personal, commercial, or educational use  
✅ **Modify and adapt** - Customize for your needs  
✅ **Distribute** - Share with others  
✅ **Commercial use** - Use in business applications  
✅ **No attribution required** - Though appreciated  
✅ **No warranty** - Use at your own risk  

This license makes ProspectAI accessible to everyone while protecting contributors from liability.

## Acknowledgments

- Built on the [CrewAI](https://github.com/joaomdmoura/crewAI) framework
- Inspired by modern multi-agent AI systems
- Community contributions welcome
