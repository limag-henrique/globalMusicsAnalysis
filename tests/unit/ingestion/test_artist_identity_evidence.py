import pytest

from chart_observatory.ingestion.artist_identity_evidence import (
    compile_artist_evidence,
    parse_artist_dictionary,
)

TRACK = "T" * 22
ARTIST = "spotify:artist:" + "A" * 22
GUEST = "spotify:artist:" + "B" * 22


def source_row(names="Group|Name | Guest", uris=None):
    return (
        "\t".join(
            [
                "0",
                "spotify:track:" + TRACK,
                "Fixture Song",
                names,
                uris or f"{ARTIST} | {GUEST}",
                "Label",
                "2020-01-01",
                "2020-01-03",
            ]
        )
        + "\n"
    )


def header(count=1):
    return ["#cc\tar\n", "#weeks\t2020-01-03\n", f"#songs\t{count}\n"]


def test_native_ids_preserve_names_and_do_not_read_chart_rows():
    def lines():
        yield from header()
        yield source_row()
        raise AssertionError("chart rows must not be read for artist identities")

    records, stats = parse_artist_dictionary(lines(), "ar", {TRACK})
    assert stats["selected_rows"] == 1
    assert records[0]["artists"] == [
        dict(uri=ARTIST, name="Group|Name"),
        dict(uri=GUEST, name="Guest"),
    ]
    assert parse_artist_dictionary([*header(), source_row()], "ar", {"X" * 22})[0] == []


def test_unaligned_artist_vectors_and_truncated_dictionary_are_not_guessed():
    records, stats = parse_artist_dictionary([*header(), source_row(uris=ARTIST)], "ar", {TRACK})
    assert records == [] and stats["invalid_rows"] == 1
    with pytest.raises(ValueError, match="truncated"):
        parse_artist_dictionary([*header(2), source_row(), "#rows\t20\n"], "ar", {TRACK})
    with pytest.raises(ValueError, match="country"):
        parse_artist_dictionary([*header(), source_row()], "br", {TRACK})


def test_name_variations_do_not_enable_aliases_and_conflicting_ids_remain_flagged():
    first = parse_artist_dictionary([*header(), source_row("Artist", ARTIST)], "ar", {TRACK})[0][0]
    other_name = {**first, "artists": [dict(uri=ARTIST, name="Other observed spelling")]}
    tracks, artists = compile_artist_evidence([first, other_name])
    assert tracks[0]["status"] == "CONSISTENT_NATIVE_ARTIST_IDS"
    assert len(artists[0]["observed_names"]) == 2
    assert not artists[0]["automatic_alias_matching_enabled"]
    different_id = {**first, "artists": [dict(uri=GUEST, name="Artist")]}
    tracks, _artists = compile_artist_evidence([first, different_id])
    assert tracks[0]["status"] == "CONFLICTING_NATIVE_ARTIST_IDS"
    assert not tracks[0]["recording_validated"]
