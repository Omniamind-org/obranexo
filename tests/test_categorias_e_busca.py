"""Categoria escrita pelo fornecedor na planilha e busca no PNCP por modalidade, lendo todas as páginas."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from obranexo.catalog.categorias import resolver_categoria
from obranexo.catalog.loader import carregar_catalogo_tabela
from obranexo.config import config
from obranexo.models import Contratacao


@pytest.mark.parametrize("bruto, esperada", [
    ("luminaria_publica_led", "luminaria_publica_led"),
    ("Luminária Pública LED", "luminaria_publica_led"),
    ("Luminária pública", "luminaria_publica_led"),
    ("Iluminação pública", "luminaria_publica_led"),
    ("Cabos", "cabo"),
    ("Disjuntores", "disjuntor"),
    ("Relé fotocélula", "rele_fotoeletrico"),
    ("  LÂMPADAS ", "lampada"),
])
def test_categoria_reconhecida(bruto, esperada):
    assert resolver_categoria(bruto)[0] == esperada


def test_categoria_exata_nao_gera_aviso():
    assert resolver_categoria("Refletor LED") == ("refletor_led", None)
    assert resolver_categoria(None) == ("outro", None)


@pytest.mark.parametrize("bruto", ["Luminária", "c", "Ferragens"])
def test_categoria_ambigua_ou_desconhecida_vira_outro_com_aviso(bruto):
    categoria, aviso = resolver_categoria(bruto)
    assert categoria == "outro"
    assert aviso and "não reconhecida" in aviso


def test_sugestao_quando_ha_categoria_parecida():
    assert "você quis dizer" in resolver_categoria("Luminária")[1]


def test_planilha_corrige_categoria_e_avisa(tmp_path):
    csv = tmp_path / "catalogo.csv"
    csv.write_text("sku,nome,categoria,potencia_w\nLP-100,Luminária 100 W,Luminária pública,100\nX-1,Abraçadeira,Ferragens,\n", encoding="utf-8")
    avisos: list[str] = []
    produtos = carregar_catalogo_tabela(csv, avisos=avisos).produtos
    assert [p.categoria for p in produtos] == ["luminaria_publica_led", "outro"]
    assert len(avisos) == 2 and avisos[0].startswith("LP-100:") and avisos[1].startswith("X-1:")


# ------------------------------------------------------------------ busca no PNCP


def _contratacao(n: int, objeto: str = "Aquisição de luminárias LED") -> Contratacao:
    return Contratacao(id=f"00000000000100-1-{n:06d}/2026", orgao_cnpj="00000000000100", orgao_nome="Prefeitura", ano=2026, sequencial=n, objeto=objeto)


class _PNCPFalso:
    """3 páginas por modalidade; a mesma contratação aparece em duas modalidades para testar a deduplicação."""

    pedidos: list[tuple[int, int]] = []

    def buscar_propostas_abertas(self, uf, modalidade, pagina, horizonte_dias):
        self.pedidos.append((modalidade, pagina))
        return [_contratacao(modalidade * 100 + pagina), _contratacao(1), _contratacao(999, "Material de limpeza")], 3

    def filtrar_por_palavras(self, lista, palavras):
        return [c for c in lista if any(p in c.objeto.lower() for p in palavras)]


@pytest.fixture()
def client(monkeypatch, entrar):
    from obranexo.api import main

    monkeypatch.setattr(config, "offline", False)
    monkeypatch.setattr(main, "PNCPClient", _PNCPFalso)
    _PNCPFalso.pedidos = []
    with TestClient(main.app) as c:
        entrar(c)
        yield c


def test_busca_le_todas_as_paginas_de_cada_modalidade(client):
    r = client.get("/api/pncp/buscar", params={"modalidades": "6,4", "palavras": "lumin"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert _PNCPFalso.pedidos == [(6, 1), (6, 2), (6, 3), (4, 1), (4, 2), (4, 3)]
    assert corpo["paginas_consultadas"] == 6 and corpo["truncada"] is False
    assert len(corpo["resultados"]) == 7  # 6 distintas + a repetida uma vez só; a de limpeza fica de fora


def test_busca_avisa_quando_atinge_o_teto(client):
    corpo = client.get("/api/pncp/buscar", params={"max_paginas": 2}).json()
    assert _PNCPFalso.pedidos == [(6, 1), (6, 2)]
    assert corpo["truncada"] is True


@pytest.mark.parametrize("modalidades", ["99", "abc", ""])
def test_busca_rejeita_modalidade_invalida(client, modalidades):
    assert client.get("/api/pncp/buscar", params={"modalidades": modalidades}).status_code == 422
