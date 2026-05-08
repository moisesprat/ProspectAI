## 1. Python Package — Ticker Lists

- [x] 1.1 In `utils/reddit_sentiment_tool.py`, remove `NVDA`, `AMD`, `INTC`, `QCOM`, `AVGO`, `MU`, `MRVL`, `ALAB`, `SMCI`, `ARM` from the `Technology` entry in `SECTOR_TICKERS`
- [x] 1.2 Add IT services tickers `EPAM`, `INFY`, `CTSH`, `ACN`, `WIT`, `IBM`, `GLOB`, `DXC` to the `Technology` entry in `SECTOR_TICKERS`
- [x] 1.3 Add a new `Semiconductors` entry to `SECTOR_TICKERS` with: `NVDA`, `AMD`, `INTC`, `QCOM`, `AVGO`, `MU`, `MRVL`, `ALAB`, `ASML`, `TSM`, `KLAC`, `LRCX`, `AMAT`, `ARM`, `SMCI`

## 2. Python Package — Subreddit Config

- [x] 2.1 Add `Stocks_picks` and `StockInvest` to the `Technology` subreddit list in `SECTOR_CONFIG`
- [x] 2.2 Add a new `Semiconductors` entry to `SECTOR_CONFIG` with subreddits `["investing", "stocks", "wallstreetbets", "hardware", "chipdesign", "Stocks_picks", "StockInvest"]` and keywords `["semiconductor", "chip", "foundry", "fabless", "wafer", "EUV", "lithography", "GPU", "AI chip", "data center", "HBM", "packaging"]`

## 3. Python Package — Tests

- [x] 3.1 Add a test asserting `set(SECTOR_TICKERS["Technology"]) & set(SECTOR_TICKERS["Semiconductors"]) == set()` (no ticker duplication)
- [x] 3.2 Add a test asserting `Semiconductors` is present in `SECTOR_TICKERS` and contains at least `ASML`, `TSM`, `NVDA`
- [x] 3.3 Add a test asserting IT services tickers (`EPAM`, `INFY`, `CTSH`) are present in `SECTOR_TICKERS["Technology"]`
- [x] 3.4 Add a test asserting `Stocks_picks` and `StockInvest` are in `SECTOR_CONFIG["Technology"]["subreddits"]` and `SECTOR_CONFIG["Semiconductors"]["subreddits"]`
- [x] 3.5 Run `pytest tests/ -v` and confirm all tests pass

## 4. Web Frontend — Sector Selector

- [x] 4.1 In `prospectai-web/ui/data.js`, add `{ ticker: 'SOXX', name: 'Semiconductors' }` to the `SECTORS` array
- [ ] 4.2 Verify the web UI renders a `Semiconductors` card with ticker `SOXX` and that clicking it enables the Run button (manual browser check or dev server)

## 5. CLAUDE.md — Supported Sectors Comment

- [x] 5.1 Update the `# Supported sectors` comment in `CLAUDE.md` to include `Semiconductors`
