import { api } from '../api.js';
import { prazo } from '../charts.js';
import { local, moedaCompacta, nomeProprio } from '../format.js';
import { carregando, erroBox, html, icon, render, toast, vazio } from '../ui.js';

const ordemPrazo = (c) => {
  const t = new Date(c.data_encerramento_proposta || 0).getTime();
  return t > Date.now() ? t : Number.MAX_SAFE_INTEGER - t; // abertas primeiro, pela data mais próxima
};

export async function render_(el) {
  render(el, html`
    <div class="page-head">
      <div><h1>Licitações</h1><p class="sub">Escolha uma licitação para analisar contra o seu catálogo.</p></div>
      <div class="segmentos" id="abas">
        <button class="ativo" data-aba="casos">Salvas</button>
        <button data-aba="pncp">Buscar no PNCP</button>
      </div>
    </div>
    <div id="aba"></div>`);

  const abas = { casos: () => abaCasos(el.querySelector('#aba')), pncp: () => abaPncp(el.querySelector('#aba')) };
  el.querySelector('#abas').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    el.querySelectorAll('#abas button').forEach((t) => t.classList.toggle('ativo', t === b));
    abas[b.dataset.aba]();
  });
  await abas.casos();
}

async function abaCasos(alvo) {
  render(alvo, carregando());
  const casos = (await api.casos()).sort((a, b) => ordemPrazo(a.contratacao) - ordemPrazo(b.contratacao));
  if (!casos.length) {
    render(alvo, vazio('Nenhuma licitação salva', 'Busque no PNCP e baixe uma licitação para começar.'));
    return;
  }
  render(alvo, html`<div class="linhas">${casos.map((c) => {
    const ultima = c.analises[0];
    return html`
      <a class="linha" href="#/casos/${c.nome}" style="grid-template-columns:minmax(0,1fr) 110px 160px 120px">
        <div style="min-width:0">
          <div class="linha-titulo truncate">${nomeProprio(c.contratacao.orgao_nome)}</div>
          <div class="linha-sub truncate">${local(c.contratacao)} · ${c.contratacao.objeto}</div>
        </div>
        <div class="num" data-tip="Valor estimado">${moedaCompacta(c.contratacao.valor_estimado)}</div>
        <div class="num">${prazo(c.contratacao.data_encerramento_proposta)}</div>
        <div class="num small ${ultima ? 'ink-2' : 'muted'}">${ultima ? 'analisada' : `${c.n_itens} itens`}</div>
      </a>`;
  })}</div>`);
}

function abaPncp(alvo) {
  render(alvo, html`
    <form class="form-row" id="form-busca" style="margin-bottom:28px">
      <label class="field">UF<input class="input" name="uf" value="GO" maxlength="2" style="width:72px;text-transform:uppercase"></label>
      <label class="field" style="flex:1;min-width:240px">Palavras no objeto
        <input class="input" name="palavras" value="lumin,led,refletor,ilumina,material elétrico,material eletrico" data-tip="Separe por vírgula"></label>
      <label class="field">Publicadas há<select name="dias"><option value="15">15 dias</option><option value="30" selected>30 dias</option><option value="60">60 dias</option><option value="90">90 dias</option></select></label>
      <label class="check"><input type="checkbox" name="abertas" checked> Só com propostas abertas</label>
      <button class="btn btn-primary" type="submit">${icon('search')} Buscar</button>
    </form>
    <div id="resultados"></div>`);

  const form = alvo.querySelector('#form-busca');
  const res = alvo.querySelector('#resultados');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    render(res, carregando('Consultando o PNCP…'));
    try {
      const r = await api.buscarPncp({ uf: f.get('uf').toUpperCase(), palavras: f.get('palavras'), dias: f.get('dias'), abertas: f.get('abertas') === 'on', max_paginas: 6 });
      if (!r.resultados.length) {
        render(res, vazio('Nada encontrado', 'Tente outras palavras ou um período maior.'));
        return;
      }
      render(res, html`
        <p class="muted small" style="margin-bottom:10px">${r.resultados.length} licitação(ões) encontrada(s)</p>
        <div class="linhas">${r.resultados.map((c, i) => html`
          <div class="linha" style="grid-template-columns:minmax(0,1fr) 110px 160px 190px">
            <div style="min-width:0">
              <div class="linha-titulo truncate">${nomeProprio(c.orgao_nome)}</div>
              <div class="linha-sub clamp-2">${local(c)} · ${c.objeto}</div>
            </div>
            <div class="num">${moedaCompacta(c.valor_estimado)}</div>
            <div class="num">${prazo(c.data_encerramento_proposta)}</div>
            <div class="actions" style="justify-content:flex-end">
              ${c.caso
                ? html`<a class="btn btn-sm" href="#/casos/${c.caso}">Abrir</a>`
                : html`<a class="btn btn-ghost btn-sm" href="${c.link_oficial}" target="_blank" rel="noopener" data-tip="Ver no PNCP">${icon('external')}</a>
                       <button class="btn btn-primary btn-sm" data-i="${i}">${icon('download')} Salvar e analisar</button>`}
            </div>
          </div>`)}</div>`);
      res.querySelectorAll('button[data-i]').forEach((b) => b.addEventListener('click', async () => {
        const c = r.resultados[Number(b.dataset.i)];
        b.disabled = true;
        b.innerHTML = '<span class="spinner"></span> Baixando anexos…';
        try {
          const col = await api.coletarPncp({ cnpj: c.orgao_cnpj, ano: c.ano, sequencial: c.sequencial });
          toast(`Licitação salva: ${col.itens} itens, ${col.baixados}/${col.documentos} anexos`);
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
