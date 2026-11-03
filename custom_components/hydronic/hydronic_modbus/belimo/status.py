"""The valve's error state and its Delta T manager."""

from __future__ import annotations

from modbus_connection.model import enum, flags, gauge

from ..model import HydronicComponent, in_range
from .enums import DeltaTLimitation, DeltaTManagerStatus, Malfunction


class Status(HydronicComponent):
    """What the valve reports about itself."""

    malfunction = flags(157, Malfunction, count=2)
    """Malfunction and service bits, high word first (firmware 4.2)."""
    delta_t_manager_status = enum(180, DeltaTManagerStatus)
    """What the Delta T manager is doing."""

    @property
    def has_error(self) -> bool | None:
        """Whether any error bit is set; ``None`` until the first poll."""
        if self.malfunction is None:
            return None
        return bool(self.malfunction)


class DeltaTManager(HydronicComponent):
    """The Delta T manager's target and mode, registers 40 and 180."""

    delta_t_setpoint = gauge(39, 0.01, unit="K", writable=in_range(0, 1000))
    """The temperature difference the Delta T manager aims for."""
    delta_t_limitation = enum(179, DeltaTLimitation, writable=True)
    """Whether, and how, the Delta T manager may throttle the valve."""

    async def async_write_delta_t_setpoint(self, kelvin: float) -> None:
        """Set the temperature difference the Delta T manager aims for."""
        await self.write("delta_t_setpoint", kelvin)

    async def async_write_delta_t_limitation(self, mode: DeltaTLimitation) -> None:
        """Set whether, and how, the Delta T manager may throttle the valve."""
        await self.write("delta_t_limitation", DeltaTLimitation(mode))
