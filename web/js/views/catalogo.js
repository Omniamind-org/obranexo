import { api } from '../api.js';
import { atualizarStatus } from '../status.js';
import { moeda, valorTecnico } from '../format.js';
import { abrirModal, html, icon, render, toast, vazio } from '../ui.js';

const COLUNAS = [
  ['potencia_w', 'Potência', 'W'],
  ['tensao_v', 'Tensão', 'V'],
  ['cct_k', 'CCT', 'K'],
  ['fluxo_lm', 'Fluxo', 'lm'],
  ['eficiencia_lm_w', 'Eficiência', 'lm/W'],
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
  const estado = { categoria: null, busca: '' };

  const filtrar = () => dados.produtos.filter((p) => (!estado.categoria || p.categoria === estado.categoria)
    && (!estado.busca || `${p.sku} ${p.nome} ${p.descricao}`.toLowerCase().includes(estado.busca)));

  const desenharTabela = () => {
    const lista = filtrar();
    render(el.querySelector('#tabela'), lista.length ? html`
      <div class="table-wrap"><table class="table">
        <thead><tr><th>SKU</th><th>Produto</th><th>Categoria</th>${COLUNAS.map(([, r]) => html`<th class="num">${r}</th>`)}<th class="num">Preço ref.</th></tr></thead>
        <tbody>${lista.map((p) => html`
          <tr class="clicavel" data-id="${p.id}">
            <td class="mono nowrap">${p.sku}</td>
            <td style="min-width:220px"><strong>${p.nome}</strong></td>
            <td class="nowrap muted">${rotuloCategoria(p.categoria)}</td>
            ${COLUNAS.map(([k, , u]) => html`<td class="num">${p.atributos[k] ? valorTecnico(p.atributos[k].valor, u) : html`<span class="muted">—</span>`}</td>`)}
            <td class="num">${moeda(p.preco_ref)}</td>
          </tr>`)}</tbody>
      </table></div>` : vazio('Nenhum produto encontrado', 'Ajuste a busca ou o filtro de categoria.'));
    el.querySelectorAll('tr[data-id]').forEach((tr) => tr.addEventListener('click', () => detalhe(dados.produtos.find((p) => p.id === tr.dataset.id), () => render_(el))));
    el.querySelector('#contagem').textContent = `${lista.length} de ${dados.produtos.length} produtos`;
  };

  render(el, html`
    <div class="page-head">
      <div>
        <div class="eyebrow">Perfil comercial</div>
        <h1>${dados.empresa.nome}</h1>
        <p>${dados.empresa.observacoes}</p>
      </div>
      <div class="actions">
        <button class="btn btn-primary" id="importar-ficha">${icon('bolt')} Importar ficha técnica (IA)</button>
        <label class="btn">${icon('upload')} Enviar planilha
          <input type="file" id="arquivo" accept=".json,.csv,.xlsx" hidden>
        </label>
        <button class="btn btn-ghost" id="restaurar">${icon('refresh')} Restaurar demo</button>
      </div>
    </div>

    <div class="grid grid-4">
      <div class="card kpi"><div class="kpi-label">Produtos</div><div class="kpi-value">${dados.produtos.length}</div></div>
      <div class="card kpi"><div class="kpi-label">Categorias</div><div class="kpi-value">${dados.categorias.length}</div></div>
      <div class="card kpi"><div class="kpi-label">UFs atendidas</div><div class="kpi-value" style="font-size:20px;padding-top:5px">${dados.empresa.ufs_atendidas.join(' · ') || '—'}</div></div>
      <div class="card kpi"><div class="kpi-label">Raio logístico</div><div class="kpi-value">${dados.empresa.raio_km ? `${dados.empresa.raio_km} km` : '—'}</div></div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="card-head" style="flex-wrap:wrap">
        <div class="chips" id="chips">
          <button class="chip ativo" data-cat="">Todas</button>
          ${dados.categorias.map((c) => html`<button class="chip" data-cat="${c}">${rotuloCategoria(c)}</button>`)}
        </div>
        <div class="actions">
          <span class="muted small" id="contagem"></span>
          <input class="input" id="busca" type="search" placeholder="Buscar SKU ou nome…" style="width:220px">
        </div>
      </div>
      <div id="tabela"></div>
    </div>
    <p class="muted small" style="margin-top:12px">CSV/XLSX: uma linha por produto, colunas <code>sku, nome, categoria</code> e qualquer atributo canônico
      (<code>potencia_w</code>, <code>tensao_v</code>, <code>ip</code>, <code>cct_k</code>…). Normas e certificações separadas por “;”.</p>`);

  desenharTabela();

  el.querySelector('#chips').addEventListener('click', (e) => {
    const b = e.target.closest('.chip');
    if (!b) return;
    estado.categoria = b.dataset.cat || null;
    el.querySelectorAll('#chips .chip').forEach((c) => c.classList.toggle('ativo', c === b));
    desenharTabela();
  });
  el.querySelector('#busca').addEventListener('input', (e) => { estado.busca = e.target.value.trim().toLowerCase(); desenharTabela(); });
  el.querySelector('#arquivo').addEventListener('change', async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const r = await api.enviarCatalogo(f);
      toast(`Catálogo carregado: ${r.produtos} produtos de ${r.empresa}`);
      atualizarStatus();
      render_(el);
    } catch (err) { toast(err.message, 'erro'); }
  });
  el.querySelector('#importar-ficha').addEventListener('click', () => importarFicha(() => render_(el)));
  el.querySelector('#restaurar').addEventListener('click', async () => {
    await api.restaurarCatalogo();
    toast('Catálogo demonstrativo restaurado');
    atualizarStatus();
    render_(el);
  });
}

function importarFicha(aoConcluir) {
  const m = abrirModal({
    titulo: 'Importar ficha técnica com IA',
    subtitulo: 'O modelo lê a ficha do fabricante e propõe os produtos. Você revisa antes de entrar no catálogo.',
    corpo: html`
      <form id="form-ficha" class="stack">
        <label class="field">Link da página ou do PDF do fabricante<input class="input" type="url" name="url" placeholder="https://fabricante.com.br/produto/luminaria-publica-led…"></label>
        <label class="field">…ou um arquivo (PDF, DOCX, XLSX, TXT ou ZIP)<input class="input" type="file" name="arquivo" accept=".pdf,.docx,.xlsx,.txt,.csv,.zip" style="padding-top:6px"></label>
        <label class="field">…ou cole o texto da ficha<textarea name="texto" rows="6" placeholder="Ex.: Luminária pública LED 100 W, 16.500 lm, 165 lm/W, 5000 K, IP66, IK08, 100–277 V, INMETRO…"></textarea></label>
        <div class="actions"><button class="btn btn-primary" type="submit">${icon('bolt')} Extrair produtos</button></div>
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
        <div class="muted small" style="margin-bottom:10px">${r.produtos.length} produto(s) identificado(s) em <strong>${r.origem}</strong> (${r.caracteres} caracteres, ${r.llm.chamadas} chamada(s) ao LLM).</div>
        ${r.avisos.length ? html`<div class="alert alert-warn" style="margin-bottom:12px">${icon('alert')}<div class="alert-body"><strong>Descartado na validação:</strong><ul style="margin:4px 0 0;padding-left:18px">${r.avisos.slice(0, 12).map((a) => html`<li>${a}</li>`)}</ul></div></div>` : ''}
        ${r.produtos.map((p, i) => html`
          <label class="card card-pad" style="display:flex;gap:12px;margin-bottom:8px;cursor:pointer">
            <input type="checkbox" data-i="${i}" checked style="margin-top:4px">
            <div style="min-width:0">
              <div><strong>${p.nome}</strong> <span class="mono small muted">${p.sku}</span> · <span class="badge plain">${rotuloCategoria(p.categoria)}</span></div>
              <div class="chips" style="margin-top:6px">${Object.entries(p.atributos).map(([k, a]) => html`<span class="badge plain mono">${k}=${valorTecnico(a.valor, a.unidade)}</span>`)}</div>
              ${p.certificacoes.length ? html`<div class="small muted" style="margin-top:6px">Certificações: ${p.certificacoes.join(' · ')}</div>` : ''}
            </div>
          </label>`)}
        ${r.produtos.length ? html`<div class="actions" style="justify-content:flex-end"><button class="btn btn-primary" id="confirmar">${icon('check')} Adicionar selecionados ao catálogo</button></div>` : ''}`);
      previa.querySelector('#confirmar')?.addEventListener('click', async () => {
        const escolhidos = [...previa.querySelectorAll('input[data-i]:checked')].map((c) => r.produtos[Number(c.dataset.i)]);
        if (!escolhidos.length) { toast('Nenhum produto selecionado', 'erro'); return; }
        try {
          const res = await api.adicionarProdutos(escolhidos);
          toast(`${res.adicionados} produto(s) adicionado(s); catálogo com ${res.produtos}`);
          m.fechar();
          atualizarStatus();
          aoConcluir();
        } catch (err) { toast(err.message, 'erro'); }
      });
    } catch (err) {
      toast(err.message, 'erro', 8000);
    } finally {
      botao.disabled = false;
      botao.innerHTML = `${icon('bolt').s} Extrair produtos`;
    }
  });
}

function detalhe(p, aoMudar) {
  const atributos = Object.entries(p.atributos);
  const m = abrirModal({
    titulo: p.nome,
    subtitulo: `${p.sku} · ${rotuloCategoria(p.categoria)}`,
    corpo: html`
      ${p.descricao ? html`<p style="margin-top:0">${p.descricao}</p>` : ''}
      <div class="grid grid-2">
        <div>
          <div class="section-title" style="margin-top:0">Atributos técnicos</div>
          <dl class="dl">${atributos.map(([k, a]) => html`<dt class="mono">${k}</dt><dd>${valorTecnico(a.valor, a.unidade)}</dd>`)}</dl>
        </div>
        <div>
          <div class="section-title" style="margin-top:0">Comercial</div>
          <dl class="dl">
            <dt>Preço de referência</dt><dd>${moeda(p.preco_ref)}</dd>
            <dt>Prazo de entrega</dt><dd>${p.prazo_entrega_dias ? `${p.prazo_entrega_dias} dias` : '—'}</dd>
            <dt>Estoque</dt><dd>${p.estoque ?? '—'}</dd>
          </dl>
          <div class="section-title">Normas</div>
          <div class="chips">${p.normas.length ? p.normas.map((n) => html`<span class="badge plain">${n}</span>`) : html`<span class="muted">—</span>`}</div>
          <div class="section-title">Certificações e documentos</div>
          <div class="chips">${p.certificacoes.length ? p.certificacoes.map((n) => html`<span class="badge b-accent plain">${n}</span>`) : html`<span class="muted">—</span>`}</div>
        </div>
      </div>`,
    rodape: html`<button class="btn btn-ghost" id="remover" style="color:var(--bad)">${icon('x')} Remover do catálogo</button>`,
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
