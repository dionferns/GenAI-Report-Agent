"""Pytest configuration and shared fixtures."""

import pytest
import tempfile
from pathlib import Path

from reportagent.config import Settings


@pytest.fixture
def temp_db():
    """Temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield str(Path(tmpdir) / "test.db")


@pytest.fixture
def temp_chroma_dir():
    """Temporary Chroma directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_settings(temp_db, temp_chroma_dir):
    """Test settings with temporary storage."""
    return Settings(
        llm_provider="anthropic",
        anthropic_api_key="test-key",
        sqlite_db_path=temp_db,
        chroma_persist_dir=temp_chroma_dir,
        log_file="/tmp/test.log",
    )
