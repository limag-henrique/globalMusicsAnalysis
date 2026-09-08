from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.corpus.eligibility import EligibilityResult
from chart_observatory.db.models.charts import ChartDefinition, ChartEntry, ChartSnapshot
from chart_observatory.db.models.corpus import (
    CanonicalChartEntry,
    ChartCellProfile,
    CorpusMembership,
    CorpusVersion,
    GenreClaim,
    MarketGeography,
    SemanticAnnotation,
    SourceConflict,
    TrackLanguage,
)
from chart_observatory.db.models.tracks import PlatformItem
from chart_observatory.metadata.geography import GeographyRecord
from chart_observatory.metadata.taxonomy import normalize_genre, normalize_language

SOURCE_PRECEDENCE = {
    "MGD": 0,
    "KAGGLE_DHRUVILDAVE": 1,
    "CHARTMETRIC": 2,
    "PRO_MUSICA_BRASIL": 3,
}


@dataclass(frozen=True)
class ReconciliationSummary:
    canonical_entries: int
    conflicts: int
    skipped_unresolved: int


@dataclass(frozen=True)
class CorpusFreezeRequest:
    name: str
    version: str
    rules: dict[str, object]
    source_snapshot_ids: tuple[str, ...]
    date_start: date
    date_end: date
    memberships: tuple[dict[str, object], ...]
    software_version: str = "0.1.0"
    git_revision: str | None = None
    dirty: bool = True


def upsert_geography(session: Session, record: GeographyRecord) -> MarketGeography:
    row = session.scalar(
        select(MarketGeography).where(
            MarketGeography.country_code == record.country_code,
            MarketGeography.source_version == record.source_version,
        )
    )
    if row is None:
        row = MarketGeography(**record.__dict__)
        session.add(row)
        session.flush()
    return row


def add_genre_claim(
    session: Session,
    track_id: UUID,
    raw_label: str,
    source: str,
    source_version: str,
    confidence: float = 1.0,
    review_status: str = "UNREVIEWED",
) -> GenreClaim:
    row = GenreClaim(
        canonical_track_id=track_id,
        raw_label=raw_label,
        normalized_genre=normalize_genre(raw_label),
        source=source,
        source_version=source_version,
        confidence=confidence,
        review_status=review_status,
    )
    session.add(row)
    return row


def add_language_claim(
    session: Session,
    track_id: UUID,
    raw_code: str,
    source: str,
    source_version: str,
    confidence: float = 1.0,
    is_multilingual: bool = False,
) -> TrackLanguage:
    row = TrackLanguage(
        canonical_track_id=track_id,
        language_code=normalize_language(raw_code),
        raw_value=raw_code,
        source=source,
        source_version=source_version,
        confidence=confidence,
        is_multilingual=is_multilingual,
    )
    session.add(row)
    return row


def add_semantic_annotation(
    session: Session,
    lyric_document_id: UUID,
    *,
    category: str,
    value: float,
    confidence: float | None,
    method: str,
    model_version: str,
    source: str,
    review_status: str = "UNREVIEWED",
) -> SemanticAnnotation:
    row = SemanticAnnotation(
        lyric_document_id=lyric_document_id,
        category=category,
        value=value,
        confidence=confidence,
        method=method,
        model_version=model_version,
        source=source,
        review_status=review_status,
    )
    session.add(row)
    return row


def profile_chart_cell(session: Session, result: EligibilityResult) -> ChartCellProfile:
    cell = result.cell
    row = session.scalar(
        select(ChartCellProfile).where(
            ChartCellProfile.provider == cell.provider,
            ChartCellProfile.platform_code == cell.platform_code,
            ChartCellProfile.country_code == cell.country_code,
            ChartCellProfile.chart_family == cell.chart_family,
            ChartCellProfile.frequency == cell.frequency,
        )
    )
    values = {
        "provider": cell.provider,
        "platform_code": cell.platform_code,
        "country_code": cell.country_code,
        "chart_family": cell.chart_family,
        "frequency": cell.frequency,
        "first_date": result.first_date,
        "last_date": result.last_date,
        "expected_periods": result.expected_periods,
        "observed_periods": result.observed_periods,
        "coverage_ratio": result.coverage_ratio,
        "longest_gap": result.longest_gap,
        "number_of_tracks": result.number_of_tracks,
        "median_chart_depth": result.median_chart_depth,
        "source_quality": cell.source_quality,
        "metadata_json": {"eligibility_reasons": list(result.reasons)},
    }
    if row is None:
        row = ChartCellProfile(**values)
        session.add(row)
    else:
        for key, value in values.items():
            setattr(row, key, value)
    session.flush()
    return row


def reconcile_entries(
    session: Session,
    *,
    precedence: dict[str, int] | None = None,
    version: str = "reconciliation-v1",
) -> ReconciliationSummary:
    ranking = precedence or SOURCE_PRECEDENCE
    rows = session.execute(
        select(
            ChartEntry,
            ChartSnapshot,
            ChartDefinition,
            PlatformItem,
        )
        .join(ChartSnapshot, ChartSnapshot.id == ChartEntry.snapshot_id)
        .join(ChartDefinition, ChartDefinition.id == ChartSnapshot.chart_definition_id)
        .join(PlatformItem, PlatformItem.id == ChartEntry.platform_item_id)
        .where(ChartEntry.canonical_track_id.is_not(None))
    ).all()
    groups: dict[
        tuple[str, str, str, date, date, UUID],
        list[tuple[ChartEntry, ChartSnapshot, ChartDefinition, PlatformItem]],
    ] = {}
    for entry, snapshot, definition, item in rows:
        track_id = entry.canonical_track_id
        if track_id is None:
            continue
        key: tuple[str, str, str, date, date, UUID] = (
            str(definition.platform_code),
            str(definition.country_code),
            str(definition.chart_name),
            snapshot.period_start,
            snapshot.period_end,
            track_id,
        )
        groups.setdefault(key, []).append((entry, snapshot, definition, item))
    created = conflicts = 0
    for key, candidates in groups.items():
        candidates.sort(key=lambda row: (ranking.get(row[2].source_code, 999), str(row[0].id)))
        selected, _, definition, _ = candidates[0]
        existing = session.scalar(
            select(CanonicalChartEntry).where(
                CanonicalChartEntry.origin_platform == key[0],
                CanonicalChartEntry.country_code == key[1],
                CanonicalChartEntry.chart_family == key[2],
                CanonicalChartEntry.period_start == key[3],
                CanonicalChartEntry.period_end == key[4],
                CanonicalChartEntry.canonical_track_id == key[5],
            )
        )
        if existing is not None:
            continue
        source_ids = [str(candidate[0].id) for candidate in candidates]
        rank_values = {candidate[0].position for candidate in candidates}
        metric_values = {str(candidate[0].metric_value) for candidate in candidates}
        conflict = len(rank_values) > 1 or len(metric_values) > 1
        canonical = CanonicalChartEntry(
            origin_platform=key[0],
            country_code=key[1],
            chart_family=key[2],
            period_start=key[3],
            period_end=key[4],
            canonical_track_id=key[5],
            rank=selected.position,
            metric_type=selected.metric_type,
            metric_value=selected.metric_value,
            selected_provider=definition.source_code,
            selected_chart_entry_id=selected.id,
            source_entry_ids=source_ids,
            conflict_status="SOURCE_CONFLICT" if conflict else "NONE",
            reconciliation_version=version,
        )
        session.add(canonical)
        session.flush()
        created += 1
        if conflict:
            session.add(
                SourceConflict(
                    canonical_chart_entry_id=canonical.id,
                    conflict_type="RANK_OR_METRIC_DISAGREEMENT",
                    source_values=[
                        {
                            "provider": candidate[2].source_code,
                            "rank": candidate[0].position,
                            "metric_value": str(candidate[0].metric_value),
                            "entry_id": str(candidate[0].id),
                        }
                        for candidate in candidates
                    ],
                )
            )
            conflicts += 1
    session.flush()
    unresolved = session.scalar(
        select(ChartEntry.id).where(ChartEntry.canonical_track_id.is_(None))
    )
    return ReconciliationSummary(created, conflicts, 1 if unresolved is not None else 0)


def freeze_corpus(session: Session, request: CorpusFreezeRequest) -> CorpusVersion:
    payload = {
        "name": request.name,
        "version": request.version,
        "rules": request.rules,
        "source_snapshot_ids": list(request.source_snapshot_ids),
        "date_start": request.date_start.isoformat(),
        "date_end": request.date_end.isoformat(),
        "memberships": list(request.memberships),
    }
    manifest_sha256 = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    version = CorpusVersion(
        name=request.name,
        version=request.version,
        status="FROZEN",
        rules=request.rules,
        source_snapshot_ids=list(request.source_snapshot_ids),
        date_start=request.date_start,
        date_end=request.date_end,
        manifest_sha256=manifest_sha256,
        software_version=request.software_version,
        git_revision=request.git_revision,
        dirty=request.dirty,
        frozen_at=datetime.now(UTC),
    )
    session.add(version)
    session.flush()
    for member in request.memberships:
        member_payload = dict(member)
        member_payload["corpus_version_id"] = version.id
        member_payload["member_key"] = str(member_payload.get("member_key", ""))
        session.add(CorpusMembership(**member_payload))
    session.flush()
    return version
