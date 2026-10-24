"""Itens e anexos do PNCP vêm paginados: o conector precisa ler todas as páginas."""

from obranexo.connectors.pncp import MAX_PAGINAS_LISTA, PNCPClient


def _cliente(tmp_path, paginas):
    """PNCPClient cujo get_json devolve `paginas[n-1]` para pagina=n (e [] além delas, como o 204 do portal)."""
    cli = PNCPClient(dir_cache=tmp_path, offline=False, pausa_s=0)
    pedidos = []

    def get_json(url, params=None, **_kw):
        pedidos.append(params)
        pagina, tamanho = params["pagina"], params["tamanhoPagina"]
        lote = paginas(pagina) if callable(paginas) else (paginas[pagina - 1] if pagina <= len(paginas) else [])
        return lote[:tamanho]

    cli.get_json = get_json
    return cli, pedidos


def _itens(inicio, fim):
    return [{"numeroItem": n, "descricao": f"item {n}", "quantidade": 1} for n in range(inicio, fim + 1)]


def _anexos(inicio, fim):
    return [{"sequencialDocumento": n, "titulo": f"anexo {n}.pdf"} for n in range(inicio, fim + 1)]


def test_le_todos_os_itens_alem_da_primeira_pagina(tmp_path):
    cli, pedidos = _cliente(tmp_path, [_itens(1, 500), _itens(501, 503)])
    itens = cli.itens("00000000000100", 2026, 1, "x")
    assert [i.numero_item for i in itens] == list(range(1, 504))
    assert [p["pagina"] for p in pedidos] == [1, 2]


def test_le_todos_os_anexos_caso_seinfra(tmp_path):
    # Concorrência 02/2026 da SEINFRA-GO: 107 anexos, que antes paravam em 100
    cli, _ = _cliente(tmp_path, [_anexos(2, 101), _anexos(102, 108)])
    anexos = cli.arquivos("01409580000138", 2026, 733)
    assert len(anexos) == 107


def test_para_quando_a_pagina_seguinte_vem_vazia(tmp_path):
    cli, pedidos = _cliente(tmp_path, [_anexos(1, 100)])  # exatamente 100: a página 2 é o 204 do portal
    assert len(cli.arquivos("00000000000100", 2026, 1)) == 100
    assert [p["pagina"] for p in pedidos] == [1, 2]


def test_uma_pagina_so_continua_com_uma_requisicao(tmp_path):
    cli, pedidos = _cliente(tmp_path, [_itens(1, 6)])
    assert len(cli.itens("00000000000100", 2026, 1, "x")) == 6
    assert len(pedidos) == 1


def test_portal_que_ignora_a_pagina_nao_gera_laco_nem_duplicata(tmp_path):
    cli, pedidos = _cliente(tmp_path, lambda _pagina: _anexos(1, 100))
    assert len(cli.arquivos("00000000000100", 2026, 1)) == 100
    assert len(pedidos) == 2


def test_teto_de_paginas(tmp_path):
    cli, pedidos = _cliente(tmp_path, lambda p: _itens((p - 1) * 500 + 1, p * 500))
    assert len(cli.itens("00000000000100", 2026, 1, "x")) == MAX_PAGINAS_LISTA * 500
    assert len(pedidos) == MAX_PAGINAS_LISTA
