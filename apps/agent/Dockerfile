# ==============================================================================
# Phoenix Agent - Python Orchestrator
# ==============================================================================

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies + Node.js
# Node.js is needed for `npx mcp-remote`
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy package metadata and source
# README.md is required by pyproject.toml during pip install
COPY pyproject.toml README.md ./
COPY src/ src/

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -e ".[dev]"

# Cloud Run uses PORT environment variable, default is 8080
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Run app
CMD ["sh", "-c", "uvicorn phoenix_agent.main:app --host 0.0.0.0 --port ${PORT:-8080}"]