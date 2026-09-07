from datetime import date
from pathlib import Path

from chart_observatory.sources.mgd import MGDSource
from chart_observatory.sources.models import SourceStatus

FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "mgd"


def test_mgd_streams_rows_and_preserves_null_metric() -> None:
    source = MGDSource(FIXTURE_ROOT)
    rows = list(source.iter_observations())
    assert len(rows) == 3
    assert rows[0].provider == "MGD"
    assert rows[0].origin_platform == "SPOTIFY"
    assert rows[0].metric_value == 1000
    assert rows[1].metric_value is None


def test_mgd_inspection_discovers_market_and_period() -> None:
    manifests = MGDSource(FIXTURE_ROOT).inspect()
    assert len(manifests) == 1
    assert manifests[0].status is SourceStatus.AVAILABLE
    assert manifests[0].countries == ("BR",)
    assert manifests[0].earliest_date == date(2022, 1, 1)
    assert manifests[0].latest_date == date(2022, 1, 2)
    assert manifests[0].row_count == 3


def test_mgd_import_is_idempotent(tmp_path: Path) -> None:
    output = tmp_path / "mgd.parquet"
    source = MGDSource(FIXTURE_ROOT)
    first = source.import_to(output)
    second = source.import_to(output)
    assert first.rows_written == 3
    assert second.rows_written == 0
    assert output.exists()
