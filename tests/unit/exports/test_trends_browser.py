import csv
from pathlib import Path

from chart_observatory.analysis.trends_browser import export_browser_results, prepare_browser_queue


def test_original_browser_export_preserves_shared_scale_and_country_year(tmp_path: Path) -> None:
    annual = tmp_path / "annual.csv"
    annual.write_text("market_code,year\nBR,2020\nBR,2021\n", encoding="utf-8")
    queue = prepare_browser_queue(annual, tmp_path / "out")
    assert len(queue) == 1
    assert set(queue[0]["terms"]) == {
        "porn",
        "pornography",
        "porn videos",
        "pornografia",
        "vídeos pornô",
    }
    raw = tmp_path / "export.csv"
    raw.write_text(
        "Categoria: Todas as categorias\n\n"
        "Mês,porn: (Brasil),pornography: (Brasil),porn videos: (Brasil),"
        "pornografia: (Brasil),vídeos pornô: (Brasil)\n"
        "2020-01,0,10,20,30,<1\n2021-01,50,40,30,20,10\n",
        encoding="utf-8",
    )
    result = export_browser_results(
        annual, tmp_path / "out", [{"batch_id": queue[0]["batch_id"], "path": str(raw)}]
    )
    assert result["completed_batches"] == 1
    with (tmp_path / "out/trends-browser-observations.csv").open(encoding="utf-8-sig") as handle:
        records = list(csv.DictReader(handle))
    observed = [r for r in records if r["sample_date"]]
    assert len(observed) == 10
    assert {r["year"] for r in observed} == {"2020", "2021"}
    assert {r["language"] for r in observed} == {"en", "pt"}
    assert len({r["comparison_group"] for r in observed}) == 1
    assert any(r["value"] == "" and r["status"] == "below_reporting_threshold" for r in observed)
    assert all(r["cross_country_comparable"] == "false" for r in observed)


def test_partial_march_bucket_is_explicit(tmp_path: Path) -> None:
    annual = tmp_path / "annual.csv"
    annual.write_text("market_code,year\nBR,2022\n", encoding="utf-8")
    queue = prepare_browser_queue(annual, tmp_path / "out")
    raw = tmp_path / "export.csv"
    raw.write_text(
        "Mês,porn: (Brasil),pornography: (Brasil),porn videos: (Brasil),"
        "pornografia: (Brasil),vídeos pornô: (Brasil)\n"
        "2022-03,50,40,30,20,10\n",
        encoding="utf-8",
    )
    export_browser_results(
        annual, tmp_path / "out", [{"batch_id": queue[0]["batch_id"], "path": str(raw)}]
    )
    with (tmp_path / "out/trends-browser-observations.csv").open(encoding="utf-8-sig") as handle:
        assert all(r["boundary_bucket"] == "true" for r in csv.DictReader(handle))
