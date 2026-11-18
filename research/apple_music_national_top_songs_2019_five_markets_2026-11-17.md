# Apple Music national Top Songs of 2019: five additional markets

Date consulted: 2026-11-17 UTC. Direct requests to the market storefronts returned HTTP 200. The pages identify these as Apple Music's 2019 national playlists; their available track rows were read from the page's serialized server data.

## Verified playlists

| Market | Official chart-market page | Apple playlist catalog ID | Ranked positions |
|---|---|---|---:|
| Australia | [Top Songs of 2019: Australia](https://music.apple.com/au/playlist/top-songs-of-2019-australia/pl.6921ccb7385845eaa0f285659b934d87) | `pl.6921ccb7385845eaa0f285659b934d87` | 1–100 |
| Canada | [Top Songs of 2019: Canada](https://music.apple.com/ca/playlist/top-songs-of-2019-canada/pl.0e2a0a89865f4aea9547e3e7fdd0d609) | `pl.0e2a0a89865f4aea9547e3e7fdd0d609` | 1–100 |
| Japan | [2019年トップソング100：日本](https://music.apple.com/jp/playlist/2019%E5%B9%B4%E3%83%88%E3%83%83%E3%83%97%E3%82%BD%E3%83%B3%E3%82%B0100-%E6%97%A5%E6%9C%AC/pl.9734ad973df641fc9fac65448b3c56c6) | `pl.9734ad973df641fc9fac65448b3c56c6` | 1–100 |
| United Kingdom | [Top Songs of 2019: UK](https://music.apple.com/gb/playlist/top-songs-of-2019-uk/pl.aa25b8952926406c90d0a66b05f1952c) | `pl.aa25b8952926406c90d0a66b05f1952c` | 1–99 |
| New Zealand | [Top Songs of 2019: New Zealand](https://music.apple.com/nz/playlist/top-songs-of-2019-new-zealand/pl.0be7025320294bb2b223987eddd2fbeb) | `pl.0be7025320294bb2b223987eddd2fbeb` | 1–100 |

Apple's playlist metadata and serialized rows agree on these counts; `rankingText` is consecutive from 1 through the final position for each page. The UK page explicitly reports 99 songs; Apple does not explain why it has one fewer row. Each playlist page's song links use the matching local storefront path (`/au/song/`, `/ca/song/`, `/jp/song/`, `/gb/song/`, or `/nz/song/`). For a spot check, the first and last local song IDs are: AU `1445949267` / `1326877136`; CA `1458638381` / `1437592171`; JP `1402042897` / `1538114965`; GB `1441539154` / `1440717826`; NZ `1445949267` / `1437955726`.

## Retrieval and limits

The public Apple pages were requested directly from their matching storefronts. Search results can resolve a country-tagged playlist through another storefront (notably New Zealand through `/us` or `/au`), so retain the direct market URL above and the local song IDs. Apple labels the playlists as 2019 but publishes no explicit chart coverage start/end dates on these pages; the page's `datePublished` metadata is a publication timestamp, not a period field. Leave `period_start` and `period_end` unspecified rather than inferring a calendar-year range.

The response-body hashes below were calculated from UTF-8 page content returned by direct HTTP GETs. Each response body is preserved as `source-page-chart-market.html` in its market packet.

| Market | Response bytes | SHA-256 |
|---|---:|---|
| Australia | 697,942 | `f4c72ab16113e31d193570897c8fb9590ff6a2beadb1271a575cd3f224f3d8d1` |
| Canada | 697,445 | `de419be38fa86abfdf4f0f933d133b8444f0679b12b13e3e1c9eb17f1bffdbb4` |
| Japan | 714,656 | `7e997ad1c66ca033d6813ecf2bc5ffbee13c74e80c1ec5dd37f786aaa592d5cd` |
| United Kingdom | 707,639 | `d0379e1a88056454f5cc712022e8bb4925a9073d067ceafd5f9e606b55b4207a` |
| New Zealand | 702,734 | `40b0163c6274152b991c22da575a190110a797b4665f68d6a018fad2ff4129da` |

## Project capture

The five packets are `apple-music-au-2019-annual`, `apple-music-ca-2019-annual`, `apple-music-jp-2019-annual`, `apple-music-gb-2019-annual`, and `apple-music-nz-2019-annual` under [`provider_series`](../data/derived/annual_revision/provider_series/). They preserve 499 ranked positions total; the UK depth is 99 because that is the published count. Each row retains its matching market storefront's song ID. Period start and end remain null. The provider series are separate and do not enter the Spotify/YouTube selection. They are included in the [current provider-series index](../data/derived/annual_revision/provider_series/provider-series-index.json) and supplemental catalog v08.

## Project capture

The five packets are `apple-music-au-2019-annual`, `apple-music-ca-2019-annual`, `apple-music-jp-2019-annual`, `apple-music-gb-2019-annual`, and `apple-music-nz-2019-annual` under [`provider_series`](../data/derived/annual_revision/provider_series/). They retain 499 ranked positions in total; the UK depth is 99 because that is the source's published count. Each row uses the matching market storefront's song ID. Period start and end remain null. The series are provider-tagged separately and are not merged into the Spotify/YouTube selection.
