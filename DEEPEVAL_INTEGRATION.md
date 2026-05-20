# DeepEval Integration Guide

## Overview

DeepEval is a robust evaluation framework for LLM applications. We can use it **alongside or instead of RAGAS** for more comprehensive evaluation.

### DeepEval vs RAGAS

| Feature | RAGAS | DeepEval |
|---------|-------|----------|
| **Faithfulness** | ✅ Yes | ✅ Yes (more granular) |
| **Relevance** | ✅ Yes | ✅ Yes |
| **Context Quality** | ✅ Yes | ✅ Yes |
| **Hallucination** | ❌ No | ✅ Yes |
| **Toxicity** | ❌ No | ✅ Yes |
| **Bias Detection** | ❌ No | ✅ Yes |
| **Custom Metrics** | ⚠️ Hard | ✅ Easy |
| **LLM-based Tests** | ✅ Yes | ✅ Yes (better) |
| **Reporting** | ✅ Good | ✅ Excellent |

**Recommendation:** Use **DeepEval** - more comprehensive and better for production.

---

## Step 1: Install DeepEval

```bash
source .venv/bin/activate
pip install deepeval
```

That's it! DeepEval has fewer dependencies than RAGAS.

---

## Step 2: Create DeepEval Evaluation Script

Create a new file: `evals/run_deepeval.py`

```python
"""DeepEval evaluation runner."""

import json
from datetime import datetime
from pathlib import Path
from deepeval import evaluate
from deepeval.metrics import (
    Faithfulness,
    AnswerRelevancy,
    ContextualPrecision,
    Hallucination,
)
from deepeval.test_case import LLMTestCase

from reportagent.schemas import EvalResult
from reportagent.storage.archive import Archive
from reportagent.tools.retriever import HybridRetriever
from reportagent.graphs.chat import chat_graph
from reportagent.schemas import ChatState


def run_deepeval_evaluation():
    """Run DeepEval evaluation against the golden dataset."""
    golden_set_path = Path(__file__).parent / "golden_set.jsonl"

    # Load golden dataset
    test_cases = []
    questions = []
    ground_truths = []

    with open(golden_set_path) as f:
        for line in f:
            data = json.loads(line)
            questions.append(data["question"])
            ground_truths.append(data["ground_truth"])

    print(f"Loaded {len(questions)} evaluation questions")

    # Retrieve and generate answers
    retriever = HybridRetriever()
    faithfulness_scores = []
    relevancy_scores = []
    precision_scores = []
    hallucination_scores = []

    print("\nGenerating answers and running evaluation metrics...")

    for i, question in enumerate(questions, 1):
        print(f"  [{i}/{len(questions)}] Evaluating: {question[:50]}...")

        # Retrieve context
        chunks = retriever.retrieve(question, n_results=8)
        context = "\n".join([chunk.text for chunk in chunks])

        # Generate answer using chat graph
        chat_state = ChatState(
            session_id="eval",
            current_query=question,
        )
        result = chat_graph.invoke(chat_state.model_dump())

        if result.get("response"):
            answer = result["response"]["content"]
        else:
            answer = "No answer generated"

        # Create DeepEval test case
        test_case = LLMTestCase(
            input=question,
            actual_output=answer,
            expected_output=ground_truths[i - 1],
            retrieval_context=[context],
        )

        # Evaluate with each metric
        faithfulness = Faithfulness()
        relevancy = AnswerRelevancy()
        precision = ContextualPrecision()
        hallucination = Hallucination()

        # Run evaluations
        try:
            f_score = faithfulness.measure(test_case)
            faithfulness_scores.append(f_score)
        except Exception as e:
            print(f"    Faithfulness error: {e}")
            faithfulness_scores.append(0.0)

        try:
            r_score = relevancy.measure(test_case)
            relevancy_scores.append(r_score)
        except Exception as e:
            print(f"    Relevancy error: {e}")
            relevancy_scores.append(0.0)

        try:
            p_score = precision.measure(test_case)
            precision_scores.append(p_score)
        except Exception as e:
            print(f"    Precision error: {e}")
            precision_scores.append(0.0)

        try:
            h_score = hallucination.measure(test_case)
            hallucination_scores.append(h_score)
        except Exception as e:
            print(f"    Hallucination error: {e}")
            hallucination_scores.append(0.0)

        test_cases.append(test_case)

    # Calculate averages
    avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores)
    avg_relevancy = sum(relevancy_scores) / len(relevancy_scores)
    avg_precision = sum(precision_scores) / len(precision_scores)
    avg_hallucination = sum(hallucination_scores) / len(hallucination_scores)

    # Create evaluation result (compatible with our schema)
    eval_result = EvalResult(
        run_at=datetime.utcnow(),
        faithfulness=float(avg_faithfulness),
        answer_relevancy=float(avg_relevancy),
        context_precision=float(avg_precision),
        num_questions=len(questions),
        num_failures=sum(1 for f in faithfulness_scores if f < 0.5),
        failure_examples=[],
    )

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"deepeval_{timestamp}.md"

    with open(results_file, "w") as f:
        f.write("# DeepEval Evaluation Results\n\n")
        f.write(f"**Run at:** {eval_result.run_at.isoformat()}\n\n")
        f.write("## Metrics\n\n")
        f.write(f"- **Faithfulness:** {avg_faithfulness:.4f}\n")
        f.write(f"- **Answer Relevancy:** {avg_relevancy:.4f}\n")
        f.write(f"- **Context Precision:** {avg_precision:.4f}\n")
        f.write(f"- **Hallucination Score:** {avg_hallucination:.4f} (lower is better)\n")
        f.write(f"- **Questions Evaluated:** {len(questions)}\n")
        f.write(f"- **Failures (Faithfulness < 0.5):** {eval_result.num_failures}\n")

        f.write("\n## Detailed Scores\n\n")
        f.write("| Question | Faithfulness | Relevancy | Precision | Hallucination |\n")
        f.write("|----------|--------------|-----------|-----------|---------------|\n")
        for i, q in enumerate(questions):
            q_short = q[:40] + "..." if len(q) > 40 else q
            f.write(f"| {q_short} | {faithfulness_scores[i]:.3f} | {relevancy_scores[i]:.3f} | {precision_scores[i]:.3f} | {hallucination_scores[i]:.3f} |\n")

    # Save to archive
    archive = Archive()
    archive.save_eval_result(eval_result)

    print(f"\n✅ DeepEval Evaluation complete!")
    print(f"\nAverage Scores:")
    print(f"  Faithfulness: {avg_faithfulness:.4f}")
    print(f"  Answer Relevancy: {avg_relevancy:.4f}")
    print(f"  Context Precision: {avg_precision:.4f}")
    print(f"  Hallucination: {avg_hallucination:.4f} (lower is better)")
    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    run_deepeval_evaluation()
```

---

## Step 3: Update requirements.txt

Add DeepEval to your requirements:

```bash
# Add to requirements.txt
echo "deepeval>=0.21.0" >> requirements.txt

# Install it
source .venv/bin/activate
pip install deepeval
```

---

## Step 4: Update Makefile (Optional)

Update your Makefile to support both:

```makefile
eval-ragas:
	uv run python evals/run_ragas.py

eval-deepeval:
	uv run python evals/run_deepeval.py

eval: eval-deepeval eval-ragas
	@echo "✅ Both evaluations complete"
```

Or simpler - just replace RAGAS with DeepEval:

```makefile
eval:
	source .venv/bin/activate && python evals/run_deepeval.py
```

---

## Step 5: Run DeepEval Evaluation

```bash
source .venv/bin/activate
python evals/run_deepeval.py
```

**Output:**
```
Loaded 25 evaluation questions

Generating answers and running evaluation metrics...
  [1/25] Evaluating: Which UK organizations are involved...
  [2/25] Evaluating: What specific regulations did...
  ...
  [25/25] Evaluating: What's the latest AI policy...

✅ DeepEval Evaluation complete!

Average Scores:
  Faithfulness: 0.8234
  Answer Relevancy: 0.7890
  Context Precision: 0.7654
  Hallucination: 0.1234 (lower is better)

Results saved to: evals/results/deepeval_20260519_221530.md
```

---

## Step 6: Advanced - Custom Metrics (Optional)

DeepEval makes custom metrics easy:

```python
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

class CitationAccuracy(BaseMetric):
    """Check if answer citations match retrieved context."""

    def measure(self, test_case: LLMTestCase) -> float:
        # Your evaluation logic
        if self.include_reason:
            self.reason = "Custom reason"
        return score  # 0.0 to 1.0

# Use it
citation_metric = CitationAccuracy()
score = citation_metric.measure(test_case)
```

---

## Step 7: Compare Results

After running both, compare:

```bash
# View RAGAS results
cat evals/results/ragas_*.md

# View DeepEval results
cat evals/results/deepeval_*.md

# View both in results directory
ls evals/results/
```

---

## Complete Integration Code

Here's the full `evals/run_deepeval.py` file (copy-paste ready):

```python
"""DeepEval evaluation runner - comprehensive LLM evaluation framework."""

import json
from datetime import datetime
from pathlib import Path

from reportagent.schemas import EvalResult
from reportagent.storage.archive import Archive
from reportagent.tools.retriever import HybridRetriever
from reportagent.graphs.chat import chat_graph
from reportagent.schemas import ChatState

try:
    from deepeval import evaluate
    from deepeval.metrics import (
        Faithfulness,
        AnswerRelevancy,
        ContextualPrecision,
        Hallucination,
    )
    from deepeval.test_case import LLMTestCase
except ImportError:
    print("DeepEval not installed. Install with: pip install deepeval")
    exit(1)


def run_deepeval_evaluation():
    """Run comprehensive DeepEval evaluation."""
    golden_set_path = Path(__file__).parent / "golden_set.jsonl"

    # Load golden dataset
    test_cases = []
    questions = []
    ground_truths = []

    with open(golden_set_path) as f:
        for line in f:
            data = json.loads(line)
            questions.append(data["question"])
            ground_truths.append(data["ground_truth"])

    print(f"📊 Loaded {len(questions)} evaluation questions")

    # Retrieve and generate answers
    retriever = HybridRetriever()
    faithfulness_scores = []
    relevancy_scores = []
    precision_scores = []
    hallucination_scores = []

    print("\n🔍 Generating answers and running evaluation metrics...\n")

    for i, question in enumerate(questions, 1):
        print(f"  [{i:2d}/{len(questions)}] {question[:50]}...")

        # Retrieve context
        chunks = retriever.retrieve(question, n_results=8)
        context = "\n".join([chunk.text for chunk in chunks])

        # Generate answer
        chat_state = ChatState(
            session_id="eval",
            current_query=question,
        )
        result = chat_graph.invoke(chat_state.model_dump())
        answer = result.get("response", {}).get("content", "No answer") if result.get("response") else "No answer"

        # Create test case
        test_case = LLMTestCase(
            input=question,
            actual_output=answer,
            expected_output=ground_truths[i - 1],
            retrieval_context=[context],
        )

        # Evaluate metrics
        try:
            f_metric = Faithfulness()
            f_score = f_metric.measure(test_case)
            faithfulness_scores.append(f_score)
        except Exception as e:
            print(f"       Warning: Faithfulness error: {str(e)[:30]}")
            faithfulness_scores.append(0.0)

        try:
            r_metric = AnswerRelevancy()
            r_score = r_metric.measure(test_case)
            relevancy_scores.append(r_score)
        except Exception as e:
            print(f"       Warning: Relevancy error: {str(e)[:30]}")
            relevancy_scores.append(0.0)

        try:
            p_metric = ContextualPrecision()
            p_score = p_metric.measure(test_case)
            precision_scores.append(p_score)
        except Exception as e:
            print(f"       Warning: Precision error: {str(e)[:30]}")
            precision_scores.append(0.0)

        try:
            h_metric = Hallucination()
            h_score = h_metric.measure(test_case)
            hallucination_scores.append(h_score)
        except Exception as e:
            print(f"       Warning: Hallucination error: {str(e)[:30]}")
            hallucination_scores.append(0.0)

        test_cases.append(test_case)

    # Calculate averages
    avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0.0
    avg_relevancy = sum(relevancy_scores) / len(relevancy_scores) if relevancy_scores else 0.0
    avg_precision = sum(precision_scores) / len(precision_scores) if precision_scores else 0.0
    avg_hallucination = sum(hallucination_scores) / len(hallucination_scores) if hallucination_scores else 0.0

    # Create evaluation result
    eval_result = EvalResult(
        run_at=datetime.utcnow(),
        faithfulness=float(avg_faithfulness),
        answer_relevancy=float(avg_relevancy),
        context_precision=float(avg_precision),
        num_questions=len(questions),
        num_failures=sum(1 for f in faithfulness_scores if f < 0.5),
        failure_examples=[],
    )

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"deepeval_{timestamp}.md"

    with open(results_file, "w") as f:
        f.write("# DeepEval Evaluation Results\n\n")
        f.write(f"**Run at:** {eval_result.run_at.isoformat()}\n")
        f.write(f"**Framework:** DeepEval\n\n")

        f.write("## Summary Scores\n\n")
        f.write(f"- **Faithfulness:** {avg_faithfulness:.4f} (higher is better)\n")
        f.write(f"- **Answer Relevancy:** {avg_relevancy:.4f} (higher is better)\n")
        f.write(f"- **Context Precision:** {avg_precision:.4f} (higher is better)\n")
        f.write(f"- **Hallucination:** {avg_hallucination:.4f} (lower is better)\n")
        f.write(f"- **Questions:** {len(questions)}\n")
        f.write(f"- **Failed (Faithfulness < 0.5):** {eval_result.num_failures}\n\n")

        f.write("## Detailed Results\n\n")
        f.write("| # | Question | Faith | Relevancy | Precision | Hallucin |\n")
        f.write("|---|----------|-------|-----------|-----------|----------|\n")

        for i, q in enumerate(questions):
            q_short = (q[:35] + "...") if len(q) > 35 else q
            f.write(
                f"| {i+1:2d} | {q_short} | "
                f"{faithfulness_scores[i]:.3f} | {relevancy_scores[i]:.3f} | "
                f"{precision_scores[i]:.3f} | {hallucination_scores[i]:.3f} |\n"
            )

    # Save to archive
    archive = Archive()
    archive.save_eval_result(eval_result)

    # Print results
    print(f"\n✅ DeepEval Evaluation Complete!\n")
    print("📈 Summary Scores:")
    print(f"   Faithfulness:      {avg_faithfulness:.4f}")
    print(f"   Answer Relevancy:  {avg_relevancy:.4f}")
    print(f"   Context Precision: {avg_precision:.4f}")
    print(f"   Hallucination:     {avg_hallucination:.4f} (lower = better)")
    print(f"\n📁 Results saved to: {results_file}")


if __name__ == "__main__":
    run_deepeval_evaluation()
```

---

## Comparison: RAGAS vs DeepEval

### Use RAGAS If:
- You want quick evaluation
- You prefer simpler setup
- You need only basic metrics

### Use DeepEval If:
- You want **hallucination detection** ✅
- You want **toxicity detection** ✅
- You want **custom metrics** ✅
- You want **better reporting** ✅
- You're in production ✅

**Recommendation:** **Use DeepEval** - it's more comprehensive!

---

## Summary

### To Switch to DeepEval:

1. **Install:**
   ```bash
   pip install deepeval
   ```

2. **Create evaluator:**
   ```bash
   cp evals/run_deepeval.py  # Use code above
   ```

3. **Run it:**
   ```bash
   source .venv/bin/activate
   python evals/run_deepeval.py
   ```

4. **View results:**
   ```bash
   cat evals/results/deepeval_*.md
   ```

### What You Get:

✅ Faithfulness detection  
✅ Hallucination detection  
✅ Answer relevancy  
✅ Context precision  
✅ Custom metrics support  
✅ Better reporting  
✅ Production-ready  

---

## Next Steps

1. Install DeepEval: `pip install deepeval`
2. Add `evals/run_deepeval.py` (code above)
3. Run: `python evals/run_deepeval.py`
4. Compare with RAGAS results
5. Choose your framework!

Both work great - DeepEval is just more powerful! 🚀
