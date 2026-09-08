import json
from datetime import date
from decimal import Decimal

import polars as pl
from typer.testing import CliRunner

from chart_observatory.cli import app
from chart_observatory.sources.chartmetric_backfill import (
    BackfillRequest,
    ChartmetricBackfillPlanner,
)
from chart_observatory.sources.models import SourceObservation


def test_plan_expands_all_countries_and_daily_periods_in_stable_order() -> None:
    request = BackfillRequest(
        platform="spotify",
        countries=("US", "BR"),
        interval="daily",
        chart_type="plays",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )

    tasks = ChartmetricBackfillPlanner().plan(request)

    assert [(task.country_code, task.period) for task in tasks] == [
        ("BR", date(2025, 1, 1)),
        ("BR", date(2025, 1, 2)),
        ("US", date(2025, 1, 1)),
        ("US", date(2025, 1, 2)),
    ]


def test_plan_keeps_weekly_periods_as_one_native_period_per_week() -> None:
    request = BackfillRequest(
        platform="spotify",
        countries=("BR",),
        interval="weekly",
        chart_type="plays",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 15),
    )

    tasks = ChartmetricBackfillPlanner().plan(request)

    assert [task.period for task in tasks] == [
        date(2025, 1, 1),
        date(2025, 1, 8),
        date(2025, 1, 15),
    ]


class FakeChartmetricClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date]] = []

    def collect_chart_pages(self, **kwargs):
        self.calls.append((kwargs["country_code"], kwargs["period"]))
        row = SourceObservation(
            provider="CHARTMETRIC",
            origin_platform="SPOTIFY",
            country_code=kwargs["country_code"],
            chart_name=kwargs["chart_type"],
            period_start=kwargs["period"],
            period_end=kwargs["period"],
            rank=1,
            track_title="Song",
            artist="Artist",
            native_id="track-1",
            metric_value=Decimal("12"),
            metric_type="STREAMS",
        )
        if kwargs.get("on_page"):
            kwargs["on_page"](0, {"obj": {"data": [{"rank": 1}]}}, (row,))
        return (row,)

    def discover_capabilities(self, *, platforms):
        from chart_observatory.sources.models import MarketCapability

        return tuple(
            MarketCapability(
                provider="CHARTMETRIC",
                origin_platform=platforms[0].upper(),
                country_code=country,
                country_name=None,
            )
            for country in ("US", "BR")
        )


def test_runner_writes_each_task_and_skips_completed_tasks(tmp_path) -> None:
    from chart_observatory.sources.chartmetric_backfill import ChartmetricBackfillRunner

    client = FakeChartmetricClient()
    request = BackfillRequest(
        platform="spotify",
        countries=("BR",),
        interval="daily",
        chart_type="plays",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 1),
    )
    runner = ChartmetricBackfillRunner(client, tmp_path / "output", tmp_path / "state")

    first = runner.run(request)
    second = runner.run(request)

    assert first.rows_written == 1
    assert first.completed_tasks == 1
    assert second.skipped_tasks == 1
    assert len(client.calls) == 1
    assert list((tmp_path / "output").glob("*.parquet"))
    assert (tmp_path / "state" / "spotify-BR-daily-plays-2025-01-01.json").exists()
    raw_files = list((tmp_path / "state" / "raw").glob("*.json"))
    assert len(raw_files) == 1
    assert json.loads(raw_files[0].read_text(encoding="utf-8"))["obj"]["data"][0]["rank"] == 1


class FailingThenResumingClient(FakeChartmetricClient):
    def collect_chart_pages(self, **kwargs):
        self.calls.append((kwargs["country_code"], kwargs["period"]))
        if len(self.calls) == 1:
            kwargs["on_page"](
                0,
                {"obj": {"data": [{"rank": 1, "trackName": "First"}]}},
                (self._observation(kwargs["period"], 1, "First"),),
            )
            raise RuntimeError("temporary page failure")
        kwargs["on_page"](
            1,
            {"obj": {"data": [{"rank": 2, "trackName": "Second"}]}},
            (self._observation(kwargs["period"], 2, "Second"),),
        )
        return (self._observation(kwargs["period"], 2, "Second"),)

    @staticmethod
    def _observation(period, rank, title):
        return SourceObservation(
            provider="CHARTMETRIC",
            origin_platform="SPOTIFY",
            country_code="BR",
            chart_name="plays",
            period_start=period,
            period_end=period,
            rank=rank,
            track_title=title,
            artist="Artist",
            native_id=f"track-{rank}",
            metric_value=Decimal(str(rank)),
            metric_type="STREAMS",
        )


def test_runner_preserves_normalized_pages_when_a_task_is_resumed(tmp_path) -> None:
    from chart_observatory.sources.chartmetric_backfill import ChartmetricBackfillRunner

    client = FailingThenResumingClient()
    request = BackfillRequest(
        platform="spotify",
        countries=("BR",),
        interval="daily",
        chart_type="plays",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 1),
    )
    runner = ChartmetricBackfillRunner(client, tmp_path / "output", tmp_path / "state")

    first = runner.run(request)
    second = runner.run(request)

    assert first.failed_tasks == 1
    assert second.completed_tasks == 1
    assert pl.read_parquet(next((tmp_path / "output").glob("*.parquet"))).height == 2


def test_backfill_command_requires_explicit_network_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("CHARTMETRIC_REFRESH_TOKEN", "refresh-token")

    result = CliRunner().invoke(
        app,
        [
            "sources",
            "chartmetric",
            "backfill",
            "--platform",
            "spotify",
            "--countries",
            "BR,US",
            "--interval",
            "daily",
            "--chart-type",
            "plays",
            "--from",
            "2025-01-01",
            "--to",
            "2025-01-02",
        ],
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == '{"provider": "CHARTMETRIC", "status": "NETWORK_DISABLED"}'


def test_backfill_command_collects_discovered_markets(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CHARTMETRIC_REFRESH_TOKEN", "refresh-token")

    class Transport:
        def close(self) -> None:
            pass

    monkeypatch.setattr("chart_observatory.cli.HttpxTransport", lambda *_args: Transport())
    monkeypatch.setattr(
        "chart_observatory.cli.ChartmetricClient",
        lambda *_args, **_kwargs: FakeChartmetricClient(),
    )
    result = CliRunner().invoke(
        app,
        [
            "sources",
            "chartmetric",
            "backfill",
            "--platform",
            "spotify",
            "--countries",
            "discovered",
            "--interval",
            "daily",
            "--chart-type",
            "plays",
            "--from",
            "2025-01-01",
            "--to",
            "2025-01-01",
            "--output-dir",
            str(tmp_path / "output"),
            "--state-dir",
            str(tmp_path / "state"),
            "--allow-network",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "COMPLETED"
    assert payload["countries"] == 2
    assert payload["total_tasks"] == 2
    assert payload["rows_written"] == 2
