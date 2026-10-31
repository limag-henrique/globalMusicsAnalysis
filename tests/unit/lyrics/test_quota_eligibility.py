from chart_observatory.lyrics.quota_eligibility import prepare_quota_review


def chart(country, quota, year=2021):
    return [
        dict(
            country_code=country,
            year=year,
            platform="SPOTIFY",
            quota_main=quota,
            position=i,
            candidate_id=f"SPOTIFY:{country}{i}",
            coverage_status="COMPLETE",
        )
        for i in range(1, quota + 1)
    ]


def proof(candidate, recording="recording", digest="a" * 64):
    return dict(
        candidate_id=candidate,
        recording_id=recording,
        document_id=recording + digest,
        lyrics_hash=digest,
        identity_verified=True,
        integrity_verified=True,
        method="human_audio_verification",
        evidence_url="https://example.org/review",
        evidence_sha256="b" * 64,
        verified_at="2026-10-31",
    )


def test_country_quotas_above_80_preserve_positions_without_promoting_reserves():
    rows = chart("BR", 230) + chart("IN", 440)
    result = prepare_quota_review(rows, [], current_documents={})
    assert len(result["ranked_positions"]) == 670
    assert [r["deficit"] for r in result["coverage"]] == [230, 440]
    assert not result["prepared_candidates"] and not result["classification_ready"]


def test_missing_country_year_remains_in_coverage_with_full_deficit():
    result = prepare_quota_review(
        [],
        [],
        current_documents={},
        expected_cells=[dict(country_code="AD", year=2018, quota_main=100)],
    )
    assert result["coverage"][0]["deficit"] == 100
    assert result["coverage"][0]["selected_positions"] == 0
    assert result["coverage"][0]["reasons"] == {"ranking_calendar_unavailable": 100}


def test_deduplicates_reviewed_native_bindings_and_rejects_changed_document_hash():
    rows = chart("BR", 1) + chart("IN", 1)
    evidence = [proof(r["candidate_id"]) for r in rows]
    docs = {evidence[0]["document_id"]: ("recording", "a" * 64)}
    result = prepare_quota_review(rows, evidence, current_documents=docs)
    assert len(result["prepared_candidates"]) == 1
    assert len(result["prepared_candidates"][0]["memberships"]) == 2
    assert result["prepared_candidates"][0]["not_for_paid_submission"]
    result = prepare_quota_review(
        rows, evidence, current_documents={evidence[0]["document_id"]: ("recording", "c" * 64)}
    )
    assert not result["prepared_candidates"]


def test_conflicting_texts_or_provisional_calendars_never_prepare_paid_work():
    rows = chart("BR", 1) + chart("IN", 1)
    evidence = [proof(rows[0]["candidate_id"]), proof(rows[1]["candidate_id"], digest="c" * 64)]
    docs = {p["document_id"]: (p["recording_id"], p["lyrics_hash"]) for p in evidence}
    result = prepare_quota_review(rows, evidence, current_documents=docs)
    assert not result["prepared_candidates"]
    assert {r["eligibility_reason"] for r in result["ranked_positions"]} == {
        "recording_has_conflicting_validated_texts"
    }
    rows[0]["selection_status"] = "PROVISIONAL_OBSERVED_PERIODS"
    rows[0]["not_for_paid_submission"] = True
    result = prepare_quota_review(rows[:1], evidence[:1], current_documents=docs)
    assert result["ranked_positions"][0]["eligibility_reason"] == "provisional_calendar"
