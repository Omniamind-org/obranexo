import { api } from '../api.js';
import { empilhada, legendaResultados, nota, prazo } from '../charts.js';
import { data, local, nomeProprio } from '../format.js';
import { badgeRevisao, html, icon, render, vazio } from '../ui.js';
import { ultimasPorContratacao } from './inicio.js';

const FILTROS = [
  ['todas', 'Todas', () => true],
  ['PENDENTE', 'A decidir', (a) => a.revisao === 'PENDENTE'],
  ['APROVADO', 'Seguir', (a) => a.revisao === 'APROVADO'],
  ['REJEITADO', 'Descartadas', (a) => a.revisao === 'REJEITADO'],
];

export async function render_(el) {
  const todas = await api.analises();
  const estado = { filtro: 'todas', historico: false };

  render(el, html`
    <div class="page-head">
      <div><h1>Análises</h1><p class="sub">Uma linha por licitação analisada. Abra para ver item a item e decidir se vale seguir.</p></div>
      <a class="btn btn-primary" href="#/demandas">${icon('play')} Nova análise</a>
    </div>
    ${todas.length ? html`
      <div class="actions" style="justify-content:space-between;margin-bottom:18px">
        <div class="segmentos" id="filtros">${FILTROS.map(([k, n]) => html`<button type="button" data-f="${k}" class="${k === 'todas' ? 'ativo' : ''}">${n}</button>`)}</div>
        <label class="check small"><input type="checkbox" id="historico"> Incluir reexecuções</label>
      </div>
      <div id="lista"></div>` : vazio('Nenhuma análise registrada', 'Escolha uma licitação para analisar.', html`<a class="btn btn-primary" href="#/demandas">Ver licitações</a>`)}`);
  if (!todas.length) return;

  const desenhar = () => {
    const base = estado.historico ? todas : [...ultimasPorContratacao(todas), ...todas.filter((a) => a.status !== 'concluida')];
    const lista = base.filter(FILTROS.find(([k]) => k === estado.filtro)[2]);
    const totais = lista.reduce((t, a) => { Object.entries(a.resultados).forEach(([k, v]) => { t[k] = (t[k] || 0) + v; }); return t; }, {});
    render(el.querySelector('#lista'), lista.length ? html`
      <div class="linhas">${lista.map((a) => {
        const c = a.contratacao;
        const ok = a.status === 'concluida';
        return html`
          <a class="linha" href="#/analises/${a.id}" style="grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) 150px 120px">
            <div style="min-width:0">
              <div class="linha-titulo truncate">${nomeProprio(c.orgao_nome)}</div>
              <div class="linha-sub truncate">${local(c)} · ${prazo(c.data_encerramento_proposta)} · analisada em ${data(a.iniciada_em, true)}</div>
            </div>
            <div>${ok ? html`${empilhada(a.resultados)}<div class="linha-sub">${(a.resultados.COMPATIVEL || 0) + (a.resultados.PARCIAL || 0)} de ${a.n_itens} itens atendidos</div>` : html`<span class="tag bad">Terminou com erro</span>`}</div>
            ${ok ? nota(a.prioridade, 'Prioridade comercial (0–100)') : html`<span></span>`}
            <div class="num">${ok && a.revisao ? badgeRevisao(a.revisao) : ''}</div>
          </a>`;
      })}</div>
      ${legendaResultados(totais)}` : vazio('Nada neste filtro'));
  };

  el.querySelector('#filtros').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    estado.filtro = b.dataset.f;
    el.querySelectorAll('#filtros button').forEach((x) => x.classList.toggle('ativo', x === b));
    desenhar();
  });
  el.querySelector('#historico').addEventListener('change', (e) => { estado.historico = e.target.checked; desenhar(); });
  desenhar();
}

export { render_ as render };
