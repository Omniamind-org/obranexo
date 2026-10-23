"""Leitura de anexos não-PDF (DOCX, XLSX, ZIP) — formatos que o PNCP entrega sem extensão ou compactados."""

import io
import zipfile

from obranexo.documents.formatos import expandir_zip, extrair_paginas_arquivo, texto_de_html, tipo_arquivo

DOCX_XML = (
    '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p><w:r><w:t>TERMO DE REFERÊNCIA</w:t></w:r></w:p>"
    "<w:p><w:r><w:t>Item 3: luminária pública LED 150 W, </w:t></w:r><w:r><w:t>IP66, 5000K</w:t></w:r></w:p></w:body></w:document>"
)


def _docx(caminho):
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", DOCX_XML)


def _xlsx(caminho):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Orçamento"
    ws.append(["Item", "Descrição", "Qtd"])
    ws.append([1, "Cabo flexível 2,5 mm²", 300])
    wb.save(caminho)


def test_docx_sem_extensao_e_detectado_pelo_conteudo(tmp_path):
    arq = tmp_path / "anexo_sem_extensao"
    _docx(arq)
    assert tipo_arquivo(arq) == "docx"
    paginas = extrair_paginas_arquivo(arq)
    assert "luminária pública LED 150 W, IP66, 5000K" in paginas[0]


def test_xlsx_salvo_como_zip(tmp_path):
    arq = tmp_path / "planilha.zip"
    _xlsx(arq)
    assert tipo_arquivo(arq) == "xlsx"
    texto = "\n".join(extrair_paginas_arquivo(arq))
    assert "[Planilha: Orçamento]" in texto and "Cabo flexível 2,5 mm² | 300" in texto


def test_zip_com_anexos_e_zip_interno(tmp_path):
    docx = tmp_path / "tr.docx"
    _docx(docx)
    interno = io.BytesIO()
    with zipfile.ZipFile(interno, "w") as z:
        z.writestr("memorial.txt", "Memorial descritivo: disjuntor 20 A curva C")
    pacote = tmp_path / "projeto.zip"
    with zipfile.ZipFile(pacote, "w") as z:
        z.write(docx, "pasta/tr.docx")
        z.writestr("projetos.zip", interno.getvalue())
        z.writestr("desenho.dwg", b"binario")  # formato não legível: ignorado
        z.writestr("../../fora_do_destino.txt", "zip slip")
    assert tipo_arquivo(pacote) == "zip"
    extraidos = expandir_zip(pacote)
    nomes = sorted(p.name for p in extraidos)
    assert "tr.docx" in nomes and "projetos__memorial.txt" in nomes and not any(n.endswith(".dwg") for n in nomes)
    destino = tmp_path / "projeto_conteudo"
    assert all(p.parent == destino for p in extraidos)  # nada sai do diretório de destino
    assert not (tmp_path.parent / "fora_do_destino.txt").exists()
    assert expandir_zip(pacote) == extraidos  # idempotente


def test_texto_de_html_descarta_scripts_e_menus():
    html = ("<html><head><script>var x=1</script></head><body><nav>Menu Loja</nav>"
            "<h1>Luminária 100W</h1><table><tr><td>Fluxo</td><td>16.000 lm</td></tr></table><footer>Rodapé</footer></body></html>")
    t = texto_de_html(html)
    assert "Luminária 100W" in t and "16.000 lm" in t
    assert "var x" not in t and "Menu Loja" not in t and "Rodapé" not in t
