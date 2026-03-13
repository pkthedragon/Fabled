"""
ui.py – all drawing functions for the Fabled prototype.
Pure rendering; no game-state mutations.
"""
import re
import pygame
from settings import *
from models import CombatantState, TeamState, BattleState


# ─────────────────────────────────────────────────────────────────────────────
# CLASS COLORS  (subtle tints for small adventurer cards/list items)
# ─────────────────────────────────────────────────────────────────────────────

CLASS_COLORS = {
    "Fighter": (52, 36, 36),
    "Rogue":   (34, 40, 40),
    "Warden":  (32, 40, 56),
    "Mage":    (48, 34, 56),
    "Ranger":  (32, 50, 36),
    "Cleric":  (50, 46, 32),
    "Noble":   (38, 40, 58),
    "Warlock": (46, 30, 52),
}

# Text accent colors per class (for the class label)
CLASS_TEXT_COLORS = {
    "Fighter": (210, 130, 110),
    "Rogue":   (130, 190, 160),
    "Warden":  (110, 165, 220),
    "Mage":    (185, 130, 220),
    "Ranger":  (120, 200, 120),
    "Cleric":  (220, 200, 110),
    "Noble":   (145, 165, 230),
    "Warlock": (185, 110, 210),
}

# Ability / item type label colors
TYPE_ACTIVE_COL  = (174, 170, 160)  # "Active"  label — muted warm grey
TYPE_PASSIVE_COL = (158, 165, 192)  # "Passive" label — muted steel blue

# Class type suffixes: M = Melee, R = Ranged, X = Mixed
_CLASS_TYPE_SUFFIX = {
    "Fighter": "(M)", "Rogue": "(M)", "Warden": "(M)",
    "Ranger":  "(R)", "Mage":  "(R)", "Cleric": "(R)",
    "Noble":   "(X)", "Warlock": "(X)",
}

def cls_label(cls):
    """Return e.g. 'Warden (M)', 'Mage (R)', 'Warlock (X)'."""
    suffix = _CLASS_TYPE_SUFFIX.get(cls, "")
    return f"{cls} {suffix}" if suffix else cls


# ─────────────────────────────────────────────────────────────────────────────
# NAME HELPERS
# ─────────────────────────────────────────────────────────────────────────────

# Explicit overrides for names that don't fit the general rules
_SHORT_NAME_OVERRIDES = {
    "Risa Redcloak": "Risa",
}

# Single-word prefixes that precede the actual first name
_TITLE_PREFIXES = {
    "sir", "dame", "lord", "lady", "prince", "princess", "king", "queen",
    "little", "lucky", "ashen", "matchstick", "snowkissed", "wench", "sea",
    "witch-hunter",
}


def short_name(full_name: str) -> str:
    """Return a short display name by stripping titles and descriptors.

    Rules (first match wins for each pass):
    1. Explicit override table.
    2. Strip everything after ", ".
    3. Strip " the ..." or " of ..." suffix (earliest occurrence).
    4. Strip Roman-numeral suffix.
    5. Strip known single-word title prefixes from the front.
    """
    if full_name in _SHORT_NAME_OVERRIDES:
        return _SHORT_NAME_OVERRIDES[full_name]

    name = full_name

    # Rule 2: comma suffix
    if ", " in name:
        name = name.split(", ")[0]

    # Rule 3: " the " / " of " suffix — pick the earliest
    lo = name.lower()
    min_idx = len(name)
    for sep in (" the ", " of "):
        idx = lo.find(sep)
        if idx != -1 and idx < min_idx:
            min_idx = idx
    if min_idx < len(name):
        name = name[:min_idx]

    # Rule 4: trailing Roman numeral
    name = re.sub(r'\s+[IVX]{1,4}$', '', name).strip()

    # Rule 5: leading title prefixes (loop to handle compound titles like "Sea Wench")
    words = name.split()
    while len(words) > 1 and words[0].lower() in _TITLE_PREFIXES:
        words = words[1:]
    name = " ".join(words)

    return name


# ─────────────────────────────────────────────────────────────────────────────
# FONT CACHE
# ─────────────────────────────────────────────────────────────────────────────
_font_cache: dict = {}

def font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        try:
            _font_cache[size] = pygame.font.SysFont("consolas", size)
        except Exception:
            _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


# ─────────────────────────────────────────────────────────────────────────────
# PRIMITIVES
# ─────────────────────────────────────────────────────────────────────────────

def draw_text(surf, text, size, color, x, y, center=False, right=False):
    f = font(size)
    s = f.render(str(text), True, color)
    r = s.get_rect()
    if center:
        r.center = (x, y)
    elif right:
        r.midright = (x, y)
    else:
        r.topleft = (x, y)
    surf.blit(s, r)
    return r


def draw_rect_border(surf, rect, fill, border_color=BORDER, width=2):
    pygame.draw.rect(surf, fill, rect, border_radius=4)
    pygame.draw.rect(surf, border_color, rect, width, border_radius=4)


def draw_button(surf, rect, label, mouse_pos,
                normal=PANEL, hover=PANEL_HIGHLIGHT, border=BORDER_ACTIVE,
                text_color=TEXT, size=18, disabled=False):
    """Draw a button; return True if hovered."""
    if disabled:
        draw_rect_border(surf, rect, (45, 45, 50), (80, 80, 90))
        draw_text(surf, label, size, TEXT_MUTED, rect.centerx, rect.centery,
                  center=True)
        return False
    hov = rect.collidepoint(mouse_pos)
    fill = hover if hov else normal
    draw_rect_border(surf, rect, fill, border)
    draw_text(surf, label, size, text_color, rect.centerx, rect.centery,
              center=True)
    return hov


def draw_panel(surf, rect, title=None, title_size=20):
    draw_rect_border(surf, rect, PANEL)
    if title:
        draw_text(surf, title, title_size, TEXT_DIM, rect.x + 10, rect.y + 8)


# ─────────────────────────────────────────────────────────────────────────────
# UNIT BOX
# ─────────────────────────────────────────────────────────────────────────────

STATUS_TOOLTIPS = {
    "burn":      "Burn: takes 10% max HP damage at end of each round.",
    "root":      "Root: cannot perform the Swap action.",
    "shock":     "Shock: ranged units must recharge after 2 ability uses instead of 3.",
    "weaken":    "Weaken: deals 20% less damage.",
    "expose":    "Expose: takes 20% more damage.",
    "guard":     "Guard: takes 20% less damage.",
    "spotlight": "Spotlight: can be targeted by melee abilities in the backline.",
    "no_heal":   "No Heal: cannot receive any healing.",
    "dormant":   "Dormant: cannot act or be targeted.",
    "reflecting_pool": "Reflecting Pool: reflects 10-20% of incoming damage back to attacker.",
    "buff_nullify":    "Buff Nullify: incoming stat buffs have no effect.",
    "burn_immune":     "Burn Immune: cannot receive the Burn status.",
    # Class type tooltips
    "Fighter": "Fighters are melee.",
    "Rogue":   "Rogues are melee.",
    "Warden":  "Wardens are melee.",
    "Ranger":  "Rangers are ranged.",
    "Mage":    "Mages are ranged.",
    "Cleric":  "Clerics are ranged.",
    "Noble":   "Nobles are mixed; FL melee & BL ranged.",
    "Warlock": "Warlocks are mixed; FL melee & BL ranged.",
}

# Maps word variants found in description text → canonical status key
STATUS_NAME_MAP = {
    "burn": "burn", "burns": "burn", "burned": "burn", "burning": "burn",
    "root": "root", "roots": "root", "rooted": "root",
    "shock": "shock", "shocks": "shock", "shocked": "shock",
    "weaken": "weaken", "weakens": "weaken", "weakened": "weaken",
    "expose": "expose", "exposes": "expose", "exposed": "expose",
    "guard": "guard", "guards": "guard", "guarded": "guard",
    "spotlight": "spotlight", "spotlighted": "spotlight",
    "dormant": "dormant",
}


def _draw_rich_line(surf, text, size, default_color, x, y, status_rects_out=None):
    """Draw a line of text word-by-word, coloring status keywords in their STATUS_COLORS.

    If status_rects_out is a list, appends (pygame.Rect, status_key) for each
    colored word so callers can show tooltips on hover.
    """
    f = font(size)
    space_w = f.size(" ")[0]
    cx = x
    for word in text.split(" "):
        if not word:
            cx += space_w
            continue
        # Strip leading/trailing punctuation for keyword lookup
        clean = word.strip(".,;:()[]!?\"'").lower()
        key = STATUS_NAME_MAP.get(clean)
        color = STATUS_COLORS.get(key, default_color) if key else default_color
        s = f.render(word, True, color)
        r = s.get_rect(topleft=(cx, y))
        surf.blit(s, r)
        if key is not None and status_rects_out is not None:
            status_rects_out.append((r, key))
        cx += r.width + space_w


def _draw_scroll_arrows(surf, view_rect, scroll, max_scroll):
    """Draw ↑/↓ arrows at top/bottom right of a scrollable viewport."""
    if max_scroll <= 0:
        return
    x = view_rect.right - 16
    if scroll > 0:
        draw_text(surf, "↑", 14, TEXT_MUTED, x, view_rect.top + 2)
    if scroll < max_scroll:
        draw_text(surf, "↓", 14, TEXT_MUTED, x, view_rect.bottom - 16)


def draw_status_tooltip(surf, kind: str, tip_x: int, tip_y: int):
    """Draw a small floating tooltip box for a status condition near (tip_x, tip_y)."""
    text = STATUS_TOOLTIPS.get(kind, kind.replace("_", " "))
    f = font(13)
    tw = f.size(text)[0] + 18
    th = 24
    x = min(tip_x + 4, WIDTH - tw - 4)
    y = max(4, tip_y - th - 6)
    tip_rect = pygame.Rect(x, y, tw, th)
    pygame.draw.rect(surf, (20, 22, 30), tip_rect, border_radius=4)
    pygame.draw.rect(surf, BORDER_ACTIVE, tip_rect, 1, border_radius=4)
    draw_text(surf, text, 13, TEXT, x + 9, y + 5)


INTRO_TEXTS = [
    "Welcome to Fantasia! You're a wealthy, but cripplingly lazy, magnate with a fondness for collecting rare artifacts.",
    "One such artifact, the Dragon Jewel, would be perfect for your collection. Unfortunately, the Dragon Jewel was shattered into nine pieces, scattered across the land, and you only have one.",
    "Over the years, you've managed to track the shards down, but you're not really the adventuring type. You don't have deep pocketbooks for nothing though; there's plenty of adventurers in Fantasia looking to take on a dangerous quest for a quick buck.",
    "No time to waste! Head to the Tavern to form a party and start gathering the shards. The Dragon Jewel will sitting pretty in your foyer in no time!",
]


def draw_intro_popup(surf, visible_count: int, mouse_pos):
    """Draw the sequential intro story popup.

    visible_count: how many text sections are currently shown (1–4).
    Returns the 'Let's Go' button rect when visible_count == 4, else None.
    """
    box_w   = 680
    content_w = box_w - 48
    text_size = 17
    line_h  = 25
    sec_gap = 18   # vertical gap between sections
    pad     = 28   # top/bottom inner padding
    footer_h = 38  # space reserved at the bottom for hint/button

    f = font(text_size)

    # Word-wrap all sections (for stable box size) but only render visible ones
    all_wrapped = []
    for text in INTRO_TEXTS:
        words = text.split()
        lines, line = [], ""
        for word in words:
            test = (line + " " + word).strip()
            if f.size(test)[0] <= content_w:
                line = test
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        all_wrapped.append(lines)

    wrapped_sections = all_wrapped[:visible_count]

    # Box height always sized for all 4 sections
    total_text_h = sum(len(lines) * line_h for lines in all_wrapped)
    total_text_h += (len(INTRO_TEXTS) - 1) * sec_gap
    box_h = pad + total_text_h + pad + footer_h

    cx, cy = WIDTH // 2, HEIGHT // 2
    box_rect = pygame.Rect(cx - box_w // 2, cy - box_h // 2, box_w, box_h)

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 165))
    surf.blit(overlay, (0, 0))

    draw_rect_border(surf, box_rect, (28, 30, 42), BORDER_ACTIVE, 2)

    ty = box_rect.y + pad
    for si, lines in enumerate(wrapped_sections):
        for ln in lines:
            draw_text(surf, ln, text_size, TEXT, cx, ty, center=True)
            ty += line_h
        if si < visible_count - 1:
            ty += sec_gap

    lets_go_btn = None
    if visible_count >= 4:
        lets_go_btn = pygame.Rect(cx - 100, box_rect.bottom - footer_h + 4, 200, 30)
        draw_button(surf, lets_go_btn, "Let's Go!", mouse_pos, size=16,
                    normal=(40, 90, 50), hover=(55, 120, 65))
    else:
        draw_text(surf, "Click anywhere to continue", 13, TEXT_MUTED,
                  cx, box_rect.bottom - footer_h + 12, center=True)

    return lets_go_btn


def draw_tutorial_popup(surf, text: str):
    """Draw a centered tutorial popup overlay. Click anywhere to dismiss."""
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 155))
    surf.blit(overlay, (0, 0))

    cx, cy = WIDTH // 2, HEIGHT // 2
    max_w = 580
    f = font(18)

    # Word-wrap text
    words = text.split()
    lines = []
    line = ""
    for word in words:
        test = (line + " " + word).strip()
        if f.size(test)[0] <= max_w - 40:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)

    line_h = 28
    pad = 26
    box_h = pad * 2 + len(lines) * line_h + 30
    box_w = max_w
    box_rect = pygame.Rect(cx - box_w // 2, cy - box_h // 2, box_w, box_h)

    draw_rect_border(surf, box_rect, (28, 30, 42), BORDER_ACTIVE, 2)

    ty = box_rect.y + pad
    for ln in lines:
        draw_text(surf, ln, 18, TEXT, cx, ty, center=True)
        ty += line_h

    draw_text(surf, "Click anywhere to continue", 13, TEXT_MUTED, cx, box_rect.bottom - 20, center=True)


def draw_unit_box(surf, rect, unit: CombatantState, selected=False,
                  is_target=False, has_queued=False,
                  is_enemy=False, mouse_pos=None, show_slot=True,
                  status_rects_out=None):
    """Draw a single adventurer's info box.

    selected  = this unit is the current actor being assigned an action (gold)
    is_target = this unit is a valid target for the current action (orange)
    has_queued = this unit already has an action queued (green dot)
    """
    if unit is None:
        draw_rect_border(surf, rect, PANEL_ALT, BORDER)
        draw_text(surf, "[empty]", 16, TEXT_MUTED, rect.centerx, rect.centery,
                  center=True)
        return

    # Background + border — each state has a distinct colour
    if unit.ko:
        fill = (35, 25, 25)
        bord = RED_DARK
        bord_w = 2
    elif selected:
        fill = (58, 52, 22)          # warm gold tint
        bord = (245, 210, 40)        # bright gold
        bord_w = 3
    elif is_target:
        fill = (52, 40, 20)          # orange tint
        bord = (235, 140, 30)        # orange
        bord_w = 3
    elif is_enemy:
        fill = (42, 38, 46)
        bord = BORDER
        bord_w = 2
    else:
        fill = PANEL_ALT
        bord = BORDER
        bord_w = 2

    draw_rect_border(surf, rect, fill, bord, bord_w)

    # Green dot when action already queued
    if has_queued and not unit.ko:
        pygame.draw.circle(surf, GREEN, (rect.right - 10, rect.y + 10), 5)

    x, y = rect.x + 8, rect.y + 6
    w = rect.width - 16

    # Slot label
    if show_slot:
        slot_lbl = SLOT_LABELS.get(unit.slot, unit.slot)
        draw_text(surf, slot_lbl, 14, TEXT_MUTED, rect.right - 8,
                  rect.y + 8, right=True)

    # Name (short form in unit boxes; full name shown in detail panels)
    name_color = RED if unit.ko else (TEXT_DIM if unit.untargetable else TEXT)
    draw_text(surf, short_name(unit.name), 18, name_color, x, y)
    y += 22

    # Class
    _clsr = draw_text(surf, cls_label(unit.cls), 14, TEXT_MUTED, x, y)
    if status_rects_out is not None:
        status_rects_out.append((_clsr, unit.cls))
    y += 18

    if unit.ko:
        draw_text(surf, "KO'd", 20, RED, rect.centerx, rect.centery, center=True)
        return

    # HP bar
    bar_w = w
    bar_h = 10
    bar_rect = pygame.Rect(x, y, bar_w, bar_h)
    pygame.draw.rect(surf, (50, 20, 20), bar_rect, border_radius=3)
    if unit.max_hp > 0:
        ratio = max(0, unit.hp / unit.max_hp)
        hp_color = GREEN_DARK if ratio > 0.5 else (ORANGE if ratio > 0.25 else RED_DARK)
        filled = pygame.Rect(x, y, int(bar_w * ratio), bar_h)
        pygame.draw.rect(surf, hp_color, filled, border_radius=3)
    pygame.draw.rect(surf, BORDER, bar_rect, 1, border_radius=3)
    draw_text(surf, f"{unit.hp}/{unit.max_hp}", 13, TEXT,
              x + bar_w // 2, y - 1, center=True)
    y += 14

    # Stats — green if buffed, red if debuffed, dim if neutral
    sx = x
    for stat, abbrev in (("attack", "ATK"), ("defense", "DEF"), ("speed", "SPD")):
        has_buff   = any(b.duration > 0 and b.stat == stat for b in unit.buffs)
        has_debuff = any(d.duration > 0 and d.stat == stat for d in unit.debuffs)
        val_color  = GREEN if has_buff else (RED if has_debuff else TEXT_DIM)
        r = draw_text(surf, f"{abbrev} {unit.get_stat(stat)}", 13, val_color, sx, y)
        sx = r.right + 6
    y += 16

    # Active stat buffs/debuffs (highest of each type applies)
    _stat_abbrevs = [("attack", "ATK"), ("defense", "DEF"), ("speed", "SPD")]
    mod_parts = []
    for stat, abbrev in _stat_abbrevs:
        best_b = max((b for b in unit.buffs if b.stat == stat and b.duration > 0),
                     key=lambda b: b.amount, default=None)
        best_d = max((d for d in unit.debuffs if d.stat == stat and d.duration > 0),
                     key=lambda d: d.amount, default=None)
        if best_b:
            mod_parts.append((f"{abbrev}+{best_b.amount}({best_b.duration}r)", GREEN))
        if best_d:
            mod_parts.append((f"{abbrev}-{best_d.amount}({best_d.duration}r)", RED))
    if mod_parts:
        sx = x
        for txt, col in mod_parts:
            r = draw_text(surf, txt, 11, col, sx, y)
            sx = r.right + 3
            if sx > rect.right - 4:
                break
        y += 13

    # Malice (Warlock resource)
    if unit.cls == "Warlock":
        malice = unit.ability_charges.get("malice", 0)
        malice_cap = unit.ability_charges.get("malice_cap", 6)
        draw_text(surf, f"Malice {malice}/{malice_cap}", 12, (170, 120, 220), x, y)
        y += 14

    # Statuses
    if unit.statuses:
        sx = x
        for s in unit.statuses:
            col = STATUS_COLORS.get(s.kind, TEXT_MUTED)
            r = draw_text(surf, f"{s.kind}({s.duration})", 12, col, sx, y)
            if status_rects_out is not None:
                status_rects_out.append((r, s.kind))
            sx = r.right + 4
            if sx > rect.right - 8:
                break
        y += 14

    # Recharge indicator
    if unit.must_recharge:
        draw_text(surf, "RECHARGE", 13, YELLOW, x, y)
    elif hasattr(unit, 'ranged_uses') and (unit.role == "ranged" or (unit.role == "warlock" and unit.slot != SLOT_FRONT)):
        limit = 2 if unit.has_status("shock") else 3
        draw_text(surf, f"uses {unit.ranged_uses}/{limit}", 12, TEXT_MUTED, x, y)


# ─────────────────────────────────────────────────────────────────────────────
# FORMATION LAYOUT  (battle screen)
# ─────────────────────────────────────────────────────────────────────────────
#
# Hourglass / two-triangles formation:
#
#   P2  BL ──────────────── BR   (wide — "base" of P2 triangle)
#            P2 FRONT            (narrow center — tip of P2 triangle)
#            P1 FRONT            (narrow center — tip of P1 triangle)
#   P1  BL ──────────────── BR   (wide — "base" of P1 triangle)
#
# Panel regions:
#   Left ~570px: formation
#   Right: log (x=580) + action panel (x=995)

UNIT_W = 170
UNIT_H = 130

_FORM_LEFT  = 10   # x of back-left units
_FORM_RIGHT = 390  # x of back-right units
_FORM_MID   = 200  # x of frontline units (centered in formation area)

# P2 (opponent): backlines at top (aligned with log/action panel), frontline below
P2_BL_RECT    = pygame.Rect(_FORM_LEFT,  80,  UNIT_W, UNIT_H)
P2_BR_RECT    = pygame.Rect(_FORM_RIGHT, 80,  UNIT_W, UNIT_H)
P2_FRONT_RECT = pygame.Rect(_FORM_MID,  230, UNIT_W, UNIT_H)

# P1 (player): frontline at top of P1 area, backlines below
P1_FRONT_RECT = pygame.Rect(_FORM_MID,  380, UNIT_W, UNIT_H)
P1_BL_RECT    = pygame.Rect(_FORM_LEFT, 530, UNIT_W, UNIT_H)
P1_BR_RECT    = pygame.Rect(_FORM_RIGHT,530, UNIT_W, UNIT_H)

SLOT_RECTS_P1 = {
    SLOT_FRONT:      P1_FRONT_RECT,
    SLOT_BACK_LEFT:  P1_BL_RECT,
    SLOT_BACK_RIGHT: P1_BR_RECT,
}
SLOT_RECTS_P2 = {
    SLOT_FRONT:      P2_FRONT_RECT,
    SLOT_BACK_LEFT:  P2_BL_RECT,
    SLOT_BACK_RIGHT: P2_BR_RECT,
}

# Horizontal centre of the formation area for labels
_FORM_CX = (_FORM_LEFT + _FORM_RIGHT + UNIT_W) // 2


def draw_formation(surf, battle: BattleState,
                   selected_unit=None, valid_targets=None,
                   mouse_pos=(0, 0),
                   acting_player=None,
                   status_rects_out=None):
    """Draw both teams in hourglass formation."""
    valid_targets = valid_targets or []

    # Team labels flanking the formation
    draw_text(surf, battle.team2.player_name, 16, BLUE,  _FORM_CX, 68, center=True)
    draw_text(surf, battle.team1.player_name, 16, GREEN, _FORM_CX, 668, center=True)

    # Thin dividing line between the two frontlines
    mid_y = (P2_FRONT_RECT.bottom + P1_FRONT_RECT.top) // 2
    pygame.draw.line(surf, BORDER, (0, mid_y), (570, mid_y), 1)

    for slot, rect in SLOT_RECTS_P2.items():
        unit = battle.team2.get_slot(slot)
        is_tgt = unit in valid_targets if valid_targets else False
        is_sel = (unit == selected_unit and acting_player == 2)
        has_q  = (unit is not None and not unit.ko and unit.queued is not None)
        draw_unit_box(surf, rect, unit, selected=is_sel, is_target=is_tgt,
                      has_queued=has_q, is_enemy=True, mouse_pos=mouse_pos,
                      status_rects_out=status_rects_out)

    for slot, rect in SLOT_RECTS_P1.items():
        unit = battle.team1.get_slot(slot)
        # Prefer alive unit at this slot; fall back to KO'd unit for display
        actual_unit = (next((m for m in battle.team1.members if m.slot == slot and not m.ko), None)
                       or next((m for m in battle.team1.members if m.slot == slot), None))
        is_tgt = unit in valid_targets if valid_targets else False
        is_acting = (acting_player == 1 and unit == selected_unit)
        has_q  = (actual_unit is not None and not actual_unit.ko
                  and actual_unit.queued is not None)
        draw_unit_box(surf, rect, actual_unit, selected=is_acting, is_target=is_tgt,
                      has_queued=has_q, is_enemy=False, mouse_pos=mouse_pos,
                      status_rects_out=status_rects_out)


def formation_rect_for(unit: CombatantState, acting_player: int):
    """Return the pygame.Rect for a given unit's position on screen."""
    rects = SLOT_RECTS_P1 if acting_player == 1 else SLOT_RECTS_P2
    return rects.get(unit.slot)


# ─────────────────────────────────────────────────────────────────────────────
# BATTLE LOG
# ─────────────────────────────────────────────────────────────────────────────

LOG_RECT = pygame.Rect(580, 80, 400, 560)


def _log_color(line: str) -> tuple:
    """Return a colour for a log entry based on its content."""
    if line.startswith("\x01"):
        line = line[1:]
    if "───" in line:
        return (100, 130, 160)          # dim blue-grey separator
    lo = line.lower()
    if "ko'd" in lo or " ko" in lo or "defeated" in lo:
        return RED
    if "winner" in lo or "victory" in lo:
        return YELLOW
    if any(k in lo for k in ("damage", " hit", "strikes", "attacks", "dmg")):
        return ORANGE
    if any(k in lo for k in ("heal", "heals", "restored", "recovers", "+hp")):
        return GREEN
    if any(k in lo for k in ("round", "initiative")):
        return YELLOW
    if any(k in lo for k in ("burn", "root", "shock", "weaken", "expose",
                              "guard", "spotlight", "dormant")):
        return (210, 175, 90)           # warm yellow for status effects
    if any(k in lo for k in ("swap", "recharge", "skip", "misses", "immune")):
        return TEXT_MUTED
    return TEXT_DIM


def draw_log(surf, log: list, rect=LOG_RECT, scroll_offset: int = 0):
    draw_panel(surf, rect, "Battle Log", 16)
    line_h = 15
    max_w = rect.width - 18   # usable text width in pixels

    # Expand each log entry into wrapped display lines (line_text, color)
    display_lines = []
    for entry in log:
        col = _log_color(entry)
        if entry.startswith("\x01"):
            entry = entry[1:]
        wrapped = _wrap_text(entry, 13, max_w)
        if not wrapped:
            wrapped = [""]
        for i, wl in enumerate(wrapped):
            display_lines.append((wl, col if i == 0 else TEXT_MUTED))

    view_lines = (rect.height - 36) // line_h
    total = len(display_lines)
    # scroll_offset 0 = bottom; positive = scrolled up (in display lines)
    max_scroll = max(0, total - view_lines)
    scroll_offset = max(0, min(scroll_offset, max_scroll))
    start = max(0, total - view_lines - scroll_offset)
    visible = display_lines[start: start + view_lines]

    y = rect.y + 28
    for text, col in visible:
        if y + line_h > rect.bottom - 4:
            break
        draw_text(surf, text, 13, col, rect.x + 8, y)
        y += line_h

    # Scroll indicators
    if scroll_offset > 0:
        draw_text(surf, f"▲ {scroll_offset} older", 11, TEXT_MUTED,
                  rect.right - 8, rect.y + 28, right=True)
        draw_text(surf, "▼ newer  (wheel to scroll)", 11, TEXT_MUTED,
                  rect.right - 8, rect.bottom - 6, right=True)
    elif total > view_lines:
        draw_text(surf, "▲ wheel to scroll", 11, TEXT_MUTED,
                  rect.right - 8, rect.y + 28, right=True)


# ─────────────────────────────────────────────────────────────────────────────
# ACTION MENU
# ─────────────────────────────────────────────────────────────────────────────

ACTION_PANEL_RECT = pygame.Rect(995, 80, 390, 800)
BUTTON_H = 36
BUTTON_W = 360
BUTTON_X = 1005


def draw_action_menu(surf, mouse_pos, actor: CombatantState,
                     valid_abilities: list, swap_used: bool,
                     state_label: str = "") -> list:
    """
    Draw the action selection menu for one actor.
    Returns a list of (pygame.Rect, action_dict) tuples for click detection.
    """
    draw_panel(surf, ACTION_PANEL_RECT, f"Actions — {actor.name}", 18)

    buttons = []
    y = ACTION_PANEL_RECT.y + 40

    # State label
    draw_text(surf, state_label, 15, YELLOW, BUTTON_X, y)
    y += 22

    # Abilities
    for ability in valid_abilities:
        mode = ability.frontline if actor.slot == SLOT_FRONT else ability.backline
        if mode.unavailable:
            continue

        title = ability.name
        detail_lines = _mode_detail_lines(mode)
        wrapped = []
        for line in detail_lines[:2]:
            wrapped.extend(_wrap_text(line, 12, BUTTON_W - 20))
        wrapped = wrapped[:3]

        btn_h = 26 + len(wrapped) * 14
        rect = pygame.Rect(BUTTON_X, y, BUTTON_W, btn_h)
        hov = rect.collidepoint(mouse_pos)
        fill = PANEL_HIGHLIGHT if hov else PANEL_ALT
        draw_rect_border(surf, rect, fill, BORDER_ACTIVE)
        draw_text(surf, title, 15, TEXT, rect.x + 8, rect.y + 5)
        ty = rect.y + 22
        for ln in wrapped:
            draw_text(surf, ln, 12, TEXT_DIM, rect.x + 10, ty)
            ty += 14

        buttons.append((rect, {"type": "ability", "ability": ability, "target": None}))
        y += btn_h + 4

    # Item — hidden when unit must recharge (forced skip)
    item = actor.item
    if not item.passive and actor.item_uses_left > 0 and not actor.must_recharge:
        y += 6
        item_btn_h = 52
        rect = pygame.Rect(BUTTON_X, y, BUTTON_W, item_btn_h)
        hov = rect.collidepoint(mouse_pos)
        fill = PANEL_HIGHLIGHT if hov else (30, 50, 40)
        draw_rect_border(surf, rect, fill, BORDER_ACTIVE)
        draw_text(surf, f"Item: {item.name}", 15, TEXT, rect.x + 8, rect.y + 5)
        desc_lines = _wrap_text(item.description, 12, BUTTON_W - 16)
        for _li, _ln in enumerate(desc_lines[:2]):
            draw_text(surf, _ln, 12, TEXT_DIM, rect.x + 12, rect.y + 24 + _li * 14)
        buttons.append((rect, {"type": "item", "target": None}))
        y += item_btn_h + 4

    # Swap (once per turn; also blocked when unit must recharge)
    y += 6
    rect = pygame.Rect(BUTTON_X, y, BUTTON_W, BUTTON_H)
    draw_button(surf, rect, "Swap with ally", mouse_pos, size=15,
                disabled=swap_used or actor.has_status("root") or actor.must_recharge)
    if not swap_used and not actor.has_status("root") and not actor.must_recharge:
        buttons.append((rect, {"type": "swap", "target": None}))
    y += BUTTON_H + 4

    # Skip — label changes to "Recharge" when must_recharge
    rect = pygame.Rect(BUTTON_X, y, BUTTON_W, BUTTON_H)
    skip_label = "Recharge" if actor.must_recharge else "Skip"
    draw_button(surf, rect, skip_label, mouse_pos, size=15, normal=(40, 40, 45))
    buttons.append((rect, {"type": "skip"}))
    y += BUTTON_H + 14  # larger gap to visually separate Back

    # Back
    rect = pygame.Rect(BUTTON_X, y, BUTTON_W, BUTTON_H)
    draw_button(surf, rect, "← Back", mouse_pos, size=15, normal=(35, 35, 50),
                hover=(55, 55, 75))
    buttons.append((rect, {"type": "back"}))

    return buttons


def draw_target_prompt(surf, mouse_pos, targets: list,
                        slot_rects_team1: dict, slot_rects_team2: dict,
                        battle: BattleState,
                        prompt_text="Select a target",
                        acting_player=None) -> list:
    """
    Draw target selection overlay. Returns list of (rect, unit) tuples.
    """
    # Dim overlay
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 120))
    surf.blit(overlay, (0, 0))

    draw_text(surf, prompt_text, 24, YELLOW, WIDTH // 2, 45, center=True)

    clickable = []
    for unit in targets:
        if unit is None:
            continue
        # Find rect
        if unit in battle.team1.members:
            rect = slot_rects_team1.get(unit.slot)
        else:
            rect = slot_rects_team2.get(unit.slot)

        if rect is None:
            continue

        hov = rect.collidepoint(mouse_pos)
        border_col = YELLOW if hov else BORDER_ACTIVE
        pygame.draw.rect(surf, border_col, rect, 3, border_radius=4)

        if hov:
            # Tooltip
            draw_text(surf, unit.name, 18, YELLOW,
                      rect.centerx, rect.bottom + 12, center=True)

        clickable.append((rect, unit))

    return clickable


def _queue_label(q) -> tuple:
    """Return (label_suffix, color) for a queued action dict."""
    if q is None:
        return "(none)", TEXT_MUTED
    if q["type"] == "skip":
        return "skip", TEXT_MUTED
    if q["type"] == "swap":
        tgt = q.get("target")
        s = "swap"
        if tgt:
            s += f" ↔ {tgt.name[:12]}"
        return s, CYAN
    if q["type"] == "ability":
        ab = q.get("ability")
        tgt = q.get("target")
        s = ab.name[:14] if ab else "?"
        if tgt:
            s += f" → {tgt.name[:10]}"
        if q.get("swap_target") is not None:
            s += f" ↔ {q['swap_target'].name[:10]}"
        return s, TEXT
    if q["type"] == "item":
        tgt = q.get("target")
        s = "item"
        if tgt:
            s += f" → {tgt.name[:10]}"
        return s, GREEN
    return "?", TEXT_MUTED


def draw_queued_summary(surf, team: TeamState, y_start: int, acting_player: int,
                        x: int = 995, panel_w: int = 380):
    """Show the queued actions for a player's team in a small bordered panel."""
    rows = sum(1 + (u.queued2 is not None) for u in team.members if not u.ko)
    panel_h = 22 + rows * 17 + 6
    panel_rect = pygame.Rect(x, y_start, panel_w, panel_h)
    draw_rect_border(surf, panel_rect, (30, 35, 30), (60, 100, 60))

    y = y_start + 5
    draw_text(surf, f"P{acting_player} — Queued Actions", 14, (130, 200, 130), x + 8, y)
    y += 19
    name_col_w = 130
    for unit in team.members:
        if unit.ko:
            continue
        suffix, col = _queue_label(unit.queued)
        draw_text(surf, f"  {short_name(unit.name)[:14]}:", 13, TEXT_DIM, x + 8, y)
        draw_text(surf, suffix, 13, col, x + name_col_w, y)
        y += 17
        if unit.queued2 is not None:
            suffix2, col2 = _queue_label(unit.queued2)
            draw_text(surf, f"    +extra:", 12, YELLOW, x + 8, y)
            draw_text(surf, suffix2, 12, col2, x + name_col_w, y)
            y += 16


# ─────────────────────────────────────────────────────────────────────────────
# PASS SCREEN
# ─────────────────────────────────────────────────────────────────────────────

def draw_pass_screen(surf, player_name: str, message: str,
                     mouse_pos) -> pygame.Rect:
    """Full-screen pass screen. Supports \\n in message. Returns the Continue button rect."""
    surf.fill(BG)
    cx, cy = WIDTH // 2, HEIGHT // 2
    draw_text(surf, "FABLED", 60, TEXT, cx, cy - 180, center=True)
    lines = message.split("\n")
    font_sz = 24 if len(lines) == 1 else 19
    line_h = 30 if len(lines) == 1 else 26
    total_h = line_h * len(lines)
    y0 = cy - 80 - total_h // 2
    for line in lines:
        draw_text(surf, line, font_sz, YELLOW, cx, y0, center=True)
        y0 += line_h
    if player_name:
        draw_text(surf, f"Pass the device to  {player_name}", 22, TEXT_DIM,
                  cx, y0 + 14, center=True)

    btn = pygame.Rect(cx - 140, cy + 70, 280, 55)
    draw_button(surf, btn, "Continue →", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE, border=BORDER_ACTIVE)
    return btn


# ─────────────────────────────────────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────────────────────────────────────

def draw_main_menu(surf, mouse_pos, player_level=0, new_catalog_unlocks=False):
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "FABLED", 80, TEXT, cx, 130, center=True)
    draw_text(surf, f"Level {player_level}", 22, TEXT_DIM, cx, 220, center=True)

    story_btn       = pygame.Rect(cx - 130, 285, 260, 52)
    practice_btn    = pygame.Rect(cx - 130, 348, 260, 52)
    teambuilder_btn = pygame.Rect(cx - 130, 411, 260, 52)
    catalog_btn     = pygame.Rect(cx - 130, 474, 260, 52)

    draw_button(surf, story_btn, "Quests", mouse_pos, size=22,
                normal=(40, 90, 50), hover=(55, 120, 65), border=BORDER_ACTIVE)
    draw_button(surf, practice_btn, "Training", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE)
    draw_button(surf, teambuilder_btn, "Tavern", mouse_pos, size=22,
                normal=(75, 45, 120), hover=(105, 65, 165), border=BORDER_ACTIVE)
    draw_button(surf, catalog_btn, "Guidebook", mouse_pos, size=22,
                normal=(55, 75, 80), hover=(75, 105, 115), border=BORDER_ACTIVE)
    if new_catalog_unlocks:
        bx, by = catalog_btn.right, catalog_btn.top
        pygame.draw.circle(surf, (190, 130, 30), (bx, by), 11)
        draw_text(surf, "!", 14, TEXT, bx - 3, by - 9)

    # Small icon buttons — upper-right corner
    settings_btn = pygame.Rect(WIDTH - 98, 14, 40, 40)
    exit_btn     = pygame.Rect(WIDTH - 52, 14, 40, 40)
    s_hov = settings_btn.collidepoint(mouse_pos)
    e_hov = exit_btn.collidepoint(mouse_pos)
    draw_rect_border(surf, settings_btn, PANEL_HIGHLIGHT if s_hov else PANEL_ALT, BORDER_ACTIVE if s_hov else BORDER)
    draw_rect_border(surf, exit_btn,     PANEL_HIGHLIGHT if e_hov else PANEL_ALT, BORDER_ACTIVE if e_hov else BORDER)
    draw_text(surf, "⚙", 22, TEXT if s_hov else TEXT_DIM, settings_btn.x + 8, settings_btn.y + 8)
    draw_text(surf, "✕", 20, RED if e_hov else TEXT_DIM,  exit_btn.x + 10,     exit_btn.y + 9)

    return story_btn, practice_btn, teambuilder_btn, catalog_btn, settings_btn, exit_btn


def draw_settings_screen(surf, mouse_pos, confirm_reset: bool = False,
                         fast_resolution: bool = False,
                         tutorials_enabled: bool = True) -> dict:
    """Draw the settings screen. Returns button rects."""
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Settings", 48, TEXT, cx, 60, center=True)

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    toggle_on  = (55, 130, 65)
    toggle_off = (50, 50, 55)

    # Tutorial toggle
    tutorial_btn = pygame.Rect(cx - 180, 160, 360, 48)
    tutorial_label = f"Tutorial: {'ON' if tutorials_enabled else 'OFF'}"
    draw_button(surf, tutorial_btn, tutorial_label, mouse_pos, size=20,
                normal=toggle_on if tutorials_enabled else toggle_off,
                hover=(80, 175, 90) if tutorials_enabled else (70, 70, 80))
    draw_text(surf, "Show tutorial popups during gameplay.",
              14, TEXT_MUTED, cx, 218, center=True)

    # Fast Skip toggle
    fast_btn = pygame.Rect(cx - 180, 240, 360, 48)
    fast_label = f"Fast Skip: {'ON' if fast_resolution else 'OFF'}"
    draw_button(surf, fast_btn, fast_label, mouse_pos, size=20,
                normal=toggle_on if fast_resolution else toggle_off,
                hover=(80, 175, 90) if fast_resolution else (70, 70, 80))
    draw_text(surf, "Resolve all actions at once instead of one at a time.",
              14, TEXT_MUTED, cx, 298, center=True)

    reset_btn = pygame.Rect(cx - 180, 336, 360, 58)
    draw_button(surf, reset_btn, "Reset Player Data", mouse_pos, size=22,
                normal=(90, 35, 35), hover=(130, 50, 50), border=(180, 60, 60))
    draw_text(surf, "Clears all campaign progress and saved parties.",
              15, TEXT_MUTED, cx, 408, center=True)

    confirm_btn = None
    cancel_btn  = None
    if confirm_reset:
        # Confirmation overlay
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))

        panel = pygame.Rect(cx - 260, HEIGHT // 2 - 110, 520, 220)
        draw_rect_border(surf, panel, (40, 30, 30), (180, 60, 60), 2)
        draw_text(surf, "Reset all player data?", 26, TEXT, cx, HEIGHT // 2 - 85, center=True)
        draw_text(surf, "This cannot be undone.", 18, RED, cx, HEIGHT // 2 - 48, center=True)
        confirm_btn = pygame.Rect(cx - 200, HEIGHT // 2 + 10, 180, 52)
        cancel_btn  = pygame.Rect(cx + 20,  HEIGHT // 2 + 10, 180, 52)
        draw_button(surf, confirm_btn, "Yes, Reset", mouse_pos, size=18,
                    normal=(110, 30, 30), hover=(155, 45, 45), border=(200, 60, 60))
        draw_button(surf, cancel_btn, "Cancel", mouse_pos, size=18)

    return {
        "back_btn":      back_btn,
        "tutorial_btn":  tutorial_btn,
        "fast_btn":      fast_btn,
        "reset_btn":     reset_btn,
        "confirm_btn":   confirm_btn,
        "cancel_btn":    cancel_btn,
    }


def draw_rename_overlay(surf, mouse_pos, current_text: str) -> dict:
    """Modal overlay for typing a team name. Returns confirm/cancel rects."""
    cx, cy = WIDTH // 2, HEIGHT // 2

    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 170))
    surf.blit(overlay, (0, 0))

    panel = pygame.Rect(cx - 280, cy - 90, 560, 180)
    draw_rect_border(surf, panel, (30, 35, 45), BORDER_ACTIVE, 2)

    draw_text(surf, "Party Name", 22, TEXT, cx, cy - 72, center=True)

    # Input box
    input_rect = pygame.Rect(cx - 220, cy - 38, 440, 40)
    draw_rect_border(surf, input_rect, (20, 25, 35), CYAN, 2)
    display = current_text if current_text else ""
    draw_text(surf, display + "▍", 20, TEXT, input_rect.x + 10, input_rect.y + 8)

    confirm_btn = pygame.Rect(cx - 200, cy + 20, 180, 44)
    cancel_btn  = pygame.Rect(cx + 20,  cy + 20, 180, 44)
    draw_button(surf, confirm_btn, "Confirm", mouse_pos, size=18,
                normal=(40, 90, 50), hover=(55, 120, 65))
    draw_button(surf, cancel_btn, "Cancel", mouse_pos, size=18)

    return {"confirm_btn": confirm_btn, "cancel_btn": cancel_btn}


def draw_practice_menu(surf, mouse_pos) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Training", 48, TEXT, cx, 80, center=True)
    draw_text(surf, "Play with full access to all adventurers, basics, and items.",
              18, TEXT_DIM, cx, 145, center=True)

    vs_ai_btn  = pygame.Rect(cx - 150, 220, 300, 62)
    vs_pvp_btn = pygame.Rect(cx - 150, 298, 300, 62)
    back_btn   = pygame.Rect(20, 20, 100, 36)

    draw_button(surf, vs_ai_btn,  "vs AI",       mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE)
    draw_button(surf, vs_pvp_btn, "vs Player",   mouse_pos, size=22,
                normal=(55, 70, 120), hover=(72, 95, 160), border=BORDER_ACTIVE)
    draw_button(surf, back_btn,   "Back",         mouse_pos, size=16)

    return {"vs_ai_btn": vs_ai_btn, "vs_pvp_btn": vs_pvp_btn, "back_btn": back_btn}


def draw_teambuilder(surf, saved_teams: list, mouse_pos, profile) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Tavern", 48, TEXT, cx, 40, center=True)
    draw_text(surf, "Build up to 6 parties using your unlocked adventurers.",
              18, TEXT_DIM, cx, 95, center=True)

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    slot_w = 620
    slot_h = 165
    pad = 16
    start_x = cx - slot_w - pad // 2
    start_y = 120

    slot_btns = []
    delete_btns = []
    rename_btns = []

    for row in range(3):
        for col in range(2):
            idx = row * 2 + col
            rect = pygame.Rect(
                start_x + col * (slot_w + pad),
                start_y + row * (slot_h + pad),
                slot_w, slot_h
            )

            if idx < len(saved_teams) and saved_teams[idx] is not None:
                team = saved_teams[idx]
                draw_rect_border(surf, rect, PANEL_ALT, BORDER_ACTIVE)
                draw_text(surf, team.get("name", f"Party {idx+1}"), 18, TEXT,
                          rect.x + 10, rect.y + 8)

                members = team.get("members", [])
                member_col_w = (slot_w - 110) // 3
                for mi, m in enumerate(members[:3]):
                    mx = rect.x + 10 + mi * member_col_w
                    my = rect.y + 34
                    adv_name = m.get("adv_id", "?").replace("_", " ").title()
                    draw_text(surf, adv_name, 14, TEXT, mx, my)
                    sig_name = m.get("sig_id", "").replace("_", " ").title()
                    draw_text(surf, sig_name[:18], 11, TEXT_DIM, mx, my + 16)
                    basics = m.get("basics", [])
                    basics_str = ", ".join(b.replace("_", " ").title() for b in basics[:2])
                    draw_text(surf, basics_str[:22], 11, TEXT_DIM, mx, my + 30)
                    item_name = m.get("item_id", "").replace("_", " ").title()
                    draw_text(surf, item_name[:18], 11, TEXT_DIM, mx, my + 44)

                edit_btn_rect   = pygame.Rect(rect.right - 95, rect.y + 10, 85, 26)
                rename_btn_rect = pygame.Rect(rect.right - 95, rect.y + 42, 85, 26)
                del_btn_rect    = pygame.Rect(rect.right - 95, rect.y + 74, 85, 26)
                draw_button(surf, edit_btn_rect,   "Edit Party", mouse_pos, size=12,
                            normal=BLUE_DARK, hover=BLUE)
                draw_button(surf, rename_btn_rect, "Rename",    mouse_pos, size=12,
                            normal=(60, 60, 30), hover=(90, 90, 45))
                draw_button(surf, del_btn_rect,    "Delete",    mouse_pos, size=12,
                            normal=(80, 30, 30), hover=(110, 45, 45))
                slot_btns.append((edit_btn_rect, idx))
                rename_btns.append((rename_btn_rect, idx))
                delete_btns.append((del_btn_rect, idx))
            else:
                draw_rect_border(surf, rect, PANEL, BORDER)
                draw_text(surf, f"Slot {idx+1}  (empty)", 16, TEXT_MUTED,
                          rect.centerx, rect.centery, center=True)
                build_btn = pygame.Rect(rect.right - 110, rect.centery - 16, 100, 32)
                draw_button(surf, build_btn, "Build Party", mouse_pos, size=14,
                            normal=(40, 90, 50), hover=(55, 120, 65))
                slot_btns.append((build_btn, idx))

    return {
        "slot_btns": slot_btns,
        "delete_btns": delete_btns,
        "rename_btns": rename_btns,
        "back_btn": back_btn,
    }


def draw_story_team_select(surf, saved_teams: list, mouse_pos, quest_def) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Select Your Party", 40, TEXT, cx, 50, center=True)
    # quest_def.key_preview omitted for now; restore the draw_text call here to re-add it

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    team_btns = []
    teambuilder_btn = None

    valid_teams = [(i, t) for i, t in enumerate(saved_teams) if t is not None]

    if not valid_teams:
        draw_text(surf, "No parties saved. Build a party in the Tavern first.",
                  20, RED, cx, 250, center=True)
        teambuilder_btn = pygame.Rect(cx - 140, 310, 280, 55)
        draw_button(surf, teambuilder_btn, "Go to Tavern", mouse_pos, size=20,
                    normal=(40, 90, 50), hover=(55, 120, 65))
    else:
        card_w = 700
        card_h = 110
        pad = 12
        start_y = 140
        for list_idx, (slot_idx, team) in enumerate(valid_teams):
            ry = start_y + list_idx * (card_h + pad)
            rect = pygame.Rect(cx - card_w // 2, ry, card_w, card_h)
            hov = rect.collidepoint(mouse_pos)
            fill = PANEL_HIGHLIGHT if hov else PANEL_ALT
            draw_rect_border(surf, rect, fill, BORDER_ACTIVE)
            draw_text(surf, team.get("name", f"Party {slot_idx+1}"), 18, TEXT,
                      rect.x + 14, rect.y + 12)
            members = team.get("members", [])
            member_str = "  |  ".join(
                m.get("adv_id", "?").replace("_", " ").title()
                for m in members
            )
            draw_text(surf, member_str, 14, TEXT_DIM, rect.x + 14, rect.y + 44)
            team_btns.append((rect, slot_idx))

    return {"team_btns": team_btns, "back_btn": back_btn, "teambuilder_btn": teambuilder_btn}


# ─────────────────────────────────────────────────────────────────────────────
# TEAM SELECTION SCREEN
# ─────────────────────────────────────────────────────────────────────────────

ROSTER_COLS   = 3
CARD_W        = 210
CARD_H        = 100
CARD_PAD      = 12
ROSTER_X      = 20
ROSTER_Y      = 90
DETAIL_X      = 700
DETAIL_Y      = 80
DETAIL_W      = 680
DETAIL_H      = 760


def draw_adventurer_card(surf, rect, defn, selected, in_team, mouse_pos, status_rects_out=None):
    if defn is None:
        return
    cls_fill = CLASS_COLORS.get(defn.cls, PANEL_ALT)
    if in_team:
        fill = tuple(min(255, c + 14) for c in cls_fill)
    elif selected:
        fill = tuple(min(255, c + 24) for c in cls_fill)
    else:
        fill = cls_fill
    bord = GREEN if in_team else (BORDER_ACTIVE if selected else BORDER)
    draw_rect_border(surf, rect, fill, bord)
    _name = defn.name
    _f15 = font(15)
    _max_name_w = rect.w - 12
    if _f15.size(_name)[0] > _max_name_w:
        while _f15.size(_name + "…")[0] > _max_name_w and len(_name) > 1:
            _name = _name[:-1]
        _name = _name + "…"
    draw_text(surf, _name, 15, TEXT, rect.x + 6, rect.y + 6)
    _cr = draw_text(surf, cls_label(defn.cls), 13, CLASS_TEXT_COLORS.get(defn.cls, TEXT_MUTED), rect.x + 6, rect.y + 24)
    if status_rects_out is not None:
        status_rects_out.append((_cr, defn.cls))
    draw_text(surf, f"HP {defn.hp}  ATK {defn.attack}", 12, TEXT_DIM,
              rect.x + 6, rect.y + 42)
    draw_text(surf, f"DEF {defn.defense}  SPD {defn.speed}", 12, TEXT_DIM,
              rect.x + 6, rect.y + 58)
    if rect.height >= 98:
        draw_text(surf, defn.talent_name, 12, YELLOW, rect.x + 6, rect.y + 76)


def draw_team_select_screen(surf, player_name: str, roster: list,
                              selected_idx: int, team_picks: list,
                              sub_phase: str, current_adv_idx: int,
                              sig_choice: int, basic_choices: list,
                              item_choice: int, items: list,
                              class_basics: dict,
                              mouse_pos,
                              scroll_offset: int = 0,
                              team_slot_selected=None,
                              sig_tier: int = 3,
                              twists_unlocked: bool = False,
                              status_rects_out: list = None,
                              confirm_label: str = "Ready",
                              pre_battle_mode: bool = False,
                              enemy_picks: list = None,
                              focused_slot: int = None) -> dict:
    """
    Draw the team selection screen.
    Returns a dict of {region_name: [list of (rect, value)]} for click handling.
    sub_phase: "pick_adventurers" | "pick_sig" | "pick_basics" | "pick_item"
    """
    surf.fill(BG)
    if pre_battle_mode:
        draw_text(surf, "Pre-Battle Setup", 28, TEXT, WIDTH // 2, 30, center=True)
    else:
        draw_text(surf, f"{player_name} — Build Your Party", 28, TEXT, WIDTH // 2,
                  30, center=True)

    clicks = {
        "roster": [],
        "sig": [],
        "basics": [],
        "items": [],
        "party_slots": [],
        "party_remove": [],
        "party_swap": [],
        "confirm": None,
        "back": None,
        "edit_sets_btn": None,
        "scroll_max": 0,
        "scroll_viewport": None,
        "enemy_cards": [],
    }

    # Always 3-column scrollable grid, sorted by class.
    roster_cols = ROSTER_COLS
    card_w = CARD_W
    card_h = CARD_H

    if pre_battle_mode:
        # ── Enemy formation cards in place of roster grid ─────────────────────
        enemy_card_w = 210
        enemy_card_h = 200
        enemy_card_pad = 12
        slot_labels_enemy = ["Front", "Back Left", "Back Right"]
        draw_text(surf, "Enemy Formation", 16, TEXT_MUTED, ROSTER_X, ROSTER_Y - 22)
        for i, ep in enumerate(enemy_picks or []):
            ex = ROSTER_X + i * (enemy_card_w + enemy_card_pad)
            ey = ROSTER_Y
            erect = pygame.Rect(ex, ey, enemy_card_w, enemy_card_h)
            ep_defn = ep.get("definition")
            cls_fill = CLASS_COLORS.get(ep_defn.cls, PANEL_ALT) if ep_defn else PANEL_ALT
            _ep_hover = erect.collidepoint(mouse_pos)
            draw_rect_border(surf, erect, cls_fill, BORDER_ACTIVE if _ep_hover else BORDER)
            clicks["enemy_cards"].append((erect, ep))
            edy = ey + 6
            draw_text(surf, slot_labels_enemy[i], 12, TEXT_MUTED, ex + 6, edy)
            edy += 16
            if ep_defn:
                _ename = ep_defn.name
                _ef = font(15)
                if _ef.size(_ename)[0] > enemy_card_w - 12:
                    while _ef.size(_ename + "…")[0] > enemy_card_w - 12 and len(_ename) > 1:
                        _ename = _ename[:-1]
                    _ename = _ename + "…"
                draw_text(surf, _ename, 15, TEXT, ex + 6, edy)
                edy += 20
                _ecr = draw_text(surf, cls_label(ep_defn.cls), 12,
                                 CLASS_TEXT_COLORS.get(ep_defn.cls, TEXT_MUTED), ex + 6, edy)
                if status_rects_out is not None:
                    status_rects_out.append((_ecr, ep_defn.cls))
                edy += 16
                draw_text(surf, f"HP {ep_defn.hp}", 11, TEXT_DIM, ex + 6, edy)
                edy += 14
                draw_text(surf, f"ATK {ep_defn.attack}  DEF {ep_defn.defense}  SPD {ep_defn.speed}",
                          11, TEXT_DIM, ex + 6, edy)
                edy += 14
                ep_sig = ep.get("signature")
                if ep_sig:
                    _sname = ep_sig.name
                    if font(12).size(_sname)[0] > enemy_card_w - 14:
                        _sname = _sname[:18] + "…"
                    draw_text(surf, _sname, 12, YELLOW, ex + 6, edy)
                    edy += 14
                for eb in ep.get("basics", []):
                    _bname = eb.name
                    if font(11).size(_bname)[0] > enemy_card_w - 14:
                        _bname = _bname[:20] + "…"
                    draw_text(surf, _bname, 11, TEXT_DIM, ex + 6, edy)
                    edy += 13
                ep_item = ep.get("item")
                if ep_item:
                    _iname = ep_item.name
                    if font(11).size(_iname)[0] > enemy_card_w - 14:
                        _iname = _iname[:20] + "…"
                    draw_text(surf, _iname, 11, (140, 190, 140), ex + 6, edy)
        # clicks["roster"] stays empty in pre_battle_mode
    else:
        roster = sorted(roster, key=lambda d: (d.cls, d.name))

        # ── Roster grid (left) ────────────────────────────────────────────────────
        # Reserve 100px at the bottom for fixed party slots
        roster_panel_h = HEIGHT - ROSTER_Y - 100
        roster_view = pygame.Rect(ROSTER_X, ROSTER_Y, DETAIL_X - ROSTER_X - 20, roster_panel_h)
        _n_roster_rows = (len(roster) + roster_cols - 1) // roster_cols
        roster_content_h = _n_roster_rows * (card_h + CARD_PAD)
        max_scroll = max(0, roster_content_h - roster_view.height)
        roster_scroll = 0
        if sub_phase == "pick_adventurers":
            roster_scroll = max(0, min(scroll_offset, max_scroll))
            clicks["scroll_max"] = max_scroll
            clicks["scroll_viewport"] = roster_view

        prev_clip = surf.get_clip()
        surf.set_clip(roster_view)
        for i, defn in enumerate(roster):
            col = i % roster_cols
            row = i // roster_cols
            x = ROSTER_X + col * (card_w + CARD_PAD)
            y = ROSTER_Y + row * (card_h + CARD_PAD) - roster_scroll
            rect = pygame.Rect(x, y, card_w, card_h)
            in_team = any(p.get("definition") == defn for p in team_picks)
            sel = selected_idx is defn
            if rect.bottom >= roster_view.top and rect.top <= roster_view.bottom:
                draw_adventurer_card(surf, rect, defn, sel, in_team, mouse_pos, status_rects_out)
            clicks["roster"].append((rect, defn))
        surf.set_clip(prev_clip)
        if sub_phase == "pick_adventurers":
            _draw_scroll_arrows(surf, roster_view, roster_scroll, max_scroll)

    # ── Party slots — fixed at the bottom of the left panel (outside scroll clip) ──
    slot_labels = ["Front", "Back Left", "Back Right"]
    draw_text(surf, "Your Party:", 18, TEXT_DIM, ROSTER_X, HEIGHT - 95)
    for i in range(3):
        x = ROSTER_X + i * 220
        rect = pygame.Rect(x, HEIGHT - 73, 210, 50)
        if i < len(team_picks):
            p = team_picks[i]
            slot_defn = p.get("definition")
            cls_fill = CLASS_COLORS.get(slot_defn.cls, PANEL_ALT) if slot_defn else PANEL_ALT
            # Highlight the slot being edited or focused
            is_editing = (sub_phase in ("pick_sig", "pick_basics", "pick_item")
                          and current_adv_idx == i)
            is_focused = (sub_phase == "pick_adventurers" and focused_slot == i)
            fill = tuple(min(255, c + 28) for c in cls_fill) if (is_editing or is_focused) else tuple(min(255, c + 14) for c in cls_fill)
            border = BORDER_ACTIVE if (is_editing or is_focused) else BORDER
            draw_rect_border(surf, rect, fill, border)
            draw_text(surf, slot_labels[i], 13, CYAN if is_editing else TEXT_MUTED, x + 6, HEIGHT - 73 + 4)
            if slot_defn:
                draw_text(surf, slot_defn.name[:22], 15, TEXT, x + 6, HEIGHT - 73 + 20)
            else:
                draw_text(surf, "(empty)", 15, TEXT_MUTED, x + 6, HEIGHT - 73 + 20)

            # Set status indicators at y+37
            _f10 = font(10)
            _sx = x + 6
            _sy = HEIGHT - 73 + 37
            _has_sig = "signature" in p
            _has_basics = len(p.get("basics", [])) == 2
            _has_item = "item" in p
            for _lbl, _ok in (("Sig", _has_sig), ("Basics", _has_basics), ("Item", _has_item)):
                _mark = "✓" if _ok else "○"
                _col = (80, 210, 80) if _ok else TEXT_MUTED
                _s = _f10.render(f"{_lbl}{_mark}", True, _col)
                surf.blit(_s, (_sx, _sy))
                _sx += _s.get_width() + 4

            if pre_battle_mode:
                # In pre_battle_mode: ⇄ shifted to where × was, no × button
                swapbtn = pygame.Rect(x + 188, HEIGHT - 73 + 2, 20, 18)
                s_hov = swapbtn.collidepoint(mouse_pos)
                pygame.draw.rect(surf, (40, 80, 120) if s_hov else (30, 55, 80), swapbtn, border_radius=3)
                draw_text(surf, "⇄", 11, (140, 200, 240) if s_hov else TEXT_MUTED, swapbtn.x + 2, swapbtn.y + 2)
                clicks["party_swap"].append((swapbtn, i))
            else:
                # Normal mode: ⇄ swap button (left of ×)
                swapbtn = pygame.Rect(x + 166, HEIGHT - 73 + 2, 20, 18)
                s_hov = swapbtn.collidepoint(mouse_pos)
                pygame.draw.rect(surf, (40, 80, 120) if s_hov else (30, 55, 80), swapbtn, border_radius=3)
                draw_text(surf, "⇄", 11, (140, 200, 240) if s_hov else TEXT_MUTED, swapbtn.x + 2, swapbtn.y + 2)
                clicks["party_swap"].append((swapbtn, i))

                # × remove button
                xbtn = pygame.Rect(x + 188, HEIGHT - 73 + 2, 20, 18)
                hov = xbtn.collidepoint(mouse_pos)
                pygame.draw.rect(surf, RED_DARK if hov else (70, 40, 40), xbtn, border_radius=3)
                draw_text(surf, "×", 14, RED if hov else TEXT_DIM, xbtn.x + 3, xbtn.y + 1)
                clicks["party_remove"].append((xbtn, i))
            clicks["party_slots"].append((rect, i))
        else:
            draw_rect_border(surf, rect, PANEL_ALT, BORDER)
            draw_text(surf, slot_labels[i], 13, TEXT_MUTED, x + 6, HEIGHT - 73 + 4)
            draw_text(surf, "(empty)", 15, TEXT_MUTED, x + 6, HEIGHT - 73 + 20)

    # ── Detail panel (right) ──────────────────────────────────────────────────
    detail_rect = pygame.Rect(DETAIL_X, DETAIL_Y, DETAIL_W, DETAIL_H)
    draw_panel(surf, detail_rect)

    # Focused slot in pick_adventurers: show that member's current sets + Edit Sets button
    if sub_phase == "pick_adventurers" and focused_slot is not None and focused_slot < len(team_picks):
        _pm = team_picks[focused_slot]
        _pm_defn = _pm.get("definition")
        _slot_lbl = ["Front", "Back Left", "Back Right"][focused_slot]
        _dx, _dy = DETAIL_X + 14, DETAIL_Y + 12
        _detail_max_w = DETAIL_W - 28
        _bottom_limit = DETAIL_Y + DETAIL_H - 65  # leave room for Edit Sets button
        draw_text(surf, _slot_lbl, 13, TEXT_MUTED, _dx, _dy)
        _dy += 18
        if _pm_defn:
            # ── Name + class ──────────────────────────────────────────────────
            draw_text(surf, _pm_defn.name, 22, TEXT, _dx, _dy)
            _dy += 26
            _pmcr = draw_text(surf, f"{cls_label(_pm_defn.cls)}  —  {_pm_defn.talent_name}",
                              14, YELLOW, _dx, _dy)
            if status_rects_out is not None:
                status_rects_out.append((_pmcr, _pm_defn.cls))
            _dy += 18
            # Talent description
            for _line in _wrap_text(_pm_defn.talent_text, 12, _detail_max_w):
                if _dy + 13 > _bottom_limit:
                    break
                _draw_rich_line(surf, _line, 12, TEXT_DIM, _dx, _dy, status_rects_out)
                _dy += 14
            _dy += 2
            # Stats
            if _dy + 14 <= _bottom_limit:
                draw_text(surf,
                          f"HP {_pm_defn.hp}   ATK {_pm_defn.attack}   DEF {_pm_defn.defense}   SPD {_pm_defn.speed}",
                          13, TEXT, _dx, _dy)
                _dy += 18

            # ── Signature ─────────────────────────────────────────────────────
            if _dy + 14 <= _bottom_limit:
                pygame.draw.line(surf, BORDER, (_dx, _dy), (_dx + _detail_max_w, _dy), 1)
                _dy += 7
            _pm_sig = _pm.get("signature")
            if _dy + 14 <= _bottom_limit:
                draw_text(surf, "Signature", 13, CYAN, _dx, _dy)
                _dy += 16
            if _pm_sig and _dy + 13 <= _bottom_limit:
                draw_text(surf, _pm_sig.name, 14, YELLOW if not _pm_sig.passive else TEXT_DIM,
                          _dx + 6, _dy)
                _dy += 16
                if _dy + 12 <= _bottom_limit:
                    _stype = "Passive" if _pm_sig.passive else "Active"
                    _scol  = TYPE_PASSIVE_COL if _pm_sig.passive else TYPE_ACTIVE_COL
                    draw_text(surf, _stype, 12, _scol, _dx + 10, _dy)
                    _dy += 13
                if _fl_bl_same(_pm_sig):
                    if _dy + 12 <= _bottom_limit:
                        _draw_rich_line(surf, f"  FL & BL: {_mode_summary(_pm_sig.frontline)}", 12, TEXT_DIM,
                                        _dx + 10, _dy, status_rects_out)
                        _dy += 13
                else:
                    if _dy + 12 <= _bottom_limit:
                        _draw_rich_line(surf, f"  FL: {_mode_summary(_pm_sig.frontline)}", 12, TEXT_DIM,
                                        _dx + 10, _dy, status_rects_out)
                        _dy += 13
                    if _dy + 12 <= _bottom_limit:
                        _draw_rich_line(surf, f"  BL: {_mode_summary(_pm_sig.backline)}", 12, TEXT_MUTED,
                                        _dx + 10, _dy, status_rects_out)
                        _dy += 13
            elif not _pm_sig and _dy + 13 <= _bottom_limit:
                draw_text(surf, "  —", 13, TEXT_MUTED, _dx + 6, _dy)
                _dy += 15
            _dy += 2

            # ── Basics ────────────────────────────────────────────────────────
            if _dy + 14 <= _bottom_limit:
                pygame.draw.line(surf, BORDER, (_dx, _dy), (_dx + _detail_max_w, _dy), 1)
                _dy += 7
            if _dy + 14 <= _bottom_limit:
                draw_text(surf, "Basics", 13, CYAN, _dx, _dy)
                _dy += 16
            _pm_basics = _pm.get("basics", [])
            if _pm_basics:
                for _pb in _pm_basics:
                    if _dy + 13 > _bottom_limit:
                        break
                    draw_text(surf, _pb.name, 13, TEXT, _dx + 6, _dy)
                    _dy += 14
                    if _dy + 12 <= _bottom_limit:
                        _btype = "Passive" if _pb.passive else "Active"
                        _bcol  = TYPE_PASSIVE_COL if _pb.passive else TYPE_ACTIVE_COL
                        draw_text(surf, _btype, 12, _bcol, _dx + 10, _dy)
                        _dy += 13
                    if _fl_bl_same(_pb):
                        if _dy + 12 <= _bottom_limit:
                            _draw_rich_line(surf, f"  FL & BL: {_mode_summary(_pb.frontline)}", 12, TEXT_DIM,
                                            _dx + 10, _dy, status_rects_out)
                            _dy += 13
                    else:
                        if _dy + 12 <= _bottom_limit:
                            _draw_rich_line(surf, f"  FL: {_mode_summary(_pb.frontline)}", 12, TEXT_DIM,
                                            _dx + 10, _dy, status_rects_out)
                            _dy += 13
                        if _dy + 12 <= _bottom_limit:
                            _draw_rich_line(surf, f"  BL: {_mode_summary(_pb.backline)}", 12, TEXT_MUTED,
                                            _dx + 10, _dy, status_rects_out)
                            _dy += 13
                    _dy += 1
            else:
                if _dy + 13 <= _bottom_limit:
                    draw_text(surf, "  —", 13, TEXT_MUTED, _dx + 6, _dy)
                    _dy += 15
            _dy += 2

            # ── Item ──────────────────────────────────────────────────────────
            if _dy + 14 <= _bottom_limit:
                pygame.draw.line(surf, BORDER, (_dx, _dy), (_dx + _detail_max_w, _dy), 1)
                _dy += 7
            if _dy + 14 <= _bottom_limit:
                draw_text(surf, "Item", 13, CYAN, _dx, _dy)
                _dy += 16
            _pm_item = _pm.get("item")
            if _pm_item and _dy + 13 <= _bottom_limit:
                draw_text(surf, _pm_item.name, 13, (140, 190, 140), _dx + 6, _dy)
                _dy += 14
                if _dy + 12 <= _bottom_limit:
                    _itype = "Passive" if _pm_item.passive else "Active"
                    _icol  = TYPE_PASSIVE_COL if _pm_item.passive else TYPE_ACTIVE_COL
                    draw_text(surf, _itype, 12, _icol, _dx + 10, _dy)
                    _dy += 13
                if _pm_item.description:
                    for _line in _wrap_text(_pm_item.description, 12, _detail_max_w - 10):
                        if _dy + 12 > _bottom_limit:
                            break
                        _draw_rich_line(surf, _line, 12, TEXT_DIM, _dx + 10, _dy, status_rects_out)
                        _dy += 13
            elif not _pm_item and _dy + 13 <= _bottom_limit:
                draw_text(surf, "  None", 13, TEXT_MUTED, _dx + 6, _dy)

        # Edit Sets button — bottom of detail panel
        edit_sets_rect = pygame.Rect(DETAIL_X + 14, DETAIL_Y + DETAIL_H - 55, 180, 44)
        draw_button(surf, edit_sets_rect, "Edit Sets →", mouse_pos,
                    normal=(45, 75, 55), hover=(60, 105, 75), size=16)
        clicks["edit_sets_btn"] = edit_sets_rect
        defn = None  # skip normal defn rendering
    elif sub_phase != "pick_adventurers" and team_picks and current_adv_idx < len(team_picks):
        defn = team_picks[current_adv_idx].get("definition")
    elif selected_idx is not None:
        defn = selected_idx  # selected_idx is now a defn object
    else:
        defn = None
        if sub_phase == "pick_adventurers" and not team_picks:
            draw_text(surf, "Click a party slot to view and edit their sets.",
                      16, TEXT_MUTED, DETAIL_X + DETAIL_W // 2, DETAIL_Y + DETAIL_H // 2,
                      center=True)
    if defn is not None:
        dx, dy = DETAIL_X + 14, DETAIL_Y + 12

        draw_text(surf, defn.name, 24, TEXT, dx, dy)
        dy += 30
        _dcr = draw_text(surf, f"{cls_label(defn.cls)}  —  {defn.talent_name}",
                         16, YELLOW, dx, dy)
        if status_rects_out is not None:
            status_rects_out.append((_dcr, defn.cls))
        dy += 20
        for line in _wrap_text(defn.talent_text, 13, DETAIL_W - 28):
            _draw_rich_line(surf, line, 13, TEXT_DIM, dx, dy, status_rects_out)
            dy += 16
        dy += 4
        draw_text(surf,
                  f"HP {defn.hp}   ATK {defn.attack}   DEF {defn.defense}   SPD {defn.speed}",
                  15, TEXT, dx, dy)
        dy += 26

        if sub_phase == "pick_adventurers":
            # ── Signatures preview ───────────────────────────────────────────
            pygame.draw.line(surf, BORDER, (dx, dy), (dx + DETAIL_W - 28, dy), 1)
            dy += 6
            avail = defn.sig_options[:sig_tier]
            draw_text(surf, f"Signatures  ({len(avail)} unlocked):", 14, CYAN, dx, dy)
            dy += 18
            bottom_limit = DETAIL_Y + DETAIL_H - 90
            for sig in avail:
                if dy + 13 > bottom_limit:
                    break
                draw_text(surf, sig.name, 14, TEXT, dx + 6, dy)
                dy += 15
                if dy + 12 <= bottom_limit:
                    _pstype = "Passive" if sig.passive else "Active"
                    _pscol  = TYPE_PASSIVE_COL if sig.passive else TYPE_ACTIVE_COL
                    draw_text(surf, _pstype, 12, _pscol, dx + 10, dy)
                    dy += 13
                if _fl_bl_same(sig):
                    if dy + 12 <= bottom_limit:
                        _draw_rich_line(surf, f"  FL & BL: {_mode_summary(sig.frontline)}", 12, TEXT_DIM, dx + 10, dy, status_rects_out)
                        dy += 13
                else:
                    if dy + 12 <= bottom_limit:
                        _draw_rich_line(surf, f"  FL: {_mode_summary(sig.frontline)}", 12, TEXT_DIM, dx + 10, dy, status_rects_out)
                        dy += 13
                    if dy + 12 <= bottom_limit:
                        _draw_rich_line(surf, f"  BL: {_mode_summary(sig.backline)}", 12, TEXT_MUTED, dx + 10, dy, status_rects_out)
                        dy += 13
                dy += 2
            # ── Twist preview ─────────────────────────────────────────────────
            if dy + 14 <= bottom_limit:
                pygame.draw.line(surf, BORDER, (dx, dy), (dx + DETAIL_W - 28, dy), 1)
                dy += 6
                if twists_unlocked:
                    twist = defn.twist
                    draw_text(surf, f"Twist: {twist.name}", 14, ORANGE, dx, dy)
                    dy += 15
                    if dy + 12 <= bottom_limit:
                        draw_text(surf, "Active", 12, TYPE_ACTIVE_COL, dx + 10, dy)
                        dy += 13
                    tfl = _mode_detail_lines(twist.frontline)
                    _twist_prefix = "  FL: "
                    for _ti, _tpart in enumerate(tfl):
                        for _twline in _wrap_text((_twist_prefix if _ti == 0 else "       ") + _tpart,
                                                   12, DETAIL_W - 38):
                            if dy + 12 > bottom_limit:
                                break
                            _draw_rich_line(surf, _twline, 12, TEXT_DIM, dx + 10, dy, status_rects_out)
                            dy += 13
                else:
                    draw_text(surf, "Twist: (locked)", 14, TEXT_MUTED, dx, dy)

        elif sub_phase == "pick_sig":
            draw_text(surf, "Choose Signature Ability:", 18, CYAN, dx, dy)
            dy += 24
            for i, sig in enumerate(defn.sig_options[:sig_tier]):
                fl_lines = _mode_detail_lines(sig.frontline)
                bl_lines = _mode_detail_lines(sig.backline)
                same = _fl_bl_same(sig)
                # Compute card height: name row + section header(s) + content lines
                def _sig_rendered_lines(lines):
                    return sum(len(_wrap_text(l, 13, DETAIL_W - 52)[:2]) for l in lines[:2])
                fl_n = _sig_rendered_lines(fl_lines)
                bl_n = _sig_rendered_lines(bl_lines)
                # name row (20) + type label (13) + section header(s) + content + padding
                if same:
                    entry_h = 20 + 13 + 14 + fl_n * 14 + 10
                else:
                    entry_h = 20 + 13 + 14 + fl_n * 14 + 14 + bl_n * 14 + 10
                entry_h = max(entry_h, 80)
                r = pygame.Rect(dx, dy, DETAIL_W - 28, entry_h)
                sel_s = sig_choice == i
                draw_rect_border(surf, r,
                                 PANEL_HIGHLIGHT if sel_s else PANEL_ALT,
                                 BORDER_ACTIVE if sel_s else BORDER)
                iy = dy + 6
                draw_text(surf, sig.name, 16, TEXT, dx + 8, iy)
                iy += 19
                # Type label
                _stype = "Passive" if sig.passive else "Active"
                _scol  = TYPE_PASSIVE_COL if sig.passive else TYPE_ACTIVE_COL
                draw_text(surf, _stype, 12, _scol, dx + 8, iy)
                iy += 14
                if same:
                    draw_text(surf, "FL & BL:", 13, CYAN, dx + 8, iy)
                    iy += 14
                    for line in fl_lines[:2]:
                        for wline in _wrap_text(line, 13, DETAIL_W - 52)[:2]:
                            _draw_rich_line(surf, f"  {wline}", 13, TEXT_DIM, dx + 8, iy, status_rects_out)
                            iy += 14
                else:
                    draw_text(surf, "Frontline:", 13, CYAN, dx + 8, iy)
                    iy += 14
                    for line in fl_lines[:2]:
                        for wline in _wrap_text(line, 13, DETAIL_W - 52)[:2]:
                            _draw_rich_line(surf, f"  {wline}", 13, TEXT_DIM, dx + 8, iy, status_rects_out)
                            iy += 14
                    draw_text(surf, "Backline:", 13, CYAN, dx + 8, iy)
                    iy += 14
                    for line in bl_lines[:2]:
                        for wline in _wrap_text(line, 13, DETAIL_W - 52)[:2]:
                            _draw_rich_line(surf, f"  {wline}", 13, TEXT_MUTED, dx + 8, iy, status_rects_out)
                            iy += 14
                clicks["sig"].append((r, i))
                dy += entry_h + 6

        elif sub_phase == "pick_basics":
            pool = class_basics.get(defn.cls, [])
            draw_text(surf, f"Choose 2 Basic Abilities ({len(basic_choices)}/2):",
                      18, CYAN, dx, dy)
            dy += 24
            list_top = dy
            list_bottom = DETAIL_Y + DETAIL_H - 95
            view_rect = pygame.Rect(dx, list_top, DETAIL_W - 28, max(0, list_bottom - list_top))
            # Compute per-ability heights
            def _basic_entry_h(ab):
                fl_l = _mode_detail_lines(ab.frontline)
                bl_l = _mode_detail_lines(ab.backline)
                def _n(lines): return sum(len(_wrap_text(l, 13, DETAIL_W - 56)[:2]) for l in lines[:2])
                # name (18) + type label (13) + section header + content + padding
                if _fl_bl_same(ab):
                    return max(18 + 13 + 13 + _n(fl_l) * 13 + 6, 75)
                return max(18 + 13 + 13 + _n(fl_l) * 13 + 13 + _n(bl_l) * 13 + 6, 95)
            ab_heights = [_basic_entry_h(ab) for ab in pool]
            unified_h = max(ab_heights) if ab_heights else 75
            content_h = len(pool) * (unified_h + 5)
            max_scroll = max(0, content_h - view_rect.height)
            scroll = max(0, min(scroll_offset, max_scroll))
            clicks["scroll_max"] = max_scroll
            clicks["scroll_viewport"] = view_rect
            prev_clip = surf.get_clip()
            surf.set_clip(view_rect)
            _ab_y = dy
            for i, ab in enumerate(pool):
                fl_lines = _mode_detail_lines(ab.frontline)
                bl_lines = _mode_detail_lines(ab.backline)
                same = _fl_bl_same(ab)
                entry_h = unified_h
                y_draw = _ab_y - scroll
                r = pygame.Rect(dx, y_draw, DETAIL_W - 28, entry_h)
                sel_b = i in basic_choices
                if r.bottom >= view_rect.top and r.top <= view_rect.bottom:
                    draw_rect_border(surf, r,
                                     PANEL_HIGHLIGHT if sel_b else PANEL_ALT,
                                     BORDER_ACTIVE if sel_b else BORDER)
                    iy = y_draw + 5
                    draw_text(surf, ab.name, 15, TEXT, dx + 8, iy)
                    iy += 17
                    # Type label
                    _abtype = "Passive" if ab.passive else "Active"
                    _abcol  = TYPE_PASSIVE_COL if ab.passive else TYPE_ACTIVE_COL
                    draw_text(surf, _abtype, 12, _abcol, dx + 8, iy)
                    iy += 13
                    if same:
                        draw_text(surf, "FL & BL:", 13, CYAN, dx + 8, iy)
                        iy += 13
                        for line in fl_lines[:2]:
                            for wline in _wrap_text(line, 13, DETAIL_W - 56)[:2]:
                                _draw_rich_line(surf, f"  {wline}", 13, TEXT_DIM, dx + 8, iy, status_rects_out)
                                iy += 13
                    else:
                        draw_text(surf, "FL:", 13, CYAN, dx + 8, iy)
                        iy += 13
                        for line in fl_lines[:2]:
                            for wline in _wrap_text(line, 13, DETAIL_W - 56)[:2]:
                                _draw_rich_line(surf, f"  {wline}", 13, TEXT_DIM, dx + 8, iy, status_rects_out)
                                iy += 13
                        draw_text(surf, "BL:", 13, CYAN, dx + 8, iy)
                        iy += 13
                        for line in bl_lines[:2]:
                            for wline in _wrap_text(line, 13, DETAIL_W - 56)[:2]:
                                _draw_rich_line(surf, f"  {wline}", 13, TEXT_MUTED, dx + 8, iy, status_rects_out)
                                iy += 13
                    clicks["basics"].append((r.copy(), i))
                _ab_y += entry_h + 5
            surf.set_clip(prev_clip)
            _draw_scroll_arrows(surf, view_rect, scroll, max_scroll)

        elif sub_phase == "pick_item":
            draw_text(surf, "Choose an Item:", 18, CYAN, dx, dy)
            dy += 24
            inner_w = DETAIL_W - 44
            # Compute taken item IDs from already-configured team members
            taken_item_ids = set()
            for _ti, _tp in enumerate(team_picks):
                if _ti < current_adv_idx and "item" in _tp:
                    taken_item_ids.add(_tp["item"].id)
            list_top = dy
            list_bottom = DETAIL_Y + DETAIL_H - 95
            view_rect = pygame.Rect(dx, list_top, DETAIL_W - 28, max(0, list_bottom - list_top))
            item_heights = []
            for i, item in enumerate(items):
                sel_i = item_choice == i
                desc_lines = _wrap_text(item.description, 13, inner_w)
                preview = desc_lines[: (3 if sel_i else 1)]
                # name row (to y+20) + type label (to y+33) + description lines + padding + dy gap
                item_heights.append(39 + len(preview) * 14)
            content_h = sum(item_heights)
            max_scroll = max(0, content_h - view_rect.height)
            scroll = max(0, min(scroll_offset, max_scroll))
            clicks["scroll_max"] = max_scroll
            clicks["scroll_viewport"] = view_rect
            prev_clip = surf.get_clip()
            surf.set_clip(view_rect)
            for i, item in enumerate(items):
                sel_i = item_choice == i
                is_taken = item.id in taken_item_ids
                tag = "[passive]" if item.passive else "[active]"
                desc_lines = _wrap_text(item.description, 13, inner_w)
                # Always show at least one description line for readability.
                preview = desc_lines[: (3 if sel_i else 1)]
                entry_h = 37 + len(preview) * 14
                y_draw = dy - scroll
                r = pygame.Rect(dx, y_draw, DETAIL_W - 28, entry_h)
                if r.bottom >= view_rect.top and r.top <= view_rect.bottom:
                    _itype_lbl = "Passive" if item.passive else "Active"
                    _itype_col = TYPE_PASSIVE_COL if item.passive else TYPE_ACTIVE_COL
                    if is_taken:
                        draw_rect_border(surf, r, (35, 35, 40), BORDER)
                        draw_text(surf, f"{item.name}  [taken]", 14, TEXT_MUTED, dx + 8, y_draw + 4)
                        draw_text(surf, _itype_lbl, 12, TEXT_MUTED, dx + 8, y_draw + 20)
                        iy = y_draw + 33
                        for line in preview:
                            _draw_rich_line(surf, line, 13, TEXT_MUTED, dx + 14, iy, status_rects_out)
                            iy += 14
                    else:
                        draw_rect_border(surf, r,
                                         PANEL_HIGHLIGHT if sel_i else PANEL_ALT,
                                         BORDER_ACTIVE if sel_i else BORDER)
                        draw_text(surf, item.name, 14,
                                  TEXT if sel_i else TEXT_DIM, dx + 8, y_draw + 4)
                        draw_text(surf, _itype_lbl, 12, _itype_col, dx + 8, y_draw + 20)
                        iy = y_draw + 33
                        for line in preview:
                            _draw_rich_line(surf, line, 13, TEXT_DIM if sel_i else TEXT_MUTED, dx + 14, iy, status_rects_out)
                            iy += 14
                    clicks["items"].append((r.copy(), i))
                dy += entry_h + 2
            surf.set_clip(prev_clip)
            _draw_scroll_arrows(surf, view_rect, scroll, max_scroll)

    # ── Confirm / instructions ────────────────────────────────────────────────
    if pre_battle_mode:
        inst = {
            "pick_adventurers": "Click a party slot below to edit their sets.",
            "pick_sig": "Select a Signature Ability, then confirm.",
            "pick_basics": "Select 2 Basic Abilities, then confirm.",
            "pick_item": "Select an Item (optional), then confirm.",
        }
    else:
        inst = {
            "pick_adventurers": "Click roster to add/remove members. Click a filled slot to edit their sets.",
            "pick_sig": "Select a Signature Ability, then confirm.",
            "pick_basics": "Select 2 Basic Abilities, then confirm.",
            "pick_item": "Select an Item (optional), then confirm.",
        }
    draw_text(surf, inst.get(sub_phase, ""), 15, TEXT_DIM,
              DETAIL_X + 14, DETAIL_Y + DETAIL_H - 80)

    def _team_valid(picks):
        return (len(picks) == 3 and
                all("signature" in pk and len(pk.get("basics", [])) == 2 for pk in picks))

    if sub_phase == "pick_adventurers":
        valid = _team_valid(team_picks)
        if valid:
            confirm_text = confirm_label
        else:
            confirm_text = "Not Ready"
        can_confirm = valid
    else:
        confirm_text = {
            "pick_sig": "Confirm Signature" if sig_choice is not None else "Pick a Signature",
            "pick_basics": "Confirm Basics" if len(basic_choices) == 2 else f"Need {2 - len(basic_choices)} more",
            "pick_item": "Confirm Item" if item_choice is not None else "Skip Item →",
        }.get(sub_phase, "Confirm")
        can_confirm = {
            "pick_sig": sig_choice is not None,
            "pick_basics": len(basic_choices) == 2,
            "pick_item": True,  # item is optional; always can confirm
        }.get(sub_phase, False)

    confirm_rect = pygame.Rect(DETAIL_X + DETAIL_W - 230, DETAIL_Y + DETAIL_H - 55,
                               220, 44)
    draw_button(surf, confirm_rect, confirm_text, mouse_pos,
                normal=BLUE_DARK, hover=BLUE, disabled=not can_confirm, size=18)
    if can_confirm:
        clicks["confirm"] = confirm_rect

    # Import Team button — only shown in pick_adventurers, not pre_battle_mode, not when a slot is focused
    if sub_phase == "pick_adventurers" and not pre_battle_mode and focused_slot is None:
        import_rect = pygame.Rect(DETAIL_X + 14, DETAIL_Y + DETAIL_H - 55, 180, 44)
        draw_button(surf, import_rect, "Import Party", mouse_pos,
                    normal=PANEL, hover=PANEL_HIGHLIGHT, border=BORDER_ACTIVE, size=16)
        clicks["import_btn"] = import_rect

    # Back button for sub-phases after pick_adventurers
    if sub_phase != "pick_adventurers":
        back_rect = pygame.Rect(DETAIL_X + 14, DETAIL_Y + DETAIL_H - 55, 160, 44)
        draw_button(surf, back_rect, "← Back", mouse_pos, size=16)
        clicks["back"] = back_rect

    return clicks


# ─────────────────────────────────────────────────────────────────────────────
# IMPORT TEAM MODAL
# ─────────────────────────────────────────────────────────────────────────────

def draw_import_modal(surf, text: str, error: str, mouse_pos) -> dict:
    """Draw a centered modal overlay for pasting/typing a team import string.

    Returns dict with keys:
        "confirm": pygame.Rect or None  (Import button, only when text is non-empty)
        "cancel":  pygame.Rect
    """
    # Semi-transparent dark overlay
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    surf.blit(overlay, (0, 0))

    # Modal box dimensions
    modal_w, modal_h = 700, 480
    mx = (WIDTH  - modal_w) // 2
    my = (HEIGHT - modal_h) // 2
    modal_rect = pygame.Rect(mx, my, modal_w, modal_h)

    draw_rect_border(surf, modal_rect, PANEL, BORDER_ACTIVE, 2)

    # Title
    draw_text(surf, "Import Party", 26, TEXT, mx + modal_w // 2, my + 18, center=True)

    # Instructions
    draw_text(surf, "Paste your party with Ctrl+V or type below:", 15, TEXT_DIM,
              mx + 16, my + 52)

    # Text area background
    text_area = pygame.Rect(mx + 14, my + 74, modal_w - 28, modal_h - 170)
    draw_rect_border(surf, text_area, (20, 22, 28), BORDER)

    # Render last ~12 lines of text with a cursor on the final line
    lines = text.split("\n") if text else [""]
    display_lines = lines[-12:]
    # Append cursor to last visible line
    if display_lines:
        display_lines = list(display_lines)
        display_lines[-1] = display_lines[-1] + "|"

    ty = text_area.y + 6
    line_h = 17
    for line in display_lines:
        if ty + line_h > text_area.bottom - 4:
            break
        draw_text(surf, line, 14, TEXT, text_area.x + 8, ty)
        ty += line_h

    # Error message
    if error:
        draw_text(surf, error, 16, RED, mx + modal_w // 2, my + modal_h - 100,
                  center=True)

    # Buttons
    cancel_rect  = pygame.Rect(mx + 14,                  my + modal_h - 56, 140, 42)
    confirm_rect = pygame.Rect(mx + modal_w - 14 - 180,  my + modal_h - 56, 180, 42)

    draw_button(surf, cancel_rect, "Cancel", mouse_pos, size=16)

    has_text = bool(text.strip())
    draw_button(surf, confirm_rect, "Import", mouse_pos,
                normal=BLUE_DARK, hover=BLUE, disabled=not has_text, size=16)

    return {
        "confirm": confirm_rect if has_text else None,
        "cancel":  cancel_rect,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SPECIAL ABILITY DESCRIPTIONS  (human-readable text for each special key)
# ─────────────────────────────────────────────────────────────────────────────
SPECIAL_DESCRIPTIONS: dict = {
    # Basic – Fighter
    "rend_back":                       "user's next ability against this target gains +10 Power",
    "cleave_back":                     "user's next ability against this target ignores 10% Defense",
    # Basic – Rogue
    "riposte_damage_reduction":        "user takes 50% less damage this round",
    "fleetfooted_front":               "first incoming ability each round deals 20% less damage",
    "fleetfooted_back":                "first incoming ability each round deals 10% less damage",
    # Basic – Warden
    "slam_bonus_if_guarded":           "+15 power if user is Guarded",
    "slam_back_guard":                 "Guards user for 2 rounds",
    "stalwart_front":                  "user takes -10 damage from abilities",
    "stalwart_back":                   "frontline ally takes -10 damage from abilities",
    "protection_front":                "allies have +10 Defense",
    "protection_back":                 "allies have +5 Defense",
    # Basic – Mage
    "arcane_wave_self_debuff":         "self: -10 Atk, -10 Def for 2 rounds",
    # Basic – Ranger
    "trapping_blow_root_weakened":     "Roots Weakened targets for 2 rounds",
    "hunters_mark_dot":                "target takes +10 damage from all abilities next round",
    # Basic – Cleric
    "medic_front":                     "healing effects cure status conditions and debuffs",
    "medic_back":                      "healing effects cure status conditions",
    # Risa
    "wolfs_pursuit_retarget":          "if target swaps, follow them with Wolf's Pursuit",
    "blood_hunt_hp_avg":               "sets Risa and target HP to the average of both",
    # Jack
    "belligerence_ignore_atk":         "Jack ignores 20% of enemy Attack",
    "magic_growth_power_buff":         "Jack's next ability gains +15 power",
    # Gretel
    "hot_mitts_front":                 "abilities Burn target (2r), or deal +10% damage to Burned targets",
    "hot_mitts_back":                  "abilities Burn target for 2 rounds",
    "crumb_trail_front":               "+20 power if an ally picked up a crumb this turn",
    "crumb_trail_drop":                "drop a crumb; allies who swap here heal 40 HP",
    "shove_over_next_atk_bonus":       "+15 power on next attack against this target",
    # Constantine
    "nine_lives":                      "up to 3x/battle: survive fatal damage at 1 HP (vs Exposed attackers)",
    "subterfuge_swap":                 "swap target and enemy after ability resolves",
    "final_deception":                 "Expose all enemies and steal 5 Atk from each for 2 rounds",
    # Hunold
    "hypnotic_aura_front":             "Shocked enemies' abilities are redirected to Hunold's back-left",
    "hypnotic_aura_back":              "Shocked enemies' abilities are redirected to Hunold's frontline",
    "devils_due":                      "Hunold uses one of his own abilities with spread, ignoring melee restriction and spread penalty",
    # Reynard
    "feign_weakness_retaliate_55":     "retaliate 55 power vs incoming attackers next round",
    "feign_weakness_retaliate_45":     "retaliate 45 power vs incoming attackers next round",
    "last_laugh":                      "retaliate 65 power + steal 10 speed (2r) vs incoming attackers",
    "cutpurse_swap_frontline":         "swap Reynard with frontline ally",
    # Roland
    "shimmering_valor_front":          "40% damage reduction for 3 rounds (ends when Roland swaps)",
    "shimmering_valor_back":           "Roland heals 55 HP + 15 HP per remaining Valor round",
    "taunt_target":                    "Taunt target for 2 rounds (forced to target Roland)",
    "taunt_front_ranged":              "Taunt front-most ranged enemy for 2 rounds",
    "banner_of_command":               "Guard ally for 2 rounds whenever they swap",
    # Porcus
    "nbth_self_reduce":                "Porcus takes 60% less damage this round",
    "nbth_ally_reduce":                "frontline ally takes 35% less damage this round",
    "porcine_honor_self":              "Guard Porcus for 1 round at the start of each round",
    "porcine_honor_ally":              "Guard frontline ally for 1 round at the start of each round",
    "sturdy_home_front":               "all allies have +7 Defense",
    "sturdy_home_back":                "frontline ally has +10 Defense",
    "unbreakable_defense":             "remove Porcus' statuses; double Defense for 2 rounds",
    # Lady
    "postmortem_passage":              "when ally is KO'd, they fire a 40-power attack at attacker",
    "drown_dmg_bonus":                 "target takes +10 damage from all sources for 2 rounds",
    "lakes_gift_pool_front":           "ally gains Reflecting Pool (2r) and +10 Atk (2r)",
    "lakes_gift_pool_back":            "ally gains Reflecting Pool (2r)",
    "journey_to_avalon":               "Lady is KO'd; revive one ally at 50% HP with Reflecting Pool (2r)",
    # Ella
    "dying_dance_front":               "Shocks Weakened targets for 2 rounds",
    "midnight_dour_swap":              "when reduced to ≤50% HP, Ella swaps with an ally (once per round)",
    "ella_ignore_two_lives":           "ignores Two Lives backline restriction",
    "struck_midnight_untargetable":    "Ella cannot act or be targeted until end of next round",
    # March Hare
    "rabbit_hole_extra_action":        "March Hare gains an extra action next round",
    "rabbit_hole_swap":                "March Hare swaps with an ally",
    "stitch_extra_action_now":         "March Hare gains an extra action this round",
    # Witch
    "toil_spread_status_right":        "spreads target's last status to enemy adjacent to their right",
    "cauldron_extend_status":          "increases target's status duration by 1 round",
    "crawling_abode":                  "+10 spd if frontline enemy is statused; 2+ statuses deal +10 dmg",
    "vile_sabbath_reapply":            "reapply last inflicted statuses to targets and refresh durations",
    # Briar Rose
    "garden_of_thorns_attack":         "enemies who attack Briar are Rooted for 2 rounds",
    "garden_of_thorns_swap":           "enemies that swap are Rooted for 2 rounds",
    "falling_kingdom":                 "refresh Root on Rooted foes (Weaken 2r); Root all others for 2r",
    # Frederic
    "heros_charge_ignore_pride_front": "ignore Heedless Pride incoming bonus damage this round",
    "slay_ignore_pride":               "ignore Heedless Pride incoming bonus damage this round",
    # Robin
    "spread_fortune_front":            "spread ability damage penalty is halved",
    "spread_fortune_back":             "spread abilities target all enemies",
    "bring_down_steal_atk":            "steal 10 Atk from target for 2r (if target is backline)",
    # Aldric
    "benefactor_front":                "healing effects restore 25% more HP",
    "benefactor_back":                 "healing effects restore 15% more HP",
    "sanctuary_front":                 "allies heal 1/10 max HP each round",
    "sanctuary_back":                  "frontline ally heals 1/12 max HP each round",
    "redemption":                      "+100 max HP; Aldric heals 50 HP at end of round for 2 rounds",
    # Liesl
    "cinder_blessing_avg":             "sets Liesl and ally HP to the average of both",
    "flame_of_renewal":                "when Liesl is KO'd, allies heal 1/2 max HP + Purifying Flame",
    "cleansing_inferno_burn_boost":    "vamp increases to 60% against Burned targets",
    # Aurora
    "toxin_purge_all":                 "remove all status conditions from Aurora or an ally",
    "toxin_purge_last":                "remove last inflicted status from Aurora or an ally",
    "birdsong_front":                  "at end of round, cure last inflicted status on Aurora and allies",
    "birdsong_back":                   "+5 Atk for 2r when Innocent Heart triggers (stacks up to x3)",
    "deathlike_slumber":               "Innocent Heart effect x2; recipient dormant 2r; cure Aurora's statuses",
    # Noble basics
    "summons_swap":                  "swap with an ally (cannot be used on consecutive turns)",
    "command_front":                 "enemies that attacked user last round take +10 damage from ally abilities",
    "command_back":                  "enemies that attacked allies last round take +10 damage from user's abilities",
    # Prince Charming (Noble)
    "condescend_back":               "next ability against target has +15 power",
    "gallant_charge_front":          "+20 power if Prince Charming was backline last round",
    "chosen_one":                    "first ally swapped with becomes champion; attackers take +25 from next ability",
    "happily_ever_after":            "gain +15 to each KO ally's highest non-HP stat for 2 rounds",
    # Green Knight (Noble)
    "heros_bargain_back":            "swap target with enemy frontline",
    "natural_order_front":           "+15 damage to targets that have not swapped for 2+ rounds",
    "natural_order_back":            "abilities vs unswapped targets do not increment ranged recharge",
    "awaited_blow_front":            "retaliate for 40 power vs incoming attackers not across from Green Knight",
    "awaited_blow_back":             "heal 40 HP at end of round",
    "fated_duel":                    "for 2 rounds, only Green Knight and the enemy across may act",
    # Rapunzel (Noble)
    "golden_snare_front":            "refresh Root duration on target",
    "lower_guard_front":             "+15 power if target has a stat debuff",
    "ivory_tower_front":             "ranged enemies have -10 defense",
    "ivory_tower_back":              "melee enemies have -10 attack",
    "severed_tether":                "Flowing Locks always active 2r; -15 def, +20 atk, +20 speed (2r)",
    # Warlock basics
    "warlock_gain_malice_1":          "gain 1 Malice",
    "warlock_spend1_weaken":         "spend 1 Malice to Weaken target for 2 rounds",
    "warlock_spend1_expose":         "spend 1 Malice to Expose target for 2 rounds",
    "blood_pact_front":              "lose 50 HP and gain 2 Malice",
    "blood_pact_back":               "heal 25 HP; spend 1 Malice to heal 25 more HP",
    "cursed_armor":                  "gain 1 Malice whenever damaged by an enemy ability",
    "void_step_front":               "on swapping to backline, gain 1 Malice",
    "void_step_back":                "on swapping to frontline, spend 2 Malice for +10 Spd (2r)",
    # Pinocchio (Warlock)
    "wooden_wallop_front":           "+5 power per Malice",
    "cut_strings_back":              "spend 2 Malice to Spotlight target for 2 rounds",
    "become_real_front":             "at 3+ Malice: abilities gain +15 damage; immune to statuses",
    "become_real_back":              "at 3+ Malice: abilities do not increment ranged recharge",
    "blue_faerie_boon":              "increase Malice cap by 6, gain 6 Malice, then heal 20 per Malice",
    # Rumpelstiltskin (Warlock)
    "straw_to_gold_front":           "steal ally's highest stat buff for 2r; +5 strength per Malice; return later",
    "straw_to_gold_back":            "convert an ally's highest stat debuff into a stat buff",
    "name_the_price_front":          "target gains +10 Atk for 2 rounds",
    "name_the_price_back":           "spend 2 Malice to nullify target's stat buffs for 2 rounds",
    "spinning_wheel_front":          "+7 ability damage per unique stat buff among all adventurers",
    "spinning_wheel_back":           "when an ally loses a stat buff, spend 2 Malice to refresh it",
    "thieve_the_first_born":         "steal all enemy stat buffs, refresh them, +5 value each per Malice",
    # Sea Wench Asha (Warlock)
    "misappropriate_front":          "spend 2 Malice to use enemy frontline signature (or gain passive for 2r)",
    "abyssal_call_front":            "spend 2 Malice: target gets -10 Def for 2 rounds",
    "abyssal_call_back":             "refresh target's existing stat debuffs",
    "faustian_bargain_front":        "on swap to frontline, spend 2 Malice to gain bottled talent for 2r",
    "faustian_bargain_back":         "on KO, bottle target's talent and gain +10 Spd for 2 rounds",
    "turn_to_foam":                  "gain 3 Malice, then consume all: enemies get -10 Def per Malice (2r)",
    # Items
    "smoke_bomb_swap":                 "user switches positions with an ally",
    "ancient_hourglass":               "user cannot act or be targeted next round (once per battle)",
    "holy_diadem":                     "once per battle: survive fatal damage at 1 HP, take no damage that round",
    "spiked_mail":                     "enemies that damage user take 15 damage",
}


def _fl_bl_same(ability) -> bool:
    """Return True if the frontline and backline effects are identical (and both available)."""
    if ability.frontline.unavailable or ability.backline.unavailable:
        return False
    return _mode_detail_lines(ability.frontline) == _mode_detail_lines(ability.backline)


def _mode_summary(mode) -> str:
    if mode.unavailable:
        return "n/a"
    summary = "; ".join(_mode_detail_lines(mode))
    return summary[:92] + "…" if len(summary) > 93 else summary


def _mode_detail_lines(mode) -> list:
    """Return a list of short descriptor strings for verbose ability display."""
    if mode.unavailable:
        return ["n/a"]
    parts = []
    if mode.power:
        s = f"{mode.power} power"
        if mode.spread:
            s += ", spread (50%)"
        if mode.def_ignore_pct:
            s += f", ignore {mode.def_ignore_pct}% def"
        if mode.ignore_guard:
            s += ", ignores Guard"
        if mode.cant_redirect:
            s += ", can't be redirected"
        parts.append(s)
    bonuses = []
    if mode.bonus_vs_low_hp:      bonuses.append(f"+{mode.bonus_vs_low_hp} vs <50%HP")
    if mode.bonus_vs_rooted:      bonuses.append(f"+{mode.bonus_vs_rooted}% dmg vs Rooted")
    if mode.bonus_if_not_acted:   bonuses.append(f"+{mode.bonus_if_not_acted} if target not acted")
    if mode.bonus_if_target_acted: bonuses.append(f"+{mode.bonus_if_target_acted} if target acted")
    if mode.bonus_vs_higher_hp:   bonuses.append(f"+{mode.bonus_vs_higher_hp} vs higher maxHP")
    if mode.bonus_vs_backline:    bonuses.append(f"+{mode.bonus_vs_backline} vs backline")
    if mode.bonus_vs_statused:    bonuses.append(f"+{mode.bonus_vs_statused} vs Exposed/Weakened")
    if bonuses:
        parts.append("  ".join(bonuses))
    if mode.double_vamp_no_base:
        parts.append("2× vamp (no base vamp on this ability)")
    elif mode.vamp:
        parts.append(f"{int(mode.vamp * 100)}% lifesteal")
    if mode.heal:         parts.append(f"heal {mode.heal}")
    if mode.heal_self:    parts.append(f"self-heal {mode.heal_self}")
    if mode.heal_lowest:  parts.append(f"heal lowest ally {mode.heal_lowest}")
    if mode.guard_self:         parts.append("guard self")
    if mode.guard_target:       parts.append("guard target")
    if mode.guard_all_allies:   parts.append("guard all allies")
    if mode.guard_frontline_ally: parts.append("guard frontline ally")
    for st, dur in [(mode.status, mode.status_dur),
                    (mode.status2, mode.status2_dur),
                    (mode.status3, mode.status3_dur)]:
        if st:
            parts.append(f"inflict {st} ({dur}r)")
    if mode.self_status:
        parts.append(f"self: {mode.self_status} ({mode.self_status_dur}r)")
    for stat, amt, dur in [
        ("atk", mode.atk_buff, mode.atk_buff_dur),
        ("spd", mode.spd_buff, mode.spd_buff_dur),
        ("def", mode.def_buff, mode.def_buff_dur),
    ]:
        if amt:
            if mode.guard_target:
                parts.append(f"+{amt} {stat} to target ({dur}r)")
            else:
                parts.append(f"+{amt} {stat} self ({dur}r)")
    for stat, amt, dur in [
        ("atk", mode.atk_debuff, mode.atk_debuff_dur),
        ("spd", mode.spd_debuff, mode.spd_debuff_dur),
        ("def", mode.def_debuff, mode.def_debuff_dur),
    ]:
        if amt:
            parts.append(f"-{amt} {stat} on target ({dur}r)")
    if mode.special:
        desc = SPECIAL_DESCRIPTIONS.get(mode.special,
                                        f"[{mode.special.replace('_', ' ')}]")
        parts.append(desc)
    return parts if parts else ["—"]


def _wrap_text(text: str, size: int, max_width: int) -> list:
    """Split text into lines that fit within max_width pixels."""
    f = font(size)
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = (current + " " + word).strip()
        if f.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ─────────────────────────────────────────────────────────────────────────────
# COMBATANT DETAIL PANEL  (battle-screen info view)
# ─────────────────────────────────────────────────────────────────────────────

BATTLE_DETAIL_RECT = pygame.Rect(20, 375, 550, 465)


def draw_combatant_detail(surf, unit: CombatantState,
                           rect: pygame.Rect = None,
                           status_rects_out: list = None) -> pygame.Rect:
    """
    Draw the full detail card for a combatant during the battle screen.
    Shows: stats, talent, signature, basics, item.
    Returns the close-button rect.
    """
    r = rect or BATTLE_DETAIL_RECT
    draw_rect_border(surf, r, PANEL, BORDER_ACTIVE, width=2)

    x, y = r.x + 12, r.y + 8
    w = r.width - 24

    # Close button
    close_rect = pygame.Rect(r.right - 26, r.y + 6, 20, 20)
    draw_rect_border(surf, close_rect, (70, 40, 40), RED_DARK)
    draw_text(surf, "×", 15, TEXT, close_rect.centerx, close_rect.centery, center=True)

    # ── Name + class + stats ─────────────────────────────────────────────────
    draw_text(surf, unit.name, 20, TEXT, x, y)
    _cdcr = draw_text(surf, cls_label(unit.cls), 14, TEXT_MUTED, r.right - 30, y + 4, right=True)
    if status_rects_out is not None:
        status_rects_out.append((_cdcr, unit.cls))
    y += 24
    draw_text(surf,
              f"HP {unit.hp}/{unit.max_hp}   "
              f"ATK {unit.get_stat('attack')}   "
              f"DEF {unit.get_stat('defense')}   "
              f"SPD {unit.get_stat('speed')}",
              13, TEXT_DIM, x, y)
    y += 18

    # ── Talent ───────────────────────────────────────────────────────────────
    draw_text(surf, f"Talent: {unit.defn.talent_name}", 14, YELLOW, x, y)
    y += 18
    for line in _wrap_text(unit.defn.talent_text, 13, w - 8):
        if y + 14 > r.bottom - 4:
            break
        _draw_rich_line(surf, line, 13, TEXT_DIM, x + 8, y, status_rects_out)
        y += 15
    y += 4

    # ── Signature ────────────────────────────────────────────────────────────
    pygame.draw.line(surf, BORDER, (x, y), (x + w, y), 1)
    y += 5
    draw_text(surf, "Signature  —  " + unit.sig.name, 14, CYAN, x, y)
    y += 17
    _stype = "Passive" if unit.sig.passive else "Active"
    _scol  = TYPE_PASSIVE_COL if unit.sig.passive else TYPE_ACTIVE_COL
    draw_text(surf, _stype, 12, _scol, x + 8, y)
    y += 14
    if _fl_bl_same(unit.sig):
        lines = _mode_detail_lines(unit.sig.frontline)
        _draw_rich_line(surf, f"FL & BL: {lines[0]}", 12, TEXT_DIM, x + 8, y, status_rects_out)
        y += 14
        for extra in lines[1:]:
            if y + 13 > r.bottom - 4:
                break
            _draw_rich_line(surf, f"         {extra}", 12, TEXT_MUTED, x + 8, y, status_rects_out)
            y += 13
    else:
        for prefix, mode in (("FL", unit.sig.frontline), ("BL", unit.sig.backline)):
            lines = _mode_detail_lines(mode)
            _draw_rich_line(surf, f"{prefix}: {lines[0]}", 12, TEXT_DIM, x + 8, y, status_rects_out)
            y += 14
            for extra in lines[1:]:
                if y + 13 > r.bottom - 4:
                    break
                _draw_rich_line(surf, f"      {extra}", 12, TEXT_MUTED, x + 8, y, status_rects_out)
                y += 13
    y += 4

    # ── Basics ───────────────────────────────────────────────────────────────
    pygame.draw.line(surf, BORDER, (x, y), (x + w, y), 1)
    y += 5
    draw_text(surf, "Basic Abilities", 14, CYAN, x, y)
    y += 17
    for ab in unit.basics:
        draw_text(surf, ab.name, 14, TEXT, x, y)
        y += 15
        _abtype = "Passive" if ab.passive else "Active"
        _abcol  = TYPE_PASSIVE_COL if ab.passive else TYPE_ACTIVE_COL
        draw_text(surf, _abtype, 12, _abcol, x + 8, y)
        y += 13
        if _fl_bl_same(ab):
            lines = _mode_detail_lines(ab.frontline)
            _draw_rich_line(surf, f"FL & BL: {lines[0]}", 12, TEXT_DIM, x + 8, y, status_rects_out)
            y += 13
            for extra in lines[1:]:
                if y + 12 > r.bottom - 4:
                    break
                _draw_rich_line(surf, f"         {extra}", 12, TEXT_MUTED, x + 8, y, status_rects_out)
                y += 12
        else:
            for prefix, mode in (("FL", ab.frontline), ("BL", ab.backline)):
                lines = _mode_detail_lines(mode)
                _draw_rich_line(surf, f"{prefix}: {lines[0]}", 12, TEXT_DIM, x + 8, y, status_rects_out)
                y += 13
                for extra in lines[1:]:
                    if y + 12 > r.bottom - 4:
                        break
                    _draw_rich_line(surf, f"      {extra}", 12, TEXT_MUTED, x + 8, y, status_rects_out)
                    y += 12
        y += 2

    # ── Item ─────────────────────────────────────────────────────────────────
    pygame.draw.line(surf, BORDER, (x, y), (x + w, y), 1)
    y += 5
    item = unit.item
    draw_text(surf, f"Item: {item.name}", 14, GREEN, x, y)
    y += 16
    # Type label + usage state
    if item.passive:
        _it_type = "Passive"
        _it_col  = TYPE_PASSIVE_COL
    else:
        _it_type = "Active"
        _it_col  = TYPE_ACTIVE_COL
    _it_state = ""
    if item.once_per_battle:
        _it_state = "  [used]" if unit.item_uses_left <= 0 else "  [once per battle]"
    draw_text(surf, _it_type + _it_state, 12, _it_col, x + 8, y)
    y += 14
    for line in _wrap_text(item.description, 13, w - 8):
        if y + 14 > r.bottom - 4:
            break
        _draw_rich_line(surf, line, 13, TEXT_DIM, x + 8, y, status_rects_out)
        y += 15

    return close_rect


# ─────────────────────────────────────────────────────────────────────────────
# RESULT SCREEN
# ─────────────────────────────────────────────────────────────────────────────

def draw_result_screen(surf, battle: BattleState, mouse_pos):
    surf.fill(BG)
    cx, cy = WIDTH // 2, HEIGHT // 2
    winner_name = battle.get_team(battle.winner).player_name if battle.winner else "?"
    draw_text(surf, "VICTORY!", 72, YELLOW, cx, cy - 120, center=True)
    draw_text(surf, f"{winner_name} wins!", 36, TEXT, cx, cy - 40, center=True)
    draw_text(surf, f"Battle lasted {battle.round_num} rounds.", 22, TEXT_DIM,
              cx, cy + 20, center=True)

    menu_btn   = pygame.Rect(cx - 160, cy + 90, 150, 52)
    rematch_btn = pygame.Rect(cx + 10,  cy + 90, 150, 52)
    draw_button(surf, menu_btn,    "Main Menu",  mouse_pos, size=20)
    draw_button(surf, rematch_btn, "Quit",       mouse_pos, size=20)
    return menu_btn, rematch_btn


# ─────────────────────────────────────────────────────────────────────────────
# TOP BAR (used during battle)
# ─────────────────────────────────────────────────────────────────────────────

def draw_top_bar(surf, battle: BattleState, phase_label: str):
    bar = pygame.Rect(0, 0, WIDTH, 55)
    pygame.draw.rect(surf, PANEL, bar)
    pygame.draw.line(surf, BORDER, (0, 55), (WIDTH, 55), 1)

    # Left: game title and round info
    draw_text(surf, "FABLED", 22, TEXT, 14, 14)
    draw_text(surf, f"Round {battle.round_num}", 20, YELLOW, 120, 17)
    draw_text(surf, f"Init: P{battle.init_player}", 16, CYAN, 240, 19)

    # Centre: matchup (clear gap from left items above)
    draw_text(surf, f"{battle.team1.player_name}  vs  {battle.team2.player_name}",
              18, TEXT, WIDTH // 2, 17, center=True)

    # Right: phase label — right-aligned so it never overlaps the centre text
    draw_text(surf, phase_label, 16, TEXT_DIM, WIDTH - 10, 19, right=True)


# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGN UI
# ─────────────────────────────────────────────────────────────────────────────

def _mission_is_unlocked(mission, profile) -> bool:
    """A mission is unlocked if its first quest is <= highest_quest_cleared + 1."""
    first_q = mission.quest_range[0]
    # Mission 1 is always available after quest 0 rewards are granted
    return first_q <= profile.highest_quest_cleared + 1


def _quest_is_unlocked(quest_id: int, profile) -> bool:
    """A quest is playable if the previous quest has been cleared (or it is quest 1)."""
    if quest_id <= 0:
        return True
    return profile.highest_quest_cleared >= quest_id - 1


def draw_campaign_mission_select(surf, missions: list, mouse_pos, profile) -> dict:
    """Show all 10 missions with lock/unlock status.  Returns click rects."""
    surf.fill(BG)
    cx = WIDTH // 2

    draw_text(surf, "FABLED — Quests", 48, TEXT, cx, 50, center=True)
    draw_text(surf, "Select a Quest", 24, TEXT_DIM, cx, 100, center=True)

    # Back button
    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    # Layout: 2 columns x 5 rows
    col_w  = 580
    col_h  = 130
    pad    = 16
    start_x = cx - col_w - pad // 2
    start_y = 140

    mission_btns = []
    missions_sorted = sorted(missions, key=lambda m: m.mission_id)
    # Skip mission 0 (prologue handled as quest 0 reward)
    display_missions = [m for m in missions_sorted if m.mission_id > 0]

    for idx, mission in enumerate(display_missions):
        col   = idx % 2
        row   = idx // 2
        rx    = start_x + col * (col_w + pad)
        ry    = start_y + row * (col_h + pad)
        rect  = pygame.Rect(rx, ry, col_w, col_h)

        unlocked = _mission_is_unlocked(mission, profile)
        first_q, last_q = mission.quest_range

        # Check if any quest in range is cleared
        any_cleared = any(profile.quest_cleared.get(q) for q in range(first_q, last_q + 1))
        all_cleared = all(profile.quest_cleared.get(q) for q in range(first_q, last_q + 1))

        if all_cleared:
            fill_col  = (35, 60, 35)
            bord_col  = GREEN
        elif unlocked:
            fill_col  = PANEL_ALT
            bord_col  = BORDER_ACTIVE
        else:
            fill_col  = (28, 28, 34)
            bord_col  = BORDER

        hov = rect.collidepoint(mouse_pos) and unlocked
        if hov:
            fill_col = PANEL_HIGHLIGHT

        draw_rect_border(surf, rect, fill_col, bord_col)

        if unlocked:
            draw_text(surf, mission.name, 20, TEXT if not all_cleared else GREEN,
                      rect.x + 14, rect.y + 10)
            draw_text(surf, f"Encounters {first_q}–{last_q}  |  Level {mission.level_range[0]}–{mission.level_range[1]}",
                      14, TEXT_DIM, rect.x + 14, rect.y + 36)
            # Wrap description within card width; cap at 2 lines
            desc_lines = _wrap_text(mission.description, 13, col_w - 28)
            for li, dl in enumerate(desc_lines[:2]):
                draw_text(surf, dl, 13, TEXT_MUTED, rect.x + 14, rect.y + 57 + li * 16)
            if all_cleared:
                draw_text(surf, "COMPLETE", 14, GREEN, rect.right - 100, rect.y + 10)
            elif any_cleared:
                cleared_count = sum(1 for q in range(first_q, last_q + 1)
                                    if profile.quest_cleared.get(q))
                total = last_q - first_q + 1
                draw_text(surf, f"{cleared_count}/{total} cleared", 13, YELLOW,
                          rect.right - 110, rect.y + 10)
            mission_btns.append((rect, mission.mission_id))
        else:
            draw_text(surf, "LOCKED", 22, TEXT_MUTED, rect.centerx, rect.centery, center=True)
            draw_text(surf, mission.name, 16, TEXT_MUTED, rect.x + 14, rect.y + 10)

    return {"mission_btns": mission_btns, "back_btn": back_btn}


def draw_quest_select(surf, mission, quests: list, mouse_pos, profile) -> dict:
    """Show quests within a mission.  Returns click rects."""
    surf.fill(BG)
    cx = WIDTH // 2

    draw_text(surf, f"FABLED — {mission.name}", 40, TEXT, cx, 45, center=True)

    # Wrap mission description so it never gets cut off
    desc_lines = _wrap_text(mission.description, 17, 900)
    desc_y = 90
    for dl in desc_lines:
        draw_text(surf, dl, 17, TEXT_DIM, cx, desc_y, center=True)
        desc_y += 22

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    # List quests vertically
    q_w   = 900
    q_h   = 95
    pad   = 12
    start_x = cx - q_w // 2
    start_y = max(130, desc_y + 10)

    quest_btns = []
    quests_sorted = sorted(quests, key=lambda q: q.quest_id)

    for idx, quest in enumerate(quests_sorted):
        ry   = start_y + idx * (q_h + pad)
        rect = pygame.Rect(start_x, ry, q_w, q_h)

        unlocked = _quest_is_unlocked(quest.quest_id, profile)
        cleared  = profile.quest_cleared.get(quest.quest_id, False)

        if cleared:
            fill_col = (30, 55, 30)
            bord_col = GREEN
        elif unlocked:
            fill_col = PANEL_ALT
            bord_col = BORDER_ACTIVE
        else:
            fill_col = (28, 28, 34)
            bord_col = BORDER

        hov = rect.collidepoint(mouse_pos) and unlocked
        if hov:
            fill_col = PANEL_HIGHLIGHT

        draw_rect_border(surf, rect, fill_col, bord_col)

        if unlocked:
            # Quest title — key_preview omitted for now; restore by appending:
            #   f"  —  {quest.key_preview}"
            draw_text(surf, f"Encounter {quest.quest_id}",
                      18, TEXT if not cleared else GREEN, rect.x + 14, rect.y + 10)
            # Reward summary
            reward_parts = []
            for item_id in quest.rewards.get("items", []):
                reward_parts.append(item_id.replace("_", " ").title())
            for entry in quest.rewards.get("recruit", []):
                reward_parts.append(f"Recruit {entry[0].replace('_', ' ').title()}")
            if quest.rewards.get("sig_tier"):
                reward_parts.append(f"Sig Tier {quest.rewards['sig_tier']}")
            if quest.rewards.get("basics_tier"):
                reward_parts.append(f"Basics Tier {quest.rewards['basics_tier']}")
            if quest.rewards.get("twists"):
                reward_parts.append("Unlock Twists")
            if quest.rewards.get("campaign_complete"):
                reward_parts.append("Campaign Complete!")
            reward_str = "Rewards: " + (", ".join(reward_parts) if reward_parts else "None")
            draw_text(surf, reward_str[:90], 13, YELLOW if reward_parts else TEXT_MUTED,
                      rect.x + 14, rect.y + 38)
            if cleared:
                draw_text(surf, "CLEARED", 14, GREEN, rect.right - 90, rect.y + 10)
            else:
                draw_text(surf, "Click to start", 13, TEXT_MUTED,
                          rect.right - 115, rect.y + 58)
            quest_btns.append((rect, quest.quest_id))
        else:
            draw_text(surf, f"Encounter {quest.quest_id}  —  LOCKED", 16, TEXT_MUTED,
                      rect.x + 14, rect.y + 36)

    return {"quest_btns": quest_btns, "back_btn": back_btn}


def draw_pre_quest(surf, quest_def, mission, quest_pos: int, total_quests: int,
                   enemy_picks: list, mouse_pos, status_rects_out: list = None) -> dict:
    """Show pre-battle screen with enemy lineup and reward preview."""
    surf.fill(BG)
    cx = WIDTH // 2

    back_btn  = pygame.Rect(20, 20, 100, 36)
    start_btn = pygame.Rect(cx - 130, HEIGHT - 80, 260, 55)
    draw_button(surf, back_btn,  "Back",          mouse_pos, size=16)
    draw_button(surf, start_btn, "Start Battle!", mouse_pos, size=22,
                normal=GREEN_DARK, hover=GREEN)

    # Header
    mission_name = mission.name if mission else "?"
    mission_id   = mission.mission_id if mission else "?"
    draw_text(surf, f"Quest {mission_id}  \u2014  {mission_name}",
              30, TEXT, cx, 42, center=True)
    # Quest position — key_preview omitted for now; restore by appending:
    #   f"  \u00b7  {quest_def.key_preview}"
    draw_text(surf, f"Encounter {quest_pos} / {total_quests}",
              18, TEXT_DIM, cx, 78, center=True)

    # Mission description — wrapped so it never gets cut off
    desc = mission.description if mission else ""
    desc_y = 105
    for line in _wrap_text(desc, 14, 1000):
        draw_text(surf, line, 14, TEXT_MUTED, cx, desc_y, center=True)
        desc_y += 18

    # Enemy lineup (3 cards side by side)
    slot_labels = ["Front", "Back Left", "Back Right"]
    card_w = 320
    card_h = 200
    total_w = card_w * 3 + 30
    card_start_x = cx - total_w // 2
    card_y = max(148, desc_y + 8)

    enemy_cards = []
    for i, pick in enumerate(enemy_picks):
        rx = card_start_x + i * (card_w + 15)
        rect = pygame.Rect(rx, card_y, card_w, card_h)
        hover = rect.collidepoint(mouse_pos)
        draw_rect_border(surf, rect, PANEL_ALT, BORDER_ACTIVE if hover else BORDER)
        enemy_cards.append((rect, pick))

        defn = pick["definition"]
        draw_text(surf, slot_labels[i], 14, TEXT_DIM, rect.x + 10, rect.y + 6)
        draw_text(surf, defn.name, 18, TEXT, rect.x + 10, rect.y + 24)
        _pqcr = draw_text(surf, cls_label(defn.cls), 14, YELLOW, rect.x + 10, rect.y + 46)
        if status_rects_out is not None:
            status_rects_out.append((_pqcr, defn.cls))
        draw_text(surf, f"HP {defn.hp}  ATK {defn.attack}  DEF {defn.defense}  SPD {defn.speed}",
                  13, TEXT_DIM, rect.x + 10, rect.y + 68)
        sig  = pick["signature"]
        b1, b2 = pick["basics"][0], pick["basics"][1]
        draw_text(surf, f"Sig: {sig.name}", 13, CYAN, rect.x + 10, rect.y + 90)
        draw_text(surf, f"Basics: {b1.name}, {b2.name}", 13, TEXT_DIM, rect.x + 10, rect.y + 110)
        item = pick["item"]
        if item.id != "no_item":
            draw_text(surf, f"Item: {item.name}", 13, ORANGE, rect.x + 10, rect.y + 130)
        if defn.talent_name and defn.talent_name != "—":
            draw_text(surf, f"Talent: {defn.talent_name}", 12, PURPLE, rect.x + 10, rect.y + 152)

    # Reward preview
    reward_y = card_y + card_h + 20
    draw_text(surf, "Rewards for Victory:", 18, TEXT_DIM, cx, reward_y, center=True)
    reward_y += 28

    rewards  = quest_def.rewards or {}
    parts    = []
    for item_id in rewards.get("items", []):
        parts.append(item_id.replace("_", " ").title())
    for entry in rewards.get("recruit", []):
        parts.append(f"Recruit {entry[0].replace('_', ' ').title()}")
    if rewards.get("sig_tier"):
        parts.append(f"Signature Tier {rewards['sig_tier']} unlocked")
    if rewards.get("basics_tier"):
        parts.append(f"Basics Tier {rewards['basics_tier']} unlocked")
    if rewards.get("twists"):
        parts.append("Twist abilities unlocked for all!")
    if rewards.get("campaign_complete"):
        parts.append("Campaign Complete! Ranked Glory unlocked!")
    if not parts:
        parts = ["No item rewards"]

    reward_text = "  |  ".join(parts)
    draw_text(surf, reward_text[:100], 16, YELLOW, cx, reward_y, center=True)

    return {"start_btn": start_btn, "back_btn": back_btn, "enemy_cards": enemy_cards}


def draw_post_quest(surf, quest_def, won: bool, rewards: dict, mouse_pos) -> dict:
    """Show post-battle rewards screen."""
    surf.fill(BG)
    cx, cy = WIDTH // 2, HEIGHT // 2

    if won:
        draw_text(surf, "VICTORY!", 72, YELLOW, cx, cy - 170, center=True)
        draw_text(surf, f"Encounter {quest_def.quest_id} Cleared!", 34, GREEN,
                  cx, cy - 85, center=True)

        # Show rewards
        draw_text(surf, "Rewards Gained:", 22, TEXT_DIM, cx, cy - 30, center=True)
        parts = []
        for item_id in rewards.get("items", []):
            parts.append(item_id.replace("_", " ").title())
        for entry in rewards.get("recruit", []):
            parts.append(f"Recruit {entry[0].replace('_', ' ').title()}")
        if rewards.get("sig_tier"):
            parts.append(f"Signature Tier {rewards['sig_tier']}")
        if rewards.get("basics_tier"):
            parts.append(f"Basics Tier {rewards['basics_tier']}")
        if rewards.get("twists"):
            parts.append("Twists Unlocked!")
        if rewards.get("ranked_glory"):
            parts.append("Ranked Glory Unlocked!")
        if rewards.get("campaign_complete"):
            parts.append("Campaign Complete!")
        if not parts:
            parts = ["Progress saved"]

        y_off = cy + 10
        for line in parts:
            draw_text(surf, line, 18, GREEN, cx, y_off, center=True)
            y_off += 26
    else:
        draw_text(surf, "DEFEATED", 72, RED, cx, cy - 120, center=True)
        draw_text(surf, "No rewards — try again!", 28, TEXT_DIM, cx, cy - 30, center=True)

    continue_btn = pygame.Rect(cx - 150, HEIGHT - 90, 300, 58)
    draw_button(surf, continue_btn, "Continue", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE)

    return {"continue_btn": continue_btn}


def draw_campaign_complete(surf, mouse_pos) -> dict:
    """Show campaign completion screen."""
    surf.fill(BG)
    cx, cy = WIDTH // 2, HEIGHT // 2

    draw_text(surf, "CAMPAIGN COMPLETE!", 64, YELLOW, cx, cy - 180, center=True)
    draw_text(surf, "You have defeated the Dragon and saved the realm!", 28, TEXT,
              cx, cy - 90, center=True)
    draw_text(surf, "Ranked Glory is now unlocked in the main menu.", 22, GREEN,
              cx, cy - 40, center=True)
    draw_text(surf, "Thank you for playing FABLED.", 20, TEXT_DIM, cx, cy + 10, center=True)

    menu_btn = pygame.Rect(cx - 150, cy + 80, 300, 58)
    draw_button(surf, menu_btn, "Return to Menu", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE)

    return {"menu_btn": menu_btn}


def _adv_damage_type(defn) -> str:
    """Return "melee", "ranged", or "mixed" for an adventurer definition."""
    role = defn.role  # "melee", "ranged", "warlock", "noble"
    if role == "melee":
        return "melee"
    elif role == "ranged":
        return "ranged"
    return "mixed"


def draw_catalog(surf, mouse_pos, active_tab: str, selected_idx,
                 scroll: int, profile, roster: list,
                 class_basics: dict, items: list,
                 status_rects_out: list = None,
                 filters: dict = None) -> dict:
    """
    Catalog screen — Adventurers / Basic Moves / Items tabs.
    filters: dict of active filter sets for the current tab, e.g.
             {"classes": {"Fighter"}, "damage_types": set()}
    Returns click dict with keys: back_btn, tab_btns, list_btns, scroll_max,
            scroll_viewport, filter_chips, clear_all_btn.
    """
    surf.fill(BG)
    cx = WIDTH // 2

    # ── Back + Title ──────────────────────────────────────────────────────────
    back_btn = pygame.Rect(20, 18, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)
    draw_text(surf, "Guidebook", 40, TEXT, cx, 28, center=True)

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_labels = [("adventurers", "Adventurers"), ("basics", "Basic Moves"), ("items", "Items")]
    tab_w, tab_h = 200, 38
    tabs_x = cx - (len(tab_labels) * tab_w + (len(tab_labels) - 1) * 8) // 2
    tab_y = 65
    tab_btns = []
    for i, (key, label) in enumerate(tab_labels):
        tr = pygame.Rect(tabs_x + i * (tab_w + 8), tab_y, tab_w, tab_h)
        is_active = (active_tab == key)
        fill = (55, 85, 110) if is_active else PANEL
        bord = BORDER_ACTIVE if is_active else BORDER
        draw_rect_border(surf, tr, fill, bord)
        draw_text(surf, label, 16, TEXT if is_active else TEXT_DIM,
                  tr.centerx, tr.centery, center=True)
        tab_btns.append((tr, key))

    # ── Layout ───────────────────────────────────────────────────────────────
    LIST_X, LIST_Y = 20, 118
    LIST_W, LIST_H = 360, 762
    DETAIL_PX, DETAIL_PY = 400, 118
    DETAIL_PW, DETAIL_PH = 980, 762
    FILTER_H = 94   # height of filter chips area above the list

    detail_rect_c = pygame.Rect(DETAIL_PX, DETAIL_PY, DETAIL_PW, DETAIL_PH)
    draw_rect_border(surf, detail_rect_c, PANEL, BORDER)

    # ── Build lists (unfiltered) ──────────────────────────────────────────────
    recruited = getattr(profile, "recruited", set())
    sig_tier = getattr(profile, "sig_tier", 3)
    twists_unlocked = getattr(profile, "twists_unlocked", False)
    unlocked_classes = getattr(profile, "unlocked_classes", set())
    basics_tier = getattr(profile, "basics_tier", 5)
    unlocked_items = getattr(profile, "unlocked_items", set())

    # Build basics-to-class map always (used by detail panel and filtering)
    _basics_cls_map = {}
    for _bcls, _babs in class_basics.items():
        for _bab in _babs:
            _basics_cls_map[_bab.id] = _bcls

    if active_tab == "adventurers":
        list_items = [d for d in roster if d.id in recruited]
    elif active_tab == "basics":
        pool = []
        for cls, abilities in class_basics.items():
            if cls in unlocked_classes:
                pool.extend(abilities[:basics_tier])
        list_items = pool
    else:  # items
        list_items = [it for it in items if it.id in unlocked_items]

    # ── Filter area ───────────────────────────────────────────────────────────
    _active_f = filters or {}
    _chip_w, _chip_h, _chip_gap = 84, 22, 4
    _row_h = _chip_h + _chip_gap
    _fx, _fy = LIST_X + 6, LIST_Y + 5
    _all_classes = ["Fighter", "Rogue", "Warden", "Mage", "Ranger", "Cleric", "Noble", "Warlock"]

    filter_chips = []
    clear_all_btn = None

    filter_rect = pygame.Rect(LIST_X, LIST_Y, LIST_W, FILTER_H)
    draw_rect_border(surf, filter_rect, PANEL, BORDER)

    def _draw_chip(text, rect, active):
        if active:
            bg, bd, tc = (45, 70, 100), BORDER_ACTIVE, TEXT
        elif rect.collidepoint(mouse_pos):
            bg, bd, tc = PANEL_ALT, BORDER, TEXT_DIM
        else:
            bg, bd, tc = (28, 30, 38), BORDER, TEXT_MUTED
        draw_rect_border(surf, rect, bg, bd, width=1)
        draw_text(surf, text, 11, tc, rect.centerx, rect.centery, center=True)

    if active_tab in ("adventurers", "basics"):
        _active_cls = _active_f.get("classes", set())
        for i, cls in enumerate(_all_classes):
            row, col = divmod(i, 4)
            r = pygame.Rect(_fx + col * (_chip_w + _chip_gap),
                            _fy + row * _row_h, _chip_w, _chip_h)
            _draw_chip(cls, r, cls in _active_cls)
            filter_chips.append((r, "classes", cls))
        _fy3 = _fy + 2 * _row_h
        if active_tab == "adventurers":
            _active_dt = _active_f.get("damage_types", set())
            for i, (lbl, val) in enumerate([("Melee", "melee"), ("Ranged", "ranged"), ("Mixed", "mixed")]):
                r = pygame.Rect(_fx + i * (_chip_w + _chip_gap), _fy3, _chip_w, _chip_h)
                _draw_chip(lbl, r, val in _active_dt)
                filter_chips.append((r, "damage_types", val))
        else:  # basics
            _active_types = _active_f.get("types", set())
            for i, (lbl, val) in enumerate([("Active", "active"), ("Passive", "passive")]):
                r = pygame.Rect(_fx + i * (_chip_w + _chip_gap), _fy3, _chip_w, _chip_h)
                _draw_chip(lbl, r, val in _active_types)
                filter_chips.append((r, "types", val))
        clear_all_btn = pygame.Rect(_fx + 3 * (_chip_w + _chip_gap), _fy3, _chip_w, _chip_h)
    else:  # items
        _active_types = _active_f.get("types", set())
        _fy_items = _fy + _row_h
        for i, (lbl, val) in enumerate([("Active", "active"), ("Passive", "passive")]):
            r = pygame.Rect(_fx + i * (_chip_w + _chip_gap), _fy_items, _chip_w, _chip_h)
            _draw_chip(lbl, r, val in _active_types)
            filter_chips.append((r, "types", val))
        clear_all_btn = pygame.Rect(_fx + 3 * (_chip_w + _chip_gap), _fy_items, _chip_w, _chip_h)

    _has_active_filters = any(bool(s) for s in _active_f.values() if isinstance(s, set))
    _ca_bg = (55, 28, 28) if _has_active_filters else (28, 30, 38)
    _ca_bd = (160, 80, 60) if _has_active_filters else BORDER
    _ca_tc = (210, 130, 110) if _has_active_filters else TEXT_MUTED
    draw_rect_border(surf, clear_all_btn, _ca_bg, _ca_bd, width=1)
    draw_text(surf, "Clear All", 11, _ca_tc, clear_all_btn.centerx, clear_all_btn.centery, center=True)

    # ── Apply active filters to list ──────────────────────────────────────────
    if active_tab == "adventurers":
        if _active_f.get("classes"):
            list_items = [x for x in list_items if x.cls in _active_f["classes"]]
        if _active_f.get("damage_types"):
            list_items = [x for x in list_items if _adv_damage_type(x) in _active_f["damage_types"]]
    elif active_tab == "basics":
        if _active_f.get("classes"):
            list_items = [x for x in list_items if _basics_cls_map.get(x.id) in _active_f["classes"]]
        if _active_f.get("types"):
            list_items = [x for x in list_items if ("passive" if x.passive else "active") in _active_f["types"]]
    else:  # items
        if _active_f.get("types"):
            list_items = [x for x in list_items if ("passive" if x.passive else "active") in _active_f["types"]]

    # ── Draw list (left panel, below filter area) ─────────────────────────────
    actual_list_y = LIST_Y + FILTER_H
    actual_list_h = LIST_H - FILTER_H
    list_view = pygame.Rect(LIST_X, actual_list_y, LIST_W, actual_list_h)
    draw_rect_border(surf, list_view, PANEL, BORDER)

    ITEM_H = 52 if active_tab == "adventurers" else 42
    content_h = len(list_items) * (ITEM_H + 4)
    scroll_max = max(0, content_h - actual_list_h + 8)
    scroll = max(0, min(scroll, scroll_max))

    prev_clip = surf.get_clip()
    surf.set_clip(list_view)
    list_btns = []
    y = actual_list_y + 6 - scroll
    for i, item in enumerate(list_items):
        r = pygame.Rect(LIST_X + 6, y, LIST_W - 12, ITEM_H)
        if r.bottom >= actual_list_y and r.top <= actual_list_y + actual_list_h:
            is_sel = (selected_idx == i)
            if active_tab == "adventurers":
                _item_cls = item.cls
            elif active_tab == "basics":
                _item_cls = _basics_cls_map.get(item.id)
            else:
                _item_cls = None
            cls_fill = CLASS_COLORS.get(_item_cls, PANEL) if _item_cls else PANEL
            if is_sel:
                fill = tuple(min(255, c + 24) for c in cls_fill)
            elif r.collidepoint(mouse_pos):
                fill = tuple(min(255, c + 16) for c in cls_fill)
            else:
                fill = cls_fill
            bord = BORDER_ACTIVE if is_sel else BORDER
            draw_rect_border(surf, r, fill, bord)
            if active_tab == "adventurers":
                draw_text(surf, item.name, 15, TEXT, r.x + 8, r.y + 6)
                _catcr = draw_text(surf, cls_label(item.cls), 13, CLASS_TEXT_COLORS.get(item.cls, TEXT_MUTED), r.x + 8, r.y + 24)
                if status_rects_out is not None:
                    status_rects_out.append((_catcr, item.cls))
                draw_text(surf, f"HP {item.hp}  ATK {item.attack}  DEF {item.defense}  SPD {item.speed}",
                          11, TEXT_DIM, r.x + 8, r.y + 38)
            elif active_tab == "basics":
                tag = "  [passive]" if item.passive else ""
                draw_text(surf, item.name + tag, 15, TEXT, r.x + 8, r.y + 6)
                draw_text(surf, _item_cls or item.category.title(), 12, CLASS_TEXT_COLORS.get(_item_cls, TEXT_MUTED), r.x + 8, r.y + 24)
            else:
                tag = "  [passive]" if item.passive else "  [active]"
                draw_text(surf, item.name + tag, 15, TEXT, r.x + 8, r.y + 6)
                draw_text(surf, item.description[:44] + ("…" if len(item.description) > 44 else ""),
                          11, TEXT_MUTED, r.x + 8, r.y + 24)
        list_btns.append((r, i))
        y += ITEM_H + 4
    surf.set_clip(prev_clip)

    if scroll_max > 0:
        # Scroll bar hint
        bar_x = LIST_X + LIST_W - 8
        bar_ratio = actual_list_h / max(content_h, 1)
        bar_h = max(30, int(actual_list_h * bar_ratio))
        bar_y = actual_list_y + int(scroll / max(scroll_max, 1) * (actual_list_h - bar_h))
        pygame.draw.rect(surf, BORDER, pygame.Rect(bar_x, bar_y, 4, bar_h), border_radius=2)

    # ── Draw detail panel (right) ─────────────────────────────────────────────
    if selected_idx is not None and 0 <= selected_idx < len(list_items):
        item = list_items[selected_idx]
        dx = DETAIL_PX + 16
        dy = DETAIL_PY + 14
        dw = DETAIL_PW - 32
        bottom_limit = DETAIL_PY + DETAIL_PH - 10

        def _dline(surf, text, size, color, x, y, indent=0, rich=False):
            if y + size + 2 > bottom_limit:
                return y
            if rich:
                _draw_rich_line(surf, text, size, color, x + indent, y, status_rects_out)
            else:
                draw_text(surf, text, size, color, x + indent, y)
            return y + size + 3

        def _dsep(surf, y):
            if y + 6 > bottom_limit:
                return y
            pygame.draw.line(surf, BORDER, (dx, y + 3), (dx + dw, y + 3), 1)
            return y + 8

        if active_tab == "adventurers":
            # Name + class
            draw_text(surf, item.name, 26, TEXT, dx, dy)
            _catdcr = draw_text(surf, cls_label(item.cls), 16, TEXT_MUTED, DETAIL_PX + DETAIL_PW - 20, dy + 4, right=True)
            if status_rects_out is not None:
                status_rects_out.append((_catdcr, item.cls))
            dy += 32
            # Stats
            dy = _dline(surf, f"HP {item.hp}   ATK {item.attack}   DEF {item.defense}   SPD {item.speed}",
                        15, TEXT, dx, dy)
            dy += 4
            # Talent
            dy = _dline(surf, f"Talent: {item.talent_name}", 15, YELLOW, dx, dy)
            for line in _wrap_text(item.talent_text, 13, dw - 8):
                dy = _dline(surf, line, 13, TEXT_DIM, dx, dy, indent=8, rich=True)
            dy = _dsep(surf, dy + 2)

            # Signature abilities
            avail_sigs = item.sig_options[:sig_tier]
            dy = _dline(surf, f"Signatures  ({len(avail_sigs)} of {len(item.sig_options)} unlocked):",
                        15, CYAN, dx, dy)
            dy += 2
            for sig in avail_sigs:
                tag = "  [passive]" if sig.passive else ""
                dy = _dline(surf, sig.name + tag, 15, TEXT, dx, dy, indent=4)
                for prefix, mode in (("FL", sig.frontline), ("BL", sig.backline)):
                    lines = _mode_detail_lines(mode)
                    dy = _dline(surf, f"  {prefix}: {lines[0]}", 13, TEXT_DIM, dx, dy, indent=12, rich=True)
                    for extra in lines[1:3]:
                        dy = _dline(surf, f"      {extra}", 12, TEXT_MUTED, dx, dy, indent=12, rich=True)
                dy += 2
            dy = _dsep(surf, dy + 2)

            # Twist
            if twists_unlocked:
                twist = item.twist
                dy = _dline(surf, f"Twist: {twist.name}", 15, ORANGE, dx, dy)
                for prefix, mode in (("FL", twist.frontline), ("BL", twist.backline)):
                    lines = _mode_detail_lines(mode)
                    dy = _dline(surf, f"  {prefix}: {lines[0]}", 13, TEXT_DIM, dx, dy, indent=12, rich=True)
                    for extra in lines[1:3]:
                        dy = _dline(surf, f"      {extra}", 12, TEXT_MUTED, dx, dy, indent=12, rich=True)
            else:
                dy = _dline(surf, "Twist: (not yet unlocked)", 14, TEXT_MUTED, dx, dy)

        elif active_tab == "basics":
            tag = "  [passive]" if item.passive else ""
            draw_text(surf, item.name + tag, 26, TEXT, dx, dy)
            dy += 34
            _bab_cls = _basics_cls_map.get(item.id)
            if _bab_cls:
                dy = _dline(surf, _bab_cls, 15, CLASS_TEXT_COLORS.get(_bab_cls, TEXT_MUTED), dx, dy)
                dy += 4
            for prefix, mode in (("Frontline", item.frontline), ("Backline", item.backline)):
                dy = _dline(surf, prefix + ":", 15, CYAN, dx, dy)
                lines = _mode_detail_lines(mode)
                for line in lines:
                    for wl in _wrap_text(line, 13, dw - 20):
                        dy = _dline(surf, wl, 13, TEXT_DIM, dx, dy, indent=12, rich=True)
                dy += 4

        else:  # items
            tag = "[passive]" if item.passive else "[active]"
            draw_text(surf, f"{item.name}  {tag}", 26, TEXT, dx, dy)
            dy += 34
            for line in _wrap_text(item.description, 14, dw):
                dy = _dline(surf, line, 14, TEXT_DIM, dx, dy, rich=True)
    else:
        # Placeholder
        hint = {
            "adventurers": "Click an adventurer to view details.",
            "basics": "Click a basic ability to view details.",
            "items": "Click an item to view details.",
        }.get(active_tab, "")
        draw_text(surf, hint, 18, TEXT_MUTED,
                  DETAIL_PX + DETAIL_PW // 2, DETAIL_PY + DETAIL_PH // 2, center=True)

    return {
        "back_btn": back_btn,
        "tab_btns": tab_btns,
        "list_btns": list_btns,
        "scroll_max": scroll_max,
        "scroll_viewport": list_view,
        "filter_chips": filter_chips,
        "clear_all_btn": clear_all_btn,
    }


def draw_pre_battle_review(surf, picks: list, selected_slot, mouse_pos, status_rects_out: list = None) -> dict:
    """Screen shown after team pick, before battle — lets player swap slot positions.

    picks: list of 3 dicts (definition, signature, basics, item)
    Returns {"slot_btns": [(rect, idx)], "start_btn": rect, "back_btn": rect}
    """
    surf.fill(BG)
    draw_text(surf, "Formation Review", 38, TEXT, WIDTH // 2, 50, center=True)
    draw_text(surf, "Click two slots to swap their positions, then start the battle.",
              17, TEXT_DIM, WIDTH // 2, 96, center=True)

    slot_labels = ["Front", "Back Left", "Back Right"]
    card_w, card_h = 330, 240
    total_w = card_w * 3 + 60
    start_x = (WIDTH - total_w) // 2
    card_y = 130
    slot_btns = []

    for i, pick in enumerate(picks):
        x = start_x + i * (card_w + 30)
        rect = pygame.Rect(x, card_y, card_w, card_h)
        is_sel = (selected_slot == i)
        _pdefn = pick.get("definition")
        _cls_fill = CLASS_COLORS.get(_pdefn.cls, PANEL_ALT) if _pdefn else PANEL_ALT
        fill = tuple(min(255, c + 24) for c in _cls_fill) if is_sel else tuple(min(255, c + 10) for c in _cls_fill)
        border = BORDER_ACTIVE if is_sel else BORDER
        draw_rect_border(surf, rect, fill, border, width=3 if is_sel else 2)

        defn = pick.get("definition")
        sig  = pick.get("signature")
        basics = pick.get("basics", [])
        item = pick.get("item")

        dy = card_y + 10
        lbl_col = CYAN if is_sel else TEXT_MUTED
        draw_text(surf, slot_labels[i], 15, lbl_col, x + 12, dy)
        dy += 22
        if defn:
            draw_text(surf, defn.name, 20, TEXT, x + 12, dy)
            dy += 26
            _pbcr = draw_text(surf, cls_label(defn.cls), 13, CLASS_TEXT_COLORS.get(defn.cls, TEXT_MUTED), x + 12, dy)
            if status_rects_out is not None:
                status_rects_out.append((_pbcr, defn.cls))
            draw_text(surf, f"   HP {defn.hp}  ATK {defn.attack}  DEF {defn.defense}  SPD {defn.speed}",
                      13, TEXT_DIM, x + 12 + font(13).size(cls_label(defn.cls))[0], dy)
            dy += 20
            if sig:
                draw_text(surf, f"Sig: {sig.name}", 14, YELLOW, x + 12, dy)
                dy += 18
            for b in basics:
                draw_text(surf, f"Basic: {b.name}", 13, TEXT_DIM, x + 12, dy)
                dy += 16
            if item:
                draw_text(surf, f"Item: {item.name}", 13, (160, 200, 160), x + 12, dy)
        else:
            draw_text(surf, "(empty)", 18, TEXT_MUTED, x + 12, dy)

        slot_btns.append((rect, i))

    back_btn  = pygame.Rect(WIDTH // 2 - 400, HEIGHT - 70, 200, 46)
    edit_btn  = pygame.Rect(WIDTH // 2 - 100, HEIGHT - 70, 200, 46)
    start_btn = pygame.Rect(WIDTH // 2 + 200, HEIGHT - 70, 200, 46)
    draw_button(surf, back_btn,  "← Back", mouse_pos, size=16,
                normal=PANEL, hover=PANEL_HIGHLIGHT)
    draw_button(surf, edit_btn,  "Edit Party Loadout", mouse_pos, size=16,
                normal=(50, 70, 50), hover=(65, 95, 65))
    draw_button(surf, start_btn, "Start Battle →", mouse_pos, size=18,
                normal=BLUE_DARK, hover=BLUE)
    return {"slot_btns": slot_btns, "start_btn": start_btn, "back_btn": back_btn, "edit_btn": edit_btn}


def draw_pvp_mode_select(surf, mouse_pos) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "vs Player", 48, TEXT, cx, 80, center=True)
    draw_text(surf, "Choose how you want to play.", 18, TEXT_DIM, cx, 145, center=True)

    same_pc_btn = pygame.Rect(cx - 150, 220, 300, 62)
    lan_btn     = pygame.Rect(cx - 150, 298, 300, 62)
    back_btn    = pygame.Rect(20, 20, 100, 36)

    draw_button(surf, same_pc_btn, "Same PC",        mouse_pos, size=22,
                normal=(55, 70, 120), hover=(72, 95, 160), border=BORDER_ACTIVE)
    draw_button(surf, lan_btn,     "LAN (Two PCs)",  mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE)
    draw_button(surf, back_btn,    "Back",           mouse_pos, size=16)

    return {"same_pc_btn": same_pc_btn, "lan_btn": lan_btn, "back_btn": back_btn}


def draw_lan_lobby(surf, mouse_pos, *, role=None, ip_input="",
                   status="", local_ip="", connecting=False) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "LAN Battle", 48, TEXT, cx, 60, center=True)

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    btns = {"back_btn": back_btn}

    if role is None:
        # Role selection
        draw_text(surf, "Are you hosting or joining?", 22, TEXT_DIM, cx, 150, center=True)
        host_btn = pygame.Rect(cx - 160, 220, 300, 62)
        join_btn = pygame.Rect(cx - 160, 298, 300, 62)
        draw_button(surf, host_btn, "Host Game", mouse_pos, size=22,
                    normal=BLUE_DARK, hover=BLUE)
        draw_button(surf, join_btn, "Join Game", mouse_pos, size=22,
                    normal=(55, 70, 120), hover=(72, 95, 160), border=BORDER_ACTIVE)
        btns["host_btn"] = host_btn
        btns["join_btn"] = join_btn

    elif role == "host":
        draw_text(surf, "Waiting for opponent to connect...", 22, YELLOW, cx, 150, center=True)
        if local_ip:
            draw_text(surf, f"Your IP address:  {local_ip}", 26, CYAN, cx, 210, center=True)
            draw_text(surf, "Share this IP with the other player.", 16, TEXT_DIM, cx, 248, center=True)
        if status:
            draw_text(surf, status, 18, GREEN, cx, 300, center=True)

    elif role == "client":
        draw_text(surf, "Enter the host's IP address:", 22, TEXT_DIM, cx, 150, center=True)
        # IP input box
        box = pygame.Rect(cx - 160, 190, 320, 48)
        pygame.draw.rect(surf, PANEL_ALT, box, border_radius=6)
        pygame.draw.rect(surf, BORDER_ACTIVE, box, width=2, border_radius=6)
        draw_text(surf, ip_input if ip_input else "192.168.x.x", 22,
                  TEXT if ip_input else TEXT_MUTED, cx, box.centery, center=True)
        btns["ip_box"] = box

        if connecting:
            draw_text(surf, "Connecting...", 18, YELLOW, cx, 260, center=True)
        else:
            connect_btn = pygame.Rect(cx - 110, 258, 220, 48)
            draw_button(surf, connect_btn, "Connect", mouse_pos, size=20,
                        normal=BLUE_DARK, hover=BLUE)
            btns["connect_btn"] = connect_btn

        if status:
            col = RED if "fail" in status.lower() or "error" in status.lower() or "refused" in status.lower() or "timed" in status.lower() else GREEN
            draw_text(surf, status, 16, col, cx, 326, center=True)

    return btns
