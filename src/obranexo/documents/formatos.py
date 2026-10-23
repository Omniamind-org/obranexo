"""Leitura de anexos além de PDF: DOCX, XLSX, texto e arquivos ZIP (expandidos).

O PNCP entrega muitos anexos sem extensão ou como .zip — projetos elétricos, atas de
resultado, planilhas orçamentárias. O tipo é decidido pelo conteúdo (bytes iniciais e
nomes internos do pacote), nunca pela extensão.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

TAMANHO_PAGINA_VIRTUAL = 3500  # DOCX/XLSX/TXT não têm páginas: o texto é fatiado para citação
EXTENSOES_SUPORTADAS = {".pdf", ".docx", ".xlsx", ".txt", ".csv"}
MAX_MEMBRO_BYTES = 40 * 1024 * 1024
MAX_TOTAL_BYTES = 120 * 1024 * 1024
MAX_MEMBROS = 40


def tipo_arquivo(caminho: Path) -> str:
    """pdf | docx | xlsx | zip | texto | desconhecido"""
    try:
        with open(caminho, "rb") as f:
            inicio = f.read(8)
    except OSError:
        return "desconhecido"
    if inicio.startswith(b"%PDF"):
        return "pdf"
    if inicio.startswith(b"PK"):
        try:
            with zipfile.ZipFile(caminho) as z:
                nomes = set(z.namelist())
        except zipfile.BadZipFile:
            return "desconhecido"
        if "word/document.xml" in nomes:
            return "docx"
        if "xl/workbook.xml" in nomes:
            return "xlsx"
        return "zip"
    if caminho.suffix.lower() in {".txt", ".csv"}:
        return "texto"
    return "desconhecido"


def _paginar(texto: str) -> list[str]:
    texto = re.sub(r"[ \t\xa0]+", " ", texto).strip()
    if not texto:
        return []
    paginas, atual = [], ""
    for paragrafo in texto.split("\n"):
        if atual and len(atual) + len(paragrafo) > TAMANHO_PAGINA_VIRTUAL:
            paginas.append(atual)
            atual = paragrafo
        else:
            atual = f"{atual}\n{paragrafo}" if atual else paragrafo
    if atual:
        paginas.append(atual)
    return paginas


def _texto_docx(caminho: Path) -> str:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(caminho) as z:
        raiz = ElementTree.fromstring(z.read("word/document.xml"))
    linhas = []
    for p in raiz.iter(f"{ns}p"):
        texto = "".join(t.text or "" for t in p.iter(f"{ns}t"))
        if texto.strip():
            linhas.append(texto)
    return "\n".join(linhas)


def _texto_xlsx(caminho: Path) -> str:
    import io
    import warnings

    from openpyxl import load_workbook

    # Por bytes: o openpyxl recusa pela extensão, e o PNCP entrega planilhas sem extensão ou como ".zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # planilhas de portais de compra quase nunca têm estilo padrão
        wb = load_workbook(io.BytesIO(caminho.read_bytes()), read_only=True, data_only=True)
    linhas = []
    for ws in wb.worksheets:
        linhas.append(f"[Planilha: {ws.title}]")
        for row in ws.iter_rows(values_only=True):
            celulas = [str(c).strip() for c in row if c is not None and str(c).strip()]
            if celulas:
                linhas.append(" | ".join(celulas))
    wb.close()
    return "\n".join(linhas)


def extrair_paginas_arquivo(caminho: Path) -> list[str]:
    """Texto por página (real no PDF, virtual nos demais). Lista vazia se não houver texto legível."""
    tipo = tipo_arquivo(caminho)
    if tipo == "pdf":
        from obranexo.documents.extract import extrair_paginas

        return extrair_paginas(caminho)
    if tipo == "docx":
        return _paginar(_texto_docx(caminho))
    if tipo == "xlsx":
        return _paginar(_texto_xlsx(caminho))
    if tipo == "texto":
        return _paginar(caminho.read_text(encoding="utf-8", errors="replace"))
    return []


def texto_de_html(html: str) -> str:
    """Texto legível de uma página de produto (descarta scripts, menus e rodapés)."""
    import html as html_mod

    titulo = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    # <head> fora: atributos de <meta> com ">" dentro do texto deixavam lixo no resultado
    html = re.sub(r"(?is)<head\b.*?</head>", " ", html)
    if titulo:
        html = f"<p>{titulo.group(1)}</p>" + html
    html = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)\b.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</tr>|</h\d>|</div>|</td>|</th>", "\n", html)
    texto = html_mod.unescape(re.sub(r"<[^>]+>", " ", html))
    texto = re.sub(r"[ \t\xa0]+", " ", texto)
    return "\n".join(linha.strip() for linha in texto.splitlines() if len(linha.strip()) > 2)


def baixar_pagina(url: str, timeout: float = 40) -> str:
    """Baixa uma página pública de produto e devolve o texto. Só http(s); nada de endereços internos."""
    from urllib.parse import urlparse

    import httpx

    partes = urlparse(url)
    if partes.scheme not in {"http", "https"} or not partes.hostname:
        raise ValueError("informe um endereço http(s) válido")
    if partes.hostname in {"localhost", "127.0.0.1", "0.0.0.0"} or partes.hostname.endswith((".local", ".internal")):
        raise ValueError("endereço não permitido")
    # Cabeçalho HTTP só aceita ASCII (um acento aqui quebrava toda importação por URL)
    resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0 (ObraNexo/0.1; leitura de ficha tecnica)"}, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    tipo = resp.headers.get("content-type", "")
    if "pdf" in tipo or resp.content[:4] == b"%PDF":
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(resp.content)
        from obranexo.documents.extract import extrair_paginas

        return "\n".join(extrair_paginas(Path(f.name)))
    return texto_de_html(resp.text)


def _nome_seguro(nome: str) -> str:
    base = Path(nome.replace("\\", "/")).name  # nunca respeita diretórios do zip (zip slip)
    base = re.sub(r"[^\w.\- ]+", "_", base, flags=re.UNICODE).strip(" ._")
    return base[:100] or "arquivo"


def expandir_zip(caminho: Path, destino: Path | None = None) -> list[Path]:
    """Extrai os anexos legíveis de um .zip (inclusive zips dentro de zip, um nível) para `destino`.
    Idempotente: reaproveita o que já foi extraído. Limites contra zip bomb."""
    destino = destino or caminho.with_name(caminho.stem + "_conteudo")
    destino.mkdir(parents=True, exist_ok=True)
    extraidos: list[Path] = []
    total = 0

    def processar(z: zipfile.ZipFile, prefixo: str, profundidade: int) -> None:
        nonlocal total
        for info in z.infolist():
            if info.is_dir() or len(extraidos) >= MAX_MEMBROS:
                continue
            if info.file_size > MAX_MEMBRO_BYTES or total + info.file_size > MAX_TOTAL_BYTES:
                continue
            nome = _nome_seguro(info.filename)
            sufixo = Path(nome).suffix.lower()
            if sufixo == ".zip" and profundidade == 0:
                import io

                with zipfile.ZipFile(io.BytesIO(z.read(info))) as interno:
                    processar(interno, prefixo + Path(nome).stem + "__", 1)
                continue
            if sufixo not in EXTENSOES_SUPORTADAS:
                continue
            alvo = destino / f"{prefixo}{nome}"
            if not alvo.exists():
                alvo.write_bytes(z.read(info))
            total += info.file_size
            extraidos.append(alvo)

    try:
        with zipfile.ZipFile(caminho) as z:
            processar(z, "", 0)
    except zipfile.BadZipFile:
        return []
    return extraidos
