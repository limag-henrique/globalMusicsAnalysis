"""Prepare a local, hash-bound Vertex dossier. No SDK clients, upload or inference."""

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from chart_observatory.config import Settings
from chart_observatory.db.models.corpus import LyricDocument
from chart_observatory.lyrics.classification import PROMPT_VERSION, TAXONOMY_VERSION
from chart_observatory.lyrics.classification_gate import ClassificationGate
from chart_observatory.lyrics.gemini_pipeline import (
    build_lyrics_generation_config,
    build_lyrics_prompt,
    lyrics_response_json_schema,
)
from chart_observatory.lyrics.quota_staging import candidates, runs
from chart_observatory.lyrics.revision_budget import RevisionBudgetPolicy

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def validate_prices(prices, settings, today):
    if (
        not date.fromisoformat(prices["verified_on"])
        <= today
        <= date.fromisoformat(prices["valid_through"])
    ):
        raise ValueError("pricing evidence is expired or from the future")
    if (
        prices["model_id"] != settings.gemini_model
        or prices["location"] != settings.google_cloud_location
        or prices["mode"] != "batch"
        or Decimal(prices["input_per_million_tokens"])
        != settings.gemini_batch_input_usd_per_million_tokens
        or Decimal(prices["output_including_reasoning_per_million_tokens"])
        != settings.gemini_batch_output_usd_per_million_tokens
    ):
        raise ValueError("configured batch prices/model/location differ from official evidence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "data/runtime"):
        parser.error("dossier must remain in project data/runtime")
    out.mkdir(parents=True, exist_ok=False)
    settings = Settings.load(ROOT)
    prices_path = ROOT / "config/vertex_price_evidence_20261108.json"
    prices = json.loads(prices_path.read_text())
    validate_prices(prices, settings, datetime.now(UTC).date())
    config = build_lyrics_generation_config(
        settings.gemini_model, settings.gemini_thinking_level, 1024
    )
    save(out / "prices.json", prices)
    save(out / "response-schema.json", lyrics_response_json_schema())
    save(out / "generation-config.json", config.model_dump(mode="json", exclude_none=True))
    (out / "prompt-template.txt").write_text(
        build_lyrics_prompt("{{APPROVED_LYRICS_ONLY}}", None), encoding="utf-8"
    )
    implementation = {}
    for name in (
        "classification.py",
        "gemini_pipeline.py",
        "classification_gate.py",
        "batch_service.py",
        "batch_jsonl.py",
        "batch_quality.py",
    ):
        implementation[name] = hashlib.sha256(
            (ROOT / "src/chart_observatory/lyrics" / name).read_bytes()
        ).hexdigest()
    save(
        out / "protocol.json",
        dict(
            model=settings.gemini_model,
            location=settings.google_cloud_location,
            taxonomy=TAXONOMY_VERSION,
            prompt=PROMPT_VERSION,
            implementation=implementation,
            scope="frozen country-year quotas 2018-2026, partial 2026 cutoff 2026-10-15",
            content_frozen=True,
            scientific_acceptance=False,
            pilot=dict(
                canary=1,
                subsequent_pilot=99,
                required_total=100,
                executed=False,
                reason="no paid calls authorized",
            ),
        ),
    )
    ledger_source = ROOT / "data/derived/annual_revision/runtime/campaign-budget.sqlite"
    ledger_copy = out / "local-budget-reconciliation.sqlite"
    with (
        sqlite3.connect(ledger_source.as_uri() + "?mode=ro", uri=True) as src,
        sqlite3.connect(ledger_copy) as dst,
    ):
        src.backup(dst)
    engine = create_engine(settings.database_url)
    gate = ClassificationGate.load()
    counts, approvals = Counter(), Counter()
    try:
        with Session(engine) as session:
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            run = session.execute(
                select(runs.c.id).order_by(runs.c.created_at.desc()).limit(1)
            ).scalar_one()
            with (out / "pending-candidates.jsonl").open("w", encoding="utf-8") as queue:
                for row in session.execute(
                    select(candidates).where(candidates.c.run_id == run)
                ).mappings():
                    counts["total"] += 1
                    counts["with_text" if row["text_sha256"] else "without_text"] += 1
                    queue.write(
                        json.dumps(
                            dict(
                                run_id=run,
                                candidate_id=row["candidate_id"],
                                title=row["payload"].get("title"),
                                artist=row["payload"].get("artist"),
                                lyrics_hash=row["text_sha256"],
                                audit=row["audit"],
                                approval="pending",
                                classification_ready=False,
                            ),
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
            approved_docs = session.scalars(
                select(LyricDocument).where(
                    text("metadata_json->'classification_adjudication' IS NOT NULL")
                )
            )
            for document in approved_docs:
                approvals[gate.assess(document).reason] += 1
            budget = RevisionBudgetPolicy(budget_path=ledger_copy).reconcile(session).snapshot()
        save(
            out / "budget.json",
            dict(
                local_database_ledger=budget,
                production_ledger_modified=False,
                provider_billing_export_verified=False,
                effective_ceilings_usd=dict(quota_selection="150", revision_campaign="180"),
                spendable_usd="0",
                note="Local records do not attest the external billing account.",
            ),
        )
        save(
            out / "readiness.json",
            dict(
                run_id=run,
                inventory=dict(counts),
                canonical_adjudications=dict(approvals),
                submission_ready=False,
                paid_calls=0,
                uploads=0,
                production_writes=0,
                blockers=[
                    "identity_and_complete_transcription_evidence",
                    "approved_candidate_to_canonical_document_binding",
                    "rights_for_vertex_processing",
                    "scientific_protocol_acceptance",
                    "external_billing_reconciliation",
                    "accepted_100_item_paid_pilot",
                ],
                request_file_generated=False,
            ),
        )
    finally:
        engine.dispose()
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()
    }
    save(out / "manifest.json", dict(created_at=datetime.now(UTC).isoformat(), sha256=manifest))
    print(json.dumps(dict(output=str(out), inventory=dict(counts), paid_calls=0, ready=False)))


if __name__ == "__main__":
    main()
