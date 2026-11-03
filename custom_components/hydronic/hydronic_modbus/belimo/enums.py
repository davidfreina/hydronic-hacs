"""Option maps from Belimo's Energy Valve register description, as enums."""

from __future__ import annotations

from enum import IntEnum, IntFlag


class OverrideControl(IntEnum):
    """Override control, register 2: what replaces the setpoint."""

    NONE = 0
    OPEN = 1
    CLOSE = 2
    MINIMUM_FLOW = 3
    MAXIMUM_FLOW = 5
    NOMINAL_FLOW = 6
    MOTOR_STOP = 10


class DeltaTLimitation(IntEnum):
    """DeltaT limitation, register 180: how the Delta T manager may act."""

    DISABLED = 0
    DT_MANAGER = 1
    DT_MANAGER_SCALING = 2


class DeltaTManagerStatus(IntEnum):
    """DeltaT manager status, register 181."""

    NOT_SELECTED = 0
    STANDBY = 1
    ACTIVE = 2
    SCALING_STANDBY = 3
    SCALING_ACTIVE = 4


class FlowUnit(IntEnum):
    """Unit selection flow, register 148: the unit of the selected-unit flows."""

    CUBIC_METERS_PER_SECOND = 0
    CUBIC_METERS_PER_HOUR = 1
    LITERS_PER_SECOND = 2
    LITERS_PER_MINUTE = 3
    LITERS_PER_HOUR = 4
    GALLONS_PER_MINUTE = 5
    CUBIC_FEET_PER_MINUTE = 6


class BusFailAction(IntEnum):
    """Bus fail action, register 109 (firmware 4.2): where the valve goes.

    Belimo's V4.1 description has a bus-fail setpoint in % here instead.
    """

    NONE = 0
    OPEN = 1
    CLOSE = 2
    MAXIMUM = 3
    MINIMUM = 4


class Malfunction(IntFlag):
    """Malfunction and service information, registers 158-159 (firmware 4.2)."""

    NO_ACTUATOR_COMMUNICATION = 1 << 0
    GEAR_DISENGAGED = 1 << 1
    ACTUATOR_CANNOT_MOVE = 1 << 2
    REVERSE_FLOW = 1 << 3
    FLOW_SETPOINT_NOT_REACHED = 1 << 4
    FLOW_WITH_CLOSED_VALVE = 1 << 5
    FLOW_EXCEEDS_NOMINAL = 1 << 6
    FLOW_MEASUREMENT_ERROR = 1 << 7
    REMOTE_TEMPERATURE_ERROR = 1 << 8
    BODY_TEMPERATURE_ERROR = 1 << 9
    SENSOR_COMMUNICATION_INTERRUPTED = 1 << 10
    FREEZE_WARNING = 1 << 11
    GLYCOL_DETECTED = 1 << 12
    POWER_SETPOINT_NOT_REACHED = 1 << 13
    END_OF_LIFE = 1 << 14
    BUS_WATCHDOG_TRIGGERED = 1 << 15
    NO_DIFFERENTIAL_PRESSURE = 1 << 16
    DIFFERENTIAL_PRESSURE_NOT_REACHED = 1 << 17
    MINIMUM_POSITION_APPLIED = 1 << 18
