import importlib
import json
from pathlib import Path

import pytest

from chart_observatory.lyrics.revision_protocol import normalize_text


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


@pytest.mark.parametrize("with_verified", [False, True])
def test_review_package_is_blind_and_preserves_persistent_registry(
    tmp_path, monkeypatch, with_verified
):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    preparation = importlib.import_module("prepare_review_protocol")
    root, prepared = tmp_path / "root", tmp_path / "prepared"
    history, review = root / "history", root / "review"
    (root / "config").mkdir(parents=True)
    (root / "config/lyrics_review_evidence.json").write_text('{"entries": []}')
    review.mkdir()
    (review / "comparison.json").write_text("[]")
    monkeypatch.setattr(preparation, "ROOT", root)
    monkeypatch.setattr(preparation, "HISTORY", history)
    monkeypatch.setattr(preparation, "REVIEW", review)
    write_rows(
        history / "recovery-targets.jsonl",
        [
            {"document_id": "doc", "recording_id": "SPOTIFY:native-1"},
        ],
    )
    text = "First verse.\nRefrain.\nRefrain."
    normalized = normalize_text(text)
    write_rows(
        history / "acquisition/acquisition.jsonl",
        [
            {
                "original_document_id": "doc",
                "recording_id": "SPOTIFY:native-1",
                "status": "candidate_pending_validation",
                "source": "LRCLIB",
                "title": "Same",
                "artist": "Same",
                "variants": [
                    {"text": text, "source": "LRCLIB", "lyrics_hash": normalized.normalized_hash}
                ],
            }
        ],
    )
    write_rows(
        prepared / "candidates.jsonl",
        [
            dict(
                candidate_id=key,
                platform=platform,
                title="Same",
                artist="Same",
                country_code="BR",
                year=2025,
                window="full_year",
                position=i,
            )
            for i, (key, platform) in enumerate(
                [
                    ("SPOTIFY:native-1", "SPOTIFY"),
                    ("SPOTIFY:native-2", "SPOTIFY"),
                    ("YOUTUBE_METADATA:unknown", "YOUTUBE"),
                ],
                1,
            )
        ],
    )
    validated = None
    if with_verified:
        validated = tmp_path / "validated.jsonl"
        write_rows(
            validated,
            [
                dict(
                    text_identity_id="edition",
                    text=text,
                    normalized_hash=normalized.normalized_hash,
                    original_hash=normalized.original_hash,
                    normalization_version=normalized.version,
                    identity_confirmed=True,
                    integrity_validated=True,
                    ai_exposed=False,
                    historical_review=False,
                    text_language_role="original",
                    equivalence_group="group",
                    source="test",
                    period="2025",
                    risk="low",
                    language="en",
                    evidence={"ref": "test"},
                )
            ],
        )
    output = tmp_path / "output"
    preparation.prepare(prepared, output, validated)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["identity_claims"] == 3
    assert manifest["pilot_music"] == int(with_verified)
    assert manifest["pilot_deficit"] == 80 - int(with_verified)
    assert manifest["validation_deficit"] == 240
    assert manifest["paid_calls"] == 0
    first = list(preparation.rows(output / "integrity-review-A.jsonl"))[0]
    second = list(preparation.rows(output / "integrity-review-B.jsonl"))[0]
    assert first["review_id"] != second["review_id"]
    assert first["variants"][0]["text"] == text
    assert not {"source", "country_code", "position", "previous_scores"} & set(first)
    identities = list(preparation.rows(output / "identities-and-equivalences.jsonl"))
    assert all(r["recording_id"] is None for r in identities)
    assert identities[2]["native_id"] is None
    preparation.prepare(prepared, tmp_path / "repeated-output", validated)
    import sqlite3

    with sqlite3.connect(manifest["persistent_registry"]) as conn:
        assert conn.execute("SELECT count(*) FROM platform_identity_claims").fetchone()[0] == 3


def test_live_ledger_partial_tail_does_not_become_evidence(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    preparation = importlib.import_module("prepare_review_protocol")
    path = tmp_path / "ledger.jsonl"
    write_rows(path, [{"original_document_id": "doc", "status": "not_found"}])
    with path.open("ab") as handle:
        handle.write(b'{"original_document_id":')
    index = preparation.acquisition_index([path], {"doc": "recording"})
    assert list(index) == ["recording"]
    assert preparation.materialize(index["recording"])[0]["status"] == "not_found"
