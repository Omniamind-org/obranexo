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
from obranexo.agents.prompts import SYSTEM_INVESTIGADOR, VERSAO
from obranexo.catalog.atributos import ATRIBUTOS, ATRIBUTOS_INVESTIGAVEIS, natureza, rotulo
from obranexo.evidence.verify import verificar_evidencia
from obranexo.models import Evidencia, ItemDemanda, Operador, Requisito
from obranexo.observability.trilha import escopo
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
                "numero_item": {"type": "integer", "description": "Número do item a que o requisito se refere; 0 = exigência geral do edital, vale para todos os itens"},
                "atributo": {"type": "string", "description": "Chave canônica, ex.: potencia_w, ip, garantia_anos, prazo_entrega_dias, doc_amostra"},
                "operador": {"type": "string", "enum": ["=", ">=", "<=", "entre", "contem", "verdadeiro"]},
                "valor_numero": {"type": ["number", "null"]},
                "valor_texto": {"type": ["string", "null"]},
                "valor_booleano": {"type": ["boolean", "null"]},
                "documento_id": {"type": "string"},
                "pagina": {"type": "integer"},
                "trecho_literal": {"type": "string", "description": "Cópia EXATA do trecho do documento (é conferida automaticamente)"},
            },
            "required": ["numero_item", "atributo", "operador", "valor_numero", "valor_texto", "valor_booleano", "documento_id", "pagina", "trecho_literal"],
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
        numero_item = int(entrada.get("numero_item") or 0)
        item = next((i for i in ctx.analise.itens if i.numero_item == numero_item), None) if numero_item else None
        if numero_item and item is None:
            return f"ERRO: não existe item {numero_item} nesta contratação. Itens: {', '.join(str(i.numero_item) for i in ctx.analise.itens)}."
        documento_id = str(entrada.get("documento_id"))
        if documento_id not in ctx.indice.paginas:
            return f"ERRO: documento '{documento_id}' não existe ou não tem texto. Use listar_documentos."
        trecho = str(entrada.get("trecho_literal", "")).strip()
        ev = ctx.nova_evidencia(documento_id, int(entrada.get("pagina") or 0) or None, trecho)
        # A citação é conferida NA HORA: o que não estiver literalmente no documento não vira requisito
        verificar_evidencia(ev, ctx.indice)
        if not ev.verificada:
            ctx.analise.evidencias.remove(ev)
            return (f"ERRO: o trecho_literal não foi encontrado no documento {documento_id} (similaridade {ev.score_match}). "
                    "Copie o trecho exatamente como aparece em buscar_trechos ou ler_pagina, sem reescrever.")
        tecnico = natureza(atributo) == "produto" and atributo not in _NAO_BLOQUEANTES and atributo not in ATRIBUTOS_INVESTIGAVEIS
        achados.append(
            Requisito(
                id=ctx.novo_id("req"),
                item_id=item.id if item else "*",
                atributo=atributo,
                operador=Operador(entrada.get("operador", ATRIBUTOS[atributo]["operador_padrao"])),
                valor=valor,
                unidade=ATRIBUTOS[atributo].get("unidade"),
                # Especificação técnica de um item, com citação conferida no TR, é exigência de verdade
                obrigatorio=(tecnico and item is not None) or (atributo not in _NAO_BLOQUEANTES and not tecnico),
                texto_origem=trecho,
                evidencia_id=ev.id,
                fonte_extracao="investigador",
            )
        )
        alvo = f"item {numero_item}" if item else "todos os itens"
        return f"OK: {atributo} registrado para {alvo}, evidência {ev.id} conferida (p.{ev.pagina})."
    if nome == "concluir_investigacao":
        return "OK"
    return f"ERRO: ferramenta desconhecida '{nome}'"


def _tarefa(ctx: Contexto, faltantes: list[str], itens_sem_spec: list[ItemDemanda]) -> str:
    partes = [f"Contratação: {ctx.analise.contratacao.id} — objeto: {ctx.analise.contratacao.objeto}"]
    if itens_sem_spec:
        linhas = "\n".join(f'- item {i.numero_item} ({i.categoria_inferida}): "{i.descricao[:220]}"' for i in itens_sem_spec)
        partes.append(
            "TAREFA 1 — Estes itens têm descrição curta ou sem especificação técnica no PNCP. Encontre no Termo de "
            "Referência / edital a especificação de cada um (potência, tensão, fluxo, temperatura de cor, IP, seção, "
            "corrente, etc.) e registre cada atributo com numero_item do item correspondente:\n" + linhas
        )
    if faltantes:
        linhas = "\n".join(f"- {a} ({rotulo(a)}): termos sugeridos: {', '.join(ATRIBUTOS_INVESTIGAVEIS.get(a, [rotulo(a)]))}" for a in faltantes)
        partes.append("TAREFA 2 — Exigências gerais do edital (registre com numero_item = 0):\n" + linhas)
    partes.append("Comece listando os documentos. Registre só o que encontrar, com o trecho copiado exatamente.")
    return "\n\n".join(partes)


def investigar_llm(ctx: Contexto, faltantes: list[str], itens_sem_spec: list[ItemDemanda] | None = None) -> list[Requisito]:
    """Loop de uso de ferramentas, independente do provedor (ver llm.client.Conversa)."""
    with escopo(agente="investigador", versao_prompt=VERSAO):
        return _investigar_llm(ctx, faltantes, itens_sem_spec)


def _investigar_llm(ctx: Contexto, faltantes: list[str], itens_sem_spec: list[ItemDemanda] | None = None) -> list[Requisito]:
    itens_sem_spec = itens_sem_spec or []
    achados: list[Requisito] = []
    # Cada item a especificar costuma exigir uma busca e um ou dois registros
    limite = min(ctx.cfg.max_passos_investigador + 2 * len(itens_sem_spec), 24)
    # Orçamento próprio do Investigador: não disputa com a extração dos itens
    inicio_tokens = ctx.llm.tokens_usados()
    conversa = ctx.llm.conversa(ctx.cfg.model_agente, SYSTEM_INVESTIGADOR, FERRAMENTAS)
    resposta = conversa.enviar(_tarefa(ctx, faltantes, itens_sem_spec))
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
        if passos >= limite:
            ctx.evento("investigador", f"Limite de {limite} passos atingido; encerrando com o que foi registrado.")
            break
        if ctx.llm.excedeu_orcamento(desde=inicio_tokens, limite=ctx.cfg.orcamento_tokens):
            ctx.evento("investigador", "Orçamento de tokens do Investigador excedido; encerrando investigação.")
            break
        restantes = limite - passos
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


def investigar(ctx: Contexto, faltantes: list[str], itens_sem_spec: list[ItemDemanda] | None = None) -> list[Requisito]:
    itens_sem_spec = itens_sem_spec if ctx.usar_llm else []  # especificar itens no TR exige leitura (LLM)
    if not faltantes and not itens_sem_spec:
        return []
    alvo = [rotulo(a) for a in faltantes] + [f"especificação do item {i.numero_item}" for i in itens_sem_spec]
    ctx.evento("investigador", f"Investigando {len(alvo)} pendência(s): {', '.join(alvo)}")
    achados: list[Requisito] = []
    if ctx.usar_llm:
        try:
            achados = investigar_llm(ctx, faltantes, itens_sem_spec)
        except Exception as exc:
            ctx.evento("investigador", f"Investigador LLM falhou ({exc}); usando contingência por regras.")
    for item in itens_sem_spec:
        if not any(r.item_id == item.id for r in achados):
            ctx.analise.lacunas.append(f"Item {item.numero_item}: a especificação técnica não foi localizada nos documentos (descrição do PNCP sem detalhes).")
    # O que o agente não registrou passa pela varredura por regras (cobre limite de passos e omissões)
    restantes = [a for a in faltantes if a not in {r.atributo for r in achados if r.item_id == "*"}]
    if restantes:
        if achados or ctx.usar_llm:
            ctx.evento("investigador", f"Contingência por regras para {len(restantes)} informação(ões): {', '.join(rotulo(a) for a in restantes)}")
        achados += investigar_regras(ctx, restantes)
    return achados


def evidencias_de(ctx: Contexto, requisitos: list[Requisito]) -> list[Evidencia]:
    ids = {r.evidencia_id for r in requisitos}
    return [e for e in ctx.analise.evidencias if e.id in ids]
