# Fontes oficiais para os cruzamentos do artigo

Verificação: 11/10/2026. Pesquisa em documentação primária e downloads oficiais. O protocolo local usa MGD/Spotify 2017–13/03/2022; a configuração genérica 2021+ não define a janela efetiva deste artigo. Mercados devem ser descobertos no CSV anual, excluindo GLOBAL/HK/PR segundo a especificação contextual. Um ano de survey ou edição de índice não deve ser convertido silenciosamente em série anual.

## Downloads obtidos

| Fonte | Endpoint oficial executado | Arquivo local | Contrato |
|---|---|---|---|
| SIGI 2019, índice e dimensões | `https://sdmx.oecd.org/archive/rest/v1/data/OECD,DF_SIGI2019,/all?format=csvfile` | `data/raw/country_context/source-discovery/oecd_sigi2019_index.csv` | CSV real; LOCATION ISO3; TIME_PERIOD=2019; VAR=SIGI_2 (índice), DF__2 (família), RPI__2 (integridade física), RAPFR__2 (recursos), RCL__2 (liberdades). Usar REGION=ALL para evitar duplicação de grupos. |
| GID-DB 2019, componentes | `https://sdmx.oecd.org/archive/rest/v1/data/OECD,DF_GIDDB2019,/all?format=csvfile` | `data/raw/country_context/source-discovery/oecd_sigi2019.csv` | Componentes de leis, práticas e atitudes; não confundir com SIGI global. |
| UNODC homicídios | `https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/data_cts_intentional_homicide.xlsx` | `data/raw/country_context/source-discovery/unodc_homicide_2026-07.xlsx` | XLSX validado por openpyxl; 7.762.260 bytes; duas planilhas; cabeçalho na linha 3. |

O [portal SIGI](https://www.oecd.org/en/about/programmes/social-institutions-and-gender-index-sigi.html) distingue discriminação institucional de resultados de desigualdade. O [arquivo original GIDDB2019](https://stats.oecd.org/Index.aspx?DataSetCode=GIDDB2019) redireciona à coleção de arquivo `DF_GIDDB2019`; a lista oficial de [dataflows arquivados](https://sdmx.oecd.org/archive/rest/v1/dataflow/OECD/all/latest) confirma também `DF_SIGI2019`. O [guia OECD API](https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html) explica SDMX e limites de uso.

O importador filtra `REGION=ALL`, `INCOME=AIC` e `VAR=SIGI_2`: o mesmo país também aparece em grupos de renda, portanto `REGION=ALL` isoladamente não elimina duplicatas. SIGI é edição periódica: importar 2019 apenas para referência 2019, com `not_survey_year` nos outros anos; não interpolar ou chamar 2023 de valor de 2021. Um alinhamento transversal mais amplo requer decisão metodológica explícita. A edição de 2023 fica fora da janela principal.

O arquivo UNODC foi descoberto no [relatório oficial de vítimas](https://data.unodc.org/datareport/hom-victim). Campos: `Iso3_code, Country, Region, Subregion, Indicator, Dimension, Category, Sex, Age, Year, Unit of measurement, VALUE, Source`. Selecionar **vítimas**, pois o arquivo também inclui suspeitos, presos e condenados. Preservar contagem e taxa como unidades distintas. Homicídio feminino não equivale automaticamente a feminicídio; mortes por parceiro/familiar são uma operacionalização específica, não todas as mortes motivadas por gênero. O [instrumento UN-CTS](https://www.unodc.org/documents/data-and-analysis/statistics/crime/global_femicide_meeting_2025/session_8/Session_8_UNODC_UN-CTS.pdf) documenta esses desdobramentos. A planilha foi exportada integralmente para `unodc_homicide_2026-07.csv` com schema e hashes em `unodc_homicide_2026-07.provenance.json`; a coleta validada tem sidecar `.xlsx.provenance.json`.

## PNUD: GII

O [centro oficial de downloads](https://hdr.undp.org/data-center/documentation-and-downloads) expõe a série de índices e componentes 1990–2023, suficiente para selecionar 2017–2022:

- CSV: `https://hdr.undp.org/sites/default/files/2025_HDR/HDR25_Composite_indices_complete_time_series.csv`.
- Metadados: `https://hdr.undp.org/sites/default/files/2025_HDR/HDR25_Composite_indices_metadata.xlsx`.
- Tabela corrente GII: `https://hdr.undp.org/sites/default/files/2025_HDR/HDR25_Statistical_Annex_GII_Table.xlsx`.

O mesmo portal anuncia [API 2.0](https://hdrdata.org) com inscrição/chave. Para esta importação, o CSV público elimina essa dependência. GII cobre saúde reprodutiva, participação/poder e mercado de trabalho: é um índice agregado, não medida direta de misoginia ou violência.

## WVS/EVS: permissividade sexual

O [arquivo conjunto oficial EVS/WVS v5](https://www.worldvaluessurvey.org/WVSEVSjoint2017.jsp) cobre 2017–2022, 92 países/territórios e inclui CSV, SPSS, Stata e R. O [arquivo WVS7](https://www.worldvaluessurvey.org/WVSDocumentationWV7.jsp) cobre 2017–2022; combinar EVS é necessário para ampliar países europeus. O [questionário oficial](https://www.worldvaluessurvey.org/docs/EVS_WVS_Joint_v1_0_0_bq_WVS7.pdf) contém justificação de prostituição (Q183), homossexualidade (Q182) e sexo antes do casamento (Q186), em escala 1–10. São construtos diferentes; não impor soma unidimensional sem validação.

O HTML da página conjunta aponta CSV ao `DOID=12158`, função `SetDocDownload`, POST `AJDownload.jsp`. Nesta verificação, GET e POST desse endereço responderam apenas um byte de espaço. Portanto **nenhum microdado WVS foi obtido aqui**. Não tratar página de download como dados importados. Alternativa primária: [GESIS ZA7505](https://search.gesis.org/research_data/ZA7505), DOI `10.14281/18241.26` (WVSA) / `10.4232/1.14320` (GESIS). O codebook deve definir variável harmonizada, peso e ano de campo antes de agregação. WVS não é painel anual: preservar ano de entrevista, wave, provedor EVS/WVS, N válido, peso, estimativa e distância temporal ao chart. Excluir códigos de não resposta sem convertê-los em baixa permissividade.

## OONI: bloqueio de sites adultos

O [guia oficial](https://docs.ooni.org/data) oferece API aberta para estatísticas/metadados e S3 público para volume. A [especificação Swagger real](https://api.ooni.io/apispec_1.json) contém `/api/v1/aggregation`, `/api/v1/measurements`, `/api/v1/measurement/{measurement_uid}`. `aggregation` aceita `category_code`, `probe_cc`, `since`, `until`, `test_name`, `time_grain`, `axis_x`, `axis_y`, `format`. O codebook da categoria precisa ser validado; não supor lista universal de sites adultos.

O importador principal executou agregações anuais por países e três domínios explícitos (`pornhub.com,xvideos.com,xnxx.com`), com `axis_x=probe_cc`, `axis_y=domain`, `since=YYYY-01-01` e `until` exclusivo. Exemplo: `https://api.ooni.io/api/v1/aggregation?probe_cc=BR,US&test_name=web_connectivity&domain=pornhub.com,xvideos.com,xnxx.com&since=2017-01-01&until=2018-01-01&axis_x=probe_cc&axis_y=domain`. Isso mede a lista selecionada, não a categoria inteira. O backend atual rejeitou `time_grain=year` apesar de a documentação genérica mencionar granularidade: não usar esse parâmetro para este caminho.

S3 público: `s3://ooni-data-eu-fra/jsonl/webconnectivity/<CC>/<YYYYMMDD>/00/` para datas antigas; `s3://ooni-data-eu-fra/raw/<YYYYMMDD>/<hour>/<CC>/webconnectivity/` desde 20/10/2020. Sem assinatura AWS. API não é indicada para downloads volumosos; é limitada. Preservar cobertura por ASN, domínio, dia e voluntários; falta de medição não é ausência de bloqueio. A [documentação de interpretação](https://ooni.org/support/interpreting-ooni-data/) distingue confirmação de bloqueio e anomalias com falsos positivos.

## Pornografia: Radar/Similarweb

[Cloudflare DNS](https://developers.cloudflare.com/radar/investigate/dns/) mede consultas ao resolvedor 1.1.1.1. Endpoint `GET https://api.cloudflare.com/client/v4/radar/dns/top/locations`; domínio só admite filtro temporal, janela máxima 31 dias, conforme [contrato oficial](https://developers.cloudflare.com/api/resources/radar/subresources/dns/subresources/top/methods/locations/). Exige token. Participação geográfica de consultas de um domínio não é proporção de pessoas que consomem pornografia, nem visita, nem categoria pornográfica nacional. Não permite somar percentuais de domínios como total. Disponibilidade 2017–2022 precisa ser comprovada antes de importar; coletas recentes ficam separadas.

[Similarweb Geography](https://developers.similarweb.com/reference/geography) oferece `https://api.similarweb.com/v4/website/{domain_name}/geo/traffic-by-country`; [documentação atual v5](https://docs.similarweb.com/api-v5/api-reference/website-analysis-api/website-performance/traffic-geography) oferece share/visits por país. Acesso/chave e histórico dependem do produto contratado. Não há acesso pago demonstrado nesta sessão; não prometer importação. Não substituir consumo populacional por tráfego estimado em seleção de domínios sem denominador.

## TikTok: viralização e permanência

Os [critérios oficiais](https://developers.tiktok.com/products/research-api/) continuam limitando a rota brasileira a instituições acadêmicas/sem fins lucrativos que estudam segurança de jovens on-line. Este tema, isoladamente, não demonstra elegibilidade. Uma conta de desenvolvedor não concede acesso; exige proposta, revisão ética e aprovação do projeto. As [FAQ oficiais](https://developers.tiktok.com/docs/en/research-api-faq?enter_method=left_navigation) explicam que estatísticas consultadas podem atualizar com atraso de até dez dias. Contagens observadas hoje não são histórico diário de viralização em 2017–2022. A análise requer eventos com data anterior ao pico do chart, vínculo `music_id`–gravação validado, versões/remixes e censura temporal. Permanência do observatório pode ser calculada sem TikTok, mas não chamada de efeito de viralização.

## Junção e inferência

A [metodologia UNODC da edição importada](https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/metadata_intentional_homicide.pdf), obtida e lida localmente, define taxas femininas sobre população feminina e taxa total sobre população total. O importador preserva o rótulo original `Rate per 100,000 population`, mas exporta unidades explícitas `per_100000_female_population` ou `per_100000_total_population`, com campo de denominador. Não comparar taxas como se o denominador fosse idêntico.

Associar indicador ao país consumidor do ranking, não nacionalidade do artista. Registrar `indicator_year`, `chart_year`, `alignment_rule`, edição, origem e ausência. Analisar prevalência entre faixas anotadas com denominador, controle de gênero/idioma e precisão da classificação. Indicadores nacionais sustentam associação ecológica; não identificam comportamento individual nem causalidade. 2022 musical termina em março: indicadores anuais de 2022 cobrem meses posteriores e precisam ser marcados como contexto anual, não exposição prévia.
