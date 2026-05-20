"""Manually trigger one ingestion run."""

import asyncio
from uuid import uuid4

from reportagent.schemas import IngestionState
from reportagent.graphs.ingestion import ingestion_graph
from reportagent.observability.logging import setup_logging
from reportagent.observability.tracing import setup_tracing


async def main():
    """Trigger one ingestion run."""
    setup_logging()
    setup_tracing()

    run_id = str(uuid4())
    print(f"Triggering ingestion run: {run_id}")

    state = IngestionState(
        run_id=run_id,
        topic="uk_ai_regulation",
    )

    result = await asyncio.to_thread(
        ingestion_graph.invoke,
        state.model_dump(),
    )

    if result.get("draft_report"):
        report = result["draft_report"]
        print(f"\n✅ Ingestion successful!")
        print(f"Report ID: {report.id}")
        print(f"Summary preview: {report.summary[:200]}...")
    else:
        print(f"\n❌ Ingestion failed or no report generated")


if __name__ == "__main__":
    asyncio.run(main())
