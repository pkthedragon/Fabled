"""
main.py – Fabled prototype entry point.
Two-player pass-and-play on one device.

Phase flow:
  menu
  → team_select_p1  (sub-phases: pick_adventurers → pick_sig × 3 → pick_basics × 3 → pick_artifacts)
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
import re
import pygame

import battle_log
import net
import ai as _ai
from ai_team_pool import AI_TEAM_POOL, RANKED_AI_TEAM_META
from settings import *
from models import BattleState, CampaignProfile
from data import (
    ROSTER,
    CLASS_BASICS,
    ARTIFACTS,
    ARTIFACTS_BY_ID,
    LEGACY_ITEM_TO_ARTIFACT_ID,
)
from logic import (
    create_team, start_new_round, determine_initiative,
    resolve_player_turn, resolve_queued_action, end_round,
    get_legal_targets, can_use_ability, do_swap,
    apply_passive_stats, can_act_this_round,
    get_legal_item_targets,
    get_subterfuge_swap_targets,
    apply_quest_rewards,
    build_quest_reward_preview,
    apply_round_start_effects,
    make_combatant,
    describe_action,
    ready_active_artifacts,
)
do_end_round = end_round
from ui import (
    font, draw_text, draw_button, draw_panel,
    draw_main_menu, draw_team_select_screen, draw_pass_screen,
    draw_formation, draw_log, draw_action_menu, draw_target_prompt,
    draw_top_bar, draw_result_screen, draw_queued_summary,
    draw_combatant_detail,
    draw_battle_strip, draw_battle_log_overlay, draw_artifact_overlay,
    draw_campaign_mission_select, draw_quest_select,
    draw_pre_quest, draw_post_quest, draw_campaign_complete,
    draw_practice_menu, draw_teambuilder, draw_story_team_select,
    draw_estate_menu, draw_training_menu,
    draw_settings_screen, draw_rename_overlay,
    draw_guild_screen, draw_embassy_screen, draw_market_closed,
    draw_catalog,
    draw_pvp_mode_select, draw_lan_lobby,
    draw_status_tooltip, draw_artifact_tooltip, draw_import_modal, draw_tutorial_popup, draw_intro_popup,
    _wrap_text,
    SLOT_RECTS_P1, SLOT_RECTS_P2, LOG_RECT, ACTION_PANEL_RECT, BATTLE_DETAIL_RECT,
    BATTLE_STRIP_RECT, ARENA_RECT,
)
from campaign_data import QUEST_TABLE, MISSION_TABLE, build_quest_enemy_team
from campaign_save import save_campaign, load_campaign, get_campaign_save_path
from progression import (
    adventurer_level_from_clears,
    all_adventurer_sigils_unlocked,
    all_class_sigils_unlocked,
    class_basics_unlocked_count,
    class_level_from_points,
    player_level_from_exp,
    player_sigil_unlocked,
    rank_name_from_rating,
    saved_team_slot_count,
    unlocked_signature_count,
    twist_unlocked,
    apply_ranked_result,
)
from economy import (
    ADVENTURER_PRICES,
    ARTIFACT_PRICES,
    EMBASSY_GOLD_PER_DOLLAR,
    QUICK_PLAY_LOSS_GOLD,
    QUICK_PLAY_WIN_GOLD,
    RANKED_LOSS_GOLD,
    RANKED_LOSS_RENOWN,
    RANKED_WIN_GOLD,
    RANKED_WIN_RENOWN,
    STARTER_ADVENTURERS,
    STARTER_ARTIFACTS,
    TUTORIAL_ADVENTURERS,
    TUTORIAL_ARTIFACTS,
    embassy_gold_for_dollars,
    random_artifact_reward_pool,
)


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
        self._ai_decision_profile = "quick"

        # Campaign state
        self.campaign_profile: CampaignProfile = load_campaign()
        self._refresh_profile_filters()
        self.campaign_quest_id: int = 0
        self.campaign_mission_id: int = 1
        self._last_campaign_btns = None
        self._campaign_won_quest = False
        self._last_reward_summary: dict = {}
        self._last_result_details: list = []
        self._last_result_subtitle: str = ""
        self._guild_tab: str = "adventurers"
        self._guild_scroll: int = 0
        self._last_guild_btns = None
        self._last_embassy_btns = None
        self._last_market_btns = None
        self._menu_level_card_open: bool = False

        # New teambuilder / story-team state
        self._editing_team_slot: int = None
        self._editing_single_member: bool = False  # True when editing one member's sets only
        self._editing_from_roster: bool = False    # True when editing sets jumped from pick_adventurers
        self._focused_slot: int = None             # slot shown in detail panel (not yet editing)
        self._edit_sets_backup: dict = None        # backup of sig/basics/item before Edit Sets
        self._team_drag_source: tuple | None = None
        self._team_drag_defn = None
        self._team_drag_slot: int | None = None
        self._team_drag_active: bool = False
        self._team_drag_hover_slot: int | None = None
        self._team_drag_hover_remove: bool = False
        self._team_drag_start_pos: tuple[int, int] | None = None
        self._team_mouse_down_target: tuple | None = None
        self._team_last_click_target: tuple | None = None
        self._team_last_click_time: int = 0
        self._team_member_prompt_slot: int | None = None
        self._team_artifact_focus = None
        self.team_artifact_scroll: int = 0

        # Import modal state
        self._import_modal_open: bool = False
        self._import_modal_text: str = ""
        self._import_modal_error: str = ""
        self._last_import_modal_clicks: dict = {}
        self._story_team_idx: int = None
        self._last_practice_btns = None
        self._last_estate_btns = None
        self._last_training_btns = None
        self._last_teambuilder_btns = None
        self._last_story_team_btns = None
        self._teambuilder_return_phase = "menu"  # where back_btn in teambuilder leads
        self._catalog_return_phase = "menu"
        self._lan_return_phase = "training_menu"
        self._campaign_back_phase = "menu"

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
            "classes":     {},
            "artifacts":   {"types": set()},
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
        self.item_choice = []            # selected artifact indices during team build
        self.team_slot_selected = None   # index 0-2 for reorder drag-by-click
        self.team_select_scroll = 0      # detail list scroll offset for basics/artifacts
        self.battle_log_scroll = 0       # battle log scroll offset (0 = bottom)
        self.p1_picks = None
        self.p2_picks = None
        self.team_artifacts = []

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
        self._battle_overlay = None         # None | "log" | "artifacts"
        self._last_battle_strip_btns = {}
        self._last_battle_overlay_btns = {}

        # Curated AI draft pool (meta-style lineups)
        self._ai_team_pool = [
            {"name": "Anti-Heal Pressure", "usage": "Open by weakening the frontline with Gretel, land no-heal with Liesl, then cash out with Robin. Once no-heal is active, stop trying to refresh it and just kill. Best into sustain and midrange.", "members": [
                {"defn": "gretel", "sig": "shove_over", "basics": ["intimidate", "strike"], "item": "misericorde"},
                {"defn": "matchstick_liesl", "sig": "cauterize", "basics": ["heal", "protection"], "item": "heart_amulet"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hunters_mark", "hawkshot"], "item": "arcane_focus"},
            ]},
            {"name": "Expose Hunter", "usage": "Lucky exposes, Prince softens or controls, Robin finishes. Never spend a turn double-exposing an already exposed target. Very easy AI script: choose one target and collapse.", "members": [
                {"defn": "prince_charming", "sig": "condescend", "basics": ["impose", "command"], "item": "main_gauche"},
                {"defn": "lucky_constantine", "sig": "feline_gambit", "basics": ["post_bounty", "sucker_punch"], "item": "holy_diadem"},
                {"defn": "robin_hooded_avenger", "sig": "bring_down", "basics": ["hawkshot", "hunters_badge"], "item": "family_seal"},
            ]},
            {"name": "Balanced Generalist", "usage": "Frederic pressures, Aurora stabilizes, Prince converts. If nobody is in danger, attack. If one ally is in danger, Aurora fixes it once, then resume pressure.", "members": [
                {"defn": "frederic", "sig": "heros_charge", "basics": ["hunters_mark", "hunters_badge"], "item": "family_seal"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["heal", "medic"], "item": "heart_amulet"},
                {"defn": "prince_charming", "sig": "condescend", "basics": ["impose", "command"], "item": "main_gauche"},
            ]},
            {"name": "Reflection Punish", "usage": "Let the enemy attack into Lady and punish the trade. Reynard is the real finisher. Roland exists to preserve formation and protect the punish core. Great into straightforward aggro.", "members": [
                {"defn": "lady_of_reflections", "sig": "drown_in_the_loch", "basics": ["condemn", "stalwart"], "item": "spiked_mail"},
                {"defn": "reynard", "sig": "feign_weakness", "basics": ["riposte", "fleetfooted"], "item": "holy_diadem"},
                {"defn": "sir_roland", "sig": "banner_of_command", "basics": ["shield_bash", "armored"], "item": "crafty_shield"},
            ]},
            {"name": "Speed Tempo", "usage": "Create tempo with Hare, then convert immediately with Jack/Frederic. If no real kill window appears by round 3, stop setting up and just burst the frontline.", "members": [
                {"defn": "little_jack", "sig": "skyfall", "basics": ["cleave", "feint"], "item": "family_seal"},
                {"defn": "march_hare", "sig": "rabbit_hole", "basics": ["arcane_wave", "thunder_call"], "item": "lightning_boots"},
                {"defn": "frederic", "sig": "on_the_hunt", "basics": ["hunters_mark", "hunters_badge"], "item": "main_gauche"},
            ]},
            {"name": "Last-Stand Brawler", "usage": "Don't over-heal Risa if she is entering a winning low-HP band. Porcus buys time, Aurora keeps the team alive, Risa closes. Best into teams that cannot burst through Porcus quickly.", "members": [
                {"defn": "risa_redcloak", "sig": "blood_hunt", "basics": ["rend", "feint"], "item": "vampire_fang"},
                {"defn": "porcus_iii", "sig": "not_by_the_hair", "basics": ["shield_bash", "armored"], "item": "iron_buckler"},
                {"defn": "snowkissed_aurora", "sig": "toxin_purge", "basics": ["heal", "medic"], "item": "heart_amulet"},
            ]},
            {"name": "Burnline Pressure", "usage": "Spread burn and anti-heal, then switch to damage. Do not keep reburning the same target if another enemy is still clean. Best into bulky teams that hate attrition plus burst.", "members": [
                {"defn": "gretel", "sig": "hot_mitts", "basics": ["intimidate", "strike"], "item": "misericorde"},
                {"defn": "matchstick_liesl", "sig": "cauterize", "basics": ["heal", "smite"], "item": "heart_amulet"},
                {"defn": "witch_of_the_woods", "sig": "toil_and_trouble", "basics": ["fire_blast", "thunder_call"], "item": "misericorde"},
            ]},
            {"name": "Root Killbox", "usage": "Root once, then convert. Jack and Briar create the trap, Robin punishes it. Great into swap-reliant teams and mixed-class backlines.", "members": [
                {"defn": "little_jack", "sig": "beanstalk_crash", "basics": ["cleave", "feint"], "item": "family_seal"},
                {"defn": "briar_rose", "sig": "creeping_doubt", "basics": ["trapping_blow", "hunters_mark"], "item": "family_seal"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hunters_mark", "hawkshot"], "item": "arcane_focus"},
            ]},
            {"name": "Shock Punish", "usage": "Shock the most dangerous ranged enemy, then manipulate tempo so their recharge timing gets ruined. Don't reshock an already shocked target unless lethal is available.", "members": [
                {"defn": "sir_roland", "sig": "banner_of_command", "basics": ["shield_bash", "armored"], "item": "crafty_shield"},
                {"defn": "hunold_the_piper", "sig": "dying_dance", "basics": ["sucker_punch", "fleetfooted"], "item": "arcane_focus"},
                {"defn": "march_hare", "sig": "tempus_fugit", "basics": ["arcane_wave", "thunder_call"], "item": "lightning_boots"},
            ]},
            {"name": "Safe Midrange", "usage": "This is the cleanest stable AI team. Roland buys turns, Aurora prevents collapse, Prince wins the middle turns. Attack more than you heal.", "members": [
                {"defn": "sir_roland", "sig": "banner_of_command", "basics": ["shield_bash", "armored"], "item": "crafty_shield"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["heal", "medic"], "item": "heart_amulet"},
                {"defn": "prince_charming", "sig": "condescend", "basics": ["impose", "command"], "item": "main_gauche"},
            ]},
            {"name": "Backline Hunter", "usage": "Lucky and Robin attack the enemy's structure while Prince keeps the team coherent. Use Subterfuge only when it improves legal targeting or forces a kill sequence.", "members": [
                {"defn": "prince_charming", "sig": "gallant_charge", "basics": ["impose", "summons"], "item": "main_gauche"},
                {"defn": "robin_hooded_avenger", "sig": "bring_down", "basics": ["hawkshot", "hunters_badge"], "item": "family_seal"},
                {"defn": "lucky_constantine", "sig": "subterfuge", "basics": ["post_bounty", "sneak_attack"], "item": "lightning_boots"},
            ]},
            {"name": "Frontline Breaker", "usage": "Jack and Frederic crack the tank, Aurora keeps the push alive. Best against Porcus/Lady/Roland type fronts.", "members": [
                {"defn": "little_jack", "sig": "belligerence", "basics": ["cleave", "strike"], "item": "family_seal"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["heal", "bless"], "item": "heart_amulet"},
                {"defn": "frederic", "sig": "on_the_hunt", "basics": ["hunters_mark", "hunters_badge"], "item": "main_gauche"},
            ]},
            {"name": "Double Rogue Tempo", "usage": "Lucky opens, Reynard punishes, Prince keeps control. Works best into squishier or poorly guarded teams.", "members": [
                {"defn": "prince_charming", "sig": "condescend", "basics": ["impose", "summons"], "item": "main_gauche"},
                {"defn": "lucky_constantine", "sig": "subterfuge", "basics": ["post_bounty", "sneak_attack"], "item": "lightning_boots"},
                {"defn": "reynard", "sig": "feign_weakness", "basics": ["riposte", "fleetfooted"], "item": "holy_diadem"},
            ]},
            {"name": "No-Heal Collapse", "usage": "Similar to Anti-Heal Pressure, but Frederic gives stronger frontline conversions instead of Robin pick power.", "members": [
                {"defn": "gretel", "sig": "shove_over", "basics": ["intimidate", "feint"], "item": "misericorde"},
                {"defn": "matchstick_liesl", "sig": "cauterize", "basics": ["heal", "bless"], "item": "heart_amulet"},
                {"defn": "frederic", "sig": "heros_charge", "basics": ["hunters_mark", "hunters_badge"], "item": "family_seal"},
            ]},
            {"name": "Status Spread", "usage": "One status on the primary threat, one different status elsewhere, then kill. This team is bad if it spends turns redundantly refreshing statuses.", "members": [
                {"defn": "witch_of_the_woods", "sig": "toil_and_trouble", "basics": ["fire_blast", "thunder_call"], "item": "misericorde"},
                {"defn": "hunold_the_piper", "sig": "dying_dance", "basics": ["sucker_punch", "fleetfooted"], "item": "arcane_focus"},
                {"defn": "briar_rose", "sig": "creeping_doubt", "basics": ["trapping_blow", "hunters_mark"], "item": "family_seal"},
            ]},
            {"name": "Burn Shock Split", "usage": "Burn one unit, shock another, no-heal the sustain anchor. Meant to overload the enemy's support bandwidth.", "members": [
                {"defn": "witch_of_the_woods", "sig": "toil_and_trouble", "basics": ["fire_blast", "thunder_call"], "item": "misericorde"},
                {"defn": "hunold_the_piper", "sig": "haunting_rhythm", "basics": ["sucker_punch", "fleetfooted"], "item": "arcane_focus"},
                {"defn": "matchstick_liesl", "sig": "cauterize", "basics": ["heal", "smite"], "item": "heart_amulet"},
            ]},
            {"name": "Double Ranger Pressure", "usage": "High legal-damage density. If Briar roots a priority target, everyone focuses it.", "members": [
                {"defn": "frederic", "sig": "on_the_hunt", "basics": ["hunters_mark", "hunters_badge"], "item": "main_gauche"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hawkshot", "hunters_mark"], "item": "arcane_focus"},
                {"defn": "briar_rose", "sig": "creeping_doubt", "basics": ["trapping_blow", "hunters_mark"], "item": "family_seal"},
            ]},
            {"name": "Ranger-Rogue Kill Chain", "usage": "Probably the simplest burst team to pilot: expose target, mark target, shoot target.", "members": [
                {"defn": "frederic", "sig": "heros_charge", "basics": ["hunters_mark", "hunters_badge"], "item": "family_seal"},
                {"defn": "lucky_constantine", "sig": "feline_gambit", "basics": ["post_bounty", "sucker_punch"], "item": "holy_diadem"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hunters_mark", "hawkshot"], "item": "arcane_focus"},
            ]},
            {"name": "Roland Counterbattery", "usage": "Roland frontloads survivability, Robin is your damage engine, Aurora keeps Robin online. Good default versus mixed offense.", "members": [
                {"defn": "sir_roland", "sig": "knights_challenge", "basics": ["shield_bash", "stalwart"], "item": "spiked_mail"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hawkshot", "hunters_mark"], "item": "arcane_focus"},
                {"defn": "snowkissed_aurora", "sig": "toxin_purge", "basics": ["heal", "medic"], "item": "heart_amulet"},
            ]},
            {"name": "Lady Control Shell", "usage": "Lady is the anchor, Prince is the closer. Use Lake's Gift to buff the ally most likely to secure tempo next turn.", "members": [
                {"defn": "lady_of_reflections", "sig": "lakes_gift", "basics": ["condemn", "armored"], "item": "crafty_shield"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["heal", "medic"], "item": "heart_amulet"},
                {"defn": "prince_charming", "sig": "condescend", "basics": ["impose", "command"], "item": "main_gauche"},
            ]},
            {"name": "Porcus Fortress", "usage": "Slow but punishing. Best used by AI into heavy aggro or glass-cannon teams, not as a blind default.", "members": [
                {"defn": "porcus_iii", "sig": "porcine_honor", "basics": ["shield_bash", "stalwart"], "item": "spiked_mail"},
                {"defn": "aldric_lost_lamb", "sig": "benefactor", "basics": ["heal", "protection"], "item": "heart_amulet"},
                {"defn": "lady_of_reflections", "sig": "lakes_gift", "basics": ["condemn", "armored"], "item": "crafty_shield"},
            ]},
            {"name": "Sustain Into Spike", "usage": "Defend early, then switch to Prince once the enemy has committed.", "members": [
                {"defn": "porcus_iii", "sig": "sturdy_home", "basics": ["shield_bash", "armored"], "item": "iron_buckler"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["heal", "bless"], "item": "heart_amulet"},
                {"defn": "prince_charming", "sig": "condescend", "basics": ["impose", "command"], "item": "main_gauche"},
            ]},
            {"name": "Brawler Punish", "usage": "Let the opponent overcommit into Lady/Reynard, then let Risa finish once she is empowered.", "members": [
                {"defn": "risa_redcloak", "sig": "blood_hunt", "basics": ["rend", "feint"], "item": "vampire_fang"},
                {"defn": "lady_of_reflections", "sig": "drown_in_the_loch", "basics": ["condemn", "stalwart"], "item": "spiked_mail"},
                {"defn": "reynard", "sig": "feign_weakness", "basics": ["riposte", "fleetfooted"], "item": "holy_diadem"},
            ]},
            {"name": "Last-Stand Midrange", "usage": "More conservative Risa shell. Use Wolf's Pursuit when the enemy wants to dance around formation.", "members": [
                {"defn": "risa_redcloak", "sig": "wolfs_pursuit", "basics": ["rend", "feint"], "item": "vampire_fang"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["heal", "medic"], "item": "heart_amulet"},
                {"defn": "prince_charming", "sig": "chosen_one", "basics": ["impose", "command"], "item": "holy_diadem"},
            ]},
            {"name": "Crowstorm Burn", "usage": "Ella frontlines for the burn spread, Liesl covers sustain, Gretel punishes burned targets. Very strong into clustered midrange.", "members": [
                {"defn": "ashen_ella", "sig": "crowstorm", "basics": ["fire_blast", "arcane_wave"], "item": "arcane_focus"},
                {"defn": "matchstick_liesl", "sig": "cauterize", "basics": ["heal", "bless"], "item": "heart_amulet"},
                {"defn": "gretel", "sig": "hot_mitts", "basics": ["intimidate", "strike"], "item": "misericorde"},
            ]},
            {"name": "Ella Pivot Shell", "usage": "Roland fronts, Ella pivots between frontline and protected value turns, Aurora keeps the shell clean. Safe, AI-friendly, and difficult to burst.", "members": [
                {"defn": "sir_roland", "sig": "banner_of_command", "basics": ["shield_bash", "armored"], "item": "crafty_shield"},
                {"defn": "ashen_ella", "sig": "fae_blessing", "basics": ["fire_blast", "arcane_wave"], "item": "arcane_focus"},
                {"defn": "snowkissed_aurora", "sig": "toxin_purge", "basics": ["heal", "medic"], "item": "heart_amulet"},
            ]},
            {"name": "Royal Root Pressure", "usage": "Prince or Briar roots, Robin capitalizes. Very good into swap-heavy teams and nobles/warlocks.", "members": [
                {"defn": "prince_charming", "sig": "condescend", "basics": ["edict", "command"], "item": "main_gauche"},
                {"defn": "briar_rose", "sig": "creeping_doubt", "basics": ["trapping_blow", "hunters_mark"], "item": "family_seal"},
                {"defn": "robin_hooded_avenger", "sig": "bring_down", "basics": ["hawkshot", "hunters_badge"], "item": "family_seal"},
            ]},
            {"name": "Gretel Tempo Kill", "usage": "Gretel establishes weaken, Lucky improves the angle, Robin kills. This is a fast kill-chain team, not a prolonged one.", "members": [
                {"defn": "gretel", "sig": "shove_over", "basics": ["intimidate", "feint"], "item": "misericorde"},
                {"defn": "lucky_constantine", "sig": "subterfuge", "basics": ["post_bounty", "sneak_attack"], "item": "lightning_boots"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hunters_mark", "hawkshot"], "item": "arcane_focus"},
            ]},
            {"name": "Shocked Quarry", "usage": "Shock the main carry, then use tempo tools to punish the forced recharge line. Frederic cleans up.", "members": [
                {"defn": "frederic", "sig": "on_the_hunt", "basics": ["hunters_mark", "hunters_badge"], "item": "main_gauche"},
                {"defn": "hunold_the_piper", "sig": "dying_dance", "basics": ["sucker_punch", "fleetfooted"], "item": "arcane_focus"},
                {"defn": "march_hare", "sig": "rabbit_hole", "basics": ["arcane_wave", "thunder_call"], "item": "lightning_boots"},
            ]},
            {"name": "Prince-Robin Midrange", "usage": "A cleaner, more offensive version of Safe Midrange. Prince and Robin do most of the work; Aurora just stops disasters.", "members": [
                {"defn": "prince_charming", "sig": "gallant_charge", "basics": ["impose", "command"], "item": "main_gauche"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hunters_mark", "hawkshot"], "item": "arcane_focus"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["heal", "medic"], "item": "heart_amulet"},
            ]},
            {"name": "Execute Line", "usage": "Lucky exposes, Jack chunks, Risa executes. High volatility, very good into fragile teams.", "members": [
                {"defn": "little_jack", "sig": "skyfall", "basics": ["cleave", "feint"], "item": "family_seal"},
                {"defn": "risa_redcloak", "sig": "blood_hunt", "basics": ["rend", "feint"], "item": "vampire_fang"},
                {"defn": "lucky_constantine", "sig": "feline_gambit", "basics": ["post_bounty", "sucker_punch"], "item": "holy_diadem"},
            ]},
            {"name": "Burn-Root Hunter", "usage": "Burn one target, root another, then collapse on whichever target is now easiest to kill. Strong into slower control teams.", "members": [
                {"defn": "witch_of_the_woods", "sig": "toil_and_trouble", "basics": ["fire_blast", "ominous_gale"], "item": "misericorde"},
                {"defn": "briar_rose", "sig": "creeping_doubt", "basics": ["hunters_mark", "trapping_blow"], "item": "family_seal"},
                {"defn": "frederic", "sig": "heros_charge", "basics": ["hunters_mark", "hunters_badge"], "item": "family_seal"},
            ]},
            {"name": "Green Knight Root Midrange", "usage": "Root the most important frontline target, then let Robin immediately convert. Aurora should only interrupt the damage plan when a heal or cleanse prevents a knockout.", "members": [
                {"defn": "green_knight", "sig": "heros_bargain", "basics": ["command", "edict"], "item": "family_seal"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hunters_mark", "hawkshot"], "item": "arcane_focus"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["heal", "medic"], "item": "heart_amulet"},
            ]},
            {"name": "Rapunzel Collapse", "usage": "Mark one target for collapse and avoid splitting damage. Use Flowing Locks opportunistically to finish a vulnerable backliner if it cleanly wins the trade.", "members": [
                {"defn": "rapunzel", "sig": "lower_guard", "basics": ["command", "edict"], "item": "main_gauche"},
                {"defn": "lucky_constantine", "sig": "feline_gambit", "basics": ["post_bounty", "sucker_punch"], "item": "holy_diadem"},
                {"defn": "frederic", "sig": "heros_charge", "basics": ["hunters_mark", "hunters_badge"], "item": "family_seal"},
            ]},
            {"name": "Rapunzel Pin Control", "usage": "Root first, then anti-heal the sustain anchor, then focus the rooted unit. This team wins by converting control into a clean kill instead of maintaining it forever.", "members": [
                {"defn": "rapunzel", "sig": "golden_snare", "basics": ["impose", "command"], "item": "family_seal"},
                {"defn": "robin_hooded_avenger", "sig": "bring_down", "basics": ["hawkshot", "hunters_badge"], "item": "arcane_focus"},
                {"defn": "matchstick_liesl", "sig": "cauterize", "basics": ["heal", "bless"], "item": "heart_amulet"},
            ]},
            {"name": "Pinocchio Malice Fortress", "usage": "Keep frontline Pinocchio in place long enough to reach 3+ Malice, then stop playing defensively and force kills with boosted warlock attacks.", "members": [
                {"defn": "pinocchio", "sig": "become_real", "basics": ["dark_grasp", "cursed_armor"], "item": "family_seal"},
                {"defn": "sir_roland", "sig": "banner_of_command", "basics": ["shield_bash", "armored"], "item": "crafty_shield"},
                {"defn": "snowkissed_aurora", "sig": "toxin_purge", "basics": ["heal", "medic"], "item": "heart_amulet"},
            ]},
            {"name": "Pinocchio Spotlight Break", "usage": "Soften with Prince, spotlight the priority target, then immediately convert with Prince and Robin. Do not stall for more Malice if a clear kill is already available.", "members": [
                {"defn": "prince_charming", "sig": "condescend", "basics": ["impose", "command"], "item": "main_gauche"},
                {"defn": "pinocchio", "sig": "cut_the_strings", "basics": ["soul_gaze", "void_step"], "item": "family_seal"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hunters_mark", "hawkshot"], "item": "arcane_focus"},
            ]},
            {"name": "Rumpel Buff Engine", "usage": "Seed buff value early, then let Rumpel convert that tempo into a swing turn. Once Rumpel has real speed and a good buff target exists, trade aggressively.", "members": [
                {"defn": "prince_charming", "sig": "chosen_one", "basics": ["decree", "summons"], "item": "holy_diadem"},
                {"defn": "rumpelstiltskin", "sig": "straw_to_gold", "basics": ["blood_pact", "soul_gaze"], "item": "arcane_focus"},
                {"defn": "snowkissed_aurora", "sig": "dictate_of_nature", "basics": ["bless", "medic"], "item": "heart_amulet"},
            ]},
            {"name": "Sea Wench Theft Shell", "usage": "Asha should stay backline until there is enough Malice and a worthwhile frontline signature to steal. Otherwise Roland protects the shell and Robin converts pressure.", "members": [
                {"defn": "sir_roland", "sig": "banner_of_command", "basics": ["shield_bash", "armored"], "item": "crafty_shield"},
                {"defn": "sea_wench_asha", "sig": "misappropriate", "basics": ["dark_grasp", "cursed_armor"], "item": "arcane_focus"},
                {"defn": "robin_hooded_avenger", "sig": "snipe_shot", "basics": ["hunters_mark", "hawkshot"], "item": "family_seal"},
            ]},
            {"name": "Sea Wench Debuff Burst", "usage": "Use Blood Pact only when it sets up a real swing turn. Once Asha and Frederic have softened a target, keep all damage on that one unit until it drops.", "members": [
                {"defn": "sea_wench_asha", "sig": "abyssal_call", "basics": ["soul_gaze", "blood_pact"], "item": "arcane_focus"},
                {"defn": "rapunzel", "sig": "lower_guard", "basics": ["impose", "summons"], "item": "main_gauche"},
                {"defn": "frederic", "sig": "on_the_hunt", "basics": ["hunters_mark", "hunters_badge"], "item": "family_seal"},
            ]},
        ]
        self._ai_team_pool = AI_TEAM_POOL

    def _is_single_player(self):
        return self.game_mode in ("single_player", "campaign", "ranked")

    def _tutorials_allowed(self):
        """Tutorial popups are allowed in solo flows, including the tavern editor."""
        return self.game_mode in ("single_player", "campaign", "teambuilder")

    def _maybe_show_tutorial(self, key: str, text: str):
        """Show a tutorial popup if it hasn't been seen yet. Only fires in single-player/campaign."""
        if not self._tutorials_allowed():
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
        if not self._tutorials_allowed() or not self.battle:
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

    def _player_level(self) -> int:
        profile = self.campaign_profile or CampaignProfile()
        return player_level_from_exp(profile.player_exp)

    def _saved_team_slot_count(self) -> int:
        return saved_team_slot_count(self._player_level())

    def _adventurer_level(self, adv_id: str) -> int:
        profile = self.campaign_profile or CampaignProfile()
        return adventurer_level_from_clears(profile.adventurer_quest_clears.get(adv_id, 0))

    def _class_level(self, class_name: str) -> int:
        profile = self.campaign_profile or CampaignProfile()
        return class_level_from_points(profile.class_points.get(class_name, 0))

    def _build_owned_basics(self) -> dict:
        profile = self.campaign_profile or CampaignProfile()
        basics = {}
        for class_name, ability_list in CLASS_BASICS.items():
            count = class_basics_unlocked_count(self._class_level(class_name))
            basics[class_name] = ability_list[:count]
        profile.unlocked_classes = {class_name for class_name, ability_list in basics.items() if ability_list}
        return basics

    def _refresh_profile_filters(self):
        profile = self.campaign_profile or CampaignProfile()
        self._campaign_roster = [defn for defn in ROSTER if defn.id in profile.recruited]
        self._campaign_artifacts = [artifact for artifact in ARTIFACTS if artifact.id in profile.unlocked_artifacts]
        self._campaign_basics = self._build_owned_basics()

    def _ranked_unlocked(self) -> bool:
        profile = self.campaign_profile or CampaignProfile()
        if not player_sigil_unlocked(self._player_level()):
            return False
        if not all_class_sigils_unlocked(profile.class_points, CLASS_BASICS.keys()):
            return False
        roster_ids = [defn.id for defn in ROSTER]
        if not set(roster_ids).issubset(profile.recruited):
            return False
        return all_adventurer_sigils_unlocked(profile.adventurer_quest_clears, roster_ids)

    def _current_party_adventurer_ids(self, picks: list | None = None) -> list:
        ids = []
        for pick in picks or []:
            if not pick:
                continue
            defn = pick.get("definition")
            if defn and defn.id not in ids:
                ids.append(defn.id)
        return ids

    def _current_guild_adventurer_ids(self) -> list:
        return [adv_id for adv_id in ADVENTURER_PRICES]

    def _current_guild_artifact_ids(self) -> list:
        return [artifact_id for artifact_id in ARTIFACT_PRICES]

    def _enter_camelot(self):
        self.game_mode = "campaign"
        self.ai_player = 2
        self._ai_decision_profile = "quick"
        self.campaign_mission_id = 1
        self._campaign_back_phase = "menu"
        self.phase = "campaign_quest_select"

    def _team_select_focus_defn(self):
        if self._focused_slot is not None and self._focused_slot < len(self.team_picks):
            pick = self.team_picks[self._focused_slot]
            if pick:
                return pick.get("definition")
        if self.current_adv_idx is not None and self.current_adv_idx < len(self.team_picks):
            pick = self.team_picks[self.current_adv_idx]
            if pick:
                return pick.get("definition")
        return self.roster_selected

    def _active_team_builder_pools(self):
        if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked") and hasattr(self, "_campaign_roster"):
            return self._campaign_roster, self._campaign_artifacts, self._campaign_basics
        return ROSTER, ARTIFACTS, CLASS_BASICS

    def _clone_team_pick(self, pick):
        if not pick:
            return None
        cloned = {"definition": pick.get("definition")}
        if pick.get("signature") is not None:
            cloned["signature"] = pick.get("signature")
        if "basics" in pick:
            cloned["basics"] = list(pick.get("basics", []))
        if "team_artifacts" in pick:
            cloned["team_artifacts"] = list(pick.get("team_artifacts", []))
        return cloned

    def _normalize_builder_picks(self, picks):
        slots = [None, None, None]
        for idx, pick in enumerate((picks or [])[:3]):
            slots[idx] = self._clone_team_pick(pick)
        return slots

    def _reset_team_builder_ui_state(self):
        self.roster_selected = None
        self.current_adv_idx = 0
        self.sig_choice = None
        self.basic_choices = []
        self.item_choice = []
        self.team_slot_selected = None
        self.team_select_scroll = 0
        self.team_artifact_scroll = 0
        self._editing_from_roster = False
        self._editing_single_member = False
        self._focused_slot = None
        self._team_drag_source = None
        self._team_drag_defn = None
        self._team_drag_slot = None
        self._team_drag_active = False
        self._team_drag_hover_slot = None
        self._team_drag_hover_remove = False
        self._team_drag_start_pos = None
        self._team_mouse_down_target = None
        self._team_member_prompt_slot = None
        self._team_artifact_focus = None
        self._detail_unit = None

    def _available_signatures_for_defn(self, defn):
        if defn is None:
            return []
        if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked") and self.campaign_profile:
            return defn.sig_options[:unlocked_signature_count(self._adventurer_level(defn.id))]
        return list(defn.sig_options)

    def _available_basics_for_defn(self, defn):
        _, _, active_cls_basics = self._active_team_builder_pools()
        if defn is None:
            return []
        return list(active_cls_basics.get(defn.cls, []))

    def _pick_has_valid_set(self, pick):
        if not pick:
            return False
        defn = pick.get("definition")
        if defn is None:
            return False
        sig = pick.get("signature")
        basics = list(pick.get("basics", []))
        available_sigs = {ability.id for ability in self._available_signatures_for_defn(defn)}
        available_basics = {ability.id for ability in self._available_basics_for_defn(defn)}
        if sig is None or sig.id not in available_sigs:
            return False
        if len(basics) != 2:
            return False
        basic_ids = [ability.id for ability in basics]
        if len(set(basic_ids)) != 2:
            return False
        return all(ability_id in available_basics for ability_id in basic_ids)

    def _team_builder_ready(self):
        return len(self.team_picks) == 3 and all(self._pick_has_valid_set(pick) for pick in self.team_picks)

    def _builder_slot_fill_count(self):
        return sum(1 for pick in self.team_picks if pick)

    def _builder_ready_count(self):
        return sum(1 for pick in self.team_picks if self._pick_has_valid_set(pick))

    def _builder_find_slot_for_defn(self, defn):
        if defn is None:
            return None
        for idx, pick in enumerate(self.team_picks):
            if pick and pick.get("definition") == defn:
                return idx
        return None

    def _builder_set_focus(self, slot_idx):
        self._team_member_prompt_slot = None
        self._detail_unit = None
        self._focused_slot = slot_idx if slot_idx is not None and 0 <= slot_idx < len(self.team_picks) else None
        if self._focused_slot is None:
            self.current_adv_idx = 0
            self.sig_choice = None
            self.basic_choices = []
            return
        pick = self.team_picks[self._focused_slot]
        if not pick:
            self.current_adv_idx = self._focused_slot
            self.sig_choice = None
            self.basic_choices = []
            return
        defn = pick.get("definition")
        sigs = self._available_signatures_for_defn(defn)
        basics = self._available_basics_for_defn(defn)
        self.current_adv_idx = self._focused_slot
        sig = pick.get("signature")
        self.sig_choice = next((idx for idx, ability in enumerate(sigs) if sig and ability.id == sig.id), None)
        picked_basic_ids = [ability.id for ability in pick.get("basics", [])]
        self.basic_choices = [
            idx for idx, ability in enumerate(basics)
            if ability.id in picked_basic_ids
        ]

    def _builder_remove_slot(self, slot_idx):
        if slot_idx is None or not (0 <= slot_idx < len(self.team_picks)):
            return
        self.team_picks[slot_idx] = None
        if self._focused_slot == slot_idx:
            self._builder_set_focus(None)
        elif self._focused_slot is not None and self._focused_slot >= len(self.team_picks):
            self._builder_set_focus(None)
        self._team_member_prompt_slot = None

    def _builder_move_pick(self, from_idx, to_idx):
        if from_idx is None or to_idx is None:
            return
        if from_idx == to_idx:
            self._builder_set_focus(to_idx)
            return
        self.team_picks[from_idx], self.team_picks[to_idx] = self.team_picks[to_idx], self.team_picks[from_idx]
        if self._focused_slot == from_idx:
            self._builder_set_focus(to_idx)
        elif self._focused_slot == to_idx:
            self._builder_set_focus(from_idx)
        self._team_member_prompt_slot = None

    def _builder_add_roster_defn_to_slot(self, defn, slot_idx):
        if defn is None or slot_idx is None or not (0 <= slot_idx < len(self.team_picks)):
            return
        existing_idx = self._builder_find_slot_for_defn(defn)
        if existing_idx is not None:
            if existing_idx != slot_idx:
                self._builder_move_pick(existing_idx, slot_idx)
            else:
                self._builder_set_focus(slot_idx)
            return
        if self.team_picks[slot_idx] is not None:
            self._builder_set_focus(slot_idx)
            return
        self.team_picks[slot_idx] = {"definition": defn}
        self._builder_set_focus(slot_idx)
        if self._builder_slot_fill_count() == 3:
            self._maybe_show_tutorial("party_built", "Now, set each adventurer's abilities and artifacts.")

    def _builder_open_detail_for_pick(self, slot_idx):
        if slot_idx is None or not (0 <= slot_idx < len(self.team_picks)):
            return
        pick = self.team_picks[slot_idx]
        if not pick:
            return
        defn = pick.get("definition")
        if defn is None:
            return
        sig = pick.get("signature") or (self._available_signatures_for_defn(defn) or defn.sig_options)[0]
        basics_pool = self._available_basics_for_defn(defn) or CLASS_BASICS.get(defn.cls, [])
        basics = list(pick.get("basics", []))
        if len(basics) < 2:
            for ability in basics_pool:
                if ability.id not in {ab.id for ab in basics}:
                    basics.append(ability)
                if len(basics) >= 2:
                    break
        self._detail_unit = make_combatant(defn, SLOT_FRONT, sig, basics[:2], None)

    def _builder_open_detail_for_roster(self, defn):
        if defn is None:
            return
        sigs = self._available_signatures_for_defn(defn) or list(defn.sig_options)
        basics = self._available_basics_for_defn(defn) or CLASS_BASICS.get(defn.cls, [])
        self._detail_unit = make_combatant(defn, SLOT_FRONT, sigs[0], basics[:2], None)

    def _builder_toggle_basic_choice(self, basic_idx):
        if self._focused_slot is None or not (0 <= self._focused_slot < len(self.team_picks)):
            return
        pick = self.team_picks[self._focused_slot]
        if not pick:
            return
        basics = self._available_basics_for_defn(pick.get("definition"))
        if not (0 <= basic_idx < len(basics)):
            return
        if basic_idx in self.basic_choices:
            self.basic_choices.remove(basic_idx)
        elif len(self.basic_choices) < 2:
            self.basic_choices.append(basic_idx)
        else:
            return
        pick["basics"] = [basics[idx] for idx in self.basic_choices[:2]]

    def _builder_set_signature_choice(self, sig_idx):
        if self._focused_slot is None or not (0 <= self._focused_slot < len(self.team_picks)):
            return
        pick = self.team_picks[self._focused_slot]
        if not pick:
            return
        sigs = self._available_signatures_for_defn(pick.get("definition"))
        if not (0 <= sig_idx < len(sigs)):
            return
        self.sig_choice = sig_idx
        pick["signature"] = sigs[sig_idx]

    def _builder_toggle_artifact(self, artifact):
        if artifact is None:
            return
        current_ids = [entry.id for entry in self.team_artifacts]
        if artifact.id in current_ids:
            self.team_artifacts = [entry for entry in self.team_artifacts if entry.id != artifact.id]
        elif len(self.team_artifacts) < 3:
            self.team_artifacts.append(artifact)
        self._team_artifact_focus = artifact
        self._attach_artifacts_to_picks(self.team_picks, self.team_artifacts)

    def _builder_remove_artifact(self, artifact):
        if artifact is None:
            return
        self.team_artifacts = [entry for entry in self.team_artifacts if entry.id != artifact.id]
        if self._team_artifact_focus and self._team_artifact_focus.id == artifact.id:
            self._team_artifact_focus = self.team_artifacts[0] if self.team_artifacts else None
        self._attach_artifacts_to_picks(self.team_picks, self.team_artifacts)

    def _reset_team_drag(self):
        self._team_drag_source = None
        self._team_drag_defn = None
        self._team_drag_slot = None
        self._team_drag_active = False
        self._team_drag_hover_slot = None
        self._team_drag_hover_remove = False
        self._team_drag_start_pos = None
        self._team_mouse_down_target = None

    def _append_progress_lines(self, lines: list, text: str):
        if text and text not in lines:
            lines.append(text)

    def _grant_player_exp_local(self, amount: int, lines: list):
        profile = self.campaign_profile
        amount = max(0, int(amount))
        if amount <= 0:
            return
        before_level = self._player_level()
        before_slots = saved_team_slot_count(before_level)
        before_vouchers = before_level // 5
        before_player_sigil = player_sigil_unlocked(before_level)
        profile.player_exp += amount
        after_level = self._player_level()
        after_slots = saved_team_slot_count(after_level)
        after_vouchers = after_level // 5
        if after_level > before_level:
            self._append_progress_lines(lines, f"Player Level Up: {after_level}")
        if after_slots > before_slots:
            self._append_progress_lines(lines, f"Saved Party Slots +{after_slots - before_slots}")
        if after_vouchers > before_vouchers:
            gained = after_vouchers - before_vouchers
            profile.guild_vouchers += gained
            self._append_progress_lines(lines, f"Guild Recruitment Voucher +{gained}")
        if not before_player_sigil and player_sigil_unlocked(after_level):
            self._append_progress_lines(lines, "Player Sigil Unlocked")

    def _grant_class_points_local(self, class_name: str, amount: int, lines: list, source: str = ""):
        profile = self.campaign_profile
        amount = max(0, int(amount))
        if amount <= 0:
            return
        before_points = profile.class_points.get(class_name, 0)
        before_level = class_level_from_points(before_points)
        profile.class_points[class_name] = before_points + amount
        after_level = class_level_from_points(profile.class_points[class_name])
        if after_level > before_level:
            self._append_progress_lines(lines, f"{class_name} Class Level Up: {after_level}")
            if after_level >= 5:
                self._append_progress_lines(lines, f"{class_name} Sigil and Title Unlocked")

    def _grant_adventurer_progress_local(self, adv_id: str, lines: list):
        profile = self.campaign_profile
        defn = next((entry for entry in ROSTER if entry.id == adv_id), None)
        if defn is None:
            return
        before_clears = profile.adventurer_quest_clears.get(adv_id, 0)
        before_level = adventurer_level_from_clears(before_clears)
        profile.adventurer_quest_clears[adv_id] = before_clears + 1
        after_level = adventurer_level_from_clears(profile.adventurer_quest_clears[adv_id])
        if after_level > before_level:
            self._append_progress_lines(lines, f"{defn.name} Level Up: {after_level}")
            if after_level >= 4 and before_level < 4:
                self._append_progress_lines(lines, f"{defn.name} Twist Unlocked")
            if after_level >= 5 and before_level < 5:
                self._append_progress_lines(lines, f"{defn.name} Sigil and Music Unlocked")

    def _grant_party_progress_local(self, party_ids: list, lines: list):
        self._grant_player_exp_local(100, lines)
        used_classes = []
        for adv_id in party_ids:
            self._grant_adventurer_progress_local(adv_id, lines)
            defn = next((entry for entry in ROSTER if entry.id == adv_id), None)
            if defn and defn.cls not in used_classes:
                used_classes.append(defn.cls)
        for class_name in used_classes:
            self._grant_class_points_local(class_name, 1, lines)

    def _hire_adventurer(self, adv_id: str, use_voucher: bool = False) -> list:
        profile = self.campaign_profile
        lines = []
        defn = next((entry for entry in ROSTER if entry.id == adv_id), None)
        if defn is None or adv_id in profile.recruited:
            return lines
        if use_voucher:
            if profile.guild_vouchers <= 0:
                return lines
            profile.guild_vouchers -= 1
            self._append_progress_lines(lines, "Guild Recruitment Voucher -1")
        else:
            price = ADVENTURER_PRICES.get(adv_id)
            if price is None or profile.gold < price:
                return lines
            profile.gold -= price
            self._append_progress_lines(lines, f"Gold -{price}")
        profile.recruited.add(adv_id)
        profile.default_sigs.setdefault(adv_id, defn.sig_options[0].id)
        self._append_progress_lines(lines, f"Adventurer Unlocked: {defn.name}")
        self._grant_player_exp_local(60, lines)
        self._grant_class_points_local(defn.cls, 1, lines, source=f"{defn.name} unlocked")
        profile.new_unlocks.add("adventurers")
        self._refresh_profile_filters()
        save_campaign(profile)
        return lines

    def _buy_artifact(self, artifact_id: str) -> list:
        profile = self.campaign_profile
        lines = []
        if artifact_id in profile.unlocked_artifacts:
            return lines
        price = ARTIFACT_PRICES.get(artifact_id)
        artifact = ARTIFACTS_BY_ID.get(artifact_id)
        if price is None or artifact is None or profile.gold < price:
            return lines
        profile.gold -= price
        profile.unlocked_artifacts.add(artifact_id)
        profile.new_unlocks.add("artifacts")
        self._append_progress_lines(lines, f"Gold -{price}")
        self._append_progress_lines(lines, f"Artifact Unlocked: {artifact.name}")
        self._refresh_profile_filters()
        save_campaign(profile)
        return lines

    def _buy_embassy_gold(self, dollars: int) -> list:
        profile = self.campaign_profile
        lines = []
        dollars = max(0, int(dollars))
        if dollars <= 0:
            return lines
        gold = embassy_gold_for_dollars(dollars)
        profile.premium_dollars_spent += dollars
        profile.gold += gold
        self._append_progress_lines(lines, f"Embassy: ${dollars} -> {gold} gold")
        save_campaign(profile)
        return lines

    def _apply_quick_play_rewards(self, won: bool):
        profile = self.campaign_profile
        lines = []
        party_ids = self._current_party_adventurer_ids(self.p1_picks)
        gold_amount = QUICK_PLAY_WIN_GOLD if won else QUICK_PLAY_LOSS_GOLD
        profile.gold += gold_amount
        self._append_progress_lines(lines, f"Gold +{gold_amount}")
        self._grant_party_progress_local(party_ids, lines)
        self._refresh_profile_filters()
        save_campaign(profile)
        self._last_result_details = lines
        self._last_result_subtitle = "Quick Play rewards"

    def _apply_ranked_rewards(self, won: bool):
        profile = self.campaign_profile
        lines = []
        party_ids = self._current_party_adventurer_ids(self.p1_picks)
        gold_amount = RANKED_WIN_GOLD if won else RANKED_LOSS_GOLD
        renown_delta = RANKED_WIN_RENOWN if won else RANKED_LOSS_RENOWN
        old_rating = profile.ranked_rating
        opp_rating = getattr(self, "_ranked_ai_rating", old_rating)
        profile.ranked_rating, profile.ranked_games_played = apply_ranked_result(
            profile.ranked_rating,
            profile.ranked_games_played,
            opp_rating,
            won,
        )
        profile.gold += gold_amount
        profile.brighthollow_renown = max(0, profile.brighthollow_renown + renown_delta)
        self._append_progress_lines(lines, f"Gold +{gold_amount}")
        self._append_progress_lines(lines, f"Renown {renown_delta:+d}")
        self._append_progress_lines(lines, f"Rating {old_rating} -> {profile.ranked_rating}")
        self._grant_party_progress_local(party_ids, lines)
        self._refresh_profile_filters()
        save_campaign(profile)
        self._last_result_details = lines
        self._last_result_subtitle = f"Ranked - {rank_name_from_rating(profile.ranked_rating)}"

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

    def _artifacts_from_picks(self, picks: list) -> list:
        if not picks:
            return []
        for pick in picks:
            if pick:
                return list(pick.get("team_artifacts", []))
        return []

    def _normalize_artifacts(self, artifacts: list) -> list:
        normalized = []
        seen = set()
        for artifact in artifacts or []:
            if artifact is None or artifact.id in seen:
                continue
            normalized.append(artifact)
            seen.add(artifact.id)
        return normalized

    def _legacy_items_to_artifacts(self, item_ids: list, *, fill_defaults: bool = True) -> list:
        artifacts = []
        for item_id in item_ids or []:
            artifact_id = LEGACY_ITEM_TO_ARTIFACT_ID.get(item_id)
            artifact = ARTIFACTS_BY_ID.get(artifact_id)
            if artifact is not None:
                artifacts.append(artifact)
        artifacts = self._normalize_artifacts(artifacts)
        if fill_defaults:
            for artifact in ARTIFACTS:
                if len(artifacts) >= 3:
                    break
                if artifact.id not in {a.id for a in artifacts}:
                    artifacts.append(artifact)
        return artifacts[:3]

    def _artifact_ids_to_artifacts(self, artifact_ids: list, *, fill_defaults: bool = False) -> list:
        artifacts = [
            ARTIFACTS_BY_ID[artifact_id]
            for artifact_id in (artifact_ids or [])
            if artifact_id in ARTIFACTS_BY_ID
        ]
        artifacts = self._normalize_artifacts(artifacts)
        if fill_defaults:
            for artifact in ARTIFACTS:
                if len(artifacts) >= 3:
                    break
                if artifact.id not in {a.id for a in artifacts}:
                    artifacts.append(artifact)
        return artifacts[:3]

    def _attach_artifacts_to_picks(self, picks: list, artifacts: list) -> list:
        attached = self._normalize_artifacts(list(artifacts or []))
        for pick in picks:
            if pick:
                pick["team_artifacts"] = list(attached)
        return picks

    def _serialize_picks(self, picks: list) -> list:
        artifact_ids = [artifact.id for artifact in self._artifacts_from_picks(picks)]
        result = []
        for p in picks:
            result.append({
                "adv_id": p["definition"].id,
                "sig_id": p["signature"].id,
                "basics": [b.id for b in p["basics"]],
                "artifact_ids": list(artifact_ids),
            })
        return result

    def _deserialize_picks(self, data: list) -> list:
        roster_by_id = {d.id: d for d in ROSTER}
        artifacts_by_id = {artifact.id: artifact for artifact in ARTIFACTS}
        picks = []
        artifact_ids = data[0].get("artifact_ids", []) if data else []
        for m in data:
            defn = roster_by_id[m["adv_id"]]
            sig = next(a for a in defn.sig_options if a.id == m["sig_id"])
            basics_pool = CLASS_BASICS[defn.cls]
            basics = [next(a for a in basics_pool if a.id == bid) for bid in m["basics"]]
            picks.append({"definition": defn, "signature": sig, "basics": basics})
        artifacts = self._artifact_ids_to_artifacts(artifact_ids)
        self._attach_artifacts_to_picks(picks, artifacts)
        return picks

    def _serialize_unit(self, u) -> dict:
        return {
            "hp": u.hp, "ko": u.ko, "slot": u.slot,
            "statuses": [{"kind": s.kind, "duration": s.duration} for s in u.statuses],
            "buffs": [{"stat": b.stat, "amount": b.amount, "duration": b.duration} for b in u.buffs],
            "debuffs": [{"stat": d.stat, "amount": d.amount, "duration": d.duration} for d in u.debuffs],
            "acted": u.acted, "must_recharge": u.must_recharge, "twist_used": u.twist_used,
            "recharge_pending": getattr(u, "recharge_pending", False),
            "recharge_exposed": getattr(u, "recharge_exposed", False),
            "item_uses_left": u.item_uses_left, "ranged_uses": u.ranged_uses,
            "ability_charges": dict(u.ability_charges), "max_hp_bonus": u.max_hp_bonus,
            "extra_actions_next": u.extra_actions_next, "extra_actions_now": u.extra_actions_now,
            "retaliate_power": u.retaliate_power, "valor_rounds": u.valor_rounds,
            "untargetable": u.untargetable, "cant_act": u.cant_act,
            "dmg_reduction": u.dmg_reduction,
            "last_status_inflicted": getattr(u, "last_status_inflicted", ""),
        }

    def _serialize_artifact_states(self, team) -> list:
        return [
            {
                "id": state.artifact.id,
                "cooldown_remaining": state.cooldown_remaining,
                "used_this_battle": state.used_this_battle,
            }
            for state in getattr(team, "artifacts", [])
        ]

    def _apply_unit_state(self, u, d: dict):
        from models import StatusInstance, StatMod
        u.hp = d["hp"]; u.ko = d["ko"]; u.slot = d["slot"]
        u.statuses = [StatusInstance(kind=s["kind"], duration=s["duration"]) for s in d["statuses"]]
        u.buffs = [StatMod(stat=b["stat"], amount=b["amount"], duration=b["duration"]) for b in d["buffs"]]
        u.debuffs = [StatMod(stat=db["stat"], amount=db["amount"], duration=db["duration"]) for db in d["debuffs"]]
        u.acted = d["acted"]; u.must_recharge = d["must_recharge"]; u.twist_used = d["twist_used"]
        u.recharge_pending = d.get("recharge_pending", False)
        u.recharge_exposed = d.get("recharge_exposed", False)
        u.item_uses_left = d["item_uses_left"]; u.ranged_uses = d["ranged_uses"]
        u.ability_charges = d["ability_charges"]; u.max_hp_bonus = d["max_hp_bonus"]
        u.extra_actions_next = d["extra_actions_next"]; u.extra_actions_now = d["extra_actions_now"]
        u.retaliate_power = d["retaliate_power"]; u.valor_rounds = d["valor_rounds"]
        u.untargetable = d["untargetable"]; u.cant_act = d["cant_act"]
        u.dmg_reduction = d["dmg_reduction"]
        u.last_status_inflicted = d.get("last_status_inflicted", "")

    def _apply_artifact_states(self, team, data: list):
        states_by_id = {state.artifact.id: state for state in getattr(team, "artifacts", [])}
        for artifact_data in data or []:
            state = states_by_id.get(artifact_data.get("id"))
            if state is None:
                continue
            state.cooldown_remaining = artifact_data.get("cooldown_remaining", state.cooldown_remaining)
            state.used_this_battle = artifact_data.get("used_this_battle", state.used_this_battle)

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
            artifact = action.get("artifact")
            if artifact is not None:
                d["artifact_id"] = artifact.id
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
                d["swap_target_slot_idx"] = team.members.index(swap_target)
        return d

    def _deserialize_action(self, data: dict, team, enemy) -> dict:
        atype = data["atype"]
        action = {"type": atype}
        if atype == "ability":
            actor = team.members[data["slot_idx"]]
            all_abs = actor.all_active_abilities()
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
            from data import ARTIFACTS
            artifacts_by_id = {artifact.id: artifact for artifact in ARTIFACTS}
            artifact_id = data.get("artifact_id")
            if artifact_id in artifacts_by_id:
                action["artifact"] = artifacts_by_id[artifact_id]
            if "target_slot_idx" in data:
                t_team = team if data.get("target_team") == "own" else enemy
                action["target"] = t_team.members[data["target_slot_idx"]]
            if "swap_target_slot_idx" in data:
                action["swap_target"] = team.members[data["swap_target_slot_idx"]]
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
            "team1_artifacts": self._serialize_artifact_states(self.battle.team1),
            "team2_artifacts": self._serialize_artifact_states(self.battle.team2),
        }
        if extra:
            msg.update(extra)
        self._lan_send(msg)

    def _lan_action_state_extra(self) -> dict:
        """Return LAN metadata for the current resolved action."""
        actor = self._action_step_unit
        if not actor or not self.battle:
            return {}
        actor_player = 1 if actor in self.battle.team1.members else 2
        return {
            "action_step_player": self._action_step_player,
            "action_log_start": self._action_log_start,
            "action_actor_player": actor_player,
            "action_actor_slot": actor.slot,
        }

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
            self._apply_artifact_states(self.battle.team1, msg.get("team1_artifacts", []))
            self._apply_artifact_states(self.battle.team2, msg.get("team2_artifacts", []))
            # Update metadata
            self.battle.round_num = msg.get("round_num", self.battle.round_num)
            self.battle.winner = msg.get("winner", self.battle.winner)
            self.battle.swap_used_this_turn = msg.get("swap_used_this_turn", False)
            self.battle.init_player = msg.get("init_player", self.battle.init_player)
            self.battle.init_reason = msg.get("init_reason", getattr(self.battle, "init_reason", ""))
            new_log = msg.get("log")
            if new_log is not None:
                self.battle.log = new_log
            self._action_step_player = msg.get("action_step_player", self._action_step_player)
            self._action_log_start = msg.get("action_log_start", self._action_log_start)
            actor_player = msg.get("action_actor_player")
            actor_slot = msg.get("action_actor_slot")
            if actor_player in (1, 2) and actor_slot:
                team = self.battle.team1 if actor_player == 1 else self.battle.team2
                self._action_step_unit = next((unit for unit in team.members if unit.slot == actor_slot), None)
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
        defn = by_id[entry["defn"]]
        sig = next(a for a in defn.sig_options if a.id == entry["sig"])
        basics_pool = CLASS_BASICS[defn.cls]
        basics = [next(a for a in basics_pool if a.id == bid) for bid in entry["basics"]]
        return {
            "definition": defn,
            "signature": sig,
            "basics": basics,
        }

    def _ai_rating_for_index(self, idx: int) -> int:
        return min(1850, 850 + idx * 25)

    def _ranked_team_meta(self, idx: int, comp: dict) -> dict:
        fallback = {
            "rating": self._ai_rating_for_index(idx),
            "weight": 1.0,
        }
        meta = dict(fallback)
        meta.update(RANKED_AI_TEAM_META.get(comp["name"], {}))
        meta["rating"] = max(0, min(2000, int(meta["rating"])))
        meta["weight"] = max(0.1, float(meta["weight"]))
        return meta

    def _ranked_team_selection_weight(self, rating: int, base_weight: float, target_rating: int) -> float:
        diff = abs(rating - target_rating)
        closeness = max(0.15, 1.0 - (diff / 450.0))
        return max(0.05, base_weight * closeness)

    def _generate_ai_team(self, target_rating: int | None = None):
        if target_rating is None:
            comp = random.choice(self._ai_team_pool)
            matched_rating = None
        else:
            weighted = [
                (comp, self._ranked_team_meta(idx, comp))
                for idx, comp in enumerate(self._ai_team_pool)
            ]
            candidates = None
            for window in (50, 100, 150):
                in_window = [(entry, meta) for entry, meta in weighted if abs(meta["rating"] - target_rating) <= window]
                if in_window:
                    candidates = in_window
                    break
            if candidates is None:
                candidates = weighted
            weights = [
                self._ranked_team_selection_weight(meta["rating"], meta["weight"], target_rating)
                for _, meta in candidates
            ]
            comp, meta = random.choices(candidates, weights=weights, k=1)[0]
            matched_rating = meta["rating"]
        picks = [self._build_ai_pick(e) for e in comp["members"]]
        if "artifacts" in comp:
            artifacts = self._artifact_ids_to_artifacts(comp.get("artifacts", []))
        else:
            artifacts = self._legacy_items_to_artifacts([entry.get("item") for entry in comp["members"]])
        self._attach_artifacts_to_picks(picks, artifacts)
        return comp["name"], picks, matched_rating

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
            profile=self._ai_decision_profile,
        )
        self._set_queued(actor, best_action)
        return True

    def _finalize_battle_result(self):
        self._detail_unit = None
        self._battle_overlay = None
        self._last_result_details = []
        self._last_result_subtitle = ""
        if self.game_mode == "campaign":
            self._campaign_won_quest = (self.battle.winner == 1)
            if self._campaign_won_quest:
                summary = apply_quest_rewards(
                    self.campaign_profile,
                    self.campaign_quest_id,
                    party_adventurer_ids=self._current_party_adventurer_ids(self.p1_picks),
                )
                self._last_reward_summary = summary
                self._last_result_details = summary.get("lines", [])
                self._last_result_subtitle = "Camelot" if self.campaign_quest_id <= 4 else "Quest rewards"
                self._refresh_profile_filters()
                save_campaign(self.campaign_profile)
            else:
                self._last_reward_summary = {}
                self._last_result_details = ["No rewards - try again."]
            self.phase = "campaign_post_quest"
            return
        if self.game_mode == "single_player":
            self._apply_quick_play_rewards(self.battle.winner == 1)
        elif self.game_mode == "ranked":
            self._apply_ranked_rewards(self.battle.winner == 1)
        self.phase = "result"

    def _auto_continue_resolve_done(self):
        self._detail_unit = None
        self._battle_overlay = None
        if self.battle.winner:
            battle_log.close()
            if self.game_mode == "lan_host":
                self._lan_send_state(phase="result")
            self._finalize_battle_result()
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
                if self.phase == "select_actions" and self.selection_sub == "review_queue":
                    self._finish_selection()
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
                "using an artifact, or swapping. You can only swap once per round, though "
                "abilities and artifacts that let you swap ignore that limit.")
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
        if self.phase == "select_actions" and self.selection_sub == "review_queue":
            self._finish_selection()
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
        self._finalize_battle_result()

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
                    evt_pos = self._to_logical(e.pos)
                    if self.phase in ("team_select", "pre_battle_edit"):
                        self._handle_team_select_mouse_down(evt_pos)
                    else:
                        self.handle_click(evt_pos)
                if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    evt_pos = self._to_logical(e.pos)
                    if self.phase in ("team_select", "pre_battle_edit"):
                        self._handle_team_select_mouse_up(evt_pos)
                if e.type == pygame.MOUSEMOTION and self.phase in ("team_select", "pre_battle_edit"):
                    evt_pos = self._to_logical(e.pos)
                    self._handle_team_select_mouse_motion(evt_pos, e.buttons)

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
            btns = self._last_menu_btns or {}
            if btns.get("level_btn") and btns["level_btn"].collidepoint(pos):
                self._menu_level_card_open = not self._menu_level_card_open
            elif btns.get("level_card_close") and btns["level_card_close"] and btns["level_card_close"].collidepoint(pos):
                self._menu_level_card_open = False
            elif btns.get("gold_btn") and btns["gold_btn"].collidepoint(pos):
                self._menu_level_card_open = False
                self._guild_tab = "adventurers"
                self.phase = "guild"
            elif btns.get("camelot_btn") and btns["camelot_btn"].collidepoint(pos):
                self._menu_level_card_open = False
                self._enter_camelot()
            elif (
                btns.get("fantasia_btn") and btns["fantasia_btn"].collidepoint(pos)
                and self.campaign_profile and self.campaign_profile.quick_play_unlocked
            ):
                self._menu_level_card_open = False
                self.game_mode = "single_player"
                if hasattr(self, "_campaign_roster"):
                    del self._campaign_roster
                self._start_team_select(1)
            elif (
                btns.get("brightheart_btn") and btns["brightheart_btn"].collidepoint(pos)
                and self._ranked_unlocked()
            ):
                self._menu_level_card_open = False
                self.game_mode = "ranked"
                if hasattr(self, "_campaign_roster"):
                    del self._campaign_roster
                self._start_team_select(1)
            elif btns.get("estate_btn") and btns["estate_btn"].collidepoint(pos):
                self._menu_level_card_open = False
                self.phase = "estate_menu"
            elif btns.get("guild_btn") and btns["guild_btn"].collidepoint(pos):
                self._menu_level_card_open = False
                self._guild_tab = "adventurers"
                self.phase = "guild"
            elif btns.get("market_btn") and btns["market_btn"].collidepoint(pos):
                self._menu_level_card_open = False
                self.phase = "market_closed"
            elif btns.get("embassy_btn") and btns["embassy_btn"].collidepoint(pos):
                self._menu_level_card_open = False
                self.phase = "embassy"
            elif btns.get("settings_btn") and btns["settings_btn"].collidepoint(pos):
                self._menu_level_card_open = False
                self._confirm_reset = False
                self.phase = "settings"
            elif btns.get("exit_btn") and btns["exit_btn"].collidepoint(pos):
                pygame.quit(); sys.exit()
            elif self._menu_level_card_open:
                card_rect = btns.get("level_card_rect")
                if card_rect and not card_rect.collidepoint(pos):
                    self._menu_level_card_open = False

        elif p == "catalog":
            btns = self._last_catalog_btns or {}
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = self._catalog_return_phase
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

        elif p == "estate_menu":
            btns = self._last_estate_btns or {}
            if btns.get("parties_btn") and btns["parties_btn"].collidepoint(pos):
                self._teambuilder_return_phase = "estate_menu"
                self.phase = "teambuilder"
            elif btns.get("guidebook_btn") and btns["guidebook_btn"].collidepoint(pos):
                self._catalog_tab = "adventurers"
                self._catalog_selected = None
                self._catalog_scroll = 0
                self._catalog_return_phase = "estate_menu"
                self.phase = "catalog"
                if self.campaign_profile:
                    self.campaign_profile.new_unlocks.discard("adventurers")
                    save_campaign(self.campaign_profile)
            elif btns.get("training_btn") and btns["training_btn"].collidepoint(pos):
                self.phase = "training_menu"
            elif btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "menu"

        elif p == "training_menu":
            btns = self._last_training_btns or {}
            if btns.get("local_btn") and btns["local_btn"].collidepoint(pos):
                self.game_mode = "pvp"
                self._start_team_select(1)
            elif btns.get("lan_btn") and btns["lan_btn"].collidepoint(pos):
                self._lan_return_phase = "training_menu"
                self._lan_role = None
                self._lan_status = ""
                self._lan = None
                self.phase = "lan_lobby"
            elif btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "estate_menu"

        elif p == "guild":
            btns = self._last_guild_btns or {}
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "menu"
                return
            for tab_key, rect in btns.get("tab_btns", []):
                if rect.collidepoint(pos):
                    self._guild_tab = tab_key
                    return
            for rect, adv_id in btns.get("buy_adventurer_btns", []):
                if rect.collidepoint(pos):
                    self._last_result_details = self._hire_adventurer(adv_id, use_voucher=False)
                    return
            for rect, adv_id in btns.get("voucher_btns", []):
                if rect.collidepoint(pos):
                    self._last_result_details = self._hire_adventurer(adv_id, use_voucher=True)
                    return
            for rect, artifact_id in btns.get("buy_artifact_btns", []):
                if rect.collidepoint(pos):
                    self._last_result_details = self._buy_artifact(artifact_id)
                    return

        elif p == "embassy":
            btns = self._last_embassy_btns or {}
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "menu"
                return
            for rect, dollars in btns.get("offer_btns", []):
                if rect.collidepoint(pos):
                    self._last_result_details = self._buy_embassy_gold(dollars)
                    return

        elif p == "market_closed":
            btns = self._last_market_btns or {}
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "menu"
                return

        elif p == "lan_lobby":
            btns = self._last_lan_lobby_btns or {}
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                if self._lan:
                    self._lan.close()
                    self._lan = None
                self._lan_role = None
                self._lan_status = ""
                self.game_mode = "pvp"
                self.phase = self._lan_return_phase
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
                        self.campaign_profile.saved_teams[slot_idx] = None
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
                self.phase = self._campaign_back_phase
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
                valid_teams = [t for t in teams[:self._saved_team_slot_count()] if t is not None]
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
                            pick["signature"], pick["basics"], pick.get("item"),
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
                if self.campaign_quest_id <= 4:
                    if self._campaign_won_quest and self.campaign_quest_id >= 4:
                        self.phase = "menu"
                    else:
                        self.campaign_mission_id = 1
                        self.phase = "campaign_quest_select"
                elif self._campaign_won_quest:
                    if self.campaign_profile.campaign_complete:
                        self.phase = "campaign_complete"
                    else:
                        self.phase = "menu"
                else:
                    self.phase = self._campaign_back_phase

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
        if self._is_in_battle() and self._battle_overlay == "log":
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
        clicks = getattr(self, "_last_team_clicks", None) or {}
        mouse_pos = self._to_logical(pygame.mouse.get_pos())
        roster_view = clicks.get("roster_viewport")
        artifact_view = clicks.get("artifact_viewport")
        step = 40
        if roster_view and roster_view.collidepoint(mouse_pos):
            max_scroll = clicks.get("roster_scroll_max", 0)
            self.team_select_scroll -= e.y * step
            self.team_select_scroll = max(0, min(self.team_select_scroll, max_scroll))
            return
        if artifact_view and artifact_view.collidepoint(mouse_pos):
            max_scroll = clicks.get("artifact_scroll_max", 0)
            self.team_artifact_scroll -= e.y * step
            self.team_artifact_scroll = max(0, min(self.team_artifact_scroll, max_scroll))

    # ─────────────────────────────────────────────────────────────────────────
    # TEAM SELECTION
    # ─────────────────────────────────────────────────────────────────────────

    def _do_team_select_back(self):
        """Shared back-navigation logic for team_select, used by Back button and ESC."""
        if self._detail_unit is not None:
            self._detail_unit = None
            return
        if self._import_modal_open:
            self._import_modal_open = False
            self._import_modal_text = ""
            self._import_modal_error = ""
            return
        if self._team_member_prompt_slot is not None:
            self._team_member_prompt_slot = None
            return
        if self.phase == "pre_battle_edit":
            if self._pbe_back_phase:
                self.phase = self._pbe_back_phase
            return
        if self.game_mode == "teambuilder":
            self.phase = "teambuilder"
        else:
            self.phase = "menu"

    def _parse_team_import(self, text: str, allow_all: bool):
        """Parse a team import string. Returns (picks_list, error_string).
        picks_list is None on any validation error.
        allow_all=True: practice/single_player mode (full ROSTER/ARTIFACTS/CLASS_BASICS).
        allow_all=False: use campaign/teambuilder restricted lists.
        """
        # Determine the active pools
        if allow_all:
            active_roster     = ROSTER
            active_artifacts  = ARTIFACTS
            active_cls_basics = CLASS_BASICS
        else:
            active_roster     = getattr(self, "_campaign_roster", ROSTER)
            active_artifacts  = getattr(self, "_campaign_artifacts", ARTIFACTS)
            active_cls_basics = getattr(self, "_campaign_basics", CLASS_BASICS)

        def _norm(s: str) -> str:
            return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

        # Build relaxed lookup dicts so capitalization and spaces do not matter.
        roster_by_name = {_norm(d.name): d for d in active_roster}
        artifacts_by_name = {_norm(artifact.name): artifact for artifact in active_artifacts}

        # Normalize lines
        raw_lines = [l.rstrip() for l in text.splitlines()]
        lines = [l for l in raw_lines if l.strip()]

        def _parse_bullet_name(raw: str):
            s = raw.strip()
            if s.startswith("-"):
                s = s[1:].strip()
            return s

        def _available_sigs(defn):
            if allow_all:
                return defn.sig_options
            return defn.sig_options[:unlocked_signature_count(self._adventurer_level(defn.id))]

        def _parse_member_header_sig(block):
            if len(block) != 3 or "@" not in block[0]:
                return None
            adv_part, sig_part = block[0].split("@", 1)
            defn = roster_by_name.get(_norm(adv_part))
            if defn is None:
                return None
            sig = {_norm(s.name): s for s in _available_sigs(defn)}.get(_norm(sig_part))
            if sig is None:
                return None
            cls_pool = active_cls_basics.get(defn.cls, [])
            basics_by_name = {_norm(b.name): b for b in cls_pool}
            basic_names = [_norm(_parse_bullet_name(raw)) for raw in block[1:3]]
            basic1 = basics_by_name.get(basic_names[0])
            basic2 = basics_by_name.get(basic_names[1])
            if basic1 is None or basic2 is None or basic1 is basic2:
                return None
            return {
                "definition": defn,
                "signature": sig,
                "basics": [basic1, basic2],
            }

        def _parse_artifact_names(name_lines):
            parsed_artifacts = []
            seen = set()
            for raw in name_lines:
                key = _norm(_parse_bullet_name(raw))
                artifact = artifacts_by_name.get(key)
                if artifact is None or artifact.id in seen:
                    return None
                parsed_artifacts.append(artifact)
                seen.add(artifact.id)
            return parsed_artifacts if len(parsed_artifacts) == 3 else None

        def _try_parse(import_lines):
            picks = []

            artifact_header_idx = next(
                (i for i, line in enumerate(import_lines) if _norm(line.split(":", 1)[0]) == "artifacts"),
                None,
            )
            if artifact_header_idx is not None:
                header = import_lines[artifact_header_idx]
                member_lines = import_lines[:artifact_header_idx]
                artifact_lines = import_lines[artifact_header_idx + 1:]
                if ":" in header and header.split(":", 1)[1].strip():
                    return (None, "Can't upload this.")
                artifacts = _parse_artifact_names(artifact_lines)
                if artifacts is None or len(member_lines) != 9 or len(artifact_lines) != 3:
                    return (None, "Can't upload this.")

                if all("@" in member_lines[i] for i in range(0, 9, 3)):
                    for block_start in range(0, 9, 3):
                        parsed = _parse_member_header_sig(member_lines[block_start:block_start + 3])
                        if parsed is None:
                            return (None, "Can't upload this.")
                        picks.append(parsed)
                else:
                    return (None, "Can't upload this.")
            else:
                return (None, "Can't upload this.")

            if len(picks) != 3:
                return (None, "Can't upload this.")
            self._attach_artifacts_to_picks(picks, artifacts)
            return (picks, "")

        parsed_picks, err = _try_parse(lines)
        if parsed_picks is not None:
            return (parsed_picks, err)

        # Allow an optional first-line party name in the new import format.
        if lines and "@" not in lines[0] and not lines[0].lstrip().startswith("-") and _norm(lines[0]) != "artifacts":
            return _try_parse(lines[1:])

        return (None, "Can't upload this.")

    def _start_team_select(self, player_num):
        if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked"):
            self._refresh_profile_filters()
        self._ai_decision_profile = "ranked" if self.game_mode == "ranked" else "quick"
        self.building_player = player_num
        self.sub_phase = "pick_adventurers"
        self.team_picks = self._normalize_builder_picks([])
        self.team_artifacts = []
        self._reset_team_builder_ui_state()
        self.phase = "team_select"
        self._maybe_show_tutorial("party_editor", "Select three adventurers to form a party!")

    def _handle_team_select_click(self, pos):
        clicks = self._last_team_clicks
        if clicks is None:
            return

        # Determine active roster for campaign / teambuilder vs normal mode
        if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked") and hasattr(self, "_campaign_roster"):
            active_roster     = self._campaign_roster
            active_items      = self._campaign_artifacts
            active_cls_basics = self._campaign_basics
        else:
            active_roster     = ROSTER
            active_items      = ARTIFACTS
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
                }
                self.team_picks[idx].pop("signature", None)
                self.team_picks[idx].pop("basics", None)
                self.sig_choice = None
                self.basic_choices = []
                self.item_choice = []
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
                    if len(self.team_artifacts) < 3:
                        self.sub_phase = "pick_item"
                        self.item_choice = [
                            idx for idx, artifact in enumerate(active_items)
                            if artifact.id in {a.id for a in self.team_artifacts}
                        ]
                        self.team_select_scroll = 0
                    elif _in_pbe:
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
                if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked") and self.campaign_profile:
                    available_sigs = defn.sig_options[:unlocked_signature_count(self._adventurer_level(defn.id))]
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
                if self._editing_single_member:
                    self._editing_single_member = False
                    self._finish_team_select()
                else:
                    self._editing_from_roster = False
                    self.sub_phase = "pick_adventurers"
                self.team_select_scroll = 0

        elif self.sub_phase == "pick_item":
            back = clicks.get("back")
            if back and back.collidepoint(pos):
                self._do_team_select_back()
                return
            for rect, idx in clicks.get("items", []):
                if rect.collidepoint(pos):
                    if idx in self.item_choice:
                        self.item_choice.remove(idx)
                    elif len(self.item_choice) < 3:
                        self.item_choice.append(idx)
                    return
            confirm = clicks.get("confirm")
            if confirm and confirm.collidepoint(pos) and len(self.item_choice) == 3:
                self.team_artifacts = [active_items[idx] for idx in self.item_choice[:3]]
                self._attach_artifacts_to_picks(self.team_picks, self.team_artifacts)
                if _in_pbe:
                    self._confirm_pre_battle_edit()
                else:
                    self._finish_team_select()
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
                            pick["signature"], pick["basics"], pick.get("item"),
                        )
                    return

    def _team_drag_target_at_pos(self, pos):
        clicks = self._last_team_clicks or {}
        for rect, defn in clicks.get("roster_cards", []):
            if rect.collidepoint(pos):
                return ("roster_card", defn)
        for rect, idx in clicks.get("party_slots", []):
            if rect.collidepoint(pos):
                return ("party_slot", idx)
        return None

    def _handle_team_select_mouse_down(self, pos):
        if self.phase not in ("team_select", "pre_battle_edit"):
            return
        self._team_drag_start_pos = pos
        self._team_mouse_down_target = self._team_drag_target_at_pos(pos)
        self._team_member_prompt_slot = None
        if self._detail_unit is not None and self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            return
        if self._import_modal_open:
            return
        if self._team_mouse_down_target is None:
            self._reset_team_drag()
            return
        kind, payload = self._team_mouse_down_target
        if kind == "roster_card":
            self._team_drag_source = ("roster", payload)
            self._team_drag_defn = payload
            self._team_drag_slot = None
        elif kind == "party_slot" and self.team_picks[payload]:
            self._team_drag_source = ("party", payload)
            self._team_drag_defn = self.team_picks[payload].get("definition")
            self._team_drag_slot = payload
        else:
            self._reset_team_drag()
            self._team_mouse_down_target = ("party_slot", payload)

    def _handle_team_select_mouse_motion(self, pos, buttons):
        if self.phase not in ("team_select", "pre_battle_edit"):
            return
        if not self._team_drag_source or not self._team_drag_start_pos:
            return
        if not buttons or not buttons[0]:
            return
        if not self._team_drag_active:
            dx = pos[0] - self._team_drag_start_pos[0]
            dy = pos[1] - self._team_drag_start_pos[1]
            if (dx * dx + dy * dy) < 64:
                return
            self._team_drag_active = True
        target = self._team_drag_target_at_pos(pos)
        self._team_drag_hover_slot = target[1] if target and target[0] == "party_slot" else None
        clicks = self._last_team_clicks or {}
        remove_zone = clicks.get("roster_drop_zone")
        self._team_drag_hover_remove = (
            self.phase == "team_select"
            and self._team_drag_source[0] == "party"
            and remove_zone is not None
            and remove_zone.collidepoint(pos)
        )

    def _handle_team_select_mouse_up(self, pos):
        if self.phase not in ("team_select", "pre_battle_edit"):
            self._reset_team_drag()
            return
        clicks = self._last_team_clicks or {}

        if self._detail_unit is not None and self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            self._reset_team_drag()
            return

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
                    self.team_picks = self._normalize_builder_picks(picks)
                    self.team_artifacts = self._artifacts_from_picks(picks)
                    self._attach_artifacts_to_picks(self.team_picks, self.team_artifacts)
                    self.roster_selected = next((pick["definition"] for pick in self.team_picks if pick), None)
                    self._builder_set_focus(next((idx for idx, pick in enumerate(self.team_picks) if pick), None))
                    self._import_modal_open = False
                    self._import_modal_text = ""
                    self._import_modal_error = ""
                else:
                    self._import_modal_error = err
            self._reset_team_drag()
            return

        if self._team_member_prompt_slot is not None:
            slot_idx = self._team_member_prompt_slot
            change_btn = clicks.get("prompt_change")
            detail_btn = clicks.get("prompt_details")
            prompt_rect = clicks.get("member_prompt_rect")
            if change_btn and change_btn.collidepoint(pos):
                self._builder_set_focus(slot_idx)
                self._team_member_prompt_slot = None
                self._reset_team_drag()
                return
            if detail_btn and detail_btn.collidepoint(pos):
                self._builder_open_detail_for_pick(slot_idx)
                self._team_member_prompt_slot = None
                self._reset_team_drag()
                return
            if prompt_rect is None or not prompt_rect.collidepoint(pos):
                self._team_member_prompt_slot = None

        if self._team_drag_active and self._team_drag_source:
            source_kind, source_payload = self._team_drag_source
            drop_target = self._team_drag_target_at_pos(pos)
            if source_kind == "roster" and drop_target and drop_target[0] == "party_slot":
                self._builder_add_roster_defn_to_slot(source_payload, drop_target[1])
            elif source_kind == "party":
                if drop_target and drop_target[0] == "party_slot":
                    self._builder_move_pick(source_payload, drop_target[1])
                elif self.phase == "team_select":
                    remove_zone = clicks.get("roster_drop_zone")
                    if remove_zone and remove_zone.collidepoint(pos):
                        self._builder_remove_slot(source_payload)
            self._reset_team_drag()
            return

        target = self._team_drag_target_at_pos(pos)
        if target == self._team_mouse_down_target and target is not None:
            now = pygame.time.get_ticks()
            is_double = (
                self._team_last_click_target == target
                and now - self._team_last_click_time <= 350
            )
            self._team_last_click_target = target
            self._team_last_click_time = now

            if target[0] == "roster_card":
                defn = target[1]
                self.roster_selected = defn
                self._builder_set_focus(None)
                if is_double:
                    self._builder_open_detail_for_roster(defn)
            elif target[0] == "party_slot":
                slot_idx = target[1]
                self.roster_selected = None
                self._builder_set_focus(slot_idx)
                if is_double and self.team_picks[slot_idx]:
                    self._team_member_prompt_slot = slot_idx
            self._reset_team_drag()
            return

        for rect, idx in clicks.get("sig_buttons", []):
            if rect.collidepoint(pos):
                self._builder_set_signature_choice(idx)
                self._reset_team_drag()
                return
        for rect, idx in clicks.get("basic_buttons", []):
            if rect.collidepoint(pos):
                self._builder_toggle_basic_choice(idx)
                self._reset_team_drag()
                return
        for rect, artifact in clicks.get("artifact_entries", []):
            if rect.collidepoint(pos):
                if artifact.id not in {entry.id for entry in self.team_artifacts} and len(self.team_artifacts) < 3:
                    self.team_artifacts.append(artifact)
                    self._attach_artifacts_to_picks(self.team_picks, self.team_artifacts)
                self._team_artifact_focus = artifact
                self._reset_team_drag()
                return
        for rect, artifact in clicks.get("artifact_selected", []):
            if rect.collidepoint(pos):
                self._team_artifact_focus = artifact
                self._reset_team_drag()
                return
        for rect, artifact in clicks.get("artifact_remove", []):
            if rect.collidepoint(pos):
                self._builder_remove_artifact(artifact)
                self._reset_team_drag()
                return

        import_btn = clicks.get("import_btn")
        if self.phase == "team_select" and import_btn and import_btn.collidepoint(pos):
            self._import_modal_open = True
            self._import_modal_text = ""
            self._import_modal_error = ""
            self._reset_team_drag()
            return

        confirm = clicks.get("confirm")
        if confirm and confirm.collidepoint(pos) and self._team_builder_ready():
            self._attach_artifacts_to_picks(self.team_picks, self.team_artifacts)
            if self.phase == "pre_battle_edit":
                self._confirm_pre_battle_edit()
            else:
                self._finish_team_select()
            self._reset_team_drag()
            return

        back = clicks.get("back")
        if back and back.collidepoint(pos):
            self._do_team_select_back()
            self._reset_team_drag()
            return

        self._reset_team_drag()

    def _handle_team_select_click(self, pos):
        """Fallback for any legacy code path that still sends a single click directly."""
        self._handle_team_select_mouse_down(pos)
        self._handle_team_select_mouse_up(pos)

    def _ensure_picks_have_items(self, picks):
        """Normalize and attach the shared party artifacts without auto-filling extras."""
        if not picks:
            return
        existing = self._artifacts_from_picks(picks)
        self._attach_artifacts_to_picks(picks, existing[:3])

    def _enter_pre_battle_edit(self, p1_picks, enemy_picks, back_phase):
        """Transition to the pre-battle team editor."""
        self.team_picks = self._normalize_builder_picks(p1_picks)
        self.team_artifacts = self._artifacts_from_picks(self.team_picks)
        self._pbe_enemy_picks = list(enemy_picks) if enemy_picks else []
        self._pbe_back_phase = back_phase
        self.sub_phase = "pick_adventurers"
        self._reset_team_builder_ui_state()
        self._lan_pbe_local_ready = False
        self._lan_pbe_opponent_ready = False
        self.phase = "pre_battle_edit"

    def _confirm_pre_battle_edit(self):
        """Player confirmed their formation in pre-battle edit."""
        if not self._team_builder_ready():
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
        self._attach_artifacts_to_picks(self.team_picks, self.team_artifacts)
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
            if self.game_mode in ("single_player", "ranked"):
                target_rating = self.campaign_profile.ranked_rating if self.game_mode == "ranked" else None
                self.ai_comp_name, self.p2_picks, self._ranked_ai_rating = self._generate_ai_team(target_rating)
                self._enter_pre_battle_edit(self.p1_picks, self.p2_picks, "team_select")
                return
            else:
                # pvp - pass to player 2
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
        self._refresh_profile_filters()
        # Load existing team picks if available, otherwise start fresh
        existing = self._resolve_saved_team(slot_idx)
        if existing is not None:
            self.team_picks = self._normalize_builder_picks(existing)
            self.team_artifacts = self._artifacts_from_picks(existing)
        else:
            self.team_picks = self._normalize_builder_picks([])
            self.team_artifacts = []
        self.building_player = 1
        self.sub_phase = "pick_adventurers"
        self._reset_team_builder_ui_state()
        self.phase = "team_select"
        self._maybe_show_tutorial("party_editor", "Select three adventurers to form a party!")

    def _start_teambuilder_edit_member(self, slot_idx: int, member_idx: int):
        """Jump directly to editing one member's sig/basics/item without changing adventurers."""
        self._editing_team_slot = slot_idx
        self._editing_single_member = True
        self.game_mode = "teambuilder"
        self._refresh_profile_filters()
        # Pre-load the existing team picks so the other two members are preserved.
        existing = self._resolve_saved_team(slot_idx)
        if existing is None:
            # Fallback: start fresh if resolve fails.
            self._editing_single_member = False
            self._start_team_select(1)
            return
        self.team_picks = self._normalize_builder_picks(existing)
        self.team_artifacts = self._artifacts_from_picks(existing)
        self.building_player = 1
        self._reset_team_builder_ui_state()
        self._editing_single_member = True
        self._builder_set_focus(member_idx)
        self.sub_phase = "pick_adventurers"
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
            members.append(entry)
        # Preserve existing name if the team already has one.
        teams = self.campaign_profile.saved_teams
        existing_name = None
        if slot < len(teams) and teams[slot] is not None:
            existing_name = teams[slot].get("name")
        team_name = existing_name if existing_name else f"Party {slot + 1}"
        entry = {
            "name": team_name,
            "members": members,
            "artifact_ids": [artifact.id for artifact in self.team_artifacts],
        }
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
        save_path = get_campaign_save_path()
        if os.path.exists(save_path):
            os.remove(save_path)
        self.campaign_profile = load_campaign()
        self._refresh_profile_filters()
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
        artifacts_by_id = {artifact.id: artifact for artifact in ARTIFACTS}
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
            picks.append({"definition": defn, "signature": sig, "basics": basics})
        artifact_ids = team_data.get("artifact_ids", [])
        artifacts = [artifacts_by_id[artifact_id] for artifact_id in artifact_ids if artifact_id in artifacts_by_id]
        self._attach_artifacts_to_picks(picks, artifacts)
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
            artifacts = self._artifacts_from_picks(picks)
            if artifacts:
                battle_log.log(
                    f"    Artifacts: {', '.join(artifact.name for artifact in artifacts)}"
                )
        battle_log.section("BATTLE START")

        team1 = create_team(p1_name, self.p1_picks)
        team2 = create_team(p2_name, self.p2_picks)
        self.battle = BattleState(team1=team1, team2=team2)
        self.battle_log_scroll = 0
        apply_passive_stats(team1, self.battle)
        apply_passive_stats(team2, self.battle)
        self.phase = "battle"
        self._battle_overlay = None
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
        self._battle_overlay = None
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
        self._battle_overlay = None
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
        # All units have actions queued — wait for explicit lock-in unless this is an extra-action phase.
        self.current_actor = None
        self.pending_action = None
        self.selection_sub = "review_queue"

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
                artifact = action_dict.get("artifact")
                desc = f"{artifact.name if artifact else 'Artifact'} → {tname}"
                if action_dict.get("swap_target") is not None:
                    desc += f" ↔ {action_dict['swap_target'].name}"
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
        self._battle_overlay = None
        self.phase = "battle"
        if self.game_mode == "lan_host":
            self._lan_send_state(phase="battle")

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
        self.pending_action = None
        self._battle_overlay = None
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

    def _reopen_queued_selection(self, unit, is_extra: bool | None = None):
        """Re-open a previously queued action so it can be changed before lock-in."""
        if not self.battle or unit is None or unit.ko:
            return False
        team = self.battle.get_team(self.selecting_player)
        if unit not in team.members:
            return False
        if is_extra is None:
            if unit.queued is not None:
                is_extra = False
            elif unit.queued2 is not None:
                is_extra = True
            else:
                return False
        queued_action = unit.queued2 if is_extra else unit.queued
        if queued_action is None:
            return False
        if is_extra:
            unit.queued2 = None
        else:
            unit.queued = None
        self.current_actor = unit
        self.current_is_extra = bool(is_extra)
        self.pending_action = None
        self.selection_sub = "pick_action"
        self._battle_overlay = None
        return True

    def _queued_action_tag(self, unit, is_extra: bool) -> tuple[str, tuple]:
        q = unit.queued2 if is_extra else unit.queued
        if q is None:
            return ("Waiting", TEXT_MUTED)
        if q["type"] == "skip":
            return ("Recharge" if unit.must_recharge else "Skip", TEXT_MUTED)
        if q["type"] == "swap":
            return ("Swap", CYAN)
        if q["type"] == "item":
            return ("Artifact", GREEN)
        ability = q.get("ability")
        if ability is not None and ability.category == "twist":
            return ("Twist", ORANGE)
        if ability is not None and ability.category == "signature":
            return ("Signature", CYAN)
        return ("Ready", GREEN)

    def _queue_units_for_strip(self):
        units = []
        for unit, is_extra in self.selection_order:
            if unit.ko:
                continue
            tag, color = self._queued_action_tag(unit, is_extra)
            units.append((unit, is_extra, tag, color))
        return units

    def _queued_artifact_ids(self, *, exclude_actor=None) -> set[str]:
        if not self.battle:
            return set()
        team = self.battle.get_team(self.selecting_player)
        queued_ids = set()
        for unit in team.members:
            if unit == exclude_actor:
                continue
            for action in (unit.queued, unit.queued2):
                if action and action.get("type") == "item" and action.get("artifact") is not None:
                    queued_ids.add(action["artifact"].id)
        return queued_ids

    def _current_valid_targets(self):
        actor = self.current_actor
        if not self.battle or not actor or self.selection_sub != "pick_target" or not self.pending_action:
            return []
        team = self.battle.get_team(self.selecting_player)
        if self.pending_action["type"] == "ability":
            ability = self.pending_action["ability"]
            if self.pending_action.get("substep") == "subterfuge_swap_target":
                return get_subterfuge_swap_targets(
                    self.battle, self.selecting_player, self.pending_action.get("target")
                )
            return get_legal_targets(self.battle, self.selecting_player, actor, ability)
        if self.pending_action["type"] == "swap":
            return [unit for unit in team.alive() if unit != actor]
        if self.pending_action["type"] == "item":
            return get_legal_item_targets(
                self.battle,
                self.selecting_player,
                actor,
                artifact=self.pending_action.get("artifact"),
                primary_target=self.pending_action.get("target"),
            )
        return []

    def _build_action_groups(self, actor, team, is_last):
        groups = {
            "basics": [],
            "signature": [],
            "twist": [],
            "artifacts": [],
            "utility": [],
        }

        if not actor.must_recharge:
            abilities = actor.all_active_abilities(is_last)
            valid_abs = [ability for ability in abilities if can_use_ability(actor, ability, team)]
            for ability in valid_abs:
                label = ability.name
                if ability.category == "basic":
                    groups["basics"].append({"label": label, "action": {"type": "ability", "ability": ability, "target": None}})
                elif ability.category == "signature":
                    groups["signature"].append({"label": label, "action": {"type": "ability", "ability": ability, "target": None}})
                elif ability.category == "twist":
                    groups["twist"].append({"label": label, "action": {"type": "ability", "ability": ability, "target": None}})

            reserved_artifacts = self._queued_artifact_ids(exclude_actor=actor)
            for artifact_state in ready_active_artifacts(team):
                artifact = artifact_state.artifact
                if artifact.id in reserved_artifacts:
                    continue
                groups["artifacts"].append({"label": artifact.name, "action": {"type": "item", "artifact": artifact, "target": None}})

        swap_disabled = self.battle.swap_used_this_turn or self._swap_queued_this_turn() or actor.has_status("root") or actor.must_recharge
        if not swap_disabled:
            groups["utility"].append({"label": "Swap", "action": {"type": "swap", "target": None}})
        groups["utility"].append({"label": "Recharge" if actor.must_recharge else "Skip", "action": {"type": "skip"}})
        groups["utility"].append({"label": "Back", "action": {"type": "back"}})
        return [{"key": key, "actions": groups[key]} for key in ("basics", "signature", "twist", "artifacts", "utility")]

    def _selection_prompt(self):
        if self._is_lan() and self.selecting_player != self._lan_my_player():
            return ("Opponent is choosing actions", "Their queue will resolve after they lock in.")
        if self.selection_sub == "review_queue":
            return ("Queue ready", "Click a queued chip or friendly adventurer to revise anything, then lock actions when you’re ready.")
        actor = self.current_actor
        if actor is None:
            return ("Waiting for next adventurer", "")
        prefix = "Extra action" if self.current_is_extra else "Queueing action"
        if self.selection_sub == "pick_target":
            if (self.pending_action and self.pending_action.get("type") == "ability"
                        and self.pending_action.get("ability").id == "subterfuge"
                        and self.pending_action.get("substep") == "subterfuge_swap_target"):
                return (f"{prefix}: {actor.name}", "Choose the second target for Subterfuge.")
            return (f"{prefix}: {actor.name}", "Click a highlighted target in the arena.")
        if actor.must_recharge:
            return (f"{prefix}: {actor.name}", "This adventurer must recharge this round. You can still click a queued chip or friendly adventurer to revise earlier choices.")
        return (f"{prefix}: {actor.name}", "Follow the queue order below, then choose from basics, signature, twist, artifacts, or utility. Click a queued chip or friendly adventurer to revise earlier choices.")

    def _handle_battle_strip_click(self, pos):
        buttons = self._last_battle_strip_btns or {}
        if buttons.get("log") and buttons["log"].collidepoint(pos):
            self._battle_overlay = None if self._battle_overlay == "log" else "log"
            return True
        if buttons.get("artifacts") and buttons["artifacts"].collidepoint(pos):
            self._battle_overlay = None if self._battle_overlay == "artifacts" else "artifacts"
            return True
        for rect, unit, is_extra in buttons.get("queue", []):
            if rect.collidepoint(pos):
                self._reopen_queued_selection(unit, is_extra)
                return True
        if buttons.get("clear") and buttons["clear"].collidepoint(pos):
            self._battle_overlay = None
            self._restart_selection()
            return True
        if buttons.get("lock") and buttons["lock"].collidepoint(pos):
            self._battle_overlay = None
            self._finish_selection()
            return True
        if buttons.get("continue") and buttons["continue"].collidepoint(pos):
            if self.phase == "actions_resolving":
                self.phase = "resolving"
                self._do_single_resolution(self._resolving_player)
            elif self.phase == "battle_start":
                self._enter_round_start()
                if self.game_mode == "lan_host":
                    self._lan_send_state(phase=self.phase)
            elif self.phase == "end_of_round":
                self._enter_round_start()
                if self.game_mode == "lan_host":
                    self._lan_send_state(phase=self.phase)
            elif self.phase == "action_result":
                self._resolve_next_step()
            elif self.phase == "resolve_done":
                self._auto_continue_resolve_done()
            elif self.phase == "battle":
                self._tk_btn_label = None
                self._tk_btn_rect = None
                if self._is_lan() and self.game_mode == "lan_host":
                    self._lan_send_state(phase="battle")
            return True
        for rect, action_dict in buttons.get("actions", []):
            if rect.collidepoint(pos):
                self._handle_pick_action(pos)
                return True
        return False

    def _handle_action_select_click(self, pos):
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return

        overlay_btns = self._last_battle_overlay_btns or {}
        if overlay_btns.get("close") and overlay_btns["close"].collidepoint(pos):
            self._battle_overlay = None
            return
        if self._battle_overlay:
            return

        if pos[1] >= BATTLE_STRIP_RECT.y:
            if self._handle_battle_strip_click(pos):
                return

        if ARENA_RECT.collidepoint(pos):
            unit = self._unit_at_pos(pos)
            if self.selection_sub == "pick_target":
                if self._handle_pick_target(pos):
                    return
                if unit and self._reopen_queued_selection(unit):
                    return
                if unit:
                    self._detail_unit = None if self._detail_unit is unit else unit
            else:
                if unit and self._reopen_queued_selection(unit):
                    return
                if unit:
                    self._detail_unit = None if self._detail_unit is unit else unit
            return

    def _handle_pick_action(self, pos):
        actor = self.current_actor
        if actor is None:
            self.pending_action = None
            self.selection_sub = "pick_action"
            self._advance_selection()
            return
        team  = self.battle.get_team(self.selecting_player)
        is_last = len(team.alive()) == 1 and team.alive()[0] == actor

        for rect, action_dict in self._last_action_buttons:
            if rect.collidepoint(pos):
                atype = action_dict["type"]

                if atype == "back":
                    self._go_back_one_selection()
                    return

                if actor.must_recharge and atype != "skip":
                    self.battle.log_add(f"{actor.name} must recharge this round.")
                    return

                if atype == "skip":
                    self._maybe_show_tutorial(
                        "ranged_recharge_skip",
                        "After using three abilities, or two while ranged for mixed adventurers, adventurers become idle for a full round. While idle, they can be targeted by melee adventurers and must use their action to recharge.",
                    )
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
                            "they become idle and must spend their next turn recharging.")
                    elif role == "melee":
                        self._maybe_show_tutorial(
                            "target_melee",
                            "Melee adventurers can only target the frontline, unless "
                            "the target is idle, and most melee abilities deal no "
                            "damage from the backline.")
                    elif role in ("noble", "warlock"):
                        self._maybe_show_tutorial(
                            "target_mixed",
                            "Mixed adventurers are melee while in the frontline and ranged while "
                            "in the backline. They only increment ranged recharge when using "
                            "abilities from the backline, and recharge after two abilities.")
                    return

                if atype == "item":
                    artifact = action_dict.get("artifact")
                    if artifact is not None and artifact.id in self._queued_artifact_ids(exclude_actor=actor):
                        self.battle.log_add(f"{artifact.name} is already queued for this turn.")
                        return
                    targets = get_legal_item_targets(
                        self.battle, self.selecting_player, actor, artifact=artifact)
                    if not targets:
                        self.battle.log_add(f"{actor.name} cannot use {artifact.name}.")
                        return
                    if len(targets) == 1:
                        self._set_queued(actor, {"type": "item", "artifact": artifact, "target": targets[0]})
                        self._on_action_queued()
                        return
                    self.pending_action = {"type": "item", "artifact": artifact, "target": None}
                    self.selection_sub = "pick_target"
                    return

    def _handle_pick_target(self, pos):
        if not self.pending_action:
            return False

        actor = self.current_actor
        if actor is None:
            self.pending_action = None
            self.selection_sub = "pick_action"
            self._advance_selection()
            return True
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
                        return True

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
                        return True
                    action = {"type": "ability", "ability": ability, "target": unit}
                    if ability.id == "subterfuge":
                        action["target"] = self.pending_action.get("target")
                        action["swap_target"] = unit
                    self._set_queued(actor, action)
                    self._on_action_queued()
                    return True

        elif atype == "item":
            artifact = self.pending_action.get("artifact")
            primary = self.pending_action.get("target")
            if artifact and artifact.id == "magic_mirror" and primary is not None:
                targets = get_legal_item_targets(
                    self.battle, self.selecting_player, actor,
                    artifact=artifact, primary_target=primary,
                )
            else:
                targets = get_legal_item_targets(
                    self.battle, self.selecting_player, actor,
                    artifact=artifact,
                )
            if not targets:
                return False
            all_rects = {}
            all_rects.update({u: SLOT_RECTS_P1.get(u.slot) for u in self.battle.team1.alive()})
            all_rects.update({u: SLOT_RECTS_P2.get(u.slot) for u in self.battle.team2.alive()})
            for unit, rect in all_rects.items():
                if rect and rect.collidepoint(pos) and unit in targets:
                    if artifact and artifact.id == "magic_mirror" and primary is None:
                        self.pending_action["target"] = unit
                        return True
                    action = {"type": "item", "artifact": artifact, "target": primary or unit}
                    if artifact and artifact.id == "magic_mirror":
                        action["swap_target"] = unit
                    self._set_queued(actor, action)
                    self._on_action_queued()
                    return True

        # Cancel: click anywhere else goes back to pick_action
        # (handled by absence of match above)
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # RESOLUTION
    # ─────────────────────────────────────────────────────────────────────────

    def _do_single_resolution(self, player_num):
        """Begin step-through resolution for player_num's queued actions."""
        self._begin_step_resolution(player_num)

    def _begin_step_resolution(self, player_num):
        """Resolve player_num's queued actions. Steps through one at a time unless fast_resolution."""
        self._battle_overlay = None
        self._action_step_player = player_num
        self.battle.log_add(f"─── P{player_num} Actions ───")

        if self.campaign_profile and self.campaign_profile.fast_resolution:
            # Fast mode: resolve everything at once
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
            if self.game_mode == "lan_host":
                self._lan_send_state(phase="action_result", extra=self._lan_action_state_extra())
            return
        # All actions done — run finish logic
        self._finish_step_resolution()

    def _finish_step_resolution(self):
        """After all step-through actions are done, route to the appropriate next phase."""
        player_num = self._action_step_player
        init = self.battle.init_player

        if self.battle.winner:
            self.phase = "resolve_done"
            if self.game_mode == "lan_host":
                self._lan_send_state(phase="resolve_done")
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
            if self.game_mode == "lan_host":
                self._lan_send_state(phase="resolve_done")
        else:
            if self._extra_action_queue:
                self._start_next_stitch_extra()
                return
            if not self.battle.winner:
                self.battle.log_add("─── End of Round ───")
                do_end_round(self.battle)
            self.phase = "resolve_done"
            if self.game_mode == "lan_host":
                self._lan_send_state(phase="resolve_done")

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
            player_level = self._player_level() if self.campaign_profile else 1
            _new_cat = bool(self.campaign_profile and self.campaign_profile.new_unlocks)
            self._last_menu_btns = draw_main_menu(
                surf,
                mouse_pos,
                self.campaign_profile,
                player_level=player_level,
                new_catalog_unlocks=_new_cat,
                quick_play_unlocked=bool(self.campaign_profile and self.campaign_profile.quick_play_unlocked),
                ranked_unlocked=self._ranked_unlocked() if self.campaign_profile else False,
                level_card_open=self._menu_level_card_open,
            )

        elif p == "estate_menu":
            self._last_estate_btns = draw_estate_menu(
                surf,
                mouse_pos,
                new_catalog_unlocks=bool(self.campaign_profile and self.campaign_profile.new_unlocks),
            )

        elif p == "training_menu":
            self._last_training_btns = draw_training_menu(surf, mouse_pos)

        elif p == "teambuilder":
            profile = self.campaign_profile or CampaignProfile()
            btns = draw_teambuilder(
                surf,
                profile.saved_teams,
                mouse_pos,
                profile,
                max_slots=self._saved_team_slot_count(),
            )
            self._last_teambuilder_btns = btns
            self._draw_screen_tooltips(surf, mouse_pos, artifact_hover=btns.get("artifact_hover", []))
            # Rename overlay drawn on top when active
            if self._renaming_team_slot is not None:
                overlay_btns = draw_rename_overlay(surf, mouse_pos, self._rename_text)
                self._last_rename_overlay_btns = overlay_btns

        elif p == "guild":
            profile = self.campaign_profile or CampaignProfile()
            guild_adventurers = [defn for defn in ROSTER if defn.id in self._current_guild_adventurer_ids()]
            guild_artifacts = [artifact for artifact in ARTIFACTS if artifact.id in self._current_guild_artifact_ids()]
            self._last_guild_btns = draw_guild_screen(
                surf,
                mouse_pos,
                profile,
                self._guild_tab,
                guild_adventurers,
                guild_artifacts,
                ADVENTURER_PRICES,
                ARTIFACT_PRICES,
            )
            self._draw_screen_tooltips(surf, mouse_pos, artifact_hover=self._last_guild_btns.get("artifact_hover", []))

        elif p == "embassy":
            profile = self.campaign_profile or CampaignProfile()
            self._last_embassy_btns = draw_embassy_screen(
                surf,
                mouse_pos,
                profile,
                EMBASSY_GOLD_PER_DOLLAR,
            )

        elif p == "market_closed":
            self._last_market_btns = draw_market_closed(surf, mouse_pos)

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
                items=ARTIFACTS,
                status_rects_out=_catalog_desc_hover,
                filters=self._catalog_filters.get(self._catalog_tab, {}),
            )
            self._last_catalog_btns = btns
            self._draw_screen_tooltips(
                surf,
                mouse_pos,
                status_hover=_catalog_desc_hover,
                artifact_hover=btns.get("artifact_hover", []),
            )

        elif p == "settings":
            btns = draw_settings_screen(surf, mouse_pos, self._confirm_reset,
                                        fast_resolution=self.campaign_profile.fast_resolution,
                                        tutorials_enabled=self.campaign_profile.tutorials_enabled)
            self._last_settings_btns = btns

        elif p == "story_team_select":
            quest = QUEST_TABLE.get(self.campaign_quest_id)
            profile = self.campaign_profile or CampaignProfile()
            btns = draw_story_team_select(
                surf,
                profile.saved_teams,
                mouse_pos,
                quest,
                max_slots=self._saved_team_slot_count(),
            )
            self._last_story_team_btns = btns
            self._draw_screen_tooltips(surf, mouse_pos, artifact_hover=btns.get("artifact_hover", []))

        elif p == "pre_battle_edit":
            _PRE_BATTLE_DETAIL_RECT = pygame.Rect(700, 80, 680, 760)
            # Use campaign-filtered roster/items when in campaign mode
            if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked") and hasattr(self, "_campaign_roster"):
                active_items      = self._campaign_artifacts
                active_cls_basics = self._campaign_basics
            else:
                active_items      = ARTIFACTS
                active_cls_basics = CLASS_BASICS

            _focus_defn = self._team_select_focus_defn()
            if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked") and self.campaign_profile and _focus_defn is not None:
                _sig_tier = unlocked_signature_count(self._adventurer_level(_focus_defn.id))
                _twists_unlocked = twist_unlocked(self._adventurer_level(_focus_defn.id))
            else:
                _sig_tier = 3
                _twists_unlocked = True
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
                twists_unlocked=_twists_unlocked,
                status_rects_out=_team_desc_hover,
                confirm_label=_confirm_lbl,
                pre_battle_mode=True,
                enemy_picks=self._pbe_enemy_picks,
                focused_slot=self._focused_slot,
                artifact_focus=self._team_artifact_focus,
                drag_info={
                    "active": self._team_drag_active,
                    "hover_slot": self._team_drag_hover_slot,
                    "hover_remove": self._team_drag_hover_remove,
                    "defn": self._team_drag_defn,
                },
                member_prompt_slot=self._team_member_prompt_slot,
                artifact_scroll=self.team_artifact_scroll,
            )
            self.team_select_scroll = min(self.team_select_scroll, clicks.get("roster_scroll_max", 0))
            self.team_artifact_scroll = min(self.team_artifact_scroll, clicks.get("artifact_scroll_max", 0))
            self._last_team_clicks = clicks
            self._draw_screen_tooltips(
                surf,
                mouse_pos,
                status_hover=_team_desc_hover,
                artifact_hover=clicks.get("artifact_hover", []),
            )
            if self._detail_unit is not None:
                _dh = []
                close_btn = draw_combatant_detail(surf, self._detail_unit,
                                                  rect=_PRE_BATTLE_DETAIL_RECT,
                                                  status_rects_out=_dh)
                self._detail_close_btn = close_btn
                self._draw_screen_tooltips(surf, mouse_pos, status_hover=_dh)
            else:
                self._detail_close_btn = None

        elif p == "team_select":
            # Use campaign-filtered roster/items when in campaign/teambuilder mode
            if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked") and hasattr(self, "_campaign_roster"):
                active_roster     = self._campaign_roster
                active_items      = self._campaign_artifacts
                active_cls_basics = self._campaign_basics
            else:
                active_roster     = ROSTER
                active_items      = ARTIFACTS
                active_cls_basics = CLASS_BASICS

            # roster_selected is a defn object (or None)
            sel_idx = self.roster_selected

            _focus_defn = self._team_select_focus_defn()
            if self.game_mode in ("campaign", "teambuilder", "single_player", "ranked") and self.campaign_profile and _focus_defn is not None:
                _sig_tier = unlocked_signature_count(self._adventurer_level(_focus_defn.id))
                _twists_unlocked = twist_unlocked(self._adventurer_level(_focus_defn.id))
            else:
                _sig_tier = 3
                _twists_unlocked = True
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
                twists_unlocked=_twists_unlocked,
                status_rects_out=_team_desc_hover,
                confirm_label=_confirm_label,
                focused_slot=self._focused_slot,
                artifact_focus=self._team_artifact_focus,
                drag_info={
                    "active": self._team_drag_active,
                    "hover_slot": self._team_drag_hover_slot,
                    "hover_remove": self._team_drag_hover_remove,
                    "defn": self._team_drag_defn,
                },
                member_prompt_slot=self._team_member_prompt_slot,
                artifact_scroll=self.team_artifact_scroll,
            )
            self.team_select_scroll = min(self.team_select_scroll, clicks.get("roster_scroll_max", 0))
            self.team_artifact_scroll = min(self.team_artifact_scroll, clicks.get("artifact_scroll_max", 0))
            self._last_team_clicks = clicks
            self._draw_screen_tooltips(
                surf,
                mouse_pos,
                status_hover=_team_desc_hover,
                artifact_hover=clicks.get("artifact_hover", []),
            )
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
            a, b = draw_result_screen(
                surf,
                self.battle,
                mouse_pos,
                subtitle=self._last_result_subtitle,
                detail_lines=self._last_result_details,
            )
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
                preview_map = {quest.quest_id: build_quest_reward_preview(profile, quest.quest_id) for quest in quests}
                btns = draw_quest_select(surf, mission, quests, mouse_pos, profile, reward_preview_map=preview_map)
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
                reward_preview = build_quest_reward_preview(self.campaign_profile or CampaignProfile(), self.campaign_quest_id)
                _pq_hover = []
                btns = draw_pre_quest(
                    surf,
                    quest,
                    mission,
                    quest_pos,
                    total_quests,
                    enemy_picks,
                    mouse_pos,
                    reward_preview_lines=reward_preview,
                    status_rects_out=_pq_hover,
                )
                self._last_campaign_btns = btns
                self._draw_screen_tooltips(
                    surf,
                    mouse_pos,
                    status_hover=_pq_hover,
                    artifact_hover=btns.get("artifact_hover", []),
                )
                if self._detail_unit is not None:
                    _dh = []
                    close_btn = draw_combatant_detail(surf, self._detail_unit, status_rects_out=_dh)
                    self._detail_close_btn = close_btn
                    self._draw_screen_tooltips(surf, mouse_pos, status_hover=_dh)
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
                    detail_lines=self._last_result_details,
                    subtitle=self._last_result_subtitle,
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
                self._draw_battle_scene(
                    surf,
                    mouse_pos,
                    strip_mode="view",
                    prompt="Waiting for opponent...",
                    subprompt="The arena will update when their state arrives.",
                )
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

    def _draw_screen_tooltips(self, surf, mouse_pos, *, status_hover=None, artifact_hover=None):
        for rect, artifact in artifact_hover or []:
            if rect.collidepoint(mouse_pos):
                draw_artifact_tooltip(surf, artifact, mouse_pos[0], mouse_pos[1])
                return
        for rect, kind in status_hover or []:
            if rect.collidepoint(mouse_pos):
                draw_status_tooltip(surf, kind, mouse_pos[0], mouse_pos[1])
                return

    def _draw_battle_overlays_and_tooltips(self, surf, mouse_pos, status_hover, artifact_hover=None):
        if self._detail_unit is not None:
            _dh = []
            close_btn = draw_combatant_detail(surf, self._detail_unit, status_rects_out=_dh)
            self._detail_close_btn = close_btn
            self._draw_screen_tooltips(surf, mouse_pos, status_hover=_dh)
        else:
            self._detail_close_btn = None

        overlay_btns = {}
        if self._battle_overlay == "log":
            overlay_btns = draw_battle_log_overlay(
                surf, self.battle.log, mouse_pos, scroll_offset=self.battle_log_scroll
            )
        elif self._battle_overlay == "artifacts":
            overlay_btns = draw_artifact_overlay(surf, self.battle, mouse_pos)
        self._last_battle_overlay_btns = overlay_btns

        overlay_artifact_hover = overlay_btns.get("artifact_hover", []) if isinstance(overlay_btns, dict) else []
        if self._battle_overlay == "artifacts":
            self._draw_screen_tooltips(surf, mouse_pos, artifact_hover=overlay_artifact_hover)
        elif self._battle_overlay is None:
            self._draw_screen_tooltips(surf, mouse_pos, status_hover=status_hover, artifact_hover=artifact_hover)

    def _draw_battle_scene(
        self,
        surf,
        mouse_pos,
        *,
        strip_mode: str,
        prompt: str = "",
        subprompt: str = "",
        selected_unit=None,
        valid_targets=None,
        queue_units=None,
        action_groups=None,
        show_review: bool = False,
        can_clear: bool = False,
        can_lock: bool = False,
        continue_label: str | None = None,
        continue_disabled: bool = False,
        waiting_label: str = "",
    ):
        surf.fill(BG)
        if not self.battle:
            return
        _status_hover = []
        draw_formation(
            surf,
            self.battle,
            selected_unit=selected_unit,
            valid_targets=valid_targets,
            mouse_pos=mouse_pos,
            acting_player=self.selecting_player if self.phase in ("select_actions",) or self.phase.startswith("extra_action_p") else None,
            status_rects_out=_status_hover,
        )
        self._last_battle_strip_btns = draw_battle_strip(
            surf,
            mouse_pos,
            self.battle,
            mode=strip_mode,
            prompt=prompt,
            subprompt=subprompt,
            action_groups=action_groups,
            queue_units=queue_units,
            current_actor=self.current_actor,
            current_is_extra=self.current_is_extra,
            show_review=show_review,
            can_clear=can_clear,
            can_lock=can_lock,
            continue_label=continue_label,
            continue_disabled=continue_disabled,
            waiting_label=waiting_label,
        )
        self._last_action_buttons = self._last_battle_strip_btns.get("actions", [])
        self._draw_battle_overlays_and_tooltips(
            surf,
            mouse_pos,
            _status_hover,
            self._last_battle_strip_btns.get("artifact_hover", []),
        )

    def _draw_battle(self, surf, mouse_pos):
        info = self._tk_msg or f"Round {self.battle.round_num} — P{self.battle.init_player} has initiative."
        self._draw_battle_scene(
            surf,
            mouse_pos,
            strip_mode="resolve" if self._tk_msg else "view",
            prompt=info,
            subprompt="Watch the arena. Use the strip to open the log or artifact view.",
            continue_label=self._tk_btn_label if self._tk_btn_label and self._tk_btn_label != "__tutorial__" else None,
        )

        if self._tk_btn_label and self._tk_btn_label != "__tutorial__":
            self._tk_btn_rect = self._last_battle_strip_btns.get("continue")
        else:
            self._tk_btn_rect = None

        if self._tk_overlay_msg:
            raw_lines = self._tk_overlay_msg.split("\n")
            box_w = 960
            text_max_w = box_w - 48
            display_lines = []
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
            by = ARENA_RECT.centery - box_h // 2
            overlay_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
            overlay_surf.fill((10, 10, 30, 210))
            surf.blit(overlay_surf, (bx, by))
            pygame.draw.rect(surf, (100, 140, 220), (bx, by, box_w, box_h), 2, border_radius=6)
            text_y = by + 18
            for text, size, col in display_lines:
                draw_text(surf, text, size, col, WIDTH // 2, text_y, center=True)
                text_y += line_h

    def _draw_extra_swap(self, surf, mouse_pos):
        player = self._extra_swap_player
        if self._is_lan() and self._extra_swap_player != self._lan_my_player():
            self._draw_battle_scene(
                surf,
                mouse_pos,
                strip_mode="view",
                prompt="Waiting for opponent's formation swap.",
                subprompt="The arena will update when they finish.",
            )
            return

        subprompt = "Click two allies to swap them."
        if hasattr(self, '_extra_swap_pending') and self._extra_swap_pending:
            subprompt = f"Selected {self._extra_swap_pending.name}. Click a second ally to finish."
        self._draw_battle_scene(
            surf,
            mouse_pos,
            strip_mode="resolve",
            prompt="Round 1 extra swap",
            subprompt=subprompt,
            continue_label="Skip Swap",
        )
        self._extra_swap_skip_btn = self._last_battle_strip_btns.get("continue")

    def _draw_select_actions(self, surf, mouse_pos):
        if not self.battle:
            return

        if self._is_lan() and self.selecting_player != self._lan_my_player():
            self._draw_battle_scene(
                surf,
                mouse_pos,
                strip_mode="view",
                prompt="Opponent is choosing actions",
                subprompt="Their queue will resolve after they lock in.",
            )
            return

        team = self.battle.get_team(self.selecting_player)
        actor = self.current_actor
        is_last = bool(actor and len(team.alive()) == 1 and team.alive()[0] == actor)
        action_groups = []
        if actor is not None and self.selection_sub == "pick_action":
            action_groups = self._build_action_groups(actor, team, is_last)
        prompt, subprompt = self._selection_prompt()
        self._draw_battle_scene(
            surf,
            mouse_pos,
            strip_mode="queue",
            prompt=prompt,
            subprompt=subprompt,
            selected_unit=actor,
            valid_targets=self._current_valid_targets(),
            queue_units=self._queue_units_for_strip(),
            action_groups=action_groups,
            show_review=bool(self.selection_sub == "review_queue"),
            can_clear=bool(self.phase == "select_actions"),
            can_lock=bool(self.phase == "select_actions" and self.selection_sub == "review_queue"),
        )
        self._last_clear_btn = self._last_battle_strip_btns.get("clear")

    def _draw_actions_resolving(self, surf, mouse_pos):
        if not self.battle:
            return
        rp = self._resolving_player
        self._draw_battle_scene(
            surf,
            mouse_pos,
            strip_mode="resolve",
            prompt=f"P{rp} locked in.",
            subprompt="Resolve the queued actions when ready.",
            continue_label="Resolve Actions →",
        )
        self._last_actions_resolving_btn = self._last_battle_strip_btns.get("continue")

    def _draw_battle_start(self, surf, mouse_pos):
        if not self.battle:
            return
        init = self.battle.init_player
        reason = getattr(self.battle, "init_reason", "")
        esp = self.battle.r1_extra_swap_player
        if self.game_mode == "lan_client":
            continue_label = None
            subprompt = "Waiting for host..."
        else:
            continue_label = "Begin Round 1 →"
            subprompt = reason
        if esp:
            subprompt = (subprompt + "  " if subprompt else "") + f"P{esp} gets a free swap first."
        self._draw_battle_scene(
            surf,
            mouse_pos,
            strip_mode="resolve",
            prompt=f"Round 1 — P{init} has initiative!",
            subprompt=subprompt,
            continue_label=continue_label,
        )
        self._last_battle_start_btn = self._last_battle_strip_btns.get("continue")

    def _draw_end_of_round(self, surf, mouse_pos):
        if not self.battle:
            return
        next_rnd = self.battle.round_num
        init = self.battle.init_player
        reason = getattr(self.battle, "init_reason", "")
        esp = self.battle.r1_extra_swap_player
        if self.game_mode == "lan_client":
            continue_label = None
            subprompt = "Waiting for host..."
        else:
            continue_label = f"Begin Round {next_rnd} →"
            subprompt = reason
        if esp:
            subprompt = (subprompt + "  " if subprompt else "") + f"P{esp} gets a free swap first."
        self._draw_battle_scene(
            surf,
            mouse_pos,
            strip_mode="resolve",
            prompt=f"Round {next_rnd} — P{init} has initiative!",
            subprompt=subprompt,
            continue_label=continue_label,
        )
        self._last_eor_btn = self._last_battle_strip_btns.get("continue")

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
        if not self.battle:
            return
        rp = self._resolving_player
        init_done = self._init_player_resolved
        if self.phase == "action_result":
            actor = self._action_step_unit
            actor_name = actor.name if actor else "?"
            new_entries = self.battle.log[self._action_log_start:]
            if new_entries:
                msg = new_entries[0][:60]  # show the primary action result (first new line)
            else:
                msg = f"{actor_name} acted."
            continue_label = None if self.game_mode == "lan_client" else "Next Action →"
            subprompt = "Waiting for host to continue..." if self.game_mode == "lan_client" else "Review the result, then continue."
            self._draw_battle_scene(
                surf,
                mouse_pos,
                strip_mode="resolve",
                prompt=msg,
                subprompt=subprompt,
                continue_label=continue_label,
            )
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
            continue_label = None if self.game_mode == "lan_client" else btn_label
            subprompt = "Waiting for host to continue..." if self.game_mode == "lan_client" else "Use the log or artifacts view while you review."
            self._draw_battle_scene(
                surf,
                mouse_pos,
                strip_mode="resolve",
                prompt=msg,
                subprompt=subprompt,
                continue_label=continue_label,
            )
        else:
            self._draw_battle_scene(
                surf,
                mouse_pos,
                strip_mode="resolve",
                prompt=f"P{rp} is resolving actions." if rp else "Resolution",
                subprompt="Battle text only appears here while effects resolve.",
            )
        self._last_resolve_btn = self._last_battle_strip_btns.get("continue")


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
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return
        overlay_btns = self._last_battle_overlay_btns or {}
        if overlay_btns.get("close") and overlay_btns["close"].collidepoint(pos):
            self._battle_overlay = None
            return
        if self._battle_overlay:
            return
        if pos[1] >= BATTLE_STRIP_RECT.y and self._handle_battle_strip_click(pos):
            return
        if ARENA_RECT.collidepoint(pos):
            unit = self._unit_at_pos(pos)
            if unit:
                self._detail_unit = None if self._detail_unit is unit else unit
        return
    if self.phase == "actions_resolving":
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return
        overlay_btns = self._last_battle_overlay_btns or {}
        if overlay_btns.get("close") and overlay_btns["close"].collidepoint(pos):
            self._battle_overlay = None
            return
        if self._battle_overlay:
            return
        if pos[1] >= BATTLE_STRIP_RECT.y:
            self._handle_battle_strip_click(pos)
            return
        if ARENA_RECT.collidepoint(pos):
            unit = self._unit_at_pos(pos)
            if unit:
                self._detail_unit = None if self._detail_unit is unit else unit
        return
    if self.phase == "battle_start":
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return
        overlay_btns = self._last_battle_overlay_btns or {}
        if overlay_btns.get("close") and overlay_btns["close"].collidepoint(pos):
            self._battle_overlay = None
            return
        if self._battle_overlay:
            return
        if pos[1] >= BATTLE_STRIP_RECT.y:
            self._handle_battle_strip_click(pos)
            return
        if ARENA_RECT.collidepoint(pos):
            unit = self._unit_at_pos(pos)
            if unit:
                self._detail_unit = None if self._detail_unit is unit else unit
        return
    if self.phase == "end_of_round":
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return
        overlay_btns = self._last_battle_overlay_btns or {}
        if overlay_btns.get("close") and overlay_btns["close"].collidepoint(pos):
            self._battle_overlay = None
            return
        if self._battle_overlay:
            return
        if pos[1] >= BATTLE_STRIP_RECT.y:
            self._handle_battle_strip_click(pos)
            return
        if ARENA_RECT.collidepoint(pos):
            unit = self._unit_at_pos(pos)
            if unit:
                self._detail_unit = None if self._detail_unit is unit else unit
        return
    if self.phase.startswith("extra_swap_p"):
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return
        overlay_btns = self._last_battle_overlay_btns or {}
        if overlay_btns.get("close") and overlay_btns["close"].collidepoint(pos):
            self._battle_overlay = None
            return
        if self._battle_overlay:
            return
        if pos[1] >= BATTLE_STRIP_RECT.y:
            btn = getattr(self, "_extra_swap_skip_btn", None)
            if btn and btn.collidepoint(pos):
                self._handle_extra_swap_click(pos)
                return
            if self._handle_battle_strip_click(pos):
                return
        self._handle_extra_swap_click(pos)
        return
    if self.phase.startswith("extra_action_p"):
        self._handle_action_select_click(pos)
        return
    if self.phase in ("resolving", "resolve_done", "action_result"):
        if self._detail_close_btn and self._detail_close_btn.collidepoint(pos):
            self._detail_unit = None
            return
        overlay_btns = self._last_battle_overlay_btns or {}
        if overlay_btns.get("close") and overlay_btns["close"].collidepoint(pos):
            self._battle_overlay = None
            return
        if self._battle_overlay:
            return
        if pos[1] >= BATTLE_STRIP_RECT.y:
            self._handle_battle_strip_click(pos)
            return
        if ARENA_RECT.collidepoint(pos):
            unit = self._unit_at_pos(pos)
            if unit:
                self._detail_unit = None if self._detail_unit is unit else unit
        return
    _orig_handle_click(self, pos)

Game.handle_click = _patched_handle_click


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    g = Game()
    # Init last-used button caches to avoid AttributeError on first frame
    _dummy = pygame.Rect(0,0,1,1)
    g._last_menu_btns   = {
        "camelot_btn": _dummy,
        "fantasia_btn": _dummy,
        "brightheart_btn": _dummy,
        "estate_btn": _dummy,
        "level_btn": _dummy,
        "gold_btn": _dummy,
        "level_card_rect": _dummy,
        "level_card_close": _dummy,
        "guild_btn": _dummy,
        "market_btn": _dummy,
        "embassy_btn": _dummy,
        "settings_btn": _dummy,
        "exit_btn": _dummy,
    }
    g._last_pass_btn    = None
    g._last_team_clicks = {}
    g._last_action_buttons = []
    g._last_result_btns = (pygame.Rect(0,0,1,1), pygame.Rect(0,0,1,1))
    g._last_campaign_btns = {}
    g._last_practice_btns = {}
    g._last_estate_btns = {}
    g._last_training_btns = {}
    g._last_teambuilder_btns = {}
    g._last_story_team_btns = {}
    g._campaign_roster    = list(ROSTER)
    g._campaign_artifacts = list(ARTIFACTS)
    g._campaign_basics    = dict(CLASS_BASICS)
    g._campaign_enemy_picks = []
    g._extra_swap_player   = 1
    g._extra_swap_pending  = None
    g._extra_swap_skip_btn = pygame.Rect(0,0,1,1)
    g._last_resolve_btn    = pygame.Rect(0,0,1,1)
    g._last_actions_resolving_btn = pygame.Rect(0,0,1,1)
    g._last_clear_btn      = None
    g._detail_close_btn    = None
    g._last_battle_strip_btns = {}
    g._last_battle_overlay_btns = {}
    g._resolving_player    = None
    g._init_player_resolved = False
    g._tk_btn_rect         = None
    g.run()


if __name__ == "__main__":
    main()
