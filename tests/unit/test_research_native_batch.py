import json

import pytest

from chart_observatory import research_native_batch as batch


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    project = tmp_path / "project"
    selection = project / "selection"
    selection.mkdir(parents=True)
    (selection / "manifest.json").write_text('{"synthetic":true}', encoding="utf-8")
    cells = [{"country_code": c, "year": 2019, "quota": 5} for c in ("BR", "PT", "US")]
    members = [
        {"country_code": c, "year": 2019, "provider": "MGD", "platform": "SPOTIFY"}
        for c in ("BR", "PT", "US")
        for _ in range(4)
    ]
    inventory = project / "inventory.json"
    batch.flow.write_json(
        inventory,
        {
            "files": [
                {
                    "provider": "MGD",
                    "origin_platform": "SPOTIFY",
                    "countries": [c],
                    "chart_types": ["Top 200"],
                    "path": f"{c}.tsv",
                }
                for c in ("BR", "PT", "US")
            ]
        },
    )
    monkeypatch.setattr(
        batch.flow,
        "load_selection",
        lambda path: (
            {"requested_positions": 15},
            cells,
            members,
            {str(selection / "manifest.json"): batch.flow.file_hash(selection / "manifest.json")},
        ),
    )
    calls = []

    def projection(**kwargs):
        calls.append((kwargs["country"], kwargs["year"]))
        output = kwargs["output"]
        output.mkdir(parents=True)
        report = {
            "country_code": kwargs["country"],
            "year": kwargs["year"],
            "selection_sha256": batch.flow.file_hash(selection / "manifest.json"),
            "selected_positions": 4,
            "observations": 100,
            "reconstruction_approved": True,
            "rank_and_metric_matches": 4,
            "metadata_exact_matches": 3,
            "all_fields_match": 3,
            "missing_display_metadata_observations": 1,
            "reconstruction_reasons": [],
            "scientific_approval": False,
        }
        batch.flow.write_json(output / "report.json", report)
        batch.flow.write_json(
            output / "manifest.json",
            {
                "input_hashes": {
                    str(selection / "manifest.json"): batch.flow.file_hash(
                        selection / "manifest.json"
                    )
                },
                "artifacts": {"report.json": batch.flow.file_hash(output / "report.json")},
            },
        )
        return report

    monkeypatch.setattr(batch.research_source_projection, "project_mgd_cell", projection)
    return {
        "project": project,
        "selection": selection,
        "source_manifest": inventory,
        "output": project / "data/runtime/native",
        "calls": calls,
        "cells": cells,
        "members": members,
    }


def run(scenario, **extra):
    return batch.run_campaign(
        **{k: scenario[k] for k in ("project", "selection", "source_manifest", "output")},
        workers=1,
        **extra,
    )


def test_bounded_resume_expands_without_repeating_completed_cells(scenario):
    first = run(scenario, limit=2)
    assert first["summary"]["processed_cells"] == 2
    assert scenario["calls"] == [("BR", 2019), ("PT", 2019)]
    second = run(scenario, limit=3)
    assert second["summary"]["processed_cells"] == 3
    assert len(scenario["calls"]) == 3
    assert second["summary"]["scientifically_approved_positions"] == 0
    assert second["summary"]["matched_rank_metric_positions"] == 12
    assert second["summary"]["processed_share_of_requested_percent"] == 80
    assert second["summary"]["production_writes"] == 0


def test_tampered_completed_evidence_cannot_be_reused(scenario):
    report = run(scenario, limit=1)
    path = next(iter(report["cells"].values()))["evidence"]
    from pathlib import Path

    (Path(path) / "report.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact changed"):
        run(scenario, limit=2)


def test_changed_campaign_inventory_requires_new_output(scenario):
    run(scenario, limit=1)
    value = json.loads(scenario["source_manifest"].read_text(encoding="utf-8"))
    value["extra_evidence"] = True
    batch.flow.write_json(scenario["source_manifest"], value)
    with pytest.raises(ValueError, match="inputs/code changed"):
        run(scenario, limit=2)


def test_per_cell_error_remains_explicit_and_does_not_approve(scenario, monkeypatch):
    def fail(**kwargs):
        raise ValueError("synthetic missing source")

    monkeypatch.setattr(batch.research_source_projection, "project_mgd_cell", fail)
    report = run(scenario, limit=2)
    assert report["summary"]["failed_cells"] == 2
    assert report["summary"]["processed_cells"] == 0
    assert all(r["scientific_approval"] is False for r in report["cells"].values())


def test_os_lock_prevents_concurrent_campaign_owner(scenario):
    root = scenario["output"]
    root.mkdir(parents=True)
    with batch._exclusive(root), pytest.raises(ValueError, match="already active"):
        run(scenario, limit=1)


def test_invalid_limit_or_external_output_has_no_campaign_writes(scenario):
    with pytest.raises(ValueError, match="positive cell limit"):
        run(scenario, limit=0)
    scenario["output"] = scenario["project"].parent / "outside"
    with pytest.raises(ValueError, match="private runtime"):
        run(scenario, limit=1)
    assert not scenario["output"].exists()


def test_non_mgd_memberships_are_not_promoted_into_native_plan():
    cells = [{"country_code": "BR", "year": 2019, "quota": 5}]
    result = batch.plan_cells(
        cells,
        [{"country_code": "BR", "year": 2019, "provider": "OTHER", "platform": "SPOTIFY"}],
        {"files": []},
    )
    assert result == []
