from datetime import date

from chart_observatory.sources.promusica import (
    ProMusicaBrasilSource,
    ProMusicaHtmlParser,
    period_from_html,
)


def test_promusica_date_range_requires_review_instead_of_silent_fix() -> None:
    review = ProMusicaBrasilSource.review_period(date(2027, 11, 1), date(2026, 8, 31))
    assert review.status == "CONFIGURATION_REQUIRES_REVIEW"


def test_promusica_parser_keeps_multi_platform_origin() -> None:
    raw = (
        "<table><tr><th>Rank</th><th>Track</th><th>Artist</th></tr>"
        "<tr><td>1</td><td>Song</td><td>Artist</td></tr></table>"
    )
    rows = ProMusicaHtmlParser().parse(raw, period=date(2026, 8, 1), source_document="doc.html")
    assert rows[0].provider == "PRO_MUSICA_BRASIL"
    assert rows[0].origin_platform == "MULTI_PLATFORM_AGGREGATE"


def test_promusica_inventory_is_domain_restricted() -> None:
    source = ProMusicaBrasilSource()
    items = source.inventory_from_html(
        '<a href="/home-2/top-50-streaming/">Top 50</a><a href="https://evil.example/chart.pdf">bad</a>'
    )
    assert len(items) == 1
    assert items[0].chart_type == "TOP_50_STREAMING"


def test_period_is_read_from_portuguese_chart_heading() -> None:
    assert period_from_html("<h2>AGOSTO DE 2026</h2>", date(2026, 9, 1)) == date(2026, 8, 1)
