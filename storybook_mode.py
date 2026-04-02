from __future__ import annotations

import copy
import random

import pygame

from campaign_save import save_campaign
from quests_ai_bout import choose_bout_pick
from quests_ai_loadout import solve_team_loadout
from quests_ai_quest import choose_quest_party
from quests_ruleset_data import ARTIFACTS, ARTIFACTS_BY_ID
from quests_sandbox import (
    build_battle_from_setup,
    create_setup_from_team_ids,
    cycle_member_weapon,
    set_member_artifact,
    set_member_class,
    set_member_skill,
    set_member_slot,
    setup_is_ready,
)
from storybook_battle import StoryBattleController, StoryLanBattleController
from storybook_content import BOUT_MODES, COSMETIC_CATEGORIES, STORY_QUESTS, catalog_entries, draft_offer, shop_items_for_tab, shop_tab_note
from storybook_lan import StoryLanSession, deserialize_setup_state, friend_host_available, serialize_member, serialize_setup_state
from storybook_progression import ARTIFACT_PURCHASE_EXP, BOUT_WIN_EXP, BOUT_WIN_GOLD, QUEST_WIN_EXP, award_exp, quest_win_gold
from storybook_ranked import (
    ai_difficulty_for_glory,
    effective_matchmaking_rating,
    ensure_storybook_glory,
    find_ai_match_profile,
    log_quest_ai_match,
    pressure_label,
    protected_rank_name,
    rank_name,
    target_team_score_for_glory,
    update_glory_after_match,
)
import storybook_ui as sbui


ALL_ARTIFACT_IDS = {artifact.id for artifact in ARTIFACTS}


class StorybookMode:
    def __init__(self, profile):
        self.profile = profile
        self.rng = random.Random()

        self.route = "main_menu"
        self.previous_route = "main_menu"
        self.last_buttons = {}
        self.last_mouse_pos = (0, 0)

        self.player_note_lines = [
            "Inventory opens the owned artifact ledger.",
            "Friends stores manual name and IP entries for quicker LAN joins.",
            "Closet and Trophies stay visible in the profile shell, but they do not open dedicated screens yet.",
            "Glory drives visible rank while quest pressure changes the opponents you face.",
        ]
        self.inventory_focus_index = 0
        self.friend_selected_index = -1
        self.friend_edit_name = ""
        self.friend_edit_ip = ""
        self.friend_active_field = "name"
        self.friend_status_lines = [
            "Save a friend's name and host IP here.",
            "Click a saved friend to test whether their Fabled LAN host is reachable.",
        ]

        self.shops_tab = "Artifacts"
        self.shops_cosmetic_index = 0
        self.shop_item_scroll = 0
        self.shop_focus_kind = "item"
        self.shop_focus_value = None
        self.shop_message = ""
        self.shop_owned_items: set[str] = set()
        self.shop_owned_cosmetics: set[str] = set()

        self.quest_index = 0
        self.quest_opponent_mode = "ai"
        self.quest_offer_ids: list[str] = []
        self.quest_focus_id: str | None = None
        self.quest_selected_ids: list[str] = []
        self.quest_draft_detail_scroll = 0
        self.quest_setup_state: dict | None = None
        self.quest_loadout_index = 0
        self.quest_loadout_detail_scroll = 0
        self.quest_loadout_summary_scroll = 0
        self.loadout_drag: dict | None = None
        self.loadout_drag_pos = None
        self.quest_player_seat = 1
        self.quest_run_active = False
        self.quest_run_wins = 0
        self.quest_run_consecutive_losses = 0
        self.quest_run_opponent_glories: list[int] = []
        self.quest_player_team: list[dict] | None = None
        self.quest_runs = {
            "ai": self._empty_quest_run_state(),
            "lan": self._empty_quest_run_state(),
        }
        self.quest_remote_team: list[dict] | None = None
        self.quest_remote_glory = ensure_storybook_glory(getattr(self.profile, "ranked_rating", 500), getattr(self.profile, "ranked_games_played", 0))
        self.quest_local_ready = False
        self.quest_remote_ready = False
        self.story_quest_best = 0

        self.bout_mode_index = 0
        self.bout_opponent_mode = "ai"
        self.bout_ready_1 = False
        self.bout_ready_2 = True
        self.bout_pool_ids: list[str] = []
        self.bout_focus_id: str | None = None
        self.bout_draft_detail_scroll = 0
        self.bout_team1_ids: list[str] = []
        self.bout_team2_ids: list[str] = []
        self.bout_current_player = 1
        self.bout_player_seat = 1
        self.bout_ai_seat = 2
        self.bout_setup_state: dict | None = None
        self.bout_loadout_index = 0
        self.bout_loadout_detail_scroll = 0
        self.bout_loadout_summary_scroll = 0
        self.bout_remote_glory = ensure_storybook_glory(getattr(self.profile, "ranked_rating", 500), getattr(self.profile, "ranked_games_played", 0))
        self.bout_local_ready = False
        self.bout_remote_ready = False
        self.story_bout_wins = 0
        self.story_bout_losses = 0

        self.catalog_section_index = 0
        self.catalog_entry_index = 0
        self.catalog_scroll = 0

        self.battle_controller = None
        self.current_battle_setup = None
        self.current_battle_human_team = 1
        self.current_battle_ai_difficulties = {2: "hard"}
        self.current_battle_second_picker = 0
        self.current_battle_player_name = "You"
        self.current_battle_enemy_name = "AI Rival"
        self.current_battle_result_kind = "quest"
        self.current_battle_opponent_glory = ensure_storybook_glory(getattr(self.profile, "ranked_rating", 500), getattr(self.profile, "ranked_games_played", 0))

        self.result_kind = "quest"
        self.result_lines: list[str] = []
        self.result_winner = ""
        self.result_victory = False

        self.lan_session = StoryLanSession()
        self.lan_context = "quest"
        self.lan_status_lines = [
            "Choose Host or Join.",
            "Host shows your local IP.",
            "Join requires the host IP address.",
        ]

        self._normalize_profile()
        if self._friends():
            self.friend_selected_index = 0
            self._load_selected_friend_into_editor()
        self._reset_shop_focus()

    @staticmethod
    def _empty_quest_run_state():
        return {
            "active": False,
            "wins": 0,
            "losses": 0,
            "opponent_glories": [],
            "team": None,
            "party_id": None,
            "match_count": 0,
        }

    def _normalize_profile(self):
        if getattr(self.profile, "gold", 0) <= 0 and getattr(self.profile, "player_exp", 0) <= 0:
            self.profile.gold = 1200
        self.profile.ranked_rating = ensure_storybook_glory(
            getattr(self.profile, "ranked_rating", 500),
            getattr(self.profile, "ranked_games_played", 0),
        )
        self.profile.storybook_rank_label = protected_rank_name(
            self.profile.ranked_rating,
            getattr(self.profile, "storybook_rank_label", None),
        )
        self.profile.unlocked_artifacts = {
            artifact_id for artifact_id in getattr(self.profile, "unlocked_artifacts", set()) if artifact_id in ARTIFACTS_BY_ID
        }
        if not hasattr(self.profile, "storybook_friends"):
            self.profile.storybook_friends = []
        if not hasattr(self.profile, "storybook_cosmetic_unlocks"):
            self.profile.storybook_cosmetic_unlocks = set()
        self.shop_owned_cosmetics = set(getattr(self.profile, "storybook_cosmetic_unlocks", set()))
        self._sync_friend_selection()

    def _persist_profile(self):
        self.profile.storybook_rank_label = protected_rank_name(
            self.profile.ranked_rating,
            getattr(self.profile, "storybook_rank_label", None),
        )
        self.profile.storybook_cosmetic_unlocks = set(self.shop_owned_cosmetics)
        save_campaign(self.profile)

    def _friends(self) -> list[dict]:
        return list(getattr(self.profile, "storybook_friends", []))

    def _sync_friend_selection(self):
        friends = self._friends()
        if not friends:
            self.friend_selected_index = -1
            return
        if self.friend_selected_index >= len(friends):
            self.friend_selected_index = len(friends) - 1
        elif self.friend_selected_index < -1:
            self.friend_selected_index = -1

    def _new_friend_entry(self):
        self.friend_selected_index = -1
        self.friend_edit_name = ""
        self.friend_edit_ip = ""
        self.friend_active_field = "name"
        self.friend_status_lines = [
            "New entry ready.",
            "Type a friend's name and host IP, then save it to the ledger.",
        ]

    def _load_selected_friend_into_editor(self):
        self._sync_friend_selection()
        friends = self._friends()
        if self.friend_selected_index < 0 or self.friend_selected_index >= len(friends):
            return
        entry = friends[self.friend_selected_index]
        self.friend_edit_name = entry["name"]
        self.friend_edit_ip = entry["ip"]
        self.friend_active_field = "name"

    def _save_friend_entry(self):
        name = self.friend_edit_name.strip()[:32]
        ip = self.friend_edit_ip.strip()[:64]
        if not name or not ip:
            self.friend_status_lines = [
                "Both fields are required.",
                "Each friend only stores a display name and a host IP address.",
            ]
            return
        friends = self._friends()
        existing_index = next(
            (index for index, entry in enumerate(friends) if entry["name"].lower() == name.lower() and entry["ip"] == ip),
            None,
        )
        payload = {"name": name, "ip": ip}
        if existing_index is not None and existing_index != self.friend_selected_index:
            self.friend_selected_index = existing_index
            self._load_selected_friend_into_editor()
            self.friend_status_lines = [
                f"{name} is already stored with that host IP.",
                "The existing ledger entry has been reselected instead of creating a duplicate.",
            ]
            return
        if self.friend_selected_index >= 0 and self.friend_selected_index < len(friends):
            friends[self.friend_selected_index] = payload
            self.friend_status_lines = [
                f"Updated {name}.",
                "Clicking their name will try to preload the LAN join field whenever that host is reachable.",
            ]
        elif existing_index is None:
            friends.append(payload)
            self.friend_selected_index = len(friends) - 1
            self.friend_status_lines = [
                f"Saved {name}.",
                "The friend ledger only stores this name and IP address.",
            ]
        else:
            self.friend_selected_index = existing_index
            self.friend_status_lines = [
                f"{name} is already in the ledger.",
                "That saved entry has been reselected in the list.",
            ]
        self.profile.storybook_friends = friends
        self._persist_profile()
        self._load_selected_friend_into_editor()

    def _remove_friend_entry(self):
        friends = self._friends()
        if self.friend_selected_index < 0 or self.friend_selected_index >= len(friends):
            self.friend_status_lines = [
                "Select a saved friend first.",
                "Then use Remove Friend to delete that ledger entry.",
            ]
            return
        removed = friends.pop(self.friend_selected_index)
        self.profile.storybook_friends = friends
        self._persist_profile()
        if friends:
            self.friend_selected_index = min(self.friend_selected_index, len(friends) - 1)
            self._load_selected_friend_into_editor()
            self.friend_status_lines = [
                f"Removed {removed['name']}.",
                "Their host IP is no longer stored in the friend ledger.",
            ]
        else:
            self._new_friend_entry()
            self.friend_status_lines = [
                f"Removed {removed['name']}.",
                "The friend ledger is empty again. Add a new host entry from the editor.",
            ]

    def _attempt_friend_autofill(self, index: int):
        friends = self._friends()
        if index < 0 or index >= len(friends):
            return
        self.friend_selected_index = index
        self._load_selected_friend_into_editor()
        entry = friends[index]
        if friend_host_available(entry["ip"]):
            self.lan_session.join_ip = entry["ip"]
            self.friend_status_lines = [
                f"{entry['name']} is reachable on the Fabled LAN port.",
                f"LAN join IP preloaded: {entry['ip']}",
            ]
        else:
            self.friend_status_lines = [
                f"{entry['name']} did not answer on the Fabled LAN port just now.",
                "The entry is still selected and editable, but the join field was left unchanged.",
            ]

    def _owned_artifacts(self):
        ids = sorted(self._owned_artifact_ids())
        return [ARTIFACTS_BY_ID[artifact_id] for artifact_id in ids]

    def _owned_artifact_ids(self) -> set[str]:
        return {artifact_id for artifact_id in getattr(self.profile, "unlocked_artifacts", set()) if artifact_id in ARTIFACTS_BY_ID}

    def _owned_shop_item_keys(self) -> set[str]:
        return set(self._owned_artifact_ids())

    def _loadout_artifact_ids(self, *, allow_all: bool = False) -> set[str]:
        if allow_all:
            return set(ALL_ARTIFACT_IDS)
        return set(self._owned_artifact_ids())

    def _apply_exp_gain(self, gained_exp: int) -> list[str]:
        if gained_exp <= 0:
            return []
        award = award_exp(getattr(self.profile, "player_exp", 0), gained_exp)
        self.profile.player_exp = award.total_exp
        if award.level_up_gold > 0:
            self.profile.gold += award.level_up_gold
        if not award.levels_gained:
            return []
        if len(award.levels_gained) == 1:
            return [f"Reached Level {award.new_level}: +{award.level_up_gold} Gold"]
        return [f"Reached Level {award.new_level}: +{award.level_up_gold} Gold across {len(award.levels_gained)} level-ups"]

    def _glory_text(self) -> str:
        glory = ensure_storybook_glory(self.profile.ranked_rating, getattr(self.profile, "ranked_games_played", 0))
        return f"{getattr(self.profile, 'storybook_rank_label', protected_rank_name(glory, None))} | {glory} Glory"

    def _quest_run_state(self, mode: str | None = None) -> dict:
        return self.quest_runs[mode or self.quest_opponent_mode]

    @staticmethod
    def _quest_party_lines_for(team: list[dict] | None) -> list[str]:
        if not team:
            return ["No current streak"]
        return [member["adventurer_id"].replace("_", " ").title() for member in team[:3]]

    def _reset_quest_run_state(self, mode: str):
        self.quest_runs[mode] = self._empty_quest_run_state()
        if mode == self.quest_opponent_mode:
            self.quest_run_active = False
            self.quest_run_wins = 0
            self.quest_run_consecutive_losses = 0
            self.quest_run_opponent_glories = []
            self.quest_player_team = None

    def _quest_avg_opponent_glory(self, mode: str | None = None) -> int:
        state = self._quest_run_state(mode)
        if not state["opponent_glories"]:
            return 0
        return round(sum(state["opponent_glories"]) / len(state["opponent_glories"]))

    def _quest_mode_summaries(self) -> list[dict]:
        summaries = []
        for mode in ("ai", "lan"):
            state = self._quest_run_state(mode)
            summaries.append(
                {
                    "mode": mode,
                    "label": "Vs AI" if mode == "ai" else "LAN",
                    "active": bool(state["active"]),
                    "streak_text": f"{state['wins']} Wins" if state["active"] else "No active streak",
                    "loss_text": f"{state['losses']} / 3" if state["active"] else "0 / 3",
                    "pressure": pressure_label(
                        self.profile.ranked_rating,
                        state["wins"],
                        state["losses"],
                        self._quest_avg_opponent_glory(mode),
                    ),
                    "party_lines": self._quest_party_lines_for(state["team"] if state["active"] else None),
                }
            )
        return summaries

    def _quest_loadout_waiting_note(self) -> str:
        if self.quest_opponent_mode != "lan":
            return ""
        if self.quest_local_ready and not self.quest_remote_ready:
            return "Loadout locked. Waiting for the remote commander to finish."
        if self.quest_remote_ready and not self.quest_local_ready:
            return "The remote commander is ready. Lock your own loadout to begin."
        return "Both commanders draft from the same six, then confirm loadouts independently."

    def _bout_loadout_waiting_note(self) -> str:
        if self.bout_opponent_mode != "lan":
            return ""
        if self.bout_local_ready and not self.bout_remote_ready:
            return "Loadout locked. Waiting for the remote commander to finish."
        if self.bout_remote_ready and not self.bout_local_ready:
            return "The remote commander is ready. Lock your own loadout to begin."
        return "Both duelists confirm their own formation and loadouts before the bout starts."

    def _clear_loadout_drag(self):
        self.loadout_drag = None
        self.loadout_drag_pos = None

    def _current_loadout_setup(self, route: str | None = None):
        current_route = route or self.route
        if current_route == "quest_loadout":
            return self.quest_setup_state
        if current_route == "bout_loadout":
            return self.bout_setup_state
        return None

    def _current_loadout_team_num(self, route: str | None = None) -> int:
        current_route = route or self.route
        return self.quest_player_seat if current_route == "quest_loadout" else self.bout_player_seat

    def _current_loadout_index(self, route: str | None = None) -> int:
        current_route = route or self.route
        return self.quest_loadout_index if current_route == "quest_loadout" else self.bout_loadout_index

    def _set_current_loadout_index(self, index: int, route: str | None = None):
        current_route = route or self.route
        setup_state = self._current_loadout_setup(current_route)
        if setup_state is None:
            return
        team_num = self._current_loadout_team_num(current_route)
        total = len(setup_state.get(f"team{team_num}", []))
        clamped = max(0, min(index, max(0, total - 1)))
        if current_route == "quest_loadout":
            self.quest_loadout_index = clamped
            self.quest_loadout_detail_scroll = 0
        elif current_route == "bout_loadout":
            self.bout_loadout_index = clamped
            self.bout_loadout_detail_scroll = 0

    def _current_loadout_detail_scroll(self, route: str | None = None) -> int:
        current_route = route or self.route
        return self.quest_loadout_detail_scroll if current_route == "quest_loadout" else self.bout_loadout_detail_scroll

    def _current_loadout_summary_scroll(self, route: str | None = None) -> int:
        current_route = route or self.route
        return self.quest_loadout_summary_scroll if current_route == "quest_loadout" else self.bout_loadout_summary_scroll

    def _set_current_loadout_detail_scroll(self, value: int, route: str | None = None):
        current_route = route or self.route
        if current_route == "quest_loadout":
            self.quest_loadout_detail_scroll = max(0, value)
        elif current_route == "bout_loadout":
            self.bout_loadout_detail_scroll = max(0, value)

    def _set_current_loadout_summary_scroll(self, value: int, route: str | None = None):
        current_route = route or self.route
        if current_route == "quest_loadout":
            self.quest_loadout_summary_scroll = max(0, value)
        elif current_route == "bout_loadout":
            self.bout_loadout_summary_scroll = max(0, value)

    def _loadout_locked(self, route: str | None = None) -> bool:
        current_route = route or self.route
        if current_route == "quest_loadout":
            return self.quest_local_ready
        if current_route == "bout_loadout":
            return self.bout_local_ready
        return True

    def _loadout_drop_slot(self, pos):
        btns = self.last_buttons or {}
        for rect, slot in btns.get("formation_slots", []):
            if rect.collidepoint(pos):
                return slot
        for rect, _index, slot in btns.get("formation_members", []):
            if rect.collidepoint(pos):
                return slot
        return None

    def _bout_lobby_status(self) -> list[str]:
        if self.bout_opponent_mode == "ai":
            return ["AI seat order is rolled when the draft begins."]
        if self.lan_session.connected:
            return ["LAN link established.", "Host controls draft start once both sides are ready."]
        return ["Connect over LAN first, then both sides can ready up here."]

    def _sync_bout_ready_flags(self):
        if self.bout_opponent_mode == "ai":
            self.bout_ready_2 = True
            return
        if self.bout_player_seat == 1:
            self.bout_ready_1 = self.bout_local_ready
            self.bout_ready_2 = self.bout_remote_ready
        else:
            self.bout_ready_1 = self.bout_remote_ready
            self.bout_ready_2 = self.bout_local_ready

    def _lan_title(self) -> str:
        return "Quest LAN Setup" if self.lan_context == "quest" else "Bout LAN Setup"

    def _lan_mode_label(self) -> str:
        return "Quest Duel" if self.lan_context == "quest" else "Bout Match"

    def draw(self, surf, mouse_pos):
        self.last_mouse_pos = mouse_pos
        self._normalize_profile()
        self._poll_nonbattle_lan()
        if self.route == "battle" and hasattr(self.battle_controller, "poll_network"):
            self.battle_controller.poll_network()
            self._check_battle_results()

        if self.route == "main_menu":
            self.last_buttons = sbui.draw_main_menu(surf, mouse_pos, self.profile)
        elif self.route == "player_menu":
            self.last_buttons = sbui.draw_player_menu(surf, mouse_pos, self.profile, self.player_note_lines)
        elif self.route == "inventory":
            self.last_buttons = sbui.draw_inventory_screen(surf, mouse_pos, self._owned_artifacts(), self.inventory_focus_index)
        elif self.route == "friends":
            self.last_buttons = sbui.draw_friends_menu(
                surf,
                mouse_pos,
                self._friends(),
                self.friend_selected_index,
                self.friend_edit_name,
                self.friend_edit_ip,
                self.friend_active_field,
                self.friend_status_lines,
                self.lan_session.join_ip,
            )
        elif self.route == "guild_hall":
            self.last_buttons = sbui.draw_guild_hall(surf, mouse_pos)
        elif self.route == "shops":
            self.last_buttons = sbui.draw_shops(
                surf,
                mouse_pos,
                self.shops_tab,
                self.shops_cosmetic_index,
                self.shop_item_scroll,
                self.profile,
                self.shop_focus_kind,
                self.shop_focus_value,
                self.shop_message,
                self._owned_shop_item_keys(),
                self.shop_owned_cosmetics,
            )
        elif self.route == "quests_menu":
            self.last_buttons = sbui.draw_quests_menu(surf, mouse_pos, self._quest_mode_summaries())
        elif self.route == "quest_draft":
            self.last_buttons = sbui.draw_quest_draft(
                surf,
                mouse_pos,
                self.quest_offer_ids,
                self.quest_focus_id,
                self.quest_selected_ids,
                detail_scroll=self.quest_draft_detail_scroll,
            )
        elif self.route == "quest_loadout":
            self.last_buttons = sbui.draw_quest_loadout(
                surf,
                mouse_pos,
                self.quest_setup_state,
                self.quest_loadout_index,
                player_team_num=self.quest_player_seat,
                waiting_note=self._quest_loadout_waiting_note(),
                drag_state=self.loadout_drag if self.route == "quest_loadout" else None,
                detail_scroll=self.quest_loadout_detail_scroll,
                summary_scroll=self.quest_loadout_summary_scroll,
            )
        elif self.route == "bouts_menu":
            self.last_buttons = sbui.draw_bouts_menu(surf, mouse_pos)
        elif self.route == "bout_lobby":
            self._sync_bout_ready_flags()
            self.last_buttons = sbui.draw_bout_lobby(
                surf,
                mouse_pos,
                self.bout_ready_1,
                self.bout_ready_2,
                player_seat=self.bout_player_seat,
                opponent_mode=self.bout_opponent_mode,
                status_lines=self._bout_lobby_status(),
            )
        elif self.route == "bout_draft":
            self.last_buttons = sbui.draw_bout_draft(
                surf,
                mouse_pos,
                self.bout_pool_ids,
                self.bout_focus_id,
                self.bout_team1_ids,
                self.bout_team2_ids,
                self.bout_current_player,
                player_seat=self.bout_player_seat,
                detail_scroll=self.bout_draft_detail_scroll,
            )
        elif self.route == "bout_loadout":
            self.last_buttons = sbui.draw_bout_loadout(
                surf,
                mouse_pos,
                self.bout_setup_state,
                self.bout_loadout_index,
                player_team_num=self.bout_player_seat,
                waiting_note=self._bout_loadout_waiting_note(),
                drag_state=self.loadout_drag if self.route == "bout_loadout" else None,
                detail_scroll=self.bout_loadout_detail_scroll,
                summary_scroll=self.bout_loadout_summary_scroll,
            )
        elif self.route == "catalog":
            self.last_buttons = sbui.draw_catalog(surf, mouse_pos, self.catalog_section_index, self.catalog_entry_index, self.catalog_scroll)
        elif self.route == "lan_setup":
            self.last_buttons = sbui.draw_lan_setup(
                surf,
                mouse_pos,
                self._lan_title(),
                self._lan_mode_label(),
                self.lan_session.connection_mode,
                self.lan_session.join_ip,
                self.lan_session.local_ip(),
                self.lan_session.connected,
                self.lan_status_lines,
            )
        elif self.route == "settings":
            self.last_buttons = sbui.draw_story_settings(
                surf,
                mouse_pos,
                getattr(self.profile, "tutorials_enabled", True),
                getattr(self.profile, "fast_resolution", False),
            )
        elif self.route == "battle":
            self.last_buttons = sbui.draw_battle_hud(surf, mouse_pos, self.battle_controller)
        elif self.route == "results":
            self.last_buttons = sbui.draw_results(
                surf,
                mouse_pos,
                self.result_kind,
                self.result_victory,
                self.result_winner,
                self.result_lines,
            )
        else:
            self.route = "main_menu"
            self.last_buttons = sbui.draw_main_menu(surf, mouse_pos, self.profile)

    def handle_click(self, pos):
        route = self.route
        btns = self.last_buttons or {}
        if self._hit(btns.get("quit"), pos):
            self._persist_profile()
            return "quit"
        if self._hit(btns.get("settings"), pos) and route != "settings":
            self.previous_route = route
            self.route = "settings"
            return None

        if route == "main_menu":
            if self._hit(btns.get("player"), pos):
                self.route = "player_menu"
            elif self._hit(btns.get("guild_hall"), pos):
                self.route = "guild_hall"
            elif self._hit(btns.get("shops"), pos):
                self._open_shops()
            return None

        if route == "player_menu":
            if self._hit(btns.get("back"), pos):
                self.route = "main_menu"
            elif self._hit(btns.get("inventory"), pos):
                self.route = "inventory"
            elif self._hit(btns.get("friends"), pos):
                self._sync_friend_selection()
                if self.friend_selected_index >= 0:
                    self._load_selected_friend_into_editor()
                elif not self.friend_edit_name and not self.friend_edit_ip:
                    self._new_friend_entry()
                self.route = "friends"
            return None

        if route == "inventory":
            if self._hit(btns.get("back"), pos):
                self.route = "player_menu"
                return None
            for rect, index in btns.get("entries", []):
                if rect.collidepoint(pos):
                    self.inventory_focus_index = index
                    return None
            return None

        if route == "friends":
            if self._hit(btns.get("back"), pos):
                self.route = "player_menu"
                return None
            if self._hit(btns.get("name_box"), pos):
                self.friend_active_field = "name"
                return None
            if self._hit(btns.get("ip_box"), pos):
                self.friend_active_field = "ip"
                return None
            if self._hit(btns.get("save"), pos):
                self._save_friend_entry()
                return None
            if self._hit(btns.get("new"), pos):
                self._new_friend_entry()
                return None
            if self._hit(btns.get("remove"), pos):
                self._remove_friend_entry()
                return None
            for rect, index in btns.get("entries", []):
                if rect.collidepoint(pos):
                    self._attempt_friend_autofill(index)
                    return None
            return None

        if route == "guild_hall":
            if self._hit(btns.get("back"), pos):
                self.route = "main_menu"
            elif self._hit(btns.get("quests"), pos):
                self.route = "quests_menu"
            elif self._hit(btns.get("bouts"), pos):
                self.route = "bouts_menu"
            elif self._hit(btns.get("catalog"), pos):
                self.route = "catalog"
            return None

        if route == "shops":
            if self._hit(btns.get("back"), pos):
                self.route = "main_menu"
                return None
            for rect, tab_name in btns.get("tabs", []):
                if rect.collidepoint(pos):
                    self.shops_tab = tab_name
                    self._reset_shop_focus()
                    return None
            if self._hit(btns.get("shop_prev"), pos):
                self.shop_item_scroll = max(0, self.shop_item_scroll - 6)
                return None
            if self._hit(btns.get("shop_next"), pos):
                self.shop_item_scroll = min(btns.get("shop_scroll_max", 0), self.shop_item_scroll + 6)
                return None
            for rect, index in btns.get("cosmetics", []):
                if rect.collidepoint(pos):
                    self.shops_cosmetic_index = index
                    self.shop_focus_kind = "cosmetic"
                    self.shop_focus_value = COSMETIC_CATEGORIES[index]
                    self.shop_message = "Cosmetic bundles are commander-only unlocks."
                    return None
            for rect, item_id in btns.get("items", []):
                if rect.collidepoint(pos):
                    self.shop_focus_kind = "item"
                    self.shop_focus_value = item_id
                    self.shop_message = "Artifact purchases use Gold and unlock immediately on your profile."
                    return None
            if self._hit(btns.get("embassy"), pos):
                self.shop_focus_kind = "embassy"
                self.shop_focus_value = "Embassy Charter"
                self.shop_message = "Embassy is informational here while artifact stock remains the only battle wares for sale."
                return None
            if self._hit(btns.get("buy"), pos):
                self._purchase_shop_focus()
            return None

        if route == "quests_menu":
            if self._hit(btns.get("back"), pos):
                self.route = "guild_hall"
                return None
            if self._hit(btns.get("vs_ai"), pos):
                self.quest_opponent_mode = "ai"
                state = self._quest_run_state("ai")
                if state["active"] and state["team"] is not None:
                    self._launch_next_quest_battle()
                else:
                    self._start_quest_draft()
                return None
            if self._hit(btns.get("vs_lan"), pos):
                self.quest_opponent_mode = "lan"
                self._open_lan_setup("quest")
                return None
            return None

        if route == "quest_draft":
            if self._hit(btns.get("back"), pos):
                self.route = "quests_menu"
            elif self._hit(btns.get("pick"), pos):
                self._pick_quest_focus()
            elif self._hit(btns.get("continue"), pos) and len(self.quest_selected_ids) == 3:
                self._enter_quest_loadout()
            else:
                for rect, adventurer_id in btns.get("cards", []):
                    if rect.collidepoint(pos):
                        self.quest_focus_id = adventurer_id
                        self.quest_draft_detail_scroll = 0
                        return None
            return None

        if route == "quest_loadout":
            if self._hit(btns.get("back"), pos):
                self._clear_loadout_drag()
                self.route = "quest_draft"
                return None
            if self._hit(btns.get("confirm"), pos):
                self._clear_loadout_drag()
                if self.quest_opponent_mode == "ai":
                    self._start_quest_run()
                else:
                    self._confirm_lan_quest_loadout()
                return None
            if self.quest_local_ready:
                return None
            for rect, index, _slot in btns.get("formation_members", []):
                if rect.collidepoint(pos):
                    self.quest_loadout_index = index
                    return None
            if self._hit(btns.get("weapon_prev"), pos) or self._hit(btns.get("weapon_next"), pos):
                cycle_member_weapon(self.quest_setup_state, self.quest_player_seat, self.quest_loadout_index)
                return None
            for rect, class_name in btns.get("classes", []):
                if rect.collidepoint(pos):
                    set_member_class(self.quest_setup_state, self.quest_player_seat, self.quest_loadout_index, class_name)
                    return None
            for rect, skill_id in btns.get("skills", []):
                if rect.collidepoint(pos):
                    set_member_skill(self.quest_setup_state, self.quest_player_seat, self.quest_loadout_index, skill_id)
                    return None
            for rect, artifact_id, locked in btns.get("artifacts", []):
                if rect.collidepoint(pos) and not locked:
                    set_member_artifact(self.quest_setup_state, self.quest_player_seat, self.quest_loadout_index, artifact_id)
                    return None
            return None

        if route == "bouts_menu":
            if self._hit(btns.get("back"), pos):
                self.route = "guild_hall"
                return None
            if self._hit(btns.get("vs_ai"), pos):
                self.bout_opponent_mode = "ai"
                self.bout_ready_1 = False
                self.bout_ready_2 = True
                self.bout_player_seat = 1
                self.route = "bout_lobby"
                return None
            if self._hit(btns.get("vs_lan"), pos):
                self.bout_opponent_mode = "lan"
                self._open_lan_setup("bout")
                return None
            return None

        if route == "bout_lobby":
            if self._hit(btns.get("back"), pos):
                self.route = "bouts_menu"
                return None
            if self.bout_opponent_mode == "ai":
                if self._hit(btns.get("ready1"), pos):
                    self.bout_ready_1 = not self.bout_ready_1
                elif self._hit(btns.get("begin"), pos) and self.bout_ready_1 and self.bout_ready_2:
                    self._start_bout_draft()
                return None
            local_ready_btn = btns.get("ready1") if self.bout_player_seat == 1 else btns.get("ready2")
            if self._hit(local_ready_btn, pos):
                self.bout_local_ready = not self.bout_local_ready
                self._sync_bout_ready_flags()
                self.lan_session.send({"type": "bout_ready", "ready": self.bout_local_ready})
                return None
            if self.lan_session.is_host and self._hit(btns.get("begin"), pos) and self.bout_ready_1 and self.bout_ready_2:
                self._start_lan_bout_draft()
            return None

        if route == "bout_draft":
            if self._hit(btns.get("back"), pos):
                self.route = "bout_lobby"
                return None
            if self._hit(btns.get("draft"), pos):
                self._draft_bout_focus()
                return None
            for rect, adventurer_id in btns.get("pool", []):
                if rect.collidepoint(pos):
                    self.bout_focus_id = adventurer_id
                    self.bout_draft_detail_scroll = 0
                    return None
            return None

        if route == "bout_loadout":
            if self._hit(btns.get("back"), pos):
                self._clear_loadout_drag()
                self.route = "bout_draft"
                return None
            if self._hit(btns.get("confirm"), pos):
                self._clear_loadout_drag()
                if self.bout_opponent_mode == "ai":
                    self._start_bout_battle()
                else:
                    self._confirm_lan_bout_loadout()
                return None
            if self.bout_local_ready:
                return None
            for rect, index, _slot in btns.get("formation_members", []):
                if rect.collidepoint(pos):
                    self.bout_loadout_index = index
                    return None
            if self._hit(btns.get("weapon_prev"), pos) or self._hit(btns.get("weapon_next"), pos):
                cycle_member_weapon(self.bout_setup_state, self.bout_player_seat, self.bout_loadout_index)
                return None
            for rect, class_name in btns.get("classes", []):
                if rect.collidepoint(pos):
                    set_member_class(self.bout_setup_state, self.bout_player_seat, self.bout_loadout_index, class_name)
                    return None
            for rect, skill_id in btns.get("skills", []):
                if rect.collidepoint(pos):
                    set_member_skill(self.bout_setup_state, self.bout_player_seat, self.bout_loadout_index, skill_id)
                    return None
            for rect, artifact_id, locked in btns.get("artifacts", []):
                if rect.collidepoint(pos) and not locked:
                    set_member_artifact(self.bout_setup_state, self.bout_player_seat, self.bout_loadout_index, artifact_id)
                    return None
            return None

        if route == "catalog":
            if self._hit(btns.get("back"), pos):
                self.route = "guild_hall"
                return None
            if self._hit(btns.get("prev_page"), pos):
                self.catalog_scroll = max(0, self.catalog_scroll - 10)
                return None
            if self._hit(btns.get("next_page"), pos):
                section_name = ["Adventurers", "Class Skills", "Artifacts"][self.catalog_section_index]
                total = len(catalog_entries(section_name))
                self.catalog_scroll = min(max(0, total - 10), self.catalog_scroll + 10)
                return None
            for rect, index in btns.get("sections", []):
                if rect.collidepoint(pos):
                    self.catalog_section_index = index
                    self.catalog_entry_index = 0
                    self.catalog_scroll = 0
                    return None
            for rect, index in btns.get("entries", []):
                if rect.collidepoint(pos):
                    self.catalog_entry_index = index
                    return None
            return None

        if route == "lan_setup":
            if self._hit(btns.get("back"), pos):
                self._close_lan()
                self.route = "quests_menu" if self.lan_context == "quest" else "bouts_menu"
                return None
            if self._hit(btns.get("host"), pos):
                self.lan_session.host_match()
                self.lan_status_lines = [
                    "Hosting on the displayed local IP.",
                    "Have the second player join from another copy of the game.",
                ]
                return None
            if self._hit(btns.get("join"), pos):
                self.lan_session.join_match()
                self.lan_status_lines = [
                    "Enter the host IP address, then connect.",
                    "The host will control when the draft opens.",
                ]
                return None
            if self._hit(btns.get("connect"), pos):
                self.lan_session.connect(self.lan_session.join_ip)
                self.lan_status_lines = [f"Connecting to {self.lan_session.join_ip}..."]
                return None
            if self._hit(btns.get("begin"), pos) and self.lan_session.connected:
                self._begin_lan_context()
                return None
            return None

        if route == "settings":
            if self._hit(btns.get("back"), pos):
                self.route = self.previous_route
            elif self._hit(btns.get("tutorials"), pos):
                self.profile.tutorials_enabled = not getattr(self.profile, "tutorials_enabled", True)
                self._persist_profile()
            elif self._hit(btns.get("fast"), pos):
                self.profile.fast_resolution = not getattr(self.profile, "fast_resolution", False)
                self._persist_profile()
            return None

        if route == "battle":
            return self._handle_battle_click(pos)

        if route == "results":
            if self._hit(btns.get("continue"), pos):
                self._continue_from_results()
            elif self._hit(btns.get("rematch"), pos):
                self._restart_current_battle()
            elif self._hit(btns.get("return"), pos) or self._hit(btns.get("back"), pos):
                self._return_from_results()
            return None
        return None

    def handle_keydown(self, e):
        if self.route == "friends":
            if e.key == pygame.K_TAB:
                self.friend_active_field = "ip" if self.friend_active_field == "name" else "name"
                return None
            if e.key == pygame.K_BACKSPACE:
                if self.friend_active_field == "ip":
                    self.friend_edit_ip = self.friend_edit_ip[:-1]
                else:
                    self.friend_edit_name = self.friend_edit_name[:-1]
                return None
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._save_friend_entry()
                return None
            if e.unicode and e.unicode.isprintable():
                if self.friend_active_field == "ip":
                    if e.unicode in "0123456789.:-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ" and len(self.friend_edit_ip) < 64:
                        self.friend_edit_ip += e.unicode
                else:
                    if len(self.friend_edit_name) < 32:
                        self.friend_edit_name += e.unicode
                return None

        if self.route == "lan_setup":
            if e.key == pygame.K_BACKSPACE:
                self.lan_session.join_ip = self.lan_session.join_ip[:-1]
                return None
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.lan_session.connection_mode == "join" and not self.lan_session.connected:
                    self.lan_session.connect(self.lan_session.join_ip)
                    self.lan_status_lines = [f"Connecting to {self.lan_session.join_ip}..."]
                elif self.lan_session.connected:
                    self._begin_lan_context()
                return None
            if self.lan_session.connection_mode == "join":
                if e.unicode and (e.unicode.isdigit() or e.unicode == ".") and len(self.lan_session.join_ip) < 30:
                    self.lan_session.join_ip += e.unicode
                return None

        if e.key == pygame.K_ESCAPE:
            if self.route in {"player_menu", "shops", "settings"}:
                self.route = self.previous_route if self.route == "settings" else "main_menu"
            elif self.route in {"inventory", "friends"}:
                self.route = "player_menu"
            elif self.route in {"quests_menu", "bouts_menu", "catalog"}:
                self.route = "guild_hall"
            elif self.route == "guild_hall":
                self.route = "main_menu"
            elif self.route == "lan_setup":
                self._close_lan()
                self.route = "quests_menu" if self.lan_context == "quest" else "bouts_menu"
            elif self.route == "quest_draft":
                self.route = "quests_menu"
            elif self.route == "quest_loadout":
                self._clear_loadout_drag()
                self.route = "quest_draft"
            elif self.route == "bout_lobby":
                self.route = "bouts_menu"
            elif self.route == "bout_draft":
                self.route = "bout_lobby"
            elif self.route == "bout_loadout":
                self._clear_loadout_drag()
                self.route = "bout_draft"
            elif self.route == "battle" and self.battle_controller is not None:
                if self.battle_controller.phase in {"action_target", "bonus_target"}:
                    self.battle_controller.cancel_targeting()
                else:
                    self._abandon_battle()
            elif self.route == "results":
                self._return_from_results()
            return None

        if self.route == "battle" and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            if self.battle_controller is not None and self.battle_controller.can_resolve():
                self.battle_controller.resolve_current_phase()
                self._check_battle_results()
            return None

        if self.route == "quest_draft" and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if len(self.quest_selected_ids) == 3:
                self._enter_quest_loadout()
            else:
                self._pick_quest_focus()
            return None

        if self.route == "bout_draft" and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._draft_bout_focus()
            return None
        if self.route == "catalog":
            section_name = ["Adventurers", "Class Skills", "Artifacts"][self.catalog_section_index]
            total = len(catalog_entries(section_name))
            max_scroll = max(0, total - 10)
            if e.key == pygame.K_UP:
                self.catalog_scroll = max(0, self.catalog_scroll - 1)
                return None
            if e.key == pygame.K_DOWN:
                self.catalog_scroll = min(max_scroll, self.catalog_scroll + 1)
                return None
            if e.key == pygame.K_PAGEUP:
                self.catalog_scroll = max(0, self.catalog_scroll - 10)
                return None
            if e.key == pygame.K_PAGEDOWN:
                self.catalog_scroll = min(max_scroll, self.catalog_scroll + 10)
                return None
        return None

    def handle_mousewheel(self, event):
        if self.route == "quest_draft":
            btns = self.last_buttons or {}
            viewport = btns.get("detail_viewport")
            if viewport is not None and viewport.collidepoint(self.last_mouse_pos):
                max_scroll = btns.get("detail_scroll_max", 0)
                self.quest_draft_detail_scroll = max(0, min(max_scroll, self.quest_draft_detail_scroll - (event.y * 28)))
                return None
        if self.route == "bout_draft":
            btns = self.last_buttons or {}
            viewport = btns.get("detail_viewport")
            if viewport is not None and viewport.collidepoint(self.last_mouse_pos):
                max_scroll = btns.get("detail_scroll_max", 0)
                self.bout_draft_detail_scroll = max(0, min(max_scroll, self.bout_draft_detail_scroll - (event.y * 28)))
                return None
        if self.route in {"quest_loadout", "bout_loadout"}:
            mouse_pos = self.last_mouse_pos
            btns = self.last_buttons or {}
            detail_viewport = btns.get("detail_viewport")
            summary_viewport = btns.get("summary_viewport")
            if detail_viewport is not None and detail_viewport.collidepoint(mouse_pos):
                max_scroll = btns.get("detail_scroll_max", 0)
                self._set_current_loadout_detail_scroll(min(max_scroll, max(0, self._current_loadout_detail_scroll() - (event.y * 28))))
                return None
            if summary_viewport is not None and summary_viewport.collidepoint(mouse_pos):
                max_scroll = btns.get("summary_scroll_max", 0)
                self._set_current_loadout_summary_scroll(min(max_scroll, max(0, self._current_loadout_summary_scroll() - (event.y * 28))))
                return None
        if self.route == "catalog":
            section_name = ["Adventurers", "Class Skills", "Artifacts"][self.catalog_section_index]
            total = len(catalog_entries(section_name))
            max_scroll = max(0, total - 10)
            self.catalog_scroll = max(0, min(max_scroll, self.catalog_scroll - event.y))
            return None
        if self.route == "shops":
            items = shop_items_for_tab(self.shops_tab)
            max_scroll = max(0, len(items) - 6)
            if max_scroll > 0:
                self.shop_item_scroll = max(0, min(max_scroll, self.shop_item_scroll - (event.y * 2)))
            return None
        return None

    def handle_mouse_down(self, pos):
        if self.route not in {"quest_loadout", "bout_loadout"} or self._loadout_locked():
            return False
        for rect, member_index, slot in (self.last_buttons or {}).get("formation_members", []):
            if rect.collidepoint(pos):
                self._set_current_loadout_index(member_index)
                self.loadout_drag = {
                    "route": self.route,
                    "member_index": member_index,
                    "origin_slot": slot,
                    "hover_slot": slot,
                }
                self.loadout_drag_pos = pos
                return True
        return False

    def handle_mousemotion(self, pos, buttons):
        if self.loadout_drag is None or not buttons[0]:
            return False
        self.loadout_drag_pos = pos
        self.loadout_drag["hover_slot"] = self._loadout_drop_slot(pos)
        return True

    def handle_mouse_up(self, pos):
        if self.loadout_drag is None:
            return False
        drag = dict(self.loadout_drag)
        self._clear_loadout_drag()
        if drag.get("route") != self.route or self._loadout_locked():
            return True
        target_slot = self._loadout_drop_slot(pos)
        if target_slot is None:
            return True
        setup_state = self._current_loadout_setup()
        if setup_state is None:
            return True
        set_member_slot(setup_state, self._current_loadout_team_num(), drag["member_index"], target_slot)
        self._set_current_loadout_index(drag["member_index"])
        return True

    def _reset_shop_focus(self):
        items = shop_items_for_tab(self.shops_tab)
        self.shop_item_scroll = 0
        if items:
            self.shop_focus_kind = "item"
            self.shop_focus_value = items[0]["id"]
            self.shop_message = "Artifacts are the only battle wares sold here. Cosmetics remain on the left rail."
        else:
            self.shop_focus_kind = None
            self.shop_focus_value = None
            self.shop_message = shop_tab_note(self.shops_tab)

    def _open_shops(self):
        self._reset_shop_focus()
        self.route = "shops"

    def _purchase_shop_focus(self):
        if self.shop_focus_kind == "item":
            item = next((entry for entry in shop_items_for_tab(self.shops_tab) if entry["id"] == self.shop_focus_value), None)
            if item is None:
                self.shop_message = "No wares are highlighted right now."
                return
            key = item["id"]
            if key in self._owned_shop_item_keys():
                self.shop_message = f"{item['name']} is already in your collection."
                return
            if self.profile.gold < item["price"]:
                self.shop_message = f"You need {item['price'] - self.profile.gold} more Gold for {item['name']}."
                return
            self.profile.gold -= item["price"]
            if item.get("artifact_id"):
                self.profile.unlocked_artifacts.add(item["artifact_id"])
            else:
                self.shop_message = "Only artifact stock is purchasable in the current build."
                return
            level_lines = self._apply_exp_gain(ARTIFACT_PURCHASE_EXP)
            self.shop_message = f"Purchased {item['name']} for {item['price']} Gold and earned +{ARTIFACT_PURCHASE_EXP} EXP."
            if level_lines:
                self.shop_message = f"{self.shop_message} {level_lines[0]}"
            self._persist_profile()
            return

        if self.shop_focus_kind == "cosmetic":
            category = str(self.shop_focus_value or COSMETIC_CATEGORIES[self.shops_cosmetic_index])
            price = 120 + self.shops_cosmetic_index * 40
            if category in self.shop_owned_cosmetics:
                self.shop_message = f"{category} is already unlocked."
                return
            if self.profile.gold < price:
                self.shop_message = f"You need {price - self.profile.gold} more Gold for the {category} bundle."
                return
            self.profile.gold -= price
            self.shop_owned_cosmetics.add(category)
            self.shop_message = f"Unlocked the {category} bundle for {price} Gold."
            self._persist_profile()
            return

        if self.shop_focus_kind == "embassy":
            self.shop_message = "Embassy is informational here. Only artifacts and cosmetics are sold in this build."
            return

        self.shop_message = "Select an artifact or cosmetic bundle first."

    def _handle_battle_click(self, pos):
        btns = self.last_buttons or {}
        controller = self.battle_controller
        if controller is None:
            return None
        if self._hit(btns.get("back"), pos):
            self._abandon_battle()
            return None
        if self._hit(btns.get("resolve"), pos) and controller.can_resolve():
            controller.resolve_current_phase()
            self._check_battle_results()
            return None
        for rect, kind in btns.get("action_buttons", []):
            if rect.collidepoint(pos):
                controller.select_action(kind)
                return None
        for rect, effect_id in btns.get("spell_buttons", []):
            if rect.collidepoint(pos):
                controller.select_spell(effect_id)
                return None
        for rect, unit in btns.get("slot_buttons", []):
            if rect.collidepoint(pos):
                if unit in controller.legal_targets():
                    controller.select_target(unit)
                    self._check_battle_results()
                else:
                    controller.inspect(unit)
                return None
        return None

    def _check_battle_results(self):
        if self.battle_controller is None or self.battle_controller.phase != "result":
            return
        winner = self.battle_controller.battle.winner
        self.result_kind = self.battle_controller.results_kind
        self.result_victory = winner == self.current_battle_human_team
        self.result_winner = "You" if self.result_victory else self.battle_controller.winner_label()
        lines = list(self.battle_controller.result_lines())
        if self.result_kind == "quest":
            lines = self._finalize_quest_result(lines)
        else:
            lines = self._finalize_bout_result(lines)
        self.result_lines = lines
        self.route = "results"

    def _apply_glory_result(self, *, did_win: bool, run_wins_before: int) -> str:
        old_glory = self.profile.ranked_rating
        new_glory, delta = update_glory_after_match(
            self.profile.ranked_rating,
            self.current_battle_opponent_glory,
            did_win=did_win,
            matches_played=getattr(self.profile, "ranked_games_played", 0),
            run_wins_before_match=run_wins_before,
        )
        self.profile.ranked_rating = new_glory
        self.profile.ranked_games_played = getattr(self.profile, "ranked_games_played", 0) + 1
        self.profile.storybook_rank_label = protected_rank_name(
            new_glory,
            getattr(self.profile, "storybook_rank_label", None),
        )
        self._persist_profile()
        return f"Glory {old_glory} -> {new_glory} ({delta:+d})"

    def _finalize_quest_result(self, lines: list[str]) -> list[str]:
        run_state = self._quest_run_state()
        run_mode = self.quest_opponent_mode
        run_wins_before = run_state["wins"]
        run_losses_before = run_state["losses"]
        glory_before = self.profile.ranked_rating
        avg_opponent_glory_before = self._quest_avg_opponent_glory("ai")
        party_snapshot = copy.deepcopy(run_state["team"]) if run_state["team"] is not None else None
        if run_mode == "ai":
            glory_line = self._apply_glory_result(did_win=self.result_victory, run_wins_before=run_wins_before)
        else:
            glory_line = "Glory is only adjusted in Quest Vs AI."
        if self.result_victory:
            if self.current_battle_opponent_glory > 0 and run_mode == "ai":
                run_state["opponent_glories"].append(self.current_battle_opponent_glory)
            gold_reward = quest_win_gold(run_state["wins"])
            run_state["wins"] += 1
            run_state["losses"] = 0
            run_state["active"] = True
            run_state["match_count"] += 1
            self.quest_run_wins = run_state["wins"]
            self.quest_run_consecutive_losses = run_state["losses"]
            self.quest_run_opponent_glories = list(run_state["opponent_glories"])
            self.story_quest_best = max(self.story_quest_best, run_state["wins"])
            self.profile.gold += gold_reward
            level_lines = self._apply_exp_gain(QUEST_WIN_EXP)
            if run_mode == "ai":
                log_quest_ai_match(
                    {
                        "did_win": True,
                        "glory_before": glory_before,
                        "glory_after": self.profile.ranked_rating,
                        "opponent_glory": self.current_battle_opponent_glory,
                        "run_wins_before": run_wins_before,
                        "run_losses_before": run_losses_before,
                        "party_ids": [member["adventurer_id"] for member in party_snapshot or []],
                        "offer_ids": list(self.quest_offer_ids),
                        "avg_opponent_glory_before": avg_opponent_glory_before,
                    }
                )
            self._persist_profile()
            return [
                f"Quest streak: {run_state['wins']}",
                "Consecutive losses: 0/3",
                f"Rewards earned: +{gold_reward} Gold, +{QUEST_WIN_EXP} EXP",
                *level_lines,
                glory_line,
                *lines,
            ]

        run_state["losses"] += 1
        run_state["match_count"] += 1
        self.quest_run_wins = run_state["wins"]
        self.quest_run_consecutive_losses = run_state["losses"]
        self.quest_run_opponent_glories = list(run_state["opponent_glories"])
        summary = [
            f"Quest streak: {run_state['wins']}",
            f"Consecutive losses: {run_state['losses']}/3",
            glory_line,
        ]
        if run_mode == "ai":
            log_quest_ai_match(
                {
                    "did_win": False,
                    "glory_before": glory_before,
                    "glory_after": self.profile.ranked_rating,
                    "opponent_glory": self.current_battle_opponent_glory,
                    "run_wins_before": run_wins_before,
                    "run_losses_before": run_losses_before,
                    "party_ids": [member["adventurer_id"] for member in party_snapshot or []],
                    "offer_ids": list(self.quest_offer_ids),
                    "avg_opponent_glory_before": avg_opponent_glory_before,
                }
            )
        if run_state["losses"] >= 3:
            summary.append("This quest run is over.")
            self._reset_quest_run_state(run_mode)
        else:
            self.quest_run_active = True
            summary.append("This quest streak remains active from the quest menu.")
        self._persist_profile()
        return summary + lines

    def _finalize_bout_result(self, lines: list[str]) -> list[str]:
        mode = self._bout_mode()
        if self.result_victory:
            self.story_bout_wins += 1
            self.profile.gold += BOUT_WIN_GOLD
            level_lines = self._apply_exp_gain(BOUT_WIN_EXP)
        else:
            self.story_bout_losses += 1
            level_lines = []
        summary = [
            f"Mode: {mode['name']}",
            f"Bout record: {self.story_bout_wins}-{self.story_bout_losses}",
        ]
        if self.result_victory:
            summary.append(f"Rewards earned: +{BOUT_WIN_GOLD} Gold, +{BOUT_WIN_EXP} EXP")
            summary.extend(level_lines)
        self._persist_profile()
        seat_note = "You drafted second and carried the round-one bonus swap." if self.bout_player_seat == 2 else "Your opponent drafted second and opened with the bonus swap advantage."
        return summary + [seat_note] + lines

    def _continue_from_results(self):
        if self.result_kind == "quest":
            if self._quest_run_state().get("active") and self.quest_opponent_mode == "ai":
                self._launch_next_quest_battle()
            else:
                self.route = "quests_menu"
        else:
            if self.bout_opponent_mode == "lan":
                self.route = "bouts_menu"
            else:
                self.bout_ready_1 = False
                self.bout_ready_2 = True
                self.route = "bout_lobby"

    def _return_from_results(self):
        if self.result_kind == "quest":
            self.route = "quests_menu"
        else:
            self.route = "bouts_menu"

    def _restart_current_battle(self):
        if self.current_battle_setup is None:
            return
        self._start_battle(
            self.current_battle_setup,
            self.current_battle_result_kind,
            human_team_num=self.current_battle_human_team,
            ai_difficulties=self.current_battle_ai_difficulties,
            second_picker=self.current_battle_second_picker,
            player_name=self.current_battle_player_name,
            enemy_name=self.current_battle_enemy_name,
            opponent_glory=self.current_battle_opponent_glory,
            use_lan=isinstance(self.battle_controller, StoryLanBattleController),
        )

    def _abandon_battle(self):
        if self.current_battle_result_kind == "quest":
            self._quest_run_state()["active"] = False
            self.quest_run_active = False
            self.route = "quests_menu"
        elif self.current_battle_result_kind == "bout":
            self.route = "bouts_menu"
        else:
            self.route = "guild_hall"
        self.battle_controller = None

    def _member_dict_from_build(self, build) -> dict:
        return {
            "adventurer_id": build.adventurer_id,
            "slot": build.slot,
            "class_name": build.class_name,
            "class_skill_id": build.class_skill_id,
            "primary_weapon_id": build.primary_weapon_id,
            "artifact_id": build.artifact_id,
        }

    def _team_from_loadout(self, loadout) -> list[dict]:
        return [self._member_dict_from_build(member) for member in loadout.members]

    def _generate_quest_ai_choice(self, target_glory: int):
        difficulty = ai_difficulty_for_glory(target_glory)
        target_score = target_team_score_for_glory(target_glory)
        best_choice = None
        best_gap = None
        for _ in range(7):
            offer = draft_offer(6, seed=self.rng.randint(0, 999999))
            choice = choose_quest_party(offer, difficulty=difficulty, rng=self.rng)
            gap = abs(choice.loadout.score - target_score)
            if best_gap is None or gap < best_gap:
                best_choice = choice
                best_gap = gap
        return difficulty, best_choice

    def _start_quest_draft(self):
        self._clear_loadout_drag()
        self.quest_player_seat = 1
        self.quest_offer_ids = draft_offer(6)
        self.quest_focus_id = self.quest_offer_ids[0]
        self.quest_selected_ids = []
        self.quest_draft_detail_scroll = 0
        self.quest_setup_state = None
        self.quest_local_ready = False
        self.quest_remote_ready = False
        self.route = "quest_draft"

    def _pick_quest_focus(self):
        if self.quest_focus_id is None or self.quest_focus_id in self.quest_selected_ids:
            return
        if len(self.quest_selected_ids) >= 3:
            return
        self.quest_selected_ids.append(self.quest_focus_id)

    def _enter_quest_loadout(self):
        if len(self.quest_selected_ids) != 3:
            return
        filler_ids = [adventurer_id for adventurer_id in self.quest_offer_ids if adventurer_id not in self.quest_selected_ids][:3]
        player_artifacts = self._loadout_artifact_ids(allow_all=self.quest_opponent_mode == "lan")
        if self.quest_player_seat == 1:
            self.quest_setup_state = create_setup_from_team_ids(
                self.quest_selected_ids,
                filler_ids,
                team1_allowed_artifact_ids=player_artifacts,
            )
        else:
            self.quest_setup_state = create_setup_from_team_ids(
                filler_ids,
                self.quest_selected_ids,
                team2_allowed_artifact_ids=player_artifacts,
            )
        self.quest_loadout_index = 0
        self._clear_loadout_drag()
        self.quest_loadout_detail_scroll = 0
        self.quest_loadout_summary_scroll = 0
        self.quest_local_ready = False
        self.quest_remote_ready = False
        self.route = "quest_loadout"

    def _start_quest_run(self):
        if self.quest_setup_state is None or len(self.quest_setup_state["team1"]) != 3:
            return
        run_state = self._quest_run_state()
        run_state["team"] = copy.deepcopy(self.quest_setup_state[f"team{self.quest_player_seat}"])
        run_state["party_id"] = "|".join(member["adventurer_id"] for member in run_state["team"])
        run_state["match_count"] = 0
        run_state["active"] = True
        run_state["wins"] = 0
        run_state["losses"] = 0
        run_state["opponent_glories"] = []
        self.quest_player_team = copy.deepcopy(run_state["team"])
        self.quest_run_active = True
        self.quest_run_wins = 0
        self.quest_run_consecutive_losses = 0
        self.quest_run_opponent_glories = []
        self._launch_next_quest_battle()

    def _launch_next_quest_battle(self):
        run_state = self._quest_run_state("ai")
        if run_state["team"] is None:
            return
        match_profile = find_ai_match_profile(
            self.profile.ranked_rating,
            run_state["wins"],
            run_state["losses"],
            avg_opponent_glory=self._quest_avg_opponent_glory("ai"),
            rng=self.rng,
        )
        difficulty, enemy_choice = self._generate_quest_ai_choice(match_profile.glory)
        player_ids = [member["adventurer_id"] for member in run_state["team"]]
        setup_state = {
            "offer_ids": list(dict.fromkeys(player_ids + list(enemy_choice.team_ids))),
            "team1": copy.deepcopy(run_state["team"]),
            "team2": self._team_from_loadout(enemy_choice.loadout),
        }
        self.quest_player_team = copy.deepcopy(run_state["team"])
        self.quest_run_active = bool(run_state["active"])
        self.quest_run_wins = run_state["wins"]
        self.quest_run_consecutive_losses = run_state["losses"]
        self.quest_run_opponent_glories = list(run_state["opponent_glories"])
        self.quest_setup_state = setup_state
        self._start_battle(
            setup_state,
            "quest",
            human_team_num=1,
            ai_difficulties={2: difficulty},
            second_picker=0,
            player_name="You",
            enemy_name=f"{rank_name(match_profile.glory)} Rival",
            opponent_glory=match_profile.glory,
        )

    def _bout_mode(self) -> dict:
        return BOUT_MODES[self.bout_mode_index]

    def _bout_opponent_name(self) -> str:
        if self.bout_opponent_mode == "lan":
            return "LAN Rival"
        return {
            "local": "Practice Rival",
            "online": "Phantom Duelist",
            "friendly": "Guild Sparring Partner",
            "ranked": "Ranked Challenger",
        }.get(self._bout_mode()["id"], "AI Rival")

    def _bout_ai_difficulty(self) -> str:
        mode_id = self._bout_mode()["id"]
        if mode_id == "ranked":
            return ai_difficulty_for_glory(self.profile.ranked_rating)
        return {
            "local": "normal",
            "online": "hard",
            "friendly": "normal",
            "ranked": "ranked",
        }.get(mode_id, "hard")

    def _start_bout_draft(self):
        self.bout_pool_ids = draft_offer(9)
        self.bout_team1_ids = []
        self.bout_team2_ids = []
        self.bout_player_seat = self.rng.choice((1, 2))
        self.bout_ai_seat = 1 if self.bout_player_seat == 2 else 2
        self.bout_current_player = 1
        self.bout_focus_id = self.bout_pool_ids[0]
        self.bout_draft_detail_scroll = 0
        self.route = "bout_draft"
        self._run_ai_bout_turns()
        self._focus_next_available_bout_pick()

    def _available_bout_ids(self) -> list[str]:
        taken = set(self.bout_team1_ids) | set(self.bout_team2_ids)
        return [adventurer_id for adventurer_id in self.bout_pool_ids if adventurer_id not in taken]

    def _seat_ids(self, seat: int) -> list[str]:
        return self.bout_team1_ids if seat == 1 else self.bout_team2_ids

    def _draft_complete(self) -> bool:
        return len(self.bout_team1_ids) == 3 and len(self.bout_team2_ids) == 3

    def _record_bout_pick(self, seat: int, adventurer_id: str):
        if adventurer_id not in self._available_bout_ids():
            return
        if seat == 1:
            self.bout_team1_ids.append(adventurer_id)
            self.bout_current_player = 2
        else:
            self.bout_team2_ids.append(adventurer_id)
            self.bout_current_player = 1

    def _focus_next_available_bout_pick(self):
        available = self._available_bout_ids()
        if available:
            self.bout_focus_id = available[0]
            self.bout_draft_detail_scroll = 0

    def _run_ai_bout_turns(self):
        while self.bout_current_player == self.bout_ai_seat and not self._draft_complete():
            available_ids = self._available_bout_ids()
            if not available_ids:
                return
            ai_ids = self._seat_ids(self.bout_ai_seat)
            enemy_ids = self._seat_ids(self.bout_player_seat)
            choice = choose_bout_pick(
                available_ids,
                ai_ids,
                enemy_ids,
                seat=self.bout_ai_seat,
                difficulty=self._bout_ai_difficulty(),
                rng=self.rng,
            )
            self._record_bout_pick(self.bout_ai_seat, choice)
            self.bout_focus_id = choice
        if self._draft_complete():
            self._enter_bout_loadout()

    def _draft_bout_focus(self):
        if self.bout_opponent_mode == "lan":
            self._draft_lan_bout_focus()
            return
        if self.bout_current_player != self.bout_player_seat:
            return
        if self.bout_focus_id is None or self.bout_focus_id not in self._available_bout_ids():
            return
        self._record_bout_pick(self.bout_player_seat, self.bout_focus_id)
        if self._draft_complete():
            self._enter_bout_loadout()
            return
        self._run_ai_bout_turns()
        self._focus_next_available_bout_pick()

    def _enter_bout_loadout(self):
        if not self._draft_complete():
            return
        allow_all_artifacts = self.bout_opponent_mode == "lan"
        player_artifacts = self._loadout_artifact_ids(allow_all=allow_all_artifacts)
        self.bout_setup_state = create_setup_from_team_ids(
            self.bout_team1_ids,
            self.bout_team2_ids,
            team1_allowed_artifact_ids=player_artifacts if self.bout_player_seat == 1 else None,
            team2_allowed_artifact_ids=player_artifacts if self.bout_player_seat == 2 else None,
        )
        self.bout_local_ready = False
        self.bout_remote_ready = False
        self.bout_loadout_index = 0
        self._clear_loadout_drag()
        self.bout_loadout_detail_scroll = 0
        self.bout_loadout_summary_scroll = 0
        if self.bout_opponent_mode == "ai":
            player_ids = tuple(self._seat_ids(self.bout_player_seat))
            ai_ids = tuple(self._seat_ids(self.bout_ai_seat))
            ai_loadout = solve_team_loadout(
                ai_ids,
                enemy_ids=player_ids,
                mode="bout",
                seat=self.bout_ai_seat,
            )
            self.bout_setup_state[f"team{self.bout_ai_seat}"] = self._team_from_loadout(ai_loadout)
        self.route = "bout_loadout"

    def _start_bout_battle(self):
        if self.bout_setup_state is None or not setup_is_ready(self.bout_setup_state):
            return
        self._start_battle(
            self.bout_setup_state,
            "bout",
            human_team_num=self.bout_player_seat,
            ai_difficulties={self.bout_ai_seat: self._bout_ai_difficulty()},
            second_picker=2,
            player_name="You",
            enemy_name=self._bout_opponent_name(),
            opponent_glory=self.profile.ranked_rating,
        )

    def _start_battle(
        self,
        setup_state,
        result_kind,
        *,
        human_team_num: int,
        ai_difficulties: dict[int, str],
        second_picker: int,
        player_name: str,
        enemy_name: str,
        opponent_glory: int,
        use_lan: bool = False,
    ):
        if setup_state is None:
            return
        self.current_battle_setup = copy.deepcopy(setup_state)
        self.current_battle_human_team = human_team_num
        self.current_battle_ai_difficulties = dict(ai_difficulties)
        self.current_battle_second_picker = second_picker
        self.current_battle_player_name = player_name
        self.current_battle_enemy_name = enemy_name
        self.current_battle_result_kind = result_kind
        self.current_battle_opponent_glory = opponent_glory

        battle = build_battle_from_setup(self.current_battle_setup)
        if second_picker == 1:
            battle.team1.markers["bonus_swap_rounds"] = 1
            battle.team1.markers["bonus_swap_used"] = 0
        elif second_picker == 2:
            battle.team2.markers["bonus_swap_rounds"] = 1
            battle.team2.markers["bonus_swap_used"] = 0

        if human_team_num == 1:
            battle.team1.player_name = player_name
            battle.team2.player_name = enemy_name
        else:
            battle.team1.player_name = enemy_name
            battle.team2.player_name = player_name

        if use_lan:
            self.battle_controller = StoryLanBattleController(
                battle,
                result_kind,
                local_team_num=human_team_num,
                lan_session=self.lan_session,
                is_host=self.lan_session.is_host,
            )
        else:
            self.battle_controller = StoryBattleController(
                battle=battle,
                results_kind=result_kind,
                human_team_num=human_team_num,
                ai_difficulties=ai_difficulties,
            )
        self.route = "battle"

    def _open_lan_setup(self, context: str):
        self.lan_context = context
        self.lan_status_lines = [
            "Choose Host or Join.",
            "Host shows your local IP.",
            "Join requires the host IP address.",
        ]
        if self.lan_session.host is None and self.lan_session.client is None:
            self.lan_session.host_match()
        self.route = "lan_setup"

    def _close_lan(self):
        self.lan_session.reset()
        self.quest_local_ready = False
        self.quest_remote_ready = False
        self.bout_local_ready = False
        self.bout_remote_ready = False

    def _begin_lan_context(self):
        if self.lan_context == "quest":
            self.quest_player_seat = 1 if self.lan_session.is_host else 2
            if self.lan_session.is_host:
                self.quest_offer_ids = draft_offer(6)
                self.lan_session.send(
                    {
                        "type": "quest_start",
                        "offer_ids": self.quest_offer_ids,
                        "host_glory": self.profile.ranked_rating,
                    }
                )
                self.quest_focus_id = self.quest_offer_ids[0]
                self.quest_selected_ids = []
                self.route = "quest_draft"
        else:
            self.bout_player_seat = 1 if self.lan_session.is_host else 2
            self.bout_local_ready = False
            self.bout_remote_ready = False
            self._sync_bout_ready_flags()
            if self.lan_session.is_host:
                self.lan_session.send({"type": "bout_lobby", "host_glory": self.profile.ranked_rating})
            self.route = "bout_lobby"

    def _confirm_lan_quest_loadout(self):
        if self.quest_setup_state is None or not setup_is_ready(self.quest_setup_state):
            return
        self.quest_local_ready = True
        local_team = copy.deepcopy(self.quest_setup_state[f"team{self.quest_player_seat}"])
        run_state = self._quest_run_state("lan")
        run_state["team"] = copy.deepcopy(local_team)
        run_state["party_id"] = "|".join(member["adventurer_id"] for member in local_team)
        run_state["match_count"] = 0 if not run_state["active"] else run_state["match_count"]
        if not run_state["active"]:
            run_state["wins"] = 0
            run_state["losses"] = 0
            run_state["opponent_glories"] = []
            run_state["active"] = True
        if self.lan_session.is_host:
            self.quest_player_team = local_team
            if self.quest_remote_ready and self.quest_remote_team is not None:
                self._start_lan_quest_battle()
        else:
            self.lan_session.send(
                {
                    "type": "quest_loadout",
                    "members": [serialize_member(member) for member in local_team],
                    "client_glory": self.profile.ranked_rating,
                }
            )

    def _start_lan_quest_battle(self):
        if self.quest_player_team is None or self.quest_remote_team is None:
            return
        setup_state = {
            "offer_ids": list(dict.fromkeys(self.quest_offer_ids)),
            "team1": copy.deepcopy(self.quest_player_team),
            "team2": copy.deepcopy(self.quest_remote_team),
        }
        self.quest_setup_state = setup_state
        payload = serialize_setup_state(setup_state)
        payload["type"] = "quest_battle_setup"
        payload["host_glory"] = self.profile.ranked_rating
        self.lan_session.send(payload)
        self.quest_run_active = self._quest_run_state("lan")["active"]
        self._start_battle(
            setup_state,
            "quest",
            human_team_num=1,
            ai_difficulties={},
            second_picker=0,
            player_name="You",
            enemy_name="LAN Rival",
            opponent_glory=self.quest_remote_glory,
            use_lan=True,
        )

    def _start_lan_bout_draft(self):
        self.bout_pool_ids = draft_offer(9)
        self.bout_team1_ids = []
        self.bout_team2_ids = []
        self.bout_current_player = 1
        self.bout_focus_id = self.bout_pool_ids[0]
        self.lan_session.send({"type": "bout_start", "pool_ids": self.bout_pool_ids, "host_glory": self.profile.ranked_rating})
        self.route = "bout_draft"

    def _draft_lan_bout_focus(self):
        if self.bout_current_player != self.bout_player_seat:
            return
        if self.bout_focus_id is None or self.bout_focus_id not in self._available_bout_ids():
            return
        if self.lan_session.is_host:
            self._record_bout_pick(1, self.bout_focus_id)
            self.lan_session.send({"type": "bout_pick", "seat": 1, "adventurer_id": self.bout_focus_id})
            if self._draft_complete():
                self._enter_bout_loadout()
            else:
                self._focus_next_available_bout_pick()
            return
        self.lan_session.send({"type": "bout_pick_request", "adventurer_id": self.bout_focus_id})

    def _confirm_lan_bout_loadout(self):
        if self.bout_setup_state is None or not setup_is_ready(self.bout_setup_state):
            return
        self.bout_local_ready = True
        local_team = copy.deepcopy(self.bout_setup_state[f"team{self.bout_player_seat}"])
        self._sync_bout_ready_flags()
        if self.lan_session.is_host:
            self.bout_setup_state["team1"] = local_team
            if self.bout_remote_ready:
                self._start_lan_bout_battle()
        else:
            self.lan_session.send(
                {
                    "type": "bout_loadout",
                    "members": [serialize_member(member) for member in local_team],
                    "client_glory": self.profile.ranked_rating,
                }
            )

    def _start_lan_bout_battle(self):
        payload = serialize_setup_state(self.bout_setup_state)
        payload["type"] = "bout_battle_setup"
        payload["host_glory"] = self.profile.ranked_rating
        self.lan_session.send(payload)
        self._start_battle(
            self.bout_setup_state,
            "bout",
            human_team_num=1,
            ai_difficulties={},
            second_picker=2,
            player_name="You",
            enemy_name="LAN Rival",
            opponent_glory=self.bout_remote_glory,
            use_lan=True,
        )

    def _poll_nonbattle_lan(self):
        if self.route == "battle":
            return
        for message in self.lan_session.poll():
            message_type = message.get("type")
            if message_type == "_disconnect":
                self.lan_status_lines = ["The LAN link was lost.", "You can host again or reconnect from the join path."]
                self.quest_remote_ready = False
                self.bout_remote_ready = False
                self._sync_bout_ready_flags()
                continue
            if message_type == "quest_start":
                self.quest_player_seat = 2
                self.quest_offer_ids = list(message.get("offer_ids", []))
                self.quest_focus_id = self.quest_offer_ids[0] if self.quest_offer_ids else None
                self.quest_selected_ids = []
                self.route = "quest_draft"
                continue
            if message_type == "quest_loadout" and self.lan_session.is_host:
                self.quest_remote_team = [dict(member) for member in message.get("members", [])]
                self.quest_remote_glory = int(message.get("client_glory", self.profile.ranked_rating))
                self.quest_remote_ready = True
                if self.quest_local_ready and self.quest_player_team is not None:
                    self._start_lan_quest_battle()
                continue
            if message_type == "quest_battle_setup" and not self.lan_session.is_host:
                self.quest_setup_state = deserialize_setup_state(message)
                self._start_battle(
                    self.quest_setup_state,
                    "quest",
                    human_team_num=2,
                    ai_difficulties={},
                    second_picker=0,
                    player_name="You",
                    enemy_name="LAN Rival",
                    opponent_glory=int(message.get("host_glory", self.profile.ranked_rating)),
                    use_lan=True,
                )
                continue
            if message_type == "bout_lobby":
                self.bout_player_seat = 2
                self.route = "bout_lobby"
                self.bout_local_ready = False
                self.bout_remote_ready = False
                self._sync_bout_ready_flags()
                continue
            if message_type == "bout_ready":
                self.bout_remote_ready = bool(message.get("ready", False))
                self._sync_bout_ready_flags()
                continue
            if message_type == "bout_start":
                self.bout_pool_ids = list(message.get("pool_ids", []))
                self.bout_team1_ids = []
                self.bout_team2_ids = []
                self.bout_focus_id = self.bout_pool_ids[0] if self.bout_pool_ids else None
                self.bout_current_player = 1
                self.route = "bout_draft"
                continue
            if message_type == "bout_pick_request" and self.lan_session.is_host:
                adventurer_id = message.get("adventurer_id")
                if self.bout_current_player == 2 and adventurer_id in self._available_bout_ids():
                    self._record_bout_pick(2, adventurer_id)
                    self.lan_session.send({"type": "bout_pick", "seat": 2, "adventurer_id": adventurer_id})
                    if self._draft_complete():
                        self._enter_bout_loadout()
                    else:
                        self._focus_next_available_bout_pick()
                continue
            if message_type == "bout_pick":
                seat = int(message.get("seat", 0))
                adventurer_id = message.get("adventurer_id")
                if adventurer_id in self._available_bout_ids():
                    self._record_bout_pick(seat, adventurer_id)
                if self._draft_complete():
                    self._enter_bout_loadout()
                else:
                    self._focus_next_available_bout_pick()
                continue
            if message_type == "bout_loadout" and self.lan_session.is_host:
                self.bout_setup_state["team2"] = [dict(member) for member in message.get("members", [])]
                self.bout_remote_glory = int(message.get("client_glory", self.profile.ranked_rating))
                self.bout_remote_ready = True
                self._sync_bout_ready_flags()
                if self.bout_local_ready:
                    self._start_lan_bout_battle()
                continue
            if message_type == "bout_battle_setup" and not self.lan_session.is_host:
                self.bout_setup_state = deserialize_setup_state(message)
                self._start_battle(
                    self.bout_setup_state,
                    "bout",
                    human_team_num=2,
                    ai_difficulties={},
                    second_picker=2,
                    player_name="You",
                    enemy_name="LAN Rival",
                    opponent_glory=int(message.get("host_glory", self.profile.ranked_rating)),
                    use_lan=True,
                )

    @staticmethod
    def _hit(rect, pos):
        return rect is not None and rect.collidepoint(pos)
