import hashlib
import json

import pytest

from chart_observatory.ingestion.import_quotas import (
    apply_native_display_metadata,
    load_quotas,
    provisional_selection,
    recovery_targets,
    select_quota_candidates,
)


def test_native_metadata_correction_preserves_rank_and_rejects_other_track_or_tampering(tmp_path):
    path = tmp_path / "proof.json"
    proof = dict(
        status=200,
        source_url="https://open.spotify.com/embed/track/native",
        metadata=dict(uri="spotify:track:native", title="Song", artist="Correct Artist"),
    )
    raw = json.dumps(proof).encode()
    path.write_bytes(raw)
    refs = {
        "SPOTIFY:native": dict(
            evidence_file=str(path), evidence_sha256=hashlib.sha256(raw).hexdigest()
        )
    }
    row = dict(
        candidate_id="SPOTIFY:native",
        title="Song",
        artist="Truncated Artist",
        country_code="RU",
        year=2021,
        position=42,
        metric_value=123,
    )
    apply_native_display_metadata([row], refs)
    assert row["artist"] == "Correct Artist"
    assert row["original_display_metadata"]["artist"] == "Truncated Artist"
    assert (row["position"], row["metric_value"], row["candidate_id"]) == (
        42,
        123,
        "SPOTIFY:native",
    )
    with pytest.raises(ValueError, match="another or unknown"):
        apply_native_display_metadata([row], {"SPOTIFY:another": refs["SPOTIFY:native"]})
    path.write_text("corrupted", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        apply_native_display_metadata([row], refs)


def test_batched_native_proof_must_still_match_each_track_uri(tmp_path):
    proof = dict(
        status=200,
        source_url="https://open.spotify.com/embed/track/one",
        metadata=dict(uri="spotify:track:one", title="Song", artist="Artist"),
    )
    raw = json.dumps({"SPOTIFY:one": proof}).encode()
    path = tmp_path / "batch.json"
    path.write_bytes(raw)
    ref = dict(
        evidence_file=str(path),
        evidence_sha256=hashlib.sha256(raw).hexdigest(),
        evidence_key="SPOTIFY:one",
    )
    row = dict(candidate_id="SPOTIFY:one", title="Old name", artist="Artist", position=1)
    apply_native_display_metadata([row], {"SPOTIFY:one": ref})
    assert row["title"] == "Song"
    with pytest.raises(ValueError, match="another or unknown"):
        apply_native_display_metadata([row], {"SPOTIFY:another": ref})


def test_provisional_respects_quota_excludes_bad_sources_and_preserves_label():
    ranks, coverage = chart("BR", "SPOTIFY", 500, complete=False)
    selected = provisional_selection(ranks, [coverage], {"BR": 230}, [])
    assert len(selected) == 230
    assert {r["selection_status"] for r in selected} == {"PROVISIONAL_OBSERVED_PERIODS"}
    targets = recovery_targets(selected)
    assert targets[0]["chart_bindings"][0]["selection_status"] == "PROVISIONAL_OBSERVED_PERIODS"
    assert provisional_selection(ranks, [coverage], {"BR": 230}, ranks[:1]) == []
    coverage["coverage_status"] = "CONFLICT_OR_INVALID"
    assert provisional_selection(ranks, [coverage], {"BR": 230}, []) == []


def chart(country, platform, count, year=2025, complete=True):
    rows = [
        dict(
            country_code=country,
            year=year,
            platform=platform,
            provider=platform,
            position=i,
            candidate_id=f"{platform}:{i}",
            title=f"Song {i}",
            artist="A",
            metric_value=10000 - i,
        )
        for i in range(1, count + 1)
    ]
    coverage = dict(
        country_code=country,
        year=year,
        platform=platform,
        provider=platform,
        coverage_status="COMPLETE" if complete else "INCOMPLETE",
        collected_periods=365 if complete else 1,
        expected_periods=365,
    )
    return rows, coverage


def test_variable_quotas_exceed_legacy_200_and_keep_country_bindings():
    br, br_cov = chart("BR", "SPOTIFY", 500)
    india, india_cov = chart("IN", "SPOTIFY", 500)
    result = select_quota_candidates(
        br + india, [br_cov, india_cov], {"BR": 230, "IN": 440}, years=[2025]
    )
    assert len(result["selections"]) == 670
    assert [r["selected_items"] for r in result["coverage"]] == [230, 440]
    targets = recovery_targets(result["selections"])
    assert len(targets) == 440
    assert len(targets[0]["chart_bindings"]) == 2
    assert all(r["track_id"] is None and r["not_for_paid_submission"] for r in targets)


def test_one_complete_source_and_no_silent_quota_fill_from_other_platform():
    spotify, s_cov = chart("BR", "SPOTIFY", 100)
    youtube, y_cov = chart("BR", "YOUTUBE", 500)
    result = select_quota_candidates(spotify + youtube, [s_cov, y_cov], {"BR": 230}, years=[2025])
    assert len(result["selections"]) == 100
    assert result["coverage"][0]["quota_shortfall"] == 130
    assert {r["platform"] for r in result["selections"]} == {"SPOTIFY"}
    s_cov["coverage_status"] = "INCOMPLETE"
    result = select_quota_candidates(spotify + youtube, [s_cov, y_cov], {"BR": 230}, years=[2025])
    assert {r["platform"] for r in result["selections"]} == {"YOUTUBE"}


def test_incomplete_calendars_and_absent_years_remain_deficits():
    rows, coverage = chart("BR", "SPOTIFY", 500, complete=False)
    result = select_quota_candidates(rows, [coverage], {"BR": 230}, years=[2024, 2025])
    assert result["selections"] == []
    assert [r["quota_shortfall"] for r in result["coverage"]] == [230, 230]


def test_conflicting_ranks_or_mirrored_providers_fail_closed():
    rows, coverage = chart("BR", "SPOTIFY", 3)
    with pytest.raises(ValueError, match="contiguous"):
        select_quota_candidates(rows + rows[:1], [coverage], {"BR": 230}, years=[2025])
    with pytest.raises(ValueError, match="multiple providers"):
        select_quota_candidates(rows, [coverage, coverage], {"BR": 230}, years=[2025])


def test_quota_file_rejects_duplicate_countries(tmp_path):
    path = tmp_path / "quotas.csv"
    path.write_text("country_code,quota_per_year_main\nBR,230\nBR,230\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_quotas(path)
