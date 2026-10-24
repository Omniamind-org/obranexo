// Formatação pt-BR.

const moedaFmt = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 2 });
const moedaCurta = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', notation: 'compact', maximumFractionDigits: 1 });
const numFmt = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });

export const moeda = (v) => (v === null || v === undefined ? '—' : moedaFmt.format(v));
export const moedaCompacta = (v) => (v === null || v === undefined ? '—' : moedaCurta.format(v));
export const numero = (v) => (v === null || v === undefined || v === '' ? '—' : typeof v === 'number' ? numFmt.format(v) : String(v));
export const pct = (v, casas = 0) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(casas)}%`);

export function data(iso, comHora = false) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const opts = { day: '2-digit', month: '2-digit', year: 'numeric' };
  if (comHora) Object.assign(opts, { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleString('pt-BR', opts);
}

export function hora(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/** Valor de requisito/atributo: faixas [a, b], booleanos, números e textos. */
export function valorTecnico(v, unidade) {
  if (v === null || v === undefined || v === '') return '—';
  if (Array.isArray(v) && v.length === 2) return `${numero(v[0])} a ${numero(v[1])}${unidade ? ` ${unidade}` : ''}`;
  if (typeof v === 'boolean') return v ? 'sim' : 'não';
  if (typeof v === 'number') return `${numero(v)}${unidade ? ` ${unidade}` : ''}`;
  return String(v);
}

export const OPERADOR = { '=': '=', '>=': '≥', '<=': '≤', entre: 'entre', contem: 'contém', verdadeiro: 'exigido' };

const MINUSCULAS = new Set(['de', 'da', 'do', 'das', 'dos', 'e', 'em', 'a', 'o', 'para', 'no', 'na']);
const SIGLAS = /^(?:[A-Z]{2}|S\/A|SA|LTDA|ME|EPP|SAAE|DAE|SESI|SENAI|IFG|UFG|[IVX]+)$/;

/** Nomes de órgão vêm do PNCP em CAIXA ALTA: exibe com iniciais maiúsculas (siglas e UFs preservadas). */
export function nomeProprio(s) {
  if (!s || s !== s.toUpperCase()) return s || '—';
  return s.split(/\s+/).map((p, i) => {
    const min = p.toLocaleLowerCase('pt-BR');
    if (i > 0 && MINUSCULAS.has(min)) return min;
    if (SIGLAS.test(p.replace(/[.,]/g, ''))) return p;
    return min.charAt(0).toLocaleUpperCase('pt-BR') + min.slice(1);
  }).join(' ');
}

export function local(c) {
  return [c.municipio, c.uf].filter(Boolean).join('/') || '—';
}
