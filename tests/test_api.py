import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://commerce:commerce@localhost:5432/commerce",
)

from app.config import get_settings
from app.db.session import Base, get_db
from app.main import app
from app.models import CashbackTransaction, Payment, Product, Settlement

get_settings.cache_clear()
settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def prepare_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE settlements, cashback_transactions, payments, "
                "orders, promotional_prices, campaigns, products "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_product(client: TestClient, stock: int = 10, minimum_price: str = "6800"):
    response = client.post(
        "/products",
        json={
            "name": "Running Shoes",
            "mrp": 9999,
            "selling_price": 7499,
            "minimum_price": float(minimum_price),
            "stock": stock,
            "gst_rate": 18,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_promo(client: TestClient, product_id: int):
    response = client.post(f"/products/{product_id}/price")
    assert response.status_code == 201, response.text
    return response.json()


def test_invalid_pricing_rejected(client: TestClient):
    response = client.post(
        "/products",
        json={
            "name": "Bad Product",
            "mrp": 9999,
            "selling_price": 7499,
            "minimum_price": 8000,
            "stock": 10,
            "gst_rate": 18,
        },
    )
    assert response.status_code == 422


def test_price_protection(client: TestClient):
    product = _create_product(client, minimum_price="6800")
    promo = _create_promo(client, product["id"])
    assert Decimal(str(promo["promotional_price"])) >= Decimal(str(promo["minimum_price"]))
    assert Decimal(str(promo["promotional_price"])) <= Decimal(str(promo["normal_price"]))


def test_cashback_across_order_counts(client: TestClient):
    product = _create_product(client, stock=20)
    promo = _create_promo(client, product["id"])
    promo_price = promo["promotional_price"]

    expected = {
        1: Decimal("100.00"),
        2: Decimal("100.00"),
        3: Decimal("100.00"),
        4: Decimal("200.00"),
        5: Decimal("200.00"),
        6: Decimal("200.00"),
        7: Decimal("300.00"),
        8: Decimal("300.00"),
        9: Decimal("300.00"),
        10: Decimal("200.00"),
    }

    for seq in range(1, 11):
        order = client.post(
            "/orders",
            json={
                "product_id": str(product["id"]),
                "quantity": 1,
                "promotional_price": promo_price,
            },
        )
        assert order.status_code == 201, order.text
        pay = client.post(f"/orders/{order.json()['order_id']}/pay")
        assert pay.status_code == 200, pay.text
        assert Decimal(str(pay.json()["cashback"])) == expected[seq]


def test_payment_idempotency(client: TestClient):
    product = _create_product(client, stock=5)
    promo = _create_promo(client, product["id"])
    order = client.post(
        "/orders",
        json={
            "product_id": str(product["id"]),
            "quantity": 1,
            "promotional_price": promo["promotional_price"],
        },
    ).json()

    first = client.post(f"/orders/{order['order_id']}/pay")
    second = client.post(f"/orders/{order['order_id']}/pay")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["payment_id"] == second.json()["payment_id"]
    assert second.json()["already_processed"] is True
    assert first.json()["cashback"] == second.json()["cashback"]
    assert first.json()["settlement"] == second.json()["settlement"]

    db = TestingSessionLocal()
    try:
        assert db.query(Payment).count() == 1
        assert db.query(CashbackTransaction).count() == 1
        assert db.query(Settlement).count() == 1
    finally:
        db.close()


def test_inventory_concurrency(client: TestClient):
    product = _create_product(client, stock=1)
    promo = _create_promo(client, product["id"])
    payload = {
        "product_id": str(product["id"]),
        "quantity": 1,
        "promotional_price": promo["promotional_price"],
    }

    def place_order():
        with TestClient(app) as threaded_client:
            return threaded_client.post("/orders", json=payload)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(place_order) for _ in range(2)]
        for future in as_completed(futures):
            results.append(future.result())

    statuses = sorted(r.status_code for r in results)
    assert statuses == [201, 409], [r.text for r in results]

    stock_check = TestingSessionLocal()
    try:
        remaining = stock_check.get(Product, product["id"]).stock
        assert remaining == 0
    finally:
        stock_check.close()
