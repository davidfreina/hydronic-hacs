"""Helpers for the Hydronic integration."""

from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from modbus_connection import ModbusSerialParams, ModbusTcpParams

from .const import CONF_BAUDRATE, TYPE_SERIAL

if TYPE_CHECKING:
    from collections.abc import Mapping


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data."""
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE], baudrate=data[CONF_BAUDRATE]
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
