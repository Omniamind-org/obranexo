// Provedor de IA no topo: indicador + seletor entre os provedores com chave no .env.

import { api } from './api.js';
import { html, render, toast } from './ui.js';

export const NOMES_IA = { gemini: 'Gemini', groq: 'Groq', anthropic: 'Claude' };

function seletorLlm(s) {
  const configurados = (s.llm.provedores || []).filter((p) => p.configurado);
  const atual = s.llm.provedor || '';
  // Modo de contingência: sem IA os agentes não leem os anexos; o veredito sai só do que está na descrição do item
  const dica = atual
    ? `Agentes: ${s.llm.modelo_agente} · extração: ${s.llm.modelo_extracao}`
    : 'Contingência: veredito só pelas regras, sem leitura dos anexos pela IA';
  if (!configurados.length) return html`<span class="dot"></span><span data-tip="${dica}">Só regras (contingência)</span>`;
  return html`
    <span class="dot ${atual ? 'on' : ''}"></span>
    <select id="seletor-llm" aria-label="Provedor de IA" data-tip="${dica}">
      ${configurados.map((p) => html`<option value="${p.id}" ${p.id === atual ? 'selected' : ''}>IA: ${NOMES_IA[p.id] || p.id}</option>`)}
      <option value="" ${atual ? '' : 'selected'}>Só regras (contingência)</option>
    </select>`;
}

async function trocar(provedor) {
  try {
    const llm = await api.trocarProvedor(provedor || null);
    await atualizarStatus();
    window.dispatchEvent(new CustomEvent('provedor-llm', { detail: llm }));
    if (!llm.disponivel) { toast('Contingência: as análises usam só as regras, sem leitura dos anexos pela IA.'); return; }
    const nome = NOMES_IA[llm.provedor] || llm.provedor;
    const t = await api.testarProvedor();
    if (t.ok) toast(`${nome} conectado (${t.latencia_s}s)`);
    else toast(`${nome} não respondeu: ${t.erro}`, 'erro', 9000);
  } catch (err) {
    toast(err.message, 'erro', 7000);
    atualizarStatus();
  }
}

export async function atualizarStatus() {
  const el = document.getElementById('status-sistema');
  if (!el) return;
  try {
    const s = await api.status();
    render(el, seletorLlm(s));
    el.querySelector('#seletor-llm')?.addEventListener('change', (e) => trocar(e.target.value));
  } catch {
    render(el, html`<span class="dot"></span><span>Servidor indisponível</span>`);
  }
}
