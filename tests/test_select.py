"""Tests for the Hydronic select platform."""

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.components.select import (
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError
from modbus_connection import ModbusTimeoutError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hydronic.const import CONF_MODEL, DOMAIN
from custom_components.hydronic.hydronic_modbus import DeviceModel

from . import MOCK_ENTRY_DATA, seed_eco

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from modbus_connection.mock import MockModbusConnection, WriteEvent

OVERRIDE = "select.belimo_energy_valve_4_override_control"
LIMITATION = "select.belimo_energy_valve_4_delta_t_limitation"
BUS_FAIL = "select.belimo_energy_valve_4_bus_fail_action"


@pytest.mark.usefixtures("init_integration")
async def test_selects_read_the_settings(hass: HomeAssistant) -> None:
    """Test the selects show the valve's codes by name."""
    state = hass.states.get(OVERRIDE)
    assert state.state == "none"
    assert state.attributes["options"] == [
        "none",
        "open",
        "close",
        "minimum_flow",
        "maximum_flow",
        "nominal_flow",
        "motor_stop",
    ]
    assert hass.states.get(LIMITATION).state == "dt_manager"
    assert hass.states.get(BUS_FAIL).state == "close"


async def test_an_undocumented_code_is_unknown(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a code outside Belimo's enumeration shows as unknown."""
    mock_connection.for_unit(1).holding[1] = 4
    await init_integration.runtime_data.settings.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(OVERRIDE).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("entity_id", "option", "address", "words"),
    [
        (OVERRIDE, "motor_stop", 1, [10]),
        (LIMITATION, "disabled", 179, [0]),
        (BUS_FAIL, "minimum", 108, [4]),
    ],
)
async def test_select_option_writes_the_code(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    entity_id: str,
    option: str,
    address: int,
    words: list[int],
) -> None:
    """Test selecting an option writes its code."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )
    assert [(w.address, w.values) for w in writes] == [(address, words)]


@pytest.mark.usefixtures("init_integration")
async def test_select_option_the_device_refuses(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a failed write raises a translated error."""
    mock_connection.for_unit(1).fail_write(1, ModbusTimeoutError())
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: OVERRIDE, ATTR_OPTION: "open"},
            blocking=True,
        )
    assert err.value.translation_key == "write_failed"


async def test_eco_modes(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test the eco controller's modes are selects, a circuit's on its device."""
    seed_eco(mock_connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, CONF_MODEL: DeviceModel.ECO_CONTROLLER.value},
        title="ECO",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hydronic.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("select.eco_quick_select").state == "winter"
    assert hass.states.get("select.solar_mode").state == "automatic"
    assert hass.states.get("select.buffer_mode").state == "automatic_summer"
    assert hass.states.get("select.heating_circuit_1_mode").state == "automatic_1"

    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.heating_circuit_1_mode", ATTR_OPTION: "setback"},
        blocking=True,
    )
    assert [(w.address, w.values) for w in writes] == [(2118, [0, 4])]
