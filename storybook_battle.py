from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from settings import SLOT_FRONT

from quests_ai_battle import queue_team_plan
from quests_ruleset_logic import (
    end_round,
    get_legal_targets,
    player_num_for_actor,
    queue_bonus_action,
    queue_skip,
    queue_spell,
    queue_strike,
    queue_swap,
    queue_switch,
    queue_ultimate,
    resolve_action_phase,
    resolve_bonus_phase,
    start_round,
    team_for_actor,
)
from storybook_lan import apply_phase_plan, serialize_phase_plan


@dataclass
class PendingChoice:
    kind: str
    label: str
    effect_id: str | None = None
    needs_target: bool = False
    bonus: bool = False


@dataclass
class StoryBattleController:
    battle: object
    results_kind: str
    human_team_num: int = 1
    ai_difficulties: dict[int, str] = field(default_factory=lambda: {2: "hard"})
    phase: str = "action_select"
    selection_index: int = -1
    active_actor: object | None = None
    pending_choice: Optional[PendingChoice] = None
    target_candidates: list[object] = field(default_factory=list)
    spellbook_open: bool = False
    focus_unit: object | None = None
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self):
        self.ai_difficulties = {
            team_num: difficulty
            for team_num, difficulty in self.ai_difficulties.items()
            if team_num != self.human_team_num
        }
        self.begin_round()

    def begin_round(self):
        start_round(self.battle)
        self.phase = "action_select"
        self.selection_index = -1
        self.active_actor = None
        self.pending_choice = None
        self.target_candidates = []
        self.spellbook_open = False
        if self.focus_unit is None:
            preferred_team = self.battle.get_team(self.human_team_num)
            self.focus_unit = preferred_team.frontline() or (preferred_team.alive() or [None])[0]
        self._queue_ai_phase(bonus=False)
        self._advance_selection()

    def current_phase_label(self) -> str:
        labels = {
            "action_select": "Action Selection",
            "action_target": "Action Selection",
            "action_resolve_ready": "Action Resolving",
            "bonus_select": "Bonus Action Selection",
            "bonus_target": "Bonus Action Selection",
            "bonus_resolve_ready": "Bonus Action Resolving",
            "result": "Battle Complete",
        }
        return labels.get(self.phase, "Battle")

    def can_resolve(self) -> bool:
        return self.phase in {"action_resolve_ready", "bonus_resolve_ready"}

    def resolve_button_label(self) -> str:
        return "Resolve Bonus Phase" if self.phase == "bonus_resolve_ready" else "Resolve Actions"

    def active_team_label(self) -> str:
        if self.active_actor is None:
            return "Resolve queued phase" if self.can_resolve() else "Round overview"
        team = team_for_actor(self.battle, self.active_actor)
        return f"{team.player_name}: {self.active_actor.name}"

    def _is_ai_team(self, team_num: int) -> bool:
        return team_num in self.ai_difficulties

    def _is_ai_actor(self, actor) -> bool:
        return self._is_ai_team(player_num_for_actor(self.battle, actor))

    def _queue_ai_phase(self, *, bonus: bool):
        for team_num, difficulty in sorted(self.ai_difficulties.items()):
            queue_team_plan(
                self.battle,
                team_num,
                bonus=bonus,
                difficulty=difficulty,
                rng=self.rng,
            )

    def _ally_targets(self, actor):
        team = team_for_actor(self.battle, actor)
        return [ally for ally in team.alive() if ally is not actor]

    def _effect_usable(self, actor, effect) -> bool:
        if effect.id == actor.defn.ultimate.id:
            team = team_for_actor(self.battle, actor)
            return team.ultimate_meter >= 10
        if actor.cooldowns.get(effect.id, 0) > 0:
            return False
        if effect in actor.primary_weapon.spells and actor.primary_weapon.ammo > 0:
            ammo_left = actor.ammo_remaining.get(actor.primary_weapon.id, actor.primary_weapon.ammo)
            return ammo_left >= effect.ammo_cost
        return True

    def available_spells(self, actor) -> list:
        if actor is None:
            return []
        spells = [effect for effect in actor.active_spells() if self._effect_usable(actor, effect)]
        if self._effect_usable(actor, actor.defn.ultimate):
            spells.append(actor.defn.ultimate)
        return spells

    def available_bonus_spells(self, actor) -> list:
        if actor is None:
            return []
        spells = []
        if actor.markers.get("spell_bonus_rounds", 0) > 0:
            spells.extend(effect for effect in actor.active_spells() if self._effect_usable(actor, effect))
        bonus_effect = actor.markers.get("artifact_bonus_spell_effect")
        if (
            actor.markers.get("artifact_bonus_spell_rounds", 0) > 0
            and bonus_effect is not None
            and self._effect_usable(actor, bonus_effect)
            and all(effect.id != bonus_effect.id for effect in spells)
        ):
            spells.append(bonus_effect)
        return spells

    def available_actions(self, actor=None) -> list[PendingChoice]:
        actor = actor or self.active_actor
        if actor is None:
            return []
        if self.phase.startswith("bonus"):
            actions = []
            team = team_for_actor(self.battle, actor)
            team_bonus_swap = team.markers.get("bonus_swap_rounds", 0) > 0 and team.markers.get("bonus_swap_used", 0) <= 0
            if (actor.class_skill.id == "covert" or actor.defn.id == "the_green_knight" or team_bonus_swap) and self._ally_targets(actor):
                actions.append(PendingChoice("swap", "Bonus Swap", needs_target=True, bonus=True))
            if (actor.class_skill.id == "tactical" or actor.defn.id == "wayward_humbert") and actor.defn.id != "ashen_ella":
                actions.append(PendingChoice("switch", "Bonus Switch", bonus=True))
            if actor.markers.get("vanguard_ready", 0) > 0:
                actions.append(PendingChoice("vanguard", "Vanguard", bonus=True))
            if self.available_bonus_spells(actor):
                actions.append(PendingChoice("spellbook", "Bonus Spell", bonus=True))
            actions.append(PendingChoice("skip", "Skip Bonus", bonus=True))
            return actions

        actions = []
        strike_targets = get_legal_targets(self.battle, actor, effect=actor.primary_weapon.strike, weapon=actor.primary_weapon)
        if strike_targets:
            actions.append(PendingChoice("strike", "Strike", needs_target=True))
        if self.available_spells(actor):
            actions.append(PendingChoice("spellbook", "Spellcast"))
        if actor.defn.id != "ashen_ella":
            actions.append(PendingChoice("switch", "Switch"))
        if self._ally_targets(actor):
            actions.append(PendingChoice("swap", "Swap", needs_target=True))
        actions.append(PendingChoice("skip", "Skip"))
        return actions

    def queued_label_for(self, actor, *, bonus: bool = False) -> str:
        action = actor.queued_bonus_action if bonus else actor.queued_action
        if action is None:
            return "Unqueued"
        action_type = action.get("type", "skip")
        if action_type == "strike":
            target = action.get("target")
            return f"Strike {target.name if target is not None else ''}".strip()
        if action_type == "spell":
            effect = action.get("effect")
            return effect.name if effect is not None else "Spell"
        if action_type == "ultimate":
            effect = action.get("effect")
            return effect.name if effect is not None else "Ultimate"
        if action_type == "swap":
            target = action.get("target")
            return f"Swap {target.name if target is not None else ''}".strip()
        if action_type == "switch":
            return "Switch"
        if action_type == "vanguard":
            return "Vanguard"
        return "Skip"

    def select_action(self, kind: str):
        if self.active_actor is None:
            return
        if kind == "spellbook":
            self.spellbook_open = not self.spellbook_open
            return
        action = next((choice for choice in self.available_actions() if choice.kind == kind), None)
        if action is None:
            return
        self.pending_choice = action
        self.target_candidates = []
        self.spellbook_open = False
        if kind == "strike":
            self.target_candidates = get_legal_targets(
                self.battle,
                self.active_actor,
                effect=self.active_actor.primary_weapon.strike,
                weapon=self.active_actor.primary_weapon,
            )
            self.phase = "bonus_target" if action.bonus else "action_target"
            return
        if kind == "swap":
            self.target_candidates = self._ally_targets(self.active_actor)
            self.phase = "bonus_target" if action.bonus else "action_target"
            return
        self._queue_choice(None)

    def select_spell(self, effect_id: str):
        if self.active_actor is None:
            return
        spell_options = self.available_bonus_spells(self.active_actor) if self.phase.startswith("bonus") else self.available_spells(self.active_actor)
        effect = next((item for item in spell_options if item.id == effect_id), None)
        if effect is None:
            return
        kind = "ultimate" if effect.id == self.active_actor.defn.ultimate.id else "spell"
        self.pending_choice = PendingChoice(kind, effect.name, effect_id=effect.id, needs_target=effect.target in {"enemy", "ally"}, bonus=self.phase.startswith("bonus"))
        self.target_candidates = []
        self.spellbook_open = False
        if effect.target in {"none", "self"}:
            self._queue_choice(None)
            return
        self.target_candidates = get_legal_targets(self.battle, self.active_actor, effect=effect, weapon=self.active_actor.primary_weapon)
        self.phase = "bonus_target" if self.pending_choice.bonus else "action_target"

    def select_target(self, unit):
        if self.pending_choice is None or self.active_actor is None:
            return
        if unit not in self.target_candidates:
            return
        self._queue_choice(unit)

    def cancel_targeting(self):
        if self.phase in {"action_target", "bonus_target"}:
            self.phase = "bonus_select" if self.phase == "bonus_target" else "action_select"
            self.pending_choice = None
            self.target_candidates = []

    def _queue_choice(self, target):
        actor = self.active_actor
        choice = self.pending_choice
        if actor is None or choice is None:
            return

        if choice.kind == "strike":
            queue_strike(actor, target)
        elif choice.kind == "spell":
            spell_options = self.available_bonus_spells(actor) if choice.bonus else self.available_spells(actor)
            effect = next(effect for effect in spell_options if effect.id == choice.effect_id)
            if choice.bonus:
                queue_bonus_action(actor, {"type": "spell", "effect": effect, "target": target})
            else:
                queue_spell(actor, effect, target)
        elif choice.kind == "ultimate":
            effect = actor.defn.ultimate
            if choice.bonus:
                queue_bonus_action(actor, {"type": "ultimate", "effect": effect, "target": target if effect.target != "self" else actor})
            else:
                queue_ultimate(actor, target if effect.target != "self" else actor)
        elif choice.kind == "switch":
            if choice.bonus:
                queue_bonus_action(actor, {"type": "switch"})
            else:
                queue_switch(actor)
        elif choice.kind == "swap":
            if choice.bonus:
                queue_bonus_action(actor, {"type": "swap", "target": target})
            else:
                queue_swap(actor, target)
        elif choice.kind == "vanguard":
            queue_bonus_action(actor, {"type": "vanguard"})
        else:
            if choice.bonus:
                queue_bonus_action(actor, {"type": "skip"})
            else:
                queue_skip(actor)

        self.pending_choice = None
        self.target_candidates = []
        self._advance_selection()

    def _advance_selection(self):
        selecting_bonus = self.phase.startswith("bonus")
        base_phase = "bonus_select" if selecting_bonus else "action_select"
        ready_phase = "bonus_resolve_ready" if selecting_bonus else "action_resolve_ready"
        self.phase = base_phase

        while True:
            self.selection_index += 1
            if self.selection_index >= len(self.battle.initiative_order):
                self.active_actor = None
                self.phase = ready_phase
                return
            actor = self.battle.initiative_order[self.selection_index]
            if actor.ko:
                continue
            if actor.markers.get("cant_act_rounds", 0) > 0:
                if selecting_bonus:
                    queue_bonus_action(actor, {"type": "skip"})
                else:
                    queue_skip(actor)
                continue
            if self._is_ai_actor(actor):
                continue
            self.active_actor = actor
            self.focus_unit = actor
            actions = self.available_actions(actor)
            if selecting_bonus and len(actions) == 1 and actions[0].kind == "skip":
                queue_bonus_action(actor, {"type": "skip"})
                continue
            return

    def resolve_current_phase(self):
        if self.phase == "action_resolve_ready":
            resolve_action_phase(self.battle)
            if self.battle.winner is not None:
                self.phase = "result"
                return
            self.phase = "bonus_select"
            self.selection_index = -1
            self.active_actor = None
            self.pending_choice = None
            self.target_candidates = []
            self._queue_ai_phase(bonus=True)
            self._advance_selection()
            return

        if self.phase == "bonus_resolve_ready":
            resolve_bonus_phase(self.battle)
            if self.battle.winner is None:
                end_round(self.battle)
            if self.battle.winner is not None:
                self.phase = "result"
                return
            self.begin_round()

    def winner_label(self) -> str:
        if self.battle.winner is None:
            return ""
        team = self.battle.team1 if self.battle.winner == 1 else self.battle.team2
        return team.player_name

    def result_lines(self) -> list[str]:
        lines = [
            f"Rounds fought: {self.battle.round_num - 1}",
            f"{self.battle.team1.player_name} survivors: {len(self.battle.team1.alive())}",
            f"{self.battle.team2.player_name} survivors: {len(self.battle.team2.alive())}",
        ]
        return lines

    def action_summary_rows(self, *, bonus: bool = False):
        rows = []
        for actor in self.battle.initiative_order:
            if actor.ko:
                continue
            rows.append(
                {
                    "actor": actor,
                    "team_num": player_num_for_actor(self.battle, actor),
                    "label": self.queued_label_for(actor, bonus=bonus),
                }
            )
        return rows

    def inspect(self, unit):
        self.focus_unit = unit

    def legal_targets(self) -> list:
        return list(self.target_candidates)

    def battlefield_slots(self) -> list[dict]:
        slots = []
        for team_num, team in ((1, self.battle.team1), (2, self.battle.team2)):
            for slot_name in ("front", "back_left", "back_right"):
                unit = next((member for member in team.members if member.slot == slot_name and not member.ko), None)
                slots.append({"team_num": team_num, "slot": slot_name, "unit": unit})
        return slots

    def highlightable_units(self) -> list:
        units = []
        for team in (self.battle.team1, self.battle.team2):
            units.extend(team.alive())
        return units

    def suggested_frontliner(self) -> str:
        front = self.battle.team1.frontline()
        return front.name if front is not None else "No frontline"


class StoryLanBattleController(StoryBattleController):
    def __init__(self, battle, results_kind: str, *, local_team_num: int, lan_session, is_host: bool):
        self.lan_session = lan_session
        self.is_host = is_host
        self.remote_team_num = 2 if local_team_num == 1 else 1
        self.waiting_for_remote_phase = False
        self.local_phase_committed = False
        self.remote_phase_ready = False
        self.remote_phase_actions: list[dict] = []
        super().__init__(
            battle=battle,
            results_kind=results_kind,
            human_team_num=local_team_num,
            ai_difficulties={},
        )

    def resolve_button_label(self) -> str:
        if self.waiting_for_remote_phase:
            return "Waiting..."
        return "Lock In Bonus" if self.phase == "bonus_resolve_ready" else "Lock In Actions"

    def active_team_label(self) -> str:
        if self.waiting_for_remote_phase:
            return "Waiting for remote plans"
        return super().active_team_label()

    def can_resolve(self) -> bool:
        return self.phase in {"action_resolve_ready", "bonus_resolve_ready"} and not self.waiting_for_remote_phase

    def _advance_selection(self):
        selecting_bonus = self.phase.startswith("bonus")
        base_phase = "bonus_select" if selecting_bonus else "action_select"
        ready_phase = "bonus_resolve_ready" if selecting_bonus else "action_resolve_ready"
        self.phase = base_phase

        while True:
            self.selection_index += 1
            if self.selection_index >= len(self.battle.initiative_order):
                self.active_actor = None
                self.phase = ready_phase
                self.local_phase_committed = False
                self.waiting_for_remote_phase = False
                return
            actor = self.battle.initiative_order[self.selection_index]
            if actor.ko:
                continue
            if actor.markers.get("cant_act_rounds", 0) > 0:
                if selecting_bonus:
                    queue_bonus_action(actor, {"type": "skip"})
                else:
                    queue_skip(actor)
                continue
            if player_num_for_actor(self.battle, actor) != self.human_team_num:
                continue
            self.active_actor = actor
            self.focus_unit = actor
            actions = self.available_actions(actor)
            if selecting_bonus and len(actions) == 1 and actions[0].kind == "skip":
                queue_bonus_action(actor, {"type": "skip"})
                continue
            return

    def poll_network(self):
        for message in self.lan_session.poll():
            if message.get("type") == "_disconnect":
                self.waiting_for_remote_phase = True
                self.phase = "result"
                self.battle.winner = self.human_team_num
                self.battle.log_add("Remote player disconnected.")
                return
            if self.is_host and message.get("type") == "battle_plan":
                phase_name = message.get("phase", "action")
                expected_bonus = phase_name == "bonus"
                if expected_bonus != self.phase.startswith("bonus"):
                    continue
                self.remote_phase_actions = list(message.get("actions", []))
                self.remote_phase_ready = True
                if self.local_phase_committed:
                    self._resolve_network_phase(phase_name)
            elif (not self.is_host) and message.get("type") == "battle_resolve":
                phase_name = message.get("phase", "action")
                expected_bonus = phase_name == "bonus"
                if expected_bonus != self.phase.startswith("bonus"):
                    continue
                self.waiting_for_remote_phase = False
                self.remote_phase_actions = list(message.get("actions", []))
                self._apply_and_finish_remote_phase(phase_name)

    def resolve_current_phase(self):
        phase_name = "bonus" if self.phase == "bonus_resolve_ready" else "action"
        self.local_phase_committed = True
        self.waiting_for_remote_phase = True
        local_actions = serialize_phase_plan(self.battle, self.human_team_num, bonus=phase_name == "bonus")
        if self.is_host:
            if self.remote_phase_ready:
                self._resolve_network_phase(phase_name)
        else:
            self.lan_session.send(
                {
                    "type": "battle_plan",
                    "phase": phase_name,
                    "actions": local_actions,
                }
            )

    def _resolve_network_phase(self, phase_name: str):
        apply_phase_plan(self.battle, self.remote_phase_actions, bonus=phase_name == "bonus")
        self.lan_session.send(
            {
                "type": "battle_resolve",
                "phase": phase_name,
                "actions": self.remote_phase_actions,
            }
        )
        self.waiting_for_remote_phase = False
        self.remote_phase_ready = False
        self._finish_phase_resolution(phase_name)

    def _apply_and_finish_remote_phase(self, phase_name: str):
        apply_phase_plan(self.battle, self.remote_phase_actions, bonus=phase_name == "bonus")
        self.remote_phase_actions = []
        self.remote_phase_ready = False
        self._finish_phase_resolution(phase_name)

    def _finish_phase_resolution(self, phase_name: str):
        if phase_name == "action":
            resolve_action_phase(self.battle)
            if self.battle.winner is not None:
                self.phase = "result"
                return
            self.phase = "bonus_select"
            self.selection_index = -1
            self.active_actor = None
            self.pending_choice = None
            self.target_candidates = []
            self.local_phase_committed = False
            self.waiting_for_remote_phase = False
            self._advance_selection()
            return

        resolve_bonus_phase(self.battle)
        if self.battle.winner is None:
            end_round(self.battle)
        if self.battle.winner is not None:
            self.phase = "result"
            return
        self.local_phase_committed = False
        self.waiting_for_remote_phase = False
        self.remote_phase_ready = False
        self.begin_round()
