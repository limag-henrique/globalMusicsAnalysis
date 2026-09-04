import hashlib
import json

import polars as pl
from typer.testing import CliRunner

from chart_observatory.cli import app
from chart_observatory.procurement.schema_profiler import profile_sample


def test_profiles_csv_without_copying_or_exposing_values(tmp_path) -> None:
    sample = tmp_path / "provider-sample.csv"
    sample.write_text(
        "country,rank,isrc,streams\nBR,1,BRABC1234567,1500\nBR,2,,\n",
        encoding="utf-8",
    )

    profile = profile_sample(sample)

    assert profile.sha256 == hashlib.sha256(sample.read_bytes()).hexdigest()
    assert profile.byte_length == sample.stat().st_size
    assert profile.format == "CSV"
    assert profile.row_count == 2
    assert [(column.path, column.null_count) for column in profile.fields] == [
        ("country", 0),
        ("rank", 0),
        ("isrc", 1),
        ("streams", 1),
    ]
    assert "BRABC1234567" not in json.dumps(profile.as_dict())
    assert list(tmp_path.iterdir()) == [sample]


def test_profiles_nested_json_structure_without_retaining_payload_values(tmp_path) -> None:
    sample = tmp_path / "provider-sample.json"
    sample.write_text(
        json.dumps(
            {
                "period": "2026-W35",
                "entries": [
                    {"rank": 1, "track": {"isrc": "BRABC1234567"}},
                    {"rank": 2, "track": {"isrc": None}},
                ],
            }
        ),
        encoding="utf-8",
    )

    profile = profile_sample(sample)

    fields = {field.path: field for field in profile.fields}
    assert profile.format == "JSON"
    assert profile.row_count is None
    assert fields["$.entries"].types == ("array",)
    assert fields["$.entries[]"].types == ("object",)
    assert fields["$.entries[].rank"].types == ("integer",)
    assert fields["$.entries[].track.isrc"].types == ("null", "string")
    assert fields["$.entries[].track.isrc"].null_count == 1
    assert "BRABC1234567" not in json.dumps(profile.as_dict())


def test_profiles_parquet_schema_and_nullability(tmp_path) -> None:
    sample = tmp_path / "provider-sample.parquet"
    pl.DataFrame({"rank": [1, 2], "views": [9000, None]}).write_parquet(sample)

    profile = profile_sample(sample)

    assert profile.format == "PARQUET"
    assert profile.row_count == 2
    assert [(column.path, column.null_count) for column in profile.fields] == [
        ("rank", 0),
        ("views", 1),
    ]


def test_rejects_unsupported_sample_format(tmp_path) -> None:
    sample = tmp_path / "provider-sample.xlsx"
    sample.write_bytes(b"not a supported sample")

    try:
        profile_sample(sample)
    except ValueError as error:
        assert "Unsupported sample format" in str(error)
    else:
        raise AssertionError("unsupported samples must fail closed")


def test_cli_emits_machine_readable_profile_without_payload_values(tmp_path) -> None:
    sample = tmp_path / "provider-sample.csv"
    sample.write_text("rank,isrc\n1,BRABC1234567\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["procurement", "profile-sample", str(sample)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["format"] == "CSV"
    assert payload["row_count"] == 1
    assert "BRABC1234567" not in result.stdout
