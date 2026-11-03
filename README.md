# Hydronic

A Home Assistant integration for hydronic heating devices that speak Modbus:

| Device | What you get |
| :--- | :--- |
| **Belimo Energy Valve 4** | Valve position, flow, T1/T2, sensor 1 and ΔT, heating power, heating energy and volume meters, ΔT manager status, one problem sensor per malfunction bit; the setpoint and ΔT setpoint as numbers, the override, bus-fail action and ΔT limitation as selects |
| **HERZ pelletstar** | Boiler state, boiler, return, flue gas, combustion chamber and stoker temperatures, output, fan, O₂ and CO₂, draught, operating-hour counters, fuel consumption, the collective fault, the error codes as the boiler's own texts, and every input and output as a binary sensor |
| **ENERGIEFREUND ECO Regulation** | Outdoor, solar, hot water and buffer temperatures, solar power, the pumps; each heating circuit as its own device, with its mixer (state and running times); quick select and every operating mode as selects; external control by a building management system: per circuit the release, the external flow setpoint and the hand-over switch, and an external keep-alive Home Assistant keeps going itself |

This is the custom-component build of an integration headed for Home
Assistant Core. It ships its device library, hydronic-modbus (not published
yet), inside the integration, so it installs without the library being
published first.

The integration shares Modbus connections through Home Assistant's own
`modbus` integration. Two integrations talking to the same gateway use one
connection and take turns on it instead of competing for the device.

## Requirements

- Home Assistant 2026.10 or newer.
- A device reachable over Modbus TCP, directly or through a gateway, or over a
  serial port wired to its RS485 terminals.

## Installation

### Manually

Copy `custom_components/hydronic` into the `custom_components` folder of your
Home Assistant configuration and restart Home Assistant.

### HACS

HACS takes custom repositories from GitHub only. Once this repository is
mirrored there, add it under **Custom repositories** with the type
**Integration**, download **Hydronic** and restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=hydronic)

Go to **Settings** > **Devices & services** > **Add integration** and pick
**Hydronic**. Choose how the device is reached, then fill in:

- **Device**: which of the three devices it is. None of them reports its
  model over Modbus, so it can't be detected.
- **Host** and **Port**, or **Serial port** and **Baud rate**.
- **Modbus unit ID**: the device's Modbus address, `1` unless you changed it.

The integration reads the device once before it creates the entry, so a wrong
address or model is caught here. Add one entry per device. To change the
connection later, use **Reconfigure** on the entry.

## How it polls

Measurements are read every 10 seconds and settings every minute. After you
change a number, switch or select, the settings are read back right away.

The eco controller's mixers move in pulses of a few seconds, so their state is
read every 300 ms, one request per circuit. This runs on its own timer rather
than the coordinator's interval, which Home Assistant rounds to whole seconds;
a poll still running when the next one is due is skipped, not queued.

While **External keep-alive** is on, Home Assistant writes the controller's
external keep-alive (register 8) every 10 seconds, alternating 1 and 2. The
controller raises an alarm when it stops changing for 30 seconds while a
building management system controls it.

Each part of a device is read on its own. If the device refuses one part, only
the entities from that part become unavailable. Counters, such as the valve's
energy meter and the boiler's operating hours, keep their last value while the
device is unreachable, so long-term statistics have no gaps.

The eco controller is probed for its heating circuits when the entry is set
up. Each circuit it answers for becomes a device of its own, under the
controller.

## Known limitations

- **Belimo bus-fail action and malfunction bits.** These follow a valve on
  firmware 4.2. Belimo's V4.1 register description puts a bus-fail setpoint
  in % at register 109 instead. Check both against the valve if yours runs
  older firmware.
- **pelletstar error texts are German.** The error sensors show the text the
  boiler's display shows, whatever Home Assistant's language.
- **Belimo flow unit.** Flow is shown in the unit selected on the valve. The
  sensor stays unavailable until the valve has reported that unit.
- **eco hot water setpoint.** It reads the same register as the buffer
  setpoint. It is disabled by default until the right register is confirmed.
- **pelletstar modules.** The boiler's own buffer, hot water, solar and
  heating circuit modules are in the library but not offered here yet.
- **eco controllers that answer everything.** A controller that answers the
  registers of circuits it doesn't have shows all three circuits.

## Troubleshooting

Turn on debug logging for the integration and the library:

```yaml
logger:
  logs:
    custom_components.hydronic: debug
    modbus_connection: debug
```

The diagnostics download of an entry contains every register the integration
reads, undecoded. Attach it to an issue about a wrong value.

## Development

This repository follows
[integration_blueprint](https://github.com/ludeeus/integration_blueprint). Open
it in the dev container, then:

```bash
scripts/develop   # start Home Assistant with the integration loaded
scripts/lint      # format and lint
scripts/test      # run the tests
```

`scripts/test` needs `requirements_test.txt` installed. The device library is
vendored: change it in hydronic-modbus and bring it over with
`scripts/vendor ../hydronic-modbus`.
