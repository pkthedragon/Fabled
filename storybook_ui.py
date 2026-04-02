from __future__ import annotations

import pygame

from settings import HEIGHT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT, WIDTH
from storybook_content import (
    BOUT_MODES,
    CATALOG_SECTIONS,
    COSMETIC_CATEGORIES,
    SHOP_TABS,
    STORY_QUESTS,
    catalog_entries,
    quest_role_summary,
    quest_warnings,
    recommendation_notes,
    role_tags_for_adventurer,
    shop_items_for_tab,
    shop_tab_note,
)
from quests_ruleset_data import ADVENTURERS_BY_ID, ARTIFACTS_BY_ID, CLASS_SKILLS
from quests_sandbox import CLASS_ORDER, compatible_artifact_ids
from storybook_progression import level_state


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

SLOT_LABELS = {
    SLOT_FRONT: "Frontline",
    SLOT_BACK_LEFT: "Backline Left",
    SLOT_BACK_RIGHT: "Backline Right",
}

CLASS_SUMMARIES = {
    "Warden": "Tanks and position manipulators built to hold the frontline.",
    "Fighter": "Melee damage dealers that convert clean reach into knockouts.",
    "Mage": "Magic damage dealers with spell pressure and cooldown leverage.",
    "Ranger": "Ranged pressure specialists with ammo management and lane control.",
    "Cleric": "Healers and enchanters that stabilize parties and patch mistakes.",
    "Rogue": "Disruptors and speedsters that thrive on timing and repositioning.",
}

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
    if disabled:
        fill_gradient(surf, rect, SURFACE_HIGH, SURFACE)
        pygame.draw.rect(surf, GOLD_DIM, rect, 2, border_radius=12)
        draw_text(surf, label, font_headline(18, bold=True), TEXT_MUTE, rect.center, center=True)
    else:
        top = _lerp_color(accent, (255, 235, 160), 0.2 if hovered else 0.0)
        bottom = _lerp_color(GOLD_DIM, accent, 0.45 if hovered else 0.2)
        fill_gradient(surf, rect, top, bottom)
        pygame.draw.rect(surf, GOLD_BRIGHT, rect, 2, border_radius=12)
        draw_text(surf, label, font_headline(18, bold=True), SBG_DEEP, rect.center, center=True)
    return rect


def draw_secondary_button(surf, rect, mouse_pos, label, *, active=False):
    hovered = rect.collidepoint(mouse_pos)
    fill_top = SURFACE_HIGH if hovered or active else SURFACE
    fill_bottom = SURFACE if hovered or active else SURFACE_LOW
    border = GOLD_BRIGHT if active else (PARCHMENT if hovered else GOLD_DIM)
    draw_beveled_panel(surf, rect, fill_top=fill_top, fill_bottom=fill_bottom, border=border)
    color = GOLD_BRIGHT if active else TEXT
    draw_text(surf, label, font_body(15, bold=True), color, rect.center, center=True)
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


def draw_adventurer_card(surf, rect, mouse_pos, adventurer, *, selected=False, unavailable=False, small=False, tag_line=None):
    base, accent = _portrait_palette(adventurer)
    hovered = rect.collidepoint(mouse_pos)
    fill_top = _lerp_color(SURFACE_HIGH, base, 0.25)
    fill_bottom = SURFACE_LOW
    border = GOLD_BRIGHT if selected else (accent if hovered else GOLD_DIM)
    draw_beveled_panel(surf, rect, fill_top=fill_top, fill_bottom=fill_bottom, border=border)
    if selected:
        draw_glow_rect(surf, rect, GOLD_BRIGHT, alpha=36)

    art_rect = pygame.Rect(rect.x + 12, rect.y + 12, rect.width - 24, 74 if small else 96)
    fill_gradient(surf, art_rect, _lerp_color(base, accent, 0.25), SBG_DEEP)
    pygame.draw.rect(surf, (255, 255, 255, 22), art_rect, 1, border_radius=10)
    initials = "".join(part[0] for part in adventurer.name.split()[:2]).upper()
    draw_text(surf, initials, font_headline(34 if small else 42, bold=True), PARCHMENT, art_rect.center, center=True)

    name_y = art_rect.bottom + 10
    draw_text(surf, adventurer.name, font_headline(18, bold=True), TEXT, (rect.x + 14, name_y))
    if tag_line:
        draw_text(surf, tag_line, font_label(11, bold=True), GOLD_BRIGHT, (rect.x + 14, name_y + 22))
    else:
        draw_text(surf, ", ".join(role_tags_for_adventurer(adventurer)), font_label(11, bold=True), GOLD_BRIGHT, (rect.x + 14, name_y + 22))

    stats_y = rect.bottom - 44
    draw_text(surf, f"HP {adventurer.hp}", font_label(11, bold=True), TEXT_SOFT, (rect.x + 14, stats_y))
    draw_text(surf, f"ATK {adventurer.attack}", font_label(11, bold=True), TEXT_SOFT, (rect.x + 92, stats_y))
    draw_text(surf, f"DEF {adventurer.defense}", font_label(11, bold=True), TEXT_SOFT, (rect.x + 14, stats_y + 18))
    draw_text(surf, f"SPD {adventurer.speed}", font_label(11, bold=True), TEXT_SOFT, (rect.x + 92, stats_y + 18))

    icon_x = rect.right - 76
    for index, weapon in enumerate(adventurer.signature_weapons):
        chip = pygame.Rect(icon_x + index * 28, rect.bottom - 38, 22, 22)
        color = GOLD_BRIGHT if weapon.kind == "melee" else (SAPPHIRE if weapon.kind == "ranged" else JADE)
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


def draw_main_menu(surf, mouse_pos, profile):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Fabled",
        mouse_pos,
        left_icon="P",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
    )
    guild_rect = pygame.Rect(WIDTH // 2 - 290, 246, 260, 278)
    shops_rect = pygame.Rect(WIDTH // 2 + 30, 246, 260, 278)
    draw_beveled_panel(surf, guild_rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    draw_beveled_panel(surf, shops_rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    draw_text(surf, "Guild Hall", font_headline(40, bold=True), TEXT, (guild_rect.centerx, guild_rect.y + 124), center=True)
    draw_text(surf, "Quests, bouts, catalog, and campaign planning.", font_body(18), TEXT_SOFT, (guild_rect.centerx, guild_rect.y + 170), center=True)
    draw_text(surf, "Shops", font_headline(40, bold=True), TEXT, (shops_rect.centerx, shops_rect.y + 124), center=True)
    draw_text(surf, "Artifacts, cosmetics, and embassy channels.", font_body(18), TEXT_SOFT, (shops_rect.centerx, shops_rect.y + 170), center=True)
    guild_btn = pygame.Rect(guild_rect.x + 26, guild_rect.bottom - 64, guild_rect.width - 52, 42)
    shops_btn = pygame.Rect(shops_rect.x + 26, shops_rect.bottom - 64, shops_rect.width - 52, 42)
    draw_primary_button(surf, guild_btn, mouse_pos, "Enter Guild Hall")
    draw_secondary_button(surf, shops_btn, mouse_pos, "Open Shops")
    draw_text(surf, "v2.0.0 prototype", font_label(10, bold=True), GOLD_DIM, (WIDTH // 2, HEIGHT - 28), center=True)
    btns["player"] = btns.pop("left")
    btns["guild_hall"] = guild_btn
    btns["shops"] = shops_btn
    return btns


def draw_player_menu(surf, mouse_pos, profile, note_lines: list[str] | None = None):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
    )
    portrait_rect = pygame.Rect(90, 120, 520, 620)
    action_rect = pygame.Rect(700, 148, 520, 420)
    draw_beveled_panel(surf, portrait_rect)
    draw_beveled_panel(surf, action_rect)
    portrait = pygame.Rect(portrait_rect.x + 40, portrait_rect.y + 64, 200, 240)
    fill_gradient(surf, portrait, (70, 62, 34), (22, 24, 28))
    pygame.draw.rect(surf, GOLD_BRIGHT, portrait, 2, border_radius=12)
    exp_value = getattr(profile, "player_exp", 0)
    level_info = level_state(exp_value)
    glory_value = getattr(profile, "ranked_rating", 500)
    rank_label = getattr(profile, "storybook_rank_label", "Baron")
    level_line = f"Level {level_info.level} | {exp_value} EXP"
    exp_progress = f"MAX" if level_info.at_cap else f"{level_info.current_level_exp} / {level_info.next_level_exp}"
    meter_value = 1 if level_info.at_cap else level_info.current_level_exp
    meter_max = 1 if level_info.at_cap else level_info.next_level_exp
    draw_text(surf, level_line, font_body(20, bold=True), GOLD_BRIGHT, (portrait_rect.x + 280, portrait_rect.y + 132))
    draw_text(surf, f"{rank_label} | {glory_value} Glory", font_body(20, bold=True), TEXT_SOFT, (portrait_rect.x + 280, portrait_rect.y + 166))
    draw_text(surf, f"Gold {getattr(profile, 'gold', 0)}", font_body(18, bold=True), TEXT_SOFT, (portrait_rect.x + 280, portrait_rect.y + 208))
    draw_meter(
        surf,
        pygame.Rect(portrait_rect.x + 40, portrait_rect.y + 352, 430, 16),
        meter_value,
        meter_max,
        right_label=exp_progress,
    )
    inventory_btn = pygame.Rect(action_rect.x + 60, action_rect.y + 74, action_rect.width - 120, 66)
    friends_btn = pygame.Rect(action_rect.x + 60, action_rect.y + 156, action_rect.width - 120, 66)
    closet_btn = pygame.Rect(action_rect.x + 60, action_rect.y + 238, action_rect.width - 120, 66)
    trophies_btn = pygame.Rect(action_rect.x + 60, action_rect.y + 320, action_rect.width - 120, 66)
    draw_secondary_button(surf, inventory_btn, mouse_pos, "Inventory")
    draw_secondary_button(surf, friends_btn, mouse_pos, "Friends")
    draw_secondary_button(surf, closet_btn, mouse_pos, "Closet")
    draw_secondary_button(surf, trophies_btn, mouse_pos, "Trophies")
    btns["back"] = btns.pop("left")
    btns["inventory"] = inventory_btn
    btns["friends"] = friends_btn
    btns["closet"] = closet_btn
    btns["trophies"] = trophies_btn
    return btns


def draw_inventory_screen(surf, mouse_pos, owned_artifacts, selected_index: int = 0):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Inventory",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Owned artifacts and attunement details",
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
        draw_text(surf, selected.name, font_headline(34, bold=True), TEXT, (detail_rect.x + 28, detail_rect.y + 64))
        draw_text(surf, f"Attunement: {', '.join(selected.attunement)}", font_label(12, bold=True), GOLD_BRIGHT, (detail_rect.x + 28, detail_rect.y + 112))
        lines = [
            f"Stat Bonus: +{selected.amount} {selected.stat.title()}",
            f"{'Reactive Spell' if selected.reactive else 'Spell'}: {selected.spell.name}",
            selected.spell.description or selected.spell.name,
            selected.description or "No additional field note recorded.",
        ]
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
        subtitle="Manual friend ledger with one-click LAN host lookup",
    )
    list_rect = pygame.Rect(74, 108, 344, 726)
    editor_rect = pygame.Rect(448, 108, 844, 430)
    notes_rect = pygame.Rect(448, 566, 844, 268)
    draw_beveled_panel(surf, list_rect, title="Friend Ledger")
    draw_beveled_panel(surf, editor_rect, title="Friend Entry")
    draw_beveled_panel(surf, notes_rect, title="LAN Shortcut Notes")

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

    draw_text(surf, "What clicking a saved friend does", font_label(12, bold=True), TEXT_MUTE, (editor_rect.x + 26, editor_rect.y + 276))
    helper_lines = [
        "It selects the saved entry and loads the editor fields.",
        "If that host is currently answering on the Fabled LAN port, its IP is copied into the LAN join field automatically.",
        "The saved ledger only stores the friend's name and host IP.",
    ]
    for index, line in enumerate(helper_lines):
        draw_text(surf, line, font_body(17), TEXT_SOFT, (editor_rect.x + 26, editor_rect.y + 304 + index * 24))

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


def draw_guild_hall(surf, mouse_pos):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Guild Hall",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    quests_btn = pygame.Rect(420, 178, 560, 140)
    bouts_btn = pygame.Rect(420, 380, 560, 140)
    catalog_btn = pygame.Rect(420, 582, 560, 140)
    draw_primary_button(surf, quests_btn, mouse_pos, "Quests")
    draw_primary_button(surf, bouts_btn, mouse_pos, "Bouts")
    draw_primary_button(surf, catalog_btn, mouse_pos, "Catalog")
    btns["back"] = btns.pop("left")
    btns["quests"] = quests_btn
    btns["bouts"] = bouts_btn
    btns["catalog"] = catalog_btn
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
        "Shops",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Artifacts, cosmetics, and embassy channels",
    )
    tab_buttons = []
    tab_width = 132
    tab_gap = 12
    tabs_total_width = len(SHOP_TABS) * tab_width + max(0, len(SHOP_TABS) - 1) * tab_gap
    tab_x = WIDTH // 2 - tabs_total_width // 2
    for index, tab_name in enumerate(SHOP_TABS):
        rect = pygame.Rect(tab_x + index * (tab_width + tab_gap), 92, tab_width, 38)
        draw_secondary_button(surf, rect, mouse_pos, tab_name, active=tab_name == active_tab)
        tab_buttons.append((rect, tab_name))
    cosmetics_panel = pygame.Rect(150, 170, 220, 452)
    inventory_panel = pygame.Rect(400, 170, 640, 560)
    embassy_panel = pygame.Rect(1070, 170, 200, 360)
    wealth_panel = pygame.Rect(1070, 550, 200, 180)
    draw_beveled_panel(surf, cosmetics_panel, title="Cosmetics")
    draw_beveled_panel(surf, inventory_panel, title=active_tab)
    draw_beveled_panel(surf, embassy_panel, title="Offer Detail")
    draw_beveled_panel(surf, wealth_panel, title="Treasury")
    cosmetic_buttons = []
    owned_items = owned_items or set()
    owned_cosmetics = owned_cosmetics or set()
    for index, name in enumerate(COSMETIC_CATEGORIES):
        rect = pygame.Rect(cosmetics_panel.x + 18, cosmetics_panel.y + 56 + index * 74, cosmetics_panel.width - 36, 56)
        draw_secondary_button(surf, rect, mouse_pos, name, active=index == cosmetic_index)
        cosmetic_buttons.append((rect, index))
    items = shop_items_for_tab(active_tab)
    max_scroll = max(0, len(items) - 6)
    item_scroll = max(0, min(item_scroll, max_scroll))
    visible_items = items[item_scroll:item_scroll + 6]
    item_buttons = []
    for index, item in enumerate(visible_items):
        row = index // 2
        col = index % 2
        rect = pygame.Rect(inventory_panel.x + 24 + col * 300, inventory_panel.y + 58 + row * 140, 276, 116)
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
        draw_text(surf, item["name"], font_headline(20, bold=True), TEXT, (rect.x + 16, rect.y + 42))
        draw_text(surf, item["subtitle"], font_body(15), TEXT_SOFT, (rect.x + 16, rect.y + 74))
        item_buttons.append((rect, item["id"]))

    if not visible_items:
        draw_text(surf, shop_tab_note(active_tab), font_body(19), TEXT_SOFT, (inventory_panel.x + 26, inventory_panel.y + 76))

    selected_item = next((item for item in items if focus_kind == "item" and item["id"] == focus_value), items[0] if items else None)
    buy_label = "Purchase"
    buy_disabled = False
    detail_lines = []
    detail_title = "Select A Wares Card"
    if focus_kind == "cosmetic":
        detail_title = str(focus_value or COSMETIC_CATEGORIES[cosmetic_index])
        price = 120 + cosmetic_index * 40
        buy_label = "Unlock Bundle"
        buy_disabled = detail_title in owned_cosmetics
        detail_lines = [
            "Commander-only cosmetic unlock.",
            f"Price: {price} Gold",
            "Use the left rail to browse Hats, Shirts, Pants, Socks, and Shoes.",
        ]
    elif focus_kind == "embassy":
        detail_title = "Embassy Charter"
        buy_label = "Info Only"
        buy_disabled = True
        detail_lines = [
            "The embassy remains part of the final shell.",
            "It does not sell battle items in the current build.",
            "Use the left rail for cosmetics and the Artifacts tab for purchasable relics.",
        ]
    elif selected_item is not None:
        detail_title = selected_item["name"]
        item_key = selected_item["id"]
        buy_disabled = item_key in owned_items
        detail_lines = [
            selected_item["subtitle"],
            f"Price: {selected_item['price']} Gold",
            "Purchases unlock immediately in the commander collection.",
        ]
    else:
        buy_disabled = True
        buy_label = "Unavailable"
        detail_title = active_tab
        detail_lines = [
            shop_tab_note(active_tab),
            "Only the Artifacts tab currently contains purchasable battle wares.",
        ]

    draw_text(surf, detail_title, font_headline(24, bold=True), TEXT, (embassy_panel.x + 18, embassy_panel.y + 56))
    for index, line in enumerate(detail_lines[:4]):
        draw_text(surf, line, font_body(16), TEXT_SOFT, (embassy_panel.x + 18, embassy_panel.y + 100 + index * 24))
    embassy_btn = pygame.Rect(embassy_panel.x + 20, embassy_panel.bottom - 116, embassy_panel.width - 40, 42)
    buy_btn = pygame.Rect(wealth_panel.x + 18, wealth_panel.bottom - 56, wealth_panel.width - 36, 38)
    prev_rect = pygame.Rect(inventory_panel.x + 24, inventory_panel.bottom - 48, 124, 34)
    next_rect = pygame.Rect(inventory_panel.right - 148, inventory_panel.bottom - 48, 124, 34)
    draw_secondary_button(surf, embassy_btn, mouse_pos, "View Embassy", active=focus_kind == "embassy")
    draw_primary_button(surf, buy_btn, mouse_pos, buy_label, disabled=buy_disabled)
    draw_secondary_button(surf, prev_rect, mouse_pos, "Prev", active=item_scroll > 0)
    draw_secondary_button(surf, next_rect, mouse_pos, "Next", active=item_scroll < max_scroll)
    draw_text(surf, "Gold", font_label(11, bold=True), TEXT_MUTE, (wealth_panel.x + 18, wealth_panel.y + 60))
    draw_text(surf, str(getattr(profile, "gold", 0) if profile is not None else 0), font_headline(24, bold=True), GOLD_BRIGHT, (wealth_panel.right - 18, wealth_panel.y + 58), right=True)
    draw_text(surf, "Spending Note", font_label(11, bold=True), TEXT_MUTE, (wealth_panel.x + 18, wealth_panel.y + 106))
    for index, line in enumerate(_wrap_text_block(status_message or "Treasury standing is stable.", font_body(14), wealth_panel.width - 36)[:5]):
        draw_text(surf, line, font_body(14), TEXT_SOFT, (wealth_panel.x + 18, wealth_panel.y + 132 + index * 18))
    btns["back"] = btns.pop("left")
    btns["tabs"] = tab_buttons
    btns["cosmetics"] = cosmetic_buttons
    btns["items"] = item_buttons
    btns["embassy"] = embassy_btn
    btns["buy"] = buy_btn
    btns["shop_prev"] = prev_rect
    btns["shop_next"] = next_rect
    btns["shop_scroll_max"] = max_scroll
    return btns


def draw_quests_menu(surf, mouse_pos, mode_summaries: list[dict] | None = None):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Quests",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=None,
    )
    ai_rect = pygame.Rect(220, 130, 420, 120)
    lan_rect = pygame.Rect(760, 130, 420, 120)
    draw_primary_button(surf, ai_rect, mouse_pos, "Vs AI")
    draw_primary_button(surf, lan_rect, mouse_pos, "LAN")
    summaries = mode_summaries or []
    panel_y = 312
    for index, summary in enumerate(summaries[:2]):
        rect = pygame.Rect(160 + index * 540, panel_y, 500, 360)
        title = f"{summary.get('label', 'Quest')} Streak"
        draw_beveled_panel(surf, rect, title=title)
        draw_text(surf, summary.get("streak_text", "No active streak"), font_headline(28, bold=True), GOLD_BRIGHT if summary.get("active") else TEXT, (rect.x + 24, rect.y + 68))
        draw_text(surf, f"Losses: {summary.get('loss_text', '0 / 3')}", font_body(18), TEXT_SOFT, (rect.x + 24, rect.y + 112))
        draw_text(surf, f"Pressure: {summary.get('pressure', 'Steady')}", font_body(18), TEXT_SOFT, (rect.x + 24, rect.y + 142))
        draw_text(surf, "Current Team", font_label(11, bold=True), TEXT_MUTE, (rect.x + 24, rect.y + 190))
        for row_index, line in enumerate(summary.get("party_lines", ["No current streak"])[:3]):
            draw_text(surf, line, font_body(18), TEXT_SOFT, (rect.x + 24, rect.y + 220 + row_index * 28))
    btns["back"] = btns.pop("left")
    btns["vs_ai"] = ai_rect
    btns["vs_lan"] = lan_rect
    return btns


def draw_quest_draft(surf, mouse_pos, offer_ids, focused_id, selected_ids):
    draw_background(surf)
    progress = f"Pick {len(selected_ids) + 1} of 3"
    btns = draw_top_bar(
        surf,
        "Quest Draft",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=progress,
    )
    cards = []
    start_x = 260
    start_y = 114
    for index, adventurer_id in enumerate(offer_ids):
        adventurer = ADVENTURERS_BY_ID[adventurer_id]
        row = index // 3
        col = index % 3
        rect = pygame.Rect(start_x + col * 224, start_y + row * 258, 204, 238)
        cards.append((draw_adventurer_card(
            surf,
            rect,
            mouse_pos,
            adventurer,
            selected=adventurer_id == focused_id,
            unavailable=adventurer_id in selected_ids,
            small=True,
        ), adventurer_id))
    party_rect = pygame.Rect(248, 650, 456, 186)
    detail_rect = pygame.Rect(742, 578, 610, 258)
    draw_beveled_panel(surf, party_rect, title="Selected Party")
    draw_beveled_panel(surf, detail_rect, title="Focused Adventurer")
    slot_buttons = []
    for index in range(3):
        rect = pygame.Rect(party_rect.x + 18 + index * 144, party_rect.y + 54, 126, 110)
        if index < len(selected_ids):
            adventurer = ADVENTURERS_BY_ID[selected_ids[index]]
            draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=True, small=True, tag_line="LOCKED IN")
            slot_buttons.append((rect, selected_ids[index]))
        else:
            draw_beveled_panel(surf, rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
            draw_text(surf, "Available", font_label(11, bold=True), TEXT_MUTE, rect.center, center=True)
    focused = ADVENTURERS_BY_ID[focused_id]
    draw_text(surf, focused.name, font_headline(28, bold=True), TEXT, (detail_rect.x + 22, detail_rect.y + 52))
    tag_x = detail_rect.x + 22
    for role in role_tags_for_adventurer(focused):
        chip_rect = pygame.Rect(tag_x, detail_rect.y + 88, 82, 22)
        draw_chip(surf, chip_rect, role.upper(), ROLE_COLORS.get(role, GOLD_BRIGHT))
        tag_x += 90
    draw_text(surf, f"HP {focused.hp}   ATK {focused.attack}   DEF {focused.defense}   SPD {focused.speed}", font_label(13, bold=True), TEXT_SOFT, (detail_rect.x + 22, detail_rect.y + 126))
    draw_text(surf, focused.innate.name, font_label(12, bold=True), GOLD_BRIGHT, (detail_rect.x + 22, detail_rect.y + 160))
    draw_text(surf, focused.innate.description, font_body(16), TEXT_SOFT, (detail_rect.x + 22, detail_rect.y + 182))
    draw_text(surf, f"Weapons: {focused.signature_weapons[0].name} / {focused.signature_weapons[1].name}", font_body(16, bold=True), TEXT_SOFT, (detail_rect.x + 22, detail_rect.y + 212))
    draw_text(surf, f"Ultimate: {focused.ultimate.name}", font_body(16, bold=True), TEXT_SOFT, (detail_rect.x + 22, detail_rect.y + 236))
    pick_btn = pygame.Rect(detail_rect.right - 198, detail_rect.bottom - 52, 176, 36)
    continue_btn = pygame.Rect(party_rect.x + 18, party_rect.bottom - 46, party_rect.width - 36, 32)
    draw_primary_button(surf, pick_btn, mouse_pos, "Pick Adventurer", disabled=focused_id in selected_ids or len(selected_ids) >= 3)
    draw_secondary_button(surf, continue_btn, mouse_pos, "Continue To Loadouts", active=len(selected_ids) == 3)
    btns["back"] = btns.pop("left")
    btns["cards"] = cards
    btns["party_slots"] = slot_buttons
    btns["pick"] = pick_btn
    btns["continue"] = continue_btn
    return btns


def _active_weapon_for_member(member):
    adventurer = ADVENTURERS_BY_ID[member["adventurer_id"]]
    weapon_id = member["primary_weapon_id"] or adventurer.signature_weapons[0].id
    return next(weapon for weapon in adventurer.signature_weapons if weapon.id == weapon_id)


def _member_index_for_slot(members, slot: str):
    for index, member in enumerate(members):
        if member["slot"] == slot:
            return index
    return None


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
    if effect.spread:
        parts.append("Spread")
    if effect.counts_as_spell:
        parts.append("Spell")
    return parts


def _effect_text(effect):
    parts = _effect_parts(effect)
    if effect.description:
        return f"{' | '.join(parts)} - {effect.description}" if parts else effect.description
    return " | ".join(parts) if parts else effect.name


def _weapon_detail_lines(weapon):
    lines = [f"{weapon.kind.title()} weapon"]
    strike_text = _effect_text(weapon.strike)
    if strike_text:
        lines.append(f"Strike: {strike_text}")
    for passive in weapon.passive_skills:
        lines.append(f"Skill: {passive.name} - {passive.description}")
    for spell in weapon.spells:
        lines.append(f"Spell: {spell.name} - {_effect_text(spell)}")
    if weapon.ammo:
        lines.append(f"Ammo: {weapon.ammo}")
    return lines


def _artifact_detail_lines(artifact):
    if artifact is None:
        return ["No artifact selected."]
    spell_prefix = "Reaction" if artifact.reactive else "Spell"
    lines = [
        f"+{artifact.amount} {artifact.stat.title()}",
        f"Attunement: {', '.join(artifact.attunement)}",
        f"{spell_prefix}: {artifact.spell.name} - {_effect_text(artifact.spell)}",
    ]
    if artifact.description:
        lines.append(artifact.description)
    return lines


def _draw_wrapped_lines(surf, lines, x, y, width, *, font, color, line_height):
    offset = 0
    for raw_line in lines:
        for wrapped in _wrap_text_block(raw_line, font, width):
            draw_text(surf, wrapped, font, color, (x, y + offset))
            offset += line_height
    return offset


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


def _draw_loadout_detail_panel(surf, rect, mouse_pos, members, selected_index, *, allowed_artifact_ids=None):
    draw_beveled_panel(surf, rect, title="Adventurer Detail")
    buttons = {
        "weapon_prev": None,
        "weapon_next": None,
        "classes": [],
        "skills": [],
        "artifacts": [],
    }
    if not members:
        draw_text(surf, "Select an adventurer to begin.", font_headline(24, bold=True), TEXT, (rect.x + 24, rect.y + 72))
        return buttons

    selected_index = max(0, min(selected_index, len(members) - 1))
    member = members[selected_index]
    adventurer = ADVENTURERS_BY_ID[member["adventurer_id"]]
    selected_weapon = _active_weapon_for_member(member)
    class_name = member["class_name"]
    current_skill = next(skill for skill in CLASS_SKILLS[class_name] if skill.id == member["class_skill_id"])
    artifact_ids = compatible_artifact_ids(class_name, allowed_artifact_ids)
    current_artifact = ARTIFACTS_BY_ID.get(member.get("artifact_id"))
    used_by_others = {
        other.get("artifact_id")
        for index, other in enumerate(members)
        if index != selected_index and other.get("artifact_id") is not None
    }

    draw_text(surf, adventurer.name, font_headline(30, bold=True), TEXT, (rect.x + 22, rect.y + 54))
    draw_text(surf, f"{SLOT_LABELS[member['slot']]} | HP {adventurer.hp} | ATK {adventurer.attack} | DEF {adventurer.defense} | SPD {adventurer.speed}", font_body(16, bold=True), TEXT_SOFT, (rect.x + 22, rect.y + 92))
    draw_text(surf, adventurer.innate.name, font_label(11, bold=True), GOLD_BRIGHT, (rect.x + 22, rect.y + 124))
    _draw_wrapped_lines(surf, [adventurer.innate.description], rect.x + 22, rect.y + 146, rect.width - 44, font=font_body(15), color=TEXT_SOFT, line_height=20)

    weapon_panel = pygame.Rect(rect.x + 22, rect.y + 204, rect.width - 44, 144)
    draw_beveled_panel(surf, weapon_panel, title="Primary Weapon")
    prev_rect = pygame.Rect(weapon_panel.x + 10, weapon_panel.y + 48, 34, 34)
    next_rect = pygame.Rect(weapon_panel.right - 44, weapon_panel.y + 48, 34, 34)
    draw_secondary_button(surf, prev_rect, mouse_pos, "<")
    draw_secondary_button(surf, next_rect, mouse_pos, ">")
    buttons["weapon_prev"] = prev_rect
    buttons["weapon_next"] = next_rect
    draw_text(surf, selected_weapon.name, font_headline(24, bold=True), TEXT, (weapon_panel.x + 56, weapon_panel.y + 48))
    draw_text(surf, f"Alternate: {next(weapon.name for weapon in adventurer.signature_weapons if weapon.id != selected_weapon.id)}", font_body(15), TEXT_MUTE, (weapon_panel.x + 56, weapon_panel.y + 80))
    _draw_wrapped_lines(surf, _weapon_detail_lines(selected_weapon), weapon_panel.x + 16, weapon_panel.y + 108, weapon_panel.width - 32, font=font_body(14), color=TEXT_SOFT, line_height=18)

    class_y = weapon_panel.bottom + 18
    draw_text(surf, "Class", font_label(11, bold=True), TEXT_MUTE, (rect.x + 22, class_y))
    class_buttons = []
    class_button_width = 76
    class_names = list(CLASS_ORDER)
    for index, cls_name in enumerate(class_names):
        row = index // 3
        col = index % 3
        cls_rect = pygame.Rect(rect.x + 22 + col * 84, class_y + 18 + row * 42, class_button_width, 32)
        draw_secondary_button(surf, cls_rect, mouse_pos, cls_name, active=cls_name == class_name)
        class_buttons.append((cls_rect, cls_name))
    buttons["classes"] = class_buttons
    draw_text(surf, CLASS_SUMMARIES.get(class_name, ""), font_body(14), TEXT_SOFT, (rect.x + 22, class_y + 106))

    skill_label_y = class_y + 138
    draw_text(surf, "Class Skill", font_label(11, bold=True), TEXT_MUTE, (rect.x + 22, skill_label_y))
    skill_buttons = []
    hovered_skill = None
    skills = CLASS_SKILLS[class_name]
    skill_width = (rect.width - 64) // 3
    for index, skill in enumerate(skills):
        skill_rect = pygame.Rect(rect.x + 22 + index * (skill_width + 10), skill_label_y + 18, skill_width, 44)
        draw_secondary_button(surf, skill_rect, mouse_pos, skill.name, active=skill.id == current_skill.id)
        skill_buttons.append((skill_rect, skill.id))
        if skill_rect.collidepoint(mouse_pos):
            hovered_skill = skill
    buttons["skills"] = skill_buttons
    skill_preview = hovered_skill or current_skill
    skill_detail_rect = pygame.Rect(rect.x + 22, skill_label_y + 74, rect.width - 44, 68)
    draw_beveled_panel(surf, skill_detail_rect, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    draw_text(surf, skill_preview.name, font_body(17, bold=True), GOLD_BRIGHT, (skill_detail_rect.x + 14, skill_detail_rect.y + 14))
    _draw_wrapped_lines(surf, [skill_preview.description], skill_detail_rect.x + 14, skill_detail_rect.y + 38, skill_detail_rect.width - 28, font=font_body(14), color=TEXT_SOFT, line_height=18)

    artifact_label_y = skill_detail_rect.bottom + 18
    draw_text(surf, "Artifact", font_label(11, bold=True), TEXT_MUTE, (rect.x + 22, artifact_label_y))
    artifact_buttons = []
    hovered_artifact = None
    for index, artifact_id in enumerate(artifact_ids):
        artifact = ARTIFACTS_BY_ID[artifact_id]
        row = index // 2
        col = index % 2
        art_rect = pygame.Rect(rect.x + 22 + col * 228, artifact_label_y + 18 + row * 38, 218, 30)
        locked = artifact_id in used_by_others
        draw_secondary_button(surf, art_rect, mouse_pos, artifact.name, active=artifact_id == member.get("artifact_id") and not locked)
        if locked:
            draw_text(surf, "TAKEN", font_label(10, bold=True), EMBER, (art_rect.right - 10, art_rect.y + 9), right=True)
        artifact_buttons.append((art_rect, artifact_id, locked))
        if art_rect.collidepoint(mouse_pos):
            hovered_artifact = artifact
    buttons["artifacts"] = artifact_buttons
    artifact_preview = hovered_artifact or current_artifact or (ARTIFACTS_BY_ID[artifact_ids[0]] if artifact_ids else None)
    artifact_detail_rect = pygame.Rect(rect.x + 22, rect.bottom - 116, rect.width - 44, 94)
    draw_beveled_panel(surf, artifact_detail_rect, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    preview_name = artifact_preview.name if artifact_preview is not None else "No artifact available"
    draw_text(surf, preview_name, font_body(17, bold=True), GOLD_BRIGHT if artifact_preview is not None else TEXT_MUTE, (artifact_detail_rect.x + 14, artifact_detail_rect.y + 12))
    _draw_wrapped_lines(surf, _artifact_detail_lines(artifact_preview), artifact_detail_rect.x + 14, artifact_detail_rect.y + 36, artifact_detail_rect.width - 28, font=font_body(13), color=TEXT_SOFT, line_height=16)
    return buttons


def _draw_loadout_summary_panel(surf, rect, summary_blocks, waiting_note, mouse_pos, confirm_label, confirm_disabled):
    draw_beveled_panel(surf, rect, title="Loadout Summary")
    y = rect.y + 60
    for title, lines in summary_blocks:
        draw_text(surf, title, font_label(11, bold=True), TEXT_MUTE, (rect.x + 18, y))
        y += 24
        for line in lines:
            y += _draw_wrapped_lines(surf, [line], rect.x + 18, y, rect.width - 36, font=font_body(15), color=TEXT_SOFT, line_height=20)
            y += 6
        y += 8
    if waiting_note:
        wait_rect = pygame.Rect(rect.x + 18, rect.bottom - 174, rect.width - 36, 76)
        draw_beveled_panel(surf, wait_rect, fill_top=SURFACE_HIGH, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
        _draw_wrapped_lines(surf, [waiting_note], wait_rect.x + 12, wait_rect.y + 12, wait_rect.width - 24, font=font_body(14), color=GOLD_BRIGHT, line_height=18)
    confirm_rect = pygame.Rect(rect.x + 18, rect.bottom - 72, rect.width - 36, 44)
    draw_primary_button(surf, confirm_rect, mouse_pos, confirm_label, disabled=confirm_disabled)
    return confirm_rect


def draw_quest_loadout(surf, mouse_pos, setup_state, selected_index, *, player_team_num: int = 1, waiting_note: str = "", drag_state: dict | None = None):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Quest Loadout Confirm",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Lock weapon, class, class skill, artifact, and formation",
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
    )
    summary_blocks = [
        ("Role Summary", [quest_role_summary(members)]),
        ("Warnings", quest_warnings(members)),
        ("Quick Notes", recommendation_notes(members)),
    ]
    confirm_btn = _draw_loadout_summary_panel(surf, right_rect, summary_blocks, waiting_note, mouse_pos, "Confirm Loadouts", len(members) != 3)
    btns["back"] = btns.pop("left")
    btns["formation_members"] = formation_members
    btns["formation_slots"] = formation_slots
    btns["weapon_prev"] = detail_buttons["weapon_prev"]
    btns["weapon_next"] = detail_buttons["weapon_next"]
    btns["classes"] = detail_buttons["classes"]
    btns["skills"] = detail_buttons["skills"]
    btns["artifacts"] = detail_buttons["artifacts"]
    btns["confirm"] = confirm_btn
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
    ai_rect = pygame.Rect(320, 240, 760, 150)
    lan_rect = pygame.Rect(320, 470, 760, 150)
    draw_primary_button(surf, ai_rect, mouse_pos, "Vs AI")
    draw_primary_button(surf, lan_rect, mouse_pos, "LAN")
    btns["back"] = btns.pop("left")
    btns["vs_ai"] = ai_rect
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
        subtitle="Prepare the duel and lock both sides before drafting",
    )
    p1_rect = pygame.Rect(122, 170, 420, 360)
    p2_rect = pygame.Rect(858, 170, 420, 360)
    rules_rect = pygame.Rect(430, 572, 540, 188)
    begin_btn = pygame.Rect(1010, 678, 268, 44)
    rival_label = "LAN Rival" if opponent_mode == "lan" else "AI Rival"
    draw_beveled_panel(surf, p1_rect, title="Player 1 • You" if player_seat == 1 else f"Player 1 • {rival_label}")
    draw_beveled_panel(surf, p2_rect, title="Player 2 • You" if player_seat == 2 else f"Player 2 • {rival_label}")
    draw_beveled_panel(surf, rules_rect, title="Lobby Rules")
    ready1 = pygame.Rect(p1_rect.x + 28, p1_rect.bottom - 60, p1_rect.width - 56, 40)
    ready2 = pygame.Rect(p2_rect.x + 28, p2_rect.bottom - 60, p2_rect.width - 56, 40)
    draw_text(surf, "Draft Order", font_label(12, bold=True), TEXT_MUTE, (rules_rect.x + 24, rules_rect.y + 66))
    draw_text(surf, "A shared pool of 9 appears after both sides are ready. Picks alternate until both rosters hit 3.", font_body(18), TEXT_SOFT, (rules_rect.x + 24, rules_rect.y + 96))
    seat_note = "You are currently queued for the second seat and will gain the round-one bonus swap." if player_seat == 2 else "The rival is queued for the second seat and will gain the round-one bonus swap."
    draw_text(surf, seat_note, font_body(17), GOLD_BRIGHT, (rules_rect.x + 24, rules_rect.y + 144))
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


def draw_bout_draft(surf, mouse_pos, pool_ids, focused_id, team1_ids, team2_ids, current_player, *, player_seat: int = 1):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Bout Draft",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle=f"{'Your' if current_player == player_seat else 'AI Rival'} Pick • Player {current_player}",
    )
    pick_pool = []
    for index, adventurer_id in enumerate(pool_ids):
        adventurer = ADVENTURERS_BY_ID[adventurer_id]
        row = index // 3
        col = index % 3
        rect = pygame.Rect(382 + col * 214, 118 + row * 186, 194, 170)
        unavailable = adventurer_id in team1_ids or adventurer_id in team2_ids
        pick_pool.append((draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=focused_id == adventurer_id, unavailable=unavailable, small=True), adventurer_id))
    side_panel = pygame.Rect(26, 118, 320, 534)
    enemy_panel = pygame.Rect(1054, 118, 320, 534)
    detail_rect = pygame.Rect(264, 670, 872, 184)
    draw_beveled_panel(surf, side_panel, title="Player 1 • You" if player_seat == 1 else "Player 1 • AI Rival")
    draw_beveled_panel(surf, enemy_panel, title="Player 2 • You" if player_seat == 2 else "Player 2 • AI Rival")
    draw_beveled_panel(surf, detail_rect, title="Focused Adventurer")
    for index in range(3):
        rect = pygame.Rect(side_panel.x + 18, side_panel.y + 54 + index * 154, side_panel.width - 36, 128)
        if index < len(team1_ids):
            draw_adventurer_card(surf, rect, mouse_pos, ADVENTURERS_BY_ID[team1_ids[index]], selected=False, small=True, tag_line="DRAFTED")
        else:
            draw_beveled_panel(surf, rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
            draw_text(surf, "Open Slot", font_label(12, bold=True), TEXT_MUTE, rect.center, center=True)
    for index in range(3):
        rect = pygame.Rect(enemy_panel.x + 18, enemy_panel.y + 54 + index * 154, enemy_panel.width - 36, 128)
        if index < len(team2_ids):
            draw_adventurer_card(surf, rect, mouse_pos, ADVENTURERS_BY_ID[team2_ids[index]], selected=False, small=True, tag_line="DRAFTED")
        else:
            draw_beveled_panel(surf, rect, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
            draw_text(surf, "Open Slot", font_label(12, bold=True), TEXT_MUTE, rect.center, center=True)
    focused = ADVENTURERS_BY_ID[focused_id]
    draw_text(surf, focused.name, font_headline(28, bold=True), TEXT, (detail_rect.x + 22, detail_rect.y + 52))
    draw_text(surf, ", ".join(role_tags_for_adventurer(focused)), font_label(12, bold=True), GOLD_BRIGHT, (detail_rect.x + 22, detail_rect.y + 88))
    draw_text(surf, f"Weapons: {focused.signature_weapons[0].name} / {focused.signature_weapons[1].name}", font_body(17, bold=True), TEXT_SOFT, (detail_rect.x + 22, detail_rect.y + 122))
    draft_btn = pygame.Rect(detail_rect.right - 198, detail_rect.bottom - 50, 176, 36)
    can_pick = focused_id not in team1_ids and focused_id not in team2_ids and len(team1_ids) + len(team2_ids) < 6
    draw_primary_button(surf, draft_btn, mouse_pos, "Draft Pick", disabled=not can_pick or current_player != player_seat)
    btns["back"] = btns.pop("left")
    btns["pool"] = pick_pool
    btns["draft"] = draft_btn
    return btns


def draw_bout_loadout(surf, mouse_pos, setup_state, selected_index, *, player_team_num: int = 1, waiting_note: str = "", drag_state: dict | None = None):
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
    )
    opponent_lines = [f"{SLOT_LABELS[member['slot']]}: {ADVENTURERS_BY_ID[member['adventurer_id']].name}" for member in enemy_members]
    pressure_line = "Second seat gets the round-one bonus swap." if player_team_num == 2 else "The rival holds the round-one bonus swap if they drafted second."
    summary_blocks = [
        ("Your Side", [f"Role Summary: {quest_role_summary(members)}", pressure_line]),
        ("Rival Roster", opponent_lines or ["The opposing side is not locked yet."]),
        ("Notes", recommendation_notes(members)[:2]),
    ]
    confirm_btn = _draw_loadout_summary_panel(surf, right_rect, summary_blocks, waiting_note, mouse_pos, "Confirm Bout Loadouts", len(members) != 3)
    btns["back"] = btns.pop("left")
    btns["formation_members"] = formation_members
    btns["formation_slots"] = formation_slots
    btns["weapon_prev"] = detail_buttons["weapon_prev"]
    btns["weapon_next"] = detail_buttons["weapon_next"]
    btns["classes"] = detail_buttons["classes"]
    btns["skills"] = detail_buttons["skills"]
    btns["artifacts"] = detail_buttons["artifacts"]
    btns["confirm"] = confirm_btn
    return btns


def draw_catalog(surf, mouse_pos, section_index, entry_index, scroll: int = 0):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Catalog",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Guild archive of adventurers, class skills, and artifacts",
    )
    rail_rect = pygame.Rect(42, 88, 248, 770)
    list_rect = pygame.Rect(316, 88, 430, 770)
    detail_rect = pygame.Rect(772, 88, 586, 770)
    draw_beveled_panel(surf, rail_rect, title="Sections")
    draw_beveled_panel(surf, list_rect, title="Entries")
    draw_beveled_panel(surf, detail_rect, title="Detail")
    section_buttons = []
    for index, name in enumerate(CATALOG_SECTIONS):
        rect = pygame.Rect(rail_rect.x + 16, rail_rect.y + 54 + index * 66, rail_rect.width - 32, 52)
        draw_secondary_button(surf, rect, mouse_pos, name, active=index == section_index)
        section_buttons.append((rect, index))
    section_name = CATALOG_SECTIONS[section_index]
    entries = catalog_entries(section_name)
    entry_index = min(entry_index, max(0, len(entries) - 1))
    entry_buttons = []
    visible_entries = entries[scroll:scroll + 10]
    for row_index, entry in enumerate(visible_entries):
        actual_index = scroll + row_index
        rect = pygame.Rect(list_rect.x + 18, list_rect.y + 54 + row_index * 68, list_rect.width - 36, 56)
        draw_secondary_button(surf, rect, mouse_pos, entry["title"], active=actual_index == entry_index)
        draw_text(surf, entry["subtitle"], font_body(13), TEXT_SOFT, (rect.x + 16, rect.y + 30))
        entry_buttons.append((rect, actual_index))
    entry = entries[entry_index]
    draw_text(surf, entry["title"], font_headline(32, bold=True), TEXT, (detail_rect.x + 24, detail_rect.y + 62))
    draw_text(surf, entry["subtitle"], font_label(12, bold=True), GOLD_BRIGHT, (detail_rect.x + 24, detail_rect.y + 104))
    for row_index, line in enumerate(_wrap_multiline_block(entry["body"], font_body(18), detail_rect.width - 48, limit=20)):
        draw_text(surf, line, font_body(18), TEXT_SOFT, (detail_rect.x + 24, detail_rect.y + 160 + row_index * 24))
    prev_rect = pygame.Rect(list_rect.x + 18, list_rect.bottom - 54, 124, 36)
    next_rect = pygame.Rect(list_rect.right - 142, list_rect.bottom - 54, 124, 36)
    max_scroll = max(0, len(entries) - 10)
    draw_secondary_button(surf, prev_rect, mouse_pos, "Prev", active=scroll > 0)
    draw_secondary_button(surf, next_rect, mouse_pos, "Next", active=scroll < max_scroll)
    btns["back"] = btns.pop("left")
    btns["sections"] = section_buttons
    btns["entries"] = entry_buttons
    btns["prev_page"] = prev_rect
    btns["next_page"] = next_rect
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
        subtitle=f"{mode_label} over local network",
    )
    left_rect = pygame.Rect(152, 168, 340, 440)
    center_rect = pygame.Rect(528, 168, 344, 440)
    right_rect = pygame.Rect(908, 168, 340, 440)
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
        subtitle="Global accessibility and resolution preferences",
    )
    card = pygame.Rect(360, 170, 680, 430)
    draw_beveled_panel(surf, card, title="Gameplay Preferences")
    tutorial_rect = pygame.Rect(card.x + 50, card.y + 96, card.width - 100, 72)
    fast_rect = pygame.Rect(card.x + 50, card.y + 210, card.width - 100, 72)
    draw_secondary_button(surf, tutorial_rect, mouse_pos, f"Tutorial Popups: {'ON' if tutorials_enabled else 'OFF'}", active=tutorials_enabled)
    draw_secondary_button(surf, fast_rect, mouse_pos, f"Fast Resolution: {'ON' if fast_resolution else 'OFF'}", active=fast_resolution)
    draw_text(surf, "Fast Resolution affects the legacy battle flow; the new storybook HUD resolves by explicit phase steps.", font_body(18), TEXT_SOFT, (card.x + 50, card.y + 314))
    btns["back"] = btns.pop("left")
    btns["tutorials"] = tutorial_rect
    btns["fast"] = fast_rect
    return btns


def _battle_slot_rects():
    return {
        (1, SLOT_BACK_LEFT): pygame.Rect(230, 254, 220, 110),
        (1, SLOT_FRONT): pygame.Rect(360, 398, 244, 126),
        (1, SLOT_BACK_RIGHT): pygame.Rect(230, 552, 220, 110),
        (2, SLOT_BACK_LEFT): pygame.Rect(950, 254, 220, 110),
        (2, SLOT_FRONT): pygame.Rect(794, 398, 244, 126),
        (2, SLOT_BACK_RIGHT): pygame.Rect(950, 552, 220, 110),
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
    log_rect = pygame.Rect(24, 178, 210, 472)
    inspect_rect = pygame.Rect(1166, 178, 210, 472)
    action_rect = pygame.Rect(198, 710, 1004, 144)
    resolve_rect = pygame.Rect(1218, 714, 158, 64)
    draw_beveled_panel(surf, log_rect, title="Battle Log")
    draw_beveled_panel(surf, inspect_rect, title="Inspect")
    draw_beveled_panel(surf, action_rect, title="Command Panel")
    draw_meter(surf, pygame.Rect(450, 668, 220, 16), controller.battle.team1.ultimate_meter, 10, label="Player Ultimate", right_label=f"{controller.battle.team1.ultimate_meter}/10")
    draw_meter(surf, pygame.Rect(732, 668, 220, 16), controller.battle.team2.ultimate_meter, 10, label="Enemy Ultimate", right_label=f"{controller.battle.team2.ultimate_meter}/10", fill=SAPPHIRE)

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
            draw_text(surf, unit.name, font_headline(20, bold=True), TEXT, (rect.x + 14, rect.y + 30))
            draw_text(surf, f"{unit.primary_weapon.name}", font_label(11, bold=True), GOLD_BRIGHT, (rect.x + 14, rect.y + 58))
            draw_meter(surf, pygame.Rect(rect.x + 14, rect.y + 84, rect.width - 28, 12), unit.hp, unit.max_hp, fill=RUBY)
            status_text = ", ".join(status.kind for status in unit.statuses[:3]) or "Ready"
            draw_text(surf, status_text, font_label(10, bold=True), TEXT_SOFT, (rect.x + 14, rect.bottom - 18))
            slot_buttons.append((rect, unit))

    phase_bonus = controller.phase.startswith("bonus")
    phase_color = JADE if phase_bonus else GOLD_BRIGHT
    prompt = "Bonus actions resolve after all normal actions are queued." if phase_bonus else "Queue one normal action for each adventurer before resolving."
    draw_text(surf, prompt, font_body(18), phase_color, (action_rect.x + 22, action_rect.y + 46))
    queue_rows = controller.action_summary_rows(bonus=phase_bonus)
    for index, row in enumerate(queue_rows[:6]):
        label = f"P{row['team_num']} | {row['actor'].name}: {row['label']}"
        draw_text(surf, label, font_label(11, bold=True), TEXT_SOFT, (action_rect.x + 22, action_rect.y + 74 + index * 18))

    action_buttons = []
    spell_buttons = []
    if controller.active_actor is not None and controller.phase in {"action_select", "bonus_select", "action_target", "bonus_target"}:
        available = controller.available_actions()
        for index, choice in enumerate(available):
            rect = pygame.Rect(action_rect.x + 22 + index * 150, action_rect.bottom - 60, 134, 42)
            active = controller.pending_choice is not None and controller.pending_choice.kind == choice.kind
            draw_secondary_button(surf, rect, mouse_pos, choice.label, active=active)
            action_buttons.append((rect, choice.kind))
        if controller.spellbook_open:
            spells = controller.available_bonus_spells(controller.active_actor) if controller.phase.startswith("bonus") else controller.available_spells(controller.active_actor)
            for index, spell in enumerate(spells):
                rect = pygame.Rect(action_rect.x + 22 + index * 158, action_rect.y + 12, 146, 26)
                active = controller.pending_choice is not None and controller.pending_choice.effect_id == spell.id
                draw_secondary_button(surf, rect, mouse_pos, spell.name, active=active)
                spell_buttons.append((rect, spell.id))
        if controller.phase in {"action_target", "bonus_target"}:
            draw_text(surf, "Choose a legal target on the battlefield.", font_body(17, bold=True), phase_color, (action_rect.right - 22, action_rect.y + 46), right=True)

    resolve_label = controller.resolve_button_label() if hasattr(controller, "resolve_button_label") else ("Resolve Bonus Phase" if controller.phase == "bonus_resolve_ready" else "Resolve Actions")
    draw_primary_button(surf, resolve_rect, mouse_pos, resolve_label, disabled=not controller.can_resolve())

    log_lines = controller.battle.log[-12:] or ["No actions resolved yet."]
    for index, line in enumerate(log_lines):
        draw_text(surf, line, font_body(14), TEXT_SOFT if index < len(log_lines) - 1 else GOLD_BRIGHT, (log_rect.x + 14, log_rect.y + 54 + index * 22))

    focus = controller.focus_unit
    if focus is not None:
        draw_text(surf, focus.name, font_headline(24, bold=True), TEXT, (inspect_rect.x + 16, inspect_rect.y + 52))
        draw_text(surf, focus.class_name, font_label(11, bold=True), GOLD_BRIGHT, (inspect_rect.x + 16, inspect_rect.y + 88))
        draw_text(surf, f"HP {focus.hp}/{focus.max_hp}", font_body(17, bold=True), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 126))
        draw_text(surf, f"ATK {focus.get_stat('attack')}  DEF {focus.get_stat('defense')}  SPD {focus.get_stat('speed')}", font_label(11, bold=True), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 154))
        ammo_text = "-"
        if focus.primary_weapon.ammo > 0:
            ammo_text = f"{focus.ammo_remaining.get(focus.primary_weapon.id, focus.primary_weapon.ammo)}/{focus.primary_weapon.ammo}"
        draw_text(surf, f"Weapon: {focus.primary_weapon.name}", font_body(16, bold=True), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 196))
        draw_text(surf, f"Ammo {ammo_text}", font_label(11, bold=True), TEXT_MUTE, (inspect_rect.x + 16, inspect_rect.y + 224))
        draw_text(surf, f"Statuses: {', '.join(status.kind for status in focus.statuses) or 'None'}", font_body(15), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 258))
        draw_text(surf, f"Artifact: {focus.artifact.name if focus.artifact is not None else 'None'}", font_body(15), TEXT_SOFT, (inspect_rect.x + 16, inspect_rect.y + 296))

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
        "Quest Results" if result_kind == "quest" else "Bout Results",
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
