import polars as pl

from chart_observatory.ui.pages.classification import (
    classification_form_values,
    profile_display_rows,
)


def test_empty_classification_form_uses_none_for_every_dimension() -> None:
    values = classification_form_values(None)

    assert len(values) == 9
    assert set(values.values()) == {None}


def test_profile_display_rows_preserve_zero_and_denominator() -> None:
    rows = profile_display_rows(
        pl.DataFrame(
            {
                "country_code": ["BR"],
                "category": ["violence"],
                "classified_track_count": [4],
                "prevalence": [0.0],
                "mean_score": [0.0],
            }
        )
    )

    assert rows == [
        {
            "Mercado": "BR",
            "Dimensão": "violence",
            "Tracks classificadas": 4,
            "Prevalência": "0,0%",
            "Média": "0,00/3",
        }
    ]
