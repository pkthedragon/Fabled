from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from itertools import product
from typing import Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_tags import ADVENTURER_AI
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
    "ranked": 5,
}


TEAM_KEEP = {
    "easy": 8,
    "normal": 16,
    "hard": 24,
    "ranked": 32,
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


def _rough_damage(actor, target, effect, *, weapon=None) -> int:
    if effect.power <= 0 or target is None or target.ko:
        return 0
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
    return max(1, int((power * (actor.get_stat("attack") / max(1, target.get_stat("defense")))) + 0.999))


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
    if actor.markers.get("spell_bonus_rounds", 0) <= 0:
        return []
    return [effect for effect in actor.active_spells() if _effect_usable(actor, effect)]


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


def _estimate_team_damage_to_target(battle, team_num: int, target) -> float:
    total = 0.0
    for actor in battle.get_team(team_num).alive():
        best = 0.0
        strike_targets = get_legal_targets(battle, actor, effect=actor.primary_weapon.strike, weapon=actor.primary_weapon)
        if target in strike_targets:
            best = max(best, _rough_damage(actor, target, actor.primary_weapon.strike, weapon=actor.primary_weapon))
        for effect in _active_spells_for_phase(actor, bonus=False):
            if effect.target != "enemy":
                continue
            if target in get_legal_targets(battle, actor, effect=effect, weapon=actor.primary_weapon):
                best = max(best, _rough_damage(actor, target, effect, weapon=actor.primary_weapon))
        if team_for_actor(battle, actor).ultimate_meter >= 10:
            effect = actor.defn.ultimate
            if effect.target == "enemy" and target in get_legal_targets(battle, actor, effect=effect):
                best = max(best, _rough_damage(actor, target, effect, weapon=actor.primary_weapon))
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
        if "healer" in ADVENTURER_AI[enemy_unit.defn.id].role_tags:
            collapse += 8
        priority = estimated * 0.35 + _threat_value(enemy_unit) + collapse
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
    plan_kind = "tempo"
    if own.ultimate_meter >= 10 and (killable or (vulnerable is not None and vulnerable.hp / max(1, vulnerable.max_hp) <= 0.35)):
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
        if actor.class_skill.id == "tactical" or actor.defn.id == "wayward_humbert":
            if actor.defn.id != "ashen_ella":
                specs.append(ActionSpec(kind="switch", bonus=True))
        if actor.class_skill.id == "covert" or actor.defn.id == "the_green_knight" or _team_bonus_swap_available(team):
            for ally in _allies(actor, battle):
                specs.append(ActionSpec(kind="swap", target_ref=_unit_ref(battle, ally), bonus=True))
        if actor.markers.get("vanguard_ready", 0) > 0:
            specs.append(ActionSpec(kind="vanguard", bonus=True))
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
    if team_meter >= 10:
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
        if player_num_for_actor(battle, unit) == team_num and unit not in ordered:
            ordered.append(unit)
    return ordered


def _evaluate_status_block(unit) -> int:
    value = 0
    for status in unit.statuses:
        weight = STATUS_WEIGHTS.get(status.kind, 0)
        value += weight * status.duration
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
        if unit.primary_weapon.ammo > 0 and unit.ammo_remaining.get(unit.primary_weapon.id, unit.primary_weapon.ammo) <= 0:
            value -= 10.0
        if unit.cooldowns.get(unit.primary_weapon.strike.id, 0) > 0:
            value -= 4.0
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
        if unit.primary_weapon.ammo > 0 and unit.ammo_remaining.get(unit.primary_weapon.id, unit.primary_weapon.ammo) <= 0:
            value += 10.0
        if unit.cooldowns.get(unit.primary_weapon.strike.id, 0) > 0:
            value += 4.0
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
    value += own.ultimate_meter * 5.0
    value -= enemy.ultimate_meter * 5.0
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
    if spec.kind == "skip":
        delta -= 3.0
    elif spec.kind == "switch":
        primary = actor.primary_weapon
        primary_stalled = actor.cooldowns.get(primary.strike.id, 0) > 0 or (
            primary.ammo > 0 and actor.ammo_remaining.get(primary.id, primary.ammo) <= 0
        )
        delta += 6.0 if primary_stalled else -0.5
    elif spec.kind in {"strike", "spell", "ultimate"} and spec.target_ref is not None:
        target = _find_unit(battle, spec.target_ref)
        if target is not None:
            if target.hp <= max(55, int(target.max_hp * 0.28)):
                delta += 6.0
            if target.has_status("expose") or target.has_status("root") or target.has_status("shock"):
                delta += 3.0
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
    return bias


def _top_local_specs(battle, actor, *, bonus: bool, difficulty: str, analysis: RoundAnalysis) -> list[ActionSpec]:
    actor_ref = _unit_ref(battle, actor)
    scored = []
    for spec in available_action_specs(battle, actor, bonus=bonus):
        score = _simulate_spec_delta(battle, player_num_for_actor(battle, actor), actor_ref, spec)
        score += _plan_bias(battle, actor, spec, analysis)
        scored.append((score, spec))
    scored.sort(key=lambda item: item[0], reverse=True)
    keep = LOCAL_KEEP.get(difficulty, 4)
    top = [item[1] for item in scored[:keep]]
    if not any(item.kind == "skip" for item in top):
        skip_spec = next((item[1] for item in scored if item[1].kind == "skip"), ActionSpec(kind="skip", bonus=bonus))
        top.append(skip_spec)
    return top


def _queue_team_plan(sim_battle, team_num: int, specs_by_ref: dict[tuple[int, str], ActionSpec], *, bonus: bool):
    for actor in _team_units_in_order(sim_battle, team_num):
        actor.queued_action = None
        actor.queued_bonus_action = None
        spec = specs_by_ref.get(_unit_ref(sim_battle, actor))
        if spec is None:
            spec = ActionSpec(kind="skip", bonus=bonus)
        _queue_spec(actor, sim_battle, spec)


def _estimate_enemy_reply_penalty(sim_battle, team_num: int, difficulty: str, rng: random.Random) -> float:
    enemy_team = 2 if team_num == 1 else 1
    reply_plan = choose_team_plan(sim_battle, enemy_team, bonus=False, difficulty="normal" if difficulty == "easy" else difficulty, rng=rng, lookahead_depth=1)
    reply_sim = copy.deepcopy(sim_battle)
    _queue_team_plan(reply_sim, enemy_team, reply_plan, bonus=False)
    resolve_action_phase(reply_sim)
    return max(0.0, evaluate_battle_state(sim_battle, team_num) - evaluate_battle_state(reply_sim, team_num))


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
    actors = _team_units_in_order(battle, team_num)
    if not actors:
        return {}
    analysis = analyze_round_state(battle, team_num)
    per_actor_choices: list[tuple[tuple[int, str], list[ActionSpec]]] = []
    for actor in actors:
        per_actor_choices.append((_unit_ref(battle, actor), _top_local_specs(battle, actor, bonus=bonus, difficulty=difficulty, analysis=analysis)))
    candidate_sets: list[tuple[float, dict[tuple[int, str], ActionSpec]]] = []
    keys = [item[0] for item in per_actor_choices]
    choice_lists = [item[1] for item in per_actor_choices]
    base_value = evaluate_battle_state(battle, team_num)
    for combo in product(*choice_lists):
        specs_by_ref = dict(zip(keys, combo))
        sim = copy.deepcopy(battle)
        _queue_team_plan(sim, team_num, specs_by_ref, bonus=bonus)
        if bonus:
            resolve_bonus_phase(sim)
        else:
            resolve_action_phase(sim)
        score = evaluate_battle_state(sim, team_num) - base_value
        if analysis.priority_target_ref is not None:
            focus_hits = sum(1 for spec in combo if spec.target_ref == analysis.priority_target_ref)
            score += focus_hits * 2.0
        focus_targets = [spec.target_ref for spec in combo if spec.target_ref is not None and spec.target_ref[0] != team_num]
        if len(focus_targets) >= 2 and len(set(focus_targets)) == 1:
            score += 6.0
        candidate_sets.append((score, specs_by_ref))
    candidate_sets.sort(key=lambda item: item[0], reverse=True)
    keep = TEAM_KEEP.get(difficulty, 24)
    trimmed = candidate_sets[:keep]
    rescored: list[tuple[float, dict[tuple[int, str], ActionSpec]]] = []
    deep_keep = min(8, len(trimmed))
    for index, (score, specs_by_ref) in enumerate(trimmed):
        deep_score = score
        if index < deep_keep and not bonus and lookahead_depth <= 0:
            sim = copy.deepcopy(battle)
            _queue_team_plan(sim, team_num, specs_by_ref, bonus=False)
            resolve_action_phase(sim)
            if sim.winner is None:
                deep_score -= _estimate_enemy_reply_penalty(sim, team_num, difficulty, rng) * 0.35
        rescored.append((deep_score, specs_by_ref))
    rescored.sort(key=lambda item: item[0], reverse=True)
    top_score = rescored[0][0]
    threshold = 5.0 if difficulty in {"easy", "normal"} else 3.0
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
