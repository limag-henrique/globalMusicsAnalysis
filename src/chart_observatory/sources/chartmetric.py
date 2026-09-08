from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from chart_observatory.adapters.http import HttpPolicy, execute_http
from chart_observatory.sources.models import MarketCapability, SourceObservation


@dataclass(frozen=True)
class ChartmetricRequest:
    method: str
    path: str
    params: dict[str, object] = field(default_factory=dict)
    body: dict[str, object] | None = None
    headers: dict[str, str] = field(default_factory=dict)


class ChartmetricError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ChartmetricAuthError(ChartmetricError):
    pass


class ChartmetricClient:
    """Small authenticated Chartmetric seam with token reuse and bounded retries."""

    base_url = "https://api.chartmetric.com"

    def __init__(
        self,
        refresh_token: str | Callable[[], str] | None,
        *,
        transport: Any,
        base_url: str = base_url,
        policy: HttpPolicy | None = None,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], object] = time.sleep,
    ) -> None:
        self.refresh_token = refresh_token
        self.transport = transport
        self.base_url = base_url.rstrip("/")
        self.policy = policy or HttpPolicy()
        self.clock = clock
        self.sleep = sleep
        self._access_token: str | None = None
        self._expires_at = 0.0

    def access_token(self) -> str:
        if self._access_token and self.clock() < self._expires_at - 60:
            return self._access_token
        token = self.refresh_token() if callable(self.refresh_token) else self.refresh_token
        if not token:
            raise ChartmetricAuthError("Chartmetric refresh token is not configured")
        request = ChartmetricRequest(
            "POST",
            "/api/token",
            body={"refreshtoken": token},
            headers={"Content-Type": "application/json"},
        )
        response = self._send_raw(request, authenticate=False)
        if response.status_code >= 400:
            raise ChartmetricAuthError(
                f"Chartmetric token exchange failed ({response.status_code})", response.status_code
            )
        body = _json_body(response)
        access_token = body.get("token")
        if not isinstance(access_token, str) or not access_token:
            raise ChartmetricAuthError("Chartmetric token response has no token")
        self._access_token = access_token
        self._expires_at = self.clock() + float(body.get("expires_in", 3600))
        return access_token

    def get(self, path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
        for refresh_attempt in range(2):
            request = ChartmetricRequest(
                "GET",
                path,
                params or {},
                headers={"Authorization": f"Bearer {self.access_token()}"},
            )
            response = self._send_raw(request, authenticate=True)
            if response.status_code == 401 and refresh_attempt == 0:
                self._access_token = None
                self._expires_at = 0
                continue
            if response.status_code >= 400:
                raise ChartmetricError(
                    f"Chartmetric request failed ({response.status_code})", response.status_code
                )
            return _json_body(response)
        raise ChartmetricAuthError("Chartmetric access token rejected after one refresh", 401)

    def discover_capabilities(
        self, platforms: tuple[str, ...] = ("spotify", "deezer", "qq", "amazon")
    ) -> tuple[MarketCapability, ...]:
        capabilities: list[MarketCapability] = []
        for platform in platforms:
            try:
                countries_payload = self.get(
                    f"/api/charts/{platform}/countries", {"chart_type": "tracks"}
                )
                countries = _countries_from_payload(countries_payload)
            except ChartmetricError:
                countries = ()
            if countries:
                capabilities.extend(
                    MarketCapability(
                        provider="CHARTMETRIC",
                        origin_platform=platform.upper(),
                        country_code=country,
                        country_name=None,
                        territory_type="GLOBAL" if country == "GLOBAL" else "COUNTRY",
                        available=True,
                        chart_types=("tracks",),
                    )
                    for country in countries
                )
                continue
            path, params = _probe_for(platform)
            try:
                payload = self.get(path, params)
            except ChartmetricError as error:
                capabilities.append(
                    MarketCapability(
                        provider="CHARTMETRIC",
                        origin_platform=platform.upper(),
                        country_code="GLOBAL",
                        country_name=None,
                        territory_type="GLOBAL",
                        available=False,
                        chart_types=(f"HTTP_{error.status_code or 'ERROR'}",),
                    )
                )
                continue
            capabilities.extend(_capabilities_from_payload(platform, payload))
        return tuple(capabilities)

    def chart_dates(
        self,
        streaming_type: str,
        *,
        from_days_ago: int,
        chart_entity: str | None = None,
        chart_type: str | None = None,
        duration: str | None = None,
        country: str | None = None,
        genre: str | None = None,
    ) -> tuple[date, ...]:
        """Return provider-supported chart dates for a bounded look-back window."""
        if from_days_ago < 1:
            raise ValueError("from_days_ago must be positive")
        params: dict[str, object] = {"fromDaysAgo": from_days_ago}
        optional = {
            "chartEntity": chart_entity,
            "chartType": chart_type,
            "duration": duration,
            "country": country,
            "genre": genre,
        }
        params.update({key: value for key, value in optional.items() if value is not None})
        payload = self.get(f"/api/charts/{streaming_type}/dates", params)
        obj = payload.get("obj", [])
        if not isinstance(obj, list):
            return ()
        dates: list[date] = []
        seen: set[date] = set()
        for row in obj:
            if not isinstance(row, dict):
                continue
            timestamp = row.get("timestp")
            if not isinstance(timestamp, str):
                continue
            try:
                value = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            if value not in seen:
                dates.append(value)
                seen.add(value)
        return tuple(dates)

    def collect_chart(
        self,
        *,
        platform: str,
        country_code: str,
        interval: str,
        chart_type: str,
        period: date,
        limit: int = 200,
        offset: int = 0,
    ) -> tuple[SourceObservation, ...]:
        payload = self.get(
            f"/api/charts/{platform}",
            {
                "country_code": country_code.upper(),
                "interval": interval,
                "type": chart_type,
                "date": period.isoformat(),
                "offset": offset,
            },
        )
        return tuple(
            _observation_from_row(platform, country_code, chart_type, period, index, row)
            for index, row in enumerate(_rows(payload)[:limit], start=offset + 1)
        )

    def collect_chart_pages(
        self,
        *,
        platform: str,
        country_code: str,
        interval: str,
        chart_type: str,
        period: date,
        page_size: int = 200,
        checkpoint_path: Path | None = None,
        max_pages: int | None = None,
        on_page: Callable[[int, dict[str, Any], tuple[SourceObservation, ...]], None] | None = None,
    ) -> tuple[SourceObservation, ...]:
        """Collect a bounded chart with an on-disk offset checkpoint.

        The checkpoint contains only the request fingerprint and the next offset;
        provider rows are returned to the caller and are never written here.
        """
        if not 1 <= page_size <= 200:
            raise ValueError("page_size must be between 1 and 200")
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be positive when provided")

        fingerprint = _checkpoint_fingerprint(
            platform, country_code, interval, chart_type, period, page_size
        )
        offset, complete = _load_checkpoint(checkpoint_path, fingerprint)
        if complete:
            return ()
        rows: list[SourceObservation] = []
        pages = 0
        while True:
            payload = self.get(
                f"/api/charts/{platform}",
                {
                    "country_code": country_code.upper(),
                    "interval": interval,
                    "type": chart_type,
                    "date": period.isoformat(),
                    "offset": offset,
                },
            )
            page_rows = _rows(payload)[:page_size]
            page_observations = tuple(
                _observation_from_row(platform, country_code, chart_type, period, index, row)
                for index, row in enumerate(page_rows, start=offset + 1)
            )
            if on_page is not None:
                on_page(offset, payload, page_observations)
            rows.extend(page_observations)
            pages += 1
            next_offset = _next_offset(payload, offset, len(page_rows), page_size)
            if next_offset is None:
                _save_checkpoint(checkpoint_path, fingerprint, "COMPLETE", None)
                return tuple(rows)
            offset = next_offset
            _save_checkpoint(checkpoint_path, fingerprint, "PAUSED", offset)
            if max_pages is not None and pages >= max_pages:
                return tuple(rows)

    def _send_raw(self, request: ChartmetricRequest, *, authenticate: bool) -> Any:
        headers = dict(request.headers)
        if authenticate and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.access_token()}"
        authorized = ChartmetricRequest(
            request.method, request.path, request.params, request.body, headers
        )
        return execute_http(self.transport, authorized, self.policy, sleep=self.sleep)


def _json_body(response: Any) -> dict[str, Any]:
    content = getattr(response, "content", b"")
    if isinstance(content, str):
        content = content.encode()
    try:
        value = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise ChartmetricError("Chartmetric returned malformed JSON") from error
    if not isinstance(value, dict):
        raise ChartmetricError("Chartmetric response must be an object")
    return value


def _rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    obj = payload.get("obj", payload)
    data = obj.get("data", obj.get("results", [])) if isinstance(obj, dict) else obj
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def _capabilities_from_payload(
    platform: str, payload: dict[str, Any]
) -> tuple[MarketCapability, ...]:
    rows = _rows(payload)
    countries: set[str] = set()
    charts: set[str] = set()
    for row in rows:
        country = row.get("country_code", row.get("code2", row.get("country")))
        if country:
            countries.add(str(country).upper())
        chart = row.get("chart_type", row.get("type"))
        if chart:
            charts.add(str(chart))
    return tuple(
        MarketCapability(
            "CHARTMETRIC",
            platform.upper(),
            country,
            None,
            territory_type="GLOBAL" if country == "GLOBAL" else "COUNTRY",
            chart_types=tuple(sorted(charts)),
        )
        for country in sorted(countries or {"GLOBAL"})
    )


def _countries_from_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    obj = payload.get("obj", payload)
    countries = obj.get("countries", []) if isinstance(obj, dict) else []
    return tuple(sorted({str(country).upper() for country in countries if country}))


def _probe_for(platform: str) -> tuple[str, dict[str, object]]:
    today = date.today().isoformat()
    if platform == "spotify":
        return "/api/charts/spotify", {
            "country_code": "GLOBAL",
            "interval": "daily",
            "type": "plays",
            "latest": "true",
            "limit": 1,
        }
    if platform == "amazon":
        return f"/api/charts/{platform}/tracks", {
            "country_code": "GLOBAL",
            "date": today,
            "limit": 1,
        }
    return f"/api/charts/{platform}", {"country_code": "GLOBAL", "date": today, "limit": 1}


def _observation_from_row(
    platform: str,
    country_code: str,
    chart_type: str,
    period: date,
    rank: int,
    row: dict[str, Any],
) -> SourceObservation:
    artists = row.get("artists", row.get("spotify_artist_names", row.get("artist_names", [])))
    if isinstance(artists, list):
        artist_names = [
            str(item.get("name", "")) if isinstance(item, dict) else str(item) for item in artists
        ]
        artist = ", ".join(name for name in artist_names if name)
    else:
        artist = str(row.get("artist", ""))
    title = str(row.get("track_name", row.get("trackName", row.get("name", ""))))
    native_id = row.get("track_id", row.get("trackId", row.get("cm_track", row.get("id"))))
    metric = row.get("plays", row.get("current_plays"))
    return SourceObservation(
        provider="CHARTMETRIC",
        origin_platform=platform.upper(),
        country_code=country_code.upper(),
        chart_name=chart_type,
        period_start=period,
        period_end=period,
        rank=int(row.get("rank", rank)),
        track_title=title,
        artist=artist,
        native_id=str(native_id) if native_id is not None else None,
        metric_value=Decimal(str(metric)) if isinstance(metric, (int, float)) else None,
        metric_type="STREAMS" if metric is not None else None,
        raw_fields=row,
    )


def _checkpoint_fingerprint(
    platform: str,
    country_code: str,
    interval: str,
    chart_type: str,
    period: date,
    page_size: int,
) -> str:
    request = "|".join(
        (
            platform.casefold(),
            country_code.upper(),
            interval,
            chart_type,
            period.isoformat(),
            str(page_size),
        )
    )
    return hashlib.sha256(request.encode("utf-8")).hexdigest()


def _load_checkpoint(path: Path | None, fingerprint: str) -> tuple[int, bool]:
    if path is None or not path.exists():
        return 0, False
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("request_fingerprint") != fingerprint:
        raise ValueError("Chartmetric checkpoint belongs to a different request")
    if payload.get("status") == "COMPLETE":
        return 0, True
    next_offset = payload.get("next_offset")
    return (int(next_offset) if next_offset is not None else 0), False


def _save_checkpoint(
    path: Path | None, fingerprint: str, status: str, next_offset: int | None
) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_fingerprint": fingerprint,
        "status": status,
        "next_offset": next_offset,
    }
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _next_offset(
    payload: dict[str, Any], offset: int, row_count: int, page_size: int
) -> int | None:
    obj = payload.get("obj", payload)
    if isinstance(obj, dict):
        for key in ("next_offset", "nextOffset"):
            value = obj.get(key)
            if value is None:
                continue
            return int(value)
        total = obj.get("total")
        if total is not None and offset + row_count < int(total):
            return offset + row_count
    if row_count == 0 or row_count < page_size:
        return None
    return offset + row_count
