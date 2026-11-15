"""Evidence-bound research stage controller. No network collection or paid dispatch.

An import checksum is deliberately not a scientific ranking approval. Human
attestations are recorded as attestations, not authentication of their authors.
Every invocation creates a new immutable audit directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, StrictInt

from chart_observatory.ingestion.source_coverage import normalize_source_coverage
from chart_observatory.lyrics.classification_gate import ClassificationGate
from chart_observatory.lyrics.research_contract import CONTRACT_VERSION, contract, validate_result
from chart_observatory.lyrics.review_protocol import PRESENCE_THRESHOLD, TOPICS
from chart_observatory.lyrics.revision_protocol import canonical_json
from chart_observatory.pipeline_state import file_hash, process_alive

VERSION = "worldwide-research-flow-v4"
THRESHOLD = 0.8  # Historical compatibility; new audits use the versioned policy below.
GATE_POLICY = "complete-rankings-lyrics80-v1"
GATE_POLICIES = {
    GATE_POLICY: {"G1": 1.0, "G2": 0.8, "G3": 1.0, "G5": 0.8},
    "legacy80-v4": {"G1": 0.8, "G2": 0.8, "G3": 0.8, "G5": 0.8},
}
LOCAL_STATUSES = (
    "data/runtime/global-lyrics-20261108/final-staging/status.json",
    "data/runtime/global-lyrics-20261108/status.json",
    "data/runtime/import-all-lyrics-web-comparison-global-20261108/status.json",
    "data/runtime/vertex-global-preparation-20261108/source-audit/status.json",
    "data/runtime/vertex-global-preparation-20261108/finalization/status.json",
)
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonBlank = Annotated[str, Field(min_length=1, pattern=r"\S")]


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Artifact(EvidenceModel):
    path: NonBlank
    sha256: Digest


class RightsScope(EvidenceModel):
    authorized: StrictBool
    basis: NonBlank
    evidence: Artifact


class VertexAuthorization(RightsScope):
    provider: Literal["vertex_ai"]
    model_id: NonBlank
    resolved_model_version: NonBlank
    region: NonBlank
    retention_days: Annotated[StrictInt, Field(ge=0)]


class RightsEvidence(EvidenceModel):
    schema_version: Literal["research-rights-v1"]
    document_id: UUID
    text_sha256: Digest
    source_url: NonBlank
    storage: RightsScope
    processing: RightsScope
    publication: RightsScope
    vertex_authorizations: list[VertexAuthorization] = Field(default_factory=list)


class Attestation(EvidenceModel):
    actor: NonBlank
    at: AwareDatetime
    evidence: Artifact


class RankApproval(EvidenceModel):
    country_code: NonBlank
    year: int
    position: int
    row_sha256: Digest
    reconstructed_row: Artifact
    source_definition: Artifact
    source_files: list[Artifact] = Field(min_length=1)
    review: Attestation


class TextReview(Attestation):
    document_id: UUID
    text_sha256: Digest
    identity_verified: StrictBool
    integrity_verified: StrictBool
    completeness_verified: StrictBool
    truncation_checked: StrictBool
    contamination_checked: StrictBool
    language_code: NonBlank
    language_competence: NonBlank
    competence_evidence: Artifact
    method: str = Field(pattern=r"^(official_transcription|human_audio_verification)$")


class LyricApproval(EvidenceModel):
    candidate_id: NonBlank
    document_id: UUID
    text_sha256: Digest
    reviews: list[TextReview] = Field(min_length=2, max_length=2)
    adjudicator: TextReview | None = None
    rights_evidence: Artifact
    canonical_evidence: Artifact


class Preparation(EvidenceModel):
    candidate_id: NonBlank
    request: Artifact
    rubric: Artifact
    review: Attestation


class ResultApproval(EvidenceModel):
    candidate_id: NonBlank
    request_id: Digest
    response: Artifact
    review: Attestation


class ResearchEvidence(EvidenceModel):
    schema_version: Literal["research-evidence-v4"]
    selection_sha256: Digest
    rankings: list[RankApproval] = Field(default_factory=list)
    lyrics: list[LyricApproval] = Field(default_factory=list)
    preparations: list[Preparation] = Field(default_factory=list)
    validation: Artifact | None = None
    validation_split: Artifact | None = None
    results: list[ResultApproval] = Field(default_factory=list)


def rows(path):
    with Path(path).open(encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, 1):
            if not line.endswith("\n"):
                raise ValueError(f"incomplete JSONL record {number}: {Path(path).name}")
            if line.strip():
                yield json.loads(line)


def object_hash(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str),
        encoding="utf-8",
    )


def write_rows(path, values):
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")


def write_csv(path, records, fields):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


class EvidenceReader:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.checked = {}
        self.reconstructions = {}

    def check(self, ref):
        path = (self.root / ref.path).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("evidence reference outside workspace")
        if self.checked.get(str(path)) == ref.sha256:
            return path
        if file_hash(path) != ref.sha256:
            raise ValueError(f"evidence missing or changed: {ref.path}")
        self.checked[str(path)] = ref.sha256
        return path

    def json(self, ref):
        return json.loads(self.check(ref).read_text(encoding="utf-8-sig"))

    def review(self, review):
        if review.at > datetime.now(UTC):
            raise ValueError("future attestation")
        self.check(review.evidence)


def load_selection(selection):
    selection = Path(selection).resolve()
    manifest = json.loads((selection / "manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("protocol") != "worldwide-annual-quotas-v1":
        raise ValueError("expected worldwide annual quota manifest")
    if manifest.get("years") != list(range(2018, 2027)) or manifest.get("cutoff") != "2026-10-15":
        raise ValueError("scope/cutoff differ from approved research protocol")
    hashes = {str(selection / "manifest.json"): file_hash(selection / "manifest.json")}
    for name, digest in manifest["output_hashes"].items():
        path = (selection / name).resolve()
        if not path.is_relative_to(selection) or file_hash(path) != digest:
            raise ValueError("selection output missing or changed: " + name)
        hashes[str(path)] = digest
    if "source_coverage.json" in manifest["output_hashes"]:
        source_coverage = json.loads(
            (selection / "source_coverage.json").read_text(encoding="utf-8-sig")
        )
        normalize_source_coverage(source_coverage)
    if not {"combined.jsonl", "country_years.jsonl"} <= manifest["output_hashes"].keys():
        raise ValueError("membership and cell hashes required")
    cells = list(rows(selection / "country_years.jsonl"))
    memberships = list(rows(selection / "combined.jsonl"))
    cell_map = {(c["country_code"], c["year"]): c for c in cells}
    if len(cell_map) != len(cells) or len(cells) != manifest["country_year_cells"]:
        raise ValueError("duplicate or missing country/year cells")
    countries = {c["country_code"] for c in cells}
    for cell in cells:
        quota = cell["quota"]
        if quota is not None and (type(quota) is not int or not 1 <= quota <= 500):
            raise ValueError("quota must be a positive integer up to 500 or null")
        end = "2026-10-15" if cell["year"] == 2026 else f"{cell['year']}-12-31"
        if cell.get("ranking_period_end") != end:
            raise ValueError("cell period differs from frozen cutoff")
    expected = {(c, y) for c in countries for y in range(2018, 2027)}
    if set(cell_map) != expected or len(countries) != manifest["countries"]:
        raise ValueError("country/year universe is incomplete")
    slots, identities = set(), set()
    cell_sources = defaultdict(set)
    for row in memberships:
        cell = cell_map.get((row["country_code"], row["year"]))
        position = row["position"]
        if cell is None or type(position) is not int or position < 1:
            raise ValueError("membership outside frozen universe")
        if cell["quota"] is None or position > cell["quota"]:
            raise ValueError("membership outside quota")
        slot = (row["country_code"], row["year"], position)
        identity = (row["country_code"], row["year"], row["candidate_id"])
        if slot in slots or identity in identities:
            raise ValueError("duplicate position or candidate within country/year")
        slots.add(slot)
        identities.add(identity)
        cell_sources[row["country_code"], row["year"]].add((row["platform"], row["provider"]))
    if any(len(sources) > 1 for sources in cell_sources.values()):
        raise ValueError("one primary platform/provider required per country/year")
    if len(memberships) != manifest["memberships"]:
        raise ValueError("membership count differs from manifest")
    total = sum(c["quota"] for c in cells if c["quota"] is not None)
    if total != manifest["requested_positions"]:
        raise ValueError("quota denominator differs from manifest")
    return manifest, cells, memberships, hashes


def _unique(values, key):
    result = {}
    for item in values:
        identity = key(item)
        if identity in result:
            raise ValueError("duplicate evidence identity")
        result[identity] = item
    return result


def inspect_local_statuses(project):
    """Separate timestamped local inventories; never merge different run IDs."""
    statuses, hashes = [], {}
    allowed = {
        "run_id",
        "stage",
        "state",
        "updated_at",
        "observed_at",
        "finished_at",
        "candidates",
        "text_candidates",
        "unique_texts",
        "total",
        "checked",
        "counts",
        "approvals",
        "classification_ready",
        "paid_ready_candidates",
        "pid",
    }
    for name in LOCAL_STATUSES:
        path = Path(project) / name
        if not path.is_file():
            continue
        digest = file_hash(path)
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if file_hash(path) != digest:
            raise ValueError("local status changed during inspection")
        hashes[str(path)] = digest
        record = {key: value[key] for key in allowed if key in value}
        record.update(
            path=name,
            sha256=digest,
            scope="local_historical_snapshot",
            current_database_certified=False,
        )
        if value.get("pid"):
            record["pid_exists"] = process_alive(value["pid"])
            record["process_identity_verified"] = False
        statuses.append(record)
    return statuses, hashes


def canonical_fingerprint(document):
    return object_hash(
        {
            "id": str(document.id),
            "recording_id": str(document.canonical_track_id),
            "text_sha256": document.content_sha256,
            "rights_status": str(document.rights_status),
            "language_code": getattr(document, "language_code", None),
            "source": document.source,
            "metadata": document.metadata_json,
        }
    )


def verify_audit(output, *, check_inputs=True):
    """Verify a versioned audit before using it; never trust a hand-edited CSV."""
    output = Path(output).resolve()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["artifacts"].items():
        path = (output / name).resolve()
        if not path.is_relative_to(output) or file_hash(path) != digest:
            raise ValueError("audit artifact missing or changed: " + name)
    if check_inputs:
        for path, digest in manifest["input_hashes"].items():
            if file_hash(path) != digest:
                raise ValueError("audit input missing or changed")
    return json.loads((output / "report.json").read_text(encoding="utf-8"))


def require_research_stage(output, gate_name, *, project, document_reader=None):
    report = verify_audit(output)
    states = {g["gate"]: g["state"] for g in report["gates"]}
    if states.get(gate_name) != "aprovado":
        raise ValueError("research stage is not approved: " + gate_name)
    current = (document_reader or read_canonical_documents)(
        project, [UUID(identity) for identity in report["canonical_state"]]
    )
    gate = ClassificationGate.load()
    for identity, digest in report["canonical_state"].items():
        document = current.get(identity)
        if (
            document is None
            or canonical_fingerprint(document) != digest
            or not gate.assess(document).eligible
        ):
            raise ValueError("canonical approval revoked or document changed; rerun audit")
    return report


def read_canonical_documents(project, ids):
    """Current PostgreSQL state, not a historical JSON approval export."""
    if not ids:
        return {}
    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import Session

    from chart_observatory.config import Settings
    from chart_observatory.db.models.corpus import LyricDocument

    engine = create_engine(
        Settings.load(Path(project)).database_url, connect_args={"connect_timeout": 5}
    )
    try:
        with Session(engine, expire_on_commit=False) as session:
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            return {
                str(d.id): d
                for d in session.scalars(
                    select(LyricDocument).where(LyricDocument.id.in_(ids))
                ).all()
            }
    finally:
        engine.dispose()


def _rank_valid(row, approval, reader, *, quota=None):
    if row.get("coverage_status") != "COMPLETE":
        return False, "incomplete_calendar"
    if "PROVISIONAL" in row.get("selection_status", ""):
        return False, "provisional_ranking"
    if any(
        not isinstance(row.get(key), str) or not row[key].strip() for key in ("title", "artist")
    ):
        return False, "unresolved_display_identity"
    if approval is None:
        return False, "ranking_scientific_evidence_missing"
    if object_hash(row) != approval.row_sha256:
        return False, "ranking_approval_stale"
    reader.review(approval.review)
    definition = reader.json(approval.source_definition)
    required = (
        "platform",
        "provider",
        "frequency",
        "metric",
        "period_start",
        "period_end",
        "depth",
        "source_url",
        "retrieved_at",
        "ranking_kind",
        "calendar_verified",
        "depth_verified",
        "identity_verified",
        "boundary_tie_resolved",
        "country_code",
        "observation_artifact",
    )
    if any(key not in definition for key in required):
        return False, "source_definition_incomplete"
    try:
        retrieved_at = datetime.fromisoformat(definition["retrieved_at"])
        source_url = urlsplit(definition["source_url"])
        if (
            retrieved_at.tzinfo is None
            or retrieved_at > datetime.now(UTC)
            or source_url.scheme != "https"
            or not source_url.netloc
        ):
            return False, "source_citation_or_timestamp_invalid"
    except (TypeError, ValueError, AttributeError):
        return False, "source_citation_or_timestamp_invalid"
    if any(
        definition[k] is not True
        for k in (
            "calendar_verified",
            "depth_verified",
            "identity_verified",
            "boundary_tie_resolved",
        )
    ):
        return False, "source_definition_unverified"
    end = "2026-10-15" if row["year"] == 2026 else f"{row['year']}-12-31"
    if (
        definition["period_start"] != f"{row['year']}-01-01"
        or definition["period_end"] != end
        or definition["platform"] != row["platform"]
        or definition["provider"] != row["provider"]
        or definition["country_code"] != row["country_code"]
        or definition["ranking_kind"] not in {"published_annual", "observed_chart_sum"}
    ):
        return False, "source_definition_binding_mismatch"
    for ref in approval.source_files:
        reader.check(ref)
    observation_ref = Artifact.model_validate(definition["observation_artifact"])
    if observation_ref not in approval.source_files:
        return False, "observation_source_binding_missing"
    from chart_observatory.research_rankings import (
        reconstruct_chart_sum,
        verify_published_annual,
    )

    effective_quota = quota if quota is not None else definition.get("quota")
    if type(effective_quota) is not int or effective_quota < 1:
        return False, "reconstruction_quota_missing"
    cache_key = (approval.source_definition.sha256, effective_quota)
    if cache_key not in reader.reconstructions:
        observation_path = reader.check(observation_ref)
        if definition["ranking_kind"] == "published_annual":
            rebuilt_chart = verify_published_annual(
                rows(observation_path),
                country_code=row["country_code"],
                year=row["year"],
                platform=row["platform"],
                provider=row["provider"],
                quota=effective_quota,
                expected_depth=definition["depth"],
                period_start=definition["period_start"],
                period_end=definition["period_end"],
            )
        else:
            rebuilt_chart = reconstruct_chart_sum(
                rows(observation_path),
                country_code=row["country_code"],
                year=row["year"],
                platform=row["platform"],
                provider=row["provider"],
                quota=effective_quota,
                frequency=definition["frequency"],
                expected_depth=definition["depth"],
                expected_period_ends=definition.get("expected_period_ends"),
            )
        reader.reconstructions[cache_key] = (
            rebuilt_chart,
            {r["candidate_id"]: r for r in rebuilt_chart["rows"]},
        )
    rebuilt_chart, rebuilt_rows = reader.reconstructions[cache_key]
    if not rebuilt_chart["approved"]:
        return False, "independent_calendar_or_rank_reconstruction_failed"
    actual = rebuilt_rows.get(row["candidate_id"])
    if actual is None or actual["position"] != row["position"] or actual["tie_group"]:
        return False, "independent_reconstruction_position_mismatch"
    if definition["ranking_kind"] == "published_annual":
        same_metric = actual.get("metric_value") == row.get("metric_value")
    else:
        try:
            same_metric = Decimal(str(actual["metric_value"])) == Decimal(str(row["metric_value"]))
        except InvalidOperation:
            same_metric = False
    if not same_metric:
        return False, "independent_reconstruction_metric_mismatch"
    if any(actual[key] != row[key] for key in ("title", "artist")):
        return False, "independent_reconstruction_metadata_mismatch"
    rebuilt = reader.json(approval.reconstructed_row)
    if any(
        rebuilt.get(key) != row.get(key)
        for key in (
            "country_code",
            "year",
            "position",
            "candidate_id",
            "platform",
            "provider",
            "metric_value",
        )
    ):
        return False, "independent_reconstruction_mismatch"
    return True, "approved"


def _lyric_valid(approval, documents, reader, gate):
    if approval is None:
        return False, "lyric_approval_missing", None
    document = documents.get(str(approval.document_id))
    if document is None:
        return False, "canonical_document_missing", None
    if document.content_sha256 != approval.text_sha256:
        return False, "lyric_approval_stale", None
    decision = gate.assess(document)
    if not decision.eligible:
        return False, decision.reason, None
    # Candidate-to-recording binding must be explicitly preserved in canonical metadata.
    links = (document.metadata_json or {}).get("research_candidate_ids", [])
    if not isinstance(links, list) or approval.candidate_id not in links:
        return False, "candidate_canonical_binding_missing", None
    reviewers = {r.actor.strip().casefold() for r in approval.reviews}
    if len(reviewers) != 2:
        return False, "independent_reviewers_required", None
    for review in approval.reviews:
        reader.review(review)
        reader.check(review.competence_evidence)
        if review.document_id != document.id or review.text_sha256 != document.content_sha256:
            return False, "review_document_binding_mismatch", None
        if (
            review.language_code.strip().casefold()
            != str(document.language_code).strip().casefold()
        ):
            return False, "review_language_mismatch", None
    original_approval = document.metadata_json["classification_adjudication"]
    if approval.canonical_evidence.sha256 != original_approval["evidence_sha256"]:
        return False, "canonical_evidence_binding_mismatch", None
    reader.check(approval.canonical_evidence)
    positive = all(
        r.identity_verified
        and r.integrity_verified
        and r.completeness_verified
        and r.truncation_checked
        and r.contamination_checked
        for r in approval.reviews
    )
    if not positive:
        adjudicator = approval.adjudicator
        if (
            adjudicator is None
            or adjudicator.actor.strip().casefold() in reviewers
            or not adjudicator.identity_verified
            or not adjudicator.integrity_verified
            or not adjudicator.completeness_verified
            or not adjudicator.truncation_checked
            or not adjudicator.contamination_checked
            or adjudicator.language_code.strip().casefold()
            != str(document.language_code).strip().casefold()
        ):
            return False, "third_reviewer_adjudication_required", None
        reader.review(adjudicator)
        reader.check(adjudicator.competence_evidence)
        if (
            adjudicator.document_id != document.id
            or adjudicator.text_sha256 != document.content_sha256
            or adjudicator.at < max(r.at for r in approval.reviews)
        ):
            return False, "adjudication_document_binding_mismatch", None
    try:
        rights = RightsEvidence.model_validate(reader.json(approval.rights_evidence))
    except (TypeError, ValueError):
        return False, "rights_evidence_incomplete", None
    source_url = urlsplit(rights.source_url)
    if (
        str(rights.document_id) != str(document.id)
        or rights.text_sha256 != document.content_sha256
        or source_url.scheme != "https"
        or not source_url.netloc
        or not rights.storage.authorized
    ):
        return False, "rights_evidence_incomplete", None
    for scope in (rights.storage, rights.processing, rights.publication):
        reader.check(scope.evidence)
    for authorization in rights.vertex_authorizations:
        reader.check(authorization.evidence)
    return True, "approved", document


def _rights_summary(approval, document, reader):
    rights = RightsEvidence.model_validate(reader.json(approval.rights_evidence))
    if rights.document_id != document.id or rights.text_sha256 != document.content_sha256:
        raise ValueError("rights evidence changed after lyric validation")
    return {
        "document_id": str(document.id),
        "text_sha256": document.content_sha256,
        "rights_evidence_sha256": approval.rights_evidence.sha256,
        "storage_authorized": rights.storage.authorized,
        "processing_authorized": rights.processing.authorized,
        "publication_authorized": rights.publication.authorized,
        "vertex_authorizations": [
            {
                "provider": item.provider,
                "model_id": item.model_id,
                "resolved_model_version": item.resolved_model_version,
                "region": item.region,
                "retention_days": item.retention_days,
                "authorized": item.authorized,
            }
            for item in rights.vertex_authorizations
        ],
    }


def require_vertex_rights(report, request, target):
    """Require an exact positive processing grant for the dispatch target."""
    if not isinstance(target, dict) or set(target) != {
        "provider",
        "model_id",
        "resolved_model_version",
        "region",
        "retention_days",
    }:
        raise ValueError("explicit Vertex model, region and retention target required")
    if (
        target.get("provider") != "vertex_ai"
        or not isinstance(target.get("model_id"), str)
        or not target["model_id"].strip()
        or not isinstance(target.get("resolved_model_version"), str)
        or not target["resolved_model_version"].strip()
        or not isinstance(target.get("region"), str)
        or not target["region"].strip()
        or type(target.get("retention_days")) is not int
        or target["retention_days"] < 0
    ):
        raise ValueError("invalid Vertex model, region or retention target")
    profile = request.get("profile", {})
    configuration = profile.get("configuration", {})
    generation = configuration.get("generation", {})
    if (
        target["model_id"] != profile.get("model_id")
        or target["resolved_model_version"] != configuration.get("resolved_model_version")
        or target["provider"] != generation.get("provider")
        or target["region"] != generation.get("region")
        or target["retention_days"] != generation.get("retention_days")
    ):
        raise ValueError("Vertex target differs from the prepared model/region/retention signature")
    rights = report.get("rights_authorizations", {}).get(request.get("edition_id"))
    if (
        rights is None
        or rights.get("text_sha256") != request.get("text_sha256")
        or rights.get("storage_authorized") is not True
        or rights.get("processing_authorized") is not True
    ):
        raise ValueError("lyrics are not explicitly authorized for external processing")
    if not any(
        item.get("authorized") is True and all(item.get(key) == target.get(key) for key in target)
        for item in rights.get("vertex_authorizations", [])
    ):
        raise ValueError("no rights grant matches the exact Vertex model/region/retention")


def evaluate_gate(name, cell_counts, *, predecessor=True, extra_blockers=(), threshold=THRESHOLD):
    if threshold not in (0.8, 1.0):
        raise ValueError("unsupported gate threshold")
    target_numerator, target_denominator = (1, 1) if threshold == 1.0 else (4, 5)
    evaluations = []
    for cell, numerator, denominator in cell_counts:
        if (
            type(numerator) is not int
            or numerator < 0
            or (
                denominator is not None
                and (type(denominator) is not int or denominator < 0 or numerator > denominator)
            )
            or (denominator is None and numerator != 0)
        ):
            raise ValueError("invalid gate numerator/denominator")
        ratio = numerator / denominator if denominator else None
        valid = (
            denominator is not None
            and denominator > 0
            and numerator * target_denominator >= denominator * target_numerator
        )
        evaluations.append(
            {
                "gate": name,
                "country_code": cell[0],
                "year": cell[1],
                "numerator": numerator,
                "denominator": denominator,
                "ratio": ratio,
                "state": ("pendente" if not predecessor else "aprovado" if valid else "reprovado"),
            }
        )
    numerator = sum(r["numerator"] for r in evaluations)
    denominator = sum(r["denominator"] or 0 for r in evaluations)
    unknown = sum(r["denominator"] is None for r in evaluations)
    passed = (
        bool(evaluations)
        and not unknown
        and denominator > 0
        and numerator * target_denominator >= denominator * target_numerator
        and all(r["state"] == "aprovado" for r in evaluations)
        and not extra_blockers
        and predecessor
    )
    return {
        "gate": name,
        "state": ("aprovado" if passed else "reprovado" if predecessor else "pendente"),
        "numerator": numerator,
        "denominator": denominator,
        "ratio": numerator / denominator if denominator else None,
        "unknown_denominators": unknown,
        "threshold": threshold,
        "approved_cells": sum(r["state"] == "aprovado" for r in evaluations),
        "total_cells": len(evaluations),
        "blockers": list(extra_blockers),
        "cells": evaluations,
    }


def audit_research_flow(
    *,
    project,
    selection,
    output,
    actor,
    evidence_path=None,
    document_reader=None,
    gate_policy=GATE_POLICY,
):
    """Record an append-only attempt and its terminal evidence-bound outcome."""
    from chart_observatory.research_stage_ledger import ResearchStageLedger

    output = Path(output).resolve()
    if output.exists():
        raise ValueError("audit output already exists; use a new version directory")
    digest = file_hash(Path(selection).resolve() / "manifest.json")
    ledger = ResearchStageLedger(output.parent / "research-stage-history.sqlite")
    run_id = ledger.begin(digest, actor, output)
    try:
        report = _audit_research_flow(
            project=project,
            selection=selection,
            output=output,
            actor=actor,
            evidence_path=evidence_path,
            document_reader=document_reader,
            run_id=run_id,
            ledger_path=ledger.path,
            gate_policy=gate_policy,
        )
        ledger.finish(run_id, report, file_hash(output / "report.json"))
        return report
    except Exception as exc:
        ledger.fail(run_id, type(exc).__name__)
        raise


def _audit_research_flow(
    *,
    project,
    selection,
    output,
    actor,
    evidence_path=None,
    document_reader=None,
    run_id=None,
    ledger_path=None,
    gate_policy=GATE_POLICY,
):
    """Freeze, check and report all five gates without promoting any source record."""
    if gate_policy not in GATE_POLICIES:
        raise ValueError("unknown gate policy")
    targets = GATE_POLICIES[gate_policy]
    project, output = Path(project).resolve(), Path(output).resolve()
    if not actor.strip():
        raise ValueError("responsible actor required")
    if output.exists():
        raise ValueError("audit output already exists; use a new version directory")
    manifest, cells, memberships, hashes = load_selection(selection)
    for filename in ("pyproject.toml", "uv.lock"):
        path = project / filename
        if path.is_file():
            hashes[str(path)] = file_hash(path)
    local_statuses, status_hashes = inspect_local_statuses(project)
    hashes.update(status_hashes)
    for name, digest in manifest.get("source_hashes", {}).items():
        path = (project / name).resolve()
        if not path.is_relative_to(project) or file_hash(path) != digest:
            raise ValueError("frozen source missing or changed: " + name)
        hashes[str(path)] = digest
    selection_hash = hashes[str(Path(selection).resolve() / "manifest.json")]
    reader = EvidenceReader(project)
    if evidence_path:
        evidence_path = Path(evidence_path).resolve()
        hashes[str(evidence_path)] = file_hash(evidence_path)
        evidence = ResearchEvidence.model_validate_json(
            evidence_path.read_text(encoding="utf-8-sig")
        )
        if evidence.selection_sha256 != selection_hash:
            raise ValueError("evidence belongs to another selection")
    else:
        evidence = ResearchEvidence(
            schema_version="research-evidence-v4",
            selection_sha256=selection_hash,
        )
    ranks = _unique(evidence.rankings, lambda r: (r.country_code, r.year, r.position))
    lyrics = _unique(evidence.lyrics, lambda r: r.candidate_id)
    preparations = _unique(evidence.preparations, lambda r: r.candidate_id)
    results = _unique(evidence.results, lambda r: r.candidate_id)
    candidates = {r["candidate_id"] for r in memberships}
    slots = {(r["country_code"], r["year"], r["position"]) for r in memberships}
    if set(ranks) - slots or (set(lyrics) | set(preparations) | set(results)) - candidates:
        raise ValueError("evidence contains items outside frozen selection")
    documents = (document_reader or read_canonical_documents)(
        project, [r.document_id for r in evidence.lyrics]
    )
    gate = ClassificationGate.load()
    counts = defaultdict(Counter)
    diagnostics, approved_documents, approved_requests, accepted_results = {}, {}, {}, {}
    rights_authorizations = {}
    for candidate in candidates:
        ok, reason, document = _lyric_valid(lyrics.get(candidate), documents, reader, gate)
        diagnostics[candidate] = reason
        if ok:
            approved_documents[candidate] = document
            rights = _rights_summary(lyrics[candidate], document, reader)
            identity = str(document.id)
            prior = rights_authorizations.get(identity)
            if prior is not None and canonical_json(prior) != canonical_json(rights):
                raise ValueError("conflicting rights scopes for one canonical text edition")
            rights_authorizations[identity] = rights
    for candidate, preparation in preparations.items():
        document = approved_documents.get(candidate)
        if document is None:
            continue
        from chart_observatory.lyrics.research_contract import validate_rubric, verify_request

        reader.review(preparation.review)
        rubric = reader.json(preparation.rubric)
        validate_rubric(rubric, require_accepted=True)
        request = reader.json(preparation.request)
        verify_request(request)
        if (
            request["edition_id"] != str(document.id)
            or request["text_sha256"] != document.content_sha256
            or request["language"] != document.language_code
            or request.get("rubric_sha256") != object_hash(rubric)
        ):
            raise ValueError("prepared request differs from canonical text/language/rubric")
        approved_requests[candidate] = request
    validation = {"approved": False, "reasons": ["independent_validation_missing"]}
    if (evidence.validation is None) != (evidence.validation_split is None):
        raise ValueError(
            "validation observations and their frozen split manifest are required together"
        )
    if evidence.validation:
        from chart_observatory.research_validation import (
            evaluate_validation,
            validate_split_manifest,
        )

        validation_rows = list(rows(reader.check(evidence.validation)))
        by_request = {r["request_id"]: r for r in approved_requests.values()}
        for row in validation_rows:
            request = by_request.get(row.get("request_id"))
            if (
                request is None
                or row.get("edition_id") != request["edition_id"]
                or row.get("language") != request["language"]
                or row.get("text_sha256") != request["text_sha256"]
            ):
                raise ValueError("validation observation is not bound to an eligible request")
            require_vertex_rights(
                {"rights_authorizations": rights_authorizations},
                request,
                row.get("dispatch_target"),
            )
            response = validate_result(
                reader.json(Artifact.model_validate(row.get("response_artifact"))), request
            )
            actual_prediction = (
                {key: value.score for key, value in response.topics.items()}
                if response.status == "classified"
                else None
            )
            if row.get("prediction") != actual_prediction:
                raise ValueError("validation predictions differ from frozen provider response")
            # Human scores must be recoverable from independently preserved cards,
            # rather than accepted as anonymous values in a metrics spreadsheet.
            for role, reviewer_key in (
                ("human_a", "reviewer_a"),
                ("human_b", "reviewer_b"),
                ("reference", "adjudicator"),
            ):
                card = reader.json(Artifact.model_validate(row.get(role + "_artifact")))
                if (
                    card.get("request_id") != request["request_id"]
                    or card.get("text_sha256") != request["text_sha256"]
                    or card.get("scores") != row.get(role)
                    or not isinstance(card.get("actor"), str)
                    or not card["actor"].strip()
                    or card["actor"].strip().casefold()
                    != str(row.get(reviewer_key, "")).strip().casefold()
                ):
                    raise ValueError("human validation card is not bound to observation")
            if row.get("human_a") != row.get("human_b") and str(
                row.get("adjudicator", "")
            ).strip().casefold() in {
                str(row.get("reviewer_a", "")).strip().casefold(),
                str(row.get("reviewer_b", "")).strip().casefold(),
            }:
                raise ValueError("disagreeing human labels require a third adjudicator")
        profiles = {object_hash(r["profile"]) for r in approved_requests.values()}
        rubrics = {r["rubric_sha256"] for r in approved_requests.values()}
        if len(profiles) != 1 or len(rubrics) != 1:
            raise ValueError("validation requires one frozen execution profile and rubric")
        split_manifest = reader.json(evidence.validation_split)
        split_report = validate_split_manifest(
            split_manifest,
            validation_rows,
            approved_requests.values(),
            expected_contract_version=CONTRACT_VERSION,
        )
        validation = evaluate_validation(validation_rows)
        validation["split"] = split_report
        required_languages = {r["language"] for r in approved_requests.values()}
        if required_languages - set(validation.get("by_language", {})):
            validation["approved"] = False
            validation["reasons"].append("production_languages_missing_from_validation")
    for candidate, result in results.items():
        request = approved_requests.get(candidate)
        if request is None:
            continue
        reader.review(result.review)
        if result.request_id != request["request_id"]:
            raise ValueError("result/request identity mismatch")
        assessment = validate_result(reader.json(result.response), request)
        if assessment.status == "classified":
            accepted_results[candidate] = assessment
    item_reports, table = [], []
    next_quota = {(c["country_code"], c["year"]): c["quota"] for c in cells}
    for row in memberships:
        cell = row["country_code"], row["year"]
        counts[cell]["observed"] += 1
        slot = (*cell, row["position"])
        quota = next_quota[row["country_code"], row["year"]]
        rank_ok, rank_reason = _rank_valid(row, ranks.get(slot), reader, quota=quota)
        lyric_ok = rank_ok and row["candidate_id"] in approved_documents
        prepared_ok = lyric_ok and row["candidate_id"] in approved_requests
        classified_ok = prepared_ok and row["candidate_id"] in accepted_results
        for key, ok in (
            ("G1", rank_ok),
            ("G2", lyric_ok),
            ("G3", prepared_ok),
            ("G5", classified_ok),
        ):
            counts[cell][key] += int(ok)
        item = {k: row[k] for k in ("country_code", "year", "position", "candidate_id")}
        item.update(
            row_sha256=object_hash(row),
            rank_verified=rank_ok,
            rank_reason=rank_reason,
            lyric_verified=lyric_ok,
            lyric_reason=diagnostics[row["candidate_id"]],
            prepared=prepared_ok,
            result_valid=classified_ok,
        )
        item_reports.append(item)
        table_row = {
            **item,
            "title": row.get("title"),
            "artist": row.get("artist"),
            "platform": row.get("platform"),
            "provider": row.get("provider"),
            "text_sha256": None,
            "document_id": None,
            "request_id": None,
            "contract_version": CONTRACT_VERSION,
            "classification_status": "pending",
        }
        doc = approved_documents.get(row["candidate_id"])
        if doc:
            table_row.update(text_sha256=doc.content_sha256, document_id=str(doc.id))
        request = approved_requests.get(row["candidate_id"])
        if request:
            table_row["request_id"] = request["request_id"]
        table_row.update(dict.fromkeys(TOPICS))
        table_row.update({f"{topic}.present": None for topic in TOPICS})
        table.append(table_row)
    ordered = sorted(cells, key=lambda c: (c["country_code"], c["year"]))

    def cell_counts(current, previous=None):
        return [
            (
                (c["country_code"], c["year"]),
                counts[c["country_code"], c["year"]][current],
                counts[c["country_code"], c["year"]][previous] if previous else c["quota"],
            )
            for c in ordered
        ]

    g1 = evaluate_gate("G1", cell_counts("G1"), threshold=targets["G1"])
    g2 = evaluate_gate(
        "G2",
        cell_counts("G2", "G1"),
        predecessor=g1["state"] == "aprovado",
        threshold=targets["G2"],
    )
    g3 = evaluate_gate(
        "G3",
        cell_counts("G3", "G2"),
        predecessor=g2["state"] == "aprovado",
        threshold=targets["G3"],
    )
    g4 = {
        "gate": "G4",
        "state": (
            "pendente"
            if g3["state"] != "aprovado"
            else "aprovado"
            if validation["approved"]
            else "reprovado"
        ),
        "validation": validation,
    }
    result_counts = cell_counts("G5", "G3")
    if g4["state"] != "aprovado":
        result_counts = [(cell, 0, denominator) for cell, _, denominator in result_counts]
    g5 = evaluate_gate(
        "G5", result_counts, predecessor=g4["state"] == "aprovado", threshold=targets["G5"]
    )
    # A syntactically valid response never becomes a scientifically accepted score
    # until the preceding corpus and classifier gates have passed.
    if g4["state"] == "aprovado":
        for row in table:
            result = accepted_results.get(row["candidate_id"])
            if result and row["prepared"]:
                for topic, value in result.topics.items():
                    row[topic] = value.score
                    row[f"{topic}.present"] = value.score >= PRESENCE_THRESHOLD
                row["classification_status"] = "classified"
    # Recheck after reading so a concurrent acquisition cannot change the freeze.
    for path, digest in {**hashes, **reader.checked}.items():
        if file_hash(path) != digest:
            raise ValueError("input changed during audit")
    output.mkdir(parents=True, exist_ok=False)
    observed = len(memberships)
    expected = manifest["requested_positions"]
    report = {
        "protocol": VERSION,
        "gate_policy_version": gate_policy,
        "gate_targets": targets,
        "audit_run_id": run_id,
        "stage_history": str(ledger_path),
        "actor": actor,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "selection_sha256": selection_hash,
        "scope": {
            k: manifest[k]
            for k in ("years", "cutoff", "countries", "country_year_cells", "requested_positions")
        },
        "inventory": {
            "observed_positions": observed,
            "candidate_identities": len(candidates),
            "observed_coverage": observed / expected if expected else None,
            "positions_to_80_percent_observed": max(0, math.ceil(expected * 0.8) - observed),
            "positions_to_ranking_target": max(0, math.ceil(expected * targets["G1"]) - observed),
            "scientifically_verified_positions": g1["numerator"],
            "current_approved_candidates": len(approved_documents),
            "current_approved_texts": len({str(d.id) for d in approved_documents.values()}),
        },
        "gates": [g1, g2, g3, g4, g5],
        "final_coverage_original_universe": (
            g5["numerator"] / expected if expected and g4["state"] == "aprovado" else 0
        ),
        "research_ready": g5["state"] == "aprovado",
        "paid_calls": 0,
        "uploads": 0,
        "attestation_limit": "Evidence binding is checked; reviewer identity is not authenticated.",
        "input_hashes": {**hashes, **reader.checked},
        "canonical_state": {
            str(d.id): canonical_fingerprint(d) for d in approved_documents.values()
        },
        "rights_authorizations": rights_authorizations,
        "local_statuses": local_statuses,
        "database_state": (
            "current_documents_read_only"
            if evidence.lyrics
            else "not_queried_no_document_evidence_supplied"
        ),
    }
    # The effective implementation is part of the freeze as well as the data.
    package = Path(__file__).parent
    for name in (
        "research_flow.py",
        "research_validation.py",
        "research_stage_ledger.py",
        "research_flow_cli.py",
        "research_classification_service.py",
        "research_rankings.py",
        "lyrics/research_contract.py",
        "lyrics/research_vertex_payload.py",
        "lyrics/classification_gate.py",
        "lyrics/review_protocol.py",
        "lyrics/revision_protocol.py",
    ):
        code = package / name
        if code.is_file():
            report["input_hashes"][str(code)] = file_hash(code)
    write_json(output / "report.json", report)
    write_json(output / "evidence-schema.json", ResearchEvidence.model_json_schema())
    write_json(
        output / "evidence-template.json",
        {
            "schema_version": "research-evidence-v4",
            "selection_sha256": selection_hash,
            "rankings": [],
            "lyrics": [],
            "preparations": [],
            "validation": None,
            "validation_split": None,
            "results": [],
        },
    )
    write_json(output / "contract.json", contract())
    write_json(output / "local-statuses.json", local_statuses)
    packages = {}
    for package in (
        "polars",
        "pydantic",
        "sqlalchemy",
        "psycopg",
        "scipy",
        "typer",
        "google-genai",
        "google-cloud-storage",
    ):
        try:
            packages[package] = version(package)
        except PackageNotFoundError:
            packages[package] = None
    write_json(
        output / "environment.json",
        {"python": sys.version, "platform": platform.platform(), "packages": packages},
    )
    write_rows(output / "items.jsonl", item_reports)
    write_csv(
        output / "gates.csv",
        [c for g in (g1, g2, g3, g5) for c in g["cells"]],
        ["gate", "country_code", "year", "numerator", "denominator", "ratio", "state"],
    )
    write_csv(
        output / "preparatory-table.csv",
        table,
        list(table[0])
        if table
        else [
            "country_code",
            "year",
            "position",
            "candidate_id",
            *TOPICS,
            *(f"{topic}.present" for topic in TOPICS),
        ],
    )
    recovery = []
    for c in ordered:
        key = c["country_code"], c["year"]
        recovery.append(
            {
                "country_code": key[0],
                "year": key[1],
                "quota": c["quota"],
                "observed": counts[key]["observed"],
                "verified": counts[key]["G1"],
                "missing_observed": (
                    max(0, c["quota"] - counts[key]["observed"]) if c["quota"] is not None else None
                ),
                "action": (
                    "resolve_quota_applicability"
                    if c["quota"] is None
                    else "find_historical_source"
                    if not counts[key]["observed"]
                    else "reconstruct_and_review_full_ranking"
                ),
            }
        )
    recovery.sort(
        key=lambda c: (
            c["quota"] is not None,
            c["observed"] > 0,
            -(c["missing_observed"] or 0),
            c["country_code"],
            c["year"],
        )
    )
    write_rows(output / "ranking-recovery-queue.jsonl", recovery)
    write_rows(
        output / "lyric-review-queue.jsonl",
        [
            {
                "candidate_id": candidate,
                "reason": reason,
                "action": "review_canonical_identity_integrity_and_rights",
            }
            for candidate, reason in sorted(diagnostics.items())
            if reason != "approved"
        ],
    )
    artifacts = {p.name: file_hash(p) for p in output.iterdir() if p.is_file()}
    write_json(
        output / "manifest.json",
        {
            "protocol": VERSION,
            "selection_sha256": selection_hash,
            "artifacts": artifacts,
            "input_hashes": report["input_hashes"],
            "producer_sha256": file_hash(Path(__file__)),
        },
    )
    return report
