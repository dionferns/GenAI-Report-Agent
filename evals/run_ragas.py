"""RAGAS evaluation runner."""

import json
import os
from datetime import datetime
from pathlib import Path

from reportagent.schemas import EvalResult
from reportagent.storage.archive import Archive
from reportagent.tools.retriever import HybridRetriever
from reportagent.graphs.chat import chat_graph
from reportagent.schemas import ChatState

try:
    from ragas.metrics import faithfulness, answer_relevancy, context_precision
    from ragas import evaluate
    from datasets import Dataset
except ImportError:
    print("RAGAS not installed. Install with: pip install ragas datasets")
    exit(1)
 

def run_evaluation():
    """Run RAGAS evaluation against the golden dataset."""
    golden_set_path = Path(__file__).parent / "golden_set.jsonl"

    # Load golden dataset
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
    answers = []
    contexts_list = []

    for question in questions:
        # Retrieve context
        chunks = retriever.retrieve(question, n_results=8)
        contexts = [[chunk.text for chunk in chunks]]

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

        answers.append(answer)
        contexts_list.append(contexts[0])

    # Create dataset for RAGAS
    eval_dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts_list,
        "ground_truth": ground_truths,
    })

    # Run evaluation
    print("Running RAGAS evaluation...")
    results = evaluate(
        eval_dataset,
        metrics=[faithfulness, answer_relevancy, context_precision],
    )

    # Extract scores
    avg_faithfulness = results["faithfulness"].mean()
    avg_answer_relevancy = results["answer_relevancy"].mean()
    avg_context_precision = results["context_precision"].mean()

    # Create evaluation result
    eval_result = EvalResult(
        run_at=datetime.utcnow(),
        faithfulness=float(avg_faithfulness),
        answer_relevancy=float(avg_answer_relevancy),
        context_precision=float(avg_context_precision),
        num_questions=len(questions),
        num_failures=sum(1 for f in results["faithfulness"] if f < 0.5),
        failure_examples=[],
    )

    # Save results
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"ragas_{timestamp}.md"

    with open(results_file, "w") as f:
        f.write("# RAGAS Evaluation Results\n\n")
        f.write(f"**Run at:** {eval_result.run_at.isoformat()}\n\n")
        f.write("## Metrics\n\n")
        f.write(f"- **Faithfulness:** {eval_result.faithfulness:.4f}\n")
        f.write(f"- **Answer Relevancy:** {eval_result.answer_relevancy:.4f}\n")
        f.write(f"- **Context Precision:** {eval_result.context_precision:.4f}\n")
        f.write(f"- **Questions Evaluated:** {eval_result.num_questions}\n")
        f.write(f"- **Failures (Faithfulness < 0.5):** {eval_result.num_failures}\n")

    # Save to archive
    archive = Archive()
    archive.save_eval_result(eval_result)

    print(f"\n✅ Evaluation complete!")
    print(f"Faithfulness: {eval_result.faithfulness:.4f}")
    print(f"Answer Relevancy: {eval_result.answer_relevancy:.4f}")
    print(f"Context Precision: {eval_result.context_precision:.4f}")
    print(f"Results saved to: {results_file}")


if __name__ == "__main__":
    run_evaluation()
