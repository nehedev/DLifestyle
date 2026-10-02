# AGENTS.md — Ficmart Backend

Backend for Dami's Lifestyle Services, a one-owner food and home-services business in Nigeria. Customers order made-to-order meals from a weekly menu (pickup or delivery) and pay online; they also send service requests (catering, cleaning, errands, home organization). The owner runs the business through admin endpoints. FastAPI + async SQLAlchemy + Celery. Auth is Auth0 (verify-only). Payments are Paystack behind a provider abstraction.

Read this file fully before writing code. Everything about the data model, flows, API, settings, and tests is in `docs/spec.md`. If the two files disagree, stop and ask.

**Scope:** this file lives in `backend/` and covers the backend only. Every path and command in this file and in `docs/spec.md` is relative to `backend/`; run commands from that directory. Do not edit `frontend/` or the repository-root files from backend tasks. The root `AGENTS.md` also applies (Git, completion, and reporting rules); where this file is more specific, this file wins.

---

## 0. Rule zero: never assume on the owner's behalf

If something is not specified in this file or `docs/spec.md`, **stop and ask**.

- Do not fill gaps with your own defaults.
- Do not silently pick a value for a missing setting. Required settings have no default in code.
- Do not build anything listed under "Not in V1" in `docs/spec.md` section 14.

---

## 1. Commands

Run everything through `uv`. Never `pip install` or hand-edit `requirements.txt`. Commit `uv.lock`.

| Task | Command |
| --- | --- |
| Install | `uv sync` |
| Add dependency (ask first, see section 2) | `uv add <pkg>` / `uv add --dev <pkg>` |
| Start stack | `docker compose up --build` |
| Run API only (local) | `uv run uvicorn app.main:app --reload` |
| Worker | `uv run celery -A app.workers.celery_app worker --loglevel=info` |
| Beat | `uv run celery -A app.workers.celery_app beat --loglevel=info` |
| Start test database | `docker compose up -d postgres` |
| Tests (real PostgreSQL, needs `TEST_DATABASE_URL`) | `uv run pytest` |
| Lint | `uv run ruff check .` |
| Format check | `uv run ruff format --check .` |
| Type check | `uv run pyright` |
| New migration | `uv run alembic revision --autogenerate -m "<one logical change>"` |
| Apply migrations (manual, never on startup) | `docker compose run --rm api uv run alembic upgrade head` |
| Seed services and starting menu | `uv run python scripts/seed_catalog.py` |

CI runs Ruff, Pyright, and `pytest` against a PostgreSQL 17 service container.

---

## 2. Stack (fixed)

Python 3.13 (`requires-python = ">=3.13"`), uv, FastAPI, Pydantic v2 + pydantic-settings, SQLAlchemy 2.x async (`asyncpg`), Alembic (async template), PostgreSQL 17, Celery + Redis 7 (+ beat), Auth0, Paystack, Resend (HTTP API), httpx (async), pytest + pytest-asyncio + httpx, Ruff + Pyright (dev dependencies).

Docker Compose services: `api`, `worker`, `beat`, `postgres`, `redis`. Deployment is undecided: **do not add deployment config.**

**Ask before adding any framework or major library not listed above.**

---

## 3. Layout

```
app/
  main.py        # FastAPI app + lifespan
  core/          # settings, Auth0 token verification, logging
  db/            # engine, session, base, naming convention
  models/        # SQLAlchemy models
  schemas/       # Pydantic request/response models
  api/           # routers + dependencies, mounted under /api/v1
  services/      # business logic (menu, orders, payments, service requests). Own transactions.
  payments/      # PaymentProvider protocol + paystack.py
  emails/        # Resend client + templates
  workers/       # celery_app.py, tasks, beat schedule
alembic/
scripts/seed_catalog.py
tests/
docs/spec.md
docker-compose.yml
.env.example
pyproject.toml
uv.lock
```

- Routes are thin and call services. No business logic or raw SQL in routes.
- Services own transactions and business rules.
- Paystack-specific code lives **only** in `app/payments/paystack.py`.

---

## 4. Code conventions (checklist)

**Python**
- `datetime.now(UTC)` (`from datetime import UTC`). Never `utcnow()` / `utcfromtimestamp()`. All datetimes tz-aware, `TIMESTAMPTZ`.
- Built-in generics and `X | None`. Never `typing.List/Dict/Optional/Union`.
- PEP 695 (`type X = ...`, `def f[T]`, `class Repo[T]`). `StrEnum`, `typing.override`, `Self`.
- `asyncio.TaskGroup` / `asyncio.timeout()`. Never `get_event_loop()`, `run_until_complete`, `asyncio.coroutine`. `asyncio.run()` only at real entry points.
- `pathlib.Path`, not `os.path`.
- Money is never `float`.

**FastAPI**
- `lifespan`, never `@app.on_event`.
- `Annotated[..., Depends(...)]`, never bare `= Depends(...)`.
- `response_model` or return annotation on every route; `status.HTTP_*` constants.

**Pydantic v2 only**
- `model_validate`, `model_dump`, `ConfigDict`, `field_validator`, `model_validator`, `Field`. Never `.dict()`, `.parse_obj()`, `class Config`, `@validator`, `orm_mode`.
- Settings via `BaseSettings` + `SettingsConfigDict`. Secrets from environment only.

**SQLAlchemy 2.x**
- `DeclarativeBase`, `Mapped[...]`, `mapped_column`. Never `declarative_base()`, bare `Column`, or `session.query`.
- `select()` / `update()` / `delete()` with `await session.execute(...)` or `session.scalars(...)`.
- `create_async_engine`, `async_sessionmaker`, `expire_on_commit=False`.
- `MetaData` naming convention for all constraints and indexes.
- No lazy loading in async code: use `selectinload` / `joinedload`.
- PostgreSQL is the only database. Use its types directly: `DateTime(timezone=True)` (`TIMESTAMPTZ`) for every timestamp, `JSONB` for JSON.

**Celery**
- `@shared_task`, lowercase `app.conf` settings only.
- Tasks are synchronous and call `asyncio.run(_impl(...))` once. Worker engine uses `NullPool`.
- Every task is idempotent and retry-safe, with `acks_late=True` (all tasks), `autoretry_for`, exponential backoff, and a max retry count (`CELERY_TASK_MAX_RETRIES`, `CELERY_RETRY_BACKOFF_MAX_SECONDS`).
- Keep task wrappers thin. Tests call the async `_impl` functions directly.

---

## 5. Settings

All settings come from environment variables via pydantic-settings. **None has a default in code.** Example values live in `.env.example` (never commit `.env`). The full list is in `docs/spec.md` section 12. A missing setting fails startup. Do not invent a value.

---

## 6. Domain invariants (the ones you can break by accident)

1. Prices and item names are snapshotted onto `order_items`. Menu edits never change existing orders.
2. Totals (items plus delivery fee) are computed server-side. Client prices, fees, and totals are ignored.
3. An order is created only for a fulfillment date the menu serves, before that date's cutoff and within the advance window, with items that are active, not sold out, and served that weekday. The same check runs again at `/pay`. Dates and cutoffs use `BUSINESS_TIMEZONE`.
4. There is no stock. Nothing is reserved, counted, or released.
5. An order may have many payment attempts. Only one can move the order to `paid`; later successes become `needs_review`. An order never has more than one `succeeded` payment.
6. Payment success is accepted only after calling the gateway verify endpoint and matching status, amount, and currency.
7. Webhooks are at-least-once. Processing must be idempotent.
8. Money is integer minor units (kobo). Currency comes from settings and is snapshotted on orders and payments.
9. Card data is never stored. Only gateway references.
10. **Every state change on `orders`, `payments`, and `service_requests` is a conditional `UPDATE ... WHERE status = :expected`, with `rowcount` checked.** Anything not in the transition table (`docs/spec.md` section 4) is illegal.
11. A browser redirect or callback is never proof of payment. Only the verified gateway webhook is.
12. Never mark a payment `failed` because a gateway call failed or timed out. Leave it `initiated`.
13. Paystack sends no failure webhook. Only `charge.success` and `refund.*` events are acted on; every other event type is acknowledged and ignored.
14. Admin endpoints require the `owner` role taken from the verified token. Never trust a role from the request body, query, or headers.
15. Menu items and services are never deleted; they are deactivated.
---

## 7. Boundaries

**Always**
- Add tests with every change. Add a migration with every schema change.
- Use explicit timeouts on every external HTTP call (Auth0 JWKS, Paystack, Resend).
- Send email only from Celery tasks, with a deterministic Resend idempotency key.
- Log anomalies and manual-review events at `ERROR` using the stable event names in `docs/spec.md` section 9.

**Ask first**
- New library or framework, new table, new endpoint, new setting.
- Any change to the API contract the frontend consumes: paths, request or response shapes, status codes, or error `detail` strings. These must be coordinated with `frontend/`.
- Any value not given in the docs (timeouts, limits, intervals, thresholds).

**Never**
- Implement Google OAuth or any OAuth/OIDC flow in FastAPI. Auth0 is verify-only.
- Add `/register`, `/login`, or password fields.
- Add endpoints that are not listed in `docs/spec.md` section 6.
- Add a cart table (the cart is client-side), or any stock or inventory tracking.
- Auto-refund duplicate payments or amount/currency mismatches (they go to `needs_review`). Automatic refunds happen only for a late payment that cannot be fulfilled and for an owner cancellation of a paid order.
- Auto-retry a failed refund.
- Auto-link accounts by email.
- Add limits on items per order or quantity per item.
- Edit an applied or merged migration. Add a new one.
- Run manual DDL.
- Log secrets, tokens, webhook secrets, or full request bodies containing PII.
- Add deployment config, external alerting, or rate limiting.

---

## 8. Testing and definition of done

A change is done when `ruff check`, `ruff format --check`, `pyright`, and `pytest` all pass.

- Tests run against a **real PostgreSQL 17 database**. There is no SQLite anywhere in the project.
- `TEST_DATABASE_URL` is a test-only environment variable (listed in `.env.example`, not an app setting). It points to a dedicated test database that **must differ from `DATABASE_URL`**; the test setup refuses to run if they are equal. Locally it targets the Compose `postgres` service; in CI it targets a PostgreSQL 17 service container.
- Setup: create the test database if missing, build the schema once per session with `metadata.create_all`, and `TRUNCATE ... RESTART IDENTITY CASCADE` all tables between tests. Services commit for real, so do not wrap tests in an outer rolled-back transaction.
- Concurrency tests open separate sessions and run them concurrently (`asyncio.TaskGroup`), then assert on committed state.
- Override dependencies for the current user, payment provider, and Resend client (no real Auth0). Mock outbound HTTP with `httpx.MockTransport`. No real network calls. Redis is not needed in tests.
- Do not run Celery tasks eagerly in the pytest loop. Test the async `_impl` functions directly.
- Must-have test list: `docs/spec.md` section 11.

---

## 9. Git and reporting

Follow the root `AGENTS.md` for commits (Conventional Commits, focused commits, never push or rewrite history) and for the final report. Backend additions:

- Each commit is a working change: code + migration (if any) + tests.
- One logical change per migration; hand-review every autogenerated migration; real `downgrade()`.
- The final report states what changed, the checks performed (`ruff`, `pyright`, `pytest`), known limitations, and whether a migration was included.