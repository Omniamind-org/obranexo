"""Assistente sem rede e sem LLM real: ferramentas, referências só com ids vistos e recuperação de falha do provedor."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from obranexo.agents import assistente as mod
from obranexo.agents.assistente import Assistente
from obranexo.catalog.loader import carregar_catalogo_json
from obranexo.config import Config, config
from obranexo.llm.client import ChamadaFerramenta, LLMIndisponivel, RespostaLLM
from obranexo.models import Contratacao

ID_REAL = "01067479000146-1-000064/2026"
ID_INVENTADO = "99999999000199-1-000001/2026"


def _contratacao(cid: str, objeto: str, valor: float) -> Contratacao:
    cnpj, resto = cid.split("-", 1)
    seq, ano = resto.split("-")[1].split("/")
    return Contratacao(id=cid, orgao_cnpj=cnpj, orgao_nome="MUNICIPIO DE TESTE", uf="GO", municipio="Teste", ano=int(ano),
                       sequencial=int(seq), objeto=objeto, valor_estimado=valor,
                       data_encerramento_proposta=datetime.now() + timedelta(days=10))


class ConversaRoteirizada:
    """Devolve as respostas na ordem e guarda o que recebeu."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.enviados: list[str] = []
        self.resultados: list = []

    def _proxima(self):
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def enviar(self, texto):
        self.enviados.append(texto)
        return self._proxima()

    def responder_ferramentas(self, resultados):
        self.resultados.append(resultados)
        return self._proxima()


class LLMFalso:
    disponivel = True

    def __init__(self, conversas):
        self.conversas = list(conversas)

    def conversa(self, modelo, system, tools):
        assert "[[" in system and {t["name"] for t in tools} >= {"buscar_licitacoes_abertas", "ver_itens", "analisar_a_fundo"}
        return self.conversas.pop(0)


@pytest.fixture
def assistente(tmp_path, monkeypatch):
    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None, groq_api_key=None, dir_dados=tmp_path)
    a = Assistente(carregar_catalogo_json(config.catalogo_demo), cfg=cfg)
    monkeypatch.setattr(mod, "_casos_locais", lambda: {})
    monkeypatch.setattr(a, "_ultimas_analises", lambda: [])
    lista = [_contratacao(ID_REAL, "Aquisição de materiais de iluminação pública", 26e6),
             _contratacao("11111111000111-1-000002/2026", "Aquisição de veículos", 1e6)]
    monkeypatch.setattr(a.pncp, "buscar_propostas_abertas", lambda **kw: (lista, 1))
    return a


def test_busca_filtra_pelo_objeto_e_registra_o_que_viu(assistente):
    saida = json.loads(assistente.buscar("go", ["ilumina"], 30))
    assert saida["total"] == 1 and saida["resultados"][0]["id"] == ID_REAL
    assert ID_REAL in assistente._vistas
    assert assistente.buscar("Goiás", ["x"], 30).startswith("ERRO")


def test_referencias_so_com_ids_que_as_ferramentas_devolveram(assistente):
    conversa = ConversaRoteirizada([
        RespostaLLM(chamadas=[ChamadaFerramenta(id="c1", nome="buscar_licitacoes_abertas", entrada={"uf": "GO", "termos": ["lumin", "ilumina"]})]),
        RespostaLLM(texto=f"Achei **Município de Teste** [[{ID_REAL}]] e também [[{ID_INVENTADO}]] e [[analise:nao-existe]]."),
    ])
    assistente.llm = LLMFalso([conversa])
    msg = assistente.responder("iluminação em GO")
    assert [r["id"] for r in msg["referencias"]] == [ID_REAL]  # o inventado não vira cartão
    assert msg["ferramentas"] == ["buscar_licitacoes_abertas"]
    assert json.loads(conversa.resultados[0][0][1])["total"] == 1
    assert [m["papel"] for m in assistente.mensagens] == ["usuario", "assistente"]


def test_falha_do_provedor_recomeca_com_resumo_da_conversa(assistente):
    primeira = ConversaRoteirizada([RespostaLLM(texto="Olá! Posso buscar licitações."), LLMIndisponivel("503")])
    segunda = ConversaRoteirizada([RespostaLLM(texto="De volta.")])
    assistente.llm = LLMFalso([primeira, segunda])
    assistente.responder("oi")
    falha = assistente.responder("e agora?")
    assert "não respondeu" in falha["texto"]
    ok = assistente.responder("tente de novo")
    assert ok["texto"] == "De volta."
    assert "Conversa até aqui" in segunda.enviados[0] and "Posso buscar licitações" in segunda.enviados[0]


def test_limite_de_rodadas_de_ferramentas(assistente):
    chamada = RespostaLLM(chamadas=[ChamadaFerramenta(id="c", nome="consultar_catalogo", entrada={"termo": "cabo"})])
    conversa = ConversaRoteirizada([chamada] * (mod.MAX_RODADAS + 1) + [RespostaLLM(texto="fim")])
    assistente.llm = LLMFalso([conversa])
    msg = assistente.responder("loop")
    assert len(msg["ferramentas"]) == mod.MAX_RODADAS
    assert "AVISO DO SISTEMA" in conversa.resultados[-1][-1][1]
