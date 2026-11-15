import csv
import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from chart_observatory import research_flow as flow
from chart_observatory.lyrics.campaign_budget import CampaignBudget
from chart_observatory.lyrics.research_contract import (
    CONTRACT_VERSION,
    build_profile,
    prepare_request,
    rubric_draft,
)
from chart_observatory.lyrics.review_protocol import TOPICS
from chart_observatory.lyrics.revision_protocol import RevisionRegistry, canonical_json
from chart_observatory.research_classification_service import ResearchClassificationService


def response(request, score=0):
    return {
        "contract_version": CONTRACT_VERSION,
        "request_id": request["request_id"],
        "status": "classified",
        "topics": {
            topic: {
                "score": score,
                "evidence_segments": ["L000001"] if score else [],
                "justification": "Synthetic fixture evidence.",
            }
            for topic in TOPICS
        },
        "auxiliary": {},
    }


@pytest.fixture
def environment(tmp_path):
    rubric = rubric_draft()
    rubric["status"] = "accepted"
    rubric["acceptance"] = {
        "actor": "reviewer",
        "at": datetime.now(UTC).isoformat(),
        "rubric_sha256": hashlib.sha256(canonical_json(rubric).encode()).hexdigest(),
    }
    profile = build_profile(
        model_id="test",
        resolved_model_version="test-fixed-001",
        generation_configuration={
            "temperature": 0,
            "provider": "vertex_ai",
            "region": "us-central1",
            "retention_days": 0,
        },
        rubric=rubric,
    )
    documents, requests = {}, []
    for index in range(2):
        text = f"Texto sintético {index}.\nRepetição.\nRepetição."
        doc = SimpleNamespace(
            id=uuid4(),
            canonical_track_id=uuid4(),
            language_code="pt",
            text=text,
            content_sha256=hashlib.sha256(text.encode()).hexdigest(),
            source="fixture",
            rights_status="authorized",
            metadata_json={},
        )
        documents[str(doc.id)] = doc
        requests.append(
            prepare_request(
                edition_id=str(doc.id),
                text=text,
                language="pt",
                profile=profile,
                rubric=rubric,
            )
        )
    audit = tmp_path / "audit"
    audit.mkdir()
    with (audit / "preparatory-table.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["request_id", "document_id", "prepared"])
        writer.writeheader()
        writer.writerows(
            {
                "request_id": request["request_id"],
                "document_id": request["edition_id"],
                "prepared": "True",
            }
            for request in requests
        )
    report = {
        "canonical_state": {
            identity: flow.canonical_fingerprint(doc) for identity, doc in documents.items()
        },
        "gates": [{"gate": "G4", "validation": {"by_language": {"pt": {"approved": True}}}}],
        "rights_authorizations": {
            identity: {
                "document_id": identity,
                "text_sha256": doc.content_sha256,
                "storage_authorized": True,
                "processing_authorized": True,
                "publication_authorized": False,
                "vertex_authorizations": [
                    {
                        "provider": "vertex_ai",
                        "model_id": "test",
                        "resolved_model_version": "test-fixed-001",
                        "region": "us-central1",
                        "retention_days": 0,
                        "authorized": True,
                    }
                ],
            }
            for identity, doc in documents.items()
        },
    }
    flags = {"blocked": False, "gates": [], "online_calls": 0, "batch_calls": 0}

    def preflight(audit, gate, **kwargs):
        flags["gates"].append(gate)
        if flags["blocked"]:
            raise ValueError("research stage is blocked")
        return report

    def online(request, *, target):
        flags["online_calls"] += 1
        return {
            "response": response(request),
            "actual_cost_usd": "0.01",
            "billing_evidence": {"fixture": "provider usage"},
            "dispatch_target": target,
        }

    def batch(manifest):
        flags["batch_calls"] += 1
        return {
            "provider_job_id": "test-job",
            "dispatch_target": manifest["dispatch_target"],
        }

    budget = CampaignBudget(tmp_path / "shared-budget.sqlite")
    budget.attest(
        external_complete=True, provider_complete=True, evidence={"fixture": "reconciled"}
    )
    registry = RevisionRegistry(tmp_path / "registry.sqlite")
    kwargs = dict(
        registry=registry,
        budget=budget,
        transport=SimpleNamespace(classify=online, submit_batch=batch),
        audit=audit,
        project=tmp_path,
        shared_budget_path=budget.path,
        vertex_region="us-central1",
        vertex_retention_days=0,
        preflight=preflight,
        document_reader=lambda project, ids: documents,
        gate_loader=lambda: SimpleNamespace(assess=lambda doc: SimpleNamespace(eligible=True)),
        journal_root=tmp_path / "private-journal",
        shared_registry_path=registry.path,
    )
    return SimpleNamespace(
        service=ResearchClassificationService(**kwargs),
        kwargs=kwargs,
        requests=requests,
        documents=documents,
        flags=flags,
        budget=budget,
        registry=registry,
        report=report,
    )


def test_paid_transport_is_disabled_by_default_and_creates_no_reservations(environment):
    env = environment
    with pytest.raises(ValueError, match="not explicitly authorized"):
        env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    assert env.flags["online_calls"] == 0
    assert env.budget.snapshot()["committed_usd"] == "0"
    with env.registry.connect() as conn:
        assert conn.execute("SELECT count(*) FROM classification_requests").fetchone()[0] == 0


@pytest.mark.parametrize(
    "change",
    [
        "storage",
        "processing",
        "model",
        "version",
        "region",
        "retention",
        "vertex_disabled",
        "missing_grant",
        "service_region",
    ],
)
def test_online_dispatch_requires_exact_processing_and_vertex_rights(environment, change):
    env = environment
    env.service.authorized = True
    grant = env.report["rights_authorizations"][env.requests[0]["edition_id"]]
    vertex = grant["vertex_authorizations"][0]
    if change == "storage":
        grant["storage_authorized"] = False
    elif change == "processing":
        grant["processing_authorized"] = False
    elif change == "model":
        vertex["model_id"] = "other-model"
    elif change == "version":
        vertex["resolved_model_version"] = "other-version"
    elif change == "region":
        vertex["region"] = "europe-west4"
    elif change == "retention":
        vertex["retention_days"] = 30
    elif change == "vertex_disabled":
        vertex["authorized"] = False
    elif change == "missing_grant":
        grant["vertex_authorizations"].clear()
    else:
        env.service.vertex_region = "europe-west4"

    with pytest.raises(ValueError, match="authorized|authorization|region|grant"):
        env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    assert env.flags["online_calls"] == 0
    assert env.budget.snapshot()["committed_usd"] == "0"
    with env.registry.connect() as conn:
        assert conn.execute("SELECT count(*) FROM classification_requests").fetchone()[0] == 0


def test_batch_dispatch_without_processing_rights_has_no_reservation(environment):
    env = environment
    env.service.authorized = True
    env.report["rights_authorizations"][env.requests[0]["edition_id"]]["processing_authorized"] = (
        False
    )
    manifest = env.service.prepare_batch(env.requests)
    assert manifest["dispatch_target"] == {
        "provider": "vertex_ai",
        "model_id": "test",
        "resolved_model_version": "test-fixed-001",
        "region": "us-central1",
        "retention_days": 0,
    }
    with pytest.raises(ValueError, match="not explicitly authorized for external processing"):
        env.service.submit_batch(manifest, max_cost_usd="0.10")
    assert env.flags["batch_calls"] == 0
    assert env.budget.snapshot()["committed_usd"] == "0"
    with env.registry.connect() as conn:
        assert conn.execute("SELECT count(*) FROM classification_requests").fetchone()[0] == 0


def test_online_uses_full_signature_revalidates_and_reuses_without_second_spend(environment):
    env = environment
    env.service.authorized = True
    first = env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    second = env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    assert first["status"] == "completed"
    assert second["status"] == "reused"
    assert env.flags["online_calls"] == 1
    assert all(gate == "G4" for gate in env.flags["gates"])
    assert env.budget.snapshot()["committed_usd"] == "0.01"
    env.flags["blocked"] = True
    with pytest.raises(ValueError, match="blocked"):
        env.service.classify_online(env.requests[0], max_cost_usd="0.05")


def test_unknown_outcome_holds_finance_and_exclusive_request_without_retry(environment):
    env = environment
    env.service.authorized = True

    def unknown(request, *, target):
        env.flags["online_calls"] += 1
        raise TimeoutError("synthetic timeout")

    env.service.transport.classify = unknown
    with pytest.raises(TimeoutError):
        env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    with pytest.raises(ValueError, match="do not retry"):
        env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    assert env.flags["online_calls"] == 1
    assert env.budget.snapshot()["committed_usd"] == "0.05"
    with env.registry.connect() as conn:
        assert (
            conn.execute("SELECT state FROM classification_requests").fetchone()[0] == "uncertain"
        )


def test_changed_profile_or_canonical_language_cannot_reuse_old_gate(environment):
    env = environment
    env.service.authorized = True
    changed = dict(env.requests[0])
    changed["profile"] = {**changed["profile"], "model_id": "other"}
    with pytest.raises(ValueError):
        env.service.classify_online(changed, max_cost_usd="0.05")
    env.documents[env.requests[0]["edition_id"]].language_code = "en"
    with pytest.raises(ValueError, match="canonical"):
        env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    assert env.flags["online_calls"] == 0


def test_batch_preparation_is_private_unsent_and_does_not_reserve(environment, tmp_path):
    env = environment
    manifest = env.service.prepare_batch(env.requests, output=tmp_path / "batch")
    assert manifest["requests"][0]["reuse_descriptor"] == env.requests[0]["reuse_descriptor"]
    assert manifest["paid_calls"] == manifest["uploads"] == 0
    assert env.flags["batch_calls"] == 0
    assert env.budget.snapshot()["committed_usd"] == "0"
    assert all(gate == "G3" for gate in env.flags["gates"])
    root = tmp_path / "batch"
    payloads = [
        json.loads(line)
        for line in (root / "vertex-input.private.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    bindings = [
        json.loads(line)
        for line in (root / "vertex-bindings.private.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert len(payloads) == len(bindings) == len(env.requests)
    for payload, binding, request in zip(payloads, bindings, env.requests, strict=True):
        content = json.loads(payload["request"]["contents"][0]["parts"][0]["text"])
        assert content["request_id"] == binding["request_id"] == request["request_id"]
        assert (
            binding["request_sha256"]
            == hashlib.sha256(canonical_json(payload["request"]).encode()).hexdigest()
        )
    exported = json.loads((root / "manifest.json").read_text())
    for name, digest in exported["artifacts"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest


def test_batch_submission_imports_by_request_id_out_of_order_and_is_idempotent(environment):
    env = environment
    env.service.authorized = True
    manifest = env.service.prepare_batch(env.requests)
    submission = env.service.submit_batch(manifest, max_cost_usd="0.10")
    raws = [response(request, score=index) for index, request in enumerate(env.requests)]
    result = env.service.import_responses(submission, list(reversed(raws)))
    assert len(result["imported"]) == 2
    assert not result["missing_request_ids"]
    repeated = env.service.import_responses(submission, raws)
    assert len(repeated["reused"]) == 2
    assert not repeated["imported"]
    assert env.flags["batch_calls"] == 1
    # No invoice was supplied: the conservative commitment must remain intact.
    assert env.budget.snapshot()["committed_usd"] == "0.10"


def test_batch_rejects_invalid_or_revoked_outputs_before_importing_any(environment):
    env = environment
    env.service.authorized = True
    manifest = env.service.prepare_batch(env.requests)
    submission = env.service.submit_batch(manifest, max_cost_usd="0.10")
    raws = [response(request) for request in env.requests]
    raws[-1]["topics"][next(iter(TOPICS))]["score"] = 9
    with pytest.raises(ValueError):
        env.service.import_responses(submission, raws)
    with env.registry.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM classification_requests WHERE state='completed'"
            ).fetchone()[0]
            == 0
        )
    env.flags["blocked"] = True
    with pytest.raises(ValueError, match="blocked"):
        env.service.import_responses(submission, [response(request) for request in env.requests])


def test_shared_ledger_and_150_dollar_operator_cap_cannot_be_bypassed(environment):
    env = environment
    with pytest.raises(ValueError, match="shared campaign ledger"):
        ResearchClassificationService(**{**env.kwargs, "shared_budget_path": "other-ledger.sqlite"})
    for category, amount in (
        ("main", "100"),
        ("review", "25"),
        ("services", "10"),
        ("contingency", "14.99"),
    ):
        env.budget.record_existing(
            category,
            category,
            amount,
            amount,
            settled=True,
            evidence={"fixture": "prior expense"},
        )
    env.service.authorized = True
    with pytest.raises(ValueError):
        env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    assert env.flags["online_calls"] == 0


def test_submission_journal_is_durable_before_transport_and_recovers_batch_binding(environment):
    env = environment
    env.service.authorized = True

    def batch(manifest):
        events = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in env.service.journal_root.glob("*.json")
        ]
        submitting = next(event for event in events if event["state"] == "submitting_batch")
        assert submitting["payload"]["manifest"]["manifest_id"] == manifest["manifest_id"]
        assert len(submitting["payload"]["owners"]) == 2
        assert submitting["payload"]["budget_key"]
        return {
            "provider_job_id": "durable-job",
            "dispatch_target": manifest["dispatch_target"],
        }

    env.service.transport.submit_batch = batch
    manifest = env.service.prepare_batch(env.requests)
    submission = env.service.submit_batch(manifest, max_cost_usd="0.10")
    events = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in env.service.journal_root.glob("*.json")
    ]
    recovered = next(event["payload"] for event in events if event["state"] == "batch_submitted")
    assert recovered == submission
    assert recovered["provider_job_id"] == "durable-job"


def test_batch_boundaries_revalidate_once_instead_of_once_per_request(environment):
    env = environment
    env.service.authorized = True
    reads = []
    original_reader = env.service.document_reader

    def reader(project, identities):
        reads.append(set(identities))
        return original_reader(project, identities)

    env.service.document_reader = reader
    manifest = env.service.prepare_batch(env.requests)
    assert len(env.flags["gates"]) == len(reads) == 1
    assert len(reads[0]) == 2
    submission = env.service.submit_batch(manifest, max_cost_usd="0.10")
    # One context at submission entry and a fresh context immediately before transport.
    assert len(env.flags["gates"]) == len(reads) == 3
    env.service.import_responses(submission, [response(request) for request in env.requests])
    assert len(env.flags["gates"]) == len(reads) == 4


def test_new_approved_profile_on_later_audit_preserves_immutable_edition_identity(
    environment,
    tmp_path,
):
    env = environment
    env.service.authorized = True
    env.service.classify_online(env.requests[0], max_cost_usd="0.05")
    old = env.requests[0]
    rubric = old["contract"]["rubric"]
    profile = build_profile(
        model_id="test",
        resolved_model_version="test-fixed-002",
        generation_configuration={
            "temperature": 0,
            "provider": "vertex_ai",
            "region": "us-central1",
            "retention_days": 0,
        },
        rubric=rubric,
    )
    document = env.documents[old["edition_id"]]
    new_request = prepare_request(
        edition_id=old["edition_id"],
        text=document.text,
        language="pt",
        profile=profile,
        rubric=rubric,
    )
    env.report["rights_authorizations"][old["edition_id"]]["vertex_authorizations"].append(
        {
            "provider": "vertex_ai",
            "model_id": "test",
            "resolved_model_version": "test-fixed-002",
            "region": "us-central1",
            "retention_days": 0,
            "authorized": True,
        }
    )
    new_audit = tmp_path / "later-audit"
    new_audit.mkdir()
    with (new_audit / "preparatory-table.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["request_id", "document_id", "prepared"])
        writer.writeheader()
        writer.writerow(
            {
                "request_id": new_request["request_id"],
                "document_id": old["edition_id"],
                "prepared": "True",
            }
        )
    service = ResearchClassificationService(
        **{**env.kwargs, "audit": new_audit, "authorized": True}
    )
    result = service.classify_online(new_request, max_cost_usd="0.05")
    assert result["status"] == "completed"
    assert env.flags["online_calls"] == 2
    with env.registry.connect() as conn:
        assert conn.execute("SELECT count(*) FROM textual_editions").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM classification_requests").fetchone()[0] == 2


def test_wrong_import_owner_rejects_entire_response_set_and_partial_invoice_does_not_settle(
    environment,
):
    env = environment
    env.service.authorized = True
    submission = env.service.submit_batch(
        env.service.prepare_batch(env.requests), max_cost_usd="0.10"
    )
    wrong = {
        **submission,
        "owners": {**submission["owners"], env.requests[-1]["request_id"]: "wrong"},
    }
    wrong["submission_id"] = flow.object_hash(
        {key: value for key, value in wrong.items() if key != "submission_id"}
    )
    with pytest.raises(ValueError, match="exclusive reservation"):
        env.service.import_responses(wrong, [response(request) for request in env.requests])
    with env.registry.connect() as conn:
        completed = conn.execute(
            "SELECT count(*) FROM classification_requests WHERE state='completed'"
        ).fetchone()[0]
        assert completed == 0
    env.service.import_responses(
        submission,
        [response(env.requests[0])],
        actual_cost_usd="0.01",
        billing_evidence={"complete": False, "partial": "invoice"},
    )
    assert env.budget.snapshot()["committed_usd"] == "0.10"
