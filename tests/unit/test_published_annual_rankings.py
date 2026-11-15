import pytest

from chart_observatory.research_rankings import verify_published_annual


def rows():
    return [
        dict(
            country_code="GB",
            year=2018,
            platform="NATIONAL",
            provider="TEST",
            period_start="2018-01-01",
            period_end="2018-12-31",
            position=p,
            candidate_id=f"TEST:{p}",
            title=f"Song {p}",
            artist="Artist",
        )
        for p in (1, 2)
    ]


def check(data, **overrides):
    args = dict(
        country_code="GB",
        year=2018,
        platform="NATIONAL",
        provider="TEST",
        quota=2,
        expected_depth=2,
        period_start="2018-01-01",
        period_end="2018-12-31",
    )
    args.update(overrides)
    return verify_published_annual(data, **args)


def test_native_positions_do_not_invent_metrics():
    result = check(rows())
    assert result["approved"]
    assert result["rows"][0]["metric_value"] is None
    assert result["scientific_approval"] is False


def test_insufficient_depth_does_not_fill_quota():
    assert "published_depth_below_quota" in check(rows(), quota=3)["reasons"]


def test_conflicting_position_rejected():
    data = rows()
    assert not check([*data, {**data[0], "candidate_id": "different"}])["approved"]


def test_gap_and_duplicate_candidate_rejected():
    assert not check(rows()[:1])["approved"]
    data = rows()
    data[1]["candidate_id"] = data[0]["candidate_id"]
    assert "published_candidate_repeated" in check(data)["reasons"]


def test_scope_and_ties_rejected():
    assert not check([{**r, "year": 2019} for r in rows()])["approved"]
    assert not check([{**r, "tie_group": ["a", "b"]} for r in rows()])["approved"]


def test_publication_after_cutoff_rejected():
    with pytest.raises(ValueError, match="outside"):
        check(rows(), year=2026, period_start="2026-01-01", period_end="2026-12-31")
