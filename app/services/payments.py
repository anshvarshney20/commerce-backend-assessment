from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Campaign,
    CashbackTransaction,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Settlement,
)
from app.services.pricing import allocate_cashback, calculate_settlement, cashback_for_sequence


def _build_settlement_payload(order: Order, settlement: Settlement) -> dict:
    return {
        "order_id": order.order_code,
        "customer_price": settlement.customer_price,
        "platform_fee": settlement.platform_fee,
        "logistics_fee": settlement.logistics_fee,
        "seller_settlement": settlement.seller_amount,
    }


def pay_order(db: Session, order_code: str) -> dict:
    order = db.scalar(
        select(Order).where(Order.order_code == order_code).with_for_update()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status == OrderStatus.CANCELLED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order is cancelled")

    if order.status == OrderStatus.PAID:
        payment = order.payment
        settlement = order.settlement
        cashback_amount = order.cashback.amount if order.cashback else Decimal("0.00")
        if payment is None or settlement is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Paid order is missing payment or settlement records",
            )
        return {
            "order_id": order.order_code,
            "status": order.status.value,
            "payment_id": payment.id,
            "amount": payment.amount,
            "cashback": cashback_amount,
            "settlement": _build_settlement_payload(order, settlement),
            "already_processed": True,
        }

    if order.status != OrderStatus.PENDING_PAYMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order cannot be paid")

    cashback_amount = Decimal("0.00")
    if order.campaign_id is not None:
        campaign = db.scalar(
            select(Campaign).where(Campaign.id == order.campaign_id).with_for_update()
        )
        if campaign is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign not found")

        next_sequence = campaign.successful_order_count + 1
        tier = cashback_for_sequence(next_sequence)
        cashback_amount = allocate_cashback(tier, campaign.pool_remaining)

        campaign.successful_order_count = next_sequence
        campaign.pool_remaining = campaign.pool_remaining - cashback_amount

        db.add(
            CashbackTransaction(
                order_id=order.id,
                campaign_id=campaign.id,
                amount=cashback_amount,
                order_sequence=next_sequence,
            )
        )

        platform_fee_pct = campaign.platform_fee_pct
        logistics_fee = campaign.logistics_fee
    else:
        from app.config import get_settings

        settings = get_settings()
        platform_fee_pct = settings.platform_fee_pct
        logistics_fee = settings.logistics_fee

    platform_fee, logistics, seller_amount = calculate_settlement(
        order.price, platform_fee_pct, logistics_fee
    )

    payment = Payment(
        order_id=order.id,
        amount=order.price,
        status=PaymentStatus.SUCCESS,
        idempotency_key=f"pay-{order.order_code}",
    )
    settlement = Settlement(
        order_id=order.id,
        customer_price=order.price,
        platform_fee=platform_fee,
        logistics_fee=logistics,
        seller_amount=seller_amount,
    )
    order.status = OrderStatus.PAID

    db.add(payment)
    db.add(settlement)
    db.commit()
    db.refresh(order)
    db.refresh(payment)
    db.refresh(settlement)

    return {
        "order_id": order.order_code,
        "status": order.status.value,
        "payment_id": payment.id,
        "amount": payment.amount,
        "cashback": cashback_amount,
        "settlement": _build_settlement_payload(order, settlement),
        "already_processed": False,
    }


def get_settlement(db: Session, order_code: str) -> dict:
    order = db.scalar(select(Order).where(Order.order_code == order_code))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.settlement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settlement not found. Order must be paid first.",
        )
    return _build_settlement_payload(order, order.settlement)
