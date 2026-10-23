// Roteador (hash) e casca da aplicação.

import { atualizarStatus } from './status.js';
import { carregando, erroBox, hidratarIcones, html, render } from './ui.js';
import * as inicio from './views/inicio.js';
import * as catalogo from './views/catalogo.js';
import * as demandas from './views/demandas.js';
import * as caso from './views/caso.js';
import * as analises from './views/analises.js';
import * as resultado from './views/resultado.js';
import * as metricas from './views/metricas.js';
import * as sobre from './views/sobre.js';
import * as prospeccao from './views/prospeccao.js';

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
    render(view, html`<div class="empty"><h3>Página não encontrada</h3><a class="btn" href="#/inicio">Voltar ao início</a></div>`);
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

hidratarIcones(document.getElementById('nav'));
window.addEventListener('hashchange', navegar);
atualizarStatus();
navegar();
