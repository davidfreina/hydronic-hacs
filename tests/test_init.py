"""Tests for the Hydronic integration setup."""

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr
from modbus_connection import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusTcpParams,
)
from modbus_connection.mock import MockModbusConnection
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hydronic.const import CONF_MODEL, DOMAIN, SCAN_INTERVAL
from custom_components.hydronic.hydronic_modbus import DeviceModel

from . import MOCK_ENTRY_DATA, seed_eco

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant


async def test_setup_and_unload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test the entry sets up on a shared unit and unloads."""
    assert init_integration.state is ConfigEntryState.LOADED
    mock_get_unit.assert_called_once()
    _, entry, params, unit_id = mock_get_unit.call_args.args
    assert entry is init_integration
    assert params == ModbusTcpParams(host="192.168.1.100", port=502)
    assert unit_id == 1

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("error", [ModbusConnectionError(), IllegalDataAddressError()])
async def test_setup_retries_an_unreachable_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    mock_get_unit: MagicMock,
    error: Exception,
) -> None:
    """Test a device that answers nothing sets up later."""
    mock_connection.for_unit(1).fail_requests(error)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_device_registry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device is registered under its entry."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, init_integration.entry_id), init_integration.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Belimo"
    assert device.model == "Energy Valve 4"
    assert device.name == "Belimo Energy Valve 4"


async def test_eco_parts_are_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test solar, the buffer and each circuit become devices of their own."""
    connection = MockModbusConnection()
    unit = connection.for_unit(1)
    seed_eco(unit)
    unit.fail_read(2200, IllegalDataAddressError())  # no circuit 2
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, CONF_MODEL: DeviceModel.ECO_CONTROLLER.value},
        title="eco",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hydronic.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: connection.for_unit(unit_id),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert parent is not None
    parts = {
        identifier
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if device.via_device_id == parent.id
        for _, identifier in device.identifiers
    }
    assert parts == {
        f"{entry.entry_id}_solar",
        f"{entry.entry_id}_buffer",
        f"{entry.entry_id}_heating_circuit_1",
        f"{entry.entry_id}_heating_circuit_3",
    }


async def test_failed_component_goes_unavailable_and_recovers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test one refused block takes only its own entities down."""
    entity_id = "sensor.belimo_energy_valve_4_remote_temperature_t1"
    assert hass.states.get(entity_id).state == "45.5"

    unit = mock_connection.for_unit(1)
    unit.fail_read(19, IllegalDataAddressError())
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.belimo_energy_valve_4_valve_position").state == (
        "63.12"
    )
    assert "temperatures failed to refresh" in caplog.text

    unit.fail_read(19, None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "45.5"
    assert "temperatures is available again" in caplog.text


async def test_dead_link_marks_everything_unavailable_but_totals(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a dropped link takes measurements down, but totals hold."""
    mock_connection.for_unit(1).fail_requests(ModbusConnectionError())
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.belimo_energy_valve_4_valve_position").state
        == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.belimo_energy_valve_4_heating_energy").state == "98765"
    )
