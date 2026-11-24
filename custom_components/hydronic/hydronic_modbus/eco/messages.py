"""Alarms, warnings and information the controller reports.

Each module (a heating circuit, the storage tank, solar) reports three codes:
an alarm (Errorstate), a warning (unkritische Meldung) and an information
(Meldung). Each holds a single code, the last condition the controller found
in that cycle, not a bit mask; 0 means none. On top, registers 3 and 5 say
whether any alarm or warning is pending anywhere.

The texts follow ENERGIEFREUND's published Modbus parameter list, corrected
and completed where a controller on v5.00.34 reports otherwise: the list's
alarm codes for the heating circuits and for solar do not match what the
controller sends, and several codes are missing from it. Codes the list names
that a v5.00.34 controller does not use keep the list's text.
"Signalverwaltung" codes mean a signal of the controller's own signal
management (configurable inputs) is pending. Heating texts are used; a circuit
that cools swaps warnings 1 and 10.
"""

from __future__ import annotations

from typing import ClassVar

from modbus_connection.model import int32

from ..model import HydronicComponent

NO_MESSAGE_TEXT = "OK"
"""What a code of 0 reads as: nothing pending."""

CIRCUIT_ALARMS: dict[int, str] = {
    1: "Vorlauffühler defekt",
    2: "Außentemperatur nicht angeschlossen",
    3: "STB aktiv",
    4: "Taupunktwächter aktiv",
    5: "Alarm der Signalverwaltung",
    6: "Vorlauffühler sekundär defekt",
}
CIRCUIT_WARNINGS: dict[int, str] = {
    1: "Vorlauftemperatur zu hoch",
    2: "Anfahrentlastung aktiv",
    3: "Rücklauffühler nicht angeschlossen",
    4: "Frostschutz aktiv",
    5: "Überhitzungsschutz aktiv",
    6: "Raumbediengerät nicht angeschlossen",
    7: "Anzeigefühler nicht angeschlossen",
    8: "STB ausgelöst",  # in the list; the controller reports STB as alarm 3
    9: "Raumtemperaturfühler nicht angeschlossen",
    10: "Vorlauftemperatur zu niedrig",
    11: "Rücklauftemperaturüberwachung: Stoppzeit aktiv",
    12: "Meldung der Mischerregelung",
    14: "Meldung der Signalverwaltung",
    15: "Rücklauffühler sekundär nicht angeschlossen",
}
CIRCUIT_INFORMATION: dict[int, str] = {
    1: "Raumtemperatur erreicht",
    2: "Zeitfenster nicht aktiv",
    3: "Außentemperaturabschaltung aktiv",
    4: "Pooltemperatur erreicht",
    5: "Externe Freigabe nicht vorhanden",
    6: "Frostschutzüberwachung aktiv",
    7: "Warmwasservorrang aktiv",
    8: "Wettereinfluss aktiv",
}

BUFFER_ALARMS: dict[int, str] = {
    1: "Verbindungsfehler",
    2: "Fühler oben nicht angeschlossen",
    3: "Fühler unten nicht angeschlossen",
    4: "Fühler mitte nicht angeschlossen",
    5: "Fühlerfehler Zirkulation",
    6: "Außentemperatur nicht angeschlossen",
    7: "Speicherfühler 1 (oben) nicht angeschlossen",
    8: "Speicherfühler 2 (oben 2) nicht angeschlossen",
    9: "Speicherfühler 3 (mitte) nicht angeschlossen",
    10: "Speicherfühler 4 (unten) nicht angeschlossen",
    11: "Fühler Umgehung nicht angeschlossen",
    12: "Rücklauffühler nicht angeschlossen",
    13: "Frischwasserfühler nicht angeschlossen",
    14: "Alarm der Signalverwaltung",
}
BUFFER_WARNINGS: dict[int, str] = {
    1: "Anfahrentlastung aktiv",
    2: "Speichertemperatur zu gering",
    3: "Speichertemperatur zu hoch",
    4: "Überhitzungsschutz aktiv",
    5: "Anfahrentlastung Zirkulation aktiv",
    6: "Zirkulationstemperatur zu gering",
    7: "Legionellenschutz abgebrochen oder Meldung der Signalverwaltung",
}
BUFFER_INFORMATION: dict[int, str] = {
    1: "Speichertemperatur erreicht",
    2: "Zeitfenster nicht aktiv",
    3: "Zeitfenster E-Patrone nicht aktiv",
    6: "Meldung der Signalverwaltung",
}

SOLAR_ALARMS: dict[int, str] = {
    2: "Kollektorfühler nicht angeschlossen",
    3: "Speicherfühler 1 nicht angeschlossen",
    4: "Speicherfühler 2 nicht angeschlossen",
    5: "Vorlauffühler nicht angeschlossen",
    6: "Rücklauffühler nicht angeschlossen",
    7: "Speicherfühler 3 nicht angeschlossen",
    8: "Fühler Zone 1 nicht angeschlossen",
    9: "Alarm der Signalverwaltung",
}
SOLAR_WARNINGS: dict[int, str] = {
    1: "Maximale Kollektortemperatur erreicht",
    2: "Kollektor Kühlfunktion aktiv",
    3: "Kollektor Frostschutz aktiv",
    5: "Spreizung zu groß",
    6: "Meldung der Signalverwaltung",
}
SOLAR_INFORMATION: dict[int, str] = {
    1: "Meldung der Signalverwaltung",
}


def message_text(texts: dict[int, str], code: int | None) -> str | None:
    """The text for ``code``: "OK" for 0, "Code n" for one the table lacks."""
    if code is None:
        return None
    if code == 0:
        return NO_MESSAGE_TEXT
    return texts.get(code, f"Code {code}")


class _ModuleMessages(HydronicComponent):
    """A module's alarm, warning and information codes, with their texts."""

    ALARMS: ClassVar[dict[int, str]] = {}
    WARNINGS: ClassVar[dict[int, str]] = {}
    INFORMATION: ClassVar[dict[int, str]] = {}

    alarm: int | None
    warning: int | None
    information: int | None

    @property
    def alarm_text(self) -> str | None:
        """The pending alarm as text, "OK" if none."""
        return message_text(self.ALARMS, self.alarm)

    @property
    def warning_text(self) -> str | None:
        """The pending warning as text, "OK" if none."""
        return message_text(self.WARNINGS, self.warning)

    @property
    def information_text(self) -> str | None:
        """The pending information as text, "OK" if none."""
        return message_text(self.INFORMATION, self.information)


class CircuitMessages(_ModuleMessages):
    """A heating circuit's codes, offsets 30-35 of its block (``base_offset``)."""

    ALARMS = CIRCUIT_ALARMS
    WARNINGS = CIRCUIT_WARNINGS
    INFORMATION = CIRCUIT_INFORMATION

    alarm = int32(30)  # type: ignore[assignment]
    warning = int32(32)  # type: ignore[assignment]
    information = int32(34)  # type: ignore[assignment]


class BufferMessages(_ModuleMessages):
    """The storage tank's codes, registers 1125-1130."""

    ALARMS = BUFFER_ALARMS
    WARNINGS = BUFFER_WARNINGS
    INFORMATION = BUFFER_INFORMATION

    alarm = int32(1124)  # type: ignore[assignment]
    warning = int32(1126)  # type: ignore[assignment]
    information = int32(1128)  # type: ignore[assignment]


class SolarMessages(_ModuleMessages):
    """The solar circuit's codes, registers 8131-8136."""

    ALARMS = SOLAR_ALARMS
    WARNINGS = SOLAR_WARNINGS
    INFORMATION = SOLAR_INFORMATION

    alarm = int32(8130)  # type: ignore[assignment]
    warning = int32(8132)  # type: ignore[assignment]
    information = int32(8134)  # type: ignore[assignment]


class GeneralAlarms(HydronicComponent):
    """Whether any alarm or warning is pending, registers 3 and 5."""

    fault = int32(2)
    """General fault (Allgemeine Störung); non-zero while an alarm is pending."""
    uncritical = int32(4)
    """General uncritical message; non-zero while a warning is pending."""
