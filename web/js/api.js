// Cliente da API do ObraNexo (mesma origem).

async function req(method, url, body) {
  const init = { method, headers: {} };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const r = await fetch(url, init);
  // Sessão expirada ou encerrada no meio do uso: a casca volta para a tela de entrada (sessao.js)
  if (r.status === 401 && !url.startsWith('/api/auth/')) window.dispatchEvent(new CustomEvent('sessao-encerrada'));
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try {
      const j = await r.json();
      if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch { /* corpo não-JSON */ }
    throw new Error(msg);
  }
  const tipo = r.headers.get('content-type') || '';
  return tipo.includes('application/json') ? r.json() : r.text();
}

const q = (params) => new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null)).toString();

export const api = {
  eu: () => req('GET', '/api/auth/eu'),
  login: (email, senha) => req('POST', '/api/auth/login', { email, senha }),
  cadastro: (dados) => req('POST', '/api/auth/cadastro', dados),
  logout: () => req('POST', '/api/auth/logout'),

  status: () => req('GET', '/api/status'),
  trocarProvedor: (provedor) => req('POST', '/api/config/llm', { provedor }),
  testarProvedor: () => req('POST', '/api/config/llm/testar'),

  catalogo: () => req('GET', '/api/catalogo'),
  enviarCatalogo: (arquivo) => {
    const fd = new FormData();
    fd.append('arquivo', arquivo);
    return req('POST', '/api/catalogo', fd);
  },
  restaurarCatalogo: () => req('DELETE', '/api/catalogo'),
  importarFicha: (arquivo, texto, url) => {
    const fd = new FormData();
    if (arquivo) fd.append('arquivo', arquivo);
    if (texto) fd.append('texto', texto);
    if (url) fd.append('url', url);
    return req('POST', '/api/catalogo/importar', fd);
  },
  adicionarProdutos: (produtos) => req('POST', '/api/catalogo/produtos', { produtos }),
  removerProduto: (sku) => req('DELETE', `/api/catalogo/produtos/${encodeURIComponent(sku)}`),

  iniciarProspeccao: (pedido) => req('POST', '/api/prospeccoes', pedido),
  prospeccoes: () => req('GET', '/api/prospeccoes'),
  prospeccao: (id) => req('GET', `/api/prospeccoes/${encodeURIComponent(id)}`),

  casos: () => req('GET', '/api/casos'),
  caso: (nome) => req('GET', `/api/casos/${encodeURIComponent(nome)}`),
  buscarPncp: (params) => req('GET', `/api/pncp/buscar?${q(params)}`),
  iniciarBuscaPncp: (pedido) => req('POST', '/api/pncp/buscas', pedido),
  coletarPncp: (pedido) => req('POST', '/api/pncp/coletar', pedido),

  iniciarAnalise: (caso) => req('POST', '/api/analises', { caso }),
  job: (id) => req('GET', `/api/jobs/${id}`),
  analises: () => req('GET', '/api/analises'),
  analise: (id) => req('GET', `/api/analises/${encodeURIComponent(id)}`),
  dossieMd: (id) => req('GET', `/api/analises/${encodeURIComponent(id)}/dossie.md`),
  revisar: (id, status, comentario) => req('PATCH', `/api/analises/${encodeURIComponent(id)}/revisao`, { status, comentario }),
  evidencia: (id, evId) => req('GET', `/api/analises/${encodeURIComponent(id)}/evidencias/${encodeURIComponent(evId)}`),
  chamadas: (id) => req('GET', `/api/analises/${encodeURIComponent(id)}/chamadas`),
  arquivoUrl: (id, docId, pagina) => `/api/analises/${encodeURIComponent(id)}/documentos/${encodeURIComponent(docId)}/arquivo${pagina ? `#page=${pagina}` : ''}`,
  dossieDownloadUrl: (id) => `/api/analises/${encodeURIComponent(id)}/dossie.md?download=true`,
  proposta: (id) => req('GET', `/api/analises/${encodeURIComponent(id)}/proposta`),
  propostaWordUrl: (id) => `/api/analises/${encodeURIComponent(id)}/proposta.docx`,
  propostaPlanilhaUrl: (id) => `/api/analises/${encodeURIComponent(id)}/proposta.xlsx`,
  propostaDocumentoUrl: (id) => `/api/analises/${encodeURIComponent(id)}/proposta.md?download=true`,

  criarConversa: () => req('POST', '/api/chat'),
  conversa: (id) => req('GET', `/api/chat/${encodeURIComponent(id)}`),
  enviarMensagem: (id, texto) => req('POST', `/api/chat/${encodeURIComponent(id)}/mensagens`, { texto }),

  metricas: () => req('GET', '/api/metricas'),
  metricasLlm: () => req('GET', '/api/metricas/llm'),
  fluxo: () => req('GET', '/api/conteudo/fluxo'),
  grafo: () => req('GET', '/api/conteudo/grafo'),
};

/**
 * Acompanha um job pela stream SSE; se a conexão cair, passa a consultar /api/jobs/{id}.
 * Retorna uma função que encerra o acompanhamento.
 */
export function acompanharJob(jobId, { onEvento, onFim, onErro }) {
  let ativo = true;
  let recebidos = 0;
  const es = new EventSource(`/api/jobs/${jobId}/eventos`);
  es.addEventListener('log', (e) => { recebidos += 1; onEvento(JSON.parse(e.data)); });
  es.addEventListener('fim', (e) => { ativo = false; es.close(); onFim(JSON.parse(e.data)); });
  es.onerror = async () => {
    es.close();
    if (!ativo) return;
    // Fallback por polling
    while (ativo) {
      try {
        const j = await api.job(jobId);
        j.log.slice(recebidos).forEach((ev) => onEvento(ev));
        recebidos = j.log.length;
        if (j.status !== 'executando') { ativo = false; onFim(j); return; }
      } catch (err) { ativo = false; onErro?.(err); return; }
      await new Promise((r) => setTimeout(r, 800));
    }
  };
  return () => { ativo = false; es.close(); };
}
