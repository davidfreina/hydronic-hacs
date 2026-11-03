"""Tests for the Hydronic diagnostics."""

from typing import TYPE_CHECKING

from modbus_connection import ModbusConnectionError
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from modbus_connection.mock import MockModbusConnection
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
    from syrupy.assertion import SnapshotAssertion


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert diag == snapshot


async def test_diagnostics_when_the_device_is_gone(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a failed read still produces a download, naming the error."""
    mock_connection.for_unit(1).fail_requests(ModbusConnectionError())
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    assert diag["read_error"] == "ModbusConnectionError"
    assert diag["raw"] is None
