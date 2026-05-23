# Stage 5 Summary — Lambda + EventBridge

## What We Did

Replaced the local APScheduler (which crashes on process restart) with serverless AWS Lambda + EventBridge for reliable hourly ingestion.

---

## 5 Key Changes

### 1️⃣ Created Lambda Handler (`src/reportagent/lambda_handler.py`)

**Purpose:** Entry point that AWS calls every hour

**What it does:**
```python
def lambda_handler(event, context):
    # AWS calls this when EventBridge triggers
    # Sets up logging, creates IngestionState, runs ingestion graph
    # Returns {"statusCode": 200, "body": {...}} to confirm success
```

**Why needed:** Lambda requires a specific function signature. This is what AWS invokes. It's thin — just a wrapper around the existing ingestion logic.

---

### 2️⃣ Created Lambda Dockerfile (`Dockerfile.lambda`)

**Purpose:** Container image for Lambda (different from App Runner)

**Key differences from App Dockerfile:**
- Base image: `public.ecr.aws/lambda/python:3.11` (Lambda optimized)
- Entrypoint: `reportagent.lambda_handler.lambda_handler` (function to call)
- No Streamlit (not a web server, just batch processing)

**Why needed:** Lambda and App Runner both use Docker, but with different requirements:
- App Runner: long-running web server
- Lambda: short function execution (2–5 min), then stop

---

### 3️⃣ Updated `.env.example`

**Added:**
```
# Lambda + EventBridge (production only)
# Set LLM_PROVIDER=bedrock, USE_S3_ARCHIVE=true, and AWS_DEFAULT_REGION
```

**Why needed:** Documents that Lambda uses different env vars (Bedrock + S3 instead of local Anthropic key). Prevents confusion later.

---

### 4️⃣ Added Makefile Targets

**`make docker-push-lambda`**
- Builds Lambda image
- Pushes to ECR
- Updates Lambda function code
- One command instead of 4+

**`make lambda-test`**
- Manually invokes Lambda
- Shows CloudWatch logs
- Verifies function works before enabling scheduled runs

**Why needed:** Automation. Testing. Removes manual AWS CLI commands.

---

### 5️⃣ Created Deployment Guide (`STAGE_5_LAMBDA_DEPLOYMENT.md`)

**Contains:**
- 8 step-by-step instructions (create ECR repo → wire EventBridge)
- Verification commands (check Lambda created, rule enabled, etc.)
- Troubleshooting guide
- Cost breakdown

**Why needed:** Lambda + EventBridge involve multiple AWS resources. Easy to miss steps. Guide is a checklist.

---

## Architecture Change

### Before (APScheduler)
```
┌─────────────────────────┐
│   App Runner            │
│  (always running)       │
│  ┌──────────────────┐   │
│  │ scheduler.py     │   │
│  │ APScheduler:     │   │
│  │ - wakes up/hour  │   │
│  │ - runs ingestion │   │
│  │ - 55 min idle    │   │
│  └──────────────────┘   │
└─────────────────────────┘
         ❌ Crashes = no more ingestion
         ❌ Wastes compute (55 min idle/hour)
         ❌ Hard to scale
```

### After (Lambda + EventBridge)
```
┌──────────────────────────┐
│   EventBridge            │
│  cron(0 * * * ? *)       │
│  Every hour at :00       │
└──────────┬───────────────┘
           │
           ↓
┌──────────────────────────┐
│   Lambda                 │
│  genai-report-agent-     │
│  ingestion               │
│  (runs 2–5 min only)     │
└──────────┬───────────────┘
           │
           ↓
    ┌──────────────┐
    │   S3         │
    │  (reports)   │
    └──────────────┘

✅ Crashes don't matter (AWS manages trigger)
✅ Zero cost when idle (~$0.20/month)
✅ Easy to scale (AWS handles parallelism)
```

---

## What Each Step Did & Why

| Step | What | Why |
|------|------|-----|
| Lambda Handler | Created `lambda_handler()` function | AWS Lambda needs a specific entry point to call |
| Lambda Dockerfile | Built container with Python + deps | Lambda runs containerized; different base than App Runner |
| `.env.example` | Added note about Lambda env vars | Prevent confusion: Lambda uses Bedrock + IAM role, not API key |
| Makefile targets | Automated build-push-test workflow | No need to type 4+ AWS CLI commands manually |
| Deployment Guide | Step-by-step instructions + verification | Multiple AWS resources; easy to miss a step |

---

## How It Works (Step-by-Step)

### 1. You run: `make docker-push-lambda`
- Builds image locally (Python 3.11 + deps + your code)
- Pushes to ECR (AWS Docker registry)
- Updates Lambda function to use new image

### 2. EventBridge fires every hour at :00
- AWS has the rule: `cron(0 * * * ? *)`
- No process running; it's a managed AWS service

### 3. Lambda cold start (~500ms)
- AWS pulls your image from ECR
- Starts Python runtime
- Calls `lambda_handler()`

### 4. Ingestion runs (2–5 min)
- Same code as local: fetches articles, generates report, saves to S3
- Logs go to CloudWatch (for debugging)

### 5. Lambda shuts down
- AWS stops the container
- You're charged only for the time it ran (~$0.02 per invocation)

---

## Cost Comparison

| Component | Old (APScheduler on App Runner) | New (Lambda + EventBridge) |
|-----------|----------------------------------|----------------------------|
| Compute | $30/month (always running) | $0.18/month (only when running) |
| Storage | - | - |
| **Total** | **~$30/month** | **~$0.20/month** |

**Savings:** ~$360/year, plus better reliability.

---

## Next Steps

1. **Create ECR repo** (if not exists)
2. **Push Lambda image**: `make docker-push-lambda`
3. **Create Lambda function** (copy command from deployment guide)
4. **Test manually**: `make lambda-test`
5. **Wire EventBridge** (4 CLI commands from deployment guide)
6. **Verify**: Check CloudWatch logs, verify S3 has new reports

Once done → **Stage 6: App Runner** (public Streamlit UI)

---

## Files Changed

```
Created:
  src/reportagent/lambda_handler.py      ← Entry point for Lambda
  Dockerfile.lambda                       ← Container image for Lambda
  STAGE_5_LAMBDA_DEPLOYMENT.md            ← Deployment guide + verification
  STAGE_5_SUMMARY.md                      ← This file

Modified:
  .env.example                            ← Added Lambda env var notes
  Makefile                                ← Added docker-push-lambda, lambda-test
```

---

## Key Insight

**Lambda is not a web server. It's a function-as-a-service.**

- App Runner: "Run my Streamlit app 24/7"
- Lambda: "Run this function when triggered, then stop"

This is why we have:
- Different Dockerfile (Lambda base image vs. Python base)
- Different entrypoint (function vs. streamlit command)
- Different pricing (per-invocation vs. per-hour)

Both use Docker, but solve different problems.
