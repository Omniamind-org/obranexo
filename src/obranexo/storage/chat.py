"""Memória das conversas do assistente: cada mensagem (do usuário e do assistente) fica no banco (db.py).

É o que o assistente lembra entre sessões: ao reiniciar o servidor, uma conversa é reconstruída daqui e o próximo
turno recomeça com o resumo das últimas mensagens (Assistente._contexto_anterior). O histórico no formato do
provedor (com os resultados de ferramenta) não é guardado: é grande, muda de formato entre provedores e o resumo
basta para continuar.

Cada mensagem guarda a empresa ativa (contas.empresa_ativa) e só é relida pela mesma empresa.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from sqlalchemy import text

from obranexo import contas, db

_lock = threading.Lock()


def salvar_mensagem(sessao_id: str, empresa: str, ordem: int, mensagem: dict[str, Any]) -> None:
    with _lock, db.escrever() as con:
        db.inserir_ou_substituir(con, db.chat_mensagens, {
            "sessao_id": sessao_id, "ordem": ordem, "empresa": empresa, "empresa_id": contas.empresa_ativa(), "ts": mensagem.get("ts"),
            "papel": mensagem.get("papel", ""), "conteudo": json.dumps(mensagem, ensure_ascii=False, default=str),
        })


def carregar(sessao_id: str) -> list[dict[str, Any]]:
    """Mensagens da conversa em ordem; lista vazia se a conversa não existe ou é de outra empresa."""
    with db.ler() as con:
        linhas = con.execute(
            text("SELECT conteudo FROM chat_mensagens WHERE sessao_id = :sessao_id AND empresa_id IS NOT DISTINCT FROM :empresa_id ORDER BY ordem"),
            {"sessao_id": sessao_id, "empresa_id": contas.empresa_ativa()},
        ).fetchall()
    return [json.loads(c) for (c,) in linhas]
