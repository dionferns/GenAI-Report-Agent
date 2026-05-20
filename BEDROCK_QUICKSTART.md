# Bedrock Quick Start — Get Running on AWS in 15 Minutes

> Everything you need to test Bedrock locally and deploy to AWS for your interview.

---

## 15-Minute Local Setup

### 1. Install AWS CLI (2 min)

```bash
# macOS
brew install awscli

# Verify
aws --version
```

### 2. Configure AWS Credentials (2 min)

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: eu-west-2
# Default output format: json
```

Or set environment variables:
```bash
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=eu-west-2
```

### 3. Request Bedrock Model Access (1 min request + 5-10 min approval)

**In AWS Console:**
1. Go to: https://console.aws.amazon.com/bedrock
2. Click: **"Model access"** (left sidebar)
3. Click: **"Manage model access"**
4. Search for: **"Claude 3.5 Sonnet"**
5. Check the box
6. Click: **"Save changes"**
7. **Wait 5-10 minutes** ⏳

**Verify approval:**
```bash
aws bedrock list-foundation-models --region eu-west-2 | grep -i sonnet
# Should show: anthropic.claude-3-5-sonnet-20241022-v2:0
```

### 4. Configure Project for Bedrock (2 min)

```bash
# Edit .env
nano .env
```

Add/update:
```env
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=eu-west-2
```

### 5. Test Bedrock Connection (2 min)

```bash
source .venv/bin/activate
python test_simple.py
```

**Expected output:**
```
✅ Imports: OK
✅ Configuration: OK
✅ Database: OK
✅ Vector Store: OK
✅ LLM (Bedrock): OK
```

All 5 tests passing? ✅ You're ready to deploy!

---

## Deploy to AWS (Option: App Runner — 10 min)

### 1. Update Dockerfile (Already done ✅)

The Dockerfile has been pre-configured for AWS App Runner.

### 2. Push to GitHub

```bash
git add -A
git commit -m "Configure for AWS Bedrock deployment"
git push origin main
```

### 3. Create App Runner Service

Go to: https://console.aws.amazon.com/apprunner

**Step 1: Create service**
- Click "Create service"

**Step 2: Source**
- "Source code repository"
- Connect to GitHub (authorize if needed)
- Select your repo
- Branch: `main`

**Step 3: Build settings**
- Runtime: Python 3.11
- Build command: `pip install -r requirements.txt && pip install -e .`
- Start command: (leave blank — uses Dockerfile)

**Step 4: Service settings**
- Service name: `genai-report-agent`
- Port: 8080

**Step 5: Environment variables**
Click "Add environment variable" for each:

| Key | Value |
|-----|-------|
| `LLM_PROVIDER` | `bedrock` |
| `AWS_ACCESS_KEY_ID` | Your AWS key |
| `AWS_SECRET_ACCESS_KEY` | Your AWS secret |
| `AWS_DEFAULT_REGION` | `eu-west-2` |
| `CHROMA_PERSIST_DIR` | `/tmp/chroma` |
| `SQLITE_DB_PATH` | `/tmp/archive.db` |

**Step 6: Instance configuration**
- vCPU: 1
- Memory: 2 GB
- Concurrency: 100

**Step 7: Review and create**
- Click "Create & deploy"
- ⏳ Wait 5-10 minutes for deployment

### 4. Get Public URL

Once deployed, App Runner shows your public URL:
```
https://xxxxx.awsapprunner.com
```

Share this with your interviewer! 🎉

---

## Test the Deployment

### 1. Visit the UI

```
https://xxxxx.awsapprunner.com
```

### 2. Trigger Ingestion

Click the **"Trigger Ingestion"** button in the sidebar.

This will:
- Fetch real BBC + gov.uk articles
- Process them through the pipeline
- Generate a report using Claude via Bedrock
- Populate the vector store

⏳ Takes 2-3 minutes.

### 3. Ask Questions

Once ingestion completes, ask the chat:
- "What's the latest AI regulation in the UK?"
- "Which organizations are involved?"
- "What's new compared to last week?"

The system will:
- Retrieve relevant articles
- Generate answers using Claude via Bedrock
- Show citations from source articles

---

## Troubleshooting

### "Bedrock model not approved"

```bash
# Check approval status
aws bedrock list-foundation-models --region eu-west-2

# If not showing, request again in AWS console
# Takes 5-10 minutes to approve
```

### "Access Denied" error

```bash
# Verify credentials are correct
aws sts get-caller-identity

# Should show your AWS account info
```

### "Service stuck in deployment"

Go to App Runner console → Click your service → Click "Actions" → "Retry deployment"

### "Streamlit not loading"

Check logs:
1. Go to App Runner console
2. Click your service
3. Go to "Logs" tab
4. Look for errors

### "Data lost after restart"

App Runner uses ephemeral storage. To persist data:
- Add EFS mount (see AWS_DEPLOYMENT.md)
- Or: Re-ingest data on each deployment

---

## What Happens Next

### For Interview Demo

1. **Local testing** (15 min with this guide):
   - ✅ Bedrock configured
   - ✅ `test_simple.py` passes
   - ✅ Can run ingestion locally

2. **AWS deployment** (10 min with this guide):
   - ✅ App Runner service live
   - ✅ Public URL ready
   - ✅ Interviewer can test live

3. **Show in interview**:
   - "This is running on AWS App Runner"
   - "It uses AWS Bedrock for LLM calls"
   - "Real data from BBC and UK Government"
   - "Can ingest new articles in real-time"
   - "Uses hybrid search (BM25 + vector)"
   - "Chat responses include citations"

### After Interview

- Shut down App Runner to stop incurring costs (or keep running for ~$40/month)
- Migrate to DynamoDB + OpenSearch if you want permanent deployment
- Add authentication if making this a real product

---

## Key Points for Interview

**Why Bedrock?**
- "AWS Bedrock provides reliable, enterprise-grade LLM access"
- "No API credit worries — pay per usage"
- "Auto-scaling, no ops needed"
- "Integrates with other AWS services (DynamoDB, OpenSearch, CloudWatch)"

**Why App Runner?**
- "Simplest path from Docker to production"
- "No Kubernetes, no container orchestration"
- "Automatic HTTPS, auto-scaling, basic monitoring"
- "Perfect for demos and MVPs"

**Architecture highlights:**
- "Two separate LangGraph StateGraphs for ingestion and chat"
- "Critic node ensures factual accuracy"
- "Hybrid search combines BM25 + vector embeddings"
- "Structured logging with LangSmith tracing"
- "Ready to scale to OpenSearch + DynamoDB on AWS"

---

## Quick Reference

### Local Commands

```bash
# Test Bedrock
python test_simple.py

# Run ingestion locally
python scripts/trigger_once.py

# Start chat UI locally
streamlit run src/reportagent/ui/app.py
```

### AWS Commands

```bash
# Check Bedrock access
aws bedrock list-foundation-models --region eu-west-2

# Check your identity
aws sts get-caller-identity

# View App Runner logs
aws apprunner describe-service \
  --service-arn arn:aws:apprunner:REGION:ACCOUNT:service/genai-report-agent

# Stop App Runner (to save costs)
aws apprunner pause-service \
  --service-arn arn:aws:apprunner:REGION:ACCOUNT:service/genai-report-agent
```

---

## Summary

| Step | Time | Status |
|------|------|--------|
| Install AWS CLI | 2 min | ⏳ Do first |
| Request Bedrock access | 1 min + 5-10 min wait | ⏳ Do while waiting |
| Configure .env | 2 min | ⏳ After approval |
| Test locally | 2 min | ✅ Should pass |
| Push to GitHub | 2 min | ✅ Ready |
| Deploy to App Runner | 5-10 min | ⏳ Wait for deployment |
| Test on AWS | 5 min | ✅ Should work |
| **Total** | **~30 min** | **Ready for demo** |

---

## Next: Full Deployment Guide

For more options and detailed troubleshooting, see: **AWS_DEPLOYMENT.md**

Good luck! 🚀

