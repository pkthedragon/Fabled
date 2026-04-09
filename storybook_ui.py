from __future__ import annotations

import re
import pygame

from settings import HEIGHT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT, STATUS_COLORS, WIDTH
from storybook_content import (
    BOUT_MODES,
    CATALOG_SECTIONS,
    CLOSET_TABS,
    COSMETIC_CATEGORIES,
    MARKET_TABS,
    SHOP_TABS,
    STORY_QUESTS,
    catalog_entries,
    catalog_filter_definitions,
    market_items_for_tab,
    market_tab_note,
    quest_role_summary,
    quest_warnings,
    recommendation_notes,
    role_tags_for_adventurer,
    shop_items_for_tab,
    shop_tab_note,
)
from quests_ruleset_data import ADVENTURERS_BY_ID, ALL_ARTIFACTS_BY_ID, ARTIFACTS_BY_ID, CLASS_SKILLS, CLASS_SKILLS_BY_ID, ULTIMATE_METER_MAX
from quests_sandbox import CLASS_ORDER, NO_CLASS_NAME, compatible_artifact_ids
from storybook_progression import level_state
from storybook_tutorial import tutorial_unit_callout_lines


SBG = (16, 18, 24)
SBG_DEEP = (10, 12, 18)
SURFACE_LOW = (27, 29, 32)
SURFACE = (34, 36, 40)
SURFACE_HIGH = (46, 48, 52)
SURFACE_GOLD = (214, 175, 55)
GOLD_BRIGHT = (242, 202, 80)
GOLD_DIM = (122, 98, 34)
TEXT = (228, 226, 221)
TEXT_SOFT = (198, 190, 176)
TEXT_MUTE = (135, 132, 126)
SLATE_BLUE = (78, 104, 132)
EMBER = (176, 72, 64)
JADE = (92, 151, 136)
RUBY = (170, 60, 58)
SAPPHIRE = (114, 166, 201)
PARCHMENT = (208, 197, 175)

ROLE_COLORS = {
    "Tank": SAPPHIRE,
    "Carry": GOLD_BRIGHT,
    "Support": JADE,
    "Control": EMBER,
    "Skirmish": SLATE_BLUE,
}

WEAPON_KIND_COLORS = {
    "melee": GOLD_BRIGHT,
    "ranged": SAPPHIRE,
    "magic": JADE,
}

CURRENT_PROFILE = None


def set_profile_context(profile):
    global CURRENT_PROFILE
    CURRENT_PROFILE = profile

SLOT_LABELS = {
    SLOT_FRONT: "Frontline",
    SLOT_BACK_LEFT: "Backline Left",
    SLOT_BACK_RIGHT: "Backline Right",
}

CLASS_SUMMARIES = {
    NO_CLASS_NAME: "No class selected. Use this while reshaping a full party before locking final loadouts.",
    "Warden": "Tanks and position manipulators built to hold the frontline.",
    "Fighter": "Melee damage dealers that convert clean reach into knockouts.",
    "Mage": "Magic damage dealers with spell pressure and cooldown leverage.",
    "Ranger": "Ranged pressure specialists with ammo management and lane control.",
    "Cleric": "Healers and enchanters that stabilize parties and patch mistakes.",
    "Rogue": "Disruptors and speedsters that thrive on timing and repositioning.",
}

SPACE_8 = 8
SPACE_16 = 16
SPACE_24 = 24
SPACE_32 = 32

LOADOUT_BG_TOP = (20, 21, 26)
LOADOUT_BG_BOTTOM = (14, 15, 19)
LOADOUT_PANEL_TOP = (35, 36, 42)
LOADOUT_PANEL_BOTTOM = (24, 25, 30)
LOADOUT_SUBCARD_TOP = (41, 42, 49)
LOADOUT_SUBCARD_BOTTOM = (30, 31, 37)
LOADOUT_BORDER = (80, 67, 38)
LOADOUT_ACCENT = (212, 176, 92)
LOADOUT_IVORY = (220, 211, 193)
LOADOUT_IVORY_MUTED = (175, 166, 151)
LOADOUT_WARNING = (201, 134, 108)

STATUS_EFFECT_RULES = {
    "burn": {
        "name": "Burn",
        "description": "Burned adventurers take 8% of their max HP as damage at the end of each round.",
    },
    "root": {
        "name": "Root",
        "description": "Rooted adventurers cannot use the Swap Positions action.",
    },
    "shock": {
        "name": "Shock",
        "description": "Shocked adventurers have -25 Speed and their Strikes have 15% recoil.",
    },
    "weaken": {
        "name": "Weaken",
        "description": "Weakened adventurers deal 15% less damage.",
    },
    "expose": {
        "name": "Expose",
        "description": "Exposed adventurers take 15% more damage.",
    },
    "guard": {
        "name": "Guard",
        "description": "Guarded adventurers take 15% less damage.",
    },
    "spotlight": {
        "name": "Spotlight",
        "description": "Spotlighted adventurers can be targeted by Melee Strikes in the backline.",
    },
    "taunt": {
        "name": "Taunt",
        "description": "Taunted adventurers can only target whoever taunted them, unless that target is illegal.",
    },
}

STATUS_EFFECT_ALIASES = {
    "burn": ("burn", "burns", "burned"),
    "root": ("root", "roots", "rooted"),
    "shock": ("shock", "shocks", "shocked"),
    "weaken": ("weaken", "weakens", "weakened"),
    "expose": ("expose", "exposes", "exposed"),
    "guard": ("guard", "guards", "guarded"),
    "spotlight": ("spotlight", "spotlights", "spotlighted"),
    "taunt": ("taunt", "taunts", "taunted"),
}

STATUS_TEXT_COLORS = {
    **STATUS_COLORS,
    "taunt": STATUS_COLORS.get("taunt", (185, 105, 185)),
}

STATUS_ALIAS_TO_KEY = {
    alias: key
    for key, aliases in STATUS_EFFECT_ALIASES.items()
    for alias in aliases
}

_HOVERED_STATUS_KEY: str | None = None
_HOVERED_STATUS_POS = (0, 0)

_FONT_CACHE: dict[tuple[str, int, bool], pygame.font.Font] = {}


def _font(candidates: list[str], size: int, *, bold: bool = False):
    key = ("|".join(candidates), size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for name in candidates:
        try:
            _FONT_CACHE[key] = pygame.font.SysFont(name, size, bold=bold)
            return _FONT_CACHE[key]
        except Exception:
            continue
    _FONT_CACHE[key] = pygame.font.Font(None, size)
    return _FONT_CACHE[key]


def font_headline(size: int, *, bold: bool = False):
    return _font(["Palatino Linotype", "Georgia", "Cambria"], size, bold=bold)


def font_body(size: int, *, bold: bool = False):
    return _font(["Segoe UI", "Trebuchet MS", "Tahoma"], size, bold=bold)


def font_label(size: int, *, bold: bool = False):
    return _font(["Bahnschrift", "Arial", "Verdana"], size, bold=bold)


def _lerp_color(a, b, t: float):
    return tuple(int(a[index] + (b[index] - a[index]) * t) for index in range(3))


def draw_text(surf, text, font_obj, color, pos, *, center=False, right=False):
    image = font_obj.render(str(text), True, color)
    rect = image.get_rect()
    if center:
        rect.center = pos
    elif right:
        rect.midright = pos
    else:
        rect.topleft = pos
    surf.blit(image, rect)
    return rect


def _ellipsize_text(text, font_obj, width):
    text = str(text)
    if width <= 0:
        return ""
    if font_obj.size(text)[0] <= width:
        return text
    ellipsis = "..."
    if font_obj.size(ellipsis)[0] > width:
        return ""
    trimmed = text
    while trimmed and font_obj.size(trimmed + ellipsis)[0] > width:
        trimmed = trimmed[:-1]
    return (trimmed.rstrip() + ellipsis) if trimmed else ellipsis


def begin_status_hover_frame():
    global _HOVERED_STATUS_KEY, _HOVERED_STATUS_POS
    _HOVERED_STATUS_KEY = None
    _HOVERED_STATUS_POS = (0, 0)


def _record_status_hover(status_key: str, mouse_pos):
    global _HOVERED_STATUS_KEY, _HOVERED_STATUS_POS
    if _HOVERED_STATUS_KEY is None:
        _HOVERED_STATUS_KEY = status_key
        _HOVERED_STATUS_POS = mouse_pos


def _status_segments_for_text(text: str, base_color):
    segments = []
    for part in re.split(r"(\s+)", text):
        if not part:
            continue
        if part.isspace():
            segments.append((part, base_color, None))
            continue
        match = re.fullmatch(r"([^A-Za-z]*)([A-Za-z][A-Za-z'-]*)([^A-Za-z]*)", part)
        if match is None:
            segments.append((part, base_color, None))
            continue
        prefix, core, suffix = match.groups()
        status_key = STATUS_ALIAS_TO_KEY.get(core.lower())
        if status_key is None:
            segments.append((part, base_color, None))
            continue
        if prefix:
            segments.append((prefix, base_color, None))
        segments.append((core, STATUS_TEXT_COLORS.get(status_key, base_color), status_key))
        if suffix:
            segments.append((suffix, base_color, None))
    return segments


def _draw_status_aware_line(surf, text, x, y, *, font_obj, base_color, mouse_pos):
    cursor_x = x
    for segment, color, status_key in _status_segments_for_text(text, base_color):
        if not segment:
            continue
        seg_width = font_obj.size(segment)[0]
        if segment.isspace():
            cursor_x += seg_width
            continue
        rect = draw_text(surf, segment, font_obj, color, (cursor_x, y))
        if status_key is not None and rect.collidepoint(mouse_pos):
            _record_status_hover(status_key, mouse_pos)
        cursor_x += seg_width


def draw_status_hover_tooltip(surf):
    if _HOVERED_STATUS_KEY is None:
        return
    entry = STATUS_EFFECT_RULES.get(_HOVERED_STATUS_KEY)
    if entry is None:
        return
    title = entry["name"]
    body_lines = _wrap_text_block(entry["description"], font_body(14), 280)
    title_font = font_label(12, bold=True)
    body_font = font_body(14)
    content_width = title_font.size(title)[0]
    for line in body_lines:
        content_width = max(content_width, body_font.size(line)[0])
    tooltip_w = content_width + 24
    tooltip_h = 36 + len(body_lines) * 18 + 12
    x = _HOVERED_STATUS_POS[0] + 16
    y = _HOVERED_STATUS_POS[1] + 18
    if x + tooltip_w > WIDTH - 8:
        x = WIDTH - tooltip_w - 8
    if y + tooltip_h > HEIGHT - 8:
        y = _HOVERED_STATUS_POS[1] - tooltip_h - 12
    x = max(8, x)
    y = max(8, y)
    tooltip_rect = pygame.Rect(x, y, tooltip_w, tooltip_h)
    border = STATUS_TEXT_COLORS.get(_HOVERED_STATUS_KEY, GOLD_BRIGHT)
    draw_beveled_panel(
        surf,
        tooltip_rect,
        fill_top=(28, 30, 36),
        fill_bottom=(18, 20, 24),
        border=border,
    )
    draw_text(surf, title, title_font, border, (tooltip_rect.x + 12, tooltip_rect.y + 10))
    for index, line in enumerate(body_lines):
        draw_text(
            surf,
            line,
            body_font,
            TEXT_SOFT,
            (tooltip_rect.x + 12, tooltip_rect.y + 32 + index * 18),
        )


def fill_gradient(surf, rect, top_color, bottom_color):
    for offset in range(rect.height):
        t = 0 if rect.height <= 1 else offset / (rect.height - 1)
        color = _lerp_color(top_color, bottom_color, t)
        pygame.draw.line(surf, color, (rect.x, rect.y + offset), (rect.right - 1, rect.y + offset))


def draw_shadow(surf, rect, radius=18, alpha=70):
    shadow = pygame.Surface((rect.width + radius * 2, rect.height + radius * 2), pygame.SRCALPHA)
    pygame.draw.rect(shadow, (0, 0, 0, alpha), pygame.Rect(radius, radius, rect.width, rect.height), border_radius=14)
    surf.blit(shadow, (rect.x - radius, rect.y - radius))


def draw_beveled_panel(surf, rect, *, title=None, title_color=TEXT, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM):
    draw_shadow(surf, rect, radius=12, alpha=55)
    fill_gradient(surf, rect, fill_top, fill_bottom)
    pygame.draw.rect(surf, border, rect, 2, border_radius=12)
    inner = rect.inflate(-6, -6)
    pygame.draw.rect(surf, (255, 255, 255, 20), inner, 1, border_radius=10)
    if title:
        draw_text(surf, title, font_headline(18, bold=True), title_color, (rect.x + 18, rect.y + 14))


def draw_glow_rect(surf, rect, color, alpha=40):
    glow = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
    pygame.draw.rect(glow, (*color, alpha), pygame.Rect(10, 10, rect.width, rect.height), border_radius=14)
    surf.blit(glow, (rect.x - 10, rect.y - 10))


def draw_icon_button(surf, rect, mouse_pos, label, *, active=False, danger=False):
    hovered = rect.collidepoint(mouse_pos)
    border = EMBER if danger else (GOLD_BRIGHT if hovered or active else GOLD_DIM)
    fill = SURFACE_HIGH if hovered or active else SURFACE
    draw_beveled_panel(surf, rect, fill_top=fill, fill_bottom=SURFACE_LOW, border=border)
    color = EMBER if danger else (GOLD_BRIGHT if hovered or active else TEXT_SOFT)
    draw_text(surf, label, font_body(18, bold=True), color, rect.center, center=True)
    return rect


def draw_primary_button(surf, rect, mouse_pos, label, *, disabled=False, accent=GOLD_BRIGHT):
    hovered = rect.collidepoint(mouse_pos) and not disabled
    button_font = font_headline(18, bold=True)
    if button_font.size(str(label))[0] > rect.width - 24:
        button_font = font_headline(16, bold=True)
    if button_font.size(str(label))[0] > rect.width - 24:
        button_font = font_headline(14, bold=True)
    button_label = _ellipsize_text(label, button_font, rect.width - 18)
    if disabled:
        fill_gradient(surf, rect, SURFACE_HIGH, SURFACE)
        pygame.draw.rect(surf, GOLD_DIM, rect, 2, border_radius=12)
        draw_text(surf, button_label, button_font, TEXT_MUTE, rect.center, center=True)
    else:
        top = _lerp_color(accent, (255, 235, 160), 0.2 if hovered else 0.0)
        bottom = _lerp_color(GOLD_DIM, accent, 0.45 if hovered else 0.2)
        fill_gradient(surf, rect, top, bottom)
        pygame.draw.rect(surf, GOLD_BRIGHT, rect, 2, border_radius=12)
        draw_text(surf, button_label, button_font, SBG_DEEP, rect.center, center=True)
    return rect


def draw_secondary_button(surf, rect, mouse_pos, label, *, active=False):
    hovered = rect.collidepoint(mouse_pos)
    fill_top = SURFACE_HIGH if hovered or active else SURFACE
    fill_bottom = SURFACE if hovered or active else SURFACE_LOW
    border = GOLD_BRIGHT if active else (PARCHMENT if hovered else GOLD_DIM)
    draw_beveled_panel(surf, rect, fill_top=fill_top, fill_bottom=fill_bottom, border=border)
    color = GOLD_BRIGHT if active else TEXT
    button_font = font_body(15, bold=True)
    if button_font.size(str(label))[0] > rect.width - 22:
        button_font = font_body(14, bold=True)
    if button_font.size(str(label))[0] > rect.width - 22:
        button_font = font_body(13, bold=True)
    button_label = _ellipsize_text(label, button_font, rect.width - 16)
    draw_text(surf, button_label, button_font, color, rect.center, center=True)
    return rect


def draw_text_input(surf, rect, mouse_pos, label, value, *, active=False, placeholder=""):
    hovered = rect.collidepoint(mouse_pos)
    border = GOLD_BRIGHT if active else (PARCHMENT if hovered else GOLD_DIM)
    draw_beveled_panel(surf, rect, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=border)
    draw_text(surf, label, font_label(11, bold=True), TEXT_MUTE, (rect.x + 14, rect.y + 10))
    shown = value or placeholder
    color = TEXT if value else TEXT_MUTE
    draw_text(surf, shown, font_body(20), color, (rect.x + 14, rect.y + 34))
    return rect


def draw_chip(surf, rect, text, color):
    pygame.draw.rect(surf, (*color, 28), rect, border_radius=10)
    pygame.draw.rect(surf, color, rect, 1, border_radius=10)
    draw_text(surf, text, font_label(10, bold=True), color, rect.center, center=True)


def draw_meter(surf, rect, value, maximum, *, fill=GOLD_BRIGHT, label=None, right_label=None):
    pygame.draw.rect(surf, SBG_DEEP, rect, border_radius=8)
    pygame.draw.rect(surf, GOLD_DIM, rect, 1, border_radius=8)
    if maximum > 0 and value > 0:
        fill_width = max(6, int((rect.width - 4) * max(0.0, min(1.0, value / maximum))))
        pygame.draw.rect(surf, fill, pygame.Rect(rect.x + 2, rect.y + 2, fill_width, rect.height - 4), border_radius=6)
    if label:
        draw_text(surf, label, font_label(10, bold=True), TEXT_MUTE, (rect.x, rect.y - 14))
    if right_label:
        draw_text(surf, right_label, font_label(10, bold=True), TEXT_SOFT, (rect.right, rect.y - 14), right=True)


def draw_background(surf):
    surf.fill(SBG)
    for index in range(12):
        radius = 180 + index * 24
        color = (20 + index * 3, 18 + index * 2, 12 + index * 2)
        pygame.draw.circle(surf, color, (WIDTH // 2, HEIGHT // 2 + 40), radius, 1)
    for index in range(8):
        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(
            glow,
            (GOLD_BRIGHT[0], GOLD_BRIGHT[1], GOLD_BRIGHT[2], 8),
            (140 + index * 160, 140 + (index % 2) * 220),
            90 + index * 10,
        )
        surf.blit(glow, (0, 0))
    pygame.draw.rect(surf, GOLD_DIM, pygame.Rect(0, 54, WIDTH, 2))


def draw_top_bar(surf, title, mouse_pos, *, left_icon=None, right_icons=(), subtitle=None):
    top_rect = pygame.Rect(0, 0, WIDTH, 56)
    fill_gradient(surf, top_rect, (8, 10, 18), (14, 16, 24))
    pygame.draw.rect(surf, GOLD_DIM, top_rect, 1)
    btns = {}
    if left_icon is not None:
        rect = pygame.Rect(20, 12, 34, 34)
        btns["left"] = draw_icon_button(surf, rect, mouse_pos, left_icon)
    title_y = 20 if subtitle is None else 8
    draw_text(surf, title, font_headline(24, bold=True), GOLD_BRIGHT, (WIDTH // 2, title_y + 8), center=True)
    if subtitle:
        draw_text(surf, subtitle, font_label(11, bold=True), TEXT_MUTE, (WIDTH // 2, 38), center=True)
    profile = CURRENT_PROFILE
    if profile is not None:
        level_info = level_state(getattr(profile, "player_exp", 0))
        reputation_value = getattr(profile, "reputation", 300)
        gold_value = getattr(profile, "gold", 0)
        stat_text = f"Gold {gold_value}   Rep {reputation_value}   Lv {level_info.level}"
        draw_text(surf, stat_text, font_label(11, bold=True), TEXT_SOFT, (WIDTH - 176, 31), right=True)
    x = WIDTH - 20
    for key, label, danger in reversed(list(right_icons)):
        rect = pygame.Rect(x - 34, 12, 34, 34)
        btns[key] = draw_icon_button(surf, rect, mouse_pos, label, danger=danger)
        x -= 44
    return btns


def _portrait_palette(adventurer):
    roles = role_tags_for_adventurer(adventurer)
    base = ROLE_COLORS.get(roles[0], SLATE_BLUE)
    accent = ROLE_COLORS.get(roles[-1], GOLD_BRIGHT)
    return base, accent


def _weapon_kind_color(kind: str):
    return WEAPON_KIND_COLORS.get(kind, GOLD_BRIGHT)


def _adventurer_weapon_kinds(adventurer):
    kinds = []
    for weapon in adventurer.signature_weapons:
        if weapon.kind not in kinds:
            kinds.append(weapon.kind)
    return kinds


def draw_adventurer_card(surf, rect, mouse_pos, adventurer, *, selected=False, unavailable=False, small=False, tag_line=None):
    base, accent = _portrait_palette(adventurer)
    hovered = rect.collidepoint(mouse_pos)
    fill_top = _lerp_color(SURFACE_HIGH, base, 0.25)
    fill_bottom = SURFACE_LOW
    border = GOLD_BRIGHT if selected else (accent if hovered else GOLD_DIM)
    draw_beveled_panel(surf, rect, fill_top=fill_top, fill_bottom=fill_bottom, border=border)
    if selected:
        draw_glow_rect(surf, rect, GOLD_BRIGHT, alpha=36)

    art_rect = pygame.Rect(rect.x + 12, rect.y + 12, rect.width - 24, 58 if small else 96)
    fill_gradient(surf, art_rect, _lerp_color(base, accent, 0.25), SBG_DEEP)
    pygame.draw.rect(surf, (255, 255, 255, 22), art_rect, 1, border_radius=10)
    initials = "".join(part[0] for part in adventurer.name.split()[:2]).upper()
    draw_text(surf, initials, font_headline(34 if small else 42, bold=True), PARCHMENT, art_rect.center, center=True)

    if small:
        name_font = font_body(15, bold=True)
        tag_font = font_label(9, bold=True)
        stat_font = font_label(10, bold=True)
        name_lines = _wrap_text_block(adventurer.name, name_font, rect.width - 28)[:2]
        meta_text = tag_line or ", ".join(role_tags_for_adventurer(adventurer)[:2])
        meta_text = _ellipsize_text(meta_text, tag_font, rect.width - 28)
        name_y = art_rect.bottom + 8
        for index, line in enumerate(name_lines):
            draw_text(surf, line, name_font, TEXT, (rect.x + 14, name_y + index * 16))
        meta_y = name_y + len(name_lines) * 16 + 2
        draw_text(surf, meta_text, tag_font, GOLD_BRIGHT, (rect.x + 14, meta_y))
        stat_y = rect.bottom - 18
        draw_text(
            surf,
            f"HP {adventurer.hp}  ATK {adventurer.attack}  DEF {adventurer.defense}  SPD {adventurer.speed}",
            stat_font,
            TEXT_SOFT,
            (rect.x + 14, stat_y),
        )
        icon_x = rect.right - 62
        for index, weapon in enumerate(adventurer.signature_weapons):
            chip = pygame.Rect(icon_x + index * 22, art_rect.y + 10, 18, 18)
            color = _weapon_kind_color(weapon.kind)
            pygame.draw.rect(surf, (*color, 28), chip, border_radius=5)
            pygame.draw.rect(surf, color, chip, 1, border_radius=5)
            draw_text(surf, weapon.kind[:1].upper(), font_label(10, bold=True), color, chip.center, center=True)
    else:
        name_y = art_rect.bottom + 10
        draw_text(surf, _ellipsize_text(adventurer.name, font_headline(18, bold=True), rect.width - 28), font_headline(18, bold=True), TEXT, (rect.x + 14, name_y))
        if tag_line:
            draw_text(surf, _ellipsize_text(tag_line, font_label(11, bold=True), rect.width - 28), font_label(11, bold=True), GOLD_BRIGHT, (rect.x + 14, name_y + 22))
        else:
            draw_text(surf, _ellipsize_text(", ".join(role_tags_for_adventurer(adventurer)), font_label(11, bold=True), rect.width - 28), font_label(11, bold=True), GOLD_BRIGHT, (rect.x + 14, name_y + 22))

        stats_y = rect.bottom - 44
        draw_text(surf, f"HP {adventurer.hp}", font_label(11, bold=True), TEXT_SOFT, (rect.x + 14, stats_y))
        draw_text(surf, f"ATK {adventurer.attack}", font_label(11, bold=True), TEXT_SOFT, (rect.x + 92, stats_y))
        draw_text(surf, f"DEF {adventurer.defense}", font_label(11, bold=True), TEXT_SOFT, (rect.x + 14, stats_y + 18))
        draw_text(surf, f"SPD {adventurer.speed}", font_label(11, bold=True), TEXT_SOFT, (rect.x + 92, stats_y + 18))

        icon_x = rect.right - 76
        for index, weapon in enumerate(adventurer.signature_weapons):
            chip = pygame.Rect(icon_x + index * 28, rect.bottom - 38, 22, 22)
            color = _weapon_kind_color(weapon.kind)
            pygame.draw.rect(surf, (*color, 28), chip, border_radius=6)
            pygame.draw.rect(surf, color, chip, 1, border_radius=6)
            draw_text(surf, weapon.kind[:1].upper(), font_label(12, bold=True), color, chip.center, center=True)

    if unavailable:
        veil = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        veil.fill((8, 8, 8, 150))
        surf.blit(veil, rect.topleft)
        draw_text(surf, "TAKEN", font_label(14, bold=True), PARCHMENT, rect.center, center=True)

    return rect


def _wrap_text_block(text, font_obj, width):
    words = str(text).split()
    lines = []
    current = ""
    for word in words:
        test = word if not current else f"{current} {word}"
        if font_obj.size(test)[0] <= width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:6]


def _wrap_multiline_block(text, font_obj, width, *, limit=18):
    lines: list[str] = []
    for paragraph in str(text).splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(_wrap_text_block(paragraph, font_obj, width))
        if len(lines) >= limit:
            break
    return lines[:limit]


def draw_main_menu(surf, mouse_pos, profile, *, has_current_quest=False):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Fabled",
        mouse_pos,
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="A tactical collectible dueling game of quests, drafting, and magical showmanship.",
    )
    level_info = level_state(getattr(profile, "player_exp", 0))
    favorite_id = getattr(profile, "storybook_favorite_adventurer", "little_jack")
    favorite_name = ADVENTURERS_BY_ID[favorite_id].name if favorite_id in ADVENTURERS_BY_ID else "Little Jack"
    training_favorite_id = getattr(profile, "storybook_training_favorite_adventurer", favorite_id)
    training_favorite_name = ADVENTURERS_BY_ID[training_favorite_id].name if training_favorite_id in ADVENTURERS_BY_ID else favorite_name
    profile_hovered = False

    profile_rect = pygame.Rect(74, 138, 310, 320)
    guild_rect = pygame.Rect(430, 168, 380, 330)
    market_rect = pygame.Rect(850, 168, 380, 330)

    profile_hovered = profile_rect.collidepoint(mouse_pos)
    draw_beveled_panel(
        surf,
        profile_rect,
        title="Profile",
        border=GOLD_BRIGHT if profile_hovered else GOLD_DIM,
    )
    if profile_hovered:
        draw_glow_rect(surf, profile_rect, GOLD_BRIGHT, alpha=28)
    draw_beveled_panel(surf, guild_rect, title="Guild Hall")
    draw_beveled_panel(surf, market_rect, title="Market")

    avatar_rect = pygame.Rect(profile_rect.x + 22, profile_rect.y + 50, 104, 134)
    fill_gradient(surf, avatar_rect, GOLD_DIM, SBG_DEEP)
    pygame.draw.rect(surf, GOLD_BRIGHT, avatar_rect, 1, border_radius=10)
    draw_text(surf, "PM", font_headline(32, bold=True), PARCHMENT, avatar_rect.center, center=True)
    draw_text(surf, "Guild Profile", font_headline(22, bold=True), TEXT, (profile_rect.x + 152, profile_rect.y + 56))
    draw_text(
        surf,
        f"Level {level_info.level}",
        font_body(19, bold=True),
        GOLD_BRIGHT,
        (profile_rect.x + 144, profile_rect.y + 96),
    )
    draw_text(
        surf,
        _ellipsize_text(
            f"{getattr(profile, 'storybook_rank_label', 'Squire')} | {getattr(profile, 'reputation', 300)} Rep",
            font_body(15),
            profile_rect.right - (profile_rect.x + 144) - 18,
        ),
        font_body(15),
        TEXT_SOFT,
        (profile_rect.x + 144, profile_rect.y + 126),
    )
    draw_text(
        surf,
        f"Gold {getattr(profile, 'gold', 0)}",
        font_body(15, bold=True),
        TEXT_SOFT,
        (profile_rect.x + 144, profile_rect.y + 154),
    )
    draw_meter(
        surf,
        pygame.Rect(profile_rect.x + 22, profile_rect.y + 210, profile_rect.width - 44, 14),
        level_info.current_level_exp,
        max(1, level_info.next_level_exp),
        right_label=f"{level_info.current_level_exp}/{level_info.next_level_exp}",
    )

    favorite_rect = pygame.Rect(profile_rect.x + 18, profile_rect.y + 236, profile_rect.width - 36, 72)
    draw_beveled_panel(surf, favorite_rect, title="Favorites")
    favorite_label_width = favorite_rect.width - 32
    draw_text(
        surf,
        _ellipsize_text(f"Quest: {favorite_name}", font_body(15, bold=True), favorite_label_width),
        font_body(15, bold=True),
        GOLD_BRIGHT,
        (favorite_rect.x + 16, favorite_rect.y + 30),
    )
    draw_text(
        surf,
        _ellipsize_text(f"Training: {training_favorite_name}", font_body(13), favorite_label_width),
        font_body(13),
        TEXT_SOFT,
        (favorite_rect.x + 16, favorite_rect.y + 50),
    )

    tile_specs = [
        (guild_rect, "Guild Hall", "Start a Quest or view the catalog"),
        (market_rect, "Market", "Buy cosmetics and get more Gold"),
    ]
    for rect, title, status in tile_specs:
        draw_text(surf, title, font_headline(36, bold=True), TEXT, (rect.x + 26, rect.y + 74))
        draw_text(surf, status, font_label(13, bold=True), TEXT_SOFT, (rect.x + 28, rect.y + 122))

    guild_label = "Guild Hall"
    guild_button_w = font_headline(18, bold=True).size(guild_label)[0] + 74
    guild_btn = pygame.Rect(guild_rect.centerx - guild_button_w // 2, guild_rect.bottom - 58, guild_button_w, 42)
    market_label = "Market"
    market_button_w = font_headline(18, bold=True).size(market_label)[0] + 74
    market_btn = pygame.Rect(market_rect.centerx - market_button_w // 2, market_rect.bottom - 58, market_button_w, 42)
    draw_primary_button(surf, guild_btn, mouse_pos, "Guild Hall")
    draw_secondary_button(surf, market_btn, mouse_pos, "Market")
    draw_text(surf, "v2.0.0 prototype", font_label(10, bold=True), GOLD_DIM, (WIDTH // 2, HEIGHT - 28), center=True)
    btns["profile"] = profile_rect
    btns["guild_hall"] = guild_btn
    btns["market"] = market_btn
    return btns


def draw_player_menu(
    surf,
    mouse_pos,
    profile,
    note_lines: list[str] | None = None,
    *,
    favorite_adventurer_id: str | None = None,
    favorite_pool_ids: list[str] | None = None,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Player",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    portrait_rect = pygame.Rect(124, 156, 360, 456)
    stats_rect = pygame.Rect(516, 156, 330, 456)
    action_rect = pygame.Rect(878, 156, 272, 456)
    draw_beveled_panel(surf, portrait_rect, title="Avatar Showcase")
    draw_beveled_panel(surf, stats_rect, title="Progress")
    draw_beveled_panel(surf, action_rect, title="Actions")
    portrait = pygame.Rect(portrait_rect.x + 34, portrait_rect.y + 56, 154, 198)
    fill_gradient(surf, portrait, (70, 62, 34), (22, 24, 28))
    pygame.draw.rect(surf, GOLD_BRIGHT, portrait, 2, border_radius=12)
    draw_text(surf, "YOU", font_label(12, bold=True), GOLD_BRIGHT, (portrait.centerx, portrait.y + 14), center=True)
    exp_value = getattr(profile, "player_exp", 0)
    level_info = level_state(exp_value)
    glory_value = getattr(profile, "reputation", 300)
    rank_label = getattr(profile, "storybook_rank_label", "Baron")
    detail_x = portrait.x + portrait.width + 26
    draw_text(surf, "Profile Stage", font_headline(20, bold=True), TEXT, (detail_x, portrait_rect.y + 72))
    detail_width = portrait_rect.right - detail_x - 18
    draw_text(surf, _ellipsize_text(f"Outfit: {getattr(profile, 'storybook_equipped_outfit', '') or 'Default'}", font_body(14), detail_width), font_body(14), TEXT_SOFT, (detail_x, portrait_rect.y + 108))
    draw_text(surf, _ellipsize_text(f"Chair: {getattr(profile, 'storybook_equipped_chair', '') or 'Default'}", font_body(14), detail_width), font_body(14), TEXT_SOFT, (detail_x, portrait_rect.y + 132))
    draw_text(surf, _ellipsize_text(f"Emote: {getattr(profile, 'storybook_equipped_emote', '') or 'Default'}", font_body(14), detail_width), font_body(14), TEXT_SOFT, (detail_x, portrait_rect.y + 156))

    level_line = f"Level {level_info.level} | {exp_value} EXP"
    exp_progress = f"{level_info.current_level_exp} / {level_info.next_level_exp}"
    meter_value = level_info.current_level_exp
    meter_max = level_info.next_level_exp
    draw_text(surf, level_line, font_body(20, bold=True), GOLD_BRIGHT, (stats_rect.x + 24, stats_rect.y + 74))
    draw_text(surf, f"{rank_label} | {glory_value} Rep", font_body(20, bold=True), TEXT_SOFT, (stats_rect.x + 24, stats_rect.y + 108))
    draw_text(surf, f"Gold {getattr(profile, 'gold', 0)}", font_body(18, bold=True), TEXT_SOFT, (stats_rect.x + 24, stats_rect.y + 140))
    draw_meter(
        surf,
        pygame.Rect(stats_rect.x + 24, stats_rect.y + 178, stats_rect.width - 48, 16),
        meter_value,
        meter_max,
        right_label=exp_progress,
    )
    favorite_rect = pygame.Rect(stats_rect.x + 24, stats_rect.y + 220, stats_rect.width - 48, 76)
    draw_beveled_panel(surf, favorite_rect, title="Favorite Adventurer")
    favorite_pool_ids = favorite_pool_ids or []
    favorite_adventurer_id = favorite_adventurer_id or (favorite_pool_ids[0] if favorite_pool_ids else None)
    favorite_name = ADVENTURERS_BY_ID[favorite_adventurer_id].name if favorite_adventurer_id in ADVENTURERS_BY_ID else "Unselected"
    draw_text(
        surf,
        favorite_name,
        font_body(20, bold=True),
        GOLD_BRIGHT,
        (favorite_rect.centerx, favorite_rect.y + 48),
        center=True,
    )
    action_font = font_headline(18, bold=True)
    friends_label = "Friends"
    friends_btn_w = action_font.size(friends_label)[0] + 74
    friends_btn = pygame.Rect(action_rect.centerx - friends_btn_w // 2, action_rect.y + 144, friends_btn_w, 44)
    closet_label = "Closet"
    closet_btn_w = action_font.size(closet_label)[0] + 74
    closet_btn = pygame.Rect(action_rect.centerx - closet_btn_w // 2, action_rect.y + 206, closet_btn_w, 44)
    draw_secondary_button(surf, friends_btn, mouse_pos, friends_label)
    draw_secondary_button(surf, closet_btn, mouse_pos, closet_label)
    btns["back"] = btns.pop("left")
    btns["favorite_card"] = favorite_rect
    btns["friends"] = friends_btn
    btns["closet"] = closet_btn
    return btns


def draw_inventory_screen(surf, mouse_pos, owned_artifacts, selected_index: int = 0):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Inventory",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Owned artifacts",
    )
    rail_rect = pygame.Rect(84, 112, 360, 708)
    detail_rect = pygame.Rect(478, 112, 812, 708)
    draw_beveled_panel(surf, rail_rect, title="Owned Artifacts")
    draw_beveled_panel(surf, detail_rect, title="Artifact Detail")
    entry_buttons = []
    if not owned_artifacts:
        draw_text(surf, "No artifacts are registered to this profile yet.", font_body(22), TEXT_SOFT, (rail_rect.x + 24, rail_rect.y + 70))
        selected = None
    else:
        selected_index = max(0, min(selected_index, len(owned_artifacts) - 1))
        for index, artifact in enumerate(owned_artifacts[:10]):
            rect = pygame.Rect(rail_rect.x + 18, rail_rect.y + 54 + index * 64, rail_rect.width - 36, 50)
            draw_secondary_button(surf, rect, mouse_pos, artifact.name, active=index == selected_index)
            draw_text(surf, ", ".join(artifact.attunement), font_body(13), TEXT_SOFT, (rect.x + 16, rect.y + 28))
            entry_buttons.append((rect, index))
        selected = owned_artifacts[selected_index]
    if selected is not None:
        draw_text(surf, _ellipsize_text(selected.name, font_headline(34, bold=True), detail_rect.width - 56), font_headline(34, bold=True), TEXT, (detail_rect.x + 28, detail_rect.y + 64))
        lines = _artifact_detail_lines(selected)
        y = detail_rect.y + 164
        for block in lines:
            for line in _wrap_multiline_block(block, font_body(20), detail_rect.width - 56, limit=6):
                draw_text(surf, line, font_body(20), TEXT_SOFT, (detail_rect.x + 28, y))
                y += 28
            y += 12
    btns["back"] = btns.pop("left")
    btns["entries"] = entry_buttons
    return btns


def draw_friends_menu(
    surf,
    mouse_pos,
    friends,
    selected_index: int,
    edit_name: str,
    edit_ip: str,
    active_field: str | None,
    status_lines: list[str] | None = None,
    queued_ip: str = "",
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Friends",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    list_rect = pygame.Rect(74, 108, 344, 726)
    editor_rect = pygame.Rect(448, 108, 844, 430)
    notes_rect = pygame.Rect(448, 566, 844, 268)
    draw_beveled_panel(surf, list_rect, title="Friend Ledger")
    draw_beveled_panel(surf, editor_rect, title="Friend Entry")
    draw_beveled_panel(surf, notes_rect, title="LAN Status")

    entry_buttons = []
    if not friends:
        draw_text(surf, "No friends saved yet.", font_headline(24, bold=True), TEXT, (list_rect.x + 22, list_rect.y + 68))
        draw_text(surf, "Add a name and host IP on the right.", font_body(17), TEXT_SOFT, (list_rect.x + 22, list_rect.y + 106))
    else:
        selected_index = max(0, min(selected_index, len(friends) - 1))
        for index, friend in enumerate(friends[:9]):
            rect = pygame.Rect(list_rect.x + 18, list_rect.y + 52 + index * 74, list_rect.width - 36, 60)
            draw_secondary_button(surf, rect, mouse_pos, friend["name"], active=index == selected_index)
            draw_text(surf, friend["ip"], font_body(13), TEXT_SOFT, (rect.x + 16, rect.y + 31))
            entry_buttons.append((rect, index))

    name_box = pygame.Rect(editor_rect.x + 26, editor_rect.y + 68, 360, 82)
    ip_box = pygame.Rect(editor_rect.x + 418, editor_rect.y + 68, 400, 82)
    draw_text_input(surf, name_box, mouse_pos, "Friend Name", edit_name, active=active_field == "name", placeholder="Ex: Rowan")
    draw_text_input(surf, ip_box, mouse_pos, "Host IP Address", edit_ip, active=active_field == "ip", placeholder="Ex: 192.168.1.18")

    save_btn = pygame.Rect(editor_rect.x + 26, editor_rect.y + 192, 218, 42)
    new_btn = pygame.Rect(editor_rect.x + 262, editor_rect.y + 192, 218, 42)
    remove_btn = pygame.Rect(editor_rect.x + 498, editor_rect.y + 192, 218, 42)
    draw_primary_button(surf, save_btn, mouse_pos, "Save Friend", disabled=not edit_name.strip() or not edit_ip.strip())
    draw_secondary_button(surf, new_btn, mouse_pos, "New Entry")
    draw_secondary_button(surf, remove_btn, mouse_pos, "Remove Friend", active=False)

    draw_text(surf, "Queued LAN Join IP", font_label(12, bold=True), TEXT_MUTE, (notes_rect.x + 24, notes_rect.y + 54))
    draw_text(surf, queued_ip or "No host has been preloaded yet.", font_headline(26, bold=True), GOLD_BRIGHT if queued_ip else TEXT_SOFT, (notes_rect.x + 24, notes_rect.y + 86))
    for index, line in enumerate((status_lines or [])[:6]):
        draw_text(surf, line, font_body(17), TEXT_SOFT, (notes_rect.x + 24, notes_rect.y + 142 + index * 24))

    btns["back"] = btns.pop("left")
    btns["entries"] = entry_buttons
    btns["name_box"] = name_box
    btns["ip_box"] = ip_box
    btns["save"] = save_btn
    btns["new"] = new_btn
    btns["remove"] = remove_btn
    return btns


def draw_guild_hall(surf, mouse_pos, *, has_current_quest: bool = False):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Guild Hall",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    current_label = "Continue Quest" if has_current_quest else "Start Quest"
    current_rect = pygame.Rect(86, 132, 680, 270)
    training_rect = pygame.Rect(86, 438, 324, 238)
    armory_rect = pygame.Rect(442, 438, 324, 238)
    catalog_rect = pygame.Rect(798, 438, 324, 238)
    draw_beveled_panel(surf, current_rect, title="Quest Desk")
    draw_beveled_panel(surf, training_rect, title="Training Grounds")
    draw_beveled_panel(surf, armory_rect, title="Armory")
    draw_beveled_panel(surf, catalog_rect, title="Catalog")

    draw_text(surf, current_label, font_headline(38, bold=True), TEXT, (current_rect.x + 28, current_rect.y + 72))
    current_lines = [
        "Resume your run or begin a fresh ranked quest.",
        "Quest starts use a 9-adventurer offer with your favorite locked in.",
    ]
    if has_current_quest:
        current_lines[0] = "Your current run is ready to resume."
    for index, line in enumerate(current_lines):
        draw_text(surf, line, font_body(16), TEXT_SOFT, (current_rect.x + 28, current_rect.y + 130 + index * 26))

    card_specs = [
        (training_rect, "Training Grounds", "One-encounter practice quest."),
        (armory_rect, "Armory", "Purchase artifacts."),
        (catalog_rect, "Catalog", "Browse the full archive."),
    ]
    for rect, title, line in card_specs:
        draw_text(surf, title, font_headline(28, bold=True), TEXT, (rect.x + 24, rect.y + 62))
        wrapped = _wrap_multiline_block(line, font_body(15), rect.width - 48, limit=4)
        for index, wrapped_line in enumerate(wrapped):
            draw_text(surf, wrapped_line, font_body(15), TEXT_SOFT, (rect.x + 24, rect.y + 108 + index * 20))

    current_btn = pygame.Rect(current_rect.x + 28, current_rect.bottom - 56, 286, 40)
    training_btn = pygame.Rect(training_rect.x + 24, training_rect.bottom - 50, training_rect.width - 48, 38)
    shops_btn = pygame.Rect(armory_rect.x + 24, armory_rect.bottom - 50, armory_rect.width - 48, 38)
    catalog_btn = pygame.Rect(catalog_rect.x + 24, catalog_rect.bottom - 50, catalog_rect.width - 48, 38)
    draw_primary_button(surf, current_btn, mouse_pos, current_label)
    draw_secondary_button(surf, training_btn, mouse_pos, "Training Grounds")
    draw_secondary_button(surf, shops_btn, mouse_pos, "Armory")
    draw_secondary_button(surf, catalog_btn, mouse_pos, "Catalog")
    btns["back"] = btns.pop("left")
    btns["current_quest"] = current_btn
    btns["training_grounds"] = training_btn
    btns["catalog"] = catalog_btn
    btns["shops"] = shops_btn
    return btns


def draw_training_grounds(surf, mouse_pos, *, training_favorite_id: str | None = None, roster_scroll: int = 0):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Training Grounds",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="One-encounter practice quest with all artifacts available.",
    )
    roster_rect = pygame.Rect(56, 108, 486, 726)
    detail_rect = pygame.Rect(560, 108, 402, 726)
    options_rect = pygame.Rect(986, 108, 248, 726)
    draw_beveled_panel(surf, roster_rect, title="Roster")
    draw_beveled_panel(surf, detail_rect, title="Adventurer Focus")
    draw_beveled_panel(surf, options_rect, title="Practice Options")

    adventurers = list(ADVENTURERS_BY_ID.values())
    max_scroll = max(0, len(adventurers) - 8)
    roster_scroll = max(0, min(roster_scroll, max_scroll))
    visible = adventurers[roster_scroll:roster_scroll + 8]
    card_buttons = []
    selected = ADVENTURERS_BY_ID.get(training_favorite_id) if training_favorite_id in ADVENTURERS_BY_ID else adventurers[0]
    for index, adventurer in enumerate(visible):
        row = index // 2
        col = index % 2
        rect = pygame.Rect(roster_rect.x + 18 + col * 226, roster_rect.y + 56 + row * 156, 210, 142)
        draw_adventurer_card(
            surf,
            rect,
            mouse_pos,
            adventurer,
            selected=adventurer.id == selected.id,
            small=True,
            tag_line="Training Favorite" if adventurer.id == selected.id else None,
        )
        card_buttons.append((rect, adventurer.id))
    draw_text(surf, _ellipsize_text(selected.name, font_headline(28, bold=True), detail_rect.width - 44), font_headline(28, bold=True), TEXT, (detail_rect.x + 22, detail_rect.y + 60))
    draw_text(surf, f"Stats: HP {selected.hp} | ATK {selected.attack} | DEF {selected.defense} | SPD {selected.speed}", font_body(15), TEXT_SOFT, (detail_rect.x + 22, detail_rect.y + 102))
    draw_text(surf, f"Innate: {selected.innate.name}", font_body(15, bold=True), GOLD_BRIGHT, (detail_rect.x + 22, detail_rect.y + 138))
    for index, line in enumerate(_wrap_text_block(selected.innate.description, font_body(14), detail_rect.width - 44)[:5]):
        draw_text(surf, line, font_body(14), TEXT_SOFT, (detail_rect.x + 22, detail_rect.y + 166 + index * 18))
    draw_text(surf, "Weapons", font_headline(22, bold=True), TEXT, (detail_rect.x + 22, detail_rect.y + 286))
    for weapon_index, weapon in enumerate(selected.signature_weapons):
        block = pygame.Rect(detail_rect.x + 22, detail_rect.y + 320 + weapon_index * 118, detail_rect.width - 44, 98)
        draw_beveled_panel(surf, block, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
        draw_text(surf, _ellipsize_text(f"{weapon.name} - {weapon.kind.title()}", font_body(16, bold=True), block.width - 28), font_body(16, bold=True), GOLD_BRIGHT, (block.x + 14, block.y + 14))
        _draw_wrapped_lines(surf, [weapon.strike.description or f"{weapon.strike.power} Power Strike"], block.x + 14, block.y + 42, block.width - 28, font=font_body(13), color=TEXT_SOFT, line_height=16)
    draw_text(surf, "Ultimate", font_headline(22, bold=True), TEXT, (detail_rect.x + 22, detail_rect.bottom - 152))
    draw_text(surf, _ellipsize_text(selected.ultimate.name, font_body(16, bold=True), detail_rect.width - 44), font_body(16, bold=True), GOLD_BRIGHT, (detail_rect.x + 22, detail_rect.bottom - 118))
    for index, line in enumerate(_wrap_text_block(selected.ultimate.description or selected.ultimate.name, font_body(14), detail_rect.width - 44)[:4]):
        draw_text(surf, line, font_body(14), TEXT_SOFT, (detail_rect.x + 22, detail_rect.bottom - 90 + index * 18))

    draw_text(surf, "All artifacts available", font_body(15, bold=True), GOLD_BRIGHT, (options_rect.x + 18, options_rect.y + 66))
    draw_text(surf, _ellipsize_text(selected.name, font_headline(20, bold=True), options_rect.width - 36), font_headline(20, bold=True), TEXT, (options_rect.x + 18, options_rect.y + 112))
    ai_btn = pygame.Rect(options_rect.x + 18, options_rect.y + 220, options_rect.width - 36, 58)
    lan_btn = pygame.Rect(options_rect.x + 18, options_rect.y + 294, options_rect.width - 36, 58)
    change_btn = pygame.Rect(options_rect.x + 18, options_rect.y + 372, options_rect.width - 36, 38)
    draw_primary_button(surf, ai_btn, mouse_pos, "AI")
    draw_secondary_button(surf, lan_btn, mouse_pos, "LAN")
    draw_secondary_button(surf, change_btn, mouse_pos, "Center Selection")
    btns["back"] = btns.pop("left")
    btns["training_cards"] = card_buttons
    btns["vs_ai"] = ai_btn
    btns["vs_lan"] = lan_btn
    btns["training_focus"] = change_btn
    btns["training_scroll_max"] = max_scroll
    return btns


def draw_market(
    surf,
    mouse_pos,
    active_tab: str,
    item_scroll: int,
    profile,
    focus_id: str | None,
    status_message: str,
    owned_cosmetics: set[str] | None = None,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Market",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Cosmetics, profile style, and Embassy exchange.",
    )
    tabs_rect = pygame.Rect(44, 86, WIDTH - 88, 102)
    list_rect = pygame.Rect(54, 210, 734, 604)
    detail_rect = pygame.Rect(816, 210, 486, 604)
    draw_beveled_panel(surf, tabs_rect)
    draw_beveled_panel(surf, list_rect, title=active_tab)
    draw_beveled_panel(surf, detail_rect, title="Preview")

    tab_buttons = []
    columns = 5
    tab_gap_x = 10
    tab_gap_y = 10
    tab_width = (tabs_rect.width - 32 - tab_gap_x * (columns - 1)) // columns
    tab_height = 28
    start_x = tabs_rect.x + 16
    start_y = tabs_rect.y + 18
    for index, tab_name in enumerate(MARKET_TABS):
        row = index // columns
        col = index % columns
        rect = pygame.Rect(
            start_x + col * (tab_width + tab_gap_x),
            start_y + row * (tab_height + tab_gap_y),
            tab_width,
            tab_height,
        )
        draw_secondary_button(surf, rect, mouse_pos, tab_name, active=tab_name == active_tab)
        tab_buttons.append((rect, tab_name))

    owned_cosmetics = owned_cosmetics or set()
    item_buttons = []
    package_buttons = []
    buy_rect = pygame.Rect(detail_rect.x + 24, detail_rect.bottom - 56, detail_rect.width - 48, 38)

    if False:  # Embassy tab removed
        pass
    else:
        items = market_items_for_tab(active_tab)
        max_scroll = max(0, len(items) - 6)
        item_scroll = max(0, min(item_scroll, max_scroll))
        visible_items = items[item_scroll:item_scroll + 6]
        selected_item = next((item for item in items if item["id"] == focus_id), items[0] if items else None)
        for index, item in enumerate(visible_items):
            row = index // 2
            col = index % 2
            rect = pygame.Rect(list_rect.x + 24 + col * 344, list_rect.y + 56 + row * 170, 320, 144)
            selected = selected_item is not None and item["id"] == selected_item["id"]
            owned = item["id"] in owned_cosmetics
            equipped = owned and item["id"] == _market_equipped_id_for_item(profile, item)
            draw_beveled_panel(
                surf,
                rect,
                fill_top=SURFACE_HIGH if selected else SURFACE,
                fill_bottom=SURFACE_LOW,
                border=GOLD_BRIGHT if selected else GOLD_DIM,
            )
            draw_text(surf, _ellipsize_text(item["name"], font_headline(20, bold=True), rect.width - 32), font_headline(20, bold=True), TEXT, (rect.x + 16, rect.y + 18))
            draw_text(surf, item["category"], font_label(10, bold=True), GOLD_BRIGHT, (rect.x + 16, rect.y + 48))
            draw_text(surf, str(item["price"]), font_label(10, bold=True), GOLD_BRIGHT, (rect.right - 16, rect.y + 18), right=True)
            state_label = "Equipped" if equipped else ("Owned" if owned else "For Sale")
            state_color = JADE if equipped else (TEXT_SOFT if owned else EMBER)
            draw_text(surf, state_label, font_label(10, bold=True), state_color, (rect.right - 16, rect.y + 48), right=True)
            subtitle_lines = _wrap_text_block(item["subtitle"], font_body(14), rect.width - 32)
            for line_index, line in enumerate(subtitle_lines[:3]):
                draw_text(surf, line, font_body(14), TEXT_SOFT, (rect.x + 16, rect.y + 78 + line_index * 18))
            item_buttons.append((rect, item["id"]))

        if selected_item is not None:
            owned = selected_item["id"] in owned_cosmetics
            equipped = owned and selected_item["id"] == _market_equipped_id_for_item(profile, selected_item)
            draw_text(surf, _ellipsize_text(selected_item["name"], font_headline(30, bold=True), detail_rect.width - 48), font_headline(30, bold=True), TEXT, (detail_rect.x + 24, detail_rect.y + 62))
            draw_text(surf, selected_item["category"], font_label(11, bold=True), GOLD_BRIGHT, (detail_rect.x + 24, detail_rect.y + 104))
            draw_text(surf, f"Price: {selected_item['price']} Gold", font_body(18, bold=True), TEXT_SOFT, (detail_rect.x + 24, detail_rect.y + 146))
            if "adventurer_id" in selected_item:
                adventurer = ADVENTURERS_BY_ID.get(str(selected_item["adventurer_id"]))
                if adventurer is not None:
                    draw_text(surf, f"For: {adventurer.name}", font_body(16), TEXT_SOFT, (detail_rect.x + 24, detail_rect.y + 176))
            state_line = "Owned and equipped." if equipped else ("Owned. Click to equip." if owned else "Not owned yet.")
            draw_text(surf, state_line, font_body(16), JADE if owned else EMBER, (detail_rect.x + 24, detail_rect.y + 208))
            for index, line in enumerate(_wrap_multiline_block(selected_item["subtitle"], font_body(16), detail_rect.width - 48, limit=8)):
                draw_text(surf, line, font_body(16), TEXT_SOFT, (detail_rect.x + 24, detail_rect.y + 256 + index * 22))
            for index, line in enumerate(_wrap_text_block(status_message or market_tab_note(active_tab), font_body(14), detail_rect.width - 48)[:5]):
                draw_text(surf, line, font_body(14), TEXT_MUTE, (detail_rect.x + 24, detail_rect.y + 438 + index * 18))
            button_label = "Equip" if owned else "Purchase"
            draw_primary_button(surf, buy_rect, mouse_pos, button_label)
        btns["market_scroll_max"] = max_scroll

    btns["back"] = btns.pop("left")
    btns["tabs"] = tab_buttons
    btns["items"] = item_buttons
    btns["packages"] = package_buttons
    btns["buy"] = buy_rect if (active_tab == "Embassy" or item_buttons) else None
    return btns


def _market_equipped_id_for_item(profile, item: dict) -> str:
    slot = str(item.get("slot", ""))
    if slot == "outfit":
        return str(getattr(profile, "storybook_equipped_outfit", ""))
    if slot == "chair":
        return str(getattr(profile, "storybook_equipped_chair", ""))
    if slot == "emote":
        return str(getattr(profile, "storybook_equipped_emote", ""))
    if slot == "adventurer_skin":
        equipped = dict(getattr(profile, "storybook_equipped_adventurer_skins", {}))
        return str(equipped.get(str(item.get("adventurer_id", "")), ""))
    return ""


def draw_closet(
    surf,
    mouse_pos,
    active_tab: str,
    items: list[dict],
    focus_id: str | None,
    owned_cosmetics: set[str] | None = None,
    profile=None,
    *,
    item_scroll: int = 0,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Closet",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    rail_rect = pygame.Rect(48, 104, 244, 730)
    preview_rect = pygame.Rect(320, 104, 432, 730)
    inventory_rect = pygame.Rect(780, 104, 528, 730)
    draw_beveled_panel(surf, rail_rect, title="Categories")
    draw_beveled_panel(surf, preview_rect, title="Preview Stage")
    draw_beveled_panel(surf, inventory_rect, title="Owned Inventory")

    owned_cosmetics = owned_cosmetics or set()
    category_buttons = []
    for index, tab_name in enumerate(CLOSET_TABS):
        rect = pygame.Rect(rail_rect.x + 18, rail_rect.y + 56 + index * 52, rail_rect.width - 36, 38)
        draw_secondary_button(surf, rect, mouse_pos, tab_name, active=tab_name == active_tab)
        category_buttons.append((rect, tab_name))

    visible_items = [item for item in items if item["id"] in owned_cosmetics]
    selected_item = next((item for item in visible_items if item["id"] == focus_id), visible_items[0] if visible_items else None)

    mannequin = pygame.Rect(preview_rect.x + 72, preview_rect.y + 76, preview_rect.width - 144, 276)
    fill_gradient(surf, mannequin, (68, 54, 26), SBG_DEEP)
    pygame.draw.rect(surf, GOLD_BRIGHT, mannequin, 2, border_radius=12)
    draw_text(surf, "PLAYER", font_label(12, bold=True), GOLD_BRIGHT, (mannequin.centerx, mannequin.y + 16), center=True)
    if selected_item is not None:
        draw_text(surf, _ellipsize_text(selected_item["name"], font_headline(26, bold=True), preview_rect.width - 52), font_headline(26, bold=True), TEXT, (preview_rect.centerx, mannequin.bottom + 40), center=True)
        draw_text(surf, selected_item["category"], font_body(16, bold=True), GOLD_BRIGHT, (preview_rect.centerx, mannequin.bottom + 78), center=True)
        equipped = profile is not None and selected_item["id"] == _market_equipped_id_for_item(profile, selected_item)
        draw_text(surf, "Equipped" if equipped else "Owned", font_body(15), JADE if equipped else TEXT_SOFT, (preview_rect.centerx, mannequin.bottom + 106), center=True)
        for index, line in enumerate(_wrap_multiline_block(selected_item["subtitle"], font_body(15), preview_rect.width - 52, limit=6)):
            draw_text(surf, line, font_body(15), TEXT_SOFT, (preview_rect.x + 26, mannequin.bottom + 156 + index * 20))
    else:
        pass

    item_buttons = []
    page_size = 8
    max_scroll = max(0, len(visible_items) - page_size)
    item_scroll = max(0, min(item_scroll, max_scroll))
    for index, item in enumerate(visible_items[item_scroll:item_scroll + page_size]):
        actual_index = item_scroll + index
        rect = pygame.Rect(inventory_rect.x + 18, inventory_rect.y + 56 + index * 74, inventory_rect.width - 36, 60)
        active = selected_item is not None and item["id"] == selected_item["id"]
        draw_secondary_button(surf, rect, mouse_pos, item["name"], active=active)
        equipped = profile is not None and item["id"] == _market_equipped_id_for_item(profile, item)
        draw_text(surf, "Equipped" if equipped else item["category"], font_body(13), JADE if equipped else TEXT_SOFT, (rect.x + 16, rect.y + 32))
        item_buttons.append((rect, item["id"], actual_index))
    equip_rect = pygame.Rect(preview_rect.x + 26, preview_rect.bottom - 56, preview_rect.width - 52, 38)
    draw_primary_button(surf, equip_rect, mouse_pos, "Equip", disabled=selected_item is None)

    btns["back"] = btns.pop("left")
    btns["categories"] = category_buttons
    btns["items"] = item_buttons
    btns["equip"] = equip_rect
    btns["scroll_max"] = max_scroll
    return btns


def draw_favored_adventurer_select(
    surf,
    mouse_pos,
    favorite_pool_ids: list[str],
    focused_id: str | None,
    selected_id: str | None,
    *,
    scroll: int = 0,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Favored Adventurer",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    grid_rect = pygame.Rect(56, 104, 760, 730)
    detail_rect = pygame.Rect(844, 104, 460, 730)
    draw_beveled_panel(surf, grid_rect, title="Eligible Favorites")
    draw_beveled_panel(surf, detail_rect, title="Detail")

    pool = [adventurer_id for adventurer_id in favorite_pool_ids if adventurer_id in ADVENTURERS_BY_ID]
    max_scroll = max(0, len(pool) - 9)
    scroll = max(0, min(scroll, max_scroll))
    visible = pool[scroll:scroll + 9]
    focused_id = focused_id if focused_id in ADVENTURERS_BY_ID else (visible[0] if visible else None)
    focused = ADVENTURERS_BY_ID[focused_id] if focused_id else None
    card_buttons = []
    visible_count = len(visible)
    columns = 3 if visible_count >= 3 else max(1, visible_count)
    card_width = 224 if visible_count >= 3 else 264
    card_gap = 18
    for index, adventurer_id in enumerate(visible):
        adventurer = ADVENTURERS_BY_ID[adventurer_id]
        row = index // columns
        col = index % columns
        row_count = min(columns, max(1, visible_count - row * columns))
        row_width = row_count * card_width + max(0, row_count - 1) * card_gap
        row_start_x = grid_rect.x + (grid_rect.width - row_width) // 2
        rect = pygame.Rect(row_start_x + col * (card_width + card_gap), grid_rect.y + 54 + row * 216, card_width, 196 if visible_count >= 3 else 214)
        draw_adventurer_card(
            surf,
            rect,
            mouse_pos,
            adventurer,
            selected=adventurer_id == focused_id,
            small=True,
            tag_line="Current Favorite" if adventurer_id == selected_id else None,
        )
        card_buttons.append((rect, adventurer_id))

    if focused is not None:
        draw_text(surf, _ellipsize_text(focused.name, font_headline(30, bold=True), detail_rect.width - 48), font_headline(30, bold=True), TEXT, (detail_rect.x + 24, detail_rect.y + 62))
        draw_text(
            surf,
            f"Stats: HP {focused.hp} | ATK {focused.attack} | DEF {focused.defense} | SPD {focused.speed}",
            font_body(16),
            TEXT_SOFT,
            (detail_rect.x + 24, detail_rect.y + 104),
        )
        draw_text(surf, f"Innate: {focused.innate.name}", font_body(16, bold=True), GOLD_BRIGHT, (detail_rect.x + 24, detail_rect.y + 142))
        for index, line in enumerate(_wrap_multiline_block(focused.innate.description, font_body(15), detail_rect.width - 48, limit=6)):
            draw_text(surf, line, font_body(15), TEXT_SOFT, (detail_rect.x + 24, detail_rect.y + 172 + index * 20))
        draw_text(surf, "Weapons", font_headline(22, bold=True), TEXT, (detail_rect.x + 24, detail_rect.y + 316))
        for weapon_index, weapon in enumerate(focused.signature_weapons):
            block = pygame.Rect(detail_rect.x + 24, detail_rect.y + 350 + weapon_index * 112, detail_rect.width - 48, 90)
            draw_beveled_panel(surf, block, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
            draw_text(surf, _ellipsize_text(f"{weapon.name} - {weapon.kind.title()}", font_body(16, bold=True), block.width - 28), font_body(16, bold=True), GOLD_BRIGHT, (block.x + 14, block.y + 12))
            detail_lines = _wrap_text_block(weapon.strike.description or f"{weapon.strike.power} Power Strike", font_body(13), block.width - 28)
            for line_index, line in enumerate(detail_lines[:3]):
                draw_text(surf, line, font_body(13), TEXT_SOFT, (block.x + 14, block.y + 40 + line_index * 16))
        draw_text(surf, _ellipsize_text(f"Ultimate: {focused.ultimate.name}", font_body(16, bold=True), detail_rect.width - 48), font_body(16, bold=True), GOLD_BRIGHT, (detail_rect.x + 24, detail_rect.bottom - 126))
        for index, line in enumerate(_wrap_multiline_block(focused.ultimate.description or focused.ultimate.name, font_body(14), detail_rect.width - 48, limit=4)):
            draw_text(surf, line, font_body(14), TEXT_SOFT, (detail_rect.x + 24, detail_rect.bottom - 98 + index * 18))

    confirm_rect = pygame.Rect(detail_rect.x + 24, detail_rect.bottom - 54, detail_rect.width - 48, 38)
    draw_primary_button(surf, confirm_rect, mouse_pos, "Set Favorite", disabled=focused is None)
    btns["back"] = btns.pop("left")
    btns["cards"] = card_buttons
    btns["confirm"] = confirm_rect
    btns["scroll_max"] = max_scroll
    return btns


def draw_party_picker(surf, mouse_pos, parties: list[dict], selected_index: int, *, title: str, subtitle: str, start_label: str):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        title,
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=subtitle,
    )
    rail_rect = pygame.Rect(64, 112, 370, 710)
    detail_rect = pygame.Rect(460, 112, 876, 710)
    draw_beveled_panel(surf, rail_rect, title="Saved Parties")
    draw_beveled_panel(surf, detail_rect, title="Party Detail")
    party_buttons = []
    for index, party in enumerate(parties[:8]):
        rect = pygame.Rect(rail_rect.x + 18, rail_rect.y + 54 + index * 78, rail_rect.width - 36, 66)
        draw_secondary_button(surf, rect, mouse_pos, party["name"], active=index == selected_index)
        draw_text(surf, f"{len(party['members'])} Adventurers", font_body(13), TEXT_SOFT, (rect.x + 16, rect.y + 34))
        party_buttons.append((rect, index))
    selected = parties[selected_index] if parties else None
    if selected is not None:
        draw_text(surf, _ellipsize_text(selected["name"], font_headline(34, bold=True), detail_rect.width - 48), font_headline(34, bold=True), TEXT, (detail_rect.x + 24, detail_rect.y + 62))
        draw_text(
            surf,
            f"Size: {len(selected['members'])} / 6 | Classes must be unique",
            font_body(16),
            TEXT_SOFT,
            (detail_rect.x + 24, detail_rect.y + 106),
        )
        for index, member in enumerate(selected["members"][:6]):
            row = index // 3
            col = index % 3
            adventurer = ADVENTURERS_BY_ID.get(member["adventurer_id"])
            if adventurer is None:
                continue
            rect = pygame.Rect(detail_rect.x + 24 + col * 278, detail_rect.y + 150 + row * 186, 260, 166)
            draw_adventurer_card(
                surf,
                rect,
                mouse_pos,
                adventurer,
                selected=False,
                small=True,
                tag_line=member.get("class_name", "Fighter"),
            )
    else:
        draw_text(surf, "No party available.", font_headline(24, bold=True), TEXT, (detail_rect.x + 24, detail_rect.y + 72))
    start_btn = pygame.Rect(detail_rect.right - 260, detail_rect.bottom - 62, 236, 42)
    draw_primary_button(
        surf,
        start_btn,
        mouse_pos,
        start_label,
        disabled=selected is None or len(selected["members"]) != 6,
    )
    btns["back"] = btns.pop("left")
    btns["parties"] = party_buttons
    btns["start"] = start_btn
    return btns


def draw_guild_parties(
    surf,
    mouse_pos,
    parties: list[dict],
    selected_index: int,
    *,
    adventurer_scroll: int = 0,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Your Guild",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Create and edit parties (6 members, unique classes)",
    )
    party_rect = pygame.Rect(44, 108, 320, 730)
    team_rect = pygame.Rect(388, 108, 446, 730)
    pool_rect = pygame.Rect(858, 108, 498, 730)
    draw_beveled_panel(surf, party_rect, title="Parties")
    draw_beveled_panel(surf, team_rect, title="Selected Party")
    draw_beveled_panel(surf, pool_rect, title="Adventurer Pool")
    party_buttons = []
    for index, party in enumerate(parties[:8]):
        rect = pygame.Rect(party_rect.x + 18, party_rect.y + 56 + index * 78, party_rect.width - 36, 64)
        draw_secondary_button(surf, rect, mouse_pos, party["name"], active=index == selected_index)
        draw_text(surf, f"{len(party['members'])} members", font_body(13), TEXT_SOFT, (rect.x + 16, rect.y + 34))
        party_buttons.append((rect, index))
    new_btn = pygame.Rect(party_rect.x + 18, party_rect.bottom - 102, party_rect.width - 36, 38)
    delete_btn = pygame.Rect(party_rect.x + 18, party_rect.bottom - 54, party_rect.width - 36, 38)
    draw_secondary_button(surf, new_btn, mouse_pos, "New Party")
    draw_secondary_button(surf, delete_btn, mouse_pos, "Delete Party", active=False)

    selected_party = parties[selected_index] if parties else None
    member_remove_buttons = []
    member_class_buttons = []
    if selected_party is not None:
        draw_text(
            surf,
            f"{selected_party['name']} | {len(selected_party['members'])}/6",
            font_headline(24, bold=True),
            TEXT,
            (team_rect.x + 18, team_rect.y + 56),
        )
        draw_text(
            surf,
            "Click a member card to remove. Cycle class to keep classes unique.",
            font_body(14),
            TEXT_SOFT,
            (team_rect.x + 18, team_rect.y + 88),
        )
        for index, member in enumerate(selected_party["members"][:6]):
            row = index // 2
            col = index % 2
            adventurer = ADVENTURERS_BY_ID.get(member["adventurer_id"])
            if adventurer is None:
                continue
            card_rect = pygame.Rect(team_rect.x + 18 + col * 208, team_rect.y + 126 + row * 194, 196, 150)
            draw_adventurer_card(
                surf,
                card_rect,
                mouse_pos,
                adventurer,
                selected=False,
                small=True,
                tag_line=member.get("class_name", "Fighter"),
            )
            member_remove_buttons.append((card_rect, index))
            class_btn = pygame.Rect(card_rect.x, card_rect.bottom + 8, card_rect.width, 28)
            draw_secondary_button(
                surf,
                class_btn,
                mouse_pos,
                f"Class: {member.get('class_name', 'Fighter')}",
                active=False,
            )
            member_class_buttons.append((class_btn, index))
        if len(selected_party["members"]) < 6:
            draw_text(
                surf,
                "Need exactly 6 members to start a ranked quest.",
                font_body(15, bold=True),
                EMBER,
                (team_rect.x + 18, team_rect.bottom - 36),
            )

    adventurer_cards = []
    all_adventurers = list(ADVENTURERS_BY_ID.values())
    max_scroll = max(0, len(all_adventurers) - 8)
    adventurer_scroll = max(0, min(adventurer_scroll, max_scroll))
    for index, adventurer in enumerate(all_adventurers[adventurer_scroll : adventurer_scroll + 8]):
        row = index // 2
        col = index % 2
        rect = pygame.Rect(pool_rect.x + 18 + col * 236, pool_rect.y + 56 + row * 160, 220, 146)
        draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=False, small=True, tag_line="ADD")
        adventurer_cards.append((rect, adventurer.id))
    btns["back"] = btns.pop("left")
    btns["party_buttons"] = party_buttons
    btns["new_party"] = new_btn
    btns["delete_party"] = delete_btn
    btns["member_remove"] = member_remove_buttons
    btns["member_class"] = member_class_buttons
    btns["adventurer_cards"] = adventurer_cards
    btns["adventurer_scroll_max"] = max_scroll
    return btns


def draw_shops(
    surf,
    mouse_pos,
    active_tab: str,
    cosmetic_index: int,
    item_scroll: int,
    profile=None,
    focus_kind: str | None = None,
    focus_value=None,
    status_message: str = "",
    owned_items: set[str] | None = None,
    owned_cosmetics: set[str] | None = None,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Armory",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Purchase artifacts for your collection.",
    )
    tab_buttons = []
    for index, tab_name in enumerate(SHOP_TABS):
        rect = pygame.Rect(98 + index * 144, 92, 132, 38)
        draw_secondary_button(surf, rect, mouse_pos, tab_name, active=tab_name == active_tab)
        tab_buttons.append((rect, tab_name))
    info_panel = pygame.Rect(58, 168, 286, 620)
    inventory_panel = pygame.Rect(370, 168, 566, 620)
    detail_panel = pygame.Rect(962, 168, 312, 620)
    draw_beveled_panel(surf, info_panel, title="Armory")
    draw_beveled_panel(surf, inventory_panel, title=active_tab)
    draw_beveled_panel(surf, detail_panel, title="Artifact Detail")
    owned_items = owned_items or set()
    items = shop_items_for_tab(active_tab)
    max_scroll = max(0, len(items) - 6)
    item_scroll = max(0, min(item_scroll, max_scroll))
    visible_items = items[item_scroll:item_scroll + 6]
    item_buttons = []
    for index, item in enumerate(visible_items):
        row = index // 2
        col = index % 2
        rect = pygame.Rect(inventory_panel.x + 24 + col * 266, inventory_panel.y + 58 + row * 140, 246, 116)
        selected = focus_kind == "item" and focus_value == item["id"]
        draw_beveled_panel(
            surf,
            rect,
            fill_top=SURFACE_HIGH if selected else SURFACE,
            fill_bottom=SURFACE_LOW,
            border=GOLD_BRIGHT if selected else GOLD_DIM,
        )
        draw_text(surf, item["tag"], font_label(10, bold=True), GOLD_BRIGHT, (rect.x + 16, rect.y + 14))
        draw_text(surf, str(item["price"]), font_label(10, bold=True), GOLD_BRIGHT, (rect.right - 16, rect.y + 14), right=True)
        draw_text(surf, _ellipsize_text(item["name"], font_headline(20, bold=True), rect.width - 32), font_headline(20, bold=True), TEXT, (rect.x + 16, rect.y + 42))
        draw_text(surf, item["subtitle"], font_body(15), TEXT_SOFT, (rect.x + 16, rect.y + 74))
        if item["id"] in owned_items:
            draw_text(surf, "Owned", font_label(10, bold=True), JADE, (rect.right - 16, rect.y + 42), right=True)
        item_buttons.append((rect, item["id"]))

    if not visible_items:
        draw_text(surf, shop_tab_note(active_tab), font_body(19), TEXT_SOFT, (inventory_panel.x + 26, inventory_panel.y + 76))

    selected_item = next((item for item in items if focus_kind == "item" and item["id"] == focus_value), items[0] if items else None)
    buy_label = "Purchase"
    buy_disabled = False
    detail_lines = []
    detail_title = "Select An Artifact"
    if selected_item is not None:
        detail_title = selected_item["name"]
        item_key = selected_item["id"]
        buy_disabled = item_key in owned_items
        artifact = ALL_ARTIFACTS_BY_ID.get(str(selected_item.get("artifact_id", item_key)))
        detail_lines = [f"Price: {selected_item['price']} Gold"]
        if artifact is not None:
            detail_lines.extend(_artifact_detail_lines(artifact))
        else:
            detail_lines.append(selected_item["subtitle"])
    else:
        buy_disabled = True
        buy_label = "Unavailable"
        detail_title = active_tab
        detail_lines = [
            "Select an artifact to inspect its effect and stat bonus.",
        ]

    for index, line in enumerate(_wrap_text_block(status_message or "Your treasury is ready for new relics.", font_body(15), info_panel.width - 40)[:6]):
        draw_text(surf, line, font_body(15), TEXT_MUTE, (info_panel.x + 20, info_panel.y + 58 + index * 18))
    draw_text(surf, "Current Gold", font_label(11, bold=True), TEXT_MUTE, (info_panel.x + 20, info_panel.bottom - 102))
    draw_text(surf, str(getattr(profile, "gold", 0) if profile is not None else 0), font_headline(28, bold=True), GOLD_BRIGHT, (info_panel.x + 20, info_panel.bottom - 72))

    draw_text(surf, _ellipsize_text(detail_title, font_headline(24, bold=True), detail_panel.width - 36), font_headline(24, bold=True), TEXT, (detail_panel.x + 18, detail_panel.y + 56))
    detail_y = detail_panel.y + 100
    for block in detail_lines:
        wrapped = _wrap_multiline_block(block, font_body(15), detail_panel.width - 36, limit=8)
        for line in wrapped:
            draw_text(surf, line, font_body(15), TEXT_SOFT, (detail_panel.x + 18, detail_y))
            detail_y += 20
        detail_y += 8
    buy_btn = pygame.Rect(detail_panel.x + 18, detail_panel.bottom - 56, detail_panel.width - 36, 38)
    draw_primary_button(surf, buy_btn, mouse_pos, buy_label, disabled=buy_disabled)
    btns["back"] = btns.pop("left")
    btns["tabs"] = tab_buttons
    btns["items"] = item_buttons
    btns["buy"] = buy_btn
    btns["shop_scroll_max"] = max_scroll
    return btns


def draw_quests_menu(
    surf,
    mouse_pos,
    *,
    run_active: bool,
    quest_wins: int,
    quest_losses: int,
    current_win_streak: int,
    current_loss_streak: int,
    party_ids: list[str] | None = None,
    enemy_party_ids: list[str] | None = None,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Current Quest",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Review your run, tune your six-member party, then enter encounter prep.",
    )
    party_ids = list(party_ids or [])
    enemy_party_ids = list(enemy_party_ids or [])
    party_rect = pygame.Rect(120, 144, 560, 612)
    status_rect = pygame.Rect(710, 144, 530, 286)
    enemy_rect = pygame.Rect(710, 470, 530, 286)
    draw_beveled_panel(surf, party_rect, title="Your Party")
    draw_beveled_panel(surf, status_rect, title="Quest Status")
    draw_beveled_panel(surf, enemy_rect, title="Encounter Prep")

    if run_active:
        for index, adventurer_id in enumerate(party_ids[:6]):
            adventurer = ADVENTURERS_BY_ID.get(adventurer_id)
            if adventurer is None:
                continue
            draw_text(
                surf,
                f"{index + 1}. {adventurer.name}",
                font_body(18, bold=True),
                TEXT_SOFT,
                (party_rect.x + 24, party_rect.y + 60 + index * 34),
            )
    else:
        draw_text(
            surf,
            "No active quest. Start one to auto-assemble a 6-member party around your favorite adventurer.",
            font_body(19, bold=True),
            TEXT_SOFT,
            (party_rect.x + 24, party_rect.y + 66),
        )

    draw_text(surf, f"Wins: {quest_wins}", font_body(22, bold=True), GOLD_BRIGHT if run_active else TEXT_SOFT, (status_rect.x + 24, status_rect.y + 62))
    draw_text(surf, f"Losses: {quest_losses} / 3", font_body(22, bold=True), EMBER if run_active else TEXT_SOFT, (status_rect.x + 24, status_rect.y + 98))
    draw_text(surf, f"Winstreak: {current_win_streak}", font_body(18), TEXT_SOFT, (status_rect.x + 24, status_rect.y + 146))
    draw_text(surf, f"Lossstreak: {current_loss_streak}", font_body(18), TEXT_SOFT, (status_rect.x + 24, status_rect.y + 178))
    status_note = "Edit Party Loadouts first, then Prepare Encounter to reveal enemy names and choose your 3."
    if not run_active:
        status_note = "Starting a quest auto-assembles a 6-member party around your favorite adventurer with class diversity."
    for index, line in enumerate(_wrap_text_block(status_note, font_body(15), status_rect.width - 48)[:3]):
        draw_text(
            surf,
            line,
            font_body(15),
            TEXT_SOFT,
            (status_rect.x + 24, status_rect.y + 224 + index * 18),
        )

    prep_lines = [
        "Party loadouts lock before the rival lineup is revealed.",
        "Prepare Encounter shows enemy names only, then you choose 3 adventurers.",
        "After that, only formation changes remain before battle.",
    ]
    if run_active and enemy_party_ids:
        prep_lines.append(f"The next rival lineup is prepared in the background ({len(enemy_party_ids)} adventurers).")
    elif not run_active:
        prep_lines = [
            "Start Quest auto-assembles your 6-member party for review.",
            "Set loadouts for all 6, then choose 3 for each encounter.",
            "You can retune loadouts and formation before every fight.",
        ]
    if run_active:
        prep_lines.append(f"Forfeit Quest costs {max(0, 3 - quest_losses) * 10} Reputation right now.")
    for index, line in enumerate(prep_lines):
        draw_text(
            surf,
            line,
            font_body(16, bold=index == 0),
            GOLD_BRIGHT if index == 0 else TEXT_SOFT,
            (enemy_rect.x + 24, enemy_rect.y + 60 + index * 34),
        )

    if run_active:
        edit_btn = pygame.Rect(120, 786, 340, 46)
        advance_btn = pygame.Rect(510, 786, 340, 46)
        forfeit_btn = pygame.Rect(900, 786, 340, 46)
        draw_secondary_button(surf, edit_btn, mouse_pos, "Edit Party Loadouts", active=True)
        draw_primary_button(surf, advance_btn, mouse_pos, "Prepare Encounter")
        draw_secondary_button(surf, forfeit_btn, mouse_pos, "Forfeit Quest")
    else:
        edit_btn = pygame.Rect(120, 786, 550, 46)
        advance_btn = pygame.Rect(690, 786, 550, 46)
        forfeit_btn = None
        draw_secondary_button(surf, edit_btn, mouse_pos, "Edit Party Loadouts", active=False)
        draw_primary_button(surf, advance_btn, mouse_pos, "Start Quest")
    btns["back"] = btns.pop("left")
    btns["edit_loadouts"] = edit_btn
    btns["advance"] = advance_btn
    btns["forfeit"] = forfeit_btn
    return btns


def draw_quest_party_reveal(surf, mouse_pos, party_ids: list, favorite_id: str | None = None):
    """Show the auto-assembled 6-member quest party before confirming the run."""
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Quest Party",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Your party has been assembled. Review and confirm to set loadouts.",
    )

    party_panel = pygame.Rect(80, 110, 840, 660)
    rules_panel = pygame.Rect(950, 110, 370, 430)
    draw_beveled_panel(surf, party_panel, title="Party (6 Members)")
    draw_beveled_panel(surf, rules_panel, title="Quest Rules")

    # 6 adventurer cards in a 3-column, 2-row grid
    card_w, card_h = 244, 196
    col_step = card_w + 18
    row_step = card_h + 18
    grid_w = 3 * card_w + 2 * 18
    grid_x = party_panel.x + (party_panel.width - grid_w) // 2
    grid_y = party_panel.y + 60

    party_buttons = []
    hover_adventurer = None
    for index, adventurer_id in enumerate(party_ids[:6]):
        adventurer = ADVENTURERS_BY_ID.get(adventurer_id)
        if adventurer is None:
            continue
        row, col = divmod(index, 3)
        card_rect = pygame.Rect(grid_x + col * col_step, grid_y + row * row_step, card_w, card_h)
        is_favorite = adventurer_id == favorite_id
        draw_adventurer_card(
            surf,
            card_rect,
            mouse_pos,
            adventurer,
            selected=is_favorite,
            tag_line="Favorite — Locked In" if is_favorite else None,
        )
        party_buttons.append((card_rect, adventurer_id))
        if card_rect.collidepoint(mouse_pos):
            hover_adventurer = adventurer

    # Quest rules text
    rule_lines = [
        "Win Condition: 3 wins before 3 losses.",
        "",
        "Each encounter: choose 3 of your 6.",
        "Tune formation between every fight.",
        "",
        "Rewards accumulate over the run.",
        "Rep gain is applied at the end.",
    ]
    for index, line in enumerate(rule_lines):
        if not line:
            continue
        draw_text(surf, line, font_body(16, bold=(index == 0)), GOLD_BRIGHT if index == 0 else TEXT_SOFT, (rules_panel.x + 24, rules_panel.y + 58 + index * 26))

    back_btn = pygame.Rect(80, 802, 280, 46)
    confirm_btn = pygame.Rect(400, 802, 520, 46)
    draw_secondary_button(surf, back_btn, mouse_pos, "Back")
    draw_primary_button(surf, confirm_btn, mouse_pos, "Confirm Party & Set Loadouts")
    btns["back"] = btns.pop("left")
    btns["confirm"] = confirm_btn
    btns["party_cards"] = party_buttons
    if hover_adventurer is not None:
        _draw_adventurer_popout(surf, pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1), hover_adventurer)
    return btns


def draw_quest_reward_choice(surf, mouse_pos, options: list, *, wins: int = 0, losses: int = 0):
    """Show the three reward options after a quest encounter win.

    Returns choices as list of (rect, choice_index, artifact_id | None).
    """
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Encounter Won!",
        mouse_pos,
        left_icon=None,
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=f"Quest Record: {wins}W – {losses}L  |  Choose your reward.",
    )

    # Left panel: Gold and Recruit options
    left_panel = pygame.Rect(60, 120, 500, 640)
    # Right panel: Artifact choices
    right_panel = pygame.Rect(590, 120, 750, 640)
    draw_beveled_panel(surf, left_panel, title="Rewards")
    draw_beveled_panel(surf, right_panel, title="Option B — Artifact (Choose One)")

    choices = []
    btn_w = left_panel.width - 60
    btn_x = left_panel.x + 30

    # Option A: Gold
    gold_option = next((o for o in options if o.get("kind") == "gold"), None)
    gold_rect = pygame.Rect(btn_x, left_panel.y + 72, btn_w, 100)
    gold_hovered = gold_rect.collidepoint(mouse_pos)
    draw_beveled_panel(surf, gold_rect, border=GOLD_BRIGHT if gold_hovered else GOLD_DIM)
    if gold_hovered:
        draw_glow_rect(surf, gold_rect, GOLD_BRIGHT, alpha=24)
    gold_amount = gold_option.get("amount", 100) if gold_option else 100
    draw_text(surf, f"A — +{gold_amount} Gold", font_headline(20, bold=True), TEXT, (gold_rect.x + 18, gold_rect.y + 20))
    draw_text(surf, "Added to your quest's Gold pool.", font_body(15), TEXT_SOFT, (gold_rect.x + 18, gold_rect.y + 52))
    gold_idx = next((i for i, o in enumerate(options) if o.get("kind") == "gold"), 0)
    choices.append((gold_rect, gold_idx, None))

    # Option C: Recruit
    recruit_option = next((o for o in options if o.get("kind") == "recruit"), None)
    recruit_idx = next((i for i, o in enumerate(options) if o.get("kind") == "recruit"), 2)
    recruit_rect = pygame.Rect(btn_x, left_panel.y + 200, btn_w, 100)
    rec_hovered = recruit_rect.collidepoint(mouse_pos)
    draw_beveled_panel(surf, recruit_rect, border=GOLD_BRIGHT if rec_hovered else GOLD_DIM)
    if rec_hovered:
        draw_glow_rect(surf, recruit_rect, GOLD_BRIGHT, alpha=24)
    draw_text(surf, "C — Recruit (100 Gold)", font_headline(20, bold=True), TEXT, (recruit_rect.x + 18, recruit_rect.y + 20))
    draw_text(surf, "Replace an adventurer (coming soon).", font_body(15), TEXT_SOFT, (recruit_rect.x + 18, recruit_rect.y + 52))
    choices.append((recruit_rect, recruit_idx, None))

    # Option B: Artifact sub-choices (right panel)
    artifact_option = next((o for o in options if o.get("kind") == "artifact"), None)
    artifact_idx = next((i for i, o in enumerate(options) if o.get("kind") == "artifact"), 1)
    artifact_choices = (artifact_option or {}).get("artifact_choices") or []
    art_card_h = 140
    art_card_gap = 24
    art_card_w = right_panel.width - 60
    art_card_x = right_panel.x + 30
    hovered_artifact = None
    for sub_index, artifact_choice in enumerate(artifact_choices[:3]):
        art_rect = pygame.Rect(art_card_x, right_panel.y + 60 + sub_index * (art_card_h + art_card_gap), art_card_w, art_card_h)
        art_hovered = art_rect.collidepoint(mouse_pos)
        draw_beveled_panel(surf, art_rect, border=GOLD_BRIGHT if art_hovered else GOLD_DIM)
        if art_hovered:
            draw_glow_rect(surf, art_rect, GOLD_BRIGHT, alpha=24)
        artifact_name = artifact_choice.get("artifact_name", "Unknown")
        artifact_id = artifact_choice.get("artifact_id")
        draw_text(surf, artifact_name, font_headline(20, bold=True), TEXT, (art_rect.x + 18, art_rect.y + 22))
        draw_text(surf, "Add to artifact pool.", font_body(15), TEXT_SOFT, (art_rect.x + 18, art_rect.y + 56))
        choices.append((art_rect, artifact_idx, artifact_id))
        if art_hovered and artifact_id in ALL_ARTIFACTS_BY_ID:
            hovered_artifact = (art_rect, ALL_ARTIFACTS_BY_ID[artifact_id])

    btns["choices"] = choices
    if hovered_artifact is not None:
        _draw_info_popout(surf, hovered_artifact[0], hovered_artifact[1].name, _artifact_detail_lines(hovered_artifact[1]))
    return btns


def draw_quest_draft(
    surf,
    mouse_pos,
    offer_ids,
    focused_id,
    selected_ids,
    *,
    detail_scroll: int = 0,
    title: str = "Encounter Prep",
    enemy_party_ids: list[str] | None = None,
    card_scroll: int = 0,
    allow_text_import: bool = False,
    import_open: bool = False,
    import_text: str = "",
    import_status_lines: list[str] | None = None,
    target_count: int = 3,
    continue_label: str = "Continue To Loadouts",
    selected_panel_title: str = "Encounter Team (Click To Remove)",
    side_panel_title: str = "Enemy Party",
    side_panel_lines: list[str] | None = None,
):
    draw_background(surf)
    progress = "Full Party" if len(selected_ids) >= target_count else f"Select {len(selected_ids) + 1} of {target_count}"
    btns = draw_top_bar(
        surf,
        title,
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=progress,
    )
    cards = []
    if target_count > 3:
        start_x = 230
        start_y = 102
        card_w = 214
        card_h = 176
        row_step = 184
    else:
        start_x = 260
        start_y = 114
        card_w = 204
        card_h = 238
        row_step = 258
    visible_capacity = 9 if target_count > 3 else 6
    max_offer_scroll = max(0, len(offer_ids) - visible_capacity)
    card_scroll = max(0, min(card_scroll, max_offer_scroll))
    visible_offer_ids = offer_ids[card_scroll : card_scroll + visible_capacity]
    for index, adventurer_id in enumerate(visible_offer_ids):
        adventurer = ADVENTURERS_BY_ID[adventurer_id]
        row = index // 3
        col = index % 3
        rect = pygame.Rect(start_x + col * 228, start_y + row * row_step, card_w, card_h)
        cards.append((draw_adventurer_card(
            surf,
            rect,
            mouse_pos,
            adventurer,
            selected=adventurer_id == focused_id,
            unavailable=adventurer_id in selected_ids,
            small=True,
        ), adventurer_id))
    if offer_ids:
        start_index = card_scroll + 1
        end_index = min(len(offer_ids), card_scroll + len(visible_offer_ids))
        draw_text(
            surf,
            f"Showing {start_index}-{end_index} of {len(offer_ids)}",
            font_body(13),
            TEXT_SOFT,
            (520, 654 if target_count > 3 else 615),
            center=True,
        )
    party_rect = pygame.Rect(230, 642, 486, 194)
    enemy_rect = pygame.Rect(726, 642, 176, 194)
    detail_rect = pygame.Rect(920, 96, 434, 740)
    draw_beveled_panel(surf, party_rect, title=selected_panel_title)
    draw_beveled_panel(surf, enemy_rect, title=side_panel_title)
    slot_buttons = []
    if target_count <= 3:
        for index in range(target_count):
            rect = pygame.Rect(party_rect.x + 18 + index * 150, party_rect.y + 52, 132, 86)
            if index < len(selected_ids):
                adventurer = ADVENTURERS_BY_ID[selected_ids[index]]
                hovered = rect.collidepoint(mouse_pos)
                draw_beveled_panel(
                    surf,
                    rect,
                    fill_top=SURFACE_HIGH if hovered else SURFACE,
                    fill_bottom=SURFACE_LOW,
                    border=GOLD_BRIGHT,
                )
                badge = pygame.Rect(rect.x + 10, rect.y + 10, 38, 26)
                base, accent = _portrait_palette(adventurer)
                fill_gradient(surf, badge, _lerp_color(base, accent, 0.25), SBG_DEEP)
                pygame.draw.rect(surf, GOLD_DIM, badge, 1, border_radius=6)
                initials = "".join(part[0] for part in adventurer.name.split()[:2]).upper()
                draw_text(surf, initials, font_body(16, bold=True), PARCHMENT, badge.center, center=True)
                draw_text(surf, _ellipsize_text(adventurer.name, font_body(13, bold=True), rect.width - 20), font_body(13, bold=True), TEXT, (rect.x + 10, rect.y + 40))
                draw_text(surf, "REMOVE", font_label(10, bold=True), GOLD_BRIGHT, (rect.x + 10, rect.y + 58))
                slot_buttons.append((rect, selected_ids[index]))
            else:
                draw_beveled_panel(surf, rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
                draw_text(surf, "Available", font_label(11, bold=True), TEXT_MUTE, rect.center, center=True)
    else:
        for index in range(target_count):
            row = index // 3
            col = index % 3
            rect = pygame.Rect(party_rect.x + 18 + col * 144, party_rect.y + 52 + row * 42, 126, 32)
            draw_beveled_panel(surf, rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
            if index < len(selected_ids):
                adventurer = ADVENTURERS_BY_ID[selected_ids[index]]
                lines = _wrap_text_block(adventurer.name, font_body(11, bold=True), rect.width - 18)
                draw_text(surf, lines[0] if lines else adventurer.name, font_body(11, bold=True), TEXT_SOFT, (rect.x + 8, rect.y + 6))
                draw_text(surf, "X", font_label(10, bold=True), GOLD_BRIGHT, (rect.right - 8, rect.y + 7), right=True)
                slot_buttons.append((rect, selected_ids[index]))
            else:
                draw_text(surf, "Available", font_body(13, bold=True), TEXT_MUTE, rect.center, center=True)
    if enemy_party_ids:
        draw_text(
            surf,
            "Names only",
            font_label(10, bold=True),
            TEXT_MUTE,
            (enemy_rect.x + 12, enemy_rect.y + 36),
        )
        for index, adventurer_id in enumerate(enemy_party_ids[:6]):
            adventurer = ADVENTURERS_BY_ID.get(adventurer_id)
            if adventurer is None:
                continue
            y = enemy_rect.y + 56 + index * 20
            draw_text(
                surf,
                f"{index + 1}. {adventurer.name}",
                font_body(12, bold=True),
                TEXT_SOFT,
                (enemy_rect.x + 12, y),
            )
    elif side_panel_lines:
        y = enemy_rect.y + 40
        for index, line in enumerate(side_panel_lines[:6]):
            wrapped = _wrap_text_block(line, font_body(12 if target_count <= 3 else 13, bold=index == 0), enemy_rect.width - 24)
            for wrapped_line in wrapped:
                draw_text(
                    surf,
                    wrapped_line,
                    font_body(12 if target_count <= 3 else 13, bold=index == 0),
                    GOLD_BRIGHT if index == 0 else TEXT_SOFT,
                    (enemy_rect.x + 12, y),
                )
                y += 16 if target_count <= 3 else 18
            y += 4
    else:
        draw_text(surf, "Unknown", font_label(11, bold=True), TEXT_MUTE, enemy_rect.center, center=True)
    pick_label = "Add To Party" if target_count > 3 else "Select Adventurer"
    pick_btn = pygame.Rect(detail_rect.right - 208, detail_rect.bottom - 52, 186, 36)
    continue_btn = pygame.Rect(party_rect.x + 18, party_rect.bottom - 38, party_rect.width - 36, 30)
    import_btn = pygame.Rect(enemy_rect.x, enemy_rect.y - 42, enemy_rect.width, 32)
    focus_id = focused_id if focused_id in ADVENTURERS_BY_ID else (visible_offer_ids[0] if visible_offer_ids else None)
    focused = ADVENTURERS_BY_ID[focus_id] if focus_id is not None else ADVENTURERS_BY_ID[next(iter(ADVENTURERS_BY_ID))]
    detail_viewport, detail_scroll_max = _draw_draft_detail_panel(surf, detail_rect, mouse_pos, focused, footer_rect=pick_btn, scroll=detail_scroll)
    draw_primary_button(surf, pick_btn, mouse_pos, pick_label, disabled=focus_id in selected_ids or len(selected_ids) >= target_count)
    draw_secondary_button(surf, continue_btn, mouse_pos, continue_label, active=len(selected_ids) == target_count)
    if allow_text_import:
        draw_secondary_button(surf, import_btn, mouse_pos, "Import Team Text")
    else:
        import_btn = None
    btns["back"] = btns.pop("left")
    btns["cards"] = cards
    btns["party_slots"] = slot_buttons
    btns["pick"] = pick_btn
    btns["continue"] = continue_btn
    btns["offer_scroll_max"] = max_offer_scroll
    btns["offer_page_size"] = visible_capacity
    btns["detail_viewport"] = detail_viewport
    btns["detail_scroll_max"] = detail_scroll_max
    btns["import_team"] = import_btn
    if import_open:
        btns.update(
            _draw_team_import_modal(
                surf,
                mouse_pos,
                text=import_text,
                status_lines=import_status_lines or [],
            )
        )
    return btns


def _draw_team_import_modal(surf, mouse_pos, *, text: str, status_lines: list[str]) -> dict:
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((6, 8, 14, 176))
    surf.blit(overlay, (0, 0))

    modal_rect = pygame.Rect(232, 104, 896, 634)
    draw_beveled_panel(surf, modal_rect, title="Import Team Text")

    helper_lines = [
        "Paste or type a 6-member team using 'Adventurer @ Weapon', then Class, skill line, and Artifact.",
        "Name matching ignores capitalization and spacing. Import applies only if the entire team is legal.",
    ]
    helper_y = modal_rect.y + 54
    for line in helper_lines:
        draw_text(surf, line, font_body(15), TEXT_SOFT, (modal_rect.x + 20, helper_y))
        helper_y += 20

    textbox_rect = pygame.Rect(modal_rect.x + 20, modal_rect.y + 104, modal_rect.width - 40, 404)
    draw_beveled_panel(
        surf,
        textbox_rect,
        fill_top=SURFACE_HIGH,
        fill_bottom=SURFACE_LOW,
        border=GOLD_DIM,
    )
    text_viewport = pygame.Rect(textbox_rect.x + 10, textbox_rect.y + 10, textbox_rect.width - 20, textbox_rect.height - 20)
    old_clip = surf.get_clip()
    surf.set_clip(text_viewport)
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = lines if lines else [""]
    line_height = 18
    max_lines = max(1, text_viewport.height // line_height)
    start = max(0, len(lines) - max_lines)
    y = text_viewport.y
    mono = font_body(14)
    for line in lines[start:]:
        draw_text(surf, line, mono, TEXT, (text_viewport.x, y))
        y += line_height
    surf.set_clip(old_clip)

    button_y = modal_rect.bottom - 106
    apply_btn = pygame.Rect(modal_rect.right - 220, button_y, 188, 36)
    cancel_btn = pygame.Rect(modal_rect.right - 424, button_y, 188, 36)
    clear_btn = pygame.Rect(modal_rect.x + 20, button_y, 120, 36)
    paste_btn = pygame.Rect(modal_rect.x + 152, button_y, 172, 36)
    draw_primary_button(surf, apply_btn, mouse_pos, "Import")
    draw_secondary_button(surf, cancel_btn, mouse_pos, "Cancel")
    draw_secondary_button(surf, clear_btn, mouse_pos, "Clear")
    draw_secondary_button(surf, paste_btn, mouse_pos, "Paste Clipboard")

    status_y = button_y + 46
    for line in status_lines[:3]:
        draw_text(surf, line, font_body(14), TEXT_SOFT, (modal_rect.x + 20, status_y))
        status_y += 18

    return {
        "import_apply": apply_btn,
        "import_cancel": cancel_btn,
        "import_clear": clear_btn,
        "import_paste": paste_btn,
        "import_textbox": textbox_rect,
        "import_modal_rect": modal_rect,
    }


def _active_weapon_for_member(member, *, adventurer_lookup=None):
    adventurer_lookup = adventurer_lookup or ADVENTURERS_BY_ID
    adventurer = adventurer_lookup[member["adventurer_id"]]
    weapon_id = member["primary_weapon_id"] or adventurer.signature_weapons[0].id
    return next(weapon for weapon in adventurer.signature_weapons if weapon.id == weapon_id)


def _member_index_for_slot(members, slot: str):
    for index, member in enumerate(members):
        if member["slot"] == slot:
            return index
    return None


def _secondary_weapon_for_member(member, *, adventurer_lookup=None):
    adventurer_lookup = adventurer_lookup or ADVENTURERS_BY_ID
    primary = _active_weapon_for_member(member, adventurer_lookup=adventurer_lookup)
    adventurer = adventurer_lookup[member["adventurer_id"]]
    return next((weapon for weapon in adventurer.signature_weapons if weapon.id != primary.id), primary)


def _selected_class_skill(class_name: str, class_skill_id: str | None):
    if class_skill_id and class_skill_id in CLASS_SKILLS_BY_ID:
        return CLASS_SKILLS_BY_ID[class_skill_id]
    skills = list(CLASS_SKILLS.get(class_name, []))
    if not skills:
        return None
    return next((skill for skill in skills if skill.id == class_skill_id), skills[0])


def _stat_short_label(stat_name: str) -> str:
    return {
        "hp": "HP",
        "attack": "ATK",
        "defense": "DEF",
        "speed": "SPD",
    }.get(stat_name, stat_name.title())


def _status_duration_text(status_spec) -> str:
    return f"{status_spec.kind.title()} ({status_spec.duration}r)"


def _stat_mod_text(stat_spec) -> str:
    sign = "+" if stat_spec.amount >= 0 else ""
    return f"{_stat_short_label(stat_spec.stat)} {sign}{stat_spec.amount} ({stat_spec.duration}r)"


def _effect_parts(effect):
    parts = []
    if effect.power:
        parts.append(f"{effect.power} Power")
    if effect.heal:
        parts.append(f"Heal {effect.heal}")
    if effect.cooldown:
        parts.append(f"CD {effect.cooldown}")
    if effect.ammo_cost:
        parts.append(f"Ammo {effect.ammo_cost}")
    if effect.recoil:
        parts.append(f"{int(effect.recoil * 100)}% Recoil")
    if effect.lifesteal:
        parts.append(f"{int(effect.lifesteal * 100)}% Lifesteal")
    if effect.spread:
        parts.append("Spread")
    if effect.counts_as_spell:
        parts.append("Counts as Spell")
    if effect.ignore_targeting:
        parts.append("Ignores Targeting")
    if effect.bonus_power_if_status and effect.bonus_power:
        parts.append(f"+{effect.bonus_power} vs {effect.bonus_power_if_status.title()}")
    return parts


def _effect_rule_lines(effect):
    lines = []
    if effect.target_statuses:
        lines.append(f"Target: {', '.join(_status_duration_text(status_spec) for status_spec in effect.target_statuses)}")
    if effect.self_statuses:
        lines.append(f"Self: {', '.join(_status_duration_text(status_spec) for status_spec in effect.self_statuses)}")
    if effect.target_buffs:
        lines.append(f"Target Buffs: {', '.join(_stat_mod_text(stat_spec) for stat_spec in effect.target_buffs)}")
    if effect.target_debuffs:
        lines.append(f"Target Debuffs: {', '.join(_stat_mod_text(stat_spec) for stat_spec in effect.target_debuffs)}")
    if effect.self_buffs:
        lines.append(f"Self Buffs: {', '.join(_stat_mod_text(stat_spec) for stat_spec in effect.self_buffs)}")
    return lines


def _effect_text(effect):
    parts = _effect_parts(effect)
    if effect.description:
        return f"{' | '.join(parts)} - {effect.description}" if parts else effect.description
    return " | ".join(parts) if parts else effect.name


def _weapon_detail_lines(weapon):
    lines = [f"{weapon.kind.title()} weapon"]
    if weapon.ammo:
        lines.append(f"Ammo: {weapon.ammo}")
    strike_text = _effect_text(weapon.strike)
    if strike_text:
        lines.append(f"Strike: {strike_text}")
    for extra in _effect_rule_lines(weapon.strike):
        lines.append(f"Strike: {extra}")
    for passive in weapon.passive_skills:
        lines.append(f"Skill: {passive.name} - {passive.description}")
    for spell in weapon.spells:
        lines.append(f"Spell: {spell.name} - {_effect_text(spell)}")
        for extra in _effect_rule_lines(spell):
            lines.append(f"Spell: {extra}")
    return lines


def _weapon_card_detail_lines(weapon):
    lines = []
    strike_text = _effect_text(weapon.strike)
    if strike_text:
        lines.append(f"Strike: {strike_text}")
    for passive in weapon.passive_skills:
        line = f"Skill: {passive.name}"
        if passive.description:
            line += f" - {passive.description}"
        lines.append(line)
    for spell in weapon.spells:
        spell_text = _effect_text(spell)
        line = f"Spell: {spell.name}"
        if spell_text and spell_text != spell.name:
            line += f" - {spell_text}"
        lines.append(line)
    if weapon.ammo:
        lines.append(f"Ammo: {weapon.ammo}")
    return lines


def _artifact_detail_lines(artifact):
    if artifact is None:
        return ["No artifact equipped."]
    active_effect = artifact.active_spell
    reactive_effect = artifact.reactive_effect
    lines = [
        f"Stat Bonus: +{artifact.amount} {_stat_short_label(artifact.stat)}",
        f"Attunement: {', '.join(artifact.attunement)}",
    ]
    if active_effect is not None:
        lines.append(f"Spell: {active_effect.name} - {_effect_text(active_effect)}")
        for extra in _effect_rule_lines(active_effect):
            lines.append(f"Spell: {extra}")
    if reactive_effect is not None:
        lines.append(f"Reactive Spell: {reactive_effect.name} - {_effect_text(reactive_effect)}")
        for extra in _effect_rule_lines(reactive_effect):
            lines.append(f"Reactive Spell: {extra}")
    if artifact.description:
        lines.append(artifact.description)
    return lines


def _draw_wrapped_lines(surf, lines, x, y, width, *, font, color, line_height):
    offset = 0
    mouse_pos = pygame.mouse.get_pos()
    for raw_line in lines:
        for wrapped in _wrap_text_block(raw_line, font, width):
            _draw_status_aware_line(
                surf,
                wrapped,
                x,
                y + offset,
                font_obj=font,
                base_color=color,
                mouse_pos=mouse_pos,
            )
            offset += line_height
    return offset


def _wrapped_lines_height(lines, *, font, width, line_height):
    total = 0
    for raw_line in lines:
        total += len(_wrap_text_block(raw_line, font, width)) * line_height
    return total


def _draw_info_popout(surf, source_rect: pygame.Rect, title: str, lines: list[str], *, width: int = 360, accent=None, body_font=None, line_height: int = 15):
    body_font = body_font or font_body(13)
    title_font = font_headline(18, bold=True)
    accent = accent or globals().get("UI_GOLD_BRIGHT", GOLD_BRIGHT)
    fill_top = globals().get("UI_BG_RAISED", SURFACE_HIGH)
    fill_bottom = globals().get("UI_BG_SURFACE", SURFACE_LOW)
    border = globals().get("UI_GOLD_DIM", GOLD_DIM)
    body_color = globals().get("UI_TEXT_SOFT", TEXT_SOFT)
    body_width = width - 24
    body_height = _wrapped_lines_height(lines, font=body_font, width=body_width, line_height=line_height)
    height = max(112, 18 + title_font.get_height() + 12 + body_height + 16)
    rect = _hover_popout_rect(source_rect, width, height)
    draw_beveled_panel(surf, rect, fill_top=fill_top, fill_bottom=fill_bottom, border=border)
    draw_text(surf, _ellipsize_text(title, title_font, rect.width - 24), title_font, accent, (rect.x + 12, rect.y + 12))
    _draw_wrapped_lines(
        surf,
        lines,
        rect.x + 12,
        rect.y + 40,
        rect.width - 24,
        font=body_font,
        color=body_color,
        line_height=line_height,
    )
    return rect


def _adventurer_detail_lines(adventurer, *, class_name: str | None = None, artifact_name: str | None = None, artifact=None):
    lines = [
        f"HP {adventurer.hp} | ATK {adventurer.attack} | DEF {adventurer.defense} | SPD {adventurer.speed}",
        f"Innate: {adventurer.innate.name} - {adventurer.innate.description}",
    ]
    if class_name and class_name != NO_CLASS_NAME:
        lines.append(f"Class: {class_name}")
    for index, weapon in enumerate(adventurer.signature_weapons[:2], start=1):
        lines.append(f"Weapon {index}: {weapon.name} ({weapon.kind.title()})")
        lines.extend(_weapon_detail_lines(weapon)[1:])
    lines.append(f"Ultimate: {adventurer.ultimate.name} - {_effect_text(adventurer.ultimate)}")
    lines.extend(f"Ultimate: {extra}" for extra in _effect_rule_lines(adventurer.ultimate))
    if artifact is not None:
        lines.append(f"Artifact: {artifact.name}")
        lines.extend(_artifact_detail_lines(artifact))
    elif artifact_name:
        lines.append(f"Artifact: {artifact_name}")
    return lines


def _class_detail_lines(class_name: str) -> list[str]:
    if class_name == NO_CLASS_NAME:
        return [CLASS_SUMMARIES.get(class_name, "No class selected.")]
    lines = [CLASS_SUMMARIES.get(class_name, class_name)]
    for skill in CLASS_SKILLS.get(class_name, []):
        hp_bonus = f" | +{skill.hp_bonus} HP" if skill.hp_bonus else ""
        lines.append(f"{skill.name}{hp_bonus} - {skill.description}")
    return lines


def _member_loadout_lines(member, *, adventurer_lookup=None, artifact_lookup=None) -> list[str]:
    adventurer_lookup = adventurer_lookup or ADVENTURERS_BY_ID
    artifact_lookup = artifact_lookup or ALL_ARTIFACTS_BY_ID
    adventurer = adventurer_lookup[member["adventurer_id"]]
    class_name = member.get("class_name", NO_CLASS_NAME)
    class_skill = _selected_class_skill(class_name, member.get("class_skill_id"))
    primary_weapon = _active_weapon_for_member(member, adventurer_lookup=adventurer_lookup)
    secondary_weapon = _secondary_weapon_for_member(member, adventurer_lookup=adventurer_lookup)
    artifact = artifact_lookup.get(member.get("artifact_id"))
    lines = [
        f"HP {adventurer.hp} | ATK {adventurer.attack} | DEF {adventurer.defense} | SPD {adventurer.speed}",
        f"Innate: {adventurer.innate.name} - {adventurer.innate.description}",
        f"Class: {class_name if class_name and class_name != NO_CLASS_NAME else 'Unassigned'}",
    ]
    if member.get("slot"):
        lines.append(f"Slot: {SLOT_LABELS.get(member['slot'], member['slot'])}")
    if class_skill is not None:
        hp_bonus = f" | +{class_skill.hp_bonus} HP" if class_skill.hp_bonus else ""
        lines.append(f"Class Skill: {class_skill.name}{hp_bonus} - {class_skill.description}")
    else:
        lines.append("Class Skill: None selected.")
    lines.append(f"Primary: {primary_weapon.name} ({primary_weapon.kind.title()})")
    lines.extend(_weapon_detail_lines(primary_weapon)[1:])
    if secondary_weapon.id != primary_weapon.id:
        lines.append(f"Secondary: {secondary_weapon.name} ({secondary_weapon.kind.title()})")
        lines.extend(_weapon_detail_lines(secondary_weapon)[1:])
    if artifact is not None:
        lines.append(f"Artifact: {artifact.name}")
        lines.extend(_artifact_detail_lines(artifact))
    else:
        lines.append("Artifact: None equipped.")
    return lines


def _runtime_weapon_lines(unit, weapon, *, label: str) -> list[str]:
    ammo_text = ""
    if weapon.ammo:
        ammo_text = f" | Ammo {unit.ammo_remaining.get(weapon.id, weapon.ammo)}/{weapon.ammo}"
    strike_cd = unit.cooldowns.get(weapon.strike.id, 0)
    strike_state = "Ready" if strike_cd <= 0 else f"CD {strike_cd}"
    lines = [f"{label}: {weapon.name} ({weapon.kind.title()})"]
    lines.append(f"Strike [{strike_state}{ammo_text}]: {_effect_text(weapon.strike)}")
    lines.extend(f"Strike: {extra}" for extra in _effect_rule_lines(weapon.strike))
    for passive in weapon.passive_skills:
        lines.append(f"Skill: {passive.name} - {passive.description}")
    for spell in weapon.spells:
        spell_cd = unit.cooldowns.get(spell.id, 0)
        spell_state = "Ready" if spell_cd <= 0 else f"CD {spell_cd}"
        lines.append(f"Spell: {spell.name} [{spell_state}] - {_effect_text(spell)}")
        lines.extend(f"Spell: {extra}" for extra in _effect_rule_lines(spell))
    return lines


def _combatant_loadout_lines(unit) -> list[str]:
    class_name = getattr(unit, "class_name", NO_CLASS_NAME) or NO_CLASS_NAME
    class_skill = getattr(unit, "class_skill", None)
    lines = [
        f"{SLOT_LABELS.get(getattr(unit, 'slot', ''), getattr(unit, 'slot', ''))} | HP {unit.hp}/{unit.max_hp} | ATK {unit.get_stat('attack')} | DEF {unit.get_stat('defense')} | SPD {unit.get_stat('speed')}",
        f"Innate: {unit.defn.innate.name} - {unit.defn.innate.description}",
        f"Class: {class_name if class_name != NO_CLASS_NAME else 'Unassigned'}",
    ]
    if class_skill is not None:
        hp_bonus = f" | +{class_skill.hp_bonus} HP" if class_skill.hp_bonus else ""
        lines.append(f"Class Skill: {class_skill.name}{hp_bonus} - {class_skill.description}")
    lines.extend(_runtime_weapon_lines(unit, unit.primary_weapon, label="Primary"))
    if unit.secondary_weapon.id != unit.primary_weapon.id:
        lines.extend(_runtime_weapon_lines(unit, unit.secondary_weapon, label="Secondary"))
    if unit.artifact is not None:
        artifact = unit.artifact
        active_effect = artifact.active_spell
        reactive_effect = artifact.reactive_effect
        lines.append(f"Artifact: {artifact.name}")
        lines.append(f"Stat Bonus: +{artifact.amount} {_stat_short_label(artifact.stat)}")
        lines.append(f"Attunement: {', '.join(artifact.attunement)}")
        if active_effect is not None:
            turns = unit.cooldowns.get(active_effect.id, 0)
            spell_state = f" [{'Ready' if turns <= 0 else f'CD {turns}'}]"
            lines.append(f"Spell: {active_effect.name}{spell_state} - {_effect_text(active_effect)}")
            lines.extend(f"Spell: {extra}" for extra in _effect_rule_lines(active_effect))
        if reactive_effect is not None:
            turns = unit.cooldowns.get(reactive_effect.id, 0)
            spell_state = f" [{'Ready' if turns <= 0 else f'CD {turns}'}]"
            lines.append(f"Reactive Spell: {reactive_effect.name}{spell_state} - {_effect_text(reactive_effect)}")
            lines.extend(f"Reactive Spell: {extra}" for extra in _effect_rule_lines(reactive_effect))
        if artifact.description:
            lines.append(artifact.description)
    else:
        lines.append("Artifact: None equipped.")
    active_buffs = [buff for buff in unit.buffs if buff.duration > 0]
    active_debuffs = [debuff for debuff in unit.debuffs if debuff.duration > 0]
    if active_buffs:
        lines.append(f"Buffs: {', '.join(_stat_mod_text(buff) for buff in active_buffs)}")
    if active_debuffs:
        lines.append(f"Debuffs: {', '.join(_stat_mod_text(debuff) for debuff in active_debuffs)}")
    if unit.statuses:
        lines.append(f"Conditions: {', '.join(_status_duration_text(status) for status in unit.statuses)}")
    else:
        lines.append("Conditions: None")
    lines.extend(tutorial_unit_callout_lines(getattr(unit.defn, "id", "")))
    return lines


def _visible_button_entries(entries, viewport):
    return [entry for entry in entries if entry[0] is not None and entry[0].colliderect(viewport)]


def _draw_scroll_hint(surf, viewport, scroll, scroll_max):
    if scroll_max <= 0:
        return
    track = pygame.Rect(viewport.right - 6, viewport.y + 4, 4, viewport.height - 8)
    pygame.draw.rect(surf, SURFACE_HIGH, track, border_radius=2)
    thumb_h = max(28, int(track.height * (viewport.height / (viewport.height + scroll_max))))
    ratio = 0 if scroll_max <= 0 else scroll / scroll_max
    thumb_y = track.y + int((track.height - thumb_h) * ratio)
    thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_h)
    pygame.draw.rect(surf, GOLD_BRIGHT, thumb, border_radius=2)


def _draw_draft_detail_panel(surf, rect, mouse_pos, adventurer, *, footer_rect=None, scroll: int = 0):
    draw_beveled_panel(surf, rect, title="Focused Adventurer")
    viewport_bottom = footer_rect.y - 10 if footer_rect is not None else rect.bottom - 12
    viewport = pygame.Rect(rect.x + 12, rect.y + 42, rect.width - 24, max(80, viewport_bottom - (rect.y + 42)))
    old_clip = surf.get_clip()
    surf.set_clip(viewport)

    y = rect.y + 52 - scroll
    draw_text(surf, _ellipsize_text(adventurer.name, font_headline(28, bold=True), rect.width - 44), font_headline(28, bold=True), TEXT, (rect.x + 22, y))
    y += 34
    tag_x = rect.x + 22
    for kind in _adventurer_weapon_kinds(adventurer):
        label = kind.upper()
        chip_width = max(74, font_label(11, bold=True).size(label)[0] + 20)
        chip_rect = pygame.Rect(tag_x, y, chip_width, 22)
        draw_chip(surf, chip_rect, label, _weapon_kind_color(kind))
        tag_x += chip_width + 8
    y += 38
    y += _draw_wrapped_lines(
        surf,
        [", ".join(role_tags_for_adventurer(adventurer))],
        rect.x + 22,
        y,
        rect.width - 44,
        font=font_label(11, bold=True),
        color=GOLD_BRIGHT,
        line_height=16,
    )
    y += 8
    draw_text(surf, f"HP {adventurer.hp} | ATK {adventurer.attack} | DEF {adventurer.defense} | SPD {adventurer.speed}", font_label(13, bold=True), TEXT_SOFT, (rect.x + 22, y))
    y += 34
    draw_text(surf, adventurer.innate.name, font_label(12, bold=True), GOLD_BRIGHT, (rect.x + 22, y))
    y += 22
    y += _draw_wrapped_lines(surf, [adventurer.innate.description], rect.x + 22, y, rect.width - 44, font=font_body(16), color=TEXT_SOFT, line_height=20)
    y += 14
    draw_text(surf, "Signature Weapons", font_label(12, bold=True), TEXT_MUTE, (rect.x + 22, y))
    y += 22
    for weapon in adventurer.signature_weapons:
        draw_text(surf, _ellipsize_text(weapon.name, font_body(17, bold=True), rect.width - 44), font_body(17, bold=True), TEXT, (rect.x + 22, y))
        y += 22
        y += _draw_wrapped_lines(surf, _weapon_detail_lines(weapon), rect.x + 36, y, rect.width - 58, font=font_body(14), color=TEXT_SOFT, line_height=18)
        y += 10
    draw_text(surf, f"Ultimate: {adventurer.ultimate.name}", font_body(17, bold=True), TEXT, (rect.x + 22, y))
    y += 24
    y += _draw_wrapped_lines(surf, [_effect_text(adventurer.ultimate)], rect.x + 22, y, rect.width - 44, font=font_body(15), color=TEXT_SOFT, line_height=18)
    # Keep a little extra tail room so the final lines can be comfortably
    # scrolled above the footer button and not feel clipped at the edge.
    content_bottom = y + SPACE_8
    bottom_buffer = SPACE_24 + (SPACE_16 if footer_rect is not None else 0)
    scroll_max = max(0, (content_bottom + bottom_buffer) - viewport.bottom)
    surf.set_clip(old_clip)
    _draw_scroll_hint(surf, viewport, scroll, scroll_max)
    return viewport, scroll_max


def _draw_loadout_formation_panel(surf, rect, mouse_pos, members, selected_index, *, drag_index=None, drag_hover_slot=None):
    draw_beveled_panel(surf, rect, title="Formation")
    draw_text(surf, "Drag an adventurer to another slot to swap positions.", font_body(16), TEXT_SOFT, (rect.x + 20, rect.y + 56))
    slot_rects = {
        SLOT_BACK_LEFT: pygame.Rect(rect.x + 24, rect.y + 118, 152, 188),
        SLOT_BACK_RIGHT: pygame.Rect(rect.right - 176, rect.y + 118, 152, 188),
        SLOT_FRONT: pygame.Rect(rect.centerx - 76, rect.y + 390, 152, 212),
    }
    formation_members = []
    formation_slots = []
    for slot in (SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT):
        slot_rect = slot_rects[slot]
        hovered = slot == drag_hover_slot
        draw_beveled_panel(
            surf,
            slot_rect,
            fill_top=SURFACE_HIGH if hovered else SURFACE,
            fill_bottom=SURFACE_LOW,
            border=GOLD_BRIGHT if hovered else GOLD_DIM,
        )
        draw_text(surf, SLOT_LABELS[slot], font_label(11, bold=True), GOLD_BRIGHT if hovered else TEXT_MUTE, (slot_rect.centerx, slot_rect.y + 14), center=True)
        formation_slots.append((slot_rect, slot))
        member_index = _member_index_for_slot(members, slot)
        if member_index is None:
            draw_text(surf, "Open", font_headline(24, bold=True), TEXT_MUTE, slot_rect.center, center=True)
            continue
        member = members[member_index]
        adventurer = ADVENTURERS_BY_ID[member["adventurer_id"]]
        card_rect = pygame.Rect(slot_rect.x + 10, slot_rect.y + 36, slot_rect.width - 20, slot_rect.height - 46)
        is_selected = member_index == selected_index
        draw_adventurer_card(
            surf,
            card_rect,
            mouse_pos,
            adventurer,
            selected=is_selected,
            small=True,
            tag_line="DRAGGING" if drag_index == member_index else ("SELECTED" if is_selected else adventurer.signature_weapons[0].kind.upper()),
        )
        if drag_index == member_index:
            draw_glow_rect(surf, slot_rect, GOLD_BRIGHT, alpha=48)
        formation_members.append((card_rect, member_index, slot))
    return formation_members, formation_slots


def _draw_loadout_detail_panel(
    surf,
    rect,
    mouse_pos,
    members,
    selected_index,
    *,
    allowed_artifact_ids=None,
    scroll: int = 0,
    header_label: str | None = None,
    editable: bool = True,
):
    draw_beveled_panel(surf, rect, title="Adventurer Detail")
    buttons = {
        "weapon_prev": None,
        "weapon_next": None,
        "classes": [],
        "skills": [],
        "artifacts": [],
        "viewport": pygame.Rect(rect.x + 12, rect.y + 42, rect.width - 24, rect.height - 54),
        "scroll_max": 0,
    }
    if not members:
        draw_text(surf, "Select an adventurer to begin.", font_headline(24, bold=True), TEXT, (rect.x + 24, rect.y + 72))
        return buttons

    viewport = buttons["viewport"]
    old_clip = surf.get_clip()
    surf.set_clip(viewport)
    selected_index = max(0, min(selected_index, len(members) - 1))
    member = members[selected_index]
    adventurer = ADVENTURERS_BY_ID[member["adventurer_id"]]
    selected_weapon = _active_weapon_for_member(member)
    class_name = member.get("class_name", NO_CLASS_NAME)
    if class_name not in CLASS_ORDER:
        class_name = NO_CLASS_NAME
    skills = list(CLASS_SKILLS.get(class_name, []))
    current_skill = None
    if skills:
        current_skill = next(
            (skill for skill in skills if skill.id == member.get("class_skill_id")),
            skills[0],
        )
    artifact_ids = compatible_artifact_ids(class_name, allowed_artifact_ids)
    current_artifact = ALL_ARTIFACTS_BY_ID.get(member.get("artifact_id"))
    used_by_others = {
        other.get("artifact_id")
        for index, other in enumerate(members)
        if index != selected_index and other.get("artifact_id") is not None
    }

    y0 = rect.y + 54 - scroll
    draw_text(surf, _ellipsize_text(adventurer.name, font_headline(30, bold=True), rect.width - 44), font_headline(30, bold=True), TEXT, (rect.x + 22, y0))
    label_text = header_label or SLOT_LABELS.get(member.get("slot"), "Unassigned")
    draw_text(
        surf,
        f"{label_text} | HP {adventurer.hp} | ATK {adventurer.attack} | DEF {adventurer.defense} | SPD {adventurer.speed}",
        font_body(16, bold=True),
        TEXT_SOFT,
        (rect.x + 22, y0 + 38),
    )
    draw_text(surf, adventurer.innate.name, font_label(11, bold=True), GOLD_BRIGHT, (rect.x + 22, y0 + 70))
    innate_height = _draw_wrapped_lines(surf, [adventurer.innate.description], rect.x + 22, y0 + 92, rect.width - 44, font=font_body(15), color=TEXT_SOFT, line_height=20)

    weapon_detail_lines = _weapon_detail_lines(selected_weapon)
    weapon_detail_height = _wrapped_lines_height(
        weapon_detail_lines,
        font=font_body(14),
        width=rect.width - 76,
        line_height=18,
    )
    weapon_panel_height = max(150, 108 + weapon_detail_height + 12)
    weapon_panel = pygame.Rect(rect.x + 22, y0 + 92 + innate_height + 16, rect.width - 44, weapon_panel_height)
    draw_beveled_panel(surf, weapon_panel, title="Primary Weapon" if editable else "Locked Weapon")
    weapon_name_x = weapon_panel.x + 16
    if editable:
        prev_rect = pygame.Rect(weapon_panel.x + 10, weapon_panel.y + 48, 34, 34)
        next_rect = pygame.Rect(weapon_panel.right - 44, weapon_panel.y + 48, 34, 34)
        draw_secondary_button(surf, prev_rect, mouse_pos, "<")
        draw_secondary_button(surf, next_rect, mouse_pos, ">")
        buttons["weapon_prev"] = prev_rect
        buttons["weapon_next"] = next_rect
        weapon_name_x = weapon_panel.x + 56
    draw_text(surf, selected_weapon.name, font_headline(24, bold=True), TEXT, (weapon_name_x, weapon_panel.y + 48))
    draw_text(
        surf,
        f"Alternate: {next(weapon.name for weapon in adventurer.signature_weapons if weapon.id != selected_weapon.id)}",
        font_body(15),
        TEXT_MUTE,
        (weapon_name_x, weapon_panel.y + 80),
    )
    _draw_wrapped_lines(surf, weapon_detail_lines, weapon_panel.x + 16, weapon_panel.y + 108, weapon_panel.width - 32, font=font_body(14), color=TEXT_SOFT, line_height=18)

    class_y = weapon_panel.bottom + 18
    draw_text(surf, "Class", font_label(11, bold=True), TEXT_MUTE, (rect.x + 22, class_y))
    class_buttons = []
    class_button_width = 76
    class_names = list(CLASS_ORDER)
    class_rows = max(1, (len(class_names) + 2) // 3)
    if not editable:
        class_rows = 1
    if editable:
        for index, cls_name in enumerate(class_names):
            row = index // 3
            col = index % 3
            cls_rect = pygame.Rect(rect.x + 22 + col * 84, class_y + 18 + row * 42, class_button_width, 32)
            draw_secondary_button(surf, cls_rect, mouse_pos, cls_name, active=cls_name == class_name)
            class_buttons.append((cls_rect, cls_name))
    else:
        class_rect = pygame.Rect(rect.x + 22, class_y + 18, 188, 32)
        draw_secondary_button(surf, class_rect, mouse_pos, class_name, active=True)
    buttons["classes"] = class_buttons
    class_summary_y = class_y + 18 + class_rows * 42 + 4
    class_summary_height = _draw_wrapped_lines(surf, [CLASS_SUMMARIES.get(class_name, "")], rect.x + 22, class_summary_y, rect.width - 44, font=font_body(14), color=TEXT_SOFT, line_height=18)

    skill_label_y = class_summary_y + max(24, class_summary_height) + 8
    draw_text(surf, "Class Skill", font_label(11, bold=True), TEXT_MUTE, (rect.x + 22, skill_label_y))
    skill_buttons = []
    hovered_skill = None
    skill_preview = None
    if editable and skills and current_skill is not None:
        skill_width = (rect.width - 64) // 3
        for index, skill in enumerate(skills):
            skill_rect = pygame.Rect(rect.x + 22 + index * (skill_width + 10), skill_label_y + 18, skill_width, 44)
            draw_secondary_button(surf, skill_rect, mouse_pos, skill.name, active=skill.id == current_skill.id)
            skill_buttons.append((skill_rect, skill.id))
            if skill_rect.collidepoint(mouse_pos):
                hovered_skill = skill
        skill_preview = hovered_skill or current_skill
        skill_body_height = _wrapped_lines_height(
            [skill_preview.description],
            font=font_body(14),
            width=rect.width - 72,
            line_height=18,
        )
        skill_detail_height = max(76, 38 + skill_body_height + 12)
    elif current_skill is not None:
        skill_preview = current_skill
        skill_body_height = _wrapped_lines_height(
            [skill_preview.description],
            font=font_body(14),
            width=rect.width - 72,
            line_height=18,
        )
        skill_detail_height = max(76, 38 + skill_body_height + 12)
    else:
        skill_body_height = _wrapped_lines_height(
            ["No class skill available until a class is selected."],
            font=font_body(14),
            width=rect.width - 72,
            line_height=18,
        )
        skill_detail_height = max(76, 38 + skill_body_height + 12)
    skill_detail_rect = pygame.Rect(rect.x + 22, skill_label_y + 74, rect.width - 44, skill_detail_height)
    draw_beveled_panel(surf, skill_detail_rect, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    buttons["skills"] = skill_buttons
    if skill_preview is not None:
        draw_text(surf, skill_preview.name, font_body(17, bold=True), GOLD_BRIGHT, (skill_detail_rect.x + 14, skill_detail_rect.y + 14))
        _draw_wrapped_lines(surf, [skill_preview.description], skill_detail_rect.x + 14, skill_detail_rect.y + 38, skill_detail_rect.width - 28, font=font_body(14), color=TEXT_SOFT, line_height=18)
    else:
        draw_text(surf, "No Class Skill", font_body(17, bold=True), TEXT_MUTE, (skill_detail_rect.x + 14, skill_detail_rect.y + 14))
        _draw_wrapped_lines(
            surf,
            ["No class skill available until a class is selected."],
            skill_detail_rect.x + 14,
            skill_detail_rect.y + 38,
            skill_detail_rect.width - 28,
            font=font_body(14),
            color=TEXT_SOFT,
            line_height=18,
        )

    artifact_label_y = skill_detail_rect.bottom + 18
    draw_text(surf, "Artifact", font_label(11, bold=True), TEXT_MUTE, (rect.x + 22, artifact_label_y))
    artifact_buttons = []
    hovered_artifact = None
    artifact_entry_count = 1
    if editable:
        artifact_entries: list[tuple[str | None, str]] = [(None, "No Artifact")]
        artifact_entries.extend((artifact_id, ARTIFACTS_BY_ID[artifact_id].name) for artifact_id in artifact_ids)
        artifact_entry_count = len(artifact_entries)
        for index, (artifact_id, label) in enumerate(artifact_entries):
            row = index // 2
            col = index % 2
            art_rect = pygame.Rect(rect.x + 22 + col * 228, artifact_label_y + 18 + row * 38, 218, 30)
            locked = artifact_id is not None and artifact_id in used_by_others
            active = artifact_id == member.get("artifact_id") or (artifact_id is None and member.get("artifact_id") is None)
            draw_secondary_button(surf, art_rect, mouse_pos, label, active=active and not locked)
            if locked:
                draw_text(surf, "TAKEN", font_label(10, bold=True), EMBER, (art_rect.right - 10, art_rect.y + 9), right=True)
            artifact_buttons.append((art_rect, artifact_id, locked))
            if artifact_id is not None and art_rect.collidepoint(mouse_pos):
                hovered_artifact = ARTIFACTS_BY_ID[artifact_id]
    buttons["artifacts"] = artifact_buttons
    artifact_preview = hovered_artifact or current_artifact or (ARTIFACTS_BY_ID[artifact_ids[0]] if artifact_ids else None)
    artifact_rows = max(1, (artifact_entry_count + 1) // 2)
    artifact_list_bottom = artifact_label_y + 18 + artifact_rows * 38
    artifact_detail_lines = _artifact_detail_lines(artifact_preview)
    artifact_detail_height = _wrapped_lines_height(
        artifact_detail_lines,
        font=font_body(13),
        width=rect.width - 72,
        line_height=16,
    )
    artifact_panel_height = max(104, 36 + artifact_detail_height + 12)
    artifact_detail_rect = pygame.Rect(rect.x + 22, artifact_list_bottom + 12, rect.width - 44, artifact_panel_height)
    draw_beveled_panel(surf, artifact_detail_rect, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    preview_name = artifact_preview.name if artifact_preview is not None else "No artifact selected"
    draw_text(surf, preview_name, font_body(17, bold=True), GOLD_BRIGHT if artifact_preview is not None else TEXT_MUTE, (artifact_detail_rect.x + 14, artifact_detail_rect.y + 12))
    _draw_wrapped_lines(surf, artifact_detail_lines, artifact_detail_rect.x + 14, artifact_detail_rect.y + 36, artifact_detail_rect.width - 28, font=font_body(13), color=TEXT_SOFT, line_height=16)
    content_bottom = artifact_detail_rect.bottom + SPACE_16
    buttons["scroll_max"] = max(0, (content_bottom + SPACE_24) - viewport.bottom)
    surf.set_clip(old_clip)
    _draw_scroll_hint(surf, viewport, scroll, buttons["scroll_max"])
    buttons["weapon_prev"] = buttons["weapon_prev"] if buttons["weapon_prev"] is not None and buttons["weapon_prev"].colliderect(viewport) else None
    buttons["weapon_next"] = buttons["weapon_next"] if buttons["weapon_next"] is not None and buttons["weapon_next"].colliderect(viewport) else None
    buttons["classes"] = _visible_button_entries(buttons["classes"], viewport)
    buttons["skills"] = _visible_button_entries(buttons["skills"], viewport)
    buttons["artifacts"] = _visible_button_entries(buttons["artifacts"], viewport)
    return buttons


def _draw_loadout_summary_panel(surf, rect, summary_blocks, waiting_note, mouse_pos, confirm_label, confirm_disabled, *, scroll: int = 0):
    draw_beveled_panel(surf, rect, title="Loadout Summary")
    viewport = pygame.Rect(rect.x + 12, rect.y + 42, rect.width - 24, rect.height - 124)
    old_clip = surf.get_clip()
    surf.set_clip(viewport)
    y = rect.y + 60 - scroll
    for title, lines in summary_blocks:
        draw_text(surf, title, font_label(11, bold=True), TEXT_MUTE, (rect.x + 18, y))
        y += 24
        for line in lines:
            y += _draw_wrapped_lines(surf, [line], rect.x + 18, y, rect.width - 36, font=font_body(15), color=TEXT_SOFT, line_height=20)
            y += 6
        y += 8
    if waiting_note:
        wait_rect = pygame.Rect(rect.x + 18, y + 8, rect.width - 36, 76)
        draw_beveled_panel(surf, wait_rect, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
        _draw_wrapped_lines(surf, [waiting_note], wait_rect.x + 12, wait_rect.y + 12, wait_rect.width - 24, font=font_body(14), color=GOLD_BRIGHT, line_height=18)
        y = wait_rect.bottom + 12
    content_bottom = y
    scroll_max = max(0, content_bottom - viewport.bottom)
    surf.set_clip(old_clip)
    _draw_scroll_hint(surf, viewport, scroll, scroll_max)
    confirm_rect = pygame.Rect(rect.x + 18, rect.bottom - 72, rect.width - 36, 44)
    draw_primary_button(surf, confirm_rect, mouse_pos, confirm_label, disabled=confirm_disabled)
    return confirm_rect, viewport, scroll_max


def draw_quest_party_loadout(surf, mouse_pos, party_state, selected_index, *, detail_scroll: int = 0):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Party Loadouts",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Set weapon, class, class skill, and artifact for all six before encounter prep.",
    )
    members = list(party_state.get("team1", []))
    left_rect = pygame.Rect(40, 104, 388, 744)
    center_rect = pygame.Rect(452, 104, 604, 744)
    right_rect = pygame.Rect(1080, 104, 276, 744)
    draw_beveled_panel(surf, left_rect, title="Quest Party")
    draw_beveled_panel(surf, right_rect, title="Party Rules")

    member_buttons = []
    if not members:
        draw_text(surf, "No adventurers are assigned to this quest yet.", font_body(18, bold=True), TEXT_SOFT, (left_rect.x + 22, left_rect.y + 64))
    else:
        selected_index = max(0, min(selected_index, len(members) - 1))
        for index, member in enumerate(members[:6]):
            adventurer = ADVENTURERS_BY_ID.get(member["adventurer_id"])
            if adventurer is None:
                continue
            rect = pygame.Rect(left_rect.x + 18, left_rect.y + 54 + index * 112, left_rect.width - 36, 96)
            draw_beveled_panel(
                surf,
                rect,
                fill_top=SURFACE_HIGH if index == selected_index or rect.collidepoint(mouse_pos) else SURFACE,
                fill_bottom=SURFACE_LOW,
                border=GOLD_BRIGHT if index == selected_index else (PARCHMENT if rect.collidepoint(mouse_pos) else GOLD_DIM),
            )
            weapon_id = member.get("primary_weapon_id") or adventurer.signature_weapons[0].id
            weapon = next((item for item in adventurer.signature_weapons if item.id == weapon_id), adventurer.signature_weapons[0])
            artifact_name = ALL_ARTIFACTS_BY_ID[member["artifact_id"]].name if member.get("artifact_id") in ALL_ARTIFACTS_BY_ID else "No Artifact"
            draw_text(surf, _ellipsize_text(adventurer.name, font_body(18, bold=True), rect.width - 32), font_body(18, bold=True), TEXT, (rect.x + 16, rect.y + 16))
            loadout_line = f"{member.get('class_name', NO_CLASS_NAME)} | {weapon.name}"
            draw_text(surf, _ellipsize_text(loadout_line, font_body(13, bold=True), rect.width - 32), font_body(13, bold=True), GOLD_BRIGHT if index == selected_index else TEXT_SOFT, (rect.x + 16, rect.y + 46))
            draw_text(surf, _ellipsize_text(artifact_name, font_body(12), rect.width - 32), font_body(12), TEXT_MUTE, (rect.x + 16, rect.y + 68))
            member_buttons.append((rect, index))

    allowed_raw = party_state.get("team1_allowed_artifact_ids", None)
    detail_buttons = _draw_loadout_detail_panel(
        surf,
        center_rect,
        mouse_pos,
        members,
        selected_index,
        allowed_artifact_ids=None if allowed_raw is None else set(allowed_raw),
        scroll=detail_scroll,
        header_label=f"Party Member {selected_index + 1} of {len(members)}" if members else "Party Member",
        editable=True,
    )

    info_lines = [
        "Non-empty classes must be unique across all six adventurers.",
        "Artifacts are optional and cannot be duplicated across the party.",
        "Prepare Encounter reveals enemy names, then you choose 3.",
        "Encounter picks inherit the loadouts locked here.",
    ]
    info_y = right_rect.y + 62
    for index, line in enumerate(info_lines):
        wrapped = _wrap_text_block(line, font_body(15, bold=index == 0), right_rect.width - 36)
        _draw_wrapped_lines(
            surf,
            wrapped,
            right_rect.x + 18,
            info_y,
            right_rect.width - 36,
            font=font_body(15, bold=index == 0),
            color=GOLD_BRIGHT if index == 0 else TEXT_SOFT,
            line_height=20,
        )
        info_y += len(wrapped) * 20 + 18

    done_btn = pygame.Rect(right_rect.x + 18, right_rect.bottom - 56, right_rect.width - 36, 40)
    draw_primary_button(surf, done_btn, mouse_pos, "Done")
    btns["back"] = btns.pop("left")
    btns["members"] = member_buttons
    btns["weapon_prev"] = detail_buttons["weapon_prev"]
    btns["weapon_next"] = detail_buttons["weapon_next"]
    btns["classes"] = detail_buttons["classes"]
    btns["skills"] = detail_buttons["skills"]
    btns["artifacts"] = detail_buttons["artifacts"]
    btns["done"] = done_btn
    btns["detail_viewport"] = detail_buttons["viewport"]
    btns["detail_scroll_max"] = detail_buttons["scroll_max"]
    return btns


def draw_quest_loadout(
    surf,
    mouse_pos,
    setup_state,
    selected_index,
    *,
    player_team_num: int = 1,
    waiting_note: str = "",
    drag_state: dict | None = None,
    detail_scroll: int = 0,
    summary_scroll: int = 0,
    editable_loadout: bool = True,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Encounter Loadout Confirm" if editable_loadout else "Encounter Formation Confirm",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Lock weapon, class, class skill, artifact, and formation for this encounter"
        if editable_loadout
        else "Rival names are revealed. Choose formation only; loadouts are already locked.",
    )
    members = setup_state[f"team{player_team_num}"]
    left_rect = pygame.Rect(44, 104, 408, 744)
    center_rect = pygame.Rect(476, 104, 540, 744)
    right_rect = pygame.Rect(1040, 104, 316, 744)
    selected_index = max(0, min(selected_index, len(members) - 1)) if members else 0
    formation_members, formation_slots = _draw_loadout_formation_panel(
        surf,
        left_rect,
        mouse_pos,
        members,
        selected_index,
        drag_index=None if drag_state is None else drag_state.get("member_index"),
        drag_hover_slot=None if drag_state is None else drag_state.get("hover_slot"),
    )
    allowed_raw = setup_state.get(f"team{player_team_num}_allowed_artifact_ids", None)
    detail_buttons = _draw_loadout_detail_panel(
        surf,
        center_rect,
        mouse_pos,
        members,
        selected_index,
        allowed_artifact_ids=None if allowed_raw is None else set(allowed_raw),
        scroll=detail_scroll,
        editable=editable_loadout,
    )
    summary_blocks = [
        ("Role Summary", [quest_role_summary(members)]),
        ("Warnings", quest_warnings(members)),
        ("Quick Notes", recommendation_notes(members)),
    ]
    confirm_btn, summary_viewport, summary_scroll_max = _draw_loadout_summary_panel(
        surf,
        right_rect,
        summary_blocks,
        waiting_note,
        mouse_pos,
        "Confirm Loadouts" if editable_loadout else "Confirm Formation",
        len(members) != 3,
        scroll=summary_scroll,
    )
    btns["back"] = btns.pop("left")
    btns["formation_members"] = formation_members
    btns["formation_slots"] = formation_slots
    btns["weapon_prev"] = detail_buttons["weapon_prev"]
    btns["weapon_next"] = detail_buttons["weapon_next"]
    btns["classes"] = detail_buttons["classes"]
    btns["skills"] = detail_buttons["skills"]
    btns["artifacts"] = detail_buttons["artifacts"]
    btns["confirm"] = confirm_btn
    btns["detail_viewport"] = detail_buttons["viewport"]
    btns["detail_scroll_max"] = detail_buttons["scroll_max"]
    btns["summary_viewport"] = summary_viewport
    btns["summary_scroll_max"] = summary_scroll_max
    return btns


def draw_bouts_menu(surf, mouse_pos):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Bouts",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    card_rect = pygame.Rect(290, 160, 820, 460)
    draw_beveled_panel(surf, card_rect, title="Modes")
    btn_w = card_rect.width - 116
    random_rect = pygame.Rect(card_rect.x + 58, card_rect.y + 72, btn_w, 88)
    focused_rect = pygame.Rect(card_rect.x + 58, card_rect.y + 192, btn_w, 88)
    lan_rect = pygame.Rect(card_rect.x + 58, card_rect.y + 316, btn_w, 88)
    draw_primary_button(surf, random_rect, mouse_pos, "Random Bout")
    draw_secondary_button(surf, focused_rect, mouse_pos, "Focused Bout")
    draw_secondary_button(surf, lan_rect, mouse_pos, "LAN")
    draw_text(surf, "Draft from a shared pool of 9 adventurers. Adapt to what your opponent leaves.", font_body(15), TEXT_SOFT, (random_rect.x + 16, random_rect.y + 52))
    draw_text(surf, "Select from your full roster. Bring the team you know.", font_body(15), TEXT_SOFT, (focused_rect.x + 16, focused_rect.y + 52))
    draw_text(surf, "Bout against a local opponent over LAN.", font_body(15), TEXT_SOFT, (lan_rect.x + 16, lan_rect.y + 52))
    btns["back"] = btns.pop("left")
    btns["vs_random"] = random_rect
    btns["vs_focused"] = focused_rect
    btns["vs_lan"] = lan_rect
    return btns


def draw_bout_lobby(surf, mouse_pos, p1_ready: bool, p2_ready: bool, *, player_seat: int = 1, opponent_mode: str = "ai", status_lines: list[str] | None = None):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Bout Lobby",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    p1_rect = pygame.Rect(122, 170, 420, 360)
    p2_rect = pygame.Rect(858, 170, 420, 360)
    rules_rect = pygame.Rect(430, 572, 540, 188)
    begin_btn = pygame.Rect(1010, 678, 268, 44)
    rival_label = "LAN Rival" if opponent_mode == "lan" else "AI Rival"
    draw_beveled_panel(surf, p1_rect, title="Player 1 - You" if player_seat == 1 else f"Player 1 - {rival_label}")
    draw_beveled_panel(surf, p2_rect, title="Player 2 - You" if player_seat == 2 else f"Player 2 - {rival_label}")
    draw_beveled_panel(surf, rules_rect, title="Status")
    ready1 = pygame.Rect(p1_rect.x + 28, p1_rect.bottom - 60, p1_rect.width - 56, 40)
    ready2 = pygame.Rect(p2_rect.x + 28, p2_rect.bottom - 60, p2_rect.width - 56, 40)
    draw_text(surf, "Draft Order", font_label(12, bold=True), TEXT_MUTE, (rules_rect.x + 24, rules_rect.y + 66))
    draw_text(surf, "Shared pool of 9. Picks alternate until both sides have 3.", font_body(18), TEXT_SOFT, (rules_rect.x + 24, rules_rect.y + 96))
    seat_note = "You draft second and gain the round-one bonus swap." if player_seat == 2 else "The rival drafts second and gains the round-one bonus swap."
    draw_text(surf, seat_note, font_body(17), GOLD_BRIGHT, (rules_rect.x + 24, rules_rect.y + 138))
    for index, line in enumerate((status_lines or [])[:2]):
        draw_text(surf, line, font_body(16), TEXT_SOFT, (rules_rect.x + 24, rules_rect.y + 176 + index * 22))
    draw_secondary_button(surf, ready1, mouse_pos, "Ready" if p1_ready else "Mark Ready", active=p1_ready)
    draw_secondary_button(surf, ready2, mouse_pos, "Ready" if p2_ready else "Mark Ready", active=p2_ready)
    draw_primary_button(surf, begin_btn, mouse_pos, "Begin Draft", disabled=not (p1_ready and p2_ready))
    btns["back"] = btns.pop("left")
    btns["ready1"] = ready1
    btns["ready2"] = ready2
    btns["begin"] = begin_btn
    return btns


def draw_bout_adapt(
    surf,
    mouse_pos,
    artifact_options: list,
    player_party: list,
    recruit_options: list | None = None,
    *,
    wins: int = 0,
    losses: int = 0,
):
    """Random Bout adapt phase: choose an artifact, recruit, or pass."""
    draw_background(surf)
    series = f"{wins}–{losses}"
    btns = draw_top_bar(
        surf,
        "Adapt Phase",
        mouse_pos,
        left_icon=None,
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=f"Series: {series}  |  Add an artifact, recruit, or pass.",
    )

    # Left info panel — current party + pool
    info_panel = pygame.Rect(60, 110, 380, 660)
    draw_beveled_panel(surf, info_panel, title="Your Party (6)")
    for idx, adv_id in enumerate(player_party[:6]):
        adv = ADVENTURERS_BY_ID.get(adv_id)
        name = adv.name if adv else adv_id
        draw_text(surf, name, font_body(16), TEXT_SOFT, (info_panel.x + 24, info_panel.y + 58 + idx * 28))

    # Right panel — artifact and recruit choices
    art_panel = pygame.Rect(470, 110, 820, 660)
    draw_beveled_panel(surf, art_panel, title="Choose One Upgrade")
    artifact_choices = []
    recruit_choices = []
    card_h = 124
    card_gap = 24
    card_w = (art_panel.width - 84) // 2
    artifact_x = art_panel.x + 20
    recruit_x = artifact_x + card_w + 24
    draw_text(surf, "Artifacts", font_body(16, bold=True), GOLD_BRIGHT, (artifact_x, art_panel.y + 24))
    draw_text(surf, "Recruits", font_body(16, bold=True), GOLD_BRIGHT, (recruit_x, art_panel.y + 24))
    for idx, artifact_id in enumerate(artifact_options[:3]):
        artifact = ALL_ARTIFACTS_BY_ID.get(artifact_id)
        rect = pygame.Rect(artifact_x, art_panel.y + 52 + idx * (card_h + card_gap), card_w, card_h)
        hovered = rect.collidepoint(mouse_pos)
        draw_beveled_panel(surf, rect, border=GOLD_BRIGHT if hovered else GOLD_DIM)
        if hovered:
            draw_glow_rect(surf, rect, GOLD_BRIGHT, alpha=24)
        name = artifact.name if artifact else artifact_id
        draw_text(surf, name, font_headline(20, bold=True), TEXT, (rect.x + 18, rect.y + 22))
        if artifact:
            attune_text = ", ".join(artifact.attunement) if artifact.attunement else "—"
            draw_text(surf, f"Attunement: {attune_text}", font_body(15), TEXT_SOFT, (rect.x + 18, rect.y + 58))
        draw_text(surf, "Add to artifact pool.", font_body(15), TEXT_MUTE, (rect.x + 18, rect.y + 86))
        artifact_choices.append((rect, artifact_id))
    for idx, adventurer_id in enumerate((recruit_options or [])[:3]):
        adventurer = ADVENTURERS_BY_ID.get(adventurer_id)
        rect = pygame.Rect(recruit_x, art_panel.y + 52 + idx * (card_h + card_gap), card_w, card_h)
        hovered = rect.collidepoint(mouse_pos)
        draw_beveled_panel(surf, rect, border=GOLD_BRIGHT if hovered else GOLD_DIM)
        if hovered:
            draw_glow_rect(surf, rect, GOLD_BRIGHT, alpha=24)
        name = adventurer.name if adventurer else adventurer_id
        draw_text(surf, name, font_headline(20, bold=True), TEXT, (rect.x + 18, rect.y + 22))
        if adventurer:
            stats_text = f"HP {adventurer.hp}  ATK {adventurer.attack}  DEF {adventurer.defense}  SPD {adventurer.speed}"
            draw_text(surf, stats_text, font_body(14), TEXT_SOFT, (rect.x + 18, rect.y + 58))
        draw_text(surf, "Replace one party member, then retune loadouts.", font_body(14), TEXT_MUTE, (rect.x + 18, rect.y + 86))
        recruit_choices.append((rect, adventurer_id))

    # Skip / pass button
    skip_btn = pygame.Rect(470, 800, 820, 46)
    draw_secondary_button(surf, skip_btn, mouse_pos, "Pass — No Change")
    btns["artifact_choices"] = artifact_choices
    btns["recruit_choices"] = recruit_choices
    btns["skip"] = skip_btn
    return btns


def draw_bout_draft(surf, mouse_pos, pool_ids, focused_id, team1_ids, team2_ids, current_player, *, player_seat: int = 1, detail_scroll: int = 0, mode_id: str = "random"):
    draw_background(surf)
    screen_title = "Focused Bout — Roster Selection" if mode_id == "focused" else "Bout Draft"
    target_picks = 6 if mode_id == "focused" else 3
    player_ids = team1_ids if player_seat == 1 else team2_ids
    if current_player == player_seat:
        pick_subtitle = f"Your Pick  ({len(player_ids)}/{target_picks})"
    else:
        ai_ids = team2_ids if player_seat == 1 else team1_ids
        pick_subtitle = f"AI Rival Picking...  ({len(ai_ids)}/{target_picks})"
    btns = draw_top_bar(
        surf,
        screen_title,
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=pick_subtitle,
    )
    def draw_compact_pick_tile(rect, adventurer, *, drafted_label="DRAFTED"):
        base, accent = _portrait_palette(adventurer)
        draw_beveled_panel(
            surf,
            rect,
            fill_top=_lerp_color(SURFACE_HIGH, base, 0.22),
            fill_bottom=SURFACE_LOW,
            border=GOLD_DIM,
        )
        banner_rect = pygame.Rect(rect.x + 8, rect.y + 8, rect.width - 16, 36)
        fill_gradient(surf, banner_rect, _lerp_color(base, accent, 0.28), SBG_DEEP)
        pygame.draw.rect(surf, (255, 255, 255, 24), banner_rect, 1, border_radius=8)
        initials = "".join(part[0] for part in adventurer.name.split()[:2]).upper()
        draw_text(surf, initials, font_headline(22, bold=True), PARCHMENT, banner_rect.center, center=True)
        draw_text(
            surf,
            _ellipsize_text(adventurer.name, font_body(15, bold=True), rect.width - 18),
            font_body(15, bold=True),
            TEXT,
            (rect.x + 10, rect.y + 52),
        )
        role_text = _ellipsize_text(", ".join(role_tags_for_adventurer(adventurer)[:2]), font_label(9, bold=True), rect.width - 18)
        draw_text(surf, role_text, font_label(9, bold=True), GOLD_BRIGHT, (rect.x + 10, rect.y + 70))
        draw_text(
            surf,
            f"HP {adventurer.hp}  ATK {adventurer.attack}  DEF {adventurer.defense}  SPD {adventurer.speed}",
            font_label(9, bold=True),
            TEXT_SOFT,
            (rect.x + 10, rect.bottom - 18),
        )
        draw_text(surf, drafted_label, font_label(9, bold=True), TEXT_MUTE, (rect.right - 10, rect.y + 52), right=True)

    pick_pool = []
    for index, adventurer_id in enumerate(pool_ids):
        adventurer = ADVENTURERS_BY_ID[adventurer_id]
        row = index // 3
        col = index % 3
        rect = pygame.Rect(366 + col * 188, 110 + row * 174, 172, 156)
        unavailable = adventurer_id in team1_ids or adventurer_id in team2_ids
        pick_pool.append((draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=focused_id == adventurer_id, unavailable=unavailable, small=True), adventurer_id))
    slots_per_side = target_picks
    slot_h = min(100, (720 - 60) // slots_per_side - 8)
    side_panel_h = 60 + slots_per_side * (slot_h + 8)
    side_panel = pygame.Rect(24, 104, 316, side_panel_h)
    enemy_panel = pygame.Rect(1060, 104, 316, side_panel_h)
    detail_y = min(side_panel.bottom + 12, 612)
    detail_rect = pygame.Rect(240, detail_y, 800, 244)
    draw_beveled_panel(surf, side_panel, title="Player 1 - You" if player_seat == 1 else "Player 1 - AI Rival")
    draw_beveled_panel(surf, enemy_panel, title="Player 2 - You" if player_seat == 2 else "Player 2 - AI Rival")
    for index in range(slots_per_side):
        rect = pygame.Rect(side_panel.x + 18, side_panel.y + 54 + index * (slot_h + 8), side_panel.width - 36, slot_h)
        if index < len(team1_ids):
            draw_compact_pick_tile(rect, ADVENTURERS_BY_ID[team1_ids[index]])
        else:
            draw_beveled_panel(surf, rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
            draw_text(surf, "Open Slot", font_label(12, bold=True), TEXT_MUTE, rect.center, center=True)
    for index in range(slots_per_side):
        rect = pygame.Rect(enemy_panel.x + 18, enemy_panel.y + 54 + index * (slot_h + 8), enemy_panel.width - 36, slot_h)
        if index < len(team2_ids):
            draw_compact_pick_tile(rect, ADVENTURERS_BY_ID[team2_ids[index]])
        else:
            draw_beveled_panel(surf, rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
            draw_text(surf, "Open Slot", font_label(12, bold=True), TEXT_MUTE, rect.center, center=True)
    draft_btn = pygame.Rect(detail_rect.right - 190, detail_rect.bottom - 44, 168, 32)
    max_total = slots_per_side * 2
    can_pick = focused_id not in team1_ids and focused_id not in team2_ids and len(team1_ids) + len(team2_ids) < max_total
    focused = ADVENTURERS_BY_ID[focused_id]
    draw_beveled_panel(surf, detail_rect, title="Focused Adventurer")
    detail_viewport = pygame.Rect(detail_rect.x + 18, detail_rect.y + 50, detail_rect.width - 214, detail_rect.height - 74)
    detail_scroll_max = 0
    old_clip = surf.get_clip()
    surf.set_clip(detail_viewport)
    y = detail_viewport.y
    draw_text(
        surf,
        _ellipsize_text(focused.name, font_headline(26, bold=True), detail_viewport.width),
        font_headline(26, bold=True),
        TEXT,
        (detail_viewport.x, y),
    )
    y += 34
    tag_x = detail_viewport.x
    for kind in _adventurer_weapon_kinds(focused):
        label = kind.upper()
        chip_width = max(66, font_label(10, bold=True).size(label)[0] + 16)
        chip_rect = pygame.Rect(tag_x, y, chip_width, 20)
        draw_chip(surf, chip_rect, label, _weapon_kind_color(kind))
        tag_x += chip_width + 8
    y += 28
    draw_text(
        surf,
        f"HP {focused.hp} | ATK {focused.attack} | DEF {focused.defense} | SPD {focused.speed}",
        font_label(12, bold=True),
        TEXT_SOFT,
        (detail_viewport.x, y),
    )
    y += 22
    role_line = _ellipsize_text(", ".join(role_tags_for_adventurer(focused)), font_label(10, bold=True), detail_viewport.width)
    draw_text(surf, role_line, font_label(10, bold=True), GOLD_BRIGHT, (detail_viewport.x, y))
    y += 24
    draw_text(surf, focused.innate.name, font_label(11, bold=True), GOLD_BRIGHT, (detail_viewport.x, y))
    y += 18
    wrapped_innate = _wrap_text_block(focused.innate.description, font_body(14), detail_viewport.width)[:3]
    for line in wrapped_innate:
        draw_text(surf, line, font_body(14), TEXT_SOFT, (detail_viewport.x, y))
        y += 18
    y += 8
    weapon_names = " / ".join(weapon.name for weapon in focused.signature_weapons)
    draw_text(
        surf,
        _ellipsize_text(f"Weapons: {weapon_names}", font_body(14, bold=True), detail_viewport.width),
        font_body(14, bold=True),
        TEXT_SOFT,
        (detail_viewport.x, y),
    )
    surf.set_clip(old_clip)
    draw_primary_button(surf, draft_btn, mouse_pos, "Draft Pick", disabled=not can_pick or current_player != player_seat)
    btns["back"] = btns.pop("left")
    btns["pool"] = pick_pool
    btns["draft"] = draft_btn
    btns["detail_viewport"] = detail_viewport
    btns["detail_scroll_max"] = detail_scroll_max
    return btns


def draw_bout_loadout(surf, mouse_pos, setup_state, selected_index, *, player_team_num: int = 1, waiting_note: str = "", drag_state: dict | None = None, detail_scroll: int = 0, summary_scroll: int = 0):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Bout Loadout Confirm",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Set formation and loadout before the duel begins",
    )
    left_rect = pygame.Rect(44, 104, 408, 744)
    center_rect = pygame.Rect(476, 104, 540, 744)
    right_rect = pygame.Rect(1040, 104, 316, 744)
    members = setup_state[f"team{player_team_num}"]
    enemy_members = setup_state[f"team{2 if player_team_num == 1 else 1}"]
    selected_index = max(0, min(selected_index, len(members) - 1)) if members else 0
    formation_members, formation_slots = _draw_loadout_formation_panel(
        surf,
        left_rect,
        mouse_pos,
        members,
        selected_index,
        drag_index=None if drag_state is None else drag_state.get("member_index"),
        drag_hover_slot=None if drag_state is None else drag_state.get("hover_slot"),
    )
    allowed_raw = setup_state.get(f"team{player_team_num}_allowed_artifact_ids", None)
    detail_buttons = _draw_loadout_detail_panel(
        surf,
        center_rect,
        mouse_pos,
        members,
        selected_index,
        allowed_artifact_ids=None if allowed_raw is None else set(allowed_raw),
        scroll=detail_scroll,
    )
    opponent_lines = [f"{SLOT_LABELS[member['slot']]}: {ADVENTURERS_BY_ID[member['adventurer_id']].name}" for member in enemy_members]
    pressure_line = "Second seat gets the round-one bonus swap." if player_team_num == 2 else "The rival holds the round-one bonus swap if they drafted second."
    summary_blocks = [
        ("Your Side", [f"Role Summary: {quest_role_summary(members)}", pressure_line]),
        ("Rival Roster", opponent_lines or ["The opposing side is not locked yet."]),
        ("Notes", recommendation_notes(members)[:2]),
    ]
    confirm_btn, summary_viewport, summary_scroll_max = _draw_loadout_summary_panel(surf, right_rect, summary_blocks, waiting_note, mouse_pos, "Confirm Bout Loadouts", len(members) != 3, scroll=summary_scroll)
    btns["back"] = btns.pop("left")
    btns["formation_members"] = formation_members
    btns["formation_slots"] = formation_slots
    btns["weapon_prev"] = detail_buttons["weapon_prev"]
    btns["weapon_next"] = detail_buttons["weapon_next"]
    btns["classes"] = detail_buttons["classes"]
    btns["skills"] = detail_buttons["skills"]
    btns["artifacts"] = detail_buttons["artifacts"]
    btns["confirm"] = confirm_btn
    btns["detail_viewport"] = detail_buttons["viewport"]
    btns["detail_scroll_max"] = detail_buttons["scroll_max"]
    btns["summary_viewport"] = summary_viewport
    btns["summary_scroll_max"] = summary_scroll_max
    return btns


def draw_catalog(
    surf,
    mouse_pos,
    section_index,
    entry_index,
    filters: dict[str, str] | None = None,
    *,
    scroll: int = 0,
    detail_scroll: int = 0,
    favorite_adventurer_id: str | None = None,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Catalog",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Guild archive of adventurers, class skills, and items",
    )
    rail_rect = pygame.Rect(42, 88, 220, 770)
    filter_rect = pygame.Rect(288, 88, 504, 170)
    list_rect = pygame.Rect(288, 282, 504, 576)
    detail_rect = pygame.Rect(818, 88, 540, 770)
    draw_beveled_panel(surf, rail_rect, title="Sections")
    draw_beveled_panel(surf, filter_rect, title="Filters")
    draw_beveled_panel(surf, list_rect, title="Entries")
    draw_beveled_panel(surf, detail_rect, title="Detail")
    section_buttons = []
    section_index = max(0, min(section_index, len(CATALOG_SECTIONS) - 1))
    for index, name in enumerate(CATALOG_SECTIONS):
        rect = pygame.Rect(rail_rect.x + 16, rail_rect.y + 54 + index * 66, rail_rect.width - 32, 52)
        draw_secondary_button(surf, rect, mouse_pos, name, active=index == section_index)
        section_buttons.append((rect, index))
    section_name = CATALOG_SECTIONS[section_index]
    filter_defs = catalog_filter_definitions(section_name)
    filters = dict(filters or {})
    for definition in filter_defs:
        options = [str(value) for value, _label in definition["options"]]
        current = str(filters.get(definition["key"], options[0])) if options else "all"
        filters[definition["key"]] = current if current in options else options[0]
    entries = catalog_entries(section_name, filters, favorite_adventurer_id=favorite_adventurer_id)
    entry_index = min(entry_index, max(0, len(entries) - 1))

    filter_buttons = []
    if filter_defs:
        columns = 2 if len(filter_defs) > 1 else 1
        gutter = 18
        cell_width = (filter_rect.width - 36 - gutter * (columns - 1)) // columns
        for index, definition in enumerate(filter_defs):
            row = index // columns
            col = index % columns
            cell_x = filter_rect.x + 18 + col * (cell_width + gutter)
            cell_y = filter_rect.y + 56 + row * 56
            draw_text(surf, definition["label"], font_label(10, bold=True), TEXT_MUTE, (cell_x, cell_y))
            current_value = next(
                (
                    label
                    for value, label in definition["options"]
                    if str(value) == str(filters.get(definition["key"], definition["options"][0][0]))
                ),
                definition["options"][0][1],
            )
            prev_rect = pygame.Rect(cell_x, cell_y + 16, 30, 28)
            value_rect = pygame.Rect(cell_x + 36, cell_y + 16, cell_width - 72, 28)
            next_rect = pygame.Rect(cell_x + cell_width - 30, cell_y + 16, 30, 28)
            draw_secondary_button(surf, prev_rect, mouse_pos, "<")
            draw_secondary_button(surf, value_rect, mouse_pos, current_value)
            draw_secondary_button(surf, next_rect, mouse_pos, ">")
            filter_buttons.append((prev_rect, definition["key"], -1))
            filter_buttons.append((value_rect, definition["key"], 1))
            filter_buttons.append((next_rect, definition["key"], 1))
        result_label = f"{len(entries)} {'entry' if len(entries) == 1 else 'entries'} in {section_name.lower()}."
        draw_text(surf, result_label, font_body(15), TEXT_SOFT, (filter_rect.x + 18, filter_rect.bottom - 34))
    else:
        draw_text(surf, "No filters are needed for this section.", font_body(15), TEXT_SOFT, (filter_rect.x + 18, filter_rect.y + 64))

    entry_buttons = []
    entries_viewport = pygame.Rect(list_rect.x + 16, list_rect.y + 50, list_rect.width - 32, list_rect.height - 108)
    row_height = 58
    page_size = max(1, entries_viewport.height // row_height)
    max_scroll = max(0, len(entries) - page_size)
    scroll = max(0, min(scroll, max_scroll))
    visible_entries = entries[scroll:scroll + page_size]
    for row_index, entry in enumerate(visible_entries):
        actual_index = scroll + row_index
        rect = pygame.Rect(entries_viewport.x + 2, entries_viewport.y + row_index * row_height, entries_viewport.width - 8, 50)
        draw_secondary_button(surf, rect, mouse_pos, entry["title"], active=actual_index == entry_index)
        subtitle_line = _wrap_text_block(entry["subtitle"], font_body(13), rect.width - 32)[0] if entry["subtitle"] else ""
        draw_text(surf, subtitle_line, font_body(13), TEXT_SOFT, (rect.x + 16, rect.y + 30))
        entry_buttons.append((rect, actual_index))
    if not visible_entries:
        draw_text(surf, "No entries match the current filters.", font_body(18), TEXT_SOFT, (entries_viewport.x + 6, entries_viewport.y + 10))

    detail_viewport = pygame.Rect(detail_rect.x + 18, detail_rect.y + 156, detail_rect.width - 36, detail_rect.height - 178)
    detail_scroll_max = 0
    if entries:
        entry = entries[entry_index]
        draw_text(surf, entry["title"], font_headline(32, bold=True), TEXT, (detail_rect.x + 24, detail_rect.y + 62))
        subtitle_lines = _wrap_multiline_block(entry["subtitle"], font_label(12, bold=True), detail_rect.width - 48, limit=3)
        for row_index, line in enumerate(subtitle_lines):
            draw_text(surf, line, font_label(12, bold=True), GOLD_BRIGHT, (detail_rect.x + 24, detail_rect.y + 104 + row_index * 18))
        detail_viewport = pygame.Rect(detail_rect.x + 18, detail_rect.y + 156 + max(0, len(subtitle_lines) - 1) * 18, detail_rect.width - 36, detail_rect.height - 178 - max(0, len(subtitle_lines) - 1) * 18)
        old_clip = surf.get_clip()
        surf.set_clip(detail_viewport)
        y = detail_viewport.y - detail_scroll
        for line in _wrap_multiline_block(entry["body"], font_body(18), detail_viewport.width - 10, limit=240):
            if line:
                draw_text(surf, line, font_body(18), TEXT_SOFT, (detail_viewport.x, y))
                y += 24
            else:
                y += 12
        content_bottom = y
        surf.set_clip(old_clip)
        detail_scroll_max = max(0, content_bottom - detail_viewport.bottom)
        _draw_scroll_hint(surf, detail_viewport, detail_scroll, detail_scroll_max)
    else:
        draw_text(surf, "No entry selected.", font_headline(24, bold=True), TEXT, (detail_rect.x + 24, detail_rect.y + 70))
        draw_text(surf, "Adjust the filters or change sections to browse the archive.", font_body(17), TEXT_SOFT, (detail_rect.x + 24, detail_rect.y + 112))

    btns["back"] = btns.pop("left")
    btns["sections"] = section_buttons
    btns["filters"] = filter_buttons
    btns["entries"] = entry_buttons
    btns["entries_viewport"] = entries_viewport
    btns["entry_page_size"] = page_size
    btns["entry_scroll_max"] = max_scroll
    btns["detail_viewport"] = detail_viewport
    btns["detail_scroll_max"] = detail_scroll_max
    return btns


def draw_lan_setup(
    surf,
    mouse_pos,
    title: str,
    mode_label: str,
    connection_mode: str,
    join_ip: str,
    local_ip: str,
    connected: bool,
    status_lines: list[str] | None = None,
):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        title,
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    left_rect = pygame.Rect(118, 164, 356, 432)
    center_rect = pygame.Rect(522, 164, 356, 432)
    right_rect = pygame.Rect(926, 164, 356, 432)
    draw_beveled_panel(surf, left_rect, title="Role")
    draw_beveled_panel(surf, center_rect, title="Connection")
    draw_beveled_panel(surf, right_rect, title="Status")
    host_rect = pygame.Rect(left_rect.x + 32, left_rect.y + 76, left_rect.width - 64, 56)
    join_rect = pygame.Rect(left_rect.x + 32, left_rect.y + 154, left_rect.width - 64, 56)
    connect_rect = pygame.Rect(center_rect.x + 34, center_rect.bottom - 76, center_rect.width - 68, 42)
    begin_rect = pygame.Rect(right_rect.x + 30, right_rect.bottom - 76, right_rect.width - 60, 42)
    draw_secondary_button(surf, host_rect, mouse_pos, "Host Match", active=connection_mode == "host")
    draw_secondary_button(surf, join_rect, mouse_pos, "Join Match", active=connection_mode == "join")
    draw_text(surf, "Local IP", font_label(11, bold=True), TEXT_MUTE, (center_rect.x + 24, center_rect.y + 76))
    draw_text(surf, local_ip or "Waiting for host socket...", font_headline(24, bold=True), GOLD_BRIGHT, (center_rect.x + 24, center_rect.y + 108))
    draw_text(surf, "Join Address", font_label(11, bold=True), TEXT_MUTE, (center_rect.x + 24, center_rect.y + 188))
    ip_box = pygame.Rect(center_rect.x + 24, center_rect.y + 216, center_rect.width - 48, 48)
    draw_beveled_panel(surf, ip_box, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    draw_text(surf, join_ip or "Type host IP here", font_body(22), TEXT if join_ip else TEXT_MUTE, (ip_box.x + 14, ip_box.y + 12))
    draw_primary_button(surf, connect_rect, mouse_pos, "Connect", disabled=connection_mode != "join")
    status_lines = status_lines or []
    state_label = "Connected" if connected else "Awaiting Connection"
    state_color = GOLD_BRIGHT if connected else TEXT_SOFT
    draw_text(surf, state_label, font_headline(26, bold=True), state_color, (right_rect.x + 24, right_rect.y + 78))
    for index, line in enumerate(status_lines[:6]):
        draw_text(surf, line, font_body(16), TEXT_SOFT, (right_rect.x + 24, right_rect.y + 132 + index * 24))
    draw_primary_button(surf, begin_rect, mouse_pos, "Begin", disabled=not connected)
    btns["back"] = btns.pop("left")
    btns["host"] = host_rect
    btns["join"] = join_rect
    btns["connect"] = connect_rect
    btns["begin"] = begin_rect
    btns["ip_box"] = ip_box
    return btns


def draw_story_settings(surf, mouse_pos, tutorials_enabled: bool, fast_resolution: bool):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Settings",
        mouse_pos,
        left_icon="<",
        right_icons=(("quit", "X", True),),
        subtitle=None,
    )
    card = pygame.Rect(380, 198, 640, 320)
    draw_beveled_panel(surf, card, title="Gameplay Preferences")
    tutorial_rect = pygame.Rect(card.x + 42, card.y + 82, card.width - 84, 62)
    fast_rect = pygame.Rect(card.x + 42, card.y + 168, card.width - 84, 62)
    draw_secondary_button(surf, tutorial_rect, mouse_pos, f"Tutorial Popups: {'ON' if tutorials_enabled else 'OFF'}", active=tutorials_enabled)
    draw_secondary_button(surf, fast_rect, mouse_pos, f"Fast Resolution: {'ON' if fast_resolution else 'OFF'}", active=fast_resolution)
    btns["back"] = btns.pop("left")
    btns["tutorials"] = tutorial_rect
    btns["fast"] = fast_rect
    return btns


def _battle_slot_rects():
    return {
        (1, SLOT_BACK_LEFT): pygame.Rect(258, 262, 198, 98),
        (1, SLOT_FRONT): pygame.Rect(362, 398, 224, 116),
        (1, SLOT_BACK_RIGHT): pygame.Rect(258, 534, 198, 98),
        (2, SLOT_BACK_LEFT): pygame.Rect(944, 262, 198, 98),
        (2, SLOT_FRONT): pygame.Rect(814, 398, 224, 116),
        (2, SLOT_BACK_RIGHT): pygame.Rect(944, 534, 198, 98),
    }


def draw_battle_hud(surf, mouse_pos, controller):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        controller.current_phase_label(),
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=f"Round {controller.battle.round_num} | {controller.active_team_label()}",
    )
    log_rect = pygame.Rect(28, 176, 196, 484)
    inspect_rect = pygame.Rect(1176, 176, 196, 484)
    action_rect = pygame.Rect(224, 696, 938, 160)
    resolve_rect = pygame.Rect(1178, 700, 194, 74)
    draw_beveled_panel(surf, log_rect, title="Battle Log")
    draw_beveled_panel(surf, inspect_rect, title="Inspect")
    draw_beveled_panel(surf, action_rect, title="Battle Plan")
    draw_meter(surf, pygame.Rect(422, 652, 218, 14), controller.battle.team1.ultimate_meter, ULTIMATE_METER_MAX, label="Player Ultimate", right_label=f"{controller.battle.team1.ultimate_meter}/{ULTIMATE_METER_MAX}")
    draw_meter(surf, pygame.Rect(760, 652, 218, 14), controller.battle.team2.ultimate_meter, ULTIMATE_METER_MAX, label="Enemy Ultimate", right_label=f"{controller.battle.team2.ultimate_meter}/{ULTIMATE_METER_MAX}", fill=SAPPHIRE)

    slot_buttons = []
    target_lookup = {id(unit) for unit in controller.legal_targets()}
    focus_unit = controller.focus_unit
    for slot_data in controller.battlefield_slots():
        rect = _battle_slot_rects()[(slot_data["team_num"], slot_data["slot"])]
        unit = slot_data["unit"]
        highlight = unit is not None and id(unit) in target_lookup
        border = GOLD_BRIGHT if highlight else GOLD_DIM
        fill_top = (64, 38, 34) if slot_data["team_num"] == 2 else (40, 46, 58)
        if unit is not None and unit is focus_unit:
            border = PARCHMENT
        draw_beveled_panel(surf, rect, fill_top=fill_top, fill_bottom=SURFACE_LOW, border=border)
        draw_text(surf, SLOT_LABELS[slot_data["slot"]], font_label(10, bold=True), TEXT_MUTE, (rect.x + 12, rect.y + 10))
        if unit is None:
            draw_text(surf, "Empty", font_label(12, bold=True), TEXT_MUTE, rect.center, center=True)
        else:
            draw_text(surf, _ellipsize_text(unit.name, font_headline(18, bold=True), rect.width - 28), font_headline(18, bold=True), TEXT, (rect.x + 14, rect.y + 28))
            draw_text(surf, _ellipsize_text(f"{unit.primary_weapon.name}", font_label(10, bold=True), rect.width - 28), font_label(10, bold=True), GOLD_BRIGHT, (rect.x + 14, rect.y + 50))
            draw_meter(surf, pygame.Rect(rect.x + 14, rect.y + 72, rect.width - 28, 11), unit.hp, unit.max_hp, fill=RUBY)
            draw_text(surf, f"{unit.hp}/{unit.max_hp}", font_label(9, bold=True), TEXT_SOFT, (rect.right - 14, rect.y + 68), right=True)
            status_text = ", ".join(status.kind for status in unit.statuses[:3]) or "Ready"
            _draw_status_aware_line(
                surf,
                status_text,
                rect.x + 14,
                rect.bottom - 16,
                font_obj=font_label(9, bold=True),
                base_color=TEXT_SOFT,
                mouse_pos=mouse_pos,
            )
            slot_buttons.append((rect, unit))

    phase_bonus = controller.phase.startswith("bonus")
    phase_color = JADE if phase_bonus else GOLD_BRIGHT
    prompt = "Queue bonus actions." if phase_bonus else "Queue one action for each adventurer."
    draw_text(surf, controller.active_team_label(), font_body(17, bold=True), TEXT, (action_rect.x + 22, action_rect.y + 42))
    draw_text(surf, prompt, font_body(15), phase_color, (action_rect.x + 22, action_rect.y + 64))
    queue_rows = controller.action_summary_rows(bonus=phase_bonus)
    draw_text(surf, "Queued", font_label(11, bold=True), TEXT_MUTE, (action_rect.x + 546, action_rect.y + 42))
    for index, row in enumerate(queue_rows[:5]):
        label = f"P{row['team_num']} | {row['actor'].name}: {row['label']}"
        wrapped = _wrap_text_block(label, font_label(10, bold=True), action_rect.width - 566)
        if wrapped:
            draw_text(surf, wrapped[0], font_label(10, bold=True), TEXT_SOFT, (action_rect.x + 546, action_rect.y + 62 + index * 16))

    action_buttons = []
    spell_buttons = []
    if controller.active_actor is not None and controller.phase in {"action_select", "bonus_select", "action_target", "bonus_target"}:
        available = controller.available_actions()
        for index, choice in enumerate(available):
            row = index // 5
            col = index % 5
            button_y = action_rect.y + (124 if controller.spellbook_open else 96)
            rect = pygame.Rect(action_rect.x + 20 + col * 92, button_y + row * 34, 84, 30)
            active = controller.pending_choice is not None and controller.pending_choice.kind == choice.kind
            draw_secondary_button(surf, rect, mouse_pos, choice.label, active=active)
            action_buttons.append((rect, choice.kind))
        if controller.spellbook_open:
            spells = controller.available_bonus_spells(controller.active_actor) if controller.phase.startswith("bonus") else controller.available_spells(controller.active_actor)
            for index, spell in enumerate(spells):
                rect = pygame.Rect(action_rect.x + 20 + index * 118, action_rect.y + 94, 108, 24)
                active = controller.pending_choice is not None and controller.pending_choice.effect_id == spell.id
                draw_secondary_button(surf, rect, mouse_pos, spell.name, active=active)
                spell_buttons.append((rect, spell.id))
        if controller.phase in {"action_target", "bonus_target"}:
            draw_text(surf, "Choose a legal target.", font_body(14, bold=True), phase_color, (action_rect.right - 18, action_rect.y + 42), right=True)

    resolve_label = controller.resolve_button_label() if hasattr(controller, "resolve_button_label") else ("Resolve Bonus Phase" if controller.phase == "bonus_resolve_ready" else "Resolve Actions")
    draw_primary_button(surf, resolve_rect, mouse_pos, resolve_label, disabled=not controller.can_resolve())

    log_lines = controller.battle.log[-8:] or ["No actions resolved yet."]
    log_y = log_rect.y + 54
    log_font = font_body(13)
    for index, line in enumerate(log_lines):
        wrapped_lines = _wrap_text_block(line, log_font, log_rect.width - 28)[:2]
        color = TEXT_SOFT if index < len(log_lines) - 1 else GOLD_BRIGHT
        for wrapped in wrapped_lines:
            draw_text(surf, wrapped, log_font, color, (log_rect.x + 14, log_y))
            log_y += 18
        log_y += 4
        if log_y > log_rect.bottom - 28:
            break

    focus = controller.focus_unit
    if focus is not None:
        focus_class_name = getattr(focus, "class_name", None) or NO_CLASS_NAME
        draw_text(surf, _ellipsize_text(focus.name, font_headline(24, bold=True), inspect_rect.width - 32), font_headline(24, bold=True), TEXT, (inspect_rect.x + 16, inspect_rect.y + 52))
        draw_text(surf, focus_class_name, font_label(11, bold=True), GOLD_BRIGHT, (inspect_rect.x + 16, inspect_rect.y + 84))
        draw_meter(surf, pygame.Rect(inspect_rect.x + 16, inspect_rect.y + 118, inspect_rect.width - 32, 14), focus.hp, focus.max_hp, fill=RUBY, right_label=f"{focus.hp}/{focus.max_hp}")
        draw_text(surf, f"ATK {focus.get_stat('attack')}  DEF {focus.get_stat('defense')}  SPD {focus.get_stat('speed')}", font_label(10, bold=True), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 146))
        ammo_text = "-"
        if focus.primary_weapon.ammo > 0:
            ammo_text = f"{focus.ammo_remaining.get(focus.primary_weapon.id, focus.primary_weapon.ammo)}/{focus.primary_weapon.ammo}"
        draw_text(surf, _ellipsize_text(f"Innate: {focus.defn.innate.name}", font_label(10, bold=True), inspect_rect.width - 32), font_label(10, bold=True), TEXT_MUTE, (inspect_rect.x + 16, inspect_rect.y + 176))
        draw_text(surf, _ellipsize_text(f"Weapon: {focus.primary_weapon.name}", font_body(14, bold=True), inspect_rect.width - 32), font_body(14, bold=True), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 200))
        draw_text(surf, f"Ammo {ammo_text}", font_label(10, bold=True), TEXT_MUTE, (inspect_rect.x + 16, inspect_rect.y + 224))
        draw_text(surf, _ellipsize_text(f"Skill: {getattr(focus.class_skill, 'name', 'None')}", font_body(13), inspect_rect.width - 32), font_body(13), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 248))
        draw_text(surf, _ellipsize_text(f"Ultimate: {focus.defn.ultimate.name}", font_body(13), inspect_rect.width - 32), font_body(13), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 274))
        draw_text(surf, _ellipsize_text(f"Artifact: {focus.artifact.name if focus.artifact is not None else 'None'}", font_body(13), inspect_rect.width - 32), font_body(13), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 300))
        _draw_wrapped_lines(
            surf,
            [f"Statuses: {', '.join(status.kind for status in focus.statuses) or 'None'}"],
            inspect_rect.x + 16,
            inspect_rect.y + 334,
            inspect_rect.width - 32,
            font=font_body(13),
            color=TEXT_SOFT,
            line_height=16,
        )

    btns["back"] = btns.pop("left")
    btns["resolve"] = resolve_rect
    btns["action_buttons"] = action_buttons
    btns["spell_buttons"] = spell_buttons
    btns["slot_buttons"] = slot_buttons
    return btns


def draw_results(surf, mouse_pos, result_kind, is_victory: bool, winner_label, lines):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Encounter Results" if result_kind == "quest" else "Bout Results",
        mouse_pos,
        left_icon="<",
        right_icons=(("quit", "X", True),),
        subtitle="Victory and post-match summary",
    )
    center = pygame.Rect(320, 160, 760, 520)
    draw_beveled_panel(surf, center, fill_top=(60, 48, 28), fill_bottom=SURFACE_LOW, border=GOLD_BRIGHT)
    draw_text(surf, "Victory" if is_victory else "Defeat", font_headline(56, bold=True), GOLD_BRIGHT if is_victory else EMBER, (center.centerx, center.y + 92), center=True)
    draw_text(surf, winner_label or "No victor", font_headline(28, bold=True), TEXT, (center.centerx, center.y + 156), center=True)
    for index, line in enumerate(lines):
        draw_text(surf, line, font_body(22), TEXT_SOFT, (center.centerx, center.y + 222 + index * 36), center=True)
    continue_btn = pygame.Rect(center.x + 68, center.bottom - 78, 180, 44)
    rematch_btn = pygame.Rect(center.centerx - 90, center.bottom - 78, 180, 44)
    return_btn = pygame.Rect(center.right - 248, center.bottom - 78, 180, 44)
    draw_primary_button(surf, continue_btn, mouse_pos, "Continue")
    draw_secondary_button(surf, rematch_btn, mouse_pos, "Rematch")
    draw_secondary_button(surf, return_btn, mouse_pos, "Return")
    btns["back"] = btns.pop("left")
    btns["continue"] = continue_btn
    btns["rematch"] = rematch_btn
    btns["return"] = return_btn
    return btns


# ============================================================================
# UI Redesign Overrides
# ============================================================================


def _hx(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


UI_BG_DEEP = _hx("08090F")
UI_BG_MID = _hx("0F1119")
UI_BG_SURFACE = _hx("181B26")
UI_BG_RAISED = _hx("222638")
UI_GOLD = _hx("D4A843")
UI_GOLD_BRIGHT = _hx("F5D978")
UI_GOLD_DIM = _hx("6B5A2A")
UI_TEXT = _hx("E8E4DC")
UI_TEXT_SOFT = _hx("9A978E")
UI_TEXT_MUTE = _hx("5C5950")
UI_GREEN = _hx("4CAF50")
UI_RED = _hx("C62828")
UI_BLUE = _hx("5C7CFA")
UI_ORANGE = _hx("E65100")
UI_STATUS_COLORS = {
    "burn": _hx("FF6D00"),
    "root": _hx("66BB6A"),
    "shock": _hx("FFEE58"),
    "weaken": _hx("AB47BC"),
    "expose": _hx("EF5350"),
    "guard": _hx("42A5F5"),
    "spotlight": _hx("FFF176"),
    "taunt": _hx("FF8A65"),
}
UI_CLASS_COLORS = {
    "Warden": _hx("5C6BC0"),
    "Fighter": _hx("EF5350"),
    "Mage": _hx("7E57C2"),
    "Ranger": _hx("66BB6A"),
    "Cleric": _hx("FFEE58"),
    "Rogue": _hx("26C6DA"),
    NO_CLASS_NAME: UI_TEXT_MUTE,
}
UI_TAB_ICONS = {
    "Player Skins": "P",
    "Player Chairs": "C",
    "Emotes": "E",
    "Poses": "O",
    "Assistant Skins": "A",
    "Bartender Skins": "B",
    "Server Skins": "S",
    "Adventurer Skins": "V",
    "Guild Hall Skins": "H",
}
HUD_HEIGHT = 36


def _with_alpha(color, alpha: int) -> tuple[int, int, int, int]:
    return (color[0], color[1], color[2], alpha)


def _blit_translucent_rect(surf, rect, color, *, border=None, radius: int = 16):
    card = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(card, color, pygame.Rect(0, 0, rect.width, rect.height), border_radius=radius)
    if border is not None:
        pygame.draw.rect(card, border, pygame.Rect(0, 0, rect.width, rect.height), 1, border_radius=radius)
    surf.blit(card, rect.topleft)


def _scene_lights(surf, *, warm=False):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    palette = [(245, 217, 120, 30), (212, 168, 67, 20)] if warm else [(92, 124, 250, 18), (212, 168, 67, 10)]
    points = [(180, 130), (WIDTH - 220, 180), (WIDTH // 2, HEIGHT // 2 + 40), (260, HEIGHT - 160)]
    for index, (x, y) in enumerate(points):
        color = palette[index % len(palette)]
        pygame.draw.circle(overlay, color, (x, y), 180 + index * 32)
    surf.blit(overlay, (0, 0))


def draw_background(surf, scene: str = "default"):
    fill_gradient(surf, pygame.Rect(0, 0, WIDTH, HEIGHT), UI_BG_DEEP, UI_BG_MID)
    if scene in {"guild", "quest", "market"}:
        pygame.draw.rect(surf, _lerp_color(UI_BG_SURFACE, UI_ORANGE, 0.18), pygame.Rect(0, HEIGHT - 210, WIDTH, 210))
        pygame.draw.rect(surf, UI_BG_DEEP, pygame.Rect(0, HEIGHT - 150, WIDTH, 150))
        for x in (140, 430, 730, 1030, 1260):
            pillar = pygame.Surface((22, HEIGHT - 220), pygame.SRCALPHA)
            pillar.fill(_with_alpha(UI_GOLD_DIM, 60))
            surf.blit(pillar, (x, 90))
        _scene_lights(surf, warm=True)
    elif scene == "arena":
        for ring in range(6):
            pygame.draw.circle(
                surf,
                _lerp_color(UI_GOLD_DIM, UI_BG_RAISED, ring / 5 if ring else 0.0),
                (WIDTH // 2, HEIGHT // 2 + 30),
                180 + ring * 54,
                1,
            )
        _scene_lights(surf, warm=False)
    else:
        _scene_lights(surf, warm=False)


def draw_beveled_panel(
    surf,
    rect,
    *,
    title=None,
    title_color=UI_TEXT,
    fill_top=UI_BG_SURFACE,
    fill_bottom=UI_BG_MID,
    border=UI_GOLD_DIM,
):
    draw_shadow(surf, rect, radius=18, alpha=80)
    fill_gradient(surf, rect, fill_top, fill_bottom)
    glow = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(glow, _with_alpha((255, 255, 255), 10), pygame.Rect(1, 1, rect.width - 2, rect.height - 2), border_radius=16)
    surf.blit(glow, rect.topleft)
    pygame.draw.rect(surf, border, rect, 1, border_radius=16)
    if title:
        draw_text(surf, str(title).upper(), font_label(11, bold=True), title_color, (rect.x + 16, rect.y + 12))


def draw_icon_button(surf, rect, mouse_pos, label, *, active=False, danger=False):
    hovered = rect.collidepoint(mouse_pos)
    border = UI_RED if danger else (UI_GOLD_BRIGHT if active or hovered else UI_GOLD_DIM)
    fill = UI_BG_RAISED if active or hovered else UI_BG_SURFACE
    draw_beveled_panel(surf, rect, fill_top=fill, fill_bottom=UI_BG_MID, border=border)
    draw_text(
        surf,
        label,
        font_label(16, bold=True),
        UI_RED if danger else (UI_GOLD_BRIGHT if active or hovered else UI_TEXT_SOFT),
        rect.center,
        center=True,
    )
    return rect


def draw_primary_button(surf, rect, mouse_pos, label, *, disabled=False, accent=UI_GOLD):
    hovered = rect.collidepoint(mouse_pos) and not disabled
    top = _lerp_color(accent, UI_GOLD_BRIGHT, 0.3 if hovered else 0.0)
    bottom = _lerp_color(UI_GOLD_DIM, accent, 0.65 if hovered else 0.4)
    fill_gradient(surf, rect, UI_BG_RAISED if disabled else top, UI_BG_SURFACE if disabled else bottom)
    pygame.draw.rect(surf, UI_GOLD_BRIGHT if not disabled else UI_GOLD_DIM, rect, 1, border_radius=14)
    draw_text(
        surf,
        _ellipsize_text(label, font_body(14, bold=True), rect.width - 16),
        font_body(14, bold=True),
        UI_TEXT_MUTE if disabled else UI_BG_DEEP,
        rect.center,
        center=True,
    )
    return rect


def draw_secondary_button(surf, rect, mouse_pos, label, *, active=False):
    hovered = rect.collidepoint(mouse_pos)
    draw_beveled_panel(
        surf,
        rect,
        fill_top=UI_BG_RAISED if active or hovered else UI_BG_SURFACE,
        fill_bottom=UI_BG_MID,
        border=UI_GOLD_BRIGHT if active else (UI_GOLD if hovered else UI_GOLD_DIM),
    )
    draw_text(
        surf,
        _ellipsize_text(label, font_body(13, bold=True), rect.width - 16),
        font_body(13, bold=True),
        UI_GOLD_BRIGHT if active else UI_TEXT,
        rect.center,
        center=True,
    )
    return rect


def draw_text_input(surf, rect, mouse_pos, label, value, *, active=False, placeholder=""):
    hovered = rect.collidepoint(mouse_pos)
    draw_beveled_panel(
        surf,
        rect,
        fill_top=UI_BG_RAISED,
        fill_bottom=UI_BG_SURFACE,
        border=UI_GOLD_BRIGHT if active else (UI_GOLD if hovered else UI_GOLD_DIM),
    )
    draw_text(surf, label.upper(), font_label(10, bold=True), UI_TEXT_MUTE, (rect.x + 14, rect.y + 10))
    shown = value or placeholder
    draw_text(surf, shown, font_body(16), UI_TEXT if value else UI_TEXT_MUTE, (rect.x + 14, rect.y + 34))
    return rect


def draw_chip(surf, rect, text, color):
    _blit_translucent_rect(surf, rect, _with_alpha(color, 30), border=color, radius=10)
    draw_text(surf, text, font_label(9, bold=True), color, rect.center, center=True)


def draw_meter(surf, rect, value, maximum, *, fill=UI_GOLD, label=None, right_label=None):
    pygame.draw.rect(surf, UI_BG_DEEP, rect, border_radius=8)
    pygame.draw.rect(surf, UI_GOLD_DIM, rect, 1, border_radius=8)
    if maximum > 0 and value > 0:
        amount = max(0.0, min(1.0, value / maximum))
        fill_width = max(8, int((rect.width - 4) * amount))
        pygame.draw.rect(surf, fill, pygame.Rect(rect.x + 2, rect.y + 2, fill_width, rect.height - 4), border_radius=6)
    if label:
        draw_text(surf, label.upper(), font_label(10, bold=True), UI_TEXT_MUTE, (rect.x, rect.y - 14))
    if right_label:
        draw_text(surf, right_label, font_label(10, bold=True), UI_TEXT_SOFT, (rect.right, rect.y - 14), right=True)


def _rank_label():
    profile = CURRENT_PROFILE
    return getattr(profile, "storybook_rank_label", "Squire") if profile is not None else "Squire"


def draw_top_bar(surf, title, mouse_pos, *, left_icon=None, right_icons=(), subtitle=None):
    strip = pygame.Rect(18, 12, WIDTH - 36, HUD_HEIGHT)
    _blit_translucent_rect(surf, strip, _with_alpha(UI_BG_DEEP, 220), border=None, radius=18)
    btns = {}
    if left_icon is not None:
        left_rect = pygame.Rect(strip.x + 10, strip.y + 6, 24, 24)
        btns["left"] = draw_icon_button(surf, left_rect, mouse_pos, "<")
    title_x = strip.x + 58 if left_icon is not None else strip.x + 18
    if title:
        draw_text(surf, str(title).upper(), font_label(11, bold=True), UI_TEXT_SOFT, (title_x, strip.y + 12))
    profile = CURRENT_PROFILE
    right_gap = 10
    icon_size = 24
    row_y = strip.y + 6
    right_cursor = strip.right - 12
    icon_positions = []
    for key, label, danger in reversed(list(right_icons)):
        rect = pygame.Rect(right_cursor - icon_size, row_y, icon_size, icon_size)
        icon_positions.append((key, label, danger, rect))
        right_cursor = rect.x - right_gap
    if profile is not None:
        level_info = level_state(getattr(profile, "player_exp", 0))
        clusters = [
            ("gold_readout", f"G {getattr(profile, 'gold', 0)}"),
            ("rank_readout", _rank_label()),
            ("level_readout", f"{level_info.level}"),
        ]
        badge_font = font_label(10, bold=True)
        badge_defs = []
        for key, text in clusters:
            width = max(42, badge_font.size(text)[0] + 20)
            badge_defs.append((key, text, width))
        total_badge_width = sum(width for _key, _text, width in badge_defs) + right_gap * max(0, len(badge_defs) - 1)
        badge_x = right_cursor - total_badge_width
        for key, text, width in badge_defs:
            badge = pygame.Rect(badge_x, row_y, width, icon_size)
            draw_beveled_panel(surf, badge, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
            color = UI_GOLD if key == "gold_readout" else UI_TEXT_SOFT
            draw_text(surf, text, badge_font, color, badge.center, center=True)
            badge_x += width + right_gap
    for key, label, danger, rect in reversed(icon_positions):
        btns[key] = draw_icon_button(surf, rect, mouse_pos, label, danger=danger)
    return btns


def _class_tint(class_name: str | None):
    return UI_CLASS_COLORS.get(class_name or NO_CLASS_NAME, UI_GOLD)


def _weapon_icon(kind: str) -> str:
    return {"melee": "M", "ranged": "R", "magic": "S"}.get(kind, "?")


def _status_dot_label(status_kind: str) -> str:
    return status_kind[:1].upper()


def _draw_portrait_block(surf, rect, title: str, *, accent, secondary=None, initials: str | None = None, show_badge: bool = True):
    fill_gradient(surf, rect, _lerp_color(accent, UI_BG_RAISED, 0.3), UI_BG_DEEP)
    pygame.draw.rect(surf, _lerp_color(accent, UI_GOLD_DIM, 0.35 if secondary is None else 0.15), rect, 1, border_radius=14)
    if show_badge:
        badge = pygame.Rect(rect.x + 12, rect.y + 12, 38, 22)
        _blit_translucent_rect(surf, badge, _with_alpha(UI_BG_DEEP, 160), border=_lerp_color(accent, UI_GOLD_DIM, 0.4), radius=8)
        draw_text(surf, title, font_label(9, bold=True), UI_GOLD_BRIGHT, badge.center, center=True)
    if secondary is not None:
        draw_text(surf, secondary, font_label(10, bold=True), UI_TEXT_SOFT, (rect.right - 12, rect.y + 16), right=True)
    draw_text(surf, initials or title[:2], font_headline(min(44, rect.height // 2), bold=True), UI_TEXT, rect.center, center=True)


def draw_adventurer_card(surf, rect, mouse_pos, adventurer, *, selected=False, unavailable=False, small=False, tag_line=None):
    hovered = rect.collidepoint(mouse_pos)
    tint = ROLE_COLORS.get(role_tags_for_adventurer(adventurer)[0], UI_GOLD)
    border = UI_GOLD_BRIGHT if selected else (_lerp_color(tint, UI_GOLD_BRIGHT, 0.3) if hovered else UI_GOLD_DIM)
    fill_top = _lerp_color(UI_BG_RAISED, tint, 0.18)
    draw_beveled_panel(surf, rect, fill_top=fill_top, fill_bottom=UI_BG_MID, border=border)
    initials = "".join(part[0] for part in adventurer.name.split()[:2]).upper()
    if small and rect.height <= 104:
        portrait_rect = pygame.Rect(rect.x + 8, rect.y + 8, max(42, min(52, rect.width // 3)), rect.height - 16)
        _draw_portrait_block(surf, portrait_rect, "ADV", accent=tint, secondary=None, initials=initials, show_badge=False)
        name_x = portrait_rect.right + 10
        name_w = rect.right - name_x - 12
        draw_text(
            surf,
            _ellipsize_text(adventurer.name, font_body(13, bold=True), name_w),
            font_body(13, bold=True),
            UI_TEXT,
            (name_x, rect.y + 12),
        )
        hp_rect = pygame.Rect(name_x, rect.y + 38, max(48, name_w - 4), 7)
        draw_meter(surf, hp_rect, adventurer.hp, adventurer.hp, fill=UI_GREEN)
        class_chip = pygame.Rect(name_x, rect.bottom - 26, 18, 18)
        draw_chip(surf, class_chip, role_tags_for_adventurer(adventurer)[0][:1], tint)
        weapon_x = rect.right - 30
        for weapon in adventurer.signature_weapons[:2]:
            chip = pygame.Rect(weapon_x, rect.bottom - 26, 18, 18)
            draw_chip(surf, chip, _weapon_icon(weapon.kind), _class_tint(weapon.kind.title()))
            weapon_x -= 22
    else:
        art_h = 56 if small else 90
        art_rect = pygame.Rect(rect.x + 10, rect.y + 10, rect.width - 20, art_h)
        _draw_portrait_block(surf, art_rect, "ADV", accent=tint, secondary=None, initials=initials)
        name_font = font_body(13 if small else 16, bold=True)
        name_y = art_rect.bottom + 8
        draw_text(
            surf,
            _ellipsize_text(adventurer.name, name_font, rect.width - 20),
            name_font,
            UI_TEXT,
            (rect.x + 10, name_y),
        )
        if small:
            if tag_line and rect.height >= 148:
                draw_text(
                    surf,
                    _ellipsize_text(tag_line, font_label(10, bold=True), rect.width - 20),
                    font_label(10, bold=True),
                    UI_GOLD_BRIGHT,
                    (rect.x + 10, name_y + 18),
                )
            footer_y = rect.bottom - 34
            class_chip = pygame.Rect(rect.x + 12, footer_y, 18, 18)
            draw_chip(surf, class_chip, role_tags_for_adventurer(adventurer)[0][:1], tint)
            weapon_x = rect.right - 30
            for weapon in adventurer.signature_weapons[:2]:
                chip = pygame.Rect(weapon_x, footer_y, 18, 18)
                draw_chip(surf, chip, _weapon_icon(weapon.kind), _class_tint(weapon.kind.title()))
                weapon_x -= 22
            hp_rect = pygame.Rect(rect.x + 10, rect.bottom - 14, rect.width - 20, 6)
            draw_meter(surf, hp_rect, adventurer.hp, adventurer.hp, fill=UI_GREEN)
        else:
            if tag_line:
                draw_text(
                    surf,
                    _ellipsize_text(tag_line, font_label(10, bold=True), rect.width - 20),
                    font_label(10, bold=True),
                    UI_GOLD_BRIGHT,
                    (rect.x + 10, name_y + 22),
                )
            else:
                draw_text(
                    surf,
                    _ellipsize_text(", ".join(role_tags_for_adventurer(adventurer)), font_label(10, bold=True), rect.width - 20),
                    font_label(10, bold=True),
                    UI_TEXT_SOFT,
                    (rect.x + 10, name_y + 22),
                )
            hp_rect = pygame.Rect(rect.x + 10, rect.bottom - 20, rect.width - 20, 8)
            draw_meter(surf, hp_rect, adventurer.hp, adventurer.hp, fill=UI_GREEN)
            class_chip = pygame.Rect(rect.x + 12, rect.bottom - 40, 18, 18)
            draw_chip(surf, class_chip, role_tags_for_adventurer(adventurer)[0][:1], tint)
            weapon_x = rect.right - 30
            for weapon in adventurer.signature_weapons[:2]:
                chip = pygame.Rect(weapon_x, rect.bottom - 40, 18, 18)
                draw_chip(surf, chip, _weapon_icon(weapon.kind), _class_tint(weapon.kind.title()))
                weapon_x -= 22
    if unavailable:
        veil = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        veil.fill((6, 8, 12, 140))
        surf.blit(veil, rect.topleft)
        pygame.draw.rect(surf, UI_TEXT_MUTE, rect, 1, border_radius=16)
    return rect


def _hover_popout_rect(source: pygame.Rect, width: int = 300, height: int = 210):
    if source.centerx < WIDTH // 2:
        x = min(WIDTH - width - 24, source.right + 18)
    else:
        x = max(24, source.left - width - 18)
    y = max(64, min(HEIGHT - height - 24, source.y - 10))
    return pygame.Rect(x, y, width, height)


def _draw_adventurer_popout(surf, rect, adventurer, *, class_name: str | None = None, artifact_name: str | None = None, artifact=None):
    _draw_info_popout(
        surf,
        rect,
        adventurer.name,
        _adventurer_detail_lines(adventurer, class_name=class_name, artifact_name=artifact_name, artifact=artifact),
        width=max(rect.width, 360),
    )


def _draw_avatar_stage(surf, rect, initials: str = "YOU"):
    draw_beveled_panel(surf, rect, fill_top=_lerp_color(UI_GOLD, UI_BG_RAISED, 0.3), fill_bottom=UI_BG_DEEP, border=UI_GOLD_DIM)
    max_size = min(40, rect.height - 22, max(20, int(rect.width * 1.25 / max(1, len(initials)))))
    draw_text(surf, initials, font_headline(max_size, bold=True), UI_TEXT, rect.center, center=True)


def _draw_scrim(surf, alpha: int = 170):
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((UI_BG_DEEP[0], UI_BG_DEEP[1], UI_BG_DEEP[2], alpha))
    surf.blit(overlay, (0, 0))


def _draw_overlay_panel(surf, rect, *, title=None):
    _draw_scrim(surf, 160)
    draw_beveled_panel(surf, rect, title=title, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)


def _draw_scene_object(surf, rect, mouse_pos, title: str, subtitle: str, *, accent, label_key: str | None = None):
    hovered = rect.collidepoint(mouse_pos)
    draw_beveled_panel(
        surf,
        rect,
        fill_top=_lerp_color(UI_BG_RAISED, accent, 0.18),
        fill_bottom=UI_BG_MID,
        border=UI_GOLD_BRIGHT if hovered else UI_GOLD_DIM,
    )
    if hovered:
        glow = pygame.Surface((rect.width + 24, rect.height + 24), pygame.SRCALPHA)
        pygame.draw.rect(glow, _with_alpha(accent, 40), pygame.Rect(12, 12, rect.width, rect.height), border_radius=20)
        surf.blit(glow, (rect.x - 12, rect.y - 12))
    label = label_key or title[:2].upper()
    _draw_portrait_block(surf, pygame.Rect(rect.x + 18, rect.y + 18, rect.width - 36, rect.height - 74), label, accent=accent, initials=label, show_badge=False)
    draw_text(
        surf,
        title,
        font_body(15, bold=True),
        UI_GOLD_BRIGHT if hovered else UI_TEXT,
        (rect.centerx, rect.bottom - 42),
        center=True,
    )
    if hovered:
        draw_text(surf, subtitle, font_label(10, bold=True), UI_TEXT_SOFT, (rect.centerx, rect.bottom - 22), center=True)


def draw_main_menu(surf, mouse_pos, profile, *, has_current_quest=False):
    draw_background(surf, "guild")
    btns = draw_top_bar(
        surf,
        "",
        mouse_pos,
        right_icons=(("settings", "S", False), ("quit", "X", True)),
    )
    pulse = (pygame.time.get_ticks() // 250) % 2
    logo_color = UI_GOLD_BRIGHT if pulse else UI_GOLD
    layout_x = 20
    layout_top = 86
    gap = 16
    big_w = 250
    big_h = 180
    cluster_w = big_w * 2 + gap
    small_w = (cluster_w - gap * 3) // 4
    small_h = 104

    draw_text(surf, "FABLED", font_headline(62, bold=True), logo_color, (layout_x + 8, layout_top), center=False)

    quest_rect = pygame.Rect(layout_x, layout_top + 82, big_w, big_h)
    bouts_rect = pygame.Rect(layout_x + big_w + gap, layout_top + 82, big_w, big_h)
    catalog_rect = pygame.Rect(layout_x, layout_top + 82 + big_h + gap, big_w, big_h)
    training_rect = pygame.Rect(layout_x + big_w + gap, layout_top + 82 + big_h + gap, big_w, big_h)

    small_y = layout_top + 82 + (big_h + gap) * 2
    market_rect = pygame.Rect(layout_x, small_y, small_w, small_h)
    assistant_rect = pygame.Rect(layout_x + (small_w + gap), small_y, small_w, small_h)
    bartender_rect = pygame.Rect(layout_x + (small_w + gap) * 2, small_y, small_w, small_h)
    server_rect = pygame.Rect(layout_x + (small_w + gap) * 3, small_y, small_w, small_h)
    avatar_right = assistant_rect.right + gap // 2
    avatar_rect = pygame.Rect(layout_x, small_y + small_h + gap, avatar_right - layout_x, 104)

    _draw_scene_object(surf, quest_rect, mouse_pos, "Quests", "Quest Runs", accent=UI_GOLD, label_key="Q")
    _draw_scene_object(surf, bouts_rect, mouse_pos, "Bouts", "Best of Three", accent=UI_RED, label_key="B")
    _draw_scene_object(surf, catalog_rect, mouse_pos, "Codex", "Rules & Roster", accent=UI_GOLD_BRIGHT, label_key="C")
    _draw_scene_object(surf, training_rect, mouse_pos, "Training", "Practice Fights", accent=UI_BLUE, label_key="T")
    _draw_scene_object(surf, market_rect, mouse_pos, "Market", "Cosmetics", accent=UI_ORANGE, label_key="M")

    draw_beveled_panel(surf, avatar_rect, fill_top=_lerp_color(UI_BG_RAISED, UI_GOLD, 0.12), fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    _draw_avatar_stage(surf, pygame.Rect(avatar_rect.x + 10, avatar_rect.y + 10, 66, avatar_rect.height - 20), "YOU")
    draw_text(surf, "Profile", font_body(18, bold=True), UI_TEXT, (avatar_rect.x + 92, avatar_rect.y + 26))
    draw_text(
        surf,
        f"{_rank_label()}  •  {level_state(getattr(profile, 'player_exp', 0)).level}",
        font_body(13),
        UI_TEXT_SOFT,
        (avatar_rect.x + 92, avatar_rect.y + 58),
    )
    if avatar_rect.collidepoint(mouse_pos):
        glow = pygame.Surface((avatar_rect.width + 24, avatar_rect.height + 24), pygame.SRCALPHA)
        pygame.draw.rect(glow, _with_alpha(UI_GOLD, 36), pygame.Rect(12, 12, avatar_rect.width, avatar_rect.height), border_radius=20)
        surf.blit(glow, (avatar_rect.x - 12, avatar_rect.y - 12))
        tooltip = _hover_popout_rect(avatar_rect, 240, 108)
        draw_beveled_panel(surf, tooltip, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
        draw_text(surf, "Guildmaster", font_body(15, bold=True), UI_TEXT, (tooltip.x + 12, tooltip.y + 14))
        draw_text(surf, _rank_label(), font_label(10, bold=True), UI_GOLD, (tooltip.x + 12, tooltip.y + 40))
        draw_text(surf, f"Level {level_state(getattr(profile, 'player_exp', 0)).level}", font_body(13), UI_TEXT_SOFT, (tooltip.x + 12, tooltip.y + 60))

    employee_specs = [
        (assistant_rect, "employee_assistant", "Assistant", getattr(profile, "assistant_skill", "") or "Select Skill", _hx("8BC34A")),
        (bartender_rect, "employee_bartender", "Bartender", getattr(profile, "bartender_skill", "") or "Select Skill", _hx("FF8A65")),
        (server_rect, "employee_server", "Supplier", getattr(profile, "server_skill", "") or "Select Skill", _hx("4DD0E1")),
    ]
    for rect, _key, name, skill_name, color in employee_specs:
        _draw_scene_object(surf, rect, mouse_pos, name, skill_name, accent=color, label_key=name[:1].upper())

    btns["profile"] = avatar_rect
    btns["guild_hall"] = quest_rect
    btns["bouts"] = bouts_rect
    btns["market"] = market_rect
    btns["catalog"] = catalog_rect
    btns["training_grounds"] = training_rect
    btns["employee_assistant"] = assistant_rect
    btns["employee_bartender"] = bartender_rect
    btns["employee_server"] = server_rect
    return btns


def draw_tutorial_gate_menu(surf, mouse_pos, *, label: str = "Once Upon A Time..."):
    draw_background(surf, "guild")
    btns = draw_top_bar(
        surf,
        "",
        mouse_pos,
        right_icons=(("settings", "S", False), ("quit", "X", True)),
    )
    draw_text(surf, "FABLED", font_headline(62, bold=True), UI_GOLD_BRIGHT, (28, 96))
    story_rect = pygame.Rect(28, 210, 520, 184)
    _draw_scene_object(surf, story_rect, mouse_pos, label, "Start The Tutorial", accent=UI_GOLD_BRIGHT, label_key="O")
    btns["tutorial_story"] = story_rect
    return btns


def draw_first_run_prompt(surf, mouse_pos):
    draw_background(surf, "guild")
    panel = pygame.Rect(340, 236, 720, 360)
    _draw_overlay_panel(surf, panel, title="FIRST TIME")
    btns = draw_top_bar(surf, "Welcome", mouse_pos, right_icons=(("quit", "X", True),))
    draw_text(surf, "Have you played Fabled before?", font_headline(30, bold=True), UI_TEXT, (panel.centerx, panel.y + 74), center=True)
    _draw_wrapped_lines(
        surf,
        ["If you are new, we will open a guided 10-encounter tutorial. If not, we will skip it and grant the same starting gold reward."],
        panel.x + 54,
        panel.y + 126,
        panel.width - 108,
        font=font_body(15),
        color=UI_TEXT_SOFT,
        line_height=20,
    )
    yes_rect = pygame.Rect(panel.x + 92, panel.bottom - 94, 236, 48)
    no_rect = pygame.Rect(panel.right - 328, panel.bottom - 94, 236, 48)
    draw_secondary_button(surf, yes_rect, mouse_pos, "Yes, Skip Tutorial")
    draw_primary_button(surf, no_rect, mouse_pos, "No, Teach Me")
    btns["played_before"] = yes_rect
    btns["new_to_fabled"] = no_rect
    return btns


def draw_tutorial_briefing(surf, mouse_pos, title: str, lines: list[str], *, continue_label: str = "Continue"):
    draw_background(surf, "quest")
    panel = pygame.Rect(212, 124, 976, 620)
    _draw_overlay_panel(surf, panel, title="TUTORIAL")
    btns = draw_top_bar(surf, title, mouse_pos, left_icon="<", right_icons=(("quit", "X", True),))
    btns["back"] = btns.pop("left")
    draw_text(surf, title, font_headline(34, bold=True), UI_GOLD_BRIGHT, (panel.x + 42, panel.y + 56))
    _draw_wrapped_lines(
        surf,
        lines,
        panel.x + 42,
        panel.y + 116,
        panel.width - 84,
        font=font_body(16),
        color=UI_TEXT_SOFT,
        line_height=24,
    )
    continue_rect = pygame.Rect(panel.right - 244, panel.bottom - 70, 200, 42)
    draw_primary_button(surf, continue_rect, mouse_pos, continue_label)
    btns["continue"] = continue_rect
    return btns


def draw_player_menu(
    surf,
    mouse_pos,
    profile,
    note_lines: list[str] | None = None,
    *,
    favorite_adventurer_id: str | None = None,
    favorite_pool_ids: list[str] | None = None,
):
    draw_background(surf, "guild")
    panel = pygame.Rect(40, 84, 820, 764)
    _draw_overlay_panel(surf, panel, title="PROFILE")
    btns = draw_top_bar(surf, "Profile", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")

    avatar_rect = pygame.Rect(panel.x + 28, panel.y + 42, 180, 220)
    _draw_avatar_stage(surf, avatar_rect, "YOU")
    draw_text(surf, "Guildmaster", font_headline(24, bold=True), UI_TEXT, (panel.x + 236, panel.y + 62))
    draw_text(surf, _rank_label(), font_body(14, bold=True), UI_GOLD, (panel.x + 236, panel.y + 98))
    level_info = level_state(getattr(profile, "player_exp", 0))
    draw_text(surf, str(level_info.level), font_headline(26, bold=True), UI_TEXT, (panel.x + 236, panel.y + 132))
    draw_meter(
        surf,
        pygame.Rect(panel.x + 236, panel.y + 172, 342, 10),
        level_info.current_level_exp,
        max(1, level_info.next_level_exp),
        fill=UI_GOLD,
    )
    draw_text(surf, f"{level_info.current_level_exp}/{level_info.next_level_exp}", font_label(10, bold=True), UI_TEXT_SOFT, (panel.x + 586, panel.y + 166), right=True)

    icon_y = panel.y + 262
    closet_rect = pygame.Rect(panel.x + 28, icon_y, 58, 58)
    friends_rect = pygame.Rect(panel.x + 96, icon_y, 58, 58)
    stats_rect = pygame.Rect(panel.x + 164, icon_y, 58, 58)
    draw_icon_button(surf, closet_rect, mouse_pos, "C", active=False)
    draw_icon_button(surf, friends_rect, mouse_pos, "F", active=False)
    draw_icon_button(surf, stats_rect, mouse_pos, "S", active=False)
    draw_text(surf, "Closet", font_label(10, bold=True), UI_TEXT_SOFT, (closet_rect.centerx, closet_rect.bottom + 8), center=True)
    draw_text(surf, "Friends", font_label(10, bold=True), UI_TEXT_SOFT, (friends_rect.centerx, friends_rect.bottom + 8), center=True)
    draw_text(surf, "Stats", font_label(10, bold=True), UI_TEXT_SOFT, (stats_rect.centerx, stats_rect.bottom + 8), center=True)

    lifetime_rect = pygame.Rect(panel.x + 28, panel.y + 362, panel.width - 56, 120)
    draw_beveled_panel(surf, lifetime_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
    stats_lines = [
        f"Ranked record {getattr(profile, 'ranked_total_wins', 0)}-{getattr(profile, 'ranked_total_losses', 0)}",
        f"Best quest run {getattr(profile, 'ranked_best_quest_wins', 0)} wins",
        f"Gold on hand {getattr(profile, 'gold', 0)}",
    ]
    for index, line in enumerate(stats_lines):
        draw_text(surf, line, font_body(14), UI_TEXT_SOFT, (lifetime_rect.x + 18, lifetime_rect.y + 24 + index * 26))

    favorite_rect = pygame.Rect(panel.x + 28, panel.y + 514, panel.width - 56, 190)
    draw_beveled_panel(surf, favorite_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    favorite = ADVENTURERS_BY_ID.get(favorite_adventurer_id or "")
    favorite_card_rect = None
    if favorite is not None:
        card_rect = pygame.Rect(favorite_rect.x + 18, favorite_rect.y + 20, 164, 150)
        draw_adventurer_card(surf, card_rect, mouse_pos, favorite, selected=True, small=True, tag_line="Favorite Adventurer")
        draw_text(surf, f"G {getattr(profile, 'gold', 0)}", font_body(16, bold=True), UI_GOLD, (favorite_rect.right - 18, favorite_rect.y + 24), right=True)
        favorite_card_rect = card_rect
    btns["favorite_card"] = favorite_rect
    btns["closet"] = closet_rect
    btns["friends"] = friends_rect
    if favorite is not None and favorite_card_rect is not None and favorite_card_rect.collidepoint(mouse_pos):
        _draw_adventurer_popout(surf, favorite_card_rect, favorite)
    return btns


def draw_friends_menu(
    surf,
    mouse_pos,
    friends,
    selected_index: int,
    edit_name: str,
    edit_ip: str,
    active_field: str | None,
    status_lines: list[str] | None = None,
    queued_ip: str = "",
):
    draw_background(surf, "guild")
    panel = pygame.Rect(52, 92, 780, 730)
    _draw_overlay_panel(surf, panel, title="FRIENDS")
    btns = draw_top_bar(surf, "Friends", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    list_rect = pygame.Rect(panel.x + 24, panel.y + 40, panel.width - 48, 470)
    edit_strip = pygame.Rect(panel.x + 24, panel.bottom - 156, panel.width - 48, 110)
    draw_beveled_panel(surf, list_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, edit_strip, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)

    entry_buttons = []
    if friends:
        selected_index = max(0, min(selected_index, len(friends) - 1))
        for index, friend in enumerate(friends[:6]):
            row = pygame.Rect(list_rect.x + 12, list_rect.y + 16 + index * 70, list_rect.width - 24, 56)
            active = index == selected_index
            draw_beveled_panel(surf, row, fill_top=UI_BG_RAISED if active or row.collidepoint(mouse_pos) else UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if active else UI_GOLD_DIM)
            pygame.draw.circle(surf, UI_GREEN if index == selected_index else UI_TEXT_MUTE, (row.x + 18, row.centery), 5)
            draw_text(surf, friend["name"], font_body(14, bold=True), UI_TEXT, (row.x + 34, row.y + 12))
            draw_text(surf, friend["ip"], font_label(10, bold=True), UI_TEXT_MUTE, (row.x + 34, row.y + 32))
            entry_buttons.append((row, index))
    else:
        draw_text(surf, "No friends saved yet.", font_body(16, bold=True), UI_TEXT, (list_rect.x + 16, list_rect.y + 18))
        draw_text(surf, "Add one below to keep a LAN roster handy.", font_body(14), UI_TEXT_SOFT, (list_rect.x + 16, list_rect.y + 40))

    name_box = pygame.Rect(edit_strip.x + 14, edit_strip.y + 18, 250, 62)
    ip_box = pygame.Rect(edit_strip.x + 278, edit_strip.y + 18, 270, 62)
    save_btn = pygame.Rect(edit_strip.x + 566, edit_strip.y + 18, 52, 52)
    remove_btn = pygame.Rect(edit_strip.x + 626, edit_strip.y + 18, 52, 52)
    new_btn = pygame.Rect(edit_strip.x + 686, edit_strip.y + 18, 52, 52)
    draw_text_input(surf, name_box, mouse_pos, "Name", edit_name, active=active_field == "name", placeholder="Friend name")
    draw_text_input(surf, ip_box, mouse_pos, "IP", edit_ip, active=active_field == "ip", placeholder="Host IP")
    draw_icon_button(surf, save_btn, mouse_pos, "S", active=bool(edit_name.strip() and edit_ip.strip()))
    draw_icon_button(surf, remove_btn, mouse_pos, "D", danger=True)
    draw_icon_button(surf, new_btn, mouse_pos, "+")
    hint = queued_ip or (status_lines[0] if status_lines else "Select a friend to edit.")
    draw_text(surf, hint, font_body(13), UI_TEXT_SOFT, (edit_strip.x + 16, edit_strip.bottom - 24))

    btns["entries"] = entry_buttons
    btns["name_box"] = name_box
    btns["ip_box"] = ip_box
    btns["save"] = save_btn
    btns["remove"] = remove_btn
    btns["new"] = new_btn
    return btns


def draw_employee_config(surf, mouse_pos, employee_name: str, role_description: str, skills: list[dict], active_skill_id: str):
    draw_background(surf, "guild")
    panel = pygame.Rect(300, 210, 800, 420)
    _draw_overlay_panel(surf, panel, title="EMPLOYEE")
    btns = draw_top_bar(surf, employee_name, mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    portrait = pygame.Rect(panel.x + 26, panel.y + 58, 176, 238)
    _draw_avatar_stage(surf, portrait, employee_name[:2].upper())
    draw_text(surf, employee_name, font_headline(20, bold=True), UI_TEXT, (panel.x + 226, panel.y + 62))
    draw_text(surf, role_description, font_body(14), UI_TEXT_SOFT, (panel.x + 226, panel.y + 92))
    skill_buttons = []
    for index, skill in enumerate(skills[:5]):
        rect = pygame.Rect(panel.x + 226 + index * 110, panel.y + 148, 100, 146)
        active = skill["id"] == active_skill_id
        draw_beveled_panel(surf, rect, fill_top=UI_BG_RAISED if active or rect.collidepoint(mouse_pos) else UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if active else UI_GOLD_DIM)
        draw_text(surf, _ellipsize_text(skill["name"], font_body(13, bold=True), rect.width - 16), font_body(13, bold=True), UI_GOLD_BRIGHT if active else UI_TEXT, (rect.x + 10, rect.y + 12))
        _draw_wrapped_lines(surf, [skill["description"]], rect.x + 10, rect.y + 40, rect.width - 20, font=font_body(12), color=UI_TEXT_SOFT, line_height=16)
        skill_buttons.append((rect, skill["id"]))
    closet_rect = pygame.Rect(panel.x + 226, panel.bottom - 62, 180, 38)
    draw_secondary_button(surf, closet_rect, mouse_pos, "Change Skin")
    btns["skills"] = skill_buttons
    btns["closet"] = closet_rect
    return btns


def _draw_nav_icon(surf, rect, mouse_pos, label: str, *, active=False):
    draw_icon_button(surf, rect, mouse_pos, label, active=active)
    return rect


def _draw_pips(surf, start_x: int, y: int, count: int, filled: int, *, fill_color):
    for index in range(count):
        center = (start_x + index * 18, y)
        pygame.draw.circle(surf, fill_color if index < filled else UI_GOLD_DIM, center, 6, 0 if index < filled else 1)


def draw_quest_hub(
    surf,
    mouse_pos,
    *,
    run_active: bool,
    quest_wins: int,
    quest_losses: int,
    current_win_streak: int,
    current_loss_streak: int,
    party_ids: list[str] | None = None,
    favorite_id: str | None = None,
):
    draw_background(surf, "quest")
    btns = draw_top_bar(surf, "Quests", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    left_rect = pygame.Rect(54, 94, 292, 710)
    center_rect = pygame.Rect(370, 130, 960, 340)
    bottom_rect = pygame.Rect(370, 620, 960, 144)
    draw_beveled_panel(surf, left_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, center_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, bottom_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)

    party_ids = list(party_ids or [])
    favorite = ADVENTURERS_BY_ID.get(favorite_id or "")
    if run_active:
        draw_text(surf, "QUEST STATUS", font_label(11, bold=True), UI_TEXT_MUTE, (left_rect.x + 18, left_rect.y + 18))
        draw_text(surf, str(quest_wins), font_headline(28, bold=True), UI_GOLD_BRIGHT, (left_rect.x + 18, left_rect.y + 54))
        draw_text(surf, "wins", font_label(10, bold=True), UI_TEXT_SOFT, (left_rect.x + 62, left_rect.y + 66))
        _draw_pips(surf, left_rect.x + 24, left_rect.y + 108, 3, quest_losses, fill_color=UI_RED)
        draw_text(surf, "losses", font_label(10, bold=True), UI_TEXT_SOFT, (left_rect.x + 18, left_rect.y + 126))
        flame_count = min(5, max(current_win_streak, current_loss_streak))
        for index in range(flame_count):
            color = UI_GOLD_BRIGHT if current_win_streak >= current_loss_streak else UI_RED
            draw_chip(surf, pygame.Rect(left_rect.x + 18 + index * 34, left_rect.y + 168, 26, 22), "!", color)
        draw_text(surf, f"G {quest_wins * 50}", font_body(16, bold=True), UI_GOLD, (left_rect.x + 18, left_rect.y + 224))
        draw_text(surf, f"Artifacts {sum(1 for _ in party_ids)}", font_body(14), UI_TEXT_SOFT, (left_rect.x + 18, left_rect.y + 252))
    else:
        begin_rect = pygame.Rect(left_rect.x + 18, left_rect.y + 24, left_rect.width - 36, 48)
        draw_primary_button(surf, begin_rect, mouse_pos, "Begin Quest")
        btns["current_quest"] = begin_rect
        btns["advance"] = begin_rect
        if favorite is not None:
            draw_text(surf, "Favorite", font_label(10, bold=True), UI_TEXT_MUTE, (left_rect.x + 18, left_rect.y + 108))
            draw_adventurer_card(surf, pygame.Rect(left_rect.x + 18, left_rect.y + 128, left_rect.width - 36, 200), mouse_pos, favorite, selected=True, small=False)

    draw_text(surf, "PARTY", font_label(11, bold=True), UI_TEXT_MUTE, (center_rect.x + 18, center_rect.y + 18))
    hover_card = None
    card_buttons = []
    for index, adventurer_id in enumerate(party_ids[:6]):
        adventurer = ADVENTURERS_BY_ID.get(adventurer_id)
        if adventurer is None:
            continue
        rect = pygame.Rect(center_rect.x + 18 + index * 156, center_rect.y + 78, 136, 186)
        draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=False, small=True)
        card_buttons.append((rect, index))
        if rect.collidepoint(mouse_pos):
            hover_card = adventurer
    if hover_card is not None:
        _draw_adventurer_popout(surf, pygame.Rect(mouse_pos[0] - 10, mouse_pos[1] - 10, 20, 20), hover_card)

    training_rect = pygame.Rect(center_rect.right - 144, center_rect.y + 16, 40, 40)
    catalog_rect = pygame.Rect(center_rect.right - 96, center_rect.y + 16, 40, 40)
    shop_rect = pygame.Rect(center_rect.right - 48, center_rect.y + 16, 40, 40)
    _draw_nav_icon(surf, training_rect, mouse_pos, "T")
    _draw_nav_icon(surf, catalog_rect, mouse_pos, "C")
    _draw_nav_icon(surf, shop_rect, mouse_pos, "A")

    prepare_rect = pygame.Rect(bottom_rect.x + 18, bottom_rect.y + 44, 280, 48)
    edit_rect = pygame.Rect(bottom_rect.x + 314, bottom_rect.y + 44, 220, 48)
    forfeit_rect = pygame.Rect(bottom_rect.x + 554, bottom_rect.y + 56, 120, 24)
    if run_active:
        draw_primary_button(surf, prepare_rect, mouse_pos, "Prepare Encounter")
        draw_secondary_button(surf, edit_rect, mouse_pos, "Edit Loadouts")
        draw_text(surf, "Forfeit", font_body(13), UI_TEXT_SOFT if not forfeit_rect.collidepoint(mouse_pos) else UI_GOLD_BRIGHT, (forfeit_rect.x, forfeit_rect.y))
        btns["edit_loadouts"] = edit_rect
        btns["forfeit"] = forfeit_rect
    else:
        draw_primary_button(surf, prepare_rect, mouse_pos, "Begin Quest")
        draw_secondary_button(surf, edit_rect, mouse_pos, "Loadouts Locked", active=False)
        btns["edit_loadouts"] = edit_rect
    btns["advance"] = prepare_rect
    btns["current_quest"] = prepare_rect
    btns["party_cards"] = card_buttons
    btns["training_grounds"] = training_rect
    btns["catalog"] = catalog_rect
    btns["shops"] = shop_rect
    return btns


def draw_quests_menu(surf, mouse_pos, **kwargs):
    return draw_quest_hub(surf, mouse_pos, **kwargs)


def draw_training_grounds(surf, mouse_pos, *, training_favorite_id: str | None = None, roster_scroll: int = 0):
    draw_background(surf, "guild")
    btns = draw_top_bar(surf, "Training", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    roster_rect = pygame.Rect(48, 96, 456, 748)
    detail_rect = pygame.Rect(540, 96, 812, 748)
    draw_beveled_panel(surf, roster_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, detail_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    adventurers = list(ADVENTURERS_BY_ID.values())
    max_scroll = max(0, len(adventurers) - 9)
    roster_scroll = max(0, min(roster_scroll, max_scroll))
    visible = adventurers[roster_scroll:roster_scroll + 9]
    selected = ADVENTURERS_BY_ID.get(training_favorite_id or "", visible[0] if visible else None)
    card_buttons = []
    hover_adv = None
    hovered_weapon = None
    weapon_buttons = []
    for index, adventurer in enumerate(visible):
        row = index // 3
        col = index % 3
        rect = pygame.Rect(roster_rect.x + 18 + col * 140, roster_rect.y + 18 + row * 194, 122, 172)
        draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=selected is not None and adventurer.id == selected.id, small=True)
        card_buttons.append((rect, adventurer.id))
        if rect.collidepoint(mouse_pos):
            hover_adv = adventurer
    if hover_adv is not None:
        _draw_adventurer_popout(surf, pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1), hover_adv)

    if selected is not None:
        portrait_rect = pygame.Rect(detail_rect.x + 24, detail_rect.y + 24, 260, 304)
        _draw_portrait_block(surf, portrait_rect, "FOCUS", accent=_class_tint(selected.signature_weapons[0].kind.title()), initials="".join(part[0] for part in selected.name.split()[:2]).upper())
        draw_text(surf, selected.name, font_headline(26, bold=True), UI_TEXT, (detail_rect.x + 314, detail_rect.y + 32))
        draw_text(surf, f"HP {selected.hp}   ATK {selected.attack}   DEF {selected.defense}   SPD {selected.speed}", font_body(16, bold=True), UI_TEXT_SOFT, (detail_rect.x + 314, detail_rect.y + 74))
        draw_text(surf, selected.innate.name, font_body(15, bold=True), UI_GOLD_BRIGHT, (detail_rect.x + 314, detail_rect.y + 112))
        _draw_wrapped_lines(surf, [selected.innate.description], detail_rect.x + 314, detail_rect.y + 138, detail_rect.width - 338, font=font_body(14), color=UI_TEXT_SOFT, line_height=18)
        for index, weapon in enumerate(selected.signature_weapons[:2]):
            rect = pygame.Rect(detail_rect.x + 314, detail_rect.y + 232 + index * 120, 420, 98)
            draw_beveled_panel(surf, rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
            draw_text(surf, _ellipsize_text(weapon.name, font_body(16, bold=True), rect.width - 24), font_body(16, bold=True), UI_TEXT, (rect.x + 12, rect.y + 12))
            draw_text(surf, f"{weapon.kind.title()}  Power {weapon.strike.power}", font_label(10, bold=True), UI_GOLD, (rect.x + 12, rect.y + 34))
            detail_lines = _weapon_detail_lines(weapon)[1:3]
            _draw_wrapped_lines(surf, detail_lines or [_effect_text(weapon.strike)], rect.x + 12, rect.y + 52, rect.width - 24, font=font_body(12), color=UI_TEXT_SOFT, line_height=14)
            weapon_buttons.append((rect, weapon.id))
            if rect.collidepoint(mouse_pos):
                hovered_weapon = weapon
        draw_text(surf, selected.ultimate.name, font_body(15, bold=True), UI_GOLD_BRIGHT, (detail_rect.x + 314, detail_rect.bottom - 136))
        _draw_wrapped_lines(surf, [selected.ultimate.description or selected.ultimate.name], detail_rect.x + 314, detail_rect.bottom - 112, detail_rect.width - 338, font=font_body(14), color=UI_TEXT_SOFT, line_height=18)
    if hovered_weapon is not None:
        _draw_info_popout(surf, pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1), hovered_weapon.name, _weapon_detail_lines(hovered_weapon))
    ai_btn = pygame.Rect(detail_rect.right - 262, detail_rect.bottom - 92, 240, 44)
    lan_btn = pygame.Rect(detail_rect.right - 262, detail_rect.bottom - 40, 240, 44)
    focus_btn = pygame.Rect(detail_rect.x + 24, detail_rect.bottom - 52, 160, 36)
    draw_primary_button(surf, ai_btn, mouse_pos, "Practice vs AI")
    draw_secondary_button(surf, lan_btn, mouse_pos, "Practice vs Friend")
    draw_secondary_button(surf, focus_btn, mouse_pos, "Set Favorite")
    btns["training_cards"] = card_buttons
    btns["weapon_cards"] = weapon_buttons
    btns["vs_ai"] = ai_btn
    btns["vs_lan"] = lan_btn
    btns["training_focus"] = focus_btn
    btns["training_scroll_max"] = max_scroll
    return btns


def draw_favored_adventurer_select(
    surf,
    mouse_pos,
    favorite_pool_ids: list[str],
    focused_id: str | None,
    selected_id: str | None,
    *,
    scroll: int = 0,
):
    draw_background(surf, "guild")
    panel = pygame.Rect(160, 90, 1080, 760)
    _draw_overlay_panel(surf, panel, title="FAVORITE")
    btns = draw_top_bar(surf, "Favorite Adventurer", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    pool = [adventurer_id for adventurer_id in favorite_pool_ids if adventurer_id in ADVENTURERS_BY_ID]
    max_scroll = max(0, len(pool) - 9)
    scroll = max(0, min(scroll, max_scroll))
    visible = pool[scroll:scroll + 9]
    card_buttons = []
    focus = ADVENTURERS_BY_ID.get(focused_id or "", ADVENTURERS_BY_ID.get(visible[0], None) if visible else None)
    hover_adventurer = None
    for index, adventurer_id in enumerate(visible):
        adventurer = ADVENTURERS_BY_ID[adventurer_id]
        row = index // 3
        col = index % 3
        rect = pygame.Rect(panel.x + 24 + col * 218, panel.y + 54 + row * 214, 194, 182)
        draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=focus is not None and adventurer.id == focus.id, small=True, tag_line="Current Favorite" if adventurer.id == selected_id else None)
        card_buttons.append((rect, adventurer_id))
        if rect.collidepoint(mouse_pos):
            hover_adventurer = adventurer
    confirm_rect = pygame.Rect(panel.right - 250, panel.bottom - 62, 220, 40)
    draw_primary_button(surf, confirm_rect, mouse_pos, "Confirm Favorite", disabled=focus is None)
    btns["cards"] = card_buttons
    btns["confirm"] = confirm_rect
    if hover_adventurer is not None:
        _draw_adventurer_popout(surf, pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1), hover_adventurer)
    return btns


def draw_quest_draft(
    surf,
    mouse_pos,
    offer_ids,
    focused_id,
    selected_ids,
    *,
    detail_scroll: int = 0,
    title: str = "Encounter Prep",
    enemy_party_ids: list[str] | None = None,
    card_scroll: int = 0,
    allow_text_import: bool = False,
    import_open: bool = False,
    import_text: str = "",
    import_status_lines: list[str] | None = None,
    target_count: int = 3,
    continue_label: str = "Continue To Loadouts",
    selected_panel_title: str = "Encounter Team (Click To Remove)",
    side_panel_title: str = "Enemy Party",
    side_panel_caption: str | None = None,
    side_panel_lines: list[str] | None = None,
    adventurer_lookup=None,
):
    adventurer_lookup = adventurer_lookup or ADVENTURERS_BY_ID
    draw_background(surf, "quest")
    btns = draw_top_bar(surf, title, mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    cards = []
    hover_adventurer = None
    focused_id = focused_id if focused_id in adventurer_lookup else (offer_ids[0] if offer_ids else None)
    focused = adventurer_lookup.get(focused_id or "")
    if target_count > 3:
        grid_rect = pygame.Rect(220, 120, 720, 620)
        picks_rect = pygame.Rect(980, 120, 280, 620)
        draw_beveled_panel(surf, grid_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        draw_beveled_panel(surf, picks_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
        visible_offer_ids = list(offer_ids[:9])
        for index, adventurer_id in enumerate(visible_offer_ids):
            adventurer = adventurer_lookup[adventurer_id]
            row = index // 3
            col = index % 3
            rect = pygame.Rect(grid_rect.x + 20 + col * 228, grid_rect.y + 20 + row * 198, 192, 172)
            draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=adventurer_id == focused_id, unavailable=adventurer_id in selected_ids, small=True)
            cards.append((rect, adventurer_id))
            if rect.collidepoint(mouse_pos):
                hover_adventurer = adventurer
        slot_buttons = []
        for index, adventurer_id in enumerate(selected_ids[:target_count]):
            adventurer = adventurer_lookup[adventurer_id]
            rect = pygame.Rect(picks_rect.x + 20, picks_rect.y + 26 + index * 96, picks_rect.width - 40, 78)
            draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=True, small=True)
            slot_buttons.append((rect, adventurer_id))
            if rect.collidepoint(mouse_pos):
                hover_adventurer = adventurer
        if focused is not None:
            favorite_rect = pygame.Rect(40, 118, 150, 196)
            draw_adventurer_card(surf, favorite_rect, mouse_pos, focused, selected=True, small=True, tag_line="Pinned")
            if favorite_rect.collidepoint(mouse_pos):
                hover_adventurer = focused
        pick_rect = pygame.Rect(220, 764, 220, 42)
        continue_rect = pygame.Rect(1040, 764, 220, 42)
        draw_secondary_button(surf, pick_rect, mouse_pos, "Pick")
        draw_primary_button(surf, continue_rect, mouse_pos, continue_label, disabled=len(selected_ids) != target_count)
        btns["party_slots"] = slot_buttons
    else:
        enemy_rect = pygame.Rect(230, 98, 940, 140)
        bench_rect = pygame.Rect(180, 276, 1040, 290)
        picks_rect = pygame.Rect(430, 604, 540, 190)
        draw_beveled_panel(surf, enemy_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
        draw_beveled_panel(surf, bench_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        draw_beveled_panel(surf, picks_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
        draw_text(surf, side_panel_title, font_label(11, bold=True), UI_TEXT_MUTE, (enemy_rect.x + 16, enemy_rect.y + 14))
        enemy_card_top = enemy_rect.y + 34
        if side_panel_caption:
            draw_text(
                surf,
                _ellipsize_text(side_panel_caption.upper(), font_label(10, bold=True), enemy_rect.width - 32),
                font_label(10, bold=True),
                UI_GOLD,
                (enemy_rect.x + 16, enemy_rect.y + 30),
            )
            enemy_card_top = enemy_rect.y + 48
        if enemy_party_ids and side_panel_lines:
            locale_line = side_panel_lines[0]
            draw_text(
                surf,
                _ellipsize_text(locale_line, font_body(12), enemy_rect.width - 32),
                font_body(12),
                UI_TEXT_SOFT,
                (enemy_rect.x + 16, enemy_card_top),
            )
            enemy_card_top += 16
        enemy_buttons = []
        for index, adventurer_id in enumerate((enemy_party_ids or [])[:3]):
            adventurer = adventurer_lookup.get(adventurer_id)
            if adventurer is None:
                continue
            rect = pygame.Rect(enemy_rect.x + 18 + index * 304, enemy_card_top, 286, 62 if side_panel_caption or side_panel_lines else 86)
            draw_beveled_panel(surf, rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
            draw_text(surf, _ellipsize_text(adventurer.name, font_body(14, bold=True), rect.width - 20), font_body(14, bold=True), UI_TEXT, (rect.x + 12, rect.y + 12))
            draw_text(surf, ", ".join(role_tags_for_adventurer(adventurer)[:2]), font_label(10, bold=True), UI_TEXT_SOFT, (rect.x + 12, rect.y + 36))
            enemy_buttons.append((rect, adventurer_id))
            if rect.collidepoint(mouse_pos):
                hover_adventurer = adventurer
        if not enemy_buttons and side_panel_lines:
            y = enemy_rect.y + 18
            for index, line in enumerate(side_panel_lines[:4]):
                wrapped = _wrap_text_block(line, font_body(13, bold=index == 0), enemy_rect.width - 30)
                for wrapped_line in wrapped:
                    draw_text(
                        surf,
                        wrapped_line,
                        font_body(13, bold=index == 0),
                        UI_GOLD_BRIGHT if index == 0 else UI_TEXT_SOFT,
                        (enemy_rect.x + 15, y),
                    )
                    y += 18
                y += 4
        for index, adventurer_id in enumerate(offer_ids[:6]):
            adventurer = adventurer_lookup[adventurer_id]
            rect = pygame.Rect(bench_rect.x + 18 + index * 170, bench_rect.y + 54, 152, 204)
            draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=adventurer_id == focused_id, unavailable=adventurer_id in selected_ids, small=True)
            cards.append((rect, adventurer_id))
            if rect.collidepoint(mouse_pos):
                hover_adventurer = adventurer
        slot_buttons = []
        slot_positions = [
            pygame.Rect(picks_rect.centerx - 72, picks_rect.y + 88, 144, 82),
            pygame.Rect(picks_rect.x + 38, picks_rect.y + 26, 144, 82),
            pygame.Rect(picks_rect.right - 182, picks_rect.y + 26, 144, 82),
        ]
        for index, rect in enumerate(slot_positions):
            if index < len(selected_ids):
                adventurer = adventurer_lookup[selected_ids[index]]
                draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=True, small=True)
                slot_buttons.append((rect, selected_ids[index]))
                if rect.collidepoint(mouse_pos):
                    hover_adventurer = adventurer
            else:
                draw_beveled_panel(surf, rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        pick_rect = pygame.Rect(230, 804, 220, 42)
        continue_rect = pygame.Rect(950, 804, 220, 42)
        draw_secondary_button(surf, pick_rect, mouse_pos, "Select")
        draw_primary_button(surf, continue_rect, mouse_pos, continue_label, disabled=len(selected_ids) != target_count)
        btns["party_slots"] = slot_buttons
        btns["enemy_cards"] = enemy_buttons
    if import_open:
        modal = pygame.Rect(380, 210, 640, 300)
        _draw_overlay_panel(surf, modal, title="IMPORT")
        text_box = pygame.Rect(modal.x + 18, modal.y + 54, modal.width - 36, 120)
        draw_beveled_panel(surf, text_box, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
        preview = import_text[:200] if import_text else "Paste a team block here."
        _draw_wrapped_lines(surf, [preview], text_box.x + 12, text_box.y + 12, text_box.width - 24, font=font_body(13), color=UI_TEXT if import_text else UI_TEXT_MUTE, line_height=16)
        cancel_rect = pygame.Rect(modal.x + 18, modal.bottom - 52, 120, 34)
        clear_rect = pygame.Rect(modal.x + 148, modal.bottom - 52, 120, 34)
        paste_rect = pygame.Rect(modal.x + 278, modal.bottom - 52, 120, 34)
        apply_rect = pygame.Rect(modal.right - 138, modal.bottom - 52, 120, 34)
        draw_secondary_button(surf, cancel_rect, mouse_pos, "Close")
        draw_secondary_button(surf, clear_rect, mouse_pos, "Clear")
        draw_secondary_button(surf, paste_rect, mouse_pos, "Paste")
        draw_primary_button(surf, apply_rect, mouse_pos, "Apply")
        btns["import_cancel"] = cancel_rect
        btns["import_clear"] = clear_rect
        btns["import_paste"] = paste_rect
        btns["import_apply"] = apply_rect
    elif allow_text_import:
        import_rect = pygame.Rect(46, 804, 140, 36)
        draw_secondary_button(surf, import_rect, mouse_pos, "Import Team")
        btns["import_team"] = import_rect
    btns["cards"] = cards
    btns["pick"] = pick_rect
    btns["continue"] = continue_rect
    if hover_adventurer is not None:
        _draw_adventurer_popout(surf, pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1), hover_adventurer)
    return btns


def draw_market(
    surf,
    mouse_pos,
    active_tab: str,
    item_scroll: int,
    profile,
    focus_id: str | None,
    status_message: str,
    owned_cosmetics: set[str] | None = None,
):
    draw_background(surf, "market")
    btns = draw_top_bar(surf, "Market", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    tabs_rect = pygame.Rect(54, 118, 72, 660)
    grid_rect = pygame.Rect(150, 118, 756, 660)
    preview_rect = pygame.Rect(934, 168, 372, 560)
    draw_beveled_panel(surf, tabs_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, grid_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, preview_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
    tab_buttons = []
    for index, tab_name in enumerate(MARKET_TABS):
        rect = pygame.Rect(tabs_rect.x + 16, tabs_rect.y + 16 + index * 54, 40, 40)
        _draw_nav_icon(surf, rect, mouse_pos, UI_TAB_ICONS.get(tab_name, tab_name[:1]), active=tab_name == active_tab)
        tab_buttons.append((rect, tab_name))
    items = market_items_for_tab(active_tab)
    owned_cosmetics = owned_cosmetics or set()
    item_buttons = []
    selected_item = next((item for item in items if item["id"] == focus_id), items[0] if items else None)
    for index, item in enumerate(items[:6]):
        row = index // 3
        col = index % 3
        rect = pygame.Rect(grid_rect.x + 18 + col * 242, grid_rect.y + 20 + row * 236, 224, 214)
        owned = item["id"] in owned_cosmetics
        equipped = owned and item["id"] == _market_equipped_id_for_item(profile, item)
        draw_beveled_panel(surf, rect, fill_top=UI_BG_RAISED if selected_item is not None and selected_item["id"] == item["id"] else UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if selected_item is not None and selected_item["id"] == item["id"] else UI_GOLD_DIM)
        _draw_portrait_block(surf, pygame.Rect(rect.x + 12, rect.y + 12, rect.width - 24, 112), UI_TAB_ICONS.get(active_tab, "I"), accent=UI_GOLD, initials=UI_TAB_ICONS.get(active_tab, "I"))
        draw_text(surf, _ellipsize_text(item["name"], font_body(14, bold=True), rect.width - 24), font_body(14, bold=True), UI_TEXT, (rect.x + 12, rect.y + 136))
        draw_text(surf, f"G {item['price']}", font_label(10, bold=True), UI_GOLD, (rect.x + 12, rect.y + 160))
        if equipped:
            draw_chip(surf, pygame.Rect(rect.right - 68, rect.y + 12, 56, 20), "EQUIP", UI_GREEN)
        elif owned:
            draw_chip(surf, pygame.Rect(rect.right - 68, rect.y + 12, 56, 20), "OWNED", UI_GREEN)
        item_buttons.append((rect, item["id"]))
    if not items:
        draw_text(surf, market_tab_note(active_tab) or "New wares are being unpacked.", font_body(16), UI_TEXT_SOFT, (grid_rect.x + 24, grid_rect.y + 28))
    buy_rect = pygame.Rect(preview_rect.x + 24, preview_rect.bottom - 54, preview_rect.width - 48, 38)
    if selected_item is not None:
        _draw_portrait_block(surf, pygame.Rect(preview_rect.x + 24, preview_rect.y + 24, preview_rect.width - 48, 210), UI_TAB_ICONS.get(active_tab, "I"), accent=UI_GOLD, initials=UI_TAB_ICONS.get(active_tab, "I"))
        draw_text(surf, selected_item["name"], font_headline(20, bold=True), UI_TEXT, (preview_rect.x + 24, preview_rect.y + 252))
        draw_text(surf, active_tab, font_label(10, bold=True), UI_GOLD, (preview_rect.x + 24, preview_rect.y + 286))
        draw_text(surf, f"G {selected_item['price']}", font_body(16, bold=True), UI_GOLD, (preview_rect.x + 24, preview_rect.y + 316))
        _draw_wrapped_lines(surf, [selected_item.get("subtitle", market_tab_note(active_tab) or "Preview")], preview_rect.x + 24, preview_rect.y + 350, preview_rect.width - 48, font=font_body(14), color=UI_TEXT_SOFT, line_height=18)
        draw_primary_button(surf, buy_rect, mouse_pos, "Equip" if selected_item["id"] in owned_cosmetics else "Buy")
    else:
        draw_text(surf, "Select an item to preview it.", font_body(16), UI_TEXT_SOFT, (preview_rect.x + 24, preview_rect.y + 28))
        draw_primary_button(surf, buy_rect, mouse_pos, "Buy", disabled=True)
    btns["tabs"] = tab_buttons
    btns["items"] = item_buttons
    btns["packages"] = []
    btns["buy"] = buy_rect
    btns["market_scroll_max"] = max(0, len(items) - 6)
    return btns


def draw_closet(
    surf,
    mouse_pos,
    active_tab: str,
    items: list[dict],
    focus_id: str | None,
    owned_cosmetics: set[str] | None = None,
    profile=None,
    *,
    item_scroll: int = 0,
):
    draw_background(surf, "guild")
    panel = pygame.Rect(130, 86, 1140, 764)
    _draw_overlay_panel(surf, panel, title="CLOSET")
    btns = draw_top_bar(surf, "Closet", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    rail_rect = pygame.Rect(panel.x + 20, panel.y + 46, 66, panel.height - 92)
    grid_rect = pygame.Rect(panel.x + 112, panel.y + 46, 604, panel.height - 92)
    preview_rect = pygame.Rect(panel.x + 740, panel.y + 46, 370, panel.height - 92)
    draw_beveled_panel(surf, rail_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, grid_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, preview_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
    category_buttons = []
    for index, tab_name in enumerate(CLOSET_TABS):
        rect = pygame.Rect(rail_rect.x + 13, rail_rect.y + 14 + index * 52, 40, 40)
        _draw_nav_icon(surf, rect, mouse_pos, UI_TAB_ICONS.get(tab_name, tab_name[:1]), active=tab_name == active_tab)
        category_buttons.append((rect, tab_name))
    visible_items = [item for item in items if item["id"] in (owned_cosmetics or set())]
    selected_item = next((item for item in visible_items if item["id"] == focus_id), visible_items[0] if visible_items else None)
    item_buttons = []
    for index, item in enumerate(visible_items[:6]):
        row = index // 2
        col = index % 2
        rect = pygame.Rect(grid_rect.x + 20 + col * 286, grid_rect.y + 20 + row * 220, 266, 198)
        equipped = profile is not None and item["id"] == _market_equipped_id_for_item(profile, item)
        draw_beveled_panel(surf, rect, fill_top=UI_BG_RAISED if selected_item is not None and item["id"] == selected_item["id"] else UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if equipped else UI_GOLD_DIM)
        _draw_portrait_block(surf, pygame.Rect(rect.x + 12, rect.y + 12, rect.width - 24, 108), UI_TAB_ICONS.get(active_tab, "I"), accent=UI_GOLD, initials=UI_TAB_ICONS.get(active_tab, "I"))
        draw_text(surf, _ellipsize_text(item["name"], font_body(14, bold=True), rect.width - 24), font_body(14, bold=True), UI_TEXT, (rect.x + 12, rect.y + 134))
        if equipped:
            draw_chip(surf, pygame.Rect(rect.right - 72, rect.y + 12, 60, 20), "EQUIP", UI_GOLD)
        item_buttons.append((rect, item["id"], index))
    if selected_item is not None:
        _draw_portrait_block(surf, pygame.Rect(preview_rect.x + 24, preview_rect.y + 24, preview_rect.width - 48, 230), UI_TAB_ICONS.get(active_tab, "I"), accent=UI_GOLD, initials="YOU")
        draw_text(surf, selected_item["name"], font_headline(20, bold=True), UI_TEXT, (preview_rect.x + 24, preview_rect.y + 274))
        equip_rect = pygame.Rect(preview_rect.x + 24, preview_rect.bottom - 54, preview_rect.width - 48, 38)
        draw_primary_button(surf, equip_rect, mouse_pos, "Equip")
    else:
        equip_rect = pygame.Rect(preview_rect.x + 24, preview_rect.bottom - 54, preview_rect.width - 48, 38)
        draw_primary_button(surf, equip_rect, mouse_pos, "Equip", disabled=True)
    btns["categories"] = category_buttons
    btns["items"] = item_buttons
    btns["equip"] = equip_rect
    btns["scroll_max"] = max(0, len(visible_items) - 6)
    return btns


def draw_catalog(
    surf,
    mouse_pos,
    section_index,
    entry_index,
    filters: dict[str, str] | None = None,
    *,
    scroll: int = 0,
    detail_scroll: int = 0,
    favorite_adventurer_id: str | None = None,
):
    draw_background(surf, "guild")
    btns = draw_top_bar(surf, "Codex", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    rail_rect = pygame.Rect(52, 96, 76, 744)
    filter_rect = pygame.Rect(150, 96, 1180, 88)
    grid_rect = pygame.Rect(150, 206, 690, 634)
    detail_rect = pygame.Rect(868, 96, 462, 744)
    draw_beveled_panel(surf, rail_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, filter_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, grid_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, detail_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
    section_buttons = []
    section_index = max(0, min(section_index, len(CATALOG_SECTIONS) - 1))
    section_labels = ["A", "T", "R"]
    for index, name in enumerate(CATALOG_SECTIONS):
        rect = pygame.Rect(rail_rect.x + 18, rail_rect.y + 18 + index * 56, 40, 40)
        _draw_nav_icon(surf, rect, mouse_pos, section_labels[index] if index < len(section_labels) else name[:1], active=index == section_index)
        section_buttons.append((rect, index))
    section_name = CATALOG_SECTIONS[section_index]
    filter_defs = catalog_filter_definitions(section_name)
    filters = dict(filters or {})
    filter_buttons = []
    cursor_x = filter_rect.x + 18
    for definition in filter_defs:
        current_value = next((label for value, label in definition["options"] if str(value) == str(filters.get(definition["key"], definition["options"][0][0]))), definition["options"][0][1])
        label_rect = pygame.Rect(cursor_x, filter_rect.y + 22, 150, 42)
        draw_secondary_button(surf, label_rect, mouse_pos, f"{definition['label']}: {current_value}")
        filter_buttons.append((label_rect, definition["key"], 1))
        cursor_x += 162
    entries = catalog_entries(section_name, filters, favorite_adventurer_id=favorite_adventurer_id)
    entry_index = max(0, min(entry_index, len(entries) - 1)) if entries else 0
    entry_buttons = []
    for index, entry in enumerate(entries[:6]):
        row = index // 2
        col = index % 2
        rect = pygame.Rect(grid_rect.x + 18 + col * 332, grid_rect.y + 18 + row * 198, 314, 180)
        active = index == entry_index
        draw_beveled_panel(surf, rect, fill_top=UI_BG_RAISED if active else UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if active else UI_GOLD_DIM)
        _draw_portrait_block(surf, pygame.Rect(rect.x + 12, rect.y + 12, rect.width - 24, 84), section_labels[section_index] if section_index < len(section_labels) else "C", accent=UI_GOLD, initials=section_labels[section_index] if section_index < len(section_labels) else "C")
        draw_text(surf, _ellipsize_text(entry["title"], font_body(14, bold=True), rect.width - 24), font_body(14, bold=True), UI_TEXT, (rect.x + 12, rect.y + 108))
        _draw_wrapped_lines(surf, [entry["subtitle"]], rect.x + 12, rect.y + 132, rect.width - 24, font=font_body(12), color=UI_TEXT_SOFT, line_height=16)
        entry_buttons.append((rect, index))
    if entries:
        entry = entries[entry_index]
        draw_text(surf, entry["title"], font_headline(22, bold=True), UI_TEXT, (detail_rect.x + 20, detail_rect.y + 28))
        draw_text(surf, entry["subtitle"], font_label(10, bold=True), UI_GOLD, (detail_rect.x + 20, detail_rect.y + 60))
        detail_viewport = pygame.Rect(detail_rect.x + 20, detail_rect.y + 92, detail_rect.width - 40, detail_rect.height - 112)
        old_clip = surf.get_clip()
        surf.set_clip(detail_viewport)
        y = detail_viewport.y - detail_scroll
        for line in _wrap_multiline_block(entry["body"], font_body(15), detail_viewport.width, limit=240):
            if line:
                draw_text(surf, line, font_body(15), UI_TEXT_SOFT, (detail_viewport.x, y))
                y += 20
            else:
                y += 10
        surf.set_clip(old_clip)
        detail_scroll_max = max(0, y - detail_viewport.bottom)
    else:
        detail_viewport = pygame.Rect(detail_rect.x + 20, detail_rect.y + 92, detail_rect.width - 40, detail_rect.height - 112)
        draw_text(surf, "No entry selected.", font_body(15, bold=True), UI_TEXT, (detail_rect.x + 20, detail_rect.y + 28))
        detail_scroll_max = 0
    btns["sections"] = section_buttons
    btns["filters"] = filter_buttons
    btns["entries"] = entry_buttons
    btns["entries_viewport"] = grid_rect
    btns["entry_page_size"] = 6
    btns["entry_scroll_max"] = max(0, len(entries) - 6)
    btns["detail_viewport"] = detail_viewport
    btns["detail_scroll_max"] = detail_scroll_max
    return btns


def draw_lan_setup(
    surf,
    mouse_pos,
    title: str,
    mode_label: str,
    connection_mode: str,
    join_ip: str,
    local_ip: str,
    connected: bool,
    status_lines: list[str] | None = None,
):
    draw_background(surf, "guild")
    modal = pygame.Rect(450, 250, 500, 300)
    _draw_overlay_panel(surf, modal, title="LAN")
    btns = draw_top_bar(surf, title, mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    draw_text(surf, local_ip or "Waiting...", font_headline(22, bold=True), UI_GOLD_BRIGHT, (modal.centerx, modal.y + 48), center=True)
    draw_text(surf, "Share this with your friend", font_label(10, bold=True), UI_TEXT_MUTE, (modal.centerx, modal.y + 76), center=True)
    ip_box = pygame.Rect(modal.x + 34, modal.y + 112, modal.width - 68, 58)
    draw_text_input(surf, ip_box, mouse_pos, "Friend's IP", join_ip, active=connection_mode == "join", placeholder="Friend's IP")
    host_rect = pygame.Rect(modal.x + 34, modal.y + 196, 200, 40)
    join_rect = pygame.Rect(modal.right - 234, modal.y + 196, 200, 40)
    connect_rect = pygame.Rect(modal.x + 34, modal.bottom - 52, 200, 34)
    begin_rect = pygame.Rect(modal.right - 234, modal.bottom - 52, 200, 34)
    draw_secondary_button(surf, host_rect, mouse_pos, "Host", active=connection_mode == "host")
    draw_secondary_button(surf, join_rect, mouse_pos, "Join", active=connection_mode == "join")
    draw_secondary_button(surf, connect_rect, mouse_pos, "Connect", active=connection_mode == "join")
    draw_primary_button(surf, begin_rect, mouse_pos, "Begin", disabled=not connected)
    draw_text(surf, (status_lines or ["Awaiting connection."])[0], font_body(13), UI_GREEN if connected else UI_TEXT_SOFT, (modal.x + 34, modal.bottom - 86))
    btns["host"] = host_rect
    btns["join"] = join_rect
    btns["connect"] = connect_rect
    btns["begin"] = begin_rect
    btns["ip_box"] = ip_box
    return btns


def draw_story_settings(surf, mouse_pos, tutorials_enabled: bool, fast_resolution: bool, battle_log_popups: bool, screen_shake: bool):
    draw_background(surf, "guild")
    modal = pygame.Rect(450, 220, 500, 400)
    _draw_overlay_panel(surf, modal, title="SETTINGS")
    btns = draw_top_bar(surf, "Settings", mouse_pos, left_icon="<", right_icons=(("quit", "X", True),))
    btns["back"] = btns.pop("left")
    toggle_specs = [
        ("tutorials", "Tutorial Popups", tutorials_enabled),
        ("fast", "Fast Resolution", fast_resolution),
        ("battle_log_popups", "Battle Log Popups", battle_log_popups),
        ("screen_shake", "Screen Shake", screen_shake),
    ]
    for index, (key, label, state) in enumerate(toggle_specs):
        row = pygame.Rect(modal.x + 28, modal.y + 54 + index * 78, modal.width - 56, 52)
        draw_beveled_panel(surf, row, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        draw_text(surf, label, font_body(15, bold=True), UI_TEXT, (row.x + 14, row.y + 16))
        toggle_rect = pygame.Rect(row.right - 92, row.y + 12, 64, 28)
        draw_beveled_panel(surf, toggle_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_BRIGHT if state else UI_GOLD_DIM)
        knob_x = toggle_rect.right - 22 if state else toggle_rect.x + 22
        pygame.draw.circle(surf, UI_GOLD_BRIGHT if state else UI_TEXT_SOFT, (knob_x, toggle_rect.centery), 10)
        btns[key] = row
    return btns


def _loadout_skill_options(class_name: str) -> list:
    return list(CLASS_SKILLS.get(class_name, []))


def _loadout_artifact_options(class_name: str, allowed_artifact_ids=None, *, artifact_lookup=None) -> list[str]:
    artifact_lookup = artifact_lookup or ALL_ARTIFACTS_BY_ID
    artifact_ids = list(allowed_artifact_ids) if allowed_artifact_ids is not None else list(artifact_lookup)
    return [artifact_id for artifact_id in artifact_ids if artifact_id in artifact_lookup]


def _draw_party_loadout_summary_panel(surf, rect: pygame.Rect, members, selected_index: int):
    if not members:
        return
    selected_index = max(0, min(selected_index, len(members) - 1))
    member = members[selected_index]
    adventurer = ADVENTURERS_BY_ID[member["adventurer_id"]]
    class_name = member.get("class_name", NO_CLASS_NAME)
    class_skill = _selected_class_skill(class_name, member.get("class_skill_id"))
    primary_weapon = _active_weapon_for_member(member)
    secondary_weapon = _secondary_weapon_for_member(member)
    artifact = ALL_ARTIFACTS_BY_ID.get(member.get("artifact_id"))
    assigned_classes = sum(1 for item in members if item.get("class_name", NO_CLASS_NAME) not in {None, "", NO_CLASS_NAME})
    assigned_skills = sum(1 for item in members if item.get("class_skill_id"))
    equipped_artifacts = sum(1 for item in members if item.get("artifact_id"))

    preview = pygame.Rect(rect.x + 20, rect.y + 18, rect.width - 40, 122)
    _draw_portrait_block(
        surf,
        preview,
        class_name[:1] if class_name and class_name != NO_CLASS_NAME else "A",
        accent=_class_tint(class_name),
        initials="".join(part[0] for part in adventurer.name.split()[:2]).upper(),
        show_badge=False,
    )
    draw_text(surf, adventurer.name, font_body(18, bold=True), UI_TEXT, (rect.x + 20, preview.bottom + 18))
    draw_text(
        surf,
        class_name if class_name and class_name != NO_CLASS_NAME else "Class unassigned",
        font_label(10, bold=True),
        UI_GOLD if class_name and class_name != NO_CLASS_NAME else UI_TEXT_MUTE,
        (rect.x + 20, preview.bottom + 42),
    )

    summary_lines = [
        f"Primary  {primary_weapon.name}",
        f"Secondary  {secondary_weapon.name}",
        f"Skill  {class_skill.name if class_skill is not None else 'None selected'}",
        f"Artifact  {artifact.name if artifact is not None else 'Empty slot'}",
    ]
    _draw_wrapped_lines(
        surf,
        summary_lines,
        rect.x + 20,
        preview.bottom + 70,
        rect.width - 40,
        font=font_body(13),
        color=UI_TEXT_SOFT,
        line_height=24,
    )

    progress_y = rect.bottom - 118
    chip_gap = 10
    chip_w = (rect.width - 40 - chip_gap * 2) // 3
    chip_specs = [
        (f"{assigned_classes}/{len(members)}", "CLASS"),
        (f"{assigned_skills}/{len(members)}", "SKILL"),
        (f"{equipped_artifacts}/{len(members)}", "ART"),
    ]
    for index, (value, label) in enumerate(chip_specs):
        chip_rect = pygame.Rect(rect.x + 20 + index * (chip_w + chip_gap), progress_y, chip_w, 58)
        draw_beveled_panel(surf, chip_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        draw_text(surf, value, font_body(18, bold=True), UI_TEXT, (chip_rect.centerx, chip_rect.y + 16), center=True)
        draw_text(surf, label, font_label(9, bold=True), UI_TEXT_MUTE, (chip_rect.centerx, chip_rect.bottom - 12), center=True)


def _draw_loadout_editor_core(
    surf,
    mouse_pos,
    members,
    selected_index: int,
    *,
    rect: pygame.Rect,
    allowed_artifact_ids=None,
    editable=True,
    adventurer_lookup=None,
    artifact_lookup=None,
    loadout_options=None,
):
    adventurer_lookup = adventurer_lookup or ADVENTURERS_BY_ID
    artifact_lookup = artifact_lookup or ALL_ARTIFACTS_BY_ID
    loadout_options = loadout_options or {
        "show_secondary_weapon": True,
        "show_classes": True,
        "class_editable": editable,
        "max_skill_options": 2,
        "skills_editable": editable,
        "show_artifacts": True,
        "artifacts_editable": editable,
    }
    selected_index = max(0, min(selected_index, len(members) - 1)) if members else 0
    buttons = {"weapons": [], "classes": [], "skills": [], "artifacts": [], "viewport": rect, "scroll_max": 0}
    if not members:
        draw_text(surf, "No adventurers ready.", font_body(16, bold=True), UI_TEXT, (rect.x + 20, rect.y + 20))
        return buttons
    member = members[selected_index]
    adventurer = adventurer_lookup[member["adventurer_id"]]
    class_name = member.get("class_name", NO_CLASS_NAME)
    weapon = _active_weapon_for_member(member, adventurer_lookup=adventurer_lookup)
    alt_weapon = _secondary_weapon_for_member(member, adventurer_lookup=adventurer_lookup)
    class_skill = _selected_class_skill(class_name, member.get("class_skill_id"))
    hover_source = None
    hover_title = None
    hover_lines = None
    show_secondary_weapon = bool(loadout_options.get("show_secondary_weapon", True))
    show_classes = bool(loadout_options.get("show_classes", True))
    class_editable = bool(editable and loadout_options.get("class_editable", True))
    max_skill_options = max(0, int(loadout_options.get("max_skill_options", 2) or 0))
    skills_editable = bool(editable and loadout_options.get("skills_editable", True))
    show_artifacts = bool(loadout_options.get("show_artifacts", True))
    artifacts_editable = bool(editable and loadout_options.get("artifacts_editable", True))
    margin = 20
    gap = 18
    side_w = 174
    top_h = 292
    stat_h = 38
    skills_h = 76
    artifact_h = 62
    stack_bottom = rect.bottom - 28
    cursor_y = stack_bottom
    artifact_y = None
    if show_artifacts:
        artifact_y = cursor_y - artifact_h
        cursor_y = artifact_y - 18
    skills_y = None
    if max_skill_options > 0:
        skills_y = cursor_y - skills_h
        cursor_y = skills_y - 18
    stat_y = cursor_y - stat_h
    left_rect = pygame.Rect(rect.x + margin, rect.y + margin, side_w, top_h)
    right_rect = pygame.Rect(rect.right - margin - side_w, rect.y + margin, side_w, top_h)
    center_h = max(228, stat_y - (rect.y + margin) - 16)
    center_rect = pygame.Rect(left_rect.right + gap, rect.y + margin, rect.width - side_w * 2 - gap * 2 - margin * 2, center_h)

    draw_beveled_panel(surf, left_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, center_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, right_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)

    portrait_w = max(176, min(224, center_rect.width - 64))
    portrait_h = 132 if rect.height < 560 else 148
    portrait = pygame.Rect(center_rect.centerx - portrait_w // 2, center_rect.y + 18, portrait_w, portrait_h)
    _draw_portrait_block(
        surf,
        portrait,
        class_name[:1] if class_name and class_name != NO_CLASS_NAME else "A",
        accent=_class_tint(class_name),
        initials="".join(part[0] for part in adventurer.name.split()[:2]).upper(),
        show_badge=False,
    )
    draw_text(surf, adventurer.name, font_headline(22, bold=True), UI_TEXT, (center_rect.centerx, portrait.bottom + 16), center=True)
    stat_specs = [
        ("HP", adventurer.hp, UI_GREEN),
        ("ATK", adventurer.attack, UI_GOLD),
        ("DEF", adventurer.defense, UI_BLUE),
        ("SPD", adventurer.speed, UI_ORANGE),
    ]
    stat_gap = 10
    stat_w = min(78, (center_rect.width - 24 - stat_gap * 3) // 4)
    stat_start_x = center_rect.centerx - (stat_w * 4 + stat_gap * 3) // 2
    for index, (label, value, color) in enumerate(stat_specs):
        stat_rect = pygame.Rect(stat_start_x + index * (stat_w + stat_gap), stat_y, stat_w, stat_h)
        draw_beveled_panel(surf, stat_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=_lerp_color(color, UI_GOLD_DIM, 0.4))
        draw_text(surf, str(value), font_body(15, bold=True), UI_TEXT, (stat_rect.centerx, stat_rect.y + 11), center=True)
        draw_text(surf, label, font_label(8, bold=True), UI_TEXT_MUTE, (stat_rect.centerx, stat_rect.bottom - 8), center=True)

    innate_rect = pygame.Rect(center_rect.x + 16, center_rect.bottom - 70, center_rect.width - 32, 54)
    draw_beveled_panel(surf, innate_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
    draw_text(surf, adventurer.innate.name, font_body(13, bold=True), UI_GOLD, (innate_rect.centerx, innate_rect.y + 13), center=True)
    _draw_wrapped_lines(
        surf,
        [adventurer.innate.description],
        innate_rect.x + 12,
        innate_rect.y + 30,
        innate_rect.width - 24,
        font=font_body(11),
        color=UI_TEXT_SOFT,
        line_height=13,
    )

    weapon_inner_gap = 10
    card_count = 2 if show_secondary_weapon else 1
    weapon_h = (left_rect.height - 24 - weapon_inner_gap * (card_count - 1)) // card_count
    left_weapon = pygame.Rect(left_rect.x + 12, left_rect.y + 12, left_rect.width - 24, weapon_h)
    right_weapon = pygame.Rect(left_rect.x + 12, left_weapon.bottom + weapon_inner_gap, left_rect.width - 24, weapon_h)
    draw_beveled_panel(surf, left_weapon, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_BRIGHT)
    draw_text(surf, "PRIMARY", font_label(9, bold=True), UI_GOLD_BRIGHT, (left_weapon.x + 10, left_weapon.y + 9))
    draw_text(surf, _ellipsize_text(weapon.name, font_body(14, bold=True), left_weapon.width - 20), font_body(14, bold=True), UI_TEXT, (left_weapon.x + 10, left_weapon.y + 24))
    draw_text(surf, weapon.kind.title(), font_label(10, bold=True), UI_TEXT_SOFT, (left_weapon.x + 10, left_weapon.y + 42))
    if show_secondary_weapon:
        draw_beveled_panel(surf, right_weapon, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        draw_text(surf, "SECONDARY", font_label(9, bold=True), UI_TEXT_MUTE, (right_weapon.x + 10, right_weapon.y + 9))
        draw_text(surf, _ellipsize_text(alt_weapon.name, font_body(13, bold=True), right_weapon.width - 20), font_body(13, bold=True), UI_TEXT_SOFT, (right_weapon.x + 10, right_weapon.y + 24))
        draw_text(surf, alt_weapon.kind.title(), font_label(10, bold=True), UI_TEXT_MUTE, (right_weapon.x + 10, right_weapon.y + 42))
    detail_font = font_body(10)
    detail_line_height = 12
    detail_width = left_weapon.width - 20
    detail_top_offset = 56
    detail_max_lines = max(1, (left_weapon.height - detail_top_offset - 10) // detail_line_height)
    detail_cards = [(left_weapon, weapon, UI_TEXT_SOFT)]
    if show_secondary_weapon:
        detail_cards.append((right_weapon, alt_weapon, UI_TEXT_MUTE))
    for card_rect, detail_weapon, detail_color in detail_cards:
        detail_top = card_rect.y + detail_top_offset
        wrapped_lines = []
        raw_detail_lines = _weapon_card_detail_lines(detail_weapon)
        for raw_line in raw_detail_lines:
            wrapped_lines.extend(_wrap_text_block(raw_line, detail_font, detail_width))
        if len(wrapped_lines) > detail_max_lines:
            wrapped_lines = wrapped_lines[:detail_max_lines]
            wrapped_lines[-1] = _ellipsize_text(f"{wrapped_lines[-1]}...", detail_font, detail_width)
        for index, line in enumerate(wrapped_lines):
            draw_text(surf, line, detail_font, detail_color, (card_rect.x + 10, detail_top + index * detail_line_height))
    buttons["weapons"].append((left_weapon, weapon.id))
    if show_secondary_weapon:
        buttons["weapons"].append((right_weapon, alt_weapon.id))
    if left_weapon.collidepoint(mouse_pos):
        hover_source = left_weapon
        hover_title = weapon.name
        hover_lines = [f"Primary Weapon ({weapon.kind.title()})", *_weapon_detail_lines(weapon)[1:]]
    elif show_secondary_weapon and right_weapon.collidepoint(mouse_pos):
        hover_source = right_weapon
        hover_title = alt_weapon.name
        hover_lines = [f"Secondary Weapon ({alt_weapon.kind.title()})", *_weapon_detail_lines(alt_weapon)[1:]]
    draw_text(
        surf,
        "CLASS",
        font_label(10, bold=True),
        UI_TEXT_MUTE,
        (right_rect.centerx, right_rect.y + 18),
        center=True,
    )
    draw_text(
        surf,
        class_name if class_name and class_name != NO_CLASS_NAME else "Unassigned",
        font_label(10, bold=True),
        UI_GOLD if class_name and class_name != NO_CLASS_NAME else UI_TEXT_MUTE,
        (right_rect.centerx, right_rect.y + 34),
        center=True,
    )
    if show_classes:
        class_names = list(CLASS_ORDER)
        icon_w = 60
        icon_h = 46
        col_gap = 12
        row_gap = 8
        class_count = len(class_names)
        class_rows = (class_count + 1) // 2
        grid_w = icon_w * 2 + col_gap
        grid_start_x = right_rect.centerx - grid_w // 2
        grid_start_y = right_rect.y + 54
        last_row_index = class_rows - 1
        for index, cls_name in enumerate(class_names):
            row = index // 2
            col = index % 2
            if row == last_row_index and class_count % 2 == 1 and col == 0 and index == class_count - 1:
                icon_x = right_rect.centerx - icon_w // 2
            else:
                icon_x = grid_start_x + col * (icon_w + col_gap)
            icon_y = grid_start_y + row * (icon_h + row_gap)
            icon_rect = pygame.Rect(icon_x, icon_y, icon_w, icon_h)
            locked = cls_name not in {NO_CLASS_NAME, class_name} and any(other.get("class_name", NO_CLASS_NAME) == cls_name for idx, other in enumerate(members) if idx != selected_index)
            draw_beveled_panel(surf, icon_rect, fill_top=UI_BG_RAISED if cls_name == class_name else UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if cls_name == class_name else UI_GOLD_DIM)
            draw_text(surf, cls_name[:1], font_body(18, bold=True), UI_TEXT_MUTE if locked else _class_tint(cls_name), (icon_rect.centerx, icon_rect.y + 16), center=True)
            draw_text(surf, cls_name[:6].upper(), font_label(8, bold=True), UI_TEXT_MUTE if locked else UI_TEXT_SOFT, (icon_rect.centerx, icon_rect.bottom - 8), center=True)
            if class_editable:
                buttons["classes"].append((icon_rect, cls_name))
            if icon_rect.collidepoint(mouse_pos):
                hover_source = icon_rect
                hover_title = cls_name
                hover_lines = _class_detail_lines(cls_name)
                if locked:
                    hover_lines = [*hover_lines, "Locked: another party member already has this class."]
                elif not class_editable:
                    hover_lines = [*hover_lines, "Class changes unlock later in the tutorial."]
    else:
        note_rect = pygame.Rect(right_rect.x + 16, right_rect.y + 88, right_rect.width - 32, 118)
        draw_beveled_panel(surf, note_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        _draw_wrapped_lines(
            surf,
            ["Class assignment unlocks later. For now, focus on weapon training and the core combat actions."],
            note_rect.x + 10,
            note_rect.y + 14,
            note_rect.width - 20,
            font=font_body(12),
            color=UI_TEXT_SOFT,
            line_height=14,
        )

    skills = _loadout_skill_options(class_name)[:max_skill_options]
    if skills_y is not None:
        skill_gap = 18
        skill_count = max(1, len(skills))
        if skill_count == 1:
            skill_w = min(320, rect.width - margin * 2)
            skill_start_x = rect.centerx - skill_w // 2
        else:
            skill_w = min(240, (rect.width - margin * 2 - skill_gap) // 2)
            skill_start_x = rect.centerx - (skill_w * skill_count + skill_gap * (skill_count - 1)) // 2
        if skills:
            for index, skill in enumerate(skills):
                skill_rect = pygame.Rect(skill_start_x + index * (skill_w + skill_gap), skills_y, skill_w, 76)
                active = skill.id == member.get("class_skill_id")
                draw_beveled_panel(surf, skill_rect, fill_top=UI_BG_RAISED if active else UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if active else UI_GOLD_DIM)
                draw_text(surf, _ellipsize_text(skill.name, font_body(13, bold=True), skill_rect.width - 16), font_body(13, bold=True), UI_TEXT, (skill_rect.x + 10, skill_rect.y + 12))
                _draw_wrapped_lines(surf, [skill.description], skill_rect.x + 10, skill_rect.y + 34, skill_rect.width - 20, font=font_body(12), color=UI_TEXT_SOFT, line_height=14)
                if skills_editable:
                    buttons["skills"].append((skill_rect, skill.id))
                if skill_rect.collidepoint(mouse_pos):
                    hover_source = skill_rect
                    hover_title = skill.name
                    hp_bonus = f"+{skill.hp_bonus} HP" if skill.hp_bonus else "No HP bonus"
                    hover_lines = [hp_bonus, skill.description]
                    if not skills_editable:
                        hover_lines = [*hover_lines, "Skill choices unlock later in the tutorial."]
        else:
            placeholder_rect = pygame.Rect(skill_start_x, skills_y, skill_w if skill_count == 1 else skill_w * 2 + skill_gap, 76)
            draw_beveled_panel(surf, placeholder_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
            draw_text(surf, "Choose a class to unlock class skills.", font_body(13, bold=True), UI_TEXT_MUTE, (placeholder_rect.centerx, placeholder_rect.centery), center=True)

    if show_artifacts and artifact_y is not None:
        options = [(None, "Empty")] + [
            (artifact_id, artifact_lookup[artifact_id].name)
            for artifact_id in _loadout_artifact_options(class_name, allowed_artifact_ids, artifact_lookup=artifact_lookup)[:5]
            if artifact_id in artifact_lookup
        ]
        used_by_others = {other.get("artifact_id") for idx, other in enumerate(members) if idx != selected_index}
        art_gap = 10
        art_w = min(106, max(82, (rect.width - margin * 2 - art_gap * (len(options) - 1)) // max(1, len(options))))
        art_total_w = art_w * len(options) + art_gap * (len(options) - 1)
        art_start_x = rect.centerx - art_total_w // 2
        for index, (artifact_id, artifact_name) in enumerate(options):
            art_rect = pygame.Rect(art_start_x + index * (art_w + art_gap), artifact_y, art_w, 62)
            locked = artifact_id is not None and artifact_id in used_by_others
            active = artifact_id == member.get("artifact_id") or (artifact_id is None and member.get("artifact_id") is None)
            attuned = True
            artifact = None
            if artifact_id is not None:
                artifact = artifact_lookup[artifact_id]
                attuned = class_name in artifact.attunement
            draw_beveled_panel(surf, art_rect, fill_top=UI_BG_RAISED if active else UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if active and not locked else UI_GOLD_DIM)
            name_color = UI_TEXT
            if locked or not attuned:
                name_color = UI_TEXT_MUTE
            draw_text(surf, _ellipsize_text(artifact_name, font_body(11, bold=True), art_rect.width - 10), font_body(11, bold=True), name_color, (art_rect.x + 6, art_rect.y + 12))
            if artifact_id is not None:
                draw_text(surf, "/".join(attn[:1] for attn in artifact.attunement[:3]), font_label(8, bold=True), UI_TEXT_SOFT if attuned and not locked else UI_TEXT_MUTE, (art_rect.centerx, art_rect.bottom - 10), center=True)
            if artifacts_editable:
                buttons["artifacts"].append((art_rect, artifact_id, locked))
            if art_rect.collidepoint(mouse_pos):
                hover_source = art_rect
                if artifact_id is None:
                    hover_title = "Unequip Artifact"
                    hover_lines = ["Leave the slot empty and return the equipped artifact to the pool."]
                else:
                    hover_title = artifact.name
                    hover_lines = _artifact_detail_lines(artifact)
                    if locked:
                        hover_lines = [*hover_lines, "Locked: another party member already has this artifact."]
                    elif not attuned:
                        hover_lines = [*hover_lines, "Unattuned: this class still gains the stat bonus, but cannot cast the artifact spell."]
                    elif not artifacts_editable:
                        hover_lines = [*hover_lines, "Artifacts unlock later in the tutorial."]
    if class_skill is not None and hover_source is None and portrait.collidepoint(mouse_pos):
        hover_source = portrait
        hover_title = adventurer.name
        hover_lines = _member_loadout_lines(member, adventurer_lookup=adventurer_lookup, artifact_lookup=artifact_lookup)
    if hover_source is not None and hover_title is not None and hover_lines is not None:
        _draw_info_popout(surf, hover_source, hover_title, hover_lines)
    return buttons


def draw_quest_party_loadout(surf, mouse_pos, party_state, selected_index, *, detail_scroll: int = 0):
    draw_background(surf, "quest")
    btns = draw_top_bar(surf, "Loadouts", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    members = list(party_state.get("team1", []))
    top_rect = pygame.Rect(72, 100, 1256, 160)
    editor_rect = pygame.Rect(72, 282, 894, 530)
    side_rect = pygame.Rect(988, 282, 340, 530)
    draw_beveled_panel(surf, top_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, editor_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_beveled_panel(surf, side_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
    member_buttons = []
    hover_member = None
    for index, member in enumerate(members[:6]):
        adventurer = ADVENTURERS_BY_ID[member["adventurer_id"]]
        rect = pygame.Rect(top_rect.x + 16 + index * 206, top_rect.y + 14, 190, 132)
        draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=index == selected_index, small=True)
        member_buttons.append((rect, index))
        if rect.collidepoint(mouse_pos):
            hover_member = member
    editor_buttons = _draw_loadout_editor_core(
        surf,
        mouse_pos,
        members,
        selected_index,
        rect=editor_rect,
        allowed_artifact_ids=party_state.get("team1_allowed_artifact_ids"),
        editable=True,
    )
    _draw_party_loadout_summary_panel(surf, side_rect, members, selected_index)
    done_rect = pygame.Rect(side_rect.x + 16, side_rect.bottom - 54, side_rect.width - 32, 38)
    draw_primary_button(surf, done_rect, mouse_pos, "Done")
    btns["members"] = member_buttons
    btns["weapons"] = editor_buttons["weapons"]
    btns["classes"] = editor_buttons["classes"]
    btns["skills"] = editor_buttons["skills"]
    btns["artifacts"] = editor_buttons["artifacts"]
    btns["done"] = done_rect
    btns["detail_viewport"] = editor_rect
    btns["detail_scroll_max"] = 0
    if hover_member is not None:
        adventurer = ADVENTURERS_BY_ID[hover_member["adventurer_id"]]
        _draw_info_popout(surf, pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1), adventurer.name, _member_loadout_lines(hover_member))
    return btns


def draw_bouts_menu(surf, mouse_pos):
    draw_background(surf, "guild")
    panel = pygame.Rect(220, 170, 960, 480)
    draw_beveled_panel(surf, panel, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    btns = draw_top_bar(surf, "Bouts", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    random_card = pygame.Rect(panel.x + 40, panel.y + 54, 400, 350)
    focused_card = pygame.Rect(panel.right - 440, panel.y + 54, 400, 350)
    for rect, title, subtitle in (
        (random_card, "Random Bout", "Draft from a shared pool"),
        (focused_card, "Focused Bout", "Bring a tuned roster"),
    ):
        draw_beveled_panel(surf, rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
        draw_text(surf, title, font_headline(24, bold=True), UI_TEXT, (rect.x + 20, rect.y + 22))
        draw_text(surf, subtitle, font_body(14), UI_TEXT_SOFT, (rect.x + 20, rect.y + 58))
    random_ai = pygame.Rect(random_card.x + 20, random_card.bottom - 96, 160, 40)
    random_lan = pygame.Rect(random_card.right - 180, random_card.bottom - 96, 160, 40)
    focused_ai = pygame.Rect(focused_card.x + 20, focused_card.bottom - 96, 160, 40)
    focused_lan = pygame.Rect(focused_card.right - 180, focused_card.bottom - 96, 160, 40)
    draw_primary_button(surf, random_ai, mouse_pos, "vs AI")
    draw_secondary_button(surf, random_lan, mouse_pos, "vs Friend")
    draw_primary_button(surf, focused_ai, mouse_pos, "vs AI")
    draw_secondary_button(surf, focused_lan, mouse_pos, "vs Friend")
    btns["vs_random"] = random_ai
    btns["vs_focused"] = focused_ai
    btns["random_lan"] = random_lan
    btns["focused_lan"] = focused_lan
    btns["vs_lan"] = random_lan
    return btns


def _triangle_slot_layout(base_rect: pygame.Rect, *, compact: bool = False):
    if compact:
        return {
            SLOT_FRONT: pygame.Rect(base_rect.centerx - 82, base_rect.y + 176, 164, 90),
            SLOT_BACK_LEFT: pygame.Rect(base_rect.x + 28, base_rect.y + 56, 150, 82),
            SLOT_BACK_RIGHT: pygame.Rect(base_rect.right - 178, base_rect.y + 56, 150, 82),
        }
    return {
        SLOT_FRONT: pygame.Rect(base_rect.centerx - 88, base_rect.bottom - 128, 176, 96),
        SLOT_BACK_LEFT: pygame.Rect(base_rect.x + 36, base_rect.y + 42, 156, 88),
        SLOT_BACK_RIGHT: pygame.Rect(base_rect.right - 192, base_rect.y + 42, 156, 88),
    }


def _draw_formation_area(surf, mouse_pos, rect: pygame.Rect, members, selected_index: int, *, drag_state=None, adventurer_lookup=None, compact: bool = False):
    adventurer_lookup = adventurer_lookup or ADVENTURERS_BY_ID
    draw_beveled_panel(surf, rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    slot_map = _triangle_slot_layout(rect, compact=compact)
    member_buttons = []
    for slot_name, slot_rect in slot_map.items():
        draw_beveled_panel(surf, slot_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_BRIGHT if drag_state and drag_state.get("hover_slot") == slot_name else UI_GOLD_DIM)
        member = next((item for item in members if item.get("slot") == slot_name), None)
        if member is None:
            continue
        adventurer = adventurer_lookup[member["adventurer_id"]]
        draw_adventurer_card(surf, slot_rect, mouse_pos, adventurer, selected=members.index(member) == selected_index, small=True)
        member_buttons.append((slot_rect, members.index(member), slot_name))
    return member_buttons, list(slot_map.items())


def _draw_enemy_roster_list(
    surf,
    mouse_pos,
    rect: pygame.Rect,
    members,
    *,
    title: str,
    subtitle: str | None = None,
    adventurer_lookup=None,
):
    adventurer_lookup = adventurer_lookup or ADVENTURERS_BY_ID
    draw_beveled_panel(surf, rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    draw_text(surf, title, font_label(11, bold=True), UI_TEXT_MUTE, (rect.x + 14, rect.y + 12))
    y = rect.y + 32
    if subtitle:
        draw_text(
            surf,
            _ellipsize_text(subtitle, font_body(11), rect.width - 28),
            font_body(11),
            UI_GOLD,
            (rect.x + 14, y),
        )
        y += 20
    buttons = []
    hover_member = None
    hover_rect = None
    visible_members = list(members or [])
    count = max(1, len(visible_members))
    max_box_height = 34
    gap = 8
    available = rect.bottom - y - 12
    box_height = min(max_box_height, max(24, (available - gap * max(0, count - 1)) // count))
    for index, member in enumerate(visible_members):
        adventurer = adventurer_lookup.get(member.get("adventurer_id", ""))
        if adventurer is None:
            continue
        item_rect = pygame.Rect(rect.x + 12, y + index * (box_height + gap), rect.width - 24, box_height)
        hovered = item_rect.collidepoint(mouse_pos)
        draw_beveled_panel(
            surf,
            item_rect,
            fill_top=UI_BG_RAISED if hovered else UI_BG_SURFACE,
            fill_bottom=UI_BG_SURFACE if hovered else UI_BG_MID,
            border=UI_GOLD_BRIGHT if hovered else UI_GOLD_DIM,
        )
        draw_text(
            surf,
            _ellipsize_text(adventurer.name, font_body(12, bold=True), item_rect.width - 20),
            font_body(12, bold=True),
            UI_TEXT,
            (item_rect.x + 10, item_rect.y + 8),
        )
        buttons.append((item_rect, member))
        if hovered:
            hover_member = member
            hover_rect = item_rect
    return buttons, hover_member, hover_rect


def draw_quest_loadout(
    surf,
    mouse_pos,
    setup_state,
    selected_index,
    *,
    player_team_num: int = 1,
    waiting_note: str = "",
    drag_state: dict | None = None,
    detail_scroll: int = 0,
    summary_scroll: int = 0,
    editable_loadout: bool = True,
    adventurer_lookup=None,
    artifact_lookup=None,
    loadout_options=None,
    required_member_count: int | None = None,
    confirm_label: str | None = None,
    waiting_lines: list[str] | None = None,
    enemy_members=None,
    enemy_list_title: str = "Enemy Party",
    enemy_list_subtitle: str | None = None,
):
    adventurer_lookup = adventurer_lookup or ADVENTURERS_BY_ID
    artifact_lookup = artifact_lookup or ALL_ARTIFACTS_BY_ID
    draw_background(surf, "quest")
    btns = draw_top_bar(surf, "Encounter Loadout", mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    members = list((setup_state or {}).get(f"team{player_team_num}", []))
    enemy_team_num = 2 if player_team_num == 1 else 1
    enemy_members = list(enemy_members if enemy_members is not None else (setup_state or {}).get(f"team{enemy_team_num}", []))
    formation_rect = pygame.Rect(60, 118, 404, 298)
    enemy_rect = pygame.Rect(60, 434, 404, 304)
    editor_rect = pygame.Rect(490, 118, 850, 620)
    member_buttons, slot_items = _draw_formation_area(surf, mouse_pos, formation_rect, members, selected_index, drag_state=drag_state, adventurer_lookup=adventurer_lookup, compact=True)
    enemy_buttons, hover_enemy_member, hover_enemy_rect = _draw_enemy_roster_list(
        surf,
        mouse_pos,
        enemy_rect,
        enemy_members,
        title=enemy_list_title,
        subtitle=enemy_list_subtitle,
        adventurer_lookup=adventurer_lookup,
    )
    hover_member = None
    hover_rect = None
    for slot_rect, member_index, _slot_name in member_buttons:
        if slot_rect.collidepoint(mouse_pos) and 0 <= member_index < len(members):
            hover_member = members[member_index]
            hover_rect = slot_rect
    if hover_member is None:
        hover_member = hover_enemy_member
        hover_rect = hover_enemy_rect
    editor_buttons = _draw_loadout_editor_core(
        surf,
        mouse_pos,
        members,
        selected_index,
        rect=editor_rect,
        allowed_artifact_ids=(setup_state or {}).get(f"team{player_team_num}_allowed_artifact_ids"),
        editable=editable_loadout,
        adventurer_lookup=adventurer_lookup,
        artifact_lookup=artifact_lookup,
        loadout_options=loadout_options,
    )
    if drag_state is not None and 0 <= drag_state.get("member_index", -1) < len(members):
        drag_member = members[drag_state["member_index"]]
        drag_adv = adventurer_lookup[drag_member["adventurer_id"]]
        drag_rect = pygame.Rect(mouse_pos[0] - 56, mouse_pos[1] - 72, 112, 144)
        draw_adventurer_card(surf, drag_rect, mouse_pos, drag_adv, selected=True, small=True)
    confirm_rect = pygame.Rect(editor_rect.right - 220, editor_rect.bottom + 18, 220, 40)
    expected_count = required_member_count if required_member_count is not None else 3
    confirm_disabled = len(members) != expected_count
    draw_primary_button(surf, confirm_rect, mouse_pos, confirm_label or ("Done" if editable_loadout else "Lock In"), disabled=confirm_disabled)
    note_lines = list(waiting_lines or [])
    if waiting_note and waiting_note not in note_lines:
        note_lines.insert(0, waiting_note)
    if note_lines:
        if not editable_loadout and any("locked" in line.lower() for line in note_lines):
            note_lines = ["Formation only here."]
        note_rect = pygame.Rect(editor_rect.x + 4, editor_rect.bottom + 12, editor_rect.width - 244, 52)
        draw_beveled_panel(surf, note_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        y = note_rect.y + 8
        for index, line in enumerate(note_lines[:3]):
            wrapped = _wrap_text_block(line, font_body(11 if index else 12, bold=index == 0), note_rect.width - 18)
            for wrapped_line in wrapped[:2]:
                draw_text(
                    surf,
                    wrapped_line,
                    font_body(11 if index else 12, bold=index == 0),
                    UI_GOLD_BRIGHT if index == 0 else UI_TEXT_SOFT,
                    (note_rect.x + 10, y),
                )
                y += 14 if index == 0 else 13
            if y > note_rect.bottom - 12:
                break
    btns["formation_members"] = member_buttons
    btns["formation_slots"] = slot_items
    btns["enemy_members"] = enemy_buttons
    btns["weapons"] = editor_buttons["weapons"]
    btns["classes"] = editor_buttons["classes"]
    btns["skills"] = editor_buttons["skills"]
    btns["artifacts"] = editor_buttons["artifacts"]
    btns["confirm"] = confirm_rect
    btns["detail_viewport"] = editor_rect
    btns["detail_scroll_max"] = 0
    btns["summary_viewport"] = pygame.Rect(formation_rect.x, formation_rect.y, formation_rect.width, enemy_rect.bottom - formation_rect.y)
    btns["summary_scroll_max"] = 0
    if hover_member is not None:
        adventurer = adventurer_lookup[hover_member["adventurer_id"]]
        _draw_info_popout(surf, hover_rect or pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1), adventurer.name, _member_loadout_lines(hover_member, adventurer_lookup=adventurer_lookup, artifact_lookup=artifact_lookup))
    return btns


def draw_bout_loadout(
    surf,
    mouse_pos,
    setup_state,
    selected_index,
    *,
    player_team_num: int = 1,
    waiting_note: str = "",
    drag_state: dict | None = None,
    detail_scroll: int = 0,
    summary_scroll: int = 0,
):
    return draw_quest_loadout(
        surf,
        mouse_pos,
        setup_state,
        selected_index,
        player_team_num=player_team_num,
        waiting_note=waiting_note,
        drag_state=drag_state,
        detail_scroll=detail_scroll,
        summary_scroll=summary_scroll,
        editable_loadout=True,
    )


def draw_battle_hud(surf, mouse_pos, controller, *, log_open=False, battle_log_popups=True):
    draw_background(surf, "arena")
    btns = draw_top_bar(surf, controller.current_phase_label(), mouse_pos, left_icon="<", right_icons=(("settings", "S", False), ("quit", "X", True)))
    btns["back"] = btns.pop("left")
    if hasattr(controller, "refresh_tutorial_guidance"):
        controller.refresh_tutorial_guidance()
    slot_buttons = []
    log_toggle = pygame.Rect(34, 810, 46, 46)
    draw_icon_button(surf, log_toggle, mouse_pos, "L", active=log_open)
    draw_text(surf, "Log", font_label(10, bold=True), UI_TEXT_SOFT, (log_toggle.centerx, log_toggle.bottom + 8), center=True)
    btns["log_toggle"] = log_toggle

    if getattr(controller, "allow_ultimate_meter", True):
        your_meter = pygame.Rect(470, 90, 210, 14)
        enemy_meter = pygame.Rect(720, 90, 210, 14)
        draw_meter(surf, your_meter, controller.battle.team1.ultimate_meter, ULTIMATE_METER_MAX, fill=UI_BLUE)
        draw_meter(surf, enemy_meter, controller.battle.team2.ultimate_meter, ULTIMATE_METER_MAX, fill=UI_ORANGE)
        draw_text(surf, "VS", font_label(10, bold=True), UI_TEXT_SOFT, (700, 90), center=True)
    tutorial_prompt = getattr(controller, "tutorial_prompt", "")
    if tutorial_prompt:
        prompt_rect = pygame.Rect(338, 112, 724, 74)
        draw_beveled_panel(surf, prompt_rect, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
        dismiss_rect = pygame.Rect(prompt_rect.right - 92, prompt_rect.y + 17, 78, 32)
        _draw_wrapped_lines(surf, [tutorial_prompt], prompt_rect.x + 14, prompt_rect.y + 13, prompt_rect.width - 122, font=font_body(13), color=UI_TEXT_SOFT, line_height=16)
        draw_secondary_button(surf, dismiss_rect, mouse_pos, getattr(controller, "tutorial_prompt_button_label", "Next"))
        btns["tutorial_prompt_dismiss"] = dismiss_rect

    target_lookup = {id(unit) for unit in controller.legal_targets()}
    hovered_unit = None
    for slot_data in controller.battlefield_slots():
        rect = _battle_slot_rects()[(slot_data["team_num"], slot_data["slot"])]
        unit = slot_data["unit"]
        border = UI_GOLD_BRIGHT if unit is not None and id(unit) in target_lookup else UI_GOLD_DIM
        if unit is not None:
            draw_beveled_panel(surf, rect, fill_top=UI_BG_RAISED if slot_data["team_num"] == 1 else _lerp_color(UI_BG_RAISED, UI_RED, 0.2), fill_bottom=UI_BG_MID, border=border)
            draw_text(surf, _ellipsize_text(unit.name, font_body(14, bold=True), rect.width - 24), font_body(14, bold=True), UI_TEXT, (rect.x + 12, rect.y + 10))
            draw_meter(surf, pygame.Rect(rect.x + 12, rect.y + 36, rect.width - 24, 8), unit.hp, unit.max_hp, fill=UI_GREEN if unit.hp / max(1, unit.max_hp) > 0.35 else UI_RED)
            draw_chip(surf, pygame.Rect(rect.x + 12, rect.y + 50, 18, 18), (getattr(unit, "class_name", NO_CLASS_NAME) or NO_CLASS_NAME)[:1], _class_tint(getattr(unit, "class_name", NO_CLASS_NAME)))
            draw_chip(surf, pygame.Rect(rect.right - 30, rect.y + 50, 18, 18), _weapon_icon(unit.primary_weapon.kind), UI_GOLD)
            for status_index, status in enumerate(unit.statuses[:3]):
                draw_chip(surf, pygame.Rect(rect.x + 12 + status_index * 20, rect.bottom - 24, 18, 18), _status_dot_label(status.kind), UI_STATUS_COLORS.get(status.kind, UI_GOLD))
            slot_buttons.append((rect, unit))
            if rect.collidepoint(mouse_pos):
                hovered_unit = unit
        else:
            outline = _lerp_color(UI_GOLD_DIM, UI_BLUE if slot_data["team_num"] == 1 else UI_RED, 0.2)
            pygame.draw.rect(surf, outline, rect, 1, border_radius=18)
            marker = pygame.Rect(rect.centerx - 18, rect.centery - 4, 36, 8)
            _blit_translucent_rect(surf, marker, _with_alpha(outline, 38), border=outline, radius=5)

    if hovered_unit is not None:
        _draw_info_popout(
            surf,
            pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1),
            hovered_unit.name,
            _combatant_loadout_lines(hovered_unit),
            width=420,
            body_font=font_body(12),
            line_height=14,
        )

    action_rect = pygame.Rect(150, 740, 1100, 120)
    draw_beveled_panel(surf, action_rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
    action_buttons = []
    spell_buttons = []
    choice_icons = {"strike": "X", "spellbook": "S", "switch": "R", "swap": "W", "skip": "-", "ultimate": "U"}
    action_tooltips = {
        "strike": "Attack with the primary weapon. Targeting follows the weapon type's rules.",
        "spellbook": "Cast a ready spell from the current weapon, your artifact, or granted effects.",
        "switch": "Swap primary and secondary weapons. Both weapons reset their cooldowns.",
        "swap": "Move to an open allied slot or swap positions with an ally.",
        "skip": "Pass this action. Some passives reward skipping.",
        "ultimate": "Spend a full Ultimate Meter to cast this adventurer's Ultimate Spell.",
    }
    hovered_action = None
    for slot_data in controller.battlefield_slots():
        unit = slot_data["unit"]
        if unit is None or slot_data["team_num"] != 1:
            continue
        queued = controller.queued_label_for(unit)
        chip_rect = pygame.Rect(_battle_slot_rects()[(slot_data["team_num"], slot_data["slot"])].centerx - 28, _battle_slot_rects()[(slot_data["team_num"], slot_data["slot"])].y - 24, 56, 20)
        draw_chip(surf, chip_rect, queued[:3].upper(), UI_GOLD)
    if controller.active_actor is not None:
        choices = controller.available_actions()
        suggested_action = getattr(controller, "tutorial_highlight_action", None)
        for index, choice in enumerate(choices):
            rect = pygame.Rect(action_rect.x + 20 + index * 104, action_rect.y + 26, 92, 64)
            is_pending = controller.pending_choice is not None and controller.pending_choice.kind == choice.kind
            is_suggested = suggested_action == choice.kind and controller.pending_choice is None
            draw_beveled_panel(
                surf,
                rect,
                fill_top=UI_BG_RAISED if is_pending or is_suggested else UI_BG_SURFACE,
                fill_bottom=UI_BG_MID,
                border=UI_GOLD_BRIGHT if is_pending or is_suggested else UI_GOLD_DIM,
            )
            draw_text(surf, choice_icons.get(choice.kind, "?"), font_headline(24, bold=True), UI_TEXT, (rect.centerx, rect.y + 20), center=True)
            draw_text(surf, choice.label, font_label(10, bold=True), UI_TEXT_SOFT, (rect.centerx, rect.bottom - 14), center=True)
            action_buttons.append((rect, choice.kind))
            if rect.collidepoint(mouse_pos):
                hovered_action = choice.kind
        if controller.spellbook_open:
            spells = controller.available_bonus_spells(controller.active_actor) if controller.phase.startswith("bonus") else controller.available_spells(controller.active_actor)
            for index, spell in enumerate(spells):
                rect = pygame.Rect(action_rect.x + 20 + index * 184, action_rect.bottom - 34, 170, 24)
                draw_secondary_button(surf, rect, mouse_pos, spell.name, active=controller.pending_choice is not None and controller.pending_choice.effect_id == spell.id)
                spell_buttons.append((rect, spell.id))
    resolve_rect = pygame.Rect(1270, 778, 90, 44)
    draw_primary_button(surf, resolve_rect, mouse_pos, controller.resolve_button_label(), disabled=not controller.can_resolve())
    if log_open:
        overlay = pygame.Rect(90, 140, 300, 520)
        draw_beveled_panel(surf, overlay, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_DIM)
        y = overlay.y + 16
        for line in controller.battle.log[-16:]:
            _draw_wrapped_lines(surf, [line], overlay.x + 14, y, overlay.width - 28, font=font_body(12), color=UI_TEXT_SOFT, line_height=14)
            y += 30
    if hovered_action is not None:
        _draw_info_popout(
            surf,
            pygame.Rect(mouse_pos[0], mouse_pos[1], 1, 1),
            hovered_action.title(),
            [action_tooltips.get(hovered_action, hovered_action.title())],
            width=280,
            body_font=font_body(12),
            line_height=14,
        )
    btns["resolve"] = resolve_rect
    btns["action_buttons"] = action_buttons
    btns["spell_buttons"] = spell_buttons
    btns["slot_buttons"] = slot_buttons
    return btns


def draw_results(surf, mouse_pos, result_kind, is_victory: bool, winner_label, lines):
    draw_background(surf, "arena")
    btns = draw_top_bar(surf, "Results", mouse_pos, left_icon="<", right_icons=(("quit", "X", True),))
    btns["back"] = btns.pop("left")
    center = pygame.Rect(290, 156, 820, 548)
    draw_beveled_panel(surf, center, fill_top=UI_BG_RAISED, fill_bottom=UI_BG_SURFACE, border=UI_GOLD_BRIGHT if is_victory else UI_RED)
    draw_text(surf, "VICTORY" if is_victory else "DEFEAT", font_headline(48, bold=True), UI_GOLD_BRIGHT if is_victory else UI_RED, (center.centerx, center.y + 78), center=True)
    if winner_label:
        draw_text(surf, winner_label, font_body(18, bold=True), UI_TEXT_SOFT, (center.centerx, center.y + 132), center=True)
    card_y = center.y + 200
    for index, line in enumerate(lines[:3]):
        rect = pygame.Rect(center.x + 46 + index * 244, card_y, 210, 140)
        draw_beveled_panel(surf, rect, fill_top=UI_BG_SURFACE, fill_bottom=UI_BG_MID, border=UI_GOLD_DIM)
        draw_text(surf, f"Card {index + 1}", font_label(10, bold=True), UI_GOLD, (rect.x + 12, rect.y + 12))
        _draw_wrapped_lines(surf, [line], rect.x + 12, rect.y + 44, rect.width - 24, font=font_body(13), color=UI_TEXT, line_height=16)
    continue_rect = pygame.Rect(center.x + 70, center.bottom - 72, 170, 40)
    rematch_rect = pygame.Rect(center.centerx - 85, center.bottom - 72, 170, 40)
    return_rect = pygame.Rect(center.right - 240, center.bottom - 72, 170, 40)
    draw_primary_button(surf, continue_rect, mouse_pos, "Continue")
    draw_secondary_button(surf, rematch_rect, mouse_pos, "Rematch")
    draw_secondary_button(surf, return_rect, mouse_pos, "Return")
    btns["continue"] = continue_rect
    btns["rematch"] = rematch_rect
    btns["return"] = return_rect
    return btns
