# Apple Music national Top Songs of 2024: additional markets

Research note: 2026-11-17 UTC. This capture adds the 2024 Apple Music annual playlist pages for the markets represented in the official 2025 national collection where a 2024 packet did not already exist. It preserves Apple Music as the provider and the playlist's named country as the chart market.

## Findings

- Apple Music first-party pages were captured for 36 of the 37 requested markets. Each playlist page was fetched through its chart-market storefront route; all 36 retrieved routes match the chart-market code, so no storefront fallback was used.
- The 36 packets contain 3,598 published positions. Thirty-four pages expose positions 1–100; Apple’s China and Netherlands storefront pages expose positions 1–99, which are retained as published.
- Apple’s Egypt page repeats the same recording at positions 18 and 29: TUL8TE’s “حبيبي ليه,” with the same native song ID (`1759421981`), track URL, title, album, artist credit, and duration in both rows. The source page and JSON-LD show a duplicate playlist entry, not a storefront ID mismatch; both published positions are retained and documented in the Egypt manifest.
- Apple publishes no numeric play counts on these playlist rows, so scores are null. Five pages state the exact end-of-year window, 2023-11-01 through 2024-10-31; all other `period_start` and `period_end` fields remain null because their pages do not state exact dates.
- Each packet retains the original Apple page HTML, ordered rows, native song IDs and URLs, source and ranking SHA-256 hashes, byte counts, and retrieval timestamps in `data/derived/annual_revision/provider_series/apple-music-{market-code}-2024-annual/`.
- Packet metadata keeps `provider_code` as `APPLE_MUSIC`, `provider_name` as Apple Music, `publisher_country_code` as `US`, and the explicitly named country in `chart_market_code`. These provider-specific rankings have not been imported into the supplemental index or canonical Spotify/YouTube selection.

## Discovery source

- [The Top Songs of 2025 — Apple Music collection](https://music.apple.com/mm/room/6755978957) is the official collection used to define the target market set. Its market-specific playlist titles supply the chart-market mapping; the storefront route is recorded separately.

## 2024 pages and packet coverage

| Market | Code | Apple Music page title | Published positions | Exact period boundaries | Official Apple Music source |
|---|---:|---|---:|---|---|
| United Arab Emirates | `AE` | Top Songs of 2024: United Arab Emirates | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/ae/playlist/top-songs-of-2024-united-arab-emirates/pl.cf9e89d4daf94b8ba1a3f565082122b8) |
| Austria | `AT` | Top-Songs 2024: Österreich | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/at/playlist/top-songs-2024-%C3%B6sterreich/pl.513dac383aa9405ca0d3d5b63fada970) |
| Australia | `AU` | Top Songs of 2024: Australia | 1–100 (100) | 2023-11-01 to 2024-10-31 | [Apple Music page](https://music.apple.com/au/playlist/top-songs-of-2024-australia/pl.7989c3303b7e4b7085a681a6ead22570) |
| Azerbaijan | `AZ` | Top Songs of 2024: Azerbaijan | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/az/playlist/top-songs-of-2024-azerbaijan/pl.a1cb834db19c4de593928b3f1f204994) |
| Belgium | `BE` | Top Songs of 2024: Belgium | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/be/playlist/top-songs-of-2024-belgium/pl.e99d3b77dece4316b1034125e8b2f8d8) |
| Brazil | `BR` | Top músicas 2024: Brasil | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/br/playlist/top-m%C3%BAsicas-2024-brasil/pl.66892fa7cb924c939dbd33a811fa4c6a) |
| Canada | `CA` | Top Songs of 2024: Canada | 1–100 (100) | 2023-11-01 to 2024-10-31 | [Apple Music page](https://music.apple.com/ca/playlist/top-songs-of-2024-canada/pl.f5fd0c0171e345a9a2e3c2e0c53ebf5c) |
| Switzerland | `CH` | Top-Songs 2024: Schweiz | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/ch/playlist/top-songs-2024-schweiz/pl.f4773db98d3c422eafc853249b664387) |
| Chile | `CL` | Top canciones de 2024: Chile | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/cl/playlist/top-canciones-de-2024-chile/pl.e49b8af85b1d4a24a191bf51c6fdaf8a) |
| China | `CN` | 2024 年度最热歌曲：中国大陆 | 1–99 (99) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/cn/playlist/2024-%E5%B9%B4%E5%BA%A6%E6%9C%80%E7%83%AD%E6%AD%8C%E6%9B%B2-%E4%B8%AD%E5%9B%BD%E5%A4%A7%E9%99%86/pl.96eb3d9582634e47a02dc0a903b6d937) |
| Colombia | `CO` | Top canciones de 2024: Colombia | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/co/playlist/top-canciones-de-2024-colombia/pl.398789406fec46b3a4d0e5969fddb4e3) |
| Germany | `DE` | Top-Songs 2024: Deutschland | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/de/playlist/top-songs-2024-deutschland/pl.0736cef1ff314158b0d9d5d9dd77d054) |
| Denmark | `DK` | Top Songs of 2024: Denmark | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/dk/playlist/top-songs-of-2024-denmark/pl.6e7609b210be460db7475e24747edaf1) |
| Egypt | `EG` | Top Songs of 2024: Egypt | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/eg/playlist/top-songs-of-2024-egypt/pl.52e489ef4c0e476c9665d0ddd31097d1) |
| Spain | `ES` | Top canciones de 2024: España | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/es/playlist/top-canciones-de-2024-espa%C3%B1a/pl.577c4e0b619c4d4689422407326860de) |
| Finland | `FI` | Top Songs of 2024: Finland | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/fi/playlist/top-songs-of-2024-finland/pl.439ba9ff47004f2683d402252f393f51) |
| France | `FR` | Les meilleurs titres de 2024 : France | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/fr/playlist/les-meilleurs-titres-de-2024-france/pl.de4da15a99a245e8953cb273024f6f0e) |
| UK | `GB` | Top Songs of 2024: United Kingdom | 1–100 (100) | 2023-11-01 to 2024-10-31 | [Apple Music page](https://music.apple.com/gb/playlist/top-songs-of-2024-united-kingdom/pl.ed551c7b03fa4571bb3eec82732b8f0b) |
| Ireland | `IE` | Top Songs of 2024: Ireland | 1–100 (100) | 2023-11-01 to 2024-10-31 | [Apple Music page](https://music.apple.com/ie/playlist/top-songs-of-2024-ireland/pl.7bbd228456d54da5afa1179d54b6b73d) |
| Israel | `IL` | Top Songs of 2024: Israel | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/il/playlist/top-songs-of-2024-israel/pl.2c5eb4e44b954eb1a36dde3cbc943457) |
| Italy | `IT` | Top brani del 2024: Italia | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/it/playlist/top-brani-del-2024-italia/pl.6c18fe0adff84c57a9b02d545b4b7093) |
| Korea | `KR` | 2024년 Top 100: 대한민국 | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/kr/playlist/2024%EB%85%84-top-100-%EB%8C%80%ED%95%9C%EB%AF%BC%EA%B5%AD/pl.c07feea7dcb541fbb135f41f348759a2) |
| Mexico | `MX` | Top canciones de 2024: México | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/mx/playlist/top-canciones-de-2024-m%C3%A9xico/pl.f413f762154a4492914cd7517306a6ae) |
| Netherlands | `NL` | De beste nummers van 2024: Nederland | 1–99 (99) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/nl/playlist/de-beste-nummers-van-2024-nederland/pl.2b4fada8b2584e06946d860551c93599) |
| Norway | `NO` | Top Songs of 2024: Norway | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/no/playlist/top-songs-of-2024-norway/pl.d22deb822ec2457a9db08e5cfaac5854) |
| New Zealand | `NZ` | Top Songs of 2024: Aotearoa New Zealand | 1–100 (100) | 2023-11-01 to 2024-10-31 | [Apple Music page](https://music.apple.com/nz/playlist/top-songs-of-2024-aotearoa-new-zealand/pl.57c67df5c699405eb8922269d9df407e) |
| Portugal | `PT` | Top músicas 2024: Portugal | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/pt/playlist/top-m%C3%BAsicas-2024-portugal/pl.e9a6381da57448a7a0b8d39639181a0e) |
| Saudi Arabia | `SA` | Top Songs of 2024: Saudi Arabia | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/sa/playlist/top-songs-of-2024-saudi-arabia/pl.0d116425239b4cd589f5c951891e8d2d) |
| Sweden | `SE` | De största låtarna 2024: Sverige | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/se/playlist/de-st%C3%B6rsta-l%C3%A5tarna-2024-sverige/pl.f5f3e81ca72f4fdfba3764c08f277f9e) |
| Singapore | `SG` | Top Songs of 2024: Singapore | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/sg/playlist/top-songs-of-2024-singapore/pl.298ce9a2146f4d89840432c14ff1c0b5) |
| Thailand | `TH` | Top Songs of 2024: Thailand | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/th/playlist/top-songs-of-2024-thailand/pl.ef8252c043d84b4d8caed959db89f4cb) |
| Türkiye | `TR` | Top Songs of 2024: Türkiye | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/tr/playlist/top-songs-of-2024-t%C3%BCrkiye/pl.d7f5fecc147b4fe499ded4c3cdde7c3d) |
| Taiwan | `TW` | 2024 百大熱門歌曲：台灣 | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/tw/playlist/2024-%E7%99%BE%E5%A4%A7%E7%86%B1%E9%96%80%E6%AD%8C%E6%9B%B2-%E5%8F%B0%E7%81%A3/pl.189b882612364948b8d0579bea8acbb2) |
| Ukraine | `UA` | Top Songs of 2024: Ukraine | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/ua/playlist/top-songs-of-2024-ukraine/pl.4ff54edf7dbd46849146e5e66affd002) |
| USA | `US` | Top Songs of 2024: USA | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/us/playlist/top-songs-of-2024-usa/pl.610738289a774a439883c659b930dbe6) |
| Vietnam | `VN` | Top Songs of 2024: Vietnam | 1–100 (100) | null (Apple page does not state exact dates) | [Apple Music page](https://music.apple.com/vn/playlist/top-songs-of-2024-vietnam/pl.276441e842d74712a8a3d0c597810b0e) |

## Source gap

- **Poland (`PL`):** no “Top Songs of 2024: Poland” playlist surfaced in the official [Apple Music Poland search for that title](https://music.apple.com/pl/search?term=Top%20Songs%20of%202024%20Poland). The 2025 collection includes Poland, but no 2024 packet was created without a matching 2024 Apple page.

## Integrity checks

All 36 packet manifests were checked against the captured Apple HTML and `rankings.jsonl`: source and ranking hashes matched, every row retained its published position, provider and market fields matched the target, scores were null, and chart-market storefront routes matched. The serialized Apple page order and native song IDs were cross-checked against each page's JSON-LD playlist track array.
