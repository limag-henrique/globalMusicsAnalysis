from chart_observatory.metadata.taxonomy import normalize_genre, normalize_language


def test_genre_normalization_preserves_scientific_bucket() -> None:
    assert normalize_genre("baile funk") == "FUNK_BR"
    assert normalize_genre("Brazilian Funk") == "FUNK_BR"
    assert normalize_genre("melodic rap") == "RAP_HIPHOP"


def test_language_normalization_supports_iso_like_aliases() -> None:
    assert normalize_language("pt-BR") == "pt"
    assert normalize_language("jpn") == "ja"
