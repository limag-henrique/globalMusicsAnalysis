from datetime import UTC, datetime

import pytest

from chart_observatory.ui.classifications import (
    ContentClassification,
    JsonClassificationRepository,
)
from chart_observatory.ui.taxonomy import TAXONOMY_VERSION, taxonomy_codes


def _record(track_id: str = "track-1") -> ContentClassification:
    return ContentClassification(
        canonical_track_id=track_id,
        taxonomy_version=TAXONOMY_VERSION,
        scores={code: (0 if code == "violence" else None) for code in taxonomy_codes()},
        reviewer="researcher",
        notes="fixture",
        review_status="REVIEWED",
        updated_at=datetime(2026, 9, 8, tzinfo=UTC),
    )


def test_json_repository_creates_reads_and_upserts_without_duplicates(tmp_path) -> None:
    repository = JsonClassificationRepository(tmp_path / "classifications.json", TAXONOMY_VERSION)
    repository.upsert(_record())
    repository.upsert(_record().with_score("violence", 3))

    loaded = repository.get("track-1")
    assert loaded is not None
    assert loaded.scores["violence"] == 3
    assert len(repository.list_all()) == 1


def test_json_repository_preserves_null_as_unannotated_and_rejects_out_of_range(tmp_path) -> None:
    repository = JsonClassificationRepository(tmp_path / "classifications.json", TAXONOMY_VERSION)
    record = _record()
    assert record.scores["crime"] is None
    with pytest.raises(ValueError):
        repository.upsert(record.with_score("crime", 4))


def test_json_repository_does_not_replace_corrupt_store(tmp_path) -> None:
    path = tmp_path / "classifications.json"
    path.write_text("{not-json", encoding="utf-8")
    repository = JsonClassificationRepository(path, TAXONOMY_VERSION)
    with pytest.raises(ValueError):
        repository.list_all()
    assert path.read_text(encoding="utf-8") == "{not-json"


def test_json_repository_rejects_non_dict_scores_without_replacing_store(tmp_path) -> None:
    path = tmp_path / "classifications.json"
    path.write_text(
        '{"schema_version":"content-v1","classifications":[{"canonical_track_id":"track-1",'
        '"taxonomy_version":"content-v1","scores":["sexual_explicitness","objectification",'
        '"transactional_sex","materialism","drugs","crime","violence","romantic_affection",'
        '"heartbreak"],"reviewer":"researcher",'
        '"notes":"fixture","review_status":"REVIEWED","updated_at":"2026-09-08T00:00:00+00:00"}]}',
        encoding="utf-8",
    )
    original = path.read_text(encoding="utf-8")
    repository = JsonClassificationRepository(path, TAXONOMY_VERSION)
    with pytest.raises(ValueError):
        repository.list_all()
    assert path.read_text(encoding="utf-8") == original
