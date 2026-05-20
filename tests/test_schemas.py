"""Tests for Pydantic schemas."""

import pytest
from datetime import datetime
from reportagent.schemas import (
    Article, Chunk, Report, ChatMessage, MessageRole, RunLog, RunStatus
)


def test_article_id_generation():
    """Test Article ID generation."""
    article = Article(
        url="https://example.com/article",
        title="Test Article",
        raw_text="<html>test</html>",
        cleaned_text="Test content",
        source="test_source",
        topic="uk_ai_regulation",
        fetched_at=datetime.utcnow(),
    )
    assert article.id is not None
    assert len(article.id) == 64  # SHA256 hex is 64 chars


def test_chunk_id_generation():
    """Test Chunk ID generation."""
    chunk = Chunk(
        article_id="test_article_123",
        text="Test chunk text",
        chunk_index=0,
    )
    assert chunk.id is not None
    assert len(chunk.id) == 64


def test_report_summary_validation():
    """Test Report summary word count validation."""
    # Valid summary (100-150 words)
    valid_summary = " ".join(["word"] * 120)

    report = Report(
        id="test_report",
        topic="uk_ai_regulation",
        generated_at=datetime.utcnow(),
        summary=valid_summary,
        key_takeaways=["Takeaway 1", "Takeaway 2", "Takeaway 3"],
        organisations_mentioned=["Org1"],
        key_terms=["term1"],
        source_urls=["https://example.com"],
        article_ids=["article1"],
        run_id="run1",
    )
    assert report.word_count == 120


def test_report_summary_too_short():
    """Test Report rejects summaries that are too short."""
    short_summary = " ".join(["word"] * 50)

    with pytest.raises(ValueError):
        Report(
            id="test_report",
            topic="uk_ai_regulation",
            generated_at=datetime.utcnow(),
            summary=short_summary,
            key_takeaways=["Takeaway 1", "Takeaway 2", "Takeaway 3"],
            organisations_mentioned=["Org1"],
            key_terms=["term1"],
            source_urls=["https://example.com"],
            article_ids=["article1"],
            run_id="run1",
        )


def test_report_key_takeaways_validation():
    """Test Report key_takeaways count validation."""
    valid_summary = " ".join(["word"] * 120)

    # Too few takeaways
    with pytest.raises(ValueError):
        Report(
            id="test_report",
            topic="uk_ai_regulation",
            generated_at=datetime.utcnow(),
            summary=valid_summary,
            key_takeaways=["Takeaway 1"],
            organisations_mentioned=["Org1"],
            key_terms=["term1"],
            source_urls=["https://example.com"],
            article_ids=["article1"],
            run_id="run1",
        )

    # Valid 3-5 takeaways
    report = Report(
        id="test_report",
        topic="uk_ai_regulation",
        generated_at=datetime.utcnow(),
        summary=valid_summary,
        key_takeaways=["Takeaway 1", "Takeaway 2", "Takeaway 3", "Takeaway 4"],
        organisations_mentioned=["Org1"],
        key_terms=["term1"],
        source_urls=["https://example.com"],
        article_ids=["article1"],
        run_id="run1",
    )
    assert len(report.key_takeaways) == 4


def test_chat_message_creation():
    """Test ChatMessage creation."""
    message = ChatMessage(
        role=MessageRole.USER,
        content="Hello, how are you?",
    )
    assert message.role == MessageRole.USER
    assert message.content == "Hello, how are you?"
    assert isinstance(message.timestamp, datetime)


def test_run_log_creation():
    """Test RunLog creation."""
    run_log = RunLog(
        id="test_run_123",
        started_at=datetime.utcnow(),
        status=RunStatus.SUCCESS,
        articles_fetched=5,
        chunks_added=20,
    )
    assert run_log.id == "test_run_123"
    assert run_log.status == RunStatus.SUCCESS
    assert run_log.articles_fetched == 5
