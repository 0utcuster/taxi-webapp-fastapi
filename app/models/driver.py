# app/models/driver.py
from sqlalchemy import Column, Integer, Boolean, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from .base import Base

class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # статусы модерации/видимости
    approved = Column(Boolean, default=False, nullable=False)
    rejected = Column(Boolean, default=False, nullable=False)
    active   = Column(Boolean, default=False, nullable=False)

    # данные профиля
    full_name       = Column(String(200), nullable=True)
    phone           = Column(String(50), nullable=True)
    license_number  = Column(String(50), nullable=True)
    license_valid_to= Column(Date, nullable=True)
    notes           = Column(String(300), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # на уровне БД запрещаем дубликаты на одного пользователя
        UniqueConstraint("user_id", name="uniq_driver_profile_per_user"),
    )