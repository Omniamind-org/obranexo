// Painel de status do sistema na barra superior (SCADA Topbar Telemetry).

import { api } from './api.js';
import { html, render } from './ui.js';

export async function atualizarStatus() {
  const el = document.getElementById('status-sistema');
  if (!el) return;
  try {
    const s = await api.status();
    const llm = s.llm.disponivel
      ? html`<span class="hud-status ok" title="${s.llm.modelo_agente}"><span class="dot on"></span>${s.llm.provedor}</span>`
      : html`<span class="hud-status warn" title="Sem chave de API configurada"><span class="dot off"></span>DETERMINÍSTICO</span>`;
    render(el, html`
      <div class="topbar-hud">
        <div class="hud-chip">
          <span class="hud-label">IA:</span>
          ${llm}
        </div>
        <div class="hud-chip">
          <span class="hud-label">PNCP:</span>
          <span class="hud-val mono">${s.pncp_offline ? 'CACHE' : 'REDE'}</span>
        </div>
        <div class="hud-ping">SYS:OK</div>
        <div class="hud-chip version-chip"><span class="hud-val mono">v${s.versao}</span></div>
      </div>`);
  } catch {
    render(el, html`
      <div class="topbar-hud">
        <div class="hud-ping bad">OFFLINE</div>
      </div>`);
  }
}


