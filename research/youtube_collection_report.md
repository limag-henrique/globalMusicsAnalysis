# YouTube Data API — coleta corrente

Coleta executada em 2026-09-08 UTC com `videos.list`, `chart=mostPopular`,
`videoCategoryId=10` (Music), `part=snippet,statistics`, uma página por região.

- Regiões solicitadas/coletadas: **111/111**.
- Observações gravadas: **3.037**.
- Vídeos distintos: **1.678**.
- Profundidade observada: ranks 1–30; a API retornou 30 itens por região nesta coleta.
- Falhas: **0**.
- O `video_category_id` efetivamente retornado é preservado por linha, assim como o
  `requested_video_category_id`; a API ocasionalmente devolve vídeos de outras
  categorias no resultado corrente, o que não é silenciosamente corrigido.
- A coleta é marcada como `YOUTUBE_VIDEO_MOST_POPULAR` e
  `NOT_YOUTUBE_MUSIC_TOP_SONGS`. Não foi feita fusão automática com o corpus
  Spotify/MGD nem com tracks canônicas.

Artefatos:

- [Parquet normalizado](../data/normalized/youtube_video_most_popular.parquet)
- [Falhas da coleta](youtube_collection_failures.json)
- [Regiões descobertas](youtube_regions.json)
- JSON bruto por região/página em `data/raw/youtube_data/2026-09-08/`.
