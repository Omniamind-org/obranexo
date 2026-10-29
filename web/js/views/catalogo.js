import { api } from '../api.js';
import { barras } from '../charts.js';
import { moeda, valorTecnico } from '../format.js';
import { atualizarStatus } from '../status.js';
import { abrirModal, aviso, html, icon, render, toast, vazio } from '../ui.js';

const COLUNAS = [
  ['potencia_w', 'Potência', 'W'],
  ['tensao_v', 'Tensão', 'V'],
  ['fluxo_lm', 'Fluxo', 'lm'],
  ['cct_k', 'Cor', 'K'],
  ['ip', 'IP', ''],
  ['garantia_anos', 'Garantia', 'anos'],
];

const ROTULO_CATEGORIA = {
  luminaria_publica_led: 'Luminária pública LED',
  luminaria_interna: 'Luminária interna',
  refletor_led: 'Refletor LED',
  lampada: 'Lâmpada',
  rele_fotoeletrico: 'Relé fotoelétrico',
  braco_luminaria: 'Braço para luminária',
  cabo: 'Cabo',
  disjuntor: 'Disjuntor',
  eletroduto: 'Eletroduto',
  quadro: 'Quadro',
  dispositivos: 'Tomadas e interruptores',
};
export const rotuloCategoria = (c) => ROTULO_CATEGORIA[c] || c || '—';

export async function render_(el) {
  const dados = await api.catalogo();
  const e = dados.empresa;
  const estado = { categoria: null, busca: '' };
  const porCategoria = {};
  dados.produtos.forEach((p) => { porCategoria[p.categoria] = (porCategoria[p.categoria] || 0) + 1; });

  const filtrar = () => dados.produtos.filter((p) => (!estado.categoria || p.categoria === estado.categoria)
    && (!estado.busca || `${p.sku} ${p.nome} ${p.descricao}`.toLowerCase().includes(estado.busca)));

  const desenharCategorias = () => {
    const linhas = Object.entries(porCategoria).sort((a, b) => b[1] - a[1]).map(([c, n]) => ({
      rot: rotuloCategoria(c), valor: n, attrs: `data-cat="${c}"`, ativo: estado.categoria === c,
      fraca: estado.categoria && estado.categoria !== c, tip: `${n} produto(s) · clique para filtrar`,
    }));
    render(el.querySelector('#categorias'), barras(linhas));
  };

  const desenharTabela = () => {
    const lista = filtrar();
    render(el.querySelector('#tabela'), lista.length ? html`
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Produto</th><th>Categoria</th>${COLUNAS.map(([, r]) => html`<th class="num">${r}</th>`)}<th class="num">Preço ref.</th></tr></thead>
        <tbody>${lista.map((p) => html`
          <tr class="clicavel" data-id="${p.id}">
            <td style="min-width:260px"><div style="font-weight:600">${p.nome}</div><div class="mono small muted">${p.sku}</div></td>
            <td class="nowrap ink-2">${rotuloCategoria(p.categoria)}</td>
            ${COLUNAS.map(([k, , u]) => html`<td class="num">${p.atributos[k] ? valorTecnico(p.atributos[k].valor, u) : html`<span class="muted">—</span>`}</td>`)}
            <td class="num">${moeda(p.preco_ref)}</td>
          </tr>`)}</tbody>
      </table></div>` : vazio('Nenhum produto encontrado', 'Ajuste a busca ou o filtro.'));
    el.querySelectorAll('tr[data-id]').forEach((tr) => tr.addEventListener('click', () => detalhe(dados.produtos.find((p) => p.id === tr.dataset.id), () => render_(el))));
    el.querySelector('#contagem').textContent = estado.categoria || estado.busca ? `${lista.length} de ${dados.produtos.length}` : '';
  };

  render(el, html`
    <div class="page-head">
      <div>
        <h1>${e.nome}</h1>
        <p class="sub">${dados.produtos.length} produtos em ${dados.categorias.length} categorias${e.ufs_atendidas.length ? ` · atende ${e.ufs_atendidas.join(', ')}` : ''}${e.raio_km ? ` · raio de ${e.raio_km} km` : ''}</p>
      </div>
      <div class="actions">
        <button class="btn btn-ghost" id="restaurar" data-tip="Volta ao catálogo de demonstração">${icon('refresh')} Restaurar demo</button>
        <label class="btn" data-tip="CSV ou XLSX: uma linha por produto com sku, nome, categoria e atributos (potencia_w, tensao_v, ip…). JSON no formato do demo.">${icon('upload')} Enviar planilha
          <input type="file" id="arquivo" accept=".json,.csv,.xlsx" hidden>
        </label>
        <button class="btn btn-primary" id="importar-ficha">${icon('bolt')} Importar ficha técnica</button>
      </div>
    </div>

    <section>
      <div class="secao-head"><h2>Por categoria</h2><button class="btn btn-ghost btn-sm" id="limpar" hidden>Mostrar todas</button></div>
      <div id="categorias" style="max-width:720px"></div>
    </section>
    <section class="secao">
      <div class="secao-head"><h2>Produtos</h2>
        <div class="actions"><span class="muted small" id="contagem"></span>
          <input class="input" id="busca" type="search" placeholder="Buscar por nome ou SKU" style="width:240px"></div>
      </div>
      <div id="tabela"></div>
    </section>
    </div>`);

  const redesenhar = () => {
    desenharCategorias();
    desenharTabela();
    el.querySelector('#limpar').hidden = !estado.categoria;
  };
  redesenhar();

  el.querySelector('#categorias').addEventListener('click', (ev) => {
    const alvo = ev.target.closest('[data-cat]');
    if (!alvo) return;
    estado.categoria = estado.categoria === alvo.dataset.cat ? null : alvo.dataset.cat;
    redesenhar();
  });
  el.querySelector('#limpar').addEventListener('click', () => { estado.categoria = null; redesenhar(); });
  el.querySelector('#busca').addEventListener('input', (ev) => { estado.busca = ev.target.value.trim().toLowerCase(); desenharTabela(); });
  el.querySelector('#arquivo').addEventListener('change', async (ev) => {
    const f = ev.target.files[0];
    if (!f) return;
    try {
      const r = await api.enviarCatalogo(f);
      toast(`Catálogo carregado: ${r.produtos} produtos de ${r.empresa}`);
      atualizarStatus();
      render_(el);
      if (r.avisos?.length) {
        abrirModal({
          titulo: 'Revise as categorias',
          subtitulo: 'Só produtos com categoria reconhecida são comparados com os itens das licitações.',
          corpo: html`<ul class="stack small">${r.avisos.map((a) => html`<li>${a}</li>`)}</ul>`,
        });
      }
    } catch (err) { toast(err.message, 'erro'); }
  });
  el.querySelector('#importar-ficha').addEventListener('click', () => importarFicha(() => render_(el)));
  el.querySelector('#restaurar').addEventListener('click', async () => {
    await api.restaurarCatalogo();
    toast('Catálogo de demonstração restaurado');
    atualizarStatus();
    render_(el);
  });
}

function importarFicha(aoConcluir) {
  const m = abrirModal({
    titulo: 'Importar ficha técnica',
    subtitulo: 'A IA lê a ficha do fabricante e sugere os produtos. Você revisa antes de adicionar.',
    corpo: html`
      <form id="form-ficha" class="stack">
        <label class="field">Link da página ou do PDF<input class="input" type="url" name="url" placeholder="https://fabricante.com.br/produto/…"></label>
        <label class="field">ou um arquivo (PDF, DOCX, XLSX, TXT, ZIP)<input class="input" type="file" name="arquivo" accept=".pdf,.docx,.xlsx,.txt,.csv,.zip" style="padding-top:8px"></label>
        <label class="field">ou cole o texto<textarea name="texto" rows="5" placeholder="Ex.: Luminária pública LED 100 W, 16.500 lm, 5000 K, IP66, 100–277 V…"></textarea></label>
        <div class="actions"><button class="btn btn-primary" type="submit">${icon('bolt')} Ler ficha</button></div>
      </form>
      <div id="previa"></div>`,
  });
  const form = m.el.querySelector('#form-ficha');
  const previa = m.el.querySelector('#previa');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    const arquivo = f.get('arquivo');
    const texto = (f.get('texto') || '').trim();
    const url = (f.get('url') || '').trim();
    if ((!arquivo || !arquivo.size) && !texto && !url) { toast('Informe um link, um arquivo ou o texto da ficha', 'erro'); return; }
    const botao = form.querySelector('button');
    botao.disabled = true;
    botao.innerHTML = '<span class="spinner"></span> Lendo a ficha…';
    try {
      const r = await api.importarFicha(arquivo && arquivo.size ? arquivo : null, texto, url);
      render(previa, html`
        <hr>
        <div class="secao-head"><h2>${r.produtos.length} produto(s) encontrado(s)</h2><span class="sub">${r.origem}</span></div>
        ${r.avisos.length ? html`<div style="margin-bottom:14px">${aviso(html`<strong>Ignorado na validação:</strong> ${r.avisos.slice(0, 6).join(' · ')}`, 'warn', 'alert')}</div>` : ''}
        <div class="linhas">${r.produtos.map((p, i) => html`
          <label class="linha" style="grid-template-columns:24px minmax(0,1fr);align-items:start;cursor:pointer">
            <input type="checkbox" data-i="${i}" checked style="margin-top:4px">
            <div style="min-width:0">
              <div><strong>${p.nome}</strong> <span class="mono small muted">${p.sku}</span> · <span class="ink-2">${rotuloCategoria(p.categoria)}</span></div>
              <div class="small ink-2" style="margin-top:4px">${Object.entries(p.atributos).map(([k, a]) => `${k.replace(/_/g, ' ')}: ${valorTecnico(a.valor, a.unidade)}`).join(' · ')}</div>
              ${p.certificacoes.length ? html`<div class="small muted" style="margin-top:2px">${p.certificacoes.join(' · ')}</div>` : ''}
            </div>
          </label>`)}</div>
        ${r.produtos.length ? html`<div class="actions" style="justify-content:flex-end;margin-top:16px"><button class="btn btn-primary" id="confirmar">${icon('check')} Adicionar ao catálogo</button></div>` : ''}`);
      previa.querySelector('#confirmar')?.addEventListener('click', async () => {
        const escolhidos = [...previa.querySelectorAll('input[data-i]:checked')].map((c) => r.produtos[Number(c.dataset.i)]);
        if (!escolhidos.length) { toast('Nenhum produto selecionado', 'erro'); return; }
        try {
          const res = await api.adicionarProdutos(escolhidos);
          toast(`${res.adicionados} produto(s) adicionado(s)`);
          m.fechar();
          atualizarStatus();
          aoConcluir();
        } catch (err) { toast(err.message, 'erro'); }
      });
    } catch (err) {
      toast(err.message, 'erro', 8000);
    } finally {
      botao.disabled = false;
      botao.innerHTML = `${icon('bolt').s} Ler ficha`;
    }
  });
}

function detalhe(p, aoMudar) {
  const m = abrirModal({
    titulo: p.nome,
    subtitulo: `${p.sku} · ${rotuloCategoria(p.categoria)}`,
    corpo: html`
      ${p.descricao ? html`<p class="ink-2" style="margin-bottom:22px">${p.descricao}</p>` : ''}
      <div class="colunas-2">
        <div>
          <div class="secao-head"><h2>Características</h2></div>
          <dl class="dl">${Object.entries(p.atributos).map(([k, a]) => html`<dt>${k.replace(/_/g, ' ')}</dt><dd>${valorTecnico(a.valor, a.unidade)}</dd>`)}</dl>
        </div>
        <div>
          <div class="secao-head"><h2>Comercial</h2></div>
          <dl class="dl">
            <dt>Preço de referência</dt><dd>${moeda(p.preco_ref)}</dd>
            <dt>Prazo de entrega</dt><dd>${p.prazo_entrega_dias ? `${p.prazo_entrega_dias} dias` : '—'}</dd>
            <dt>Estoque</dt><dd>${p.estoque ?? '—'}</dd>
            <dt>Normas</dt><dd>${p.normas.length ? p.normas.join(' · ') : '—'}</dd>
            <dt>Certificações</dt><dd>${p.certificacoes.length ? p.certificacoes.join(' · ') : '—'}</dd>
          </dl>
        </div>
      </div>`,
    rodape: html`<button class="btn btn-ghost" id="remover" style="color:var(--bad-ink)">${icon('x')} Remover do catálogo</button>`,
  });
  m.el.querySelector('#remover').addEventListener('click', async () => {
    try {
      await api.removerProduto(p.sku);
      toast(`${p.sku} removido`);
      m.fechar();
      aoMudar();
    } catch (err) { toast(err.message, 'erro'); }
  });
}

export { render_ as render };
