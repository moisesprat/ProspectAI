from crewai import Crew, Task
from typing import Dict, Any, List

from crewai.tools import BaseTool
from crewai_tools import SerperDevTool, ScrapeWebsiteTool, PDFSearchTool, CSVSearchTool, CodeInterpreterTool, RagTool, YoutubeVideoSearchTool
from agents.market_analyst_agent import MarketAnalystAgent
from agents.technical_analyst_agent import TechnicalAnalystAgent
from agents.fundamental_analyst_agent import FundamentalAnalystAgent
from agents.investor_strategic_agent import InvestorStrategicAgent
from config.config import Config
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaLLM

from utils.technical_analysis_tool import TechnicalAnalysisTool

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
      
    def create_market_analysys_tools(self) -> List[BaseTool]:
        """Create the tools for the market analysis"""
        return [ 
            SerperDevTool(),
            ScrapeWebsiteTool(),
            PDFSearchTool(),
            CSVSearchTool(),
            CodeInterpreterTool(),
            RagTool(),
            YoutubeVideoSearchTool()
        ]

    def create_tasks(self, market_criteria: Dict[str, Any]) -> List[Task]:
        """Create the sequence of tasks for the investment analysis workflow"""
        
        sector = market_criteria.get("sector", "Technology")
        
        # Market Analysis Task
        market_analysis_task = Task(
            description=f"""Analyze Reddit discussions to identify trending stocks in the {sector} sector.
            
            You have access to specialized Reddit analysis tools:
            - analyze_sector_sentiment: Complete sector analysis (recommended for this task)
            - fetch_reddit_posts: Get Reddit posts for a sector
            - analyze_stock_mentions: Find stock ticker mentions in posts
            - calculate_sentiment: Calculate sentiment scores for stocks
            
            Your task is to:
            1. Use the analyze_sector_sentiment tool to get comprehensive analysis
            2. Generate detailed rationales for each stock using LLM reasoning based on actual Reddit posts
            3. Provide insights about user perceptions, concerns, and excitement points from Reddit discussions
            4. Create a comprehensive sector summary that other agents can use for investment decisions
            
            The tool will return Reddit data and calculations, but YOU must generate the rationales using your LLM reasoning capabilities.
            Focus on extracting real user insights and perceptions from the actual Reddit content.
            
            Output must be a Python dictionary with the exact schema:
            {{
                "sector": "{sector}",
                "candidate_stocks": [
                    {{
                        "ticker": "AAPL",
                        "mention_count": 45,
                        "average_sentiment": 0.7,
                        "relevance_score": 0.82,
                        "rationale": "Comprehensive analysis of Reddit user perceptions, concerns, and excitement points about AAPL based on actual post content"
                    }}
                ],
                "summary": "Detailed sector analysis with key themes, trends, and market implications from Reddit discussions"
            }}
            
            IMPORTANT: Use the tools for data collection and calculations, but generate rationales yourself using LLM reasoning.
            The rationale should contain all perceptions Reddit users have about each stock, extracted from actual post content.""",
            agent=self.market_analyst.get_agent(),
            tools=self.create_market_analysys_tools(),
            expected_output=f"Python dictionary with {sector} sector analysis and top 5 candidate stocks with comprehensive rationales"
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
            tools=[TechnicalAnalysisTool()],
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
