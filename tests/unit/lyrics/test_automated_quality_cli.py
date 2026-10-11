from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[3]


def classification_payload(consent: str = "not_applicable") -> dict[str, object]:
    return {
        "classification_status": "classified",
        "confidence": 0.99,
        "sexuality": {
            "sexual_explicitness": 0,
            "sexual_desire": 0,
            "sexual_innuendo": 0,
            "explicit_sexual_act": 0,
            "explicit_sexual_anatomy": 0,
        },
        "relationships": {
            "romantic_affection": 0,
            "heartbreak": 0,
            "infidelity": 0,
            "transactional_sex": 0,
            "casual_sex": 0,
            "jealousy_possession": 0,
            "reciprocity": 0,
            "consent": consent,
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
    }


def test_command_creates_clean_derivative_without_promoting_original_classification(
    tmp_path: Path,
) -> None:
    original = (
        "First complete lyric with &#39;apostrophe&#39;\nSecond complete lyric line\n"
        "Adicionar aos favoritos Adicionar à playlist Tamanho do texto Cifra Imprimir "
        "Corrigir Rolagem automática Anotações Ativadas Desativadas"
    )
    fixture = tmp_path / "input.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "document_id": "00000000-0000-0000-0000-000000000001",
                "document_track_id": "00000000-0000-0000-0000-000000000002",
                "source": "LETRAS",
                "text": original,
                "rights_status": "RESEARCH_AUTHORIZED",
                "content_sha256": hashlib.sha256(original.encode()).hexdigest(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "quality"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/correct_lyrics_quality.py"),
            "--input-jsonl",
            str(fixture),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    derivative = pl.read_parquet(output / "text-derivatives.parquet").row(0, named=True)
    assert derivative["text"] == (
        "First complete lyric with 'apostrophe'\nSecond complete lyric line"
    )
    manifest = json.loads((output / "quality-manifest.jsonl").read_text(encoding="utf-8"))
    assert "classification_does_not_cover_derivative" in manifest["blocking_reasons"]
    assert manifest["automated_operational_eligible"] is False
    assert fixture.read_text(encoding="utf-8").strip() == json.dumps(
        {
            "document_id": "00000000-0000-0000-0000-000000000001",
            "document_track_id": "00000000-0000-0000-0000-000000000002",
            "source": "LETRAS",
            "text": original,
            "rights_status": "RESEARCH_AUTHORIZED",
            "content_sha256": hashlib.sha256(original.encode()).hexdigest(),
        }
    )


def test_command_detects_identity_collisions_exposed_by_entity_cleaning(tmp_path: Path) -> None:
    fixture = tmp_path / "input.jsonl"
    texts = [
        "A sufficiently long lyric about an 'example'\nA second complete line",
        "A sufficiently long lyric about an &#39;example&#39;\nA second complete line",
    ]
    rows = []
    for index, lyric in enumerate(texts, start=1):
        rows.append(
            {
                "document_id": f"00000000-0000-0000-0000-{index:012d}",
                "document_track_id": f"00000000-0000-0000-0001-{index:012d}",
                "source": "GENIUS",
                "rights_status": "RESEARCH_AUTHORIZED",
                "text": lyric,
                "content_sha256": hashlib.sha256(lyric.encode()).hexdigest(),
            }
        )
    fixture.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    output = tmp_path / "quality"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/correct_lyrics_quality.py"),
            "--input-jsonl",
            str(fixture),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["cleaned_text_groups_across_tracks"] == 1
    manifest = [
        json.loads(line)
        for line in (output / "quality-manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all("cleaned_text_across_track_identities" in row["warnings"] for row in manifest)


def test_command_blocks_categorical_disagreement_and_hash_errors_despite_high_confidence(
    tmp_path: Path,
) -> None:
    lyric = (
        "This is a sufficiently long synthetic lyric without any encoded interface artifacts.\n"
        "The second line is also complete."
    )
    records = []
    for index, consent in enumerate(("not_applicable", "ambiguous", "not_applicable"), start=1):
        track = f"00000000-0000-0000-0001-{index:012d}"
        digest = hashlib.sha256(lyric.encode()).hexdigest()
        records.append(
            {
                "document_id": f"00000000-0000-0000-0000-{index:012d}",
                "document_track_id": track,
                "canonical_track_id": track,
                "source": "GENIUS",
                "rights_status": "RESEARCH_AUTHORIZED",
                "text": lyric,
                "content_sha256": digest if index < 3 else "0" * 64,
                "lyrics_hash": digest,
                "classification_status": "classified",
                "result_json": classification_payload(consent),
                "confidence": 0.99,
                "snapshot_id": f"00000000-0000-0000-0002-{index:012d}",
                "model_id": "gemini-3.8-flash",
                "taxonomy_version": "lyrics-classification-v1",
                "prompt_version": "lyrics-classification-prompt-v2",
                "input_tokens": 40,
                "output_tokens": 200,
                "estimated_cost_usd": "0.01",
            }
        )
    fixture = tmp_path / "input.jsonl"
    fixture.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
    output = tmp_path / "quality"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/correct_lyrics_quality.py"),
            "--input-jsonl",
            str(fixture),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    rows = [
        json.loads(line)
        for line in (output / "quality-manifest.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all("duplicate_text_label_disagreement" in row["blocking_reasons"] for row in rows[:2])
    assert "stored_content_hash_mismatch" in rows[2]["blocking_reasons"]
    assert pl.read_parquet(output / "operational-classifications.parquet").height == 0


def test_command_retains_a_structurally_valid_unmodified_high_confidence_result(
    tmp_path: Path,
) -> None:
    lyric = (
        "This synthetic lyric is long enough and contains no themes within this taxonomy.\n"
        "Another complete line with no metadata."
    )
    digest = hashlib.sha256(lyric.encode()).hexdigest()
    record = {
        "document_id": "00000000-0000-0000-0000-000000000001",
        "document_track_id": "00000000-0000-0000-0001-000000000001",
        "canonical_track_id": "00000000-0000-0000-0001-000000000001",
        "source": "GENIUS",
        "rights_status": "RESEARCH_AUTHORIZED",
        "text": lyric,
        "content_sha256": digest,
        "lyrics_hash": digest,
        "classification_status": "classified",
        "result_json": classification_payload(),
        "confidence": 0.99,
        "snapshot_id": "00000000-0000-0000-0002-000000000001",
        "model_id": "gemini-3.8-flash",
        "taxonomy_version": "lyrics-classification-v1",
        "prompt_version": "lyrics-classification-prompt-v2",
        "input_tokens": 40,
        "output_tokens": 200,
        "estimated_cost_usd": "0.01",
    }
    fixture = tmp_path / "input.jsonl"
    fixture.write_text(json.dumps(record), encoding="utf-8")
    output = tmp_path / "quality"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/correct_lyrics_quality.py"),
            "--input-jsonl",
            str(fixture),
            "--output-dir",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    selected = pl.read_parquet(output / "operational-classifications.parquet")
    assert selected.height == 1
    assert selected["original_sha256"][0] == digest
