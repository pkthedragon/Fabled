from __future__ import annotations

import copy
import random

import pygame

from campaign_save import save_campaign
from models import BoutRunState
from quests_ai_bout import choose_bout_pick
from quests_ai_loadout import solve_team_loadout
from quests_ai_quest import choose_quest_party
from quests_ai_tags import ADVENTURER_AI
from quests_ruleset_data import ADVENTURERS_BY_ID, ARTIFACTS, ARTIFACTS_BY_ID, CLASS_SKILLS
from quests_sandbox import (
    NO_CLASS_NAME,
    build_battle_from_setup,
    create_setup_from_team_ids,
    cycle_member_weapon,
    import_team_from_text,
    set_member_artifact,
    set_member_class,
    set_member_skill,
    set_member_slot,
    set_member_weapon,
    setup_is_ready,
)
from storybook_battle import StoryBattleController, StoryLanBattleController
from storybook_content import CATALOG_SECTIONS, BOUT_MODES, CLOSET_TABS, COSMETIC_CATEGORIES, STORY_QUESTS, catalog_entries, catalog_filter_definitions, draft_offer, shop_items_for_tab, shop_tab_note
from storybook_content import MARKET_TABS, market_items_for_tab, market_tab_note
from storybook_lan import StoryLanSession, deserialize_setup_state, friend_host_available, serialize_member, serialize_setup_state
from storybook_progression import award_exp
from storybook_ranked import (
    ai_difficulty_for_reputation,
    clamp_reputation,
    ensure_storybook_reputation,
    find_ai_match_profile,
    get_rank_from_reputation,
    rank_floor_for_reputation,
    log_quest_ai_match,
    pressure_label,
    rank_name,
    target_team_score_for_reputation,
    update_reputation_after_match,
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
            "Little Jack is always eligible as your quest favorite.",
            "Other favorites unlock after they have joined one of your quests outside the Training Grounds.",
            "Training Grounds uses a separate sandbox favorite and always opens the full roster.",
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
        self.market_tab = "Featured"
        self.market_item_scroll = 0
        self.market_focus_id: str | None = None
        self.market_message = ""
        self.closet_tab = "Outfits"
        self.closet_item_scroll = 0
        self.closet_focus_id: str | None = None
        self.favorite_select_scroll = 0
        self.favorite_select_focus_id: str | None = None
        self.training_roster_scroll = 0
        self.training_focus_id: str | None = None

        self.quest_index = 0
        self.quest_opponent_mode = "ai"
        self.quest_offer_ids: list[str] = []
        self.quest_focus_id: str | None = None
        self.quest_selected_ids: list[str] = []
        self.quest_draft_mode = "encounter"
        self.quest_draft_locked_id: str | None = None
        self.quest_enemy_party_ids: list[str] = []
        self.quest_enemy_selected_ids: list[str] = []
        self.quest_enemy_setup_members: list[dict] = []
        self.quest_draft_detail_scroll = 0
        self.quest_setup_state: dict | None = None
        self.quest_loadout_index = 0
        self.quest_loadout_detail_scroll = 0
        self.quest_loadout_summary_scroll = 0
        self.quest_party_loadout_state: dict | None = None
        self.quest_party_loadout_index = 0
        self.quest_party_loadout_detail_scroll = 0
        self.loadout_drag: dict | None = None
        self.loadout_drag_pos = None
        self.quest_player_seat = 1
        self.quest_run_active = False
        self.quest_run_wins = 0
        self.quest_run_losses = 0
        self.quest_run_current_win_streak = 0
        self.quest_run_current_loss_streak = 0
        self.quest_run_opponent_glories: list[int] = []
        self.quest_context = "ranked"
        self.quest_draft_offer_scroll = 0
        self.quest_team_import_open = False
        self.quest_team_import_text = ""
        self.quest_team_import_status_lines: list[str] = []
        self.quest_imported_party_members: list[dict] = []
        self.quest_imported_party_name = ""
        self.prepared_quest_id: str | None = None
        self.quest_player_team: list[dict] | None = None
        self.quest_reward_pending: bool = False
        self.quest_reward_options: list[dict] = []
        self.quest_runs = {
            "ai": self._empty_quest_run_state(),
            "lan": self._empty_quest_run_state(),
        }
        self.quest_remote_team: list[dict] | None = None
        self.quest_remote_glory = ensure_storybook_reputation(getattr(self.profile, "reputation", 300), getattr(self.profile, "ranked_games_played", 0))
        self.quest_local_ready = False
        self.quest_remote_ready = False
        self.story_quest_best = 0

        self.training_mode = "ai"
        self.guild_party_index = 0
        self.guild_party_adventurer_scroll = 0

        self.bout_run = BoutRunState()
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
        # Full 6-person parties for random/focused bouts (new flow)
        self.bout_player_full_party: list[str] = []
        self.bout_ai_full_party: list[str] = []
        self.bout_player_artifact_pool: list[str] = []
        self.bout_player_seat = 1
        self.bout_ai_seat = 2
        self.bout_setup_state: dict | None = None
        self.bout_loadout_index = 0
        self.bout_loadout_detail_scroll = 0
        self.bout_loadout_summary_scroll = 0
        self.bout_remote_glory = ensure_storybook_reputation(getattr(self.profile, "reputation", 300), getattr(self.profile, "ranked_games_played", 0))
        self.bout_local_ready = False
        self.bout_remote_ready = False
        self.story_bout_wins = 0
        self.story_bout_losses = 0

        self.catalog_section_index = 0
        self.catalog_entry_index = 0
        self.catalog_scroll = 0
        self.catalog_detail_scroll = 0
        self.catalog_filters = {
            section: {
                definition["key"]: definition["options"][0][0]
                for definition in catalog_filter_definitions(section)
            }
            for section in CATALOG_SECTIONS
        }

        self.battle_controller = None
        self.current_battle_setup = None
        self.current_battle_human_team = 1
        self.current_battle_ai_difficulties = {2: "hard"}
        self.current_battle_second_picker = 0
        self.current_battle_player_name = "You"
        self.current_battle_enemy_name = "AI Rival"
        self.current_battle_result_kind = "quest"
        self.current_battle_opponent_glory = ensure_storybook_reputation(getattr(self.profile, "reputation", 300), getattr(self.profile, "ranked_games_played", 0))

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
            "quest_id": None,
            "wins": 0,
            "losses": 0,
            "current_win_streak": 0,
            "current_loss_streak": 0,
            "opponent_glories": [],
            "opponent_reputations": [],
            "team": None,
            "party_id": None,
            "match_count": 0,
            "total_gold_earned": 0,
            "artifact_pool": [],
            "reputation_gain_total": 0,
            "gold_pool": 0,
        }

    def _normalize_profile(self):
        if getattr(self.profile, "gold", 0) <= 0 and getattr(self.profile, "player_exp", 0) <= 0:
            self.profile.gold = 1200
        self.profile.reputation = ensure_storybook_reputation(
            getattr(self.profile, "reputation", 300),
            getattr(self.profile, "ranked_games_played", 0),
        )
        self.profile.storybook_rank_label = get_rank_from_reputation(self.profile.reputation)
        self.profile.season_high_reputation = max(
            getattr(self.profile, "season_high_reputation", self.profile.reputation),
            self.profile.reputation,
        )
        self.profile.floor_reputation = rank_floor_for_reputation(self.profile.reputation)
        self.profile.storybook_adventurer_unlocks = {
            adventurer_id
            for adventurer_id in getattr(self.profile, "storybook_adventurer_unlocks", set())
            if adventurer_id in ADVENTURERS_BY_ID
        }
        if not hasattr(self.profile, "storybook_quested_adventurers"):
            self.profile.storybook_quested_adventurers = {"little_jack"}
        self.profile.storybook_quested_adventurers = {
            adventurer_id
            for adventurer_id in getattr(self.profile, "storybook_quested_adventurers", {"little_jack"})
            if adventurer_id in ADVENTURERS_BY_ID
        }
        self.profile.storybook_quested_adventurers.add("little_jack")
        if not hasattr(self.profile, "storybook_favorite_adventurer"):
            self.profile.storybook_favorite_adventurer = "little_jack"
        if self.profile.storybook_favorite_adventurer not in self.profile.storybook_quested_adventurers:
            self.profile.storybook_favorite_adventurer = "little_jack"
        if not hasattr(self.profile, "storybook_training_favorite_adventurer"):
            self.profile.storybook_training_favorite_adventurer = "little_jack"
        if self.profile.storybook_training_favorite_adventurer not in ADVENTURERS_BY_ID:
            self.profile.storybook_training_favorite_adventurer = "little_jack"
        if not hasattr(self.profile, "storybook_friends"):
            self.profile.storybook_friends = []
        if not hasattr(self.profile, "storybook_cosmetic_unlocks"):
            self.profile.storybook_cosmetic_unlocks = set()
        if not hasattr(self.profile, "storybook_equipped_outfit"):
            self.profile.storybook_equipped_outfit = ""
        if not hasattr(self.profile, "storybook_equipped_chair"):
            self.profile.storybook_equipped_chair = ""
        if not hasattr(self.profile, "storybook_equipped_emote"):
            self.profile.storybook_equipped_emote = ""
        if not hasattr(self.profile, "storybook_equipped_adventurer_skins"):
            self.profile.storybook_equipped_adventurer_skins = {}
        if not hasattr(self.profile, "saved_teams"):
            self.profile.saved_teams = []
        self.shop_owned_cosmetics = set(getattr(self.profile, "storybook_cosmetic_unlocks", set()))
        if self.training_focus_id not in ADVENTURERS_BY_ID:
            self.training_focus_id = self._training_favorite_adventurer_id()
        self._normalize_guild_parties()
        self._sync_friend_selection()

    def _favorite_pool_ids(self) -> list[str]:
        pool = {
            adventurer_id
            for adventurer_id in getattr(self.profile, "storybook_quested_adventurers", {"little_jack"})
            if adventurer_id in ADVENTURERS_BY_ID
        }
        pool.add("little_jack")
        return sorted(pool, key=lambda adventurer_id: ADVENTURERS_BY_ID[adventurer_id].name)

    def _favorite_adventurer_id(self) -> str:
        favorite = getattr(self.profile, "storybook_favorite_adventurer", "little_jack")
        if favorite not in self._favorite_pool_ids():
            return "little_jack"
        return favorite

    def _set_favorite_adventurer(self, adventurer_id: str):
        if adventurer_id not in self._favorite_pool_ids():
            return
        self.profile.storybook_favorite_adventurer = adventurer_id
        self._persist_profile()

    def _cycle_favorite_adventurer(self, direction: int):
        pool = self._favorite_pool_ids()
        if not pool:
            return
        current = self._favorite_adventurer_id()
        if current not in pool:
            self._set_favorite_adventurer(pool[0])
            return
        index = pool.index(current)
        self._set_favorite_adventurer(pool[(index + direction) % len(pool)])

    def _training_favorite_pool_ids(self) -> list[str]:
        return sorted(ADVENTURERS_BY_ID.keys(), key=lambda adventurer_id: ADVENTURERS_BY_ID[adventurer_id].name)

    def _training_favorite_adventurer_id(self) -> str:
        favorite = getattr(self.profile, "storybook_training_favorite_adventurer", "little_jack")
        if favorite not in ADVENTURERS_BY_ID:
            return "little_jack"
        return favorite

    def _set_training_favorite_adventurer(self, adventurer_id: str):
        if adventurer_id not in ADVENTURERS_BY_ID:
            return
        self.profile.storybook_training_favorite_adventurer = adventurer_id
        self._persist_profile()

    def _cycle_training_favorite_adventurer(self, direction: int):
        pool = self._training_favorite_pool_ids()
        if not pool:
            return
        current = self._training_favorite_adventurer_id()
        index = pool.index(current) if current in pool else 0
        self._set_training_favorite_adventurer(pool[(index + direction) % len(pool)])

    def _record_quested_adventurers(self, adventurer_ids: list[str] | set[str] | tuple[str, ...]):
        quested = {
            adventurer_id
            for adventurer_id in adventurer_ids
            if adventurer_id in ADVENTURERS_BY_ID
        }
        if not quested:
            return
        if not hasattr(self.profile, "storybook_quested_adventurers"):
            self.profile.storybook_quested_adventurers = {"little_jack"}
        self.profile.storybook_quested_adventurers.update(quested)
        self.profile.storybook_quested_adventurers.add("little_jack")

    def _market_items(self, tab_name: str | None = None) -> list[dict]:
        return market_items_for_tab(tab_name or self.market_tab)

    def _reset_market_focus(self):
        items = self._market_items()
        self.market_item_scroll = 0
        self.market_focus_id = items[0]["id"] if items else None
        self.market_message = market_tab_note(self.market_tab)

    def _open_market(self):
        self.previous_route = self.route
        self._reset_market_focus()
        self.route = "market"

    def _open_armory(self):
        self.previous_route = self.route
        self.shops_tab = "Artifacts"
        self._reset_shop_focus()
        self.route = "armory"

    def _closet_items(self, tab_name: str | None = None) -> list[dict]:
        target_tab = tab_name or self.closet_tab
        if target_tab not in CLOSET_TABS:
            return []
        return self._market_items(target_tab)

    def _reset_closet_focus(self):
        items = [item for item in self._closet_items() if item["id"] in self.shop_owned_cosmetics]
        self.closet_item_scroll = 0
        self.closet_focus_id = items[0]["id"] if items else None

    def _open_closet(self):
        self.previous_route = self.route
        if self.closet_tab not in CLOSET_TABS:
            self.closet_tab = CLOSET_TABS[0]
        self._reset_closet_focus()
        self.route = "closet"

    def _open_favorite_select(self):
        self.previous_route = self.route
        self.favorite_select_scroll = 0
        self.favorite_select_focus_id = self._favorite_adventurer_id()
        self.route = "favored_adventurer_select"

    @staticmethod
    def _market_slot_for(item: dict) -> str:
        return str(item.get("slot", ""))

    def _equipped_market_item_id(self, item: dict) -> str:
        slot = self._market_slot_for(item)
        if slot == "outfit":
            return getattr(self.profile, "storybook_equipped_outfit", "")
        if slot == "chair":
            return getattr(self.profile, "storybook_equipped_chair", "")
        if slot == "emote":
            return getattr(self.profile, "storybook_equipped_emote", "")
        if slot == "adventurer_skin":
            adventurer_id = str(item.get("adventurer_id", ""))
            return dict(getattr(self.profile, "storybook_equipped_adventurer_skins", {})).get(adventurer_id, "")
        return ""

    def _set_equipped_market_item(self, item: dict):
        item_id = str(item.get("id", ""))
        if not item_id or item_id not in self.shop_owned_cosmetics:
            return
        slot = self._market_slot_for(item)
        if slot == "outfit":
            self.profile.storybook_equipped_outfit = item_id
        elif slot == "chair":
            self.profile.storybook_equipped_chair = item_id
        elif slot == "emote":
            self.profile.storybook_equipped_emote = item_id
        elif slot == "adventurer_skin":
            adventurer_id = str(item.get("adventurer_id", ""))
            if adventurer_id:
                equipped = dict(getattr(self.profile, "storybook_equipped_adventurer_skins", {}))
                equipped[adventurer_id] = item_id
                self.profile.storybook_equipped_adventurer_skins = equipped
        self.market_message = f"Equipped {item['name']}."
        self._persist_profile()

    def _purchase_market_focus(self):
        item = next((entry for entry in self._market_items() if entry["id"] == self.market_focus_id), None)
        if item is None:
            self.market_message = "Select a market item first."
            return
        item_id = str(item["id"])
        if item_id in self.shop_owned_cosmetics:
            self._set_equipped_market_item(item)
            return
        price = int(item["price"])
        if self.profile.gold < price:
            self.market_message = f"You need {price - self.profile.gold} more Gold for {item['name']}."
            return
        self.profile.gold -= price
        self.shop_owned_cosmetics.add(item_id)
        self.profile.storybook_cosmetic_unlocks = set(self.shop_owned_cosmetics)
        self._set_equipped_market_item(item)
        self.market_message = f"Purchased {item['name']} for {price} Gold."
        self._persist_profile()

    def _set_training_focus(self, adventurer_id: str):
        if adventurer_id not in ADVENTURERS_BY_ID:
            return
        self.training_focus_id = adventurer_id
        self._set_training_favorite_adventurer(adventurer_id)

    def _catalog_section_name(self) -> str:
        if not CATALOG_SECTIONS:
            return "Adventurers"
        self.catalog_section_index = max(0, min(self.catalog_section_index, len(CATALOG_SECTIONS) - 1))
        return CATALOG_SECTIONS[self.catalog_section_index]

    def _catalog_filters_for_section(self, section_name: str | None = None) -> dict[str, str]:
        section_name = section_name or self._catalog_section_name()
        filters = dict(self.catalog_filters.get(section_name, {}))
        normalized: dict[str, str] = {}
        for definition in catalog_filter_definitions(section_name):
            options = [str(value) for value, _label in definition["options"]]
            current = str(filters.get(definition["key"], options[0]))
            normalized[definition["key"]] = current if current in options else options[0]
        self.catalog_filters[section_name] = normalized
        return normalized

    def _catalog_entries_for_section(self, section_name: str | None = None) -> list[dict]:
        section_name = section_name or self._catalog_section_name()
        return catalog_entries(
            section_name,
            self._catalog_filters_for_section(section_name),
            favorite_adventurer_id=self._favorite_adventurer_id(),
        )

    def _reset_catalog_navigation(self):
        self.catalog_entry_index = 0
        self.catalog_scroll = 0
        self.catalog_detail_scroll = 0

    def _cycle_catalog_filter(self, key: str, direction: int):
        section_name = self._catalog_section_name()
        filters = self._catalog_filters_for_section(section_name)
        for definition in catalog_filter_definitions(section_name):
            if definition["key"] != key:
                continue
            values = [str(value) for value, _label in definition["options"]]
            if not values:
                return
            current = filters.get(key, values[0])
            index = values.index(current) if current in values else 0
            filters[key] = values[(index + direction) % len(values)]
            self.catalog_filters[section_name] = filters
            self._reset_catalog_navigation()
            return

    def _persist_profile(self):
        self.profile.storybook_rank_label = get_rank_from_reputation(self.profile.reputation)
        self.profile.season_high_reputation = max(
            getattr(self.profile, "season_high_reputation", self.profile.reputation),
            self.profile.reputation,
        )
        self.profile.floor_reputation = rank_floor_for_reputation(self.profile.reputation)
        self.profile.storybook_cosmetic_unlocks = set(self.shop_owned_cosmetics)
        self.profile.storybook_adventurer_unlocks = {
            adventurer_id
            for adventurer_id in getattr(self.profile, "storybook_adventurer_unlocks", set())
            if adventurer_id in ADVENTURERS_BY_ID
        }
        self.profile.saved_teams = self._guild_parties_serialized()
        save_campaign(self.profile)

    def _friends(self) -> list[dict]:
        return list(getattr(self.profile, "storybook_friends", []))

    def _guild_parties(self) -> list[dict]:
        return list(getattr(self, "_storybook_guild_parties", []))

    def _guild_parties_serialized(self) -> list[dict]:
        return copy.deepcopy(self._guild_parties())

    def _normalize_guild_parties(self):
        normalized: list[dict] = []
        raw_parties = list(getattr(self.profile, "saved_teams", []))
        for index, raw in enumerate(raw_parties):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", "")).strip() or f"Party {index + 1}"
            raw_members = raw.get("members", [])
            if not isinstance(raw_members, list):
                continue
            members: list[dict] = []
            used_classes: set[str] = set()
            for entry in raw_members[:6]:
                if not isinstance(entry, dict):
                    continue
                adventurer_id = str(entry.get("adventurer_id", ""))
                if adventurer_id not in ADVENTURERS_BY_ID:
                    continue
                class_name = str(entry.get("class_name", ""))
                if class_name not in CLASS_SKILLS or class_name in used_classes:
                    class_name = next((cls for cls in CLASS_SKILLS if cls not in used_classes), "Fighter")
                used_classes.add(class_name)
                members.append({"adventurer_id": adventurer_id, "class_name": class_name})
            if len(members) >= 3:
                used_ids = {member["adventurer_id"] for member in members}
                while len(members) < 6:
                    next_class = next((cls for cls in CLASS_SKILLS if cls not in {m["class_name"] for m in members}), None)
                    next_adv = next((aid for aid in ADVENTURERS_BY_ID if aid not in used_ids), None)
                    if next_class is None or next_adv is None:
                        break
                    members.append({"adventurer_id": next_adv, "class_name": next_class})
                    used_ids.add(next_adv)
                normalized.append({"name": name, "members": members})
        if not normalized:
            starter_ids = [member for member in getattr(self.profile, "recruited", set()) if member in ADVENTURERS_BY_ID]
            if len(starter_ids) < 6:
                starter_ids = list(ADVENTURERS_BY_ID.keys())[:6]
            members = []
            for index, adventurer_id in enumerate(starter_ids[:6]):
                class_name = list(CLASS_SKILLS.keys())[index % len(CLASS_SKILLS)]
                members.append({"adventurer_id": adventurer_id, "class_name": class_name})
            normalized.append({"name": "Guild Party 1", "members": members})
        self._storybook_guild_parties = normalized
        self.guild_party_index = max(0, min(self.guild_party_index, len(normalized) - 1))

    def _guild_party_members(self, party_index: int | None = None) -> list[dict]:
        parties = self._guild_parties()
        if not parties:
            return []
        index = self.guild_party_index if party_index is None else party_index
        index = max(0, min(index, len(parties) - 1))
        return parties[index]["members"]

    def _add_guild_party(self):
        parties = self._guild_parties()
        new_index = len(parties) + 1
        starter_pool = [adventurer_id for adventurer_id in ADVENTURERS_BY_ID if adventurer_id not in {m["adventurer_id"] for p in parties for m in p["members"]}]
        if len(starter_pool) < 6:
            starter_pool = list(ADVENTURERS_BY_ID.keys())
        members = []
        for index, adventurer_id in enumerate(starter_pool[:6]):
            class_name = list(CLASS_SKILLS.keys())[index % len(CLASS_SKILLS)]
            members.append({"adventurer_id": adventurer_id, "class_name": class_name})
        parties.append({"name": f"Guild Party {new_index}", "members": members})
        self._storybook_guild_parties = parties
        self.guild_party_index = len(parties) - 1
        self._persist_profile()

    def _delete_guild_party(self):
        parties = self._guild_parties()
        if len(parties) <= 1:
            return
        parties.pop(self.guild_party_index)
        self._storybook_guild_parties = parties
        self.guild_party_index = max(0, min(self.guild_party_index, len(parties) - 1))
        self._persist_profile()

    def _cycle_party_member_class(self, member_index: int):
        members = self._guild_party_members()
        if not (0 <= member_index < len(members)):
            return
        used = {member["class_name"] for index, member in enumerate(members) if index != member_index}
        class_order = list(CLASS_SKILLS.keys())
        current = members[member_index]["class_name"]
        current_index = class_order.index(current) if current in class_order else 0
        for offset in range(1, len(class_order) + 1):
            candidate = class_order[(current_index + offset) % len(class_order)]
            if candidate not in used:
                members[member_index]["class_name"] = candidate
                self._persist_profile()
                return

    def _remove_party_member(self, member_index: int):
        members = self._guild_party_members()
        if not (0 <= member_index < len(members)):
            return
        if len(members) <= 3:
            return
        members.pop(member_index)
        self._persist_profile()

    def _add_party_member(self, adventurer_id: str):
        if adventurer_id not in ADVENTURERS_BY_ID:
            return
        members = self._guild_party_members()
        if len(members) >= 6:
            return
        if any(member["adventurer_id"] == adventurer_id for member in members):
            return
        used_classes = {member["class_name"] for member in members}
        class_name = next((cls for cls in CLASS_SKILLS if cls not in used_classes), None)
        if class_name is None:
            return
        members.append({"adventurer_id": adventurer_id, "class_name": class_name})
        self._persist_profile()

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
        return set(ALL_ARTIFACT_IDS)

    def _owned_shop_item_keys(self) -> set[str]:
        return set(self._owned_artifact_ids())

    def _loadout_artifact_ids(self, *, allow_all: bool = False) -> set[str]:
        if allow_all:
            return set(ALL_ARTIFACT_IDS)
        return set(self._owned_artifact_ids())

    def _default_party_loadout_member(self, adventurer_id: str) -> dict:
        adventurer = ADVENTURERS_BY_ID[adventurer_id]
        primary_weapon_id = adventurer.signature_weapons[0].id if adventurer.signature_weapons else None
        return {
            "adventurer_id": adventurer_id,
            "class_name": NO_CLASS_NAME,
            "class_skill_id": None,
            "primary_weapon_id": primary_weapon_id,
            "artifact_id": None,
        }

    def _normalize_quest_party_team(self, team: list[dict] | None) -> list[dict]:
        if not team:
            return []
        normalized: list[dict] = []
        used_classes: set[str] = set()
        used_artifacts: set[str] = set()
        used_adventurers: set[str] = set()
        for raw_member in list(team)[:6]:
            adventurer_id = raw_member.get("adventurer_id")
            if adventurer_id not in ADVENTURERS_BY_ID or adventurer_id in used_adventurers:
                continue
            used_adventurers.add(adventurer_id)
            member = self._default_party_loadout_member(adventurer_id)
            class_name = raw_member.get("class_name", NO_CLASS_NAME)
            if class_name not in CLASS_SKILLS or class_name in used_classes:
                class_name = NO_CLASS_NAME
            if class_name != NO_CLASS_NAME:
                used_classes.add(class_name)
            member["class_name"] = class_name
            if class_name != NO_CLASS_NAME:
                valid_skill_ids = {skill.id for skill in CLASS_SKILLS[class_name]}
                skill_id = raw_member.get("class_skill_id")
                member["class_skill_id"] = skill_id if skill_id in valid_skill_ids else CLASS_SKILLS[class_name][0].id
            weapon_ids = {weapon.id for weapon in ADVENTURERS_BY_ID[adventurer_id].signature_weapons}
            weapon_id = raw_member.get("primary_weapon_id")
            if weapon_id in weapon_ids:
                member["primary_weapon_id"] = weapon_id
            artifact_id = raw_member.get("artifact_id")
            if (
                artifact_id in ARTIFACTS_BY_ID
                and artifact_id not in used_artifacts
                and class_name != NO_CLASS_NAME
                and class_name in ARTIFACTS_BY_ID[artifact_id].attunement
            ):
                member["artifact_id"] = artifact_id
                used_artifacts.add(artifact_id)
            normalized.append(member)
        return normalized

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

    def _reputation_text(self) -> str:
        reputation = ensure_storybook_reputation(self.profile.reputation, getattr(self.profile, "ranked_games_played", 0))
        return f"{getattr(self.profile, 'storybook_rank_label', get_rank_from_reputation(reputation))} | {reputation} Reputation"

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
            self.quest_run_losses = 0
            self.quest_run_current_win_streak = 0
            self.quest_run_current_loss_streak = 0
            self.quest_run_opponent_glories = []
            self.quest_player_team = None
        if mode == "ai":
            self.profile.ranked_current_quest_id = None
            self.prepared_quest_id = None
            self.quest_offer_ids = []
            self.quest_enemy_party_ids = []
            self.quest_enemy_selected_ids = []
            self.quest_enemy_setup_members = []
            self.quest_selected_ids = []
            self.quest_draft_mode = "encounter"
            self.quest_draft_locked_id = None
            self.quest_setup_state = None
            self.quest_party_loadout_state = None

    def _forfeit_current_quest(self):
        run_state = self._quest_run_state("ai")
        if not run_state.get("active"):
            return
        # Forfeit Penalty: −10 Rep × losses remaining, added to quest's running total
        remaining_losses = max(0, 3 - int(run_state.get("losses", 0)))
        forfeit_rep_penalty = -(remaining_losses * 10)
        run_state["reputation_gain_total"] = run_state.get("reputation_gain_total", 0) + forfeit_rep_penalty
        # Run end-of-quest resolution (sell artifacts, collect gold, apply rep, exp)
        artifact_pool = list(run_state.get("artifact_pool") or [])
        party_team = run_state.get("team") or []
        equipped_artifact_ids = [m.get("artifact_id") for m in party_team if m.get("artifact_id")]
        all_quest_artifacts = list(dict.fromkeys(equipped_artifact_ids + artifact_pool))
        artifact_sale_gold = len(all_quest_artifacts) * 100
        run_state["gold_pool"] = run_state.get("gold_pool", 0) + artifact_sale_gold
        quest_gold = run_state.get("gold_pool", 0)
        self.profile.gold = getattr(self.profile, "gold", 0) + quest_gold
        rep_total = run_state.get("reputation_gain_total", 0)
        self._commit_quest_reputation(rep_total)
        final_wins = run_state.get("wins", 0)
        quest_exp = 50 + (20 * final_wins)
        self._apply_exp_gain(quest_exp)
        self._reset_quest_run_state("ai")
        self._persist_profile()
        self.route = "quests_menu"

    def _route_after_lan_setup(self) -> str:
        if self.lan_context == "training":
            return "training_grounds"
        if self.lan_context == "quest":
            return "guild_hall"
        return "bouts_menu"

    def _route_after_quest_draft_back(self) -> str:
        if self.quest_context == "training":
            return "training_grounds"
        return "quests_menu"

    def _quest_draft_target_count(self) -> int:
        return 6 if self.quest_draft_mode == "party_builder" else 3

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
                        self.profile.reputation,
                        state["current_win_streak"],
                        state["current_loss_streak"],
                        self._quest_avg_opponent_glory(mode),
                    ),
                    "party_lines": self._quest_party_lines_for(state["team"] if state["active"] else None),
                }
            )
        return summaries

    def _quest_loadout_waiting_note(self) -> str:
        if self.quest_context == "ranked":
            return "Loadouts are already locked from the six-member party screen. Finalize formation only here."
        if self.quest_opponent_mode != "lan":
            return ""
        if self.quest_local_ready and not self.quest_remote_ready:
            return "Loadout locked. Waiting for the remote commander to finish."
        if self.quest_remote_ready and not self.quest_local_ready:
            return "The remote commander is ready. Lock your own loadout to begin."
        return "Both commanders draft from the same six, then confirm loadouts independently."

    def _enter_quest_party_loadout(self):
        run_state = self._quest_run_state("ai")
        team = self._normalize_quest_party_team(run_state.get("team"))
        run_state["team"] = team
        if not run_state.get("active") or len(team) != 6:
            return
        pool_ids = run_state.get("artifact_pool") or []
        allowed_artifact_ids = sorted(pool_ids) if pool_ids else sorted(self._loadout_artifact_ids(allow_all=False))
        self.quest_party_loadout_state = {
            "team1": run_state["team"],
            "team2": [],
            "team1_allowed_artifact_ids": allowed_artifact_ids,
        }
        self.quest_party_loadout_index = 0
        self.quest_party_loadout_detail_scroll = 0
        self.route = "quest_party_loadout"

    def _open_quest_team_import(self):
        self.quest_team_import_open = True
        if not self.quest_team_import_status_lines:
            self.quest_team_import_status_lines = [
                "Paste a six-member team block, then press Import.",
                "Formatting is flexible: capitalization and spacing do not need to match exactly.",
            ]

    def _close_quest_team_import(self):
        self.quest_team_import_open = False

    def _set_quest_team_import_status(self, lines: list[str]):
        self.quest_team_import_status_lines = list(lines[:3])

    def _append_quest_team_import_text(self, chunk: str):
        if not chunk:
            return
        normalized = chunk.replace("\r\n", "\n").replace("\r", "\n")
        max_len = 24000
        if len(self.quest_team_import_text) >= max_len:
            return
        self.quest_team_import_text += normalized[: max_len - len(self.quest_team_import_text)]

    def _paste_quest_team_import_from_clipboard(self):
        try:
            if not pygame.scrap.get_init():
                pygame.scrap.init()
            clip = pygame.scrap.get(pygame.SCRAP_TEXT)
            if clip is None:
                self._set_quest_team_import_status(["Clipboard is empty or unavailable."])
                return
            if isinstance(clip, bytes):
                text = clip.decode("utf-8", errors="ignore")
            else:
                text = str(clip)
            text = text.replace("\x00", "")
            if not text.strip():
                self._set_quest_team_import_status(["Clipboard did not contain readable team text."])
                return
            self._append_quest_team_import_text(text)
            self._set_quest_team_import_status(["Pasted from clipboard. Press Import to validate and apply."])
        except Exception:
            self._set_quest_team_import_status(["Clipboard paste failed on this platform. You can still type the team text manually."])

    def _extract_import_team_name(self, text: str) -> str:
        for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw.strip()
            if not line:
                continue
            if "@" in line:
                return ""
            return line[:48]
        return ""

    def _apply_quest_team_import(self):
        members, errors = import_team_from_text(self.quest_team_import_text, expected_members=6)
        if errors:
            self._set_quest_team_import_status(errors)
            return
        self.quest_imported_party_members = copy.deepcopy(members)
        self.quest_imported_party_name = self._extract_import_team_name(self.quest_team_import_text)
        self.quest_offer_ids = [member["adventurer_id"] for member in members]
        self.quest_selected_ids = [adventurer_id for adventurer_id in self.quest_selected_ids if adventurer_id in self.quest_offer_ids][:3]
        self.quest_focus_id = self.quest_offer_ids[0] if self.quest_offer_ids else None
        self.quest_draft_offer_scroll = 0
        self.quest_draft_detail_scroll = 0
        label = self.quest_imported_party_name or "Imported team"
        self._set_quest_team_import_status(
            [
                f"{label} imported successfully.",
                "Only legal teams can be imported; this team passed validation.",
            ]
        )
        self._close_quest_team_import()

    def _prefill_quest_loadout_from_import(self):
        if self.quest_setup_state is None or not self.quest_imported_party_members:
            return
        imported_by_adventurer = {
            member["adventurer_id"]: member
            for member in self.quest_imported_party_members
        }
        team_num = self.quest_player_seat
        team_key = f"team{team_num}"
        team_members = list(self.quest_setup_state.get(team_key, []))
        for index, member in enumerate(team_members):
            imported = imported_by_adventurer.get(member["adventurer_id"])
            if imported is None:
                continue
            set_member_class(self.quest_setup_state, team_num, index, imported["class_name"])
        team_members = list(self.quest_setup_state.get(team_key, []))
        for index, member in enumerate(team_members):
            imported = imported_by_adventurer.get(member["adventurer_id"])
            if imported is None:
                continue
            set_member_skill(self.quest_setup_state, team_num, index, imported["class_skill_id"])
            set_member_weapon(self.quest_setup_state, team_num, index, imported["primary_weapon_id"])
            set_member_artifact(self.quest_setup_state, team_num, index, imported["artifact_id"])

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
        sbui.set_profile_context(self.profile)
        sbui.begin_status_hover_frame()
        if self.route == "battle" and hasattr(self.battle_controller, "poll_network"):
            self.battle_controller.poll_network()
            self._check_battle_results()

        if self.route == "main_menu":
            self.last_buttons = sbui.draw_main_menu(
                surf,
                mouse_pos,
                self.profile,
                has_current_quest=self._quest_run_state("ai").get("active", False),
            )
        elif self.route == "player_menu":
            self.last_buttons = sbui.draw_player_menu(
                surf,
                mouse_pos,
                self.profile,
                self.player_note_lines,
                favorite_adventurer_id=self._favorite_adventurer_id(),
                favorite_pool_ids=self._favorite_pool_ids(),
            )
        elif self.route == "market":
            self.last_buttons = sbui.draw_market(
                surf,
                mouse_pos,
                self.market_tab,
                self.market_item_scroll,
                self.profile,
                self.market_focus_id,
                self.market_message,
                self.shop_owned_cosmetics,
            )
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
            self.last_buttons = sbui.draw_guild_hall(
                surf,
                mouse_pos,
                has_current_quest=self._quest_run_state("ai").get("active", False),
            )
        elif self.route in {"shops", "armory"}:
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
        elif self.route == "closet":
            self.last_buttons = sbui.draw_closet(
                surf,
                mouse_pos,
                self.closet_tab,
                self._closet_items(),
                self.closet_focus_id,
                self.shop_owned_cosmetics,
                self.profile,
                item_scroll=self.closet_item_scroll,
            )
        elif self.route == "favored_adventurer_select":
            self.last_buttons = sbui.draw_favored_adventurer_select(
                surf,
                mouse_pos,
                self._favorite_pool_ids(),
                self.favorite_select_focus_id,
                self._favorite_adventurer_id(),
                scroll=self.favorite_select_scroll,
            )
        elif self.route == "quests_menu":
            run_state = self._quest_run_state("ai")
            run_state["team"] = self._normalize_quest_party_team(run_state.get("team"))
            party_ids = [member["adventurer_id"] for member in (run_state.get("team") or [])]
            self.last_buttons = sbui.draw_quests_menu(
                surf,
                mouse_pos,
                run_active=bool(run_state.get("active")),
                quest_wins=int(run_state.get("wins", 0)),
                quest_losses=int(run_state.get("losses", 0)),
                current_win_streak=int(run_state.get("current_win_streak", 0)),
                current_loss_streak=int(run_state.get("current_loss_streak", 0)),
                party_ids=party_ids,
                enemy_party_ids=list(self.quest_enemy_party_ids),
            )
        elif self.route == "quest_party_loadout":
            self.last_buttons = sbui.draw_quest_party_loadout(
                surf,
                mouse_pos,
                self.quest_party_loadout_state or {"team1": []},
                self.quest_party_loadout_index,
                detail_scroll=self.quest_party_loadout_detail_scroll,
            )
        elif self.route == "training_grounds":
            self.last_buttons = sbui.draw_training_grounds(
                surf,
                mouse_pos,
                training_favorite_id=self._training_favorite_adventurer_id(),
                roster_scroll=self.training_roster_scroll,
            )
        elif self.route in {"ranked_party_select", "guild_parties"}:
            self.route = "guild_hall"
            self.last_buttons = sbui.draw_guild_hall(
                surf,
                mouse_pos,
                has_current_quest=self._quest_run_state("ai").get("active", False),
            )
        elif self.route == "quest_party_reveal":
            self.last_buttons = sbui.draw_quest_party_reveal(
                surf,
                mouse_pos,
                self.quest_selected_ids,
                self.quest_draft_locked_id,
            )
        elif self.route == "quest_reward_choice":
            run_state = self._quest_run_state("ai")
            self.last_buttons = sbui.draw_quest_reward_choice(
                surf,
                mouse_pos,
                self.quest_reward_options,
                wins=int(run_state.get("wins", 0)),
                losses=int(run_state.get("losses", 0)),
            )
        elif self.route == "quest_draft":
            draft_title = "Start Quest" if self.quest_draft_mode == "party_builder" else "Encounter Prep"
            draft_continue = "Continue To Party Loadouts" if self.quest_draft_mode == "party_builder" else "Continue To Loadouts"
            selected_panel_title = "Quest Party" if self.quest_draft_mode == "party_builder" else "Encounter Team"
            side_panel_title = "Quest Rules" if self.quest_draft_mode == "party_builder" else "Enemy Party"
            side_panel_lines = (
                [
                    "Favorite locked in.",
                    "Choose 5 more from this pool of 9.",
                    "Then set loadouts for all 6.",
                ]
                if self.quest_draft_mode == "party_builder"
                else None
            )
            self.last_buttons = sbui.draw_quest_draft(
                surf,
                mouse_pos,
                self.quest_offer_ids,
                self.quest_focus_id,
                self.quest_selected_ids,
                detail_scroll=self.quest_draft_detail_scroll,
                title=draft_title,
                enemy_party_ids=self.quest_enemy_party_ids if self.quest_draft_mode != "party_builder" else None,
                card_scroll=self.quest_draft_offer_scroll,
                allow_text_import=self.quest_context == "training" and self.quest_opponent_mode == "ai",
                import_open=self.quest_team_import_open,
                import_text=self.quest_team_import_text,
                import_status_lines=self.quest_team_import_status_lines,
                target_count=self._quest_draft_target_count(),
                continue_label=draft_continue,
                selected_panel_title=selected_panel_title,
                side_panel_title=side_panel_title,
                side_panel_lines=side_panel_lines,
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
                editable_loadout=self.quest_context != "ranked",
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
                mode_id=self._bout_mode()["id"],
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
            section_name = self._catalog_section_name()
            self.last_buttons = sbui.draw_catalog(
                surf,
                mouse_pos,
                self.catalog_section_index,
                self.catalog_entry_index,
                self._catalog_filters_for_section(section_name),
                scroll=self.catalog_scroll,
                detail_scroll=self.catalog_detail_scroll,
                favorite_adventurer_id=self._favorite_adventurer_id(),
            )
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
            self.last_buttons = sbui.draw_main_menu(
                surf,
                mouse_pos,
                self.profile,
                has_current_quest=self._quest_run_state("ai").get("active", False),
            )
        sbui.draw_status_hover_tooltip(surf)

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
            if self._hit(btns.get("profile"), pos):
                self.route = "player_menu"
            elif self._hit(btns.get("guild_hall"), pos):
                self.route = "guild_hall"
            elif self._hit(btns.get("market"), pos):
                self._open_market()
            return None

        if route == "player_menu":
            if self._hit(btns.get("back"), pos):
                self.route = "main_menu"
            elif self._hit(btns.get("favorite_card"), pos):
                self._open_favorite_select()
            elif self._hit(btns.get("closet"), pos):
                self._open_closet()
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
            elif self._hit(btns.get("current_quest"), pos):
                if self._quest_run_state("ai").get("active"):
                    self._prepare_next_quest_encounter(route_if_ready="quests_menu")
                else:
                    self._start_ranked_quest_from_favorite()
            elif self._hit(btns.get("training_grounds"), pos):
                self.route = "training_grounds"
            elif self._hit(btns.get("catalog"), pos):
                self.route = "catalog"
            elif self._hit(btns.get("shops"), pos):
                self.shops_tab = "Artifacts"
                self._open_armory()
            return None

        if route == "ranked_party_select":
            self.route = "guild_hall"
            return None

        if route == "training_grounds":
            if self._hit(btns.get("back"), pos):
                self.route = "guild_hall"
                return None
            for rect, adventurer_id in btns.get("training_cards", []):
                if rect.collidepoint(pos):
                    self._set_training_focus(adventurer_id)
                    return None
            if self._hit(btns.get("training_focus"), pos):
                self._set_training_focus(self._training_favorite_adventurer_id())
                return None
            if self._hit(btns.get("vs_ai"), pos):
                self.training_mode = "ai"
                self.quest_opponent_mode = "ai"
                self._start_training_builder()
                return None
            if self._hit(btns.get("vs_lan"), pos):
                self.training_mode = "lan"
                self.quest_context = "training"
                self.quest_opponent_mode = "lan"
                self._open_lan_setup("training")
                return None
            return None

        if route == "guild_parties":
            self.route = "guild_hall"
            return None

        if route in {"shops", "armory"}:
            if self._hit(btns.get("back"), pos):
                self.route = self.previous_route if self.previous_route not in {"shops", "armory"} else "main_menu"
                return None
            for rect, tab_name in btns.get("tabs", []):
                if rect.collidepoint(pos):
                    self.shops_tab = tab_name
                    self._reset_shop_focus()
                    return None
            for rect, item_id in btns.get("items", []):
                if rect.collidepoint(pos):
                    self.shop_focus_kind = "item"
                    self.shop_focus_value = item_id
                    self.shop_message = ""
                    return None
            if self._hit(btns.get("buy"), pos):
                self._purchase_shop_focus()
            return None

        if route == "market":
            if self._hit(btns.get("back"), pos):
                self.route = self.previous_route if self.previous_route != "market" else "main_menu"
                return None
            for rect, tab_name in btns.get("tabs", []):
                if rect.collidepoint(pos):
                    self.market_tab = tab_name
                    self._reset_market_focus()
                    return None
            for rect, item_id in btns.get("items", []):
                if rect.collidepoint(pos):
                    self.market_focus_id = item_id
                    return None
            for rect, package_id in btns.get("packages", []):
                if rect.collidepoint(pos):
                    self.market_focus_id = package_id
                    return None
            if self._hit(btns.get("buy"), pos):
                self._purchase_market_focus()
                return None
            return None

        if route == "closet":
            if self._hit(btns.get("back"), pos):
                self.route = "player_menu"
                return None
            for rect, tab_name in btns.get("categories", []):
                if rect.collidepoint(pos):
                    self.closet_tab = tab_name
                    self._reset_closet_focus()
                    return None
            for rect, item_id, _index in btns.get("items", []):
                if rect.collidepoint(pos):
                    self.closet_focus_id = item_id
                    return None
            if self._hit(btns.get("equip"), pos):
                item = next((entry for entry in self._closet_items() if entry["id"] == self.closet_focus_id), None)
                if item is not None and item["id"] in self.shop_owned_cosmetics:
                    self._set_equipped_market_item(item)
                return None
            return None

        if route == "favored_adventurer_select":
            if self._hit(btns.get("back"), pos):
                self.route = "player_menu"
                return None
            for rect, adventurer_id in btns.get("cards", []):
                if rect.collidepoint(pos):
                    self.favorite_select_focus_id = adventurer_id
                    return None
            if self._hit(btns.get("confirm"), pos) and self.favorite_select_focus_id:
                self._set_favorite_adventurer(self.favorite_select_focus_id)
                self.route = "player_menu"
                return None
            return None

        if route == "quests_menu":
            if self._hit(btns.get("back"), pos):
                self.route = "guild_hall"
                return None
            if self._hit(btns.get("forfeit"), pos):
                self._forfeit_current_quest()
                return None
            if self._hit(btns.get("edit_loadouts"), pos):
                state = self._quest_run_state("ai")
                if state.get("active") and state.get("team") is not None:
                    self._enter_quest_party_loadout()
                return None
            if self._hit(btns.get("advance"), pos):
                state = self._quest_run_state("ai")
                if state.get("active") and state.get("team") is not None:
                    self._prepare_next_quest_encounter(route_if_ready="quest_draft")
                else:
                    self._start_ranked_quest_from_favorite()
                return None
            return None

        if route == "quest_party_loadout":
            if self._hit(btns.get("back"), pos) or self._hit(btns.get("done"), pos):
                self.route = "quests_menu"
                return None
            for rect, index in btns.get("members", []):
                if rect.collidepoint(pos):
                    self.quest_party_loadout_index = index
                    self.quest_party_loadout_detail_scroll = 0
                    return None
            if self._hit(btns.get("weapon_prev"), pos) or self._hit(btns.get("weapon_next"), pos):
                cycle_member_weapon(self.quest_party_loadout_state, 1, self.quest_party_loadout_index)
                return None
            for rect, class_name in btns.get("classes", []):
                if rect.collidepoint(pos):
                    set_member_class(self.quest_party_loadout_state, 1, self.quest_party_loadout_index, class_name)
                    return None
            for rect, skill_id in btns.get("skills", []):
                if rect.collidepoint(pos):
                    set_member_skill(self.quest_party_loadout_state, 1, self.quest_party_loadout_index, skill_id)
                    return None
            for rect, artifact_id, locked in btns.get("artifacts", []):
                if rect.collidepoint(pos) and not locked:
                    set_member_artifact(self.quest_party_loadout_state, 1, self.quest_party_loadout_index, artifact_id)
                    return None
            return None

        if route == "quest_party_reveal":
            if self._hit(btns.get("back"), pos):
                self.quest_selected_ids = []
                self.quest_draft_locked_id = None
                self.route = "quests_menu"
                return None
            if self._hit(btns.get("confirm"), pos):
                self._confirm_quest_party_reveal()
                return None
            return None

        if route == "quest_reward_choice":
            # Top-level choices (gold, recruit) and artifact sub-choices
            for rect, choice_index, artifact_id in btns.get("choices", []):
                if rect.collidepoint(pos):
                    self._apply_quest_reward(choice_index, artifact_id)
                    return None
            return None

        if route == "quest_draft":
            if self.quest_team_import_open:
                if self._hit(btns.get("import_cancel"), pos):
                    self._close_quest_team_import()
                    return None
                if self._hit(btns.get("import_apply"), pos):
                    self._apply_quest_team_import()
                    return None
                if self._hit(btns.get("import_clear"), pos):
                    self.quest_team_import_text = ""
                    self._set_quest_team_import_status(["Import text cleared."])
                    return None
                if self._hit(btns.get("import_paste"), pos):
                    self._paste_quest_team_import_from_clipboard()
                    return None
                # Keep modal open and swallow clicks while importing.
                return None
            if self._hit(btns.get("import_team"), pos):
                self._open_quest_team_import()
                return None
            if self._hit(btns.get("back"), pos):
                self.route = self._route_after_quest_draft_back()
                return None
            if self._hit(btns.get("pick"), pos):
                self._pick_quest_focus()
                return None
            if self._hit(btns.get("continue"), pos) and len(self.quest_selected_ids) == self._quest_draft_target_count():
                if self.quest_draft_mode == "party_builder":
                    self._confirm_ranked_quest_party()
                else:
                    self._enter_quest_loadout()
                return None
            if any(rect.collidepoint(pos) for rect, _ in btns.get("party_slots", [])):
                for rect, adventurer_id in btns.get("party_slots", []):
                    if rect.collidepoint(pos):
                        self._remove_quest_selected_adventurer(adventurer_id)
                        self.quest_draft_detail_scroll = 0
                        return None
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
                    self._start_quest_encounter()
                else:
                    self._confirm_lan_quest_loadout()
                return None
            if self.quest_local_ready:
                return None
            for rect, index, _slot in btns.get("formation_members", []):
                if rect.collidepoint(pos):
                    self.quest_loadout_index = index
                    return None
            if self.quest_context == "ranked":
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
            if self._hit(btns.get("vs_random"), pos):
                self._start_bout_series("random")
                return None
            if self._hit(btns.get("vs_focused"), pos):
                self._start_bout_series("focused")
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
            for rect, index in btns.get("sections", []):
                if rect.collidepoint(pos):
                    self.catalog_section_index = index
                    self._reset_catalog_navigation()
                    return None
            for rect, key, direction in btns.get("filters", []):
                if rect.collidepoint(pos):
                    self._cycle_catalog_filter(key, direction)
                    return None
            for rect, index in btns.get("entries", []):
                if rect.collidepoint(pos):
                    self.catalog_entry_index = index
                    self.catalog_detail_scroll = 0
                    return None
            return None

        if route == "lan_setup":
            if self._hit(btns.get("back"), pos):
                self._close_lan()
                self.route = self._route_after_lan_setup()
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

        if self.route == "quest_draft" and self.quest_team_import_open:
            if e.key == pygame.K_ESCAPE:
                self._close_quest_team_import()
                return None
            if e.key == pygame.K_v and (e.mod & pygame.KMOD_CTRL):
                self._paste_quest_team_import_from_clipboard()
                return None
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and (e.mod & pygame.KMOD_CTRL):
                self._apply_quest_team_import()
                return None
            if e.key == pygame.K_BACKSPACE:
                self.quest_team_import_text = self.quest_team_import_text[:-1]
                return None
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._append_quest_team_import_text("\n")
                return None
            if e.key == pygame.K_TAB:
                self._append_quest_team_import_text("    ")
                return None
            if e.unicode and e.unicode.isprintable():
                self._append_quest_team_import_text(e.unicode)
                return None
            return None

        if e.key == pygame.K_ESCAPE:
            if self.route == "settings":
                self.route = self.previous_route
            elif self.route in {"player_menu", "market"}:
                self.route = "main_menu"
            elif self.route in {"armory", "shops", "catalog", "training_grounds", "quests_menu", "bouts_menu"}:
                self.route = "guild_hall"
            elif self.route in {"inventory", "friends", "closet", "favored_adventurer_select"}:
                self.route = "player_menu"
            elif self.route == "guild_hall":
                self.route = "main_menu"
            elif self.route == "lan_setup":
                self._close_lan()
                self.route = self._route_after_lan_setup()
            elif self.route == "quest_draft":
                self.route = self._route_after_quest_draft_back()
            elif self.route == "quest_party_loadout":
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
            if len(self.quest_selected_ids) == self._quest_draft_target_count():
                if self.quest_draft_mode == "party_builder":
                    self._confirm_ranked_quest_party()
                else:
                    self._enter_quest_loadout()
            else:
                self._pick_quest_focus()
            return None

        if self.route == "bout_draft" and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._draft_bout_focus()
            return None
        if self.route == "catalog":
            total = len(self._catalog_entries_for_section())
            page_size = max(1, (self.last_buttons or {}).get("entry_page_size", 8))
            max_scroll = max(0, total - page_size)
            if e.key == pygame.K_UP:
                self.catalog_scroll = max(0, self.catalog_scroll - 1)
                return None
            if e.key == pygame.K_DOWN:
                self.catalog_scroll = min(max_scroll, self.catalog_scroll + 1)
                return None
            if e.key == pygame.K_PAGEUP:
                self.catalog_scroll = max(0, self.catalog_scroll - page_size)
                return None
            if e.key == pygame.K_PAGEDOWN:
                self.catalog_scroll = min(max_scroll, self.catalog_scroll + page_size)
                return None
        return None

    def handle_mousewheel(self, event):
        if self.route == "quest_draft":
            if self.quest_team_import_open:
                return None
            btns = self.last_buttons or {}
            viewport = btns.get("detail_viewport")
            if viewport is not None and viewport.collidepoint(self.last_mouse_pos):
                max_scroll = btns.get("detail_scroll_max", 0)
                self.quest_draft_detail_scroll = max(0, min(max_scroll, self.quest_draft_detail_scroll - (event.y * 28)))
                return None
            max_scroll = btns.get("offer_scroll_max", 0)
            page_size = max(1, btns.get("offer_page_size", 6))
            if max_scroll > 0:
                step = max(1, min(3, page_size // 3))
                self.quest_draft_offer_scroll = max(0, min(max_scroll, self.quest_draft_offer_scroll - (event.y * step)))
            return None
        if self.route == "bout_draft":
            btns = self.last_buttons or {}
            viewport = btns.get("detail_viewport")
            if viewport is not None and viewport.collidepoint(self.last_mouse_pos):
                max_scroll = btns.get("detail_scroll_max", 0)
                self.bout_draft_detail_scroll = max(0, min(max_scroll, self.bout_draft_detail_scroll - (event.y * 28)))
                return None
        if self.route == "quest_party_loadout":
            btns = self.last_buttons or {}
            viewport = btns.get("detail_viewport")
            if viewport is not None and viewport.collidepoint(self.last_mouse_pos):
                max_scroll = btns.get("detail_scroll_max", 0)
                self.quest_party_loadout_detail_scroll = max(0, min(max_scroll, self.quest_party_loadout_detail_scroll - (event.y * 28)))
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
            btns = self.last_buttons or {}
            detail_viewport = btns.get("detail_viewport")
            if detail_viewport is not None and detail_viewport.collidepoint(self.last_mouse_pos):
                max_scroll = btns.get("detail_scroll_max", 0)
                self.catalog_detail_scroll = max(0, min(max_scroll, self.catalog_detail_scroll - (event.y * 28)))
                return None
            entries_viewport = btns.get("entries_viewport")
            if entries_viewport is not None and entries_viewport.collidepoint(self.last_mouse_pos):
                max_scroll = btns.get("entry_scroll_max", 0)
                self.catalog_scroll = max(0, min(max_scroll, self.catalog_scroll - event.y))
                return None
            return None
        if self.route in {"shops", "armory"}:
            items = shop_items_for_tab(self.shops_tab)
            max_scroll = max(0, len(items) - 6)
            if max_scroll > 0:
                self.shop_item_scroll = max(0, min(max_scroll, self.shop_item_scroll - (event.y * 2)))
            return None
        if self.route == "market":
            if self.market_tab == "Embassy":
                return None
            max_scroll = max(0, len(self._market_items()) - 6)
            if max_scroll > 0:
                self.market_item_scroll = max(0, min(max_scroll, self.market_item_scroll - (event.y * 2)))
            return None
        if self.route == "closet":
            max_scroll = max(0, len([item for item in self._closet_items() if item["id"] in self.shop_owned_cosmetics]) - 8)
            if max_scroll > 0:
                self.closet_item_scroll = max(0, min(max_scroll, self.closet_item_scroll - (event.y * 2)))
            return None
        if self.route == "training_grounds":
            max_scroll = max(0, len(ADVENTURERS_BY_ID) - 8)
            if max_scroll > 0:
                self.training_roster_scroll = max(0, min(max_scroll, self.training_roster_scroll - (event.y * 2)))
            return None
        if self.route == "favored_adventurer_select":
            max_scroll = max(0, len(self._favorite_pool_ids()) - 9)
            if max_scroll > 0:
                self.favorite_select_scroll = max(0, min(max_scroll, self.favorite_select_scroll - (event.y * 2)))
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
            self.shop_message = shop_tab_note(self.shops_tab)
        else:
            self.shop_focus_kind = None
            self.shop_focus_value = None
            self.shop_message = shop_tab_note(self.shops_tab)

    def _open_shops(self):
        self.previous_route = self.route
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
                pass  # Artifacts no longer unlocked individually; they enter the run pool via draft
            else:
                self.shop_message = "This stock card is not purchasable in the current build."
                return
            level_lines = self._apply_exp_gain(0)
            self.shop_message = f"Purchased {item['name']} for {item['price']} Gold."
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
            self.shop_message = "Embassy is informational here. Artifacts and cosmetics are sold in this build."
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

    def _sync_quest_run_cache(self, state: dict):
        state["team"] = self._normalize_quest_party_team(state.get("team"))
        self.quest_run_active = bool(state["active"])
        self.quest_run_wins = int(state["wins"])
        self.quest_run_losses = int(state["losses"])
        self.quest_run_current_win_streak = int(state["current_win_streak"])
        self.quest_run_current_loss_streak = int(state["current_loss_streak"])
        self.quest_run_opponent_glories = list(state["opponent_glories"])
        self.quest_player_team = copy.deepcopy(state["team"]) if state["team"] is not None else None

    def _apply_reputation_result(
        self,
        *,
        did_win: bool,
        current_win_streak_before: int,
        current_loss_streak_before: int,
    ) -> str:
        old_reputation = self.profile.reputation
        new_reputation, delta = update_reputation_after_match(
            self.profile.reputation,
            self.current_battle_opponent_glory,
            did_win=did_win,
            current_win_streak_before_match=current_win_streak_before,
            current_loss_streak_before_match=current_loss_streak_before,
            floor_reputation=1,
        )
        self.profile.reputation = new_reputation
        self.profile.ranked_games_played = getattr(self.profile, "ranked_games_played", 0) + 1
        self.profile.storybook_rank_label = get_rank_from_reputation(new_reputation)
        self.profile.floor_reputation = rank_floor_for_reputation(new_reputation)
        self.profile.season_high_reputation = max(
            getattr(self.profile, "season_high_reputation", new_reputation),
            new_reputation,
        )
        return f"Reputation {old_reputation} -> {new_reputation} ({delta:+d})"

    def _finalize_quest_result(self, lines: list[str]) -> list[str]:
        run_state = self._quest_run_state(self.quest_opponent_mode)
        run_mode = self.quest_opponent_mode
        run_wins_before = run_state["wins"]
        run_losses_before = run_state["losses"]
        win_streak_before = run_state["current_win_streak"]
        loss_streak_before = run_state["current_loss_streak"]
        reputation_before = self.profile.reputation
        avg_opponent_glory_before = self._quest_avg_opponent_glory("ai")
        party_snapshot = copy.deepcopy(run_state["team"]) if run_state["team"] is not None else None
        ranked_ai = self.quest_context == "ranked" and run_mode == "ai"

        if ranked_ai:
            # Accumulate reputation delta; apply total at quest end (Section 2.6)
            _, rep_delta = update_reputation_after_match(
                self.profile.reputation + run_state.get("reputation_gain_total", 0),
                self.current_battle_opponent_glory,
                did_win=self.result_victory,
                current_win_streak_before_match=win_streak_before,
                current_loss_streak_before_match=loss_streak_before,
                floor_reputation=1,
            )
            run_state["reputation_gain_total"] = run_state.get("reputation_gain_total", 0) + rep_delta
            self.profile.ranked_games_played = getattr(self.profile, "ranked_games_played", 0) + 1
            running_total = run_state["reputation_gain_total"]
            reputation_line = f"Rep change this encounter: {rep_delta:+d} (quest total: {running_total:+d}, applied at end)"
        else:
            reputation_line = "Reputation is unchanged in training or LAN encounters."

        if ranked_ai and run_mode == "ai" and self.current_battle_opponent_glory > 0:
            run_state["opponent_glories"].append(self.current_battle_opponent_glory)
            if len(run_state["opponent_glories"]) > 20:
                run_state["opponent_glories"] = run_state["opponent_glories"][-20:]

        if self.result_victory:
            gold_reward = 0
            if ranked_ai:
                run_state["wins"] += 1
                run_state["current_win_streak"] += 1
                run_state["current_loss_streak"] = 0
                run_state["active"] = True
                run_state["match_count"] += 1
                run_state["total_gold_earned"] += gold_reward
                self.profile.ranked_total_wins = max(0, int(getattr(self.profile, "ranked_total_wins", 0))) + 1
                self.profile.ranked_best_quest_wins = max(
                    getattr(self.profile, "ranked_best_quest_wins", 0),
                    run_state["wins"],
                )
                self.story_quest_best = max(self.story_quest_best, run_state["wins"])
                if run_state.get("quest_id"):
                    self.profile.ranked_current_quest_id = run_state["quest_id"]
            if gold_reward > 0:
                self.profile.gold += gold_reward
            level_lines = self._apply_exp_gain(0)
            if ranked_ai:
                log_quest_ai_match(
                    {
                        "did_win": True,
                        "reputation_before": reputation_before,
                        "reputation_after": self.profile.reputation,
                        "opponent_glory": self.current_battle_opponent_glory,
                        "run_wins_before": run_wins_before,
                        "run_losses_before": run_losses_before,
                        "win_streak_before": win_streak_before,
                        "loss_streak_before": loss_streak_before,
                        "party_ids": [member["adventurer_id"] for member in party_snapshot or []],
                        "offer_ids": list(self.quest_offer_ids),
                        "avg_opponent_glory_before": avg_opponent_glory_before,
                    }
                )
            if ranked_ai:
                self._sync_quest_run_cache(run_state)
            summary = []
            if ranked_ai:
                summary.extend(
                    [
                        f"Quest Record: {run_state['wins']}W-{run_state['losses']}L",
                        f"Winstreak: {run_state['current_win_streak']} | Lossstreak: 0",
                    ]
                )
            else:
                summary.append("Training Encounter Complete")
            if ranked_ai:
                self.quest_reward_pending = True
                self.quest_reward_options = self._build_quest_reward_options()
                reward_line = "Choose your reward below after reviewing results."
            else:
                reward_line = "Encounter complete."
            self._persist_profile()
            return [*summary, reward_line, *level_lines, reputation_line, *lines]

        if ranked_ai:
            run_state["losses"] += 1
            run_state["current_loss_streak"] += 1
            run_state["current_win_streak"] = 0
            run_state["match_count"] += 1
            self.profile.ranked_total_losses = max(0, int(getattr(self.profile, "ranked_total_losses", 0))) + 1
            # −10 Rep subtracted from quest's running total; −50 Gold from quest pool (floor: 0)
            run_state["reputation_gain_total"] = run_state.get("reputation_gain_total", 0) - 10
            gold_penalty = 50
            current_pool = run_state.get("gold_pool", 0)
            run_state["gold_pool"] = max(0, current_pool - gold_penalty)

        summary = []
        if ranked_ai:
            rep_running = run_state.get("reputation_gain_total", 0)
            summary.extend(
                [
                    f"Quest Record: {run_state['wins']}W-{run_state['losses']}L",
                    f"Winstreak: 0 | Lossstreak: {run_state['current_loss_streak']}",
                    "Loss: −10 Rep (quest total), −50 Gold from quest pool.",
                    f"Quest Rep total: {rep_running:+d}",
                ]
            )
        else:
            summary.append("Training Encounter Lost")

        if ranked_ai:
            log_quest_ai_match(
                {
                    "did_win": False,
                    "reputation_before": reputation_before,
                    "reputation_after": self.profile.reputation,
                    "opponent_glory": self.current_battle_opponent_glory,
                    "run_wins_before": run_wins_before,
                    "run_losses_before": run_losses_before,
                    "win_streak_before": win_streak_before,
                    "loss_streak_before": loss_streak_before,
                    "party_ids": [member["adventurer_id"] for member in party_snapshot or []],
                    "offer_ids": list(self.quest_offer_ids),
                    "avg_opponent_glory_before": avg_opponent_glory_before,
                }
            )
        if ranked_ai and run_state["losses"] >= 3:
            # --- End of Quest: 4-step resolution (Section 4.5) ---
            # Step 1: Sell all artifacts (equipped + pool) for 100 Gold each
            artifact_pool = list(run_state.get("artifact_pool") or [])
            party_team = run_state.get("team") or []
            equipped_artifact_ids = [m.get("artifact_id") for m in party_team if m.get("artifact_id")]
            all_quest_artifacts = list(dict.fromkeys(equipped_artifact_ids + artifact_pool))
            artifact_sale_gold = len(all_quest_artifacts) * 100
            run_state["gold_pool"] = run_state.get("gold_pool", 0) + artifact_sale_gold
            # Step 2: Collect Gold — transfer quest pool to permanent balance
            quest_gold = run_state.get("gold_pool", 0)
            self.profile.gold = getattr(self.profile, "gold", 0) + quest_gold
            # Step 3: Apply Reputation
            rep_total = run_state.get("reputation_gain_total", 0)
            rep_applied_line = self._commit_quest_reputation(rep_total)
            is_successful = rep_total > 0
            # Step 4: Earn Exp
            final_wins = run_state["wins"]
            quest_exp = 50 + (20 * final_wins)
            quest_level_lines = self._apply_exp_gain(quest_exp)
            summary.append(f"Quest ended: {final_wins} wins, 3 losses.")
            if artifact_sale_gold > 0:
                summary.append(f"Artifacts sold: {len(all_quest_artifacts)} × 100 = {artifact_sale_gold} Gold")
            summary.append(f"Quest Gold collected: {quest_gold} Gold")
            summary.append(rep_applied_line)
            if is_successful:
                summary.append("Successful Quest (net Rep gain is positive).")
            summary.append(f"Quest Exp: +{quest_exp}")
            summary.extend(quest_level_lines)
            self._reset_quest_run_state(run_mode)
        elif ranked_ai:
            run_state["active"] = True
            self._sync_quest_run_cache(run_state)
            summary.append("Quest remains active. Continue to the next encounter.")
        else:
            summary.append("Return to Training Grounds to queue another encounter.")
        self._persist_profile()
        return [*summary, reputation_line, *lines]

    def _finalize_bout_result(self, lines: list[str]) -> list[str]:
        mode = self._bout_mode()
        player_wins_before = self.bout_run.player_wins
        opponent_wins_before = self.bout_run.opponent_wins
        self.bout_run.match_count += 1
        gold_earned = 0
        mode_id = self._bout_mode()["id"]
        if self.result_victory:
            self.story_bout_wins += 1
            self.bout_run.player_wins += 1
            bout_exp = 80 if mode_id == "random" else 50
            level_lines = self._apply_exp_gain(bout_exp)
            # AI bouts: no Gold reward (Section 5.1/5.2); LAN bouts use Bartender skill
            if self.bout_opponent_mode == "lan":
                gold_earned = 50  # placeholder; Bartender skill determines actual amount
                self.profile.gold += gold_earned
                self.bout_run.gold_earned += gold_earned
        else:
            self.story_bout_losses += 1
            self.bout_run.opponent_wins += 1
            bout_exp = 30 if mode_id == "random" else 20
            level_lines = self._apply_exp_gain(bout_exp)
        series_score = f"{self.bout_run.player_wins}-{self.bout_run.opponent_wins}"
        series_over = self.bout_run.player_wins >= 2 or self.bout_run.opponent_wins >= 2
        if series_over:
            self.bout_run.active = False
            series_result = "Series won!" if self.bout_run.player_wins >= 2 else "Series lost."
        else:
            series_result = f"Match {self.bout_run.match_count} of 3."
        summary = [
            f"Mode: {mode['name']}",
            f"Series: {series_score}  —  {series_result}",
        ]
        if gold_earned > 0:
            summary.append(f"+{gold_earned} Gold")
        summary.append(f"+{bout_exp} Exp")
        summary.extend(level_lines)
        self._persist_profile()
        seat_note = "You drafted second and carried the round-one bonus swap." if self.bout_player_seat == 2 else "Your opponent drafted second and opened with the bonus swap advantage."
        return summary + [seat_note] + lines

    def _continue_from_results(self):
        if self.result_kind == "quest":
            if self.quest_reward_pending:
                self.quest_reward_pending = False
                self.route = "quest_reward_choice"
                return
            if self.quest_context == "ranked" and self.quest_opponent_mode == "ai" and self._quest_run_state("ai").get("active"):
                self._prepare_next_quest_encounter(force_new=True, route_if_ready="quests_menu")
            elif self.quest_context == "training":
                self.route = "training_grounds"
            else:
                self.route = "guild_hall"
        else:
            if self.bout_opponent_mode == "lan":
                self.route = "bouts_menu"
            elif self.bout_run.active:
                # Series still in progress — start next encounter
                mode_id = self._bout_mode()["id"]
                if mode_id == "focused":
                    self._enter_bout_loadout()
                elif self.bout_player_full_party:
                    # Random bout with auto-assembled parties: re-pick 3 from same 6
                    self._restart_random_bout_encounter()
                else:
                    self._start_bout_draft()
            else:
                # Series over — return to bouts menu
                self.route = "bouts_menu"

    def _return_from_results(self):
        if self.result_kind == "quest":
            if self.quest_context == "training":
                self.route = "training_grounds"
            elif self.quest_context == "ranked" and self.quest_opponent_mode == "ai" and self._quest_run_state("ai").get("active"):
                self._prepare_next_quest_encounter(force_new=True, route_if_ready="quests_menu")
            else:
                self.route = "guild_hall"
        else:
            self.bout_run.active = False
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
            if self.quest_context == "ranked" and self.quest_opponent_mode == "ai":
                self._reset_quest_run_state("ai")
                self._persist_profile()
            self.route = "training_grounds" if self.quest_context == "training" else "guild_hall"
        elif self.current_battle_result_kind == "bout":
            self.bout_run = BoutRunState()
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

    def _pick_quest_focus(self):
        if self.quest_focus_id is None or self.quest_focus_id in self.quest_selected_ids:
            return
        if len(self.quest_selected_ids) >= self._quest_draft_target_count():
            return
        self.quest_selected_ids.append(self.quest_focus_id)

    def _remove_quest_selected_adventurer(self, adventurer_id: str):
        if adventurer_id not in self.quest_selected_ids:
            return
        if self.quest_draft_mode == "party_builder" and adventurer_id == self.quest_draft_locked_id:
            return
        self.quest_selected_ids = [selected_id for selected_id in self.quest_selected_ids if selected_id != adventurer_id]
        self.quest_focus_id = adventurer_id

    def _confirm_ranked_quest_party(self):
        if self.quest_draft_mode != "party_builder" or len(self.quest_selected_ids) != 6:
            return
        favorite_id = self.quest_draft_locked_id or self._favorite_adventurer_id()
        run_state = self._quest_run_state("ai")
        quest_id = f"quest-{self.rng.randint(100000, 999999)}"
        run_state["active"] = True
        run_state["quest_id"] = quest_id
        run_state["wins"] = 0
        run_state["losses"] = 0
        run_state["current_win_streak"] = 0
        run_state["current_loss_streak"] = 0
        run_state["opponent_glories"] = []
        run_state["team"] = [self._default_party_loadout_member(adventurer_id) for adventurer_id in self.quest_selected_ids]
        run_state["party_id"] = f"Favorite:{favorite_id}"
        run_state["match_count"] = 0
        run_state["total_gold_earned"] = 0
        self.profile.ranked_current_quest_id = quest_id
        self.quest_draft_mode = "encounter"
        self.quest_draft_locked_id = None
        self._record_quested_adventurers(self.quest_selected_ids)
        self._sync_quest_run_cache(run_state)
        self._persist_profile()
        self._prepare_next_quest_encounter(force_new=True, route_if_ready="quests_menu")
        self._enter_quest_party_loadout()

    def _confirm_quest_party_reveal(self):
        if len(self.quest_selected_ids) != 6:
            return
        favorite_id = self.quest_draft_locked_id or self._favorite_adventurer_id()
        run_state = self._quest_run_state("ai")
        quest_id = f"quest-{self.rng.randint(100000, 999999)}"
        run_state["active"] = True
        run_state["quest_id"] = quest_id
        run_state["wins"] = 0
        run_state["losses"] = 0
        run_state["current_win_streak"] = 0
        run_state["current_loss_streak"] = 0
        run_state["opponent_glories"] = []
        run_state["team"] = [self._default_party_loadout_member(adventurer_id) for adventurer_id in self.quest_selected_ids]
        run_state["party_id"] = f"Favorite:{favorite_id}"
        run_state["match_count"] = 0
        run_state["total_gold_earned"] = 0
        run_state["gold_pool"] = 0
        run_state["reputation_gain_total"] = 0
        run_state["artifact_pool"] = self._draw_quest_artifact_pool(self.quest_selected_ids)
        self.profile.ranked_current_quest_id = quest_id
        self.quest_draft_mode = "encounter"
        self.quest_draft_locked_id = None
        self._record_quested_adventurers(self.quest_selected_ids)
        self._sync_quest_run_cache(run_state)
        self._persist_profile()
        self._prepare_next_quest_encounter(force_new=True, route_if_ready="quests_menu")
        self._enter_quest_party_loadout()

    def _draw_quest_artifact_pool(self, party_ids: list, count: int = 3) -> list:
        """Draw `count` starting artifacts for a quest run (Section 4.1 Step 3).

        Constraints:
        - No two selected artifacts share any attunement classes.
        - Every class represented in the party can attune to at least one of the three.
        Falls back gracefully if the full constraint cannot be satisfied.
        """
        party_classes: set[str] = set()
        for adv_id in party_ids:
            profile = ADVENTURER_AI.get(adv_id)
            if profile:
                party_classes.update(profile.preferred_classes)
            else:
                party_classes.update(CLASS_SKILLS.keys())

        all_artifacts = list(ARTIFACTS)
        self.rng.shuffle(all_artifacts)
        selected: list = []
        used_attunements: set[str] = set()
        covered_classes: set[str] = set()
        # Greedy selection with constraint check
        for attempt_expanded in (False, True):
            selected = []
            used_attunements = set()
            covered_classes = set()
            candidates = all_artifacts[:]
            if attempt_expanded:
                # Relax no-shared-attunement constraint on second pass
                pass
            for artifact in candidates:
                if len(selected) >= count:
                    break
                attunement_set = set(artifact.attunement)
                if not attempt_expanded and attunement_set & used_attunements:
                    continue
                # Prefer artifacts that cover uncovered party classes
                new_coverage = attunement_set & party_classes - covered_classes
                if not new_coverage and covered_classes >= party_classes and len(selected) > 0:
                    # Already covered all classes; still add if we need more
                    pass
                selected.append(artifact.id)
                used_attunements.update(attunement_set)
                covered_classes.update(attunement_set & party_classes)
            if len(selected) == count:
                break
        # Fill remaining slots if needed
        if len(selected) < count:
            remaining = [a.id for a in ARTIFACTS if a.id not in selected]
            self.rng.shuffle(remaining)
            selected += remaining[:count - len(selected)]
        return selected[:count]

    def _build_quest_reward_options(self) -> list[dict]:
        """Generate the three reward choices shown after a quest win."""
        run_state = self._quest_run_state("ai")
        current_pool = list(run_state.get("artifact_pool") or [])
        # Option 1: Gold
        gold_amount = 100
        # Option 2: Artifact — choose from 3 with different stat bonuses, no shared attunements
        existing_ids = set(current_pool)
        available = [a for a in ARTIFACTS if a.id not in existing_ids]
        self.rng.shuffle(available)
        artifact_choices: list[dict] = []
        used_attunements: set[str] = set()
        for artifact in available:
            if len(artifact_choices) >= 3:
                break
            attunement_set = set(artifact.attunement)
            if attunement_set & used_attunements:
                continue
            artifact_choices.append({"artifact_id": artifact.id, "artifact_name": artifact.name})
            used_attunements.update(attunement_set)
        # Fallback: fill with any remaining if constraint can't be met
        if len(artifact_choices) < 3:
            for artifact in available:
                if len(artifact_choices) >= 3:
                    break
                if not any(c["artifact_id"] == artifact.id for c in artifact_choices):
                    artifact_choices.append({"artifact_id": artifact.id, "artifact_name": artifact.name})
        artifact_option = {"kind": "artifact", "artifact_choices": artifact_choices}
        # Option 3: Recruit — costs 100 Gold from quest pool (placeholder)
        recruit_option = {"kind": "recruit", "adventurer_id": None}
        return [
            {"kind": "gold", "amount": gold_amount},
            artifact_option,
            recruit_option,
        ]

    def _apply_quest_reward(self, choice_index: int, artifact_id: str | None = None):
        """Apply the selected reward option and advance to the next encounter."""
        if not self.quest_reward_options or choice_index >= len(self.quest_reward_options):
            self._advance_quest_after_reward()
            return
        option = self.quest_reward_options[choice_index]
        run_state = self._quest_run_state("ai")
        if option["kind"] == "gold":
            run_state["gold_pool"] = run_state.get("gold_pool", 0) + option["amount"]
        elif option["kind"] == "artifact" and artifact_id:
            pool = list(run_state.get("artifact_pool") or [])
            if artifact_id not in pool:
                pool.append(artifact_id)
            run_state["artifact_pool"] = pool
        # "recruit" is deferred — no action yet
        self.quest_reward_options = []
        self._persist_profile()
        self._advance_quest_after_reward()

    def _commit_quest_reputation(self, rep_total: int) -> str:
        """Apply the accumulated quest reputation total to the player's permanent profile."""
        old_rep = self.profile.reputation
        new_rep = max(1, old_rep + rep_total)
        self.profile.reputation = new_rep
        from storybook_ranked import get_rank_from_reputation, rank_floor_for_reputation
        self.profile.storybook_rank_label = get_rank_from_reputation(new_rep)
        self.profile.floor_reputation = rank_floor_for_reputation(new_rep)
        self.profile.season_high_reputation = max(
            getattr(self.profile, "season_high_reputation", new_rep),
            new_rep,
        )
        return f"Reputation applied: {old_rep} → {new_rep} ({rep_total:+d})"

    def _restart_random_bout_encounter(self):
        """Re-enter encounter pick for the next Random Bout match from the same 6-person parties."""
        self.quest_context = "bout_random"
        self.quest_draft_mode = "encounter"
        self.quest_offer_ids = list(self.bout_player_full_party)
        self.quest_focus_id = self.bout_player_full_party[0] if self.bout_player_full_party else None
        self.quest_selected_ids = []
        self.quest_enemy_party_ids = list(self.bout_ai_full_party)
        candidate_pool = list(self.bout_ai_full_party)[:6]
        try:
            enemy_choice = choose_quest_party(
                candidate_pool,
                enemy_party_ids=list(self.bout_player_full_party),
                difficulty="normal",
                rng=self.rng,
            )
            self.quest_enemy_selected_ids = list(enemy_choice.team_ids)
            self.quest_enemy_setup_members = self._team_from_loadout(enemy_choice.loadout)
        except Exception:
            self.quest_enemy_selected_ids = candidate_pool[:3]
            self.quest_enemy_setup_members = [self._default_party_loadout_member(adv_id) for adv_id in candidate_pool[:3]]
        self.quest_draft_detail_scroll = 0
        self.quest_setup_state = None
        self.route = "quest_draft"

    def _advance_quest_after_reward(self):
        if self.quest_context == "ranked" and self.quest_opponent_mode == "ai" and self._quest_run_state("ai").get("active"):
            self._prepare_next_quest_encounter(force_new=True, route_if_ready="quests_menu")
        else:
            self.route = "guild_hall"

    def _enter_quest_loadout(self):
        if len(self.quest_selected_ids) != 3:
            return
        run_state = self._quest_run_state("ai")
        run_state["team"] = self._normalize_quest_party_team(run_state.get("team"))
        enemy_ids = self.quest_enemy_selected_ids[:3]
        if len(enemy_ids) < 3:
            enemy_ids = [adventurer_id for adventurer_id in self.quest_offer_ids if adventurer_id not in self.quest_selected_ids][:3]
        allow_all = self.quest_context == "training" or self.quest_opponent_mode == "lan"
        if self.quest_context == "bout_random" and self.bout_player_artifact_pool:
            player_artifacts = set(self.bout_player_artifact_pool)
        else:
            player_artifacts = self._loadout_artifact_ids(allow_all=allow_all)
        self.quest_setup_state = create_setup_from_team_ids(
            self.quest_selected_ids,
            enemy_ids,
            team1_allowed_artifact_ids=player_artifacts if self.quest_player_seat == 1 else None,
            team2_allowed_artifact_ids=player_artifacts if self.quest_player_seat == 2 else None,
        )
        if self.quest_enemy_setup_members:
            enemy_key = f"team{2 if self.quest_player_seat == 1 else 1}"
            self.quest_setup_state[enemy_key] = copy.deepcopy(self.quest_enemy_setup_members)
        if self.quest_context == "ranked":
            player_key = f"team{self.quest_player_seat}"
            saved_by_id = {
                member["adventurer_id"]: member
                for member in run_state.get("team", [])
            }
            for index, member in enumerate(self.quest_setup_state[player_key]):
                saved = saved_by_id.get(member["adventurer_id"])
                if saved is None:
                    continue
                saved_class = saved.get("class_name", NO_CLASS_NAME)
                set_member_class(self.quest_setup_state, self.quest_player_seat, index, saved_class)
                set_member_weapon(
                    self.quest_setup_state,
                    self.quest_player_seat,
                    index,
                    saved.get("primary_weapon_id") or member["primary_weapon_id"],
                )
                saved_skill = saved.get("class_skill_id")
                if saved_skill:
                    set_member_skill(self.quest_setup_state, self.quest_player_seat, index, saved_skill)
                set_member_artifact(
                    self.quest_setup_state,
                    self.quest_player_seat,
                    index,
                    saved.get("artifact_id"),
                )
        self._prefill_quest_loadout_from_import()
        self.quest_loadout_index = 0
        self._clear_loadout_drag()
        self.quest_loadout_detail_scroll = 0
        self.quest_loadout_summary_scroll = 0
        self.quest_local_ready = False
        self.quest_remote_ready = False
        self.route = "quest_loadout"

    def _start_ranked_quest_from_guild_party(self, party_index: int):
        parties = self._guild_parties()
        if not parties:
            return
        party_index = max(0, min(party_index, len(parties) - 1))
        party = parties[party_index]
        if len(party["members"]) < 6:
            return
        run_state = self._quest_run_state("ai")
        quest_id = f"quest-{self.rng.randint(100000, 999999)}"
        run_state["active"] = True
        run_state["quest_id"] = quest_id
        run_state["wins"] = 0
        run_state["losses"] = 0
        run_state["current_win_streak"] = 0
        run_state["current_loss_streak"] = 0
        run_state["opponent_glories"] = []
        run_state["team"] = self._normalize_quest_party_team(copy.deepcopy(party["members"]))
        run_state["party_id"] = party["name"]
        run_state["match_count"] = 0
        run_state["total_gold_earned"] = 0
        self.profile.ranked_current_quest_id = quest_id
        self.quest_context = "ranked"
        self.quest_opponent_mode = "ai"
        self._record_quested_adventurers([member["adventurer_id"] for member in run_state["team"]])
        self._sync_quest_run_cache(run_state)
        self._persist_profile()
        self._prepare_next_quest_encounter()

    def _auto_assemble_quest_party(self, favorite_id: str) -> list:
        """Pick 5 adventurers to join the favorite, applying a class-diversity constraint.

        Constraint: each of the 6 classes must be represented in the preferred_classes of
        at least 2 of the 6 adventurers.  Up to 50 random attempts are made; if none
        satisfy the constraint the last sample is used as a fallback.
        """
        all_classes = list(CLASS_SKILLS.keys())
        candidate_pool = [adv_id for adv_id in ADVENTURERS_BY_ID if adv_id != favorite_id]

        def adv_classes(adv_id: str) -> set:
            profile = ADVENTURER_AI.get(adv_id)
            return set(profile.preferred_classes) if profile else set()

        favorite_classes = adv_classes(favorite_id)
        pick_count = min(5, len(candidate_pool))
        fallback: list | None = None
        for _ in range(50):
            candidates = self.rng.sample(candidate_pool, pick_count)
            class_counts = {c: (1 if c in favorite_classes else 0) for c in all_classes}
            for adv_id in candidates:
                for c in adv_classes(adv_id):
                    if c in class_counts:
                        class_counts[c] += 1
            if fallback is None:
                fallback = candidates
            if all(count >= 2 for count in class_counts.values()):
                return [favorite_id] + candidates
        return [favorite_id] + (fallback or [])

    def _start_ranked_quest_from_favorite(self):
        if len(ADVENTURERS_BY_ID) < 6:
            return
        favorite_id = self._favorite_adventurer_id()
        self._reset_quest_run_state("ai")
        self.prepared_quest_id = None
        self.quest_context = "ranked"
        self.quest_opponent_mode = "ai"
        self.quest_player_seat = 1
        self.quest_draft_mode = "encounter"
        self.quest_draft_locked_id = favorite_id
        self.quest_selected_ids = self._auto_assemble_quest_party(favorite_id)
        self.quest_focus_id = favorite_id
        self.quest_offer_ids = []
        self.quest_enemy_party_ids = []
        self.quest_enemy_selected_ids = []
        self.quest_enemy_setup_members = []
        self.quest_draft_detail_scroll = 0
        self.quest_draft_offer_scroll = 0
        self.quest_setup_state = None
        self.quest_local_ready = False
        self.quest_remote_ready = False
        self.quest_team_import_open = False
        self.quest_team_import_text = ""
        self.quest_team_import_status_lines = []
        self.quest_imported_party_members = []
        self.quest_imported_party_name = ""
        self.route = "quest_party_reveal"

    def _start_training_builder(self):
        self._clear_loadout_drag()
        self.quest_context = "training"
        self.quest_opponent_mode = "ai"
        self.quest_player_seat = 1
        self.quest_draft_mode = "encounter"
        self.quest_draft_locked_id = None
        training_favorite_id = self._training_favorite_adventurer_id()
        self.quest_offer_ids = list(ADVENTURERS_BY_ID.keys())
        if training_favorite_id in self.quest_offer_ids:
            self.quest_offer_ids.remove(training_favorite_id)
            self.quest_offer_ids.insert(0, training_favorite_id)
        self.quest_focus_id = training_favorite_id if training_favorite_id in ADVENTURERS_BY_ID else (self.quest_offer_ids[0] if self.quest_offer_ids else None)
        self.quest_selected_ids = []
        self.quest_draft_offer_scroll = 0
        self.quest_enemy_party_ids = list(ADVENTURERS_BY_ID.keys())
        training_enemy_choice = choose_quest_party(
            self.quest_enemy_party_ids,
            enemy_party_ids=self.quest_offer_ids,
            difficulty="normal",
            rng=self.rng,
        )
        self.quest_enemy_selected_ids = list(training_enemy_choice.team_ids)
        self.quest_enemy_setup_members = self._team_from_loadout(training_enemy_choice.loadout)
        self.current_battle_opponent_glory = self.profile.reputation
        self.current_battle_ai_difficulties = {2: "normal"}
        self.current_battle_enemy_name = "Training Rival"
        self.quest_draft_detail_scroll = 0
        self.quest_team_import_open = False
        self.quest_team_import_status_lines = []
        self.quest_imported_party_members = []
        self.quest_imported_party_name = ""
        self.route = "quest_draft"

    def _prepare_next_quest_encounter(self, *, force_new: bool = False, route_if_ready: str = "quest_draft"):
        run_state = self._quest_run_state("ai")
        run_state["team"] = self._normalize_quest_party_team(run_state.get("team"))
        if not run_state.get("active") or run_state["team"] is None:
            self.route = "guild_hall"
            return
        if run_state.get("quest_id") is None:
            run_state["quest_id"] = f"quest-{self.rng.randint(100000, 999999)}"
        self.profile.ranked_current_quest_id = run_state["quest_id"]
        self.quest_context = "ranked"
        self.quest_opponent_mode = "ai"
        self.quest_player_seat = 1
        self.quest_draft_mode = "encounter"
        self.quest_draft_locked_id = None
        player_party_ids = [member["adventurer_id"] for member in run_state["team"]]
        self._record_quested_adventurers(player_party_ids)
        has_prepared_encounter = (
            not force_new
            and self.prepared_quest_id == run_state["quest_id"]
            and self.quest_offer_ids == list(player_party_ids)
            and len(self.quest_enemy_party_ids) == 6
            and len(self.quest_enemy_selected_ids) == 3
            and len(self.quest_enemy_setup_members) == 3
        )
        if has_prepared_encounter:
            self._sync_quest_run_cache(run_state)
            self.route = route_if_ready
            return
        self.quest_offer_ids = list(player_party_ids)
        match_profile = find_ai_match_profile(
            self.profile.reputation,
            run_state["current_win_streak"],
            run_state["current_loss_streak"],
            avg_opponent_reputation=self._quest_avg_opponent_glory("ai"),
            rng=self.rng,
        )
        difficulty = ai_difficulty_for_reputation(match_profile.reputation)
        all_adventurer_ids = list(ADVENTURERS_BY_ID.keys())
        # choose_quest_party requires a small pool (class-uniqueness constraint); sample 12
        # from the full roster so the enemy conceptually draws from anyone.
        candidate_pool = [adv_id for adv_id in all_adventurer_ids if adv_id not in player_party_ids]
        # assign_blind_quest_loadouts requires unique classes per adventurer (6 classes max)
        sample_size = min(6, len(candidate_pool))
        enemy_sample = self.rng.sample(candidate_pool, sample_size)
        enemy_choice = choose_quest_party(
            enemy_sample,
            enemy_party_ids=player_party_ids,
            difficulty=difficulty,
            rng=self.rng,
        )
        self.quest_enemy_party_ids = all_adventurer_ids
        self.quest_enemy_selected_ids = list(enemy_choice.team_ids)
        self.quest_enemy_setup_members = self._team_from_loadout(enemy_choice.loadout)
        self.quest_focus_id = self.quest_offer_ids[0] if self.quest_offer_ids else None
        self.quest_selected_ids = []
        self.quest_draft_detail_scroll = 0
        self.quest_draft_offer_scroll = 0
        self.quest_setup_state = None
        self.quest_party_loadout_state = None
        self.quest_team_import_open = False
        self.quest_team_import_text = ""
        self.quest_team_import_status_lines = []
        self.quest_imported_party_members = []
        self.quest_imported_party_name = ""
        self.current_battle_opponent_glory = match_profile.reputation
        self.current_battle_enemy_name = f"{rank_name(match_profile.reputation)} Rival"
        self.current_battle_ai_difficulties = {2: difficulty}
        self.prepared_quest_id = run_state["quest_id"]
        self._sync_quest_run_cache(run_state)
        self.route = route_if_ready

    def _start_quest_encounter(self):
        if self.quest_setup_state is None or not setup_is_ready(self.quest_setup_state):
            return
        difficulty = self.current_battle_ai_difficulties.get(2, "normal")
        if self.quest_context == "training":
            enemy_name = "Training Rival"
            opponent_glory = self.profile.reputation
        else:
            enemy_name = self.current_battle_enemy_name or "Ranked Rival"
            opponent_glory = self.current_battle_opponent_glory
        result_kind = "bout" if self.quest_context == "bout_random" else "quest"
        self._start_battle(
            self.quest_setup_state,
            result_kind,
            human_team_num=1,
            ai_difficulties={2: difficulty},
            second_picker=0,
            player_name="You",
            enemy_name=enemy_name,
            opponent_glory=opponent_glory,
        )

    def _bout_mode(self) -> dict:
        return BOUT_MODES[self.bout_mode_index]

    def _bout_opponent_name(self) -> str:
        if self.bout_opponent_mode == "lan":
            return "LAN Rival"
        return {
            "random": "Draft Rival",
            "focused": "Roster Challenger",
        }.get(self._bout_mode()["id"], "AI Rival")

    def _bout_ai_difficulty(self) -> str:
        mode_id = self._bout_mode()["id"]
        return {
            "random": "normal",
            "focused": "hard",
        }.get(mode_id, "normal")

    def _start_bout_series(self, mode: str):
        mode_index = next((i for i, m in enumerate(BOUT_MODES) if m["id"] == mode), 0)
        self.bout_mode_index = mode_index
        self.bout_opponent_mode = "ai"
        self.bout_player_seat = 1
        self.bout_ai_seat = 2
        self.bout_run = BoutRunState(active=True, mode=mode)
        self.bout_player_full_party = []
        self.bout_ai_full_party = []
        self.bout_player_artifact_pool = []
        if mode == "focused":
            self._start_focused_bout_selection()
        else:
            self._start_random_bout_setup()

    def _start_random_bout_setup(self):
        """Auto-assemble both parties for a Random Bout (Section 5.1)."""
        favorite_id = self._favorite_adventurer_id()
        # Player party: favorite + 5 random (class-diversity constraint)
        player_party = self._auto_assemble_quest_party(favorite_id)
        self.bout_player_full_party = player_party
        self.bout_player_artifact_pool = self._draw_quest_artifact_pool(player_party)
        # AI party: auto-assembled around a different random favorite
        all_ids = list(ADVENTURERS_BY_ID.keys())
        ai_candidates = [adv_id for adv_id in all_ids if adv_id not in player_party]
        ai_favorite = self.rng.choice(ai_candidates) if ai_candidates else all_ids[0]
        self.bout_ai_full_party = self._auto_assemble_quest_party(ai_favorite)
        # Set up teams for the encounter draft (choose 3 from 6 on each side)
        self.bout_player_seat = 1
        self.bout_ai_seat = 2
        # Use quest infrastructure: offer = player party, enemy = AI party
        self.quest_context = "bout_random"
        self.quest_opponent_mode = "ai"
        self.quest_player_seat = 1
        self.quest_draft_mode = "encounter"
        self.quest_draft_locked_id = None
        self.quest_offer_ids = list(player_party)
        self.quest_focus_id = player_party[0] if player_party else None
        self.quest_selected_ids = []
        self.quest_enemy_party_ids = list(self.bout_ai_full_party)
        # AI picks 3 from its party via choose_quest_party
        candidate_pool = [adv_id for adv_id in self.bout_ai_full_party]
        enemy_choice = choose_quest_party(
            candidate_pool[:6],
            enemy_party_ids=player_party,
            difficulty="normal",
            rng=self.rng,
        )
        self.quest_enemy_selected_ids = list(enemy_choice.team_ids)
        self.quest_enemy_setup_members = self._team_from_loadout(enemy_choice.loadout)
        self.quest_draft_detail_scroll = 0
        self.quest_draft_offer_scroll = 0
        self.quest_setup_state = None
        self.current_battle_ai_difficulties = {2: "normal"}
        self.current_battle_enemy_name = "AI Rival"
        self.route = "quest_draft"

    def _start_focused_bout_selection(self):
        """Focused Bout: player builds a party of 6 from the full roster (Section 5.2)."""
        all_ids = sorted(ADVENTURERS_BY_ID.keys())
        self.bout_pool_ids = all_ids
        self.bout_team1_ids = []
        self.bout_team2_ids = []
        self.bout_player_seat = self.rng.choice((1, 2))
        self.bout_ai_seat = 1 if self.bout_player_seat == 2 else 2
        self.bout_current_player = self.bout_player_seat
        self.bout_focus_id = self.bout_pool_ids[0]
        self.bout_draft_detail_scroll = 0
        self.route = "bout_draft"
        self._focus_next_available_bout_pick()

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
        # TODO: Focused Bout should pick 6, then choose 3 per encounter (Section 5.2)
        return len(self.bout_team1_ids) == 3 and len(self.bout_team2_ids) == 3

    def _record_bout_pick(self, seat: int, adventurer_id: str):
        if adventurer_id not in self._available_bout_ids():
            return
        focused = self._bout_mode()["id"] == "focused"
        if seat == 1:
            self.bout_team1_ids.append(adventurer_id)
            if not focused or len(self.bout_team1_ids) >= 3:
                self.bout_current_player = 2
        else:
            self.bout_team2_ids.append(adventurer_id)
            if not focused or len(self.bout_team2_ids) >= 3:
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
            opponent_glory=self.profile.reputation,
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
        if self.lan_context in {"quest", "training"}:
            self.quest_player_seat = 1 if self.lan_session.is_host else 2
            self.quest_opponent_mode = "lan"
            self.quest_context = "training" if self.lan_context == "training" else "ranked"
            if self.lan_session.is_host:
                self.quest_offer_ids = list(ADVENTURERS_BY_ID.keys()) if self.lan_context == "training" else draft_offer(6)
                self.lan_session.send(
                    {
                        "type": "quest_start",
                        "offer_ids": self.quest_offer_ids,
                        "host_reputation": self.profile.reputation,
                        "quest_context": self.quest_context,
                    }
                )
                self.quest_draft_mode = "encounter"
                self.quest_draft_locked_id = None
                self.quest_focus_id = self.quest_offer_ids[0]
                self.quest_selected_ids = []
                self.quest_draft_offer_scroll = 0
                self.route = "quest_draft"
        else:
            self.bout_player_seat = 1 if self.lan_session.is_host else 2
            self.bout_local_ready = False
            self.bout_remote_ready = False
            self._sync_bout_ready_flags()
            if self.lan_session.is_host:
                self.lan_session.send({"type": "bout_lobby", "host_reputation": self.profile.reputation, "mode": self._bout_mode()["id"]})
            self.route = "bout_lobby"

    def _confirm_lan_quest_loadout(self):
        if self.quest_setup_state is None or not setup_is_ready(self.quest_setup_state):
            return
        self.quest_local_ready = True
        local_team = copy.deepcopy(self.quest_setup_state[f"team{self.quest_player_seat}"])
        if self.quest_context == "ranked":
            run_state = self._quest_run_state("lan")
            run_state["team"] = copy.deepcopy(local_team)
            run_state["party_id"] = "|".join(member["adventurer_id"] for member in local_team)
            run_state["match_count"] = 0 if not run_state["active"] else run_state["match_count"]
            if not run_state["active"]:
                run_state["wins"] = 0
                run_state["losses"] = 0
                run_state["current_win_streak"] = 0
                run_state["current_loss_streak"] = 0
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
                    "client_reputation": self.profile.reputation,
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
        payload["host_reputation"] = self.profile.reputation
        self.lan_session.send(payload)
        self.quest_run_active = self._quest_run_state("lan")["active"] if self.quest_context == "ranked" else False
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
        mode_id = self._bout_mode()["id"]
        if mode_id == "focused":
            self.bout_pool_ids = sorted(ADVENTURERS_BY_ID.keys())
        else:
            self.bout_pool_ids = draft_offer(9)
        self.bout_team1_ids = []
        self.bout_team2_ids = []
        self.bout_current_player = 1
        self.bout_focus_id = self.bout_pool_ids[0]
        self.lan_session.send({
            "type": "bout_start",
            "pool_ids": self.bout_pool_ids,
            "host_reputation": self.profile.reputation,
            "mode": mode_id,
        })
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
                    "client_reputation": self.profile.reputation,
                }
            )

    def _start_lan_bout_battle(self):
        payload = serialize_setup_state(self.bout_setup_state)
        payload["type"] = "bout_battle_setup"
        payload["host_reputation"] = self.profile.reputation
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
                self.quest_draft_mode = "encounter"
                self.quest_draft_locked_id = None
                self.quest_offer_ids = list(message.get("offer_ids", []))
                self.quest_focus_id = self.quest_offer_ids[0] if self.quest_offer_ids else None
                self.quest_selected_ids = []
                self.quest_draft_offer_scroll = 0
                self.quest_context = str(message.get("quest_context", "ranked"))
                self.quest_opponent_mode = "lan"
                self.route = "quest_draft"
                continue
            if message_type == "quest_loadout" and self.lan_session.is_host:
                self.quest_remote_team = [dict(member) for member in message.get("members", [])]
                self.quest_remote_glory = int(message.get("client_reputation", self.profile.reputation))
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
                    opponent_glory=int(message.get("host_reputation", self.profile.reputation)),
                    use_lan=True,
                )
                continue
            if message_type == "bout_lobby":
                self.bout_player_seat = 2
                host_mode = str(message.get("mode", "random"))
                self.bout_mode_index = next((i for i, m in enumerate(BOUT_MODES) if m["id"] == host_mode), 0)
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
                recv_mode = str(message.get("mode", "random"))
                self.bout_mode_index = next((i for i, m in enumerate(BOUT_MODES) if m["id"] == recv_mode), 0)
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
                self.bout_remote_glory = int(message.get("client_reputation", self.profile.reputation))
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
                    opponent_glory=int(message.get("host_reputation", self.profile.reputation)),
                    use_lan=True,
                )

    @staticmethod
    def _hit(rect, pos):
        return rect is not None and rect.collidepoint(pos)
