"""Annual article selection; never compare streams with video views."""

import json
import unicodedata
from collections import defaultdict
from datetime import date


def song_key(title, artist):
    return tuple(
        " ".join(unicodedata.normalize("NFKC", v).casefold().split()) for v in (title, artist)
    )


def native_item_id(row):
    value = row.get("native_id")
    if isinstance(value, str) and value.strip() and not value.startswith("web-derived:"):
        return value
    return None


def observation_key(row):
    native = native_item_id(row)
    return ("native", native) if native else ("metadata", *song_key(row["title"], row["artist"]))


def select_annual(captures, expected, *, candidate_limit=80, include_comparison=False):
    """Select at most 80 per market/year, only from complete metric calendars.

    expected maps (market, year, platform) to the required period-end dates.
    Conflicting copies invalidate a period instead of double-counting it.
    """
    if not 1 <= candidate_limit <= 200:
        raise ValueError("candidate_limit must be between 1 and 200")
    periods = {}
    conflicts = set()
    for doc in captures:
        platform = doc["provider"]
        if platform not in ("SPOTIFY", "YOUTUBE"):
            continue
        end = doc["period_end"]
        year = date.fromisoformat(end).year
        group = (doc["country_code"], year, platform)
        if end not in expected.get(group, set()):
            continue
        rows = doc["rows"]
        if not rows or any(
            type(r.get("metric_value")) is not int
            or r["metric_value"] < 0
            or not isinstance(r.get("title"), str)
            or not r["title"].strip()
            or not isinstance(r.get("artist"), str)
            for r in rows
        ):
            continue
        keys = [observation_key(r) for r in rows]
        # Repeated real platform IDs within a single chart are contradictory rows.
        native_keys = [key for key in keys if key[0] == "native"]
        if len(set(native_keys)) != len(native_keys):
            continue
        # Metadata-only aggregation is a provisional popularity candidate, never
        # proof of recording or textual equivalence. Real item IDs stay distinct.
        key = (*group, end)
        signature = json.dumps(
            sorted((k, song_key(r["title"], r["artist"]), r["metric_value"])
                   for k, r in zip(keys, rows, strict=True)),
            ensure_ascii=False,
        )
        if key in periods and periods[key][0] != signature:
            conflicts.add(key)
        else:
            periods[key] = (signature, doc)
    available = defaultdict(dict)
    for key, (_, doc) in periods.items():
        if key not in conflicts:
            available[key[:3]][key[3]] = doc
    selections, coverage = [], []
    markets = sorted({(c, y) for c, y, _ in expected})
    for country, year in markets:
        chosen = []
        for platform in ("SPOTIFY", "YOUTUBE"):
            group = country, year, platform
            required = expected.get(group, set())
            saved = available[group]
            complete = bool(required) and set(saved) == set(required)
            coverage.append(
                dict(
                    country=country,
                    year=year,
                    platform=platform,
                    expected_periods=len(required),
                    collected_periods=len(saved),
                    status="COMPLETE" if complete else "INCOMPLETE",
                )
            )
            if complete and (include_comparison or not chosen):
                chosen.append(platform)
        for platform in chosen:
            totals = {}
            for doc in available[country, year, platform].values():
                for row in doc["rows"]:
                    key = observation_key(row)
                    item = totals.setdefault(
                        key, dict(title=row["title"], artist=row["artist"], metric_value=0)
                    )
                    item["metric_value"] += row["metric_value"]
                    if native_item_id(row):
                        item["native_id"] = native_item_id(row)
            ranked = sorted(
                totals.values(),
                key=lambda r: (-r["metric_value"], song_key(r["title"], r["artist"]),
                               r.get("native_id", ""))
            )[:candidate_limit]
            for position, row in enumerate(ranked, 1):
                selections.append(
                    dict(country_code=country, year=year, platform=platform,
                         position=position, **row)
                )
    return dict(selections=selections, coverage=coverage)
