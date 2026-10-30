import pytest

from chart_observatory.lyrics.annual_eligibility import select_eligible


def candidate(rank, recording=None):
    return dict(country_code="BR", year=2025, platform="SPOTIFY", window="full_year",
                position=rank, candidate_id=f"spotify:{rank}", recording_id=recording,
                title=f"Song {rank}", artist="Artist", coverage_status="COMPLETE")


def test_original_positions_are_preserved_and_reserve_requires_hash_bound_integrity():
    rows = [candidate(i, f"recording-{i}") for i in range(1, 83)]
    evidence = [dict(candidate_id=f"spotify:{i}", recording_id=f"recording-{i}",
                     document_id=f"doc-{i}", lyrics_hash="a" * 64,
                     identity_verified=True, integrity_verified=True,
                     method="human_audio_verification", evidence_url="https://artist.test/lyrics",
                     evidence_sha256="b" * 64, verified_at="2026-10-25")
                for i in range(2, 83)]
    current = {f"doc-{i}": (f"recording-{i}", "a" * 64) for i in range(2, 83)}
    result = select_eligible(rows, evidence, current_documents=current)
    assert len(result["original_top80"]) == 80
    assert result["original_top80"][0]["eligibility_reason"] == "validation_missing"
    assert [r["position"] for r in result["eligible"]] == list(range(2, 82))
    assert result["coverage"][0]["original_losses"] == 1
    assert result["coverage"][0]["reserve_entries"] == 1
    assert len(result["classification_queue"]) == 80


@pytest.mark.parametrize("change,reason", [
    ({"identity_verified": False}, "identity_unverified"),
    ({"integrity_verified": False}, "integrity_unverified"),
    ({"lyrics_hash": "c" * 64}, "validation_binding_mismatch"),
    ({"method": "two_websites_agree"}, "integrity_evidence_missing"),
    ({"evidence_url": ""}, "integrity_evidence_missing"),
])
def test_scrape_success_or_identity_alone_never_validates_integrity(change, reason):
    entry = dict(candidate_id="spotify:1", recording_id="one", document_id="doc",
                 lyrics_hash="a" * 64, identity_verified=True, integrity_verified=True,
                 method="official_transcription", evidence_url="https://artist.test/lyrics",
                 evidence_sha256="b" * 64, verified_at="2026-10-25")
    result = select_eligible([candidate(1, "one")], [{**entry, **change}],
                             current_documents={"doc": ("one", "a" * 64)})
    assert result["original_top80"][0]["eligibility_reason"] == reason
    assert result["classification_queue"] == []


def test_shared_recording_is_queued_once_and_existing_hash_can_be_reused():
    entry = dict(candidate_id="spotify:1", recording_id="one", document_id="doc",
                 lyrics_hash="a" * 64, identity_verified=True, integrity_verified=True,
                 method="official_transcription", evidence_url="https://artist.test/lyrics",
                 evidence_sha256="b" * 64, verified_at="2026-10-25")
    rows = [candidate(1, "one"), {**candidate(1, "one"), "country_code": "AR"}]
    args = dict(current_documents={"doc": ("one", "a" * 64)})
    result = select_eligible(rows, [entry], **args)
    assert len(result["eligible"]) == 2
    assert len(result["classification_queue"]) == 1
    assert len(result["classification_queue"][0]["memberships"]) == 2
    reused = select_eligible(rows, [entry], **args,
                             reusable_classifications=[("one", "a" * 64)])
    assert reused["classification_queue"] == []
    blocked = select_eligible(rows, [entry], **args, blocked=[("doc", "a" * 64)])
    assert blocked["eligible"] == []
