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
    describe_action,
    apply_quest_rewards,
    apply_round_start_effects,
    make_combatant,
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
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
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
            apply_quest_rewards(self.campaign_profile, 0)
            save_campaign(self.campaign_profile)
        self.campaign_quest_id: int = 0
        self.campaign_mission_id: int = 1
        self._last_campaign_btns = None
        self._campaign_won_quest = False

        # New teambuilder / story-team state
        self._editing_team_slot: int = None
        self._story_team_idx: int = None
        self._last_practice_btns = None
        self._last_teambuilder_btns = None
        self._last_story_team_btns = None
        self._teambuilder_return_phase = "menu"  # where back_btn in teambuilder leads

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

        # Per-player resolution tracking
        self._resolving_player = None       # which player's turn is being resolved
        self._init_player_resolved = False  # True after init player resolves, before second selects

        # Detail panel
        self._detail_unit = None            # unit whose card is currently shown
        self._detail_close_btn = None       # close button rect for the detail panel

        # Curated AI draft pool (meta-style lineups)
        self._ai_team_pool = [
            {
                "name": "Tempo Lockdown",
                "members": [
                    {"defn": "march_hare", "sig": "rabbit_hole", "basics": ["fire_blast", "arcane_wave"], "item": "ancient_hourglass"},
                    {"defn": "witch_of_the_woods", "sig": "crawling_abode", "basics": ["fire_blast", "breakthrough"], "item": "hunters_net"},
                    {"defn": "briar_rose", "sig": "garden_of_thorns", "basics": ["hawkshot", "trapping_blow"], "item": "smoke_bomb"},
                ],
            },
            {
                "name": "Guarded Attrition",
                "members": [
                    {"defn": "sir_roland", "sig": "knights_challenge", "basics": ["shield_bash", "stalwart"], "item": "iron_buckler"},
                    {"defn": "aldric_lost_lamb", "sig": "sanctuary", "basics": ["bless", "protection"], "item": "holy_diadem"},
                    {"defn": "porcus_iii", "sig": "porcine_honor", "basics": ["slam", "stalwart"], "item": "spiked_mail"},
                ],
            },
            {
                "name": "Burst Hunters",
                "members": [
                    {"defn": "frederic", "sig": "on_the_hunt", "basics": ["hawkshot", "hunters_badge"], "item": "vampire_fang"},
                    {"defn": "risa_redcloak", "sig": "blood_hunt", "basics": ["strike", "feint"], "item": "hunters_net"},
                    {"defn": "robin_hooded_avenger", "sig": "bring_down", "basics": ["volley", "trapping_blow"], "item": "main_gauche"},
                ],
            },
            {
                "name": "Debuff & Control",
                "members": [
                    {"defn": "hunold_the_piper", "sig": "hypnotic_aura", "basics": ["sneak_attack", "fleetfooted"], "item": "ancient_hourglass"},
                    {"defn": "gretel", "sig": "hot_mitts", "basics": ["strike", "intimidate"], "item": "hunters_net"},
                    {"defn": "ashen_ella", "sig": "midnight_dour", "basics": ["fire_blast", "breakthrough"], "item": "holy_diadem"},
                ],
            },
            {
                "name": "Swap Tricks",
                "members": [
                    {"defn": "lucky_constantine", "sig": "subterfuge", "basics": ["sneak_attack", "sucker_punch"], "item": "smoke_bomb"},
                    {"defn": "reynard", "sig": "cutpurse", "basics": ["riposte", "fleetfooted"], "item": "main_gauche"},
                    {"defn": "lady_of_reflections", "sig": "postmortem_passage", "basics": ["shield_bash", "armored"], "item": "iron_buckler"},
                ],
            },
            {
                "name": "Burn & Sustain",
                "members": [
                    {"defn": "little_jack", "sig": "magic_growth", "basics": ["strike", "cleave"], "item": "vampire_fang"},
                    {"defn": "matchstick_liesl", "sig": "cinder_blessing", "basics": ["heal", "bless"], "item": "health_potion"},
                    {"defn": "snowkissed_aurora", "sig": "birdsong", "basics": ["smite", "medic"], "item": "holy_diadem"},
                ],
            },
        ]

    def _is_single_player(self):
        return self.game_mode in ("single_player", "campaign")

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
        player_num = self.selecting_player
        team = self.battle.get_team(player_num)
        enemy = self.battle.get_enemy(player_num)

        def _target_score(target):
            score = (target.max_hp - target.hp) * 0.5
            score += target.get_stat("attack") * 0.3
            if target.hp <= max(35, target.max_hp * 0.3):
                score += 25
            if target.slot == SLOT_FRONT:
                score += 5
            return score

        best_action = {"type": "skip"}
        best_score = -9999.0

        abilities = actor.basics + [actor.sig]
        if len(team.alive()) == 1 and team.alive()[0] == actor:
            abilities.append(actor.defn.twist)

        for ability in abilities:
            if not can_use_ability(actor, ability, team):
                continue
            mode = ability.frontline if actor.slot == SLOT_FRONT else ability.backline
            targets = get_legal_targets(self.battle, player_num, actor, ability)
            if mode.spread:
                if not enemy.alive():
                    continue
                score = sum(_target_score(e) for e in enemy.alive()) * 0.35
                score += mode.power * 0.4
                if score > best_score:
                    best_score = score
                    best_action = {"type": "ability", "ability": ability, "target": None}
                continue
            for target in targets:
                score = 0.0
                if target in enemy.alive():
                    score += mode.power * 0.8
                    score += _target_score(target)
                    if target.hp <= max(35, target.max_hp * 0.35):
                        score += 20
                    if mode.status or mode.status2 or mode.status3:
                        score += 10
                    if mode.atk_debuff or mode.spd_debuff or mode.def_debuff:
                        score += 7
                else:
                    missing = target.max_hp - target.hp
                    score += min(missing, mode.heal + mode.heal_lowest + mode.heal_self) * 0.9
                    if target.hp < target.max_hp * 0.5:
                        score += 20
                    if mode.guard_target or mode.guard_all_allies or mode.guard_frontline_ally:
                        score += 10
                    if target is actor and (mode.atk_buff or mode.spd_buff or mode.def_buff):
                        score += 7

                action = {"type": "ability", "ability": ability, "target": target}
                if ability.id == "subterfuge":
                    swap_targets = get_subterfuge_swap_targets(self.battle, player_num, target)
                    if not swap_targets:
                        continue
                    swap_target = max(swap_targets, key=_target_score)
                    action["swap_target"] = swap_target
                    score += 8

                if score > best_score:
                    best_score = score
                    best_action = action

        if not self.current_is_extra and not self.battle.swap_used_this_turn and not self._swap_queued_this_turn() and not actor.has_status("root"):
            allies = [u for u in team.alive() if u != actor]
            if allies:
                weakest = min(team.alive(), key=lambda u: u.get_stat("defense") + u.hp)
                if weakest is actor and actor.slot == SLOT_FRONT:
                    swap_target = max(allies, key=lambda u: u.get_stat("defense") + u.hp)
                    swap_score = 24.0
                    if swap_score > best_score:
                        best_action = {"type": "swap", "target": swap_target}

        item_targets = get_legal_item_targets(self.battle, player_num, actor)
        if item_targets:
            it = actor.item
            for target in item_targets:
                score = -5.0
                if it.heal > 0:
                    score += min(target.max_hp - target.hp, it.heal) * 0.8
                if it.guard:
                    score += 14
                if it.status:
                    score += _target_score(target) * 0.4 + 8
                if target.hp < target.max_hp * 0.4:
                    score += 10
                if score > best_score:
                    best_score = score
                    best_action = {"type": "item", "target": target}

        self._set_queued(actor, best_action)
        return True

    def _auto_continue_resolve_done(self):
        self._detail_unit = None
        if self.battle.winner:
            if self.game_mode == "campaign":
                self._campaign_won_quest = (self.battle.winner == 1)
                self.phase = "campaign_post_quest"
            else:
                self.phase = "result"
        elif self._init_player_resolved:
            second = 3 - self.battle.init_player
            self._enter_action_selection(second)
        else:
            apply_passive_stats(self.battle.team1, self.battle)
            apply_passive_stats(self.battle.team2, self.battle)
            determine_initiative(self.battle)
            self._enter_round_start()

    def _maybe_auto_progress(self):
        if not self._is_single_player() or (not self.battle and self.phase != "menu"):
            return

        progressed = True
        safety = 0
        while progressed and safety < 10:
            safety += 1
            progressed = False
            p = self.phase

            if p.startswith("pass_to_select_p") and self._is_ai_player(int(p[-1])):
                self._advance_from_pass(); progressed = True; continue
            if p.startswith("pass_to_extra_swap_p") and self._is_ai_player(int(p[-1])):
                self._advance_from_pass(); progressed = True; continue
            if p.startswith("pass_to_extra_action_p") and self._is_ai_player(int(p[-1])):
                self._advance_from_pass(); progressed = True; continue
            if p == "pass_to_resolve" and self._is_ai_player(self._resolving_player or 0):
                self._advance_from_pass(); progressed = True; continue

            if p.startswith("extra_swap_p") and self._is_ai_player(self._extra_swap_player):
                self._ai_pick_extra_swap(self._extra_swap_player)
                self._enter_action_selection(self.battle.init_player)
                progressed = True
                continue

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

            if p.startswith("extra_action_p") and self._is_ai_player(self.selecting_player):
                if self.current_actor and self.current_actor.queued2 is None:
                    if not self._ai_queue_current_actor_action():
                        self._set_queued(self.current_actor, {"type": "skip"})
                self._on_action_queued()
                progressed = True
                continue

            if p == "resolve_done":
                if self._init_player_resolved:
                    second = 3 - (self._resolving_player or self.battle.init_player)
                    if self._is_ai_player(second):
                        self._auto_continue_resolve_done()
                        progressed = True
                else:
                    self._auto_continue_resolve_done()
                    progressed = True

    # ─────────────────────────────────────────────────────────────────────────
    def run(self):
        while True:
            mouse_pos = pygame.mouse.get_pos()
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

            self._maybe_auto_progress()

            self.draw(mouse_pos)
            pygame.display.flip()
            self.clock.tick(FPS)

    # ─────────────────────────────────────────────────────────────────────────
    # CLICK HANDLER
    # ─────────────────────────────────────────────────────────────────────────

    def handle_click(self, pos):
        p = self.phase

        if p == "menu":
            story_btn, practice_btn, teambuilder_btn, exit_btn = self._last_menu_btns
            if story_btn.collidepoint(pos):
                self.phase = "campaign_mission_select"
            elif practice_btn.collidepoint(pos):
                self.phase = "practice_menu"
            elif teambuilder_btn.collidepoint(pos):
                self._teambuilder_return_phase = "menu"
                self.phase = "teambuilder"
            elif exit_btn.collidepoint(pos):
                pygame.quit(); sys.exit()

        elif p == "practice_menu":
            btns = self._last_practice_btns or {}
            if btns.get("vs_ai_btn") and btns["vs_ai_btn"].collidepoint(pos):
                self.game_mode = "single_player"
                if hasattr(self, "_campaign_roster"):
                    del self._campaign_roster
                self._start_team_select(1)
            elif btns.get("vs_pvp_btn") and btns["vs_pvp_btn"].collidepoint(pos):
                self.game_mode = "pvp"
                if hasattr(self, "_campaign_roster"):
                    del self._campaign_roster
                self._start_team_select(1)
            elif btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = "menu"

        elif p == "teambuilder":
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
            if btns.get("back_btn") and btns["back_btn"].collidepoint(pos):
                self.phase = self._teambuilder_return_phase

        elif p == "team_select":
            self._handle_team_select_click(pos)

        elif p.startswith("pass_"):
            if self._last_pass_btn and self._last_pass_btn.collidepoint(pos):
                self._advance_from_pass()

        elif p == "select_actions":
            self._handle_action_select_click(pos)

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
        if e.key != pygame.K_ESCAPE:
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
            p in ("select_actions", "resolving", "resolve_done", "end_round", "result")
            or p.startswith(("pass_to_", "extra_swap_p", "extra_action_p"))
        )

    def _handle_mousewheel(self, e):
        # Battle log scroll: works anywhere on screen during battle
        if self._is_in_battle():
            self.battle_log_scroll = max(0, self.battle_log_scroll + e.y * 3)
            return
        if self.phase != "team_select":
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
        self.phase = "team_select"

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

        if self.sub_phase == "pick_adventurers":
            # Party slot click: select for reordering, or swap with already-selected slot
            for rect, idx in clicks.get("party_slots", []):
                if rect.collidepoint(pos):
                    if self.team_slot_selected is None:
                        self.team_slot_selected = idx
                    elif self.team_slot_selected == idx:
                        self.team_slot_selected = None
                    else:
                        i, j = self.team_slot_selected, idx
                        self.team_picks[i], self.team_picks[j] = \
                            self.team_picks[j], self.team_picks[i]
                        self.team_slot_selected = None
                    return
            for rect, idx in clicks.get("roster", []):
                if rect.collidepoint(pos):
                    defn = active_roster[idx]
                    self.team_slot_selected = None
                    # Toggle: if already in team, remove it
                    existing = [i for i, p in enumerate(self.team_picks)
                                if p.get("definition") == defn]
                    if existing:
                        self.team_picks.pop(existing[0])
                    elif len(self.team_picks) < 3:
                        self.team_picks.append({"definition": defn})
                    self.roster_selected = idx
                    return
            confirm = clicks.get("confirm")
            if confirm and confirm.collidepoint(pos) and len(self.team_picks) == 3:
                self.team_slot_selected = None
                self.current_adv_idx = 0
                self.sub_phase = "pick_sig"
                self.sig_choice = None

        elif self.sub_phase == "pick_sig":
            back = clicks.get("back")
            if back and back.collidepoint(pos):
                if self.current_adv_idx > 0:
                    # Go back to item pick for previous adventurer
                    self.current_adv_idx -= 1
                    self.team_picks[self.current_adv_idx].pop("item", None)
                    self.item_choice = None
                    self.sub_phase = "pick_item"
                else:
                    # Go back to adventurer selection
                    self.sub_phase = "pick_adventurers"
                self.team_select_scroll = 0
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
                self.sub_phase = "pick_basics"
                self.basic_choices = []
                self.team_select_scroll = 0

        elif self.sub_phase == "pick_basics":
            back = clicks.get("back")
            if back and back.collidepoint(pos):
                self.team_picks[self.current_adv_idx].pop("signature", None)
                self.sig_choice = None
                self.sub_phase = "pick_sig"
                self.team_select_scroll = 0
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
                self.team_picks[self.current_adv_idx].pop("basics", None)
                self.basic_choices = []
                self.sub_phase = "pick_basics"
                self.team_select_scroll = 0
                return
            for rect, idx in clicks.get("items", []):
                if rect.collidepoint(pos):
                    # Reject items already used by other team members
                    taken_ids = {p["item"].id for i, p in enumerate(self.team_picks)
                                 if "item" in p and i < self.current_adv_idx}
                    if active_items[idx].id in taken_ids:
                        return  # item already taken by another team member
                    self.item_choice = idx
                    return
            confirm = clicks.get("confirm")
            if confirm and confirm.collidepoint(pos) and self.item_choice is not None:
                self.team_picks[self.current_adv_idx]["item"] = \
                    active_items[self.item_choice]
                self.current_adv_idx += 1
                if self.current_adv_idx < 3:
                    self.sub_phase = "pick_sig"
                    self.sig_choice = None
                    self.team_select_scroll = 0
                else:
                    # Done with this player
                    self._finish_team_select()

    def _finish_team_select(self):
        if self.game_mode == "teambuilder":
            self._save_built_team_to_slot()
            self.phase = "teambuilder"
            return

        if self.building_player == 1:
            self.p1_picks = list(self.team_picks)
            if self.game_mode == "single_player":
                self.ai_comp_name, self.p2_picks = self._generate_ai_team()
                self._start_battle()
            else:
                # pvp — pass to player 2
                self.phase = "pass_to_team_p2"
        else:
            self.p2_picks = list(self.team_picks)
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
        self._start_team_select(1)

    def _save_built_team_to_slot(self):
        """Serialize completed team_picks and save to campaign profile."""
        slot = self._editing_team_slot
        if slot is None or len(self.team_picks) < 3:
            return
        members = []
        for p in self.team_picks:
            members.append({
                "adv_id":  p["definition"].id,
                "sig_id":  p["signature"].id,
                "basics":  [b.id for b in p["basics"]],
                "item_id": p["item"].id,
            })
        team_name = f"Team {slot + 1}"
        entry = {"name": team_name, "members": members}
        while len(self.campaign_profile.saved_teams) <= slot:
            self.campaign_profile.saved_teams.append(None)
        self.campaign_profile.saved_teams[slot] = entry
        save_campaign(self.campaign_profile)
        self._editing_team_slot = None

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
            item = items_by_id.get(m.get("item_id"))
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
        self.p1_picks = picks
        self.p2_picks = build_quest_enemy_team(self.campaign_quest_id)
        self.game_mode = "campaign"
        self.ai_player = 2
        self._start_battle()

    # ─────────────────────────────────────────────────────────────────────────
    # BATTLE SETUP
    # ─────────────────────────────────────────────────────────────────────────

    def _start_battle(self):
        p1_name = "Player 1"
        if self.game_mode == "campaign":
            quest = QUEST_TABLE.get(self.campaign_quest_id)
            p2_name = f"Quest {self.campaign_quest_id} Enemies" if quest else "Enemy"
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
        determine_initiative(self.battle)
        self.battle.log_add("Battle begins!")
        self._enter_round_start()

    def _enter_round_start(self):
        """Begin a new round: check for extra swap phase or go straight to action selection."""
        # Apply start-of-round effects (e.g. Briar Rose Curse of Sleeping)
        apply_round_start_effects(self.battle)
        # Check if round 1 extra swap applies
        if self.battle.r1_extra_swap_player is not None:
            esp = self.battle.r1_extra_swap_player
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
        self.phase = f"pass_to_select_p{player_num}"

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
            self.phase = "resolving"
            self._do_single_resolution(self._resolving_player)

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
                        # Move to first player's action selection
                        self._enter_action_selection(self.battle.init_player)
                    else:
                        self._extra_swap_pending = None
                return

        # Done button (skip swap)
        if hasattr(self, '_extra_swap_skip_btn') and \
                self._extra_swap_skip_btn.collidepoint(pos):
            self._enter_action_selection(self.battle.init_player)

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
        # All units have actions queued → done with this player
        self._finish_selection()

    def _on_action_queued(self):
        """Called after an action has been stored. Routes to resolve or next slot."""
        if self.phase.startswith("extra_action_p"):
            self._resolve_stitch_extra_and_continue()
        else:
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
            self.battle.log_add(f"[Queued Extra] {actor.name}: {describe_action(action_dict)}")
        else:
            if actor.queued is not None:
                return  # already has an action queued; ignore duplicate
            actor.queued = action_dict
            self.battle.log_add(f"[Queued] {actor.name}: {describe_action(action_dict)}")

    def _finish_selection(self):
        """Selection done: route to this player's resolution phase."""
        # In the new flow, each player selects then immediately resolves.
        # init player → resolve init → (review) → second player selects → resolve second → end round
        self._resolving_player = self.selecting_player
        self.phase = "pass_to_resolve"

    def _unit_at_pos(self, pos):
        """Return the CombatantState whose formation box contains pos, or None."""
        for team, rects in ((self.battle.team1, SLOT_RECTS_P1),
                             (self.battle.team2, SLOT_RECTS_P2)):
            for slot, rect in rects.items():
                if rect.collidepoint(pos):
                    return next((m for m in team.members if m.slot == slot), None)
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
        """Resolve one player's queued actions, then route to the next phase.

        Flow:
          init player resolves → show resolve_done (review) → Continue → second selects
          second player resolves → end_round → show resolve_done → Continue → round_start
        """
        init   = self.battle.init_player
        second = 3 - init

        self.battle.log_add(f"─── P{player_num} Actions ───")
        resolve_player_turn(self.battle, player_num)

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
            # Show resolve_done so players can review before second player selects
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
        self.phase = f"pass_to_extra_action_p{pnum}"

    def _resolve_stitch_extra_and_continue(self):
        """Resolve the queued2 extra action for the current Stitch In Time unit."""
        unit = self.current_actor
        pnum = self.selecting_player
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
        self._start_next_stitch_extra()

    def _do_end_round(self):
        pass  # Already handled inline in _do_full_resolution

    # ─────────────────────────────────────────────────────────────────────────
    # DRAW
    # ─────────────────────────────────────────────────────────────────────────

    def draw(self, mouse_pos):
        surf = self.screen
        p = self.phase

        if p == "menu":
            player_level = max(0, self.campaign_profile.highest_quest_cleared) if self.campaign_profile else 0
            s, pr, tb, e = draw_main_menu(surf, mouse_pos, player_level)
            self._last_menu_btns = (s, pr, tb, e)

        elif p == "practice_menu":
            btns = draw_practice_menu(surf, mouse_pos)
            self._last_practice_btns = btns

        elif p == "teambuilder":
            profile = self.campaign_profile or CampaignProfile()
            btns = draw_teambuilder(surf, profile.saved_teams, mouse_pos, profile)
            self._last_teambuilder_btns = btns

        elif p == "story_team_select":
            quest = QUEST_TABLE.get(self.campaign_quest_id)
            profile = self.campaign_profile or CampaignProfile()
            btns = draw_story_team_select(surf, profile.saved_teams, mouse_pos, quest)
            self._last_story_team_btns = btns

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

            # Compute selected_idx in the active roster
            sel_idx = None
            if self.roster_selected is not None:
                # roster_selected was stored as index into active_roster at click time
                if 0 <= self.roster_selected < len(active_roster):
                    sel_idx = self.roster_selected

            _sig_tier = (
                self.campaign_profile.sig_tier
                if self.game_mode in ("campaign", "teambuilder") and self.campaign_profile
                else 3
            )
            clicks = draw_team_select_screen(
                surf,
                player_name=f"Player {self.building_player}",
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
            )
            self.team_select_scroll = min(
                self.team_select_scroll,
                clicks.get("scroll_max", 0),
            )
            self._last_team_clicks = clicks

        elif p.startswith("pass_"):
            msg, next_who = self._pass_screen_info(p)
            btn = draw_pass_screen(surf, next_who, msg, mouse_pos)
            self._last_pass_btn = btn

        elif p.startswith("extra_swap_p"):
            self._draw_extra_swap(surf, mouse_pos)

        elif p == "select_actions" or p.startswith("extra_action_p"):
            self._draw_select_actions(surf, mouse_pos)

        elif p in ("resolving", "resolve_done"):
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
                btns = draw_pre_quest(surf, quest, mission, quest_pos, total_quests, enemy_picks, mouse_pos)
                self._last_campaign_btns = btns
                if self._detail_unit is not None:
                    close_btn = draw_combatant_detail(surf, self._detail_unit)
                    self._detail_close_btn = close_btn
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

        else:
            surf.fill(BG)
            draw_text(surf, f"Phase: {p}", 24, TEXT, 20, 20)

    def _pass_screen_info(self, phase_key):
        """Return (message, next_player_name) for the pass screen."""
        rnd = self.battle.round_num if self.battle else 1
        init = self.battle.init_player if self.battle else 1

        if phase_key == "pass_to_team_p2":
            return "Player 1 has set their team.", "Player 2"
        if phase_key == "pass_to_extra_swap_p1":
            return "P1 lost initiative — free swap before round starts.", "Player 1"
        if phase_key == "pass_to_extra_swap_p2":
            return "P2 lost initiative — free swap before round starts.", "Player 2"
        if phase_key == "pass_to_select_p1":
            if self._init_player_resolved:
                return f"P{init} has acted. P1 — plan your response!", "Player 1"
            return f"Round {rnd} — P1 has initiative. Plan your actions!", "Player 1"
        if phase_key == "pass_to_select_p2":
            if self._init_player_resolved:
                return f"P{init} has acted. P2 — plan your response!", "Player 2"
            return f"Round {rnd} — P2 has initiative. Plan your actions!", "Player 2"
        if phase_key == "pass_to_resolve":
            p = self._resolving_player or init
            return (f"P{p} locked in — both players watch their actions!",
                    f"Both Watch")
        if phase_key.startswith("pass_to_extra_action_p"):
            pnum = phase_key[-1]
            unit = self._extra_action_queue[0][1] if self._extra_action_queue else None
            name = unit.name if unit else "?"
            return (f"Stitch In Time — {name} gets an extra action!",
                    f"Player {pnum}")
        return "Ready?", "Next Player"

    def _draw_extra_swap(self, surf, mouse_pos):
        surf.fill(BG)
        player = self._extra_swap_player
        draw_top_bar(surf, self.battle,
                     f"Round 1 Extra Swap — Player {player}")
        draw_formation(surf, self.battle, mouse_pos=mouse_pos)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)

        draw_text(surf, "Click TWO allies to swap them, or skip.", 20, YELLOW,
                  WIDTH // 2, HEIGHT - 80, center=True)
        if hasattr(self, '_extra_swap_pending') and self._extra_swap_pending:
            draw_text(surf, f"Selected: {self._extra_swap_pending.name}",
                      18, CYAN, WIDTH // 2, HEIGHT - 54, center=True)

        skip_btn = pygame.Rect(WIDTH // 2 - 90, HEIGHT - 48, 180, 40)
        draw_button(surf, skip_btn, "Skip Swap", mouse_pos, size=18)
        self._extra_swap_skip_btn = skip_btn

        # Click handling must go here for extra_swap phase
        # (handled in handle_click already)

    def _draw_select_actions(self, surf, mouse_pos):
        surf.fill(BG)
        if not self.battle or not self.current_actor:
            return

        actor = self.current_actor
        team  = self.battle.get_team(self.selecting_player)
        is_last = len(team.alive()) == 1 and team.alive()[0] == actor

        draw_top_bar(surf, self.battle,
                     f"P{self.selecting_player} — Selecting Actions")

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

        draw_formation(surf, self.battle,
                       selected_unit=actor,
                       valid_targets=valid_targets,
                       mouse_pos=mouse_pos,
                       acting_player=self.selecting_player)

        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)

        # Queued summary + clear-queue button
        draw_queued_summary(surf, team, 520, self.selecting_player)

        # Clear Queue button (only in main selection phase, not extra-action phase)
        if self.phase == "select_actions":
            team_has_queued = any(
                u.queued is not None or u.queued2 is not None
                for u in team.members if not u.ko
            )
            clear_rect = pygame.Rect(580, 646, 190, 34)
            draw_button(surf, clear_rect, "Clear Queue", mouse_pos, size=15,
                        normal=(55, 30, 30), hover=(80, 40, 40),
                        disabled=not team_has_queued)
            self._last_clear_btn = clear_rect if team_has_queued else None
        else:
            self._last_clear_btn = None

        # Detail panel — drawn below formations when a unit is inspected
        if self._detail_unit is not None:
            close_btn = draw_combatant_detail(surf, self._detail_unit)
            self._detail_close_btn = close_btn
        else:
            self._detail_close_btn = None

        # Hint: click any unit to view details
        if self._detail_unit is None:
            draw_text(surf, "Click any unit to inspect", 13, TEXT_MUTED,
                      20, BATTLE_DETAIL_RECT.y + 6)

        # Action buttons
        if self.selection_sub == "pick_action":
            abilities = actor.all_active_abilities(is_last)
            valid_abs = [a for a in abilities
                         if can_use_ability(actor, a, team)]
            btns = draw_action_menu(
                surf, mouse_pos, actor, valid_abs,
                swap_used=self.battle.swap_used_this_turn or self._swap_queued_this_turn(),
                state_label=f"Slot: {SLOT_LABELS.get(actor.slot, actor.slot)}"
            )
            self._last_action_buttons = btns

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


    def _draw_resolving(self, surf, mouse_pos):
        surf.fill(BG)
        if not self.battle:
            return
        rp = self._resolving_player
        init_done = self._init_player_resolved

        if self.phase == "resolve_done" and init_done:
            lbl = f"P{rp} acted — review, then pass to P{3 - (rp or 1)}"
        elif self.phase == "resolve_done":
            lbl = "Round complete — Continue when ready"
        else:
            lbl = f"P{rp} Acting — Both Watch" if rp else "Resolution"

        draw_top_bar(surf, self.battle, lbl)
        draw_formation(surf, self.battle, mouse_pos=mouse_pos)
        draw_log(surf, self.battle.log, scroll_offset=self.battle_log_scroll)

        # Detail panel
        if self._detail_unit is not None:
            close_btn = draw_combatant_detail(surf, self._detail_unit)
            self._detail_close_btn = close_btn
        else:
            self._detail_close_btn = None
            draw_text(surf, "Click any unit to inspect", 13, TEXT_MUTED,
                      20, BATTLE_DETAIL_RECT.y + 6)

        if self.phase == "resolve_done":
            if init_done:
                second = 3 - (rp or self.battle.init_player)
                btn_label = f"Continue → P{second} selects"
                msg = f"P{rp} done! Review the log, then hand to P{second}."
            else:
                btn_label = "Continue → Next Round"
                msg = "Round complete! Click Continue for the next round."
            draw_text(surf, msg, 20, GREEN, WIDTH // 2, HEIGHT - 36, center=True)
            cont_btn = pygame.Rect(WIDTH // 2 - 130, HEIGHT - 60, 260, 44)
            draw_button(surf, cont_btn, btn_label, mouse_pos, size=18,
                        normal=BLUE_DARK, hover=BLUE)
            self._last_resolve_btn = cont_btn


# ─────────────────────────────────────────────────────────────────────────────
# HANDLE EXTRA SWAP CLICK (patch into handle_click)
# ─────────────────────────────────────────────────────────────────────────────

_orig_handle_click = Game.handle_click

def _patched_handle_click(self, pos):
    if self.phase.startswith("extra_swap_p"):
        self._handle_extra_swap_click(pos)
        return
    if self.phase.startswith("extra_action_p"):
        self._handle_action_select_click(pos)
        return
    if self.phase in ("resolving", "resolve_done"):
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
    g._last_menu_btns   = (pygame.Rect(0,0,1,1),) * 4
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
    g._last_clear_btn      = None
    g._detail_close_btn    = None
    g._resolving_player    = None
    g._init_player_resolved = False
    g.run()


if __name__ == "__main__":
    main()
