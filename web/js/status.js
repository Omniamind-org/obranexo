// Painel de status do sistema no rodapé da barra lateral.

import { api } from './api.js';
import { html, render } from './ui.js';

export async function atualizarStatus() {
  const el = document.getElementById('status-sistema');
  if (!el) return;
  try {
    const s = await api.status();
    const llm = s.llm.disponivel
      ? html`<span class="dot on"></span><strong>${s.llm.provedor}</strong>`
      : html`<span class="dot off"></span><strong>determinístico</strong>`;
    render(el, html`
      <div class="linha"><span>Agentes</span><span>${llm}</span></div>
      ${s.llm.disponivel ? html`<div class="linha"><span>Modelo</span><span class="mono truncate" title="${s.llm.modelo_agente}">${s.llm.modelo_agente}</span></div>` : ''}
      <div class="linha"><span>PNCP</span><strong>${s.pncp_offline ? 'offline' : 'online + cache'}</strong></div>
      <div class="linha"><span>Versão</span><span>v${s.versao}</span></div>`);
  } catch {
    render(el, html`<div class="linha"><span><span class="dot off"></span>API indisponível</span></div>`);
  }
}
