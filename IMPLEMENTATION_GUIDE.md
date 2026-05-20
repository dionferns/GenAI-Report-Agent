# Complete Implementation & Testing Guide

## Overview

This is a production-grade GenAI News Intelligence System. Follow these steps to get it fully working.

---

## Phase 1: Environment Setup (5 minutes)

### Step 1.1: Create Virtual Environment

```bash
cd /Users/dionfernandes/Projects/GenAI-Report-Agent
~/.pyenv/versions/3.11.9/bin/python3 -m venv .venv
```

### Step 1.2: Activate Virtual Environment

```bash
source .venv/bin/activate
```

*You should see `(.venv)` at the start of your terminal prompt*

### Step 1.3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will take 2-3 minutes. You'll see lots of output as packages are downloaded and installed.

### Step 1.4: Configure API Key

```bash
cp .env.example .env
nano .env
```

Find this line and add your Anthropic API key:
```
ANTHROPIC_API_KEY=sk-ant-v1-xxxxxxxxxxxxx
```

Save the file (Ctrl+X, then Y, then Enter in nano)

---

## Phase 2: Quick Verification (2 minutes)

Once everything is installed, verify it works:

```bash
source .venv/bin/activate
python test_simple.py
```

You should see:
```
[Test 1] Testing imports... ✅ All imports successful
[Test 2] Testing configuration... ✅ Config loaded: anthropic
[Test 3] Testing LLM connectivity... ✅ Claude responded: 'Hello'
[Test 4] Testing database... ✅ Database initialized
[Test 5] Testing vector store... ✅ Vector store working

Results: 5/5 tests passed
🎉 All tests passed!
```

If any test fails, see Troubleshooting section below.

---

## Phase 3: Seed Sample Data (1 minute)

```bash
source .venv/bin/activate
python scripts/seed_corpus.py
```

Expected output:
```
Seeding vector store with sample articles...
✓ Seeded article: UK announces new AI safety standards (3 chunks)
✓ Seeded article: BBC reports on AI regulation progress (3 chunks)

✅ Seeding complete! 2 articles added.
```

This populates the vector store with sample articles so retrieval works.

---

## Phase 4: Test Ingestion Pipeline (3 minutes)

```bash
source .venv/bin/activate
python scripts/trigger_once.py
```

This will:
1. Fetch articles from BBC News and gov.uk
2. Extract clean text
3. Remove duplicates
4. Create embeddings
5. Generate a structured report
6. Fact-check the report
7. Save to database

Expected output:
```
Triggering ingestion run: <uuid>
... [processing logs] ...
✅ Ingestion successful!
Report ID: <uuid>
Summary preview: The UK government has announced...
```

**What this demonstrates:**
- ✅ Web fetching works
- ✅ HTML cleaning works
- ✅ Deduplication works
- ✅ Embeddings work
- ✅ LLM report generation works
- ✅ Critic fact-checking works
- ✅ Database persistence works

---

## Phase 5: Test Chat System (2 minutes)

### Option A: Test Chat Graph Directly

```bash
source .venv/bin/activate
python -c "
from reportagent.schemas import ChatState
from reportagent.graphs.chat import chat_graph

state = ChatState(
    session_id='test',
    current_query='What is UK AI regulation?'
)

result = chat_graph.invoke(state.model_dump())
if result.get('response'):
    print('Question:', state.current_query)
    print('Answer:', result['response']['content'][:200], '...')
    print('Citations:', len(result['response'].get('citations', [])))
"
```

Expected output:
```
Question: What is UK AI regulation?
Answer: UK AI regulation focuses on establishing a principles-based framework...
Citations: 3
```

### Option B: Interactive Streamlit UI (Recommended)

```bash
source .venv/bin/activate
streamlit run src/reportagent/ui/app.py
```

This opens a web interface at `http://localhost:8501` where you can:
- See the latest report in the sidebar
- Ask questions in natural language
- Get answers with citations
- Manually trigger ingestion runs

---

## Phase 6: Run Tests (2 minutes)

```bash
source .venv/bin/activate
pytest tests/ -v
```

Expected output:
```
tests/test_schemas.py::test_article_id_generation PASSED
tests/test_schemas.py::test_chunk_id_generation PASSED
tests/test_schemas.py::test_report_summary_validation PASSED
...
====== 12 passed in 1.23s ======
```

---

## Phase 7: Run Full Test Suite (3 minutes)

```bash
source .venv/bin/activate
python run_full_test.py
```

This runs 8 comprehensive tests:
1. Imports
2. Configuration
3. LLM Connectivity
4. Database
5. Vector Store
6. Guardrails
7. Corpus Seeding
8. Chat Graph

---

## Phase 8: Evaluate System (Optional, 5 minutes)

```bash
source .venv/bin/activate
python evals/run_summary_eval.py
```

This validates the report structure against the schema.

---

## Complete Workflow Summary

Here's the entire workflow in one place:

```bash
# 1. Initial setup (one time)
~/.pyenv/versions/3.11.9/bin/python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # Add ANTHROPIC_API_KEY

# 2. Verify installation
python test_simple.py

# 3. Seed data
python scripts/seed_corpus.py

# 4. Test ingestion
python scripts/trigger_once.py

# 5. Test chat
streamlit run src/reportagent/ui/app.py
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'reportagent'"

**Solution:**
```bash
source .venv/bin/activate
```

Make sure the virtual environment is activated (you should see `(.venv)` in your prompt).

### "ANTHROPIC_API_KEY not set"

**Solution:**
```bash
nano .env
```

Add your API key:
```
ANTHROPIC_API_KEY=sk-ant-v1-xxxxxxxxxxxxx
```

Get a key from: https://console.anthropic.com/account/keys

### "pip install fails with network error"

**Solution:**
```bash
pip install --upgrade pip
pip install -r requirements.txt --retries 5
```

### "Chroma connection error"

**Solution:**
```bash
rm -rf data/chroma/
python scripts/seed_corpus.py
```

This resets the Chroma database and reseeds it.

### "LLM call times out or fails"

**Solution:**
1. Check your internet connection
2. Check your API key is valid
3. Check your rate limits: https://console.anthropic.com/account/usage
4. Wait a minute and try again

### "Tests fail with 'No report found'"

**Solution:**
Make sure you've run the seeding step:
```bash
python scripts/seed_corpus.py
```

---

## What Each Component Does

### Ingestion Pipeline (Runs hourly)
1. **Planner** - Decides which RSS feeds to check
2. **Fetcher** - Downloads articles from URLs
3. **Cleaner** - Extracts clean text from HTML
4. **Deduper** - Removes duplicate articles
5. **Chunker/Embedder** - Splits text into chunks and creates embeddings
6. **Reporter** - Uses Claude to generate structured report
7. **Critic** - Fact-checks the report against sources
8. **Persister** - Saves to Chroma (vectors) + SQLite (reports)

### Chat System (Runs on user input)
1. **Guardrail** - Detects injection attacks and scrubs PII
2. **Query Router** - Classifies question type
3. **Retriever** - Uses hybrid search (BM25 + vector)
4. **Responder** - Generates answer with citations
5. **Faithfulness Check** - Verifies answer accuracy (optional)

### Storage
- **Chroma** - Vector database for semantic search
- **SQLite** - Relational database for reports, logs, evaluations

---

## Architecture

```
News Sources (BBC, gov.uk)
        ↓
    Ingestion Pipeline
        ↓
    Chroma (vectors) + SQLite (reports)
        ↓
    Chat System ← User Queries
        ↓
    Streamlit UI
```

---

## Key Features Implemented

✅ **Hallucination Mitigation** - Critic node fact-checks reports  
✅ **Deduplication** - Vector store stays clean over time  
✅ **Hybrid Search** - BM25 + vector retrieval  
✅ **Citations** - Every response includes source links  
✅ **Security** - Injection detection + PII scrubbing  
✅ **Observability** - Structured logs + LangSmith traces  
✅ **Evaluation** - RAGAS metrics + structure validation  
✅ **Production Ready** - Async support, error handling, retries  

---

## Environment Variables Reference

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| ANTHROPIC_API_KEY | Yes | - | Claude API key |
| LLM_PROVIDER | No | anthropic | "bedrock" or "anthropic" |
| CHROMA_PERSIST_DIR | No | ./data/chroma | Vector store location |
| SQLITE_DB_PATH | No | ./data/archive.db | Database location |
| LOG_FILE | No | ./logs/agent.log | Log file path |
| DEFAULT_TOPIC | No | uk_ai_regulation | Topic to monitor |
| INGEST_INTERVAL_MINUTES | No | 60 | How often to ingest |
| MAX_URLS_PER_RUN | No | 15 | Max URLs per run |
| MAX_CRITIC_ITERATIONS | No | 2 | Max report revisions |
| LANGCHAIN_API_KEY | No | - | LangSmith API key (optional) |

---

## Next Steps After Everything Works

1. **Customize sources** in `src/reportagent/config.py` SOURCE_MAP
2. **Adjust report format** in `src/reportagent/graphs/ingestion.py` reporter_node
3. **Fine-tune retrieval** in `src/reportagent/tools/retriever.py` weights
4. **Add more evaluation questions** to `evals/golden_set.jsonl`
5. **Deploy to production** - See AWS deployment notes in README.md

---

## Support

- **README.md** - Full specification and architecture
- **IMPLEMENTATION_STATUS.md** - What's been built
- **SETUP_AND_TESTING.md** - Detailed testing guide
- **docs/architecture.md** - Technical architecture details

Good luck! 🚀
