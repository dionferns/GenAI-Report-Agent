# Article Relevance Filtering — Explored Approaches

The current planner fetches all articles from BBC RSS feeds without topic filtering. Below are the approaches considered for filtering articles to only UK economy content, with honest pros and cons.

---

## Option 1: Hardcoded Keyword Matching (Current Approach)

Filter RSS entry titles and summaries against a list of UK economy keywords before fetching HTML.

| | |
|---|---|
| **Pros** | Zero cost, no API calls, instant, fully deterministic |
| **Cons** | Brittle — `"economy"` matches "US economy"; multi-word phrases like `"bank of england"` must be matched as a whole unit, not individual words; misses semantic variants like "Rachel Reeves announces spending cuts" |

---

## Option 2: News API / SerpAPI Source Discovery

Replace hardcoded RSS feeds with a news search API (NewsAPI.org, SerpAPI). Query with your topic keywords and get back pre-filtered, structured results (title, URL, snippet) without fetching HTML first.

| | |
|---|---|
| **Pros** | No hardcoded URLs; returns only relevant articles by design; structured metadata (title, snippet, date) without HTML fetching |
| **Cons** | NewsAPI free tier: 100 requests/day, 24-hour delay on articles; paid tier is $449/month. SerpAPI free tier: 100 searches/month — insufficient for hourly runs |

---

## Option 3: Semantic Similarity Filtering (Embedding-Based)

Embed the article title + first 2-3 sentences. Embed a natural language topic description (e.g. *"News about the UK economy including inflation, GDP, wages, employment and government fiscal policy"*). Filter by cosine similarity above a threshold.

| | |
|---|---|
| **Pros** | No brittle keyword rules; catches semantic variants ("chancellor announces spending cuts"); works across any topic without reconfiguration; cheap — only short snippets are embedded, not full articles |
| **Cons** | Threshold tuning is non-trivial (see below); embedding a keyword list instead of a natural language description produces a noisy centroid; requires empirical validation on a labelled dataset |

### On Threshold Tuning

The threshold is essentially a classifier decision boundary and must be tuned empirically:

1. Run the pipeline without filtering for several cycles, collect all articles
2. Manually label a sample (50-100 examples) as relevant / not relevant
3. Compute the precision-recall curve across thresholds using `sklearn.metrics.precision_recall_curve`
4. Select the F1-optimal threshold — or bias toward recall if missing relevant articles is a worse failure than letting noise through (which it is here, since the downstream critic node provides a second quality gate)
5. Re-evaluate periodically — news topic distributions drift over time

```python
from sklearn.metrics import precision_recall_curve
import numpy as np

precision, recall, thresholds = precision_recall_curve(labels, scores)
f1_scores = 2 * (precision * recall) / (precision + recall + 1e-9)
optimal_threshold = thresholds[np.argmax(f1_scores)]
```

This is the standard industry approach — W&B or MLflow would be used to track threshold experiments across runs. LangSmith (already integrated) can serve a similar purpose for tracking what gets filtered per run.

### Why a Natural Language Description, Not a Keyword List

Embedding `"UK economy inflation budget wages"` gives a noisy centroid — the model averages across unrelated concepts. Embedding `"News about the UK economy including inflation, GDP, wages, employment and government fiscal policy"` gives a semantically coherent vector that better represents the topic.

---

## Option 4: LLM-Based Relevance Classification

After fetching title + snippet from the news API or RSS feed, ask a cheap LLM (e.g. Claude Haiku, GPT-4o-mini): *"Is this article about the UK economy? Answer yes or no."*

| | |
|---|---|
| **Pros** | Most accurate; handles context naturally; no threshold to tune; understands nuance (e.g. "Reeves budget" is UK economy even without the word "economy") |
| **Cons** | ~$0.001 per 100 articles — cheap but non-zero; adds latency per article; requires an LLM call before deciding whether to fetch HTML |

---

## Option 5: Fine-Tuned Classifier (Large Scale)

Train a small BERT/DistilBERT classifier on labelled news articles for the topic.

| | |
|---|---|
| **Pros** | Fastest inference; most accurate at scale; used by Reuters, Bloomberg internally |
| **Cons** | Requires labelled training data; retraining overhead; overkill for this project scope |

---

## Production Recommendation

The most common production pattern is **Option 2 + Option 4**: a news API handles broad source discovery, and an LLM classifier provides a post-fetch relevance gate. For this project, **Option 3** (semantic similarity with empirically-tuned threshold) is the most practical upgrade — it eliminates brittle keyword rules without requiring a paid API, and the threshold calibration methodology is well-established.
