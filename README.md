# MuminMate

A grounded Quran and hadith assistant: every answer cites its sources, or says it couldn't find one.

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
uv run python manage.py createsuperuser   # logs in with email, no username
```

A database migrated before the custom user model (it has `auth_user`) must be recreated:
`docker compose down -v && make up`, then migrate. This deletes the local db data.

## Configuration

Every variable is required; the app refuses to start if one is missing.

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Signing key. Generate with the command in `.env.example` |
| `DJANGO_DEBUG` | `true` only for local development |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames the app serves |
| `DJANGO_HTTPS` | `true` only when served over HTTPS (redirect + secure cookies) |
| `DJANGO_HSTS_SECONDS` | HSTS max-age; `0` locally, start production at `3600` |
| `DJANGO_SESSION_IDLE_SECONDS` | Log out after this long without a request (`10800` = 3 h) |
| `DJANGO_SESSION_ABSOLUTE_SECONDS` | Log out this long after login, even if active (`43200` = 12 h); at least the idle value |
| `DJANGO_LOGIN_LIMITS` | Failed-login limits as one-line JSON (see Login limits below) |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_HOST` | `localhost` from the host; the service name inside compose |
| `POSTGRES_PORT` | Host port mapped to the db container |
| `POSTGRES_POOL_TIMEOUT_SECONDS` | Wait for a pooled connection; keep below the readiness probe timeout (`5`) |

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
| `make test` | Run the tests with coverage (fails below 95%) |

## Endpoints

| Endpoint | Purpose |
|---|---|
| `/api/health/live` | Liveness: the process is up (no dependencies; public) |
| `/api/health/ready` | Readiness: database reachable and migrated, else `503` Problem+JSON (public) |
| `/api/docs` | Interactive OpenAPI docs (staff only) |
| `/` | Home: shows who is logged in |
| `/accounts/login/` | Consumer login (staff and superuser accounts are refused; they use `/admin/`) |
| `/accounts/logout/` | Log out (POST only) |
| `/admin/` | Django admin (email login): staff manage consumer accounts; only superusers manage staff accounts and their privileges |

## Access

Deny by default. Every page requires login (Django's `LoginRequiredMiddleware`, extended in
`users/middleware.py`); a public page opts out with `@login_not_required`. Every API endpoint requires a
session (Ninja `django_auth`, CSRF-checked); a public router opts out with `auth=None` (only health).
Staff and superusers use separate accounts: every consumer page, public ones included, sends them to
`/admin/`, which has its own login and logout. A superuser must be staff (a database constraint).

## Passwords

Hashed with Argon2id. A password needs at least 8 characters, and is rejected if it's common, entirely
numeric or too similar to the email. `createsuperuser --noinput` (`DJANGO_SUPERUSER_PASSWORD`) skips
these checks, as Django does: choose a strong password.

## Sessions

Logins use Django's database sessions. A session ends after `DJANGO_SESSION_IDLE_SECONDS` without a
request, and `DJANGO_SESSION_ABSOLUTE_SECONDS` after login even if active (logging in again restarts
it). Activity refreshes the session at most every 5 minutes, so it can end up to 5 minutes before the
idle limit. With `DJANGO_HTTPS=true` the cookies are named `__Host-sessionid` and `__Host-csrftoken`.

## Login limits

`DJANGO_LOGIN_LIMITS` caps failed logins in sliding windows (seconds). Set it as JSON on one line;
expanded, the `.env.example` value is:

```json
{
  "email_ip": {"max_failures": 5, "window_seconds": 900},
  "ip": {"max_failures": 100, "window_seconds": 900},
  "email": {"max_failures": 20, "window_seconds": 3600, "backoff_seconds": 60}
}
```

`email_ip` is one email from one IP; `ip` is one IP for any email (loose, since mobile carriers share
IPs); `email` is one email from any IP, after which it gets one attempt per `backoff_seconds` instead
of a permanent lock. A targeted attacker spending each attempt from several IPs can still keep an
account in backoff. Every value must be a positive integer, and unknown or missing keys stop the app
at startup.

The limits apply to both logins (`/accounts/login/` and `/admin/`) and to `authenticate()` itself.
A refused attempt looks like a wrong password, skips the password check and isn't counted, so waiting
works unless someone keeps guessing. Unknown emails count too. A successful login clears only that
email's failures from that IP. IPv6 addresses count per `/64`.

Each failure stores a keyed hash of the email (never the email itself), the IP and the time. IPs are
personal data, so `python manage.py deleteexpiredloginfailures` deletes rows older than the longest
window; in production run it as a scheduled job (a Kubernetes CronJob, every 15 minutes).

The client IP is `REMOTE_ADDR`. Behind a proxy or ingress, set uvicorn's `FORWARDED_ALLOW_IPS` to the
proxy's address so it reads `X-Forwarded-For`; never `*`, which lets clients choose their own IP.

## Load tests

[k6](https://k6.io) scripts in `load-tests/`, run against `make stack`. `login.js` sends 20 logins a
second for one unknown email (throttled after a few, so they must skip the password hash), then 2 real
logins a second for a consumer account (each pays for Argon2). It fails if a p95 threshold or the error
rate is exceeded:

```sh
k6 run -e LOAD_BASE_URL=http://localhost:8000 -e LOAD_EMAIL=… -e LOAD_PASSWORD=… load-tests/login.js
```

`LOAD_EMAIL` must be a consumer account (staff are refused there). Watch memory with `docker stats`
alongside: Argon2 uses 100 MiB per hash. Each run records a few failures from your IP, so many runs
within 15 minutes trip the `ip` limit and valid logins fail: wait, or delete the `login_failures`
rows. CI runs `login.js` against the built image on every PR.

## CI

GitHub Actions runs these jobs on every PR, in parallel except `load_test`:

| Job | Does |
|---|---|
| `lint` | pre-commit (ruff, zizmor on the workflows, whitespace) and mypy |
| `audit` | pip-audit on the locked dependencies |
| `test` | migration check, tests with coverage (at least 95%), `check --deploy`; results in the run summary, JUnit and HTML coverage as an artifact |
| `image` | builds the Docker image, scans it with Trivy (fails on fixable HIGH/CRITICAL), smoke-tests it (readiness, the login page and its static files) |
| `load_test` | runs `load-tests/login.js` against that image; p95 table in the run summary, k6's HTML report as an artifact |
| `checks` | passes only if every job above passed; the one required check |

Actions are pinned to commit SHAs and images to digests. Dependabot proposes updates monthly, except
for images in the workflow itself (the ParadeDB service, Trivy, k6): bump those by hand.

## Look and feel

Server-rendered pages styled with [Pico CSS](https://picocss.com) 2.1.1 (classless, fluid) plus
`static/css/theme.css`: ivory, emerald and gold, with dark mode following the device. Headings use
Cormorant Garamond, Arabic uses Amiri (both from Fontsource 5.3.0). Everything is self-hosted under
`static/` (no CDN); licences sit next to each file. The logo is one variable, `--mm-logo` in `theme.css`
(`rub-el-hizb.svg`, `crescent.svg` or `slim-crescent.svg`); the browser-tab icon is
`static/img/favicon.svg`.

## Project layout

```
config/    settings, env, URL and API wiring
core/      cross-cutting: health checks, Problem+JSON errors
users/     custom user model (email login, no username), manager, admin, login/logout, session timeouts,
           login throttling
web/       server-rendered pages (home)
templates/ shared layout (base.html)
static/    CSS, fonts, logos (self-hosted, with licences)
tests/     mirrors the source tree
load-tests/ k6 load tests
```
