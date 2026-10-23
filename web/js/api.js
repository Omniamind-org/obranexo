// Cliente da API do ObraNexo (mesma origem).

async function req(method, url, body) {
  const init = { method, headers: {} };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const r = await fetch(url, init);
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
  status: () => req('GET', '/api/status'),

  catalogo: () => req('GET', '/api/catalogo'),
  enviarCatalogo: (arquivo) => {
    const fd = new FormData();
    fd.append('arquivo', arquivo);
    return req('POST', '/api/catalogo', fd);
  },
  restaurarCatalogo: () => req('DELETE', '/api/catalogo'),

  casos: () => req('GET', '/api/casos'),
  caso: (nome) => req('GET', `/api/casos/${encodeURIComponent(nome)}`),
  buscarPncp: (params) => req('GET', `/api/pncp/buscar?${q(params)}`),
  coletarPncp: (pedido) => req('POST', '/api/pncp/coletar', pedido),

  iniciarAnalise: (caso) => req('POST', '/api/analises', { caso }),
  job: (id) => req('GET', `/api/jobs/${id}`),
  analises: () => req('GET', '/api/analises'),
  analise: (id) => req('GET', `/api/analises/${encodeURIComponent(id)}`),
  dossieMd: (id) => req('GET', `/api/analises/${encodeURIComponent(id)}/dossie.md`),
  revisar: (id, status, comentario) => req('PATCH', `/api/analises/${encodeURIComponent(id)}/revisao`, { status, comentario }),
  evidencia: (id, evId) => req('GET', `/api/analises/${encodeURIComponent(id)}/evidencias/${encodeURIComponent(evId)}`),
  arquivoUrl: (id, docId, pagina) => `/api/analises/${encodeURIComponent(id)}/documentos/${encodeURIComponent(docId)}/arquivo${pagina ? `#page=${pagina}` : ''}`,
  dossieDownloadUrl: (id) => `/api/analises/${encodeURIComponent(id)}/dossie.md?download=true`,

  metricas: () => req('GET', '/api/metricas'),
  fluxo: () => req('GET', '/api/conteudo/fluxo'),
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
