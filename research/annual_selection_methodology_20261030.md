# Dimensionamento da seleção anual de músicas por país

Data: 30/10/2026. Status: proposta metodológica baseada em fontes primárias e análise descritiva local. Não substitui as especificações vigentes nem autoriza execução paga. Nenhum ranking, letra, classificação ou banco de produção foi alterado.

## Recomendação

Importar e preservar todos os metadados disponíveis do ranking. Dimensionar separadamente a recuperação e classificação das letras. Não estabelecer cotas por população, receita do mercado, país nomeado ou uma escala arbitrária de 80/120/160/200.

Para o objetivo de comparar a circulação dos temas das letras nos sucessos de cada mercado, adotar como resultado principal a prevalência ponderada pelas reproduções observadas, por país, plataforma e ano. Usar inicialmente cobertura de 95% dessas reproduções como cenário de planejamento, comparar com 90% e 97,5%, e definir a tolerância final antes de observar os novos resultados temáticos. O número de músicas deve resultar dessa regra. Não existe nas fontes consultadas um percentual universal obrigatório.

Se a pergunta principal continuar sendo a proporção de músicas distintas do repertório anual com cada tema, a seleção por massa de streams não basta: usar censo do repertório observado ou amostragem probabilística estratificada. Essa distinção precisa constar do protocolo; alterar a ponderação altera a pergunta científica.

## O que está sendo contado

Separar quatro quantidades:

1. Observações de ranking: item, país, plataforma e período nativo, preservando fonte e proveniência.
2. Itens ou gravações que integram o quadro anual e suas reproduções observadas.
3. Edições textuais validadas, com vínculos auditados às gravações.
4. Classificações compatíveis com hash textual, rubrica, prompt e modelo definidos.

Uma letra pode ser classificada uma vez e reutilizada em muitos países/anos. Cada país conserva seu peso próprio. Não unir remixes, versões limpas/explícitas, traduções ou faixas de mesmo título sem evidência suficiente. Deduplicar custo textual não permite apagar as diferentes gravações ou ocorrências do ranking.

## Por que população e Top-N fixo são insuficientes

População humana não é a unidade amostral deste estudo. Diversidade do repertório, distribuição de reproduções, precisão desejada e desenho amostral são relevantes. A Statistics Canada explicita que tamanhos amostrais dependem de objetivos, variabilidade, precisão e desenho; acima de certo tamanho populacional, dobrar a população não exige dobrar a amostra. [Fonte](https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/sample-echantillon/5214900-eng.htm).

Um top fixo compara a mesma faixa de posições, o que pode ser legítimo para estudar os maiores sucessos. Mas não garante a mesma participação nas reproduções, nem amostra aleatória do repertório. Dar 200 músicas ao Brasil e 80 à República Dominicana combina recortes de popularidade diferentes. Por outro lado, dar 80 a ambos tampouco garante cobertura semelhante.

Um top determinístico não recebe a margem de erro de uma amostra aleatória. Aumentar N não corrige automaticamente viés de seleção, identidade ou cobertura. [Statistics Canada: amostragem não probabilística](https://www150.statcan.gc.ca/n1/edu/power-pouvoir/ch13/nonprob/5214898-eng.htm).

## Análise empírica local

Entrada: `data/normalized/mgd_observations.parquet`, provedor MGD, Spotify Top 200 diário. Foram examinadas 311 células país/ano entre 2017 e 2021, excluindo GLOBAL. Não foram somados provedores espelhados. Duplicações por país/data/ID nativo foram reduzidas a um registro; conflitos de métrica/posição e valores inválidos foram contabilizados. As estatísticas centrais abaixo usam apenas 120 células com todos os dias do calendário e exatamente 200 itens distintos por dia, sem conflitos ou inválidos detectados.

Esta é uma análise de itens nativos Spotify. Não equivale a uma deduplicação científica final de gravações, nem certifica a correção de identidade, território e extração dos arquivos de origem. A condição de profundidade é conservadora; uma parada oficialmente mais curta pode ser válida, mas precisa de verificação documental. Dias presentes com menos de 200 itens não foram automaticamente considerados completos em profundidade.

| Medida nas 120 células | Mínimo | Mediana | Máximo |
| --- | ---: | ---: | ---: |
| Participação do Top 80 nas reproduções observadas | 31,5% | 41,7% | 57,6% |
| Participação do Top 200 nas reproduções observadas | 53,5% | 68,7% | 82,8% |
| Itens necessários para 80% | 179 | 300,5 | 502 |
| Itens necessários para 90% | 278 | 458,5 | 816 |
| Itens necessários para 95% | 382 | 608 | 1.163 |
| Itens necessários para 97,5% | 469 | 771,5 | 1.521 |

A mediana pode ser fracionária porque resume um conjunto com número par de células. Não é uma instrução para selecionar frações de música. Os extremos não são projeções para anos futuros ou outras plataformas.

Exemplo com calendário de 2019 completo:

| Mercado | Itens no quadro anual | Cobertura Top 80 | Cobertura Top 200 | N para 90% | N para 95% |
| --- | ---: | ---: | ---: | ---: | ---: |
| Brasil | 1.095 | 43,7% | 72,3% | 365 | 464 |
| República Dominicana | 1.243 | 48,2% | 74,5% | 358 | 469 |

Brasil tem 365 dias com profundidade 200. República Dominicana tem 365 dias, mas profundidade mínima 199; por isso serve como ilustração provisória e não integra o resumo de 120 células. Os resultados mostram que um mercado menor pode precisar de quantidade semelhante ou superior para a mesma cobertura. Em 2018, o N de 95% foi 521 para Brasil e 549 para República Dominicana; esta última tem profundidade mínima 157 e exige investigação adicional.

O Top 200 diário não limita a união anual a 200 músicas: entradas e saídas produzem um quadro anual com centenas ou milhares de itens. Para o Brasil de 2019, uma verificação independente em pandas reproduziu 73.000 linhas, 365 dias, 1.095 itens, 11.105.842.661 streams observados, cobertura Top 80 de 0,43747698615086655 e N95 de 464.

Artefatos reproduzíveis:

- Script: `research/annual_selection_analysis_20261030.py`.
- Resultados: `data/derived/research_quality/annual-selection-method-20261030/country_year_sensitivity.csv`.
- Resumo: `data/derived/research_quality/annual-selection-method-20261030/summary.json`.

## O denominador precisa ser honesto

Se a entrada é a união de paradas diárias, somam-se as reproduções somente nos dias em que o item foi registrado. Dias fora do Top 200 não significam zero reproduções. Portanto, o quadro é um ranking reconstruído por streams observados na parada, não necessariamente o ranking anual oficial da plataforma.

O próprio Spotify informa que nem toda reprodução é elegível às paradas e que pico de posição é outra medida. [Spotify: Understanding Spotify charts](https://support.spotify.com/us/artists/article/understanding-spotify-charts/).

Preferir um ranking anual oficial territorial com contagens comparáveis e profundidade documentada, quando disponível e compatível com o objetivo. Caso só sejam fornecidos os primeiros 100/200, isso não identifica o consumo fora do quadro publicado. Sem contagens, não se pode calcular participação em streams: rankings apenas por posição exigem análise separada. Não inventar pesos de reprodução a partir de posições.

Calendário incompleto, profundidade desconhecida, falha de extração e censura natural abaixo do corte são problemas diferentes. Recuperar dados faltantes antes da seleção; não corrigir sazonalidade multiplicando automaticamente um ano parcial por 365/dias observados. O ano de 2026 deve ser tratado como parcial, com janela equivalente se comparado a outros anos.

Não somar streams de Spotify com views de YouTube; não somar a cópia MGD à cópia Kaggle; não combinar registros diários e semanais sobrepostos. Mudança de plataforma ao longo da série deve ficar visível e não pode ser interpretada automaticamente como mudança temática de um país.

## Regra adaptativa proposta

Para cada país c, ano a e plataforma p:

1. Auditar quadro e períodos; resolver duplicações, fontes e conflitos.
2. Estabelecer a unidade de gravação e conservar a linhagem dos itens nativos.
3. Ordenar pelo total anual comparável w_i.
4. Calcular W = soma de w_i no quadro inteiro, antes de truncar candidatos.
5. Definir N(q) como o menor N com soma dos primeiros N pesos / W >= q.
6. Comparar q = 90%, 95% e 97,5%; orçar a união de letras únicas de cada cenário.
7. Congelar q e a regra de empates antes da reclassificação. Preferir incluir todo o empate na fronteira quando o total coincidir, documentando o pequeno excedente.
8. Recuperar e validar as letras; manter ausências no denominador e registrar cobertura efetivamente classificada.

Não há piso ou teto universal. Um limite operacional pode existir, mas uma célula que o alcança sem cumprir q permanece abaixo do alvo. Não chamá-la de completa. Ausência de letra não autoriza substituir silenciosamente um sucesso pelo próximo item para completar uma contagem.

## Quanto de incerteza a cobertura deixa

Derivação própria, sem pressupor amostragem aleatória: para uma categoria binária, seja C a fração do total de streams efetivamente vinculada a rótulos corretos e A a soma de streams positivos conhecidos dividida por W. A prevalência no quadro inteiro pertence a [A, A + 1-C]. A parcela desconhecida pode ser toda negativa ou toda positiva.

| Cobertura efetivamente classificada | Largura máxima do intervalo por tema/país |
| --- | ---: |
| 80% | 20 pontos percentuais |
| 90% | 10 pontos percentuais |
| 95% | 5 pontos percentuais |
| 97,5% | 2,5 pontos percentuais |

São limites determinísticos da informação faltante, não intervalos de confiança, e não incluem erro do Gemini nem defeitos de dados. Exemplo: C=95% e 40% de positivos na parte conhecida implicam prevalência total entre 38% e 43%. Para uma diferença entre dois países com C=95%, o intervalo da diferença pode ter largura de 10 pontos. Comparações pequenas ou posições próximas não devem gerar uma ordenação definitiva sem evidência suficiente.

Cobertura da seleção não é cobertura da classificação: selecionar 95% e falhar em letras de 8% do total deixa apenas 87% classificados. Também não é possível usar a regra de 95% dos streams para assegurar cobertura de 95% das músicas distintas.

Nos escores de intensidade de 0 a 3, aplicar o raciocínio à intensidade normalizada em [0,1] ou explicitar o fator de escala. Não somar os 26 temas como se fossem categorias mutuamente exclusivas.

## Alternativa quando 95% não couber no orçamento

Para inferir sobre o quadro observado inteiro com menor custo, considerar um desenho em dois estratos: incluir os grandes sucessos com certeza e sortear probabilisticamente músicas da parte restante. Registrar probabilidades, semente, estratos, repetição de sorteios se houver e estimadores adequados. Para exposição, amostragem proporcional aos streams pode ser eficiente; para repertório de músicas, um sorteio estratificado por faixa de popularidade pode ser mais adequado. A estimativa final combina os estratos com seus pesos, não com média simples das músicas obtidas.

O tamanho da parte sorteada é definido pela precisão requerida, variabilidade temática, perdas e custo do piloto. Não deve ser fixado agora em um número universal. A precisão deve considerar os temas prioritários e o conjunto de comparações, não apenas uma categoria binária isolada. Se o desenho for escolhido, precisa de especificação estatística própria antes de implementação. Um top puro é mais simples; a amostra probabilística pode oferecer melhor custo-precisão, mas requer ponderação e estimação de variância corretas.

Para composição do repertório, alternativas são censo de todas as gravações do quadro ou esse desenho probabilístico com pesos apropriados. A média não ponderada apenas do Top N(q) descreve o subconjunto selecionado, não toda a música do país.

## Custo e Gemini

Nas 120 células mais completas, a união de IDs nativos selecionados foi:

| Regra | IDs únicos na união |
| --- | ---: |
| Top 80 | 3.699 |
| Top 200 | 8.473 |
| Cobertura 80% | 13.192 |
| Cobertura 90% | 19.974 |
| Cobertura 95% | 26.931 |
| Cobertura 97,5% | 34.370 |

Esses valores não são quantidades finais de letras únicas, nem orçamento: IDs diferentes podem ter a mesma edição textual validada, e a cobertura de países/anos é apenas um subconjunto do projeto. O custo deve ser estimado após deduplicação textual e piloto, incluindo tokens de entrada/saída, tradução se usada, tentativas, revisão humana e compromissos já assumidos. A documentação local registra teto global de US$180 e preparação sem chamadas pagas; esta análise não altera isso.

O piloto deve representar idiomas reais, gêneros, faixas de popularidade e categorias; português/inglês não podem ser usados como substitutos de todos os idiomas. Separar revisão direcionada a erros de auditoria probabilística para estimar desempenho. Manter rótulos humanos independentes e reservar dados de validação que não foram usados para ajustar o prompt.

Pangakis, Wolken e Fasching mostram que desempenho de anotação por LLM varia com tarefa e dados, exigindo validação específica com rótulos humanos. [Artigo](https://arxiv.org/abs/2306.00176). Inferência que integra previsões e uma amostra rotulada de referência é uma possibilidade metodológica, sujeita às hipóteses de desenho e estimação; não emerge automaticamente ao executar Gemini. [Angelopoulos et al.](https://arxiv.org/abs/2301.09633).

## Validação e decisão de parada

Concluída a pesquisa documental, a análise de sensibilidade local e a conferência independente do Brasil em 2019. Os resultados são descritivos e provisórios; não validam as importações históricas. O script não chama rede, banco ou Gemini e não seleciona um novo corpus de produção.

Próxima decisão recomendada: fixar o objetivo principal, a menor diferença temática de interesse e a tolerância à parcela não classificada; só depois congelar cobertura ou desenho probabilístico, universo elegível e orçamento real. Preservar as especificações antigas como histórico até que uma nova versão seja aprovada.

Fontes primárias adicionais e justificativas: `research/annual_selection_methodological_sources_20261030.md`.
