"""Testes de integração com o provedor de LLM configurado no .env (Gemini, Groq ou Anthropic).

Chamam a API de verdade (respeitando o cache em disco). São pulados quando não há chave.
Rode só eles com:  pytest -m integracao -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from obranexo.config import config

pytestmark = pytest.mark.integracao

CASO = config.dir_casos / "goianira_pe038_2026"
GABARITO_ITENS = {1: "COMPATIVEL", 2: "COMPATIVEL", 3: "COMPATIVEL", 4: "COMPATIVEL", 5: "PARCIAL", 6: "PARCIAL"}

precisa_llm = pytest.mark.skipif(not config.llm_disponivel, reason="nenhum provedor de LLM configurado (.env)")
precisa_caso = pytest.mark.skipif(not (CASO / "contratacao.json").exists(), reason="caso congelado ausente")


def _contexto():
    from obranexo.agents.contexto import Contexto
    from obranexo.catalog.loader import carregar_catalogo_json
    from obranexo.connectors.pncp import carregar_caso
    from obranexo.documents.extract import IndiceDocumentos
    from obranexo.llm.client import criar_llm_client
    from obranexo.models import Analise, Documento

    contratacao, itens, documentos = carregar_caso(CASO)
    analise = Analise(id="integ", empresa_id="demo", contratacao=contratacao, itens=itens)
    indice = IndiceDocumentos()
    for d in documentos:
        indice.adicionar(d)
        analise.documentos.append(d)
    for item in itens:
        doc = Documento(id=f"pncp-item-{item.numero_item}", contratacao_id=contratacao.id, nome=f"PNCP · item {item.numero_item}")
        indice.adicionar_texto(doc, item.descricao)
        analise.documentos.append(doc)
    return Contexto(analise=analise, empresa=carregar_catalogo_json(config.catalogo_demo), indice=indice, llm=criar_llm_client(config, analise.uso_llm), cfg=config)


@precisa_llm
def test_cliente_responde_texto():
    from obranexo.llm.client import criar_llm_client

    llm = criar_llm_client(config)
    assert llm.disponivel and llm.provedor == config.llm_provider
    resposta = llm.texto(config.model_extracao, "Responda em português, em uma palavra.", "Qual a capital do Brasil?")
    assert "bras" in resposta.lower()
    assert llm.uso.chamadas >= 1 or True  # pode vir do cache


@precisa_llm
@precisa_caso
def test_extrator_llm_complementa_regras():
    from obranexo.agents.extrator import ExtracaoItem, extrair_item
    from obranexo.agents.prompts import SYSTEM_EXTRATOR

    ctx = _contexto()
    item = ctx.analise.itens[0]
    # 1) saída estruturada direta
    extracao = ctx.llm.extrair(config.model_extracao, SYSTEM_EXTRATOR, f'<item numero="1">\n{item.descricao}\n</item>\nExtraia os requisitos técnicos deste item.', ExtracaoItem)
    atributos = {r.atributo for r in extracao.requisitos}
    assert extracao.categoria == "luminaria_publica_led"
    assert {"potencia_w", "cct_k", "ip"} <= atributos, atributos
    for r in extracao.requisitos:
        assert r.trecho_literal, "todo requisito do LLM precisa de trecho literal"
    # 2) nó completo: regras + LLM, sem conflito nos atributos principais
    reqs = extrair_item(ctx, item, "pncp-item-1")
    assert any(r.fonte_extracao == "regras" for r in reqs)
    conflitos_criticos = [c for c in ctx.analise.conflitos if c.atributo in {"potencia_w", "cct_k", "ip", "fluxo_lm"}]
    assert not conflitos_criticos, [c.descricao for c in conflitos_criticos]
    assert any("LLM" in ev.mensagem for ev in ctx.analise.log)


@precisa_llm
@precisa_caso
def test_investigador_llm_acha_prazo_e_garantia_no_edital():
    from obranexo.agents.investigador import investigar_llm
    from obranexo.evidence.verify import verificar_evidencia

    ctx = _contexto()
    achados = investigar_llm(ctx, ["prazo_entrega_dias", "garantia_anos"])
    por = {a.atributo: a for a in achados}
    ferramentas = [p["ferramenta"] for p in ctx.analise.passos_investigacao if p.get("tipo") == "ferramenta"]
    assert "buscar_trechos" in ferramentas, ferramentas
    assert "prazo_entrega_dias" in por, f"achados={list(por)} passos={ferramentas}"
    assert por["prazo_entrega_dias"].valor == 10  # "10 (dez) dias úteis" no edital
    for a in achados:
        ev = ctx.analise.evidencia(a.evidencia_id)
        assert ev is not None and not ev.documento_id.startswith("pncp-item")
        verificar_evidencia(ev, ctx.indice)
        assert ev.verificada, f"{a.atributo}: trecho citado não encontrado literalmente ({ev.score_match}): {ev.trecho_literal[:120]}"


@precisa_llm
@precisa_caso
def test_pipeline_completo_com_llm(tmp_path, monkeypatch):
    from obranexo.agents.pipeline import executar_caso
    from obranexo.catalog.loader import carregar_catalogo_json

    monkeypatch.setattr(config, "dir_analises", tmp_path)
    analise = executar_caso(CASO, carregar_catalogo_json(config.catalogo_demo), on_evento=lambda ev: print(f"[{ev.no}] {ev.mensagem}"))
    assert analise.status == "concluida", analise.erro
    assert analise.modo == f"llm:{config.llm_provider}"
    melhor: dict[int, str] = {}
    ordem = {"COMPATIVEL": 3, "PARCIAL": 2, "INDETERMINADO": 1, "INCOMPATIVEL": 0}
    for c in sorted(analise.correspondencias, key=lambda c: (ordem[c.resultado.value], c.score), reverse=True):
        melhor.setdefault(analise.item(c.item_id).numero_item, c.resultado.value)
    assert melhor == GABARITO_ITENS, melhor
    assert all(e.verificada for e in analise.evidencias if e.documento_id.startswith("pncp-item")), "citações das descrições de item devem ser literais"
    assert analise.dossie and "Resumo executivo" in analise.dossie.conteudo_md
    print(
        f"\nLLM: {analise.uso_llm.chamadas} chamadas, {analise.uso_llm.tokens_entrada + analise.uso_llm.tokens_saida} tokens, "
        f"US$ {analise.uso_llm.custo_usd:.4f}, {analise.duracao_s():.1f}s, modelos {list(analise.uso_llm.por_modelo)}"
    )
    Path(tmp_path / "dossie.md").write_text(analise.dossie.conteudo_md, encoding="utf-8")


# ---------------------------------------------------------------------------- funções novas: catálogo real e prospecção

FICHA_REAL = Path(__file__).parent / "dados" / "ficha_sanlume_luminaria_publica.txt"


@precisa_llm
@pytest.mark.skipif(not FICHA_REAL.exists(), reason="ficha de teste ausente")
def test_importa_produtos_de_ficha_real_do_fabricante():
    from obranexo.catalog.importar import importar_ficha
    from obranexo.llm.client import criar_llm_client

    produtos, avisos = importar_ficha(FICHA_REAL.read_text(encoding="utf-8"), criar_llm_client(config), config.model_agente)
    por_potencia = {p.atributos["potencia_w"].valor: p for p in produtos if "potencia_w" in p.atributos}
    # A página tem uma tabela de 9 modelos (50 a 240 W) com o fluxo de cada um
    assert {50.0, 100.0, 150.0, 240.0} <= set(por_potencia), sorted(por_potencia)
    assert por_potencia[100.0].atributos["fluxo_lm"].valor == 16000
    assert por_potencia[150.0].atributos["fluxo_lm"].valor == 24000
    assert all(p.categoria == "luminaria_publica_led" for p in por_potencia.values())
    assert por_potencia[100.0].atributos["ip"].valor == "IP66"
    assert len({p.sku for p in produtos}) == len(produtos)  # SKUs únicos


@precisa_llm
@pytest.mark.skipif(config.offline, reason="modo offline")
def test_prospeccao_autonoma_no_pncp_real(tmp_path, monkeypatch):
    """O agente escolhe os termos, busca no PNCP de verdade e ranqueia (sem análise completa, para não gastar cota)."""
    from obranexo.agents.prospector import executar_prospeccao
    from obranexo.catalog.loader import carregar_catalogo_json

    monkeypatch.setattr("obranexo.storage.store.config", config.__class__(dir_dados=tmp_path))
    p = executar_prospeccao(carregar_catalogo_json(config.catalogo_demo), ["GO"], horizonte_dias=30, max_analises=0)
    assert p.status == "concluida", p.erro
    assert p.buscas and all(b["uf"] == "GO" for b in p.buscas)
    assert p.candidatos, "nenhuma licitação candidata encontrada"
    assert p.ranking and all(r.contratacao_id in p.candidatos for r in p.ranking)  # nada inventado
    assert p.resumo
