import polars as pl
import pytest

from chart_observatory.analysis.revision_rankings import build_rankings
from chart_observatory.lyrics.review_protocol import TOPICS

TOPIC = next(iter(TOPICS))


def membership(i, *, validated=True, country="BR", platform="SPOTIFY", applicable="applicable"):
    return dict(country_code=country, year=2025, platform=platform, window="full_year",
                sample="original", candidate_id=f"item-{i}", recording_id=f"recording-{i}"
                if validated else None, text_identity_id=f"edition-{i}",
                normalized_hash=f"hash-{i}", request_key=f"key-{i}", text_validated=validated,
                applicability=applicable, coverage_status="COMPLETE", metric_value=10,
                metric_type="STREAMS" if platform == "SPOTIFY" else "VIEWS")


def classification(i, score):
    return dict(text_identity_id=f"edition-{i}", normalized_hash=f"hash-{i}",
                request_key=f"key-{i}", topic=TOPIC, score=score, classification_status="classified")


def test_missing_lyrics_are_unknown_and_extreme_scenarios_do_not_replace_the_observed_denominator():
    members = pl.DataFrame([membership(1), membership(2), membership(3, validated=False)])
    result = build_rankings(members, pl.DataFrame([classification(1, 2), classification(2, 0)]))
    row = result.filter(pl.col("topic") == TOPIC).row(0, named=True)
    assert row["scored_n"] == 2
    assert row["unknown_n"] == 1
    assert row["observed_proportion"] == 0.5
    assert row["missing_all_absent"] == pytest.approx(1/3)
    assert row["missing_all_present"] == pytest.approx(2/3)
    assert row["primary_proportion"] is None
    assert row["country_rank"] is None


def test_same_request_with_wrong_text_hash_is_not_reused():
    members = pl.DataFrame([membership(1)])
    labels = pl.DataFrame([{**classification(1, 3), "normalized_hash": "different"}])
    row = build_rankings(members, labels).filter(pl.col("topic") == TOPIC).row(0, named=True)
    assert row["scored_n"] == 0
    assert row["observed_proportion"] is None
    assert row["missing_all_absent"] == 0
    assert row["missing_all_present"] == 1


def test_instrumental_is_excluded_not_a_zero_theme():
    members = pl.DataFrame([membership(1), membership(2, validated=False,
                                                   applicable="not_applicable")])
    row = build_rankings(members, pl.DataFrame([classification(1, 2)])).filter(
        pl.col("topic") == TOPIC).row(0, named=True)
    assert row["not_applicable_n"] == 1
    assert row["applicable_n"] == row["scored_n"] == 1
    assert row["observed_proportion"] == 1


def test_ranking_uses_common_platform_and_period_without_combining_streams_and_views():
    selections = {("BR", "SPOTIFY"): range(80),
                  ("AR", "SPOTIFY"): [*range(40), *range(80, 120)],
                  ("BR", "YOUTUBE"): range(80, 160),
                  ("AR", "YOUTUBE"): range(100, 180)}
    members = pl.DataFrame([membership(i, country=country, platform=platform)
                            for (country, platform), ids in selections.items() for i in ids])
    positives = {*range(20), *range(80, 100)}
    labels = pl.DataFrame([classification(i, 2 if i in positives else 0) for i in range(180)])
    rows = build_rankings(members, labels).filter(pl.col("topic") == TOPIC).to_dicts()
    ranks = {(r["country_code"], r["platform"]): r["country_rank"] for r in rows}
    assert ranks == {("BR", "SPOTIFY"): 2, ("AR", "SPOTIFY"): 1,
                     ("BR", "YOUTUBE"): 1, ("AR", "YOUTUBE"): 2}
    assert all(r["scored_n"] == 80 for r in rows)


def test_conflicting_classifications_and_wrong_platform_metrics_are_rejected():
    members = pl.DataFrame([membership(1)])
    with pytest.raises(ValueError, match="ambiguous"):
        build_rankings(members, pl.DataFrame([classification(1, 0), classification(1, 3)]))
    with pytest.raises(ValueError, match="incompatible"):
        build_rankings(members.with_columns(pl.lit("VIEWS").alias("metric_type")),
                       pl.DataFrame([classification(1, 0)]))
