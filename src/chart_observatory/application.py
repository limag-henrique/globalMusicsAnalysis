from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

import polars as pl

from chart_observatory.adapters.files.manual import (
    ImportRequest,
    InMemoryImportSink,
    ManualChartImporter,
)
from chart_observatory.artifacts.store import ArtifactStore
from chart_observatory.domain.enums import RightsOperation, RightsProfileStatus
from chart_observatory.exports.manifest import manifest_sha256
from chart_observatory.exports.models import ExportManifest
from chart_observatory.exports.writer import AtomicDatasetWriter, AuthorizedDatasetWriter
from chart_observatory.rights.gate import RightsGate
from chart_observatory.rights.models import RightsGrant, RightsProfile
from chart_observatory.rights.repository import InMemoryRightsRepository


class LocalResearchApplication:
    """Local 1A application service. Authorization must be explicitly enabled by its caller."""

    def __init__(self, root: Path, *, manual_authorized: bool = False) -> None:
        self.root = Path(root)
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
        self.sink = InMemoryImportSink()
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
        result = self.importer.import_file(ImportRequest(path, schema, datetime.now(UTC)))
        return {
            "snapshot_id": str(result.snapshot_id),
            "entry_count": result.created_entries,
            "checksum": result.checksum,
        }

    def rankings(self, country: str | None = None) -> dict[str, object]:
        rows = [
            row for row in self.sink.rows if country is None or row.country_code == country.upper()
        ]
        return {
            "rows": [
                {
                    "country": row.country_code,
                    "position": row.position,
                    "platform_item_id": row.native_id,
                    "title": row.title,
                    "metric_value": str(row.metric_value) if row.metric_value is not None else None,
                }
                for row in sorted(rows, key=lambda item: (item.period_start, item.position))
            ]
        }

    def coverage(self, country: str | None = None) -> dict[str, object]:
        periods = sorted(
            {
                (row.country_code, row.period_start, row.period_end)
                for row in self.sink.rows
                if country is None or row.country_code == country.upper()
            }
        )
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
        return {
            "unresolved": len(self.sink.rows),
            "resolved": 0,
            "status": "UNRESOLVED" if self.sink.rows else "EMPTY",
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
        periods = [(row.period_start, row.period_end) for row in self.sink.rows]
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
            tuple(str(result.snapshot_id) for result in self.sink.results.values()),
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
        observations = [
            {
                "country_code": row.country_code,
                "period_start": row.period_start,
                "period_end": row.period_end,
                "position": row.position,
                "platform_item_id": row.native_id,
                "canonical_track_id": None,
                "metric_value": float(row.metric_value) if row.metric_value is not None else None,
            }
            for row in self.sink.rows
        ]
        if name == "chart_observations":
            return pl.DataFrame(observations) if observations else pl.DataFrame({"position": []})
        if name == "coverage_matrix":
            return (
                pl.DataFrame(cast(list[dict[str, object]], self.coverage()["cells"]))
                if self.sink.rows
                else pl.DataFrame({"status": []})
            )
        if name == "track_master":
            return pl.DataFrame({"canonical_track_id": [], "title": []})
        if name == "track_platform_country_summary":
            return pl.DataFrame({"canonical_track_id": [], "appearances": []})
        if name == "cross_platform_presence":
            return pl.DataFrame({"canonical_track_id": [], "platforms": []})
        raise ValueError(f"unknown dataset: {name}")
