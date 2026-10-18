"""
CAN Bus Sender for PyCanSim.
Transmits CAN frames to SocketCAN (vcan0) based on keyboard inputs and periodic timer loops.

Supported CAN IDs:
  0x0C8 - Engine ECU  : RPM (uint16 BE) + Throttle position (uint8, 0-200 = 0-100%)
  0x110 - Speed/Brake : Speed (uint16 BE, *100) + Brake flag (uint8)
  0x280 - Doors       : Door bitmask (uint8)
  0x290 - Lights      : Turn signal (uint8) + Headlights (uint8)
  0x2B0 - Chassis     : Steering angle (int16 BE, 0.1 deg/LSB) + Battery voltage (uint8, 10ths of V)
  0x3B0 - Body ECU    : Coolant temp (uint8, offset -40°C) + Fuel level (uint8, 0-200 = 0-100%)
"""

import random
import struct
import time
import threading
import logging
import can

from ..core.constants import (
    CAN_ID_SPEED_BRAKE,
    CAN_ID_DOORS,
    CAN_ID_LIGHTS,
    CAN_ID_ENGINE,
    CAN_ID_TEMP_FUEL,
    CAN_ID_STEER_BAT,
)
from ..core.state import VehicleState

logger = logging.getLogger("pycansim.sender")


class CanSender:
    """
    Handles CAN message encoding and transmission over python-can bus interface.
    Runs periodic transmission thread for regular ECU telemetry broadcasts.
    All physical sensor values carry small, realistic noise to mimic real ECU behaviour.
    """

    def __init__(self, bus: can.BusABC, state: VehicleState):
        self.bus = bus
        self.state = state
        self.running = False
        self._thread = None

    def start(self):
        """Start periodic CAN transmission thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._periodic_loop, name="CanSenderThread", daemon=True)
        self._thread.start()
        logger.info("CanSender periodic thread started.")

    def stop(self):
        """Stop periodic CAN transmission thread."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("CanSender thread stopped.")

    # --- INDIVIDUAL FRAME SENSORS / TRANSMITTERS ---

    def send_speed_brake(self, speed_kmh: float, brake_pressed: bool):
        """
        Send CAN ID 0x110 (Speed & Brake)
        Byte 0-1: Big-endian uint16 (speed * 100), ±0.2 km/h ADC noise
        Byte 2: Brake (0x01: Pressed, 0x00: Free)
        """
        if not self.bus:
            return

        # Slight ADC noise on speed measurement (±0.15 km/h)
        noisy_speed = speed_kmh + random.gauss(0, 0.15) if speed_kmh > 0.5 else 0.0
        raw_speed = int(round(clamp(noisy_speed, 0.0, 160.0) * 100.0))
        brake_val = 0x01 if brake_pressed else 0x00

        data = struct.pack(">HB", raw_speed, brake_val)
        self._send_frame(CAN_ID_SPEED_BRAKE, data)

    def send_engine(self, rpm: float, throttle_pos: float):
        """
        Send CAN ID 0x0C8 (Engine ECU - highest frequency, 10ms)
        Byte 0-1: Big-endian uint16 RPM
        Byte 2:   Throttle position 0-200 maps to 0-100%
        """
        if not self.bus:
            return

        # Engine RPM has realistic ±15 RPM jitter at idle/cruise
        noise_scale = 25.0 if throttle_pos > 5 else 8.0
        noisy_rpm = rpm + random.gauss(0, noise_scale)
        raw_rpm = int(clamp(noisy_rpm, 0.0, 7000.0))

        # Throttle has ±0.3% position noise
        noisy_thr = throttle_pos + random.gauss(0, 0.3)
        raw_thr = int(clamp(noisy_thr * 2.0, 0, 200))   # 0-200 = 0.0-100.0%

        data = struct.pack(">HB", raw_rpm, raw_thr)
        self._send_frame(CAN_ID_ENGINE, data)

    def send_temp_fuel(self, coolant_temp: float, fuel_level: float):
        """
        Send CAN ID 0x3B0 (Body ECU - 200ms)
        Byte 0: Coolant temp (uint8, offset -40°C, so 0x00 = -40°C, 0x82 = 90°C)
        Byte 1: Fuel level (0-200 maps to 0-100%)
        """
        if not self.bus:
            return

        # Coolant sensor ±0.5°C noise
        noisy_temp = coolant_temp + random.gauss(0, 0.5)
        raw_temp = int(clamp(noisy_temp + 40.0, 0, 255))

        # Fuel level sensor ±0.1% noise
        noisy_fuel = fuel_level + random.gauss(0, 0.1)
        raw_fuel = int(clamp(noisy_fuel * 2.0, 0, 200))

        data = bytes([raw_temp, raw_fuel])
        self._send_frame(CAN_ID_TEMP_FUEL, data)

    def send_steer_bat(self, steering_angle: float, battery_voltage: float):
        """
        Send CAN ID 0x2B0 (Chassis ECU - 50ms)
        Byte 0-1: Steering angle int16 BE (0.1 deg/LSB, signed)
        Byte 2:   Battery voltage uint8 (0.1 V/LSB, offset 0 V, so 124 = 12.4V)
        """
        if not self.bus:
            return

        # Steering angle ±0.2° sensor noise
        noisy_steer = steering_angle + random.gauss(0, 0.2)
        raw_steer = int(clamp(noisy_steer * 10.0, -32768, 32767))

        # Battery voltage ±0.03 V ripple noise
        noisy_bat = battery_voltage + random.gauss(0, 0.03)
        raw_bat = int(clamp(noisy_bat * 10.0, 90, 150))

        data = struct.pack(">hB", raw_steer, raw_bat)
        self._send_frame(CAN_ID_STEER_BAT, data)

    def send_doors(self, bitmask: int):
        """
        Send CAN ID 0x280 (Doors)
        Byte 0: Bitmask (Bit 0: FL, Bit 1: FR, Bit 2: RL, Bit 3: RR)
        """
        if not self.bus:
            return
        data = bytes([bitmask & 0x0F])
        self._send_frame(CAN_ID_DOORS, data)

    def send_lights(self, turn_signal: int, headlights: bool):
        """
        Send CAN ID 0x290 (Lighting & Warnings)
        Byte 0: Signal (0x00: Off, 0x01: Left, 0x02: Right, 0x03: Hazard)
        Byte 1: Headlights (0x01: On, 0x00: Off)
        """
        if not self.bus:
            return
        headlight_val = 0x01 if headlights else 0x00
        data = bytes([turn_signal & 0x03, headlight_val])
        self._send_frame(CAN_ID_LIGHTS, data)

    # --- INTERNAL HELPERS ---

    def _send_frame(self, arb_id: int, data: bytes):
        """Low-level CAN frame transmit with error logging."""
        msg = can.Message(arbitration_id=arb_id, data=data, is_extended_id=False)
        try:
            self.bus.send(msg)
        except Exception as e:
            logger.error(f"Failed to send 0x{arb_id:03X}: {e}")

    # --- PERIODIC TRANSMISSION LOOP ---

    def _periodic_loop(self):
        """
        Broadcast periodic frames at ECU intervals:
        - 0x0C8 Engine ECU      (10 ms)
        - 0x110 Speed / Brake   (20 ms)
        - 0x2B0 Steering / Bat  (50 ms)
        - 0x290 Lights          (50 ms)
        - 0x280 Doors           (100 ms)
        - 0x3B0 Temp / Fuel     (200 ms)
        """
        last_0C8 = 0.0
        last_110 = 0.0
        last_2B0 = 0.0
        last_290 = 0.0
        last_280 = 0.0
        last_3B0 = 0.0

        while self.running:
            now = time.time()

            # 10 ms cycle – Engine ECU (highest priority / fastest)
            if now - last_0C8 >= 0.010:
                self.send_engine(self.state.engine_rpm, self.state.throttle_pos)
                last_0C8 = now

            # 20 ms cycle – Speed & Brake
            if now - last_110 >= 0.020:
                self.send_speed_brake(self.state.speed_kmh, self.state.brake_pressed)
                last_110 = now

            # 50 ms cycle – Steering angle & Battery voltage
            if now - last_2B0 >= 0.050:
                self.send_steer_bat(self.state.steering_angle, self.state.battery_voltage)
                last_2B0 = now

            # 50 ms cycle – Lights & Signals
            if now - last_290 >= 0.050:
                self.send_lights(self.state.turn_signal, self.state.headlights)
                last_290 = now

            # 100 ms cycle – Doors
            if now - last_280 >= 0.100:
                self.send_doors(self.state.get_doors_bitmask())
                last_280 = now

            # 200 ms cycle – Coolant temp & Fuel level
            if now - last_3B0 >= 0.200:
                self.send_temp_fuel(self.state.coolant_temp, self.state.fuel_level)
                last_3B0 = now

            # Minimal sleep to keep CPU usage low
            time.sleep(0.004)


def clamp(val, min_val, max_val):
    return max(min_val, min(max_val, val))
