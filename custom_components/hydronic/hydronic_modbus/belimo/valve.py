"""What the valve is told to do, and where it is."""

from __future__ import annotations

from modbus_connection.model import enum, gauge, uint32

from ..model import HydronicComponent, in_range
from .enums import BusFailAction, FlowUnit, OverrideControl


class ValveControl(HydronicComponent):
    """The setpoint and the override, registers 1 and 2."""

    setpoint = gauge(0, 0.01, signed=False, unit="%", writable=in_range(0, 100))
    """Relative setpoint, 0-100 % of the configured maximum."""
    override_control = enum(1, OverrideControl, writable=True)
    """What overrides the setpoint, if anything.

    The valve drops an override on its own after a while, so read it back
    rather than assume it is still in force.
    """

    async def async_write_setpoint(self, percent: float) -> None:
        """Command the valve to ``percent`` of its maximum, 0-100."""
        await self.write("setpoint", percent)

    async def async_write_override(self, override: OverrideControl) -> None:
        """Override the setpoint, or hand control back with ``NONE``."""
        await self.write("override_control", OverrideControl(override))


class BusFail(HydronicComponent):
    """Where the valve goes when the bus goes quiet, register 109."""

    bus_fail_action = enum(108, BusFailAction, writable=True)
    """What the valve does once the bus watchdog fires."""

    async def async_write_bus_fail_action(self, action: BusFailAction) -> None:
        """Set what the valve does on a bus failure."""
        await self.write("bus_fail_action", BusFailAction(action))


class ValvePosition(HydronicComponent):
    """Where the valve actually is, and the flow through it."""

    relative_position = gauge(4, 0.01, signed=False, unit="%")
    """Relative position of the valve, 0-100 %."""
    flow = uint32(9, scale=0.001, word_order="little")
    """Absolute volumetric flow, in ``Units.flow_unit``."""


class Units(HydronicComponent):
    """The unit the valve reports its selected-unit flows in, register 148."""

    flow_unit = enum(147, FlowUnit)
    """Unit of ``ValvePosition.flow``; the factory default is l/h."""
