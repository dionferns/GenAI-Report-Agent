# Test: Deduplication Safeguard

## Scenario: 30 Duplicate URLs with max_empty_batches=3

Setup:
- RSS feeds return 30 URLs total
- max_urls_per_run = 10
- max_empty_batches = 3 (new setting)
- ALL 30 URLs are duplicates (already in vector store)

### Expected Behavior

**Iteration 1:**
```
planner_node
├─ all_urls = [URL_1...URL_30]
├─ urls_to_fetch = [URL_1...URL_10]
└─ urls_tried_in_run = [URL_1...URL_10]

fetcher → cleaner → deduper
├─ All 10 articles are duplicates
├─ state.articles = []
└─ consecutive_empty_batches = 0 (not incremented yet)

after_deduper
├─ if len(articles) == 0 AND NOT processed_all:  ✅ TRUE
├─ consecutive_empty_batches += 1  → 1
├─ if consecutive_empty_batches >= 3:  ❌ (1 < 3)
└─ return "planner"  ← Try next batch
```

**Iteration 2:**
```
planner_node
├─ urls_to_fetch = [URL_11...URL_20]
└─ urls_tried_in_run = [URL_1...URL_20]

fetcher → cleaner → deduper
├─ All 10 articles are duplicates
├─ state.articles = []

after_deduper
├─ consecutive_empty_batches += 1  → 2
├─ if consecutive_empty_batches >= 3:  ❌ (2 < 3)
└─ return "planner"  ← Try next batch
```

**Iteration 3:**
```
planner_node
├─ urls_to_fetch = [URL_21...URL_30]
└─ urls_tried_in_run = [URL_1...URL_30]

fetcher → cleaner → deduper
├─ All 10 articles are duplicates
├─ state.articles = []

after_deduper
├─ consecutive_empty_batches += 1  → 3
├─ if consecutive_empty_batches >= 3:  ✅ TRUE
├─ Set processed_all_articles = True  ← Exit condition
├─ Log: "max_empty_batches_reached batches=3 max=3"
└─ return "chunker_embedder"  ← Skip retry, continue forward
```

**Iteration 4:**
```
fetcher_node
├─ if not state.urls_to_fetch:  ✅ TRUE (empty)
└─ return state  (skip)

cleaner, deduper
└─ Skip (empty articles)

chunker_embedder → reporter → critic → persister
├─ chunker_embedder: state.new_chunks = []
├─ reporter: if not state.new_chunks: return  (skip)
└─ persister: if state.processed_all_articles: return  (skip, no report saved)

Graph ends ✅
```

### Timing Improvement

**Without safeguard:**
- 3 iterations × 10 URLs × 7 sec/batch = 210 seconds
- Would keep looping until all 30 URLs checked

**With safeguard:**
- 3 iterations × 10 URLs × 7 sec/batch = 210 seconds
- **But stops after 3**, doesn't continue to URLs 31-1000

**Real-world example (500 URLs):**
- Without: 500 / 10 = 50 iterations × 7 sec = 350 seconds (5.8 min)
- With: 3 iterations × 7 sec = 21 seconds

**Savings: 329 seconds per run = ~$0.04 per Lambda invocation**

## Configuration

To adjust the threshold, set environment variable:

```bash
MAX_EMPTY_BATCHES=5  # Try up to 5 batches before giving up
```

Or edit `.env`:
```
MAX_EMPTY_BATCHES=3
```

Default: 3 batches (30 URLs with max_urls_per_run=10)

## Why 3?

- Small enough to avoid wasting Lambda time on stale feeds
- Large enough to handle normal deduplication (most feeds have <30 new URLs per hour)
- Configurable if needed
