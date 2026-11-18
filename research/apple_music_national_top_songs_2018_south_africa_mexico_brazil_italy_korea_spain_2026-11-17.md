# Apple Music national Top 100 Songs 2018: South Africa, Mexico, Brazil, Italy, Korea, and Spain

Audit date: 2026-11-17.

## Findings

Apple Music has first-party local storefront pages for all six markets. Each playlist title is Top 100 Songs 2018 for the named market. The captured serialized track order and the ordered schema.org MusicPlaylist sequence match track-for-track on titles and local Apple song IDs. None embeds numeric rank labels, so packet positions are 1-based source-order ordinals marked as playlist_order:<n>; they are not numeric labels printed by Apple. Exact chart-window boundaries are unstated and remain null.

| Market | Official Apple Music source | Page count | Page SHA-256 | Packet ranking SHA-256 |
|---|---|---:|---|---|
| South Africa | [Top 100 Songs 2018: South Africa](https://music.apple.com/za/playlist/top-100-songs-2018-south-africa/pl.85df0e50a43343e886df15b376543c2a) | 100 | d967ebd8b608bd14ec0e1081a12532d3379d2220ebeae442ff9143b0c089ac9c | a862e008e5fb87079711ac41bbf2659cfdb90fe513348c087e394b79b716a9fc |
| Mexico | [Top 100 Songs 2018: Mexico](https://music.apple.com/mx/playlist/top-100-songs-2018-mexico/pl.ba6edb5940d04fbdb8a2e6dae239933c?l=en-GB) | 100 | 06a989ca7f4240041613dbb92154e001aaf5b9ae9598826aa75420a14276dbe8 | 629aceb25a5d8c840e620a521f7fdb14bbdbbb0df42e1a4a1c68da8a06d62cf4 |
| Brazil | [Top 100 Songs 2018: Brazil](https://music.apple.com/br/playlist/top-100-songs-2018-brazil/pl.68c7cd1a1b1f457db0af27bf80912124?l=en-GB) | 99 | 12f2932b758780cfc518c5199a3ea85665a039279572f50d08a1263b5d04fa32 | 219898afc949d11f198671f062000965aac565e5b800e5500759c07f3c0da406 |
| Italy | [Top 100 Songs 2018: Italy](https://music.apple.com/it/playlist/top-100-songs-2018-italy/pl.329eb48f62ab4b22aabb3477cef874e7?l=en-GB) | 100 | da1a353f401b71ddedd104c5302f457eee5ab99f12974291b2482f29e46dd98a | eb5fdd84a9799b9bcf948d238720cae8139e6db29838079f2bf86187ef3e5bb1 |
| Korea | [Top 100 Songs 2018: Korea](https://music.apple.com/kr/playlist/top-100-songs-2018-korea/pl.10849cb08a19491cbf8c55f52b4d4254?l=en-GB) | 100 | 40029430f0ede1a88a3336d988c7feab4df0cd487464e2934d828f313b960909 | 930bcee45d121943f633f2de8e367f2cf6d0ac87cc1098137acfbe76ad69658e |
| Spain | [Top 100 Songs 2018: Spain](https://music.apple.com/es/playlist/top-100-songs-2018-spain/pl.6e990b92482746fabea87a8ebc8ce740?l=en-GB) | 100 | 5761e0cf23321927f73afc1c5767a5cc222a87d9bfc82f41d0946becb21a926a | e71df5332c29517f7bcdfe8e9b5eff6dd2a6a0892fd5a905631c027d18e8292 |

Apple's pages describe these as the year's most-played songs in the country. The Brazil page is internally inconsistent: its title says “Top 100,” while its page metadata and MusicPlaylist JSON-LD report 99 songs. The packet preserves the 99 recovered ordinal rows, leaves reported_depth null, and records the title/count conflict. No 100th song or position is inferred.

## Evidence and import

Raw source pages, response headers, capture manifests, and extracted order files are under data/raw/national_charts/apple_music_{za,mx,br,it,kr,es}_2018/. Separate provider packets are under data/derived/annual_revision/provider_series/apple-music-{za,mx,br,it,kr,es}-2018-annual/. The source IDs come from each matching storefront.

The six packets add 599 memberships across six independent APPLE_MUSIC series. Five report depth 100; Brazil has 99 observed rows and unknown depth. Supplemental snapshot v35 contains 346 series and 39,298 ranked memberships, 31,063 known reported-depth positions, 27 unknown-depth series, and 19,517 normalized identity keys. Apple Music contributes 298 series and 29,786 memberships. The normalized identity keys are not adjudicated canonical songs.

The exact v34 catalog, report, index, active-index copy, import output, and packet order are preserved at data/runtime/supplemental-provider-snapshot-history-20261117-v34/. All v34 series, memberships, and existing song rows compare equal in v35. The importer verified packet hashes; SQLite quick_check is ok and foreign_key_check returns zero rows.

These Apple Music series remain separate from the Spotify/YouTube core. It remains at 69,032 of 150,000 observed memberships, with 80,968 positions missing.

