from __future__ import annotations

import threading
import time
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import chart_observatory.lyrics.classification_service as classification_service
from chart_observatory.db.base import Base
from chart_observatory.db.models.corpus import LyricClassificationSnapshot, LyricDocument
from chart_observatory.lyrics.classification import LyricsClassification, UsageTelemetry
from chart_observatory.lyrics.classification_service import (
    ClassificationRequest,
    CostLimitExceeded,
    LyricsClassificationService,
)
from chart_observatory.lyrics.gemini_pipeline import (
    GeminiClassificationResponse,
    GeminiOutcomeStatus,
)
from chart_observatory.lyrics.repository import LyricDocumentInput, ingest_lyric_document


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as database_session:
        yield database_session


def _settings(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "gemini_model": "gemini-fixed-model",
        "gemini_output_token_allowance": 100,
        "gemini_input_usd_per_million_tokens": Decimal("1"),
        "gemini_output_usd_per_million_tokens": Decimal("2"),
        "gemini_thought_usd_per_million_tokens": Decimal("3"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _classification() -> LyricsClassification:
    return LyricsClassification.model_validate(
        {
            "classification_status": "classified",
            "confidence": 0.8,
            "sexuality": {
                "sexual_explicitness": 0,
                "sexual_desire": 0,
                "sexual_innuendo": 0,
                "explicit_sexual_act": 0,
                "explicit_sexual_anatomy": 0,
            },
            "relationships": {
                "romantic_affection": 1,
                "heartbreak": 0,
                "infidelity": 0,
                "transactional_sex": 0,
                "casual_sex": 0,
                "jealousy_possession": 0,
                "reciprocity": 1,
                "consent": "explicit_mutual",
            },
            "gender_representation": {
                "objectification": 0,
                "misogyny": 0,
                "sexual_agency": 1,
                "status_symbolization": 0,
                "commodification": 0,
                "target_gender": "unspecified",
                "representation_roles": ["narrator"],
            },
            "material_status": {
                "money_reference": 0,
                "materialism": 0,
                "conspicuous_consumption": 0,
                "wealth_as_status": 0,
            },
            "antisocial": {
                name: {"intensity": 0, "stance": "neutral"}
                for name in ("drugs_alcohol", "crime", "violence", "weapons")
            },
            "territorial_identity": 0,
            "romantic_summary": "Reciprocal affection.",
        }
    )


class FakeClassifier:
    def __init__(self, *, input_tokens: int | None = 10, delay: float = 0.0) -> None:
        self.input_tokens = input_tokens
        self.delay = delay
        self.classified_texts: list[str] = []
        self.estimated_texts: list[str] = []
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def classify(self, lyrics: str, language: str | None = None) -> GeminiClassificationResponse:
        with self._lock:
            self.classified_texts.append(lyrics)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                time.sleep(self.delay)
            return GeminiClassificationResponse(
                outcome=GeminiOutcomeStatus.SUCCESS,
                result=_classification(),
                usage=UsageTelemetry(
                    input_tokens=10,
                    output_tokens=20,
                    thought_tokens=5,
                    total_tokens=35,
                ),
            )
        finally:
            with self._lock:
                self.active -= 1

    def estimate_input_tokens(self, lyrics: str, language: str | None = None) -> int | None:
        with self._lock:
            self.estimated_texts.append(lyrics)
        return self.input_tokens


def _document(
    session: Session,
    text: str | None,
    *,
    track_id: UUID | None = None,
    source: str | None = None,
    rights_status: str = "RESEARCH_AUTHORIZED",
    metadata: dict[str, object] | None = None,
) -> LyricDocument:
    return ingest_lyric_document(
        session,
        LyricDocumentInput(
            canonical_track_id=track_id or uuid4(),
            source=source or f"SOURCE-{uuid4()}",
            source_version="v1",
            rights_status=rights_status,
            language_code="pt-BR",
            text=text,
            metadata=metadata or {},
        ),
    )


def test_same_signature_does_not_call_classifier_twice(session: Session) -> None:
    """Catches a rerun that spends a second provider call for existing evidence."""
    _document(session, "uma letra longa o bastante para classificação")
    classifier = FakeClassifier()
    service = LyricsClassificationService(session, classifier, _settings())

    first = service.run(ClassificationRequest())
    second = service.run(ClassificationRequest())

    assert first.classified == 1
    assert second.skipped_idempotent == 1
    assert len(classifier.classified_texts) == 1
    assert len(session.scalars(select(LyricClassificationSnapshot)).all()) == 1


def test_force_appends_linked_history_and_calls_classifier_again(session: Session) -> None:
    """Catches force rewriting or silently reusing the previous immutable result."""
    _document(session, "outra letra longa o bastante para classificação")
    classifier = FakeClassifier()
    service = LyricsClassificationService(session, classifier, _settings())

    service.run(ClassificationRequest())
    service.run(ClassificationRequest(force=True))

    rows = session.scalars(
        select(LyricClassificationSnapshot).order_by(LyricClassificationSnapshot.append_order)
    ).all()
    assert len(classifier.classified_texts) == 2
    assert len(rows) == 2
    assert rows[1].forced_from_snapshot_id == rows[0].id


def test_local_preflight_persists_non_scored_outcomes_without_provider_calls(
    session: Session,
) -> None:
    """Catches missing/short or trusted instrumental lyrics being sent to Gemini."""
    _document(session, "  ")
    _document(session, "instrumental metadata wins", metadata={"instrumental": True})
    classifier = FakeClassifier()

    summary = LyricsClassificationService(session, classifier, _settings()).run(
        ClassificationRequest()
    )

    rows = session.scalars(select(LyricClassificationSnapshot)).all()
    assert classifier.classified_texts == []
    assert summary.status_outcomes == {"insufficient_text": 1, "instrumental": 1}
    assert {row.classification_status for row in rows} == {
        "insufficient_text",
        "instrumental",
    }
    assert all(row.result_json is None for row in rows)


def test_selection_is_authorized_deduplicated_and_limited(session: Session) -> None:
    """Catches duplicate signatures, unauthorized rows, or limit bypass reaching Gemini."""
    duplicate_track = uuid4()
    duplicate_text = "letra repetida mas longa o bastante para classificação"
    _document(session, duplicate_text, track_id=duplicate_track, source="A")
    _document(session, duplicate_text, track_id=duplicate_track, source="B")
    _document(session, "texto sem autorização que nunca pode sair", rights_status="LICENSED")
    unauthorized = session.scalars(select(LyricDocument)).all()[-1]
    unauthorized.rights_status = "FORBIDDEN"
    session.flush()
    _document(session, "segunda letra elegível e longa para classificar")
    _document(session, "terceira letra elegível que deve ficar fora pelo limite")
    classifier = FakeClassifier()

    summary = LyricsClassificationService(session, classifier, _settings()).run(
        ClassificationRequest(limit=2, workers=2)
    )

    assert summary.selected == 2
    assert len(classifier.classified_texts) == 2
    assert len(set(classifier.classified_texts)) == 2
    assert "texto sem autorização que nunca pode sair" not in classifier.classified_texts


def test_only_unclassified_excludes_tracks_with_success_even_when_forced(
    session: Session,
) -> None:
    """Catches only-unclassified degenerating into same-signature filtering."""
    _document(session, "primeiro texto longo que já será classificado")
    classifier = FakeClassifier()
    service = LyricsClassificationService(session, classifier, _settings())
    service.run(ClassificationRequest())
    _document(session, "segundo texto longo ainda não classificado")

    summary = service.run(ClassificationRequest(force=True, only_unclassified=True))

    assert summary.selected == 1
    assert classifier.classified_texts.count(
        "primeiro texto longo que já será classificado"
    ) == 1
    assert classifier.classified_texts.count(
        "segundo texto longo ainda não classificado"
    ) == 1


def test_workers_bound_concurrency_and_each_eligible_lyric_is_called_once(
    session: Session,
) -> None:
    """Catches unbounded submission or duplicate provider work inside a batch."""
    for index in range(6):
        _document(session, f"letra número {index} longa o bastante para classificação")
    classifier = FakeClassifier(delay=0.02)

    summary = LyricsClassificationService(session, classifier, _settings()).run(
        ClassificationRequest(workers=2)
    )

    assert summary.classified == 6
    assert classifier.max_active == 2
    assert len(classifier.classified_texts) == len(set(classifier.classified_texts)) == 6


def test_signature_is_rechecked_after_waiting_for_an_inflight_slot(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches stale idempotency checks performed before a worker-slot wait."""
    _document(session, "primeira letra longa ocupa o único worker disponível")
    _document(session, "segunda letra longa ganha snapshot enquanto aguarda")

    class CompletingClassifier(FakeClassifier):
        completed = False

        def classify(
            self, lyrics: str, language: str | None = None
        ) -> GeminiClassificationResponse:
            time.sleep(0.03)
            response = super().classify(lyrics, language)
            self.completed = True
            return response

    classifier = CompletingClassifier()
    existing = SimpleNamespace(id=uuid4())
    lookups = 0

    def matching_after_first_completion(_session, _snapshot):
        nonlocal lookups
        lookups += 1
        return existing if classifier.completed else None

    monkeypatch.setattr(
        classification_service, "find_matching_snapshot", matching_after_first_completion
    )

    summary = LyricsClassificationService(session, classifier, _settings()).run(
        ClassificationRequest(workers=1)
    )

    assert lookups == 2
    assert len(classifier.classified_texts) == 1
    assert summary.skipped_idempotent == 1


def test_estimate_cost_counts_tokens_only_and_returns_conservative_upper_bound(
    session: Session,
) -> None:
    """Catches estimation that generates content or understates the configured allowance."""
    _document(session, "primeira letra longa para estimar tokens sem gerar conteúdo")
    _document(session, "segunda letra longa para estimar tokens sem gerar conteúdo")
    classifier = FakeClassifier(input_tokens=10)

    summary = LyricsClassificationService(session, classifier, _settings()).run(
        ClassificationRequest(estimate_cost=True, workers=2)
    )

    assert summary.selected == 2
    assert summary.estimated_candidates == 2
    assert summary.estimated_input_tokens == 20
    assert summary.output_token_allowance == 200
    assert summary.estimated_cost_usd == Decimal("0.000620")
    assert len(classifier.estimated_texts) == 2
    assert classifier.classified_texts == []
    assert session.scalars(select(LyricClassificationSnapshot)).all() == []


def test_max_cost_preflight_counts_an_idempotent_skip_once(session: Session) -> None:
    """Catches cost preflight and execution both adding the same skipped signature."""
    _document(session, "letra longa com snapshot já existente antes do cost guard")
    classifier = FakeClassifier()
    service = LyricsClassificationService(session, classifier, _settings())
    service.run(ClassificationRequest())

    summary = service.run(ClassificationRequest(max_cost_usd=Decimal("1")))

    assert summary.selected == 1
    assert summary.skipped_idempotent == 1
    assert len(classifier.classified_texts) == 1


@pytest.mark.parametrize(
    ("input_tokens", "max_cost"),
    [(None, Decimal("1")), (10, Decimal("0.0001"))],
)
def test_max_cost_rejects_unknown_or_excessive_estimate_before_generation(
    session: Session, input_tokens: int | None, max_cost: Decimal
) -> None:
    """Catches an unknown or over-budget batch being allowed to generate content."""
    _document(session, "letra longa cujo custo precisa ser limitado antes da chamada")
    classifier = FakeClassifier(input_tokens=input_tokens)

    with pytest.raises(CostLimitExceeded):
        LyricsClassificationService(session, classifier, _settings()).run(
            ClassificationRequest(max_cost_usd=max_cost)
        )

    assert classifier.classified_texts == []
    assert session.scalars(select(LyricClassificationSnapshot)).all() == []


def test_provider_failure_persists_safe_error_and_partial_telemetry(session: Session) -> None:
    """Catches recoverable failures leaking lyrics or losing known input token usage."""
    secret = "letra confidencial longa que não deve aparecer em saída ou erro"
    _document(session, secret)

    class FailingClassifier(FakeClassifier):
        def classify(
            self, lyrics: str, language: str | None = None
        ) -> GeminiClassificationResponse:
            self.classified_texts.append(lyrics)
            return GeminiClassificationResponse(
                outcome=GeminiOutcomeStatus.TRANSIENT_ERROR,
                usage=UsageTelemetry(input_tokens=19),
                error="provider unavailable",
            )

    summary = LyricsClassificationService(
        session, FailingClassifier(), _settings()
    ).run(ClassificationRequest())

    row = session.scalar(select(LyricClassificationSnapshot))
    assert row is not None
    assert row.classification_status == "error"
    assert row.result_json is None
    assert row.input_tokens == 19
    assert row.output_tokens is None
    assert row.estimated_cost_usd is None
    assert secret not in str(summary.to_json())
    assert secret not in (row.error or "")


def test_non_scored_provider_status_discards_taxonomy_payload(session: Session) -> None:
    """Catches unsupported-language outcomes being persisted as invented score evidence."""
    _document(session, "texto longo em idioma não suportado pelo classificador")
    payload = _classification().model_dump(mode="python")
    payload["classification_status"] = "language_unsupported"
    unsupported = LyricsClassification.model_validate(payload)

    class UnsupportedLanguageClassifier(FakeClassifier):
        def classify(
            self, lyrics: str, language: str | None = None
        ) -> GeminiClassificationResponse:
            self.classified_texts.append(lyrics)
            return GeminiClassificationResponse(
                outcome=GeminiOutcomeStatus.SUCCESS,
                result=unsupported,
                usage=UsageTelemetry(input_tokens=7),
            )

    summary = LyricsClassificationService(
        session, UnsupportedLanguageClassifier(), _settings()
    ).run(ClassificationRequest())

    row = session.scalar(select(LyricClassificationSnapshot))
    assert row is not None
    assert row.classification_status == "language_unsupported"
    assert row.result_json is None
    assert row.confidence is None
    assert summary.classified == 0
