FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Builder stage ──────────────────────────────────────────────────────────────
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --prefix=/install ".[otel-otlp]"

# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM base AS runtime

COPY --from=builder /install /usr/local
COPY vclaw/ ./vclaw/
COPY sdk/ ./sdk/
COPY main.py ./

# Non-root user for security
RUN useradd -r -u 1001 vclaw && chown -R vclaw:vclaw /app
USER vclaw

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
