"""
ui.py – all drawing functions for the Fabled prototype.
Pure rendering; no game-state mutations.
"""
import pygame
from settings import *
from models import CombatantState, TeamState, BattleState


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

def draw_unit_box(surf, rect, unit: CombatantState, selected=False,
                  is_target=False, has_queued=False,
                  is_enemy=False, mouse_pos=None, show_slot=True):
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

    # Name
    name_color = RED if unit.ko else (TEXT_DIM if unit.untargetable else TEXT)
    draw_text(surf, unit.name, 18, name_color, x, y)
    y += 22

    # Class
    draw_text(surf, unit.cls, 14, TEXT_MUTED, x, y)
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

    # Stats
    draw_text(surf, f"ATK {unit.get_stat('attack')}  DEF {unit.get_stat('defense')}  "
              f"SPD {unit.get_stat('speed')}", 13, TEXT_DIM, x, y)
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
        parts = []
        for s in unit.statuses:
            col = STATUS_COLORS.get(s.kind, TEXT_MUTED)
            parts.append((f"{s.kind}({s.duration})", col))
        sx = x
        for txt, col in parts:
            r = draw_text(surf, txt, 12, col, sx, y)
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
# Formation display:
#   Player 2 (top)    BL     Front     BR
#   Player 1 (bottom) BL     Front     BR
#
# Panel regions:
#   Left 560px: both teams
#   Right 840px: log + action panel

UNIT_W = 170
UNIT_H = 130

# Player 2 row: y=80
P2_FRONT_RECT = pygame.Rect(200, 80,  UNIT_W, UNIT_H)
P2_BL_RECT    = pygame.Rect(20,  80,  UNIT_W, UNIT_H)
P2_BR_RECT    = pygame.Rect(385, 80,  UNIT_W, UNIT_H)

# Player 1 row: y=230
P1_FRONT_RECT = pygame.Rect(200, 230, UNIT_W, UNIT_H)
P1_BL_RECT    = pygame.Rect(20,  230, UNIT_W, UNIT_H)
P1_BR_RECT    = pygame.Rect(385, 230, UNIT_W, UNIT_H)

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


def draw_formation(surf, battle: BattleState,
                   selected_unit=None, valid_targets=None,
                   mouse_pos=(0, 0),
                   acting_player=None):
    """Draw both teams in formation."""
    valid_targets = valid_targets or []

    # Labels
    draw_text(surf, f"← {battle.team2.player_name}", 18, BLUE,
              20, 60)
    draw_text(surf, f"← {battle.team1.player_name}", 18, GREEN,
              20, 210)

    for slot, rect in SLOT_RECTS_P2.items():
        unit = battle.team2.get_slot(slot)
        is_tgt = unit in valid_targets if valid_targets else False
        is_sel = (unit == selected_unit and acting_player == 2)
        has_q  = (unit is not None and not unit.ko and unit.queued is not None)
        draw_unit_box(surf, rect, unit, selected=is_sel, is_target=is_tgt,
                      has_queued=has_q, is_enemy=True, mouse_pos=mouse_pos)

    for slot, rect in SLOT_RECTS_P1.items():
        unit = battle.team1.get_slot(slot)
        actual_unit = next((m for m in battle.team1.members if m.slot == slot), None)
        is_tgt = unit in valid_targets if valid_targets else False
        is_acting = (acting_player == 1 and unit == selected_unit)
        has_q  = (actual_unit is not None and not actual_unit.ko
                  and actual_unit.queued is not None)
        draw_unit_box(surf, rect, actual_unit, selected=is_acting, is_target=is_tgt,
                      has_queued=has_q, is_enemy=False, mouse_pos=mouse_pos)


def formation_rect_for(unit: CombatantState, acting_player: int):
    """Return the pygame.Rect for a given unit's position on screen."""
    rects = SLOT_RECTS_P1 if acting_player == 1 else SLOT_RECTS_P2
    return rects.get(unit.slot)


# ─────────────────────────────────────────────────────────────────────────────
# BATTLE LOG
# ─────────────────────────────────────────────────────────────────────────────

LOG_RECT = pygame.Rect(580, 80, 400, 420)


def _log_color(line: str) -> tuple:
    """Return a colour for a log entry based on its content."""
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
    max_chars = 56
    view_lines = (rect.height - 36) // line_h
    total = len(log)
    # scroll_offset 0 = bottom of log; positive = scrolled up
    max_scroll = max(0, total - view_lines)
    scroll_offset = max(0, min(scroll_offset, max_scroll))
    start = total - view_lines - scroll_offset
    start = max(0, start)
    visible = log[start: start + view_lines]
    y = rect.y + 28
    for line in visible:
        if y + line_h > rect.bottom - 4:
            break
        col = _log_color(line)
        draw_text(surf, line[:max_chars], 13, col, rect.x + 8, y)
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

    # Item
    item = actor.item
    if not item.passive and actor.item_uses_left > 0:
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

    # Swap (once per turn)
    y += 6
    rect = pygame.Rect(BUTTON_X, y, BUTTON_W, BUTTON_H)
    draw_button(surf, rect, "Swap with ally", mouse_pos, size=15,
                disabled=swap_used or actor.has_status("root"))
    if not swap_used and not actor.has_status("root"):
        buttons.append((rect, {"type": "swap", "target": None}))
    y += BUTTON_H + 4

    # Skip
    rect = pygame.Rect(BUTTON_X, y, BUTTON_W, BUTTON_H)
    draw_button(surf, rect, "Skip", mouse_pos, size=15, normal=(40, 40, 45))
    buttons.append((rect, {"type": "skip"}))

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


def draw_queued_summary(surf, team: TeamState, y_start: int, acting_player: int):
    """Show the queued actions for a player's team in a small bordered panel."""
    x = 580
    # Count rows needed
    rows = sum(1 + (u.queued2 is not None) for u in team.members if not u.ko)
    panel_h = 22 + rows * 17 + 6
    panel_rect = pygame.Rect(x, y_start, 400, panel_h)
    draw_rect_border(surf, panel_rect, (30, 35, 30), (60, 100, 60))

    y = y_start + 5
    draw_text(surf, f"P{acting_player} — Queued Actions", 14, (130, 200, 130), x + 8, y)
    y += 19
    for unit in team.members:
        if unit.ko:
            continue
        suffix, col = _queue_label(unit.queued)
        # Name in normal text, action in its colour
        draw_text(surf, f"  {unit.name[:14]}:", 13, TEXT_DIM, x + 8, y)
        draw_text(surf, suffix, 13, col, x + 130, y)
        y += 17
        if unit.queued2 is not None:
            suffix2, col2 = _queue_label(unit.queued2)
            draw_text(surf, f"    +extra:", 12, YELLOW, x + 8, y)
            draw_text(surf, suffix2, 12, col2, x + 130, y)
            y += 16


# ─────────────────────────────────────────────────────────────────────────────
# PASS SCREEN
# ─────────────────────────────────────────────────────────────────────────────

def draw_pass_screen(surf, player_name: str, message: str,
                     mouse_pos) -> pygame.Rect:
    """Full-screen pass screen. Returns the Continue button rect."""
    surf.fill(BG)
    cx, cy = WIDTH // 2, HEIGHT // 2
    draw_text(surf, "FABLED", 60, TEXT, cx, cy - 160, center=True)
    draw_text(surf, message, 28, YELLOW, cx, cy - 60, center=True)
    draw_text(surf, f"Pass the device to  {player_name}", 22, TEXT_DIM,
              cx, cy - 10, center=True)

    btn = pygame.Rect(cx - 140, cy + 60, 280, 55)
    draw_button(surf, btn, "Continue →", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE, border=BORDER_ACTIVE)
    return btn


# ─────────────────────────────────────────────────────────────────────────────
# MAIN MENU
# ─────────────────────────────────────────────────────────────────────────────

def draw_main_menu(surf, mouse_pos, player_level=0):
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "FABLED", 80, TEXT, cx, 140, center=True)
    draw_text(surf, f"Level {player_level}", 22, TEXT_DIM, cx, 235, center=True)

    story_btn       = pygame.Rect(cx - 130, 320, 260, 58)
    practice_btn    = pygame.Rect(cx - 130, 394, 260, 58)
    teambuilder_btn = pygame.Rect(cx - 130, 468, 260, 58)
    exit_btn        = pygame.Rect(cx - 130, 542, 260, 58)

    draw_button(surf, story_btn, "Story", mouse_pos, size=22,
                normal=(40, 90, 50), hover=(55, 120, 65), border=BORDER_ACTIVE)
    draw_button(surf, practice_btn, "Practice", mouse_pos, size=22,
                normal=BLUE_DARK, hover=BLUE)
    draw_button(surf, teambuilder_btn, "Teambuilder", mouse_pos, size=22,
                normal=(75, 45, 120), hover=(105, 65, 165), border=BORDER_ACTIVE)
    draw_button(surf, exit_btn, "Exit", mouse_pos, size=22,
                normal=PANEL, hover=PANEL_HIGHLIGHT)

    return story_btn, practice_btn, teambuilder_btn, exit_btn


def draw_practice_menu(surf, mouse_pos) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Practice", 48, TEXT, cx, 80, center=True)
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
    draw_text(surf, "Team Builder", 48, TEXT, cx, 40, center=True)
    draw_text(surf, "Build up to 6 teams using your unlocked adventurers.",
              18, TEXT_DIM, cx, 95, center=True)

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    slot_w = 620
    slot_h = 130
    pad = 16
    start_x = cx - slot_w - pad // 2
    start_y = 130

    slot_btns = []
    delete_btns = []

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
                draw_text(surf, team.get("name", f"Team {idx+1}"), 18, TEXT,
                          rect.x + 10, rect.y + 8)
                # Show member names
                members = team.get("members", [])
                names = "  |  ".join(
                    m.get("adv_id", "?").replace("_", " ").title()
                    for m in members
                )
                draw_text(surf, names, 14, TEXT_DIM, rect.x + 10, rect.y + 34)

                edit_btn_rect = pygame.Rect(rect.right - 90, rect.y + 10, 80, 32)
                del_btn_rect  = pygame.Rect(rect.right - 90, rect.y + 50, 80, 28)
                draw_button(surf, edit_btn_rect, "Edit",   mouse_pos, size=14,
                            normal=BLUE_DARK, hover=BLUE)
                draw_button(surf, del_btn_rect,  "Delete", mouse_pos, size=14,
                            normal=(80, 30, 30), hover=(110, 45, 45))
                slot_btns.append((edit_btn_rect, idx))
                delete_btns.append((del_btn_rect, idx))
            else:
                draw_rect_border(surf, rect, PANEL, BORDER)
                draw_text(surf, f"Slot {idx+1}  (empty)", 16, TEXT_MUTED,
                          rect.centerx, rect.centery, center=True)
                build_btn = pygame.Rect(rect.right - 110, rect.centery - 16, 100, 32)
                draw_button(surf, build_btn, "Build Team", mouse_pos, size=14,
                            normal=(40, 90, 50), hover=(55, 120, 65))
                slot_btns.append((build_btn, idx))

    return {"slot_btns": slot_btns, "delete_btns": delete_btns, "back_btn": back_btn}


def draw_story_team_select(surf, saved_teams: list, mouse_pos, quest_def) -> dict:
    surf.fill(BG)
    cx = WIDTH // 2
    draw_text(surf, "Select Your Team", 40, TEXT, cx, 50, center=True)
    if quest_def:
        draw_text(surf, quest_def.key_preview, 18, TEXT_DIM, cx, 100, center=True)

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    team_btns = []
    teambuilder_btn = None

    valid_teams = [(i, t) for i, t in enumerate(saved_teams) if t is not None]

    if not valid_teams:
        draw_text(surf, "No teams saved. Build a team in the Teambuilder first.",
                  20, RED, cx, 250, center=True)
        teambuilder_btn = pygame.Rect(cx - 140, 310, 280, 55)
        draw_button(surf, teambuilder_btn, "Go to Teambuilder", mouse_pos, size=20,
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
            draw_text(surf, team.get("name", f"Team {slot_idx+1}"), 18, TEXT,
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


def draw_adventurer_card(surf, rect, defn, selected, in_team, mouse_pos):
    if defn is None:
        return
    fill = (50, 65, 50) if in_team else (PANEL_ALT if not selected else PANEL_HIGHLIGHT)
    bord = GREEN if in_team else (BORDER_ACTIVE if selected else BORDER)
    draw_rect_border(surf, rect, fill, bord)
    draw_text(surf, defn.name, 15, TEXT, rect.x + 6, rect.y + 6)
    draw_text(surf, defn.cls,  13, TEXT_MUTED, rect.x + 6, rect.y + 24)
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
                              sig_tier: int = 3) -> dict:
    """
    Draw the team selection screen.
    Returns a dict of {region_name: [list of (rect, value)]} for click handling.
    sub_phase: "pick_adventurers" | "pick_sig" | "pick_basics" | "pick_item"
    """
    surf.fill(BG)
    draw_text(surf, f"{player_name} — Build Your Party", 28, TEXT, WIDTH // 2,
              30, center=True)

    clicks = {
        "roster": [],
        "sig": [],
        "basics": [],
        "items": [],
        "party_slots": [],
        "confirm": None,
        "back": None,
        "scroll_max": 0,
        "scroll_viewport": None,
    }

    # Dynamic roster layout so larger pools (e.g. 24 adventurers) fit.
    roster_cols = 4 if len(roster) >= 24 else ROSTER_COLS
    card_w = 160 if roster_cols == 4 else CARD_W
    card_h = 92 if roster_cols == 4 else CARD_H

    # ── Roster grid (left) ────────────────────────────────────────────────────
    roster_panel_h = HEIGHT - ROSTER_Y - 20
    roster_view = pygame.Rect(ROSTER_X, ROSTER_Y, DETAIL_X - ROSTER_X - 20, roster_panel_h)
    _n_roster_rows = (len(roster) + roster_cols - 1) // roster_cols
    roster_content_h = _n_roster_rows * (card_h + CARD_PAD)
    slots_h = 22 + 50
    roster_content_h += slots_h + 36
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
        sel = selected_idx == i
        if rect.bottom >= roster_view.top and rect.top <= roster_view.bottom:
            draw_adventurer_card(surf, rect, defn, sel, in_team, mouse_pos)
        clicks["roster"].append((rect, i))

    # Party slots
    _slots_y = ROSTER_Y + _n_roster_rows * (card_h + CARD_PAD) - roster_scroll
    if sub_phase == "pick_adventurers" and len(team_picks) >= 2:
        draw_text(surf, "Your Party:  (click slots to reorder)", 18, TEXT_DIM, ROSTER_X, _slots_y)
    else:
        draw_text(surf, "Your Party:", 18, TEXT_DIM, ROSTER_X, _slots_y)
    slot_labels = ["Front", "Back Left", "Back Right"]
    for i in range(3):
        x = ROSTER_X + i * 220
        y = _slots_y + 22
        rect = pygame.Rect(x, y, 210, 50)
        is_selected = (sub_phase == "pick_adventurers" and team_slot_selected == i)
        if i < len(team_picks):
            p = team_picks[i]
            slot_defn = p.get("definition")
            fill = PANEL_HIGHLIGHT if is_selected else PANEL_ALT
            border = BORDER_ACTIVE if is_selected else BORDER
            draw_rect_border(surf, rect, fill, border)
            draw_text(surf, slot_labels[i], 13, CYAN if is_selected else TEXT_MUTED, x + 6, y + 4)
            if slot_defn:
                draw_text(surf, slot_defn.name[:22], 15, TEXT, x + 6, y + 20)
            else:
                draw_text(surf, "(empty)", 15, TEXT_MUTED, x + 6, y + 20)
            if sub_phase == "pick_adventurers":
                clicks["party_slots"].append((rect, i))
        else:
            draw_rect_border(surf, rect, PANEL_ALT, BORDER)
            draw_text(surf, slot_labels[i], 13, TEXT_MUTED, x + 6, y + 4)
            draw_text(surf, "(empty)", 15, TEXT_MUTED, x + 6, y + 20)
    surf.set_clip(prev_clip)

    # ── Detail panel (right) ──────────────────────────────────────────────────
    detail_rect = pygame.Rect(DETAIL_X, DETAIL_Y, DETAIL_W, DETAIL_H)
    draw_panel(surf, detail_rect)

    if sub_phase != "pick_adventurers" and team_picks and current_adv_idx < len(team_picks):
        defn = team_picks[current_adv_idx].get("definition")
    elif selected_idx is not None and 0 <= selected_idx < len(roster):
        defn = roster[selected_idx]
    else:
        defn = None
    if defn is not None:
        dx, dy = DETAIL_X + 14, DETAIL_Y + 12

        draw_text(surf, defn.name, 24, TEXT, dx, dy)
        dy += 30
        draw_text(surf, f"{defn.cls}  —  {defn.talent_name}",
                  16, YELLOW, dx, dy)
        dy += 20
        for line in _wrap_text(defn.talent_text, 13, DETAIL_W - 28):
            draw_text(surf, line, 13, TEXT_DIM, dx, dy)
            dy += 16
        dy += 4
        draw_text(surf,
                  f"HP {defn.hp}   ATK {defn.attack}   DEF {defn.defense}   SPD {defn.speed}",
                  15, TEXT, dx, dy)
        dy += 26

        if sub_phase == "pick_sig":
            draw_text(surf, "Choose Signature Ability:", 18, CYAN, dx, dy)
            dy += 24
            for i, sig in enumerate(defn.sig_options[:sig_tier]):
                # Measure how tall this entry needs to be
                fl_lines = _mode_detail_lines(sig.frontline)
                bl_lines = _mode_detail_lines(sig.backline)
                # Fixed generous height so wrapped FL/BL lines fit without clipping.
                entry_h = 152
                r = pygame.Rect(dx, dy, DETAIL_W - 28, entry_h)
                sel_s = sig_choice == i
                draw_rect_border(surf, r,
                                 PANEL_HIGHLIGHT if sel_s else PANEL_ALT,
                                 BORDER_ACTIVE if sel_s else BORDER)
                iy = dy + 5
                draw_text(surf, sig.name, 16, TEXT, dx + 8, iy)
                iy += 20
                draw_text(surf, "Frontline:", 13, CYAN, dx + 8, iy)
                iy += 14
                for line in fl_lines[:2]:
                    for wline in _wrap_text(line, 13, DETAIL_W - 52)[:2]:
                        draw_text(surf, f"  {wline}", 13, TEXT_DIM, dx + 8, iy)
                        iy += 14
                draw_text(surf, "Backline:", 13, CYAN, dx + 8, iy)
                iy += 14
                for line in bl_lines[:2]:
                    for wline in _wrap_text(line, 13, DETAIL_W - 52)[:2]:
                        draw_text(surf, f"  {wline}", 13, TEXT_MUTED, dx + 8, iy)
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
            content_h = len(pool) * 145
            max_scroll = max(0, content_h - view_rect.height)
            scroll = max(0, min(scroll_offset, max_scroll))
            clicks["scroll_max"] = max_scroll
            clicks["scroll_viewport"] = view_rect
            prev_clip = surf.get_clip()
            surf.set_clip(view_rect)
            for i, ab in enumerate(pool):
                fl_lines = _mode_detail_lines(ab.frontline)
                bl_lines = _mode_detail_lines(ab.backline)
                # Fixed generous height so wrapped FL/BL lines fit without clipping.
                entry_h = 140
                y_draw = dy - scroll
                r = pygame.Rect(dx, y_draw, DETAIL_W - 28, entry_h)
                sel_b = i in basic_choices
                if r.bottom >= view_rect.top and r.top <= view_rect.bottom:
                    draw_rect_border(surf, r,
                                     PANEL_HIGHLIGHT if sel_b else PANEL_ALT,
                                     BORDER_ACTIVE if sel_b else BORDER)
                    iy = y_draw + 5
                    tag = "  [passive]" if ab.passive else ""
                    draw_text(surf, ab.name + tag, 15, TEXT, dx + 8, iy)
                    iy += 18
                    draw_text(surf, "FL:", 13, CYAN, dx + 8, iy)
                    iy += 13
                    for line in fl_lines[:2]:
                        for wline in _wrap_text(line, 13, DETAIL_W - 56)[:2]:
                            draw_text(surf, f"  {wline}", 13, TEXT_DIM, dx + 8, iy)
                            iy += 13
                    draw_text(surf, "BL:", 13, CYAN, dx + 8, iy)
                    iy += 13
                    for line in bl_lines[:2]:
                        for wline in _wrap_text(line, 13, DETAIL_W - 56)[:2]:
                            draw_text(surf, f"  {wline}", 13, TEXT_MUTED, dx + 8, iy)
                            iy += 13
                clicks["basics"].append((r.copy(), i))
                dy += entry_h + 5
            surf.set_clip(prev_clip)

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
                item_heights.append(24 + len(preview) * 14 + 4)
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
                entry_h = 24 + len(preview) * 14 + 2
                y_draw = dy - scroll
                r = pygame.Rect(dx, y_draw, DETAIL_W - 28, entry_h)
                if r.bottom >= view_rect.top and r.top <= view_rect.bottom:
                    if is_taken:
                        draw_rect_border(surf, r, (35, 35, 40), BORDER)
                        display_name = f"{item.name}  {tag}  [taken]"
                        draw_text(surf, display_name, 14, TEXT_MUTED, dx + 8, y_draw + 4)
                        iy = y_draw + 20
                        for line in preview:
                            draw_text(surf, line, 13, TEXT_MUTED, dx + 14, iy)
                            iy += 14
                    else:
                        draw_rect_border(surf, r,
                                         PANEL_HIGHLIGHT if sel_i else PANEL_ALT,
                                         BORDER_ACTIVE if sel_i else BORDER)
                        draw_text(surf, f"{item.name}  {tag}", 14,
                                  TEXT if sel_i else TEXT_DIM, dx + 8, y_draw + 4)
                        iy = y_draw + 20
                        for line in preview:
                            draw_text(surf, line, 13, TEXT_DIM if sel_i else TEXT_MUTED, dx + 14, iy)
                            iy += 14
                clicks["items"].append((r.copy(), i))
                dy += entry_h + 2
            surf.set_clip(prev_clip)

    if clicks["scroll_max"] > 0 and clicks["scroll_viewport"] is not None:
        draw_text(surf, "Scroll list with mouse wheel", 13, TEXT_MUTED,
                  DETAIL_X + 14, DETAIL_Y + DETAIL_H - 102)

    # ── Confirm / instructions ────────────────────────────────────────────────
    inst = {
        "pick_adventurers": "Click adventurers to add them (first = Front). Need 3.",
        "pick_sig": "Select a Signature Ability, then confirm.",
        "pick_basics": "Select 2 Basic Abilities, then confirm.",
        "pick_item": "Select an Item, then confirm.",
    }
    draw_text(surf, inst.get(sub_phase, ""), 15, TEXT_DIM,
              DETAIL_X + 14, DETAIL_Y + DETAIL_H - 80)

    confirm_text = {
        "pick_adventurers": "Continue →" if len(team_picks) == 3 else f"Need {3 - len(team_picks)} more",
        "pick_sig": "Confirm Signature" if sig_choice is not None else "Pick a Signature",
        "pick_basics": "Confirm Basics" if len(basic_choices) == 2 else f"Need {2 - len(basic_choices)} more",
        "pick_item": "Confirm Item" if item_choice is not None else "Pick an Item",
    }.get(sub_phase, "Confirm")

    can_confirm = {
        "pick_adventurers": len(team_picks) == 3,
        "pick_sig": sig_choice is not None,
        "pick_basics": len(basic_choices) == 2,
        "pick_item": item_choice is not None,
    }.get(sub_phase, False)

    confirm_rect = pygame.Rect(DETAIL_X + DETAIL_W - 230, DETAIL_Y + DETAIL_H - 55,
                               220, 44)
    draw_button(surf, confirm_rect, confirm_text, mouse_pos,
                normal=BLUE_DARK, hover=BLUE, disabled=not can_confirm, size=18)
    if can_confirm:
        clicks["confirm"] = confirm_rect

    # Back button for sub-phases after pick_adventurers
    if sub_phase != "pick_adventurers":
        back_rect = pygame.Rect(DETAIL_X, DETAIL_Y + DETAIL_H - 55, 160, 44)
        draw_button(surf, back_rect, "← Back", mouse_pos, size=16)
        clicks["back"] = back_rect

    return clicks


# ─────────────────────────────────────────────────────────────────────────────
# SPECIAL ABILITY DESCRIPTIONS  (human-readable text for each special key)
# ─────────────────────────────────────────────────────────────────────────────
SPECIAL_DESCRIPTIONS: dict = {
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
    "devils_due":                      "one ally ability becomes spread, ignoring melee restriction and spread penalty",
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
    "sanctuary_back":                  "frontline ally heals 1/8 max HP each round",
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
    "blood_pact_front":              "lose 20 HP and gain 2 Malice",
    "blood_pact_back":               "heal 20 HP; spend 1 Malice to heal 20 more HP",
    "cursed_armor":                  "gain 1 Malice whenever damaged by an enemy ability",
    "void_step_front":               "on swapping to backline, gain 1 Malice",
    "void_step_back":                "on swapping to frontline, spend 2 Malice for +10 Spd (2r)",
    # Pinocchio (Warlock)
    "wooden_wallop_front":           "+10 power per Malice",
    "cut_strings_back":              "spend 2 Malice to Spotlight target for 2 rounds",
    "become_real_front":             "at 3+ Malice: abilities gain +15 damage; immune to statuses",
    "become_real_back":              "at 3+ Malice: abilities do not increment ranged recharge",
    "blue_faerie_boon":              "increase Malice cap by 6, gain 6 Malice, then heal 20 per Malice",
    # Rumpelstiltskin (Warlock)
    "straw_to_gold_front":           "steal ally's highest stat buff for 2r; +5 strength per Malice; return later",
    "straw_to_gold_back":            "convert an ally's highest stat debuff into a stat buff",
    "name_the_price_front":          "target gains +10 Atk for 2 rounds",
    "name_the_price_back":           "spend 2 Malice to nullify target's stat buffs for 2 rounds",
    "spinning_wheel_front":          "+5 ability damage per unique ally stat buff",
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
    if mode.bonus_vs_statused:    bonuses.append(f"+{mode.bonus_vs_statused} vs Exposed/Weakened")
    if bonuses:
        parts.append("  ".join(bonuses))
    if mode.vamp:
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
                           rect: pygame.Rect = None) -> pygame.Rect:
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
    draw_text(surf, unit.cls, 14, TEXT_MUTED, r.right - 30, y + 4, right=True)
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
        draw_text(surf, line, 13, TEXT_DIM, x + 8, y)
        y += 15
    y += 4

    # ── Signature ────────────────────────────────────────────────────────────
    pygame.draw.line(surf, BORDER, (x, y), (x + w, y), 1)
    y += 5
    draw_text(surf, "Signature  —  " + unit.sig.name, 14, CYAN, x, y)
    y += 17
    for prefix, mode in (("FL", unit.sig.frontline), ("BL", unit.sig.backline)):
        lines = _mode_detail_lines(mode)
        label = f"{prefix}: {lines[0]}"
        draw_text(surf, label, 12, TEXT_DIM, x + 8, y)
        y += 14
        for extra in lines[1:2]:          # at most one continuation line
            draw_text(surf, f"     {extra}", 12, TEXT_MUTED, x + 8, y)
            y += 13
    y += 4

    # ── Basics ───────────────────────────────────────────────────────────────
    pygame.draw.line(surf, BORDER, (x, y), (x + w, y), 1)
    y += 5
    draw_text(surf, "Basic Abilities", 14, CYAN, x, y)
    y += 17
    for ab in unit.basics:
        tag = " [passive]" if ab.passive else ""
        draw_text(surf, ab.name + tag, 14, TEXT, x, y)
        y += 15
        for prefix, mode in (("FL", ab.frontline), ("BL", ab.backline)):
            lines = _mode_detail_lines(mode)
            draw_text(surf, f"{prefix}: {lines[0]}", 12, TEXT_DIM, x + 8, y)
            y += 13
        y += 2

    # ── Item ─────────────────────────────────────────────────────────────────
    pygame.draw.line(surf, BORDER, (x, y), (x + w, y), 1)
    y += 5
    item = unit.item
    if item.passive:
        tag = "[passive]"
    elif item.once_per_battle:
        tag = "[used]" if unit.item_uses_left <= 0 else "[once per battle]"
    else:
        tag = "[active]"
    draw_text(surf, f"Item: {item.name}  {tag}", 14, GREEN, x, y)
    y += 16
    for line in _wrap_text(item.description, 13, w - 8):
        if y + 14 > r.bottom - 4:
            break
        draw_text(surf, line, 13, TEXT_DIM, x + 8, y)
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

    draw_text(surf, f"FABLED", 22, TEXT, 14, 14)
    draw_text(surf, f"Round {battle.round_num}", 20, YELLOW, 150, 17)
    draw_text(surf, f"Initiative: Player {battle.init_player}", 18, CYAN,
              290, 17)
    draw_text(surf, phase_label, 17, TEXT_DIM, 520, 17)
    draw_text(surf, f"{battle.team1.player_name}  vs  {battle.team2.player_name}",
              18, TEXT, WIDTH // 2, 17, center=True)


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

    draw_text(surf, "FABLED — Story Mode", 48, TEXT, cx, 50, center=True)
    draw_text(surf, "Select a Mission", 24, TEXT_DIM, cx, 100, center=True)

    # Back button
    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    # Layout: 2 columns x 5 rows
    col_w  = 580
    col_h  = 110
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
            draw_text(surf, f"Quests {first_q}–{last_q}  |  Level {mission.level_range[0]}–{mission.level_range[1]}",
                      14, TEXT_DIM, rect.x + 14, rect.y + 36)
            # Truncate description to fit
            desc = mission.description[:70] + ("..." if len(mission.description) > 70 else "")
            draw_text(surf, desc, 13, TEXT_MUTED, rect.x + 14, rect.y + 57)
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
    draw_text(surf, mission.description[:90], 17, TEXT_DIM, cx, 95, center=True)

    back_btn = pygame.Rect(20, 20, 100, 36)
    draw_button(surf, back_btn, "Back", mouse_pos, size=16)

    # List quests vertically
    q_w   = 900
    q_h   = 95
    pad   = 12
    start_x = cx - q_w // 2
    start_y = 130

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
            draw_text(surf, f"Quest {quest.quest_id}  —  {quest.key_preview}",
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
            draw_text(surf, f"Quest {quest.quest_id}  —  LOCKED", 16, TEXT_MUTED,
                      rect.x + 14, rect.y + 28)

    return {"quest_btns": quest_btns, "back_btn": back_btn}


def draw_pre_quest(surf, quest_def, mission, quest_pos: int, total_quests: int,
                   enemy_picks: list, mouse_pos) -> dict:
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
    draw_text(surf, f"Mission {mission_id}  \u2014  {mission_name}",
              30, TEXT, cx, 42, center=True)
    draw_text(surf, f"Quest {quest_pos} / {total_quests}  \u00b7  {quest_def.key_preview}",
              18, TEXT_DIM, cx, 78, center=True)
    # Mission description truncated
    desc = mission.description if mission else ""
    if len(desc) > 110:
        desc = desc[:110] + "..."
    draw_text(surf, desc, 14, TEXT_MUTED, cx, 108, center=True)

    # Enemy lineup (3 cards side by side)
    slot_labels = ["Front", "Back Left", "Back Right"]
    card_w = 320
    card_h = 200
    total_w = card_w * 3 + 30
    card_start_x = cx - total_w // 2
    card_y = 148

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
        draw_text(surf, defn.cls, 14, YELLOW, rect.x + 10, rect.y + 46)
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
        draw_text(surf, f"Quest {quest_def.quest_id} Cleared!", 34, GREEN,
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
