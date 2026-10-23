# Teste cego — 23/10/2026

Cinco pregões eletrônicos **com propostas abertas** no PNCP (GO), escolhidos por redação diferente e **nunca vistos**
pelo sistema, rodados sem ajuste prévio. Objetivo: medir robustez fora dos casos usados no desenvolvimento.

| Caso | Contratação | Itens | Antes das correções | Depois |
|---|---|---|---|---|
| `cego_itumbiara_refletores` | REGISTRO DE PREÇOS DE FUTURA E EVENTUAL AQUISIÇÃO DE REFLETORES CONFOR… | 3 | Compatível 0 · Parcial 0 · Indeterminado 0 · Incompatível 3 · Fora do portfólio 0 | Compatível 0 · Parcial 0 · Indeterminado 0 · Incompatível 3 · Fora do portfólio 0 |
| `cego_itaberai_mat_eletrico` | AQUISIÇÃO DE MATERIAIS ELÉTRICOS DESTINADOS Á MANUTENÇÃO DE PRAÇAS PÚB… | 21 | Compatível 4 · Parcial 4 · Indeterminado 9 · Incompatível 1 · Fora do portfólio 3 | Compatível 3 · Parcial 3 · Indeterminado 3 · Incompatível 9 · Fora do portfólio 3 |
| `cego_chapadao_iluminacao` | AQUISIÇÃO DE MATERIAIS DESTINADOS A ILUMINAÇÃO GO-206, INGÁ LESTE, PAR… | 32 | Compatível 4 · Parcial 5 · Indeterminado 2 · Incompatível 7 · Fora do portfólio 14 | Compatível 4 · Parcial 1 · Indeterminado 2 · Incompatível 5 · Fora do portfólio 20 |
| `cego_cezarina_ilum_publica` | REGISTRO DE PREÇO para futuras aquisições de materiais de iluminação p… | 34 | Compatível 0 · Parcial 4 · Indeterminado 5 · Incompatível 20 · Fora do portfólio 5 | Compatível 0 · Parcial 2 · Indeterminado 4 · Incompatível 20 · Fora do portfólio 8 |
| `cego_anapolis_consumo` | Registro de preços para eventual aquisição de material de consumo - Ma… | 43 | Compatível 7 · Parcial 1 · Indeterminado 16 · Incompatível 4 · Fora do portfólio 15 | Compatível 6 · Parcial 1 · Indeterminado 8 · Incompatível 5 · Fora do portfólio 23 |

Todas as citações dos dossiês foram verificadas literalmente nos documentos nas duas rodadas (rastreabilidade 100%).

## O que estava errado (e foi corrigido)

| # | Problema | Exemplo real | Efeito | Correção |
|---|---|---|---|---|
| 1 | Busca "propostas abertas" sempre vazia | `dataFinal` do PNCP é o limite de encerramento; passávamos hoje | interface e CLI mostravam 0 resultados (havia 419 em GO) | padrão = hoje + 60 dias |
| 2 | Categoria por qualquer menção no texto | "SUPORTE PARA 1 PÉTALA PARA LUMINÁRIA", "BRAÇO … FIXAÇÃO DE LUMINÁRIAS" | **falso positivo**: acessório casava com luminária | categoria pelo núcleo da descrição; acessórios saem do portfólio |
| 3 | Item sem especificação técnica virava compatível | "Plafonier, Cor: Branca"; luminária de emergência | **falso positivo** só por cláusulas gerais (garantia, prazo) | sem requisito técnico do item → INDETERMINADO, com explicação |
| 4 | Formato CATMAT (rótulo: valor, sem unidade) não lido | `seção nominal: 16`, `potência lâmpada: 100`, `temperatura de cor: 6.500` | cabos e refletores sem requisitos → INDETERMINADO; luminária 6.000 K aceita produto de 5.000 K | padrões rotulados sem unidade |
| 5 | Separadores e faixas | `85V~265V`, `IRC: >80`, `fator de potência: > 0,99`, `4000K A 5000K` | requisitos perdidos ou faixa lida como valor único | separadores e faixa de CCT |
| 6 | Tipo de cabo não verificado | "Cabo … tipo: fotovoltaico" | **falso positivo**: cabo solar casava com cabo predial pela seção | atributo `tipo_cabo` (fotovoltaico, PP, nu, lógico, coaxial, alumínio, multiplexado) |
| 7 | **Valor do LLM derrubava a análise inteira** | Gemini devolveu `cct_k = "branca fria"` | análise de Itaberaí terminou em erro | validação por tipo e faixa (`rules/validar.py`); comparação nunca lança exceção |
| 8 | Requisitos inventados pelo LLM reprovavam itens corretos | `tensao_v = 600–1000` (isolação de cabo), `material_corpo = "PRETA"`, `tipo_cabo` em texto livre | **falsos negativos** em cabos e eletrodutos | valores fora do tipo/faixa descartados; requisito só do LLM entra como desejável |
| 9 | LLM reclassificava acessórios | "SUPORTE PARA PÉTALA" virou braço de luminária | desfazia a correção 2 | LLM não sugere categoria para acessório |
| 10 | Lentidão | 32 itens em série no Gemini gratuito: 483 s | demo inviável ao vivo | extrações em paralelo, processamento sequencial pelo cache |

Cada exemplo virou teste de regressão em `tests/test_regressao_teste_cego.py` e `tests/test_validar_llm.py`.
O benchmark original continuou em 100%.

## Rodada com o Gemini (agentes ligados), depois das correções

| Caso | Status | Duração | Chamadas LLM | Resultado | Evidências |
|---|---|---|---|---|---|
| `cego_itaberai_mat_eletrico` | concluida | 75.2 s | 21 | Compatível 4 · Parcial 4 · Indeterminado 1 · Incompatível 9 · Fora do portfólio 3 | 72/72 |
| `cego_chapadao_iluminacao` | concluida | 242.1 s | 42 | Compatível 4 · Parcial 2 · Indeterminado 1 · Incompatível 5 · Fora do portfólio 20 | 72/72 |

## O que continua em aberto

- **Gabarito humano dos 5 casos**: a planilha `docs/teste_cego_rotulagem.csv` lista cada item com o resultado do sistema;
  a equipe deve preencher `esperado` (duas pessoas, resolvendo divergências) para estes casos entrarem no benchmark.
  Não rotulei os casos eu mesmo para o benchmark não virar circular.
- **Atributos não modelados**: número de condutores do cabo, comprimento do braço, classe de encordoamento.
- **Catálogo demonstrativo**: refletores acima de 200 W, lâmpadas de alta potência e cabos de 16 mm² não existem — os
  INCOMPATÍVEIS desses itens estão corretos, não são erro do sistema.

## Resultado por item (depois das correções)

### cego_itumbiara_refletores

| Item | Categoria | Req. técnicos | Resultado | Melhor produto | Descrição |
|---|---|---|---|---|---|
| 1 | refletor_led | 13 | Incompatível | RFL-30 | REFLETOR LED MODULAR PROFISSIONAL PARA ILUMINAÇÃO DE ESTÁDIOS, CAMPOS DE FUTEBOL, QUADRAS ESPORTIVAS E GINÁSIO |
| 2 | refletor_led | 15 | Incompatível | RFL-30 | REFLETOR LED MODULAR PROFISSIONAL PARA ILUMINAÇÃO DE ESTÁDIOS, ARENAS ESPORTIVAS, CAMPOS DE FUTEBOL E GINÁSIOS |
| 3 | refletor_led | 13 | Incompatível | RFL-30 | REFLETOR LED MODULAR PROFISSIONAL PARA ILUMINAÇÃO DE ESTÁDIOS, CAMPOS DE FUTEBOL, QUADRAS ESPORTIVAS E GINÁSIO |

### cego_itaberai_mat_eletrico

| Item | Categoria | Req. técnicos | Resultado | Melhor produto | Descrição |
|---|---|---|---|---|---|
| 1 | luminaria_publica_led | 3 | Compatível | LPL-100-50K | Luminária Iluminação Pública material: alumínio injetado/policarbonato, modelo: led, aplicação: iluminação púb |
| 2 | refletor_led | 6 | Parcial | RFL-30 | Refletor material corpo: alumínio injetado, aplicação: sistema de iluminação, tipo lâmpada: led, potência lâmp |
| 3 | refletor_led | 6 | Parcial | RFL-50 | Refletor material corpo: alumínio injetado, aplicação: sistema de iluminação, tipo lâmpada: led, potência lâmp |
| 4 | outro | 0 | Fora do portfólio | — | Caixa Medição material: policarbonato, comprimento: 520, largura: 620, profundidade: 253, aplicação: instalaçõ |
| 5 | cabo | 1 | Incompatível | CB-1.5 | Cabo Elétrico Flexível tipo: tripolar chato, cor da cobertura: preta, tensão isolamento: 750, seção nominal: 1 |
| 6 | cabo | 1 | Incompatível | CB-1.5 | Cabo Elétrico Flexível tipo: tripolar chato, cor da cobertura: preta, tensão isolamento: 750, seção nominal: 1 |
| 7 | cabo | 2 | Incompatível | CB-6 | Cabo Elétrico Flexível tipo: fotovoltaico unifilar, aplicação: instalação de módulos fotovoltaico, têmpera con |
| 8 | outro | 0 | Fora do portfólio | — | Passa Fio material: pvc, comprimento: 10, aplicação: passagem cabo/fio, características adicionais: com ponta  |
| 9 | eletroduto | 0 | Indeterminado | ELT-25 | Duto material: polietileno alta densidade (pead), tipo: corrugado, dimensões: 40 cm  x 110, cor: prêta, caract |
| 10 | cabo | 2 | Incompatível | CB-6 | Cabo Elétrico Flexível tipo: fotovoltaico unifilar, aplicação: instalação de módulos fotovoltaico, têmpera con |
| 11 | quadro | 1 | Indeterminado | QD-12 | Quadro Distribuição quantidade fases: 3, barramento: sem barramento, cor: branca, revestimento: pintura eletro |
| 12 | cabo | 2 | Incompatível | CB-6 | Cabo Elétrico Flexível tipo: fotovoltaico unifilar, aplicação: instalação de módulos fotovoltaico, têmpera con |
| 13 | refletor_led | 8 | Incompatível | RFL-100 | Refletor material corpo: alumínio, material refletor: vidro, formato: retangular, aplicação: iluminação extern |
| 14 | refletor_led | 3 | Incompatível | RFL-30 | Refletor material corpo: alumínio, formato: retangular, tipo lâmpada: microled, potência lâmpada: 500, tensão  |
| 15 | luminaria_interna | 4 | Parcial | PNL-40-6060 | Luminária tipo: sobrepor, formato: quadrado, tipo lâmpada: led, características adicionais: ângulo de abertura |
| 16 | cabo | 2 | Incompatível | CB-6 | Cabo Elétrico Flexível tipo: fotovoltaico unifilar, aplicação: instalação de módulos fotovoltaico, têmpera con |
| 17 | disjuntor | 1 | Compatível | DJ-10 | Disjuntor Baixa Tensão funcionamento: termomagnético, acionamento: alavanca, corrente nominal: 16, tipo: mini, |
| 18 | luminaria_publica_led | 2 | Compatível | LPL-100-50K | Luminária Iluminação Pública material: chapa alumínio, aplicação: iluminação pública poste, potência nominal l |
| 19 | refletor_led | 6 | Incompatível | RFL-30 | Refletor material corpo: alumínio injetado, aplicação: sistema de iluminação, tipo lâmpada: led, potência lâmp |
| 20 | luminaria_publica_led | 0 | Indeterminado | LPL-100-50K-PRO | Luminária Iluminação Pública modelo: pétala, aplicação: lâmpada led, potência nominal lâmpada: 50, quantidade  |
| 21 | outro | 0 | Fora do portfólio | — | Sinalizador Trânsito material corpo: polietileno de alta densidade, tipo: giratório, alimentação: solar, carac |

### cego_chapadao_iluminacao

| Item | Categoria | Req. técnicos | Resultado | Melhor produto | Descrição |
|---|---|---|---|---|---|
| 1 | poste | 0 | Fora do portfólio | — | POSTE CONICO CONTINUO EM ACO GALVANIZADO, RETO, ENGASTADO, H = 7 M, DIAMETRO INFERIOR = *125* MM |
| 2 | poste | 0 | Fora do portfólio | — | POSTE DE CONCRETO ARMADO SEÇÃO CIRCULAR, EXTENSÃO 11 METROS, 600 DAN, TIPO C-17 |
| 3 | luminaria_publica_led | 11 | Incompatível | LPL-200-40K | LUMINÁRIA LED 200W, COM CARCAÇA EM ALUMÍNIO INJETADO, LENTE DE POLICARBONATO (RESISTENTE AO AMARELAMENTO PRECO |
| 4 | cabo | 1 | Compatível | CB-10 | CABO DE COBRE, FLEXIVEL, CLASSE 4 OU 5, ISOLACAO EM PVC/A, ANTICHAMA BWF-B, COBERTURA PVC-ST1, ANTICHAMA BWF-B |
| 5 | cabo | 2 | Incompatível | CB-1.5 | CABO DE COBRE NU 35 MM2 MEIO-DURO |
| 6 | outro | 0 | Fora do portfólio | — | SUPORTE PARA 1 PÉTALA PARA LUMINÁRIA DE ILUMINAÇÃO PÚBLICA |
| 7 | eletroduto | 0 | Indeterminado | ELT-25 | ELETRODUTO/DUTO PEAD FLEXIVEL PAREDE SIMPLES, CORRUGACAO HELICOIDAL, COR PRETA, SEM ROSCA, DE 2", CRC 680 N, P |
| 8 | cabo | 2 | Compatível | CB-PP-3x2.5 | CABO ISOLADO PP 3 X 2,5 MM2 |
| 9 | outro | 0 | Fora do portfólio | — | CAIXA DE CONCRETO ARMADO PRE-MOLDADO, SEM FUNDO, QUADRADA, DIMENSOES DE 0,30 X 0,30 X 0,30 M |
| 10 | outro | 1 | Fora do portfólio | — | GRAMPO METALICO TIPO U PARA HASTE DE ATERRAMENTO DE ATE 5/8", CONDUTOR DE 10 A 25 MM2 |
| 11 | outro | 0 | Fora do portfólio | — | HASTE DE ATERRAMENTO EM ACO COM 3,00 M DE COMPRIMENTO E DN = 3/4", REVESTIDA COM BAIXA CAMADA DE COBRE, SEM CO |
| 12 | cabo | 1 | Compatível | CB-4 | CABO DE COBRE, FLEXIVEL, CLASSE 4 OU 5, ISOLACAO EM PVC/A, ANTICHAMA BWF-B, COBERTURA PVC-ST1, ANTICHAMA BWF-B |
| 13 | outro | 0 | Fora do portfólio | — | FITA ISOLANTE ADESIVA ANTICHAMA, USO ATE 750 V, EM ROLO DE 18 MM X 20 M |
| 14 | outro | 0 | Fora do portfólio | — | SUPORTE PARA 2 PÉTALAS PARA LUMINÁRIA DE ILUMINAÇÃO PÚBLICA |
| 15 | outro | 0 | Fora do portfólio | — | SUPORTE PARA 3 PÉTALAS PARA LUMINÁRIA DE ILUMINAÇÃO PÚBLICA |
| 16 | eletroduto | 0 | Indeterminado | ELT-25 | ELETRODUTO/DUTO PEAD FLEXIVEL PAREDE SIMPLES, CORRUGACAO HELICOIDAL, COR PRETA, SEM ROSCA, DE 1 1/2", CRC 680  |
| 17 | outro | 1 | Fora do portfólio | — | CONECTOR DE PERFURAÇÃO PARA UTILIZAÇÃO EM REDES SECUNDÁRIAS MULTIPLEXADAS ATÉ 1KV, EM MATERIAL POLIMÉRICO, CON |
| 18 | cabo | 1 | Compatível | CB-2.5 | CABO DE COBRE, FLEXIVEL, CLASSE 4 OU 5, ISOLACAO EM PVC/A, ANTICHAMA BWF-B, COBERTURA PVC-ST1, ANTICHAMA BWF-B |
| 19 | outro | 1 | Fora do portfólio | — | GRAMPO PARALELO METALICO PARA CABO DE 6 A 50 MM2, COM 1 PARAFUSOS |
| 20 | outro | 0 | Fora do portfólio | — | ARMACAO SECUNDARIA VERTICAL COM HASTE E CONTRA-PINO, EM CHAPA DE ACO GALVANIZADO 3/16", COM 1 ESTRIBO E 1 ISOL |
| 21 | outro | 0 | Fora do portfólio | — | FITA ISOLANTE ADESIVA ANTICHAMA, USO ATE 750 V, EM ROLO DE 19 MM X 5 M |
| 22 | cabo | 1 | Parcial | CB-1.5 | ALCA PREFORMADA DE DISTRIBUICAO, EM ACO GALVANIZADO, PARA CABO DE ALUMINIO DIAMETRO 10MM |
| 23 | outro | 0 | Fora do portfólio | — | TAMPA EM CONCRETO ARMADO 25 MPA E=5CM (0,30*0,30) |
| 24 | luminaria_publica_led | 5 | Incompatível | LPL-100-50K | LUMINARIA PUBLICA SOLAR 6500K. 30.000H, MINIMO 3.800LM, ÂNGULO DE ABERTURA 120°, GRAU DE PROTEÇÃO IP66, TEMPER |
| 25 | refletor_led | 12 | Incompatível | RFL-200 | PROJETOR LED 200W 5000K 43500 LUMENS, GRAU DE PROTEÇÃO IP66, TEMPERATURA - 15°C A +35°C. FATOR DE POTENCIA >0, |
| 26 | outro | 0 | Fora do portfólio | — | CRUZETA PARA NO MINIMO 4 PROJETORES. CRUZETA PARA FIXAÇÃO/SUSTENTAÇÃO DE 04 PROJETORES, FABRICADA COM CANTONEI |
| 27 | outro | 0 | Fora do portfólio | — | FABRICAÇÃO DE FERRO CHATO 1.1/2 X 1/8 – PEÇA 8M |
| 28 | outro | 0 | Fora do portfólio | — | FABRICAÇÃO DE TUBO REDONDO EM AÇO CARBONO, DIÂMETRO 2”, ESPESSURA 2,25MM, COMPRIMENTO ORIGINAL 8,00 M, A SER F |
| 29 | outro | 0 | Fora do portfólio | — | FABRICAÇÃO DE TUBO REDONDO EM AÇO CARBONO, DIÂMETRO 8”, ESPESSURA 2,65MM, COMPRIMENTO ORIGINAL 8,00 M, A SER F |
| 30 | poste | 0 | Fora do portfólio | — | POSTE CONICO CONTINUO EM ACO GALVANIZADO, RETO, ENGASTADO, H = 7 M, DIAMETRO INFERIOR = *125* MM |
| 31 | poste | 0 | Fora do portfólio | — | POSTE DE CONCRETO ARMADO SEÇÃO CIRCULAR, EXTENSÃO 11 METROS, 600 DAN, TIPO C-17 |
| 32 | luminaria_publica_led | 11 | Incompatível | LPL-200-40K | LUMINÁRIA LED 200W, COM CARCAÇA EM ALUMÍNIO INJETADO, LENTE DE POLICARBONATO (RESISTENTE AO AMARELAMENTO PRECO |

### cego_cezarina_ilum_publica

| Item | Categoria | Req. técnicos | Resultado | Melhor produto | Descrição |
|---|---|---|---|---|---|
| 1 | outro | 0 | Fora do portfólio | — | CIMENTO PORTLAND COMPOSTO CP II-32 |
| 2 | outro | 0 | Fora do portfólio | — | CIMENTO PORTLAND COMPOSTO CP II-32 - EXCLUSIVO ME/EPP |
| 3 | outro | 0 | Fora do portfólio | — | FITA DE AUTOFUSÃO, ROLO COM 10 METROS DE COMPRIMENTO, LARGURA MÍNIMA DE 19 MM, COR PRETA, À BASE DE BORRACHA O |
| 4 | outro | 0 | Fora do portfólio | — | FITA ISOLANTE, ROLO COM 20 METROS DE COMPRIMENTO, LARGURA MÍNIMA DE 19 MM, COR PRETA, CONFECCIONADA EM MATERIA |
| 5 | lampada | 4 | Incompatível | LMP-HO-40 | LÂMPADA BULBO LED, BASE E27, BIVOLT 30 W, 4.000 LUMENS, LUZ BRANCA, VIDA ULTIL NOMINAL: 25.000 horas, PRIMEIRA |
| 6 | lampada | 4 | Incompatível | LMP-HO-40 | LÂMPADA BULBO LED, BASE E27, BIVOLT 30 W, 4.000 LUMENS, LUZ BRANCA, VIDA ULTIL NOMINAL: 25.000 horas, PRIMEIRA |
| 7 | lampada | 4 | Incompatível | LMP-HO-40 | LÂMPADA BULBO LED, BASE E27, BIVOLT 50 W, 4.000 LUMENS, LUZ BRANCA, VIDA ULTIL NOMINAL: 25.000 horas, PRIMEIRA |
| 8 | lampada | 4 | Incompatível | LMP-HO-40 | LÂMPADA BULBO LED, BASE E27, BIVOLT 50 W, 4.000 LUMENS, LUZ BRANCA, VIDA ULTIL NOMINAL: 25.000 horas, PRIMEIRA |
| 9 | lampada | 4 | Incompatível | LMP-HO-40 | LÂMPADA BULBO LED, BASE E27, BIVOLT 65 W, 4.000 LUMENS, LUZ BRANCA, VIDA ULTIL NOMINAL: 25.000 horas, PRIMEIRA |
| 10 | lampada | 4 | Incompatível | LMP-HO-40 | LÂMPADA BULBO LED, BASE E27, BIVOLT 65 W, 4.000 LUMENS, LUZ BRANCA, VIDA ULTIL NOMINAL: 25.000 horas, PRIMEIRA |
| 11 | lampada | 4 | Incompatível | LMP-HO-40 | LÂMPADA BULBO LED, BASE E27, BIVOLT 80 W, 4.000 LUMENS, LUZ BRANCA, VIDA ULTIL NOMINAL: 25.000 horas, PRIMEIRA |
| 12 | lampada | 4 | Incompatível | LMP-HO-40 | LÂMPADA BULBO LED, BASE E27, BIVOLT 80 W, 4.000 LUMENS, LUZ BRANCA, VIDA ULTIL NOMINAL: 25.000 horas, PRIMEIRA |
| 13 | lampada | 5 | Incompatível | LMP-BULBO-9 | LÂMPADA BULBO LED, BASE E27, BIVOLT, 100 W, FLUXO LUMINOSO MÍNIMO DE 10.000 LUMENS, LUZ BRANCA, TEMPERATURA DE |
| 14 | lampada | 5 | Incompatível | LMP-BULBO-9 | LÂMPADA BULBO LED, BASE E27, BIVOLT, 100 W, FLUXO LUMINOSO MÍNIMO DE 10.000 LUMENS, LUZ BRANCA, TEMPERATURA DE |
| 15 | outro | 0 | Fora do portfólio | — | ADAPTADOR PORCELANA E40 PARA E27 |
| 16 | refletor_led | 9 | Incompatível | RFL-30 | REFLETOR MODULAR LED 500W, POTÊNCIA: 500W, TEMPERATURA DE COR: 5.500K, TENSÃO DE FUNCIONAMENTO: 85V~265V, FREQ |
| 17 | refletor_led | 9 | Incompatível | RFL-30 | REFLETOR MODULAR LED 500W, POTÊNCIA: 500W, TEMPERATURA DE COR: 5.500K, TENSÃO DE FUNCIONAMENTO: 85V~265V, FREQ |
| 18 | refletor_led | 11 | Incompatível | RFL-30 | REFLETOR LED 1000W, MATERIAL: CORPO EM ALUMÍNIO E PROTEÇÃO DA LENTE EM VIDRO TEMPERADO, POTÊNCIA: 1000W, TEMPE |
| 19 | refletor_led | 11 | Incompatível | RFL-30 | REFLETOR LED 1000W, MATERIAL: CORPO EM ALUMÍNIO E PROTEÇÃO DA LENTE EM VIDRO TEMPERADO, POTÊNCIA: 1000W, TEMPE |
| 20 | refletor_led | 9 | Incompatível | RFL-30 | REFLETOR MODULAR LED 1000W, POTÊNCIA: 1000W, TEMPERATURA DE COR: 5.500K, TENSÃO DE FUNCIONAMENTO: 85V~265V, FR |
| 21 | refletor_led | 9 | Incompatível | RFL-30 | REFLETOR MODULAR LED 1000W, POTÊNCIA: 1000W, TEMPERATURA DE COR: 5.500K, TENSÃO DE FUNCIONAMENTO: 85V~265V, FR |
| 22 | refletor_led | 11 | Incompatível | RFL-200 | PROJETOR DE LED 100W PARA ÁREA EXTERNA, TENSÃO BIVOLT, TEMPERATURA DE COR DE 4000K A 5000K, FLUXO LUMINOSO MÍN |
| 23 | refletor_led | 11 | Incompatível | RFL-200 | PROJETOR DE LED 150W PARA ÁREA EXTERNA, TENSÃO BIVOLT, TEMPERATURA DE COR DE 4000K A 5000K, FLUXO LUMINOSO MÍN |
| 24 | refletor_led | 11 | Incompatível | RFL-200 | PROJETOR DE LED 150W PARA ÁREA EXTERNA, TENSÃO BIVOLT, TEMPERATURA DE COR DE 4000K A 5000K, FLUXO LUMINOSO MÍN |
| 25 | refletor_led | 11 | Incompatível | RFL-200 | PROJETOR DE LED 50W PARA ÁREA EXTERNA, TENSÃO BIVOLT/AUTOVOLT, TEMPERATURA DE COR DE 4000K A 5000K, FLUXO LUMI |
| 26 | rele_fotoeletrico | 3 | Parcial | RF-MULTI | RELÉ FOTOELÉTRICO PARA ILUMINAÇÃO PÚBLICA, TENSÃO DE OPERAÇÃO 220V, CORRENTE NOMINAL MÍNIMA DE 10A, COM ACIONA |
| 27 | rele_fotoeletrico | 3 | Parcial | RF-MULTI | RELÉ FOTOELÉTRICO PARA ILUMINAÇÃO PÚBLICA, TENSÃO DE OPERAÇÃO 220V, CORRENTE NOMINAL MÍNIMA DE 10A, COM ACIONA |
| 28 | outro | 3 | Fora do portfólio | — | BASE PARA RELÉ FOTOELÉTRICO, PARA INSTALAÇÃO EM SISTEMAS DE ILUMINAÇÃO PÚBLICA, MODELO COMPATÍVEL COM RELÉ FOT |
| 29 | braco_luminaria | 0 | Indeterminado | BR-1M | BRAÇO PARA ILUMINAÇÃO PÚBLICA, COM 1,50 METRO DE COMPRIMENTO, RETO, CONFECCIONADO EM AÇO CARBONO GALVANIZADO,  |
| 30 | braco_luminaria | 0 | Indeterminado | BR-1M | BRAÇO PARA ILUMINAÇÃO PÚBLICA, COM 1,50 METRO DE COMPRIMENTO, RETO, CONFECCIONADO EM AÇO CARBONO GALVANIZADO,  |
| 31 | braco_luminaria | 0 | Indeterminado | BR-1M | BRAÇO PARA ILUMINAÇÃO PÚBLICA, COM 1,00 METRO DE COMPRIMENTO, RETO, CONFECCIONADO EM AÇO CARBONO GALVANIZADO,  |
| 32 | braco_luminaria | 0 | Indeterminado | BR-1M | BRAÇO PARA ILUMINAÇÃO PÚBLICA, COM 1,00 METRO DE COMPRIMENTO, RETO, CONFECCIONADO EM AÇO CARBONO GALVANIZADO,  |
| 33 | outro | 2 | Fora do portfólio | — | BOBINA PARA CONTATOR 60A, TENSÃO DE COMANDO 220V, FREQUÊNCIA 60 HZ, COMPATÍVEL COM CONTATOR DE CAPACIDADE NOMI |
| 34 | outro | 3 | Fora do portfólio | — | CONTATOR TRIPOLAR 60A, TENSÃO DA BOBINA 220V, FREQUÊNCIA 60 HZ, CORRENTE NOMINAL MÍNIMA DE 60A, PARA ACIONAMEN |

### cego_anapolis_consumo

| Item | Categoria | Req. técnicos | Resultado | Melhor produto | Descrição |
|---|---|---|---|---|---|
| 1 | outro | 0 | Fora do portfólio | — | Haste Aterramento Haste Aterramento, Material:Aço Carbono, Tipo:Cilíndrica, Revestimento:Cobre, Tratamento Sup |
| 2 | outro | 1 | Fora do portfólio | — | Placa Cega Placa Cega, Material:Alumínio Anodizado, Formato:Retangular, Comprimento:4 POL, Largura:2 POL, Diâm |
| 3 | quadro | 0 | Indeterminado | QD-12 | Quadro Distribuição Quadro Distribuição, Quantidade Fases:3, Barramento:Cobre Eletrolítico Para Fases Neutra E |
| 4 | cabo | 1 | Compatível | CB-1.5 | Cabo Elétrico Flexível Cabo Elétrico Flexível, Tensão Isolamento:750 V, Material:Cobre Eletrolítico, Revestime |
| 5 | quadro | 1 | Indeterminado | QD-12 | Quadro Distribuição Quadro Distribuição, Quantidade Fases:3, Barramento:Cobre Eletrolítico + Neutro Isolado E  |
| 6 | outro | 0 | Fora do portfólio | — | Espaçador De Cabos Espaçador De Cabos, Material:Polimérico, Tipo:Losangular, Tensão Nominal:15 KV, Cor:Cinza/P |
| 7 | cabo | 1 | Compatível | CB-2.5 | Cabo Elétrico Isolado material condutor: cobre nu, têmpera condutor: mole, seção nominal: 2,5, tensão isolamen |
| 8 | cabo | 1 | Compatível | CB-2.5 | Cabo Elétrico Isolado material condutor: cobre nu, têmpera condutor: mole, seção nominal: 2,5, tensão isolamen |
| 9 | cabo | 2 | Compatível | CB-PP-3x2.5 | Cabo Elétrico Flexível Cabo Elétrico Flexível, Tipo:Pp, Têmpera Condutor:Mole, Cor Da Cobertura:Preta, Formaçã |
| 10 | eletroduto | 0 | Indeterminado | ELT-25 | Eletroduto Eletroduto, Material:Pvc, Tipo:Rígido Anti-Chama, Cor:Cinza, Características Adicionais:Com Rosca,  |
| 11 | outro | 1 | Fora do portfólio | — | Luva Emenda Compressão Luva Emenda Compressão, Tipo:Pré-Isolado, Material:Cobre, Bitola Condutor:2,5 MM |
| 12 | outro | 1 | Fora do portfólio | — | Luva Emenda Compressão Luva Emenda Compressão, Tipo:Pré-Isolado, Material:Cobre, Bitola Condutor:4 MM |
| 13 | outro | 0 | Fora do portfólio | — | Luva Emenda Compressão Luva Emenda Compressão, Tipo:Pré-Isolado, Material:Cobre, Faixa De Bitolas Do Condutor: |
| 14 | cabo | 1 | Incompatível | CB-1.5 | Cabo Lógico Blindado Cabo Lógico Blindado, Aplicação:Para Rede Cat6e Sem Espelho, Formação Do Cabo:4 X 24 AWG, |
| 15 | eletroduto | 0 | Indeterminado | ELT-25 | Eletroduto Eletroduto, Material:Pvc, Tipo:Flexível Corrugado, Cor:Amarela, Diâmetro Nominal:3/4 POL |
| 16 | outro | 1 | Fora do portfólio | — | Campainha Elétrica Campainha Elétrica, Material:Plástico, Tensão Alimentação:220 V, Cor:Branca, Característica |
| 17 | outro | 0 | Fora do portfólio | — | Canaleta Canaleta, Material:Pvc Rígido, Cor:Cinza, Características Adicionais:Para Piso, De Alto Impacto, Anti |
| 18 | cabo | 2 | Incompatível | CB-4 | Cabo Elétrico Flexível Cabo Elétrico Flexível, Tipo:Pp, Têmpera Condutor:Mole, Cor Da Cobertura:Preta, Formaçã |
| 19 | cabo | 3 | Incompatível | CB-4 | Cabo Elétrico Flexível Cabo Elétrico Flexível, Tipo:Pp, Têmpera Condutor:Mole, Formação Do Cabo:3 X 4 MM2, Ten |
| 20 | luminaria_interna | 0 | Indeterminado | PNL-40-6060 | Plafonier Plafonier, Material Corpo:Pvc, Cor:Branca, Características Adicionais:Duplo Com Soquetes De Porcelan |
| 21 | luminaria_interna | 0 | Indeterminado | PNL-40-6060 | Luminária Luminária, Tipo:Emergência, Material Corpo:Plástico Abs Alto Impacto, Formato:Retangular, Tipo Lâmpa |
| 22 | cabo | 1 | Compatível | CB-10 | Cabo Elétrico Isolado material condutor: cobre nu, têmpera condutor: mole, seção nominal: 10, tensão isolament |
| 23 | cabo | 1 | Compatível | CB-10 | Cabo Elétrico Isolado material condutor: cobre nu, têmpera condutor: mole, seção nominal: 10, tensão isolament |
| 24 | outro | 0 | Fora do portfólio | — | Abraçadeira Abraçadeira, Material:Pvc - Cloreto De Polivinila, Diâmetro Amarração:3/4 POL, Cor:Cinza |
| 25 | poste | 1 | Fora do portfólio | — | Poste Final Poste Final, Tipo:Poste Solar Fotovoltaico, Material Do Mastro:Aço Galvanizado, Altura Do Mastro:6 |
| 26 | poste | 1 | Fora do portfólio | — | Poste Final Poste Final, Tipo:Poste Solar Fotovoltaico, Material Do Mastro:Aço Galvanizado, Altura Do Mastro:6 |
| 27 | luminaria_interna | 1 | Parcial | PNL-40-6060 | Luminária Luminária, Material Corpo:Alumínio, Tipo Lâmpada:Led |
| 28 | luminaria_publica_led | 6 | Incompatível | LPL-150-50K-PRO | Luminária Luminária, Tipo:Pública, Material Corpo:Alumínio Injetado Alta Pressão, Tipo Lâmpada:Led, Caracterís |
| 29 | outro | 0 | Fora do portfólio | — | Isolador Epoxi Isolador Epoxi, Tipo / Modelo:Paralelo, Tamanho Da Rosca:1/4 POL, Dimensões:16 X 20 MM, Aplicaç |
| 30 | outro | 0 | Fora do portfólio | — | Isolador Epoxi Isolador Epoxi, Tipo / Modelo:Mns, Tamanho Da Rosca:1/4 POL, Dimensões:25 X 30 MM, Cor:Laranja, |
| 31 | dispositivos | 1 | Incompatível | TM-2PT-10 | Tomada Tomada, Tipo:Fêmea, Cor Corpo:Bege, Tensão Nominal:125/250 V, Aplicação:Extensão Elétrica, Número Conta |
| 32 | dispositivos | 0 | Indeterminado | TM-2PT-10 | Espelho Tomada Espelho Tomada, Material:Pvc, Formato:4 X 4 POL, Cor:Cinza, Características Adicionais:Para 2 T |
| 33 | outro | 0 | Fora do portfólio | — | Conexão Hidráulica Conexão Hidráulica, Material:Pvc - Cloreto De Polivinila, Tipo:Adaptador Com Flanges, Tipo  |
| 34 | outro | 1 | Fora do portfólio | — | Tampa Condulete Tampa Condulete, Material:Pvc, Cor:Cinza, Bitola:4 X 2 POL, Características Adicionais:Com Mol |
| 35 | outro | 0 | Fora do portfólio | — | Eletrocalha Eletrocalha, Material:Aço, Tratamento Superficial:Galvanização A Fogo, Comprimento:3.000 MM, Altur |
| 36 | outro | 0 | Fora do portfólio | — | Suporte Eletrocalha Suporte Eletrocalha, Tipo:Vertical, Largura:300 MM, Altura:100 MM, Material:Aço, Tratament |
| 37 | outro | 0 | Fora do portfólio | — | Eletrocalha Eletrocalha, Material:Aço Galvanizado, Comprimento:3.000 MM, Altura:100 MM, Largura:150 MM, Caract |
| 38 | outro | 0 | Fora do portfólio | — | Parafuso Parafuso, Material:Aço Zincado, Tipo:Cabeça Lentilha, Comprimento:1/2 POL, Diâmetro:1/4 POL |
| 39 | outro | 1 | Fora do portfólio | — | Bóia Caixa D'Água Bóia Caixa D'Água, Material:Metal, Tipo:Pressão, Bitola:3 POL, Características Adicionais:Ha |
| 40 | outro | 1 | Fora do portfólio | — | Capacitor Capacitor, Capacitância:20 + 5 MF, Aplicação:Ar Condicionado, Número De Fases:Monofásico, Tensão Nom |
| 41 | outro | 2 | Fora do portfólio | — | Resistência Elétrica Resistência Elétrica, Potência:4.400 W, Tensão:220 V, Aplicação:Chuveiro Elétrico, Marca  |
| 42 | bateria | 0 | Fora do portfólio | — | Bateria Recarregável Bateria Recarregável, Tipo:M18 Milwaukee, Aplicação 1:Ferramentas Elétricas Sem Fio, Sist |
| 43 | luminaria_interna | 0 | Indeterminado | PNL-40-6060 | Luminária Luminária, Tipo:Emergência, Material Corpo:Plástico Abs Alto Impacto, Formato:Retangular, Tipo Lâmpa |
