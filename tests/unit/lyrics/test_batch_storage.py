from pathlib import Path
from types import SimpleNamespace

import pytest

from chart_observatory.lyrics.batch_storage import (
    BatchStorageAdapter,
    BucketSecurityError,
)


class FakeBlob:
    def __init__(self, name: str) -> None:
        self.name = name
        self.metadata = None
        self.generation = 7
        self.size = 0
        self.upload_precondition = None
        self.deleted = False
        self.raise_after_upload = False

    def upload_from_filename(self, path: str, *, if_generation_match: int) -> None:
        self.upload_precondition = if_generation_match
        self.size = Path(path).stat().st_size
        if self.raise_after_upload:
            raise TimeoutError("simulated lost upload response")

    def reload(self) -> None:
        return None

    def delete(self, *, if_generation_match: int) -> None:
        assert if_generation_match == self.generation
        self.deleted = True


class FakeBucket:
    storage_class = "STANDARD"
    versioning_enabled = False
    retention_period = None
    soft_delete_policy = SimpleNamespace(retention_duration_seconds=0)
    iam_configuration = SimpleNamespace(
        uniform_bucket_level_access_enabled=True,
        public_access_prevention="enforced",
    )
    lifecycle_rules = [{"action": {"type": "Delete"}, "condition": {"age": 7}}]

    def __init__(self) -> None:
        self.blobs = {}

    def reload(self) -> None:
        return None

    def blob(self, name: str) -> FakeBlob:
        return self.blobs.setdefault(name, FakeBlob(name))


class FakeClient:
    def __init__(self, bucket: FakeBucket) -> None:
        self.bucket_value = bucket

    def bucket(self, name: str) -> FakeBucket:
        assert name == "private-bucket"
        return self.bucket_value

    def list_blobs(self, bucket: FakeBucket, *, prefix: str):
        return [blob for name, blob in bucket.blobs.items() if name.startswith(prefix)]


def test_preflight_accepts_bucket_without_retention_period() -> None:
    result = BatchStorageAdapter(FakeClient(FakeBucket()), "private-bucket").preflight()

    assert result.lifecycle_delete_age_days == 7


def test_preflight_accepts_zero_soft_delete_duration_from_storage_client() -> None:
    bucket = FakeBucket()
    bucket.soft_delete_policy = {"retentionDurationSeconds": "0"}

    result = BatchStorageAdapter(FakeClient(bucket), "private-bucket").preflight()

    assert result.bucket_name == "private-bucket"


def test_preflight_rejects_bucket_without_public_access_prevention() -> None:
    bucket = FakeBucket()
    bucket.iam_configuration = SimpleNamespace(
        uniform_bucket_level_access_enabled=True,
        public_access_prevention="inherited",
    )

    with pytest.raises(BucketSecurityError, match="public access prevention"):
        BatchStorageAdapter(FakeClient(bucket), "private-bucket").preflight()


def test_preflight_rejects_dict_shaped_soft_delete_policy() -> None:
    bucket = FakeBucket()
    bucket.soft_delete_policy = {"retentionDurationSeconds": 604800}

    with pytest.raises(BucketSecurityError, match="soft delete"):
        BatchStorageAdapter(FakeClient(bucket), "private-bucket").preflight()


def test_preflight_rejects_missing_vertex_service_agent_binding() -> None:
    bucket = FakeBucket()
    bucket.get_iam_policy = lambda **_kwargs: SimpleNamespace(bindings=[])

    with pytest.raises(BucketSecurityError, match="Vertex service agent"):
        BatchStorageAdapter(FakeClient(bucket), "private-bucket").preflight(
            "service-123@gcp-sa-aiplatform.iam.gserviceaccount.com"
        )


def test_upload_uses_create_only_and_deletes_local_after_verification(tmp_path) -> None:
    bucket = FakeBucket()
    source = tmp_path / "private.jsonl"
    source.write_bytes(b'{"key":"opaque"}\n')

    stored = BatchStorageAdapter(FakeClient(bucket), "private-bucket").upload(
        source, "runs/opaque/input.jsonl"
    )

    blob = bucket.blobs["runs/opaque/input.jsonl"]
    assert blob.upload_precondition == 0
    assert blob.metadata["sha256"] == stored.sha256
    assert blob.metadata["upload_attempt"]
    assert stored.uri == "gs://private-bucket/runs/opaque/input.jsonl"
    assert not source.exists()


def test_delete_uses_recorded_generation(tmp_path) -> None:
    bucket = FakeBucket()
    source = tmp_path / "private.jsonl"
    source.write_bytes(b"{}\n")
    adapter = BatchStorageAdapter(FakeClient(bucket), "private-bucket")
    stored = adapter.upload(source, "runs/run-1/input.jsonl")

    adapter.delete(stored)

    assert bucket.blob(stored.name).deleted is True


def test_upload_cleans_its_exact_object_after_lost_response(tmp_path) -> None:
    bucket = FakeBucket()
    source = tmp_path / "private.jsonl"
    source.write_bytes(b"{}\n")
    blob = bucket.blob("runs/run-timeout/input.jsonl")
    blob.raise_after_upload = True

    with pytest.raises(TimeoutError, match="lost upload response"):
        BatchStorageAdapter(FakeClient(bucket), "private-bucket").upload(
            source, "runs/run-timeout/input.jsonl"
        )

    assert blob.deleted is True


def test_cleanup_requires_exact_recorded_object_set() -> None:
    bucket = FakeBucket()
    bucket.blob("runs/run-1/input.jsonl")
    bucket.blob("runs/run-1/output/result.jsonl")
    adapter = BatchStorageAdapter(FakeClient(bucket), "private-bucket")

    with pytest.raises(BucketSecurityError, match="object set"):
        adapter.cleanup_prefix("runs/run-1/", {"runs/run-1/input.jsonl"})
