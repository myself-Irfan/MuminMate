.PHONY: run up down test lint format typecheck

run:
	uv run python manage.py runserver

up:
	docker compose up -d --wait

down:
	docker compose down

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy .
