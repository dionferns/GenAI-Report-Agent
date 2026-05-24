"""SQLite archive for reports, run logs, and evaluation results."""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from reportagent.config import get_settings
from reportagent.schemas import Report, RunLog, EvalResult
import structlog

log = structlog.get_logger()


class Archive:
    """SQLite-based archive for reports and metadata."""

    def __init__(self):
        settings = get_settings()
        self.db_path = settings.sqlite_db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)

        # Run logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS run_logs (
                id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                data TEXT NOT NULL
            )
        """)

        # Eval results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS eval_results (
                run_at TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()
        log.info("archive_initialized", db_path=self.db_path)

    def save_report(self, report: Report) -> None:
        """Save a report to the archive."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO reports (id, topic, generated_at, data) VALUES (?, ?, ?, ?)",
            (report.id, report.topic, report.generated_at.isoformat(), report.model_dump_json()),
        )

        conn.commit()
        conn.close()
        log.info("report_saved", report_id=report.id)

    def get_latest_report(self, topic: str) -> Report | None:
        """Get the most recent report for a topic."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data FROM reports WHERE topic = ? ORDER BY generated_at DESC LIMIT 1",
            (topic,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return Report.model_validate_json(row[0])
        return None

    def get_reports_since(self, topic: str, since: datetime) -> list[Report]:
        """Get all reports since a given timestamp."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data FROM reports WHERE topic = ? AND generated_at >= ? ORDER BY generated_at DESC",
            (topic, since.isoformat()),
        )
        rows = cursor.fetchall()
        conn.close()

        return [Report.model_validate_json(row[0]) for row in rows]

    def save_run_log(self, run_log: RunLog) -> None:
        """Save a run log to the archive."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO run_logs (id, started_at, data) VALUES (?, ?, ?)",
            (run_log.id, run_log.started_at.isoformat(), run_log.model_dump_json()),
        )

        conn.commit()
        conn.close()

    def update_run_log(self, run_id: str, **kwargs) -> None:
        """Update a run log with new values."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Fetch existing run log
        cursor.execute("SELECT data FROM run_logs WHERE id = ?", (run_id,))
        row = cursor.fetchone()

        if row:
            run_log = RunLog.model_validate_json(row[0])
            # Update fields
            for key, value in kwargs.items():
                if hasattr(run_log, key):
                    setattr(run_log, key, value)
            cursor.execute(
                "UPDATE run_logs SET data = ? WHERE id = ?",
                (run_log.model_dump_json(), run_id),
            )
        else:
            log.warning("run_log_not_found", run_id=run_id)

        conn.commit()
        conn.close()

    def get_latest_run_log(self) -> RunLog | None:
        """Get the most recent run log."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data FROM run_logs ORDER BY started_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return RunLog.model_validate_json(row[0])
        return None

    def get_recent_run_logs(self, limit: int = 10) -> list[RunLog]:
        """Get the most recent run logs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data FROM run_logs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [RunLog.model_validate_json(row[0]) for row in rows]

    def save_eval_result(self, result: EvalResult) -> None:
        """Save an evaluation result."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO eval_results (run_at, data) VALUES (?, ?)",
            (result.run_at.isoformat(), result.model_dump_json()),
        )

        conn.commit()
        conn.close()

    def get_latest_eval(self) -> EvalResult | None:
        """Get the most recent evaluation result."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data FROM eval_results ORDER BY run_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return EvalResult.model_validate_json(row[0])
        return None


def get_archive():
    """
    Return the appropriate archive backend (S3 or SQLite).

    Uses S3 if:
    - USE_S3_ARCHIVE=true in .env
    - Running on AWS Lambda (detected via AWS_LAMBDA_FUNCTION_NAME env var)
    - Running on AWS (detected via AWS_EXECUTION_ENV or AWS_REGION env vars)

    Otherwise uses SQLite (local development).
    """
    import os
    settings = get_settings()

    is_lambda = os.getenv("AWS_LAMBDA_FUNCTION_NAME")
    # App Runner and other AWS services set these environment variables
    is_aws_environment = bool(os.getenv("AWS_EXECUTION_ENV")) or bool(os.getenv("AWS_REGION"))

    if settings.use_s3_archive or is_lambda or is_aws_environment:
        from reportagent.storage.s3_archive import S3Archive
        return S3Archive()
    return Archive()
