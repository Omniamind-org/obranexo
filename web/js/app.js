// Roteador (hash) e casca da aplicação.

import { iniciarChat } from './chat.js';
import { aoPerderSessao, carregarSessao, desenharConta, linkDeConta, mostrarEntrada } from './sessao.js';
import { atualizarStatus } from './status.js';
import { iniciarTema } from './tema.js';
import { ativarDicas, carregando, erroBox, html, render } from './ui.js';
import * as inicio from './views/inicio.js';
import * as catalogo from './views/catalogo.js';
import * as demandas from './views/demandas.js';
import * as caso from './views/caso.js';
import * as analises from './views/analises.js';
import * as resultado from './views/resultado.js';
import * as metricas from './views/metricas.js';
import * as sobre from './views/sobre.js';
import * as prospeccao from './views/prospeccao.js';
import * as equipe from './views/equipe.js';

const ROTAS = [
  { re: /^\/?(?:inicio)?$/, nav: 'inicio', view: inicio },
  { re: /^\/agente$/, nav: 'agente', view: prospeccao },
  { re: /^\/agente\/([^/]+)$/, nav: 'agente', view: prospeccao },
  { re: /^\/catalogo$/, nav: 'catalogo', view: catalogo },
  { re: /^\/demandas$/, nav: 'demandas', view: demandas },
  { re: /^\/casos\/([^/]+)$/, nav: 'demandas', view: caso },
  { re: /^\/analises$/, nav: 'analises', view: analises },
  { re: /^\/analises\/([^/]+)$/, nav: 'analises', view: resultado },
  { re: /^\/metricas$/, nav: 'metricas', view: metricas },
  { re: /^\/sobre$/, nav: 'sobre', view: sobre },
  { re: /^\/equipe$/, nav: 'equipe', view: equipe },
];

const view = document.getElementById('view');
let limpar = null;
let navegacao = 0;

async function navegar() {
  const caminho = decodeURIComponent(location.hash.replace(/^#/, '')) || '/inicio';
  const rota = ROTAS.find((r) => r.re.test(caminho));
  const minha = ++navegacao;
  if (typeof limpar === 'function') {
    try { limpar(); } catch { /* view já descartada */ }
  }
  limpar = null;
  document.getElementById('modal-root').innerHTML = '';
  document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('ativo', Boolean(rota) && a.dataset.rota === rota.nav));
  if (!rota) {
    render(view, html`<div class="empty"><h3>Página não encontrada</h3><a class="btn" href="#/inicio" style="margin-top:12px">Voltar ao início</a></div>`);
    return;
  }
  const params = caminho.match(rota.re).slice(1);
  render(view, carregando());
  window.scrollTo(0, 0);
  // Cada navegação renderiza num contêiner próprio; só a mais recente entra na tela.
  // Sem isso, uma página lenta que termina depois sobrescreveria a página para onde o usuário já foi.
  const alvo = document.createElement('div');
  let fim = null;
  try {
    fim = await rota.view.render(alvo, ...params);
  } catch (err) {
    console.error(err);
    render(alvo, erroBox(err.message || String(err)));
  }
  if (minha !== navegacao) {
    if (typeof fim === 'function') fim();
    return;
  }
  limpar = fim;
  // O contêiner inteiro entra na tela: as views guardam referência a ele para eventos futuros
  view.replaceChildren(alvo);
  view.focus({ preventScroll: true });
}

iniciarTema();
ativarDicas();
aoPerderSessao(view);
// Sem sessão, só a tela de entrada; depois do login a página recarrega e a aplicação sobe daqui.
// Um link de convite ou de nova senha abre a tela de entrada mesmo com alguém logado neste navegador.
if (!(await carregarSessao()) || linkDeConta()) {
  await mostrarEntrada(view);
} else {
  desenharConta();
  iniciarChat();
  window.addEventListener('hashchange', navegar);
  // Telas que mostram o provedor de LLM (início e prospecção) são redesenhadas quando ele é trocado no seletor
  window.addEventListener('provedor-llm', () => {
    if (/^#?\/?(inicio|agente)?$/.test(location.hash)) navegar();
  });
  atualizarStatus();
  navegar();
}
