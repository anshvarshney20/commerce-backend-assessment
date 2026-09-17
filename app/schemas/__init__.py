from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    mrp: Decimal = Field(gt=0)
    selling_price: Decimal = Field(gt=0)
    minimum_price: Decimal = Field(ge=0)
    stock: int = Field(ge=0)
    gst_rate: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_price_ladder(self) -> "ProductCreate":
        if self.minimum_price > self.selling_price:
            raise ValueError("minimum_price must be <= selling_price")
        if self.selling_price > self.mrp:
            raise ValueError("selling_price must be <= mrp")
        return self


class ProductResponse(BaseModel):
    id: int
    name: str
    mrp: Decimal
    selling_price: Decimal
    minimum_price: Decimal
    stock: int
    gst_rate: Decimal

    model_config = {"from_attributes": True}


class PromotionalPriceResponse(BaseModel):
    product_id: str
    normal_price: Decimal
    promotional_price: Decimal
    minimum_price: Decimal
    expires_at: datetime

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)
    promotional_price: Decimal = Field(gt=0)

    @field_validator("product_id")
    @classmethod
    def product_id_must_be_int_string(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("product_id must be a numeric string")
        return value


class OrderResponse(BaseModel):
    order_id: str
    status: str
    product_id: str
    quantity: int
    price: Decimal


class SettlementResponse(BaseModel):
    order_id: str
    customer_price: Decimal
    platform_fee: Decimal
    logistics_fee: Decimal
    seller_settlement: Decimal


class PaymentResponse(BaseModel):
    order_id: str
    status: str
    payment_id: int
    amount: Decimal
    cashback: Decimal
    settlement: SettlementResponse
    already_processed: bool = False


class ErrorResponse(BaseModel):
    detail: str
