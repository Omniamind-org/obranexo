// Utilitários de interface: template HTML com escape, ícones, toasts, dicas, modal e etiquetas.

export class Raw {
  constructor(s) { this.s = s; }
  toString() { return this.s; }
}
export const raw = (s) => new Raw(s);

export function esc(v) {
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function valor(v) {
  if (v === null || v === undefined || v === false) return '';
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(valor).join('');
  return esc(v);
}

/** Template literal com escape automático. Use raw() para HTML confiável. */
export function html(strings, ...vals) {
  let out = '';
  strings.forEach((s, i) => { out += s + (i < vals.length ? valor(vals[i]) : ''); });
  return new Raw(out);
}

export function render(el, conteudo) {
  el.innerHTML = conteudo instanceof Raw ? conteudo.s : String(conteudo);
}

// ------------------------------------------------------------------ ícones (traço, 24x24)

const ICONES = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M10 21v-6h4v6"/>',
  box: '<path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  file: '<path d="M14 3H6v18h12V7Z"/><path d="M14 3v4h4"/><path d="M9 12h6M9 16h6"/>',
  chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  play: '<path d="M7 4v16l13-8Z"/>',
  upload: '<path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v4h16v-4"/>',
  download: '<path d="M12 4v12M7 11l5 5 5-5"/><path d="M4 20h16"/>',
  external: '<path d="M14 4h6v6"/><path d="M20 4 10 14"/><path d="M19 14v6H4V5h6"/>',
  check: '<path d="m5 12 5 5L20 7"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  alert: '<path d="M12 3 2 20h20Z"/><path d="M12 10v4M12 17h.01"/>',
  pin: '<path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  money: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01M18 12h.01"/>',
  doc: '<path d="M14 3H6v18h12V7Z"/><path d="M14 3v4h4"/>',
  quote: '<path d="M7 7h4v4c0 3-2 5-4 6M15 7h4v4c0 3-2 5-4 6"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7Z"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5Z"/><path d="m3 13 9 5 9-5"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17h.01"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/><path d="M8.5 10.5h7M8.5 13.5h4"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/>',
  send: '<path d="M4 12 20 4l-6 16-3-7Z"/><path d="m11 13 9-9"/>',
  sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
};

export function icon(nome, cls = '') {
  return raw(`<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONES[nome] || ''}</svg>`);
}

export function hidratarIcones(raiz = document) {
  raiz.querySelectorAll('[data-icon]').forEach((el) => {
    el.outerHTML = icon(el.dataset.icon).s;
  });
}

// ------------------------------------------------------------------ toasts

export function toast(mensagem, tipo = 'ok', ms = 4200) {
  const raiz = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast ${tipo}`;
  el.innerHTML = html`${icon(tipo === 'erro' ? 'alert' : 'check')}<div>${mensagem}</div>`.s;
  raiz.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

// ------------------------------------------------------------------ dica flutuante (gráficos)

/** Qualquer elemento com data-tip mostra a dica ao passar o mouse ou receber foco. */
export function ativarDicas() {
  const dica = document.getElementById('dica');
  if (!dica) return;
  let alvo = null;
  const posicionar = (x, y) => {
    const r = dica.getBoundingClientRect();
    const left = Math.min(window.innerWidth - r.width - 8, Math.max(8, x - r.width / 2));
    const top = y - r.height - 12 < 8 ? y + 18 : y - r.height - 12;
    dica.style.left = `${left}px`;
    dica.style.top = `${top}px`;
  };
  const mostrar = (el, x, y) => {
    alvo = el;
    dica.innerHTML = esc(el.dataset.tip).replace(/\n/g, '<br>').replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    dica.classList.add('on');
    posicionar(x, y);
  };
  const esconder = () => { alvo = null; dica.classList.remove('on'); };
  document.addEventListener('mouseover', (e) => {
    const el = e.target.closest('[data-tip]');
    if (el && el.dataset.tip) mostrar(el, e.clientX, e.clientY);
    else if (alvo) esconder();
  });
  document.addEventListener('mousemove', (e) => { if (alvo) posicionar(e.clientX, e.clientY); });
  document.addEventListener('focusin', (e) => {
    const el = e.target.closest('[data-tip]');
    if (el && el.dataset.tip) { const r = el.getBoundingClientRect(); mostrar(el, r.left + r.width / 2, r.top); }
  });
  document.addEventListener('focusout', esconder);
  window.addEventListener('scroll', esconder, { passive: true });
  window.addEventListener('hashchange', esconder);
}

// ------------------------------------------------------------------ modal

export function abrirModal({ titulo, subtitulo = '', corpo, rodape = '' }) {
  const raiz = document.getElementById('modal-root');
  raiz.innerHTML = html`
    <div class="modal-backdrop" data-fechar>
      <div class="modal" role="dialog" aria-modal="true" aria-label="${titulo}">
        <div class="modal-head">
          <div><h2>${titulo}</h2>${subtitulo ? html`<div class="muted small" style="margin-top:4px">${subtitulo}</div>` : ''}</div>
          <button class="btn btn-ghost btn-sm" data-fechar aria-label="Fechar">${icon('x')}</button>
        </div>
        <div class="modal-body">${corpo}</div>
        ${rodape ? html`<div class="modal-foot">${rodape}</div>` : ''}
      </div>
    </div>`.s;
  const fechar = () => { raiz.innerHTML = ''; document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape') fechar(); };
  document.addEventListener('keydown', onKey);
  raiz.querySelector('.modal-backdrop').addEventListener('click', (e) => {
    if (e.target.hasAttribute('data-fechar') || e.target.closest('button[data-fechar]')) fechar();
  });
  return { el: raiz.querySelector('.modal'), fechar };
}

// ------------------------------------------------------------------ estados

export const carregando = (texto = 'Carregando…') => html`
  <div class="empty"><span class="spinner" style="color:var(--teal)"></span><div style="margin-top:10px">${texto}</div></div>`;

export const vazio = (titulo, texto = '', acao = '') => html`
  <div class="empty">${icon('layers')}<h3>${titulo}</h3>${texto ? html`<div>${texto}</div>` : ''}${acao ? html`<div style="margin-top:16px">${acao}</div>` : ''}</div>`;

export const erroBox = (msg) => html`
  <div class="aviso bad">${icon('alert')}<div><strong>Não foi possível carregar.</strong> ${msg}</div></div>`;

export const aviso = (texto, tipo = '', ico = 'info') => html`<div class="aviso ${tipo}">${icon(ico)}<div>${texto}</div></div>`;

// ------------------------------------------------------------------ etiquetas de domínio

const RESULTADO = {
  COMPATIVEL: ['Compatível', 'ok'],
  PARCIAL: ['Parcial', 'warn'],
  INDETERMINADO: ['Indeterminado', ''],
  INCOMPATIVEL: ['Incompatível', 'bad'],
  FORA_DO_PORTFOLIO: ['Fora do catálogo', 'plain'],
};
const TIPO = {
  PUBLICADA: ['Licitação publicada', 'teal'],
  PLANEJADA: ['Compra planejada', 'teal'],
  INDIRETA_POTENCIAL: ['Oportunidade indireta', 'warn'],
  INFERIDA: ['Inferida', ''],
};
const PRAZO = {
  ABERTA: ['Propostas abertas', 'ok'],
  ENCERRADA: ['Prazo encerrado', 'plain'],
  DESCONHECIDA: ['Prazo desconhecido', 'plain'],
};
const REVISAO = {
  PENDENTE: ['A decidir', 'plain'],
  APROVADO: ['Seguir', 'ok'],
  REJEITADO: ['Descartada', 'bad'],
};
const CONFIANCA = { alta: ['Confiança alta', 'ok'], media: ['Confiança média', 'warn'], baixa: ['Confiança baixa', 'bad'] };

function tagDe(mapa, chave) {
  const [rotulo, cls] = mapa[chave] || [chave || '—', 'plain'];
  return html`<span class="tag ${cls}">${rotulo}</span>`;
}
export const badgeResultado = (v) => tagDe(RESULTADO, v);
export const badgeTipo = (v) => tagDe(TIPO, v);
export const badgePrazo = (v) => tagDe(PRAZO, v);
export const badgeRevisao = (v) => tagDe(REVISAO, v);
export const badgeConfianca = (v) => tagDe(CONFIANCA, v);
export const rotuloResultado = (v) => (RESULTADO[v] || [v])[0];

// Agentes que chamam modelos (nome interno → rótulo). Nomes desconhecidos viram texto legível.
const AGENTE = {
  analista_tecnico: 'Analista Técnico', especificador: 'Especificador', investigador: 'Investigador',
  verificador: 'Verificador', planejador: 'Planejador', prospector: 'Prospecção', assistente: 'Assistente',
  curador_catalogo: 'Curador do catálogo',
};
export const rotuloAgente = (v) => AGENTE[v] || (v ? String(v).replace(/_/g, ' ') : '—');

const OPERACAO = { extrair: 'extração', texto: 'texto', conversa: 'conversa' };
export const rotuloOperacao = (v) => OPERACAO[v] || v || '—';

const REQUISITO = { ATENDE: ['Atende', 'ok', 'check'], NAO_ATENDE: ['Não atende', 'bad', 'x'], INDETERMINADO: ['Sem dado', 'indet', 'help'] };
export function badgeRequisito(v) {
  const [rotulo, cls, ico] = REQUISITO[v] || [v, 'indet', 'help'];
  return html`<span class="res ${cls}">${icon(ico)}${rotulo}</span>`;
}
