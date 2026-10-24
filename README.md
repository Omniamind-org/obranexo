<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/logo-complete-dark.png">
    <img src="images/logo-complete.png" alt="ObraNexo" width="440">
  </picture>
</p>

<h3 align="center">Todo dia, o governo publica mais de mil pedidos de compra.<br>Quem entende primeiro, vende primeiro.</h3>

<p align="center">
  O ObraNexo é uma plataforma de agentes de IA que lê essas licitações no PNCP, item por item, cruza cada exigência<br>
  com o catálogo de um fornecedor e mostra o que ele atende, apontando a linha exata do edital.<br>
  Começamos por material elétrico e iluminação, onde 9 em cada 10 pregões não citam esses itens no título.
</p>

<p align="center">
  <a href="https://kauandivino.github.io/obranexo/"><img alt="Business Model Canvas: ver o canvas" src="https://img.shields.io/badge/Business%20Model%20Canvas-ver%20o%20canvas%20%E2%86%92-00ab9f?style=for-the-badge&labelColor=0b2a3c"></a>
</p>

<p align="center">
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-0b2a3c?style=flat-square&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-API%20%2B%20SSE-00ab9f?style=flat-square">
  <a href="https://github.com/kauandivino/obranexo/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/kauandivino/obranexo/ci.yml?branch=main&style=flat-square&label=CI"></a>
  <img alt="Rastreabilidade" src="https://img.shields.io/badge/cita%C3%A7%C3%B5es%20conferidas-100%25-0ca30c?style=flat-square">
  <img alt="Versão" src="https://img.shields.io/badge/vers%C3%A3o-0.1%20%C2%B7%20MVP-7d8b96?style=flat-square">
  <img alt="AKCIT Camp 2026" src="https://img.shields.io/badge/AKCIT%20Camp-2026-fab219?style=flat-square">
</p>

<p align="center">
  <a href="#em-30-segundos">Em 30 segundos</a> ·
  <a href="#o-problema-em-números">Problema</a> ·
  <a href="#como-funciona">Como funciona</a> ·
  <a href="#arquitetura-agêntica">Arquitetura agêntica</a> ·
  <a href="#validação-e-resultados">Resultados</a> ·
  <a href="#status-e-roadmap">Roadmap</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#referência">Referência</a>
</p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/prova_dark.png">
    <img src="docs/images/prova_light.png" alt="Prova no documento: o trecho literal do edital que sustenta o veredito, destacado na página de origem" width="920">
  </picture>
  <br>
  <sub>Cada conclusão abre o trecho literal que a sustenta. Pregão real: Goianira/GO, PE 038/2026, luminárias LED.</sub>
</p>

---

## Em 30 segundos

| | |
|---|---|
| **O que é** | Uma plataforma de inteligência comercial agêntica para contratações públicas. O fornecedor carrega o catálogo; os agentes buscam no PNCP, leem edital, termo de referência e anexos, e dizem, **item a item**, se cada produto atende, não atende, atende em parte ou se falta informação. Todo veredito vem com a prova. Quando o fornecedor decide disputar, o ObraNexo também ajuda a montar a proposta que ele entrega ao órgão: cada item com o produto, a marca e o modelo ofertados, já conferidos contra as exigências do edital, e a lista de documentos de habilitação pedidos. Quem revisa e envia é sempre o fornecedor. *(em construção)* |
| **Para quem** | Distribuidores e atacadistas de material elétrico e iluminação, em geral micro e pequenas empresas sem analista de licitação. Depois: varejo elétrico, fabricantes, assessorias de licitação e construtoras. |
| **Por que importa** | O PNCP publica cerca de **1.100 pregões eletrônicos por dia**. Cerca de **90% dos pregões com itens elétricos não dizem isso no objeto**, então escapam de qualquer alerta por palavra-chave. Quem lê tudo, acha a licitação certa e acerta a especificação disputa contra poucos; quem erra uma especificação é desclassificado. |
| **O que já funciona** | Prospecção autônoma no PNCP ao vivo, análise completa de 9 licitações reais congeladas, 7 agentes, assistente em linguagem natural, catálogo por ficha técnica do fabricante, dossiê com prova, 3 provedores de IA com reserva automática. Roda em modo determinístico sem chave de API. |

> **Princípio de projeto.** A IA decide o que buscar, o que abrir, o que ler e o que investigar. Um núcleo verificável — validação por tipo e faixa, motor de regras e citação conferida no documento — garante que o veredito final seja auditável. Sem prova, o sistema diz **indeterminado** em vez de inventar.

## O problema em números

Medição própria feita com o conector do ObraNexo sobre **64.473 pregões eletrônicos do PNCP** (junho e setembro–outubro de 2026). Método e limitações em [`BMC_ObraNexo.txt`](BMC_ObraNexo.txt).

| Número | O que significa |
|---|---|
| **~1.110 pregões eletrônicos por dia** | 33.406 em 30 dias (24/09 a 23/10/2026). Ninguém lê isso à mão. |
| **R$ 6,1–6,4 bilhões por ano** | valor estimado em itens de material elétrico, só em pregão eletrônico; iluminação é 83% disso |
| **~90% invisíveis por palavra-chave** | dos pregões com itens elétricos, só cerca de 10% citam material elétrico no objeto. O item está na lista, não no título. |
| **23 itens elétricos por pregão** (mediana 8) | cada um com potência, fluxo, IP, garantia, INMETRO… a conferir contra o catálogo |
| **45% dos itens elétricos exclusivos para ME/EPP** | um mercado reservado por lei que fica deserto quando faltam pequenas empresas qualificadas |
| **6–12% dos itens desertos ou fracassados** | demanda que ninguém viu, ou propostas recusadas por especificação |
| **8 dias úteis** | prazo mínimo entre a publicação e a proposta (Lei 14.133) |
| **R$ 110 a R$ 700 por edital** | custo interno de analisar um edital à mão, ganhando ou não (estimativa sobre salário médio de analista) |

## Como funciona

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#e2f4f2','primaryTextColor':'#10222f','primaryBorderColor':'#00ab9f','lineColor':'#7d8b96','edgeLabelBackground':'#f1f3f3','fontSize':'15px','clusterBkg':'transparent','clusterBorder':'#7d8b96','titleColor':'#7d8b96'}}}%%
flowchart LR
  F([🏭 Fornecedor<br/>catálogo real: planilha<br/>ou ficha do fabricante]):::nav
  P[(🏛️ PNCP<br/>licitações, itens e anexos<br/>~1.100 pregões por dia)]:::nav
  subgraph ON[" ObraNexo "]
    direction LR
    A1[🔎 Prospecção<br/>o agente decide o que<br/>buscar e o que abrir]:::ag
    A2[📄 Leitura<br/>edital, TR e anexos,<br/>item a item]:::ag
    A3[⚖️ Veredito verificável<br/>regras + prova literal]:::core
    A4[📋 Dossiê<br/>prioridade, riscos,<br/>próximos passos]:::ag
    A1 --> A2 --> A3 --> A4
  end
  F -- catálogo --> ON
  P -- dados abertos --> ON
  ON --> H{{👤 Decisão humana<br/>seguir · descartar · comentar}}:::hum
  H -. feedback .-> ON
  classDef nav fill:#0b2a3c,stroke:#0b2a3c,color:#ffffff
  classDef ag fill:#e2f4f2,stroke:#00ab9f,color:#10222f
  classDef core fill:#00ab9f,stroke:#00756c,color:#ffffff
  classDef hum fill:#fdf3dc,stroke:#fab219,color:#10222f
```

1. **Catálogo.** Planilha CSV/XLSX, JSON, ou o link/PDF da ficha técnica do fabricante: a IA propõe os produtos com atributos validados e o usuário revisa antes de adicionar.
2. **Prospecção.** O agente lê o catálogo, escolhe os termos de busca, consulta os pregões com propostas abertas no PNCP, examina itens e decide quais licitações merecem análise completa.
3. **Leitura.** Edital, termo de referência e anexos (PDF, DOCX, XLSX, ZIPs expandidos). Itens publicados só com o nome ("cabo elétrico flexível") ganham a especificação lida no TR.
4. **Veredito.** Cada exigência é comparada com cada atributo do produto. Quatro estados por item: **compatível**, **parcial**, **indeterminado**, **incompatível**. Nunca "atende" sem prova.
5. **Dossiê e decisão.** Classificação da oportunidade (publicada, planejada, indireta em obra), comprador provável, prioridade 0–100, riscos, próximos passos — e a decisão humana de seguir ou descartar.

<details>
<summary><b>Exemplo real de entrada e saída</b> — Goianira/GO, PE 038/2026, item 1 (modo determinístico, 2,8 s)</summary>

**Entrada** (descrição do item no PNCP, 1.125 unidades a R$ 311,50):

> LUMINÁRIA PÚBLICA LED 100 WTS, POTÊNCIA 100 WTS, COR 5000K LUZ BRANCA FRIA, TENSÃO DE OPERAÇÃO AUTOVOLT (100V-277) […] EFICIÊNCIA LUMINOSA 140LM/WATT, FLUXO LUMINOSO 14000 LM […] ÍNDICE DE PROTEÇÃO IP 66, VIDA ÚTIL 50,000 HORAS […] 05 ANOS DE GARANTIA […] OBRIGATÓRIO APRESENTAÇÃO DO TERMO DE GARANTIA, REGISTRO DE INMETRO, ENSAIOS E CURVA FOTOMÉTRICA IES.

**Saída**: 27 requisitos (25 da descrição, 2 encontrados pelo Investigador no edital: prazo de 10 dias e amostra). Três candidatos da categoria, cada requisito com o trecho que o originou:

| Produto | Veredito | Por quê |
|---|---|---|
| LPL-100-50K | ✅ **COMPATÍVEL** | 100 W, 5000 K, 145 lm/W ≥ 140, 14.500 lm ≥ 14.000, IP66, IK09 ≥ IK08, 60.000 h, 5 anos, INMETRO, dimerizável, tomada para relé |
| LPL-100-50K-PRO | ⚪ **INDETERMINADO** | tecnicamente superior (175 lm/W, IK10), mas o catálogo **não informa a garantia** exigida de 5 anos |
| LPL-150-50K-PRO | 🔴 **INCOMPATÍVEL** | 150 W quando o edital pede 100 W; fator de potência 0,96 < 0,98 |

107 evidências na análise, **107 conferidas literalmente** no documento de origem. Dossiê completo em [`docs/exemplo_dossie_goianira.md`](docs/exemplo_dossie_goianira.md).
</details>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/itens_dark.png">
    <img src="docs/images/itens_light.png" alt="Itens da licitação com o veredito e o produto sugerido" width="920">
  </picture>
</p>

## Arquitetura agêntica

**Legenda de status**, usada em todo este documento: ✅ roda hoje · 🟡 parcial · ⬜ planejado (F1–F4, ver [roadmap](#status-e-roadmap)).

O ObraNexo é **IA-first**: os agentes conduzem o trabalho de fronteira — o que buscar, o que abrir, o que ler, onde investigar, como ranquear. O que os torna confiáveis é o **núcleo verificável** por onde toda proposta de um modelo precisa passar antes de virar fato. Esse núcleo não é uma limitação da IA; é o que permite deixá-la agir com autonomia.

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#e2f4f2','primaryTextColor':'#10222f','primaryBorderColor':'#00ab9f','lineColor':'#7d8b96','edgeLabelBackground':'#f1f3f3','fontSize':'14px','clusterBkg':'transparent','clusterBorder':'#7d8b96','titleColor':'#7d8b96'}}}%%
flowchart TB
  subgraph ORQ[" Orquestração · agentes de fronteira (decidem o que fazer) · grafo durável com checkpoints e pausas para revisão ⬜ F2 "]
    direction LR
    PR[🧭 Prospector ✅<br/>escolhe termos, abre licitações,<br/>decide o que analisar a fundo]:::ag
    AS[💬 Assistente ✅<br/>conversa com dados<br/>ao vivo do PNCP]:::ag
    MO[📡 Monitor ⬜ F2<br/>ingestão contínua,<br/>retificações e alertas]:::plan
    CU[🗂️ Curador de catálogo 🟡<br/>ficha do fabricante → atributos ✅<br/>lacunas que geram INDETERMINADO ⬜]:::ag
  end
  subgraph AN[" Análise de uma licitação · agentes especialistas "]
    direction LR
    AT[📑 Analista Técnico ✅<br/>requisitos em lote,<br/>com trecho literal]:::ag
    ES[🔍 Especificador ✅<br/>lê o TR dos itens<br/>publicados só com o nome]:::ag
    IN[🕵️ Investigador ✅<br/>ferramentas sobre os anexos:<br/>buscar, ler página, registrar]:::ag
    HB[📜 Habilitação ⬜ F2<br/>checklist documental<br/>e prazos do edital]:::plan
    VE[🛡️ Verificador ✅<br/>reconfere citações, conflitos,<br/>confiança, parecer]:::ag
    PL[🧠 Planejador ✅<br/>resumo executivo,<br/>riscos, próximos passos]:::ag
    AT --> ES --> IN --> VE --> PL
    IN -.-> HB
  end
  subgraph NUC[" Núcleo verificável · o que torna o veredito auditável "]
    direction LR
    N1[Validação por tipo e faixa<br/>de todo valor proposto por IA ✅]:::core
    N2[Motor de regras determinístico<br/>ATENDE · NÃO ATENDE · INDETERMINADO ✅]:::core
    N3[Citação conferida no documento<br/>no ato do registro, similaridade ≥ 90 ✅]:::core
  end
  subgraph MEM[" Memória e estado "]
    direction LR
    M1[(Estado da análise<br/>JSON ✅ → Postgres com checkpoints ⬜)]:::mem
    M2[(Memória da empresa<br/>catálogo ✅ · perfil 🟡 · decisões ⬜)]:::mem
    M3[(Índice de itens do PNCP<br/>busca híbrida, pgvector ⬜)]:::mem
  end
  subgraph INF[" Plataforma "]
    direction LR
    TR[🧰 Ferramentas<br/>por agente ✅ → registro único MCP ⬜]:::inf
    GW[🔀 Gateway de modelos<br/>3 provedores com reserva ✅<br/>roteamento por tarefa e lote ⬜]:::inf
    OB[📈 Observabilidade e avaliação<br/>trilha por análise ✅ · benchmark com trava no CI ✅<br/>OTel + Langfuse ⬜]:::inf
  end
  PR -- analisar_a_fundo --> AN
  AS -- analisar_a_fundo --> AN
  AN --- NUC
  AN --- MEM
  ORQ --- INF
  classDef ag fill:#e2f4f2,stroke:#00ab9f,color:#10222f
  classDef plan fill:#f1f3f3,stroke:#a5b0b8,color:#4b5b67,stroke-dasharray:5 4
  classDef core fill:#00ab9f,stroke:#00756c,color:#ffffff
  classDef mem fill:#0b2a3c,stroke:#0b2a3c,color:#ffffff
  classDef inf fill:#ffffff,stroke:#0b2a3c,color:#10222f
```

### Os agentes

Três agentes conduzem loops de ferramentas (decidem a ordem e a profundidade do trabalho); os demais são especialistas chamados pelo pipeline com saída estruturada validada por esquema.

| Agente | Papel | Ferramentas | Limites e memória | Status |
|---|---|---|---|---|
| 🧭 **Prospector** | Lê o catálogo, escolhe os termos, busca pregões abertos no PNCP, examina itens, decide quais analisar a fundo e entrega um ranking justificado | `buscar_licitacoes_abertas` · `ver_itens` · `analisar_a_fundo` · `concluir` | 16 passos; até 5 análises completas; ids inventados são descartados; ranking que contradiz a análise volta com os fatos | ✅ |
| 🕵️ **Investigador** | Procura nos anexos a especificação que falta e as exigências gerais do edital (garantia, prazo, amostra, INMETRO, ensaios) | `listar_documentos` · `buscar_trechos` · `ler_pagina` · `registrar_requisito` · `concluir_investigacao` | 12 passos (+2 por item sem spec, máx. 24); orçamento próprio de tokens; **citação conferida no ato do registro**: trecho inexistente volta como erro para o agente corrigir | ✅ |
| 💬 **Assistente** | Conversa em linguagem natural com dados ao vivo: busca licitações, consulta o catálogo e as análises salvas, dispara análises | `buscar_licitacoes_abertas` · `ver_itens` · `consultar_catalogo` · `analises_salvas` · `detalhar_analise` · `analisar_a_fundo` | 8 chamadas de ferramenta por mensagem; histórico por sessão | ✅ |
| 📑 **Analista Técnico** | Extrai requisitos canônicos dos itens, em lotes de até 10, cada um com o trecho literal | saída estruturada (Pydantic) | regras pt-BR sempre rodam; o que só a IA achou entra como desejável | ✅ |
| 🔍 **Especificador** | Localiza as páginas do TR que tratam dos itens publicados só com o nome e lê todas de uma vez | saída estruturada | trecho precisa existir no documento e no bloco daquele item | ✅ |
| 🛡️ **Verificador** | Reconfere todas as citações, detecta conflitos entre fontes, atribui confiança e escreve o parecer para revisão humana | regras + parecer em texto | confiança baixa → fila de revisão | ✅ |
| 🧠 **Planejador** | Resumo executivo, riscos e próximos passos, só a partir dos fatos já verificados | saída estruturada | qualificação (tipo, comprador, prazo, prioridade) vem de regras | ✅ |
| 🗂️ **Curador de catálogo** | Lê a ficha do fabricante (link, PDF, DOCX, XLSX, texto) e propõe produtos com atributos validados; vai apontar as lacunas do catálogo que geram INDETERMINADO e sugerir fichas | saída estruturada | usuário revisa antes de adicionar | 🟡 |
| 📡 **Monitor** | Ingestão contínua por UF e categoria, retificações de edital, alertas de novas oportunidades aderentes | coleta agendada · índice de itens | — | ⬜ F2 |
| 📜 **Habilitação** | Checklist documental do edital (certidões, atestados, amostra, prazos) cruzado com o que a empresa tem | leitura do edital · memória da empresa | — | ⬜ F2 |
| 🏗️ **Rastreador de obras** | Em oportunidades indiretas, identifica a construtora vencedora na ata e no contrato e sugere o contato | PNCP (atas, contratos) | — | ⬜ F3 |
| 💰 **Precificação** | Histórico de preços homologados por item e órgão para apoiar a proposta — **nunca dá lance** | PNCP (resultados) · índice de itens | — | ⬜ F4 |

### Núcleo verificável

Toda proposta de um modelo passa por três portas antes de virar fato. É isso que permite dar autonomia aos agentes.

| Porta | O que faz | Exemplos reais, do teste cego |
|---|---|---|
| **Validação por tipo e faixa** (`rules/validar.py`) | cada valor proposto é checado contra o tipo e a faixa plausível do atributo | rejeitados: `cct_k = "branca fria"`, `tensao_v = 600–1000` (era isolação de cabo), `material_corpo = "PRETA"`, `irc = 0,7` |
| **Citação conferida** (`evidence/verify.py`) | o trecho literal precisa existir na página citada (similaridade ≥ 90); conferido no registro e de novo pelo Verificador | 107/107 em Goianira, 72/72 em Itaberaí, 62/62 em Aruanã |
| **Motor de regras** (`rules/compare.py`) | compara cada requisito com cada atributo: número com tolerância, faixa que precisa cobrir, IP/IK ordinais, booleanos, texto, exigências documentais | IP65 < IP66 → não atende; garantia ausente no catálogo → indeterminado, nunca "atende" |

Agregação por item: qualquer obrigatório não atendido → **INCOMPATÍVEL**; obrigatório sem informação → **INDETERMINADO**; só desejáveis falhando → **PARCIAL**; todos os obrigatórios atendidos → **COMPATÍVEL**.

### Orquestração, estado e memória

| Dimensão | Hoje ✅ | Produção |
|---|---|---|
| Orquestração | sequência explícita em Python (`agents/pipeline.py`); nós com fronteiras claras; jobs em threads com eventos SSE | grafo durável (LangGraph) com checkpoints no Postgres: retomar após falha, pausar para revisão humana, reexecutar um nó ⬜ F2 |
| Estado da análise | JSON por análise: itens, requisitos, correspondências, evidências, conflitos, lacunas, trilha de eventos | Postgres com isolamento por empresa (RLS) ⬜ F1–F2 |
| Memória da empresa | catálogo persistido; UFs atendidas e raio logístico | decisões "seguir/descartar" que recalibram a prioridade; documentos de habilitação; histórico de propostas ⬜ F2 |
| Memória de mercado | pacotes congelados de licitações; cache do PNCP | índice de itens com busca híbrida (texto + vetorial, pgvector); histórico de preços ⬜ F2–F4 |
| Ferramentas | definidas por agente, com esquema `strict` | registro único no padrão MCP, com permissões por agente ⬜ F2 |
| Modelos | Gemini, Groq e Anthropic pela mesma interface; reserva automática em 429/503/timeout; quarentena de 10 min; cache em disco por entrada | gateway com roteamento por tarefa (extração em lote no modelo barato, raciocínio no forte), Batch API, orçamento por cliente ⬜ F3 |

### Guardrails e revisão humana

- Documentos e descrições entram **como dados** (`<documento>`, `<item>`), nunca como instruções.
- **Nenhum agente tem ferramenta de ação externa**: não envia proposta, não dá lance, não participa de licitação.
- Saída de modelo sempre validada por esquema (Pydantic, `strict: true`); valor fora do tipo ou da faixa é descartado com registro.
- Limites de passos, de tokens e de análises por prospecção; orçamento proporcional ao número de itens.
- Requisito tirado **só** pela IA da descrição entra como desejável: pode deixar o item parcial, nunca o derruba sozinho. Especificação do TR com citação conferida é exigência de verdade.
- **Pontos de revisão humana:** revisão dos produtos propostos pela ficha técnica ✅ · aprovar/rejeitar/comentar o dossiê ✅ · fila de confiança baixa 🟡 · pausa no grafo antes de análises caras e feedback que recalibra a prioridade ⬜ F2.

### Observabilidade e avaliação

- **Hoje ✅:** trilha completa de cada análise (nó, mensagem, modelo, item, documento), visível na interface e via SSE; contagem de chamadas, tokens e custo por modelo; benchmark contra gabaritos revisados (`eval/run_benchmark.py`); testes de regressão gerados a partir de cada defeito encontrado em dados reais; **CI em todo PR** (lint, testes e o benchmark como trava: se uma métrica cair abaixo do mínimo em `eval/limiares.json`, o PR fica vermelho).
- **Produção ⬜:** OpenTelemetry + Langfuse por agente e por cliente; conjunto rotulado por duas pessoas com concordância medida (F1); amostragem revisada em produção e monitor de deriva da qualidade (F3).

### Decisões de projeto

| Decisão | Por quê |
|---|---|
| **Agentes, e não um pipeline fixo, para prospecção e investigação** | São tarefas de busca em aberto: os termos certos dependem do catálogo, a licitação certa depende dos itens, e a especificação que falta pode estar em qualquer anexo. Um pipeline fixo com palavras-chave enxerga ~10% do mercado (medição própria). |
| **Regras decidem a compatibilidade, a IA interpreta** | "IP65 atende IP66?" tem resposta certa e precisa ser a mesma sempre. O veredito determinístico é auditável, testável e explicável linha a linha. No teste cego, um valor inventado pelo modelo derrubava a análise inteira; hoje é descartado e registrado. |
| **Citação conferida no ato do registro** | Verificar só no fim deixa o agente seguir por um caminho errado. Devolver o erro na hora faz o agente corrigir a si mesmo e barra alucinação de trecho na origem. |
| **Três provedores pela mesma interface** | Nível gratuito instável (429/503) não pode derrubar uma demo nem um cliente. Troca de modelo é configuração, não reescrita. |
| **Máquina de estados em Python puro na v0.1, grafo durável depois** | O roadmap previa LangGraph; o plano B (loop simples) entregou o hackathon sem fechar a porta: os nós já têm fronteiras claras e viram nós do grafo. |
| **Sem busca vetorial na v0.1** | Primeiro provar o veredito com prova; o índice semântico entra quando a ingestão contínua existir (F2) e passa a atacar os 90% invisíveis. |
| **Modo determinístico sem chave de API** | A demo e os testes nunca dependem de cota de terceiros; o núcleo verificável roda sozinho. |

### Uma prospecção real atravessando o sistema

```mermaid
%%{init: {'theme':'base','themeVariables':{'actorBkg':'#0b2a3c','actorTextColor':'#ffffff','actorBorder':'#0b2a3c','actorLineColor':'#7d8b96','signalColor':'#7d8b96','signalTextColor':'#7d8b96','noteBkgColor':'#e2f4f2','noteTextColor':'#10222f','noteBorderColor':'#00ab9f','labelBoxBkgColor':'#f1f3f3','labelBoxBorderColor':'#7d8b96','labelTextColor':'#10222f','loopTextColor':'#7d8b96','activationBkgColor':'#00ab9f','activationBorderColor':'#00756c','sequenceNumberColor':'#ffffff','fontSize':'14px'}}}%%
sequenceDiagram
  autonumber
  actor U as Fornecedor
  participant P as Prospector (agente)
  participant T as Ferramentas · PNCP
  participant A as Análise (Analista · Especificador · Investigador)
  participant N as Núcleo verificável (validação · citação · regras)
  participant V as Verificador · Planejador
  U->>P: "Prospecte em GO nos próximos 30 dias"
  P->>P: lê o catálogo e escolhe os termos de busca
  P->>T: buscar_licitacoes_abertas(uf, termos)
  T-->>P: ~450 pregões abertos → 18 candidatos
  P->>T: ver_itens(contratação)
  T-->>P: 206 itens
  P->>A: analisar_a_fundo(contratação, motivo)
  A->>A: baixa edital, TR e anexos (PDF, DOCX, XLSX, ZIP)
  A->>N: requisitos propostos pela IA, cada um com trecho literal
  N-->>A: valor fora do tipo ou da faixa → descartado
  loop Investigador · até N passos, orçamento próprio de tokens
    A->>N: registrar_requisito(item, atributo, valor, trecho)
    N-->>A: trecho não existe no documento → erro devolvido ao agente
  end
  N->>N: motor de regras: ATENDE · NÃO ATENDE · INDETERMINADO
  N->>V: correspondências + evidências verificadas
  V-->>P: resultado por item, confiança, prioridade
  P->>P: concluir(ranking)
  Note over P,N: ranking que contradiz a análise volta ao agente com os fatos
  P-->>U: ranking justificado + dossiês com prova
  U->>V: seguir · descartar · comentar (revisão humana)
  Note over U,V: decisão que recalibra a prioridade ⬜ F2
```

Os números do diagrama são de uma execução real em 24/10/2026: 9 páginas e cerca de 450 pregões com propostas abertas em GO; 18 candidatos pelos termos de iluminação e material elétrico; Anápolis com 206 itens. Fontes dos diagramas em [`docs/diagrams/`](docs/diagrams/).

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/trilha_dark.png">
    <img src="docs/images/trilha_light.png" alt="Trilha do agente: cada etapa da análise registrada com documento, página e item" width="920">
  </picture>
  <br>
  <sub>Trilha do agente: cada passo da análise fica registrado e visível.</sub>
</p>

## Diferenciais

O que é difícil de copiar não é "ler edital com IA" — isso virou padrão de mercado. É a combinação:

1. **Veredito por atributo contra o catálogo, com quatro estados.** Não "este edital parece relevante", mas "o LPL-100-50K atende os 25 requisitos do item 1; o PRO fica indeterminado porque falta a garantia na ficha".
2. **Prova literal em cada conclusão, conferida duas vezes.** Trecho, documento e página. Quem revisa clica e vê.
3. **Indeterminado explícito.** O sistema diz o que não sabe e onde procurou. É o estado que gera confiança e, no produto, puxa o cliente a completar o catálogo.
4. **Leitura item a item que acha a demanda escondida.** Os ~90% de pregões com itens elétricos sem menção no objeto só aparecem lendo os itens.
5. **Demanda indireta em obras.** Concorrência de obra pública não lista luminárias nos itens; o sistema varre projetos e memoriais e aponta a construtora como comprador provável.
6. **Vertical em material elétrico e iluminação.** Taxonomia de 32 atributos (potência, fluxo, eficiência, CCT, IRC, IP, IK, DPS, seção, tipo de cabo…) com regras de comparação específicas. O motor é genérico; a taxonomia é o ativo.
7. **Autonomia com freios auditáveis.** Agentes decidem; validação, citação e regras garantem; a pessoa aprova.

## Validação e resultados

Só dados reais. Tudo abaixo é reproduzível a partir deste repositório, em modo determinístico, sem chave de API.

| O quê | Resultado | Como conferir |
|---|---|---|
| Testes automatizados | **112 passando** (unitários + API), lint limpo (ruff); rodam em todo PR no CI, em Linux | `pytest -m "not integracao"` · [Actions](https://github.com/kauandivino/obranexo/actions/workflows/ci.yml) |
| Benchmark contra gabaritos revisados | 2 contratações, 9 itens e 8 pares item × produto: **100% de acerto por item, 100% nos pares, 100% de rastreabilidade** | `python eval/run_benchmark.py` · [`docs/benchmark_resultado.json`](docs/benchmark_resultado.json) |
| Tempo | 5 s para os 2 casos em modo determinístico; 55 s com Gemini (2 chamadas) | idem |
| Teste cego | **5 pregões abertos nunca vistos**, 133 itens, rodados sem ajuste prévio; 10 defeitos encontrados e corrigidos, cada um virou teste de regressão; rastreabilidade 100% nas duas rodadas | [`docs/teste_cego_2026-10-23.md`](docs/teste_cego_2026-10-23.md) · `tests/test_regressao_teste_cego.py` |
| Busca ao vivo no PNCP | 24/10/2026: 9 páginas, ~450 pregões abertos em GO em 44 s; 18 candidatos pelos termos de iluminação; detalhe de uma licitação com 206 itens em 1,4 s | `obranexo abertas --uf GO` |
| Casos reais congelados | 9 contratações do PNCP (R$ 1,4 mi a R$ 32 mi), 343 itens, 170 anexos | `obranexo casos` |

**Limites honestos desses números.** O benchmark de 100% é **dentro da amostra**: os 2 casos rotulados foram usados no desenvolvimento e o gabarito é da própria equipe. Os 5 casos do teste cego estão rotulados pelo sistema, com **gabarito humano pendente** em [`docs/teste_cego_rotulagem.csv`](docs/teste_cego_rotulagem.csv) — não foram rotulados pela mesma pessoa que corrigiu o código, para o benchmark não virar circular. O custo em dólar aparece como zero porque os modelos usados estão no nível gratuito; o custo estimado por análise com preços de tabela é de R$ 0,02 a R$ 0,48.

**Metodologia planejada (F1–F2).** Gabarito duplo (duas pessoas, divergências resolvidas, concordância medida) para 10 ou mais contratações e 150 a 300 pares; métricas-alvo do roadmap: precisão de COMPATÍVEL ≥ 85%, recall de itens relevantes ≥ 80%, detecção de incompatibilidade obrigatória ≥ 90%, rastreabilidade ≥ 95%, consistência entre execuções ≥ 90%, tempo ≤ 3 min; cronometragem do trabalho manual contra o assistido com 5 a 10 empresas no piloto.

## Modelo de negócio e mercado

Resumo do [Business Model Canvas](https://kauandivino.github.io/obranexo/) (versão interativa; texto completo com fontes em [`BMC_ObraNexo.txt`](BMC_ObraNexo.txt)) e do [relatório de modelo de negócio](reports/Modelo%20de%20negócio%20ObraNexo.md). Natureza de cada número: **[FATO]** publicado com fonte · **[DADO PRÓPRIO]** medido pela equipe no PNCP · **[ESTIMATIVA]** cálculo da equipe · **[PREMISSA]** hipótese a validar.

| | |
|---|---|
| **Mercado** | R$ 1 trilhão em compras no PNCP em 2025 [FATO, MGI] → R$ 6,1–6,4 bi/ano em itens elétricos [DADO PRÓPRIO] → 7–13 mil empresas-alvo e R$ 51–96 mi/ano de mercado de software [ESTIMATIVA] → cenário-base de 250 clientes e R$ 1,8 mi de ARR em 36 meses [PREMISSA] |
| **Cliente núcleo** | distribuidores e atacadistas de material elétrico (CNAE 4673-7/00): 3,4–4,2 mil empresas, em geral ME/EPP [FATO]; persona: sócio-gerente ou vendedor técnico que acumula a licitação |
| **Planos** [PREMISSA] | Radar grátis (1 UF, 3 análises/mês) · Essencial R$ 397/mês · Profissional R$ 897/mês (todas as UFs, obras, 3 usuários) · Assessoria R$ 1.490–2.490/mês (5–10 CNPJs) · Fabricante/Enterprise sob consulta · créditos avulsos R$ 39/análise. Âncoras: concorrentes cobram R$ 101–1.397/mês [FATO] |
| **Economia unitária** | IA custa R$ 0,02–0,48 por análise [ESTIMATIVA sobre preços oficiais]; margem bruta-alvo 75–85%; custo interno evitado pelo cliente de R$ 110–700 por edital [ESTIMATIVA] |
| **Canais** | assessorias de licitação (multi-CNPJ, canal de revenda), radar gratuito que converte, fabricantes que querem a rede de revenda vendendo ao governo, Sebrae e feiras |
| **Impacto** | cada licitante qualificado a mais reduz o preço em ~3,4% [FATO, estudo europeu]; ganhar um contrato acelera o crescimento da empresa em 2,2 p.p. [FATO, NBER]; iluminação pública com ~80% dos 22 milhões de pontos sem LED [FATO]. ODS 7, 8, 9, 11, 12.7, 16 |
| **Validação com clientes** | [DADO NECESSÁRIO] entrevistas com fornecedores · [DADO NECESSÁRIO] disposição a pagar · [DADO NECESSÁRIO] piloto supervisionado — planejados para F1–F2 |

**Pedido do pitch:** piloto de 60 dias com 10 distribuidores de Goiás e apoio AKCIT/Embrapii para levar o MVP a produção.

## Status e roadmap

A visão é ampla; a execução começa pequena, verificável e orientada por resultados. Cada fase só avança quando o critério de saída é atingido.

| Fase | Período | Objetivo | Entregas principais | Critério de saída |
|---|---|---|---|---|
| **F0 · v0.1** Prova de conceito | 22–24/10/2026 | demo de ponta a ponta com dados reais | 7 agentes, PNCP ao vivo, 9 casos reais, catálogo por ficha, assistente, 3 provedores, benchmark, teste cego | os 7 critérios da demo rodam offline sem intervenção — **atingido ✅** |
| **F1 · v0.2** MVP robusto | 25/10–28/11/2026 | confiabilidade e primeira prova de valor | gabarito duplo em 10+ contratações; PostgreSQL + Alembic; login e isolamento por empresa; Docker; CI com benchmark como trava ✅; busca em todas as modalidades; temperatura 0 e versão de prompt no cache; preços reais dos modelos; logs estruturados; recalibração da prioridade; 5 entrevistas e 1–2 pilotos | roda na nuvem com Postgres; benchmark ≥ 10 contratações; ≥ 1 piloto com fornecedor real |
| **F2 · v0.3** Beta fechado | dez/2026–fev/2027 | plataforma agêntica e piloto em escala | grafo durável com checkpoints e pausas para revisão; registro MCP de ferramentas; Monitor (ingestão contínua, índice híbrido com pgvector, alertas); Habilitação; feedback que recalibra; fila com workers; OTel + Langfuse; PCA, OCR e tabelas; **piloto de 60 dias com 10 distribuidores** | precisão ≥ 95% fora da amostra; rastreabilidade 100%; custo medido < R$ 1/análise; 95% das análises em < 3 min |
| **F3 · v1.0** Produção | mar–jun/2027 | operar com clientes pagantes | AWS como código (ECS, RDS + pgvector, S3, Bedrock); gateway de modelos com roteamento, lote e orçamento por cliente; RLS e anexos versionados; Rastreador de obras; planos e cobrança; LGPD documentada, pentest, trilha de auditoria; avaliação contínua em produção | 30 dias cumprindo as metas de serviço (99,5%, p95 < 90 s); margem 75–85% |
| **F4 · v1.x** Escala | 2º sem/2027 → | novas fontes, segmentos e agentes | Obrasgov e portais estaduais; Precificação com histórico de preços; grafo órgão–objeto–item–fornecedor; API pública e servidor MCP para CRM e assessorias; novos segmentos (hidráulica, climatização, incêndio) | churn < 3%/mês; LTV/CAC ≥ 3 |

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#e2f4f2','primaryTextColor':'#10222f','primaryBorderColor':'#00ab9f','lineColor':'#7d8b96','edgeLabelBackground':'#f1f3f3','fontSize':'14px','clusterBkg':'transparent','clusterBorder':'#7d8b96','titleColor':'#7d8b96'}}}%%
flowchart LR
  subgraph CLI[" Clientes "]
    direction TB
    W[🖥️ Web app ✅<br/>JS puro, sem build]:::inf
    API2[🔌 API pública e servidor MCP ⬜ F4<br/>para CRM e assessorias]:::plan
  end
  subgraph APP[" Aplicação · AWS, infraestrutura como código ⬜ F3 "]
    direction TB
    G[🚪 API FastAPI ✅<br/>login e isolamento por empresa ⬜ F1]:::inf
    Q[📬 Fila e workers ⬜ F2<br/>hoje: threads ✅]:::plan
    OR[🕸️ Orquestrador de agentes ⬜ F2<br/>grafo durável · checkpoints · pausas para revisão<br/>hoje: sequência fixa em Python ✅]:::plan
    GW[🔀 Gateway de modelos ✅<br/>roteamento, lote, cache,<br/>orçamento por cliente ⬜ F3]:::inf
  end
  subgraph DAT[" Dados "]
    direction TB
    PG[(🐘 PostgreSQL + pgvector ⬜ F1–F2<br/>hoje: JSON em disco ✅)]:::mem
    S3[(🗄️ Anexos versionados, S3 ⬜ F3<br/>hoje: pacotes congelados ✅)]:::mem
  end
  subgraph ING[" Ingestão "]
    direction TB
    PN[(🏛️ PNCP ✅)]:::mem
    IG[📡 Coleta agendada e índice de itens ⬜ F2<br/>hoje: busca ao vivo com cache ✅]:::plan
    OUT[(Obrasgov e portais estaduais ⬜ F4)]:::plan
  end
  subgraph OBS[" Qualidade "]
    direction TB
    OT[📈 OpenTelemetry + Langfuse ⬜ F2<br/>hoje: trilha por análise ✅]:::plan
    EV[🧪 Avaliação contínua<br/>benchmark com trava no CI ✅<br/>amostragem em produção ⬜ F3]:::plan
  end
  LLM{{Gemini · Groq · Anthropic ✅<br/>Bedrock ⬜ F3}}:::inf
  W --> G
  API2 --> G
  G --> Q --> OR --> GW --> LLM
  OR --- PG
  OR --- S3
  PN --> IG --> PG
  OUT -.-> IG
  OR -.-> OT
  OR -.-> EV
  classDef plan fill:#f1f3f3,stroke:#a5b0b8,color:#4b5b67,stroke-dasharray:5 4
  classDef mem fill:#0b2a3c,stroke:#0b2a3c,color:#ffffff
  classDef inf fill:#e2f4f2,stroke:#00ab9f,color:#10222f
```

O plano de desenvolvimento detalhado, com cada item ligado ao status acima, está em [`docs/PLANO_DESENVOLVIMENTO.md`](docs/PLANO_DESENVOLVIMENTO.md); o roadmap original do MVP, em [`ROADMAP_MVP.txt`](ROADMAP_MVP.txt).

## Quickstart

Testado em Windows 11 com Python 3.12. Sem chave de API, tudo roda em **modo determinístico** (sem agentes de linguagem); com uma chave, os agentes entram.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env     # opcional: preencha GEMINI_API_KEY e/ou GROQ_API_KEY (ou ANTHROPIC_API_KEY)

obranexo servidor          # API + interface em http://127.0.0.1:8000 · documentação em /api/docs
```

Na interface: **Licitações → Goianira → Analisar** mostra a análise ao vivo com a trilha dos agentes; na análise, clique numa prova. Com chave de IA, **Prospecção → Buscar oportunidades** roda o agente contra o PNCP ao vivo.

```powershell
obranexo casos                            # as 9 licitações reais congeladas
obranexo analisar goianira_pe038_2026     # análise completa pela linha de comando (2,8 s sem IA)
obranexo abertas --uf GO                  # pregões com propostas abertas, ao vivo no PNCP
obranexo coletar 01291707000167 2026 75 meu_caso   # baixa e congela uma contratação

pytest -m "not integracao"                # 112 testes, sem chamar o LLM
pytest -m integracao -v                   # chama o provedor configurado (usa cota)
python eval/run_benchmark.py              # benchmark contra os gabaritos
python eval/run_benchmark.py --limiares eval/limiares.json   # a mesma trava de qualidade do CI
```

### Provedores de IA

| Provedor | Chave no `.env` | Modelos padrão | Observação |
|---|---|---|---|
| **Google Gemini** (padrão) | `GEMINI_API_KEY` | agentes `gemini-3.8-flash` → reserva `gemini-3.5-flash-lite`; extração `gemini-3.5-flash-lite` | nível gratuito; o cliente cai para o reserva em 429/503 e põe o modelo em quarentena por 10 min |
| **Groq** | `GROQ_API_KEY` | agentes `openai/gpt-oss-120b`; extração `openai/gpt-oss-20b`; reserva `llama-3.3-70b-versatile` | saída estruturada por `json_schema` quando o modelo suporta; lotes menores por causa do limite de tokens por minuto |
| **Anthropic** | `ANTHROPIC_API_KEY` | `claude-sonnet-5-5` / `claude-haiku-5-5` | `OBRANEXO_LLM_PROVIDER=anthropic` |

Com mais de uma chave, o provedor é escolhido no seletor **IA** da barra superior (ou por `POST /api/config/llm`); a troca faz uma chamada mínima de teste. Texto, saída estruturada validada por Pydantic e chamada de ferramentas têm a mesma interface em todos os provedores (`src/obranexo/llm/client.py`).

## Limitações conhecidas e próximos desafios

Encontradas em auditoria do código em 24/10/2026; todas têm item no plano de desenvolvimento.

| Limitação | Efeito | Correção |
|---|---|---|
| Busca só em pregão eletrônico (modalidade 6) | concorrências (obras), pregões presenciais e dispensas não entram na prospecção | parâmetro de modalidades · F1 |
| Tela de busca lê até 6 páginas; GO tinha 9 | cerca de um terço dos pregões abertos não aparece na interface (o Prospector lê 12) | limite dinâmico · F1 |
| Filtro do objeto por substring | ruído: "faróis em **LED**" num SUV, "controle de **lumin**osidade" em persianas | índice de itens com busca híbrida · F2 |
| Temperatura 0 só no Groq | reprodutibilidade depende do cache em disco | temperatura 0 em todos; versão do prompt na chave do cache · F1 |
| Um catálogo ativo por servidor | dois fornecedores na mesma instalação veriam o catálogo um do outro | login e isolamento por empresa · F1 |
| Categoria do produto precisa ser a chave exata (`luminaria_publica_led`) | planilha com "Luminária pública" não casa com nada, sem aviso | validação e sugestão na importação · F1 |
| Pesos da prioridade não calibrados | licitação encerrada (SRP) pode ficar acima de uma aberta | prazo aberto pesa mais; feedback recalibra · F1–F2 |
| Benchmark só com 2 casos internos | precisão fora da amostra ainda desconhecida | gabarito duplo dos 5 casos cegos + 3 novos · F1 |
| Custo exibido como zero (nível gratuito) | meta de custo não validada | preços reais dos modelos no `config.py` · F1 |
| 32 atributos, quase todos de iluminação | número de condutores, comprimento de braço, classe de encordoamento ficam de fora | taxonomia por categoria · F2 |
| Sem OCR, sem PCA, sem tabelas de PDF | editais digitalizados e demanda planejada não são lidos | F2 |
| Persistência em JSON; chat e jobs em memória | perde conversas ao reiniciar; não escala horizontalmente | Postgres, fila e workers · F1–F2 |

## Referência

<details>
<summary><b>Arquitetura da aplicação</b></summary>

```
navegador ──► web/ (HTML + CSS + JavaScript puro, ES modules, sem build)
                │  fetch / Server-Sent Events
                ▼
             FastAPI  src/obranexo/api/main.py  ──►  pipeline de agentes (thread em segundo plano)
                │                                     │
                ▼                                     ▼
       data/casos (PNCP congelado)         data/analises (JSON) · data/prospeccoes · data/llm_cache
```

O frontend não tem dependências externas nem etapa de build: o próprio FastAPI serve a pasta `web/`, e a demo funciona offline. Rotas da interface (hash): `#/inicio`, `#/catalogo`, `#/demandas`, `#/agente`, `#/agente/<id>`, `#/casos/<caso>`, `#/analises`, `#/analises/<id>`, `#/metricas`, `#/sobre`.
</details>

<details>
<summary><b>Endpoints da API</b></summary>

| Método | Rota | Para quê |
|---|---|---|
| GET | `/api/status` | versão, provedor/modelos de LLM (e provedores com chave), modo offline, contadores |
| POST | `/api/chat` | abre uma conversa com o assistente |
| POST | `/api/chat/{id}/mensagens` | envia uma pergunta; a resposta (texto + cartões) chega no evento `fim` de `/api/jobs/{job}/eventos` |
| GET | `/api/chat/{id}` | histórico da conversa |
| POST | `/api/config/llm` | troca o provedor de LLM (`gemini`, `groq`, `anthropic` ou `null`) |
| POST | `/api/config/llm/testar` | chamada mínima ao provedor ativo (confere chave, rede e modelo) |
| GET · POST · DELETE | `/api/catalogo` | catálogo ativo · enviar JSON/CSV/XLSX (multipart `arquivo`) · restaurar o demo |
| POST | `/api/catalogo/importar` | ficha técnica real (multipart `url`, `arquivo` ou `texto`) → produtos propostos pelo LLM, para revisão |
| POST · DELETE | `/api/catalogo/produtos` · `/api/catalogo/produtos/{sku}` | adicionar produtos revisados · remover (o catálogo fica salvo em disco) |
| POST | `/api/prospeccoes` | `{ufs, horizonte_dias, max_analises}` → inicia o Agente de Prospecção (202, devolve o job) |
| GET | `/api/prospeccoes` · `/api/prospeccoes/{id}` | histórico · ranking, buscas, candidatos e trilha de decisões do agente |
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
</details>

<details>
<summary><b>Casos reais congelados</b> (dados públicos do PNCP, coletados em 22–23/10/2026)</summary>

| Pasta | Contratação | O que demonstra |
|---|---|---|
| `goianira_pe038_2026` | Goianira/GO — PE 038/2026 — RP de luminárias LED (R$ 1,67 mi) | COMPATÍVEL, INCOMPATÍVEL e INDETERMINADO com evidências no edital; gabarito revisado |
| `aruana_pp005_2026` | Aruanã/GO — PP 005/2026 — luminárias LED 50/100/150 W (R$ 1,42 mi) | exigência de 170 lm/W derruba produtos comuns; gabarito revisado |
| `anapolis_pe_material_eletrico_2026` | Anápolis/GO — RP de material elétrico e iluminação pública (R$ 26,5 mi, 206 itens), escolhida e baixada pelo Agente de Prospecção | itens publicados só com o nome: o Especificador lê a especificação na relação de itens do TR (dentro de um ZIP) |
| `cego_*` (5 casos) | Pregões **com propostas abertas** em GO em 23/10/2026: refletores (Itumbiara), material elétrico (Itaberaí), iluminação de rodovia (Chapadão do Céu), iluminação pública (Cezarina), material de consumo (Base Aérea de Anápolis) | teste cego de robustez — `docs/teste_cego_2026-10-23.md`; gabarito humano pendente em `docs/teste_cego_rotulagem.csv` |
| `seinfra_basileu_franca_2026` | Estado de Goiás — Concorrência 02/2026 — obra da EFG Basileu França (R$ 31,98 mi) | classificação INDIRETA (o comprador é a construtora) e varredura de insumos elétricos nos projetos; dos 100 anexos, só edital, TR, ETP, orçamento e projeto elétrico foram congelados |
</details>

<details open>
<summary><b>Estrutura do repositório</b></summary>

```
src/obranexo/
  agents/
    prospector.py        Agente de Prospecção (loop de ferramentas sobre o PNCP)
    assistente.py        Assistente de conversa (ferramentas sobre PNCP, catálogo e análises)
    investigador.py      Agente Investigador (ferramentas sobre os documentos; citação conferida no registro)
    extrator.py          Analista Técnico: requisitos por regras + LLM em lote
    especificador.py     Especificador: lê o TR dos itens publicados só com o nome
    verificador.py       Verificador: citações, conflitos, confiança, parecer
    planejador.py        Qualificação (regras) + Planejador (LLM)
    pipeline.py          Orquestração explícita dos nós (v0.1; vira grafo durável em F2)
    contexto.py          Estado compartilhado da análise
    prompts.py           Prompts versionados e guardrails
  rules/
    extrair.py           Extração determinística de requisitos (pt-BR, formato CATMAT)
    compare.py           Motor de regras de compatibilidade (sem LLM)
    validar.py           Validação por tipo e faixa de todo valor proposto por IA
  evidence/verify.py     Verificação literal das citações (similaridade ≥ 90)
  catalog/               atributos canônicos, loader (JSON/CSV/XLSX), importação por ficha técnica
  connectors/pncp.py     Conector PNCP (cache, retentativas, cópia antiga se o portal falhar, pacotes congelados)
  documents/             PDF/DOCX/XLSX/ZIP → páginas → trechos; busca textual
  llm/client.py          Gemini, Groq e Anthropic pela mesma interface (cache, custo, reserva, quarentena)
  dossier/render.py      Dossiê em Markdown
  storage/store.py       Persistência JSON (v0.1 → PostgreSQL em F1)
  api/main.py            API FastAPI + servidor estático do frontend
  api/jobs.py            Execução em segundo plano com eventos SSE
  cli.py · config.py · models.py
web/
  index.html             casca da aplicação
  css/app.css            design system (tokens, tema claro/escuro, responsivo)
  js/app.js              roteador por hash
  js/api.js              cliente da API (fetch + SSE com fallback para polling)
  js/chat.js             painel do assistente
  js/charts.js · ui.js · format.js · markdown.js · tema.js
  js/views/              início, catálogo, demandas, prospecção, caso (execução ao vivo), análises, resultado, métricas, sobre
data/
  casos/<caso>/          pacotes congelados (contratacao.json, itens.json, documentos.json, arquivos/, gabarito.json)
  catalogo_demo/         catálogo demonstrativo (41 SKUs fictícios, com atributos completos e incompletos de propósito)
docs/
  fluxo_agentes.md       fluxo dos agentes em detalhe
  PLANO_DESENVOLVIMENTO.md  plano de desenvolvimento alinhado a este README
  diagrams/              fontes Mermaid dos diagramas (+ PNG claro/escuro)
  images/                capturas da interface
  teste_cego_*.{md,csv}  teste cego e planilha de rotulagem
  benchmark_resultado.json
eval/run_benchmark.py    benchmark contra gabaritos (com --limiares, trava de qualidade)
eval/limiares.json       mínimos por métrica usados pela trava
tests/                   112 testes (regras, agentes sem LLM, API, regressão do teste cego, integração com LLM)
.github/workflows/ci.yml lint, testes e benchmark como trava em todo PR (Linux, modo determinístico e offline)
pitch/                   planejamento, fala e slides do pitch
BMC_ObraNexo.txt · reports/ · research_notes/   modelo de negócio e pesquisa
```

**Estrutura-alvo** (F1–F3, incremental sobre a atual): `src/obranexo/graph/` (grafo durável, checkpoints, interrupções) · `tools/` (registro MCP) · `gateway/` (roteamento de modelos) · `ingest/` (coleta agendada, índice de itens) · `db/` (SQLModel + Alembic) · `observability/` · `infra/` (Docker, Terraform).
</details>

## Documentação

- [`docs/fluxo_agentes.md`](docs/fluxo_agentes.md) — fluxo dos agentes, ferramentas, guardrails
- [`docs/PLANO_DESENVOLVIMENTO.md`](docs/PLANO_DESENVOLVIMENTO.md) — plano de desenvolvimento por fase
- [`ROADMAP_MVP.txt`](ROADMAP_MVP.txt) — roadmap original do MVP (requisitos, stack, métricas, DoD)
- [`docs/teste_cego_2026-10-23.md`](docs/teste_cego_2026-10-23.md) — teste cego em 5 pregões abertos
- [`BMC_ObraNexo.txt`](BMC_ObraNexo.txt) · [`reports/`](reports/) · [`research_notes/`](research_notes/) — modelo de negócio, medição própria no PNCP, concorrentes, impacto
- [`pitch/`](pitch/) — planejamento e fala do pitch
- [`ObraNexo_PreProjeto_Documento_Norteador_v0.1.pdf`](ObraNexo_PreProjeto_Documento_Norteador_v0.1.pdf) — documento norteador

## Time e contato

Kauan Divino · Fabrycio Nakano · Victor Emanuel · Maykon Adriell

[contato.omniamind@gmail.com](mailto:contato.omniamind@gmail.com)

## Licença

Proprietária, conforme o edital do programa. Dados do PNCP são públicos e abertos por lei (Lei 14.133/2021, art. 174); catálogos pertencem a cada fornecedor e ficam isolados por empresa.

<p align="center"><sub>O governo já está comprando o que você vende. Só faltava alguém avisar.</sub></p>
