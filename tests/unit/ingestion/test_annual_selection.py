from chart_observatory.ingestion.annual_selection import select_annual


def capture(provider, day, rows):
    return dict(
        provider=provider,
        country_code="BR",
        period_start=day,
        period_end=day,
        source_url="https://example.test/chart",
        rows=rows,
    )


def test_spotify_precedence_order_cap_and_duplicate_periods():
    rows = [dict(title=f"Song {i:03}", artist="Artist", metric_value=i) for i in range(100)]
    spotify = capture("SPOTIFY", "2025-01-01", rows)
    youtube = capture(
        "YOUTUBE", "2025-01-01", [dict(title="Other", artist="A", metric_value=99999)]
    )
    result = select_annual(
        [spotify, spotify, youtube],
        {("BR", 2025, "SPOTIFY"): {"2025-01-01"}, ("BR", 2025, "YOUTUBE"): {"2025-01-01"}},
    )
    selected = result["selections"]
    assert len(selected) == 80
    assert selected[0]["title"] == "Song 099"
    assert selected[0]["metric_value"] == 99
    assert selected[-1]["position"] == 80
    assert all(r["platform"] == "SPOTIFY" for r in selected)


def test_complete_youtube_wins_over_incomplete_spotify_without_mixing_metrics():
    expected = {("BR", 2025, p): {"2025-01-01", "2025-01-08"} for p in ("SPOTIFY", "YOUTUBE")}
    docs = [capture("SPOTIFY", "2025-01-01", [dict(title="S", artist="A", metric_value=999)])]
    docs += [
        capture("YOUTUBE", d, [dict(title="Y", artist="A", metric_value=20)])
        for d in expected["BR", 2025, "YOUTUBE"]
    ]
    result = select_annual(docs, expected)
    assert result["selections"] == [
        dict(
            country_code="BR",
            year=2025,
            platform="YOUTUBE",
            position=1,
            title="Y",
            artist="A",
            metric_value=40,
        )
    ]


def test_missing_metrics_and_conflicting_periods_do_not_publish_annual_ranking():
    expected = {("BR", 2025, "SPOTIFY"): {"2025-01-01"}}
    first = capture("SPOTIFY", "2025-01-01", [dict(title="S", artist="A", metric_value=10)])
    conflict = capture("SPOTIFY", "2025-01-01", [dict(title="S", artist="A", metric_value=20)])
    assert select_annual([first, conflict], expected)["selections"] == []
    missing = capture("SPOTIFY", "2025-01-01", [dict(title="S", artist="A")])
    assert select_annual([missing], expected)["selections"] == []


def test_distinct_chart_rows_for_same_song_are_combined_into_one_annual_song():
    expected = {("BR", 2025, "YOUTUBE"): {"2025-01-01"}}
    doc = capture(
        "YOUTUBE",
        "2025-01-01",
        [
            dict(title="Song", artist="Artist", metric_value=10),
            dict(title="Song", artist="Artist", metric_value=20),
        ],
    )
    result = select_annual([doc, doc], expected)["selections"]
    assert len(result) == 1
    assert result[0]["metric_value"] == 30


def test_revision_retains_both_platforms_and_popularity_reserves():
    expected = {("BR", 2025, p): {"2025-01-01"} for p in ("SPOTIFY", "YOUTUBE")}
    rows = [dict(title=f"Song {i:03}", artist="Artist", metric_value=i) for i in range(130)]
    result = select_annual(
        [capture(p, "2025-01-01", rows) for p in ("SPOTIFY", "YOUTUBE")],
        expected, candidate_limit=120, include_comparison=True,
    )
    assert len(result["selections"]) == 240
    for platform in ("SPOTIFY", "YOUTUBE"):
        selected = [r for r in result["selections"] if r["platform"] == platform]
        assert selected[0]["title"] == "Song 129"
        assert selected[-1]["position"] == 120


def test_equal_names_with_different_real_platform_ids_are_not_merged():
    expected = {("BR", 2025, "YOUTUBE"): {"2025-01-01"}}
    rows = [dict(title="Same title", artist="Same artist", native_id=native, metric_value=value)
            for native, value in [("song-original", 10), ("song-remix", 20)]]
    selected = select_annual([capture("YOUTUBE", "2025-01-01", rows)], expected)["selections"]
    assert len(selected) == 2
    assert [r["native_id"] for r in selected] == ["song-remix", "song-original"]
    assert [r["metric_value"] for r in selected] == [20, 10]
