"""Native evidence projection; extraction success never fabricates approval."""

import csv
import json
from datetime import date, timedelta

import pytest

from chart_observatory import research_source_projection as projection

FIELDS = ["ID", "Track", "Artist", "Position", "Streams", "Date", "Chart", "market"]
FIRST_ID = "A" * 22
SECOND_ID = "B" * 22


def native(**changes):
    return {
        "ID": FIRST_ID,
        "Track": "Native title",
        "Artist": "Native artist",
        "Position": "9",
        "Streams": "1,234,567",
        "Date": "2026-01-01",
        "Chart": "Top 200",
        "market": "br",
        **changes,
    }


def save_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def save_tsv(path, values, fields=FIELDS):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(values)


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    selection = project / "selection"
    selection.mkdir()
    save_json(selection / "manifest.json", {"synthetic_selection": True})
    raw = project / "native.tsv"
    inventory_path = project / "source-inventory.json"
    member = {
        "country_code": "BR",
        "year": 2026,
        "provider": "MGD",
        "platform": "SPOTIFY",
        "candidate_id": "SPOTIFY:" + FIRST_ID,
        "position": 1,
        "metric_value": 1234567,
        "title": "Native title",
        "artist": "Native artist",
    }
    members, cells, captured = [member], [{"country_code": "BR", "year": 2026, "quota": 1}], {}

    def inventory(values):
        save_tsv(raw, values)
        save_json(
            inventory_path,
            {
                "files": [
                    {
                        "path": raw.relative_to(project).as_posix(),
                        "sha256": projection.flow.file_hash(raw),
                        "provider": "MGD",
                        "origin_platform": "SPOTIFY",
                    }
                ]
            },
        )

    inventory([native()])
    monkeypatch.setattr(
        projection.flow,
        "load_selection",
        lambda _: (
            {"cutoff": "2026-10-15"},
            cells,
            members,
            {
                str(selection / "manifest.json"): projection.flow.file_hash(
                    selection / "manifest.json"
                )
            },
        ),
    )

    def fake_reconstruction(observations, **kwargs):
        captured["observations"] = list(observations)
        captured["kwargs"] = kwargs
        return {
            "approved": True,
            "reasons": [],
            "counts": {"missing_display_metadata_observations": 0},
            "rows": [
                {
                    **member,
                    "tie_group": [],
                    "position": 1,
                    "title": "Native title",
                    "artist": "Native artist",
                }
            ],
        }

    monkeypatch.setattr(projection, "reconstruct_chart_sum", fake_reconstruction)
    arguments = {
        "project": project,
        "selection": selection,
        "raw_source": raw,
        "output": project / "evidence",
        "country": "br",
        "year": 2026,
        "source_manifest": inventory_path,
    }
    return {
        "arguments": arguments,
        "inventory": inventory,
        "captured": captured,
        "members": members,
        "cells": cells,
        "project": project,
        "raw": raw,
        "inventory_path": inventory_path,
    }


def test_keeps_native_rank_exact_integer_streams_and_row_provenance(scenario):
    report = projection.project_mgd_cell(**scenario["arguments"])
    obs = scenario["captured"]["observations"]
    assert len(obs) == 1
    assert obs[0]["position"] == 9  # File order and annual selected rank are both different.
    assert obs[0]["metric_value"] == 1234567
    assert type(obs[0]["metric_value"]) is int
    assert obs[0]["candidate_id"] == "SPOTIFY:" + FIRST_ID
    assert obs[0]["source_row_number"] == 2
    assert obs[0]["source_artifact"] == "native.tsv"
    assert scenario["captured"]["kwargs"]["expected_depth"] == 200
    assert report["observations"] == 1


def test_selects_only_top200_country_year_and_cutoff(scenario):
    scenario["inventory"](
        [
            native(),
            native(Chart="Viral 50"),
            native(market="PT"),
            native(Date="2025-12-31"),
            native(Date="2026-10-16"),
            native(Date="2027-01-01"),
            native(Date="2026-10-15", ID=SECOND_ID, Position="3"),
        ]
    )
    report = projection.project_mgd_cell(**scenario["arguments"])
    assert report["observations"] == 2
    assert [r["position"] for r in scenario["captured"]["observations"]] == [9, 3]
    assert [r["source_row_number"] for r in scenario["captured"]["observations"]] == [2, 8]


@pytest.mark.parametrize("metric", ["1,23", "12.5", "NaN", "-3", "", "unavailable"])
def test_invalid_metrics_are_preserved_for_verifier_instead_of_dropped(scenario, metric):
    scenario["inventory"]([native(Streams=metric)])
    report = projection.project_mgd_cell(**scenario["arguments"])
    assert report["observations"] == 1
    assert scenario["captured"]["observations"][0]["metric_value"] is None


def test_zero_metric_is_preserved_as_zero(scenario):
    scenario["inventory"]([native(Streams="0")])
    projection.project_mgd_cell(**scenario["arguments"])
    assert scenario["captured"]["observations"][0]["metric_value"] == 0


def test_invalid_native_id_and_rank_are_preserved_for_verifier(scenario):
    scenario["inventory"]([native(ID="not-a-native-id", Position="unknown")])
    projection.project_mgd_cell(**scenario["arguments"])
    obs = scenario["captured"]["observations"][0]
    assert obs["candidate_id"] is None
    assert obs["position"] is None


def test_invalid_date_remains_explicit_deficit_and_blocks_reconstruction_approval(scenario):
    scenario["inventory"]([native(), native(Date="not-a-date")])
    report = projection.project_mgd_cell(**scenario["arguments"])
    assert report["invalid_dates"] == 1
    assert report["reconstruction_approved"] is False
    bad = list(projection.flow.rows(scenario["arguments"]["output"] / "invalid-source-rows.jsonl"))
    assert bad == [{"source_row_number": 3, "reason": "invalid_date"}]


def test_matching_rank_metric_and_disagreeing_metadata_are_reported_separately(scenario):
    scenario["members"][0]["title"] = "Reviewed display name differs"
    report = projection.project_mgd_cell(**scenario["arguments"])
    assert report["rank_and_metric_matches"] == 1
    assert report["metadata_exact_matches"] == 0
    assert report["all_fields_match"] == 0
    comparison = next(
        projection.flow.rows(scenario["arguments"]["output"] / "selection-comparison.jsonl")
    )
    assert comparison["reconstructed_title"] == "Native title"
    assert comparison["selected_title"] == "Reviewed display name differs"


def test_even_complete_matching_extraction_does_not_fabricate_scientific_review(scenario):
    report = projection.project_mgd_cell(**scenario["arguments"])
    assert report["reconstruction_approved"] is True
    assert report["all_fields_match"] == 1
    assert report["scientific_approval"] is False
    assert report["paid_calls"] == report["production_writes"] == 0
    output = scenario["arguments"]["output"]
    definition = json.loads((output / "source-definition.draft.json").read_text(encoding="utf-8"))
    assert definition["source_url"] is definition["retrieved_at"] is None
    assert all(
        definition[key] is False
        for key in (
            "calendar_verified",
            "depth_verified",
            "identity_verified",
            "boundary_tie_resolved",
        )
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert all(
        projection.flow.file_hash(output / name) == digest
        for name, digest in manifest["artifacts"].items()
    )


def test_changed_native_bytes_are_rejected_before_writing_evidence(scenario):
    with scenario["raw"].open("a", encoding="utf-8") as handle:
        handle.write("modified after inventory\n")
    with pytest.raises(ValueError, match="does not match frozen"):
        projection.project_mgd_cell(**scenario["arguments"])
    assert not scenario["arguments"]["output"].exists()


def test_source_change_during_reconstruction_is_rejected(scenario, monkeypatch):
    old = projection.reconstruct_chart_sum

    def changed(*args, **kwargs):
        result = old(*args, **kwargs)
        with scenario["raw"].open("a", encoding="utf-8") as handle:
            handle.write("changed mid-run\n")
        return result

    monkeypatch.setattr(projection, "reconstruct_chart_sum", changed)
    with pytest.raises(ValueError, match="input changed"):
        projection.project_mgd_cell(**scenario["arguments"])
    assert not scenario["arguments"]["output"].exists()


def test_output_outside_project_is_rejected_before_writing(scenario, tmp_path):
    scenario["arguments"]["output"] = tmp_path / "outside"
    with pytest.raises(ValueError, match="inside project"):
        projection.project_mgd_cell(**scenario["arguments"])
    assert not (tmp_path / "outside").exists()


def test_missing_or_different_primary_source_is_rejected(scenario):
    scenario["members"][0]["provider"] = "KAGGLE"
    with pytest.raises(ValueError, match="primary source"):
        projection.project_mgd_cell(**scenario["arguments"])
    assert not scenario["arguments"]["output"].exists()


def test_real_complete_200_deep_native_calendar_reconstructs_exact_totals(scenario, monkeypatch):
    from chart_observatory.research_rankings import reconstruct_chart_sum

    monkeypatch.setattr(projection, "reconstruct_chart_sum", reconstruct_chart_sum)
    start, end = date(2026, 1, 1), date(2026, 10, 15)
    days = (end - start).days + 1
    scenario["inventory"](
        [
            native(
                ID=f"{position:022d}",
                Track=f"Track {position}",
                Artist=f"Artist {position}",
                Position=str(position),
                Streams=f"{1000 - position:,}",
                Date=(start + timedelta(days=day)).isoformat(),
            )
            for day in range(days)
            for position in range(1, 201)
        ]
    )
    scenario["members"][:] = [
        {
            "country_code": "BR",
            "year": 2026,
            "provider": "MGD",
            "platform": "SPOTIFY",
            "candidate_id": "SPOTIFY:" + f"{position:022d}",
            "position": position,
            "metric_value": (1000 - position) * days,
            "title": f"Track {position}",
            "artist": f"Artist {position}",
        }
        for position in (1, 2)
    ]
    scenario["cells"][0]["quota"] = 2
    report = projection.project_mgd_cell(**scenario["arguments"])
    assert report["observations"] == days * 200
    assert report["reconstruction_approved"] is True
    assert report["rank_and_metric_matches"] == report["all_fields_match"] == 2
    assert report["scientific_approval"] is False
    reconstruction = json.loads(
        (scenario["arguments"]["output"] / "reconstruction.json").read_text(encoding="utf-8")
    )
    assert reconstruction["rows"][0]["metric_value"] == str(999 * days)
    assert reconstruction["partial_year"] is True
