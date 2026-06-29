"""Pytest configuration for the Harvst tests."""

from __future__ import annotations

import contextlib

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(scope="session", autouse=True)
def _warmup_dns_resolver():
    """Pre-spawn the aiodns/pycares resolver thread before tests run.

    Newer pycares releases (>=4.5) start a persistent daemon thread the first
    time an ``AsyncResolver`` is constructed, which happens implicitly when any
    ``aiohttp.ClientSession`` is created (including the mocked sessions used by
    the Home Assistant test harness). The harness' ``verify_cleanup`` fixture
    snapshots the running threads at the start of each test and fails if a new
    non-dummy thread appears during the test. Creating the resolver once here,
    before any per-test snapshot is taken, ensures the thread is already part of
    the baseline and is therefore never flagged as a leak.
    """
    try:
        from aiohttp.resolver import AsyncResolver
    except Exception:  # pragma: no cover - aiodns not installed
        yield
        return

    with contextlib.suppress(Exception):  # pragma: no cover - resolver unavailable
        AsyncResolver()
    yield


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    yield


# A representative idle reading from the panel's /events stream.
IDLE_READING = (
    '{"te":22,"teAve":14.66667,"ti":-13,"ta":-13,"h":-13,"isr":0,'
    '"ts_1":-13,"ts_2":-13,"s1":-13,"s2":-13,"x1":0,"x2":0,"x3":0,"cc":100}'
)
# A reading captured while the pump is running.
PUMPING_READING = (
    '{"pump_state":1,"te":22,"teAve":14.66667,"ti":-13,"ta":-13,"h":-13,'
    '"isr":0,"ts_1":-13,"ts_2":-13,"s1":-13,"s2":-13,"x1":0,"x2":0,"x3":0,'
    '"cc":-4104}'
)

SSE_IDLE = (
    "retry: 10000\n"
    "id: 1\n"
    "data: hello!\n\n"
    "id: 2\n"
    "event: new_readings\n"
    f"data: {IDLE_READING}\n\n"
)

SETTINGS_HTML = """
<html><body>
<div class="box"><div class="device-id">Device ID: <div>A84467B865E4</div></div></div>
<table class="table-data"><tbody>
<tr><td>Pump back pressure</td><td>56 / 4712</td></tr>
<tr><td>Pump detection</td><td>Pump OK</td></tr>
<tr><td>Battery volts</td><td>0.00 V</td></tr>
</tbody></table>
</body></html>
"""


@pytest.fixture
def host() -> str:
    """Return a test host."""
    return "192.168.2.172"
