import json
from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.charts.dto import ChartEntryDTO, ChartPayload
from chart_observatory.ingestion.youtube import collect_youtube_current


class Source:
    def fetch(self, region: str, category_id: str, occurred_at: datetime) -> ChartPayload:
        if region == "US":
            raise RuntimeError("quota")
        return ChartPayload(
            source_code="YOUTUBE_DATA_API",
            platform_code="YOUTUBE_VIDEO",
            country_code=region,
            chart_name="YouTube Video Most Popular",
            native_frequency="DAILY",
            observed_at=occurred_at,
            raw_bytes=json.dumps(
                ["eyJpdGVtcyI6W3siaWQiOiJ2aWRlby1hIiwic25pcHBldCI6e319XX0="]
            ).encode(),
            entries=(
                ChartEntryDTO(
                    1,
                    "video-a",
                    "VIDEO",
                    None,
                    "NONE",
                    {"availability": "AVAILABLE"},
                    "Video A",
                ),
            ),
            provider_metadata={"video_category_id": category_id},
        )


def test_collect_youtube_current_writes_normalized_rows_and_failures(tmp_path: Path) -> None:
    output = tmp_path / "youtube.parquet"
    failures = tmp_path / "failures.json"
    summary = collect_youtube_current(
        Source(),
        ["BR", "US"],
        observed_at=datetime(2026, 9, 7, tzinfo=UTC),
        output=output,
        raw_root=tmp_path / "raw",
        failure_output=failures,
    )
    assert summary.regions_collected == 1
    assert summary.rows_written == 1
    assert summary.failures[0]["country_code"] == "US"
    assert output.exists()
    assert failures.exists()
