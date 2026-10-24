"""Carregamento e normalização do catálogo do fornecedor (JSON, CSV ou XLSX)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from obranexo.catalog.atributos import ATRIBUTOS
from obranexo.models import Atributo, Empresa, Produto, TipoAtributo


def _parse_valor(atributo: str, bruto: Any) -> Atributo:
    """Converte um valor bruto (string de planilha ou JSON) no Atributo tipado."""
    meta = ATRIBUTOS.get(atributo, {})
    tipo = meta.get("tipo", TipoAtributo.TEXTO)
    unidade = meta.get("unidade")
    if isinstance(bruto, dict):
        return Atributo(valor=bruto.get("valor"), unidade=bruto.get("unidade", unidade), tipo=bruto.get("tipo", tipo))
    if tipo == TipoAtributo.BOOLEANO:
        if isinstance(bruto, str):
            return Atributo(valor=bruto.strip().lower() in {"sim", "s", "true", "1", "x"}, tipo=tipo)
        return Atributo(valor=bool(bruto), tipo=tipo)
    if tipo == TipoAtributo.FAIXA:
        if isinstance(bruto, list | tuple) and len(bruto) == 2:
            return Atributo(valor=[float(bruto[0]), float(bruto[1])], unidade=unidade, tipo=tipo)
        if isinstance(bruto, int | float):
            return Atributo(valor=[float(bruto), float(bruto)], unidade=unidade, tipo=tipo)
        numeros = re.findall(r"-?\d+(?:[.,]\d+)?", str(bruto))
        if len(numeros) >= 2:
            a, b = (float(n.replace(",", ".")) for n in numeros[:2])
            return Atributo(valor=[min(a, b), max(a, b)], unidade=unidade, tipo=tipo)
        if numeros:
            v = float(numeros[0].replace(",", "."))
            return Atributo(valor=[v, v], unidade=unidade, tipo=tipo)
        return Atributo(valor=None, unidade=unidade, tipo=tipo)
    if tipo == TipoAtributo.NUMERO:
        if isinstance(bruto, int | float):
            return Atributo(valor=float(bruto), unidade=unidade, tipo=tipo)
        m = re.search(r"-?\d+(?:[.,]\d+)?", str(bruto).replace(".", "") if re.search(r"\d\.\d{3}\b", str(bruto)) else str(bruto))
        return Atributo(valor=float(m.group().replace(",", ".")) if m else None, unidade=unidade, tipo=tipo)
    if tipo == TipoAtributo.ENUM:
        return Atributo(valor=str(bruto).upper().replace(" ", "").replace("-", ""), tipo=tipo)
    return Atributo(valor=str(bruto), unidade=unidade, tipo=tipo)


def _texto_ou_none(v: Any) -> str | None:
    return str(v).strip() or None if v is not None else None


def produto_de_dict(d: dict[str, Any]) -> Produto:
    atributos = {k: _parse_valor(k, v) for k, v in (d.get("atributos") or {}).items() if v is not None and v != ""}
    # Colunas ausentes em CSV/XLSX chegam como None: normaliza para os padrões do modelo
    return Produto(
        id=str(d.get("id") or d.get("sku")),
        sku=str(d.get("sku") or d.get("id")),
        nome=str(d.get("nome") or ""),
        categoria=str(d.get("categoria") or "outro"),
        subcategoria=d.get("subcategoria"),
        fabricante=_texto_ou_none(d.get("fabricante")),
        marca=_texto_ou_none(d.get("marca")),
        modelo=_texto_ou_none(d.get("modelo")),
        descricao=str(d.get("descricao") or ""),
        atributos=atributos,
        normas=list(d.get("normas") or []),
        certificacoes=list(d.get("certificacoes") or []),
        preco_ref=d.get("preco_ref"),
        prazo_entrega_dias=d.get("prazo_entrega_dias"),
        estoque=d.get("estoque"),
    )


def carregar_catalogo_json(caminho: Path) -> Empresa:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    empresa = dados.get("empresa", {})
    produtos = [produto_de_dict(p) for p in dados.get("produtos", [])]
    return Empresa(
        id=empresa.get("id", "empresa-demo"),
        nome=empresa.get("nome", "Fornecedor"),
        cnpj=empresa.get("cnpj"),
        **{k: _texto_ou_none(empresa.get(k)) for k in ("razao_social", "endereco", "telefone", "email", "representante",
                                                        "representante_cargo", "dados_bancarios")},
        ufs_atendidas=list(empresa.get("ufs_atendidas") or []),
        raio_km=empresa.get("raio_km"),
        observacoes=empresa.get("observacoes", ""),
        produtos=produtos,
    )


def carregar_catalogo_tabela(caminho: Path, empresa: Empresa | None = None) -> Empresa:
    """CSV/XLSX com uma linha por produto. Colunas fixas: sku, nome, categoria, subcategoria, fabricante,
    marca, modelo, descricao, normas, certificacoes, preco_ref, prazo_entrega_dias. Demais colunas cujo
    nome coincide com um atributo canônico viram atributos (ex.: potencia_w, ip, cct_k)."""
    import pandas as pd

    caminho = Path(caminho)
    df = pd.read_excel(caminho) if caminho.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(caminho, sep=None, engine="python")
    fixas = {"sku", "id", "nome", "categoria", "subcategoria", "fabricante", "marca", "modelo", "descricao", "normas", "certificacoes",
             "preco_ref", "prazo_entrega_dias", "estoque"}
    produtos: list[Produto] = []
    for _, linha in df.iterrows():
        reg: dict[str, Any] = {k: (None if pd.isna(v) else v) for k, v in linha.to_dict().items()}
        atributos = {k: v for k, v in reg.items() if k in ATRIBUTOS and v is not None}
        for campo in ("normas", "certificacoes"):
            if isinstance(reg.get(campo), str):
                reg[campo] = [s.strip() for s in re.split(r"[;|,]", reg[campo]) if s.strip()]
        produtos.append(produto_de_dict({**{k: reg.get(k) for k in fixas}, "atributos": atributos}))
    base = empresa or Empresa(id="empresa-upload", nome="Fornecedor (upload)")
    return base.model_copy(update={"produtos": produtos})
