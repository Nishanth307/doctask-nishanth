.PHONY: up down migrate revision lint format test logs run

up:
	docker compose up -d

down:
	docker compose down

migrate:
	cd backend && PYTHONPATH=. ../venv/bin/alembic upgrade head

lint:
	cd backend && ../venv/bin/ruff check app/

format:
	cd backend && ../venv/bin/black app/

test:
	cd backend && PYTHONPATH=. ../venv/bin/pytest

logs:
	docker compose logs -f

run:
	cd backend && PYTHONPATH=. ../venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000