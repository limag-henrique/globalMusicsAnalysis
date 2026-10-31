import hashlib
import json

from sqlalchemy import create_engine

from chart_observatory.lyrics.quota_staging import persist_lyric_staging
from chart_observatory.lyrics.staging_review import load_conflicting_alternatives, pending_detail


def evidence(tmp_path):
    root = tmp_path / "replays"
    root.mkdir()
    payload = dict(recording_id="SPOTIFY:one", title="Song", artist="Artist")
    old_text = "Old full fixture text"
    old_hash = hashlib.sha256(old_text.encode()).hexdigest()
    old = dict(source="LETRAS", text_sha256=old_hash)
    text = "First alternative fixture line\nFinal alternative fixture line"
    digest = hashlib.sha256(text.encode()).hexdigest()
    replay = dict(
        payload=payload,
        replay_kind="flagged_repair",
        replaces_text_sha256=old_hash,
        result=dict(
            source="LRCLIB",
            generated_by_ai=False,
            text=text,
            source_metadata=dict(id=123, observed_title="Song", observed_artist="Artist"),
        ),
    )
    raw = json.dumps(replay).encode()
    name = "b" * 64 + ".json"
    (root / name).write_bytes(raw)
    reference = dict(
        candidate_id="SPOTIFY:one",
        source="LRCLIB",
        text_sha256=digest,
        replay_evidence_file="C:\\previous-computer\\replays\\" + name,
        replay_evidence_sha256=hashlib.sha256(raw).hexdigest(),
    )
    old["conflicting_offline_alternatives"] = [reference]
    return root, payload, old, old_text, text, reference


def test_conflict_review_reads_complete_hash_bound_local_evidence_without_approval(tmp_path):
    root, payload, old, old_text, text, _ref = evidence(tmp_path)
    engine = create_engine("sqlite://")
    run = persist_lyric_staging(
        engine,
        {},
        [
            dict(
                candidate_id=payload["recording_id"],
                text_sha256=old["text_sha256"],
                acquisition_status="pending_review",
                payload=payload,
                source_result=old,
                audit={},
            )
        ],
        {old["text_sha256"]: old_text},
    )
    detail = pending_detail(engine, payload["recording_id"], run_id=run["run_id"], replay_root=root)
    assert detail["text"] == old_text
    alternative = detail["alternatives"][0]
    assert alternative["text"] == text and alternative["text"].endswith(
        "Final alternative fixture line"
    )
    assert alternative["evidence_integrity_verified"] and not alternative["classification_ready"]
    engine.dispose()


def test_changed_evidence_and_other_song_never_return_alternative_text(tmp_path):
    root, payload, old, _body, _text, reference = evidence(tmp_path)
    reference["replay_evidence_sha256"] = "f" * 64
    result = load_conflicting_alternatives(payload, old, root)[0]
    assert result["text"] is None and result["error"]
    reference["replay_evidence_sha256"] = hashlib.sha256(
        next(root.glob("*.json")).read_bytes()
    ).hexdigest()
    reference["candidate_id"] = "SPOTIFY:other"
    assert load_conflicting_alternatives(payload, old, root)[0]["text"] is None


def test_evidence_outside_configured_cache_is_not_read(tmp_path):
    root, payload, old, _body, _text, reference = evidence(tmp_path)
    outside = tmp_path / ("c" * 64 + ".json")
    outside.write_text("Sensitive external fixture")
    reference["replay_evidence_file"] = str(outside)
    reference["replay_evidence_sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    result = load_conflicting_alternatives(payload, old, root)[0]
    assert result["text"] is None and not result["evidence_integrity_verified"]
