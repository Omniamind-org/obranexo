# Plano de desenvolvimento — ObraNexo

Versão 1.0 · 24/10/2026 · alinhado ao [README](../README.md) (cada item abaixo corresponde a um selo ⬜ ou 🟡 de lá).

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

Defeitos encontrados em 24/10 que afetam resultado ou credibilidade. Pequenos, independentes, alto retorno.

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Busca em todas as modalidades relevantes: parâmetro `modalidades: list[int]` em `buscar_publicacoes` e `buscar_propostas_abertas`; padrão `[6, 7, 4, 5, 8]` (pregão eletrônico e presencial, concorrência eletrônica e presencial, dispensa); UI e ferramentas do Prospector e do Assistente expõem o filtro | `connectors/pncp.py`, `api/main.py` (`/api/pncp/buscar`), `agents/prospector.py`, `agents/assistente.py`, `web/js/views/demandas.js` | teste com resposta gravada por modalidade; `obranexo abertas --uf GO --modalidades 4,6` devolve concorrências |
| b | Tela de busca lê todas as páginas: `max_paginas` deixa de ter teto 6 na UI; o backend pagina até `total_paginas` com limite de segurança 20 | `web/js/views/demandas.js`, `api/main.py` | busca em GO devolve as 9 páginas (hoje 6) |
| c | Reprodutibilidade: `temperature=0` em Gemini e Anthropic (já existe no Groq); versão do prompt (`PROMPT_VERSION` em `prompts.py`) entra na chave do cache | `llm/client.py` (`GeminiClient._gerar`, `AnthropicClient`), `agents/prompts.py` | teste unitário confere o payload da chamada e a chave do cache |
| d | Validação de categorias na importação de planilha: categoria fora de `CATEGORIAS` → erro 400 com sugestão (fuzzy) e lista válida; normalização de sinônimos simples ("Luminária pública" → `luminaria_publica_led`) | `catalog/loader.py`, `api/main.py` (`POST /api/catalogo`), `web/js/views/catalogo.js` | upload com categoria inválida é recusado com mensagem; teste em `tests/test_api.py` |
| e | Prioridade recalibrada: prazo ABERTO vale +35, ENCERRADO com SRP +5 e sem SRP 0; cobertura de valor 0,5; pesos em constantes nomeadas no topo de `planejador.py` | `agents/planejador.py`, `tests/test_agentes_sem_llm.py` | Itaberaí (aberta, 51%) fica acima de Goianira (encerrada, 100%); benchmark continua 100% |
| f | ✅ Preços de tabela dos modelos (out/2026, com fonte) em `precos_usd`, incluindo Groq e a faixa do Haiku 5.5 acima de 100k tokens; endpoint interno `GET /api/custos` (US$ e R$, média/mediana/p95, por modelo, por dia, meta de R$ 1 por análise), ainda sem tela | `config.py`, `llm/client.py`, `custos.py`, `api/main.py`, `tests/test_custos.py` | custo deixa de ser zero em análises com IA; endpoint testado |
| g | Logs estruturados: `structlog` em JSON por evento (análise, nó, ferramenta, modelo, tokens, duração, erro); `EventoLog` passa a emitir também para o logger | `agents/contexto.py`, `api/jobs.py`, novo `observability/logging.py` | cada análise gera linhas JSON parseáveis; teste lê o log de uma análise determinística |
| i | ✅ Pacotes congelados portáveis: `documentos.json` gravado no Windows guardava `arquivos\x.pdf`, e em Linux nenhum anexo era lido (achado pelo CI); leitura aceita os dois formatos e a gravação usa `/` | `connectors/pncp.py`, `tests/test_casos_portaveis.py` | os 3 jobs do CI passam em Linux |
| h | ✅ Limites por licitação: paginar itens (>500) e anexos (>100) do PNCP | `connectors/pncp.py`, `tests/test_pncp_paginacao.py` | SEINFRA lista os 107 anexos (antes 100; os 7 perdidos incluíam a ata de contratação e o termo de homologação); teste com 2 páginas |

### PT-1.2 · Avaliação com gabarito duplo (semanas 1–3, em paralelo)

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Rotular os 5 casos cegos (133 itens) por **duas pessoas** na planilha existente; resolver divergências; registrar concordância (Cohen's kappa) | `docs/teste_cego_rotulagem.csv` → `data/casos/cego_*/gabarito.json` | kappa reportado em `docs/avaliacao.md`; 7 casos com gabarito |
| b | Coletar e rotular 3 contratações novas de outras UFs (DF, MT, TO), uma delas com TR em DOCX e uma concorrência de obra | `data/casos/` | ≥ 10 contratações, ≥ 150 pares item × produto |
| c | `run_benchmark.py` passa a calcular precisão/recall por classe, matriz de confusão e consistência (3 execuções); sai em JSON e Markdown | `eval/run_benchmark.py`, `eval/metrics.py` (novo) | `docs/avaliacao.md` gerado com as métricas-alvo do roadmap (seção 13.2) |
| d | ✅ Benchmark como trava no CI: job que roda o benchmark determinístico e falha se qualquer métrica cair abaixo do limiar definido em `eval/limiares.json` | `.github/workflows/ci.yml`, `eval/limiares.json` | PR que degrada o benchmark fica vermelho |

### PT-1.3 · PostgreSQL e persistência (semanas 2–3)

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Modelos SQLModel: `Empresa`, `Usuario`, `Produto`, `Analise` (JSONB para o corpo + colunas de índice: contratação, status, prioridade, empresa_id), `Prospeccao`, `Conversa`, `Decisao` (seguir/descartar/comentário, quem, quando) | novo `db/models.py`, `db/session.py` | `alembic upgrade head` cria o esquema do zero |
| b | Alembic com migração inicial; `DATABASE_URL` no `.env`; SQLite continua como padrão local para desenvolvimento sem Docker | `alembic/`, `config.py` | testes rodam em SQLite em memória; produção em Postgres |
| c | `storage/store.py` vira repositório sobre o banco, mantendo a mesma interface (`salvar`, `carregar`, `listar`, prospecções, catálogo ativo por empresa) | `storage/store.py` | todos os testes atuais passam sem alteração nas chamadas |
| d | Chat persistido (hoje em memória): sessões e mensagens no banco | `agents/assistente.py` (`sessoes`) | conversa sobrevive a reinício do servidor |
| e | Script de migração dos JSONs existentes em `data/analises` e `data/prospeccoes` | `scripts/migrar_json.py` | análises antigas aparecem na interface após a migração |

### PT-1.4 · Login e isolamento por empresa (semanas 3–4)

Pré-requisito para qualquer piloto com catálogo real.

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Autenticação: e-mail + senha (argon2) com sessão por cookie assinado; convite por link; papéis `admin` e `analista` | novo `api/auth.py`, `db/models.py`, `web/js/views/login.js` | fluxo de login/logout na UI; rotas `/api/*` exigem sessão, exceto `/api/status` |
| b | Remover o estado global `_estado["empresa"]`: toda rota recebe `empresa_atual(usuario)`; catálogo, análises, prospecções e conversas filtrados por `empresa_id` | `api/main.py`, `storage/store.py` | teste: dois usuários de empresas diferentes não veem dados um do outro |
| c | Perfil da empresa editável: UFs atendidas, raio logístico, capacidade por categoria, documentos de habilitação que possui (base para o agente de Habilitação em F2) e os dados da proposta de preços (razão social, CNPJ, endereço, contato, representante, dados bancários — ver PT-1.8 B1.5g) | `web/js/views/empresa.js` (novo), `models.py` (`Empresa`) | perfil salvo e usado pela qualificação (UF fora da área penaliza) e pela proposta de preços |
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

### PT-1.8 · Kit da proposta (frente B)

Ajuda o fornecedor a montar o que entrega ao órgão para disputar a licitação (proposta por item, documentos técnicos, habilitação, declarações e prazos), a partir da análise e do próprio edital. Por decisão da equipe em 24/10/2026, vem **antes** da triagem (PT-1.9). A extração dirigida do edital (prazos, habilitação, declarações, modelo de proposta) é compartilhada com o portão 2 da triagem.

**Regras fixas:** o edital é a fonte; todo atributo ofertado vem do catálogo e toda conformidade vem do motor de regras; produto INCOMPATÍVEL nunca é ofertado; item PARCIAL ou INDETERMINADO entra com o que falta resolver; documento só aparece como "declarado" se o catálogo declarar; **sem preço** (o valor estimado pelo órgão é só referência) e **sem envio** — quem revisa, precifica, assina e envia é o fornecedor; o que o sistema não sabe sai como "[preencher]", nunca como suposição.

| Fase | Entrega | Situação |
|---|---|---|
| **B1** · Kit a partir da análise | `proposta.py` + `GET /api/analises/{id}/proposta` (JSON), `.md` (guia com provas) e `.xlsx` (uma linha por item, para o portal); situação por item (ofertar, ofertar com ressalva, resolver antes, não ofertar, fora do catálogo); descrição para a proposta só com atributos confirmados; exigências e prazos com prova; documentos técnicos (declarado, falta, operacional); aba e botão **Proposta** na tela da análise. Produto ganha `fabricante`, `marca` e `modelo` (planilha, JSON e importação de ficha); o catálogo de demonstração recebe marcas fictícias por linha | ✅ 24/10/2026 |
| **B3a** · Proposta de preços padrão (.docx) | `GET /api/analises/{id}/proposta.docx`: cabeçalho do fornecedor, referência à licitação, tabela dos itens ofertáveis (especificação, marca, modelo, fabricante, unidade, quantidade; preços em branco), condições do edital (prazo de entrega, garantia; validade "[preencher]"), declarações padrão, assinatura e uma página de **conferência interna** a remover antes do envio. Perfil da empresa ganha razão social, endereço, contato, representante e dados bancários (fictícios evidentes no fornecedor de demonstração) | ✅ 24/10/2026 |
| **B1.5** · Editor da proposta no site | ver tabela abaixo | ⬜ planejado |
| **B2** · Extração dirigida do edital | prazos de impugnação, amostra e proposta reajustada; validade mínima da proposta; lista de habilitação; declarações pedidas; localização do modelo de proposta do edital — tudo com citação conferida (é também o portão 2 da triagem) | ⬜ |
| **B3b** · Modelo do próprio edital | preencher o modelo de proposta que o edital traz (ex.: Goianira, p. 25 e 55) em vez do modelo padrão; descrição técnica redigida por IA com verificador: todo número citado precisa existir no catálogo, senão a frase é rejeitada | ⬜ |
| **B4** · Perfil documental da empresa | certidões e atestados com validade; habilitação marcada como tem, vencido ou falta; alerta de vencimento | ⬜ (com PT-1.4c) |

**B1.5 · Editor da proposta no site (registrado em 24/10/2026 como plano futuro).** Em vez de o fornecedor completar tudo no Word, a proposta é editada na própria aba Proposta e o Word ou o PDF são gerados no fim, a partir do que foi editado. Motivos: o preço é o que o fornecedor mais preenche e, no site, ganha cálculo e validação; a conferência interna vira checklist; os dados ficam estruturados (histórico de propostas, KPI "propostas enviadas" do BMC, aprendizado com vitórias e derrotas e, depois, o Agente de Precificação). Prioridade sugerida: depois do pitch regional e antes de B2. Esforço estimado: ~2 dias para a versão completa; menos de 1 dia para a mínima (preços com totais, validade, local e data, incluir ou tirar item, gerar Word e PDF).

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Rascunho da proposta salvo por análise: preço unitário por item, itens incluídos ou retirados, validade, local e data, descrições editadas, pendências marcadas como resolvidas, data da última edição | `models.py` (`RascunhoProposta`), `storage/store.py` (`data/propostas/<analise_id>.json`; PostgreSQL com o PT-1.3) | rascunho sobrevive a reinício do servidor; análise sem rascunho começa do kit |
| b | API do rascunho: `GET` e `PUT /api/analises/{id}/proposta/rascunho`, com validação (preço ≥ 0, item que não pode ser ofertado não entra) e totais calculados no servidor | `api/main.py`, `proposta.py` | totais por item e valor global conferem; item INCOMPATÍVEL recusado com 422 |
| c | Avisos de risco no rascunho: preço unitário acima do valor estimado pelo órgão (causa comum de desclassificação no pregão); pendência não resolvida; campo obrigatório vazio (validade, local e data, dados do fornecedor) | `proposta.py` | avisos devolvidos pela API e exibidos na tela; nenhum bloqueia a edição |
| d | Descrição técnica editável sem perder a rastreabilidade: o texto conferido fica como referência e a versão editada é marcada como "editada pelo fornecedor" na tela e na conferência interna | `proposta.py`, `web/js/views/resultado.js` | diferença visível entre o texto conferido e o editado |
| e | Tela de edição na aba Proposta: tabela com campo de preço e total ao vivo, incluir ou retirar item, campos das condições, checklist de pendências, salvamento automático e indicação de "salvo" | `web/js/views/resultado.js`, `web/css/app.css` | funciona nos temas claro e escuro, sem erro no console; edição preservada ao trocar de aba e recarregar |
| f | Saída final a partir do rascunho: Word (`proposta.docx` passa a usar preços, validade, local e data editados; valor global preenchido) e **PDF pela impressão do navegador**, como o "Imprimir / PDF" do dossiê — sem dependência nova; a conferência interna sai só no Word, nunca no PDF | `proposta.py`, `web/js/views/resultado.js` | Word e PDF iguais ao rascunho; PDF sem a página de conferência |
| g | Dados do fornecedor editáveis no site (razão social, CNPJ, endereço, contato, representante, dados bancários), em vez de virem do JSON do catálogo — junto com o perfil da empresa do PT-1.4c | `web/js/views/empresa.js` (novo), `api/main.py` | proposta usa os dados editados; campos vazios seguem como "[preencher]" |
| h | Testes: rascunho (salvar, ler, validar, totais, avisos), saída do Word com preços, item incompatível recusado; retrato da demo inalterado | `tests/test_proposta_rascunho.py` | testes no CI |

**Cuidados:** sem login (PT-1.4) há um fornecedor por instalação, o que serve para demo e piloto; a descrição editada perde a garantia de "conferido" e precisa ser marcada como tal; nada é enviado ao órgão pelo sistema.

### PT-1.9 · Triagem em camadas (frente A)

**Objetivo:** decidir o que vale analisar a fundo **sem perder licitação que serve ao fornecedor**, e parar de gastar IA com itens fora do portfólio. Hoje a extração por IA roda em todos os itens antes do filtro de portfólio (`agents/pipeline.py`); no teste cego, 54 dos 133 itens (41%) estavam fora do portfólio e passaram pela IA à toa, e o pregão de 206 itens de Anápolis esgotava o orçamento de tokens só na extração.

**Princípios** (valem para todo item deste pacote):

1. **Três estados: seguir, rebaixar, descartar.** Só **fato verificável** descarta: licitação revogada ou anulada; proposta encerrada sem registro de preços, e só na prospecção; item exclusivo para ME/EPP quando a empresa comprovadamente não é ME/EPP (descarta o item, não a licitação; cota reservada não descarta). Heurística — categoria pelo texto, palavra no objeto, valor, UF fora da área, licitação suspensa, prazo encerrado com registro de preços — **só rebaixa**, com o motivo.
2. **A triagem decide o que buscar, não o que analisar.** Licitação escolhida pelo usuário nunca é descartada: a triagem só anota (por exemplo, "prazo encerrado; vale para adesão à ata"). Isso protege o fluxo da demonstração: Goianira, Aruanã e SEINFRA têm prazo encerrado.
3. **Nunca descartar pelo objeto.** 90% dos pregões com itens elétricos não citam isso no objeto (medição própria). A triagem olha os itens; um item só sai quando é reconhecido como outra coisa fora do portfólio. Item que as regras não reconhecem vai para a classificação barata por IA e, na dúvida, fica.
4. **"Não sei" nunca descarta.** Porte da empresa desconhecido, benefício ausente no PNCP ou em caso congelado antigo: o critério não age.
5. **Tudo reversível e auditável.** Nada é apagado; toda licitação ou item descartado guarda motivo e evidência, com "analisar mesmo assim".
6. **Nasce em modo sombra.** O corte é ligado critério a critério, só depois de medido com zero falso negativo.

**Portões** (cada um mais caro que o anterior; só passa para o seguinte quem atravessou o atual):

| Portão | O que olha | Custo |
|---|---|---|
| 0 · Dados do PNCP | prazo, situação, modalidade, UF, valor, registro de preços | zero, sem baixar nada |
| 1 · Itens | categoria por regras; itens no portfólio; benefício ME/EPP por item × porte; pré-comparação por regras com a descrição | regras; IA só para classificar, em lote, itens não reconhecidos |
| 2 · Barreiras do edital | busca dirigida: habilitação técnica, amostra, visita técnica, prazo de entrega, garantia, exigência de marca e modelo | texto já extraído; IA só nos trechos achados (compartilhado com PT-1.8) |
| 3 · Análise completa | o pipeline atual, só nos itens que passaram | o atual, menor |

| # | Tarefa | Arquivos | Aceite |
|---|---|---|---|
| a | Dados de entrada: benefício por item do PNCP (`tipoBeneficio`: exclusiva ME/EPP, cota reservada) e porte da empresa (ME, EPP, demais, desconhecido) | `connectors/pncp.py` (`item_de_api`), `models.py` (`ItemDemanda`, `Empresa`) | itens coletados guardam o benefício; casos congelados antigos continuam abrindo (campos opcionais) |
| b | Regras de triagem dos portões 0 e 1: estado e motivo por licitação e por item; classificação barata por IA, em lote, só dos itens não reconhecidos | novo `src/obranexo/triagem.py`, `tests/test_triagem.py` | toda decisão tem motivo e dado de origem; nenhuma heurística descarta |
| c | Na análise: extração por IA só dos itens que passaram no portão 1; itens fora do portfólio seguem aparecendo como "fora do catálogo", com o motivo; licitação escolhida pelo usuário nunca é descartada | `agents/pipeline.py`, `agents/extrator.py` | sem IA, resultado idêntico ao retrato da demo; com IA, menos chamadas nos casos com itens fora do portfólio (medido em `GET /api/custos`) |
| d | No Prospector: ferramenta `triar(contratacao_id)` com os números do portão 1 (valor atendível, itens no portfólio, itens exclusivos ME/EPP, prazo), para o agente decidir o que analisar a fundo | `agents/prospector.py` | ranking usa a triagem; descartes aparecem na trilha com o motivo |
| e | Modo sombra: `OBRANEXO_TRIAGEM=desligada\|sombra\|ativa`, padrão `sombra`; em sombra a análise completa roda sempre e um relatório cruza "teria descartado" × resultado real | `config.py`, `triagem.py`, `eval/triagem_sombra.py` | relatório sobre ≥ 200 licitações reais do PNCP; cada critério só é ligado com zero falso negativo (descartada que tinha item COMPATÍVEL ou PARCIAL) |
| f | Lista de descartadas reversível: `GET /api/triagem/descartadas` e "analisar mesmo assim"; tela depois | `api/main.py` | nada é apagado; toda descartada tem motivo e evidência |
| g | **Testes de proteção da demo, no CI:** (1) ✅ retrato dos 9 casos congelados — veredito e produto por item, prioridade, tipo de oportunidade, provas, requisitos — com a data fixada, porque a prioridade depende do prazo; (2) licitação escolhida pelo usuário nunca é descartada (Goianira, prazo encerrado, analisada por completo com a triagem `ativa`); (3) modo sombra idêntico a desligado | `tests/test_retrato_demo.py`, `tests/dados/retrato_demo.json`, `tests/test_triagem.py` | os três no CI; mudança não intencional na demo reprova o PR; mudança intencional atualiza o retrato no próprio PR, visível na revisão |
| h | "Recall do funil" no benchmark: itens relevantes do gabarito (COMPATÍVEL ou PARCIAL) mantidos pela triagem; mínimo inicial 100% | `eval/run_benchmark.py`, `eval/limiares.json` | PR que faça o funil perder item relevante fica vermelho |
| i | Auditoria e feedback: amostra semanal dos descartes revisada por uma pessoa; licitação descartada que o fornecedor marcar como relevante vira caso rotulado e teste de regressão | `docs/avaliacao.md` | rotina documentada; primeiro ciclo executado no piloto |

**Dependências:** PT-1.2 (gabaritos) para medir o recall; PT-1.4c (perfil com porte); portão 2 compartilhado com PT-1.8.

**Verificação de base (24/10/2026):** os 9 casos congelados rodados sem IA com o código anterior a esta sessão (`c166904`) e com a `main` (`39a43c5`) deram resultado idêntico — é o retrato que a tarefa g transforma em teste.

**Sequência sugerida de F1:** semana 1 (25–31/10): PT-1.1 completo, PT-1.2a iniciado · semana 2 (01–07/11): PT-1.3, PT-1.5a/b, PT-1.2b/c · semana 3 (08–14/11): PT-1.4, PT-1.2d, PT-1.5c/d · semana 4 (15–21/11): PT-1.6, pilotos, deploy · semana 5 (22–28/11): congelar em 24/11, `docs/avaliacao.md`, tag `v0.2-nacional`. Frentes novas de 24/10: PT-1.8 (kit da proposta) antes de PT-1.9 (triagem); o retrato da demo (PT-1.9g, parte 1) entrou antes de ambas, porque protege qualquer mudança (`tests/test_retrato_demo.py`, ✅ 24/10/2026). Depois do pitch regional: PT-1.8 B1.5 (editor da proposta no site) antes de B2.

---

## F2 · v0.3 — Beta fechado (dez/2026 → fev/2027)

**Objetivo:** plataforma agêntica e piloto em escala. **Critério de saída:** precisão ≥ 95% fora da amostra; rastreabilidade 100%; custo medido < R$ 1 por análise; 95% das análises em < 3 min; 10 distribuidores no piloto de 60 dias.

### PT-2.1 · Grafo durável de agentes

| # | Tarefa | Aceite |
|---|---|---|
| a | Migrar `agents/pipeline.py` para LangGraph: cada nó atual vira um nó do grafo; estado tipado (`AnaliseState`) a partir de `Contexto`; checkpointer no Postgres | análise interrompida (kill do worker) retoma do último nó concluído |
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

- OpenTelemetry (traces por análise, spans por nó e por chamada de modelo) exportado para Langfuse self-hosted; painéis de custo, latência, tokens e taxa de INDETERMINADO por empresa e por agente; alertas de erro e de custo.
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
| LangGraph atrasar a equipe | nós já têm fronteiras claras; migração nó a nó; manter o pipeline atual até o grafo passar no benchmark |
| Escopo crescer | respeitar critérios de saída; nada de F2 antes de F1 fechar |

## Definição de Pronto (vale para todo item)

- Teste automatizado (regras, conectores, evidência, API) ou roteiro de teste manual documentado (UI).
- Passa no ruff, no pytest e no benchmark determinístico (sem regressão).
- Não quebra o fluxo de ponta a ponta de `goianira_pe038_2026` em modo determinístico.
- Emite logs estruturados.
- Documentado no README (selo atualizado) ou em `docs/` quando muda o uso.
- Revisado por outra pessoa da equipe (PR pequeno; integração na `main` pelo menos duas vezes por semana).
