# Avaliação contra gabaritos

Gerado por `python eval/run_benchmark.py --markdown docs/avaliacao.md` · modo **deterministico** · 2 contratação(ões) com gabarito · 9 itens · 8 pares item × produto.

Casos: `aruana_pp005_2026`, `goianira_pe038_2026`.

## Métricas-alvo

| Métrica | Obtido |
|---|---|
| Acerto por item | 100% |
| Precisão de COMPATÍVEL | 100% |
| Detecção de incompatibilidade | 100% |
| Acerto nos pares item × produto | 100% |
| Citações conferidas (rastreabilidade) | 100% |
| Consistência entre execuções | 100% |

## Por classe

| Classe | Precisão | Recall | Itens no gabarito |
|---|---|---|---|
| COMPATIVEL | 100% | 100% | 5 |
| PARCIAL | 100% | 100% | 3 |
| INDETERMINADO | — | — | 0 |
| INCOMPATIVEL | 100% | 100% | 1 |
| FORA_DO_PORTFOLIO | — | — | 0 |

## Matriz de confusão

Linha: o que o gabarito diz; coluna: o que o sistema respondeu.

| Gabarito \ Sistema | Comp. | Parc. | Indet. | Incomp. | Fora |
|---|---|---|---|---|---|
| Comp. | 5 | 0 | 0 | 0 | 0 |
| Parc. | 0 | 3 | 0 | 0 | 0 |
| Indet. | 0 | 0 | 0 | 0 | 0 |
| Incomp. | 0 | 0 | 0 | 1 | 0 |
| Fora | 0 | 0 | 0 | 0 | 0 |
