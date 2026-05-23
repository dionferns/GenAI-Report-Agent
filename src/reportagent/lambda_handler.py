"""Lambda entrypoint — triggered by EventBridge every hour."""

import json
from uuid import uuid4
from reportagent.observability.logging import setup_logging
from reportagent.observability.tracing import setup_tracing


def lambda_handler(event, context):
    """EventBridge calls this every hour."""
    setup_logging()
    setup_tracing()

    from reportagent.schemas import IngestionState
    from reportagent.graphs.ingestion import ingestion_graph
    from reportagent.config import get_settings

    settings = get_settings()
    run_id = str(uuid4())

    print(f"ingestion_started run_id={run_id} topic={settings.default_topic}")

    try:
        state = IngestionState(
            run_id=run_id,
            topic=settings.default_topic,
        )

        ingestion_graph.invoke(state.model_dump())

        print(f"ingestion_completed run_id={run_id}")
        return {
            "statusCode": 200,
            "body": json.dumps({"run_id": run_id, "status": "success"})
        }

    except Exception as e:
        print(f"ingestion_failed run_id={run_id} error={str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"run_id": run_id, "status": "failed", "error": str(e)})
        }
