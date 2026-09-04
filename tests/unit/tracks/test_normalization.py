import pytest

from chart_observatory.domain.errors import DomainValidationError
from chart_observatory.tracks.normalization import normalize_isrc


def test_isrc_is_normalized_without_losing_semantics() -> None:
    assert normalize_isrc("br-abc-21-00001") == "BRABC2100001"


@pytest.mark.parametrize("value", ["", "BR123", "BRABC21@0001"])
def test_invalid_isrc_is_rejected(value: str) -> None:
    with pytest.raises(DomainValidationError):
        normalize_isrc(value)
