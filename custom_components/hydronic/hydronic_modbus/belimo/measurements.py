"""What the valve measures: temperatures, power and the meters.

The 32-bit values put the low word first.
"""

from __future__ import annotations

from modbus_connection.model import gauge, uint32

from ..model import HydronicComponent


class Temperatures(HydronicComponent):
    """The valve's temperature sensors, and the difference between them."""

    sensor_1_temperature = gauge(13, 0.01, unit="°C")
    """The additional sensor on input 1, as a temperature.

    Only meaningful with a temperature sensor wired to that input.
    """
    remote_temperature = gauge(19, 0.01, unit="°C")
    """T1, the external sensor; usually mounted in the supply."""
    body_temperature = gauge(21, 0.01, unit="°C")
    """T2, the sensor integrated in the valve body; usually the return."""
    delta_t = gauge(23, 0.01, unit="K")
    """Temperature difference between T1 and T2."""


class Power(HydronicComponent):
    """Thermal power through the valve while heating."""

    heating_power = uint32(33, scale=0.001, word_order="little", unit="kW")
    """Absolute heating power."""


class Meters(HydronicComponent):
    """The valve's accumulated volume and heating energy.

    Which meter these read, certified or lifetime, is the valve's own
    setting (register 205).
    """

    volume = uint32(59, scale=0.01, word_order="little", unit="m³")
    """Total volume that has passed through the valve."""
    heating_energy = uint32(71, word_order="little", unit="kWh")
    """Heating energy that has passed through the valve."""
