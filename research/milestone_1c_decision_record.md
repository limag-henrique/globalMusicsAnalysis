# Milestone 1C historical-provider decision record

**Status:** PENDING  
**Prepared:** 2026-09-04  
**Selected provider:** none  
**Production adapter authorized:** no

## Decision boundary

This record cannot become `APPROVED` from public marketing or API documentation alone.
Approval requires a provider-specific coverage extract and sample, executed contractual
rights, institutional/legal sign-off, and explicit human selection/cost approval. Until
then, Luminate, Soundcharts, and Chartmetric adapters remain disabled and no vendor
sample enters the research corpus.

## Current candidate disposition

| Provider | Technical position | Contract position | Decision |
|---|---|---|---|
| Luminate | Leading candidate for documented multinational consumption/history; exact 2021 cells and breaks require an extract | Publication, collaboration, retention, and replication rights require negotiated language | PENDING |
| Soundcharts | Historical chart/date interfaces appear suitable; exact country/platform cells and depths require authenticated evidence | Academic use, upstream rights, retention, and publication require negotiated language | PENDING |
| Chartmetric | Date-aware chart APIs and cross-platform identifiers appear suitable; completeness and metric nullability require a sample | API/Data Share terms, rights, quotas, and price require a separate proposal | PENDING |

This ordering is a procurement priority, not a provider selection.
The dated primary-source review supporting it is
`research/milestone_1c_provider_diligence_2026-09-04.md`.

## Exit-evidence register

| Required evidence | Luminate | Soundcharts | Chartmetric | Acceptance rule |
|---|---|---|---|---|
| Coverage matrix and missing-date manifest | PENDING | PENDING | PENDING | All selected chart cells, first/last period, gaps, depth, frequency, and trend breaks verified |
| Sample checksum and schema profile | PENDING | PENDING | PENDING | Sample is licensed for evaluation; SHA-256 and value-free schema profile recorded |
| Data dictionary and methodology | PENDING | PENDING | PENDING | IDs, units, nulls, rank provenance, correction/version rules documented |
| Price and total cost | PENDING | PENDING | PENDING | Nine-country history, updates, rights, support, and overages included |
| Quota, delivery, and SLA | PENDING | PENDING | PENDING | Bulk/API limits support reproducible collection and correction handling |
| Storage and retention grant | PENDING | PENDING | PENDING | Raw, normalized, backups, audit records, and post-termination rules explicit |
| Academic analysis grant | PENDING | PENDING | PENDING | Derived metrics and cross-country/platform analysis explicit |
| Collaboration/reviewer grant | PENDING | PENDING | PENDING | Named collaborators, reviewers, institution, and processors covered |
| Aggregate publication grant | PENDING | PENDING | PENDING | Tables, figures, lists, IDs, and suppression thresholds explicit |
| Replication rule | PENDING | PENDING | PENDING | Allowed artifacts or enclave/replicator route explicit |
| Upstream-term allocation | PENDING | PENDING | PENDING | Provider warranties and client duties explicit |
| Institutional/legal approval | PENDING | PENDING | PENDING | Written approval references exact agreement version |

## Coverage decision

- Required window: 2021-01-01 through latest available date.
- Alternative balanced window: not selected; 2022 may be considered only after comparing
  verified gaps and scientific consequences.
- Required countries: BR, US, GB, FR, DE, ES, PT, IT, SE.
- Required origin platforms/chart families: PENDING human confirmation and vendor
  coverage evidence.
- Minimum acceptable depth: PENDING human confirmation and vendor evidence.
- Allowed methodology breaks: none silently combined; each must be versioned and exposed.

## Selection rationale

No selection can yet be written. When the evidence register is complete, compare:

1. verified chart-cell coverage and missingness;
2. semantic fit of ranked item, rank, metric, frequency, and methodology;
3. identifier quality and recording-version treatment;
4. legal fit for retention, analysis, collaboration, publication, and replication;
5. reproducibility of deliveries, corrections, and version history;
6. total cost, quota, service level, and operational burden.

Any accepted trade-off must identify the evidence, scientific impact, mitigation, and
residual risk. A lower price cannot compensate for missing publication or retention
rights.

## Required approvals

| Role | Name | Decision/date | Evidence reference |
|---|---|---|---|
| Research owner — provider and cost | PENDING | PENDING | PENDING |
| Institutional procurement | PENDING | PENDING | PENDING |
| Legal/data governance | PENDING | PENDING | PENDING |
| Information security/DPA, if applicable | PENDING | PENDING | PENDING |

## Activation rule

After all approvals, create a provider-specific design addendum and TDD plan from the
exact contracted schema. Adapter implementation and network activation remain separate
human decisions; this document alone does not enable either.
