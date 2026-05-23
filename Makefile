.PHONY: help install run ingest chat eval test lint docker-build docker-push seed

help:
	@echo "Available targets:"
	@echo "  make install        Install dev dependencies (chromadb, evals, tests)"
	@echo "  make run           Start scheduler (hourly ingestion) + Streamlit UI"
	@echo "  make ingest        Trigger one ingestion run immediately"
	@echo "  make chat          Launch Streamlit UI only"
	@echo "  make eval          Run RAGAS + custom evals"
	@echo "  make test          Run pytest suite"
	@echo "  make lint          Run ruff linter"
	@echo "  make docker-build  Build Docker image (production, ~150MB)"
	@echo "  make docker-push   Build and push Docker image to ECR"
	@echo "  make seed          Populate vector store with sample articles"
	@echo ""
	@echo "Note: Docker uses requirements-prod.txt (minimal deps)"
	@echo "Local dev uses requirements.txt (includes chromadb, evals, tests)"

install:
	uv sync --extra eval

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

docker-push:
	@echo "Logging into ECR..."
	AWS_PROFILE=genai aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin 743808053008.dkr.ecr.eu-west-2.amazonaws.com
	@echo "Building image for linux/amd64 (AWS App Runner)..."
	docker buildx build --platform linux/amd64 -t genai-report-agent:latest .
	docker tag genai-report-agent:latest 743808053008.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent:latest
	docker tag genai-report-agent:latest 743808053008.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent:v1.0.0
	@echo "Pushing to ECR..."
	docker push 743808053008.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent:latest
	docker push 743808053008.dkr.ecr.eu-west-2.amazonaws.com/genai-report-agent:v1.0.0
	@echo "✅ Image pushed to ECR (latest + v1.0.0)"

seed:
	uv run python scripts/seed_corpus.py
