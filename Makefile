.PHONY: setup dev lint format test migrate migration seed worker

setup:
	cd apps/api && uv sync && ([ -f .env ] || cp .env.example .env) && uv run alembic upgrade head
	cd apps/web && pnpm install && ([ -f .env.local ] || cp .env.example .env.local)

dev:
	@trap 'kill 0' INT TERM; \
	(cd apps/api && uv run uvicorn app.main:app --reload --port 8000) & \
	(cd apps/api && uv run python -m app.worker) & \
	(cd apps/web && pnpm dev) & \
	wait

worker:
	cd apps/api && uv run python -m app.worker

lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check .
	cd apps/web && pnpm lint && pnpm typecheck

format:
	cd apps/api && uv run ruff format . && uv run ruff check --fix .
	cd apps/web && pnpm format

test:
	cd apps/api && uv run pytest

migrate:
	cd apps/api && uv run alembic upgrade head

# The only way to create migrations: edit models, then `make migration m="..."`.
migration:
	cd apps/api && uv run alembic revision --autogenerate -m "$(m)"

seed: migrate
	cd apps/api && uv run python -m app.seed
