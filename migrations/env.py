from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

# --- your app imports ---
from app.core.config import settings
from app.db.model_registry import metadata  # <- THIS pulls in all models

# Alembic Config object
config = context.config
fileConfig(config.config_file_name)  # logging

target_metadata = metadata  # <- use the aggregated metadata

def run_migrations_offline():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,       # detect type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        {"sqlalchemy.url": settings.database_url},
        prefix="",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
