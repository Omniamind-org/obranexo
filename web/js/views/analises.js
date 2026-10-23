import { api } from '../api.js';
import { data, local, pct } from '../format.js';
import { badgePrazo, badgeRevisao, badgeTipo, html, icon, render, vazio } from '../ui.js';

export function barraResultados(r) {
  const total = Object.values(r).reduce((s, v) => s + v, 0) || 1;
  const partes = [
    ['COMPATIVEL', 'c-ok', 'Compatível'],
    ['PARCIAL', 'c-parcial', 'Parcial'],
    ['INDETERMINADO', 'c-indet', 'Indeterminado'],
    ['INCOMPATIVEL', 'c-bad', 'Incompatível'],
    ['FORA_DO_PORTFOLIO', 'c-fora', 'Fora do portfólio'],
  ];
  return html`
    <div class="barra" title="${partes.map(([k, , n]) => `${n}: ${r[k] || 0}`).join(' · ')}">
      ${partes.map(([k, c]) => (r[k] ? html`<span class="${c}" style="width:${(r[k] / total) * 100}%"></span>` : ''))}
    </div>`;
}

export function legendaResultados(r) {
  const partes = [['COMPATIVEL', 'c-ok', 'Compatível'], ['PARCIAL', 'c-parcial', 'Parcial'], ['INDETERMINADO', 'c-indet', 'Indeterminado'], ['INCOMPATIVEL', 'c-bad', 'Incompatível'], ['FORA_DO_PORTFOLIO', 'c-fora', 'Fora do portfólio']];
  return html`<div class="legenda">${partes.map(([k, c, n]) => html`<span><i class="${c}"></i>${n}: <strong>${r[k] || 0}</strong></span>`)}</div>`;
}

export async function render_(el) {
  const lista = await api.analises();
  render(el, html`
    <div class="page-head">
      <div><div class="eyebrow">Histórico</div><h1>Análises e dossiês</h1><p>Cada análise guarda os requisitos, as correspondências, as evidências e a decisão humana sobre o dossiê.</p></div>
      <a class="btn btn-primary" href="#/demandas">${icon('play')} Nova análise</a>
    </div>
    <div class="card">
      ${lista.length ? html`
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Contratação</th><th>Classificação</th><th style="width:180px">Itens</th><th class="num">Prioridade</th><th class="num">Evidências</th><th>Modo</th><th>Revisão</th><th>Quando</th></tr></thead>
        <tbody>${lista.map((a) => html`
          <tr class="clicavel" data-href="#/analises/${a.id}">
            <td><div class="truncate" style="max-width:280px;font-weight:600">${a.contratacao.orgao_nome}</div><div class="muted small">${local(a.contratacao)} · ${a.contratacao.id}</div></td>
            <td>${a.status === 'concluida' ? html`${badgeTipo(a.tipo_oportunidade)}<div style="margin-top:4px">${badgePrazo(a.prazo_status)}</div>` : html`<span class="badge b-bad">erro</span>`}</td>
            <td>${barraResultados(a.resultados)}<div class="muted small" style="margin-top:4px">${a.n_itens} itens · ${a.resultados.COMPATIVEL} compatíveis</div></td>
            <td class="num"><strong>${a.prioridade ?? '—'}</strong></td>
            <td class="num">${a.evidencias_total ? pct(a.evidencias_verificadas / a.evidencias_total) : '—'}<div class="muted small">${a.evidencias_verificadas}/${a.evidencias_total}</div></td>
            <td class="small"><span class="mono">${a.modo}</span><div class="muted">${a.duracao_s}s${a.llm.chamadas ? ` · ${a.llm.chamadas} chamadas` : ''}</div></td>
            <td>${a.revisao ? badgeRevisao(a.revisao) : ''}</td>
            <td class="nowrap muted small">${data(a.iniciada_em, true)}</td>
          </tr>`)}</tbody>
      </table></div>`
      : vazio('Nenhuma análise registrada', 'Execute uma análise a partir de uma demanda.', html`<a class="btn btn-primary" href="#/demandas">Ir para demandas</a>`)}
    </div>`);
  el.querySelectorAll('tr[data-href]').forEach((tr) => tr.addEventListener('click', () => { location.hash = tr.dataset.href; }));
}

export { render_ as render };
