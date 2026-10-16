.PHONY: run worker up down stack test lint format typecheck

run:
	uv run python manage.py runserver

worker:
	docker compose up --build --watch worker

up:
	docker compose up -d --wait db rabbitmq

down:
	docker compose down

stack:
	docker compose up -d --build --wait --remove-orphans

test:
	uv run pytest --cov

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run mypy .
