from decimal import Decimal, ROUND_HALF_UP


def money(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def clamp_price(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    if value < minimum:
        return money(minimum)
    if value > maximum:
        return money(maximum)
    return money(value)


def calculate_promotional_price(
    selling_price: Decimal,
    minimum_price: Decimal,
    pool_amount: Decimal,
    target_orders: int,
) -> Decimal:
    if target_orders <= 0:
        raise ValueError("target_orders must be positive")
    discount_per_order = (pool_amount / Decimal(target_orders)).to_integral_value(
        rounding=ROUND_HALF_UP
    )
    candidate = selling_price - discount_per_order
    return clamp_price(candidate, minimum_price, selling_price)


def cashback_for_sequence(sequence: int) -> Decimal:
    if sequence <= 0:
        return money(0)
    if sequence <= 3:
        return money(100)
    if sequence <= 6:
        return money(200)
    if sequence <= 10:
        return money(300)
    return money(0)


def allocate_cashback(tier_amount: Decimal, pool_remaining: Decimal) -> Decimal:
    if pool_remaining <= 0:
        return money(0)
    return money(min(tier_amount, pool_remaining))


def calculate_settlement(
    customer_price: Decimal,
    platform_fee_pct: Decimal,
    logistics_fee: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    platform_fee = money(customer_price * platform_fee_pct / Decimal("100"))
    seller_amount = money(customer_price - platform_fee - logistics_fee)
    return platform_fee, money(logistics_fee), seller_amount
