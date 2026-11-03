"""Custom types for the Hydronic integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import HydronicDataUpdateCoordinator
    from .hydronic_modbus import HydronicDevice


type HydronicConfigEntry = ConfigEntry[HydronicRuntimeData]


@dataclass
class HydronicRuntimeData:
    """Data the integration keeps for one config entry."""

    readings: HydronicDataUpdateCoordinator
    settings: HydronicDataUpdateCoordinator
    device_id: str  # the registry id parts hang off
    fast: HydronicDataUpdateCoordinator | None = None  # only with fast components

    @property
    def device(self) -> HydronicDevice:
        """The device object both coordinators poll."""
        return self.readings.device

    @property
    def served_components(self) -> frozenset[str]:
        """Component names this device polls, answered or not."""
        return frozenset(self.device.components)

    @property
    def coordinators(self) -> list[HydronicDataUpdateCoordinator]:
        """Every coordinator polling this device."""
        return [
            coordinator
            for coordinator in (self.readings, self.settings, self.fast)
            if coordinator is not None
        ]

    def coordinator_for(self, component: str) -> HydronicDataUpdateCoordinator:
        """Which coordinator owns a given component's data."""
        if component in self.device.readings_components:
            return self.readings
        if self.fast is not None and component in self.device.fast_components:
            return self.fast
        return self.settings
