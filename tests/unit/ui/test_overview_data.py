from pathlib import Path

import polars as pl
from streamlit.testing.v1 import AppTest

from chart_observatory.ui.data import load_youtube_summary, manifest_metric_labels


def test_manifest_metric_labels_expose_completed_corpus_v1_numbers() -> None:
    """Catch a regression that presents frozen Corpus v1 metrics incorrectly."""
    labels = manifest_metric_labels(
        {
            "status": "FROZEN",
            "observations": {"rows": 21257472},
            "total_cells": 68,
            "eligible_cells": 55,
            "manifest_sha256": "b" * 64,
            "analytical_datasets": [
                {"path": "track_master.parquet", "rows": 126213},
            ],
        }
    )

    assert labels["observations"] == "21.257.472"
    assert labels["tracks"] == "126.213"
    assert labels["markets"] == "55/68 elegíveis"
    assert labels["freeze"] == "FROZEN"


def test_youtube_summary_counts_distinct_native_videos(tmp_path: Path) -> None:
    """Catch counting repeated regional video observations as unique videos."""
    path = tmp_path / "youtube.parquet"
    pl.DataFrame(
        {
            "native_id": ["video-1", "video-1", "video-2"],
            "country_code": ["BR", "US", "BR"],
            "view_count": [10, 20, 30],
        }
    ).write_parquet(path)

    summary = load_youtube_summary(path)

    assert summary.observations == 3
    assert summary.markets == 2
    assert summary.videos == 2


def test_overview_renders_youtube_corpus_counts_and_boundary_marker() -> None:
    """Catch replacing the distinct-video corpus count or its semantic boundary."""
    app = AppTest.from_file(Path(__file__).parents[3] / "src/chart_observatory/ui/app.py")

    app.run(timeout=10)

    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Observações"] == "3.037"
    assert metrics["Regiões"] == "111"
    assert metrics["Vídeos"] == "1.678"
    assert "NOT_YOUTUBE_MUSIC_TOP_SONGS" in [caption.value for caption in app.caption]
