"""
Road Renderer for PyCanSim.
Asphalt, shoulders, and speed-synced lane markings that follow window size.
"""

import pygame
from ..core.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    COLOR_ASPHALT,
    COLOR_ROAD_EDGE,
    COLOR_ROAD_MARKING,
    COLOR_SHOULDER,
)


class RoadRenderer:
    """Renders an animated road that scales with the window."""

    def __init__(self, width: int = WINDOW_WIDTH, height: int = WINDOW_HEIGHT):
        self.dash_offset = 0.0
        self.dash_length = 52
        self.dash_gap = 38
        self.cycle_length = self.dash_length + self.dash_gap
        self.resize(width, height)

    def resize(self, width: int, height: int):
        self.width = width
        self.height = height
        self.center_x = width // 2
        road_w = max(220, min(int(width * 0.46), 480))
        self.road_left = self.center_x - road_w // 2
        self.road_right = self.center_x + road_w // 2

    def update_and_render(self, surface: pygame.Surface, speed_kmh: float, dt: float):
        scroll_speed = speed_kmh * 5.4
        self.dash_offset = (self.dash_offset + scroll_speed * dt) % self.cycle_length

        surface.fill(COLOR_SHOULDER)

        # Soft roadside gradient strips
        shoulder = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(
            shoulder,
            (22, 32, 24, 90),
            (0, 0, self.road_left - 8, self.height),
        )
        pygame.draw.rect(
            shoulder,
            (22, 32, 24, 90),
            (self.road_right + 8, 0, self.width - self.road_right, self.height),
        )
        surface.blit(shoulder, (0, 0))

        road_rect = pygame.Rect(
            self.road_left,
            0,
            self.road_right - self.road_left,
            self.height,
        )
        pygame.draw.rect(surface, COLOR_ASPHALT, road_rect)

        # Subtle center wear
        wear_w = max(18, (self.road_right - self.road_left) // 8)
        pygame.draw.rect(
            surface,
            (34, 36, 42),
            (self.center_x - wear_w // 2, 0, wear_w, self.height),
        )

        edge_w = 5
        pygame.draw.line(
            surface, COLOR_ROAD_EDGE,
            (self.road_left + 10, 0), (self.road_left + 10, self.height), edge_w,
        )
        pygame.draw.line(
            surface, COLOR_ROAD_EDGE,
            (self.road_right - 10, 0), (self.road_right - 10, self.height), edge_w,
        )

        y = -self.cycle_length + self.dash_offset
        dash_w = 7
        while y < self.height + self.cycle_length:
            dash_bottom = min(y + self.dash_length, float(self.height))
            if dash_bottom > 0:
                pygame.draw.line(
                    surface,
                    COLOR_ROAD_MARKING,
                    (self.center_x, max(0.0, y)),
                    (self.center_x, dash_bottom),
                    dash_w,
                )
            y += self.cycle_length

        # Soft vignette so HUD sits on a darker frame
        vignette = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        band = max(48, self.height // 12)
        pygame.draw.rect(vignette, (0, 0, 0, 70), (0, 0, self.width, band))
        pygame.draw.rect(vignette, (0, 0, 0, 90), (0, self.height - band, self.width, band))
        surface.blit(vignette, (0, 0))
