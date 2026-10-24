// Assistente: painel lateral de conversa, disponível em todas as telas.
// O texto do assistente cita licitações como [[id]] e análises como [[analise:id]]; aqui viram links e cartões.

import { acompanharJob, api } from './api.js';
import { empilhada, prazo } from './charts.js';
import { moedaCompacta, nomeProprio } from './format.js';
import { renderMarkdown } from './markdown.js';
import { NOMES_IA } from './status.js';
import { esc, html, icon, raw, render, toast } from './ui.js';

const CHAVE_SESSAO = 'obranexo.chat';
const SUGESTOES = [
  'Licitações de iluminação pública abertas em GO',
  'Tenho refletores LED: onde posso vender nas próximas semanas?',
  'Qual a minha melhor oportunidade já analisada?',
  'O que o meu catálogo tem de luminárias públicas?',
];

const estado = { sessao: null, mensagens: [], ocupado: false, parar: null, carregada: false };

const lerSessao = () => { try { return sessionStorage.getItem(CHAVE_SESSAO); } catch { return null; } };
const gravarSessao = (id) => { try { if (id) sessionStorage.setItem(CHAVE_SESSAO, id); else sessionStorage.removeItem(CHAVE_SESSAO); } catch { /* sem storage */ } };

// ------------------------------------------------------------------ renderização

function textoComMarcas(texto, refs) {
  const porId = Object.fromEntries(refs.map((r) => [r.id, r]));
  const porAnalise = Object.fromEntries(refs.filter((r) => r.analise_id).map((r) => [r.analise_id, r]));
  let h = renderMarkdown(texto);
  h = h.replace(/\[\[\s*analise:\s*([\w-]+)\s*\]\]/g, (_, id) => (porAnalise[id] || refs.find((r) => r.analise_id === id)
    ? `<a class="ref" href="#/analises/${esc(id)}">${icon('file').s}análise</a>` : ''));
  h = h.replace(/\[\[\s*(\d{14}-\d+-\d+\/\d{4})\s*\]\]/g, (_, id) => {
    const r = porId[id];
    if (!r) return '';
    const destino = r.analise_id ? `#/analises/${r.analise_id}` : r.caso ? `#/casos/${r.caso}` : r.link_oficial;
    const externo = !r.analise_id && !r.caso;
    return `<a class="ref" href="${esc(destino)}"${externo ? ' target="_blank" rel="noopener"' : ''} data-tip="${esc(r.analise_id ? 'Ver a análise' : r.caso ? 'Abrir a licitação' : 'Ver no PNCP')}">${icon(externo ? 'external' : 'arrow').s}abrir</a>`;
  });
  return raw(h);
}

function cartao(r, i) {
  const res = r.resultados;
  const atendidos = res ? (res.COMPATIVEL || 0) + (res.PARCIAL || 0) : 0;
  const total = res ? Object.values(res).reduce((s, v) => s + v, 0) : 0;
  let acao;
  if (r.analise_id) acao = html`<a class="btn btn-sm" href="#/analises/${r.analise_id}">Ver análise</a>`;
  else if (r.caso) acao = html`<a class="btn btn-sm" href="#/casos/${r.caso}">Abrir</a>`;
  else acao = html`<button class="btn btn-primary btn-sm" data-coletar="${i}">${icon('download')} Salvar e analisar</button>`;
  return html`
    <div class="chat-cartao">
      <div class="chat-cartao-topo">
        <div style="min-width:0">
          <div class="linha-titulo truncate">${nomeProprio(r.orgao)}</div>
          <div class="linha-sub truncate" data-tip="${r.objeto}">${r.municipio} · ${r.objeto}</div>
        </div>
        ${r.prioridade !== null && r.prioridade !== undefined ? html`<div class="chat-nota" data-tip="Prioridade da análise (0–100)">${Math.round(r.prioridade)}</div>` : ''}
      </div>
      ${res ? html`<div style="margin:10px 0 2px">${empilhada(res)}</div><div class="linha-sub">${atendidos} de ${total} itens atendidos (análise)</div>` : ''}
      <div class="chat-cartao-base">
        <span class="small"><b>${moedaCompacta(r.valor_estimado)}</b> · ${prazo(r.encerra_iso)}</span>
        <span class="actions">${r.link_oficial ? html`<a class="btn btn-ghost btn-sm" href="${r.link_oficial}" target="_blank" rel="noopener" data-tip="Ver no PNCP">${icon('external')}</a>` : ''}${acao}</span>
      </div>
    </div>`;
}

function mensagemHtml(m, idx) {
  if (m.papel === 'usuario') return html`<div class="chat-msg usuario"><div class="balao">${m.texto}</div></div>`;
  if (m.papel === 'pensando') {
    return html`<div class="chat-msg assistente"><div class="chat-pensando"><span class="spinner"></span><span id="chat-status">${m.texto}</span></div></div>`;
  }
  const refs = m.referencias || [];
  return html`
    <div class="chat-msg assistente ${m.erro ? 'erro' : ''}" data-msg="${idx}">
      <div class="markdown">${textoComMarcas(m.texto, refs)}</div>
      ${refs.length ? html`<div class="chat-cartoes">${refs.map((r, i) => cartao(r, i))}</div>` : ''}
    </div>`;
}

function desenharMensagens() {
  const lista = document.querySelector('#chat .chat-corpo');
  if (!lista) return;
  if (!estado.mensagens.length) {
    render(lista, html`
      <div class="chat-vazio">
        <span class="chat-vazio-ic">${icon('sparkle')}</span>
        <h3>O que você quer encontrar?</h3>
        <p class="ink-2 small">Pergunte em linguagem natural. Eu busco no PNCP, olho os itens, comparo com o seu catálogo e com as análises já feitas.</p>
        <div class="chat-sugestoes">${SUGESTOES.map((s) => html`<button type="button" class="pilula" data-sugestao="${s}">${s}</button>`)}</div>
      </div>`);
    return;
  }
  render(lista, html`${estado.mensagens.map(mensagemHtml)}`);
  lista.scrollTop = lista.scrollHeight;
}

function desenharPainel(status) {
  const painel = document.getElementById('chat');
  const ia = status?.llm?.disponivel ? (NOMES_IA[status.llm.provedor] || status.llm.provedor) : null;
  render(painel, html`
    <div class="chat-topo">
      <div><h2>Assistente</h2><div class="muted small">${ia ? `IA: ${ia} · dados ao vivo do PNCP` : 'Sem IA configurada'}</div></div>
      <div class="actions">
        <button class="btn btn-ghost btn-sm" id="chat-nova" data-tip="Nova conversa">${icon('refresh')}</button>
        <button class="btn btn-ghost btn-sm" id="chat-fechar" aria-label="Fechar">${icon('x')}</button>
      </div>
    </div>
    <div class="chat-corpo" aria-live="polite"></div>
    <form class="chat-entrada" id="chat-form">
      <textarea id="chat-texto" rows="1" placeholder="${ia ? 'Pergunte o que você procura…' : 'Escolha um provedor de IA no topo para conversar'}" ${ia ? '' : 'disabled'}></textarea>
      <button class="btn btn-primary" type="submit" aria-label="Enviar" ${ia ? '' : 'disabled'}>${icon('send')}</button>
    </form>`);
  desenharMensagens();

  const texto = painel.querySelector('#chat-texto');
  const ajustar = () => { texto.style.height = 'auto'; texto.style.height = `${Math.min(texto.scrollHeight, 160)}px`; };
  texto.addEventListener('input', ajustar);
  texto.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); painel.querySelector('#chat-form').requestSubmit(); }
  });
  painel.querySelector('#chat-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const v = texto.value.trim();
    if (!v || estado.ocupado) return;
    texto.value = '';
    ajustar();
    enviar(v);
  });
  painel.querySelector('#chat-fechar').addEventListener('click', fecharChat);
  painel.querySelector('#chat-nova').addEventListener('click', novaConversa);
}

async function aoClicar(e) {
  const s = e.target.closest('[data-sugestao]');
  if (s) { enviar(s.dataset.sugestao); return; }
  const col = e.target.closest('[data-coletar]');
  if (col) {
    const msg = estado.mensagens[Number(col.closest('[data-msg]').dataset.msg)];
    const r = msg.referencias[Number(col.dataset.coletar)];
    col.disabled = true;
    col.innerHTML = '<span class="spinner"></span> Baixando…';
    try {
      const c = await api.coletarPncp({ cnpj: r.cnpj, ano: r.ano, sequencial: r.sequencial });
      r.caso = c.caso;
      toast(`Licitação salva: ${c.itens} itens, ${c.baixados}/${c.documentos} anexos`);
      location.hash = `#/casos/${c.caso}`;
      desenharMensagens();
    } catch (err) {
      toast(err.message, 'erro');
      col.disabled = false;
      col.innerHTML = `${icon('download').s} Tentar de novo`;
    }
    return;
  }
  // Em telas estreitas, seguir um link fecha o painel para mostrar a página
  if (e.target.closest('a[href^="#/"]') && window.innerWidth < 900) fecharChat();
}

// ------------------------------------------------------------------ conversa

async function garantirSessao() {
  if (estado.sessao) return estado.sessao;
  const s = await api.criarConversa();
  estado.sessao = s.sessao_id;
  gravarSessao(s.sessao_id);
  return estado.sessao;
}

async function enviar(texto) {
  if (estado.ocupado) return;
  estado.ocupado = true;
  estado.mensagens.push({ papel: 'usuario', texto });
  estado.mensagens.push({ papel: 'pensando', texto: 'Pensando…' });
  desenharMensagens();
  const terminar = (msg) => {
    estado.mensagens = estado.mensagens.filter((m) => m.papel !== 'pensando');
    if (msg) estado.mensagens.push(msg);
    estado.ocupado = false;
    desenharMensagens();
    document.getElementById('chat-texto')?.focus();
  };
  try {
    let sessao = await garantirSessao();
    let job;
    try {
      job = await api.enviarMensagem(sessao, texto);
    } catch (err) {
      if (!/não encontrada/.test(err.message)) throw err;
      estado.sessao = null; // o servidor reiniciou: abre outra conversa e reenvia
      sessao = await garantirSessao();
      job = await api.enviarMensagem(sessao, texto);
    }
    estado.parar = acompanharJob(job.id, {
      onEvento: (ev) => {
        const st = document.getElementById('chat-status');
        if (st) st.textContent = ev.mensagem;
        const p = estado.mensagens.find((m) => m.papel === 'pensando');
        if (p) p.texto = ev.mensagem;
      },
      onFim: (fim) => {
        estado.parar = null;
        if (fim.status === 'concluida' && fim.dados?.mensagem) terminar(fim.dados.mensagem);
        else terminar({ papel: 'assistente', erro: true, texto: `Não consegui responder: ${fim.erro || 'erro desconhecido'}.` });
      },
      onErro: (err) => terminar({ papel: 'assistente', erro: true, texto: `Conexão perdida: ${err.message}` }),
    });
  } catch (err) {
    terminar({ papel: 'assistente', erro: true, texto: err.message });
  }
}

async function novaConversa() {
  estado.parar?.();
  estado.parar = null;
  estado.sessao = null;
  estado.mensagens = [];
  estado.ocupado = false;
  gravarSessao(null);
  desenharMensagens();
  document.getElementById('chat-texto')?.focus();
}

async function carregarSessaoAnterior() {
  if (estado.carregada) return;
  estado.carregada = true;
  const id = lerSessao();
  if (!id) return;
  try {
    const s = await api.conversa(id);
    estado.sessao = s.sessao_id;
    estado.mensagens = s.mensagens;
  } catch {
    gravarSessao(null);
  }
}

// ------------------------------------------------------------------ abrir / fechar

export async function abrirChat(pergunta) {
  const painel = document.getElementById('chat');
  const botao = document.getElementById('chat-abrir');
  if (painel.hidden) {
    const status = await api.status().catch(() => null);
    await carregarSessaoAnterior();
    desenharPainel(status);
    painel.hidden = false;
    document.body.classList.add('chat-aberto');
    botao.setAttribute('aria-expanded', 'true');
  }
  if (pergunta) enviar(pergunta);
  else document.getElementById('chat-texto')?.focus();
}

export function fecharChat() {
  document.getElementById('chat').hidden = true;
  document.body.classList.remove('chat-aberto');
  document.getElementById('chat-abrir').setAttribute('aria-expanded', 'false');
}

export function iniciarChat() {
  document.getElementById('chat-abrir').addEventListener('click', () => abrirChat());
  document.getElementById('chat').addEventListener('click', aoClicar);
  // Trocar o provedor de IA no topo atualiza o cabeçalho do painel aberto
  window.addEventListener('provedor-llm', async () => {
    const painel = document.getElementById('chat');
    if (!painel.hidden) desenharPainel(await api.status().catch(() => null));
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !document.getElementById('chat').hidden && !document.querySelector('.modal-backdrop')) fecharChat();
  });
}
