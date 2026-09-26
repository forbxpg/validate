# The local stand of validate. `make` lists the targets.
# Settings and secrets: backend/.env (cp backend/.env.example backend/.env).

ENV_FILE ?= backend/.env
ENV_PATH := $(abspath $(ENV_FILE))

# Optional services: make dev WITH="grafana loki"; WITH=obs is all of them.
OPTIONAL := prometheus loki grafana glitchtip
WITH ?=
PROFILES := $(sort $(if $(filter obs,$(WITH)),$(OPTIONAL),$(WITH)))
UNKNOWN := $(filter-out $(OPTIONAL) obs,$(WITH))
ifneq ($(UNKNOWN),)
$(error Unknown WITH: $(UNKNOWN). Known: $(OPTIONAL) obs)
endif

# Mailpit joins the stand whenever APP_ENV=local.
APP_ENV := $(shell sed -n 's/^APP_ENV=//p' $(ENV_FILE) 2>/dev/null | tail -n 1)
MAIL_FILE := $(if $(filter local,$(APP_ENV)),-f infrastructure/compose.mail.yaml)

COMPOSE := VLD_ENV_FILE=$(ENV_PATH) docker compose -f infrastructure/compose.yaml $(MAIL_FILE) --env-file $(ENV_PATH)
UP := $(COMPOSE) $(foreach p,$(PROFILES),--profile $(p))
ALL := $(COMPOSE) --profile '*'

TEST_DATABASE_URL := postgresql+asyncpg://postgres:postgres@localhost:5452/postgres
TEST_REDIS_URL := redis://localhost:6399/15

.DEFAULT_GOAL := help
.PHONY: help env dev up down reset logs ps migrate build api-host test test-integration check urls

help:
	@printf '%s\n' \
		'make dev [WITH="..."]   the stand in the foreground, code synced into the containers' \
		'make up [WITH="..."]    the same in the background' \
		'make down               stop every container of the stand; volumes stay' \
		'make reset              stop and delete the volumes (initdb runs again)' \
		'make logs [S=api]       follow the logs of the stand or of one service' \
		'make ps                 containers of the stand' \
		'make migrate            run the migrator once more' \
		'make build              rebuild the images' \
		'make api-host           the API on the host with --reload, for a debugger' \
		'make test               unit tests' \
		'make test-integration   integration tests against the running stand' \
		'make check              ruff, basedpyright, import contracts, unit tests' \
		'' \
		'WITH: $(OPTIONAL), or obs for all. Mailpit runs when APP_ENV=local.'

env:
	@test -f $(ENV_FILE) || { \
		printf '%s\n' "$(ENV_FILE) is missing. Create it once:" \
			"  cp backend/.env.example backend/.env" >&2; \
		exit 1; }

urls:
	@printf '%s\n' \
		'API          http://localhost:8010  (health: /health, docs: /docs)' \
		'RabbitMQ UI  http://localhost:15692  (validate / validate)'
	@$(if $(MAIL_FILE),printf '%s\n' 'Mailpit      http://localhost:8035')
	@$(if $(filter prometheus,$(PROFILES)),printf '%s\n' 'Prometheus   http://localhost:9092')
	@$(if $(filter grafana,$(PROFILES)),printf '%s\n' 'Grafana      http://localhost:3002')
	@$(if $(filter loki,$(PROFILES)),printf '%s\n' 'Loki         http://localhost:3102  (read it in Grafana)')
	@$(if $(filter glitchtip,$(PROFILES)),printf '%s\n' 'GlitchTip    http://localhost:8036')

dev: env urls
	$(UP) up --build --watch

up: env
	$(UP) up --build --detach --wait
	@$(MAKE) --no-print-directory urls WITH="$(WITH)"

down:
	$(ALL) down --remove-orphans

reset:
	$(ALL) down --volumes --remove-orphans

logs:
	$(ALL) logs --follow $(S)

ps:
	$(ALL) ps

migrate: env
	$(COMPOSE) run --rm migrator

build: env
	$(UP) build

api-host: env
	$(COMPOSE) stop api
	cd backend && uv run --env-file $(ENV_PATH) vld-api run --port 8010 --reload

test:
	cd backend && uv run pytest

test-integration:
	cd backend && TEST_DATABASE_URL=$(TEST_DATABASE_URL) TEST_REDIS_URL=$(TEST_REDIS_URL) \
		uv run pytest -m integration

check:
	cd backend && uv run ruff check . && uv run ruff format --check . \
		&& uv run basedpyright && uv run lint-imports && uv run pytest
