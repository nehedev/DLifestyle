# Dami's Lifestyle Services

*Your home, your comfort, our care.*

Web app for Dami's Lifestyle Services, a one-owner food and home-services business in Nigeria. Customers order made-to-order meals from a weekly menu (pickup or delivery) and pay online. They can also send requests for personal chef and catering, home cleaning, errand running, and home organization. The owner manages the menu, orders, and requests through admin endpoints.

## Repository layout

| Path | What it is |
| --- | --- |
| `frontend/` | Customer storefront: React, Vite, TypeScript |
| `backend/` | API: Python 3.13, FastAPI, PostgreSQL, Celery |
| `AGENTS.md` | Rules for coding agents working in this repo |
| `backend/AGENTS.md` | Backend rules, commands, and invariants |
| `backend/docs/spec.md` | The full backend specification |

The backend owns authentication verification, business rules, orders, payments, and persistence. The frontend consumes its API and never duplicates business rules.

## How it works

- **Menu:** each dish is served on specific weekdays. Orders are made to order, so there is no stock; items are active, hidden, or sold out.
- **Ordering:** a customer picks dishes, a fulfillment date, and delivery or pickup. The server computes the total (items plus a flat delivery fee) and checks the owner's order cutoff.
- **Payment:** Paystack hosted checkout. An order is marked paid only after a signed webhook is received and verified against Paystack's API.
- **Service requests:** customers describe what they need and the owner follows up. There is no online payment for services yet.
- **Owner:** an Auth0 `owner` role unlocks admin endpoints for the menu, services, orders, payments, service requests, and store settings (delivery fee, cutoff time, how far ahead people can order).
- **Sign-in:** Google through Auth0. The backend only verifies tokens.
- **Email:** Resend, always sent from background jobs.

## Tech stack

**Backend:** Python 3.13, uv, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL 17, Celery with Redis 7, Auth0, Paystack, Resend. Tests run against a real PostgreSQL database.

**Frontend:** React 19, Vite, TypeScript.

## Getting started

### Prerequisites

- Docker with Compose
- [uv](https://docs.astral.sh/uv/)
- Node.js 20 or newer

### Backend

All backend commands run from `backend/`.

```bash
cd backend
cp .env.example .env        # fill in the values; never commit .env
docker compose up --build   # api, worker, beat, postgres, redis
```

Apply migrations manually (they never run on startup), then seed the services and starting menu:

```bash
docker compose run --rm api uv run alembic upgrade head
uv run python scripts/seed_catalog.py
```

Run the checks:

```bash
docker compose up -d postgres   # tests need PostgreSQL and TEST_DATABASE_URL
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

Configuration is environment-only and has no defaults in code. The full list of settings is in `backend/docs/spec.md` section 12.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Build for production with `npm run build`.

## One-time setup outside the code

1. **Auth0:** create an API and a Google social connection. Add an Action that puts email, first name, last name, and roles into the access token as namespaced custom claims, and give the owner's account the `owner` role. The claim names go in the backend `.env`.
2. **Paystack:** set the webhook URL to `/api/v1/webhooks/paystack` on the backend and put the secret key in `.env`. Test in the sandbox first.
3. **Resend:** verify a sending domain and set the API key and sender address.
4. **Store settings:** after the first deploy, the owner sets the delivery fee, order cutoff time, and advance window through `PUT /admin/store-settings`. Ordering stays closed until she does.

## Status

- **Frontend:** the storefront shows the weekly menu and services with a cart. It currently sends orders to the owner through WhatsApp. Online payment, sign-in, and the owner dashboard are not built yet.
- **Backend:** built milestone by milestone from `backend/docs/spec.md`.

Not in V1: online payment for service requests (quotes and deposits), event availability calendar, guest checkout, portion limits, delivery fees by area, and image uploads. The full list is in `backend/docs/spec.md` section 14.

## Contributing

Read `AGENTS.md` first. Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, and so on), each one focused on a single change. Secrets, credentials, and `.env` files are never committed.