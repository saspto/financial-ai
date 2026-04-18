# Financial AI Daily Report System

Automated daily financial intelligence report delivered as a PDF via AWS Lambda.

## Features
- Top 50 stocks + top 50 ETFs with performance analysis
- Buy/sell point identification
- Upcoming earnings calendar (current + next week)
- 10 things to know today
- AI-powered "why they performed well" and future prospects analysis
- Sources: WSJ, Bloomberg, Reuters, MarketWatch, Seeking Alpha, Yahoo Finance, CNBC
- Runs Mon–Fri; Monday report covers Friday + weekend activity
- Up to 20-page PDF, delivered via S3 + SES

## Architecture
```
EventBridge Scheduler (Mon-Fri)
    → Lambda (orchestrator)
        → Bedrock Claude Haiku (analysis + narrative)
        → Financial data APIs (yfinance, Alpha Vantage, Finnhub)
        → News APIs (NewsAPI, RSS feeds)
        → ReportLab PDF generation
        → S3 (PDF storage)
        → SES (email delivery)
```

## AWS Services Used (FedRAMP)
- **Lambda** — compute
- **S3** — PDF storage
- **SES** — email delivery
- **Bedrock** (Claude Haiku 3) — LLM analysis (cost-optimized)
- **EventBridge Scheduler** — cron scheduling
- **SSM Parameter Store** — secrets
- **CloudWatch** — logging

## Cost Estimate
- Lambda: ~$0.02/run (1GB, ~3min)
- Bedrock Claude Haiku: ~$0.10/run
- S3: ~$0.01/month
- SES: ~$0.0001/email
- **Total: ~$3–4/month**

## Setup

### Prerequisites
- AWS CLI configured
- Python 3.12
- Docker (for Lambda layer build)

### Deploy
```bash
# 1. Set configuration
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your API keys and email

# 2. Store secrets in SSM
./scripts/setup_ssm.sh

# 3. Build and deploy
./scripts/deploy.sh
```

### Local Testing
```bash
cd lambda
pip install -r requirements.txt
python -c "from handler import lambda_handler; lambda_handler({'test': True}, {})"
```

## Configuration
See `config/config.example.yaml` for all options.

## Project Structure
```
financial-ai/
├── lambda/
│   ├── handler.py              # Main Lambda entrypoint
│   ├── data/
│   │   ├── market_data.py      # Stock/ETF price data
│   │   ├── news_fetcher.py     # Financial news scraping
│   │   └── earnings_calendar.py # Earnings data
│   ├── analysis/
│   │   ├── performance.py      # Performance ranking
│   │   ├── buy_sell_signals.py # Technical buy/sell points
│   │   └── ai_analyst.py      # Bedrock LLM analysis
│   └── report/
│       ├── pdf_generator.py    # ReportLab PDF builder
│       └── templates.py        # PDF section templates
├── infrastructure/
│   ├── cloudformation.yaml     # Full AWS stack
│   └── iam_policy.json         # Lambda IAM policy
├── config/
│   └── config.example.yaml
├── scripts/
│   ├── deploy.sh
│   └── setup_ssm.sh
└── requirements.txt
```
