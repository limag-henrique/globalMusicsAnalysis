from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol

import polars as pl


@dataclass(frozen=True)
class BackfillRequest:
    platform: str
    countries: tuple[str, ...]
    interval: str
    chart_type: str
    start_date: date
    end_date: date
    page_size: int = 200
    available_dates_by_country: Mapping[str, tuple[date, ...]] | None = None


@dataclass(frozen=True)
class BackfillTask:
    platform: str
    country_code: str
    interval: str
    chart_type: str
    period: date
    page_size: int

    @property
    def task_id(self) -> str:
        return "-".join(
            (
                self.platform.casefold(),
                self.country_code,
                self.interval.casefold(),
                self.chart_type.casefold(),
                self.period.isoformat(),
            )
        )


@dataclass(frozen=True)
class BackfillSummary:
    total_tasks: int
    completed_tasks: int
    skipped_tasks: int
    failed_tasks: int
    rows_written: int
    failures: tuple[str, ...] = ()


class ChartmetricPageCollector(Protocol):
    def collect_chart_pages(
        self,
        *,
        platform: str,
        country_code: str,
        interval: str,
        chart_type: str,
        period: date,
        page_size: int,
        checkpoint_path: Path,
        on_page: Callable[[int, dict[str, object], tuple[Any, ...]], None] | None = None,
    ) -> tuple[Any, ...]: ...


class ChartmetricBackfillPlanner:
    def plan(self, request: BackfillRequest) -> tuple[BackfillTask, ...]:
        requested_periods = _periods(request.start_date, request.end_date, request.interval)
        tasks: list[BackfillTask] = []
        for country in sorted({value.upper() for value in request.countries}):
            periods = requested_periods
            if request.available_dates_by_country is not None:
                available = {
                    value
                    for value in request.available_dates_by_country.get(country, ())
                    if request.start_date <= value <= request.end_date
                }
                periods = tuple(period for period in requested_periods if period in available)
            tasks.extend(
                BackfillTask(
                    platform=request.platform,
                    country_code=country,
                    interval=request.interval,
                    chart_type=request.chart_type,
                    period=period,
                    page_size=request.page_size,
                )
                for period in periods
            )
        return tuple(tasks)


class ChartmetricBackfillRunner:
    """Execute planned Chartmetric cells with append-only task artifacts."""

    def __init__(
        self,
        client: ChartmetricPageCollector,
        output_dir: Path,
        state_dir: Path,
    ) -> None:
        self.client = client
        self.output_dir = Path(output_dir)
        self.state_dir = Path(state_dir)
        self.checkpoint_dir = self.state_dir / "checkpoints"

    def run(self, request: BackfillRequest, *, resume: bool = True) -> BackfillSummary:
        tasks = ChartmetricBackfillPlanner().plan(request)
        completed = skipped = failed = rows_written = 0
        failures: list[str] = []
        for task in tasks:
            state_path = self.state_dir / f"{task.task_id}.json"
            output_path = self.output_dir / f"{task.task_id}.parquet"
            state = _read_json(state_path) if resume else {}
            if resume and state.get("status") == "COMPLETE" and output_path.exists():
                skipped += 1
                continue
            _write_json(state_path, {"status": "RUNNING", "task_id": task.task_id})
            try:
                observations = self.client.collect_chart_pages(
                    platform=task.platform,
                    country_code=task.country_code,
                    interval=task.interval,
                    chart_type=task.chart_type,
                    period=task.period,
                    page_size=task.page_size,
                    checkpoint_path=self.checkpoint_dir / f"{task.task_id}.json",
                    on_page=_raw_page_callback(
                        self.state_dir / "raw",
                        self.output_dir / ".parts" / task.task_id,
                        task.task_id,
                    ),
                )
                part_paths = sorted(
                    (self.output_dir / ".parts" / task.task_id).glob("*.parquet")
                )
                if not part_paths:
                    _write_observations(
                        self.output_dir / ".parts" / task.task_id / "000000.parquet",
                        observations,
                    )
                    part_paths = [
                        self.output_dir / ".parts" / task.task_id / "000000.parquet"
                    ]
                _consolidate_observations(output_path, part_paths)
                total_rows = sum(pl.read_parquet(path).height for path in part_paths)
                _write_json(
                    state_path,
                    {
                        "status": "COMPLETE",
                        "task_id": task.task_id,
                        "rows": total_rows,
                        "output": str(output_path),
                    },
                )
                completed += 1
                rows_written += total_rows
            except Exception as error:  # noqa: BLE001 - one failed cell must not stop a backfill
                message = f"{task.task_id}: {error}"
                _write_json(
                    state_path,
                    {"status": "FAILED", "task_id": task.task_id, "error": str(error)},
                )
                failed += 1
                failures.append(message)
        return BackfillSummary(
            total_tasks=len(tasks),
            completed_tasks=completed,
            skipped_tasks=skipped,
            failed_tasks=failed,
            rows_written=rows_written,
            failures=tuple(failures),
        )


def _write_observations(path: Path, observations: tuple[Any, ...]) -> None:
    if not observations:
        return
    records = [
        {
            "provider": row.provider,
            "origin_platform": row.origin_platform,
            "country_code": row.country_code,
            "chart_name": row.chart_name,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "rank": row.rank,
            "track_title": row.track_title,
            "artist": row.artist,
            "native_id": row.native_id,
            "metric_value": str(row.metric_value) if row.metric_value is not None else None,
            "metric_type": row.metric_type,
            "source_artifact": row.source_artifact,
            "source_row_number": row.source_row_number,
            "track_language": row.track_language,
            "raw_fields": json.dumps(row.raw_fields, sort_keys=True, default=str),
        }
        for row in observations
    ]
    frame = pl.DataFrame(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.write_parquet(temporary, compression="zstd")
    temporary.replace(path)


def _write_raw_page(
    raw_dir: Path, task_id: str, offset: int, payload: dict[str, object]
) -> None:
    path = raw_dir / f"{task_id}-{offset:06d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, default=str) + "\n", encoding="utf-8")
    temporary.replace(path)


def _raw_page_callback(
    raw_dir: Path, parts_dir: Path, task_id: str
) -> Callable[[int, dict[str, Any], tuple[Any, ...]], None]:
    def save(offset: int, payload: dict[str, Any], observations: tuple[Any, ...]) -> None:
        _write_raw_page(raw_dir, task_id, offset, payload)
        _write_observations(parts_dir / f"{offset:06d}.parquet", observations)

    return save


def _consolidate_observations(path: Path, part_paths: list[Path]) -> None:
    frames = [pl.read_parquet(part_path) for part_path in part_paths]
    frame = pl.concat(frames, how="vertical_relaxed") if frames else pl.DataFrame()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.write_parquet(temporary, compression="zstd")
    temporary.replace(path)


def consolidate_backfill_observations(output_dir: Path, output_path: Path) -> int:
    paths = sorted(Path(output_dir).glob("*.parquet"))
    if not paths:
        return 0
    frame = pl.concat([pl.read_parquet(path) for path in paths], how="vertical_relaxed")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    frame.write_parquet(temporary, compression="zstd")
    temporary.replace(output_path)
    return frame.height


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _periods(start_date: date, end_date: date, interval: str) -> tuple[date, ...]:
    if start_date > end_date:
        raise ValueError("start_date must not be later than end_date")
    normalized_interval = interval.casefold()
    if normalized_interval not in {"daily", "weekly"}:
        raise ValueError("interval must be 'daily' or 'weekly'")
    step = timedelta(days=7 if normalized_interval == "weekly" else 1)
    result: list[date] = []
    current = start_date
    while current <= end_date:
        result.append(current)
        current += step
    return tuple(result)
