FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/

EXPOSE 8002

CMD ["uvicorn", "phoenix_runner.main:app", "--host", "0.0.0.0", "--port", "8002"]
