"""Operator-supplied connection URL, never persisted in alembic.ini."""
import os
from alembic import context
from sqlalchemy import create_engine
from billing_backend.db import Base
from billing_backend.settings import validate_database_url

url = os.environ['BILLING_DATABASE_URL']
validate_database_url(url, os.getenv('BILLING_ALLOW_SQLITE_TEST') == 'true')
if context.is_offline_mode():
    raise RuntimeError('Use an explicit online migration against the sandbox database')
engine = create_engine(url, hide_parameters=True)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
