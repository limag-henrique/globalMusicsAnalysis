"""Prepare identity evidence and blind-review instruments locally, without AI calls."""

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from secrets import token_hex

from chart_observatory.lyrics.review_protocol import (
    AUXILIARY_MARKERS,
    BOUNDARY_EXAMPLES,
    PROMPT_VERSION,
    RUBRIC_VERSION,
    TOPICS,
    blind_forms,
    split_verified,
)
from chart_observatory.lyrics.revision_protocol import (
    NORMALIZATION_VERSION,
    RevisionRegistry,
    normalize_text,
    prepare_text_requests,
)

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "data/derived/research_quality/annual-top80-20261024-v2"
REVIEW = ROOT / "data/derived/research_quality/corpus-revision-20261023"


def rows(path):
    if path.exists():
        with path.open("rb") as handle:
            while line := handle.readline():
                if not line.endswith(b"\n"):
                    break  # A live acquisition tail is not a completed record.
                if line.strip():
                    yield json.loads(line)


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def save_rows(path, values):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def acquisition_index(paths, document_keys):
    index = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open("rb") as handle:
            while True:
                offset = handle.tell()
                line = handle.readline()
                if not line or not line.endswith(b"\n"):
                    break
                record = json.loads(line)
                key = record.get("recording_id") or document_keys.get(
                    record["original_document_id"]
                )
                if key:
                    index[key] = {
                        "path": str(path),
                        "offset": offset,
                        "status": record["status"],
                        "agreement": record.get("cross_source_text_agreement"),
                        "source": record.get("source", "unknown"),
                        "flags": record.get("signals", []),
                    }
    return index


def materialize(entry):
    with Path(entry["path"]).open("rb") as handle:
        handle.seek(entry["offset"])
        line = handle.readline()
    return json.loads(line), hashlib.sha256(line).hexdigest()


def prepare(
    prepared,
    output,
    validated_path=None,
    profile_path=None,
    registry_path=None,
    identity_evidence_path=None,
):
    prepared, output = prepared.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "private").mkdir()
    secret = token_hex(32)
    save_json(output / "private/blinding-secret.json", {"secret": secret})
    review_evidence = json.loads(
        (ROOT / "config/lyrics_review_evidence.json").read_text(encoding="utf-8")
    )["entries"]
    comparisons = {
        r["document_id"]: r
        for r in json.loads((REVIEW / "comparison.json").read_text(encoding="utf-8"))
    }
    historical = list(rows(HISTORY / "recovery-targets.jsonl"))
    doc_keys = {r["document_id"]: r["recording_id"] for r in historical}
    doc_keys.update({r["document_id"]: f"SPOTIFY:{r['recording_id']}" for r in review_evidence})
    index = acquisition_index(
        [
            HISTORY / "acquisition/acquisition.jsonl",
            prepared / "acquisition/acquisition.jsonl",
            REVIEW / "recovery-human-20261023/acquisition.jsonl",
        ],
        doc_keys,
    )
    identities = {}
    for row in rows(prepared / "candidates.jsonl"):
        key = row["candidate_id"]
        entity = identities.setdefault(
            key,
            {
                "candidate_id": key,
                "platform": row["platform"],
                "native_id": key.split(":", 1)[1]
                if key.startswith(("SPOTIFY:", "YOUTUBE:"))
                else None,
                "work_id": None,
                "recording_id": None,
                "textual_edition_id": None,
                "isrc": None,
                "identity_decision": "pending",
                "metadata_variants": [],
                "memberships": [],
            },
        )
        metadata = {"title": row["title"], "artist": row["artist"]}
        if metadata not in entity["metadata_variants"]:
            entity["metadata_variants"].append(metadata)
        entity["memberships"].append(
            {k: row[k] for k in ("country_code", "year", "platform", "window", "position")}
        )
    registry_path = registry_path or ROOT / "data/derived/annual_revision/revision-registry.sqlite"
    registry = RevisionRegistry(registry_path)
    with (prepared / "candidates.jsonl").open("rb") as handle:
        artifact_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    registry.record_pending_claims(
        {
            "claim_id": key + ":" + artifact_hash,
            "platform": value["platform"],
            "native_id": value["native_id"],
            "metadata": {
                "variants": value["metadata_variants"],
                "cohort_memberships": value["memberships"],
            },
            "evidence": {
                "source": str(prepared / "candidates.jsonl"),
                "artifact_sha256": artifact_hash,
                "identity_verified": False,
                "native_id_absent": value["native_id"] is None,
            },
        }
        for key, value in identities.items()
    )
    for key, identity in identities.items():
        acquisition = index.get(key, {}).get("status")
        identity["acquisition_state"] = {
            "candidate_pending_validation": "recovered",
            "not_found": "unavailable",
        }.get(acquisition, "pending")
        identity["identity_state"] = "pending"
        identity["integrity_state"] = "pending"
        identity["textual_analysis_applicability"] = "pending"
    save_rows(output / "identities-and-equivalences.jsonl", identities.values())
    diagnostics = []
    for report in review_evidence:
        old = comparisons.get(report["document_id"], {})
        case = {
            "title": report["title"],
            "artist": report["artist"],
            "document_id": report["document_id"],
            "original_hash": report["lyrics_hash"],
            "spotify_id_claim": report["recording_id"],
            "human_report": report["justification"],
            "ai_exposed": report.get("ai_exposed"),
            "reported_problem": report["decision"],
            "historical_raw_import_matches_stored_text": old.get("raw_import_matches_stored_text"),
            "candidate_hash": old.get("candidate_hash"),
            "candidate_differs": old.get("candidate_differs"),
            "candidate_status": old.get("candidate_status", "pending"),
            "diagnosis": "Defeito reportado já rastreado no artefato histórico; "
            "a causa e a integridade do substituto exigem adjudicação.",
            "decision": "pending_adjudication",
            "classification_blocked": True,
        }
        if report["title"] == "Culpable":
            case.update(
                diagnosis="Associação de identidade contestada; Culpable e Culpables "
                "não serão unidos por semelhança do título.",
                alternative_spotify_id="6n5NCZLglzqbYFgadmcOqP",
                alternative_is_confirmed=False,
                discovery_evidence=str(REVIEW / "culpable-discovery.json"),
            )
            if identity_evidence_path:
                case["official_platform_metadata"] = json.loads(
                    identity_evidence_path.read_text(encoding="utf-8")
                )
                case["textual_equivalence_confirmed"] = False
        diagnostics.append(case)
    save_rows(output / "eight-case-diagnostics.jsonl", diagnostics)
    # Integrity triage precedes the thematic pilot; these are not eligible pilot items.
    priorities = [f"SPOTIFY:{r['recording_id']}" for r in review_evidence]
    candidates = [
        (key, entity)
        for key, entity in identities.items()
        if key in index and index[key]["status"] == "candidate_pending_validation"
    ]
    strata = defaultdict(list)
    for key, entity in candidates:
        entry = index[key]
        risk = "high" if entry["agreement"] is False or entry["flags"] else "unknown"
        period = min(r["year"] for r in entity["memberships"])
        strata[entry["source"], period, risk].append(key)
    for values in strata.values():
        values.sort(key=lambda key: (-len(identities[key]["memberships"]), key))
    chosen = list(dict.fromkeys(key for key in priorities if key in index))
    while len(chosen) < 80 and any(strata.values()):
        for stratum in sorted(strata):
            if strata[stratum]:
                key = strata[stratum].pop(0)
                if key not in chosen:
                    chosen.append(key)
                if len(chosen) == 80:
                    break
    mapping, triage = [], []
    for key in chosen:
        record, row_hash = materialize(index[key])
        variants = record.get("variants") or ([record] if record.get("text") else [])
        triage.append((key, record, variants, row_hash))
    import hmac

    for reviewer in ("A", "B"):
        cards = []
        for key, record, variants, row_hash in triage:
            token = hmac.new(secret.encode(), f"{reviewer}:{key}".encode(), "sha256").hexdigest()[
                :20
            ]
            public_variants = []
            for number, variant in enumerate(variants):
                variant_id = f"{token}-{number + 1}"
                public_variants.append(
                    {
                        "variant_id": variant_id,
                        "text": variant["text"],
                        "identity_verdict": None,
                        "integrity_verdict": None,
                        "language": None,
                        "edition_kind": None,
                        "evidence_urls": [],
                        "notes": None,
                    }
                )
                mapping.append(
                    {
                        "reviewer": reviewer,
                        "review_id": token,
                        "variant_id": variant_id,
                        "candidate_id": key,
                        "source": variant.get("source"),
                        "lyrics_hash": variant.get("lyrics_hash"),
                        "ledger_row_sha256": row_hash,
                    }
                )
            cards.append(
                {
                    "review_id": token,
                    "title": record["title"],
                    "artist": record["artist"],
                    "stage": "integrity_triage_not_thematic_pilot",
                    "variants": public_variants,
                }
            )
        save_rows(
            output / f"integrity-review-{reviewer}.jsonl",
            sorted(cards, key=lambda c: c["review_id"]),
        )
    save_rows(output / "private/integrity-review-mapping.jsonl", mapping)
    verified = list(rows(validated_path)) if validated_path else []
    for row in verified:
        text = normalize_text(row["text"])
        if row.get("original_hash") != text.original_hash:
            raise ValueError("validated edition original hash mismatch")
        if row.get("normalized_hash") != text.normalized_hash:
            raise ValueError("validated edition text/hash mismatch")
        if row.get("normalization_version") != NORMALIZATION_VERSION:
            raise ValueError("validated edition uses an incompatible normalization")
        if row.get("candidate_id") in priorities:
            row["historical_review"] = True
        registry.register_edition(
            row["text_identity_id"],
            text.normalized_hash,
            text.version,
            original_hash=text.original_hash,
            identity_confirmed=row.get("identity_confirmed") is True,
            integrity_validated=row.get("integrity_validated") is True,
            instrumental=row.get("instrumental") is True,
            language=row.get("language"),
            edition_kind=row.get("edition_kind", "unknown"),
            evidence=row.get("evidence"),
        )
    requests = {"requests": [], "reused_keys": []}
    if profile_path:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        requests = prepare_text_requests(verified, profile, registry)
    save_rows(output / "classification-requests-v2.jsonl", requests["requests"])
    split = split_verified(verified)
    for name in ("pilot", "validation"):
        for reviewer in ("A", "B"):
            cards, private = blind_forms(split[name], f"{name}-{reviewer}", secret)
            save_rows(output / f"{name}-{reviewer}.jsonl", cards)
            save_rows(output / f"private/{name}-{reviewer}-mapping.jsonl", private)
    rubric = {
        "version": RUBRIC_VERSION,
        "status": "draft_not_approved",
        "presence_threshold": 2,
        "scale": {"0": "ausente", "1": "incidental", "2": "substancial", "3": "central"},
        "topics": {k: {"label": v[0], "definition": v[1]} for k, v in TOPICS.items()},
        "auxiliary_markers": AUXILIARY_MARKERS,
        "boundary_examples": BOUNDARY_EXAMPLES,
    }
    save_json(output / "rubric-v2-draft.json", rubric)
    save_json(
        output / "quality-criteria-proposal.json",
        {
            "status": "proposed_not_accepted",
            "accept_before_evaluation": True,
            "pilot_target": 80,
            "independent_validation_target": 240,
            "presence_threshold": 2,
            "minimum_scored_coverage": 0.98,
            "per_topic": {
                "quadratic_weighted_kappa": 0.80,
                "precision": 0.90,
                "sensitivity": 0.90,
                "precision_95_lower_bound": 0.80,
                "sensitivity_95_lower_bound": 0.80,
                "minimum_reference_positives": 30,
                "minimum_reference_negatives": 30,
            },
            "support_inadequate": "exploratory_or_collect_more_adjudicated_examples",
            "sample_size_warning": "240 does not ensure support in each topic/language",
            "model_comparison": "economic_vs_reference_on_same_adjudicated_pilot_subset",
            "model_ids": None,
            "model_selection": "pending_criteria_and_human_validation",
        },
    )
    prompt = """DRAFT — not approved for production.
Analyze only the supplied original-language lyric. Do not reconstruct missing text.
Use the 26 rubric intensities and preserve threshold >=2 for comparison.
Keep mention, depiction and endorsement separate. Desire is not an explicit act;
sexual agency is not objectification; self-love is not romance; money is not materialism.
Record negation, quotation, fiction, satire, metaphor, stance and language switching
as auxiliary markers. Unknown or insufficient evidence is not absence.
Instrumental or unscorable texts receive an explicit status, without 26 zero scores.
Country, popularity, acquisition supplier and earlier labels must not be supplied.
"""
    (output / "prompt-v4-draft.txt").write_text(prompt, encoding="utf-8")
    template = {
        "review_id": None,
        "identity_verdict": None,
        "integrity_verdict": None,
        "classification_status": None,
        "scores": dict.fromkeys(TOPICS),
        "markers": dict.fromkeys(AUXILIARY_MARKERS),
        "evidence_notes": None,
    }
    save_json(output / "blind-assessment-template.json", template)
    save_json(
        output / "classification-profile-template.json",
        {
            "rubric_version": RUBRIC_VERSION,
            "prompt_version": PROMPT_VERSION,
            "model_id": None,
            "configuration": {
                "resolved": False,
                "provider_model_version": None,
                "execution_mode": None,
                "system_instruction_sha256": None,
                "response_schema_version": "review-assessment-v2-draft1",
                "generation_parameters": {
                    "temperature": None,
                    "top_p": None,
                    "top_k": None,
                    "thinking_level": None,
                    "max_output_tokens": None,
                    "safety_settings": None,
                },
            },
        },
    )
    save_json(
        output / "adjudication-template.json",
        {
            "review_A_id": None,
            "review_B_id": None,
            "adjudicator_id": None,
            "text_identity_id": None,
            "normalized_hash": None,
            "decision": None,
            "classification_status": None,
            "scores": dict.fromkeys(TOPICS),
            "disagreements_resolved": [],
            "evidence": [],
            "reviewed_at": None,
        },
    )
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "rubric_version": RUBRIC_VERSION,
        "prompt_version": PROMPT_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "identity_claims": len(identities),
        "equivalences_confirmed": 0,
        "eight_cases": len(diagnostics),
        "integrity_triage_music": len(triage),
        "pilot_music": len(split["pilot"]),
        "pilot_deficit": split["pilot_deficit"],
        "validation_music": len(split["validation"]),
        "validation_deficit": split["validation_deficit"],
        "reviewers_assigned": False,
        "criteria_accepted": False,
        "classification_requests": len(requests["requests"]),
        "compatible_results_reused": len(requests["reused_keys"]),
        "paid_calls": 0,
        "historical_database_writes": 0,
        "persistent_registry": str(registry_path),
        "privacy": "Keep private mappings, reviewer assignments and lyrics local",
        "states": [
            "recovered",
            "identity_confirmed",
            "integrity_validated",
            "pending",
            "unavailable",
            "not_applicable_to_textual_analysis",
        ],
    }
    save_json(output / "manifest.json", manifest)
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validated-editions", type=Path)
    parser.add_argument("--classification-profile", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--identity-metadata-evidence", type=Path)
    args = parser.parse_args()
    prepare(
        args.prepared,
        args.output,
        args.validated_editions,
        args.classification_profile,
        args.registry,
        args.identity_metadata_evidence,
    )
