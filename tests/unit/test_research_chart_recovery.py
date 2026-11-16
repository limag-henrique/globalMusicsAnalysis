import json
from types import SimpleNamespace

import pycountry
import pytest

from chart_observatory import research_chart_recovery as recovery


def help_html():
    names = [c.name for c in list(pycountry.countries)[:35]]
    return (
        "<p>YouTube Music Charts are available in regions:</p><ul>"
        + "".join(f"<li>{name}</li>" for name in names)
        + "</ul>"
    )


def test_market_directory_is_parsed_from_actual_list_not_headline_number():
    html = help_html().replace("available in regions", "available in 61 countries")
    result = recovery.markets_from_help(html)
    assert len(result) == 35
    assert "AF" in result


@pytest.mark.parametrize(
    "html",
    [
        "<html>Unknown</html>",
        "<p>YouTube Music Charts are available in regions</p>",
        "<p>YouTube Music Charts are available in regions</p><ul><li>Brazil</li></ul>",
    ],
)
def test_missing_or_short_market_directory_does_not_authorize_worldwide_collection(html):
    with pytest.raises(ValueError):
        recovery.markets_from_help(html)


def test_week_end_calendar_is_native_thursday_and_cutoff_bound():
    values = recovery.weeks(2026)
    assert values[0] == "2026-01-01"
    assert values[-1] == "2026-10-15"
    assert len(values) == 42
    assert recovery.weeks(2018)[0] == "2018-01-04"
    with pytest.raises(ValueError):
        recovery.weeks(2017)


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.google.com/recaptcha/enterprise/bframe?hl=en", True),
        ("https://www.google.com/recaptcha/api2/bframe?hl=en", True),
        ("https://www.google.com/recaptcha/enterprise/anchor?hl=en", False),
        ("https://example.com/recaptcha/enterprise/bframe", False),
        ("not a URL", False),
    ],
)
def test_interactive_recaptcha_frame_is_distinguished_from_normal_anchor(url, expected):
    assert recovery.is_recaptcha_challenge_frame_url(url) is expected


def test_interactive_recaptcha_frame_pauses_but_silent_anchor_does_not():
    challenge = SimpleNamespace(
        frames=[SimpleNamespace(url="https://www.google.com/recaptcha/enterprise/bframe?hl=en")]
    )
    silent_anchor = SimpleNamespace(
        frames=[SimpleNamespace(url="https://www.google.com/recaptcha/enterprise/anchor?hl=en")]
    )
    assert recovery.recaptcha_challenge_present(challenge)
    assert not recovery.recaptcha_challenge_present(silent_anchor)


def test_plan_preserves_unknown_countries_and_quota_applicability(tmp_path, monkeypatch):
    selection = tmp_path / "selection"
    selection.mkdir()
    (selection / "manifest.json").write_text("{}")
    cells = [
        dict(
            country_code=c,
            year=y,
            quota=q,
            selected_positions=0,
            missing_complete_annual_positions=q,
        )
        for c, q in (("BR", 100), ("KE", 100), ("AQ", None))
        for y in range(2018, 2027)
    ]
    monkeypatch.setattr(
        recovery,
        "load_selection",
        lambda _: (
            {"cutoff": "2026-10-15", "requested_positions": 1800},
            cells,
            [{"country_code": "BR"}],
            {},
        ),
    )
    result = recovery.build_plan(selection, {"KE": "Kenya"})
    assert len(result["tasks"]) == 9
    assert result["tasks"][0]["country_code"] == "KE"
    assert len(result["other_source_tasks"]) == 18
    reasons = {r["reason"] for r in result["other_source_tasks"]}
    assert reasons == {"quota_applicability_unresolved", "not_in_current_youtube_chart_directory"}
    assert result["catalog_capacity_percent"] == 50
    assert result["other_sources_may_exist"]
    assert not result["classification_ready"]
    assert all(not r["annual_rank_certified"] for r in result["tasks"])


def capture():
    return dict(
        country_code="KE",
        observed_country_code="KE",
        period_end="2026-01-08",
        observed_period_end="2026-01-08",
        source_url="https://charts.youtube.com/charts/TopSongs/ke/weekly/20260108",
        rows=[dict(rank=1, title="Synthetic", artist="Artist", metric_value=123)],
    )


def test_correct_week_capture_is_discovery_not_annual_or_recording_approval():
    result = recovery.validate_capture(capture())
    assert result["selection_status"] == "DISCOVERY_QUARANTINE"
    assert result["annual_rank_certified"] is False
    assert result["recording_identity_validated"] is False
    assert result["classification_ready"] is False
    assert result["rows"][0]["metric_value"] == 123


def test_missing_display_name_is_retained_as_identity_hold_not_missing_calendar():
    doc = capture()
    doc["rows"][0]["artist"] = ""
    result = recovery.validate_capture(doc)
    assert result["rows"][0]["metric_value"] == 123
    assert result["missing_display_positions"] == [1]
    assert result["annual_rank_certified"] is False


def test_native_chart_entity_is_retained_but_representative_video_is_not_recording_id():
    entry = recovery.normalize_native_entry(
        {
            "rank": 1,
            "source_rank": 1,
            "title": "Displayed Title",
            "artist": "Artist",
            "metric_text": "1,234",
            "native_rank": 1,
            "native_metric_value": 1234,
            "native_entity_title": "Native Title",
            "native_artist_names": "Artist",
            "native_artist_ids": [{"id": "/g/artist-1", "name": "Artist"}],
            "representative_video_url": "https://www.youtube.com/watch?v=abcdefghijk",
            "native_release_date": "2026-01-02",
        },
        lambda value: int(value.replace(",", "")),
    )
    assert entry["title"] == "Native Title"
    assert entry["rendered_title"] == "Displayed Title"
    assert entry["display_metadata_conflict"]
    assert entry["representative_video_id"] == "abcdefghijk"
    assert entry["representative_video_is_recording_id"] is False
    assert entry["recording_identity_validated"] is False


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("native_rank", 2, "rank differs"),
        ("native_metric_value", 999, "metric differs"),
    ],
)
def test_native_chart_entity_must_match_published_rank_and_metric(field, value, error):
    row = {
        "rank": 1,
        "source_rank": 1,
        "title": "Title",
        "artist": "Artist",
        "metric_text": "1,234",
        "native_rank": 1,
        "native_metric_value": 1234,
        "native_entity_title": "Title",
        "native_artist_names": "Artist",
    }
    row[field] = value
    with pytest.raises(ValueError, match=error):
        recovery.normalize_native_entry(row, lambda text: int(text.replace(",", "")))


def test_representative_video_id_parser_rejects_non_youtube_and_malformed_urls():
    assert recovery.representative_video_id("https://www.youtube.com/watch?v=abcdefghijk") == (
        "abcdefghijk"
    )
    assert recovery.representative_video_id("https://example.com/watch?v=abcdefghijk") is None
    assert recovery.representative_video_id("https://www.youtube.com/watch?v=short") is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_country_code", "US"),
        ("observed_period_end", "2026-10-15"),
        ("source_url", "https://charts.youtube.com/current"),
    ],
)
def test_current_or_other_market_cannot_replace_requested_historical_chart(field, value):
    doc = capture()
    doc[field] = value
    with pytest.raises(ValueError, match="another market or period"):
        recovery.validate_capture(doc)


@pytest.mark.parametrize("metric", [True, "123", -1, None])
def test_exact_nonnegative_integer_weekly_views_required(metric):
    doc = capture()
    doc["rows"][0]["metric_value"] = metric
    with pytest.raises(ValueError):
        recovery.validate_capture(doc)


def test_source_order_cannot_hide_published_rank_gaps():
    doc = capture()
    doc["rows"].append({**doc["rows"][0], "rank": 3})
    with pytest.raises(ValueError, match="ranks"):
        recovery.validate_capture(doc)


def test_resume_rejects_changed_selection_before_network(tmp_path):
    project = tmp_path / "project"
    selection, state = project / "selection", project / "data/runtime/recovery"
    selection.mkdir(parents=True)
    state.mkdir(parents=True)
    (selection / "manifest.json").write_text("{}")
    (state / "campaign.json").write_text(json.dumps({"selection_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="another frozen selection"):
        recovery.initialize_campaign(project=project, selection=selection, state=state)


def test_resume_preserves_source_hash_contract(tmp_path):
    project = tmp_path / "project"
    selection, state = project / "selection", project / "data/runtime/recovery"
    selection.mkdir(parents=True)
    state.mkdir(parents=True)
    source = project / "source"
    source.write_text("changed")
    (selection / "manifest.json").write_text("{}")
    (state / "campaign.json").write_text(
        json.dumps(
            {
                "selection_sha256": recovery.file_hash(selection / "manifest.json"),
                "input_hashes": {str(source): "0" * 64},
            }
        )
    )
    with pytest.raises(ValueError, match="input changed"):
        recovery.initialize_campaign(project=project, selection=selection, state=state)


def test_campaign_output_cannot_escape_private_runtime(tmp_path):
    with pytest.raises(ValueError, match="runtime"):
        recovery.initialize_campaign(
            project=tmp_path, selection=tmp_path, state=tmp_path / "outside"
        )
