# MuminMate

A grounded Quran and hadith assistant: every answer cites its sources, or says it couldn't find one.

CI (GitHub Actions) runs pre-commit, mypy, the migration check and the tests, then builds the Docker image and
smoke-tests it, on every PR.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Docker
- make

## Setup

```bash
uv sync
uv run pre-commit install
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
| `DJANGO_HTTPS` | `true` only when served over HTTPS (redirect + secure cookies) |
| `DJANGO_HSTS_SECONDS` | HSTS max-age; `0` locally, start production at `3600` |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_HOST` | `localhost` from the host; the service name inside compose |
| `POSTGRES_PORT` | Host port mapped to the db container |

## Commands

| Command | Does |
|---|---|
| `make up` | Start the database (for `make run` and `make test`) |
| `make down` | Stop all containers |
| `make stack` | Build and run the production image (db, migrate, web) on :8000 |
| `make run` | Start the dev server on :8000 (API docs at `/api/docs`) |
| `make lint` | Lint and format check |
| `make format` | Auto-fix lint and formatting |
| `make typecheck` | Type check (mypy, strict) |
| `make test` | Run the test suite |

## API

| Endpoint | Purpose |
|---|---|
| `/api/health/live` | Liveness: the process is up (no dependencies) |
| `/api/health/ready` | Readiness: database reachable and migrated, else `503` Problem+JSON |
| `/api/docs` | Interactive OpenAPI docs |

## Project layout

```
config/   settings, env, URL and API wiring
core/     cross-cutting: health checks, Problem+JSON errors
tests/    mirrors the source tree
```
