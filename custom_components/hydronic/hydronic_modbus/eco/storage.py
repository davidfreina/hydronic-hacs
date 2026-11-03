"""Storage (Puffer) module 1, the block at 1000 + 100.

One storage tank with its circulation and tap: ENERGIEFREUND's parameter
list describes the whole block as a single module. Temperatures are whole
degrees.
"""

from __future__ import annotations

from modbus_connection.model import enum, int32

from ..model import HydronicComponent
from .enums import BufferOperatingMode


class Buffer(HydronicComponent):
    """The storage tank's sensors, pumps and its circulation."""

    top_temperature = int32(1100, unit="°C")
    """Temperature at the top of the tank (Puffertemperatur Oben)."""
    top_1_temperature = int32(1102, unit="°C")
    """The second sensor near the top (Puffertemperatur Oben 1)."""
    middle_temperature = int32(1104, unit="°C")
    """Temperature in the middle of the tank."""
    bottom_temperature = int32(1106, unit="°C")
    """Temperature at the bottom of the tank."""
    setpoint = int32(1108, unit="°C")
    """The temperature the tank is asked for (Anforderungstemperatur)."""
    electric_heater = int32(1110)
    """Electric heater (E-Patrone); 1 while it heats."""
    charging_pump = int32(1112)
    """Buffer charging pump (Pufferladepumpe); 1 while it runs."""
    circulation_temperature = int32(1114, unit="°C")
    """Temperature in the circulation return."""
    circulation_pump = int32(1116)
    """Circulation pump; 1 while it runs."""
    tap_temperature = int32(1144, unit="°C")
    """Temperature at the tap (Zapftemperatur)."""


class BufferMode(HydronicComponent):
    """The storage tank's operating mode for heating, register 1121."""

    mode = enum(1120, BufferOperatingMode, count=2, writable=True)
    """Operating mode."""

    async def async_write_mode(self, mode: BufferOperatingMode) -> None:
        """Switch the tank to another operating mode."""
        await self.write("mode", BufferOperatingMode(mode))
