import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts/build_research_flow_package.py"
_SPEC = importlib.util.spec_from_file_location("build_research_flow_package", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
package_builder = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(package_builder)


def _write(path: Path, content: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _fixture(tmp_path, monkeypatch):
    root = tmp_path.resolve()
    monkeypatch.setattr(package_builder, "ROOT", root)
    monkeypatch.setattr(package_builder, "AUDIT_FILES", ("report.json",))
    monkeypatch.setattr(package_builder, "SOURCES", ("source.txt",))
    audit = root / "data/runtime/audit-1"
    _write(audit / "report.json", b"{}")
    _write(root / "source.txt", b"source")
    monkeypatch.setattr(
        package_builder,
        "verify_audit",
        lambda _audit: {
            "research_ready": False,
            "selection_sha256": "audit-selection-hash",
            "audit_run_id": "audit-1",
            "gates": [{"gate": "G1", "state": "reprovado"}],
        },
    )

    selection = root / "data/derived/annual-rescan-v1"
    years = list(range(2018, 2027))
    cells = [
        {
            "country_code": "AA",
            "year": year,
            "quota": 1,
            "ranking_period_end": "2026-10-15" if year == 2026 else f"{year}-12-31",
        }
        for year in years
    ]
    contents = {
        "combined.jsonl": b"",
        "country_years.jsonl": "".join(json.dumps(row) + "\n" for row in cells).encode(),
        "countries.json": b"[]",
        "source_coverage.json": b"[]",
        "position_tie_tasks.jsonl": b"",
        "adjudication_tasks.jsonl": b"",
        "zenodo_provenance.json": b"{}",
    }
    hashes = {name: _write(selection / name, content) for name, content in contents.items()}
    source_readme = root / "data/raw/historical_backfill/zenodo-23645386/README.md"
    source_record = root / "data/raw/historical_backfill/zenodo-23645386/record.json"
    source_hashes = {
        "data/raw/historical_backfill/zenodo-23645386/README.md": _write(
            source_readme, b"dataset README"
        ),
        "data/raw/historical_backfill/zenodo-23645386/record.json": _write(
            source_record, b'{"doi":"10.5281/zenodo.test"}'
        ),
    }
    manifest = {
        "protocol": "worldwide-annual-quotas-v1",
        "selection_revision": "test-rescan-v1",
        "years": years,
        "cutoff": "2026-10-15",
        "countries": 1,
        "country_year_cells": 9,
        "requested_positions": 9,
        "memberships": 0,
        "output_hashes": hashes,
        "source_hashes": source_hashes,
    }
    _write(selection / "manifest.json", json.dumps(manifest).encode())
    return audit, selection


def test_package_includes_verified_selection_and_source_metadata_but_stays_blocked(
    tmp_path, monkeypatch
):
    audit, selection = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "data/runtime/package.zip"

    result = package_builder.build(audit, output, selection=selection)

    assert result["status"] == "blocked_preparation"
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "selection/manifest.json" in names
        assert "selection/combined.jsonl" in names
        assert "selection/country_years.jsonl" in names
        assert "selection/source/README.md" in names
        assert "selection/source/record.json" in names
        assert not any("lyrics" in name.lower() for name in names)
        package_manifest = json.loads(archive.read("package-manifest.json"))
    assert package_manifest["selection_path"] == selection.relative_to(tmp_path).as_posix()
    assert package_manifest["selection_revision"] == "test-rescan-v1"
    assert package_manifest["gate_states"] == {"G1": "reprovado"}
    assert not package_manifest["selection_matches_audit"]
    assert not package_manifest["research_ready"]


def test_package_refuses_changed_selection_output_hash(tmp_path, monkeypatch):
    audit, selection = _fixture(tmp_path, monkeypatch)
    (selection / "combined.jsonl").write_text('{"lyrics":"must not package"}\n')
    output = tmp_path / "data/runtime/package.zip"

    with pytest.raises(ValueError, match="selection output missing or changed"):
        package_builder.build(audit, output, selection=selection)

    assert not output.exists()


def test_package_refuses_lyrics_in_an_otherwise_valid_selection(tmp_path, monkeypatch):
    audit, selection = _fixture(tmp_path, monkeypatch)
    content = (
        b'{"country_code":"AA","year":2018,"position":1,'
        b'"candidate_id":"SPOTIFY:track","platform":"SPOTIFY",'
        b'"provider":"TEST","lyrics":"must not package"}\n'
    )
    _write(selection / "combined.jsonl", content)
    manifest = json.loads((selection / "manifest.json").read_text())
    manifest["output_hashes"]["combined.jsonl"] = hashlib.sha256(content).hexdigest()
    manifest["memberships"] = 1
    _write(selection / "manifest.json", json.dumps(manifest).encode())
    output = tmp_path / "data/runtime/package.zip"

    with pytest.raises(ValueError, match="contains lyric text"):
        package_builder.build(audit, output, selection=selection)

    assert not output.exists()
