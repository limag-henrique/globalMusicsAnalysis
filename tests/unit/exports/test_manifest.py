from datetime import UTC, date, datetime

from chart_observatory.exports.manifest import manifest_bytes, manifest_sha256
from chart_observatory.exports.models import ExportManifest


def test_manifest_is_deterministic_and_complete() -> None:
    manifest = ExportManifest(
        dataset_name="chart_observations",
        schema_version="v1",
        row_count=3,
        file_sha256="a" * 64,
        source_rights_profiles=("profile-1",),
        chart_methodology_versions=("v1",),
        resolution_rule_version="resolution-v1",
        date_start=date(2026, 1, 1),
        date_end=date(2026, 9, 3),
        top_n=100,
        temporal_policy="SAME_NATIVE_FREQUENCY",
        input_artifacts=("b" * 64,),
        input_snapshots=("snapshot-1",),
        software_version="0.1.0",
        git_revision=None,
        dirty=True,
        patch_sha256="c" * 64,
        created_at=datetime(2026, 9, 3, tzinfo=UTC),
    )
    assert manifest_bytes(manifest) == manifest_bytes(manifest)
    assert len(manifest_sha256(manifest)) == 64
    assert b"chart_observations" in manifest_bytes(manifest)
