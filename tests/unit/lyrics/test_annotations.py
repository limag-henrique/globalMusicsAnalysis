import pytest

from chart_observatory.lyrics.annotations import SemanticAnnotationInput, validate_annotation


def test_semantic_annotations_require_bounded_values() -> None:
    valid = SemanticAnnotationInput("violence", 0.8, 0.9, "manual", "v1", "researcher")
    assert validate_annotation(valid) == valid
    with pytest.raises(ValueError):
        validate_annotation(
            SemanticAnnotationInput("violence", 1.1, 0.9, "manual", "v1", "researcher")
        )
