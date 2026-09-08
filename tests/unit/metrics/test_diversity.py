from pytest import approx

from chart_observatory.metrics.diversity import genre_diversity, jensen_shannon


def test_diversity_metrics_are_normalized_and_concentration_is_explicit() -> None:
    metrics = genre_diversity({"pop": 1, "rap": 1})
    assert metrics.hhi == approx(0.5)
    assert metrics.simpson_diversity == approx(0.5)
    assert jensen_shannon({"pop": 1}, {"rap": 1}) > 0
