# Architecture Documentation

## System Overview

This document provides extended architecture details for the GenAI Report Agent.

### Two-Graph Pattern

The system uses two independent LangGraph StateGraphs:

1. **Ingestion Graph** - Processes raw articles → Generates structured reports
2. **Chat Graph** - Processes user queries → Generates answers with citations

This separation provides clear separation of concerns and different optimization requirements.

### Ingestion Pipeline

```
Input (URLs) 
  → Planner (select sources)
  → Fetcher (download HTML)
  → Cleaner (extract text)
  → Deduper (remove duplicates)
  → Chunker/Embedder (vectorize)
  → Reporter (generate summary)
  → Critic (fact-check)
  → Persister (save to DB)
```

The **Critic** node is critical for preventing hallucinations. It verifies every claim in the generated report against the source chunks, with up to 2 retry cycles.

### Chat Pipeline

```
Input (user question)
  → Guardrail (injection detection + PII scrubbing)
  → QueryRouter (classify question type)
  → Retriever (hybrid BM25 + vector search)
  → Responder (generate answer with citations)
  → FaithfulnessCheck (optional secondary check)
```

### Storage Architecture

**Chroma (Vector Store)**
- Single collection per topic
- Stores embeddings + chunk text + metadata
- Used for semantic search

**SQLite (Archive)**
- Three tables: reports, run_logs, eval_results
- Persistent historical data
- Used for latest report retrieval

### Hybrid Retrieval Strategy

The retriever combines two approaches:

1. **Vector Search** (Semantic) - 60% weight
   - Captures conceptual relevance
   - Handles synonym variation
   
2. **BM25 Search** (Lexical) - 40% weight
   - Catches exact entity matches
   - Effective for legislation names, acronyms

This hybrid approach handles both "what does the regulation say?" (BM25) and "how does the government approach this?" (vector) queries.

### LLM Provider Abstraction

```python
LLMProvider Protocol
├── Bedrock Implementation (AWS production)
├── Anthropic Direct Implementation (local dev)
```

Configuration via `LLM_PROVIDER` env var enables seamless switching.

### Observability

**Structured Logging (structlog)**
- JSON format for machine parsing
- Context binding per run (run_id, graph type, node name)
- File + stdout output

**Tracing (LangSmith)**
- Per-node execution time
- Token usage tracking
- Input/output recording

## Deployment Considerations

### Local Development
- APScheduler (in-process)
- Chroma (local file persistence)
- SQLite (local file)
- CPU-based embeddings (all-MiniLM-L6-v2)

### AWS Production
| Component | Local | AWS Equivalent |
|-----------|-------|-----------------|
| Scheduler | APScheduler | EventBridge → Lambda |
| Vector Store | Chroma | OpenSearch Serverless |
| Archive | SQLite | DynamoDB / RDS |
| Embeddings | Sentence Transformers | Bedrock Titan Embeddings |
| LLM | Bedrock / Anthropic API | Bedrock |
| Logs | structlog → file | CloudWatch Logs |

The abstraction layers (`LLMProvider`, `VectorStore`, `Archive`) make this migration straightforward.

## Design Decisions

### 1. Principles-Based Approach
Rather than trying to prevent all hallucinations upfront, we:
- Generate draft reports
- Verify every claim with the Critic
- Retry if grounding fails

This is more practical than trying to engineer perfect prompts.

### 2. Separate Ingestion & Chat
Different requirements:
- Ingestion: deterministic, idempotent, long-running, high latency tolerance
- Chat: interactive, varied, low latency required

Separate graphs allow independent optimization.

### 3. Hybrid Retrieval
Pure vector search sometimes misses named entities (legislation, acronyms). BM25 retrieval is cheap and fills this gap.

### 4. Persistent Vector Store
Hourly deduplication prevents corpus degradation. As the vector store grows, the system becomes more knowledgeable.

### 5. Citations from Retrieval
Every citation points to a specific chunk with metadata (URL, fetch time). This provides explainability and auditability.
