# Deployment Instructions — Financial AI Daily Report

## Current Deployment State

| Resource | Value |
|----------|-------|
| AWS Account | 064357173439 |
| Region | us-west-2 |
| Lambda | `financial-ai-report` |
| S3 Bucket | `financial-ai-reports-064357173439` |
| Scheduler | `financial-ai-daily` (Mon–Fri 6:30 AM ET) |
| SES Recipient | sas3d@yahoo.com |
| Bedrock Model | Claude Haiku 3.5 (`anthropic.claude-3-5-haiku-20241022-v1:0`) |

---

## Prerequisites

Before deploying to a new account/environment, ensure you have:

1. **AWS CLI** installed and configured
   ```bash
   aws --version          # >= 2.x
   aws sts get-caller-identity   # confirm your identity
   ```

2. **Python 3.12** and **pip**
   ```bash
   python3 --version      # 3.12.x
   pip --version
   ```

3. **zip** utility
   ```bash
   # Ubuntu/Debian
   sudo apt-get install -y zip
   # Amazon Linux / RHEL
   sudo yum install -y zip
   ```

4. **SES email verified** (see Step 2 below)

5. **Bedrock model access enabled** — Claude Haiku 3.5 must be enabled in your region:
   - AWS Console → Bedrock → Model access → Enable `Anthropic Claude Haiku 3.5`

---

## Step-by-Step Deployment

### Step 1: Clone the repository

```bash
git clone https://github.com/saspto/financial-ai.git
cd financial-ai
```

### Step 2: Verify SES email address

SES is in sandbox mode by default. **Both sender and recipient must be verified**.

```bash
REGION="us-west-2"
EMAIL="sas3d@yahoo.com"

# Request verification (triggers email to the address)
aws sesv2 create-email-identity \
  --email-identity "$EMAIL" \
  --region "$REGION"
```

**Check your inbox** at `sas3d@yahoo.com` and click the verification link from AWS.

Check verification status:
```bash
aws sesv2 get-email-identity \
  --email-identity "sas3d@yahoo.com" \
  --region "$REGION" \
  --query "VerifiedForSendingStatus"
```
Should return `true` once clicked.

> **Sandbox limitation**: In sandbox mode you can only send to verified emails (max 200/day).
> To send to any address, request production access:
> AWS Console → SES → Account Dashboard → Request production access.

### Step 3: (Optional) Store API keys in SSM

Both APIs are optional — the system works with yfinance + RSS feeds alone.

```bash
./scripts/setup_ssm.sh
```

This prompts for:
- **NewsAPI key** — https://newsapi.org/register (free, 100 req/day)
- **Finnhub key** — https://finnhub.io/register (free, 60 req/min)

Or store them manually:
```bash
REGION="us-west-2"

aws ssm put-parameter \
  --name "/financial-ai/newsapi-key" \
  --value "YOUR_NEWSAPI_KEY" \
  --type SecureString \
  --region "$REGION"

aws ssm put-parameter \
  --name "/financial-ai/finnhub-key" \
  --value "YOUR_FINNHUB_KEY" \
  --type SecureString \
  --region "$REGION"
```

### Step 4: Enable Bedrock model access

```bash
# Check if model is accessible
aws bedrock list-foundation-models \
  --region us-west-2 \
  --query "modelSummaries[?modelId=='anthropic.claude-3-5-haiku-20241022-v1:0'].modelId" \
  --output text
```

If empty, go to: **AWS Console → Bedrock → Model access → Request access → Claude Haiku 3.5**

### Step 5: Run the deploy script

```bash
export AWS_REGION="us-west-2"
export SES_SENDER="sas3d@yahoo.com"
export SES_RECIPIENTS="sas3d@yahoo.com"

./scripts/deploy.sh
```

The script performs:
1. Creates deploy S3 bucket (`financial-ai-deploy-<ACCOUNT_ID>`)
2. Installs Python dependencies into a Lambda layer (~67 MB)
3. Zips and uploads the layer to S3
4. Packages and uploads Lambda function code
5. Deploys CloudFormation stack `financial-ai` (creates all resources)
6. Updates Lambda code in-place on re-deploys

---

## Manual Deploy (step by step)

If the deploy script fails, run each phase manually:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"
DEPLOY_BUCKET="financial-ai-deploy-${ACCOUNT_ID}"

# 1. Create deploy bucket
aws s3 mb "s3://$DEPLOY_BUCKET" --region "$REGION"

# 2. Build layer
mkdir -p /tmp/lambda-layer/python
pip install yfinance pandas numpy requests beautifulsoup4 lxml \
  boto3 reportlab Pillow feedparser python-dateutil pytz finnhub-python \
  --target /tmp/lambda-layer/python --quiet
cd /tmp/lambda-layer && zip -r /tmp/layer.zip python/ -x "*.pyc" -x "*/__pycache__/*"

# 3. Upload artifacts
aws s3 cp /tmp/layer.zip "s3://$DEPLOY_BUCKET/layer.zip"
cd financial-ai/lambda && zip -r /tmp/lambda.zip . -x "*.pyc" -x "*/__pycache__/*"
aws s3 cp /tmp/lambda.zip "s3://$DEPLOY_BUCKET/lambda.zip"

# 4. Deploy CloudFormation
aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yaml \
  --stack-name financial-ai \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --parameter-overrides \
    SESEmailSender="sas3d@yahoo.com" \
    SESEmailRecipients="sas3d@yahoo.com" \
    BedrockRegion="$REGION"
```

---

## Test the Lambda

### Quick test (skips S3 upload and email):
```bash
aws lambda invoke \
  --function-name financial-ai-report \
  --region us-west-2 \
  --payload '{"test": true}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/test-output.json && cat /tmp/test-output.json
```

### Full test (generates PDF, uploads to S3, sends email):
```bash
aws lambda invoke \
  --function-name financial-ai-report \
  --region us-west-2 \
  --payload '{}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/test-output.json && cat /tmp/test-output.json
```

### Watch logs in real time:
```bash
aws logs tail /aws/lambda/financial-ai-report \
  --region us-west-2 \
  --follow
```

---

## Re-deploy after code changes

```bash
cd financial-ai/lambda
zip -r /tmp/lambda.zip . -x "*.pyc" -x "*/__pycache__/*"
aws s3 cp /tmp/lambda.zip s3://financial-ai-deploy-064357173439/lambda.zip
aws lambda update-function-code \
  --function-name financial-ai-report \
  --s3-bucket financial-ai-deploy-064357173439 \
  --s3-key lambda.zip \
  --region us-west-2
```

---

## CloudFormation Stack Resources

| Resource | Type | Name |
|----------|------|------|
| Lambda Function | `AWS::Lambda::Function` | `financial-ai-report` |
| Lambda Layer | `AWS::Lambda::LayerVersion` | `financial-ai-deps` |
| IAM Role | `AWS::IAM::Role` | `financial-ai-lambda-role` |
| S3 Bucket | `AWS::S3::Bucket` | `financial-ai-reports-<ACCOUNT>` |
| KMS Key | `AWS::KMS::Key` | `alias/financial-ai-reports` |
| EventBridge Schedule | `AWS::Scheduler::Schedule` | `financial-ai-daily` |
| Scheduler IAM Role | `AWS::IAM::Role` | `financial-ai-scheduler-role` |
| CloudWatch Log Group | `AWS::Logs::LogGroup` | `/aws/lambda/financial-ai-report` |
| CloudWatch Alarm | `AWS::CloudWatch::Alarm` | `financial-ai-lambda-errors` |

---

## IAM Permissions Required for Deployment

The deploying principal needs:

```json
{
  "Effect": "Allow",
  "Action": [
    "cloudformation:*",
    "lambda:*",
    "s3:*",
    "iam:CreateRole", "iam:AttachRolePolicy", "iam:PutRolePolicy",
    "iam:PassRole", "iam:GetRole", "iam:DeleteRole", "iam:DetachRolePolicy",
    "kms:CreateKey", "kms:CreateAlias", "kms:Describe*",
    "scheduler:CreateSchedule", "scheduler:UpdateSchedule",
    "logs:CreateLogGroup", "logs:PutRetentionPolicy",
    "cloudwatch:PutMetricAlarm",
    "ssm:GetParameter"
  ],
  "Resource": "*"
}
```

---

## Teardown

To remove all resources:
```bash
# Empty the S3 bucket first (required before CFN deletion)
aws s3 rm s3://financial-ai-reports-064357173439 --recursive --region us-west-2

# Delete the stack
aws cloudformation delete-stack \
  --stack-name financial-ai \
  --region us-west-2

# Delete deploy bucket
aws s3 rb s3://financial-ai-deploy-064357173439 --force --region us-west-2

# Delete SSM parameters
aws ssm delete-parameter --name "/financial-ai/newsapi-key" --region us-west-2
aws ssm delete-parameter --name "/financial-ai/finnhub-key" --region us-west-2
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Lambda timeout | yfinance slow on market data day | Increase `LambdaTimeoutSec` to 900 |
| `AccessDeniedException` on Bedrock | Model not enabled | Enable Claude Haiku 3.5 in Bedrock console |
| `MessageRejected` from SES | Email not verified | Click verification link in inbox |
| `NoSuchBucket` | Deploy bucket not created | Re-run step 1 of manual deploy |
| Layer too large (>250MB) | Unzipped layer limit | Remove unused packages from requirements |
| PDF empty / no stocks | yfinance rate limited | Wait 60s and retry; data is cached after first call |
| `InvalidJSONResponse` from Bedrock | Haiku returned non-JSON | Check CloudWatch logs; often a transient issue |

---

## Schedule Reference

The EventBridge Scheduler runs: `cron(30 11 ? * MON-FRI *)` (UTC)
= **6:30 AM Eastern Time, Monday through Friday**

- **Monday**: report covers Friday 4 PM ET close through Sunday
- **Tuesday–Friday**: report covers previous trading day

To change the time, update the CloudFormation parameter `ScheduleExpression` or edit the scheduler directly:
```bash
aws scheduler update-schedule \
  --name financial-ai-daily \
  --schedule-expression "cron(0 12 ? * MON-FRI *)" \
  --schedule-expression-timezone "America/New_York" \
  --flexible-time-window '{"Mode":"FLEXIBLE","MaximumWindowInMinutes":10}' \
  --target '{"Arn":"arn:aws:lambda:us-west-2:064357173439:function:financial-ai-report","RoleArn":"..."}' \
  --region us-west-2
```

---

## Optional: Switch to Google Gemini instead of AWS Bedrock

By default the system uses **AWS Bedrock Claude Haiku 3.5**. You can switch to **Google Gemini** at any time — no code changes needed, only configuration.

### What changes

| Layer | Default (Bedrock) | Gemini alternative |
|-------|-------------------|-------------------|
| `LLM_PROVIDER` env var | `bedrock` | `gemini` |
| Auth | AWS IAM (automatic) | Gemini API key in SSM |
| Model | `anthropic.claude-3-5-haiku-20241022-v1:0` | `gemini-2.0-flash` (recommended) |
| Cost per report | ~$0.10 | ~$0.05–0.08 (Flash) |
| AWS Bedrock access needed | Yes | No |

### Supported Gemini models

| Model | Quality | Speed | Cost (input/output per 1M tokens) |
|-------|---------|-------|-----------------------------------|
| `gemini-2.0-flash` | Good | Fastest | $0.10 / $0.40 |
| `gemini-2.0-flash-thinking` | Better | Fast | $0.10 / $3.50 |
| `gemini-1.5-pro` | Best | Slower | $1.25 / $5.00 |
| `gemini-1.5-flash` | Good | Fast | $0.075 / $0.30 |

**Recommended**: `gemini-2.0-flash` — cheapest, fastest, sufficient for structured JSON financial summaries.

### Step 1: Get a Gemini API key

1. Go to **https://aistudio.google.com/apikey**
2. Click **Create API key**
3. Copy the key (starts with `AIza...`)

> Free tier: 15 req/min, 1,500 req/day — more than enough for one daily report.
> Paid tier activates automatically if you exceed free limits.

### Step 2: Store the API key in SSM

```bash
REGION="us-west-2"

aws ssm put-parameter \
  --name "/financial-ai/gemini-key" \
  --value "AIzaSy..." \
  --type SecureString \
  --overwrite \
  --region "$REGION"
```

Verify it was stored:
```bash
aws ssm get-parameter \
  --name "/financial-ai/gemini-key" \
  --with-decryption \
  --region "$REGION" \
  --query "Parameter.Value" \
  --output text
```

### Step 3: Re-deploy with Gemini enabled

**Option A — CloudFormation parameter** (recommended, keeps infra-as-code):

```bash
REGION="us-west-2"

aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yaml \
  --stack-name financial-ai \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --parameter-overrides \
    SESEmailSender="sas3d@yahoo.com" \
    SESEmailRecipients="sas3d@yahoo.com" \
    LLMProvider="gemini" \
    GeminiModelId="gemini-2.0-flash" \
  --no-fail-on-empty-changeset
```

**Option B — Update Lambda env var directly** (faster, no CFN update cycle):

```bash
REGION="us-west-2"

aws lambda update-function-configuration \
  --function-name financial-ai-report \
  --region "$REGION" \
  --environment "Variables={
    S3_BUCKET=financial-ai-reports-064357173439,
    SES_SENDER=sas3d@yahoo.com,
    SES_RECIPIENTS=sas3d@yahoo.com,
    BEDROCK_REGION=us-west-2,
    REPORT_PREFIX=reports,
    LLM_PROVIDER=gemini,
    GEMINI_MODEL_ID=gemini-2.0-flash,
    GEMINI_KEY_SSM_PARAM=/financial-ai/gemini-key
  }"
```

### Step 4: Add `google-generativeai` to the Lambda layer

The Gemini SDK must be included in the Lambda layer. Rebuild and re-upload:

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"
DEPLOY_BUCKET="financial-ai-deploy-${ACCOUNT_ID}"

# Rebuild layer with Gemini SDK added
rm -rf /tmp/lambda-layer
mkdir -p /tmp/lambda-layer/python
pip install \
  yfinance pandas numpy requests beautifulsoup4 lxml \
  boto3 reportlab Pillow feedparser python-dateutil pytz \
  finnhub-python google-generativeai \
  --target /tmp/lambda-layer/python --quiet

cd /tmp/lambda-layer
zip -r /tmp/layer.zip python/ -x "*.pyc" -x "*/__pycache__/*" > /dev/null
echo "Layer size: $(du -sh /tmp/layer.zip | cut -f1)"

# Upload and publish new layer version
aws s3 cp /tmp/layer.zip "s3://$DEPLOY_BUCKET/layer.zip" --region "$REGION"

LAYER_ARN=$(aws lambda publish-layer-version \
  --layer-name financial-ai-deps \
  --content "S3Bucket=$DEPLOY_BUCKET,S3Key=layer.zip" \
  --compatible-runtimes python3.12 \
  --region "$REGION" \
  --query "LayerVersionArn" \
  --output text)

echo "New layer ARN: $LAYER_ARN"

# Attach the new layer version to the function
aws lambda update-function-configuration \
  --function-name financial-ai-report \
  --layers "$LAYER_ARN" \
  --region "$REGION"
```

### Step 5: Test the Gemini-powered report

```bash
aws lambda invoke \
  --function-name financial-ai-report \
  --region us-west-2 \
  --payload '{"test": true}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/test-output.json && cat /tmp/test-output.json
```

Watch logs to confirm the right provider was used:
```bash
aws logs tail /aws/lambda/financial-ai-report \
  --region us-west-2 \
  --follow \
  --filter-pattern "LLM provider"
# Should print: LLM provider: Gemini (gemini-2.0-flash)
```

### Switching back to Bedrock

```bash
aws lambda update-function-configuration \
  --function-name financial-ai-report \
  --region us-west-2 \
  --environment "Variables={
    S3_BUCKET=financial-ai-reports-064357173439,
    SES_SENDER=sas3d@yahoo.com,
    SES_RECIPIENTS=sas3d@yahoo.com,
    BEDROCK_REGION=us-west-2,
    REPORT_PREFIX=reports,
    LLM_PROVIDER=bedrock,
    GEMINI_MODEL_ID=gemini-2.0-flash,
    GEMINI_KEY_SSM_PARAM=/financial-ai/gemini-key
  }"
```

### Gemini IAM note

No additional IAM permissions are required — Gemini authenticates via the API key fetched from SSM (already covered by the existing `/financial-ai/*` SSM policy). The `bedrock:InvokeModel` permission in the Lambda role is simply unused when `LLM_PROVIDER=gemini`.

### Troubleshooting Gemini

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RuntimeError: Gemini API key not found` | Key not in SSM | Run Step 2 above |
| `google.api_core.exceptions.PermissionDenied` | Invalid or revoked key | Regenerate key at aistudio.google.com |
| `ResourceExhausted: 429` | Free tier rate limit (15 req/min) | Add `time.sleep(5)` between calls, or upgrade to paid |
| `JSONDecodeError` after Gemini response | Model returned prose instead of JSON | Already handled — `response_mime_type: application/json` enforces JSON mode |
| `ModuleNotFoundError: google.generativeai` | Old layer without Gemini SDK | Re-run Step 4 to rebuild layer |
