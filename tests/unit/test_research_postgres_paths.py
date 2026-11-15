import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PostgreSQL path discovery")
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/research_postgres_paths.ps1"


def cluster(base, version="16"):
    binaries = base / "postgresql16/bin"
    binaries.mkdir(parents=True)
    for name in ("pg_ctl.exe", "pg_isready.exe"):
        (binaries / name).write_text("placeholder, never executed")
    data = base / "postgres16-destination"
    data.mkdir()
    (data / "PG_VERSION").write_text(version)
    return base


def resolve(local, override=""):
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"

    command = (
        "$ErrorActionPreference='Stop'; . " + quote(SCRIPT)
        + "; Get-ResearchPostgresLayout -LocalDataRoot " + quote(local)
        + " -OverrideBase " + quote(override) + " | ConvertTo-Json -Compress"
    )
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )


def test_existing_packaged_cluster_survives_runtime_virtualization_change(tmp_path):
    expected = cluster(tmp_path / "Packages/OpenAI.Codex_test/LocalCache/Local/ChartObservatory")
    result = resolve(tmp_path)
    assert result.returncode == 0, result.stderr
    assert Path(json.loads(result.stdout)["Base"]) == expected


def test_ambiguous_clusters_require_explicit_target_instead_of_starting_wrong_database(tmp_path):
    native = cluster(tmp_path / "ChartObservatory")
    packaged = cluster(tmp_path / "Packages/OpenAI.Codex_test/LocalCache/Local/ChartObservatory")
    assert resolve(tmp_path).returncode != 0
    result = resolve(tmp_path, override=packaged)
    assert result.returncode == 0
    assert Path(json.loads(result.stdout)["Base"]) == packaged
    assert native.exists()


@pytest.mark.parametrize("version", [None, "18"])
def test_missing_or_incompatible_cluster_never_creates_an_empty_database(tmp_path, version):
    if version:
        cluster(tmp_path / "ChartObservatory", version=version)
    before = {p.relative_to(tmp_path) for p in tmp_path.rglob("*")}
    assert resolve(tmp_path).returncode != 0
    assert {p.relative_to(tmp_path) for p in tmp_path.rglob("*")} == before
