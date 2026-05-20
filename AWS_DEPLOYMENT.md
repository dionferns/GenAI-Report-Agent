# AWS Deployment Guide — GenAI Report Agent

> Deploy your Streamlit UI to AWS for your interview demo.

---

## TL;DR (5-Minute Setup)

```bash
# 1. Set up Bedrock credentials locally first
cp .env.example .env
# Edit .env with your AWS credentials

# 2. Test Bedrock connectivity
source .venv/bin/activate
python test_simple.py

# 3. Deploy to App Runner
aws apprunner create-service \
  --service-name genai-report-agent \
  --source-configuration imageRepository={imageIdentifier=ACCOUNT.dkr.ecr.REGION.amazonaws.com/genai-report-agent:latest,imageRepositoryType=ECR}

# 4. Visit public URL (provided by App Runner)
# https://xxxxx.awsapprunner.com
```

---

## Prerequisites

### AWS Account Setup

1. **Create AWS Account** (if needed)
   - https://aws.amazon.com/

2. **Install AWS CLI**
   ```bash
   # macOS
   brew install awscli

   # Or via pip
   pip install awscli
   ```

3. **Configure Credentials**
   ```bash
   aws configure
   # Enter:
   # AWS Access Key ID: [your key]
   # AWS Secret Access Key: [your secret]
   # Default region: eu-west-2
   # Default output format: json
   ```

   Or set environment variables:
   ```bash
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=eu-west-2
   ```

### Request Bedrock Model Access

1. Go to: https://console.aws.amazon.com/bedrock
2. Click: **"Model access"** (bottom left)
3. Click: **"Manage model access"**
4. Find: **"Anthropic Claude 3.5 Sonnet"**
5. Check the box and click **"Save changes"**
6. **Wait 5-10 minutes** for approval

**Verify approval:**
```bash
aws bedrock list-foundation-models --region eu-west-2
# Should include: anthropic.claude-3-5-sonnet-20241022-v2:0
```

---

## Option 1: AWS App Runner (Easiest)

**Best for:** Quick interview demo, minimal DevOps

### Step 1: Enable Bedrock Locally

```bash
# Edit .env
nano .env

# Set:
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_DEFAULT_REGION=eu-west-2
```

### Step 2: Test Bedrock Connection

```bash
source .venv/bin/activate
python test_simple.py

# Should output:
# ✅ Bedrock connected
```

### Step 3: Push to GitHub

```bash
git add -A
git commit -m "Configure for AWS Bedrock and App Runner deployment"
git push origin main
```

### Step 4: Create App Runner Service (Via Console)

1. Go to: https://console.aws.amazon.com/apprunner
2. Click: **"Create service"**
3. **Source:**
   - Select: "Source code repository"
   - Click: "Connect to GitHub"
   - Select your repo
   - Branch: `main`

4. **Build settings:**
   - Runtime: Python 3.11
   - Build command: `pip install -r requirements.txt && pip install -e .`

5. **Configure service:**
   - **Port:** 8080
   - **Start command:** `streamlit run src/reportagent/ui/app.py --server.port=8080 --server.address=0.0.0.0`

6. **Environment variables:**
   ```
   LLM_PROVIDER=bedrock
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   AWS_DEFAULT_REGION=eu-west-2
   CHROMA_PERSIST_DIR=/tmp/chroma
   SQLITE_DB_PATH=/tmp/archive.db
   ```

7. **Instance:**
   - CPU: 1 vCPU
   - Memory: 2 GB (minimum)
   - Concurrency: 100

8. Click: **"Create & deploy"**

9. **Wait 5-10 minutes** for deployment

10. **Visit:** Copy the public URL from the App Runner dashboard
    ```
    https://xxxxx.awsapprunner.com
    ```

---

## Option 2: AWS ECS + Fargate (More Control)

**Best for:** Production-grade setup, auto-scaling

### Step 1: Create ECR Repository

```bash
aws ecr create-repository \
  --repository-name genai-report-agent \
  --region eu-west-2
```

Save the URI from output (e.g., `123456789.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent`)

### Step 2: Build and Push Docker Image

```bash
# Login to ECR
aws ecr get-login-password --region eu-west-2 | \
  docker login --username AWS --password-stdin 123456789.dkr.ecr.eu-west-2.amazonaws.com

# Build image
docker build -t genai-report-agent:latest .

# Tag image
docker tag genai-report-agent:latest \
  123456789.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent:latest

# Push to ECR
docker push 123456789.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent:latest
```

### Step 3: Create ECS Task Definition

Create file: `ecs-task-definition.json`

```json
{
  "family": "genai-report-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "genai-report-agent",
      "image": "123456789.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "hostPort": 8080,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "LLM_PROVIDER",
          "value": "bedrock"
        },
        {
          "name": "AWS_DEFAULT_REGION",
          "value": "eu-west-2"
        }
      ],
      "secrets": [
        {
          "name": "AWS_ACCESS_KEY_ID",
          "valueFrom": "arn:aws:secretsmanager:eu-west-2:123456789012:secret:genai/aws-key"
        },
        {
          "name": "AWS_SECRET_ACCESS_KEY",
          "valueFrom": "arn:aws:secretsmanager:eu-west-2:123456789012:secret:genai/aws-secret"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/genai-report-agent",
          "awslogs-region": "eu-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole"
}
```

### Step 4: Register Task Definition

```bash
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json \
  --region eu-west-2
```

### Step 5: Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name genai-report-agent \
  --region eu-west-2
```

### Step 6: Create ECS Service

```bash
aws ecs create-service \
  --cluster genai-report-agent \
  --service-name genai-report-agent-service \
  --task-definition genai-report-agent:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=genai-report-agent,containerPort=8080 \
  --region eu-west-2
```

---

## Option 3: AWS Lambda + API Gateway (Serverless)

**Best for:** Cost-sensitive, minimal traffic

Not ideal for Streamlit (requires web socket support), but possible.

Alternative: Use Lambda for ingestion only, keep Streamlit on App Runner.

---

## Storage Considerations

### Current Setup (File-Based)

```
.env:
CHROMA_PERSIST_DIR=./data/chroma
SQLITE_DB_PATH=./data/archive.db
```

**Problem:** Data lost on App Runner restart

### Solution 1: EFS (Persistent File System)

For App Runner:

```bash
# Create EFS
aws efs create-file-system \
  --region eu-west-2 \
  --performance-mode generalPurpose

# Mount to App Runner service
# (Via console: Service Details → EFS → Mount)
```

Then use:
```env
CHROMA_PERSIST_DIR=/mnt/efs/chroma
SQLITE_DB_PATH=/mnt/efs/archive.db
```

### Solution 2: DynamoDB + S3 (Production)

See [migration guide](#migrating-storage-to-aws) below.

---

## Migrating Storage to AWS

For production, replace local storage:

### Chroma → OpenSearch Serverless

```python
# src/reportagent/storage/vector_aws.py
import boto3

opensearch_client = boto3.client(
    'opensearchserverless',
    region_name='eu-west-2'
)

# Use instead of local Chroma
# Full implementation in docs/architecture.md Section 18
```

### SQLite → DynamoDB

```python
# src/reportagent/storage/archive_aws.py
import boto3

dynamodb = boto3.resource(
    'dynamodb',
    region_name='eu-west-2'
)

# Use instead of local SQLite
# Full implementation in docs/architecture.md Section 18
```

---

## Monitoring & Logs

### App Runner Logs

```bash
# View real-time logs
aws apprunner describe-service \
  --service-arn arn:aws:apprunner:eu-west-2:123456789012:service/genai-report-agent \
  --region eu-west-2 \
  --query 'Service.ServiceStatus' \
  --output text

# View logs in CloudWatch
# https://console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logStream:
```

### Set Up Alarms

```bash
# Monitor service health
aws cloudwatch put-metric-alarm \
  --alarm-name genai-report-agent-health \
  --alarm-description "Alert if App Runner service is unhealthy" \
  --metric-name ServiceStatus \
  --namespace AWS/AppRunner \
  --statistic Average \
  --period 300 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --evaluation-periods 1 \
  --region eu-west-2
```

---

## Cost Estimate

### Option 1: App Runner

- **Base:** $0.029 per vCPU-hour + $0.005 per GB-hour
- **Minimum config (1 vCPU, 2GB):** ~$30-50/month
- **With data transfer:** +$0.01/GB after free tier

### Option 2: ECS + Fargate

- **Fargate compute:** $0.04664 per vCPU-hour + $0.00511 per GB-hour
- **Minimum config:** ~$30-40/month
- **Load Balancer:** +$16/month
- **Total:** ~$50-60/month

### Option 3: Lambda (if you rewrite for API)

- **Invocations:** $0.20 per 1M
- **Compute:** $0.0000166667 per GB-second
- **Could be ~$10/month** if low traffic

**For interview demo:** Use App Runner (simplest, ~$40/month)

---

## Deployment Checklist

- [ ] AWS account created
- [ ] AWS CLI installed and configured
- [ ] Bedrock model access requested and approved
- [ ] `.env` configured with AWS credentials
- [ ] Bedrock connectivity tested locally (`python test_simple.py`)
- [ ] Code pushed to GitHub
- [ ] App Runner service created (or ECS cluster set up)
- [ ] Environment variables configured in AWS
- [ ] Service deployed and running
- [ ] Public URL accessible
- [ ] Ingestion tested (manual trigger in UI)
- [ ] Chat tested with real data

---

## Troubleshooting

### "Bedrock model not found"
```bash
# Check if model access is approved
aws bedrock list-foundation-models --region eu-west-2

# If not showing claude-3-5-sonnet, request access again in console
```

### "Access Denied" on Bedrock
```bash
# Verify credentials
aws sts get-caller-identity

# Check IAM permissions
# User needs: bedrock:InvokeModel on *
```

### "Streamlit connection refused"
```bash
# App Runner exposes port 8080, ensure Streamlit is listening
# Check Dockerfile and App Runner config

# Restart service
aws apprunner start-deployment \
  --service-arn arn:aws:apprunner:eu-west-2:123456789012:service/genai-report-agent
```

### "Data lost on restart"
```bash
# Add EFS or migrate to DynamoDB
# See "Storage Considerations" section above
```

---

## Next Steps

1. **Set up Bedrock locally first** (test before deploying)
   ```bash
   python test_simple.py
   ```

2. **Deploy to App Runner** (easiest for interview)
   - Follow "Option 1" steps above

3. **Monitor in production**
   - Watch CloudWatch logs
   - Set up cost alarms

4. **Scale if needed** (after interview)
   - Switch to ECS + Fargate for auto-scaling
   - Migrate to DynamoDB + OpenSearch for larger corpus

---

## Resources

- [AWS App Runner docs](https://docs.aws.amazon.com/apprunner/)
- [Bedrock API docs](https://docs.aws.amazon.com/bedrock/latest/APIReference/)
- [Streamlit AWS deployment guide](https://docs.streamlit.io/knowledge-base/deployment/deploy-streamlit-using-aws-apprunner)
- [Project README Section 18](./README.md#18-aws-deployment-notes)

---

## Support

If deployment fails:

1. Check CloudWatch logs: `https://console.aws.amazon.com/cloudwatch`
2. Verify Bedrock access: `aws bedrock list-foundation-models --region eu-west-2`
3. Test locally first: `python test_simple.py`
4. Review this guide's Troubleshooting section

Good luck with your interview! 🚀

