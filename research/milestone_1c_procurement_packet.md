# Milestone 1C procurement packet

**Status:** DRAFT — not sent  
**Prepared:** 2026-09-04  
**Providers:** Luminate, Soundcharts, Chartmetric  
**Research window:** 2021-01-01 through latest available date  
**Countries:** BR, US, GB, FR, DE, ES, PT, IT, SE

This packet requests the evidence required by Milestone 1C. It does not authorize a
purchase, account creation, authenticated API call, sample ingestion, or production
adapter. Public documentation is useful for triage but cannot replace a coverage
extract, the executed order form, or institutional/legal approval.

## Requested response package

Each provider should return the following as part of, or expressly incorporated into,
the proposed order form:

1. A machine-readable coverage extract using
   `research/milestone_1c_coverage_matrix.csv` as the minimum schema.
2. A representative, non-production sample for every materially different endpoint,
   delivery format, chart family, frequency, and methodology version in scope.
3. The exact data dictionary, schema registry/changelog, methodology, known-gap list,
   backfill/correction policy, and trend-break register.
4. The proposed academic order form and every incorporated policy or upstream term.
5. A price sheet covering initial history, ongoing deltas, API/bulk delivery, overages,
   support, and all requested publication/collaboration/replication rights.
6. Quota, pagination/range limits, delivery cadence, service levels, incident notice,
   and termination/deletion rules.

## Outreach template

**Subject:** Academic historical music-chart dataset — coverage and licensing request

> Hello,
>
> We are evaluating a licensed historical music-chart dataset for non-commercial
> academic research. The required geography is Brazil, United States, United Kingdom,
> France, Germany, Spain, Portugal, Italy, and Sweden. The target window begins on
> 2021-01-01 and continues through the latest available period.
>
> Before selecting a provider, we need a machine-readable coverage extract, data
> dictionary, representative sample, methodology and gap documentation, and a proposed
> order form that expressly addresses the twenty questions below. Please distinguish
> each origin platform, chart family, country, native frequency, methodology version,
> and metric. Please do not describe company age or general market availability as
> evidence of a particular historical chart cell.
>
> The research requires immutable internal snapshots and audit checksums; academic
> analysis and derived metrics; controlled access for named coauthors, supervisors,
> reviewers, institutional infrastructure, and approved cloud processors; publication
> of tables, figures, statistics, track lists and identifiers at agreed thresholds; and
> a workable replication route. We will not assume that dashboard terms grant these
> rights to API or bulk data.
>
> A sample will be used only for schema and coverage evaluation and will not enter the
> research corpus before contracting and institutional approval. Please specify its
> permitted retention and required deletion date.
>
> Could you return the requested package and identify the commercial and legal contacts
> who can bind these answers into the order form?

## Questions that must be answered in the contract

1. Which exact `platform × chart family × country × date` combinations exist from
   2021-01-01 to the present? Supply a coverage matrix and missing-date manifest.
2. What are the first and last dates per cell, and which gaps, backfills, corrections,
   and trend breaks exist?
3. What are the native frequency, timezone, weekly boundary, and normal/maximum delay?
4. What is the real chart depth? Does pagination expose the whole chart or only Top N?
5. Is rank official, provider-reconstructed, or proprietary? Identify methodology and
   version.
6. Which metric accompanies rank? Is it observed, estimated, or modeled, and what does
   `NULL` mean?
7. Are ISRC and recording identifiers included? How are versions, remasters,
   clean/explicit editions, UGC rollups, and multiple ISRCs represented?
8. May raw files and immutable snapshots, checksums, backups, and cold storage be kept
   permanently and after subscription termination?
9. Are academic analysis, derived metrics, regressions, cross-country benchmarking,
   and combination with third-party metadata permitted?
10. May raw and derived data be shared with named coauthors, supervisors, reviewers,
    annotators, institutional repositories, and cloud processors, and in which regions?
11. May papers contain tables, figures, aggregates, small samples, track lists, and
    identifiers? State any aggregation or suppression threshold.
12. What may a replication package contain: ranks by track/date/country, ISRC or other
    IDs, code/manifests only, an enclave, or a replicator license?
13. Which upstream platform terms remain applicable, and what sublicensing rights does
    the provider warrant for analysis and publication?
14. Are refresh/deletion, takedown, audit, or retroactive-removal duties imposed for
    YouTube or other upstream data? Who performs them and how do they affect snapshots?
15. What are the API/bulk quotas, monthly limits, RPM/RPS, overage prices, date-range
    limits, page sizes, and support SLA?
16. Is an initial 2021-present bulk delivery plus deltas available? Specify formats,
    schema registry, changelog, and versioning.
17. How are historical corrections delivered? Can “as originally published” and
    “latest corrected” series both be reconstructed?
18. Does the provider accept institutional DPA/security terms, disclose subprocessors
    and data residency, and provide incident notification?
19. What is the total academic price for the nine countries, full period and required
    depth, including delivery and publication/collaboration/replication rights?
20. On termination, what raw and derived material must be deleted, when, and what may
    remain in papers, backups, audit records, and repositories?

## Provider-specific emphasis

| Provider | Ask first | Do not infer |
|---|---|---|
| Luminate | Cell-level gaps and trend breaks in 2021; Music API vs Data Share; academic publication language | That documented country availability means complete 2021 coverage |
| Soundcharts | Exact chart slugs/dates/depth per platform and country; upstream rights; API versus dump pricing | That public endpoint availability grants research publication or retention |
| Chartmetric | API/Data Share contract, dates endpoint extract, historical null metrics, and backfill limits | That dashboard research language governs bulk/API use |

Official starting points:

- Luminate: [sales](https://luminatedata.com/contact-us-sales/) and Music Data Share/API
  support at `datasupport@luminatedata.com`.
- Soundcharts: [contact form](https://soundcharts.typeform.com/to/IFQ4MvtU) and
  `contact@soundcharts.com`.
- Chartmetric: [Developer API request](https://chartmetric.com/contact-us/developer-api)
  and [Data Share request](https://chartmetric.com/contact-us/data-shares).

The evidence behind these channels and the current technical/commercial comparison is
recorded in `research/milestone_1c_provider_diligence_2026-09-04.md`.

## Sample handling procedure

1. Keep the provider sample outside `data/raw`, `data/interim`, and `data/processed`.
2. Record the provider's sample license, receipt time, permitted users, and deletion date.
3. Run:

   ```text
   uv run chart-observatory procurement profile-sample <sample.csv|sample.json|sample.parquet>
   ```

4. Save only the generated schema profile when the sample agreement permits it. The
   profiler reports file name, SHA-256, byte length, row count, field paths, observed
   types, and null counts; it does not emit row values or copy the sample.
5. Compare the profile with the supplied data dictionary and coverage extract.
6. Delete or return the sample by the contractual deadline. Never import it into the
   research corpus before an approved rights profile exists.

## Human actions required before sending

- Add the researcher's name, institution, role, official email, project title, expected
  publication route, funding status, and desired procurement timeline.
- Choose the required origin platforms/chart families and minimum ranking depth.
- Obtain authority to contact vendors on behalf of the institution.
- Send the request and preserve all replies/order-form versions in the institution's
  approved records system.

The source assessment and its primary citations remain in
`research/historical_sources_assessment.md`.
