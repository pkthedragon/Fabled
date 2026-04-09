from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from settings import SLOT_FRONT, SLOT_LABELS

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
from quests_ruleset_data import ULTIMATE_METER_MAX
from storybook_lan import apply_phase_plan, serialize_phase_plan
from storybook_tutorial import queue_tutorial_enemy_plan


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
            return team.ultimate_meter >= ULTIMATE_METER_MAX
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
            team_swap_taken = (
                team.markers.get("swap_action_selected", 0) > 0
                or any(
                    m is not actor and not m.ko
                    and (
                        (m.queued_action is not None and m.queued_action.get("type") == "swap")
                        or (m.queued_bonus_action is not None and m.queued_bonus_action.get("type") == "swap")
                    )
                    for m in team.members
                )
            )
            team_bonus_swap = team.markers.get("bonus_swap_rounds", 0) > 0 and team.markers.get("bonus_swap_used", 0) <= 0
            is_intrinsic_swapper = actor.class_skill.id == "covert" or actor.defn.id == "the_green_knight"
            if (is_intrinsic_swapper or (team_bonus_swap and not team_swap_taken)) and self._ally_targets(actor):
                actions.append(PendingChoice("swap", "Bonus Swap", needs_target=True, bonus=True))
            if (
                actor.defn.id != "ashen_ella"
                and not actor.dual_primary_weapons_active()
                and (actor.defn.id == "wayward_humbert" or actor.markers.get("bonus_switch_rounds", 0) > 0)
            ):
                actions.append(PendingChoice("switch", "Bonus Switch", bonus=True))
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
        if actor.defn.id != "ashen_ella" and not actor.dual_primary_weapons_active():
            actions.append(PendingChoice("switch", "Switch"))
        own_team = team_for_actor(self.battle, actor)
        team_swap_queued = any(
            m is not actor and not m.ko
            and m.queued_action is not None and m.queued_action.get("type") == "swap"
            for m in own_team.members
        )
        if self._ally_targets(actor) and not team_swap_queued:
            actions.append(PendingChoice("swap", "Swap", needs_target=True))
        actions.append(PendingChoice("skip", "Skip"))
        return actions

    def queued_label_for(self, actor, *, bonus: bool = False) -> str:
        action = actor.queued_bonus_action if bonus else actor.queued_action
        if action is None:
            return "Unqueued"
        action_type = action.get("type", "skip")
        target_slot = action.get("target_slot")
        target_slot_label = SLOT_LABELS.get(target_slot, target_slot.title() if isinstance(target_slot, str) else "")
        if action_type == "strike":
            return f"Strike {target_slot_label}".strip()
        if action_type == "spell":
            effect = action.get("effect")
            if target_slot_label and effect is not None and getattr(effect, "target", "") in {"enemy", "ally", "any"}:
                return f"{effect.name} {target_slot_label}"
            return effect.name if effect is not None else "Spell"
        if action_type == "ultimate":
            effect = action.get("effect")
            if target_slot_label and effect is not None and getattr(effect, "target", "") in {"enemy", "ally", "any"}:
                return f"{effect.name} {target_slot_label}"
            return effect.name if effect is not None else "Ultimate"
        if action_type == "swap":
            return f"Swap {target_slot_label}".strip()
        if action_type == "switch":
            return "Switch"
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
        self.pending_choice = PendingChoice(kind, effect.name, effect_id=effect.id, needs_target=effect.target in {"enemy", "ally", "any"}, bonus=self.phase.startswith("bonus"))
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
                queue_spell(actor, effect, target, self.battle)
        elif choice.kind == "ultimate":
            effect = actor.defn.ultimate
            if choice.bonus:
                queue_bonus_action(actor, {"type": "ultimate", "effect": effect, "target": target if effect.target != "self" else actor})
            else:
                queue_ultimate(actor, target if effect.target != "self" else actor, self.battle)
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


@dataclass
class TutorialBattleController(StoryBattleController):
    encounter_index: int = 1
    unlocked_actions: set[str] = field(default_factory=set)
    allow_bonus_actions: bool = False
    allow_ultimate_meter: bool = False
    tutorials_enabled: bool = True
    tutorial_prompt: str = ""
    tutorial_prompt_id: str | None = None
    tutorial_prompt_seen: set[str] = field(default_factory=set)
    tutorial_highlight_action: str | None = None
    tutorial_prompt_button_label: str = "Next"

    def begin_round(self):
        super().begin_round()
        self.refresh_tutorial_guidance()

    def _is_ai_team(self, team_num: int) -> bool:
        return team_num != self.human_team_num

    def _queue_ai_phase(self, *, bonus: bool):
        queue_tutorial_enemy_plan(self.battle, self.encounter_index, bonus=bonus)

    def available_spells(self, actor) -> list:
        spells = super().available_spells(actor)
        if "spellbook" not in self.unlocked_actions:
            return []
        if "ultimate" not in self.unlocked_actions:
            return [effect for effect in spells if effect.id != actor.defn.ultimate.id]
        return spells

    def available_actions(self, actor=None) -> list[PendingChoice]:
        actions = super().available_actions(actor)
        if self.phase.startswith("bonus") and not self.allow_bonus_actions:
            return [choice for choice in actions if choice.kind == "skip"]
        filtered = []
        for choice in actions:
            if choice.kind == "spellbook" and "spellbook" not in self.unlocked_actions:
                continue
            if choice.kind == "switch" and "switch" not in self.unlocked_actions:
                continue
            if choice.kind == "swap" and "swap" not in self.unlocked_actions:
                continue
            if choice.kind == "strike" and "strike" not in self.unlocked_actions:
                continue
            filtered.append(choice)
        forced_kind = self._forced_tutorial_action_kind(actor or self.active_actor)
        if forced_kind is not None:
            forced = [choice for choice in filtered if choice.kind == forced_kind]
            skips = [choice for choice in filtered if choice.kind == "skip"]
            if forced:
                return forced + skips
        return filtered

    def select_action(self, kind: str):
        super().select_action(kind)
        self.refresh_tutorial_guidance()

    def select_spell(self, effect_id: str):
        super().select_spell(effect_id)
        self.refresh_tutorial_guidance()

    def select_target(self, unit):
        super().select_target(unit)
        self.refresh_tutorial_guidance()

    def resolve_current_phase(self):
        if self.phase == "action_resolve_ready" and not self.allow_bonus_actions:
            resolve_action_phase(self.battle)
            if self.battle.winner is None:
                end_round(self.battle)
            if self.battle.winner is not None:
                self.phase = "result"
                self.refresh_tutorial_guidance()
                return
            self.begin_round()
            return
        super().resolve_current_phase()
        self.refresh_tutorial_guidance()

    def dismiss_tutorial_prompt(self):
        if self.tutorial_prompt_id is not None:
            self.tutorial_prompt_seen.add(self.tutorial_prompt_id)
        self.tutorial_prompt = ""
        self.tutorial_prompt_id = None
        self.tutorial_highlight_action = None
        self.refresh_tutorial_guidance()

    def _prompt_unit(self, defn_id: str, *, team_num: int):
        team = self.battle.team1 if team_num == 1 else self.battle.team2
        return next((unit for unit in team.members if unit.defn.id == defn_id), None)

    def _set_tutorial_prompt(self, prompt_id: str, text: str, *, highlight_action: str | None = None):
        self.tutorial_prompt_id = prompt_id
        self.tutorial_prompt = text
        self.tutorial_highlight_action = highlight_action

    def _forced_tutorial_action_kind(self, actor) -> str | None:
        if not self.tutorials_enabled or actor is None or self.phase.startswith("bonus") or self.encounter_index > 3:
            return None
        enemy_team_num = 2 if self.human_team_num == 1 else 1
        jack = self._prompt_unit("little_jack", team_num=self.human_team_num)
        marigold = self._prompt_unit("tutorial_marigold", team_num=enemy_team_num)
        daeny = self._prompt_unit("tutorial_daeny", team_num=enemy_team_num)
        rowan = self._prompt_unit("tutorial_rowan", team_num=enemy_team_num)
        if actor is not jack:
            return None
        if self.encounter_index == 1 and self.battle.round_num == 1:
            return "strike"
        if self.encounter_index == 2:
            if self.battle.round_num == 1 and jack.markers.get("ignore_targeting_strikes", 0) <= 0 and jack.cooldowns.get("cloudburst", 0) <= 0:
                return "spellbook"
            if marigold is not None and not marigold.ko and jack.markers.get("ignore_targeting_strikes", 0) > 0:
                return "strike"
        if self.encounter_index == 3:
            if self.battle.round_num == 1 and daeny is not None and not daeny.ko:
                return "strike"
        return None

    def refresh_tutorial_guidance(self):
        if not self.tutorials_enabled:
            self.tutorial_prompt = ""
            self.tutorial_prompt_id = None
            self.tutorial_highlight_action = None
            return
        if self.phase == "result":
            self.tutorial_prompt = ""
            self.tutorial_prompt_id = None
            self.tutorial_highlight_action = None
            return
        if self.tutorial_prompt_id is not None:
            return

        player_team = self.battle.team1 if self.human_team_num == 1 else self.battle.team2
        enemy_team = self.battle.team2 if self.human_team_num == 1 else self.battle.team1
        player_front = player_team.frontline()
        enemy_team_num = 2 if self.human_team_num == 1 else 1
        jack = self._prompt_unit("little_jack", team_num=self.human_team_num)
        liesl = self._prompt_unit("matchbox_liesl", team_num=self.human_team_num)
        porcus = self._prompt_unit("porcus_iii", team_num=self.human_team_num)
        marigold = self._prompt_unit("tutorial_marigold", team_num=enemy_team_num)
        daeny = self._prompt_unit("tutorial_daeny", team_num=enemy_team_num)
        rowan = self._prompt_unit("tutorial_rowan", team_num=enemy_team_num)
        tree_sentry = self._prompt_unit("tutorial_tree_sentry", team_num=enemy_team_num)
        tree_scout = self._prompt_unit("tutorial_tree_scout", team_num=enemy_team_num)
        tree_sentinel = self._prompt_unit("tutorial_tree_sentinel", team_num=enemy_team_num)
        tree_druid = self._prompt_unit("tutorial_tree_druid", team_num=enemy_team_num)
        tree_knight = self._prompt_unit("tutorial_tree_knight", team_num=enemy_team_num)
        tree_sorcerer = self._prompt_unit("tutorial_tree_sorcerer", team_num=enemy_team_num)
        wormwood_beast = self._prompt_unit("tutorial_wormwood_beast", team_num=enemy_team_num)

        prompt_checks: list[tuple[str, bool, str, str | None]] = []
        if self.encounter_index == 1:
            prompt_checks.extend(
                [
                    (
                        "enc1_intro",
                        self.phase == "action_select" and self.battle.round_num == 1 and self.active_actor is jack,
                        "Select Strike to attack with Jack's Skyfall. Melee weapons hit the enemy in front of you.",
                        "strike",
                    ),
                    (
                        "enc1_formula",
                        jack is not None and any(enemy.hp < enemy.max_hp for enemy in enemy_team.members),
                        "Damage is Weapon Power x (your Attack / target Defense), rounded up.",
                        None,
                    ),
                    (
                        "enc1_giant_slayer",
                        jack is not None and any(enemy.hp < enemy.max_hp and enemy.max_hp > jack.max_hp for enemy in enemy_team.members),
                        "Jack's Giant Slayer is active here, adding +25 damage against enemies with higher max HP than him.",
                        None,
                    ),
                ]
            )
        elif self.encounter_index == 2:
            prompt_checks.extend(
                [
                    (
                        "enc2_intro",
                        self.phase == "action_select" and self.battle.round_num == 1 and self.active_actor is jack,
                        "Try Spellcast first. Cloudburst makes Jack's next Strike ignore targeting restrictions, so he can reach Marigold behind Bar.",
                        "spellbook",
                    ),
                    (
                        "enc2_cloudburst",
                        jack is not None and (jack.cooldowns.get("cloudburst", 0) > 0 or jack.markers.get("ignore_targeting_strikes", 0) > 0),
                        "Cloudburst is active. Strike Marigold now, even though she is in the backline.",
                        "strike",
                    ),
                    (
                        "enc2_cooldown",
                        jack is not None and jack.cooldowns.get("cloudburst", 0) > 0,
                        "Cloudburst is on cooldown for 1 round now. Spells with cooldowns need time before they can be cast again.",
                        None,
                    ),
                    (
                        "enc2_ammo",
                        marigold is not None and marigold.primary_weapon.ammo > 0 and marigold.ammo_remaining.get(marigold.primary_weapon.id, marigold.primary_weapon.ammo) < marigold.primary_weapon.ammo,
                        "Marigold's Darts spend Ammo each time she Strikes. When it runs out, she has to reload before attacking again.",
                        None,
                    ),
                ]
            )
        elif self.encounter_index == 3:
            prompt_checks.extend(
                [
                    (
                        "enc3_intro",
                        self.phase == "action_select" and self.battle.round_num == 1 and self.active_actor is jack,
                        "Jack now has two signature weapons. Start with Skyfall on Daeny, then swap to Giant's Harp when you need backline reach.",
                        "strike",
                    ),
                    (
                        "enc3_switch",
                        jack is not None
                        and daeny is not None
                        and daeny.ko
                        and rowan is not None
                        and not rowan.ko
                        and rowan.slot != SLOT_FRONT
                        and jack.primary_weapon.id == "skyfall",
                        "Daeny is down, but Rowan is still protected in the backline. Switch to Giant's Harp so Jack can hit her with Magic.",
                        "switch",
                    ),
                    (
                        "enc3_magic",
                        jack is not None and jack.primary_weapon.id == "giants_harp",
                        "Magic weapons can strike from the frontline into the matching lane, but they go on cooldown after attacking.",
                        "strike",
                    ),
                ]
            )
        elif self.encounter_index == 4:
            prompt_checks.extend(
                [
                    (
                        "enc4_intro",
                        self.phase == "action_select" and self.battle.round_num == 1,
                        "Classes add bonus HP and passive power. Initiative also matters now, and backline Speed is halved before turn order is set.",
                        None,
                    ),
                    (
                        "enc4_initiative",
                        self.phase == "action_select" and self.battle.round_num == 1 and self.active_actor is jack,
                        "Check the initiative order: Jack acts before Liesl because he is in the frontline, while backline Speed is halved for Liesl and the Tree Archer.",
                        None,
                    ),
                    (
                        "enc4_martial",
                        jack is not None and jack.markers.get("struck_this_round", 0) > 0,
                        "Jack's Martial class skill adds +25 damage to his Melee Strikes, on top of his weapon's normal power.",
                        None,
                    ),
                    (
                        "enc4_guard",
                        tree_sentry is not None and tree_sentry.has_status("guard"),
                        "Tree Sentry's shield strike applies Guard, reducing the damage it takes while the condition lasts.",
                        None,
                    ),
                ]
            )
        elif self.encounter_index == 5:
            prompt_checks.extend(
                [
                    (
                        "enc5_intro",
                        self.phase == "action_select" and self.battle.round_num == 1 and self.active_actor is not None,
                        "Swap Positions is unlocked. Try moving Liesl forward to remove her backline Speed penalty, but remember Tree Scout punishes recent Swappers.",
                        "swap",
                    ),
                    (
                        "enc5_swapped",
                        any(unit.markers.get("swapped_this_round", 0) > 0 for unit in player_team.members),
                        "That swap immediately changed formation. Frontline removes the Speed penalty, while backline halves Speed again.",
                        None,
                    ),
                    (
                        "enc5_assassin",
                        tree_scout is not None and any(unit.markers.get("swapped_this_round", 0) > 0 for unit in player_team.members),
                        "Tree Scout's Assassin skill threatens units that just swapped. Powerful repositioning always comes with some risk.",
                        None,
                    ),
                ]
            )
        elif self.encounter_index == 6:
            prompt_checks.extend(
                [
                    (
                        "enc6_intro",
                        self.phase == "action_select" and self.battle.round_num == 1 and player_front is porcus,
                        "Porcus holds the frontline now. This is your first full 3v3 battle, so use him to protect Jack and Liesl.",
                        None,
                    ),
                    (
                        "enc6_bonus",
                        self.phase == "bonus_select",
                        "This is the Bonus Action phase. Not every adventurer has one yet, but from here on the round is split into main actions and bonus actions.",
                        None,
                    ),
                    (
                        "enc6_bricklayer",
                        porcus is not None and porcus.markers.get("bricklayer_triggered_this_round", 0) > 0,
                        "Porcus's Bricklayer just triggered. Heavy Strikes into him are softened, and the attacker is Weakened for 2 rounds.",
                        None,
                    ),
                ]
            )
        elif self.encounter_index == 7:
            prompt_checks.extend(
                [
                    (
                        "enc7_intro",
                        self.phase == "action_select" and self.battle.round_num == 1,
                        "This is your first battle with a self-built trio. Your class and class-skill choices from loadout matter now.",
                        None,
                    ),
                    (
                        "enc7_sentinel",
                        tree_sentinel is not None and any(buff.stat == "defense" and buff.duration > 0 for buff in tree_sentinel.buffs),
                        "Tree Sentinel's strike fortifies the whole enemy team with extra Defense for 2 rounds. Bursting through that timing matters.",
                        None,
                    ),
                    (
                        "enc7_druid",
                        tree_druid is not None and tree_druid.markers.get("spells_cast_this_round", 0) > 0,
                        "Tree Druid can use its sigil to heal allies instead of damaging you, and Medic-style healing removes status problems too.",
                        None,
                    ),
                ]
            )
        elif self.encounter_index == 8:
            prompt_checks.extend(
                [
                    (
                        "enc8_intro",
                        self.phase == "action_select" and self.battle.round_num == 1,
                        "Artifacts grant their stat bonus even when unattuned. Attunement only controls whether the artifact spell can be used.",
                        None,
                    ),
                    (
                        "enc8_unattuned",
                        any(unit.artifact is not None and unit.class_name not in unit.artifact.attunement for unit in player_team.members),
                        "One of your artifacts is unattuned here. You still keep its stat bonus, but its spell stays unavailable until the class matches.",
                        None,
                    ),
                    (
                        "enc8_enemy_artifact",
                        (
                            tree_knight is not None
                            and tree_knight.cooldowns.get("grave_tiding", 0) > 0
                        ) or (
                            tree_sorcerer is not None
                            and tree_sorcerer.cooldowns.get("clear_skies", 0) > 0
                        ),
                        "Enemy artifacts are active too. Some are reactive like Black Torch, while others set up a stronger follow-up strike like Bottled Clouds.",
                        None,
                    ),
                ]
            )
        elif self.encounter_index == 9:
            prompt_checks.extend(
                [
                    (
                        "enc9_intro",
                        self.phase == "action_select" and self.battle.round_num == 1,
                        "The Ultimate Meter is live now. Non-Magic Strikes add 1, Spells add 2, and a full meter unlocks an Ultimate.",
                        None,
                    ),
                    (
                        "enc9_meter",
                        player_team.ultimate_meter > 0,
                        "Your team has started charging the Ultimate Meter. Keep mixing Strikes and Spells to fill it.",
                        None,
                    ),
                    (
                        "enc9_full",
                        player_team.ultimate_meter >= 5 and self.active_actor is not None,
                        "The meter is full. Open Spellcast for the active adventurer and choose their Ultimate.",
                        "spellbook",
                    ),
                    (
                        "enc9_cast",
                        player_team.markers.get("ultimates_cast", 0) > 0 and player_team.ultimate_meter == 0,
                        "An Ultimate was cast, so the meter reset to 0. Cast three Ultimates in one encounter to win instantly by Ultimate Victory.",
                        None,
                    ),
                    (
                        "enc9_one_more",
                        player_team.markers.get("ultimates_cast", 0) >= 2,
                        "One more Ultimate cast will end the encounter immediately with Ultimate Victory.",
                        None,
                    ),
                ]
            )
        for prompt_id, condition, text, highlight_action in prompt_checks:
            if prompt_id in self.tutorial_prompt_seen:
                continue
            if condition:
                self._set_tutorial_prompt(prompt_id, text, highlight_action=highlight_action)
                return

        self.tutorial_prompt = ""
        self.tutorial_prompt_id = None
        self.tutorial_highlight_action = None


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
