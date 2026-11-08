import csv
import importlib.util
import json
from pathlib import Path

import pytest

from chart_observatory.ingestion.global_expansion import (
    african_ranking,
    apple_ranking,
    population_quota,
)


def fixture_html(positions=(1, 2), label="Top 100: Test"):
    items = [
        dict(
            title=f"Song {i}",
            artistName="Artist",
            rankingText=str(p),
            contentDescriptor=dict(
                kind="song",
                identifiers=dict(storeAdamID=str(i)),
                url=f"https://example.test/?i={i}",
            ),
        )
        for i, p in enumerate(positions, 100)
    ]
    schema = dict(
        name=label,
        numTracks=2,
        track=[dict(name=x["title"], url=x["contentDescriptor"]["url"]) for x in items],
    )
    data = dict(
        data=[
            dict(
                data=dict(
                    sections=[
                        dict(
                            itemKind="containerDetailHeaderLockup",
                            id="header - pl.test",
                            items=[dict(title=label)],
                        ),
                        dict(itemKind="trackLockup", id="tracks - pl.test", items=items),
                    ]
                )
            )
        ]
    )
    return (
        f'<script id="schema:music-playlist">{json.dumps(schema)}</script>'
        f'<script id="serialized-server-data">{json.dumps(data)}</script>'
    )


def test_quota_floor_ceiling_monotonic():
    assert population_quota(100, None) == 100
    assert population_quota(2_000_000_000, 1) == 500
    assert population_quota(200_000_000, 0.5) > population_quota(10_000_000, 0.5)
    for p in [100, 100000, 10000000, 200000000]:
        assert population_quota(p, None) % 10 == 0


@pytest.mark.parametrize("population,diversity", [(0, None), (-1, 0.5), (100, 2), (100, -0.1)])
def test_invalid_demographics(population, diversity):
    with pytest.raises(ValueError):
        population_quota(population, diversity)


def test_ordinal_evidence_never_authorizes_annual_or_paid_import():
    result = apple_ranking(fixture_html(), "Top 100: Test", "pl.test")
    assert [r["position"] for r in result["rows"]] == [1, 2]
    assert result["period_scope"] == "CURRENT_DAILY_SNAPSHOT"
    assert not any(
        result[k]
        for k in ["annual_rank_certified", "classification_ready", "lyrics_acquisition_ready"]
    )


@pytest.mark.parametrize(
    "positions,label,playlist",
    [
        ((1, 1), "Top 100: Test", "pl.test"),
        ((1, 3), "Top 100: Test", "pl.test"),
        ((1, 2), "Wrong country", "pl.test"),
        ((1, 2), "Top 100: Test", "pl.other"),
    ],
)
def test_identity_and_integrity_rejections(positions, label, playlist):
    with pytest.raises(ValueError):
        apple_ranking(fixture_html(positions), label, playlist)


def test_truncated_chart_rejected():
    with pytest.raises(ValueError):
        apple_ranking(fixture_html((1,)), "Top 100: Test", "pl.test")


def test_global_build_preserves_every_legacy_quota_and_is_reproducible(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "incorporation", root / "scripts/incorporate_global_rankings.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUT", tmp_path / "research")
    monkeypatch.setattr(module, "RUNTIME", tmp_path / "runtime")
    rows = module.build()
    original = (tmp_path / "research/campaign.json").read_bytes()
    module.build()
    assert (tmp_path / "research/campaign.json").read_bytes() == original
    assert len(rows) == 250
    by_code = {r["country_code"]: r for r in rows}
    legacy_path = (
        root
        / "data/derived/annual_revision"
        / "reconciled-russia-2018-2026-20261031/sources/country_quotas.csv"
    )
    with legacy_path.open(encoding="utf-8-sig") as f:
        old = list(csv.DictReader(f))
    assert len(old) == 68
    for row in old:
        assert by_code[row["country_code"]]["quota_per_year_main"] == int(
            row["quota_per_year_main"]
        )
    assert by_code["CN"]["population"] > 1_000_000_000
    assert by_code["AQ"]["quota_per_year_main"] is None
    assert by_code["PN"]["population_year"] == 2022
    assert not json.loads(original)["paid_calls_authorized"]


def test_nigeria_composite_rank_integrity_and_family():
    items = [
        dict(rank=i, title=f"Song {i}", artiste="Artist", id=i, musicLink="") for i in range(1, 101)
    ]
    data = dict(
        props=dict(
            pageProps=dict(
                chartData=dict(
                    category="Official Nigeria Top 100",
                    isDeleted=False,
                    dateCreated="2026-10-29T00:00:00",
                    chartItems=items,
                )
            )
        )
    )
    html = f'<script id="__NEXT_DATA__">{json.dumps(data)}</script>'
    result = african_ranking(html, "TURNTABLE_NG_COMPOSITE")
    assert len(result["rows"]) == 100
    assert result["comparability"] == "COMPOSITE_STREAMING_AND_AIRPLAY"
    assert not result["annual_rank_certified"]
    items[-1]["rank"] = 1
    with pytest.raises(ValueError):
        african_ranking(
            f'<script id="__NEXT_DATA__">{json.dumps(data)}</script>', "TURNTABLE_NG_COMPOSITE"
        )


def test_kenya_chart_excludes_recommendations():
    songs = "".join(
        f'<li class="str_off" data-element-type="song" data-element-id="{i}">'
        f'<a class="song-info" href="/song/{i}"><span class="song-title">Song {i}</span>'
        f'<span class="song-author">{i}. Artist</span></a></li>'
        for i in range(1, 101)
    )
    html = (
        f'<section class="song-list_section"><h1>Weekly Top 100 in Kenya</h1>'
        f'<ul>{songs}</ul></section><section class="song-list_section">'
        '<li class="str_off" data-element-type="song">Recommendation</li></section>'
    )
    result = african_ranking(html, "MDUNDO_KE_WEEKLY")
    assert len(result["rows"]) == 100
    assert result["source_published_at"] is None
    assert not result["annual_rank_certified"]
