from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from chart_observatory.db.base import Base
from chart_observatory.db.repositories.sources import SourceInventoryRepository
from chart_observatory.sources.models import MarketCapability, SourceManifest, SourceStatus


def test_inventory_persists_manifest_and_keeps_provider_separate_from_platform() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    manifest = SourceManifest(
        provider="SOUNDCHARTS",
        origin_platform="SPOTIFY",
        filename="spotify-br.csv",
        path=Path("data/raw/spotify-br.csv"),
        sha256="a" * 64,
        size_bytes=100,
        row_count=2,
        schema_version="v1",
        status=SourceStatus.IMPORTED,
        countries=("BR",),
        chart_types=("top200",),
        earliest_date=date(2022, 1, 1),
        latest_date=date(2022, 1, 2),
    )

    with Session(engine) as session:
        repository = SourceInventoryRepository(session)
        saved = repository.save_manifest(manifest)
        session.commit()

        rows = repository.list_manifests(provider="SOUNDCHARTS")

    assert saved.provider == "SOUNDCHARTS"
    assert saved.origin_platform == "SPOTIFY"
    assert len(rows) == 1
    assert rows[0].provider == "SOUNDCHARTS"
    assert rows[0].origin_platform == "SPOTIFY"


def test_inventory_is_idempotent_by_artifact_checksum() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    manifest = SourceManifest(
        provider="MGD",
        origin_platform="SPOTIFY",
        filename="charts/br.csv",
        path=Path("mgd/charts/br.csv"),
        sha256="b" * 64,
        size_bytes=50,
        row_count=1,
        schema_version="v1",
        status=SourceStatus.AVAILABLE,
        countries=("BR",),
    )

    with Session(engine) as session:
        repository = SourceInventoryRepository(session)
        first = repository.save_manifest(manifest)
        second = repository.save_manifest(manifest)
        session.commit()

        assert first.id == second.id
        assert len(repository.list_manifests()) == 1


def test_capability_and_coverage_queries_filter_without_merging_sources() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    soundcharts_manifest = SourceManifest(
        provider="SOUNDCHARTS",
        origin_platform="SPOTIFY",
        filename="soundcharts.csv",
        path=Path("soundcharts.csv"),
        sha256="c" * 64,
        size_bytes=1,
        row_count=1,
        schema_version="v1",
        status=SourceStatus.IMPORTED,
        countries=("BR",),
    )
    chartmetric_manifest = SourceManifest(
        provider="CHARTMETRIC",
        origin_platform="SPOTIFY",
        filename="chartmetric.json",
        path=Path("chartmetric.json"),
        sha256="d" * 64,
        size_bytes=1,
        row_count=1,
        schema_version="v1",
        status=SourceStatus.DISCOVERED,
        countries=("BR",),
    )

    with Session(engine) as session:
        repository = SourceInventoryRepository(session)
        repository.save_manifest(
            soundcharts_manifest,
            capabilities=(
                MarketCapability(
                    provider="SOUNDCHARTS",
                    origin_platform="SPOTIFY",
                    country_code="BR",
                    country_name="Brasil",
                    chart_types=("top200",),
                    native_frequency="DAILY",
                    ranking_depth=200,
                ),
            ),
            coverage=(
                {
                    "country_code": "BR",
                    "chart_name": "top200",
                    "period_start": date(2022, 1, 1),
                    "period_end": date(2022, 1, 1),
                    "status": "AVAILABLE",
                },
            ),
        )
        repository.save_manifest(
            chartmetric_manifest,
            capabilities=(
                MarketCapability(
                    provider="CHARTMETRIC",
                    origin_platform="SPOTIFY",
                    country_code="BR",
                    country_name="Brasil",
                    chart_types=("plays",),
                    native_frequency="DAILY",
                    ranking_depth=200,
                ),
            ),
        )
        session.commit()

        capabilities = repository.list_capabilities(provider="CHARTMETRIC")
        coverage = repository.list_coverage(provider="SOUNDCHARTS", country_code="BR")

    assert len(capabilities) == 1
    assert capabilities[0].provider == "CHARTMETRIC"
    assert capabilities[0].origin_platform == "SPOTIFY"
    assert len(coverage) == 1
    assert coverage[0].provider == "SOUNDCHARTS"
    assert coverage[0].chart_name == "top200"
