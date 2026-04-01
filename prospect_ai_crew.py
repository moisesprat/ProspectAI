import json
import os
from datetime import datetime
from crewai import Crew, LLM, Task
from typing import Any, Callable, Dict, List, Optional

from crewai_tools import SerperDevTool
from agents.market_analyst_agent import MarketAnalystAgent
from agents.technical_analyst_agent import TechnicalAnalystAgent
from agents.fundamental_analyst_agent import FundamentalAnalystAgent
from agents.investor_strategic_agent import InvestorStrategicAgent
from config.config import Config

from utils.reddit_sentiment_tool import RedditSentimentTool
from utils.technical_analysis_tool import TechnicalAnalysisTool
from utils.fundamental_data_tool import FundamentalDataTool


class ProspectAICrew:
    """Main orchestrator for ProspectAI multi-agent investment analysis."""

    def __init__(self):
        self.config = Config()

        # Agents
        self.market_analyst = MarketAnalystAgent()
        self.technical_analyst = TechnicalAnalystAgent()
        self.fundamental_analyst = FundamentalAnalystAgent()
        self.investor_strategist = InvestorStrategicAgent()

        # Tools (only what each task actually uses)
        self.search_tool = SerperDevTool()  # Serper fallback for market analyst
        self.crew = None

    # ─────────────────────────────────────────────────────────────────────────
    # LLM helper (used at the Crew level as a fallback default)
    # ─────────────────────────────────────────────────────────────────────────
    def _get_llm(self):
        provider = os.getenv("MODEL_PROVIDER", "anthropic")
        if provider == "ollama":
            return LLM(
                model=f"ollama/{self.config.OLLAMA_MODEL}",
                base_url=self.config.OLLAMA_BASE_URL,
                temperature=0.1,
            )
        return LLM(
            model=f"anthropic/{self.config.ANTHROPIC_MODEL}",
            api_key=self.config.ANTHROPIC_API_KEY,
            temperature=0.1,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Task definitions
    # ─────────────────────────────────────────────────────────────────────────
    def create_tasks(self, market_criteria: Dict[str, Any]) -> List[Task]:
        sector = market_criteria.get("sector", "Technology")
        today = datetime.now().strftime("%Y-%m-%d")

        # ── Task 1: Market Sentiment Analysis ────────────────────────────────
        market_analysis_task = Task(
            description=f"""You are the first agent in the ProspectAI pipeline.
Identify the top 5 most-discussed stocks in the {sector} sector from Reddit retail
investor communities and produce a structured sentiment report.

STEP 1 — Call the Reddit tool:
  Call the tool named 'analyze_sector_reddit_sentiment' with sector="{sector}".
  It returns a dict with 'candidate_stocks' (list) and 'fallback_required' (bool).

STEP 2 — Handle fallback if needed:
  If fallback_required is True, use 'search_internet' (SerperDevTool) with query:
    "{sector} sector stocks investors discussing {today}"
  Extract up to 5 stock tickers from the search snippets. Assign:
    mention_count = 0, relevance_score = 0.5
    average_sentiment: positive news = 0.65, mixed = 0.40, negative = 0.15
  Set data_source to "serper_fallback".

STEP 3 — Write LLM rationales (200-400 words each):
  For each stock, write a 'rationale' covering:
  a) Key themes retail investors are discussing right now
  b) Sentiment tone (bullish / bearish / mixed) and the specific reasons
  c) Catalysts or concerns mentioned (products, earnings, regulation, competition)
  d) Red flags or risks visible in community sentiment
  e) How current macroeconomic conditions, geopolitical events, or sector trends
     are influencing investor sentiment at this moment in time
  Today's date is {today}. All analysis must reflect the current market environment.
  For Reddit data: base rationale on the 'sample_posts' field from the tool output.
  For Serper fallback: base rationale on the search result snippets.

STEP 4 — Output EXACTLY this structure (pure Python dict, no markdown wrapper).
Use the actual tickers identified in STEP 1 or STEP 2 — do NOT substitute example tickers:
{{
  "sector": "{sector}",
  "data_source": "reddit",
  "candidate_stocks": [
    {{
      "ticker": "<TICKER_FROM_STEP_1_OR_2>",
      "mention_count": <integer>,
      "average_sentiment": <float>,
      "relevance_score": <float>,
      "rationale": "<200-400 words>"
    }}
  ],
  "summary": "<2-3 paragraph overview of overall sector sentiment as of {today}, key themes, current macro/geopolitical context, and notable patterns — minimum 150 words>"
}}

RULES:
- Output exactly 5 stocks (fewer only if truly fewer were found).
- Do NOT invent tickers. Use only tickers returned by the tool or found in search results.
- All numeric values must be numbers, not strings.
- The 'summary' must be at least 150 words.""",
            agent=self.market_analyst.get_agent(),
            tools=[RedditSentimentTool(), self.search_tool],
            expected_output=(
                f"Python dict with sector='{sector}', data_source, "
                f"candidate_stocks (list of 5 dicts: ticker, mention_count, "
                f"average_sentiment, relevance_score, rationale), and summary string."
            ),
        )

        # ── Task 2: Technical Analysis ────────────────────────────────────────
        technical_analysis_task = Task(
            description=f"""You are the Technical Analyst in the ProspectAI pipeline.
You receive the Market Analyst output as context. Run technical analysis on every
ticker in the candidate_stocks list and produce a structured report.

STEP 1 — Extract tickers:
  Read the context. Find the 'candidate_stocks' list. Extract each 'ticker' value.
  You will typically get 5 tickers.

STEP 2 — Call the tool for EACH ticker:
  Call 'calculate_technical_indicators' with ticker="<TICKER>" and period="1y".
  Collect all results before writing your output. If a ticker returns an 'error'
  key, record the error and continue to the next ticker.

STEP 3 — Interpret results for each stock using ONLY values returned by the tool:
  - overall_signal: "BULLISH" if MACD is Bullish AND MA status contains "Uptrend";
                    "BEARISH" if MACD is Bearish AND MA status contains "Downtrend";
                    "MIXED" if one bullish one bearish; "NEUTRAL" otherwise.
  - key_signals: list of 3-5 plain-English strings
    (e.g. "RSI=68 approaching overbought", "MACD Bullish crossover", "Strong uptrend SMA20>SMA50>SMA200").
  - entry_zone: "<SMA20 value> to <SMA20 * 0.98>" (2% buffer below SMA20).
  - stop_loss: current_price - (ATR * 2.0). Round to 2 decimal places.
  - momentum_score: integer 1-10. Award +2 points for each true condition (cap at 10):
      RSI between 45 and 65; MACD status Bullish; MA status Strong Uptrend or Uptrend;
      ADX > 25; Bollinger status Normal Range; price above lower Bollinger band.
  - risk_level: "HIGH" if ATR/current_price > 0.03; "LOW" if < 0.015; "MEDIUM" otherwise.

STEP 4 — Output EXACTLY this structure (pure Python dict, no markdown wrapper):
{{
  "sector": "{sector}",
  "analysis_date": "{today}",
  "stock_analyses": [
    {{
      "ticker": "NVDA",
      "current_price": 875.50,
      "period_analyzed": "1y",
      "raw_indicators": {{
        "rsi": 68.4,
        "macd_status": "Bullish",
        "ma_status": "Strong Uptrend",
        "bb_status": "Normal Range",
        "adx": 31.2,
        "atr": 22.5,
        "sma_20": 851.0,
        "ema_12": 860.0
      }},
      "interpretation": {{
        "overall_signal": "BULLISH",
        "key_signals": ["RSI=68 near overbought", "Strong uptrend SMA20>SMA50>SMA200", "MACD Bullish"],
        "entry_zone": "851-834",
        "stop_loss": 830.5,
        "momentum_score": 8,
        "risk_level": "MEDIUM"
      }},
      "error": null
    }}
  ],
  "sector_technical_summary": "2-3 paragraph summary of the overall technical picture for the sector."
}}

RULES:
- raw_indicators must use actual numbers from the tool — never invented values.
- If the tool returns an error for a ticker, set error to that string and all other
  fields (current_price, raw_indicators, interpretation) to null.
- Do not skip any ticker from the market analyst output.""",
            agent=self.technical_analyst.get_agent(),
            tools=[TechnicalAnalysisTool()],
            expected_output=(
                f"Python dict with sector='{sector}', analysis_date, "
                f"stock_analyses (one entry per ticker with raw_indicators and "
                f"interpretation), and sector_technical_summary string."
            ),
            context=[market_analysis_task],
        )

        # ── Task 3: Fundamental Analysis ──────────────────────────────────────
        fundamental_analysis_task = Task(
            description=f"""You are the Fundamental Analyst in the ProspectAI pipeline.
You receive context from the Market Analyst (sentiment) and Technical Analyst (indicators).
Fetch real financial data for each stock and produce a structured fundamental report.

STEP 1 — Extract tickers:
  Read the technical analysis context. Find 'stock_analyses'. Extract each 'ticker'.

STEP 2 — Call the tool for EACH ticker:
  Call 'fetch_fundamental_data' with ticker="<TICKER>".
  Collect all results. If a ticker returns an 'error' key, skip grading for that stock.

STEP 3 — Grade each stock using ONLY tool-returned values:

  valuation_grade (use pe_ratio; if null use ps_ratio):
    pe_ratio < 15             → "CHEAP"
    pe_ratio 15-25            → "FAIR"
    pe_ratio 25-40            → "EXPENSIVE"
    pe_ratio > 40             → "VERY_EXPENSIVE"
    pe_ratio null, ps < 3    → "CHEAP"
    pe_ratio null, ps 3-6    → "FAIR"
    pe_ratio null, ps > 6    → "EXPENSIVE"

  financial_health:
    STRONG:   current_ratio > 1.5 AND debt_to_equity < 1.0 AND free_cash_flow > 0
    WEAK:     current_ratio < 1.0 OR debt_to_equity > 3.0 OR free_cash_flow < 0
    ADEQUATE: everything else (including nulls)

  growth_outlook (use revenue_growth_yoy):
    > 0.15    → "HIGH"
    0.05-0.15 → "MODERATE"
    0-0.05    → "LOW"
    negative  → "DECLINING"
    null      → "MODERATE"

  risk_factors: list of exactly 3 items citing specific numbers from raw_fundamentals.
  catalysts: list of 2-3 items citing specific numbers from raw_fundamentals.
  fundamental_summary: 150-200 words integrating quantitative data with the
    market sentiment rationale from the Market Analyst context.

STEP 4 — Output EXACTLY this structure (pure Python dict, no markdown wrapper):
{{
  "sector": "{sector}",
  "analysis_date": "{today}",
  "stock_analyses": [
    {{
      "ticker": "NVDA",
      "raw_fundamentals": {{
        "pe_ratio": 65.2,
        "forward_pe": 38.1,
        "pb_ratio": 28.4,
        "ps_ratio": 30.1,
        "ev_ebitda": 55.3,
        "market_cap": 2150000000000,
        "revenue_growth_yoy": 0.122,
        "net_margin": 0.554,
        "gross_margin": 0.745,
        "return_on_equity": 1.234,
        "debt_to_equity": 0.41,
        "current_ratio": 4.17,
        "free_cash_flow": 26900000000,
        "dividend_yield": null
      }},
      "assessment": {{
        "valuation_grade": "VERY_EXPENSIVE",
        "financial_health": "STRONG",
        "growth_outlook": "MODERATE",
        "fundamental_summary": "...",
        "risk_factors": ["PE ratio of 65x is historically elevated", "..."],
        "catalysts": ["Revenue growing at 12% YoY", "..."]
      }},
      "error": null
    }}
  ],
  "sector_fundamental_summary": "2-3 paragraph overview of sector-wide fundamental trends."
}}

RULES:
- raw_fundamentals must contain ONLY values from 'fetch_fundamental_data'. No invented numbers.
- valuation_grade, financial_health, growth_outlook must use the exact enum strings above.
- If tool returns an error, set error to the string and assessment to null.
- Include all tickers from technical analysis context.""",
            agent=self.fundamental_analyst.get_agent(),
            tools=[FundamentalDataTool()],
            expected_output=(
                f"Python dict with sector='{sector}', analysis_date, "
                f"stock_analyses (one entry per ticker with raw_fundamentals and "
                f"assessment), and sector_fundamental_summary string."
            ),
            context=[market_analysis_task, technical_analysis_task],
        )

        # ── Task 4: Investment Strategy ───────────────────────────────────────
        investment_strategy_task = Task(
            description=f"""You are the final agent in the ProspectAI pipeline.
Synthesize the outputs from all three prior agents and produce a machine-readable
JSON investment recommendation dict. This output is parsed programmatically —
no markdown fences, no text before or after the JSON.

STEP 1 — Cross-reference data for each ticker:
  From Market context:      mention_count, average_sentiment, rationale
  From Technical context:   overall_signal, momentum_score, risk_level, entry_zone, stop_loss
  From Fundamental context: valuation_grade, financial_health, growth_outlook, risk_factors, catalysts

STEP 2 — Compute composite_score (0-100) using this exact formula:
  sentiment_component  = min(average_sentiment * 100, 30)     [max 30 pts]
  technical_component  = momentum_score * 4                    [max 40 pts; score is 1-10]
  fundamental_component:
    financial_health: STRONG=20, ADEQUATE=10, WEAK=0, null=5
    growth_outlook:   HIGH=10, MODERATE=7, LOW=3, DECLINING=0, null=5
  composite_score = sentiment_component + technical_component + fundamental_component
  Round to 1 decimal place.

STEP 3 — Map composite_score to recommendation:
  >= 75 → "STRONG_BUY"
  >= 55 → "BUY"
  >= 40 → "HOLD"
  >= 25 → "REDUCE"
  <  25 → "AVOID"

STEP 4 — Compute portfolio allocation:
  Only STRONG_BUY and BUY stocks receive allocation_pct > 0.
  Allocation is proportional to composite_score among eligible stocks.
  The sum of all allocation_pct values must equal exactly 100.0.
  Stocks with HOLD/REDUCE/AVOID get allocation_pct = 0.
  If NO stocks are BUY or STRONG_BUY, distribute equally across all stocks.

STEP 5 — Determine sector outlook:
  avg_composite_score = mean of all composite_scores
  avg >= 55 → "BULLISH"; avg <= 35 → "BEARISH"; else → "NEUTRAL"

STEP 6 — Output EXACTLY this JSON (the complete pipeline output):
{{
  "pipeline_version": "2.0",
  "sector": "{sector}",
  "analysis_date": "{today}",
  "overall_sector_outlook": "BULLISH",
  "overall_risk_level": "MEDIUM",
  "stock_recommendations": [
    {{
      "ticker": "NVDA",
      "recommendation": "STRONG_BUY",
      "composite_score": 84.0,
      "allocation_pct": 35.2,
      "score_breakdown": {{
        "sentiment_component": 19.5,
        "technical_component": 32.0,
        "fundamental_component": 30.0
      }},
      "rationale": "150-word synthesis citing specific signals from all three agents",
      "entry_zone": "851-834",
      "stop_loss": 830.5,
      "time_horizon": "MEDIUM_TERM",
      "key_risks": ["risk 1", "risk 2"],
      "key_catalysts": ["catalyst 1", "catalyst 2"]
    }}
  ],
  "portfolio_summary": {{
    "total_allocated_pct": 100.0,
    "stocks_recommended": 3,
    "stocks_avoided": 2,
    "avg_composite_score": 71.4,
    "portfolio_rationale": "2-3 paragraph explanation of the portfolio construction logic"
  }},
  "execution_plan": {{
    "immediate_actions": ["action 1", "action 2"],
    "monitoring_triggers": ["trigger 1", "trigger 2"],
    "review_frequency": "MONTHLY"
  }}
}}

RULES:
- allocation_pct values must sum to exactly 100.0 (round to 1 decimal).
- composite_score must follow the Step 2 formula exactly.
- recommendation must use only: STRONG_BUY, BUY, HOLD, REDUCE, AVOID.
- overall_sector_outlook must be: BULLISH, NEUTRAL, or BEARISH.
- overall_risk_level: HIGH if >50% of stocks have risk_level HIGH;
  LOW if >50% LOW; MEDIUM otherwise.
- time_horizon: LONG_TERM if growth_outlook=HIGH; SHORT_TERM if technical-signal-only;
  MEDIUM_TERM for all other cases.
- All tickers from fundamental analysis must appear in stock_recommendations.
- Output only the JSON dict — no surrounding text.""",
            agent=self.investor_strategist.get_agent(),
            tools=[],
            expected_output=(
                f"JSON dict with pipeline_version='2.0', sector='{sector}', analysis_date, "
                f"overall_sector_outlook, overall_risk_level, stock_recommendations "
                f"(ticker/recommendation/composite_score/allocation_pct/score_breakdown/"
                f"rationale/entry_zone/stop_loss/time_horizon/key_risks/key_catalysts), "
                f"portfolio_summary, and execution_plan."
            ),
            context=[
                market_analysis_task,
                technical_analysis_task,
                fundamental_analysis_task,
            ],
        )

        return [
            market_analysis_task,
            technical_analysis_task,
            fundamental_analysis_task,
            investment_strategy_task,
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Run the full pipeline
    # ─────────────────────────────────────────────────────────────────────────
    def run_analysis(
        self,
        market_criteria: Dict[str, Any],
        progress_callback: Optional[Callable[[Dict], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run the complete investment analysis pipeline.

        Args:
            market_criteria: Dict with at least 'sector' key.
            progress_callback: Optional callable(event_dict) for streaming progress.
                               Reserved for future web-UI integration.

        Returns:
            Dict with 'status', 'result' (structured dict), and 'summary' keys.
        """
        tasks = self.create_tasks(market_criteria)

        self.crew = Crew(
            agents=[
                self.market_analyst.get_agent(),
                self.technical_analyst.get_agent(),
                self.fundamental_analyst.get_agent(),
                self.investor_strategist.get_agent(),
            ],
            tasks=tasks,
            verbose=True,
        )

        crew_result = self.crew.kickoff()

        # Parse the final agent's output into a structured dict
        structured = self._parse_result(crew_result)

        summary = (
            structured.get("portfolio_summary", {}).get("portfolio_rationale", "")
            or str(structured)[:300]
        )

        return {
            "status": "success",
            "workflow_completed": True,
            "result": structured,
            "summary": summary,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Output parsing
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_result(crew_result) -> Dict[str, Any]:
        """
        Extract a JSON dict from the CrewAI result object.
        Handles markdown code fences and plain JSON strings.
        Falls back to a minimal error dict on parse failure.
        """
        # CrewAI >= 0.30 exposes result.json_dict (dict | None) when output is JSON
        if hasattr(crew_result, "json_dict") and crew_result.json_dict:
            return crew_result.json_dict

        raw = getattr(crew_result, "raw", None) or str(crew_result)

        # Strip markdown code fences if the LLM wrapped the output
        cleaned = raw.strip()
        for fence in ("```json", "```python", "```"):
            if cleaned.startswith(fence):
                cleaned = cleaned[len(fence):]
                break
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Return raw text in a wrapper so callers can still display it
            return {
                "pipeline_version": "2.0",
                "parse_error": True,
                "raw_output": raw,
                "portfolio_summary": {
                    "portfolio_rationale": raw[:500],
                },
            }
