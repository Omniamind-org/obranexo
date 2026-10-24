import { api } from '../api.js';
import { barras } from '../charts.js';
import { dolar, latencia, numero, pct } from '../format.js';
import { aviso, html, render, rotuloAgente } from '../ui.js';

const paraNumero = (v) => (typeof v === 'number' ? (v <= 1 ? v * 100 : v) : parseFloat(String(v).replace(',', '.')) || 0);

export async function render_(el) {
  const [m, llm] = await Promise.allSettled([api.metricas(), api.metricasLlm()]).then((rs) => rs.map((r) => (r.status === 'fulfilled' ? r.value : r.reason)));
  if (m instanceof Error) throw m;
  const b = m.benchmark;
  const indicadores = b ? [
    ['Acerto por item', b.acuracia_itens, 'Itens classificados igual ao gabarito revisado'],
    ['Precisão de “compatível”', b.precisao_compativel, 'Quando a análise diz que o produto atende, quantas vezes está certa'],
    ['Incompatibilidades detectadas', b.deteccao_incompatibilidade, 'Quantos produtos que NÃO atendem foram barrados'],
    ['Conclusões com prova', b.rastreabilidade, 'Conclusões ligadas a um trecho conferido no documento'],
  ] : [];
  const decisoes = [['APROVADO', 'Seguir'], ['PENDENTE', 'A decidir'], ['REJEITADO', 'Descartadas']];

  render(el, html`
    <div class="page-head">
      <div><h1>Qualidade</h1><p class="sub">Quanto dá para confiar nas análises: acerto contra gabaritos revisados por pessoas e prova de cada conclusão.</p></div>
    </div>

    <div class="colunas">
      <div>
        <div class="secao-head"><h2>Acerto no benchmark</h2>${b ? html`<span class="sub">gabaritos revisados</span>` : ''}</div>
        ${b ? barras(indicadores.map(([n, v, tip]) => ({ rot: n, valor: paraNumero(v), txt: v, tip }))
          , { max: 100 })
          : aviso(html`Rode <code>python eval/run_benchmark.py</code> para medir o acerto.`)}
      </div>
      <div>
        <div class="secao-head"><h2>Decisões sobre as análises</h2></div>
        ${barras(decisoes.map(([k, n]) => ({ rot: n, valor: m.revisoes[k] || 0, fraca: k === 'PENDENTE' })))}
      </div>
    </div>

    <section class="secao">
      <div class="secao-head"><h2>Operação</h2></div>
      <div class="numeros">
        <div class="numero"><b>${m.concluidas}</b><span>análises concluídas</span></div>
        <div class="numero ${m.rastreabilidade === 1 ? 'ok' : ''}"><b>${pct(m.rastreabilidade)}</b><span>das provas conferidas</span></div>
        <div class="numero"><b>${m.duracao_media_s ?? '—'} s</b><span>em média por licitação</span></div>
        <div class="numero" data-tip="${numero(m.tokens)} tokens no total"><b>${numero(m.chamadas_llm)}</b><span>chamadas à IA · US$ ${m.custo_total_usd}</span></div>
      </div>
    </section>

    <section class="secao">
      <div class="secao-head"><h2>Uso de modelos</h2><span class="sub">todas as análises, prospecções e conversas</span></div>
      ${usoDeModelos(llm)}
    </section>`);
}

// ---------------------------------------------------------------------------- uso de modelos (LLMOps)

function usoDeModelos(llm) {
  if (llm instanceof Error) return aviso(html`<strong>Não foi possível carregar o uso de modelos.</strong> ${llm.message}`, 'bad', 'alert');
  if (!llm || !llm.chamadas) return aviso('Nenhuma chamada de modelo registrada ainda: as análises rodaram em modo determinístico ou a IA ainda não foi usada.');

  const tokens = llm.tokens || {};
  const lat = llm.latencia_ms || {};
  const precos = llm.precos_usd || {};
  const porAgente = [...(llm.por_agente || [])];
  const porModelo = [...(llm.por_modelo || [])].sort((x, y) => (y.custo_usd || 0) - (x.custo_usd || 0));
  const dicaChamadas = llm.chamadas_api !== undefined && llm.chamadas_api !== llm.chamadas
    ? `${numero(llm.chamadas_api)} foram à API; as demais vieram do cache` : '';

  const custoPorAgente = [...porAgente].sort((x, y) => (y.custo_usd || 0) - (x.custo_usd || 0)).map((g) => ({
    rot: rotuloAgente(g.agente), valor: g.custo_usd || 0, txt: dolar(g.custo_usd),
    tip: `**${rotuloAgente(g.agente)}**: ${numero(g.chamadas)} chamadas · ${numero(g.tokens_entrada)} tokens de entrada · ${numero(g.tokens_saida)} de saída`,
  }));
  const latenciaPorAgente = [...porAgente].sort((x, y) => (y.latencia_media_ms || 0) - (x.latencia_media_ms || 0)).map((g) => ({
    rot: rotuloAgente(g.agente), valor: g.latencia_media_ms || 0, txt: latencia(g.latencia_media_ms),
    tip: `**${rotuloAgente(g.agente)}**: ${numero(g.chamadas)} chamadas · ${numero(g.cache_hits)} do cache · ${numero(g.reservas)} em reserva · ${numero(g.erros)} com erro`,
  }));
  const dicaPreco = (modelo) => {
    const p = precos[modelo];
    if (!p) return '';
    return `US$ por 1M tokens — entrada ${numero(p[0])} · saída ${numero(p[1])}${p[2] !== undefined && p[2] !== null ? ` · cache de leitura ${numero(p[2])}` : ''}`;
  };

  return html`
    <div class="numeros" style="margin-bottom:36px">
      <div class="numero" data-tip="${dicaChamadas}"><b>${numero(llm.chamadas)}</b><span>chamadas</span></div>
      <div class="numero" data-tip="${numero(tokens.entrada)} tokens de entrada · ${numero(tokens.saida)} de saída · ${numero(tokens.raciocinio)} de raciocínio · ${numero(tokens.cache_leitura)} lidos do cache do provedor"><b>${dolar(llm.custo_usd)}</b><span>custo total estimado</span></div>
      <div class="numero" data-tip="Máxima: ${latencia(lat.maxima)}"><b>${latencia(lat.media)}</b><span>latência média · p95 ${latencia(lat.p95)}</span></div>
      <div class="numero ${llm.taxa_cache > 0 ? 'ok' : ''}"><b>${pct(llm.taxa_cache)}</b><span>respondidas pelo cache</span></div>
      <div class="numero ${llm.taxa_reserva > 0 ? 'warn' : ''}" data-tip="Chamadas respondidas por um modelo diferente do pedido"><b>${pct(llm.taxa_reserva)}</b><span>em modelo reserva</span></div>
      <div class="numero ${llm.taxa_erro > 0 ? 'bad' : ''}"><b>${pct(llm.taxa_erro)}</b><span>com erro</span></div>
    </div>

    ${porAgente.length ? html`
      <div class="colunas-2">
        <div>
          <div class="secao-head"><h2>Custo por agente</h2><span class="sub">US$ estimados</span></div>
          ${barras(custoPorAgente)}
        </div>
        <div>
          <div class="secao-head"><h2>Latência média por agente</h2></div>
          ${barras(latenciaPorAgente)}
        </div>
      </div>` : ''}

    ${porModelo.length ? html`
      <div class="secao-head" style="margin-top:40px"><h2>Por modelo</h2><span class="sub">passe o mouse no nome para ver o preço usado na estimativa</span></div>
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Modelo</th><th class="num">Chamadas</th><th class="num" data-tip="entrada / saída / raciocínio">Tokens</th><th class="num">Custo</th><th class="num">Latência média</th></tr></thead>
        <tbody>${porModelo.map((g) => html`<tr>
          <td><span class="mono" data-tip="${dicaPreco(g.modelo_usado)}">${g.modelo_usado || '—'}</span>${g.reservas ? html` <span class="tag warn" data-tip="${numero(g.reservas)} chamada(s) caíram neste modelo como reserva">reserva</span>` : ''}${g.erros ? html` <span class="tag bad">${numero(g.erros)} erro(s)</span>` : ''}</td>
          <td class="num">${numero(g.chamadas)}${g.cache_hits ? html` <span class="muted small">(${numero(g.cache_hits)} do cache)</span>` : ''}</td>
          <td class="num">${numero(g.tokens_entrada)} / ${numero(g.tokens_saida)} / ${numero(g.tokens_raciocinio)}</td>
          <td class="num">${dolar(g.custo_usd)}</td>
          <td class="num">${latencia(g.latencia_media_ms)}</td>
        </tr>`)}</tbody>
      </table></div>` : ''}

    ${llm.nota ? html`<p class="muted small" style="margin-top:16px">${llm.nota}</p>` : ''}`;
}

export { render_ as render };
