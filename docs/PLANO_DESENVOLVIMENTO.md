# Plano de desenvolvimento — ObraNexo

Versão 1.1 · 24/10/2026 · alinhado ao [README](../README.md) (cada item abaixo corresponde a um selo ⬜ ou 🟡 de lá; os marcados ✅ foram concluídos no próprio dia 24/10, branch `feat/observabilidade`).

**Como usar.** O plano está organizado por fase e por pacote de trabalho (PT). Cada PT tem objetivo, tarefas no nível de arquivo, critério de aceite verificável e dependências. A ordem dentro de cada fase é a ordem sugerida de execução. Um PT só está pronto quando cumpre a **Definição de Pronto** do fim do documento. Datas depois de 28/11/2026 são propostas e devem ser revistas no fim de cada fase.

**Invariantes** (não mudam em nenhuma fase):

1. A IA interpreta, investiga e planeja; **o motor de regras decide a compatibilidade**.
2. Toda conclusão aponta para um trecho literal conferido no documento; sem prova, **INDETERMINADO**.
3. Todo valor proposto por um modelo passa pela validação de tipo e faixa.
4. Nenhum agente tem ferramenta de ação externa (não envia proposta, não dá lance).
5. Documentos entram como dados, nunca como instruções.
6. A decisão final é humana e fica registrada.
7. Sem chave de API, o núcleo roda em modo determinístico; a demo e os testes nunca dependem de cota de terceiros.

---

## F1 · v0.2 — MVP robusto (25/10 → 28/11/2026)

**Objetivo:** confiabilidade e primeira prova de valor. **Critério de saída:** roda na nuvem com PostgreSQL; benchmark com ≥ 10 contratações rotuladas por duas pessoas; ≥ 1 piloto com fornecedor real.

### PT-1.1 · Correções da auditoria (semana 1)

Defeitos encontrados em 24/10 que afetam resultado ou credibilidade. Pequenos, independentes, alto retorno. Os itens **c, f, g e i** foram concluídos ainda em 24/10 (120 testes passando; benchmark 100%); restam a, b, d, e, h.

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Busca em todas as modalidades relevantes: parâmetro `modalidades: list[int]` em `buscar_publicacoes` e `buscar_propostas_abertas`; padrão `[6, 7, 4, 5, 8]` (pregão eletrônico e presencial, concorrência eletrônica e presencial, dispensa); UI e ferramentas do Prospector e do Assistente expõem o filtro | `connectors/pncp.py`, `api/main.py` (`/api/pncp/buscar`), `agents/prospector.py`, `agents/assistente.py`, `web/js/views/demandas.js` | teste com resposta gravada por modalidade; `obranexo abertas --uf GO --modalidades 4,6` devolve concorrências |
| b | Tela de busca lê todas as páginas: `max_paginas` deixa de ter teto 6 na UI; o backend pagina até `total_paginas` com limite de segurança 20 | `web/js/views/demandas.js`, `api/main.py` | busca em GO devolve as 9 páginas (hoje 6) |
| c | ✅ **24/10** — Reprodutibilidade: `temperature=0` em Gemini e Anthropic (já existia no Groq); a versão dos prompts (`VERSAO` em `prompts.py`, hoje `v0.3`) fica rastreável na análise (`analise.versao_prompts`, impressa no rodapé do dossiê), em cada linha da trilha de chamadas (`versao_prompt`) e em `GET /api/status`. Nota: a chave do cache em disco já é o hash do payload completo (modelo, system, prompt e esquema), então mudar o texto de um prompt invalida o cache sem precisar da versão na chave | `llm/client.py`, `agents/prompts.py`, `agents/pipeline.py`, `observability/trilha.py` | `tests/test_observabilidade.py` (escopo, agente e versão gravados por chamada) |
| d | Validação de categorias na importação de planilha: categoria fora de `CATEGORIAS` → erro 400 com sugestão (fuzzy) e lista válida; normalização de sinônimos simples ("Luminária pública" → `luminaria_publica_led`) | `catalog/loader.py`, `api/main.py` (`POST /api/catalogo`), `web/js/views/catalogo.js` | upload com categoria inválida é recusado com mensagem; teste em `tests/test_api.py` |
| e | Prioridade recalibrada: prazo ABERTO vale +35, ENCERRADO com SRP +5 e sem SRP 0; cobertura de valor 0,5; pesos em constantes nomeadas no topo de `planejador.py` | `agents/planejador.py`, `tests/test_agentes_sem_llm.py` | Itaberaí (aberta, 51%) fica acima de Goianira (encerrada, 100%); benchmark continua 100% |
| f | ✅ **24/10** — Preços reais dos modelos: tabela oficial consultada em 24/10/2026 em `PRECOS_USD` (US$ por 1M tokens: entrada, saída, leitura de cache) para Gemini, Groq (gpt-oss 120b/20b) e Anthropic, mais a faixa do Haiku 5.5 acima de 100k tokens; tokens de raciocínio lidos da resposta de cada API (`thoughts_token_count`, `reasoning_tokens`, `thinking_tokens`) e cobrados como saída; `UsoLLM` ganhou `tokens_raciocinio`, `chamadas_cache`, `chamadas_reserva`, `latencia_ms`. O custo aparece por chamada (aba Trilha do agente → Chamadas de IA), por análise e por modelo (tela Qualidade → Uso de modelos), no rodapé do dossiê e no endpoint interno `GET /api/custos` (US$ e R$, média/mediana/p95, por modelo, por dia, meta de R$ 1 por análise). É estimativa pela tabela paga: no nível gratuito do Gemini e do Groq a cobrança real é zero. O reserva do Groq passou de `llama-3.3-70b-versatile` para `openai/gpt-oss-20b` (o Llama 3.3 70B saiu do nível gratuito em 16/08/2026) | `config.py`, `models.py`, `llm/client.py`, `custos.py`, `api/main.py`, `dossier/render.py`, `web/js/views/metricas.js`, `web/js/views/resultado.js` | `tests/test_observabilidade.py` (cálculo do custo e leitura do raciocínio nos três provedores), `tests/test_custos.py` |
| g | ✅ **24/10** — Logs estruturados com a biblioteca padrão (`logging`), não `structlog`: `observability/logs.py`; uma linha por etapa do fluxo (`Contexto.evento`) e por chamada de modelo (`Trilha.gravar`), com campos fixos; JSON por linha com `OBRANEXO_LOG_JSON=1` (ver `.env.example`), senão linhas legíveis; configurado uma vez no servidor e na CLI | `observability/logs.py`, `agents/contexto.py`, `api/main.py`, `cli.py` | cada etapa e cada chamada geram uma linha parseável; coberto indiretamente por `tests/test_observabilidade.py` |
| h | ✅ Limites por licitação: paginar itens (>500) e anexos (>100) do PNCP | `connectors/pncp.py`, `tests/test_pncp_paginacao.py` | SEINFRA lista os 107 anexos (antes 100; os 7 perdidos incluíam a ata de contratação e o termo de homologação); teste com 2 páginas |
| i | ✅ Pacotes congelados portáveis: `documentos.json` gravado no Windows guardava `arquivos\x.pdf`, e em Linux/macOS nenhum anexo era lido (achado pelo CI e na instalação no macOS); leitura aceita os dois formatos e a gravação usa `/` | `connectors/pncp.py`, `tests/test_casos_portaveis.py` | os 3 jobs do CI passam em Linux; `test_fluxo_completo_de_analise` passa no macOS |
| j | ✅ **24/10** — Trilha de chamadas de modelo em SQLite (`data/obranexo.db`, tabela `chamadas_llm`): toda chamada lógica a um provedor vira uma linha com agente (por escopo `escopo(agente=...)`, um contextvar que vale também nos lotes em paralelo do Analista Técnico), origem (análise, prospecção, chat, importação), versão do prompt, operação, provedor, modelo pedido × usado, tokens de entrada/saída/raciocínio/cache, custo, latência, cache_hit, reserva, status/erro, resumo da entrada e da saída; falha na trilha nunca derruba a análise. Exposta em `GET /api/analises/{id}/chamadas` e `GET /api/metricas/llm` (custo, latência média/p95, taxas de cache/reserva/erro, por agente e por modelo) | `observability/trilha.py`, `llm/client.py`, `api/main.py`, `web/js/views/resultado.js`, `web/js/views/metricas.js` | `tests/test_observabilidade.py` (11 testes), `tests/test_grafo.py::test_api_expoe_grafo_trilha_e_metricas_de_llm` |

### PT-1.2 · Avaliação com gabarito duplo (semanas 1–3, em paralelo)

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Rotular os 5 casos cegos (133 itens) por **duas pessoas** na planilha existente; resolver divergências; registrar concordância (Cohen's kappa) | `docs/teste_cego_rotulagem.csv` → `data/casos/cego_*/gabarito.json` | kappa reportado em `docs/avaliacao.md`; 7 casos com gabarito |
| b | Coletar e rotular 3 contratações novas de outras UFs (DF, MT, TO), uma delas com TR em DOCX e uma concorrência de obra | `data/casos/` | ≥ 10 contratações, ≥ 150 pares item × produto |
| c | `run_benchmark.py` passa a calcular precisão/recall por classe, matriz de confusão e consistência (3 execuções); sai em JSON e Markdown | `eval/run_benchmark.py`, `eval/metrics.py` (novo) | `docs/avaliacao.md` gerado com as métricas-alvo do roadmap (seção 13.2) |
| d | ✅ Benchmark como trava no CI: job que roda o benchmark determinístico e falha se qualquer métrica cair abaixo do limiar definido em `eval/limiares.json` | `.github/workflows/ci.yml`, `eval/limiares.json` | PR que degrada o benchmark fica vermelho |

### PT-1.3 · PostgreSQL e persistência (semanas 2–3)

Ponto de partida em 24/10: o SQLite já existe em `data/obranexo.db`, mas guarda **só a trilha de chamadas de modelo** (`observability/trilha.py`, SQL direto, sem ORM). As mensagens do chat também já estão nele (`storage/chat.py`, item d). Análises, prospecções e catálogo seguem em JSON (`storage/store.py`); jobs, em memória. Este PT leva o restante para o banco e unifica a trilha nele.

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Modelos SQLModel: `Empresa`, `Usuario`, `Produto`, `Analise` (JSONB para o corpo + colunas de índice: contratação, status, prioridade, empresa_id), `Prospeccao`, `Conversa`, `Decisao` (seguir/descartar/comentário, quem, quando) | novo `db/models.py`, `db/session.py` | `alembic upgrade head` cria o esquema do zero |
| b | Alembic com migração inicial; `DATABASE_URL` no `.env`; SQLite continua como padrão local para desenvolvimento sem Docker (hoje `config.caminho_db`) | `alembic/`, `config.py` | testes rodam em SQLite em memória; produção em Postgres |
| c | `storage/store.py` vira repositório sobre o banco, mantendo a mesma interface (`salvar`, `carregar`, `listar`, prospecções, catálogo ativo por empresa) | `storage/store.py` | todos os testes atuais passam sem alteração nas chamadas |
| d | ✅ 24/10 — Chat persistido: mensagens em `data/obranexo.db` (`storage/chat.py`); `Sessoes.obter` reconstrói a conversa fora da memória e o próximo turno parte do resumo das últimas mensagens | `agents/assistente.py`, `storage/chat.py` | conversa sobrevive a reinício do servidor (teste em `tests/test_assistente.py`) |
| e | Script de migração dos JSONs existentes em `data/analises` e `data/prospeccoes` | `scripts/migrar_json.py` | análises antigas aparecem na interface após a migração |
| f | Trilha de chamadas (`chamadas_llm`) passa a ser um modelo SQLModel no mesmo banco, com `empresa_id`; `Trilha.gravar/listar/resumo` mantêm a interface | `observability/trilha.py`, `db/models.py` | `tests/test_observabilidade.py` passa sem alteração; `/api/metricas/llm` filtra por empresa |

### PT-1.4 · Login e isolamento por empresa (semanas 3–4)

Pré-requisito para qualquer piloto com catálogo real.

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Autenticação: e-mail + senha (argon2) com sessão por cookie assinado; convite por link; papéis `admin` e `analista` | novo `api/auth.py`, `db/models.py`, `web/js/views/login.js` | fluxo de login/logout na UI; rotas `/api/*` exigem sessão, exceto `/api/status` |
| b | Remover o estado global `_estado["empresa"]`: toda rota recebe `empresa_atual(usuario)`; catálogo, análises, prospecções e conversas filtrados por `empresa_id` | `api/main.py`, `storage/store.py` | teste: dois usuários de empresas diferentes não veem dados um do outro |
| c | Perfil da empresa editável: UFs atendidas, raio logístico, capacidade por categoria, documentos de habilitação que possui (base para o agente de Habilitação em F2) | `web/js/views/empresa.js` (novo), `models.py` (`Empresa`) | perfil salvo e usado pela qualificação (UF fora da área penaliza) |
| d | Chaves de IA por empresa (opcional) com criptografia em repouso; fallback para as chaves do servidor | `config.py`, `db/models.py` | chave da empresa nunca aparece em log nem em resposta de API |
| e | Custo em US$ sai da visão do cliente: rodapé do dossiê e tela Qualidade passam a mostrar a cota de análises do plano; o custo vai para uma tela interna que consome `GET /api/custos` | `dossier/render.py`, `web/js/views/metricas.js`, nova tela interna | cliente não vê dólar; administrador vê custo e margem |

### PT-1.5 · Docker, CI e deploy (semanas 2–4)

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | `Dockerfile` (python 3.12-slim, `uv`), `docker-compose.yml` com `app` + `postgres:16` + volume para `data/` | `Dockerfile`, `docker-compose.yml`, `.dockerignore` | `docker compose up` sobe a aplicação com banco em < 2 min |
| b | 🟡 CI no GitHub Actions: ruff, `pytest -m "not integracao"`, benchmark determinístico (PT-1.2d) ✅; build da imagem entra com o Dockerfile (PT-1.5a) | `.github/workflows/ci.yml` | badge real no README substitui o estático ✅ |
| c | Deploy em uma VM ou serviço gerenciado simples (Fly.io, Railway ou EC2 única) com HTTPS; `OBRANEXO_LLM_CACHE` e `data/` em volume persistente | `infra/` (scripts), documentação em `docs/deploy.md` | URL pública estável para o piloto; healthcheck em `/api/status` |
| d | `detect-secrets` ou `gitleaks` no pre-commit e no CI | `.pre-commit-config.yaml`, CI | commit com chave é bloqueado |

### PT-1.6 · Curador de catálogo 🟡 → ✅ (semana 4)

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Relatório de lacunas: para cada produto, quais atributos obrigatórios da categoria faltam e quantos INDETERMINADOS nas análises recentes vieram dessa lacuna | `catalog/lacunas.py` (novo), `api/main.py` (`GET /api/catalogo/lacunas`), `web/js/views/catalogo.js` | tela do catálogo mostra "3 produtos sem garantia informada → 7 itens indeterminados" |
| b | Sugestão de ficha: para produtos com lacunas, o agente busca a ficha do fabricante (URL informada ou busca por SKU/nome) e propõe o preenchimento, com revisão humana | `catalog/importar.py` | lacuna preenchida após revisão reduz os INDETERMINADOS na reexecução |

### PT-1.7 · Negócio e piloto (contínuo)

- 15–20 fornecedores de GO listados; roteiro de entrevista; **5 entrevistas** até 14/11.
- **1–2 pilotos supervisionados** com catálogo real (termo de autorização; dados isolados por PT-1.4) até 21/11.
- Cronometragem manual × assistido em 3 editais por piloto; registro das decisões seguir/descartar.
- BMC atualizado com dados reais; hipótese de preço testada.

**Sequência sugerida de F1:** semana 1 (25–31/10): PT-1.1 restante (a, b, d, e, h), PT-1.2a iniciado · semana 2 (01–07/11): PT-1.3, PT-1.5a/b, PT-1.2b/c · semana 3 (08–14/11): PT-1.4, PT-1.2d, PT-1.5c/d · semana 4 (15–21/11): PT-1.6, pilotos, deploy · semana 5 (22–28/11): congelar em 24/11, `docs/avaliacao.md`, tag `v0.2-nacional`.

---

## F2 · v0.3 — Beta fechado (dez/2026 → fev/2027)

**Objetivo:** plataforma agêntica e piloto em escala. **Critério de saída:** precisão ≥ 95% fora da amostra; rastreabilidade 100%; custo medido < R$ 1 por análise; 95% das análises em < 3 min; 10 distribuidores no piloto de 60 dias.

### PT-2.1 · Grafo durável de agentes

Ponto de partida em 24/10: o grafo já existe **como dado** (`agents/grafo.py`; `GRAFO` em `agents/pipeline.py`, 13 nós com agente, modelo, condição e campos lidos/escritos do `Contexto`), é quem executa a análise e alimenta `GET /api/conteudo/grafo` e a tela "Como funciona" (`tests/test_grafo.py`). Sem LangChain/LangGraph por decisão de projeto (ver README, "Decisões de projeto"); LangGraph entra aqui só se os checkpoints duráveis e as interrupções compensarem.

| # | Tarefa | Aceite |
|---|---|---|
| a | Checkpoints duráveis: estado do `Contexto` salvo no Postgres ao fim de cada nó do `GRAFO` (ou migração nó a nó para LangGraph, se for o caminho mais curto); estado tipado a partir de `Contexto` | análise interrompida (kill do worker) retoma do último nó concluído |
| b | Interrupções para revisão humana: antes de `analisar_a_fundo` acima de um custo estimado; quando o Verificador marca confiança baixa em item de alto valor | UI mostra "aguardando revisão" e permite continuar ou cancelar |
| c | Reexecução parcial: reexecutar só "casar_com_catalogo" após o usuário completar o catálogo, sem reler os documentos | reexecução parcial em < 10% do tempo da análise completa |
| d | Prospector e Assistente como subgrafos que invocam o grafo de análise | trilha única por prospecção com os nós de cada análise aninhados |

### PT-2.2 · Registro de ferramentas (MCP)

- Servidor MCP interno expondo as ferramentas atuais (PNCP, documentos, catálogo, análises) com esquema único; Prospector, Investigador e Assistente consomem do registro; permissões por agente (o Investigador não busca no PNCP; o Assistente não registra requisito).
- Aceite: a lista de ferramentas por agente é declarativa e testada; adicionar uma ferramenta nova não exige mudar os agentes.

### PT-2.3 · Fila e workers

- Substituir `ThreadPoolExecutor` por uma fila persistente baseada em Postgres (`procrastinate`) ou Redis (`arq`): jobs de análise, prospecção, ingestão e importação; retentativa com espera crescente; cancelamento.
- Aceite: 3 workers processam 10 análises simultâneas sem perda; reinício do servidor não perde jobs.

### PT-2.4 · Agente Monitor e índice de itens

| # | Tarefa | Aceite |
|---|---|---|
| a | Coleta agendada: a cada 6 h, novas contratações nas UFs atendidas (todas as modalidades), com itens e lista de anexos; detecção de retificações | cobertura ≥ 99% das publicações do dia nas UFs monitoradas |
| b | Índice de itens no Postgres com `pgvector`: embeddings dos itens (modelo multilíngue, `bge-m3` local ou API) + busca por texto (`tsvector`); busca híbrida com RRF | consulta "luminária LED 100 W IP66" devolve itens de pregões cujo objeto não cita iluminação |
| c | Alertas: por e-mail/WhatsApp quando um item novo é aderente ao catálogo (pré-filtro barato + análise completa automática dentro da cota do plano) | alerta chega em < 1 h da publicação |
| d | PCA (planos anuais) como fonte de demanda PLANEJADA | tipo PLANEJADA passa a existir em análises reais |

### PT-2.5 · Agente de Habilitação

- Lê as seções de habilitação do edital (jurídica, fiscal, técnica, econômica), extrai o checklist com citação conferida e cruza com os documentos declarados no perfil da empresa (PT-1.4c); aponta o que falta e o prazo.
- Aceite: checklist com evidência para 10 editais do benchmark; concordância com rotulagem humana ≥ 90%.

### PT-2.6 · Feedback que recalibra

- Decisões seguir/descartar e comentários viram dados de treino para os pesos da prioridade (regressão logística simples sobre as variáveis já existentes); pesos por empresa quando houver volume, globais antes.
- Aceite: ordenação das recomendações melhora a concordância com as decisões humanas em validação cruzada.

### PT-2.7 · Observabilidade

- Ponto de partida em 24/10: a **trilha por chamada já existe** (`observability/trilha.py`, SQLite + `GET /api/analises/{id}/chamadas` + `GET /api/metricas/llm` + UI): agente, origem, versão do prompt, modelo pedido × usado, tokens com raciocínio, custo pela tabela oficial, latência, cache, reserva, erro, resumo da entrada e da saída; logs estruturados por etapa e por chamada (`observability/logs.py`, JSON com `OBRANEXO_LOG_JSON=1`).
- Evolução: OpenTelemetry (traces por análise, spans por nó do `GRAFO` e por chamada de modelo, gerados a partir dos mesmos pontos que hoje alimentam a trilha) exportado para Langfuse self-hosted; painéis de custo, latência, tokens e taxa de INDETERMINADO por empresa e por agente; alertas de erro e de custo.
- Aceite: qualquer análise pode ser inspecionada ponta a ponta no Langfuse com prompt, resposta e custo.

### PT-2.8 · Leitura de documentos

- Tabelas em PDF (`pdfplumber`), OCR para PDF digitalizado (Tesseract ou modelo multimodal, só quando não há texto), classificação do tipo de documento (edital, TR, memorial, planilha, ata).
- Aceite: os 5 casos cegos mais 5 com PDF digitalizado extraídos com ≥ 95% dos itens lidos.

### PT-2.9 · Match 2.0

- Estoque × quantidade pedida, prazo de entrega × prazo do edital, preço de referência × valor estimado (sinaliza, não decide); equivalência entre normas (NBR IEC 60598 ↔ Portaria INMETRO); taxonomia por categoria (cabos: condutores, classe de encordoamento; braços: comprimento).
- Aceite: 10 atributos novos cobertos por testes; benchmark não regride.

### PT-2.10 · Piloto de 60 dias com 10 distribuidores

- Onboarding assistido (catálogo importado + primeira análise em 7 dias); fila de revisão humana na UI; medição de horas economizadas, propostas enviadas e CNPJ do cliente entre licitantes no PNCP.

---

## F3 · v1.0 — Produção (mar → jun/2027)

**Critério de saída:** 30 dias cumprindo as metas de serviço (99,5% de disponibilidade, p95 < 90 s por análise); margem bruta 75–85%; LGPD documentada; pentest sem achados críticos.

| PT | Escopo | Aceite |
|---|---|---|
| 3.1 Infraestrutura como código | AWS: ECS Fargate (API e workers), RDS Postgres com pgvector, S3 para anexos com versionamento, CloudFront; Terraform; ambientes staging e produção; backups com restauração pontual | ambiente recriado do zero pelo Terraform em < 30 min; restauração testada |
| 3.2 Gateway de modelos | roteamento por tarefa (extração em lote no modelo barato via Batch API; raciocínio no modelo forte), cache do catálogo no prompt, orçamento por cliente e por análise, troca de modelo só após execução em paralelo com comparação no benchmark; Bedrock como provedor | custo por análise medido e reportado por plano; troca de modelo sem regressão no benchmark |
| 3.3 Isolamento e segurança | RLS no Postgres por `empresa_id`; segredos em gerenciador; trilha de auditoria das ações dos agentes e dos usuários; testes de ataque com editais hostis (prompt injection) no CI; pentest externo | relatório do pentest; suíte de injeção com 0 ações fora do esperado |
| 3.4 LGPD | relatório de impacto; contratos com provedores que não treinam com dados do cliente (o nível gratuito do Gemini não serve); mascaramento de dados pessoais nos documentos (CPF, contatos de servidores); política de retenção | documentos publicados; mascaramento testado |
| 3.5 Planos e cobrança | Radar grátis, Essencial, Profissional, Assessoria (multi-CNPJ), créditos avulsos; cotas por plano aplicadas na fila; integração de pagamento | ciclo completo de assinatura e cota |
| 3.6 Rastreador de obras | em oportunidades INDIRETAS, acompanha ata e contrato no PNCP, identifica a construtora vencedora e sugere o contato com os insumos encontrados nos projetos | 10 obras reais com a vencedora identificada |
| 3.7 Avaliação contínua | amostragem de análises em produção revisada por pessoas; monitor de deriva (taxa de INDETERMINADO, concordância com decisões, citações não conferidas); LLM-as-judge só como pré-filtro, nunca como gabarito | painel de qualidade semanal |

---

## F4 · v1.x — Escala (2º semestre de 2027 →)

- Conectores: Obrasgov, portais estaduais de GO, DF, MT e MS.
- Agente de Precificação: histórico de preços homologados por item, órgão e região (resultados do PNCP); apoio à proposta com faixa e justificativa; **nunca dá lance**.
- Grafo de conhecimento órgão–objeto–item–fornecedor; histórico de concorrentes por item.
- API pública e servidor MCP para clientes (CRM, assessorias com dezenas de CNPJs); integrações RD Station, HubSpot, Pipedrive; Kanban de oportunidades.
- Monitor de especificações para fabricantes (que exigências aparecem nos editais e quais produtos da rede atendem).
- Novos segmentos pela taxonomia: hidráulica, climatização, incêndio, segurança eletrônica.

---

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| PNCP instável ou com mudança de API | ingestão própria (PT-2.4), cache com cópia antiga (já existe), testes com respostas gravadas |
| Qualidade fora da amostra abaixo do esperado | PT-1.2 é a primeira tarefa; corrigir antes de escalar; benchmark como trava |
| Custo de IA crescer com o volume | gateway com lote e cache (PT-3.2); cotas por plano; modo determinístico como piso |
| Sigilo do catálogo e dos preços do cliente | isolamento por empresa (PT-1.4) antes de qualquer piloto; RLS em F3; provedores pagos |
| LangGraph atrasar a equipe | o grafo próprio já roda e é declarado como dado; LangGraph só entra se os checkpoints duráveis compensarem, nó a nó, mantendo o `GRAFO` atual até passar no benchmark |
| Escopo crescer | respeitar critérios de saída; nada de F2 antes de F1 fechar |

## Definição de Pronto (vale para todo item)

- Teste automatizado (regras, conectores, evidência, API) ou roteiro de teste manual documentado (UI).
- Passa no ruff, no pytest e no benchmark determinístico (sem regressão).
- Não quebra o fluxo de ponta a ponta de `goianira_pe038_2026` em modo determinístico.
- Emite logs estruturados.
- Documentado no README (selo atualizado) ou em `docs/` quando muda o uso.
- Revisado por outra pessoa da equipe (PR pequeno; integração na `main` pelo menos duas vezes por semana).
