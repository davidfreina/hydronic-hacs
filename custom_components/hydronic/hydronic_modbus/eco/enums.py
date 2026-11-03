"""The controller's operating-mode codes, as enums.

From ENERGIEFREUND's ModBus Parameterbeschreibung ECO v5.00.29.
"""

from __future__ import annotations

from enum import IntEnum


class QuickSelectMode(IntEnum):
    """The controller-wide quick select (Schnellauswahl)."""

    WINTER = 1
    SUMMER = 2
    ABSENT = 3
    USER_DEFINED_1 = 4
    USER_DEFINED_2 = 5


class SolarOperatingMode(IntEnum):
    """The solar circuit's operating mode (Betriebsart)."""

    OFF = 0
    MANUAL = 1
    AUTOMATIC = 2


class CircuitOperatingMode(IntEnum):
    """A heating circuit's operating mode (Betriebsart)."""

    OFF = 0
    FROST_PROTECTION = 1
    MANUAL = 2
    CONTINUOUS_HEATING = 3
    SETBACK = 4
    AUTOMATIC_1 = 5
    AUTOMATIC_2 = 6
    PARTY = 9


class BufferOperatingMode(IntEnum):
    """The buffer tank's operating mode (Betriebsart)."""

    OFF = 0
    MANUAL = 1
    AUTOMATIC_WINTER = 2
    AUTOMATIC_SUMMER = 3
    AUTOMATIC_OUTDOOR_TEMPERATURE = 4
    AUTOMATIC_ELECTRIC_HEATER = 5
    AUTOMATIC_HEAT_DISTRIBUTION = 6


class MixerState(IntEnum):
    """Which way a circuit's three-way mixer is being driven."""

    CLOSING = -1
    IDLE = 0
    OPENING = 1
