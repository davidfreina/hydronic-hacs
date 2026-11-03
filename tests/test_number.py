"""Tests for the Hydronic number platform."""

from typing import TYPE_CHECKING

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from modbus_connection import ModbusTimeoutError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from modbus_connection.mock import MockModbusConnection, WriteEvent
    from pytest_homeassistant_custom_component.common import MockConfigEntry

SETPOINT = "number.belimo_energy_valve_4_setpoint"
DELTA_T = "number.belimo_energy_valve_4_delta_t_setpoint"


@pytest.mark.usefixtures("init_integration")
async def test_numbers_read_the_settings(hass: HomeAssistant) -> None:
    """Test the numbers show what the settings poll read."""
    assert hass.states.get(SETPOINT).state == "65.5"
    assert hass.states.get(DELTA_T).state == "10.0"


@pytest.mark.parametrize(
    ("entity_id", "value", "address", "words"),
    [
        (SETPOINT, 42.5, 0, [4250]),
        (DELTA_T, 12.5, 39, [1250]),
    ],
)
async def test_set_value_writes_the_register(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_connection: MockModbusConnection,
    entity_id: str,
    value: float,
    address: int,
    words: list[int],
) -> None:
    """Test setting a number writes its register and reads it back."""
    writes: list[WriteEvent] = []
    mock_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    assert [(w.address, w.values) for w in writes] == [(address, words)]


@pytest.mark.usefixtures("init_integration")
async def test_set_value_the_device_refuses(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a failed write raises a translated error."""
    mock_connection.for_unit(1).fail_write(0, ModbusTimeoutError())
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: SETPOINT, ATTR_VALUE: 10},
            blocking=True,
        )
    assert err.value.translation_key == "write_failed"


@pytest.mark.usefixtures("init_integration")
async def test_set_value_the_library_refuses(hass: HomeAssistant) -> None:
    """Test a value the library will not encode raises a validation error."""
    entity = hass.data["entity_components"][NUMBER_DOMAIN].get_entity(DELTA_T)
    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_native_value(2000)  # beyond 1000 K
    assert err.value.translation_key == "invalid_value"
