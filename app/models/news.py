from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from .base import Base

class NewsPost(Base):
    __tablename__ = "news_posts"
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author_tg_id = Column(Integer, index=True, nullable=False)
    author_name = Column(String(200))
    title = Column(String(200), nullable=False)
    body = Column(String(4000))
    image_url = Column(String(500))
    pinned = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())