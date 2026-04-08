from __future__ import annotations

import copy
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import campaign_save
import storybook_mode as storybook_mode_module
from campaign_save import load_campaign
from quests_ruleset_data import ADVENTURERS_BY_ID
from settings import HEIGHT, WIDTH
from storybook_content import MARKET_TABS, market_items_for_tab
from storybook_mode import StorybookMode


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "screen_image_gallery"


# Prevent the gallery run from mutating the real save file or probing LAN.
campaign_save.save_campaign = lambda _profile: None
storybook_mode_module.save_campaign = lambda _profile: None
storybook_mode_module.friend_host_available = lambda _ip: False


@dataclass(frozen=True)
class ScreenSpec:
    slug: str
    title: str
    builder_name: str


@dataclass(frozen=True)
class Interactable:
    key: str
    label: str
    rect_sig: tuple[int, int, int, int]
    pos: tuple[int, int]


SCREEN_SPECS = [
    ScreenSpec("main_menu", "Main Menu", "build_main_menu"),
    ScreenSpec("player_profile", "Player Profile", "build_player_menu"),
    ScreenSpec("friends", "Friends", "build_friends"),
    ScreenSpec("employee_config", "Employee Config", "build_employee_config"),
    ScreenSpec("quest_hub_idle", "Quest Hub Idle", "build_guild_hall_idle"),
    ScreenSpec("quest_hub_active", "Quest Hub Active", "build_guild_hall_active"),
    ScreenSpec("training_grounds", "Training Grounds", "build_training_grounds"),
    ScreenSpec("favorite_select", "Favorite Select", "build_favorite_select"),
    ScreenSpec("quest_party_reveal", "Quest Party Reveal", "build_quest_party_reveal"),
    ScreenSpec("quest_party_loadout", "Quest Party Loadout", "build_quest_party_loadout"),
    ScreenSpec("quest_encounter_select", "Quest Encounter Select", "build_quest_draft_encounter"),
    ScreenSpec("quest_loadout", "Quest Loadout", "build_quest_loadout"),
    ScreenSpec("quest_reward_choice", "Quest Reward Choice", "build_quest_reward_choice"),
    ScreenSpec("battle", "Battle", "build_battle"),
    ScreenSpec("results_quest", "Results Quest", "build_results_quest"),
    ScreenSpec("market", "Market", "build_market"),
    ScreenSpec("closet", "Closet", "build_closet"),
    ScreenSpec("codex", "Codex", "build_catalog"),
    ScreenSpec("armory", "Armory", "build_armory"),
    ScreenSpec("bout_mode_select", "Bout Mode Select", "build_bouts_menu"),
    ScreenSpec("bout_lobby", "Bout Lobby", "build_bout_lobby"),
    ScreenSpec("bout_draft_focused", "Bout Draft Focused", "build_bout_draft_focused"),
    ScreenSpec("bout_party_loadout_random", "Bout Party Loadout Random", "build_bout_party_loadout_random"),
    ScreenSpec("bout_loadout", "Bout Loadout", "build_bout_loadout"),
    ScreenSpec("bout_adapt", "Bout Adapt", "build_bout_adapt"),
    ScreenSpec("results_bout", "Results Bout", "build_results_bout"),
    ScreenSpec("lan_connect", "LAN Connect", "build_lan_setup"),
    ScreenSpec("settings", "Settings", "build_settings"),
    ScreenSpec("inventory", "Inventory", "build_inventory"),
]


def _slugify(text: str) -> str:
    out = []
    last_was_sep = False
    for char in text.lower():
        if char.isalnum():
            out.append(char)
            last_was_sep = False
        elif not last_was_sep:
            out.append("_")
            last_was_sep = True
    return "".join(out).strip("_") or "item"


def _rect_sig(rect: pygame.Rect) -> tuple[int, int, int, int]:
    return (rect.x, rect.y, rect.width, rect.height)


def _center(rect: pygame.Rect) -> tuple[int, int]:
    return (rect.centerx, rect.centery)


def _render(mode: StorybookMode, mouse_pos: tuple[int, int] = (-2000, -2000)) -> pygame.Surface:
    surf = pygame.Surface((WIDTH, HEIGHT))
    mode.draw(surf, mouse_pos)
    return surf


def _save_surface(surf: pygame.Surface, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(path))


def _profile_template():
    profile = copy.deepcopy(load_campaign())
    profile.gold = max(int(getattr(profile, "gold", 0)), 5000)
    profile.player_exp = max(int(getattr(profile, "player_exp", 0)), 1800)
    profile.reputation = max(int(getattr(profile, "reputation", 300)), 420)
    profile.rank = getattr(profile, "rank", "Knight")
    profile.storybook_quested_adventurers = set(ADVENTURERS_BY_ID.keys())
    profile.storybook_favorite_adventurer = getattr(profile, "storybook_favorite_adventurer", "little_jack")
    profile.storybook_training_favorite_adventurer = getattr(profile, "storybook_training_favorite_adventurer", "little_jack")
    profile.storybook_friends = [
        {"name": "Ari", "ip": "192.168.0.10"},
        {"name": "Beck", "ip": "192.168.0.22"},
        {"name": "Cy", "ip": "10.0.0.14"},
    ]
    owned_cosmetics = set(getattr(profile, "storybook_cosmetic_unlocks", set()))
    for tab_name in MARKET_TABS:
        for item in market_items_for_tab(tab_name)[:2]:
            owned_cosmetics.add(str(item["id"]))
    profile.storybook_cosmetic_unlocks = owned_cosmetics
    if MARKET_TABS:
        first_items = market_items_for_tab(MARKET_TABS[0])
        if first_items:
            profile.storybook_equipped_outfit = str(first_items[0]["id"])
    return profile


BASE_PROFILE = _profile_template()


def _make_mode() -> StorybookMode:
    mode = StorybookMode(copy.deepcopy(BASE_PROFILE))
    mode.rng.seed(7)
    mode.profile.storybook_quested_adventurers = set(ADVENTURERS_BY_ID.keys())
    mode.shop_owned_cosmetics = set(getattr(mode.profile, "storybook_cosmetic_unlocks", set()))
    return mode


def _build_ranked_run_base() -> StorybookMode:
    mode = _make_mode()
    mode._start_ranked_quest_from_favorite()
    mode._confirm_quest_party_reveal()
    return mode


def _build_ranked_encounter_base() -> StorybookMode:
    mode = _build_ranked_run_base()
    mode._prepare_next_quest_encounter(route_if_ready="quest_draft")
    return mode


def _build_ranked_loadout_base() -> StorybookMode:
    mode = _build_ranked_encounter_base()
    mode.quest_selected_ids = list(mode.quest_offer_ids[:3])
    mode.quest_focus_id = mode.quest_selected_ids[0] if mode.quest_selected_ids else None
    mode._enter_quest_loadout()
    return mode


def build_main_menu() -> StorybookMode:
    return _make_mode()


def build_player_menu() -> StorybookMode:
    mode = _make_mode()
    mode.previous_route = "main_menu"
    mode.route = "player_menu"
    return mode


def build_friends() -> StorybookMode:
    mode = _make_mode()
    mode.previous_route = "player_menu"
    mode.route = "friends"
    mode.friend_selected_index = 0
    mode._load_selected_friend_into_editor()
    return mode


def build_employee_config() -> StorybookMode:
    mode = _make_mode()
    mode.employee_focus = "assistant"
    mode.previous_route = "main_menu"
    mode.route = "employee_config"
    return mode


def build_guild_hall_idle() -> StorybookMode:
    mode = _make_mode()
    mode.route = "guild_hall"
    return mode


def build_guild_hall_active() -> StorybookMode:
    mode = _build_ranked_run_base()
    mode.route = "guild_hall"
    return mode


def build_training_grounds() -> StorybookMode:
    mode = _make_mode()
    mode.previous_route = "guild_hall"
    mode.route = "training_grounds"
    return mode


def build_favorite_select() -> StorybookMode:
    mode = _make_mode()
    mode.route = "player_menu"
    mode._open_favorite_select()
    return mode


def build_quest_party_reveal() -> StorybookMode:
    mode = _make_mode()
    mode._start_ranked_quest_from_favorite()
    return mode


def build_quest_party_loadout() -> StorybookMode:
    return _build_ranked_run_base()


def build_quest_draft_encounter() -> StorybookMode:
    return _build_ranked_encounter_base()


def build_quest_loadout() -> StorybookMode:
    return _build_ranked_loadout_base()


def build_quest_reward_choice() -> StorybookMode:
    mode = _build_ranked_run_base()
    mode.quest_reward_options = mode._build_quest_reward_options()
    mode.route = "quest_reward_choice"
    return mode


def build_battle() -> StorybookMode:
    mode = _build_ranked_loadout_base()
    mode._start_quest_encounter()
    return mode


def build_results_quest() -> StorybookMode:
    mode = _build_ranked_run_base()
    mode.result_kind = "quest"
    mode.result_victory = True
    mode.result_winner = "You"
    mode.result_lines = [
        "Quest win secured.",
        "Gold pool +100.",
        "Choose a reward to continue.",
    ]
    mode.route = "results"
    return mode


def build_market() -> StorybookMode:
    mode = _make_mode()
    mode._open_market()
    return mode


def build_closet() -> StorybookMode:
    mode = _make_mode()
    mode.route = "player_menu"
    mode._open_closet()
    return mode


def build_catalog() -> StorybookMode:
    mode = _make_mode()
    mode.previous_route = "guild_hall"
    mode.route = "catalog"
    return mode


def build_armory() -> StorybookMode:
    mode = _make_mode()
    mode.route = "guild_hall"
    mode._open_armory()
    return mode


def build_bouts_menu() -> StorybookMode:
    mode = _make_mode()
    mode.previous_route = "guild_hall"
    mode.route = "bouts_menu"
    return mode


def build_bout_lobby() -> StorybookMode:
    mode = _make_mode()
    mode.bout_opponent_mode = "lan"
    mode.bout_player_seat = 1
    mode.bout_local_ready = False
    mode.bout_remote_ready = True
    mode._sync_bout_ready_flags()
    mode.route = "bout_lobby"
    return mode


def build_bout_draft_focused() -> StorybookMode:
    mode = _make_mode()
    mode._start_bout_series("focused")
    return mode


def build_bout_party_loadout_random() -> StorybookMode:
    mode = _make_mode()
    mode._start_bout_series("random")
    return mode


def build_bout_loadout() -> StorybookMode:
    mode = _make_mode()
    all_ids = list(ADVENTURERS_BY_ID.keys())
    mode.bout_mode_index = 0
    mode.bout_opponent_mode = "ai"
    mode.bout_player_seat = 1
    mode.bout_ai_seat = 2
    mode.bout_pool_ids = all_ids[:9]
    mode.bout_team1_ids = all_ids[:3]
    mode.bout_team2_ids = all_ids[3:6]
    mode.bout_current_player = mode.bout_player_seat
    available = [adventurer_id for adventurer_id in mode.bout_pool_ids if adventurer_id not in set(mode.bout_team1_ids) | set(mode.bout_team2_ids)]
    mode.bout_focus_id = available[0] if available else mode.bout_pool_ids[0]
    mode._enter_bout_loadout()
    return mode


def build_bout_adapt() -> StorybookMode:
    mode = _make_mode()
    mode._start_bout_series("random")
    mode._start_bout_adapt()
    return mode


def build_results_bout() -> StorybookMode:
    mode = _make_mode()
    mode.result_kind = "bout"
    mode.result_victory = False
    mode.result_winner = "AI Rival"
    mode.result_lines = [
        "Series tied 1-1.",
        "Adapt before the next round.",
        "Rematch available.",
    ]
    mode.route = "results"
    return mode


def build_lan_setup() -> StorybookMode:
    mode = _make_mode()
    mode.previous_route = "training_grounds"
    mode.route = "lan_setup"
    mode.lan_context = "training"
    mode.lan_session.connection_mode = "join"
    mode.lan_session.join_ip = "192.168.0.10"
    mode.lan_status_lines = ["Connecting...", "Connected!", "Failed - retry?"]
    return mode


def build_settings() -> StorybookMode:
    mode = _make_mode()
    mode.previous_route = "main_menu"
    mode.route = "settings"
    return mode


def build_inventory() -> StorybookMode:
    mode = _make_mode()
    mode.previous_route = "player_menu"
    mode.route = "inventory"
    return mode


def _extract_interactables(btns: dict) -> list[Interactable]:
    items: list[Interactable] = []
    seen_rects: set[tuple[int, int, int, int]] = set()
    skip_keys = {
        "detail_viewport",
        "summary_viewport",
        "entries_viewport",
        "entry_page_size",
        "offer_page_size",
        "training_scroll_max",
        "market_scroll_max",
        "shop_scroll_max",
        "entry_scroll_max",
        "detail_scroll_max",
        "summary_scroll_max",
        "scroll_max",
        "offer_scroll_max",
        "adventurer_scroll_max",
    }
    for key, value in btns.items():
        if key in skip_keys or key.endswith("_max") or key.endswith("_viewport") or key.endswith("_page_size"):
            continue
        if isinstance(value, pygame.Rect):
            sig = _rect_sig(value)
            if sig in seen_rects:
                continue
            seen_rects.add(sig)
            items.append(Interactable(key=key, label=_slugify(key), rect_sig=sig, pos=_center(value)))
            continue
        if isinstance(value, list):
            for index, entry in enumerate(value):
                if not entry or not isinstance(entry, tuple) or not isinstance(entry[0], pygame.Rect):
                    continue
                if isinstance(entry[-1], bool) and entry[-1]:
                    continue
                rect = entry[0]
                sig = _rect_sig(rect)
                if sig in seen_rects:
                    continue
                seen_rects.add(sig)
                label = _slugify(f"{key}_{index}")
                items.append(Interactable(key=key, label=label, rect_sig=sig, pos=_center(rect)))
    return items


def _find_interactable_by_sig(mode: StorybookMode, rect_sig: tuple[int, int, int, int]) -> Interactable | None:
    _render(mode)
    for item in _extract_interactables(mode.last_buttons or {}):
        if item.rect_sig == rect_sig:
            return item
    return None


def _simulate_click(mode: StorybookMode, pos: tuple[int, int]) -> None:
    mode.handle_click(pos)


def _capture_screen(spec: ScreenSpec) -> dict:
    builder = globals()[spec.builder_name]
    screen_dir = OUTPUT_DIR / spec.slug
    screen_dir.mkdir(parents=True, exist_ok=True)

    mode = builder()
    base = _render(mode)
    _save_surface(base, screen_dir / "base.png")

    interactables = _extract_interactables(mode.last_buttons or {})
    manifest = {
        "title": spec.title,
        "route": mode.route,
        "builder": spec.builder_name,
        "interactables": [],
    }

    for item in interactables:
        hover_mode = builder()
        hover = _render(hover_mode, item.pos)
        hover_path = screen_dir / f"hover__{item.label}.png"
        _save_surface(hover, hover_path)

        click_mode = builder()
        resolved = _find_interactable_by_sig(click_mode, item.rect_sig)
        click_path = None
        after_route = click_mode.route
        click_error = None
        if resolved is not None:
            try:
                _render(click_mode)
                _simulate_click(click_mode, resolved.pos)
                after_route = click_mode.route
                clicked = _render(click_mode, resolved.pos)
                click_path = screen_dir / f"click__{item.label}__{_slugify(after_route)}.png"
                _save_surface(clicked, click_path)
            except Exception as exc:  # noqa: BLE001 - keep the export running
                click_error = f"{type(exc).__name__}: {exc}"

        manifest["interactables"].append(
            {
                "key": item.key,
                "label": item.label,
                "hover": hover_path.name,
                "click": click_path.name if click_path is not None else None,
                "after_route": after_route,
                "click_error": click_error,
            }
        )

    with (screen_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifests = []
    try:
        for spec in SCREEN_SPECS:
            manifests.append(_capture_screen(spec))
        with (OUTPUT_DIR / "index.json").open("w", encoding="utf-8") as handle:
            json.dump(manifests, handle, indent=2)
        total_images = len(list(OUTPUT_DIR.rglob("*.png")))
        print(f"Generated {len(SCREEN_SPECS)} screen folders and {total_images} PNG files in {OUTPUT_DIR}")
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
