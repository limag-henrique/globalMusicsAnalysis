import json
from copy import deepcopy

import pytest
from google.genai import types

from chart_observatory.lyrics.research_contract import build_profile, prepare_request
from chart_observatory.lyrics.research_vertex_payload import vertex_payload
from chart_observatory.lyrics.review_protocol import TOPICS


def prepared(**generation):
    return prepare_request(
        edition_id="synthetic-edition",
        text="Texto sintético.\r\nRefrão 😀\nRefrão 😀\n",
        language="pt",
        profile=build_profile(
            model_id="alias-model",
            resolved_model_version="resolved-model-001",
            generation_configuration={
                "provider": "vertex_ai",
                "region": "global",
                "retention_days": 0,
                "temperature": 0,
                "max_output_tokens": 8192,
                **generation,
            },
        ),
    )


def test_vertex_wire_uses_new_schema_resolved_target_and_lossless_segments():
    request = prepared(thinking_config={"thinking_level": "LOW"})
    payload = vertex_payload(request)
    assert payload["model"] == "resolved-model-001"
    assert payload["dispatch_target"]["retention_days"] == 0
    body = payload["request"]
    config = types.GenerateContentConfig.model_validate(body["generationConfig"])
    assert config.temperature == 0
    assert config.max_output_tokens == 8192
    assert config.response_mime_type == "application/json"
    assert config.response_schema is None
    assert set(config.response_json_schema["properties"]["topics"]["properties"]) == set(TOPICS)
    assert config.thinking_config.thinking_level == "LOW"
    assert not {"provider", "region", "retention_days"} & body["generationConfig"].keys()
    content = json.loads(body["contents"][0]["parts"][0]["text"])
    assert set(content) == {"request_id", "language", "segments"}
    assert content["request_id"] == request["request_id"]
    assert content["segments"] == request["segments"]
    assert "".join(part["text"] for part in content["segments"]) == (
        "Texto sintético.\r\nRefrão 😀\nRefrão 😀\n"
    )


def test_vertex_wire_rejects_unmapped_settings_instead_of_changing_frozen_configuration():
    for changes in (
        {"unsupported_setting": True},
        {"response_json_schema": {}},
        {"thinking_config": {"unsupported_setting": True}},
    ):
        with pytest.raises(ValueError, match="unsupported"):
            vertex_payload(prepared(**changes))


def test_vertex_wire_requires_target_and_unchanged_full_request():
    with pytest.raises(ValueError, match="explicit Vertex"):
        vertex_payload(prepared(region=""))
    request = deepcopy(prepared())
    request["segments"][0]["text"] = "Changed text"
    with pytest.raises(ValueError, match="changed"):
        vertex_payload(request)
