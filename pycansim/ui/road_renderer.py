"""
Road Renderer for PyCanSim.
Scrolling asphalt with grain texture, edge lines, dashed center lane and
speed-synced roadside reflector posts for a strong sense of motion.
"""

import random
import pygame
from ..core.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLOR_ASPHALT,
    COLOR_ROAD_EDGE,
    COLOR_ROAD_MARKING,
)


class RoadRenderer:
    """Renders an animated road that scales with the window."""

    C_GRASS_DARK = (14, 20, 16)
    C_GRASS = (20, 30, 22)
    C_SHOULDER = (40, 44, 52)
    C_ASPHALT_HI = (40, 43, 50)
    C_POST = (210, 214, 222)
    C_POST_REFLECT = (255, 92, 70)

    def __init__(self, width: int = WINDOW_WIDTH, height: int = WINDOW_HEIGHT):
        self.dash_offset = 0.0
        self.post_offset = 0.0
        self.dash_length = 54
        self.dash_gap = 40
        self.cycle_length = self.dash_length + self.dash_gap
        self.post_cycle = 150
        self._grain = None
        self._grain_h = 0
        self.resize(width, height)

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.center_x = width // 2
        road_w = max(240, min(int(width * 0.5), 520))
        self.road_left = self.center_x - road_w // 2
        self.road_right = self.center_x + road_w // 2
        self.lane_x = (
            self.road_left + road_w // 4,   # not drawn, kept for reference
            self.center_x,
            self.road_right - road_w // 4,
        )
        self._build_grain(road_w, height)

    def _build_grain(self, road_w: int, height: int):
        """Pre-render a tileable asphalt grain strip so we don't rebuild per frame."""
        h = height + 4
        strip = pygame.Surface((road_w, h), pygame.SRCALPHA)
        rng = random.Random(1337)
        for _ in range(int(road_w * h * 0.012)):
            x = rng.randint(0, road_w - 1)
            y = rng.randint(0, h - 1)
            shade = rng.randint(-14, 16)
            a = rng.randint(30, 70)
            col = (
                max(0, min(255, COLOR_ASPHALT[0] + shade)),
                max(0, min(255, COLOR_ASPHALT[1] + shade)),
                max(0, min(255, COLOR_ASPHALT[2] + shade)),
                a,
            )
            strip.set_at((x, y), col)
        self._grain = strip
        self._grain_h = h

    def update_and_render(self, surface: pygame.Surface, speed_kmh: float, dt: float):
        scroll = speed_kmh * 5.6
        self.dash_offset = (self.dash_offset + scroll * dt) % self.cycle_length
        self.post_offset = (self.post_offset + scroll * dt) % self.post_cycle

        road_w = self.road_right - self.road_left

        # Grass / verge background
        surface.fill(self.C_GRASS_DARK)
        verge = pygame.Rect(0, 0, self.width, self.height)
        pygame.draw.rect(surface, self.C_GRASS, verge)

        # Shoulder bands just outside the asphalt
        pygame.draw.rect(surface, self.C_SHOULDER,
                         (self.road_left - 14, 0, 14, self.height))
        pygame.draw.rect(surface, self.C_SHOULDER,
                         (self.road_right, 0, 14, self.height))

        # Asphalt
        road_rect = pygame.Rect(self.road_left, 0, road_w, self.height)
        pygame.draw.rect(surface, COLOR_ASPHALT, road_rect)

        # Scrolling grain texture (two tiles for seamless wrap)
        if self._grain is not None:
            y0 = (self.dash_offset * 1.0) % self._grain_h - self._grain_h
            y = y0
            while y < self.height:
                surface.blit(self._grain, (self.road_left, int(y)))
                y += self._grain_h

        # Subtle centre sheen
        sheen = pygame.Surface((road_w, self.height), pygame.SRCALPHA)
        sw = max(40, road_w // 3)
        pygame.draw.rect(sheen, (*self.C_ASPHALT_HI, 40),
                         (road_w // 2 - sw // 2, 0, sw, self.height))
        surface.blit(sheen, (self.road_left, 0))

        # Solid edge lines
        edge_w = 6
        pygame.draw.line(surface, COLOR_ROAD_EDGE,
                         (self.road_left + 12, 0), (self.road_left + 12, self.height), edge_w)
        pygame.draw.line(surface, COLOR_ROAD_EDGE,
                         (self.road_right - 12, 0), (self.road_right - 12, self.height), edge_w)

        # Dashed centre lane (with soft glow)
        y = -self.cycle_length + self.dash_offset
        dash_w = 9
        while y < self.height + self.cycle_length:
            top = max(0.0, y)
            bottom = min(y + self.dash_length, float(self.height))
            if bottom > 0 and bottom > top:
                pygame.draw.line(surface, COLOR_ROAD_MARKING,
                                 (self.center_x, top), (self.center_x, bottom), dash_w)
            y += self.cycle_length

        # Roadside reflector posts — strong motion cue
        self._draw_posts(surface)

        # Vignette top & bottom to frame the HUD
        vignette = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        band = max(60, self.height // 9)
        for i in range(band):
            a = int(150 * (1 - i / band))
            pygame.draw.line(vignette, (0, 0, 0, a), (0, i), (self.width, i))
            pygame.draw.line(vignette, (0, 0, 0, a),
                             (0, self.height - 1 - i), (self.width, self.height - 1 - i))
        surface.blit(vignette, (0, 0))

    def _draw_posts(self, surface: pygame.Surface):
        y = -self.post_cycle + self.post_offset
        pw, ph = 5, 20
        while y < self.height + self.post_cycle:
            if 0 < y < self.height:
                for px in (self.road_left - 22, self.road_right + 17):
                    pygame.draw.rect(surface, self.C_POST, (px, int(y), pw, ph), border_radius=2)
                    pygame.draw.rect(surface, self.C_POST_REFLECT, (px, int(y), pw, 6), border_radius=2)
            y += self.post_cycle
