import { api } from '../api.js';
import { renderMarkdown } from '../markdown.js';
import { html, icon, raw, render } from '../ui.js';

export async function render_(el) {
  const md = await api.fluxo();
  render(el, html`
    <div class="page-head">
      <div><div class="eyebrow">Arquitetura</div><h1>Como o ObraNexo funciona</h1>
        <p>O LLM interpreta e investiga; as regras decidem a compatibilidade objetiva; toda conclusão aponta para uma evidência.</p></div>
      <a class="btn" href="/api/docs" target="_blank" rel="noopener">${icon('external')} Endpoints da API</a>
    </div>
    <div class="card"><div class="card-body markdown">${raw(renderMarkdown(md.replace(/^# .*\n/, '')))}</div></div>`);
}

export { render_ as render };
