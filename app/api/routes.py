from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    OrderCreate,
    OrderResponse,
    PaymentResponse,
    ProductCreate,
    ProductResponse,
    PromotionalPriceResponse,
    SettlementResponse,
)
from app.services import orders as order_service
from app.services import payments as payment_service
from app.services import products as product_service

router = APIRouter()


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> ProductResponse:
    product = product_service.create_product(
        db,
        name=payload.name,
        mrp=payload.mrp,
        selling_price=payload.selling_price,
        minimum_price=payload.minimum_price,
        stock=payload.stock,
        gst_rate=payload.gst_rate,
    )
    return ProductResponse.model_validate(product)


@router.post(
    "/products/{product_id}/price",
    response_model=PromotionalPriceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_promotional_price(product_id: int, db: Session = Depends(get_db)) -> PromotionalPriceResponse:
    promo = product_service.generate_promotional_price(db, product_id)
    return PromotionalPriceResponse(
        product_id=str(promo.product_id),
        normal_price=promo.normal_price,
        promotional_price=promo.promotional_price,
        minimum_price=promo.minimum_price,
        expires_at=promo.expires_at,
    )


@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> OrderResponse:
    order = order_service.create_order(
        db,
        product_id=int(payload.product_id),
        quantity=payload.quantity,
        promotional_price=payload.promotional_price,
    )
    return OrderResponse(
        order_id=order.order_code,
        status=order.status.value,
        product_id=str(order.product_id),
        quantity=order.quantity,
        price=order.price,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str, db: Session = Depends(get_db)) -> OrderResponse:
    order = order_service.get_order_by_code(db, order_id)
    return OrderResponse(
        order_id=order.order_code,
        status=order.status.value,
        product_id=str(order.product_id),
        quantity=order.quantity,
        price=order.price,
    )


@router.post("/orders/{order_id}/pay", response_model=PaymentResponse)
def pay_order(order_id: str, db: Session = Depends(get_db)) -> PaymentResponse:
    result = payment_service.pay_order(db, order_id)
    return PaymentResponse(**result)


@router.get("/orders/{order_id}/settlement", response_model=SettlementResponse)
def get_settlement(order_id: str, db: Session = Depends(get_db)) -> SettlementResponse:
    result = payment_service.get_settlement(db, order_id)
    return SettlementResponse(**result)
