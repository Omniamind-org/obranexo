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
    <a class="btn btn-ghost btn-sm" href="#/equipe" data-tip="Quem tem acesso e convites">Equipe</a>
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

function formRecuperar() {
  return html`
    <form class="stack" id="form-recuperar">
      <label class="field">E-mail da sua conta<input class="input" name="email" type="email" autocomplete="username" required></label>
      <button class="btn btn-primary btn-lg" type="submit">Mandar link de nova senha</button>
    </form>`;
}

function formSenhaNova(comNome) {
  return html`
    <form class="stack" id="form-senha-nova">
      ${comNome ? html`<label class="field">Seu nome<input class="input" name="nome" autocomplete="name"></label>` : ''}
      <label class="field">Senha (mínimo 8 caracteres)<input class="input" name="senha" type="password" autocomplete="new-password" required minlength="8"></label>
      <label class="field">Repita a senha<input class="input" name="repetida" type="password" autocomplete="new-password" required minlength="8"></label>
      <button class="btn btn-primary btn-lg" type="submit">${comNome ? 'Criar conta e entrar' : 'Trocar a senha e entrar'}</button>
    </form>`;
}

/** Link de convite ou de nova senha aberto (#/convite/<token>, #/redefinir/<token>): o token fica só no navegador. */
export function linkDeConta() {
  const m = location.hash.match(/^#\/(convite|redefinir)\/([A-Za-z0-9_-]{20,})$/);
  return m ? { tipo: m[1], token: m[2] } : null;
}

const TITULOS = {
  entrar: ['Entrar no ObraNexo', 'Cada empresa vê só o próprio catálogo, análises e conversas.'],
  cadastro: ['Criar conta', 'A conta é da sua empresa: catálogo, análises e conversas ficam visíveis só para ela.'],
  recuperar: ['Esqueci a senha', 'Mandamos um link para escolher uma senha nova. Ele vale 1 hora.'],
  convite: ['Aceitar convite', ''],
  redefinir: ['Escolha uma senha nova', 'As outras sessões abertas da sua conta serão encerradas.'],
};

/** Tela de entrada no lugar da aplicação; depois do login a página recarrega já com a sessão. */
export async function mostrarEntrada(el) {
  document.body.classList.add('sem-sessao');
  const status = await api.status().catch(() => null);
  const cadastroAberto = Boolean(status?.cadastro_aberto);
  const link = linkDeConta();
  let modo = link ? link.tipo : 'entrar';
  let convite = null;
  let aviso = null;
  if (link?.tipo === 'convite') {
    try { convite = await api.verConvite(link.token); } catch (err) { aviso = { tipo: 'bad', texto: err.message }; }
  }
  // Depois de entrar por um link, a aplicação abre no início (o token sai da barra de endereço)
  const entrou = () => { location.replace(`${location.pathname}#/inicio`); location.reload(); };

  const desenhar = () => {
    const [titulo, sub] = TITULOS[modo];
    const subtitulo = modo === 'convite' && convite ? `Conta de ${convite.email} na empresa ${convite.empresa}.` : sub;
    const formulario = { entrar: formEntrar, cadastro: formCadastro, recuperar: formRecuperar }[modo]?.()
      ?? (modo === 'convite' && !convite ? '' : formSenhaNova(modo === 'convite'));
    render(el, html`
      <div class="entrada">
        <div class="entrada-cartao">
          <img class="entrada-emblema" src="/images/emblem.png" alt="">
          <h1>${titulo}</h1>
          ${subtitulo ? html`<p class="sub">${subtitulo}</p>` : ''}
          <div id="entrada-erro">${aviso ? html`<div class="aviso ${aviso.tipo}">${icon(aviso.tipo === 'bad' ? 'alert' : 'check')}<div>${aviso.texto}</div></div>` : ''}</div>
          ${formulario}
          ${modo === 'entrar' ? html`<p class="small muted entrada-troca"><button class="btn btn-ghost btn-sm" data-modo="recuperar" type="button">Esqueci a senha</button></p>` : ''}
          ${modo !== 'entrar' ? html`<p class="small muted entrada-troca"><button class="btn btn-ghost btn-sm" data-modo="entrar" type="button">Voltar para entrar</button></p>` : ''}
          ${modo === 'entrar' && cadastroAberto ? html`<p class="small muted entrada-troca">Ainda não tem conta?
                <button class="btn btn-ghost btn-sm" data-modo="cadastro" type="button">Criar conta</button></p>` : ''}
          ${modo === 'entrar' && !cadastroAberto ? html`<p class="small muted entrada-troca">Sem conta? O acesso é por convite: peça a alguém da sua empresa ou à equipe do ObraNexo.</p>` : ''}
        </div>
      </div>`);
    el.querySelectorAll('[data-modo]').forEach((b) => b.addEventListener('click', () => {
      modo = b.dataset.modo;
      aviso = null;
      if (link) history.replaceState(null, '', `${location.pathname}#/inicio`); // saiu do link: o token sai do endereço
      desenhar();
    }));
    const form = el.querySelector('form');
    if (!form) return;
    form.querySelector('input')?.focus();
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const botao = form.querySelector('button[type=submit]');
      const dados = Object.fromEntries(new FormData(form));
      const erro = (msg) => render(el.querySelector('#entrada-erro'), html`<div class="aviso bad">${icon('alert')}<div>${msg}</div></div>`);
      if ('repetida' in dados && dados.repetida !== dados.senha) { erro('As duas senhas não são iguais.'); return; }
      botao.disabled = true;
      try {
        if (modo === 'entrar') { await api.login(dados.email, dados.senha); location.reload(); return; }
        if (modo === 'cadastro') { await api.cadastro({ ...dados, cnpj: dados.cnpj || null }); location.reload(); return; }
        if (modo === 'convite') { await api.aceitarConvite(link.token, dados.senha, dados.nome || ''); entrou(); return; }
        if (modo === 'redefinir') { await api.redefinirSenha(link.token, dados.senha); entrou(); return; }
        const r = await api.recuperarSenha(dados.email);
        modo = 'entrar';
        aviso = { tipo: 'ok', texto: r.email_configurado
          ? 'Se houver conta com esse e-mail, o link chega em alguns minutos. Confira também o spam.'
          : 'O envio de e-mail não está configurado neste servidor: peça o link de nova senha a um administrador do ObraNexo.' };
        desenhar();
      } catch (err) {
        botao.disabled = false;
        erro(err.message);
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
