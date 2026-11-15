import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from chart_observatory import research_database_health as health


class Rows:
    def __init__(self, values):
        self.values = values

    def mappings(self):
        return self.values

    def one(self):
        return self.values

    def scalar_one_or_none(self):
        return self.values[0] if self.values else None


class Connection:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, runs, counts=(3, 2, 0), ranking_count=10):
        self.runs, self.counts, self.ranking_count = runs, counts, ranking_count
        self.ranking_runs = []
        self.readonly = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query):
        sql = str(query)
        if sql.startswith("SET TRANSACTION"):
            assert "READ ONLY" in sql
            self.readonly = True
            return None
        assert self.readonly, "inventory must never query production without READ ONLY"
        assert not any(word in sql.upper() for word in ("INSERT ", "UPDATE ", "DELETE ", "CREATE "))
        if sql.startswith("SET LOCAL"):
            return None
        if "global_annual_import_runs.manifest" in sql:
            if "WHERE global_annual_import_runs.id" in sql:
                return Rows(
                    [row["manifest"] for row in self.ranking_runs if row["id"] == "rank-run"]
                )
            return Rows(self.ranking_runs)
        if "quota_lyric_staging_runs" in sql:
            return Rows(self.runs)
        if "quota_lyric_staging_candidates" in sql:
            return Rows(self.counts)
        if "global_annual_import_runs" in sql:
            return Rows(self.ranking_runs)
        raise AssertionError(sql)

    def scalar(self, query):
        assert self.readonly
        sql = str(query)
        if sql == "SHOW transaction_read_only":
            return "on"
        if sql == "SHOW server_version":
            return "16.15"
        if "pg_is_in_recovery" in sql:
            return False
        if "global_annual_import_memberships" in sql:
            return self.ranking_count
        if "global_annual_import_cells" in sql:
            return 9
        raise AssertionError(sql)


@pytest.fixture
def inventory(tmp_path):
    selection = tmp_path / "selection"
    selection.mkdir()
    (selection / "manifest.json").write_text(
        json.dumps(
            {
                "memberships": 10,
                "country_year_cells": 9,
            }
        ),
        encoding="utf-8",
    )
    (selection / "postgres_import.json").write_text('{"run_id":"rank-run"}', encoding="utf-8")
    digest = health.file_hash(selection / "manifest.json")
    rows = [
        {
            "id": "wrong-newest",
            "manifest": {"global_manifest_sha256": "f" * 64},
            "created_at": datetime.now(UTC),
        },
        {
            "id": "correct-run",
            "manifest": {"global_manifest_sha256": digest, "unique_candidates": 3},
            "created_at": datetime.now(UTC),
        },
    ]
    connection = Connection(rows)
    connection.ranking_runs = [
        {
            "id": "rank-run",
            "manifest": {"global_manifest_sha256": digest},
        }
    ]
    return selection, connection, SimpleNamespace(connect=lambda: connection)


def test_live_inventory_binds_selection_uses_latest_compatible_run_and_is_readonly(inventory):
    selection, connection, engine = inventory
    result = health.current_inventory(selection.parent, selection, engine=engine)
    assert connection.readonly
    assert result["current_database_certified"] is True
    assert result["staging"]["run_id"] == "correct-run"
    assert result["staging"]["candidates"] == 3
    assert result["staging"]["text_candidates"] == 2
    assert result["staging"]["identity_or_integrity_approval_implied"] is False
    assert result["rankings"]["memberships"] == 10
    assert result["production_writes"] == 0


@pytest.mark.parametrize("counts", [(4, 2, 0), (3, 1, 2)])
def test_inconsistent_candidate_inventory_cannot_be_certified(inventory, counts):
    selection, connection, engine = inventory
    connection.counts = counts
    with pytest.raises(ValueError, match="contradicts"):
        health.current_inventory(selection.parent, selection, engine=engine)


def test_missing_compatible_run_does_not_borrow_another_selections_texts(inventory):
    selection, connection, engine = inventory
    connection.runs = connection.runs[:1]
    result = health.current_inventory(selection.parent, selection, engine=engine)
    assert result["staging"] is None


def test_other_ranking_version_or_partial_import_is_not_current(inventory):
    selection, connection, engine = inventory
    connection.ranking_count = 11
    with pytest.raises(ValueError, match="ranking counts"):
        health.current_inventory(selection.parent, selection, engine=engine)


def test_immutable_selection_resolves_import_by_exact_manifest_hash(inventory):
    selection, connection, engine = inventory
    (selection / "postgres_import.json").unlink()
    connection.ranking_runs = [
        {"id": "wrong-version", "manifest": {"global_manifest_sha256": "f" * 64}},
        {"id": "exact-version", "manifest": {
            "global_manifest_sha256": health.file_hash(selection / "manifest.json")
        }},
    ]
    report = health.current_inventory(selection.parent, selection, engine=engine)
    assert report["rankings"]["run_id"] == "exact-version"
    assert not (selection / "postgres_import.json").exists()


def test_unimported_immutable_selection_does_not_borrow_another_run(inventory):
    selection, connection, engine = inventory
    (selection / "postgres_import.json").unlink()
    connection.ranking_runs = [
        {"id": "wrong-version", "manifest": {"global_manifest_sha256": "f" * 64}}
    ]
    assert "rankings" not in health.current_inventory(selection.parent, selection, engine=engine)


def test_receipt_with_same_counts_but_different_selection_manifest_is_rejected(inventory):
    selection, connection, engine = inventory
    connection.ranking_runs = [
        {"id": "rank-run", "manifest": {"global_manifest_sha256": "f" * 64}}
    ]
    with pytest.raises(ValueError, match="different selection"):
        health.current_inventory(selection.parent, selection, engine=engine)


def test_legacy_receipt_requires_canonical_manifest_equality(inventory):
    selection, connection, engine = inventory
    connection.ranking_runs = [
        {
            "id": "rank-run",
            "manifest": json.loads((selection / "manifest.json").read_text()),
        }
    ]
    assert health.current_inventory(selection.parent, selection, engine=engine)["rankings"][
        "run_id"
    ] == "rank-run"
    connection.ranking_runs[0]["manifest"]["countries"] = 249
    with pytest.raises(ValueError, match="different selection"):
        health.current_inventory(selection.parent, selection, engine=engine)
