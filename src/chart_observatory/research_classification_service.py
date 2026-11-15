"""New-contract orchestration through injected transports; disabled for spending by default.

This does not alter the legacy dispatcher. A caller supplies an existing reconciled
campaign ledger, and must explicitly authorize transport use. No SDK is imported.
"""

from __future__ import annotations

import csv
import hashlib
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from chart_observatory import research_flow as flow
from chart_observatory.lyrics.campaign_budget import DEFAULT_BUDGET_PATH, money
from chart_observatory.lyrics.classification_gate import ClassificationGate
from chart_observatory.lyrics.research_contract import (
    complete_reserved_result,
    validate_result,
    validate_rubric,
    verify_request,
)
from chart_observatory.lyrics.research_vertex_payload import vertex_payload
from chart_observatory.lyrics.revision_protocol import (
    ClassificationKey,
    canonical_json,
    normalize_text,
)

SERVICE_VERSION = "research-classification-service-v2"


class ResearchClassificationService:
    def __init__(
        self,
        *,
        registry,
        budget,
        transport,
        audit,
        project,
        authorized=False,
        operator_cap_usd=Decimal("150"),
        shared_budget_path=DEFAULT_BUDGET_PATH,
        preflight=None,
        document_reader=None,
        gate_loader=None,
        journal_root=None,
        shared_registry_path=None,
        vertex_region: str | None = None,
        vertex_retention_days: int | None = None,
    ):
        self.registry, self.budget, self.transport = registry, budget, transport
        self.audit, self.project = Path(audit).resolve(), Path(project).resolve()
        registry_path = (
            Path(shared_registry_path)
            if shared_registry_path is not None
            else (self.project / "data/runtime/research-classification-registry.sqlite")
        )
        if Path(registry.path).resolve() != registry_path.resolve():
            raise ValueError(
                "use the declared shared research registry; no isolated request registry"
            )
        self.authorized = authorized is True
        self.vertex_region = (
            vertex_region.strip() or None if isinstance(vertex_region, str) else None
        )
        self.vertex_retention_days = vertex_retention_days
        if vertex_retention_days is not None and (
            type(vertex_retention_days) is not int or vertex_retention_days < 0
        ):
            raise ValueError("configured Vertex retention days must be a nonnegative integer")
        self.cap = min(Decimal("150"), money(operator_cap_usd))
        if self.cap <= 0:
            raise ValueError("positive operator cap required")
        if Path(budget.path).resolve() != Path(shared_budget_path).resolve():
            raise ValueError("use the declared shared campaign ledger; no separate spending ledger")
        self.preflight = preflight or flow.require_research_stage
        self.document_reader = document_reader or flow.read_canonical_documents
        self.gate_loader = gate_loader or ClassificationGate.load
        self.journal_root = (
            Path(journal_root)
            if journal_root is not None
            else (self.project / "data/runtime/research-classification-journal")
        )

    def _journal(self, subject, state, payload):
        """Private immutable events, durably renamed before any provider operation."""
        self.journal_root.mkdir(parents=True, exist_ok=True)
        path = self.journal_root / f"{subject}-{uuid4()}.json"
        temporary = path.with_suffix(".tmp")
        event = {
            "version": SERVICE_VERSION,
            "private": True,
            "subject": subject,
            "state": state,
            "at": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(event))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        return str(path)

    def _context(self, requests, phase):
        if phase not in {"pilot", "production"}:
            raise ValueError("phase must be pilot or production")
        report = self.preflight(
            self.audit,
            "G3" if phase == "pilot" else "G4",
            project=self.project,
        )
        with (self.audit / "preparatory-table.csv").open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            allowed = {
                (row.get("request_id"), row.get("document_id"))
                for row in csv.DictReader(handle)
                if row.get("prepared") == "True"
            }
        identities = {UUID(request["edition_id"]) for request in requests}
        return {
            "report": report,
            "allowed": allowed,
            "documents": self.document_reader(self.project, list(identities)),
            "gate": self.gate_loader(),
        }

    def _preflight(self, request, phase, context=None):
        verify_request(request)
        validate_rubric(request["contract"]["rubric"], require_accepted=True)
        context = context or self._context([request], phase)
        report = context["report"]
        if (request["request_id"], request["edition_id"]) not in context["allowed"]:
            raise ValueError("request/profile is not in the currently approved audit")
        identity = request["edition_id"]
        document = context["documents"].get(identity)
        if (
            document is None
            or identity not in report["canonical_state"]
            or flow.canonical_fingerprint(document) != report["canonical_state"][identity]
            or not context["gate"].assess(document).eligible
            or not isinstance(document.text, str)
            or hashlib.sha256(document.text.encode()).hexdigest() != request["text_sha256"]
            or document.content_sha256 != request["text_sha256"]
            or document.language_code != request["language"]
        ):
            raise ValueError("current canonical identity, text, language or approval changed")
        if phase == "production":
            g4 = next(gate for gate in report["gates"] if gate["gate"] == "G4")
            if (
                not g4["validation"]
                .get("by_language", {})
                .get(request["language"], {})
                .get("approved")
            ):
                raise ValueError("request language is not independently homologated")
        return document

    def _dispatch_target(self, request, *, required):
        generation = request["profile"]["configuration"].get("generation", {})
        region = generation.get("region")
        retention_days = generation.get("retention_days")
        if (
            generation.get("provider") != "vertex_ai"
            or not isinstance(region, str)
            or not region.strip()
            or type(retention_days) is not int
        ):
            if required:
                raise ValueError(
                    "request must bind Vertex provider, region and retention in its profile"
                )
            return None
        if retention_days < 0:
            raise ValueError("Vertex retention days must be nonnegative")
        if self.vertex_region is not None and region != self.vertex_region:
            raise ValueError("service region differs from the prepared Vertex target")
        if self.vertex_retention_days is not None and retention_days != self.vertex_retention_days:
            raise ValueError("service retention differs from the prepared Vertex target")
        configuration = request["profile"]["configuration"]
        target = {
            "provider": "vertex_ai",
            "model_id": request["profile"]["model_id"],
            "resolved_model_version": configuration["resolved_model_version"],
            "region": region,
            "retention_days": retention_days,
        }
        return target

    @staticmethod
    def _key(request):
        key = ClassificationKey(**request["reuse_descriptor"])
        if key.digest != request["reuse_key"]:
            raise ValueError("inconsistent complete reuse signature")
        return key

    def _cached(self, request):
        value = self.registry.result(self._key(request))
        if value is None:
            return None
        raw = value["result"].get("research_result")
        if not raw:
            raise ValueError("legacy result is not compatible with the new research contract")
        validate_result(raw, request)
        return raw

    def _spending(self, category, amount):
        if not self.authorized:
            raise ValueError("paid transport is not explicitly authorized")
        snapshot = self.budget.snapshot()
        if (
            snapshot.get("reconciled") is not True
            or snapshot.get("within_limits") is not True
            or money(snapshot["committed_usd"]) > self.cap
        ):
            raise ValueError("shared campaign ledger is unreconciled or exceeds the effective cap")
        amount = money(amount)
        if amount <= 0:
            raise ValueError("positive conservative maximum cost required")
        self.budget.preview(category, amount, operator_cap=self.cap)
        return amount

    def _register(self, request, document):
        norm = normalize_text(document.text)
        self.registry.register_edition(
            request["edition_id"],
            norm.normalized_hash,
            norm.version,
            identity_confirmed=True,
            integrity_validated=True,
            original_hash=norm.original_hash,
            language=document.language_code,
            evidence={
                "document_id": str(document.id),
                "recording_id": str(document.canonical_track_id),
                "original_sha256": document.content_sha256,
                "source": document.source,
            },
        )

    def _unknown(self, request, owner):
        self.registry.mark_outcome_unknown(self._key(request), owner)

    def classify_online(self, request: dict, *, max_cost_usd, phase="production") -> dict:
        context = self._context([request], phase)
        document = self._preflight(request, phase, context=context)
        cached = self._cached(request)
        if cached is not None:
            return {"status": "reused", "response": cached}
        if not self.authorized:
            raise ValueError("paid transport is not explicitly authorized")
        target = self._dispatch_target(request, required=True)
        flow.require_vertex_rights(context["report"], request, target)
        category = "pilot" if phase == "pilot" else "main"
        amount = self._spending(category, max_cost_usd)
        self._register(request, document)
        key = self._key(request)
        owner = self.registry.reserve(key)
        if owner is None:
            raise ValueError("request is already reserved, submitted or uncertain; do not retry")
        budget_key = "research:online:" + key.digest
        try:
            if not self.budget.reserve(
                budget_key,
                category,
                amount,
                {"request_id": request["request_id"], "signature": key.digest},
                operator_cap=self.cap,
            ):
                raise ValueError(
                    "existing financial reservation does not grant transport ownership"
                )
            self._preflight(request, phase)
            pending = {"request": request, "owner": owner, "budget_key": budget_key}
            self._journal(request["request_id"], "submitting_online", pending)
            outcome = self.transport.classify(request, target=target)
            if outcome.get("dispatch_target") != target:
                raise ValueError("provider did not confirm the authorized Vertex target")
            self._journal(
                request["request_id"], "online_response_received", {**pending, "outcome": outcome}
            )
            current_context = self._context([request], phase)
            self._preflight(request, phase, context=current_context)
            flow.require_vertex_rights(current_context["report"], request, target)
            raw = outcome["response"]
            validate_result(raw, request)
            complete_reserved_result(self.registry, key, owner, raw, request, method="provider")
            if outcome.get("actual_cost_usd") is not None and outcome.get("billing_evidence"):
                self.budget.settle(
                    budget_key, outcome["actual_cost_usd"], outcome["billing_evidence"]
                )
            return {"status": "completed", "response": raw, "budget_key": budget_key}
        except Exception:
            if self.registry.result(key) is None:
                self._unknown(request, owner)
                self._journal(
                    request["request_id"],
                    "uncertain_online",
                    {"request": request, "owner": owner, "budget_key": budget_key},
                )
            raise

    def _build_manifest(self, requests, phase, context):
        if not requests:
            raise ValueError("batch must contain at least one request")
        seen_ids, seen_keys = set(), set()
        for request in requests:
            self._preflight(request, phase, context=context)
            if request["request_id"] in seen_ids or request["reuse_key"] in seen_keys:
                raise ValueError("duplicate request or equivalent signature in batch")
            seen_ids.add(request["request_id"])
            seen_keys.add(request["reuse_key"])
        targets = [self._dispatch_target(request, required=False) for request in requests]
        dispatch_target = targets[0]
        if any(target != dispatch_target for target in targets[1:]):
            raise ValueError("one batch must use a single exact Vertex dispatch target")
        manifest = {
            "version": SERVICE_VERSION,
            "phase": phase,
            "private": True,
            "audit": str(self.audit),
            "requests": requests,
            "dispatch_target": dispatch_target,
            "status": "prepared_not_submitted",
            "paid_calls": 0,
            "uploads": 0,
        }
        manifest["manifest_id"] = flow.object_hash(manifest)
        return manifest

    def prepare_batch(self, requests: list[dict], *, phase="pilot", output=None) -> dict:
        context = self._context(requests, phase)
        manifest = self._build_manifest(requests, phase, context)
        payloads = (
            [vertex_payload(request) for request in requests]
            if manifest["dispatch_target"] is not None
            else []
        )
        if any(payload["dispatch_target"] != manifest["dispatch_target"] for payload in payloads):
            raise ValueError("serialized payload lost the exact Vertex target")
        if output is not None:
            output = Path(output)
            output.mkdir(parents=True, exist_ok=False)
            flow.write_json(output / "request-manifest.private.json", manifest)
            flow.write_rows(output / "requests.private.jsonl", requests)
            if payloads:
                flow.write_rows(
                    output / "vertex-input.private.jsonl",
                    [{"request": payload["request"]} for payload in payloads],
                )
                flow.write_rows(
                    output / "vertex-bindings.private.jsonl",
                    [
                        {
                            "request_id": payload["request_id"],
                            "reuse_key": payload["reuse_key"],
                            "model": payload["model"],
                            "request_sha256": hashlib.sha256(
                                canonical_json(payload["request"]).encode()
                            ).hexdigest(),
                        }
                        for payload in payloads
                    ],
                )
            flow.write_json(
                output / "manifest.json",
                {
                    "version": SERVICE_VERSION,
                    "private": True,
                    "paid_calls": 0,
                    "uploads": 0,
                    "artifacts": {
                        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in output.iterdir()
                        if path.is_file()
                    },
                },
            )
        return manifest

    def _batch(self, manifest):
        body = {key: value for key, value in manifest.items() if key != "manifest_id"}
        if (
            manifest.get("version") != SERVICE_VERSION
            or manifest.get("manifest_id") != flow.object_hash(body)
            or manifest.get("audit") != str(self.audit)
        ):
            raise ValueError("batch manifest or complete execution signatures changed")
        context = self._context(manifest["requests"], manifest["phase"])
        rebuilt = self._build_manifest(manifest["requests"], manifest["phase"], context)
        if canonical_json(rebuilt) != canonical_json(manifest):
            raise ValueError("batch manifest is not the exact prepared contract")
        return context

    def submit_batch(self, manifest: dict, *, max_cost_usd) -> dict:
        context = self._batch(manifest)
        # A prepared manifest is exact: reuse must be resolved before preparing a
        # new manifest, rather than silently changing the submitted request set.
        if any(self._cached(request) is not None for request in manifest["requests"]):
            raise ValueError("batch contains completed requests; prepare only outstanding items")
        if not self.authorized:
            raise ValueError("paid transport is not explicitly authorized")
        target = manifest.get("dispatch_target")
        if target is None:
            raise ValueError("batch has no explicit Vertex model, region and retention target")
        for request in manifest["requests"]:
            flow.require_vertex_rights(context["report"], request, target)
        phase = manifest["phase"]
        category = "pilot" if phase == "pilot" else "main"
        amount = self._spending(category, max_cost_usd)
        owners = {}
        try:
            for request in manifest["requests"]:
                self._register(request, self._preflight(request, phase, context=context))
                owner = self.registry.reserve(self._key(request))
                if owner is None:
                    raise ValueError(
                        "batch item already reserved/submitted/uncertain; do not retry"
                    )
                owners[request["request_id"]] = owner
            budget_key = "research:batch:" + manifest["manifest_id"]
            if not self.budget.reserve(
                budget_key,
                category,
                amount,
                {"manifest_id": manifest["manifest_id"]},
                operator_cap=self.cap,
            ):
                raise ValueError(
                    "existing financial reservation does not grant submission ownership"
                )
            self._batch(manifest)
            pending = {"manifest": manifest, "owners": owners, "budget_key": budget_key}
            self._journal(manifest["manifest_id"], "submitting_batch", pending)
            outcome = self.transport.submit_batch(manifest)
            if (
                not isinstance(outcome.get("provider_job_id"), str)
                or not outcome["provider_job_id"].strip()
            ):
                raise ValueError("provider did not return an identifiable batch job")
            if outcome.get("dispatch_target") != target:
                raise ValueError("provider did not confirm the authorized Vertex batch target")
            submission = {
                "manifest": manifest,
                "owners": owners,
                "budget_key": budget_key,
                "provider_job_id": outcome["provider_job_id"],
                "dispatch_target": target,
            }
            submission["submission_id"] = flow.object_hash(submission)
            self._journal(manifest["manifest_id"], "batch_submitted", submission)
            return submission
        except Exception as exc:
            if owners:
                self._journal(
                    manifest["manifest_id"],
                    "uncertain_batch",
                    {"manifest": manifest, "owners": owners, "error_type": type(exc).__name__},
                )
            raise
        finally:
            # Both accepted batch jobs and unknown provider outcomes remain
            # exclusively held until a validated import or manual reconciliation.
            for request in manifest["requests"]:
                owner = owners.get(request["request_id"])
                if owner:
                    self._unknown(request, owner)

    def import_responses(
        self,
        submission: dict,
        responses: list[dict],
        *,
        actual_cost_usd=None,
        billing_evidence=None,
    ) -> dict:
        body = {key: value for key, value in submission.items() if key != "submission_id"}
        if submission.get("submission_id") != flow.object_hash(body):
            raise ValueError("submission binding changed")
        manifest = submission["manifest"]
        context = self._batch(manifest)
        target = submission.get("dispatch_target")
        if target is None or target != manifest.get("dispatch_target"):
            raise ValueError("submission lost its authorized Vertex target")
        requests = {request["request_id"]: request for request in manifest["requests"]}
        if set(submission["owners"]) != set(requests):
            raise ValueError("submission owners do not cover the exact request set")
        keyed = {}
        for raw in responses:
            identity = raw.get("request_id")
            if identity not in requests or identity in keyed:
                raise ValueError("unknown or duplicate response request_id")
            validate_result(raw, requests[identity])
            keyed[identity] = raw
        # Validate every output and current approval before importing any row.
        for identity in keyed:
            self._preflight(requests[identity], manifest["phase"], context=context)
            flow.require_vertex_rights(context["report"], requests[identity], target)
            cached = self._cached(requests[identity])
            if cached is not None and canonical_json(cached) != canonical_json(keyed[identity]):
                raise ValueError("conflicting output for an immutable completed request")
            with self.registry.connect() as conn:
                reservation = conn.execute(
                    "SELECT owner,descriptor_json FROM classification_requests WHERE request_key=?",
                    (requests[identity]["reuse_key"],),
                ).fetchone()
                if (
                    reservation is None
                    or reservation["owner"] != submission["owners"][identity]
                    or reservation["descriptor_json"] != self._key(requests[identity]).descriptor
                ):
                    raise ValueError("response does not belong to this exclusive reservation")
        self._journal(
            manifest["manifest_id"],
            "batch_responses_received",
            {"submission": submission, "responses": responses},
        )
        imported, reused = [], []
        for identity, raw in keyed.items():
            request, key = requests[identity], self._key(requests[identity])
            cached = self._cached(request)
            if cached is not None:
                if canonical_json(cached) != canonical_json(raw):
                    raise ValueError("conflicting output for an immutable completed request")
                reused.append(identity)
                continue
            complete_reserved_result(
                self.registry,
                key,
                submission["owners"][identity],
                raw,
                request,
                method="provider",
            )
            imported.append(identity)
        if (
            actual_cost_usd is not None
            and billing_evidence
            and billing_evidence.get("complete") is True
        ):
            self.budget.settle(submission["budget_key"], actual_cost_usd, billing_evidence)
        return {
            "imported": imported,
            "reused": reused,
            "missing_request_ids": sorted(set(requests) - keyed.keys()),
            "paid_calls": 0,
            "uploads": 0,
        }
