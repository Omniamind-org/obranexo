# Como rotular o gabarito

O benchmark só mede alguma coisa se o gabarito vier de pessoas, e não do próprio sistema. Por isso cada item é rotulado por **duas pessoas, sem ver o rótulo da outra**. Onde elas divergem, as duas conversam e registram o rótulo final.

## Planilhas

| Planilha | Casos | Itens |
|---|---|---|
| [`teste_cego_rotulagem.csv`](teste_cego_rotulagem.csv) | 5 pregões de GO, nunca vistos pelo sistema (teste cego de 23/10) | 133 |
| [`rotulagem_novos_casos.csv`](rotulagem_novos_casos.csv) | DF (ferragens), MT (Alto Boa Vista, material elétrico) e TO (Porto Nacional, concorrência de obra de iluminação pública) | 124 |

Abra a planilha no LibreOffice ou no Excel, com `;` como separador e UTF-8 como codificação. Cada linha é um item: o que o sistema respondeu (`resultado_sistema`, `produto_sistema`) e a descrição do item. Os casos estão em `data/casos/<caso>/`: os itens em `itens.json` e o edital e os anexos em `arquivos/`.

## O que cada pessoa preenche

| Coluna | Quem preenche | O quê |
|---|---|---|
| `revisor_1` | primeira pessoa | o rótulo certo, na opinião dela |
| `revisor_2` | segunda pessoa, **sem olhar `revisor_1`** | o rótulo certo, na opinião dela |
| `esperado` | as duas juntas, **só onde divergiram** | o rótulo final combinado |
| `produto_esperado` | opcional | o SKU do catálogo de demonstração que atende o item, quando há |
| `observacao` | qualquer uma | por que o rótulo é esse, principalmente nos casos difíceis |

Para que uma pessoa não veja o rótulo da outra, o mais simples é trabalhar em cópias separadas da planilha e juntar as duas colunas depois.

## Os rótulos

O catálogo de referência é o de demonstração (`data/catalogo_demo/produtos.json`, 41 produtos). A pergunta é sempre: **o melhor produto desse catálogo atende o item, pelo que o edital exige?**

| Rótulo | Quando usar |
|---|---|
| `COMPATIVEL` | um produto atende todas as exigências técnicas do item |
| `PARCIAL` | atende as principais, mas falta comprovar ou cumprir alguma secundária (um laudo, um acessório, uma faixa de tensão) |
| `INDETERMINADO` | o item ou o edital não traz especificação suficiente para decidir |
| `INCOMPATIVEL` | é da categoria que o catálogo vende, mas nenhum produto atende (potência, grau de proteção, tipo de cabo…) |
| `FORA` | o catálogo não vende esse tipo de produto (ferragens, ferramentas, serviços, acessórios) |

Na dúvida entre dois rótulos, use o mais conservador (`INDETERMINADO` em vez de `COMPATIVEL`) e explique em `observacao`. Rotule pelo **edital**, não pelo que o sistema respondeu: a coluna `resultado_sistema` serve só de referência, e concordar com ela não é o objetivo.

## Depois de rotular

```bash
python eval/gabarito_da_planilha.py docs/teste_cego_rotulagem.csv              # andamento e concordância (kappa)
python eval/gabarito_da_planilha.py docs/teste_cego_rotulagem.csv --escrever   # grava data/casos/<caso>/gabarito.json
python eval/run_benchmark.py --repeticoes 3 --markdown docs/avaliacao.md       # mede e atualiza o relatório
```

O script só grava o gabarito de um caso quando todos os itens dele estão resolvidos. Com **kappa abaixo de ~0,6**, o critério não está combinado: revisem juntos os itens em que divergiram e ajustem este guia antes de medir.

Com os gabaritos novos, o benchmark deixa de medir só os 2 casos internos. Então é preciso recalibrar os mínimos de `eval/limiares.json` com os valores medidos, sem descer abaixo das metas do roadmap: 85% de precisão em COMPATÍVEL, 90% de detecção de incompatibilidade e 95% de rastreabilidade.
