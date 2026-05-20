"""Pydantic schemas for all agent state, data models, and validation."""

import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


# ── Article (raw ingested content) ──────────────────────────────────────────

class Article(BaseModel):
    id: str = Field(default="")
    url: HttpUrl
    title: str
    raw_text: str
    cleaned_text: str
    source: str
    topic: str
    fetched_at: datetime
    published_at: Optional[datetime] = None
    word_count: int = 0

    def model_post_init(self, __context) -> None:
        if not self.id:
            url_str = str(self.url)
            date_str = str(self.published_at.date()) if self.published_at else ""
            content = f"{url_str}{date_str}".encode()
            self.id = hashlib.sha256(content).hexdigest()
        if not self.word_count:
            self.word_count = len(self.cleaned_text.split())


# ── Chunk (vector store unit) ────────────────────────────────────────────────

class Chunk(BaseModel):
    id: str = Field(default="")
    article_id: str
    text: str
    chunk_index: int
    embedding: Optional[list[float]] = None
    metadata: dict = Field(default_factory=dict)

    def model_post_init(self, __context) -> None:
        if not self.id:
            content = f"{self.article_id}{self.chunk_index}".encode()
            self.id = hashlib.sha256(content).hexdigest()


# ── Report (hourly output) ───────────────────────────────────────────────────

class Report(BaseModel):
    id: str
    topic: str
    generated_at: datetime
    summary: str
    key_takeaways: list[str] = Field(min_length=3, max_length=5)
    organisations_mentioned: list[str]
    key_terms: list[str]
    source_urls: list[HttpUrl]
    article_ids: list[str]
    delta_notes: Optional[str] = None
    run_id: str
    word_count: int = 0

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count < 80 or word_count > 180:
            raise ValueError(
                f"Summary must be 80-180 words. Got {word_count} words."
            )
        return v

    def model_post_init(self, __context) -> None:
        if not self.word_count:
            self.word_count = len(self.summary.split())


# ── CriticVerdict ────────────────────────────────────────────────────────────

class CriticVerdict(BaseModel):
    grounded: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    verdict: str
    reasoning: str


# ── ChatMessage ──────────────────────────────────────────────────────────────

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Citation(BaseModel):
    index: int
    url: HttpUrl
    title: str
    retrieved_at: datetime
    chunk_id: str


class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    citations: list[Citation] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── RunLog (scheduler + ingestion metadata) ──────────────────────────────────

class RunStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class RunLog(BaseModel):
    id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: RunStatus
    articles_fetched: int = 0
    articles_deduplicated: int = 0
    chunks_added: int = 0
    report_id: Optional[str] = None
    critic_iterations: int = 0
    error_message: Optional[str] = None


# ── EvalResult ───────────────────────────────────────────────────────────────

class EvalResult(BaseModel):
    run_at: datetime
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    num_questions: int
    num_failures: int
    failure_examples: list[dict] = Field(default_factory=list)


# ── Ingestion State ──────────────────────────────────────────────────────────

class IngestionState(BaseModel):
    run_id: str
    topic: str
    urls_to_fetch: list[str] = Field(default_factory=list)
    raw_pages: list[tuple[str, str, datetime]] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)
    new_chunks: list[Chunk] = Field(default_factory=list)
    previous_report: Optional[Report] = None
    draft_report: Optional[Report] = None
    critic_verdict: Optional[CriticVerdict] = None
    critic_iterations: int = 0
    errors: list[str] = Field(default_factory=list)
    processed_all_articles: bool = False


# ── Chat State ───────────────────────────────────────────────────────────────

class ChatState(BaseModel):
    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    current_query: str = ""
    sanitised_query: str = ""
    query_type: str = ""
    retrieved_chunks: list[Chunk] = Field(default_factory=list)
    latest_report: Optional[Report] = None
    response: Optional[ChatMessage] = None
    guardrail_triggered: bool = False
