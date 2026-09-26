"""Bounded coordination for immutable automatic lyric classification."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import suppress
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.lyrics.classification import (
    PROMPT_VERSION,
    TAXONOMY_VERSION,
    CostRateCard,
    LyricsClassification,
    UsageTelemetry,
)
from chart_observatory.lyrics.gemini_pipeline import (
    GeminiClassificationResponse,
    GeminiOutcomeStatus,
)
from chart_observatory.lyrics.repository import (
    AUTHORIZED_RIGHTS,
    ClassificationSnapshotInput,
    append_classification_snapshot,
    find_matching_snapshot,
)

MIN_CLASSIFIABLE_TEXT_CHARS = 20
HANDLED_CLASSIFICATION_STATUSES = (
    "classified",
    "ambiguous",
    "instrumental",
    "insufficient_text",
    "language_unsupported",
    "blocked",
    "error",
)


class LyricsClassifier(Protocol):
    def classify(
        self, lyrics: str, language: str | None = None
    ) -> GeminiClassificationResponse: ...

    def estimate_input_tokens(self, lyrics: str, language: str | None = None) -> int | None: ...


class ClassificationSettings(Protocol):
    gemini_model: str | None
    gemini_output_token_allowance: int
    gemini_input_usd_per_million_tokens: Decimal | None
    gemini_output_usd_per_million_tokens: Decimal | None
    gemini_thought_usd_per_million_tokens: Decimal | None


class CostLimitExceeded(ValueError):
    """Raised before generation when a requested cost ceiling cannot be honored."""


@dataclass(frozen=True, slots=True)
class ClassificationRequest:
    limit: int | None = None
    force: bool = False
    only_unclassified: bool = False
    estimate_cost: bool = False
    max_cost_usd: Decimal | None = None
    workers: int = 2

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit < 1:
            raise ValueError("classification limit must be at least one")
        if not 1 <= self.workers <= 8:
            raise ValueError("classification workers must be between one and eight")
        if self.max_cost_usd is not None and self.max_cost_usd < 0:
            raise ValueError("classification cost limit cannot be negative")


@dataclass(slots=True)
class ClassificationRunSummary:
    selected: int = 0
    skipped_idempotent: int = 0
    classified: int = 0
    status_outcomes: dict[str, int] = field(default_factory=dict)
    known_input_tokens: int = 0
    known_output_tokens: int = 0
    known_thought_tokens: int = 0
    known_total_tokens: int = 0
    known_cost_usd: Decimal | None = None
    errors: int = 0
    skipped_due_to_error: int = 0
    item_outcomes: list[dict[str, str | None]] = field(default_factory=list)
    estimated_candidates: int = 0
    estimated_input_tokens: int | None = None
    output_token_allowance: int = 0
    estimated_cost_usd: Decimal | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "selected": self.selected,
            "skipped_idempotent": self.skipped_idempotent,
            "classified": self.classified,
            "status_outcomes": dict(sorted(self.status_outcomes.items())),
            "known_input_tokens": self.known_input_tokens,
            "known_output_tokens": self.known_output_tokens,
            "known_thought_tokens": self.known_thought_tokens,
            "known_total_tokens": self.known_total_tokens,
            "known_cost_usd": (
                str(self.known_cost_usd) if self.known_cost_usd is not None else None
            ),
            "errors": self.errors,
            "skipped_due_to_error": self.skipped_due_to_error,
            "item_outcomes": list(self.item_outcomes),
            "estimated_candidates": self.estimated_candidates,
            "estimated_input_tokens": self.estimated_input_tokens,
            "output_token_allowance": self.output_token_allowance,
            "estimated_cost_usd": (
                str(self.estimated_cost_usd) if self.estimated_cost_usd is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class _Candidate:
    lyric_document_id: UUID
    canonical_track_id: UUID
    lyrics_hash: str
    text: str | None
    language: str | None
    instrumental: bool


class LyricsClassificationService:
    """Select, preflight, classify, and durably append one outcome per signature."""

    def __init__(
        self,
        session: Session,
        classifier: LyricsClassifier,
        settings: ClassificationSettings,
    ) -> None:
        if not settings.gemini_model:
            raise ValueError("GEMINI_MODEL is required for lyric classification")
        self._session = session
        self._classifier = classifier
        self._settings = settings
        self._model_id = settings.gemini_model
        self._rate_card = CostRateCard(
            input_usd_per_million_tokens=settings.gemini_input_usd_per_million_tokens,
            output_usd_per_million_tokens=settings.gemini_output_usd_per_million_tokens,
            thought_usd_per_million_tokens=settings.gemini_thought_usd_per_million_tokens,
        )

    def run(self, request: ClassificationRequest) -> ClassificationRunSummary:
        candidates = self._select_candidates(request)
        summary = ClassificationRunSummary(selected=len(candidates))

        if request.estimate_cost or request.max_cost_usd is not None:
            self._estimate(candidates, request, summary)
            if request.max_cost_usd is not None:
                if summary.estimated_cost_usd is None:
                    raise CostLimitExceeded(
                        "classification cost estimate is unavailable; generation was not started"
                    )
                if summary.estimated_cost_usd > request.max_cost_usd:
                    raise CostLimitExceeded(
                        "classification cost estimate exceeds --max-cost-usd; "
                        "generation was not started"
                    )
            if request.estimate_cost:
                return summary

        self._classify(candidates, request, summary)
        return summary

    def count_initial_pass_remaining(self) -> int:
        """Count authorized tracks with no durable outcome in the unattended queue."""
        handled_snapshot = exists(
            select(LyricClassificationSnapshot.id).where(
                LyricClassificationSnapshot.canonical_track_id
                == LyricDocument.canonical_track_id,
                LyricClassificationSnapshot.classification_status.in_(
                    HANDLED_CLASSIFICATION_STATUSES
                ),
            )
        )
        count = self._session.scalar(
            select(func.count(func.distinct(LyricDocument.canonical_track_id))).where(
                LyricDocument.rights_status.in_(sorted(AUTHORIZED_RIGHTS)),
                ~handled_snapshot,
            )
        )
        return int(count or 0)

    def _select_candidates(self, request: ClassificationRequest) -> list[_Candidate]:
        statement = select(LyricDocument).where(
            LyricDocument.rights_status.in_(sorted(AUTHORIZED_RIGHTS))
        )
        if request.only_unclassified:
            successful_snapshot = exists(
                select(LyricClassificationSnapshot.id).where(
                    LyricClassificationSnapshot.canonical_track_id
                    == LyricDocument.canonical_track_id,
                    LyricClassificationSnapshot.classification_status.in_(
                        HANDLED_CLASSIFICATION_STATUSES
                    ),
                )
            )
            statement = statement.where(~successful_snapshot)
        statement = statement.order_by(LyricDocument.created_at, LyricDocument.id)

        selected: list[_Candidate] = []
        seen_signatures: set[tuple[UUID, str, str, str, str]] = set()
        for document in self._session.scalars(statement).yield_per(100):
            signature = (
                document.canonical_track_id,
                document.content_sha256,
                self._model_id,
                TAXONOMY_VERSION,
                PROMPT_VERSION,
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            metadata = document.metadata_json or {}
            selected.append(
                _Candidate(
                    lyric_document_id=document.id,
                    canonical_track_id=document.canonical_track_id,
                    lyrics_hash=document.content_sha256,
                    text=document.text,
                    language=document.language_code,
                    instrumental=metadata.get("instrumental") is True,
                )
            )
            if request.limit is not None and len(selected) >= request.limit:
                break
        return selected

    def _estimate(
        self,
        candidates: list[_Candidate],
        request: ClassificationRequest,
        summary: ClassificationRunSummary,
    ) -> None:
        provider_candidates: list[_Candidate] = []
        for candidate in candidates:
            match = self._find_match(candidate)
            if not request.force and match is not None and self._is_handled_match(match):
                if request.estimate_cost:
                    summary.skipped_idempotent += 1
                continue
            if self._local_status(candidate) is None:
                provider_candidates.append(candidate)

        summary.estimated_candidates = len(provider_candidates)
        summary.output_token_allowance = (
            len(provider_candidates) * self._settings.gemini_output_token_allowance
        )
        if not provider_candidates:
            summary.estimated_input_tokens = 0
            summary.estimated_cost_usd = Decimal(0)
            return

        token_counts = list(
            _bounded_map(
                provider_candidates,
                request.workers,
                lambda candidate: self._classifier.estimate_input_tokens(
                    candidate.text or "", candidate.language
                ),
            )
        )
        if any(value is None for value in token_counts):
            return
        summary.estimated_input_tokens = sum(value for value in token_counts if value is not None)
        input_rate = self._rate_card.input_usd_per_million_tokens
        output_rate = self._rate_card.output_usd_per_million_tokens
        thought_rate = self._rate_card.thought_usd_per_million_tokens
        if input_rate is None or output_rate is None or thought_rate is None:
            return
        # The configured generation ceiling covers output and thought tokens together. Using
        # the dearer rate for the full allowance is a reliable upper bound without guessing
        # the provider's eventual split between those two billed classes.
        output_upper_rate = max(output_rate, thought_rate)
        summary.estimated_cost_usd = (
            Decimal(summary.estimated_input_tokens) * input_rate
            + Decimal(summary.output_token_allowance) * output_upper_rate
        ) / Decimal(1_000_000)

    def _classify(
        self,
        candidates: list[_Candidate],
        request: ClassificationRequest,
        summary: ClassificationRunSummary,
    ) -> None:
        pending: dict[Future[GeminiClassificationResponse], tuple[_Candidate, UUID | None]] = {}
        with ThreadPoolExecutor(max_workers=request.workers) as executor:
            for candidate in candidates:
                while len(pending) >= request.workers:
                    self._complete_one(pending, summary)
                match = self._find_match(candidate)
                if match is not None and not request.force and self._is_handled_match(match):
                    summary.skipped_idempotent += 1
                    continue
                forced_from_id = match.id if match is not None and request.force else None
                local_status = self._local_status(candidate)
                if local_status is not None:
                    self._persist(
                        candidate,
                        local_status,
                        None,
                        forced_from_id,
                        summary,
                    )
                    continue
                future = executor.submit(
                    self._classifier.classify,
                    candidate.text or "",
                    candidate.language,
                )
                pending[future] = (candidate, forced_from_id)

            while pending:
                self._complete_one(pending, summary)

    def _complete_one(
        self,
        pending: dict[Future[GeminiClassificationResponse], tuple[_Candidate, UUID | None]],
        summary: ClassificationRunSummary,
    ) -> None:
        completed, _ = wait(pending, return_when=FIRST_COMPLETED)
        for future in completed:
            candidate, forced_from_id = pending.pop(future)
            try:
                response = future.result()
            except MemoryError:
                raise
            except Exception as exc:  # adapter bugs remain durable without leaking request text
                response = GeminiClassificationResponse(
                    outcome=GeminiOutcomeStatus.PROVIDER_ERROR,
                    error=f"classifier raised {type(exc).__name__}",
                )
            self._persist_response(candidate, response, forced_from_id, summary)

    def _persist_response(
        self,
        candidate: _Candidate,
        response: GeminiClassificationResponse,
        forced_from_id: UUID | None,
        summary: ClassificationRunSummary,
    ) -> None:
        if response.outcome is GeminiOutcomeStatus.SUCCESS and response.result is not None:
            status = response.result.classification_status.value
            result = response.result if status in {"classified", "ambiguous"} else None
            error = None
        elif response.outcome is GeminiOutcomeStatus.BLOCKED:
            status = "blocked"
            result = None
            error = response.error
        else:
            status = "error"
            result = None
            error = response.error or f"Gemini outcome: {response.outcome.value}"
        self._persist(
            candidate,
            status,
            response.usage,
            forced_from_id,
            summary,
            result=result,
            error=error,
            provider_outcome=response.outcome.value,
        )

    def _persist(
        self,
        candidate: _Candidate,
        status: str,
        usage: UsageTelemetry | None,
        forced_from_id: UUID | None,
        summary: ClassificationRunSummary,
        *,
        result: object | None = None,
        error: str | None = None,
        provider_outcome: str | None = None,
    ) -> None:
        validated_result = result if isinstance(result, LyricsClassification) else None
        row = append_classification_snapshot(
            self._session,
            ClassificationSnapshotInput(
                lyric_document_id=candidate.lyric_document_id,
                canonical_track_id=candidate.canonical_track_id,
                lyrics_hash=candidate.lyrics_hash,
                model_id=self._model_id,
                taxonomy_version=TAXONOMY_VERSION,
                prompt_version=PROMPT_VERSION,
                classification_status=status,
                result=validated_result,
                error=error,
                usage=usage,
                rate_card=self._rate_card,
                forced_from_snapshot_id=forced_from_id,
            ),
        )
        self._session.commit()
        summary.status_outcomes[status] = summary.status_outcomes.get(status, 0) + 1
        if status in {"classified", "ambiguous"}:
            summary.classified += 1
        if status == "error":
            summary.errors += 1
            summary.skipped_due_to_error += 1
        summary.item_outcomes.append(
            {
                "lyric_document_id": str(candidate.lyric_document_id),
                "canonical_track_id": str(candidate.canonical_track_id),
                "status": status,
                "error": error,
                "provider_outcome": provider_outcome,
            }
        )
        self._add_usage(summary, usage)
        if row.estimated_cost_usd is not None:
            summary.known_cost_usd = (summary.known_cost_usd or Decimal(0)) + Decimal(
                row.estimated_cost_usd
            )

    def _find_match(self, candidate: _Candidate) -> LyricClassificationSnapshot | None:
        return find_matching_snapshot(
            self._session,
            ClassificationSnapshotInput(
                lyric_document_id=candidate.lyric_document_id,
                canonical_track_id=candidate.canonical_track_id,
                lyrics_hash=candidate.lyrics_hash,
                model_id=self._model_id,
                taxonomy_version=TAXONOMY_VERSION,
                prompt_version=PROMPT_VERSION,
                classification_status="pending",
            ),
        )

    @staticmethod
    def _is_handled_match(snapshot: LyricClassificationSnapshot) -> bool:
        status = getattr(snapshot, "classification_status", None)
        return status is None or status in HANDLED_CLASSIFICATION_STATUSES

    @staticmethod
    def _local_status(candidate: _Candidate) -> str | None:
        if candidate.instrumental:
            return "instrumental"
        normalized = " ".join((candidate.text or "").split())
        if len(normalized) < MIN_CLASSIFIABLE_TEXT_CHARS:
            return "insufficient_text"
        return None

    @staticmethod
    def _add_usage(
        summary: ClassificationRunSummary, usage: UsageTelemetry | None
    ) -> None:
        if usage is None:
            return
        if usage.input_tokens is not None:
            summary.known_input_tokens += usage.input_tokens
        if usage.output_tokens is not None:
            summary.known_output_tokens += usage.output_tokens
        if usage.thought_tokens is not None:
            summary.known_thought_tokens += usage.thought_tokens
        if usage.total_tokens is not None:
            summary.known_total_tokens += usage.total_tokens


def _bounded_map[T](
    items: list[T], workers: int, operation: Callable[[T], int | None]
) -> Iterator[int | None]:
    """Yield operation results while keeping no more than workers futures in flight."""
    iterator = iter(items)
    pending: set[Future[int | None]] = set()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for _ in range(workers):
            try:
                pending.add(executor.submit(operation, next(iterator)))
            except StopIteration:
                break
        while pending:
            completed, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                yield future.result()
                with suppress(StopIteration):
                    pending.add(executor.submit(operation, next(iterator)))
