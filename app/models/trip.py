from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base
import enum

class TripStatus(str, enum.Enum):
    NEW = "new"          # создано
    ACCEPTED = "accepted" # принято водителем
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELED = "canceled"

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True)
    rider_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    from_address = Column(String(255), nullable=False)
    to_address   = Column(String(255), nullable=False)

    # вариант 1: цену ставит клиент; вариант 2: цену ставит водитель
    client_price = Column(Numeric(10,2), nullable=True)
    driver_price = Column(Numeric(10,2), nullable=True)

    car_make = Column(String(100))    # заполняется при назначении
    car_plate = Column(String(50))

    status = Column(Enum(TripStatus), default=TripStatus.NEW, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    rider = relationship("User", foreign_keys=[rider_id])
    driver = relationship("User", foreign_keys=[driver_id])