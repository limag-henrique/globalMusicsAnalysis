# Coleta gratuita para complemento do artigo em 2026

Data de consulta: 2026-10-21. Escopo: orientação e pesquisa documental; nenhuma nova coleta/importação executada. Não foi validada cobertura histórica completa de 2026 em nenhum provedor.

## Contexto local

O inventário `research/source_inventory.md` registra MGD até 2022-03-13 e Kaggle/Dhruvil até 2021-12-31. Esses conjuntos não fornecem 2026. `research/youtube_collection_report.md` registra uma coleta de vídeos populares em 2026-09-08, distinta de YouTube Music Top Songs. Há importação de arquivos autorizados no CLI e esquema em `config/schemas/manual_generic.yaml`; seus defaults Spotify/DAILY/STREAMS devem ser ajustados para outra fonte.

## Opções e limites

- **Spotify Charts:** consultar a interface oficial e verificar CSV e datas disponíveis com conta humana. Uma [resposta de moderador](https://community.spotify.com/t5/Desktop-Windows/How-to-save-Spotify-charts-as-playlist/td-p/6659610) descreve exportação CSV, mas não constitui contrato atual de histórico ou automação. Não foi confirmado acesso a todas as semanas de 2026. A [Developer Policy](https://developer.spotify.com/policy) restringe análise de conteúdo/serviço e uso em IA; as [User Guidelines](https://www.spotify.com/us/legal/user-guidelines/) restringem scraping. Gratuidade de acesso não demonstra autorização para pesquisa, retenção ou publicação. Streams de charts são filtrados conforme a [metodologia oficial](https://support.spotify.com/us/artists/article/understanding-spotify-charts/).
- **YouTube Music Charts:** a [documentação oficial](https://support.google.com/youtubemusic/answer/9014376?hl=en) descreve Weekly Top Songs, agregando diferentes versões/vídeos da mesma canção. Histórico e exportação de todas as semanas de 2026 precisam de piloto na interface; não foram confirmados. Preferir exportação oficial disponível e verificar condições de reutilização.
- **YouTube Data API:** [videos.list](https://developers.google.com/youtube/data/reference/rest/v3/videos/list) suporta mostPopular, regionCode e videoCategoryId, com custo de uma unidade; a [quota padrão](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits?hl=en) permite coleta pequena sem compra de serviço. Não há filtro histórico nesse método. Popularidade de vídeo não equivale a Top Songs; viewCount acumulado global não mede consumo nacional em 2026. Conferir [políticas de retenção e métricas](https://developers.google.com/youtube/terms/developer-policies) antes de montar série permanente.
- **Apple Marketing Tools RSS:** o [gerador oficial](https://rss.marketingtools.apple.com/) oferece feeds por storefront e formato para retratos correntes. Não foi identificado parâmetro histórico no gerador. Não confundir com API completa ou Apple Music Feed; acesso público não resolve automaticamente licença de análise/republicação.
- **Last.fm:** [geo.getTopTracks](https://www.last.fm/api/show/geo.getTopTracks) fornece músicas populares da última semana por país com chave de API, sem parâmetros históricos de início/fim. A [página da API](https://www.last.fm/api) solicita contato prévio para uso acadêmico. É uma amostra de usuários Last.fm, não consumo nacional total.
- **Paradas nacionais:** consultar arquivos dos próprios publicadores por mercado, por exemplo [Official Charts](https://www.officialcharts.com/charts/singles-chart/) e [Pró-Música Brasil](https://pro-musicabr.org.br/home-2/top-50-streaming/). Verificar disponibilidade de 2026, autorização e periodicidade individualmente. Métricas entre publicadores não são automaticamente comparáveis.

## Recomendação metodológica

Separar duas perguntas: retrato da última semana completa comum entre mercados versus acumulado de 2026. Para o acumulado, exigir observações desde janeiro até a última semana completa publicada na data de corte, com cobertura auditada por mercado. Não chamar a semana atual ou um snapshot de acumulado anual.

Fazer piloto com um mercado e três períodos (janeiro, meio do ano, último completo), depois verificar todos os países efetivamente usados no artigo. Priorizar mesma plataforma, família de chart, profundidade e frequência. Não somar observações diárias e semanais sobrepostas. Ausência de observação não é zero. Soma de métricas dentro de um Top N representa somente consumo observado no recorte do chart.

Para cada registro: fonte, plataforma, mercado, início/fim do período, chart, posição, título, artistas, identificador, tipo/valor da métrica, URL e instante de coleta. Preservar arquivo bruto e hash quando autorizado. Classificação de letras exige dados e permissões próprios; coletar rankings não fornece letras nem áudio.

Ferramentas locais sem cobrança de serviço: httpx/requests para endpoints autorizados, BeautifulSoup/pandas.read_html para tabelas HTML e Playwright para páginas dinâmicas quando permitido. Não foram instaladas nem executadas nesta pesquisa. Validar primeiro disponibilidade, significado e condições da fonte; ferramenta de scraping não cria histórico inexistente.

## Validação e limite de encerramento

Inventário local confrontado com documentação primária atual de rankings/APIs. Conclusão é viabilidade documental, não teste de downloads ou garantia de cobertura. Sem alterações de código, banco, branch ou commits.
