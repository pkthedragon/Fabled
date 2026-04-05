from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from itertools import product
from typing import Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_tags import ADVENTURER_AI
from quests_ruleset_data import ULTIMATE_METER_MAX, ULTIMATE_WIN_COUNT
from quests_ruleset_logic import (
    determine_initiative_order,
    get_legal_targets,
    player_num_for_actor,
    queue_bonus_action,
    queue_skip,
    queue_spell,
    queue_strike,
    queue_swap,
    queue_switch,
    queue_ultimate,
    resolve_action,
    resolve_action_phase,
    resolve_bonus_phase,
    team_for_actor,
)


STATUS_WEIGHTS = {
    "burn": 5,
    "root": 11,
    "shock": 9,
    "weaken": 8,
    "expose": 10,
    "guard": 8,
    "spotlight": 6,
    "taunt": 8,
}


LOCAL_KEEP = {
    "easy": 2,
    "normal": 3,
    "hard": 4,
    "ranked": 4,
}


TEAM_KEEP = {
    "easy": 6,
    "normal": 10,
    "hard": 14,
    "ranked": 18,
}


OPPONENT_PACKAGE_KEEP = {
    "easy": 1,
    "normal": 2,
    "hard": 4,
    "ranked": 4,
}


DEEP_LOOKAHEAD_KEEP = {
    "easy": 0,
    "normal": 2,
    "hard": 3,
    "ranked": 3,
}


@dataclass(frozen=True)
class ActionSpec:
    kind: str
    target_ref: Optional[tuple[int, str]] = None
    effect_id: Optional[str] = None
    bonus: bool = False


@dataclass(frozen=True)
class RoundAnalysis:
    plan_kind: str
    race_kind: str
    priority_target_ref: Optional[tuple[int, str]]
    killable_enemy_refs: tuple[tuple[int, str], ...]
    vulnerable_ally_ref: Optional[tuple[int, str]]
    fallback_front_ref: Optional[tuple[int, str]]
    pivot_needed: bool


def _unit_ref(battle, unit) -> tuple[int, str]:
    return (player_num_for_actor(battle, unit), unit.defn.id)


def _find_unit(battle, ref: tuple[int, str]):
    team = battle.team1 if ref[0] == 1 else battle.team2
    return next((unit for unit in team.members if unit.defn.id == ref[1]), None)


def _team_bonus_swap_available(team) -> bool:
    return team.markers.get("bonus_swap_rounds", 0) > 0 and team.markers.get("bonus_swap_used", 0) <= 0


def _rough_damage(battle, actor, target, effect, *, weapon=None) -> int:
    if effect.power <= 0 or target is None or target.ko:
        return 0
    attack_stat = "attack"
    if actor.defn.id == "maui_sunthief" and actor.primary_weapon.id == "ancestral_warclub":
        attack_stat = "defense"
    power = effect.power
    if weapon is not None:
        if weapon.kind == "melee" and actor.class_skill.id == "martial":
            power += 15
        elif weapon.kind == "magic" and actor.class_skill.id == "arcane":
            power += 10
        elif weapon.kind == "ranged" and actor.class_skill.id == "deadeye":
            power += 10
    if actor.has_status("weaken"):
        power = int((power * 0.85) + 0.999)
    if target.has_status("guard") and actor.defn.id != "robin_hooded_avenger":
        power = int((power * 0.85) + 0.999)
    if target.has_status("expose"):
        power = int((power * 1.15) + 0.999)
    damage = max(1, int((power * (actor.get_stat(attack_stat) / max(1, target.get_stat("defense")))) + 0.999))
    actor_team = team_for_actor(battle, actor)
    target_team = battle.team1 if actor_team is battle.team2 else battle.team2
    if actor_team is not target_team:
        if any(ally.defn.id == "kama_the_honeyed" and ally is not actor and ally.slot == target.slot for ally in actor_team.alive()):
            damage += 10
    return damage


def _effect_usable(actor, effect) -> bool:
    if actor.cooldowns.get(effect.id, 0) > 0:
        return False
    if effect in actor.primary_weapon.spells and actor.primary_weapon.ammo > 0:
        ammo_left = actor.ammo_remaining.get(actor.primary_weapon.id, actor.primary_weapon.ammo)
        if ammo_left < effect.ammo_cost:
            return False
    return True


def _active_spells_for_phase(actor, *, bonus: bool) -> list:
    if not bonus:
        return [effect for effect in actor.active_spells() if _effect_usable(actor, effect)]
    effects = []
    if actor.markers.get("spell_bonus_rounds", 0) > 0:
        effects.extend(effect for effect in actor.active_spells() if _effect_usable(actor, effect))
    bonus_effect = actor.markers.get("artifact_bonus_spell_effect")
    if (
        actor.markers.get("artifact_bonus_spell_rounds", 0) > 0
        and bonus_effect is not None
        and _effect_usable(actor, bonus_effect)
        and all(existing.id != bonus_effect.id for existing in effects)
    ):
        effects.append(bonus_effect)
    return effects


def _allies(actor, battle):
    team = team_for_actor(battle, actor)
    return [ally for ally in team.alive() if ally is not actor]


def _threat_value(unit) -> float:
    profile = ADVENTURER_AI[unit.defn.id]
    value = profile.base_power * 0.4
    tags = set(profile.role_tags)
    if "burst_finisher" in tags:
        value += 18
    if "shock_engine" in tags or "root_enabler" in tags or "expose_enabler" in tags:
        value += 12
    if "healer" in tags or "guard_support" in tags:
        value += 10
    if unit.slot == SLOT_FRONT:
        value += 6
    return value


def _access_count(battle, team_num: int, target) -> int:
    count = 0
    if target is None or target.ko:
        return 0
    for actor in battle.get_team(team_num).alive():
        strike_targets = get_legal_targets(battle, actor, effect=actor.primary_weapon.strike, weapon=actor.primary_weapon)
        if target in strike_targets:
            count += 1
            continue
        for effect in _active_spells_for_phase(actor, bonus=False):
            if effect.target != "enemy":
                continue
            if target in get_legal_targets(battle, actor, effect=effect, weapon=actor.primary_weapon):
                count += 1
                break
    return count


def _estimate_team_damage_to_target(battle, team_num: int, target) -> float:
    total = 0.0
    for actor in battle.get_team(team_num).alive():
        best = 0.0
        strike_targets = get_legal_targets(battle, actor, effect=actor.primary_weapon.strike, weapon=actor.primary_weapon)
        if target in strike_targets:
            best = max(best, _rough_damage(battle, actor, target, actor.primary_weapon.strike, weapon=actor.primary_weapon))
        for effect in _active_spells_for_phase(actor, bonus=False):
            if effect.target != "enemy":
                continue
            if target in get_legal_targets(battle, actor, effect=effect, weapon=actor.primary_weapon):
                best = max(best, _rough_damage(battle, actor, target, effect, weapon=actor.primary_weapon))
        if team_for_actor(battle, actor).ultimate_meter >= ULTIMATE_METER_MAX:
            effect = actor.defn.ultimate
            if effect.target == "enemy" and target in get_legal_targets(battle, actor, effect=effect):
                best = max(best, _rough_damage(battle, actor, target, effect, weapon=actor.primary_weapon))
        total += best
    return total


def analyze_round_state(battle, team_num: int) -> RoundAnalysis:
    own = battle.get_team(team_num)
    enemy = battle.get_enemy(team_num)
    killable: list[tuple[int, str]] = []
    priority_target_ref: Optional[tuple[int, str]] = None
    best_priority = float("-inf")
    for enemy_unit in enemy.alive():
        estimated = _estimate_team_damage_to_target(battle, team_num, enemy_unit)
        target_ref = _unit_ref(battle, enemy_unit)
        if estimated >= enemy_unit.hp:
            killable.append(target_ref)
        collapse = 12 if enemy_unit.slot == SLOT_FRONT else 6
        tags = set(ADVENTURER_AI[enemy_unit.defn.id].role_tags)
        if "healer" in tags:
            collapse += 8
        if {"guard_support", "tempo_engine", "spell_loop", "shock_engine", "root_enabler", "expose_enabler"} & tags:
            collapse += 5
        access = _access_count(battle, team_num, enemy_unit)
        focus_bonus = 0.0
        if access >= 2:
            focus_bonus += 7.0
        elif access == 1:
            focus_bonus += 2.0
        if enemy_unit.hp <= max(50, int(enemy_unit.max_hp * 0.32)):
            focus_bonus += 9.0
        priority = estimated * 0.35 + _threat_value(enemy_unit) + collapse + focus_bonus
        if priority > best_priority:
            best_priority = priority
            priority_target_ref = target_ref
    vulnerable = None
    vulnerable_score = float("-inf")
    for ally in own.alive():
        hp_ratio = ally.hp / max(1, ally.max_hp)
        risk = (1.0 - hp_ratio) * 100.0
        if ally.slot == SLOT_FRONT:
            risk += 10.0
        if "fragile" in ADVENTURER_AI[ally.defn.id].role_tags:
            risk += 12.0
        if risk > vulnerable_score:
            vulnerable_score = risk
            vulnerable = ally
    back_left = own.get_slot(SLOT_BACK_LEFT)
    front = own.frontline()
    fallback_ref = _unit_ref(battle, back_left) if back_left is not None else None
    pivot_needed = False
    if front is not None and back_left is not None:
        front_score = ADVENTURER_AI[front.defn.id].position_scores[SLOT_FRONT]
        back_left_score = ADVENTURER_AI[back_left.defn.id].position_scores[SLOT_FRONT]
        if back_left_score - front_score >= 16:
            pivot_needed = True
        if front.hp / max(1, front.max_hp) <= 0.3 and back_left_score > front_score:
            pivot_needed = True

    own_kill_pressure = sum(_estimate_team_damage_to_target(battle, team_num, enemy_unit) for enemy_unit in enemy.alive())
    enemy_kill_pressure = sum(_estimate_team_damage_to_target(battle, 2 if team_num == 1 else 1, ally) for ally in own.alive())
    own_ultimates = own.markers.get("ultimates_cast", 0)
    enemy_ultimates = enemy.markers.get("ultimates_cast", 0)
    own_meter_edge = own.ultimate_meter - enemy.ultimate_meter
    race_kind = "hybrid"
    if killable or own_kill_pressure >= enemy_kill_pressure * 1.18:
        race_kind = "ko"
    elif own_ultimates > enemy_ultimates or (own_ultimates == enemy_ultimates and own_meter_edge >= 2):
        race_kind = "ultimate"
    elif enemy_ultimates >= max(1, ULTIMATE_WIN_COUNT - 1) and enemy.ultimate_meter >= max(4, ULTIMATE_METER_MAX - 2):
        race_kind = "deny_ultimate"

    plan_kind = "tempo"
    if own.ultimate_meter >= ULTIMATE_METER_MAX and (killable or (vulnerable is not None and vulnerable.hp / max(1, vulnerable.max_hp) <= 0.35)):
        plan_kind = "ultimate"
    elif killable:
        plan_kind = "kill"
    elif vulnerable is not None and vulnerable.hp / max(1, vulnerable.max_hp) <= 0.35:
        plan_kind = "stabilize"
    elif pivot_needed:
        plan_kind = "pivot"
    else:
        roles = set()
        for ally in own.alive():
            roles.update(ADVENTURER_AI[ally.defn.id].role_tags)
        if {"root_enabler", "shock_engine", "expose_enabler", "burn_enabler"} & roles:
            plan_kind = "setup"
    return RoundAnalysis(
        plan_kind=plan_kind,
        race_kind=race_kind,
        priority_target_ref=priority_target_ref,
        killable_enemy_refs=tuple(killable),
        vulnerable_ally_ref=_unit_ref(battle, vulnerable) if vulnerable is not None else None,
        fallback_front_ref=fallback_ref,
        pivot_needed=pivot_needed,
    )


def available_action_specs(battle, actor, *, bonus: bool = False) -> list[ActionSpec]:
    if actor.ko:
        return []
    specs: list[ActionSpec] = []
    team = team_for_actor(battle, actor)
    if bonus:
        if actor.defn.id == "wayward_humbert":
            if actor.defn.id != "ashen_ella":
                specs.append(ActionSpec(kind="switch", bonus=True))
        if actor.class_skill.id == "covert" or actor.defn.id == "the_green_knight" or _team_bonus_swap_available(team):
            for ally in _allies(actor, battle):
                specs.append(ActionSpec(kind="swap", target_ref=_unit_ref(battle, ally), bonus=True))
        if actor.markers.get("vanguard_ready", 0) > 0:
            specs.append(ActionSpec(kind="vanguard", bonus=True))
        if actor.markers.get("spell_bonus_rounds", 0) > 0 and team.ultimate_meter >= ULTIMATE_METER_MAX:
            effect = actor.defn.ultimate
            targets = get_legal_targets(battle, actor, effect=effect)
            if effect.target in {"none", "self"}:
                specs.append(ActionSpec(kind="ultimate", effect_id=effect.id, bonus=True))
            else:
                for target in targets:
                    specs.append(ActionSpec(kind="ultimate", effect_id=effect.id, target_ref=_unit_ref(battle, target), bonus=True))
        for effect in _active_spells_for_phase(actor, bonus=True):
            targets = get_legal_targets(battle, actor, effect=effect, weapon=actor.primary_weapon)
            if effect.target in {"none", "self"}:
                specs.append(ActionSpec(kind="spell", effect_id=effect.id, bonus=True))
            else:
                for target in targets:
                    specs.append(ActionSpec(kind="spell", effect_id=effect.id, target_ref=_unit_ref(battle, target), bonus=True))
        specs.append(ActionSpec(kind="skip", bonus=True))
        return specs

    strike_targets = get_legal_targets(battle, actor, effect=actor.primary_weapon.strike, weapon=actor.primary_weapon)
    for target in strike_targets:
        specs.append(ActionSpec(kind="strike", target_ref=_unit_ref(battle, target)))
    team_meter = team.ultimate_meter
    if team_meter >= ULTIMATE_METER_MAX:
        effect = actor.defn.ultimate
        targets = get_legal_targets(battle, actor, effect=effect)
        if effect.target in {"none", "self"}:
            specs.append(ActionSpec(kind="ultimate", effect_id=effect.id))
        else:
            for target in targets:
                specs.append(ActionSpec(kind="ultimate", effect_id=effect.id, target_ref=_unit_ref(battle, target)))
    for effect in _active_spells_for_phase(actor, bonus=False):
        targets = get_legal_targets(battle, actor, effect=effect, weapon=actor.primary_weapon)
        if effect.target in {"none", "self"}:
            specs.append(ActionSpec(kind="spell", effect_id=effect.id))
        else:
            for target in targets:
                specs.append(ActionSpec(kind="spell", effect_id=effect.id, target_ref=_unit_ref(battle, target)))
    if actor.defn.id != "ashen_ella":
        specs.append(ActionSpec(kind="switch"))
    for ally in _allies(actor, battle):
        specs.append(ActionSpec(kind="swap", target_ref=_unit_ref(battle, ally)))
    specs.append(ActionSpec(kind="skip"))
    return specs


def _effect_by_id(actor, effect_id: str):
    if effect_id == actor.defn.ultimate.id:
        return actor.defn.ultimate
    for effect in actor.active_spells():
        if effect.id == effect_id:
            return effect
    bonus_effect = actor.markers.get("artifact_bonus_spell_effect")
    if bonus_effect is not None and actor.markers.get("artifact_bonus_spell_rounds", 0) > 0 and bonus_effect.id == effect_id:
        return bonus_effect
    raise KeyError(f"{actor.name} cannot access effect {effect_id}.")


def _queue_spec(actor, battle, spec: ActionSpec):
    target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
    if spec.kind == "strike":
        if spec.bonus:
            queue_bonus_action(actor, {"type": "strike", "target": target})
        else:
            queue_strike(actor, target)
        return
    if spec.kind == "spell":
        effect = _effect_by_id(actor, spec.effect_id)
        if spec.bonus:
            queue_bonus_action(actor, {"type": "spell", "effect": effect, "target": target})
        else:
            queue_spell(actor, effect, target)
        return
    if spec.kind == "ultimate":
        effect = actor.defn.ultimate
        if spec.bonus:
            queue_bonus_action(actor, {"type": "ultimate", "effect": effect, "target": target})
        else:
            queue_ultimate(actor, target)
        return
    if spec.kind == "switch":
        if spec.bonus:
            queue_bonus_action(actor, {"type": "switch"})
        else:
            queue_switch(actor)
        return
    if spec.kind == "swap":
        if spec.bonus:
            queue_bonus_action(actor, {"type": "swap", "target": target})
        else:
            queue_swap(actor, target)
        return
    if spec.kind == "vanguard":
        queue_bonus_action(actor, {"type": "vanguard"})
        return
    if spec.bonus:
        queue_bonus_action(actor, {"type": "skip"})
    else:
        queue_skip(actor)


def _team_units_in_order(battle, team_num: int) -> list:
    if not battle.initiative_order:
        determine_initiative_order(battle)
    ordered = []
    for unit in battle.initiative_order:
        if unit.ko:
            continue
        if player_num_for_actor(battle, unit) == team_num and not any(existing is unit for existing in ordered):
            ordered.append(unit)
    return ordered


def _evaluate_status_block(unit) -> int:
    value = 0
    for status in unit.statuses:
        weight = STATUS_WEIGHTS.get(status.kind, 0)
        value += weight * status.duration
    return value


def _reactive_artifact_ready(unit) -> bool:
    return (
        unit.artifact is not None
        and unit.artifact.reactive
        and unit.cooldowns.get(unit.artifact.spell.id, 0) <= 0
    )


def _marker_state_score(unit) -> float:
    value = 0.0
    if unit.markers.get("cant_act_rounds", 0) > 0:
        value -= 18.0
    if unit.markers.get("cant_strike_rounds", 0) > 0:
        value -= 7.0
    if unit.markers.get("untargetable_rounds", 0) > 0:
        value += 10.0
    if unit.markers.get("spell_bonus_rounds", 0) > 0:
        value += 6.0
    if unit.markers.get("next_spell_no_cooldown", 0) > 0:
        value += 4.0
    if unit.markers.get("vanguard_ready", 0) > 0:
        value += 5.0
    if unit.markers.get("mistform_ready", 0) > 0:
        value += 6.0
    if unit.markers.get("blood_diamond_ready", 0) > 0:
        value += 6.0
    if unit.markers.get("dazzle_redirect_ref") is not None:
        value += 7.0
    if unit.markers.get("jovial_shot_ready", 0) > 0:
        value += 8.0
    if unit.markers.get("vine_snare_ready", 0) > 0:
        value += 4.0
    if unit.markers.get("rabbit_hole_extra_rounds", 0) > 0:
        value += 7.0
    if unit.markers.get("tea_party_rounds", 0) > 0:
        value += 6.0
    return value


def _resource_state_score(unit) -> float:
    value = 0.0
    primary = unit.primary_weapon
    if primary.ammo > 0:
        ammo_left = unit.ammo_remaining.get(primary.id, primary.ammo)
        ammo_ratio = ammo_left / max(1, primary.ammo)
        if ammo_left <= 0:
            value -= 12.0
        else:
            value += ammo_ratio * 4.0
    ready_spells = sum(1 for effect in unit.active_spells() if unit.cooldowns.get(effect.id, 0) <= 0)
    value += ready_spells * 1.4
    if _reactive_artifact_ready(unit):
        value += 6.0 if "fragile" in ADVENTURER_AI[unit.defn.id].role_tags else 4.0
    return value


def _lethal_pressure_score(battle, team_num: int) -> float:
    own = battle.get_team(team_num)
    enemy = battle.get_enemy(team_num)
    enemy_team_num = 2 if team_num == 1 else 1
    value = 0.0
    for enemy_unit in enemy.alive():
        estimated = _estimate_team_damage_to_target(battle, team_num, enemy_unit)
        if estimated >= enemy_unit.hp:
            value += 28.0 + _threat_value(enemy_unit) * 0.18
            if enemy_unit.slot == SLOT_FRONT:
                value += 8.0
        elif estimated >= enemy_unit.hp * 0.7:
            value += 8.0
    for ally in own.alive():
        estimated = _estimate_team_damage_to_target(battle, enemy_team_num, ally)
        if estimated >= ally.hp:
            penalty = 30.0 + _threat_value(ally) * 0.12
            if "fragile" in ADVENTURER_AI[ally.defn.id].role_tags or ally.slot != SLOT_FRONT:
                penalty += 10.0
            value -= penalty
        elif estimated >= ally.hp * 0.7:
            value -= 10.0
    return value


def evaluate_battle_state(battle, team_num: int) -> float:
    own = battle.get_team(team_num)
    enemy = battle.get_enemy(team_num)
    value = 0.0
    value += (len(enemy.alive()) - len(own.alive())) * -180.0
    for unit in own.members:
        if unit.ko:
            value -= 60.0
            continue
        profile = ADVENTURER_AI[unit.defn.id]
        value += 80.0 * (unit.hp / max(1, unit.max_hp))
        value += profile.position_scores[unit.slot] * 0.12
        value += _evaluate_status_block(unit) * (-1.0 if unit.has_status("burn") or unit.has_status("root") or unit.has_status("shock") or unit.has_status("weaken") or unit.has_status("expose") or unit.has_status("spotlight") or unit.has_status("taunt") else 0.35)
        if unit.has_status("guard"):
            value += 12.0
        value += _marker_state_score(unit)
        value += _resource_state_score(unit)
    for unit in enemy.members:
        if unit.ko:
            value += 60.0
            continue
        profile = ADVENTURER_AI[unit.defn.id]
        value -= 80.0 * (unit.hp / max(1, unit.max_hp))
        value -= profile.position_scores[unit.slot] * 0.12
        value += _evaluate_status_block(unit) * 0.55
        if unit.has_status("guard"):
            value -= 10.0
        value -= _marker_state_score(unit)
        value -= _resource_state_score(unit)
    own_front = own.frontline()
    enemy_front = enemy.frontline()
    if own_front is not None:
        value += 15.0 + 10.0 * (own_front.hp / max(1, own_front.max_hp))
    else:
        value -= 25.0
    if enemy_front is not None:
        value -= 10.0 * (enemy_front.hp / max(1, enemy_front.max_hp))
    else:
        value += 15.0
    back_left = own.get_slot(SLOT_BACK_LEFT)
    if back_left is not None:
        value += ADVENTURER_AI[back_left.defn.id].position_scores[SLOT_BACK_LEFT] * 0.08
    meter_weight = 50.0 / ULTIMATE_METER_MAX
    value += own.ultimate_meter * meter_weight
    value -= enemy.ultimate_meter * meter_weight
    value += _lethal_pressure_score(battle, team_num)
    return value


def _simulate_spec_delta(battle, team_num: int, actor_ref: tuple[int, str], spec: ActionSpec) -> float:
    base_value = evaluate_battle_state(battle, team_num)
    sim = copy.deepcopy(battle)
    actor = _find_unit(sim, actor_ref)
    if actor is None or actor.ko:
        return -999.0
    materialized = _find_unit(sim, actor_ref)
    _queue_spec(materialized, sim, spec)
    action = materialized.queued_bonus_action if spec.bonus else materialized.queued_action
    resolve_action(materialized, action, sim, is_bonus=spec.bonus)
    delta = evaluate_battle_state(sim, team_num) - base_value
    real_actor = _find_unit(battle, actor_ref)
    target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
    effect = None
    if real_actor is not None:
        if spec.kind == "strike":
            effect = real_actor.primary_weapon.strike
        elif spec.kind == "spell" and spec.effect_id is not None:
            effect = _effect_by_id(real_actor, spec.effect_id)
        elif spec.kind == "ultimate":
            effect = real_actor.defn.ultimate
    if spec.kind == "skip":
        delta -= 3.0
    elif spec.kind == "switch":
        primary = actor.primary_weapon
        primary_stalled = actor.cooldowns.get(primary.strike.id, 0) > 0 or (
            primary.ammo > 0 and actor.ammo_remaining.get(primary.id, primary.ammo) <= 0
        )
        delta += 6.0 if primary_stalled else -0.5
    elif spec.kind == "swap" and target is not None and real_actor is not None:
        delta += max(0.0, 2.0 + _formation_delta(battle, real_actor, target))
        if real_actor.slot == SLOT_FRONT and target.slot != SLOT_FRONT:
            delta += 3.0
        if spec.target_ref == actor_ref:
            delta -= 4.0
    elif spec.kind in {"strike", "spell", "ultimate"} and target is not None and effect is not None and real_actor is not None:
        if effect.target == "enemy":
            rough = _rough_damage(battle, real_actor, target, effect, weapon=real_actor.primary_weapon)
            if rough >= target.hp:
                delta += 14.0
                if target.slot == SLOT_FRONT:
                    delta += 6.0
            elif rough >= target.hp * 0.6:
                delta += 6.0
            if target.hp <= max(55, int(target.max_hp * 0.28)):
                delta += 6.0
            if target.has_status("expose") or target.has_status("root") or target.has_status("shock") or target.has_status("spotlight"):
                delta += 3.0
        elif effect.target in {"ally", "self"}:
            resolved_target = target if effect.target == "ally" else real_actor
            if effect.heal > 0 and resolved_target is not None:
                hp_ratio = resolved_target.hp / max(1, resolved_target.max_hp)
                delta += effect.heal * (0.08 if hp_ratio > 0.5 else 0.16)
            if any(status.kind == "guard" for status in effect.target_statuses):
                delta += 8.0
            if effect.special == "dazzle" and resolved_target is not None:
                threatened = _estimate_team_damage_to_target(battle, 2 if team_num == 1 else 1, resolved_target)
                delta += 5.0
                if threatened >= resolved_target.hp * 0.6:
                    delta += 8.0
                elif threatened > 0:
                    delta += 4.0
            if effect.heal > 0 and any(
                resolved_target.has_status(kind)
                for kind in ("burn", "root", "shock", "weaken", "expose", "spotlight", "taunt")
            ):
                delta += 4.0
    return delta


def _formation_delta(battle, actor, target) -> float:
    if target is None or target.ko or team_for_actor(battle, actor) != team_for_actor(battle, target):
        return 0.0
    actor_profile = ADVENTURER_AI[actor.defn.id]
    target_profile = ADVENTURER_AI[target.defn.id]
    before = actor_profile.position_scores[actor.slot] + target_profile.position_scores[target.slot]
    after = actor_profile.position_scores[target.slot] + target_profile.position_scores[actor.slot]
    return (after - before) * 0.18


def _plan_bias(battle, actor, spec: ActionSpec, analysis: RoundAnalysis) -> float:
    bias = 0.0
    target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
    if analysis.plan_kind == "kill":
        if spec.kind == "ultimate":
            bias += 14.0
        if spec.kind in {"strike", "spell", "ultimate"} and spec.target_ref in analysis.killable_enemy_refs:
            bias += 10.0
        elif spec.kind in {"strike", "spell", "ultimate"} and spec.target_ref == analysis.priority_target_ref:
            bias += 6.0
    elif analysis.plan_kind == "stabilize":
        if spec.kind == "swap" and target is not None:
            bias += max(0.0, 4.0 + _formation_delta(battle, actor, target))
        if spec.kind == "spell" and spec.effect_id is not None:
            effect = _effect_by_id(actor, spec.effect_id)
            if effect.heal > 0 or any(status.kind == "guard" for status in effect.target_statuses):
                bias += 12.0
            if effect.special == "dazzle":
                bias += 11.0
        if spec.kind in {"strike", "spell", "ultimate"} and spec.target_ref == analysis.priority_target_ref:
            bias += 4.0
    elif analysis.plan_kind == "setup":
        if spec.kind == "switch":
            bias += 5.0
        if spec.kind == "spell" and spec.effect_id is not None:
            effect = _effect_by_id(actor, spec.effect_id)
            status_kinds = {status.kind for status in effect.target_statuses}
            if {"shock", "root", "expose", "spotlight", "taunt"} & status_kinds:
                bias += 9.0
        if spec.kind == "swap" and target is not None:
            bias += max(0.0, _formation_delta(battle, actor, target))
    elif analysis.plan_kind == "pivot":
        if spec.kind == "swap" and target is not None:
            bias += 10.0 + max(0.0, _formation_delta(battle, actor, target))
        if spec.kind == "switch":
            bias += 3.0
    elif analysis.plan_kind == "ultimate":
        if spec.kind == "ultimate":
            bias += 16.0
        elif spec.kind in {"strike", "spell"} and spec.target_ref == analysis.priority_target_ref:
            bias += 4.0
    else:
        if spec.kind == "switch":
            bias += 2.0
        if spec.kind == "vanguard":
            bias += 6.0
        if spec.kind == "spell" and spec.effect_id is not None:
            effect = _effect_by_id(actor, spec.effect_id)
            status_kinds = {status.kind for status in effect.target_statuses}
            if {"shock", "root", "expose", "spotlight"} & status_kinds:
                bias += 4.0

    if analysis.race_kind == "ko":
        if spec.kind in {"strike", "spell", "ultimate"} and spec.target_ref == analysis.priority_target_ref:
            bias += 3.0
        if spec.kind == "skip":
            bias -= 2.0
    elif analysis.race_kind == "ultimate":
        if spec.kind == "ultimate":
            bias += 6.0
        elif spec.kind == "spell":
            bias += 2.5
        elif spec.kind == "switch":
            bias += 1.5
    elif analysis.race_kind == "deny_ultimate":
        if spec.kind in {"strike", "spell", "ultimate"} and spec.target_ref == analysis.priority_target_ref:
            bias += 4.0
        if spec.kind == "swap" and target is not None:
            bias += max(0.0, 2.0 + _formation_delta(battle, actor, target))

    # March Hare's Cracked Stopwatch line is a key bonus-spell enabler; value it explicitly.
    if (
        spec.kind == "strike"
        and actor.defn.id == "march_hare"
        and actor.primary_weapon.id == "cracked_stopwatch"
        and target is not None
        and target.has_status("shock")
    ):
        bias += 12.0
    if spec.bonus and spec.kind == "spell" and actor.defn.id == "march_hare" and actor.markers.get("spell_bonus_rounds", 0) > 0:
        bias += 6.0

    bias += _character_specific_bias(battle, actor, spec, analysis)
    return bias


def _character_specific_bias(battle, actor, spec: ActionSpec, analysis: RoundAnalysis) -> float:
    bias = 0.0
    target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
    team = team_for_actor(battle, actor)
    enemy_team = battle.team1 if team is battle.team2 else battle.team2
    enemy_team_num = 2 if player_num_for_actor(battle, actor) == 1 else 1

    if actor.artifact is not None:
        if actor.artifact.id == "suspicious_eye" and spec.kind == "strike" and target is not None and target.slot == actor.slot:
            bias += 4.0
        if actor.artifact.id == "blood_diamond" and actor.markers.get("blood_diamond_ready", 0) > 0 and spec.kind == "strike":
            bias += 6.0
        if actor.artifact.id == "starskin_veil" and spec.kind == "spell" and spec.effect_id == "dazzle" and target is not None:
            threatened = _estimate_team_damage_to_target(battle, enemy_team_num, target)
            if threatened > 0:
                bias += 5.0
            if target.hp / max(1, target.max_hp) <= 0.6:
                bias += 4.0

    if actor.defn.id == "little_jack":
        if spec.kind == "spell" and spec.effect_id == "cloudburst":
            priority_target = _find_unit(battle, analysis.priority_target_ref) if analysis.priority_target_ref is not None else None
            legal_now = get_legal_targets(battle, actor, effect=actor.primary_weapon.strike, weapon=actor.primary_weapon)
            if priority_target is not None and priority_target not in legal_now:
                bias += 8.0
            elif analysis.plan_kind in {"kill", "ultimate"}:
                bias += 4.0
        if spec.kind == "strike" and actor.primary_weapon.id == "skyfall" and target is not None:
            if spec.target_ref == analysis.priority_target_ref:
                bias += 5.0
            if target.has_status("expose"):
                bias += 3.0
        if spec.kind == "strike" and actor.primary_weapon.id == "giants_harp" and target is not None:
            if target.get_stat("defense") >= 70:
                bias += 4.0

    if actor.defn.id == "red_blanchette":
        if spec.kind == "spell" and spec.effect_id == "blood_transfusion" and target is not None:
            if actor.hp <= actor.max_hp * 0.5 and target.hp > actor.hp:
                bias += 10.0
        if spec.kind == "ultimate" and actor.hp <= actor.max_hp * 0.65:
            bias += 6.0

    if actor.defn.id == "witch_hunter_gretel":
        if spec.kind == "strike" and actor.primary_weapon.id == "hot_mitts" and target is not None:
            if target.has_status("burn"):
                bias += 6.0
            else:
                bias += 4.0
        if spec.kind == "strike" and actor.primary_weapon.id == "crumb_shot":
            if team.markers.get("crumb_picked_round", 0) > 0:
                bias += 6.0
            else:
                bias += 2.5

    if actor.defn.id == "destitute_vasilisa":
        if spec.kind == "strike" and actor.primary_weapon.id == "guiding_doll" and target is not None:
            bias += 6.0
            if spec.target_ref == analysis.priority_target_ref:
                bias += 4.0
            ally_followups = 0
            for ally in team.alive():
                if ally is actor:
                    continue
                strike_targets = get_legal_targets(battle, ally, effect=ally.primary_weapon.strike, weapon=ally.primary_weapon)
                if target in strike_targets:
                    ally_followups += 1
            bias += min(6.0, ally_followups * 2.0)
        if spec.kind == "spell" and spec.effect_id is not None:
            effect = _effect_by_id(actor, spec.effect_id)
            if effect.target == "enemy":
                bias += 2.5
        if spec.kind == "ultimate":
            strike_allies = sum(1 for ally in team.alive() if ally is not actor)
            bias += 3.0 + strike_allies * 1.2

    if actor.defn.id == "ali_baba":
        if spec.kind == "spell" and spec.effect_id == "seal_the_cave" and target is not None:
            active_cooldowns = sum(1 for turns in target.cooldowns.values() if turns > 0)
            bias += 4.0 + min(6.0, active_cooldowns * 1.6)
            if target.artifact is not None:
                bias += 2.0
        if spec.kind == "strike" and actor.primary_weapon.id == "jar_of_oil" and target is not None and not target.has_status("burn"):
            bias += 4.0
        if spec.kind == "ultimate":
            ranged_enemies = 0
            for enemy in enemy_team.alive():
                if any(weapon.kind == "ranged" for weapon in enemy.defn.signature_weapons):
                    ranged_enemies += 1
            bias += ranged_enemies * 2.5

    if actor.defn.id == "maui_sunthief":
        if spec.kind == "strike" and actor.primary_weapon.id == "whale_jaw_hook" and target is not None and not target.has_status("expose"):
            bias += 3.0
        if spec.kind == "spell" and spec.effect_id == "swallow_the_sun":
            pressured_allies = sum(1 for ally in team.alive() if ally.hp / max(1, ally.max_hp) <= 0.65)
            bias += pressured_allies * 3.0
        if spec.kind == "ultimate":
            if actor.markers.get("conquer_death_used", 0) > 0:
                bias += 10.0
            if actor.hp / max(1, actor.max_hp) <= 0.45:
                bias += 5.0

    if actor.defn.id == "porcus_iii":
        if spec.kind == "spell" and spec.effect_id == "not_by_the_hair":
            threatened = _estimate_team_damage_to_target(battle, enemy_team_num, actor)
            if threatened >= actor.max_hp * 0.20 or actor.hp / max(1, actor.max_hp) <= 0.65:
                bias += 10.0
        if spec.kind == "strike" and actor.primary_weapon.id == "crafty_wall":
            threatened = _estimate_team_damage_to_target(battle, enemy_team_num, actor)
            if threatened >= actor.max_hp * 0.18:
                bias += 4.0

    if actor.defn.id == "kama_the_honeyed":
        if spec.kind == "strike" and actor.primary_weapon.id == "sugarcane_bow" and target is not None and not target.has_status("spotlight"):
            bias += 4.0
        if spec.kind == "strike" and actor.primary_weapon.id == "the_stinger" and target is not None and target.has_status("spotlight"):
            bias += 8.0
        if spec.kind == "spell" and spec.effect_id == "sukas_eyes":
            unlit = sum(1 for enemy in enemy_team.alive() if not enemy.has_status("spotlight"))
            bias += unlit * 2.5
        if spec.kind == "ultimate":
            ranged_allies = sum(1 for ally in team.alive() if ally.primary_weapon.kind == "ranged")
            bias += 2.0 + ranged_allies * 2.0

    if actor.defn.id == "hunold_the_piper":
        if spec.kind == "strike" and actor.primary_weapon.id == "lightning_rod" and target is not None and not target.has_status("shock"):
            bias += 3.0
        if spec.kind == "strike" and actor.primary_weapon.id == "golden_fiddle" and target is not None and target.has_status("shock"):
            bias += 8.0

    if actor.defn.id == "briar_rose":
        if spec.kind == "strike" and actor.primary_weapon.id == "thorn_snare":
            bias += min(6.0, len(enemy_team.alive()) * 1.5)
        if spec.kind == "spell" and spec.effect_id == "vine_snare":
            bias += 3.0

    if actor.defn.id == "sir_roland":
        if spec.kind == "spell" and spec.effect_id == "knights_challenge":
            if spec.target_ref == analysis.priority_target_ref:
                bias += 5.0
            if target is not None and target.slot == SLOT_FRONT:
                bias += 2.5

    if actor.defn.id == "lady_of_reflections":
        if spec.kind == "strike" and actor.primary_weapon.id == "lantern_of_avalon":
            if actor.slot == SLOT_FRONT and actor.hp / max(1, actor.max_hp) <= 0.65:
                bias += 5.0
            if analysis.plan_kind in {"pivot", "stabilize"}:
                bias += 3.0
        if spec.kind == "ultimate":
            fainted_allies = sum(1 for ally in team.members if ally.ko)
            if fainted_allies > 0:
                bias += 10.0

    if actor.defn.id == "robin_hooded_avenger":
        if spec.kind == "spell" and spec.effect_id == "spread_fortune":
            if actor.primary_weapon.id == "the_flock" and len(enemy_team.alive()) >= 2:
                bias += 7.0
        if spec.kind == "strike" and actor.primary_weapon.id == "kingmaker" and target is not None:
            if target.slot != SLOT_FRONT or target.has_status("spotlight"):
                bias += 7.0

    if actor.defn.id == "the_good_beast":
        if spec.kind == "spell" and spec.effect_id == "crystal_ball" and actor.markers.get("guest_last_attacker") is not None:
            bias += 6.0
        if spec.kind == "strike" and actor.primary_weapon.id == "dinner_bell" and target is not None:
            if target in team.alive() and target.hp / max(1, target.max_hp) <= 0.5:
                bias += 6.0

    if actor.defn.id == "rapunzel_the_golden":
        if spec.kind == "spell" and spec.effect_id == "lower_guard" and target is not None:
            if target.has_status("root") or spec.target_ref == analysis.priority_target_ref:
                bias += 8.0
        if spec.kind == "spell" and spec.effect_id == "sanctuary" and target is not None:
            if target.hp / max(1, target.max_hp) <= 0.55:
                bias += 8.0

    if actor.defn.id == "pinocchio_cursed_puppet":
        if spec.kind == "spell" and spec.effect_id == "bloodstain":
            malice = actor.markers.get("malice", 0)
            if malice < 3 and actor.hp / max(1, actor.max_hp) >= 0.55:
                bias += 8.0
            elif malice >= 5 and actor.hp / max(1, actor.max_hp) <= 0.4:
                bias -= 4.0

    if actor.defn.id == "rumpelstiltskin":
        if spec.kind == "spell" and spec.effect_id == "straw_to_gold" and target is not None:
            active_debuffs = sum(1 for debuff in target.debuffs if debuff.duration > 0)
            bias += active_debuffs * 2.5
        if spec.kind == "strike" and actor.primary_weapon.id == "spinning_wheel":
            bias += 2.0

    if actor.defn.id == "reynard_lupine_trickster":
        if spec.kind == "strike" and actor.primary_weapon.id == "foxfire_bow" and target is not None:
            if all(debuff.stat != "defense" or debuff.duration <= 0 for debuff in target.debuffs):
                bias += 4.5
            if spec.target_ref == analysis.priority_target_ref:
                bias += 2.0
        if spec.kind == "strike" and actor.primary_weapon.id == "fang" and target is not None:
            if any(debuff.duration > 0 for debuff in target.debuffs):
                bias += 5.0
        if spec.kind == "spell" and spec.effect_id == "silver_tongue" and spec.target_ref == analysis.priority_target_ref:
            bias += 5.0
        if spec.kind == "ultimate":
            bias += 6.0

    return bias


def _combo_metrics(battle, team_num: int, actors: list, combo: tuple[ActionSpec, ...], analysis: RoundAnalysis) -> dict[str, float]:
    offense = 0.0
    defense = 0.0
    setup = 0.0
    ultimate = 0.0
    focus = 0.0
    focused_enemy_targets: list[tuple[int, str]] = []
    for actor, spec in zip(actors, combo):
        target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
        effect = None
        if spec.kind in {"spell", "ultimate"} and spec.effect_id is not None:
            effect = _effect_by_id(actor, spec.effect_id)
        if spec.kind == "strike":
            offense += 2.4
        elif spec.kind == "ultimate":
            offense += 3.2
            ultimate += 4.0
        elif spec.kind == "spell":
            if effect is not None:
                status_kinds = {status.kind for status in effect.target_statuses}
                if effect.target == "enemy":
                    offense += 1.8
                    if effect.power > 0:
                        offense += 1.2
                if effect.heal > 0:
                    defense += 2.4
                if effect.target in {"ally", "self"} and ("guard" in status_kinds or effect.heal > 0):
                    defense += 1.6
                if status_kinds & {"burn", "root", "shock", "weaken", "expose", "spotlight", "taunt"}:
                    setup += 2.0
            else:
                setup += 1.0
        elif spec.kind == "swap":
            defense += 1.6
            setup += 1.0
        elif spec.kind == "switch":
            setup += 1.4
        elif spec.kind == "vanguard":
            offense += 1.6
        elif spec.kind == "skip":
            offense -= 0.8
            defense -= 0.8
        if spec.target_ref == analysis.priority_target_ref and spec.kind in {"strike", "spell", "ultimate"}:
            focus += 1.5
        if spec.target_ref is not None and spec.target_ref[0] != team_num and spec.kind in {"strike", "spell", "ultimate"}:
            focused_enemy_targets.append(spec.target_ref)
        if spec.target_ref is not None and spec.target_ref[0] == team_num:
            defense += 0.5
        if target is not None and target.hp <= max(40, int(target.max_hp * 0.28)):
            offense += 0.8
    if len(focused_enemy_targets) >= 2 and len(set(focused_enemy_targets)) == 1:
        focus += 2.0
    return {
        "offense": offense,
        "defense": defense,
        "setup": setup,
        "ultimate": ultimate,
        "focus": focus,
    }


def _profile_score(metrics: dict[str, float], profile: str) -> float:
    if profile == "aggressive":
        return metrics["offense"] * 1.25 + metrics["focus"] * 1.2 + metrics["ultimate"] * 0.35
    if profile == "defensive":
        return metrics["defense"] * 1.35 + metrics["setup"] * 0.3 - metrics["offense"] * 0.1
    if profile == "setup":
        return metrics["setup"] * 1.35 + metrics["focus"] * 0.45
    if profile == "ultimate":
        return metrics["ultimate"] * 1.5 + metrics["offense"] * 0.4
    return metrics["offense"] + metrics["defense"] + metrics["setup"] + metrics["focus"] + metrics["ultimate"]


def _profile_weights_for_plan(plan_kind: str) -> dict[str, float]:
    if plan_kind == "kill":
        return {"base": 0.30, "aggressive": 0.35, "setup": 0.10, "defensive": 0.05, "ultimate": 0.20}
    if plan_kind == "stabilize":
        return {"base": 0.30, "aggressive": 0.10, "setup": 0.15, "defensive": 0.35, "ultimate": 0.10}
    if plan_kind == "setup":
        return {"base": 0.28, "aggressive": 0.18, "setup": 0.36, "defensive": 0.10, "ultimate": 0.08}
    if plan_kind == "pivot":
        return {"base": 0.30, "aggressive": 0.15, "setup": 0.20, "defensive": 0.25, "ultimate": 0.10}
    if plan_kind == "ultimate":
        return {"base": 0.22, "aggressive": 0.20, "setup": 0.08, "defensive": 0.10, "ultimate": 0.40}
    return {"base": 0.30, "aggressive": 0.22, "setup": 0.20, "defensive": 0.18, "ultimate": 0.10}


def _race_profile_adjustment(analysis: RoundAnalysis, metrics: dict[str, float]) -> float:
    if analysis.race_kind == "ko":
        return _profile_score(metrics, "aggressive") * 0.12 + metrics["focus"] * 0.12
    if analysis.race_kind == "ultimate":
        return _profile_score(metrics, "ultimate") * 0.14 + metrics["setup"] * 0.05
    if analysis.race_kind == "deny_ultimate":
        return _profile_score(metrics, "aggressive") * 0.08 + _profile_score(metrics, "defensive") * 0.08
    return _profile_score(metrics, "setup") * 0.04


def _specs_signature(specs_by_ref: dict[tuple[int, str], ActionSpec]) -> tuple:
    return tuple(sorted((ref, spec) for ref, spec in specs_by_ref.items()))


def _top_local_specs(battle, actor, *, bonus: bool, difficulty: str, analysis: RoundAnalysis) -> list[ActionSpec]:
    actor_ref = _unit_ref(battle, actor)
    scored = []
    for spec in available_action_specs(battle, actor, bonus=bonus):
        score = _simulate_spec_delta(battle, player_num_for_actor(battle, actor), actor_ref, spec)
        score += _plan_bias(battle, actor, spec, analysis)
        scored.append((score, spec))
    scored.sort(key=lambda item: item[0], reverse=True)
    keep = LOCAL_KEEP.get(difficulty, 4)
    diverse: list[ActionSpec] = []
    seen_specs: set[ActionSpec] = set()
    for kind in ("ultimate", "spell", "swap", "switch", "strike", "vanguard", "skip"):
        best_of_kind = next((spec for _score, spec in scored if spec.kind == kind), None)
        if best_of_kind is not None and best_of_kind not in seen_specs:
            diverse.append(best_of_kind)
            seen_specs.add(best_of_kind)
    for _score, spec in scored:
        if spec in seen_specs:
            continue
        diverse.append(spec)
        seen_specs.add(spec)
        if len(diverse) >= keep + 1:
            break
    if not any(item.kind == "skip" for item in diverse):
        skip_spec = next((item[1] for item in scored if item[1].kind == "skip"), ActionSpec(kind="skip", bonus=bonus))
        diverse.append(skip_spec)
    return diverse[: max(keep, min(len(diverse), keep + 1))]


def _queue_team_plan(sim_battle, team_num: int, specs_by_ref: dict[tuple[int, str], ActionSpec], *, bonus: bool):
    for actor in _team_units_in_order(sim_battle, team_num):
        actor.queued_action = None
        actor.queued_bonus_action = None
        spec = specs_by_ref.get(_unit_ref(sim_battle, actor))
        if spec is None:
            spec = ActionSpec(kind="skip", bonus=bonus)
        _queue_spec(actor, sim_battle, spec)


def _rank_team_plan_candidates(
    battle,
    team_num: int,
    *,
    bonus: bool,
    difficulty: str,
) -> tuple[RoundAnalysis, list[tuple[float, dict[tuple[int, str], ActionSpec], dict[str, float]]]]:
    actors = _team_units_in_order(battle, team_num)
    analysis = analyze_round_state(battle, team_num)
    if not actors:
        return analysis, []
    per_actor_choices: list[tuple[tuple[int, str], list[ActionSpec]]] = []
    for actor in actors:
        per_actor_choices.append((_unit_ref(battle, actor), _top_local_specs(battle, actor, bonus=bonus, difficulty=difficulty, analysis=analysis)))
    keys = [item[0] for item in per_actor_choices]
    choice_lists = [item[1] for item in per_actor_choices]
    base_value = evaluate_battle_state(battle, team_num)
    candidate_sets: list[tuple[float, dict[tuple[int, str], ActionSpec], dict[str, float]]] = []
    for combo in product(*choice_lists):
        specs_by_ref = dict(zip(keys, combo))
        sim = copy.deepcopy(battle)
        _queue_team_plan(sim, team_num, specs_by_ref, bonus=bonus)
        if bonus:
            resolve_bonus_phase(sim)
        else:
            resolve_action_phase(sim)
        score = evaluate_battle_state(sim, team_num) - base_value
        metrics = _combo_metrics(battle, team_num, actors, combo, analysis)
        score += metrics["focus"] * 1.2
        score += metrics["ultimate"] * 0.25
        candidate_sets.append((score, specs_by_ref, metrics))
    candidate_sets.sort(key=lambda item: item[0], reverse=True)
    keep = TEAM_KEEP.get(difficulty, 24)
    return analysis, candidate_sets[:keep]


def _select_likely_plan_packages(
    candidates: list[tuple[float, dict[tuple[int, str], ActionSpec], dict[str, float]]],
    analysis: RoundAnalysis,
    difficulty: str,
) -> list[tuple[float, dict[tuple[int, str], ActionSpec]]]:
    if not candidates:
        return []
    weights = _profile_weights_for_plan(analysis.plan_kind)
    package_keep = min(OPPONENT_PACKAGE_KEEP.get(difficulty, 4), len(candidates))
    selected: list[tuple[float, dict[tuple[int, str], ActionSpec]]] = []
    seen_signatures: set[tuple] = set()

    def _pick_best_for_profile(profile: str) -> tuple[float, dict[tuple[int, str], ActionSpec]] | None:
        ranked = sorted(
            candidates,
            key=lambda item: item[0] + _profile_score(item[2], profile) * 0.8,
            reverse=True,
        )
        for score, specs_by_ref, _metrics in ranked:
            signature = _specs_signature(specs_by_ref)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            return score, specs_by_ref
        return None

    for profile in ("base", "aggressive", "defensive", "setup", "ultimate"):
        weight = weights.get(profile, 0.0)
        if weight <= 0.0:
            continue
        pick = _pick_best_for_profile("tempo" if profile == "base" else profile)
        if pick is None:
            continue
        _score, specs_by_ref = pick
        selected.append((weight, specs_by_ref))
        if len(selected) >= package_keep:
            break

    if not selected:
        selected = [(1.0, candidates[0][1])]

    total_weight = sum(weight for weight, _specs in selected)
    if total_weight <= 0:
        return [(1.0, selected[0][1])]
    return [(weight / total_weight, specs_by_ref) for weight, specs_by_ref in selected]


def _expected_enemy_reply_penalty(sim_battle, team_num: int, difficulty: str, rng: random.Random) -> float:
    _ = rng
    enemy_team = 2 if team_num == 1 else 1
    if difficulty in {"easy", "normal", "hard"}:
        predictor_difficulty = "normal"
    else:
        predictor_difficulty = "hard"
    analysis, enemy_candidates = _rank_team_plan_candidates(
        sim_battle,
        enemy_team,
        bonus=False,
        difficulty=predictor_difficulty,
    )
    packages = _select_likely_plan_packages(enemy_candidates, analysis, predictor_difficulty)
    if not packages:
        return 0.0
    base_value = evaluate_battle_state(sim_battle, team_num)
    expected_penalty = 0.0
    for weight, specs_by_ref in packages:
        reply_sim = copy.deepcopy(sim_battle)
        _queue_team_plan(reply_sim, enemy_team, specs_by_ref, bonus=False)
        resolve_action_phase(reply_sim)
        post_reply = evaluate_battle_state(reply_sim, team_num)
        expected_penalty += weight * max(0.0, base_value - post_reply)
    return expected_penalty


def choose_team_plan(
    battle,
    team_num: int,
    *,
    bonus: bool = False,
    difficulty: str = "hard",
    rng: random.Random | None = None,
    lookahead_depth: int = 0,
) -> dict[tuple[int, str], ActionSpec]:
    rng = rng or random.Random()
    analysis, ranked_candidates = _rank_team_plan_candidates(
        battle,
        team_num,
        bonus=bonus,
        difficulty=difficulty,
    )
    if not ranked_candidates:
        return {}

    trimmed = ranked_candidates
    rescored: list[tuple[float, dict[tuple[int, str], ActionSpec]]] = []
    deep_keep = min(DEEP_LOOKAHEAD_KEEP.get(difficulty, 3), len(trimmed))
    evaluate_replies = analysis.plan_kind in {"kill", "ultimate", "stabilize"}
    for index, (score, specs_by_ref, metrics) in enumerate(trimmed):
        deep_score = score
        if analysis.plan_kind in {"kill", "ultimate"}:
            deep_score += _profile_score(metrics, "aggressive") * 0.15
        elif analysis.plan_kind == "stabilize":
            deep_score += _profile_score(metrics, "defensive") * 0.18
        elif analysis.plan_kind in {"setup", "pivot"}:
            deep_score += _profile_score(metrics, "setup") * 0.16
        deep_score += _race_profile_adjustment(analysis, metrics)
        if evaluate_replies and index < deep_keep and not bonus and lookahead_depth <= 0:
            sim = copy.deepcopy(battle)
            _queue_team_plan(sim, team_num, specs_by_ref, bonus=False)
            resolve_action_phase(sim)
            if sim.winner is None:
                deep_score -= _expected_enemy_reply_penalty(sim, team_num, difficulty, rng) * 0.40
        rescored.append((deep_score, specs_by_ref))
    rescored.sort(key=lambda item: item[0], reverse=True)
    top_score = rescored[0][0]
    threshold = 6.0 if difficulty in {"easy", "normal"} else 4.0
    band = [item for item in rescored if top_score - item[0] <= threshold]
    if difficulty == "ranked" and len(band) > 1 and rng.random() < 0.8:
        return band[0][1]
    return rng.choice(band)[1]


def queue_team_plan(battle, team_num: int, *, bonus: bool = False, difficulty: str = "hard", rng: random.Random | None = None) -> dict[tuple[int, str], ActionSpec]:
    plan = choose_team_plan(battle, team_num, bonus=bonus, difficulty=difficulty, rng=rng)
    for actor in _team_units_in_order(battle, team_num):
        spec = plan.get(_unit_ref(battle, actor), ActionSpec(kind="skip", bonus=bonus))
        _queue_spec(actor, battle, spec)
    return plan


def queue_both_teams_for_phase(battle, *, bonus: bool = False, difficulty1: str = "hard", difficulty2: str = "hard", rng: random.Random | None = None):
    rng = rng or random.Random()
    plan1 = queue_team_plan(battle, 1, bonus=bonus, difficulty=difficulty1, rng=rng)
    plan2 = queue_team_plan(battle, 2, bonus=bonus, difficulty=difficulty2, rng=rng)
    return plan1, plan2
