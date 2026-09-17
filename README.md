# Commerce Backend

FastAPI + PostgreSQL backend for product listing, promotional pricing, orders,
cashback, payments, and seller settlement.

## Architecture

```
HTTP -> FastAPI routes -> services -> SQLAlchemy -> PostgreSQL
```

- Routes handle request/response validation
- Services hold pricing, order, payment, and settlement logic
- Postgres row locks (`SELECT FOR UPDATE`) protect stock and campaign pool updates

## Setup

```bash
docker compose up -d
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

OpenAPI: http://localhost:8000/docs

Postman collection: [docs/postman_collection.json](docs/postman_collection.json)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/products` | Create product |
| POST | `/products/{id}/price` | Create promotional price |
| POST | `/orders` | Create order (reserves stock) |
| POST | `/orders/{id}/pay` | Pay order |
| GET | `/orders/{id}` | Get order |
| GET | `/orders/{id}/settlement` | Get settlement |

```json
POST /products
{
  "name": "Running Shoes",
  "mrp": 9999,
  "selling_price": 7499,
  "minimum_price": 6800,
  "stock": 10,
  "gst_rate": 18
}
```

## Pricing

```
discount = round(pool_amount / target_orders)
promo = clamp(selling_price - discount, minimum_price, selling_price)
```

Sample values (`pool=2000`, `target=10`, `selling=7499`, `min=6800`):

`7499 - 200 = 7299`

Promo price is always `>= minimum_price`.

## Inventory

`POST /orders` takes a `FOR UPDATE` lock on the product, checks stock, decrements it,
then inserts the order in the same transaction. Concurrent buyers on the last unit
serialize on the lock; the second request gets `409 Out of stock`.

## Cashback

Paid order sequence within a campaign:

| Orders | Cashback |
|--------|----------|
| 1–3 | 100 |
| 4–6 | 200 |
| 7–10 | 300 |

`cashback = min(tier_amount, pool_remaining)` so the pool cannot go negative.
With pool `2000`, tiers sum to `2100`, so order 10 gets `200` instead of `300`.

## Idempotency

`POST /orders/{id}/pay`:

1. Lock the order row
2. If already `PAID`, return existing payment / cashback / settlement
3. Else mark paid, allocate cashback, write payment + settlement in one transaction
4. Unique constraints on payment / cashback / settlement `order_id` block duplicates

## Settlement

```
platform_fee = round(price * 7%, 2)
seller = price - platform_fee - 80
```

For `6950`: fee `486.50`, logistics `80`, seller `6383.50`.

## Design notes

1. Stock is reserved when the order is created, not at payment time, so checkout races
   cannot oversell.
2. Used Postgres row locks instead of optimistic retries so the concurrency behavior
   is simple to reason about and test.

## Tests

```bash
pytest -q
```

Covers invalid pricing, min-price protection, cashback tiers + pool clamp,
payment idempotency, and concurrent stock=1 orders.

## AI USAGE

AI Tool:
Claude

What I used AI for:
Minor help — sanity-checking the cashback pool edge case and a second pair of
eyes on the concurrency test approach.

Which parts I designed myself:
Overall architecture, data model, APIs, pricing formula, stock reservation,
payment idempotency, settlement logic, and the bulk of the implementation/tests.

What I reviewed or changed after AI generation:
Verified suggested edge cases against the actual pool math and kept my own
locking/idempotency implementation.

One limitation/problem I identified in the AI-generated output:
It initially understated that tier cashback can exceed remaining pool on later
orders (tiers sum to 2100 vs pool 2000); I kept explicit min(tier, remaining)
clamping because of that.
