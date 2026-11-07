"""Local revision registry: musical entities and exact, transactional reuse keys.

This preparation store does not submit provider jobs or replace the historical DB.
Unknown outcomes remain reserved; time alone never authorizes a duplicate send.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

NORMALIZATION_VERSION = "lyrics-normalization-v2-draft1"
_HASH = re.compile(r"[0-9a-f]{64}")


def canonical_json(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    )


def execution_profile(
    *,
    model_id,
    resolved_model_version,
    prompt_template,
    output_schema,
    rubric_version,
    prompt_version,
    preprocessing_version,
    protocol_version,
    generation_configuration,
):
    """Build a complete reuse profile; never resolve a mutable model alias by guessing."""
    required = (
        model_id,
        resolved_model_version,
        prompt_template,
        rubric_version,
        prompt_version,
        preprocessing_version,
        protocol_version,
    )
    if any(not isinstance(value, str) or not value.strip() for value in required):
        raise ValueError("explicit resolved model and protocol inputs are required")
    if not output_schema or not generation_configuration:
        raise ValueError("schema and generation configuration are required")
    return dict(
        model_id=model_id,
        rubric_version=rubric_version,
        prompt_version=prompt_version,
        configuration=dict(
            resolved=True,
            resolved_model_version=resolved_model_version,
            prompt_sha256=hashlib.sha256(prompt_template.encode()).hexdigest(),
            output_schema_sha256=hashlib.sha256(canonical_json(output_schema).encode()).hexdigest(),
            preprocessing_version=preprocessing_version,
            protocol_version=protocol_version,
            generation=json.loads(canonical_json(generation_configuration)),
        ),
    )


@dataclass(frozen=True)
class NormalizedText:
    text: str
    original_hash: str
    normalized_hash: str
    version: str = NORMALIZATION_VERSION


def normalize_text(text: str) -> NormalizedText:
    normalized = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    normalized = "\n".join(
        re.sub(r"[ \t\u00a0]+", " ", line).strip(" \t\u00a0") for line in normalized.split("\n")
    )
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip("\n")
    return NormalizedText(
        normalized,
        hashlib.sha256(text.encode()).hexdigest(),
        hashlib.sha256(normalized.encode()).hexdigest(),
    )


def audit_text_chain(expected_normalized_hash, *, stored=None, presented=None, sent=None):
    stages = {"stored": stored, "presented": presented, "sent": sent}
    hashes = {
        name: normalize_text(value).normalized_hash
        for name, value in stages.items()
        if value is not None
    }
    missing = [name for name, value in stages.items() if value is None]
    mismatches = [name for name, digest in hashes.items() if digest != expected_normalized_hash]
    return {
        "verified": not missing and not mismatches,
        "missing_stages": missing,
        "mismatched_stages": mismatches,
        "normalized_hashes": hashes,
    }


@dataclass(frozen=True)
class ClassificationKey:
    text_identity_id: str
    normalized_hash: str
    normalization_version: str
    rubric_version: str
    prompt_version: str
    model_id: str
    configuration: dict
    descriptor: str = field(init=False)

    def __post_init__(self):
        fields = (
            "text_identity_id",
            "normalized_hash",
            "normalization_version",
            "rubric_version",
            "prompt_version",
            "model_id",
        )
        if any(
            not isinstance(getattr(self, k), str) or not getattr(self, k).strip() for k in fields
        ) or not _HASH.fullmatch(self.normalized_hash):
            raise ValueError("complete textual identity and protocol versions are required")
        if not self.configuration or self.configuration.get("resolved") is not True:
            raise ValueError("resolved model configuration is required")
        payload = {k: getattr(self, k) for k in fields}
        payload["configuration"] = self.configuration
        # Freeze a canonical copy so mutating the caller's dict cannot change a key.
        object.__setattr__(self, "descriptor", canonical_json(payload))

    @property
    def digest(self):
        return hashlib.sha256(self.descriptor.encode()).hexdigest()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS registry_meta(version INTEGER PRIMARY KEY CHECK(version=1));
INSERT OR IGNORE INTO registry_meta VALUES (1);
CREATE TABLE IF NOT EXISTS musical_works(
    id TEXT PRIMARY KEY, title TEXT NOT NULL, evidence_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recordings(
    id TEXT PRIMARY KEY, work_id TEXT REFERENCES musical_works(id),
    version_kind TEXT NOT NULL, evidence_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS textual_editions(
    id TEXT PRIMARY KEY, normalized_hash TEXT NOT NULL CHECK(length(normalized_hash)=64),
    normalization_version TEXT NOT NULL, original_hash TEXT,
    edition_kind TEXT NOT NULL, language TEXT,
    identity_confirmed INTEGER NOT NULL CHECK(identity_confirmed IN (0,1)),
    integrity_validated INTEGER NOT NULL CHECK(integrity_validated IN (0,1)),
    instrumental INTEGER NOT NULL CHECK(instrumental IN (0,1)), evidence_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS edition_recording_links(
    edition_id TEXT NOT NULL REFERENCES textual_editions(id),
    recording_id TEXT NOT NULL REFERENCES recordings(id),
    decision TEXT NOT NULL CHECK(decision IN ('pending','confirmed','rejected')),
    evidence_json TEXT NOT NULL, PRIMARY KEY(edition_id,recording_id));
CREATE TABLE IF NOT EXISTS platform_identity_claims(
    claim_id TEXT PRIMARY KEY, platform TEXT NOT NULL, native_id TEXT,
    recording_id TEXT REFERENCES recordings(id), isrc TEXT,
    decision TEXT NOT NULL CHECK(decision IN ('pending','confirmed','rejected')),
    metadata_json TEXT NOT NULL, evidence_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS classification_requests(
    request_key TEXT PRIMARY KEY CHECK(length(request_key)=64),
    edition_id TEXT NOT NULL REFERENCES textual_editions(id),
    descriptor_json TEXT NOT NULL, owner TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('reserved','submitted','uncertain','completed')),
    method TEXT, result_json TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""


class RevisionRegistry:
    """One local SQLite file, guarded by foreign keys and unique request signatures."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def register_edition(
        self,
        edition_id,
        normalized_hash,
        normalization_version,
        *,
        identity_confirmed,
        integrity_validated,
        evidence,
        original_hash=None,
        edition_kind="unknown",
        language=None,
        instrumental=False,
    ):
        if not _HASH.fullmatch(normalized_hash) or not normalization_version or not evidence:
            raise ValueError("edition hash, normalization and evidence are required")
        values = (
            edition_id,
            normalized_hash,
            normalization_version,
            original_hash,
            edition_kind,
            language,
            int(identity_confirmed),
            int(integrity_validated),
            int(instrumental),
            canonical_json(evidence),
        )
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO textual_editions VALUES (?,?,?,?,?,?,?,?,?,?)", values
            )
            existing = conn.execute(
                "SELECT * FROM textual_editions WHERE id=?", (edition_id,)
            ).fetchone()
            if tuple(existing) != values:
                raise ValueError("edition is immutable; record a new version and evidence")

    def record_platform_claim(
        self,
        claim_id,
        platform,
        native_id,
        *,
        metadata,
        evidence,
        recording_id=None,
        isrc=None,
        decision="pending",
    ):
        if not evidence or not claim_id or not platform:
            raise ValueError("claim provenance is required")
        if native_id and native_id.startswith(("web-derived:", "YOUTUBE_METADATA:")):
            raise ValueError("a locally derived identifier is not a native platform ID")
        if decision == "confirmed" and (not recording_id or not native_id):
            raise ValueError("confirmed platform links require native and recording IDs")
        values = (
            claim_id,
            platform,
            native_id,
            recording_id,
            isrc,
            decision,
            canonical_json(metadata),
            canonical_json(evidence),
        )
        with self.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO platform_identity_claims VALUES (?,?,?,?,?,?,?,?)", values
            )
            row = conn.execute(
                "SELECT * FROM platform_identity_claims WHERE claim_id=?", (claim_id,)
            ).fetchone()
            if tuple(row) != values:
                raise ValueError("claim is immutable; append a versioned claim")

    def record_pending_claims(self, claims):
        """Insert an acquisition inventory in one transaction, without inferred merges."""
        with self.connect() as conn:
            for row in claims:
                native = row.get("native_id")
                if native and native.startswith(("web-derived:", "YOUTUBE_METADATA:")):
                    raise ValueError("a derived ID is not a native ID")
                values = (
                    row["claim_id"],
                    row["platform"],
                    native,
                    None,
                    row.get("isrc"),
                    "pending",
                    canonical_json(row["metadata"]),
                    canonical_json(row["evidence"]),
                )
                conn.execute(
                    """INSERT OR IGNORE INTO platform_identity_claims VALUES (?,?,?,?,?,?,?,?)""",
                    values,
                )
                existing = conn.execute(
                    "SELECT * FROM platform_identity_claims WHERE claim_id=?", (row["claim_id"],)
                ).fetchone()
                if tuple(existing) != values:
                    raise ValueError("claim provenance changed; append a versioned claim")

    def reserve(self, key: ClassificationKey):
        """Return the sole owner token, or None if the key is already handled/in flight."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            edition = conn.execute(
                "SELECT * FROM textual_editions WHERE id=?", (key.text_identity_id,)
            ).fetchone()
            if (
                not edition
                or not edition["identity_confirmed"]
                or not edition["integrity_validated"]
                or edition["instrumental"]
                or edition["normalized_hash"] != key.normalized_hash
                or edition["normalization_version"] != key.normalization_version
            ):
                raise ValueError(
                    "only validated non-instrumental textual identities can be reserved"
                )
            owner = str(uuid4())
            inserted = conn.execute(
                """INSERT OR IGNORE INTO classification_requests
                (request_key,edition_id,descriptor_json,owner,state) VALUES (?,?,?,?,'reserved')""",
                (key.digest, key.text_identity_id, key.descriptor, owner),
            )
            return owner if inserted.rowcount == 1 else None

    def complete(self, key, owner, result, *, method):
        from chart_observatory.lyrics.review_protocol import validate_assessment

        if method not in {"provider", "human_adjudication"} or not result:
            raise ValueError("a result and explicit completion method are required")
        validate_assessment(result)
        with self.connect() as conn:
            changed = conn.execute(
                """UPDATE classification_requests SET state='completed',
                method=?,result_json=? WHERE request_key=? AND owner=?
                AND state IN ('reserved','submitted','uncertain')""",
                (method, canonical_json(result), key.digest, owner),
            )
            if changed.rowcount != 1:
                raise ValueError("reservation owner or state does not match")

    def mark_outcome_unknown(self, key, owner):
        with self.connect() as conn:
            changed = conn.execute(
                """UPDATE classification_requests SET state='uncertain'
                WHERE request_key=? AND owner=? AND state IN ('reserved','submitted')""",
                (key.digest, owner),
            )
            if changed.rowcount != 1:
                raise ValueError("reservation owner or state does not match")

    def result(self, key):
        with self.connect() as conn:
            row = conn.execute(
                """SELECT method,result_json FROM classification_requests
                WHERE request_key=? AND descriptor_json=? AND state='completed'""",
                (key.digest, key.descriptor),
            ).fetchone()
            return {"method": row[0], "result": json.loads(row[1])} if row else None


def prepare_text_requests(rows, profile, registry):
    """Deduplicate validated editions and reuse only a complete compatible signature.

    Preparing does not reserve or send requests. The eventual sender must obtain
    the sole owner token through reserve() immediately before submitting.
    """
    tasks, reused, pending = {}, [], []
    for row in rows:
        if (
            row.get("identity_confirmed") is not True
            or row.get("integrity_validated") is not True
            or row.get("instrumental")
            or row.get("text_language_role") != "original"
        ):
            continue
        normalized = normalize_text(row["text"])
        if (
            row.get("normalized_hash") != normalized.normalized_hash
            or row.get("normalization_version") != normalized.version
        ):
            raise ValueError("validated text and normalization signature disagree")
        key = ClassificationKey(
            text_identity_id=row["text_identity_id"],
            normalized_hash=normalized.normalized_hash,
            normalization_version=normalized.version,
            **{
                **profile,
                "configuration": {
                    **profile["configuration"],
                    "context_language": row.get("language"),
                },
            },
        )
        existing = registry.result(key)
        if existing is not None:
            if existing["result"]["classification_status"] == "classified":
                reused.append(key.digest)
            else:
                pending.append(key.digest)
            continue
        task = tasks.setdefault(
            key.digest,
            {
                "request_key": key.digest,
                "signature": json.loads(key.descriptor),
                "model_input": {"text": normalized.text, "language": row.get("language")},
                "status": "prepared_not_submitted",
                "memberships": [],
            },
        )
        task["memberships"].extend(row.get("memberships", []))
    return {
        "requests": list(tasks.values()),
        "reused_keys": sorted(set(reused)),
        "pending_human_review": sorted(set(pending)),
    }
