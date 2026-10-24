# Modelo de negócio ObraNexo: benchmarks de receita, custos, canais, parceiros e regulação

> Data da pesquisa: 24/10/2026. Câmbio usado: **US$ 1 = R$ 5,0377** (PTAX de venda de 23/10/2026, segundo [Piranot, 23/10/2026](https://www.piranot.com.br/2026/10/23/noticias/economia/dolar-ptax-fecha-em-r-50377-nesta-sexta-feira-23-10-2026-veja-a/); fonte secundária, conferir no boletim do BCB). Para contas rápidas, R$ 5,04.
> Aviso geral: muitos benchmarks de SaaS que aparecem em busca vêm de blogs secundários com atribuição inconsistente. Isso está marcado em cada item.

---

## 1. Modelos de preço em ferramentas de licitação (Brasil) e taxa de êxito das assessorias

### Takeaway
No Brasil, os softwares para licitantes cobram **assinatura de R$ 200 a R$ 500 por mês** por empresa, com desconto no plano anual, e reservam os recursos de IA para os planos mais caros. As assessorias cobram **mensalidade mais taxa de êxito**. Não existe percentual oficial: as simulações publicadas ficam em **2% a 3% do valor efetivamente recebido ou contratado**, e a mensalidade de referência é de cerca de R$ 2.000.

### Cited Findings
- **Siga Pregão (site oficial, segundo resumo de busca):** plano Basic a **R$ 397/mês**; Infinity Plus a **12x R$ 272,80 ou R$ 2.800 à vista por ano** (cerca de R$ 233/mês); Ultra a **12x R$ 584,57 ou R$ 6.000 à vista por ano** (cerca de R$ 500/mês). Só o Ultra traz conectores com ChatGPT, Claude e Gemini, monitoramento do chat do pregoeiro e o "Pagômetro". — [Siga Pregão, preços](https://www.sigapregao.com.br/precos/); [Siga Pregão, página de preços com IA](https://www.sigapregao.com.br/p/precos/)
- **Siga Pregão (agregador):** o B2B Stack lista um plano mensal "Ultimate" a R$ 497 e um anual a R$ 3.600. Esses valores divergem do site oficial. — [B2B Stack, Siga Pregão planos e preços](https://www.b2bstack.com.br/product/siga-pregao/planos-e-precos)
- **Siga Pregão** também vende um plano "Multiempresas", voltado a assessorias que atendem vários CNPJs, o que indica precificação por número de empresas atendidas. — [Siga Pregão Multiempresas](https://www.sigapregao.com.br/multiempresas/)
- **ConLicitação:** preço "sob consulta", sem valores públicos. — [B2B Stack, ConLicitação vs Siga Pregão](https://www.b2bstack.com.br/compare/conlicitacao-vs-siga-pregao)
- **Effecti:** os planos são divididos por volume de participação (começam no "Iniciante", para quem disputa poucas licitações por mês), mas não há preço público. — [Effecti, plataforma e planos](https://effecti.com.br/plataforma/)
- **Acumi** (concorrente que se posiciona como "análise do edital campo a campo"): o resumo de busca cita Basic a R$ 397/mês e Pro a R$ 197/mês, com 7 dias grátis. Os valores parecem invertidos ou desatualizados, então é preciso conferir. — [Acumi, comparativo com Siga Pregão](https://acumi.com.br/comparar/siga-pregao)
- **Taxa de êxito das assessorias:** "Não existe um percentual oficial de comissão". As simulações do artigo usam **3%** (R$ 24 mil de meta variável anual sobre R$ 800 mil de base elegível) e **2%** sobre R$ 100 mil recebidos pelo cliente no mês, o que dá R$ 2.000 de comissão. O modelo híbrido simulado tem **R$ 2.000 de mensalidade mais R$ 2.000 de comissão, total de R$ 4.000/mês**. Um serviço avulso simulado custa no mínimo R$ 1.700 (8 h × R$ 150/h + R$ 200 de custos + R$ 300 de reserva). Atualizado em 03/08/2026. — [Effecti, quanto cobrar por consultoria em licitações](https://effecti.com.br/comissao-consultoria-licitacoes/)
- O modelo mais comum entre assessorias estruturadas é o **híbrido (retainer mais êxito)**. O contrato precisa definir o evento gatilho (adjudicação, homologação, assinatura, empenho, ordem de fornecimento, faturamento ou recebimento) e a base de cálculo, porque um processo pode ser homologado sem nunca virar contrato. Êxito puro transfere ao consultor o risco de trabalhar meses sem receber. — [Siga Pregão, como o assessor pode cobrar](https://www.sigapregao.com.br/como-o-assessor-de-licitacoes-pode-cobrar-pelo-servico/); [Effecti, comissão](https://effecti.com.br/comissao-consultoria-licitacoes/)
- Um modelo de contrato público prevê comissão percentual sobre contratos futuros mais mensalidade fixa (documento no Scribd, não verificado). — [Scribd, contrato de assessoria com êxito](https://www.scribd.com/document/569771655/CONTRATO-DE-PRESTACAO-DE-SERVICOS-DE-ASSESSORIA-EM-LICITACOES-EXITO)
- A AM Consulte publica uma página de preços de assessoria; o conteúdo não foi extraído. — [AM Consulte, preços](https://amconsulte.com.br/index.php/precos/)

### Inferences
- **Âncora de preço:** quem disputa licitação já paga de R$ 200 a R$ 600 por mês por software de busca e lances. Um plano de entrada do ObraNexo entre **R$ 297 e R$ 497/mês** fica dentro da faixa conhecida. A diferenciação (análise item a item contra o catálogo, com evidência literal) sustentaria um plano Pro de **R$ 790 a R$ 1.490/mês** com cota de análises.
- **Modelo sugerido:** assinatura em degraus com **cota de análises por mês**, mais créditos avulsos de análise e um plano multi-CNPJ para assessorias, seguindo o padrão do "Multiempresas". Taxa de êxito própria (por exemplo, 0,5% a 1% do valor homologado) é tecnicamente possível, mas exige prova de causalidade e cobrança pós-contrato, com o mesmo risco que as assessorias relatam. Faz mais sentido como **upsell opcional** ou por meio de assessorias parceiras que já cobram êxito.
- Para assessorias, o ObraNexo substitui horas de análise que custam cerca de R$ 150/h. Se poupar 8 h por edital, uma análise vale até cerca de R$ 1.200 em custo interno evitado, o que justifica preço por crédito bem acima do custo de inferência.

### Gaps
- Não encontrei preços públicos atualizados de Effecti, ConLicitação, Licitanet, Alerta Licitação ou BLL. Também não encontrei preços de ferramentas estrangeiras de govtech/tender (GovSpend, GovWin/Deltek, Tenders Electronic Daily, Tussell); nenhuma foi pesquisada por limite de tempo.
- Não há estudo sistemático (fonte independente) sobre a taxa de êxito média das assessorias. As faixas de 2% a 3% vêm de simulações em conteúdo de marketing.

---

## 2. Benchmarks de SaaS B2B para SMB (ARPA, churn, CAC payback, LTV/CAC) e margem bruta de SaaS nativo de IA

### Takeaway
Para SMB, os benchmarks mais citados são **churn mensal de logos de 2% a 7%** (abaixo de 2% é bom), **CAC payback de 8 a 15 meses** e **LTV/CAC alvo de 3:1** (medianas reais entre 2:1 e 4:1). Produtos nativos de IA têm margem bruta de **cerca de 45% a 60%**, contra 75% a 85% do SaaS tradicional, porque a inferência entra no CPV.

### Cited Findings
- **Churn SMB:** self-serve SMB fica em **3% a 7% ao mês (31% a 58% ao ano)**. — [Stealth Agents, SaaS startup metrics 2026](https://stealthagents.com/research/saas-startup-metrics-statistics-2026) (blog secundário)
- **Churn de self-serve B2B abaixo de US$ 1M de ARR:** **3,0% a 6,5% ao mês**, atribuído à ChartMogul. — [Data-Mania, B2B SaaS benchmarks 2026](https://www.data-mania.com/blog/b2b-saas-benchmarks-2026-annual-report/) (secundário)
- **Faixas de referência para SMB:** abaixo de **2,0% ao mês é bom**; de 2% a 4% é aceitável. — [SaasDash, benchmarks 2026](https://saasdash.ai/blog/saas-metrics-benchmarks-2026)
- **CAC payback:** a mediana de B2B SaaS no FY2025 foi de **16 meses** (18 em 2024), e a de **SMB fica em 8 a 12 meses** (Benchmarkit × Aleph, segundo secundário). — [Data-Mania](https://www.data-mania.com/blog/b2b-saas-benchmarks-2026-annual-report/). Outra fonte cita mediana Benchmarkit 2025 de **20 meses**, em conflito com a anterior. — [Stealth Agents](https://stealthagents.com/research/saas-startup-metrics-statistics-2026). Faixas de SMB de 6 a 14 meses. — [Proven SaaS, CAC payback](https://proven-saas.com/benchmarks/cac-payback-benchmarks)
- **LTV/CAC:** a regra de bolso é **3:1** como piso saudável. Medianas reportadas: **2,1:1** (atribuída à SaaS Capital), **4,1x** (Benchmarkit × Aleph) e **2,8:1** para SMB. — [Stealth Agents](https://stealthagents.com/research/saas-startup-metrics-statistics-2026); [Data-Mania](https://www.data-mania.com/blog/b2b-saas-benchmarks-2026-annual-report/); [Optif, LTV benchmark de 939 empresas](https://optif.ai/learn/questions/b2b-saas-ltv-benchmark/)
- **CAC SMB (EUA):** estimativas vão de US$ 200–500 até US$ 1.100–1.400 (atribuído à OpenView) e US$ 4.800 de mediana, numa dispersão muito grande. — [LTV CAC Book, CAC benchmarks 2026](https://ltvcacbook.com/blog/cac-benchmarks-2026); [Optif](https://optif.ai/learn/questions/b2b-saas-ltv-benchmark/)
- **Margem bruta de produtos de IA (ICONIQ, State of AI):** média de **cerca de 45% em 2025**, com projeção de **cerca de 52–53% em 2026** e **59% em 2027**; 41% em 2024. Faixas por perfil: cerca de 80% para SaaS "AI-augmented", 60–79% para "AI-enabled" e **50–59% para "AI-native"**. Inferência responde por cerca de 20% dos custos do produto de IA antes do lançamento e 23% em escala (fatia do orçamento de IA, não da receita). — [CloudZero, AI gross margin](https://www.cloudzero.com/blog/ai-gross-margin/); [Jeff Brokaw, AI gross margins](https://jeffbrokaw.com/blog/ai-gross-margins/); [SoftwareSeni](https://www.softwareseni.com/why-ai-gross-margins-are-so-much-lower-than-saas-and-what-that-means-for-your-business/) (todos secundários; as fontes divergem entre 52% e 53%)
- **Bessemer:** no State of AI 2025, as empresas de IA que mais crescem tinham margem bruta média de **cerca de 25%**, e as aplicações "steadier" de **cerca de 60%**. No State of the Cloud 2024, o portfólio de **IA vertical** tinha **cerca de 65% de margem bruta**, com custo de modelo em **cerca de 10% da receita**. — [1752vc, AI gross margins](https://www.1752.vc/learn/ai-gross-margins-and-inference-costs); [Rework, AI vs SaaS gross margins](https://resources.rework.com/libraries/ai-startup-growth/ai-vs-saas-gross-margins) (secundários)

### Inferences
- **Premissas conservadoras para o plano do ObraNexo:** churn mensal de 3% (vida média de cerca de 33 meses), ARPA de R$ 600/mês, margem bruta de 70% (possível porque o motor determinístico e o roteamento para modelos baratos reduzem a inferência; ver seção 3). LTV ≈ 600 × 0,70 / 0,03 ≈ **R$ 14.000**. Com LTV/CAC de 3:1, o **CAC máximo fica em cerca de R$ 4.700**; com payback de 12 meses, o CAC teto é cerca de R$ 5.000 (600 × 0,70 × 12).
- Um SaaS vertical de IA com camada determinística pode mirar a faixa da Bessemer para IA vertical (**cerca de 65% de margem, modelo em cerca de 10% da receita**), acima da média ICONIQ para "AI-native".
- Clientes que disputam licitações têm sazonalidade e dependem do ciclo orçamentário público, o que pode elevar o churn em planos mensais. Planos anuais pré-pagos (prática comum no setor, como no Siga Pregão) reduzem esse risco.

### Gaps
- **Não encontrei dados primários brasileiros** (Distrito, ABStartups ou Sebrae) de ARPA, churn ou CAC de SaaS B2B SMB no Brasil. Os relatórios primários de SaaS Capital, KeyBanc, OpenView e Benchmarkit não foram abertos diretamente; os números acima vêm de agregadores. A OpenView encerrou atividades em 2024 (conhecimento prévio, não verificado aqui).
- Não encontrei o PDF original do ICONIQ nem da Bessemer.

---

## 3. Custo de inferência por análise de edital (preços oficiais de API, out/2026) e hospedagem

### Takeaway
Com os preços oficiais de outubro de 2026, **uma análise de 30 mil a 150 mil tokens custa de R$ 0,02 a R$ 0,16** em modelos baratos (Gemini 2.5 Flash-Lite, Claude Haiku 5.5 com prompts de até 100k tokens, gpt-oss-120b na Groq), **de R$ 0,10 a R$ 0,90** em modelos Flash intermediários e **de R$ 0,48 a R$ 3,63** em Claude Sonnet. Mesmo no pior caso, a inferência é pequena perto de um plano de R$ 400 a R$ 1.000/mês, a menos que o volume passe de centenas de análises por cliente por mês com modelos topo de linha. A API do PNCP é pública e gratuita.

### Cited Findings — preços oficiais por 1 milhão de tokens (USD)
**Google Gemini (padrão pago; página atualizada em 22/10/2026)** — [Google AI, Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
| Modelo | Entrada | Saída | Batch (entrada/saída) |
|---|---|---|---|
| Gemini 3.8 Flash / 3.6 Flash | US$ 0,75 até 31/12/2026, depois US$ 1,50 | US$ 3,75, depois US$ 7,50 | 0,375 / 1,875 |
| Gemini 3 Flash Preview | 0,50 | 3,00 | 0,25 / 1,50 |
| Gemini 2.5 Flash | 0,30 | 2,50 | 0,15 / 1,25 |
| Gemini 3.5 Flash-Lite | 0,30 | 2,50 | 0,15 / 1,25 |
| Gemini 3.1 Flash-Lite | 0,25 | 1,50 | 0,125 / 0,75 |
| Gemini 2.5 Flash-Lite | 0,10 | 0,40 | 0,05 / 0,20 |
| Gemini 3.1 Pro Preview | 2,00 (≤200k) | 12,00 | 1,00 / 6,00 |
| Gemini 2.5 Pro | 1,25 (≤200k) | 10,00 | 0,625 / 5,00 |
- O Batch API custa 50% menos. Os modelos Flash, Flash-Lite e 2.5 Pro têm **free tier** (uso que pode servir para melhorar produtos do Google); o 3.1 Pro Preview não tem. — [Google AI pricing](https://ai.google.dev/gemini-api/docs/pricing)

**Anthropic Claude** — [Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing)
| Modelo | Entrada | Saída | Leitura de cache |
|---|---|---|---|
| Claude Haiku 5.5 (prompt ≤100k tokens) | 0,10 | 0,50 | 0,01 |
| Claude Haiku 5.5 (prompt >100k tokens) | 0,50 | 2,50 | 0,05 |
| Claude Haiku 4.5 | 1,00 | 5,00 | 0,10 |
| Claude Sonnet 5.5 | 2,00 | 10,00 | 0,10 |
| Claude Sonnet 4.6 / 4.5 | 3,00 | 15,00 | 0,30 |
| Claude Opus 5.5 | 4,00 | 20,00 | 0,20 |
| Claude Opus 5 / 4.8 / 4.5 | 5,00 | 25,00 | 0,50 |
- O Batch API dá **50% de desconto** em entrada e saída (por exemplo, Opus 5.5 em batch sai por US$ 2 / US$ 10). — [Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing)

**Groq** (a página oficial não trouxe a tabela; valores de fontes secundárias de 2026)
- **gpt-oss-120b: US$ 0,15 de entrada e US$ 0,60 de saída**; entrada em cache a US$ 0,075. **gpt-oss-20b: US$ 0,075 / US$ 0,30.** Batch e cache dão 50% de desconto cada. — [CloudZero, Groq pricing 2026](https://www.cloudzero.com/blog/groq-pricing/); [Spheron, Groq API pricing 2026](https://www.spheron.network/blog/groq-api-pricing-2026-cost-per-token-vs-gpu-rental/)
- **Llama na Groq:** guias antigos listavam Llama 3.3 70B a US$ 0,59/0,79 e Llama 3.1 8B a US$ 0,05/0,08. Guias recentes dizem que a Groq **descontinuou esses modelos no self-serve em 16/08/2026** e que eles seguem só para clientes Enterprise com contrato. O free tier é de cerca de 1.000 requisições por dia. — [Klymentiev, Groq free tier 2026](https://klymentiev.com/blog/groq-pricing); [Layer3 Labs, Groq pricing](https://www.layer3labs.io/guides/groq-pricing) (conflito entre fontes; conferir em console.groq.com)

### Cálculo próprio: custo por análise
Premissas: 30k e 150k tokens totais por análise, divididos em **85% de entrada e 15% de saída** (edital longo, saída estruturada), sem cache nem batch. Câmbio de R$ 5,0377.

| Modelo | 30k tokens (US$) | 150k tokens (US$) | 30k (R$) | 150k (R$) |
|---|---|---|---|---|
| Gemini 2.5 Flash-Lite | 0,0044 | 0,0218 | 0,02 | 0,11 |
| Groq gpt-oss-20b | 0,0033 | 0,0163 | 0,02 | 0,08 |
| Groq gpt-oss-120b | 0,0065 | 0,0326 | 0,03 | 0,16 |
| Claude Haiku 5.5 (chamadas ≤100k) | 0,0048 | 0,0240 | 0,02 | 0,12 |
| Claude Haiku 5.5 (uma chamada >100k) | — | 0,1200 | — | 0,60 |
| Gemini 3.1 Flash-Lite | 0,0131 | 0,0656 | 0,07 | 0,33 |
| Gemini 2.5 Flash | 0,0189 | 0,0945 | 0,10 | 0,48 |
| Gemini 3.x Flash (preço até dez/2026) | 0,0360 | 0,1800 | 0,18 | 0,91 |
| Gemini 3.x Flash (preço a partir de jan/2027) | 0,0720 | 0,3600 | 0,36 | 1,81 |
| Claude Haiku 4.5 | 0,0480 | 0,2400 | 0,24 | 1,21 |
| Claude Sonnet 5.5 | 0,0960 | 0,4800 | 0,48 | 2,42 |
| Claude Sonnet 4.6 | 0,1440 | 0,7200 | 0,73 | 3,63 |

**Hospedagem**
- O **Cloud Run** do Google tem free tier mensal de 180 mil vCPU-segundos, 360 mil GiB-segundos e 2 milhões de requisições (cobrança por requisição), ou 240 mil vCPU-s e 450 mil GiB-s (cobrança por instância). Um worker sempre ligado (1 vCPU, 0,5 GiB) foi estimado em **cerca de US$ 11,61/mês** depois dos créditos gratuitos. — [Google Cloud Run pricing](https://cloud.google.com/run/pricing); [CloudChipr, Cloud Run pricing](https://cloudchipr.com/blog/cloud-run-pricing)
- **API do PNCP:** a API de Consultas (`https://pncp.gov.br/api/consulta`, Swagger em `/api/consulta/swagger`) é **pública, REST/JSON e não exige autenticação**. Só as APIs de manutenção e envio exigem token JWT. — [PNCP, manuais](https://www.gov.br/pncp/pt-br/central-de-conteudo/manuais); [Manual API de Consultas v1.0](https://www.gov.br/pncp/pt-br/central-de-conteudo/manuais/versoes-anteriores/ManualPNCPAPIConsultasVerso1.0.pdf); [StatusLicitações, API PNCP](https://statuslicitacoes.com.br/api-pncp)
- A Transparência Brasil apontou problemas técnicos e de qualidade nos dados do PNCP (jun/2024 e dez/2024), o que é um risco operacional para quem depende da fonte. — [Transparência Brasil, API e acesso](https://www.transparencia.org.br/downloads/publicacoes/portalnacionaldecontratacoespublicas_recomendacoesedesafiostecnicos.pdf); [Transparência Brasil, qualidade de dados](https://www.transparencia.org.br/downloads/publicacoes/qualidade_dados_portal_nacional_de_contratacoes_publicas.pdf)

### Inferences
- **Custo variável por cliente:** com 100 análises/mês de 150k tokens, o gasto mensal seria de cerca de **R$ 11** (Flash-Lite ou Haiku 5.5 com chamadas fatiadas), **R$ 48** (Gemini 2.5 Flash), **R$ 91** (Gemini 3.x Flash na promoção) ou **R$ 242** (Sonnet 5.5). Num plano de R$ 497, isso equivale a 2%, 10%, 18% ou 49% da receita. **O roteamento de modelos é a principal alavanca de margem**: modelo barato para triagem e extração item a item, modelo forte só para a síntese do dossiê ou para casos ambíguos, e o motor determinístico sempre que possível.
- Agentes com várias chamadas de ferramenta, retentativas e reenvio de contexto podem multiplicar os tokens efetivos por 2 a 5. Vale usar **cache de prompt** (catálogo do fornecedor como prefixo fixo; a leitura de cache custa cerca de 10% da entrada) e **batch** (50% de desconto) nas análises noturnas.
- Atenção ao **degrau de preço do Haiku 5.5 acima de 100k tokens** (5x mais caro) e ao **reajuste do Gemini 3.x Flash em 01/01/2027** (o dobro). Fatiar o edital por item mantém as chamadas abaixo dos limiares.
- **Infraestrutura fixa no MVP:** de R$ 0 a cerca de R$ 300/mês (Cloud Run ou VM pequena, armazenamento de PDFs e banco gerenciado pequeno), com dados do PNCP de custo zero. O custo dominante passa a ser pessoas e aquisição de clientes, não infraestrutura.
- Margem bruta-alvo plausível: **75% a 85%** com roteamento barato, acima da média ICONIQ para "AI-native" (seção 2).

### Gaps
- Não consegui extrair a tabela oficial da Groq em groq.com/pricing (a página não retornou preços); os valores vêm de agregadores.
- Não levantei preços atuais de VM pequena (GCP e2-small, Hetzner, Magalu Cloud, AWS Lightsail) nem de armazenamento de objetos.
- A divisão de 85/15 entre entrada e saída e a faixa de 30–150k tokens são premissas da tarefa, não medições no ObraNexo.

---

## 4. Canais para alcançar fornecedores (associações, Sebrae, feiras, distribuidores, contadores, conteúdo, assessorias) e CAC por canal

### Takeaway
Encontrei pouca informação verificável. Há confirmação de feiras setoriais (Expolux, set/2026; FEICON, jul/2026) e do papel do Sebrae nas compras públicas, mas **nenhum dado público de CAC por canal no Brasil** nem informações sobre programas de ABREME, ABINEE, ABILUX ou ANAMACO voltados a licitações.

### Cited Findings
- A **Expolux 2026** (19ª Feira Internacional da Iluminação) aconteceu de **15 a 18/09/2026** no Expo Center Norte, em São Paulo. Teve uma área "Retail Experience" dedicada a varejistas, lojistas, atacadistas e distribuidores. Uma fonte indica a próxima edição para 19–22/09/2028. — [Jornal de Barueri, Expolux 2026](https://jornaldebarueri.com.br/tecnologia/expolux-2026-reune-conteudo-e-tecnologia-em-iluminacao); [Portal Radar, reposicionamento da Expolux](https://portalradar.com.br/expolux-2026-marca-reposicionamento-e-virada-de-conceito/); [Revista Potência, lançamento da Expolux 2026](https://revistapotencia.com.br/portal-potencia/feiras-e-eventos/lancamento-oficial-da-expolux-2026/)
- A Expolux participou da **FEICON** com foco em negócios. A FEICON 2026 ocorreu de **7 a 10/07/2026** no São Paulo Expo (data de fonte terceira). — [Expolux, blog sobre a FEICON](https://www.expolux.com.br/pt-br/blog/o-evento/expolux-participa-da-feicon-com-foco-estrategico-em-negocios.html); [Vendelux, FEICON 2026](https://vendelux.com/insights/feicon-2026-attendee-list)
- **Sebrae:** no Sebrae/MT, as compras da própria instituição somaram R$ 124 milhões em 2025, e **85% dos vencedores foram micro ou pequenas empresas** (comunicação institucional). O Sebrae mantém um portal sobre licitações e compras públicas para pequenos negócios. — [Agência Sebrae MT](https://mt.agenciasebrae.com.br/cultura-empreendedora/licitacoes-do-sebrae-mt-movimentam-r-124-milhoes-e-impulsionam-a-economia-regional-em-2025/); [Sebrae, conheça licitações](https://sebrae.com.br/sites/PortalSebrae/canais_adicionais/conheca_licitacoes)
- Notícia da Agência Sebrae: o Senado aprovou aumento da participação de pequenos negócios nas compras públicas. O **Contrata+Brasil** (plataforma para MEIs) tinha 2.422 MEIs e 400 instituições públicas aderidas (notícia aparentemente anterior a 2025). — [Agência Sebrae](https://agenciasebrae.com.br/economia-e-politica/senado-aprova-aumento-da-participacao-de-pequenos-negocios-nas-compras-publicas/)
- **Conteúdo e SEO como canal:** concorrentes como Effecti, ConLicitação e Siga Pregão publicam conteúdo educativo extenso para assessorias e licitantes (comissão, taxa de conversão, KPIs de ROI). Isso mostra o marketing de conteúdo como canal dominante do setor. — [Effecti, como conquistar clientes de consultoria](https://effecti.com.br/consultoria-licitacoes-clientes/); [ConLicitação, KPIs de ROI](https://conlicitacao.com.br/gestao-de-licitacoes-kpis-essenciais-para-medir-o-roi/); [Effecti, taxa de conversão 2026](https://effecti.com.br/taxa-de-conversao-licitacoes/)
- **Assessorias como canal:** os softwares do setor têm plano específico para quem atende vários CNPJs (Siga Pregão Multiempresas), o que reforça a assessoria como canal de revenda e multiplicação. — [Siga Pregão Multiempresas](https://www.sigapregao.com.br/multiempresas/)

### Inferences
- **Canais prioritários (hipótese):** (1) **assessorias de licitação** como parceiras ou revendedoras, já que uma assessoria atende de 10 a 50 CNPJs e pode receber comissão recorrente ou plano multi-CNPJ; (2) **conteúdo e SEO** sobre análise de editais de material elétrico, que é o canal de menor custo usado pelos concorrentes; (3) **fabricantes** que indicam a ferramenta à sua rede de distribuidores (co-marketing); (4) **Sebrae/Sebraetec** e eventos de compras públicas; (5) feiras (Expolux, FEICON) para geração de leads, com custo alto e ciclo bienal no caso da Expolux.
- O CAC deve ser medido na prática. Use o teto de cerca de R$ 4.700 a R$ 5.000 (seção 2) como limite de decisão por canal.

### Gaps
- **Nenhum dado de CAC por canal no Brasil** foi encontrado.
- Não verifiquei programas de ABINEE, ABILUX, ABREME, ABRAMAT ou ANAMACO para compras públicas, nem os seus números de associados. A busca não retornou nada sobre a ABREME.
- Não verifiquei FIMAI, parcerias com contadores nem números de expositores ou visitantes das feiras.
- Não encontrei um levantamento nacional consolidado do Sebrae sobre a participação de MPEs em licitações em 2025.

---

## 5. Parceiros-chave (dados, LLMs, nuvem, Sebrae, ICTs/EMBRAPII/AKCIT, INMETRO) e fomento para startups de IA

### Takeaway
O fomento público a IA no Brasil é grande: **R$ 10,5 bilhões aprovados por BNDES, Finep e Embrapii entre jan/2023 e fev/2026**. Para uma startup em estágio inicial, os instrumentos mais acessíveis são o **Centelha 3** (subvenção de **R$ 85 mil a R$ 128 mil** por projeto, conforme o estado, mais até R$ 50 mil em bolsas CNPq; em Goiás, cerca de R$ 85,4 mil via FAPEG), a **EMBRAPII** (até **50% não reembolsável** para empresas com ROB abaixo de R$ 90 milhões no modelo com o BNDES) e o **BNDES Garagem** (aceleração com prêmios de R$ 32 mil a R$ 160 mil).

### Cited Findings
- **BNDES, Finep e Embrapii** somaram **R$ 10,5 bilhões** em apoio a projetos de IA entre jan/2023 e fev/2026. A parcela da Embrapii foi de **R$ 1,2 bilhão em 632 projetos**, com mais de 90 unidades credenciadas. — [Agência BNDES](https://agenciadenoticias.bndes.gov.br/industria/BNDES-Finep-e-Embrapii-somam-R$105bi-em-apoio-a-projetos-de-IA-desde-2023/); [Canal Rural](https://www.canalrural.com.br/economia/bndes-finep-e-embrapii-aprovam-r-105-bilhoes-para-projetos-de-inteligencia-artificial/)
- **EMBRAPII + BNDES:** empresas com **ROB abaixo de R$ 90 milhões** podem receber **até 50% do projeto** em recursos não reembolsáveis; empresas maiores, até 1/3. No modelo tradicional, o limite é de até 1/3 (cerca de 33%). Os recursos podem ser combinados com Lei do Bem, Lei da Informática etc. — [Embrapii e BNDES](https://embrapii.org.br/bndes/); [Embrapii, perguntas frequentes](https://embrapii.org.br/perguntas-frequentes/); [JUS Braziliense, 06/08/2026](https://blogs.correiobraziliense.com.br/jusbraziliense/2026/08/06/lei-do-bem-bndes-e-embrapii-o-dinheiro-para-inovacao-que-sua-empresa-ignora/)
- O Sebrae pode cobrir **até 70% da contrapartida** de micro e pequenas empresas em projetos com a Embrapii (fonte possivelmente desatualizada). — [JUS Braziliense](https://blogs.correiobraziliense.com.br/jusbraziliense/2026/08/06/lei-do-bem-bndes-e-embrapii-o-dinheiro-para-inovacao-que-sua-empresa-ignora/)
- Uma consultoria afirma que é possível "captar até R$ 8M sem diluir equity" via Embrapii (afirmação de marketing). — [Baita, Embrapii](https://baita.ac/insights/como-captar-com-a-embrapii-para-inovar-mm2vaypr)
- **Lei do Bem (Lei 11.196/2005):** é um incentivo fiscal a P&D e **exige lucro** (lucro real) para ser aproveitado. Por isso, tende a não servir a startups no início. — [JUS Braziliense](https://blogs.correiobraziliense.com.br/jusbraziliense/2026/08/06/lei-do-bem-bndes-e-embrapii-o-dinheiro-para-inovacao-que-sua-empresa-ignora/)
- **Centelha 3** (MCTI, Finep e CNPq com CONFAP e as FAPs, com chamadas estaduais). Teto de subvenção por projeto: **SP e RJ R$ 128 mil**; **PR, SC e MG R$ 96 mil**; MS cerca de R$ 89,6 mil; PE cerca de R$ 86,7 mil; **Goiás (FAPEG/Finep, Chamada 29/2025) cerca de R$ 85,4 mil**. Há ainda **bolsas CNPq de até R$ 50 mil** por projeto. Orçamentos estaduais: SP R$ 6 milhões, PR R$ 4,6 milhões, SC R$ 4 milhões, MG R$ 2,4 milhões. — [FAPEG, edital Centelha 3 GO](https://goias.gov.br/fapeg/wp-content/uploads/sites/5/2026/05/Edital_Centelha_3_GO_4__Retificacao_DPM_19_05_2026_revisado_GI-1.pdf); [FAPERJ, edital 12/2026](https://www.faperj.br/rp/downloads/Edital_FAPERJ_N%C2%BA_12_2026_Programa_CENTELHA_3_16_jun_2026.pdf); [FAPESP, Centelha 3 SP](https://fapesp.br/18109/programa-nacional-de-apoio-a-geracao-de-empreendimentos-inovadores-programa-centelha-3-sao-paulo); [Agência FAPESP](https://agencia.fapesp.br/programa-centelha-sp-destina-r-6-milhoes-para-inovacao/57791); [CRN1, Paraná](https://crn1.com.br/2026/05/abertas-inscricoes-para-o-programa-que-investira-r-46-milhoes-em-startups-e-negocios-inovadores); [FAPESC](https://fapesc.sc.gov.br/programa-centelha-3-com-capacitacoes-e-fomento-de-r-4-milhoes-governo-do-estado-incentiva-empreendedores-catarinenses-a-inovarem-na-criacao-de-novos-negocios/); [FAPEMIG](https://fapemig.br/difusao-do-conhecimento/imprensa/noticias-e-eventos/fapemig-lanca-centelha-3-com-r-24-milhoes-destinados-ao-empreendedorismo-de-base-tecnologica); [FACEPE](https://www.facepe.br/wp-content/uploads/2026/06/2.12_Edital_Centelha-PE-3_FACEPE_Retificacao_Cronograma_Versao-26Junho2026_assinado-1.pdf); [Midiamax, MS](https://midiamax.com.br/cotidiano/2026/tem-ideia-inovadora-centelha-seleciona-47-propostas-receber-ate-r-139-mil-ms/)
- **BNDES Garagem** (aceleração conduzida pela Quintessa): cada ciclo apoia **50 startups no módulo Criação e 50 no módulo Tração**, até 400 startups em 4 ciclos entre 2024 e 2028. Os 5 vencedores de Tração recebem prêmios de **R$ 64 mil a R$ 160 mil**, e os de Criação, de **R$ 32 mil a R$ 85 mil**. A aceleração do ciclo atual foi de março a junho de 2026. Não encontrei edital aberto em out/2026. — [BNDES Garagem](https://garagem.bndes.gov.br/); [Agência BNDES, novo ciclo](https://agenciadenoticias.bndes.gov.br/bndes/Em-novo-ciclo-BNDES-Garagem-abre-inscricoes-para-selecionar-ate-100-startups-de-impacto/); [CONFAP](https://news.confap.org.br/bndes-garagem-lanca-novo-ciclo-de-aceleracao-para-selecao-de-100-empreendedores-e-startups-de-impacto/)
- **Dados como parceiro:** a API de Consultas do PNCP é pública e gratuita (ver seção 3). — [PNCP, manuais](https://www.gov.br/pncp/pt-br/central-de-conteudo/manuais)
- **LLMs e nuvem:** Google (Gemini, com free tier nos modelos Flash), Anthropic (Claude) e Groq (modelos abertos gpt-oss) têm preços públicos (seção 3). O free tier do Gemini pode usar os dados para melhorar produtos do Google; o tier pago, na maior parte dos modelos, não. Isso importa para a LGPD e para a confidencialidade do catálogo dos clientes. — [Google AI pricing](https://ai.google.dev/gemini-api/docs/pricing)

### Inferences
- **Mapa de parceiros sugerido:** dados (PNCP e Compras.gov.br), LLMs (Google, Anthropic, Groq, numa estratégia multi-provedor que reduz dependência e permite arbitragem de preço), nuvem (GCP, com créditos de programas para startups), fomento (FAPEG/Centelha GO, Embrapii via uma unidade como o AKCIT em Goiás, Finep, BNDES Garagem), canal (Sebrae, assessorias, fabricantes) e certificação (INMETRO, para validar a conformidade de luminárias e materiais elétricos exigida nos editais).
- **Sequência de fomento para uma equipe em Goiás:** Centelha GO (cerca de R$ 85 mil mais bolsas), depois Embrapii/AKCIT (até 50% não reembolsável num projeto de P&D de IA), depois BNDES Garagem (Tração). A Lei do Bem só quando houver lucro real.

### Gaps
- Não verifiquei dados do **AKCIT** (unidade Embrapii em Goiás: escopo exato, teto e contrapartida), do **Finep Mais Inovação/Startup**, do **InovAtiva** nem a disponibilidade e o formato de dados abertos do **INMETRO** sobre certificações de produtos.
- Não verifiquei as APIs do Compras.gov.br (dados abertos) além do PNCP.
- Não verifiquei os percentuais da Lei do Bem (exclusão adicional de 60% a 80% das despesas de P&D, por conhecimento prévio, não confirmado nesta pesquisa).
- Não pesquisei programas de créditos para startups (Google for Startups Cloud, AWS Activate, Anthropic) nem os seus valores em 2026.

---

## 6. Regulação: LGPD, dados públicos (LAI e dados abertos do PNCP) e PL 2338/2023

### Takeaway
O **PL 2338/2023 (Marco Legal da IA)** foi aprovado no Senado, mas **ainda não foi votado na Câmara em out/2026**. O relator adiou a votação para depois das eleições de outubro de 2026, e se a Câmara alterar o texto ele volta ao Senado. Usar os dados abertos do PNCP é legítimo (API pública). A LGPD se aplica sobretudo aos dados dos clientes e às pessoas físicas que aparecem em editais e atas.

### Cited Findings
- Em **24/08/2026**, o relator, deputado **Aguinaldo Ribeiro (PP-PB)**, disse que a votação do PL 2338/2023 ficaria **para depois das eleições de outubro**. Um monitor legislativo registra **cinco datas de votação marcadas e perdidas desde nov/2025**. O projeto está na Comissão Especial sobre IA da Câmara, aguardando parecer; se for alterado, volta ao Senado antes da sanção. — [Bairo Gonzalez, PL 2338 em 2026](https://bairogonzalez.com/en/in-the-world/ia/pl-2338-brazil-ai-legal-framework-2026/); [LCF Monitor, PL 2338/2023](https://monitor.lcfconsulting.com.br/proposicoes/pl-2338-2023/); [Tyna, status do PL 2338](https://tyna.com.br/pl-2338/); [The Leveraged Years](https://www.theleveragedyears.com/ai-regulation-news/brazil-pl-2338-ai-act-marco-legal-status-2026)
- Uma previsão anterior, de votação em fev/2026, não se confirmou. — [Desinformante](https://desinformante.com.br/votacao-do-marco-da-ia-fica-para-2026-em-meio-a-impasses-politicos-e-criticas-ao-texto)
- Guias empresariais citam multas de até **R$ 50 milhões** por infração no texto do PL (valor do texto em tramitação, não lei vigente). — [IA Locus, PL 2338](https://ialocus.com.br/blog/post-pl-2338-marco-legal-ia-brasil-2026.html); [Prismon, guia para empresas](https://prismon.ai/blog/marco-legal-inteligencia-artificial-pl-2338-2023)
- A **API de Consultas do PNCP** é de acesso público; o "Manual de Dados Abertos" aparece na central de conteúdo oficial. — [PNCP, manuais](https://www.gov.br/pncp/pt-br/central-de-conteudo/manuais)
- **Base legal (textos oficiais):** LGPD, [Lei 13.709/2018](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm); Lei de Acesso à Informação, [Lei 12.527/2011](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm); Nova Lei de Licitações, que institui o PNCP (art. 174), [Lei 14.133/2021](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm).

### Inferences
- O ObraNexo provavelmente não se enquadraria como sistema de "alto risco" no texto do PL 2338: faz análise de apoio à decisão comercial B2B, não decide sobre pessoas. Mesmo assim, convém manter **rastreabilidade e evidência literal**, que já são um diferencial do produto e se alinham às exigências de transparência do PL. Isso depende do texto final.
- **LGPD:** os dados de clientes (catálogo, preços, CNPJ, usuários) exigem contrato de tratamento de dados, operadores (provedores de LLM e nuvem) listados como suboperadores e preferência por tiers pagos de LLM que não treinam com os dados. Editais e atas podem conter dados pessoais (CPF de pregoeiros, sócios); o tratamento se apoia na publicidade legal, mas deve seguir finalidade e minimização.
- O risco regulatório para o modelo de receita é baixo no curto prazo. O risco operacional maior é a **qualidade e a estabilidade da API do PNCP** (seção 3).

### Gaps
- Não consultei a ficha oficial do PL 2338/2023 no site da Câmara; o status vem de monitores e escritórios.
- Não pesquisei orientações da ANPD sobre IA ou dados públicos de 2025–2026, nem termos de uso específicos do PNCP para reuso comercial.
