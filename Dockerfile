# A stage, not COPY --from=<image>: Dependabot only updates FROM lines.
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

FROM python:3.13.17-slim-trixie@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS builder

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
    DJANGO_PUBLIC_URL=http://localhost \
    DJANGO_HTTPS=false DJANGO_HSTS_SECONDS=0 DJANGO_SESSION_IDLE_MINUTES=1 \
    DJANGO_SESSION_ABSOLUTE_HOURS=1 DJANGO_EMAIL_LINK_TIMEOUT_HOURS=1 \
    DJANGO_PASSWORD_RESET_LINK_TIMEOUT_MINUTES=1 DJANGO_EMAIL_CHANGE_LINK_TIMEOUT_MINUTES=1 \
    DJANGO_AUDIT_RETENTION_DAYS=1 \
    DJANGO_LOGGING='{"level":"INFO","format":"json"}' \
    DJANGO_THROTTLE_LIMITS='{"login":{"email_ip_max_events":1,"email_ip_window_seconds":1,"ip_max_events":1,"ip_window_seconds":1,"email_max_events":1,"email_window_seconds":2,"email_backoff_seconds":1},"password_reset":{"email_max_events":1,"email_window_seconds":2,"email_cooldown_seconds":1,"ip_max_events":1,"ip_window_seconds":1},"signup":{"ip_max_events":1,"ip_window_seconds":1},"verification_email":{"email_max_events":1,"email_window_seconds":2,"email_cooldown_seconds":1},"current_password":{"user_max_events":1,"user_window_seconds":1},"email_change":{"user_max_events":1,"user_window_seconds":2,"user_cooldown_seconds":1}}' \
    DJANGO_EMAIL='{"host":"collectstatic","port":25,"use_tls":false,"timeout_seconds":1,"default_from_email":"collectstatic","support_email":"collectstatic@example.com"}' \
    DJANGO_EMAIL_HOST_USER= DJANGO_EMAIL_HOST_PASSWORD= \
    POSTGRES_DB=collectstatic POSTGRES_USER=collectstatic \
    POSTGRES_PASSWORD=collectstatic POSTGRES_HOST=collectstatic POSTGRES_PORT=0 POSTGRES_POOL_TIMEOUT_SECONDS=1 \
    LOG_POSTGRES_DB=collectstatic LOG_POSTGRES_USER=collectstatic LOG_POSTGRES_PASSWORD=collectstatic \
    LOG_POSTGRES_HOST=collectstatic LOG_POSTGRES_PORT=0 \
    RABBITMQ_HOST=collectstatic RABBITMQ_PORT=0 RABBITMQ_USER=collectstatic RABBITMQ_PASSWORD=collectstatic \
    RABBITMQ_VHOST=collectstatic FORWARDED_ALLOW_IPS=127.0.0.1 \
    .venv/bin/python manage.py collectstatic --noinput

RUN .venv/bin/python -m compileall -q .

FROM python:3.13.17-slim-trixie@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962 AS runtime

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

# OWASP HTTP Headers: don't announce the server.
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
