import json
import zipfile

import pytest

from chart_observatory import revision_workflow as workflow
from chart_observatory.pipeline_state import StageResult


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    prepared, reviews, state = [tmp_path / name for name in ("prepared", "reviews", "state")]
    for path in (prepared, reviews, state):
        path.mkdir()
    (prepared / "manifest.json").write_text('{"candidate_limit":120}')
    (reviews / "manifest.json").write_text('{"eight_cases":8}')
    (reviews / "quality-criteria-proposal.json").write_text('{"status":"draft"}')
    (prepared / "country-year-platform-coverage.csv").write_text(
        "country_code,coverage_status\nBR,PARTIAL\n"
    )
    row = dict(
        country_code="BR",
        year=2025,
        platform="SPOTIFY",
        window="full_year",
        candidate_id="one",
        coverage_status="PARTIAL",
        metric_value=10,
    )
    (prepared / "original_top80.jsonl").write_text(json.dumps(row) + "\n")
    (prepared / "eligible.jsonl").write_text("")
    article = tmp_path / "previous-article.md"
    article.write_text("preserve this edition")
    monkeypatch.setattr(
        workflow,
        "reconcile_budget",
        lambda *_: {"reconciled": False, "within_limits": True, "spendable_usd": "0"},
    )
    monkeypatch.setattr(
        workflow,
        "_recovery",
        lambda *_: StageResult("completed_with_deficits", {"valid_lyrics": 0}),
    )
    monkeypatch.setattr(
        workflow.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail(
            "Preparation must not start provider or collection processes by default"
        ),
    )
    return tmp_path, state, prepared, reviews


def test_preparation_is_resumable_and_exports_no_lyrics_or_fake_results(campaign):
    report = workflow.run_workflow(*campaign)
    assert report["paid_calls"] == 0
    assert report["scientific_ready"] is False
    assert report["stages"]["calcular_rankings"]["counters"]["publishable_country_ranks"] == 0
    package = next(campaign[1].rglob("preparation-package.zip"))
    with zipfile.ZipFile(package) as archive:
        assert set(archive.namelist()) == {
            "article-methods-draft.md",
            "acceptance.json",
            "country-year-platform-coverage.csv",
            "missing-lyrics-scenarios.csv",
        }
    assert (campaign[0] / "previous-article.md").read_text() == "preserve this edition"
    again = workflow.run_workflow(*campaign)
    assert all(stage["cached"] for stage in again["stages"].values())


def test_explicit_resume_invalidates_cached_recovery_without_repeating_other_stages(
    campaign, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        workflow,
        "_recovery",
        lambda *_args: calls.append(_args[-1]) or StageResult("completed_with_deficits"),
    )
    workflow.run_workflow(*campaign, through="recuperar_letras")
    report = workflow.run_workflow(*campaign, through="recuperar_letras", resume=True)
    assert calls == [False, True]
    assert report["stages"]["inventariar"]["cached"] is True


def test_independent_stage_and_changed_coverage_refresh_package(campaign):
    workflow.run_workflow(*campaign)
    (campaign[2] / "country-year-platform-coverage.csv").write_text(
        "country_code,coverage_status\nBR,MISSING\n"
    )
    report = workflow.run_workflow(*campaign, only="gerar_artigo_pacote")
    assert list(report["stages"]) == ["gerar_artigo_pacote"]
    assert report["stages"]["gerar_artigo_pacote"]["cached"] is False
    package = next(
        path for path in report["stages"]["gerar_artigo_pacote"]["outputs"] if path.endswith(".zip")
    )
    with zipfile.ZipFile(package) as archive:
        assert "MISSING" in archive.read("country-year-platform-coverage.csv").decode()
        # A previous diagnostic cannot accompany changed coverage without recomputation.
        assert "missing-lyrics-scenarios.csv" not in archive.namelist()


def test_outputs_outside_project_are_rejected_before_writing(campaign):
    project, state, prepared, reviews = campaign
    with pytest.raises(ValueError, match="physically inside"):
        workflow.run_workflow(project, project.parent / "outside", prepared, reviews)
    assert not (project.parent / "outside").exists()
