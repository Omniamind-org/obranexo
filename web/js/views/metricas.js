import { api } from '../api.js';
import { barras } from '../charts.js';
import { numero, pct } from '../format.js';
import { aviso, html, render } from '../ui.js';

const paraNumero = (v) => (typeof v === 'number' ? (v <= 1 ? v * 100 : v) : parseFloat(String(v).replace(',', '.')) || 0);

export async function render_(el) {
  const m = await api.metricas();
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
    </section>`);
}

export { render_ as render };
