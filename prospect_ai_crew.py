from crewai import Crew, Task
from typing import Dict, Any, List
from agents.market_analyst_agent import MarketAnalystAgent
from agents.technical_analyst_agent import TechnicalAnalystAgent
from agents.fundamental_analyst_agent import FundamentalAnalystAgent
from agents.investor_strategic_agent import InvestorStrategicAgent
from config.config import Config
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM

class ProspectAICrew:
    """Main orchestrator for ProspectAI multi-agent investment analysis"""
    
    def __init__(self):
        """Initialize all agents"""
        self.config = Config()
        self.market_analyst = MarketAnalystAgent()
        self.technical_analyst = TechnicalAnalystAgent()
        self.fundamental_analyst = FundamentalAnalystAgent()
        self.investor_strategist = InvestorStrategicAgent()
        
        self.crew = None
        
    def _get_llm(self):
        """Get the appropriate LLM based on configuration"""
        if self.config.MODEL_PROVIDER == "ollama":
            # Use the format that litellm expects for Ollama
            return OllamaLLM(
                base_url=self.config.OLLAMA_BASE_URL,
                model=f"ollama/{self.config.OLLAMA_MODEL}",  # Add ollama/ prefix
                temperature=0.1,
                format="json"
            )
        else:
            # Default to OpenAI
            return ChatOpenAI(
                model=self.config.OPENAI_MODEL,
                temperature=0.1,
                api_key=self.config.OPENAI_API_KEY
            )
        
    def create_tasks(self, market_criteria: Dict[str, Any]) -> List[Task]:
        """Create the sequence of tasks for the investment analysis workflow"""
        
        sector = market_criteria.get("sector", "Technology")
        
        # Task 1: Market Analysis
        market_analysis_task = Task(
            description=f"""
            Analyze Reddit discussions to identify trending stocks in the {sector} sector.
            
            You have access to specialized Reddit analysis tools:
            - analyze_sector_sentiment: Complete sector analysis (recommended for this task)
            - fetch_reddit_posts: Get Reddit posts for a sector
            - analyze_stock_mentions: Find stock ticker mentions in posts
            - calculate_sentiment: Calculate sentiment scores for stocks
            
            Your task is to:
            1. Use the analyze_sector_sentiment tool to get comprehensive analysis
            2. Review the results and ensure they meet the requirements
            3. If needed, use other tools for deeper analysis
            
            The tool will return a Python dictionary with the exact schema:
            {{
                "sector": "{sector}",
                "candidate_stocks": [
                    {{
                        "ticker": "AAPL",
                        "mention_count": 45,
                        "average_sentiment": 0.7,
                        "relevance_score": 0.82,
                        "rationale": "AAPL is highly discussed on Reddit with bullish sentiment, indicating strong retail investor interest."
                    }}
                ],
                "summary": "Reddit sentiment for {sector} sector is bullish. Top trending stock is AAPL with 45 mentions and bullish sentiment. Retail investors are showing strong interest in 3 stocks in this sector."
            }}
            
            IMPORTANT: Use the tools provided and return ONLY the Python dictionary, no additional text or explanations.
            """,
            agent=self.market_analyst.get_agent(),
            expected_output=f"Python dictionary with {sector} sector analysis and top 5 candidate stocks"
        )
        
        # Task 2: Technical Analysis
        technical_analysis_task = Task(
            description=f"""
            Perform technical analysis on the identified stocks from the {sector} sector.
            Calculate technical indicators, analyze price patterns, and assess technical outlook.
            Output: Technical analysis report for each stock.
            """,
            agent=self.technical_analyst.get_agent(),
            expected_output="Technical analysis report with indicators and patterns",
            context=[market_analysis_task]
        )
        
        # Task 3: Fundamental Analysis
        fundamental_analysis_task = Task(
            description=f"""
            Perform fundamental analysis on the {sector} sector stocks with technical analysis.
            Analyze financial statements, calculate valuation metrics, and assess company fundamentals.
            Output: Comprehensive analysis combining technical and fundamental factors.
            """,
            agent=self.fundamental_analyst.get_agent(),
            expected_output="Fundamental analysis report with financial metrics",
            context=[technical_analysis_task]
        )
        
        # Task 4: Investment Strategy
        investment_strategy_task = Task(
            description=f"""
            Provide final investment recommendations for the {sector} sector based on all previous analysis.
            Assess risk-reward profiles, suggest portfolio allocation, and provide actionable insights.
            Output: Final investment recommendations with risk assessment.
            """,
            agent=self.investor_strategist.get_agent(),
            expected_output="Investment recommendations and portfolio strategy",
            context=[fundamental_analysis_task]
        )
        
        return [
            market_analysis_task,
            technical_analysis_task,
            fundamental_analysis_task,
            investment_strategy_task
        ]
    
    def run_analysis(self, market_criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Run the complete investment analysis workflow"""
        
        # Create tasks
        tasks = self.create_tasks(market_criteria)
        
        # Create crew with LLM configuration
        self.crew = Crew(
            agents=[
                self.market_analyst.get_agent(),
                self.technical_analyst.get_agent(),
                self.fundamental_analyst.get_agent(),
                self.investor_strategist.get_agent()
            ],
            tasks=tasks,
            verbose=True,
            llm=self._get_llm()
        )
        
        # Execute the workflow
        result = self.crew.kickoff()
        
        return {
            "status": "success",
            "workflow_completed": True,
            "result": result,
            "summary": "ProspectAI analysis completed successfully"
        }
