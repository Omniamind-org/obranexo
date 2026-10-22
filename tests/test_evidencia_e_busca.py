from obranexo.documents.extract import IndiceDocumentos, gerar_trechos
from obranexo.evidence.verify import verificar_evidencia
from obranexo.models import Documento, Evidencia


def _indice():
    idx = IndiceDocumentos()
    doc = Documento(id="edital", contratacao_id="x", nome="edital.pdf")
    idx.documentos[doc.id] = doc
    paginas = [
        "1. DO OBJETO\nRegistro de preços para aquisição de luminárias.\n\n2. DA ENTREGA\nO prazo de entrega será de 30 (trinta) dias corridos a contar da ordem de fornecimento.",
        "3. DA GARANTIA\nA garantia mínima dos produtos é de 5 (cinco) anos contados do recebimento definitivo.",
    ]
    idx.paginas[doc.id] = paginas
    idx.trechos = gerar_trechos(doc.id, paginas)
    for t in idx.trechos:
        from obranexo.documents.extract import normalizar_busca

        idx._norm[t.id] = normalizar_busca(t.texto)
    return idx


def test_busca_encontra_pagina_certa():
    idx = _indice()
    res = idx.buscar("prazo de entrega", top_k=1)
    assert res and res[0].trecho.pagina == 1
    res = idx.buscar("garantia mínima", top_k=1)
    assert res and res[0].trecho.pagina == 2


def test_verificacao_de_evidencia():
    idx = _indice()
    ok = verificar_evidencia(Evidencia(id="e1", documento_id="edital", pagina=2, trecho_literal="garantia mínima dos produtos é de 5 (cinco) anos"), idx)
    assert ok.verificada and ok.score_match >= 90
    corrigida = verificar_evidencia(Evidencia(id="e2", documento_id="edital", pagina=1, trecho_literal="garantia mínima dos produtos é de 5 (cinco) anos"), idx)
    assert corrigida.verificada and corrigida.pagina == 2  # página corrigida pelo verificador
    falsa = verificar_evidencia(Evidencia(id="e3", documento_id="edital", pagina=1, trecho_literal="garantia de 10 anos com troca imediata"), idx)
    assert not falsa.verificada


def test_investigador_por_regras_acha_prazo_e_garantia():
    from obranexo.agents.contexto import Contexto
    from obranexo.agents.investigador import investigar_regras
    from obranexo.config import Config
    from obranexo.llm.client import criar_llm_client
    from obranexo.models import Analise, Contratacao, Empresa

    cfg = Config(llm_provider=None, anthropic_api_key=None, gemini_api_key=None)
    analise = Analise(id="t", empresa_id="e", contratacao=Contratacao(id="c", orgao_cnpj="0", orgao_nome="Org", ano=2026, sequencial=1, objeto="x"))
    ctx = Contexto(analise=analise, empresa=Empresa(id="e", nome="E"), indice=_indice(), llm=criar_llm_client(cfg), cfg=cfg)
    assert not ctx.usar_llm
    achados = investigar_regras(ctx, ["prazo_entrega_dias", "garantia_anos", "doc_amostra"])
    por = {a.atributo: a for a in achados}
    assert por["prazo_entrega_dias"].valor == 30
    assert por["garantia_anos"].valor == 5
    assert "doc_amostra" not in por and any("amostra" in lac.lower() for lac in analise.lacunas)
    for a in achados:
        ev = analise.evidencia(a.evidencia_id)
        assert verificar_evidencia(ev, ctx.indice).verificada
