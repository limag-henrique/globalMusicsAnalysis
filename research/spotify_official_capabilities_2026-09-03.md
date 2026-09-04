# Spotify official capabilities and constraints for cross-cultural chart research

**Audit date:** 2026-09-03  
**Scope:** Spotify Charts, Spotify Web API, and Spotify's governing developer/user policies.  
**Source rule:** Spotify-owned primary sources only. A Spotify Community moderator post is included once as lower-authority, non-contractual evidence and is labelled accordingly.

## Executive finding

The proposed platform is **technically only partly feasible, and not policy-cleared, using Spotify as the data supplier**.

- Spotify Charts officially exposes global/regional, daily/weekly, viral, and city-oriented chart experiences, but the public documentation reviewed does **not** document a public Charts API, an automated export API, a stable CSV schema, complete market coverage, retention guarantees, or a promised Top-200 size.
- The Charts landing page currently requires a Spotify login to access all charts. Automating that login or reverse-engineering the site's private calls is not a documented/permitted collection route.
- The Web API can still resolve/search tracks and retrieve single-track catalog metadata, including ISRC, but Development Mode was materially reduced in February/March 2026. Batch track fetch is removed in Development Mode; popularity and several other fields are removed there.
- Most importantly, the current Developer Policy expressly prohibits analyzing Spotify Content or the Spotify Service for any purpose, including derived listenership metrics, benchmarking, usage statistics, and user profiles. It also prohibits using Spotify Platform/Content to train or ingest into an ML/AI model. The Developer Terms restrict long-term storage, aggregation, databases, redistribution, automated retrieval, and derivative works. There is no documented academic-research exception in these policies.

**Practical conclusion:** do not base the research corpus, longitudinal database, derived metrics, classification pipeline, or publication exports on Spotify Platform/Charts data without written Spotify permission and legal review. Preserve the proposed `ChartSource` and `MetadataProvider` boundaries, but make the operational baseline a researcher-supplied or independently licensed dataset whose terms expressly permit storage, analysis, reproducibility, and publication.

## Evidence labels

- **Documented fact** — stated in current Spotify documentation/policy.
- **Documentation absence** — not found in the official Charts support page, Charts public landing page, or current Web API reference reviewed on the audit date. This is not proof that no internal/private capability exists.
- **Inference / recommendation** — implementation or legal-risk conclusion drawn from the documented facts; it is not a statement by Spotify and is not legal advice.

## 1. Spotify Charts: what is officially documented

### Documented facts

Spotify directs users to [charts.spotify.com](https://charts.spotify.com/home) or Search > Charts in the Spotify app. Its support documentation describes:

- daily and weekly song/album chart eligibility;
- global and regional viral charts (the localized official support page still describes global/regional viral behavior);
- city charts and Local Pulse;
- chart-visible stream numbers, current chart positions, peak positions, and consecutive-day/week streaks;
- daily publication usually before 18:00 EST / 22:00 UTC the next day;
- weekly periods running Friday 00:00 UTC through Thursday 23:59 UTC;
- filtered, chart-eligible stream counts calculated by an undisclosed integrity formula, so chart streams can differ from Spotify for Artists and not every Spotify stream is eligible.

Sources: [Understanding Spotify charts](https://support.spotify.com/us/artists/article/understanding-spotify-charts/), [localized official page retaining the viral-chart section](https://support.spotify.com/sg-en/artists/article/understanding-spotify-charts/).

The [current Charts landing page](https://charts.spotify.com/home) says users must “Log in with Spotify” to access all global charts and go deeper into genre and city charts. Spotify does not state there that Premium is required; only a Spotify login is evidenced.

### CSV/export status and access constraints

- **Documented fact:** the current formal Charts help page documents downloading **Promo Card images**, not downloading chart rows as CSV. Its related “Exporting data” article concerns an artist/team's own Spotify for Artists statistics, not the public chart corpus ([Spotify for Artists export documentation](https://support.spotify.com/us/artists/article/exporting-data/)).
- **Lower-authority historical first-party evidence:** in January 2025, a Spotify Community moderator said a chart page had a button to download chart data as CSV ([moderator response](https://community.spotify.com/t5/Desktop-Windows/How-to-save-Spotify-charts-as-playlist/td-p/6659610)). This is not a current formal API/export contract, does not document automation rights, and does not specify a stable schema or retention guarantee.
- **Documentation absence:** no current formal Spotify source reviewed documents a public Charts API, API credentials, rate limits for Charts, automated/bulk export, unattended collection, official CSV URL contract, CSV schema/versioning, full historical availability, complete market list, or guaranteed chart length (including Top 200).
- **Inference:** a human-authenticated, manually downloaded CSV may exist in the live UI, but this must be verified manually by the account holder and its reuse/license checked before ingestion. It must not be converted into an automated collector by replaying private browser requests.

### Safest supported posture

1. Keep `ChartSource` pluggable.
2. Disable any `SpotifyChartsOfficialSource` network collector until Spotify publishes a documented mechanism or grants written permission.
3. Allow manual import only after recording the export provenance and confirming that the applicable terms permit the intended database, analysis, and publication uses.
4. Treat all fields as source-versioned and optional; capture the file exactly as received, its SHA-256, acquisition time, human operator, account context (without credentials), observed UI route, and parser version.

## 2. Spotify Web API: current resolution/enrichment capability

### Authentication

- All Web API requests require authorization ([API calls](https://developer.spotify.com/documentation/web-api/concepts/api-calls)).
- Server-to-server `Client Credentials` is documented for endpoints that do not access user information ([Client Credentials flow](https://developer.spotify.com/documentation/web-api/tutorials/client-credentials-flow)). It is the least-privilege technical flow for catalog resolution; user OAuth scopes are unnecessary for `GET /search` and `GET /tracks/{id}`.
- Access tokens are Bearer tokens and currently last one hour / 3600 seconds ([Access Token](https://developer.spotify.com/documentation/web-api/concepts/access-token)).
- Creating/using Development Mode apps currently requires the app owner to have Spotify Premium ([Web API overview](https://developer.spotify.com/documentation/web-api), [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)).

### Endpoints useful for track identity

1. `GET /search` can find catalog tracks and supports filters including `track`, `artist`, `album`, `year`, `isrc`, `upc`, and `genre` where applicable ([Search for Item](https://developer.spotify.com/documentation/web-api/reference/search)). Under current Development Mode restrictions its maximum `limit` is 10, default 5.
2. `GET /tracks/{id}` remains available for one track at a time ([Get Track](https://developer.spotify.com/documentation/web-api/reference/get-track)).
3. `GET /tracks?ids=...` / Get Several Tracks is removed for Development Mode; fetch individually. Extended Quota Mode apps were stated to be unaffected by the February 2026 changes ([February 2026 migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)).

### Fields currently usable for a single track

The reference and 2026 changelogs support these fields, subject to nullability, market restrictions, takedowns, and quota mode:

- track: `id`, `uri`, `external_urls.spotify`, `href`, `name`, `type`, `duration_ms`, `explicit`, `disc_number`, `track_number`, `is_local`, `is_playable`, `restrictions`;
- identity: `external_ids.isrc` (plus EAN/UPC where supplied). The March 2026 changelog explicitly reverted the planned removal of `external_ids` ([March 2026 changelog](https://developer.spotify.com/documentation/web-api/references/changes/march-2026));
- artists: array of artist `id`, `name`, `uri`, Spotify URL, and API `href`;
- album: `id`, `name`, `uri`, Spotify URL, API `href`, `album_type`, `total_tracks`, `release_date`, `release_date_precision`, restrictions, album artists, and artwork URLs/dimensions.

Important semantics:

- `explicit=false` means “no **or unknown**”; it is not proof that a track has no explicit lyrics ([Get Track](https://developer.spotify.com/documentation/web-api/reference/get-track)).
- `market` affects availability; a user token's account country overrides the request's market. With neither a market nor user country, content is considered unavailable.
- Release date has an explicit precision (`year`, `month`, or `day`); do not coerce an imprecise date into an invented day.

### Fields/capabilities that must not be relied upon in Development Mode

The February 2026 migration guide says Development Mode removed track `available_markets`, `linked_from`, and `popularity`; album `available_markets`, `label`, and `popularity`; and artist `followers` and `popularity`. `external_ids` was subsequently restored. It also removed batch track fetch, browse categories/new releases, artist top tracks, and available markets endpoints. The generic reference still displays some removed fields as deprecated, so the migration guide/changelogs must control Development Mode expectations.

The Web API does not document regional Top charts, chart ranks, chart streams, prior position/movement, chart longevity, or chart history. It is enrichment/resolution only, not the success-measure source.

The current Web API reference contains no lyrics endpoint. Spotify states that displayed lyrics are licensed/synchronized by Musixmatch (PetitLyrics in Japan), which is evidence that lyrics require another authorized source and rights arrangement ([Managing your lyrics on Spotify](https://support.spotify.com/us/artists/article/managing-your-lyrics-on-spotify/)).

## 3. Rate limits, quotas, and Development Mode constraints

### Documented facts

- API-wide rate limiting uses a rolling 30-second request window. Spotify does not publish the numeric threshold; it varies by Development versus Extended Quota Mode, and individual endpoints can have custom limits ([Rate Limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits)).
- Rate-limit excess returns HTTP 429. The response **normally** includes `Retry-After` in seconds; Spotify recommends waiting that duration.
- Development Mode also has endpoint-bucket quotas, separately enforced from the rolling-window rate limit. Spotify does not publish the bucket groupings or numeric limits and says they may change ([Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)).
- Since July 2026, Development Mode quotas are counted per developer account across its Client IDs. Quota exhaustion returns 429 with JSON `error.reason = "QUOTA_EXCEEDED"`; developers can create up to 25 Client IDs per account ([July 2026 changelog](https://developer.spotify.com/documentation/web-api/references/changes/july-2026), [July announcement](https://developer.spotify.com/blog/2026-07-23-web-api-quota-updates)).
- Development Mode permits at most five authenticated users per app; each must be allowlisted. A non-allowlisted user can log in but API requests receive 403. The owner must maintain Premium.
- Extended Quota Mode removes that user allowlist and raises rate limits, but new applications have been organization-only since 2025 and list demanding eligibility criteria, including a legal entity, launched service, at least 250k MAU, key-market availability, commercial viability, and policy compliance. Approval is not guaranteed.

### Engineering implications (inference)

- Distinguish `429 + QUOTA_EXCEEDED` from rolling-window 429; `Retry-After` backoff cannot create more quota.
- For ordinary 429, obey `Retry-After` first, then apply bounded jittered exponential backoff if absent; cap concurrency globally per developer account.
- Cache only where the policy permits it; rate-limit efficiency does not override content-storage restrictions.
- Log request purpose, endpoint, response status, retry delay, quota reason, and correlation ID, but never tokens/secrets.
- Because Development Mode removed batch track retrieval, a large chart corpus may be operationally slow or quota-infeasible even before the policy prohibition is considered.

## 4. Policy restrictions material to this research design

The governing documents are the [Spotify Developer Policy](https://developer.spotify.com/policy) (effective 2025-05-15), [Spotify Developer Terms](https://developer.spotify.com/terms) (v10, effective 2025-05-15), and the [Spotify Terms of Use](https://www.spotify.com/us/legal/end-user-agreement/) (updated 2025-08-26). This is a risk reading, not legal advice.

### Analysis and derived metrics — critical blocker

- **Documented fact:** Developer Policy III.13 says not to analyze Spotify Content or the Spotify Service “for any purpose,” expressly including new/derived listenership metrics, benchmarking, functionality, usage statistics, user metrics, or user profiles.
- **Inference:** cross-country prevalence/exposure measures, chart longevity, diffusion, overlaps, regressions, and paper tables derived from Spotify-supplied chart/metadata content are within or uncomfortably close to this prohibition. Academic intent is not an exception stated in the policy.

### ML/AI and deterministic classification

- **Documented fact:** Developer Policy III.14 and Developer Terms IV.2.1 prohibit using Spotify Platform or Spotify Content to train an ML/AI model or otherwise ingest Spotify Content into an ML/AI model.
- **Inference:** do not send Spotify-sourced metadata, lyrics, artwork, audio, chart rows, or derived Spotify content to an LLM/embedding/classification service. A deterministic keyword system is not necessarily “ML/AI,” but the broader analysis prohibition still applies. Classification is safer only on independently licensed/researcher-supplied lyrics, with no Spotify Content as model input.

### Storage, databases, caching, and historical reproducibility

- **Documented fact:** Developer Terms IV.3 prohibits storing, aggregating, or creating compilations/databases of Spotify Content except as strictly necessary to operate the SDA; requires reasonable efforts to keep displayed data current and delete older data; and says not to store Spotify Content indefinitely. Local caching is limited to temporary metadata/cover-art caching strictly necessary for SDA performance (plus tightly constrained conditional audio downloads).
- **Documented fact:** “Spotify Content” is defined broadly to include data/material made available through the Spotify Platform, Spotify Service, or by Spotify, including recordings, artwork, musical works, lyrics, metadata, playlists, and user data.
- **Inference:** immutable raw snapshots, permanent Spotify metadata tables, archival chart history, reproducible frozen datasets, and public research packages conflict with the ordinary developer license. Written authorization or a separately licensed dataset is required to reconcile scientific reproducibility with those terms.

### Scraping, private endpoints, and login automation

- **Documented fact:** Developer Terms IV.2.4 prohibits improper automated retrieval/indexing with robots, spiders, site-search/retrieval tools, or other tools, excessive calls, credential collection, and unauthorized purposes; IV.2.1 prohibits reverse engineering and unauthorized derivative works.
- **Documented fact:** ordinary Spotify service access is limited to personal, non-commercial use and the Terms of Use prohibit redistribution/sale/transfer of the service or content.
- **Recommendation:** no Charts scraping, no login automation, no replay of undocumented browser calls, no private endpoints, and no evasion of geography/authentication controls.

### Metadata, artwork, audio, and attribution

- Metadata, cover art, artist images, and preview clips must link back to the applicable Spotify object; Spotify attribution/marks are required when displaying Spotify Content; these assets cannot be offered as a standalone product ([Developer Policy](https://developer.spotify.com/policy), II.4).
- Visual content must remain in original form; the endpoint page says not to crop, overlay, or place logos on artwork ([Get Track](https://developer.spotify.com/documentation/web-api/reference/get-track)).
- Spotify content may not be downloaded or stream-ripped. Preview URLs are deprecated; preview clips, where available, may only promote the underlying content, must link back, cannot be standalone, and have territorial constraints.
- **Recommendation:** omit artwork and audio entirely from research exports and model pipelines. Store Spotify URLs as attribution pointers only if permission allows the underlying metadata use.

### Lyrics and copyright

- Lyrics are included in Spotify's definition of Spotify Content, but the Web API provides no lyrics endpoint. Spotify identifies Musixmatch/PetitLyrics as its licensed lyrics suppliers.
- **Inference:** visible lyrics in the Spotify client are not a granted research corpus license. Obtain lyrics through a provider contract or researcher corpus that expressly permits storage, computational analysis, human annotation, quotations, derived-feature publication, and (if used) model processing. Do not publish or commit full lyrics absent those rights; copyright exceptions are jurisdiction- and use-specific.

### Research/publication and redistribution

- The policies reviewed do not document an academic-use, text-and-data-mining, reproducibility, or publication exception for Web API/Charts content.
- Spotify's privacy policy notes that Spotify itself may disclose pseudonymized user/usage data to academic researchers, but no public research-data application path or license was found; this is not permission for a developer to collect or publish data.
- Developer Terms prohibit selling Spotify Content and restrict third-party transfers; aggregate/anonymous/derivative data cannot be transferred into advertising/monetization systems. The broader analysis and storage prohibitions remain even for noncommercial work.
- **Recommendation:** before collection, request written Spotify authorization specifying chart exports, market/date scope, retention, database creation, derived measures, academic publication, replication materials, collaborator/processors, and deletion obligations. Separately obtain institutional legal/ethics review.

## 5. Capability matrix for the proposed platform

| Need | Official Spotify status on 2026-09-03 | Design decision |
|---|---|---|
| Regional daily/weekly rankings | Human-facing Charts documented; login required for all charts | Manual/licensed import only after permission |
| Public Charts API | Not documented | Do not implement network collector |
| Official chart CSV | Historically reported by Spotify moderator; not in current formal docs; schema/automation rights undocumented | Human verification + license check; importer schema-adaptive |
| Rank/stream/streak/peak | Concepts documented; exact export fields not contracted | Treat fields as optional and preserve raw values |
| Previous rank/movement | No current formal field/schema documentation found | Optional source field, never assumed |
| Spotify ID/URL in chart export | No current formal CSV schema documentation found | Resolve only when provided/permitted; otherwise probabilistic candidate workflow |
| Track search | `GET /search`, Development max 10 results | Candidate generation only; keep scores and human review |
| Single-track metadata | `GET /tracks/{id}` remains | Technically available; policy permission still required |
| Batch metadata | Removed in Development Mode | One-by-one, rate-limited; avoid scale assumptions |
| ISRC | `external_ids.isrc` restored March 2026 | Preferred identity when supplied; preserve provenance |
| Popularity | Removed in Development Mode | Do not model/store as a dependable field |
| Track genre | No track-level genre field documented | Independent `GenreProvider` |
| Lyrics | No Web API lyrics endpoint | Licensed/researcher `LyricsProvider` |
| Artwork/audio | Technically referenced, heavily restricted | Exclude from analysis/storage/export |
| ML/AI over Spotify content | Expressly prohibited | Never ingest Spotify Content into ML/AI |
| Statistical analysis of Spotify content | Expressly prohibited by Developer Policy | Written authorization or non-Spotify licensed source |
| Permanent reproducible Spotify dataset | Conflicts with storage/deletion rules | Separate license/permission required |

## 6. Recommended architecture boundary

Maintain the scientific architecture, but make data rights a first-class gate:

```text
PermittedChartSource
  -> immutable licensed/researcher raw file
  -> provenance + rights manifest
  -> schema-versioned parser
  -> normalized chart snapshot/entries
  -> PermittedMetadataProvider
  -> metrics
  -> LicensedLyricsProvider
  -> deterministic keyword annotations
  -> human validation / adjudication / gold standard
  -> statistics and publication exports
```

Every source/version should carry:

```text
source_id
license_or_permission_reference
permitted_purposes
retention_rule
publication_rule
redistribution_rule
ml_ai_rule
retrieved_at
effective_terms_date
raw_checksum
parser_version
```

The Spotify adapters should default to **disabled** unless a permission record explicitly authorizes the operation. “Technically reachable” must never mean “permitted.”

## 7. Decisions requiring approval before implementation

1. **Data-rights strategy:** obtain written Spotify permission, license chart/metadata data from another supplier, or use a researcher-supplied corpus with documented rights.
2. **Charts ingestion:** authorize only manual imports, or postpone all Spotify Charts ingestion pending formal access.
3. **Metadata strategy:** use Spotify Web API only if written permission covers the research database/analysis; otherwise choose an independently licensed metadata source.
4. **Publication package:** decide whether replication files can contain identifiers/ranks/derived data under the selected license, or only code plus synthetic fixtures and instructions for authorized researchers.
5. **Lyrics:** choose a licensed provider/corpus and its allowed persistence/analysis/publication terms before Milestone 2.
6. **AI boundary:** confirm that no Spotify Content enters any ML/AI system; decide separately whether independently licensed lyrics may be used with ML/AI.

## 8. Minimum acceptance criteria for a legally viable data foundation

- A written rights basis exists for every source and expressly covers collection/import, storage duration, database creation, computation, human annotation, collaboration/processors, statistical publication, and replication.
- No undocumented Spotify endpoints, scraping, login automation, or private-request replay.
- Source and parser versions, checksums, acquisition timestamps, and applicable terms/permission versions are immutable and queryable.
- Spotify-derived content is excluded from ML/AI ingestion and from analysis unless Spotify gives express written permission that resolves the current policy prohibition.
- The platform remains functional with Spotify adapters disabled, using local synthetic fixtures and permitted manual imports.

## Official sources consulted

- [Spotify Charts landing page](https://charts.spotify.com/home)
- [Understanding Spotify charts](https://support.spotify.com/us/artists/article/understanding-spotify-charts/)
- [Spotify Web API overview](https://developer.spotify.com/documentation/web-api)
- [Web API reference index](https://developer.spotify.com/documentation/web-api/reference)
- [Get Track](https://developer.spotify.com/documentation/web-api/reference/get-track)
- [Search for Item](https://developer.spotify.com/documentation/web-api/reference/search)
- [Client Credentials flow](https://developer.spotify.com/documentation/web-api/tutorials/client-credentials-flow)
- [Access Token](https://developer.spotify.com/documentation/web-api/concepts/access-token)
- [Rate Limits](https://developer.spotify.com/documentation/web-api/concepts/rate-limits)
- [Quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes)
- [February 2026 migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
- [March 2026 changelog](https://developer.spotify.com/documentation/web-api/references/changes/march-2026)
- [July 2026 changelog](https://developer.spotify.com/documentation/web-api/references/changes/july-2026)
- [Spotify Developer Policy](https://developer.spotify.com/policy)
- [Spotify Developer Terms](https://developer.spotify.com/terms)
- [Compliance Tips](https://developer.spotify.com/compliance-tips)
- [Spotify Terms of Use](https://www.spotify.com/us/legal/end-user-agreement/)
- [Managing lyrics on Spotify](https://support.spotify.com/us/artists/article/managing-your-lyrics-on-spotify/)

