from chart_observatory.ui.pages.observations import format_observation_rows


def test_observation_rows_show_human_classification_state() -> None:
    rows = format_observation_rows(
        [
            {
                "track_title": "Song",
                "artist": "Artist",
                "rank": 1,
                "metric_value": 12345,
                "classification_state": "UNANNOTATED",
            }
        ]
    )

    assert rows[0]["Classificação"] == "Sem anotação"
    assert rows[0]["Valor da métrica"] == 12345


def test_observation_rows_preserve_zero_metric_value() -> None:
    rows = format_observation_rows([{"metric_value": 0}])

    assert rows[0]["Valor da métrica"] == 0
