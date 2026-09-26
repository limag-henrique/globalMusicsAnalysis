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
        gemini_thinking_level="MINIMAL",
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
