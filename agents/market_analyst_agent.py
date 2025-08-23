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
        """Execute market analysis task for the given sector"""
        try:
            # Get raw Reddit data and calculations from the tool
            raw_result = self.reddit_tools._analyze_sector_sentiment(sector)
            
            if not raw_result.get("candidate_stocks"):
                return {
                    "sector": sector,
                    "candidate_stocks": [],
                    "summary": f"No stocks found for {sector} sector. Please check Reddit API credentials and try again."
                }
            
            # Generate comprehensive rationales using LLM reasoning
            enhanced_stocks = []
            for stock in raw_result["candidate_stocks"]:
                # Generate rationale based on actual Reddit posts
                rationale = self._generate_comprehensive_rationale(
                    stock["ticker"], 
                    stock["reddit_posts"], 
                    stock["average_sentiment"],
                    stock["mention_count"],
                    sector
                )
                
                enhanced_stock = {
                    "ticker": stock["ticker"],
                    "mention_count": stock["mention_count"],
                    "average_sentiment": stock["average_sentiment"],
                    "relevance_score": stock["relevance_score"],
                    "rationale": rationale
                }
                enhanced_stocks.append(enhanced_stock)
            
            # Generate enhanced sector summary using LLM
            enhanced_summary = self._generate_enhanced_sector_summary(enhanced_stocks, sector)
            
            return {
                "sector": sector,
                "candidate_stocks": enhanced_stocks,
                "summary": enhanced_summary
            }
            
        except Exception as e:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "summary": f"Error analyzing sector {sector}: {str(e)}"
            }
    
    def _generate_comprehensive_rationale(self, ticker: str, reddit_posts: List[Dict], 
                                       sentiment: float, mention_count: int, sector: str) -> str:
        """Generate comprehensive rationale based on actual Reddit posts using LLM reasoning"""
        
        if not reddit_posts:
            return f"{ticker} has limited Reddit discussion with {mention_count} mentions and {sentiment:.3f} sentiment."
        
        # Prepare context for LLM reasoning
        posts_summary = []
        for post in reddit_posts[:5]:  # Limit to top 5 posts to avoid token limits
            posts_summary.append(f"Title: {post['title']}\nContent: {post['content'][:200]}...\nUpvotes: {post['upvotes']}, Comments: {post['comments']}")
        
        posts_text = "\n\n".join(posts_summary)
        
        # Create prompt for LLM reasoning
        prompt = f"""You are a market analyst analyzing Reddit sentiment for {ticker} in the {sector} sector.

Reddit Posts Analysis:
{posts_text}

Based on these Reddit posts, generate a comprehensive rationale that includes:
1. Key themes and topics Reddit users are discussing about {ticker}
2. User sentiment and perceptions (bullish/bearish/neutral)
3. Specific concerns or excitement points mentioned
4. Market sentiment indicators from the community
5. Potential catalysts or events driving discussion

Focus on extracting real user insights and perceptions from the actual Reddit content.
Make the rationale informative for other investment analysts to understand Reddit sentiment.

Rationale:"""
        
        try:
            # Use the agent's LLM directly from the base agent
            llm = self._get_llm()
            
            # Generate rationale using the LLM
            response = llm.invoke(prompt)
            rationale = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the response
            rationale = rationale.strip()
            if rationale.startswith("Rationale:"):
                rationale = rationale[10:].strip()
            
            return rationale
            
        except Exception as e:
            print(f"⚠️  LLM reasoning failed for {ticker}: {str(e)}")
            # Fallback rationale if LLM reasoning fails
            return f"{ticker} is discussed on Reddit with {mention_count} mentions and {sentiment:.3f} sentiment. "
    
    def _generate_enhanced_sector_summary(self, stocks: List[Dict], sector: str) -> str:
        """Generate enhanced sector summary using LLM reasoning"""
        
        if not stocks:
            return f"Limited Reddit discussion found for {sector} sector."
        
        top_stock = stocks[0]
        avg_sentiment = sum(stock["average_sentiment"] for stock in stocks) / len(stocks)
        
        # Create prompt for sector summary
        stocks_summary = []
        for stock in stocks[:3]:  # Top 3 stocks
            stocks_summary.append(f"{stock['ticker']}: {stock['mention_count']} mentions, {stock['average_sentiment']:.3f} sentiment")
        
        stocks_text = "\n".join(stocks_summary)
        
        prompt = f"""You are a market analyst summarizing Reddit sentiment for the {sector} sector.

Top Trending Stocks:
{stocks_text}

Overall Sector Sentiment: {self._get_sentiment_description(avg_sentiment)}

Generate a comprehensive sector summary that includes:
1. Overall market sentiment for the sector
2. Key themes driving Reddit discussions
3. Notable trends or patterns
4. Potential market implications
5. Summary of top performing stocks

Make this summary useful for investment analysts and portfolio managers.

Sector Summary:"""
        
        try:
            # Use the agent's LLM directly from the base agent
            llm = self._get_llm()
            
            # Generate summary using the LLM
            response = llm.invoke(prompt)
            summary = response.content if hasattr(response, 'content') else str(response)
            
            # Clean up the response
            summary = summary.strip()
            if summary.startswith("Sector Summary:"):
                summary = summary[15:].strip()
            
            return summary
            
        except Exception as e:
            print(f"⚠️  LLM reasoning failed for sector summary: {str(e)}")
            # Fallback summary if LLM reasoning fails
            fallback_summary = f"Reddit sentiment analysis for {sector} sector reveals {len(stocks)} trending stocks. "
            fallback_summary += f"Top performer is {top_stock['ticker']} with {top_stock['mention_count']} mentions and "
            fallback_summary += f"{top_stock['average_sentiment']:.3f} sentiment. "
            fallback_summary += f"Overall sector sentiment is {self._get_sentiment_description(avg_sentiment)}."
            
            return fallback_summary
    
    def _get_sentiment_description(self, sentiment: float) -> str:
        """Convert sentiment score to descriptive text"""
        if sentiment > 0.3:
            return "bullish"
        elif sentiment < -0.3:
            return "bearish"
        else:
            return "neutral"
