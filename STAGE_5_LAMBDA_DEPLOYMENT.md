# Stage 5 — Lambda + EventBridge Deployment

Replace APScheduler (which dies on process restart) with serverless EventBridge triggers.

```
Current:  scheduler.py runs APScheduler in-process → calls run_ingestion() every hour
After:    EventBridge cron rule → triggers Lambda → calls run_ingestion() every hour
```

---

## Step 5.1 — Create the ECR Repository for Lambda

```bash
# Create a separate repo for Lambda (different base image than App Runner)
AWS_PROFILE=genai aws ecr create-repository \
  --repository-name genai-report-agent-lambda \
  --region eu-west-2 \
  --image-scanning-configuration scanOnPush=true
```

---

## Step 5.2 — Build and Push Lambda Image

```bash
# Build for linux/amd64
make docker-push-lambda
```

This will:
1. Log into ECR
2. Build the Lambda image using `Dockerfile.lambda`
3. Push to `743808053008.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent-lambda:latest`
4. Update the Lambda function code (if function already exists)

---

## Step 5.3 — Create the Lambda Function

```bash
AWS_PROFILE=genai aws lambda create-function \
  --function-name genai-report-agent-ingestion \
  --package-type Image \
  --code ImageUri=743808053008.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent-lambda:latest \
  --role arn:aws:iam::743808053008:role/GenAIReportAgentRole \
  --timeout 900 \
  --memory-size 2048 \
  --region eu-west-2 \
  --environment "Variables={
    LLM_PROVIDER=bedrock,
    AWS_DEFAULT_REGION=eu-west-2,
    AWS_ROLE_ARN=arn:aws:iam::743808053008:role/GenAIReportAgentRole,
    DEFAULT_TOPIC=uk_economy,
    USE_S3_ARCHIVE=true,
    MAX_URLS_PER_RUN=10,
    MAX_CRITIC_ITERATIONS=2
  }"
```

**Key settings:**
- `--timeout 900` — 15 minutes max (ingestion takes 2–5 min, plenty of headroom)
- `--memory-size 2048` — 2GB RAM (needed for LangGraph embeddings + Chroma)
- `--role` — Already has S3, Bedrock, Lambda permissions
- No `ANTHROPIC_API_KEY` — using Bedrock via role

---

## Step 5.4 — Test Lambda Manually

```bash
# Invoke manually
make lambda-test
```

This will:
1. Invoke the Lambda function
2. Decode and print the CloudWatch logs
3. Display the response JSON

**Success looks like:**
```json
{"statusCode": 200, "body": "{\"run_id\": \"abc123\", \"status\": \"success\"}"}
```

Verify the report landed in S3:
```bash
AWS_PROFILE=genai aws s3 ls s3://genai-report-agent/reports/uk_economy/
# Should show a new .json file with recent timestamp
```

---

## Step 5.5 — Create the EventBridge Rule

```bash
# Create cron rule — fires every hour at minute 0
AWS_PROFILE=genai aws events put-rule \
  --name genai-ingestion-hourly \
  --schedule-expression "cron(0 * * * ? *)" \
  --state ENABLED \
  --region eu-west-2

# Give EventBridge permission to invoke Lambda
AWS_PROFILE=genai aws lambda add-permission \
  --function-name genai-report-agent-ingestion \
  --statement-id EventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:eu-west-2:743808053008:rule/genai-ingestion-hourly \
  --region eu-west-2

# Wire the rule to the Lambda
AWS_PROFILE=genai aws events put-targets \
  --rule genai-ingestion-hourly \
  --targets "Id=genai-lambda,Arn=arn:aws:lambda:eu-west-2:743808053008:function:genai-report-agent-ingestion" \
  --region eu-west-2
```

---

## Step 5.6 — Verify Everything is Wired

```bash
# Lambda exists and is ready
AWS_PROFILE=genai aws lambda get-function \
  --function-name genai-report-agent-ingestion \
  --region eu-west-2

# EventBridge rule is enabled
AWS_PROFILE=genai aws events list-rules \
  --region eu-west-2 \
  --query "Rules[?Name=='genai-ingestion-hourly']"

# Rule has targets
AWS_PROFILE=genai aws events list-targets-by-rule \
  --rule genai-ingestion-hourly \
  --region eu-west-2

# Lambda has permission from EventBridge
AWS_PROFILE=genai aws lambda get-policy \
  --function-name genai-report-agent-ingestion \
  --region eu-west-2
```

---

## Step 5.7 — Monitor Ingestion

View Lambda invocations and logs:

```bash
# Last 10 invocations (success/failure)
AWS_PROFILE=genai aws logs tail /aws/lambda/genai-report-agent-ingestion \
  --region eu-west-2 --follow

# Or check CloudWatch for metrics:
# - Invocations (should increase every hour)
# - Duration (should be 2–5 min)
# - Errors (should be 0)
```

---

## Step 5.8 — Update Lambda Code (Deployment)

When you push new code:

```bash
make docker-push-lambda
```

This rebuilds the image, pushes it, and updates the Lambda function in one step.

---

## Troubleshooting

**Lambda invocation fails:**
- Check IAM role has S3, Bedrock, and KMS permissions
- Check environment variables are set (LLM_PROVIDER, USE_S3_ARCHIVE)
- Check CloudWatch logs: `aws logs tail /aws/lambda/genai-report-agent-ingestion --follow`

**EventBridge never triggers:**
- Verify rule is ENABLED: `aws events list-rules --query "Rules[?Name=='genai-ingestion-hourly']"`
- Check rule has targets: `aws events list-targets-by-rule --rule genai-ingestion-hourly`
- Check Lambda has permission: `aws lambda get-policy --function-name genai-report-agent-ingestion`

**Reports not in S3:**
- Check Lambda logs for ingestion errors
- Verify S3 bucket exists: `aws s3 ls s3://genai-report-agent/`
- Check IAM role has S3 PutObject permission

---

## Next: Stage 6 — App Runner

Once Lambda is working, move to App Runner (the public Streamlit UI). Ready?
