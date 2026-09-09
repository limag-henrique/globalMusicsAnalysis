from datetime import date

import polars as pl

from chart_observatory.corpus.catalog_reconciliation import (
    canonicalize_catalog_lazy,
    reconcile_catalog,
)


def _rows() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "source_observation_key": ["mgd-1", "kaggle-1", "mgd-2", "video-1"],
            "provider": ["MGD", "KAGGLE_DHRUVILDAVE", "MGD", "YOUTUBE_DATA_API"],
            "origin_platform": ["SPOTIFY", "SPOTIFY", "SPOTIFY", "YOUTUBE_VIDEO"],
            "item_kind": ["TRACK", "TRACK", "TRACK", "VIDEO"],
            "market_code": ["BR", "BR", "BR", "BR"],
            "chart_family": ["TOP_200", "TOP_200", "TOP_200", "YOUTUBE_VIDEO_MOST_POPULAR"],
            "period_start": [date(2021, 1, 1)] * 4,
            "period_end": [date(2021, 1, 1)] * 4,
            "rank": [1, 3, 2, 1],
            "track_title": ["Song", "Song", "Same title", "Song video"],
            "artist": ["Artist", "Artist", "Artist", "Channel"],
            "native_id": [
                "3n3Ppam7vgaVa1iaRUc9Lp",
                "https://open.spotify.com/track/3n3Ppam7vgaVa1iaRUc9Lp",
                "different-id",
                "video-id",
            ],
            "metric_type": ["STREAMS", "STREAMS", "STREAMS", "VIEWS"],
            "metric_value": [100.0, 80.0, 100.0, 200.0],
        }
    )


def test_reconciliation_assigns_exact_cross_source_identity_and_preserves_rows() -> None:
    canonical, conflicts = reconcile_catalog(_rows())

    assert canonical.height == 4
    matched = canonical.filter(pl.col("source_observation_key").is_in(["mgd-1", "kaggle-1"]))
    assert matched["canonical_track_id"].n_unique() == 1
    assert set(matched["resolution_status"].to_list()) == {"MATCHED_EXACT"}
    assert (
        canonical.filter(pl.col("item_kind") == "VIDEO")["canonical_track_id"].to_list()
        == [None]
    )
    assert (
        canonical["source_observation_key"].to_list()
        == _rows()["source_observation_key"].to_list()
    )
    assert conflicts.height == 1
    assert conflicts["conflict_status"].to_list() == ["SOURCE_CONFLICT"]


def test_reconciliation_does_not_resolve_title_artist_collision_without_id_evidence() -> None:
    rows = _rows().with_columns(
        pl.when(pl.col("source_observation_key") == "mgd-2")
        .then(pl.lit("Song"))
        .otherwise(pl.col("track_title"))
        .alias("track_title")
    )

    canonical, conflicts = reconcile_catalog(rows)

    unresolved = canonical.filter(pl.col("source_observation_key") == "mgd-2")
    assert unresolved["canonical_track_id"].to_list() == [None]
    assert unresolved["resolution_status"].to_list() == ["UNRESOLVED"]
    assert conflicts.height == 1


def test_lazy_canonicalization_adds_identity_without_collecting_conflict_joins() -> None:
    result = canonicalize_catalog_lazy(_rows().lazy()).collect()

    assert result.filter(pl.col("source_observation_key") == "mgd-1")[
        "resolution_status"
    ].to_list() == ["MATCHED_EXACT"]
    assert result.height == _rows().height
