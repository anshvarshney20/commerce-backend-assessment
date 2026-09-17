from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Campaign, Product, PromotionalPrice
from app.services.pricing import calculate_promotional_price


def create_product(
    db: Session,
    *,
    name: str,
    mrp: Decimal,
    selling_price: Decimal,
    minimum_price: Decimal,
    stock: int,
    gst_rate: Decimal,
) -> Product:
    product = Product(
        name=name,
        mrp=mrp,
        selling_price=selling_price,
        minimum_price=minimum_price,
        stock=stock,
        gst_rate=gst_rate,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def generate_promotional_price(db: Session, product_id: int) -> PromotionalPrice:
    settings = get_settings()
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(minutes=settings.campaign_duration_minutes)

    promo_amount = calculate_promotional_price(
        selling_price=product.selling_price,
        minimum_price=product.minimum_price,
        pool_amount=settings.campaign_pool_amount,
        target_orders=settings.campaign_target_orders,
    )

    if promo_amount < product.minimum_price:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Promotional price would violate minimum seller price",
        )

    campaign = Campaign(
        product_id=product.id,
        duration_minutes=settings.campaign_duration_minutes,
        target_orders=settings.campaign_target_orders,
        pool_amount=settings.campaign_pool_amount,
        pool_remaining=settings.campaign_pool_amount,
        platform_fee_pct=settings.platform_fee_pct,
        logistics_fee=settings.logistics_fee,
        starts_at=now,
        ends_at=ends_at,
        successful_order_count=0,
    )
    db.add(campaign)
    db.flush()

    promo = PromotionalPrice(
        product_id=product.id,
        campaign_id=campaign.id,
        normal_price=product.selling_price,
        promotional_price=promo_amount,
        minimum_price=product.minimum_price,
        expires_at=ends_at,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return promo


def get_active_promotional_price(
    db: Session, product_id: int, promotional_price: Decimal
) -> PromotionalPrice:
    now = datetime.now(timezone.utc)
    stmt = (
        select(PromotionalPrice)
        .where(
            PromotionalPrice.product_id == product_id,
            PromotionalPrice.promotional_price == promotional_price,
            PromotionalPrice.expires_at > now,
        )
        .order_by(PromotionalPrice.id.desc())
    )
    promo = db.scalars(stmt).first()
    if promo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promotional price is invalid or expired",
        )
    if promo.promotional_price < promo.minimum_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Promotional price is below minimum seller price",
        )
    return promo
