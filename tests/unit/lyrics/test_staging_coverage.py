import pytest

from chart_observatory.lyrics.staging_coverage import summarize_coverage


def record(key, country, year, position, *, text=False, provisional=False):
    return dict(
        candidate_id=key,
        text_sha256="saved" if text else None,
        audit={},
        payload={
            "chart_bindings": [
                dict(
                    country_code=country,
                    year=year,
                    position=position,
                    selection_status="PROVISIONAL_OBSERVED_PERIODS"
                    if provisional
                    else "CALENDAR_ELIGIBLE",
                )
            ]
        },
    )


def test_missing_rankings_are_distinct_from_missing_lyrics_and_shared_song_counts_positions():
    records = [
        record("same-song", "BR", 2020, 1, text=True),
        record("same-song", "BR", 2021, 1, text=True),
        record("gap", "BR", 2021, 2, provisional=True),
    ]
    result = summarize_coverage(records, {"BR": 2, "IN": 1}, [2020, 2021])
    cells = {(r["country_code"], r["year"]): r for r in result["cells"]}
    assert cells["BR", 2020]["missing_ranking_positions"] == [2]
    assert cells["BR", 2020]["missing_text_positions"] == []
    assert cells["BR", 2021]["missing_text_positions"] == [2]
    assert cells["BR", 2021]["provisional_positions"] == 1
    assert result["summary"]["unique_candidates"] == 2
    assert result["summary"]["unique_candidates_with_text"] == 1
    assert result["summary"]["unique_candidates_missing_text"] == 1
    assert result["missing_text_candidates"] == [
        dict(candidate_id="gap", selected_memberships=1, best_position=2)
    ]
    assert result["summary"]["positions_with_text"] == 2
    assert result["summary"]["empty_cells"] == 2
    assert not result["summary"]["lyrics_validated"]


def test_conflicting_identity_at_rank_cannot_look_complete_and_over_quota_is_rejected():
    records = [record("one", "BR", 2020, 1), record("other", "BR", 2020, 1)]
    result = summarize_coverage(records, {"BR": 1}, [2020])
    assert result["cells"][0]["conflicting_ranking_positions"] == [1]
    assert not result["cells"][0]["rank_selection_complete"]
    with pytest.raises(ValueError, match="outside"):
        summarize_coverage([record("overflow", "BR", 2020, 2)], {"BR": 1}, [2020])


def test_recovery_inventory_deduplicates_shared_missing_candidates():
    rows = [record("shared", "BR", 2020, 2), record("shared", "BR", 2021, 2),
            record("single", "BR", 2020, 1)]
    result = summarize_coverage(rows, {"BR": 2}, [2020, 2021])
    assert result["summary"]["missing_text_positions"] == 3
    assert result["summary"]["unique_candidates_missing_text"] == 2
    assert result["missing_text_candidates"] == [
        dict(candidate_id="shared", selected_memberships=2, best_position=2),
        dict(candidate_id="single", selected_memberships=1, best_position=1),
    ]
