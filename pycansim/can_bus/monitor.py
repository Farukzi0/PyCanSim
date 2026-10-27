"""
CAN Traffic Monitor for PyCanSim.
Keeps a live log of external frames, flags spoofed frames (IDS) and records
all traffic in candump -L format so it can be replayed with canplayer.

Detection rule: SocketCAN does not loop our own frames back to our socket,
so any frame we *receive* on an ID we broadcast ourselves was injected by
another node — e.g. `cansend vcan0 110#2EE000`.
"""

import os
import time
import threading
import logging
from collections import deque

from ..core.constants import (
    BROADCAST_IDS,
    CAN_ID_UDS_FUNCTIONAL,
    CAN_ID_UDS_REQUEST,
    CAN_ID_UDS_RESPONSE,
    FRAME_LOG_SIZE,
    IDS_ALERT_WINDOW,
)

logger = logging.getLogger("pycansim.monitor")

TAG_SPOOF = "SPOOF"
TAG_UDS = "UDS"
TAG_UNKNOWN = "?"


class TrafficMonitor:
    """Thread-safe frame log, injection detector and candump-style recorder."""

    def __init__(self, channel: str, log_dir: str):
        self.channel = channel
        self.log_dir = log_dir
        self._lock = threading.Lock()
        self._frames = deque(maxlen=FRAME_LOG_SIZE)
        self._spoof_count = 0
        self._spoofed_ids = {}          # arb_id -> last seen time
        self._rec_file = None
        self._rec_path = None
        self._rec_count = 0

    # --- RX / TX HOOKS ---

    def on_rx(self, arb_id: int, data: bytes):
        """Called by the receiver for every frame from another node."""
        now = time.time()
        if arb_id in BROADCAST_IDS:
            tag = TAG_SPOOF
        elif arb_id in (CAN_ID_UDS_FUNCTIONAL, CAN_ID_UDS_REQUEST):
            tag = TAG_UDS
        else:
            tag = TAG_UNKNOWN

        with self._lock:
            self._frames.append((now, "RX", arb_id, bytes(data), tag))
            if tag == TAG_SPOOF:
                self._spoof_count += 1
                self._spoofed_ids[arb_id] = now
            self._record(now, arb_id, data)

    def on_tx(self, arb_id: int, data: bytes):
        """Called by the sender for every frame we transmit."""
        with self._lock:
            if arb_id == CAN_ID_UDS_RESPONSE:
                self._frames.append((time.time(), "TX", arb_id, bytes(data), TAG_UDS))
            self._record(time.time(), arb_id, data)

    # --- IDS STATUS ---

    @property
    def spoof_count(self) -> int:
        with self._lock:
            return self._spoof_count

    def active_alerts(self) -> list[int]:
        """IDs that received spoofed frames within the alert window."""
        now = time.time()
        with self._lock:
            return sorted(i for i, t in self._spoofed_ids.items() if now - t < IDS_ALERT_WINDOW)

    def recent_frames(self) -> list[tuple]:
        with self._lock:
            return list(self._frames)

    # --- RECORDER (candump -L format) ---

    @property
    def recording(self) -> bool:
        with self._lock:
            return self._rec_file is not None

    @property
    def record_info(self) -> tuple[str | None, int]:
        with self._lock:
            return self._rec_path, self._rec_count

    def toggle_recording(self) -> str | None:
        """Start or stop recording. Returns the log path when stopping/starting."""
        with self._lock:
            if self._rec_file is not None:
                self._rec_file.close()
                self._rec_file = None
                logger.info(f"Recording stopped: {self._rec_path} ({self._rec_count} frames)")
                return self._rec_path

            os.makedirs(self.log_dir, exist_ok=True)
            name = time.strftime("candump-%Y-%m-%d_%H%M%S.log")
            self._rec_path = os.path.join(self.log_dir, name)
            self._rec_file = open(self._rec_path, "w")
            self._rec_count = 0
            logger.info(f"Recording to {self._rec_path}")
            return self._rec_path

    def close(self):
        with self._lock:
            if self._rec_file is not None:
                self._rec_file.close()
                self._rec_file = None

    def _record(self, ts: float, arb_id: int, data: bytes):
        # Caller holds self._lock
        if self._rec_file is None:
            return
        self._rec_file.write(f"({ts:.6f}) {self.channel} {arb_id:03X}#{bytes(data).hex().upper()}\n")
        self._rec_count += 1
