"""Read and control hydronic heating devices over Modbus, as typed objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .belimo import BelimoEnergyValve
from .eco import EcoController
from .herz import HerzPelletstar
from .model import (
    CONNECT_DELAY,
    DeviceModel,
    HydronicComponent,
    HydronicDevice,
    UpdateReport,
)

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

__all__ = [
    "CONNECT_DELAY",
    "DEVICE_CLASSES",
    "BelimoEnergyValve",
    "DeviceModel",
    "EcoController",
    "HerzPelletstar",
    "HydronicComponent",
    "HydronicDevice",
    "UpdateReport",
    "create_device",
]

DEVICE_CLASSES: dict[DeviceModel, type[HydronicDevice]] = {
    DeviceModel.BELIMO_ENERGY_VALVE: BelimoEnergyValve,
    DeviceModel.ECO_CONTROLLER: EcoController,
    DeviceModel.HERZ_PELLETSTAR: HerzPelletstar,
}


def create_device(
    model: DeviceModel | str, unit: ModbusUnit, *, timeout: float | None = None
) -> HydronicDevice:
    """The device object for ``model`` over ``unit``, at its defaults.

    Raises ``ValueError`` for a model this library does not know.
    """
    return DEVICE_CLASSES[DeviceModel(model)](unit, timeout=timeout)
