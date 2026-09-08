# Milestone 1D activation record

**Status:** APPROVED by the project owner  
**Recorded:** 2026-09-07  
**Scope:** all source providers and origin platforms listed in this project

The project owner explicitly granted the rights decision for the listed sources,
including Spotify, YouTube Music, Amazon Music, Apple network collection, YouTube
Data API, Chartmetric, Pro-Música Brasil, Kaggle, MGD, and authorized institutional
files. The implementation may therefore persist, analyze, and export data according
to the source-specific grants configured for each run.

This decision does not invent technical coverage. A source remains `NOT_SUPPORTED`,
`NOT_CONFIGURED`, `AUTH_FAILED`, `RATE_LIMITED`, or `SOURCE_UNAVAILABLE` when its
adapter, credential, endpoint, quota, or observed market capability is not available.
Current-state rankings, historical rankings, aggregate charts, video charts, and
track charts remain separate constructs.

Network collection is still explicit and bounded at the command boundary. The
operator must pass the provider's opt-in flag and a concrete market/chart/window;
there is no broad collection default. Raw artifacts and normalized rows continue to
be retained only through the existing rights-gated application services.
