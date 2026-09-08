from dataclasses import dataclass


@dataclass(frozen=True)
class SemanticAnnotationInput:
    category: str
    value: float
    confidence: float | None
    method: str
    model_version: str
    source: str
    review_status: str = "UNREVIEWED"


def validate_annotation(annotation: SemanticAnnotationInput) -> SemanticAnnotationInput:
    if not annotation.category.strip():
        raise ValueError("semantic annotation category is required")
    if not 0 <= annotation.value <= 1:
        raise ValueError("semantic annotation value must be between 0 and 1")
    if annotation.confidence is not None and not 0 <= annotation.confidence <= 1:
        raise ValueError("semantic annotation confidence must be between 0 and 1")
    return annotation
