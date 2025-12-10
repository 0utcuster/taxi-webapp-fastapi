# from __future__ import annotations

# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, DeclarativeBase
# from .config import settings

# # ---------- Declarative Base ----------
# class Base(DeclarativeBase):
#     pass

# # ---------- Engine / Session ----------
# # Если у тебя PostgreSQL в Docker на 127.0.0.1:5432:
# # убедись, что settings.DATABASE_URL вида:
# # postgresql+psycopg://village:village@127.0.0.1:5432/village
# DATABASE_URL = settings.DATABASE_URL

# engine = create_engine(
#     DATABASE_URL,
#     pool_pre_ping=True,
#     future=True,
# )

# SessionLocal = sessionmaker(
#     bind=engine,
#     autoflush=False,
#     autocommit=False,
#     expire_on_commit=False,
#     future=True,
# )
# from app.models import user, taxi, delivery, courier, classifieds

# Base.metadata.create_all(bind=engine)
# # ---------- Dependency ----------
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()




from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings
import os

# ---------- Declarative Base ----------
class Base(DeclarativeBase):
    pass

# ---------- Engine / Session ----------
# Строка берётся из настроек (например из .env через app.config.settings)
DATABASE_URL = settings.DATABASE_URL

# Поддержка SQLite и PostgreSQL (или любой другой, поддерживаемый SQLAlchemy)
if DATABASE_URL and DATABASE_URL.startswith("sqlite"):
    # Для sqlite важно указать check_same_thread=False для многопоточного доступа
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        future=True,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        future=True,
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,      # оставляем False — поведение как было
    expire_on_commit=False,
    future=True,
)

# Импорт моделей (чтобы при create_all были зарегистрированы все таблицы)
# Подкорректируй список, если у тебя другие модули/имена моделей
from app.models import user, taxi, delivery, courier, classifieds  # noqa: E402,F401

# Создать таблицы (удобно для разработки). В проде при миграциях это обычно отключают.
Base.metadata.create_all(bind=engine)

# ---------- Dependency ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()