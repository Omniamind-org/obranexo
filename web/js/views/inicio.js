import { api } from '../api.js';
import { abrirChat } from '../chat.js';
import { empilhada, legendaResultados, nota, prazo } from '../charts.js';
import { local, moedaCompacta, pct, nomeProprio } from '../format.js';
import { html, icon, render, vazio } from '../ui.js';

/** Última análise concluída de cada contratação (as reexecuções não repetem a mesma licitação). */
export function ultimasPorContratacao(analises) {
  const vistas = new Set();
  return analises.filter((a) => {
    if (a.status !== 'concluida' || vistas.has(a.contratacao.id)) return false;
    vistas.add(a.contratacao.id);
    return true;
  });
}

const atendidos = (r) => (r.COMPATIVEL || 0) + (r.PARCIAL || 0);

export function linhaAnalise(a) {
  const c = a.contratacao;
  return html`
    <a class="linha" href="#/analises/${a.id}" style="grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) 150px 140px">
      <div style="min-width:0">
        <div class="linha-titulo truncate">${nomeProprio(c.orgao_nome)}</div>
        <div class="linha-sub truncate">${local(c)} · ${c.objeto}</div>
      </div>
      <div>
        ${empilhada(a.resultados)}
        <div class="linha-sub">${atendidos(a.resultados)} de ${a.n_itens} itens atendidos</div>
      </div>
      ${nota(a.prioridade, 'Prioridade comercial (0–100)')}
      <div class="num">${prazo(c.data_encerramento_proposta)}</div>
    </a>`;
}

export async function render_(el) {
  const [casos, analises] = await Promise.all([api.casos(), api.analises()]);
  const recentes = ultimasPorContratacao(analises);
  const concluidas = analises.filter((a) => a.status === 'concluida');
  const evTotal = concluidas.reduce((s, a) => s + a.evidencias_total, 0);
  const evOk = concluidas.reduce((s, a) => s + a.evidencias_verificadas, 0);
  const itensAtendidos = recentes.reduce((s, a) => s + atendidos(a.resultados), 0);
  const totais = recentes.reduce((t, a) => { Object.entries(a.resultados).forEach(([k, v]) => { t[k] = (t[k] || 0) + v; }); return t; }, {});
  const agora = new Date();
  const abertas = casos
    .filter((c) => c.contratacao.data_encerramento_proposta && new Date(c.contratacao.data_encerramento_proposta) > agora)
    .sort((x, y) => new Date(x.contratacao.data_encerramento_proposta) - new Date(y.contratacao.data_encerramento_proposta));

  render(el, html`
    <section class="boas-vindas">
      <div>
        <h1>Encontre as licitações que o seu catálogo atende</h1>
        <p class="sub">O agente busca no PNCP, lê os editais e mostra, item a item, onde você é competitivo — sempre com o trecho do edital como prova.</p>
        <form class="pergunta" id="pergunta">
          <input name="q" autocomplete="off" placeholder="O que você quer encontrar? Ex.: refletores LED em GO" aria-label="Pergunte ao assistente">
          <button class="btn btn-primary" type="submit">${icon('chat')} Perguntar</button>
        </form>
        <div class="atalhos">
          <a href="#/agente">${icon('bolt')} Deixar o agente prospectar sozinho</a>
          <a href="#/demandas">Analisar uma licitação específica</a>
        </div>
      </div>
      <div class="numeros">
        <div class="numero"><b>${recentes.length}</b><span>licitações analisadas</span></div>
        <div class="numero"><b>${itensAtendidos}</b><span>itens que o catálogo atende</span></div>
        <div class="numero ${evTotal && evOk === evTotal ? 'ok' : ''}" data-tip="${evOk} de ${evTotal} citações conferidas no documento original"><b>${evTotal ? pct(evOk / evTotal) : '—'}</b><span>das conclusões com prova conferida</span></div>
      </div>
    </section>

    <section class="secao">
      <div class="secao-head">
        <h2>Análises recentes</h2>
        <a href="#/analises">Ver todas</a>
      </div>
      ${recentes.length ? html`
        <div class="linhas">${recentes.slice(0, 6).map(linhaAnalise)}</div>
        ${legendaResultados(totais)}`
      : vazio('Nenhuma análise ainda', 'Escolha uma licitação ou deixe o agente buscar por você.', html`<a class="btn btn-primary" href="#/agente">${icon('bolt')} Buscar oportunidades</a>`)}
    </section>

    ${abertas.length ? html`
      <section class="secao">
        <div class="secao-head"><h2>Propostas abertas</h2><a href="#/demandas">Todas as licitações</a></div>
        <div class="linhas">${abertas.slice(0, 5).map((c) => html`
          <a class="linha" href="#/casos/${c.nome}" style="grid-template-columns:minmax(0,1fr) 120px 150px">
            <div style="min-width:0">
              <div class="linha-titulo truncate">${nomeProprio(c.contratacao.orgao_nome)}</div>
              <div class="linha-sub truncate">${local(c.contratacao)} · ${c.contratacao.objeto}</div>
            </div>
            <div class="num" data-tip="Valor estimado da contratação">${moedaCompacta(c.contratacao.valor_estimado)}</div>
            <div class="num">${prazo(c.contratacao.data_encerramento_proposta)}</div>
          </a>`)}</div>
      </section>` : ''}`);

  el.querySelector('#pergunta').addEventListener('submit', (e) => {
    e.preventDefault();
    const q = e.currentTarget.elements.q.value.trim();
    abrirChat(q || undefined);
    e.currentTarget.reset();
  });
}

export { render_ as render };
