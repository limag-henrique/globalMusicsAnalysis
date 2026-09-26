from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import select
from typer.testing import CliRunner

import chart_observatory.cli as cli
from chart_observatory.application import ResearchApplication
from chart_observatory.cli import app
from chart_observatory.db.models.corpus import LyricClassificationSnapshot
from chart_observatory.lyrics.classification_service import ClassificationRunSummary
from chart_observatory.lyrics.repository import LyricDocumentInput, ingest_lyric_document


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        database_url="sqlite+pysqlite:///:memory:",
        google_cloud_project="test-project",
        google_cloud_location="global",
        gemini_model="gemini-fixed-model",
        gemini_thinking_level="LOW",
        gemini_output_token_allowance=100,
        gemini_input_usd_per_million_tokens=Decimal("1"),
        gemini_output_usd_per_million_tokens=Decimal("2"),
        gemini_thought_usd_per_million_tokens=Decimal("3"),
    )


def test_cli_forwards_bounded_options_and_prints_compact_json(monkeypatch) -> None:
    """Catches CLI flags being dropped or a verbose/non-JSON result exposing payloads."""
    requests: list[object] = []

    class FakeApplication:
        session = object()

        def __init__(self, *_args, **_kwargs) -> None:
            pass

    class FakeClassifier:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

    class FakeService:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, request):
            requests.append(request)
            return ClassificationRunSummary(selected=5, classified=3, skipped_idempotent=2)

    monkeypatch.setattr(cli.Settings, "load", lambda _path: _settings())
    monkeypatch.setattr(cli, "ResearchApplication", FakeApplication)
    monkeypatch.setattr(cli, "GeminiLyricsClassifier", FakeClassifier)
    monkeypatch.setattr(cli, "LyricsClassificationService", FakeService)

    result = CliRunner().invoke(
        app,
        [
            "corpus",
            "classify-lyrics",
            "--limit",
            "5",
            "--force",
            "--only-unclassified",
            "--estimate-cost",
            "--max-cost-usd",
            "1.25",
            "--workers",
            "3",
        ],
    )

    assert result.exit_code == 0, result.stdout
    request = requests[0]
    assert request.limit == 5
    assert request.force is True
    assert request.only_unclassified is True
    assert request.estimate_cost is True
    assert request.max_cost_usd == Decimal("1.25")
    assert request.workers == 3
    assert json.loads(result.stdout) == {
        "selected": 5,
        "skipped_idempotent": 2,
        "classified": 3,
        "status_outcomes": {},
        "known_input_tokens": 0,
        "known_output_tokens": 0,
        "known_thought_tokens": 0,
        "known_total_tokens": 0,
        "known_cost_usd": None,
        "errors": 0,
        "skipped_due_to_error": 0,
        "item_outcomes": [],
        "estimated_candidates": 0,
        "estimated_input_tokens": None,
        "output_token_allowance": 0,
        "estimated_cost_usd": None,
    }


def test_cli_rejects_worker_count_above_controlled_maximum() -> None:
    """Catches accidental removal of the CLI's conservative concurrency ceiling."""
    result = CliRunner().invoke(app, ["corpus", "classify-lyrics", "--workers", "9"])

    assert result.exit_code == 2
    assert "Invalid value" in result.stderr


def test_cli_persists_insufficient_text_without_sdk_generation(
    tmp_path: Path, monkeypatch
) -> None:
    """Catches the CLI bypassing local preflight and sending short text to the SDK."""
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'lyrics.sqlite3').as_posix()}"
    seed = ResearchApplication(tmp_path / "seed", database_url=database_url)
    ingest_lyric_document(
        seed.session,
        LyricDocumentInput(
            canonical_track_id=uuid4(),
            source="TEST",
            source_version="v1",
            rights_status="RESEARCH_AUTHORIZED",
            text="zqxjv",
        ),
    )
    seed.session.commit()

    class NoSdkClassifier:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def classify(self, *_args, **_kwargs):
            raise AssertionError("short text must not reach SDK generation")

        def estimate_input_tokens(self, *_args, **_kwargs):
            raise AssertionError("short text must not reach SDK token counting")

    monkeypatch.setattr(cli.Settings, "load", lambda _path: _settings())
    monkeypatch.setattr(cli, "GeminiLyricsClassifier", NoSdkClassifier)

    result = CliRunner().invoke(
        app,
        ["corpus", "classify-lyrics", "--database-url", database_url],
    )

    assert result.exit_code == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status_outcomes"] == {"insufficient_text": 1}
    assert "zqxjv" not in result.stdout
    seed.session.expire_all()
    row = seed.session.scalar(select(LyricClassificationSnapshot))
    assert row is not None
    assert row.classification_status == "insufficient_text"
    assert row.result_json is None


def test_run_cli_estimates_then_continues_after_item_error(
    tmp_path: Path, monkeypatch
) -> None:
    """An item error is logged as skipped while the unattended run advances."""
    requests: list[object] = []
    responses = iter(
        [
            ClassificationRunSummary(
                selected=2,
                estimated_candidates=2,
                estimated_input_tokens=20,
                output_token_allowance=200,
                estimated_cost_usd=Decimal("0.001"),
            ),
            ClassificationRunSummary(
                selected=2,
                classified=1,
                errors=1,
                skipped_due_to_error=1,
                status_outcomes={"classified": 1, "error": 1},
                item_outcomes=[
                    {
                        "lyric_document_id": "doc-error",
                        "canonical_track_id": "track-error",
                        "status": "error",
                        "error": "temporary transport failure",
                        "provider_outcome": "transient_error",
                    },
                    {
                        "lyric_document_id": "doc-ok",
                        "canonical_track_id": "track-ok",
                        "status": "classified",
                        "error": None,
                        "provider_outcome": "success",
                    },
                ],
            ),
        ]
    )

    class FakeApplication:
        session = SimpleNamespace(expire_all=lambda: None)

        def __init__(self, *_args, **_kwargs) -> None:
            pass

    class FakeClassifier:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

    class FakeService:
        def __init__(self, *_args, **_kwargs) -> None:
            self.remaining = iter([2, 0])

        def count_initial_pass_remaining(self) -> int:
            return next(self.remaining)

        def run(self, request):
            requests.append(request)
            return next(responses)

    monkeypatch.setattr(cli.Settings, "load", lambda _path: _settings())
    monkeypatch.setattr(cli, "ResearchApplication", FakeApplication)
    monkeypatch.setattr(cli, "GeminiLyricsClassifier", FakeClassifier)
    monkeypatch.setattr(cli, "LyricsClassificationService", FakeService)
    log_path = tmp_path / "classification.jsonl"

    result = CliRunner().invoke(
        app,
        [
            "corpus",
            "classify-lyrics-run",
            "--batch-size",
            "5",
            "--workers",
            "1",
            "--log-path",
            str(log_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert [event["event"] for event in events] == ["estimate", "batch", "complete"]
    assert events[1]["skipped_due_to_error"] == 1
    assert events[1]["remaining"] == 0
    assert events[-1]["total_classified"] == 1
    assert events[-1]["total_skipped_due_to_error"] == 1
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3
    assert requests[0].estimate_cost is True
    assert all(request.only_unclassified is True for request in requests)
    assert all(request.workers == 1 for request in requests)


def test_run_cli_stops_after_global_authentication_error(tmp_path: Path, monkeypatch) -> None:
    """A global credential failure must stop before wasting calls on later batches."""
    calls = 0

    class FakeApplication:
        session = SimpleNamespace(expire_all=lambda: None)

        def __init__(self, *_args, **_kwargs) -> None:
            pass

    class FakeClassifier:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

    class FakeService:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def count_initial_pass_remaining(self) -> int:
            return 10

        def run(self, request):
            nonlocal calls
            calls += 1
            if request.estimate_cost:
                return ClassificationRunSummary(
                    selected=5,
                    estimated_candidates=5,
                    estimated_input_tokens=50,
                    output_token_allowance=500,
                    estimated_cost_usd=Decimal("0.01"),
                )
            return ClassificationRunSummary(
                selected=1,
                errors=1,
                skipped_due_to_error=1,
                status_outcomes={"error": 1},
                item_outcomes=[
                    {
                        "lyric_document_id": "doc-auth",
                        "canonical_track_id": "track-auth",
                        "status": "error",
                        "error": "Gemini authentication failed (HTTP 401)",
                        "provider_outcome": "auth_error",
                    }
                ],
            )

    monkeypatch.setattr(cli.Settings, "load", lambda _path: _settings())
    monkeypatch.setattr(cli, "ResearchApplication", FakeApplication)
    monkeypatch.setattr(cli, "GeminiLyricsClassifier", FakeClassifier)
    monkeypatch.setattr(cli, "LyricsClassificationService", FakeService)

    result = CliRunner().invoke(
        app,
        ["corpus", "classify-lyrics-run", "--log-path", str(tmp_path / "run.jsonl")],
    )

    assert result.exit_code == 2
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert events[-1]["event"] == "fatal"
    assert events[-1]["reason"] == "authentication_or_authorization"
    assert calls == 2
