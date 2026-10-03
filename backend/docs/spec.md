# Dami's Lifestyle Services: Backend Spec

The business: Dami's Lifestyle Services (tagline "Your home, your comfort, our care") is a one-owner business in Nigeria. It sells made-to-order meals from a weekly rotating menu, with pickup or delivery, paid online. It also takes requests for services: personal chef and catering, home cleaning, errand running, home organization, and anything else the owner adds. The owner runs everything through admin endpoints.

This file is the full backend specification. Anything not specified here or in `AGENTS.md` must be asked, not assumed.

---

## 1. Auth (Auth0)

- The frontend authenticates with Auth0 and sends `Authorization: Bearer <access_token>`.
- The backend **only verifies** tokens: RS256 signature via the tenant JWKS, plus `iss`, `aud`, `exp`. Settings: `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`.
- JWKS is cached with a TTL (`JWKS_CACHE_TTL_SECONDS`). The fetch must not block the event loop (async httpx or `asyncio.to_thread`) and has an explicit timeout (`JWKS_TIMEOUT_SECONDS`).
- `CurrentUser` dependency verifies the token and resolves the local `users` row by Auth0 `sub`.
- No `/register`, no `/login`, no password fields. Users sign in with Google via an Auth0 social connection; the backend is provider-agnostic. Do not implement any OAuth/OIDC flow in FastAPI.
- **Claims:** email, first name, last name, and roles arrive as namespaced custom claims added to the access token by an Auth0 Action. Settings: `AUTH0_EMAIL_CLAIM`, `AUTH0_FIRST_NAME_CLAIM`, `AUTH0_LAST_NAME_CLAIM`, `AUTH0_ROLES_CLAIM`. The backend never calls `/userinfo`.
  - Email and first name are required and non-empty. If either is missing or empty, return `401`.
  - Last name is optional. A missing or empty last-name claim is stored as `NULL`.
  - The roles claim is a list of role names. A missing roles claim means no roles (not an error).
  - `email_verified` is not required.
- **Owner role:** a user is the owner when the roles claim contains `owner`. Roles are read from each verified token and are not stored in the database. `OwnerUser` dependency: valid token plus `owner` role, otherwise `403`. Never accept a role from anything but the verified token.
- **Provisioning:** the `users` row is created lazily on the user's first authenticated request, inside `CurrentUser`. Use an insert that tolerates concurrent first requests (unique `auth0_sub`; on conflict, re-select). Only the request that actually inserted the row enqueues the welcome email, after commit.
- **Sync:** later authenticated requests sync email, first name, and last name from the verified token.
- **Email conflicts:** if a token's `sub` has no local row but its email already belongs to another user, or a sync would make an email collide with another user, return `409` with `detail` `"account_exists_use_existing_sign_in"`, log `user.email_conflict` at `ERROR`, and write nothing. Never auto-link accounts. The frontend sends the user to sign in with their original method.
- **Public endpoints** (no token): `GET /menu`, `GET /services`, `GET /store`, and `POST /webhooks/paystack` (authenticated by signature). Everything else requires a token. Customers must sign in to order or send a service request; the WhatsApp button on the site is the no-sign-in path.

---

## 2. Data model

Money is stored as **integers in minor units** (kobo). The single currency comes from settings (`CURRENCY`, a 3-letter code, `NGN`). Orders and payments snapshot the currency at creation. All timestamps are `TIMESTAMPTZ`; "business dates" and times are interpreted in `BUSINESS_TIMEZONE` (an IANA name such as `Africa/Lagos`, used through `zoneinfo`).

**users**: `id` (bigint PK), `auth0_sub` (unique, not null), `email` (unique, not null), `first_name` (not null), `last_name` (nullable), `created_at`. Every email addresses the user by `first_name`.

**menu_items**: `id`, `name`, `description` (nullable), `category` (text, not null), `image_url` (image URL, nullable), `image_alt` (image alt text, nullable), `price_minor` (int, >= 0), `is_active` (hidden from customers when false), `is_sold_out` (visible but not orderable when true), `created_at`, `updated_at`. Items are never deleted (orders reference them); the owner deactivates them.

**menu_item_days**: `menu_item_id` -> menu_items (cascade), `weekday` (smallint, ISO: 1 = Monday ... 7 = Sunday, `CHECK` between 1 and 7). Primary key `(menu_item_id, weekday)`. One item can be served on several days.

**services**: `id`, `name`, `description`, `is_active`, `sort_order` (int), `created_at`, `updated_at`. Never deleted; the owner deactivates.

**store_settings**: a single row (`id` is always 1, enforced by `CHECK (id = 1)`): `delivery_fee_minor` (int, >= 0), `order_cutoff_time` (time of day, in `BUSINESS_TIMEZONE`), `max_advance_days` (int, >= 0), `updated_at`. The row is created by the owner's first `PUT /admin/store-settings`. Until it exists, ordering is closed.

**orders**: `id`, `user_id` -> users, `status` (`pending | paid | preparing | ready | completed | cancelled`), `fulfillment_type` (`delivery | pickup`), `fulfillment_date` (date), `contact` (JSONB snapshot, see below), `notes` (nullable text), `items_total_minor`, `delivery_fee_minor` (snapshot; 0 for pickup), `total_minor` (items total + delivery fee), `currency`, `idempotency_key` (nullable string, max 255), `created_at`, `updated_at`. Index on `user_id`. Unique `(user_id, idempotency_key)`.

**order_items**: `id`, `order_id` -> orders (cascade), `menu_item_id` -> menu_items, `name` (snapshot), `quantity` (> 0), `unit_price_minor` (snapshot). Unique `(order_id, menu_item_id)`.

**payments**: `id`, `order_id` -> orders, `provider` (e.g. `paystack`), `reference` (unique; generated by us, sent to the gateway; also the idempotency key), `provider_transaction_id` (nullable), `amount_minor`, `currency`, `status` (`initiated | succeeded | failed | needs_review | refund_pending | refunded`), `created_at`, `updated_at`. Index on `order_id`. Unique `(provider, provider_transaction_id)` (PostgreSQL allows multiple NULLs). `needs_review` means money was received at the gateway but not applied to an order. An order may have many payment attempts; each payment belongs to exactly one order. An order never has more than one `succeeded` payment.

**service_requests**: `id`, `user_id` -> users, `service_id` -> services, `preferred_date` (nullable date), `location` (text), `details` (text), `contact_phone` (E.164), `status` (`requested | contacted | confirmed | completed | cancelled`), `quoted_amount_minor` (nullable int, >= 0; informational only), `owner_note` (nullable text), `created_at`, `updated_at`. Indexes on `user_id` and `status`.

**contact** (order snapshot, validated by Pydantic): `name` (required), `phone` (required, E.164), `address` (required when `fulfillment_type` is `delivery`, otherwise omitted or null). Free-text address; no postal code, no country field. Strings are trimmed, non-empty, max 255 characters.

**Length limits:** order `notes` max 1000 characters; service request `location` max 255 and `details` max 2000; menu item `category` max 255, `image_url` max 2048, and `image_alt` max 255.

Rules:
- Never store card data. Only gateway references.
- `total_minor` is computed server-side. Never trust a total, price, or fee from the client.
- Every timestamp column is `DateTime(timezone=True)`. Naive datetimes are never written.

---

## 3. System invariants

1. Prices and item names are snapshotted onto `order_items`. Changing the menu never changes an existing order.
2. Totals (items plus delivery fee) are computed server-side. Client-supplied prices and totals are ignored.
3. An order is created only for a fulfillment date the menu serves, before that date's cutoff, within the advance window, and only with items that are active, not sold out, and served on that weekday. The same check runs again at `/pay`.
4. There is no stock. Nothing is reserved, counted, or released.
5. An order may have multiple payment attempts. Only one payment can move an order to `paid`; later successful attempts become `needs_review`.
6. Payment success is accepted only after gateway verification.
7. Webhook delivery is at-least-once; processing is idempotent.
8. Card data is never stored.
9. Every status change is a conditional, forward-only transition (section 4).
10. Owner endpoints require the `owner` role from the verified token.

---

## 4. State transitions (forward-only, conditional)

Every transition is a conditional `UPDATE ... WHERE status = :expected` and checks `rowcount`. Anything not listed is illegal and rejected (`409`).

| Entity | Allowed transitions |
| --- | --- |
| order | `pending -> paid`; `pending -> cancelled` (expiry or customer); `cancelled -> paid` (late payment, only if the order can still be fulfilled, see 5.4); `paid -> preparing`; `preparing -> ready`; `ready -> completed`; `paid -> cancelled` and `preparing -> cancelled` (owner, triggers a refund, see 5.5) |
| payment | `initiated -> succeeded`; `initiated -> failed`; `initiated -> needs_review`; `initiated -> refund_pending` (late payment that cannot be fulfilled); `succeeded -> refund_pending` (owner cancelled a paid order); `refund_pending -> refunded`; `refund_pending -> needs_review` (refund failed). `needs_review -> succeeded` and `needs_review -> refunded` are manual resolutions (no code sets them). |
| service request | `requested -> contacted`; `requested -> cancelled`; `contacted -> confirmed`; `contacted -> cancelled`; `confirmed -> completed`; `confirmed -> cancelled` (owner only; customers can cancel only `requested` and `contacted`) |

**Can still be fulfilled** (used for late payments and `/pay`): the fulfillment date's cutoff has not passed, and every item in the order is still active, not sold out, and served on that date's weekday.

---

## 5. Core flows

All routes are mounted under `/api/v1`. Paths below are relative to that prefix.

### 5.1 Public storefront data

- `GET /menu`: all active items with `id`, `name`, `description`, `category`, `image_url`, `image_alt`, `price_minor`, `is_sold_out`, and `weekdays` (list of ISO weekday numbers). Response `{"items": [...]}`. Not paginated.
- `GET /services`: active services ordered by `sort_order`, with `id`, `name`, `description`. Response `{"items": [...]}`.
- `GET /store`: `delivery_fee_minor`, `order_cutoff_time` (`HH:MM`), `max_advance_days`, `currency`, `timezone`. If store settings have not been configured, return `503` with `detail` `"store_not_configured"`.

### 5.2 `POST /orders`: create an order

The cart lives client-side in browser storage; the backend has no cart tables. The client sends:

```json
{
  "items": [{"menu_item_id": 3, "quantity": 2}],
  "fulfillment_type": "delivery",
  "fulfillment_date": "2026-10-05",
  "contact": {"name": "Ada Obi", "phone": "+2348012345678", "address": "12 Example Street, Lekki"},
  "notes": "No pepper please"
}
```

The frontend converts local phone formats (for example `0708...`) to E.164 before sending.

1. If store settings are not configured, return `503` `"store_not_configured"`.
2. Validate input (Pydantic): contact, `fulfillment_type`, `fulfillment_date`, quantity > 0, no duplicate `menu_item_id`, address present for delivery. Malformed input returns `422`.
3. Check the date rules in `BUSINESS_TIMEZONE`: the date is not in the past, is at most `max_advance_days` ahead, and the current time is before the cutoff instant (`fulfillment_date` at `order_cutoff_time`). Otherwise `409` with `detail` `"ordering_closed_for_date"`.
4. Check the items: each exists, is active, is not sold out, and is served on the weekday of `fulfillment_date`. Otherwise `409` with a `detail` identifying the unavailable items.
5. Read current prices and names from the database, add the delivery fee (delivery only), and compute totals.
6. In one transaction insert the `pending` order and its `order_items`. No stock is touched.

There is no maximum on items per order or quantity per item. Unpaid pending orders are cancelled after `PENDING_ORDER_TIMEOUT_MINUTES` (5.5).

**Idempotency-Key.** `POST /orders` accepts an optional `Idempotency-Key` header (non-empty, max 255 characters) to stop double-click duplicates.
- Same user, same key, same payload (same items and quantities, fulfillment type and date, contact, notes): return the original order in the normal response shape.
- Same user, same key, different payload: return `422`.
- Concurrent requests with the same key: the unique `(user_id, idempotency_key)` constraint decides. The loser rolls back and returns the original order.
- No header: a normal create with no deduplication.

### 5.3 `POST /orders/{id}/pay`

1. The order must belong to the current user (another user's order returns `404`) and be `pending` (otherwise `409`).
2. The order must still be fulfillable by date rules (cutoff not passed). Otherwise `409` `"ordering_closed_for_date"`.
3. Create a `payments` row (`initiated`) with a new unique `reference`.
4. **Commit** the `initiated` payment row before making the external gateway call.
5. Call `PaymentProvider.initialize(...)`. For Paystack this is "initialize transaction" and returns an `authorization_url`.
6. Return the `authorization_url`. The frontend redirects the user to the hosted checkout page.
7. If initialization fails or times out, return `502` and leave the payment `initiated` (the gateway may have accepted it even if the response was lost). A later webhook resolves it.

`/pay` may be called again while the order is `pending`, even if an earlier payment is still `initiated`. Each call creates a new payment row with a new reference. The first payment to succeed marks the order `paid`. A later success after the order is already `paid` is a duplicate payment: set that payment to `needs_review`, with no automatic refund.

### 5.4 `POST /webhooks/paystack`: payment confirmation (critical path)

Payment is confirmed **only** by the gateway webhook, verified server-side. A browser redirect or callback is never proof of payment.

1. Read the **raw body**. Verify the `x-paystack-signature` header (HMAC-SHA512 of the raw body with the secret key) using a constant-time comparison. Invalid signature: `401`, no work, log `webhook.invalid_signature` at `WARNING`.
2. Parse into a normalized `PaymentEvent`. The Paystack adapter acts only on `charge.success`, `refund.processed`, `refund.failed`, and `refund.needs-attention`. `refund.pending` and `refund.processing` normalize to no-ops. **Every other event type** (disputes, transfers, subscriptions, invoices, customer identification, anything unknown) is acknowledged with `200`, not enqueued, and logged `webhook.event_ignored` at `INFO`. Paystack documents no webhook for failed or abandoned one-time charges, so the adapter never emits a payment-failed event.
3. Enqueue the Celery task `process_payment_event` with the normalized event and return `200` immediately. Never do heavy work in the webhook request. If enqueue fails, return `503` and log `webhook.enqueue_failed` at `ERROR` so the gateway retries. Webhook events are not persisted; idempotency is enforced by the payment/order state machine.

**Task `process_payment_event`, on `charge.success`:**

1. Call the gateway **verify** endpoint for the reference and check status, amount, and currency against our `payments` row. Mismatch: do not mark the order paid; set the payment to `needs_review` and log `payment.amount_mismatch` at `ERROR`. Unknown reference: log `payment.unknown_reference` at `ERROR`.
2. Idempotency: if the payment is already `succeeded`, do nothing.
3. In **one transaction**, branch on the order's current status:
   - `pending` (normal path): payment `succeeded`, order `pending -> paid`. A pending order is honored even if the cutoff passed after it was created, because it is still inside the pending hold.
   - `cancelled` (late payment, e.g. the hold expired or the customer cancelled first): if the order can still be fulfilled (section 4), payment `succeeded`, order `cancelled -> paid`, log `payment.late_reinstated` at `WARNING`. Otherwise keep the order `cancelled`, set the payment `initiated -> refund_pending`, enqueue `refund_payment`, log `payment.late_refund_pending` at `ERROR`.
   - `paid`, `preparing`, `ready`, `completed` (any status where another payment already won), or any other status: do not change the order; set the payment `needs_review`; log `payment.duplicate_needs_review` at `ERROR`.
4. After commit, when the order actually became `paid`, enqueue the customer order-confirmation email and the owner new-order email.

**Payment-failed handling** exists for gateways that emit a normalized payment-failed event; Paystack does not, so in practice it is exercised only by tests with fake events. If the payment is not `initiated`, do nothing. Otherwise, in one transaction, mark it `failed`; if the order is `pending`, also move `pending -> cancelled`; if the order is in any other status, leave it alone. After commit, enqueue the payment-failed email if the payment actually became `failed`, and the order-cancelled email if the order was cancelled.

**Task `refund_payment`:** calls `PaymentProvider.refund(reference=..., amount_minor=..., currency=...)` for a payment already in `refund_pending`. Retry is safe: the status transition happened once, and a gateway "already refunded/pending" response counts as success.

**Refund webhooks** arrive on the same endpoint and are matched to the payment by reference:
- `refund.processed`: `refund_pending -> refunded` (the order stays `cancelled`).
- `refund.failed` or `refund.needs-attention`: `refund_pending -> needs_review`, log `payment.refund_failed` at `ERROR`.
- `refund.pending` and `refund.processing`: change nothing.
- Never auto-retry a failed refund.

### 5.5 Cancelling orders

**Expiry.** Celery beat task `cancel_expired_orders` runs every `EXPIRY_JOB_INTERVAL_MINUTES` (5) and cancels `pending` orders older than `PENDING_ORDER_TIMEOUT_MINUTES` (15).
- Cancel with a conditional update (`WHERE status = 'pending'`) so it cannot race a webhook marking the order `paid`.
- Never cancel an order that has a `succeeded` payment.
- Do not pre-verify payments with the gateway at expiry.
- After commit, enqueue the order-cancelled email. Log `order.expired_cancelled` at `INFO`.
- Payments on an expired order stay `initiated`. A later `charge.success` follows the late-payment branch in 5.4.

**Customer cancel.** `POST /orders/{id}/cancel`: the order must belong to the current user and be `pending`. Conditional `pending -> cancelled`, then enqueue the cancelled email. Log `order.user_cancelled` at `INFO`. If a payment completes afterwards, the late-payment branch in 5.4 applies. A paid order cannot be cancelled by the customer; they contact the owner.

**Owner cancel.** `POST /admin/orders/{id}/status` with `cancelled`, allowed from `paid` or `preparing`. In **one transaction**: conditional order `paid|preparing -> cancelled`, and the order's `succeeded` payment `succeeded -> refund_pending` (both conditional; if either `rowcount` is wrong, roll back and return `409`). After commit, enqueue `refund_payment` and the order-cancelled email. Log `order.owner_cancelled` at `INFO`. The refund then follows the same webhook handling as above.

### 5.6 Service requests

Customers request a service and the owner follows up (usually by phone or WhatsApp). V1 has no online payment for services; any quote is informational.

- `POST /service-requests`: body `service_id` (must be an active service), `preferred_date` (optional, not in the past in `BUSINESS_TIMEZONE`), `location`, `details`, `contact_phone` (E.164). Creates a `requested` request. After commit, enqueue the customer "request received" email and the owner new-request email. Log `service_request.created` at `INFO`.
- `GET /service-requests` and `GET /service-requests/{id}`: the current user's requests only (another user's returns `404`).
- `POST /service-requests/{id}/cancel`: own request, only from `requested` or `contacted`. Conditional transition, otherwise `409`.
- Owner endpoints are in 5.7.

### 5.7 Owner (admin) endpoints

All under `/admin`, all require `OwnerUser` (`401` without a token, `403` without the `owner` role).

- **Orders:** `GET /admin/orders` (filters `status` and `fulfillment_date`; cursor paginated), `GET /admin/orders/{id}` (any user's order; payments include `id`, `reference`, `provider_transaction_id`, `status`, `amount_minor`, `currency`), `POST /admin/orders/{id}/status` with body `{"status": "preparing" | "ready" | "completed" | "cancelled"}`. Only the transitions in section 4 are accepted (`409` otherwise). Owner status changes send no email in V1.
- **Payments:** `GET /admin/payments` (filter `status`; cursor paginated) so `needs_review` and `refund_pending` payments are visible to the owner.
- **Menu:** `GET /admin/menu-items` (all items, including inactive), `POST /admin/menu-items`, `PATCH /admin/menu-items/{id}` (any of `name`, `description`, `category`, `image_url`, `image_alt`, `price_minor`, `weekdays`, `is_active`, `is_sold_out`). No delete. Price edits affect only new orders.
- **Services:** `GET /admin/services`, `POST /admin/services`, `PATCH /admin/services/{id}` (any of `name`, `description`, `is_active`, `sort_order`). No delete.
- **Service requests:** `GET /admin/service-requests` (filter `status`; cursor paginated), `GET /admin/service-requests/{id}`, `PATCH /admin/service-requests/{id}` (any of `status`, `quoted_amount_minor`, `owner_note`; status changes follow section 4).
- **Store settings:** `GET /admin/store-settings`, `PUT /admin/store-settings` (replaces `delivery_fee_minor`, `order_cutoff_time`, `max_advance_days`; creates the row if missing).

---

## 6. Endpoints

**Public:** `GET /menu`, `GET /services`, `GET /store`, `POST /webhooks/paystack`.

**Signed-in customer:** `GET /me`, `POST /orders`, `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/pay`, `POST /orders/{id}/cancel`, `POST /service-requests`, `GET /service-requests`, `GET /service-requests/{id}`, `POST /service-requests/{id}/cancel`.

**Owner:** the `/admin/...` endpoints in 5.7.

`scripts/seed_catalog.py` seeds the services and the starting menu (section 15) and is safe to run again.

### Read behavior

- `GET /orders` and `GET /orders/{id}` return only the current user's orders. Another user's order returns `404`. Order detail includes fulfillment fields, contact, notes, items (name, quantity, unit price), totals, and the order's payments, each with only `id`, `status`, `amount_minor`, `currency` (no reference, no provider details).
- `GET /me` returns `id`, `email`, `first_name`, `last_name` (nullable), and `is_owner`.

### Conventions

- Prefix `/api/v1`. Errors use FastAPI's default `{"detail": ...}`. No custom error envelope. Stable string codes in `detail` are listed where they are defined (`account_exists_use_existing_sign_in`, `store_not_configured`, `ordering_closed_for_date`).
- **Cursor pagination** on `GET /orders`, `GET /service-requests`, and the admin list endpoints. Query parameters `limit` (default 20, max 100) and `cursor`, plus the endpoint's filters, which the client repeats on every page. Cursors are opaque encoded keyset positions, never offsets. All lists sort by `(created_at DESC, id DESC)`. Response: `{"items": [...], "next_cursor": str | null}`. Invalid or expired cursor: `400`.

---

## 7. Payment provider abstraction

Paystack-specific code lives only in `app/payments/paystack.py`.

```python
class PaymentProvider(Protocol):
    name: str

    async def initialize(
        self,
        *,
        reference: str,
        amount_minor: int,
        currency: str,
        email: str,
        callback_url: str,
    ) -> InitializedPayment: ...
    async def verify(self, reference: str) -> VerifiedPayment: ...
    async def refund(
        self, *, reference: str, amount_minor: int, currency: str
    ) -> InitiatedRefund: ...
    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool: ...
    def parse_webhook(self, raw_body: bytes) -> PaymentEvent: ...
```

Services depend on the protocol and receive the provider via dependency injection. The provider is selected by `PAYMENT_PROVIDER`. Gateway events are normalized into our own `PaymentEvent` type (charge success, payment failed, refund events) so nothing outside the adapter knows Paystack payload shapes. `callback_url` comes from `PAYMENT_CALLBACK_URL`.

---

## 8. Email (Resend)

- Sent through Resend's HTTP API with async httpx, **inside Celery tasks only**. Never in a request handler.
- Credentials from settings (`RESEND_API_KEY`); sender on a domain verified in Resend (`EMAIL_FROM_ADDRESS`). Owner alerts go to `OWNER_NOTIFICATION_EMAIL`.
- Each email uses a deterministic Resend idempotency key derived from the email type and a stable entity ID; retries of the same logical email reuse it. No email-status columns or tables.

| Email | To | Trigger |
| --- | --- | --- |
| Welcome | Customer | First sign-in, when the lazy user row is created |
| Order confirmation | Customer | Order becomes `paid` |
| New order | Owner | Order becomes `paid` (includes fulfillment type, date, items, contact, notes) |
| Payment failed | Customer | Normalized payment-failed event (not emitted by Paystack) |
| Order cancelled | Customer | Cancelled by expiry, by the customer, or by the owner |
| Request received | Customer | Service request created |
| New service request | Owner | Service request created |

No order-status update, refund, or manual-review emails.

---

## 9. Logging

Stable event names. Never log secrets, tokens, or full bodies containing PII. No external alerting.

| Level | Events |
| --- | --- |
| ERROR | `payment.amount_mismatch`, `payment.unknown_reference`, `payment.duplicate_needs_review`, `payment.late_refund_pending`, `payment.refund_failed`, `payment.invalid_transition`, `webhook.enqueue_failed`, `user.email_conflict`, `email.send_failed` |
| WARNING | `webhook.invalid_signature`, `payment.late_reinstated` |
| INFO | `webhook.event_ignored`, `order.expired_cancelled`, `order.user_cancelled`, `order.owner_cancelled`, `service_request.created`, `user.provisioned` |

---

## 10. Migrations (Alembic)

- Async template. Import all models in `env.py`. Set `compare_type=True`.
- One logical change per migration. Review every autogenerated migration by hand.
- Never edit a migration that has been applied or merged. Add a new one.
- Real `downgrade()` functions. Schema changes only via models + Alembic, never manual DDL.
- Run against PostgreSQL in Docker Compose. Migrations run **manually**, not on API startup. Tests build their schema with `metadata.create_all`.

---

## 11. Testing plan

Setup rules (real PostgreSQL, `TEST_DATABASE_URL`) are in `AGENTS.md` section 8. Must-have tests:

- **Order creation:** totals computed server-side (items plus delivery fee, pickup has no fee), name and price snapshots, unchanged after the owner edits the menu item, contact validated (E.164 phone, address required only for delivery), duplicate or unknown or inactive or sold-out items rejected, item not served on the fulfillment weekday rejected, Sunday rejected, no quantity maximums.
- **Date rules:** past date, beyond `max_advance_days`, and after the cutoff each return `409 ordering_closed_for_date`; same-day order before the cutoff succeeds; business-timezone boundaries are respected; unconfigured store returns `503 store_not_configured`.
- **Idempotency-Key:** same key and payload returns the original order; different payload returns `422`; no header means no deduplication.
- **Public endpoints:** `GET /menu`, `/services`, `/store` work without a token and hide inactive entries; sold-out items appear flagged.
- **Pay:** `/pay` called twice creates two payments with distinct references; `/pay` after the cutoff is rejected; gateway failure returns `502` and leaves the payment `initiated`.
- **Webhooks:** signature rejection; ignored event types return `200` without enqueue; enqueue failure returns `503`; replay of `charge.success` changes nothing twice; amount or currency mismatch goes to `needs_review`.
- **Late payment:** on a cancelled order, reinstated when still fulfillable (and confirmation plus owner emails enqueued); refund started when the cutoff has passed or an item is now unavailable.
- **Duplicate payment** on an already-paid order goes to `needs_review`, with no refund called.
- **Refunds:** refund task calls the provider once; `refund.processed` sets `refunded`; `refund.failed` and `refund.needs-attention` set `needs_review`; replayed refund webhooks change nothing.
- **Cancellation:** user cancel and expiry each cancel once and replay is harmless; expiry never cancels an order with a `succeeded` payment; expiry racing a paid webhook; user cancel racing a webhook.
- **Owner order flow:** only the listed transitions are accepted; non-owner gets `403`, no token gets `401`; owner cancel of a paid order moves the order to `cancelled` and the payment to `refund_pending` atomically and starts one refund.
- **Owner catalog and settings:** menu and service create/patch work and never delete; weekday changes apply to new orders only; `PUT /admin/store-settings` creates then updates the single row.
- **Service requests:** create validates the service is active and the date is not past; customer sees only their own; customer cancel only from `requested` or `contacted`; owner transitions follow section 4; both emails enqueued once.
- **Users:** lazy creation yields one row under truly concurrent first requests and one welcome email; token without email or first-name claim rejected with `401`; missing or empty last name stored as `NULL`; email conflict returns `409` and writes nothing; roles claim sets `is_owner`.
- **Read API:** another user's order or request returns `404`; order detail payments expose only the four allowed fields.
- **Cursor pagination:** stable ordering, no duplicates or gaps across pages, filters honored, invalid cursor rejected.
- **Concurrency** (separate sessions run concurrently against PostgreSQL): concurrent same-key order creation yields one order; cancel racing payment confirmation ends in one consistent state; two simultaneous `charge.success` events for different payments on one order yield exactly one `paid` and one `needs_review`.

---

## 12. Settings (required, no defaults in code)

Values shown go in `.env.example`. `.env.example` also carries `TEST_DATABASE_URL`, which is read only by the test suite and is not an app setting.

| Setting | Purpose | Example value |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL async URL | per environment |
| `REDIS_URL` | Celery broker | per environment |
| `AUTH0_DOMAIN` | Tenant domain | per environment |
| `AUTH0_AUDIENCE` | API audience | per environment |
| `AUTH0_EMAIL_CLAIM` | Namespaced email claim | per environment |
| `AUTH0_FIRST_NAME_CLAIM` | Namespaced first-name claim | per environment |
| `AUTH0_LAST_NAME_CLAIM` | Namespaced last-name claim | per environment |
| `AUTH0_ROLES_CLAIM` | Namespaced roles claim (list of names) | per environment |
| `JWKS_CACHE_TTL_SECONDS` | JWKS cache TTL | `3600` |
| `JWKS_TIMEOUT_SECONDS` | JWKS fetch timeout | `5` |
| `CURRENCY` | 3-letter currency code | `NGN` |
| `BUSINESS_TIMEZONE` | IANA timezone for dates and the cutoff | `Africa/Lagos` |
| `PAYMENT_PROVIDER` | Provider selector | `paystack` |
| `PAYSTACK_SECRET_KEY` | API and webhook signature key | secret |
| `PAYSTACK_CONNECT_TIMEOUT_SECONDS` | Connect timeout | `5` |
| `PAYSTACK_TIMEOUT_SECONDS` | Total timeout | `10` |
| `PAYMENT_CALLBACK_URL` | Provider callback URL | per environment |
| `CORS_ORIGINS` | Allowed origins | per environment |
| `RESEND_API_KEY` | Resend credential | secret |
| `RESEND_CONNECT_TIMEOUT_SECONDS` | Connect timeout | `5` |
| `RESEND_TIMEOUT_SECONDS` | Total timeout | `10` |
| `EMAIL_FROM_ADDRESS` | Sender on a Resend-verified domain | per environment |
| `OWNER_NOTIFICATION_EMAIL` | Where owner alerts are sent | per environment |
| `PENDING_ORDER_TIMEOUT_MINUTES` | Unpaid order hold before expiry | `15` |
| `EXPIRY_JOB_INTERVAL_MINUTES` | Expiry beat interval | `5` |
| `CELERY_TASK_MAX_RETRIES` | Retry cap for all tasks | `5` |
| `CELERY_RETRY_BACKOFF_MAX_SECONDS` | Exponential backoff cap | `600` |

Business values the owner controls at runtime (delivery fee, cutoff time, advance window) are **not** settings; they live in `store_settings` and are changed through `PUT /admin/store-settings`.

---

## 13. Local dev (Docker Compose)

Services: `api`, `worker`, `beat`, `postgres` (PostgreSQL 17), `redis` (Redis 7). Env via `.env` (never committed); provide `.env.example`. `api`, `worker`, and `beat` share one image built with uv. Healthchecks on postgres and redis; `api`, `worker`, and `beat` wait on them. The same `postgres` service hosts the dedicated test database named in `TEST_DATABASE_URL` (see `AGENTS.md` section 8). No deployment config.

---

## 14. Not in V1 and known limitations

**Not built:**
- Online payment for service requests (quotes, deposits, balances), and any availability calendar or date blocking for events.
- Per-day portion limits, item options (such as choice of protein; customers use `notes`), and delivery fees that vary by area.
- Signed-out (guest) orders or service requests.
- Order-status, refund, and manual-review emails; WhatsApp or SMS notifications.
- Image uploads for menu items or galleries.
- Rate limiting, external alerting, deployment config.
- Limits on items per order or quantity per item.
- A refund recovery sweeper.

**Known limitations (accepted):**
- Emails, refund tasks, and confirmations are enqueued after commit. If an enqueue is lost, a payment can sit in `refund_pending` until the owner handles it manually. Nothing re-enqueues it in V1.
- Paystack sends no failure webhook, so abandoned or failed orders are cancelled only by expiry, and their payments stay `initiated`. A later `charge.success` is handled by the late-payment rules.
- Dispute (`charge.dispute.*`) events are ignored, so chargebacks are not visible to the backend.
- `is_sold_out` is a manual toggle; nothing resets it automatically.

**Before go-live:**
- Paystack sandbox: confirm no failure event exists beyond those documented, and confirm the gateway response when a refund has already been requested for a reference (the `refund_payment` task treats it as success).
- The owner must `PUT /admin/store-settings` (delivery fee, cutoff time, advance window) before ordering opens, and the Auth0 Action must add the `owner` role to her account.

---

## 15. Starting catalog (seed data)

`scripts/seed_catalog.py` creates these if missing. Prices are in kobo (naira x 100). Weekdays are ISO numbers.

**Services** (in order): Personal chef and catering; Home cleaning; Errand running; Home organization.

**Menu items:**

| Name | Price (NGN) | Weekdays | Category |
| --- | --- | --- | --- |
| Jollof rice + chicken | 3500 | Mon | Rice |
| Jollof rice + fried plantain | 2500 | Mon | Rice |
| Assorted moi moi | 1500 | Mon | Beans |
| Beans + fried plantain | 2500 | Tue | Beans |
| Beans + plantain + egg | 3000 | Tue | Beans |
| Jollof spaghetti + chicken | 3000 | Wed | Pasta |
| Spaghetti + egg | 2000 | Wed | Pasta |
| Noodles + egg | 2000 | Wed | Pasta |
| Fried rice + chicken | 3500 | Thu | Rice |
| Semo + egusi soup + protein | 3500 | Thu, Fri | Soups |
| Semo + vegetable soup + protein | 3500 | Thu | Soups |
| Amala + ewedu + protein | 3000 | Fri | Soups |
| White rice + stew + chicken | 3000 | Sat | Rice |