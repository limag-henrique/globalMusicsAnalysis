# Cotas para nova importação de sucessos anuais — 30/10/2026

## Resultado e escopo

Plano para os 68 mercados já analisados, janela candidata 2017–2026. São cotas de músicas por país e ano, não por década e não por plataforma. Uma fonte principal é escolhida para cada célula: calendário completo primeiro; Spotify tem preferência em igualdade de completude. Spotify e YouTube não têm reproduções somadas. Provedores espelhados não são somados.

O cálculo reconstruiu 235,461 linhas de ranking até a posição 500. Os metadados históricos locais vêm de MGD e Kaggle para Spotify (2017–2022) e capturas web de YouTube (2025–2026). Isso comprova a presença de arquivos locais, não acesso gratuito atual a qualquer data de 2017–2026. A ausência local exige verificar a fonte e coletar, não significa indisponibilidade definitiva de uma API ou página web. Não houve coleta nova de rankings, importação em banco ou análise paga.

O corte das capturas utilizadas é 15/10/2026. Rankings de 2026 são acumulados parciais. YouTube usa o ano de encerramento da semana, inclusive semanas que cruzam a virada do ano. Calendário completo não prova profundidade integral, extração correta, identidade de gravação ou integridade da letra. Dias fora da parada não equivalem a zero streams: o total mede reproduções registradas enquanto a faixa esteve no quadro observado, não todo o consumo nacional.

## Regra de cálculo

Base de 100 por país/ano, teto 500, passos de 10. O peso é sqrt(população2024/1.000.000) × (1 + 0,5 × diversidade étnica histórica). A cota é min(500, 100 + 10 × floor(coeficiente × peso / 10)).

Coeficiente principal calibrado: 7.470872933482. Expansão: 13.391866505117. Os coeficientes foram encontrados por busca monotônica, sob dois limites simultâneos: união das identidades observadas e total máximo de participações país/ano para dez anos.

Principal: até 24.000 candidatos conhecidos, com 6.000 reservados na meta de 30.000; no máximo 100.000 participações se todos os 68 mercados tiverem dez anos. Expansão: até 36.000 conhecidos e meta de 45.000, com no máximo 125.000 participações. Os números de cotas são decisões operacionais explícitas, não precisão estatística garantida.

População: Banco Mundial 2024, SP.POP.TOTL, resposta local atualizada em 08/10/2026. Exceção Taiwan: 23.400.220 no registro domiciliar ao fim de 2024, Ministério do Interior, conceito diferente do residente de meio de ano do Banco Mundial. Fontes por linha nos arquivos de cotas.

Diversidade: Alesina et al. (2003), índice étnico dos autores, dados de 1981–2001 nos 68 mercados. Não é diversidade atual e não garante representação de grupos internos em uma parada nacional. Usado somente como prioridade histórica limitada. A sensibilidade só população foi recalibrada sob os mesmos limites; consta da tabela e da planilha. Não se misturaram as medidas linguística e religiosa ao índice étnico. Documentação e fontes: research/annual_allocation_demographic_sources_20261030.md.

## Volume e custo

- Principal observado: 71,348 participações país/ano e 23,984 identidades candidatas distintas.
- Destas, 40,520 participações e 16,410 candidatos estão em 270 calendários elegíveis. Incluem 48 janelas parciais de 2026 e 222 células anuais completas.
- Expansão observada: 30,184 identidades candidatas distintas.
- Hipótese fornecida pelo pesquisador: US$0,001 por música. Principal observado: US$23.984; expansão: US$30.184. Metas globais de 30.000 e 45.000 equivalem a US$30 e US$45 sob essa hipótese.
- Principal para todos os dez anos, sem qualquer reaproveitamento: 99,800 participações, equivalentes a US$99.80 na mesma hipótese. Expansão: 125,000, equivalentes a US$125.00. São limites aritméticos de uma classificação por participação ao custo assumido, não garantias de faturamento, e não incluem tentativas adicionais, múltiplas versões ou revisão humana.

Esses candidatos não são letras únicas validadas. IDs Spotify são reaproveitados entre países/anos; metadados YouTube normalizados são candidatos provisórios. Não se fundiram Spotify e YouTube por título/artista. Uma reconciliação correta pode reduzir duplicações entre plataformas, enquanto erros de identidade, variantes e novas coletas podem alterar a contagem. O orçamento de produção deve ser refeito sobre edições textuais validadas e piloto real. Teto total vigente informado pelo usuário: US$150; configurações de campanhas antigas não foram editadas.

Ao completar anos faltantes, reordenar o quadro anual inteiro e recalcular a união global. Não acrescentar simplesmente as novas músicas ao fim da lista antiga. A reserva de 6.000 não garante que todos os dados futuros caibam em 30.000; se a união exceder a meta, recalibrar antes de chamadas pagas. Não cobrar novas classificações incompatíveis como se fossem reaproveitamento do mesmo resultado.

## Disponibilidade

2017 e 2022 não têm células anuais completas no material analisado. Em 2018 há 48; em 2019, 53; em 2020, 60; em 2021, 11; em 2025, 50. Em 2026 há 48 janelas completas até o corte parcial. Não há arquivos de ranking usados neste cálculo para 2023–2024. A matriz contém 194 células sem dados locais e 216 com calendário incompleto. Uma cota de 230 não autoriza inventar as posições faltantes nem usar um snapshot diário como ranking anual.

Manter o mesmo critério de seleção antes de recuperar letras. Não substituir silenciosamente um sucesso por música inferior por falta de letra. Déficits de coleta, identidade e letra ficam explícitos. O estudo descreve sucessos selecionados, não uma amostra probabilística da população ou de toda a música de um país. Comparações devem usar denominadores e cobertura próprios, com uma análise comum do Top 100 quando disponível.

## Cotas completas

| ISO | Mercado | Principal por ano | Expansão por ano | Só população por ano |
| --- | --- | ---: | ---: | ---: |
| IN | Índia | 440 | 500 | 430 |
| US | Estados Unidos | 270 | 400 | 260 |
| ID | Indonésia | 270 | 400 | 240 |
| BR | Brasil | 230 | 340 | 220 |
| RU | Rússia | 200 | 280 | 200 |
| MX | México | 200 | 290 | 200 |
| JP | Japão | 180 | 240 | 190 |
| EG | Egito | 180 | 250 | 190 |
| PH | Filipinas | 180 | 260 | 190 |
| VN | Vietnã | 180 | 250 | 180 |
| TR | Turquia | 180 | 240 | 180 |
| TH | Tailândia | 180 | 240 | 170 |
| ZA | África do Sul | 180 | 240 | 170 |
| DE | Alemanha | 170 | 230 | 170 |
| CO | Colômbia | 170 | 220 | 160 |
| GB | Reino Unido | 160 | 210 | 170 |
| FR | França | 160 | 210 | 170 |
| IT | Itália | 160 | 200 | 160 |
| ES | Espanha | 160 | 210 | 160 |
| CA | Canadá | 160 | 210 | 150 |
| KR | Coreia do Sul | 150 | 190 | 160 |
| AR | Argentina | 150 | 200 | 150 |
| MA | Marrocos | 150 | 200 | 150 |
| UA | Ucrânia | 150 | 200 | 150 |
| MY | Malásia | 150 | 200 | 150 |
| PE | Peru | 150 | 200 | 150 |
| PL | Polônia | 140 | 180 | 150 |
| SA | Arábia Saudita | 140 | 180 | 150 |
| AU | Austrália | 140 | 170 | 140 |
| TW | Taiwan | 140 | 170 | 140 |
| GT | Guatemala | 140 | 170 | 130 |
| EC | Equador | 140 | 170 | 130 |
| CL | Chile | 130 | 160 | 130 |
| RO | Romênia | 130 | 160 | 130 |
| NL | Países Baixos | 130 | 150 | 130 |
| BO | Bolívia | 130 | 160 | 130 |
| BE | Bélgica | 130 | 150 | 130 |
| DO | República Dominicana | 130 | 150 | 120 |
| AE | Emirados Árabes Unidos | 130 | 150 | 120 |
| CZ | Chéquia | 120 | 150 | 120 |
| HN | Honduras | 120 | 140 | 120 |
| PT | Portugal | 120 | 140 | 120 |
| SE | Suécia | 120 | 140 | 120 |
| GR | Grécia | 120 | 140 | 120 |
| IL | Israel | 120 | 140 | 120 |
| HU | Hungria | 120 | 140 | 120 |
| AT | Áustria | 120 | 140 | 120 |
| CH | Suíça | 120 | 150 | 120 |
| PY | Paraguai | 120 | 130 | 120 |
| NI | Nicarágua | 120 | 140 | 120 |
| BG | Bulgária | 120 | 140 | 120 |
| SV | El Salvador | 120 | 130 | 120 |
| SG | Cingapura | 120 | 130 | 120 |
| NZ | Nova Zelândia | 120 | 130 | 120 |
| PA | Panamá | 120 | 130 | 110 |
| DK | Dinamarca | 110 | 130 | 120 |
| FI | Finlândia | 110 | 130 | 120 |
| NO | Noruega | 110 | 130 | 120 |
| SK | Eslováquia | 110 | 130 | 120 |
| IE | Irlanda | 110 | 130 | 120 |
| CR | Costa Rica | 110 | 130 | 110 |
| UY | Uruguai | 110 | 120 | 110 |
| LT | Lituânia | 110 | 120 | 110 |
| LV | Letônia | 110 | 120 | 110 |
| EE | Estônia | 110 | 110 | 110 |
| LU | Luxemburgo | 100 | 110 | 100 |
| IS | Islândia | 100 | 100 | 100 |
| AD | Andorra | 100 | 100 | 100 |

## Arquivos e operação

- country_quotas.csv: regra por país.
- country_year_import_plan.csv: 680 células com cota, fonte e disponibilidade.
- import_calendar_eligible.csv: lista nominal, ordenada por ranking anual, apenas de calendários completos na janela correspondente. Inclui 2026 parcial e identidades pendentes.
- selected_observed_planning.csv: seleção observada para planejamento, incluindo calendários incompletos; não usar como ranking anual final.
- rankings.parquet e source_coverage.csv: base intermediária de análise.
- allocation_summary.json: parâmetros, estimativas e ressalvas.
- research/calculate_import_quotas_20261030.py: reprodução local sem rede ou banco.

Os importadores antigos mantêm limites fixos de 80/200 em alguns contratos. Este trabalho entrega cálculo e manifesto, não modifica esses importadores nem inicia a coleta. Não executar o comando antigo supondo que ele aplicará estas cotas. A nova execução deve consumir a política por país/ano e preservar as validações acima.

## Verificação

Verificados: 68 países únicos, 680 células únicas, cotas inteiras em passos de dez, ordenação decrescente, deduplicação das identidades e conciliação dos totais. O Top 230 do Brasil em 2019 foi conferido independentemente em pandas, com correspondência exata de IDs, ordem e reproduções com a agregação do MGD. A planilha Excel compara todas as fórmulas de cota às saídas do cálculo, passa por varredura de erros e é renderizada para inspeção. Nenhum gasto foi realizado.
