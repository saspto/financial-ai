#!/usr/bin/env bash
# Store API keys in SSM Parameter Store (encrypted)
# Usage: ./scripts/setup_ssm.sh
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"

echo "==> Setting up SSM Parameter Store secrets"
echo "    Region: $REGION"
echo ""

read -p "NewsAPI key (https://newsapi.org, free tier OK, press Enter to skip): " NEWSAPI_KEY
if [ -n "$NEWSAPI_KEY" ]; then
  aws ssm put-parameter \
    --name "/financial-ai/newsapi-key" \
    --value "$NEWSAPI_KEY" \
    --type SecureString \
    --overwrite \
    --region "$REGION"
  echo "   ✓ NewsAPI key stored"
fi

read -p "Finnhub key (https://finnhub.io, free tier OK, press Enter to skip): " FINNHUB_KEY
if [ -n "$FINNHUB_KEY" ]; then
  aws ssm put-parameter \
    --name "/financial-ai/finnhub-key" \
    --value "$FINNHUB_KEY" \
    --type SecureString \
    --overwrite \
    --region "$REGION"
  echo "   ✓ Finnhub key stored"
fi

echo ""
echo "✅  SSM parameters configured."
echo ""
echo "Both APIs have free tiers sufficient for this use case:"
echo "  NewsAPI: 100 req/day free — https://newsapi.org/register"
echo "  Finnhub: 60 req/min free — https://finnhub.io/register"
echo ""
echo "yfinance requires no API key."
echo "AWS Bedrock Claude Haiku 3.5 is billed per token (≈\$0.10/report)."
