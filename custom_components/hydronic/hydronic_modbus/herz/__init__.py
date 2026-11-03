"""The HERZ pelletstar pellet boiler.

Every value is a 32-bit pair of holding registers, high word first.
Read-only: the map these come from writes nothing.
"""

from .boiler import Boiler, Combustion, Fuel, OperatingHours
from .device import HerzPelletstar, module_circuit_name
from .enums import (
    BoilerState,
    FaultStatus,
    InputByte1,
    InputByte2,
    OutputByte1,
    OutputByte2,
    OutputByte3,
)
from .errors import ERROR_TEXTS, error_text
from .faults import ERROR_CODE_SLOTS, Faults, InputsOutputs
from .modules import (
    HerzBuffer,
    HerzHeatingCircuit,
    HerzHotWater,
    HerzSolar,
    heating_circuit_base,
)

__all__ = [
    "ERROR_CODE_SLOTS",
    "ERROR_TEXTS",
    "Boiler",
    "BoilerState",
    "Combustion",
    "FaultStatus",
    "Faults",
    "Fuel",
    "HerzBuffer",
    "HerzHeatingCircuit",
    "HerzHotWater",
    "HerzPelletstar",
    "HerzSolar",
    "InputByte1",
    "InputByte2",
    "InputsOutputs",
    "OperatingHours",
    "OutputByte1",
    "OutputByte2",
    "OutputByte3",
    "error_text",
    "heating_circuit_base",
    "module_circuit_name",
]
