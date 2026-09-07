from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any


class SourceStatus(StrEnum):
    NOT_DISCOVERED = "NOT_DISCOVERED"
    DISCOVERED = "DISCOVERED"
    AVAILABLE = "AVAILABLE"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    IMPORTING = "IMPORTING"
    IMPORTED = "IMPORTED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    AUTH_FAILED = "AUTH_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"


@dataclass(frozen=True)
class SourceObservation:
    provider: str
    origin_platform: str
    country_code: str
    chart_name: str
    period_start: date
    period_end: date
    rank: int
    track_title: str
    artist: str
    native_id: str | None = None
    metric_value: Decimal | None = None
    metric_type: str | None = None
    source_artifact: str | None = None
    source_row_number: int | None = None
    track_language: str | None = None
    raw_fields: dict[str, Any] = field(default_factory=dict)

    def observation_key(self) -> tuple[object, ...]:
        """Identify one provider observation without discarding its provenance."""
        return (
            self.provider,
            self.origin_platform,
            self.country_code,
            self.chart_name,
            self.period_start,
            self.period_end,
            self.rank,
            self.native_id or self.track_title.casefold(),
        )

    def canonical_equivalence_key(self) -> tuple[object, ...]:
        """Identify candidates for cross-source equivalence/conflict analysis."""
        return (
            self.origin_platform,
            self.country_code,
            self.chart_name,
            self.period_start,
            self.period_end,
            self.rank,
            self.native_id or (self.artist.casefold(), self.track_title.casefold()),
        )


@dataclass(frozen=True)
class MarketCapability:
    provider: str
    origin_platform: str
    country_code: str
    country_name: str | None
    territory_type: str = "COUNTRY"
    available: bool = True
    earliest_date: date | None = None
    latest_date: date | None = None
    chart_types: tuple[str, ...] = ()
    native_frequency: str | None = None
    ranking_depth: int | None = None
    number_of_tracks: int | None = None
    number_of_observations: int | None = None
    coverage_ratio: float | None = None


@dataclass(frozen=True)
class SourceManifest:
    provider: str
    origin_platform: str
    filename: str
    path: Path
    sha256: str
    size_bytes: int
    row_count: int
    schema_version: str
    status: SourceStatus
    countries: tuple[str, ...] = ()
    chart_types: tuple[str, ...] = ()
    earliest_date: date | None = None
    latest_date: date | None = None
    number_of_tracks: int | None = None
    number_of_observations: int | None = None
    missing_periods: int | None = None
    parser_version: str = "1"


@dataclass(frozen=True)
class ImportSummary:
    provider: str
    rows_seen: int
    rows_written: int
    rows_skipped: int
    countries: tuple[str, ...]
    charts: tuple[str, ...]
    earliest_date: date | None
    latest_date: date | None
    output_path: Path
    status: SourceStatus
