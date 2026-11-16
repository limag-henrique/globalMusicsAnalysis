"""User-authorized technical preparation, separate from scientific adjudication."""

from __future__ import annotations

import json
from pathlib import Path

from chart_observatory.final_pipeline import MAX_SONGS, digest, encode
from chart_observatory.lyrics.research_contract import contract, segments

POLICY = "automated-native-full-source-v1"


def assess(decision):
    validation = decision.get("validation", {})
    reasons = []
    for name in ("identity", "completeness", "source_text_integrity"):
        if validation.get(name, {}).get("status") != "passed":
            reasons.append(name + "_not_passed")
    native = decision.get("native_evidence", {})
    if (
        not decision.get("native_supported")
        or native.get("native_proof_present") is not True
        or not isinstance(native.get("body_sha256"), str)
        or len(native["body_sha256"]) != 64
    ):
        reasons.append("native_recording_not_supported")
    if not decision.get("body_hash_verified"):
        reasons.append("text_hash_not_verified")
    if decision.get("audit", {}).get("text_quality_flags"):
        reasons.append("quality_or_identity_flags")
    if decision.get("audit", {}).get("source_quarantined"):
        reasons.append("source_quarantined")
    if not decision.get("provider_supported"):
        reasons.append("full_cohort_provider_validation_not_passed")
    if decision.get("error_type"):
        reasons.append("validator_error")
    return dict(
        eligible=not reasons,
        reasons=reasons,
        policy=POLICY,
        scientific_approval=False,
        audio_transcription_equivalence_proven=False,
    )


def register(db, *, recording_id, request_id, text_hash, selection_hash):
    db.execute(
        "CREATE TABLE IF NOT EXISTS automatic_prepared("
        "recording_id TEXT PRIMARY KEY,request_id TEXT,text_hash TEXT,selection_hash TEXT)"
    )
    previous = db.execute(
        "SELECT request_id,text_hash FROM automatic_prepared WHERE recording_id=?", (recording_id,)
    ).fetchone()
    if previous:
        if tuple(previous) != (request_id, text_hash):
            raise ValueError("recording already prepared with a different text/profile")
        return True
    old = db.execute("SELECT count(*) FROM prepared").fetchone()[0]
    new = db.execute("SELECT count(*) FROM automatic_prepared").fetchone()[0]
    if old + new >= MAX_SONGS:
        return False
    db.execute(
        "INSERT INTO automatic_prepared VALUES (?,?,?,?)",
        (recording_id, request_id, text_hash, selection_hash),
    )
    return True


def request_body(job, text, definition=None):
    if digest(text.encode()) != job["text_sha256"]:
        raise ValueError("prepared transcription changed")
    definition = definition or contract()
    system = definition["prompt"].replace("rubrica aprovada", "rubrica operacional")
    system += "\nA validação científica desta classificação automatizada permanece separada."
    return dict(
        systemInstruction=dict(parts=[dict(text=system + "\n" + encode(definition["rubric"]))]),
        contents=[
            dict(
                role="user",
                parts=[
                    dict(
                        text=encode(
                            dict(
                                request_id=job["request_id"],
                                segments=segments(text),
                            )
                        )
                    )
                ],
            )
        ],
        generationConfig=dict(
            responseMimeType="application/json",
            responseJsonSchema=definition["response_schema"],
            maxOutputTokens=8192,
        ),
    )


def materialize(jobs_file, output, project):
    from chart_observatory.final_pipeline import read_result

    count = 0
    output = Path(output)
    if output.exists():
        raise ValueError("materialized output already exists")
    temporary = output.with_suffix(output.suffix + ".tmp")
    with (
        Path(jobs_file).open(encoding="utf-8") as source,
        temporary.open("x", encoding="utf-8") as dest,
    ):
        for line in source:
            job = json.loads(line)
            if count >= MAX_SONGS:
                raise ValueError("maximum 150000 songs")
            if not job.get("automatic_eligibility", {}).get("eligible"):
                raise ValueError("unapproved automatic job")
            _, text, _ = read_result(job["source_reference"], project)
            if text is None:
                raise ValueError("prepared text no longer available")
            dest.write(encode(dict(request=request_body(job, text))) + "\n")
            count += 1
    temporary.replace(output)
    return count
