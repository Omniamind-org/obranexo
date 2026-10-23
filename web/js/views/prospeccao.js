// Agente de Prospecção: o LLM decide o que buscar no PNCP, examina itens, escolhe o que analisar a fundo e ranqueia.

import { acompanharJob, api } from '../api.js';
import { data, hora, moeda } from '../format.js';
import { badgePrazo, html, icon, render, toast, vazio } from '../ui.js';

const ROTULO_NO = {
  inicio: 'Início', buscar: 'Busca no PNCP', ver_itens: 'Itens', analisar: 'Análise completa', raciocinio: 'Raciocínio',
  concluir: 'Conclusão', fim: 'Fim', erro: 'Erro',
};

function linhaEvento(ev) {
  const sub = ev.no.startsWith('↳');
  return html`<li style="${sub ? 'opacity:.75' : ''}"><span class="ts">${hora(ev.ts)}</span><span class="no">${ROTULO_NO[ev.no] || ev.no}</span><span>${ev.mensagem}</span></li>`;
}

function cartaoRanking(r, i) {
  const c = r.contratacao || {};
  const encerra = c.encerra ? c.encerra.split('/').reverse().join('-') : null;
  return html`
    <div class="card demanda">
      <div style="flex:none;text-align:center;min-width:64px">
        <div class="score-ring" style="--v:${r.nota};width:58px;height:58px"><span style="width:46px;height:46px;font-size:15px">${Math.round(r.nota)}</span></div>
        <div class="muted small" style="margin-top:4px">#${i + 1}</div>
      </div>
      <div class="demanda-main">
        <div class="demanda-org">${c.orgao || r.contratacao_id}</div>
        <div class="demanda-obj clamp-2">${c.objeto || ''}</div>
        <div class="quote" style="margin:8px 0">${r.justificativa}</div>
        <div class="meta">
          <span>${icon('pin')}${c.municipio || '—'}</span>
          <span>${icon('money')}${moeda(c.valor_estimado)}</span>
          ${c.encerra ? html`<span>${icon('calendar')}encerra ${c.encerra}</span>` : ''}
          ${encerra ? badgePrazo(new Date(encerra) >= new Date(new Date().toDateString()) ? 'ABERTA' : 'ENCERRADA') : ''}
          <span class="mono">${r.contratacao_id}</span>
        </div>
      </div>
      <div class="demanda-side">
        ${r.analise_id
          ? html`<a class="btn btn-primary" href="#/analises/${r.analise_id}">${icon('file')} Ver dossiê</a><div class="muted small" style="text-align:center">analisada a fundo</div>`
          : html`<span class="badge plain" style="justify-content:center">triagem pelo objeto/itens</span>`}
      </div>
    </div>`;
}

async function telaResultado(alvo, id) {
  const { prospeccao: p, resumo } = await api.prospeccao(id);
  const passos = p.passos.filter((x) => x.tipo === 'ferramenta');
  render(alvo, html`
    ${p.status === 'erro' ? html`<div class="alert alert-bad" style="margin-bottom:14px">${icon('alert')}<div class="alert-body"><strong>A prospecção terminou com erro.</strong> ${p.erro}</div></div>` : ''}
    <div class="grid grid-4" style="margin-bottom:16px">
      <div class="card kpi"><div class="kpi-label">Buscas no PNCP</div><div class="kpi-value">${p.buscas.length}</div><div class="kpi-sub">${p.buscas.map((b) => `${b.uf}: ${b.resultados}`).join(' · ') || '—'}</div></div>
      <div class="card kpi"><div class="kpi-label">Licitações consideradas</div><div class="kpi-value">${resumo.candidatos}</div><div class="kpi-sub">${Object.values(p.candidatos).filter((c) => c.itens_vistos).length} com itens examinados</div></div>
      <div class="card kpi"><div class="kpi-label">Análises completas</div><div class="kpi-value">${resumo.analises}</div><div class="kpi-sub">limite ${p.parametros.max_analises}</div></div>
      <div class="card kpi"><div class="kpi-label">Agente</div><div class="kpi-value">${resumo.llm.chamadas}</div><div class="kpi-sub">chamadas · ${resumo.duracao_s}s</div></div>
    </div>
    ${p.resumo ? html`<div class="card card-pad" style="margin-bottom:16px"><div class="eyebrow">Resumo do agente</div><p style="margin:0">${p.resumo}</p></div>` : ''}
    <div class="section-title" style="margin-top:0">Ranking de oportunidades</div>
    ${p.ranking.length ? html`<div class="stack">${p.ranking.map(cartaoRanking)}</div>` : vazio('Nenhuma oportunidade ranqueada', 'O agente não encontrou licitações abertas aderentes ao catálogo nesta busca.')}
    <details class="item" style="margin-top:16px">
      <summary style="grid-template-columns:1fr auto"><span class="t">Trilha de decisões do agente (${passos.length} chamadas de ferramenta)</span><span class="muted small">expandir</span></summary>
      <div class="item-body"><ul class="timeline" style="max-height:none">
        ${p.passos.map((x) => (x.tipo === 'ferramenta'
          ? html`<li style="grid-template-columns:64px 190px 1fr"><span class="ts">passo ${x.passo}</span><span class="no">${x.ferramenta}</span><span><span class="mono small">${JSON.stringify(x.entrada).slice(0, 300)}</span><div class="muted small">→ ${String(x.saida).slice(0, 260)}</div></span></li>`
          : html`<li style="grid-template-columns:64px 190px 1fr"><span class="ts">passo ${x.passo}</span><span class="no">raciocínio</span><span>${x.texto}</span></li>`))}
      </ul></div>
    </details>`);
}

export async function render_(el, id) {
  if (id) {
    render(el, html`
      <div class="crumbs"><a href="#/agente">Agente de prospecção</a> / ${id}</div>
      <div class="page-head"><div><div class="eyebrow">Prospecção</div><h1>Oportunidades encontradas pelo agente</h1></div>
        <a class="btn" href="#/agente">${icon('refresh')} Nova prospecção</a></div>
      <div id="res"></div>`);
    await telaResultado(el.querySelector('#res'), id);
    return undefined;
  }

  const [status, catalogo, anteriores] = await Promise.all([api.status(), api.catalogo(), api.prospeccoes()]);
  const ufs = catalogo.empresa.ufs_atendidas.length ? catalogo.empresa.ufs_atendidas : ['GO'];
  render(el, html`
    <div class="page-head">
      <div>
        <div class="eyebrow">Agente autônomo</div>
        <h1>Prospecção de oportunidades</h1>
        <p>O agente lê o seu catálogo, decide o que buscar no PNCP entre as licitações com propostas abertas, examina os itens,
           escolhe quais vale analisar a fundo (edital, Investigador, Verificador) e entrega um ranking justificado.</p>
      </div>
    </div>
    ${status.llm.disponivel ? '' : html`<div class="alert alert-warn" style="margin-bottom:16px">${icon('alert')}<div class="alert-body">A prospecção exige um provedor de LLM. Configure <code>GEMINI_API_KEY</code> no <code>.env</code>.</div></div>`}
    <div class="card card-pad">
      <form class="form-row" id="form">
        <div class="field" style="font-size:12.5px;font-weight:600;color:var(--text-2)">UFs
          <div class="chips" id="ufs" style="margin-top:5px">${ufs.map((u, i) => html`<label class="chip ${i === 0 ? 'ativo' : ''}"><input type="checkbox" value="${u}" ${i === 0 ? 'checked' : ''} hidden>${u}</label>`)}</div>
        </div>
        <label class="field">Propostas encerrando em<select name="horizonte"><option value="15">15 dias</option><option value="30" selected>30 dias</option><option value="60">60 dias</option></select></label>
        <label class="field">Análises completas<select name="max"><option value="1">1</option><option value="2" selected>2</option><option value="3">3</option></select></label>
        <button class="btn btn-primary btn-lg" type="submit" ${status.llm.disponivel ? '' : 'disabled'}>${icon('bolt')} Iniciar prospecção</button>
      </form>
      <p class="muted small" style="margin:10px 0 0">Catálogo: <strong>${catalogo.empresa.nome}</strong> (${catalogo.produtos.length} produtos) · modelo ${status.llm.modelo_agente || '—'}.
        Cada análise completa usa várias chamadas ao LLM; no nível gratuito, uma prospecção leva alguns minutos.</p>
    </div>
    <div id="execucao"></div>
    <div class="section-title">Prospecções anteriores</div>
    <div class="card">
      ${anteriores.length ? html`<div class="table-wrap"><table class="table">
        <thead><tr><th>Quando</th><th>UFs</th><th class="num">Consideradas</th><th class="num">Analisadas</th><th>Melhor oportunidade</th><th>Status</th></tr></thead>
        <tbody>${anteriores.map((p) => html`<tr class="clicavel" data-href="#/agente/${p.id}">
          <td class="nowrap small">${data(p.iniciada_em, true)}</td><td>${(p.parametros.ufs || []).join(', ')}</td>
          <td class="num">${p.candidatos}</td><td class="num">${p.analises}</td>
          <td><div class="truncate" style="max-width:360px">${p.melhor ? `${Math.round(p.melhor.nota)} · ${p.melhor.contratacao?.orgao || p.melhor.contratacao_id}` : '—'}</div></td>
          <td>${p.status === 'concluida' ? html`<span class="badge b-ok">concluída</span>` : html`<span class="badge b-bad">${p.status}</span>`}</td></tr>`)}</tbody>
      </table></div>` : vazio('Nenhuma prospecção ainda')}
    </div>`);

  el.querySelectorAll('tr[data-href]').forEach((tr) => tr.addEventListener('click', () => { location.hash = tr.dataset.href; }));
  el.querySelector('#ufs').addEventListener('change', () => {
    el.querySelectorAll('#ufs label').forEach((l) => l.classList.toggle('ativo', l.querySelector('input').checked));
  });

  let parar = null;
  el.querySelector('#form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const escolhidas = [...el.querySelectorAll('#ufs input:checked')].map((i) => i.value);
    if (!escolhidas.length) { toast('Escolha ao menos uma UF', 'erro'); return; }
    const botao = e.currentTarget.querySelector('button[type=submit]');
    botao.disabled = true;
    botao.innerHTML = '<span class="spinner"></span> Agente trabalhando…';
    const alvo = el.querySelector('#execucao');
    render(alvo, html`<div class="card" style="margin-top:16px">
      <div class="card-head"><h2>O agente está trabalhando</h2><span class="muted small" id="st">iniciando…</span></div>
      <ul class="timeline" id="tl" style="padding:6px 16px;max-height:480px"></ul></div>`);
    const tl = alvo.querySelector('#tl');
    try {
      const job = await api.iniciarProspeccao({ ufs: escolhidas, horizonte_dias: Number(f.get('horizonte')), max_analises: Number(f.get('max')) });
      alvo.querySelector('#st').textContent = 'em execução';
      parar = acompanharJob(job.id, {
        onEvento: (ev) => {
          tl.insertAdjacentHTML('beforeend', linhaEvento(ev).s);
          tl.scrollTop = tl.scrollHeight;
        },
        onFim: (fim) => {
          if (fim.prospeccao_id) {
            toast(fim.status === 'concluida' ? 'Prospecção concluída' : 'Prospecção terminou com erro', fim.status === 'concluida' ? 'ok' : 'erro');
            location.hash = `#/agente/${fim.prospeccao_id}`;
          } else {
            toast(fim.erro || 'Falha na prospecção', 'erro', 8000);
            botao.disabled = false;
            botao.innerHTML = `${icon('bolt').s} Iniciar prospecção`;
          }
        },
        onErro: (err) => toast(err.message, 'erro'),
      });
    } catch (err) {
      toast(err.message, 'erro', 8000);
      botao.disabled = false;
      botao.innerHTML = `${icon('bolt').s} Iniciar prospecção`;
    }
  });
  return () => parar?.();
}

export { render_ as render };
