"""Tests for the Hydronic integration."""

import struct
from typing import TYPE_CHECKING

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from modbus_connection import IllegalDataAddressError

from custom_components.hydronic.const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    TYPE_SERIAL,
    TYPE_TCP,
)
from custom_components.hydronic.hydronic_modbus import DeviceModel

if TYPE_CHECKING:
    from modbus_connection.mock import MockModbusUnit

MOCK_TCP_INPUT = {
    CONF_MODEL: DeviceModel.BELIMO_ENERGY_VALVE.value,
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}
MOCK_ENTRY_DATA = {CONF_TYPE: TYPE_TCP, **MOCK_TCP_INPUT}

MOCK_SERIAL_INPUT = {
    CONF_MODEL: DeviceModel.BELIMO_ENERGY_VALVE.value,
    CONF_DEVICE: "/dev/ttyUSB0",
    CONF_BAUDRATE: DEFAULT_BAUDRATE,
    CONF_UNIT_ID: 1,
}
MOCK_SERIAL_ENTRY_DATA = {CONF_TYPE: TYPE_SERIAL, **MOCK_SERIAL_INPUT}


def int32_words(value: int) -> list[int]:
    """A signed 32-bit value as two registers, high word first."""
    raw = value & 0xFFFFFFFF
    return [raw >> 16, raw & 0xFFFF]


def seed_belimo(unit: MockModbusUnit) -> None:
    """Seed a Belimo Energy Valve reporting flow in m³/h."""
    unit.holding.update(
        {
            0: 6550,  # setpoint -> 65.5 %
            4: 6312,  # relative position -> 63.12 %
            9: list(reversed(int32_words(1234))),  # flow -> 1.234 m³/h
            13: 4210,  # sensor 1 -> 42.1 °C
            19: 4550,  # T1 -> 45.5 °C
            21: 3020,  # T2 -> 30.2 °C
            23: 1530,  # delta T -> 15.3 K
            33: list(reversed(int32_words(12345))),  # heating power -> 12.345 kW
            39: 1000,  # delta T setpoint -> 10.0 K
            59: list(reversed(int32_words(3141592))),  # volume -> 31415.92 m³
            71: list(reversed(int32_words(98765))),  # heating energy -> 98765 kWh
            108: 2,  # bus fail action -> close
            157: int32_words(0),  # malfunction -> none
            147: 1,  # flow unit -> m³/h
            179: 1,  # delta T limitation -> dT-Manager
            180: 2,  # delta T manager status -> active
        }
    )


def seed_eco(unit: MockModbusUnit) -> None:
    """Seed an eco controller; only circuit 3 has the secondary sensor."""
    unit.holding.update(
        {
            6: int32_words(1),  # quick select -> winter
            1116: int32_words(1),  # circulation pump running
            1120: int32_words(3),  # buffer mode -> automatic summer
            2118: int32_words(5),  # circuit 1 mode -> automatic 1
            2106: int32_words(1),  # circuit 1 pump running
            0x1FC0: int32_words(2),  # solar mode -> automatic
            20: int32_words(-52),  # outdoor -> -5.2 °C
            1100: int32_words(55),  # storage top
            1102: int32_words(68),  # storage top 1
            2100: int32_words(345),  # circuit 1 flow -> 34.5 °C
            2104: int32_words(38),  # circuit 1 flow setpoint -> 38 °C
            2108: int32_words(-1),  # circuit 1 mixer closing
            2150: int32_words(4),  # circuit 1 mixer runtime -> 4 s
            2152: int32_words(6),  # circuit 1 mixer runtime target -> 6 s
            2208: int32_words(1),  # circuit 2 mixer opening
            2300: int32_words(412),  # circuit 3 flow -> 41.2 °C
            2346: int32_words(398),  # circuit 3 secondary -> 39.8 °C
            2322: int32_words(1),  # circuit 3 released
            2324: int32_words(425),  # circuit 3 external setpoint -> 42.5 °C
            2336: int32_words(1),  # circuit 3 under external control
            0x1FBE: list(
                struct.unpack(">HH", struct.pack(">f", 2.5))
            ),  # solar -> 2500 W
        }
    )
    for base in (2100, 2200):
        unit.fail_read(base + 46, IllegalDataAddressError())


def seed_herz(unit: MockModbusUnit) -> None:
    """Seed a HERZ pelletstar with one error code set."""
    unit.holding.update(
        {
            0: int32_words(725),  # boiler -> 72.5 °C
            4: int32_words(8),  # state -> modulating
            26: int32_words(-10),  # oxygen -> no reading
            30: int32_words(105),  # co2 -> 10.5 %
            22: int32_words(18500),  # fan speed -> 1850 rpm
            44: int32_words(123456),  # full load -> 12345.6 h
            86: int32_words(-150),  # draught -> -15.0 Pa
            92: int32_words(1),  # collective fault
            292: int32_words(0x88),  # outputs 2 -> return pump, no alarm
            294: int32_words(0x01),  # outputs 3 -> overtemperature monitor satisfied
            298: int32_words(0x02),  # inputs 2 -> hopper empty, STB tripped
            300: int32_words(69),  # error code 1 -> STB
            302: int32_words(217),  # error code 2 -> a code without a text
            7078: int32_words(5321),  # fuel consumption -> 5321 kg
        }
    )
