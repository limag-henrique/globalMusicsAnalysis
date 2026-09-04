from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

import polars as pl
from sqlalchemy import select
from sqlalchemy.orm import Session

from chart_observatory.adapters.files.schema import ManualSchema, load_schema
from chart_observatory.adapters.files.validation import ImportErrorDetail, parse_date
from chart_observatory.artifacts.models import ArtifactContext
from chart_observatory.artifacts.repository import ArtifactCatalog
from chart_observatory.artifacts.store import ArtifactStore
from chart_observatory.db.models.charts import ChartDefinition, ChartEntry, ChartSnapshot
from chart_observatory.db.models.tracks import PlatformItem
from chart_observatory.domain.enums import RightsOperation
from chart_observatory.rights.gate import RightsGate


@dataclass(frozen=True)
class ManualRow:
    country_code: str
    period_start: date
    period_end: date
    position: int
    native_id: str
    title: str
    metric_value: Decimal | None
    raw_fields: dict[str, object]


@dataclass(frozen=True)
class ImportPreview:
    token: str
    valid_rows: int
    rows: tuple[ManualRow, ...]
    errors: tuple[ImportErrorDetail, ...]
    checksum: str


@dataclass(frozen=True)
class ImportRequest:
    path: Path
    schema_version: str
    occurred_at: datetime


@dataclass(frozen=True)
class ImportResult:
    snapshot_id: UUID
    created_entries: int
    checksum: str


class ImportSink(Protocol):
    def existing(self, checksum: str) -> ImportResult | None: ...
    def persist(self, preview: ImportPreview, schema: ManualSchema) -> ImportResult: ...


class InMemoryImportSink:
    """Small deterministic sink used by local acceptance flows and tests."""

    def __init__(self) -> None:
        self.results: dict[str, ImportResult] = {}
        self.rows: list[ManualRow] = []

    def existing(self, checksum: str) -> ImportResult | None:
        return self.results.get(checksum)

    def persist(self, preview: ImportPreview, schema: ManualSchema) -> ImportResult:
        result = ImportResult(uuid4(), len(preview.rows), preview.checksum)
        self.rows.extend(preview.rows)
        self.results[preview.checksum] = result
        return result


class SqlManualImportSink:
    """Persists one supplied chart period as an atomic unresolved snapshot."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def existing(self, checksum: str) -> ImportResult | None:
        snapshot = self.session.scalar(
            select(ChartSnapshot).where(ChartSnapshot.checksum == checksum)
        )
        if snapshot is None:
            return None
        return ImportResult(snapshot.id, 0, snapshot.checksum)

    def persist(self, preview: ImportPreview, schema: ManualSchema) -> ImportResult:
        dimensions = {(row.country_code, row.period_start, row.period_end) for row in preview.rows}
        if len(dimensions) != 1:
            raise ValueError("one import file must contain one country and native period")
        country, period_start, period_end = next(iter(dimensions))
        defaults = schema.defaults
        definition = self.session.scalar(
            select(ChartDefinition).where(
                ChartDefinition.platform_code == defaults["platform_code"],
                ChartDefinition.source_code == defaults["source_code"],
                ChartDefinition.country_code == country,
                ChartDefinition.chart_name == defaults["chart_name"],
            )
        )
        if definition is None:
            definition = ChartDefinition(
                platform_code=defaults["platform_code"],
                source_code=defaults["source_code"],
                country_code=country,
                chart_name=defaults["chart_name"],
                native_frequency=defaults["native_frequency"],
                nominal_depth=max(row.position for row in preview.rows),
                methodology_version=schema.version,
            )
            self.session.add(definition)
            self.session.flush()
        snapshot = ChartSnapshot(
            chart_definition_id=definition.id,
            period_start=period_start,
            period_end=period_end,
            observed_at=datetime.now(UTC),
            checksum=preview.checksum,
            schema_version=schema.version,
            collector_version="manual-importer-v1",
            entry_count=len(preview.rows),
            provider_metadata={},
        )
        self.session.add(snapshot)
        self.session.flush()
        for row in preview.rows:
            item = self.session.scalar(
                select(PlatformItem).where(
                    PlatformItem.platform_code == defaults["platform_code"],
                    PlatformItem.native_id == row.native_id,
                )
            )
            if item is None:
                item = PlatformItem(
                    platform_code=defaults["platform_code"],
                    native_id=row.native_id,
                    item_kind=defaults["item_kind"],
                    title=row.title,
                )
                self.session.add(item)
                self.session.flush()
            self.session.add(
                ChartEntry(
                    snapshot_id=snapshot.id,
                    platform_item_id=item.id,
                    canonical_track_id=None,
                    position=row.position,
                    metric_type=defaults["metric_type"],
                    metric_value=row.metric_value,
                    raw_fields=row.raw_fields,
                )
            )
        self.session.flush()
        return ImportResult(snapshot.id, len(preview.rows), preview.checksum)


class ManualChartImporter:
    def __init__(
        self,
        *,
        config_root: Path | None = None,
        overrides: dict[str, str] | None = None,
        source_id: UUID | None = None,
        rights_gate: RightsGate | None = None,
        artifact_store: ArtifactStore | None = None,
        artifact_catalog: ArtifactCatalog | None = None,
        sink: ImportSink | None = None,
    ) -> None:
        self.config_root = config_root or Path(__file__).parents[4] / "config"
        self.overrides = overrides or {}
        self.source_id = source_id
        self.rights_gate = rights_gate
        self.artifact_store = artifact_store
        self.artifact_catalog = artifact_catalog
        self.sink = sink
        self.persisted_count = 0

    @classmethod
    def for_preview(cls, overrides: dict[str, str] | None = None) -> "ManualChartImporter":
        return cls(overrides=overrides)

    def preview(self, path: Path, schema_version: str) -> ImportPreview:
        content = Path(path).read_bytes()
        checksum = sha256(content).hexdigest()
        schema = load_schema(schema_version, self.config_root)
        frame = pl.read_csv(content, infer_schema_length=0, null_values=[""])
        missing = set(schema.columns.values()) - set(frame.columns)
        if missing:
            missing_errors = tuple(
                ImportErrorDetail(0, column, "missing required column")
                for column in sorted(missing)
            )
            return ImportPreview(checksum, 0, (), missing_errors, checksum)
        rows: list[ManualRow] = []
        errors: list[ImportErrorDetail] = []
        seen: set[tuple[str, date, date, int]] = set()
        for number, raw in enumerate(frame.to_dicts(), start=2):
            parsed, row_errors = self._parse_row(raw, schema, number)
            errors.extend(row_errors)
            if parsed is None:
                continue
            key = (parsed.country_code, parsed.period_start, parsed.period_end, parsed.position)
            if key in seen:
                errors.append(
                    ImportErrorDetail(number, "position", "duplicate rank in chart period")
                )
                continue
            seen.add(key)
            rows.append(parsed)
        return ImportPreview(checksum, len(rows), tuple(rows), tuple(errors), checksum)

    def import_file(self, request: ImportRequest) -> ImportResult:
        source_id = self.source_id
        rights_gate = self.rights_gate
        artifact_store = self.artifact_store
        sink = self.sink
        if source_id is None or rights_gate is None or artifact_store is None or sink is None:
            raise RuntimeError("import dependencies are not configured")
        for operation in (
            RightsOperation.IMPORT,
            RightsOperation.STORE_RAW,
            RightsOperation.STORE_NORMALIZED,
        ):
            rights_gate.require(source_id, operation, request.occurred_at)
        preview = self.preview(request.path, request.schema_version)
        if preview.errors:
            raise ValueError(preview.errors)
        existing = sink.existing(preview.checksum)
        if existing is not None:
            return ImportResult(existing.snapshot_id, 0, existing.checksum)
        content = request.path.read_bytes()
        stored = artifact_store.put(
            content,
            ArtifactContext(
                source_id,
                request.occurred_at,
                "text/csv",
                "manual-importer-v1",
                request.schema_version,
                {"filename": request.path.name},
            ),
        )
        decision = rights_gate.authorize(source_id, RightsOperation.STORE_RAW, request.occurred_at)
        if self.artifact_catalog is not None and decision.profile_id is not None:
            self.artifact_catalog.record_artifact(stored, decision.profile_id)
        result = sink.persist(preview, load_schema(request.schema_version, self.config_root))
        if self.artifact_catalog is not None:
            self.artifact_catalog.record_event(
                "IMPORT",
                "manual-importer-v1",
                {
                    "snapshot_id": str(result.snapshot_id),
                    "artifact_sha256": stored.sha256,
                    "created_entries": result.created_entries,
                },
            )
        self.persisted_count += result.created_entries
        return result

    def _parse_row(
        self, raw: dict[str, object], schema: ManualSchema, number: int
    ) -> tuple[ManualRow | None, list[ImportErrorDetail]]:
        col = schema.columns
        errors: list[ImportErrorDetail] = []
        start, error = parse_date(raw[col["period_start"]], "period_start", number)
        if error:
            errors.append(error)
        end, error = parse_date(raw[col["period_end"]], "period_end", number)
        if error:
            errors.append(error)
        try:
            position = int(str(raw[col["position"]]))
            if position <= 0:
                raise ValueError
        except (TypeError, ValueError):
            position = 0
            errors.append(ImportErrorDetail(number, "position", "rank must be positive"))
        native_id = str(raw[col["native_id"]] or "").strip()
        if not native_id:
            errors.append(ImportErrorDetail(number, "native_id", "native ID is required"))
        metric_raw = raw.get(col["metric_value"])
        try:
            metric = None if metric_raw is None else Decimal(str(metric_raw))
        except InvalidOperation:
            metric = None
            errors.append(ImportErrorDetail(number, "metric_value", "invalid decimal metric"))
        country = str(raw[col["country"]]).upper()
        if len(country) != 2 or not country.isalpha():
            errors.append(ImportErrorDetail(number, "country", "country must be ISO alpha-2"))
        if start and end and start > end:
            errors.append(ImportErrorDetail(number, "period", "period start must not exceed end"))
        if errors or start is None or end is None:
            return None, errors
        mapped_columns = set(col.values())
        provider_fields = {key: value for key, value in raw.items() if key not in mapped_columns}
        return ManualRow(
            country,
            start,
            end,
            position,
            native_id,
            str(raw[col["title"]]),
            metric,
            provider_fields,
        ), errors
