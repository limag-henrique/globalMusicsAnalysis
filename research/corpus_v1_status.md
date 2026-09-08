# Corpus científico canônico — status do Corpus v1

Atualizado em 2026-09-07.

## Entregue

- MGD normalizado: **21.257.472 observações**, 68 mercados, Spotify Top 200, de 2017-01-01 a 2022-03-13.
- Elegibilidade: **55 de 68 células** aprovadas com cobertura mínima de 95%, pelo menos 3 anos e profundidade mediana mínima de 100.
- Resolução de tracks: **126.213 tracks canônicas** no `track_master`.
- Turnover por mercado/período: **114.828 linhas**.
- Gênero derivado do catálogo de artistas: **85.144 claims**; diversidade por mercado/ano: **384 linhas**.
- Kaggle Spotify Charts importado para validação: **26.173.514 observações**, 70 regiões, 2017-01-01 a 2021-12-31.
- Sobreposição MGD × Kaggle: **19.942.141 equivalências exatas por ID Spotify** e **19.867.209 por título/artista/data/rank**. As fontes permanecem preservadas separadamente; a reconciliação usa precedência de fonte.
- Pro-Música Brasil: inventário descoberto com 6 itens e captura pública atual de 50 linhas.
- Apple Music removido da camada ativa de adapters, testes, fixtures, enums e referências operacionais.

## Artefatos

- [Manifesto imutável do congelamento de fonte](../data/derived/corpus_v1_source_manifest.json)
- [Cobertura e elegibilidade](../data/derived/mgd_coverage.parquet)
- [Track master](../data/derived/track_master.parquet)
- [Turnover](../data/derived/turnover_by_market_period.parquet)
- [Claims de gênero](../data/derived/genre_claims.parquet)
- [Diversidade de gênero](../data/derived/genre_diversity_by_market_period.parquet)
- [Relatório de sobreposição MGD/Kaggle](mgd_kaggle_overlap_report.md)

O manifesto registra hashes SHA-256, contagens, intervalo temporal, regras e os 55 mercados elegíveis. Ele é um congelamento de artefatos de fonte; a associação de memberships no PostgreSQL fica explicitamente marcada como pendente.

## Estado operacional

O `ResearchApplication` agora usa repositórios SQL reais, a ingestão é idempotente por hash da fonte, a reconciliação preserva todas as observações de origem e a CLI expõe cobertura, ingestão, reconciliação, exportação e congelamento.

O carregamento completo no PostgreSQL não foi executado porque não há serviço PostgreSQL local disponível e o Docker Desktop não está com o engine ativo. Foi executado somente um smoke test SQLite de 10.000 linhas; ele não é o Corpus v1 e não deve ser usado para inferência. O congelamento operacional deve ser rodado após subir PostgreSQL:

```text
python -m chart_observatory.cli corpus ingest-mgd --database-url postgresql+psycopg://...
python -m chart_observatory.cli corpus reconcile --database-url postgresql+psycopg://...
python -m chart_observatory.cli corpus freeze --database-url postgresql+psycopg://...
```

## Lacunas deliberadas

- Idioma, letras e anotações semânticas têm schema, validação e persistência prontos, mas não foram preenchidos sem uma fonte licenciada/eticamente autorizada de letras.
- Chartmetric e YouTube permanecem como fontes opcionais: não há credenciais configuradas nesta execução.
- A cadeia Alembic existente contém uma migration PostgreSQL-específica anterior (`0005`), portanto a validação completa não pode ser feita em SQLite; a migration `0010` do corpus está criada e foi validada por lint, testes e inspeção estática.
