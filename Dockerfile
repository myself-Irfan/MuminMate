# A stage, not COPY --from=<image>: Dependabot only updates FROM lines.
FROM ghcr.io/astral-sh/uv:0.12.21@sha256:a7aed3216253ee804de3e2d8afa5073baa1a177335345d43845cd4165e43b711 AS uv

FROM python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b AS builder

COPY --from=uv /uv /bin/uv

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
    DJANGO_HTTPS=false DJANGO_HSTS_SECONDS=0 DJANGO_SESSION_IDLE_SECONDS=1 \
    DJANGO_SESSION_ABSOLUTE_SECONDS=1 POSTGRES_DB= POSTGRES_USER= \
    POSTGRES_PASSWORD= POSTGRES_HOST= POSTGRES_PORT=0 POSTGRES_POOL_TIMEOUT_SECONDS=1 \
    .venv/bin/python manage.py collectstatic --noinput

RUN .venv/bin/python -m compileall -q .

FROM python:3.13.15-slim-trixie@sha256:7c61056e61ac89e852de05f3dc6fa51a6dd2181797bceed46aa725dd7cb2cd3b

# Debian fixes land before the base image is rebuilt; pip is unused at runtime (uv installs).
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall --yes --root-user-action ignore pip

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app
COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
