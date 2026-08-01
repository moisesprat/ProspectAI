# ProspectAI Version History

## v1.9.1 - Deterministic Enforcement

- `ProspectAIFlow` re-invokes `allocate_portfolio` itself after the Final Strategist
  phase and overwrites every numeric allocation/trade-setup field — the LLM no longer
  decides whether the allocator runs.
- New `PortfolioBoundsValidator` (`utils/portfolio_bounds_validator.py`) validates the
  final output against per-profile allocation, stop-distance, R/R, bucket-sum, and
  entry-zone invariants before publication; raises `BoundsViolationError` (fail-closed,
  one repair re-invocation) rather than publishing a non-compliant result.
- New `ActionPolicyGate` (`utils/action_policy_gate.py`) deterministically drops Critic
  `revision_directives` that order an action outside the entry_zone_status/risk_profile
  policy table before they reach the Final Strategist.
- `MarketAnalysisOutput.sentiment_available` sentinel: `average_sentiment` is `null`
  (never a fabricated `0.0`) when both Reddit and the Serper fallback fail;
  `CompositeScoreTool` renormalizes technical + fundamental weights to a 100 ceiling
  when sentiment is unavailable.
- `utils/patient_serper_tool.py::PatientSerperDevTool` wraps `SerperDevTool` with retry
  classification: 4xx fails fast (response body logged), only 429/5xx retry (max 2,
  backoff).
- `PortfolioAllocatorTool` emits `reserved_allocations: [{ticker, pct}]` for explicit
  per-ticker attribution of `reserved_pct`; Critic's `WAIT_ENTRY_ZERO_ALLOC` check
  reworded to match.
- Sector-benchmark ETFs (e.g. XLE) and broad-market ETFs (SPY, QQQ, ...) are excluded
  from the candidate universe on both the Reddit and Serper-fallback paths
  (`utils/candidate_universe_filter.py`).
- **BREAKING**: `run_analysis()` can now raise `BoundsViolationError` instead of
  returning a result, when the final output cannot be made bounds-compliant even after
  one allocator re-invocation.

---

## v1.7.0 - Risk Aversion Profile Selector

- Add `risk_profile` parameter (`conservative` / `aggressive`) to `run_analysis()` and `main.py --risk-profile`
- `PortfolioAllocatorTool` applies per-profile bounds: allocation cap, stop-loss multiplier, R/R ratio
- Draft Strategist, Critic, and Final Strategist receive `$risk_profile` in task prompts for qualitative guidance
- `InvestorStrategicOutput` and `CriticOutput` schemas carry `risk_profile` field
- Backend `/api/analyze` endpoint accepts `risk_profile` query param; analytics tracks by profile
- Web UI adds Conservative / Aggressive toggle before pipeline trigger

---

## v1.0.0 - First Official Release

### 🎉 Major Features
- **Multi-Agent Investment Analysis System** — Four specialized AI agents working in sequence
- **Real Reddit Integration** — Live sentiment analysis from Reddit communities
- **Technical Analysis Engine** — 13+ technical indicators and momentum analysis
- **Fundamental Analysis** — Financial statement analysis and valuation metrics
- **Investment Strategy Agent** — Portfolio recommendations and risk assessment

### 🚀 Technical Capabilities
- **Anthropic Claude Support** — Powered by Claude Sonnet / Opus / Haiku via LiteLLM
- **Ollama Support** — Fully local inference with any Ollama-compatible model
- **CrewAI Framework** — Professional multi-agent orchestration
- **Sector Analysis** — Technology, Healthcare, Finance, Energy, Consumer
- **Command-Line Interface** — Easy-to-use CLI with provider/model flags
- **Startup Validation** — `.env` file checked at launch; missing keys reported clearly
- **Time-Aware Market Analysis** — Market Analyst reflects conditions at execution time, not a fixed date

### 📊 Agent Capabilities
- **Market Analyst Agent**: Reddit sentiment analysis, trending stock identification, macro/geopolitical context
- **Technical Analyst Agent**: 13+ technical indicators, momentum scoring (1–10), risk assessment
- **Fundamental Analyst Agent**: Financial ratios, valuation grading, growth outlook
- **Investor Strategic Agent**: Composite scoring, portfolio allocation (sums to 100%), STRONG_BUY → AVOID recommendations

### 🔧 Development Principles
- **Modular Architecture** — Each agent built and tested in isolation
- **No Hardcoded Defaults** — All configuration comes from `.env`; no silent fallbacks
- **LiteLLM Routing** — Single `crewai.LLM` abstraction; no direct langchain dependencies
- **Engineering Standards** — Production-ready quality with proper testing

---

## Roadmap - Future Versions

### v1.1 - Enhanced Market Analysis
- Integration with financial news APIs (Bloomberg, Reuters)
- Real-time market sentiment from multiple sources
- Enhanced sector rotation analysis

### v1.2 - Agent Improvements
- Enhanced financial modeling capabilities
- More sophisticated valuation algorithms
- Advanced portfolio optimization algorithms

### v1.3 - Investment Strategy PDFs
- Professional PDF report generation
- Interactive decision support tools
- Portfolio visualization and charts

### v1.4 - Advanced Risk Management
- Monte Carlo simulations for portfolio scenarios
- Advanced risk metrics (VaR, CVaR, Sharpe ratios)
- Dynamic risk adjustment based on market conditions
- Options and derivatives analysis

---

## Dependencies

- Python 3.9+
- CrewAI 1.x (LiteLLM-based LLM routing)
- Anthropic API key (or Ollama for local inference)
- Reddit API credentials or Serper API key (at least one required)
