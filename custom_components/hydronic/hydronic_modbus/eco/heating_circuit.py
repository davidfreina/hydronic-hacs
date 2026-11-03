"""A heating circuit; circuit n is the 100-register block at 2000 + 100 n.

Each component here is declared relative to its circuit's block and
placed with ``base_offset``, so one class serves every circuit.
"""

from __future__ import annotations

from modbus_connection.model import enum, int32

from ..model import HydronicComponent, in_range
from .enums import CircuitOperatingMode, MixerState

BLOCK_START = 2000
BLOCK_SIZE = 100

NO_SENSOR = (-4000) & 0xFFFFFFFF
"""The raw reading of a sensor input with no sensor wired to it, -400.0 °C."""


def circuit_base(number: int) -> int:
    """The first register of heating circuit ``number``, counting from 1."""
    if number < 1:
        raise ValueError(f"heating circuit {number} is not 1 or more")
    return BLOCK_START + BLOCK_SIZE * number


class HeatingCircuit(HydronicComponent):
    """What one heating circuit measures."""

    flow_temperature = int32(0, scale=0.1, unit="°C")
    """Flow temperature."""
    return_temperature = int32(2, scale=0.1, unit="°C")
    """Return temperature."""
    flow_setpoint = int32(4, unit="°C")
    """The flow temperature the circuit aims for, in whole degrees.

    ENERGIEFREUND's parameter list gives tenths, but the controller reports
    whole degrees here.
    """
    pump = int32(6)
    """Circuit pump output; anything above 0 means it runs."""


class HeatingCircuitMode(HydronicComponent):
    """One heating circuit's operating mode."""

    mode = enum(18, CircuitOperatingMode, count=2, writable=True)
    """Operating mode."""

    async def async_write_mode(self, mode: CircuitOperatingMode) -> None:
        """Switch the circuit to another operating mode."""
        await self.write("mode", CircuitOperatingMode(mode))


class HeatingCircuitControl(HydronicComponent):
    """External control of one circuit by a building management system (GLT).

    The circuit follows these only while ``external_control`` is 1; until
    then the controller ignores the release and the external setpoint.
    """

    enabled = int32(22, writable=in_range(0, 1))
    """Release (Freigabe Heizkreis): 1 lets the circuit heat, 0 blocks it."""
    external_flow_setpoint = int32(24, scale=0.1, unit="°C", writable=in_range(0, 80))
    """The flow temperature asked for from outside, 0-80 °C.

    The controller holds it in tenths of a degree, where ENERGIEFREUND's
    parameter list gives whole degrees.
    """
    external_control = int32(36, writable=in_range(0, 1))
    """Whether the circuit takes its orders from outside (HK-Steuerung GLT).

    ENERGIEFREUND's parameter list marks this read-only, but the controller
    takes a write to it.
    """

    async def async_write_enabled(self, enabled: bool) -> None:
        """Release or block the circuit."""
        await self.write("enabled", int(enabled))

    async def async_write_external_flow_setpoint(self, celsius: float) -> None:
        """Ask for a flow temperature, 0-80 °C to a tenth of a degree."""
        await self.write("external_flow_setpoint", celsius)

    async def async_write_external_control(self, active: bool) -> None:
        """Hand the circuit to external control, or take it back."""
        await self.write("external_control", int(active))


class HeatingCircuitMixer(HydronicComponent):
    """Which way the circuit's three-way mixer is being driven.

    The mixer moves in pulses of a few seconds, so this is polled apart from
    the circuit's other readings, and faster.
    """

    state = enum(8, MixerState, count=2, signed=True)
    """Closing, idle or opening."""


class HeatingCircuitMixerRuntime(HydronicComponent):
    """How long the circuit's mixer has run, and how long it is to run.

    Not in ENERGIEFREUND's parameter list, which ends at offset 48; some
    controllers may refuse these, so setup probes for them.
    """

    # Setup only keeps this once both have answered, so one read covers both.
    register_ranges = ((50, 53),)

    runtime = int32(50, unit="s")
    """How long the mixer has been driven in its current move."""
    runtime_target = int32(52, unit="s")
    """How long the mixer is to be driven in its current move."""


class HeatingCircuitSecondary(HydronicComponent):
    """The secondary flow sensor some circuits have."""

    secondary_flow_temperature = int32(46, scale=0.1, nan=NO_SENSOR, unit="°C")
    """Flow temperature on the secondary side; ``None`` with no sensor wired."""
