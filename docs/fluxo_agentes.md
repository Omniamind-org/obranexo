# Fluxo dos agentes — ObraNexo

O ObraNexo transforma licitações públicas reais (PNCP) + o catálogo de um fornecedor em
**oportunidades verificáveis**. O princípio: *o LLM decide, interpreta e investiga; as regras decidem a
compatibilidade objetiva; toda conclusão aponta para um trecho literal de um documento.*

São dois níveis de agente:

```
AGENTE DE PROSPECÇÃO  (decide o que buscar, o que abrir, o que analisar a fundo e como ranquear)
   ferramentas: buscar_licitacoes_abertas · ver_itens · analisar_a_fundo · concluir
        │
        └── analisar_a_fundo ──► ANÁLISE DE UMA LICITAÇÃO
             coletar_documentos (PDF, DOCX, XLSX, ZIP) ─► ANALISTA TÉCNICO (itens em lote)
             ─► filtrar_relevantes ─► ESPECIFICADOR (lê o TR dos itens "conforme TR")
             ─► motor de regras ─► INVESTIGADOR (ferramentas sobre os documentos) ─► re-casar
             ─► VERIFICADOR ─► qualificar ─► PLANEJADOR ─► dossiê
```

## Agente de Prospecção (`agents/prospector.py`)

Recebe o catálogo, as UFs e o horizonte de prazo. O LLM conduz tudo:

| Ferramenta | O que faz de verdade |
|---|---|
| `buscar_licitacoes_abertas(uf, termos)` | consulta o PNCP (pregões com propostas abertas) e filtra pelo objeto com os termos que **o agente escolheu** a partir do catálogo |
| `ver_itens(contratacao_id)` | lista os itens da licitação direto do PNCP |
| `analisar_a_fundo(contratacao_id, motivo)` | baixa edital e anexos e roda a análise completa abaixo (limitada por prospecção) |
| `concluir(ranking, resumo)` | ranking justificado; só aceita licitações que vieram das ferramentas |

Controles do sistema sobre as decisões do agente:
- ids inventados são descartados do ranking;
- **o ranking não pode contradizer a análise**: nota alta para uma licitação em que a análise completa não
  confirmou nenhum item compatível/parcial volta para o agente como erro, com os fatos; se ele insistir, a
  nota é limitada e a justificativa recebe a marcação;
- limite de passos e de análises completas; sem concluir, ranking de contingência pela prioridade calculada.

## Análise de uma licitação

| Nó | O que faz | Com LLM |
|---|---|---|
| coletar_documentos | Texto por página de PDF, DOCX, XLSX e TXT; **ZIPs são expandidos** (projetos, atas, planilhas) e cada arquivo vira documento citável; o tipo é detectado pelo conteúdo, não pela extensão | — |
| **Analista Técnico** (`extrator.py`) | Requisitos canônicos de cada item (potência, tensão, CCT, fluxo, lm/W, IP, IK, seção, tipo de cabo…). Regras pt-BR sempre rodam; o LLM complementa **em lotes de até 10 itens por chamada** | modelo de extração |
| filtrar_relevantes | Categoria pelo núcleo da descrição; acessórios saem do portfólio | — |
| **Especificador** (`especificador.py`) | Itens publicados só com o nome ("Cabo elétrico flexível"): localiza as páginas do TR que tratam deles e lê todas de uma vez; cada atributo só entra com trecho conferido no documento | modelo de extração |
| motor de regras (`rules/compare.py`) | ATENDE / NÃO ATENDE / INDETERMINADO por requisito → COMPATÍVEL / PARCIAL / INCOMPATÍVEL / INDETERMINADO por item | nunca |
| **Investigador** (`investigador.py`) | Loop de ferramentas (listar_documentos, buscar_trechos, ler_pagina, registrar_requisito) para (1) especificar itens que ainda faltam e (2) exigências gerais (garantia, prazo, amostra, INMETRO, ensaios). **A citação é conferida no registro**: trecho que não existe no documento volta como erro para o agente corrigir | modelo de agente, orçamento próprio |
| **Verificador** | Reconfere todas as citações, detecta conflitos entre fontes, atribui confiança e escreve o parecer de revisão humana | parecer |
| qualificar | Tipo (publicada / planejada / indireta), comprador provável, prazo, prioridade 0–100, riscos | — |
| **Planejador** | Resumo executivo e próximos passos, só a partir dos fatos verificados | saída estruturada |

## O LLM interpreta, as regras decidem

- **Todo valor proposto por um modelo é validado** (`rules/validar.py`) pelo tipo e pela faixa plausível do
  atributo. Exemplos rejeitados em dados reais: `cct_k = "branca fria"`, `tensao_v = 600–1000` (isolação de
  cabo), `material_corpo = "PRETA"`, `irc = 0,7`.
- **Toda citação é conferida literalmente** no documento (similaridade ≥ 90) — no registro (Investigador,
  Especificador) e de novo no Verificador.
- Requisito tirado **só pelo LLM da descrição do item** entra como desejável; especificação do TR com citação
  conferida é exigência.
- A comparação nunca derruba a análise; sem especificação técnica do item, o resultado é INDETERMINADO.
- Orçamento de tokens proporcional ao número de itens; o Investigador tem orçamento próprio.

## Catálogo a partir de fichas técnicas reais (`catalog/importar.py`)

O fornecedor envia o link da página/PDF do fabricante, o arquivo da ficha (PDF, DOCX, XLSX, ZIP) ou cola o
texto. O LLM propõe os produtos (um por modelo/variação), cada atributo passa pela validação acima e o
usuário revisa antes de adicionar. Páginas montadas por JavaScript são recusadas com aviso.

## Guardrails

- Documentos e descrições entram como **dados** (`<documento>`, `<item>`), nunca como instruções.
- Nenhum agente tem ferramenta de ação externa (não envia proposta, não participa de licitação).
- Saídas do LLM validadas por esquema (Pydantic / `strict: true`).
- Sem chave de API, a análise roda em modo determinístico; prospecção e importação por IA exigem o LLM.

## Resultados possíveis por requisito

| Resultado | Quando |
|---|---|
| ATENDE | o atributo do produto satisfaz o operador exigido (=, ≥, ≤, entre, contém, verdadeiro) |
| NAO_ATENDE | o atributo existe e não satisfaz |
| INDETERMINADO | o catálogo não informa o atributo **ou** o valor não é interpretável — nunca é tratado como "atende" |

## Classificação da oportunidade

| Tipo | Regra | Comprador provável |
|---|---|---|
| PUBLICADA | aquisição/fornecimento de bens publicada no PNCP | o órgão |
| PLANEJADA | item de Plano de Contratações Anual (PCA) | o órgão (futuro) |
| INDIRETA_POTENCIAL | objeto é obra/serviço de engenharia/locação | a empresa contratada (construtora/prestadora) |
