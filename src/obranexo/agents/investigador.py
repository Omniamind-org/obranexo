"""Agente Investigador: procura nos documentos do processo as informações que faltam.

Com LLM: loop de uso de ferramentas (buscar_trechos, ler_pagina, registrar_requisito,
concluir_investigacao) limitado por número de passos e orçamento de tokens.
Sem LLM: busca textual guiada por sinônimos + extração por regras nos trechos achados.
"""

from __future__ import annotations

import json
import re
from typing import Any

from obranexo.agents.contexto import Contexto
from obranexo.agents.prompts import SYSTEM_INVESTIGADOR
from obranexo.catalog.atributos import ATRIBUTOS, ATRIBUTOS_INVESTIGAVEIS, rotulo
from obranexo.models import Evidencia, Operador, Requisito
from obranexo.rules.extrair import extrair_requisitos, numero_br
from obranexo.rules.validar import normalizar_valor

FERRAMENTAS: list[dict[str, Any]] = [
    {
        "name": "listar_documentos",
        "description": "Lista os documentos disponíveis desta contratação (id, nome, tipo, número de páginas).",
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
    {
        "name": "buscar_trechos",
        "description": "Busca textual nos documentos. Devolve os trechos mais relevantes com documento_id e página.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "consulta": {"type": "string", "description": "Termos de busca curtos, ex.: 'prazo de entrega'"},
                "top_k": {"type": "integer", "description": "Quantidade de trechos (1 a 8)"},
            },
            "required": ["consulta", "top_k"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ler_pagina",
        "description": "Devolve o texto completo de uma página de um documento.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"documento_id": {"type": "string"}, "pagina": {"type": "integer"}},
            "required": ["documento_id", "pagina"],
            "additionalProperties": False,
        },
    },
    {
        "name": "registrar_requisito",
        "description": "Registra uma informação encontrada, com a evidência exata. Use valores normalizados.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "atributo": {"type": "string", "description": "Chave canônica, ex.: garantia_anos, prazo_entrega_dias, doc_amostra"},
                "operador": {"type": "string", "enum": ["=", ">=", "<=", "entre", "contem", "verdadeiro"]},
                "valor_numero": {"type": ["number", "null"]},
                "valor_texto": {"type": ["string", "null"]},
                "valor_booleano": {"type": ["boolean", "null"]},
                "documento_id": {"type": "string"},
                "pagina": {"type": "integer"},
                "trecho_literal": {"type": "string", "description": "Cópia exata do trecho do documento"},
            },
            "required": ["atributo", "operador", "valor_numero", "valor_texto", "valor_booleano", "documento_id", "pagina", "trecho_literal"],
            "additionalProperties": False,
        },
    },
    {
        "name": "concluir_investigacao",
        "description": "Encerra a investigação com um resumo do que foi encontrado e do que não foi localizado.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"resumo": {"type": "string"}, "nao_encontrados": {"type": "array", "items": {"type": "string"}}},
            "required": ["resumo", "nao_encontrados"],
            "additionalProperties": False,
        },
    },
]


def _executar_ferramenta(ctx: Contexto, nome: str, entrada: dict[str, Any], achados: list[Requisito]) -> str:
    indice = ctx.indice
    if nome == "listar_documentos":
        return json.dumps(indice.listar(), ensure_ascii=False)
    if nome == "buscar_trechos":
        top_k = max(1, min(int(entrada.get("top_k", 5)), 8))
        res = indice.buscar(str(entrada.get("consulta", "")), top_k=top_k)
        return json.dumps(
            [{"documento_id": r.trecho.documento_id, "pagina": r.trecho.pagina, "score": r.score, "texto": r.trecho.texto} for r in res],
            ensure_ascii=False,
        )
    if nome == "ler_pagina":
        texto = indice.ler_pagina(str(entrada.get("documento_id")), int(entrada.get("pagina", 0)))
        return texto if texto is not None else "ERRO: documento ou página inexistente."
    if nome == "registrar_requisito":
        atributo = str(entrada.get("atributo"))
        if atributo not in ATRIBUTOS:
            return f"ERRO: atributo '{atributo}' não é canônico. Use um dos: {', '.join(ATRIBUTOS)}"
        if entrada.get("valor_numero") is not None:
            bruto: Any = entrada["valor_numero"]
        elif entrada.get("valor_booleano") is not None:
            bruto = entrada["valor_booleano"]
        else:
            bruto = entrada.get("valor_texto")
        if bruto is None:
            return "ERRO: informe valor_numero, valor_texto ou valor_booleano."
        valor, motivo = normalizar_valor(atributo, bruto)
        if valor is None:
            # Volta para o agente corrigir (ex.: garantia em anos, prazo em dias), em vez de entrar errado
            return f"ERRO: valor inválido para {atributo} ({motivo}). Registre o valor normalizado na unidade {ATRIBUTOS[atributo].get('unidade') or 'canônica'}."
        ev = ctx.nova_evidencia(str(entrada.get("documento_id")), int(entrada.get("pagina") or 0) or None, str(entrada.get("trecho_literal", "")))
        achados.append(
            Requisito(
                id=ctx.novo_id("req"),
                item_id="*",
                atributo=atributo,
                operador=Operador(entrada.get("operador", ATRIBUTOS[atributo]["operador_padrao"])),
                valor=valor,
                unidade=ATRIBUTOS[atributo].get("unidade"),
                obrigatorio=atributo not in _NAO_BLOQUEANTES,
                texto_origem=str(entrada.get("trecho_literal", "")),
                evidencia_id=ev.id,
                fonte_extracao="investigador",
            )
        )
        return f"OK: {atributo} registrado com evidência {ev.id}."
    if nome == "concluir_investigacao":
        return "OK"
    return f"ERRO: ferramenta desconhecida '{nome}'"


def investigar_llm(ctx: Contexto, faltantes: list[str]) -> list[Requisito]:
    """Loop de uso de ferramentas, independente do provedor (ver llm.client.Conversa)."""
    achados: list[Requisito] = []
    alvo = "\n".join(f"- {a} ({rotulo(a)}): termos sugeridos: {', '.join(ATRIBUTOS_INVESTIGAVEIS.get(a, [rotulo(a)]))}" for a in faltantes)
    objeto = ctx.analise.contratacao.objeto
    conversa = ctx.llm.conversa(ctx.cfg.model_agente, SYSTEM_INVESTIGADOR, FERRAMENTAS)
    resposta = conversa.enviar(
        f"Contratação: {ctx.analise.contratacao.id} — objeto: {objeto}\n\n"
        f"Informações a localizar nos documentos:\n{alvo}\n\n"
        "Comece listando os documentos e buscando cada informação. Registre só o que encontrar com evidência."
    )
    passos = 1
    while True:
        if resposta.texto:
            ctx.analise.passos_investigacao.append({"passo": passos, "tipo": "raciocinio", "texto": resposta.texto})
        if resposta.parada == "recusa":
            ctx.evento("investigador", "Modelo recusou continuar; encerrando investigação.")
            break
        if not resposta.chamadas:
            break
        resultados: list[tuple[str, str, bool]] = []
        concluiu = False
        for chamada in resposta.chamadas:
            saida = _executar_ferramenta(ctx, chamada.nome, chamada.entrada, achados)
            ctx.analise.passos_investigacao.append(
                {"passo": passos, "tipo": "ferramenta", "ferramenta": chamada.nome, "entrada": chamada.entrada, "saida": saida[:600]}
            )
            ctx.evento("investigador", f"Passo {passos}: {chamada.nome}({json.dumps(chamada.entrada, ensure_ascii=False, default=str)[:120]})")
            resultados.append((chamada.id, saida, saida.startswith("ERRO")))
            concluiu |= chamada.nome == "concluir_investigacao"
        if concluiu:
            break
        if passos >= ctx.cfg.max_passos_investigador:
            ctx.evento("investigador", f"Limite de {ctx.cfg.max_passos_investigador} passos atingido; encerrando com o que foi registrado.")
            break
        if ctx.llm.excedeu_orcamento():
            ctx.evento("investigador", "Orçamento de tokens excedido; encerrando investigação.")
            break
        restantes = ctx.cfg.max_passos_investigador - passos
        if restantes <= 2:
            # Aviso dentro do resultado da última ferramenta: o modelo precisa registrar o que já achou
            cid, saida, erro = resultados[-1]
            resultados[-1] = (cid, saida + f"\n\n[AVISO DO SISTEMA] Restam {restantes} passo(s). Registre agora, com registrar_requisito, tudo o que já localizou e chame concluir_investigacao.", erro)
        resposta = conversa.responder_ferramentas(resultados)
        passos += 1
    return achados


# ---------------------------------------------------------------------------
# Contingência determinística
# ---------------------------------------------------------------------------

# Padrões tolerantes a redação de edital ("30 (trinta) dias", "garantia mínima dos produtos é de 5 (cinco) anos").
# O texto de PDF tem quebras de linha no meio das frases, por isso [^.;] em vez de [^.;\n].
_PADROES_DIRETOS = {
    "prazo_entrega_dias": [
        r"PRAZO\s*(?:MAXIMO\s*)?(?:DE|PARA)\s*(?:A\s*)?ENTREGA[^.;]{0,80}?(\d{1,3})\s*\(?[A-Z ]*\)?\s*(DIAS)",
        r"ENTREG\w+[^.;]{0,80}?(?:PRAZO|EM\s*ATE|NO\s*PRAZO\s*DE|ATE)\s*(\d{1,3})\s*\(?[A-Z ]*\)?\s*(DIAS)",
        r"(\d{1,3})\s*\(?[A-Z ]*\)?\s*(DIAS)[^.;]{0,60}?(?:PARA|DE)\s*(?:A\s*)?ENTREGA",
    ],
    "garantia_anos": [
        r"GARANTIA[^.;]{0,70}?(\d{1,2})\s*\(?[A-Z ]*\)?\s*(ANOS?|MESES)",
        r"(\d{1,2})\s*\(?[A-Z ]*\)?\s*(ANOS?|MESES)[^.;]{0,40}?GARANTIA",
    ],
}

# Exigências documentais/operacionais encontradas no edital entram como DESEJÁVEIS: não bloqueiam a
# compatibilidade técnica do produto, mas aparecem no dossiê (PARCIAL quando faltam).
_NAO_BLOQUEANTES = {"doc_amostra", "doc_ensaios", "doc_termo_garantia", "doc_curva_ies", "doc_registro_inmetro", "prazo_entrega_dias"}


def investigar_regras(ctx: Contexto, faltantes: list[str]) -> list[Requisito]:
    from obranexo.rules.extrair import _sem_acentos

    achados: list[Requisito] = []
    for atributo in faltantes:
        termos = ATRIBUTOS_INVESTIGAVEIS.get(atributo, [rotulo(atributo)])
        encontrado = False
        for termo in termos:
            # Sem LLM não há julgamento de relevância: varre todos os trechos com o termo e aplica os padrões
            resultados = [r for r in ctx.indice.buscar(termo, top_k=60) if not r.trecho.documento_id.startswith("pncp-item")]
            ctx.analise.passos_investigacao.append(
                {"passo": len(ctx.analise.passos_investigacao) + 1, "tipo": "ferramenta", "ferramenta": "buscar_trechos",
                 "entrada": {"consulta": termo, "top_k": 60}, "saida": f"{len(resultados)} trecho(s)"}
            )
            ctx.evento("investigador", f"[regras] buscar_trechos('{termo}') → {len(resultados)} trecho(s)", atributo=atributo)
            for r in resultados:
                texto_up = _sem_acentos(r.trecho.texto).upper()
                valor: Any = None
                trecho_ev = ""
                if atributo in _PADROES_DIRETOS:
                    for padrao in _PADROES_DIRETOS[atributo]:
                        m = re.search(padrao, texto_up)
                        if m:
                            valor = numero_br(m.group(1))
                            if valor is not None and m.lastindex and m.lastindex >= 2 and m.group(2).startswith("MES"):
                                valor = valor / 12
                            trecho_ev = r.trecho.texto[max(0, m.start() - 10) : m.end() + 10]
                            break
                elif atributo == "doc_amostra":
                    m = re.search(r"AMOSTRA", texto_up)
                    if m and re.search(r"DEVER|APRESENT|EXIG|ENTREG", texto_up):
                        valor, trecho_ev = True, r.trecho.texto[max(0, m.start() - 80) : m.end() + 120]
                else:
                    for bruto in extrair_requisitos(r.trecho.texto):
                        if bruto.atributo == atributo:
                            valor, trecho_ev = bruto.valor, bruto.texto_origem
                            break
                if valor is None:
                    continue
                ev = ctx.nova_evidencia(r.trecho.documento_id, r.trecho.pagina, trecho_ev)
                achados.append(
                    Requisito(
                        id=ctx.novo_id("req"),
                        item_id="*",
                        atributo=atributo,
                        operador=Operador(ATRIBUTOS[atributo]["operador_padrao"]),
                        valor=valor,
                        unidade=ATRIBUTOS[atributo].get("unidade"),
                        obrigatorio=atributo not in _NAO_BLOQUEANTES,
                        texto_origem=trecho_ev,
                        evidencia_id=ev.id,
                        fonte_extracao="investigador",
                    )
                )
                ctx.analise.passos_investigacao.append(
                    {"passo": len(ctx.analise.passos_investigacao) + 1, "tipo": "ferramenta", "ferramenta": "registrar_requisito",
                     "entrada": {"atributo": atributo, "valor": valor, "documento_id": r.trecho.documento_id, "pagina": r.trecho.pagina},
                     "saida": f"OK: evidência {ev.id} — “{trecho_ev[:120]}”"}
                )
                ctx.evento("investigador", f"[regras] {rotulo(atributo)} localizado em {r.trecho.documento_id} p.{r.trecho.pagina}", atributo=atributo)
                encontrado = True
                break
            if encontrado:
                break
        if not encontrado:
            ctx.analise.lacunas.append(f"{rotulo(atributo)}: não localizado nos documentos disponíveis (termos buscados: {', '.join(termos)}).")
    return achados


def investigar(ctx: Contexto, faltantes: list[str]) -> list[Requisito]:
    if not faltantes:
        return []
    ctx.evento("investigador", f"Investigando {len(faltantes)} informação(ões) ausente(s): {', '.join(rotulo(a) for a in faltantes)}")
    achados: list[Requisito] = []
    if ctx.usar_llm:
        try:
            achados = investigar_llm(ctx, faltantes)
        except Exception as exc:
            ctx.evento("investigador", f"Investigador LLM falhou ({exc}); usando contingência por regras.")
    # O que o agente não registrou passa pela varredura por regras (cobre limite de passos e omissões)
    restantes = [a for a in faltantes if a not in {r.atributo for r in achados}]
    if restantes:
        if achados or ctx.usar_llm:
            ctx.evento("investigador", f"Contingência por regras para {len(restantes)} informação(ões): {', '.join(rotulo(a) for a in restantes)}")
        achados += investigar_regras(ctx, restantes)
    return achados


def evidencias_de(ctx: Contexto, requisitos: list[Requisito]) -> list[Evidencia]:
    ids = {r.evidencia_id for r in requisitos}
    return [e for e in ctx.analise.evidencias if e.id in ids]
