// Renderizador Markdown mínimo e seguro (escapa todo o HTML de entrada).
// Cobre o que os dossiês e a documentação usam: títulos, parágrafos com quebra "  ",
// listas, tabelas, blocos de código, linhas horizontais, negrito, itálico, código e links.

import { esc } from './ui.js';

function inline(texto) {
  let t = esc(texto);
  const codigos = [];
  t = t.replace(/`([^`]+)`/g, (_, c) => { codigos.push(c); return `\u0000${codigos.length - 1}\u0000`; });
  t = t.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
  t = t.replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?!\w)/g, '$1<em>$2</em>');
  t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  t = t.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
  t = t.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codigos[Number(i)]}</code>`);
  return t;
}

const celulas = (linha) => linha.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());

function tabela(linhas) {
  const cab = celulas(linhas[0]);
  const temSeparador = linhas[1] && /^\|?\s*:?-{2,}/.test(linhas[1].trim());
  const corpo = linhas.slice(temSeparador ? 2 : 1).map(celulas);
  return `<div class="table-wrap"><table class="table"><thead><tr>${cab.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead>`
    + `<tbody>${corpo.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

const INICIO_BLOCO = /^(#{1,6}\s|```|\||---+\s*$|\s*[-*]\s+|\s*\d+\.\s+)/;

export function renderMarkdown(md) {
  const linhas = String(md || '').replace(/\r/g, '').split('\n');
  const out = [];
  let i = 0;
  while (i < linhas.length) {
    const l = linhas[i];
    if (/^```/.test(l)) {
      const buf = [];
      i += 1;
      while (i < linhas.length && !/^```/.test(linhas[i])) buf.push(linhas[i++]);
      i += 1;
      out.push(`<pre><code>${esc(buf.join('\n'))}</code></pre>`);
      continue;
    }
    if (/^\s*$/.test(l)) { i += 1; continue; }
    const h = l.match(/^(#{1,6})\s+(.*)$/);
    if (h) { out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); i += 1; continue; }
    if (/^---+\s*$/.test(l)) { out.push('<hr>'); i += 1; continue; }
    if (/^\|/.test(l)) {
      const rows = [];
      while (i < linhas.length && /^\|/.test(linhas[i])) rows.push(linhas[i++]);
      out.push(tabela(rows));
      continue;
    }
    if (/^\s*[-*]\s+/.test(l)) {
      const itens = [];
      while (i < linhas.length && /^\s*[-*]\s+/.test(linhas[i])) itens.push(linhas[i++].replace(/^\s*[-*]\s+/, ''));
      out.push(`<ul>${itens.map((x) => `<li>${inline(x)}</li>`).join('')}</ul>`);
      continue;
    }
    if (/^\s*\d+\.\s+/.test(l)) {
      const itens = [];
      while (i < linhas.length && /^\s*\d+\.\s+/.test(linhas[i])) itens.push(linhas[i++].replace(/^\s*\d+\.\s+/, ''));
      out.push(`<ol>${itens.map((x) => `<li>${inline(x)}</li>`).join('')}</ol>`);
      continue;
    }
    const buf = [];
    while (i < linhas.length && !/^\s*$/.test(linhas[i]) && !INICIO_BLOCO.test(linhas[i])) buf.push(linhas[i++]);
    if (!buf.length) { buf.push(linhas[i++]); }
    out.push(`<p>${buf.map((x, k) => inline(x.replace(/\s+$/, '')) + (k < buf.length - 1 ? (/\s{2,}$/.test(x) ? '<br>' : ' ') : '')).join('')}</p>`);
  }
  return out.join('\n');
}
