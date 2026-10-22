# Fluxo dos agentes — ObraNexo v0.1

O ObraNexo transforma uma contratação pública (PNCP) + o catálogo de um fornecedor em um
**dossiê comercial verificável**. O princípio: *o LLM interpreta e investiga; as regras decidem a
compatibilidade objetiva; toda conclusão aponta para uma evidência.*

```
carregar_contexto ─► coletar_documentos ─► extrair_itens ─► filtrar_relevantes ─► casar_com_catalogo
                                                                                        │
                                   ┌─ falta informação contratual (garantia, prazo…)? ─┘
                                   ▼
                          AGENTE INVESTIGADOR  (ferramentas: listar_documentos, buscar_trechos,
                                   │             ler_pagina, registrar_requisito, concluir_investigacao)
                                   ▼
                          re-casar itens afetados ─► AGENTE VERIFICADOR ─► qualificar ─► AGENTE PLANEJADOR ─► gerar_dossie
```

## Nós

| Nó | O que faz | Determinístico | Com LLM |
|---|---|---|---|
| coletar_documentos | Extrai texto dos PDFs com página (PyMuPDF), indexa trechos; cada item do PNCP vira um documento citável | ✔ | — |
| extrair_itens (**Analista Técnico**) | Lê a descrição do item e produz requisitos canônicos (potência, tensão, CCT, fluxo, lm/W, IP, IK, garantia, INMETRO…) com o trecho literal de origem | regex + normalização pt-BR | modelo de extração (Gemini 3.5 Flash-Lite por padrão) com saída estruturada; complementa o que as regras não acharam; divergência vira **conflito**; atributos textuais entram como desejáveis |
| filtrar_relevantes | Mantém só itens de categorias existentes no catálogo | ✔ | — |
| casar_com_catalogo (**motor de regras**) | Compara cada requisito com cada produto candidato: ATENDE / NAO_ATENDE / INDETERMINADO → agrega em COMPATÍVEL / PARCIAL / INCOMPATÍVEL / INDETERMINADO | ✔ (nunca usa LLM) | — |
| **Investigador** | Procura no edital o que não estava no item (garantia, prazo de entrega, amostra, ensaios) e registra com evidência | busca textual + regex nos trechos | modelo de agente (Gemini 3.8 Flash, reserva 3.5 Flash-Lite) em loop de ferramentas (máx. 12 passos, aviso nos 2 últimos, orçamento de tokens); o que ele não registrar passa pela contingência por regras |
| varrer_insumos (só quando nenhum item cabe no portfólio — obras/serviços) | Procura nos projetos, memoriais e orçamentos menções a categorias do catálogo (luminária, cabo, disjuntor, eletroduto…) e registra cada uma com evidência: é a base da oportunidade INDIRETA | ✔ | — |
| **Verificador** | Confere que cada trecho citado existe literalmente na página (rapidfuzz ≥ 90), corrige a página quando necessário, detecta conflitos entre fontes, atribui confiança e lista pendências de revisão humana | ✔ | parecer crítico em até 8 linhas |
| qualificar | Classifica PUBLICADA / PLANEJADA / INDIRETA / INFERIDA, identifica o comprador provável, status do prazo, prioridade 0-100, riscos | ✔ | — |
| **Planejador Comercial** | Resumo executivo e próximos passos datados | template | modelo de agente com saída estruturada, a partir só dos fatos verificados |

Provedores: Google Gemini (padrão, nível gratuito) ou Anthropic — mesma interface em `llm/client.py`
(`extrair`, `texto`, `conversa`), com cache em disco por requisição, contagem de tokens por modelo e
fallback automático para o modelo reserva em 429/503.
| gerar_dossie | Markdown com 12 seções e rodapé de custo/tempo | ✔ | — |

## Guardrails

- Documentos e descrições são injetados como **dados** (`<documento>`, `<item>`), nunca como instruções.
- O Investigador **não tem ferramentas de ação externa** (não envia e-mail, não participa de licitação).
- Toda saída do LLM é validada por esquema (Pydantic / `strict: true`); valores só entram com trecho literal.
- Limites por análise: passos do Investigador e orçamento de tokens; estourou, encerra com resultado parcial.
- Sem chave de API, **todo o fluxo roda em modo determinístico** — a demo nunca depende da rede.

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
| INFERIDA | hipótese por histórico (fora do MVP) | — |
