"""Data update coordinator for Hydronic devices."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import ModbusError
from propcache.api import cached_property

from .const import DOMAIN, MANUFACTURERS, MODEL_NAMES
from .hydronic_modbus import DeviceModel, HydronicDevice, UpdateReport

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import timedelta

    from homeassistant.core import HomeAssistant

    from .data import HydronicConfigEntry

_LOGGER = logging.getLogger(__name__)


class HydronicDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Run one of the device's update methods on its own interval."""

    config_entry: HydronicConfigEntry
    device: HydronicDevice

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HydronicConfigEntry,
        device: HydronicDevice,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta | None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=interval,
        )
        self.device = device
        self._poll = poll
        self._failed: frozenset[str] = frozenset()

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        model = DeviceModel(self.device.model)
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer=MANUFACTURERS[model],
            model=MODEL_NAMES[model],
            name=self.config_entry.title,
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self._poll()
        except ModbusError as err:
            # ModbusConnectionError (dead link) and ModbusTimeoutError reach
            # here; per-block failures once alive land in report.failed instead.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        if report.failed and not report.updated:
            errors = list(report.failed.values())
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup("all components failed to refresh", errors)

        for name in sorted(report.failed.keys() - self._failed):
            _LOGGER.warning(
                "%s: %s failed to refresh and is keeping its previous values: %s",
                self.name,
                name,
                report.failed[name],
            )
        for name in sorted(self._failed - report.failed.keys()):
            _LOGGER.info("%s: %s is available again", self.name, name)
        self._failed = frozenset(report.failed)
        return report
