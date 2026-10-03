from pathlib import Path

import django_stubs_ext

from config.env import Env

# Runtime support for typed generics like `UserChangeForm[User]`.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent

env = Env()
SECRET_KEY = env.django_secret_key.get_secret_value()
DEBUG = env.django_debug
ALLOWED_HOSTS = env.django_allowed_hosts

SECURE_SSL_REDIRECT = env.django_https
# Probes call the pod over plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^api/health/"]
SESSION_COOKIE_SECURE = env.django_https
CSRF_COOKIE_SECURE = env.django_https
# `__Host-` cookies must be Secure, so plain names over local HTTP.
SESSION_COOKIE_NAME = "__Host-sessionid" if env.django_https else "sessionid"
CSRF_COOKIE_NAME = "__Host-csrftoken" if env.django_https else "csrftoken"
SESSION_COOKIE_AGE = env.django_session_idle_seconds
SESSION_ABSOLUTE_AGE = env.django_session_absolute_seconds
SECURE_HSTS_SECONDS = env.django_hsts_seconds
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.django_hsts_seconds > 0
# HSTS preload is near-irreversible and needs a real domain; revisit at release.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "ninja",
    "core",
    "users",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "users.middleware.SessionTimeoutMiddleware",
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
    }
}

AUTH_USER_MODEL = "users.User"
# Replaces ModelBackend; listing both lets throttled logins through.
AUTHENTICATION_BACKENDS = ["users.backends.ThrottledModelBackend"]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

LOGIN_LIMITS = env.django_login_limits

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
