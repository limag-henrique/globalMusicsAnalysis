from datetime import date
from decimal import Decimal
from pathlib import Path

from chart_observatory.sources.models import SourceObservation
from chart_observatory.sources.reports import write_artist_year_report, write_global_market_coverage


def row(country: str, artist: str, rank: int, year: int) -> SourceObservation:
    return SourceObservation(
        provider="MGD",
        origin_platform="SPOTIFY",
        country_code=country,
        chart_name="Top 200",
        period_start=date(year, 1, 1),
        period_end=date(year, 1, 1),
        rank=rank,
        track_title=f"Track {rank}",
        artist=artist,
        native_id=f"id-{rank}",
        metric_value=Decimal("10"),
        metric_type="STREAMS",
    )


def test_artist_year_report_ranks_appearances_and_keeps_country(tmp_path: Path) -> None:
    output = tmp_path / "artists.csv"
    summary = write_artist_year_report(
        [row("BR", "A", 1, 2022), row("BR", "A", 2, 2022), row("US", "A", 1, 2022)], output
    )
    assert summary.rows_written == 2
    assert "BR" in output.read_text(encoding="utf-8")
    assert "chart_appearances" in output.read_text(encoding="utf-8")


def test_market_coverage_lists_sources_and_platforms(tmp_path: Path) -> None:
    from chart_observatory.sources.models import SourceManifest, SourceStatus

    manifest = SourceManifest(
        "MGD", "SPOTIFY", "x", Path("x"), "a" * 64, 1, 1, "v1", SourceStatus.AVAILABLE, ("BR",)
    )
    output = write_global_market_coverage([manifest], tmp_path)
    assert "BR" in output.read_text(encoding="utf-8")
    assert "MGD" in output.read_text(encoding="utf-8")
