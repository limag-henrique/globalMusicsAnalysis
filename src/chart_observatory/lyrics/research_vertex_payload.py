"""Serialize the new research contract locally for future Vertex requests.

These functions create no clients, uploads, reservations or approvals. Callers
must revalidate scientific eligibility and the exact target before dispatch.
"""

from __future__ import annotations

from copy import deepcopy

from chart_observatory.lyrics.research_contract import verify_request
from chart_observatory.lyrics.revision_protocol import canonical_json

_GENERATION_FIELDS = {
    "temperature": "temperature",
    "top_p": "topP",
    "top_k": "topK",
    "max_output_tokens": "maxOutputTokens",
    "seed": "seed",
    "stop_sequences": "stopSequences",
    "candidate_count": "candidateCount",
}
_TARGET_FIELDS = {"provider", "region", "retention_days"}
_THINKING_FIELDS = {
    "thinking_level": "thinkingLevel",
    "thinking_budget": "thinkingBudget",
    "include_thoughts": "includeThoughts",
}


def vertex_payload(request: dict) -> dict:
    """Return an exact model target and REST generateContent body, without IO."""
    verify_request(request)
    configuration = request["profile"]["configuration"]
    generation = configuration["generation"]
    if (
        generation.get("provider") != "vertex_ai"
        or not isinstance(generation.get("region"), str)
        or not generation["region"].strip()
        or type(generation.get("retention_days")) is not int
        or generation["retention_days"] < 0
    ):
        raise ValueError("explicit Vertex provider, region and retention required")
    unknown = set(generation) - _GENERATION_FIELDS.keys() - _TARGET_FIELDS - {"thinking_config"}
    if unknown:
        raise ValueError("unsupported frozen generation settings: " + ", ".join(sorted(unknown)))
    wire = {
        alias: deepcopy(generation[field])
        for field, alias in _GENERATION_FIELDS.items()
        if field in generation
    }
    thinking = generation.get("thinking_config")
    if thinking is not None:
        if not isinstance(thinking, dict) or set(thinking) - _THINKING_FIELDS.keys():
            raise ValueError("unsupported frozen thinking settings")
        wire["thinkingConfig"] = {
            _THINKING_FIELDS[field]: deepcopy(value) for field, value in thinking.items()
        }
    definition = request["contract"]
    wire.update(
        responseMimeType="application/json",
        responseJsonSchema=deepcopy(definition["response_schema"]),
    )
    target = {
        "provider": "vertex_ai",
        "model_id": request["profile"]["model_id"],
        "resolved_model_version": configuration["resolved_model_version"],
        "region": generation["region"],
        "retention_days": generation["retention_days"],
    }
    return {
        "request_id": request["request_id"],
        "reuse_key": request["reuse_key"],
        "model": target["resolved_model_version"],
        "dispatch_target": target,
        "request": {
            "systemInstruction": {
                "parts": [{"text": definition["prompt"] + canonical_json(definition["rubric"])}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": canonical_json(
                                {
                                    "request_id": request["request_id"],
                                    "language": request["language"],
                                    "segments": request["segments"],
                                }
                            )
                        }
                    ],
                }
            ],
            "generationConfig": wire,
        },
    }
