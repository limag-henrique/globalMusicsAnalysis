from chart_observatory.lyrics.identity_collisions import flag_shared_text_identities


def row(key, artist, title="Song", digest="a" * 64):
    return dict(candidate_id=key, text_sha256=digest,
                payload=dict(title=title, artist=artist), audit={})


def test_same_title_different_performers_needs_review_without_deleting_either():
    rows = [row("original", "Singer"), row("cover", "Other Singer")]
    collisions = flag_shared_text_identities(rows)
    assert len(collisions) == 1
    assert collisions[0]["flags"] == ["same_text_different_performers"]
    assert all(r["audit"]["text_quality_flags"] == collisions[0]["flags"] for r in rows)
    assert len(rows) == 2
    assert flag_shared_text_identities(rows) == collisions


def test_case_and_punctuation_do_not_create_false_identity_collision():
    rows = [row("one", "Singer", "Song!"), row("two", "SINGER", "song")]
    assert flag_shared_text_identities(rows) == []
    assert flag_shared_text_identities([row("missing", "Other", digest=None)]) == []
