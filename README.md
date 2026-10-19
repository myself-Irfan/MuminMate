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
| `DJANGO_PUBLIC_URL` | How users reach the site, `scheme://host[:port]` without a trailing slash; links in mail start here |
| `DJANGO_HTTPS` | `true` only when served over HTTPS (redirect + secure cookies) |
| `DJANGO_HSTS_SECONDS` | HSTS max-age; `0` locally, start production at `3600` |
| `DJANGO_SESSION_IDLE_MINUTES` | Log out after this long without a request (`180`) |
| `DJANGO_SESSION_ABSOLUTE_HOURS` | Log out this long after login, even if active (`12`); at least the idle value |
| `DJANGO_PASSWORD_RESET_TIMEOUT_HOURS` | Password reset and email verification links expire after this long (`72`); a change also applies to links already sent |
| `DJANGO_LOGGING` | Log level and format as one-line JSON: `console` locally, `json` in production (see Logging below) |
| `DJANGO_LOGIN_LIMITS` | Failed-login limits as one-line JSON (see Login limits below) |
| `DJANGO_EMAIL` | Mail server as one-line JSON (see Email below) |
| `DJANGO_EMAIL_HOST_USER` | Mail server login; empty when it needs none (Mailpit), else set with the password |
| `DJANGO_EMAIL_HOST_PASSWORD` | Mail server password; empty or set together with the user |
| `POSTGRES_DB` | Database name |
| `POSTGRES_USER` | Database user |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_HOST` | `localhost` from the host; the service name inside compose |
| `POSTGRES_PORT` | Host port mapped to the db container |
| `POSTGRES_POOL_TIMEOUT_SECONDS` | Wait for a pooled connection; keep below the readiness probe timeout (`5`) |
| `RABBITMQ_HOST` | Celery broker (RabbitMQ) host: `localhost` from the host; the service name inside compose |
| `RABBITMQ_PORT` | Host port mapped to the broker's AMQP port (`5673` locally, so a local RabbitMQ keeps 5672) |
| `RABBITMQ_USER` | Broker user, created by the container on first start |
| `RABBITMQ_PASSWORD` | Broker user's password; generate with the command in `.env.example` |
| `RABBITMQ_VHOST` | Broker virtual host (RabbitMQ's isolation unit; `muminmate`) |

## Commands

| Command | Does |
|---|---|
| `make up` | Start the database, RabbitMQ and Mailpit (for `make run`, `make worker` and `make test`) |
| `make down` | Stop all containers |
| `make stack` | Build and run the production image (db, rabbitmq, mailpit, migrate, worker, web) on :8000 |
| `make run` | Start the dev server on :8000 (API docs at `/api/docs`) |
| `make worker` | Run the Celery worker in Docker, attached; rebuilds it when a file changes (Compose Watch) |
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
| `/accounts/signup/` | Create a consumer account (public); always ends on `/accounts/signup/done/` |
| `/accounts/password-reset/` | Email a link to choose a new password (public); always ends on `/accounts/password-reset/done/` |
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

Staff add a user by email only, as an invite: staff never choose or see a user's password. The
account has no usable password until the user sets one from the invite email, so it can't log in
before that (the invite email arrives with email verification).

## Signup

`/accounts/signup/` says when an email already has an account ("An account with this email already
exists. Log in instead."), and nothing is saved or mailed. A race between two signups for one email
ends the same way: the loser gets the same message, never an error page. Signup isn't rate-limited yet
(1.9b).

After signup, the worker mails a link to confirm the address. The link opens a confirm page, and only
its button confirms, so mail scanners that open links change nothing. It stops working once used,
after `DJANGO_PASSWORD_RESET_TIMEOUT_HOURS`, or when the email changes, and every bad link gets the
same page. Logins aren't refused for unconfirmed emails yet (1.9b).

Email addresses are ASCII only, everywhere (signup, admin, `createsuperuser`, and a database
constraint): lookalike letters such as `ı` would otherwise make `ırfan@` a different account from
`irfan@`. This matches the HTML standard's valid email address; for an international domain, browsers
send (and users can type) its `xn--` form.

## Password reset

"Forgot your password?" on the login page opens `/accounts/password-reset/`. Every email gets the same
"check your email" page, whether or not an account exists, and the worker sends the mail. Only an
active consumer account with a password gets one; staff and superusers get nothing here (a superuser
resets a staff password in `/admin/`, and their own with `python manage.py changepassword`).

The link opens a page that first moves the token out of the address bar (Django keeps it in the
session), then asks for the new password. It stops working once used, after
`DJANGO_PASSWORD_RESET_TIMEOUT_HOURS`, or when the password changes or the user logs in. Setting a new
password logs out the account's other sessions, confirms the email if it wasn't yet (the link proved
the inbox), and clears that email's failed logins from that IP. It doesn't log the user in. Reset
requests aren't rate-limited yet (1.9b).

## Sessions

Logins use Django's database sessions. A session ends after `DJANGO_SESSION_IDLE_MINUTES` without a
request, and `DJANGO_SESSION_ABSOLUTE_HOURS` after login even if active (logging in again restarts
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
works unless someone keeps guessing. Unknown emails count too. A successful login (or password reset)
clears only that email's failures from that IP. IPv6 addresses count per `/64`.

Each failure stores a keyed hash of the email (never the email itself), the IP and the time. The hash is
keyed with `DJANGO_SECRET_KEY`, so rotating the key resets every email's failure count. IPs are
personal data, so `python manage.py deleteexpiredloginfailures` deletes rows older than the longest
window; in production run it as a scheduled job (a Kubernetes CronJob, every 15 minutes).

The client IP is `REMOTE_ADDR`. Behind a proxy or ingress, set uvicorn's `FORWARDED_ALLOW_IPS` to the
proxy's address so it reads `X-Forwarded-For`; never `*`, which lets clients choose their own IP.

## Logging

Every log line goes to stdout, from our code, Django and uvicorn alike, in the format `DJANGO_LOGGING`
picks. `console` is for reading in a terminal, `json` is for production, where a log collector reads
each line as fields:

```
console:  2026-10-14T16:05:36.682380Z [warning  ] request_finished               [django_structlog.middlewares.request] code=404 func_name=handle_response ip=127.0.0.1 lineno=162 request='GET /api/nope' request_id=6754f0c3-5840-4d44-8f8b-ae458c9d7fad user_id=None
json:     {"code": 404, "request": "GET /api/nope", "event": "request_finished", "ip": "127.0.0.1", "user_id": null, "request_id": "78d2927a-f9ba-4c56-a0a6-723619528a08", "logger": "django_structlog.middlewares.request", "level": "warning", "timestamp": "2026-10-14T16:05:36.684763Z", "func_name": "handle_response", "lineno": 162}
```

In `json`, an exception is a list of `{"exc_type", "exc_value", "frames", ...}`, one per exception in
the chain, never with local variables.

Each request logs `request_started` and `request_finished` (`request_failed` on a crash) with its
`request_id`, `user_id` and `ip`. Successful health probes are not logged; failing ones are, marked
`is_probe: true`.

- **Request ID:** send `X-Request-ID` (letters, digits, `.`, `_`, `-`, up to 128) or get a new one;
  either way it comes back in the response header and is on every line of that request. Quote it when
  reporting a problem. Other values are replaced, and a client's `X-Correlation-ID` is ignored, so
  clients can't write into the logs.
- **IP:** `REMOTE_ADDR`, so set uvicorn's `FORWARDED_ALLOW_IPS` behind a proxy (see Login limits); a
  client's own `X-Forwarded-For` is never trusted.
- **Masking:** values of keys that name a secret (`password`, `token`, `api_key`, `cookie`,
  `authorization`, …, in any spelling) and of such query-string parameters are logged as `***`.
  Tokens inside URL paths (email verification, password reset) are logged as `*****`, and those pages
  send `Referrer-Policy: same-origin` (the token goes to no other site). Our events carry ids, never
  emails or message text. An exception's message is logged as written and can include data from the
  database (a duplicate-key error names the email), so treat logs as personal data and restrict who
  can read them.

Auth events (each logged once, from wherever the decision is made; every line also has `request_id`,
and `ip` unless the worker logged it):

| Event | Level | Keys |
|---|---|---|
| `login_succeeded` | info | `user_id` |
| `login_failed` | warning | `reason` (`bad_credentials`, `throttled`), `email_digest`, `user_id` (`null` without an account, and always when throttled: no lookup) |
| `login_refused` | warning | `reason` (`privileged_account`: staff at the consumer login; `not_staff`: a consumer at the admin login), `user_id` |
| `logout_succeeded` | info | `user_id` |
| `session_expired` | info, warning when `login_time_missing` | `reason` (`absolute_age` with `session_age_seconds`, `login_time_missing`), `user_id` |
| `signup_succeeded` | info | `user_id` |
| `signup_refused` | info | `reason` (`email_taken`), `user_id` of the existing account |
| `signup_email_skipped` | info | `user_id` (worker: the account was deactivated or deleted before the mail went out) |
| `email_verified` | info | `user_id` (from a confirm link or a completed password reset) |
| `email_verification_refused` | warning | `user_id` (always `null`: a bad link names no account we can trust) |
| `password_reset_requested` | info | `user_id` (`null` when no eligible account matches: unknown, inactive or without a password) |
| `password_reset_refused` | warning | `reason` (`privileged_account`), `user_id` |
| `password_reset_completed` | info | `user_id` |
| `password_reset_email_skipped` | info | `user_id` (worker: the account is no longer eligible) |
| `signup_email_queue_failed`, `password_reset_email_queue_failed` | error | `user_id`; the broker couldn't be reached, so no mail was queued (traceback attached) |

`email_digest` is the same keyed hash the `login_failures` table stores, so many failures on one
address show up even when it has no account; the email itself is never logged. The pages look the
same whatever the outcome: only these lines tell a wrong password from throttling.

Reading logs: the `make run` terminal; `docker compose logs -f web` for `make stack`;
`kubectl logs -f deploy/<name>` (`--previous` after a crash) in Kubernetes. To see the production
format locally, set `"format":"json"` and pipe through `jq`. The app writes no log files (Twelve-Factor
XI): storing and searching logs is the platform's job.

## Background jobs

[Celery](https://docs.celeryq.dev) runs background work in a separate worker process, with RabbitMQ as
the broker. `make up` starts RabbitMQ (`127.0.0.1:5673`; its web UI at http://localhost:15673, log
in with the `.env` user). Run `make worker` next to `make run`: the worker runs in Docker and is
rebuilt when a file changes. Its logs stream there and in `docker compose logs -f worker`.
`make stack` runs a worker too. Run one worker at a time: they share the broker, so any of them could
take a task.

To debug a task with breakpoints, stop the Docker worker (`docker compose stop worker`) and run
`uv run celery -A config worker -Q default,email --pool solo` from your IDE: `solo` runs each task in that
process. Don't run the default pool on macOS: with Celery 5.6.3 and billiard 4.3 every task fails
there ([celery#10683](https://github.com/celery/celery/issues/10683), fixed in Celery 5.7).

- Each kind of task has its own queue (`email` for now), declared in `CELERY_TASK_QUEUES` and routed
  in `CELERY_TASK_ROUTES`, on one topic exchange (`tasks`). Celery also requires a `default` queue: it
  catches tasks without a route, and a test fails for any task that has none. The `worker` service
  consumes the light queues (`-Q default,email`); heavy ones get their own worker.
- Mail is sent by tasks (`send_signup_email`, `send_password_reset_email`): each retries temporary
  SMTP errors with growing, randomised waits (up to 5 times, about 12 minutes on average) and gives
  up at once on a refused address or a wrong login. Each attempt is limited to 60 seconds.
- Tasks take ids, never personal data, and are queued only after the transaction commits. A task
  runs again if its worker is killed or loses the broker mid-task, so every task must be safe to run
  twice; one whose process alone crashes (out of memory, say) is marked failed instead.
- Messages are JSON only, and task results aren't stored.
- Queues are quorum queues (RabbitMQ's durable, replicated type), and queuing a task waits until
  the broker has stored it. Tasks survive a broker restart (a volume keeps its data).
- Worker lines use the `DJANGO_LOGGING` format and level (`celery worker -l` is ignored). A task's
  lines carry its `task_id` and the `request_id` and `user_id` of the request that queued it
  (`task_enqueued`, `task_started`, `task_succeeded`, `task_failed`).
- Each worker sets `--concurrency` (Celery's default is one process per CPU the machine has, not
  the container's share); scale by running more workers.

Processes, all from the one image:

| Process | Command | Queues | Concurrency |
|---|---|---|---|
| web | `uvicorn config.asgi:application --host 0.0.0.0 --port 8000` | — | 1; scale by replicas |
| migrate | `python manage.py migrate --noinput` (one-shot, before web and workers) | — | — |
| worker | `celery -A config --quiet worker -Q default,email -n default@%h --concurrency 2` | `default`, `email` | 2; scale by replicas |

## Email

`DJANGO_EMAIL` is the mail server, as JSON on one line; expanded, the `.env.example` value is:

```json
{
  "host": "localhost",
  "port": 1025,
  "use_tls": false,
  "timeout_seconds": 10,
  "default_from_email": "MuminMate <no-reply@localhost>"
}
```

`use_tls` starts TLS on a plain connection (STARTTLS, usually port 587); `timeout_seconds` bounds a hung
server; `default_from_email` is what recipients see as the sender, and its domain must be authorized by
the provider (SPF/DKIM) or mail lands in spam. Unknown or missing keys stop the app at startup. The
login (`DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`) is separate because the password is a
secret; both are empty or both set.

Locally, [Mailpit](https://mailpit.axllent.org) catches every mail and delivers nothing: `make up`
starts it; read the inbox at http://127.0.0.1:8025. The worker sends the mail, so inside compose it
reaches Mailpit as `mailpit`. Tests never send mail (pytest-django uses Django's in-memory backend).

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
| `image` | builds the Docker image, scans it with Trivy (fails on fixable HIGH/CRITICAL), smoke-tests it (readiness, the login page and its static files, a worker answering a ping) |
| `load_test` | runs `load-tests/login.js` against that image; p95 table in the run summary, k6's HTML report as an artifact |
| `checks` | passes only if every job above passed; the one required check |

Actions are pinned to commit SHAs and images to digests. Dependabot proposes updates monthly, except
for images in the workflow itself (the ParadeDB and RabbitMQ services, Trivy, k6): bump those by hand.

## Look and feel

Server-rendered pages styled with [Pico CSS](https://picocss.com) 2.1.1 (classless, fluid) plus
`static/css/theme.css`: ivory, emerald and gold, with dark mode following the device. Headings use
Cormorant Garamond, Arabic uses Amiri (both from Fontsource 5.3.0). Everything is self-hosted under
`static/` (no CDN); licences sit next to each file. The logo is one variable, `--mm-logo` in `theme.css`
(`rub-el-hizb.svg`, `crescent.svg` or `slim-crescent.svg`); the browser-tab icon is
`static/img/favicon.svg`. Forms render through one field template, `templates/django/forms/field.html`
(label, input, then the hint and errors under it, as Pico styles them).

## Project layout

```
config/    settings, env, URL, API, admin site and Celery wiring
core/      cross-cutting: health checks, Problem+JSON errors, request ID, log processors and masking
users/     custom user model (email login, no username), manager, admin, signup, email verification,
           password reset, login/logout, session timeouts, login throttling, auth event logging
web/       server-rendered pages (home)
templates/ shared layout (base.html)
static/    CSS, fonts, logos (self-hosted, with licences)
tests/     mirrors the source tree
load-tests/ k6 load tests
```
