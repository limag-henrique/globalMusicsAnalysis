from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class PresenceSummary:
    canonical_track_id: UUID
    countries: int
    platforms: int
    charted_items: int


def presence_summary(
    canonical_track_id: UUID, observations: list[tuple[str, str, str]]
) -> PresenceSummary:
    """Observations are (country, platform, platform_item_id); item multiplicity is retained."""
    return PresenceSummary(
        canonical_track_id,
        len({country for country, _, _ in observations}),
        len({platform for _, platform, _ in observations}),
        len({item for _, _, item in observations}),
    )
