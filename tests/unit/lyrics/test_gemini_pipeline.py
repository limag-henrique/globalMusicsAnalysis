from types import SimpleNamespace

import pytest
from google.genai import errors

from chart_observatory.lyrics.classification import LyricsClassification
from chart_observatory.lyrics.gemini_pipeline import (
    GeminiAnnotationClient,
    GeminiLyricsClassifier,
    GeminiOutcomeStatus,
    LyricsOvhClient,
    extract_usage,
    normalize_lookup_text,
)

VALID_CLASSIFICATION = {
    "classification_status": "classified",
    "confidence": 0.9,
    "sexuality": {
        "sexual_explicitness": 0,
        "sexual_desire": 0,
        "sexual_innuendo": 0,
        "explicit_sexual_act": 0,
        "explicit_sexual_anatomy": 0,
    },
    "relationships": {
        "romantic_affection": 1,
        "heartbreak": 0,
        "infidelity": 0,
        "transactional_sex": 0,
        "casual_sex": 0,
        "jealousy_possession": 0,
        "reciprocity": 1,
        "consent": "not_applicable",
    },
    "gender_representation": {
        "objectification": 0,
        "misogyny": 0,
        "sexual_agency": 0,
        "status_symbolization": 0,
        "commodification": 0,
        "target_gender": "not_applicable",
        "representation_roles": [],
    },
    "material_status": {
        "money_reference": 0,
        "materialism": 0,
        "conspicuous_consumption": 0,
        "wealth_as_status": 0,
    },
    "antisocial": {
        name: {"intensity": 0, "stance": "neutral"}
        for name in ("drugs_alcohol", "crime", "violence", "weapons")
    },
    "territorial_identity": 0,
    "romantic_summary": "Mutual affection.",
}


def test_lookup_normalization_removes_feature_markers_and_accents() -> None:
    assert normalize_lookup_text("Música (feat. João)") == "musica"


def test_vertex_client_uses_adc_and_structured_schema(monkeypatch) -> None:
    construction: list[dict[str, object]] = []
    calls: list[dict[str, object]] = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                parsed=VALID_CLASSIFICATION,
                usage_metadata=None,
                prompt_feedback=None,
                candidates=[],
            )

    class FakeClient:
        def __init__(self, **kwargs):
            construction.append(kwargs)
            self.models = FakeModels()

    monkeypatch.setattr("chart_observatory.lyrics.gemini_pipeline.genai.Client", FakeClient)

    classifier = GeminiLyricsClassifier(
        project_id="test-project",
        location="global",
        model_id="gemini-3.5-flash",
    )
    response = classifier.classify("lyric only", language="pt")

    assert response.result == LyricsClassification.model_validate(VALID_CLASSIFICATION)
    assert construction[0]["vertexai"] is True
    assert construction[0]["project"] == "test-project"
    assert construction[0]["location"] == "global"
    assert "api_key" not in construction[0]
    assert construction[0]["http_options"].api_version == "v1"
    assert construction[0]["http_options"].timeout == 120_000
    assert calls[0]["config"].response_schema is LyricsClassification
    assert calls[0]["config"].response_mime_type == "application/json"


def test_prompt_contains_only_lyrics_and_optional_language_metadata(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                parsed=VALID_CLASSIFICATION,
                usage_metadata=None,
                prompt_feedback=None,
                candidates=[],
            )

    fake_client = SimpleNamespace(models=FakeModels())
    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: fake_client,
    )
    classifier = GeminiLyricsClassifier("project", "global", "gemini-3.5-flash")

    classifier.classify("uma letra exclusiva", language="pt-BR")

    prompt = str(calls[0]["contents"])
    assert prompt.count("uma letra exclusiva") == 1
    assert "Lyric language: pt-BR" in prompt
    for forbidden in (
        "song id",
        "title",
        "artist",
        "country",
        "chart",
        "rank",
        "streams",
        "platform",
        "tiktok",
        "genre",
        "hypothesis",
    ):
        assert forbidden not in prompt.casefold()


def test_prompt_anchors_social_classification_without_overclaiming(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                parsed=VALID_CLASSIFICATION,
                usage_metadata=None,
                prompt_feedback=None,
                candidates=[],
            )

    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )

    GeminiLyricsClassifier("project", "global", "gemini-3.5-flash").classify(
        "texto de teste longo o bastante",
        language="pt-BR",
    )

    prompt = str(calls[0]["contents"]).casefold()
    assert "0 (absent), 1 (incidental), 2 (substantial), or 3 (central)" in prompt
    assert "narrator or quoted voice" in prompt
    assert "absence of consent language is not coercion" in prompt
    assert "use ambiguous" in prompt
    assert "do not infer demographic identity" in prompt


@pytest.mark.parametrize(
    ("model_id", "temperature", "thinking_level"),
    [
        ("gemini-3.5-flash", None, "MINIMAL"),
        ("gemini-2.5-flash", 0.0, None),
        ("future-model", None, None),
    ],
)
def test_generation_policy_matches_model_family(
    monkeypatch,
    model_id: str,
    temperature: float | None,
    thinking_level: str | None,
) -> None:
    calls: list[dict[str, object]] = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                parsed=VALID_CLASSIFICATION,
                usage_metadata=None,
                prompt_feedback=None,
                candidates=[],
            )

    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )

    GeminiLyricsClassifier("project", "global", model_id).classify("lyrics")

    config = calls[0]["config"]
    assert config.temperature == temperature
    assert config.top_p is None
    assert config.top_k is None
    actual_thinking = config.thinking_config
    assert (
        actual_thinking.thinking_level.value if actual_thinking is not None else None
    ) == thinking_level


def test_gemini_3_uses_configured_compatible_thinking_level(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                parsed=VALID_CLASSIFICATION,
                usage_metadata=None,
                prompt_feedback=None,
                candidates=[],
            )

    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )

    GeminiLyricsClassifier(
        "project", "global", "gemini-3.5-flash", thinking_level="LOW"
    ).classify("lyrics")

    config = calls[0]["config"]
    assert config.thinking_config.thinking_level.value == "LOW"
    assert config.temperature is None


def test_classifier_reuses_one_sdk_client_per_thread(monkeypatch) -> None:
    construction_count = 0
    generation_count = 0

    class FakeModels:
        def generate_content(self, **_kwargs):
            nonlocal generation_count
            generation_count += 1
            return SimpleNamespace(
                parsed=VALID_CLASSIFICATION,
                usage_metadata=None,
                prompt_feedback=None,
                candidates=[],
            )

    def make_client(**_kwargs):
        nonlocal construction_count
        construction_count += 1
        return SimpleNamespace(models=FakeModels())

    monkeypatch.setattr("chart_observatory.lyrics.gemini_pipeline.genai.Client", make_client)
    classifier = GeminiLyricsClassifier("project", "global", "gemini-2.5-flash")

    classifier.classify("first")
    classifier.classify("second")

    assert construction_count == 1
    assert generation_count == 2


def test_legacy_annotation_facade_delegates_with_lyrics_only(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                parsed=VALID_CLASSIFICATION,
                usage_metadata=None,
                prompt_feedback=None,
                candidates=[],
            )

    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )
    client = GeminiAnnotationClient(
        project_id="project",
        location="global",
        model="gemini-2.5-flash",
        http_client=object(),
    )

    result = client.annotate(
        "secret-song-id",
        "Secret Title",
        "Secret Artist",
        "only these lyrics",
    )

    assert result["classification_status"] == "classified"
    assert calls[0]["model"] == "gemini-2.5-flash"
    prompt = str(calls[0]["contents"])
    assert "only these lyrics" in prompt
    assert "secret-song-id" not in prompt
    assert "Secret Title" not in prompt
    assert "Secret Artist" not in prompt


def test_usage_metadata_is_extracted_without_inventing_missing_tokens() -> None:
    usage = extract_usage(SimpleNamespace(prompt_token_count=10))

    assert usage is not None
    assert usage.input_tokens == 10
    assert usage.output_tokens is None
    assert usage.thought_tokens is None
    assert usage.total_tokens is None


def test_success_returns_supplied_usage_metadata(monkeypatch) -> None:
    response = SimpleNamespace(
        parsed=VALID_CLASSIFICATION,
        usage_metadata=SimpleNamespace(
            prompt_token_count=10,
            candidates_token_count=20,
            thoughts_token_count=30,
            total_token_count=60,
        ),
        prompt_feedback=None,
        candidates=[],
    )
    models = SimpleNamespace(generate_content=lambda **_kwargs: response)
    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=models),
    )

    outcome = GeminiLyricsClassifier("project", "global", "gemini-2.5-flash").classify(
        "lyrics"
    )

    assert outcome.usage is not None
    assert outcome.usage.model_dump() == {
        "input_tokens": 10,
        "output_tokens": 20,
        "thought_tokens": 30,
        "total_tokens": 60,
    }


@pytest.mark.parametrize(
    ("parsed", "expected"),
    [
        (None, GeminiOutcomeStatus.MALFORMED_RESPONSE),
        ({**VALID_CLASSIFICATION, "confidence": 4}, GeminiOutcomeStatus.VALIDATION_ERROR),
    ],
)
def test_malformed_or_invalid_parsed_output_is_recoverable(
    monkeypatch, parsed: object, expected: GeminiOutcomeStatus
) -> None:
    response = SimpleNamespace(
        parsed=parsed,
        usage_metadata=SimpleNamespace(prompt_token_count=4),
        prompt_feedback=None,
        candidates=[],
    )
    models = SimpleNamespace(generate_content=lambda **_kwargs: response)
    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=models),
    )

    outcome = GeminiLyricsClassifier("project", "global", "gemini-2.5-flash").classify(
        "private lyric"
    )

    assert outcome.outcome is expected
    assert outcome.result is None
    assert outcome.usage is not None
    assert "private lyric" not in (outcome.error or "")


def test_sdk_model_instance_is_revalidated_from_its_python_payload(monkeypatch) -> None:
    valid = LyricsClassification.model_validate(VALID_CLASSIFICATION)
    invalid = valid.model_copy(update={"confidence": 4})
    response = SimpleNamespace(
        parsed=invalid,
        usage_metadata=None,
        prompt_feedback=None,
        candidates=[],
    )
    models = SimpleNamespace(generate_content=lambda **_kwargs: response)
    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=models),
    )

    outcome = GeminiLyricsClassifier("project", "global", "gemini-2.5-flash").classify(
        "private lyric"
    )

    assert outcome.outcome is GeminiOutcomeStatus.VALIDATION_ERROR
    assert outcome.result is None


def test_safety_block_is_a_typed_recoverable_outcome(monkeypatch) -> None:
    response = SimpleNamespace(
        parsed=None,
        usage_metadata=SimpleNamespace(prompt_token_count=4),
        prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
        candidates=[],
    )
    models = SimpleNamespace(generate_content=lambda **_kwargs: response)
    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=models),
    )

    outcome = GeminiLyricsClassifier("project", "global", "gemini-2.5-flash").classify(
        "private lyric"
    )

    assert outcome.outcome is GeminiOutcomeStatus.BLOCKED
    assert outcome.result is None
    assert outcome.usage is not None


def test_rate_limit_is_retried_then_succeeds(monkeypatch) -> None:
    attempts = 0

    def generate_content(**_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise errors.ClientError(429, {"message": "slow down", "status": "RESOURCE_EXHAUSTED"})
        return SimpleNamespace(
            parsed=VALID_CLASSIFICATION,
            usage_metadata=None,
            prompt_feedback=None,
            candidates=[],
        )

    models = SimpleNamespace(generate_content=generate_content)
    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=models),
    )

    outcome = GeminiLyricsClassifier(
        "project", "global", "gemini-2.5-flash", retry_wait_seconds=0
    ).classify("lyrics")

    assert outcome.outcome is GeminiOutcomeStatus.SUCCESS
    assert attempts == 2


def test_auth_failure_is_terminal_and_safe(monkeypatch) -> None:
    attempts = 0

    def generate_content(**_kwargs):
        nonlocal attempts
        attempts += 1
        raise errors.ClientError(
            401,
            {"message": "credential token secret-value", "status": "UNAUTHENTICATED"},
        )

    models = SimpleNamespace(generate_content=generate_content)
    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=models),
    )

    outcome = GeminiLyricsClassifier(
        "project", "global", "gemini-2.5-flash", retry_wait_seconds=0
    ).classify("private lyric")

    assert outcome.outcome is GeminiOutcomeStatus.AUTH_ERROR
    assert outcome.result is None
    assert attempts == 1
    assert "private lyric" not in (outcome.error or "")
    assert "secret-value" not in (outcome.error or "")


def test_service_unavailable_stops_after_bounded_retries(monkeypatch) -> None:
    attempts = 0

    def generate_content(**_kwargs):
        nonlocal attempts
        attempts += 1
        raise errors.ServerError(503, {"message": "unavailable", "status": "UNAVAILABLE"})

    models = SimpleNamespace(generate_content=generate_content)
    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=models),
    )

    outcome = GeminiLyricsClassifier(
        "project",
        "global",
        "gemini-2.5-flash",
        max_attempts=3,
        retry_wait_seconds=0,
    ).classify("lyrics")

    assert outcome.outcome is GeminiOutcomeStatus.TRANSIENT_ERROR
    assert outcome.error == (
        "Gemini remained unavailable after bounded retries (HTTP 503)"
    )
    assert attempts == 3


def test_token_estimation_uses_count_tokens_without_generation(monkeypatch) -> None:
    count_calls: list[dict[str, object]] = []

    class FakeModels:
        def count_tokens(self, **kwargs):
            count_calls.append(kwargs)
            return SimpleNamespace(total_tokens=37)

        def generate_content(self, **_kwargs):
            raise AssertionError("token estimation must not generate content")

    monkeypatch.setattr(
        "chart_observatory.lyrics.gemini_pipeline.genai.Client",
        lambda **_kwargs: SimpleNamespace(models=FakeModels()),
    )
    classifier = GeminiLyricsClassifier("project", "global", "gemini-2.5-flash")

    total = classifier.estimate_input_tokens("lyrics", language=None)

    assert total == 37
    assert count_calls == [{"model": "gemini-2.5-flash", "contents": count_calls[0]["contents"]}]
    assert "lyrics" in str(count_calls[0]["contents"])


def test_lyrics_ovh_client_returns_none_for_http_errors() -> None:
    class FakeResponse:
        status_code = 404

    class FakeHttp:
        def get(self, *args, **kwargs):
            return FakeResponse()

    client = LyricsOvhClient(http_client=FakeHttp())

    assert client.fetch("Title", "Artist") is None
