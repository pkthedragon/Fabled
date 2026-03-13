"""
main.py – Fabled prototype entry point.
Two-player pass-and-play on one device.

Phase flow:
  menu
  → team_select_p1  (sub-phases: pick_adventurers → pick_sig × 3 → pick_basics × 3 → pick_item × 3)
  → pass_to_p2
  → team_select_p2  (same sub-phases)
  → round_start
  [→ extra_swap_p{N}  (round 1 initiative loser only)]
  → pass_to_select_p{init}
  → select_p{init}   (per-adventurer action selection)
  → pass_to_select_p{second}
  → select_p{second}
  → resolving        (both watch)
  → end_round
  → round_start  (loop)
  → result
"""
import sys
import random
import pygame

import battle_log
import net
import ai as _ai
from settings import *
from models import BattleState, CampaignProfile
from data import ROSTER, CLASS_BASICS, ITEMS
from logic import (
    create_team, start_new_round, determine_initiative,
    resolve_player_turn, resolve_queued_action, end_round,
    get_legal_targets, can_use_ability, do_swap,
    apply_passive_stats, can_act_this_round,
    get_legal_item_targets,
    get_subterfuge_swap_targets,
    apply_quest_rewards,
    apply_round_start_effects,
    make_combatant,
    describe_action,
)
do_end_round = end_round
from ui import (
    font, draw_text, draw_button, draw_panel,
    draw_main_menu, draw_team_select_screen, draw_pass_screen,
    draw_formation, draw_log, draw_action_menu, draw_target_prompt,
    draw_top_bar, draw_result_screen, draw_queued_summary,
    draw_combatant_detail,
    draw_campaign_mission_select, draw_quest_select,
    draw_pre_quest, draw_post_quest, draw_campaign_complete,
    draw_practice_menu, draw_teambuilder, draw_story_team_select,
    draw_settings_screen, draw_rename_overlay,
    draw_catalog,
    draw_pvp_mode_select, draw_lan_lobby,
    draw_status_tooltip, draw_import_modal, draw_tutorial_popup, draw_intro_popup,
    _wrap_text,
    SLOT_RECTS_P1, SLOT_RECTS_P2, LOG_RECT, ACTION_PANEL_RECT, BATTLE_DETAIL_RECT,
)
from campaign_data import QUEST_TABLE, MISSION_TABLE, build_quest_enemy_team
from campaign_save import save_campaign, load_campaign


# ─────────────────────────────────────────────────────────────────────────────
# GAME CLASS
# ─────────────────────────────────────────────────────────────────────────────

class Game:
    def __init__(self):
        pygame.init()
        # Fullscreen at native resolution; all game logic uses the 1400×900 canvas.
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        try:
            pygame.scrap.init()
        except Exception:
            pass
        self._native_w, self._native_h = self.screen.get_size()
        self._canvas = pygame.Surface((WIDTH, HEIGHT))
        # Pre-compute scale and letterbox offset.
        scale = min(self._native_w / WIDTH, self._native_h / HEIGHT)
        self._scale = scale
        scaled_w = int(WIDTH  * scale)
        scaled_h = int(HEIGHT * scale)
        self._canvas_offset = (
            (self._native_w - scaled_w) // 2,
            (self._native_h - scaled_h) // 2,
        )
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        self.phase = "menu"
        self.battle: BattleState = None
        self.game_mode = "pvp"  # "pvp" | "single_player" | "campaign"
        self.ai_player = 2
        self.ai_comp_name = None

        # Campaign state
        self.campaign_profile: CampaignProfile = load_campaign()
        if not self.campaign_profile.quest_cleared.get(0):
            apply_quest_rewards(self.campaign_profile, 0, notify=False)
            save_campaign(self.campaign_profile)
        self.campaign_quest_id: int = 0
        self.campaign_mission_id: int = 1
        self._last_campaign_btns = None
        self._campaign_won_quest = False

        # New teambuilder / story-team state
        self._editing_team_slot: int = None
        self._editing_single_member: bool = False  # True when editing one member's sets only
        self._editing_from_roster: bool = False    # True when editing sets jumped from pick_adventurers
        self._focused_slot: int = None             # slot shown in detail panel (not yet editing)
        self._edit_sets_backup: dict = None        # backup of sig/basics/item before Edit Sets

        # Import modal state
        self._import_modal_open: bool = False
        self._import_modal_text: str = ""
        self._import_modal_error: str = ""
        self._last_import_modal_clicks: dict = {}
        self._story_team_idx: int = None
        self._last_practice_btns = None
        self._last_teambuilder_btns = None
        self._last_story_team_btns = None
        self._teambuilder_return_phase = "menu"  # where back_btn in teambuilder leads

        # Rename overlay state (drawn on top of teambuilder)
        self._renaming_team_slot: int = None
        self._rename_text: str = ""
        self._last_rename_overlay_btns = None

        # Tutorial popup state
        self._tutorial_pending: str = None
        self._practice_tutorials_seen: "Set[str]" = set()

        # Intro story popup state
        self._intro_visible: int = 0     # 0 = hidden; 1–4 = sections shown
        self._intro_timer: float = 0.0   # countdown before showing
        self._intro_lets_go_btn = None
        if (self.campaign_profile
                and self.campaign_profile.tutorials_enabled
                and "intro" not in self.campaign_profile.tutorial_seen):
            self._intro_timer = 1.0
            self.campaign_profile.tutorial_seen.add("intro")
            save_campaign(self.campaign_profile)

        # Settings state
        self._last_settings_btns = None
        self._confirm_reset: bool = False

        # Catalog state
        self._catalog_tab = "adventurers"
        self._catalog_selected = None
        self._catalog_scroll = 0
        self._last_catalog_btns = None
        self._catalog_filters = {
            "adventurers": {"classes": set(), "damage_types": set()},
            "basics":      {"classes": set(), "types": set()},
            "items":       {"types": set()},
        }

        # Pre-battle review state
        self._pre_battle_picks = []
        self._pre_battle_slot_selected = None
        self._last_pre_battle_btns = None

        # Pre-battle edit state
        self._pbe_enemy_picks = []
        self._pbe_back_phase = "menu"
        self._lan_pbe_local_ready = False
        self._lan_pbe_opponent_ready = False

        # Ticker queue (new battle flow)
        self._tk            = []     # ticker queue: list of step dicts
        self._tk_timer      = 0.0    # seconds remaining for current text step
        self._tk_msg        = ""     # current bottom-bar text
        self._tk_overlay_msg = ""   # centered overlay box text (round start etc.)
        self._tk_btn_label  = None   # None = timer; str = show pass button with this label
        self._tk_btn_rect   = None   # pygame.Rect, set during draw

        # LAN state
        self._lan = None                    # LANHost or LANClient
        self._lan_role = None               # "host" | "client"
        self._lan_ip_input = ""             # IP being typed (client)
        self._lan_ip_active = False         # IP text field focused
        self._lan_status = ""               # status shown in lobby
        self._lan_p1_ready = False          # host team built
        self._lan_p2_ready = False          # client team received
        self._lan_disconnected = False
        self._last_pvp_mode_btns = None
        self._last_lan_lobby_btns = None

        # Team building state
        self.building_player = 1
        self.sub_phase = "pick_adventurers"
        self.roster_selected = None      # index in ROSTER
        self.team_picks = []             # list of partial dicts
        self.current_adv_idx = 0         # which adventurer in team_picks we're configuring
        self.sig_choice = None           # index in defn.sig_options
        self.basic_choices = []          # list of indices into CLASS_BASICS[cls]
        self.item_choice = None          # index in ITEMS
        self.team_slot_selected = None   # index 0-2 for reorder drag-by-click
        self.team_select_scroll = 0      # detail list scroll offset for basics/items
        self.battle_log_scroll = 0       # battle log scroll offset (0 = bottom)
        self.p1_picks = None
        self.p2_picks = None

        # Action selection state
        self.selecting_player = 1
        self.selection_order = []        # slots in clockwise order that still need an action
        self.current_actor = None        # CombatantState currently being assigned
        self.pending_action = None       # partially-built action dict
        self.selection_sub = "pick_action"  # "pick_action" | "pick_target"

        # Resolution step
        self.resolve_step = 0
        self.resolve_done = False

        # Extra-action phase (Rabbit Hole pre-planned / Stitch In Time post-resolve)
        self.current_is_extra = False       # True when filling queued2 for extra action
        self._extra_action_queue = []       # list of (player_num, unit) for Stitch In Time

        # Battle start / end-of-round / initiative screens
        self._last_battle_start_btn = None
        self._last_eor_btn = None
        self._last_init_result_btn = None
        self._completed_round_num = 0   # round that just finished (for end_of_round display)

        # Per-player resolution tracking
        self._resolving_player = None       # which player's turn is being resolved
        self._init_player_resolved = False  # True after init player resolves, before second selects

        # Per-action step-through during resolution
        self._action_step_queue = []        # list of (unit, player_num, is_queued2)
        self._action_step_unit = None       # unit whose action just resolved
        self._action_step_player = None     # player_num for the current step batch
        self._action_log_start = 0          # log length before the current action resolved

        # Detail panel
        self._detail_unit = None            # unit whose card is currently shown
        self._detail_close_btn = None       # close button rect for the detail panel

        # Curated AI draft pool (meta-style lineups)
        self._ai_team_pool = [
            {
                "name": "Expose Focus",
                "members": [
                    {"defn": "prince_charming",      "sig": "condescend",      "basics": ["impose", "command"],       "item": "family_seal"},
                    {"defn": "lucky_constantine",    "sig": "feline_gambit",   "basics": ["post_bounty", "sucker_punch"], "item": "holy_diadem"},
                    {"defn": "robin_hooded_avenger", "sig": "snipe_shot",      "basics": ["hunters_mark", "hunters_badge"], "item": "arcane_focus"},
                ],
            },
            {
                "name": "Shock Punish",
                "members": [
                    {"defn": "sir_roland",           "sig": "knights_challenge","basics": ["shield_bash", "stalwart"], "item": "spiked_mail"},
                    {"defn": "hunold_the_piper",     "sig": "haunting_rhythm", "basics": ["sucker_punch", "fleetfooted"], "item": "family_seal"},
                    {"defn": "march_hare",           "sig": "tempus_fugit",    "basics": ["thunder_call", "arcane_wave"], "item": "lightning_boots"},
                ],
            },
            {
                "name": "Root Lock",
                "members": [
                    {"defn": "green_knight",         "sig": "heros_bargain",   "basics": ["edict", "command"],        "item": "iron_buckler"},
                    {"defn": "briar_rose",           "sig": "thorn_snare",     "basics": ["trapping_blow", "hunters_badge"], "item": "misericorde"},
                    {"defn": "rapunzel",             "sig": "golden_snare",    "basics": ["edict", "decree"],         "item": "holy_diadem"},
                ],
            },
            {
                "name": "Burn Pressure",
                "members": [
                    {"defn": "gretel",               "sig": "hot_mitts",       "basics": ["cleave", "intimidate"],    "item": "family_seal"},
                    {"defn": "witch_of_the_woods",   "sig": "cauldron_bubble", "basics": ["fire_blast", "breakthrough"], "item": "misericorde"},
                    {"defn": "matchstick_liesl",     "sig": "cauterize",       "basics": ["heal", "protection"],      "item": "heart_amulet"},
                ],
            },
            {
                "name": "Tank Sustain",
                "members": [
                    {"defn": "porcus_iii",           "sig": "porcine_honor",   "basics": ["shield_bash", "stalwart"], "item": "spiked_mail"},
                    {"defn": "aldric_lost_lamb",     "sig": "benefactor",      "basics": ["heal", "protection"],      "item": "heart_amulet"},
                    {"defn": "lady_of_reflections",  "sig": "lakes_gift",      "basics": ["condemn", "armored"],      "item": "crafty_shield"},
                ],
            },
            {
                "name": "Last-Stand Brawler",
                "members": [
                    {"defn": "risa_redcloak",        "sig": "blood_hunt",      "basics": ["rend", "feint"],           "item": "vampire_fang"},
                    {"defn": "porcus_iii",           "sig": "not_by_the_hair", "basics": ["shield_bash", "armored"],  "item": "iron_buckler"},
                    {"defn": "snowkissed_aurora",    "sig": "toxin_purge",     "basics": ["heal", "medic"],           "item": "heart_amulet"},
                ],
            },
            {
                "name": "Speed Tempo",
                "members": [
                    {"defn": "little_jack",          "sig": "skyfall",         "basics": ["cleave", "feint"],         "item": "family_seal"},
                    {"defn": "march_hare",           "sig": "rabbit_hole",     "basics": ["arcane_wave", "thunder_call"], "item": "lightning_boots"},
                    {"defn": "frederic",             "sig": "on_the_hunt",     "basics": ["hunters_mark", "hunters_badge"], "item": "main_gauche"},
                ],
            },
            {
                "name": "Swap Punish",
                "members": [
                    {"defn": "briar_rose",           "sig": "garden_of_thorns","basics": ["trapping_blow", "volley"], "item": "misericorde"},
                    {"defn": "green_knight",         "sig": "natural_order",   "basics": ["summons", "edict"],        "item": "family_seal"},
                    {"defn": "reynard",              "sig": "cutpurse",        "basics": ["sneak_attack", "fleetfooted"], "item": "smoke_bomb"},
                ],
            },
            {
                "name": "Safe Mage Shell",
                "members": [
                    {"defn": "sir_roland",           "sig": "shimmering_valor","basics": ["shield_bash", "armored"],  "item": "spiked_mail"},
                    {"defn": "ashen_ella",           "sig": "fae_blessing",    "basics": ["fire_blast", "arcane_wave"], "item": "holy_diadem"},
                    {"defn": "snowkissed_aurora",    "sig": "birdsong",        "basics": ["heal", "medic"],           "item": "heart_amulet"},
                ],
            },
            {
                "name": "Backline Hunter",
                "members": [
                    {"defn": "prince_charming",      "sig": "gallant_charge",  "basics": ["impose", "summons"],       "item": "main_gauche"},
                    {"defn": "robin_hooded_avenger", "sig": "bring_down",      "basics": ["hawkshot", "hunters_badge"], "item": "family_seal"},
                    {"defn": "lucky_constantine",    "sig": "subterfuge",      "basics": ["post_bounty", "sneak_attack"], "item": "lightning_boots"},
                ],
            },
            {
                "name": "Malice Growth",
                "members": [
                    {"defn": "pinocchio",            "sig": "become_real",     "basics": ["dark_grasp", "cursed_armor"], "item": "family_seal"},
                    {"defn": "rumpelstiltskin",      "sig": "straw_to_gold",   "basics": ["soul_gaze", "blood_pact"],  "item": "arcane_focus"},
                    {"defn": "prince_charming",      "sig": "chosen_one",      "basics": ["decree", "summons"],       "item": "holy_diadem"},
                ],
            },
            {
                "name": "Anti-Heal Pressure",
                "members": [
                    {"defn": "gretel",               "sig": "shove_over",      "basics": ["intimidate", "strike"],    "item": "misericorde"},
                    {"defn": "matchstick_liesl",     "sig": "cauterize",       "basics": ["heal", "protection"],      "item": "heart_amulet"},
                    {"defn": "robin_hooded_avenger", "sig": "snipe_shot",      "basics": ["hunters_mark", "hawkshot"], "item": "arcane_focus"},
                ],
            },
            {
                "name": "Reflection Punish",
                "members": [
                    {"defn": "lady_of_reflections",  "sig": "drown_in_the_loch","basics": ["condemn", "stalwart"],    "item": "spiked_mail"},
                    {"defn": "reynard",              "sig": "feign_weakness",  "basics": ["riposte", "fleetfooted"],  "item": "holy_diadem"},
                    {"defn": "sir_roland",           "sig": "banner_of_command","basics": ["shield_bash", "armored"], "item": "crafty_shield"},
                ],
            },
            {
                "name": "Noble Midrange",
                "members": [
                    {"defn": "prince_charming",      "sig": "chosen_one",      "basics": ["decree", "summons"],       "item": "family_seal"},
                    {"defn": "green_knight",         "sig": "awaited_blow",    "basics": ["edict", "command"],        "item": "iron_buckler"},
                    {"defn": "rapunzel",             "sig": "ivory_tower",     "basics": ["impose", "decree"],        "item": "holy_diadem"},
                ],
            },
            {
                "name": "Status Spread",
                "members": [
                    {"defn": "witch_of_the_woods",   "sig": "toil_and_trouble","basics": ["fire_blast", "thunder_call"], "item": "misericorde"},
                    {"defn": "hunold_the_piper",     "sig": "dying_dance",     "basics": ["sucker_punch", "fleetfooted"], "item": "arcane_focus"},
                    {"defn": "briar_rose",           "sig": "creeping_doubt",  "basics": ["trapping_blow", "hunters_mark"], "item": "family_seal"},
                ],
            },
            {
                "name": "Balanced Generalist",
                "members": [
                    {"defn": "frederic",             "sig": "heros_charge",    "basics": ["hunters_mark", "hunters_badge"], "item": "family_seal"},
                    {"defn": "snowkissed_aurora",    "sig": "dictate_of_nature","basics": ["heal", "medic"],           "item": "heart_amulet"},
                    {"defn": "prince_charming",      "sig": "condescend",      "basics": ["impose", "command"],       "item": "main_gauche"},
                ],
            },
        ]

    def _is_single_player(self):
        return self.game_mode in ("single_player", "campaign")

    def _maybe_show_tutorial(self, key: str, text: str):
        """Show a tutorial popup if it hasn't been seen yet. Only fires in single-player/campaign."""
        if not self._is_single_player():
            return
        if self.campaign_profile:
            if not self.campaign_profile.tutorials_enabled:
                return
            if key in self.campaign_profile.tutorial_seen:
                return
            self.campaign_profile.tutorial_seen.add(key)
            save_campaign(self.campaign_profile)
        else:
            if key in self._practice_tutorials_seen:
                return
            self._practice_tutorials_seen.add(key)
        self._tutorial_pending = text

    def _maybe_inject_battle_tutorials(self) -> list:
        """Return ticker steps for any first-time battle tutorials that should now fire."""
        if not self._is_single_player() or not self.battle:
            return []
        if self.campaign_profile and not self.campaign_profile.tutorials_enabled:
            return []
        seen = (self.campaign_profile.tutorial_seen
                if self.campaign_profile else self._practice_tutorials_seen)
        steps = []
        all_units = self.battle.team1.members + self.battle.team2.members
        if "status_condition" not in seen and any(u.statuses for u in all_units):
            steps.append({"k": "status_condition_tutorial"})
        if "stat_mod" not in seen and any(u.buffs or u.debuffs for u in all_units):
            steps.append({"k": "stat_mod_tutorial"})
        return steps

    # ─────────────────────────────────────────────────────────────────────────
    # LAN HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _is_lan(self) -> bool:
        return self.game_mode in ("lan_host", "lan_client")

    def _lan_my_player(self) -> int:
        return 1 if self.game_mode == "lan_host" else 2

    def _lan_send(self, msg: dict):
        if self._lan:
            self._lan.send(msg)

    def _serialize_picks(self, picks: list) -> list:
        result = []
        for p in picks:
            result.append({
                "adv_id": p["definition"].id,
                "sig_id": p["signature"].id,
                "basics": [b.id for b in p["basics"]],
                "item_id": p["item"].id,
            })
        return result

    def _deserialize_picks(self, data: list) -> list:
        roster_by_id = {d.id: d for d in ROSTER}
        items_by_id = {i.id: i for i in ITEMS}
        picks = []
        for m in data:
            defn = roster_by_id[m["adv_id"]]
            sig = next(a for a in defn.sig_options if a.id == m["sig_id"])
            basics_pool = CLASS_BASICS[defn.cls]
            basics = [next(a for a in basics_pool if a.id == bid) for bid in m["basics"]]
            item = items_by_id[m["item_id"]]
            picks.append({"definition": defn, "signature": sig, "basics": basics, "item": item})
        return picks

    def _serialize_unit(self, u) -> dict:
        return {
            "hp": u.hp, "ko": u.ko, "slot": u.slot,
            "statuses": [{"kind": s.kind, "duration": s.duration} for s in u.statuses],
            "buffs": [{"stat": b.stat, "amount": b.amount, "duration": b.duration} for b in u.buffs],
            "debuffs": [{"stat": d.stat, "amount": d.amount, "duration": d.duration} for d in u.debuffs],
            "acted": u.acted, "must_recharge": u.must_recharge, "twist_used": u.twist_used,
            "item_uses_left": u.item_uses_left, "ranged_uses": u.ranged_uses,
            "ability_charges": dict(u.ability_charges), "max_hp_bonus": u.max_hp_bonus,
            "extra_actions_next": u.extra_actions_next, "extra_actions_now": u.extra_actions_now,
            "retaliate_power": u.retaliate_power, "valor_rounds": u.valor_rounds,
            "untargetable": u.untargetable, "cant_act": u.cant_act,
            "dmg_reduction": u.dmg_reduction,
            "last_status_inflicted": getattr(u, "last_status_inflicted", ""),
        }

    def _apply_unit_state(self, u, d: dict):
        from models import StatusInstance, StatMod
        u.hp = d["hp"]; u.ko = d["ko"]; u.slot = d["slot"]
        u.statuses = [StatusInstance(kind=s["kind"], duration=s["duration"]) for s in d["statuses"]]
        u.buffs = [StatMod(stat=b["stat"], amount=b["amount"], duration=b["duration"]) for b in d["buffs"]]
        u.debuffs = [StatMod(stat=db["stat"], amount=db["amount"], duration=db["duration"]) for db in d["debuffs"]]
        u.acted = d["acted"]; u.must_recharge = d["must_recharge"]; u.twist_used = d["twist_used"]
        u.item_uses_left = d["item_uses_left"]; u.ranged_uses = d["ranged_uses"]
        u.ability_charges = d["ability_charges"]; u.max_hp_bonus = d["max_hp_bonus"]
        u.extra_actions_next = d["extra_actions_next"]; u.extra_actions_now = d["extra_actions_now"]
        u.retaliate_power = d["retaliate_power"]; u.valor_rounds = d["valor_rounds"]
        u.untargetable = d["untargetable"]; u.cant_act = d["cant_act"]
        u.dmg_reduction = d["dmg_reduction"]
        u.last_status_inflicted = d.get("last_status_inflicted", "")

    def _serialize_action(self, action: dict, slot_idx: int, team, enemy, is_extra: bool) -> dict:
        atype = action.get("type", "skip")
        d = {"slot_idx": slot_idx, "atype": atype, "is_extra": is_extra}
        if atype == "ability":
            d["ability_id"] = action["ability"].id
            target = action.get("target")
            if target is not None:
                if target in team.members:
                    d["target_team"] = "own"
                    d["target_slot_idx"] = team.members.index(target)
                else:
                    d["target_team"] = "enemy"
                    d["target_slot_idx"] = enemy.members.index(target)
            swap_target = action.get("swap_target")
            if swap_target is not None:
                d["swap_target_slot_idx"] = enemy.members.index(swap_target)
        elif atype == "swap":
            target = action.get("target")
            if target is not None:
                d["target_slot_idx"] = team.members.index(target)
        elif atype == "item":
            target = action.get("target")
            if target is not None:
                if target in team.members:
                    d["target_team"] = "own"
                    d["target_slot_idx"] = team.members.index(target)
                else:
                    d["target_team"] = "enemy"
                    d["target_slot_idx"] = enemy.members.index(target)
        return d

    def _deserialize_action(self, data: dict, team, enemy) -> dict:
        atype = data["atype"]
        action = {"type": atype}
        if atype == "ability":
            actor = team.members[data["slot_idx"]]
            all_abs = actor.basics + [actor.sig, actor.defn.twist]
            ability = next((a for a in all_abs if a.id == data["ability_id"]), None)
            if ability:
                action["ability"] = ability
            if "target_slot_idx" in data:
                t_team = team if data.get("target_team") == "own" else enemy
                action["target"] = t_team.members[data["target_slot_idx"]]
            if "swap_target_slot_idx" in data:
                action["swap_target"] = enemy.members[data["swap_target_slot_idx"]]
        elif atype == "swap":
            if "target_slot_idx" in data:
                action["target"] = team.members[data["target_slot_idx"]]
        elif atype == "item":
            if "target_slot_idx" in data:
                t_team = team if data.get("target_team") == "own" else enemy
                action["target"] = t_team.members[data["target_slot_idx"]]
        return action

    def _lan_send_state(self, *, phase: str, extra: dict = None):
        """Serialize current battle state and send to client (host only)."""
        if not self.battle or self.game_mode != "lan_host":
            return
        msg = {
            "type": "state_update",
            "phase": phase,
            "round_num": self.battle.round_num,
            "winner": self.battle.winner,
            "init_player": self.battle.init_player,
            "init_reason": getattr(self.battle, "init_reason", ""),
            "swap_used_this_turn": self.battle.swap_used_this_turn,
            "completed_round_num": self._completed_round_num,
            "log": list(self.battle.log),
            "team1": [self._serialize_unit(u) for u in self.battle.team1.members],
            "team2": [self._serialize_unit(u) for u in self.battle.team2.members],
        }
        if extra:
            msg.update(extra)
        self._lan_send(msg)

    def _lan_tick(self):
        """Called every frame: drain incoming messages and check connection status."""
        if not self._lan:
            return
        # Check for new host connection
        if (self.phase == "lan_lobby" and self.game_mode == "lan_host"
                and self._lan.connected
                and not getattr(self, "_lan_host_notified", False)):
            self._lan_host_notified = True
            self._lan_status = "Opponent connected! Building your party..."
            self._start_team_select(1)

        # Check for client connection success
        if (self.phase == "lan_lobby" and self.game_mode == "lan_client"
                and isinstance(self._lan, net.LANClient)
                and self._lan.connected
                and not getattr(self, "_lan_client_notified", False)):
            self._lan_client_notified = True
            self._lan_status = "Connected! Building your party..."
            self._start_team_select(2)  # Client picks P2's team

        if (self.phase == "lan_lobby" and self.game_mode == "lan_client"
                and isinstance(self._lan, net.LANClient)
                and self._lan.error
                and not self._lan._connecting):
            self._lan_status = f"Connection failed: {self._lan.error}"
            self._lan.error = ""  # Clear so it doesn't repeat

        for msg in self._lan.poll():
            self._handle_lan_message(msg)

    def _handle_lan_message(self, msg: dict):
        mtype = msg.get("type")
        if mtype == "_disconnect":
            self._lan_disconnected = True
            return
        if self.game_mode == "lan_host":
            self._handle_lan_host_msg(msg)
        elif self.game_mode == "lan_client":
            self._handle_lan_client_msg(msg)

    def _handle_lan_host_msg(self, msg: dict):
        mtype = msg.get("type")
        if mtype == "team_ready":
            self.p2_picks = self._deserialize_picks(msg["picks"])
            self._lan_p2_ready = True
            if self._lan_p1_ready:
                self._enter_pre_battle_edit(self.p1_picks, self.p2_picks, None)
                # Tell client to enter pre_battle_edit (client=p2, enemy=p1)
                self._lan_send({
                    "type": "pre_battle_start",
                    "p1_picks": self._serialize_picks(self.p1_picks),
                    "p2_picks": self._serialize_picks(self.p2_picks),
                })
            # If host not ready yet, they'll enter pre_battle_edit when they finish (and send msg)

        elif mtype == "pre_battle_ready":
            self._lan_pbe_opponent_ready = True
            if self._lan_pbe_local_ready:
                self._start_lan_battle()

        elif mtype == "actions_ready":
            if self.phase != "select_actions" or self.selecting_player != 2:
                return
            team2 = self.battle.team2
            team1 = self.battle.team1
            # Clear P2 queues
            for u in team2.members:
                u.queued = None
                u.queued2 = None
            self.battle.swap_used_this_turn = False
            self.current_is_extra = False
            # Apply received actions
            for adata in msg.get("actions", []):
                slot_idx = adata["slot_idx"]
                actor = team2.members[slot_idx]
                self.current_is_extra = adata.get("is_extra", False)
                self.current_actor = actor
                action = self._deserialize_action(adata, team2, team1)
                action["queued_from_slot"] = actor.slot
                if self.current_is_extra:
                    if actor.queued2 is None:
                        actor.queued2 = action
                else:
                    if actor.queued is None:
                        actor.queued = action
            self.current_is_extra = False
            self.current_actor = None
            # Trigger resolution for P2
            self._resolving_player = 2
            self.phase = "battle"

        elif mtype == "extra_swap_ready":
            slot_a = msg.get("slot_a")
            slot_b = msg.get("slot_b")
            if slot_a is not None and slot_b is not None:
                team = self.battle.team2
                do_swap(team.members[slot_a], team.members[slot_b], team, self.battle)
            # Return to ticker — it has the remaining round steps (select, resolve, etc.) queued
            self.phase = "battle"

    def _handle_lan_client_msg(self, msg: dict):
        mtype = msg.get("type")
        if mtype == "battle_ready":
            self.p1_picks = self._deserialize_picks(msg["p1_picks"])
            self.p2_picks = self._deserialize_picks(msg["p2_picks"])
            self._start_battle()

        elif mtype == "pre_battle_start":
            # Host signals both teams built: client enters pre_battle_edit
            self.p1_picks = self._deserialize_picks(msg["p1_picks"])
            self.p2_picks = self._deserialize_picks(msg["p2_picks"])
            # Client is p2, enemy is p1
            self._enter_pre_battle_edit(self.p2_picks, self.p1_picks, None)

        elif mtype == "pre_battle_ready":
            self._lan_pbe_opponent_ready = True
            if self._lan_pbe_local_ready:
                self._start_battle()

        elif mtype == "state_update":
            if not self.battle:
                return
            # Apply unit states
            for i, udata in enumerate(msg.get("team1", [])):
                if i < len(self.battle.team1.members):
                    self._apply_unit_state(self.battle.team1.members[i], udata)
            for i, udata in enumerate(msg.get("team2", [])):
                if i < len(self.battle.team2.members):
                    self._apply_unit_state(self.battle.team2.members[i], udata)
            # Update metadata
            self.battle.round_num = msg.get("round_num", self.battle.round_num)
            self.battle.winner = msg.get("winner", self.battle.winner)
            self.battle.swap_used_this_turn = msg.get("swap_used_this_turn", False)
            self.battle.init_player = msg.get("init_player", self.battle.init_player)
            self.battle.init_reason = msg.get("init_reason", getattr(self.battle, "init_reason", ""))
            new_log = msg.get("log")
            if new_log is not None:
                self.battle.log = new_log
            # Update phase
            new_phase = msg.get("phase")
            if not new_phase:
                return
            selecting_player = msg.get("selecting_player", 0)
            if new_phase == "select_actions" and selecting_player == 2:
                # Client's turn to pick actions
                self.selecting_player = 2
                team = self.battle.team2
                self.selection_order = []
                for slot in CLOCKWISE_ORDER:
                    unit = team.get_slot(slot)
                    if unit and not unit.ko:
                        self.selection_order.append((unit, False))
                        if unit.extra_actions_now > 0:
                            self.selection_order.append((unit, True))
                for unit in team.members:
                    unit.queued = None
                    unit.queued2 = None
                self.battle.swap_used_this_turn = False
                self.current_is_extra = False
                self._init_player_resolved = False
                self.phase = "select_actions"
                self._advance_selection()
            elif new_phase == "extra_swap_p2":
                self.phase = "extra_swap_p2"
                self._init_extra_swap(2)
            elif new_phase == "battle":
                self.phase = "battle"
                # Advance past any pending pass button
                self._tk_btn_label = None
                self._tk_btn_rect  = None
            elif new_phase == "end_of_round":
                self._completed_round_num = msg.get("completed_round_num", 0)
                self.phase = "end_of_round"
            elif new_phase == "result":
                battle_log.close()
                self.phase = "result"
            else:
                self.selecting_player = selecting_player or self.selecting_player
                self.phase = new_phase

    def _start_lan_battle(self):
        """Host: both teams received, start battle and send to client."""
        self._start_battle()
        self._lan_send({
            "type": "battle_ready",
            "p1_picks": self._serialize_picks(self.p1_picks),
            "p2_picks": self._serialize_picks(self.p2_picks),
        })
        self._lan_send_state(phase="battle_start")

    def _is_ai_player(self, player_num: int) -> bool:
        return self._is_single_player() and player_num == self.ai_player

    def _build_ai_pick(self, entry):
        by_id = {d.id: d for d in ROSTER}
        items_by_id = {i.id: i for i in ITEMS}
        defn = by_id[entry["defn"]]
        sig = next(a for a in defn.sig_options if a.id == entry["sig"])
        basics_pool = CLASS_BASICS[defn.cls]
        basics = [next(a for a in basics_pool if a.id == bid) for bid in entry["basics"]]
        item = items_by_id[entry["item"]]
        return {
            "definition": defn,
            "signature": sig,
            "basics": basics,
            "item": item,
        }

    def _generate_ai_team(self):
        comp = random.choice(self._ai_team_pool)
        picks = [self._build_ai_pick(e) for e in comp["members"]]
        return comp["name"], picks

    def _ai_pick_extra_swap(self, player_num):
        team = self.battle.get_team(player_num)
        front = team.frontline()
        if not front:
            return False
        backliners = [u for u in team.alive() if u.slot != SLOT_FRONT]
        if not backliners:
            return False
        strongest = max(backliners, key=lambda u: u.get_stat("defense") + u.get_stat("attack"))
        if strongest.get_stat("defense") > front.get_stat("defense") + 5:
            do_swap(front, strongest, team, self.battle)
            return True
        return False

    def _ai_queue_current_actor_action(self):
        actor = self.current_actor
        if actor is None or actor.ko:
            return False
        best_action = _ai.pick_action(
            self.battle,
            self.selecting_player,
            actor,
            self.current_is_extra,
            self.battle.swap_used_this_turn,
            self._swap_queued_this_turn(),
        )
        self._set_queued(actor, best_action)
        return True

    def _auto_continue_resolve_done(self):
        self._detail_unit = None
        if self.battle.winner:
            battle_log.close()
            if self.game_mode == "lan_host":
                self._lan_send_state(phase="result")
            if self.game_mode == "campaign":
                self._campaign_won_quest = (self.battle.winner == 1)
                self.phase = "campaign_post_quest"
            else:
                self.phase = "result"
        elif self._init_player_resolved:
            second = 3 - self.battle.init_player
            self._enter_action_selection(second)
            # _enter_action_selection sends state to client when second==2
        else:
            apply_passive_stats(self.battle.team1, self.battle)
            apply_passive_stats(self.battle.team2, self.battle)
            # round_num was already incremented by end_round; the completed round is one less
            self._completed_round_num = self.battle.round_num - 1
            determine_initiative(self.battle)
            self.phase = "end_of_round"
            if self.game_mode == "lan_host":
                self._lan_send_state(phase="end_of_round")

    def _maybe_auto_progress(self):
        if not self._is_single_player() and not self._is_lan():
            return
        if not self._is_single_player() and not self.battle and self.phase != "menu":
            return

        progressed = True
        safety = 0
        while progressed and safety < 10:
            safety += 1
            progressed = False
            p = self.phase

            # LAN-specific auto-progress
            if self._is_lan() and p == "resolve_done":
                self._auto_continue_resolve_done()
                progressed = True
                continue
            if self._is_lan() and p.startswith("pass_to_"):
                self._advance_from_pass()
                progressed = True
                continue

            # LAN extra-swap for AI (LAN compatibility)
            if p.startswith("extra_swap_p") and self._is_ai_player(self._extra_swap_player) and self._is_lan():
                swapped = self._ai_pick_extra_swap(self._extra_swap_player)
                if not swapped:
                    self.battle.log_add(f"P{self._extra_swap_player} passed on free swap.")
                self._enter_action_selection(self.battle.init_player)
                progressed = True
                continue

            # select_actions AI (for LAN compatibility)
            if p == "select_actions" and self._is_ai_player(self.selecting_player):
                while self.phase == "select_actions" and self.current_actor is not None and self.selecting_player == self.ai_player:
                    actor = self.current_actor
                    already_queued = actor.queued2 is not None if self.current_is_extra else actor.queued is not None
                    if already_queued:
                        self._on_action_queued()
                        continue
                    if not self._ai_queue_current_actor_action():
                        self._set_queued(self.current_actor, {"type": "skip"})
                    self._on_action_queued()
                progressed = True
                continue

            # extra_action_p AI (for LAN compatibility)
            if p.startswith("extra_action_p") and self._is_ai_player(self.selecting_player) and self._is_lan():
                if self.current_actor and self.current_actor.queued2 is None:
                    if not self._ai_queue_current_actor_action():
                        self._set_queued(self.current_actor, {"type": "skip"})
                self._on_action_queued()
                progressed = True
                continue

            if p == "resolve_done" and self._is_lan():
                if self._init_player_resolved:
                    second = 3 - (self._resolving_player or self.battle.init_player)
                    if self._is_ai_player(second) or self._is_single_player():
                        self._auto_continue_resolve_done()
                        progressed = True
                else:
                    self._auto_continue_resolve_done()
                    progressed = True

    def _maybe_fast_skip(self):
        """Auto-advance battle-flow screens when Fast Skip is enabled."""
        # Battle ticker handles fast-skip internally; nothing to do here.
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # TICKER METHODS
    # ─────────────────────────────────────────────────────────────────────────

    def _tk_advance(self, dt: float):
        """Advance the bottom-text ticker each frame."""
        if self.phase != "battle":
            return
        if self._tk_btn_label is not None:
            return  # waiting for pass-button click
        if self._tk_timer > 0:
            self._tk_timer = max(0.0, self._tk_timer - dt)
            return
        if self._tk:
            self._tk_process_next()

    def _tk_process_next(self):
        """Pop and handle the next step from the ticker queue."""
        if not self._tk:
            return
        step = self._tk.pop(0)
        k = step["k"]
        self._tk_overlay_msg = ""   # clear overlay before each new step
        fast = bool(
            self.campaign_profile and self.campaign_profile.fast_resolution
            and not step.get("important", False)
        )

        if k == "text":
            if step.get("overlay"):
                self._tk_overlay_msg = step["msg"]
                self._tk_msg = ""
            else:
                self._tk_msg = step["msg"]
            self._tk_timer = 0.0 if fast else step.get("dur", 2.0)

        elif k == "btn":
            self._tk_msg = step["msg"]
            self._tk_btn_label = step["label"]
            # _tk_btn_rect is set in draw()

        elif k == "initiative_tutorial":
            self._maybe_show_tutorial(
                "initiative",
                "The speed of the frontline adventurer determines who goes first each round. "
                "In the case of a tie, it goes to whoever lost the last initiative. For only "
                "the first round, whoever loses initiative can make a swap at the beginning "
                "of the battle for free.")
            if self._tutorial_pending:
                # Pause the ticker until the popup is dismissed
                self._tk_btn_label = "__tutorial__"

        elif k == "action_selection_tutorial":
            self._maybe_show_tutorial(
                "action_selection",
                "Each adventurer can select one action each turn: using an ability, "
                "using an item, or swapping. You can only swap once per round, though "
                "abilities and items that let you swap ignore that limit.")
            if self._tutorial_pending:
                self._tk_btn_label = "__tutorial__"

        elif k == "status_condition_tutorial":
            self._maybe_show_tutorial(
                "status_condition",
                "Adventurers can be inflicted with status conditions from a variety of effects. "
                "Status conditions of the same type do not stack, but an adventurer "
                "can have any number of different status conditions, most always lasting for "
                "2 rounds. Hover over a status condition to see what it does!")
            if self._tutorial_pending:
                self._tk_btn_label = "__tutorial__"

        elif k == "stat_mod_tutorial":
            self._maybe_show_tutorial(
                "stat_mod",
                "An adventurer's stats can be buffed or debuffed by a variety of effects. "
                "Temporary stat buffs and debuffs do not stack, but multiple stats can be "
                "buffed or debuffed at once.")
            if self._tutorial_pending:
                self._tk_btn_label = "__tutorial__"

        elif k == "select":
            player = step["player"]
            self._tk_msg = f"P{player} is selecting their actions..."
            self._tk_timer = 0.0
            if self._is_ai_player(player):
                self._tk_ai_select_all(player)
            else:
                self._enter_action_selection(player)
                # phase changes to select_actions; _tk resumes when done

        elif k == "swap":
            player = step["player"]
            if self._is_ai_player(player):
                log_before = len(self.battle.log)
                swapped = self._ai_pick_extra_swap(player)
                new_lines = self.battle.log[log_before:]
                inject = [{"k": "text", "msg": line, "dur": 2.0}
                  for line in new_lines if not line.startswith("\x01")]
                if not swapped:
                    inject.insert(0, {"k": "text",
                                      "msg": f"P{player} passed on the free swap.", "dur": 2.0})
                self._tk[0:0] = inject
            else:
                self.phase = f"extra_swap_p{player}"
                self._init_extra_swap(player)
                # For LAN: notify the client so they can show their swap UI
                if self._is_lan() and self.game_mode == "lan_host" and player == 2:
                    self._lan_send_state(phase=f"extra_swap_p{player}")
                # returns to "battle" when swap done

        elif k == "init_resolve":
            player = step["player"]
            self._resolving_player = player
            self._init_player_resolved = False
            team = self.battle.get_team(player)
            self._action_step_queue = []
            for slot in CLOCKWISE_ORDER:
                unit = team.get_slot(slot)
                if unit and not unit.ko:
                    self._action_step_queue.append((unit, player, False))
                    if unit.extra_actions_now > 0 and unit.queued2 is not None:
                        self._action_step_queue.append((unit, player, True))

        elif k == "resolve_action":
            self._tk_do_one_action()

        elif k == "stitch_select":
            if self._extra_action_queue:
                pnum, u = self._extra_action_queue[0]
                self.selecting_player = pnum
                self.current_actor    = u
                self.current_is_extra = True
                self.selection_sub    = "pick_action"
                self.pending_action   = None
                if self._is_ai_player(pnum):
                    if not self._ai_queue_current_actor_action():
                        self._set_queued(u, {"type": "skip"})
                    self._tk.insert(0, {"k": "stitch_resolve"})
                else:
                    self.phase = f"extra_action_p{pnum}"

        elif k == "stitch_resolve":
            self._resolve_stitch_extra_and_continue()

        elif k == "do_end_round":
            log_before = len(self.battle.log)
            self.battle.log_add("─── End of Round ───")
            do_end_round(self.battle)
            new_lines = self.battle.log[log_before:]
            inject = [{"k": "text", "msg": line, "dur": 2.0}
                  for line in new_lines if not line.startswith("\x01")]
            if self.battle.winner:
                inject.append({"k": "battle_end"})
                self._tk.clear()   # discard any remaining steps (text, btn, next_round)
            else:
                inject += self._maybe_inject_battle_tutorials()
            self._tk[0:0] = inject

        elif k == "next_round":
            if self.battle.winner:
                self._tk_finish_battle()
            else:
                self._tk_setup_next_round()

        elif k == "battle_end":
            self._tk_finish_battle()

    def _tk_do_one_action(self):
        """Execute one action from _action_step_queue and inject its log lines."""
        # Skip KO'd units
        while self._action_step_queue and self._action_step_queue[0][0].ko:
            self._action_step_queue.pop(0)

        if not self._action_step_queue:
            # All actions resolved — check for Stitch In Time extras
            player = self._resolving_player
            extras = [
                unit for unit in self.battle.get_team(player).alive()
                if unit.extra_actions_now > 0 and unit.queued2 is None
            ]
            if extras:
                self._extra_action_queue = [(player, u) for u in extras]
                self._tk.insert(0, {"k": "stitch_select"})
            else:
                if player == self.battle.init_player:
                    self._init_player_resolved = True
            return  # fall through to next pre-built queue item

        unit, player_num, is_queued2 = self._action_step_queue.pop(0)
        log_before = len(self.battle.log)
        if is_queued2:
            unit.extra_actions_now -= 1
            saved       = unit.queued
            unit.queued  = unit.queued2
            unit.queued2 = None
            resolve_queued_action(unit, player_num, self.battle)
            unit.queued  = saved
        else:
            resolve_queued_action(unit, player_num, self.battle)
            unit.queued = None

        new_lines = self.battle.log[log_before:]
        inject = [{"k": "text", "msg": line, "dur": 2.0}
                  for line in new_lines if not line.startswith("\x01")]
        if self.battle.winner:
            inject.append({"k": "battle_end"})
        else:
            inject += self._maybe_inject_battle_tutorials()
            inject.append({"k": "resolve_action"})
        self._tk[0:0] = inject

    def _tk_ai_select_all(self, player: int):
        """Auto-select all actions for an AI player, synchronously."""
        self._enter_action_selection(player)
        safety = 0
        while self.phase == "select_actions" and self.current_actor is not None and safety < 30:
            safety += 1
            already = (self.current_actor.queued2 is not None
                       if self.current_is_extra else
                       self.current_actor.queued is not None)
            if already:
                self._on_action_queued()
                continue
            if not self._ai_queue_current_actor_action():
                self._set_queued(self.current_actor, {"type": "skip"})
            self._on_action_queued()
        # _finish_selection sets phase = "battle"; ensure we're back
        self.phase = "battle"

    def _tk_setup_next_round(self):
        """Determine initiative and inject round steps into the ticker."""
        apply_passive_stats(self.battle.team1, self.battle)
        apply_passive_stats(self.battle.team2, self.battle)
        apply_round_start_effects(self.battle)
        determine_initiative(self.battle)

        init   = self.battle.init_player
        second = 3 - init
        rnd    = self.battle.round_num
        reason = getattr(self.battle, "init_reason", "")
        esp    = self.battle.r1_extra_swap_player
        sp     = self._is_single_player()
        lan    = self._is_lan()

        msg = f"Round {rnd} — P{init} has initiative!"
        if reason:
            msg += f"\n{reason}"

        steps = [{"k": "text", "msg": msg, "dur": 2.0, "important": True, "overlay": True}]

        if rnd == 1:
            steps.insert(0, {"k": "initiative_tutorial"})

        if esp:
            steps.append({"k": "text",
                           "msg": f"P{esp} receives a free formation swap.", "dur": 2.0})
            steps.append({"k": "swap", "player": esp})

        # ── Init player selects and resolves ──────────────────────────────────
        steps.append({"k": "text",
                       "msg": f"P{init} is selecting their actions.", "dur": 2.0})
        if rnd == 1 and not self._is_ai_player(init):
            steps.append({"k": "action_selection_tutorial"})
        steps.append({"k": "select", "player": init})
        steps.append({"k": "init_resolve", "player": init})
        steps.append({"k": "resolve_action"})
        steps.append({"k": "text",
                       "msg": f"P{init}'s actions are complete.", "dur": 2.0, "important": True})

        # Pass Turn button: when init player is human, or LAN
        if lan or (sp and not self._is_ai_player(init)):
            steps.append({"k": "btn",
                           "msg": f"P{init} has acted — pass the turn to P{second}.",
                           "label": "Pass Turn →"})

        # ── Second player selects and resolves ────────────────────────────────
        steps.append({"k": "text",
                       "msg": f"P{second} is selecting their actions.", "dur": 2.0})
        if rnd == 1 and not self._is_ai_player(second):
            steps.append({"k": "action_selection_tutorial"})
        steps.append({"k": "select", "player": second})
        steps.append({"k": "init_resolve", "player": second})
        steps.append({"k": "resolve_action"})

        # End-of-round effects (injected dynamically by do_end_round)
        steps.append({"k": "do_end_round"})

        steps.append({"k": "text",
                       "msg": f"P{second}'s actions are complete.", "dur": 2.0, "important": True})

        # End Round button: when second player is human, or LAN
        if lan or (sp and not self._is_ai_player(second)):
            steps.append({"k": "btn",
                           "msg": "Round complete — end the round.",
                           "label": "End Round →"})

        steps.append({"k": "next_round"})

        self._tk[0:0] = steps

    def _tk_finish_battle(self):
        """Route to result screen after battle ends."""
        battle_log.close()
        if self._is_lan() and self.game_mode == "lan_host":
            self._lan_send_state(phase="result")
        if self.game_mode == "campaign":
            self._campaign_won_quest = (self.battle.winner == 1)
            self.phase = "campaign_post_quest"
        else:
            self.phase = "result"

    # ─────────────────────────────────────────────────────────────────────────
    def _to_logical(self, screen_pos):
        """Translate a screen-space position to the 1400×900 logical canvas space."""
        ox, oy = self._canvas_offset
        lx = (screen_pos[0] - ox) / self._scale
        ly = (screen_pos[1] - oy) / self._scale
        return (int(lx), int(ly))

    def run(self):
        while True:
            mouse_pos = self._to_logical(pygame.mouse.get_pos())
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if e.type == pygame.KEYDOWN:
                    self._handle_keydown(e)
                if e.type == pygame.MOUSEWHEEL:
                    self._handle_mousewheel(e)
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    self.handle_click(mouse_pos)

            self._lan_tick()
            self._maybe_auto_progress()
            self._maybe_fast_skip()

            dt = self.clock.tick(FPS) / 1000.0
            self._tk_advance(dt)
            if self._intro_timer > 0:
                self._intro_timer -= dt
                if self._intro_timer <= 0:
                    self._intro_visible = 1
            self.draw(mouse_pos)

            # Scale the logical canvas to fill the screen (letterboxed if aspect differs).
            scaled_w = int(WIDTH  * self._scale)
            scaled_h = int(HEIGHT * self._scale)
            scaled = pygame.transform.smoothscale(self._canvas, (scaled_w, scaled_h))
            self.screen.fill((0, 0, 0))
            self.screen.blit(scaled, self._canvas_offset)
            pygame.display.flip()

    # ─────────────────────────────────────────────────────────────────────────
    # CLICK HANDLER
    # ─────────────────────────────────────────────────────────────────────────

    def handle_click(self, pos):
        if self._intro_visible > 0:
            if self._intro_visible < 4:
                self._intro_visible += 1
            elif self._intro_lets_go_btn and self._intro_lets_go_btn.collidepoint(pos):
                self._intro_visible = 0
            return

        if self._lan_disconnected and self._is_lan():
            disc_btn = getattr(self, "_last_disconnect_btn", None)
            if disc_btn and disc_btn.collidepoint(pos):
                self._lan_disconnected = False
                if self._lan:
                    self._lan.close()
                    self._lan = None
                self.game_mode = "pvp"
                self.battle = None
                self.phase = "menu"
            return

        if self._tutorial_pending:
            self._tutorial_pending = None
            if self._tk_btn_label == "__tutorial__":
                self._tk_btn_label = None
                self._tk_btn_rect = None
            return

        p = self.phase

        if p == "menu":
            story_btn, practice_btn, teambuilder_btn, catalog_btn, settings_btn, exit_btn = self._last_menu_btns
            if story_btn.collidepoint(pos):
                self.phase = "campaign_mission_select"
            elif practice_btn.collidepoint(pos):
                self.phase = "practice_menu"
            elif teambuilder_btn.collidepoint(pos):
                self._teambuilder_return_phase = "menu"
                self.phase = "teambuilder"
            elif catalog_btn.collidepoint(pos):
                self._catalog_tab = "adventurers"
                self._catalog_selected = None
                self._catalog_scroll = 0
                self.phase = "catalog"
                if self.campaign_profile:
                    self.campaign_profile.new_unlocks.discard("adventurers")
                    save_campaign(self.campaign_profile)
            elif settings_btn.collidepoint(pos):
                self._confirm_reset = False
                self.phase = "settings"
            elif exit_btn.collidepoint(pos):
                pygame.quit(); sys.exit()

        elif p == "catalog":
            btns = self._last_catalog_btns or {}
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "menu"
                return
            for rect, key in btns.get("tab_btns", []):
                if rect.collidepoint(pos):
                    self._catalog_tab = key
                    self._catalog_selected = None
                    self._catalog_scroll = 0
                    if self.campaign_profile:
                        self.campaign_profile.new_unlocks.discard(key)
                        save_campaign(self.campaign_profile)
                    return
            if btns.get("clear_all_btn") and btns["clear_all_btn"].collidepoint(pos):
                for s in self._catalog_filters.get(self._catalog_tab, {}).values():
                    if isinstance(s, set):
                        s.clear()
                self._catalog_selected = None
                return
            for rect, fkey, val in btns.get("filter_chips", []):
                if rect.collidepoint(pos):
                    tab_f = self._catalog_filters.setdefault(self._catalog_tab, {})
                    fset = tab_f.setdefault(fkey, set())
                    if val in fset:
                        fset.discard(val)
                    else:
                        fset.add(val)
                    self._catalog_selected = None
                    return
            for rect, idx in btns.get("list_btns", []):
                if rect.collidepoint(pos):
                    self._catalog_selected = idx
                    return

        elif p == "practice_menu":
            btns = self._last_practice_btns or {}
            if btns.get("vs_ai_btn") and btns["vs_ai_btn"].collidepoint(pos):
                self.game_mode = "single_player"
                if hasattr(self, "_campaign_roster"):
                    del self._campaign_roster
                self._start_team_select(1)
            elif btns.get("vs_pvp_btn") and btns["vs_pvp_btn"].collidepoint(pos):
                self.game_mode = "pvp"
                self._lan_role = None
                self._lan = None
                self._lan_p1_ready = False
                self._lan_p2_ready = False
                self._lan_status = ""
                self._lan_ip_input = ""
                self.phase = "lan_lobby"
            elif btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "menu"

        elif p == "lan_lobby":
            btns = self._last_lan_lobby_btns or {}
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                if self._lan:
                    self._lan.close()
                    self._lan = None
                self._lan_role = None
                self._lan_status = ""
                self.game_mode = "pvp"
                self.phase = "practice_menu"
                return
            if self._lan_role is None:
                if btns.get("host_btn") and btns["host_btn"].collidepoint(pos):
                    self._lan_role = "host"
                    self._lan = net.LANHost()
                    self.game_mode = "lan_host"
                    self._lan_host_notified = False
                    self._lan_p1_ready = False
                    self._lan_p2_ready = False
                elif btns.get("join_btn") and btns["join_btn"].collidepoint(pos):
                    self._lan_role = "client"
                    self._lan = net.LANClient()
                    self.game_mode = "lan_client"
                    self._lan_ip_active = True
            elif self._lan_role == "client":
                if btns.get("ip_box") and btns["ip_box"].collidepoint(pos):
                    self._lan_ip_active = True
                if btns.get("connect_btn") and btns["connect_btn"].collidepoint(pos):
                    self._lan_status = ""
                    self._lan.connect_async(self._lan_ip_input)

        elif p == "teambuilder":
            # If the rename overlay is active, route clicks to it instead.
            if self._renaming_team_slot is not None:
                overlay_btns = self._last_rename_overlay_btns or {}
                if overlay_btns.get("confirm_btn") and overlay_btns["confirm_btn"].collidepoint(pos):
                    self._commit_rename()
                elif overlay_btns.get("cancel_btn") and overlay_btns["cancel_btn"].collidepoint(pos):
                    self._renaming_team_slot = None
                    self._rename_text = ""
                return

            btns = self._last_teambuilder_btns or {}
            for rect, slot_idx in btns.get("slot_btns", []):
                if rect.collidepoint(pos):
                    self._start_teambuilder_edit(slot_idx)
                    return
            for rect, slot_idx in btns.get("delete_btns", []):
                if rect.collidepoint(pos):
                    if 0 <= slot_idx < len(self.campaign_profile.saved_teams):
                        self.campaign_profile.saved_teams.pop(slot_idx)
                        save_campaign(self.campaign_profile)
                    return
            for rect, slot_idx in btns.get("rename_btns", []):
                if rect.collidepoint(pos):
                    self._start_rename(slot_idx)
                    return
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = self._teambuilder_return_phase

        elif p == "settings":
            btns = self._last_settings_btns or {}
            if self._confirm_reset:
                if btns.get("confirm_btn") and btns["confirm_btn"].collidepoint(pos):
                    self._reset_player_data()
                elif btns.get("cancel_btn") and btns["cancel_btn"].collidepoint(pos):
                    self._confirm_reset = False
            else:
                if btns.get("tutorial_btn") and btns["tutorial_btn"].collidepoint(pos):
                    self.campaign_profile.tutorials_enabled = not self.campaign_profile.tutorials_enabled
                    save_campaign(self.campaign_profile)
                elif btns.get("fast_btn") and btns["fast_btn"].collidepoint(pos):
                    self.campaign_profile.fast_resolution = not self.campaign_profile.fast_resolution
                    save_campaign(self.campaign_profile)
                elif btns.get("reset_btn") and btns["reset_btn"].collidepoint(pos):
                    self._confirm_reset = True
                elif btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                    self.phase = "menu"

        elif p == "team_select":
            # Import modal intercepts clicks when open
            if self._import_modal_open:
                modal_clicks = getattr(self, "_last_import_modal_clicks", {}) or {}
                cancel = modal_clicks.get("cancel")
                confirm = modal_clicks.get("confirm")
                if cancel and cancel.collidepoint(pos):
                    self._import_modal_open = False
                    self._import_modal_text = ""
                    self._import_modal_error = ""
                elif confirm and confirm.collidepoint(pos):
                    allow_all = self.game_mode not in ("campaign", "teambuilder")
                    picks, err = self._parse_team_import(self._import_modal_text, allow_all)
                    if picks is not None:
                        self.team_picks = picks
                        self.roster_selected = picks[0]["definition"]
                        self._import_modal_open = False
                        self._import_modal_text = ""
                        self._import_modal_error = ""
                        self.sub_phase = "pick_adventurers"
                        self.team_select_scroll = 0
                    else:
                        self._import_modal_error = err
                return
            self._handle_team_select_click(pos)

        elif p == "pre_battle_edit":
            if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
                self._detail_unit = None
                return
            self._handle_team_select_click(pos)

        elif p.startswith("pass_"):
            if self._last_pass_btn and self._last_pass_btn.collidepoint(pos):
                self._advance_from_pass()

        elif p == "select_actions":
            self._handle_action_select_click(pos)

        elif p == "lan_waiting":
            if self.battle:
                if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
                    self._detail_unit = None
                    return
                unit = self._unit_at_pos(pos)
                if unit:
                    self._detail_unit = None if self._detail_unit is unit else unit

        elif p == "result":
            menu_btn, quit_btn = self._last_result_btns
            if menu_btn.collidepoint(pos):
                self.phase = "menu"
            elif quit_btn.collidepoint(pos):
                pygame.quit(); sys.exit()

        elif p == "campaign_mission_select":
            btns = self._last_campaign_btns or {}
            back_btn = btns.get("back_btn")
            if back_btn and back_btn.collidepoint(pos):
                self.phase = "menu"
                return
            for rect, mission_id in btns.get("mission_btns", []):
                if rect.collidepoint(pos):
                    self.campaign_mission_id = mission_id
                    self.phase = "campaign_quest_select"
                    return

        elif p == "campaign_quest_select":
            btns = self._last_campaign_btns or {}
            back_btn = btns.get("back_btn")
            if back_btn and back_btn.collidepoint(pos):
                self.phase = "campaign_mission_select"
                return
            for rect, quest_id in btns.get("quest_btns", []):
                if rect.collidepoint(pos):
                    self.campaign_quest_id = quest_id
                    self.phase = "campaign_pre_quest"
                    return

        elif p == "campaign_pre_quest":
            btns = self._last_campaign_btns or {}
            # Close detail panel
            if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
                self._detail_unit = None
                return
            back_btn  = btns.get("back_btn")
            start_btn = btns.get("start_btn")
            if back_btn and back_btn.collidepoint(pos):
                self._detail_unit = None
                self.phase = "campaign_quest_select"
                return
            if start_btn and start_btn.collidepoint(pos):
                self._detail_unit = None
                teams = self.campaign_profile.saved_teams if self.campaign_profile else []
                valid_teams = [t for t in teams if t is not None]
                if valid_teams:
                    self.phase = "story_team_select"
                else:
                    self._teambuilder_return_phase = "story_team_select"
                    self.phase = "teambuilder"
                return
            # Enemy card click → show detail panel (click same card again to close)
            for rect, pick in btns.get("enemy_cards", []):
                if rect.collidepoint(pos):
                    defn = pick["definition"]
                    if self._detail_unit and self._detail_unit.defn is defn:
                        self._detail_unit = None
                    else:
                        self._detail_unit = make_combatant(
                            defn, SLOT_FRONT,
                            pick["signature"], pick["basics"], pick["item"],
                        )
                    return

        elif p == "story_team_select":
            btns = self._last_story_team_btns or {}
            for rect, slot_idx in btns.get("team_btns", []):
                if rect.collidepoint(pos):
                    self._story_team_idx = slot_idx
                    self._start_campaign_battle_with_team(slot_idx)
                    return
            tb_btn = btns.get("teambuilder_btn")
            if tb_btn and tb_btn.collidepoint(pos):
                self._teambuilder_return_phase = "story_team_select"
                self.phase = "teambuilder"
                return
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "campaign_pre_quest"

        elif p == "campaign_post_quest":
            btns = self._last_campaign_btns or {}
            cont_btn = btns.get("continue_btn")
            if cont_btn and cont_btn.collidepoint(pos):
                if self._campaign_won_quest:
                    apply_quest_rewards(self.campaign_profile, self.campaign_quest_id)
                    save_campaign(self.campaign_profile)
                    if self.campaign_profile.campaign_complete:
                        self.phase = "campaign_complete"
                    else:
                        self.phase = "campaign_mission_select"
                else:
                    self.phase = "campaign_mission_select"

        elif p == "campaign_complete":
            btns = self._last_campaign_btns or {}
            menu_btn = btns.get("menu_btn")
            if menu_btn and menu_btn.collidepoint(pos):
                self.phase = "menu"

    def _concede_battle(self, conceding_player: int):
        """Immediately concede the current battle for one player."""
        if not self.battle or conceding_player not in (1, 2):
            return
        winner = 2 if conceding_player == 1 else 1
        self.battle.winner = winner
        self.battle.log_add(f"Player {conceding_player} concedes. Player {winner} wins!")
        battle_log.close()
        self.phase = "result"

    def _current_phase_player(self):
        """Best-effort player context for single-device ESC concede flow."""
        p = self.phase
        if p.endswith("p1"):
            return 1
        if p.endswith("p2"):
            return 2
        if self.selecting_player in (1, 2):
            return self.selecting_player
        if self._resolving_player in (1, 2):
            return self._resolving_player
        if self.battle and self.battle.init_player in (1, 2):
            return self.battle.init_player
        return None

    def _handle_keydown(self, e):
        # Import modal text input — takes priority
        if self._import_modal_open:
            if e.key == pygame.K_ESCAPE:
                self._import_modal_open = False
                self._import_modal_text = ""
                self._import_modal_error = ""
            elif e.key == pygame.K_BACKSPACE:
                self._import_modal_text = self._import_modal_text[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._import_modal_text += "\n"
            elif (e.key == pygame.K_v
                  and (e.mod & pygame.KMOD_CTRL)):
                # Paste from clipboard
                try:
                    clip_data = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if clip_data:
                        # pygame.scrap returns bytes on some platforms
                        if isinstance(clip_data, (bytes, bytearray)):
                            clip_str = clip_data.decode("utf-8", errors="ignore").rstrip("\x00")
                        else:
                            clip_str = str(clip_data)
                        self._import_modal_text += clip_str
                except Exception:
                    pass
            else:
                ch = e.unicode
                if ch and ch.isprintable():
                    self._import_modal_text += ch
            return

        # LAN IP text input
        if self._lan_ip_active and self.phase == "lan_lobby" and self._lan_role == "client":
            if e.key == pygame.K_RETURN:
                self._lan_ip_active = False
            elif e.key == pygame.K_BACKSPACE:
                self._lan_ip_input = self._lan_ip_input[:-1]
            else:
                ch = e.unicode
                if ch and (ch.isdigit() or ch == ".") and len(self._lan_ip_input) < 15:
                    self._lan_ip_input += ch
            return

        # Text input for rename overlay
        if self._renaming_team_slot is not None:
            if e.key == pygame.K_RETURN or e.key == pygame.K_KP_ENTER:
                self._commit_rename()
            elif e.key == pygame.K_ESCAPE:
                self._renaming_team_slot = None
                self._rename_text = ""
            elif e.key == pygame.K_BACKSPACE:
                self._rename_text = self._rename_text[:-1]
            else:
                ch = e.unicode
                if ch and ch.isprintable() and len(self._rename_text) < 24:
                    self._rename_text += ch
            return

        if e.key != pygame.K_ESCAPE:
            return

        # ESC closes settings confirmation without leaving settings
        if self.phase == "settings" and self._confirm_reset:
            self._confirm_reset = False
            return

        # ESC exits the teambuilder screen.
        if self.phase == "teambuilder":
            self.phase = self._teambuilder_return_phase
            return

        # ESC steps back through team-select sub-phases.
        if self.phase in ("team_select", "pre_battle_edit"):
            self._do_team_select_back()
            return

        # Keep existing UX: ESC cancels target picking first.
        if self.phase in ("select_actions",) or self.phase.startswith("extra_action_p"):
            if self.selection_sub == "pick_target":
                self.selection_sub = "pick_action"
                self.pending_action = None
                return

        # ESC can concede in battle-related phases.
        battleish = (
            self.battle is not None
            and self.phase not in ("menu", "team_select", "result", "pass_to_team_p2")
        )
        if battleish:
            conceder = self._current_phase_player()
            if conceder in (1, 2):
                self._concede_battle(conceder)

    def _is_in_battle(self):
        """True when the battle UI is active (any phase where the log is visible)."""
        if self.battle is None:
            return False
        p = self.phase
        return (
            p in ("battle", "battle_start", "end_of_round",
                  "select_actions", "resolving", "resolve_done", "actions_resolving",
                  "action_result", "end_round", "result", "lan_waiting")
            or p.startswith(("pass_to_", "extra_swap_p", "extra_action_p"))
        )

    def _handle_mousewheel(self, e):
        # Battle log scroll: works anywhere on screen during battle
        if self._is_in_battle():
            self.battle_log_scroll = max(0, self.battle_log_scroll + e.y * 3)
            return
        if self.phase == "catalog":
            btns = self._last_catalog_btns or {}
            max_scroll = btns.get("scroll_max", 0)
            if max_scroll > 0:
                self._catalog_scroll -= e.y * 40
                self._catalog_scroll = max(0, min(self._catalog_scroll, max_scroll))
            return
        if self.phase not in ("team_select", "pre_battle_edit"):
            return
        if self.sub_phase not in ("pick_adventurers", "pick_basics", "pick_item"):
            return
        clicks = getattr(self, "_last_team_clicks", None) or {}
        max_scroll = clicks.get("scroll_max", 0)
        if max_scroll <= 0:
            self.team_select_scroll = 0
            return
        step = 40
        self.team_select_scroll -= e.y * step
        self.team_select_scroll = max(0, min(self.team_select_scroll, max_scroll))

    # ─────────────────────────────────────────────────────────────────────────
    # TEAM SELECTION
    # ─────────────────────────────────────────────────────────────────────────

    def _do_team_select_back(self):
        """Shared back-navigation logic for team_select, used by Back button and ESC."""
        sp = self.sub_phase
        if sp == "pick_adventurers":
            if self.phase == "pre_battle_edit":
                # Back from pick_adventurers in pre_battle_edit goes to back_phase
                if self._pbe_back_phase:
                    self.phase = self._pbe_back_phase
                return
            # Leave team select entirely.
            if self.game_mode == "teambuilder":
                self.phase = "teambuilder"
            else:
                self.phase = "menu"
        elif sp == "pick_sig":
            # In the new flow, Back from pick_sig always returns to pick_adventurers
            if self._editing_single_member:
                # Cancel single-member edit and return to teambuilder.
                self._editing_single_member = False
                self.phase = "teambuilder"
            else:
                self._editing_from_roster = False
                self._focused_slot = self.current_adv_idx  # restore focus to the member we were editing
                # Restore sets backup if available (user backed out without changing anything)
                if self._edit_sets_backup is not None:
                    bk = self._edit_sets_backup
                    if bk.get("signature"):
                        self.team_picks[self.current_adv_idx]["signature"] = bk["signature"]
                    if bk.get("basics"):
                        self.team_picks[self.current_adv_idx]["basics"] = bk["basics"]
                    if bk.get("item"):
                        self.team_picks[self.current_adv_idx]["item"] = bk["item"]
                    self._edit_sets_backup = None
                self.sub_phase = "pick_adventurers"
                self.team_select_scroll = 0
        elif sp == "pick_basics":
            self.team_picks[self.current_adv_idx].pop("signature", None)
            self.sig_choice = None
            self.sub_phase = "pick_sig"
            self.team_select_scroll = 0
        elif sp == "pick_item":
            self.team_picks[self.current_adv_idx].pop("basics", None)
            self.basic_choices = []
            self.sub_phase = "pick_basics"
            self.team_select_scroll = 0

    def _parse_team_import(self, text: str, allow_all: bool):
        """Parse a team import string. Returns (picks_list, error_string).
        picks_list is None on any validation error.
        allow_all=True: practice/single_player mode (full ROSTER/ITEMS/CLASS_BASICS).
        allow_all=False: use campaign/teambuilder restricted lists.
        """
        # Determine the active pools
        if allow_all:
            active_roster     = ROSTER
            active_items      = ITEMS
            active_cls_basics = CLASS_BASICS
        else:
            active_roster     = getattr(self, "_campaign_roster", ROSTER)
            active_items      = getattr(self, "_campaign_items", ITEMS)
            active_cls_basics = getattr(self, "_campaign_basics", CLASS_BASICS)

        # Build case-insensitive lookup dicts
        roster_by_name = {d.name.lower(): d for d in active_roster}
        items_by_name  = {it.name.lower(): it for it in active_items}

        # Normalize lines
        raw_lines = [l.rstrip() for l in text.splitlines()]
        lines = [l for l in raw_lines if l.strip()]

        # Need exactly 12 non-empty lines: 4 per member * 3 members
        if len(lines) != 12:
            return (None, "Can't upload this.")

        picks = []
        used_item_ids = set()

        for block_start in range(0, 12, 4):
            block = lines[block_start: block_start + 4]
            # Line 0: "Adventurer @ Item"
            if " @ " not in block[0]:
                return (None, "Can't upload this.")
            adv_part, item_part = block[0].split(" @ ", 1)
            adv_name  = adv_part.strip().lower()
            item_name = item_part.strip().lower()

            # Lines 1-3: "- AbilityName"
            ability_names = []
            for raw in block[1:4]:
                s = raw.strip()
                if not s.startswith("- "):
                    return (None, "Can't upload this.")
                ability_names.append(s[2:].strip().lower())

            # Look up adventurer
            defn = roster_by_name.get(adv_name)
            if defn is None:
                return (None, "Can't upload this.")

            # Look up item
            item = items_by_name.get(item_name)
            if item is None:
                return (None, "Can't upload this.")

            # No duplicate items
            if item.id in used_item_ids:
                return (None, "Can't upload this.")
            used_item_ids.add(item.id)

            # Look up signature (case-insensitive, within allowed sigs)
            if allow_all:
                avail_sigs = defn.sig_options
            else:
                sig_tier = (
                    self.campaign_profile.sig_tier
                    if self.campaign_profile else 3
                )
                avail_sigs = defn.sig_options[:sig_tier]
            sig_by_name = {s.name.lower(): s for s in avail_sigs}
            sig = sig_by_name.get(ability_names[0])
            if sig is None:
                return (None, "Can't upload this.")

            # Look up basics (2 basics for this class)
            cls_pool = active_cls_basics.get(defn.cls, [])
            basics_by_name = {b.name.lower(): b for b in cls_pool}
            basic1 = basics_by_name.get(ability_names[1])
            basic2 = basics_by_name.get(ability_names[2])
            if basic1 is None or basic2 is None:
                return (None, "Can't upload this.")
            if basic1 is basic2:
                return (None, "Can't upload this.")

            picks.append({
                "definition": defn,
                "signature":  sig,
                "basics":     [basic1, basic2],
                "item":       item,
            })

        return (picks, "")

    def _start_team_select(self, player_num):
        self.building_player = player_num
        self.sub_phase = "pick_adventurers"
        self.roster_selected = None
        self.team_picks = []
        self.current_adv_idx = 0
        self.sig_choice = None
        self.basic_choices = []
        self.item_choice = None
        self.team_slot_selected = None
        self.team_select_scroll = 0
        self._editing_single_member = False
        self._focused_slot = None
        self.phase = "team_select"
        self._maybe_show_tutorial("party_editor", "Select three adventurers to form a party!")

    def _handle_team_select_click(self, pos):
        clicks = self._last_team_clicks
        if clicks is None:
            return

        # Determine active roster for campaign / teambuilder vs normal mode
        if self.game_mode in ("campaign", "teambuilder") and hasattr(self, "_campaign_roster"):
            active_roster     = self._campaign_roster
            active_items      = self._campaign_items
            active_cls_basics = self._campaign_basics
        else:
            active_roster     = ROSTER
            active_items      = ITEMS
            active_cls_basics = CLASS_BASICS

        _in_pbe = (self.phase == "pre_battle_edit")

        # Party slot × remove button — check before swap/slots so the small hit-target wins
        # Not used in pre_battle_edit mode
        if not _in_pbe:
            for rect, idx in clicks.get("party_remove", []):
                if rect.collidepoint(pos):
                    if idx < len(self.team_picks):
                        self.team_picks.pop(idx)
                        # If we were editing this or a later member's sets, cancel that
                        if self._editing_from_roster and self.current_adv_idx >= idx:
                            self._editing_from_roster = False
                            self.sub_phase = "pick_adventurers"
                        if self.current_adv_idx >= len(self.team_picks):
                            self.current_adv_idx = max(0, len(self.team_picks) - 1)
                        self.team_slot_selected = None
                    return

        # Party slot ⇄ swap button — rotate member i to (i+1) % len
        for rect, idx in clicks.get("party_swap", []):
            if rect.collidepoint(pos):
                n = len(self.team_picks)
                if n >= 2 and idx < n:
                    j = (idx + 1) % n
                    self.team_picks[idx], self.team_picks[j] = \
                        self.team_picks[j], self.team_picks[idx]
                    # Keep current_adv_idx pointing at the same member after swap
                    if self.current_adv_idx == idx:
                        self.current_adv_idx = j
                    elif self.current_adv_idx == j:
                        self.current_adv_idx = idx
                    self._editing_from_roster = False
                    if self.sub_phase != "pick_adventurers":
                        self.sub_phase = "pick_adventurers"
                    self.team_slot_selected = None
                return

        # Party slot body click — focus the slot (show info), don't edit yet
        for rect, idx in clicks.get("party_slots", []):
            if rect.collidepoint(pos):
                if idx < len(self.team_picks):
                    if self.sub_phase == "pick_adventurers":
                        # Just focus the slot; editing requires clicking "Edit Sets"
                        self._focused_slot = idx
                    elif self.sub_phase in ("pick_sig", "pick_basics", "pick_item"):
                        # Clicking a different slot while editing: focus it, return to pick_adventurers
                        self._focused_slot = idx
                        self.sub_phase = "pick_adventurers"
                        self.team_select_scroll = 0
                    self.team_slot_selected = None
                return

        # Edit Sets button — now clear sets and open set editor for the focused slot
        edit_sets_btn = clicks.get("edit_sets_btn")
        if edit_sets_btn and edit_sets_btn.collidepoint(pos):
            idx = self._focused_slot
            if idx is not None and idx < len(self.team_picks):
                self.current_adv_idx = idx
                self._editing_from_roster = True
                # Save backup so Back can restore without losing sets
                self._edit_sets_backup = {
                    "signature": self.team_picks[idx].get("signature"),
                    "basics":    list(self.team_picks[idx].get("basics", [])),
                    "item":      self.team_picks[idx].get("item"),
                }
                self.team_picks[idx].pop("signature", None)
                self.team_picks[idx].pop("basics", None)
                self.team_picks[idx].pop("item", None)
                self.sig_choice = None
                self.basic_choices = []
                self.item_choice = None
                self.sub_phase = "pick_sig"
                self.team_select_scroll = 0
            return

        if self.sub_phase == "pick_adventurers":
            # Import Team button
            import_btn = clicks.get("import_btn")
            if import_btn and import_btn.collidepoint(pos):
                self._import_modal_open = True
                self._import_modal_text = ""
                self._import_modal_error = ""
                return

            for rect, defn in clicks.get("roster", []):
                if rect.collidepoint(pos):
                    self.team_slot_selected = None
                    # Check if already in team
                    existing = [i for i, p in enumerate(self.team_picks)
                                if p.get("definition") == defn]
                    if existing:
                        if len(self.team_picks) == 3:
                            # All 3 slots filled — focus this member for editing
                            self._focused_slot = existing[0]
                        else:
                            # Fewer than 3 — remove as before
                            self.team_picks.pop(existing[0])
                            self._focused_slot = None
                    elif len(self.team_picks) < 3:
                        self.team_picks.append({"definition": defn})
                        if len(self.team_picks) == 3:
                            self._maybe_show_tutorial("party_built", "Now, edit their sets to give them abilities!")
                    self.roster_selected = defn
                    return
            confirm = clicks.get("confirm")
            if confirm and confirm.collidepoint(pos):
                # Validate: all 3 members must have sig and 2 basics
                def _team_valid(picks):
                    return (len(picks) == 3 and
                            all("signature" in pk and len(pk.get("basics", [])) == 2
                                for pk in picks))
                if _team_valid(self.team_picks):
                    self.team_slot_selected = None
                    if _in_pbe:
                        self._confirm_pre_battle_edit()
                    else:
                        self._finish_team_select()

        elif self.sub_phase == "pick_sig":
            back = clicks.get("back")
            if back and back.collidepoint(pos):
                self._do_team_select_back()
                return
            for rect, idx in clicks.get("sig", []):
                if rect.collidepoint(pos):
                    self.sig_choice = idx
                    return
            confirm = clicks.get("confirm")
            if confirm and confirm.collidepoint(pos) and self.sig_choice is not None:
                defn = self.team_picks[self.current_adv_idx]["definition"]
                # In campaign/teambuilder mode, only allow sigs up to profile.sig_tier
                if self.game_mode in ("campaign", "teambuilder") and self.campaign_profile:
                    available_sigs = defn.sig_options[:self.campaign_profile.sig_tier]
                else:
                    available_sigs = defn.sig_options
                if self.sig_choice < len(available_sigs):
                    self.team_picks[self.current_adv_idx]["signature"] = \
                        available_sigs[self.sig_choice]
                else:
                    self.team_picks[self.current_adv_idx]["signature"] = \
                        available_sigs[0] if available_sigs else defn.sig_options[0]
                self._edit_sets_backup = None  # committed to new sig; discard backup
                self.sub_phase = "pick_basics"
                self.basic_choices = []
                self.team_select_scroll = 0

        elif self.sub_phase == "pick_basics":
            back = clicks.get("back")
            if back and back.collidepoint(pos):
                self._do_team_select_back()
                return
            pool = active_cls_basics.get(
                self.team_picks[self.current_adv_idx]["definition"].cls, [])
            for rect, idx in clicks.get("basics", []):
                if rect.collidepoint(pos):
                    if idx in self.basic_choices:
                        self.basic_choices.remove(idx)
                    elif len(self.basic_choices) < 2:
                        self.basic_choices.append(idx)
                    return
            confirm = clicks.get("confirm")
            if confirm and confirm.collidepoint(pos) and len(self.basic_choices) == 2:
                self.team_picks[self.current_adv_idx]["basics"] = \
                    [pool[i] for i in self.basic_choices]
                self.sub_phase = "pick_item"
                self.item_choice = None
                self.team_select_scroll = 0

        elif self.sub_phase == "pick_item":
            back = clicks.get("back")
            if back and back.collidepoint(pos):
                self._do_team_select_back()
                return
            for rect, idx in clicks.get("items", []):
                if rect.collidepoint(pos):
                    # Reject items already used by other team members
                    taken_ids = {p["item"].id for i, p in enumerate(self.team_picks)
                                 if "item" in p and i != self.current_adv_idx}
                    if active_items[idx].id in taken_ids:
                        return  # item already taken by another team member
                    self.item_choice = idx
                    return
            confirm = clicks.get("confirm")
            if confirm and confirm.collidepoint(pos):
                # Item is optional — save if one is selected, otherwise clear it
                if self.item_choice is not None:
                    self.team_picks[self.current_adv_idx]["item"] = \
                        active_items[self.item_choice]
                else:
                    self.team_picks[self.current_adv_idx].pop("item", None)
                if self._editing_single_member:
                    # Only editing this one member's sets — save and return.
                    self._editing_single_member = False
                    self._finish_team_select()
                else:
                    # Always return to pick_adventurers after item (new flow)
                    self._editing_from_roster = False
                    self.sub_phase = "pick_adventurers"
                    self.team_select_scroll = 0

        # Enemy card click in pre_battle_edit — toggle detail panel
        if _in_pbe:
            for rect, pick in clicks.get("enemy_cards", []):
                if rect.collidepoint(pos):
                    defn = pick["definition"]
                    if self._detail_unit and self._detail_unit.defn is defn:
                        self._detail_unit = None
                    else:
                        self._detail_unit = make_combatant(
                            defn, SLOT_FRONT,
                            pick["signature"], pick["basics"], pick["item"],
                        )
                    return

    def _ensure_picks_have_items(self, picks):
        """Ensure each pick has an item (use first available as fallback)."""
        fallback = ITEMS[0] if ITEMS else None
        if fallback is None:
            return
        for p in picks:
            if "item" not in p:
                p["item"] = fallback

    def _enter_pre_battle_edit(self, p1_picks, enemy_picks, back_phase):
        """Transition to the pre-battle team editor."""
        self.team_picks = list(p1_picks)
        self._pbe_enemy_picks = list(enemy_picks) if enemy_picks else []
        self._pbe_back_phase = back_phase
        self.sub_phase = "pick_adventurers"
        self.current_adv_idx = 0
        self.sig_choice = None
        self.basic_choices = []
        self.item_choice = None
        self.team_select_scroll = 0
        self.roster_selected = None
        self.team_slot_selected = None
        self._editing_from_roster = False
        self._editing_single_member = False
        self._focused_slot = None
        self._lan_pbe_local_ready = False
        self._lan_pbe_opponent_ready = False
        self.phase = "pre_battle_edit"

    def _confirm_pre_battle_edit(self):
        """Player confirmed their formation in pre-battle edit."""
        def _team_valid(picks):
            return (len(picks) == 3 and
                    all("signature" in pk and len(pk.get("basics", [])) == 2
                        for pk in picks))
        if not _team_valid(self.team_picks):
            return
        # Store picks for the appropriate player
        if self.game_mode == "lan_client":
            self.p2_picks = list(self.team_picks)
            self._ensure_picks_have_items(self.p2_picks)
        else:
            self.p1_picks = list(self.team_picks)
            self._ensure_picks_have_items(self.p1_picks)

        if self._is_lan():
            self._lan_pbe_local_ready = True
            self._lan_send({"type": "pre_battle_ready"})
            # If opponent already ready, start now
            if self._lan_pbe_opponent_ready:
                if self.game_mode == "lan_host":
                    self._start_lan_battle()
                else:
                    self._start_battle()
            # else: wait for opponent's pre_battle_ready message
            return

        # For all non-LAN modes, start the battle
        self._start_battle()

    def _finish_team_select(self):
        if self.game_mode == "teambuilder":
            self._save_built_team_to_slot()
            self.phase = "teambuilder"
            return

        # LAN: host picks P1's team, client picks P2's team, simultaneously
        if self.game_mode == "lan_host":
            self.p1_picks = list(self.team_picks)
            self._ensure_picks_have_items(self.p1_picks)
            self._lan_p1_ready = True
            if self._lan_p2_ready:
                self._enter_pre_battle_edit(self.p1_picks, self.p2_picks, None)
                self._lan_send({
                    "type": "pre_battle_start",
                    "p1_picks": self._serialize_picks(self.p1_picks),
                    "p2_picks": self._serialize_picks(self.p2_picks),
                })
            else:
                self.phase = "lan_waiting_teams"
            return

        if self.game_mode == "lan_client":
            self.p2_picks = list(self.team_picks)
            self._ensure_picks_have_items(self.p2_picks)
            self._lan_send({
                "type": "team_ready",
                "picks": self._serialize_picks(self.p2_picks),
            })
            self.phase = "lan_waiting_teams"
            return

        if self.building_player == 1:
            self.p1_picks = list(self.team_picks)
            self._ensure_picks_have_items(self.p1_picks)
            if self.game_mode == "single_player":
                self.ai_comp_name, self.p2_picks = self._generate_ai_team()
                self._enter_pre_battle_edit(self.p1_picks, self.p2_picks, "team_select")
                return
            else:
                # pvp — pass to player 2
                self.phase = "pass_to_team_p2"
        else:
            self.p2_picks = list(self.team_picks)
            self._ensure_picks_have_items(self.p2_picks)
            self._start_battle()

    def _start_teambuilder_edit(self, slot_idx: int):
        """Start editing a team slot in the Teambuilder."""
        self._editing_team_slot = slot_idx
        self.game_mode = "teambuilder"
        profile = self.campaign_profile
        self._campaign_roster = [d for d in ROSTER if d.id in profile.recruited]
        self._campaign_items = [it for it in ITEMS if it.id in profile.unlocked_items]
        self._campaign_basics = {
            cls_name: basics_list[:profile.basics_tier]
            for cls_name, basics_list in CLASS_BASICS.items()
            if cls_name in profile.unlocked_classes
        }
        # Load existing team picks if available, otherwise start fresh
        existing = self._resolve_saved_team(slot_idx)
        if existing is not None:
            self.team_picks = existing
        else:
            self.team_picks = []
        self.building_player = 1
        self.sub_phase = "pick_adventurers"
        self.roster_selected = self.team_picks[0]["definition"] if self.team_picks else None
        self.current_adv_idx = 0
        self.sig_choice = None
        self.basic_choices = []
        self.item_choice = None
        self.team_slot_selected = None
        self.team_select_scroll = 0
        self._editing_from_roster = False
        self._editing_single_member = False
        self.phase = "team_select"
        self._maybe_show_tutorial("party_editor", "Select three adventurers to form a party!")

    def _start_teambuilder_edit_member(self, slot_idx: int, member_idx: int):
        """Jump directly to editing one member's sig/basics/item without changing adventurers."""
        self._editing_team_slot = slot_idx
        self._editing_single_member = True
        self.game_mode = "teambuilder"
        profile = self.campaign_profile
        self._campaign_roster = [d for d in ROSTER if d.id in profile.recruited]
        self._campaign_items = [it for it in ITEMS if it.id in profile.unlocked_items]
        self._campaign_basics = {
            cls_name: basics_list[:profile.basics_tier]
            for cls_name, basics_list in CLASS_BASICS.items()
            if cls_name in profile.unlocked_classes
        }
        # Pre-load the existing team picks so the other two members are preserved.
        existing = self._resolve_saved_team(slot_idx)
        if existing is None:
            # Fallback: start fresh if resolve fails.
            self._editing_single_member = False
            self._start_team_select(1)
            return
        self.team_picks = existing
        self.building_player = 1
        self.current_adv_idx = member_idx
        # Clear only this member's set choices so the user picks fresh.
        self.team_picks[member_idx].pop("signature", None)
        self.team_picks[member_idx].pop("basics", None)
        self.team_picks[member_idx].pop("item", None)
        self.sig_choice = None
        self.basic_choices = []
        self.item_choice = None
        self.roster_selected = None
        self.team_slot_selected = None
        self.team_select_scroll = 0
        self.sub_phase = "pick_sig"
        self.phase = "team_select"

    def _save_built_team_to_slot(self):
        """Serialize completed team_picks and save to campaign profile."""
        slot = self._editing_team_slot
        if slot is None or len(self.team_picks) < 3:
            return
        members = []
        for p in self.team_picks:
            entry = {
                "adv_id":  p["definition"].id,
                "sig_id":  p["signature"].id,
                "basics":  [b.id for b in p["basics"]],
            }
            if "item" in p:
                entry["item_id"] = p["item"].id
            else:
                entry["item_id"] = ""
            members.append(entry)
        # Preserve existing name if the team already has one.
        teams = self.campaign_profile.saved_teams
        existing_name = None
        if slot < len(teams) and teams[slot] is not None:
            existing_name = teams[slot].get("name")
        team_name = existing_name if existing_name else f"Party {slot + 1}"
        entry = {"name": team_name, "members": members}
        while len(self.campaign_profile.saved_teams) <= slot:
            self.campaign_profile.saved_teams.append(None)
        self.campaign_profile.saved_teams[slot] = entry
        save_campaign(self.campaign_profile)
        self._editing_team_slot = None

    # ── Rename ────────────────────────────────────────────────────────────────

    def _start_rename(self, slot_idx: int):
        """Open the rename overlay for the given team slot."""
        teams = self.campaign_profile.saved_teams if self.campaign_profile else []
        current = ""
        if slot_idx < len(teams) and teams[slot_idx]:
            current = teams[slot_idx].get("name", "")
        self._renaming_team_slot = slot_idx
        self._rename_text = current

    def _commit_rename(self):
        """Save the typed name and close the overlay."""
        slot = self._renaming_team_slot
        text = self._rename_text.strip()
        if slot is not None and text:
            teams = self.campaign_profile.saved_teams
            if slot < len(teams) and teams[slot] is not None:
                teams[slot]["name"] = text
                save_campaign(self.campaign_profile)
        self._renaming_team_slot = None
        self._rename_text = ""

    # ── Settings / Reset ──────────────────────────────────────────────────────

    def _reset_player_data(self):
        """Wipe all campaign progress and saved teams, then reload."""
        import os
        if os.path.exists("campaign_save.json"):
            os.remove("campaign_save.json")
        self.campaign_profile = load_campaign()
        # Re-apply starter quest rewards (no badge for starting gear)
        apply_quest_rewards(self.campaign_profile, 0, notify=False)
        save_campaign(self.campaign_profile)
        self._confirm_reset = False
        self.phase = "menu"

    def _resolve_saved_team(self, slot_idx: int):
        """Resolve a saved team to picks format. Returns None if invalid."""
        teams = self.campaign_profile.saved_teams if self.campaign_profile else []
        if slot_idx >= len(teams) or teams[slot_idx] is None:
            return None
        team_data = teams[slot_idx]
        roster_by_id = {d.id: d for d in ROSTER}
        items_by_id  = {i.id: i for i in ITEMS}
        picks = []
        for m in team_data.get("members", []):
            defn = roster_by_id.get(m.get("adv_id"))
            if defn is None:
                return None
            sig = next((a for a in defn.sig_options if a.id == m.get("sig_id")), None)
            if sig is None:
                sig = defn.sig_options[0]
            basics_pool = CLASS_BASICS.get(defn.cls, [])
            basics_by_id = {b.id: b for b in basics_pool}
            basics = [basics_by_id.get(bid) for bid in m.get("basics", [])]
            if any(b is None for b in basics) or len(basics) != 2:
                return None
            item_id = m.get("item_id")
            item = items_by_id.get(item_id) if item_id else None
            # Fall back to first available item if none set (item is optional in teambuilder)
            if item is None and ITEMS:
                item = ITEMS[0]
            if item is None:
                return None
            picks.append({"definition": defn, "signature": sig, "basics": basics, "item": item})
        return picks if len(picks) == 3 else None

    def _start_campaign_battle_with_team(self, slot_idx: int):
        """Start a campaign battle using the saved team at slot_idx."""
        picks = self._resolve_saved_team(slot_idx)
        if picks is None:
            self.phase = "story_team_select"
            return
        self.p2_picks = build_quest_enemy_team(self.campaign_quest_id)
        self.game_mode = "campaign"
        self.ai_player = 2
        # Go to pre-battle edit so player can adjust slot order and sets before the fight
        self._ensure_picks_have_items(picks)
        self._enter_pre_battle_edit(picks, self.p2_picks, "story_team_select")

    # ─────────────────────────────────────────────────────────────────────────
    # BATTLE SETUP
    # ─────────────────────────────────────────────────────────────────────────

    def _start_battle(self):
        p1_name = "Player 1"
        if self.game_mode == "campaign":
            quest = QUEST_TABLE.get(self.campaign_quest_id)
            p2_name = f"Encounter {self.campaign_quest_id} Enemies" if quest else "Enemy"
        elif self._is_single_player():
            p2_name = "AI Opponent"
        else:
            p2_name = "Player 2"

        # ── Initialise battle log file ────────────────────────────────────────
        battle_log.init()
        battle_log.section("TEAM COMPOSITIONS")
        if self._is_single_player() and self.ai_comp_name:
            battle_log.log(f"AI archetype: {self.ai_comp_name}")
        for pname, picks in [("Player 1", self.p1_picks), ("Player 2", self.p2_picks)]:
            battle_log.log(f"{pname}:")
            for i, pick in enumerate(picks):
                d = pick["definition"]
                slot_label = ["front", "back_left", "back_right"][i]
                battle_log.log(
                    f"  [{slot_label}] {d.name} ({d.cls})"
                    f"  HP={d.hp}  ATK={d.attack}  DEF={d.defense}  SPD={d.speed}"
                )
                battle_log.log(
                    f"    Talent: {d.talent_name}"
                )
                battle_log.log(
                    f"    Sig:    {pick['signature'].name}  (passive={pick['signature'].passive})"
                )
                battle_log.log(
                    f"    Basics: {', '.join(b.name for b in pick['basics'])}"
                )
                battle_log.log(
                    f"    Item:   {pick['item'].name}"
                )
        battle_log.section("BATTLE START")

        team1 = create_team(p1_name, self.p1_picks)
        team2 = create_team(p2_name, self.p2_picks)
        self.battle = BattleState(team1=team1, team2=team2)
        self.battle_log_scroll = 0
        apply_passive_stats(team1, self.battle)
        apply_passive_stats(team2, self.battle)
        self.phase = "battle"
        # LAN clients are driven entirely by host state_updates — they never run the ticker.
        if self.game_mode == "lan_client":
            self._tk = []
        else:
            self._tk = [
                {"k": "text", "msg": "Battle begins!", "dur": 2.0},
                {"k": "next_round"},
            ]

    def _enter_round_start(self):
        """Begin a new round: check for extra swap phase or go straight to action selection."""
        # Apply start-of-round effects (e.g. Briar Rose Curse of Sleeping)
        apply_round_start_effects(self.battle)
        # Check if round 1 extra swap applies
        if self.battle.r1_extra_swap_player is not None:
            esp = self.battle.r1_extra_swap_player
            if self._is_lan() and esp == 2 and self.game_mode == "lan_host":
                # Client's extra swap — notify them, host waits
                self.phase = "extra_swap_p2"
                self._init_extra_swap(2)
                self._lan_send_state(phase="extra_swap_p2")
            else:
                self.phase = f"pass_to_extra_swap_p{esp}"
        else:
            self._enter_action_selection(self.battle.init_player)

    def _enter_action_selection(self, player_num):
        self.selecting_player = player_num
        team = self.battle.get_team(player_num)
        # Build ordered list of (unit, is_extra) tuples.
        # Units with extra_actions_now > 0 (from Rabbit Hole previous round)
        # get a second slot so the player pre-plans their extra action.
        self.selection_order = []
        for slot in CLOCKWISE_ORDER:
            unit = team.get_slot(slot)
            if unit and not unit.ko:
                self.selection_order.append((unit, False))
                if unit.extra_actions_now > 0:
                    self.selection_order.append((unit, True))
        # Clear existing queues for this player
        for unit in team.members:
            unit.queued = None
            unit.queued2 = None
        self.battle.swap_used_this_turn = False
        self.current_is_extra = False

        if self._is_lan():
            self._init_player_resolved = False
            self.phase = "select_actions"
            if self.game_mode == "lan_host":
                if player_num == 2:
                    # Client's turn — notify them
                    self._lan_send_state(phase="select_actions", extra={"selecting_player": 2})
                    # Host shows waiting UI (current_actor stays None)
                else:
                    # Host's own turn
                    self._advance_selection()
            # lan_client: _advance_selection called from _handle_lan_client_msg
        else:
            # New ticker flow: go directly to select_actions (no pass screen needed)
            self.phase = "select_actions"
            self._advance_selection()

    # ─────────────────────────────────────────────────────────────────────────
    # PASS SCREEN ROUTING
    # ─────────────────────────────────────────────────────────────────────────

    def _advance_from_pass(self):
        p = self.phase

        if p == "pass_to_team_p2":
            self._start_team_select(2)

        elif p.startswith("pass_to_extra_swap_p"):
            player = int(p[-1])
            self.phase = f"extra_swap_p{player}"
            self._init_extra_swap(player)

        elif p.startswith("pass_to_select_p"):
            player = int(p[-1])
            self._init_player_resolved = False   # reset once second player starts selecting
            self.phase = "select_actions"
            self.selecting_player = player
            self._advance_selection()

        elif p == "pass_to_resolve":
            # Show a brief "Actions Resolving" pause before executing (skip for LAN)
            if self._is_lan():
                self.phase = "resolving"
                self._do_single_resolution(self._resolving_player)
            else:
                self.phase = "actions_resolving"

        elif p == "pass_to_round_end":
            self.phase = "end_round"
            self._do_end_round()

        elif p.startswith("pass_to_extra_action_p"):
            player = int(p[-1])
            self.phase = f"extra_action_p{player}"

    # ─────────────────────────────────────────────────────────────────────────
    # EXTRA SWAP PHASE (round 1 initiative loser)
    # ─────────────────────────────────────────────────────────────────────────

    def _init_extra_swap(self, player):
        self._extra_swap_player  = player
        self._extra_swap_pending = None  # first unit clicked
        self._extra_swap_done    = False

    def _handle_extra_swap_click(self, pos):
        # Click a unit to select for swapping; click a second unit to swap
        team = self.battle.get_team(self._extra_swap_player)
        rects = SLOT_RECTS_P1 if self._extra_swap_player == 1 else SLOT_RECTS_P2
        for slot, rect in rects.items():
            if rect.collidepoint(pos):
                unit = team.get_slot(slot)
                if unit is None:
                    continue
                if self._extra_swap_pending is None:
                    self._extra_swap_pending = unit
                else:
                    if self._extra_swap_pending != unit:
                        do_swap(self._extra_swap_pending, unit, team, self.battle)
                        self._extra_swap_done = True
                        if self.game_mode == "lan_client":
                            idx_a = team.members.index(self._extra_swap_pending)
                            idx_b = team.members.index(unit)
                            self._lan_send({"type": "extra_swap_ready", "slot_a": idx_a, "slot_b": idx_b})
                            self.phase = "lan_waiting"
                            return
                        # Return to battle ticker — it has the next steps queued
                        self.phase = "battle"
                    else:
                        self._extra_swap_pending = None
                return

        # Done button (skip swap)
        if hasattr(self, '_extra_swap_skip_btn') and \
                self._extra_swap_skip_btn.collidepoint(pos):
            if self.game_mode == "lan_client":
                self._lan_send({"type": "extra_swap_ready"})
                self.phase = "lan_waiting"
                return
            self.battle.log_add(f"P{self._extra_swap_player} passed on free swap.")
            # Return to battle ticker — it has the next steps queued
            self.phase = "battle"

    # ─────────────────────────────────────────────────────────────────────────
    # ACTION SELECTION
    # ─────────────────────────────────────────────────────────────────────────

    def _advance_selection(self):
        """Move to the next unqueued actor (or extra-action slot), or finish."""
        # Count how many non-extra actors have already been queued this selection phase
        n_queued = sum(1 for (u, ie) in self.selection_order if not ie and u.queued is not None)
        for (unit, is_extra) in self.selection_order:
            if unit.ko:
                continue
            needs_queue = (unit.queued2 is None) if is_extra else (unit.queued is None)
            if needs_queue:
                self.current_actor = unit
                self.current_is_extra = is_extra
                self.pending_action = None
                self.selection_sub = "pick_action"
                return
        # All units have actions queued → done with this player
        self._finish_selection()

    def _on_action_queued(self):
        """Called after an action has been stored. Routes to resolve or next slot."""
        if self.phase.startswith("extra_action_p"):
            self._resolve_stitch_extra_and_continue()
        else:
            if not self.current_is_extra:
                just_queued = self.current_actor.queued
                if just_queued and just_queued.get("type") == "ability":
                    self._maybe_show_tutorial(
                        "ability_selected",
                        "Abilities change their effects depending on whether the user is "
                        "frontline or backline when they resolve.")
            self._advance_selection()

    def _swap_queued_this_turn(self):
        """True if any team member has already queued a swap this turn."""
        team = self.battle.get_team(self.selecting_player)
        return any(u.queued and u.queued.get("type") == "swap" for u in team.members)

    def _set_queued(self, actor, action_dict):
        """Store action into queued or queued2 depending on current_is_extra."""
        action_dict["queued_from_slot"] = actor.slot
        if self.current_is_extra:
            if actor.queued2 is not None:
                return  # already has an extra action queued; ignore duplicate
            actor.queued2 = action_dict
        else:
            if actor.queued is not None:
                return  # already has an action queued; ignore duplicate
            actor.queued = action_dict
        # Log queued action to battle log panel only (not shown in moving ticker)
        if self.battle:
            atype = action_dict.get("type", "")
            if atype == "item":
                t = action_dict.get("target")
                tname = t.name if t else "self"
                desc = f"{actor.item.name} → {tname}"
            else:
                desc = describe_action(action_dict)
            self.battle.log_noshow(f"[Queued] {actor.name}: {desc}")

    def _finish_selection(self):
        """Selection done: route to this player's resolution phase."""
        if self.game_mode == "lan_client":
            # Serialize all queued P2 actions and send to host
            team = self.battle.team2
            enemy = self.battle.team1
            actions = []
            for i, unit in enumerate(team.members):
                if unit.queued is not None:
                    actions.append(self._serialize_action(unit.queued, i, team, enemy, False))
                if unit.queued2 is not None:
                    actions.append(self._serialize_action(unit.queued2, i, team, enemy, True))
            self._lan_send({"type": "actions_ready", "actions": actions})
            self.phase = "lan_waiting"
            return

        # In the new flow, each player selects then immediately resolves.
        # init player → resolve init → (review) → second player selects → resolve second → end round
        self._resolving_player = self.selecting_player
        self.phase = "battle"

    def _unit_at_pos(self, pos):
        """Return the CombatantState whose formation box contains pos, or None."""
        for team, rects in ((self.battle.team1, SLOT_RECTS_P1),
                             (self.battle.team2, SLOT_RECTS_P2)):
            for slot, rect in rects.items():
                if rect.collidepoint(pos):
                    # Prefer alive unit at slot; fall back to KO'd for card viewing
                    return (next((m for m in team.members if m.slot == slot and not m.ko), None)
                            or next((m for m in team.members if m.slot == slot), None))
        return None

    def _restart_selection(self):
        """Clear all queued actions for the current player and restart selection."""
        team = self.battle.get_team(self.selecting_player)
        for unit in team.members:
            unit.queued  = None
            unit.queued2 = None
        self.battle.swap_used_this_turn = False
        self.current_is_extra = False
        self._advance_selection()

    def _go_back_one_selection(self):
        """Cancel current sub-state or unqueue the previous actor and re-open their selection."""
        if self.selection_sub == "pick_target":
            self.selection_sub = "pick_action"
            self.pending_action = None
            return
        # In pick_action: find the most recently queued actor and unqueue them
        for unit, is_extra in reversed(self.selection_order):
            if unit.ko:
                continue
            if is_extra and unit.queued2 is not None:
                unit.queued2 = None
                self.current_actor = unit
                self.current_is_extra = True
                self.pending_action = None
                self.selection_sub = "pick_action"
                return
            if not is_extra and unit.queued is not None:
                unit.queued = None
                self.current_actor = unit
                self.current_is_extra = False
                self.pending_action = None
                self.selection_sub = "pick_action"
                return
        # Nothing to go back to — no-op

    def _handle_action_select_click(self, pos):
        # ── Close the detail panel ───────────────────────────────────────────
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return

        # ── Clear-queue button ───────────────────────────────────────────────
        if getattr(self, '_last_clear_btn', None) and \
                self._last_clear_btn.collidepoint(pos):
            self._restart_selection()
            return

        # ── Formation area (x < 570) → target pick or detail card ──────────
        if pos[0] < 570:
            if self.selection_sub == "pick_target":
                self._handle_pick_target(pos)
            else:
                unit = self._unit_at_pos(pos)
                if unit:
                    self._detail_unit = None if self._detail_unit is unit else unit
            return

        # ── Right side: action or target selection ───────────────────────────
        if self.selection_sub == "pick_action":
            self._handle_pick_action(pos)
        elif self.selection_sub == "pick_target":
            self._handle_pick_target(pos)

    def _handle_pick_action(self, pos):
        actor = self.current_actor
        team  = self.battle.get_team(self.selecting_player)
        is_last = len(team.alive()) == 1 and team.alive()[0] == actor

        for rect, action_dict in self._last_action_buttons:
            if rect.collidepoint(pos):
                atype = action_dict["type"]

                if atype == "back":
                    self._go_back_one_selection()
                    return

                if atype == "skip":
                    self._set_queued(actor, {"type": "skip"})
                    self._on_action_queued()
                    return

                if atype == "swap":
                    if not self.battle.swap_used_this_turn and not self._swap_queued_this_turn():
                        self.pending_action = {"type": "swap", "target": None}
                        self.selection_sub = "pick_target"
                    return

                if atype == "ability":
                    ability = action_dict["ability"]
                    mode = ability.frontline if actor.slot == SLOT_FRONT \
                           else ability.backline
                    if mode.spread:
                        # Spread doesn't need a target choice
                        self._set_queued(actor, {"type": "ability", "ability": ability,
                                                 "target": None})
                        self._on_action_queued()
                        return
                    # Check if targets are needed
                    targets = get_legal_targets(
                        self.battle, self.selecting_player, actor, ability)
                    if not targets:
                        self.battle.log_add(
                            f"No legal targets for {ability.name}.")
                        return
                    if len(targets) == 1 and (
                            mode.guard_all_allies or mode.guard_frontline_ally
                            or mode.heal_self > 0
                            or targets[0] is actor):
                        # Auto-target self/frontline
                        self._set_queued(actor, {"type": "ability", "ability": ability,
                                                  "target": targets[0]})
                        self._on_action_queued()
                        return
                    self.pending_action = {
                        "type": "ability",
                        "ability": ability,
                        "target": None,
                        "substep": "pick_primary",
                    }
                    self.selection_sub = "pick_target"
                    role = actor.role
                    if role == "ranged":
                        self._maybe_show_tutorial(
                            "target_ranged",
                            "While in the backline, ranged adventurers can only target the enemy "
                            "across from them and the frontline. In the frontline however, they "
                            "can target any enemy. Be careful though, after three abilities, "
                            "they must recharge for one round.")
                    elif role == "melee":
                        self._maybe_show_tutorial(
                            "target_melee",
                            "Melee adventurers can only target the frontline, and most melee "
                            "abilities deal no damage from the backline.")
                    elif role in ("noble", "warlock"):
                        self._maybe_show_tutorial(
                            "target_mixed",
                            "Mixed adventurers are melee while in the frontline and ranged while "
                            "in the backline. They only increment ranged recharge when using "
                            "abilities from the backline.")
                    return

                if atype == "item":
                    targets = get_legal_item_targets(
                        self.battle, self.selecting_player, actor)
                    if not targets:
                        self.battle.log_add(f"{actor.name} cannot use {actor.item.name}.")
                        return
                    if len(targets) == 1:
                        self._set_queued(actor, {"type": "item", "target": targets[0]})
                        self._on_action_queued()
                        return
                    self.pending_action = {"type": "item", "target": None}
                    self.selection_sub = "pick_target"
                    return

    def _handle_pick_target(self, pos):
        if not self.pending_action:
            return

        actor = self.current_actor
        atype = self.pending_action["type"]

        if atype == "swap":
            # Target is an ally
            team  = self.battle.get_team(self.selecting_player)
            rects = SLOT_RECTS_P1 if self.selecting_player == 1 else SLOT_RECTS_P2
            for slot, rect in rects.items():
                if rect.collidepoint(pos):
                    unit = team.get_slot(slot)
                    if unit and unit != actor:
                        self._set_queued(actor, {"type": "swap", "target": unit})
                        self._on_action_queued()
                        return

        elif atype == "ability":
            ability = self.pending_action["ability"]
            substep = self.pending_action.get("substep", "pick_primary")
            if substep == "subterfuge_swap_target":
                primary = self.pending_action.get("target")
                targets = get_subterfuge_swap_targets(
                    self.battle, self.selecting_player, primary
                )
            else:
                targets = get_legal_targets(
                    self.battle, self.selecting_player, actor, ability)

            # Use fixed on-screen team lanes (P1 bottom, P2 top) so click
            # resolution matches target highlighting exactly.
            all_rects = {}
            all_rects.update({u: SLOT_RECTS_P1.get(u.slot) for u in self.battle.team1.alive()})
            all_rects.update({u: SLOT_RECTS_P2.get(u.slot) for u in self.battle.team2.alive()})
            for unit, rect in all_rects.items():
                if rect and rect.collidepoint(pos) and unit in targets:
                    if ability.id == "subterfuge" and substep != "subterfuge_swap_target":
                        self.pending_action["target"] = unit
                        self.pending_action["substep"] = "subterfuge_swap_target"
                        return
                    action = {"type": "ability", "ability": ability, "target": unit}
                    if ability.id == "subterfuge":
                        action["target"] = self.pending_action.get("target")
                        action["swap_target"] = unit
                    self._set_queued(actor, action)
                    self._on_action_queued()
                    return

        elif atype == "item":
            targets = get_legal_item_targets(
                self.battle, self.selecting_player, actor)
            if not targets:
                return
            all_rects = {}
            all_rects.update({u: SLOT_RECTS_P1.get(u.slot) for u in self.battle.team1.alive()})
            all_rects.update({u: SLOT_RECTS_P2.get(u.slot) for u in self.battle.team2.alive()})
            for unit, rect in all_rects.items():
                if rect and rect.collidepoint(pos) and unit in targets:
                    self._set_queued(actor, {"type": "item", "target": unit})
                    self._on_action_queued()
                    return

        # Cancel: click anywhere else goes back to pick_action
        # (handled by absence of match above)

    # ─────────────────────────────────────────────────────────────────────────
    # RESOLUTION
    # ─────────────────────────────────────────────────────────────────────────

    def _do_single_resolution(self, player_num):
        """Begin step-through resolution for player_num's queued actions."""
        self._begin_step_resolution(player_num)

    def _begin_step_resolution(self, player_num):
        """Resolve player_num's queued actions. Steps through one at a time unless fast_resolution or LAN."""
        self._action_step_player = player_num
        self.battle.log_add(f"─── P{player_num} Actions ───")

        if self._is_lan() or (self.campaign_profile and self.campaign_profile.fast_resolution):
            # LAN/Fast mode: resolve everything at once
            resolve_player_turn(self.battle, player_num)
            self._finish_step_resolution()
            return

        team = self.battle.get_team(player_num)
        order = [team.get_slot(slot) for slot in CLOCKWISE_ORDER]
        self._action_step_queue = []
        for unit in order:
            if unit is None or unit.ko or unit.queued is None:
                continue
            self._action_step_queue.append((unit, player_num, False))
            # Rabbit Hole pre-planned extra action
            if unit.queued2 is not None and unit.extra_actions_now > 0:
                self._action_step_queue.append((unit, player_num, True))
        self._resolve_next_step()

    def _resolve_next_step(self):
        """Resolve the next action in the step queue, then show action_result."""
        while self._action_step_queue:
            unit, player_num, is_queued2 = self._action_step_queue[0]
            if unit.ko:
                self._action_step_queue.pop(0)
                continue
            self._action_step_queue.pop(0)
            self._action_log_start = len(self.battle.log)
            if is_queued2:
                unit.extra_actions_now -= 1
                saved = unit.queued
                unit.queued = unit.queued2
                unit.queued2 = None
                resolve_queued_action(unit, player_num, self.battle)
                unit.queued = saved
            else:
                resolve_queued_action(unit, player_num, self.battle)
                unit.queued = None
            self._action_step_unit = unit
            self._action_step_player = player_num
            self.battle_log_scroll = 0  # scroll to bottom to show latest
            self.phase = "action_result"
            return
        # All actions done — run finish logic
        self._finish_step_resolution()

    def _finish_step_resolution(self):
        """After all step-through actions are done, route to the appropriate next phase."""
        player_num = self._action_step_player
        init = self.battle.init_player

        if self.battle.winner:
            self.phase = "resolve_done"
            return

        # Detect Stitch In Time extras for this player
        self._extra_action_queue = [
            (player_num, unit)
            for unit in self.battle.get_team(player_num).alive()
            if unit.extra_actions_now > 0 and unit.queued2 is None
        ]

        if player_num == init:
            self._init_player_resolved = True
            if self._extra_action_queue:
                self._start_next_stitch_extra()
                return
            self.phase = "resolve_done"
        else:
            if self._extra_action_queue:
                self._start_next_stitch_extra()
                return
            if not self.battle.winner:
                self.battle.log_add("─── End of Round ───")
                do_end_round(self.battle)
            self.phase = "resolve_done"

    def _start_next_stitch_extra(self):
        """Start the next pending Stitch In Time extra-action selection."""
        if not self._extra_action_queue:
            if self._init_player_resolved and not self.battle.winner:
                # Init player's extras done — show resolve_done for review
                self.phase = "resolve_done"
            else:
                # Second player's extras done — end round
                if not self.battle.winner:
                    self.battle.log_add("─── End of Round ───")
                    do_end_round(self.battle)
                self.phase = "resolve_done"
            return
        pnum, unit = self._extra_action_queue[0]
        self.selecting_player = pnum
        self.current_actor    = unit
        self.current_is_extra = True
        self.selection_sub    = "pick_action"
        self.pending_action   = None
        if not self._is_lan():
            self.phase = f"extra_action_p{pnum}"
        else:
            self.phase = f"pass_to_extra_action_p{pnum}"

    def _resolve_stitch_extra_and_continue(self):
        """Resolve the queued2 extra action for the current Stitch In Time unit."""
        unit = self.current_actor
        pnum = self.selecting_player
        log_before = len(self.battle.log)
        if unit.queued2 is not None:
            unit.extra_actions_now -= 1
            saved = unit.queued
            unit.queued  = unit.queued2
            unit.queued2 = None
            resolve_queued_action(unit, pnum, self.battle)
            unit.queued = saved
        else:
            unit.extra_actions_now = 0
        self._extra_action_queue.pop(0)
        new_lines = self.battle.log[log_before:]
        inject = [{"k": "text", "msg": line, "dur": 2.0}
                  for line in new_lines if not line.startswith("\x01")]
        if self.battle.winner:
            inject.append({"k": "battle_end"})
        elif self._extra_action_queue:
            inject.append({"k": "stitch_select"})
        else:
            if self._resolving_player == self.battle.init_player:
                self._init_player_resolved = True
        self._tk[0:0] = inject
        self.phase = "battle"

    def _do_end_round(self):
        pass  # Already handled inline in _do_full_resolution

    # ─────────────────────────────────────────────────────────────────────────
    # DRAW
    # ─────────────────────────────────────────────────────────────────────────

    def draw(self, mouse_pos):
        surf = self._canvas
        p = self.phase

        if p == "menu":
            player_level = max(0, self.campaign_profile.highest_quest_cleared) if self.campaign_profile else 0
            _new_cat = bool(self.campaign_profile and self.campaign_profile.new_unlocks)
            s, pr, tb, cat, st, e = draw_main_menu(surf, mouse_pos, player_level, new_catalog_unlocks=_new_cat)
            self._last_menu_btns = (s, pr, tb, cat, st, e)

        elif p == "practice_menu":
            btns = draw_practice_menu(surf, mouse_pos)
            self._last_practice_btns = btns

        elif p == "teambuilder":
            profile = self.campaign_profile or CampaignProfile()
            btns = draw_teambuilder(surf, profile.saved_teams, mouse_pos, profile)
            self._last_teambuilder_btns = btns
            # Rename overlay drawn on top when active
            if self._renaming_team_slot is not None:
                overlay_btns = draw_rename_overlay(surf, mouse_pos, self._rename_text)
                self._last_rename_overlay_btns = overlay_btns

        elif p == "catalog":
            profile = self.campaign_profile or CampaignProfile()
            _catalog_desc_hover = []
            btns = draw_catalog(
                surf, mouse_pos,
                active_tab=self._catalog_tab,
                selected_idx=self._catalog_selected,
                scroll=self._catalog_scroll,
                profile=profile,
                roster=ROSTER,
                class_basics=CLASS_BASICS,
                items=ITEMS,
                status_rects_out=_catalog_desc_hover,
                filters=self._catalog_filters.get(self._catalog_tab, {}),
            )
            self._last_catalog_btns = btns
            for _r, _kind in _catalog_desc_hover:
                if _r.collidepoint(mouse_pos):
                    draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                    break

        elif p == "settings":
            btns = draw_settings_screen(surf, mouse_pos, self._confirm_reset,
                                        fast_resolution=self.campaign_profile.fast_resolution,
                                        tutorials_enabled=self.campaign_profile.tutorials_enabled)
            self._last_settings_btns = btns

        elif p == "story_team_select":
            quest = QUEST_TABLE.get(self.campaign_quest_id)
            profile = self.campaign_profile or CampaignProfile()
            btns = draw_story_team_select(surf, profile.saved_teams, mouse_pos, quest)
            self._last_story_team_btns = btns

        elif p == "pre_battle_edit":
            _PRE_BATTLE_DETAIL_RECT = pygame.Rect(700, 80, 680, 760)
            # Use campaign-filtered roster/items when in campaign mode
            if self.game_mode in ("campaign", "teambuilder") and hasattr(self, "_campaign_roster"):
                active_items      = self._campaign_items
                active_cls_basics = self._campaign_basics
            else:
                active_items      = ITEMS
                active_cls_basics = CLASS_BASICS

            _sig_tier = (
                self.campaign_profile.sig_tier
                if self.game_mode in ("campaign", "teambuilder") and self.campaign_profile
                else 3
            )
            _lan_wait = self._is_lan() and self._lan_pbe_local_ready
            _confirm_lbl = "Waiting for opponent…" if _lan_wait else "Ready for Battle →"
            _team_desc_hover = []
            clicks = draw_team_select_screen(
                surf,
                player_name="Pre-Battle Setup",
                roster=[],
                selected_idx=self.roster_selected,
                team_picks=self.team_picks,
                sub_phase=self.sub_phase,
                current_adv_idx=self.current_adv_idx,
                sig_choice=self.sig_choice,
                basic_choices=self.basic_choices,
                item_choice=self.item_choice,
                items=active_items,
                class_basics=active_cls_basics,
                mouse_pos=mouse_pos,
                scroll_offset=self.team_select_scroll,
                team_slot_selected=self.team_slot_selected,
                sig_tier=_sig_tier,
                twists_unlocked=(
                    self.campaign_profile.twists_unlocked
                    if self.game_mode in ("campaign", "teambuilder") and self.campaign_profile
                    else True
                ),
                status_rects_out=_team_desc_hover,
                confirm_label=_confirm_lbl,
                pre_battle_mode=True,
                enemy_picks=self._pbe_enemy_picks,
                focused_slot=self._focused_slot,
            )
            self.team_select_scroll = min(
                self.team_select_scroll,
                clicks.get("scroll_max", 0),
            )
            self._last_team_clicks = clicks
            for _r, _kind in _team_desc_hover:
                if _r.collidepoint(mouse_pos):
                    draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                    break
            if self._detail_unit is not None:
                _dh = []
                close_btn = draw_combatant_detail(surf, self._detail_unit,
                                                  rect=_PRE_BATTLE_DETAIL_RECT,
                                                  status_rects_out=_dh)
                self._detail_close_btn = close_btn
                for _r, _kind in _dh:
                    if _r.collidepoint(mouse_pos):
                        draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                        break
            else:
                self._detail_close_btn = None

        elif p == "team_select":
            # Use campaign-filtered roster/items when in campaign/teambuilder mode
            if self.game_mode in ("campaign", "teambuilder") and hasattr(self, "_campaign_roster"):
                active_roster     = self._campaign_roster
                active_items      = self._campaign_items
                active_cls_basics = self._campaign_basics
            else:
                active_roster     = ROSTER
                active_items      = ITEMS
                active_cls_basics = CLASS_BASICS

            # roster_selected is a defn object (or None)
            sel_idx = self.roster_selected

            _sig_tier = (
                self.campaign_profile.sig_tier
                if self.game_mode in ("campaign", "teambuilder") and self.campaign_profile
                else 3
            )
            if self._editing_single_member and self.team_picks and self.current_adv_idx < len(self.team_picks):
                _adv_name = self.team_picks[self.current_adv_idx].get("definition")
                _adv_name = _adv_name.name if _adv_name else f"Member {self.current_adv_idx + 1}"
                _panel_title = f"Edit Sets — {_adv_name}"
            else:
                _panel_title = f"Player {self.building_player}"
            _team_desc_hover = []
            _confirm_label = "Save Party" if self.game_mode == "teambuilder" else "Ready"
            clicks = draw_team_select_screen(
                surf,
                player_name=_panel_title,
                roster=active_roster,
                selected_idx=sel_idx,
                team_picks=self.team_picks,
                sub_phase=self.sub_phase,
                current_adv_idx=self.current_adv_idx,
                sig_choice=self.sig_choice,
                basic_choices=self.basic_choices,
                item_choice=self.item_choice,
                items=active_items,
                class_basics=active_cls_basics,
                mouse_pos=mouse_pos,
                scroll_offset=self.team_select_scroll,
                team_slot_selected=self.team_slot_selected,
                sig_tier=_sig_tier,
                twists_unlocked=(
                    self.campaign_profile.twists_unlocked
                    if self.game_mode in ("campaign", "teambuilder") and self.campaign_profile
                    else True
                ),
                status_rects_out=_team_desc_hover,
                confirm_label=_confirm_label,
                focused_slot=self._focused_slot,
            )
            self.team_select_scroll = min(
                self.team_select_scroll,
                clicks.get("scroll_max", 0),
            )
            self._last_team_clicks = clicks
            for _r, _kind in _team_desc_hover:
                if _r.collidepoint(mouse_pos):
                    draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                    break
            # Draw import modal on top if open
            if self._import_modal_open:
                _modal_clicks = draw_import_modal(
                    surf, self._import_modal_text, self._import_modal_error, mouse_pos)
                self._last_import_modal_clicks = _modal_clicks

        elif p.startswith("pass_"):
            msg, next_who = self._pass_screen_info(p)
            btn = draw_pass_screen(surf, next_who, msg, mouse_pos)
            self._last_pass_btn = btn

        elif p == "battle":
            self._draw_battle(surf, mouse_pos)

        elif p == "battle_start":
            self._draw_battle_start(surf, mouse_pos)

        elif p == "end_of_round":
            self._draw_end_of_round(surf, mouse_pos)

        elif p == "actions_resolving":
            self._draw_actions_resolving(surf, mouse_pos)

        elif p.startswith("extra_swap_p"):
            self._draw_extra_swap(surf, mouse_pos)

        elif p == "select_actions" or p.startswith("extra_action_p"):
            self._draw_select_actions(surf, mouse_pos)

        elif p in ("resolving", "resolve_done", "action_result"):
            self._draw_resolving(surf, mouse_pos)

        elif p == "result":
            a, b = draw_result_screen(surf, self.battle, mouse_pos)
            self._last_result_btns = (a, b)

        elif p == "campaign_mission_select":
            profile = self.campaign_profile or CampaignProfile()
            missions = list(MISSION_TABLE.values())
            btns = draw_campaign_mission_select(surf, missions, mouse_pos, profile)
            self._last_campaign_btns = btns

        elif p == "campaign_quest_select":
            profile = self.campaign_profile or CampaignProfile()
            mission = MISSION_TABLE.get(self.campaign_mission_id)
            if mission:
                first_q, last_q = mission.quest_range
                quests = [QUEST_TABLE[qid] for qid in range(first_q, last_q + 1)
                          if qid in QUEST_TABLE and QUEST_TABLE[qid].enemy_lineup is not None]
                btns = draw_quest_select(surf, mission, quests, mouse_pos, profile)
                self._last_campaign_btns = btns

        elif p == "campaign_pre_quest":
            quest = QUEST_TABLE.get(self.campaign_quest_id)
            if quest and quest.enemy_lineup:
                mission = MISSION_TABLE.get(quest.mission_id)
                if mission:
                    fq, lq = mission.quest_range
                    quest_pos    = self.campaign_quest_id - fq + 1
                    total_quests = lq - fq + 1
                else:
                    quest_pos, total_quests = 1, 1
                    mission = None
                enemy_picks = build_quest_enemy_team(self.campaign_quest_id)
                _pq_hover = []
                btns = draw_pre_quest(surf, quest, mission, quest_pos, total_quests, enemy_picks, mouse_pos, status_rects_out=_pq_hover)
                self._last_campaign_btns = btns
                for _r, _kind in _pq_hover:
                    if _r.collidepoint(mouse_pos):
                        draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                        break
                if self._detail_unit is not None:
                    _dh = []
                    close_btn = draw_combatant_detail(surf, self._detail_unit, status_rects_out=_dh)
                    self._detail_close_btn = close_btn
                    for _r, _kind in _dh:
                        if _r.collidepoint(mouse_pos):
                            draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                            break
                else:
                    self._detail_close_btn = None

        elif p == "campaign_post_quest":
            quest = QUEST_TABLE.get(self.campaign_quest_id)
            if quest:
                btns = draw_post_quest(
                    surf, quest,
                    won=self._campaign_won_quest,
                    rewards=quest.rewards if self._campaign_won_quest else {},
                    mouse_pos=mouse_pos,
                )
                self._last_campaign_btns = btns

        elif p == "campaign_complete":
            btns = draw_campaign_complete(surf, mouse_pos)
            self._last_campaign_btns = btns

        elif p == "lan_lobby":
            btns = draw_lan_lobby(
                surf, mouse_pos,
                role=self._lan_role,
                ip_input=self._lan_ip_input,
                status=self._lan_status,
                local_ip=self._lan.local_ip() if isinstance(self._lan, net.LANHost) else "",
                connecting=isinstance(self._lan, net.LANClient) and self._lan._connecting,
            )
            self._last_lan_lobby_btns = btns

        elif p in ("lan_waiting", "lan_waiting_teams"):
            if self.battle:
                surf.fill(BG)
                draw_top_bar(surf, self.battle, "Waiting for opponent...")
                draw_formation(surf, self.battle, mouse_pos=mouse_pos)
                draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)
                draw_text(surf, "Waiting for opponent...", 24, TEXT_DIM,
                          WIDTH // 2, HEIGHT - 70, center=True)
                if self._detail_unit is not None:
                    _dh = []
                    close_btn = draw_combatant_detail(surf, self._detail_unit, status_rects_out=_dh)
                    self._detail_close_btn = close_btn
                    for _r, _kind in _dh:
                        if _r.collidepoint(mouse_pos):
                            draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                            break
                else:
                    self._detail_close_btn = None
            else:
                surf.fill(BG)
                draw_text(surf, "Waiting for opponent...", 28, TEXT_DIM,
                          WIDTH // 2, HEIGHT // 2, center=True)

        else:
            surf.fill(BG)
            draw_text(surf, f"Phase: {p}", 24, TEXT, 20, 20)

        # Tutorial popup overlay
        if self._tutorial_pending:
            draw_tutorial_popup(surf, self._tutorial_pending)

        # LAN disconnect overlay
        if self._lan_disconnected and self._is_lan():
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            surf.blit(overlay, (0, 0))
            draw_text(surf, "Opponent Disconnected", 36, RED, WIDTH // 2, HEIGHT // 2 - 40, center=True)
            disc_btn = pygame.Rect(WIDTH // 2 - 120, HEIGHT // 2 + 10, 240, 44)
            draw_button(surf, disc_btn, "Return to Menu", mouse_pos, size=18)
            self._last_disconnect_btn = disc_btn

        # Intro story popup (topmost overlay)
        if self._intro_visible > 0:
            self._intro_lets_go_btn = draw_intro_popup(surf, self._intro_visible, mouse_pos)

    def _pass_screen_info(self, phase_key):
        """Return (message, next_player_name) for the pass screen.

        In single-player mode, next_player_name is returned as "" to suppress
        the 'Pass the device to...' line when there is no second human player.
        """
        rnd = self.battle.round_num if self.battle else 1
        init = self.battle.init_player if self.battle else 1
        sp = self._is_single_player()

        def _who(pnum):
            """Return player label, or "" in single-player (no handoff needed)."""
            return "" if sp else f"Player {pnum}"

        if phase_key == "pass_to_team_p2":
            return "Player 1 has set their party.", _who(2)
        reason = getattr(self.battle, "init_reason", "")
        if phase_key == "pass_to_extra_swap_p1":
            msg = "P1 lost initiative — free swap before round starts."
            if reason:
                msg = f"P2 wins initiative!\n{reason}\nP1 gets a free formation swap first."
            return msg, _who(1)
        if phase_key == "pass_to_extra_swap_p2":
            msg = "P2 lost initiative — free swap before round starts."
            if reason:
                msg = f"P1 wins initiative!\n{reason}\nP2 gets a free formation swap first."
            return msg, _who(2)
        if phase_key == "pass_to_select_p1":
            if self._init_player_resolved:
                return f"P{init} has acted. P1 — plan your response!", _who(1)
            msg = f"Round {rnd} — P1 acts first! Plan your actions!"
            if reason:
                msg = f"Round {rnd} — P1 acts first!\n{reason}"
            return msg, _who(1)
        if phase_key == "pass_to_select_p2":
            if self._init_player_resolved:
                return f"P{init} has acted. P2 — plan your response!", _who(2)
            msg = f"Round {rnd} — P2 acts first! Plan your actions!"
            if reason:
                msg = f"Round {rnd} — P2 acts first!\n{reason}"
            return msg, _who(2)
        if phase_key == "pass_to_resolve":
            p = self._resolving_player or init
            return (f"P{p} locked in — both players watch their actions!",
                    "" if sp else "Both Watch")
        if phase_key.startswith("pass_to_extra_action_p"):
            pnum = phase_key[-1]
            unit = self._extra_action_queue[0][1] if self._extra_action_queue else None
            name = unit.name if unit else "?"
            return (f"Stitch In Time — {name} gets an extra action!",
                    _who(int(pnum)))
        return "Ready?", "" if sp else "Next Player"

    def _draw_battle(self, surf, mouse_pos):
        """Main battle view: always shows formation + log + bottom ticker."""
        surf.fill(BG)
        if not self.battle:
            return
        init = self.battle.init_player
        rnd  = self.battle.round_num
        draw_top_bar(surf, self.battle, f"Round {rnd}  —  P{init} has initiative")
        _status_hover = []
        draw_formation(surf, self.battle, mouse_pos=mouse_pos, status_rects_out=_status_hover)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)

        # Bottom bar: message text
        if self._tk_msg:
            draw_text(surf, self._tk_msg, 20, YELLOW, WIDTH // 2, HEIGHT - 68, center=True)

        # Pass button
        if self._tk_btn_label and self._tk_btn_label != "__tutorial__":
            btn_rect = pygame.Rect(WIDTH // 2 - 130, HEIGHT - 50, 260, 40)
            draw_button(surf, btn_rect, self._tk_btn_label, mouse_pos, size=18,
                        normal=BLUE_DARK, hover=BLUE)
            self._tk_btn_rect = btn_rect
        else:
            self._tk_btn_rect = None

        # Centered overlay box for round-start / initiative announcement
        if self._tk_overlay_msg:
            raw_lines = self._tk_overlay_msg.split("\n")
            box_w = 960
            text_max_w = box_w - 48
            # Expand each raw line using word-wrap (first line larger font)
            display_lines = []  # (text, size, color)
            for i, raw in enumerate(raw_lines):
                if i == 0:
                    display_lines.append((raw, 26, (230, 230, 255)))
                else:
                    wrapped = _wrap_text(raw, 17, text_max_w) or [raw]
                    for wl in wrapped:
                        display_lines.append((wl, 17, (180, 190, 230)))
            line_h = 32
            box_h = 36 + line_h * len(display_lines)
            bx = WIDTH // 2 - box_w // 2
            by = HEIGHT // 2 - box_h // 2
            overlay_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            overlay_surf.fill((10, 10, 30, 210))
            surf.blit(overlay_surf, (bx, by))
            pygame.draw.rect(surf, (100, 140, 220), (bx, by, box_w, box_h), 2, border_radius=6)
            text_y = by + 18
            for text, size, col in display_lines:
                draw_text(surf, text, size, col, WIDTH // 2, text_y, center=True)
                text_y += line_h

        # Status tooltip
        for r, kind in _status_hover:
            if r.collidepoint(mouse_pos):
                draw_status_tooltip(surf, kind, mouse_pos[0], mouse_pos[1])
                break

    def _draw_extra_swap(self, surf, mouse_pos):
        surf.fill(BG)
        player = self._extra_swap_player
        draw_top_bar(surf, self.battle,
                     f"Round 1 Extra Swap — Player {player}")
        _status_hover = []
        draw_formation(surf, self.battle, mouse_pos=mouse_pos,
                       status_rects_out=_status_hover)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)

        # LAN: only interactive for the player whose swap it is
        if self._is_lan() and self._extra_swap_player != self._lan_my_player():
            draw_text(surf, "Waiting for opponent's formation swap...", 22, TEXT_DIM,
                      WIDTH // 2, HEIGHT - 70, center=True)
            return

        draw_text(surf, "Click TWO allies to swap them, or skip.", 20, YELLOW,
                  WIDTH // 2, HEIGHT - 80, center=True)
        if hasattr(self, '_extra_swap_pending') and self._extra_swap_pending:
            draw_text(surf, f"Selected: {self._extra_swap_pending.name}",
                      18, CYAN, WIDTH // 2, HEIGHT - 54, center=True)

        skip_btn = pygame.Rect(WIDTH // 2 - 90, HEIGHT - 48, 180, 40)
        draw_button(surf, skip_btn, "Skip Swap", mouse_pos, size=18)
        self._extra_swap_skip_btn = skip_btn

        # Status tooltip — drawn last
        for r, kind in _status_hover:
            if r.collidepoint(mouse_pos):
                draw_status_tooltip(surf, kind, mouse_pos[0], mouse_pos[1])
                break

    def _draw_select_actions(self, surf, mouse_pos):
        surf.fill(BG)
        if not self.battle:
            return

        # LAN: show waiting overlay when it's the opponent's turn
        if self._is_lan() and self.selecting_player != self._lan_my_player():
            draw_top_bar(surf, self.battle, f"Waiting for P{self.selecting_player}...")
            _lan_sh = []
            draw_formation(surf, self.battle, mouse_pos=mouse_pos, status_rects_out=_lan_sh)
            draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)
            draw_text(surf, "Waiting for opponent to pick their actions...",
                      22, TEXT_DIM, WIDTH // 2, HEIGHT - 70, center=True)
            if self._detail_unit is not None:
                _dh = []
                close_btn = draw_combatant_detail(surf, self._detail_unit, status_rects_out=_dh)
                self._detail_close_btn = close_btn
                for _r, _kind in _dh:
                    if _r.collidepoint(mouse_pos):
                        draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                        break
            else:
                self._detail_close_btn = None
            for r, kind in _lan_sh:
                if r.collidepoint(mouse_pos):
                    draw_status_tooltip(surf, kind, mouse_pos[0], mouse_pos[1])
                    break
            return

        if not self.current_actor:
            return

        actor = self.current_actor
        team  = self.battle.get_team(self.selecting_player)
        is_last = len(team.alive()) == 1 and team.alive()[0] == actor

        rnd = self.battle.round_num
        init = self.battle.init_player
        ai_turn = self._is_single_player() and self._is_ai_player(self.selecting_player)
        if self.selecting_player == init:
            ctx = f"Round {rnd} — Initiative  |  P{self.selecting_player} Selecting Actions"
        else:
            ctx = f"Round {rnd} — Responding  |  P{self.selecting_player} Selecting Actions"
        draw_top_bar(surf, self.battle, ctx)

        # Formation (left)
        valid_targets = []
        if self.selection_sub == "pick_target" and self.pending_action:
            if self.pending_action["type"] == "ability":
                ability = self.pending_action["ability"]
                if self.pending_action.get("substep") == "subterfuge_swap_target":
                    valid_targets = get_subterfuge_swap_targets(
                        self.battle,
                        self.selecting_player,
                        self.pending_action.get("target"),
                    )
                else:
                    valid_targets = get_legal_targets(
                        self.battle, self.selecting_player, actor, ability)
            elif self.pending_action["type"] == "swap":
                valid_targets = [u for u in team.alive() if u != actor]
            elif self.pending_action["type"] == "item":
                valid_targets = team.alive()

        _status_hover = []
        draw_formation(surf, self.battle,
                       selected_unit=actor,
                       valid_targets=valid_targets,
                       mouse_pos=mouse_pos,
                       acting_player=self.selecting_player,
                       status_rects_out=_status_hover)

        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)

        # Detail panel — drawn below formations when a unit is inspected
        if self._detail_unit is not None:
            _dh = []
            close_btn = draw_combatant_detail(surf, self._detail_unit, status_rects_out=_dh)
            self._detail_close_btn = close_btn
            for _r, _kind in _dh:
                if _r.collidepoint(mouse_pos):
                    draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                    break
        else:
            self._detail_close_btn = None

        # Hint: click any unit to view details
        if self._detail_unit is None:
            draw_text(surf, "Click any unit to inspect", 13, TEXT_MUTED,
                      20, BATTLE_DETAIL_RECT.y + 6)

        # Action buttons (drawn first so panel background is laid down)
        if self.selection_sub == "pick_action":
            abilities = actor.all_active_abilities(is_last)
            _twists_ok = (
                self.game_mode not in ("campaign", "teambuilder")
                or not self.campaign_profile
                or self.campaign_profile.twists_unlocked
            )
            valid_abs = [a for a in abilities
                         if can_use_ability(actor, a, team)
                         and (_twists_ok or a.category != "twist")]
            btns = draw_action_menu(
                surf, mouse_pos, actor, valid_abs,
                swap_used=self.battle.swap_used_this_turn or self._swap_queued_this_turn(),
                state_label=f"Slot: {SLOT_LABELS.get(actor.slot, actor.slot)}"
            )
            self._last_action_buttons = btns

        # Queued summary — drawn after action menu so it renders on top
        # x and panel_w match ACTION_PANEL_RECT exactly
        draw_queued_summary(surf, team, 700, self.selecting_player,
                            x=ACTION_PANEL_RECT.x, panel_w=ACTION_PANEL_RECT.width)

        # Clear Queue button (only in main selection phase, not extra-action phase)
        if self.phase == "select_actions":
            team_has_queued = any(
                u.queued is not None or u.queued2 is not None
                for u in team.members if not u.ko
            )
            clear_rect = pygame.Rect(995, 840, 190, 34)
            draw_button(surf, clear_rect, "Clear Queue", mouse_pos, size=15,
                        normal=(55, 30, 30), hover=(80, 40, 40),
                        disabled=not team_has_queued)
            self._last_clear_btn = clear_rect if team_has_queued else None
        else:
            self._last_clear_btn = None

        # Bottom status text
        if ai_turn:
            draw_text(surf, f"P{self.selecting_player} is choosing their actions...",
                      20, TEXT_DIM, WIDTH // 2, HEIGHT - 36, center=True)
        elif self.selection_sub == "pick_action":
            prefix = "EXTRA ACTION — " if self.current_is_extra else ""
            draw_text(surf, f"{prefix}Assigning: {actor.name}", 22, CYAN,
                      WIDTH // 2, HEIGHT - 36, center=True)
        elif self.selection_sub == "pick_target":
            prompt = "Click a valid target (highlighted)"
            if (self.pending_action and self.pending_action.get("type") == "ability"
                    and self.pending_action.get("ability").id == "subterfuge"
                    and self.pending_action.get("substep") == "subterfuge_swap_target"):
                prompt = "Subterfuge: choose who swaps with the first target"
            draw_text(surf, prompt, 22, YELLOW,
                      WIDTH // 2, HEIGHT - 36, center=True)
            draw_text(surf, "(Click elsewhere or press ESC to cancel; ESC again to concede)", 16,
                      TEXT_MUTED, WIDTH // 2, HEIGHT - 16, center=True)
            self._last_action_buttons = []

        # Status tooltip — drawn last so it appears on top of everything
        for r, kind in _status_hover:
            if r.collidepoint(mouse_pos):
                draw_status_tooltip(surf, kind, mouse_pos[0], mouse_pos[1])
                break

    def _draw_actions_resolving(self, surf, mouse_pos):
        surf.fill(BG)
        if not self.battle:
            return
        rp = self._resolving_player
        draw_top_bar(surf, self.battle, f"P{rp} — Actions Selected")
        draw_formation(surf, self.battle, mouse_pos=mouse_pos)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)
        draw_text(surf, "Actions Selected", 34, (200, 200, 80),
                  WIDTH // 2, HEIGHT - 90, center=True)
        cont_btn = pygame.Rect(WIDTH // 2 - 130, HEIGHT - 60, 260, 44)
        draw_button(surf, cont_btn, "Resolve Actions →", mouse_pos, size=18,
                    normal=BLUE_DARK, hover=BLUE)
        self._last_actions_resolving_btn = cont_btn

    def _draw_battle_start(self, surf, mouse_pos):
        surf.fill(BG)
        if not self.battle:
            return
        t1 = self.battle.team1.player_name
        t2 = self.battle.team2.player_name
        draw_top_bar(surf, self.battle, f"{t1}  vs  {t2}")
        draw_formation(surf, self.battle, mouse_pos=mouse_pos)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)
        init = self.battle.init_player
        reason = getattr(self.battle, "init_reason", "")
        esp = self.battle.r1_extra_swap_player
        # Stack text lines above the button, anchored from the bottom up
        btn_top = HEIGHT - 50
        cont_btn = pygame.Rect(WIDTH // 2 - 130, btn_top, 260, 40)
        y = btn_top - 22
        if esp:
            draw_text(surf, f"P{esp} receives a free formation swap before actions.", 15, CYAN,
                      WIDTH // 2, y, center=True)
            y -= 22
        if reason:
            draw_text(surf, reason, 15, TEXT_DIM, WIDTH // 2, y, center=True)
            y -= 28
        draw_text(surf, f"Round 1 — P{init} has initiative!", 22, YELLOW,
                  WIDTH // 2, y, center=True)
        if self.game_mode == "lan_client":
            draw_text(surf, "Waiting for host...", 18, TEXT_DIM, WIDTH // 2, btn_top + 10, center=True)
            self._last_battle_start_btn = pygame.Rect(0, 0, 0, 0)  # non-clickable
        else:
            draw_button(surf, cont_btn, "Begin Round 1 →", mouse_pos, size=18,
                        normal=BLUE_DARK, hover=BLUE)
            self._last_battle_start_btn = cont_btn

    def _draw_end_of_round(self, surf, mouse_pos):
        surf.fill(BG)
        if not self.battle:
            return
        next_rnd = self.battle.round_num
        init = self.battle.init_player
        reason = getattr(self.battle, "init_reason", "")
        esp = self.battle.r1_extra_swap_player
        draw_top_bar(surf, self.battle, f"Round {next_rnd}")
        draw_formation(surf, self.battle, mouse_pos=mouse_pos)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)
        btn_top = HEIGHT - 50
        cont_btn = pygame.Rect(WIDTH // 2 - 130, btn_top, 260, 40)
        y = btn_top - 22
        if esp:
            draw_text(surf, f"P{esp} receives a free formation swap before actions.", 15, CYAN,
                      WIDTH // 2, y, center=True)
            y -= 22
        if reason:
            draw_text(surf, reason, 15, TEXT_DIM, WIDTH // 2, y, center=True)
            y -= 28
        draw_text(surf, f"Round {next_rnd} — P{init} has initiative!", 22, YELLOW,
                  WIDTH // 2, y, center=True)
        if self.game_mode == "lan_client":
            draw_text(surf, "Waiting for host...", 18, TEXT_DIM, WIDTH // 2, btn_top + 10, center=True)
            self._last_eor_btn = pygame.Rect(0, 0, 0, 0)  # non-clickable
        else:
            draw_button(surf, cont_btn, f"Begin Round {next_rnd} →", mouse_pos, size=18,
                        normal=BLUE_DARK, hover=BLUE)
            self._last_eor_btn = cont_btn

    def _draw_initiative_result(self, surf, mouse_pos):
        surf.fill(BG)
        if not self.battle:
            return
        init = self.battle.init_player
        rnd = self.battle.round_num
        draw_top_bar(surf, self.battle, f"Round {rnd} — Initiative")
        draw_formation(surf, self.battle, mouse_pos=mouse_pos)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)
        reason = getattr(self.battle, "init_reason", "")
        draw_text(surf, f"P{init} acts first this round!", 26, YELLOW,
                  WIDTH // 2, HEIGHT - 96, center=True)
        if reason:
            draw_text(surf, reason, 17, TEXT_DIM, WIDTH // 2, HEIGHT - 66, center=True)
        if self.game_mode == "lan_client":
            draw_text(surf, "Waiting for host...", 18, TEXT_DIM, WIDTH // 2, HEIGHT - 50, center=True)
            self._last_init_result_btn = pygame.Rect(0, 0, 0, 0)  # non-clickable
        else:
            cont_btn = pygame.Rect(WIDTH // 2 - 130, HEIGHT - 44, 260, 38)
            draw_button(surf, cont_btn, "Continue →", mouse_pos, size=18,
                        normal=BLUE_DARK, hover=BLUE)
            self._last_init_result_btn = cont_btn

    def _draw_resolving(self, surf, mouse_pos):
        surf.fill(BG)
        if not self.battle:
            return
        rp = self._resolving_player
        init_done = self._init_player_resolved

        if self.phase == "action_result":
            actor = self._action_step_unit
            actor_name = actor.name if actor else "?"
            lbl = f"{actor_name} acted — review, then continue"
        elif self.phase == "resolve_done" and init_done:
            lbl = f"P{rp} acted — review, then pass to P{3 - (rp or 1)}"
        elif self.phase == "resolve_done":
            lbl = "Round complete — Continue when ready"
        else:
            lbl = f"P{rp} Acting — Both Watch" if rp else "Resolution"

        draw_top_bar(surf, self.battle, lbl)
        _status_hover = []
        draw_formation(surf, self.battle, mouse_pos=mouse_pos,
                       status_rects_out=_status_hover)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)

        # Detail panel
        if self._detail_unit is not None:
            _dh = []
            close_btn = draw_combatant_detail(surf, self._detail_unit, status_rects_out=_dh)
            self._detail_close_btn = close_btn
            for _r, _kind in _dh:
                if _r.collidepoint(mouse_pos):
                    draw_status_tooltip(surf, _kind, mouse_pos[0], mouse_pos[1])
                    break
        else:
            self._detail_close_btn = None
            draw_text(surf, "Click any unit to inspect", 13, TEXT_MUTED,
                      20, BATTLE_DETAIL_RECT.y + 6)

        if self.phase == "action_result":
            actor = self._action_step_unit
            actor_name = actor.name if actor else "?"
            new_entries = self.battle.log[self._action_log_start:]
            if new_entries:
                msg = new_entries[0][:60]  # show the primary action result (first new line)
            else:
                msg = f"{actor_name} acted."
            draw_text(surf, msg, 18, GREEN, WIDTH // 2, HEIGHT - 90, center=True)
            cont_btn = pygame.Rect(WIDTH // 2 - 100, HEIGHT - 60, 200, 44)
            draw_button(surf, cont_btn, "Next Action →", mouse_pos, size=18,
                        normal=BLUE_DARK, hover=BLUE)
            self._last_resolve_btn = cont_btn
        elif self.phase == "resolve_done":
            sp = self._is_single_player()
            if init_done:
                second = 3 - (rp or self.battle.init_player)
                btn_label = f"Continue → P{second} selects"
                if sp:
                    msg = f"P{rp} done! Review the log, then continue."
                else:
                    msg = f"P{rp} done! Review the log, then hand to P{second}."
            else:
                btn_label = "Continue → Next Round"
                msg = "Round complete! Click Continue for the next round."
            draw_text(surf, msg, 20, GREEN, WIDTH // 2, HEIGHT - 90, center=True)
            cont_btn = pygame.Rect(WIDTH // 2 - 130, HEIGHT - 60, 260, 44)
            draw_button(surf, cont_btn, btn_label, mouse_pos, size=18,
                        normal=BLUE_DARK, hover=BLUE)
            self._last_resolve_btn = cont_btn

        # Status tooltip — drawn last
        for r, kind in _status_hover:
            if r.collidepoint(mouse_pos):
                draw_status_tooltip(surf, kind, mouse_pos[0], mouse_pos[1])
                break


# ─────────────────────────────────────────────────────────────────────────────
# HANDLE EXTRA SWAP CLICK (patch into handle_click)
# ─────────────────────────────────────────────────────────────────────────────

_orig_handle_click = Game.handle_click

def _patched_handle_click(self, pos):
    if self._tutorial_pending:
        self._tutorial_pending = None
        if self._tk_btn_label == "__tutorial__":
            self._tk_btn_label = None
            self._tk_btn_rect = None
        return
    if self.phase == "battle":
        btn = getattr(self, "_tk_btn_rect", None)
        if btn and btn.collidepoint(pos):
            self._tk_btn_label = None
            self._tk_btn_rect  = None
            # For LAN host: send state update when passing
            if self._is_lan() and self.game_mode == "lan_host":
                self._lan_send_state(phase="battle")
        return
    if self.phase == "actions_resolving":
        btn = getattr(self, "_last_actions_resolving_btn", None)
        if btn and btn.collidepoint(pos):
            self.phase = "resolving"
            self._do_single_resolution(self._resolving_player)
        return
    if self.phase == "battle_start":
        btn = getattr(self, "_last_battle_start_btn", None)
        if btn and btn.collidepoint(pos):
            self._enter_round_start()
            if self.game_mode == "lan_host":
                self._lan_send_state(phase=self.phase)
        return
    if self.phase == "end_of_round":
        btn = getattr(self, "_last_eor_btn", None)
        if btn and btn.collidepoint(pos):
            self._enter_round_start()
            if self.game_mode == "lan_host":
                self._lan_send_state(phase=self.phase)
        return
    if self.phase.startswith("extra_swap_p"):
        self._handle_extra_swap_click(pos)
        return
    if self.phase.startswith("extra_action_p"):
        self._handle_action_select_click(pos)
        return
    if self.phase in ("resolving", "resolve_done", "action_result"):
        # Close detail panel
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return
        # Formation click → inspect unit
        if pos[0] < 570:
            unit = self._unit_at_pos(pos)
            if unit:
                self._detail_unit = None if self._detail_unit is unit else unit
            return
        btn = getattr(self, "_last_resolve_btn", None)
        if btn and btn.collidepoint(pos):
            if self.phase == "action_result":
                self._resolve_next_step()
            else:
                self._auto_continue_resolve_done()
        return
    _orig_handle_click(self, pos)

Game.handle_click = _patched_handle_click


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    g = Game()
    # Init last-used button caches to avoid AttributeError on first frame
    g._last_menu_btns   = (pygame.Rect(0,0,1,1),) * 5
    g._last_pass_btn    = None
    g._last_team_clicks = {}
    g._last_action_buttons = []
    g._last_result_btns = (pygame.Rect(0,0,1,1), pygame.Rect(0,0,1,1))
    g._last_campaign_btns = {}
    g._last_practice_btns = {}
    g._last_teambuilder_btns = {}
    g._last_story_team_btns = {}
    g._campaign_roster    = list(ROSTER)
    g._campaign_items     = list(ITEMS)
    g._campaign_basics    = dict(CLASS_BASICS)
    g._campaign_enemy_picks = []
    g._extra_swap_player   = 1
    g._extra_swap_pending  = None
    g._extra_swap_skip_btn = pygame.Rect(0,0,1,1)
    g._last_resolve_btn    = pygame.Rect(0,0,1,1)
    g._last_actions_resolving_btn = pygame.Rect(0,0,1,1)
    g._last_clear_btn      = None
    g._detail_close_btn    = None
    g._resolving_player    = None
    g._init_player_resolved = False
    g._tk_btn_rect         = None
    g.run()


if __name__ == "__main__":
    main()
