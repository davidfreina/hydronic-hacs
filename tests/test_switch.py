"""Tests for the Hydronic switch platform and the eco circuits' external control."""

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from modbus_connection import ModbusTimeoutError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
)

from custom_components.hydronic.const import (
    CONF_MODEL,
    DOMAIN,
    KEEPALIVE_INTERVAL,
)
from custom_components.hydronic.hydronic_modbus import DeviceModel

from . import MOCK_ENTRY_DATA, seed_eco

if TYPE_CHECKING:
    from collections.abc import Generator

    from freezegun.api import FrozenDateTimeFactory
    from modbus_connection.mock import MockModbusConnection, WriteEvent

KEEPALIVE = "switch.eco_external_keep_alive"
RELEASE_1 = "switch.heating_circuit_1_release"
RELEASE_3 = "switch.heating_circuit_3_release"
GLT_3 = "switch.heating_circuit_3_external_control_glt"
SETPOINT_3 = "number.heating_circuit_3_external_flow_setpoint"


@pytest.fixture
def eco_connection(mock_connection: MockModbusConnection) -> MockModbusConnection:
    """The mock connection seeded as an eco controller."""
    seed_eco(mock_connection.for_unit(1))
    return mock_connection


@pytest.fixture
def eco_entry() -> MockConfigEntry:
    """An eco controller config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, CONF_MODEL: DeviceModel.ECO_CONTROLLER.value},
        title="ECO",
        entry_id="01JECO_CONTROLLER",
    )


@pytest.fixture
def get_unit(eco_connection: MockModbusConnection) -> Generator[None]:
    """Hand out units on the eco connection."""
    with patch(
        "custom_components.hydronic.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: eco_connection.for_unit(
            unit_id
        ),
    ):
        yield


async def setup_eco(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the eco controller entry up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let one keep-alive interval pass."""
    freezer.tick(timedelta(seconds=KEEPALIVE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def keepalive_writes(writes: list[WriteEvent]) -> list[list[int]]:
    """The values written to the external keep-alive."""
    return [w.values for w in writes if w.address == 8]


@pytest.mark.usefixtures("get_unit")
async def test_circuit_control_reads_the_settings(
    hass: HomeAssistant, eco_entry: MockConfigEntry
) -> None:
    """Test the circuit switches and setpoint show what the controller holds."""
    await setup_eco(hass, eco_entry)
    assert hass.states.get(RELEASE_1).state == STATE_OFF
    assert hass.states.get(RELEASE_3).state == STATE_ON
    assert hass.states.get(GLT_3).state == STATE_ON
    assert hass.states.get(SETPOINT_3).state == "42.5"
    assert hass.states.get(KEEPALIVE).state == STATE_OFF


@pytest.mark.parametrize(
    ("entity_id", "service", "address", "words", "expected"),
    [
        (RELEASE_1, SERVICE_TURN_ON, 2122, [0, 1], STATE_ON),
        (RELEASE_3, SERVICE_TURN_OFF, 2322, [0, 0], STATE_OFF),
        (GLT_3, SERVICE_TURN_OFF, 2336, [0, 0], STATE_OFF),
    ],
)
@pytest.mark.usefixtures("get_unit")
async def test_circuit_switch_writes_the_register(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    eco_connection: MockModbusConnection,
    entity_id: str,
    service: str,
    address: int,
    words: list[int],
    expected: str,
) -> None:
    """Test a circuit switch writes 1 or 0 and reads it back."""
    await setup_eco(hass, eco_entry)
    writes: list[WriteEvent] = []
    eco_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert [(w.address, w.values) for w in writes] == [(address, words)]
    assert hass.states.get(entity_id).state == expected


@pytest.mark.usefixtures("get_unit")
async def test_circuit_switch_the_device_refuses(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    eco_connection: MockModbusConnection,
) -> None:
    """Test a failed write raises a translated error."""
    await setup_eco(hass, eco_entry)
    eco_connection.for_unit(1).fail_write(2122, ModbusTimeoutError())
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: RELEASE_1}, blocking=True
        )
    assert err.value.translation_key == "write_failed"


@pytest.mark.usefixtures("get_unit")
async def test_external_flow_setpoint_writes_tenths(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    eco_connection: MockModbusConnection,
) -> None:
    """Test the external setpoint writes tenths of a degree."""
    await setup_eco(hass, eco_entry)
    writes: list[WriteEvent] = []
    eco_connection.for_unit(1).on_write(writes.append)
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: SETPOINT_3, ATTR_VALUE: 45.5},
        blocking=True,
    )
    assert [(w.address, w.values) for w in writes] == [(2324, [0, 455])]


@pytest.mark.usefixtures("get_unit")
async def test_keepalive_beats_while_on(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    eco_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the keep-alive alternates 1 and 2 while on, and stops when off."""
    await setup_eco(hass, eco_entry)
    writes: list[WriteEvent] = []
    eco_connection.for_unit(1).on_write(writes.append)

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: KEEPALIVE}, blocking=True
    )
    assert hass.states.get(KEEPALIVE).state == STATE_ON
    await tick(hass, freezer)
    await tick(hass, freezer)
    assert keepalive_writes(writes) == [[0, 2], [0, 1], [0, 2]]

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: KEEPALIVE}, blocking=True
    )
    assert hass.states.get(KEEPALIVE).state == STATE_OFF
    await tick(hass, freezer)
    assert len(keepalive_writes(writes)) == 3


@pytest.mark.usefixtures("get_unit")
async def test_keepalive_resumes_after_a_restart(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    eco_connection: MockModbusConnection,
) -> None:
    """Test a keep-alive left on starts beating again when the entry sets up."""
    mock_restore_cache(hass, [State(KEEPALIVE, STATE_ON)])
    writes: list[WriteEvent] = []
    eco_connection.for_unit(1).on_write(writes.append)
    await setup_eco(hass, eco_entry)
    assert hass.states.get(KEEPALIVE).state == STATE_ON
    assert keepalive_writes(writes) == [[0, 2]]


@pytest.mark.usefixtures("get_unit")
async def test_keepalive_logs_a_failure_once(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    eco_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failing keep-alive warns once, then says when it recovers."""
    await setup_eco(hass, eco_entry)
    unit = eco_connection.for_unit(1)
    unit.fail_write(8, ModbusTimeoutError())
    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: KEEPALIVE}, blocking=True
    )
    await tick(hass, freezer)
    assert caplog.text.count("failed to send the external keep-alive") == 1

    unit.fail_write(8, None)
    await tick(hass, freezer)
    assert "external keep-alive sent again" in caplog.text
