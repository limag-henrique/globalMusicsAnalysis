# TopHit Russia Top Radio Hits Annual Chart 2025: source review

Audit date: 2026-11-17. This review covers a separate national radio chart provider series.

## Archived source and payload

The [first-party TopHit chart route](https://tophit.com/chart/top/radio/hits/ru/annual/2025) identifies the chart as **Top Radio Hits Russia Annual Chart**. The retained [Wayback capture](https://web.archive.org/web/20260106114803id_/https://tophit.com/chart/top/radio/hits/ru/annual/2025), timestamped 2026-01-06 11:48:03 UTC, is cataloged as HTTP 200; the official live route returned HTTP 403 at capture and again during this audit. These statuses and the capture metadata are recorded in the packet [manifest](../data/derived/annual_revision/provider_series/tophit-russia-top-radio-hits-annual-2025/manifest.json). The saved [HTML payload](../data/raw/national_charts/tophit_ru_annual_2025/tophit-top-radio-hits-russia-annual-2025-archive-20260106.html) has SHA-256 `038b8f0fc1ef21c746ca1134c9928ef83928767aca953fd8a5287808a1978de3`.

The decoded page payload selects variant `top`, category `radio`, type `hits`, region `ru`, annual period starting 2025, with row dates 2025-01-01 through 2025-12-31. It declares depth 200 and contains 200 entries at contiguous positions 1–200; each source row reports `top=200` and an `airs` metric (airplay count). The [ranking packet](../data/derived/annual_revision/provider_series/tophit-russia-top-radio-hits-annual-2025/rankings.jsonl) preserves those published positions and the source `airs` values; its SHA-256 is `8a0157e6cfc921f1997519e3dbd42f8bb04ba85da79e1795899baf8c494e6ed4`. All 200 packet rows match the archived payload.

## Publisher country qualification and catalog treatment

Ukraine (`UA`) is a defensible **inference**, not a direct legal attribution from the chart page: the registry profile for TOV “ТОПХІТ” / “TOPHIT” LLC (EDRPOU 42089400) lists a Kyiv registration and Igor Kraev as director, while [RMA identifies Kraev as founder and head of Tophit.ru](https://www.rma.ru/speakers/ikraev/). The matching name and leadership link support the inference, but the chart page itself does not name that legal entity. Keep publisher country `UA` qualified as inferred; keep chart market `RU` distinct.

Catalog this as `TOPHIT_TOP_RADIO_HITS_RU_2025`, a separate TopHit provider series. It is not part of, and must not be merged into, the 150,000-position Spotify/YouTube core selection. Sources: [TopHit chart](https://tophit.com/chart/top/radio/hits/ru/annual/2025), [archived capture](https://web.archive.org/web/20260106114803id_/https://tophit.com/chart/top/radio/hits/ru/annual/2025), [TOV TOPHIT registry profile](https://opendatabot.ua/c/42089400), and [RMA's Igor Kraev profile](https://www.rma.ru/speakers/ikraev/).
