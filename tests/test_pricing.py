from decimal import Decimal

import pytest

from app.services.pricing import (
    allocate_cashback,
    calculate_promotional_price,
    calculate_settlement,
    cashback_for_sequence,
)


def test_promotional_price_never_below_minimum():
    price = calculate_promotional_price(
        selling_price=Decimal("7499"),
        minimum_price=Decimal("6800"),
        pool_amount=Decimal("2000"),
        target_orders=10,
    )
    assert price >= Decimal("6800")
    assert price <= Decimal("7499")
    assert price == Decimal("7299.00")


def test_promotional_price_clamps_when_discount_too_large():
    price = calculate_promotional_price(
        selling_price=Decimal("7499"),
        minimum_price=Decimal("7400"),
        pool_amount=Decimal("5000"),
        target_orders=10,
    )
    assert price == Decimal("7400.00")


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [
        (1, Decimal("100.00")),
        (3, Decimal("100.00")),
        (4, Decimal("200.00")),
        (6, Decimal("200.00")),
        (7, Decimal("300.00")),
        (10, Decimal("300.00")),
        (11, Decimal("0.00")),
    ],
)
def test_cashback_tiers(sequence: int, expected: Decimal):
    assert cashback_for_sequence(sequence) == expected


def test_cashback_pool_protection():
    assert allocate_cashback(Decimal("300"), Decimal("150")) == Decimal("150.00")
    assert allocate_cashback(Decimal("300"), Decimal("0")) == Decimal("0.00")


def test_settlement_example():
    platform_fee, logistics, seller = calculate_settlement(
        Decimal("6950"), Decimal("7"), Decimal("80")
    )
    assert platform_fee == Decimal("486.50")
    assert logistics == Decimal("80.00")
    assert seller == Decimal("6383.50")
