# Data Sources & AWS Configuration Guide

## Part 1: Data Sources (Currently Working)

### Live RSS Feeds (Automatic)

Your system is **already configured to fetch real data** from:

1. **BBC News Technology Feed**
   ```
   https://feeds.bbci.co.uk/news/technology/rss.xml
   ```
   - Real BBC technology articles
   - Updates hourly

2. **Gov.uk AI Regulation Search**
   ```
   https://www.gov.uk/search/news-and-communications.atom?keywords=artificial+intelligence
   https://www.gov.uk/search/news-and-communications.atom?keywords=ai+regulation
   ```
   - Official UK government AI policy news
   - Official regulations and announcements

### How It Works

When you run ingestion:
```bash
python scripts/trigger_once.py
```

The system will:
1. ✅ **Fetch** articles from BBC + gov.uk (real data)
2. ✅ **Extract** clean text using trafilatura
3. ✅ **Deduplicate** to avoid repeats
4. ✅ **Embed** into vector store
5. ✅ **Generate** report from real content
6. ✅ **Fact-check** against sources

---

## Part 2: Customize Data Sources

Want to monitor different topics? Edit `src/reportagent/config.py`:

### Example 1: Add a New Topic

```python
SOURCE_MAP = {
    "uk_ai_regulation": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://www.gov.uk/search/news-and-communications.atom?keywords=artificial+intelligence",
        "https://www.gov.uk/search/news-and-communications.atom?keywords=ai+regulation",
    ],
    # Add this:
    "climate_policy": [
        "https://feeds.bbc.co.uk/news/science_and_environment/rss.xml",
        "https://www.gov.uk/search/news-and-communications.atom?keywords=climate",
    ],
    # And this:
    "tech_trends": [
        "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "https://www.techcrunch.com/feed/",
    ],
}
```

### Example 2: Use Different Sources

Replace with your own RSS feeds:
```python
SOURCE_MAP = {
    "financial_news": [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.ft.com/home/rss",
    ],
    "healthcare": [
        "https://www.nih.gov/news-events/news-releases/rss.xml",
        "https://feeds.bbci.co.uk/news/health/rss.xml",
    ],
}
```

### Running for Different Topics

```bash
# Edit .env to change default
nano .env
# Change: DEFAULT_TOPIC=uk_ai_regulation
# To: DEFAULT_TOPIC=climate_policy
```

Or modify the ingestion call in `scripts/trigger_once.py`:
```python
state = IngestionState(
    run_id=run_id,
    topic="climate_policy",  # Change here
)
```

---

## Part 3: AWS Configuration (Optional - For Production)

### Current Setup (Local - No AWS Needed)

```
┌─────────────────────┐
│   Local Machine     │
├─────────────────────┤
│ .venv/              │
│ data/chroma/        │ ← Vector store
│ data/archive.db     │ ← Reports database
│ logs/               │
└─────────────────────┘
```

**This works perfectly for development!**

### Production Setup (With AWS)

To deploy to AWS, you have two paths:

#### **Path A: Simple (Use Bedrock for LLM only)**

```bash
# 1. Set in .env
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=eu-west-2

# 2. Everything else stays local
# - Chroma (local) for vector store
# - SQLite (local) for reports
# - APScheduler (local) for scheduling
```

**Code already supports this!** Just set `LLM_PROVIDER=bedrock` in .env

See: `src/reportagent/llm/bedrock.py` ✅

#### **Path B: Full AWS (Recommended for Scale)**

Replace each component:

| Component | Local → AWS |
|-----------|-----------|
| LLM | Anthropic API → **AWS Bedrock** |
| Vector Store | Chroma → **OpenSearch Serverless** |
| Reports DB | SQLite → **DynamoDB** or **RDS PostgreSQL** |
| Scheduling | APScheduler → **EventBridge + Lambda** |
| Logging | Local file → **CloudWatch Logs** |
| Storage | Local disk → **S3** |

---

## Part 4: Step-by-Step AWS Setup

### Step 1: Enable AWS Bedrock

```bash
# 1. Install AWS CLI
pip install awscli-v2

# 2. Configure credentials
aws configure
# Enter:
# AWS Access Key ID: xxx
# AWS Secret Access Key: xxx
# Default region: eu-west-2
# Default output format: json

# 3. Request access to Claude model
# Go to: https://console.aws.amazon.com/bedrock
# Click: Model Access
# Request access to: anthropic.claude-sonnet-4-5

# 4. Wait ~5 minutes for approval

# 5. Update .env
nano .env
```

Add these lines:
```env
LLM_PROVIDER=bedrock
AWS_ACCESS_KEY_ID=YOUR_KEY
AWS_SECRET_ACCESS_KEY=YOUR_SECRET
AWS_DEFAULT_REGION=eu-west-2
```

### Step 2: Test Bedrock Connection

```bash
source .venv/bin/activate
python -c "
from reportagent.llm import get_llm_provider
provider = get_llm_provider()
response = provider.invoke(
    [{'role': 'user', 'content': 'Say OK'}],
    max_tokens=10
)
print('Bedrock response:', response)
"
```

### Step 3: (Optional) Migrate Vector Store to AWS

**For production scale, migrate Chroma to OpenSearch:**

```python
# This would go in storage/vector.py
import boto3

# Replace Chroma with OpenSearch Serverless
opensearch_client = boto3.client(
    'opensearchserverless',
    region_name='eu-west-2'
)

# Use OpenSearch Serverless instead of Chroma
# (Requires different implementation - see docs)
```

See: `docs/architecture.md` Section 18 for full migration guide.

---

## Part 5: Testing Your Setup

### Test 1: Verify Data Sources Work

```bash
source .venv/bin/activate
python -c "
import feedparser

sources = [
    'https://feeds.bbci.co.uk/news/technology/rss.xml',
    'https://www.gov.uk/search/news-and-communications.atom?keywords=artificial+intelligence',
]

for url in sources:
    feed = feedparser.parse(url)
    print(f'{url}: {len(feed.entries)} articles')
"
```

### Test 2: Ingest Real Data

```bash
source .venv/bin/activate
python scripts/trigger_once.py
```

This will:
- Fetch real BBC + gov.uk articles
- Generate a real report
- Show you actual data flowing through the system

### Test 3: Check Ingested Data

```bash
source .venv/bin/activate
python -c "
from reportagent.storage.archive import Archive

archive = Archive()
report = archive.get_latest_report('uk_ai_regulation')
if report:
    print('Latest Report:')
    print(f'Generated: {report.generated_at}')
    print(f'Summary: {report.summary[:200]}...')
    print(f'Sources: {len(report.source_urls)}')
else:
    print('No report yet - run: python scripts/trigger_once.py')
"
```

---

## Part 6: Recommended Setup

### For Learning/Development
```
✅ Use: Local Anthropic API
✅ Vector Store: Local Chroma
✅ Database: Local SQLite
✅ Scheduling: Local APScheduler
```

**This is what you have now - perfect for testing!**

### For Small Production (< 100 articles/day)
```
✅ Use: AWS Bedrock for LLM
✅ Vector Store: Local Chroma (or small OpenSearch)
✅ Database: RDS PostgreSQL (managed)
✅ Scheduling: Lambda + EventBridge
```

### For Enterprise (1000+ articles/day)
```
✅ Use: AWS Bedrock for LLM
✅ Vector Store: OpenSearch Serverless
✅ Database: DynamoDB (auto-scale)
✅ Scheduling: EventBridge
✅ Logging: CloudWatch
✅ Storage: S3
```

---

## Quick Reference

### Data Sources

Add to `src/reportagent/config.py`:
```python
SOURCE_MAP = {
    "your_topic": [
        "https://your-rss-feed-1.com/feed.xml",
        "https://your-rss-feed-2.com/feed.xml",
    ],
}
```

### AWS Bedrock Setup

1. Set in `.env`:
   ```
   LLM_PROVIDER=bedrock
   AWS_ACCESS_KEY_ID=xxx
   AWS_SECRET_ACCESS_KEY=xxx
   AWS_DEFAULT_REGION=eu-west-2
   ```

2. Request Bedrock access in AWS console

3. Test: `python test_simple.py`

### Run Ingestion

```bash
python scripts/trigger_once.py
```

This fetches real data from your configured sources.

---

## Next Steps

1. **Local Testing** (Recommended first)
   - Run: `python scripts/trigger_once.py`
   - Verify real BBC + gov.uk data is ingested
   - Test chat with real data

2. **Add Custom Sources** (Optional)
   - Edit `config.py` SOURCE_MAP
   - Add your own RSS feeds
   - Re-run ingestion

3. **AWS Bedrock** (For production)
   - Set `LLM_PROVIDER=bedrock` in .env
   - Add AWS credentials
   - Request Bedrock model access
   - Test: `python test_simple.py`

4. **Scale to AWS** (Enterprise)
   - Follow Section 18 in README.md
   - Migrate Chroma → OpenSearch
   - Migrate SQLite → DynamoDB
   - Deploy to Lambda + EventBridge

---

## Resources

- **README.md** - Full specification
- **docs/architecture.md** - AWS migration details
- **src/reportagent/config.py** - Configuration options
- **src/reportagent/llm/bedrock.py** - Bedrock implementation (already done!)
- **scripts/trigger_once.py** - Ingestion script

You're all set! Start with local testing, then add AWS as needed. 🚀
