from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, Integer, String, Boolean, DateTime, UniqueConstraint
from ..models.base import Base


class CourierProfile(Base):
    __tablename__ = "courier_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_courier_profiles_user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)  # user.id
    full_name = Column(String(255))
    phone = Column(String(64))
    notes = Column(String(1000))

    approved = Column(Boolean, nullable=False, default=False)
    rejected = Column(Boolean, nullable=False, default=False)
    active   = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False)
    # ВАЖНО: никаких updated_at — раньше БД ругалась на отсутствие этой колонки