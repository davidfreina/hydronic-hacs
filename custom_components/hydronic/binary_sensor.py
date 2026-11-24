"""Support for Hydronic binary sensors."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .entity import (
    BUFFER,
    SOLAR,
    HydronicEntity,
    HydronicEntityDescription,
    served_descriptions,
)
from .hydronic_modbus import DeviceModel
from .hydronic_modbus.belimo import Malfunction
from .hydronic_modbus.eco import HEATING_CIRCUITS, circuit_name
from .hydronic_modbus.herz import (
    InputByte1,
    InputByte2,
    OutputByte1,
    OutputByte2,
    OutputByte3,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from enum import IntFlag

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import HydronicConfigEntry

PARALLEL_UPDATES = 0

BELIMO = frozenset({DeviceModel.BELIMO_ENERGY_VALVE})
ECO = frozenset({DeviceModel.ECO_CONTROLLER})
HERZ = frozenset({DeviceModel.HERZ_PELLETSTAR})


@dataclass(frozen=True, kw_only=True)
class HydronicBinarySensorDescription(
    BinarySensorEntityDescription, HydronicEntityDescription
):
    """Describe a Hydronic binary sensor."""


def _flag_set(
    field: str, flag: IntFlag, *, inverted: bool = False
) -> Callable[[Any], bool | None]:
    """Whether ``flag`` is set in a flags field; inverted, whether it is clear."""

    def value(component: Any) -> bool | None:
        flags: IntFlag | None = getattr(component, field)
        if flags is None:
            return None
        return (flag in flags) != inverted

    return value


def _non_zero(field: str) -> Callable[[Any], bool | None]:
    """Whether a code or flag field is anything but 0."""

    def value(component: Any) -> bool | None:
        code: int | None = getattr(component, field)
        return None if code is None else code != 0

    return value


def _running(field: str) -> Callable[[Any], bool | None]:
    """Whether a pump output is above zero."""

    def value(component: Any) -> bool | None:
        output: int | None = getattr(component, field)
        return None if output is None else output > 0

    return value


BELIMO_BINARY_SENSORS = tuple(
    HydronicBinarySensorDescription(
        key=f"malfunction_{flag.name.lower()}",
        models=BELIMO,
        component="status",
        translation_key=f"malfunction_{flag.name.lower()}",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag_set("malfunction", flag),
    )
    for flag in Malfunction
    if flag.name is not None
)

ECO_BINARY_SENSORS: tuple[HydronicBinarySensorDescription, ...] = (
    HydronicBinarySensorDescription(
        key="circulation_pump",
        models=ECO,
        component="buffer",
        part=BUFFER,
        translation_key="circulation_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_running("circulation_pump"),
    ),
    HydronicBinarySensorDescription(
        key="charging_pump",
        models=ECO,
        component="buffer",
        part=BUFFER,
        translation_key="charging_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_running("charging_pump"),
    ),
    HydronicBinarySensorDescription(
        key="electric_heater",
        models=ECO,
        component="buffer",
        part=BUFFER,
        translation_key="electric_heater",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_running("electric_heater"),
    ),
    HydronicBinarySensorDescription(
        key="solar_pump",
        models=ECO,
        component="solar",
        part=SOLAR,
        translation_key="solar_pump",
        device_class=BinarySensorDeviceClass.RUNNING,
        value_fn=_running("pump"),
    ),
    *(
        HydronicBinarySensorDescription(
            key=f"{circuit_name(number)}_pump",
            models=ECO,
            component=circuit_name(number),
            part=("heating_circuit", number),
            translation_key="pump",
            device_class=BinarySensorDeviceClass.RUNNING,
            value_fn=_running("pump"),
        )
        for number in HEATING_CIRCUITS
    ),
    HydronicBinarySensorDescription(
        key="general_fault",
        models=ECO,
        component="general_alarms",
        translation_key="general_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_non_zero("fault"),
    ),
    HydronicBinarySensorDescription(
        key="general_warning",
        models=ECO,
        component="general_alarms",
        translation_key="general_warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_non_zero("uncritical"),
    ),
)


def _io(
    key: str,
    field: str,
    flag: IntFlag,
    device_class: BinarySensorDeviceClass | None = None,
    *,
    inverted: bool = False,
    diagnostic: bool = True,
) -> HydronicBinarySensorDescription:
    """One bit of the pelletstar's I/O image."""
    return HydronicBinarySensorDescription(
        key=key,
        models=HERZ,
        component="inputs_outputs",
        translation_key=key,
        device_class=device_class,
        entity_category=EntityCategory.DIAGNOSTIC if diagnostic else None,
        value_fn=_flag_set(field, flag, inverted=inverted),
    )


PROBLEM = BinarySensorDeviceClass.PROBLEM
SAFETY = BinarySensorDeviceClass.SAFETY
DOOR = BinarySensorDeviceClass.DOOR
RUNNING = BinarySensorDeviceClass.RUNNING

HERZ_BINARY_SENSORS: tuple[HydronicBinarySensorDescription, ...] = (
    HydronicBinarySensorDescription(
        key="fault",
        models=HERZ,
        component="faults",
        field="has_fault",
        device_class=PROBLEM,
    ),
    _io("pellet_suction", "output_byte_1", OutputByte1.PELLET_SUCTION),
    _io("grate_cleaning", "output_byte_1", OutputByte1.GRATE_CLEANING),
    _io(
        "heat_exchanger_cleaning",
        "output_byte_1",
        OutputByte1.HEAT_EXCHANGER_CLEANING,
    ),
    _io("ignition_heater", "output_byte_1", OutputByte1.IGNITION_HEATER),
    _io("ignition_fan", "output_byte_1", OutputByte1.IGNITION_FAN),
    _io("discharge_screw", "output_byte_1", OutputByte1.DISCHARGE_SCREW),
    _io("burnback_flap_open", "output_byte_1", OutputByte1.BURNBACK_FLAP_OPEN),
    _io("hopper_screw", "output_byte_2", OutputByte2.HOPPER_SCREW),
    _io("solenoid_valve", "output_byte_2", OutputByte2.SOLENOID_VALVE),
    _io("ash_removal", "output_byte_2", OutputByte2.ASH_REMOVAL),
    _io(
        "return_pump",
        "output_byte_2",
        OutputByte2.RETURN_PUMP,
        RUNNING,
        diagnostic=False,
    ),
    # Energised while there is no alarm.
    _io(
        "alarm_output",
        "output_byte_2",
        OutputByte2.ALARM_OUTPUT,
        PROBLEM,
        inverted=True,
    ),
    # Set while the temperature monitor is satisfied.
    _io(
        "overtemperature_output",
        "output_byte_3",
        OutputByte3.OVERTEMPERATURE_OUTPUT,
        SAFETY,
        inverted=True,
    ),
    _io(
        "operating_signal",
        "output_byte_3",
        OutputByte3.OPERATING_SIGNAL,
        BinarySensorDeviceClass.POWER,
    ),
    _io("feed_screw_release", "output_byte_3", OutputByte3.FEED_SCREW_RELEASE),
    _io("lambda_heating", "output_byte_3", OutputByte3.LAMBDA_HEATING, RUNNING),
    _io("system_stop", "input_byte_1", InputByte1.SYSTEM_STOP, SAFETY),
    _io(
        "overtemperature_input",
        "input_byte_1",
        InputByte1.OVERTEMPERATURE_INPUT,
        SAFETY,
        inverted=True,
    ),
    _io("burnback_flap", "input_byte_1", InputByte1.BURNBACK_FLAP_OPENED, DOOR),
    _io("burnback_flap_closed", "input_byte_1", InputByte1.BURNBACK_FLAP_CLOSED),
    _io(
        "discharge_motor_protection",
        "input_byte_1",
        InputByte1.DISCHARGE_MOTOR_PROTECTION,
        PROBLEM,
        inverted=True,
    ),
    # The input reports the door closed, so the door is open when it is clear.
    _io("ash_door", "input_byte_1", InputByte1.ASH_DOOR_CLOSED, DOOR, inverted=True),
    _io(
        "discharge_limit_switch",
        "input_byte_1",
        InputByte1.DISCHARGE_LIMIT_SWITCH,
    ),
    _io("auxiliary_input", "input_byte_1", InputByte1.AUXILIARY_INPUT),
    _io(
        "ash_removal_monitoring",
        "input_byte_2",
        InputByte2.ASH_REMOVAL_MONITORING,
        PROBLEM,
    ),
    _io("hopper_empty", "input_byte_2", InputByte2.HOPPER_EMPTY, PROBLEM),
    _io("grate_closed", "input_byte_2", InputByte2.GRATE_CLOSED),
    _io("suction_flap", "input_byte_2", InputByte2.SUCTION_FLAP, DOOR),
    _io(
        "central_ash_removal",
        "input_byte_2",
        InputByte2.CENTRAL_ASH_REMOVAL,
        PROBLEM,
        inverted=True,
    ),
    _io(
        "safety_temperature_limiter",
        "input_byte_2",
        InputByte2.SAFETY_TEMPERATURE_LIMITER,
        SAFETY,
        inverted=True,
    ),
    _io(
        "heat_exchanger_monitoring",
        "input_byte_2",
        InputByte2.HEAT_EXCHANGER_MONITORING,
        PROBLEM,
        inverted=True,
    ),
)

BINARY_SENSOR_DESCRIPTIONS: tuple[HydronicBinarySensorDescription, ...] = (
    *BELIMO_BINARY_SENSORS,
    *ECO_BINARY_SENSORS,
    *HERZ_BINARY_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hydronic binary sensor platform."""
    runtime_data = entry.runtime_data
    async_add_entities(
        HydronicBinarySensor(runtime_data, description)
        for description in served_descriptions(runtime_data, BINARY_SENSOR_DESCRIPTIONS)
    )


class HydronicBinarySensor(HydronicEntity, BinarySensorEntity):
    """Defines a Hydronic binary sensor."""

    entity_description: HydronicBinarySensorDescription

    @property
    @override
    def is_on(self) -> bool | None:
        value = self.entity_description.value(self.coordinator.device)
        return None if value is None else bool(value)
