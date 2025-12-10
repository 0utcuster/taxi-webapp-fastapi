from sqlalchemy import Column, Integer, String
from .base import Base

class InfoEntry(Base):
    __tablename__ = "info_entries"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)     # "Скорая", "Полиция", ...
    value = Column(String(500), nullable=False)     # "103", "102", "расписание: ...", ссылка и т.п.
    group = Column(String(100), nullable=True)      # "Экстренные", "Автобусы", "Учреждения"