# Enhanced Build Prompt

This document captures the full prompt and design decisions used to build this system.

## Original Request

> Generate a report of the financial activity that happened yesterday. It should run every day from Mon to Fri. Mon should have all the Friday and weekend activity. Show top 50 stocks and top 50 ETFs that have performed well. Why did they perform well? What are the future prospects? Are there any upcoming earnings this week and next week? What are the stocks that reach buy point and sell point? Give all the recommendations for today. What are the 10 things to know? The report can be up to 20 pages in PDF format. Want to run this in a Lambda function on AWS. The sources are all the reputed financial newspapers, magazines, websites. Prepare the source code and deploy. Use only FedRAMP services, no Cognito, cost is a factor - use cheaper resources. Use LLM agents and models that are optimal but not too expensive for this purpose. Use Python for coding.

## Enhanced Prompt (Full Design Spec)

### System Overview

Build a **daily financial intelligence report system** that:

1. **Triggers automatically** via AWS EventBridge Scheduler at 6:30 AM ET, Mon–Fri.
   - Monday run looks back to Friday close + all weekend news (3-day lookback).
   - Tue–Fri runs look back 1 day.

2. **Data collection** (parallel fetch):
   - **Market data**: yfinance (no API key needed) fetches close prices for:
     - ~150 S&P 500 / large-cap / growth stocks
     - ~120 ETFs (broad market, sector, thematic, international, fixed income, commodities, leveraged, dividend)
   - **News**: RSS feeds from WSJ, Bloomberg, Reuters, MarketWatch, CNBC, FT, Barron's, Seeking Alpha, Motley Fool, Investopedia, Morningstar + NewsAPI (free tier, optional)
   - **Earnings calendar**: Finnhub (free tier) + yfinance fallback

3. **Analysis pipeline**:
   - Rank top 50 stocks and top 50 ETFs by period return
   - Enrich with sector, industry, market cap, P/E, 52-week range, analyst targets
   - Technical signals: RSI (14), SMA-20/50/200, golden/death cross, distance from 52W high/low
   - Buy signals: RSI < 35, near 52W low, golden cross, above 50/200DMA, strong momentum
   - Sell signals: RSI > 75, near 52W high, death cross, below 200DMA

4. **AI analysis** via **AWS Bedrock Claude Haiku 3.5** (cost-optimized, ~$0.10/run):
   - Market overview narrative with mood and key themes
   - Why each stock/ETF performed well (from news + data correlation)
   - Future prospects and risk factors for top movers
   - Buy/sell point commentary
   - Earnings preview for top names
   - "10 Things to Know Today" — the most important briefing items

5. **PDF generation** via ReportLab (~15–20 pages):
   - Page 1: Cover — headline, market snapshot table, key themes
   - Page 2: Market overview — full index table, macro narrative
   - Page 3: 10 Things to Know
   - Pages 4–5: Top 50 Stocks table (split 25+25)
   - Pages 6–7: Stock performance narrative (AI-generated, why + prospects)
   - Pages 8–9: Top 50 ETFs table
   - Page 10: ETF performance narrative
   - Page 11–12: Buy & sell signals with technical detail
   - Page 13–14: Earnings calendar (this week + next week)
   - Page 15+: Recommendations for today

6. **Delivery**:
   - PDF uploaded to S3 (KMS-encrypted, versioned, Glacier after 90 days)
   - Email via SES with HTML summary + PDF attachment

### AWS Architecture (FedRAMP-authorized services only)

```
EventBridge Scheduler (cron Mon-Fri 6:30 AM ET)
  → Lambda (Python 3.12, 1.75GB RAM, 9min timeout)
      → yfinance (external, no key) ──────────────→ price data
      → RSS/NewsAPI (external, optional key) ──────→ news articles
      → Finnhub (external, free key) ─────────────→ earnings calendar
      → Bedrock Claude Haiku 3.5 ─────────────────→ AI narratives
      → ReportLab ────────────────────────────────→ PDF bytes
      → S3 (KMS-encrypted) ───────────────────────→ stored PDF
      → SES ──────────────────────────────────────→ email delivery
SSM Parameter Store ────────────────────────────→ API keys
CloudWatch Logs ────────────────────────────────→ observability
```

**No Cognito** — no user authentication needed (system-only Lambda).
**No RDS, DynamoDB, or ECS** — single Lambda execution, no persistence needed.
**No NAT Gateway** — Lambda in default VPC, internet access via public subnets.

### Cost Breakdown (monthly, weekdays only ~22 runs)

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 22 runs × 3min × 1.75GB | ~$0.05 |
| Bedrock Claude Haiku 3.5 | ~200K tokens/run × 22 | ~$2.20 |
| S3 | 22 PDFs × ~2MB | ~$0.01 |
| SES | 22 emails | ~$0.001 |
| EventBridge Scheduler | 22 invocations | ~$0.001 |
| SSM Parameter Store | 4 reads/run | ~$0.002 |
| **Total** | | **~$2.50–3.00/month** |

### Key Design Decisions

1. **Claude Haiku over Sonnet/Opus**: Haiku 3.5 is 10–20x cheaper than Sonnet while producing excellent structured financial summaries. The prompts are highly structured (JSON output) so reasoning depth matters less than speed and cost.

2. **yfinance as primary data source**: Free, reliable, covers all major US equities and ETFs. No API key = no SSM secret needed. Limitations: 15-min delayed, no intraday.

3. **RSS-first news strategy**: 15+ RSS feeds from premium sources work without API keys. NewsAPI is optional enhancement for better date filtering.

4. **Lambda over ECS/Fargate**: Single daily run with ~3 min execution time — Lambda is 100x cheaper than running a container 24/7. 1.75GB memory is sufficient for yfinance parallel downloads.

5. **ReportLab over WeasyPrint/wkhtmltopdf**: ReportLab is pure Python, no system dependencies, works in Lambda without custom layers or headless Chrome.

6. **EventBridge Scheduler over CloudWatch Events**: Newer, supports timezone-aware cron expressions natively. Single schedule, no rule + target complexity.

7. **S3 + SES over SNS**: PDF attachment in email is more useful than a link. SES sends raw MIME with attachment cleanly.

8. **SSM SecureString over Secrets Manager**: SSM is cheaper ($0.05/10K API calls vs $0.40/secret/month). Fine for non-rotating API keys.

### Extension Points

- Add Alpha Vantage for real-time intraday data (free tier: 5 req/min)
- Add Polygon.io for institutional-grade tick data
- Add SEC EDGAR RSS for 8-K/10-K filings monitoring
- Add Reddit/Twitter sentiment via Pushshift / Twitter Academic API
- Add pre-market futures data via yfinance (`ES=F`, `NQ=F`)
- Extend to international markets (LSE, TSE, BSE)
- Add portfolio-specific analysis by passing a watchlist via EventBridge event
