.PHONY: run up down stack test lint format typecheck

run:
	uv run python manage.py runserver

up:
	docker compose up -d --wait db

down:
	docker compose down

stack:
	docker compose up -d --build --wait --remove-orphans

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
