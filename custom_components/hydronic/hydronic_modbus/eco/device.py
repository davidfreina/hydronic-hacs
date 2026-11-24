"""The top-level object for an eco heating controller."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from modbus_connection.model import read_optional

from ..model import DeviceModel, HydronicDevice
from .heating_circuit import (
    HeatingCircuit,
    HeatingCircuitControl,
    HeatingCircuitMixer,
    HeatingCircuitMixerRuntime,
    HeatingCircuitMode,
    HeatingCircuitSecondary,
    circuit_base,
)
from .messages import BufferMessages, CircuitMessages, GeneralAlarms, SolarMessages
from .solar import Solar, SolarMode
from .storage import Buffer, BufferMode
from .system import ExternalKeepAlive, QuickSelect, System

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

_LOGGER = logging.getLogger(__name__)

HEATING_CIRCUITS = (1, 2, 3)
"""The circuits setup probes for, when the caller names none."""


def circuit_name(number: int) -> str:
    """The attribute heating circuit ``number``'s measurements live on."""
    return f"heating_circuit_{number}"


def circuit_mode_name(number: int) -> str:
    """The attribute heating circuit ``number``'s mode lives on."""
    return f"heating_circuit_{number}_mode"


def circuit_control_name(number: int) -> str:
    """The attribute heating circuit ``number``'s external control lives on."""
    return f"heating_circuit_{number}_control"


def circuit_mixer_name(number: int) -> str:
    """The attribute heating circuit ``number``'s mixer state lives on."""
    return f"heating_circuit_{number}_mixer"


def circuit_mixer_runtime_name(number: int) -> str:
    """The attribute heating circuit ``number``'s mixer runtimes live on."""
    return f"heating_circuit_{number}_mixer_runtime"


def circuit_secondary_name(number: int) -> str:
    """The attribute heating circuit ``number``'s secondary sensor lives on."""
    return f"heating_circuit_{number}_secondary"


def circuit_messages_name(number: int) -> str:
    """The attribute heating circuit ``number``'s alarm/warning codes live on."""
    return f"heating_circuit_{number}_messages"


class EcoController(HydronicDevice):
    """An eco heating controller reached through a ``ModbusUnit``.

    Every value is a 32-bit pair of holding registers, high word first.
    The controller covers solar, a storage tank with its circulation, and
    a number of heating circuits.

    Setup probes which heating circuits exist, and which of them have a
    secondary flow sensor: a controller refuses the registers of a circuit
    it does not have, and reports -400.0 °C for a sensor that is not wired.
    Name the circuits with ``heating_circuits`` to skip probing for them.
    Each circuit's components are attributes named by ``circuit_name()``,
    ``circuit_mode_name()``, ``circuit_control_name()``,
    ``circuit_mixer_name()``, ``circuit_mixer_runtime_name()``,
    ``circuit_secondary_name()`` and ``circuit_messages_name()``, ``None``
    where the circuit (or, for the mixer runtimes, the secondary sensor and
    the messages, the reading) is absent. The mixer states are polled with
    ``async_update_fast()``.

    The alarm, warning and information codes (``general_alarms``,
    ``buffer_messages``, ``solar_messages`` and each circuit's messages) are
    probed at setup and stay ``None`` where the controller refuses them.
    """

    model = DeviceModel.ECO_CONTROLLER
    READINGS = (
        "system",
        "solar",
        "buffer",
        "general_alarms",
        "buffer_messages",
        "solar_messages",
    )
    SETTINGS = ("quick_select", "solar_mode", "buffer_mode", "external_keepalive")

    def __init__(
        self,
        unit: ModbusUnit,
        *,
        heating_circuits: Iterable[int] | None = None,
        timeout: float | None = None,
    ) -> None:
        super().__init__(unit, timeout=timeout)
        self.system = System(unit)
        self.quick_select = QuickSelect(unit)
        self.external_keepalive = ExternalKeepAlive(unit)
        self.buffer = Buffer(unit)
        self.buffer_mode = BufferMode(unit)
        self.solar = Solar(unit)
        self.solar_mode = SolarMode(unit)
        self.general_alarms: GeneralAlarms | None = GeneralAlarms(unit)
        self.buffer_messages: BufferMessages | None = BufferMessages(unit)
        self.solar_messages: SolarMessages | None = SolarMessages(unit)

        self._probe_circuits = heating_circuits is None
        self.heating_circuit_numbers: tuple[int, ...] = tuple(
            sorted(
                set(HEATING_CIRCUITS if heating_circuits is None else heating_circuits)
            )
        )
        for number in self.heating_circuit_numbers:
            base = circuit_base(number)
            setattr(self, circuit_name(number), HeatingCircuit(unit, base_offset=base))
            setattr(
                self,
                circuit_mode_name(number),
                HeatingCircuitMode(unit, base_offset=base),
            )
            setattr(
                self,
                circuit_control_name(number),
                HeatingCircuitControl(unit, base_offset=base),
            )
            setattr(
                self,
                circuit_mixer_name(number),
                HeatingCircuitMixer(unit, base_offset=base),
            )
            setattr(self, circuit_mixer_runtime_name(number), None)
            setattr(self, circuit_secondary_name(number), None)
            setattr(self, circuit_messages_name(number), None)

    def _readings(self) -> tuple[str, ...]:
        return (
            *self.READINGS,
            *(circuit_name(n) for n in self.heating_circuit_numbers),
            *(circuit_mixer_runtime_name(n) for n in self.heating_circuit_numbers),
            *(circuit_secondary_name(n) for n in self.heating_circuit_numbers),
            *(circuit_messages_name(n) for n in self.heating_circuit_numbers),
        )

    def _fast(self) -> tuple[str, ...]:
        return tuple(circuit_mixer_name(n) for n in self.heating_circuit_numbers)

    def _settings(self) -> tuple[str, ...]:
        return (
            *self.SETTINGS,
            *(circuit_mode_name(n) for n in self.heating_circuit_numbers),
            *(circuit_control_name(n) for n in self.heating_circuit_numbers),
        )

    def heating_circuit(self, number: int) -> HeatingCircuit | None:
        """Heating circuit ``number``'s measurements, ``None`` if it is absent."""
        circuit: HeatingCircuit | None = getattr(self, circuit_name(number), None)
        return circuit

    def heating_circuit_mode(self, number: int) -> HeatingCircuitMode | None:
        """Heating circuit ``number``'s mode, ``None`` if it is absent."""
        mode: HeatingCircuitMode | None = getattr(self, circuit_mode_name(number), None)
        return mode

    def heating_circuit_control(self, number: int) -> HeatingCircuitControl | None:
        """Heating circuit ``number``'s external control, ``None`` if absent."""
        control: HeatingCircuitControl | None = getattr(
            self, circuit_control_name(number), None
        )
        return control

    def heating_circuit_mixer(self, number: int) -> HeatingCircuitMixer | None:
        """Heating circuit ``number``'s mixer state, ``None`` if absent."""
        mixer: HeatingCircuitMixer | None = getattr(
            self, circuit_mixer_name(number), None
        )
        return mixer

    def heating_circuit_mixer_runtime(
        self, number: int
    ) -> HeatingCircuitMixerRuntime | None:
        """Heating circuit ``number``'s mixer runtimes, ``None`` if absent."""
        runtime: HeatingCircuitMixerRuntime | None = getattr(
            self, circuit_mixer_runtime_name(number), None
        )
        return runtime

    def heating_circuit_secondary(self, number: int) -> HeatingCircuitSecondary | None:
        """Heating circuit ``number``'s secondary sensor, ``None`` if absent."""
        secondary: HeatingCircuitSecondary | None = getattr(
            self, circuit_secondary_name(number), None
        )
        return secondary

    def heating_circuit_messages(self, number: int) -> CircuitMessages | None:
        """Heating circuit ``number``'s alarm/warning codes, ``None`` if absent."""
        messages: CircuitMessages | None = getattr(
            self, circuit_messages_name(number), None
        )
        return messages

    async def _async_setup(self) -> None:
        """Settle which circuits exist, their second sensors and message codes."""
        for name in ("general_alarms", "buffer_messages", "solar_messages"):
            component = getattr(self, name)
            if component is not None and await read_optional(component) is None:
                _LOGGER.debug("Controller refuses %s", name)
                setattr(self, name, None)
        present: list[int] = []
        for number in self.heating_circuit_numbers:
            circuit = self.heating_circuit(number)
            if circuit is None:
                continue  # refused by a setup that later failed; stays refused
            if self._probe_circuits and await read_optional(circuit) is None:
                _LOGGER.debug("Controller refuses heating circuit %s", number)
                setattr(self, circuit_name(number), None)
                setattr(self, circuit_mode_name(number), None)
                setattr(self, circuit_control_name(number), None)
                setattr(self, circuit_mixer_name(number), None)
                continue
            present.append(number)
            runtime = HeatingCircuitMixerRuntime(
                self.modbus_unit, base_offset=circuit_base(number)
            )
            if await read_optional(runtime) is not None:
                setattr(self, circuit_mixer_runtime_name(number), runtime)
            secondary = HeatingCircuitSecondary(
                self.modbus_unit, base_offset=circuit_base(number)
            )
            if (
                await read_optional(secondary) is not None
                and secondary.secondary_flow_temperature is not None
            ):
                setattr(self, circuit_secondary_name(number), secondary)
            messages = CircuitMessages(
                self.modbus_unit, base_offset=circuit_base(number)
            )
            if await read_optional(messages) is not None:
                setattr(self, circuit_messages_name(number), messages)
        _LOGGER.debug(
            "Controller serves heating circuits %s; secondary flow on %s",
            ", ".join(map(str, present)) or "none",
            ", ".join(str(n) for n in present if self.heating_circuit_secondary(n))
            or "none",
        )
