"""Run-specific logging to data folder for debugging ingestion."""

import json
import os
from datetime import datetime
from pathlib import Path


class RunLogger:
    """Log detailed information about ingestion runs to a file in data folder."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
        self.log_file = Path(f"./data/run_logs/{run_id}.jsonl")

        # Only create directory on non-Lambda (local dev/App Runner)
        if not self.is_lambda:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

        self.events = []

    def log(self, event: str, **kwargs):
        """Log an event with structured data."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "run_id": self.run_id,
            "event": event,
            **kwargs,
        }
        self.events.append(entry)

        # Write immediately to file (only on local dev/App Runner)
        if not self.is_lambda:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def log_section(self, section_name: str):
        """Log a section header."""
        self.log("section_start", section=section_name)

    def log_planner(self, all_urls: int, urls_tried: list, urls_to_fetch: list, processed_all: bool):
        """Log planner node execution."""
        self.log(
            "planner_executed",
            total_available=all_urls,
            urls_tried_count=len(urls_tried),
            urls_tried=urls_tried,
            urls_to_fetch_count=len(urls_to_fetch),
            urls_to_fetch=urls_to_fetch,
            processed_all_articles=processed_all,
        )

    def log_fetcher(self, urls_requested: int, fetched_count: int, urls_fetched: list):
        """Log fetcher node execution."""
        self.log(
            "fetcher_executed",
            urls_requested=urls_requested,
            urls_fetched_count=fetched_count,
            urls_fetched=urls_fetched,
        )

    def log_cleaner(self, raw_pages: int, articles_extracted: int, article_titles: list):
        """Log cleaner node execution."""
        self.log(
            "cleaner_executed",
            raw_pages_count=raw_pages,
            articles_extracted=articles_extracted,
            article_titles=article_titles,
        )

    def log_deduper(self, input_articles: int, kept: int, skipped: int, article_ids: dict):
        """Log deduper node execution."""
        self.log(
            "deduper_executed",
            input_articles=input_articles,
            kept=kept,
            skipped=skipped,
            articles_checked={
                "kept": list(article_ids.get("kept", [])),
                "skipped": list(article_ids.get("skipped", [])),
            },
        )

    def log_loop_summary(self, loop_number: int, urls_fetched: int, articles_found: int, chunks_created: int, total_new_articles: int):
        """Log summary for each loop iteration."""
        self.log(
            "loop_completed",
            loop=loop_number,
            urls_fetched=urls_fetched,
            articles_found=articles_found,
            chunks_created=chunks_created,
            total_new_articles_so_far=total_new_articles,
        )

    def get_summary(self):
        """Return a human-readable summary of the run."""
        return "\n".join([json.dumps(e) for e in self.events])
