"""Reproducible contextual indicators; no inferred visits or synthetic measurements."""

# ruff: noqa: B008

import csv
import hashlib
import io
import json
import math
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
import typer
from pydantic_settings import BaseSettings, SettingsConfigDict


class RadarCredentials(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    cloudflare_api_token: str | None = None


COUNTRY_LANGUAGES = {
    "AD": "ca es",
    "AE": "ar en",
    "AR": "es",
    "AT": "de",
    "AU": "en",
    "BE": "nl fr de",
    "BG": "bg",
    "BO": "es",
    "BR": "pt",
    "CA": "en fr",
    "CH": "de fr it",
    "CL": "es",
    "CO": "es",
    "CR": "es",
    "CZ": "cs",
    "DE": "de",
    "DK": "da",
    "DO": "es",
    "EC": "es",
    "EE": "et",
    "EG": "ar",
    "ES": "es ca",
    "FI": "fi sv",
    "FR": "fr",
    "GB": "en",
    "GR": "el",
    "GT": "es",
    "HN": "es",
    "HU": "hu",
    "ID": "id",
    "IE": "en ga",
    "IL": "he ar",
    "IN": "hi en bn ta te mr",
    "IS": "is",
    "IT": "it",
    "JP": "ja",
    "KR": "ko",
    "LT": "lt",
    "LU": "lb fr de",
    "LV": "lv",
    "MA": "ar fr",
    "MX": "es",
    "MY": "ms en zh ta",
    "NI": "es",
    "NL": "nl",
    "NO": "no",
    "NZ": "en mi",
    "PA": "es",
    "PE": "es",
    "PH": "fil en",
    "PL": "pl",
    "PT": "pt",
    "PY": "es gn",
    "RO": "ro",
    "RU": "ru",
    "SA": "ar",
    "SE": "sv",
    "SG": "en zh ms ta",
    "SK": "sk",
    "SV": "es",
    "TH": "th",
    "TR": "tr",
    "TW": "zh-Hant",
    "UA": "uk ru",
    "US": "en es",
    "UY": "es",
    "VN": "vi",
    "ZA": "en af zu xh",
}
# Initial search vocabulary, intentionally not represented as validated translations.
TERMS = {
    "en": ["porn", "pornography", "porn videos"],
    "pt": ["pornografia", "vídeos pornô"],
    "es": ["pornografía", "videos porno"],
    "ca": ["pornografia", "vídeos porno"],
    "fr": ["pornographie", "vidéos porno"],
    "de": ["Pornografie", "Pornovideos"],
    "nl": ["pornografie", "pornovideo"],
    "it": ["pornografia", "video porno"],
    "ar": ["إباحية", "أفلام إباحية"],
    "bg": ["порно", "порнография"],
    "cs": ["porno", "pornografie"],
    "da": ["porno", "pornografi"],
    "et": ["porno", "pornograafia"],
    "fi": ["porno", "pornografia"],
    "sv": ["porr", "pornografi"],
    "el": ["πορνό", "πορνογραφία"],
    "hu": ["pornó", "pornográfia"],
    "id": ["pornografi", "video porno"],
    "he": ["פורנו", "פורנוגרפיה"],
    "hi": ["पोर्न", "अश्लील वीडियो"],
    "bn": ["পর্ন", "পর্নোগ্রাফি"],
    "ta": ["ஆபாசம்", "ஆபாச வீடியோ"],
    "te": ["పోర్న్", "అశ్లీల వీడియోలు"],
    "mr": ["पॉर्न", "अश्लील व्हिडिओ"],
    "is": ["klám", "klámmyndir"],
    "ja": ["ポルノ", "アダルト動画"],
    "ko": ["포르노", "야동"],
    "lt": ["pornografija", "porno"],
    "lv": ["pornogrāfija", "porno"],
    "ms": ["pornografi", "video lucah"],
    "zh": ["色情", "色情影片"],
    "zh-Hant": ["色情", "色情影片"],
    "no": ["porno", "pornografi"],
    "fil": ["pornograpiya", "malaswang video"],
    "pl": ["pornografia", "porno"],
    "ro": ["pornografie", "filme porno"],
    "ru": ["порно", "порнография"],
    "sk": ["porno", "pornografia"],
    "th": ["หนังโป๊", "สื่อลามก"],
    "tr": ["porno", "pornografi"],
    "uk": ["порно", "порнографія"],
    "vi": ["phim sex", "phim khiêu dâm"],
    "af": ["pornografie", "pornografiese video's"],
}
DOMAINS = ("pornhub.com", "xvideos.com", "xnxx.com")
FIELDS = [
    "query_id",
    "country_iso2",
    "year",
    "period_start",
    "period_end",
    "scope",
    "source",
    "term",
    "language",
    "domain",
    "value",
    "status",
    "scale",
    "cross_country_comparable",
    "sample_date",
    "raw_value",
    "raw_sha256",
    "source_url",
    "retrieved_at",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, records: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def _plan(annual: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    with annual.open(encoding="utf-8-sig", newline="") as handle:
        pairs = sorted(
            {
                (r["market_code"], int(r["year"]))
                for r in csv.DictReader(handle)
                if r["market_code"] not in {"GLOBAL", "HK", "PR"}
            }
        )
    plan = []
    gaps = []
    for country, year in pairs:
        if country not in COUNTRY_LANGUAGES:
            raise ValueError(f"No language policy for market {country}")
        start = f"{year}-01-01"
        end = "2022-03-13" if year == 2022 else f"{year}-12-31"
        for language in dict.fromkeys(["en", *COUNTRY_LANGUAGES[country].split()]):
            if language not in TERMS:
                gaps.append(
                    {
                        "country_iso2": country,
                        "language": language,
                        "status": "needs_native_vocabulary",
                    }
                )
            for term in TERMS.get(language, []):
                identity = f"{country}|{start}|{end}|{language}|{term}"
                plan.append(
                    {
                        "query_id": hashlib.sha256(identity.encode()).hexdigest()[:20],
                        "country_iso2": country,
                        "year": year,
                        "period_start": start,
                        "period_end": end,
                        "scope": "corpus_history",
                        "source": "google_trends_export",
                        "term": term,
                        "language": language,
                        "domain": "",
                        "value": "",
                        "status": "missing_input",
                        "scale": "google_trends_local_0_100",
                        "cross_country_comparable": "false",
                        "sample_date": "",
                        "raw_value": "",
                        "raw_sha256": "",
                        "retrieved_at": "",
                        "source_url": "https://trends.google.com/trends/explore?"
                        + urlencode({"date": f"{start} {end}", "geo": country, "q": term}),
                        "lexicon_status": "candidate_requires_review",
                    }
                )
    return plan, list({(g["country_iso2"], g["language"]): g for g in gaps}.values())


def _import_trends(manifest: Path, plan: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    queries = {r["query_id"]: r for r in plan}
    imported: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        query_id = entry["query_id"]
        if query_id not in queries or query_id in imported:
            raise ValueError(f"Unknown or duplicate query_id: {query_id}")
        query = queries[query_id]
        raw = manifest.parent / entry["path"]
        digest = _sha(raw)
        if digest != entry["sha256"]:
            raise ValueError(f"Input hash mismatch: {query_id}")
        if entry["source_url"] != query["source_url"]:
            raise ValueError(f"Source URL must match planned country, term and period: {query_id}")
        datetime.fromisoformat(entry["exported_at"].replace("Z", "+00:00"))
        text = raw.read_text(encoding="utf-8-sig")
        lines = text.splitlines()
        date_column, value_column = entry["date_column"], entry["value_column"]
        header = next(
            (
                i
                for i, line in enumerate(lines)
                if date_column in next(csv.reader([line]), [])
                and value_column in next(csv.reader([line]), [])
            ),
            None,
        )
        if header is None:
            raise ValueError(f"Google Trends CSV header not found: {query_id}")
        records = []
        for row in csv.DictReader(io.StringIO("\n".join(lines[header:]))):
            sample = date.fromisoformat(row[date_column])
            if (
                not date.fromisoformat(query["period_start"])
                <= sample
                <= date.fromisoformat(query["period_end"])
            ):
                raise ValueError(f"Sample outside planned period: {query_id}")
            raw_value = row[value_column].strip()
            value: str | float = ""
            status = "observed_relative_index"
            if raw_value == "<1":
                status = "below_reporting_threshold"
            elif raw_value in {"", "N/A", "NA"}:
                status = "missing_input"
            else:
                value = float(raw_value)
                if not math.isfinite(value) or not 0 <= value <= 100:
                    raise ValueError(f"Invalid Trends index: {query_id}")
            records.append(
                {
                    **query,
                    "sample_date": sample.isoformat(),
                    "value": value,
                    "raw_value": raw_value,
                    "status": status,
                    "raw_sha256": digest,
                    "retrieved_at": entry["exported_at"],
                }
            )
        if not records:
            raise ValueError(f"Empty Trends export: {query_id}")
        imported[query_id] = records
    return imported


def export_context(
    annual: Path,
    output: Path,
    *,
    trends_manifest: Path | None = None,
    radar_token: str | None = None,
    radar_start: str | None = None,
    radar_end: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Export measured observations and explicit gaps; Radar's dateEnd is inclusive."""
    plan, gaps = _plan(annual)
    imported = _import_trends(trends_manifest, plan) if trends_manifest else {}
    indicators = [record for query in plan for record in imported.get(query["query_id"], [query])]
    countries = sorted({r["country_iso2"] for r in plan})
    if bool(radar_start) != bool(radar_end):
        raise ValueError("Provide both radar_start and radar_end")
    if radar_token and not radar_start:
        raise ValueError("Explicit Radar period required")
    if radar_start and radar_end:
        duration = (date.fromisoformat(radar_end) - date.fromisoformat(radar_start)).days
        if not 0 < duration <= 31:
            raise ValueError("Radar domain window must be between 1 and 31 days")
    output.mkdir(parents=True, exist_ok=True)
    if trends_manifest:
        raw_dir = output / "raw"
        raw_dir.mkdir(exist_ok=True)
        for entry in json.loads(trends_manifest.read_text(encoding="utf-8")):
            target = raw_dir / f"trends-{entry['query_id']}.csv"
            source = trends_manifest.parent / entry["path"]
            if target.resolve() != source.resolve():
                shutil.copyfile(source, target)
    # Credentials are only transmitted to Cloudflare, never saved in artifacts.
    for domain in DOMAINS:
        values: dict[str, Any] = {}
        digest, retrieved = "", ""
        status = "missing_input"
        url = "https://api.cloudflare.com/client/v4/radar/dns/top/locations"
        metadata: dict[str, Any] = {}
        if radar_token and radar_start and radar_end:
            params = {
                "domain": domain,
                "dateStart": radar_start + "T00:00:00Z",
                "dateEnd": radar_end + "T00:00:00Z",
                "format": "JSON",
                "limit": "200",
            }
            headers = {"Authorization": f"Bearer {radar_token}"}
            if client is None:
                with httpx.Client(timeout=30) as owned:
                    response = owned.get(url, params=params, headers=headers)
            else:
                response = client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
            if payload.get("success") is not True:
                raise ValueError(f"Radar query unsuccessful for {domain}")
            result = payload["result"]
            metadata = result["meta"]
            if metadata.get("normalization") != "PERCENTAGE":
                raise ValueError("Radar normalization must be PERCENTAGE")
            expected = {
                "startTime": radar_start + "T00:00:00Z",
                "endTime": radar_end + "T00:00:00Z",
            }
            actual = metadata["dateRange"][0]
            if any(
                datetime.fromisoformat(actual[k].replace("Z", "+00:00"))
                != datetime.fromisoformat(v.replace("Z", "+00:00"))
                for k, v in expected.items()
            ):
                raise ValueError("Radar response period differs from requested period")
            for record in result["top_0"]:
                value = float(record["value"])
                if not math.isfinite(value) or not 0 <= value <= 100:
                    raise ValueError("Invalid Radar percentage")
                values[record["clientCountryAlpha2"]] = value
            raw_dir = output / "raw"
            raw_dir.mkdir(exist_ok=True)
            raw_path = raw_dir / f"radar-{domain}-{radar_start}-{radar_end}.json"
            raw_path.write_bytes(response.content)
            digest = _sha(raw_path)
            retrieved = datetime.now(UTC).isoformat()
            status = "not_returned"
        for country in countries:
            indicators.append(
                {
                    "query_id": f"radar:{domain}:{country}:{radar_start}:{radar_end}",
                    "country_iso2": country,
                    "year": "",
                    "period_start": radar_start or "",
                    "period_end": radar_end or "",
                    "scope": "recent",
                    "source": "cloudflare_radar",
                    "term": "",
                    "language": "",
                    "domain": domain,
                    "value": values.get(country, ""),
                    "status": "observed_dns_share" if country in values else status,
                    "scale": "dns_domain_country_share_percent",
                    "cross_country_comparable": "true" if country in values else "false",
                    "raw_sha256": digest,
                    "source_url": url,
                    "retrieved_at": retrieved,
                }
            )
    _write(output / "query-plan.csv", plan, [*FIELDS, "lexicon_status"])
    _write(output / "language-gaps.csv", gaps, ["country_iso2", "language", "status"])
    _write(output / "indicators.csv", indicators, FIELDS)
    manifest_data = {
        "schema_version": "country-context-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "countries": countries,
        "query_count": len(plan),
        "imported_queries": len(imported),
        "annual_input": {"path": str(annual.resolve()), "sha256": _sha(annual)},
        "trends_manifest_sha256": _sha(trends_manifest) if trends_manifest else None,
        "radar_period_end_inclusive": True,
        "outputs": {p.name: _sha(p) for p in output.glob("*.csv")},
        "limitations": [
            "Local Trends indices cannot rank countries or be summed across queries",
            "Trends zero may represent low volume; <1 remains censored",
            "Exports contain supplied samples; full-year coverage is not guaranteed",
            "DNS is 1.1.1.1 resolver geography, not visits or internet-user prevalence",
            "Domains are an initial panel, not the whole adult industry",
            "Vocabulary requires native review; language gaps remain explicit",
            "Recent context must not be joined to historical charts as contemporaneous",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest_data


app = typer.Typer(help="Export country context from original Trends CSVs and Cloudflare Radar.")


@app.command()
def export(
    annual: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(...),
    trends_manifest: Path | None = typer.Option(None, exists=True, dir_okay=False),
    radar_start: str | None = None,
    radar_end: str | None = None,
    collect_radar: bool = False,
) -> None:
    """Build plan and missingness CSV; optionally import exports and collect DNS."""
    token = RadarCredentials().cloudflare_api_token if collect_radar else None
    if collect_radar and not token:
        raise typer.BadParameter("CLOUDFLARE_API_TOKEN required for --collect-radar")
    try:
        result = export_context(
            annual,
            output,
            trends_manifest=trends_manifest,
            radar_token=token,
            radar_start=radar_start,
            radar_end=radar_end,
        )
    except (ValueError, KeyError, httpx.HTTPError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        json.dumps(
            {
                "countries": len(result["countries"]),
                "planned_queries": result["query_count"],
                "imported_queries": result["imported_queries"],
            }
        )
    )


@app.command("collect-trends")
def collect_trends_command(
    annual: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(...),
    limit: int | None = typer.Option(None, min=1),
    interval: float = typer.Option(8, min=1),
) -> None:
    """Collect the public website endpoints; resume checkpoints, stop on rejection."""
    from chart_observatory.analysis.trends_automation import collect_trends

    typer.echo(json.dumps(collect_trends(annual, output, limit=limit, interval=interval)))


@app.command("trends-browser")
def trends_browser_command(
    annual: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(...),
    downloads: Path | None = typer.Option(None, exists=True, dir_okay=False),
) -> None:
    """Prepare native/English browser batches and import original downloaded CSVs."""
    from chart_observatory.analysis.trends_browser import export_browser_results

    entries = json.loads(downloads.read_text(encoding="utf-8")) if downloads else []
    typer.echo(json.dumps(export_browser_results(annual, output, entries)))


@app.command("historical-panel")
def historical_panel_command(
    annual: Path = typer.Option(..., exists=True, dir_okay=False),
    trends: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(...),
    context: Path | None = typer.Option(None, exists=True, dir_okay=False),
) -> None:
    """Build annual local trajectories and exploratory within-country models."""
    from chart_observatory.analysis.historical_report import build_historical_report

    typer.echo(json.dumps(build_historical_report(annual, trends, output, context=context)))


@app.command("traffic-pilot")
def traffic_pilot_command(
    annual: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(...),
    collect: bool = False,
    limit: int = typer.Option(1, min=1),
) -> None:
    """Plan commercial traffic; --collect explicitly requests bounded API calls."""
    import polars as pl

    from chart_observatory.analysis.traffic_pilot import export_traffic_pilot

    class TrafficCredentials(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", extra="ignore")
        semrush_api_key: str | None = None

    try:
        result = export_traffic_pilot(
            pl.read_csv(annual), output, collect=collect, limit=limit,
            api_key=TrafficCredentials().semrush_api_key,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
    typer.echo(json.dumps(result))


if __name__ == "__main__":
    app()
