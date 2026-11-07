from concurrent.futures import ThreadPoolExecutor

import pytest

from chart_observatory.lyrics.review_protocol import TOPICS
from chart_observatory.lyrics.revision_protocol import (
    ClassificationKey,
    RevisionRegistry,
    audit_text_chain,
    normalize_text,
    prepare_text_requests,
)


def key(**overrides):
    return ClassificationKey(
        **{
            "text_identity_id": "edition-one",
            "normalized_hash": "a" * 64,
            "normalization_version": "lyrics-normalization-v1",
            "rubric_version": "rubric-v2-draft",
            "prompt_version": "prompt-v4-draft",
            "model_id": "test-model",
            "configuration": {
                "resolved": True,
                "temperature": 0,
                "max_output_tokens": 1024,
                "thinking": "MINIMAL",
            },
            **overrides,
        }
    )


def test_normalization_retains_words_sections_case_and_repeated_refrains():
    result = normalize_text("[Refrão]\r\nAmor!\r\nAmor!\r\n\r\nNão é amor.\r\n")
    assert result.text == "[Refrão]\nAmor!\nAmor!\n\nNão é amor."
    assert result.original_hash != result.normalized_hash
    assert normalize_text(result.text).normalized_hash == result.normalized_hash


def test_formatting_does_not_create_a_new_text_signature_or_remove_repetitions():
    plain = "First verse\n\n[Refrão]\nAmor!\nAmor!"
    formatted = "  First\t verse \r\n\r\n\r\n[Refrão]  \r\n Amor! \r\n Amor! \r\n"
    assert normalize_text(formatted).text == plain
    assert normalize_text(formatted).normalized_hash == normalize_text(plain).normalized_hash


def test_unresolved_configuration_cannot_produce_a_reuse_key():
    with pytest.raises(ValueError, match="resolved"):
        key(configuration={"resolved": False, "temperature": 0})


@pytest.mark.parametrize(
    "change",
    [
        {"text_identity_id": "edition-clean"},
        {"normalized_hash": "b" * 64},
        {"normalization_version": "v2"},
        {"rubric_version": "other"},
        {"prompt_version": "other"},
        {"model_id": "other"},
        {
            "configuration": {
                "resolved": True,
                "temperature": 0,
                "max_output_tokens": 2048,
                "thinking": "MINIMAL",
            }
        },
    ],
)
def test_every_protocol_component_changes_reuse_key(change):
    assert key().digest != key(**change).digest


def test_configuration_order_does_not_change_the_key():
    assert (
        key().digest
        == key(
            configuration={
                "resolved": True,
                "thinking": "MINIMAL",
                "max_output_tokens": 1024,
                "temperature": 0,
            }
        ).digest
    )


def test_only_one_concurrent_reservation_and_human_adjudication_needs_no_provider(tmp_path):
    registry = RevisionRegistry(tmp_path / "registry.sqlite")
    registry.register_edition(
        "edition-one",
        "a" * 64,
        "lyrics-normalization-v1",
        identity_confirmed=True,
        integrity_validated=True,
        evidence={"reference": "local-test-evidence"},
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        owners = list(pool.map(lambda _: registry.reserve(key()), range(2)))
    assert sum(owner is not None for owner in owners) == 1
    owner = next(owner for owner in owners if owner)
    registry.complete(
        key(),
        owner,
        {"classification_status": "classified", "scores": dict.fromkeys(TOPICS, 0)},
        method="human_adjudication",
    )
    assert registry.reserve(key()) is None
    assert registry.result(key())["method"] == "human_adjudication"


def test_unvalidated_edition_cannot_be_reserved(tmp_path):
    registry = RevisionRegistry(tmp_path / "registry.sqlite")
    with pytest.raises(ValueError, match="validated"):
        registry.reserve(key())


def test_unknown_provider_outcome_does_not_release_reservation(tmp_path):
    registry = RevisionRegistry(tmp_path / "registry.sqlite")
    registry.register_edition(
        "edition-one",
        "a" * 64,
        "lyrics-normalization-v1",
        identity_confirmed=True,
        integrity_validated=True,
        evidence={"reference": "test"},
    )
    owner = registry.reserve(key())
    registry.mark_outcome_unknown(key(), owner)
    assert RevisionRegistry(registry.path).reserve(key()) is None


def test_preparation_reuses_adjudication_and_omits_market_data_from_model_input(tmp_path):
    registry = RevisionRegistry(tmp_path / "registry.sqlite")
    normalized = normalize_text("Original words.\nOriginal words.")
    row = dict(
        text_identity_id="edition-one",
        normalized_hash=normalized.normalized_hash,
        normalization_version=normalized.version,
        text=normalized.text,
        identity_confirmed=True,
        integrity_validated=True,
        text_language_role="original",
        language="en",
        memberships=[{"country": "BR"}],
        country="BR",
        popularity=1,
    )
    registry.register_edition(
        "edition-one",
        normalized.normalized_hash,
        normalized.version,
        identity_confirmed=True,
        integrity_validated=True,
        evidence={"reference": "test"},
    )
    profile = dict(
        rubric_version="rubric-v2-draft",
        prompt_version="prompt-v4-draft",
        model_id="test-model",
        configuration={"resolved": True, "temperature": 0},
    )
    result = prepare_text_requests(
        [row, {**row, "memberships": [{"country": "AR"}]}], profile, registry
    )
    assert len(result["requests"]) == 1
    request = result["requests"][0]
    assert request["model_input"] == {"text": normalized.text, "language": "en"}
    signature = ClassificationKey(**request["signature"])
    owner = registry.reserve(signature)
    registry.complete(
        signature,
        owner,
        {"classification_status": "classified", "scores": dict.fromkeys(TOPICS, 0)},
        method="human_adjudication",
    )
    reused = prepare_text_requests([row], profile, registry)
    assert reused["requests"] == []
    assert reused["reused_keys"] == [signature.digest]


def test_missing_or_changed_render_and_request_text_do_not_pass_chain_audit():
    text = "First verse.\nRefrain.\nRefrain."
    digest = normalize_text(text).normalized_hash
    assert audit_text_chain(digest, stored=text)["verified"] is False
    result = audit_text_chain(digest, stored=text, presented="Refrain.", sent=text)
    assert result["mismatched_stages"] == ["presented"]
    assert audit_text_chain(digest, stored=text, presented=text, sent=text)["verified"] is True


def test_same_names_do_not_merge_platform_identities_and_derived_ids_are_not_native(tmp_path):
    registry = RevisionRegistry(tmp_path / "registry.sqlite")
    claims = [
        {
            "claim_id": str(i),
            "platform": "SPOTIFY",
            "native_id": str(i),
            "metadata": {"title": "Same", "artist": "Same"},
            "evidence": {"artifact": "test"},
        }
        for i in range(2)
    ]
    registry.record_pending_claims(claims)
    with registry.connect() as conn:
        assert conn.execute("SELECT count(*) FROM platform_identity_claims").fetchone()[0] == 2
        assert conn.execute("SELECT count(*) FROM recordings").fetchone()[0] == 0
    with pytest.raises(ValueError, match="derived"):
        registry.record_pending_claims([{**claims[0], "native_id": "web-derived:123"}])


@pytest.mark.parametrize(
    "field,value",
    [
        ("resolved_model_version", "model@new"),
        ("prompt_template", "New instructions"),
        ("output_schema", {"type": "array"}),
        ("rubric_version", "new-rubric"),
        ("prompt_version", "new-prompt"),
        ("preprocessing_version", "new-preprocessor"),
        ("protocol_version", "new-protocol"),
        ("generation_configuration", {"temperature": 1}),
    ],
)
def test_complete_execution_profile_invalidates_every_scientific_input(field, value):
    from chart_observatory.lyrics.revision_protocol import execution_profile

    inputs = dict(
        model_id="model",
        resolved_model_version="model@fixed",
        prompt_template="Instructions",
        output_schema={"type": "object"},
        rubric_version="rubric",
        prompt_version="prompt",
        preprocessing_version="prep",
        protocol_version="protocol",
        generation_configuration={"temperature": 0},
    )
    first = key(**execution_profile(**inputs))
    second = key(**execution_profile(**{**inputs, field: value}))
    assert first.digest != second.digest


def test_language_context_changes_prepared_signature(tmp_path):
    registry = RevisionRegistry(tmp_path / "language-signature.sqlite")
    normalized = normalize_text("Synthetic words with an ambiguous language cue")
    base = dict(
        text_identity_id="edition",
        normalized_hash=normalized.normalized_hash,
        normalization_version=normalized.version,
        text=normalized.text,
        identity_confirmed=True,
        integrity_validated=True,
        text_language_role="original",
    )
    profile = dict(
        rubric_version="r", prompt_version="p", model_id="m", configuration={"resolved": True}
    )
    requests = prepare_text_requests(
        [{**base, "language": "en"}, {**base, "language": "pt"}], profile, registry
    )
    assert len(requests["requests"]) == 2
