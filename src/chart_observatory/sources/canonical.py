from __future__ import annotations

from dataclasses import dataclass

from chart_observatory.sources.models import SourceObservation

type SlotKey = tuple[object, ...]


@dataclass(frozen=True)
class CanonicalChartEntry:
    """A reviewable slot-level interpretation of one or more source observations."""

    slot_key: SlotKey
    observations: tuple[SourceObservation, ...]
    preferred_source: str | None
    selected_observation: SourceObservation | None
    status: str


def slot_key(observation: SourceObservation) -> SlotKey:
    """Locate the chart slot before deciding whether track values agree."""
    return (
        observation.origin_platform,
        observation.country_code,
        observation.chart_name,
        observation.period_start,
        observation.period_end,
        observation.rank,
    )


def track_candidate_key(observation: SourceObservation) -> tuple[str, str]:
    return (observation.artist.casefold().strip(), observation.track_title.casefold().strip())


def canonicalize(
    observations: list[SourceObservation] | tuple[SourceObservation, ...],
    *,
    precedence: tuple[str, ...] = (
        "MGD",
        "CHARTMETRIC",
        "KAGGLE_DHRUVILDAVE",
        "PRO_MUSICA_BRASIL",
        "YOUTUBE_DATA_API",
    ),
) -> tuple[CanonicalChartEntry, ...]:
    """Consolidate equivalent chart slots without discarding source evidence."""
    grouped: dict[SlotKey, list[SourceObservation]] = {}
    for observation in observations:
        grouped.setdefault(slot_key(observation), []).append(observation)

    priority = {provider: index for index, provider in enumerate(precedence)}
    result: list[CanonicalChartEntry] = []
    for key, group in grouped.items():
        ordered = tuple(
            sorted(
                group,
                key=lambda item: (priority.get(item.provider, len(priority)), item.provider),
            )
        )
        candidates = {track_candidate_key(item) for item in ordered}
        selected = ordered[0] if len(candidates) == 1 else None
        result.append(
            CanonicalChartEntry(
                slot_key=key,
                observations=ordered,
                preferred_source=ordered[0].provider if ordered else None,
                selected_observation=selected,
                status="SOURCE_CONFLICT" if len(candidates) > 1 else "CANONICAL",
            )
        )
    return tuple(sorted(result, key=lambda item: str(item.slot_key)))
