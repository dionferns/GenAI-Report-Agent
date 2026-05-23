# AWS Integration Plan

## Overview

This plan outlines how to migrate the GenAI Report Agent from a local, self-contained setup to production-grade AWS services. It maps directly to the AWS services mentioned in the job description (Lambda, SageMaker, Bedrock, S3, EC2, ECS) while keeping the scope realistic for a portfolio project.

The goal: **Create a deployable system where someone can visit a single AWS URL and use the full product end-to-end.**

---

## Current Local Architecture vs Production Gaps

| Component | Current (Local) | Production Gap | AWS Solution |
|---|---|---|---|
| **LLM** | Bedrock (llama3-70b) — already stubbed | ✅ Ready | Activate existing BedrockProvider |
| **Embeddings** | sentence-transformers (local) | Slow, CPU-bound | Bedrock Titan Embeddings v2 |
| **Vector DB** | Chroma (local persistent) | Not scalable, no auth | Amazon OpenSearch Serverless |
| **Report Storage** | SQLite (file-based) | Not cloud-native | Amazon S3 |
| **Scheduling** | APScheduler (in-process) | Dies if process restarts | AWS EventBridge + Lambda |
| **UI Hosting** | localhost:8501 | Not accessible | AWS App Runner |
| **Logs** | structlog → JSON files | Local files only | Amazon CloudWatch |
| **Auth** | None | Out of scope | Skip for MVP (or add Cognito later) |

---

## Detailed Implementation Plan

### Phase 1: Activate Bedrock (1–2 hours)
**Goal:** Replace local embeddings with Bedrock Titan, validate LLM still works.

#### Current State
- `src/reportagent/llm/bedrock.py` already exists with BedrockProvider
- `src/reportagent/llm/embedder.py` already uses Bedrock Titan v2
- Both are conditionally loaded based on `LLM_PROVIDER=bedrock` environment variable

#### Implementation
1. **Update config to always use Bedrock in AWS deployments:**
   - In `src/reportagent/config.py`, detect if running on Lambda/App Runner (check for `LAMBDA_TASK_ROOT` or `AWS_EXECUTION_ENV`)
   - If true, default `LLM_PROVIDER=bedrock` and `EMBEDDER_PROVIDER=bedrock`
   - Fall back to Anthropic/sentence-transformers locally

2. **Test end-to-end locally:**
   ```bash
   export LLM_PROVIDER=bedrock
   export EMBEDDER_PROVIDER=bedrock
   export AWS_REGION=us-east-1
   make ingest  # Verify one full ingestion cycle works
   ```

3. **Add IAM policy:**
   Create IAM role with permissions:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel",
           "bedrock:InvokeModelWithResponseStream"
         ],
         "Resource": "arn:aws:bedrock:us-east-1::foundation-model/meta.llama3-70b-instruct-v1:0"
       },
       {
         "Effect": "Allow",
         "Action": [
           "bedrock:InvokeModel"
         ],
         "Resource": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0"
       }
     ]
   }
   ```

**Why first?** Bedrock is the core differentiator mentioned in the JD. Getting this working validates the LLM/embedding layer.

---

### Phase 2: S3 Archive Backend (1 hour)
**Goal:** Store reports in S3 instead of SQLite, keep SQLite for caching.

#### Implementation
1. **Create S3 backend for Archive class:**
   - Add `S3ArchiveBackend` class alongside `Archive`
   - Reports stored at: `s3://genai-report-agent/reports/{topic}/{report_id}.json`
   - Run logs stored at: `s3://genai-report-agent/run_logs/{run_id}.json`

2. **Code structure (new file: `src/reportagent/storage/s3_archive.py`):**
   ```python
   import json
   import boto3
   from reportagent.schemas import Report

   class S3Archive:
       def __init__(self, bucket_name: str = "genai-report-agent"):
           self.s3 = boto3.client("s3")
           self.bucket = bucket_name

       def save_report(self, report: Report) -> None:
           key = f"reports/{report.topic}/{report.id}.json"
           self.s3.put_object(
               Bucket=self.bucket,
               Key=key,
               Body=report.model_dump_json(),
               ContentType="application/json",
           )
           log.info("report_saved_to_s3", key=key)

       def get_latest_report(self, topic: str) -> Report | None:
           # List all reports for topic, sort by timestamp, fetch latest
           # (Alternatively: use S3 metadata to track write-time)
           ...

       def get_reports_since(self, topic: str, since: datetime) -> list[Report]:
           # List all, filter by timestamp
           ...
   ```

3. **Update `persister_node` in `graphs/ingestion.py`:**
   ```python
   from reportagent.storage.s3_archive import S3Archive
   s3_archive = S3Archive()
   s3_archive.save_report(state.draft_report)
   ```

4. **Keep SQLite as local cache for UI:**
   - Streamlit still reads from SQLite for immediate display
   - Background job syncs SQLite from S3 (or UI reads from S3 on load)

5. **IAM policy:**
   ```json
   {
     "Effect": "Allow",
     "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
     "Resource": [
       "arn:aws:s3:::genai-report-agent",
       "arn:aws:s3:::genai-report-agent/*"
     ]
   }
   ```

**Outcome:** Reports persist durably, accessible from anywhere, no local file dependency.

---

### Phase 3: OpenSearch Serverless (1 hour)
**Goal:** Replace Chroma with OpenSearch for production vector retrieval.

#### Implementation
1. **Provision OpenSearch Serverless collection:**
   - Collection name: `uk-economy-articles`
   - Dimension: 1024 (Titan embeddings output dimension)
   - Vector search enabled

2. **Create OpenSearch backend for VectorStore:**
   - New file: `src/reportagent/storage/opensearch_vector.py`
   - Implement same interface as Chroma backend (upsert_chunks, similarity_search, article_exists)

3. **Code outline:**
   ```python
   from opensearchpy import OpenSearch, RequestsHttpConnection
   from requests_aws4auth import AWS4Auth

   class OpenSearchVector:
       def __init__(self, collection_name: str = "uk-economy-articles"):
           # Auth with AWS credentials
           auth = AWS4Auth(
               boto3.Session().get_credentials(),
               "us-east-1",
               "aoss",
               "aws4"
           )
           self.client = OpenSearch(
               hosts=[f"{collection_arn}.us-east-1.aoss.amazonaws.com:443"],
               auth=auth,
               connection_class=RequestsHttpConnection,
               use_ssl=True,
               verify_certs=True,
           )

       def upsert_chunks(self, chunks: list[Chunk]) -> None:
           for chunk in chunks:
               self.client.index(
                   index=self.collection_name,
                   body={
                       "id": chunk.id,
                       "text": chunk.text,
                       "embedding": chunk.embedding,
                       "metadata": chunk.metadata,
                   },
               )

       def similarity_search(self, query_embedding: list[float], n_results: int = 10) -> list[Chunk]:
           results = self.client.search(
               index=self.collection_name,
               body={
                   "size": n_results,
                   "query": {
                       "knn": {"embedding": {"vector": query_embedding, "k": n_results}}
                   },
               },
           )
           return [Chunk(**hit["_source"]) for hit in results["hits"]["hits"]]
   ```

4. **Toggle between Chroma and OpenSearch:**
   - In `config.py`, add `VECTOR_STORE_PROVIDER` setting
   - Default: `opensearch` on AWS, `chroma` locally
   - `VectorStore.__init__()` returns the right backend

**Outcome:** Serverless vector DB, auto-scales, no ops overhead.

---

### Phase 4: EventBridge + Lambda Scheduling (1 hour)
**Goal:** Replace APScheduler with EventBridge cron triggers.

#### Implementation
1. **Create Lambda handler:**
   - New file: `src/reportagent/lambda_handler.py`
   ```python
   def lambda_handler(event, context):
       """Entrypoint for EventBridge trigger."""
       from reportagent.scheduler import run_ingestion
       run_ingestion()
       return {"statusCode": 200, "body": "Ingestion completed"}
   ```

2. **Package Lambda:**
   - Dockerfile or SAM template (AWS Serverless Application Model)
   - Compress `src/` + `pyproject.toml` dependencies into ZIP
   - Upload to AWS Lambda

3. **EventBridge rule:**
   - Schedule: `cron(0 * * * ? *)` (every hour at minute 0)
   - Target: Lambda function
   - IAM role: Bedrock + S3 + OpenSearch permissions

4. **Remove APScheduler:**
   - `scheduler.py` becomes optional (keep for local dev)
   - Production runs via EventBridge only

**Why?** Removes in-process scheduling, makes ingestion horizontally scalable (could trigger multiple Lambda in parallel for different topics).

---

### Phase 5: App Runner Deployment (30 mins)
**Goal:** Deploy Streamlit UI to AWS App Runner with public URL.

#### Current State
- `Dockerfile` already configured for App Runner (port 8080, headless Streamlit)

#### Implementation
1. **Push Dockerfile to ECR (Elastic Container Registry):**
   ```bash
   aws ecr create-repository --repository-name genai-report-agent --region us-east-1
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   docker build -t genai-report-agent .
   docker tag genai-report-agent:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/genai-report-agent:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/genai-report-agent:latest
   ```

2. **Create App Runner service:**
   - IAM role: Bedrock + S3 + OpenSearch + CloudWatch permissions
   - Environment variables: AWS_REGION, LLM_PROVIDER=bedrock, etc.
   - Memory: 2 GB, vCPU: 1
   - Scaling: min=1, max=2 (auto-scale on CPU > 70%)

3. **Enable public access:**
   - App Runner auto-generates a public HTTPS URL
   - Share that URL with stakeholders

**Outcome:** Anyone with the URL can access the full system — no local setup needed.

---

### Phase 6: CloudWatch Logging (20 mins)
**Goal:** Route structlog JSON output to CloudWatch Logs.

#### Implementation
1. **Modify logging config in `src/reportagent/observability/logging.py`:**
   - Detect if running on Lambda/App Runner
   - If true, add CloudWatch handler to structlog
   - All JSON logs go to CloudWatch Logs group: `/aws/genai-report-agent/{env}`

2. **Code snippet:**
   ```python
   import structlog
   from watchtower import CloudWatchLogHandler

   def setup_logging():
       if os.getenv("AWS_EXECUTION_ENV"):
           # Running on Lambda or App Runner
           handler = CloudWatchLogHandler(
               log_group="/aws/genai-report-agent/prod",
               log_stream=f"instance-{uuid4()}",
           )
           structlog.configure(
               processors=[...],
               logger_factory=structlog.PrintLoggerFactory(),
               cache_logger_on_first_use=True,
               wrapper_class=structlog.make_filtering_bound_logger(20),
               processors=[
                   structlog.processors.JSONRenderer(),
                   handler,
               ],
           )
   ```

3. **No code change needed for file logging locally** — it still works.

**Outcome:** All ingestion logs visible in CloudWatch, queryable, traceable.

---

## Optional: Phase 7 (Stretch)

### SageMaker Notebook for Fine-Tuning
If extending beyond MVP: use SageMaker to fine-tune a 7B Llama model on 3 months of production chat data. Out of scope for now.

### Cognito Authentication
Add user authentication if deploying to public. Out of scope for MVP.

---

## Deployment Sequence

**Week 1: Core Stack**
1. Bedrock activation (validate locally)
2. S3 archive (modify persister_node)
3. OpenSearch provisioning (modify vector store)

**Week 2: Serverless + Hosting**
4. EventBridge + Lambda (replace scheduler)
5. App Runner (push Dockerfile, get public URL)

**Week 3: Observability**
6. CloudWatch logging (optional but recommended)

---

## Testing Checklist

- [ ] Local: `LLM_PROVIDER=bedrock make ingest` completes successfully
- [ ] S3: Reports appear in S3 bucket after ingestion
- [ ] OpenSearch: Chunks retrieved from OpenSearch in chat pipeline
- [ ] Lambda: EventBridge triggers Lambda, ingestion runs hourly
- [ ] App Runner: Streamlit UI accessible at public URL
- [ ] Chat pipeline: Query the chat interface, verify responses are sourced
- [ ] CloudWatch: Logs appear in CloudWatch Logs for all stages

---

## Cost Estimate (Monthly)

| Service | Estimate | Notes |
|---|---|---|
| **Bedrock** | $20–40 | ~100 ingestions/month + chat queries; pricing per 1K tokens |
| **OpenSearch Serverless** | $5–10 | 1M vector queries/month, tiny corpus |
| **S3** | <$1 | ~100 reports/month, tiny payload |
| **Lambda** | <$1 | 100 hours free tier/month, well within limits |
| **App Runner** | $20–30 | Always-on, 1 vCPU + 2 GB memory |
| **CloudWatch** | <$5 | Logs ingestion + storage, small volume |
| **EventBridge** | <$1 | 100 rules/month, free tier |
| **Total** | ~$50–90 | Production-grade AWS stack |

---

## Migration Checklist

### Before Deploying to AWS
- [ ] All tests pass locally (`make test`)
- [ ] One full ingestion cycle works with `LLM_PROVIDER=bedrock`
- [ ] Dockerfile builds and runs locally
- [ ] RAGAS evaluation passes (if running manually)
- [ ] AWS credentials configured in `~/.aws/credentials`

### AWS Setup
- [ ] VPC and security groups configured (OpenSearch)
- [ ] IAM role created with all necessary permissions
- [ ] S3 bucket created and versioning enabled
- [ ] OpenSearch Serverless collection created
- [ ] Lambda function packaged and uploaded
- [ ] EventBridge rule created and tested
- [ ] App Runner service deployed
- [ ] CloudWatch Logs group created

### Post-Deployment
- [ ] Visit App Runner URL, verify UI loads
- [ ] Trigger manual chat query, verify sources
- [ ] Check CloudWatch Logs for ingestion
- [ ] Verify next scheduled ingestion runs (check S3 for new reports)
- [ ] Load test with concurrent chat queries

---

## Files to Create/Modify

| File | Change | Impact |
|---|---|---|
| `src/reportagent/config.py` | Add cloud provider detection | Sets defaults for Bedrock/OpenSearch |
| `src/reportagent/storage/s3_archive.py` | **NEW** | S3 backend for reports |
| `src/reportagent/storage/opensearch_vector.py` | **NEW** | OpenSearch backend for vectors |
| `src/reportagent/lambda_handler.py` | **NEW** | Lambda entrypoint for EventBridge |
| `src/reportagent/graphs/ingestion.py` | Modify persister_node | Use S3Archive instead of SQLite |
| `src/reportagent/graphs/chat.py` | Modify for OpenSearch | Read vectors from OpenSearch |
| `src/reportagent/observability/logging.py` | Add CloudWatch handler | Route logs to CloudWatch |
| `Dockerfile` | ✅ No change | Already App Runner–ready |
| `pyproject.toml` | Add boto3, opensearch-py | AWS SDK dependencies |
| `.github/workflows/ci.yml` | **DELETE** | Remove CI emails |
| `.env.example` | Add AWS region, bucket names | Configuration template |

---

## Key Design Decisions

### Why OpenSearch over DynamoDB?
- **DynamoDB:** Great for key-value access (get latest report by topic) but not suitable for k-NN vector search without custom code
- **OpenSearch Serverless:** Built for semantic search, native k-NN, scales with query volume

### Why S3 over DynamoDB for reports?
- **S3:** Stores full JSON blobs, cheap for large payloads, easy to version/archive
- **DynamoDB:** Limited item size (400 KB), overkill for read-mostly access pattern

### Why Lambda not EC2?
- **EC2:** Always-on cost, manual scaling, ops overhead
- **Lambda:** Triggered only on schedule, auto-scales, ~$1/month for this workload

### Why keep SQLite locally?
- **SQLite:** Fast local cache for Streamlit (no network latency)
- **Background sync:** Streamlit reads latest from SQLite; on page load, sync from S3 if stale

---

## Next Steps

1. **Local validation:** Test full pipeline with `LLM_PROVIDER=bedrock` before touching AWS
2. **Incremental rollout:** Deploy Bedrock first, then S3, then OpenSearch
3. **Team review:** Share this plan with stakeholders before AWS spend
4. **Documentation:** Add AWS setup guide to README once deployed