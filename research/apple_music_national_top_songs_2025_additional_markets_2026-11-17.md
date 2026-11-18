# Apple Music national Top Songs 2025 playlists

Research note: 2026-11-17. This capture adds 37 national Apple Music provider series from the official Apple Music year-end collection. Each series remains independent from Spotify, YouTube, and other providers.

## Findings

The official Apple Music collection links to country-specific playlists titled “Top Songs of 2025: [market]”. We used the country-market storefront page for each playlist and preserved the collection-route page as supporting evidence. This matters because the same Apple playlist can resolve to different Apple song IDs by storefront; the ranked rows use the native IDs and song URLs returned by the chart-market storefront.

All 37 pages publish consecutive rankings from position 1. Thirty-four pages list 100 songs; Saudi Arabia lists 96, the United Arab Emirates 99, and China 99 in its chart-market storefront. The China playlist’s initial collection-route page exposed 100 rows for the same playlist ID, but the China storefront page reports 99; this packet records only the 99 positions available in the China storefront and does not infer a position 100. No score or play-count values are published in the captured ranking rows.

Apple explicitly states the 2025 play window (2024-11-01 through 2025-10-31) on the Australia, Canada, Ireland, New Zealand, United Kingdom, and United States pages. Exact period boundaries remain null in the other 31 packets. Publisher jurisdiction is recorded as Apple Music (`US`); the chart-market code comes from the national playlist title. These are provider-specific Apple Music rankings and are not merged into Spotify/YouTube positions.

The packets contain 3,694 ranked positions. Every manifest, ranking file, source page, reported song count, position sequence, and per-series native-ID uniqueness check passed after the chart-market storefront recapture. They have not yet been imported into the supplemental index or supplemental database; import will wait for the canonical catalog lock to clear.

## Official Apple Music collection

- [The Top Songs of 2025 — Apple Music](https://music.apple.com/mm/room/6755978957) lists country playlists alongside global and regional playlists. Aggregate playlists (such as Global, Middle East, and Sub-Saharan Africa) were excluded from this country-market packet set.

## National playlist pages and packets

| Market | Code | Published positions | Official chart-market storefront page |
|---|---:|---:|---|
| United Arab Emirates | `AE` | 1–99 (99) | [Top Songs of 2025: United Arab Emirates](https://music.apple.com/ae/playlist/top-songs-of-2025-united-arab-emirates/pl.8d081c80f73a4b04b323d9f6daa439a5) |
| Austria | `AT` | 1–100 (100) | [Top Songs of 2025: Austria](https://music.apple.com/at/playlist/top-songs-of-2025-austria/pl.3b9d01f531494bc38b3cf2b014fbe434?l=en-GB) |
| Australia | `AU` | 1–100 (100) | [Top Songs of 2025: Australia](https://music.apple.com/au/playlist/top-songs-of-2025-australia/pl.a9531412b81b495c9d22aca5afd5f997) |
| Azerbaijan | `AZ` | 1–100 (100) | [Top Songs of 2025: Azerbaijan](https://music.apple.com/az/playlist/top-songs-of-2025-azerbaijan/pl.5352ee455e7b4503abf095ae832f5c45) |
| Belgium | `BE` | 1–100 (100) | [Top Songs of 2025: Belgium](https://music.apple.com/be/playlist/top-songs-of-2025-belgium/pl.eda9b856fb93423a872f6eee8cc6b124) |
| Brazil | `BR` | 1–100 (100) | [Top Songs of 2025: Brazil](https://music.apple.com/br/playlist/top-songs-of-2025-brazil/pl.66b878121dd347b18758db0b83c8eaaa?l=en-GB) |
| Canada | `CA` | 1–100 (100) | [Top Songs of 2025: Canada](https://music.apple.com/ca/playlist/top-songs-of-2025-canada/pl.1735c4dcc74b47a481e8b08444ed3328) |
| Switzerland | `CH` | 1–100 (100) | [Top Songs of 2025: Switzerland](https://music.apple.com/ch/playlist/top-songs-of-2025-switzerland/pl.6ff2d4994f364ddd9f368f4da30744a8?l=en-GB) |
| Chile | `CL` | 1–100 (100) | [Top Songs of 2025: Chile](https://music.apple.com/cl/playlist/top-songs-of-2025-chile/pl.a066c7da17d94378af54edc9eaf23128?l=en-GB) |
| China | `CN` | 1–99 (99) | [Top Songs of 2025: China](https://music.apple.com/cn/playlist/top-songs-of-2025-china/pl.134996c706dd4dddaea911a68b10241a?l=en-GB) |
| Colombia | `CO` | 1–100 (100) | [Top Songs of 2025: Colombia](https://music.apple.com/co/playlist/top-songs-of-2025-colombia/pl.599f85abec2f42d19f77f1ade9d35e88?l=en-GB) |
| Germany | `DE` | 1–100 (100) | [Top Songs of 2025: Germany](https://music.apple.com/de/playlist/top-songs-of-2025-germany/pl.388fa1f9624d4ea5a1ead9b0ee31ac5c?l=en-GB) |
| Denmark | `DK` | 1–100 (100) | [Top Songs of 2025: Denmark](https://music.apple.com/dk/playlist/top-songs-of-2025-denmark/pl.e6d6bbc7d13e416f8a5d70a2e2a0ff43) |
| Egypt | `EG` | 1–100 (100) | [Top Songs of 2025: Egypt](https://music.apple.com/eg/playlist/top-songs-of-2025-egypt/pl.f28ff15e5cb749c59741ee50c8340748) |
| Spain | `ES` | 1–100 (100) | [Top Songs of 2025: Spain](https://music.apple.com/es/playlist/top-songs-of-2025-spain/pl.bf5608a75430462cb75d19a9e0a1b84b?l=en-GB) |
| Finland | `FI` | 1–100 (100) | [Top Songs of 2025: Finland](https://music.apple.com/fi/playlist/top-songs-of-2025-finland/pl.03c04fb723464ec5b02eabac331ca873) |
| France | `FR` | 1–100 (100) | [Top Songs of 2025: France](https://music.apple.com/fr/playlist/top-songs-of-2025-france/pl.b11dd1f28e574f4cabab8d8e962df4d5?l=en-GB) |
| United Kingdom | `GB` | 1–100 (100) | [Top Songs of 2025: United Kingdom](https://music.apple.com/gb/playlist/top-songs-of-2025-united-kingdom/pl.fed2a5875e3a4a90996ecb93b8e7ba89) |
| Ireland | `IE` | 1–100 (100) | [Top Songs of 2025: Ireland](https://music.apple.com/ie/playlist/top-songs-of-2025-ireland/pl.6e951bbba57349bcadd38e32e1c6cfb4) |
| Israel | `IL` | 1–100 (100) | [Top Songs of 2025: Israel](https://music.apple.com/il/playlist/top-songs-of-2025-israel/pl.e07ef954ac0b4b3dbe703fa758ddd2d7) |
| Italy | `IT` | 1–100 (100) | [Top Songs of 2025: Italy](https://music.apple.com/it/playlist/top-songs-of-2025-italy/pl.6c669fcf47a34520b9d8aebfd3adabac?l=en-GB) |
| Korea | `KR` | 1–100 (100) | [Top Songs of 2025: Korea](https://music.apple.com/kr/playlist/top-songs-of-2025-korea/pl.a75eab2c0d4c44789b4cacdd33d89a62?l=en-GB) |
| Mexico | `MX` | 1–100 (100) | [Top Songs of 2025: Mexico](https://music.apple.com/mx/playlist/top-songs-of-2025-mexico/pl.ec16c90a60d246aab60343cf3d0ef88d?l=en-GB) |
| Netherlands | `NL` | 1–100 (100) | [Top Songs of 2025: Netherlands](https://music.apple.com/nl/playlist/top-songs-of-2025-netherlands/pl.da62bbc953114e70b7667e1ad9356ba6?l=en-GB) |
| Norway | `NO` | 1–100 (100) | [Top Songs of 2025: Norway](https://music.apple.com/no/playlist/top-songs-of-2025-norway/pl.76718df54068480a98351a559990122e) |
| New Zealand | `NZ` | 1–100 (100) | [Top Songs of 2025: New Zealand](https://music.apple.com/nz/playlist/top-songs-of-2025-new-zealand/pl.de62e3d30a7f483cb1412517da7b6239) |
| Poland | `PL` | 1–100 (100) | [Top Songs of 2025: Poland](https://music.apple.com/pl/playlist/top-songs-of-2025-poland/pl.11a657f875504344a642938eae619b2a) |
| Portugal | `PT` | 1–100 (100) | [Top Songs of 2025: Portugal](https://music.apple.com/pt/playlist/top-songs-of-2025-portugal/pl.5b6674e41d1b44d89e12997d954d3328?l=en-GB) |
| Saudi Arabia | `SA` | 1–96 (96) | [Top Songs of 2025: Saudi Arabia](https://music.apple.com/sa/playlist/top-songs-of-2025-saudi-arabia/pl.d605e05c061948d48a48f7b7994a2c50) |
| Sweden | `SE` | 1–100 (100) | [Top Songs of 2025: Sweden](https://music.apple.com/se/playlist/top-songs-of-2025-sweden/pl.9bf33760c0b94836b5e0d18b4a1fdf8a?l=en-GB) |
| Singapore | `SG` | 1–100 (100) | [Top Songs of 2025: Singapore](https://music.apple.com/sg/playlist/top-songs-of-2025-singapore/pl.24c7ec07d8654e469c75031d886acfff) |
| Thailand | `TH` | 1–100 (100) | [Top Songs of 2025: Thailand](https://music.apple.com/th/playlist/top-songs-of-2025-thailand/pl.e656937ce1a741d8b0f22ab66c738903) |
| Türkiye | `TR` | 1–100 (100) | [Top Songs of 2025: Türkiye](https://music.apple.com/tr/playlist/top-songs-of-2025-t%C3%BCrkiye/pl.53fa26466afe40729207d56a5b1779fb) |
| Taiwan | `TW` | 1–100 (100) | [Top Songs of 2025: Taiwan](https://music.apple.com/tw/playlist/top-songs-of-2025-taiwan/pl.28293286194748d1b5147078e8bd22bd?l=en-GB) |
| Ukraine | `UA` | 1–100 (100) | [Top Songs of 2025: Ukraine](https://music.apple.com/ua/playlist/top-songs-of-2025-ukraine/pl.620784cd97cf45fe8fadf9ba02b56abb) |
| USA | `US` | 1–100 (100) | [Top Songs of 2025: USA](https://music.apple.com/us/playlist/top-songs-of-2025-usa/pl.fc6a6f1547634ed69d95555d22791381) |
| Vietnam | `VN` | 1–100 (100) | [Top Songs of 2025: Vietnam](https://music.apple.com/vn/playlist/top-songs-of-2025-vietnam/pl.1a12c37801e34450ad43e9eb4cf5ce47) |

Packet directories are `data/derived/annual_revision/provider_series/apple-music-{market-code}-2025-annual/`. Each retains `source-page.html` from the annual-collection route, `source-page-chart-market.html` from the chart-market storefront, `rankings-prior-storefront.jsonl` for the initial extracted rows, and the current storefront-specific `rankings.jsonl` used by the manifest.

## Capture and integrity checks

The collection and playlist pages were captured from Apple Music. Playlist order was read from Apple’s serialized page data; native song IDs came from each market’s own Apple storefront route. The displayed page count, position sequence, market code, provider code, and hashes were checked in every packet. The CN discrepancy described above remains explicit in its manifest.
