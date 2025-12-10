from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    Column, Integer, String, Enum, Boolean, DateTime, BigInteger, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from ..db import Base


class DeliveryStatus(str, enum.Enum):
    NEW        = "NEW"
    ASSIGNED   = "ASSIGNED"
    ON_WAY     = "ON_WAY"
    IN_PROGRESS= "IN_PROGRESS"
    COMPLETED  = "COMPLETED"
    CANCELLED  = "CANCELLED"


class DeliveryPriceMode(str, enum.Enum):
    CLIENT_SETS  = "CLIENT_SETS"   # фикс от клиента
    COURIER_BIDS = "COURIER_BIDS"  # ставки курьеров


class DeliveryBidStatus(str, enum.Enum):
    PENDING  = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class DeliveryOrder(Base):
    __tablename__ = "delivery_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # клиент
    customer_id    = Column(Integer, nullable=False, index=True)   # user.id
    customer_tg_id = Column(BigInteger, nullable=False)            # TG id (BIGINT! чтобы не было "integer out of range")

    # назначенный курьер (когда назначен)
    assigned_courier_id    = Column(Integer)
    assigned_courier_tg_id = Column(BigInteger)

    # содержимое заказа
    title       = Column(String(255), nullable=False)      # было ошибки "column title does not exist" — теперь есть
    details     = Column(String(2000))
    from_place  = Column(String(255))
    to_street   = Column(String(255))
    to_house    = Column(String(64))
    to_comment  = Column(String(500))

    price_mode  = Column(Enum(DeliveryPriceMode), nullable=False, default=DeliveryPriceMode.CLIENT_SETS)
    client_price= Column(Integer)   # фикс от клиента
    final_price = Column(Integer)   # финал после назначения/завершения

    status      = Column(Enum(DeliveryStatus), nullable=False, default=DeliveryStatus.NEW)

    created_at  = Column(DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime(timezone=True), default=None, onupdate=dt.datetime.utcnow)

    bids = relationship("DeliveryBid", back_populates="order", cascade="all, delete-orphan")

Index("ix_delivery_orders_status", DeliveryOrder.status)
Index("ix_delivery_orders_price_mode", DeliveryOrder.price_mode)


class DeliveryBid(Base):
    __tablename__ = "delivery_bids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id   = Column(Integer, ForeignKey("delivery_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    driver_id  = Column(Integer, nullable=False)     # курьер = user.id
    driver_tg_id = Column(BigInteger, nullable=False)

    offered_price = Column(Integer, nullable=False)
    status = Column(Enum(DeliveryBidStatus), nullable=False, default=DeliveryBidStatus.PENDING)

    created_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False)

    order = relationship("DeliveryOrder", back_populates="bids")

Index("ix_delivery_bids_order_driver_unique", DeliveryBid.order_id, DeliveryBid.driver_id)