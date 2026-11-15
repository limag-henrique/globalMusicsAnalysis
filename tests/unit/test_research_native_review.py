import json

import pytest

from chart_observatory import research_native_review as review


def comparison(country="BR", **changes):
    return {
        "country_code": country,
        "year": 2019,
        "position": 1,
        "candidate_id": "SPOTIFY:synthetic",
        "row_sha256": "a" * 64,
        "rank_match": True,
        "metric_match": True,
        "metadata_match": False,
        "selected_title": "Synthetic title",
        "selected_artist": "A | B",
        "reconstructed_title": "Synthetic title",
        "reconstructed_artist": "A, B",
        **changes,
    }


@pytest.fixture
def campaign(tmp_path):
    root = tmp_path / "campaign"
    root.mkdir()
    status = {"state": "completed_with_deficits", "selection_sha256": "b" * 64, "cells": {}}
    for country in ("BR", "PT"):
        cell = root / country
        cell.mkdir()
        review.flow.write_rows(cell / "selection-comparison.jsonl", [comparison(country)])
        review.flow.write_json(
            cell / "report.json",
            {
                "selection_sha256": "b" * 64,
                "scientific_approval": False,
            },
        )
        review.flow.write_json(
            cell / "manifest.json",
            {
                "artifacts": {
                    "selection-comparison.jsonl": review.flow.file_hash(
                        cell / "selection-comparison.jsonl"
                    )
                },
            },
        )
        status["cells"][f"{country}-2019"] = {
            "state": "completed",
            "evidence": str(cell),
            "report_sha256": review.flow.file_hash(cell / "report.json"),
        }
    review.flow.write_json(root / "status.json", status)
    return root, tmp_path / "review"


def test_deduplicated_review_preserves_every_membership_and_never_approves(campaign):
    root, output = campaign
    report = review.build_queue(root, output)
    assert report["affected_memberships"] == 2
    assert report["distinct_review_forms"] == 1
    assert report["scientific_approval"] is False
    assert report["rank_metric_conflicts"] == 0
    card = next(review.flow.rows(output / "metadata-review.jsonl"))
    assert len(card["memberships"]) == 2
    assert card["kind"] == "possible_artist_separator_change"
    assert card["decision"] is None
    assert card["reviewer"] is None
    assert card["scientific_approval"] is False


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"reconstructed_artist": None}, "source_display_metadata_missing"),
        ({"selected_artist": None}, "selected_display_metadata_missing"),
        (
            {"selected_artist": "artist", "reconstructed_artist": "ARTIST"},
            "possible_case_or_unicode_representation_change",
        ),
        (
            {"reconstructed_title": "Synthetic title - Live"},
            "title_or_version_discrepancy_requires_review",
        ),
        ({"reconstructed_artist": "Other artist"}, "artist_credit_discrepancy_requires_review"),
    ],
)
def test_hints_are_explicit_and_do_not_infer_identity(changes, expected):
    assert review.discrepancy_kind(comparison(**changes)) == expected


def test_tampered_comparison_is_rejected_before_creating_review_output(campaign):
    root, output = campaign
    (root / "BR/selection-comparison.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact changed"):
        review.build_queue(root, output)
    assert not output.exists()


def test_current_campaign_advancing_requires_a_stable_checkpoint(campaign, monkeypatch):
    root, output = campaign
    original = review.flow.rows

    def racing_rows(path):
        status = json.loads((root / "status.json").read_text(encoding="utf-8"))
        status["updated_at"] = "changed"
        review.flow.write_json(root / "status.json", status)
        yield from original(path)

    monkeypatch.setattr(review.flow, "rows", racing_rows)
    with pytest.raises(ValueError, match="advanced"):
        review.build_queue(root, output)
    assert not output.exists()


def test_numeric_conflicts_remain_separate_from_metadata_review(campaign):
    root, output = campaign
    path = root / "BR/selection-comparison.jsonl"
    review.flow.write_rows(path, [comparison(metric_match=False)])
    review.flow.write_json(
        root / "BR/manifest.json",
        {
            "artifacts": {"selection-comparison.jsonl": review.flow.file_hash(path)},
        },
    )
    report = review.build_queue(root, output)
    assert report["rank_metric_conflicts"] == 1
    assert len(list(review.flow.rows(output / "rank-metric-conflicts.jsonl"))) == 1


def test_old_review_version_cannot_be_overwritten(campaign):
    root, output = campaign
    review.build_queue(root, output)
    with pytest.raises(ValueError, match="new version"):
        review.build_queue(root, output)
