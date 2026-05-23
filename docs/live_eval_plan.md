# Live Evaluation & Experiment Tracking Plan

## Overview

The current evaluation setup has two components:
- **Critic node** (ingestion graph) — binary grounding check, blocks bad reports inline
- **RAGAS** (offline) — batch evaluation against 25 golden Q&A pairs, run manually

This plan adds three new layers without replacing anything that exists:

| Layer | Tool | Purpose |
|---|---|---|
| Live quality scoring | DeepEval | Score every report and chat response as it's produced |
| Experiment tracking | W&B | Track scores over time, compare runs, visualise trends |
| Local persistence | SQLite (existing) | Store scores for UI display and offline analysis |

---

## How the Three Tools Relate

It is important to understand that these tools are **complementary, not overlapping**:

- **DeepEval** computes the scores — it is the measurement instrument
- **W&B** stores and visualises those scores across runs — it is the tracking layer
- **SQLite** persists scores locally for the Streamlit UI — it is the display layer
- **LangSmith** (already wired) captures per-node traces — it is the debugging layer
- **RAGAS** (already wired) runs offline batch eval — it is the benchmarking layer

DeepEval tells you "this report scored 0.84 faithfulness."
W&B tells you "faithfulness has been trending up since you added the relevance filter."
LangSmith tells you "the reporter node took 3.2s and used 847 tokens on run X."
RAGAS tells you "across 25 golden questions, your system scores 0.79 faithfulness."

None of these do the same thing. All four should coexist.

---

## What We're Adding

1. `DeepEvalBaseLLM` wrapper — plugs our LLM provider into DeepEval as judge
2. `quality_eval_node` in ingestion graph — scores report before persisting
3. `response_eval_node` in chat graph — replaces `faithfulness_check_node`, always async
4. Schema changes — score fields on `Report` and `ChatMessage`, new `ChatEvalResult`
5. Archive changes — `chat_eval_results` table in SQLite
6. UI changes — quality summary in sidebar

> W&B experiment tracking is a separate concern — see [experiment_tracking_plan.md](experiment_tracking_plan.md)

---

## Step 1 — Dependencies

Add to `pyproject.toml`:

```toml
deepeval>=1.0
```

---

## Step 2 — Custom LLM Judge Wrapper (CRITICAL — implement first)

DeepEval defaults to OpenAI as judge and will fail at runtime with a key error if OpenAI is not configured. We wrap our existing `LLMProvider` in a `DeepEvalBaseLLM` subclass and pass it explicitly to every metric.

Create `src/reportagent/llm/deepeval_judge.py`:

```python
from deepeval.models import DeepEvalBaseLLM
from reportagent.llm import get_llm_provider


class OurJudgeLLM(DeepEvalBaseLLM):
    def load_model(self):
        return get_llm_provider()

    def generate(self, prompt: str) -> str:
        provider = self.load_model()
        return provider.invoke(
            [{"role": "user", "content": prompt}],
            max_tokens=1000,
        )

    async def a_generate(self, prompt: str) -> str:
        provider = self.load_model()
        return provider.invoke(
            [{"role": "user", "content": prompt}],
            max_tokens=1000,
        )

    def get_model_name(self) -> str:
        return "llama3-70b-bedrock"
```

Every metric must receive this judge explicitly:

```python
judge = OurJudgeLLM()
metric = FaithfulnessMetric(threshold=0.7, model=judge)
```

**Test this in isolation before wiring into graphs.** DeepEval passes raw string prompts to `generate()`. Verify that Llama 3 70B via Bedrock returns clean text responses to these prompts without wrapping them in extra formatting.

---

## Step 3 — Schema Changes (`schemas.py`)

Add quality scores to `Report`:

```python
class Report(BaseModel):
    ...
    faithfulness_score: Optional[float] = None    # 0-1, from DeepEval
    hallucination_score: Optional[float] = None   # 0-1, from DeepEval
```

Add quality scores to `ChatMessage`:

```python
class ChatMessage(BaseModel):
    ...
    answer_relevancy_score: Optional[float] = None
    faithfulness_score: Optional[float] = None
```

Add new `ChatEvalResult` schema:

```python
class ChatEvalResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    query: str
    query_type: str = ""               # slice scores by query type later
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    guardrail_triggered: bool = False  # exclude blocked queries from averages
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

**Why `query_type`:** Adversarial queries should score lower on faithfulness. If they don't, the guardrail may not be functioning correctly. Storing this field lets you verify that assumption later. `guardrail_triggered` prevents blocked queries from polluting quality averages.

---

## Step 4 — DeepEval Input Format

DeepEval requires an `LLMTestCase` object:

```python
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(
    input=query,
    actual_output=response.content,
    retrieval_context=[c.text for c in chunks],  # list of strings
    expected_output=None,
)
```

**Metrics that work without `expected_output` (use in live pipeline):**
- `FaithfulnessMetric` — does the answer stick to retrieved chunks?
- `AnswerRelevancyMetric` — did the response answer the question?
- `HallucinationMetric` — are there hallucinated facts?

**Metrics that require `expected_output` (keep in RAGAS offline eval only):**
- `ContextualPrecisionMetric`
- `ContextualRecallMetric`

---

## Step 5 — Ingestion Graph: `quality_eval_node`

**Position:** After `critic_node`, before `persister_node`

```
reporter → critic → quality_eval_node → persister
```

**What it does:**
- Runs `FaithfulnessMetric` and `HallucinationMetric` on the draft report
- Attaches scores to `state.draft_report`
- Hard blocks (drops report, routes to END) only if faithfulness < 0.3
- Logs scores to structlog

**Why no retry routing:** The critic already handles retries via `critic_iterations`. Adding a second retry gate here using the same counter would allow up to 4 revision cycles, violating `MAX_CRITIC_ITERATIONS=2`. DeepEval's role here is **scoring and hard failure detection only**.

```python
def after_quality_eval(state: IngestionState) -> str:
    score = state.draft_report.faithfulness_score
    if score is not None and score < 0.3:
        log.warning("quality_eval_hard_block", score=score)
        return END
    return "persister"
```

**Why it sits after the critic:** The critic catches obvious failures and triggers rewrites. By the time `quality_eval_node` runs, the report has already passed a grounding check. DeepEval adds a scored signal on top of an already-filtered output.

---

## Step 6 — Chat Graph: `response_eval_node`

**Position:** Replaces `faithfulness_check_node`

```
responder → response_eval_node → END
```

**What it does:**
- Fires eval in background thread — user gets response immediately
- Runs `FaithfulnessMetric` and `AnswerRelevancyMetric`
- Hard blocks (appends warning to response) only if faithfulness < 0.5
- Logs scores to SQLite and W&B

**Pass primitives into thread, not state objects:**

```python
import threading

def response_eval_node(state: ChatState) -> ChatState:
    response_content = state.response.content
    chunk_texts = [c.text for c in state.retrieved_chunks]
    query = state.sanitised_query
    session_id = state.session_id
    query_type = state.query_type

    threading.Thread(
        target=_run_eval_in_background,
        args=(response_content, chunk_texts, query, session_id, query_type),
        daemon=True,
    ).start()
    return state


def _run_eval_in_background(
    response_content: str,
    chunk_texts: list[str],
    query: str,
    session_id: str,
    query_type: str,
) -> None:
    from deepeval.test_case import LLMTestCase
    from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
    from reportagent.llm.deepeval_judge import OurJudgeLLM
    from reportagent.storage.archive import Archive
    import wandb

    judge = OurJudgeLLM()
    test_case = LLMTestCase(
        input=query,
        actual_output=response_content,
        retrieval_context=chunk_texts,
    )

    faithfulness_metric = FaithfulnessMetric(threshold=0.5, model=judge)
    relevancy_metric = AnswerRelevancyMetric(threshold=0.5, model=judge)
    faithfulness_metric.measure(test_case)
    relevancy_metric.measure(test_case)

    result = ChatEvalResult(
        session_id=session_id,
        query=query,
        query_type=query_type,
        faithfulness=faithfulness_metric.score,
        answer_relevancy=relevancy_metric.score,
    )

    # Persist to SQLite
    Archive().save_chat_eval(result)
    # W&B logging happens here too — see experiment_tracking_plan.md
```

**Why primitives not objects:** Streamlit reruns the session on any user interaction. If a rerun mutates the state object while the background thread is still reading it, you get a race condition. Passing `str` and `list[str]` copies eliminates this entirely.

---

## Step 7 — W&B Integration

### Initialisation

W&B is initialised once per scheduler startup in `scheduler.py`:

```python
import wandb

wandb.init(
    project="genai-report-agent",
    name=f"run_{run_id}",
    config={
        "topic": settings.default_topic,
        "chunk_size": 512,
        "chunk_overlap": 64,
        "max_critic_iterations": settings.max_critic_iterations,
        "llm_provider": settings.llm_provider,
    }
)
```

### What Gets Logged and Where

**In `persister_node` (ingestion graph) — per ingestion run:**

```python
wandb.log({
    # Pipeline metrics
    "ingestion/articles_fetched": len(state.articles),
    "ingestion/chunks_added": len(state.new_chunks),
    "ingestion/critic_iterations": state.critic_iterations,

    # Quality scores from DeepEval
    "quality/faithfulness": state.draft_report.faithfulness_score,
    "quality/hallucination": state.draft_report.hallucination_score,

    # Report metadata
    "report/word_count": state.draft_report.word_count,
    "report/n_takeaways": len(state.draft_report.key_takeaways),
    "report/n_sources": len(state.draft_report.source_urls),
})
wandb.finish()
```

**In `_run_eval_in_background` (chat graph) — per chat response:**

```python
wandb.log({
    "chat/faithfulness": result.faithfulness,
    "chat/answer_relevancy": result.answer_relevancy,
    "chat/query_type": query_type,
    "chat/chunks_retrieved": len(chunk_texts),
})
```

**In threshold calibration script (future) — per threshold experiment:**

```python
wandb.log({
    "threshold/value": threshold,
    "threshold/precision": precision,
    "threshold/recall": recall,
    "threshold/f1": f1,
    "threshold/articles_passed": n_passed,
})
```

This last one is particularly useful — it means threshold tuning experiments from `article_filtering.md` are tracked and comparable in the W&B dashboard.

### What W&B Gives You That Nothing Else Does

- **Time-series charts** of faithfulness/hallucination scores across every ingestion run
- **Run comparison** — "did quality improve after I changed the retrieval threshold?"
- **Config tracking** — each run logs chunk size, LLM provider, topic so you can correlate config changes with quality changes
- **Alerts** — W&B can alert if faithfulness drops below a baseline threshold across runs

---

## Step 8 — Archive: SQLite for UI Display

Add `chat_eval_results` table:

```sql
CREATE TABLE chat_eval_results (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    query TEXT,
    query_type TEXT,
    faithfulness REAL,
    answer_relevancy REAL,
    guardrail_triggered INTEGER DEFAULT 0,
    timestamp TEXT
)
```

New `Archive` methods:

```python
def save_chat_eval(self, result: ChatEvalResult) -> None: ...
def get_recent_chat_evals(self, limit: int = 20) -> list[ChatEvalResult]: ...
def get_avg_chat_scores(self) -> dict: ...
```

---

## Step 9 — UI: Show Scores in Streamlit

**Sidebar run history** — faithfulness and hallucination per ingestion run:
```
✅ 21 May 14:00 — 5 new articles, faithfulness: 0.87, hallucination: 0.12
```

**Sidebar quality summary** — rolling averages:
```
📊 Chat Quality (last 20 responses)
   Avg Faithfulness:    0.83
   Avg Relevancy:       0.88
```

> **Streamlit constraint:** Scores are async. They do not exist when the response first renders. Do not show scores inline in the chat window. Show them only in the sidebar quality summary, which reads fresh from SQLite on each page interaction.

---

## What We're NOT Changing

| Component | Reason |
|---|---|
| RAGAS offline eval | Different purpose — batch benchmarking against golden set |
| Critic node | Stays as fast binary pre-filter before `quality_eval_node` |
| LangSmith tracing | Different layer — per-node debugging, not cross-run trending |
| Pydantic validation | Structural gate, not quality measurement |

---

## Updated Graph Structures

### Ingestion Graph
```
planner → fetcher → cleaner → deduper
    → chunker_embedder → reporter → critic
    → quality_eval_node → persister
```

### Chat Graph
```
guardrail → query_router → retriever
    → responder → response_eval_node (async: DeepEval + SQLite) → END
```

---

## Full File Changelist

| File | Change |
|---|---|
| `pyproject.toml` | Add `deepeval` |
| `src/reportagent/llm/deepeval_judge.py` | New — `DeepEvalBaseLLM` wrapper |
| `schemas.py` | Score fields on `Report`, `ChatMessage`; new `ChatEvalResult` |
| `graphs/ingestion.py` | Add `quality_eval_node`, `after_quality_eval` edge |
| `graphs/chat.py` | Replace `faithfulness_check_node` with async `response_eval_node` |
| `storage/archive.py` | `chat_eval_results` table, save/query methods |
| `scheduler.py` | `wandb.init()` on startup, `wandb.finish()` on completion |
| `ui/app.py` | Quality summary in sidebar |

---

## Implementation Order

1. `deepeval_judge.py` — test in isolation, verify Llama 3 70B prompt format
2. `schemas.py` — score fields and `ChatEvalResult`
3. `storage/archive.py` — table and methods
4. `graphs/ingestion.py` — `quality_eval_node`
5. `graphs/chat.py` — `response_eval_node`
6. `scheduler.py` — W&B init
7. `ui/app.py` — sidebar quality summary
