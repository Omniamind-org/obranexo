// Resultado de uma análise: resumo, itens × catálogo, evidências, trilha do Investigador, pendências e dossiê.

import { api } from '../api.js';
import { data, local, moeda, numero, OPERADOR, pct, valorTecnico } from '../format.js';
import { renderMarkdown } from '../markdown.js';
import {
  abrirModal, badgeConfianca, badgePrazo, badgeRequisito, badgeResultado, badgeRevisao, badgeTipo,
  esc, html, icon, raw, render, toast, vazio,
} from '../ui.js';
import { barraResultados, legendaResultados } from './analises.js';
import { rotuloCategoria } from './catalogo.js';

const ORDEM = { COMPATIVEL: 3, PARCIAL: 2, INDETERMINADO: 1, INCOMPATIVEL: 0 };

export async function render_(el, id) {
  const dados = await api.analise(id);
  const { analise: a, resumo, produtos, atributos } = dados;
  const ctx = montarContexto(a, produtos, atributos);
  const c = a.contratacao;

  if (a.status !== 'concluida') {
    render(el, html`<div class="crumbs"><a href="#/analises">Análises</a> / ${a.id}</div>
      <div class="alert alert-bad">${icon('alert')}<div class="alert-body"><strong>A análise terminou com erro.</strong> ${a.erro}</div></div>`);
    return;
  }

  const abas = [
    ['resumo', 'Resumo', null],
    ['itens', 'Itens × catálogo', a.itens.length],
    ['evidencias', 'Evidências', a.evidencias.length],
    ['investigacao', 'Investigação', a.passos_investigacao.length],
    ['pendencias', 'Pendências', a.lacunas.length + a.conflitos.length + a.revisao_humana.length],
    ['dossie', 'Dossiê', null],
  ];

  render(el, html`
    <div class="crumbs"><a href="#/analises">Análises</a> / ${a.id}</div>
    <div class="page-head">
      <div>
        <div class="eyebrow">${c.modalidade || 'Contratação'}${c.numero_compra ? ` nº ${c.numero_compra}/${c.ano}` : ''} · ${local(c)}</div>
        <h1>${c.orgao_nome}</h1>
        <p class="clamp-2">${c.objeto}</p>
        <div class="chips" style="margin-top:10px">
          ${badgeTipo(resumo.tipo_oportunidade)} ${badgePrazo(resumo.prazo_status)} ${badgeRevisao(resumo.revisao)}
          <span class="badge plain mono">${a.modo}</span>
        </div>
      </div>
      <div class="actions">
        ${resumo.caso ? html`<a class="btn" href="#/casos/${resumo.caso}">${icon('refresh')} Reexecutar</a>` : ''}
        <a class="btn" href="${c.link_oficial}" target="_blank" rel="noopener">${icon('external')} PNCP</a>
        <a class="btn btn-primary" href="${api.dossieDownloadUrl(a.id)}">${icon('download')} Dossiê .md</a>
      </div>
    </div>
    <div class="tabs" role="tablist">
      ${abas.map(([k, n, cnt], i) => html`<button class="tab ${i === 0 ? 'ativo' : ''}" data-aba="${k}">${n}${cnt !== null ? html`<span class="count">${cnt}</span>` : ''}</button>`)}
    </div>
    <div id="conteudo"></div>`);

  const conteudo = el.querySelector('#conteudo');
  const telas = {
    resumo: () => telaResumo(conteudo, a, resumo, ctx),
    itens: () => telaItens(conteudo, a, ctx),
    evidencias: () => telaEvidencias(conteudo, a, ctx),
    investigacao: () => telaInvestigacao(conteudo, a),
    pendencias: () => telaPendencias(conteudo, a, ctx),
    dossie: () => telaDossie(conteudo, a),
  };
  const abrir = (k) => {
    el.querySelectorAll('.tab').forEach((t) => t.classList.toggle('ativo', t.dataset.aba === k));
    telas[k]();
  };
  el.querySelector('.tabs').addEventListener('click', (e) => { const b = e.target.closest('.tab'); if (b) abrir(b.dataset.aba); });
  // Botões de evidência em qualquer aba abrem o modal de conferência
  conteudo.addEventListener('click', (e) => {
    const b = e.target.closest('[data-ev]');
    if (b) abrirEvidencia(a, ctx, b.dataset.ev);
    const irAba = e.target.closest('[data-ir-aba]');
    if (irAba) abrir(irAba.dataset.irAba);
  });
  abrir('resumo');
}

// ---------------------------------------------------------------------------- contexto

function montarContexto(a, produtos, atributos) {
  const reqs = Object.fromEntries(a.requisitos.map((r) => [r.id, r]));
  const evs = Object.fromEntries(a.evidencias.map((e) => [e.id, e]));
  const docs = Object.fromEntries(a.documentos.map((d) => [d.id, d]));
  const porItem = {};
  a.correspondencias.forEach((c) => { (porItem[c.item_id] ||= []).push(c); });
  Object.values(porItem).forEach((l) => l.sort((x, y) => (ORDEM[y.resultado] - ORDEM[x.resultado]) || (y.score - x.score)));
  return {
    reqs, evs, docs, porItem, produtos,
    rotulo: (k) => atributos[k]?.rotulo || k,
    unidade: (k) => atributos[k]?.unidade || '',
  };
}

const evBotao = (ctx, evId) => {
  const ev = ctx.evs[evId];
  if (!ev) return html`<span class="muted small">sem evidência</span>`;
  const doc = ctx.docs[ev.documento_id];
  const nome = doc ? doc.nome.replace(/\.pdf$/i, '') : ev.documento_id;
  return html`<button class="ev-link ${ev.verificada ? '' : 'nv'}" data-ev="${ev.id}" title="${ev.trecho_literal}">
    ${icon(ev.verificada ? 'quote' : 'alert')}<span class="truncate" style="max-width:190px">${nome}${ev.pagina ? `, p.${ev.pagina}` : ''}</span></button>`;
};

// ---------------------------------------------------------------------------- resumo

function telaResumo(alvo, a, resumo, ctx) {
  const q = a.qualificacao;
  const evOk = resumo.evidencias_verificadas;
  const passos = q.proximos_passos || [];
  const riscos = q.riscos || [];
  const itensCompat = a.itens
    .map((i) => ({ i, m: ctx.porItem[i.id]?.[0] }))
    .filter(({ m }) => m && (m.resultado === 'COMPATIVEL' || m.resultado === 'PARCIAL'));
  const valorCompat = itensCompat.reduce((s, { i }) => s + (i.quantidade || 0) * (i.valor_unit_estimado || 0), 0);

  render(alvo, html`
    <div class="grid grid-main">
      <div class="stack">
        <div class="card card-pad">
          <div class="qualif">
            <div class="score-ring" style="--v:${q.prioridade}"><span>${Math.round(q.prioridade)}</span></div>
            <div>
              <div class="kpi-label">Prioridade comercial</div>
              <div style="font-weight:650;margin:2px 0 4px">${q.comprador_provavel}</div>
              <div class="muted small">${q.justificativa_prioridade}</div>
            </div>
          </div>
          <hr>
          <div class="section-title" style="margin-top:0">Resumo executivo</div>
          <p style="margin:0">${a.dossie?.resumo_executivo}</p>
        </div>

        <div class="card">
          <div class="card-head"><h2>Resultado por item</h2><button class="btn btn-ghost btn-sm" data-ir-aba="itens">Ver itens ${icon('arrow')}</button></div>
          <div class="card-body">
            ${barraResultados(resumo.resultados)}
            ${legendaResultados(resumo.resultados)}
            ${itensCompat.length ? html`<div class="alert alert-ok" style="margin-top:14px">${icon('check')}<div class="alert-body">
              <strong>${moeda(valorCompat)}</strong> do valor estimado está em ${itensCompat.length} item(ns) que o catálogo atende total ou parcialmente.</div></div>` : ''}
            ${a.insumos_indiretos?.length ? html`<div class="alert alert-info" style="margin-top:14px">${icon('layers')}<div class="alert-body">
              Oportunidade indireta: ${a.insumos_indiretos.length} menção(ões) a insumos do portfólio nos projetos e orçamentos. <button class="ev-link" data-ir-aba="itens">Ver insumos</button></div></div>` : ''}
          </div>
        </div>

        <div class="grid grid-2">
          <div class="card">
            <div class="card-head"><h2>Próximos passos</h2></div>
            <div class="card-body"><ol style="margin:0;padding-left:20px">${passos.map((p) => html`<li style="margin:4px 0">${p}</li>`)}</ol></div>
          </div>
          <div class="card">
            <div class="card-head"><h2>Riscos</h2></div>
            <div class="card-body">${riscos.length ? html`<ul style="margin:0;padding-left:20px">${riscos.map((r) => html`<li style="margin:4px 0">${r}</li>`)}</ul>` : html`<span class="muted">Nenhum risco adicional identificado.</span>`}</div>
          </div>
        </div>
      </div>

      <div class="stack">
        <div class="card">
          <div class="card-head"><h2>Classificação</h2></div>
          <div class="card-body">
            <dl class="dl">
              <dt>Tipo</dt><dd>${badgeTipo(q.tipo_oportunidade)}</dd>
              <dt>Comprador</dt><dd>${q.comprador_provavel}</dd>
              <dt>Prazo</dt><dd>${badgePrazo(q.prazo_status)}<div class="muted small" style="margin-top:4px">${q.prazo_observacao}</div></dd>
              <dt>Valor</dt><dd>${moeda(a.contratacao.valor_estimado)}</dd>
              <dt>SRP</dt><dd>${a.contratacao.srp ? 'sim (registro de preços)' : 'não'}</dd>
            </dl>
            <p class="muted small" style="margin:12px 0 0">${q.justificativa_tipo}</p>
          </div>
        </div>
        <div class="grid grid-2">
          <div class="card kpi"><div class="kpi-label">Evidências</div><div class="kpi-value ${evOk === resumo.evidencias_total ? 'ok' : 'warn'}">${pct(resumo.evidencias_total ? evOk / resumo.evidencias_total : null)}</div><div class="kpi-sub">${evOk}/${resumo.evidencias_total} verificadas</div></div>
          <div class="card kpi"><div class="kpi-label">Pendências</div><div class="kpi-value ${resumo.conflitos || resumo.lacunas ? 'warn' : ''}">${resumo.lacunas + resumo.conflitos}</div><div class="kpi-sub">${resumo.lacunas} lacuna(s), ${resumo.conflitos} conflito(s)</div></div>
          <div class="card kpi"><div class="kpi-label">Duração</div><div class="kpi-value">${numero(resumo.duracao_s)}s</div><div class="kpi-sub">${data(a.iniciada_em, true)}</div></div>
          <div class="card kpi"><div class="kpi-label">Uso de LLM</div><div class="kpi-value">${resumo.llm.chamadas}</div><div class="kpi-sub">${numero(resumo.llm.tokens)} tokens · US$ ${resumo.llm.custo_usd.toFixed(4)}</div></div>
        </div>
        ${resumo.llm.modelos.length ? html`<div class="muted small">Modelos: ${resumo.llm.modelos.map((m) => html`<span class="mono">${m}</span> `)}</div>` : ''}
      </div>
    </div>`);
}

// ---------------------------------------------------------------------------- itens

function telaItens(alvo, a, ctx) {
  const blocoProduto = (c) => {
    const p = ctx.produtos[c.produto_id] || { sku: c.produto_id, nome: '' };
    return html`
      <div class="produto-bloco">
        <div class="produto-head">
          <div><strong class="mono">${p.sku}</strong> — ${p.nome}</div>
          <div class="chips">${badgeResultado(c.resultado)} ${badgeConfianca(c.confianca)} <span class="badge plain">score ${c.score.toFixed(2)}</span></div>
        </div>
        <div class="table-wrap" style="border:1px solid var(--border);border-radius:8px"><table class="table">
          <thead><tr><th>Requisito</th><th>Exigido</th><th>Produto</th><th>Resultado</th><th>Origem</th><th>Evidência</th></tr></thead>
          <tbody>${c.detalhes.map((d) => {
            const r = ctx.reqs[d.requisito_id] || {};
            const op = OPERADOR[r.operador] || r.operador || '';
            const mostraOp = op && !['exigido', 'contém'].includes(op);
            return html`<tr title="${d.justificativa}">
              <td>${ctx.rotulo(d.atributo)}${r.obrigatorio === false ? html` <span class="muted small">(desejável)</span>` : ''}</td>
              <td class="nowrap">${mostraOp ? `${op} ` : ''}${valorTecnico(d.valor_exigido, ctx.unidade(d.atributo))}</td>
              <td>${valorTecnico(d.valor_produto, ctx.unidade(d.atributo))}</td>
              <td>${badgeRequisito(d.resultado)}</td>
              <td class="small muted">${r.fonte_extracao || '—'}</td>
              <td>${evBotao(ctx, r.evidencia_id)}</td>
            </tr>`;
          })}</tbody>
        </table></div>
      </div>`;
  };

  const insumos = a.insumos_indiretos || [];
  render(alvo, html`
    ${insumos.length ? html`
      <div class="card" style="margin-bottom:16px">
        <div class="card-head"><h2>Insumos do portfólio nos projetos/orçamentos</h2><span class="muted small">oportunidade indireta</span></div>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>Categoria</th><th>Documento</th><th>Trecho</th><th>Evidência</th></tr></thead>
          <tbody>${insumos.map((i) => html`<tr><td class="nowrap">${rotuloCategoria(i.categoria)}</td><td class="small">${ctx.docs[i.documento_id]?.nome || i.documento_id}, p.${i.pagina}</td>
            <td class="small"><div class="clamp-2">${i.trecho}</div></td><td>${evBotao(ctx, i.evidencia_id)}</td></tr>`)}</tbody>
        </table></div>
      </div>` : ''}
    ${a.itens.map((item) => {
      const cs = ctx.porItem[item.id] || [];
      const melhor = cs[0];
      const p = melhor ? ctx.produtos[melhor.produto_id] : null;
      return html`
        <details class="item">
          <summary>
            <span class="item-num">Item ${item.numero_item}</span>
            <span class="item-desc">
              <span class="t clamp-2">${item.descricao}</span>
              <span class="muted small">${numero(item.quantidade)} ${item.unidade || ''} · ${moeda(item.valor_unit_estimado)} un. · ${rotuloCategoria(item.categoria_inferida)}</span>
            </span>
            <span style="text-align:right">${melhor ? html`${badgeResultado(melhor.resultado)}<div class="mono small muted" style="margin-top:4px">${p?.sku}</div>` : badgeResultado('FORA_DO_PORTFOLIO')}</span>
          </summary>
          <div class="item-body">
            <p class="small" style="margin-top:0;color:var(--text-2)">${item.descricao}</p>
            ${cs.length ? cs.map(blocoProduto) : html`<div class="alert alert-info">${icon('info')}<div class="alert-body">Categoria <strong>${rotuloCategoria(item.categoria_inferida)}</strong> não existe no catálogo ativo — item fora do portfólio.</div></div>`}
          </div>
        </details>`;
    })}`);
  const primeiro = alvo.querySelector('details.item');
  if (primeiro) primeiro.open = true;
}

// ---------------------------------------------------------------------------- evidências

function telaEvidencias(alvo, a, ctx) {
  const filtros = {
    todas: () => true,
    edital: (e) => !e.documento_id.startsWith('pncp-item'),
    itens: (e) => e.documento_id.startsWith('pncp-item'),
    nv: (e) => !e.verificada,
  };
  const desenhar = (f) => {
    const lista = a.evidencias.filter(filtros[f]);
    render(alvo.querySelector('#lista-ev'), lista.length ? html`
      <div class="table-wrap"><table class="table">
        <thead><tr><th>ID</th><th>Documento</th><th class="num">Pág.</th><th>Trecho citado</th><th>Verificação</th></tr></thead>
        <tbody>${lista.map((e) => html`
          <tr class="clicavel" data-ev="${e.id}">
            <td class="mono small nowrap">${e.id}</td>
            <td class="small" style="max-width:240px"><div class="truncate">${ctx.docs[e.documento_id]?.nome || e.documento_id}</div></td>
            <td class="num">${e.pagina ?? '—'}</td>
            <td class="small"><div class="clamp-2">“${e.trecho_literal}”</div></td>
            <td class="nowrap">${e.verificada ? html`<span class="badge b-ok">verificada</span>` : html`<span class="badge b-warn">não verificada</span>`}<div class="muted small">score ${e.score_match ?? '—'}</div></td>
          </tr>`)}</tbody>
      </table></div>` : vazio('Nenhuma evidência neste filtro'));
  };
  const n = (f) => a.evidencias.filter(filtros[f]).length;
  render(alvo, html`
    <div class="alert alert-info" style="margin-bottom:14px">${icon('quote')}<div class="alert-body">Cada evidência é um trecho literal de um documento. O Verificador confere se ele existe na página citada (similaridade ≥ 90) e corrige a página quando necessário. Clique para conferir.</div></div>
    <div class="card">
      <div class="card-head"><div class="chips" id="filtros-ev">
        <button class="chip ativo" data-f="todas">Todas (${n('todas')})</button>
        <button class="chip" data-f="edital">Anexos do edital (${n('edital')})</button>
        <button class="chip" data-f="itens">Descrições de item (${n('itens')})</button>
        <button class="chip" data-f="nv">Não verificadas (${n('nv')})</button>
      </div></div>
      <div id="lista-ev"></div>
    </div>`);
  alvo.querySelector('#filtros-ev').addEventListener('click', (e) => {
    const b = e.target.closest('.chip');
    if (!b) return;
    alvo.querySelectorAll('#filtros-ev .chip').forEach((c) => c.classList.toggle('ativo', c === b));
    desenhar(b.dataset.f);
  });
  desenhar('todas');
}

// ---------------------------------------------------------------------------- investigação

function telaInvestigacao(alvo, a) {
  const passos = a.passos_investigacao;
  if (!passos.length) {
    render(alvo, vazio('O Investigador não foi acionado', 'Todas as informações necessárias estavam nas descrições dos itens, ou não havia anexos com texto.'));
    return;
  }
  const modoLlm = a.modo.startsWith('llm');
  render(alvo, html`
    <div class="alert alert-info" style="margin-bottom:14px">${icon('search')}<div class="alert-body">
      O Agente Investigador procura nos anexos as exigências que não estão na descrição dos itens (garantia, prazo de entrega, amostra, ensaios)
      ${modoLlm ? 'usando ferramentas (buscar trechos, ler página, registrar requisito) em um loop limitado de passos' : 'por busca textual e padrões (modo determinístico)'}.
      Tudo o que ele registra vira um requisito com evidência.</div></div>
    <div class="card"><ul class="timeline" style="max-height:none;padding:6px 16px">
      ${passos.map((p) => p.tipo === 'ferramenta' ? html`
        <li style="grid-template-columns:64px 170px 1fr">
          <span class="ts">passo ${p.passo}</span>
          <span class="no">${p.ferramenta}</span>
          <span><span class="mono small">${JSON.stringify(p.entrada)}</span><div class="muted small" style="margin-top:3px">→ ${String(p.saida).slice(0, 320)}</div></span>
        </li>` : html`
        <li style="grid-template-columns:64px 170px 1fr"><span class="ts">passo ${p.passo}</span><span class="no">raciocínio</span><span>${p.texto}</span></li>`)}
    </ul></div>`);
}

// ---------------------------------------------------------------------------- pendências

function telaPendencias(alvo, a) {
  const parecer = a.revisao_humana.find((x) => x.startsWith('Parecer'));
  const outras = a.revisao_humana.filter((x) => !x.startsWith('Parecer'));
  render(alvo, html`
    ${parecer ? html`<div class="card" style="margin-bottom:16px"><div class="card-head"><h2>Parecer do Agente Verificador</h2><span class="badge b-accent plain">LLM</span></div>
      <div class="card-body markdown">${raw(renderMarkdown(parecer.replace(/^Parecer do Agente Verificador:\s*/, '')))}</div></div>` : ''}
    <div class="grid grid-3">
      <div class="card"><div class="card-head"><h2>Lacunas</h2><span class="count badge plain">${a.lacunas.length}</span></div>
        <div class="card-body">${a.lacunas.length ? html`<ul class="list">${a.lacunas.map((x) => html`<li class="small">${x}</li>`)}</ul>` : html`<span class="muted small">Nenhuma informação ausente.</span>`}</div></div>
      <div class="card"><div class="card-head"><h2>Conflitos</h2><span class="count badge plain">${a.conflitos.length}</span></div>
        <div class="card-body">${a.conflitos.length ? html`<ul class="list">${a.conflitos.map((c) => html`<li class="small">${c.descricao}
          <div class="muted" style="margin-top:4px">${c.valores.map((v) => html`<div>${v.fonte}: <strong>${valorTecnico(v.valor)}</strong></div>`)}</div></li>`)}</ul>` : html`<span class="muted small">Nenhum conflito entre fontes.</span>`}</div></div>
      <div class="card"><div class="card-head"><h2>Revisão humana</h2><span class="count badge plain">${outras.length}</span></div>
        <div class="card-body">${outras.length ? html`<ul class="list">${outras.map((x) => html`<li class="small">${x}</li>`)}</ul>` : html`<span class="muted small">Nada marcado para revisão.</span>`}</div></div>
    </div>`);
}

// ---------------------------------------------------------------------------- dossiê

function telaDossie(alvo, a) {
  const d = a.dossie;
  render(alvo, html`
    <div class="grid grid-main">
      <div class="card"><div class="card-body markdown" id="md">${raw(renderMarkdown(d.conteudo_md))}</div></div>
      <div class="stack">
        <div class="card">
          <div class="card-head"><h2>Decisão humana</h2>${badgeRevisao(d.status_revisao)}</div>
          <form class="card-body" id="form-revisao">
            <div class="chips" style="margin-bottom:12px">
              ${['PENDENTE', 'APROVADO', 'REJEITADO'].map((s) => html`<label class="chip ${d.status_revisao === s ? 'ativo' : ''}"><input type="radio" name="status" value="${s}" ${d.status_revisao === s ? raw('checked') : ''} hidden>${s === 'PENDENTE' ? 'Pendente' : s === 'APROVADO' ? 'Seguir com a oportunidade' : 'Descartar'}</label>`)}
            </div>
            <label class="field">Comentário<textarea name="comentario" rows="4" placeholder="Motivo da decisão, responsável, próximos contatos…">${d.comentario_usuario}</textarea></label>
            <button class="btn btn-primary" type="submit" style="margin-top:12px;width:100%">${icon('check')} Salvar decisão</button>
            <p class="muted small" style="margin:10px 0 0">A decisão fica registrada na análise e alimenta o benchmark de qualidade.</p>
          </form>
        </div>
        <div class="card card-pad">
          <a class="btn" style="width:100%" href="${api.dossieDownloadUrl(a.id)}">${icon('download')} Baixar dossiê (.md)</a>
          <button class="btn btn-ghost" style="width:100%;margin-top:8px" id="imprimir">${icon('doc')} Imprimir / salvar PDF</button>
        </div>
      </div>
    </div>`);
  const form = alvo.querySelector('#form-revisao');
  form.addEventListener('change', (e) => {
    if (e.target.name !== 'status') return;
    form.querySelectorAll('label.chip').forEach((l) => l.classList.toggle('ativo', l.querySelector('input').checked));
  });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    try {
      const r = await api.revisar(a.id, f.get('status'), f.get('comentario') || '');
      d.status_revisao = r.revisao;
      d.comentario_usuario = r.comentario;
      toast('Decisão registrada');
      telaDossie(alvo, a);
    } catch (err) { toast(err.message, 'erro'); }
  });
  alvo.querySelector('#imprimir').addEventListener('click', () => {
    const w = window.open('', '_blank');
    w.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${esc(d.titulo)}</title><link rel="stylesheet" href="/css/app.css">
      <style>body{background:#fff;color:#13232b}.markdown{max-width:900px;margin:30px auto;padding:0 24px}</style></head>
      <body><div class="markdown">${renderMarkdown(d.conteudo_md)}</div><script>setTimeout(()=>print(),300)<\/script></body></html>`);
    w.document.close();
  });
}

// ---------------------------------------------------------------------------- modal de evidência

function realcar(texto, trecho) {
  if (!texto) return html`<span class="muted">Texto da página indisponível.</span>`;
  const tokens = trecho.split(/\s+/).filter(Boolean).slice(0, 40).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!tokens.length) return html`${texto}`;
  for (let n = tokens.length; n >= Math.min(3, tokens.length); n -= Math.max(1, Math.floor(n / 4))) {
    const re = new RegExp(tokens.slice(0, n).join('\\s+'), 'i');
    const m = texto.match(re);
    if (m) {
      const ini = m.index;
      return html`${texto.slice(0, ini)}<mark>${m[0]}</mark>${texto.slice(ini + m[0].length)}`;
    }
  }
  return html`${texto}`;
}

async function abrirEvidencia(a, ctx, evId) {
  const m = abrirModal({ titulo: 'Conferir evidência', subtitulo: evId, corpo: html`<div class="empty"><span class="spinner"></span></div>` });
  try {
    const r = await api.evidencia(a.id, evId);
    const ev = r.evidencia;
    const doc = r.documento;
    const corpo = html`
      <div class="chips" style="margin-bottom:12px">
        ${ev.verificada ? html`<span class="badge b-ok">verificada no documento</span>` : html`<span class="badge b-warn">não localizada literalmente</span>`}
        <span class="badge plain">similaridade ${ev.score_match ?? '—'}</span>
        <span class="badge plain">${doc.nome}${ev.pagina ? ` · página ${ev.pagina}` : ''}</span>
      </div>
      <div class="quote" style="margin-bottom:14px">“${ev.trecho_literal}”</div>
      <div class="kpi-label" style="margin-bottom:6px">${doc.id.startsWith('pncp-item') ? 'Descrição do item no PNCP' : `Texto da página ${ev.pagina}`}</div>
      <div class="page-text">${realcar(r.texto_pagina, ev.trecho_literal)}</div>`;
    m.el.querySelector('.modal-body').innerHTML = corpo.s;
    const rodape = document.createElement('div');
    rodape.className = 'modal-foot';
    rodape.innerHTML = html`
      ${doc.url_origem ? html`<a class="btn btn-ghost" href="${doc.url_origem}" target="_blank" rel="noopener">${icon('external')} Origem (PNCP)</a>` : ''}
      ${doc.tem_arquivo ? html`<a class="btn btn-primary" href="${api.arquivoUrl(a.id, doc.id, ev.pagina)}" target="_blank" rel="noopener">${icon('doc')} Abrir PDF na página ${ev.pagina || ''}</a>` : ''}`.s;
    m.el.appendChild(rodape);
    const marca = m.el.querySelector('mark');
    if (marca) marca.scrollIntoView({ block: 'center' });
  } catch (err) {
    m.el.querySelector('.modal-body').innerHTML = html`<div class="alert alert-bad">${icon('alert')}<div class="alert-body">${err.message}</div></div>`.s;
  }
}

export { render_ as render };
