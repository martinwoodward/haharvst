"""Tests for the HarvstClient using a lightweight fake aiohttp session.

These avoid real sockets/DNS (which the Home Assistant test harness forbids)
while still exercising the SSE parsing, command building and HTML scraping.
"""

from __future__ import annotations

import aiohttp
import pytest

from custom_components.harvst.client import HarvstClient, HarvstConnectionError

from .conftest import SETTINGS_HTML, SSE_IDLE


class _FakeContent:
    """Async byte-line iterator mimicking aiohttp's StreamReader content."""

    def __init__(self, data: bytes) -> None:
        self._lines = data.splitlines(keepends=True)

    async def __aiter__(self):
        for line in self._lines:
            yield line


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        body: str = "",
        exc: Exception | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self._exc = exc
        self.content = _FakeContent(body.encode())

    async def __aenter__(self) -> _FakeResponse:
        if self._exc is not None:
            raise self._exc
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status)

    async def text(self) -> str:
        return self._body


class _FakeSession:
    """Records GET calls and returns canned responses."""

    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self._response


async def test_get_reading_parses_sse():
    """The client extracts the first JSON reading from the SSE stream."""
    session = _FakeSession(_FakeResponse(body=SSE_IDLE))
    reading = await HarvstClient("host", session).async_get_reading()
    assert reading["te"] == 22
    assert reading["cc"] == 100


async def test_get_reading_no_data_raises():
    """A stream with only keep-alives raises a connection error."""
    session = _FakeSession(_FakeResponse(body="data: ping\n\ndata: hello!\n\n"))
    with pytest.raises(HarvstConnectionError):
        await HarvstClient("host", session).async_get_reading()


async def test_get_reading_connection_error():
    """Transport errors surface as HarvstConnectionError."""
    session = _FakeSession(_FakeResponse(exc=aiohttp.ClientError()))
    with pytest.raises(HarvstConnectionError):
        await HarvstClient("host", session).async_get_reading()


async def test_water_zone_sends_control_request():
    """Watering a zone issues the expected control URL."""
    session = _FakeSession(_FakeResponse(status=302))
    await HarvstClient("1.2.3.4", session).async_water_zone(2, 45)
    url, kwargs = session.calls[-1]
    assert url == "http://1.2.3.4/control?device=pump&state=on&zone=2&time=45"
    assert kwargs.get("allow_redirects") is False


async def test_get_device_id():
    """The device id is scraped from the settings page."""
    session = _FakeSession(_FakeResponse(body=SETTINGS_HTML))
    client = HarvstClient("host", session)
    assert await client.async_get_device_id() == "A84467B865E4"


async def test_get_device_id_missing_returns_none():
    """Missing device id returns None rather than raising."""
    session = _FakeSession(_FakeResponse(body="<html>no id here</html>"))
    assert await HarvstClient("host", session).async_get_device_id() is None


async def test_get_settings_info():
    """Pump diagnostics are scraped from the settings page."""
    session = _FakeSession(_FakeResponse(body=SETTINGS_HTML))
    info = await HarvstClient("host", session).async_get_settings_info()
    assert info["pump_back_pressure"] == "56 / 4712"
    assert info["pump_detection"] == "Pump OK"


async def test_get_settings_info_missing_rows():
    """Absent diagnostic rows are simply omitted from the result."""
    session = _FakeSession(_FakeResponse(body="<html>no table</html>"))
    info = await HarvstClient("host", session).async_get_settings_info()
    assert info == {}
