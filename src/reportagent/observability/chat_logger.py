"""Chat session logging with local and S3 support."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import structlog

log = structlog.get_logger()


class ChatLogger:
    """Log detailed chat messages to local files and S3 (when deployed)."""

    def __init__(self, session_id: str, use_s3: bool = False):
        self.session_id = session_id
        self.use_s3 = use_s3
        self.start_time = time.time()

        # Local storage
        self.local_dir = Path(f"./data/chat_logs/{session_id}")
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.local_dir / "messages.jsonl"

        # S3 storage (if deployed)
        self.s3_client = None
        self.s3_bucket = None
        self.s3_prefix = None
        if use_s3:
            self._init_s3()

    def _init_s3(self):
        """Initialize S3 client for log uploads."""
        try:
            import boto3
            from reportagent.config import get_settings

            settings = get_settings()
            self.s3_client = boto3.client("s3", region_name=settings.aws_default_region)
            self.s3_bucket = settings.s3_bucket_name
            self.s3_prefix = f"chat-logs/{self.session_id}"
            log.info("s3_initialized_for_chat_logs", session_id=self.session_id, bucket=self.s3_bucket)
        except Exception as e:
            log.warning("s3_initialization_failed_for_chat", error=str(e))
            self.s3_client = None

    def log_message(
        self,
        message_id: str,
        user_message: str,
        assistant_response: str,
        retrieved_chunks_count: int,
        citations_count: int,
        model_used: str = "bedrock",
        latency_ms: float = 0.0,
        query_type: str = "general",
        topic: str = "uk_economy",
        retrieved_chunks: list = None,
        llm_prompt: str = None,
    ):
        """Log a complete chat exchange with metadata, prompt, and chunks."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
            "message_id": message_id,
            "event": "chat_message_completed",
            "user_input": user_message,
            "assistant_response": assistant_response,
            "retrieved_chunks_count": retrieved_chunks_count,
            "citations_count": citations_count,
            "model_used": model_used,
            "latency_ms": latency_ms,
            "query_type": query_type,
            "topic": topic,
        }

        # Write Markdown file (human-readable with full context)
        self._write_markdown(message_id, entry, retrieved_chunks, llm_prompt)

        # Upload to S3 if available
        if self.s3_client and llm_prompt:
            self._upload_to_s3_markdown(message_id, entry, retrieved_chunks, llm_prompt)

    def log_guardrail_triggered(self, message_id: str, reason: str, user_message: str):
        """Log when a guardrail blocks a message."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
            "message_id": message_id,
            "event": "guardrail_triggered",
            "reason": reason,
            "user_input": user_message,
        }

        self._write_local(entry)
        if self.s3_client:
            self._upload_to_s3(entry)

    def log_error(self, message_id: str, error_message: str, user_message: str):
        """Log when an error occurs during processing."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
            "message_id": message_id,
            "event": "chat_error",
            "error": error_message,
            "user_input": user_message,
        }

        self._write_local(entry)
        if self.s3_client:
            self._upload_to_s3(entry)

    def log_session_summary(self, messages_count: int, total_duration_sec: float, topics_discussed: list):
        """Log session summary at the end."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
            "event": "session_summary",
            "messages_count": messages_count,
            "total_duration_sec": total_duration_sec,
            "topics_discussed": topics_discussed,
        }

        self._write_local(entry)
        if self.s3_client:
            self._upload_to_s3(entry)

    def _write_markdown(self, message_id: str, entry: dict, retrieved_chunks: list = None, llm_prompt: str = None):
        """Write entry to markdown file with full context and prompt."""
        try:
            md_file = self.local_dir / f"{message_id}.md"
            with open(md_file, "w") as f:
                f.write(f"# Chat Message {message_id}\n\n")
                f.write(f"**Timestamp:** {entry['timestamp']}\n")
                f.write(f"**Query Type:** {entry.get('query_type', 'unknown')}\n")
                f.write(f"**Topic:** {entry.get('topic', 'unknown')}\n")
                f.write(f"**Latency:** {entry.get('latency_ms', 0):.2f}ms\n\n")

                f.write("## User Input\n\n")
                f.write(f"{entry['user_input']}\n\n")

                if llm_prompt:
                    f.write("## LLM Prompt Sent to Model\n\n")
                    f.write("```\n")
                    f.write(llm_prompt)
                    f.write("\n```\n\n")

                f.write("## Assistant Response\n\n")
                f.write(f"{entry['assistant_response']}\n\n")

                f.write("## Metadata\n\n")
                f.write(f"- **Retrieved Chunks:** {entry.get('retrieved_chunks_count', 0)}\n")
                f.write(f"- **Citations:** {entry.get('citations_count', 0)}\n")
                f.write(f"- **Model:** {entry.get('model_used', 'unknown')}\n")

        except Exception as e:
            log.error("markdown_chat_log_write_failed", error=str(e), session_id=self.session_id, message_id=message_id)

    def _write_local(self, entry: dict):
        """Write entry to local JSONL file."""
        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            log.error("local_chat_log_write_failed", error=str(e), session_id=self.session_id)

    def _upload_to_s3_markdown(self, message_id: str, entry: dict, retrieved_chunks: list = None, llm_prompt: str = None):
        """Upload markdown entry to S3."""
        if not self.s3_client:
            return

        try:
            md_content = f"# Chat Message {message_id}\n\n"
            md_content += f"**Timestamp:** {entry['timestamp']}\n"
            md_content += f"**Query Type:** {entry.get('query_type', 'unknown')}\n"
            md_content += f"**Topic:** {entry.get('topic', 'unknown')}\n"
            md_content += f"**Latency:** {entry.get('latency_ms', 0):.2f}ms\n\n"

            md_content += "## User Input\n\n"
            md_content += f"{entry['user_input']}\n\n"

            if llm_prompt:
                md_content += "## LLM Prompt Sent to Model\n\n"
                md_content += "```\n"
                md_content += llm_prompt
                md_content += "\n```\n\n"

            md_content += "## Assistant Response\n\n"
            md_content += f"{entry['assistant_response']}\n\n"

            md_content += "## Metadata\n\n"
            md_content += f"- **Retrieved Chunks:** {entry.get('retrieved_chunks_count', 0)}\n"
            md_content += f"- **Citations:** {entry.get('citations_count', 0)}\n"
            md_content += f"- **Model:** {entry.get('model_used', 'unknown')}\n"

            s3_key = f"{self.s3_prefix}/{message_id}.md"
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=md_content,
                ContentType="text/markdown",
            )
            log.debug("markdown_chat_log_uploaded_to_s3", session_id=self.session_id, s3_key=s3_key)
        except Exception as e:
            log.warning("s3_markdown_chat_log_upload_failed", error=str(e), session_id=self.session_id)

    def _upload_to_s3(self, entry: dict):
        """Upload entry to S3."""
        if not self.s3_client:
            return

        try:
            message_id = entry.get("message_id", "unknown")
            s3_key = f"{self.s3_prefix}/{message_id}.json"

            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=json.dumps(entry),
                ContentType="application/json",
            )
            log.debug("chat_log_uploaded_to_s3", session_id=self.session_id, s3_key=s3_key)
        except Exception as e:
            log.warning("s3_chat_log_upload_failed", error=str(e), session_id=self.session_id)

    def get_local_logs_path(self) -> Path:
        """Get path to local logs directory."""
        return self.local_dir