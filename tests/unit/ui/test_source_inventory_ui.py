import json

from chart_observatory.ui.source_inventory import load_capabilities, load_manifests


def test_load_manifests_exposes_provider_platform_and_status(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "provider": "MGD",
                "origin_platform": "SPOTIFY",
                "files": [
                    {
                        "filename": "charts/br.csv",
                        "status": "IMPORTED",
                        "countries": ["BR"],
                        "row_count": 3,
                        "earliest_date": "2022-01-01",
                        "latest_date": "2022-01-03",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert load_manifests(manifest) == [
        {
            "provider": "MGD",
            "origin_platform": "SPOTIFY",
            "filename": "charts/br.csv",
            "status": "IMPORTED",
            "countries": "BR",
            "row_count": "3",
            "earliest_date": "2022-01-01",
            "latest_date": "2022-01-03",
        }
    ]


def test_load_capabilities_keeps_unavailable_source_rows_visible(tmp_path) -> None:
    capabilities = tmp_path / "capabilities.csv"
    capabilities.write_text(
        "provider,origin_platform,country_code,available\n"
        "CHARTMETRIC,SPOTIFY,BR,True\n"
        "CHARTMETRIC,AMAZON,GLOBAL,False\n",
        encoding="utf-8",
    )

    rows = load_capabilities(capabilities)

    assert [row["origin_platform"] for row in rows] == ["SPOTIFY", "AMAZON"]
    assert rows[1]["available"] == "False"
