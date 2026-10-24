// Tema claro/escuro: a escolha do usuário fica salva; sem escolha, acompanha o tema do sistema.

import { icon } from './ui.js';

const CHAVE = 'obranexo.tema';
const salvo = () => { try { const t = localStorage.getItem(CHAVE); return t === 'light' || t === 'dark' ? t : null; } catch { return null; } };
const sistema = () => (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
export const temaAtual = () => document.documentElement.getAttribute('data-theme') || 'light';

function aplicar(tema) {
  document.documentElement.setAttribute('data-theme', tema);
  const b = document.getElementById('tema');
  if (!b) return;
  const proximo = tema === 'dark' ? 'claro' : 'escuro';
  b.innerHTML = icon(tema === 'dark' ? 'sun' : 'moon').s;
  b.setAttribute('aria-label', `Usar tema ${proximo}`);
  b.dataset.tip = `Usar tema ${proximo}`;
}

export function iniciarTema() {
  aplicar(salvo() || sistema());
  document.getElementById('tema')?.addEventListener('click', () => {
    const novo = temaAtual() === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem(CHAVE, novo); } catch { /* sem storage: vale só nesta visita */ }
    aplicar(novo);
  });
  // Sem escolha salva, segue o sistema se ele mudar com a página aberta
  window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => { if (!salvo()) aplicar(sistema()); });
}
