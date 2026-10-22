"""Interface de demonstração do ObraNexo (MVP-08).

Execute:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from obranexo import __version__  # noqa: E402
from obranexo.agents.pipeline import executar_analise  # noqa: E402
from obranexo.catalog.atributos import rotulo  # noqa: E402
from obranexo.catalog.loader import carregar_catalogo_json, carregar_catalogo_tabela  # noqa: E402
from obranexo.config import config  # noqa: E402
from obranexo.connectors.pncp import PNCPClient, PNCPError, carregar_caso, listar_casos  # noqa: E402
from obranexo.documents.extract import IndiceDocumentos  # noqa: E402
from obranexo.models import ResultadoItem, StatusRevisao  # noqa: E402
from obranexo.storage import store  # noqa: E402

st.set_page_config(page_title="ObraNexo", page_icon="🔆", layout="wide")

ICONE = {"COMPATIVEL": "✅", "PARCIAL": "🟡", "INDETERMINADO": "❔", "INCOMPATIVEL": "❌"}


# --------------------------------------------------------------------------- estado


def empresa_atual():
    if "empresa" not in st.session_state:
        st.session_state.empresa = carregar_catalogo_json(config.catalogo_demo)
    return st.session_state.empresa


def moeda(v):
    return "—" if v is None else "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.title("🔆 ObraNexo")
    st.caption(f"v{__version__} · AKCIT Camp 2026")
    pagina = st.radio("Navegação", ["Catálogo", "Demandas", "Análise", "Dossiê", "Métricas", "Como funciona"], label_visibility="collapsed")
    st.divider()
    modo = f"🤖 LLM ({config.llm_provider})" if config.llm_disponivel else "⚙️ determinístico (sem chave de API)"
    st.caption(f"Modo: {modo}")
    if config.llm_disponivel:
        st.caption(f"Agentes: `{config.model_agente}`\n\nExtração: `{config.model_extracao}`")
    st.caption("PNCP: " + ("offline (pacotes congelados)" if config.offline else "online + cache"))

# =========================================================================== Catálogo
if pagina == "Catálogo":
    empresa = empresa_atual()
    st.header("Perfil comercial e catálogo")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader(empresa.nome)
        st.write(f"UFs atendidas: **{', '.join(empresa.ufs_atendidas) or '—'}** · raio: {empresa.raio_km or '—'} km · {len(empresa.produtos)} produtos")
        if empresa.observacoes:
            st.info(empresa.observacoes)
    with c2:
        arquivo = st.file_uploader("Carregar outro catálogo (JSON / CSV / XLSX)", type=["json", "csv", "xlsx"])
        if arquivo is not None:
            destino = config.dir_cache / f"upload_{arquivo.name}"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(arquivo.getvalue())
            st.session_state.empresa = carregar_catalogo_json(destino) if destino.suffix == ".json" else carregar_catalogo_tabela(destino)
            st.success(f"Catálogo carregado: {len(st.session_state.empresa.produtos)} produtos")
            st.rerun()
    linhas = []
    for p in empresa.produtos:
        a = {k: v.valor for k, v in p.atributos.items()}
        linhas.append(
            {"SKU": p.sku, "Produto": p.nome, "Categoria": p.categoria, "Potência (W)": a.get("potencia_w"), "Tensão (V)": a.get("tensao_v"),
             "CCT (K)": a.get("cct_k"), "Fluxo (lm)": a.get("fluxo_lm"), "lm/W": a.get("eficiencia_lm_w"), "IP": a.get("ip"), "IK": a.get("ik"),
             "Garantia (anos)": a.get("garantia_anos"), "INMETRO": a.get("inmetro"), "Dimerizável": a.get("dimerizavel"), "Preço ref.": p.preco_ref}
        )
    st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True, height=560)
    with st.expander("Ver um produto em detalhe"):
        sku = st.selectbox("SKU", [p.sku for p in empresa.produtos])
        p = next(x for x in empresa.produtos if x.sku == sku)
        st.json({"nome": p.nome, "categoria": p.categoria, "descricao": p.descricao, "atributos": {k: {"valor": v.valor, "unidade": v.unidade} for k, v in p.atributos.items()},
                 "normas": p.normas, "certificacoes": p.certificacoes, "prazo_entrega_dias": p.prazo_entrega_dias})

# =========================================================================== Demandas
elif pagina == "Demandas":
    st.header("Demandas públicas")
    aba1, aba2 = st.tabs(["Casos congelados (demo reproduzível)", "Buscar no PNCP (ao vivo)"])
    with aba1:
        casos = listar_casos()
        if not casos:
            st.warning("Nenhum caso em data/casos. Use `obranexo coletar` ou a aba ao vivo.")
        for d in casos:
            c, itens, docs = carregar_caso(d)
            with st.container(border=True):
                a, b = st.columns([4, 1])
                with a:
                    st.markdown(f"**{c.orgao_nome}** — {c.municipio}/{c.uf} · {c.modalidade} · {c.id}")
                    st.write(c.objeto)
                    enc = c.data_encerramento_proposta.strftime("%d/%m/%Y") if c.data_encerramento_proposta else "—"
                    st.caption(f"Valor estimado {moeda(c.valor_estimado)} · encerramento de propostas {enc} · {len(itens)} itens · {len(docs)} anexos · {c.link_oficial}")
                with b:
                    if st.button("Selecionar", key=f"sel-{d.name}", width="stretch"):
                        st.session_state.caso = d
                        st.session_state.pop("analise", None)
                        st.success("Selecionado. Vá para **Análise**.")
    with aba2:
        if config.offline:
            st.info("OBRANEXO_OFFLINE=1: busca ao vivo desativada.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            uf = c1.text_input("UF", "GO")
            dias = c2.number_input("Últimos N dias", 7, 180, 30)
            palavras = c3.text_input("Palavras no objeto (vírgula)", "lumin,led,refletor,ilumina,material elétrico")
            so_abertas = c4.checkbox("Só propostas em aberto", value=True)
            if st.button("Buscar no PNCP"):
                cli = PNCPClient()
                lista_pal = [p.strip() for p in palavras.split(",") if p.strip()]
                achados, pagina_n, total = [], 1, 1
                with st.spinner("Consultando o PNCP…"):
                    try:
                        while pagina_n <= total and pagina_n <= 8:
                            if so_abertas:
                                lista, total = cli.buscar_propostas_abertas(datetime.now().strftime("%Y%m%d"), uf=uf, pagina=pagina_n)
                            else:
                                fim = datetime.now()
                                lista, total = cli.buscar_publicacoes((fim - timedelta(days=int(dias))).strftime("%Y%m%d"), fim.strftime("%Y%m%d"), uf=uf, pagina=pagina_n)
                            achados += cli.filtrar_por_palavras(lista, lista_pal) if lista_pal else lista
                            pagina_n += 1
                    except PNCPError as exc:
                        st.error(f"PNCP indisponível: {exc}")
                st.session_state.busca = achados
            for c in st.session_state.get("busca", []):
                with st.container(border=True):
                    a, b = st.columns([4, 1])
                    enc = c.data_encerramento_proposta.strftime("%d/%m/%Y") if c.data_encerramento_proposta else "—"
                    a.markdown(f"**{c.orgao_nome}** — {c.municipio}/{c.uf} · {c.id}  \n{c.objeto}  \n*{moeda(c.valor_estimado)} · encerra {enc}*")
                    if b.button("Baixar e selecionar", key=f"dl-{c.id}", width="stretch"):
                        nome = f"{c.orgao_cnpj}_{c.ano}_{c.sequencial}"
                        with st.spinner("Baixando itens e anexos…"):
                            PNCPClient().coletar_caso(c.orgao_cnpj, c.ano, c.sequencial, config.dir_casos / nome)
                        st.session_state.caso = config.dir_casos / nome
                        st.session_state.pop("analise", None)
                        st.success("Caso congelado em data/casos. Vá para **Análise**.")

# =========================================================================== Análise
elif pagina == "Análise":
    st.header("Análise assistida por agentes")
    caso = st.session_state.get("caso")
    if not caso:
        casos = listar_casos()
        if casos:
            caso = st.selectbox("Selecione um caso", casos, format_func=lambda p: p.name)
            st.session_state.caso = caso
        else:
            st.warning("Selecione uma demanda na página **Demandas**.")
            st.stop()
    c, itens, docs = carregar_caso(caso)
    empresa = empresa_atual()
    st.markdown(f"**{c.orgao_nome}** · {c.id} · {len(itens)} itens · {len(docs)} anexos · catálogo **{empresa.nome}**")
    with st.expander("Itens da contratação"):
        st.dataframe(pd.DataFrame([{"Item": i.numero_item, "Descrição": i.descricao, "Qtd": i.quantidade, "Un": i.unidade, "Valor unit.": i.valor_unit_estimado} for i in itens]), width="stretch", hide_index=True)
    if st.button("▶ Executar análise", type="primary"):
        status = st.status("Executando o fluxo agêntico…", expanded=True)
        log = status.container()

        def on_evento(ev):
            log.write(f"`{ev.no}` {ev.mensagem}")

        analise = executar_analise(empresa, c, itens, docs, on_evento=on_evento)
        if analise.status == "concluida":
            status.update(label=f"Concluído em {analise.duracao_s():.1f}s · modo {analise.modo} · custo US$ {analise.uso_llm.custo_usd:.4f}", state="complete", expanded=False)
        else:
            status.update(label=f"Erro: {analise.erro}", state="error")
        st.session_state.analise = analise
    analise = st.session_state.get("analise")
    if analise and analise.status == "concluida":
        q = analise.qualificacao
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tipo", q.tipo_oportunidade.value)
        m2.metric("Prazo", q.prazo_status)
        m3.metric("Prioridade", f"{q.prioridade:.0f}/100")
        m4.metric("Evidências verificadas", f"{sum(e.verificada for e in analise.evidencias)}/{len(analise.evidencias)}")
        st.subheader("Correspondência técnica por item")
        produtos = {p.id: p for p in empresa.produtos}
        reqs = {r.id: r for r in analise.requisitos}
        ordem = {ResultadoItem.COMPATIVEL: 3, ResultadoItem.PARCIAL: 2, ResultadoItem.INDETERMINADO: 1, ResultadoItem.INCOMPATIVEL: 0}
        for item in analise.itens:
            cs = sorted((x for x in analise.correspondencias if x.item_id == item.id), key=lambda x: (ordem[x.resultado], x.score), reverse=True)
            titulo = f"Item {item.numero_item} — {item.descricao[:80]}…"
            if not cs:
                with st.expander(f"⬜ {titulo}  ·  fora do portfólio ({item.categoria_inferida})"):
                    st.write(item.descricao)
                continue
            melhor = cs[0]
            with st.expander(f"{ICONE[melhor.resultado.value]} {titulo}  ·  {melhor.resultado.value} ({produtos[melhor.produto_id].sku})"):
                st.write(item.descricao)
                for corr in cs:
                    p = produtos[corr.produto_id]
                    st.markdown(f"**{ICONE[corr.resultado.value]} {p.sku} — {p.nome}** · score {corr.score:.2f} · confiança {corr.confianca.value}")
                    tabela = []
                    for d in corr.detalhes:
                        r = reqs.get(d.requisito_id)
                        ev = analise.evidencia(r.evidencia_id) if r else None
                        tabela.append({"Requisito": rotulo(d.atributo) + ("" if (r and r.obrigatorio) else " (desejável)"), "Exigido": str(d.valor_exigido), "Produto": str(d.valor_produto),
                                       "Resultado": f"{ {'ATENDE': '✅', 'NAO_ATENDE': '❌', 'INDETERMINADO': '❔'}[d.resultado.value] } {d.resultado.value}",
                                       "Justificativa": d.justificativa, "Evidência": f"{ev.documento_id} p.{ev.pagina} {'✔' if ev.verificada else '⚠'}" if ev else "—", "Fonte": r.fonte_extracao if r else "—"})
                    st.dataframe(pd.DataFrame(tabela), width="stretch", hide_index=True)
        if analise.passos_investigacao:
            with st.expander("🔎 Trilha do Agente Investigador"):
                for p in analise.passos_investigacao:
                    if p.get("tipo") == "ferramenta":
                        st.markdown(f"- Passo {p['passo']}: `{p['ferramenta']}` `{p['entrada']}` → {str(p['saida'])[:300]}")
                    else:
                        st.markdown(f"- Passo {p['passo']}: {p['texto'][:400]}")
        if analise.lacunas or analise.conflitos or analise.revisao_humana:
            with st.expander("⚠️ Lacunas, conflitos e pendências de revisão humana", expanded=True):
                for x in analise.lacunas:
                    st.write("• Lacuna: " + x)
                for x in analise.conflitos:
                    st.write("• Conflito: " + x.descricao)
                for x in analise.revisao_humana:
                    st.write("• " + x)
        st.info("Veja o dossiê completo na página **Dossiê**.")

# =========================================================================== Dossiê
elif pagina == "Dossiê":
    st.header("Dossiê comercial")
    analises = store.listar()
    atual = st.session_state.get("analise")
    opcoes = ([atual] if atual and atual.status == "concluida" else []) + [a for a in analises if not atual or a.id != atual.id]
    if not opcoes:
        st.warning("Nenhuma análise ainda. Execute uma na página **Análise**.")
        st.stop()
    escolha = st.selectbox("Análise", opcoes, format_func=lambda a: f"{a.id} · {a.contratacao.orgao_nome[:40]} · {a.contratacao.id}")
    if escolha.dossie is None:
        st.error(escolha.erro or "Análise sem dossiê.")
        st.stop()
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.download_button("⬇ Baixar dossiê (.md)", escolha.dossie.conteudo_md, file_name=f"dossie_{escolha.id}.md", mime="text/markdown")
    c2.download_button("⬇ Baixar análise (.json)", escolha.model_dump_json(indent=1), file_name=f"analise_{escolha.id}.json", mime="application/json")
    with c3:
        novo = st.radio("Revisão humana", ["PENDENTE", "APROVADO", "REJEITADO"], index=["PENDENTE", "APROVADO", "REJEITADO"].index(escolha.dossie.status_revisao.value), horizontal=True)
        comentario = st.text_input("Comentário", escolha.dossie.comentario_usuario)
        if st.button("Salvar revisão"):
            escolha.dossie.status_revisao = StatusRevisao(novo)
            escolha.dossie.comentario_usuario = comentario
            store.salvar(escolha)
            st.success("Revisão salva (feedback registrado para o benchmark).")
    st.markdown(escolha.dossie.conteudo_md)
    with st.expander("🔍 Abrir uma evidência no documento"):
        evs = [e for e in escolha.evidencias]
        if evs:
            ev = st.selectbox("Evidência", evs, format_func=lambda e: f"{e.id} · {e.documento_id} p.{e.pagina} · {'verificada' if e.verificada else 'NÃO verificada'}")
            doc = next((d for d in escolha.documentos if d.id == ev.documento_id), None)
            st.markdown(f"**Trecho citado:** “{ev.trecho_literal}”")
            if doc and doc.caminho_local and Path(doc.caminho_local).exists() and ev.pagina:
                idx = IndiceDocumentos()
                idx.adicionar(doc)
                texto = idx.ler_pagina(doc.id, ev.pagina) or ""
                st.text_area(f"{doc.nome} — página {ev.pagina}", texto, height=400)
                st.caption(f"Arquivo: {doc.caminho_local} · origem: {doc.url_origem}")
            elif doc and doc.id.startswith("pncp-item"):
                item = next((i for i in escolha.itens if f"pncp-item-{i.numero_item}" == doc.id), None)
                st.text_area(doc.nome, item.descricao if item else "", height=200)
                st.caption(f"Origem: {doc.url_origem}")

# =========================================================================== Métricas
elif pagina == "Métricas":
    st.header("Métricas de execução")
    analises = store.listar()
    if not analises:
        st.info("Sem análises registradas.")
        st.stop()
    linhas = []
    for a in analises:
        ev_total = len(a.evidencias)
        ev_ok = sum(e.verificada for e in a.evidencias)
        melhor = {}
        for c in a.correspondencias:
            melhor.setdefault(c.item_id, c.resultado.value)
        linhas.append({"Análise": a.id, "Contratação": a.contratacao.id, "Modo": a.modo, "Status": a.status, "Duração (s)": round(a.duracao_s() or 0, 1),
                       "Chamadas LLM": a.uso_llm.chamadas, "Tokens": a.uso_llm.tokens_entrada + a.uso_llm.tokens_saida, "Custo (US$)": a.uso_llm.custo_usd,
                       "Evidências verificadas": f"{ev_ok}/{ev_total}", "Itens": len(a.itens), "Compatíveis": sum(1 for v in melhor.values() if v == "COMPATIVEL"),
                       "Incompatíveis": sum(1 for v in melhor.values() if v == "INCOMPATIVEL"), "Indeterminados": sum(1 for v in melhor.values() if v == "INDETERMINADO"),
                       "Revisão": a.dossie.status_revisao.value if a.dossie else "—"})
    st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    st.caption("Custo estimado com a tabela de preços em config.py. Benchmark completo: `python eval/run_benchmark.py`.")

# =========================================================================== Como funciona
else:
    st.header("Como o ObraNexo funciona")
    st.markdown((RAIZ / "docs" / "fluxo_agentes.md").read_text(encoding="utf-8"))
