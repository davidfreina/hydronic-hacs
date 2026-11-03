"""The boiler's status code and its I/O bits, as enums and flags.

Names translate the boiler's own German display texts, kept alongside.
"""

from __future__ import annotations

from enum import IntEnum, IntFlag


class BoilerState(IntEnum):
    """The boiler's operating state (Kesselstatus)."""

    AFTER_RESET = 0  # Nach Reset
    HEATING_OFF = 1  # Heizung Aus
    READY = 2  # Bereit
    IGNITION_PREPARATION = 3  # Zündvorbereiten
    PRE_VENTILATION = 4  # Vorbelüften
    COLD_START = 5  # Kaltstart
    KINDLING = 6  # Anbrennphase
    RAMP_UP = 7  # Hochlaufphase
    MODULATING = 8  # Regelphase
    BURNOUT = 9  # Ausbrennphase
    CHIMNEY_SWEEP = 10  # Kaminkehrfunktion
    LAMBDA_CALIBRATION = 11  # Lambdakalibrierung
    SUCTION = 12  # Saugen
    BURNER_CLEANING = 13  # Brennerreinigung
    IGNITION = 14  # Zündphase
    RESTART = 15  # Neuanlauf
    REHEATING = 16  # Nachheizen
    WARM_START = 17  # Warmstart
    WAITING = 18  # Warten


class FaultStatus(IntEnum):
    """Whether an error, a warning or an information is pending (register 93)."""

    NONE = 0
    ERROR = 1  # Fehler aktiv
    WARNING = 2  # Warnung aktiv
    INFORMATION = 3  # Infomeldung aktiv


class OutputByte1(IntFlag):
    """Outputs, first byte."""

    PELLET_SUCTION = 0x02  # Pellets-Sauger / Pelletsrührer / Vorschubrost
    GRATE_CLEANING = 0x04  # Rostreinigung
    HEAT_EXCHANGER_CLEANING = 0x08  # WTR
    IGNITION_HEATER = 0x10  # Zündung Heizung
    IGNITION_FAN = 0x20  # Zündung Ventilator
    DISCHARGE_SCREW = 0x40  # Austragschnecke
    BURNBACK_FLAP_OPEN = 0x80  # RSE Auf


class OutputByte2(IntFlag):
    """Outputs, second byte."""

    HOPPER_SCREW = 0x01  # Behälterschnecke
    SOLENOID_VALVE = 0x02  # Magnetventil
    ASH_REMOVAL = 0x04  # Aschenaustragung
    RETURN_PUMP = 0x08  # Rücklaufpumpe
    RETURN_MIXER_OPEN = 0x10  # Rücklaufmischer Auf
    RETURN_MIXER_CLOSE = 0x20  # Rücklaufmischer Zu
    ALARM_OUTPUT = 0x80  # Alarmausgang; set while there is no alarm


class OutputByte3(IntFlag):
    """Outputs, third byte."""

    OVERTEMPERATURE_OUTPUT = 0x01  # TÜB Ausgang; set while safe
    OPERATING_SIGNAL = 0x02  # Betriebsmelder
    FEED_SCREW_RELEASE = 0x04  # Freigabe Einschubschnecke
    LAMBDA_HEATING = 0x08  # Lambdaheizung


class InputByte1(IntFlag):
    """Inputs, first byte."""

    SYSTEM_STOP = 0x01  # Anlage Halt
    OVERTEMPERATURE_INPUT = 0x02  # TÜB Eingang; set while safe
    BURNBACK_FLAP_OPENED = 0x04  # RSE offen
    BURNBACK_FLAP_CLOSED = 0x08  # RSE geschlossen
    DISCHARGE_MOTOR_PROTECTION = 0x10  # Motorschutz AS; set while healthy
    ASH_DOOR_CLOSED = 0x20  # Aschentür ZU
    DISCHARGE_LIMIT_SWITCH = 0x40  # Endschalter AS
    AUXILIARY_INPUT = 0x80  # Zusatzeingang


class InputByte2(IntFlag):
    """Inputs, second byte."""

    ASH_REMOVAL_MONITORING = 0x01  # Aschenaustragungsüberwachung
    HOPPER_EMPTY = 0x02  # Behälter leer
    GRATE_CLOSED = 0x04  # Rost geschlossen
    SUCTION_FLAP = 0x08  # Vacutransklappe / Int. Saugbehälter
    CENTRAL_ASH_REMOVAL = 0x10  # Störung zentrale Aschenaustragung; set while healthy
    SAFETY_TEMPERATURE_LIMITER = 0x20  # STB; set while safe
    # WTR-Überwachung / Störung E-Filter; set while healthy
    HEAT_EXCHANGER_MONITORING = 0x40
