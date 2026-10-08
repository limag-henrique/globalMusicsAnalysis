from types import SimpleNamespace
from uuid import uuid4

import pytest

from chart_observatory.lyrics.batch_contract import BatchRunState
from chart_observatory.lyrics.batch_vertex import (
    AmbiguousBatchSubmission,
    StaticApiKeyConfigured,
    VertexBatchAdapter,
    assert_adc_only_environment,
)


def provider_job(name: str = "projects/p/locations/global/batchPredictionJobs/1"):
    return SimpleNamespace(
        name=name,
        display_name="lyrics-batch-" + str(RUN_ID),
        state="JOB_STATE_QUEUED",
        src=SimpleNamespace(gcs_uri="gs://private/input.jsonl"),
        dest=SimpleNamespace(gcs_uri="gs://private/output/"),
        completion_stats=None,
        error=None,
    )


RUN_ID = uuid4()


class FakeBatches:
    def __init__(self) -> None:
        self.create_kwargs = None
        self.jobs = []
        self.raise_after_create = False
        self.create_calls = 0

    def create(self, **kwargs):
        self.create_calls += 1
        self.create_kwargs = kwargs
        job = provider_job()
        self.jobs.append(job)
        if self.raise_after_create:
            raise ConnectionError("response lost")
        return job

    def list(self, **_kwargs):
        return list(self.jobs)

    def get(self, *, name: str):
        return next(job for job in self.jobs if job.name == name)


def run_record():
    return SimpleNamespace(
        id=RUN_ID,
        model_id="gemini-3.8-flash",
        location="global",
        source_uri="gs://private/input.jsonl",
        output_uri_prefix="gs://private/output/",
        provider_job_name=None,
    )


def test_submit_uses_exact_model_private_uris_and_recovers_lost_response() -> None:
    batches = FakeBatches()
    batches.raise_after_create = True
    adapter = VertexBatchAdapter("project", "global", SimpleNamespace(batches=batches))

    job = adapter.submit(run_record())

    assert batches.create_kwargs["model"] == "gemini-3.8-flash"
    assert batches.create_kwargs["src"] == "gs://private/input.jsonl"
    assert batches.create_kwargs["config"].dest == "gs://private/output/"
    assert job.state is BatchRunState.SUBMITTED


def test_duplicate_display_names_are_fatal() -> None:
    batches = FakeBatches()
    batches.jobs = [provider_job("one"), provider_job("two")]

    with pytest.raises(AmbiguousBatchSubmission):
        VertexBatchAdapter("project", "global", SimpleNamespace(batches=batches)).find_unique(
            "lyrics-batch-" + str(RUN_ID)
        )


def test_existing_unique_job_is_reused_before_create() -> None:
    batches = FakeBatches()
    batches.jobs = [provider_job()]

    job = VertexBatchAdapter(
        "project", "global", SimpleNamespace(batches=batches)
    ).submit(run_record())

    assert job.display_name == "lyrics-batch-" + str(RUN_ID)
    assert batches.create_calls == 0


def test_static_api_keys_fail_adc_preflight(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "forbidden")

    with pytest.raises(StaticApiKeyConfigured):
        assert_adc_only_environment()
