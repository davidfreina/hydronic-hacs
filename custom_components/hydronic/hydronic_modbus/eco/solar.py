"""The solar thermal circuit, solar module 1 at 8000 + 100.

Temperatures in this block are whole degrees on a controller running
v5.00.30, although ENERGIEFREUND's parameter list gives tenths.
"""

from __future__ import annotations

from modbus_connection.model import enum, float32, int32

from ..model import HydronicComponent
from .enums import SolarOperatingMode


class Solar(HydronicComponent):
    """What the solar circuit measures."""

    collector_temperature = int32(0x1FA4, unit="°C")
    """Collector temperature."""
    storage_temperature = int32(0x1FA8, unit="°C")
    """Temperature of the store the collector charges."""
    collector_return_temperature = int32(0x1FB0, unit="°C")
    """Return temperature to the collector."""
    pump = int32(0x1FB2)
    """Collector pump output; anything above 0 means it runs."""
    power = float32(0x1FBE, scale=1000, unit="W")
    """Thermal power the collector delivers; the register holds kW."""


class SolarMode(HydronicComponent):
    """The solar circuit's operating mode."""

    mode = enum(0x1FC0, SolarOperatingMode, count=2, writable=True)
    """Operating mode.

    The parameter list has 1 automatic and 2 manual, but a controller on
    v5.00.30 showing automatic on its display reports 2.
    """

    async def async_write_mode(self, mode: SolarOperatingMode) -> None:
        """Switch the solar circuit to another operating mode."""
        await self.write("mode", SolarOperatingMode(mode))
