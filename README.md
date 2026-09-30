# MuminMate

A grounded Quran and hadith assistant: every answer cites its sources, or says it couldn't find one.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker
- make

## Setup

```bash
uv sync
cp .env.example .env   # fill in the secrets; DJANGO_DEBUG=true locally
make up
uv run python manage.py migrate
uv run python manage.py check
```

## Configuration

Every variable is required; the app refuses to start if one is missing.

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Signing key. Generate with the command in `.env.example` |
| `DJANGO_DEBUG` | `true` only for local development |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames the app serves |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_HOST` | `localhost` from the host; the service name inside compose |
| `POSTGRES_PORT` | Host port mapped to the db container |

## Commands

| Command | Does |
|---|---|
| `make up` / `make down` | Start / stop the database |
| `make lint` | Lint and format check (what CI runs) |
| `make format` | Auto-fix lint and formatting |
| `make typecheck` | Type check (mypy, strict) |
