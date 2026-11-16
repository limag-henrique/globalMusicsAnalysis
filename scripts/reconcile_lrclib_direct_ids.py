"""Recheck LRCLIB records by exact provider ID and publish a new verified staging run."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from recover_low_coverage_lyrics import load_baseline  # noqa: E402

from chart_observatory.config import Settings  # noqa: E402
from chart_observatory.lyrics.quota_acquisition import (  # noqa: E402
    PacedHTTP,
    identities_compatible,
    lrclib_text,
)
from chart_observatory.lyrics.quota_discovery import (  # noqa: E402
    match_lrclib_credit_binding,
)
from chart_observatory.lyrics.recovery_pipeline import (  # noqa: E402
    persist_verified_staging,
    verify_all_candidates,
)
from chart_observatory.lyrics.text_quality import (  # noqa: E402
    prepare_lyric_derivative,
    recording_duration_mismatch,
)
from chart_observatory.research_flow import file_hash  # noqa: E402

V4_SELECTION = ROOT / "data/derived/annual_revision/global-rescan-2018-2026-20261111-v4-final-0002"
V5_SELECTION = (
    ROOT
    / "data/derived/annual_revision/global-rescan-2018-2026-20261115-v5-published-provisional-0003"
)
PARENT_RUN = ROOT / "data/runtime/antigravity-collaboration-20261115/pipeline-run-20261116-batch2"
V4_STAGE = PARENT_RUN / "staging-v4/pending-staging.sqlite"
V5_STAGE = PARENT_RUN / "staging-v5/pending-staging.sqlite"
V4_RUN_ID = "a64c0c0ee968e5c7979bd615f566152052472b13e9a2b508c13f19c261a3f4e9"
V5_RUN_ID = "f95dbbeb5e130565786dd67410966ad3c4b616be4a0039bb40e1249b4d4b08ce"
DEFAULT_OUT = (
    ROOT
    / "data/runtime/antigravity-collaboration-20261115/lrclib-direct-id-refresh-20261116"
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _source_chain_reuse(record: dict[str, Any]) -> dict[str, Any] | None:
    """Reuse only a persisted exact chain bound to this unchanged text hash."""
    result = record.get("source_result") or {}
    source_metadata = result.get("source_metadata") or {}
    # Replay cached Genius HTML when its page-level credit proof is incomplete;
    # the offline parser may be able to establish the missing identity fields.
    if result.get("source") == "GENIUS" and not source_metadata.get(
        "provider_credit_evidence"
    ):
        return None
    digest = record.get("text_sha256")
    automated = (record.get("audit") or {}).get("automated_validation") or {}
    integrity = automated.get("source_text_integrity") or {}
    evidence = automated.get("source_chain_evidence") or {}
    raw_digest = integrity.get("raw_response_sha256")
    if (
        not digest
        or integrity.get("stored_text_sha256") != digest
        or integrity.get("replayed_text_sha256") != digest
        or integrity.get("exact_replay_hash_match") is not True
        or integrity.get("source_replay_matched") is not True
        or not isinstance(raw_digest, str)
        or len(raw_digest) != 64
    ):
        return None
    return {
        "status": integrity.get("source_chain_status"),
        "extracted_text_sha256": integrity.get("replayed_text_sha256"),
        "exact_text_hash_match": integrity.get("exact_replay_hash_match"),
        "evidence_sha256": raw_digest,
        "source_url": evidence.get("source_url"),
        "errors": evidence.get("errors", []),
    }


def _load_cohort(path: Path, run_id: str):
    records, texts = load_baseline(path, run_id)
    return records, texts


def _collect_ids(records: dict[str, dict[str, Any]]) -> dict[int, list[str]]:
    targets: dict[int, list[str]] = {}
    for candidate_id, record in records.items():
        result = record.get("source_result") or {}
        metadata = result.get("source_metadata") or {}
        provider_id = metadata.get("id")
        if (
            result.get("source") == "LRCLIB"
            and isinstance(provider_id, int)
            and not isinstance(provider_id, bool)
            and provider_id > 0
            and (
                not isinstance(metadata.get("duration_seconds"), (int, float))
                or not metadata.get("duration_seconds")
                or metadata.get("lyric_representation") not in {"plain", "timestamped_lrc"}
            )
        ):
            targets.setdefault(provider_id, []).append(candidate_id)
    return targets


def _recover_provider_records(
    records: dict[str, dict[str, Any]],
    texts: dict[str, str],
    provider_records: dict[int, dict[str, Any]],
    http_events: dict[int, dict[str, Any]],
) -> tuple[set[str], dict[str, int]]:
    changed: set[str] = set()
    rejected: dict[str, int] = {}
    for candidate_id, record in records.items():
        result = record.get("source_result") or {}
        if result.get("source") != "LRCLIB":
            continue
        metadata = result.get("source_metadata") or {}
        provider_id = metadata.get("id")
        if provider_id not in provider_records:
            continue
        row = provider_records[provider_id]
        event = http_events[provider_id]
        expected_body = texts.get(record.get("text_sha256"))
        actual_text = lrclib_text(row) if not row.get("instrumental") else None
        reason = None
        if row.get("id") != provider_id:
            reason = "provider_id_mismatch"
        elif not identities_compatible(
            (record.get("payload") or {}).get("title"), row.get("trackName")
        ):
            reason = "requested_title_mismatch"
        elif not (
            identities_compatible(
                (record.get("payload") or {}).get("artist"),
                row.get("artistName"),
                is_artist=True,
            )
            or match_lrclib_credit_binding(
                (record.get("payload") or {}).get("title"),
                (record.get("payload") or {}).get("artist"),
                row.get("artistName"),
                metadata,
            )
        ):
            reason = "requested_artist_credit_mismatch"
        elif not isinstance(row.get("duration"), (int, float)) or row.get("duration", 0) <= 0:
            reason = "provider_duration_missing"
        elif not actual_text:
            reason = "provider_full_lyrics_field_missing"
        elif event.get("status") != 200 or not event.get("body_sha256"):
            reason = "raw_http_evidence_missing"
        elif "shared_provider_id_across_editions" in (
            (record.get("audit") or {}).get("text_quality_flags") or []
        ):
            reason = "provider_id_shared_across_editions"
        elif recording_duration_mismatch(
            ((record.get("payload") or {}).get("metadata_resolution") or {}).get(
                "duration_ms"
            ),
            row.get("duration"),
        ):
            reason = "native_recording_duration_mismatch"
        elif prepare_lyric_derivative(actual_text, "LRCLIB").flags:
            reason = "provider_text_quality_flags"
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue

        plain_lyrics = row.get("plainLyrics")
        representation = (
            "plain"
            if isinstance(plain_lyrics, str) and plain_lyrics
            else "timestamped_lrc"
        )
        result["source_metadata"] = {
            **metadata,
            "observed_title": row["trackName"],
            "observed_artist": row["artistName"],
            "duration_seconds": row["duration"],
            "lyric_representation": representation,
            "direct_record_url": event["url"],
            "direct_record_sha256": event["body_sha256"],
        }
        evidence = list(result.get("http_evidence") or [])
        if not any(item.get("url") == event.get("url") for item in evidence):
            evidence.append({**event, "acquisition_stage": "lrclib_direct_record_id_refresh"})
        result["http_evidence"] = evidence
        if actual_text != expected_body:
            previous_hash = record.get("text_sha256")
            new_hash = hashlib.sha256(actual_text.encode("utf-8")).hexdigest()
            texts[new_hash] = actual_text
            record["text_sha256"] = new_hash
            result["text_sha256"] = new_hash
            result["replaces_text_sha256"] = previous_hash
            result["source_metadata"]["direct_id_text_replacement"] = {
                "previous_text_sha256": previous_hash,
                "replacement_text_sha256": new_hash,
                "basis": "exact_provider_record_id_title_artist_duration_and_quality_checks",
            }
        record["source_result"] = result
        changed.add(candidate_id)
    return changed, rejected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--interval", type=float, default=0.75)
    parser.add_argument("--max-requests", type=int)
    parser.add_argument("--cache-source", action="append", type=Path, default=[])
    args = parser.parse_args()
    output = args.out.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise ValueError("output must be a new path inside the project")
    if args.interval < 0.65:
        raise ValueError("LRCLIB public API interval must be at least 0.65 seconds")
    if args.max_requests is not None and args.max_requests < 1:
        raise ValueError("max-requests must be positive")
    output.mkdir(parents=True)
    v4_records, v4_texts = _load_cohort(V4_STAGE, V4_RUN_ID)
    v5_records, v5_texts = _load_cohort(V5_STAGE, V5_RUN_ID)
    targets = _collect_ids(v5_records)
    if not targets:
        raise ValueError("no LRCLIB records with missing direct-record metadata")
    cache = output / "http-cache"
    status_path = output / "status.json"
    results_path = output / "provider-records.json"
    provider_records: dict[int, dict[str, Any]] = {}
    http_events: dict[int, dict[str, Any]] = {}
    result_summary: dict[str, Any] = {
        "schema_version": "lrclib-direct-record-refresh-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "endpoint": "https://lrclib.net/api/get/{id}",
        "target_provider_ids": len(targets),
        "target_candidates_v5": sum(len(ids) for ids in targets.values()),
        "requests_attempted": 0,
        "http_status_counts": {},
        "valid_exact_text_records": 0,
        "candidate_rejections": {},
    }
    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": (
                "ChartObservatoryResearch/1.0 "
                "(https://github.com/limag-henrique/globalMusicsAnalysis)"
            )
        },
    ) as client:
        http = PacedHTTP(
            cache,
            client,
            cache_sources=args.cache_source,
            interval=args.interval,
        )
        for index, provider_id in enumerate(sorted(targets), start=1):
            if args.max_requests is not None and index > args.max_requests:
                break
            url = f"https://lrclib.net/api/get/{provider_id}"
            http.start_trace()
            try:
                response = http.get(url)
                event = next(
                    (dict(item) for item in reversed(http.trace) if item.get("url") == url),
                    {"url": url, "status": response.status_code},
                )
                event["status"] = response.status_code
                if response.status_code == 200:
                    payload = response.json()
                    if isinstance(payload, dict):
                        provider_records[provider_id] = payload
                        http_events[provider_id] = event
                        result_summary["valid_exact_text_records"] += 1
                    else:
                        result_summary["candidate_rejections"]["response_not_object"] = (
                            result_summary["candidate_rejections"].get("response_not_object", 0) + 1
                        )
                result_summary["http_status_counts"][str(response.status_code)] = (
                    result_summary["http_status_counts"].get(str(response.status_code), 0) + 1
                )
            except (httpx.HTTPError, OSError, ValueError, TypeError) as error:
                event = {"url": url, "status": None, "error_type": type(error).__name__}
                result_summary["http_status_counts"]["error"] = (
                    result_summary["http_status_counts"].get("error", 0) + 1
                )
            result_summary["requests_attempted"] += 1
            if index % 25 == 0 or index == len(targets):
                _write_json(
                    status_path,
                    {
                        "stage": "fetching_lrclib_records_by_exact_id",
                        "updated_at": datetime.now(UTC).isoformat(),
                        "completed_provider_ids": index,
                        "target_provider_ids": len(targets),
                        "summary": result_summary,
                        "paid_calls": 0,
                    },
                )
            if event.get("status") == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = max(900, int(retry_after)) if retry_after else 900
                except ValueError:
                    delay = 900
                _write_json(
                    status_path,
                    {
                        "stage": "provider_rate_limit_pause",
                        "updated_at": datetime.now(UTC).isoformat(),
                        "retry_after_seconds": delay,
                        "summary": result_summary,
                        "paid_calls": 0,
                    },
                )
                time.sleep(delay * random.uniform(1.01, 1.15))

    _write_json(
        results_path,
        {
            "summary": result_summary,
            "results": {
                str(key): {
                    "id": value.get("id"),
                    "trackName": value.get("trackName"),
                    "artistName": value.get("artistName"),
                    "albumName": value.get("albumName"),
                    "duration": value.get("duration"),
                    "instrumental": value.get("instrumental"),
                    "has_plain_lyrics": bool(value.get("plainLyrics")),
                    "has_synced_lyrics": bool(value.get("syncedLyrics")),
                    "http_evidence": http_events[key],
                }
                for key, value in provider_records.items()
            },
        },
    )

    v4_changed, v4_rejected = _recover_provider_records(
        v4_records, v4_texts, provider_records, http_events
    )
    v5_changed, v5_rejected = _recover_provider_records(
        v5_records, v5_texts, provider_records, http_events
    )
    result_summary["updated_candidates_v4"] = len(v4_changed)
    result_summary["updated_candidates_v5"] = len(v5_changed)
    result_summary["candidate_rejections"] = {
        "v4": v4_rejected,
        "v5": v5_rejected,
    }
    settings = Settings.load(ROOT)
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 15})
    try:
        cohorts = [
            ("v4", v4_records, v4_texts, v4_changed, V4_SELECTION, 90600),
            ("v5", v5_records, v5_texts, v5_changed, V5_SELECTION, 91480),
        ]
        persisted: dict[str, Any] = {}
        for label, records_map, texts, changed_ids, selection, memberships in cohorts:
            preverified = {
                candidate_id: chain
                for candidate_id, record in records_map.items()
                if candidate_id not in changed_ids
                and (chain := _source_chain_reuse(record)) is not None
            }
            record_list, verification = verify_all_candidates(
                records_map,
                texts,
                ROOT,
                selection_hash=file_hash(selection / "manifest.json"),
                preverified_chains=preverified,
            )
            local_path = output / f"staging-{label}" / "pending-staging.sqlite"
            saved = persist_verified_staging(
                record_list,
                texts,
                selection_dir=selection,
                local_sqlite_path=local_path,
                pg_engine=engine,
                phase="lrclib-direct-id-metadata-refresh",
                memberships_count=memberships,
                extra_manifest={
                    "updated_at": datetime.now(UTC).isoformat(),
                    "parent_run_id": V4_RUN_ID if label == "v4" else V5_RUN_ID,
                    "incrementally_reused_source_chains": len(preverified),
                    "direct_id_rechecks": len(changed_ids),
                    "direct_id_cache_sha256": file_hash(results_path),
                },
            )
            persisted[label] = {
                "run_id": saved["run_id"],
                "local_sqlite": saved["local_sqlite"],
                "candidate_count": len(record_list),
                "candidates_with_text": verification["candidates_with_text"],
                "strict_source_supported": verification["automated_validation_counts"].get(
                    "overall_passed", 0
                ),
                "direct_id_rechecks": len(changed_ids),
                "incrementally_reused_source_chains": len(preverified),
            }
    finally:
        engine.dispose()

    result_summary["new_staging_runs"] = persisted
    result_summary["completed_at"] = datetime.now(UTC).isoformat()
    result_summary["paid_calls"] = 0
    _write_json(output / "summary.json", result_summary)
    _write_json(status_path, {"stage": "persisted_pending_independent_audit", **result_summary})
    print(json.dumps(result_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
