"""Tests for the Hydronic sensor platform."""

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)

from custom_components.hydronic.binary_sensor import _flag_set
from custom_components.hydronic.const import CONF_MODEL, DOMAIN
from custom_components.hydronic.hydronic_modbus import DeviceModel, create_device
from custom_components.hydronic.hydronic_modbus.eco.messages import (
    CIRCUIT_WARNINGS,
    message_text,
)
from custom_components.hydronic.hydronic_modbus.herz import InputByte1
from custom_components.hydronic.sensor import (
    SENSOR_DESCRIPTIONS,
    _error_value,
    _return_mixer,
)

from . import MOCK_ENTRY_DATA, int32_words, seed_belimo, seed_eco, seed_herz

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.helpers import entity_registry as er
    from syrupy.assertion import SnapshotAssertion

SEEDS: dict[DeviceModel, Callable[[MockModbusUnit], None]] = {
    DeviceModel.BELIMO_ENERGY_VALVE: seed_belimo,
    DeviceModel.ECO_CONTROLLER: seed_eco,
    DeviceModel.HERZ_PELLETSTAR: seed_herz,
}


async def _setup(
    hass: HomeAssistant, model: DeviceModel, platforms: list[Platform]
) -> MockConfigEntry:
    """Set up an entry for ``model`` with only ``platforms`` loaded."""
    connection = MockModbusConnection()
    SEEDS[model](connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, CONF_MODEL: model.value},
        title=model.value,
        entry_id=f"01J{model.name}",
    )
    entry.add_to_hass(hass)
    with (
        patch("custom_components.hydronic.PLATFORMS", platforms),
        patch(
            "custom_components.hydronic.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: connection.for_unit(
                unit_id
            ),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("model", list(DeviceModel))
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    model: DeviceModel,
) -> None:
    """Test all entities match their snapshot for every model."""
    entry = await _setup(hass, model, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


def test_sensor_descriptions_name_real_fields() -> None:
    """Guards SENSOR_DESCRIPTIONS against a component/field transcription slip."""
    for model in DeviceModel:
        device = create_device(model, MockModbusConnection().for_unit(1))
        for description in SENSOR_DESCRIPTIONS:
            if model not in description.models:
                continue
            component = getattr(device, description.component, None)
            if component is None:  # a circuit setup has not settled yet
                assert description.part is not None, description.key
                continue
            if description.value_fn is None:
                field = description.field or description.key
                assert hasattr(component, field), f"{description.key}: {field}"


async def test_total_restores_its_last_value(hass: HomeAssistant) -> None:
    """Test a total starts from its restored value and ignores a small dip."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("sensor.belimo_energy_valve_heating_energy", "99000"),
                {"native_value": 99000, "native_unit_of_measurement": "kWh"},
            )
        ],
    )
    await _setup(hass, DeviceModel.BELIMO_ENERGY_VALVE, [Platform.SENSOR])
    # The device reads 98765, within 1 % below the restored 99000: held.
    assert hass.states.get("sensor.belimo_energy_valve_heating_energy").state == "99000"


async def test_flow_follows_the_valve_unit(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test flow is reported in the unit selected on the valve."""
    state = hass.states.get("sensor.belimo_energy_valve_4_flow")
    assert state.state == "1.234"
    assert state.attributes["unit_of_measurement"] == "m³/h"


async def test_flow_without_a_unit_is_unavailable(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> None:
    """Test flow stays unavailable until the valve has said what unit it uses."""
    mock_connection.for_unit(1).fail_read(147, IllegalDataAddressError())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.belimo_energy_valve_4_flow").state == (
        STATE_UNAVAILABLE
    )


async def test_boiler_marks_missing_readings(hass: HomeAssistant) -> None:
    """Test readings the boiler marks as absent show as unknown."""
    entry = await _setup(hass, DeviceModel.HERZ_PELLETSTAR, [Platform.SENSOR])
    prefix = "sensor.herz_pelletstar"
    assert hass.states.get(f"{prefix}_residual_oxygen").state == STATE_UNKNOWN
    assert hass.states.get(f"{prefix}_carbon_dioxide").state == "10.5"
    assert hass.states.get(f"{prefix}_draught").state == "-15.0"

    unit = entry.runtime_data.device.modbus_unit
    unit.holding[86] = int32_words(-900000)  # -90000 Pa: no reading
    await entry.runtime_data.readings.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(f"{prefix}_draught").state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("outputs", "state"),
    [(0x88, "idle"), (0x10, "opening"), (0x20, "closing")],
)
async def test_boiler_return_mixer(
    hass: HomeAssistant, outputs: int, state: str
) -> None:
    """Test the return mixer reads as the direction it is driven in."""
    entry = await _setup(hass, DeviceModel.HERZ_PELLETSTAR, [Platform.SENSOR])
    entry.runtime_data.device.modbus_unit.holding[292] = int32_words(outputs)
    await entry.runtime_data.readings.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.herz_pelletstar_return_mixer").state == state


async def test_boiler_errors_use_its_texts(hass: HomeAssistant) -> None:
    """Test each error slot shows the boiler's text, or the code without one."""
    await _setup(hass, DeviceModel.HERZ_PELLETSTAR, [Platform.SENSOR])
    assert hass.states.get("sensor.herz_pelletstar_error_1").state == "STB"
    assert hass.states.get("sensor.herz_pelletstar_error_2").state == "217"
    assert hass.states.get("sensor.herz_pelletstar_error_3").state == "OK"


async def test_eco_messages_use_their_texts(hass: HomeAssistant) -> None:
    """Test the eco's codes show as texts, follow changes, and skip a refusal."""
    entry = await _setup(hass, DeviceModel.ECO_CONTROLLER, [Platform.SENSOR])
    assert (
        hass.states.get("sensor.heating_circuit_1_warning").state
        == "Anfahrentlastung aktiv"
    )
    assert hass.states.get("sensor.heating_circuit_1_alarm").state == "OK"
    assert hass.states.get("sensor.solar_warning").state == "Code 99"
    # circuit 2 refuses its message registers, so it has no message sensors
    assert hass.states.get("sensor.heating_circuit_2_warning") is None

    unit = entry.runtime_data.device.modbus_unit
    unit.holding[2130] = int32_words(2)  # circuit 1 alarm -> outdoor sensor missing
    unit.holding[2132] = int32_words(0)
    await entry.runtime_data.readings.async_refresh()
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.heating_circuit_1_alarm").state
        == "Außentemperatur nicht angeschlossen"
    )
    assert hass.states.get("sensor.heating_circuit_1_warning").state == "OK"


def test_message_text() -> None:
    """Test a code's text: OK for none, the code itself where none is known."""
    assert message_text(CIRCUIT_WARNINGS, 0) == "OK"
    assert message_text(CIRCUIT_WARNINGS, 2) == "Anfahrentlastung aktiv"
    assert message_text(CIRCUIT_WARNINGS, 42) == "Code 42"
    assert message_text(CIRCUIT_WARNINGS, None) is None


def test_values_before_the_first_read_are_unknown() -> None:
    """Test the derived values pass through a field that was never read."""
    assert _error_value(None) is None
    assert _return_mixer(None) is None
    assert (
        _flag_set("input_byte_1", InputByte1.ASH_DOOR_CLOSED)(
            SimpleNamespace(input_byte_1=None)
        )
        is None
    )
