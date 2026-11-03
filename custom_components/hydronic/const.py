"""Constants for the Hydronic integration."""

from .hydronic_modbus import DeviceModel

DOMAIN = "hydronic"

DEFAULT_BAUDRATE = 9600
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
SCAN_INTERVAL = 10
SETTINGS_SCAN_INTERVAL = 60
# Mixers move in pulses of a few seconds; a slower poll misses them.
FAST_SCAN_INTERVAL = 0.3
# The controller alarms after 30 s without an external keep-alive.
KEEPALIVE_INTERVAL = 10

CONF_BAUDRATE = "baudrate"
CONF_MODEL = "model"
CONF_UNIT_ID = "unit_id"

TYPE_SERIAL = "serial"
TYPE_TCP = "tcp"

MANUFACTURERS: dict[DeviceModel, str] = {
    DeviceModel.BELIMO_ENERGY_VALVE: "Belimo",
    DeviceModel.ECO_CONTROLLER: "ENERGIEFREUND",
    DeviceModel.HERZ_PELLETSTAR: "HERZ",
}

MODEL_NAMES: dict[DeviceModel, str] = {
    DeviceModel.BELIMO_ENERGY_VALVE: "Energy Valve 4",
    DeviceModel.ECO_CONTROLLER: "ECO Regulation",
    DeviceModel.HERZ_PELLETSTAR: "pelletstar",
}
