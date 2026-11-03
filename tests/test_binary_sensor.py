"""Tests for the Hydronic binary sensor platform."""

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hydronic.const import CONF_MODEL, DOMAIN
from custom_components.hydronic.hydronic_modbus import DeviceModel

from . import MOCK_ENTRY_DATA, int32_words, seed_belimo, seed_eco, seed_herz

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant


async def _setup(
    hass: HomeAssistant,
    model: DeviceModel,
    seed: Callable[[MockModbusUnit], None],
    title: str,
) -> tuple[MockConfigEntry, MockModbusUnit]:
    """Set up ``model`` with only the binary sensor platform."""
    connection = MockModbusConnection()
    unit = connection.for_unit(1)
    seed(unit)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, CONF_MODEL: model.value},
        title=title,
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.hydronic.PLATFORMS", [Platform.BINARY_SENSOR]),
        patch(
            "custom_components.hydronic.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: connection.for_unit(
                unit_id
            ),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, unit


async def test_valve_malfunction_bits(hass: HomeAssistant) -> None:
    """Test each of the valve's malfunction bits is its own problem sensor."""
    entry, unit = await _setup(
        hass, DeviceModel.BELIMO_ENERGY_VALVE, seed_belimo, "Valve"
    )
    reverse = "binary_sensor.valve_reverse_flow"
    watchdog = "binary_sensor.valve_bus_watchdog_triggered"
    assert hass.states.get(reverse).state == STATE_OFF

    unit.holding[157] = int32_words(0x0000_8008)
    await entry.runtime_data.readings.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(reverse).state == STATE_ON
    assert hass.states.get(watchdog).state == STATE_ON
    assert hass.states.get("binary_sensor.valve_freeze_warning").state == STATE_OFF


@pytest.mark.parametrize(
    ("entity_id", "state"),
    [
        ("binary_sensor.boiler_problem", STATE_ON),  # collective fault
        ("binary_sensor.boiler_return_pump", STATE_ON),
        # Energised while there is no alarm, so set means no problem.
        ("binary_sensor.boiler_alarm_output", STATE_OFF),
        # Set while the monitor is satisfied, so set means safe.
        ("binary_sensor.boiler_overtemperature_output", STATE_OFF),
        ("binary_sensor.boiler_hopper_empty", STATE_ON),
        # Clear means the limiter has tripped.
        ("binary_sensor.boiler_safety_temperature_limiter", STATE_ON),
        # The input reports the door closed; clear means open.
        ("binary_sensor.boiler_ash_door", STATE_ON),
    ],
)
async def test_boiler_io_bits(hass: HomeAssistant, entity_id: str, state: str) -> None:
    """Test the boiler's I/O bits, inverted where the boiler sets them when fine."""
    await _setup(hass, DeviceModel.HERZ_PELLETSTAR, seed_herz, "Boiler")
    assert hass.states.get(entity_id).state == state


async def test_boiler_fault_clears(hass: HomeAssistant) -> None:
    """Test the collective fault drives the boiler's problem sensor."""
    entry, unit = await _setup(hass, DeviceModel.HERZ_PELLETSTAR, seed_herz, "Boiler")
    unit.holding[92] = int32_words(0)
    await entry.runtime_data.readings.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.boiler_problem").state == STATE_OFF


async def test_eco_pumps(hass: HomeAssistant) -> None:
    """Test a pump output above zero reads as running."""
    await _setup(hass, DeviceModel.ECO_CONTROLLER, seed_eco, "ECO")
    assert hass.states.get("binary_sensor.buffer_circulation_pump").state == STATE_ON
    assert hass.states.get("binary_sensor.solar_collector_pump").state == STATE_OFF
    assert hass.states.get("binary_sensor.heating_circuit_1_pump").state == STATE_ON
    assert hass.states.get("binary_sensor.heating_circuit_3_pump").state == STATE_OFF
