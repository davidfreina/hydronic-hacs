"""Support for Hydronic switches."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import STATE_ON, EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from modbus_connection import ModbusError

from .const import DOMAIN, KEEPALIVE_INTERVAL
from .entity import HydronicEntity, HydronicEntityDescription, served_descriptions
from .hydronic_modbus import DeviceModel
from .hydronic_modbus.eco import (
    HEATING_CIRCUITS,
    ExternalKeepAlive,
    circuit_control_name,
)

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import HydronicConfigEntry, HydronicRuntimeData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

ECO = frozenset({DeviceModel.ECO_CONTROLLER})


@dataclass(frozen=True, kw_only=True)
class HydronicSwitchDescription(SwitchEntityDescription, HydronicEntityDescription):
    """Describe a Hydronic switch backed by a 0/1 register."""


SWITCH_DESCRIPTIONS: tuple[HydronicSwitchDescription, ...] = tuple(
    description
    for number in HEATING_CIRCUITS
    for description in (
        HydronicSwitchDescription(
            key=f"heating_circuit_{number}_enabled",
            models=ECO,
            component=circuit_control_name(number),
            field="enabled",
            part=("heating_circuit", number),
            translation_key="circuit_enabled",
        ),
        HydronicSwitchDescription(
            key=f"heating_circuit_{number}_external_control",
            models=ECO,
            component=circuit_control_name(number),
            field="external_control",
            part=("heating_circuit", number),
            translation_key="circuit_external_control",
            entity_category=EntityCategory.CONFIG,
        ),
    )
)

KEEPALIVE_DESCRIPTION = HydronicSwitchDescription(
    key="external_keepalive",
    models=ECO,
    component="external_keepalive",
    translation_key="external_keepalive",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HydronicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hydronic switch platform."""
    runtime_data = entry.runtime_data
    entities: list[SwitchEntity] = [
        HydronicSwitch(runtime_data, description)
        for description in served_descriptions(runtime_data, SWITCH_DESCRIPTIONS)
    ]
    entities.extend(
        HydronicKeepAliveSwitch(runtime_data, description)
        for description in served_descriptions(runtime_data, (KEEPALIVE_DESCRIPTION,))
    )
    async_add_entities(entities)


class HydronicSwitch(HydronicEntity, SwitchEntity):
    """A switch writing 1 or 0 to a register, then reading it back."""

    entity_description: HydronicSwitchDescription

    @property
    @override
    def is_on(self) -> bool | None:
        value = self.entity_description.value(self.coordinator.device)
        return None if value is None else value == 1

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_write(1)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_write(0)

    async def _async_write(self, value: int) -> None:
        description = self.entity_description
        component = self.coordinator.device.component(description.component)
        try:
            await component.write(description.field or description.key, value)
        except ModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
            ) from err
        await self.coordinator.async_request_refresh()


class HydronicKeepAliveSwitch(HydronicEntity, RestoreEntity, SwitchEntity):
    """
    Keep the controller's external keep-alive going while on.

    The controller raises an alarm unless whoever controls it from outside
    changes the keep-alive at least every 30 seconds. While this is on,
    Home Assistant does that itself. The state survives a restart.
    """

    entity_description: HydronicSwitchDescription
    _attr_is_on = False

    def __init__(
        self,
        runtime_data: HydronicRuntimeData,
        entity_description: HydronicSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(runtime_data, entity_description)
        self._keepalive = cast(
            "ExternalKeepAlive",
            runtime_data.device.component(entity_description.component),
        )
        self._cancel_beat: CALLBACK_TYPE | None = None
        self._failing = False

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state == STATE_ON:
            await self._async_start()
        self.async_on_remove(self._stop)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_start()
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        self._stop()
        self.async_write_ha_state()

    async def _async_start(self) -> None:
        self._attr_is_on = True
        if self._cancel_beat is None:
            self._cancel_beat = async_track_time_interval(
                self.hass,
                self._async_beat,
                timedelta(seconds=KEEPALIVE_INTERVAL),
                name=f"{self.entity_id} keep-alive",
            )
        await self._async_beat()

    @callback
    def _stop(self) -> None:
        self._attr_is_on = False
        if self._cancel_beat is not None:
            self._cancel_beat()
            self._cancel_beat = None

    async def _async_beat(self, _now: datetime | None = None) -> None:
        try:
            await self._keepalive.async_beat()
        except ModbusError as err:
            if not self._failing:
                _LOGGER.warning(
                    "%s: failed to send the external keep-alive: %s",
                    self.coordinator.name,
                    err,
                )
                self._failing = True
            return
        if self._failing:
            _LOGGER.info("%s: external keep-alive sent again", self.coordinator.name)
            self._failing = False
