# Build stage: install production dependencies only
FROM python:3.11-slim AS builder

WORKDIR /app

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (changes less frequently, better caching)
COPY requirements-prod.txt ./

# Install production dependencies
RUN pip install --no-cache-dir --user --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --user -r requirements-prod.txt

# Copy source files after dependencies (they change more frequently)
COPY pyproject.toml .
COPY src/ src/

# Install package in editable mode so imports work
RUN pip install --no-cache-dir --user -e .

# Runtime stage: minimal image with only runtime dependencies
FROM python:3.11-slim

WORKDIR /app

# Set environment early (used by CMD)
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Copy only the installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy only source code needed at runtime
COPY src/ src/

# Create Streamlit config (pre-built, no runtime echo)
RUN mkdir -p ~/.streamlit
COPY .streamlit/config.toml ~/.streamlit/config.toml

# Expose port (App Runner expects 8080)
EXPOSE 8080

# Default: run Streamlit
CMD ["streamlit", "run", "src/reportagent/ui/app.py", "--server.port=8080", "--server.address=0.0.0.0"]
