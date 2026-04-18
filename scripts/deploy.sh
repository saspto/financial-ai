#!/usr/bin/env bash
# Deploy Financial AI report Lambda to AWS
# Usage: ./scripts/deploy.sh [--region us-east-1] [--account 123456789012]
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
DEPLOY_BUCKET="financial-ai-deploy-${ACCOUNT_ID}"
STACK_NAME="financial-ai"
SES_SENDER="${SES_SENDER:-}"
SES_RECIPIENTS="${SES_RECIPIENTS:-}"

echo "==> Account: $ACCOUNT_ID | Region: $REGION"

# 1. Create deploy bucket if not exists
echo "==> Ensuring deploy S3 bucket: $DEPLOY_BUCKET"
aws s3api head-bucket --bucket "$DEPLOY_BUCKET" 2>/dev/null || \
  aws s3 mb "s3://$DEPLOY_BUCKET" --region "$REGION"

# 2. Build Lambda layer (dependencies)
echo "==> Building Lambda layer..."
rm -rf /tmp/lambda-layer
mkdir -p /tmp/lambda-layer/python
pip install \
  yfinance pandas numpy requests beautifulsoup4 lxml \
  boto3 reportlab Pillow feedparser python-dateutil pytz \
  finnhub-python \
  --target /tmp/lambda-layer/python \
  --quiet

cd /tmp/lambda-layer
zip -r /tmp/layer.zip python/ -x "*.pyc" -x "*/__pycache__/*" > /dev/null
echo "   Layer size: $(du -sh /tmp/layer.zip | cut -f1)"

# 3. Upload layer
echo "==> Uploading layer to S3..."
aws s3 cp /tmp/layer.zip "s3://$DEPLOY_BUCKET/layer.zip"

# 4. Package Lambda code
echo "==> Packaging Lambda code..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT/lambda"
zip -r /tmp/lambda.zip . -x "*.pyc" -x "*/__pycache__/*" > /dev/null
echo "   Code size: $(du -sh /tmp/lambda.zip | cut -f1)"

# 5. Upload code
echo "==> Uploading Lambda code to S3..."
aws s3 cp /tmp/lambda.zip "s3://$DEPLOY_BUCKET/lambda.zip"

# 6. Deploy CloudFormation
echo "==> Deploying CloudFormation stack: $STACK_NAME..."
if [ -z "$SES_SENDER" ]; then
  read -p "SES Sender email: " SES_SENDER
fi
if [ -z "$SES_RECIPIENTS" ]; then
  read -p "SES Recipients (comma-separated): " SES_RECIPIENTS
fi

aws cloudformation deploy \
  --template-file "$REPO_ROOT/infrastructure/cloudformation.yaml" \
  --stack-name "$STACK_NAME" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --parameter-overrides \
    SESEmailSender="$SES_SENDER" \
    SESEmailRecipients="$SES_RECIPIENTS" \
    BedrockRegion="$REGION" \
  --no-fail-on-empty-changeset

echo "==> Stack deployed successfully."

# 7. Update Lambda code directly (faster than full CFN update on re-deploys)
LAMBDA_FUNCTION="financial-ai-report"
if aws lambda get-function --function-name "$LAMBDA_FUNCTION" --region "$REGION" &>/dev/null; then
  echo "==> Updating Lambda function code..."
  aws lambda update-function-code \
    --function-name "$LAMBDA_FUNCTION" \
    --s3-bucket "$DEPLOY_BUCKET" \
    --s3-key lambda.zip \
    --region "$REGION" \
    --no-cli-pager
fi

echo ""
echo "✅  Deployment complete!"
echo "   Stack: $STACK_NAME"
echo "   Lambda: $LAMBDA_FUNCTION"
echo "   Schedule: Mon-Fri 6:30 AM ET"
echo ""
echo "To test immediately:"
echo "   aws lambda invoke --function-name $LAMBDA_FUNCTION --payload '{\"test\":true}' /tmp/out.json"
