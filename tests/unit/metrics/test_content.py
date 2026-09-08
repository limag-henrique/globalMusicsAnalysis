from chart_observatory.metrics.content import (
    ContentObservation,
    category_exposure,
    category_prevalence,
)


def test_prevalence_counts_a_track_once_but_exposure_counts_appearances() -> None:
    rows = [
        ContentObservation("BR", "violence", "track-a", 1),
        ContentObservation("BR", "violence", "track-a", 2),
        ContentObservation("BR", "violence", "track-b", 3),
        ContentObservation("BR", "joy", "track-b", 4),
    ]
    prevalence = category_prevalence(rows)
    violence = prevalence.filter(prevalence["category"] == "violence").row(0, named=True)
    assert violence["tracks_with_category"] == 2
    assert violence["track_denominator"] == 2
    exposure = category_exposure(rows)
    violence_exposure = exposure.filter(exposure["category"] == "violence").row(0, named=True)
    assert violence_exposure["weighted_exposure"] == 3.0
    assert violence_exposure["observation_weight_denominator"] == 4.0
