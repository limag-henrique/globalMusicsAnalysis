"""Finite Vertex AI Gemini batch adapter using ADC only."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from chart_observatory.db.models.lyrics_batch import LyricClassificationBatchRun
from chart_observatory.lyrics.batch_contract import BatchRunState


class StaticApiKeyConfigured(RuntimeError):
    """Raised when a static Gemini key could override the required ADC path."""


class AmbiguousBatchSubmission(RuntimeError):
    """Raised when a lost create response cannot be reconciled uniquely."""


class BatchSubmissionUnknown(RuntimeError):
    """Raised when submission outcome is unknown and must not be retried blindly."""


@dataclass(frozen=True, slots=True)
class VertexBatchJob:
    name: str
    display_name: str
    state: BatchRunState
    source_uri: str
    output_prefix: str
    successful_count: int | None
    failed_count: int | None
    provider_error: str | None


def assert_adc_only_environment() -> None:
    configured = [name for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY") if os.getenv(name)]
    if configured:
        raise StaticApiKeyConfigured(
            "static Gemini API keys are forbidden; remove " + ", ".join(configured)
        )


class VertexBatchAdapter:
    """Submit once, recover by opaque display name, and inspect without side effects."""

    def __init__(self, project_id: str, location: str, client: Any | None = None) -> None:
        assert_adc_only_environment()
        if not project_id.strip():
            raise ValueError("Google Cloud project is required")
        if location != "global":
            raise ValueError("Gemini lyric batches require the global endpoint")
        self._client = client or genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=types.HttpOptions(api_version="v1"),
        )

    def submit(self, run: LyricClassificationBatchRun) -> VertexBatchJob:
        if run.model_id != "gemini-3.8-flash" or run.location != "global":
            raise ValueError("batch run model/location contract is invalid")
        if run.provider_job_name:
            return self.get(run.provider_job_name)
        if not run.source_uri or not run.output_uri_prefix:
            raise ValueError("uploaded source and output prefix are required")
        if not run.source_uri.startswith("gs://") or not run.output_uri_prefix.startswith("gs://"):
            raise ValueError("batch source and destination must be private GCS URIs")
        display_name = f"lyrics-batch-{run.id}"
        try:
            existing = self.find_unique(display_name)
        except AmbiguousBatchSubmission:
            raise
        except Exception as exc:
            raise BatchSubmissionUnknown(
                f"pre-submit reconciliation failed ({type(exc).__name__}); not submitted"
            ) from exc
        if existing is not None:
            return existing
        try:
            raw = self._client.batches.create(
                model="gemini-3.8-flash",
                src=run.source_uri,
                config=types.CreateBatchJobConfig(
                    display_name=display_name,
                    dest=run.output_uri_prefix,
                ),
            )
        except Exception as exc:
            recovered = self.find_unique(display_name)
            if recovered is None:
                raise BatchSubmissionUnknown(
                    f"batch create outcome unknown ({type(exc).__name__}); not resubmitted"
                ) from exc
            return recovered
        return _normalize_job(raw)

    def get(self, job_name: str) -> VertexBatchJob:
        if not job_name.strip():
            raise ValueError("provider job name is required")
        return _normalize_job(self._client.batches.get(name=job_name))

    def find_unique(self, display_name: str) -> VertexBatchJob | None:
        jobs = list(
            self._client.batches.list(
                config=types.ListBatchJobsConfig(filter=f'display_name="{display_name}"')
            )
        )
        matches = [job for job in jobs if getattr(job, "display_name", None) == display_name]
        if len(matches) > 1:
            raise AmbiguousBatchSubmission(
                "multiple Vertex batch jobs share the opaque display name"
            )
        return _normalize_job(matches[0]) if matches else None


def _normalize_job(job: Any) -> VertexBatchJob:
    stats = getattr(job, "completion_stats", None)
    provider_error = getattr(job, "error", None)
    error_text = None
    if provider_error is not None:
        code = getattr(provider_error, "code", None)
        error_text = f"provider_error:{code}" if code is not None else "provider_error"
    return VertexBatchJob(
        name=str(getattr(job, "name", "")),
        display_name=str(getattr(job, "display_name", "")),
        state=_normalize_state(getattr(job, "state", None)),
        source_uri=_gcs_uri(getattr(job, "src", None)),
        output_prefix=_gcs_uri(getattr(job, "dest", None)),
        successful_count=_optional_nonnegative(stats, "successful_count"),
        failed_count=_optional_nonnegative(stats, "failed_count"),
        provider_error=error_text,
    )


def _gcs_uri(value: Any) -> str:
    if isinstance(value, str):
        return value
    uri = getattr(value, "gcs_uri", None)
    return str(uri or "")


def _optional_nonnegative(value: Any, field: str) -> int | None:
    number = getattr(value, field, None)
    return number if isinstance(number, int) and number >= 0 else None


def _normalize_state(state: Any) -> BatchRunState:
    raw = str(getattr(state, "value", state) or "").upper()
    mapping = {
        "JOB_STATE_QUEUED": BatchRunState.SUBMITTED,
        "JOB_STATE_PENDING": BatchRunState.SUBMITTED,
        "JOB_STATE_RUNNING": BatchRunState.RUNNING,
        "JOB_STATE_SUCCEEDED": BatchRunState.SUCCEEDED,
        "JOB_STATE_PARTIALLY_SUCCEEDED": BatchRunState.FAILED,
        "JOB_STATE_FAILED": BatchRunState.FAILED,
        "JOB_STATE_CANCELLED": BatchRunState.CANCELLED,
        "JOB_STATE_EXPIRED": BatchRunState.EXPIRED,
    }
    return mapping.get(raw, BatchRunState.SUBMITTED)
