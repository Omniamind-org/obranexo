// Resultado de uma análise: resumo visual, itens × catálogo, provas, pendências, dossiê e trilha do agente.

import { api } from '../api.js';
import { barras, COR_RESULTADO, gauge, legendaResultados, medidor, prazo, RESULTADOS, ROTULO_RESULTADO, waffle } from '../charts.js';
import { dolar, hora, latencia, local, moeda, moedaCompacta, numero, OPERADOR, pct, valorTecnico, nomeProprio } from '../format.js';
import { renderMarkdown } from '../markdown.js';
import {
  abrirModal, aviso, badgeConfianca, badgePrazo, badgeRequisito, badgeResultado, badgeRevisao, badgeTipo,
  carregando, esc, html, icon, raw, render, rotuloAgente, rotuloOperacao, toast, vazio,
} from '../ui.js';
import { rotuloCategoria } from './catalogo.js';

const ORDEM = { COMPATIVEL: 3, PARCIAL: 2, INDETERMINADO: 1, INCOMPATIVEL: 0 };

export async function render_(el, id) {
  const dados = await api.analise(id);
  const { analise: a, resumo, produtos, atributos } = dados;
  const ctx = montarContexto(a, produtos, atributos);
  const c = a.contratacao;

  if (a.status !== 'concluida') {
    render(el, html`<a class="voltar" href="#/analises">${icon('back')} Análises</a>
      ${aviso(html`<strong>A análise terminou com erro.</strong> ${a.erro}`, 'bad', 'alert')}`);
    return;
  }

  const pendencias = a.lacunas.length + a.conflitos.length + a.revisao_humana.filter((x) => !x.startsWith('Parecer')).length;
  const abas = [
    ['resumo', 'Resumo', null],
    ['itens', 'Itens', a.itens.length],
    ['provas', 'Provas', a.evidencias.length],
    ['pendencias', 'Pendências', pendencias || null],
    ['dossie', 'Dossiê e decisão', null],
    ['trilha', 'Trilha do agente', null],
  ];

  render(el, html`
    <a class="voltar" href="#/analises">${icon('back')} Análises</a>
    <div class="page-head" style="margin-bottom:24px">
      <div style="min-width:0;flex:1">
        <div class="sobretitulo">${c.modalidade || 'Contratação'}${c.numero_compra ? ` nº ${c.numero_compra}/${c.ano}` : ''} · ${local(c)}</div>
        <h1>${nomeProprio(c.orgao_nome)}</h1>
        <p class="sub clamp-2" data-tip="${c.objeto}">${c.objeto}</p>
        <div class="fatos" style="margin-top:14px">
          <span data-tip="Valor estimado da contratação">${icon('money')}${moeda(c.valor_estimado)}</span>
          <span>${icon('calendar')}${prazo(c.data_encerramento_proposta)}</span>
          ${badgeTipo(resumo.tipo_oportunidade)}
          ${badgeRevisao(resumo.revisao)}
        </div>
      </div>
      <div class="actions">
        ${resumo.caso ? html`<a class="btn btn-ghost" href="#/casos/${resumo.caso}" data-tip="Analisar de novo esta licitação">${icon('refresh')} Reexecutar</a>` : ''}
        <a class="btn" href="${c.link_oficial}" target="_blank" rel="noopener">${icon('external')} PNCP</a>
        <a class="btn btn-primary" href="${api.dossieDownloadUrl(a.id)}">${icon('download')} Dossiê</a>
      </div>
    </div>
    <div class="tabs" role="tablist">
      ${abas.map(([k, n, cnt], i) => html`<button class="tab ${i === 0 ? 'ativo' : ''}" data-aba="${k}">${n}${cnt !== null ? html`<span class="count">${cnt}</span>` : ''}</button>`)}
    </div>
    <div id="conteudo"></div>`);

  const conteudo = el.querySelector('#conteudo');
  const telas = {
    resumo: () => telaResumo(conteudo, a, resumo, ctx),
    itens: (itemId) => telaItens(conteudo, a, ctx, itemId),
    provas: () => telaProvas(conteudo, a, ctx),
    pendencias: () => telaPendencias(conteudo, a),
    dossie: () => telaDossie(conteudo, a),
    trilha: () => telaTrilha(conteudo, a),
  };
  const abrir = (k, arg) => {
    el.querySelectorAll('.tab').forEach((t) => t.classList.toggle('ativo', t.dataset.aba === k));
    telas[k](arg);
  };
  el.querySelector('.tabs').addEventListener('click', (e) => { const b = e.target.closest('.tab'); if (b) abrir(b.dataset.aba); });
  conteudo.addEventListener('click', (e) => {
    const ev = e.target.closest('[data-ev]');
    if (ev) { abrirEvidencia(a, ctx, ev.dataset.ev); return; }
    const item = e.target.closest('[data-item]');
    if (item) { abrir('itens', item.dataset.item); return; }
    const irAba = e.target.closest('[data-ir-aba]');
    if (irAba) abrir(irAba.dataset.irAba);
  });
  abrir('resumo');
}

// ---------------------------------------------------------------------------- contexto

function montarContexto(a, produtos, atributos) {
  const reqs = Object.fromEntries(a.requisitos.map((r) => [r.id, r]));
  const evs = Object.fromEntries(a.evidencias.map((e) => [e.id, e]));
  const docs = Object.fromEntries(a.documentos.map((d) => [d.id, d]));
  const porItem = {};
  a.correspondencias.forEach((c) => { (porItem[c.item_id] ||= []).push(c); });
  Object.values(porItem).forEach((l) => l.sort((x, y) => (ORDEM[y.resultado] - ORDEM[x.resultado]) || (y.score - x.score)));
  const resultadoItem = (i) => porItem[i.id]?.[0]?.resultado || 'FORA_DO_PORTFOLIO';
  return {
    reqs, evs, docs, porItem, produtos, resultadoItem,
    rotulo: (k) => atributos[k]?.rotulo || k,
    unidade: (k) => atributos[k]?.unidade || '',
  };
}

const nomeDoc = (ctx, id) => {
  const d = ctx.docs[id];
  if (!d) return id;
  return id.startsWith('pncp-item') ? 'Descrição do item' : d.nome.replace(/\.pdf$/i, '');
};

const evBotao = (ctx, evId) => {
  const ev = ctx.evs[evId];
  if (!ev) return html`<span class="muted small">—</span>`;
  return html`<button class="ev-link ${ev.verificada ? '' : 'nv'}" data-ev="${ev.id}" data-tip="“${ev.trecho_literal.slice(0, 220)}”">
    ${icon(ev.verificada ? 'quote' : 'alert')}<span class="truncate">${nomeDoc(ctx, ev.documento_id)}${ev.pagina && !ev.documento_id.startsWith('pncp-item') ? `, p. ${ev.pagina}` : ''}</span></button>`;
};

const valorItem = (i) => (i.quantidade || 0) * (i.valor_unit_estimado || 0);

// ---------------------------------------------------------------------------- resumo

function telaResumo(alvo, a, resumo, ctx) {
  const q = a.qualificacao;
  const passos = q.proximos_passos || [];
  const riscos = q.riscos || [];
  const evOk = resumo.evidencias_verificadas;
  const evTotal = resumo.evidencias_total;
  const pend = resumo.lacunas + resumo.conflitos;

  const itens = a.itens.map((i) => {
    const r = ctx.resultadoItem(i);
    const sku = ctx.porItem[i.id]?.[0] ? ctx.produtos[ctx.porItem[i.id][0].produto_id]?.sku : null;
    return {
      id: i.id, num: i.numero_item, resultado: r,
      tip: `**Item ${i.numero_item} · ${ROTULO_RESULTADO[r]}**${sku ? ` (${sku})` : ''}\n${i.descricao.slice(0, 140)}${i.descricao.length > 140 ? '…' : ''}`,
    };
  });
  const valorPor = {};
  a.itens.forEach((i) => { const r = ctx.resultadoItem(i); valorPor[r] = (valorPor[r] || 0) + valorItem(i); });
  const linhasValor = RESULTADOS.filter(([k]) => valorPor[k]).map(([k, , n]) => ({
    rot: n, valor: valorPor[k], txt: moedaCompacta(valorPor[k]), cor: COR_RESULTADO[k],
    tip: `**${n}**: ${moeda(valorPor[k])} em valor estimado`,
  }));
  const valorAtendido = (valorPor.COMPATIVEL || 0) + (valorPor.PARCIAL || 0);

  render(alvo, html`
    <div class="destaque">
      ${gauge(q.prioridade, 'prioridade')}
      <div class="texto">
        <div class="quem">${q.comprador_provavel}</div>
        <p class="ink-2 clamp-3" style="margin-top:6px;max-width:640px" data-tip="${q.justificativa_prioridade}">${q.justificativa_prioridade}</p>
        <div class="fatos" style="margin-top:10px">${badgePrazo(q.prazo_status)}${a.contratacao.srp ? html`<span class="tag plain" data-tip="Registro de preços: o órgão compra sob demanda durante a vigência da ata">Registro de preços</span>` : ''}</div>
      </div>
    </div>

    <div class="colunas secao" style="margin-top:44px">
      <div>
        <div class="secao-head"><h2>Itens</h2><span class="sub">clique num quadrado para ver o item</span></div>
        ${waffle(itens)}
        ${legendaResultados(resumo.resultados)}

        ${linhasValor.length ? html`
          <div class="secao-head" style="margin-top:40px"><h2>Valor estimado por resultado</h2>
            ${valorAtendido ? html`<span class="sub"><b style="color:var(--ink)">${moedaCompacta(valorAtendido)}</b> em itens atendidos</span>` : ''}</div>
          ${barras(linhasValor)}` : ''}

        ${a.dossie?.resumo_executivo ? html`
          <div class="secao-head" style="margin-top:40px"><h2>Resumo</h2></div>
          <p class="resumo-exec">${a.dossie.resumo_executivo}</p>` : ''}
      </div>

      <div>
        ${passos.length ? html`
          <div class="secao-head"><h2>Próximos passos</h2></div>
          <ol class="passos-lista">${passos.map((p) => html`<li><span>${p}</span></li>`)}</ol>` : ''}
        ${riscos.length ? html`
          <div class="secao-head" style="margin-top:36px"><h2>Riscos</h2></div>
          <ul class="riscos">${riscos.map((r) => html`<li>${icon('alert')}<span>${r}</span></li>`)}</ul>` : ''}

        <div class="secao-head" style="margin-top:36px"><h2>Confiabilidade</h2></div>
        <div class="small ink-2" style="display:flex;justify-content:space-between;margin-bottom:6px">
          <span>Provas conferidas no documento</span><b style="color:var(--ink)">${pct(evTotal ? evOk / evTotal : null)}</b></div>
        ${medidor(evTotal ? evOk / evTotal : 0, { ok: evOk === evTotal, tip: `${evOk} de ${evTotal} trechos citados foram localizados literalmente no documento` })}
        <p class="small ink-2" style="margin-top:14px">${pend
          ? html`${icon('alert')} <button class="ev-link" data-ir-aba="pendencias">${pend} ponto(s) para revisar</button> — informações ausentes ou divergentes.`
          : 'Nenhuma informação ausente ou divergente.'}</p>
        ${a.insumos_indiretos?.length ? html`<p class="small ink-2" style="margin-top:10px">${icon('layers')} <button class="ev-link" data-ir-aba="itens">${a.insumos_indiretos.length} menção(ões)</button> a produtos do catálogo nos projetos e orçamentos (oportunidade indireta).</p>` : ''}
      </div>
    </div>`);
}

// ---------------------------------------------------------------------------- itens

function telaItens(alvo, a, ctx, abrirItemId) {
  const contagem = {};
  a.itens.forEach((i) => { const r = ctx.resultadoItem(i); contagem[r] = (contagem[r] || 0) + 1; });
  let filtro = null;

  const blocoProduto = (c) => {
    const p = ctx.produtos[c.produto_id] || { sku: c.produto_id, nome: '' };
    return html`
      <div class="produto-bloco">
        <div class="produto-head">
          <div><span class="mono muted">${p.sku}</span> <strong>${p.nome}</strong></div>
          <div class="fatos">${badgeResultado(c.resultado)} ${badgeConfianca(c.confianca)}</div>
        </div>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>Exigência</th><th>Edital pede</th><th>Seu produto</th><th>Resultado</th><th>Prova</th></tr></thead>
          <tbody>${c.detalhes.map((d) => {
            const r = ctx.reqs[d.requisito_id] || {};
            const op = OPERADOR[r.operador] || r.operador || '';
            const mostraOp = op && !['exigido', 'contém'].includes(op);
            return html`<tr>
              <td>${ctx.rotulo(d.atributo)}${r.obrigatorio === false ? html` <span class="muted small" data-tip="Requisito desejável: não reprova o item sozinho">(desejável)</span>` : ''}</td>
              <td class="nowrap">${mostraOp ? `${op} ` : ''}${valorTecnico(d.valor_exigido, ctx.unidade(d.atributo))}</td>
              <td>${valorTecnico(d.valor_produto, ctx.unidade(d.atributo))}</td>
              <td><span data-tip="${d.justificativa}">${badgeRequisito(d.resultado)}</span></td>
              <td>${evBotao(ctx, r.evidencia_id)}</td>
            </tr>`;
          })}</tbody>
        </table></div>
      </div>`;
  };

  const desenhar = () => {
    const lista = a.itens.filter((i) => !filtro || ctx.resultadoItem(i) === filtro);
    render(alvo.querySelector('#lista-itens'), lista.length ? html`${lista.map((item) => {
      const cs = ctx.porItem[item.id] || [];
      const melhor = cs[0];
      const p = melhor ? ctx.produtos[melhor.produto_id] : null;
      return html`
        <details class="item" id="item-${item.id}">
          <summary>
            <span class="item-num">${item.numero_item}</span>
            <span class="item-desc" style="min-width:0">
              <span class="t clamp-2">${item.descricao}</span>
              <span class="muted small">${numero(item.quantidade)} ${item.unidade || ''} · ${moeda(item.valor_unit_estimado)} cada · ${rotuloCategoria(item.categoria_inferida)}</span>
            </span>
            <span style="text-align:right">${badgeResultado(melhor ? melhor.resultado : 'FORA_DO_PORTFOLIO')}${p ? html`<div class="mono small muted" style="margin-top:4px">${p.sku}</div>` : ''}</span>
          </summary>
          <div class="item-body">
            ${cs.length ? cs.map(blocoProduto) : html`<p class="ink-2">A categoria <strong>${rotuloCategoria(item.categoria_inferida)}</strong> não está no seu catálogo.</p>`}
          </div>
        </details>`;
    })}` : vazio('Nenhum item com este resultado'));
  };

  const insumos = a.insumos_indiretos || [];
  render(alvo, html`
    <div class="pilulas" id="filtro-itens" style="margin-bottom:12px">
      <button class="pilula ativo" data-r="">Todos <span class="cnt">${a.itens.length}</span></button>
      ${RESULTADOS.filter(([k]) => contagem[k]).map(([k, c, n]) => html`<button class="pilula" data-r="${k}"><i class="${c}" style="width:8px;height:8px;border-radius:50%;display:inline-block"></i>${n} <span class="cnt">${contagem[k]}</span></button>`)}
    </div>
    <div id="lista-itens"></div>
    ${insumos.length ? html`
      <section class="secao">
        <div class="secao-head"><h2>Produtos do catálogo citados nos projetos</h2><span class="sub">oportunidade indireta</span></div>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>Categoria</th><th>Trecho</th><th>Prova</th></tr></thead>
          <tbody>${insumos.map((i) => html`<tr><td class="nowrap">${rotuloCategoria(i.categoria)}</td>
            <td class="small"><div class="clamp-2">${i.trecho}</div></td><td>${evBotao(ctx, i.evidencia_id)}</td></tr>`)}</tbody>
        </table></div>
      </section>` : ''}`);

  alvo.querySelector('#filtro-itens').addEventListener('click', (e) => {
    const b = e.target.closest('.pilula');
    if (!b) return;
    filtro = b.dataset.r || null;
    alvo.querySelectorAll('#filtro-itens .pilula').forEach((x) => x.classList.toggle('ativo', x === b));
    desenhar();
  });
  desenhar();
  const alvoItem = abrirItemId ? alvo.querySelector(`#item-${CSS.escape(abrirItemId)}`) : null;
  if (alvoItem) {
    alvoItem.open = true;
    alvoItem.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

// ---------------------------------------------------------------------------- provas

function telaProvas(alvo, a, ctx) {
  const filtros = {
    todas: () => true,
    edital: (e) => !e.documento_id.startsWith('pncp-item'),
    itens: (e) => e.documento_id.startsWith('pncp-item'),
    nv: (e) => !e.verificada,
  };
  const n = (f) => a.evidencias.filter(filtros[f]).length;
  const desenhar = (f) => {
    const lista = a.evidencias.filter(filtros[f]);
    render(alvo.querySelector('#lista-ev'), lista.length ? html`
      <div class="table-wrap"><table class="table">
        <thead><tr><th style="width:220px">Documento</th><th>Trecho citado</th><th>Conferência</th></tr></thead>
        <tbody>${lista.map((e) => html`
          <tr class="clicavel" data-ev="${e.id}">
            <td class="small"><div class="truncate" style="max-width:220px" data-tip="${ctx.docs[e.documento_id]?.nome || e.documento_id}">${nomeDoc(ctx, e.documento_id)}</div>
              ${e.pagina && !e.documento_id.startsWith('pncp-item') ? html`<div class="muted">página ${e.pagina}</div>` : ''}</td>
            <td><div class="clamp-2">“${e.trecho_literal}”</div></td>
            <td class="nowrap">${e.verificada
              ? html`<span class="res ok" data-tip="Trecho localizado no documento (similaridade ${e.score_match ?? '—'})">${icon('check')}Conferida</span>`
              : html`<span class="res bad" data-tip="O trecho não foi localizado literalmente (similaridade ${e.score_match ?? '—'})">${icon('alert')}Não localizada</span>`}</td>
          </tr>`)}</tbody>
      </table></div>` : vazio('Nenhuma prova neste filtro'));
  };
  render(alvo, html`
    <div class="actions" style="justify-content:space-between;margin-bottom:16px">
      <div class="segmentos" id="filtros-ev">
        <button class="ativo" data-f="todas">Todas ${n('todas')}</button>
        <button data-f="edital">Anexos do edital ${n('edital')}</button>
        <button data-f="itens">Descrições dos itens ${n('itens')}</button>
        ${n('nv') ? html`<button data-f="nv">Não localizadas ${n('nv')}</button>` : ''}
      </div>
      <span class="muted small">Clique num trecho para vê-lo destacado no documento.</span>
    </div>
    <div id="lista-ev"></div>`);
  alvo.querySelector('#filtros-ev').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    alvo.querySelectorAll('#filtros-ev button').forEach((c) => c.classList.toggle('ativo', c === b));
    desenhar(b.dataset.f);
  });
  desenhar('todas');
}

// ---------------------------------------------------------------------------- trilha do agente

function telaTrilha(alvo, a) {
  const passos = a.passos_investigacao;
  render(alvo, html`
    <p class="ink-2" style="margin-bottom:20px;max-width:760px">Etapas que a análise percorreu e, quando acionado, o que o Investigador procurou nos anexos
      (garantia, prazo de entrega, amostra, ensaios) para completar o que a descrição dos itens não dizia.</p>
    ${a.log?.length ? html`<details class="mais" open><summary>Linha do tempo da análise (${a.log.length} eventos)</summary>
      <ul class="feed">${a.log.map((ev) => html`<li><span class="ts">${hora(ev.ts)}</span><span class="no">${ev.no}</span><span>${ev.mensagem}</span></li>`)}</ul></details>` : ''}
    ${passos.length ? html`<details class="mais" style="margin-top:24px"><summary>Passos do Investigador (${passos.length})</summary>
      <ul class="feed">${passos.map((p) => (p.tipo === 'ferramenta'
        ? html`<li><span class="ts">passo ${p.passo}</span><span class="no">${p.ferramenta}</span><span><span class="small">${JSON.stringify(p.entrada)}</span><div class="muted small" style="margin-top:3px">→ ${String(p.saida).slice(0, 320)}</div></span></li>`
        : html`<li><span class="ts">passo ${p.passo}</span><span class="no">raciocínio</span><span>${p.texto}</span></li>`))}</ul></details>` : ''}
    <section class="secao">
      <div class="secao-head"><h2>Chamadas de IA</h2><span class="sub">modelo, tokens, custo estimado e latência de cada chamada</span></div>
      <div id="chamadas-ia">${carregando('Carregando chamadas…')}</div>
    </section>`);
  telaChamadas(alvo.querySelector('#chamadas-ia'), a.id);
}

// ---------------------------------------------------------------------------- chamadas de IA

async function telaChamadas(alvo, analiseId) {
  let dados;
  try {
    dados = await api.chamadas(analiseId);
  } catch (err) {
    render(alvo, aviso(html`<strong>Não foi possível carregar as chamadas.</strong> ${err.message}`, 'bad', 'alert'));
    return;
  }
  if (!alvo.isConnected) return; // a aba já foi trocada
  const chamadas = dados.chamadas || [];
  const r = dados.resumo || {};
  if (!chamadas.length) {
    render(alvo, html`<p class="muted small">Nenhuma chamada de modelo: análise em modo determinístico.</p>`);
    return;
  }

  const tokens = r.tokens || {};
  const lat = r.latencia_ms || {};
  const dicaChamadas = r.chamadas_api !== undefined && r.chamadas_api !== r.chamadas
    ? `${numero(r.chamadas_api)} foram à API; as demais vieram do cache` : '';
  render(alvo, html`
    <div class="numeros" style="margin-bottom:24px">
      <div class="numero" data-tip="${dicaChamadas}"><b>${numero(r.chamadas)}</b><span>chamadas</span></div>
      <div class="numero" data-tip="${numero(tokens.entrada)} tokens de entrada · ${numero(tokens.saida)} de saída · ${numero(tokens.raciocinio)} de raciocínio"><b>${dolar(r.custo_usd)}</b><span>custo estimado</span></div>
      <div class="numero" data-tip="Máxima: ${latencia(lat.maxima)}"><b>${latencia(lat.media)}</b><span>latência média · p95 ${latencia(lat.p95)}</span></div>
      <div class="numero ${r.taxa_cache > 0 ? 'ok' : ''}"><b>${pct(r.taxa_cache)}</b><span>respondidas pelo cache</span></div>
    </div>
    <div class="table-wrap"><table class="table chamadas">
      <thead><tr>
        <th>Quando</th><th>Agente</th><th>Operação</th><th>Modelo</th>
        <th class="num" data-tip="entrada / saída / raciocínio">Tokens</th><th class="num">Custo</th><th class="num">Latência</th><th></th>
      </tr></thead>
      <tbody>${chamadas.map((c) => html`
        <tr class="clicavel chamada" data-chamada="${c.id}">
          <td class="nowrap mono small">${hora(c.quando)}</td>
          <td class="nowrap">${rotuloAgente(c.agente)}${c.versao_prompt ? html` <span class="muted small">${c.versao_prompt}</span>` : ''}</td>
          <td class="nowrap">${rotuloOperacao(c.operacao)}</td>
          <td><div class="fatos">
            <span class="mono small" data-tip="Provedor: ${c.provedor || '—'}">${c.modelo_usado || c.modelo_pedido || '—'}</span>
            ${c.reserva ? html`<span class="tag warn" data-tip="Modelo pedido: ${c.modelo_pedido}" title="Modelo pedido: ${c.modelo_pedido}">reserva</span>` : ''}
            ${c.cache_hit ? html`<span class="tag ok" data-tip="Resposta reaproveitada do cache local">cache</span>` : ''}
            ${c.status === 'erro' ? html`<span class="tag bad">erro</span>` : ''}
          </div></td>
          <td class="num">${numero(c.tokens_entrada)} / ${numero(c.tokens_saida)} / ${numero(c.tokens_raciocinio)}</td>
          <td class="num">${dolar(c.custo_usd)}</td>
          <td class="num">${latencia(c.latencia_ms)}</td>
          <td class="num"><button type="button" class="chamada-abrir" aria-expanded="false" aria-label="Detalhes da chamada">${icon('arrow')}</button></td>
        </tr>
        <tr class="chamada-detalhe" hidden>
          <td colspan="8">
            <div class="fatos small" style="margin-bottom:12px">
              <span>${icon('bolt')}${c.provedor || '—'} · pedido <span class="mono">${c.modelo_pedido || '—'}</span>${c.reserva ? ' → respondeu ' : ''}${c.reserva ? html`<span class="mono">${c.modelo_usado}</span>` : ''}</span>
              ${c.tokens_cache_leitura || c.tokens_cache_escrita ? html`<span>${icon('layers')}cache do provedor: ${numero(c.tokens_cache_leitura || 0)} lidos · ${numero(c.tokens_cache_escrita || 0)} gravados</span>` : ''}
              ${c.origem_tipo ? html`<span>${icon('file')}${c.origem_tipo}${c.origem_id ? html` <span class="mono">${c.origem_id}</span>` : ''}</span>` : ''}
            </div>
            <div class="chamada-painel">
              ${c.erro ? html`<div class="erro"><div class="rotulo">Erro</div><pre class="quebra">${c.erro}</pre></div>` : ''}
              <div><div class="rotulo">Entrada</div><pre class="quebra">${c.entrada_resumo || '—'}</pre></div>
              <div><div class="rotulo">Saída</div><pre class="quebra">${c.saida_resumo || '—'}</pre></div>
            </div>
          </td>
        </tr>`)}</tbody>
    </table></div>`);

  alvo.querySelector('tbody').addEventListener('click', (e) => {
    const linha = e.target.closest('tr.chamada');
    if (!linha) return;
    const detalhe = linha.nextElementSibling;
    const aberto = detalhe.hidden;
    detalhe.hidden = !aberto;
    linha.classList.toggle('aberta', aberto);
    linha.querySelector('.chamada-abrir').setAttribute('aria-expanded', String(aberto));
  });
}

// ---------------------------------------------------------------------------- pendências

function telaPendencias(alvo, a) {
  const parecer = a.revisao_humana.find((x) => x.startsWith('Parecer'));
  const outras = a.revisao_humana.filter((x) => !x.startsWith('Parecer'));
  const vazioTudo = !a.lacunas.length && !a.conflitos.length && !outras.length;
  const lista = (titulo, sub, itens) => (itens.length ? html`
    <section style="margin-bottom:36px">
      <div class="secao-head"><h2>${titulo} <span class="muted" style="font-weight:500">${itens.length}</span></h2><span class="sub">${sub}</span></div>
      <ul class="riscos">${itens.map((x) => html`<li>${icon('alert')}<span>${x}</span></li>`)}</ul>
    </section>` : '');
  render(alvo, html`
    ${vazioTudo ? aviso('Nada pendente: nenhuma informação ausente, divergente ou marcada para revisão.', 'ok', 'check') : ''}
    <div class="colunas" style="margin-top:${vazioTudo ? '28px' : '0'}">
      <div>
        ${lista('Informações ausentes', 'o edital não diz', a.lacunas)}
        ${a.conflitos.length ? html`<section style="margin-bottom:36px">
          <div class="secao-head"><h2>Divergências <span class="muted" style="font-weight:500">${a.conflitos.length}</span></h2><span class="sub">fontes discordam</span></div>
          <ul class="riscos">${a.conflitos.map((c) => html`<li>${icon('alert')}<span>${c.descricao}
            <span class="muted small" style="display:block;margin-top:2px">${c.valores.map((v) => `${v.fonte}: ${valorTecnico(v.valor)}`).join(' · ')}</span></span></li>`)}</ul></section>` : ''}
        ${lista('Para revisão humana', 'conferir antes de decidir', outras)}
      </div>
      <div>${parecer ? html`<div class="secao-head"><h2>Parecer do Verificador</h2></div>
        <div class="markdown small">${raw(renderMarkdown(parecer.replace(/^Parecer do Agente Verificador:\s*/, '')))}</div>` : ''}</div>
    </div>`);
}

// ---------------------------------------------------------------------------- dossiê

function telaDossie(alvo, a) {
  const d = a.dossie;
  const OPCOES = [['APROVADO', 'Seguir'], ['PENDENTE', 'A decidir'], ['REJEITADO', 'Descartar']];
  render(alvo, html`
    <div class="colunas">
      <div class="markdown" id="md">${raw(renderMarkdown(d.conteudo_md))}</div>
      <div>
        <div style="position:sticky;top:96px">
          <div class="secao-head"><h2>Sua decisão</h2>${badgeRevisao(d.status_revisao)}</div>
          <form id="form-revisao">
            <div class="segmentos" style="margin-bottom:14px">
              ${OPCOES.map(([s, n]) => html`<button type="button" data-s="${s}" class="${d.status_revisao === s ? 'ativo' : ''}">${n}</button>`)}
            </div>
            <input type="hidden" name="status" value="${d.status_revisao}">
            <label class="field">Comentário<textarea name="comentario" rows="4" placeholder="Motivo, responsável, próximos contatos…">${d.comentario_usuario}</textarea></label>
            <button class="btn btn-primary" type="submit" style="margin-top:12px;width:100%">${icon('check')} Salvar decisão</button>
          </form>
          <div class="actions" style="margin-top:24px">
            <a class="btn btn-ghost" href="${api.dossieDownloadUrl(a.id)}">${icon('download')} Baixar (.md)</a>
            <button class="btn btn-ghost" id="imprimir">${icon('doc')} Imprimir / PDF</button>
          </div>
        </div>
      </div>
    </div>`);
  const form = alvo.querySelector('#form-revisao');
  form.querySelector('.segmentos').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    form.querySelectorAll('.segmentos button').forEach((x) => x.classList.toggle('ativo', x === b));
    form.elements.status.value = b.dataset.s;
  });
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    try {
      const r = await api.revisar(a.id, f.get('status'), f.get('comentario') || '');
      d.status_revisao = r.revisao;
      d.comentario_usuario = r.comentario;
      toast('Decisão registrada');
      telaDossie(alvo, a);
    } catch (err) { toast(err.message, 'erro'); }
  });
  alvo.querySelector('#imprimir').addEventListener('click', () => {
    const w = window.open('', '_blank');
    w.document.write(`<!doctype html><html lang="pt-BR" data-theme="light"><head><meta charset="utf-8"><title>${esc(d.titulo)}</title><link rel="stylesheet" href="/css/app.css">
      <style>body{background:#fff}.markdown{max-width:860px;margin:30px auto;padding:0 24px}</style></head>
      <body><div class="markdown">${renderMarkdown(d.conteudo_md)}</div><script>setTimeout(()=>print(),300)<\/script></body></html>`);
    w.document.close();
  });
}

// ---------------------------------------------------------------------------- modal de evidência

function realcar(texto, trecho) {
  if (!texto) return html`<span class="muted">Texto da página indisponível.</span>`;
  const tokens = trecho.split(/\s+/).filter(Boolean).slice(0, 40).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  if (!tokens.length) return html`${texto}`;
  for (let n = tokens.length; n >= Math.min(3, tokens.length); n -= Math.max(1, Math.floor(n / 4))) {
    const re = new RegExp(tokens.slice(0, n).join('\\s+'), 'i');
    const m = texto.match(re);
    if (m) {
      const ini = m.index;
      return html`${texto.slice(0, ini)}<mark>${m[0]}</mark>${texto.slice(ini + m[0].length)}`;
    }
  }
  return html`${texto}`;
}

async function abrirEvidencia(a, ctx, evId) {
  const m = abrirModal({ titulo: 'Prova no documento', corpo: html`<div class="empty"><span class="spinner"></span></div>` });
  try {
    const r = await api.evidencia(a.id, evId);
    const ev = r.evidencia;
    const doc = r.documento;
    const ehItem = doc.id.startsWith('pncp-item');
    m.el.querySelector('.modal-head .muted, .modal-head h2').insertAdjacentHTML('afterend',
      html`<div class="muted small" style="margin-top:4px">${ehItem ? 'Descrição do item no PNCP' : `${doc.nome}${ev.pagina ? ` · página ${ev.pagina}` : ''}`}</div>`.s);
    m.el.querySelector('.modal-body').innerHTML = html`
      <div style="margin-bottom:14px">${ev.verificada
        ? html`<span class="res ok">${icon('check')}Trecho localizado no documento</span>`
        : html`<span class="res bad">${icon('alert')}Trecho não localizado literalmente</span>`}</div>
      <div class="citacao" style="margin-bottom:18px">“${ev.trecho_literal}”</div>
      <div class="page-text">${realcar(r.texto_pagina, ev.trecho_literal)}</div>`.s;
    if (doc.url_origem || doc.tem_arquivo) {
      const rodape = document.createElement('div');
      rodape.className = 'modal-foot';
      rodape.innerHTML = html`
        ${doc.url_origem ? html`<a class="btn btn-ghost" href="${doc.url_origem}" target="_blank" rel="noopener">${icon('external')} Origem no PNCP</a>` : ''}
        ${doc.tem_arquivo ? html`<a class="btn btn-primary" href="${api.arquivoUrl(a.id, doc.id, doc.eh_pdf ? ev.pagina : null)}" target="_blank" rel="noopener">${icon('doc')} ${doc.eh_pdf ? `Abrir o PDF na página ${ev.pagina || ''}` : 'Abrir o arquivo'}</a>` : ''}`.s;
      m.el.appendChild(rodape);
    }
    const marca = m.el.querySelector('mark');
    if (marca) marca.scrollIntoView({ block: 'center' });
  } catch (err) {
    m.el.querySelector('.modal-body').innerHTML = aviso(err.message, 'bad', 'alert').s;
  }
}

export { render_ as render };
