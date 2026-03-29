---
name: market-sentiment
description: >
  Use this skill when working with market data, stock analysis, sentiment scoring,
  or anything related to the Alpaca API and financial data pipelines.
  Invoke with /market-sentiment or automatically when discussing stocks, quotes, or sentiment.
---

# Market Sentiment Analysis

You are working on the Market-Sentiment-Analyst project — a Flask REST API for stock sentiment analysis.

## Architecture
- **Backend:** Flask (Python) running on port 5000
- **Data Source:** Alpaca Markets API (requires `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`)
- **Endpoints:**
  - `GET /quote?symbol=<SYMBOL>` — Fetch latest stock quote
  - `GET /sentiment?symbol=<SYMBOL>` — Analyze bullish/bearish sentiment from bid/ask spread

## When Analyzing Sentiment
1. Fetch current market data via Alpaca API
2. Compare ask price vs bid price to determine spread
3. Classify as bullish (ask > bid by significant margin) or bearish
4. Return structured JSON with symbol, sentiment, confidence, and raw data

## Standards
- Always validate stock symbols before API calls
- Handle API rate limits and errors gracefully
- Never hardcode API keys — use environment variables
- Log all API calls for debugging
- Test with real and mock data

## Enhancement Opportunities
- Add more sophisticated sentiment indicators (volume, moving averages, news)
- Integrate OpenAI for news-based sentiment (already in requirements.txt)
- Add historical trend analysis
- Support batch symbol queries
