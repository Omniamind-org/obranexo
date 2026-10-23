import { api } from '../api.js';
import { data, local, moeda } from '../format.js';
import { badgePrazo, html, icon, render, toast, vazio, carregando, erroBox } from '../ui.js';

const prazo = (c) => (!c.data_encerramento_proposta ? 'DESCONHECIDA' : new Date(c.data_encerramento_proposta) > new Date() ? 'ABERTA' : 'ENCERRADA');

function cartao(c, lado) {
  return html`
    <div class="card demanda">
      <div class="demanda-main">
        <div class="demanda-org">${c.orgao_nome}</div>
        <div class="demanda-obj clamp-2">${c.objeto}</div>
        <div class="meta">
          <span>${icon('pin')}${local(c)}</span>
          <span>${icon('doc')}${c.modalidade || '—'}${c.numero_compra ? ` nº ${c.numero_compra}/${c.ano}` : ''}</span>
          <span>${icon('money')}${moeda(c.valor_estimado)}</span>
          <span>${icon('calendar')}encerra ${data(c.data_encerramento_proposta, true)}</span>
          ${badgePrazo(prazo(c))}
          ${c.srp ? html`<span class="badge b-info plain">Registro de preços</span>` : ''}
        </div>
      </div>
      <div class="demanda-side">${lado}</div>
    </div>`;
}

export async function render_(el) {
  render(el, html`
    <div class="page-head">
      <div>
        <div class="eyebrow">Demandas públicas</div>
        <h1>Escolha uma contratação para analisar</h1>
        <p>Use um caso congelado (reproduzível, funciona offline) ou busque no PNCP contratações publicadas agora.</p>
      </div>
    </div>
    <div class="tabs" role="tablist">
      <button class="tab ativo" data-aba="casos">Casos congelados</button>
      <button class="tab" data-aba="pncp">Buscar no PNCP</button>
    </div>
    <div id="aba"></div>`);

  const abas = { casos: () => abaCasos(el.querySelector('#aba')), pncp: () => abaPncp(el.querySelector('#aba')) };
  el.querySelector('.tabs').addEventListener('click', (e) => {
    const b = e.target.closest('.tab');
    if (!b) return;
    el.querySelectorAll('.tab').forEach((t) => t.classList.toggle('ativo', t === b));
    abas[b.dataset.aba]();
  });
  await abas.casos();
}

async function abaCasos(alvo) {
  render(alvo, carregando());
  const casos = await api.casos();
  if (!casos.length) {
    render(alvo, vazio('Nenhum caso congelado', 'Busque no PNCP e baixe uma contratação para começar.'));
    return;
  }
  render(alvo, html`<div class="stack">${casos.map((c) => cartao(c.contratacao, html`
    <a class="btn btn-primary" href="#/casos/${c.nome}">${icon('play')} Abrir e analisar</a>
    <div class="muted small" style="text-align:center">${c.n_itens} itens · ${c.n_documentos_baixados}/${c.n_documentos} anexos${c.tem_gabarito ? ' · com gabarito' : ''}</div>
    ${c.analises.length ? html`<a class="btn btn-ghost btn-sm" href="#/analises/${c.analises[0].id}">Última análise ${icon('arrow')}</a>` : ''}`))}</div>`);
}

function abaPncp(alvo) {
  render(alvo, html`
    <div class="card card-pad">
      <form class="form-row" id="form-busca">
        <label class="field">UF<input class="input" name="uf" value="GO" maxlength="2" style="width:70px;text-transform:uppercase"></label>
        <label class="field" style="flex:1;min-width:240px">Palavras no objeto (separadas por vírgula)
          <input class="input" name="palavras" value="lumin,led,refletor,ilumina,material elétrico,material eletrico"></label>
        <label class="field">Publicadas nos últimos<select name="dias"><option value="15">15 dias</option><option value="30" selected>30 dias</option><option value="60">60 dias</option><option value="90">90 dias</option></select></label>
        <label class="check"><input type="checkbox" name="abertas" checked> Só propostas em aberto</label>
        <button class="btn btn-primary" type="submit">${icon('search')} Buscar</button>
      </form>
    </div>
    <div id="resultados" style="margin-top:16px"></div>`);

  const form = alvo.querySelector('#form-busca');
  const res = alvo.querySelector('#resultados');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    render(res, carregando('Consultando o PNCP… (pode levar alguns segundos)'));
    try {
      const r = await api.buscarPncp({ uf: f.get('uf').toUpperCase(), palavras: f.get('palavras'), dias: f.get('dias'), abertas: f.get('abertas') === 'on', max_paginas: 6 });
      if (!r.resultados.length) {
        render(res, vazio('Nada encontrado', `Consultadas ${r.paginas_consultadas} de ${r.total_paginas} páginas. Tente outras palavras ou um período maior.`));
        return;
      }
      render(res, html`
        <div class="muted small" style="margin-bottom:10px">${r.resultados.length} contratação(ões) · ${r.paginas_consultadas} de ${r.total_paginas} página(s) consultadas</div>
        <div class="stack">${r.resultados.map((c, i) => cartao(c, c.caso
          ? html`<a class="btn btn-primary" href="#/casos/${c.caso}">${icon('play')} Abrir caso</a><div class="muted small" style="text-align:center">já congelado</div>`
          : html`<button class="btn btn-primary" data-i="${i}">${icon('download')} Baixar e analisar</button>
                 <a class="btn btn-ghost btn-sm" href="${c.link_oficial}" target="_blank" rel="noopener">Ver no PNCP ${icon('external')}</a>`))}</div>`);
      res.querySelectorAll('button[data-i]').forEach((b) => b.addEventListener('click', async () => {
        const c = r.resultados[Number(b.dataset.i)];
        b.disabled = true;
        b.innerHTML = '<span class="spinner"></span> Baixando anexos…';
        try {
          const col = await api.coletarPncp({ cnpj: c.orgao_cnpj, ano: c.ano, sequencial: c.sequencial });
          toast(`Caso congelado: ${col.itens} itens, ${col.baixados}/${col.documentos} anexos baixados`);
          location.hash = `#/casos/${col.caso}`;
        } catch (err) {
          toast(err.message, 'erro');
          b.disabled = false;
          b.innerHTML = `${icon('download').s} Tentar de novo`;
        }
      }));
    } catch (err) {
      render(res, erroBox(err.message));
    }
  });
}

export { render_ as render };
