# Stage 5 Quick Reference

## Files Created This Stage

| File | Purpose | Key Content |
|------|---------|-------------|
| `src/reportagent/lambda_handler.py` | AWS Lambda entry point | `def lambda_handler(event, context):` — invokes ingestion graph |
| `Dockerfile.lambda` | Lambda container image | Base: `public.ecr.aws/lambda/python:3.11` |
| `STAGE_5_LAMBDA_DEPLOYMENT.md` | Full deployment guide | 8 steps + verification + troubleshooting |
| `STAGE_5_SUMMARY.md` | Architecture explanation | Before/after, cost, what each step does |

## Files Modified This Stage

| File | Change |
|------|--------|
| `.env.example` | Added comment: Lambda uses Bedrock + S3 (no local API key) |
| `Makefile` | Added `docker-push-lambda` and `lambda-test` targets |
| `MEMORY.md` | Added entry: Stage 5 implementation details |

## What Each File Does

### `lambda_handler.py`
- **What:** Function that AWS calls every hour
- **Why:** Lambda requires a specific entry point
- **How:** Sets up logging, creates IngestionState, runs ingestion_graph, returns JSON response

### `Dockerfile.lambda`
- **What:** Container image for Lambda (different from App Runner)
- **Why:** Lambda and App Runner have different requirements (function vs. web server)
- **How:** Uses AWS Lambda Python base, installs deps, sets entrypoint to `lambda_handler`

### `Makefile targets`
- **`make docker-push-lambda`:** Build image → Push to ECR → Update Lambda function (1 command)
- **`make lambda-test`:** Manually invoke Lambda once, decode logs, show response (for verification)

### `STAGE_5_LAMBDA_DEPLOYMENT.md`
- **What:** Step-by-step guide to deploy Lambda + EventBridge
- **Why:** Multiple AWS resources must be created and wired together
- **How:** 8 ordered steps, verification commands, troubleshooting

### `STAGE_5_SUMMARY.md`
- **What:** Explanation of what we built and why
- **Why:** Helps understand the architecture change
- **How:** Before/after diagram, cost comparison, step-by-step walkthrough

---

## The 5 Steps We Did & Why

### Step 1: Created Lambda Handler
**What:** `lambda_handler()` function  
**Why:** AWS Lambda needs a specific entry point to call every hour  
**Result:** EventBridge can now call your Python function

### Step 2: Created Lambda Dockerfile
**What:** Container image with Python + dependencies + code  
**Why:** Lambda and App Runner both run Docker, but different bases/entrypoints  
**Result:** AWS can pull the image and run your function

### Step 3: Updated `.env.example`
**What:** Documented that Lambda uses Bedrock (not Anthropic API key)  
**Why:** Prevent confusion when deploying to Lambda  
**Result:** Clear instructions for configuring Lambda environment

### Step 4: Added Makefile Targets
**What:** `docker-push-lambda` and `lambda-test` commands  
**Why:** Automate the build-push-test workflow  
**Result:** One command instead of 4+ AWS CLI calls

### Step 5: Created Deployment Guide
**What:** 8-step checklist from "image ready" → "EventBridge invoking Lambda hourly"  
**Why:** Multiple AWS resources; easy to miss a step  
**Result:** Repeatable, documented deployment process

---

## Why We Needed Each File

| File | Solves | Problem |
|------|--------|---------|
| `lambda_handler.py` | "How do I tell AWS what to run?" | AWS Lambda needs a function entry point |
| `Dockerfile.lambda` | "How do I package code for Lambda?" | Lambda runs containerized code |
| Makefile targets | "How do I avoid typing 4+ AWS CLI commands?" | Manual deployment is error-prone |
| `STAGE_5_LAMBDA_DEPLOYMENT.md` | "What are the exact steps to deploy?" | Lambda + EventBridge involve many resources |
| `STAGE_5_SUMMARY.md` | "Why are we doing this?" | Understand the architecture change and cost savings |

---

## Architecture at a Glance

```
OLD: App Runner runs scheduler 24/7 (costs $30/month, crashes = no ingestion)
NEW: EventBridge → Lambda every hour (costs $0.20/month, auto-restarts)
```

---

## How to Deploy (Quick Checklist)

```bash
# 1. Create ECR repo (one-time setup)
aws ecr create-repository --repository-name genai-report-agent-lambda

# 2. Build & push image
make docker-push-lambda

# 3. Create Lambda function (copy-paste from deployment guide)
aws lambda create-function --function-name genai-report-agent-ingestion ...

# 4. Test manually
make lambda-test

# 5. Wire EventBridge (3 AWS CLI commands from deployment guide)
# See STAGE_5_LAMBDA_DEPLOYMENT.md Step 5.5

# 6. Verify everything
aws lambda get-function --function-name genai-report-agent-ingestion
aws events list-rules --query "Rules[?Name=='genai-ingestion-hourly']"
```

---

## What "Serverless" Really Means

- **Not:** There's no server
- **Actually:** AWS manages the server for you
- **You:** Write the function, push the image, set the trigger
- **AWS:** Runs it when needed, charges only for execution time
- **Benefit:** Don't worry about uptime, auto-scaling, or keeping processes alive

---

## Next Stage: Stage 6 (App Runner)

Once Lambda works:
1. App Runner runs just Streamlit (no scheduler)
2. Lambda handles all ingestion
3. App Runner reads reports from S3 (populated by Lambda)
4. Users hit the public App Runner URL, chat with the bot

Ready? → Continue to Stage 6
