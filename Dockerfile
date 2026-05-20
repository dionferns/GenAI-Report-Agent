FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY evals/ evals/
COPY scripts/ scripts/

# Create data directories
RUN mkdir -p data/chroma data/archive logs

# Create Streamlit config for AWS
RUN mkdir -p ~/.streamlit
RUN echo "[server]" > ~/.streamlit/config.toml && \
    echo "headless = true" >> ~/.streamlit/config.toml && \
    echo "port = 8080" >> ~/.streamlit/config.toml && \
    echo "enableCORS = false" >> ~/.streamlit/config.toml

# Install package in editable mode
RUN pip install -e .

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port (App Runner expects 8080)
EXPOSE 8080

# Default: run Streamlit
CMD ["streamlit", "run", "src/reportagent/ui/app.py", "--server.port=8080", "--server.address=0.0.0.0"]
