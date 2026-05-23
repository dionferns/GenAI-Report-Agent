# Experiment Tracking Plan (W&B / MLflow)

## What Problem This Solves

The current stack captures what happens *inside* a single run (LangSmith traces, structlog JSON, RunLogger JSONL) but has no way to answer cross-run questions:

- Did report quality improve after changing the retrieval threshold?
- Is faithfulness trending down over the last 10 ingestion runs?
- Which LLM configuration produces the highest quality summaries?
- At what threshold value does article filtering precision peak?

None of structlog, LangSmith, or SQLite answer these. Experiment tracking does.

---

## W&B vs MLflow

| | W&B | MLflow |
|---|---|---|
| **Hosting** | SaaS, free tier available | Self-hosted (`mlflow ui` on localhost) or managed |
| **Best for** | Inference-time metric tracking, visual dashboards, demos | ML training experiments, model registry, self-hosted preference |
| **LangGraph integration** | Native `WandbTracer` for LangChain/LangGraph | Manual logging only |
| **Dashboard quality** | Excellent — good for writeups and demos | Functional but less polished |
| **Free tier** | Sufficient for this project | Fully free (self-hosted) |
| **External dependency** | Yes — requires internet + W&B account | No — runs locally |

**Recommendation: W&B.** You are already using LangSmith (cloud-hosted observability), so cloud tooling fits the stack. The visual dashboard is better for a demo or writeup. The native LangGraph integration reduces boilerplate. MLflow is the better choice if you later fine-tune a model or need a self-hosted setup — note that in the writeup as a future path.

---

## What Gets Logged and Where

### Layer Separation

| Tool | What it captures | Scope |
|---|---|---|
| structlog | Node entry/exit events, errors | Per node, per run |
| LangSmith | Full LLM traces, token usage, latency | Per node, per run |
| DeepEval | Quality scores (faithfulness, relevancy) | Per output |
| **W&B** | All of the above unified, with history and comparison | Across runs |
| SQLite | Scores for Streamlit UI display | Local persistence |

W&B sits above all the others — it tracks the metrics that DeepEval computes, alongside pipeline metadata, across every run over time.

---

## Implementation

### Step 1 — Install

Add to `pyproject.toml`:

```toml
wandb>=0.17
```

### Step 2 — Initialisation (`scheduler.py`)

W&B is initialised once per ingestion run in `scheduler.py`. Each run becomes a separate W&B run, so you can compare them:

```python
import wandb

def run_ingestion():
    run_id = str(uuid4())
    
    wandb.init(
        project="genai-report-agent",
        name=f"ingestion_{run_id[:8]}",
        config={
            "topic": settings.default_topic,
            "chunk_size": 512,
            "chunk_overlap": 64,
            "max_critic_iterations": settings.max_critic_iterations,
            "llm_provider": settings.llm_provider,
            "max_urls_per_run": settings.max_urls_per_run,
        },
        tags=[settings.default_topic, settings.llm_provider],
    )
    
    # ... run the ingestion graph ...
    
    wandb.finish()
```

The `config` block is important — it means every run records what parameters were used, so you can later correlate config changes with quality changes in the W&B UI.

### Step 3 — Log Per Ingestion Run (`persister_node`)

In `graphs/ingestion.py`, add W&B logging at the end of `persister_node` after the report is saved:

```python
import wandb

# Inside persister_node, after archive.save_report():
wandb.log({
    # Pipeline metrics
    "ingestion/articles_fetched": len(state.articles),
    "ingestion/chunks_added": len(state.new_chunks),
    "ingestion/critic_iterations": state.critic_iterations,

    # Quality scores (populated by quality_eval_node from DeepEval)
    "quality/faithfulness": state.draft_report.faithfulness_score,
    "quality/hallucination": state.draft_report.hallucination_score,

    # Report structure
    "report/word_count": state.draft_report.word_count,
    "report/n_takeaways": len(state.draft_report.key_takeaways),
    "report/n_sources": len(state.draft_report.source_urls),
    "report/critic_approved": state.critic_verdict.verdict == "approve" if state.critic_verdict else None,
})
```

### Step 4 — Log Per Chat Response (`_run_eval_in_background`)

In `graphs/chat.py`, add W&B logging inside the background eval thread after DeepEval scores are computed:

```python
import wandb

wandb.log({
    "chat/faithfulness": result.faithfulness,
    "chat/answer_relevancy": result.answer_relevancy,
    "chat/query_type": query_type,
    "chat/chunks_retrieved": len(chunk_texts),
    "chat/guardrail_triggered": False,
})
```

Note: Chat responses are logged to the same W&B project but outside a specific ingestion run. W&B handles this — logs outside `wandb.init()`/`wandb.finish()` blocks go to a persistent run for the session.

### Step 5 — Log Threshold Calibration Experiments

When running the article relevance threshold tuning from `article_filtering.md`, log each threshold experiment to W&B:

```python
import wandb

wandb.init(project="genai-report-agent", name="threshold_calibration")

for threshold in thresholds:
    precision, recall, f1 = evaluate_threshold(threshold, labelled_data)
    wandb.log({
        "threshold/value": threshold,
        "threshold/precision": precision,
        "threshold/recall": recall,
        "threshold/f1": f1,
        "threshold/articles_passed": n_passed,
    })

wandb.finish()
```

This directly addresses the empirical threshold tuning methodology described in `article_filtering.md` — every experiment is tracked and the precision-recall curve is visible in the W&B dashboard.

---

## What the W&B Dashboard Shows

Once implemented, the W&B project dashboard gives you:

**Time-series charts:**
- `quality/faithfulness` over time — is report quality stable or drifting?
- `ingestion/articles_fetched` over time — are we consistently getting new articles?
- `ingestion/critic_iterations` distribution — how often does the critic need to retry?

**Run comparison table:**
- Compare any two ingestion runs side by side — articles fetched, quality scores, config used
- Identify which config change caused a quality improvement or regression

**Threshold calibration chart:**
- Precision-recall curve from the threshold tuning experiments
- F1 score vs threshold — pick the operating point deliberately

**Chat quality trend:**
- `chat/faithfulness` and `chat/answer_relevancy` over time
- Sliced by `chat/query_type` — verify adversarial queries score lower than vague queries

---

## What We're NOT Changing

- LangSmith stays for per-node debugging traces — W&B does not replace it
- structlog stays for file-based JSON logs — W&B does not replace it
- SQLite stays for Streamlit UI display — W&B is not queried by the UI

---

## File Changelist

| File | Change |
|---|---|
| `pyproject.toml` | Add `wandb` |
| `scheduler.py` | `wandb.init()` on startup, `wandb.finish()` on completion |
| `graphs/ingestion.py` | `wandb.log()` in `persister_node` |
| `graphs/chat.py` | `wandb.log()` in `_run_eval_in_background` |
| `scripts/calibrate_threshold.py` | New script — threshold tuning with W&B logging |

---

## Note on MLflow as an Alternative

MLflow is worth noting in the writeup as the production-grade alternative:

- Fully self-hosted — no external SaaS dependency
- Has a model registry — relevant if you later fine-tune a 7B Llama model
- `mlflow.log_metric()` and `mlflow.log_params()` are equivalent to W&B's API
- The trade-off is a less polished UI and no native LangGraph integration

The architecture supports swapping W&B for MLflow with minimal changes — the logging calls are nearly identical. This is the same provider abstraction pattern used for the LLM layer.
