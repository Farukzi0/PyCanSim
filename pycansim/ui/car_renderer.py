"""
Car and HUD Renderer for PyCanSim.
Smooth top-down vehicle with glow outline and a grid-aligned glass HUD
(instrument cluster, CAN telemetry, gauges and a live sniffer panel).
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

    # Text / panels
    C_TEXT_MAIN = (238, 243, 250)
    C_TEXT_MUTED = (140, 152, 170)
    C_ACCENT = (64, 214, 255)
    C_GLASS = (14, 18, 26, 214)
    C_GLASS_LINE = (64, 78, 98, 150)
    C_TRACK = (38, 46, 60)

    # Car body
    C_BODY = (40, 48, 62)
    C_BODY_HI = (96, 112, 136)
    C_BODY_LO = (18, 22, 30)
    C_GLOW = (64, 214, 255)
    C_GLASS_ROOF = (16, 26, 42)
    C_WINDSHIELD = (34, 54, 76)
    C_PANEL_LINE = (22, 26, 34)
    C_TIRE = (14, 14, 18)
    C_RIM = (120, 130, 146)
    C_HUB = (198, 206, 216)
    C_SIGNAL_ON = (255, 170, 40)
    C_SIGNAL_OFF = (58, 46, 26)
    C_BRAKE_ON = (255, 46, 56)
    C_BRAKE_OFF = (70, 24, 26)
    C_HEADLIGHT = (255, 250, 232)
    C_TAIL = (255, 60, 64)

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
        scale = max(0.82, min(width / 860.0, height / 920.0))
        self.font_speed = pygame.font.SysFont("dejavusans,helvetica,sans", int(56 * scale), bold=True)
        self.font_unit = pygame.font.SysFont("dejavusans,helvetica,sans", int(14 * scale), bold=True)
        self.font_header = pygame.font.SysFont("dejavusans,helvetica,sans", int(13 * scale), bold=True)
        self.font_body = pygame.font.SysFont("dejavusansmono,liberationmono,nimbusmonol,monospace", int(13 * scale))
        self.font_badge = pygame.font.SysFont("dejavusans,helvetica,sans", int(16 * scale), bold=True)
        self.font_small = pygame.font.SysFont("dejavusans,helvetica,sans", int(11 * scale))

    # ======================================================================
    #  TOP-LEVEL
    # ======================================================================

    def render(self, surface: pygame.Surface, state: VehicleState, monitor=None):
        w, h = surface.get_size()
        s = max(0.72, min(w / 860.0, h / 920.0))
        cx = w // 2
        cy = h // 2 + int(42 * s)

        if state.headlights:
            self._draw_headlights(surface, cx, cy, s)
        if state.brake_pressed:
            self._draw_brake_glow(surface, cx, cy, s)

        self._draw_shadow(surface, cx, cy, s)
        self._draw_wheels(surface, cx, cy, s)
        self._draw_car_body(surface, cx, cy, s)
        self._draw_doors(surface, state, cx, cy, s)
        self._draw_turn_signals(surface, state, cx, cy, s)
        self._draw_brake_lights(surface, state, cx, cy, s)
        self._draw_hud(surface, state, w, h)
        if monitor is not None:
            self._draw_sniffer(surface, monitor, w, h)

    # ======================================================================
    #  CAR BODY
    # ======================================================================

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

    def _body_points(self, cx, cy, s, inset=0.0, t0=0.0, t1=1.0):
        n = 64
        length = 250.0 * s
        y0 = cy - 125.0 * s
        left, right = [], []
        for i in range(n):
            t = t0 + (t1 - t0) * (i / (n - 1))
            y = y0 + t * length
            hw = max(4.0, (self._profile_width(t) - inset) * s)
            left.append((cx - hw, y))
            right.append((cx + hw, y))
        return left + list(reversed(right))

    def _draw_shadow(self, surface, cx, cy, s):
        shadow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for i, a in enumerate((26, 36, 48)):
            spread = (10 - i * 3) * s
            pts = [(x, y + 10 * s) for x, y in self._body_points(cx, cy, s, inset=-spread)]
            pygame.draw.polygon(shadow, (0, 0, 0, a), pts)
        surface.blit(shadow, (0, 0))

    def _draw_car_body(self, surface, cx, cy, s):
        pts = self._body_points(cx, cy, s)

        # Cyan glow halo around the silhouette
        glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for i, a in enumerate((22, 34, 60)):
            w = max(2, int((9 - i * 3) * s))
            pygame.draw.polygon(glow, (*self.C_GLOW, a), self._body_points(cx, cy, s, inset=-(8 - i * 3)), w)
        surface.blit(glow, (0, 0))

        # Base body
        pygame.draw.polygon(surface, self.C_BODY_LO, pts)
        pygame.draw.polygon(surface, self.C_BODY, pts)

        # Vertical sheen: lighter upper half, blended via alpha
        hi = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        top_half = self._body_points(cx, cy, s, inset=8, t0=0.03, t1=0.5)
        pygame.draw.polygon(hi, (*self.C_BODY_HI, 55), top_half)
        side = self._body_points(cx - 10 * s, cy, s, inset=16)
        pygame.draw.polygon(hi, (*self.C_BODY_HI, 40), side)
        surface.blit(hi, (0, 0))

        # Crisp cyan outline
        pygame.draw.polygon(surface, self.C_GLOW, pts, max(2, int(2.2 * s)))

        # Hood & trunk panel seams
        self._panel_seam(surface, cx, cy, s, 0.14)
        self._panel_seam(surface, cx, cy, s, 0.86)

        # Greenhouse (roof glass)
        roof = self._body_points(cx, cy, s, inset=15, t0=0.24, t1=0.76)
        pygame.draw.polygon(surface, self.C_GLASS_ROOF, roof)
        pygame.draw.polygon(surface, (58, 82, 108), roof, max(1, int(2 * s)))

        # Windshield & rear glass tint
        windshield = self._body_points(cx, cy, s, inset=17, t0=0.20, t1=0.34)
        pygame.draw.polygon(surface, self.C_WINDSHIELD, windshield)
        rear = self._body_points(cx, cy, s, inset=17, t0=0.72, t1=0.86)
        pygame.draw.polygon(surface, (26, 42, 58), rear)

        # Thin roof spine highlight
        pygame.draw.line(surface, (58, 80, 104),
                         (cx, cy - 30 * s), (cx, cy + 30 * s), max(1, int(2 * s)))

        self._draw_mirrors(surface, cx, cy, s)

        # Rounded bumper caps
        for yy, wsc, hsc in ((-122, 36, 20), (122, 40, 18)):
            cap = pygame.Rect(0, 0, int(wsc * s), int(hsc * s))
            cap.center = (int(cx), int(cy + yy * s))
            pygame.draw.ellipse(surface, self.C_BODY, cap)

        # Front LED headlight strips
        for side in (-1, 1):
            led = pygame.Rect(0, 0, int(22 * s), int(7 * s))
            led.center = (int(cx + side * 34 * s), int(cy - 114 * s))
            pygame.draw.rect(surface, self.C_HEADLIGHT, led, border_radius=int(3 * s))
        # Rear tail light bar
        tail = pygame.Rect(0, 0, int(84 * s), int(7 * s))
        tail.center = (int(cx), int(cy + 118 * s))
        pygame.draw.rect(surface, (120, 26, 30), tail, border_radius=int(3 * s))

    def _panel_seam(self, surface, cx, cy, s, t):
        y = (cy - 125.0 * s) + t * (250.0 * s)
        hw = self._profile_width(t) * s - 6 * s
        pygame.draw.line(surface, self.C_PANEL_LINE, (cx - hw, y), (cx + hw, y), max(1, int(1.5 * s)))

    def _draw_mirrors(self, surface, cx, cy, s):
        my = int(cy - 54 * s)
        for side in (-1, 1):
            arm = pygame.Rect(0, 0, int(12 * s), int(6 * s))
            arm.center = (int(cx + side * 62 * s), my)
            pygame.draw.rect(surface, self.C_BODY, arm, border_radius=2)
            cap = pygame.Rect(0, 0, int(18 * s), int(11 * s))
            cap.center = (int(cx + side * 72 * s), my)
            pygame.draw.ellipse(surface, self.C_BODY, cap)
            pygame.draw.ellipse(surface, (74, 92, 112), cap.inflate(-4, -4))

    def _draw_wheels(self, surface, cx, cy, s):
        positions = [
            (cx - 64 * s, cy - 74 * s),
            (cx + 64 * s, cy - 74 * s),
            (cx - 64 * s, cy + 66 * s),
            (cx + 64 * s, cy + 66 * s),
        ]
        tw, th = int(17 * s), int(40 * s)
        for px, py in positions:
            tire = pygame.Rect(0, 0, tw, th)
            tire.center = (int(px), int(py))
            pygame.draw.ellipse(surface, (0, 0, 0), tire.inflate(4, 4))
            pygame.draw.ellipse(surface, self.C_TIRE, tire)
            rim = tire.inflate(-int(5 * s), -int(13 * s))
            pygame.draw.ellipse(surface, self.C_RIM, rim)
            hub = tire.inflate(-int(10 * s), -int(26 * s))
            pygame.draw.ellipse(surface, self.C_HUB, hub)

    def _draw_headlights(self, surface, cx, cy, s):
        w, h = surface.get_size()
        beam = pygame.Surface((w, h), pygame.SRCALPHA)
        origin_y = cy - 116 * s
        for i in range(12):
            t = i / 11.0
            length = (40 + t * 300) * s
            width = (18 + t * 120) * s
            alpha = int(36 * (1.0 - t) ** 1.7)
            for sx in (cx - 34 * s, cx + 34 * s):
                rect = pygame.Rect(0, 0, int(width), int(length * 0.55))
                rect.midbottom = (int(sx), int(origin_y + 6 * s))
                pygame.draw.ellipse(beam, (*self.C_HEADLIGHT, alpha), rect)
        for sx in (cx - 34 * s, cx + 34 * s):
            glow = pygame.Rect(0, 0, int(22 * s), int(14 * s))
            glow.center = (int(sx), int(origin_y))
            pygame.draw.ellipse(beam, (255, 255, 255, 230), glow)
        surface.blit(beam, (0, 0))

    def _draw_brake_glow(self, surface, cx, cy, s):
        glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, int(190 * s), int(90 * s))
        rect.center = (int(cx), int(cy + 160 * s))
        pygame.draw.ellipse(glow, (230, 26, 34, 55), rect)
        surface.blit(glow, (0, 0))

    def _blit_pivoted(self, dest, image, pivot, origin, angle_deg):
        image_rect = image.get_rect(topleft=(pivot[0] - origin[0], pivot[1] - origin[1]))
        offset = pygame.math.Vector2(pivot) - pygame.math.Vector2(image_rect.center)
        rotated_offset = offset.rotate(-angle_deg)
        rotated = pygame.transform.rotate(image, angle_deg)
        rect = rotated.get_rect(center=image_rect.center + rotated_offset)
        dest.blit(rotated, rect)

    def _draw_doors(self, surface, state, cx, cy, s):
        length = int(52 * s)
        thickness = max(8, int(11 * s))
        specs = [
            (state.door_fl, (cx - 56 * s, cy - 62 * s), 1, 58),
            (state.door_fr, (cx + 56 * s, cy - 62 * s), -1, -58),
            (state.door_rl, (cx - 55 * s, cy - 2 * s), 1, 58),
            (state.door_rr, (cx + 55 * s, cy - 2 * s), -1, -58),
        ]
        for is_open, hinge, side, open_angle in specs:
            door = pygame.Surface((thickness, length), pygame.SRCALPHA)
            color = self.C_BRAKE_ON if is_open else (56, 66, 82)
            pygame.draw.rect(door, color, door.get_rect(), border_radius=max(3, int(5 * s)))
            window = pygame.Rect(2, 6, thickness - 4, int(length * 0.42))
            pygame.draw.rect(door, (28, 44, 60), window, border_radius=3)
            origin = (thickness // 2, 4)
            angle = open_angle if is_open else 0
            self._blit_pivoted(surface, door, hinge, origin, angle)

    def _draw_turn_signals(self, surface, state, cx, cy, s):
        blink = (pygame.time.get_ticks() // 380) % 2 == 0
        mode = state.turn_signal
        left_on = (mode in (SIGNAL_LEFT, SIGNAL_HAZARD)) and blink
        right_on = (mode in (SIGNAL_RIGHT, SIGNAL_HAZARD)) and blink
        coords = [
            (cx - 46 * s, cy - 110 * s, left_on),
            (cx + 46 * s, cy - 110 * s, right_on),
            (cx - 48 * s, cy + 114 * s, left_on),
            (cx + 48 * s, cy + 114 * s, right_on),
        ]
        for sx, sy, on in coords:
            col = self.C_SIGNAL_ON if on else self.C_SIGNAL_OFF
            rect = pygame.Rect(0, 0, int(15 * s), int(9 * s))
            rect.center = (int(sx), int(sy))
            pygame.draw.ellipse(surface, col, rect)
            if on:
                glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (*self.C_SIGNAL_ON, 80), rect.inflate(16, 12))
                surface.blit(glow, (0, 0))

    def _draw_brake_lights(self, surface, state, cx, cy, s):
        col = self.C_BRAKE_ON if state.brake_pressed else self.C_BRAKE_OFF
        bar = pygame.Rect(0, 0, int(80 * s), max(5, int(7 * s)))
        bar.center = (int(cx), int(cy + 118 * s))
        pygame.draw.rect(surface, col, bar, border_radius=bar.height // 2)
        if state.brake_pressed:
            glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*self.C_BRAKE_ON, 90), bar.inflate(20, 14),
                             border_radius=bar.height)
            surface.blit(glow, (0, 0))

    # ======================================================================
    #  HUD HELPERS
    # ======================================================================

    def _glass_card(self, size, radius=16):
        card = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(card, self.C_GLASS, card.get_rect(), border_radius=radius)
        # top inner highlight
        hi = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(hi, (255, 255, 255, 14), (0, 0, size[0], max(2, size[1] // 2)), border_radius=radius)
        card.blit(hi, (0, 0))
        pygame.draw.rect(card, self.C_GLASS_LINE, card.get_rect(), 1, border_radius=radius)
        return card

    def _label(self, surf, text, x, y):
        surf.blit(self.font_header.render(text, True, self.C_TEXT_MUTED), (x, y))

    def _mini_bar(self, card, x, y, bar_w, bar_h, ratio, color):
        pygame.draw.rect(card, self.C_TRACK, (x, y, bar_w, bar_h), border_radius=bar_h // 2)
        fill = int(bar_w * min(max(ratio, 0.0), 1.0))
        if fill:
            pygame.draw.rect(card, color, (x, y, fill, bar_h), border_radius=bar_h // 2)

    def _draw_speed_arc(self, panel, cx, cy, radius, speed, color_bg, color_fg):
        rect = pygame.Rect(0, 0, radius * 2, radius * 2)
        rect.center = (cx, cy)
        pygame.draw.arc(panel, color_bg, rect, math.radians(210), math.radians(330), 7)
        ratio = min(max(speed / MAX_SPEED_KMH, 0.0), 1.0)
        end = 210 + 120 * ratio
        if ratio > 0.002:
            pygame.draw.arc(panel, color_fg, rect, math.radians(210), math.radians(end), 7)

    def _badge(self, surf, x, y, w, h, label, active, active_col):
        bg = active_col if active else (34, 40, 52)
        fg = (255, 255, 255) if active else self.C_TEXT_MUTED
        pygame.draw.rect(surf, bg, pygame.Rect(x, y, w, h), border_radius=h // 2)
        t = self.font_small.render(label, True, fg)
        surf.blit(t, (x + (w - t.get_width()) // 2, y + (h - t.get_height()) // 2))

    def _gauge(self, surface, x, y, gw, gh, label, value_str, ratio, color):
        card = self._glass_card((gw, gh))
        card.blit(self.font_small.render(label, True, self.C_TEXT_MUTED), (12, 8))
        card.blit(self.font_badge.render(value_str, True, self.C_TEXT_MAIN), (12, 21))
        self._mini_bar(card, 12, gh - 13, gw - 24, 6, ratio, color)
        surface.blit(card, (x, y))

    @staticmethod
    def _grade(ratio, good, warn, bad, lo=0.75, hi=0.9):
        return good if ratio < lo else warn if ratio < hi else bad

    # ======================================================================
    #  HUD
    # ======================================================================

    def _draw_hud(self, surface, state, w, h):
        GUT = 20
        GAP = 12

        # ---------- ROW 1 : speed cluster + CAN telemetry ----------
        h1 = int(min(188, max(158, h * 0.2)))
        inner = w - 2 * GUT
        left_w = int(min(300, max(236, inner * 0.33)))
        right_w = int(min(360, max(300, inner * 0.40)))

        # Speed cluster (left)
        card = self._glass_card((left_w, h1))
        self._label(card, "SPEED", 20, 16)
        spd = self.font_speed.render(f"{int(state.speed_kmh)}", True, self.C_TEXT_MAIN)
        card.blit(spd, (18, 38))
        card.blit(self.font_unit.render("km/h", True, self.C_TEXT_MUTED),
                  (24 + spd.get_width(), 38 + spd.get_height() - 24))
        self._draw_speed_arc(card, left_w - 58, 74, 42, state.speed_kmh, (46, 54, 68), self.C_ACCENT)
        self._mini_bar(card, 20, h1 - 26, left_w - 40, 8, state.speed_kmh / MAX_SPEED_KMH, self.C_ACCENT)
        surface.blit(card, (GUT, GUT))

        # CAN telemetry (right)
        card = self._glass_card((right_w, h1))
        self._label(card, "CAN BUS", 18, 16)
        ok = state.can_connected
        dot = (72, 220, 150) if ok else (236, 78, 78)
        pygame.draw.circle(card, dot, (right_w - 78, 22), 5)
        card.blit(self.font_body.render("LIVE" if ok else "OFFLINE", True, dot), (right_w - 66, 15))

        raw_speed = int(round(min(max(state.speed_kmh, 0.0), MAX_SPEED_KMH) * 100.0))
        brake_b = 0x01 if state.brake_pressed else 0x00
        frames = [
            ("0x0C8", f"{int(state.engine_rpm):04X} {int(state.throttle_pos * 2):02X}", "rpm/thr"),
            ("0x110", f"{raw_speed:04X} {brake_b:02X}", "spd/brk"),
            ("0x2B0", f"{int(state.steering_angle * 10) & 0xFFFF:04X} {int(state.battery_voltage * 10):02X}", "str/bat"),
            ("0x3B0", f"{int(state.coolant_temp + 40):02X} {int(state.fuel_level * 2):02X}", "tmp/fuel"),
            ("0x280", f"{state.get_doors_bitmask():02X}", "doors"),
            ("0x290", f"{state.turn_signal & 0x03:02X} {0x01 if state.headlights else 0x00:02X}", "sig/lmp"),
        ]
        row_h = (h1 - 48) // 6
        for i, (cid, payload, cap) in enumerate(frames):
            y = 44 + i * row_h
            card.blit(self.font_body.render(cid, True, self.C_ACCENT), (18, y))
            card.blit(self.font_body.render(payload, True, self.C_TEXT_MAIN), (84, y))
            card.blit(self.font_small.render(cap, True, self.C_TEXT_MUTED), (right_w - 70, y + 1))
        surface.blit(card, (w - right_w - GUT, GUT))

        # ---------- ROW 2 : six equal gauges ----------
        y2 = GUT + h1 + GAP
        h2 = int(min(62, max(52, h * 0.065)))
        gw = (inner - 5 * GAP) // 6
        xs = [GUT + i * (gw + GAP) for i in range(6)]

        rpm_r = state.engine_rpm / 7000.0
        self._gauge(surface, xs[0], y2, gw, h2, "RPM", f"{int(state.engine_rpm):,}",
                    rpm_r, self._grade(rpm_r, (120, 220, 90), (255, 150, 40), (236, 48, 48)))
        tmp_r = min(max((state.coolant_temp - 20) / 100.0, 0.0), 1.0)
        self._gauge(surface, xs[1], y2, gw, h2, "TEMP", f"{int(state.coolant_temp)}°C",
                    tmp_r, self._grade(tmp_r, (90, 170, 255), (120, 220, 90), (236, 48, 48), 0.3, 0.78))
        self._gauge(surface, xs[2], y2, gw, h2, "GAS", f"{int(state.throttle_pos)}%",
                    state.throttle_pos / 100.0, (72, 206, 128) if state.throttle_pos < 70 else (255, 162, 36))

        # Steering (centre-origin) — custom bar
        card = self._glass_card((gw, h2))
        card.blit(self.font_small.render("STEER", True, self.C_TEXT_MUTED), (12, 8))
        card.blit(self.font_badge.render(f"{state.steering_angle:+.1f}°", True, self.C_TEXT_MAIN), (12, 21))
        bw = gw - 24
        pygame.draw.rect(card, self.C_TRACK, (12, h2 - 13, bw, 6), border_radius=3)
        mid = 12 + bw // 2
        pygame.draw.rect(card, (70, 82, 100), (mid - 1, h2 - 16, 2, 12))
        sr = (state.steering_angle + 540.0) / 1080.0
        nx = int(12 + min(max(sr, 0.0), 1.0) * bw)
        pygame.draw.rect(card, self.C_ACCENT, (min(nx, 12 + bw - 3) - 2, h2 - 15, 4, 10), border_radius=2)
        surface.blit(card, (xs[3], y2))

        bat_r = min(max((state.battery_voltage - 11.0) / 4.0, 0.0), 1.0)
        self._gauge(surface, xs[4], y2, gw, h2, "BATTERY", f"{state.battery_voltage:.2f}V",
                    bat_r, (236, 48, 48) if bat_r < 0.25 else (120, 220, 90))
        fuel_r = state.fuel_level / 100.0
        self._gauge(surface, xs[5], y2, gw, h2, "FUEL", f"{state.fuel_level:.0f}%",
                    fuel_r, self._grade(1 - fuel_r, (72, 206, 128), (255, 180, 40), (236, 48, 48), 0.7, 0.85))

        # ---------- ROW 3 : status chips ----------
        y3 = y2 + h2 + GAP
        sig = {SIGNAL_LEFT: "LEFT", SIGNAL_RIGHT: "RIGHT", SIGNAL_HAZARD: "HAZARD"}.get(state.turn_signal, "SIG OFF")
        door_open = any((state.door_fl, state.door_fr, state.door_rl, state.door_rr))
        chips = [
            ("LIGHTS", state.headlights, (66, 120, 196)),
            ("BRAKE", state.brake_pressed, self.C_BRAKE_ON),
            (sig, state.turn_signal != SIGNAL_OFF, self.C_SIGNAL_ON),
            ("DOOR AJAR" if door_open else "DOORS OK", door_open, self.C_BRAKE_ON),
        ]
        cw, ch, cgap = 108, 28, 10
        total = len(chips) * cw + (len(chips) - 1) * cgap
        strip = pygame.Surface((total, ch), pygame.SRCALPHA)
        for i, (label, active, col) in enumerate(chips):
            self._badge(strip, i * (cw + cgap), 0, cw, ch, label, active, col)
        surface.blit(strip, ((w - total) // 2, y3))

        # ---------- Footer ----------
        footer_w = min(w - 40, 940)
        fh = 38
        footer = self._glass_card((footer_w, fh))
        ctrl = "[W] Gaz   [S] Fren   [A/D] Sinyal   [F] Dörtlü   [L] Far   [1-4] Kapılar   [R] Kayıt"
        txt = self.font_small.render(ctrl, True, self.C_TEXT_MUTED)
        if txt.get_width() > footer_w - 24:
            txt = self.font_small.render("[W/S] Gaz/Fren  [A/D/F] Sinyal  [L] Far  [1-4] Kapı  [R] Kayıt", True, self.C_TEXT_MUTED)
        footer.blit(txt, ((footer_w - txt.get_width()) // 2, (fh - txt.get_height()) // 2))
        surface.blit(footer, ((w - footer_w) // 2, h - fh - 14))

    # ======================================================================
    #  SNIFFER PANEL
    # ======================================================================

    def _draw_sniffer(self, surface, monitor, w, h):
        frames = monitor.recent_frames()
        alerts = monitor.active_alerts()
        recording = monitor.recording
        _, rec_count = monitor.record_info

        GUT = 20
        row_h = 16
        header_h = 46
        visible = frames[-10:]
        n = max(2, len(visible))
        panel_w = int(min(320, max(258, w * 0.3)))
        panel_h = header_h + n * row_h + 10
        panel_x = GUT
        panel_y = h - 64 - panel_h

        card = self._glass_card((panel_w, panel_h))
        card.blit(self.font_header.render("CAN SNIFFER", True, self.C_TEXT_MUTED), (16, 12))

        spoofs = monitor.spoof_count
        if spoofs:
            t = self.font_small.render(f"⚠ {spoofs} injected", True, (255, 120, 120))
            card.blit(t, (panel_w - t.get_width() - 16, 13))

        if recording:
            blink = (pygame.time.get_ticks() // 500) % 2 == 0
            pygame.draw.circle(card, (236, 44, 50) if blink else (110, 22, 26), (22, 34), 5)
            card.blit(self.font_small.render(f"REC  {rec_count}", True, (236, 128, 128)), (34, 28))
        else:
            card.blit(self.font_small.render("[R] kaydı başlat", True, self.C_TEXT_MUTED), (16, 28))

        y0 = header_h + 2
        tag_cols = {"SPOOF": (255, 96, 96), "UDS": self.C_ACCENT}
        for i, (ts, direction, arb_id, data, tag) in enumerate(visible):
            y = y0 + i * row_h
            dir_col = self.C_ACCENT if direction == "RX" else (120, 220, 120)
            card.blit(self.font_body.render(f"{direction} {arb_id:03X}#{data.hex().upper()}", True, dir_col), (16, y))
            if tag in tag_cols:
                t = self.font_small.render(tag, True, tag_cols[tag])
                card.blit(t, (panel_w - t.get_width() - 16, y + 1))

        if not frames:
            card.blit(self.font_small.render("dış frame bekleniyor…", True, self.C_TEXT_MUTED), (16, y0 + 4))

        surface.blit(card, (panel_x, panel_y))

        # IDS injection banner — placed below the chip row, blinking
        if alerts and (pygame.time.get_ticks() // 300) % 2 == 0:
            h1 = int(min(188, max(158, h * 0.2)))
            h2 = int(min(62, max(52, h * 0.065)))
            banner_y = 20 + h1 + 12 + h2 + 12 + 28 + 12
            ids = " ".join(f"0x{i:03X}" for i in alerts)
            t = self.font_header.render(f"⚠  CAN INJECTION  —  {ids}", True, (255, 255, 255))
            pad = 18
            bw, bh = t.get_width() + pad * 2, t.get_height() + 14
            banner = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.rect(banner, (208, 28, 36, 240), banner.get_rect(), border_radius=11)
            pygame.draw.rect(banner, (255, 130, 130), banner.get_rect(), 2, border_radius=11)
            banner.blit(t, (pad, 7))
            surface.blit(banner, ((w - bw) // 2, banner_y))
