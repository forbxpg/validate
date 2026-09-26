# syntax=docker/dockerfile:1
# The worker image. Built from backend/: docker build -f apps/worker/Dockerfile .

ARG PYTHON_VERSION=3.13

FROM ghcr.io/astral-sh/uv:0.12.5 AS uv

FROM python:${PYTHON_VERSION}-slim AS builder

COPY --from=uv /uv /bin/uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first: a change of code does not reinstall them.
COPY pyproject.toml uv.lock ./
COPY --parents packages/*/pyproject.toml apps/*/pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package vld-worker --no-install-workspace

# The workspace packages install editable, so `docker compose watch` can sync code.
COPY alembic.ini ./
COPY packages/ packages/
COPY apps/ apps/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package vld-worker


FROM python:${PYTHON_VERSION}-slim

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin vld
WORKDIR /app
COPY --from=builder --chown=vld:vld /app /app
USER vld
ENV WORKER_METRICS_HOST=0.0.0.0
EXPOSE 9100
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9100/metrics', timeout=2)"]
CMD ["vld-worker"]
