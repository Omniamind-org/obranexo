"""Esquema inicial: contas, sessões, links de convite, chat, trilha de chamadas de IA e jobs.

Os bancos SQLite criados antes do Alembic já têm parte destas tabelas (feitas com CREATE TABLE IF NOT EXISTS pelos
próprios módulos, que nunca acrescentavam colunas novas): aqui só se cria o que falta, tabela, coluna ou índice.
Coluna acrescentada a uma tabela com linhas entra como opcional quando não tem valor padrão.

Revisão: 0001 · anterior: nenhuma
"""

from alembic import op
from sqlalchemy import Column, inspect

from obranexo import db

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    con = op.get_bind()
    existentes = set(inspect(con).get_table_names())
    for tabela in db.metadata.sorted_tables:
        if tabela.name not in existentes:
            tabela.create(con)
            continue
        colunas = {c["name"] for c in inspect(con).get_columns(tabela.name)}
        for coluna in tabela.columns:
            if coluna.name not in colunas:
                op.add_column(tabela.name, Column(coluna.name, coluna.type, server_default=coluna.server_default,
                                                  nullable=coluna.nullable or coluna.server_default is None))
        indices = {i["name"] for i in inspect(con).get_indexes(tabela.name)}
        for indice in tabela.indexes:
            if indice.name not in indices:
                indice.create(con)


def downgrade() -> None:
    for tabela in reversed(db.metadata.sorted_tables):
        op.drop_table(tabela.name)
