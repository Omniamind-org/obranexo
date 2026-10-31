"""Banco (db.py): migração sobre bancos SQLite criados antes do Alembic e o "insira ou substitua" dos dois bancos."""

from __future__ import annotations

import sqlite3

from sqlalchemy import inspect, text

from obranexo import db

# Como os módulos criavam as tabelas antes do Alembic (contas.py e trilha.py; o chat ainda sem empresa_id)
ESQUEMA_ANTIGO = """
CREATE TABLE empresas (id TEXT PRIMARY KEY, nome TEXT NOT NULL, cnpj TEXT, criada_em TEXT NOT NULL);
CREATE TABLE usuarios (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, nome TEXT NOT NULL DEFAULT '', senha_hash TEXT NOT NULL,
  empresa_id TEXT NOT NULL REFERENCES empresas(id), admin INTEGER NOT NULL DEFAULT 0, ativo INTEGER NOT NULL DEFAULT 1, criado_em TEXT NOT NULL);
CREATE TABLE chat_mensagens (sessao_id TEXT NOT NULL, ordem INTEGER NOT NULL, empresa TEXT, ts TEXT, papel TEXT NOT NULL,
  conteudo TEXT NOT NULL, PRIMARY KEY (sessao_id, ordem));
CREATE TABLE chamadas_llm (id TEXT PRIMARY KEY, quando TEXT NOT NULL, agente TEXT NOT NULL, operacao TEXT NOT NULL,
  provedor TEXT NOT NULL, modelo_pedido TEXT NOT NULL, status TEXT NOT NULL);
INSERT INTO empresas VALUES ('emp_1', 'Alfa', NULL, '2026-10-24T10:00:00');
INSERT INTO chat_mensagens VALUES ('s1', 0, 'Alfa', NULL, 'usuario', '{"texto": "oi"}');
INSERT INTO chamadas_llm VALUES ('c1', '2026-10-24T10:00:00', 'investigador', 'texto', 'gemini', 'gemini-3.8-flash', 'ok');
"""


def test_migracao_preserva_um_banco_antigo_e_completa_o_que_falta(tmp_path):
    caminho = tmp_path / "antigo.db"
    with sqlite3.connect(caminho) as con:
        con.executescript(ESQUEMA_ANTIGO)
    e = db.engine(caminho)
    tabelas = set(inspect(e).get_table_names())
    assert {"sessoes", "links_conta", "jobs", "job_eventos", "alembic_version"} <= tabelas
    assert "empresa_id" in {c["name"] for c in inspect(e).get_columns("chat_mensagens")}
    with e.connect() as con:
        assert con.execute(text("SELECT nome FROM empresas")).scalar_one() == "Alfa"
        assert con.execute(text("SELECT count(*) FROM chamadas_llm")).scalar_one() == 1
        assert con.execute(text("SELECT conteudo FROM chat_mensagens")).scalar_one() == '{"texto": "oi"}'
        assert con.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "0001"
    db.migrar(e)  # rodar de novo não muda nada


def test_inserir_ou_substituir_atualiza_pela_chave(tmp_path):
    caminho = tmp_path / "novo.db"
    linha = {"sessao_id": "s1", "ordem": 0, "empresa": "Alfa", "empresa_id": None, "ts": None, "papel": "usuario", "conteudo": "1"}
    with db.escrever(caminho) as con:
        db.inserir_ou_substituir(con, db.chat_mensagens, linha)
        db.inserir_ou_substituir(con, db.chat_mensagens, {**linha, "conteudo": "2"})
    with db.ler(caminho) as con:
        assert con.execute(text("SELECT conteudo FROM chat_mensagens")).scalars().all() == ["2"]


def test_esquema_do_codigo_bate_com_o_banco_migrado(tmp_path):
    """O que `alembic check` confere no CI: nenhuma diferença entre db.metadata e o banco criado pelas migrações."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    with db.engine(tmp_path / "novo.db").connect() as con:
        assert compare_metadata(MigrationContext.configure(con), db.metadata) == []
