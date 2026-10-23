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
      <div class="eyebrow">// RECONHECIMENTO PNCP · PROTOCOLO AKCIT 2026 · V${status.versao}</div>
      <h1>Operações Comerciais & Auditoria Forense de Editais</h1>
      <p>Varredura contínua de contratações públicas no PNCP. Extração determinística de requisitos, cruzamento com catálogo elétrico e verificação cruzada com rastreabilidade de prova documental.</p>
      <div class="actions">
        <a class="btn btn-primary btn-lg" href="#/agente">${icon('bolt')} Prospecção Autônoma</a>
        <a class="btn btn-lg" href="#/demandas">${icon('play')} Radar PNCP</a>
        <a class="btn btn-lg" href="#/catalogo">${icon('box')} Catálogo Ativo (${status.empresa})</a>
        <a class="btn btn-lg" href="#/sobre">${icon('info')} Topologia Agêntica</a>
      </div>
    </section>

    <div class="grid grid-4" style="margin-top:20px">
      <div class="card kpi">
        <div class="kpi-label"><span class="dot on"></span>CH-01 · Casos Congelados</div>
        <div class="kpi-value">${casos.length}</div>
        <div class="kpi-sub">pacotes documentais do PNCP</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label"><span class="dot on"></span>CH-02 · Dossiês Gerados</div>
        <div class="kpi-value">${concluidas.length}</div>
        <div class="kpi-sub">${compat} item(ns) aderente(s)</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label"><span class="dot on"></span>CH-03 · Rastreabilidade</div>
        <div class="kpi-value ${evTotal && evOk === evTotal ? 'ok' : ''}">${evTotal ? pct(evOk / evTotal) : '—'}</div>
        <div class="kpi-sub">${evOk} de ${evTotal} citações conferidas</div>
      </div>
      <div class="card kpi">
        <div class="kpi-label"><span class="dot ${status.llm.disponivel ? 'on' : 'off'}"></span>CH-04 · Núcleo de IA</div>
        <div class="kpi-value" style="font-size:20px;padding-top:4px">${status.llm.disponivel ? status.llm.provedor : 'DETERMINÍSTICO'}</div>
        <div class="kpi-sub truncate" title="${status.llm.disponivel ? status.llm.modelo_agente : 'sem chave configurada'}">${status.llm.disponivel ? status.llm.modelo_agente : 'regras sem LLM'}</div>
      </div>
    </div>

    <div class="grid grid-main" style="margin-top:18px">
      <div class="card">
        <div class="card-head">
          <h2>// Dossiês Recentes</h2>
          <a class="btn btn-ghost btn-sm" href="#/analises">Ver Histórico Completo ${icon('arrow')}</a>
        </div>
        ${analises.length ? html`
          <div class="table-wrap"><table class="table">
            <thead><tr><th>Órgão / Licitação</th><th>Status</th><th class="num">Score</th><th>Revisão</th><th>Registro</th></tr></thead>
            <tbody>${analises.slice(0, 6).map((a) => html`
              <tr class="clicavel" data-href="#/analises/${a.id}">
                <td><div class="truncate" style="max-width:320px;font-weight:600;color:var(--text-bright)">${a.contratacao.orgao_nome}</div><div class="muted small mono">${local(a.contratacao)} · ${a.contratacao.id}</div></td>
                <td>${a.tipo_oportunidade ? badgeTipo(a.tipo_oportunidade) : html`<span class="badge b-bad">erro</span>`}</td>
                <td class="num mono"><strong>${a.prioridade ?? '—'}</strong></td>
                <td>${a.revisao ? badgeRevisao(a.revisao) : ''}</td>
                <td class="nowrap muted small mono">${data(a.iniciada_em, true)}</td>
              </tr>`)}</tbody>
          </table></div>`
        : vazio('Nenhum dossiê gerado', 'Selecione uma demanda no radar e execute a primeira varredura.', html`<a class="btn btn-primary" href="#/demandas">${icon('play')} Iniciar Reconhecimento</a>`)}
      </div>

      <div class="card">
        <div class="card-head"><h2>// Casos de Referência</h2></div>
        <ul class="list" style="padding:4px 20px">
          ${casos.map((c) => html`
            <li>
              <a href="#/casos/${c.nome}" style="font-weight:600;color:var(--text-bright)">${c.contratacao.orgao_nome}</a>
              <div class="muted small clamp-2">${c.contratacao.objeto}</div>
              <div class="meta" style="margin-top:8px">
                <span class="mono">${icon('money')}${moedaCompacta(c.contratacao.valor_estimado)}</span>
                <span class="mono">${c.n_itens} itens</span>
                ${badgePrazo(new Date(c.contratacao.data_encerramento_proposta) > new Date() ? 'ABERTA' : 'ENCERRADA')}
              </div>
            </li>`)}
        </ul>
      </div>
    </div>

    <div class="card card-pad" style="margin-top:18px">
      <div class="eyebrow">// Topologia do Pipeline Agêntico</div>
      <div class="fluxo">
<<<<<<< HEAD
        <span class="agente">Prospecção</span><b>→</b><span>Coleta PNCP</span><b>→</b><span>Leitura dos anexos</span><b>→</b>
        <span class="agente">Analista Técnico</span><b>→</b><span class="agente">Especificador</span><b>→</b><span>Motor de regras</span><b>→</b>
        <span class="agente">Investigador</span><b>→</b><span class="agente">Verificador</span><b>→</b>
        <span>Qualificação</span><b>→</b><span class="agente">Planejador</span><b>→</b><span>Dossiê</span>
=======
        <span>01. Catálogo Técnico</span><b>→</b>
        <span>02. Radar PNCP</span><b>→</b>
        <span>03. Análise Documental</span><b>→</b>
        <span class="agente">04. Analista Técnico (IA)</span><b>→</b>
        <span>05. Motor Determinístico</span><b>→</b>
        <span class="agente">06. Investigador Forense (IA)</span><b>→</b>
        <span class="agente">07. Verificador de Citações (IA)</span><b>→</b>
        <span>08. Qualificação de Risco</span><b>→</b>
        <span class="agente">09. Planejador Estratégico (IA)</span><b>→</b>
        <span>10. Dossiê Comercial</span>
>>>>>>> 28fbc28 (feat(frontend): atualiza layout, logo, emblema e telemetria)
      </div>
    </div>`);

  el.querySelectorAll('tr[data-href]').forEach((tr) => tr.addEventListener('click', () => { location.hash = tr.dataset.href; }));
}

export { render_ as render };
