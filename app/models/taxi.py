# app/models/taxi.py
from sqlalchemy import (
    Column, Integer, BigInteger, String, DateTime, Boolean, ForeignKey, Enum, Index
)
from sqlalchemy.sql import func
import enum
from .base import Base

class PriceMode(str, enum.Enum):
    CLIENT_SETS = "client_sets"   # клиент указывает цену
    DRIVER_BIDS = "driver_bids"   # водители делают ставки

class TripStatus(str, enum.Enum):
    NEW         = "new"
    ASSIGNED    = "assigned"
    ON_WAY      = "on_way"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    CANCELLED   = "cancelled"

class TaxiVehicle(Base):
    __tablename__ = "taxi_vehicles"
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    make = Column(String(80), nullable=True)
    model = Column(String(80), nullable=True)
    color = Column(String(40), nullable=True)
    plate = Column(String(20), nullable=True)
    seats = Column(Integer, nullable=True)
    photo_url = Column(String(400), nullable=True)

    verified = Column(Boolean, default=False)
    active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TaxiTrip(Base):
    __tablename__ = "taxi_trips"
    id = Column(Integer, primary_key=True)

    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    passenger_tg_id = Column(BigInteger, nullable=False, index=True)

    from_street = Column(String(160), nullable=False)
    from_house  = Column(String(40), nullable=True)
    from_comment = Column(String(200), nullable=True)

    to_street = Column(String(160), nullable=False)
    to_house  = Column(String(40), nullable=True)
    to_comment = Column(String(200), nullable=True)

    price_mode = Column(Enum(PriceMode), nullable=False)
    client_price = Column(Integer, nullable=True)
    final_price  = Column(Integer, nullable=True)

    assigned_driver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_driver_tg_id = Column(BigInteger, nullable=True, index=True)
    assigned_vehicle_id = Column(Integer, ForeignKey("taxi_vehicles.id"), nullable=True)

    status = Column(Enum(TripStatus), nullable=False, default=TripStatus.NEW)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_taxi_trips_status", "status"),
        Index("ix_taxi_trips_price_mode", "price_mode"),
    )

    # удобный сериализатор для фронта (без bid’ов)
    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "price_mode": self.price_mode.value if hasattr(self.price_mode, "value") else self.price_mode,
            "client_price": self.client_price,
            "final_price": self.final_price,
            "from": {"street": self.from_street, "house": self.from_house, "comment": self.from_comment},
            "to":   {"street": self.to_street,   "house": self.to_house,   "comment": self.to_comment},
            "driver": None,  # заполняем в сервисе при необходимости
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class TaxiBidStatus(str, enum.Enum):
    PENDING   = "pending"
    ACCEPTED  = "accepted"
    REJECTED  = "rejected"
    WITHDRAWN = "withdrawn"

class TaxiBid(Base):
    __tablename__ = "taxi_bids"
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey("taxi_trips.id"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    driver_tg_id = Column(BigInteger, nullable=False, index=True)
    offered_price = Column(Integer, nullable=False)
    comment = Column(String(200), nullable=True)
    status = Column(Enum(TaxiBidStatus), nullable=False, default=TaxiBidStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_taxi_bids_trip_status", "trip_id", "status"),)