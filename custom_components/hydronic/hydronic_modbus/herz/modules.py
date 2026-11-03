"""Hydraulic modules the boiler can drive itself, each a 40-register block.

Module slot n is the 40-register block at 1000 + 40 n (registers 41000 + X
in HERZ's Modbus TCP parameter list); which kind of module sits in a slot
depends on the installation. The offsets follow that list. They are only
read when the caller asks for them. Each is declared relative to its block
and placed with ``base_offset``.
"""

from __future__ import annotations

from modbus_connection.model import int32, uint32

from ..model import HydronicComponent

BUFFER_BASE = 1000
HOT_WATER_BASE = 1040
SOLAR_BASE = 1280
HEATING_CIRCUIT_STRIDE = 40


def heating_circuit_base(number: int) -> int:
    """The first register of heating circuit ``number``, counting from 1."""
    if number < 1:
        raise ValueError(f"heating circuit {number} is not 1 or more")
    return HOT_WATER_BASE + HEATING_CIRCUIT_STRIDE * number


class _Module(HydronicComponent):
    """A module block: the boiler answers 30 registers of it in one read."""

    register_ranges = ((0, 29),)


class HerzBuffer(_Module):
    """The buffer tank, from register 1001."""

    top_temperature = int32(2, scale=0.1, unit="°C")
    bottom_temperature = int32(4, scale=0.1, unit="°C")
    outdoor_temperature = int32(6, scale=0.1, unit="°C")
    middle_temperature = int32(8, scale=0.1, unit="°C")
    setpoint = int32(10, scale=0.1, unit="°C")
    inputs_outputs = int32(12)
    locked = int32(26)
    """Whether a lock period is active (Sperrzeit aktiv), 0 or 1."""


class HerzHotWater(_Module):
    """The hot water cylinder, from register 1041."""

    temperature = int32(2, scale=0.1, unit="°C")
    circulation_temperature = int32(4, scale=0.1, unit="°C")
    bottom_temperature = int32(8, scale=0.1, unit="°C")
    inputs_outputs = int32(12)
    setpoint = int32(16, scale=0.1, unit="°C")
    quick_start = int32(28)
    """Whether a one-off heat-up has been asked for."""


class HerzHeatingCircuit(_Module):
    """One heating circuit; circuit n starts at register 1041 + 40 n."""

    flow_temperature = int32(2, scale=0.1, unit="°C")
    return_temperature = int32(4, scale=0.1, unit="°C")
    inputs_outputs = int32(12)
    flow_setpoint = int32(16, scale=0.1, unit="°C")


class HerzSolar(_Module):
    """The solar circuit, from register 1281."""

    collector_temperature = int32(2, scale=0.1, unit="°C")
    collector_return_temperature = int32(4, scale=0.1, unit="°C")
    storage_1_temperature = int32(6, scale=0.1, unit="°C")
    storage_2_temperature = int32(8, scale=0.1, unit="°C")
    pump = int32(10, scale=0.1, unit="%")
    inputs_outputs = int32(12)
    yield_today = uint32(16, unit="Wh")
    """Today's yield."""
    power = uint32(18, unit="W")
    """Current yield."""
