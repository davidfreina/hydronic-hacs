"""Diagnostics support for Hydronic devices."""

from typing import TYPE_CHECKING, Any

from modbus_connection import ModbusError

from .const import CONF_MODEL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import HydronicConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HydronicConfigEntry
) -> dict[str, Any]:
    """
    Return diagnostics for a config entry.

    No register these devices serve holds personal information, so the raw
    map goes out whole.
    """
    runtime_data = entry.runtime_data
    device = runtime_data.device
    raw = read_error = None
    try:
        raw = await device.async_read_raw()
    except ModbusError as err:
        read_error = type(err).__name__

    return {
        "model": entry.data[CONF_MODEL],
        "readings_components": device.readings_components,
        "settings_components": device.settings_components,
        "fast_components": device.fast_components,
        "failed": {
            name: type(err).__name__
            for coordinator in runtime_data.coordinators
            if coordinator.data is not None
            for name, err in coordinator.data.failed.items()
        },
        "read_error": read_error,
        "raw": raw,
    }
