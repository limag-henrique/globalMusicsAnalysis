"""Research gates against frozen synthetic inputs; no database or provider calls."""

import copy
import csv
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from chart_observatory import research_flow as flow
from chart_observatory.lyrics.classification_gate import ClassificationGate
from chart_observatory.lyrics.review_protocol import TOPICS
from chart_observatory.research_validation import build_split_manifest


def _save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return {"path": str(path), "sha256": flow.file_hash(path)}


def _jsonl(path, values):
    path.write_text("".join(json.dumps(row) + "\n" for row in values), encoding="utf-8")


def _freeze(selection, cells, members):
    _jsonl(selection / "country_years.jsonl", cells)
    _jsonl(selection / "combined.jsonl", members)
    manifest = {
        "protocol": "worldwide-annual-quotas-v1",
        "years": list(range(2018, 2027)),
        "cutoff": "2026-10-15",
        "countries": len({c["country_code"] for c in cells}),
        "country_year_cells": len(cells),
        "memberships": len(members),
        "requested_positions": sum(c["quota"] or 0 for c in cells),
        "output_hashes": {
            name: flow.file_hash(selection / name)
            for name in ("country_years.jsonl", "combined.jsonl")
        },
    }
    _save(selection / "manifest.json", manifest)
    return manifest


def test_load_selection_rejects_hash_valid_but_malformed_source_coverage(frozen):
    coverage_path = frozen.selection / "source_coverage.json"
    coverage_path.write_text(json.dumps(["country_code"]), encoding="utf-8")
    manifest_path = frozen.selection / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_hashes"]["source_coverage.json"] = flow.file_hash(coverage_path)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(TypeError, match=r"source_coverage\[0\]\[0\] must be an object"):
        flow.load_selection(frozen.selection)


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    selection = tmp_path / "selection"
    selection.mkdir()
    cells = [
        {
            "country_code": code,
            "year": year,
            "quota": 5,
            "ranking_period_end": "2026-10-15" if year == 2026 else f"{year}-12-31",
        }
        for code in ("BR", "PT")
        for year in range(2018, 2027)
    ]
    members = [
        {
            "country_code": cell["country_code"],
            "year": cell["year"],
            "position": position,
            "candidate_id": f"SPOTIFY:synthetic-{position}",
            "title": f"Synthetic {position}",
            "artist": "Synthetic Artist",
            "platform": "SPOTIFY",
            "provider": "SYNTHETIC_FIXTURE",
            "coverage_status": "COMPLETE",
            "selection_status": "QUOTA_FILLED",
            "metric_value": (100 - position)
            * (
                (date.fromisoformat(cell["ranking_period_end"]) - date(cell["year"], 1, 1)).days + 1
            ),
        }
        for cell in cells
        for position in range(1, 5)
    ]
    manifest = _freeze(selection, cells, members)
    gate = ClassificationGate(frozenset(), frozenset(), frozenset())
    monkeypatch.setattr(flow.ClassificationGate, "load", lambda: gate)
    return SimpleNamespace(
        project=tmp_path,
        selection=selection,
        cells=cells,
        members=members,
        manifest=manifest,
        gate=gate,
    )


def _rank_evidence(frozen):
    project = frozen.project
    review_ref = _save(project / "proof/rank-review.json", {"synthetic_review": True})
    sources = {}
    for cell in frozen.cells:
        start = date(cell["year"], 1, 1)
        end = date.fromisoformat(cell["ranking_period_end"])
        observations = [
            {
                "country_code": cell["country_code"],
                "platform": "SPOTIFY",
                "provider": "SYNTHETIC_FIXTURE",
                "period_start": period.isoformat(),
                "period_end": period.isoformat(),
                "candidate_id": f"SPOTIFY:synthetic-{position}",
                "position": position,
                "metric_value": 100 - position,
                "title": f"Synthetic {position}",
                "artist": "Synthetic Artist",
            }
            for day in range((end - start).days + 1)
            for period in [start + timedelta(days=day)]
            for position in range(1, 6)
        ]
        path = project / f"proof/observations-{cell['country_code']}-{cell['year']}.jsonl"
        _jsonl(path, observations)
        sources[cell["country_code"], cell["year"]] = {
            "path": str(path),
            "sha256": flow.file_hash(path),
        }
    ranks = []
    for row in frozen.members:
        slug = f"{row['country_code']}-{row['year']}-{row['position']}"
        definition = {
            "country_code": row["country_code"],
            "platform": row["platform"],
            "provider": row["provider"],
            "frequency": "daily",
            "metric": "streams",
            "period_start": f"{row['year']}-01-01",
            "period_end": "2026-10-15" if row["year"] == 2026 else f"{row['year']}-12-31",
            "depth": 5,
            "quota": 5,
            "observation_artifact": sources[row["country_code"], row["year"]],
            "source_url": "https://example.org/synthetic-chart",
            "retrieved_at": "2026-11-01T00:00:00Z",
            "ranking_kind": "observed_chart_sum",
            "calendar_verified": True,
            "depth_verified": True,
            "identity_verified": True,
            "boundary_tie_resolved": True,
        }
        ranks.append(
            {
                "country_code": row["country_code"],
                "year": row["year"],
                "position": row["position"],
                "row_sha256": flow.object_hash(row),
                "reconstructed_row": _save(project / f"proof/{slug}.json", row),
                "source_definition": _save(project / f"proof/{slug}-definition.json", definition),
                "source_files": [sources[row["country_code"], row["year"]]],
                "review": {
                    "actor": "synthetic-rank-reviewer",
                    "at": "2026-11-02T00:00:00Z",
                    "evidence": review_ref,
                },
            }
        )
    return {
        "schema_version": "research-evidence-v4",
        "selection_sha256": flow.file_hash(frozen.selection / "manifest.json"),
        "rankings": ranks,
        "lyrics": [],
        "preparations": [],
        "results": [],
    }


def _audit(frozen, *, evidence=None, output_name="audit", documents=None):
    evidence_path = None
    if evidence is not None:
        evidence_path = frozen.project / f"{output_name}-evidence.json"
        _save(evidence_path, evidence)
    return flow.audit_research_flow(
        project=frozen.project,
        selection=frozen.selection,
        output=frozen.project / output_name,
        actor="synthetic-auditor",
        gate_policy="legacy80-v4",
        evidence_path=evidence_path,
        document_reader=lambda project, ids: documents or {},
    )


def _canonical(frozen, candidate_index=1):
    text = f"Synthetic complete lyric {candidate_index}.\nRepeated chorus.\nRepeated chorus.\n"
    identifier, recording = uuid4(), uuid4()
    digest = hashlib.sha256(text.encode()).hexdigest()
    canonical_evidence = _save(
        frozen.project / f"proof/canonical-evidence-{candidate_index}.json",
        {"synthetic_audio_comparison": True, "document_id": str(identifier), "text_sha256": digest},
    )
    document = SimpleNamespace(
        id=identifier,
        canonical_track_id=recording,
        source="SYNTHETIC_FIXTURE",
        language_code="pt",
        text=text,
        content_sha256=digest,
        rights_status="AUTHORIZED",
        metadata_json={
            "research_candidate_ids": [f"SPOTIFY:synthetic-{candidate_index}"],
            "classification_adjudication": {
                "gate_version": "lyrics-classification-gate-v1",
                "adjudication_id": "synthetic-decision",
                "document_id": str(identifier),
                "recording_id": str(recording),
                "lyrics_hash": digest,
                "source": "SYNTHETIC_FIXTURE",
                "status": "approved",
                "identity_verified": True,
                "integrity_verified": True,
                "method": "human_audio_verification",
                "evidence_url": "https://example.org/synthetic-audio",
                "evidence_sha256": canonical_evidence["sha256"],
                "verified_at": "2026-11-01T00:00:00Z",
                "adjudicated_at": "2026-11-02T00:00:00Z",
                "adjudicator": "synthetic-third",
            },
        },
    )
    rights = _save(
        frozen.project / f"proof/rights-{candidate_index}.json",
        {
            "schema_version": "research-rights-v1",
            "document_id": str(identifier),
            "text_sha256": digest,
            "source_url": "https://example.org/rights",
            "storage": {
                "authorized": True,
                "basis": "Synthetic test storage grant",
                "evidence": _save(
                    frozen.project / f"proof/rights-storage-{candidate_index}.json",
                    {"scope": "storage"},
                ),
            },
            "processing": {
                "authorized": True,
                "basis": "Synthetic test processing grant",
                "evidence": _save(
                    frozen.project / f"proof/rights-processing-{candidate_index}.json",
                    {"scope": "processing"},
                ),
            },
            "publication": {
                "authorized": False,
                "basis": "Publication is not granted in this synthetic fixture",
                "evidence": _save(
                    frozen.project / f"proof/rights-publication-{candidate_index}.json",
                    {"scope": "publication", "authorized": False},
                ),
            },
            "vertex_authorizations": [
                {
                    "authorized": True,
                    "basis": "Synthetic exact Vertex processing grant",
                    "provider": "vertex_ai",
                    "model_id": "synthetic-model",
                    "resolved_model_version": "synthetic-001",
                    "region": "us-central1",
                    "retention_days": 0,
                    "evidence": _save(
                        frozen.project / f"proof/rights-vertex-{candidate_index}.json",
                        {"scope": "vertex", "authorized": True},
                    ),
                }
            ],
        },
    )
    review_ref = _save(
        frozen.project / f"proof/text-review-{candidate_index}.json", {"synthetic_review": True}
    )
    competence_ref = _save(
        frozen.project / f"proof/language-competence-{candidate_index}.json",
        {"language": "pt", "level": "fluent", "basis": "synthetic test fixture"},
    )
    approval = {
        "candidate_id": f"SPOTIFY:synthetic-{candidate_index}",
        "document_id": str(identifier),
        "text_sha256": digest,
        "rights_evidence": rights,
        "canonical_evidence": canonical_evidence,
        "reviews": [
            {
                "actor": actor,
                "at": "2026-11-02T00:00:00Z",
                "evidence": review_ref,
                "document_id": str(identifier),
                "text_sha256": digest,
                "identity_verified": True,
                "integrity_verified": True,
                "completeness_verified": True,
                "truncation_checked": True,
                "contamination_checked": True,
                "language_code": "pt",
                "language_competence": "fluent Portuguese (synthetic fixture)",
                "competence_evidence": competence_ref,
                "method": "human_audio_verification",
            }
            for actor in ("synthetic-reviewer-a", "synthetic-reviewer-b")
        ],
    }
    return document, approval


def _validation_split(frozen, requests, documents, validation_request, validation_group):
    development_request = next(
        request
        for request in requests.values()
        if request["edition_id"] != validation_request["edition_id"]
    )

    def row(request, group):
        document = documents[request["edition_id"]]
        return {
            "text_identity_id": request["edition_id"],
            "text": "".join(part["text"] for part in request["segments"]),
            "equivalence_group": group,
            "recording_id": str(document.canonical_track_id),
            "work_id": "work-" + str(document.id),
            "language": request["language"],
        }

    split = build_split_manifest(
        [row(development_request, "development-" + development_request["edition_id"])],
        [row(validation_request, validation_group)],
        development_target=1,
        validation_target=1,
        seed="synthetic-frozen-split-v1",
    )
    return _save(frozen.project / "proof/validation-split.json", split)


def test_load_selection_preserves_all_cells_and_exact_denominator(frozen):
    manifest, cells, memberships, hashes = flow.load_selection(frozen.selection)
    assert manifest["requested_positions"] == 90
    assert len(cells) == 18
    assert len(memberships) == 72
    assert {c["year"] for c in cells} == set(range(2018, 2027))
    assert len(hashes) == 3


def test_legacy_research_evidence_requires_explicit_v2_reannotation(frozen):
    legacy = _rank_evidence(frozen)
    legacy.pop("schema_version")
    with pytest.raises(ValueError):
        flow.ResearchEvidence.model_validate(legacy)


def test_load_selection_rejects_changed_output_even_if_json_still_valid(frozen):
    frozen.members[0]["metric_value"] = 999
    _jsonl(frozen.selection / "combined.jsonl", frozen.members)
    with pytest.raises(ValueError, match="missing or changed"):
        flow.load_selection(frozen.selection)


@pytest.mark.parametrize(
    "change", ["duplicate_slot", "duplicate_identity", "missing_cell", "cutoff"]
)
def test_load_selection_rejects_ambiguous_or_reduced_universe(frozen, change):
    if change == "duplicate_slot":
        frozen.members.append(copy.deepcopy(frozen.members[0]))
    elif change == "duplicate_identity":
        frozen.members[1]["candidate_id"] = frozen.members[0]["candidate_id"]
    elif change == "missing_cell":
        frozen.cells.pop()
        frozen.members = [
            r for r in frozen.members if not (r["country_code"] == "PT" and r["year"] == 2026)
        ]
    manifest = _freeze(frozen.selection, frozen.cells, frozen.members)
    if change == "cutoff":
        manifest["cutoff"] = "2026-11-09"
        _save(frozen.selection / "manifest.json", manifest)
    with pytest.raises(ValueError):
        flow.load_selection(frozen.selection)


@pytest.mark.parametrize("numerator,expected", [(79, "reprovado"), (80, "aprovado")])
def test_gate_uses_exact_eighty_percent_boundary(numerator, expected):
    report = flow.evaluate_gate("G1", [(("BR", 2019), numerator, 100)])
    assert report["state"] == expected


def test_gate_cannot_hide_one_bad_cell_behind_global_average():
    report = flow.evaluate_gate("G1", [(("BR", 2019), 99, 100), (("PT", 2019), 79, 100)])
    assert report["ratio"] == 0.89
    assert report["state"] == "reprovado"
    assert report["approved_cells"] == 1


def test_unknown_or_empty_denominator_never_passes():
    report = flow.evaluate_gate("G1", [(("BR", 2019), 100, 100), (("AQ", 2019), 0, None)])
    assert report["unknown_denominators"] == 1
    assert report["state"] == "reprovado"
    assert flow.evaluate_gate("G2", [(("BR", 2019), 0, 0)])["state"] == "reprovado"
    assert flow.evaluate_gate("G1", [])["state"] == "reprovado"


def test_predecessor_and_explicit_blockers_prevent_advance():
    counts = [(("BR", 2019), 100, 100)]
    assert flow.evaluate_gate("G2", counts, predecessor=False)["state"] == "pendente"
    assert (
        flow.evaluate_gate("G1", counts, extra_blockers=["missing_evidence"])["state"]
        == "reprovado"
    )


def test_current_unapproved_corpus_exports_null_scores_and_all_deficits(frozen):
    report = _audit(frozen)
    assert report["inventory"]["observed_coverage"] == 0.8
    assert report["inventory"]["scientifically_verified_positions"] == 0
    assert [g["state"] for g in report["gates"]] == [
        "reprovado",
        "pendente",
        "pendente",
        "pendente",
        "pendente",
    ]
    assert not report["research_ready"]
    assert report["paid_calls"] == report["uploads"] == 0
    with (frozen.project / "audit/preparatory-table.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        table = list(csv.DictReader(handle))
    assert len(table) == 72
    assert all(row[topic] == "" for row in table for topic in TOPICS)
    assert len(list(flow.rows(frozen.project / "audit/ranking-recovery-queue.jsonl"))) == 18
    assert len(list(flow.rows(frozen.project / "audit/lyric-review-queue.jsonl"))) == 4
    output_manifest = json.loads((frozen.project / "audit/manifest.json").read_text())
    assert all(
        flow.file_hash(frozen.project / "audit" / name) == digest
        for name, digest in output_manifest["artifacts"].items()
    )
    with pytest.raises(ValueError, match="already exists"):
        _audit(frozen)


def test_evidenced_ranks_pass_only_at_all_cell_threshold_and_no_implicit_lyrics(frozen):
    evidence = _rank_evidence(frozen)
    report = _audit(frozen, evidence=evidence)
    assert report["gates"][0]["state"] == "aprovado"
    assert report["gates"][0]["approved_cells"] == 18
    assert report["gates"][1]["state"] == "reprovado"
    assert report["gates"][1]["numerator"] == 0


def test_one_missing_rank_approval_blocks_all_cell_advance(frozen):
    evidence = _rank_evidence(frozen)
    evidence["rankings"].pop()
    report = _audit(frozen, evidence=evidence)
    assert report["gates"][0]["ratio"] > 0.78
    assert report["gates"][0]["state"] == "reprovado"
    assert report["gates"][0]["approved_cells"] == 17


@pytest.mark.parametrize(
    "reason", ["incomplete", "provisional", "stale", "reconstruction", "title", "artist"]
)
def test_rank_requires_current_complete_and_independently_reconstructed_evidence(frozen, reason):
    evidence = _rank_evidence(frozen)
    row, approval = frozen.members[0], evidence["rankings"][0]
    if reason == "incomplete":
        row["coverage_status"] = "INCOMPLETE"
    elif reason == "provisional":
        row["selection_status"] = "PROVISIONAL_OBSERVED_PERIODS"
    elif reason == "stale":
        row["metric_value"] += 1
    elif reason in {"title", "artist"}:
        row[reason] = "Incorrect metadata despite a correct native ID"
        approval["row_sha256"] = flow.object_hash(row)
        approval["reconstructed_row"] = _save(frozen.project / "proof/wrong-metadata.json", row)
    else:
        rebuilt = copy.deepcopy(row)
        rebuilt["candidate_id"] = "SPOTIFY:wrong"
        approval["reconstructed_row"] = _save(frozen.project / "proof/wrong.json", rebuilt)
    parsed = flow.RankApproval.model_validate(approval)
    ok, _ = flow._rank_valid(row, parsed, flow.EvidenceReader(frozen.project))
    assert not ok


def test_same_reviewer_cannot_supply_two_independent_lyric_reviews(frozen):
    document, raw = _canonical(frozen)
    raw["reviews"][1]["actor"] = raw["reviews"][0]["actor"]
    ok, reason, _ = flow._lyric_valid(
        flow.LyricApproval.model_validate(raw),
        {str(document.id): document},
        flow.EvidenceReader(frozen.project),
        frozen.gate,
    )
    assert not ok
    assert reason == "independent_reviewers_required"


def test_two_positive_reviews_do_not_bypass_current_canonical_revocation(frozen):
    document, raw = _canonical(frozen)
    parsed = flow.LyricApproval.model_validate(raw)
    arguments = ({str(document.id): document}, flow.EvidenceReader(frozen.project), frozen.gate)
    assert flow._lyric_valid(parsed, *arguments)[0]
    document.metadata_json.pop("classification_adjudication")
    ok, reason, _ = flow._lyric_valid(parsed, *arguments)
    assert not ok
    assert reason == "adjudication_missing"


def test_disagreement_requires_distinct_positive_third_reviewer(frozen):
    document, raw = _canonical(frozen)
    raw["reviews"][1]["integrity_verified"] = False
    arguments = ({str(document.id): document}, flow.EvidenceReader(frozen.project), frozen.gate)
    assert (
        flow._lyric_valid(flow.LyricApproval.model_validate(raw), *arguments)[1]
        == "third_reviewer_adjudication_required"
    )
    raw["adjudicator"] = {**raw["reviews"][0], "actor": "synthetic-third"}
    assert flow._lyric_valid(flow.LyricApproval.model_validate(raw), *arguments)[0]


@pytest.mark.parametrize(
    "field",
    ["completeness_verified", "truncation_checked", "contamination_checked"],
)
def test_g2_requires_each_reviewer_to_complete_the_text_quality_checklist(frozen, field):
    document, raw = _canonical(frozen)
    raw["reviews"][0][field] = False
    ok, reason, _ = flow._lyric_valid(
        flow.LyricApproval.model_validate(raw),
        {str(document.id): document},
        flow.EvidenceReader(frozen.project),
        frozen.gate,
    )
    assert not ok
    assert reason == "third_reviewer_adjudication_required"


def test_g2_review_language_must_match_the_canonical_edition(frozen):
    document, raw = _canonical(frozen)
    raw["reviews"][0]["language_code"] = "es"
    ok, reason, _ = flow._lyric_valid(
        flow.LyricApproval.model_validate(raw),
        {str(document.id): document},
        flow.EvidenceReader(frozen.project),
        frozen.gate,
    )
    assert not ok
    assert reason == "review_language_mismatch"


def test_changed_text_and_wrong_candidate_binding_never_pass(frozen):
    document, raw = _canonical(frozen)
    parsed = flow.LyricApproval.model_validate(raw)
    arguments = ({str(document.id): document}, flow.EvidenceReader(frozen.project), frozen.gate)
    document.text += " changed"
    assert flow._lyric_valid(parsed, *arguments)[1] == "text_hash_mismatch"
    document.text = document.text.removesuffix(" changed")
    document.metadata_json["research_candidate_ids"] = []
    assert flow._lyric_valid(parsed, *arguments)[1] == "candidate_canonical_binding_missing"


def test_evidence_rejects_escape_future_attestation_and_changed_artifact(tmp_path):
    reader = flow.EvidenceReader(tmp_path / "workspace")
    outside = _save(tmp_path / "outside.json", {})
    with pytest.raises(ValueError, match="outside workspace"):
        reader.check(flow.Artifact.model_validate(outside))
    inside = _save(tmp_path / "workspace/proof.json", {})
    future = datetime.now(UTC).replace(year=2099).isoformat()
    with pytest.raises(ValueError, match="future"):
        reader.review(flow.Attestation(actor="synthetic", at=future, evidence=inside))
    (tmp_path / "workspace/proof.json").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        reader.check(flow.Artifact.model_validate(inside))


@pytest.mark.parametrize("change", ["document", "hash", "canonical_evidence"])
def test_positive_reviews_are_bound_to_the_current_document_and_evidence(frozen, change):
    document, raw = _canonical(frozen)
    if change == "document":
        raw["reviews"][0]["document_id"] = str(uuid4())
    elif change == "hash":
        raw["reviews"][0]["text_sha256"] = "0" * 64
    else:
        raw["canonical_evidence"] = _save(frozen.project / "proof/unrelated.json", {})
    approval = flow.LyricApproval.model_validate(raw)
    ok, _, _ = flow._lyric_valid(
        approval, {str(document.id): document}, flow.EvidenceReader(frozen.project), frozen.gate
    )
    assert not ok


@pytest.mark.parametrize("numerator,denominator", [(101, 100), (-1, 100), (1, -1), (True, 1)])
def test_gate_rejects_impossible_or_noninteger_counts(numerator, denominator):
    with pytest.raises(ValueError):
        flow.evaluate_gate("G1", [(("BR", 2019), numerator, denominator)])


@pytest.mark.parametrize("quota", [0, -1, True, 5.5, 501])
def test_quota_requires_strict_positive_bounded_integer(frozen, quota):
    frozen.cells[0]["quota"] = quota
    _freeze(frozen.selection, frozen.cells, frozen.members)
    with pytest.raises(ValueError, match="quota"):
        flow.load_selection(frozen.selection)


def test_original_sources_are_part_of_the_audit_freeze(frozen):
    source = frozen.project / "source.json"
    _save(source, {"original": True})
    manifest_path = frozen.selection / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["source_hashes"] = {"source.json": flow.file_hash(source)}
    _save(manifest_path, manifest)
    _audit(frozen)
    report = flow.verify_audit(frozen.project / "audit")
    assert str(source.resolve()) in report["input_hashes"]
    _save(source, {"original": False})
    with pytest.raises(ValueError, match="input missing or changed"):
        flow.verify_audit(frozen.project / "audit")


def test_audit_verification_rejects_changed_table_and_unapproved_advance(frozen):
    _audit(frozen)
    output = frozen.project / "audit"
    with pytest.raises(ValueError, match="not approved"):
        flow.require_research_stage(output, "G2", project=frozen.project)
    (output / "preparatory-table.csv").write_text("invented,scores\n")
    with pytest.raises(ValueError, match="artifact missing or changed"):
        flow.verify_audit(output)


def test_advance_revalidates_current_canonical_state(frozen):
    document, approval = _canonical(frozen)
    evidence = _rank_evidence(frozen)
    evidence["lyrics"] = [approval]
    _audit(frozen, evidence=evidence, documents={str(document.id): document})
    documents = {str(document.id): document}
    output = frozen.project / "audit"
    assert (
        flow.require_research_stage(
            output, "G1", project=frozen.project, document_reader=lambda project, ids: documents
        )["gates"][0]["state"]
        == "aprovado"
    )
    document.metadata_json.pop("classification_adjudication")
    with pytest.raises(ValueError, match="revoked or document changed"):
        flow.require_research_stage(
            output, "G1", project=frozen.project, document_reader=lambda project, ids: documents
        )


@pytest.mark.parametrize(
    ("scope", "authorized", "expected"),
    [("storage", False, False), ("processing", False, True), ("publication", False, True)],
)
def test_lyric_approval_keeps_storage_processing_and_publication_scopes_separate(
    frozen, scope, authorized, expected
):
    document, approval = _canonical(frozen)
    rights_path = Path(approval["rights_evidence"]["path"])
    rights = json.loads(rights_path.read_text(encoding="utf-8"))
    rights[scope]["authorized"] = authorized
    approval["rights_evidence"] = _save(rights_path, rights)

    valid, reason, _ = flow._lyric_valid(
        flow.LyricApproval.model_validate(approval),
        {str(document.id): document},
        flow.EvidenceReader(frozen.project),
        frozen.gate,
    )

    assert valid is expected
    if not expected:
        assert reason == "rights_evidence_incomplete"


@pytest.mark.parametrize("actor", [" SYNTHETIC-REVIEWER-A ", "Synthetic-Reviewer-A"])
def test_case_and_space_variants_of_one_reviewer_are_not_independent(frozen, actor):
    document, raw = _canonical(frozen)
    raw["reviews"][1]["actor"] = actor
    ok, reason, _ = flow._lyric_valid(
        flow.LyricApproval.model_validate(raw),
        {str(document.id): document},
        flow.EvidenceReader(frozen.project),
        frozen.gate,
    )
    assert not ok
    assert reason == "independent_reviewers_required"


def _prepared_evidence(frozen):
    from chart_observatory.lyrics.research_contract import (
        build_profile,
        prepare_request,
        rubric_draft,
    )

    evidence = _rank_evidence(frozen)
    rubric = rubric_draft()
    rubric["status"] = "accepted"
    rubric["acceptance"] = {
        "actor": "Synthetic scientific reviewer",
        "at": "2026-11-02T00:00:00Z",
        "rubric_sha256": flow.object_hash(rubric),
    }
    rubric_ref = _save(frozen.project / "proof/accepted-rubric.json", rubric)
    review_ref = _save(frozen.project / "proof/preparation-review.json", {"synthetic_review": True})
    profile = build_profile(
        model_id="synthetic-model",
        resolved_model_version="synthetic-001",
        generation_configuration={
            "temperature": 0,
            "provider": "vertex_ai",
            "region": "us-central1",
            "retention_days": 0,
        },
        rubric=rubric,
    )
    documents, requests = {}, {}
    for index in range(1, 5):
        document, approval = _canonical(frozen, index)
        documents[str(document.id)] = document
        evidence["lyrics"].append(approval)
        candidate = approval["candidate_id"]
        request = prepare_request(
            edition_id=str(document.id),
            text=document.text,
            language="pt",
            profile=profile,
            rubric=rubric,
        )
        requests[candidate] = request
        evidence["preparations"].append(
            {
                "candidate_id": candidate,
                "rubric": rubric_ref,
                "request": _save(frozen.project / f"proof/request-{index}.json", request),
                "review": {
                    "actor": "Synthetic preparer",
                    "at": "2026-11-03T00:00:00Z",
                    "evidence": review_ref,
                },
            }
        )
    return evidence, documents, requests


def test_g3_rejects_a_validly_signed_request_with_a_different_canonical_language(frozen):
    from chart_observatory.lyrics.research_contract import prepare_request

    evidence, documents, requests = _prepared_evidence(frozen)
    preparation = evidence["preparations"][0]
    original = requests[preparation["candidate_id"]]
    document = documents[original["edition_id"]]
    wrong_language = prepare_request(
        edition_id=original["edition_id"],
        text=document.text,
        language="en",
        profile=original["profile"],
        rubric=original["contract"]["rubric"],
    )
    preparation["request"] = _save(
        frozen.project / "proof/request-wrong-language.json", wrong_language
    )

    with pytest.raises(ValueError, match="canonical text/language/rubric"):
        _audit(frozen, evidence=evidence, documents=documents)
    assert not (frozen.project / "audit").exists()


def test_vertex_serialization_producer_is_frozen_and_changed_code_invalidates_audit(
    frozen, monkeypatch
):
    report = _audit(frozen)
    serializer = Path(flow.__file__).parent / "lyrics/research_vertex_payload.py"
    digest = flow.file_hash(serializer)
    assert report["input_hashes"][str(serializer)] == digest
    flow.verify_audit(frozen.project / "audit")
    file_hash = flow.file_hash
    monkeypatch.setattr(
        flow,
        "file_hash",
        lambda path: "0" * 64 if Path(path).resolve() == serializer.resolve() else file_hash(path),
    )

    with pytest.raises(ValueError, match="audit input missing or changed"):
        flow.verify_audit(frozen.project / "audit")


def test_prepared_valid_responses_do_not_fill_scores_before_classifier_homologation(frozen):
    evidence, documents, requests = _prepared_evidence(frozen)
    for index, (candidate, request) in enumerate(requests.items(), 1):
        response = {
            "contract_version": request["contract"]["version"],
            "request_id": request["request_id"],
            "status": "classified",
            "topics": {
                topic: {
                    "score": 2,
                    "evidence_segments": ["L000001"],
                    "justification": "Synthetic evidence",
                }
                for topic in TOPICS
            },
            "auxiliary": {},
        }
        evidence["results"].append(
            {
                "candidate_id": candidate,
                "request_id": request["request_id"],
                "response": _save(frozen.project / f"proof/response-{index}.json", response),
                "review": evidence["preparations"][0]["review"],
            }
        )
    report = _audit(frozen, evidence=evidence, documents=documents)
    assert [gate["state"] for gate in report["gates"]] == [
        "aprovado",
        "aprovado",
        "aprovado",
        "reprovado",
        "pendente",
    ]
    assert report["final_coverage_original_universe"] == 0
    with (frozen.project / "audit/preparatory-table.csv").open(encoding="utf-8-sig") as handle:
        table = list(csv.DictReader(handle))
    assert all(row[topic] == "" for row in table for topic in TOPICS)


def test_validation_of_unrelated_requests_cannot_homologate_current_preparation(frozen):
    evidence, documents, requests = _prepared_evidence(frozen)
    request = next(iter(requests.values()))
    group = "validation-" + request["edition_id"]
    path = frozen.project / "proof/validation.jsonl"
    _jsonl(path, [{"request_id": "b" * 64, "edition_id": "unrelated", "language": "pt"}])
    evidence["validation"] = {"path": str(path), "sha256": flow.file_hash(path)}
    evidence["validation_split"] = _validation_split(frozen, requests, documents, request, group)
    with pytest.raises(ValueError, match="not bound to an eligible request"):
        _audit(frozen, evidence=evidence, documents=documents)


@pytest.mark.parametrize("mismatch", ["prediction", "human_hash", "human_scores", "human_actor"])
def test_validation_scores_and_human_cards_must_match_preserved_artifacts(frozen, mismatch):
    evidence, documents, requests = _prepared_evidence(frozen)
    request = next(iter(requests.values()))
    scores = dict.fromkeys(TOPICS, 2)
    response = {
        "contract_version": request["contract"]["version"],
        "request_id": request["request_id"],
        "status": "classified",
        "topics": {
            topic: {
                "score": 2,
                "evidence_segments": ["L000001"],
                "justification": "Synthetic evidence",
            }
            for topic in TOPICS
        },
        "auxiliary": {},
    }
    observation = {
        "request_id": request["request_id"],
        "edition_id": request["edition_id"],
        "text_sha256": request["text_sha256"],
        "language": "pt",
        "split": "validation",
        "equivalence_group": "validation-" + request["edition_id"],
        "dispatch_target": {
            "provider": "vertex_ai",
            "model_id": request["profile"]["model_id"],
            "resolved_model_version": request["profile"]["configuration"]["resolved_model_version"],
            "region": "us-central1",
            "retention_days": 0,
        },
        "reference": scores,
        "human_a": scores,
        "human_b": scores,
        "prediction": dict(scores),
        "reviewer_a": "Synthetic A",
        "reviewer_b": "Synthetic B",
        "adjudicator": "Synthetic C",
        "response_artifact": _save(frozen.project / "proof/validation-response.json", response),
    }
    for role, actor in (
        ("human_a", "Synthetic A"),
        ("human_b", "Synthetic B"),
        ("reference", "Synthetic C"),
    ):
        card = {
            "request_id": request["request_id"],
            "text_sha256": request["text_sha256"],
            "scores": dict(scores),
            "actor": actor,
        }
        if role == "human_a":
            if mismatch == "human_hash":
                card["text_sha256"] = "f" * 64
            elif mismatch == "human_scores":
                card["scores"][next(iter(TOPICS))] = 0
            elif mismatch == "human_actor":
                card["actor"] = "Unrelated Reviewer"
        observation[role + "_artifact"] = _save(frozen.project / f"proof/{role}-card.json", card)
    if mismatch == "prediction":
        observation["prediction"][next(iter(TOPICS))] = 0
    path = frozen.project / "proof/validation.jsonl"
    _jsonl(path, [observation])
    evidence["validation"] = {"path": str(path), "sha256": flow.file_hash(path)}
    evidence["validation_split"] = _validation_split(
        frozen, requests, documents, request, observation["equivalence_group"]
    )
    expected = "predictions differ" if mismatch == "prediction" else "human validation card"
    with pytest.raises(ValueError, match=expected):
        _audit(frozen, evidence=evidence, documents=documents)


def test_validation_requires_a_hash_bound_frozen_split(frozen):
    evidence, documents, _ = _prepared_evidence(frozen)
    path = frozen.project / "proof/validation.jsonl"
    _jsonl(path, [])
    evidence["validation"] = {"path": str(path), "sha256": flow.file_hash(path)}
    with pytest.raises(ValueError, match="frozen split manifest"):
        _audit(frozen, evidence=evidence, documents=documents)


def test_accepted_g4_results_fill_scores_and_derived_presence_by_participation(frozen, monkeypatch):
    evidence, documents, requests = _prepared_evidence(frozen)
    topics = list(TOPICS)
    result_rows = {}
    for index, (candidate, request) in enumerate(requests.items(), 1):
        scores = dict.fromkeys(TOPICS, 2)
        if index == len(requests):
            scores[topics[0]] = 1
        raw = {
            "contract_version": request["contract"]["version"],
            "request_id": request["request_id"],
            "status": "classified",
            "topics": {
                topic: {
                    "score": score,
                    "evidence_segments": ["L000001"],
                    "justification": "Synthetic evidence for the table integration test.",
                }
                for topic, score in scores.items()
            },
            "auxiliary": {},
        }
        result_rows[candidate] = raw
        evidence["results"].append(
            {
                "candidate_id": candidate,
                "request_id": request["request_id"],
                "response": _save(frozen.project / f"proof/accepted-response-{index}.json", raw),
                "review": evidence["preparations"][0]["review"],
            }
        )

    request = next(iter(requests.values()))
    candidate = next(
        candidate
        for candidate, value in requests.items()
        if value["edition_id"] == request["edition_id"]
    )
    prediction = result_rows[candidate]
    scores = {topic: item["score"] for topic, item in prediction["topics"].items()}
    observation = {
        "request_id": request["request_id"],
        "edition_id": request["edition_id"],
        "text_sha256": request["text_sha256"],
        "language": request["language"],
        "split": "validation",
        "equivalence_group": "validation-" + request["edition_id"],
        "dispatch_target": {
            "provider": "vertex_ai",
            "model_id": request["profile"]["model_id"],
            "resolved_model_version": request["profile"]["configuration"]["resolved_model_version"],
            "region": "us-central1",
            "retention_days": 0,
        },
        "reference": dict(scores),
        "human_a": dict(scores),
        "human_b": dict(scores),
        "prediction": dict(scores),
        "reviewer_a": "Synthetic A",
        "reviewer_b": "Synthetic B",
        "adjudicator": "Synthetic C",
        "response_artifact": _save(
            frozen.project / "proof/accepted-validation-response.json", prediction
        ),
    }
    for role, actor in (
        ("human_a", "Synthetic A"),
        ("human_b", "Synthetic B"),
        ("reference", "Synthetic C"),
    ):
        observation[role + "_artifact"] = _save(
            frozen.project / f"proof/accepted-{role}-card.json",
            {
                "request_id": request["request_id"],
                "text_sha256": request["text_sha256"],
                "scores": dict(scores),
                "actor": actor,
            },
        )
    validation_path = frozen.project / "proof/accepted-validation.jsonl"
    _jsonl(validation_path, [observation])
    evidence["validation"] = {
        "path": str(validation_path),
        "sha256": flow.file_hash(validation_path),
    }
    evidence["validation_split"] = _validation_split(
        frozen, requests, documents, request, observation["equivalence_group"]
    )
    monkeypatch.setattr(
        "chart_observatory.research_validation.evaluate_validation",
        lambda rows: {
            "approved": True,
            "by_language": {"pt": {"approved": True}},
        },
    )

    report = _audit(frozen, evidence=evidence, documents=documents)
    assert [gate["state"] for gate in report["gates"]] == [
        "aprovado",
        "aprovado",
        "aprovado",
        "aprovado",
        "aprovado",
    ]
    with (frozen.project / "audit/preparatory-table.csv").open(encoding="utf-8-sig") as handle:
        table = list(csv.DictReader(handle))
    assert len(table) == len(frozen.members)
    for row in table:
        if row["candidate_id"] == candidate:
            assert row[topics[0]] == "2"
            assert row[f"{topics[0]}.present"] == "True"
        elif row["candidate_id"] == list(requests)[-1]:
            assert row[topics[0]] == "1"
            assert row[f"{topics[0]}.present"] == "False"


def test_source_definition_cannot_approve_a_different_country(frozen):
    evidence = _rank_evidence(frozen)
    row = frozen.members[0]
    approval = evidence["rankings"][0]
    definition = json.loads(Path(approval["source_definition"]["path"]).read_text())
    definition["country_code"] = "ZZ"
    approval["source_definition"] = _save(frozen.project / "proof/wrong-country.json", definition)
    ok, reason = flow._rank_valid(
        row, flow.RankApproval.model_validate(approval), flow.EvidenceReader(frozen.project)
    )
    assert not ok
    assert reason == "source_definition_binding_mismatch"


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_url", None),
        ("source_url", "http://example.org/chart"),
        ("retrieved_at", None),
        ("retrieved_at", "2026-11-01T00:00:00"),
    ],
)
def test_source_citation_requires_https_and_aware_timestamp(frozen, field, value):
    evidence = _rank_evidence(frozen)
    approval = evidence["rankings"][0]
    definition = json.loads(Path(approval["source_definition"]["path"]).read_text())
    definition[field] = value
    approval["source_definition"] = _save(
        frozen.project / "proof/invalid-citation.json", definition
    )
    ok, reason = flow._rank_valid(
        frozen.members[0],
        flow.RankApproval.model_validate(approval),
        flow.EvidenceReader(frozen.project),
    )
    assert not ok
    assert reason == "source_citation_or_timestamp_invalid"


@pytest.mark.parametrize("field,value", [("provider", "OTHER_PROVIDER"), ("platform", "YOUTUBE")])
def test_country_year_has_one_whole_primary_source(frozen, field, value):
    frozen.members[1][field] = value
    _freeze(frozen.selection, frozen.cells, frozen.members)
    with pytest.raises(ValueError, match="one primary platform/provider"):
        flow.load_selection(frozen.selection)


@pytest.mark.parametrize("gate,threshold", [("G1", 1.0), ("G2", 0.8), ("G3", 1.0), ("G5", 0.8)])
def test_versioned_complete_rankings_policy(gate, threshold):
    target = flow.GATE_POLICIES[flow.GATE_POLICY][gate]
    assert target == threshold
    result = flow.evaluate_gate(gate, [(("BR", 2019), 80, 100)], threshold=target)
    assert result["state"] == ("aprovado" if threshold == 0.8 else "reprovado")
    assert result["threshold"] == threshold


def test_published_annual_evidence_is_verified_without_synthetic_metrics(frozen):
    for row in frozen.members:
        row["metric_value"] = None
    _freeze(frozen.selection, frozen.cells, frozen.members)
    evidence = _rank_evidence(frozen)
    for approval in evidence["rankings"]:
        definition = json.loads(Path(approval["source_definition"]["path"]).read_text())
        year, country = approval["year"], approval["country_code"]
        annual = [
            {
                "country_code": country,
                "year": year,
                "platform": "SPOTIFY",
                "provider": "SYNTHETIC_FIXTURE",
                "period_start": definition["period_start"],
                "period_end": definition["period_end"],
                "position": position,
                "candidate_id": f"SPOTIFY:synthetic-{position}",
                "title": f"Synthetic {position}",
                "artist": "Synthetic Artist",
                "metric_value": None,
            }
            for position in range(1, 6)
        ]
        path = frozen.project / f"proof/published-{country}-{year}.jsonl"
        _jsonl(path, annual)
        ref = {"path": str(path), "sha256": flow.file_hash(path)}
        definition["ranking_kind"] = "published_annual"
        definition["observation_artifact"] = ref
        approval["source_files"] = [ref]
        approval["source_definition"] = _save(
            Path(approval["source_definition"]["path"]), definition
        )
    report = _audit(frozen, evidence=evidence)
    assert report["gates"][0]["state"] == "aprovado"
    assert report["inventory"]["scientifically_verified_positions"] == len(frozen.members)


def test_new_audit_default_requires_complete_rankings(frozen):
    evidence_path = frozen.project / "proof/default-evidence.json"
    _save(evidence_path, _rank_evidence(frozen))
    report = flow.audit_research_flow(
        project=frozen.project,
        selection=frozen.selection,
        output=frozen.project / "default-audit",
        actor="synthetic-auditor",
        evidence_path=evidence_path,
        document_reader=lambda project, ids: {},
    )
    assert report["gate_policy_version"] == flow.GATE_POLICY
    assert report["gates"][0]["threshold"] == 1.0
    assert report["gates"][0]["ratio"] == 0.8
    assert report["gates"][0]["state"] == "reprovado"
    assert report["gates"][1]["state"] == "pendente"
