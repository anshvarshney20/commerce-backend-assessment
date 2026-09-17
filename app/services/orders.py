from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatus, Product
from app.services.products import get_active_promotional_price


def create_order(
    db: Session,
    *,
    product_id: int,
    quantity: int,
    promotional_price: Decimal,
) -> Order:
    product = db.scalar(
        select(Product).where(Product.id == product_id).with_for_update()
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    promo = get_active_promotional_price(db, product_id, promotional_price)

    if quantity > product.stock:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Out of stock")

    product.stock -= quantity
    order = Order(
        order_code=f"T{uuid4().hex[:15]}",
        status=OrderStatus.PENDING_PAYMENT,
        product_id=product.id,
        quantity=quantity,
        price=promo.promotional_price,
        promotional_price_id=promo.id,
        campaign_id=promo.campaign_id,
    )
    db.add(order)
    db.flush()
    order.order_code = f"ORD{1000 + order.id}"
    db.commit()
    db.refresh(order)
    return order


def get_order_by_code(db: Session, order_code: str) -> Order:
    order = db.scalar(select(Order).where(Order.order_code == order_code))
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
