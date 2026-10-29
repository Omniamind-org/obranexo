"""Banco de dados: SQLite local por padrão (data/obranexo.db) ou PostgreSQL com OBRANEXO_DATABASE_URL.

Guarda contas, sessões, links de convite, conversas do assistente, a trilha de chamadas de IA e os jobs.
O esquema abaixo é a referência do Alembic (src/obranexo/migracoes): mudou aqui, gera migração nova.
Análises, prospecções e catálogos continuam em JSON (storage/store.py).

O SQL dos módulos é o mesmo nos dois bancos (SQLAlchemy Core com parâmetros nomeados); o que difere entre
eles, como o "insira ou substitua", fica em funções daqui.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Column, Connection, Engine, Float, ForeignKey, Index, Integer, MetaData, Table, Text, create_engine, event
from sqlalchemy.dialects import postgresql, sqlite

from obranexo.config import config

metadata = MetaData()

empresas = Table(
    "empresas", metadata,
    Column("id", Text, primary_key=True),
    Column("nome", Text, nullable=False),
    Column("cnpj", Text),
    Column("criada_em", Text, nullable=False),
)
usuarios = Table(
    "usuarios", metadata,
    Column("id", Text, primary_key=True),
    Column("email", Text, nullable=False, unique=True),
    Column("nome", Text, nullable=False, server_default=""),
    Column("senha_hash", Text, nullable=False),
    Column("empresa_id", Text, ForeignKey("empresas.id"), nullable=False),
    Column("admin", Integer, nullable=False, server_default="0"),
    Column("ativo", Integer, nullable=False, server_default="1"),
    Column("criado_em", Text, nullable=False),
)
sessoes = Table(
    "sessoes", metadata,
    Column("token_hash", Text, primary_key=True),
    Column("usuario_id", Text, ForeignKey("usuarios.id"), nullable=False),
    Column("criada_em", Text, nullable=False),
    Column("expira_em", Text, nullable=False),
)
links_conta = Table(
    "links_conta", metadata,
    Column("id", Text, primary_key=True),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("tipo", Text, nullable=False),
    Column("email", Text, nullable=False),
    Column("empresa_id", Text, ForeignKey("empresas.id")),
    Column("empresa_nova", Text),
    Column("admin", Integer, nullable=False, server_default="0"),
    Column("criado_por", Text, ForeignKey("usuarios.id")),
    Column("criado_em", Text, nullable=False),
    Column("expira_em", Text, nullable=False),
    Column("usado_em", Text),
)
chat_mensagens = Table(
    "chat_mensagens", metadata,
    Column("sessao_id", Text, primary_key=True),
    Column("ordem", Integer, primary_key=True),
    Column("empresa", Text),
    Column("ts", Text),
    Column("papel", Text, nullable=False),
    Column("conteudo", Text, nullable=False),
    Column("empresa_id", Text),
)
chamadas_llm = Table(
    "chamadas_llm", metadata,
    Column("id", Text, primary_key=True),
    Column("quando", Text, nullable=False),
    Column("origem_tipo", Text),
    Column("origem_id", Text),
    Column("agente", Text, nullable=False),
    Column("versao_prompt", Text),
    Column("operacao", Text, nullable=False),
    Column("provedor", Text, nullable=False),
    Column("modelo_pedido", Text, nullable=False),
    Column("modelo_usado", Text),
    Column("tokens_entrada", Integer, nullable=False, server_default="0"),
    Column("tokens_saida", Integer, nullable=False, server_default="0"),
    Column("tokens_raciocinio", Integer, nullable=False, server_default="0"),
    Column("tokens_cache_leitura", Integer, nullable=False, server_default="0"),
    Column("tokens_cache_escrita", Integer, nullable=False, server_default="0"),
    Column("custo_usd", Float, nullable=False, server_default="0"),
    Column("latencia_ms", Integer, nullable=False, server_default="0"),
    Column("cache_hit", Integer, nullable=False, server_default="0"),
    Column("reserva", Integer, nullable=False, server_default="0"),
    Column("status", Text, nullable=False),
    Column("erro", Text),
    Column("entrada_resumo", Text),
    Column("saida_resumo", Text),
    Index("idx_chamadas_origem", "origem_id"),
    Index("idx_chamadas_quando", "quando"),
)
jobs = Table(
    "jobs", metadata,
    Column("id", Text, primary_key=True),
    Column("tipo", Text, nullable=False),
    Column("alvo", Text, nullable=False),
    Column("empresa_id", Text),
    Column("status", Text, nullable=False),
    Column("resultado_id", Text),
    Column("erro", Text),
    Column("dados", Text),
    Column("parametros", Text),
    Column("iniciado_em", Text, nullable=False),
    Column("finalizado_em", Text),
)
job_eventos = Table(
    "job_eventos", metadata,
    Column("job_id", Text, ForeignKey("jobs.id"), primary_key=True),
    Column("ordem", Integer, primary_key=True),
    Column("evento", Text, nullable=False),
)

_engines: dict[str, Engine] = {}
_lock = threading.Lock()


def url(caminho_sqlite: Path | None = None) -> str:
    """OBRANEXO_DATABASE_URL quando definida; senão o SQLite do diretório de dados (que os testes trocam por teste)."""
    if caminho_sqlite is None and config.database_url:
        return config.database_url
    return f"sqlite:///{caminho_sqlite or config.caminho_db}"


def engine(caminho_sqlite: Path | None = None) -> Engine:
    """Um engine por banco, criado e migrado (alembic upgrade head) no primeiro uso."""
    endereco = url(caminho_sqlite)
    with _lock:
        if endereco not in _engines:
            if endereco.startswith("sqlite:///"):
                Path(endereco.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
                e = create_engine(endereco, connect_args={"timeout": 5, "check_same_thread": False})
                event.listen(e, "connect", lambda con, _: con.execute("PRAGMA foreign_keys = ON"))
            else:
                e = create_engine(endereco, pool_pre_ping=True)
            migrar(e)
            _engines[endereco] = e
        return _engines[endereco]


def migrar(e: Engine) -> None:
    from alembic import command
    from alembic.config import Config as ConfigAlembic

    cfg = ConfigAlembic()
    cfg.set_main_option("script_location", "obranexo:migracoes")
    with e.begin() as con:
        cfg.attributes["connection"] = con
        command.upgrade(cfg, "head")


@contextmanager
def escrever(caminho_sqlite: Path | None = None) -> Iterator[Connection]:
    """Transação: confirma no fim do bloco, desfaz se der erro."""
    with engine(caminho_sqlite).begin() as con:
        yield con


@contextmanager
def ler(caminho_sqlite: Path | None = None) -> Iterator[Connection]:
    with engine(caminho_sqlite).connect() as con:
        yield con


def inserir_ou_substituir(con: Connection, tabela: Table, valores: dict[str, Any]) -> None:
    """O "INSERT OR REPLACE" do SQLite, nos dois bancos: pela chave primária, atualiza o que já existe."""
    dialeto = postgresql if con.dialect.name == "postgresql" else sqlite
    chave = [c.name for c in tabela.primary_key.columns]
    comando = dialeto.insert(tabela).values(**valores)
    atualizar = {k: comando.excluded[k] for k in valores if k not in chave}
    con.execute(comando.on_conflict_do_update(index_elements=chave, set_=atualizar) if atualizar else comando.on_conflict_do_nothing())


def limpar() -> None:
    """Só para os testes num Postgres compartilhado: apaga as linhas de todas as tabelas, das dependentes às donas."""
    with escrever() as con:
        for tabela in reversed(metadata.sorted_tables):
            con.execute(tabela.delete())

