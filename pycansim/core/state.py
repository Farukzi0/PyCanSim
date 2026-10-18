"""
Thread-safe VehicleState class for PyCanSim.
"""

import threading
from .constants import (
    MAX_SPEED_KMH,
    SIGNAL_OFF,
    SIGNAL_LEFT,
    SIGNAL_RIGHT,
    SIGNAL_HAZARD,
    DOOR_FL_BIT,
    DOOR_FR_BIT,
    DOOR_RL_BIT,
    DOOR_RR_BIT,
    IDLE_RPM,
    MAX_RPM,
    NORMAL_COOLANT_TEMP,
)


class VehicleState:
    """
    Stores and manages all real-time vehicle parameters in a thread-safe manner.
    Used by CAN Receiver, CAN Sender, and Pygame UI Renderer.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Vehicle Telemetry & Controls
        self._speed_kmh = 0.0
        self._brake_pressed = False

        # Extended ECU Sensors (always broadcast)
        self._engine_rpm = IDLE_RPM           # RPM
        self._throttle_pos = 0.0              # 0.0 - 100.0 %
        self._coolant_temp = 20.0             # °C (warms up over time)
        self._fuel_level = 78.0              # % (slowly decreases)
        self._steering_angle = 0.0           # degrees, -540 .. +540
        self._battery_voltage = 12.4         # Volts

        # Door States
        self._door_fl = False
        self._door_fr = False
        self._door_rl = False
        self._door_rr = False

        # Lighting & Signals
        self._turn_signal = SIGNAL_OFF  # 0x00=Off, 0x01=Left, 0x02=Right, 0x03=Hazard
        self._headlights = False

        # System / CAN Status
        self._can_connected = False
        self._can_interface_name = "vcan0"

    # --- SPEED & BRAKE ---
    @property
    def speed_kmh(self) -> float:
        with self._lock:
            return self._speed_kmh

    @speed_kmh.setter
    def speed_kmh(self, val: float):
        with self._lock:
            self._speed_kmh = max(0.0, min(MAX_SPEED_KMH, float(val)))

    @property
    def brake_pressed(self) -> bool:
        with self._lock:
            return self._brake_pressed

    @brake_pressed.setter
    def brake_pressed(self, val: bool):
        with self._lock:
            self._brake_pressed = bool(val)

    # --- DOORS ---
    @property
    def door_fl(self) -> bool:
        with self._lock:
            return self._door_fl

    @door_fl.setter
    def door_fl(self, val: bool):
        with self._lock:
            self._door_fl = bool(val)

    @property
    def door_fr(self) -> bool:
        with self._lock:
            return self._door_fr

    @door_fr.setter
    def door_fr(self, val: bool):
        with self._lock:
            self._door_fr = bool(val)

    @property
    def door_rl(self) -> bool:
        with self._lock:
            return self._door_rl

    @door_rl.setter
    def door_rl(self, val: bool):
        with self._lock:
            self._door_rl = bool(val)

    @property
    def door_rr(self) -> bool:
        with self._lock:
            return self._door_rr

    @door_rr.setter
    def door_rr(self, val: bool):
        with self._lock:
            self._door_rr = bool(val)

    def get_doors_bitmask(self) -> int:
        """Calculate CAN Byte 0 bitmask for 0x280 frame."""
        with self._lock:
            mask = 0
            if self._door_fl:
                mask |= DOOR_FL_BIT
            if self._door_fr:
                mask |= DOOR_FR_BIT
            if self._door_rl:
                mask |= DOOR_RL_BIT
            if self._door_rr:
                mask |= DOOR_RR_BIT
            return mask

    def set_doors_from_bitmask(self, mask: int):
        """Update door states from CAN Byte 0 bitmask of 0x280 frame."""
        with self._lock:
            self._door_fl = bool(mask & DOOR_FL_BIT)
            self._door_fr = bool(mask & DOOR_FR_BIT)
            self._door_rl = bool(mask & DOOR_RL_BIT)
            self._door_rr = bool(mask & DOOR_RR_BIT)

    # --- LIGHTING & SIGNALS ---
    @property
    def turn_signal(self) -> int:
        with self._lock:
            return self._turn_signal

    @turn_signal.setter
    def turn_signal(self, mode: int):
        with self._lock:
            if mode in (SIGNAL_OFF, SIGNAL_LEFT, SIGNAL_RIGHT, SIGNAL_HAZARD):
                self._turn_signal = mode

    @property
    def headlights(self) -> bool:
        with self._lock:
            return self._headlights

    @headlights.setter
    def headlights(self, val: bool):
        with self._lock:
            self._headlights = bool(val)

    # --- TOGGLE HELPERS ---
    def toggle_door_fl(self):
        with self._lock:
            self._door_fl = not self._door_fl

    def toggle_door_fr(self):
        with self._lock:
            self._door_fr = not self._door_fr

    def toggle_door_rl(self):
        with self._lock:
            self._door_rl = not self._door_rl

    def toggle_door_rr(self):
        with self._lock:
            self._door_rr = not self._door_rr

    def toggle_left_signal(self):
        with self._lock:
            if self._turn_signal == SIGNAL_LEFT:
                self._turn_signal = SIGNAL_OFF
            else:
                self._turn_signal = SIGNAL_LEFT

    def toggle_right_signal(self):
        with self._lock:
            if self._turn_signal == SIGNAL_RIGHT:
                self._turn_signal = SIGNAL_OFF
            else:
                self._turn_signal = SIGNAL_RIGHT

    def toggle_hazard_lights(self):
        with self._lock:
            if self._turn_signal == SIGNAL_HAZARD:
                self._turn_signal = SIGNAL_OFF
            else:
                self._turn_signal = SIGNAL_HAZARD

    def toggle_headlights(self):
        with self._lock:
            self._headlights = not self._headlights

    # --- EXTENDED ECU SENSORS ---
    @property
    def engine_rpm(self) -> float:
        with self._lock:
            return self._engine_rpm

    @engine_rpm.setter
    def engine_rpm(self, val: float):
        with self._lock:
            self._engine_rpm = max(0.0, min(MAX_RPM, float(val)))

    @property
    def throttle_pos(self) -> float:
        with self._lock:
            return self._throttle_pos

    @throttle_pos.setter
    def throttle_pos(self, val: float):
        with self._lock:
            self._throttle_pos = max(0.0, min(100.0, float(val)))

    @property
    def coolant_temp(self) -> float:
        with self._lock:
            return self._coolant_temp

    @coolant_temp.setter
    def coolant_temp(self, val: float):
        with self._lock:
            self._coolant_temp = max(-40.0, min(130.0, float(val)))

    @property
    def fuel_level(self) -> float:
        with self._lock:
            return self._fuel_level

    @fuel_level.setter
    def fuel_level(self, val: float):
        with self._lock:
            self._fuel_level = max(0.0, min(100.0, float(val)))

    @property
    def steering_angle(self) -> float:
        with self._lock:
            return self._steering_angle

    @steering_angle.setter
    def steering_angle(self, val: float):
        with self._lock:
            self._steering_angle = max(-540.0, min(540.0, float(val)))

    @property
    def battery_voltage(self) -> float:
        with self._lock:
            return self._battery_voltage

    @battery_voltage.setter
    def battery_voltage(self, val: float):
        with self._lock:
            self._battery_voltage = max(9.0, min(15.0, float(val)))

    # --- CAN STATUS ---
    @property
    def can_connected(self) -> bool:
        with self._lock:
            return self._can_connected

    @can_connected.setter
    def can_connected(self, val: bool):
        with self._lock:
            self._can_connected = bool(val)

    @property
    def can_interface_name(self) -> str:
        with self._lock:
            return self._can_interface_name

    @can_interface_name.setter
    def can_interface_name(self, name: str):
        with self._lock:
            self._can_interface_name = str(name)
