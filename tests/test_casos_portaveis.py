"""Pacotes congelados precisam abrir em Windows e em Linux (CI, servidor na nuvem)."""

import json
from pathlib import Path

from obranexo.config import config
from obranexo.connectors.pncp import carregar_caso, listar_casos


def test_caminho_gravado_no_windows_abre_em_qualquer_sistema(tmp_path):
    caso = tmp_path / "caso"
    (caso / "arquivos").mkdir(parents=True)
    (caso / "arquivos" / "edital.pdf").write_bytes(b"%PDF-1.4")
    origem = config.dir_casos / "goianira_pe038_2026"
    for nome in ("contratacao.json", "itens.json"):
        (caso / nome).write_text((origem / nome).read_text(encoding="utf-8"), encoding="utf-8")
    doc = {"id": "doc-1", "contratacao_id": "x", "nome": "edital.pdf", "caminho_local": "arquivos\\edital.pdf"}
    (caso / "documentos.json").write_text(json.dumps([doc]), encoding="utf-8")

    _, _, documentos = carregar_caso(caso)

    assert Path(documentos[0].caminho_local).exists()


def test_todos_os_anexos_baixados_dos_casos_existem():
    faltando = []
    for diretorio in listar_casos():
        _, _, documentos = carregar_caso(diretorio)
        faltando += [f"{diretorio.name}: {d.caminho_local}" for d in documentos if d.caminho_local and not Path(d.caminho_local).exists()]
    assert not faltando, faltando
