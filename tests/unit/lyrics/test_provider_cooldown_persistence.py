import sqlite3
import time

import httpx
import pytest

from chart_observatory.lyrics.quota_acquisition import PacedHTTP


def test_new_process_honors_persisted_pause_and_keeps_cached_responses_available(tmp_path):
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return (
            httpx.Response(200, text="Preserved response")
            if request.url.path == "/saved"
            else httpx.Response(429, headers={"retry-after": "3600"})
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        previous = PacedHTTP(tmp_path, client)
        previous.get("https://genius.com/saved")
        previous.get("https://genius.com/limited")
        current = PacedHTTP(tmp_path, client)
        assert current.get("https://genius.com/new").status_code == 429
        assert current.get("https://genius.com/saved").text == "Preserved response"
        assert current.provider_retry_delays()["genius.com"] > 3500
    assert calls == ["/saved", "/limited"]


def test_late_short_failure_does_not_shorten_persisted_pause_and_expiry_allows_work(tmp_path):
    calls = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: calls.append(request.url.path) or httpx.Response(200, text="Available")
        )
    ) as client:
        previous = PacedHTTP(tmp_path, client)
        previous._pause_domain("genius.com", httpx.Response(429, headers={"retry-after": "3600"}))
        stale = PacedHTTP(tmp_path, client)
        stale._blocked_until.clear()
        stale._pause_domain("genius.com", httpx.Response(503))
        current = PacedHTTP(tmp_path, client)
        assert current.provider_retry_delays()["genius.com"] > 3500
        assert current.get("https://genius.com/paused").status_code == 429
        with sqlite3.connect(tmp_path / "provider-cooldowns.sqlite") as db:
            db.execute("UPDATE provider_cooldowns SET until_epoch=?", (time.time() - 1,))
        resumed = PacedHTTP(tmp_path, client)
        assert resumed.provider_retry_delays() == {}
        assert resumed.get("https://genius.com/resumed").status_code == 200
    assert calls == ["/resumed"]


def test_corrupt_pause_database_is_not_silently_ignored(tmp_path):
    (tmp_path / "provider-cooldowns.sqlite").write_bytes(b"Corrupt state")
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(AssertionError("must not access network"))
            )
        ) as client,
        pytest.raises(sqlite3.DatabaseError),
    ):
        PacedHTTP(tmp_path, client)
