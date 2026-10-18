"""
Car and HUD Renderer for PyCanSim.
Smooth top-down vehicle, lighting, and a live CAN instrument cluster.
"""

import math
import pygame
from ..core.constants import (
    SIGNAL_OFF,
    SIGNAL_LEFT,
    SIGNAL_RIGHT,
    SIGNAL_HAZARD,
    MAX_SPEED_KMH,
)
from ..core.state import VehicleState


class CarRenderer:
    """Draws a rounded vehicle silhouette plus a glass-style HUD."""

    C_TEXT_MAIN = (244, 246, 250)
    C_TEXT_MUTED = (148, 158, 172)
    C_GLASS = (16, 20, 28, 210)
    C_GLASS_LINE = (70, 82, 98, 160)
    C_BODY = (46, 52, 62)
    C_BODY_HI = (78, 88, 102)
    C_BODY_LO = (28, 32, 40)
    C_OUTLINE = (168, 180, 196)
    C_GLASS_ROOF = (18, 28, 40)
    C_TIRE = (18, 18, 22)
    C_RIM = (92, 100, 112)
    C_SIGNAL_ON = (255, 168, 36)
    C_SIGNAL_OFF = (62, 48, 28)
    C_BRAKE_ON = (236, 36, 42)
    C_BRAKE_OFF = (62, 22, 24)
    C_BEAM = (236, 244, 255)

    _BODY_PROFILE = (
        (0.00, 10.0),
        (0.03, 22.0),
        (0.06, 36.0),
        (0.10, 48.0),
        (0.16, 55.0),
        (0.24, 58.0),
        (0.36, 55.0),
        (0.50, 54.0),
        (0.66, 56.0),
        (0.78, 57.0),
        (0.88, 50.0),
        (0.94, 34.0),
        (0.98, 20.0),
        (1.00, 11.0),
    )

    def __init__(self):
        pygame.font.init()
        self._rebuild_fonts(860, 920)

    def resize(self, width: int, height: int):
        self._rebuild_fonts(width, height)

    def _rebuild_fonts(self, width: int, height: int):
        scale = max(0.78, min(width / 860.0, height / 920.0))
        self.font_speed = pygame.font.SysFont("dejavusans,helvetica,sans", int(54 * scale), bold=True)
        self.font_unit = pygame.font.SysFont("dejavusans,helvetica,sans", int(13 * scale), bold=True)
        self.font_header = pygame.font.SysFont("dejavusans,helvetica,sans", int(13 * scale), bold=True)
        self.font_body = pygame.font.SysFont("dejavusansmono,liberationmono,nimbusmonol,monospace", int(13 * scale))
        self.font_badge = pygame.font.SysFont("dejavusans,helvetica,sans", int(11 * scale), bold=True)
        self.font_small = pygame.font.SysFont("dejavusans,helvetica,sans", int(11 * scale))

    def render(self, surface: pygame.Surface, state: VehicleState):
        w, h = surface.get_size()
        s = max(0.72, min(w / 860.0, h / 920.0))
        cx = w // 2
        cy = h // 2 + int(18 * s)

        if state.headlights:
            self._draw_headlights(surface, cx, cy, s)
        if state.brake_pressed:
            self._draw_brake_glow(surface, cx, cy, s)

        self._draw_wheels(surface, cx, cy, s)
        self._draw_car_body(surface, cx, cy, s)
        self._draw_doors(surface, state, cx, cy, s)
        self._draw_turn_signals(surface, state, cx, cy, s)
        self._draw_brake_lights(surface, state, cx, cy, s)
        self._draw_hud(surface, state, w, h)

    def _profile_width(self, t: float) -> float:
        keys = self._BODY_PROFILE
        if t <= 0.0:
            return keys[0][1]
        if t >= 1.0:
            return keys[-1][1]
        for i in range(len(keys) - 1):
            t0, w0 = keys[i]
            t1, w1 = keys[i + 1]
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0)
                u = (1.0 - math.cos(u * math.pi)) * 0.5
                return w0 + (w1 - w0) * u
        return keys[-1][1]

    def _body_points(self, cx: float, cy: float, s: float, inset: float = 0.0, t0: float = 0.0, t1: float = 1.0):
        n = 64
        length = 236.0 * s
        y0 = cy - 118.0 * s
        left = []
        right = []
        for i in range(n):
            t = t0 + (t1 - t0) * (i / (n - 1))
            y = y0 + t * length
            hw = max(4.0, (self._profile_width(t) - inset) * s)
            left.append((cx - hw, y))
            right.append((cx + hw, y))
        return left + list(reversed(right))

    def _draw_car_body(self, surface: pygame.Surface, cx: int, cy: int, s: float):
        pts = self._body_points(cx, cy, s)
        shadow = [(x + 2, y + 8) for x, y in pts]
        pygame.draw.polygon(surface, (8, 10, 12), shadow)

        pygame.draw.polygon(surface, self.C_BODY_LO, pts)
        pygame.draw.polygon(surface, self.C_BODY, pts)

        hi = self._body_points(cx - 4 * s, cy - 6 * s, s, inset=10)
        hi_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(hi_surf, (*self.C_BODY_HI, 70), hi)
        surface.blit(hi_surf, (0, 0))

        pygame.draw.polygon(surface, self.C_OUTLINE, pts, max(2, int(2 * s)))

        glass = self._body_points(cx, cy, s, inset=14, t0=0.22, t1=0.78)
        pygame.draw.polygon(surface, self.C_GLASS_ROOF, glass)
        pygame.draw.polygon(surface, (48, 68, 88), glass, max(1, int(2 * s)))

        windshield = self._body_points(cx, cy, s, inset=16, t0=0.18, t1=0.32)
        pygame.draw.polygon(surface, (30, 48, 66), windshield)
        rear_glass = self._body_points(cx, cy, s, inset=16, t0=0.74, t1=0.86)
        pygame.draw.polygon(surface, (26, 40, 54), rear_glass)

        # Roof highlight
        roof = pygame.Rect(0, 0, int(42 * s), int(78 * s))
        roof.center = (int(cx), int(cy - 4 * s))
        pygame.draw.ellipse(surface, (40, 58, 74), roof)

        self._draw_mirrors(surface, cx, cy, s)

        # Soft bumper caps so the nose/tail stay round
        nose = pygame.Rect(0, 0, int(38 * s), int(22 * s))
        nose.center = (int(cx), int(cy - 116 * s))
        pygame.draw.ellipse(surface, self.C_BODY, nose)
        tail = pygame.Rect(0, 0, int(40 * s), int(20 * s))
        tail.center = (int(cx), int(cy + 116 * s))
        pygame.draw.ellipse(surface, self.C_BODY, tail)

    def _draw_mirrors(self, surface: pygame.Surface, cx: int, cy: int, s: float):
        my = int(cy - 52 * s)
        for side in (-1, 1):
            rect = pygame.Rect(0, 0, int(18 * s), int(12 * s))
            rect.center = (int(cx + side * 70 * s), my)
            pygame.draw.ellipse(surface, self.C_BODY, rect)
            inner = rect.inflate(-4, -4)
            pygame.draw.ellipse(surface, (70, 88, 104), inner)

    def _draw_wheels(self, surface: pygame.Surface, cx: int, cy: int, s: float):
        positions = [
            (cx - 62 * s, cy - 70 * s),
            (cx + 62 * s, cy - 70 * s),
            (cx - 62 * s, cy + 62 * s),
            (cx + 62 * s, cy + 62 * s),
        ]
        tw, th = int(16 * s), int(38 * s)
        for px, py in positions:
            tire = pygame.Rect(0, 0, tw, th)
            tire.center = (int(px), int(py))
            pygame.draw.ellipse(surface, self.C_TIRE, tire)
            rim = tire.inflate(-int(6 * s), -int(12 * s))
            pygame.draw.ellipse(surface, self.C_RIM, rim)
            hub = tire.inflate(-int(10 * s), -int(22 * s))
            pygame.draw.ellipse(surface, (210, 214, 220), hub)

    def _draw_headlights(self, surface: pygame.Surface, cx: int, cy: int, s: float):
        w, h = surface.get_size()
        beam = pygame.Surface((w, h), pygame.SRCALPHA)
        origin_y = cy - 108 * s
        for i in range(10):
            t = i / 9.0
            length = (40 + t * 240) * s
            width = (16 + t * 90) * s
            alpha = int(40 * (1.0 - t) ** 1.6)
            for sx in (cx - 34 * s, cx + 34 * s):
                rect = pygame.Rect(0, 0, int(width), int(length * 0.55))
                rect.midbottom = (int(sx), int(origin_y + 6 * s))
                pygame.draw.ellipse(beam, (*self.C_BEAM, alpha), rect)
        for sx in (cx - 34 * s, cx + 34 * s):
            glow = pygame.Rect(0, 0, int(20 * s), int(14 * s))
            glow.center = (int(sx), int(origin_y))
            pygame.draw.ellipse(beam, (255, 255, 255, 220), glow)
        surface.blit(beam, (0, 0))

    def _draw_brake_glow(self, surface: pygame.Surface, cx: int, cy: int, s: float):
        glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, int(170 * s), int(80 * s))
        rect.center = (int(cx), int(cy + 150 * s))
        pygame.draw.ellipse(glow, (220, 24, 32, 50), rect)
        surface.blit(glow, (0, 0))

    def _blit_pivoted(self, dest, image, pivot, origin, angle_deg):
        image_rect = image.get_rect(topleft=(pivot[0] - origin[0], pivot[1] - origin[1]))
        offset = pygame.math.Vector2(pivot) - pygame.math.Vector2(image_rect.center)
        rotated_offset = offset.rotate(-angle_deg)
        rotated = pygame.transform.rotate(image, angle_deg)
        rect = rotated.get_rect(center=image_rect.center + rotated_offset)
        dest.blit(rotated, rect)

    def _draw_doors(self, surface: pygame.Surface, state: VehicleState, cx: int, cy: int, s: float):
        length = int(52 * s)
        thickness = max(8, int(11 * s))
        specs = [
            (state.door_fl, (cx - 56 * s, cy - 58 * s), 1, 58),
            (state.door_fr, (cx + 56 * s, cy - 58 * s), -1, -58),
            (state.door_rl, (cx - 55 * s, cy + 2 * s), 1, 58),
            (state.door_rr, (cx + 55 * s, cy + 2 * s), -1, -58),
        ]
        for is_open, hinge, side, open_angle in specs:
            door = pygame.Surface((thickness, length), pygame.SRCALPHA)
            color = self.C_BRAKE_ON if is_open else (58, 66, 78)
            pygame.draw.rect(door, color, door.get_rect(), border_radius=max(3, int(5 * s)))
            window = pygame.Rect(2, 6, thickness - 4, int(length * 0.42))
            pygame.draw.rect(door, (28, 40, 52), window, border_radius=3)
            origin = (thickness // 2 if side < 0 else thickness // 2, 4)
            angle = open_angle if is_open else 0
            self._blit_pivoted(surface, door, hinge, origin, angle)

    def _draw_turn_signals(self, surface: pygame.Surface, state: VehicleState, cx: int, cy: int, s: float):
        blink = (pygame.time.get_ticks() // 380) % 2 == 0
        mode = state.turn_signal
        left_on = (mode in (SIGNAL_LEFT, SIGNAL_HAZARD)) and blink
        right_on = (mode in (SIGNAL_RIGHT, SIGNAL_HAZARD)) and blink
        coords = [
            (cx - 42 * s, cy - 104 * s, left_on),
            (cx + 42 * s, cy - 104 * s, right_on),
            (cx - 44 * s, cy + 108 * s, left_on),
            (cx + 44 * s, cy + 108 * s, right_on),
        ]
        for sx, sy, on in coords:
            col = self.C_SIGNAL_ON if on else self.C_SIGNAL_OFF
            rect = pygame.Rect(0, 0, int(16 * s), int(10 * s))
            rect.center = (int(sx), int(sy))
            pygame.draw.ellipse(surface, col, rect)
            if on:
                glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                g = rect.inflate(14, 10)
                pygame.draw.ellipse(glow, (*self.C_SIGNAL_ON, 70), g)
                surface.blit(glow, (0, 0))

    def _draw_brake_lights(self, surface: pygame.Surface, state: VehicleState, cx: int, cy: int, s: float):
        col = self.C_BRAKE_ON if state.brake_pressed else self.C_BRAKE_OFF
        bar = pygame.Rect(0, 0, int(88 * s), max(5, int(7 * s)))
        bar.center = (int(cx), int(cy + 112 * s))
        pygame.draw.rect(surface, col, bar, border_radius=bar.height // 2)
        lamp_w = max(10, int(14 * s))
        for side in (-1, 1):
            lamp = pygame.Rect(0, 0, lamp_w, max(8, int(10 * s)))
            lamp.center = (int(cx + side * 40 * s), int(cy + 112 * s))
            pygame.draw.ellipse(surface, col, lamp)

    def _draw_speed_arc(self, panel, cx, cy, radius, speed, color_bg, color_fg):
        rect = pygame.Rect(0, 0, radius * 2, radius * 2)
        rect.center = (cx, cy)
        pygame.draw.arc(panel, color_bg, rect, math.radians(210), math.radians(330), 6)
        ratio = min(max(speed / MAX_SPEED_KMH, 0.0), 1.0)
        end = 210 + 120 * ratio
        if ratio > 0.002:
            pygame.draw.arc(panel, color_fg, rect, math.radians(210), math.radians(end), 6)

    def _badge(self, surf, x, y, w, h, label, active, active_col):
        bg = active_col if active else (36, 42, 54)
        fg = (255, 255, 255) if active else self.C_TEXT_MUTED
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surf, bg, rect, border_radius=h // 2)
        t = self.font_badge.render(label, True, fg)
        surf.blit(t, (x + (w - t.get_width()) // 2, y + (h - t.get_height()) // 2))

    def _glass_card(self, size):
        card = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(card, self.C_GLASS, card.get_rect(), border_radius=18)
        pygame.draw.rect(card, self.C_GLASS_LINE, card.get_rect(), 1, border_radius=18)
        return card

    def _mini_bar(self, card, x, y, bar_w, bar_h, ratio, color):
        """Draw a small colored fill bar with background track."""
        pygame.draw.rect(card, (40, 48, 60), (x, y, bar_w, bar_h), border_radius=bar_h // 2)
        fill = int(bar_w * min(max(ratio, 0.0), 1.0))
        if fill:
            pygame.draw.rect(card, color, (x, y, fill, bar_h), border_radius=bar_h // 2)

    def _draw_hud(self, surface: pygame.Surface, state: VehicleState, w: int, h: int):
        margin = 22
        card_h = min(168, max(132, h // 6))
        left_w = min(300, max(220, w // 3))
        right_w = min(360, max(250, w // 2 - 40))

        # ── Speed cluster (top-left) ──────────────────────────────────────────
        panel_l = self._glass_card((left_w, card_h))
        title = self.font_header.render("SPEED", True, self.C_TEXT_MUTED)
        panel_l.blit(title, (18, 12))
        speed_txt = self.font_speed.render(f"{int(state.speed_kmh)}", True, self.C_TEXT_MAIN)
        unit = self.font_unit.render("km/h", True, self.C_TEXT_MUTED)
        panel_l.blit(speed_txt, (18, 34))
        panel_l.blit(unit, (22 + speed_txt.get_width(), 58))
        self._draw_speed_arc(
            panel_l, left_w - 58, 78, 44,
            state.speed_kmh, (48, 56, 70), (232, 236, 242),
        )
        bar_w = left_w - 36
        self._mini_bar(panel_l, 18, card_h - 22, bar_w, 7,
                       state.speed_kmh / MAX_SPEED_KMH, (236, 240, 246))
        surface.blit(panel_l, (margin, margin))

        # ── CAN telemetry panel (top-right) – all 6 IDs ──────────────────────
        panel_r = self._glass_card((right_w, card_h))
        sys_title = self.font_header.render("CAN BUS", True, self.C_TEXT_MUTED)
        panel_r.blit(sys_title, (18, 12))
        can_ok = state.can_connected
        can_col = (64, 214, 140) if can_ok else (236, 72, 72)
        can_txt = self.font_body.render(
            f"{state.can_interface_name}  {'LIVE' if can_ok else 'OFFLINE'}",
            True, can_col,
        )
        panel_r.blit(can_txt, (18, 34))

        raw_speed = int(round(min(max(state.speed_kmh, 0.0), MAX_SPEED_KMH) * 100.0))
        brake_b   = 0x01 if state.brake_pressed else 0x00
        doors_b   = state.get_doors_bitmask()
        lights_b  = state.turn_signal & 0x03
        hl_b      = 0x01 if state.headlights else 0x00
        raw_rpm   = int(state.engine_rpm)
        raw_thr   = int(state.throttle_pos * 2.0)
        raw_temp  = int(state.coolant_temp + 40.0)
        raw_fuel  = int(state.fuel_level * 2.0)
        raw_steer = int(state.steering_angle * 10.0) & 0xFFFF
        raw_bat   = int(state.battery_voltage * 10.0)

        frames = [
            ("0x0C8", f"{raw_rpm:04X} {raw_thr:02X}",     "rpm / throttle"),
            ("0x110", f"{raw_speed:04X} {brake_b:02X}",   "speed / brake"),
            ("0x2B0", f"{raw_steer:04X} {raw_bat:02X}",   "steer / battery"),
            ("0x3B0", f"{raw_temp:02X} {raw_fuel:02X}",   "temp / fuel"),
            ("0x280", f"{doors_b:02X}",                    "doors bitmask"),
            ("0x290", f"{lights_b:02X} {hl_b:02X}",       "signal / lamps"),
        ]
        id_col, pay_col, cap_col = 14, 72, 160
        for i, (cid, payload, caption) in enumerate(frames):
            y = 56 + i * 18
            panel_r.blit(self.font_body.render(cid,      True, (120, 196, 255)), (id_col, y))
            panel_r.blit(self.font_body.render(payload,  True, self.C_TEXT_MAIN), (pay_col, y))
            panel_r.blit(self.font_small.render(caption, True, self.C_TEXT_MUTED), (cap_col, y + 1))

        surface.blit(panel_r, (w - right_w - margin, margin))

        # ── Second row: mini-gauge strip ──────────────────────────────────────
        gauge_y = margin + card_h + 10
        gauge_h = min(56, max(44, h // 18))
        gauge_gap = 8

        # RPM gauge
        rpm_w = min(left_w, 200)
        rpm_card = self._glass_card((rpm_w, gauge_h))
        rpm_card.blit(self.font_small.render("RPM", True, self.C_TEXT_MUTED), (12, 6))
        rpm_card.blit(self.font_badge.render(f"{int(state.engine_rpm):,}", True, self.C_TEXT_MAIN), (12, 22))
        rpm_ratio = state.engine_rpm / 7000.0
        rpm_col = (120, 220, 80) if rpm_ratio < 0.75 else (255, 120, 30) if rpm_ratio < 0.9 else (236, 40, 40)
        self._mini_bar(rpm_card, 12, gauge_h - 10, rpm_w - 24, 5, rpm_ratio, rpm_col)
        surface.blit(rpm_card, (margin, gauge_y))

        # Coolant temp gauge
        temp_w = 110
        temp_x = margin + rpm_w + gauge_gap
        temp_card = self._glass_card((temp_w, gauge_h))
        temp_card.blit(self.font_small.render("TEMP", True, self.C_TEXT_MUTED), (10, 6))
        temp_card.blit(self.font_badge.render(f"{int(state.coolant_temp)}°C", True, self.C_TEXT_MAIN), (10, 22))
        temp_ratio = min(max((state.coolant_temp - 20.0) / 100.0, 0.0), 1.0)
        t_col = (80, 160, 255) if temp_ratio < 0.3 else (120, 220, 80) if temp_ratio < 0.75 else (236, 40, 40)
        self._mini_bar(temp_card, 10, gauge_h - 10, temp_w - 20, 5, temp_ratio, t_col)
        surface.blit(temp_card, (temp_x, gauge_y))

        # Throttle gauge (new)
        thr_w = 100
        thr_x = temp_x + temp_w + gauge_gap
        thr_card = self._glass_card((thr_w, gauge_h))
        thr_card.blit(self.font_small.render("GAS", True, self.C_TEXT_MUTED), (10, 6))
        thr_card.blit(self.font_badge.render(f"{int(state.throttle_pos)}%", True, self.C_TEXT_MAIN), (10, 22))
        thr_col = (64, 200, 120) if state.throttle_pos < 70 else (255, 160, 30)
        self._mini_bar(thr_card, 10, gauge_h - 10, thr_w - 20, 5,
                       state.throttle_pos / 100.0, thr_col)
        surface.blit(thr_card, (thr_x, gauge_y))

        # Fuel gauge (right side, anchored right)
        fuel_w = 110
        fuel_x = w - margin - fuel_w
        fuel_card = self._glass_card((fuel_w, gauge_h))
        fuel_card.blit(self.font_small.render("FUEL", True, self.C_TEXT_MUTED), (10, 6))
        fuel_card.blit(self.font_badge.render(f"{state.fuel_level:.1f}%", True, self.C_TEXT_MAIN), (10, 22))
        fuel_ratio = state.fuel_level / 100.0
        f_col = (236, 40, 40) if fuel_ratio < 0.15 else (255, 180, 30) if fuel_ratio < 0.30 else (64, 200, 120)
        self._mini_bar(fuel_card, 10, gauge_h - 10, fuel_w - 20, 5, fuel_ratio, f_col)
        surface.blit(fuel_card, (fuel_x, gauge_y))

        # Battery voltage gauge
        bat_w = 120
        bat_x = fuel_x - bat_w - gauge_gap
        bat_card = self._glass_card((bat_w, gauge_h))
        bat_card.blit(self.font_small.render("BATTERY", True, self.C_TEXT_MUTED), (10, 6))
        bat_card.blit(self.font_badge.render(f"{state.battery_voltage:.2f}V", True, self.C_TEXT_MAIN), (10, 22))
        bat_ratio = min(max((state.battery_voltage - 11.0) / 4.0, 0.0), 1.0)
        b_col = (236, 40, 40) if bat_ratio < 0.25 else (120, 220, 80)
        self._mini_bar(bat_card, 10, gauge_h - 10, bat_w - 20, 5, bat_ratio, b_col)
        surface.blit(bat_card, (bat_x, gauge_y))

        # Steering angle gauge
        steer_w = 120
        steer_x = bat_x - steer_w - gauge_gap
        steer_card = self._glass_card((steer_w, gauge_h))
        steer_card.blit(self.font_small.render("STEER", True, self.C_TEXT_MUTED), (10, 6))
        steer_card.blit(self.font_badge.render(f"{state.steering_angle:+.1f}°", True, self.C_TEXT_MAIN), (10, 22))
        # Centre-origin bar: 0 = centre, positive = right
        steer_ratio = (state.steering_angle + 540.0) / 1080.0
        s_col = (120, 196, 255)
        bar_fw = steer_w - 20
        pygame.draw.rect(steer_card, (40, 48, 60), (10, gauge_h - 10, bar_fw, 5), border_radius=3)
        mid = bar_fw // 2
        pygame.draw.rect(steer_card, (70, 80, 96), (10 + mid - 1, gauge_h - 13, 2, 11))  # centre marker
        steer_px = int(steer_ratio * bar_fw)
        needle_x = min(10 + steer_px, 10 + bar_fw - 1)
        pygame.draw.rect(steer_card, s_col, (needle_x - 2, gauge_h - 12, 4, 9), border_radius=2)
        surface.blit(steer_card, (steer_x, gauge_y))

        # ── Status chips ─────────────────────────────────────────────────────
        chip_y = gauge_y + gauge_h + 10
        sig_name = "SIG OFF"
        if state.turn_signal == SIGNAL_LEFT:
            sig_name = "LEFT"
        elif state.turn_signal == SIGNAL_RIGHT:
            sig_name = "RIGHT"
        elif state.turn_signal == SIGNAL_HAZARD:
            sig_name = "HAZARD"

        chips = pygame.Surface((min(w - margin * 2, 520), 34), pygame.SRCALPHA)
        self._badge(chips,   0, 4,  86, 26, "LIGHTS",                            state.headlights,                state.headlights and (70, 108, 168) or (70, 108, 168))
        self._badge(chips,  96, 4,  86, 26, "BRAKE",                             state.brake_pressed,             self.C_BRAKE_ON)
        self._badge(chips, 192, 4,  96, 26, sig_name,                            state.turn_signal != SIGNAL_OFF, self.C_SIGNAL_ON)
        door_open = any((state.door_fl, state.door_fr, state.door_rl, state.door_rr))
        self._badge(chips, 298, 4, 110, 26, "DOOR AJAR" if door_open else "DOORS OK", door_open,                 self.C_BRAKE_ON)
        surface.blit(chips, ((w - chips.get_width()) // 2, chip_y))

        # ── Footer controls ───────────────────────────────────────────────────
        footer_w = min(w - 40, 980)
        footer_h = 40
        footer = self._glass_card((footer_w, footer_h))
        ctrl = "[W] Gaz   [S] Fren   [A/D] Sinyal   [F] Dörtlü   [L] Far   [1-4] Kapılar   pencereyi sürükleyerek boyutlandır"
        txt = self.font_small.render(ctrl, True, self.C_TEXT_MUTED)
        if txt.get_width() > footer_w - 24:
            ctrl = "[W/S] Gaz/Fren  [A/D/F] Sinyal  [L] Far  [1-4] Kapı  kenardan boyutlandır"
            txt = self.font_small.render(ctrl, True, self.C_TEXT_MUTED)
        footer.blit(txt, ((footer_w - txt.get_width()) // 2, (footer_h - txt.get_height()) // 2))
        surface.blit(footer, ((w - footer_w) // 2, h - footer_h - 16))
