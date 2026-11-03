"""Support for Hydronic selects."""

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, override

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from modbus_connection import ModbusError

from .const import DOMAIN
from .entity import (
    BUFFER,
    SOLAR,
    HydronicEntity,
    HydronicEntityDescription,
    enum_options,
    served_descriptions,
)
from .hydronic_modbus import DeviceModel
from .hydronic_modbus.belimo import BusFailAction, DeltaTLimitation, OverrideControl
from .hydronic_modbus.eco import (
    HEATING_CIRCUITS,
    BufferOperatingMode,
    CircuitOperatingMode,
    QuickSelectMode,
    SolarOperatingMode,
    circuit_mode_name,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .data import HydronicConfigEntry

PARALLEL_UPDATES = 1

BELIMO = frozenset({DeviceModel.BELIMO_ENERGY_VALVE})
ECO = frozenset({DeviceModel.ECO_CONTROLLER})


@dataclass(frozen=True, kw_only=True)
class HydronicSelectDescription(SelectEntityDescription, HydronicEntityDescription):
    """Describe a Hydronic select backed by an enum register."""

    options_enum: type[IntEnum]


SELECT_DESCRIPTIONS: tuple[HydronicSelectDescription, ...] = (
    HydronicSelectDescription(
        key="override_control",
        models=BELIMO,
        component="control",
        translation_key="override_control",
        options=enum_options(OverrideControl),
        options_enum=OverrideControl,
    ),
    HydronicSelectDescription(
        key="delta_t_limitation",
        models=BELIMO,
        component="delta_t_manager",
        translation_key="delta_t_limitation",
        entity_category=EntityCategory.CONFIG,
        options=enum_options(DeltaTLimitation),
        options_enum=DeltaTLimitation,
    ),
    HydronicSelectDescription(
        key="bus_fail_action",
        models=BELIMO,
        component="bus_fail",
        translation_key="bus_fail_action",
        entity_category=EntityCategory.CONFIG,
        options=enum_options(BusFailAction),
        options_enum=BusFailAction,
    ),
    HydronicSelectDescription(
        key="quick_select",
        models=ECO,
        component="quick_select",
        translation_key="quick_select",
        options=enum_options(QuickSelectMode),
        options_enum=QuickSelectMode,
    ),
    HydronicSelectDescription(
        key="solar_mode",
        models=ECO,
        component="solar_mode",
        field="mode",
        part=SOLAR,
        translation_key="solar_mode",
        options=enum_options(SolarOperatingMode),
        options_enum=SolarOperatingMode,
    ),
    HydronicSelectDescription(
        key="buffer_mode",
        models=ECO,
        component="buffer_mode",
        field="mode",
        part=BUFFER,
        translation_key="buffer_mode",
        options=enum_options(BufferOperatingMode),
        options_enum=BufferOperatingMode,
    ),
    *(
        HydronicSelectDescription(
            key=circuit_mode_name(number),
            models=ECO,
            component=circuit_mode_name(number),
            field="mode",
            part=("heating_circuit", number),
            translation_key="circuit_mode",
            options=enum_options(CircuitOperatingMode),
            options_enum=CircuitOperatingMode,
        )
        for number in HEATING_CIRCUITS
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hydronic select platform."""
    runtime_data = entry.runtime_data
    async_add_entities(
        HydronicSelect(runtime_data, description)
        for description in served_descriptions(runtime_data, SELECT_DESCRIPTIONS)
    )


class HydronicSelect(HydronicEntity, SelectEntity):
    """Defines a Hydronic select entity."""

    entity_description: HydronicSelectDescription

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = self.entity_description.value(self.coordinator.device)
        return value.name.lower() if isinstance(value, IntEnum) else None

    @override
    async def async_select_option(self, option: str) -> None:
        """Write the selected option, then read the settings back."""
        description = self.entity_description
        value = description.options_enum[option.upper()]
        component = self.coordinator.device.component(description.component)
        try:
            await component.write(description.field or description.key, value)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
            ) from err
        await self.coordinator.async_request_refresh()
