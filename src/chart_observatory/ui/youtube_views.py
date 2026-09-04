from dataclasses import dataclass

from chart_observatory.adapters.youtube_data.mapper import VIEW_COUNT_DEFINITION_VERSION
from chart_observatory.charts.dto import ChartEntryDTO


@dataclass(frozen=True)
class YouTubeVideoChartView:
    country_code: str
    chart_label: str
    ranked_item_count: int
    video_category_id: str
    view_count_definition_version: str
    semantic_equivalence: str


def build_youtube_video_chart_view(
    country_code: str,
    video_category_id: str,
    entries: tuple[ChartEntryDTO, ...],
) -> YouTubeVideoChartView:
    return YouTubeVideoChartView(
        country_code=country_code.upper(),
        chart_label="YouTube Video Most Popular",
        ranked_item_count=len(entries),
        video_category_id=video_category_id,
        view_count_definition_version=VIEW_COUNT_DEFINITION_VERSION,
        semantic_equivalence="NOT_YOUTUBE_MUSIC_TOP_SONGS",
    )
