import pytest

from chart_observatory.ui.taxonomy import CONTENT_TAXONOMY, level_label, taxonomy_codes


def test_taxonomy_keeps_the_nine_dimensions_and_exact_labels() -> None:
    assert taxonomy_codes() == (
        "sexual_explicitness",
        "objectification",
        "transactional_sex",
        "materialism",
        "drugs",
        "crime",
        "violence",
        "romantic_affection",
        "heartbreak",
    )
    assert CONTENT_TAXONOMY[0].levels == ("ausente", "sugestivo", "explícito", "gráfico")
    assert CONTENT_TAXONOMY[2].levels == ("ausente", "—", "presente", "central")
    assert CONTENT_TAXONOMY[-1].levels == ("ausente", "secundário", "relevante", "central")


def test_taxonomy_distinguishes_unannotated_from_zero() -> None:
    assert level_label("violence", None) == "Sem anotação"
    assert level_label("violence", 0) == "ausente"
    with pytest.raises(ValueError):
        level_label("violence", 4)
    with pytest.raises(ValueError):
        level_label("violence", True)


def test_taxonomy_rejects_unknown_dimension() -> None:
    with pytest.raises(KeyError):
        level_label("unknown", 0)
