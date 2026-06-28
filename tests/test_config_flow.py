"""Tests for the Harvst config flow."""

from __future__ import annotations

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.harvst.const import CONF_HOST, DOMAIN

from .conftest import SETTINGS_HTML, SSE_IDLE


def _mock_panel(aioclient_mock, host: str) -> None:
    aioclient_mock.get(f"http://{host}/events", text=SSE_IDLE)
    aioclient_mock.get(f"http://{host}/settings", text=SETTINGS_HTML)


async def test_user_flow_success(hass: HomeAssistant, aioclient_mock, host):
    """A reachable panel creates a config entry keyed by device id."""
    _mock_panel(aioclient_mock, host)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host}
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: host}
    assert result["result"].unique_id == "A84467B865E4"


async def test_user_flow_cannot_connect(hass: HomeAssistant, aioclient_mock, host):
    """An unreachable panel surfaces a cannot_connect error."""
    aioclient_mock.get(f"http://{host}/events", exc=TimeoutError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_duplicate_aborts(hass: HomeAssistant, aioclient_mock, host):
    """Configuring the same panel twice aborts."""
    _mock_panel(aioclient_mock, host)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_HOST: host})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
