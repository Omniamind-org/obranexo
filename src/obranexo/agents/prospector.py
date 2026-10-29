"""Agente de Prospecção: encontra, sozinho, as licitações abertas que valem a pena para o fornecedor.

O LLM conduz o processo com ferramentas reais:
  buscar_licitacoes_abertas -> ver_itens -> analisar_a_fundo (pipeline completo) -> concluir
Ele decide os termos de busca a partir do catálogo, quais licitações abrir, quais analisar a fundo
(cada análise custa chamadas) e produz um ranking justificado. Nada é roteirizado: a ordem e as
escolhas são do agente, dentro de limites de passos e de análises.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from datetime import datetime
from typing import Any

from obranexo.agents.prompts import SYSTEM_PROSPECTOR, VERSAO
from obranexo.config import Config, config
from obranexo.connectors.pncp import MODALIDADES_LICITACAO, PNCPClient, PNCPError, carregar_caso
from obranexo.documents.extract import normalizar_busca
from obranexo.llm.client import criar_llm_client
from obranexo.models import Analise, CandidatoProspeccao, Contratacao, Empresa, EventoLog, ItemRanking, Prospeccao
from obranexo.observability.trilha import escopo
from obranexo.storage import store

MAX_PASSOS = 16
MAX_PAGINAS_POR_MODALIDADE = 12  # 50 por página: cobre as ~400-600 licitações abertas de um estado em cada modalidade

FERRAMENTAS: list[dict[str, Any]] = [
    {
        "name": "buscar_licitacoes_abertas",
        "description": "Busca no PNCP licitações (pregões, concorrências e dispensas) com propostas ABERTAS numa UF, cujo objeto contenha algum dos termos. "
        "Devolve até 30 resultados (id, órgão, município, objeto, valor estimado, data de encerramento).",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "uf": {"type": "string", "description": "Sigla da UF, ex.: GO"},
                "termos": {"type": "array", "items": {"type": "string"}, "description": "Palavras ou radicais para o objeto, ex.: ['lumin', 'ilumina', 'material eletric']"},
            },
            "required": ["uf", "termos"],
            "additionalProperties": False,
        },
    },
    {
        "name": "ver_itens",
        "description": "Lista os itens de uma licitação (número, descrição, quantidade, valor unitário) direto do PNCP.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"contratacao_id": {"type": "string", "description": "numeroControlePNCP, ex.: 01291707000167-1-000075/2026"}},
            "required": ["contratacao_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "analisar_a_fundo",
        "description": "Baixa edital e anexos e roda a análise técnica completa (extração, motor de regras, Investigador, "
        "Verificador, dossiê). Caro: use só nas licitações mais promissoras. Devolve o resultado por item e a prioridade.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "contratacao_id": {"type": "string"},
                "motivo": {"type": "string", "description": "Por que esta licitação merece análise completa"},
            },
            "required": ["contratacao_id", "motivo"],
            "additionalProperties": False,
        },
    },
    {
        "name": "concluir",
        "description": "Encerra a prospecção com o ranking das oportunidades consideradas (melhor primeiro) e um resumo para o gestor.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "ranking": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "contratacao_id": {"type": "string"},
                            "nota": {"type": "number", "description": "0 a 100: aderência ao catálogo, valor, prazo e confiança"},
                            "justificativa": {"type": "string"},
                        },
                        "required": ["contratacao_id", "nota", "justificativa"],
                        "additionalProperties": False,
                    },
                },
                "resumo": {"type": "string"},
            },
            "required": ["ranking", "resumo"],
            "additionalProperties": False,
        },
    },
]


def partes_id(contratacao_id: str) -> tuple[str, int, int]:
    """'01291707000167-1-000075/2026' -> ('01291707000167', 2026, 75)"""
    m = re.fullmatch(r"\s*(\d{14})-\d+-(\d+)/(\d{4})\s*", contratacao_id)
    if not m:
        raise ValueError(f"id de contratação inválido: {contratacao_id!r}")
    return m.group(1), int(m.group(3)), int(m.group(2))


def melhor_por_item(analise: Analise) -> dict[str, str]:
    """Melhor resultado de cada item entre os produtos do catálogo (itens sem correspondência ficam de fora)."""
    melhor: dict[str, str] = {}
    ordem = {"COMPATIVEL": 3, "PARCIAL": 2, "INDETERMINADO": 1, "INCOMPATIVEL": 0}
    for c in sorted(analise.correspondencias, key=lambda c: (ordem[c.resultado.value], c.score), reverse=True):
        melhor.setdefault(c.item_id, c.resultado.value)
    return melhor


def resumir_analise(analise: Analise) -> dict[str, Any]:
    """Números de uma análise concluída, no formato que os agentes recebem como resultado de ferramenta."""
    melhor = melhor_por_item(analise)
    contagem = Counter(melhor.values())
    valor_compat = sum((i.quantidade or 0) * (i.valor_unit_estimado or 0) for i in analise.itens if melhor.get(i.id) in ("COMPATIVEL", "PARCIAL"))
    q = analise.qualificacao
    return {
        "analise_id": analise.id,
        "itens": len(analise.itens),
        "compativeis": contagem.get("COMPATIVEL", 0),
        "parciais": contagem.get("PARCIAL", 0),
        "indeterminados": contagem.get("INDETERMINADO", 0),
        "incompativeis": contagem.get("INCOMPATIVEL", 0),
        "fora_do_portfolio": len(analise.itens) - len(melhor),
        "valor_compativel": round(valor_compat, 2),
        "tipo": q.tipo_oportunidade.value if q else None,
        "prazo": q.prazo_status if q else None,
        "prioridade": q.prioridade if q else None,
        "resumo_executivo": (analise.dossie.resumo_executivo[:600] if analise.dossie else ""),
    }


def _resumo_catalogo(empresa: Empresa) -> str:
    por_cat: dict[str, list[str]] = {}
    for p in empresa.produtos:
        a = {k: v.valor for k, v in p.atributos.items()}
        specs = ", ".join(f"{k}={a[k]}" for k in ("potencia_w", "cct_k", "ip", "secao_mm2", "corrente_a") if k in a)
        por_cat.setdefault(p.categoria, []).append(f"{p.nome}" + (f" ({specs})" if specs else ""))
    linhas = [f"- {cat} ({len(lst)} produtos): " + "; ".join(lst[:5]) + (" …" if len(lst) > 5 else "") for cat, lst in sorted(por_cat.items())]
    return "\n".join(linhas)


def _compacto(c: Contratacao) -> dict[str, Any]:
    return {
        "id": c.id,
        "orgao": c.orgao_nome,
        "municipio": f"{c.municipio}/{c.uf}",
        "modalidade": c.modalidade,
        "objeto": c.objeto[:220],
        "valor_estimado": c.valor_estimado,
        "encerra": c.data_encerramento_proposta.strftime("%d/%m/%Y") if c.data_encerramento_proposta else None,
    }


class Prospector:
    def __init__(self, empresa: Empresa, ufs: list[str], horizonte_dias: int, max_analises: int,
                 cfg: Config | None = None, on_evento=None, modalidades: tuple[int, ...] | list[int] = MODALIDADES_LICITACAO):
        self.cfg = cfg or config
        self.empresa = empresa
        self.ufs = [u.upper() for u in ufs] or ["GO"]
        self.horizonte_dias = horizonte_dias
        self.max_analises = max_analises
        self.modalidades = list(modalidades)
        self.on_evento = on_evento
        self.p = Prospeccao(
            id=f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}",
            empresa_id=empresa.id,
            empresa_nome=empresa.nome,
            parametros={"ufs": self.ufs, "horizonte_dias": horizonte_dias, "max_analises": max_analises, "modalidades": self.modalidades},
        )
        self.llm = criar_llm_client(self.cfg, self.p.uso_llm)
        self.pncp = PNCPClient()
        self._abertas: dict[str, list[Contratacao]] = {}
        self._por_id: dict[str, Contratacao] = {}
        self._analises_feitas = 0
        self._avisado_contradicao = False
        self._erros_pncp: list[str] = []

    # ------------------------------------------------------------------ eventos

    def evento(self, no: str, mensagem: str, **dados) -> None:
        ev = EventoLog(no=no, mensagem=mensagem, dados=dados)
        self.p.log.append(ev)
        if self.on_evento:
            self.on_evento(ev)

    # ------------------------------------------------------------------ ferramentas

    def _abertas_uf(self, uf: str) -> list[Contratacao]:
        if uf not in self._abertas:
            # Uma página que falha não para a prospecção; sem nenhuma página não há o que buscar (o erro sobe)
            res = self.pncp.buscar_todas(uf, self.modalidades, dias=self.horizonte_dias, max_paginas=MAX_PAGINAS_POR_MODALIDADE, tolerante=True)
            for falha in res.falhas:
                self.evento("buscar", f"PNCP falhou em {falha}; seguindo com as licitações já obtidas")
            lista = res.contratacoes
            self._abertas[uf] = lista
            for c in lista:
                self._por_id[c.id] = c
            por_modalidade = Counter(c.modalidade or "?" for c in lista)
            detalhe = ", ".join(f"{n} {m}" for m, n in por_modalidade.most_common())
            self.evento("buscar", f"PNCP: {len(lista)} licitações com propostas abertas em {uf} (próximos {self.horizonte_dias} dias)"
                        + (f": {detalhe}" if detalhe else ""))
            if self.pncp.aviso:
                self.evento("buscar", self.pncp.aviso)
                self.pncp.aviso = None
        return self._abertas[uf]

    def buscar(self, uf: str, termos: list[str]) -> str:
        uf = (uf or "").upper()[:2]
        if uf not in self.ufs:
            return f"ERRO: UF {uf} fora das regiões da prospecção ({', '.join(self.ufs)})."
        termos_norm = [normalizar_busca(t) for t in termos if t and len(t.strip()) >= 3]
        if not termos_norm:
            return "ERRO: informe ao menos um termo com 3 letras ou mais."
        achados = [c for c in self._abertas_uf(uf) if any(t in normalizar_busca(c.objeto) for t in termos_norm)]
        achados.sort(key=lambda c: c.valor_estimado or 0, reverse=True)
        self.p.buscas.append({"uf": uf, "termos": termos, "resultados": len(achados)})
        for c in achados[:30]:
            self.p.candidatos.setdefault(c.id, CandidatoProspeccao(contratacao=_compacto(c)))
        self.evento("buscar", f"Termos {termos} em {uf}: {len(achados)} licitação(ões) com objeto compatível")
        return json.dumps({"total": len(achados), "resultados": [_compacto(c) for c in achados[:30]]}, ensure_ascii=False)

    def ver_itens(self, contratacao_id: str) -> str:
        try:
            cnpj, ano, seq = partes_id(contratacao_id)
        except ValueError as exc:
            return f"ERRO: {exc}"
        itens = self.pncp.itens(cnpj, ano, seq, contratacao_id)
        cand = self.p.candidatos.get(contratacao_id)
        if cand:
            cand.itens_vistos = True
        self.evento("ver_itens", f"{contratacao_id}: {len(itens)} item(ns)")
        return json.dumps(
            [{"n": i.numero_item, "descricao": i.descricao[:200], "qtd": i.quantidade, "unidade": i.unidade, "valor_unit": i.valor_unit_estimado} for i in itens[:60]],
            ensure_ascii=False,
        )

    def analisar(self, contratacao_id: str, motivo: str) -> str:
        if self._analises_feitas >= self.max_analises:
            return f"ERRO: limite de {self.max_analises} análise(s) completa(s) atingido. Conclua com o que já tem."
        try:
            cnpj, ano, seq = partes_id(contratacao_id)
        except ValueError as exc:
            return f"ERRO: {exc}"
        from obranexo.agents.pipeline import executar_caso

        destino = store.dir_casos() / f"{cnpj}_{ano}_{seq}"
        self.evento("analisar", f"Análise completa de {contratacao_id} — {motivo[:140]}")
        if not (destino / "contratacao.json").exists():
            self.pncp.coletar_caso(cnpj, ano, seq, destino, max_mb=15)
        self._analises_feitas += 1

        def repassar(ev: EventoLog) -> None:
            if ev.no in {"carregar_contexto", "investigador", "verificador", "qualificar", "gerar_dossie", "erro"}:
                self.evento(f"↳ {ev.no}", ev.mensagem)

        analise = executar_caso(destino, self.empresa, cfg=self.cfg, on_evento=repassar)
        if analise.status != "concluida":
            return f"ERRO: a análise falhou ({analise.erro})."
        resumo = resumir_analise(analise)
        if contratacao_id not in self.p.candidatos:
            c, _, _ = carregar_caso(destino)
            self.p.candidatos[contratacao_id] = CandidatoProspeccao(contratacao=_compacto(c))
        self.p.candidatos[contratacao_id].analise_id = analise.id
        self.p.candidatos[contratacao_id].resumo_analise = resumo
        self.evento("analisar", f"{contratacao_id}: {resumo['compativeis']} compatível(is), {resumo['parciais']} parcial(is) · prioridade {resumo['prioridade']}")
        return json.dumps(resumo, ensure_ascii=False)

    NOTA_MAX_SEM_ADERENCIA = 35.0

    def concluir(self, ranking: list[dict[str, Any]], resumo: str) -> str:
        # A análise completa é a verdade técnica: nota alta para o que ela reprovou volta para o agente revisar
        contradicoes = []
        for r in ranking:
            cand = self.p.candidatos.get(str(r.get("contratacao_id", "")).strip())
            ra = cand.resumo_analise if cand else None
            if ra and ra["compativeis"] + ra["parciais"] == 0 and float(r.get("nota") or 0) > self.NOTA_MAX_SEM_ADERENCIA:
                contradicoes.append(f"{r['contratacao_id']}: nota {r.get('nota')}, mas a análise completa encontrou 0 compatíveis e 0 parciais "
                                    f"({ra['indeterminados']} indeterminados, {ra['incompativeis']} incompatíveis, {ra['fora_do_portfolio']} fora do portfólio)")
        if contradicoes and not self._avisado_contradicao:
            self._avisado_contradicao = True
            return ("ERRO: o ranking contradiz as análises completas, que são a verificação técnica:\n- " + "\n- ".join(contradicoes)
                    + f"\nItens indeterminados significam especificação não confirmada, não aderência. Revise as notas "
                    f"(no máximo {self.NOTA_MAX_SEM_ADERENCIA:.0f} sem itens compatíveis/parciais) e as justificativas, e chame concluir de novo.")
        itens = []
        for r in ranking:
            cid = str(r.get("contratacao_id", "")).strip()
            cand = self.p.candidatos.get(cid)
            if cand is None:
                continue  # só entra no ranking o que o agente realmente encontrou
            nota = max(0.0, min(100.0, float(r.get("nota") or 0)))
            justificativa = str(r.get("justificativa", ""))[:800]
            ra = cand.resumo_analise
            if ra and ra["compativeis"] + ra["parciais"] == 0 and nota > self.NOTA_MAX_SEM_ADERENCIA:
                nota = self.NOTA_MAX_SEM_ADERENCIA
                justificativa += " [Nota limitada pelo sistema: a análise completa não confirmou nenhum item compatível ou parcial.]"
            itens.append(ItemRanking(contratacao_id=cid, nota=nota, justificativa=justificativa, analise_id=cand.analise_id, contratacao=cand.contratacao))
        itens.sort(key=lambda x: x.nota, reverse=True)
        self.p.ranking = itens
        self.p.resumo = resumo
        return "OK"

    def _executar(self, nome: str, entrada: dict[str, Any]) -> str:
        try:
            if nome == "buscar_licitacoes_abertas":
                return self.buscar(str(entrada.get("uf", "")), list(entrada.get("termos") or []))
            if nome == "ver_itens":
                return self.ver_itens(str(entrada.get("contratacao_id", "")))
            if nome == "analisar_a_fundo":
                return self.analisar(str(entrada.get("contratacao_id", "")), str(entrada.get("motivo", "")))
            if nome == "concluir":
                return self.concluir(list(entrada.get("ranking") or []), str(entrada.get("resumo", "")))
        except PNCPError as exc:
            self._erros_pncp.append(str(exc)[:200])
            return f"ERRO: PNCP indisponível ({exc}). Tente outra licitação ou conclua."
        return f"ERRO: ferramenta desconhecida '{nome}'"

    # ------------------------------------------------------------------ loop

    def executar(self) -> Prospeccao:
        # As chamadas de modelo da prospecção (e das análises que ela dispara) ficam ligadas a ela na trilha
        with escopo(agente="prospector", versao_prompt=VERSAO, origem_tipo="prospeccao", origem_id=self.p.id):
            return self._loop()

    def _loop(self) -> Prospeccao:
        try:
            if not self.llm.disponivel:
                raise RuntimeError("a prospecção autônoma exige um provedor de LLM configurado (GEMINI_API_KEY, GROQ_API_KEY ou ANTHROPIC_API_KEY)")
            self.evento("inicio", f"Prospecção para {self.empresa.nome} em {', '.join(self.ufs)} · até {self.max_analises} análise(s) completa(s)")
            tarefa = (
                f"Fornecedor: {self.empresa.nome}. UFs da prospecção: {', '.join(self.ufs)}. "
                f"Propostas encerrando nos próximos {self.horizonte_dias} dias. Data de hoje: {datetime.now():%d/%m/%Y}.\n"
                f"Você pode fazer até {self.max_analises} análise(s) completa(s) com analisar_a_fundo.\n\n"
                f"CATÁLOGO DO FORNECEDOR (categorias e produtos):\n{_resumo_catalogo(self.empresa)}\n\n"
                "Encontre as licitações abertas em que este fornecedor tem mais chance real de vender. Comece buscando."
            )
            conversa = self.llm.conversa(self.cfg.model_agente, SYSTEM_PROSPECTOR, FERRAMENTAS)
            resposta = conversa.enviar(tarefa)
            passos, concluiu = 1, False
            while True:
                if resposta.texto:
                    self.p.passos.append({"passo": passos, "tipo": "raciocinio", "texto": resposta.texto})
                    self.evento("raciocinio", resposta.texto[:300])
                if resposta.parada == "recusa" or not resposta.chamadas:
                    break
                resultados = []
                for ch in resposta.chamadas:
                    saida = self._executar(ch.nome, ch.entrada)
                    self.p.passos.append({"passo": passos, "tipo": "ferramenta", "ferramenta": ch.nome, "entrada": ch.entrada, "saida": saida[:800]})
                    if ch.nome not in {"buscar_licitacoes_abertas", "analisar_a_fundo", "ver_itens"}:
                        self.evento(ch.nome, json.dumps(ch.entrada, ensure_ascii=False, default=str)[:200])
                    resultados.append((ch.id, saida, saida.startswith("ERRO")))
                    concluiu |= ch.nome == "concluir" and not saida.startswith("ERRO")
                if concluiu or passos >= MAX_PASSOS:
                    break
                if MAX_PASSOS - passos <= 2:
                    cid, saida, erro = resultados[-1]
                    resultados[-1] = (cid, saida + f"\n\n[AVISO DO SISTEMA] Restam {MAX_PASSOS - passos} passo(s). Chame concluir agora com o ranking.", erro)
                resposta = conversa.responder_ferramentas(resultados)
                passos += 1
            if not concluiu:
                self._ranking_de_contingencia()
            if not self.p.buscas and self._erros_pncp:
                # Nenhuma busca chegou a acontecer: não é "nada encontrado", é falha da fonte
                raise RuntimeError(f"o PNCP recusou as consultas ({self._erros_pncp[0]}). Tente de novo em alguns minutos.")
            self.p.status = "concluida"
            self.evento("fim", f"Ranking com {len(self.p.ranking)} oportunidade(s) · {self.p.uso_llm.chamadas} chamada(s) ao LLM")
        except Exception as exc:
            self.p.status = "erro"
            self.p.erro = f"{type(exc).__name__}: {exc}"
            self.evento("erro", self.p.erro)
        self.p.finalizada_em = datetime.now()
        store.salvar_prospeccao(self.p)
        return self.p

    def _ranking_de_contingencia(self) -> None:
        """O agente não concluiu (limite de passos ou recusa): ranqueia o que foi analisado pela prioridade calculada."""
        itens = []
        for cid, cand in self.p.candidatos.items():
            if cand.resumo_analise:
                itens.append(ItemRanking(contratacao_id=cid, nota=float(cand.resumo_analise.get("prioridade") or 0),
                                         justificativa="Ranking automático pela prioridade da análise (o agente não concluiu).",
                                         analise_id=cand.analise_id, contratacao=cand.contratacao))
        itens.sort(key=lambda x: x.nota, reverse=True)
        self.p.ranking = itens
        self.p.resumo = self.p.resumo or "O agente encerrou sem concluir; o ranking abaixo usa a prioridade das análises completas."
        self.evento("fim", "Agente não concluiu dentro do limite de passos; ranking de contingência pela prioridade das análises.")


def executar_prospeccao(empresa: Empresa, ufs: list[str], horizonte_dias: int = 30, max_analises: int = 2,
                        cfg: Config | None = None, on_evento=None,
                        modalidades: tuple[int, ...] | list[int] = MODALIDADES_LICITACAO) -> Prospeccao:
    return Prospector(empresa, ufs, horizonte_dias, max_analises, cfg=cfg, on_evento=on_evento, modalidades=modalidades).executar()
