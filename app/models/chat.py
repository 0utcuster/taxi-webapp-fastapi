from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from .base import Base

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    author_tg_id = Column(BigInteger, index=True, nullable=False)  # <-- BIGINT
    author_name = Column(String(200))
    text = Column(String(2000), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())