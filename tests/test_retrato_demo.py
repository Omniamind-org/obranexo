"""Retrato da demonstração: os casos congelados versionados, sem IA, têm de dar sempre o mesmo resultado.

Qualquer mudança no veredito ou no produto de um item, na prioridade, no tipo de oportunidade, nas provas
conferidas ou na quantidade de requisitos e documentos reprova o teste. Mudança intencional: regenerar com
    OBRANEXO_ATUALIZAR_RETRATO=1 pytest tests/test_retrato_demo.py
e revisar a diferença do tests/dados/retrato_demo.json no próprio PR.

A prioridade depende do prazo (aberta × encerrada), então a data de "hoje" é fixada.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from obranexo.config import config

RETRATO = Path(__file__).parent / "dados" / "retrato_demo.json"
HOJE = datetime(2026, 10, 24, 12, 0)
# Licitações baixadas pelo Prospector (CNPJ_ANO_SEQ) ficam fora do git (.gitignore) e variam de máquina para máquina
COLETADO_LOCALMENTE = re.compile(r"^\d+_\d+_\d+$")
ORDEM = {"COMPATIVEL": 3, "PARCIAL": 2, "INDETERMINADO": 1, "INCOMPATIVEL": 0}


class _DataFixa(datetime):
    @classmethod
    def now(cls, tz=None):
        return HOJE if tz is None else HOJE.replace(tzinfo=tz)


def _retrato_atual(monkeypatch) -> dict:
    from obranexo.agents import pipeline, planejador
    from obranexo.catalog.loader import carregar_catalogo_json
    from obranexo.connectors.pncp import listar_casos

    monkeypatch.setattr(planejador, "datetime", _DataFixa)
    cfg = replace(config, llm_provider=None, offline=True)
    empresa = carregar_catalogo_json(config.catalogo_demo)
    skus = {p.id: p.sku for p in empresa.produtos}
    retrato = {}
    for caso in (c for c in listar_casos() if not COLETADO_LOCALMENTE.match(c.name)):
        a = pipeline.executar_caso(caso, empresa, cfg=cfg, salvar=False)
        melhor: dict[int, str] = {}
        for c in sorted(a.correspondencias, key=lambda c: (ORDEM[c.resultado.value], c.score), reverse=True):
            melhor.setdefault(a.item(c.item_id).numero_item, f"{c.resultado.value} {skus.get(c.produto_id, c.produto_id)}")
        q = a.qualificacao
        retrato[caso.name] = {
            "status": a.status,
            "itens": {str(i.numero_item): melhor.get(i.numero_item, "FORA") for i in a.itens},
            "prioridade": q.prioridade if q else None,
            "tipo": q.tipo_oportunidade.value if q else None,
            "evidencias": f"{sum(e.verificada for e in a.evidencias)}/{len(a.evidencias)}",
            "requisitos": len(a.requisitos),
            "documentos": len(a.documentos),
        }
    return retrato


@pytest.mark.retrato
def test_demo_continua_igual(monkeypatch):
    atual = _retrato_atual(monkeypatch)
    if os.getenv("OBRANEXO_ATUALIZAR_RETRATO") == "1":
        RETRATO.write_text(json.dumps(atual, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        pytest.skip("retrato regenerado: revise a diferença no PR")
    esperado = json.loads(RETRATO.read_text(encoding="utf-8"))
    assert set(atual) == set(esperado), "casos congelados mudaram"
    diferencas = []
    for caso, e in esperado.items():
        for campo, valor in e.items():
            if atual[caso].get(campo) != valor:
                diferencas.append(f"{caso}.{campo}: esperado {str(valor)[:120]} · obtido {str(atual[caso].get(campo))[:120]}")
    assert not diferencas, "a demonstração mudou:\n" + "\n".join(diferencas)
