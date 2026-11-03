"""Base entity for Hydronic devices."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HydronicDataUpdateCoordinator
from .hydronic_modbus import DeviceModel, HydronicDevice

if TYPE_CHECKING:
    from collections.abc import Callable
    from enum import IntEnum

    from .data import HydronicRuntimeData

# A part of the device, as (device translation key, number); the number is
# None for a part the device has only one of.
type HydronicPart = tuple[str, int | None]

# The eco controller's single parts, each a device of its own under it.
SOLAR: HydronicPart = ("solar", None)
BUFFER: HydronicPart = ("buffer", None)


@dataclass(frozen=True, kw_only=True)
class HydronicEntityDescription(EntityDescription):
    """Describe a Hydronic entity backed by one field of one component."""

    models: frozenset[DeviceModel]
    component: str  # attribute name on the device object, e.g. 'meters'
    field: str | None = None  # attribute on the component; defaults to the key
    part: HydronicPart | None = None  # None keeps the entity on the device
    value_fn: Callable[[Any], Any] | None = None  # derives the value instead

    def value(self, device: HydronicDevice) -> Any:
        """Read this entity's value off the device."""
        component = device.component(self.component)
        if self.value_fn is not None:
            return self.value_fn(component)
        return getattr(component, self.field or self.key)


class HydronicEntity(CoordinatorEntity[HydronicDataUpdateCoordinator]):
    """Defines a base Hydronic entity."""

    _attr_has_entity_name = True
    entity_description: HydronicEntityDescription

    def __init__(
        self,
        runtime_data: HydronicRuntimeData,
        entity_description: HydronicEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(runtime_data.coordinator_for(entity_description.component))
        self.entity_description = entity_description
        entry_id = self.coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{entity_description.key}"
        self._attr_device_info = self._device_info(runtime_data, entry_id)

    def _device_info(
        self, runtime_data: HydronicRuntimeData, entry_id: str
    ) -> dr.DeviceInfo:
        """Place the entity on the device, or on the part it measures."""
        if (part := self.entity_description.part) is None:
            return self.coordinator.device_info
        kind, number = part
        if number is None:
            return dr.DeviceInfo(
                identifiers={(DOMAIN, f"{entry_id}_{kind}")},
                via_device_id=runtime_data.device_id,
                translation_key=kind,
            )
        return dr.DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{kind}_{number}")},
            via_device_id=runtime_data.device_id,
            translation_key=kind,
            translation_placeholders={"number": str(number)},
        )

    @property
    @override
    def available(self) -> bool:
        """Whether this entity's component answered the most recent poll."""
        if not super().available:
            return False
        return self.entity_description.component not in self.coordinator.data.failed


def served_descriptions[D: HydronicEntityDescription](
    runtime_data: HydronicRuntimeData, descriptions: tuple[D, ...]
) -> list[D]:
    """The descriptions for this device's model and served components."""
    model = DeviceModel(runtime_data.device.model)
    served = runtime_data.served_components
    return [
        description
        for description in descriptions
        if model in description.models and description.component in served
    ]


def enum_options(enum_type: type[IntEnum]) -> list[str]:
    """The option slugs a device enum maps to."""
    return [member.name.lower() for member in enum_type]
