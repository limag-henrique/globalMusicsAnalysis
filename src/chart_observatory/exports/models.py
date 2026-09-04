from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class ExportManifest:
    dataset_name: str
    schema_version: str
    row_count: int
    file_sha256: str
    source_rights_profiles: tuple[str, ...]
    chart_methodology_versions: tuple[str, ...]
    resolution_rule_version: str
    date_start: date
    date_end: date
    top_n: int | None
    temporal_policy: str
    input_artifacts: tuple[str, ...]
    input_snapshots: tuple[str, ...]
    software_version: str
    git_revision: str | None
    dirty: bool
    patch_sha256: str | None
    created_at: datetime
