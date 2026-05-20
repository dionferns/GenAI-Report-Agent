.PHONY: help install run ingest chat eval test lint docker-build seed

help:
	@echo "Available targets:"
	@echo "  make install        Install dependencies with uv"
	@echo "  make run           Start scheduler (hourly ingestion) + Streamlit UI"
	@echo "  make ingest        Trigger one ingestion run immediately"
	@echo "  make chat          Launch Streamlit UI only"
	@echo "  make eval          Run RAGAS + custom evals"
	@echo "  make test          Run pytest suite"
	@echo "  make lint          Run ruff linter"
	@echo "  make docker-build  Build Docker image"
	@echo "  make seed          Populate vector store with sample articles"

install:
	uv sync

run:
	uv run python -m reportagent.scheduler &
	uv run streamlit run src/reportagent/ui/app.py

ingest:
	uv run python -c "from reportagent.scheduler import run_ingestion; run_ingestion()"

chat:
	uv run streamlit run src/reportagent/ui/app.py

eval:
	uv run python evals/run_ragas.py
	uv run python evals/run_summary_eval.py

test:
	uv run pytest tests/ -v --tb=short

lint:
	uv run ruff check src/ tests/ evals/

docker-build:
	docker-compose up --build

seed:
	uv run python scripts/seed_corpus.py
