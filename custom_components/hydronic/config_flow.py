"""Config flow for Hydronic devices."""

import logging
from typing import TYPE_CHECKING, Any, override

import probatio
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from modbus_connection import ModbusError

from .const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MANUFACTURERS,
    MODEL_NAMES,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .helpers import create_modbus_params
from .hydronic_modbus import DeviceModel, HydronicDevice, create_device

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

STEP_RECONFIGURE_SERIAL = "reconfigure_serial"
STEP_RECONFIGURE_TCP = "reconfigure_tcp"

MODEL_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[model.value for model in DeviceModel],
        mode=SelectSelectorMode.DROPDOWN,
        translation_key=CONF_MODEL,
    )
)

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)),
    probatio.Coerce(int),
)

TCP_FIELDS: dict[Any, Any] = {
    probatio.Required(CONF_HOST): TextSelector(),
    probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
        NumberSelector(
            NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
        ),
        probatio.Coerce(int),
    ),
    probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
}

SERIAL_FIELDS: dict[Any, Any] = {
    probatio.Required(CONF_DEVICE): SerialPortSelector(),
    probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): probatio.All(
        NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1)),
        probatio.Coerce(int),
    ),
    probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
}

STEP_TCP_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_MODEL): MODEL_SELECTOR, **TCP_FIELDS}
)
STEP_SERIAL_DATA_SCHEMA = probatio.Schema(
    {probatio.Required(CONF_MODEL): MODEL_SELECTOR, **SERIAL_FIELDS}
)
STEP_RECONFIGURE_TCP_DATA_SCHEMA = probatio.Schema(TCP_FIELDS)
STEP_RECONFIGURE_SERIAL_DATA_SCHEMA = probatio.Schema(SERIAL_FIELDS)


class CannotConnectError(HomeAssistantError):
    """The device answered nothing the integration reads."""


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Read the device once, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        device: HydronicDevice = create_device(data[CONF_MODEL], unit)
        report = await device.async_update()
    if not report.updated:
        errors = report.failed.values()
        raise CannotConnectError(next(iter(errors), "no component answered"))


def _link_match(data: Mapping[str, Any]) -> dict[str, Any]:
    """The entry data naming the same device on the same link."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        keys: tuple[str, ...] = (CONF_TYPE, CONF_DEVICE, CONF_UNIT_ID)
    else:
        keys = (CONF_TYPE, CONF_HOST, CONF_PORT, CONF_UNIT_ID)
    return {key: data[key] for key in keys}


def _title(model: DeviceModel) -> str:
    """A name for a new entry: the device's maker and model."""
    return f"{MANUFACTURERS[model]} {MODEL_NAMES[model]}"


class HydronicConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Hydronic config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how the device is reached."""
        return self.async_show_menu(
            step_id="user", menu_options=[TYPE_TCP, TYPE_SERIAL]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a device reached over the network."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a device reached over a serial port."""
        return await self._async_step_link(
            TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_link(
        self,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the model and link settings, then probe the device."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            self._async_abort_entries_match(_link_match(data))
            errors, description_placeholders = await self._async_validate(data)
            if not errors:
                return self.async_create_entry(
                    title=_title(DeviceModel(data[CONF_MODEL])), data=data
                )

        return self.async_show_form(
            step_id=connection_type,
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle updating an existing entry's connection details."""
        entry = self._get_reconfigure_entry()
        if entry.data[CONF_TYPE] == TYPE_SERIAL:
            return await self.async_step_reconfigure_serial()
        return await self.async_step_reconfigure_tcp()

    async def async_step_reconfigure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle updating a device reached over the network."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_TCP,
            TYPE_TCP,
            STEP_RECONFIGURE_TCP_DATA_SCHEMA,
            user_input,
        )

    async def async_step_reconfigure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle updating a device reached over a serial port."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_SERIAL,
            TYPE_SERIAL,
            STEP_RECONFIGURE_SERIAL_DATA_SCHEMA,
            user_input,
        )

    async def _async_step_reconfigure_link(
        self,
        step_id: str,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the entry's model behind them."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_TYPE: connection_type,
                CONF_MODEL: entry.data[CONF_MODEL],
                **user_input,
            }
            if _link_match(data) != _link_match(entry.data):
                self._async_abort_entries_match(_link_match(data))

            # The entry holds its link open; new line settings on the same
            # port could not be probed beside it, so let go of it first.
            relinking = False
            if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
                current = create_modbus_params(entry.data)
                new = create_modbus_params(data)
                if new.endpoint == current.endpoint and new != current:
                    relinking = await self.hass.config_entries.async_unload(
                        entry.entry_id
                    )

            errors, description_placeholders = await self._async_validate(data)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=data)
            if relinking:
                await self.hass.config_entries.async_setup(entry.entry_id)

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or entry.data
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Probe the device, returning the errors and placeholders to show."""
        try:
            await _async_probe(self.hass, data)
        except (ModbusError, HomeAssistantError) as err:
            return {"base": "cannot_connect"}, {"error": str(err) or type(err).__name__}
        except Exception:
            _LOGGER.exception("Unexpected error probing the device")
            return {"base": "unknown"}, {}
        return {}, {}
