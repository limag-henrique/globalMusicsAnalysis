from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from chart_observatory.lyrics.legacy_corpus_import import (
    legacy_annotation_candidate,
)


def test_candidate_identity_ignores_provider_song_id() -> None:
    retrieved_at = datetime(2026, 9, 19, tzinfo=UTC)
    payload = {
        "song_id": "provider-id-one",
        "title": "  Coração  ",
        "artist": " Banda Exemplo ",
        "lyrics_status": "FOUND",
        "lyrics_source": "GENIUS",
        "original_lyrics": "verso de teste",
    }

    first = legacy_annotation_candidate(payload, 1, retrieved_at)
    second = legacy_annotation_candidate({**payload, "song_id": "provider-id-two"}, 1, retrieved_at)

    assert first is not None and second is not None
    assert first.canonical_track_id == second.canonical_track_id
    assert first.lyrics_hash == second.lyrics_hash
    assert first.source == second.source
    assert first.rights_status == "RESEARCH_AUTHORIZED"
    assert first.metadata == {"ingest_artifact": "gemini_annotations.jsonl"}


def test_candidate_uses_stable_track_and_artist_ids_and_preserves_source() -> None:
    candidate = legacy_annotation_candidate(
        {
            "title": "Canção",
            "artist": "Artista",
            "lyrics_status": "FOUND",
            "lyrics_source": "letras",
            "original_lyrics": "texto",
        },
        22,
        datetime(2026, 9, 19, tzinfo=UTC),
        suspended_sources=frozenset(),
    )

    assert candidate is not None
    assert candidate.title == "Canção"
    assert candidate.artist_name == "Artista"
    assert candidate.source == "LETRAS"
    assert candidate.line_number == 22


def test_candidate_skips_missing_or_non_found_lyrics() -> None:
    retrieved_at = datetime(2026, 9, 19, tzinfo=UTC)

    assert (
        legacy_annotation_candidate(
            {
                "lyrics_status": "MISSING",
                "original_lyrics": "texto antigo",
            },
            1,
            retrieved_at,
        )
        is None
    )


def test_candidate_skips_a_quarantined_source_content_signature() -> None:
    retrieved_at = datetime(2026, 9, 19, tzinfo=UTC)
    text = "synthetic instrumental placeholder payload"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    payload = {
        "title": "Example Track",
        "artist": "Example Artist",
        "lyrics_status": "FOUND",
        "lyrics_source": "LETRAS",
        "original_lyrics": text,
    }

    assert (
        legacy_annotation_candidate(
            payload,
            1,
            retrieved_at,
            quarantined_source_signatures=frozenset({("LETRAS", digest)}),
            suspended_sources=frozenset(),
        )
        is None
    )
    assert (
        legacy_annotation_candidate(
            {**payload, "lyrics_source": "GENIUS"},
            2,
            retrieved_at,
            quarantined_source_signatures=frozenset({("LETRAS", digest)}),
            suspended_sources=frozenset(),
        )
        is not None
    )
    assert (
        legacy_annotation_candidate(
            {
                **payload,
                "title": "Example Track (Acoustic Version)",
                "original_lyrics": "distinct lyrics from the legitimate acoustic release",
            },
            3,
            retrieved_at,
            quarantined_source_signatures=frozenset({("LETRAS", digest)}),
            suspended_sources=frozenset(),
        )
        is not None
    )
    assert (
        legacy_annotation_candidate(
            {"lyrics_status": "FOUND", "original_lyrics": "   "}, 2, retrieved_at
        )
        is None
    )


def test_candidate_skips_every_row_from_a_suspended_source() -> None:
    retrieved_at = datetime(2026, 9, 19, tzinfo=UTC)
    payload = {
        "title": "Example Track",
        "artist": "Example Artist",
        "lyrics_status": "FOUND",
        "lyrics_source": "LETRAS",
        "original_lyrics": "complete lyric text that would otherwise be importable",
    }

    assert (
        legacy_annotation_candidate(
            payload,
            1,
            retrieved_at,
            quarantined_source_signatures=frozenset(),
            suspended_sources=frozenset({"LETRAS"}),
        )
        is None
    )
    assert (
        legacy_annotation_candidate(
            {**payload, "lyrics_source": "GENIUS"},
            2,
            retrieved_at,
            quarantined_source_signatures=frozenset(),
            suspended_sources=frozenset({"LETRAS"}),
        )
        is not None
    )


def test_candidate_truncates_display_artist_without_changing_track_identity() -> None:
    candidate = legacy_annotation_candidate(
        {
            "title": "Canção",
            "artist": "a" * 501,
            "lyrics_status": "FOUND",
            "lyrics_source": "GENIUS",
            "original_lyrics": "texto",
        },
        1,
        datetime(2026, 9, 19, tzinfo=UTC),
    )

    assert candidate is not None
    assert len(candidate.artist_name) == 500
