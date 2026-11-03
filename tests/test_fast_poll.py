"""Tests for the fast poll: the eco circuits' mixers."""

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hydronic.const import (
    CONF_MODEL,
    DOMAIN,
    FAST_SCAN_INTERVAL,
)
from custom_components.hydronic.hydronic_modbus import DeviceModel

from . import MOCK_ENTRY_DATA, int32_words, seed_eco

if TYPE_CHECKING:
    from collections.abc import Generator

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from modbus_connection.mock import MockModbusConnection

MIXER_1 = "sensor.heating_circuit_1_mixer"
FLOW_1 = "sensor.heating_circuit_1_flow_temperature"


@pytest.fixture
def eco_entry(mock_connection: MockModbusConnection) -> Generator[MockConfigEntry]:
    """An eco controller entry, its units handed out on the mock connection."""
    seed_eco(mock_connection.for_unit(1))
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_ENTRY_DATA, CONF_MODEL: DeviceModel.ECO_CONTROLLER.value},
        title="ECO",
    )
    with patch(
        "custom_components.hydronic.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        yield entry


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the entry up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let one fast interval pass."""
    freezer.tick(timedelta(seconds=FAST_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_mixer_follows_the_fast_poll(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a mixer change shows after one fast interval, the readings not."""
    await setup(hass, eco_entry)
    assert eco_entry.runtime_data.fast is not None
    assert hass.states.get(MIXER_1).state == "closing"
    assert hass.states.get(FLOW_1).state == "34.5"

    unit = mock_connection.for_unit(1)
    unit.holding[2108] = int32_words(1)
    unit.holding[2100] = int32_words(400)
    await tick(hass, freezer)
    assert hass.states.get(MIXER_1).state == "opening"
    assert hass.states.get(FLOW_1).state == "34.5"


async def test_a_tick_during_a_slow_poll_is_skipped(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a poll still running makes the next tick skip, not queue."""
    await setup(hass, eco_entry)
    fast = eco_entry.runtime_data.fast
    assert fast is not None
    release = asyncio.Event()
    calls = 0

    async def slow_refresh() -> None:
        nonlocal calls
        calls += 1
        await release.wait()

    with patch.object(fast, "async_refresh", slow_refresh):
        freezer.tick(timedelta(seconds=FAST_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await asyncio.sleep(0)
        freezer.tick(timedelta(seconds=FAST_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await asyncio.sleep(0)
        assert calls == 1
        release.set()
        await hass.async_block_till_done()
        await tick(hass, freezer)
        assert calls == 2


async def test_unload_stops_the_fast_poll(
    hass: HomeAssistant,
    eco_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test no fast poll runs once the entry is unloaded."""
    await setup(hass, eco_entry)
    assert await hass.config_entries.async_unload(eco_entry.entry_id)
    await hass.async_block_till_done()
    unit = mock_connection.for_unit(1)
    unit.read_events.clear()
    await tick(hass, freezer)
    assert not unit.read_events


async def test_a_device_without_fast_components_gets_no_fast_poll(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the Belimo valve has no fast coordinator."""
    assert init_integration.runtime_data.fast is None
    assert len(init_integration.runtime_data.coordinators) == 2
