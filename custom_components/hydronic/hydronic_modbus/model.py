"""The pieces every device family builds on."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

from modbus_connection.model import Component, Device, Raw, UpdateReport

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

__all__ = [
    "CONNECT_DELAY",
    "DeviceModel",
    "HydronicComponent",
    "HydronicDevice",
    "UpdateReport",
    "in_range",
]

CONNECT_DELAY = 0.05
"""Seconds every supported device is given to settle after the link opens.

The configurations these maps come from all waited 50 ms before their
first request.
"""


class DeviceModel(StrEnum):
    """The device families this library speaks to."""

    BELIMO_ENERGY_VALVE = "belimo_energy_valve"
    ECO_CONTROLLER = "eco_controller"
    HERZ_PELLETSTAR = "herz_pelletstar"


class HydronicComponent(Component):
    """A sub-system of one of the supported devices.

    ``max_gap`` is 0: a read covers adjacent registers only and never
    bridges a gap, since nothing is known about whether a device answers
    the registers between two mapped ones. A family that knows its map
    declares ``register_ranges`` instead.
    """

    max_gap = 0


def in_range(low: float, high: float) -> Callable[[Any], Any]:
    """A write validator refusing a value outside ``low``-``high``."""

    def validate(value: Any) -> Any:
        if not low <= float(value) <= high:
            raise ValueError(f"{value} is outside {low}-{high}")
        return value

    return validate


class HydronicDevice(Device):
    """A device reached through a ``ModbusUnit``, polled by category.

    Each family lists its sub-systems by attribute name: what the device
    measures (``READINGS``), what it has been told to do (``SETTINGS``) and
    what changes too quickly for the readings' pace (``FAST``), such as a
    mixer being driven in short pulses. A sub-system the caller did not ask
    for is ``None`` and is skipped.
    """

    model: ClassVar[DeviceModel]
    READINGS: ClassVar[tuple[str, ...]] = ()
    SETTINGS: ClassVar[tuple[str, ...]] = ()
    FAST: ClassVar[tuple[str, ...]] = ()

    def __init__(self, unit: ModbusUnit, *, timeout: float | None = None) -> None:
        super().__init__(unit)
        unit.require_timeout(timeout)
        unit.require_connect_delay(CONNECT_DELAY)

    def _readings(self) -> tuple[str, ...]:
        """Every reading this device might poll; a family may compute it."""
        return self.READINGS

    def _settings(self) -> tuple[str, ...]:
        """Every setting this device might poll; a family may compute it."""
        return self.SETTINGS

    def _fast(self) -> tuple[str, ...]:
        """Every fast reading this device might poll; a family may compute it."""
        return self.FAST

    def _served(self, names: Iterable[str]) -> list[str]:
        """The names among ``names`` this device instance has."""
        return [name for name in names if getattr(self, name, None) is not None]

    @property
    def readings_components(self) -> list[str]:
        """What ``async_update_readings()`` polls, by attribute name.

        Before the first poll, this is what setup will probe for.
        """
        return self._served(self._readings())

    @property
    def settings_components(self) -> list[str]:
        """What ``async_update_settings()`` polls, by attribute name."""
        return self._served(self._settings())

    @property
    def fast_components(self) -> list[str]:
        """What ``async_update_fast()`` polls, by attribute name.

        Before the first poll, this is what setup will probe for.
        """
        return self._served(self._fast())

    @property
    def components(self) -> list[str]:
        """Every sub-system this device polls, in any group."""
        return [
            *self.readings_components,
            *self.settings_components,
            *self.fast_components,
        ]

    def component(self, name: str) -> HydronicComponent:
        """The sub-system an attribute name stands for.

        Raises ``KeyError`` for a name this device does not poll.
        """
        if name not in self.components:
            raise KeyError(name)
        component: HydronicComponent = getattr(self, name)
        return component

    async def async_update_readings(self) -> UpdateReport:
        """Refresh what the device measures.

        A dead link (``ModbusConnectionError``) raises, and so does a
        timeout before any sub-system has answered.
        """
        return await self.async_poll(self.readings_components)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh what the device has been configured to do.

        Run one after a write to read back what took effect.
        """
        return await self.async_poll(self.settings_components)

    async def async_update_fast(self) -> UpdateReport:
        """Refresh what changes faster than the readings are polled."""
        return await self.async_poll(self.fast_components)

    async def async_update(self) -> UpdateReport:
        """Refresh every group, in one merged report."""
        report = await self.async_poll(self.readings_components)
        report = await self.async_poll(self.fast_components, report)
        return await self.async_poll(self.settings_components, report)

    async def async_read_raw(self, names: Iterable[str] | None = None) -> Raw:
        """Every register this device reads, undecoded, for diagnostics.

        Nothing notifies here: a diagnostics download is not a poll.
        """
        if names is None:
            names = self.components
        return await super().async_read_raw(names)
