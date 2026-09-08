from datetime import date, timedelta
from pathlib import Path

import polars as pl

from chart_observatory.exports.analytical import build_turnover_dataset


def test_turnover_dataset_materializes_adjacent_period_metrics(tmp_path: Path) -> None:
    rows = []
    for period, tracks in enumerate((("a", "b"), ("a", "c"))):
        for rank, track in enumerate(tracks, 1):
            rows.append(
                {
                    "country_code": "BR",
                    "period_start": date(2020, 1, 1) + timedelta(days=period),
                    "native_id": track,
                    "rank": rank,
                }
            )
    source = tmp_path / "source.parquet"
    pl.DataFrame(rows).write_parquet(source)
    result = build_turnover_dataset(source, top_n=2)
    assert result.height == 1
    assert result["new_entries"].to_list() == [1]
    assert result["exits"].to_list() == [1]
    assert result["jaccard"].to_list() == [1 / 3]
