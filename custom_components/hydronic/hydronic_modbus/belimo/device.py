"""The top-level object for a Belimo Energy Valve."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..model import DeviceModel, HydronicDevice
from .measurements import Meters, Power, Temperatures
from .status import DeltaTManager, Status
from .valve import BusFail, Units, ValveControl, ValvePosition

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit


class BelimoEnergyValve(HydronicDevice):
    """A Belimo Energy Valve 4 reached through a ``ModbusUnit``.

    Register numbers in Belimo's documentation start at 1; every address
    here is that number less one.
    """

    model = DeviceModel.BELIMO_ENERGY_VALVE
    READINGS = ("position", "temperatures", "power", "meters", "status")
    SETTINGS = ("control", "bus_fail", "delta_t_manager", "units")

    def __init__(self, unit: ModbusUnit, *, timeout: float | None = None) -> None:
        super().__init__(unit, timeout=timeout)
        self.control = ValveControl(unit)
        self.bus_fail = BusFail(unit)
        self.delta_t_manager = DeltaTManager(unit)
        self.units = Units(unit)
        self.position = ValvePosition(unit)
        self.temperatures = Temperatures(unit)
        self.power = Power(unit)
        self.meters = Meters(unit)
        self.status = Status(unit)
