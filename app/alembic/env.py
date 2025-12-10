from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

config = context.config
fileConfig(config.config_file_name)

def get_url():
    return os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/village_app")

from app.db import Base  # импорт моделей для автогенерации метаданных
from app.models.user import User  # noqa: F401

def run_migrations_offline():
    url = get_url()
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()