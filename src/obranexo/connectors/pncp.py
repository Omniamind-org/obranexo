"""Conector do Portal Nacional de Contratações Públicas (PNCP).

Endpoints verificados em 22/10/2026:
  - Busca por publicação ... GET /api/consulta/v1/contratacoes/publicacao
  - Propostas em aberto .... GET /api/consulta/v1/contratacoes/proposta
  - Detalhe da compra ...... GET /api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}
  - Itens da compra ........ GET /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens
  - Arquivos da compra ..... GET /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos

O detalhe migrou para a base "consulta" (a antiga responde 301); itens e arquivos
continuam na base "pncp". Todas as respostas JSON e os arquivos baixados são
cacheados em disco para reprodutibilidade e para não sobrecarregar o portal.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from obranexo.config import config
from obranexo.models import Contratacao, Documento, ItemDemanda

BASE_CONSULTA = "https://pncp.gov.br/api/consulta/v1"
BASE_PNCP = "https://pncp.gov.br/api/pncp/v1"
USER_AGENT = "ObraNexo/0.1 (AKCIT Camp 2026; contato: equipe ObraNexo)"
MODALIDADE_PREGAO_ELETRONICO = 6
MODALIDADES = {
    1: "Leilão - Eletrônico",
    2: "Diálogo Competitivo",
    3: "Concurso",
    4: "Concorrência - Eletrônica",
    5: "Concorrência - Presencial",
    6: "Pregão - Eletrônico",
    7: "Pregão - Presencial",
    8: "Dispensa de Licitação",
    9: "Inexigibilidade",
    12: "Credenciamento",
    13: "Leilão - Presencial",
}


class PNCPError(RuntimeError):
    pass


class _Transiente(PNCPError):
    pass


def _parse_dt(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return None


def _nome_arquivo_seguro(nome: str) -> str:
    nome = re.sub(r"[^\w.\-]+", "_", nome, flags=re.UNICODE).strip("_")
    return nome[:90] or "documento"


def contratacao_de_api(d: dict[str, Any]) -> Contratacao:
    orgao = d.get("orgaoEntidade") or {}
    unidade = d.get("unidadeOrgao") or {}
    return Contratacao(
        id=d["numeroControlePNCP"],
        orgao_cnpj=orgao.get("cnpj", ""),
        orgao_nome=orgao.get("razaoSocial", ""),
        unidade_nome=unidade.get("nomeUnidade"),
        uf=unidade.get("ufSigla"),
        municipio=unidade.get("municipioNome"),
        modalidade=d.get("modalidadeNome"),
        numero_compra=d.get("numeroCompra"),
        ano=int(d.get("anoCompra") or 0),
        sequencial=int(d.get("sequencialCompra") or 0),
        objeto=(d.get("objetoCompra") or "").strip(),
        valor_estimado=d.get("valorTotalEstimado"),
        valor_homologado=d.get("valorTotalHomologado"),
        srp=bool(d.get("srp")),
        data_publicacao=_parse_dt(d.get("dataPublicacaoPncp")),
        data_abertura_proposta=_parse_dt(d.get("dataAberturaProposta")),
        data_encerramento_proposta=_parse_dt(d.get("dataEncerramentoProposta")),
        situacao=d.get("situacaoCompraNome"),
        link_oficial=f"https://pncp.gov.br/app/editais/{orgao.get('cnpj')}/{d.get('anoCompra')}/{d.get('sequencialCompra')}",
        link_sistema_origem=d.get("linkSistemaOrigem"),
        bruto=d,
    )


def item_de_api(d: dict[str, Any], contratacao_id: str) -> ItemDemanda:
    numero = int(d.get("numeroItem") or 0)
    return ItemDemanda(
        id=f"{contratacao_id}#item-{numero}",
        contratacao_id=contratacao_id,
        numero_item=numero,
        descricao=(d.get("descricao") or "").strip(),
        quantidade=d.get("quantidade"),
        unidade=d.get("unidadeMedida"),
        valor_unit_estimado=d.get("valorUnitarioEstimado"),
        situacao=d.get("situacaoCompraItemNome"),
    )


class PNCPClient:
    """Cliente HTTP com cache em disco e retentativas com espera crescente."""

    def __init__(self, dir_cache: Path | None = None, pausa_s: float = 0.6, offline: bool | None = None):
        self.dir_cache = dir_cache or config.dir_cache
        self.dir_cache.mkdir(parents=True, exist_ok=True)
        self.pausa_s = pausa_s
        self.offline = config.offline if offline is None else offline
        self.aviso: str | None = None
        self._http = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=90, follow_redirects=True)

    # ---------------------------------------------------------------- HTTP

    def _cache_path(self, url: str, sufixo: str) -> Path:
        return self.dir_cache / f"{hashlib.sha1(url.encode()).hexdigest()}{sufixo}"

    @retry(
        retry=retry_if_exception_type(_Transiente),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=3, max=30),
        reraise=True,
    )
    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        if self.offline:
            raise PNCPError(f"modo offline: não consulto {url}")
        resp = self._http.get(url, params=params)
        if resp.status_code in (429, 500, 502, 503, 504):
            espera = resp.headers.get("Retry-After")
            if resp.status_code == 429 and espera and espera.isdigit():
                time.sleep(min(int(espera), 60))  # o portal diz quanto esperar: respeitamos
            raise _Transiente(f"HTTP {resp.status_code} em {resp.url}")
        if resp.status_code >= 400:
            raise PNCPError(f"HTTP {resp.status_code} em {resp.url}: {resp.text[:200]}")
        time.sleep(self.pausa_s)
        return resp

    def get_json(self, url: str, params: dict[str, Any] | None = None, usar_cache: bool = True, ttl_s: float | None = None) -> Any:
        """Cache em disco. `ttl_s` define a validade (None = para sempre). Se o PNCP falhar e houver uma cópia
        antiga, ela é usada e `self.aviso` explica a idade — melhor do que parar a prospecção."""
        chave = str(httpx.URL(url, params=params or {}))
        cache = self._cache_path(chave, ".json")
        idade = time.time() - cache.stat().st_mtime if cache.exists() else None
        if usar_cache and idade is not None and (ttl_s is None or idade <= ttl_s):
            return json.loads(cache.read_text(encoding="utf-8"))
        try:
            resp = self._get(url, params)
        except (PNCPError, httpx.HTTPError) as exc:
            if idade is not None:
                self.aviso = f"PNCP indisponível ({str(exc)[:80]}); usando a consulta de {idade / 60:.0f} min atrás"
                return json.loads(cache.read_text(encoding="utf-8"))
            raise PNCPError(str(exc)) from exc
        if resp.status_code == 204 or not resp.content:
            dados: Any = []
        else:
            dados = resp.json()
        cache.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        return dados

    # ------------------------------------------------------------- Buscas

    def buscar_publicacoes(
        self,
        data_inicial: str,
        data_final: str,
        uf: str | None = "GO",
        modalidade: int = MODALIDADE_PREGAO_ELETRONICO,
        pagina: int = 1,
        tamanho: int = 50,
    ) -> tuple[list[Contratacao], int]:
        """Contratações publicadas no período (datas AAAAMMDD). Retorna (lista, total_paginas)."""
        params: dict[str, Any] = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": modalidade,
            "pagina": pagina,
            "tamanhoPagina": tamanho,
        }
        if uf:
            params["uf"] = uf
        dados = self.get_json(f"{BASE_CONSULTA}/contratacoes/publicacao", params)
        lista = [contratacao_de_api(d) for d in (dados or {}).get("data", [])]
        return lista, int((dados or {}).get("totalPaginas") or 1)

    def buscar_propostas_abertas(
        self,
        data_final: str | None = None,
        uf: str | None = "GO",
        modalidade: int = MODALIDADE_PREGAO_ELETRONICO,
        pagina: int = 1,
        tamanho: int = 50,
        horizonte_dias: int = 60,
    ) -> tuple[list[Contratacao], int]:
        """Contratações com propostas ainda abertas cujo prazo encerra ATÉ data_final (AAAAMMDD).

        Atenção: `dataFinal` é o limite do encerramento, não "a data de hoje". Passar hoje devolve só
        o que fecha hoje (foi o que fez a busca voltar vazia); por isso o padrão é hoje + horizonte_dias."""
        if data_final is None:
            data_final = (datetime.now() + timedelta(days=horizonte_dias)).strftime("%Y%m%d")
        params: dict[str, Any] = {
            "dataFinal": data_final,
            "codigoModalidadeContratacao": modalidade,
            "pagina": pagina,
            "tamanhoPagina": tamanho,
        }
        if uf:
            params["uf"] = uf
        # Listagem muda devagar: 30 min de cache evita o limite de requisições do portal entre prospecções
        dados = self.get_json(f"{BASE_CONSULTA}/contratacoes/proposta", params, ttl_s=1800)
        # 204 (sem corpo) chega aqui como lista vazia
        if not isinstance(dados, dict):
            return [], 1
        lista = [contratacao_de_api(d) for d in dados.get("data", [])]
        return lista, int(dados.get("totalPaginas") or 1)

    def filtrar_por_palavras(self, contratacoes: list[Contratacao], palavras: list[str]) -> list[Contratacao]:
        chaves = [p.lower() for p in palavras]
        return [c for c in contratacoes if any(k in c.objeto.lower() for k in chaves)]

    # ----------------------------------------------------------- Detalhes

    def detalhe(self, cnpj: str, ano: int, seq: int) -> Contratacao:
        dados = self.get_json(f"{BASE_CONSULTA}/orgaos/{cnpj}/compras/{ano}/{seq}")
        return contratacao_de_api(dados)

    def itens(self, cnpj: str, ano: int, seq: int, contratacao_id: str) -> list[ItemDemanda]:
        dados = self.get_json(
            f"{BASE_PNCP}/orgaos/{cnpj}/compras/{ano}/{seq}/itens", {"pagina": 1, "tamanhoPagina": 500}
        )
        return [item_de_api(d, contratacao_id) for d in (dados or [])]

    def arquivos(self, cnpj: str, ano: int, seq: int) -> list[dict[str, Any]]:
        dados = self.get_json(
            f"{BASE_PNCP}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos", {"pagina": 1, "tamanhoPagina": 100}
        )
        return list(dados or [])

    def baixar_arquivo(self, url: str, destino_dir: Path, nome_sugerido: str) -> Path:
        destino_dir.mkdir(parents=True, exist_ok=True)
        cache = self._cache_path(url, ".bin")
        if cache.exists():
            blob = cache.read_bytes()
        else:
            resp = self._get(url)
            blob = resp.content
            cache.write_bytes(blob)
        nome = _nome_arquivo_seguro(nome_sugerido)
        destino = destino_dir / nome
        destino.write_bytes(blob)
        # Extensão pelo conteúdo: o PNCP manda docx/xlsx sem extensão (antes viravam ".zip")
        from obranexo.documents.formatos import tipo_arquivo

        sufixo = {"pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx", "zip": ".zip"}.get(tipo_arquivo(destino))
        if sufixo and not nome.lower().endswith(sufixo):
            final = destino.with_name(nome + sufixo)
            destino.replace(final)
            destino = final
        return destino

    # -------------------------------------------------------------- Casos

    def tamanho_remoto(self, url: str) -> int | None:
        try:
            resp = self._http.head(url)
            return int(resp.headers.get("Content-Length") or 0) or None
        except httpx.HTTPError:
            return None

    def coletar_caso(
        self, cnpj: str, ano: int, seq: int, destino: Path, max_mb: float | None = None, so_pdf: bool = False
    ) -> tuple[Contratacao, list[ItemDemanda], list[Documento]]:
        """Baixa detalhe, itens e anexos de uma contratação e congela tudo em `destino`.

        Anexos acima de `max_mb` (ou não-PDF, se `so_pdf`) ficam listados em documentos.json sem download,
        para que o dossiê ainda os mencione — obras públicas chegam a centenas de MB de projetos."""
        contratacao = self.detalhe(cnpj, ano, seq)
        itens = self.itens(cnpj, ano, seq, contratacao.id)
        arquivos = self.arquivos(cnpj, ano, seq)
        documentos: list[Documento] = []
        for a in arquivos:
            url = a.get("url") or a.get("uri")
            if not url:
                continue
            seq_doc = a.get("sequencialDocumento")
            titulo = a.get("titulo") or "documento"
            nome = f"{seq_doc}_{titulo}"
            doc = Documento(id=f"doc-{seq_doc}", contratacao_id=contratacao.id, nome=nome, tipo_doc=a.get("tipoDocumentoNome"), url_origem=url)
            tamanho = self.tamanho_remoto(url) if max_mb else None
            parece_pdf = titulo.lower().endswith(".pdf") or "pdf" in titulo.lower()
            if (max_mb and tamanho and tamanho > max_mb * 1024 * 1024) or (so_pdf and not parece_pdf and titulo.lower().endswith((".zip", ".dwg", ".rar"))):
                doc.extraivel = False
                doc.nome = f"{nome} (não baixado: {tamanho / 1024 / 1024:.0f} MB)" if tamanho else f"{nome} (não baixado)"
                documentos.append(doc)
                continue
            caminho = self.baixar_arquivo(url, destino / "arquivos", nome)
            doc.nome = caminho.name
            doc.sha256 = hashlib.sha256(caminho.read_bytes()).hexdigest()
            doc.caminho_local = caminho.relative_to(destino).as_posix()  # "/" funciona em Windows e Linux
            doc.extraivel = caminho.suffix.lower() in {".pdf", ".docx", ".xlsx", ".zip"}
            documentos.append(doc)
        salvar_caso(destino, contratacao, itens, documentos)
        return contratacao, itens, documentos


# ---------------------------------------------------------------------------
# Pacotes congelados (modo offline / demo reproduzível)
# ---------------------------------------------------------------------------


def salvar_caso(destino: Path, contratacao: Contratacao, itens: list[ItemDemanda], documentos: list[Documento]) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "contratacao.json").write_text(
        contratacao.model_dump_json(indent=1, exclude={"bruto"}), encoding="utf-8"
    )
    (destino / "contratacao_bruto.json").write_text(
        json.dumps(contratacao.bruto, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (destino / "itens.json").write_text(
        json.dumps([i.model_dump(mode="json") for i in itens], ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (destino / "documentos.json").write_text(
        json.dumps([d.model_dump(mode="json") for d in documentos], ensure_ascii=False, indent=1), encoding="utf-8"
    )


def carregar_caso(diretorio: Path) -> tuple[Contratacao, list[ItemDemanda], list[Documento]]:
    contratacao = Contratacao.model_validate_json((diretorio / "contratacao.json").read_text(encoding="utf-8"))
    bruto = diretorio / "contratacao_bruto.json"
    if bruto.exists():
        contratacao.bruto = json.loads(bruto.read_text(encoding="utf-8"))
    itens = [ItemDemanda.model_validate(d) for d in json.loads((diretorio / "itens.json").read_text(encoding="utf-8"))]
    documentos = [
        Documento.model_validate(d) for d in json.loads((diretorio / "documentos.json").read_text(encoding="utf-8"))
    ]
    for doc in documentos:
        if doc.caminho_local:
            # Pacotes gravados no Windows têm "arquivos\\x.pdf": em Linux a barra invertida faria parte do nome
            doc.caminho_local = str(diretorio / doc.caminho_local.replace("\\", "/"))
    return contratacao, itens, documentos


def listar_casos(dir_casos: Path | None = None) -> list[Path]:
    base = dir_casos or config.dir_casos
    if not base.exists():
        return []
    return sorted(p for p in base.iterdir() if (p / "contratacao.json").exists())
