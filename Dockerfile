FROM python:3.13.15-slim-trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY . .

# Placeholders: settings require every env var.
RUN DJANGO_SECRET_KEY=collectstatic DJANGO_DEBUG=false DJANGO_ALLOWED_HOSTS= \
    DJANGO_HTTPS=false DJANGO_HSTS_SECONDS=0 POSTGRES_DB= POSTGRES_USER= \
    POSTGRES_PASSWORD= POSTGRES_HOST= POSTGRES_PORT=0 \
    .venv/bin/python manage.py collectstatic --noinput

RUN .venv/bin/python -m compileall -q .

FROM python:3.13.15-slim-trixie

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
