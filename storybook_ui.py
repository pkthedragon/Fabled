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
)
from quests_ruleset_data import ADVENTURERS_BY_ID, ARTIFACTS_BY_ID, CLASS_SKILLS


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
    draw_text(surf, "Artifacts, armory wares, embassy channels, and cosmetics.", font_body(18), TEXT_SOFT, (shops_rect.centerx, shops_rect.y + 170), center=True)
    guild_btn = pygame.Rect(guild_rect.x + 26, guild_rect.bottom - 64, guild_rect.width - 52, 42)
    shops_btn = pygame.Rect(shops_rect.x + 26, shops_rect.bottom - 64, shops_rect.width - 52, 42)
    draw_primary_button(surf, guild_btn, mouse_pos, "Enter Guild Hall")
    draw_secondary_button(surf, shops_btn, mouse_pos, "Open Shops")
    draw_text(surf, "Lumenforge", font_headline(14, bold=True), TEXT_MUTE, (WIDTH // 2, HEIGHT - 48), center=True)
    draw_text(surf, "v2.0.0 prototype", font_label(10, bold=True), GOLD_DIM, (WIDTH // 2, HEIGHT - 28), center=True)
    btns["player"] = btns.pop("left")
    btns["guild_hall"] = guild_btn
    btns["shops"] = shops_btn
    return btns


def draw_player_menu(surf, mouse_pos, profile, note_lines: list[str] | None = None):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Player Menu",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Account, friends, wardrobe, trophies, and standing",
    )
    portrait_rect = pygame.Rect(90, 120, 520, 620)
    action_rect = pygame.Rect(700, 148, 520, 530)
    draw_beveled_panel(surf, portrait_rect, title="Commander Profile")
    draw_beveled_panel(surf, action_rect, title="Profile Links")
    portrait = pygame.Rect(portrait_rect.x + 40, portrait_rect.y + 64, 200, 240)
    fill_gradient(surf, portrait, (70, 62, 34), (22, 24, 28))
    pygame.draw.rect(surf, GOLD_BRIGHT, portrait, 2, border_radius=12)
    draw_text(surf, "CM", font_headline(72, bold=True), PARCHMENT, portrait.center, center=True)
    draw_text(surf, "Commander", font_headline(34, bold=True), TEXT, (portrait_rect.x + 280, portrait_rect.y + 86))
    exp_value = getattr(profile, "player_exp", 0)
    level_value = max(1, exp_value // 100 + 1)
    glory_value = getattr(profile, "ranked_rating", 500)
    rank_label = getattr(profile, "storybook_rank_label", "Baron")
    draw_text(surf, f"Level {level_value} | {exp_value} EXP", font_body(20, bold=True), GOLD_BRIGHT, (portrait_rect.x + 280, portrait_rect.y + 138))
    draw_text(surf, f"{rank_label} | {glory_value} Glory", font_body(20, bold=True), TEXT_SOFT, (portrait_rect.x + 280, portrait_rect.y + 170))
    draw_text(surf, f"Gold {getattr(profile, 'gold', 0)}", font_body(18, bold=True), TEXT_SOFT, (portrait_rect.x + 280, portrait_rect.y + 226))
    draw_meter(surf, pygame.Rect(portrait_rect.x + 40, portrait_rect.y + 352, 430, 16), exp_value % 100, 100, label="Experience", right_label="Next Level")
    draw_text(surf, "This hub only tracks the three long-term account stats that matter in the current build: level, gold, and Glory.", font_body(18), TEXT_SOFT, (portrait_rect.x + 40, portrait_rect.y + 392))
    inventory_btn = pygame.Rect(action_rect.x + 60, action_rect.y + 74, action_rect.width - 120, 66)
    friends_btn = pygame.Rect(action_rect.x + 60, action_rect.y + 156, action_rect.width - 120, 66)
    closet_btn = pygame.Rect(action_rect.x + 60, action_rect.y + 238, action_rect.width - 120, 66)
    trophies_btn = pygame.Rect(action_rect.x + 60, action_rect.y + 320, action_rect.width - 120, 66)
    draw_secondary_button(surf, inventory_btn, mouse_pos, "Inventory")
    draw_secondary_button(surf, friends_btn, mouse_pos, "Friends")
    draw_secondary_button(surf, closet_btn, mouse_pos, "Closet")
    draw_secondary_button(surf, trophies_btn, mouse_pos, "Trophies")
    detail_rect = pygame.Rect(action_rect.x + 48, action_rect.y + 406, action_rect.width - 96, 104)
    draw_beveled_panel(surf, detail_rect, title="Profile Notes")
    for index, line in enumerate((note_lines or [])[:4]):
        draw_text(surf, line, font_body(16), TEXT_SOFT, (detail_rect.x + 18, detail_rect.y + 42 + index * 18))
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
        subtitle="Campaign, bouts, and the sovereign archive",
    )
    banner = pygame.Rect(120, 104, 1160, 140)
    draw_beveled_panel(surf, banner, fill_top=(52, 45, 30), fill_bottom=SURFACE, border=GOLD_DIM)
    draw_text(surf, "Plan your next expedition, tune a duel roster, or study the archive.", font_headline(28, bold=True), TEXT, (banner.x + 40, banner.y + 40))
    draw_text(surf, "The hall is the strategic heart of Fabled: draft, prepare, then descend into a round-driven 3v3 duel.", font_body(20), TEXT_SOFT, (banner.x + 40, banner.y + 84))
    quests_btn = pygame.Rect(120, 286, 360, 176)
    bouts_btn = pygame.Rect(510, 286, 360, 176)
    catalog_btn = pygame.Rect(120, 500, 750, 122)
    intel_panel = pygame.Rect(910, 286, 370, 336)
    draw_beveled_panel(surf, quests_btn, fill_top=(56, 48, 34), fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    draw_beveled_panel(surf, bouts_btn, fill_top=(40, 48, 58), fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    draw_beveled_panel(surf, catalog_btn, fill_top=SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_DIM)
    draw_beveled_panel(surf, intel_panel, title="Sovereign Intel")
    draw_text(surf, "Quests", font_headline(34, bold=True), TEXT, (quests_btn.centerx, quests_btn.y + 72), center=True)
    draw_text(surf, "Show 6, pick 3, then tune the loadout.", font_body(18), TEXT_SOFT, (quests_btn.centerx, quests_btn.y + 118), center=True)
    draw_text(surf, "Bouts", font_headline(34, bold=True), TEXT, (bouts_btn.centerx, bouts_btn.y + 72), center=True)
    draw_text(surf, "Shared pool draft with competitive setup.", font_body(18), TEXT_SOFT, (bouts_btn.centerx, bouts_btn.y + 118), center=True)
    draw_text(surf, "Catalog", font_headline(32, bold=True), TEXT, (catalog_btn.x + 40, catalog_btn.y + 36))
    draw_text(surf, "Adventurers, weapons, class skills, conditions, and battle rules all live in one codex.", font_body(18), TEXT_SOFT, (catalog_btn.x + 40, catalog_btn.y + 76))
    draw_meter(surf, pygame.Rect(intel_panel.x + 24, intel_panel.y + 90, intel_panel.width - 48, 16), 84, 100, label="Guild Stability", right_label="84%")
    draw_meter(surf, pygame.Rect(intel_panel.x + 24, intel_panel.y + 148, intel_panel.width - 48, 16), 62, 100, label="Resource Flow", right_label="62%")
    draw_text(surf, "The current restructuring favors clean draft interfaces, visible formation risk, and battle-state clarity over spectacle.", font_body(18), TEXT_SOFT, (intel_panel.x + 24, intel_panel.y + 206))
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
        subtitle="Premium trade, customization, and embassy channels",
    )
    tab_buttons = []
    tab_x = WIDTH // 2 - 210
    for index, tab_name in enumerate(SHOP_TABS):
        rect = pygame.Rect(tab_x + index * 144, 92, 132, 38)
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
    item_buttons = []
    for index, item in enumerate(items):
        row = index // 2
        col = index % 2
        rect = pygame.Rect(inventory_panel.x + 24 + col * 300, inventory_panel.y + 58 + row * 140, 276, 116)
        selected = focus_kind == "item" and focus_value == item["name"]
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
        item_buttons.append((rect, item["name"]))

    selected_item = next((item for item in items if focus_kind == "item" and item["name"] == focus_value), items[0] if items else None)
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
        buy_label = "Broker Favor"
        detail_lines = [
            "Commission a gold-funded embassy contract.",
            "Embassy favors convert treasury into bespoke wardrobe bundles or curated wares.",
            "The current desktop build keeps it simple: one charter buys a prestige package.",
        ]
    elif selected_item is not None:
        detail_title = selected_item["name"]
        item_key = f"{active_tab}:{selected_item['name']}"
        buy_disabled = item_key in owned_items
        detail_lines = [
            selected_item["subtitle"],
            f"Price: {selected_item['price']} Gold",
            "Purchases are added to the commander collection and reflected on the Player Menu.",
        ]

    draw_text(surf, detail_title, font_headline(24, bold=True), TEXT, (embassy_panel.x + 18, embassy_panel.y + 56))
    for index, line in enumerate(detail_lines[:4]):
        draw_text(surf, line, font_body(16), TEXT_SOFT, (embassy_panel.x + 18, embassy_panel.y + 100 + index * 24))
    embassy_btn = pygame.Rect(embassy_panel.x + 20, embassy_panel.bottom - 116, embassy_panel.width - 40, 42)
    buy_btn = pygame.Rect(wealth_panel.x + 18, wealth_panel.bottom - 56, wealth_panel.width - 36, 38)
    draw_secondary_button(surf, embassy_btn, mouse_pos, "View Embassy", active=focus_kind == "embassy")
    draw_primary_button(surf, buy_btn, mouse_pos, buy_label, disabled=buy_disabled)
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
    return btns


def draw_quests_menu(surf, mouse_pos, selected_index: int, opponent_mode: str, run_summary: dict | None = None):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Quest Board",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Show 6, pick 3, then ride the run until three straight defeats end it",
    )
    list_rect = pygame.Rect(82, 98, 290, 700)
    detail_rect = pygame.Rect(398, 98, 584, 700)
    summary_rect = pygame.Rect(1008, 98, 310, 700)
    draw_beveled_panel(surf, list_rect, title="Available Quests")
    draw_beveled_panel(surf, detail_rect, title="Quest Brief")
    draw_beveled_panel(surf, summary_rect, title="Run State")
    list_buttons = []
    for index, quest in enumerate(STORY_QUESTS):
        rect = pygame.Rect(list_rect.x + 14, list_rect.y + 54 + index * 92, list_rect.width - 28, 78)
        draw_secondary_button(surf, rect, mouse_pos, quest.name, active=index == selected_index)
        draw_text(surf, quest.locale, font_body(14), TEXT_SOFT, (rect.x + 16, rect.y + 40))
        draw_text(surf, quest.difficulty, font_label(10, bold=True), GOLD_BRIGHT, (rect.right - 14, rect.y + 16), right=True)
        list_buttons.append((rect, index))
    quest = STORY_QUESTS[selected_index]
    draw_text(surf, quest.name, font_headline(34, bold=True), TEXT, (detail_rect.x + 28, detail_rect.y + 66))
    draw_text(surf, quest.locale, font_label(12, bold=True), GOLD_BRIGHT, (detail_rect.x + 28, detail_rect.y + 108))
    lines = _wrap_text_block(quest.blurb, font_body(20), detail_rect.width - 56)
    for index, line in enumerate(lines):
        draw_text(surf, line, font_body(20), TEXT_SOFT, (detail_rect.x + 28, detail_rect.y + 150 + index * 28))
    draw_text(surf, "Operational Note", font_label(12, bold=True), TEXT_MUTE, (detail_rect.x + 28, detail_rect.y + 286))
    for index, line in enumerate(_wrap_text_block(quest.note, font_body(18), detail_rect.width - 56)):
        draw_text(surf, line, font_body(18), TEXT_SOFT, (detail_rect.x + 28, detail_rect.y + 314 + index * 24))
    draw_text(surf, "Threat Pattern", font_label(12, bold=True), TEXT_MUTE, (summary_rect.x + 22, summary_rect.y + 70))
    draw_text(surf, quest.threat, font_headline(24, bold=True), TEXT, (summary_rect.x + 22, summary_rect.y + 98))
    draw_meter(surf, pygame.Rect(summary_rect.x + 22, summary_rect.y + 172, summary_rect.width - 44, 16), selected_index + 2, 5, label="Difficulty", right_label=quest.difficulty)
    draw_text(surf, "Gold Reward", font_label(11, bold=True), TEXT_MUTE, (summary_rect.x + 22, summary_rect.y + 232))
    draw_text(surf, str(quest.reward_gold), font_headline(24, bold=True), GOLD_BRIGHT, (summary_rect.right - 22, summary_rect.y + 228), right=True)
    draw_text(surf, "EXP Reward", font_label(11, bold=True), TEXT_MUTE, (summary_rect.x + 22, summary_rect.y + 274))
    draw_text(surf, str(quest.reward_exp), font_headline(24, bold=True), TEXT_SOFT, (summary_rect.right - 22, summary_rect.y + 270), right=True)
    ai_rect = pygame.Rect(summary_rect.x + 22, summary_rect.y + 334, 128, 38)
    lan_rect = pygame.Rect(summary_rect.x + 160, summary_rect.y + 334, 128, 38)
    draw_secondary_button(surf, ai_rect, mouse_pos, "Vs AI", active=opponent_mode == "ai")
    draw_secondary_button(surf, lan_rect, mouse_pos, "Via LAN", active=opponent_mode == "lan")
    summary = run_summary or {}
    draw_text(surf, f"Streak: {summary.get('streak_text', 'Fresh Run')}", font_body(18, bold=True), GOLD_BRIGHT, (summary_rect.x + 22, summary_rect.y + 394))
    draw_text(surf, f"Losses: {summary.get('loss_text', '0 / 3')}", font_body(16), TEXT_SOFT, (summary_rect.x + 22, summary_rect.y + 424))
    draw_text(surf, f"Pressure: {summary.get('pressure', 'Steady')}", font_body(16), TEXT_SOFT, (summary_rect.x + 22, summary_rect.y + 448))
    draw_text(surf, "Current Party", font_label(11, bold=True), TEXT_MUTE, (summary_rect.x + 22, summary_rect.y + 490))
    party_lines = summary.get("party_lines", ["No active party"])
    for index, line in enumerate(party_lines[:3]):
        draw_text(surf, line, font_body(16), TEXT_SOFT, (summary_rect.x + 22, summary_rect.y + 518 + index * 24))
    start_label = "Continue Run" if summary.get("can_continue") else "Start Quest Draft"
    start_btn = pygame.Rect(summary_rect.x + 22, summary_rect.bottom - 116, summary_rect.width - 44, 44)
    new_btn = pygame.Rect(summary_rect.x + 22, summary_rect.bottom - 64, summary_rect.width - 44, 36)
    draw_primary_button(surf, start_btn, mouse_pos, start_label)
    draw_secondary_button(surf, new_btn, mouse_pos, "New Draft")
    btns["back"] = btns.pop("left")
    btns["quest_list"] = list_buttons
    btns["mode_ai"] = ai_rect
    btns["mode_lan"] = lan_rect
    btns["start"] = start_btn
    btns["new_run"] = new_btn
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


def draw_loadout_member_editor(surf, rect, mouse_pos, member, *, selected=False):
    adventurer = ADVENTURERS_BY_ID[member["adventurer_id"]]
    weapon = next(weapon for weapon in adventurer.signature_weapons if weapon.id == (member["primary_weapon_id"] or adventurer.signature_weapons[0].id))
    class_name = member["class_name"]
    skill = next(skill for skill in CLASS_SKILLS[class_name] if skill.id == member["class_skill_id"])
    artifact = ARTIFACTS_BY_ID.get(member["artifact_id"])
    draw_beveled_panel(surf, rect, fill_top=SURFACE_HIGH if selected else SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_BRIGHT if selected else GOLD_DIM)
    draw_text(surf, adventurer.name, font_headline(18, bold=True), TEXT, (rect.x + 14, rect.y + 12))
    fields = [
        ("slot", SLOT_LABELS[member["slot"]]),
        ("class", class_name),
        ("skill", skill.name),
        ("weapon", weapon.name),
        ("artifact", artifact.name if artifact is not None else "None"),
    ]
    field_buttons = []
    for index, (field_name, value) in enumerate(fields):
        button_rect = pygame.Rect(rect.x + 14, rect.y + 42 + index * 36, rect.width - 28, 28)
        draw_secondary_button(surf, button_rect, mouse_pos, f"{field_name.title()}: {value}")
        field_buttons.append((button_rect, field_name))
    return field_buttons


def draw_quest_loadout(surf, mouse_pos, setup_state, selected_index, *, player_team_num: int = 1, waiting_note: str = ""):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Quest Loadout Confirm",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Lock weapon, class, class skill, artifact, and formation",
    )
    left_rect = pygame.Rect(64, 104, 280, 730)
    center_rect = pygame.Rect(370, 104, 540, 730)
    right_rect = pygame.Rect(936, 104, 400, 730)
    draw_beveled_panel(surf, left_rect, title="Party")
    draw_beveled_panel(surf, center_rect, title="Selected Adventurer")
    draw_beveled_panel(surf, right_rect, title="Team Summary")
    selector_buttons = []
    members = setup_state[f"team{player_team_num}"]
    for index, member in enumerate(members):
        adventurer = ADVENTURERS_BY_ID[member["adventurer_id"]]
        rect = pygame.Rect(left_rect.x + 18, left_rect.y + 56 + index * 140, left_rect.width - 36, 122)
        draw_adventurer_card(surf, rect, mouse_pos, adventurer, selected=index == selected_index, small=True, tag_line=SLOT_LABELS[member["slot"]].upper())
        selector_buttons.append((rect, index))
    field_buttons = []
    if members:
        field_buttons = draw_loadout_member_editor(surf, pygame.Rect(center_rect.x + 24, center_rect.y + 64, center_rect.width - 48, 260), mouse_pos, members[selected_index], selected=True)
        focused = ADVENTURERS_BY_ID[members[selected_index]["adventurer_id"]]
        draw_text(surf, focused.innate.name, font_label(11, bold=True), GOLD_BRIGHT, (center_rect.x + 28, center_rect.y + 352))
        for idx, line in enumerate(_wrap_text_block(focused.innate.description, font_body(18), center_rect.width - 56)):
            draw_text(surf, line, font_body(18), TEXT_SOFT, (center_rect.x + 28, center_rect.y + 378 + idx * 24))
        draw_text(surf, f"Ultimate: {focused.ultimate.name}", font_body(18, bold=True), TEXT, (center_rect.x + 28, center_rect.y + 500))
        for idx, line in enumerate(_wrap_text_block(focused.ultimate.description or focused.ultimate.name, font_body(17), center_rect.width - 56)):
            draw_text(surf, line, font_body(17), TEXT_SOFT, (center_rect.x + 28, center_rect.y + 528 + idx * 22))
    draw_text(surf, f"Role Summary: {quest_role_summary(members)}", font_headline(22, bold=True), TEXT, (right_rect.x + 22, right_rect.y + 68))
    draw_text(surf, "Warnings", font_label(12, bold=True), TEXT_MUTE, (right_rect.x + 22, right_rect.y + 124))
    for index, line in enumerate(quest_warnings(members)):
        draw_text(surf, line, font_body(17), TEXT_SOFT, (right_rect.x + 22, right_rect.y + 152 + index * 26))
    draw_text(surf, "Quick Notes", font_label(12, bold=True), TEXT_MUTE, (right_rect.x + 22, right_rect.y + 264))
    for index, line in enumerate(recommendation_notes(members)):
        draw_text(surf, line, font_body(17), TEXT_SOFT, (right_rect.x + 22, right_rect.y + 292 + index * 26))
    if waiting_note:
        for index, line in enumerate(_wrap_text_block(waiting_note, font_body(16), right_rect.width - 44)[:3]):
            draw_text(surf, line, font_body(16), GOLD_BRIGHT, (right_rect.x + 22, right_rect.y + 408 + index * 22))
    confirm_btn = pygame.Rect(right_rect.x + 22, right_rect.bottom - 70, right_rect.width - 44, 44)
    draw_primary_button(surf, confirm_btn, mouse_pos, "Confirm Loadouts", disabled=len(members) != 3)
    btns["back"] = btns.pop("left")
    btns["selectors"] = selector_buttons
    btns["fields"] = [(rect, field) for rect, field in field_buttons]
    btns["confirm"] = confirm_btn
    return btns


def draw_bouts_menu(surf, mouse_pos, selected_mode: int, opponent_mode: str, glory_text: str = ""):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Bouts",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Competitive drafting with a shared pool of nine",
    )
    mode_buttons = []
    for index, mode in enumerate(BOUT_MODES):
        rect = pygame.Rect(132 + (index % 2) * 400, 148 + (index // 2) * 182, 340, 150)
        draw_beveled_panel(surf, rect, fill_top=SURFACE_HIGH if index == selected_mode else SURFACE, fill_bottom=SURFACE_LOW, border=GOLD_BRIGHT if index == selected_mode else GOLD_DIM)
        draw_text(surf, mode["name"], font_headline(28, bold=True), TEXT, (rect.x + 24, rect.y + 36))
        draw_text(surf, mode["subtitle"], font_body(18), TEXT_SOFT, (rect.x + 24, rect.y + 74))
        draw_text(surf, mode["note"], font_body(16), TEXT_MUTE, (rect.x + 24, rect.y + 104))
        mode_buttons.append((rect, index))
    rules_rect = pygame.Rect(882, 148, 386, 332)
    draw_beveled_panel(surf, rules_rect, title="Rules Explainer")
    points = [
        "Shared pool of 9 adventurers.",
        "Players alternate picks until both have 3.",
        "Loadouts lock after the draft and before round one.",
        "Bonus actions resolve in a distinct phase after normal actions.",
    ]
    for index, line in enumerate(points):
        draw_text(surf, line, font_body(18), TEXT_SOFT, (rules_rect.x + 24, rules_rect.y + 72 + index * 38))
    ai_rect = pygame.Rect(882, 500, 184, 38)
    lan_rect = pygame.Rect(1084, 500, 184, 38)
    draw_secondary_button(surf, ai_rect, mouse_pos, "Vs AI", active=opponent_mode == "ai")
    draw_secondary_button(surf, lan_rect, mouse_pos, "Via LAN", active=opponent_mode == "lan")
    if glory_text:
        draw_text(surf, glory_text, font_body(18, bold=True), GOLD_BRIGHT, (rules_rect.x + 24, rules_rect.y + 276))
    enter_btn = pygame.Rect(882, 560, 386, 46)
    draw_primary_button(surf, enter_btn, mouse_pos, "Open Bout Lobby")
    btns["back"] = btns.pop("left")
    btns["modes"] = mode_buttons
    btns["mode_ai"] = ai_rect
    btns["mode_lan"] = lan_rect
    btns["enter"] = enter_btn
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


def draw_bout_loadout(surf, mouse_pos, setup_state, *, player_team_num: int = 1):
    draw_background(surf)
    btns = draw_top_bar(
        surf,
        "Bout Loadout Confirm",
        mouse_pos,
        left_icon="<",
        right_icons=(("settings", "S", False), ("quit", "X", True)),
        subtitle="Finalize your side while the AI locks the opposing loadout",
    )
    left_rect = pygame.Rect(42, 102, 626, 732)
    right_rect = pygame.Rect(732, 102, 626, 732)
    draw_beveled_panel(surf, left_rect, title="Player 1 • You" if player_team_num == 1 else "Player 1 • AI Rival")
    draw_beveled_panel(surf, right_rect, title="Player 2 • You" if player_team_num == 2 else "Player 2 • AI Rival")
    field_buttons = []
    for team_num, panel_rect in ((1, left_rect), (2, right_rect)):
        members = setup_state[f"team{team_num}"]
        for index, member in enumerate(members):
            row_rect = pygame.Rect(panel_rect.x + 20, panel_rect.y + 58 + index * 216, panel_rect.width - 40, 190)
            editable = team_num == player_team_num
            field_buttons.extend([(rect, team_num, index, field) for rect, field in draw_loadout_member_editor(surf, row_rect, mouse_pos, member, selected=editable)] if editable else [])
    confirm_btn = pygame.Rect(WIDTH // 2 - 190, HEIGHT - 62, 380, 40)
    draw_primary_button(surf, confirm_btn, mouse_pos, "Confirm Bout Loadouts")
    btns["back"] = btns.pop("left")
    btns["fields"] = field_buttons
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
    draw_secondary_button(surf, prev_rect, mouse_pos, "Prev", active=False)
    draw_secondary_button(surf, next_rect, mouse_pos, "Next", active=False)
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
