# syntax=docker/dockerfile:1
# The migrator image. Built from backend/: docker build -f apps/migrator/Dockerfile .

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
    uv sync --frozen --no-dev --package vld-migrator --no-install-workspace

# The workspace packages install editable, so `docker compose watch` can sync code.
COPY alembic.ini ./
COPY packages/ packages/
COPY apps/ apps/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package vld-migrator


FROM python:${PYTHON_VERSION}-slim
# pg_dump of the server's major version: the migrator dumps the database before
# every upgrade in production.
ARG POSTGRES_MAJOR=18
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl --fail -sSo /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends "postgresql-client-${POSTGRES_MAJOR}" \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin vld
WORKDIR /app
COPY --from=builder --chown=vld:vld /app /app
USER vld
CMD ["vld-migrate", "upgrade"]
