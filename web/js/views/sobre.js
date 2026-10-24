import { api } from '../api.js';
import { renderMarkdown } from '../markdown.js';
import { html, icon, raw, render } from '../ui.js';

const ETAPAS = [
  ['box', 'Catálogo', 'Seus produtos e características técnicas — por planilha ou lendo a ficha do fabricante.'],
  ['search', 'Busca', 'O agente procura no PNCP licitações com propostas abertas nas suas UFs.'],
  ['file', 'Análise', 'Lê os itens e os anexos do edital e compara cada exigência com o seu produto.'],
  ['check', 'Decisão', 'Você recebe prioridade, riscos e próximos passos — e decide se segue.'],
];

const AGENTES = [
  ['Prospecção', true], ['Coleta no PNCP', false], ['Leitura dos anexos', false], ['Analista Técnico', true],
  ['Especificador', true], ['Motor de regras', false], ['Investigador', true], ['Verificador', true],
  ['Qualificação', false], ['Planejador', true], ['Dossiê', false],
];

export async function render_(el) {
  const md = await api.fluxo();
  render(el, html`
    <div class="page-head">
      <div><h1>Como funciona</h1><p class="sub">A IA interpreta e investiga; regras fixas decidem a compatibilidade; toda conclusão aponta para um trecho do documento.</p></div>
      <a class="btn btn-ghost" href="/api/docs" target="_blank" rel="noopener">${icon('external')} API</a>
    </div>

    <div class="grade grade-4">
      ${ETAPAS.map(([ic, t, d], i) => html`
        <div>
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
            <span style="width:36px;height:36px;border-radius:50%;background:var(--teal-soft);color:var(--teal-ink);display:grid;place-items:center">${icon(ic)}</span>
            <span class="muted small">${i + 1}</span>
          </div>
          <h3 style="font-size:16px;margin-bottom:4px">${t}</h3>
          <p class="ink-2 small">${d}</p>
        </div>`)}
    </div>

    <section class="secao">
      <div class="secao-head"><h2>Os agentes, em ordem</h2>
        <span class="legenda" style="margin:0"><span><i style="background:var(--teal-soft)"></i>usa IA</span><span><i style="background:var(--surface-2);border:1px solid var(--line)"></i>regras</span></span></div>
      <div class="fluxo">${AGENTES.map(([n, ia], i) => html`${i ? html`<b>→</b>` : ''}<span class="${ia ? 'agente' : ''}">${n}</span>`)}</div>
    </section>

    <section class="secao">
      <div class="grade grade-3">
        <div><h3 style="font-size:15px;margin-bottom:6px">Regras decidem</h3><p class="ink-2 small">A IA extrai e propõe; quem diz se o produto atende é um motor de regras determinístico, com o valor exigido e o do produto lado a lado.</p></div>
        <div><h3 style="font-size:15px;margin-bottom:6px">Tudo tem prova</h3><p class="ink-2 small">Cada exigência guarda o trecho literal do edital, conferido no documento antes de virar requisito.</p></div>
        <div><h3 style="font-size:15px;margin-bottom:6px">Você decide</h3><p class="ink-2 small">Pendências e divergências ficam visíveis; a decisão de seguir ou descartar é sempre humana.</p></div>
      </div>
    </section>

    <details class="mais secao">
      <summary>Documentação técnica completa</summary>
      <div class="markdown">${raw(renderMarkdown(md.replace(/^# .*\n/, '')))}</div>
    </details>`);
}

export { render_ as render };
