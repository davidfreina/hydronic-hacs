"""Integrate hydronic heating devices into Home Assistant."""

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_MODEL,
    CONF_UNIT_ID,
    FAST_SCAN_INTERVAL,
    SCAN_INTERVAL,
    SETTINGS_SCAN_INTERVAL,
)
from .coordinator import HydronicDataUpdateCoordinator
from .data import HydronicConfigEntry, HydronicRuntimeData
from .helpers import create_modbus_params
from .hydronic_modbus import create_device

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: HydronicConfigEntry) -> bool:
    """Set up a hydronic device from a config entry."""
    unit = async_get_unit(
        hass,
        entry,
        create_modbus_params(entry.data),
        entry.data[CONF_UNIT_ID],
    )
    device = create_device(entry.data[CONF_MODEL], unit)

    readings = HydronicDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_readings,
        timedelta(seconds=SCAN_INTERVAL),
    )
    settings = HydronicDataUpdateCoordinator(
        hass,
        entry,
        device,
        device.async_update_settings,
        timedelta(seconds=SETTINGS_SCAN_INTERVAL),
    )
    # The first readings poll also settles which sub-systems the device has.
    await readings.async_config_entry_first_refresh()
    await settings.async_config_entry_first_refresh()
    # Only a device with something that changes fast gets the fast poll.
    fast = None
    if device.fast_components:
        fast = HydronicDataUpdateCoordinator(
            hass, entry, device, device.async_update_fast, None
        )
        await fast.async_config_entry_first_refresh()
        _start_fast_poll(hass, entry, fast)

    # Up front: a part's device must name a device that has an id.
    parent = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **readings.device_info
    )
    entry.runtime_data = HydronicRuntimeData(readings, settings, parent.id, fast)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _start_fast_poll(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    fast: HydronicDataUpdateCoordinator,
) -> None:
    """
    Refresh the fast coordinator on a steady sub-second timer.

    A coordinator's own interval is rounded to whole seconds, which runs a
    sub-second one back to back for most of each second. A tick that finds
    the previous poll still running is skipped, so a slow link cannot queue
    polls up.
    """
    busy = asyncio.Lock()

    async def _async_refresh(_now: datetime) -> None:
        if busy.locked():
            return
        async with busy:
            await fast.async_refresh()

    entry.async_on_unload(
        async_track_time_interval(
            hass,
            _async_refresh,
            timedelta(seconds=FAST_SCAN_INTERVAL),
            name=f"{entry.title} fast poll",
            cancel_on_shutdown=True,
        )
    )


async def async_unload_entry(hass: HomeAssistant, entry: HydronicConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
