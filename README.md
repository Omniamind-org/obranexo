# ObraNexo

Plataforma de inteligência comercial agêntica: transforma contratações públicas (PNCP) em
oportunidades **tecnicamente verificáveis** para fornecedores de materiais elétricos.
MVP v0.1 para o AKCIT Camp Multicêntrico 2026.

- Documento norteador: `ObraNexo_PreProjeto_Documento_Norteador_v0.1.pdf`
- Roadmap do MVP: `ROADMAP_MVP.txt`
- Fluxo dos agentes: `docs/fluxo_agentes.md`

## O que a v0.1 faz

1. Carrega o catálogo do fornecedor (demo em `data/catalogo_demo/produtos.json`, ou upload CSV/XLSX/JSON).
2. Busca contratações no PNCP (ou usa os **casos reais congelados** em `data/casos/`).
3. Extrai texto dos editais com número de página e lê cada item da contratação.
4. Extrai requisitos técnicos (regras determinísticas + LLM opcional).
5. Compara requisito a requisito com o catálogo por um **motor de regras** (sem LLM).
6. O **Agente Investigador** procura no edital o que faltava (garantia, prazo de entrega, amostra…).
7. O **Agente Verificador** confere cada citação no documento, detecta conflitos e marca o que precisa de revisão humana.
8. Classifica a oportunidade (publicada / planejada / indireta), prioriza e gera o **dossiê comercial** com evidências e próximos passos.

Sem chave de API, tudo roda em modo determinístico. Com uma chave, os agentes de linguagem complementam a
extração, a investigação, a verificação e o plano. Provedores suportados (SDKs oficiais):

| Provedor | Chave no `.env` | Modelos padrão | Observação |
|---|---|---|---|
| **Google Gemini** (padrão do MVP) | `GEMINI_API_KEY` | agentes `gemini-3.8-flash` → reserva `gemini-3.5-flash-lite`; extração `gemini-3.5-flash-lite` | nível gratuito da API Gemini Developer; o cliente cai para o reserva em 429/503 e põe o modelo em quarentena por 10 min |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` / `claude-haiku-5-5` | `OBRANEXO_LLM_PROVIDER=anthropic` |

Os três recursos usados pelos agentes — texto, saída estruturada validada por Pydantic e chamada de ferramentas —
têm a mesma interface nos dois provedores (`src/obranexo/llm/client.py`). Testes de integração que chamam a API
de verdade: `pytest -m integracao -v`.

## Instalação

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env     # preencha GEMINI_API_KEY (ou ANTHROPIC_API_KEY)
```

## Uso

```powershell
# API + interface web (abre em http://127.0.0.1:8000 · documentação dos endpoints em /api/docs)
obranexo servidor
obranexo servidor --reload      # desenvolvimento: recarrega ao editar o código Python

# Linha de comando
obranexo casos
obranexo analisar goianira_pe038_2026
obranexo buscar --uf GO --dias 30 --palavras "lumin,led"
obranexo abertas --uf GO
obranexo coletar 01291707000167 2026 75 meu_caso

# Testes e benchmark
pytest -m "not integracao"      # unitários + API, sem chamar o LLM
pytest -m integracao -v         # chama o provedor de LLM configurado
python eval/run_benchmark.py
```

## Arquitetura da aplicação

```
navegador ──► web/ (HTML + CSS + JavaScript puro, ES modules, sem build)
                │  fetch / Server-Sent Events
                ▼
             FastAPI  src/obranexo/api/main.py  ──►  pipeline de agentes (thread em segundo plano)
                │                                     │
                ▼                                     ▼
       data/casos (PNCP congelado)         data/analises (JSON) · data/llm_cache
```

O frontend não tem dependências externas nem etapa de build: o próprio FastAPI serve a pasta `web/`,
e a demo funciona offline. Rotas da interface (hash): `#/inicio`, `#/catalogo`, `#/demandas`,
`#/casos/<caso>`, `#/analises`, `#/analises/<id>`, `#/metricas`, `#/sobre`.

### Endpoints

| Método | Rota | Para quê |
|---|---|---|
| GET | `/api/status` | versão, provedor/modelos de LLM, modo offline, contadores |
| GET · POST · DELETE | `/api/catalogo` | catálogo ativo · enviar JSON/CSV/XLSX (multipart `arquivo`) · restaurar o demo |
| GET | `/api/casos` · `/api/casos/{caso}` | casos congelados · itens, anexos e análises de um caso |
| GET | `/api/pncp/buscar?uf&palavras&abertas&dias&max_paginas` | busca ao vivo no PNCP |
| POST | `/api/pncp/coletar` | `{cnpj, ano, sequencial, max_mb}` → baixa e congela uma contratação |
| POST | `/api/analises` | `{caso}` → inicia a análise em segundo plano (202, devolve o job) |
| GET | `/api/jobs/{id}` · `/api/jobs/{id}/eventos` | estado do job · stream SSE (`log` a cada passo, `fim` com `analise_id`) |
| GET | `/api/analises` · `/api/analises/{id}` | histórico resumido · análise completa + rótulos + produtos |
| GET | `/api/analises/{id}/dossie.md[?download=true]` | dossiê em Markdown |
| PATCH | `/api/analises/{id}/revisao` | `{status: PENDENTE\|APROVADO\|REJEITADO, comentario}` |
| GET | `/api/analises/{id}/evidencias/{ev}` | trecho citado + texto da página de origem |
| GET | `/api/analises/{id}/documentos/{doc}/arquivo` | PDF original (abre na página com `#page=N`) |
| GET | `/api/metricas` · `/api/conteudo/fluxo` | agregados + benchmark · documentação do fluxo |

## Casos reais congelados (dados públicos do PNCP, coletados em 22/10/2026)

| Pasta | Contratação | O que demonstra |
|---|---|---|
| `goianira_pe038_2026` | Goianira/GO — PE 038/2026 — RP de luminárias LED (R$ 1,67 mi) | COMPATÍVEL, INCOMPATÍVEL e INDETERMINADO com evidências no edital |
| `aruana_pp005_2026` | Aruanã/GO — PP 005/2026 — luminárias LED 50/100/150 W (R$ 1,42 mi) | exigência de 170 lm/W derruba produtos comuns |
| `seinfra_basileu_franca_2026` | Estado de Goiás — Concorrência 02/2026 — obra da EFG Basileu França (R$ 31,98 mi) | classificação INDIRETA (o comprador é a construtora) e varredura de insumos elétricos nos projetos; dos 100 anexos, só edital, TR, ETP, orçamento e projeto elétrico foram congelados — os demais ficam listados sem download |

## Estrutura

```
src/obranexo/
  connectors/pncp.py     conector PNCP (cache, retentativas, pacotes congelados)
  documents/extract.py   PDF -> páginas -> trechos; busca textual
  catalog/               atributos canônicos, loader (JSON/CSV/XLSX)
  rules/extrair.py       extração determinística de requisitos (pt-BR)
  rules/compare.py       motor de regras de compatibilidade
  llm/client.py          clientes Gemini e Anthropic (interface única, cache, custo, fallback)
  agents/                extrator, investigador, verificador, planejador, pipeline
  evidence/verify.py     verificação literal das citações
  dossier/render.py      dossiê em Markdown
  storage/store.py       persistência JSON (v0.2: PostgreSQL)
  api/main.py            API FastAPI (endpoints acima) + servidor estático do frontend
  api/jobs.py            execução das análises em segundo plano com eventos SSE
web/
  index.html             casca da aplicação
  css/app.css            design system (tokens, tema claro/escuro, responsivo)
  js/app.js              roteador por hash
  js/api.js              cliente da API (fetch + SSE com fallback para polling)
  js/ui.js · format.js   template com escape, ícones, modal, toasts, badges · formatação pt-BR
  js/markdown.js         renderizador Markdown seguro (dossiê e documentação)
  js/views/              início, catálogo, demandas, caso (execução ao vivo), análises, resultado, métricas, sobre
eval/run_benchmark.py    benchmark contra gabaritos
tests/                   pytest
```

## Equipe

Kauan Divino · Fabrycio Nakano · Victor Emanuel · Maykon Adriell
