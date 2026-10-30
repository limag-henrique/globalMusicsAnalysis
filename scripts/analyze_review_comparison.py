"""Describe exported human/AI differences without treating defective lyrics as ground truth."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from chart_observatory.lyrics.review_evidence import import_comparison_export


def run(source: Path, output: Path):
    evidence = import_comparison_export(source)
    payload = json.loads(source.read_text(encoding="utf-8"))
    dimensions = [row["code"] for row in payload["dimensions"]]
    paired = defaultdict(list)
    songs = []
    for evaluation in payload["evaluations"]:
        human = evaluation["review"]["scores"]
        ai = evaluation["comparison"]["ai"]
        values = []
        for dimension in dimensions:
            h, a = human.get(dimension), ai.get(dimension)
            if h is None or a is None:
                continue
            if any(type(value) is not int or not 0 <= value <= 3 for value in (h, a)):
                raise ValueError("invalid exported intensity")
            values.append((h, a))
            paired[dimension].append((h, a))
        songs.append({
            "title": evaluation["recording"]["title"],
            "recording_id": evaluation["recording"]["id"],
            "ai_exposed": evaluation["review"]["aiExposed"],
            "paired_dimensions": len(values),
            "exact_disagreements": sum(h != a for h, a in values),
            "positive_label_disagreements": sum((h >= 2) != (a >= 2) for h, a in values),
            "mean_absolute_difference": (
                sum(abs(h - a) for h, a in values) / len(values) if values else None
            ),
        })
    by_dimension = []
    for dimension, values in paired.items():
        by_dimension.append({
            "dimension": dimension, "paired_songs": len(values),
            "exact_disagreements": sum(h != a for h, a in values),
            "positive_label_disagreements": sum((h >= 2) != (a >= 2) for h, a in values),
            "mean_absolute_difference": sum(abs(h - a) for h, a in values) / len(values),
            "mean_human_minus_ai": sum(h - a for h, a in values) / len(values),
        })
    summary = {
        "reviewed_songs": len(songs), "dimensions": len(dimensions),
        "paired_scores": sum(row["paired_dimensions"] for row in songs),
        "exact_score_disagreements": sum(row["exact_disagreements"] for row in songs),
        "positive_label_disagreements": sum(row["positive_label_disagreements"] for row in songs),
        "ai_exposed_songs": sum(row["ai_exposed"] is True for row in songs),
        "songs_with_reported_lyric_defects": sum(row["decision"] in {
            "reported_identity_mismatch", "reported_text_defect",
        } for row in evidence),
        "positive_threshold": 2, "difference_is_human_minus_ai": True,
        "independent_unit": "song_not_dimension", "valid_accuracy_estimate": False,
        "human_scores_promoted": False,
    }
    output.mkdir(parents=True, exist_ok=False)
    for name, rows in (("by-song", songs), ("by-dimension", by_dimension)):
        with (output / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.reviews, args.output_dir), indent=2))
