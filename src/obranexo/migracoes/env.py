"""Ambiente do Alembic. O app chama as migrações com a conexão já aberta (db.migrar); pela linha de comando
(`alembic upgrade head`, com alembic.ini na raiz), usa OBRANEXO_DATABASE_URL ou o SQLite padrão."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from obranexo import db

conexao = context.config.attributes.get("connection")
if conexao is not None:
    context.configure(connection=conexao, target_metadata=db.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(db.url()).begin() as con:
        context.configure(connection=con, target_metadata=db.metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
