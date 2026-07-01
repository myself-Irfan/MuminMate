# مؤمن MuminMate

Islamic chatbot that answers knowledge questions and provides spiritual guidance, rooted exclusively in Quran and authentic hadith. Three modes: **QA** (knowledge), **Spiritual** (guidance), **History** (prophets & companions).

Built with FastAPI · PostgreSQL + pgvector · Ollama (llama3.1:7b) · Server-Sent Events

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.13+ | |
| uv | latest | `brew install uv` |
| Docker | latest | for Postgres |
| Ollama | latest | `brew install ollama` |

---

## Quickstart

```bash
# 1. Clone and install deps
git clone <repo-url> && cd MuminMate
uv sync

# 2. Configure environment
cp .env.example .env
# Open .env and set SECRET_KEY:
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Start Postgres (port 5433, avoids conflict with local pg)
docker compose up -d

# 4. Run migrations
uv run alembic upgrade head

# 5. Pull Ollama models (one-time, ~5 GB)
bash ollama/pull.sh

# 6. Start the server
uv run uvicorn backend.main:app --reload --port 8080
```

App is at `http://localhost:8080`. API docs at `/docs` (Swagger) and `/redoc`.

---

## Running tests

```bash
# Start the test DB (port 5434)
docker compose -f docker-compose.test.yml up -d

# Run the full suite with coverage
uv run pytest --cov=backend --cov-report=term-missing
```

---

## Development commands

```bash
uv run alembic revision --autogenerate -m "description"  # new migration
uv run alembic upgrade head                              # apply migrations
uv run alembic downgrade -1                              # rollback one
uv run ruff check backend/                              # lint
uv run ruff format backend/                             # format
```

---

## API overview

All endpoints are under `/api/`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Create account |
| POST | `/api/auth/login` | — | Login, sets httpOnly cookies |
| POST | `/api/auth/refresh` | cookie | Rotate access + refresh tokens |
| POST | `/api/auth/logout` | cookie | Invalidate refresh token |
| GET | `/api/auth/me` | cookie | Current user info |
| GET | `/api/threads` | cookie | List threads *(Phase 2)* |
| POST | `/api/chat/stream` | cookie | SSE chat stream *(Phase 4)* |

### SSE event types (Phase 4)

```
event: token          data: {"content": "..."}
event: sources        data: {"sources": [{"ref": "Quran 2:255", "type": "quran"}]}
event: clarification  data: {"question": "...", "options": ["Full story", "His trials"]}
event: cache_hit      data: {"content": "...full cached answer..."}
event: done           data: {}
event: error          data: {"detail": "..."}
```

---

## Project structure

```
backend/
  config.py           Pydantic Settings (all values from .env, no silent defaults)
  database.py         AsyncEngine, Base, TimestampMixin, get_db
  limiter.py          shared slowapi Limiter
  logger.py           structlog JSON logging (stdout, cloud-friendly)
  tasks.py            background cleanup loop
  main.py             create_app() factory, lifespan, middleware
  routers.py          register_routers() — central router registration
  templates.py        Jinja2Templates instance
  middleware/
    logging_context.py  per-request structlog context + sanitized query params
  auth/               register · login · JWT cookies · lockout
  views/              server-rendered HTML pages (Jinja2)
  threads/            thread + message CRUD          (Phase 2)
  knowledge/          corpus chunks + query cache    (Phase 3)
  chat/               RAG pipeline · SSE stream      (Phase 4)
    strategies/       mode detect · prompt · cache   (Phase 4)
  tests/
alembic/              async migrations
static/               CSS and JS assets
templates/            Jinja2 HTML templates (base.html + page templates)
data/corpus/          raw Islamic text corpus        (Phase 3, gitignored)
ollama/pull.sh        pull llama3.1:7b + nomic-embed-text
docker-compose.yml          Postgres on :5433
docker-compose.test.yml     test DB on :5434
```

---

## Architecture notes

- **Repository pattern** — each domain has an ABC + SQLAlchemy implementation; service layer only talks to the ABC.
- **Strategy pattern** — mode detection, prompt building, cacheability, and clarification are all swappable strategies.
- **Facade pattern** — `ChatService.stream()` orchestrates RAG, caching, and SSE from a single entry point.
- **Self-contained** — view routers serve Jinja2 HTML; JS in those pages calls the JSON API. One deploy serves browser and mobile clients.
- **Structured logging** — structlog JSON to stdout; request context (method, path, user_id, IP) bound per request via middleware.
- **Token rotation** — refresh uses DELETE + INSERT (not UPDATE) for atomic rotation; prevents double-spend under concurrent requests.
- **Rate limiting** — slowapi (in-memory, per IP) + `login_attempts` table (per email, survives restarts).
- **Cleanup** — FastAPI lifespan background task; no pg_cron dependency.