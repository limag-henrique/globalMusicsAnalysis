from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from chart_observatory.ui.taxonomy import taxonomy_codes


@dataclass(frozen=True, slots=True)
class ContentClassification:
    canonical_track_id: str
    taxonomy_version: str
    scores: dict[str, int | None]
    reviewer: str
    notes: str
    review_status: str
    updated_at: datetime

    def with_score(self, code: str, score: int | None) -> ContentClassification:
        if code not in taxonomy_codes():
            raise ValueError(f"unknown taxonomy code: {code!r}")
        _validate_score(score)
        scores = dict(self.scores)
        scores[code] = score
        return ContentClassification(
            self.canonical_track_id, self.taxonomy_version, scores, self.reviewer,
            self.notes, self.review_status, self.updated_at,
        )


class ClassificationRepository(Protocol):
    def get(self, track_id: str) -> ContentClassification | None: ...
    def list_all(self) -> list[ContentClassification]: ...
    def upsert(self, record: ContentClassification) -> ContentClassification: ...


class JsonClassificationRepository:
    def __init__(self, path: Path, taxonomy_version: str):
        self.path = Path(path)
        self.taxonomy_version = taxonomy_version

    def get(self, track_id: str) -> ContentClassification | None:
        return next(
            (record for record in self.list_all() if record.canonical_track_id == track_id), None
        )

    def list_all(self) -> list[ContentClassification]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version") != self.taxonomy_version
            ):
                raise ValueError("invalid classification store schema")
            records = payload.get("classifications")
            if not isinstance(records, list):
                raise ValueError("classifications must be a list")
            return [self._from_json(item) for item in records]
        except (json.JSONDecodeError, OSError, TypeError) as error:
            raise ValueError("invalid classification store") from error

    def upsert(self, record: ContentClassification) -> ContentClassification:
        self._validate_record(record)
        records = [r for r in self.list_all() if not (
            r.canonical_track_id == record.canonical_track_id
            and r.taxonomy_version == record.taxonomy_version
        )]
        records.append(record)
        payload = {
            "schema_version": self.taxonomy_version,
            "classifications": [self._to_json(r) for r in records],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            with suppress(FileNotFoundError):
                os.unlink(temporary)
            raise
        return record

    def _from_json(self, item: object) -> ContentClassification:
        if not isinstance(item, dict) or set(item) != {
            "canonical_track_id", "taxonomy_version", "scores", "reviewer", "notes",
            "review_status", "updated_at",
        }:
            raise ValueError("invalid classification record")
        timestamp = datetime.fromisoformat(item["updated_at"])
        if timestamp.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        record = ContentClassification(
            item["canonical_track_id"], item["taxonomy_version"], item["scores"],
            item["reviewer"], item["notes"], item["review_status"], timestamp.astimezone(UTC),
        )
        self._validate_record(record)
        return record

    @staticmethod
    def _to_json(record: ContentClassification) -> dict[str, object]:
        return {
            "canonical_track_id": record.canonical_track_id,
            "taxonomy_version": record.taxonomy_version,
            "scores": record.scores,
            "reviewer": record.reviewer,
            "notes": record.notes,
            "review_status": record.review_status,
            "updated_at": record.updated_at.astimezone(UTC).isoformat(),
        }

    def _validate_record(self, record: ContentClassification) -> None:
        if not isinstance(record.scores, dict):
            raise ValueError("scores must be a dictionary")
        if (
            record.taxonomy_version != self.taxonomy_version
            or set(record.scores) != set(taxonomy_codes())
        ):
            raise ValueError("record taxonomy does not match repository")
        if record.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        for score in record.scores.values():
            _validate_score(score)


def _validate_score(score: int | None) -> None:
    if score is not None and (
        isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 3
    ):
        raise ValueError(f"invalid score: {score!r}")
