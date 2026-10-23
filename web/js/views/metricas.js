import { api } from '../api.js';
import { data, numero, pct } from '../format.js';
import { badgeRevisao, html, icon, render, vazio } from '../ui.js';
import { barraResultados } from './analises.js';

export async function render_(el) {
  const m = await api.metricas();
  const b = m.benchmark;
  const lista = m.lista.filter((x) => x.status === 'concluida');

  render(el, html`
    <div class="page-head">
      <div><div class="eyebrow">Avaliação</div><h1>Métricas</h1><p>Qualidade (benchmark contra gabaritos revisados) e operação (tempo, custo, rastreabilidade) das análises registradas.</p></div>
    </div>

    <div class="section-title" style="margin-top:0">Benchmark ${b ? html`<span class="badge plain mono" style="margin-left:6px">${b.modo}</span>` : ''}</div>
    ${b ? html`
      <div class="grid grid-4">
        ${[['Acurácia por item', b.acuracia_itens], ['Precisão de “compatível”', b.precisao_compativel], ['Detecção de incompatibilidade', b.deteccao_incompatibilidade], ['Rastreabilidade', b.rastreabilidade]]
          .map(([k, v]) => html`<div class="card kpi"><div class="kpi-label">${k}</div><div class="kpi-value ${v === '100%' ? 'ok' : ''}">${v}</div></div>`)}
      </div>
      <p class="muted small" style="margin-top:8px">Gerado por <code>python eval/run_benchmark.py</code> · ${b.chamadas_llm} chamadas de LLM · ${numero(b.tempo_total_s)} s · US$ ${b.custo_total_usd}</p>`
    : html`<div class="alert alert-info">${icon('info')}<div class="alert-body">Rode <code>python eval/run_benchmark.py</code> para gerar o benchmark.</div></div>`}

    <div class="section-title">Operação</div>
    <div class="grid grid-4">
      <div class="card kpi"><div class="kpi-label">Análises concluídas</div><div class="kpi-value">${m.concluidas}</div><div class="kpi-sub">de ${m.analises} registradas</div></div>
      <div class="card kpi"><div class="kpi-label">Rastreabilidade</div><div class="kpi-value">${pct(m.rastreabilidade)}</div><div class="kpi-sub">citações conferidas</div></div>
      <div class="card kpi"><div class="kpi-label">Duração média</div><div class="kpi-value">${m.duracao_media_s ?? '—'}s</div><div class="kpi-sub">por contratação</div></div>
      <div class="card kpi"><div class="kpi-label">LLM</div><div class="kpi-value">${m.chamadas_llm}</div><div class="kpi-sub">${numero(m.tokens)} tokens · US$ ${m.custo_total_usd}</div></div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head"><h2>Por análise</h2><div class="chips">${Object.entries(m.revisoes).map(([k, v]) => html`${badgeRevisao(k)}<span class="small muted" style="margin-right:8px">${v}</span>`)}</div></div>
      ${lista.length ? html`<div class="table-wrap"><table class="table">
        <thead><tr><th>Análise</th><th>Contratação</th><th style="width:170px">Itens</th><th class="num">Evidências</th><th class="num">Duração</th><th class="num">Chamadas</th><th class="num">Tokens</th><th>Modo</th></tr></thead>
        <tbody>${lista.map((a) => html`<tr class="clicavel" data-href="#/analises/${a.id}">
          <td class="small nowrap">${data(a.iniciada_em, true)}</td>
          <td><div class="truncate" style="max-width:240px">${a.contratacao.orgao_nome}</div></td>
          <td>${barraResultados(a.resultados)}</td>
          <td class="num">${a.evidencias_verificadas}/${a.evidencias_total}</td>
          <td class="num">${a.duracao_s}s</td>
          <td class="num">${a.llm.chamadas}</td>
          <td class="num">${numero(a.llm.tokens)}</td>
          <td class="mono small">${a.modo}</td></tr>`)}</tbody>
      </table></div>` : vazio('Sem análises concluídas')}
    </div>`);
  el.querySelectorAll('tr[data-href]').forEach((tr) => tr.addEventListener('click', () => { location.hash = tr.dataset.href; }));
}

export { render_ as render };
