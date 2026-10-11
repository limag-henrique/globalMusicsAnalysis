"""Local-only full corpus cost projection; never uploads or generates."""

import json
from collections import Counter
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from chart_observatory.config import Settings
from chart_observatory.db.models.corpus import LyricDocument
from chart_observatory.db.models.lyrics_batch import (
    LyricClassificationBatchItem,
    LyricClassificationBatchRun,
)
from chart_observatory.lyrics.batch_jsonl import (
    BatchJsonlArtifact,
    build_batch_request,
    estimate_batch_cost,
)
from chart_observatory.lyrics.batch_repository import BatchRepository
from chart_observatory.lyrics.batch_service import BatchClassificationService
from chart_observatory.lyrics.classification import PROMPT_VERSION, TAXONOMY_VERSION
from chart_observatory.lyrics.classification_queue import (
    ClassificationCandidate,
    ClassificationSignature,
    iter_remaining_candidates,
    local_classification_status,
)
from chart_observatory.lyrics.continuous import TECHNICAL_RESPONSE_ERRORS
from chart_observatory.lyrics.gemini_pipeline import build_lyrics_generation_config


def main():
    root = Path(__file__).resolve().parents[1]
    settings = Settings.load(root)
    endpoint = make_url(settings.database_url)
    if endpoint.host != "127.0.0.1" or endpoint.port != 56433:
        raise ValueError("unexpected database endpoint")
    directory = root / "data/derived/lyrics/budget-20261008"
    evidence = json.loads((directory / "billing-policy.json").read_text())
    signature = ClassificationSignature(settings.gemini_model, TAXONOMY_VERSION, PROMPT_VERSION)
    selected = {}
    baseline_ids = []
    with Session(create_engine(settings.database_url)) as session:
        repository = BatchRepository(session)
        for run in session.scalars(
            select(LyricClassificationBatchRun).order_by(LyricClassificationBatchRun.created_at)
        ):
            candidates = repository.error_retry_candidates(
                run.id,
                TECHNICAL_RESPONSE_ERRORS,
                include_identity_holds=True,
            )
            if candidates:
                baseline_ids.append(str(run.id))
            for candidate in candidates:
                document = session.get(LyricDocument, candidate.lyric_document_id)
                selected.setdefault(
                    (document.canonical_track_id, document.content_sha256),
                    (document, candidate.prior_snapshot_id),
                )
        for candidate in iter_remaining_candidates(session, signature, include_identity_holds=True):
            if local_classification_status(candidate) is None:
                selected.setdefault(
                    (candidate.canonical_track_id, candidate.lyrics_hash),
                    (session.get(LyricDocument, candidate.lyric_document_id), None),
                )
        sources = Counter()
        total_bytes = count = 0
        config = build_lyrics_generation_config(settings.gemini_model, "LOW", 1024)
        for document, _snapshot in selected.values():
            candidate = ClassificationCandidate(
                document.id,
                document.canonical_track_id,
                document.content_sha256,
                document.text,
                document.language_code,
                False,
            )
            if local_classification_status(candidate) is not None:
                continue
            item = LyricClassificationBatchItem(opaque_key=uuid4(), lyric_document_id=document.id)
            payload = build_batch_request(item, candidate, config)
            total_bytes += (
                len(
                    json.dumps(
                        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                )
                + 1
            )
            count += 1
            sources[document.source] += 1
        service = BatchClassificationService(
            session, settings, SimpleNamespace(), SimpleNamespace()
        )
        estimate = estimate_batch_cost(
            [
                BatchJsonlArtifact(
                    Path("not_written.jsonl"), "0" * 64, total_bytes, count, uuid4(), uuid4()
                )
            ],
            None,
            service._pilot_usage(),
            service._rate_card(),
            1024,
        )
        scale = max(
            Decimal(evidence["input_brl_per_million"]) / Decimal("0.375"),
            Decimal(evidence["output_brl_per_million"]) / Decimal("1.875"),
        )
        expected = estimate.expected_cost_usd * scale
        bound = estimate.conservative_cost_usd * scale
        # Five percent of the entire byte/output allowance for one bounded technical re-analysis.
        retry = (bound * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
        evidence["retry_reserve_brl"] = str(retry)
        evidence["retry_reserve_method"] = (
            "5% of full remaining input-byte plus 1024 output-token bound; "
            "one additional retry per newly attempted document"
        )
        (directory / "billing-policy.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
        plan = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "remaining_provider_documents": count,
            "sources": dict(sources),
            "request_bytes": total_bytes,
            "expected_remaining_brl": str(expected),
            "conservative_remaining_brl": str(bound),
            "retry_reserve_brl": str(retry),
            "baseline_run_ids": ["remaining_corpus", *baseline_ids, "bounded_reanalysis"],
            "retains_identity_flags": True,
            "paid_api_calls": 0,
            "budget_brl": "3500",
            "current_account_credit_brl": evidence["current_account_credit_brl"],
            "second_account_credit_verified": False,
        }
        (directory / "corpus-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {key: value for key, value in plan.items() if key != "baseline_run_ids"}, indent=2
            )
        )


if __name__ == "__main__":
    main()
