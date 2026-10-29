"""Memória das conversas do assistente: cada mensagem (do usuário e do assistente) fica no SQLite data/obranexo.db.

É o que o assistente lembra entre sessões: ao reiniciar o servidor, uma conversa é reconstruída daqui e o próximo
turno recomeça com o resumo das últimas mensagens (Assistente._contexto_anterior). O histórico no formato do
provedor (com os resultados de ferramenta) não é guardado: é grande, muda de formato entre provedores e o resumo
basta para continuar.

Cada mensagem guarda a empresa ativa (contas.empresa_ativa) e só é relida pela mesma empresa.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from obranexo import contas
from obranexo.config import config

_DDL = """
CREATE TABLE IF NOT EXISTS chat_mensagens (
  sessao_id TEXT NOT NULL,
  ordem INTEGER NOT NULL,
  empresa TEXT,
  ts TEXT,
  papel TEXT NOT NULL,
  conteudo TEXT NOT NULL,
  PRIMARY KEY (sessao_id, ordem)
);
"""

_lock = threading.Lock()
_preparados: set[str] = set()


def _conectar() -> sqlite3.Connection:
    caminho = config.caminho_db
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho, timeout=5)
    if str(caminho) not in _preparados:
        con.executescript(_DDL)
        colunas = {c[1] for c in con.execute("PRAGMA table_info(chat_mensagens)")}
        if "empresa_id" not in colunas:  # bancos criados antes do login
            con.execute("ALTER TABLE chat_mensagens ADD COLUMN empresa_id TEXT")
        _preparados.add(str(caminho))
    return con


def salvar_mensagem(sessao_id: str, empresa: str, ordem: int, mensagem: dict[str, Any]) -> None:
    with _lock, _conectar() as con:
        con.execute(
            "INSERT OR REPLACE INTO chat_mensagens (sessao_id, ordem, empresa, empresa_id, ts, papel, conteudo) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sessao_id, ordem, empresa, contas.empresa_ativa(), mensagem.get("ts"), mensagem.get("papel", ""),
             json.dumps(mensagem, ensure_ascii=False, default=str)),
        )


def carregar(sessao_id: str) -> list[dict[str, Any]]:
    """Mensagens da conversa em ordem; lista vazia se a conversa não existe ou é de outra empresa."""
    with _conectar() as con:
        linhas = con.execute(
            "SELECT conteudo FROM chat_mensagens WHERE sessao_id = ? AND empresa_id IS ? ORDER BY ordem", (sessao_id, contas.empresa_ativa())
        ).fetchall()
    return [json.loads(c) for (c,) in linhas]
