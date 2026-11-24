"""Support for Hydronic sensors."""

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Any, cast, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

from .entity import (
    BUFFER,
    SOLAR,
    HydronicEntity,
    HydronicEntityDescription,
    HydronicPart,
    enum_options,
    served_descriptions,
)
from .hydronic_modbus import DeviceModel
from .hydronic_modbus.belimo import DeltaTManagerStatus, FlowUnit
from .hydronic_modbus.eco import (
    HEATING_CIRCUITS,
    MixerState,
    circuit_messages_name,
    circuit_mixer_name,
    circuit_mixer_runtime_name,
    circuit_name,
    circuit_secondary_name,
)
from .hydronic_modbus.herz import (
    ERROR_CODE_SLOTS,
    BoilerState,
    FaultStatus,
    OutputByte2,
    error_text,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .data import HydronicConfigEntry

PARALLEL_UPDATES = 0

BELIMO = frozenset({DeviceModel.BELIMO_ENERGY_VALVE})
ECO = frozenset({DeviceModel.ECO_CONTROLLER})
HERZ = frozenset({DeviceModel.HERZ_PELLETSTAR})

# The pelletstar reports a draught at or below this while it has no reading.
NO_DRAUGHT_READING = -90000
# Error slots past these rarely fill, so their sensors start disabled.
ENABLED_ERROR_SLOTS = 3


@dataclass(frozen=True, kw_only=True)
class HydronicSensorDescription(SensorEntityDescription, HydronicEntityDescription):
    """Describe a Hydronic sensor."""

    # The unit, where the device decides it; None leaves the entity unavailable.
    unit_fn: Callable[[Any], str | None] | None = None


_FLOW_UNITS: dict[FlowUnit | None, UnitOfVolumeFlowRate] = {
    FlowUnit.CUBIC_METERS_PER_SECOND: UnitOfVolumeFlowRate.CUBIC_METERS_PER_SECOND,
    FlowUnit.CUBIC_METERS_PER_HOUR: UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    FlowUnit.LITERS_PER_SECOND: UnitOfVolumeFlowRate.LITERS_PER_SECOND,
    FlowUnit.LITERS_PER_MINUTE: UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
    FlowUnit.LITERS_PER_HOUR: UnitOfVolumeFlowRate.LITERS_PER_HOUR,
    FlowUnit.GALLONS_PER_MINUTE: UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
    FlowUnit.CUBIC_FEET_PER_MINUTE: UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
}


def _temperature(
    models: frozenset[DeviceModel],
    component: str,
    key: str,
    *,
    field: str | None = None,
    translation_key: str | None = None,
    part: HydronicPart | None = None,
    enabled: bool = True,
) -> HydronicSensorDescription:
    """A temperature measured in °C."""
    return HydronicSensorDescription(
        key=key,
        models=models,
        component=component,
        field=field,
        part=part,
        translation_key=translation_key or key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _percentage(
    models: frozenset[DeviceModel],
    component: str,
    key: str,
    *,
    enabled: bool = True,
) -> HydronicSensorDescription:
    """A percentage."""
    return HydronicSensorDescription(
        key=key,
        models=models,
        component=component,
        translation_key=key,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=enabled,
    )


def _code(
    models: frozenset[DeviceModel],
    component: str,
    key: str,
    *,
    field: str | None = None,
    part: HydronicPart | None = None,
    translation_key: str | None = None,
    enabled: bool = True,
) -> HydronicSensorDescription:
    """One of the device's own codes, shown as the raw number."""
    return HydronicSensorDescription(
        key=key,
        models=models,
        component=component,
        field=field,
        part=part,
        translation_key=translation_key or key,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


def _operating_hours(key: str) -> HydronicSensorDescription:
    """One of the pelletstar's operating-hour counters."""
    return HydronicSensorDescription(
        key=f"hours_{key}",
        models=HERZ,
        component="operating_hours",
        field=key,
        translation_key=f"hours_{key}",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    )


BELIMO_SENSORS: tuple[HydronicSensorDescription, ...] = (
    _percentage(BELIMO, "position", "relative_position"),
    HydronicSensorDescription(
        key="flow",
        models=BELIMO,
        component="position",
        translation_key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        unit_fn=lambda device: _FLOW_UNITS.get(device.units.flow_unit),
    ),
    _temperature(BELIMO, "temperatures", "remote_temperature"),
    _temperature(BELIMO, "temperatures", "body_temperature"),
    _temperature(BELIMO, "temperatures", "sensor_1_temperature"),
    HydronicSensorDescription(
        key="delta_t",
        models=BELIMO,
        component="temperatures",
        translation_key="delta_t",
        device_class=SensorDeviceClass.TEMPERATURE_DELTA,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HydronicSensorDescription(
        key="heating_power",
        models=BELIMO,
        component="power",
        translation_key="heating_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HydronicSensorDescription(
        key="heating_energy",
        models=BELIMO,
        component="meters",
        translation_key="heating_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HydronicSensorDescription(
        key="volume",
        models=BELIMO,
        component="meters",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HydronicSensorDescription(
        key="delta_t_manager_status",
        models=BELIMO,
        component="status",
        translation_key="delta_t_manager_status",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(DeltaTManagerStatus),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


MESSAGE_KINDS = ("alarm", "warning", "information")
"""The three codes each eco module reports, as sensor keys and translation keys."""


def _eco_messages(
    component: str, key_prefix: str, part: HydronicPart
) -> tuple[HydronicSensorDescription, ...]:
    """An eco module's alarm, warning and information, shown as their texts."""
    return tuple(
        HydronicSensorDescription(
            key=f"{key_prefix}_{kind}",
            models=ECO,
            component=component,
            field=f"{kind}_text",
            part=part,
            translation_key=f"eco_{kind}",
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        for kind in MESSAGE_KINDS
    )


def _eco_circuit_sensors(number: int) -> tuple[HydronicSensorDescription, ...]:
    """The sensors one of the eco controller's heating circuits has."""
    part = ("heating_circuit", number)
    component = circuit_name(number)
    return (
        _temperature(
            ECO,
            component,
            f"{component}_flow_temperature",
            field="flow_temperature",
            translation_key="flow_temperature",
            part=part,
        ),
        _temperature(
            ECO,
            component,
            f"{component}_return_temperature",
            field="return_temperature",
            translation_key="return_temperature",
            part=part,
        ),
        _temperature(
            ECO,
            component,
            f"{component}_flow_setpoint",
            field="flow_setpoint",
            translation_key="flow_setpoint",
            part=part,
        ),
        HydronicSensorDescription(
            key=f"{component}_mixer",
            models=ECO,
            component=circuit_mixer_name(number),
            field="state",
            part=part,
            translation_key="circuit_mixer",
            device_class=SensorDeviceClass.ENUM,
            options=enum_options(MixerState),
        ),
        *(
            HydronicSensorDescription(
                key=f"{component}_mixer_{field}",
                models=ECO,
                component=circuit_mixer_runtime_name(number),
                field=field,
                part=part,
                translation_key=f"mixer_{field}",
                device_class=SensorDeviceClass.DURATION,
                native_unit_of_measurement=UnitOfTime.SECONDS,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
            for field in ("runtime", "runtime_target")
        ),
        _temperature(
            ECO,
            circuit_secondary_name(number),
            f"{component}_secondary_flow_temperature",
            field="secondary_flow_temperature",
            translation_key="secondary_flow_temperature",
            part=part,
        ),
        *_eco_messages(circuit_messages_name(number), component, part),
    )


ECO_SENSORS: tuple[HydronicSensorDescription, ...] = (
    _temperature(ECO, "system", "outdoor_temperature"),
    _code(ECO, "system", "keepalive", enabled=False),
    *(
        _temperature(ECO, "buffer", f"buffer_{field}", field=field, part=BUFFER)
        for field in (
            "top_temperature",
            "top_1_temperature",
            "middle_temperature",
            "bottom_temperature",
        )
    ),
    _temperature(ECO, "buffer", "buffer_setpoint", field="setpoint", part=BUFFER),
    _temperature(ECO, "buffer", "circulation_temperature", part=BUFFER),
    _temperature(ECO, "buffer", "tap_temperature", part=BUFFER),
    _temperature(ECO, "solar", "collector_temperature", part=SOLAR),
    _temperature(ECO, "solar", "collector_return_temperature", part=SOLAR),
    _temperature(
        ECO,
        "solar",
        "solar_storage_temperature",
        field="storage_temperature",
        part=SOLAR,
    ),
    HydronicSensorDescription(
        key="solar_power",
        models=ECO,
        component="solar",
        field="power",
        part=SOLAR,
        translation_key="solar_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    *_eco_messages("buffer_messages", "buffer", BUFFER),
    *_eco_messages("solar_messages", "solar", SOLAR),
    *(
        description
        for number in HEATING_CIRCUITS
        for description in _eco_circuit_sensors(number)
    ),
)


def _non_negative(value: float | None) -> float | None:
    """A gas reading; the boiler reports a negative one while it has none."""
    return None if value is None or value < 0 else value


def _gas_reading(field: str) -> Callable[[Any], float | None]:
    """Read a gas field, dropping the negative value that marks no reading."""

    def value(boiler: Any) -> float | None:
        return _non_negative(getattr(boiler, field))

    return value


def _draught(value: float | None) -> float | None:
    """The draught; the boiler reports -90000 Pa or below while it has none."""
    return None if value is None or value <= NO_DRAUGHT_READING else value


def _error(slot: int) -> HydronicSensorDescription:
    """One of the pelletstar's ten error-code slots, shown as its display text."""
    return HydronicSensorDescription(
        key=f"error_{slot}",
        models=HERZ,
        component="faults",
        translation_key="error",
        translation_placeholders={"slot": str(slot)},
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=slot <= ENABLED_ERROR_SLOTS,
        value_fn=lambda faults: _error_value(getattr(faults, f"error_code_{slot}")),
    )


def _error_value(code: int | None) -> str | None:
    """The boiler's own text for an error code, or the code itself."""
    if code is None:
        return None
    return error_text(code) or str(code)


def _return_mixer(outputs: OutputByte2 | None) -> str | None:
    """Which way the return mixer is driven."""
    if outputs is None:
        return None
    if OutputByte2.RETURN_MIXER_OPEN in outputs:
        return "opening"
    if OutputByte2.RETURN_MIXER_CLOSE in outputs:
        return "closing"
    return "idle"


HERZ_SENSORS: tuple[HydronicSensorDescription, ...] = (
    _temperature(HERZ, "boiler", "boiler_temperature"),
    _temperature(HERZ, "boiler", "demand_temperature"),
    HydronicSensorDescription(
        key="boiler_state",
        models=HERZ,
        component="boiler",
        field="state",
        translation_key="boiler_state",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(BoilerState),
    ),
    _percentage(HERZ, "boiler", "output"),
    _temperature(HERZ, "boiler", "return_temperature"),
    _temperature(HERZ, "boiler", "return_setpoint"),
    _temperature(HERZ, "boiler", "flue_gas_temperature"),
    _temperature(HERZ, "boiler", "combustion_chamber_temperature"),
    _temperature(HERZ, "boiler", "stoker_temperature"),
    _percentage(HERZ, "boiler", "induced_draught_fan"),
    _percentage(HERZ, "boiler", "secondary_air_flap"),
    _percentage(HERZ, "boiler", "fan_speed"),
    _percentage(HERZ, "boiler", "fan_speed_setpoint"),
    *(
        HydronicSensorDescription(
            key=key,
            models=HERZ,
            component="boiler",
            translation_key=key,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=_gas_reading(key),
        )
        for key in ("oxygen", "oxygen_setpoint", "co2", "co2_setpoint")
    ),
    _operating_hours("full_load"),
    _operating_hours("modulating"),
    _operating_hours("part_load"),
    _operating_hours("ignition_and_burnout"),
    _operating_hours("boiler_runtime"),
    _operating_hours("total"),
    _percentage(HERZ, "combustion", "grate_activity"),
    _percentage(HERZ, "combustion", "feed_activity"),
    HydronicSensorDescription(
        key="draught",
        models=HERZ,
        component="combustion",
        translation_key="draught",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda combustion: _draught(combustion.draught),
    ),
    HydronicSensorDescription(
        key="draught_setpoint",
        models=HERZ,
        component="combustion",
        translation_key="draught_setpoint",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HydronicSensorDescription(
        key="fuel_consumption",
        models=HERZ,
        component="fuel",
        translation_key="fuel_consumption",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    HydronicSensorDescription(
        key="return_mixer",
        models=HERZ,
        component="inputs_outputs",
        translation_key="return_mixer",
        device_class=SensorDeviceClass.ENUM,
        options=["opening", "closing", "idle"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda io: _return_mixer(io.output_byte_2),
    ),
    HydronicSensorDescription(
        key="fault_status",
        models=HERZ,
        component="faults",
        translation_key="fault_status",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(FaultStatus),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    *(_error(slot) for slot in range(1, ERROR_CODE_SLOTS + 1)),
)

SENSOR_DESCRIPTIONS: tuple[HydronicSensorDescription, ...] = (
    *BELIMO_SENSORS,
    *ECO_SENSORS,
    *HERZ_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hydronic sensor platform."""
    runtime_data = entry.runtime_data
    async_add_entities(
        _sensor_class(description)(runtime_data, description)
        for description in served_descriptions(runtime_data, SENSOR_DESCRIPTIONS)
    )


def _sensor_class(
    description: HydronicSensorDescription,
) -> type[HydronicSensor | HydronicTotalSensor]:
    """Pick the entity class a description's semantics ask for."""
    if description.state_class in (
        SensorStateClass.TOTAL,
        SensorStateClass.TOTAL_INCREASING,
    ):
        return HydronicTotalSensor
    return HydronicSensor


class HydronicSensor(HydronicEntity, SensorEntity):
    """Defines a Hydronic sensor."""

    entity_description: HydronicSensorDescription

    @property
    @override
    def native_value(self) -> StateType:
        value = self.entity_description.value(self.coordinator.device)
        # IntEnum stringifies as the raw int; use the option slug.
        if isinstance(value, IntEnum):
            return value.name.lower()
        return cast("StateType", value)

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        if (unit_fn := self.entity_description.unit_fn) is None:
            return super().native_unit_of_measurement
        return unit_fn(self.coordinator.device)

    @property
    @override
    def available(self) -> bool:
        """Unavailable, too, while the device has not said what unit it uses."""
        if self.entity_description.unit_fn is not None and (
            self.native_unit_of_measurement is None
        ):
            return False
        return super().available


class HydronicTotalSensor(HydronicEntity, RestoreSensor):
    """A long-term statistic: it holds its last value, and may outlive the device."""

    entity_description: HydronicSensorDescription

    @property
    @override
    def available(self) -> bool:
        """Stay available, so a device going quiet leaves no gap in statistics."""
        return True

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_sensor_data()) is None:
            return
        if isinstance(last_data.native_value, (int, float)):
            self._attr_native_value = last_data.native_value

    @property
    @override
    def native_value(self) -> int | float | None:
        value = self.entity_description.value(self.coordinator.device)
        last = self._attr_native_value
        if isinstance(value, (int, float)) and not (
            # A counter read mid-update can dip; hold it rather than reset it.
            isinstance(last, (int, float)) and last * 0.99 <= value < last
        ):
            self._attr_native_value = value
        return cast("int | float | None", self._attr_native_value)
