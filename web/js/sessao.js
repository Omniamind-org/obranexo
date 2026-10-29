// Login: quem está na sessão, a tela de entrada (e de cadastro, quando aberto) e a conta no topo.

import { api } from './api.js';
import { html, icon, render, toast } from './ui.js';

let atual = null;

/** Usuário logado ({ email, nome, admin, empresa: { id, nome } }) ou null. */
export const usuario = () => atual;

export async function carregarSessao() {
  try { atual = await api.eu(); } catch { atual = null; }
  return atual;
}

export function desenharConta() {
  const el = document.getElementById('conta');
  if (!el || !atual) return;
  render(el, html`
    <span class="conta-nome" data-tip="${atual.email}${atual.admin ? ' · administrador' : ''}">${atual.empresa.nome}</span>
    <button class="btn btn-ghost btn-sm" id="sair" type="button">Sair</button>`);
  el.querySelector('#sair').addEventListener('click', async () => {
    await api.logout().catch(() => null);
    try { sessionStorage.clear(); } catch { /* sem storage */ }
    location.hash = '#/inicio';
    location.reload();
  });
}

function formEntrar() {
  return html`
    <form class="stack" id="form-entrar">
      <label class="field">E-mail<input class="input" name="email" type="email" autocomplete="username" required autofocus></label>
      <label class="field">Senha<input class="input" name="senha" type="password" autocomplete="current-password" required></label>
      <button class="btn btn-primary btn-lg" type="submit">Entrar</button>
    </form>`;
}

function formCadastro() {
  return html`
    <form class="stack" id="form-cadastro">
      <label class="field">Empresa<input class="input" name="empresa" autocomplete="organization" required minlength="2"></label>
      <label class="field">CNPJ (só números, opcional)<input class="input" name="cnpj" inputmode="numeric" pattern="\\d{14}"></label>
      <label class="field">Seu nome<input class="input" name="nome" autocomplete="name"></label>
      <label class="field">E-mail<input class="input" name="email" type="email" autocomplete="username" required></label>
      <label class="field">Senha (mínimo 8 caracteres)<input class="input" name="senha" type="password" autocomplete="new-password" required minlength="8"></label>
      <button class="btn btn-primary btn-lg" type="submit">Criar conta</button>
    </form>`;
}

/** Tela de entrada no lugar da aplicação; depois do login a página recarrega já com a sessão. */
export async function mostrarEntrada(el) {
  document.body.classList.add('sem-sessao');
  const status = await api.status().catch(() => null);
  const cadastroAberto = Boolean(status?.cadastro_aberto);
  let modo = 'entrar';

  const desenhar = () => {
    render(el, html`
      <div class="entrada">
        <div class="entrada-cartao">
          <img class="entrada-emblema" src="/images/emblem.png" alt="">
          <h1>${modo === 'entrar' ? 'Entrar no ObraNexo' : 'Criar conta'}</h1>
          <p class="sub">${modo === 'entrar'
            ? 'Cada empresa vê só o próprio catálogo, análises e conversas.'
            : 'A conta é da sua empresa: catálogo, análises e conversas ficam visíveis só para ela.'}</p>
          <div id="entrada-erro"></div>
          ${modo === 'entrar' ? formEntrar() : formCadastro()}
          ${cadastroAberto
            ? html`<p class="small muted entrada-troca">${modo === 'entrar' ? 'Ainda não tem conta?' : 'Já tem conta?'}
                <button class="btn btn-ghost btn-sm" id="trocar-modo" type="button">${modo === 'entrar' ? 'Criar conta' : 'Entrar'}</button></p>`
            : html`<p class="small muted entrada-troca">Sem conta? O acesso é por convite: fale com a equipe do ObraNexo.</p>`}
        </div>
      </div>`);
    el.querySelector('#trocar-modo')?.addEventListener('click', () => { modo = modo === 'entrar' ? 'cadastro' : 'entrar'; desenhar(); });
    const form = el.querySelector('form');
    form.querySelector('input')?.focus();
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const botao = form.querySelector('button[type=submit]');
      const dados = Object.fromEntries(new FormData(form));
      botao.disabled = true;
      try {
        if (modo === 'entrar') await api.login(dados.email, dados.senha);
        else await api.cadastro({ ...dados, cnpj: dados.cnpj || null });
        location.reload();
      } catch (err) {
        botao.disabled = false;
        render(el.querySelector('#entrada-erro'), html`<div class="aviso bad">${icon('alert')}<div>${err.message}</div></div>`);
      }
    });
  };
  desenhar();
}

/** Uma chamada voltou 401 no meio do uso (sessão expirou ou foi encerrada): volta para a tela de entrada. */
export function aoPerderSessao(el) {
  let avisado = false;
  window.addEventListener('sessao-encerrada', () => {
    if (avisado || !atual) return;
    avisado = true;
    atual = null;
    toast('Sua sessão terminou. Entre de novo para continuar.', 'erro', 7000);
    mostrarEntrada(el);
  });
}
