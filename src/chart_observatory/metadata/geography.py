from __future__ import annotations

from dataclasses import dataclass

import pycountry

SUBREGIONS: dict[str, str] = {
    **{code: "South America" for code in ("AR", "BO", "BR", "CL", "CO", "EC", "PY", "PE")},
    **{code: "Central America" for code in ("CR", "GT", "HN", "MX", "NI", "PA", "SV")},
    "DO": "Caribbean",
    **{code: "Northern America" for code in ("CA", "US")},
    **{code: "Western Europe" for code in ("AT", "BE", "CH", "DE", "FR", "LU", "NL")},
    **{code: "Eastern Europe" for code in ("BG", "CZ", "HU", "PL", "RO", "RU", "SK", "UA")},
    **{
        code: "Northern Europe"
        for code in ("DK", "EE", "FI", "GB", "IE", "IS", "LT", "LV", "NO", "SE")
    },
    **{code: "Southern Europe" for code in ("ES", "GR", "IT", "PT")},
    **{code: "Eastern Asia" for code in ("HK", "JP", "KR", "TW")},
    **{code: "South-eastern Asia" for code in ("ID", "MY", "PH", "SG", "TH", "VN")},
    "IN": "Southern Asia",
    **{code: "Western Asia" for code in ("AE", "IL", "SA", "TR")},
    **{code: "Northern Africa" for code in ("EG", "MA")},
    "ZA": "Sub-Saharan Africa",
    **{code: "Australia and New Zealand" for code in ("AU", "NZ")},
}


@dataclass(frozen=True)
class GeographyRecord:
    country_code: str
    iso3: str
    country_name: str
    m49: str
    region: str
    subregion: str
    intermediate_region: str | None
    source: str = "UN_M49_ISO_3166"
    source_version: str = "2026-09"


def geography_for_market(country_code: str) -> GeographyRecord:
    code = country_code.upper()
    if code == "GLOBAL":
        return GeographyRecord("GLOBAL", "GLB", "World", "001", "World", "World", None)
    country = pycountry.countries.get(alpha_2=code)
    if country is None:
        raise ValueError(f"unknown ISO-3166 alpha-2 market: {country_code}")
    subregion = SUBREGIONS.get(code)
    if subregion is None:
        raise ValueError(f"market has no configured UN M49 subregion: {country_code}")
    region = {
        "Africa": "Africa",
        "Americas": "Americas",
        "Asia": "Asia",
        "Europe": "Europe",
        "Oceania": "Oceania",
    }[
        "Africa"
        if subregion in {"Northern Africa", "Sub-Saharan Africa"}
        else "Americas"
        if subregion in {"South America", "Central America", "Caribbean", "Northern America"}
        else "Asia"
        if subregion in {"Eastern Asia", "South-eastern Asia", "Southern Asia", "Western Asia"}
        else "Oceania"
        if subregion == "Australia and New Zealand"
        else "Europe"
    ]
    intermediate = (
        "Southern Africa"
        if code == "ZA"
        else ("South America" if code in {"AR", "BO", "BR", "CL", "CO", "EC", "PY", "PE"} else None)
    )
    return GeographyRecord(
        country_code=code,
        iso3=country.alpha_3,
        country_name=country.name,
        m49=str(country.numeric).zfill(3),
        region=region,
        subregion=subregion,
        intermediate_region=intermediate,
    )
