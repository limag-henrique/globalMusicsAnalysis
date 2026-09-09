from pathlib import Path

from sqlalchemy import select

from chart_observatory.adapters.files.manual import ImportMetadata
from chart_observatory.application import ResearchApplication
from chart_observatory.db.models.charts import ChartDefinition
from chart_observatory.db.models.tracks import PlatformItem


def test_generic_import_persists_provider_platform_artist_and_isrc(tmp_path: Path) -> None:
    source = tmp_path / "chart.csv"
    source.write_text(
        "country,period_start,period_end,rank,platform_item_id,title,artist,isrc,metric_value\n"
        "BR,2024-01-07,2024-01-07,1,apple-1,Flowers,Miley Cyrus,USSM12200001,100\n",
        encoding="utf-8",
    )
    service = ResearchApplication(tmp_path / "runtime", manual_authorized=True)
    metadata = ImportMetadata("SOUNDCHARTS", "APPLE_MUSIC", "TOP_TRACKS", "WEEKLY", "STREAMS")

    preview = service.preview_import(source, "manual_generic_v2", metadata)
    service.apply_import(str(preview["token"]))

    definition = service.session.scalar(select(ChartDefinition))
    item = service.session.scalar(select(PlatformItem))
    assert definition is not None
    assert definition.source_code == "SOUNDCHARTS"
    assert definition.platform_code == "APPLE_MUSIC"
    assert definition.chart_name == "TOP_TRACKS"
    assert item is not None
    assert item.artist == "Miley Cyrus"

