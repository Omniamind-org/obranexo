"""Categoria escrita pelo fornecedor na planilha e busca no PNCP por modalidade, lendo todas as páginas."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from obranexo.catalog.categorias import resolver_categoria
from obranexo.catalog.loader import carregar_catalogo_tabela
from obranexo.config import config
from obranexo.connectors.pncp import PNCPClient, PNCPError
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
    assert resolver_categoria("Luminária")[1].endswith("você quis dizer luminaria_publica_led ou luminaria_interna?")
    assert resolver_categoria("Transformadr de força")[1].endswith("você quis dizer transformador?")


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


class _PNCPFalso(PNCPClient):
    """3 páginas por modalidade; a mesma contratação aparece em duas modalidades para testar a deduplicação."""

    pedidos: list[tuple[int, int]] = []

    def buscar_propostas_abertas(self, uf, modalidade, pagina, horizonte_dias):
        self.pedidos.append((modalidade, pagina))
        return [_contratacao(modalidade * 100 + pagina), _contratacao(1), _contratacao(999, "Material de limpeza")], 3


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


def test_busca_em_segundo_plano_mostra_cada_pagina_e_entrega_os_resultados(client):
    r = client.post("/api/pncp/buscas", json={"modalidades": "6,4", "palavras": "lumin"})
    assert r.status_code == 202, r.text
    job_id = r.json()["id"]
    for _ in range(100):
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "executando":
            break
        time.sleep(0.05)
    assert j["status"] == "concluida", j
    mensagens = [e["mensagem"] for e in j["log"]]
    assert mensagens[0] == "Pregão - Eletrônico: página 1 de 3 (modalidade 1 de 2)"
    assert mensagens[-1] == "Concorrência - Eletrônica: página 3 de 3 (modalidade 2 de 2)"
    assert len(j["dados"]["resultados"]) == 7


def test_busca_em_segundo_plano_valida_antes_de_comecar(client):
    assert client.post("/api/pncp/buscas", json={"modalidades": "99"}).status_code == 422


# ------------------------------------------------------------------ conector: várias modalidades, tolerância a falha


class _PortalInstavel(PNCPClient):
    """Pregão eletrônico: 2 páginas; concorrência falha na página 2; dispensa falha já na página 1."""

    def __init__(self):
        super().__init__(offline=False, pausa_s=0)

    def buscar_propostas_abertas(self, uf, modalidade, pagina, horizonte_dias):
        if (modalidade, pagina) in {(4, 2), (8, 1)}:
            raise PNCPError("HTTP 500")
        return [_contratacao(modalidade * 100 + pagina)], 2


def test_modo_tolerante_segue_com_o_que_ja_leu():
    res = _PortalInstavel().buscar_todas("GO", [6, 4, 8], tolerante=True)
    assert len(res.contratacoes) == 3 and res.paginas_lidas == 3
    assert [f.split(":")[0] for f in res.falhas] == ["Concorrência - Eletrônica, página 2", "Dispensa de Licitação, página 1"]


def test_sem_tolerancia_a_falha_sobe():
    with pytest.raises(PNCPError):
        _PortalInstavel().buscar_todas("GO", [6, 4])


def test_tolerante_sem_nada_lido_tambem_sobe():
    with pytest.raises(PNCPError):
        _PortalInstavel().buscar_todas("GO", [8], tolerante=True)


def test_prospector_busca_em_todas_as_modalidades(tmp_path):
    from obranexo.agents.prospector import Prospector
    from obranexo.config import Config
    from obranexo.models import Empresa

    cfg = Config(llm_provider=None, gemini_api_key=None, anthropic_api_key=None, dir_dados=tmp_path)
    pr = Prospector(Empresa(id="e", nome="E"), ["GO"], 30, 0, cfg=cfg)
    pr.pncp = _PortalInstavel()
    assert len(pr._abertas_uf("GO")) == 7  # 6, 7 e 5 com 2 páginas; 4 só a 1ª; 8 falha logo
    log = [e.mensagem for e in pr.p.log]
    assert any("Dispensa de Licitação, página 1" in m for m in log)
    assert pr.p.parametros["modalidades"] == [6, 7, 4, 5, 8]


def test_cli_abertas_aceita_modalidades(monkeypatch, capsys):
    from obranexo import cli
    from obranexo.connectors import pncp

    pedidos = []

    class _Falso(_PortalInstavel):
        def buscar_propostas_abertas(self, uf, modalidade, pagina, horizonte_dias):
            pedidos.append(modalidade)
            return [_contratacao(modalidade * 100 + pagina)], 1

    monkeypatch.setattr(pncp, "PNCPClient", _Falso)
    assert cli.main(["abertas", "--uf", "GO", "--modalidades", "4,6", "--palavras", ""]) == 0
    assert pedidos == [4, 6]
    assert "2 contratação(ões) com propostas abertas · 2/2 página(s)" in capsys.readouterr().out


# ------------------------------------------------------------------ prioridade


def test_aberta_com_cobertura_parcial_fica_acima_de_encerrada_completa():
    """Aceite do plano: Itaberaí (aberta, cobertura parcial) acima de Goianira (encerrada, 100% compatível)."""
    import json
    from pathlib import Path

    retrato = json.loads((Path(__file__).parent / "dados" / "retrato_demo.json").read_text(encoding="utf-8"))
    assert retrato["cego_itaberai_mat_eletrico"]["prioridade"] > retrato["goianira_pe038_2026"]["prioridade"]
