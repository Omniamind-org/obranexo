"""Assistente conversacional: o usuário pergunta o que procura e o agente responde com dados reais.

Cada mensagem do usuário vira um loop de ferramentas (PNCP ao vivo, catálogo, análises salvas e, se pedido,
a análise completa). O texto da resposta cita licitações como [[id]] e análises como [[analise:id]]; a
interface transforma essas marcas em links e cartões a partir das `referencias` montadas aqui, só com
ids que as ferramentas realmente devolveram.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime
from typing import Any

from obranexo import contas
from obranexo.agents.prompts import SYSTEM_ASSISTENTE, VERSAO
from obranexo.agents.prospector import _compacto, _resumo_catalogo, melhor_por_item, partes_id, resumir_analise
from obranexo.config import Config, config
from obranexo.connectors.pncp import MODALIDADES_LICITACAO, PNCPClient, PNCPError, carregar_caso, listar_casos
from obranexo.documents.extract import normalizar_busca
from obranexo.llm.client import LLMIndisponivel, criar_llm_client
from obranexo.models import Analise, Contratacao, Empresa, EventoLog, UsoLLM
from obranexo.observability import logs
from obranexo.observability.trilha import escopo
from obranexo.rules.extrair import eh_acessorio, inferir_categoria
from obranexo.storage import chat, store

MAX_RODADAS = 8  # chamadas de ferramenta por mensagem do usuário
MAX_PAGINAS_POR_MODALIDADE = 12

FERRAMENTAS: list[dict[str, Any]] = [
    {
        "name": "buscar_licitacoes_abertas",
        "description": "Licitações (pregões, concorrências e dispensas) com propostas ABERTAS no PNCP numa UF, cujo objeto contenha algum dos termos. "
        "Devolve o total e até 20 resultados (id, órgão, município, objeto, valor estimado, encerramento), maiores primeiro.",
        "input_schema": {
            "type": "object",
            "properties": {
                "uf": {"type": "string", "description": "Sigla da UF, ex.: GO"},
                "termos": {"type": "array", "items": {"type": "string"}, "description": "Radicais para o objeto, ex.: ['lumin', 'ilumina']"},
                "encerra_em_dias": {"type": "integer", "description": "Só propostas que encerram nos próximos N dias (3 a 90; padrão 30)"},
            },
            "required": ["uf", "termos"],
        },
    },
    {
        "name": "ver_itens",
        "description": "Itens de uma licitação (número, descrição, quantidade, valor unitário), com a categoria provável de cada "
        "um e se essa categoria existe no catálogo do fornecedor.",
        "input_schema": {
            "type": "object",
            "properties": {"contratacao_id": {"type": "string", "description": "id da licitação, ex.: 01291707000167-1-000075/2026"}},
            "required": ["contratacao_id"],
        },
    },
    {
        "name": "consultar_catalogo",
        "description": "Produtos do catálogo do fornecedor que contêm o termo no nome, descrição ou categoria (vazio = resumo de todos).",
        "input_schema": {
            "type": "object",
            "properties": {"termo": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "analises_salvas",
        "description": "Análises técnicas já feitas (a mais recente de cada licitação): órgão, município, contagem de itens por "
        "resultado, prioridade e prazo. Filtra pelo termo no órgão, município ou objeto (vazio = todas).",
        "input_schema": {
            "type": "object",
            "properties": {"termo": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "detalhar_analise",
        "description": "Detalhe de uma análise salva: resultado item a item (com o produto do catálogo), valor dos itens atendidos, "
        "riscos e próximos passos.",
        "input_schema": {
            "type": "object",
            "properties": {"analise_id": {"type": "string"}},
            "required": ["analise_id"],
        },
    },
    {
        "name": "analisar_a_fundo",
        "description": "Análise técnica completa de uma licitação (baixa edital e anexos, compara cada exigência com o catálogo, "
        "verifica as citações). Leva cerca de 1 minuto. Só use se o usuário pediu ou confirmou.",
        "input_schema": {
            "type": "object",
            "properties": {"contratacao_id": {"type": "string"}},
            "required": ["contratacao_id"],
        },
    },
]

_RE_LICITACAO = re.compile(r"\[\[\s*(\d{14}-\d+-\d+/\d{4})\s*\]\]")
_RE_ANALISE = re.compile(r"\[\[\s*analise:\s*([\w-]+)\s*\]\]")


class Assistente:
    """Uma conversa. Guarda o histórico do LLM (com os resultados de ferramenta) e o que já foi visto."""

    def __init__(self, empresa: Empresa, cfg: Config | None = None):
        self.cfg = cfg or config
        self.empresa = empresa
        self.empresa_id = contas.empresa_ativa()  # a conta dona da conversa
        self.id = uuid.uuid4().hex[:12]
        self.criado_em = datetime.now()
        self.uso = UsoLLM()
        self.llm = criar_llm_client(self.cfg, self.uso)
        self.pncp = PNCPClient()
        self.mensagens: list[dict[str, Any]] = []  # o que a interface mostra
        self._conversa = None
        self._lock = threading.Lock()
        self._abertas: dict[tuple[str, int], list[Contratacao]] = {}
        self._vistas: dict[str, dict[str, Any]] = {}  # licitações devolvidas pelas ferramentas
        self._analises_vistas: set[str] = set()
        self._foco: list[str] = []  # licitações abertas a fundo no turno atual (itens, análise)
        self._on_evento = None

    # ------------------------------------------------------------------ apoio

    def _evento(self, no: str, mensagem: str) -> None:
        if self._on_evento:
            self._on_evento(EventoLog(no=no, mensagem=mensagem))

    def _system(self) -> str:
        e = self.empresa
        return (
            f"{SYSTEM_ASSISTENTE}\n\nHoje: {datetime.now():%d/%m/%Y}. Fornecedor: {e.nome}. "
            f"UFs atendidas: {', '.join(e.ufs_atendidas) or 'não informadas (use GO)'}.\n"
            f"CATÁLOGO (categorias e exemplos):\n{_resumo_catalogo(e)}"
        )

    def _registrar(self, c: Contratacao) -> dict[str, Any]:
        d = _compacto(c)
        self._vistas[c.id] = {
            **d,
            "encerra_iso": c.data_encerramento_proposta.isoformat() if c.data_encerramento_proposta else None,
            "link_oficial": c.link_oficial,
        }
        return d

    # ------------------------------------------------------------------ ferramentas

    def _abertas_uf(self, uf: str, dias: int) -> list[Contratacao]:
        chave = (uf, dias)
        if chave not in self._abertas:
            def progresso(_modalidade: int, posicao: int, n: int, pagina: int, total: int) -> None:
                if total > 1 or n > 1:
                    self._evento("buscar", f"Lendo as licitações abertas em {uf} no PNCP (modalidade {posicao} de {n}, página {pagina} de {total})")

            res = self.pncp.buscar_todas(uf, MODALIDADES_LICITACAO, dias=dias, max_paginas=MAX_PAGINAS_POR_MODALIDADE,
                                         progresso=progresso, tolerante=True)
            self._abertas[chave] = res.contratacoes
        return self._abertas[chave]

    def buscar(self, uf: str, termos: list[str], dias: int | None) -> str:
        uf = (uf or "").strip().upper()[:2]
        if not re.fullmatch(r"[A-Z]{2}", uf):
            return "ERRO: informe a sigla da UF (ex.: GO)."
        dias = max(3, min(90, int(dias or 30)))
        termos_norm = [normalizar_busca(t) for t in termos if t and len(t.strip()) >= 3]
        if not termos_norm:
            return "ERRO: informe ao menos um termo com 3 letras ou mais."
        self._evento("buscar", f"Buscando no PNCP em {uf}: {', '.join(termos)}")
        achados = [c for c in self._abertas_uf(uf, dias) if any(t in normalizar_busca(c.objeto) for t in termos_norm)]
        achados.sort(key=lambda c: c.valor_estimado or 0, reverse=True)
        self._evento("buscar", f"{len(achados)} licitação(ões) aberta(s) em {uf} com esses termos")
        return json.dumps({"uf": uf, "encerra_em_ate_dias": dias, "total": len(achados),
                           "resultados": [self._registrar(c) for c in achados[:20]]}, ensure_ascii=False)

    def ver_itens(self, contratacao_id: str) -> str:
        try:
            cnpj, ano, seq = partes_id(contratacao_id)
        except ValueError as exc:
            return f"ERRO: {exc}"
        self._evento("ver_itens", f"Lendo os itens de {contratacao_id}")
        self._foco.append(contratacao_id)
        if contratacao_id not in self._vistas:
            try:
                self._registrar(self.pncp.detalhe(cnpj, ano, seq))
            except PNCPError:
                pass
        itens = self.pncp.itens(cnpj, ano, seq, contratacao_id)
        categorias = self.empresa.categorias()
        # Se a licitação já foi analisada, o resultado técnico de cada item vale mais que a triagem por categoria
        feita = next((a for a in self._ultimas_analises() if a.contratacao.id == contratacao_id), None)
        resultado_por_n: dict[int, str] = {}
        if feita:
            melhor = melhor_por_item(feita)
            resultado_por_n = {i.numero_item: melhor.get(i.id, "FORA_DO_PORTFOLIO") for i in feita.itens}
        saida = []
        for i in itens[:60]:
            cat = "outro" if eh_acessorio(i.descricao) else inferir_categoria(i.descricao)
            linha = {"n": i.numero_item, "descricao": i.descricao[:120], "qtd": i.quantidade, "unidade": i.unidade,
                     "valor_unit": i.valor_unit_estimado, "categoria": cat, "categoria_no_catalogo": cat in categorias}
            if feita:
                linha["resultado_da_analise"] = resultado_por_n.get(i.numero_item, "NAO_ANALISADO")
            saida.append(linha)
        no_cat = sum(1 for s in saida if s["categoria_no_catalogo"])
        # O resumo vem antes da lista: a saída da ferramenta é truncada e o que importa não pode ficar no fim
        resposta: dict[str, Any] = {
            "aviso": "categoria_no_catalogo indica só que o fornecedor vende esse TIPO de produto; as especificações não foram comparadas.",
            "total_itens": len(itens), "itens_de_categorias_do_catalogo": no_cat,
        }
        if feita:
            self._analises_vistas.add(feita.id)
            resposta["analise_existente"] = {k: v for k, v in resumir_analise(feita).items() if k != "resumo_executivo"}
            # Todos os itens (a lista abaixo corta em 60): o que a análise confirmou, com a descrição curta
            atendidos = [{"n": i.numero_item, "descricao": i.descricao[:90], "resultado": resultado_por_n[i.numero_item]}
                         for i in feita.itens if resultado_por_n.get(i.numero_item) in ("COMPATIVEL", "PARCIAL")]
            resposta["analise_existente"]["itens_atendidos"] = atendidos[:40]
            resposta["analise_existente"]["itens_incompativeis"] = [i.numero_item for i in feita.itens if resultado_por_n.get(i.numero_item) == "INCOMPATIVEL"][:60]
            resposta["aviso"] = ("Esta licitação JÁ FOI ANALISADA: analise_existente é a verificação técnica "
                                 "(COMPATIVEL/PARCIAL = atende total/parcialmente; INCOMPATIVEL = não atende; INDETERMINADO = não confirmado). "
                                 f"Responda por ela, cite a análise como [[analise:{feita.id}]] e não ofereça analisar de novo.")
        resposta["itens"] = saida if len(itens) <= 60 else saida + [{"aviso": f"lista cortada: mais {len(itens) - 60} itens"}]
        return json.dumps(resposta, ensure_ascii=False)

    def consultar_catalogo(self, termo: str) -> str:
        t = normalizar_busca(termo or "")
        produtos = [p for p in self.empresa.produtos if not t or t in normalizar_busca(f"{p.nome} {p.descricao} {p.categoria} {p.sku}")]
        return json.dumps({"total": len(produtos), "produtos": [
            {"sku": p.sku, "nome": p.nome, "categoria": p.categoria, "preco_ref": p.preco_ref,
             "atributos": {k: v.valor for k, v in list(p.atributos.items())[:8]}}
            for p in produtos[:25]]}, ensure_ascii=False)

    def _ultimas_analises(self) -> list[Analise]:
        vistas, saida = set(), []
        for a in store.listar():
            if a.status == "concluida" and a.contratacao.id not in vistas:
                vistas.add(a.contratacao.id)
                saida.append(a)
        return saida

    def analises_salvas(self, termo: str) -> str:
        t = normalizar_busca(termo or "")
        lista = [a for a in self._ultimas_analises()
                 if not t or t in normalizar_busca(f"{a.contratacao.orgao_nome} {a.contratacao.municipio} {a.contratacao.objeto}")]
        saida = []
        for a in lista[:15]:
            r = resumir_analise(a)
            self._analises_vistas.add(a.id)
            saida.append({**self._registrar(a.contratacao), "analise_id": a.id, "analisada_em": f"{a.iniciada_em:%d/%m/%Y}",
                          **{k: r[k] for k in ("itens", "compativeis", "parciais", "indeterminados", "incompativeis", "fora_do_portfolio", "valor_compativel", "prioridade")}})
        return json.dumps({"total": len(lista), "analises": saida}, ensure_ascii=False)

    def detalhar_analise(self, analise_id: str) -> str:
        a = store.carregar(analise_id.strip())
        if a is None or a.status != "concluida":
            return "ERRO: análise não encontrada (use um analise_id devolvido por analises_salvas)."
        self._analises_vistas.add(a.id)
        self._registrar(a.contratacao)
        self._foco.append(a.contratacao.id)
        melhor = melhor_por_item(a)
        skus = {p.id: p.sku for p in self.empresa.produtos}
        produto_item: dict[str, str] = {}
        for c in a.correspondencias:
            if c.resultado.value == melhor.get(c.item_id):
                produto_item.setdefault(c.item_id, skus.get(c.produto_id, c.produto_id))
        q = a.qualificacao
        return json.dumps({
            **resumir_analise(a),
            "contratacao_id": a.contratacao.id,
            "itens_detalhe": [{"n": i.numero_item, "descricao": i.descricao[:120], "resultado": melhor.get(i.id, "FORA_DO_PORTFOLIO"),
                               "produto": produto_item.get(i.id)} for i in a.itens[:60]],
            "riscos": (q.riscos if q else [])[:6],
            "proximos_passos": (q.proximos_passos if q else [])[:6],
            "pendencias": len(a.lacunas) + len(a.conflitos),
        }, ensure_ascii=False)

    def analisar(self, contratacao_id: str) -> str:
        try:
            cnpj, ano, seq = partes_id(contratacao_id)
        except ValueError as exc:
            return f"ERRO: {exc}"
        from obranexo.agents.pipeline import executar_caso

        destino = self.cfg.dir_casos / f"{cnpj}_{ano}_{seq}"
        self._evento("analisar", f"Baixando o edital e os anexos de {contratacao_id}")
        if not (destino / "contratacao.json").exists():
            self.pncp.coletar_caso(cnpj, ano, seq, destino, max_mb=15)

        def repassar(ev: EventoLog) -> None:
            if ev.no in {"coletar_documentos", "extrair_itens", "casar_com_catalogo", "investigador", "verificador", "gerar_dossie"}:
                self._evento("analisar", ev.mensagem[:160])

        analise = executar_caso(destino, self.empresa, cfg=self.cfg, on_evento=repassar)
        if analise.status != "concluida":
            return f"ERRO: a análise falhou ({analise.erro})."
        self._analises_vistas.add(analise.id)
        self._registrar(analise.contratacao)
        self._foco.append(analise.contratacao.id)
        return json.dumps(resumir_analise(analise), ensure_ascii=False)

    def _executar(self, nome: str, entrada: dict[str, Any]) -> str:
        try:
            if nome == "buscar_licitacoes_abertas":
                return self.buscar(str(entrada.get("uf", "")), list(entrada.get("termos") or []), entrada.get("encerra_em_dias"))
            if nome == "ver_itens":
                return self.ver_itens(str(entrada.get("contratacao_id", "")))
            if nome == "consultar_catalogo":
                return self.consultar_catalogo(str(entrada.get("termo") or ""))
            if nome == "analises_salvas":
                return self.analises_salvas(str(entrada.get("termo") or ""))
            if nome == "detalhar_analise":
                return self.detalhar_analise(str(entrada.get("analise_id", "")))
            if nome == "analisar_a_fundo":
                return self.analisar(str(entrada.get("contratacao_id", "")))
        except PNCPError as exc:
            self._evento("erro", f"PNCP indisponível: {str(exc)[:120]}")
            return f"ERRO: o PNCP não respondeu ({str(exc)[:200]}). Avise o usuário e sugira tentar de novo em instantes."
        except (TypeError, ValueError) as exc:
            return f"ERRO: parâmetros inválidos ({exc})."
        return f"ERRO: ferramenta desconhecida '{nome}'"

    # ------------------------------------------------------------------ referências para a interface

    def _referencias(self, texto: str) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        casos = _casos_locais()
        analises = {a.contratacao.id: a for a in self._ultimas_analises()} if (_RE_LICITACAO.search(texto) or _RE_ANALISE.search(texto)) else {}
        vistos: set[str] = set()
        # Marcas no texto primeiro; depois as licitações que o assistente abriu neste turno e não marcou
        ids = list(dict.fromkeys(_RE_LICITACAO.findall(texto) + [c for c in self._foco if c in self._vistas][:3]))
        if self._foco and not analises:
            analises = {a.contratacao.id: a for a in self._ultimas_analises()}
        for cid in ids:
            if cid in vistos or cid not in self._vistas:
                continue
            vistos.add(cid)
            a = analises.get(cid)
            cnpj, ano, seq = partes_id(cid)
            refs.append({"tipo": "licitacao", **self._vistas[cid], "cnpj": cnpj, "ano": ano, "sequencial": seq,
                         "caso": casos.get(cid), "analise_id": a.id if a else None,
                         "resultados": _contagem(a) if a else None, "prioridade": a.qualificacao.prioridade if a and a.qualificacao else None})
        for aid in _RE_ANALISE.findall(texto):
            if aid in vistos or aid not in self._analises_vistas:
                continue
            vistos.add(aid)
            a = store.carregar(aid)
            if a is None or a.contratacao.id in vistos:
                continue  # a licitação já tem cartão (com o botão da análise)
            vistos.add(a.contratacao.id)
            refs.append({"tipo": "analise", "analise_id": a.id, "id": a.contratacao.id, "orgao": a.contratacao.orgao_nome,
                         "municipio": f"{a.contratacao.municipio}/{a.contratacao.uf}", "objeto": a.contratacao.objeto[:220],
                         "valor_estimado": a.contratacao.valor_estimado, "link_oficial": a.contratacao.link_oficial,
                         "encerra_iso": a.contratacao.data_encerramento_proposta.isoformat() if a.contratacao.data_encerramento_proposta else None,
                         "resultados": _contagem(a), "prioridade": a.qualificacao.prioridade if a.qualificacao else None})
        return refs

    # ------------------------------------------------------------------ conversa

    def _contexto_anterior(self) -> str:
        """Se o histórico do LLM se perdeu (erro do provedor), resume as últimas trocas para não perder o fio."""
        trocas = [f"{'Usuário' if m['papel'] == 'usuario' else 'Assistente'}: {m['texto'][:500]}" for m in self.mensagens[-8:]]
        return "Conversa até aqui (resumo):\n" + "\n".join(trocas) + "\n\nNova mensagem do usuário:\n" if trocas else ""

    def responder(self, texto: str, on_evento=None) -> dict[str, Any]:
        with self._lock:
            self._on_evento = on_evento
            try:
                return self._responder(texto.strip()[:4000])
            finally:
                self._on_evento = None

    def _responder(self, texto: str) -> dict[str, Any]:
        with escopo(agente="assistente", versao_prompt=VERSAO, origem_tipo="chat", origem_id=self.id):
            return self._responder_no_escopo(texto)

    def _responder_no_escopo(self, texto: str) -> dict[str, Any]:
        if not self.llm.disponivel:
            raise RuntimeError("o assistente precisa de um provedor de IA configurado")
        entrada = texto
        if self._conversa is None:
            entrada = self._contexto_anterior() + texto
            self._conversa = self.llm.conversa(self.cfg.model_agente, self._system(), FERRAMENTAS)
        self._guardar({"papel": "usuario", "texto": texto, "ts": datetime.now().isoformat()})
        passos: list[str] = []
        self._foco = []
        try:
            resposta = self._conversa.enviar(entrada)
            rodadas = 0
            while resposta.chamadas and rodadas < MAX_RODADAS:
                resultados = []
                for ch in resposta.chamadas:
                    saida = self._executar(ch.nome, ch.entrada)
                    passos.append(ch.nome)
                    resultados.append((ch.id, saida[:12000], saida.startswith("ERRO")))
                rodadas += 1
                if rodadas == MAX_RODADAS:
                    cid, saida, erro = resultados[-1]
                    resultados[-1] = (cid, saida + "\n\n[AVISO DO SISTEMA] Limite de consultas desta mensagem: responda agora com o que já tem.", erro)
                self._evento("pensando", "Organizando a resposta")
                resposta = self._conversa.responder_ferramentas(resultados)
            final = (resposta.texto or "").strip()
            if not final:
                final = "Não consegui montar uma resposta agora. Pode reformular ou tentar de novo?"
        except LLMIndisponivel as exc:
            self._conversa = None  # o histórico do provedor ficou incompleto; o próximo turno recomeça com resumo
            final = f"O provedor de IA não respondeu agora ({str(exc)[:160]}). Tente de novo em instantes ou troque o provedor no topo da página."
        msg = {"papel": "assistente", "texto": final, "referencias": self._referencias(final), "ferramentas": passos,
               "ts": datetime.now().isoformat()}
        self._guardar(msg)
        return msg

    def _guardar(self, mensagem: dict[str, Any]) -> None:
        """Acrescenta à conversa e persiste (storage/chat.py); falha de disco não interrompe a resposta."""
        self.mensagens.append(mensagem)
        try:
            chat.salvar_mensagem(self.id, self.empresa.nome, len(self.mensagens) - 1, mensagem)
        except Exception as exc:
            logs.registrar("chat_nao_persistido", sessao_id=self.id, erro=f"{type(exc).__name__}: {exc}")

    @classmethod
    def restaurar(cls, sessao_id: str, empresa: Empresa, cfg: Config | None = None) -> Assistente | None:
        """Reconstrói uma conversa persistida (após reinício do servidor). O próximo turno parte do resumo das
        últimas mensagens, porque o histórico no formato do provedor não é guardado."""
        mensagens = chat.carregar(sessao_id)
        if not mensagens:
            return None
        a = cls(empresa, cfg)
        a.id = sessao_id
        a.mensagens = mensagens
        return a


def _contagem(a: Analise) -> dict[str, int]:
    melhor = melhor_por_item(a)
    r = {k: 0 for k in ("COMPATIVEL", "PARCIAL", "INDETERMINADO", "INCOMPATIVEL")}
    for v in melhor.values():
        r[v] += 1
    r["FORA_DO_PORTFOLIO"] = len(a.itens) - len(melhor)
    return r


def _casos_locais() -> dict[str, str]:
    mapa: dict[str, str] = {}
    for d in listar_casos():
        try:
            c, _, _ = carregar_caso(d)
            mapa[c.id] = d.name
        except Exception:
            continue
    return mapa


class Sessoes:
    """Conversas ativas em memória; as mensagens ficam no SQLite (storage/chat.py), por isso uma conversa
    sobrevive ao reinício do servidor: `obter` a reconstrói quando não está mais em memória."""

    MAX = 50

    def __init__(self) -> None:
        self._s: dict[str, Assistente] = {}
        self._lock = threading.Lock()

    def criar(self, empresa: Empresa) -> Assistente:
        return self._registrar(Assistente(empresa))

    def obter(self, sessao_id: str, empresa: Empresa | None = None) -> Assistente | None:
        """A conversa, se for da empresa ativa."""
        a = self._s.get(sessao_id)
        if a is not None and a.empresa_id != contas.empresa_ativa():
            return None
        if a is None and empresa is not None:
            a = Assistente.restaurar(sessao_id, empresa)
            if a is not None:
                self._registrar(a)
        return a

    def _registrar(self, a: Assistente) -> Assistente:
        with self._lock:
            self._s[a.id] = a
            while len(self._s) > self.MAX:
                self._s.pop(next(iter(self._s)))
        return a


sessoes = Sessoes()
