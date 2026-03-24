"""
ui.py â€“ all drawing functions for the Fabled prototype.
Pure rendering; no game-state mutations.
"""
import re
import pygame
from settings import *
from models import CombatantState, TeamState, BattleState
from data import ARTIFACTS_BY_ID, LEGACY_ITEM_TO_ARTIFACT_ID
from progression import (
    adventurer_level_from_clears,
    adventurer_sigil_unlocked,
    class_sigil_unlocked,
    class_basics_unlocked_count,
    class_level_from_points,
    exp_to_next_level,
    player_level_from_exp,
    player_sigil_unlocked,
    saved_team_slot_count,
    total_exp_for_level,
    twist_unlocked,
    unlocked_signature_count,
)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CLASS COLORS  (subtle tints for small adventurer cards/list items)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
TYPE_ACTIVE_COL  = (174, 170, 160)  # "Active"  label â€” muted warm grey
TYPE_PASSIVE_COL = (158, 165, 192)  # "Passive" label â€” muted steel blue

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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# NAME HELPERS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    # Rule 3: " the " / " of " suffix â€” pick the earliest
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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FONT CACHE
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_font_cache: dict = {}

def font(size: int) -> pygame.font.Font:
    if size not in _font_cache:
        try:
            _font_cache[size] = pygame.font.SysFont("consolas", size)
        except Exception:
            _font_cache[size] = pygame.font.Font(None, size)
    return _font_cache[size]


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PRIMITIVES
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UNIT BOX
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

STATUS_TOOLTIPS = {
    "burn":      "Burn: takes 8% max HP damage at end of each round.",
    "root":      "Root: cannot perform the Swap action.",
    "shock":     "Shock: -15 Speed and this adventurer must recharge after two abilities.",
    "weaken":    "Weaken: deals 15% less damage.",
    "expose":    "Expose: takes 15% more damage.",
    "guard":     "Guard: takes 15% less damage.",
    "spotlight": "Spotlight: can be targeted by melee abilities in the backline.",
    "no_heal":   "No Heal: cannot receive any healing.",
    "dormant":   "Dormant: cannot act or be targeted.",
    "reflecting_pool": "Reflecting Pool: reflects 12-15% of incoming damage back to attacker.",
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

# Maps word variants found in description text â†’ canonical status key
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
    """Draw â†‘/â†“ arrows at top/bottom right of a scrollable viewport."""
    if max_scroll <= 0:
        return
    x = view_rect.right - 16
    if scroll > 0:
        draw_text(surf, "â†‘", 14, TEXT_MUTED, x, view_rect.top + 2)
    if scroll < max_scroll:
        draw_text(surf, "â†“", 14, TEXT_MUTED, x, view_rect.bottom - 16)


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


def draw_artifact_tooltip(surf, artifact, tip_x: int, tip_y: int):
    """Draw a floating tooltip with an artifact's full description."""
    header = artifact.name
    meta = f"{'Reactive' if artifact.reactive else 'Active'}  |  Cooldown {artifact.cooldown}"
    desc_lines = _wrap_text(artifact.description, 13, 320) or [artifact.description]
    f_header = font(14)
    f_meta = font(12)
    f_body = font(13)
    widths = [f_header.size(header)[0], f_meta.size(meta)[0]]
    widths.extend(f_body.size(line)[0] for line in desc_lines)
    tw = min(380, max(widths) + 22)
    th = 14 + 18 + 16 + len(desc_lines) * 16 + 10
    x = min(tip_x + 8, WIDTH - tw - 6)
    y = max(6, tip_y - th - 8)
    tip_rect = pygame.Rect(x, y, tw, th)
    pygame.draw.rect(surf, (18, 20, 28), tip_rect, border_radius=6)
    pygame.draw.rect(surf, ORANGE, tip_rect, 1, border_radius=6)
    draw_text(surf, header, 14, TEXT, x + 10, y + 8)
    draw_text(
        surf,
        meta,
        12,
        TYPE_PASSIVE_COL if artifact.reactive else TYPE_ACTIVE_COL,
        x + 10,
        y + 26,
    )
    body_y = y + 44
    for line in desc_lines:
        draw_text(surf, line, 13, TEXT_DIM, x + 10, body_y)
        body_y += 16


def draw_artifact_name_list(
    surf,
    prefix: str,
    artifacts: list,
    *,
    size: int,
    prefix_color,
    artifact_color,
    x: int,
    y: int,
    artifact_rects_out: list | None = None,
    max_width: int = 9999,
    center: bool = False,
    right: bool = False,
    line_gap: int = 4,
):
    """Draw a prefix plus hoverable artifact names, wrapping by artifact token."""
    if not artifacts:
        draw_text(surf, prefix + "None", size, prefix_color, x, y, center=center, right=right)
        return y + size + line_gap

    f = font(size)
    segments = [(prefix, prefix_color, None)]
    for idx, artifact in enumerate(artifacts):
        segments.append((artifact.name, artifact_color, artifact))
        if idx < len(artifacts) - 1:
            segments.append((", ", prefix_color, None))

    lines = []
    current = []
    current_w = 0
    for text, color, artifact in segments:
        seg_w = f.size(text)[0]
        if current and current_w + seg_w > max_width:
            lines.append((current, current_w))
            current = []
            current_w = 0
        current.append((text, color, artifact, seg_w))
        current_w += seg_w
    if current:
        lines.append((current, current_w))

    cy = y
    for segs, total_w in lines:
        if center:
            cx = x - total_w // 2
        elif right:
            cx = x - total_w
        else:
            cx = x
        for text, color, artifact, seg_w in segs:
            rect = draw_text(surf, text, size, color, cx, cy)
            if artifact is not None and artifact_rects_out is not None:
                artifact_rects_out.append((rect, artifact))
            cx += seg_w
        cy += size + line_gap
    return cy


INTRO_TEXTS = [
    "Welcome to Fantasia. You are a wealthy magnate with a fondness for collecting rare artifacts, but quests are for other people.",
    "Fortunately, Fantasia is full of thrill-seeking adventurers willing to fight on your behalf if the pay is right.",
    "You are not the only rich collector in the kingdom, so every battle is a race to claim the best finds before a rival does.",
    "Head to the Tavern, hire a party, and start bringing rare artifacts home in your name.",
]


def draw_intro_popup(surf, visible_count: int, mouse_pos):
    """Draw the sequential intro story popup.

    visible_count: how many text sections are currently shown (1â€“4).
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

    # Background + border â€” each state has a distinct colour
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
        pygame.draw.circle(surf, GREEN, (rect.x + 10, rect.y + 10), 5)

    x = rect.x + 8
    w = rect.width - 16

    # Slot label â€” own top row; midright y accounts for center-anchor
    if show_slot:
        slot_lbl = SLOT_LABELS.get(unit.slot, unit.slot)
        draw_text(surf, slot_lbl, 13, TEXT_MUTED, rect.right - 8,
                  rect.y + 14, right=True)

    # Name starts below the slot label
    y = rect.y + 25
    name_color = RED if unit.ko else (TEXT_DIM if unit.untargetable else TEXT)
    draw_text(surf, short_name(unit.name), 17, name_color, x, y)
    y += 22

    # Class
    _clsr = draw_text(surf, cls_label(unit.cls), 13, TEXT_MUTED, x, y)
    if status_rects_out is not None:
        status_rects_out.append((_clsr, unit.cls))
    y += 18

    if unit.ko:
        draw_text(surf, "KO'd", 20, RED, rect.centerx, rect.centery, center=True)
        return

    # HP bar â€” text centered inside via center=True (y = bar vertical midpoint)
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
    draw_text(surf, f"{unit.hp}/{unit.max_hp}", 12, TEXT,
              x + bar_w // 2, y + bar_h // 2, center=True)
    y += 13

    # Stats â€” green if buffed, red if debuffed, dim if neutral
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
    elif hasattr(unit, 'ranged_uses') and (
        unit.role == "ranged"
        or (unit.role in ("warlock", "noble") and unit.slot != SLOT_FRONT)
    ):
        limit = 2 if unit.role in ("warlock", "noble") and unit.slot != SLOT_FRONT else 3
        draw_text(surf, f"uses {unit.ranged_uses}/{limit}", 12, TEXT_MUTED, x, y)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# FORMATION LAYOUT  (battle screen)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#
# Side-facing battle layout:
#
#   P1 team on the left, facing right.
#   P2 team on the right, facing left.
#   Frontliners meet in the middle; backliners sit behind them.

BATTLE_STRIP_H = 184
BATTLE_STRIP_RECT = pygame.Rect(0, HEIGHT - BATTLE_STRIP_H, WIDTH, BATTLE_STRIP_H)
ARENA_RECT = pygame.Rect(0, 0, WIDTH, BATTLE_STRIP_RECT.top)

UNIT_W = 184
UNIT_H = 150

_BACK_TOP_Y = 126
_BACK_BOTTOM_Y = 398
_FRONT_Y = 260

_P1_BACK_X = 104
_P1_FRONT_X = 414
_P2_FRONT_X = WIDTH - _P1_FRONT_X - UNIT_W
_P2_BACK_X = WIDTH - _P1_BACK_X - UNIT_W

P1_FRONT_RECT = pygame.Rect(_P1_FRONT_X, _FRONT_Y, UNIT_W, UNIT_H)
P1_BL_RECT    = pygame.Rect(_P1_BACK_X, _BACK_TOP_Y, UNIT_W, UNIT_H)
P1_BR_RECT    = pygame.Rect(_P1_BACK_X, _BACK_BOTTOM_Y, UNIT_W, UNIT_H)

P2_FRONT_RECT = pygame.Rect(_P2_FRONT_X, _FRONT_Y, UNIT_W, UNIT_H)
P2_BL_RECT    = pygame.Rect(_P2_BACK_X, _BACK_TOP_Y, UNIT_W, UNIT_H)
P2_BR_RECT    = pygame.Rect(_P2_BACK_X, _BACK_BOTTOM_Y, UNIT_W, UNIT_H)

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

ARENA_CENTER_X = WIDTH // 2


def draw_formation(surf, battle: BattleState,
                   selected_unit=None, valid_targets=None,
                   mouse_pos=(0, 0),
                   acting_player=None,
                   status_rects_out=None):
    """Draw both teams in the rotated side-facing arena formation."""
    valid_targets = valid_targets or []

    arena = ARENA_RECT.inflate(-32, -26)
    pygame.draw.rect(surf, (24, 26, 34), arena, border_radius=18)
    pygame.draw.rect(surf, (52, 56, 72), arena, 2, border_radius=18)

    lane_rect = pygame.Rect(ARENA_CENTER_X - 105, arena.y + 44, 210, arena.height - 88)
    glow = pygame.Surface((lane_rect.width, lane_rect.height), pygame.SRCALPHA)
    pygame.draw.ellipse(glow, (75, 95, 135, 45), glow.get_rect())
    surf.blit(glow, lane_rect.topleft)
    pygame.draw.line(surf, (90, 96, 118), (ARENA_CENTER_X, arena.y + 42),
                     (ARENA_CENTER_X, arena.bottom - 42), 2)
    pygame.draw.line(surf, (58, 62, 78), (lane_rect.left, arena.y + 72),
                     (lane_rect.left, arena.bottom - 72), 1)
    pygame.draw.line(surf, (58, 62, 78), (lane_rect.right, arena.y + 72),
                     (lane_rect.right, arena.bottom - 72), 1)

    draw_text(surf, battle.team1.player_name, 18, GREEN,
              P1_FRONT_RECT.centerx, 34, center=True)
    draw_text(surf, "Facing Right", 13, TEXT_MUTED,
              P1_FRONT_RECT.centerx, 58, center=True)
    draw_text(surf, battle.team2.player_name, 18, BLUE,
              P2_FRONT_RECT.centerx, 34, center=True)
    draw_text(surf, "Facing Left", 13, TEXT_MUTED,
              P2_FRONT_RECT.centerx, 58, center=True)

    for slot, rect in SLOT_RECTS_P2.items():
        unit = battle.team2.get_slot(slot)
        actual_unit = (next((m for m in battle.team2.members if m.slot == slot and not m.ko), None)
                       or next((m for m in battle.team2.members if m.slot == slot), None))
        is_tgt = unit in valid_targets if valid_targets else False
        is_sel = (unit == selected_unit and acting_player == 2)
        has_q  = (actual_unit is not None and not actual_unit.ko and actual_unit.queued is not None)
        draw_unit_box(surf, rect, actual_unit, selected=is_sel, is_target=is_tgt,
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


ACTION_GROUP_STYLES = {
    "basics": {
        "label": "Basics",
        "header": (90, 162, 140),
        "normal": (36, 54, 50),
        "hover": (52, 78, 70),
        "border": (92, 162, 142),
    },
    "signature": {
        "label": "Signature",
        "header": CYAN,
        "normal": (34, 46, 62),
        "hover": (52, 72, 96),
        "border": (98, 154, 208),
    },
    "twist": {
        "label": "Twist",
        "header": (232, 150, 78),
        "normal": (66, 42, 26),
        "hover": (96, 58, 34),
        "border": (235, 157, 82),
    },
    "artifacts": {
        "label": "Artifacts",
        "header": (208, 198, 110),
        "normal": (56, 50, 28),
        "hover": (84, 72, 40),
        "border": (188, 176, 88),
    },
    "utility": {
        "label": "Utility",
        "header": (160, 160, 176),
        "normal": (46, 46, 56),
        "hover": (66, 66, 82),
        "border": (128, 128, 150),
    },
}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# BATTLE LOG
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

LOG_RECT = pygame.Rect(580, 80, 400, 560)


def _log_color(line: str) -> tuple:
    """Return a colour for a log entry based on its content."""
    if line.startswith("\x01"):
        line = line[1:]
    if "â”€â”€â”€" in line:
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


def draw_log(surf, log: list, rect=LOG_RECT, scroll_offset: int = 0, title: str | None = "Battle Log"):
    if title:
        draw_panel(surf, rect, title, 16)
    else:
        draw_rect_border(surf, rect, PANEL, BORDER, 1)
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
        draw_text(surf, f"â–² {scroll_offset} older", 11, TEXT_MUTED,
                  rect.right - 8, rect.y + 28, right=True)
        draw_text(surf, "â–¼ newer  (wheel to scroll)", 11, TEXT_MUTED,
                  rect.right - 8, rect.bottom - 6, right=True)
    elif total > view_lines:
        draw_text(surf, "â–² wheel to scroll", 11, TEXT_MUTED,
                  rect.right - 8, rect.y + 28, right=True)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ACTION MENU
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

ACTION_PANEL_RECT = pygame.Rect(995, 80, 390, 800)
BUTTON_H = 36
BUTTON_W = 360
BUTTON_X = 1005


def draw_action_menu(surf, mouse_pos, actor: CombatantState,
                     valid_abilities: list, swap_used: bool,
                     active_artifacts: list = None,
                     state_label: str = "") -> list:
    """
    Draw the action selection menu for one actor.
    Returns a list of (pygame.Rect, action_dict) tuples for click detection.
    """
    draw_panel(surf, ACTION_PANEL_RECT, f"Actions â€” {actor.name}", 18)

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

    # Active artifacts
    for artifact in (active_artifacts or []):
        if actor.must_recharge:
            break
        y += 6
        item_btn_h = 52
        rect = pygame.Rect(BUTTON_X, y, BUTTON_W, item_btn_h)
        hov = rect.collidepoint(mouse_pos)
        fill = PANEL_HIGHLIGHT if hov else (30, 50, 40)
        draw_rect_border(surf, rect, fill, BORDER_ACTIVE)
        draw_text(surf, f"Artifact: {artifact.name}", 15, TEXT, rect.x + 8, rect.y + 5)
        desc_lines = _wrap_text(artifact.description, 12, BUTTON_W - 16)
        for _li, _ln in enumerate(desc_lines[:2]):
            draw_text(surf, _ln, 12, TEXT_DIM, rect.x + 12, rect.y + 24 + _li * 14)
        buttons.append((rect, {"type": "item", "artifact": artifact, "target": None}))
        y += item_btn_h + 4

    # Swap (once per turn; also blocked when unit must recharge)
    y += 6
    rect = pygame.Rect(BUTTON_X, y, BUTTON_W, BUTTON_H)
    draw_button(surf, rect, "Swap with ally", mouse_pos, size=15,
                disabled=swap_used or actor.has_status("root") or actor.must_recharge)
    if not swap_used and not actor.has_status("root") and not actor.must_recharge:
        buttons.append((rect, {"type": "swap", "target": None}))
    y += BUTTON_H + 4

    # Skip â€” label changes to "Recharge" when must_recharge
    rect = pygame.Rect(BUTTON_X, y, BUTTON_W, BUTTON_H)
    skip_label = "Recharge" if actor.must_recharge else "Skip"
    draw_button(surf, rect, skip_label, mouse_pos, size=15, normal=(40, 40, 45))
    buttons.append((rect, {"type": "skip"}))
    y += BUTTON_H + 14  # larger gap to visually separate Back

    # Back
    rect = pygame.Rect(BUTTON_X, y, BUTTON_W, BUTTON_H)
    draw_button(surf, rect, "â† Back", mouse_pos, size=15, normal=(35, 35, 50),
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
            s += f" â†” {tgt.name[:12]}"
        return s, CYAN
    if q["type"] == "ability":
        ab = q.get("ability")
        tgt = q.get("target")
        s = ab.name[:14] if ab else "?"
        if tgt:
            s += f" â†’ {tgt.name[:10]}"
        if q.get("swap_target") is not None:
            s += f" â†” {q['swap_target'].name[:10]}"
        return s, TEXT
    if q["type"] == "item":
        artifact = q.get("artifact")
        tgt = q.get("target")
        s = artifact.name if artifact else "artifact"
        if tgt:
            s += f" â†’ {tgt.name[:10]}"
        if q.get("swap_target") is not None:
            s += f" â†” {q['swap_target'].name[:10]}"
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
    draw_text(surf, f"P{acting_player} â€” Queued Actions", 14, (130, 200, 130), x + 8, y)
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


def draw_battle_overlay(scrim_surf, panel_rect, title, mouse_pos):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 165))
    scrim_surf.blit(overlay, (0, 0))
    draw_rect_border(scrim_surf, panel_rect, (30, 32, 44), BORDER_ACTIVE, 2)
    draw_text(scrim_surf, title, 24, TEXT, panel_rect.x + 18, panel_rect.y + 14)
    close_rect = pygame.Rect(panel_rect.right - 42, panel_rect.y + 12, 26, 26)
    draw_rect_border(scrim_surf, close_rect, (74, 42, 42), RED_DARK)
    draw_text(scrim_surf, "Ã—", 18, TEXT, close_rect.centerx, close_rect.centery, center=True)
    return close_rect


def draw_battle_log_overlay(surf, log: list, mouse_pos, scroll_offset: int = 0):
    panel_rect = pygame.Rect(160, 74, WIDTH - 320, HEIGHT - 148)
    close_rect = draw_battle_overlay(surf, panel_rect, "Battle Log", mouse_pos)
    inner = panel_rect.inflate(-26, -62)
    draw_log(surf, log, rect=inner, scroll_offset=scroll_offset, title=None)
    return {"close": close_rect, "panel": panel_rect}


def draw_artifact_overlay(surf, battle: BattleState, mouse_pos):
    panel_rect = pygame.Rect(130, 92, WIDTH - 260, HEIGHT - 184)
    close_rect = draw_battle_overlay(surf, panel_rect, "Artifacts", mouse_pos)
    inner = panel_rect.inflate(-28, -66)
    col_w = (inner.width - 18) // 2
    artifact_hover = []
    team_panels = [
        (battle.team1, pygame.Rect(inner.x, inner.y, col_w, inner.height)),
        (battle.team2, pygame.Rect(inner.x + col_w + 18, inner.y, col_w, inner.height)),
    ]
    for team, rect in team_panels:
        draw_rect_border(surf, rect, (24, 26, 36), BORDER, 1)
        accent = GREEN if team is battle.team1 else BLUE
        draw_text(surf, team.player_name, 18, accent, rect.x + 14, rect.y + 12)
        y = rect.y + 42
        if not team.artifacts:
            draw_text(surf, "No artifacts equipped.", 15, TEXT_MUTED, rect.x + 14, y)
            continue
        for state in team.artifacts:
            card = pygame.Rect(rect.x + 12, y, rect.width - 24, 94)
            draw_rect_border(surf, card, (36, 40, 52), BORDER_ACTIVE if state.cooldown_remaining == 0 else BORDER, 1)
            name_rect = draw_text(surf, state.artifact.name, 17, TEXT, card.x + 12, card.y + 10)
            artifact_hover.append((name_rect, state.artifact))
            if state.artifact.reactive:
                cd_text = f"Reactive  |  CD {state.artifact.cooldown}"
            else:
                cd_text = f"Active  |  CD {state.artifact.cooldown}"
            if state.used_this_battle and state.artifact.cooldown >= 900:
                cd_text += "  |  Spent this battle"
            elif state.cooldown_remaining > 0:
                cd_text += f"  |  Ready in {state.cooldown_remaining}"
            else:
                cd_text += "  |  Ready"
            draw_text(surf, cd_text, 12, YELLOW if state.cooldown_remaining > 0 else TEXT_DIM,
                      card.x + 12, card.y + 32)
            desc_lines = _wrap_text(state.artifact.description, 13, card.width - 24)
            for idx, line in enumerate(desc_lines[:3]):
                draw_text(surf, line, 13, TEXT_DIM, card.x + 12, card.y + 50 + idx * 14)
            y += 104
    return {"close": close_rect, "panel": panel_rect, "artifact_hover": artifact_hover}


def _draw_strip_button(surf, rect, label, mouse_pos, normal, hover, border=BORDER_ACTIVE,
                       text_color=TEXT, size=16, disabled=False):
    return draw_button(
        surf, rect, label, mouse_pos,
        normal=normal, hover=hover, border=border,
        text_color=text_color, size=size, disabled=disabled
    )


def draw_battle_strip(
    surf,
    mouse_pos,
    battle: BattleState,
    *,
    mode: str = "view",
    prompt: str = "",
    subprompt: str = "",
    action_groups: list | None = None,
    queue_units: list | None = None,
    current_actor: CombatantState | None = None,
    current_is_extra: bool = False,
    show_review: bool = False,
    can_clear: bool = False,
    can_lock: bool = False,
    continue_label: str | None = None,
    continue_disabled: bool = False,
    waiting_label: str = "",
):
    strip = BATTLE_STRIP_RECT
    pygame.draw.rect(surf, (18, 20, 28), strip)
    pygame.draw.line(surf, BORDER_ACTIVE, (0, strip.y), (WIDTH, strip.y), 2)

    left_rect = pygame.Rect(strip.x + 18, strip.y + 16, 188, strip.height - 32)
    main_rect = pygame.Rect(left_rect.right + 18, strip.y + 16, 924, strip.height - 32)
    right_rect = pygame.Rect(main_rect.right + 18, strip.y + 16, strip.right - main_rect.right - 36, strip.height - 32)

    buttons = {
        "log": None,
        "artifacts": None,
        "artifact_hover": [],
        "queue": [],
        "clear": None,
        "lock": None,
        "continue": None,
        "actions": [],
    }

    draw_rect_border(surf, left_rect, (28, 30, 40), BORDER, 1)
    draw_text(surf, f"Round {battle.round_num}", 18, YELLOW, left_rect.x + 14, left_rect.y + 12)
    draw_text(surf, f"Init P{battle.init_player}", 14, CYAN, left_rect.x + 14, left_rect.y + 38)
    buttons["log"] = pygame.Rect(left_rect.x + 14, left_rect.y + 72, left_rect.width - 28, 38)
    buttons["artifacts"] = pygame.Rect(left_rect.x + 14, left_rect.y + 118, left_rect.width - 28, 38)
    _draw_strip_button(surf, buttons["log"], "Battle Log", mouse_pos,
                       normal=(38, 48, 64), hover=(56, 70, 92))
    _draw_strip_button(surf, buttons["artifacts"], "Artifacts", mouse_pos,
                       normal=(66, 58, 34), hover=(90, 78, 44))

    draw_rect_border(surf, main_rect, (24, 26, 36), BORDER, 1)
    queue_row = pygame.Rect(main_rect.x + 12, main_rect.y + 10, main_rect.width - 24, 42)
    content_top = queue_row.bottom + 10

    if queue_units:
        draw_text(surf, "Queue", 13, TEXT_MUTED, queue_row.x, queue_row.y)
        chip_x = queue_row.x + 50
        chip_y = queue_row.y + 2
        for entry in queue_units:
            if len(entry) >= 4:
                unit, is_extra, tag, color = entry[:4]
            else:
                unit, tag, color = entry
                is_extra = False
            label = short_name(unit.name) + (" +" if is_extra else "")
            if tag:
                label += f" Â· {tag}"
            chip_w = min(170, max(104, font(13).size(label)[0] + 18))
            chip = pygame.Rect(chip_x, chip_y, chip_w, 28)
            is_current_chip = unit is current_actor and bool(is_extra) == bool(current_is_extra)
            fill = (68, 60, 24) if is_current_chip else (40, 44, 58)
            border = (232, 204, 84) if is_current_chip else BORDER
            if color == GREEN:
                fill = (28, 54, 36)
                border = (88, 182, 112)
            elif color == TEXT_MUTED:
                fill = (36, 38, 48)
            draw_rect_border(surf, chip, fill, border, 1)
            draw_text(surf, label, 13, TEXT if is_current_chip else color,
                      chip.centerx, chip.centery, center=True)
            buttons["queue"].append((chip, unit, bool(is_extra)))
            if is_extra and is_current_chip:
                draw_text(surf, "+", 14, YELLOW, chip.right - 14, chip.y + 6)
            chip_x += chip_w + 8
            if chip_x > queue_row.right - 120:
                break

    if prompt:
        draw_text(surf, prompt, 20, CYAN if mode == "queue" else TEXT, main_rect.x + 14, content_top)
    if subprompt:
        draw_text(surf, subprompt, 13, TEXT_MUTED, main_rect.x + 14, content_top + 26)

    if mode == "queue":
        if action_groups:
            columns = [
                ("basics", pygame.Rect(main_rect.x + 12, content_top + 52, 215, 86)),
                ("signature", pygame.Rect(main_rect.x + 237, content_top + 52, 165, 86)),
                ("twist", pygame.Rect(main_rect.x + 412, content_top + 52, 165, 86)),
                ("artifacts", pygame.Rect(main_rect.x + 587, content_top + 52, 190, 86)),
                ("utility", pygame.Rect(main_rect.x + 787, content_top + 52, 113, 86)),
            ]
            group_map = {group["key"]: group for group in action_groups}
            for key, rect in columns:
                style = ACTION_GROUP_STYLES[key]
                draw_rect_border(surf, rect, (30, 32, 42), style["border"], 1)
                draw_text(surf, style["label"], 13, style["header"], rect.x + 10, rect.y + 8)
                actions = group_map.get(key, {}).get("actions", [])
                if not actions:
                    draw_text(surf, "No action", 12, TEXT_MUTED, rect.x + 10, rect.y + 38)
                    continue
                btn_y = rect.y + 28
                btn_h = 22 if len(actions) >= 3 else 26
                gap = 6 if len(actions) >= 3 else 8
                for action in actions[:3]:
                    btn_rect = pygame.Rect(rect.x + 8, btn_y, rect.width - 16, btn_h)
                    label = action["label"]
                    if font(13).size(label)[0] > btn_rect.width - 10:
                        label = label[: max(4, len(label) - 3)] + "â€¦"
                    _draw_strip_button(
                        surf, btn_rect, label, mouse_pos,
                        normal=style["normal"], hover=style["hover"],
                        border=style["border"], size=13
                    )
                    buttons["actions"].append((btn_rect, action["action"]))
                    artifact = action["action"].get("artifact") if isinstance(action.get("action"), dict) else None
                    if artifact is not None:
                        buttons["artifact_hover"].append((btn_rect, artifact))
                    btn_y += btn_h + gap
        elif show_review:
            review_rect = pygame.Rect(main_rect.x + 18, content_top + 58, main_rect.width - 36, 74)
            draw_rect_border(surf, review_rect, (32, 36, 50), (86, 110, 156), 1)
            draw_text(surf, "All actions are queued.", 18, TEXT, review_rect.x + 16, review_rect.y + 18)
            draw_text(surf, "Use Clear Queue to adjust anything, or Lock Actions to begin resolution.",
                      13, TEXT_MUTED, review_rect.x + 16, review_rect.y + 44)
    elif waiting_label:
        draw_text(surf, waiting_label, 18, TEXT_MUTED, main_rect.x + 14, content_top + 54)

    draw_rect_border(surf, right_rect, (28, 30, 40), BORDER, 1)
    if can_clear:
        buttons["clear"] = pygame.Rect(right_rect.x + 12, right_rect.y + 26, right_rect.width - 24, 40)
        _draw_strip_button(surf, buttons["clear"], "Clear Queue", mouse_pos,
                           normal=(70, 34, 34), hover=(96, 46, 46))
    if can_lock:
        buttons["lock"] = pygame.Rect(right_rect.x + 12, right_rect.y + 78, right_rect.width - 24, 52)
        _draw_strip_button(surf, buttons["lock"], "Lock Actions", mouse_pos,
                           normal=(42, 92, 58), hover=(58, 122, 78), size=18)
    if continue_label:
        buttons["continue"] = pygame.Rect(right_rect.x + 12, right_rect.y + 78, right_rect.width - 24, 52)
        _draw_strip_button(
            surf, buttons["continue"], continue_label, mouse_pos,
            normal=BLUE_DARK, hover=BLUE, size=17, disabled=continue_disabled
        )
    return buttons


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PASS SCREEN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    draw_button(surf, btn, "Continue â†’", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE, border=BORDER_ACTIVE)
    return btn


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN MENU
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def draw_main_menu(surf, mouse_pos, profile, player_level=1, new_catalog_unlocks=False,
                   quick_play_unlocked=False, ranked_unlocked=False, level_card_open=False):
    surf.fill(BG)
    cx = WIDTH // 2
    player_exp = getattr(profile, "player_exp", 0) if profile is not None else 0
    exp_floor = total_exp_for_level(player_level)
    exp_into = max(0, player_exp - exp_floor)
    exp_need = exp_to_next_level(player_level)
    exp_remaining = max(0, exp_need - exp_into)

    level_btn = pygame.Rect(20, 18, 132, 38)
    gold_btn = pygame.Rect(20, 62, 176, 38)

    for rect, label, fill_base, fill_hover, text_color in (
        (level_btn, f"Level {player_level}", (42, 52, 76), (58, 72, 102), CYAN),
        (gold_btn, f"Gold {getattr(profile, 'gold', 0)}", (74, 58, 24), (102, 78, 28), YELLOW),
    ):
        hovered = rect.collidepoint(mouse_pos)
        draw_rect_border(surf, rect, fill_hover if hovered else fill_base, BORDER_ACTIVE if hovered else BORDER)
        draw_text(surf, label, 18, text_color if hovered else TEXT, rect.centerx, rect.centery, center=True)

    draw_text(surf, "FABLED", 80, TEXT, cx, 130, center=True)
    if level_card_open:
        card_rect = pygame.Rect(20, 108, 320, 152)
        close_rect = pygame.Rect(card_rect.right - 28, card_rect.y + 8, 20, 20)
        draw_rect_border(surf, card_rect, PANEL, BORDER_ACTIVE, width=2)
        draw_rect_border(surf, close_rect, (70, 40, 40), RED_DARK)
        draw_text(surf, "x", 14, TEXT, close_rect.centerx, close_rect.centery, center=True)
        draw_text(surf, f"Player Level {player_level}", 22, TEXT, card_rect.x + 14, card_rect.y + 14)
        draw_text(surf, f"Total EXP {player_exp}", 15, TEXT_DIM, card_rect.x + 14, card_rect.y + 44)
        draw_text(surf, f"Current Level Progress {exp_into}/{exp_need}", 15, CYAN, card_rect.x + 14, card_rect.y + 68)
        bar_rect = pygame.Rect(card_rect.x + 14, card_rect.y + 98, card_rect.width - 28, 18)
        draw_rect_border(surf, bar_rect, (26, 30, 38), BORDER)
        fill_w = 0 if exp_need <= 0 else int((bar_rect.width - 4) * (exp_into / exp_need))
        if fill_w > 0:
            pygame.draw.rect(surf, CYAN, pygame.Rect(bar_rect.x + 2, bar_rect.y + 2, fill_w, bar_rect.height - 4), border_radius=3)
        draw_text(surf, f"{exp_remaining} EXP needed for next level", 14, TEXT_MUTED, card_rect.x + 14, card_rect.y + 124)
    else:
        card_rect = None
        close_rect = None

    def _draw_primary_option(rect, title, subtitle, *, normal, hover, enabled=True):
        draw_button(surf, rect, title, mouse_pos, size=22, normal=normal, hover=hover, border=BORDER_ACTIVE, disabled=not enabled)

    camelot_btn    = pygame.Rect(cx - 170, 300, 340, 52)
    fantasia_btn   = pygame.Rect(cx - 170, 370, 340, 52)
    bright_btn     = pygame.Rect(cx - 170, 440, 340, 52)
    estate_btn     = pygame.Rect(cx - 170, 510, 340, 52)
    guild_btn      = pygame.Rect(cx - 300, 610, 180, 44)
    market_btn     = pygame.Rect(cx - 90, 610, 180, 44)
    embassy_btn    = pygame.Rect(cx + 120, 610, 180, 44)

    _draw_primary_option(
        camelot_btn,
        "Camelot",
        "Tutorial campaign with four quests.",
        normal=(40, 90, 50),
        hover=(55, 120, 65),
        enabled=True,
    )
    _draw_primary_option(
        fantasia_btn,
        "Fantasia",
        "Quick Play",
        normal=BLUE_DARK,
        hover=BLUE,
        enabled=quick_play_unlocked,
    )
    _draw_primary_option(
        bright_btn,
        "Brightheart",
        "Ranked ladder",
        normal=(90, 60, 30),
        hover=(125, 85, 45),
        enabled=ranked_unlocked,
    )
    _draw_primary_option(
        estate_btn,
        "The Estate",
        "Parties, guidebook, and training.",
        normal=(75, 45, 120),
        hover=(105, 65, 165),
        enabled=True,
    )

    draw_button(surf, guild_btn, "Guild", mouse_pos, size=18,
                normal=(55, 90, 55), hover=(75, 125, 75), border=BORDER_ACTIVE)
    draw_button(surf, market_btn, "Market", mouse_pos, size=18,
                normal=(55, 55, 55), hover=(75, 75, 75), border=BORDER_ACTIVE)
    draw_button(surf, embassy_btn, "Embassy", mouse_pos, size=18,
                normal=(80, 60, 30), hover=(110, 85, 45), border=BORDER_ACTIVE)
    if new_catalog_unlocks:
        bx, by = estate_btn.right, estate_btn.top
        pygame.draw.circle(surf, (190, 130, 30), (bx, by), 11)
        draw_text(surf, "!", 14, TEXT, bx - 3, by - 9)

    # Small icon buttons â€” upper-right corner
    settings_btn = pygame.Rect(WIDTH - 98, 14, 40, 40)
    exit_btn     = pygame.Rect(WIDTH - 52, 14, 40, 40)
    s_hov = settings_btn.collidepoint(mouse_pos)
    e_hov = exit_btn.collidepoint(mouse_pos)
    draw_rect_border(surf, settings_btn, PANEL_HIGHLIGHT if s_hov else PANEL_ALT, BORDER_ACTIVE if s_hov else BORDER)
    draw_rect_border(surf, exit_btn,     PANEL_HIGHLIGHT if e_hov else PANEL_ALT, BORDER_ACTIVE if e_hov else BORDER)
    draw_text(surf, "âš™", 22, TEXT if s_hov else TEXT_DIM, settings_btn.x + 8, settings_btn.y + 8)
    draw_text(surf, "âœ•", 20, RED if e_hov else TEXT_DIM,  exit_btn.x + 10,     exit_btn.y + 9)

    return {
        "camelot_btn": camelot_btn,
        "fantasia_btn": fantasia_btn,
        "brightheart_btn": bright_btn,
        "estate_btn": estate_btn,
        "level_btn": level_btn,
        "gold_btn": gold_btn,
        "level_card_rect": card_rect,
        "level_card_close": close_rect,
        "guild_btn": guild_btn,
        "market_btn": market_btn,
        "embassy_btn": embassy_btn,
        "settings_btn": settings_btn,
        "exit_btn": exit_btn,
    }


def draw_estate_menu(surf, mouse_pos, new_catalog_unlocks=False) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "The Estate", 48, TEXT, cx, 80, center=True)
    draw_text(surf, "Manage your parties, study the guidebook, or head to training.", 18, TEXT_DIM, cx, 145, center=True)

    parties_btn = pygame.Rect(cx - 170, 235, 340, 62)
    guidebook_btn = pygame.Rect(cx - 170, 319, 340, 62)
    training_btn = pygame.Rect(cx - 170, 403, 340, 62)
    back_btn = pygame.Rect(20, 20, 100, 36)

    draw_button(surf, parties_btn, "Parties", mouse_pos, size=22,
                normal=(75, 45, 120), hover=(105, 65, 165), border=BORDER_ACTIVE)
    draw_button(surf, guidebook_btn, "Guidebook", mouse_pos, size=22,
                normal=(55, 75, 80), hover=(75, 105, 115), border=BORDER_ACTIVE)
    draw_button(surf, training_btn, "Training", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE, border=BORDER_ACTIVE)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    if new_catalog_unlocks:
        pygame.draw.circle(surf, (190, 130, 30), (guidebook_btn.right, guidebook_btn.top), 11)
        draw_text(surf, "!", 14, TEXT, guidebook_btn.right - 3, guidebook_btn.top - 9)

    draw_text(surf, "Training uses the full local collection and ignores progression locks.", 15, TEXT_MUTED, cx, 500, center=True)

    return {
        "parties_btn": parties_btn,
        "guidebook_btn": guidebook_btn,
        "training_btn": training_btn,
        "back_btn": back_btn,
    }


def draw_training_menu(surf, mouse_pos) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Training", 48, TEXT, cx, 80, center=True)
    draw_text(surf, "Both modes use every adventurer and artifact in this local build.", 18, TEXT_DIM, cx, 145, center=True)

    local_btn = pygame.Rect(cx - 170, 250, 340, 62)
    lan_btn = pygame.Rect(cx - 170, 334, 340, 62)
    back_btn = pygame.Rect(20, 20, 100, 36)

    draw_button(surf, local_btn, "Local Play", mouse_pos, size=22,
                normal=(55, 70, 120), hover=(72, 95, 160), border=BORDER_ACTIVE)
    draw_button(surf, lan_btn, "LAN Mode", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE, border=BORDER_ACTIVE)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    draw_text(surf, "Local Play is same-device pass-and-play. LAN Mode is for two PCs on the same network.", 15, TEXT_MUTED, cx, 430, center=True)

    return {
        "local_btn": local_btn,
        "lan_btn": lan_btn,
        "back_btn": back_btn,
    }


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
    draw_text(surf, display + "â–", 20, TEXT, input_rect.x + 10, input_rect.y + 8)

    confirm_btn = pygame.Rect(cx - 200, cy + 20, 180, 44)
    cancel_btn  = pygame.Rect(cx + 20,  cy + 20, 180, 44)
    draw_button(surf, confirm_btn, "Confirm", mouse_pos, size=18,
                normal=(40, 90, 50), hover=(55, 120, 65))
    draw_button(surf, cancel_btn, "Cancel", mouse_pos, size=18)

    return {"confirm_btn": confirm_btn, "cancel_btn": cancel_btn}


def draw_practice_menu(surf, mouse_pos, quick_play_unlocked=False, ranked_unlocked=False,
                       player_rank_name="Margrave") -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Play", 48, TEXT, cx, 80, center=True)
    draw_text(surf, "Quick Play and Ranked use your local collection and progression.",
              18, TEXT_DIM, cx, 145, center=True)

    quick_btn  = pygame.Rect(cx - 170, 215, 340, 62)
    ranked_btn = pygame.Rect(cx - 170, 293, 340, 62)
    vs_pvp_btn = pygame.Rect(cx - 170, 371, 340, 62)
    back_btn   = pygame.Rect(20, 20, 100, 36)

    draw_button(surf, quick_btn, "Quick Play", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE, disabled=not quick_play_unlocked)
    draw_button(surf, ranked_btn, f"Ranked ({player_rank_name})", mouse_pos, size=22,
                normal=(90, 60, 30), hover=(125, 85, 45), border=BORDER_ACTIVE,
                disabled=not ranked_unlocked)
    draw_button(surf, vs_pvp_btn, "Local Versus", mouse_pos, size=22,
                normal=(55, 70, 120), hover=(72, 95, 160), border=BORDER_ACTIVE)
    draw_button(surf, back_btn,   "Back",         mouse_pos, size=16)
    if not quick_play_unlocked:
        draw_text(surf, "Complete Camelot to unlock Quick Play.", 16, TEXT_MUTED, cx, 452, center=True)
    elif not ranked_unlocked:
        draw_text(surf, "Ranked unlocks after the player, class, and adventurer sigil milestones are complete.",
                  16, TEXT_MUTED, cx, 452, center=True)

    return {
        "quick_btn": quick_btn,
        "ranked_btn": ranked_btn,
        "vs_pvp_btn": vs_pvp_btn,
        "back_btn": back_btn,
    }


def draw_teambuilder(surf, saved_teams: list, mouse_pos, profile, max_slots: int = 1) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Parties", 48, TEXT, cx, 40, center=True)
    draw_text(surf, f"Saved party slots unlocked: {max_slots}/6",
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
    artifact_hover = []

    for row in range(3):
        for col in range(2):
            idx = row * 2 + col
            rect = pygame.Rect(
                start_x + col * (slot_w + pad),
                start_y + row * (slot_h + pad),
                slot_w, slot_h
            )

            if idx >= max_slots:
                draw_rect_border(surf, rect, PANEL, BORDER)
                draw_text(surf, f"Slot {idx + 1} Locked", 18, TEXT_MUTED,
                          rect.centerx, rect.centery - 12, center=True)
                draw_text(surf, f"Unlocks at Player Level {idx * 2 + 1}",
                          14, TEXT_DIM, rect.centerx, rect.centery + 18, center=True)
            elif idx < len(saved_teams) and saved_teams[idx] is not None:
                team = saved_teams[idx]
                draw_rect_border(surf, rect, PANEL_ALT, BORDER_ACTIVE)
                draw_text(surf, team.get("name", f"Party {idx+1}"), 18, TEXT,
                          rect.x + 10, rect.y + 8)

                members = team.get("members", [])
                artifact_defs = [
                    ARTIFACTS_BY_ID[artifact_id]
                    for artifact_id in team.get("artifact_ids", [])
                    if artifact_id in ARTIFACTS_BY_ID
                ][:3]
                draw_artifact_name_list(
                    surf,
                    "Party Artifacts: ",
                    artifact_defs,
                    size=11,
                    prefix_color=ORANGE,
                    artifact_color=ORANGE,
                    x=rect.x + 10,
                    y=rect.y + 28,
                    artifact_rects_out=artifact_hover,
                    max_width=rect.width - 140,
                )
                member_col_w = (slot_w - 110) // 3
                for mi, m in enumerate(members[:3]):
                    mx = rect.x + 10 + mi * member_col_w
                    my = rect.y + 52
                    adv_name = m.get("adv_id", "?").replace("_", " ").title()
                    draw_text(surf, adv_name, 14, TEXT, mx, my)
                    sig_name = m.get("sig_id", "").replace("_", " ").title()
                    draw_text(surf, sig_name[:18], 11, TEXT_DIM, mx, my + 16)
                    basics = m.get("basics", [])
                    basics_str = ", ".join(b.replace("_", " ").title() for b in basics[:2])
                    draw_text(surf, basics_str[:22], 11, TEXT_DIM, mx, my + 30)
                    if False and mi == 0 and artifact_names:
                        artifact_str = ", ".join(artifact_names[:2])
                        if len(artifact_names) > 2:
                            artifact_str += "â€¦"
                        draw_text(surf, artifact_str[:22], 11, TEXT_DIM, mx, my + 44)

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
        "artifact_hover": artifact_hover,
    }


def draw_story_team_select(surf, saved_teams: list, mouse_pos, quest_def, max_slots: int = 1) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Select Your Party", 40, TEXT, cx, 50, center=True)
    # quest_def.key_preview omitted for now; restore the draw_text call here to re-add it

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    team_btns = []
    teambuilder_btn = None
    artifact_hover = []

    valid_teams = [(i, t) for i, t in enumerate(saved_teams[:max_slots]) if t is not None]

    if not valid_teams:
        draw_text(surf, "No parties saved. Build a party in Parties first.",
                  20, RED, cx, 250, center=True)
        teambuilder_btn = pygame.Rect(cx - 140, 310, 280, 55)
        draw_button(surf, teambuilder_btn, "Go to Parties", mouse_pos, size=20,
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
            artifact_defs = [
                ARTIFACTS_BY_ID[artifact_id]
                for artifact_id in team.get("artifact_ids", [])
                if artifact_id in ARTIFACTS_BY_ID
            ][:3]
            draw_artifact_name_list(
                surf,
                "Artifacts: ",
                artifact_defs,
                size=13,
                prefix_color=ORANGE,
                artifact_color=ORANGE,
                x=rect.x + 14,
                y=rect.y + 70,
                artifact_rects_out=artifact_hover,
                max_width=rect.width - 28,
            )
            team_btns.append((rect, slot_idx))

    return {
        "team_btns": team_btns,
        "back_btn": back_btn,
        "teambuilder_btn": teambuilder_btn,
        "artifact_hover": artifact_hover,
    }


def draw_guild_screen(surf, mouse_pos, profile, guild_tab: str,
                      adventurers: list, artifacts: list,
                      adventurer_prices: dict, artifact_prices: dict) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Guild", 48, TEXT, cx, 42, center=True)
    draw_text(surf, "Hire adventurers and purchase artifacts with gold.", 18, TEXT_DIM, cx, 88, center=True)
    draw_text(
        surf,
        f"Gold {getattr(profile, 'gold', 0)}  |  Vouchers {getattr(profile, 'guild_vouchers', 0)}",
        18,
        YELLOW,
        cx,
        114,
        center=True,
    )
    draw_text(surf, "Starter and Camelot rewards are not sold here.", 14, TEXT_MUTED, cx, 138, center=True)

    back_btn = pygame.Rect(20, 20, 100, 36)
    adv_tab_btn = pygame.Rect(cx - 180, 164, 170, 40)
    art_tab_btn = pygame.Rect(cx + 10, 164, 170, 40)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)
    draw_button(
        surf, adv_tab_btn, "Adventurers", mouse_pos, size=18,
        normal=(55, 90, 55) if guild_tab == "adventurers" else PANEL,
        hover=(75, 125, 75), border=BORDER_ACTIVE,
    )
    draw_button(
        surf, art_tab_btn, "Artifacts", mouse_pos, size=18,
        normal=(80, 60, 30) if guild_tab == "artifacts" else PANEL,
        hover=(110, 85, 45), border=BORDER_ACTIVE,
    )

    tab_btns = [("adventurers", adv_tab_btn), ("artifacts", art_tab_btn)]
    buy_adventurer_btns = []
    voucher_btns = []
    buy_artifact_btns = []
    artifact_hover = []

    card_w = 640
    card_h = 62
    pad = 10
    start_x = cx - card_w - 10
    start_y = 224

    if guild_tab == "adventurers":
        for idx, defn in enumerate(adventurers):
            col = idx % 2
            row = idx // 2
            rect = pygame.Rect(start_x + col * (card_w + 20), start_y + row * (card_h + pad), card_w, card_h)
            draw_rect_border(
                surf,
                rect,
                CLASS_COLORS.get(defn.cls, PANEL_ALT),
                BORDER_ACTIVE if rect.collidepoint(mouse_pos) else BORDER,
            )
            draw_text(surf, defn.name, 17, TEXT, rect.x + 12, rect.y + 9)
            draw_text(surf, cls_label(defn.cls), 13, CLASS_TEXT_COLORS.get(defn.cls, TEXT_DIM), rect.x + 12, rect.y + 32)

            owned = defn.id in getattr(profile, "recruited", set())
            price = adventurer_prices.get(defn.id, 0)
            buy_btn = pygame.Rect(rect.right - 126, rect.y + 10, 116, 18)
            voucher_btn = pygame.Rect(rect.right - 126, rect.y + 34, 116, 18)

            if owned:
                draw_text(surf, "Owned", 16, GREEN, rect.right - 22, rect.y + 20, right=True)
            else:
                draw_button(
                    surf, buy_btn, f"Buy {price}g", mouse_pos, size=13,
                    normal=BLUE_DARK, hover=BLUE,
                    disabled=getattr(profile, "gold", 0) < price,
                )
                buy_adventurer_btns.append((buy_btn, defn.id))
                can_voucher = getattr(profile, "guild_vouchers", 0) > 0
                draw_button(
                    surf, voucher_btn, "Use Voucher", mouse_pos, size=13,
                    normal=(55, 90, 55), hover=(75, 125, 75),
                    disabled=not can_voucher,
                )
                voucher_btns.append((voucher_btn, defn.id))
    else:
        for idx, artifact in enumerate(artifacts):
            col = idx % 2
            row = idx // 2
            rect = pygame.Rect(start_x + col * (card_w + 20), start_y + row * (card_h + pad), card_w, card_h)
            draw_rect_border(surf, rect, PANEL_ALT, BORDER_ACTIVE if rect.collidepoint(mouse_pos) else BORDER)
            name_rect = draw_text(surf, artifact.name, 17, TEXT, rect.x + 12, rect.y + 9)
            artifact_hover.append((name_rect, artifact))
            draw_text(surf, artifact.description[:68], 12, TEXT_DIM, rect.x + 12, rect.y + 32)

            owned = artifact.id in getattr(profile, "unlocked_artifacts", set())
            price = artifact_prices.get(artifact.id, 0)
            buy_btn = pygame.Rect(rect.right - 126, rect.y + 18, 116, 24)
            if owned:
                draw_text(surf, "Owned", 16, GREEN, rect.right - 22, rect.y + 22, right=True)
            else:
                draw_button(
                    surf, buy_btn, f"Buy {price}g", mouse_pos, size=13,
                    normal=BLUE_DARK, hover=BLUE,
                    disabled=getattr(profile, "gold", 0) < price,
                )
                buy_artifact_btns.append((buy_btn, artifact.id))

    return {
        "back_btn": back_btn,
        "tab_btns": tab_btns,
        "buy_adventurer_btns": buy_adventurer_btns,
        "voucher_btns": voucher_btns,
        "buy_artifact_btns": buy_artifact_btns,
        "artifact_hover": artifact_hover,
    }


def draw_embassy_screen(surf, mouse_pos, profile, exchange_rate: int, offers: tuple = (1, 5, 10, 20)) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Embassy", 48, TEXT, cx, 56, center=True)
    draw_text(surf, f"Exchange rate: $1 -> {exchange_rate} gold", 22, YELLOW, cx, 118, center=True)
    draw_text(surf, "Local-only for now: this simulates premium currency purchases on your machine.", 16, TEXT_DIM, cx, 150, center=True)
    draw_text(
        surf,
        f"Current Gold {getattr(profile, 'gold', 0)}  |  Lifetime Embassy Spend ${getattr(profile, 'premium_dollars_spent', 0)}",
        16,
        CYAN,
        cx,
        178,
        center=True,
    )

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    offer_btns = []
    card_y = 250
    card_w = 250
    card_h = 96
    pad = 24
    start_x = cx - (2 * card_w + pad) // 2
    for idx, dollars in enumerate(offers):
        col = idx % 2
        row = idx // 2
        rect = pygame.Rect(start_x + col * (card_w + pad), card_y + row * (card_h + pad), card_w, card_h)
        draw_rect_border(surf, rect, PANEL_ALT, BORDER_ACTIVE if rect.collidepoint(mouse_pos) else BORDER)
        draw_text(surf, f"${dollars}", 28, TEXT, rect.centerx, rect.y + 18, center=True)
        draw_text(surf, f"{dollars * exchange_rate} gold", 18, YELLOW, rect.centerx, rect.y + 52, center=True)
        offer_btns.append((rect, dollars))

    return {"back_btn": back_btn, "offer_btns": offer_btns}


def draw_market_closed(surf, mouse_pos) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Market", 48, TEXT, cx, 90, center=True)
    draw_text(surf, "Closed", 42, YELLOW, cx, 220, center=True)
    draw_text(
        surf,
        "Cosmetic and feature purchases are not implemented in this local build yet.",
        18,
        TEXT_DIM,
        cx,
        285,
        center=True,
    )
    back_btn = pygame.Rect(cx - 120, 360, 240, 52)
    draw_button(surf, back_btn, "Back", mouse_pos, size=20)
    return {"back_btn": back_btn}


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TEAM SELECTION SCREEN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
        while _f15.size(_name + "â€¦")[0] > _max_name_w and len(_name) > 1:
            _name = _name[:-1]
        _name = _name + "â€¦"
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
        draw_text(surf, f"{player_name} â€” Build Your Party", 28, TEXT, WIDTH // 2,
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
    team_artifacts = list(team_picks[0].get("team_artifacts", [])) if team_picks else []

    # Always 3-column scrollable grid, sorted by class.
    roster_cols = ROSTER_COLS
    card_w = CARD_W
    card_h = CARD_H

    if pre_battle_mode:
        # â”€â”€ Enemy formation cards in place of roster grid â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                    while _ef.size(_ename + "â€¦")[0] > enemy_card_w - 12 and len(_ename) > 1:
                        _ename = _ename[:-1]
                    _ename = _ename + "â€¦"
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
                        _sname = _sname[:18] + "â€¦"
                    draw_text(surf, _sname, 12, YELLOW, ex + 6, edy)
                    edy += 14
                for eb in ep.get("basics", []):
                    _bname = eb.name
                    if font(11).size(_bname)[0] > enemy_card_w - 14:
                        _bname = _bname[:20] + "â€¦"
                    draw_text(surf, _bname, 11, TEXT_DIM, ex + 6, edy)
                    edy += 13
        # clicks["roster"] stays empty in pre_battle_mode
    else:
        roster = sorted(roster, key=lambda d: (d.cls, d.name))

        # â”€â”€ Roster grid (left) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Party slots â€” fixed at the bottom of the left panel (outside scroll clip) â”€â”€
    slot_labels = ["Front", "Back Left", "Back Right"]
    draw_text(surf, "Your Party:", 18, TEXT_DIM, ROSTER_X, HEIGHT - 95)
    draw_text(surf, f"Shared Artifacts: {len(team_artifacts)}/3", 16, TEXT_DIM,
              ROSTER_X + 650, HEIGHT - 94, right=True)
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
            for _lbl, _ok in (("Sig", _has_sig), ("Basics", _has_basics)):
                _mark = "âœ“" if _ok else "â—‹"
                _col = (80, 210, 80) if _ok else TEXT_MUTED
                _s = _f10.render(f"{_lbl}{_mark}", True, _col)
                surf.blit(_s, (_sx, _sy))
                _sx += _s.get_width() + 4

            if pre_battle_mode:
                # In pre_battle_mode: â‡„ shifted to where Ã— was, no Ã— button
                swapbtn = pygame.Rect(x + 188, HEIGHT - 73 + 2, 20, 18)
                s_hov = swapbtn.collidepoint(mouse_pos)
                pygame.draw.rect(surf, (40, 80, 120) if s_hov else (30, 55, 80), swapbtn, border_radius=3)
                draw_text(surf, "â‡„", 11, (140, 200, 240) if s_hov else TEXT_MUTED, swapbtn.x + 2, swapbtn.y + 2)
                clicks["party_swap"].append((swapbtn, i))
            else:
                # Normal mode: â‡„ swap button (left of Ã—)
                swapbtn = pygame.Rect(x + 166, HEIGHT - 73 + 2, 20, 18)
                s_hov = swapbtn.collidepoint(mouse_pos)
                pygame.draw.rect(surf, (40, 80, 120) if s_hov else (30, 55, 80), swapbtn, border_radius=3)
                draw_text(surf, "â‡„", 11, (140, 200, 240) if s_hov else TEXT_MUTED, swapbtn.x + 2, swapbtn.y + 2)
                clicks["party_swap"].append((swapbtn, i))

                # Ã— remove button
                xbtn = pygame.Rect(x + 188, HEIGHT - 73 + 2, 20, 18)
                hov = xbtn.collidepoint(mouse_pos)
                pygame.draw.rect(surf, RED_DARK if hov else (70, 40, 40), xbtn, border_radius=3)
                draw_text(surf, "Ã—", 14, RED if hov else TEXT_DIM, xbtn.x + 3, xbtn.y + 1)
                clicks["party_remove"].append((xbtn, i))
            clicks["party_slots"].append((rect, i))
        else:
            draw_rect_border(surf, rect, PANEL_ALT, BORDER)
            draw_text(surf, slot_labels[i], 13, TEXT_MUTED, x + 6, HEIGHT - 73 + 4)
            draw_text(surf, "(empty)", 15, TEXT_MUTED, x + 6, HEIGHT - 73 + 20)

    # â”€â”€ Detail panel (right) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            # â”€â”€ Name + class â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            draw_text(surf, _pm_defn.name, 22, TEXT, _dx, _dy)
            _dy += 26
            _pmcr = draw_text(surf, f"{cls_label(_pm_defn.cls)}  â€”  {_pm_defn.talent_name}",
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

            # â”€â”€ Signature â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                draw_text(surf, "  â€”", 13, TEXT_MUTED, _dx + 6, _dy)
                _dy += 15
            _dy += 2

            # â”€â”€ Basics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                    draw_text(surf, "  â€”", 13, TEXT_MUTED, _dx + 6, _dy)
                    _dy += 15
            _dy += 2

            # â”€â”€ Artifacts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if _dy + 14 <= _bottom_limit:
                pygame.draw.line(surf, BORDER, (_dx, _dy), (_dx + _detail_max_w, _dy), 1)
                _dy += 7
            if _dy + 14 <= _bottom_limit:
                draw_text(surf, "Party Artifacts", 13, CYAN, _dx, _dy)
                _dy += 16
            if team_artifacts:
                for _artifact in team_artifacts:
                    if _dy + 13 > _bottom_limit:
                        break
                    draw_text(surf, _artifact.name, 13, (140, 190, 140), _dx + 6, _dy)
                    _dy += 14
                    if _dy + 12 <= _bottom_limit:
                        _atype = "Reactive" if _artifact.reactive else "Active"
                        _acol = TYPE_PASSIVE_COL if _artifact.reactive else TYPE_ACTIVE_COL
                        draw_text(surf, _atype, 12, _acol, _dx + 10, _dy)
                        _dy += 13
                    for _line in _wrap_text(_artifact.description, 12, _detail_max_w - 10):
                        if _dy + 12 > _bottom_limit:
                            break
                        _draw_rich_line(surf, _line, 12, TEXT_DIM, _dx + 10, _dy, status_rects_out)
                        _dy += 13
                    _dy += 2
            elif _dy + 13 <= _bottom_limit:
                draw_text(surf, "  None", 13, TEXT_MUTED, _dx + 6, _dy)

        # Edit Sets button â€” bottom of detail panel
        edit_sets_rect = pygame.Rect(DETAIL_X + 14, DETAIL_Y + DETAIL_H - 55, 180, 44)
        draw_button(surf, edit_sets_rect, "Edit Sets â†’", mouse_pos,
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

        if sub_phase == "pick_item":
            draw_text(surf, "Party Artifacts", 24, TEXT, dx, dy)
            dy += 30
            for line in _wrap_text(
                "Artifacts are shared by the whole party and are not equipped by individual adventurers.",
                13, DETAIL_W - 28,
            ):
                _draw_rich_line(surf, line, 13, TEXT_DIM, dx, dy, status_rects_out)
                dy += 16
            dy += 10
        else:
            draw_text(surf, defn.name, 24, TEXT, dx, dy)
            dy += 30
            _dcr = draw_text(surf, f"{cls_label(defn.cls)}  â€”  {defn.talent_name}",
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
            # â”€â”€ Signatures preview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            # â”€â”€ Twist preview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if dy + 14 <= bottom_limit:
                pygame.draw.line(surf, BORDER, (dx, dy), (dx + DETAIL_W - 28, dy), 1)
                dy += 6
                if twists_unlocked:
                    twist = defn.twist
                    for _tw_name_line in _wrap_text(f"Twist: {twist.name}", 14, DETAIL_W - 32):
                        if dy + 14 > bottom_limit:
                            break
                        draw_text(surf, _tw_name_line, 14, ORANGE, dx, dy)
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
            selected_artifacts = set(item_choice or [])
            draw_text(surf, f"Choose 3 Artifacts ({len(selected_artifacts)}/3):", 18, CYAN, dx, dy)
            dy += 24
            inner_w = DETAIL_W - 44
            list_top = dy
            list_bottom = DETAIL_Y + DETAIL_H - 95
            view_rect = pygame.Rect(dx, list_top, DETAIL_W - 28, max(0, list_bottom - list_top))
            item_heights = []
            for i, item in enumerate(items):
                sel_i = i in selected_artifacts
                desc_lines = _wrap_text(item.description, 13, inner_w)
                preview = desc_lines[: (3 if sel_i else 1)]
                item_heights.append(39 + len(preview) * 14)
            content_h = sum(item_heights)
            max_scroll = max(0, content_h - view_rect.height)
            scroll = max(0, min(scroll_offset, max_scroll))
            clicks["scroll_max"] = max_scroll
            clicks["scroll_viewport"] = view_rect
            prev_clip = surf.get_clip()
            surf.set_clip(view_rect)
            for i, item in enumerate(items):
                sel_i = i in selected_artifacts
                desc_lines = _wrap_text(item.description, 13, inner_w)
                preview = desc_lines[: (3 if sel_i else 1)]
                entry_h = 37 + len(preview) * 14
                y_draw = dy - scroll
                r = pygame.Rect(dx, y_draw, DETAIL_W - 28, entry_h)
                if r.bottom >= view_rect.top and r.top <= view_rect.bottom:
                    _itype_lbl = "Reactive" if item.reactive else "Active"
                    _itype_col = TYPE_PASSIVE_COL if item.reactive else TYPE_ACTIVE_COL
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

    # â”€â”€ Confirm / instructions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if pre_battle_mode:
        inst = {
            "pick_adventurers": "Click a party slot below to edit their sets.",
            "pick_sig": "Select a Signature Ability, then confirm.",
            "pick_basics": "Select 2 Basic Abilities, then confirm.",
            "pick_item": "Select 3 Artifacts, then confirm.",
        }
    else:
        inst = {
            "pick_adventurers": "Click roster to add/remove members. Click a filled slot to edit their sets.",
            "pick_sig": "Select a Signature Ability, then confirm.",
            "pick_basics": "Select 2 Basic Abilities, then confirm.",
            "pick_item": "Select 3 Artifacts, then confirm.",
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
            "pick_item": "Confirm Artifacts" if len(set(item_choice or [])) == 3 else f"Need {3 - len(set(item_choice or []))} more",
        }.get(sub_phase, "Confirm")
        can_confirm = {
            "pick_sig": sig_choice is not None,
            "pick_basics": len(basic_choices) == 2,
            "pick_item": len(set(item_choice or [])) == 3,
        }.get(sub_phase, False)

    confirm_rect = pygame.Rect(DETAIL_X + DETAIL_W - 230, DETAIL_Y + DETAIL_H - 55,
                               220, 44)
    draw_button(surf, confirm_rect, confirm_text, mouse_pos,
                normal=BLUE_DARK, hover=BLUE, disabled=not can_confirm, size=18)
    if can_confirm:
        clicks["confirm"] = confirm_rect

    # Import Team button â€” only shown in pick_adventurers, not pre_battle_mode, not when a slot is focused
    if sub_phase == "pick_adventurers" and not pre_battle_mode and focused_slot is None:
        import_rect = pygame.Rect(DETAIL_X + 14, DETAIL_Y + DETAIL_H - 55, 180, 44)
        draw_button(surf, import_rect, "Import Party", mouse_pos,
                    normal=PANEL, hover=PANEL_HIGHLIGHT, border=BORDER_ACTIVE, size=16)
        clicks["import_btn"] = import_rect

    # Back button for sub-phases after pick_adventurers
    if sub_phase != "pick_adventurers":
        back_rect = pygame.Rect(DETAIL_X + 14, DETAIL_Y + DETAIL_H - 55, 160, 44)
        draw_button(surf, back_rect, "â† Back", mouse_pos, size=16)
        clicks["back"] = back_rect

    return clicks


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
                              focused_slot: int = None,
                              artifact_focus=None,
                              drag_info: dict | None = None,
                              member_prompt_slot: int | None = None,
                              artifact_scroll: int = 0) -> dict:
    surf.fill(BG)
    clicks = {
        "roster_cards": [],
        "party_slots": [],
        "sig_buttons": [],
        "basic_buttons": [],
        "artifact_entries": [],
        "artifact_selected": [],
        "artifact_remove": [],
        "confirm": None,
        "back": None,
        "import_btn": None,
        "prompt_change": None,
        "prompt_details": None,
        "member_prompt_rect": None,
        "roster_viewport": None,
        "roster_scroll_max": 0,
        "artifact_viewport": None,
        "artifact_scroll_max": 0,
        "roster_drop_zone": None,
        "artifact_hover": [],
    }
    drag_info = drag_info or {}
    slot_labels = ["Back Left", "Back Right", "Frontline"]
    slot_short = ["BL", "BR", "FL"]
    team_artifacts = []
    for pick in team_picks or []:
        if pick:
            team_artifacts = list(pick.get("team_artifacts", []))
            break
    if not team_artifacts:
        team_artifacts = list(item_choice or [])
    title = "Pre-Battle Setup" if pre_battle_mode else f"{player_name} - Build Party"
    draw_text(surf, title, 30, TEXT, WIDTH // 2, 28, center=True)

    left_rect = None
    if not pre_battle_mode:
        left_rect = pygame.Rect(24, 74, 392, 794)
        clicks["roster_drop_zone"] = left_rect
        draw_panel(surf, left_rect)
        draw_text(surf, "Adventurer Roster", 22, TEXT, left_rect.x + 18, left_rect.y + 16)
        draw_text(
            surf,
            "Drag into a party slot. Double-click for details.",
            14,
            TEXT_DIM,
            left_rect.x + 18,
            left_rect.y + 46,
        )
        roster_view = pygame.Rect(left_rect.x + 14, left_rect.y + 80, left_rect.w - 28, left_rect.h - 110)
        clicks["roster_viewport"] = roster_view
        sorted_roster = sorted(roster, key=lambda d: (d.cls, d.name))
        card_h = 86
        content_h = len(sorted_roster) * (card_h + 10)
        max_scroll = max(0, content_h - roster_view.h)
        scroll = max(0, min(scroll_offset, max_scroll))
        clicks["roster_scroll_max"] = max_scroll
        prev_clip = surf.get_clip()
        surf.set_clip(roster_view)
        for idx, defn in enumerate(sorted_roster):
            y = roster_view.y + idx * (card_h + 10) - scroll
            rect = pygame.Rect(roster_view.x, y, roster_view.w, card_h)
            if rect.bottom < roster_view.y or rect.top > roster_view.bottom:
                continue
            in_team = any(pick and pick.get("definition") == defn for pick in team_picks)
            selected = selected_idx is defn
            draw_adventurer_card(surf, rect, defn, selected, in_team, mouse_pos, status_rects_out)
            clicks["roster_cards"].append((rect, defn))
        surf.set_clip(prev_clip)
        _draw_scroll_arrows(surf, roster_view, scroll, max_scroll)
        if drag_info.get("active") and drag_info.get("hover_remove"):
            pygame.draw.rect(surf, RED, left_rect, 3, border_radius=10)
            draw_text(surf, "Release here to remove from party", 15, RED, left_rect.centerx, left_rect.bottom - 26, center=True)

    right_rect = pygame.Rect(448, 74, 928, 794) if not pre_battle_mode else pygame.Rect(220, 74, 960, 794)
    draw_panel(surf, right_rect)
    header_y = right_rect.y + 14
    draw_text(surf, "Party Formation", 22, TEXT, right_rect.x + 20, header_y)
    fill_count = sum(1 for pick in team_picks if pick)
    ready_count = sum(1 for pick in team_picks if pick and "signature" in pick and len(pick.get("basics", [])) == 2)
    draw_text(surf, f"Party {fill_count}/3   Sets {ready_count}/3   Artifacts {len(team_artifacts)}/3", 15, TEXT_DIM, right_rect.right - 20, header_y + 4, right=True)

    party_rect = pygame.Rect(right_rect.x + 18, right_rect.y + 52, right_rect.w - 36, 232)
    editor_rect = pygame.Rect(right_rect.x + 18, party_rect.bottom + 14, right_rect.w - 36, 310)
    artifact_rect = pygame.Rect(right_rect.x + 18, editor_rect.bottom + 14, right_rect.w - 36, right_rect.bottom - (editor_rect.bottom + 32))

    draw_rect_border(surf, party_rect, PANEL_ALT, BORDER)
    draw_rect_border(surf, editor_rect, PANEL_ALT, BORDER)
    draw_rect_border(surf, artifact_rect, PANEL_ALT, BORDER)

    party_slots = [
        pygame.Rect(party_rect.centerx - 255, party_rect.y + 20, 210, 92),
        pygame.Rect(party_rect.centerx + 45, party_rect.y + 20, 210, 92),
        pygame.Rect(party_rect.centerx - 105, party_rect.y + 126, 210, 92),
    ]
    for idx, rect in enumerate(party_slots):
        pick = team_picks[idx] if idx < len(team_picks) else None
        hovered_drop = drag_info.get("active") and drag_info.get("hover_slot") == idx
        is_focused = focused_slot == idx
        fill = PANEL_HIGHLIGHT if hovered_drop else PANEL
        border = BORDER_ACTIVE if (hovered_drop or is_focused) else BORDER
        if pick and pick.get("definition"):
            defn = pick["definition"]
            fill = tuple(min(255, c + 12) for c in CLASS_COLORS.get(defn.cls, PANEL_ALT))
        draw_rect_border(surf, rect, fill, border)
        clicks["party_slots"].append((rect, idx))
        draw_text(surf, slot_labels[idx], 13, TEXT_MUTED, rect.x + 10, rect.y + 8)
        if pick and pick.get("definition"):
            defn = pick["definition"]
            draw_text(surf, defn.name, 18, TEXT, rect.x + 10, rect.y + 30)
            draw_text(surf, cls_label(defn.cls), 13, CLASS_TEXT_COLORS.get(defn.cls, TEXT_MUTED), rect.x + 10, rect.y + 52)
            sig_ready = "signature" in pick
            basics_ready = len(pick.get("basics", [])) == 2
            draw_text(surf, f"Sig {'OK' if sig_ready else '--'}", 12, GREEN if sig_ready else TEXT_MUTED, rect.x + 10, rect.y + 70)
            draw_text(surf, f"Basics {len(pick.get('basics', []))}/2", 12, GREEN if basics_ready else TEXT_MUTED, rect.right - 10, rect.y + 70, right=True)
        else:
            draw_text(surf, "Drop Adventurer Here", 18, TEXT_MUTED, rect.centerx, rect.y + 34, center=True)
            draw_text(surf, slot_short[idx], 12, TEXT_DIM, rect.centerx, rect.y + 60, center=True)

    if drag_info.get("active"):
        arrow_pts = [
            (party_rect.centerx, party_rect.y + 95),
            (party_rect.centerx - 12, party_rect.y + 110),
            (party_rect.centerx + 12, party_rect.y + 110),
        ]
        pygame.draw.polygon(surf, TEXT_DIM, arrow_pts)

    editor_dx = editor_rect.x + 18
    editor_dy = editor_rect.y + 16
    focus_pick = team_picks[focused_slot] if focused_slot is not None and focused_slot < len(team_picks) else None
    if focus_pick and focus_pick.get("definition"):
        defn = focus_pick["definition"]
        draw_text(surf, f"{slot_labels[focused_slot]} Set", 20, TEXT, editor_dx, editor_dy)
        editor_dy += 28
        draw_text(surf, defn.name, 22, TEXT, editor_dx, editor_dy)
        draw_text(surf, cls_label(defn.cls), 14, CLASS_TEXT_COLORS.get(defn.cls, TEXT_MUTED), editor_dx + 250, editor_dy + 4)
        editor_dy += 28
        draw_text(surf, f"HP {defn.hp}   ATK {defn.attack}   DEF {defn.defense}   SPD {defn.speed}", 14, TEXT_DIM, editor_dx, editor_dy)
        editor_dy += 24
        draw_text(surf, "Signature", 15, CYAN, editor_dx, editor_dy)
        editor_dy += 20
        sigs = defn.sig_options[:sig_tier]
        sig_w = (editor_rect.w - 56 - 16) // 3
        for idx, sig in enumerate(sigs):
            rect = pygame.Rect(editor_dx + idx * (sig_w + 8), editor_dy, sig_w, 84)
            selected = sig_choice == idx or ("signature" in focus_pick and focus_pick["signature"].id == sig.id)
            draw_rect_border(surf, rect, PANEL_HIGHLIGHT if selected else PANEL, BORDER_ACTIVE if selected else BORDER)
            draw_text(surf, sig.name, 14, TEXT, rect.x + 8, rect.y + 8)
            summary = _mode_summary(sig.frontline)
            for line_idx, line in enumerate(_wrap_text(summary, 12, rect.w - 16)[:3]):
                _draw_rich_line(surf, line, 12, TEXT_DIM, rect.x + 8, rect.y + 28 + line_idx * 13, status_rects_out)
            clicks["sig_buttons"].append((rect, idx))
        editor_dy += 98
        draw_text(surf, "Basics (pick 2)", 15, CYAN, editor_dx, editor_dy)
        editor_dy += 20
        basics = class_basics.get(defn.cls, [])
        basic_w = (editor_rect.w - 56 - 12) // 2
        for idx, basic in enumerate(basics):
            row = idx // 2
            col = idx % 2
            rect = pygame.Rect(editor_dx + col * (basic_w + 12), editor_dy + row * 72, basic_w, 62)
            selected = idx in (basic_choices or [])
            draw_rect_border(surf, rect, PANEL_HIGHLIGHT if selected else PANEL, BORDER_ACTIVE if selected else BORDER)
            draw_text(surf, basic.name, 14, TEXT, rect.x + 8, rect.y + 8)
            summary = _mode_summary(basic.frontline)
            for line_idx, line in enumerate(_wrap_text(summary, 12, rect.w - 16)[:2]):
                _draw_rich_line(surf, line, 12, TEXT_DIM, rect.x + 8, rect.y + 28 + line_idx * 13, status_rects_out)
            clicks["basic_buttons"].append((rect, idx))
        status_y = editor_rect.bottom - 26
        set_ready = ("signature" in focus_pick) and len(focus_pick.get("basics", [])) == 2
        status_text = "Set locked in." if set_ready else "Choose 1 signature and 2 basics to finish this set."
        draw_text(surf, status_text, 14, GREEN if set_ready else TEXT_DIM, editor_dx, status_y)
    elif focused_slot is not None:
        draw_text(surf, slot_labels[focused_slot], 20, TEXT, editor_dx, editor_dy)
        editor_dy += 32
        draw_text(surf, "Drop an adventurer into this slot to begin.", 16, TEXT_MUTED, editor_dx, editor_dy)
    elif selected_idx is not None and not pre_battle_mode:
        defn = selected_idx
        draw_text(surf, defn.name, 22, TEXT, editor_dx, editor_dy)
        editor_dy += 28
        draw_text(surf, f"{cls_label(defn.cls)} - {defn.talent_name}", 15, YELLOW, editor_dx, editor_dy)
        editor_dy += 22
        for line in _wrap_text(defn.talent_text, 13, editor_rect.w - 36)[:6]:
            _draw_rich_line(surf, line, 13, TEXT_DIM, editor_dx, editor_dy, status_rects_out)
            editor_dy += 16
        draw_text(surf, "Double-click this adventurer for the full detail card.", 14, CYAN, editor_dx, editor_rect.bottom - 26)
    else:
        draw_text(surf, "Build Your Party", 22, TEXT, editor_dx, editor_dy)
        editor_dy += 30
        info_lines = [
            "Drag adventurers from the roster into the formation triangle.",
            "Drag a party member onto another slot to swap positions.",
            "Drag a party member back to the roster to remove them.",
            "Double-click roster cards for details, or party members for the set/details prompt.",
        ]
        for line in info_lines:
            draw_text(surf, line, 15, TEXT_DIM, editor_dx, editor_dy)
            editor_dy += 22

    art_dx = artifact_rect.x + 18
    art_dy = artifact_rect.y + 14
    draw_text(surf, "Party Artifacts", 20, TEXT, art_dx, art_dy)
    draw_text(surf, "Up to 3 shared artifacts. Click the list to add, click a selected artifact to inspect it.", 13, TEXT_DIM, art_dx, art_dy + 24)
    tray_y = art_dy + 50
    for idx in range(3):
        rect = pygame.Rect(art_dx + idx * 176, tray_y, 164, 54)
        artifact = team_artifacts[idx] if idx < len(team_artifacts) else None
        draw_rect_border(surf, rect, PANEL, BORDER_ACTIVE if artifact_focus and artifact and artifact_focus.id == artifact.id else BORDER)
        if artifact:
            name_rect = draw_text(surf, artifact.name, 14, TEXT, rect.x + 8, rect.y + 8)
            clicks["artifact_hover"].append((name_rect, artifact))
            draw_text(surf, "Reactive" if artifact.reactive else "Active", 12, TYPE_PASSIVE_COL if artifact.reactive else TYPE_ACTIVE_COL, rect.x + 8, rect.y + 28)
            clicks["artifact_selected"].append((rect, artifact))
            remove_rect = pygame.Rect(rect.right - 24, rect.y + 6, 18, 18)
            pygame.draw.rect(surf, RED_DARK, remove_rect, border_radius=4)
            draw_text(surf, "x", 12, RED, remove_rect.centerx, remove_rect.y + 1, center=True)
            clicks["artifact_remove"].append((remove_rect, artifact))
        else:
            draw_text(surf, "Empty", 14, TEXT_MUTED, rect.centerx, rect.y + 18, center=True)
    list_rect = pygame.Rect(art_dx, artifact_rect.y + 118, 320, artifact_rect.h - 132)
    desc_rect = pygame.Rect(list_rect.right + 18, artifact_rect.y + 118, artifact_rect.right - (list_rect.right + 34), artifact_rect.h - 132)
    draw_rect_border(surf, list_rect, PANEL, BORDER)
    draw_rect_border(surf, desc_rect, PANEL, BORDER)
    clicks["artifact_viewport"] = list_rect
    art_content_h = len(items) * 42
    art_scroll_max = max(0, art_content_h - list_rect.h)
    art_scroll = max(0, min(artifact_scroll, art_scroll_max))
    clicks["artifact_scroll_max"] = art_scroll_max
    prev_clip = surf.get_clip()
    surf.set_clip(list_rect)
    for idx, artifact in enumerate(items):
        y = list_rect.y + idx * 42 - art_scroll
        rect = pygame.Rect(list_rect.x + 6, y, list_rect.w - 12, 36)
        if rect.bottom < list_rect.y or rect.top > list_rect.bottom:
            continue
        selected = artifact.id in {entry.id for entry in team_artifacts}
        draw_rect_border(surf, rect, PANEL_HIGHLIGHT if selected else PANEL_ALT, BORDER_ACTIVE if selected else BORDER)
        name_rect = draw_text(surf, artifact.name, 13, TEXT, rect.x + 8, rect.y + 7)
        clicks["artifact_hover"].append((name_rect, artifact))
        tag = "Selected" if selected else "Click to Add"
        color = GREEN if selected else TEXT_DIM
        draw_text(surf, tag, 12, color, rect.right - 8, rect.y + 8, right=True)
        clicks["artifact_entries"].append((rect, artifact))
    surf.set_clip(prev_clip)
    _draw_scroll_arrows(surf, list_rect, art_scroll, art_scroll_max)
    focused_artifact = artifact_focus or (team_artifacts[0] if team_artifacts else None)
    if focused_artifact:
        name_rect = draw_text(surf, focused_artifact.name, 18, TEXT, desc_rect.x + 12, desc_rect.y + 10)
        clicks["artifact_hover"].append((name_rect, focused_artifact))
        draw_text(surf, f"Cooldown: {focused_artifact.cooldown}", 13, TEXT_DIM, desc_rect.x + 12, desc_rect.y + 34)
        draw_text(surf, "Reactive" if focused_artifact.reactive else "Active", 13, TYPE_PASSIVE_COL if focused_artifact.reactive else TYPE_ACTIVE_COL, desc_rect.x + 12, desc_rect.y + 54)
        dy = desc_rect.y + 78
        for line in _wrap_text(focused_artifact.description, 13, desc_rect.w - 24):
            _draw_rich_line(surf, line, 13, TEXT_DIM, desc_rect.x + 12, dy, status_rects_out)
            dy += 16
    else:
        draw_text(surf, "Select an artifact to read what it does.", 15, TEXT_MUTED, desc_rect.x + 12, desc_rect.y + 16)

    back_rect = pygame.Rect(right_rect.x + 18, right_rect.bottom - 58, 160, 42)
    draw_button(surf, back_rect, "Back", mouse_pos, size=18)
    clicks["back"] = back_rect
    can_confirm = all(pick and "signature" in pick and len(pick.get("basics", [])) == 2 for pick in team_picks)
    if can_confirm:
        confirm_rect = pygame.Rect(right_rect.right - 220, right_rect.bottom - 58, 200, 42)
        draw_button(surf, confirm_rect, confirm_label, mouse_pos, normal=BLUE_DARK, hover=BLUE, size=18)
        clicks["confirm"] = confirm_rect
    else:
        draw_text(surf, "Finish all three sets to continue.", 14, TEXT_DIM, right_rect.right - 20, right_rect.bottom - 48, right=True)

    if not pre_battle_mode:
        import_rect = pygame.Rect(left_rect.x + 14, left_rect.bottom - 48, left_rect.w - 28, 36)
        draw_button(surf, import_rect, "Import Party", mouse_pos, normal=PANEL, hover=PANEL_HIGHLIGHT, border=BORDER_ACTIVE, size=16)
        clicks["import_btn"] = import_rect

    if member_prompt_slot is not None and 0 <= member_prompt_slot < len(team_picks) and team_picks[member_prompt_slot]:
        anchor = party_slots[member_prompt_slot]
        prompt_rect = pygame.Rect(min(anchor.centerx - 120, right_rect.right - 256), min(anchor.bottom + 10, right_rect.bottom - 126), 240, 108)
        draw_rect_border(surf, prompt_rect, PANEL, BORDER_ACTIVE)
        draw_text(surf, "Party Member", 16, TEXT, prompt_rect.centerx, prompt_rect.y + 10, center=True)
        change_rect = pygame.Rect(prompt_rect.x + 18, prompt_rect.y + 40, prompt_rect.w - 36, 24)
        detail_rect = pygame.Rect(prompt_rect.x + 18, prompt_rect.y + 72, prompt_rect.w - 36, 24)
        draw_button(surf, change_rect, "Change Set", mouse_pos, normal=(45, 72, 96), hover=(62, 102, 136), size=15)
        draw_button(surf, detail_rect, "View Details", mouse_pos, normal=PANEL_ALT, hover=PANEL_HIGHLIGHT, size=15)
        clicks["member_prompt_rect"] = prompt_rect
        clicks["prompt_change"] = change_rect
        clicks["prompt_details"] = detail_rect

    if drag_info.get("active") and drag_info.get("defn") is not None:
        ghost = pygame.Rect(mouse_pos[0] - 110, mouse_pos[1] - 36, 220, 72)
        ghost_surf = pygame.Surface((ghost.w, ghost.h), pygame.SRCALPHA)
        ghost_surf.fill((18, 24, 34, 220))
        surf.blit(ghost_surf, ghost.topleft)
        pygame.draw.rect(surf, BORDER_ACTIVE, ghost, 2, border_radius=8)
        draw_text(surf, drag_info["defn"].name, 16, TEXT, ghost.x + 10, ghost.y + 10)
        draw_text(surf, cls_label(drag_info["defn"].cls), 13, CLASS_TEXT_COLORS.get(drag_info["defn"].cls, TEXT_MUTED), ghost.x + 10, ghost.y + 34)

    return clicks


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# IMPORT TEAM MODAL
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SPECIAL ABILITY DESCRIPTIONS  (human-readable text for each special key)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SPECIAL_DESCRIPTIONS: dict = {
    # Basic â€“ Fighter
    "rend_back":                       "user's next ability against this target gains +10 Power",
    "cleave_back":                     "user's next ability against this target ignores 10% Defense",
    # Basic â€“ Rogue
    "riposte_damage_reduction":        "user takes 50% less damage this round",
    "fleetfooted_front":               "first incoming ability each round deals 15% less damage",
    "fleetfooted_back":                "first incoming ability each round deals 12% less damage",
    # Basic â€“ Warden
    "slam_bonus_if_guarded":           "+15 power if user is Guarded",
    "slam_back_guard":                 "Guards user for 2 rounds",
    "stalwart_front":                  "user takes -12 damage from abilities",
    "stalwart_back":                   "frontline ally takes -12 damage from abilities",
    "protection_front":                "allies have +12 Defense",
    "protection_back":                 "allies have +7 Defense",
    # Basic â€“ Mage
    "arcane_wave_self_debuff":         "self: -10 Atk for 2 rounds",
    "ominous_gale_back":               "refresh the duration of target's last inflicted status",
    "breakthrough_front":              "for 2 rounds: user's abilities become spread",
    # Basic â€“ Ranger
    "sucker_punch_front":              "+15 power if target is Exposed or Shocked",
    "trapping_blow_root_spotlight":    "Roots Spotlighted targets for 2 rounds",
    "trapping_blow_root_weakened":     "Roots Weakened targets for 2 rounds",
    "hunters_mark_dot":                "target takes +12 damage from abilities next round",
    # Basic â€“ Cleric
    "medic_front":                     "healing effects cure status conditions and debuffs",
    "medic_back":                      "healing effects cure the last inflicted status condition or debuff",
    # Risa
    "crimson_fury_recoil":             "after dealing damage, Risa takes recoil equal to 30% of damage dealt",
    "wolfs_pursuit_retarget":          "if target swaps, follow them with Wolf's Pursuit",
    "blood_hunt_hp_avg":               "sets Risa and target HP to the average of both",
    "stomach_of_the_wolf":             "for 2 rounds: Red and Wolf is always active and its lifesteal is doubled",
    # Jack
    "belligerence_ignore_atk":         "Jack ignores 20% of enemy Attack",
    "magic_growth_power_buff":         "Jack's next ability gains +15 power",
    "castle_on_cloud_nine":            "for 2 rounds: abilities cleave half of the target's Defense",
    # Gretel
    "hot_mitts_front":                 "abilities Burn target (2r), or deal +15% damage to Burned targets",
    "hot_mitts_back":                  "abilities Burn target for 2 rounds",
    "crumb_trail_front":               "+20 power if an ally picked up a crumb this turn",
    "crumb_trail_drop":                "drop a crumb; allies who swap here heal 40 HP",
    "shove_over_next_atk_bonus":       "+15 power on next attack against this target",
    "into_the_oven":                   "for 2 rounds: enemies take +10 damage from all sources",
    # Constantine
    "nine_lives":                      "up to 3x/battle: survive fatal damage at 1 HP (vs Exposed attackers)",
    "subterfuge_swap":                 "swap target and enemy after ability resolves",
    "all_seeing":                      "for 2 rounds: cannot lose initiative; Expose all enemies",
    "final_deception":                 "Expose all enemies and steal 5 Atk from each for 2 rounds",
    # Hunold
    "hypnotic_aura_front":             "Shocked enemies' abilities are redirected to Hunold's back-left",
    "hypnotic_aura_back":              "Shocked enemies' abilities are redirected to Hunold's frontline",
    "mass_hysteria":                   "for 2 rounds: abilities become spread and ignore melee restriction/spread penalty",
    "devils_due":                      "Hunold uses one of his abilities as spread, ignoring melee restriction and spread damage penalty",
    # Reynard
    "feign_weakness_retaliate_45":     "retaliate 45 power vs incoming attackers next round",
    "feign_weakness_retaliate_40":     "retaliate 45 power vs incoming attackers next round",
    "smoke_and_mirrors":               "for 2 rounds: retaliate 70 power and steal 12 Speed from incoming attackers",
    "last_laugh":                      "retaliate 70 power + steal 12 Speed (2r) vs incoming attackers",
    "cutpurse_swap_frontline":         "swap Reynard with frontline ally",
    # Roland
    "shimmering_valor_front":          "35% damage reduction for 3 rounds (ends when Roland swaps)",
    "shimmering_valor_back":           "Roland heals 60 HP + 20 HP per remaining Valor round",
    "taunt_target":                    "Taunt target for 2 rounds (forced to target Roland)",
    "taunt_front_ranged":              "Taunt front-most ranged enemy for 2 rounds",
    "banner_of_command":               "Guard ally for 2 rounds whenever they swap",
    "purehearted_stand":               "for 2 rounds: Silver Aegis is always active",
    # Porcus
    "nbth_self_reduce":                "Bricklayer is doubled and triggers on all incoming abilities next round",
    "nbth_ally_reduce":                "Bricklayer triggers on all incoming abilities next round",
    "porcine_honor_self":              "Guard Porcus for 1 round at the start of each round",
    "porcine_honor_ally":              "Guard frontline ally for 1 round at the start of each round",
    "sturdy_home_front":               "when Bricklayer triggers, Porcus gains +20 Attack for 2 rounds",
    "sturdy_home_back":                "frontline ally gets the effects of Bricklayer",
    "unfettered":                      "for 2 rounds: +100 Attack, -50 Defense, +100 Speed",
    # Lady
    "postmortem_passage":              "when ally is KO'd, they fire a 55-power attack at attacker",
    "drown_dmg_bonus":                 "target takes +10 damage from all sources for 2 rounds",
    "lakes_gift_pool_front":           "ally gains Reflecting Pool (2r) and +12 Atk (2r)",
    "lakes_gift_pool_back":            "ally gains Reflecting Pool (2r)",
    "journey_to_avalon":               "for 2 rounds: allies gain Reflecting Pool; if an ally is KO'd, the Lady is sacrificed to revive them at 60% HP",
    # Ella
    "dying_dance_front":               "Shocks Spotlighted targets for 2 rounds",
    "midnight_dour_swap":              "when reduced to <=50% HP, Ella swaps with an ally (once per round)",
    "ella_ignore_two_lives":           "ignores Two Lives backline restriction",
    "struck_midnight_untargetable":    "Burn all enemies; Ella cannot act or be targeted for 2 rounds",
    # March Hare
    "tempus_fugit_back":               "ignores ranged recharge if target is slower",
    "rabbit_hole_extra_action":        "March Hare gains an extra action next round",
    "rabbit_hole_swap":                "March Hare swaps with an ally",
    "nebulous_ides_back":              "+15 power if March Hare swapped this round",
    "stitch_extra_action_now":         "March Hare gains an extra action this round",
    # Witch
    "toil_spread_status_right":        "spreads target's last status to enemy adjacent to their right",
    "cauldron_extend_status":          "increases target's status duration by 1 round",
    "crawling_abode":                  "+10 spd if frontline enemy is statused; 2+ statuses deal +10 dmg",
    "vile_sabbath":                    "for 2 rounds: Double Double also refreshes the target's status durations",
    # Briar Rose
    "thorn_snare_back":                "Spotlights Rooted targets for 2 rounds",
    "creeping_doubt_front":            "+15 power against Rooted targets",
    "garden_of_thorns_attack":         "enemies who attack Briar are Rooted for 2 rounds",
    "garden_of_thorns_swap":           "enemies that swap are Rooted for 2 rounds",
    "falling_kingdom":                 "for 2 rounds: Curse of Sleeping no longer removes or restricts Root; Root all enemies for 2 rounds",
    # Frederic
    "heros_charge_ignore_pride_front": "ignore Heedless Pride incoming bonus damage this round",
    "raze_the_village":                "for 2 rounds: ignore Heedless Pride incoming bonus damage; Spotlight all enemies",
    # Robin
    "spread_fortune_front":            "spread ability damage penalty is halved",
    "spread_fortune_back":             "spread abilities target all enemies",
    "bring_down_steal_atk":            "steal 7 Atk from target for 2r (if target is backline)",
    "lawless":                         "for 2 rounds: abilities cannot be redirected and ignore targeting restrictions",
    # Aldric
    "benefactor_front":                "healing effects restore 35% more HP",
    "benefactor_back":                 "healing effects restore 20% more HP",
    "sanctuary_front":                 "allies heal 1/8 max HP each round",
    "sanctuary_back":                  "frontline ally heals 1/8 max HP each round",
    "repentance_front":                "next ability against target has 25% lifesteal (triggers All-Caring)",
    "redemption":                      "for 2 rounds: All-Caring can swap healed allies with an ally",
    # Liesl
    "cinder_blessing_avg":             "sets Liesl and ally HP to the average of both",
    "flame_of_renewal":                "when Liesl is KO'd, allies heal 1/2 max HP + Purifying Flame",
    "cleansing_inferno":               "for 2 rounds: whenever an enemy loses HP, the lowest-HP ally heals that amount",
    # Aurora
    "toxin_purge_all":                 "remove all status conditions from Aurora or an ally; heal 12 per removed",
    "toxin_purge_last":                "remove last inflicted status from Aurora or an ally",
    "birdsong_front":                  "when Innocent Heart triggers, gain a bird; Aurora abilities deal +7 damage per bird (up to x3)",
    "birdsong_back":                   "end of round: cure Aurora if she has a bird, plus one more ally per additional bird clockwise",
    "deathlike_slumber":               "for 2 rounds: Aurora cannot act; damage to her is divided among allies and removes their statuses",
    # Noble basics
    "summons_swap_cleanse":          "swap with an ally and remove that ally's stat buffs and debuffs",
    "command_front":                 "enemies that attacked user last round take +7 damage from ally abilities",
    "command_back":                  "enemies that attacked allies last round take +7 damage from user's abilities",
    # Prince Charming (Noble)
    "condescend_back":               "next ability against target has +10 power",
    "gallant_charge_front":          "+15 power if Prince Charming was backline last round",
    "chosen_one":                    "first ally swapped with becomes champion; attackers take +15 from next ability",
    "happily_ever_after":            "for 2 rounds: Prince Charming and target ally can use each other's abilities",
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
    "ivory_tower_front":             "ranged enemies have -12 defense",
    "ivory_tower_back":              "melee enemies have -12 attack",
    "severed_tether":                "Flowing Locks always active 2r; -15 def, +30 atk, +30 speed (2r)",
    # Warlock basics
    "warlock_gain_malice_1":          "gain 1 Malice",
    "warlock_spend1_weaken":         "spend 1 Malice to Weaken target for 2 rounds",
    "warlock_spend1_expose":         "spend 1 Malice to Expose target for 2 rounds",
    "blood_pact_front":              "lose 45 HP and gain 2 Malice",
    "blood_pact_back":               "heal 30 HP; spend 1 Malice to heal 30 more HP",
    "cursed_armor":                  "gain 1 Malice whenever damaged by an enemy ability",
    "void_step_front":               "on swapping to backline, gain 1 Malice",
    "void_step_back":                "on swapping to frontline, spend 2 Malice for +12 Spd (2r)",
    # Pinocchio (Warlock)
    "wooden_wallop_front":           "+5 power per Malice",
    "cut_strings_back":              "spend 2 Malice to Spotlight target for 2 rounds",
    "become_real_front":             "at 3+ Malice: abilities gain +10 damage; immune to statuses",
    "become_real_back":              "at 3+ Malice: abilities do not increment ranged recharge",
    "blue_faerie_boon":              "gain 6 Malice, up to 12",
    # Rumpelstiltskin (Warlock)
    "straw_to_gold_front":           "steal ally's highest stat buff for 2r; +5 strength per Malice; return later",
    "straw_to_gold_back":            "convert an ally's highest stat debuff into a stat buff",
    "name_the_price_front":          "target gains +7 Atk for 2 rounds",
    "name_the_price_back":           "spend 2 Malice to nullify target's stat buffs for 2 rounds",
    "spinning_wheel_front":          "+5 ability damage per unique stat buff among all adventurers",
    "spinning_wheel_back":           "when an ally loses a stat buff, spend 2 Malice to refresh it",
    "devils_nursery":                "for 2 rounds: stat buffs gain +5 per Malice; steal and refresh all enemy stat buffs",
    # Sea Wench Asha (Warlock)
    "misappropriate_front":          "spend 1 Malice to use enemy frontline signature (or gain passive for 2r)",
    "abyssal_call_front":            "spend 1 Malice: target gets -12 Def for 2 rounds",
    "abyssal_call_back":             "refresh target's existing stat debuffs",
    "faustian_bargain_front":        "on swap to frontline, spend 1 Malice to gain bottled talent for 2r",
    "faustian_bargain_back":         "on KO, bottle target's talent and gain +12 Spd for 2 rounds",
    "foam_prison":                   "block target frontline's twist for 2 rounds, then copy and use that twist",
    # Dragon Head abilities
    "sovereign_edict_front":         "if target has 2+ statuses, ignore Guard and defense buffs",
    "sovereign_edict_back":          "Spotlight target for 2 rounds",
    "cataclysm_front":               "+10 damage per status on target",
    "cataclysm_back":                "refresh all of target's status durations",
    "dark_aura_passive":             "end of round: spend 2 Malice to Weaken all enemies",
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
    return summary[:92] + "â€¦" if len(summary) > 93 else summary


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
    if mode.bonus_vs_statused:    bonuses.append(f"+{mode.bonus_vs_statused} vs statused target")
    if bonuses:
        parts.append("  ".join(bonuses))
    if mode.double_vamp_no_base:
        parts.append("2Ã— lifesteal (no base lifesteal on this ability)")
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
    return parts if parts else ["â€”"]


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


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# COMBATANT DETAIL PANEL  (battle-screen info view)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

BATTLE_DETAIL_RECT = pygame.Rect(450, 86, 500, 620)


def draw_combatant_detail(surf, unit: CombatantState,
                           rect: pygame.Rect = None,
                           status_rects_out: list = None) -> pygame.Rect:
    """
    Draw the full detail card for a combatant during the battle screen.
    Shows: stats, talent, signature, basics, and twist.
    Returns the close-button rect.
    """
    r = rect or BATTLE_DETAIL_RECT
    draw_rect_border(surf, r, PANEL, BORDER_ACTIVE, width=2)

    x, y = r.x + 12, r.y + 8
    w = r.width - 24

    # Close button
    close_rect = pygame.Rect(r.right - 26, r.y + 6, 20, 20)
    draw_rect_border(surf, close_rect, (70, 40, 40), RED_DARK)
    draw_text(surf, "Ã—", 15, TEXT, close_rect.centerx, close_rect.centery, center=True)

    # â”€â”€ Name + class + stats â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    # â”€â”€ Talent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    draw_text(surf, f"Talent: {unit.defn.talent_name}", 14, YELLOW, x, y)
    y += 18
    for line in _wrap_text(unit.defn.talent_text, 13, w - 8):
        if y + 14 > r.bottom - 4:
            break
        _draw_rich_line(surf, line, 13, TEXT_DIM, x + 8, y, status_rects_out)
        y += 15
    y += 4

    # â”€â”€ Signature â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    pygame.draw.line(surf, BORDER, (x, y), (x + w, y), 1)
    y += 5
    for _sig_name_line in _wrap_text("Signature  -  " + unit.sig.name, 14, w - 8):
        if y + 14 > r.bottom - 4:
            break
        draw_text(surf, _sig_name_line, 14, CYAN, x, y)
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

    # â”€â”€ Basics â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    pygame.draw.line(surf, BORDER, (x, y), (x + w, y), 1)
    y += 5
    twist = unit.defn.twist
    for _twist_name_line in _wrap_text("Twist  -  " + twist.name, 14, w - 8):
        if y + 14 > r.bottom - 4:
            break
        draw_text(surf, _twist_name_line, 14, ORANGE, x, y)
        y += 17
    draw_text(surf, "Active", 12, TYPE_ACTIVE_COL, x + 8, y)
    y += 14
    if _fl_bl_same(twist):
        lines = _mode_detail_lines(twist.frontline)
        for _line in _wrap_text(f"FL & BL: {lines[0]}", 12, w - 20):
            if y + 13 > r.bottom - 4:
                break
            _draw_rich_line(surf, _line, 12, TEXT_DIM, x + 8, y, status_rects_out)
            y += 13
        for extra in lines[1:]:
            for _line in _wrap_text(f"         {extra}", 12, w - 20):
                if y + 13 > r.bottom - 4:
                    break
                _draw_rich_line(surf, _line, 12, TEXT_MUTED, x + 8, y, status_rects_out)
                y += 13
    else:
        for prefix, mode in (("FL", twist.frontline), ("BL", twist.backline)):
            lines = _mode_detail_lines(mode)
            for _line in _wrap_text(f"{prefix}: {lines[0]}", 12, w - 20):
                if y + 13 > r.bottom - 4:
                    break
                _draw_rich_line(surf, _line, 12, TEXT_DIM, x + 8, y, status_rects_out)
                y += 13
            for extra in lines[1:]:
                for _line in _wrap_text(f"      {extra}", 12, w - 20):
                    if y + 13 > r.bottom - 4:
                        break
                    _draw_rich_line(surf, _line, 12, TEXT_MUTED, x + 8, y, status_rects_out)
                    y += 13

    return close_rect


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# RESULT SCREEN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _progress_line_color(text: str):
    lower = (text or "").lower()
    if "gold" in lower:
        return YELLOW
    if "gained" in lower:
        return GREEN
    if "level up" in lower:
        return CYAN
    if "unlocked" in lower or "voucher" in lower or "slots" in lower:
        return ORANGE
    if "rating" in lower:
        return CYAN
    if "renown" in lower:
        return GREEN if "+" in text else RED
    return TEXT


def _draw_centered_wrapped_lines(surf, lines: list[str], center_x: int, start_y: int, max_width: int,
                                 *, size: int = 16, line_gap: int = 6):
    y = start_y
    for line in lines:
        color = _progress_line_color(line)
        wrapped = _wrap_text(line, size, max_width) or [line]
        for segment in wrapped:
            draw_text(surf, segment, size, color, center_x, y, center=True)
            y += size + line_gap
    return y


def _class_basic_unlock_level(index: int) -> int:
    return 1 if index < 2 else index


def draw_result_screen(surf, battle: BattleState, mouse_pos, subtitle: str = "", detail_lines: list | None = None):
    surf.fill(BG)
    cx, cy = WIDTH // 2, HEIGHT // 2
    winner_name = battle.get_team(battle.winner).player_name if battle.winner else "?"
    draw_text(surf, "VICTORY!", 72, YELLOW, cx, cy - 120, center=True)
    draw_text(surf, f"{winner_name} wins!", 36, TEXT, cx, cy - 40, center=True)
    draw_text(surf, f"Battle lasted {battle.round_num} rounds.", 22, TEXT_DIM,
              cx, cy + 20, center=True)
    if subtitle:
        draw_text(surf, subtitle, 18, CYAN, cx, cy + 52, center=True)
    _draw_centered_wrapped_lines(surf, list(detail_lines or [])[:10], cx, cy + 84, 820, size=16)

    menu_btn   = pygame.Rect(cx - 160, HEIGHT - 100, 150, 52)
    rematch_btn = pygame.Rect(cx + 10,  HEIGHT - 100, 150, 52)
    draw_button(surf, menu_btn,    "Main Menu",  mouse_pos, size=20)
    draw_button(surf, rematch_btn, "Quit",       mouse_pos, size=20)
    return menu_btn, rematch_btn


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TOP BAR (used during battle)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def draw_top_bar(surf, battle: BattleState, phase_label: str):
    bar = pygame.Rect(0, 0, WIDTH, 55)
    pygame.draw.rect(surf, PANEL, bar)
    pygame.draw.line(surf, BORDER, (0, 55), (WIDTH, 55), 1)

    def _fit_text(text: str, size: int, max_width: int) -> str:
        f = font(size)
        if f.size(text)[0] <= max_width:
            return text
        trimmed = text
        ellipsis = "..."
        while trimmed and f.size(trimmed + ellipsis)[0] > max_width:
            trimmed = trimmed[:-1]
        return (trimmed + ellipsis) if trimmed else ellipsis

    def _artifact_summary(team: TeamState) -> str:
        if not team.artifacts:
            return "none"
        parts = []
        for state in team.artifacts:
            label = state.artifact.name
            if state.cooldown_remaining > 0:
                label += f" ({state.cooldown_remaining})"
            parts.append(label)
        return ", ".join(parts)

    # Left: game title and round info
    draw_text(surf, "FABLED", 22, TEXT, 14, 14)
    draw_text(surf, f"Round {battle.round_num}", 20, YELLOW, 120, 17)
    draw_text(surf, f"Init: P{battle.init_player}", 16, CYAN, 240, 19)

    # Centre: matchup (clear gap from left items above)
    draw_text(surf, f"{battle.team1.player_name}  vs  {battle.team2.player_name}",
              18, TEXT, WIDTH // 2, 17, center=True)

    # Right: phase label â€” right-aligned so it never overlaps the centre text
    draw_text(surf, phase_label, 16, TEXT_DIM, WIDTH - 10, 19, right=True)

    p1_artifacts = _fit_text(f"P1 Artifacts: {_artifact_summary(battle.team1)}", 11, WIDTH // 2 - 24)
    p2_artifacts = _fit_text(f"P2 Artifacts: {_artifact_summary(battle.team2)}", 11, WIDTH // 2 - 24)
    draw_text(surf, p1_artifacts, 11, GREEN, 14, 38)
    draw_text(surf, p2_artifacts, 11, BLUE, WIDTH - 10, 38, right=True)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CAMPAIGN UI
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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

    draw_text(surf, "FABLED â€” Quests", 48, TEXT, cx, 50, center=True)
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
            draw_text(surf, f"Encounters {first_q}â€“{last_q}  |  Level {mission.level_range[0]}â€“{mission.level_range[1]}",
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


def draw_quest_select(surf, mission, quests: list, mouse_pos, profile, reward_preview_map: dict | None = None) -> dict:
    """Show quests within a mission.  Returns click rects."""
    surf.fill(BG)
    cx = WIDTH // 2

    draw_text(surf, f"FABLED â€” {mission.name}", 40, TEXT, cx, 45, center=True)

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
            # Quest title â€” key_preview omitted for now; restore by appending:
            #   f"  â€”  {quest.key_preview}"
            draw_text(surf, f"Encounter {quest.quest_id}",
                      18, TEXT if not cleared else GREEN, rect.x + 14, rect.y + 10)
            reward_parts = list((reward_preview_map or {}).get(quest.quest_id, []))
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
            draw_text(surf, f"Encounter {quest.quest_id}  â€”  LOCKED", 16, TEXT_MUTED,
                      rect.x + 14, rect.y + 36)

    return {"quest_btns": quest_btns, "back_btn": back_btn}


def draw_pre_quest(surf, quest_def, mission, quest_pos: int, total_quests: int,
                   enemy_picks: list, mouse_pos, reward_preview_lines: list | None = None,
                   status_rects_out: list = None) -> dict:
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
    # Quest position â€” key_preview omitted for now; restore by appending:
    #   f"  \u00b7  {quest_def.key_preview}"
    draw_text(surf, f"Encounter {quest_pos} / {total_quests}",
              18, TEXT_DIM, cx, 78, center=True)

    # Mission description â€” wrapped so it never gets cut off
    desc = mission.description if mission else ""
    desc_y = 105
    artifact_hover = []
    for line in _wrap_text(desc, 14, 1000):
        draw_text(surf, line, 14, TEXT_MUTED, cx, desc_y, center=True)
        desc_y += 18

    enemy_team_artifacts = list(enemy_picks[0].get("team_artifacts", [])) if enemy_picks else []
    if enemy_team_artifacts:
        desc_y = draw_artifact_name_list(
            surf,
            "Enemy Artifacts: ",
            enemy_team_artifacts,
            size=14,
            prefix_color=ORANGE,
            artifact_color=ORANGE,
            x=cx,
            y=desc_y,
            artifact_rects_out=artifact_hover,
            max_width=1000,
            center=True,
        ) + 4

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
        if defn.talent_name and defn.talent_name != "â€”":
            draw_text(surf, f"Talent: {defn.talent_name}", 12, PURPLE, rect.x + 10, rect.y + 152)

    # Reward preview
    reward_y = card_y + card_h + 20
    draw_text(surf, "Rewards for Victory:", 18, TEXT_DIM, cx, reward_y, center=True)
    reward_y += 28

    parts = reward_preview_lines or ["No rewards preview available"]
    _draw_centered_wrapped_lines(surf, parts[:4], cx, reward_y, 860, size=16, line_gap=5)

    return {
        "start_btn": start_btn,
        "back_btn": back_btn,
        "enemy_cards": enemy_cards,
        "artifact_hover": artifact_hover,
    }


def draw_post_quest(surf, quest_def, won: bool, rewards: dict, mouse_pos,
                    detail_lines: list | None = None, subtitle: str = "") -> dict:
    """Show post-battle rewards screen."""
    surf.fill(BG)
    cx, cy = WIDTH // 2, HEIGHT // 2

    if won:
        draw_text(surf, "VICTORY!", 72, YELLOW, cx, cy - 170, center=True)
        draw_text(surf, f"Encounter {quest_def.quest_id} Cleared!", 34, GREEN,
                  cx, cy - 85, center=True)
        if subtitle:
            draw_text(surf, subtitle, 18, CYAN, cx, cy - 52, center=True)

        # Show rewards
        draw_text(surf, "Battle Summary:", 22, TEXT_DIM, cx, cy - 30, center=True)
        parts = list(detail_lines or [])
        if not parts:
            parts = ["Progress saved"]

        _draw_centered_wrapped_lines(surf, parts[:12], cx, cy + 10, 860, size=18, line_gap=6)
    else:
        draw_text(surf, "DEFEATED", 72, RED, cx, cy - 120, center=True)
        draw_text(surf, "No rewards â€” try again!", 28, TEXT_DIM, cx, cy - 30, center=True)

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
    draw_text(surf, "Your progress has been saved to your local account.", 22, GREEN,
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


def _reward_artifact_names(rewards: dict) -> list[str]:
    names = []
    seen = set()
    for artifact_id in rewards.get("artifacts", []):
        if artifact_id in ARTIFACTS_BY_ID and artifact_id not in seen:
            names.append(ARTIFACTS_BY_ID[artifact_id].name)
            seen.add(artifact_id)
    for item_id in rewards.get("items", []):
        artifact_id = LEGACY_ITEM_TO_ARTIFACT_ID.get(item_id)
        if artifact_id in ARTIFACTS_BY_ID and artifact_id not in seen:
            names.append(ARTIFACTS_BY_ID[artifact_id].name)
            seen.add(artifact_id)
    return names


def draw_catalog(surf, mouse_pos, active_tab: str, selected_idx,
                 scroll: int, profile, roster: list,
                 class_basics: dict, items: list,
                 status_rects_out: list = None,
                 filters: dict = None) -> dict:
    """
    Catalog screen — Adventurers / Classes / Artifacts tabs.
    filters: dict of active filter sets for the current tab.
    Returns click dict with keys: back_btn, tab_btns, list_btns, scroll_max,
            scroll_viewport, filter_chips, clear_all_btn.
    """
    surf.fill(BG)
    cx = WIDTH // 2

    back_btn = pygame.Rect(20, 18, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)
    draw_text(surf, "Guidebook", 40, TEXT, cx, 28, center=True)

    tab_labels = [("adventurers", "Adventurers"), ("classes", "Classes"), ("artifacts", "Artifacts")]
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
        draw_text(surf, label, 16, TEXT if is_active else TEXT_DIM, tr.centerx, tr.centery, center=True)
        tab_btns.append((tr, key))

    player_exp = getattr(profile, "player_exp", 0)
    player_level = player_level_from_exp(player_exp)
    exp_floor = total_exp_for_level(player_level)
    exp_into = player_exp - exp_floor
    exp_need = exp_to_next_level(player_level)
    player_slots = saved_team_slot_count(player_level)
    player_sigil_ready = player_sigil_unlocked(player_level)
    guild_vouchers = getattr(profile, "guild_vouchers", 0)

    summary_rect = pygame.Rect(20, 112, WIDTH - 40, 58)
    draw_rect_border(surf, summary_rect, PANEL, BORDER)
    draw_text(surf, f"Player Level {player_level}", 18, TEXT, summary_rect.x + 16, summary_rect.y + 10)
    draw_text(surf, f"EXP {exp_into}/{exp_need} to next level", 14, CYAN, summary_rect.x + 16, summary_rect.y + 32)
    draw_text(surf, f"Saved Parties {player_slots}", 16, YELLOW, summary_rect.centerx, summary_rect.y + 20, center=True)
    draw_text(
        surf,
        "Player Sigil Unlocked" if player_sigil_ready else "Player Sigil at Level 10",
        14,
        GREEN if player_sigil_ready else TEXT_MUTED,
        summary_rect.right - 18,
        summary_rect.y + 10,
        right=True,
    )
    draw_text(surf, f"Guild Vouchers {guild_vouchers}", 14, ORANGE, summary_rect.right - 18, summary_rect.y + 32, right=True)

    LIST_X, LIST_Y = 20, 188
    LIST_W, LIST_H = 360, 692
    DETAIL_PX, DETAIL_PY = 400, 188
    DETAIL_PW, DETAIL_PH = 980, 692
    FILTER_H = 94 if active_tab == "adventurers" else (58 if active_tab == "artifacts" else 0)

    detail_rect_c = pygame.Rect(DETAIL_PX, DETAIL_PY, DETAIL_PW, DETAIL_PH)
    draw_rect_border(surf, detail_rect_c, PANEL, BORDER)

    recruited = getattr(profile, "recruited", set())
    unlocked_artifacts = getattr(profile, "unlocked_artifacts", set())
    adventurer_clears = getattr(profile, "adventurer_quest_clears", {})
    class_points = getattr(profile, "class_points", {})
    all_classes = ["Fighter", "Rogue", "Warden", "Mage", "Ranger", "Cleric", "Noble", "Warlock"]
    class_thresholds = {2: 2, 3: 4, 4: 7, 5: 10}

    if active_tab == "adventurers":
        list_items = [d for d in roster if d.id in recruited]
    elif active_tab == "classes":
        list_items = [cls for cls in all_classes if cls in class_basics]
    else:
        list_items = [it for it in items if it.id in unlocked_artifacts]

    active_filters = filters or {}
    chip_w, chip_h, chip_gap = 84, 22, 4
    row_h = chip_h + chip_gap
    fx, fy = LIST_X + 6, LIST_Y + 5

    filter_chips = []
    clear_all_btn = None
    artifact_hover = []

    def _draw_chip(text, rect, active):
        if active:
            bg, bd, tc = (45, 70, 100), BORDER_ACTIVE, TEXT
        elif rect.collidepoint(mouse_pos):
            bg, bd, tc = PANEL_ALT, BORDER, TEXT_DIM
        else:
            bg, bd, tc = (28, 30, 38), BORDER, TEXT_MUTED
        draw_rect_border(surf, rect, bg, bd, width=1)
        draw_text(surf, text, 11, tc, rect.centerx, rect.centery, center=True)

    if FILTER_H > 0:
        filter_rect = pygame.Rect(LIST_X, LIST_Y, LIST_W, FILTER_H)
        draw_rect_border(surf, filter_rect, PANEL, BORDER)
        if active_tab == "adventurers":
            active_classes = active_filters.get("classes", set())
            for i, cls in enumerate(all_classes):
                row, col = divmod(i, 4)
                rect = pygame.Rect(fx + col * (chip_w + chip_gap), fy + row * row_h, chip_w, chip_h)
                _draw_chip(cls, rect, cls in active_classes)
                filter_chips.append((rect, "classes", cls))
            damage_y = fy + 2 * row_h
            active_damage = active_filters.get("damage_types", set())
            for i, (lbl, val) in enumerate([("Melee", "melee"), ("Ranged", "ranged"), ("Mixed", "mixed")]):
                rect = pygame.Rect(fx + i * (chip_w + chip_gap), damage_y, chip_w, chip_h)
                _draw_chip(lbl, rect, val in active_damage)
                filter_chips.append((rect, "damage_types", val))
            clear_all_btn = pygame.Rect(fx + 3 * (chip_w + chip_gap), damage_y, chip_w, chip_h)
        elif active_tab == "artifacts":
            active_types = active_filters.get("types", set())
            types_y = fy + row_h
            for i, (lbl, val) in enumerate([("Active", "active"), ("Reactive", "reactive")]):
                rect = pygame.Rect(fx + i * (chip_w + chip_gap), types_y, chip_w, chip_h)
                _draw_chip(lbl, rect, val in active_types)
                filter_chips.append((rect, "types", val))
            clear_all_btn = pygame.Rect(fx + 3 * (chip_w + chip_gap), types_y, chip_w, chip_h)

        if clear_all_btn:
            has_active_filters = any(bool(s) for s in active_filters.values() if isinstance(s, set))
            ca_bg = (55, 28, 28) if has_active_filters else (28, 30, 38)
            ca_bd = (160, 80, 60) if has_active_filters else BORDER
            ca_tc = (210, 130, 110) if has_active_filters else TEXT_MUTED
            draw_rect_border(surf, clear_all_btn, ca_bg, ca_bd, width=1)
            draw_text(surf, "Clear All", 11, ca_tc, clear_all_btn.centerx, clear_all_btn.centery, center=True)

    if active_tab == "adventurers":
        if active_filters.get("classes"):
            list_items = [x for x in list_items if x.cls in active_filters["classes"]]
        if active_filters.get("damage_types"):
            list_items = [x for x in list_items if _adv_damage_type(x) in active_filters["damage_types"]]
    elif active_tab == "artifacts":
        if active_filters.get("types"):
            list_items = [x for x in list_items if ("reactive" if x.reactive else "active") in active_filters["types"]]

    actual_list_y = LIST_Y + FILTER_H
    actual_list_h = LIST_H - FILTER_H
    list_view = pygame.Rect(LIST_X, actual_list_y, LIST_W, actual_list_h)
    draw_rect_border(surf, list_view, PANEL, BORDER)

    item_h = 52
    content_h = len(list_items) * (item_h + 4)
    scroll_max = max(0, content_h - actual_list_h + 8)
    scroll = max(0, min(scroll, scroll_max))

    prev_clip = surf.get_clip()
    surf.set_clip(list_view)
    list_btns = []
    y = actual_list_y + 6 - scroll
    for i, item in enumerate(list_items):
        rect = pygame.Rect(LIST_X + 6, y, LIST_W - 12, item_h)
        if rect.bottom >= actual_list_y and rect.top <= actual_list_y + actual_list_h:
            is_sel = (selected_idx == i)
            if active_tab == "adventurers":
                item_cls = item.cls
            elif active_tab == "classes":
                item_cls = item
            else:
                item_cls = None
            cls_fill = CLASS_COLORS.get(item_cls, PANEL) if item_cls else PANEL
            if is_sel:
                fill = tuple(min(255, c + 24) for c in cls_fill)
            elif rect.collidepoint(mouse_pos):
                fill = tuple(min(255, c + 16) for c in cls_fill)
            else:
                fill = cls_fill
            bord = BORDER_ACTIVE if is_sel else BORDER
            draw_rect_border(surf, rect, fill, bord)

            if active_tab == "adventurers":
                adv_level = adventurer_level_from_clears(adventurer_clears.get(item.id, 0))
                draw_text(surf, item.name, 15, TEXT, rect.x + 8, rect.y + 6)
                class_rect = draw_text(surf, cls_label(item.cls), 13, CLASS_TEXT_COLORS.get(item.cls, TEXT_MUTED), rect.x + 8, rect.y + 24)
                if status_rects_out is not None:
                    status_rects_out.append((class_rect, item.cls))
                draw_text(surf, f"HP {item.hp}  ATK {item.attack}  DEF {item.defense}  SPD {item.speed}", 11, TEXT_DIM, rect.x + 8, rect.y + 38)
                draw_text(surf, f"Lv {adv_level}", 13, CYAN, rect.right - 10, rect.y + 8, right=True)
            elif active_tab == "classes":
                class_level = class_level_from_points(class_points.get(item, 0))
                class_pts = class_points.get(item, 0)
                draw_text(surf, item, 15, TEXT, rect.x + 8, rect.y + 6)
                class_rect = draw_text(surf, cls_label(item), 12, CLASS_TEXT_COLORS.get(item, TEXT_MUTED), rect.x + 8, rect.y + 24)
                if status_rects_out is not None:
                    status_rects_out.append((class_rect, item))
                draw_text(surf, f"Lv {class_level}  •  {class_pts} pts", 12, TEXT_DIM, rect.right - 10, rect.y + 8, right=True)
                next_label = "Sigil + Title at Lv 5" if class_level >= 4 else f"Next unlock at Lv {min(class_level + 1, 5)}"
                draw_text(surf, next_label, 11, TEXT_MUTED, rect.x + 8, rect.y + 38)
            else:
                item_type = "Reactive" if item.reactive else "Active"
                item_col = TYPE_PASSIVE_COL if item.reactive else TYPE_ACTIVE_COL
                name_rect = draw_text(surf, item.name, 15, TEXT, rect.x + 8, rect.y + 4)
                artifact_hover.append((name_rect, item))
                draw_text(surf, item_type, 12, item_col, rect.x + 8, rect.y + 20)
                draw_text(surf, item.description[:44] + ("..." if len(item.description) > 44 else ""), 11, TEXT_MUTED, rect.x + 8, rect.y + 34)
        list_btns.append((rect, i))
        y += item_h + 4
    surf.set_clip(prev_clip)

    if scroll_max > 0:
        bar_x = LIST_X + LIST_W - 8
        bar_ratio = actual_list_h / max(content_h, 1)
        bar_h = max(30, int(actual_list_h * bar_ratio))
        bar_y = actual_list_y + int(scroll / max(scroll_max, 1) * (actual_list_h - bar_h))
        pygame.draw.rect(surf, BORDER, pygame.Rect(bar_x, bar_y, 4, bar_h), border_radius=2)

    if selected_idx is not None and 0 <= selected_idx < len(list_items):
        item = list_items[selected_idx]
        dx = DETAIL_PX + 16
        dy = DETAIL_PY + 14
        dw = DETAIL_PW - 32
        bottom_limit = DETAIL_PY + DETAIL_PH - 10

        def _dline(text, size, color, y_pos, indent=0, rich=False):
            wrap_width = max(80, dw - indent - 8)
            segments = _wrap_text(text, size, wrap_width) or [text]
            for segment in segments:
                if y_pos + size + 2 > bottom_limit:
                    break
                if rich:
                    _draw_rich_line(surf, segment, size, color, dx + indent, y_pos, status_rects_out)
                else:
                    draw_text(surf, segment, size, color, dx + indent, y_pos)
                y_pos += size + 3
            return y_pos

        def _dsep(y_pos):
            if y_pos + 6 > bottom_limit:
                return y_pos
            pygame.draw.line(surf, BORDER, (dx, y_pos + 3), (dx + dw, y_pos + 3), 1)
            return y_pos + 8

        if active_tab == "adventurers":
            adv_level = adventurer_level_from_clears(adventurer_clears.get(item.id, 0))
            clears = adventurer_clears.get(item.id, 0)

            draw_text(surf, item.name, 26, TEXT, dx, dy)
            class_rect = draw_text(surf, cls_label(item.cls), 16, CLASS_TEXT_COLORS.get(item.cls, TEXT_MUTED), DETAIL_PX + DETAIL_PW - 20, dy + 4, right=True)
            if status_rects_out is not None:
                status_rects_out.append((class_rect, item.cls))
            dy += 32
            dy = _dline(f"HP {item.hp}   ATK {item.attack}   DEF {item.defense}   SPD {item.speed}", 15, TEXT, dy)
            dy = _dline(f"Adventurer Level {adv_level}   •   Quest Clears {clears}", 14, CYAN, dy)
            dy = _dline(
                "Sigil + Music Unlocked" if adventurer_sigil_unlocked(adv_level) else "Sigil + Music at Adventurer Level 5",
                13,
                GREEN if adventurer_sigil_unlocked(adv_level) else TEXT_MUTED,
                dy,
            )
            dy += 4
            dy = _dline(f"Talent: {item.talent_name}", 15, YELLOW, dy)
            for line in _wrap_text(item.talent_text, 13, dw - 8):
                dy = _dline(line, 13, TEXT_DIM, dy, indent=8, rich=True)
            dy = _dsep(dy + 2)

            dy = _dline("Signature Abilities:", 15, CYAN, dy)
            dy += 2
            for idx, sig in enumerate(item.sig_options, start=1):
                is_unlocked = adv_level >= idx
                dy = _dline(f"Level {idx} — {sig.name}", 15, TEXT if is_unlocked else TEXT_MUTED, dy, indent=4)
                if is_unlocked:
                    sig_type = "Passive" if sig.passive else "Active"
                    sig_col = TYPE_PASSIVE_COL if sig.passive else TYPE_ACTIVE_COL
                    dy = _dline(sig_type, 12, sig_col, dy, indent=12)
                    if _fl_bl_same(sig):
                        lines = _mode_detail_lines(sig.frontline)
                        dy = _dline(f"FL & BL: {lines[0]}", 13, TEXT_DIM, dy, indent=12, rich=True)
                        for extra in lines[1:3]:
                            dy = _dline(f"      {extra}", 12, TEXT_MUTED, dy, indent=12, rich=True)
                    else:
                        for prefix, mode in (("FL", sig.frontline), ("BL", sig.backline)):
                            lines = _mode_detail_lines(mode)
                            dy = _dline(f"{prefix}: {lines[0]}", 13, TEXT_DIM, dy, indent=12, rich=True)
                            for extra in lines[1:3]:
                                dy = _dline(f"      {extra}", 12, TEXT_MUTED, dy, indent=12, rich=True)
                else:
                    dy = _dline(f"Unlocks at Adventurer Level {idx}", 12, TEXT_MUTED, dy, indent=12)
                dy += 2
            dy = _dsep(dy + 2)

            twist_ready = twist_unlocked(adv_level)
            twist = item.twist
            dy = _dline("Twist Ability:", 15, ORANGE, dy)
            dy = _dline(f"Level 4 — {twist.name}", 15, ORANGE if twist_ready else TEXT_MUTED, dy, indent=4)
            if twist_ready:
                dy = _dline("Active", 12, TYPE_ACTIVE_COL, dy, indent=12)
                if _fl_bl_same(twist):
                    lines = _mode_detail_lines(twist.frontline)
                    dy = _dline(f"FL & BL: {lines[0]}", 13, TEXT_DIM, dy, indent=12, rich=True)
                    for extra in lines[1:3]:
                        dy = _dline(f"      {extra}", 12, TEXT_MUTED, dy, indent=12, rich=True)
                else:
                    for prefix, mode in (("FL", twist.frontline), ("BL", twist.backline)):
                        lines = _mode_detail_lines(mode)
                        dy = _dline(f"{prefix}: {lines[0]}", 13, TEXT_DIM, dy, indent=12, rich=True)
                        for extra in lines[1:3]:
                            dy = _dline(f"      {extra}", 12, TEXT_MUTED, dy, indent=12, rich=True)
            else:
                dy = _dline("Unlocks at Adventurer Level 4", 12, TEXT_MUTED, dy, indent=12)

        elif active_tab == "classes":
            class_name = item
            class_level = class_level_from_points(class_points.get(class_name, 0))
            class_pts = class_points.get(class_name, 0)

            draw_text(surf, class_name, 26, TEXT, dx, dy)
            class_rect = draw_text(surf, cls_label(class_name), 16, CLASS_TEXT_COLORS.get(class_name, TEXT_MUTED), DETAIL_PX + DETAIL_PW - 20, dy + 4, right=True)
            if status_rects_out is not None:
                status_rects_out.append((class_rect, class_name))
            dy += 32
            dy = _dline(f"Class Level {class_level}   •   Class Points {class_pts}", 15, CYAN, dy)
            next_threshold = next((class_thresholds[lvl] for lvl in range(class_level + 1, 6) if lvl in class_thresholds), None)
            if next_threshold is None:
                dy = _dline("Class progression complete", 13, GREEN, dy)
            else:
                dy = _dline(f"Next class level at {next_threshold} points", 13, TEXT_MUTED, dy)
            dy = _dline(
                "Class Sigil + Title Unlocked" if class_sigil_unlocked(class_level) else "Class Sigil + Title at Class Level 5",
                13,
                GREEN if class_sigil_unlocked(class_level) else TEXT_MUTED,
                dy,
            )
            dy = _dsep(dy + 2)

            dy = _dline("Basic Abilities:", 15, CYAN, dy)
            dy += 2
            for idx, ability in enumerate(class_basics.get(class_name, [])):
                unlock_level = _class_basic_unlock_level(idx)
                is_unlocked = class_level >= unlock_level
                dy = _dline(f"Level {unlock_level} — {ability.name}", 15, TEXT if is_unlocked else TEXT_MUTED, dy, indent=4)
                if is_unlocked:
                    ability_type = "Passive" if ability.passive else "Active"
                    ability_col = TYPE_PASSIVE_COL if ability.passive else TYPE_ACTIVE_COL
                    dy = _dline(ability_type, 12, ability_col, dy, indent=12)
                    if _fl_bl_same(ability):
                        lines = _mode_detail_lines(ability.frontline)
                        dy = _dline(f"FL & BL: {lines[0]}", 13, TEXT_DIM, dy, indent=12, rich=True)
                        for extra in lines[1:3]:
                            dy = _dline(f"      {extra}", 12, TEXT_MUTED, dy, indent=12, rich=True)
                    else:
                        for prefix, mode in (("FL", ability.frontline), ("BL", ability.backline)):
                            lines = _mode_detail_lines(mode)
                            dy = _dline(f"{prefix}: {lines[0]}", 13, TEXT_DIM, dy, indent=12, rich=True)
                            for extra in lines[1:3]:
                                dy = _dline(f"      {extra}", 12, TEXT_MUTED, dy, indent=12, rich=True)
                else:
                    dy = _dline(f"Unlocks at Class Level {unlock_level}", 12, TEXT_MUTED, dy, indent=12)
                dy += 2

        else:
            name_rect = draw_text(surf, item.name, 26, TEXT, dx, dy)
            artifact_hover.append((name_rect, item))
            dy += 34
            item_type = "Reactive" if item.reactive else "Active"
            item_col = TYPE_PASSIVE_COL if item.reactive else TYPE_ACTIVE_COL
            dy = _dline(item_type, 14, item_col, dy)
            for line in _wrap_text(item.description, 14, dw):
                dy = _dline(line, 14, TEXT_DIM, dy, rich=True)
    else:
        hint = {
            "adventurers": "Click an adventurer to view progression details.",
            "classes": "Click a class to view level progress and basic abilities.",
            "artifacts": "Click an artifact to view details.",
        }.get(active_tab, "")
        draw_text(surf, hint, 18, TEXT_MUTED, DETAIL_PX + DETAIL_PW // 2, DETAIL_PY + DETAIL_PH // 2, center=True)

    return {
        "back_btn": back_btn,
        "tab_btns": tab_btns,
        "list_btns": list_btns,
        "scroll_max": scroll_max,
        "scroll_viewport": list_view,
        "filter_chips": filter_chips,
        "clear_all_btn": clear_all_btn,
        "artifact_hover": artifact_hover,
    }

def draw_pre_battle_review(surf, picks: list, selected_slot, mouse_pos, status_rects_out: list = None) -> dict:
    """Screen shown after team pick, before battle â€” lets player swap slot positions.

    picks: list of 3 dicts (definition, signature, basics, team_artifacts)
    Returns {"slot_btns": [(rect, idx)], "start_btn": rect, "back_btn": rect}
    """
    surf.fill(BG)
    artifact_hover = []
    draw_text(surf, "Formation Review", 38, TEXT, WIDTH // 2, 50, center=True)
    draw_text(surf, "Click two slots to swap their positions, then start the battle.",
              17, TEXT_DIM, WIDTH // 2, 96, center=True)
    artifacts = list(picks[0].get("team_artifacts", [])) if picks else []
    if artifacts:
        draw_artifact_name_list(
            surf,
            "Artifacts: ",
            artifacts,
            size=15,
            prefix_color=TEXT_DIM,
            artifact_color=ORANGE,
            x=WIDTH // 2,
            y=120,
            artifact_rects_out=artifact_hover,
            max_width=900,
            center=True,
        )

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
        else:
            draw_text(surf, "(empty)", 18, TEXT_MUTED, x + 12, dy)

        slot_btns.append((rect, i))

    back_btn  = pygame.Rect(WIDTH // 2 - 400, HEIGHT - 70, 200, 46)
    edit_btn  = pygame.Rect(WIDTH // 2 - 100, HEIGHT - 70, 200, 46)
    start_btn = pygame.Rect(WIDTH // 2 + 200, HEIGHT - 70, 200, 46)
    draw_button(surf, back_btn,  "â† Back", mouse_pos, size=16,
                normal=PANEL, hover=PANEL_HIGHLIGHT)
    draw_button(surf, edit_btn,  "Edit Party Loadout", mouse_pos, size=16,
                normal=(50, 70, 50), hover=(65, 95, 65))
    draw_button(surf, start_btn, "Start Battle â†’", mouse_pos, size=18,
                normal=BLUE_DARK, hover=BLUE)
    return {
        "slot_btns": slot_btns,
        "start_btn": start_btn,
        "back_btn": back_btn,
        "edit_btn": edit_btn,
        "artifact_hover": artifact_hover,
    }


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

