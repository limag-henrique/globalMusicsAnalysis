# Apple Music national Top 100 Songs 2018: Canada, UK, New Zealand, France, and Germany

Audit date: 2026-11-17.

## Findings

Apple Music has a first-party storefront playlist titled Top 100 Songs 2018 for each of these five markets. Each page reports 100 songs and describes the playlist as the year's most-played songs in that market. Captured serialized track records and the ordered schema.org MusicPlaylist track sequence agree on all 100 titles and local Apple song IDs for every market. Each market has 100 unique IDs.

None of these pages embeds numeric rank labels. Packet positions 1–100 therefore preserve the publisher's playlist order as ordinals, and each published_rank value is marked playlist_order:<n>. These are not numeric labels printed by Apple. The playlist title and descriptions establish the annual chart context; exact chart-window boundaries are unstated, so period_start and period_end remain null.

| Market | Official Apple Music source | Page wording | Publication date | Page SHA-256 | Packet ranking SHA-256 |
|---|---|---|---|---|---|
| Canada | [Top 100 Songs 2018: Canada](https://music.apple.com/ca/playlist/top-100-songs-2018-canada/pl.5c6c46b7c93141789392073df37d7720) | “The year's most-played songs in Canada.” | 2018-11-29T17:37:53Z | 567befe379c8910e9878622868e14c216d38c9468f72a9104d7882d91ba2175a | 5689288b8307d472c4ee31c8854c32ed55b2edd56806f5148e5222d7350a8466 |
| United Kingdom | [Top 100 Songs 2018: UK](https://music.apple.com/gb/playlist/top-100-songs-2018-uk/pl.e649f413a74d49e98b253ac4bbc2989e) | “The year's most-played songs in the UK.” | 2018-11-29T17:43:56Z | 3928f627804078326331fd4599fe5704a751791a193e418dab18313b261afcca | 7376d087e4f5d5fb25f1c98482224a5e236598c6b9dd130fd253fc1009e93312 |
| New Zealand | [Top 100 Songs 2018: New Zealand](https://music.apple.com/nz/playlist/top-100-songs-2018-new-zealand/pl.8f100aba0023453b85775624df51dfd4) | “The year's most-played songs in New Zealand.” | 2018-11-29T17:57:30Z | a0255fc3d5967ab44790c92fc612a3ce36be0805656a8b7a54b8c74e16c90f9b | 5adc62ec3b7eebff0d30e5122144778c22cb8622a02f95ce6139c31c0c27b7ad |
| France | [Top 100 Songs 2018: France](https://music.apple.com/fr/playlist/top-100-songs-2018-france/pl.c6fa9e049580461882bf29c3e66e0cf7?l=en-GB) | “The year's most-played songs in the country.” | 2018-11-29T17:38:53Z | 51e42b104ff50096bf1559a2a64a150fed25891265dfbf4ed2c796dac754c775 | e92a78c6d7fe5939bc705d30b671be1df1f32a2a012e26e44a2a2126b733c400 |
| Germany | [Top 100 Songs 2018: Germany](https://music.apple.com/de/playlist/top-100-songs-2018-germany/pl.a9e631db8c364b42b36feee55b51a33d?l=en-GB) | “The year's most-played songs in the country.” | 2018-11-29T17:46:45Z | b008952e9332d86927ffc960c5ca1fe90d595b4787a0c3d900320ce237ced7a0 | 28731381546f839c9073bb8446acd1b6eac2af40bed897ad19c660cf8fd7d2f8 |

## Evidence and import

Raw source bodies, response headers, capture manifests, and ordered extractions are stored under data/raw/national_charts/apple_music_{ca,gb,nz,fr,de}_2018/. Provider packets are stored under data/derived/annual_revision/provider_series/apple-music-{ca,gb,nz,fr,de}-2018-annual/. The Apple page was retrieved with the matching storefront and all source track IDs use that storefront.

Each market is a separate APPLE_MUSIC provider series with 100 ordinal positions, an independently stated depth of 100, and unknown exact period boundaries. These memberships remain separate from Spotify/YouTube rankings and do not fill the 150,000-position core.

Supplemental snapshot v34 has 340 provider series and 38,699 ranked memberships; its denominator report totals 30,563 known reported-depth positions with 26 series whose depth remains unknown. It has 19,234 normalized identity keys, which are not adjudicated canonical songs. Apple Music contributes 292 series and 29,187 memberships. The v33 catalog, report, index, active-index copy, import output, and packet order were preserved under data/runtime/supplemental-provider-snapshot-history-20261117-v33/. All v33 series, memberships, and existing song rows compare equal in v34; the five new series add 500 memberships and 182 net normalized identity keys. SQLite quick_check is ok and foreign_key_check returns zero rows.

The Spotify/YouTube core remains at 69,032 of 150,000 observed memberships, with 80,968 positions missing. These Apple Music series are supplemental evidence and do not reduce that gap.

