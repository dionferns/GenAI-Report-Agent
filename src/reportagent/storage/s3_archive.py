"""S3-backed archive for reports and run logs."""

import json
import boto3
from datetime import datetime
from reportagent.config import get_settings
from reportagent.schemas import Report, RunLog, EvalResult
from reportagent.llm.aws_auth import get_aws_client
import structlog

log = structlog.get_logger()


class S3Archive:
    """
    S3-backed archive for reports, run logs, and evaluation results.

    Structure:
        reports/{topic}/{report_id}.json
        run_logs/{run_id}.json
        eval_results/{timestamp}.json
    """

    def __init__(self):
        settings = get_settings()
        self.bucket = settings.s3_bucket_name
        self.client = get_aws_client("s3")

    # ── Reports ──────────────────────────────────────────────────────────

    def save_report(self, report: Report) -> None:
        """Save a report to S3."""
        key = f"reports/{report.topic}/{report.id}.json"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=report.model_dump_json(),
            ContentType="application/json",
        )
        log.info("report_saved_to_s3", key=key, report_id=report.id)

    def get_latest_report(self, topic: str) -> Report | None:
        """Get the most recent report for a topic from S3."""
        try:
            prefix = f"reports/{topic}/"
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
            )

            objects = response.get("Contents", [])
            if not objects:
                return None

            # Most recently modified = latest report
            latest = max(objects, key=lambda o: o["LastModified"])
            obj = self.client.get_object(Bucket=self.bucket, Key=latest["Key"])
            data = obj["Body"].read().decode("utf-8")
            return Report.model_validate_json(data)
        except Exception as e:
            log.error("failed_to_get_latest_report_from_s3", error=str(e))
            return None

    def get_reports_since(self, topic: str, since: datetime) -> list[Report]:
        """Get all reports since a given timestamp from S3."""
        try:
            prefix = f"reports/{topic}/"
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
            )

            objects = response.get("Contents", [])
            reports = []
            for obj in objects:
                # Compare timestamps (S3 LastModified is timezone-aware)
                obj_time = obj["LastModified"].replace(tzinfo=None)
                if obj_time >= since:
                    body = self.client.get_object(
                        Bucket=self.bucket, Key=obj["Key"]
                    )
                    data = body["Body"].read().decode("utf-8")
                    reports.append(Report.model_validate_json(data))

            return sorted(reports, key=lambda r: r.generated_at, reverse=True)
        except Exception as e:
            log.error("failed_to_get_reports_since_from_s3", error=str(e))
            return []

    # ── Run Logs ──────────────────────────────────────────────────────────

    def save_run_log(self, run_log: RunLog) -> None:
        """Save a run log to S3."""
        key = f"run_logs/{run_log.id}.json"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=run_log.model_dump_json(),
            ContentType="application/json",
        )
        log.info("run_log_saved_to_s3", key=key, run_id=run_log.id)

    def get_latest_run_log(self) -> RunLog | None:
        """Get the most recent run log from S3."""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix="run_logs/",
            )
            objects = response.get("Contents", [])
            if not objects:
                return None

            latest = max(objects, key=lambda o: o["LastModified"])
            obj = self.client.get_object(Bucket=self.bucket, Key=latest["Key"])
            data = obj["Body"].read().decode("utf-8")
            return RunLog.model_validate_json(data)
        except Exception as e:
            log.error("failed_to_get_latest_run_log_from_s3", error=str(e))
            return None

    def get_recent_run_logs(self, limit: int = 10) -> list[RunLog]:
        """Get the N most recent run logs from S3."""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix="run_logs/",
            )
            objects = response.get("Contents", [])
            objects_sorted = sorted(
                objects, key=lambda o: o["LastModified"], reverse=True
            )[:limit]

            logs = []
            for obj in objects_sorted:
                body = self.client.get_object(Bucket=self.bucket, Key=obj["Key"])
                data = body["Body"].read().decode("utf-8")
                logs.append(RunLog.model_validate_json(data))
            return logs
        except Exception as e:
            log.error("failed_to_get_recent_run_logs_from_s3", error=str(e))
            return []

    def update_run_log(self, run_id: str, **kwargs) -> None:
        """Update a run log in S3."""
        try:
            key = f"run_logs/{run_id}.json"
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
            data = obj["Body"].read().decode("utf-8")
            run_log = RunLog.model_validate_json(data)

            # Update fields
            for key_name, value in kwargs.items():
                if hasattr(run_log, key_name):
                    setattr(run_log, key_name, value)

            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=run_log.model_dump_json(),
                ContentType="application/json",
            )
        except Exception as e:
            log.error("failed_to_update_run_log_in_s3", run_id=run_id, error=str(e))

    # ── Evaluation Results ────────────────────────────────────────────────

    def save_eval_result(self, result: EvalResult) -> None:
        """Save an evaluation result to S3."""
        key = f"eval_results/{result.run_at.isoformat()}.json"
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=result.model_dump_json(),
            ContentType="application/json",
        )
        log.info("eval_result_saved_to_s3", key=key)

    def get_latest_eval(self) -> EvalResult | None:
        """Get the most recent evaluation result from S3."""
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix="eval_results/",
            )
            objects = response.get("Contents", [])
            if not objects:
                return None

            latest = max(objects, key=lambda o: o["LastModified"])
            obj = self.client.get_object(Bucket=self.bucket, Key=latest["Key"])
            data = obj["Body"].read().decode("utf-8")
            return EvalResult.model_validate_json(data)
        except Exception as e:
            log.error("failed_to_get_latest_eval_from_s3", error=str(e))
            return None
