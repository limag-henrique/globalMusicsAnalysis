from pathlib import Path

from chart_observatory.adapters.files.manual import ImportMetadata, ManualChartImporter


def test_generic_schema_carries_provider_platform_and_artist_metadata(tmp_path: Path) -> None:
    source = tmp_path / "chart.csv"
    source.write_text(
        "country,period_start,period_end,rank,platform_item_id,title,artist,isrc,metric_value\n"
        "BR,2024-01-07,2024-01-07,1,apple-1,Flowers,Miley Cyrus,USSM12200001,100\n",
        encoding="utf-8",
    )

    preview = ManualChartImporter.for_preview().preview(source, "manual_generic_v2")

    assert preview.valid_rows == 1
    assert preview.rows[0].artist == "Miley Cyrus"
    assert preview.rows[0].isrc == "USSM12200001"

    request = ImportMetadata(
        provider="SOUNDCHARTS",
        origin_platform="APPLE_MUSIC",
        chart_family="TOP_TRACKS",
        native_frequency="WEEKLY",
        metric_type="STREAMS",
    )
    assert request.provider == "SOUNDCHARTS"
