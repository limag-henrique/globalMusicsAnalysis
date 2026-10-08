"""Private Cloud Storage boundary for ephemeral Gemini batch artifacts."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator, Set
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from google.cloud import storage  # type: ignore[import-untyped]


class BucketSecurityError(RuntimeError):
    """Raised when bucket controls or an exact-object operation fail closed."""


@dataclass(frozen=True, slots=True)
class StoredObject:
    uri: str
    name: str
    generation: int
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class BucketPreflight:
    bucket_name: str
    storage_class: str
    lifecycle_delete_age_days: int


class BatchStorageAdapter:
    """Validate a pre-provisioned bucket and perform generation-guarded I/O."""

    def __init__(self, client: Any, bucket_name: str) -> None:
        if not bucket_name.strip():
            raise ValueError("batch bucket name cannot be empty")
        self._client = client
        self._bucket_name = bucket_name
        self._bucket = client.bucket(bucket_name)

    @classmethod
    def from_adc(cls, project_id: str, bucket_name: str) -> BatchStorageAdapter:
        return cls(storage.Client(project=project_id), bucket_name)

    def preflight(self, expected_vertex_service_agent: str | None = None) -> BucketPreflight:
        self._bucket.reload()
        if str(self._bucket.storage_class).upper() != "STANDARD":
            raise BucketSecurityError("bucket storage class must be STANDARD")
        iam = self._bucket.iam_configuration
        if not bool(iam.uniform_bucket_level_access_enabled):
            raise BucketSecurityError("uniform bucket-level access must be enabled")
        if str(iam.public_access_prevention).casefold() != "enforced":
            raise BucketSecurityError("public access prevention must be enforced")
        if bool(self._bucket.versioning_enabled):
            raise BucketSecurityError("object versioning must be disabled")
        if self._bucket.retention_period:
            raise BucketSecurityError("retention policy must be absent")
        soft_delete = getattr(self._bucket, "soft_delete_policy", None)
        if isinstance(soft_delete, dict):
            retention_seconds = soft_delete.get(
                "retentionDurationSeconds",
                soft_delete.get("retention_duration_seconds"),
            )
        else:
            retention_seconds = (
                getattr(soft_delete, "retention_duration_seconds", None)
                if soft_delete is not None
                else 0
            )
        if isinstance(retention_seconds, str) and retention_seconds.isdecimal():
            retention_seconds = int(retention_seconds)
        if retention_seconds not in {None, 0}:
            raise BucketSecurityError("soft delete must be disabled")
        if not _has_seven_day_delete_rule(self._bucket.lifecycle_rules):
            raise BucketSecurityError("seven-day Delete lifecycle rule is required")
        if expected_vertex_service_agent:
            policy = self._bucket.get_iam_policy(requested_policy_version=3)
            member = f"serviceAccount:{expected_vertex_service_agent}"
            if not _policy_has_member_role(policy, member, "roles/storage.objectAdmin"):
                raise BucketSecurityError(
                    "Vertex service agent lacks bucket-scoped storage.objectAdmin"
                )
        return BucketPreflight(self._bucket_name, "STANDARD", 7)

    def upload(self, local_path: Path, object_name: str) -> StoredObject:
        _validate_object_name(object_name)
        raw_digest = hashlib.sha256()
        byte_count = 0
        with local_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                raw_digest.update(chunk)
                byte_count += len(chunk)
        sha256 = raw_digest.hexdigest()
        upload_attempt = str(uuid4())
        blob = self._bucket.blob(object_name)
        blob.metadata = {"sha256": sha256, "upload_attempt": upload_attempt}
        try:
            blob.upload_from_filename(str(local_path), if_generation_match=0)
            blob.reload()
            generation = int(blob.generation)
            if (
                int(blob.size) != byte_count
                or (blob.metadata or {}).get("sha256") != sha256
                or (blob.metadata or {}).get("upload_attempt") != upload_attempt
            ):
                raise BucketSecurityError("uploaded object failed size/hash verification")
        except Exception:
            try:
                blob.reload()
                metadata = blob.metadata or {}
                if metadata.get("upload_attempt") == upload_attempt:
                    blob.delete(if_generation_match=int(blob.generation))
            except Exception:
                # A failed or ambiguous cleanup is bounded by the bucket's lifecycle policy.
                pass
            raise
        local_path.unlink()
        return StoredObject(
            uri=f"gs://{self._bucket_name}/{object_name}",
            name=object_name,
            generation=generation,
            sha256=sha256,
            byte_count=byte_count,
        )

    def verify(self, stored: StoredObject) -> None:
        blob = self._bucket.blob(stored.name)
        blob.reload()
        if (
            int(blob.generation) != stored.generation
            or int(blob.size) != stored.byte_count
            or (blob.metadata or {}).get("sha256") != stored.sha256
        ):
            raise BucketSecurityError("source object generation/size/hash changed")

    def delete(self, stored: StoredObject) -> None:
        """Delete one exact object only while its uploaded generation still matches."""

        _validate_object_name(stored.name)
        blob = self._bucket.blob(stored.name)
        blob.reload()
        if int(blob.generation) != stored.generation:
            raise BucketSecurityError("object generation changed before cleanup")
        blob.delete(if_generation_match=stored.generation)

    def iter_lines(self, prefix: str) -> Iterator[bytes]:
        _validate_prefix(prefix)
        for blob in sorted(
            self._client.list_blobs(self._bucket, prefix=prefix), key=lambda item: item.name
        ):
            opener = getattr(blob, "open", None)
            if opener is None:
                data = blob.download_as_bytes()
                yield from data.splitlines(keepends=True)
                continue
            with opener("rb") as handle:
                yield from _binary_lines(handle)

    def cleanup_prefix(self, prefix: str, expected_objects: Set[str]) -> int:
        _validate_prefix(prefix)
        if not expected_objects or any(not name.startswith(prefix) for name in expected_objects):
            raise BucketSecurityError("expected object set is outside the recorded prefix")
        blobs = list(self._client.list_blobs(self._bucket, prefix=prefix))
        actual = {blob.name for blob in blobs}
        if actual != set(expected_objects):
            raise BucketSecurityError("bucket object set does not match the recorded object set")
        for blob in blobs:
            blob.delete(if_generation_match=int(blob.generation))
        return len(blobs)

    def object_names(self, prefix: str) -> set[str]:
        _validate_prefix(prefix)
        return {blob.name for blob in self._client.list_blobs(self._bucket, prefix=prefix)}


def _binary_lines(handle: BinaryIO) -> Iterator[bytes]:
    while line := handle.readline():
        yield line


def _validate_object_name(name: str) -> None:
    if not name or name.startswith("/") or ".." in name.split("/"):
        raise BucketSecurityError("unsafe Cloud Storage object name")


def _validate_prefix(prefix: str) -> None:
    _validate_object_name(prefix)
    if not prefix.endswith("/") or prefix.count("/") < 2:
        raise BucketSecurityError("cleanup requires an exact run prefix")


def _has_seven_day_delete_rule(rules: object) -> bool:
    if not isinstance(rules, Iterable):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        action = rule.get("action", {})
        condition = rule.get("condition", {})
        if (
            isinstance(action, dict)
            and isinstance(condition, dict)
            and str(action.get("type")).casefold() == "delete"
            and condition.get("age") == 7
        ):
            return True
    return False


def _policy_has_member_role(policy: object, member: str, role: str) -> bool:
    bindings = getattr(policy, "bindings", None)
    if isinstance(bindings, dict):
        members = bindings.get(role, ())
        return member in members
    if isinstance(bindings, Iterable):
        for binding in bindings:
            if not isinstance(binding, dict) or binding.get("role") != role:
                continue
            members = binding.get("members", ())
            if isinstance(members, Iterable) and member in members:
                return True
    return False
