// Detalhe de um caso congelado + execução da análise com acompanhamento ao vivo (SSE).

import { acompanharJob, api } from '../api.js';
import { data, hora, local, moeda, numero } from '../format.js';
import { badgePrazo, html, icon, render, toast } from '../ui.js';

export const ETAPAS = [
  ['carregar_contexto', 'Contexto', 'catálogo × contratação'],
  ['coletar_documentos', 'Documentos', 'leitura dos anexos'],
  ['extrair_itens', 'Analista Técnico', 'requisitos dos itens'],
  ['filtrar_relevantes', 'Portfólio', 'itens do catálogo'],
  ['casar_com_catalogo', 'Motor de regras', 'compatibilidade'],
  ['investigador', 'Investigador', 'busca no edital'],
  ['varrer_insumos', 'Insumos', 'obras/serviços'],
  ['verificador', 'Verificador', 'citações e conflitos'],
  ['qualificar', 'Qualificação', 'tipo, prazo, prioridade'],
  ['planejador', 'Planejador', 'próximos passos'],
  ['gerar_dossie', 'Dossiê', 'documento final'],
];

export async function render_(el, nome) {
  const caso = await api.caso(nome);
  const c = caso.contratacao;
  const aberta = c.data_encerramento_proposta && new Date(c.data_encerramento_proposta) > new Date();

  render(el, html`
    <div class="crumbs"><a href="#/demandas">Demandas</a> / ${caso.nome}</div>
    <div class="page-head">
      <div>
        <div class="eyebrow">${c.modalidade || 'Contratação'}${c.numero_compra ? ` nº ${c.numero_compra}/${c.ano}` : ''}</div>
        <h1>${c.orgao_nome}</h1>
        <p>${c.objeto}</p>
      </div>
      <div class="actions">
        <a class="btn" href="${c.link_oficial}" target="_blank" rel="noopener">${icon('external')} Ver no PNCP</a>
        <button class="btn btn-primary btn-lg" id="executar">${icon('play')} Executar análise</button>
      </div>
    </div>

    <div class="grid grid-4">
      <div class="card kpi"><div class="kpi-label">Valor estimado</div><div class="kpi-value" style="font-size:21px">${moeda(c.valor_estimado)}</div><div class="kpi-sub">${c.valor_homologado ? `homologado ${moeda(c.valor_homologado)}` : 'sem valor homologado'}</div></div>
      <div class="card kpi"><div class="kpi-label">Local</div><div class="kpi-value" style="font-size:21px">${local(c)}</div><div class="kpi-sub truncate">${c.unidade_nome || '—'}</div></div>
      <div class="card kpi"><div class="kpi-label">Propostas até</div><div class="kpi-value" style="font-size:21px">${data(c.data_encerramento_proposta)}</div><div class="kpi-sub">${badgePrazo(aberta ? 'ABERTA' : 'ENCERRADA')}</div></div>
      <div class="card kpi"><div class="kpi-label">Itens / anexos</div><div class="kpi-value" style="font-size:21px">${caso.itens.length} / ${caso.documentos.length}</div><div class="kpi-sub">${caso.documentos.filter((d) => d.baixado).length} anexo(s) com arquivo local</div></div>
    </div>

    <div id="execucao"></div>

    <div class="grid grid-main" style="margin-top:16px">
      <div class="card">
        <div class="card-head"><h2>Itens da contratação</h2><span class="muted small">${caso.itens.length} itens</span></div>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>#</th><th>Descrição</th><th class="num">Qtd</th><th class="num">Valor unit.</th></tr></thead>
          <tbody>${caso.itens.map((i) => html`
            <tr><td class="muted">${i.numero_item}</td><td><div class="clamp-2" title="${i.descricao}">${i.descricao}</div></td>
            <td class="num">${numero(i.quantidade)} <span class="muted small">${i.unidade || ''}</span></td><td class="num">${moeda(i.valor_unit_estimado)}</td></tr>`)}</tbody>
        </table></div>
      </div>
      <div class="stack">
        <div class="card">
          <div class="card-head"><h2>Anexos</h2></div>
          <ul class="list" style="padding:0 20px;max-height:340px;overflow-y:auto">
            ${caso.documentos.map((d) => html`<li class="small" style="display:flex;gap:8px;align-items:flex-start">
              ${icon(d.baixado ? 'doc' : 'x')}<div style="min-width:0"><div class="truncate" title="${d.nome}">${d.nome}</div><div class="muted">${d.tipo || ''}${d.baixado ? '' : ' · não baixado'}</div></div></li>`)}
          </ul>
        </div>
        <div class="card">
          <div class="card-head"><h2>Análises anteriores</h2></div>
          <ul class="list" style="padding:0 20px">
            ${caso.analises.length ? caso.analises.map((a) => html`<li class="small" style="display:flex;justify-content:space-between;gap:8px">
              <a href="#/analises/${a.id}">${data(a.iniciada_em, true)}</a><span class="muted">${a.modo}${a.status === 'concluida' ? '' : ' · erro'}</span></li>`)
            : html`<li class="muted small">Nenhuma análise deste caso ainda.</li>`}
          </ul>
        </div>
      </div>
    </div>`);

  let parar = null;
  el.querySelector('#executar').addEventListener('click', async (e) => {
    const botao = e.currentTarget;
    botao.disabled = true;
    botao.innerHTML = '<span class="spinner"></span> Executando…';
    const alvo = el.querySelector('#execucao');
    render(alvo, html`
      <div class="card" style="margin-top:16px">
        <div class="card-head"><h2>Execução do fluxo agêntico</h2><span class="muted small" id="exec-status">iniciando…</span></div>
        <div class="card-body">
          <div class="stepper" id="stepper">${ETAPAS.map(([id, nome, sub]) => html`<div class="step" data-etapa="${id}"><strong>${nome}</strong><span>${sub}</span></div>`)}</div>
          <ul class="timeline" id="timeline" style="margin-top:14px"></ul>
        </div>
      </div>`);
    alvo.scrollIntoView({ behavior: 'smooth', block: 'start' });

    const timeline = alvo.querySelector('#timeline');
    const statusEl = alvo.querySelector('#exec-status');
    let etapaAtual = null;
    // Etapas podem se repetir (o motor de regras roda de novo após o Investigador): nunca desmarca o que já terminou.
    const marcar = (no) => {
      const passo = alvo.querySelector(`.step[data-etapa="${no}"]`);
      if (!passo) return;
      alvo.querySelectorAll('.step.ativo').forEach((s) => { s.classList.remove('ativo'); s.classList.add('feito'); });
      passo.classList.remove('feito');
      passo.classList.add('ativo');
      etapaAtual = no;
    };

    try {
      const job = await api.iniciarAnalise(nome);
      statusEl.textContent = 'em execução';
      parar = acompanharJob(job.id, {
        onEvento: (ev) => {
          if (ev.no !== etapaAtual) marcar(ev.no);
          const li = document.createElement('li');
          li.innerHTML = html`<span class="ts">${hora(ev.ts)}</span><span class="no">${ev.no}</span><span>${ev.mensagem}</span>`.s;
          timeline.appendChild(li);
          timeline.scrollTop = timeline.scrollHeight;
        },
        onFim: (fim) => {
          alvo.querySelectorAll('.step').forEach((s) => {
            if (s.classList.contains('ativo')) { s.classList.remove('ativo'); s.classList.add('feito'); }
            if (!s.classList.contains('feito')) s.classList.add('pulado');
          });
          if (fim.status === 'concluida') {
            statusEl.textContent = 'concluída';
            toast('Análise concluída — abrindo o dossiê');
            setTimeout(() => { location.hash = `#/analises/${fim.analise_id}`; }, 700);
          } else {
            statusEl.textContent = 'erro';
            toast(fim.erro || 'A análise terminou com erro', 'erro', 8000);
            botao.disabled = false;
            botao.innerHTML = `${icon('refresh').s} Tentar de novo`;
          }
        },
        onErro: (err) => toast(err.message, 'erro'),
      });
    } catch (err) {
      toast(err.message, 'erro');
      botao.disabled = false;
      botao.innerHTML = `${icon('play').s} Executar análise`;
    }
  });

  return () => parar?.();
}

export { render_ as render };
