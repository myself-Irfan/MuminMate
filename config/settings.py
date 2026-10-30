from datetime import timedelta
from pathlib import Path

import django_stubs_ext
from csp.constants import NONE, SELF
from kombu import Queue

from config.env import Env
from config.logging_config import build_logging, configure_structlog

# Runtime support for typed generics like `UserChangeForm[User]`.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent

env = Env()
SECRET_KEY = env.django_secret_key.get_secret_value()
DEBUG = env.django_debug
# The broker URL holds a password Django's filter misses.
DEFAULT_EXCEPTION_REPORTER_FILTER = "core.debug.BrokerSafeExceptionReporterFilter"
ALLOWED_HOSTS = env.django_allowed_hosts

SECURE_SSL_REDIRECT = env.django_https
# Probes call the pod over plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^api/health/"]
SESSION_COOKIE_SECURE = env.django_https
CSRF_COOKIE_SECURE = env.django_https
# `__Host-` cookies must be Secure, so plain names over local HTTP.
SESSION_COOKIE_NAME = "__Host-sessionid" if env.django_https else "sessionid"
CSRF_COOKIE_NAME = "__Host-csrftoken" if env.django_https else "csrftoken"
SESSION_COOKIE_AGE = int(timedelta(minutes=env.django_session_idle_minutes).total_seconds())
SESSION_ABSOLUTE_AGE = int(timedelta(hours=env.django_session_absolute_hours).total_seconds())
# Each request saves the session, which restarts the idle timeout.
SESSION_SAVE_EVERY_REQUEST = True
SECURE_HSTS_SECONDS = env.django_hsts_seconds
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.django_hsts_seconds > 0
# HSTS preload is near-irreversible and needs a real domain; revisit at release.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
# Self-hosted, nothing inline; data: is Pico's SVG icons. Django 6.2 LTS: SECURE_CSP instead.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "img-src": [SELF, "data:"],
        "object-src": [NONE],
        "base-uri": [NONE],
        "form-action": [SELF],
        "frame-ancestors": [NONE],
    },
}

INSTALLED_APPS = [
    "config.apps.MuminMateAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.forms",
    "csp",
    "ninja",
    "django_structlog",
    "core",
    "users",
    "audit",
]

MIDDLEWARE = [
    "core.middleware.RequestIDMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
    "audit.middleware.AuditMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "csp.middleware.CSPMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "users.middleware.SessionTimeoutMiddleware",
    "users.middleware.AuthenticatedNoStoreMiddleware",
    "users.middleware.ConsumerLoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Lets templates/django/forms/ override Django's form templates.
FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.postgres_db,
        "USER": env.postgres_user,
        "PASSWORD": env.postgres_password.get_secret_value(),
        "HOST": env.postgres_host,
        "PORT": env.postgres_port,
        "OPTIONS": {"pool": {"timeout": env.postgres_pool_timeout_seconds}},
    },
    "log": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.log_postgres_db,
        "USER": env.log_postgres_user,
        "PASSWORD": env.log_postgres_password.get_secret_value(),
        "HOST": env.log_postgres_host,
        "PORT": env.log_postgres_port,
        "OPTIONS": {"pool": {"timeout": env.postgres_pool_timeout_seconds}},
        # Django's default makes it wait for default's test db, which a log-only run never creates.
        "TEST": {"DEPENDENCIES": []},
    },
}
DATABASE_ROUTERS = ["config.db_router.LogRouter"]
AUDIT_RETENTION_DAYS = env.django_audit_retention_days

CELERY_BROKER_URL = env.rabbitmq_url
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_DEFAULT_EXCHANGE = "tasks"
# Native delayed delivery skips direct exchanges: countdowns would hold a worker.
CELERY_TASK_DEFAULT_EXCHANGE_TYPE = "topic"
CELERY_TASK_DEFAULT_ROUTING_KEY = "task.default"
CELERY_TASK_QUEUES = [
    Queue("default", routing_key="task.#", queue_arguments={"x-queue-type": "quorum"}),
    Queue("email", routing_key="email.#", queue_arguments={"x-queue-type": "quorum"}),
    Queue("audit", routing_key="audit.#", queue_arguments={"x-queue-type": "quorum"}),
]
CELERY_TASK_ROUTES = {
    "users.tasks.send_verification_email": {"queue": "email", "routing_key": "email.verification"},
    "users.tasks.send_password_reset_email": {
        "queue": "email",
        "routing_key": "email.password_reset",
    },
    "users.tasks.send_invite_email": {"queue": "email", "routing_key": "email.invite"},
    "audit.tasks.record_incoming_event": {"queue": "audit", "routing_key": "audit.incoming"},
}
# A typo'd queue name fails at publish instead of creating a queue no worker reads.
CELERY_TASK_CREATE_MISSING_QUEUES = False
# RabbitMQ 4.3 refuses Celery's default control and event queues.
CELERY_CONTROL_QUEUE_EXCLUSIVE = True
CELERY_EVENT_QUEUE_EXCLUSIVE = True
# A blocked broker fails a publish in ~4 s, not hangs: the timeouts bound the channel close.
CELERY_BROKER_TRANSPORT_OPTIONS = {"confirm_publish": True, "read_timeout": 1, "write_timeout": 1}
CELERY_TASK_PUBLISH_RETRY = True
# One immediate retry on a new connection (a restarted broker), still bounded under an alarm.
CELERY_TASK_PUBLISH_RETRY_POLICY = {"max_retries": 1, "interval_start": 0}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Explicit per the Security guide: pickle can run code.
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_IGNORE_RESULT = True
# Acked after running, so a crash mid-task redelivers it: tasks must be idempotent.
CELERY_TASK_ACKS_LATE = True
# A killed child process (OOM, SIGKILL) is otherwise acked; quorum delivery-limit 20 bounds loops.
CELERY_TASK_REJECT_ON_WORKER_LOST = True
# Else the redelivered copy runs alongside this one.
CELERY_WORKER_CANCEL_LONG_RUNNING_TASKS_ON_CONNECTION_LOSS = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

AUTH_USER_MODEL = "users.User"
# Replaces ModelBackend; listing both lets throttled logins through.
AUTHENTICATION_BACKENDS = ["users.backends.ThrottledModelBackend"]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

THROTTLE_LIMITS = env.django_throttle_limits
# Django's name; it sets every email link's lifetime (all generators subclass its own).
PASSWORD_RESET_TIMEOUT = int(timedelta(hours=env.django_email_link_timeout_hours).total_seconds())
# HttpUrl renders a trailing "/"; links append reverse() paths.
PUBLIC_URL = str(env.django_public_url).rstrip("/")

EMAIL_HOST = env.django_email.host
EMAIL_PORT = env.django_email.port
EMAIL_USE_TLS = env.django_email.use_tls
EMAIL_TIMEOUT = env.django_email.timeout_seconds
DEFAULT_FROM_EMAIL = env.django_email.default_from_email
EMAIL_HOST_USER = env.django_email_host_user
EMAIL_HOST_PASSWORD = env.django_email_host_password.get_secret_value()

# With real users, add hashers first and never remove one: its hashes stop verifying.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = build_logging(env.django_logging)
configure_structlog()
# Its ipware trusts X-Forwarded-For; core.signals binds get_client_ip() instead.
DJANGO_STRUCTLOG_IP_LOGGING_ENABLED = False
DJANGO_STRUCTLOG_CELERY_ENABLED = True
