// Detalhe de uma licitação salva + execução da análise com acompanhamento ao vivo (SSE).

import { acompanharJob, api } from '../api.js';
import { prazo } from '../charts.js';
import { data, hora, local, moeda, moedaCompacta, numero, nomeProprio } from '../format.js';
import { html, icon, raw, render, toast } from '../ui.js';

export const ETAPAS = [
  ['carregar_contexto', 'Contexto'],
  ['coletar_documentos', 'Documentos'],
  ['extrair_itens', 'Requisitos'],
  ['filtrar_relevantes', 'Catálogo'],
  ['especificador', 'Termo de referência'],
  ['casar_com_catalogo', 'Comparação'],
  ['investigador', 'Investigação'],
  ['varrer_insumos', 'Insumos'],
  ['verificador', 'Verificação'],
  ['qualificar', 'Qualificação'],
  ['planejador', 'Plano'],
  ['gerar_dossie', 'Dossiê'],
];

export async function render_(el, nome) {
  const caso = await api.caso(nome);
  const c = caso.contratacao;
  const valorItem = (i) => (i.quantidade || 0) * (i.valor_unit_estimado || 0);
  const maxValor = Math.max(1, ...caso.itens.map(valorItem));
  const ultima = caso.analises.find((a) => a.status === 'concluida');

  render(el, html`
    <a class="voltar" href="#/demandas">${icon('back')} Licitações</a>
    <div class="page-head">
      <div style="min-width:0;flex:1">
        <div class="sobretitulo">${c.modalidade || 'Contratação'}${c.numero_compra ? ` nº ${c.numero_compra}/${c.ano}` : ''} · ${local(c)}</div>
        <h1>${nomeProprio(c.orgao_nome)}</h1>
        <p class="sub clamp-3">${c.objeto}</p>
        <div class="fatos" style="margin-top:14px">
          <span data-tip="Valor estimado">${icon('money')}${moeda(c.valor_estimado)}</span>
          <span>${icon('calendar')}${prazo(c.data_encerramento_proposta)}</span>
          <span>${icon('layers')}${caso.itens.length} itens</span>
          <span data-tip="${caso.documentos.filter((d) => d.baixado).length} com arquivo baixado">${icon('doc')}${caso.documentos.length} anexos</span>
        </div>
        ${ultima ? html`<p class="small ink-2" style="margin-top:12px">Já analisada em ${data(ultima.iniciada_em, true)} — <a href="#/analises/${ultima.id}">ver resultado</a></p>` : ''}
      </div>
      <div class="actions">
        <a class="btn" href="${c.link_oficial}" target="_blank" rel="noopener">${icon('external')} PNCP</a>
        <button class="btn btn-primary btn-lg" id="executar">${icon('play')} ${ultima ? 'Analisar de novo' : 'Analisar'}</button>
      </div>
    </div>

    <div id="execucao"></div>

    <div class="colunas secao" style="margin-top:40px">
      <div>
        <div class="secao-head"><h2>Itens</h2><span class="sub">barra = valor total estimado do item</span></div>
        <div class="table-wrap"><table class="table">
          <thead><tr><th>#</th><th>Descrição</th><th class="num">Qtd.</th><th style="width:170px">Valor total</th></tr></thead>
          <tbody>${caso.itens.map((i, k) => html`
            <tr ${k >= 15 ? raw('hidden data-extra') : ''}><td class="muted">${i.numero_item}</td>
              <td><div class="clamp-2" data-tip="${i.descricao}">${i.descricao}</div></td>
              <td class="num">${numero(i.quantidade)} <span class="muted small">${i.unidade || ''}</span></td>
              <td data-tip="${moeda(i.valor_unit_estimado)} por unidade"><div class="barras" style="grid-template-columns:1fr"><div class="trilho">
                <span class="barra" style="width:${Math.max(1, (valorItem(i) / maxValor) * 100)}%"></span><span class="val">${moedaCompacta(valorItem(i))}</span></div></div></td></tr>`)}</tbody>
        </table></div>
        ${caso.itens.length > 15 ? html`<button class="btn btn-ghost" id="todos-itens" style="margin-top:10px">Mostrar todos os ${caso.itens.length} itens</button>` : ''}
      </div>
      <div>
        <div class="secao-head"><h2>Anexos</h2></div>
        <ul class="riscos">${caso.documentos.map((d) => html`<li style="color:${d.baixado ? 'var(--ink)' : 'var(--muted)'}">${icon(d.baixado ? 'doc' : 'x')}
          <span style="min-width:0"><span class="truncate" style="display:block" data-tip="${d.nome}">${d.nome}</span><span class="muted small">${d.tipo || ''}${d.baixado ? '' : ' · não baixado'}</span></span></li>`)}</ul>
      </div>
    </div>`);

  el.querySelector('#todos-itens')?.addEventListener('click', (e) => {
    el.querySelectorAll('tr[data-extra]').forEach((tr) => { tr.hidden = false; });
    e.currentTarget.remove();
  });

  let parar = null;
  el.querySelector('#executar').addEventListener('click', async (e) => {
    const botao = e.currentTarget;
    botao.disabled = true;
    botao.innerHTML = '<span class="spinner"></span> Analisando…';
    const alvo = el.querySelector('#execucao');
    render(alvo, html`
      <section style="padding:8px 0 4px">
        <div class="progresso" id="progresso">${ETAPAS.map(([id, n]) => html`<div class="passo" data-etapa="${id}"><i></i><span>${n}</span></div>`)}</div>
        <div class="agora"><span class="spinner" id="girando"></span><span id="agora">Iniciando a análise…</span></div>
        <details class="mais" style="margin-top:14px"><summary>Ver detalhes</summary><ul class="feed" id="feed"></ul></details>
      </section>`);
    alvo.scrollIntoView({ behavior: 'smooth', block: 'center' });

    const feed = alvo.querySelector('#feed');
    const agora = alvo.querySelector('#agora');
    let etapaAtual = null;
    // Etapas podem se repetir (o motor de regras roda de novo após o Investigador): nunca desmarca o que já terminou.
    const marcar = (no) => {
      const passo = alvo.querySelector(`.passo[data-etapa="${no}"]`);
      if (!passo) return;
      alvo.querySelectorAll('.passo.ativo').forEach((s) => { s.classList.remove('ativo'); s.classList.add('feito'); });
      passo.classList.remove('feito');
      passo.classList.add('ativo');
      etapaAtual = no;
    };

    try {
      const job = await api.iniciarAnalise(nome);
      parar = acompanharJob(job.id, {
        onEvento: (ev) => {
          if (ev.no !== etapaAtual) marcar(ev.no);
          agora.textContent = ev.mensagem;
          const li = document.createElement('li');
          li.innerHTML = html`<span class="ts">${hora(ev.ts)}</span><span class="no">${ev.no}</span><span>${ev.mensagem}</span>`.s;
          feed.appendChild(li);
          feed.scrollTop = feed.scrollHeight;
        },
        onFim: (fim) => {
          alvo.querySelectorAll('.passo').forEach((s) => {
            if (s.classList.contains('ativo')) { s.classList.remove('ativo'); s.classList.add('feito'); }
            if (!s.classList.contains('feito')) s.classList.add('pulado');
          });
          alvo.querySelector('#girando')?.remove();
          if (fim.status === 'concluida') {
            agora.textContent = 'Análise concluída — abrindo o resultado…';
            setTimeout(() => { location.hash = `#/analises/${fim.analise_id}`; }, 700);
          } else {
            agora.textContent = fim.erro || 'A análise terminou com erro.';
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
      botao.innerHTML = `${icon('play').s} Analisar`;
    }
  });

  return () => parar?.();
}

export { render_ as render };
