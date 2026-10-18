"""
PyCanSim Constants: Window dimensions, Colors, CAN IDs, and Protocol Bitmasks.
"""

# Window configuration
WINDOW_WIDTH = 860
WINDOW_HEIGHT = 920
MIN_WINDOW_WIDTH = 640
MIN_WINDOW_HEIGHT = 700
FPS = 60

# CAN IDs
CAN_ID_SPEED_BRAKE = 0x110  # 20ms period / event
CAN_ID_DOORS       = 0x280  # 100ms period / event
CAN_ID_LIGHTS      = 0x290  # 50ms period / event
CAN_ID_ENGINE      = 0x0C8  # 10ms period  – RPM & throttle position
CAN_ID_TEMP_FUEL   = 0x3B0  # 200ms period – coolant temp & fuel level
CAN_ID_STEER_BAT   = 0x2B0  # 50ms period  – steering angle & battery voltage

# CAN Protocol Constants
MAX_SPEED_KMH   = 160.0
ACCEL_RATE      = 40.0    # km/h per second on W
DECEL_RATE      = 120.0   # km/h per second on S (Brake)
COAST_RATE      = 15.0    # km/h per second natural slowdown when releasing W
MAX_RPM         = 7000.0  # Maximum engine RPM
IDLE_RPM        = 850.0   # Idle RPM when engine is running
MAX_COOLANT_TEMP = 120.0  # °C maximum coolant temperature
NORMAL_COOLANT_TEMP = 90.0  # °C normal operating temperature

# Door Bitmasks (0x280 Byte 0)
DOOR_FL_BIT = 0x01  # Bit 0: Front Left
DOOR_FR_BIT = 0x02  # Bit 1: Front Right
DOOR_RL_BIT = 0x04  # Bit 2: Rear Left
DOOR_RR_BIT = 0x08  # Bit 3: Rear Right

# Signal Modes (0x290 Byte 0)
SIGNAL_OFF    = 0x00
SIGNAL_LEFT   = 0x01
SIGNAL_RIGHT  = 0x02
SIGNAL_HAZARD = 0x03

# Color Palette (RGB & RGBA tuples)
COLOR_ASPHALT       = (28, 30, 36)       # Pavement
COLOR_SHOULDER      = (16, 22, 18)       # Dark roadside
COLOR_ROAD_EDGE     = (232, 228, 214)    # Warm edge line
COLOR_ROAD_MARKING  = (236, 214, 92)     # Lane dash gold
COLOR_CAR_BODY      = (12, 14, 20)       # #0C0E14 Interior dark body fill
COLOR_CAR_OUTLINE   = (0, 229, 255)      # #00E5FF Cyan glowing body outline
COLOR_CAR_WINDOW    = (0, 150, 200, 180) # Semi-transparent window tint
COLOR_DOOR_CLOSED   = (0, 229, 255)      # Matches cyan body line
COLOR_DOOR_OPEN     = (255, 45, 85)       # #FF2D55 Red alert warning line
COLOR_HEADLIGHT_LED = (255, 255, 255)    # #FFFFFF Bright white LED fixture
COLOR_HEADLIGHT_BEAM= (255, 245, 200, 45) # Soft transparent light cone
COLOR_SIGNAL_ON     = (255, 153, 0)      # #FF9900 Vivid orange LED
COLOR_SIGNAL_OFF    = (60, 40, 0)        # Dim dark orange when inactive
COLOR_BRAKE_ON      = (255, 20, 20)      # #FF1414 Bright glowing red stop light
COLOR_BRAKE_OFF     = (80, 10, 10)       # Dim dark red stop light
COLOR_HUD_TEXT      = (240, 240, 240)    # White text
COLOR_HUD_BG        = (10, 12, 18, 200)  # Dark glass panel for status overlay
