from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from .base import Base

class Ad(Base):
    __tablename__ = "ads"
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(String(2000))
    image_url = Column(String(500))
    category = Column(String(100))   # "Куплю", "Продам", "Услуги"
    created_at = Column(DateTime(timezone=True), server_default=func.now())