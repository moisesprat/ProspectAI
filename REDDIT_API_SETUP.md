# Reddit API Setup Guide

## Overview
The Market Analyst Agent now uses the real Reddit API to fetch actual posts and analyze real sentiment instead of simulated data.

## Step 1: Create a Reddit App

1. **Go to Reddit App Preferences**
   - Visit: https://www.reddit.com/prefs/apps
   - Sign in to your Reddit account

2. **Create a New App**
   - Click "Create App" or "Create Another App"
   - Fill in the details:
     - **Name**: `ProspectAI` (or any name you prefer)
     - **App Type**: Select "script"
     - **Description**: `Multi-agent investment analysis system`
     - **About URL**: Leave blank or add your GitHub repo
     - **Redirect URI**: `http://localhost:8080` (for local development)

3. **Get Your Credentials**
   - After creating the app, you'll see:
     - **Client ID**: A string under the app name (e.g., `abc123def456`)
     - **Client Secret**: A longer string (e.g., `ghi789jkl012mno345pqr678stu901vwx234`)

## Step 2: Configure Environment Variables

1. **Copy the environment template**
   ```bash
   cp env.example .env
   ```

2. **Edit your .env file**
   ```bash
   # Reddit API Configuration
   REDDIT_CLIENT_ID=your_reddit_client_id_here
   REDDIT_CLIENT_SECRET=your_reddit_client_secret_here
   REDDIT_USER_AGENT=ProspectAI/1.0
   ```

3. **Replace the placeholder values**
   ```bash
   REDDIT_CLIENT_ID=abc123def456
   REDDIT_CLIENT_SECRET=ghi789jkl012mno345pqr678stu901vwx234
   ```

## Step 3: Test the Integration

1. **Run the Market Analyst Agent test**
   ```bash
   python -c "
   from agents.market_analyst_agent import MarketAnalystAgent
   agent = MarketAnalystAgent()
   result = agent.execute_task('Technology')
   print('Result:', result)
   "
   ```

2. **Test with the full workflow**
   ```bash
   python main.py --sector Technology
   ```

## API Rate Limits

- **Reddit API**: 1000 requests per 10 minutes
- **Our implementation**: Includes rate limiting (1 second between subreddit calls, 0.5 seconds between keyword searches)
- **Typical usage**: ~50-100 API calls per sector analysis

## Subreddits and Keywords

The agent searches these subreddits for each sector:

### Technology
- **Subreddits**: r/investing, r/stocks, r/wallstreetbets, r/technology, r/artificial
- **Keywords**: tech, software, AI, semiconductor, cloud, digital, innovation

### Healthcare
- **Subreddits**: r/investing, r/stocks, r/wallstreetbets, r/healthcare, r/biotech
- **Keywords**: healthcare, biotech, pharma, medical, drug, treatment, health

### Finance
- **Subreddits**: r/investing, r/stocks, r/wallstreetbets, r/finance, r/cryptocurrency
- **Keywords**: finance, banking, fintech, insurance, investment, crypto, blockchain

### Energy
- **Subreddits**: r/investing, r/stocks, r/wallstreetbets, r/energy, r/renewableenergy
- **Keywords**: energy, oil, gas, renewable, solar, wind, battery, clean

### Consumer
- **Subreddits**: r/investing, r/stocks, r/wallstreetbets, r/consumer, r/retail
- **Keywords**: consumer, retail, ecommerce, food, beverage, apparel, luxury

## Sentiment Analysis

The agent analyzes sentiment using:

1. **Keyword Analysis**: Positive/negative words in posts
2. **Engagement Metrics**: Upvotes and comments
3. **Combined Scoring**: 70% keyword sentiment + 30% engagement

## Troubleshooting

### Common Issues

1. **"Reddit API credentials not configured"**
   - Check your .env file has REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET
   - Ensure no extra spaces or quotes around values

2. **"Failed to get Reddit access token"**
   - Verify your client ID and secret are correct
   - Check if Reddit is accessible from your network

3. **"No Reddit data found"**
   - Check your internet connection
   - Verify Reddit API is working (visit reddit.com)
   - Check if you've hit rate limits

### Debug Mode

To see detailed API calls, you can temporarily add debug prints:

```python
# In _fetch_subreddit_posts method
print(f"Fetching from r/{subreddit} with keyword: {keyword}")
print(f"Response status: {response.status_code}")
```

## Security Notes

- **Never commit your .env file** (it's already in .gitignore)
- **Keep your client secret private**
- **Use environment variables** in production deployments
- **Monitor API usage** to avoid rate limiting

## Production Considerations

- **Environment Variables**: Use proper secret management in production
- **Rate Limiting**: Implement more sophisticated rate limiting for high-volume usage
- **Caching**: Consider caching Reddit data to reduce API calls
- **Monitoring**: Add logging and monitoring for API health

## Support

If you encounter issues:
1. Check this guide first
2. Verify your Reddit app credentials
3. Test with a simple Reddit API call
4. Check Reddit's API status page
