"""Integração com a API do Groq (texto, saída estruturada e ferramentas), independente do provedor ativo.

Pulados sem GROQ_API_KEY ou quando a rede não alcança o Groq (403 "Access denied. Please check your
network settings" é bloqueio de rede/região do provedor, antes da autenticação).
Rode só eles com:  pytest tests/test_integracao_groq.py -m integracao -v
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import BaseModel

from obranexo.config import config

pytestmark = [pytest.mark.integracao, pytest.mark.skipif(not config.groq_api_key, reason="GROQ_API_KEY ausente no .env")]


@pytest.fixture(scope="module")
def groq_cfg():
    from obranexo.llm.client import GroqClient, LLMClient, LLMIndisponivel

    cfg = replace(config, llm_cache=False)
    cfg.usar_provedor("groq")
    try:
        GroqClient(cfg).texto(cfg.model_extracao, "Responda só com a palavra pedida.", "Diga: ok", max_tokens=200)
    except LLMIndisponivel as exc:
        LLMClient._indisponiveis.clear()
        pytest.skip(f"Groq inalcançável desta rede: {exc}")
    return cfg


class Cabo(BaseModel):
    secao_mm2: float
    tensao_isolamento_kv: str


def test_groq_extrai_json_validado(groq_cfg):
    from obranexo.llm.client import GroqClient

    llm = GroqClient(groq_cfg)
    out = llm.extrair(groq_cfg.model_extracao, "Extraia os dados técnicos do texto.", "Cabo flexível 2,5 mm² 450/750 V", Cabo, max_tokens=2000)
    assert out.secao_mm2 == pytest.approx(2.5)
    assert llm.uso.chamadas >= 1


def test_groq_chama_ferramenta(groq_cfg):
    from obranexo.llm.client import GroqClient

    tools = [{"name": "consultar_preco", "description": "Consulta o preço de um produto pelo nome.",
              "input_schema": {"type": "object", "properties": {"produto": {"type": "string"}}, "required": ["produto"]}}]
    conversa = GroqClient(groq_cfg).conversa(groq_cfg.model_agente, "Use as ferramentas para responder.", tools)
    r = conversa.enviar("Quanto custa o produto 'luminária LED 40W'? Consulte antes de responder.")
    assert r.parada == "ferramentas" and r.chamadas and r.chamadas[0].nome == "consultar_preco"
    assert "lumin" in r.chamadas[0].entrada.get("produto", "").lower()
    final = conversa.responder_ferramentas([(r.chamadas[0].id, '{"preco_brl": 89.9}', False)])
    assert "89" in final.texto
