import json
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from typer.testing import CliRunner

import chart_observatory.cli as cli_module
from chart_observatory.cli import app

runner = CliRunner()


def test_batch_service_factory_caps_output_at_1024(monkeypatch) -> None:
    captured: dict[str, object] = {}
    settings = SimpleNamespace(
        database_url="sqlite://",
        google_cloud_project="test-project",
        google_cloud_location="global",
        gemini_batch_bucket="test-bucket",
        gemini_model="gemini-3.8-flash",
        gemini_thinking_level="LOW",
    )

    monkeypatch.setattr(cli_module.Settings, "load", lambda _root: settings)
    monkeypatch.setattr(
        cli_module,
        "ResearchApplication",
        lambda _root, database_url: SimpleNamespace(session=object()),
    )
    monkeypatch.setattr(
        cli_module.BatchStorageAdapter,
        "from_adc",
        lambda _project, _bucket: object(),
    )
    monkeypatch.setattr(cli_module, "VertexBatchAdapter", lambda _project, _location: object())

    def fake_classifier(*_args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(cli_module, "GeminiLyricsClassifier", fake_classifier)
    monkeypatch.setattr(
        cli_module,
        "BatchClassificationService",
        lambda *_args, **_kwargs: object(),
    )

    cli_module._build_batch_service(None)

    assert captured["max_output_tokens"] == 1024


def test_prepare_main_requires_positive_cost_cap() -> None:
    result = runner.invoke(
        app,
        [
            "corpus",
            "classify-lyrics-batch",
            "prepare-main",
            "--max-cost-usd",
            "0",
        ],
    )

    assert result.exit_code == 2
    assert "positive" in result.stderr


def test_import_prints_counts_without_payloads(monkeypatch, tmp_path) -> None:
    run_id = uuid4()
    summary = SimpleNamespace(
        processed=100,
        classified=98,
        ambiguous=1,
        blocked=0,
        language_unsupported=0,
        insufficient_text=0,
        instrumental=0,
        errors=1,
        duplicates=0,
        input_tokens=1000,
        output_tokens=500,
        thought_tokens=100,
        total_tokens=1600,
        known_cost_usd=Decimal("0.42"),
    )
    fake = SimpleNamespace(import_results=lambda value: summary)
    monkeypatch.setattr("chart_observatory.cli._build_batch_service", lambda _url: fake)
    monkeypatch.setattr(
        "chart_observatory.cli._BATCH_EVENT_LOG", tmp_path / "safe-events.jsonl"
    )

    result = runner.invoke(
        app,
        ["corpus", "classify-lyrics-batch", "import-results", "--run-id", str(run_id)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["classified"] == 98
    assert "lyrics" not in result.stdout.casefold()
    assert "prompt" not in result.stdout.casefold()


def test_batch_help_has_all_explicit_commands_and_no_force() -> None:
    result = runner.invoke(app, ["corpus", "classify-lyrics-batch", "--help"])

    assert result.exit_code == 0
    for command in (
        "preflight",
        "prepare-canary",
        "prepare-pilot",
        "prepare-main",
        "submit",
        "status",
        "import-results",
        "quality-report",
        "accept-pilot",
        "finalize",
        "cleanup",
        "retry-errors",
    ):
        assert command in result.stdout
    assert "--force" not in result.stdout


def test_retry_errors_can_be_limited_to_explicit_error_codes(monkeypatch, tmp_path) -> None:
    run_id = uuid4()
    captured: dict[str, object] = {}

    def prepare(
        prior_run_id, max_cost_usd, error_codes=None, limit=None, missing_usage_only=False
    ):
        captured.update(
            prior_run_id=prior_run_id,
            max_cost_usd=max_cost_usd,
            error_codes=error_codes,
            limit=limit,
            missing_usage_only=missing_usage_only,
        )
        return []

    monkeypatch.setattr(
        "chart_observatory.cli._build_batch_service",
        lambda _url: SimpleNamespace(prepare_retry_errors=prepare),
    )
    monkeypatch.setattr(
        "chart_observatory.cli._BATCH_EVENT_LOG", tmp_path / "safe-events.jsonl"
    )

    result = runner.invoke(
        app,
        [
            "corpus",
            "classify-lyrics-batch",
            "retry-errors",
            "--prior-run-id",
            str(run_id),
            "--max-cost-usd",
            "595",
            "--error-code",
            "batch_malformed_response",
            "--limit",
            "40000",
            "--missing-usage-only",
        ],
    )

    assert result.exit_code == 0
    assert captured["error_codes"] == frozenset({"batch_malformed_response"})
    assert captured["limit"] == 40000
    assert captured["missing_usage_only"] is True
