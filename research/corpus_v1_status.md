# Corpus científico canônico — status do Corpus v1

Atualizado em 2026-09-08.

## Entregue

- MGD normalizado: **21.257.472 observações**, 68 mercados, Spotify Top 200, de 2017-01-01 a 2022-03-13.
- Elegibilidade: **55 de 68 células** aprovadas com cobertura mínima de 95%, pelo menos 3 anos e profundidade mediana mínima de 100.
- Resolução de tracks: **126.213 tracks canônicas** no `track_master`.
- Turnover por mercado/período: **114.828 linhas**.
- Gênero derivado do catálogo de artistas: **85.144 claims**; diversidade por mercado/ano: **384 linhas**.
- Kaggle Spotify Charts importado para validação: **26.173.514 observações**, 70 regiões, 2017-01-01 a 2021-12-31.
- Sobreposição MGD × Kaggle: **19.942.141 equivalências exatas por ID Spotify** e **19.867.209 por título/artista/data/rank**. As fontes permanecem preservadas separadamente; a reconciliação usa precedência de fonte.
- Pro-Música Brasil: inventário descoberto com 6 itens e captura pública atual de 50 linhas.
- YouTube Data API: coleta atual completa para 111 regiões, categoria solicitada Music (`10`), com 3.037 observações de vídeos, 1.678 vídeos distintos e artefatos brutos por região/página. O resultado é um corpus de vídeo/viralidade, não YouTube Music Top Songs.
- Catálogo unificado materializado: **47.434.073 observações preservadas por fonte**, com 47.431.036 linhas de faixa e 3.037 linhas de vídeo. A lista pode ser filtrada por fonte, plataforma, país/mercado, ano, chart, posição e texto pela CLI e pela página de observações.
- Analytics do artigo materializadas a partir do MGD: **382.688 combinações de permanência**, **114.828 comparações de ansiedade/turnover**, **27.704 distribuições de gênero** e **12.157 pares de distância Jensen–Shannon**, com resolução exata por ID Spotify e observações não resolvidas preservadas nos denominadores.
- Apple Music removido da camada ativa de adapters, testes, fixtures, enums e referências operacionais.

## Artefatos

- [Manifesto imutável do congelamento de fonte](../data/derived/corpus_v1_source_manifest.json)
- [Cobertura e elegibilidade](../data/derived/mgd_coverage.parquet)
- [Track master](../data/derived/track_master.parquet)
- [Turnover](../data/derived/turnover_by_market_period.parquet)
- [Claims de gênero](../data/derived/genre_claims.parquet)
- [Diversidade de gênero](../data/derived/genre_diversity_by_market_period.parquet)
- [Relatório de sobreposição MGD/Kaggle](mgd_kaggle_overlap_report.md)
- [Catálogo unificado de fontes](../data/normalized/source_catalog.parquet)
- [Analytics do artigo](../data/derived/article/manifest.json) — manifesto com hashes e os Parquet de permanência, ansiedade, gênero e dispersão.

O manifesto registra hashes SHA-256, contagens, intervalo temporal, regras e os 55 mercados elegíveis. Ele é um congelamento de artefatos de fonte; a associação de memberships no PostgreSQL fica explicitamente marcada como pendente.

## Estado operacional

O `ResearchApplication` agora usa repositórios SQL reais, a ingestão é idempotente por hash da fonte, a reconciliação preserva todas as observações de origem e a CLI expõe cobertura, ingestão, reconciliação, exportação, congelamento e consulta/materialização do catálogo unificado.

O carregamento completo no PostgreSQL não foi executado porque não há serviço PostgreSQL local disponível e o Docker Desktop não está com o engine ativo. Foi executado somente um smoke test SQLite de 10.000 linhas; ele não é o Corpus v1 e não deve ser usado para inferência. O congelamento operacional deve ser rodado após subir PostgreSQL:

```text
python -m chart_observatory.cli corpus ingest-mgd --database-url postgresql+psycopg://...
python -m chart_observatory.cli corpus reconcile --database-url postgresql+psycopg://...
python -m chart_observatory.cli corpus freeze --database-url postgresql+psycopg://...
```

## Lacunas deliberadas

- Idioma, letras e anotações semânticas têm schema, validação e persistência prontos, mas não foram preenchidos sem uma fonte licenciada/eticamente autorizada de letras.
- Chartmetric histórico permanece como lacuna: a capacidade foi descoberta, mas não há `chartmetric_observations.parquet` nem backfill local materializado nesta execução. O catálogo inclui Chartmetric automaticamente assim que esse artefato for fornecido.
- Viralidade e conteúdo só geram saídas quando forem fornecidos vínculos de vídeos e classificações autorizadas; sem esses insumos a aplicação exibe `INSUFFICIENT_DATA`/pendência, sem transformar ausência em zero.
- YouTube histórico não foi inferido a partir do corpus atual: o artefato disponível é somente o snapshot oficial atual de Video Most Popular por região.
- A deduplicação entre fontes continua deliberadamente pendente; linhas equivalentes permanecem separadas e rastreáveis.
- Letras continuam fora do catálogo até a futura implementação licenciada/autorizada; o esquema não fabrica conteúdo ausente.
- A cadeia Alembic existente contém uma migration PostgreSQL-específica anterior (`0005`), portanto a validação completa não pode ser feita em SQLite; a migration `0010` do corpus está criada e foi validada por lint, testes e inspeção estática.
