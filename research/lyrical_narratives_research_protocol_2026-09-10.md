# Proposta de pesquisa: narrativas líricas e desempenho nos mercados musicais

Data: 2026-09-10. Estado: proposta metodológica para revisão, sem execução de classificação ou mudança no software. As escalas e os limiares abaixo são propostas a validar, não instrumentos já validados.

## 1. Base existente e alcance

O relatório `corpus_v1_status.md` registra 21.257.472 observações MGD, Spotify Top 200, 2017-01-01 a 2022-03-13, 68 mercados (incluindo GLOBAL), 55 células elegíveis e 126.213 gravações canônicas. Esses números são os documentados, não uma nova auditoria do banco. GLOBAL não deve integrar comparações de países. O catálogo de 47,4 milhões de linhas preserva sobreposições entre provedores; não representa eventos independentes.

O manifesto `data/derived/article/manifest.json` confirma saídas de permanência, turnover e gêneros, mas classificações e vínculos de vídeos estão nulos. As letras e anotações não estão preenchidas segundo o relatório. Claims de gênero são derivados de artistas, não necessariamente da faixa.

Há divergência documental: o status descreve Chartmetric como smoke test de duas observações, enquanto `chartmetric_historical_smoke_2026-09-08.md` relata páginas de 200 linhas e 8.000 linhas em oito mercados. Antes de ampliar o painel, reconciliar artefatos, datas e carga operacional. Nenhum desses registros demonstra backfill longitudinal completo. YouTube mostPopular atual é ranking de vídeos, não histórico YouTube Music Top Songs.

Recomendação: estudo principal Spotify histórico com janela comum escolhida após matriz de cobertura (2019–2021 é candidata, não seleção já verificada). Extensão contemporânea e multiplataforma em painel separado. Não combinar 2026 com 2017–2022 como se fossem a mesma população.

## 2. Perguntas e hipóteses testáveis

1. Como diferem as distribuições de narrativas entre mercados nacionais do Spotify?
2. Hits do mercado brasileiro apresentam maior prevalência/intensidade de dimensões específicas que os mercados comparadores? Não pressupor a resposta nem usar “problemático” como variável única.
3. Quanto das diferenças permanece ao padronizar composição de gêneros, idioma, período e origem do repertório? O residual não identifica cultura nacional.
4. Afeto romântico, sofrimento amoroso e demais dimensões estão associados a streams observados, posição e permanência entre faixas que entraram no chart?
5. A associação conteúdo–desempenho varia com atividade TikTok anterior? Só testar onde houver série temporal e ligação som–gravação adequadas.
6. Quais processos de oferta, exposição e recepção podem explicar centralidade no mainstream? Complementar análise quantitativa com evidências de playlists, promoção, selos, rádio, curadoria e entrevistas.

Separar país do chart (mercado consumidor), origem do artista e idioma. Uma música estrangeira no Top Brasil pertence ao mainstream consumido no Brasil, não automaticamente à produção brasileira. Charts não representam toda a população nem todas as plataformas.

“Vende mais” exige vendas ou receita; streams medem consumo observado. Soma de streams nos dias em Top 200 não equivale ao total de streams da música. Com apenas hits não se estima a probabilidade de uma música qualquer se tornar hit; isso exigiria uma amostra de lançamentos que não entraram no ranking, com exposição e acompanhamento comparáveis.

## 3. Unidade e aquisição das letras

Manter gravação canônica, versão da letra e aparição faixa–mercado–período como entidades distintas. Identificar remix, versão clean/explicit, tradução, idioma e alternância de idiomas. Reutilizar anotação somente quando a versão textual for comprovadamente idêntica, registrando vínculo e hash; não inferir identidade apenas pelo título.

Confirmar fonte das letras, fidelidade à gravação e condições efetivas de armazenamento, envio às APIs e publicação. A aprovação prévia das fontes de charts não resolve, por si, a disponibilidade técnica de letras. Não usar memória do modelo para completar letras ausentes. Instrumental, letra indisponível, texto incompleto e recusa do modelo são estados diferentes de escore zero.

Ler a letra inteira e anotar segmentos numerados no contexto global. Evitar requisição independente por linha: isso perde negação, ironia, interlocutor e desfecho. Conservar repetições e produzir frequência por segmentos únicos e ponderada pelas repetições; um refrão repetido não é várias músicas independentes. Análise textual não cobre interpretação vocal, videoclipe ou sonoridade; esses exigem protocolo adicional.

## 4. Codebook proposto

Não usar uma única escala que misture presença, detalhe, centralidade e aprovação. Para cada tema, registrar separadamente:

- presença: sim/não/indeterminada;
- centralidade: 0 ausente, 1 incidental, 2 recorrente ou relevante, 3 estruturante;
- postura por segmento: descrição, endosso, glorificação, crítica, consequência negativa, ambivalência ou indeterminada (pode haver mais de uma postura na canção);
- evidência: IDs dos segmentos e justificativa semântica curta;
- narrador, alvo e contexto quando identificáveis; nunca atribuir automaticamente a fala à opinião ou conduta biográfica do artista;
- intensidade específica apenas onde exista definição própria.

| Dimensão solicitada | Operacionalização proposta |
|---|---|
| Explicitude sexual | 0 ausente, 1 insinuada, 2 referência direta, 3 descrição gráfica; independente de avaliação moral |
| Objetificação | Redução de pessoa a corpo, instrumento ou recurso, com evidência de supressão de agência; atração ou sexo casual isoladamente não bastam |
| Sexo transacional | Troca explicitada de sexo/intimidade por dinheiro, bens ou benefício; presença e centralidade, sem escala com nível 1 vazio |
| Materialismo | Valorização de posses/consumo como medida de valor pessoal; separar simples menção a dinheiro |
| Drogas e álcool | Separar álcool e outras substâncias, uso, comércio, consequência e postura; não equiparar consumo a glorificação |
| Crime | Ato narrado e contexto; participação do narrador distinta de endosso |
| Violência | Ameaça, ato, consequência e celebração separados; metáforas identificadas |
| Afeto romântico | Cuidado, vínculo, compromisso ou afeição; centralidade 0–3 |
| Sofrimento amoroso | Saudade dolorosa, separação, rejeição ou perda afetiva; pode coexistir com afeto |
| Vida da favela | Renomear para identidade territorial, pertencimento, orgulho comunitário, cotidiano e estigma/resistência; crime em categoria separada; comparar equivalentes locais apenas após revisão cultural |
| Infidelidade | Prática, desejo, acusação, sofrimento e reprovação separados; não inferir traição sem indício de compromisso violado |
| Misoginia | Desprezo, inferiorização, hostilidade ou controle baseado em gênero, distinguindo citação criticada de endosso; registrar alvo |
| Anatomia sexual explícita | Presença de referência anatômica sexual direta e detalhamento; não confundir corpo em geral com anatomia sexual |
| Ato sexual explícito | Referência direta ao ato; detalhamento 0–3 definido por exemplos sintéticos antes do piloto |
| Armas | Menção, posse/uso, ameaça e glorificação; distinguir literal de metáfora |
| Dinheiro | Menção e função: sobrevivência, trabalho, dívida, troca, consumo, status; ostentação separada |
| TikTok viral | Variável externa observada, com data e proveniência; nunca inferida da letra |

Tags adicionais não exclusivas: desejo, reciprocidade, sexo casual, posse relacional, consentimento explícito, inferência de consentimento, ambiguidade e coerção. Ausência de fala sobre consentimento não prova coerção. Papéis representados: parceiro afetivo, sujeito sexual autônomo, objeto sexual, símbolo de status e recurso transacional. Anotar por personagem/segmento; não forçar um papel único para toda a música.

No exemplo fornecido pelo usuário, a morte do irmão por tráfico registra referência ao tráfico e consequência negativa; a afirmação de poder por ser traficante registra autorrepresentação e endosso/glorificação. Não receberiam o mesmo rótulo de postura. “Intensidade extrema” deve ter limiar definido por dimensão antes da análise, e não equivaler a qualquer presença sexual.

## 5. Humanos, LLMs e agregação

Piloto sugerido: 600–1.000 letras únicas, estratificadas por mercado, idioma, gênero, ano e faixa de posição. É uma escala operacional inicial, não cálculo de poder. Casos raros e gírias merecem conjunto de desafio suplementar, separado da amostra de prevalência. Para muitos idiomas, ampliar o piloto ou restringir o primeiro estudo.

Dois anotadores humanos independentes com competência linguística/cultural, terceiro para adjudicação. Reservar desenvolvimento e teste cego antes de ajustar prompts; manter mesma obra, versões relacionadas e, quando viável, artistas no mesmo split. Conservar rótulos humanos originais e decisões de adjudicação. Medir concordância humana antes de exigir desempenho da automação.

Três modelos de fornecedores diferentes recebem o mesmo texto, codebook e exemplos, sem as respostas uns dos outros. Omitir rank, streams, hipóteses sobre Brasil e nacionalidade do artista; o idioma continua visível. Glossários culturais revisados podem ser fornecidos de forma padronizada. Instruir que o conteúdo da letra é dado, não instrução. Solicitar JSON validável, evidências por segmentos e abstenção quando necessário. Não pedir cadeias de pensamento.

Avaliar macro-F1 e precisão/recall por categoria; matriz de confusão, erro ordinal e kappa ponderado para escalas; alpha de Krippendorff com nível de medida adequado para concordância. Desagregar por idioma, gênero, mercado e classe rara; intervalos por reamostragem na unidade musical, não por linha repetida. Confiança autodeclarada não é probabilidade calibrada. Medir custo, recusas, saídas inválidas e instabilidade em repetições de uma subamostra.

Regra candidata de aceitação: alpha humano >= 0,80 e macro-F1 contra referência >= 0,80, com revisão de precisão/recall por categoria e subgrupo antes da produção. São metas de projeto a pactuar, não garantias universais; classes raras precisam amostra suficiente e limiares próprios. Se uma dimensão falhar, revisar definição ou mantê-la manual/exploratória; não ocultar falha por uma média global alta.

Conservar o vetor das três avaliações. Usar maioria em presença, mediana em escores ordinais e adjudicação humana em divergências relevantes (por exemplo, 0/1/3, coerção ou glorificação disputada). Com dois modelos, empates precisam adjudicação. Média de 0–3 pode ser análise de sensibilidade, mas pressupõe distâncias equivalentes entre categorias. Modelos não são três observações sociais independentes. Auditar também amostra aleatória dos consensos. Rodar resultados por modelo, consenso e referência humana para medir robustez.

## 6. Automação e custos

Fluxo: corpus congelado → identidade/versão → letra verificada → segmentação → três classificadores independentes → validação de schema/evidências → divergências e auditoria humana → anotações versionadas → junção aos charts → análise.

Registrar hash da letra, fonte, língua, versão do codebook/prompt/schema, fornecedor, ID exato do modelo, parâmetros, data, resposta original, status de recusa, tokens, custo e revisão humana. Ter cache por hash + modelo + prompt, idempotência, checkpoints, retries limitados e orçamento máximo. Uma atualização de modelo exige teste de ponte antes de misturar saídas.

Para N versões de letras e três modelos: 3N chamadas lógicas, mais testes/retries. As 126.213 gravações documentadas implicariam 378.639 avaliações se cada uma tivesse letra elegível distinta, não milhões de chamadas por aparição em chart. Exemplo puramente orçamentário com 4.000 tokens de entrada e 1.000 de saída por avaliação: cerca de 1,515 bilhão de tokens de entrada e 379 milhões de saída. Medir tokens reais no piloto; somar preços de cada modelo, processamento adicional cobrado, letras e trabalho humano. Não confundir assinatura de chatbot com orçamento de API.

As opções de modelos e capacidades verificadas ficam em `llm_lyrics_model_options_2026-09-10.md`. Escolher pelo teste nas letras do projeto, não por ranking geral de chatbots. Pode-se comparar variantes econômicas no piloto, mas usar três modelos em toda a produção se a tripla anotação de cada música for requisito.

## 7. Plano analítico

- Prevalência: proporção de músicas únicas com cada dimensão por mercado e período; publicar denominadores e faltantes.
- Exposição observada: ponderar pelos streams efetivamente disponíveis nos charts; apresentar separadamente prevalência por faixa, por aparição e por streams. Não somar views, vendas e creations.
- Brasil: comparação bruta e padronizada a uma composição comum de gênero/ano/idioma; usar gêneros por faixa quando disponíveis e análise de sensibilidade aos claims de artista. Exigir suporte comum; não extrapolar comparações sem gêneros comparáveis. Ajustar por gênero muda a pergunta e não revela automaticamente mecanismo causal.
- Romance e sofrimento: quatro grupos (só afeto, só sofrimento, ambos, nenhum), além de modelo com dimensões contínuas/ordinais separadas e interação.
- Desempenho: modelagem adequada à distribuição de streams e posições, com covariáveis prévias de idade da faixa, histórico do artista e período quando disponíveis. Tratar repetição de música/artista/mercado com estrutura multinível ou erros agrupados; não assumir independência de milhões de linhas.
- Permanência: curvas de sobrevivência e modelos de tempo até saída com censura à direita, faixas já presentes no início tratadas por desenho de entrada adequado, lacunas como desconhecidas e regra explícita para reentrada. Distinguir primeira passagem contínua, períodos totais e intervalo primeiro–último registro.
- TikTok: atividade medida antes do resultado (por exemplo, incremento semanal defasado), interação conteúdo × atividade e efeito principal de ambos; controlar desempenho prévio. Associação permanece sujeita a causalidade reversa e promoção não observada.
- Relatar efeitos e intervalos, controlar múltiplas comparações e pré-registrar resultados primários. Propagar incerteza de classificação por análises de sensibilidade, não tratar consenso como verdade infalível.

Dados de letras ausentes podem ser seletivos por idioma, gênero ou popularidade. Publicar cobertura por estrato; ponderação por disponibilidade requer hipótese justificável e não corrige ausência não aleatória automaticamente.

## 8. Gráficos e limites de interpretação

1. Curvas de permanência por mercado e plataforma comparável, com intervalos e número em risco.
2. Séries de turnover Top N, na mesma frequência e profundidade: 1 - |interseção|/N quando os dois charts têm N entradas válidas. Separar deslocamento de rank, entradas e saídas; lacunas não são churn.
3. Áreas de participação de gêneros por período e entropia/número efetivo de gêneros. Fixar regra fracionária para faixas multigênero e mostrar desconhecidos.
4. Matriz de distância Jensen–Shannon entre distribuições e dispersão média de cada mercado em relação aos demais em período comum. Não confundir diversidade interna com distância entre mercados.
5. Forest plots de diferenças de conteúdo brutas e ajustadas, com incerteza.
6. Associação narrativa–desempenho por país; interação TikTok apenas onde houver dados suficientes.

O arquivo legado `market_anxiety` mede turnover. Usar “rotatividade” ou “renovação do repertório” na pesquisa. Não rotular países como mais ansiosos a partir dele. Um estudo distinto de ansiedade precisaria de medidas populacionais externas validadas, alinhamento temporal e desenho que enfrente a falácia ecológica; ainda não permitiria diagnosticar ouvintes individuais.

“Mainstream versus nicho” exige observar também nichos/lançamentos fora do Top 200. Explicações sobre ecossistemas de MCs ou ressurgimento por TikTok são hipóteses, não achados do corpus atual.

## 9. Novos dados prioritários e fontes

Prioridade: letras completas e versões; idiomas e revisão cultural; gêneros por faixa; datas de lançamento e histórico do artista; depois séries de TikTok por som, datas de snapshots, incrementos e resolução de remixes/sounds. Contagem global de creations não mede automaticamente viralidade em cada país, nem seu valor atual reconstrói seu valor antes do hit. Região do criador não equivale à região de quem ouviu. Não somar sounds sem política de deduplicação.

### Opções de aquisição de letras

Para produção em escala, priorizar negociação/licença com **Musixmatch API** (busca por faixa e endpoints de letras; catálogo anunciado como licenciado) ou **LyricFind** (produtos de lyric search/display e licenciamento de dados). As páginas públicas não constituem autorização automática para armazenar um corpus e enviá-lo a LLMs: exigir por contrato análise computacional, processamento por terceiros, retenção, cobertura territorial/linguística e publicação de derivados. Musixmatch mantém documentação e SDK público em [developer.musixmatch.com](https://developer.musixmatch.com/) e orienta consulta de termos; LyricFind descreve seus produtos e licenciamento em [lyricfind.com](https://www.lyricfind.com/).

**Vagalume API** exige token, mas seus termos atuais proíbem copiar/gravar o conteúdo, coletar uma base de dados e transferir conteúdo a terceiros; portanto, não é fonte de produção para este estudo sem autorização escrita específica ([documentação](https://api.vagalume.com.br/docs/), [termos](https://www.vagalume.com.br/terms/)). **LRCLIB** e **Lyrics.ovh** oferecem endpoints comunitários/públicos para consulta, mas não foram tratados como fonte licenciada de corpus neste protocolo; só usar para protótipo ou cobertura após verificar direitos, cobertura, estabilidade e permissão de envio às LLMs. **Genius API** é adequada para busca/metadados; bibliotecas que retornam a letra normalmente raspam a página HTML e não substituem uma licença de letras. Spotify Web API não fornece endpoint de letras e sua política restringe ingestão de Spotify Content em modelos de IA.

Antes de contratar, enviar uma amostra de pelo menos 100 ISRCs (ou 10% do catálogo, se maior), estratificada por idioma, mercado e versão, e medir cobertura, correspondência de versão, latência, limites, custo e direitos. Nenhum fornecedor deve ser presumido como capaz de cobrir as 126.213 gravações.

A [TikTok Research API](https://developers.tiktok.com/docs/en/research-api-specs-query-videos) documenta `music_id`, `create_time` e `region_code` em consultas de vídeos. Isso não estabelece um total histórico completo de creations por música–país; acesso, cobertura, paginação e significado territorial precisam ser verificados na fonte selecionada.

O [estudo de comunicação sexual](https://pubmed.ncbi.nlm.nih.gov/37676780/), publicado online em 2023, estudou 584 músicas (197 pop, 193 hip-hop, 194 country), de 2016–2019. É referência para distinguir demandas, preferências, sugestões, pedidos e consentimento inferido; não demonstra diferenças Brasil–EUA. Ler o instrumento completo antes de adaptar categorias.

[Primack et al.](https://pubmed.ncbi.nlm.nih.gov/18828414/) distinguem referências sexuais degradantes e não degradantes, apoiando a separação conceitual entre sexualidade e degradação. [Cui et al.](https://aclanthology.org/2025.ommm-1.1/) discutem vieses de instrução, anotador e contexto cultural em anotação multilíngue; a diversidade de fornecedores não elimina essas fontes de erro.

## 10. Sequência de preparação

1. Fixar perguntas primárias, definição de sucesso e população; selecionar janela/mercados mediante cobertura.
2. Completar codebook com exemplos sintéticos positivos, negativos e ambíguos, revisados por idioma; pré-registrar hipóteses e plano.
3. Resolver aquisição e ligação de letras e preparar amostra humana; manter teste separado.
4. Executar piloto dos três modelos e humanos; selecionar versões e medir orçamento real.
5. Congelar protocolo e automatizar com auditoria de consensos/divergências.
6. Produzir análise principal do Spotify e só então extensões de plataformas/TikTok conforme cobertura.

Não foi executada coleta paga, classificação ou alteração de código nesta preparação.
