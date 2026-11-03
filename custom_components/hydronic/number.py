"""Support for Hydronic numbers."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from modbus_connection import ModbusError

from .const import DOMAIN
from .entity import HydronicEntity, HydronicEntityDescription, served_descriptions
from .hydronic_modbus import DeviceModel
from .hydronic_modbus.eco import HEATING_CIRCUITS, circuit_control_name

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import HydronicConfigEntry

PARALLEL_UPDATES = 1

BELIMO = frozenset({DeviceModel.BELIMO_ENERGY_VALVE})
ECO = frozenset({DeviceModel.ECO_CONTROLLER})


@dataclass(frozen=True, kw_only=True)
class HydronicNumberDescription(NumberEntityDescription, HydronicEntityDescription):
    """Describe a Hydronic number entity."""


NUMBER_DESCRIPTIONS: tuple[HydronicNumberDescription, ...] = (
    HydronicNumberDescription(
        key="setpoint",
        models=BELIMO,
        component="control",
        translation_key="setpoint",
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=0.01,
        mode=NumberMode.SLIDER,
    ),
    HydronicNumberDescription(
        key="delta_t_setpoint",
        models=BELIMO,
        component="delta_t_manager",
        translation_key="delta_t_setpoint",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        native_min_value=0,
        native_max_value=1000,
        native_step=0.01,
        mode=NumberMode.BOX,
    ),
    *(
        HydronicNumberDescription(
            key=f"heating_circuit_{number}_external_flow_setpoint",
            models=ECO,
            component=circuit_control_name(number),
            field="external_flow_setpoint",
            part=("heating_circuit", number),
            translation_key="circuit_external_flow_setpoint",
            device_class=NumberDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            native_min_value=0,
            native_max_value=80,
            native_step=0.1,
            mode=NumberMode.BOX,
        )
        for number in HEATING_CIRCUITS
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hydronic number platform."""
    runtime_data = entry.runtime_data
    async_add_entities(
        HydronicNumber(runtime_data, description)
        for description in served_descriptions(runtime_data, NUMBER_DESCRIPTIONS)
    )


class HydronicNumber(HydronicEntity, NumberEntity):
    """Defines a Hydronic number entity."""

    entity_description: HydronicNumberDescription

    @property
    @override
    def native_value(self) -> float | None:
        value = self.entity_description.value(self.coordinator.device)
        return None if value is None else float(value)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Write the value to the device, then read the settings back."""
        description = self.entity_description
        component = self.coordinator.device.component(description.component)
        try:
            await component.write(description.field or description.key, value)
        except (ValueError, OverflowError) as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_value",
                translation_placeholders={"value": str(value)},
            ) from err
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
            ) from err
        await self.coordinator.async_request_refresh()
