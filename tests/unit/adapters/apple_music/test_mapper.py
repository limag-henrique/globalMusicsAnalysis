from datetime import UTC, datetime
from pathlib import Path

from chart_observatory.adapters.apple_music.mapper import map_chart_payload

FIXTURE = Path(__file__).parents[3] / "fixtures" / "apple_music" / "charts_songs_br.json"


def test_apple_mapping_preserves_identity_and_does_not_invent_period() -> None:
    observed = datetime(2026, 9, 3, tzinfo=UTC)
    mapped = map_chart_payload(FIXTURE.read_bytes(), "br", observed)
    assert mapped.observed_at == observed
    assert mapped.period_start is None
    assert mapped.period_end is None
    assert mapped.entries[0].native_id == "apple-1"
    assert mapped.entries[0].raw_fields["isrc"] == "BRABC2100001"
    assert mapped.entries[0].raw_fields["genreNames"] == ["Pop"]
