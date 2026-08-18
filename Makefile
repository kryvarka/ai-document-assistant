.PHONY: dev dev-backend dev-frontend test test-backend test-frontend lint seed migrate migration eval docker-up docker-down clean help

help:
	@echo "Available commands:"
	@echo "  make dev          - Run both backend and frontend locally in development mode"
	@echo "  make dev-backend  - Run FastAPI backend with uvicorn reloader on port 8000"
	@echo "  make dev-frontend - Run Vite React frontend on port 5173"
	@echo "  make migrate      - Apply database migrations (alembic upgrade head)"
	@echo "  make migration m='msg' - Autogenerate a new migration revision"
	@echo "  make seed         - Seed the relational database with demo users"
	@echo "  make test         - Run backend (pytest) and frontend (vitest) test suites"
	@echo "  make lint         - Run ruff linter and formatting checks"
	@echo "  make eval         - Run RAG quality evaluation against the golden set (uses live API)"
	@echo "  make docker-up    - Build and start full stack (PostgreSQL + Backend + Frontend)"
	@echo "  make docker-down  - Stop all docker compose containers and volumes"

dev-backend:
	cd backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	$(MAKE) dev-backend & $(MAKE) dev-frontend

eval:
	cd backend && uv run python -m evals.run_eval

migrate:
	cd backend && uv run alembic upgrade head

migration:
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

seed:
	cd backend && uv run python -m src.scripts.seed

test-backend:
	cd backend && uv run pytest -v

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

lint:
	cd backend && uv run ruff check src/ tests/ evals/ && uv run ruff format --check src/ tests/ evals/
	cd frontend && npm run lint && npx tsc -b --noEmit

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf backend/chroma_data backend/uploads backend/docqa.db frontend/dist
