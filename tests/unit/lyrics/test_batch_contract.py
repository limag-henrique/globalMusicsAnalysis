import json

from chart_observatory.lyrics.classification import LyricsClassification
from chart_observatory.lyrics.gemini_pipeline import (
    build_lyrics_generation_config,
    build_lyrics_prompt,
    lyrics_response_json_schema,
)


def test_online_and_batch_schema_is_json_serializable_and_complete() -> None:
    schema = lyrics_response_json_schema()

    assert json.loads(json.dumps(schema)) == schema
    assert schema["required"] == list(LyricsClassification.model_fields)
    assert "default" not in json.dumps(schema)


def test_gemini_38_low_omits_sampling_parameters() -> None:
    config = build_lyrics_generation_config("gemini-3.8-flash", "LOW", 4096)
    payload = config.model_dump(mode="json", by_alias=True, exclude_none=True)

    assert payload["thinkingConfig"] == {"thinkingLevel": "LOW"}
    assert payload["responseMimeType"] == "application/json"
    assert "responseJsonSchema" in payload
    assert not {"temperature", "topP", "topK", "candidateCount"} & payload.keys()


def test_prompt_contains_only_control_text_language_and_lyrics() -> None:
    prompt = build_lyrics_prompt("texto único da letra", "pt-BR")

    assert prompt.count("texto único da letra") == 1
    assert "Lyric language: pt-BR" in prompt
    for forbidden in ("artist", "country", "chart_rank", "streams", "platform", "genre"):
        assert forbidden not in prompt.casefold()
