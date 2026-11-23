import importlib.util
import json
import sqlite3
from pathlib import Path


def test_delta_preserves_processed_records_and_does_not_inherit_another_recording(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "queue_builder", Path(__file__).parents[2] / "scripts/build_supplemental_lyric_queue.py",
    )
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    canon, supp, processed = [tmp_path / name for name in ("canon.db", "supp.db", "done.db")]
    with sqlite3.connect(canon) as db:
        db.execute("CREATE TABLE songs(id TEXT,payload TEXT,result TEXT)")
        db.execute("INSERT INTO songs VALUES (?,?,?)", (
            "SPOTIFY:one", json.dumps(dict(title="Song", artist="Artist")),
            json.dumps(dict(text_sha256="saved")),
        ))
    with sqlite3.connect(supp) as db:
        db.execute("""CREATE TABLE supplemental_songs(song_id,title,artist_credit,
            native_provider,native_song_id,version_tags_json,featured_artists_json)""")
        db.executemany("INSERT INTO supplemental_songs VALUES (?,?,?,?,?,?,?)", [
            ("old", "Song", "Artist", "SPOTIFY", "one", "[]", "[]"),
            ("new", "Song", "Artist", "APPLE_MUSIC", "different", "[]", "[]"),
        ])
        db.execute("CREATE TABLE supplemental_memberships(song_id,position,raw_json)")
    with sqlite3.connect(processed) as db:
        db.execute("CREATE TABLE supplemental_lyrics(song_id TEXT)")
        db.execute("INSERT INTO supplemental_lyrics VALUES ('old')")
    audit = tmp_path / "decisions.jsonl"
    audit.write_text(json.dumps(dict(candidate_id="SPOTIFY:one", provider_supported=True)) + "\n")
    output = tmp_path / "queue"
    builder.main(["--supp-db", str(supp), "--canon-db", str(canon),
                  "--strict-audit", str(audit), "--output-dir", str(output),
                  "--exclude-processed-db", str(processed), "--native-match-only"])
    rows = [json.loads(line) for line in (output / "supplemental-lyric-queue.jsonl").open()]
    assert [row["song_id"] for row in rows] == ["new"]
    assert rows[0]["state"] == "new_requires_acquisition"
    assert rows[0]["matched_canonical_id"] is None
    summary = json.loads((output / "queue-summary.json").read_text())
    assert summary["excluded_processed"] == 1
    assert summary["total_provider_identity_keys"] == 2
