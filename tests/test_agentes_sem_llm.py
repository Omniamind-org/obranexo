"""Mecânica dos agentes sem chamar a API: lotes, conferência de citações e o loop do Agente de Prospecção.

Aqui o LLM é substituído por um roteiro de chamadas de ferramenta — o objetivo é testar o que o
SISTEMA faz com as decisões do agente (limites, validação, ids inventados), não o modelo.
"""

from __future__ import annotations

from obranexo.agents.contexto import Contexto
from obranexo.agents.extrator import _lotes
from obranexo.agents.investigador import _executar_ferramenta
from obranexo.agents.prospector import Prospector, partes_id
from obranexo.config import Config
from obranexo.connectors.pncp import PNCPClient
from obranexo.documents.extract import IndiceDocumentos
from obranexo.llm.client import ChamadaFerramenta, ClienteNulo, Conversa, RespostaLLM
from obranexo.models import Analise, Contratacao, Documento, Empresa, ItemDemanda


def _item(n, desc="Luminária LED 100 W"):
    return ItemDemanda(id=f"c#item-{n}", contratacao_id="c", numero_item=n, descricao=desc)


def test_lotes_respeitam_limites():
    itens = [_item(i, "x" * 1500) for i in range(1, 15)]
    lotes = _lotes(itens)
    assert all(len(lote) <= 10 for lote in lotes)
    assert all(sum(len(i.descricao) for i in lote) <= 9000 for lote in lotes)
    assert [i.numero_item for lote in lotes for i in lote] == list(range(1, 15))


def test_ancora_do_item_em_listagem_numerada():
    from obranexo.agents.especificador import item_do_trecho

    pagina = ("18 - Bucha fixação\nDescrição Detalhada: Bucha Tipo Grampo, Tamanho: 8\nValor: 0,20\n"
              "19 - Cabo elétrico flexível\nDescrição Detalhada: Cabo Tipo Bwf, Seção Nominal: 4MM2, Tensão Isolamento: 750V\n"
              "20 - Disjuntor\nDescrição Detalhada: Corrente Nominal: 80A, Classe Tensão: 380V\n")
    assert item_do_trecho(pagina, "Seção Nominal: 4MM2") == 19
    assert item_do_trecho(pagina, "Corrente Nominal: 80A") == 20
    assert item_do_trecho("Texto corrido sem listagem: corrente de 80A", "corrente de 80A") is None


def test_partes_id():
    assert partes_id("01291707000167-1-000075/2026") == ("01291707000167", 2026, 75)


def _ctx():
    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None)
    analise = Analise(id="t", empresa_id="e", contratacao=Contratacao(id="c", orgao_cnpj="0", orgao_nome="O", ano=2026, sequencial=1, objeto="x"),
                      itens=[_item(3, "Luminária pública LED conforme TR")])
    idx = IndiceDocumentos()
    idx.adicionar_texto(Documento(id="tr", contratacao_id="c", nome="TR"), "ITEM 3 - Luminária pública LED de 150 W, fluxo mínimo de 24.000 lm, IP66.")
    return Contexto(analise=analise, empresa=Empresa(id="e", nome="E"), indice=idx, llm=ClienteNulo(cfg), cfg=cfg)


def _registrar(ctx, achados, **entrada):
    base = {"numero_item": 3, "atributo": "potencia_w", "operador": "=", "valor_numero": 150, "valor_texto": None,
            "valor_booleano": None, "documento_id": "tr", "pagina": 1, "trecho_literal": "Luminária pública LED de 150 W"}
    base.update(entrada)
    return _executar_ferramenta(ctx, "registrar_requisito", base, achados)


def test_investigador_confere_citacao_na_hora():
    ctx = _ctx()
    achados = []
    assert _registrar(ctx, achados).startswith("OK")
    assert achados[0].item_id == "c#item-3" and achados[0].obrigatorio  # especificação do item, citação conferida
    # Trecho que não existe no documento: rejeitado, e a evidência não fica registrada
    saida = _registrar(ctx, achados, trecho_literal="Luminária de 200 W com garantia de 10 anos")
    assert saida.startswith("ERRO") and "não foi encontrado" in saida
    assert len(achados) == 1 and len(ctx.analise.evidencias) == 1
    assert _registrar(ctx, achados, numero_item=99).startswith("ERRO: não existe item 99")
    assert _registrar(ctx, achados, documento_id="inventado").startswith("ERRO: documento")
    assert _registrar(ctx, achados, atributo="cct_k", valor_numero=None, valor_texto="branca fria").startswith("ERRO: valor inválido")


class _ConversaRoteirizada(Conversa):
    def __init__(self, roteiro):
        self.roteiro = list(roteiro)

    def _proxima(self):
        if not self.roteiro:
            return RespostaLLM(texto="", parada="fim")
        chamadas = [ChamadaFerramenta(id=f"c{i}", nome=n, entrada=e) for i, (n, e) in enumerate(self.roteiro.pop(0))]
        return RespostaLLM(texto="", chamadas=chamadas, parada="ferramentas")

    def enviar(self, texto):
        return self._proxima()

    def responder_ferramentas(self, resultados):
        self.ultimos = resultados
        return self._proxima()


class _LLMRoteirizado(ClienteNulo):
    def __init__(self, cfg, roteiro):
        super().__init__(cfg)
        self._conv = _ConversaRoteirizada(roteiro)

    @property
    def disponivel(self):
        return True

    def conversa(self, modelo, system, tools):
        return self._conv


class _PNCPFalso(PNCPClient):
    """Só a rede é falsa: a paginação por modalidade (buscar_todas) é a real."""

    def __init__(self, contratacoes):
        super().__init__(offline=True, pausa_s=0)
        self.contratacoes = contratacoes

    def buscar_propostas_abertas(self, uf=None, pagina=1, horizonte_dias=60, **_):
        return [c for c in self.contratacoes if c.uf == uf], 1

    def itens(self, cnpj, ano, seq, cid):
        return [_item(1, "LUMINÁRIA PÚBLICA LED 100 W")]


def test_prospector_so_ranqueia_o_que_encontrou(tmp_path, monkeypatch):
    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None, dir_dados=tmp_path)
    monkeypatch.setattr("obranexo.storage.store.config", cfg)
    abertas = [
        Contratacao(id="01291707000167-1-000075/2026", orgao_cnpj="01291707000167", orgao_nome="Prefeitura A", uf="GO", municipio="A",
                    ano=2026, sequencial=75, objeto="Aquisição de luminárias LED para iluminação pública", valor_estimado=500000),
        Contratacao(id="02506012000118-1-000051/2026", orgao_cnpj="02506012000118", orgao_nome="Prefeitura B", uf="GO", municipio="B",
                    ano=2026, sequencial=51, objeto="Aquisição de veículo SUV", valor_estimado=200000),
    ]
    roteiro = [
        [("buscar_licitacoes_abertas", {"uf": "GO", "termos": ["lumin", "ilumina"]}), ("buscar_licitacoes_abertas", {"uf": "SP", "termos": ["lumin"]})],
        [("ver_itens", {"contratacao_id": "01291707000167-1-000075/2026"})],
        [("concluir", {"resumo": "Uma boa oportunidade.", "ranking": [
            {"contratacao_id": "01291707000167-1-000075/2026", "nota": 80, "justificativa": "Itens de luminária LED"},
            {"contratacao_id": "99999999999999-1-000001/2026", "nota": 99, "justificativa": "inventada pelo modelo"},
        ]})],
    ]
    pr = Prospector(Empresa(id="e", nome="E"), ["GO"], 30, 1, cfg=cfg)
    pr.llm = _LLMRoteirizado(cfg, roteiro)
    pr.pncp = _PNCPFalso(abertas)
    p = pr.executar()
    assert p.status == "concluida", p.erro
    assert list(p.candidatos) == ["01291707000167-1-000075/2026"]  # o SUV não casou com os termos
    assert p.candidatos["01291707000167-1-000075/2026"].itens_vistos
    assert [r.contratacao_id for r in p.ranking] == ["01291707000167-1-000075/2026"]  # o id inventado foi ignorado
    assert any("fora das regiões" in s["saida"] for s in p.passos if s.get("ferramenta") == "buscar_licitacoes_abertas")
    assert (tmp_path / "prospeccoes" / f"{p.id}.json").exists()


def test_ranking_nao_pode_contradizer_a_analise(tmp_path):
    from obranexo.models import CandidatoProspeccao

    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None, dir_dados=tmp_path)
    pr = Prospector(Empresa(id="e", nome="E"), ["GO"], 30, 1, cfg=cfg)
    cid = "01067479000146-1-000064/2026"
    pr.p.candidatos[cid] = CandidatoProspeccao(contratacao={"id": cid}, analise_id="a1", resumo_analise={
        "compativeis": 0, "parciais": 0, "indeterminados": 84, "incompativeis": 0, "fora_do_portfolio": 122, "prioridade": 38.7})
    ranking = [{"contratacao_id": cid, "nota": 88, "justificativa": "Diversos itens alinhados ao catálogo"}]
    primeira = pr.concluir(ranking, "resumo")
    assert primeira.startswith("ERRO") and "0 compatíveis" in primeira  # o agente recebe os fatos para revisar
    assert pr.concluir(ranking, "resumo") == "OK"  # insistiu: o sistema limita a nota
    assert pr.p.ranking[0].nota == Prospector.NOTA_MAX_SEM_ADERENCIA
    assert "limitada pelo sistema" in pr.p.ranking[0].justificativa


def test_prospector_falha_da_fonte_nao_vira_nada_encontrado(tmp_path, monkeypatch):
    from obranexo.connectors.pncp import PNCPError

    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None, dir_dados=tmp_path)
    monkeypatch.setattr("obranexo.storage.store.config", cfg)

    class _PNCPFora(_PNCPFalso):
        aviso = None

        def buscar_propostas_abertas(self, **_):
            raise PNCPError("HTTP 429 Too Many Requests")

    pr = Prospector(Empresa(id="e", nome="E"), ["GO"], 30, 1, cfg=cfg)
    pr.llm = _LLMRoteirizado(cfg, [[("buscar_licitacoes_abertas", {"uf": "GO", "termos": ["lumin"]})],
                                   [("concluir", {"resumo": "PNCP fora do ar.", "ranking": []})]])
    pr.pncp = _PNCPFora([])
    p = pr.executar()
    assert p.status == "erro" and "PNCP recusou" in p.erro


def test_pncp_usa_copia_antiga_quando_o_portal_falha(tmp_path):
    import json as _json
    import os
    import time as _time

    import httpx

    from obranexo.connectors.pncp import PNCPClient, PNCPError

    cli = PNCPClient(dir_cache=tmp_path, offline=False, pausa_s=0)
    url, params = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta", {"uf": "GO"}
    copia = cli._cache_path(str(httpx.URL(url, params=params)), ".json")
    copia.write_text(_json.dumps({"data": [], "totalPaginas": 1}), encoding="utf-8")
    velho = _time.time() - 7200
    os.utime(copia, (velho, velho))

    def fora(*_a, **_k):
        raise PNCPError("HTTP 429")

    cli._get = fora
    assert cli.get_json(url, params, ttl_s=1800) == {"data": [], "totalPaginas": 1}
    assert "120 min" in cli.aviso
    copia.unlink()
    import pytest as _pytest

    with _pytest.raises(PNCPError):
        cli.get_json(url, params, ttl_s=1800)


def test_prospector_respeita_limite_de_analises(tmp_path):
    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None, dir_dados=tmp_path)
    pr = Prospector(Empresa(id="e", nome="E"), ["GO"], 30, 0, cfg=cfg)
    assert pr.analisar("01291707000167-1-000075/2026", "teste").startswith("ERRO: limite de 0 análise")


def test_prospector_sem_llm_falha_com_mensagem_clara(tmp_path, monkeypatch):
    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None, dir_dados=tmp_path)
    monkeypatch.setattr("obranexo.storage.store.config", cfg)
    p = Prospector(Empresa(id="e", nome="E"), ["GO"], 30, 1, cfg=cfg).executar()
    assert p.status == "erro" and "exige um provedor de LLM" in p.erro
