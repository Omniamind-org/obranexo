// Gráficos leves em HTML/SVG (sem biblioteca). Cores de estado sempre acompanhadas de rótulo (legenda/dica).

import { numero } from './format.js';
import { html, raw } from './ui.js';

export const RESULTADOS = [
  ['COMPATIVEL', 'r-ok', 'Compatível'],
  ['PARCIAL', 'r-parcial', 'Parcial'],
  ['INDETERMINADO', 'r-indet', 'Indeterminado'],
  ['INCOMPATIVEL', 'r-bad', 'Incompatível'],
  ['FORA_DO_PORTFOLIO', 'r-fora', 'Fora do catálogo'],
];
export const CLASSE_RESULTADO = Object.fromEntries(RESULTADOS.map(([k, c]) => [k, c]));
export const ROTULO_RESULTADO = Object.fromEntries(RESULTADOS.map(([k, , n]) => [k, n]));

const plural = (n, um, varios) => `${numero(n)} ${n === 1 ? um : varios}`;

/** Barra empilhada com a contagem de itens por resultado. */
export function empilhada(r, { alta = false } = {}) {
  const total = RESULTADOS.reduce((s, [k]) => s + (r[k] || 0), 0);
  if (!total) return html`<div class="empilhada ${alta ? 'alta' : ''}"><span class="r-fora" style="flex:1"></span></div>`;
  return html`<div class="empilhada ${alta ? 'alta' : ''}" role="img" aria-label="${RESULTADOS.map(([k, , n]) => `${n}: ${r[k] || 0}`).join(', ')}">
    ${RESULTADOS.map(([k, c, n]) => (r[k] ? html`<span class="${c}" style="flex:${r[k]}" data-tip="**${n}**: ${plural(r[k], 'item', 'itens')} de ${total}"></span>` : ''))}
  </div>`;
}

export function legendaResultados(r, { soPresentes = true } = {}) {
  return html`<div class="legenda">${RESULTADOS.filter(([k]) => !soPresentes || r[k]).map(([k, c, n]) => html`<span><i class="${c}"></i>${n} <b>${r[k] || 0}</b></span>`)}</div>`;
}

/** Um quadrado por item; cor = resultado. `itens`: [{num, resultado, tip}] */
export function waffle(itens) {
  return html`<div class="waffle">${itens.map((i) => html`
    <button type="button" class="${CLASSE_RESULTADO[i.resultado] || 'r-fora'}" data-item="${i.id}" data-tip="${i.tip}" aria-label="Item ${i.num}: ${ROTULO_RESULTADO[i.resultado] || i.resultado}">${i.num}</button>`)}</div>`;
}

/** Arco 0–100 com o valor no centro. */
export function gauge(valor, rotulo) {
  const v = Math.max(0, Math.min(100, Number(valor) || 0));
  const arco = 'M 14 84 A 70 70 0 0 1 154 84';
  return html`<div class="gauge" role="img" aria-label="${rotulo}: ${Math.round(v)} de 100">
    <svg viewBox="0 0 168 92" aria-hidden="true">
      <path d="${arco}" fill="none" stroke="var(--teal-soft)" stroke-width="14" stroke-linecap="round"/>
      ${v > 0 ? html`<path d="${arco}" fill="none" stroke="var(--teal)" stroke-width="14" stroke-linecap="round" pathLength="100" stroke-dasharray="${v} 100"/>` : ''}
    </svg>
    <div class="valor"><b>${Math.round(v)}</b><span>${rotulo}</span></div>
  </div>`;
}

export const COR_RESULTADO = {
  COMPATIVEL: 'var(--ok)', PARCIAL: 'var(--warn)', INDETERMINADO: 'var(--indet)', INCOMPATIVEL: 'var(--bad)', FORA_DO_PORTFOLIO: 'var(--line-strong)',
};

/** Barras horizontais. linhas: [{rot, valor, txt, tip, attrs, ativo, fraca, cor}] */
export function barras(linhas, { max } = {}) {
  const m = max ?? Math.max(1, ...linhas.map((l) => l.valor || 0));
  return html`<div class="barras">${linhas.map((l) => html`
    <div class="rot ${l.attrs ? 'clicavel' : ''} ${l.ativo ? 'ativo' : ''}" ${l.attrs ? raw(l.attrs) : ''}>${l.rot}</div>
    <div class="trilho ${l.attrs ? 'clicavel' : ''} ${l.ativo ? 'ativo' : ''}" ${l.attrs ? raw(l.attrs) : ''} data-tip="${l.tip || ''}">
      <span class="barra ${l.fraca ? 'fraca' : ''}" style="width:${Math.max(0.5, ((l.valor || 0) / m) * 100)}%${l.cor ? `;background:${l.cor}` : ''}"></span>
      <span class="val">${l.txt ?? numero(l.valor)}</span>
    </div>`)}</div>`;
}

export function medidor(frac, { ok = false, tip = '' } = {}) {
  const p = Math.max(0, Math.min(1, Number(frac) || 0)) * 100;
  return html`<div class="medidor ${ok ? 'ok' : ''}" data-tip="${tip}" role="img" aria-label="${Math.round(p)}%"><span style="width:${p}%"></span></div>`;
}

/** Nota 0–100 com barra curta. */
export function nota(v, tip = '') {
  return html`<div class="nota" data-tip="${tip}"><b>${v === null || v === undefined ? '—' : Math.round(v)}</b>${medidor((v || 0) / 100)}</div>`;
}

/** "encerra em 5 dias" / "encerrada" a partir da data de encerramento das propostas. */
export function prazo(iso) {
  if (!iso) return html`<span class="prazo encerrada">prazo não informado</span>`;
  const fim = new Date(iso);
  if (Number.isNaN(fim.getTime())) return html`<span class="prazo encerrada">prazo não informado</span>`;
  const dias = Math.ceil((fim - new Date()) / 86_400_000);
  const quando = fim.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
  if (dias < 0) return html`<span class="prazo encerrada" data-tip="Propostas encerradas em ${fim.toLocaleString('pt-BR')}">encerrada em ${quando}</span>`;
  const txt = dias === 0 ? 'encerra hoje' : dias === 1 ? 'encerra amanhã' : `encerra em ${dias} dias`;
  return html`<span class="prazo ${dias <= 7 ? 'urgente' : 'aberta'}" data-tip="Propostas até ${fim.toLocaleString('pt-BR')}">${txt}</span>`;
}
