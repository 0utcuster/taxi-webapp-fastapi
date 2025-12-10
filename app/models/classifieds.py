from __future__ import annotations
import datetime as dt
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from .base import Base


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner_tg_id = Column(String(32), nullable=True, index=True)

    title = Column(String(200), nullable=False)
    description = Column(String(4000), nullable=True)
    price = Column(Integer, nullable=True)            # ₽; null — “договорная”
    photo_url = Column(String(1000), nullable=True)   # URL фото
    phone = Column(String(64), nullable=True)         # телефон владельца объявления

    approved = Column(Boolean, default=False, nullable=False)
    rejected = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow, nullable=True)

    owner = relationship("User", backref="listings")