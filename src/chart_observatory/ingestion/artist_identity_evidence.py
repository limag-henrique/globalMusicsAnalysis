"""Extract native artist identifiers without matching names or modifying rankings."""

import hashlib
import re
from collections import defaultdict

TRACK_URI = re.compile(r"spotify:track:([A-Za-z0-9]{22})")
ARTIST_URI = re.compile(r"spotify:artist:[A-Za-z0-9]{22}")


def parse_artist_dictionary(lines, expected_country, wanted_tracks):
    iterator = iter(lines)
    try:
        country = next(iterator).rstrip("\r\n").split("\t")
        weeks = next(iterator)
        header = next(iterator).rstrip("\r\n").split("\t")
        if country != ["#cc", expected_country.lower()] or not weeks.startswith("#weeks\t"):
            raise ValueError("unexpected source country or header")
        if len(header) != 2 or header[0] != "#songs":
            raise ValueError("missing song dictionary header")
        count = int(header[1])
        if count < 0:
            raise ValueError("negative song dictionary length")
        records, invalid = [], 0
        for _ in range(count):
            line = next(iterator).rstrip("\r\n")
            if line.startswith("#"):
                raise ValueError("truncated source dictionary")
            fields = line.split("\t")
            if len(fields) != 8 or not fields[0].isdigit():
                invalid += 1
                continue
            match = TRACK_URI.fullmatch(fields[1])
            if not match:
                invalid += 1
                continue
            native = match[1]
            if native not in wanted_tracks:
                continue
            names = [value.strip() for value in fields[3].split(" | ")]
            uris = [value.strip() for value in fields[4].split(" | ")]
            if (
                len(names) != len(uris)
                or not all(names)
                or len(set(uris)) != len(uris)
                or not all(ARTIST_URI.fullmatch(uri) for uri in uris)
                or any(ord(char) < 32 for name in names for char in name)
            ):
                invalid += 1
                continue
            records.append(
                dict(
                    candidate_id="SPOTIFY:" + native,
                    source_song_index=int(fields[0]),
                    dictionary_row_sha256=hashlib.sha256(line.encode()).hexdigest(),
                    observed_title=fields[2],
                    artists=[
                        dict(uri=uri, name=name) for uri, name in zip(uris, names, strict=True)
                    ],
                )
            )
    except StopIteration:
        raise ValueError("truncated source dictionary") from None
    return records, dict(dictionary_rows=count, selected_rows=len(records), invalid_rows=invalid)


def compile_artist_evidence(observations):
    tracks, artists = defaultdict(list), defaultdict(lambda: dict(names=set(), tracks=set()))
    for observation in observations:
        key = observation["candidate_id"]
        tracks[key].append(observation)
        for artist in observation["artists"]:
            artists[artist["uri"]]["names"].add(artist["name"])
            artists[artist["uri"]]["tracks"].add(key)
    track_records = []
    for key, rows in sorted(tracks.items()):
        variants = {tuple(sorted(artist["uri"] for artist in row["artists"])) for row in rows}
        track_records.append(
            dict(
                candidate_id=key,
                artist_uri_sets=[list(v) for v in sorted(variants)],
                status="CONSISTENT_NATIVE_ARTIST_IDS"
                if len(variants) == 1
                else "CONFLICTING_NATIVE_ARTIST_IDS",
                observations=rows,
                recording_validated=False,
                lyrics_validated=False,
            )
        )
    artist_records = [
        dict(
            spotify_artist_uri=uri,
            observed_names=sorted(value["names"]),
            selected_track_count=len(value["tracks"]),
            automatic_alias_matching_enabled=False,
        )
        for uri, value in sorted(artists.items())
    ]
    return track_records, artist_records
