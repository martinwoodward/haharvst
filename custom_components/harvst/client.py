"""Low-level HTTP client for the Harvst control panel.

The control panel is an ESP-based device that exposes:

* ``GET /events``  - a Server-Sent-Events stream. Every ~1s it emits a
  ``new_readings`` event whose ``data:`` line is a JSON document, e.g.::

      {"te":22,"teAve":14.66,"ti":-13,"ta":-13,"h":-13,"isr":0,
       "ts_1":-13,"ts_2":-13,"s1":-13,"s2":-13,"x1":0,"x2":0,"x3":0,"cc":100}

  ``te`` is the wired "silver bullet" temperature in °C (``-13`` means the
  sensor is absent). ``cc`` is the measured pump current in mA: roughly
  ``100`` when idle and strongly negative (~``-4000``) while a pump is
  running, which is how we detect active watering. When the pump turns on or
  off the panel additionally includes a ``pump_state`` (1/0) field on that
  transition reading.

* ``GET /control?device=pump&state=on&zone=<n>&time=<seconds>`` - triggers
  watering on ``zone`` (1 or 2) for ``seconds`` seconds. Responds with a
  ``302`` redirect to ``/?updated=y``.

* ``GET /settings`` - an HTML page that contains the device id, used to build
  a stable unique id for the config entry.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEVICE_ID_RE = re.compile(r"Device ID:\s*<div>\s*([0-9A-Fa-f]+)\s*</div>")

DEFAULT_TIMEOUT = 10
# How long we are prepared to wait on the SSE stream for a single reading.
READING_TIMEOUT = 8


class HarvstError(Exception):
    """Base error for the Harvst client."""


class HarvstConnectionError(HarvstError):
    """Raised when the control panel cannot be reached."""


class HarvstClient:
    """Talk to a single Harvst control panel."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        """Initialise the client for ``host`` using an aiohttp ``session``."""
        self._host = host.strip().rstrip("/")
        self._session = session

    @property
    def host(self) -> str:
        """Return the configured host."""
        return self._host

    def _url(self, path: str) -> str:
        path = path if path.startswith("/") else f"/{path}"
        return f"http://{self._host}{path}"

    async def async_get_reading(self) -> dict[str, Any]:
        """Return the next sensor reading from the panel's event stream."""
        url = self._url("/events")
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=READING_TIMEOUT)
            ) as resp:
                resp.raise_for_status()
                reading = await self._read_first_reading(resp)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise HarvstConnectionError(
                f"Error fetching readings from {self._host}: {err}"
            ) from err

        if reading is None:
            raise HarvstConnectionError(f"No sensor reading received from {self._host}")
        return reading

    @staticmethod
    async def _read_first_reading(resp: aiohttp.ClientResponse) -> dict | None:
        """Parse the SSE stream and return the first JSON reading found."""
        async for raw_line in resp.content:
            line = raw_line.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:") :].strip()
            if not payload.startswith("{"):
                # Keep-alive markers like "hello!" / "ping".
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                _LOGGER.debug("Ignoring malformed reading: %s", payload)
                continue
            if isinstance(data, dict):
                return data
        return None

    async def async_water_zone(self, zone: int, seconds: int) -> None:
        """Run the pump for ``seconds`` seconds on ``zone``."""
        url = self._url(
            f"/control?device=pump&state=on&zone={int(zone)}&time={int(seconds)}"
        )
        await self._async_command(url)

    async def async_clear_last_watered(self, zone: int) -> None:
        """Clear the 'last watered' timestamp for ``zone``."""
        await self._async_command(self._url(f"/control?do=clear{int(zone)}"))

    async def _async_command(self, url: str) -> None:
        try:
            async with self._session.get(
                url,
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                # The panel answers control requests with a 302 redirect.
                if resp.status not in (200, 302):
                    resp.raise_for_status()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise HarvstConnectionError(
                f"Error sending command to {self._host}: {err}"
            ) from err

    async def async_get_device_id(self) -> str | None:
        """Return the panel's device id, or ``None`` if it can't be read."""
        try:
            async with self._session.get(
                self._url("/settings"),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise HarvstConnectionError(
                f"Error reading settings from {self._host}: {err}"
            ) from err

        match = DEVICE_ID_RE.search(text)
        return match.group(1).upper() if match else None
