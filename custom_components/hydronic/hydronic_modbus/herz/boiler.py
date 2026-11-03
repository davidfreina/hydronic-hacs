"""The boiler's own measurements, the blocks from register 1.

Every value is a 32-bit pair of holding registers, high word first.
"""

from __future__ import annotations

from modbus_connection.model import enum, int32, uint32

from ..model import HydronicComponent
from .enums import BoilerState


class Boiler(HydronicComponent):
    """Temperatures, combustion and fan, registers 1-34."""

    register_ranges = ((0, 33),)

    boiler_temperature = int32(0, scale=0.1, unit="°C")
    """Boiler water temperature."""
    demand_temperature = int32(2, scale=0.1, unit="°C")
    """The temperature the consumers ask of the boiler."""
    state = enum(4, BoilerState, count=2)
    """Operating state."""
    output = int32(6, scale=0.1, unit="%")
    """Firing output."""
    return_temperature = int32(8, scale=0.1, unit="°C")
    """Return temperature."""
    return_setpoint = int32(10, scale=0.1, unit="°C")
    """The lowest return temperature the boiler accepts."""
    flue_gas_temperature = int32(12, scale=0.1, unit="°C")
    """Flue gas temperature."""
    combustion_chamber_temperature = int32(14, scale=0.1, unit="°C")
    """Temperature in the combustion chamber."""
    stoker_temperature = int32(16, scale=0.1, unit="°C")
    """Temperature of the stoker (feed) channel."""
    induced_draught_fan = int32(18, scale=0.1, unit="%")
    """Induced draught fan control."""
    secondary_air_flap = int32(20, scale=0.1, unit="%")
    """Secondary air flap opening."""
    fan_speed = int32(22, scale=0.1, unit="%")
    """Induced draught fan speed."""
    fan_speed_setpoint = int32(24, scale=0.1, unit="%")
    """Induced draught fan target speed."""
    oxygen = int32(26, scale=0.1, unit="%")
    """Residual oxygen in the flue gas; negative while there is no reading."""
    oxygen_setpoint = int32(28, scale=0.1, unit="%")
    """Residual oxygen the combustion control aims for."""
    co2 = int32(30, scale=0.1, unit="%")
    """Carbon dioxide in the flue gas."""
    co2_setpoint = int32(32, scale=0.1, unit="%")
    """Carbon dioxide the combustion control aims for."""


class OperatingHours(HydronicComponent):
    """The operating-hour counters, registers 45-56."""

    register_ranges = ((44, 55),)

    full_load = uint32(44, scale=0.1, unit="h")
    """Hours at nominal (full) load."""
    modulating = uint32(46, scale=0.1, unit="h")
    """Hours modulating."""
    part_load = uint32(48, scale=0.1, unit="h")
    """Hours at part load."""
    ignition_and_burnout = uint32(50, scale=0.1, unit="h")
    """Hours spent igniting and burning out."""
    boiler_runtime = uint32(52, scale=0.1, unit="h")
    """Hours the boiler has run."""
    total = uint32(54, scale=0.1, unit="h")
    """Hours in total."""


class Combustion(HydronicComponent):
    """Grate, feed and draught, registers 83-90."""

    register_ranges = ((82, 89),)

    grate_activity = int32(82, scale=0.1, unit="%")
    """Grate activity."""
    feed_activity = int32(84, scale=0.1, unit="%")
    """Fuel feed activity."""
    draught = int32(86, scale=0.1, unit="Pa")
    """Negative pressure in the combustion chamber.

    The boiler reports -90000 Pa or below while there is no reading.
    """
    draught_setpoint = int32(88, scale=0.1, unit="Pa")
    """Negative pressure the draught control aims for."""


class Fuel(HydronicComponent):
    """The fuel the boiler has burnt, register 7079."""

    register_ranges = ((7078, 7079),)

    fuel_consumption = uint32(7078, unit="kg")
    """Fuel burnt since commissioning."""
