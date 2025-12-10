from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime
from sqlalchemy.sql import func
from .base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)  # твой not null
    tg_id = Column(BigInteger, unique=True, index=True, nullable=True)         # зеркалим для совместимости

    username = Column(String, nullable=True)
    name = Column(String, nullable=True)          # вместо first_name/last_name
    role = Column(String, nullable=True)          # 'admin'/'user'/...
    is_active = Column(Boolean, nullable=True)    # можно по умолчанию True в коде
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())

    # Удобное отображаемое имя
    @property
    def display_name(self) -> str:
        return self.name or (f"@{self.username}" if self.username else f"ID {self.telegram_id or self.tg_id}")