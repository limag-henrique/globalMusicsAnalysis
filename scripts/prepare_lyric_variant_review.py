"""Build hash-bound independent review forms for ambiguous preserved LRCLIB editions."""

import argparse
import base64
import hashlib
import json
import random
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from chart_observatory.lyrics.quota_acquisition import identity, lrclib_text
from chart_observatory.lyrics.revision_protocol import normalize_text
from chart_observatory.lyrics.text_quality import recording_duration_mismatch
from chart_observatory.runtime_status import publish_status

ROOT = Path(__file__).resolve().parents[1]


def read_variants(event, payload, texts):
    path = Path(event["cache_path"])
    raw = path.read_bytes()
    saved = json.loads(raw)
    if urlparse(saved.get("url", "")).hostname != "lrclib.net":
        return []
    body = (
        base64.b64decode(saved["body_base64"], validate=True)
        if "body_base64" in saved
        else saved["body"].encode()
    )
    if hashlib.sha256(body).hexdigest() != saved["body_sha256"]:
        raise ValueError("preserved response checksum mismatch")
    rows = json.loads(body)
    rows = rows if isinstance(rows, list) else [rows]
    variants = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        value = lrclib_text(row)
        if not value:
            continue
        # Nonmatching search hits remain in their original response evidence;
        # independent reviewers receive exact title/artist edition candidates.
        if any(
            identity(row.get(provider)) != identity(payload.get(field))
            for provider, field in (("trackName", "title"), ("artistName", "artist"))
        ):
            continue
        digest = hashlib.sha256(value.encode()).hexdigest()
        texts[digest] = value
        variants.append(
            dict(
                provider="LRCLIB",
                provider_record_id=row.get("id"),
                provider_url=f"https://lrclib.net/api/get/{row.get('id')}",
                track_name=row.get("trackName"),
                artist_name=row.get("artistName"),
                album_name=row.get("albumName"),
                duration_seconds=row.get("duration"),
                native_duration_disagrees=recording_duration_mismatch(
                    (payload.get("metadata_resolution") or {}).get("duration_ms"),
                    row.get("duration"),
                ),
                text_sha256=digest,
                normalized_text_sha256=normalize_text(value).normalized_hash,
                representation="plain" if row.get("plainLyrics") else "timestamped_lrc",
                response_file=str(path.resolve()),
                response_file_sha256=hashlib.sha256(raw).hexdigest(),
                response_body_sha256=saved["body_sha256"],
                observed_at=saved.get("retrieved_at"),
            )
        )
    return variants


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition-db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    if not all(p.resolve().is_relative_to(ROOT) for p in (args.acquisition_db, args.out)):
        raise ValueError("review paths must remain inside project")
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / "texts").mkdir()
    cases, texts, counts = [], {}, Counter()
    with sqlite3.connect(args.acquisition_db.resolve().as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute(
            "SELECT identity,payload,result FROM tasks WHERE result IS NOT NULL ORDER BY identity"
        ).fetchall()
    frozen_results = "".join(
        json.dumps(
            dict(candidate_id=key, payload=json.loads(payload), result=json.loads(result)),
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
        for key, payload, result in rows
    ).encode()
    (args.out / "source-results.jsonl").write_bytes(frozen_results)
    for key, raw_payload, raw_result in rows:
        payload, result = json.loads(raw_payload), json.loads(raw_result)
        if result.get("text_sha256"):
            continue
        variants, seen_events = [], set()
        for event in result.get("http_evidence", []):
            path = event.get("cache_path")
            if not path or path in seen_events:
                continue
            seen_events.add(path)
            variants.extend(read_variants(event, payload, texts))
        by_record = {}
        for variant in variants:
            by_record.setdefault((variant["provider_record_id"], variant["text_sha256"]), variant)
        variants = list(by_record.values())
        if not variants:
            counts["without_exact_preserved_variant"] += 1
            continue
        counts["cases"] += 1
        counts["variants"] += len(variants)
        counts["ambiguous_text_cases"] += len({v["normalized_text_sha256"] for v in variants}) > 1
        cases.append(
            dict(
                case_id=hashlib.sha256(key.encode()).hexdigest(),
                candidate_id=key,
                title=payload["title"],
                artist=payload["artist"],
                native_metadata=payload.get("metadata_resolution"),
                recording_url="https://open.spotify.com/track/" + key.removeprefix("SPOTIFY:")
                if key.startswith("SPOTIFY:")
                else None,
                chart_bindings=payload["chart_bindings"],
                variants=variants,
                review=dict(
                    reviewer_id=None,
                    selected_text_sha256=None,
                    identity_correct=None,
                    complete_against_identified_recording=None,
                    version_correct=None,
                    evidence_urls=[],
                    notes=None,
                    reviewed_at=None,
                ),
                approvals=[],
                classification_ready=False,
            )
        )
    artifacts = {}
    for digest, text in texts.items():
        (args.out / "texts" / f"{digest}.txt").write_bytes(text.encode())
    for reviewer in ("A", "B"):
        order = list(cases)
        random.Random(f"independent-lyric-review-{reviewer}-v1").shuffle(order)
        raw = "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in order
        ).encode()
        filename = f"reviewer-{reviewer}.jsonl"
        (args.out / filename).write_bytes(raw)
        artifacts[filename] = dict(sha256=hashlib.sha256(raw).hexdigest(), cases=len(order))
    instructions = (
        "Cada revisor deve trabalhar sem consultar as decisões do outro. "
        "Confirme o ID da gravação, a edição (clean/explicit/remix/live), "
        "todos os versos e repetições contra uma fonte oficial adequada "
        "ou a gravação identificada completa. Título/artista/duração e concordância "
        "de sites servem como evidência auxiliar. Registre o hash exato escolhido, "
        "fontes e data. Não atribua aprovação a uma variante ausente ou incompleta; "
        "divergências seguem para terceiro adjudicador. "
        "Campos vazios significam pendência; nenhuma aprovação foi gerada nesta preparação.\n"
    )
    (args.out / "instructions.txt").write_text(instructions, encoding="utf8")
    publish_status(
        args.out / "manifest.json",
        dict(
            prepared_at=datetime.now(UTC).isoformat(),
            acquisition_db=str(args.acquisition_db.resolve()),
            source_results_sha256=hashlib.sha256(frozen_results).hexdigest(),
            producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            examined_results=len(rows),
            counts=dict(counts),
            text_blobs=len(texts),
            artifacts=artifacts,
            text_inventory={
                digest: hashlib.sha256(
                    (args.out / "texts" / f"{digest}.txt").read_bytes()
                ).hexdigest()
                for digest in sorted(texts)
            },
            independent_human_reviewers_required=2,
            adjudicator_on_disagreement=True,
            approvals=0,
            scientific_approved_positions=0,
            classification_ready=False,
        ),
    )


if __name__ == "__main__":
    main()
