"""APScheduler-based ingestion trigger."""

from uuid import uuid4
from apscheduler.schedulers.blocking import BlockingScheduler
import structlog

from reportagent.config import get_settings
from reportagent.schemas import IngestionState
from reportagent.graphs.ingestion import ingestion_graph
from reportagent.observability.logging import setup_logging
from reportagent.observability.tracing import setup_tracing

log = structlog.get_logger()


def run_ingestion():
    """Run one ingestion cycle."""
    settings = get_settings()
    run_id = str(uuid4())

    task_log = structlog.get_logger().bind(run_id=run_id, trigger="scheduler")
    task_log.info("ingestion_started")

    try:
        state = IngestionState(
            run_id=run_id,
            topic=settings.default_topic,
        )

        # Run the graph
        final_state = ingestion_graph.invoke(state.model_dump())
        task_log.info("ingestion_completed")

    except Exception as e:
        task_log.error("ingestion_failed", error=str(e))


def main():
    """Start the scheduler."""
    setup_logging()
    setup_tracing()

    settings = get_settings()

    log.info("scheduler_starting", interval_minutes=settings.ingest_interval_minutes)

    # Run once immediately on startup
    run_ingestion()

    # Schedule recurring job
    scheduler = BlockingScheduler()

    scheduler.add_job(
        run_ingestion,
        "interval",
        minutes=settings.ingest_interval_minutes,
        id="ingestion_job",
    )

    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info("scheduler_stopped")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
