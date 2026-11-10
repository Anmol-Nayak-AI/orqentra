from sqlalchemy import engine_from_config, pool

from alembic import context
from orqentra.core.config import Settings
from orqentra.persistence.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations() -> None:
    supplied = config.attributes.get("connection")
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    secret = Settings().migration_database_url
    if secret is None:
        raise RuntimeError("Set ORQENTRA_MIGRATION_DATABASE_URL explicitly; no default database.")
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = secret.get_secret_value()
    engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Use an online reviewed migration; offline secret URLs are not rendered.")
run_migrations()
