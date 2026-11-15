import pytest

from chart_observatory.ingestion.source_coverage import normalize_source_coverage


def _row(country_code, year):
    return {
        "country_code": country_code,
        "year": year,
        "platform": "SPOTIFY",
        "provider": "TEST",
        "expected_periods": 365,
        "collected_periods": 365,
        "coverage_status": "COMPLETE",
    }


def test_normalizes_multiple_source_coverage_lists():
    first = [_row("IL", 2021)]
    second = [_row("RU", 2021)]

    result = normalize_source_coverage(first, second, [])

    assert result == first + second
    assert result[0] is not first[0]


@pytest.mark.parametrize("invalid", [{"country_code": "IL"}, "country_code", None])
def test_rejects_non_list_source_coverage(invalid):
    with pytest.raises(TypeError, match="must be a list"):
        normalize_source_coverage(invalid)


@pytest.mark.parametrize("invalid_row", ["IL", 2021, None, ["IL", 2021]])
def test_rejects_non_object_coverage_rows(invalid_row):
    with pytest.raises(TypeError, match=r"source_coverage\[0\]\[0\] must be an object"):
        normalize_source_coverage([invalid_row])
