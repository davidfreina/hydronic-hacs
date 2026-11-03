"""Tests for the Hydronic config flow."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, _patch, call, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from modbus_connection import (
    IllegalDataAddressError,
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    get_schema_suggested_value,
)

from custom_components.hydronic.config_flow import (
    STEP_RECONFIGURE_SERIAL,
    STEP_RECONFIGURE_TCP,
)
from custom_components.hydronic.const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from custom_components.hydronic.hydronic_modbus import DeviceModel

from . import (
    MOCK_ENTRY_DATA,
    MOCK_SERIAL_ENTRY_DATA,
    MOCK_SERIAL_INPUT,
    MOCK_TCP_INPUT,
    seed_eco,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from homeassistant.core import HomeAssistant


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch[Any]:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant,
        params: ModbusSerialParams | ModbusTcpParams,
        unit_id: int,
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "custom_components.hydronic.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


async def _start_flow(hass: HomeAssistant, connection_type: str) -> str:
    """Open the flow, pick a connection type, and return the flow ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == [TYPE_TCP, TYPE_SERIAL]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": connection_type}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == connection_type
    assert result["errors"] == {}
    return result["flow_id"]


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("connection_type", "user_input", "expected_data"),
    [
        pytest.param(
            TYPE_TCP,
            {**MOCK_TCP_INPUT, CONF_PORT: 1502},
            {**MOCK_ENTRY_DATA, CONF_PORT: 1502},
            id="tcp",
        ),
        pytest.param(
            TYPE_SERIAL,
            {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200},
            {**MOCK_SERIAL_ENTRY_DATA, CONF_BAUDRATE: 19200},
            id="serial",
        ),
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    connection_type: str,
    user_input: dict[str, Any],
    expected_data: dict[str, Any],
) -> None:
    """Test a device is probed and its entry created."""
    flow_id = await _start_flow(hass, connection_type)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Belimo Energy Valve 4"
    assert result["data"] == expected_data
    assert result["result"].unique_id is None


@pytest.mark.usefixtures("mock_setup_entry")
async def test_flow_names_the_eco_controller(hass: HomeAssistant) -> None:
    """Test a new entry is titled after its device's maker and model."""
    connection = MockModbusConnection()
    seed_eco(connection.for_unit(1))
    flow_id = await _start_flow(hass, TYPE_TCP)
    with _patch_temporary_unit(connection):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {**MOCK_TCP_INPUT, CONF_MODEL: DeviceModel.ECO_CONTROLLER.value},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ENERGIEFREUND ECO Regulation"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ModbusTimeoutError(), "cannot_connect"),
        (IllegalDataAddressError(), "cannot_connect"),
    ],
)
async def test_flow_cannot_connect_then_recovers(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    error: Exception,
    expected: str,
) -> None:
    """Test a device that answers nothing shows an error, then can be retried."""
    flow_id = await _start_flow(hass, TYPE_TCP)
    unit = mock_connection.for_unit(1)
    unit.fail_requests(error)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert "error" in result["description_placeholders"]
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == (MOCK_TCP_INPUT[CONF_HOST])
    )

    unit.fail_requests(None)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test an unexpected error while probing is reported as unknown."""
    flow_id = await _start_flow(hass, TYPE_TCP)
    with patch(
        "custom_components.hydronic.config_flow._async_probe",
        side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_configure(flow_id, MOCK_TCP_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same device on the same link cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start_flow(hass, TYPE_TCP)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {**MOCK_TCP_INPUT, CONF_MODEL: DeviceModel.HERZ_PELLETSTAR.value},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_tcp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> None:
    """Test the link settings of an entry can be changed."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_RECONFIGURE_TCP
    assert (
        get_schema_suggested_value(result["data_schema"].schema, CONF_HOST)
        == MOCK_TCP_INPUT[CONF_HOST]
    )

    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.1.200", CONF_PORT: 502, "unit_id": 1},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**MOCK_ENTRY_DATA, CONF_HOST: "192.168.1.200"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_serial_error_then_success(
    hass: HomeAssistant, mock_connection: MockModbusConnection
) -> None:
    """Test a serial entry is reconfigured on the serial form."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_SERIAL_ENTRY_DATA)
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == STEP_RECONFIGURE_SERIAL

    unit = mock_connection.for_unit(1)
    unit.fail_requests(ModbusTimeoutError())
    new_input = {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
    del new_input[CONF_MODEL]
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )
    assert result["errors"] == {"base": "cannot_connect"}

    unit.fail_requests(None)
    with _patch_temporary_unit(mock_connection):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], new_input
        )
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_BAUDRATE] == 19200
    assert entry.data[CONF_MODEL] == MOCK_SERIAL_ENTRY_DATA[CONF_MODEL]


async def test_reconfigure_onto_another_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an entry cannot be moved onto a device another entry has."""
    mock_config_entry.add_to_hass(hass)
    other = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_ENTRY_DATA, CONF_HOST: "192.168.1.200"}
    )
    other.add_to_hass(hass)
    result = await other.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_ENTRY_DATA[CONF_HOST], CONF_PORT: 502, "unit_id": 1},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize("succeeds", [True, False])
async def test_reconfigure_line_settings_of_a_loaded_entry(
    hass: HomeAssistant,
    mock_connection: MockModbusConnection,
    succeeds: bool,
) -> None:
    """Test a loaded entry lets go of its port to probe new line settings."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_SERIAL_ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.hydronic.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

        result = await entry.start_reconfigure_flow(hass)
        unit = mock_connection.for_unit(1)
        if not succeeds:
            unit.fail_requests(ModbusTimeoutError())
        new_input = {**MOCK_SERIAL_INPUT, CONF_BAUDRATE: 19200}
        del new_input[CONF_MODEL]
        with (
            _patch_temporary_unit(mock_connection),
            patch.object(
                hass.config_entries,
                "async_unload",
                wraps=hass.config_entries.async_unload,
            ) as unload,
            patch.object(
                hass.config_entries,
                "async_setup",
                AsyncMock(wraps=hass.config_entries.async_setup),
            ) as setup,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], new_input
            )
        # Let go of the port before probing; a success then reloads on its own.
        assert unload.call_args_list[0] == call(entry.entry_id)
        if succeeds:
            assert result["reason"] == "reconfigure_successful"
        else:
            assert result["errors"] == {"base": "cannot_connect"}
            setup.assert_called_once_with(entry.entry_id)
        unit.fail_requests(None)
        await hass.async_block_till_done()
