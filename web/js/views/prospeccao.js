// Agente de Prospecção: o LLM decide o que buscar no PNCP, examina itens, escolhe o que analisar a fundo e ranqueia.

import { acompanharJob, api } from '../api.js';
import { nota, prazo } from '../charts.js';
import { data, hora, moedaCompacta, nomeProprio } from '../format.js';
import { aviso, html, icon, render, toast, vazio } from '../ui.js';

const ROTULO_NO = {
  inicio: 'Início', buscar: 'Busca no PNCP', ver_itens: 'Itens', analisar: 'Análise', raciocinio: 'Raciocínio',
  concluir: 'Conclusão', fim: 'Fim', erro: 'Erro',
};

const isoDeBr = (s) => (s ? s.split('/').reverse().join('-') : null);

function linhaRanking(r, i) {
  const c = r.contratacao || {};
  return html`
    <div class="linha" style="grid-template-columns:40px 150px minmax(0,1fr) 150px 130px;align-items:start">
      <div class="muted" style="font-weight:650;padding-top:2px">${i + 1}º</div>
      ${nota(r.nota, 'Nota do agente (0–100): aderência do catálogo, valor e prazo')}
      <div style="min-width:0">
        <div class="linha-titulo">${nomeProprio(c.orgao) || r.contratacao_id}</div>
        <div class="linha-sub truncate">${c.municipio || ''}${c.objeto ? ` · ${c.objeto}` : ''}</div>
        <p class="small ink-2 clamp-2" style="margin-top:6px" data-tip="${r.justificativa}">${r.justificativa}</p>
      </div>
      <div class="num">
        <div style="font-weight:600">${moedaCompacta(c.valor_estimado)}</div>
        <div style="margin-top:2px">${c.encerra ? prazo(`${isoDeBr(c.encerra)}T23:59:00`) : ''}</div>
      </div>
      <div class="num">${r.analise_id
        ? html`<a class="btn btn-sm" href="#/analises/${r.analise_id}">Ver análise</a>`
        : html`<span class="muted small" data-tip="Avaliada pelo objeto e pelos itens, sem análise completa do edital">só triagem</span>`}</div>
    </div>`;
}

function trilha(p) {
  return html`<ul class="feed">${p.passos.map((x) => (x.tipo === 'ferramenta'
    ? html`<li><span class="ts">passo ${x.passo}</span><span class="no">${x.ferramenta}</span><span><span class="small">${JSON.stringify(x.entrada).slice(0, 300)}</span><div class="muted small">→ ${String(x.saida).slice(0, 260)}</div></span></li>`
    : html`<li><span class="ts">passo ${x.passo}</span><span class="no">raciocínio</span><span>${x.texto}</span></li>`))}</ul>`;
}

async function telaResultado(el, id) {
  const { prospeccao: p, resumo } = await api.prospeccao(id);
  render(el, html`
    <a class="voltar" href="#/agente">${icon('back')} Prospecção</a>
    <div class="page-head">
      <div>
        <h1>Oportunidades encontradas</h1>
        <p class="sub">${data(p.iniciada_em, true)} · ${(p.parametros.ufs || []).join(', ')}</p>
      </div>
      <a class="btn" href="#/agente">${icon('refresh')} Nova prospecção</a>
    </div>
    ${p.status === 'erro' ? html`<div style="margin-bottom:24px">${aviso(html`<strong>A prospecção terminou com erro.</strong> ${p.erro}`, 'bad', 'alert')}</div>` : ''}
    <div class="numeros" style="margin-bottom:36px">
      <div class="numero"><b>${resumo.candidatos}</b><span>licitações consideradas</span></div>
      <div class="numero"><b>${p.ranking.length}</b><span>ranqueadas</span></div>
      <div class="numero"><b>${resumo.analises}</b><span>analisadas a fundo</span></div>
    </div>
    ${p.resumo ? html`<p class="resumo-exec" style="max-width:820px;margin-bottom:36px">${p.resumo}</p>` : ''}
    <div class="secao-head"><h2>Ranking</h2></div>
    ${p.ranking.length ? html`<div class="linhas">${p.ranking.map(linhaRanking)}</div>`
      : vazio('Nenhuma oportunidade ranqueada', 'O agente não encontrou licitações abertas aderentes ao catálogo nesta busca.')}
    <details class="mais secao" style="margin-top:40px">
      <summary>Como o agente decidiu (${p.passos.filter((x) => x.tipo === 'ferramenta').length} ações)</summary>
      ${trilha(p)}
    </details>`);
}

export async function render_(el, id) {
  if (id) {
    await telaResultado(el, id);
    return undefined;
  }

  const [status, catalogo, anteriores] = await Promise.all([api.status(), api.catalogo(), api.prospeccoes()]);
  const ufs = catalogo.empresa.ufs_atendidas.length ? catalogo.empresa.ufs_atendidas : ['GO'];
  render(el, html`
    <div class="page-head">
      <div>
        <h1>Prospecção</h1>
        <p class="sub">O agente lê o seu catálogo, busca licitações com propostas abertas no PNCP, examina os itens,
          analisa a fundo as mais promissoras e entrega um ranking justificado.</p>
      </div>
    </div>
    ${status.llm.disponivel ? '' : html`<div style="margin-bottom:24px">${aviso('A prospecção precisa de um provedor de IA. Escolha um no topo da página ou configure GEMINI_API_KEY no .env.', 'warn', 'alert')}</div>`}
    <form class="form-row" id="form">
      <div class="field">Onde buscar
        <div class="pilulas" id="ufs">${ufs.map((u, i) => html`<label class="pilula ${i === 0 ? 'ativo' : ''}"><input type="checkbox" value="${u}" ${i === 0 ? 'checked' : ''} hidden>${u}</label>`)}</div>
      </div>
      <label class="field">Propostas encerrando em<select name="horizonte"><option value="15">até 15 dias</option><option value="30" selected>até 30 dias</option><option value="60">até 60 dias</option></select></label>
      <label class="field" data-tip="Quantas licitações o agente pode analisar a fundo (edital completo). Mais análises = mais tempo.">Análises completas<select name="max"><option value="1">1</option><option value="2" selected>2</option><option value="3">3</option></select></label>
      <button class="btn btn-primary btn-lg" type="submit" ${status.llm.disponivel ? '' : 'disabled'}>${icon('bolt')} Buscar oportunidades</button>
    </form>
    <p class="muted small" style="margin-top:10px">Catálogo: ${catalogo.empresa.nome} · ${catalogo.produtos.length} produtos. Leva alguns minutos.</p>
    <div id="execucao"></div>

    ${anteriores.length ? html`
      <section class="secao">
        <div class="secao-head"><h2>Prospecções anteriores</h2></div>
        <div class="linhas">${anteriores.map((p) => html`
          <a class="linha" href="#/agente/${p.id}" style="grid-template-columns:170px minmax(0,1fr) 150px 170px">
            <div><div class="linha-titulo">${data(p.iniciada_em, true)}</div><div class="linha-sub">${(p.parametros.ufs || []).join(', ')}</div></div>
            <div style="min-width:0">${p.melhor
              ? html`<div class="linha-sub">melhor oportunidade</div><div class="truncate" style="font-weight:550">${nomeProprio(p.melhor.contratacao?.orgao) || p.melhor.contratacao_id}</div>`
              : html`<span class="muted">${p.status === 'concluida' ? 'nenhuma oportunidade aderente' : 'terminou com erro'}</span>`}</div>
            ${p.melhor ? nota(p.melhor.nota) : html`<span></span>`}
            <div class="num small ink-2">${p.candidatos} vistas · ${p.analises} analisadas</div>
          </a>`)}</div>
      </section>` : ''}`);

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
    botao.innerHTML = '<span class="spinner"></span> Buscando…';
    const alvo = el.querySelector('#execucao');
    render(alvo, html`
      <section style="margin-top:28px">
        <div class="agora"><span class="spinner" id="girando"></span><span id="agora">O agente está começando…</span></div>
        <details class="mais" style="margin-top:14px"><summary>Ver detalhes</summary><ul class="feed" id="tl"></ul></details>
      </section>`);
    const tl = alvo.querySelector('#tl');
    const agora = alvo.querySelector('#agora');
    const restaurar = () => {
      botao.disabled = false;
      botao.innerHTML = `${icon('bolt').s} Buscar oportunidades`;
      alvo.querySelector('#girando')?.remove();
    };
    try {
      const job = await api.iniciarProspeccao({ ufs: escolhidas, horizonte_dias: Number(f.get('horizonte')), max_analises: Number(f.get('max')) });
      parar = acompanharJob(job.id, {
        onEvento: (ev) => {
          const sub = ev.no.startsWith('↳');
          if (!sub) agora.textContent = ev.mensagem;
          tl.insertAdjacentHTML('beforeend', html`<li class="${sub ? 'sub' : ''}"><span class="ts">${hora(ev.ts)}</span><span class="no">${ROTULO_NO[ev.no] || ev.no}</span><span>${ev.mensagem}</span></li>`.s);
          tl.scrollTop = tl.scrollHeight;
        },
        onFim: (fim) => {
          if (fim.prospeccao_id) {
            toast(fim.status === 'concluida' ? 'Prospecção concluída' : 'Prospecção terminou com erro', fim.status === 'concluida' ? 'ok' : 'erro');
            location.hash = `#/agente/${fim.prospeccao_id}`;
          } else {
            agora.textContent = fim.erro || 'Falha na prospecção';
            toast(fim.erro || 'Falha na prospecção', 'erro', 8000);
            restaurar();
          }
        },
        onErro: (err) => toast(err.message, 'erro'),
      });
    } catch (err) {
      agora.textContent = err.message;
      toast(err.message, 'erro', 8000);
      restaurar();
    }
  });
  return () => parar?.();
}

export { render_ as render };
