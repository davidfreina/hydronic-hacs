"""The controller as a whole: its heartbeat, the outside, the quick select."""

from __future__ import annotations

from modbus_connection.model import enum, int32

from ..model import HydronicComponent, in_range
from .enums import QuickSelectMode


class System(HydronicComponent):
    """The controller's heartbeat and outdoor temperature."""

    keepalive = int32(0)
    """A counter the controller keeps moving while it runs."""
    outdoor_temperature = int32(20, scale=0.1, unit="°C")
    """Outdoor temperature."""


class QuickSelect(HydronicComponent):
    """The controller-wide operating mode, register 7."""

    quick_select = enum(6, QuickSelectMode, count=2, writable=True)
    """The quick-select mode: winter, summer or absent."""

    async def async_write_quick_select(self, mode: QuickSelectMode) -> None:
        """Switch the controller to another quick-select mode."""
        await self.write("quick_select", QuickSelectMode(mode))


class ExternalKeepAlive(HydronicComponent):
    """The heartbeat an external controller has to keep up, register 9.

    While a building management system controls the controller, this has to
    change between 1 and 2 at least every 30 seconds; otherwise the
    controller raises an alarm.
    """

    value = int32(8, writable=in_range(1, 2))
    """The value as last read: 1 or 2, 0 before anyone wrote it."""

    _last_beat: int | None = None

    async def async_beat(self) -> int:
        """Write the other of 1 and 2 than last time, and return it.

        Without a beat of its own yet, it goes by the value last read.
        """
        last = self._last_beat if self._last_beat is not None else self.value
        beat = 1 if last == 2 else 2
        await self.write("value", beat)
        self._last_beat = beat
        return beat
