from typing import Dict, Any, List
from crewai.tools.base_tool import Tool
from pydantic import BaseModel, Field
import requests
import re
import time
import os

# Pydantic models for tool arguments
class SectorInput(BaseModel):
    sector: str = Field(description="The industry sector to analyze (e.g., 'Technology', 'Healthcare', 'Finance')")

class PostsInput(BaseModel):
    posts: List[Dict[str, Any]] = Field(description="List of Reddit posts to analyze")
    sector: str = Field(description="The sector being analyzed")

class TickerAnalysisInput(BaseModel):
    ticker_analysis: Dict[str, Any] = Field(description="Dictionary of stock ticker analysis data")

class RedditAnalysisTool:
    """Tool for analyzing Reddit discussions and sentiment"""
    
    def __init__(self):
        self.reddit_client_id = os.getenv("REDDIT_CLIENT_ID")
        self.reddit_client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.reddit_user_agent = os.getenv("REDDIT_USER_AGENT", "ProspectAI/1.0")
    
    def get_tools(self) -> List[Tool]:
        """Get all Reddit analysis tools"""
        return [
            self.analyze_sector_sentiment_tool(),
            self.fetch_reddit_posts_tool(),
            self.analyze_stock_mentions_tool(),
            self.calculate_sentiment_tool()
        ]
    
    def analyze_sector_sentiment_tool(self) -> Tool:
        """Tool for analyzing Reddit sentiment for a specific sector"""
        return Tool(
            name="analyze_sector_sentiment",
            description="""Analyze Reddit discussions to identify trending stocks in a specific sector.
            This tool fetches Reddit posts, analyzes sentiment, and returns the top trending stocks.
            
            Args:
                sector: The industry sector to analyze (e.g., "Technology", "Healthcare", "Finance")
                
            Returns:
                A dictionary containing:
                - sector: The analyzed sector
                - candidate_stocks: List of top 5 trending stocks with sentiment scores
                - summary: Overall sector sentiment summary
            """,
            func=self._analyze_sector_sentiment,
            args_schema=SectorInput
        )
    
    def fetch_reddit_posts_tool(self) -> Tool:
        """Tool for fetching Reddit posts for a sector"""
        return Tool(
            name="fetch_reddit_posts",
            description="""Fetch Reddit posts related to a specific sector.
            
            Args:
                sector: The industry sector to search for
                
            Returns:
                List of Reddit posts with titles, content, and engagement metrics
            """,
            func=self._fetch_reddit_posts,
            args_schema=SectorInput
        )
    
    def analyze_stock_mentions_tool(self) -> Tool:
        """Tool for analyzing stock ticker mentions in Reddit posts"""
        return Tool(
            name="analyze_stock_mentions",
            description="""Analyze Reddit posts to find and count stock ticker mentions.
            
            Args:
                posts: List of Reddit posts to analyze
                sector: The sector being analyzed
                
            Returns:
                Dictionary mapping stock tickers to mention counts and sentiment data
            """,
            func=self._analyze_stock_mentions,
            args_schema=PostsInput
        )
    
    def calculate_sentiment_tool(self) -> Tool:
        """Tool for calculating sentiment scores for stocks"""
        return Tool(
            name="calculate_sentiment",
            description="""Calculate sentiment scores and relevance for stocks based on Reddit data.
            
            Args:
                ticker_analysis: Dictionary of stock ticker analysis data
                
            Returns:
                List of candidate stocks with relevance scores and rationale
            """,
            func=self._calculate_sentiment_scores,
            args_schema=TickerAnalysisInput
        )
    
    def _analyze_sector_sentiment(self, sector: str) -> Dict[str, Any]:
        """Main function to analyze sector sentiment"""
        try:
            # Check if Reddit API credentials are available
            if not self.reddit_client_id or not self.reddit_client_secret:
                return {
                    "sector": sector,
                    "candidate_stocks": [],
                    "summary": f"Reddit API credentials not configured. Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in your .env file."
                }
            
            # Fetch real Reddit data
            reddit_data = self._fetch_reddit_data(sector)
            
            if not reddit_data:
                return {
                    "sector": sector,
                    "candidate_stocks": [],
                    "summary": f"No Reddit data found for {sector} sector. Please check your API credentials and try again."
                }
            
            # Parse tickers and analyze sentiment
            ticker_analysis = self._analyze_reddit_sentiment(reddit_data, sector)
            
            # Calculate relevance scores and select top stocks
            candidate_stocks = self._calculate_relevance_scores(ticker_analysis)
            
            # Generate summary
            summary = self._generate_sector_summary(candidate_stocks, sector)
            
            return {
                "sector": sector,
                "candidate_stocks": candidate_stocks[:5],  # Top 5 stocks
                "summary": summary
            }
            
        except Exception as e:
            return {
                "sector": sector,
                "candidate_stocks": [],
                "summary": f"Error analyzing sector {sector}: {str(e)}"
            }
    
    def _fetch_reddit_posts(self, sector: str) -> List[Dict[str, Any]]:
        """Fetch Reddit posts for a sector"""
        return self._fetch_reddit_data(sector)
    
    def _analyze_stock_mentions(self, posts: List[Dict[str, Any]], sector: str) -> Dict[str, Dict]:
        """Analyze stock ticker mentions in posts"""
        return self._analyze_reddit_sentiment(posts, sector)
    
    def _calculate_sentiment_scores(self, ticker_analysis: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """Calculate sentiment scores for stocks"""
        return self._calculate_relevance_scores(ticker_analysis)
    
    def _get_reddit_access_token(self) -> str:
        """Get Reddit API access token"""
        auth_url = "https://www.reddit.com/api/v1/access_token"
        auth_data = {
            "grant_type": "client_credentials"
        }
        
        response = requests.post(
            auth_url,
            data=auth_data,
            auth=(self.reddit_client_id, self.reddit_client_secret),
            headers={"User-Agent": self.reddit_user_agent}
        )
        
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            raise Exception(f"Failed to get Reddit access token: {response.status_code}")
    
    def _fetch_reddit_data(self, sector: str) -> List[Dict[str, Any]]:
        """Fetch real Reddit posts data for the given sector"""
        try:
            access_token = self._get_reddit_access_token()
            
            # Define subreddits and keywords for each sector
            sector_config = {
                "Technology": {
                    "subreddits": ["investing", "stocks", "wallstreetbets", "technology", "artificial"],
                    "keywords": ["tech", "software", "AI", "semiconductor", "cloud", "digital", "innovation"]
                },
                "Healthcare": {
                    "subreddits": ["investing", "stocks", "wallstreetbets", "healthcare", "biotech"],
                    "keywords": ["healthcare", "biotech", "pharma", "medical", "drug", "treatment", "health"]
                },
                "Finance": {
                    "subreddits": ["investing", "stocks", "wallstreetbets", "finance", "cryptocurrency"],
                    "keywords": ["finance", "banking", "fintech", "insurance", "investment", "crypto", "blockchain"]
                },
                "Energy": {
                    "subreddits": ["investing", "stocks", "wallstreetbets", "energy", "renewableenergy"],
                    "keywords": ["energy", "oil", "gas", "renewable", "solar", "wind", "battery", "clean"]
                },
                "Consumer": {
                    "subreddits": ["investing", "stocks", "wallstreetbets", "consumer", "retail"],
                    "keywords": ["consumer", "retail", "ecommerce", "food", "beverage", "apparel", "luxury"]
                }
            }
            
            config = sector_config.get(sector, sector_config["Technology"])
            all_posts = []
            
            # Fetch posts from multiple subreddits
            for subreddit in config["subreddits"]:
                posts = self._fetch_subreddit_posts(subreddit, config["keywords"], access_token)
                all_posts.extend(posts)
                time.sleep(1)  # Rate limiting
            
            return all_posts
            
        except Exception as e:
            print(f"Error fetching Reddit data: {str(e)}")
            return []
    
    def _fetch_subreddit_posts(self, subreddit: str, keywords: List[str], access_token: str) -> List[Dict[str, Any]]:
        """Fetch posts from a specific subreddit"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": self.reddit_user_agent
        }
        
        posts = []
        
        try:
            # Search for posts with sector keywords
            for keyword in keywords[:3]:  # Limit to top 3 keywords to avoid rate limiting
                search_url = f"https://oauth.reddit.com/r/{subreddit}/search"
                params = {
                    "q": keyword,
                    "restrict_sr": "on",
                    "sort": "hot",
                    "t": "week",
                    "limit": 25
                }
                
                response = requests.get(search_url, headers=headers, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and "children" in data["data"]:
                        for post in data["data"]["children"]:
                            post_data = post["data"]
                            posts.append({
                                "title": post_data.get("title", ""),
                                "content": post_data.get("selftext", ""),
                                "upvotes": post_data.get("score", 0),
                                "comments": post_data.get("num_comments", 0),
                                "subreddit": subreddit,
                                "created_utc": post_data.get("created_utc", 0),
                                "url": f"https://reddit.com{post_data.get('permalink', '')}"
                            })
                
                time.sleep(0.5)  # Rate limiting
                
        except Exception as e:
            print(f"Error fetching from r/{subreddit}: {str(e)}")
        
        return posts
    
    def _analyze_reddit_sentiment(self, reddit_data: List[Dict], sector: str) -> Dict[str, Dict]:
        """Analyze Reddit sentiment for stock tickers in the sector"""
        # Common stock tickers by sector
        sector_tickers = {
            "Technology": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA", "META", "AMZN", "NFLX", "AMD", "INTC", "CRM", "ADBE", "ORCL", "CSCO", "QCOM"],
            "Healthcare": ["JNJ", "PFE", "UNH", "ABBV", "TMO", "ABT", "LLY", "DHR", "BMY", "AMGN", "GILD", "CVS", "WBA", "CI", "ANTM"],
            "Finance": ["JPM", "BAC", "WFC", "GS", "MS", "C", "USB", "PNC", "TFC", "COF", "AXP", "BLK", "SCHW", "V", "MA"],
            "Energy": ["XOM", "CVX", "COP", "EOG", "SLB", "VLO", "PSX", "MPC", "OXY", "HAL", "KMI", "WMB", "OKE", "DVN", "EOG"],
            "Consumer": ["PG", "KO", "PEP", "WMT", "HD", "MCD", "SBUX", "NKE", "DIS", "CMCSA", "TGT", "COST", "LOW", "TJX", "ROST"]
        }
        
        tickers = sector_tickers.get(sector, sector_tickers["Technology"])
        ticker_analysis = {}
        
        for ticker in tickers:
            mention_count = 0
            sentiment_scores = []
            
            # Search for ticker mentions in Reddit data
            for post in reddit_data:
                text = f"{post['title']} {post['content']}".upper()
                
                # Look for ticker mentions (with word boundaries)
                if re.search(rf'\b{ticker}\b', text):
                    mention_count += 1
                    
                    # Calculate sentiment based on post engagement and keywords
                    sentiment = self._calculate_post_sentiment(post, ticker)
                    sentiment_scores.append(sentiment)
            
            if mention_count > 0:
                ticker_analysis[ticker] = {
                    "ticker": ticker,
                    "mention_count": mention_count,
                    "sentiment_scores": sentiment_scores,
                    "average_sentiment": sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
                }
        
        return ticker_analysis
    
    def _calculate_post_sentiment(self, post: Dict[str, Any], ticker: str) -> float:
        """Calculate sentiment score for a Reddit post"""
        text = f"{post['title']} {post['content']}".lower()
        
        # Positive sentiment indicators
        positive_words = [
            "bullish", "buy", "long", "moon", "rocket", "🚀", "💎", "diamond", "hands", "hodl",
            "profit", "gain", "up", "rise", "surge", "jump", "climb", "soar", "rally", "breakout",
            "strong", "solid", "excellent", "amazing", "incredible", "fantastic", "love", "like"
        ]
        
        # Negative sentiment indicators
        negative_words = [
            "bearish", "sell", "short", "dump", "crash", "fall", "drop", "decline", "plunge", "tank",
            "loss", "down", "weak", "terrible", "awful", "horrible", "hate", "dislike", "avoid", "stay away"
        ]
        
        # Count positive and negative words
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        # Calculate base sentiment
        if positive_count == 0 and negative_count == 0:
            base_sentiment = 0.0
        else:
            base_sentiment = (positive_count - negative_count) / (positive_count + negative_count)
        
        # Adjust sentiment based on engagement (upvotes and comments)
        engagement_score = min((post['upvotes'] + post['comments']) / 100.0, 1.0)
        
        # Combine base sentiment with engagement
        final_sentiment = base_sentiment * 0.7 + engagement_score * 0.3
        
        # Clamp to [-1, 1] range
        return max(-1.0, min(1.0, final_sentiment))
    
    def _calculate_relevance_scores(self, ticker_analysis: Dict[str, Dict]) -> List[Dict[str, Any]]:
        """Calculate relevance scores and prepare candidate stocks"""
        candidates = []
        
        for ticker_data in ticker_analysis.values():
            # Normalize mention count to 0-1 scale (assuming max 100 mentions)
            frequency_score = min(ticker_data["mention_count"] / 100.0, 1.0)
            
            # Normalize sentiment to 0-1 scale
            sentiment_score = (ticker_data["average_sentiment"] + 1.0) / 2.0
            
            # Calculate relevance score: 60% frequency + 40% sentiment
            relevance_score = (0.6 * frequency_score) + (0.4 * sentiment_score)
            
            # Generate rationale based on sentiment and mentions
            rationale = self._generate_rationale(
                ticker_data["ticker"], 
                ticker_data["mention_count"], 
                ticker_data["average_sentiment"]
            )
            
            candidates.append({
                "ticker": ticker_data["ticker"],
                "mention_count": ticker_data["mention_count"],
                "average_sentiment": round(ticker_data["average_sentiment"], 3),
                "relevance_score": round(relevance_score, 3),
                "rationale": rationale
            })
        
        # Sort by relevance score (highest first)
        candidates.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return candidates
    
    def _generate_rationale(self, ticker: str, mention_count: int, sentiment: float) -> str:
        """Generate rationale for why a stock is trending"""
        if sentiment > 0.5:
            sentiment_desc = "bullish"
        elif sentiment < -0.5:
            sentiment_desc = "bearish"
        else:
            sentiment_desc = "mixed"
        
        if mention_count > 30:
            popularity = "highly discussed"
        elif mention_count > 15:
            popularity = "moderately discussed"
        else:
            popularity = "discussed"
        
        return f"{ticker} is {popularity} on Reddit with {sentiment_desc} sentiment, indicating strong retail investor interest."
    
    def _generate_sector_summary(self, candidate_stocks: List[Dict], sector: str) -> str:
        """Generate a summary of Reddit sentiment for the sector"""
        if not candidate_stocks:
            return f"Limited Reddit discussion found for {sector} sector."
        
        top_stock = candidate_stocks[0]
        avg_sentiment = sum(stock["average_sentiment"] for stock in candidate_stocks) / len(candidate_stocks)
        
        if avg_sentiment > 0.3:
            overall_sentiment = "bullish"
        elif avg_sentiment < -0.3:
            overall_sentiment = "bearish"
        else:
            overall_sentiment = "neutral"
        
        summary = f"Reddit sentiment for {sector} sector is {overall_sentiment}. "
        summary += f"Top trending stock is {top_stock['ticker']} with {top_stock['mention_count']} mentions "
        summary += f"and {overall_sentiment} sentiment. Retail investors are showing strong interest "
        summary += f"in {len([s for s in candidate_stocks if s['relevance_score'] > 0.5])} stocks in this sector."
        
        return summary
