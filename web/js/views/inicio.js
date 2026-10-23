import { api } from '../api.js';
import { data, local, moedaCompacta, pct } from '../format.js';
import { badgePrazo, badgeRevisao, badgeTipo, html, icon, render, vazio } from '../ui.js';

export async function render_(el) {
  const [status, casos, analises] = await Promise.all([api.status(), api.casos(), api.analises()]);
  const concluidas = analises.filter((a) => a.status === 'concluida');
  const evTotal = concluidas.reduce((s, a) => s + a.evidencias_total, 0);
  const evOk = concluidas.reduce((s, a) => s + a.evidencias_verificadas, 0);
  const compat = concluidas.reduce((s, a) => s + a.resultados.COMPATIVEL + a.resultados.PARCIAL, 0);

  render(el, html`
    <section class="hero">
      <div class="eyebrow" style="color:#7fd8cc">AKCIT Camp 2026 · MVP v${status.versao}</div>
      <h1>Oportunidades públicas, qualificadas com evidência.</h1>
      <p>O ObraNexo lê contratações do PNCP, compara cada requisito técnico com o catálogo do fornecedor e entrega um dossiê
         em que toda conclusão aponta para o trecho do documento que a sustenta.</p>
      <div class="actions">
        <a class="btn btn-primary btn-lg" href="#/demandas">${icon('play')} Analisar uma demanda</a>
        <a class="btn btn-lg" href="#/catalogo">${icon('box')} Ver catálogo (${status.empresa})</a>
        <a class="btn btn-lg" href="#/sobre">${icon('info')} Como funciona</a>
      </div>
    </section>

    <div class="grid grid-4" style="margin-top:18px">
      <div class="card kpi"><div class="kpi-label">Casos disponíveis</div><div class="kpi-value">${casos.length}</div><div class="kpi-sub">contratações reais congeladas do PNCP</div></div>
      <div class="card kpi"><div class="kpi-label">Análises</div><div class="kpi-value">${concluidas.length}</div><div class="kpi-sub">${compat} item(ns) compatível(is) ou parcial(is)</div></div>
      <div class="card kpi"><div class="kpi-label">Rastreabilidade</div><div class="kpi-value ${evTotal && evOk === evTotal ? 'ok' : ''}">${evTotal ? pct(evOk / evTotal) : '—'}</div><div class="kpi-sub">${evOk} de ${evTotal} citações conferidas no documento</div></div>
      <div class="card kpi"><div class="kpi-label">Agentes de IA</div><div class="kpi-value" style="font-size:19px;padding-top:6px">${status.llm.disponivel ? status.llm.provedor : 'Determinístico'}</div><div class="kpi-sub">${status.llm.disponivel ? status.llm.modelo_agente : 'sem chave de API configurada'}</div></div>
    </div>

    <div class="grid grid-main" style="margin-top:16px">
      <div class="card">
        <div class="card-head"><h2>Análises recentes</h2><a class="btn btn-ghost btn-sm" href="#/analises">Ver todas ${icon('arrow')}</a></div>
        ${analises.length ? html`
          <div class="table-wrap"><table class="table">
            <thead><tr><th>Contratação</th><th>Tipo</th><th class="num">Prioridade</th><th>Revisão</th><th>Quando</th></tr></thead>
            <tbody>${analises.slice(0, 6).map((a) => html`
              <tr class="clicavel" data-href="#/analises/${a.id}">
                <td><div class="truncate" style="max-width:320px;font-weight:600">${a.contratacao.orgao_nome}</div><div class="muted small">${local(a.contratacao)} · ${a.contratacao.id}</div></td>
                <td>${a.tipo_oportunidade ? badgeTipo(a.tipo_oportunidade) : html`<span class="badge b-bad">erro</span>`}</td>
                <td class="num"><strong>${a.prioridade ?? '—'}</strong></td>
                <td>${a.revisao ? badgeRevisao(a.revisao) : ''}</td>
                <td class="nowrap muted small">${data(a.iniciada_em, true)}</td>
              </tr>`)}</tbody>
          </table></div>`
        : vazio('Nenhuma análise ainda', 'Escolha uma demanda e execute a primeira análise.', html`<a class="btn btn-primary" href="#/demandas">${icon('play')} Ir para demandas</a>`)}
      </div>

      <div class="card">
        <div class="card-head"><h2>Casos para demonstração</h2></div>
        <ul class="list" style="padding:4px 20px">
          ${casos.map((c) => html`
            <li>
              <a href="#/casos/${c.nome}" style="font-weight:600">${c.contratacao.orgao_nome}</a>
              <div class="muted small clamp-2">${c.contratacao.objeto}</div>
              <div class="meta" style="margin-top:6px">
                <span>${icon('money')}${moedaCompacta(c.contratacao.valor_estimado)}</span>
                <span>${c.n_itens} itens</span>
                ${badgePrazo(new Date(c.contratacao.data_encerramento_proposta) > new Date() ? 'ABERTA' : 'ENCERRADA')}
              </div>
            </li>`)}
        </ul>
      </div>
    </div>

    <div class="card card-pad" style="margin-top:16px">
      <div class="eyebrow">Fluxo agêntico</div>
      <div class="fluxo">
        <span>Catálogo</span><b>→</b><span>Coleta PNCP</span><b>→</b><span>Leitura dos PDFs</span><b>→</b>
        <span class="agente">Analista Técnico</span><b>→</b><span>Motor de regras</span><b>→</b>
        <span class="agente">Investigador</span><b>→</b><span class="agente">Verificador</span><b>→</b>
        <span>Qualificação</span><b>→</b><span class="agente">Planejador</span><b>→</b><span>Dossiê</span>
      </div>
    </div>`);

  el.querySelectorAll('tr[data-href]').forEach((tr) => tr.addEventListener('click', () => { location.hash = tr.dataset.href; }));
}

export { render_ as render };
