from typing import Dict, Any, List
from .base_agent import BaseAgent
from crewai import Agent
from utils.reddit_analysis_tool import RedditAnalysisTool

class MarketAnalystAgent(BaseAgent):
    """Agent responsible for identifying trending stocks from Reddit discussions"""
    
    def __init__(self):
        super().__init__(
            name="Market Analyst Agent",
            role="Sector-focused Reddit analyst",
            goal="Identify trending stocks from Reddit discussions for further analysis",
            backstory="""You are a sharp market researcher who listens to retail investors 
            and sentiment on Reddit, extracting the most discussed and promising stocks in a sector. 
            You excel at parsing social media sentiment and identifying stocks that are gaining 
            attention from retail investors. You use specialized tools to analyze Reddit data 
            and provide insights about market sentiment."""
        )
        self.reddit_tools = RedditAnalysisTool()
        
    def create_agent(self) -> Agent:
        """Create the Market Analyst Agent with Reddit analysis tools"""
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            verbose=True,
            allow_delegation=False,
            llm=self._get_llm(),
            tools=self.reddit_tools.get_tools()
        )
    
    def execute_task(self, sector: str = "Technology") -> Dict[str, Any]:
        """
        Execute market analysis to identify trending stocks from Reddit discussions
        
        Args:
            sector: The industry sector to analyze (defaults to "Technology")
            
        Returns:
            Dictionary containing identified stocks and Reddit sentiment analysis
        """
        try:
            # Use the Reddit analysis tool to perform the analysis
            result = self.reddit_tools._analyze_sector_sentiment(sector)
            return result
            
        except Exception as e:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "summary": f"Error analyzing sector {sector}: {str(e)}"
            }
