"""The top-level object for a HERZ pelletstar boiler."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from ..model import DeviceModel, HydronicDevice
from .boiler import Boiler, Combustion, Fuel, OperatingHours
from .faults import Faults, InputsOutputs
from .modules import (
    BUFFER_BASE,
    HOT_WATER_BASE,
    SOLAR_BASE,
    HerzBuffer,
    HerzHeatingCircuit,
    HerzHotWater,
    HerzSolar,
    heating_circuit_base,
)

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit


def module_circuit_name(number: int) -> str:
    """The attribute heating circuit module ``number`` lives on."""
    return f"heating_circuit_{number}"


class HerzPelletstar(HydronicDevice):
    """A HERZ pelletstar pellet boiler reached through a ``ModbusUnit``.

    Register numbers in the boiler's map start at 1; every address here
    is that number less one. Each component declares the blocks the
    boiler is known to answer in one read.

    The boiler's own hydraulic modules are not polled unless asked for:
    pass ``buffer``, ``hot_water``, ``solar`` or ``heating_circuits`` for
    the ones it drives. An installation whose circuits another controller
    drives leaves them off.
    """

    model = DeviceModel.HERZ_PELLETSTAR
    READINGS = (
        "boiler",
        "combustion",
        "operating_hours",
        "faults",
        "inputs_outputs",
        "fuel",
        "buffer",
        "hot_water",
        "solar",
    )
    SETTINGS = ()

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        buffer: bool = False,
        hot_water: bool = False,
        solar: bool = False,
        heating_circuits: Iterable[int] = (),
        timeout: float | None = None,
    ) -> None:
        super().__init__(unit, timeout=timeout)
        self.boiler = Boiler(unit)
        self.combustion = Combustion(unit)
        self.operating_hours = OperatingHours(unit)
        self.faults = Faults(unit)
        self.inputs_outputs = InputsOutputs(unit)
        self.fuel = Fuel(unit)

        self.buffer = HerzBuffer(unit, base_offset=BUFFER_BASE) if buffer else None
        self.hot_water = (
            HerzHotWater(unit, base_offset=HOT_WATER_BASE) if hot_water else None
        )
        self.solar = HerzSolar(unit, base_offset=SOLAR_BASE) if solar else None
        self.heating_circuit_numbers = tuple(sorted(set(heating_circuits)))
        for number in self.heating_circuit_numbers:
            setattr(
                self,
                module_circuit_name(number),
                HerzHeatingCircuit(unit, base_offset=heating_circuit_base(number)),
            )

    def _readings(self) -> tuple[str, ...]:
        return (
            *self.READINGS,
            *(module_circuit_name(n) for n in self.heating_circuit_numbers),
        )

    def heating_circuit(self, number: int) -> HerzHeatingCircuit | None:
        """Heating circuit module ``number``, ``None`` unless asked for."""
        circuit: HerzHeatingCircuit | None = getattr(
            self, module_circuit_name(number), None
        )
        return circuit
