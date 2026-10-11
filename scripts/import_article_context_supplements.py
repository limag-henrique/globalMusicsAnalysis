"""Exact-reference-year OECD SIGI and UNODC context, without extra dependencies."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import httpx
import pycountry

SIGI_URL = "https://sdmx.oecd.org/archive/rest/v1/data/OECD,DF_SIGI2019,/all?format=csvfile"
HOMICIDE_URL = "https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/data_cts_intentional_homicide.xlsx"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
INDICATORS = [
    "sigi_2019",
    "homicide_unodc_total",
    "homicide_unodc_female",
    "homicide_unodc_female_intimate_partner_family",
    "homicide_unodc_female_intimate_partner",
]


def _raw(root, filename, url):
    path = root / "data/raw/country_context/source-discovery" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    if path.exists() and sidecar.exists():
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        if (
            meta.get("source_url") != url
            or meta.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            raise ValueError(f"Invalid raw cache: {path}")
        return path, meta
    # Re-fetch previously discovered files lacking collection timestamps.
    response = httpx.get(url, follow_redirects=True, timeout=120)
    response.raise_for_status()
    path.write_bytes(response.content)
    meta = {
        "source_url": url,
        "resolved_url": str(response.url),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "raw_path": str(path.relative_to(root)),
        "bytes": len(response.content),
        "status_code": response.status_code,
    }
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path, meta


def _xlsx_rows(path):
    """Read first official worksheet, resolving XLSX shared strings with stdlib."""
    with ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            tree = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(si.itertext()) for si in tree.findall(NS + "si")]
        with archive.open("xl/worksheets/sheet1.xml") as stream:
            header = None
            for _, elem in ET.iterparse(stream, events=("end",)):
                if elem.tag != NS + "row":
                    continue
                values = [None] * 13
                for cell in elem.findall(NS + "c"):
                    letters = "".join(c for c in cell.attrib["r"] if c.isalpha())
                    index = 0
                    for letter in letters:
                        index = index * 26 + ord(letter) - 64
                    value = cell.findtext(NS + "v")
                    if cell.attrib.get("t") == "s" and value is not None:
                        value = strings[int(value)]
                    elif cell.attrib.get("t") == "inlineStr":
                        value = "".join(cell.find(NS + "is").itertext())
                    if index <= len(values):
                        values[index - 1] = value
                if elem.attrib.get("r") == "3":
                    header = values
                    if header[:2] != ["Iso3_code", "Country"]:
                        raise ValueError("Unexpected UNODC workbook schema")
                elif header is not None:
                    yield dict(zip(header, values, strict=True))
                elem.clear()


def load_supplements(root, pairs):
    """Return normalized records, raw-source manifests, and indicator names."""
    root = Path(root)
    pairs = set(pairs)
    iso = {market: pycountry.countries.get(alpha_2=market).alpha_3 for market, _ in pairs}
    records, manifests = [], []

    def emit(market, year, code, value, unit, source, meta, status=None, **extra):
        records.append(
            {
                "market_code": market,
                "country_iso3": iso[market],
                "reference_year": year,
                "indicator_code": code,
                "value": value,
                "unit": unit,
                "source": source,
                "source_url": meta.get("source_url"),
                "retrieved_at": meta.get("retrieved_at"),
                "raw_sha256": meta.get("sha256"),
                "raw_path": meta.get("raw_path"),
                "coverage_status": status
                or ("observed" if value is not None else "source_missing"),
                "methodology_version": "article-context-v1",
                **extra,
            }
        )

    try:
        path, meta = _raw(root, "oecd_sigi2019_index.csv", SIGI_URL)
        manifests.append(meta)
        values = {}
        for row in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))):
            if (row["REGION"], row["INCOME"], row["VAR"]) != ("ALL", "AIC", "SIGI_2"):
                continue
            key = (row["LOCATION"], int(row["TIME_PERIOD"]))
            if key in values:
                raise ValueError(f"Duplicate OECD observation {key}")
            values[key] = float(row["OBS_VALUE"]) if row["OBS_VALUE"] else None
        for market, year in sorted(pairs):
            value = values.get((iso[market], year)) if year == 2019 else None
            emit(
                market,
                year,
                "sigi_2019",
                value,
                "index_0_100",
                "OECD SIGI 2019",
                meta,
                status="not_survey_year" if year != 2019 else None,
                original_indicator_code="SIGI_2",
            )
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        manifests.append({"source_url": SIGI_URL, "error": str(exc), "status": "failed"})
        for market, year in sorted(pairs):
            emit(
                market,
                year,
                "sigi_2019",
                None,
                "index_0_100",
                "OECD SIGI 2019",
                {},
                status="not_survey_year" if year != 2019 else "source_unavailable",
            )

    definitions = {
        ("Total", "Total", "Total"): "homicide_unodc_total",
        ("Total", "Total", "Female"): "homicide_unodc_female",
        (
            "by relationship to perpetrator",
            "Intimate partner or family member",
            "Female",
        ): "homicide_unodc_female_intimate_partner_family",
        (
            "by relationship to perpetrator",
            "Intimate partner or family member: Intimate partner",
            "Female",
        ): "homicide_unodc_female_intimate_partner",
    }
    try:
        path, meta = _raw(root, "unodc_homicide_2026-07.xlsx", HOMICIDE_URL)
        manifests.append(meta)
        values = {}
        for row in _xlsx_rows(path):
            if (
                row["Indicator"] != "Victims of intentional homicide"
                or row["Age"] != "Total"
                or row["Unit of measurement"] != "Rate per 100,000 population"
            ):
                continue
            code = definitions.get((row["Dimension"], row["Category"], row["Sex"]))
            if code is None or row["Year"] is None:
                continue
            key = (row["Iso3_code"], int(float(row["Year"])), code)
            if key in values:
                raise ValueError(f"Duplicate UNODC observation {key}; source selection required")
            values[key] = (float(row["VALUE"]) if row["VALUE"] is not None else None, row["Source"])
        for market, year in sorted(pairs):
            for code in INDICATORS[1:]:
                value, provider = values.get((iso[market], year, code), (None, None))
                emit(
                    market,
                    year,
                    code,
                    value,
                    "per_100000_total_population"
                    if code == "homicide_unodc_total"
                    else "per_100000_female_population",
                    "UNODC UN-CTS",
                    meta,
                    original_source=provider,
                    original_unit="Rate per 100,000 population",
                    denominator_population="total" if code == "homicide_unodc_total" else "female",
                    metadata_url=(
                        "https://data.unodc.org/sites/dataportal.unodc.org/files/2026-07/"
                        "metadata_intentional_homicide.pdf"
                    ),
                )
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        manifests.append({"source_url": HOMICIDE_URL, "error": str(exc), "status": "failed"})
        for market, year in sorted(pairs):
            for code in INDICATORS[1:]:
                emit(
                    market,
                    year,
                    code,
                    None,
                    "per_100000_total_population"
                    if code == "homicide_unodc_total"
                    else "per_100000_female_population",
                    "UNODC UN-CTS",
                    {},
                    status="source_unavailable",
                )
    return records, manifests, INDICATORS.copy()
