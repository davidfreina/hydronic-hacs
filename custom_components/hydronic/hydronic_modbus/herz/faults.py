"""Faults and the I/O image."""

from __future__ import annotations

from modbus_connection.model import enum, flags, int32

from ..model import HydronicComponent
from .enums import (
    FaultStatus,
    InputByte1,
    InputByte2,
    OutputByte1,
    OutputByte2,
    OutputByte3,
)
from .errors import error_text

ERROR_CODE_SLOTS = 10
"""How many error codes the boiler reports at once."""


class Faults(HydronicComponent):
    """The fault status and the error codes, registers 93 and 301-320."""

    register_ranges = ((92, 93), (300, 319))

    fault_status = enum(92, FaultStatus, count=2)
    """Whether an error, a warning or an information is pending."""
    error_code_1 = int32(300)
    error_code_2 = int32(302)
    error_code_3 = int32(304)
    error_code_4 = int32(306)
    error_code_5 = int32(308)
    error_code_6 = int32(310)
    error_code_7 = int32(312)
    error_code_8 = int32(314)
    error_code_9 = int32(316)
    error_code_10 = int32(318)

    @property
    def active_error_codes(self) -> list[int]:
        """The error codes currently set, in slot order; 0 marks a free slot."""
        codes = (
            getattr(self, f"error_code_{slot}")
            for slot in range(1, ERROR_CODE_SLOTS + 1)
        )
        return [code for code in codes if code]

    @property
    def active_errors(self) -> list[tuple[int, str | None]]:
        """The error codes currently set, each with the boiler's display text."""
        return [(code, error_text(code)) for code in self.active_error_codes]

    @property
    def has_fault(self) -> bool | None:
        """Whether an error is pending; ``None`` until the first poll.

        A warning or an information is not a fault.
        """
        if self.fault_status is None:
            return None
        return self.fault_status is FaultStatus.ERROR


class InputsOutputs(HydronicComponent):
    """The boiler's I/O image, registers 291-300, a byte per pair.

    Some bits are set while all is well (see ``enums``), so their absence is
    the alarm.
    """

    register_ranges = ((290, 299),)

    output_byte_1 = flags(290, OutputByte1, count=2)
    output_byte_2 = flags(292, OutputByte2, count=2)
    output_byte_3 = flags(294, OutputByte3, count=2)
    input_byte_1 = flags(296, InputByte1, count=2)
    input_byte_2 = flags(298, InputByte2, count=2)
