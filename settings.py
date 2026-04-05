WIDTH  = 1400
HEIGHT = 900
FPS    = 60
TITLE  = "Fabled"

# ── Colours ──────────────────────────────────────────────────────────────────
BG              = (20, 20, 25)
PANEL           = (38, 38, 46)
PANEL_ALT       = (50, 50, 60)
PANEL_HIGHLIGHT = (65, 65, 80)
BORDER          = (90, 90, 110)
BORDER_ACTIVE   = (170, 170, 210)
TEXT            = (235, 235, 245)
TEXT_DIM        = (155, 155, 175)
TEXT_MUTED      = (110, 110, 130)
RED             = (205, 85, 85)
RED_DARK        = (130, 45, 45)
GREEN           = (85, 195, 115)
GREEN_DARK      = (45, 120, 65)
YELLOW          = (215, 195, 80)
BLUE            = (95, 135, 215)
BLUE_DARK       = (55, 85, 155)
ORANGE          = (215, 145, 75)
PURPLE          = (155, 95, 205)
CYAN            = (80, 195, 195)

# ── Slots ─────────────────────────────────────────────────────────────────────
SLOT_FRONT      = "front"
SLOT_BACK_LEFT  = "back_left"
SLOT_BACK_RIGHT = "back_right"
SLOTS           = [SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT]

# Clockwise resolution order: front first, then back-right, then back-left
CLOCKWISE_ORDER = [SLOT_FRONT, SLOT_BACK_RIGHT, SLOT_BACK_LEFT]

SLOT_LABELS = {
    SLOT_FRONT:      "Front",
    SLOT_BACK_LEFT:  "Back Left",
    SLOT_BACK_RIGHT: "Back Right",
}

# ── Status colours ────────────────────────────────────────────────────────────
STATUS_COLORS = {
    "burn":      (210, 100, 55),
    "root":      (95,  175, 75),
    "shock":     (175, 175, 55),
    "weaken":    (155, 95,  155),
    "expose":    (195, 115, 75),
    "guard":     (75,  135, 200),
    "spotlight": (215, 195, 75),
    "taunt":     (185, 105, 185),
    "no_heal":   (180, 60,  60),
    "dormant":   (100, 100, 120),
}
