"""
CAN Bus Receiver for PyCanSim.
Listens to SocketCAN (vcan0) in a daemon thread, parses incoming CAN frames,
and updates the shared VehicleState in real-time.

Supported CAN IDs:
  0x0C8 - Engine ECU  : RPM (uint16 BE) + Throttle position (uint8)
  0x110 - Speed/Brake : Speed (uint16 BE, *100) + Brake flag (uint8)
  0x280 - Doors       : Door bitmask (uint8)
  0x290 - Lights      : Turn signal (uint8) + Headlights (uint8)
  0x2B0 - Chassis     : Steering angle (int16 BE) + Battery voltage (uint8)
  0x3B0 - Body ECU    : Coolant temp (uint8, -40 offset) + Fuel level (uint8)
"""

import struct
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

logger = logging.getLogger("pycansim.receiver")


def create_can_bus(channel: str = "vcan0", bustype: str = "socketcan") -> tuple[can.BusABC | None, str]:
    """
    Attempt to connect to SocketCAN bus (vcan0).
    If socketcan fails (e.g. vcan0 interface down or missing), attempts virtual fallback.
    Returns (bus, active_interface_name).
    """
    # 1. Try primary channel (SocketCAN vcan0)
    try:
        bus = can.interface.Bus(channel=channel, bustype=bustype)
        logger.info(f"Successfully connected to CAN interface '{channel}' ({bustype}).")
        return bus, channel
    except Exception as e:
        logger.warning(f"Could not open '{channel}' with bustype '{bustype}': {e}")
        print("\n" + "=" * 65)
        print(f"[!] SOCKETCAN ERROR: Could not connect to '{channel}'!")
        print("To setup virtual CAN interface on Linux, run:")
        print("    sudo modprobe vcan")
        print(f"    sudo ip link add dev {channel} type vcan")
        print(f"    sudo ip link set up {channel}")
        print("=" * 65)

    # 2. Virtual CAN Fallback for testing without root / vcan setup
    try:
        fallback_channel = "virtual_vcan"
        bus = can.interface.Bus(channel=fallback_channel, bustype="virtual")
        logger.info(f"Fallback: Connected to virtual CAN interface '{fallback_channel}'.")
        print(f"[+] Fallback mode active: Running on virtual bus '{fallback_channel}'.\n")
        return bus, f"virtual ({channel} offline)"
    except Exception as e:
        logger.error(f"Failed to initialize virtual CAN bus: {e}")
        return None, "Disconnected"


class CanReceiver:
    """
    Threaded CAN Receiver that polls the CAN bus and updates VehicleState.
    """

    def __init__(self, bus: can.BusABC, state: VehicleState, monitor=None):
        self.bus = bus
        self.state = state
        self.monitor = monitor
        self.running = False
        self._thread = None

    def start(self):
        """Start CAN listening daemon thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, name="CanReceiverThread", daemon=True)
        self._thread.start()
        logger.info("CanReceiver thread started.")

    def stop(self):
        """Stop CAN listening daemon thread."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("CanReceiver thread stopped.")

    def _listen_loop(self):
        """Main listening loop parsing CAN packets."""
        while self.running and self.bus:
            try:
                msg = self.bus.recv(timeout=0.1)
                if msg is None:
                    continue
                # SocketCAN does not echo our own frames back to us, so any
                # frame arriving here came from another node (cansend, canplayer…).
                if self.monitor is not None:
                    self.monitor.on_rx(msg.arbitration_id, msg.data)
                self._parse_message(msg)
            except Exception as e:
                if self.running:
                    logger.error(f"Error reading CAN message: {e}")

    def _parse_message(self, msg: can.Message):
        """
        Parse received frame according to PyCanSim CAN protocol:
        - 0x0C8: Engine ECU (RPM & Throttle)
        - 0x110: Speed & Brake
        - 0x280: Doors
        - 0x290: Lighting & Signals
        - 0x2B0: Steering angle & Battery voltage
        - 0x3B0: Coolant temp & Fuel level
        """
        data = msg.data
        dlc = len(data)

        # 0x0C8 Engine ECU (RPM + Throttle)
        if msg.arbitration_id == CAN_ID_ENGINE:
            if dlc >= 3:
                raw_rpm, raw_thr = struct.unpack(">HB", data[:3])
                self.state.engine_rpm = float(raw_rpm)
                self.state.throttle_pos = raw_thr / 2.0   # 0-200 -> 0-100%
            elif dlc >= 2:
                (raw_rpm,) = struct.unpack(">H", data[:2])
                self.state.engine_rpm = float(raw_rpm)

        # 0x110 (Speed & Brake)
        elif msg.arbitration_id == CAN_ID_SPEED_BRAKE:
            if dlc >= 3:
                raw_speed, brake_val = struct.unpack(">HB", data[:3])
                self.state.speed_kmh = raw_speed / 100.0
                self.state.brake_pressed = (brake_val == 0x01)
            elif dlc >= 2:
                (raw_speed,) = struct.unpack(">H", data[:2])
                self.state.speed_kmh = raw_speed / 100.0

        # 0x280 (Doors Bitmask)
        elif msg.arbitration_id == CAN_ID_DOORS:
            if dlc >= 1:
                self.state.set_doors_from_bitmask(data[0])

        # 0x290 (Lights & Signals)
        elif msg.arbitration_id == CAN_ID_LIGHTS:
            if dlc >= 1:
                self.state.turn_signal = data[0]
            if dlc >= 2:
                self.state.headlights = (data[1] == 0x01)

        # 0x2B0 (Steering angle + Battery voltage)
        elif msg.arbitration_id == CAN_ID_STEER_BAT:
            if dlc >= 3:
                raw_steer, raw_bat = struct.unpack(">hB", data[:3])
                self.state.steering_angle = raw_steer / 10.0   # 0.1 deg/LSB
                self.state.battery_voltage = raw_bat / 10.0    # 0.1 V/LSB

        # 0x3B0 (Coolant temp + Fuel level)
        elif msg.arbitration_id == CAN_ID_TEMP_FUEL:
            if dlc >= 1:
                self.state.coolant_temp = float(data[0]) - 40.0  # offset -40°C
            if dlc >= 2:
                self.state.fuel_level = data[1] / 2.0            # 0-200 -> 0-100%
