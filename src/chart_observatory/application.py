from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

import polars as pl
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from chart_observatory.adapters.files.manual import (
    ImportRequest,
    ManualChartImporter,
    SqlManualImportSink,
)
from chart_observatory.artifacts.store import ArtifactStore
from chart_observatory.db.base import Base
from chart_observatory.db.models.charts import ChartDefinition, ChartEntry, ChartSnapshot
from chart_observatory.db.models.tracks import CanonicalTrack, PlatformItem
from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.exports.manifest import manifest_sha256
from chart_observatory.exports.models import ExportManifest
from chart_observatory.exports.writer import AtomicDatasetWriter, AuthorizedDatasetWriter
from chart_observatory.rights.gate import RightsGate
from chart_observatory.rights.models import RightsGrant, RightsProfile
from chart_observatory.rights.repository import InMemoryRightsRepository


class ResearchApplication:
    """Operational application service shared by CLI, API, and UI.

    PostgreSQL is selected by passing ``database_url`` (the CLI does this from
    settings). A local SQLite file remains the default for deterministic tests
    and offline development. Both paths use the same repositories and schema.
    """

    def __init__(
        self,
        root: Path,
        *,
        database_url: str | None = None,
        manual_authorized: bool = False,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        url = database_url or f"sqlite+pysqlite:///{(self.root / 'research.sqlite3').as_posix()}"
        self.engine = create_engine(url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine, class_=Session, expire_on_commit=False
        )
        self.session = self.session_factory()
        self.source_id = uuid5(NAMESPACE_URL, "chart-observatory:manual-authorized-file")
        self.profile_id = uuid5(NAMESPACE_URL, "chart-observatory:local-manual-profile")
        now = datetime.now(UTC)
        operations = tuple(RightsOperation) if manual_authorized else ()
        profile = RightsProfile(
            source_id=self.source_id,
            status=(
                RightsProfileStatus.APPROVED if manual_authorized else RightsProfileStatus.PENDING
            ),
            valid_from=now - timedelta(days=1),
            valid_until=None,
            grants=tuple(RightsGrant(self.profile_id, operation, True) for operation in operations),
            id=self.profile_id,
        )
        self.gate = RightsGate(InMemoryRightsRepository([profile]))
        self.sink = SqlManualImportSink(self.session)
        self.artifact_store = ArtifactStore(self.root / "raw", self.gate)
        self.importer = ManualChartImporter(
            source_id=self.source_id,
            rights_gate=self.gate,
            artifact_store=self.artifact_store,
            sink=self.sink,
        )
        self.previews: dict[str, tuple[Path, str]] = {}

    def preview_import(
        self, path: Path, schema_version: str = "manual_generic_v1"
    ) -> dict[str, object]:
        preview = self.importer.preview(path, schema_version)
        self.previews[preview.token] = (Path(path), schema_version)
        return {
            "token": preview.token,
            "valid_rows": preview.valid_rows,
            "errors": [error.__dict__ for error in preview.errors],
            "checksum": preview.checksum,
        }

    def apply_import(self, token: str) -> dict[str, object]:
        path, schema = self.previews[token]
        try:
            result = self.importer.import_file(ImportRequest(path, schema, datetime.now(UTC)))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return {
            "snapshot_id": str(result.snapshot_id),
            "entry_count": result.created_entries,
            "checksum": result.checksum,
        }

    def rankings(self, country: str | None = None) -> dict[str, object]:
        statement = (
            select(
                ChartDefinition.country_code,
                ChartSnapshot.period_start,
                ChartEntry.position,
                PlatformItem.native_id,
                PlatformItem.title,
                ChartEntry.metric_value,
            )
            .join(ChartSnapshot, ChartSnapshot.chart_definition_id == ChartDefinition.id)
            .join(ChartEntry, ChartEntry.snapshot_id == ChartSnapshot.id)
            .join(PlatformItem, PlatformItem.id == ChartEntry.platform_item_id)
            .order_by(ChartSnapshot.period_start, ChartEntry.position)
        )
        if country:
            statement = statement.where(ChartDefinition.country_code == country.upper())
        rows = self.session.execute(statement).all()
        return {
            "rows": [
                {
                    "country": row.country_code,
                    "position": row.position,
                    "platform_item_id": row.native_id,
                    "title": row.title,
                    "metric_value": str(row.metric_value) if row.metric_value is not None else None,
                }
                for row in rows
            ]
        }

    def coverage(self, country: str | None = None) -> dict[str, object]:
        statement = (
            select(
                ChartDefinition.country_code,
                ChartSnapshot.period_start,
                ChartSnapshot.period_end,
            )
            .join(ChartSnapshot, ChartSnapshot.chart_definition_id == ChartDefinition.id)
            .distinct()
            .order_by(ChartDefinition.country_code, ChartSnapshot.period_start)
        )
        if country:
            statement = statement.where(ChartDefinition.country_code == country.upper())
        periods = self.session.execute(statement).all()
        return {
            "cells": [
                {
                    "country": code,
                    "period_start": start.isoformat(),
                    "period_end": end.isoformat(),
                    "status": "AVAILABLE",
                }
                for code, start, end in periods
            ]
        }

    def provenance(self) -> dict[str, object]:
        artifacts = [path.name for path in (self.root / "raw" / "sha256").glob("*/*")]
        return {
            "artifacts": sorted(artifacts),
            "source_code": "MANUAL_AUTHORIZED_FILE",
            "rights_profile_id": str(self.profile_id),
        }

    def resolution(self) -> dict[str, object]:
        total = self.session.scalar(select(func.count(ChartEntry.id))) or 0
        resolved = (
            self.session.scalar(
                select(func.count(ChartEntry.id)).where(ChartEntry.canonical_track_id.is_not(None))
            )
            or 0
        )
        return {
            "unresolved": total - resolved,
            "resolved": resolved,
            "status": "UNRESOLVED"
            if total and resolved < total
            else ("RESOLVED" if total else "EMPTY"),
        }

    def rights(self) -> dict[str, object]:
        decision = self.gate.authorize(self.source_id, RightsOperation.IMPORT, datetime.now(UTC))
        return {
            "source_code": "MANUAL_AUTHORIZED_FILE",
            "import_allowed": decision.allowed,
            "reason": decision.reason,
        }

    def export(self, dataset_name: str, format: str) -> dict[str, object]:
        frame = self._dataset(dataset_name)
        writer = AuthorizedDatasetWriter(AtomicDatasetWriter(self.root / "exports"), self.gate)
        path = writer.write(frame, dataset_name, format, [self.source_id], datetime.now(UTC))
        file_hash = sha256(path.read_bytes()).hexdigest()
        periods = self.session.execute(
            select(ChartSnapshot.period_start, ChartSnapshot.period_end)
        ).all()
        manifest = ExportManifest(
            dataset_name,
            "v1",
            frame.height,
            file_hash,
            (str(self.profile_id),),
            ("v1",),
            "resolution-v1",
            min((p[0] for p in periods), default=date.today()),
            max((p[1] for p in periods), default=date.today()),
            None,
            "SAME_NATIVE_FREQUENCY",
            tuple(cast(list[str], self.provenance()["artifacts"])),
            tuple(
                str(snapshot_id)
                for (snapshot_id,) in self.session.execute(select(ChartSnapshot.id)).all()
            ),
            "0.1.0",
            None,
            True,
            None,
            datetime.now(UTC),
        )
        return {
            "path": str(path),
            "row_count": frame.height,
            "manifest_sha256": manifest_sha256(manifest),
        }

    def _dataset(self, name: str) -> pl.DataFrame:
        observation_rows = (
            self.session.execute(
                select(
                    ChartSnapshot.id.label("snapshot_id"),
                    ChartDefinition.country_code,
                    ChartDefinition.platform_code,
                    ChartDefinition.source_code,
                    ChartSnapshot.period_start,
                    ChartSnapshot.period_end,
                    ChartDefinition.native_frequency,
                    ChartEntry.position,
                    ChartEntry.platform_item_id,
                    ChartEntry.canonical_track_id,
                    ChartEntry.metric_type,
                    ChartEntry.metric_value,
                )
                .join(ChartSnapshot, ChartSnapshot.chart_definition_id == ChartDefinition.id)
                .join(ChartEntry, ChartEntry.snapshot_id == ChartSnapshot.id)
            )
            .mappings()
            .all()
        )
        observations = [
            {
                key: (
                    str(value)
                    if key in {"snapshot_id", "platform_item_id", "canonical_track_id"}
                    and value is not None
                    else (float(value) if key == "metric_value" and value is not None else value)
                )
                for key, value in dict(row).items()
            }
            for row in observation_rows
        ]
        if name == "chart_observations":
            return pl.DataFrame(observations) if observations else pl.DataFrame({"position": []})
        if name == "coverage_matrix":
            return (
                pl.DataFrame(cast(list[dict[str, object]], self.coverage()["cells"]))
                if observations
                else pl.DataFrame({"status": []})
            )
        if name == "track_master":
            rows = self.session.execute(select(CanonicalTrack.id, CanonicalTrack.title)).all()
            return (
                pl.DataFrame(
                    [{"canonical_track_id": str(row.id), "title": row.title} for row in rows]
                )
                if rows
                else pl.DataFrame({"canonical_track_id": [], "title": []})
            )
        if name == "track_platform_country_summary":
            rows = self.session.execute(
                select(
                    ChartEntry.canonical_track_id,
                    ChartDefinition.platform_code,
                    ChartDefinition.country_code,
                    func.count(ChartEntry.id).label("appearances"),
                )
                .join(ChartSnapshot, ChartSnapshot.id == ChartEntry.snapshot_id)
                .join(ChartDefinition, ChartDefinition.id == ChartSnapshot.chart_definition_id)
                .where(ChartEntry.canonical_track_id.is_not(None))
                .group_by(
                    ChartEntry.canonical_track_id,
                    ChartDefinition.platform_code,
                    ChartDefinition.country_code,
                )
            ).all()
            return (
                pl.DataFrame([dict(row._mapping) for row in rows])
                if rows
                else pl.DataFrame({"canonical_track_id": [], "appearances": []})
            )
        if name == "cross_platform_presence":
            rows = self.session.execute(
                select(
                    ChartEntry.canonical_track_id,
                    func.count(func.distinct(ChartDefinition.platform_code)).label("platforms"),
                    func.count(func.distinct(ChartDefinition.country_code)).label("countries"),
                    func.count(ChartEntry.id).label("charted_items"),
                )
                .join(ChartSnapshot, ChartSnapshot.id == ChartEntry.snapshot_id)
                .join(ChartDefinition, ChartDefinition.id == ChartSnapshot.chart_definition_id)
                .where(ChartEntry.canonical_track_id.is_not(None))
                .group_by(ChartEntry.canonical_track_id)
            ).all()
            return (
                pl.DataFrame([dict(row._mapping) for row in rows])
                if rows
                else pl.DataFrame({"canonical_track_id": [], "platforms": []})
            )
        raise ValueError(f"unknown dataset: {name}")


# Existing callers retain the old name while all new entry points use the
# operational implementation above.
LocalResearchApplication = ResearchApplication
