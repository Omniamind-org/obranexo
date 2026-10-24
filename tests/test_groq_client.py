"""Cliente Groq sem rede: conversão de formatos e tratamento dos erros particulares da API do Groq."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import groq
import httpx
import pytest
from pydantic import BaseModel

from obranexo.config import Config
from obranexo.llm.client import GroqClient, LLMClient, LLMIndisponivel, _json_da_resposta, criar_llm_client


class Saida(BaseModel):
    nome: str
    valor: float


def _resp(conteudo: str = "", tool_calls=None, finish: str = "stop"):
    msg = SimpleNamespace(content=conteudo, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)],
                           usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5))


def _erro(cls, status: int, codigo: str, mensagem: str = "erro"):
    resposta = httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    return cls(mensagem, response=resposta, body={"error": {"message": mensagem, "code": codigo}})


class FakeGroq:
    """Devolve (ou levanta) os itens da fila em ordem e guarda os pedidos."""

    def __init__(self, fila):
        self.fila = list(fila)
        self.pedidos: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.pedidos.append(kw)
        item = self.fila.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def cliente(tmp_path):
    LLMClient._indisponiveis.clear()
    cfg = Config(llm_provider=None, groq_api_key="gsk_teste", gemini_api_key=None, anthropic_api_key=None,
                 dir_llm_cache=tmp_path, llm_cache=False)
    cfg.usar_provedor("groq")
    cfg.modelos_reserva = ["llama-3.3-70b-versatile"]
    c = GroqClient(cfg)
    yield c
    LLMClient._indisponiveis.clear()


def test_fabrica_e_modelos_do_groq(tmp_path):
    cfg = Config(llm_provider=None, groq_api_key="gsk_teste", gemini_api_key=None, anthropic_api_key=None, dir_llm_cache=tmp_path)
    cfg.usar_provedor("groq")
    assert isinstance(criar_llm_client(cfg), GroqClient)
    assert cfg.model_agente.startswith("openai/gpt-oss") and cfg.lote_max_itens < 10
    with pytest.raises(ValueError):
        replace(cfg, anthropic_api_key=None).usar_provedor("anthropic")


def test_extrair_com_json_schema(cliente):
    fake = FakeGroq([_resp('{"nome": "cabo", "valor": 2.5}')])
    cliente._client = fake
    out = cliente.extrair("openai/gpt-oss-20b", "sys", "prompt", Saida)
    assert out == Saida(nome="cabo", valor=2.5)
    pedido = fake.pedidos[0]
    assert pedido["response_format"]["type"] == "json_schema"
    assert pedido["reasoning_effort"] == "low"  # particularidade dos gpt-oss
    assert "max_completion_tokens" in pedido and "max_tokens" not in pedido
    assert cliente.uso.chamadas == 1 and cliente.uso.tokens_entrada == 10


def test_modelo_sem_json_schema_cai_para_json_object(cliente):
    recusa = _erro(groq.BadRequestError, 400, "invalid_request_error", "This model does not support response format `json_schema`")
    fake = FakeGroq([recusa, _resp('<think>raciocínio</think>```json\n{"nome": "x", "valor": 1}\n```')])
    cliente._client = fake
    out = cliente.extrair("llama-3.3-70b-versatile", "sys", "prompt", Saida)
    assert out.nome == "x"
    assert fake.pedidos[1]["response_format"] == {"type": "json_object"}
    assert "JSON" in fake.pedidos[1]["messages"][0]["content"]  # json_object exige a palavra JSON
    assert "llama-3.3-70b-versatile" in cliente._sem_json_schema


def test_json_fora_do_esquema_pede_correcao(cliente):
    fake = FakeGroq([_resp('{"nome": "x"}'), _resp('{"nome": "x", "valor": 3}')])
    cliente._client = fake
    assert cliente.extrair("openai/gpt-oss-20b", "sys", "p", Saida).valor == 3
    assert fake.pedidos[1]["messages"][-1]["role"] == "user" and "não validou" in fake.pedidos[1]["messages"][-1]["content"]


@pytest.mark.parametrize("erro", [
    _erro(groq.PermissionDeniedError, 403, "", "Access denied. Please check your network settings."),
    _erro(groq.RateLimitError, 429, "rate_limit_exceeded"),
    _erro(groq.APIStatusError, 413, "request_too_large"),
])
def test_erros_do_groq_usam_o_reserva(cliente, erro):
    fake = FakeGroq([erro, _resp('{"nome": "r", "valor": 0}')])
    cliente._client = fake
    assert cliente.extrair("openai/gpt-oss-20b", "s", "p", Saida).nome == "r"
    assert [p["model"] for p in fake.pedidos] == ["openai/gpt-oss-20b", "llama-3.3-70b-versatile"]
    assert "openai/gpt-oss-20b" in LLMClient._indisponiveis


def test_403_explica_bloqueio_de_rede(cliente):
    cliente.cfg.modelos_reserva = []
    cliente._client = FakeGroq([_erro(groq.PermissionDeniedError, 403, "", "Access denied. Please check your network settings.")])
    with pytest.raises(LLMIndisponivel, match="rede"):
        cliente.texto("openai/gpt-oss-20b", "s", "p")


def test_conversa_com_ferramentas_no_formato_openai(cliente):
    chamada = SimpleNamespace(id="call_1", function=SimpleNamespace(name="buscar", arguments='{"termo": "cabo"}'))
    fake = FakeGroq([
        _erro(groq.BadRequestError, 400, "tool_use_failed"),  # chamada malformada: tenta de novo
        _resp("", tool_calls=[chamada], finish="tool_calls"),
        _resp("pronto"),
    ])
    cliente._client = fake
    tools = [{"name": "buscar", "description": "busca", "strict": True,
              "input_schema": {"type": "object", "properties": {"termo": {"type": "string"}}, "required": ["termo"]}}]
    conversa = cliente.conversa("openai/gpt-oss-120b", "sistema", tools)
    r = conversa.enviar("comece")
    assert r.parada == "ferramentas" and r.chamadas[0].nome == "buscar" and r.chamadas[0].entrada == {"termo": "cabo"}
    assert fake.pedidos[0]["tools"][0] == {"type": "function", "function": {"name": "buscar", "description": "busca",
                                                                            "parameters": tools[0]["input_schema"]}}
    r2 = conversa.responder_ferramentas([("call_1", json.dumps({"ok": True}), False)])
    assert r2.texto == "pronto" and r2.parada == "fim"
    msgs = fake.pedidos[-1]["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[2]["tool_calls"][0]["function"]["arguments"] == '{"termo": "cabo"}'  # argumentos voltam como string
    assert msgs[3] == {"role": "tool", "tool_call_id": "call_1", "content": '{"ok": true}'}


def test_argumentos_invalidos_nao_quebram_a_conversa(cliente):
    chamada = SimpleNamespace(id="c", function=SimpleNamespace(name="buscar", arguments="{quebrado"))
    cliente._client = FakeGroq([_resp("", tool_calls=[chamada], finish="tool_calls")])
    r = cliente.conversa("openai/gpt-oss-120b", "s", []).enviar("x")
    assert r.chamadas[0].entrada == {}


def test_json_da_resposta():
    assert _json_da_resposta('<think>a {b}</think> texto {"a": 1} fim') == '{"a": 1}'
