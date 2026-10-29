"""Categorias do catálogo e reconhecimento do que o fornecedor escreve na planilha.

O casamento item × produto exige a chave exata (pipeline: `p.categoria == item.categoria_inferida`): um produto
com "Luminária pública" nunca é comparado com nada. Aqui a categoria escrita vira a chave canônica quando
o reconhecimento é seguro; quando não é, o produto fica como "outro" e a importação avisa com uma sugestão.
"""

from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz, process

CATEGORIAS = (
    "luminaria_publica_led", "luminaria_interna", "refletor_led", "lampada", "rele_fotoeletrico", "braco_luminaria",
    "poste", "cabo", "disjuntor", "eletroduto", "quadro", "dispositivos", "transformador", "bateria", "outro",
)

# Nomes comuns que a semelhança de texto não alcança ou alcança de forma ambígua
SINONIMOS = {
    "luminaria_publica": "luminaria_publica_led",
    "iluminacao_publica": "luminaria_publica_led",
    "luminaria_viaria": "luminaria_publica_led",
    "luminaria_de_led_publica": "luminaria_publica_led",
    "refletor": "refletor_led",
    "projetor_led": "refletor_led",
    "rele": "rele_fotoeletrico",
    "rele_fotocelula": "rele_fotoeletrico",
    "fotocelula": "rele_fotoeletrico",
    "braco": "braco_luminaria",
    "braco_de_luminaria": "braco_luminaria",
    "fio": "cabo",
    "fio_e_cabo": "cabo",
    "condutor": "cabo",
    "quadro_de_distribuicao": "quadro",
    "tomada": "dispositivos",
    "interruptor": "dispositivos",
    "plafon": "luminaria_interna",
    "painel_led": "luminaria_interna",
}
# Correção automática só com texto quase igual (plural, letra trocada) e sem empate com outra categoria
LIMIAR_AUTOMATICO = 85
LIMIAR_SUGESTAO = 60
MARGEM = 10


def _chave(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def resolver_categoria(bruto: object) -> tuple[str, str | None]:
    """Devolve (categoria canônica, aviso). O aviso é None quando a categoria foi reconhecida sem dúvida."""
    if bruto is None or not str(bruto).strip():
        return "outro", None
    chave = _chave(str(bruto))
    if chave in CATEGORIAS:
        return chave, None
    if chave in SINONIMOS:
        return SINONIMOS[chave], f'categoria "{bruto}" entendida como {SINONIMOS[chave]}'
    candidatos = process.extract(chave, CATEGORIAS, scorer=fuzz.ratio, limit=2)
    (melhor, nota, _), segunda = candidatos[0], (candidatos[1][1] if len(candidatos) > 1 else 0)
    if nota >= LIMIAR_AUTOMATICO and nota - segunda >= MARGEM:
        return melhor, f'categoria "{bruto}" entendida como {melhor}'
    sugestao = f"; você quis dizer {melhor}?" if nota >= LIMIAR_SUGESTAO else ""
    return "outro", f'categoria "{bruto}" não reconhecida, o produto ficou como "outro" e não será comparado com os itens{sugestao}'
