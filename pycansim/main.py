"""
PyCanSim: Lightweight, Modern 2D CAN Bus Simulator.
Single-window Pygame application with Decoupled Publisher/Subscriber architecture over SocketCAN (vcan0).

Author: Experienced Automotive & Cybersecurity Engineer
"""

import sys
import os
import time
import random
import math
import logging
import pygame

# Ensure local pycansim package imports work smoothly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pycansim.core.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    FPS,
    MAX_SPEED_KMH,
    ACCEL_RATE,
    DECEL_RATE,
    COAST_RATE,
    IDLE_RPM,
    MAX_RPM,
    NORMAL_COOLANT_TEMP,
)
from pycansim.core.state import VehicleState
from pycansim.can_bus.receiver import create_can_bus, CanReceiver
from pycansim.can_bus.sender import CanSender
from pycansim.can_bus.monitor import TrafficMonitor
from pycansim.ui.road_renderer import RoadRenderer
from pycansim.ui.car_renderer import CarRenderer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("pycansim.main")


def main():
    """Main application launcher."""
    print("=" * 60)
    print("        🚗 PyCanSim - 2D CAN Bus Simulator 🚗        ")
    print("=" * 60)
    print("Single Window Decoupled Architecture Initializing...\n")

    # 1. Initialize Pygame
    pygame.init()
    screen = pygame.display.set_mode(
        (WINDOW_WIDTH, WINDOW_HEIGHT),
        pygame.RESIZABLE,
    )
    pygame.display.set_caption("PyCanSim - 2D CAN Bus Simulator (vcan0)")
    try:
        pygame.display.set_window_minimum_size(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
    except Exception:
        pass
    clock = pygame.time.Clock()

    # 2. Initialize Shared Vehicle State
    state = VehicleState()

    # 3. Setup SocketCAN Bus Connection
    bus, active_iface = create_can_bus(channel="vcan0", bustype="socketcan")
    if bus is not None:
        state.can_connected = True
        state.can_interface_name = active_iface
    else:
        state.can_connected = False
        state.can_interface_name = "Disconnected"

    # 4. Initialize Traffic Monitor (frame log + injection IDS + recorder)
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    monitor = TrafficMonitor(channel=active_iface, log_dir=log_dir)

    # 5. Initialize Sender and Receiver CAN Threads
    sender = CanSender(bus, state, monitor=monitor)
    receiver = CanReceiver(bus, state, monitor=monitor)

    sender.start()
    receiver.start()

    # 6. Initialize Renderers
    road_renderer = RoadRenderer(WINDOW_WIDTH, WINDOW_HEIGHT)
    car_renderer = CarRenderer()

    logger.info("Application loop starting...")
    running = True

    try:
        while running:
            dt = clock.tick(FPS) / 1000.0  # Delta time in seconds

            # --- KEYBOARD EVENT HANDLING (Toggle Controls) ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.VIDEORESIZE:
                    new_w = max(MIN_WINDOW_WIDTH, event.w)
                    new_h = max(MIN_WINDOW_HEIGHT, event.h)
                    screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
                    road_renderer.resize(new_w, new_h)
                    car_renderer.resize(new_w, new_h)

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

                    # Lighting & Signal Toggles (0x290)
                    elif event.key == pygame.K_a:
                        state.toggle_left_signal()
                        sender.send_lights(state.turn_signal, state.headlights)

                    elif event.key == pygame.K_d:
                        state.toggle_right_signal()
                        sender.send_lights(state.turn_signal, state.headlights)

                    elif event.key == pygame.K_f:
                        state.toggle_hazard_lights()
                        sender.send_lights(state.turn_signal, state.headlights)

                    elif event.key == pygame.K_l:
                        state.toggle_headlights()
                        sender.send_lights(state.turn_signal, state.headlights)

                    # CAN traffic recording toggle (candump -L format)
                    elif event.key == pygame.K_r:
                        path = monitor.toggle_recording()
                        if monitor.recording:
                            logger.info(f"Recording CAN traffic -> {path}")
                        else:
                            logger.info(f"Recording saved -> {path}")

                    # Door Toggles (0x280)
                    elif event.key == pygame.K_1:
                        state.toggle_door_fl()
                        sender.send_doors(state.get_doors_bitmask())

                    elif event.key == pygame.K_2:
                        state.toggle_door_fr()
                        sender.send_doors(state.get_doors_bitmask())

                    elif event.key == pygame.K_3:
                        state.toggle_door_rl()
                        sender.send_doors(state.get_doors_bitmask())

                    elif event.key == pygame.K_4:
                        state.toggle_door_rr()
                        sender.send_doors(state.get_doors_bitmask())

            # --- CONTINUOUS HELD KEYS HANDLING (Throttle W & Brake S Physics) ---
            keys = pygame.key.get_pressed()
            is_w_pressed = keys[pygame.K_w]
            is_s_pressed = keys[pygame.K_s]

            current_speed = state.speed_kmh
            brake_active = False

            if is_s_pressed:
                # S key: Apply brakes
                brake_active = True
                current_speed = max(0.0, current_speed - DECEL_RATE * dt)
            elif is_w_pressed:
                # W key: Accelerate up to 160 km/h limit
                current_speed = min(MAX_SPEED_KMH, current_speed + ACCEL_RATE * dt)
            else:
                # Neither W nor S pressed: Coast down gradually
                if current_speed > 0.0:
                    current_speed = max(0.0, current_speed - COAST_RATE * dt)

            # Update vehicle speed and brake status
            state.speed_kmh = current_speed
            state.brake_pressed = brake_active

            # --- EXTENDED ECU PHYSICS SIMULATION ---

            # Throttle position: reflects W key pressure, smoothed towards target
            throttle_target = 85.0 if is_w_pressed else (5.0 if current_speed > 1.0 else 0.0)
            if is_s_pressed:
                throttle_target = 0.0
            state.throttle_pos += (throttle_target - state.throttle_pos) * min(1.0, dt * 6.0)

            # Engine RPM: correlated with speed + throttle, with idle floor
            # Approximate gear shift effect: rpm oscillates around speed-based curve
            speed_ratio = current_speed / MAX_SPEED_KMH
            rpm_target = IDLE_RPM + (MAX_RPM - IDLE_RPM) * (
                (speed_ratio ** 0.65) * 0.78 + (state.throttle_pos / 100.0) * 0.22
            )
            if current_speed < 1.0 and not is_w_pressed:
                rpm_target = IDLE_RPM   # idle when stopped
            state.engine_rpm += (rpm_target - state.engine_rpm) * min(1.0, dt * 3.5)

            # Coolant temperature: warms up slowly, stabilises near 90°C at speed
            warm_target = NORMAL_COOLANT_TEMP + (current_speed / MAX_SPEED_KMH) * 8.0
            heat_rate = 4.0 if is_w_pressed else 0.8   # heats faster under load
            state.coolant_temp += (warm_target - state.coolant_temp) * min(1.0, dt * heat_rate * 0.02)

            # Fuel level: slowly decreases proportional to throttle & speed
            fuel_burn = (0.0003 + state.throttle_pos * 0.000006) * dt   # %/sec
            state.fuel_level = max(0.0, state.fuel_level - fuel_burn)

            # Steering angle: oscillates mildly to mimic lane corrections
            # Amplitude grows very slightly with speed for realism
            steer_freq = 0.18 + current_speed * 0.0008
            steer_amp  = 2.5  + current_speed * 0.018
            # Phase accumulator for a slow, organic sine drift
            if not hasattr(state, '_steer_phase'):
                state._steer_phase = 0.0
            state._steer_phase += steer_freq * dt
            steer_base = math.sin(state._steer_phase) * steer_amp
            # Small random micro-corrections
            steer_noise = random.gauss(0, 0.15 + current_speed * 0.005)
            state.steering_angle = steer_base + steer_noise

            # Battery voltage: sags slightly under high RPM load, ripple always present
            load_sag = (state.engine_rpm / MAX_RPM) * 0.4
            bat_target = 14.1 - load_sag
            state.battery_voltage += (bat_target - state.battery_voltage) * min(1.0, dt * 2.0)

            # Immediately push physics update frame to CAN Bus (0x110)
            sender.send_speed_brake(state.speed_kmh, state.brake_pressed)

            # --- RENDERING PIPELINE ---
            sw, sh = screen.get_size()
            if sw != road_renderer.width or sh != road_renderer.height:
                road_renderer.resize(sw, sh)
                car_renderer.resize(sw, sh)

            # 1. Draw animated road surface
            road_renderer.update_and_render(screen, state.speed_kmh, dt)

            # 2. Draw car vector graphics & HUD
            car_renderer.render(screen, state, monitor)

            # 3. Swap buffers
            pygame.display.flip()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        print("\n[+] Shutting down PyCanSim...")
        sender.stop()
        receiver.stop()
        monitor.close()
        if bus:
            try:
                bus.shutdown()
            except Exception:
                pass
        pygame.quit()
        print("[+] Cleanup complete. Bye!")


if __name__ == "__main__":
    main()
