from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from itertools import product
from typing import Optional

from quest_enemy_runtime import QUEST_ENEMY_META_BY_ID
from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_tags import ADVENTURER_AI, AdventurerAIProfile
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



DISRUPTIVE_EFFECT_SPECIALS = {
    "artifact_swap_with_ally",
    "cant_strike_next_turn",
    "midnight_waltz",
    "self_swap_after_strike",
    "swap_target_with_enemy",
    "trojan_horse",
    "zephyr",
}

SELF_PROTECTION_INVALIDATING_SPECIALS = {
    "crowstorm",
}

SELF_PROTECTION_DISRUPTION_SPECIALS = {
    "crowstorm",
    "time_stop",
}

SELF_PROTECTION_STRIKE_SOFT_SPECIALS = {
    "mistform",
}


INVALID_PLAN_LOG_WEIGHTS: tuple[tuple[str, float], ...] = (
    (" queued Strike failed because ", 34.0),
    (" queued Swap failed because ", 24.0),
    (" cannot Strike right now because ", 34.0),
    (" cannot Strike right now.", 34.0),
    (" is on cooldown.", 30.0),
    (" is out of ammo.", 30.0),
    (" has no legal Strike on that target.", 26.0),
    (" cannot Swap.", 22.0),
    (" is Rooted and cannot Swap.", 22.0),
    (" cannot Swap while Polymorphed.", 22.0),
    (" has no legal target.", 20.0),
    (" cannot cast Spells from the backline.", 22.0),
)


@dataclass(frozen=True)
class ActionSpec:
    kind: str
    target_ref: Optional[tuple[int, str]] = None
    effect_id: Optional[str] = None
    weapon_id: Optional[str] = None
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


def _ref_slot(battle, ref: tuple[int, str] | None) -> Optional[str]:
    if ref is None:
        return None
    unit = _find_unit(battle, ref)
    return None if unit is None or unit.ko else unit.slot


def _same_target_slot(battle, left_ref: tuple[int, str] | None, right_ref: tuple[int, str] | None) -> bool:
    if left_ref is None or right_ref is None:
        return False
    if left_ref[0] != right_ref[0]:
        return False
    left_slot = _ref_slot(battle, left_ref)
    right_slot = _ref_slot(battle, right_ref)
    return left_slot is not None and left_slot == right_slot


def _ref_matches_any_slot(
    battle,
    ref: tuple[int, str] | None,
    refs: tuple[tuple[int, str], ...] | list[tuple[int, str]],
) -> bool:
    return any(_same_target_slot(battle, ref, other_ref) for other_ref in refs)


def _unit_ref(battle, unit) -> tuple[int, str]:
    return (player_num_for_actor(battle, unit), unit.defn.id)


def _find_unit(battle, ref: tuple[int, str]):
    team = battle.team1 if ref[0] == 1 else battle.team2
    return next((unit for unit in team.members if unit.defn.id == ref[1]), None)


def _all_unit_effects(unit) -> list:
    effects = []
    for weapon in unit.active_strike_weapons():
        effects.append(weapon.strike)
        effects.extend(weapon.spells)
    if getattr(unit.defn, "ultimate", None) is not None:
        effects.append(unit.defn.ultimate)
    if unit.artifact is not None:
        if unit.artifact.active_spell is not None:
            effects.append(unit.artifact.active_spell)
        if unit.artifact.reactive_effect is not None:
            effects.append(unit.artifact.reactive_effect)
    return effects


def _profile_for(unit) -> AdventurerAIProfile:
    profile = ADVENTURER_AI.get(unit.defn.id)
    if profile is not None:
        return profile
    meta = QUEST_ENEMY_META_BY_ID.get(unit.defn.id, {})
    weapons = unit.active_strike_weapons()
    effects = _all_unit_effects(unit)
    role_tags: set[str] = set()
    if any(effect.heal > 0 for effect in effects) or unit.class_skill.id in {"healer", "medic", "saint", "oracle"}:
        role_tags.add("healer")
    if any(status.kind == "guard" for effect in effects for status in effect.target_statuses):
        role_tags.add("guard_support")
    if any(status.kind == "shock" for effect in effects for status in effect.target_statuses):
        role_tags.add("shock_engine")
    if any(status.kind == "root" for effect in effects for status in effect.target_statuses):
        role_tags.add("root_enabler")
    if any(status.kind == "expose" for effect in effects for status in effect.target_statuses):
        role_tags.add("expose_enabler")
    if any(status.kind == "burn" for effect in effects for status in effect.target_statuses):
        role_tags.add("burn_enabler")
    if any(weapon.kind == "magic" for weapon in weapons) or any(effect.target in {"ally", "self"} or effect.cooldown > 0 for effect in effects):
        role_tags.add("spell_loop")
    if any(weapon.kind == "melee" for weapon in weapons):
        role_tags.add("frontline_ready")
    if any(weapon.kind != "melee" or weapon.strike.spread or weapon.strike.ignore_targeting for weapon in weapons):
        role_tags.add("tempo_engine")
    if max((weapon.strike.power for weapon in weapons), default=0) >= 110:
        role_tags.add("burst_finisher")
    if unit.defn.hp <= 300 and unit.defn.defense <= 65:
        role_tags.add("fragile")
    front_score = int(meta.get("frontline_score") or (45 + unit.defn.defense * 2 + unit.defn.hp // 6 + (18 if any(weapon.kind == "melee" for weapon in weapons) else 0)))
    back_score = int(meta.get("backline_score") or (45 + unit.defn.speed * 2 + (22 if any(weapon.kind in {"ranged", "magic"} for weapon in weapons) else 0) - (12 if all(weapon.kind == "melee" for weapon in weapons) else 0)))
    return AdventurerAIProfile(
        base_power=max((weapon.strike.power for weapon in weapons), default=70) + int(unit.defn.attack * 0.2),
        reliability=70,
        complexity=55,
        role_tags=tuple(sorted(role_tags)),
        shell_tags=(),
        matchup_tags=(),
        good_into=(),
        bad_into=(),
        preferred_classes=(),
        preferred_skills={},
        preferred_weapons=tuple(weapon.id for weapon in weapons),
        preferred_artifacts=((unit.artifact.id,) if unit.artifact is not None else ()),
        position_scores={
            SLOT_FRONT: front_score,
            SLOT_BACK_LEFT: back_score,
            SLOT_BACK_RIGHT: back_score,
        },
    )


def _strike_weapon_for_spec(actor, spec: ActionSpec):
    return actor.strike_weapon_by_id(spec.weapon_id)


def _weapon_for_effect(actor, effect):
    if effect is None:
        return actor.primary_weapon
    return actor.weapon_for_effect(getattr(effect, "id", None)) or actor.primary_weapon


def _team_bonus_swap_available(team) -> bool:
    return team.markers.get("bonus_swap_rounds", 0) > 0 and team.markers.get("bonus_swap_used", 0) <= 0


def _rough_damage(battle, actor, target, effect, *, weapon=None) -> int:
    if effect.power <= 0 or target is None or target.ko:
        return 0
    weapon = weapon or _weapon_for_effect(actor, effect)
    attack_stat = "attack"
    if actor.defn.id == "maui_sunthief" and weapon is not None and weapon.id == "ancestral_warclub":
        attack_stat = "defense"
    power = effect.power
    if weapon is not None:
        if weapon.kind == "melee" and actor.class_skill.id == "martial":
            power += 25
        elif weapon.kind == "ranged" and actor.class_skill.id == "deadeye":
            power += 5
        if actor.defn.id == "odysseus_the_nobody" and weapon.id == "olivewood_spear" and target.slot == actor.slot:
            power += 50
    if actor.has_status("weaken"):
        power = int((power * 0.85) + 0.999)
    actor_team = team_for_actor(battle, actor)
    target_team = battle.team1 if actor_team is battle.team2 else battle.team2
    if weapon is not None and target_team.frontline() is not None:
        enemy_front = target_team.frontline()
        if enemy_front.defn.id == "scheherazade_dawns_ransom" and enemy_front.primary_weapon.id == "tome_of_ancients":
            power = max(0, power - 25)
    if target.has_status("guard") and actor.defn.id != "robin_hooded_avenger":
        power = int((power * 0.85) + 0.999)
    if target.has_status("expose"):
        power = int((power * 1.15) + 0.999)
    damage = max(1, int((power * (actor.get_stat(attack_stat) / max(1, target.get_stat("defense")))) + 0.999))
    if target.markers.get("bargain_rounds", 0) > 0 and weapon is not None:
        damage += 25
    if target.has_status("root") and target.markers.get("silken_prose_rounds", 0) > 0 and weapon is not None:
        damage += 8
    if actor_team is not target_team:
        if any(ally.defn.id == "kama_the_honeyed" and ally is not actor and ally.slot == target.slot for ally in actor_team.alive()):
            damage += 25
    return damage


def _effect_usable(actor, effect) -> bool:
    if effect.special == "time_stop" and actor.markers.get("time_stop_used", 0) > 0:
        return False
    if actor.cooldowns.get(effect.id, 0) > 0:
        return False
    source_weapon = _weapon_for_effect(actor, effect)
    if source_weapon is not None and any(spell.id == effect.id for spell in source_weapon.spells) and source_weapon.ammo > 0:
        ammo_left = actor.ammo_remaining.get(source_weapon.id, source_weapon.ammo)
        if ammo_left < effect.ammo_cost:
            return False
    return True


def _failure_weight_for_line(line: str) -> float:
    for fragment, weight in INVALID_PLAN_LOG_WEIGHTS:
        if fragment in line:
            return weight
    if " failed because " in line:
        return 20.0
    if " cannot access " in line:
        return 20.0
    return 0.0


def _enemy_team_for_actor(battle, actor):
    actor_team = team_for_actor(battle, actor)
    return battle.team1 if actor_team is battle.team2 else battle.team2


def _fated_duel_blocks(actor, battle) -> bool:
    active_lanes = battle.markers.get("fated_duel_lanes", {})
    return bool(active_lanes) and actor.slot not in active_lanes


def _has_seal_the_cave_cooldown(actor) -> bool:
    tracked = actor.markers.get("sealed_cave_effects")
    if not isinstance(tracked, set):
        return False
    return any(actor.cooldowns.get(effect_id, 0) > 0 for effect_id in tracked)


def _actor_forced_to_skip(actor, battle) -> bool:
    return actor.ko or actor.markers.get("cant_act_rounds", 0) > 0 or _fated_duel_blocks(actor, battle)


def _can_attempt_strike(actor, weapon=None) -> bool:
    weapon = weapon or actor.primary_weapon
    if actor.markers.get("cant_strike_rounds", 0) > 0:
        return False
    if actor.cooldowns.get(weapon.strike.id, 0) > 0:
        return False
    if weapon.ammo > 0 and actor.ammo_remaining.get(weapon.id, weapon.ammo) <= 0:
        return False
    return True


def _can_cast_effect(battle, actor, effect) -> bool:
    if actor.defn.id == "ashen_ella" and actor.slot != SLOT_FRONT:
        return False
    if effect.id == actor.defn.ultimate.id:
        return True
    if effect not in actor.active_spells():
        bonus_effect = actor.markers.get("artifact_bonus_spell_effect")
        if not (
            actor.markers.get("artifact_bonus_spell_rounds", 0) > 0
            and bonus_effect is not None
            and bonus_effect.id == effect.id
        ):
            return False
    if not _effect_usable(actor, effect):
        return False
    if (
        actor.artifact is not None
        and actor.artifact.active_spell is not None
        and effect.id == actor.artifact.active_spell.id
        and (actor.has_status("burn") or _has_seal_the_cave_cooldown(actor))
    ):
        enemy_team = _enemy_team_for_actor(battle, actor)
        if any(enemy.defn.id == "ali_baba" and enemy.primary_weapon.id == "jar_of_oil" for enemy in enemy_team.alive()):
            return False
    return True


def _can_switch(actor, *, bonus: bool) -> bool:
    if actor.defn.id == "ashen_ella" or actor.dual_primary_weapons_active():
        return False
    if actor.primary_weapon.id == actor.secondary_weapon.id:
        return False
    if not bonus:
        return True
    return actor.defn.id == "wayward_humbert" or actor.markers.get("bonus_switch_rounds", 0) > 0


def _can_swap(battle, actor, target, *, bonus: bool) -> bool:
    if target is None or target is actor or target.ko:
        return False
    if team_for_actor(battle, target) != team_for_actor(battle, actor):
        return False
    if actor.has_status("root"):
        return False
    if actor.markers.get("polymorph_rounds", 0) > 0 or target.markers.get("polymorph_rounds", 0) > 0:
        return False
    # Only one Swap action may be selected per round per team
    if team_for_actor(battle, actor).markers.get("swap_action_selected", 0) > 0:
        return False
    if not bonus:
        return True
    if actor.class_skill.id == "covert":
        intrinsic_bonus_swap = actor.markers.get("spells_cast_this_round", 0) > 0
    else:
        intrinsic_bonus_swap = actor.defn.id == "the_green_knight"
    return intrinsic_bonus_swap or _team_bonus_swap_available(team_for_actor(battle, actor))


def _legal_targets_for_spec(battle, actor, spec: ActionSpec):
    if spec.kind == "strike":
        weapon = _strike_weapon_for_spec(actor, spec)
        return get_legal_targets(battle, actor, effect=weapon.strike, weapon=weapon)
    if spec.kind == "ultimate":
        return get_legal_targets(battle, actor, effect=actor.defn.ultimate)
    if spec.kind == "spell" and spec.effect_id is not None:
        try:
            effect = _effect_by_id(actor, spec.effect_id)
        except KeyError:
            return []
        return get_legal_targets(battle, actor, effect=effect, weapon=_weapon_for_effect(actor, effect))
    return []


def _spec_effect(actor, spec: ActionSpec):
    if spec.kind == "strike":
        return _strike_weapon_for_spec(actor, spec).strike
    if spec.kind == "spell" and spec.effect_id is not None:
        try:
            return _effect_by_id(actor, spec.effect_id)
        except KeyError:
            return None
    if spec.kind == "ultimate":
        return actor.defn.ultimate
    return None


def _spec_is_legal(battle, actor, spec: ActionSpec) -> bool:
    if actor is None or actor.ko:
        return False
    if spec.kind == "skip":
        return True
    if _actor_forced_to_skip(actor, battle):
        return False
    if spec.kind == "switch":
        return _can_switch(actor, bonus=spec.bonus)
    if spec.kind == "swap":
        target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
        return _can_swap(battle, actor, target, bonus=spec.bonus)
    if spec.kind == "strike":
        if not _can_attempt_strike(actor, _strike_weapon_for_spec(actor, spec)):
            return False
        target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
        return any(candidate is target for candidate in _legal_targets_for_spec(battle, actor, spec))
    if spec.kind == "ultimate":
        team = team_for_actor(battle, actor)
        if team.ultimate_meter < ULTIMATE_METER_MAX:
            return False
        if spec.bonus:
            return False
        effect = actor.defn.ultimate
        if effect.target in {"none", "self"}:
            return True
        target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
        return any(candidate is target for candidate in _legal_targets_for_spec(battle, actor, spec))
    if spec.kind == "spell":
        if spec.effect_id is None:
            return False
        try:
            effect = _effect_by_id(actor, spec.effect_id)
        except KeyError:
            return False
        if spec.bonus:
            bonus_effect = actor.markers.get("artifact_bonus_spell_effect")
            has_artifact_bonus = (
                actor.markers.get("artifact_bonus_spell_rounds", 0) > 0
                and bonus_effect is not None
                and bonus_effect.id == effect.id
            )
            if not has_artifact_bonus:
                return False
        if not _can_cast_effect(battle, actor, effect):
            return False
        if effect.target in {"none", "self"}:
            return True
        target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
        return any(candidate is target for candidate in _legal_targets_for_spec(battle, actor, spec))
    return False


def _sanitize_spec(battle, actor, spec: ActionSpec | None, *, bonus: bool) -> ActionSpec:
    if spec is not None and _spec_is_legal(battle, actor, spec):
        return spec
    for candidate in available_action_specs(battle, actor, bonus=bonus):
        if _spec_is_legal(battle, actor, candidate):
            return candidate
    return ActionSpec(kind="skip", bonus=bonus)


def _active_spells_for_phase(actor, *, bonus: bool) -> list:
    if not bonus:
        return [effect for effect in actor.active_spells() if _effect_usable(actor, effect)]
    effects = []
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
    profile = _profile_for(unit)
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


def _runtime_threat_bonus(battle, enemy_unit, own_team_num: int) -> float:
    """Dynamic threat bonus based on current combat leverage, not just static role tags."""
    bonus = 0.0
    # Enemy snowballing via attack/speed buffs
    if any(buff.stat in {"attack", "speed"} and buff.duration > 0 for buff in enemy_unit.buffs):
        bonus += 4.0
    # Active power multiplier markers
    if enemy_unit.markers.get("jovial_shot_ready", 0) > 0:
        bonus += 6.0
    if enemy_unit.markers.get("rabbit_hole_extra_rounds", 0) > 0:
        bonus += 6.0
    # Enemy has applied combo-enabling statuses to our team
    own_team = battle.get_team(own_team_num)
    combo_count = sum(
        1 for ally in own_team.alive()
        if ally.has_status("expose") or ally.has_status("shock") or ally.has_status("spotlight")
    )
    if combo_count >= 2:
        bonus += 5.0
    elif combo_count == 1:
        bonus += 2.0
    # Reactive artifact ready — approaching them is costly
    if _reactive_artifact_ready(enemy_unit):
        bonus += 4.0
    if enemy_unit.markers.get("dazzle_redirect_ref") is not None:
        bonus += 3.0
    return bonus


def _access_count(battle, team_num: int, target) -> int:
    count = 0
    if target is None or target.ko:
        return 0
    for actor in battle.get_team(team_num).alive():
        if any(
            target in get_legal_targets(battle, actor, effect=weapon.strike, weapon=weapon)
            for weapon in actor.active_strike_weapons()
            if _can_attempt_strike(actor, weapon)
        ):
            count += 1
            continue
        for effect in _active_spells_for_phase(actor, bonus=False):
            if effect.target != "enemy":
                continue
            if target in get_legal_targets(battle, actor, effect=effect, weapon=_weapon_for_effect(actor, effect)):
                count += 1
                break
    return count


def _estimate_team_damage_to_target(battle, team_num: int, target) -> float:
    total = 0.0
    for actor in battle.get_team(team_num).alive():
        best = 0.0
        for weapon in actor.active_strike_weapons():
            if not _can_attempt_strike(actor, weapon):
                continue
            strike_targets = get_legal_targets(battle, actor, effect=weapon.strike, weapon=weapon)
            if target in strike_targets:
                best = max(best, _rough_damage(battle, actor, target, weapon.strike, weapon=weapon))
        for effect in _active_spells_for_phase(actor, bonus=False):
            if effect.target != "enemy":
                continue
            spell_weapon = _weapon_for_effect(actor, effect)
            if target in get_legal_targets(battle, actor, effect=effect, weapon=spell_weapon):
                best = max(best, _rough_damage(battle, actor, target, effect, weapon=spell_weapon))
        if team_for_actor(battle, actor).ultimate_meter >= ULTIMATE_METER_MAX:
            effect = actor.defn.ultimate
            if effect.target == "enemy" and target in get_legal_targets(battle, actor, effect=effect):
                best = max(best, _rough_damage(battle, actor, target, effect, weapon=_weapon_for_effect(actor, effect)))
        total += best
    return total


def _estimate_window_damage_to_target(
    battle,
    start_index: int,
    end_index: int,
    team_num: int,
    target,
) -> float:
    if target is None or target.ko:
        return 0.0
    total = 0.0
    start_index = max(0, start_index)
    end_index = min(end_index, len(battle.initiative_order))
    for attacker in battle.initiative_order[start_index:end_index]:
        if attacker.ko or player_num_for_actor(battle, attacker) != team_num:
            continue
        best = 0.0
        for weapon in attacker.active_strike_weapons():
            if not _can_attempt_strike(attacker, weapon):
                continue
            strike_targets = get_legal_targets(battle, attacker, effect=weapon.strike, weapon=weapon)
            if target in strike_targets:
                best = max(best, _rough_damage(battle, attacker, target, weapon.strike, weapon=weapon))
        for effect in _active_spells_for_phase(attacker, bonus=False):
            if effect.target != "enemy":
                continue
            spell_weapon = _weapon_for_effect(attacker, effect)
            if target in get_legal_targets(battle, attacker, effect=effect, weapon=spell_weapon):
                best = max(best, _rough_damage(battle, attacker, target, effect, weapon=spell_weapon))
        if team_for_actor(battle, attacker).ultimate_meter >= ULTIMATE_METER_MAX:
            effect = attacker.defn.ultimate
            if effect.target == "enemy" and target in get_legal_targets(battle, attacker, effect=effect):
                best = max(best, _rough_damage(battle, attacker, target, effect, weapon=_weapon_for_effect(attacker, effect)))
        total += best
    return total


def _estimate_pre_actor_damage_to_target(battle, actor_index: int, team_num: int, target) -> float:
    return _estimate_window_damage_to_target(battle, 0, actor_index, team_num, target)


def _has_pre_actor_swap_risk(battle, actor_index: int, target_ref: tuple[int, str] | None) -> bool:
    if target_ref is None:
        return False
    for mover in battle.initiative_order[:actor_index]:
        if mover.ko or player_num_for_actor(battle, mover) != target_ref[0]:
            continue
        mover_ref = _unit_ref(battle, mover)
        for spec in available_action_specs(battle, mover, bonus=False):
            if spec.kind != "swap":
                continue
            if not _spec_is_legal(battle, mover, spec):
                continue
            if mover_ref == target_ref or spec.target_ref == target_ref:
                return True
    return False


def _has_pre_actor_ally_swap_exposure_risk(battle, actor, actor_index: int, target) -> bool:
    if target is None or target.ko:
        return False
    actor_team_num = player_num_for_actor(battle, actor)
    enemy_team_num = 2 if actor_team_num == 1 else 1
    actor_ref = _unit_ref(battle, actor)
    target_ref = _unit_ref(battle, target)
    for mover in battle.initiative_order[:actor_index]:
        if mover.ko or player_num_for_actor(battle, mover) != actor_team_num:
            continue
        mover_ref = _unit_ref(battle, mover)
        if mover_ref == actor_ref:
            continue
        mover_index = _initiative_index(battle, mover)
        for spec in available_action_specs(battle, mover, bonus=False):
            if spec.kind != "swap" or not _spec_is_legal(battle, mover, spec):
                continue
            if target_ref not in {mover_ref, spec.target_ref}:
                continue
            sim = copy.deepcopy(battle)
            sim_mover = _find_unit(sim, mover_ref)
            if sim_mover is None or sim_mover.ko:
                continue
            _queue_spec(sim_mover, sim, spec)
            sim_action = sim_mover.queued_bonus_action if spec.bonus else sim_mover.queued_action
            resolve_action(sim_mover, sim_action, sim, is_bonus=spec.bonus)
            sim_target = _find_unit(sim, target_ref)
            if sim_target is None or sim_target.ko:
                return True
            threatened = _estimate_window_damage_to_target(
                sim,
                mover_index + 1,
                actor_index,
                enemy_team_num,
                sim_target,
            )
            if threatened >= sim_target.hp:
                return True
    return False


def _pre_actor_target_self_protection_risk(
    battle,
    actor,
    actor_index: int,
    target,
    spec: ActionSpec,
) -> tuple[float, bool]:
    if (
        target is None
        or target.ko
        or spec.kind not in {"strike", "spell", "ultimate"}
        or spec.target_ref is None
        or player_num_for_actor(battle, target) == player_num_for_actor(battle, actor)
    ):
        return 0.0, False
    target_index = _initiative_index(battle, target)
    if target_index >= actor_index:
        return 0.0, False

    incoming_effect = _spec_effect(actor, spec)
    if incoming_effect is None or incoming_effect.target != "enemy":
        return 0.0, False

    incoming_weapon = (
        _strike_weapon_for_spec(actor, spec)
        if spec.kind == "strike"
        else _weapon_for_effect(actor, incoming_effect)
    )
    direct_pressure = _rough_damage(battle, actor, target, incoming_effect, weapon=incoming_weapon)
    team_pressure = _estimate_team_damage_to_target(
        battle, player_num_for_actor(battle, actor), target
    )
    hp_ratio = target.hp / max(1, target.max_hp)
    threatened = (
        direct_pressure >= max(1, int(target.hp * 0.45))
        or team_pressure >= max(1, int(target.hp * 0.75))
        or hp_ratio <= 0.55
    )

    risk = 0.0
    hard_invalid = False
    for target_spec in available_action_specs(battle, target, bonus=False):
        if target_spec.kind not in {"spell", "ultimate"}:
            continue
        effect = _spec_effect(target, target_spec)
        if effect is None or effect.target != "self":
            continue
        if effect.special in SELF_PROTECTION_INVALIDATING_SPECIALS:
            if threatened:
                return 28.0, True
            risk = max(risk, 10.0)
            continue
        if effect.special == "time_stop":
            if threatened:
                risk = max(risk, 6.0)
            continue
        if effect.special in SELF_PROTECTION_STRIKE_SOFT_SPECIALS and spec.kind == "strike":
            if direct_pressure > 0 or hp_ratio <= 0.8:
                risk = max(risk, 10.0)
    return risk, hard_invalid


def _ally_will_ko_target(battle, team_num: int, actor, target) -> bool:
    """Returns True if an ally acting before actor in initiative order will KO target."""
    if target is None or target.ko:
        return False
    actor_idx = _initiative_index(battle, actor)
    for ally in battle.get_team(team_num).alive():
        if ally is actor:
            continue
        if _initiative_index(battle, ally) >= actor_idx:
            continue  # acts after us, won't pre-empt
        for weapon in ally.active_strike_weapons():
            if not _can_attempt_strike(ally, weapon):
                continue
            rough = _rough_damage(battle, ally, target, weapon.strike, weapon=weapon)
            if rough >= target.hp:
                return True
        for effect in _active_spells_for_phase(ally, bonus=False):
            if effect.target != "enemy":
                continue
            if _rough_damage(battle, ally, target, effect, weapon=_weapon_for_effect(ally, effect)) >= target.hp:
                return True
    return False


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
        tags = set(_profile_for(enemy_unit).role_tags)
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
        priority = estimated * 0.35 + _threat_value(enemy_unit) + _runtime_threat_bonus(battle, enemy_unit, team_num) + collapse + focus_bonus
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
        if "fragile" in _profile_for(ally).role_tags:
            risk += 12.0
        if risk > vulnerable_score:
            vulnerable_score = risk
            vulnerable = ally
    back_left = own.get_slot(SLOT_BACK_LEFT)
    front = own.frontline()
    fallback_ref = _unit_ref(battle, back_left) if back_left is not None else None
    pivot_needed = False
    if front is not None and back_left is not None:
        front_score = _profile_for(front).position_scores[SLOT_FRONT]
        back_left_score = _profile_for(back_left).position_scores[SLOT_FRONT]
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
    # Late-game escalation: after round 10, ultimate win condition becomes dominant
    if battle.round_num > 10 and race_kind not in {"ko"}:
        if enemy_ultimates >= max(1, ULTIMATE_WIN_COUNT - 1) or (enemy_ultimates > own_ultimates and battle.round_num > 14):
            race_kind = "deny_ultimate"
        elif own.ultimate_meter >= ULTIMATE_METER_MAX // 2 and race_kind == "hybrid":
            race_kind = "ultimate"

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
            roles.update(_profile_for(ally).role_tags)
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
    if _actor_forced_to_skip(actor, battle):
        return [ActionSpec(kind="skip", bonus=bonus)]
    specs: list[ActionSpec] = []
    team = team_for_actor(battle, actor)
    if bonus:
        if _can_switch(actor, bonus=True):
            specs.append(ActionSpec(kind="switch", bonus=True))
        covert_bonus_swap = actor.class_skill.id == "covert" and actor.markers.get("spells_cast_this_round", 0) > 0
        if covert_bonus_swap or actor.defn.id == "the_green_knight" or _team_bonus_swap_available(team):
            for ally in _allies(actor, battle):
                spec = ActionSpec(kind="swap", target_ref=_unit_ref(battle, ally), bonus=True)
                if _spec_is_legal(battle, actor, spec):
                    specs.append(spec)
        for effect in _active_spells_for_phase(actor, bonus=True):
            targets = get_legal_targets(battle, actor, effect=effect, weapon=_weapon_for_effect(actor, effect))
            if effect.target in {"none", "self"}:
                spec = ActionSpec(kind="spell", effect_id=effect.id, bonus=True)
                if _spec_is_legal(battle, actor, spec):
                    specs.append(spec)
            else:
                for target in targets:
                    spec = ActionSpec(kind="spell", effect_id=effect.id, target_ref=_unit_ref(battle, target), bonus=True)
                    if _spec_is_legal(battle, actor, spec):
                        specs.append(spec)
        specs.append(ActionSpec(kind="skip", bonus=True))
        return specs

    for weapon in actor.active_strike_weapons():
        if not _can_attempt_strike(actor, weapon):
            continue
        strike_targets = get_legal_targets(battle, actor, effect=weapon.strike, weapon=weapon)
        for target in strike_targets:
            spec = ActionSpec(kind="strike", target_ref=_unit_ref(battle, target), weapon_id=weapon.id)
            if _spec_is_legal(battle, actor, spec):
                specs.append(spec)
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
        spell_weapon = _weapon_for_effect(actor, effect)
        targets = get_legal_targets(battle, actor, effect=effect, weapon=spell_weapon)
        if effect.target in {"none", "self"}:
            spec = ActionSpec(kind="spell", effect_id=effect.id)
            if _spec_is_legal(battle, actor, spec):
                specs.append(spec)
        else:
            for target in targets:
                spec = ActionSpec(kind="spell", effect_id=effect.id, target_ref=_unit_ref(battle, target))
                if _spec_is_legal(battle, actor, spec):
                    specs.append(spec)
    if _can_switch(actor, bonus=False):
        specs.append(ActionSpec(kind="switch"))
    for ally in _allies(actor, battle):
        spec = ActionSpec(kind="swap", target_ref=_unit_ref(battle, ally))
        if _spec_is_legal(battle, actor, spec):
            specs.append(spec)
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
            queue_bonus_action(actor, {"type": "strike", "target": target, "weapon_id": spec.weapon_id or actor.primary_weapon.id})
        else:
            queue_strike(actor, target, weapon_id=spec.weapon_id)
        return
    if spec.kind == "spell":
        effect = _effect_by_id(actor, spec.effect_id)
        if spec.bonus:
            queue_bonus_action(actor, {"type": "spell", "effect": effect, "target": target})
        else:
            queue_spell(actor, effect, target, battle)
        return
    if spec.kind == "ultimate":
        effect = actor.defn.ultimate
        if spec.bonus:
            queue_bonus_action(actor, {"type": "ultimate", "effect": effect, "target": target})
        else:
            queue_ultimate(actor, target, battle)
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
        and unit.artifact.reactive_effect is not None
        and unit.cooldowns.get(unit.artifact.reactive_effect.id, 0) <= 0
    )


def _marker_state_score(unit) -> float:
    value = 0.0
    if unit.markers.get("cant_act_rounds", 0) > 0:
        value -= 18.0
    if unit.markers.get("cant_strike_rounds", 0) > 0:
        value -= 7.0
    if unit.markers.get("untargetable_rounds", 0) > 0:
        value += 10.0
    if unit.markers.get("next_spell_no_cooldown", 0) > 0:
        value += 4.0
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
    return value


def _resource_state_score(unit) -> float:
    value = 0.0
    for primary in unit.active_strike_weapons():
        if primary.ammo <= 0:
            continue
        ammo_left = unit.ammo_remaining.get(primary.id, primary.ammo)
        ammo_ratio = ammo_left / max(1, primary.ammo)
        if ammo_left <= 0:
            value -= 12.0
        else:
            value += ammo_ratio * 4.0
    ready_spells = sum(1 for effect in unit.active_spells() if unit.cooldowns.get(effect.id, 0) <= 0)
    value += ready_spells * 1.4
    if _reactive_artifact_ready(unit):
        value += 6.0 if "fragile" in _profile_for(unit).role_tags else 4.0
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
            if "fragile" in _profile_for(ally).role_tags or ally.slot != SLOT_FRONT:
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
        profile = _profile_for(unit)
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
        profile = _profile_for(unit)
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
        value += _profile_for(back_left).position_scores[SLOT_BACK_LEFT] * 0.08
    meter_weight = 50.0 / ULTIMATE_METER_MAX
    if battle.round_num > 10:
        meter_weight *= min(2.5, 1.0 + (battle.round_num - 10) / 8.0)
    value += own.ultimate_meter * meter_weight
    value -= enemy.ultimate_meter * meter_weight
    if battle.round_num > 10:
        own_casts = own.markers.get("ultimates_cast", 0)
        enemy_casts = enemy.markers.get("ultimates_cast", 0)
        cast_weight = 25.0 * min(2.0, (battle.round_num - 10) / 8.0)
        value += (own_casts - enemy_casts) * cast_weight
    value += _lethal_pressure_score(battle, team_num)
    return value


def _plan_failure_penalty(log_lines: list[str]) -> tuple[float, float]:
    penalty = 0.0
    failures = 0.0
    for line in log_lines:
        weight = _failure_weight_for_line(line)
        if weight > 0:
            penalty += weight
            failures += 1.0
    return penalty, failures


def _initiative_index(battle, actor) -> int:
    if not battle.initiative_order:
        determine_initiative_order(battle)
    for index, unit in enumerate(battle.initiative_order):
        if unit is actor:
            return index
    return len(battle.initiative_order)


def _actor_failure_weight(log_lines: list[str], actor_name: str) -> float:
    best = 0.0
    actor_prefixes = (
        f"{actor_name}'s queued ",
        f"{actor_name} cannot ",
        f"{actor_name} has no ",
    )
    for line in log_lines:
        if not line.startswith(actor_prefixes):
            continue
        best = max(best, _failure_weight_for_line(line))
    return best


def _team_failure_penalty(log_lines: list[str], actor_names: list[str]) -> tuple[float, float]:
    penalty = 0.0
    failures = 0.0
    if not actor_names:
        return penalty, failures
    actor_prefixes = {
        actor_name: (
            f"{actor_name}'s queued ",
            f"{actor_name} cannot ",
            f"{actor_name} has no ",
        )
        for actor_name in actor_names
    }
    for line in log_lines:
        weight = 0.0
        for prefixes in actor_prefixes.values():
            if line.startswith(prefixes):
                weight = _failure_weight_for_line(line)
                break
        if weight <= 0.0:
            continue
        penalty += weight
        failures += 1.0
    return penalty, failures


def _relevant_enemy_disruption_specs(battle, enemy, actor, own_spec: ActionSpec) -> list[ActionSpec]:
    actor_ref = _unit_ref(battle, actor)
    own_target_ref = own_spec.target_ref
    enemy_team_num = player_num_for_actor(battle, enemy)
    actor_team_num = player_num_for_actor(battle, actor)
    relevant: list[ActionSpec] = []
    for spec in available_action_specs(battle, enemy, bonus=False):
        if spec.kind in {"skip", "switch"}:
            continue
        if spec.kind == "swap":
            moved_refs = {_unit_ref(battle, enemy)}
            if spec.target_ref is not None:
                moved_refs.add(spec.target_ref)
            if actor_ref in moved_refs:
                relevant.append(spec)
                continue
            if own_target_ref is not None and own_target_ref in moved_refs:
                relevant.append(spec)
            continue
        effect = _spec_effect(enemy, spec)
        if effect is None:
            continue
        if (
            own_target_ref is not None
            and own_target_ref == _unit_ref(battle, enemy)
            and effect.target == "self"
            and (
                effect.special in SELF_PROTECTION_DISRUPTION_SPECIALS
                or (effect.special in SELF_PROTECTION_STRIKE_SOFT_SPECIALS and own_spec.kind == "strike")
            )
        ):
            relevant.append(spec)
            continue
        target_ref = spec.target_ref
        status_kinds = {status.kind for status in effect.target_statuses}
        if target_ref is not None and target_ref[0] == actor_team_num:
            if (
                target_ref == actor_ref
                or own_target_ref == target_ref
                or effect.power > 0
                or effect.special in DISRUPTIVE_EFFECT_SPECIALS
                or bool(status_kinds)
            ):
                relevant.append(spec)
                continue
        if effect.special in {"zephyr", "swap_target_with_enemy"} and target_ref is not None and target_ref[0] == actor_team_num:
            relevant.append(spec)
            continue
        if effect.special in {"artifact_swap_with_ally", "midnight_waltz"} and own_target_ref is not None and own_target_ref[0] == enemy_team_num:
            if own_target_ref in {_unit_ref(battle, enemy), target_ref}:
                relevant.append(spec)
                continue
        if effect.special in {"self_swap_after_strike", "trojan_horse"} and own_target_ref is not None and own_target_ref == _unit_ref(battle, enemy):
            relevant.append(spec)
            continue
        if effect.special == "cant_strike_next_turn" and own_spec.kind == "strike" and target_ref == actor_ref:
            relevant.append(spec)
            continue
        if "taunt" in status_kinds and target_ref == actor_ref and own_spec.target_ref is not None and own_spec.target_ref[0] != actor_team_num:
            relevant.append(spec)
            continue
        if effect.special in DISRUPTIVE_EFFECT_SPECIALS and target_ref is not None and target_ref[0] == actor_team_num:
            relevant.append(spec)
    return relevant


def _pre_resolution_enemy_risk(battle, team_num: int, actor_ref: tuple[int, str], spec: ActionSpec) -> float:
    if spec.bonus or spec.kind == "skip":
        return 0.0
    actor = _find_unit(battle, actor_ref)
    if actor is None or actor.ko:
        return 0.0
    actor_index = _initiative_index(battle, actor)
    total_risk = 0.0
    for enemy in battle.initiative_order[:actor_index]:
        if enemy.ko or player_num_for_actor(battle, enemy) == team_num:
            continue
        enemy_risk = 0.0
        for enemy_spec in _relevant_enemy_disruption_specs(battle, enemy, actor, spec):
            sim = copy.deepcopy(battle)
            sim_enemy = _find_unit(sim, _unit_ref(battle, enemy))
            sim_actor = _find_unit(sim, actor_ref)
            if sim_enemy is None or sim_actor is None or sim_actor.ko:
                continue
            _queue_spec(sim_enemy, sim, enemy_spec)
            enemy_action = sim_enemy.queued_bonus_action if enemy_spec.bonus else sim_enemy.queued_action
            resolve_action(sim_enemy, enemy_action, sim, is_bonus=enemy_spec.bonus)
            sim_actor = _find_unit(sim, actor_ref)
            if sim_actor is None or sim_actor.ko:
                enemy_risk = max(enemy_risk, 18.0)
                continue
            log_start = len(sim.log)
            _queue_spec(sim_actor, sim, spec)
            own_action = sim_actor.queued_bonus_action if spec.bonus else sim_actor.queued_action
            resolve_action(sim_actor, own_action, sim, is_bonus=spec.bonus)
            failure_weight = _actor_failure_weight(sim.log[log_start:], sim_actor.name)
            if failure_weight > 0:
                enemy_risk = max(enemy_risk, failure_weight * 0.9)
                continue
            strike_weapon = _strike_weapon_for_spec(actor, spec) if spec.kind == "strike" else None
            if spec.kind == "strike" and strike_weapon is not None and strike_weapon.kind == "melee" and sim_actor.slot != actor.slot:
                enemy_risk = max(enemy_risk, 12.0)
        total_risk += enemy_risk
    return min(total_risk, 24.0)


def _simulate_spec_delta(battle, team_num: int, actor_ref: tuple[int, str], spec: ActionSpec) -> float:
    base_value = evaluate_battle_state(battle, team_num)
    own_before = battle.get_team(team_num)
    enemy_before = battle.get_enemy(team_num)
    own_alive_before = sum(1 for unit in own_before.members if not unit.ko)
    enemy_alive_before = sum(1 for unit in enemy_before.members if not unit.ko)
    enemy_front_before = enemy_before.frontline()
    sim = copy.deepcopy(battle)
    actor = _find_unit(sim, actor_ref)
    if actor is None or actor.ko:
        return -999.0
    materialized = _find_unit(sim, actor_ref)
    _queue_spec(materialized, sim, spec)
    action = materialized.queued_bonus_action if spec.bonus else materialized.queued_action
    resolve_action(materialized, action, sim, is_bonus=spec.bonus)
    delta = evaluate_battle_state(sim, team_num) - base_value
    own_after = sim.get_team(team_num)
    enemy_after = sim.get_enemy(team_num)
    own_alive_after = sum(1 for unit in own_after.members if not unit.ko)
    enemy_alive_after = sum(1 for unit in enemy_after.members if not unit.ko)
    enemy_kos = enemy_alive_before - enemy_alive_after
    own_losses = own_alive_before - own_alive_after
    if enemy_kos > 0:
        delta += enemy_kos * 26.0
    if own_losses > 0:
        delta -= own_losses * 28.0
    if enemy_front_before is not None:
        sim_enemy_front_before = _find_unit(sim, _unit_ref(battle, enemy_front_before))
        if sim_enemy_front_before is not None and sim_enemy_front_before.ko:
            delta += 8.0
    real_actor = _find_unit(battle, actor_ref)
    target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
    effect = _spec_effect(real_actor, spec) if real_actor is not None else None
    actor_index = _initiative_index(battle, real_actor) if real_actor is not None else len(battle.initiative_order)
    enemy_team_num = 2 if team_num == 1 else 1
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
        threatened = _estimate_pre_actor_damage_to_target(battle, actor_index, enemy_team_num, target)
        if threatened >= target.hp:
            delta -= 120.0
        elif threatened >= target.hp * 0.85:
            delta -= 60.0
        elif threatened >= target.hp * 0.6:
            delta -= 20.0
    elif spec.kind in {"strike", "spell", "ultimate"} and target is not None and effect is not None and real_actor is not None:
        source_weapon = (
            _strike_weapon_for_spec(real_actor, spec)
            if spec.kind == "strike"
            else _weapon_for_effect(real_actor, effect)
        )
        if effect.target == "enemy":
            self_protection_risk, _hard_invalid = _pre_actor_target_self_protection_risk(
                battle, real_actor, actor_index, target, spec
            )
            delta -= self_protection_risk
            rough = _rough_damage(battle, real_actor, target, effect, weapon=source_weapon)
            if rough >= target.hp:
                delta += 24.0
                if target.slot == SLOT_FRONT:
                    delta += 10.0
                # Initiative-aware KO securing: first-mover gets extra bonus
                if _initiative_index(battle, real_actor) < _initiative_index(battle, target):
                    delta += 8.0
                # Focus-fire overkill redirect: a faster ally will already secure this kill
                if _ally_will_ko_target(battle, team_num, real_actor, target):
                    delta -= 22.0
            elif rough >= target.hp * 0.6:
                delta += 6.0
            if target.hp <= max(55, int(target.max_hp * 0.28)):
                delta += 6.0
            if target.has_status("expose") or target.has_status("root") or target.has_status("shock") or target.has_status("spotlight"):
                delta += 3.0
            if target.slot != SLOT_FRONT:
                if _has_pre_actor_swap_risk(battle, actor_index, spec.target_ref):
                    delta -= 24.0
                target_front = team_for_actor(battle, target).frontline()
                if target_front is not None and target_front is not target:
                    front_threatened = _estimate_pre_actor_damage_to_target(battle, actor_index, team_num, target_front)
                    if front_threatened >= target_front.hp * 0.85:
                        delta -= 12.0
                    elif front_threatened >= target_front.hp * 0.6:
                        delta -= 5.0
            if real_actor.slot != SLOT_FRONT:
                own_front = team_for_actor(battle, real_actor).frontline()
                if own_front is not None and own_front is not real_actor:
                    own_front_threatened = _estimate_pre_actor_damage_to_target(battle, actor_index, enemy_team_num, own_front)
                    if own_front_threatened >= own_front.hp * 0.85:
                        delta -= 14.0
                    elif own_front_threatened >= own_front.hp * 0.6:
                        delta -= 6.0
            # Redundant debuff suppression (non-stacking: only best debuff applies)
            for debuff_spec in effect.target_debuffs:
                if target.best_debuff(debuff_spec.stat) >= debuff_spec.amount:
                    delta -= 1.5
            # Reactive artifact awareness: penalty for striking units that will negate/counter
            if rough < target.hp:
                if target.markers.get("mistform_ready", 0) > 0 and spec.kind == "strike":
                    delta -= 10.0
                elif _reactive_artifact_ready(target):
                    delta -= 4.0
                if target.markers.get("vine_snare_ready", 0) > 0 and spec.kind == "strike":
                    delta -= 3.0
        elif effect.target in {"ally", "self"}:
            resolved_target = target if effect.target == "ally" else real_actor
            if effect.target == "ally" and resolved_target is not None:
                threatened = _estimate_pre_actor_damage_to_target(battle, actor_index, enemy_team_num, resolved_target)
                if threatened >= resolved_target.hp:
                    delta -= 120.0
                elif _has_pre_actor_ally_swap_exposure_risk(
                    battle, real_actor, actor_index, resolved_target
                ):
                    delta -= 120.0
                elif threatened >= resolved_target.hp * 0.85:
                    delta -= 60.0
                elif threatened >= resolved_target.hp * 0.6:
                    delta -= 20.0
            if effect.heal > 0 and resolved_target is not None:
                hp_ratio = resolved_target.hp / max(1, resolved_target.max_hp)
                delta += effect.heal * (0.08 if hp_ratio > 0.5 else 0.16)
                # Wasted heal suppression: target already near full HP
                if hp_ratio > 0.85:
                    delta -= 3.0
            if any(status.kind == "guard" for status in effect.target_statuses):
                delta += 8.0
                # Wasted guard suppression: target already guarded
                if resolved_target is not None and resolved_target.has_status("guard"):
                    delta -= 7.0
            # Redundant status suppression (wasted application)
            for status_spec in effect.target_statuses:
                if resolved_target is not None and resolved_target.has_status(status_spec.kind):
                    existing = next((s for s in resolved_target.statuses if s.kind == status_spec.kind), None)
                    if existing is not None and existing.duration >= status_spec.duration:
                        delta -= 3.0
            # Non-stacking buff awareness (only best buff applies to stat calculation)
            for buff_spec in effect.self_buffs:
                if real_actor.best_buff(buff_spec.stat) >= buff_spec.amount:
                    delta -= 2.0
            for buff_spec in effect.target_buffs:
                if resolved_target is not None and resolved_target.best_buff(buff_spec.stat) >= buff_spec.amount:
                    delta -= 2.0
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
    if real_actor is not None:
        delta -= _pre_resolution_enemy_risk(battle, team_num, actor_ref, spec)
    return delta


def _spec_has_hard_invalid_pre_resolution_risk(battle, actor, spec: ActionSpec) -> bool:
    if spec.bonus or spec.kind == "skip":
        return False
    actor_ref = _unit_ref(battle, actor)
    team_num = player_num_for_actor(battle, actor)
    enemy_team_num = 2 if team_num == 1 else 1
    actor_index = _initiative_index(battle, actor)
    target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
    if spec.kind == "swap" and target is not None:
        threatened = _estimate_pre_actor_damage_to_target(battle, actor_index, enemy_team_num, target)
        return threatened >= target.hp
    if spec.kind in {"strike", "spell", "ultimate"}:
        effect = _spec_effect(actor, spec)
        if target is not None and effect is not None and effect.target == "enemy":
            if target.slot != SLOT_FRONT and _has_pre_actor_swap_risk(battle, actor_index, spec.target_ref):
                return True
            _risk, hard_invalid = _pre_actor_target_self_protection_risk(
                battle, actor, actor_index, target, spec
            )
            if hard_invalid:
                return True
        if target is not None and effect is not None and effect.target == "ally":
            threatened = _estimate_pre_actor_damage_to_target(battle, actor_index, enemy_team_num, target)
            return threatened >= target.hp or _has_pre_actor_ally_swap_exposure_risk(
                battle, actor, actor_index, target
            )
    return _pre_resolution_enemy_risk(battle, team_num, actor_ref, spec) >= 18.0


def _formation_delta(battle, actor, target) -> float:
    if target is None or target.ko or team_for_actor(battle, actor) != team_for_actor(battle, target):
        return 0.0
    actor_profile = _profile_for(actor)
    target_profile = _profile_for(target)
    before = actor_profile.position_scores[actor.slot] + target_profile.position_scores[target.slot]
    after = actor_profile.position_scores[target.slot] + target_profile.position_scores[actor.slot]
    return (after - before) * 0.18


def _plan_bias(battle, actor, spec: ActionSpec, analysis: RoundAnalysis) -> float:
    bias = 0.0
    target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None

    # Low-HP desperation: universal per-actor urgency (red-zone analog)
    actor_hp_ratio = actor.hp / max(1, actor.max_hp)
    if actor_hp_ratio <= 0.20:
        if spec.kind == "swap":
            bias += 9.0
        elif spec.kind == "switch":
            bias += 4.0
        elif spec.kind in {"strike", "spell", "ultimate"}:
            if _ref_matches_any_slot(battle, spec.target_ref, analysis.killable_enemy_refs):
                bias += 4.0  # go out swinging for a confirmed kill
            else:
                bias -= 2.0  # deprioritize chip damage at critical HP
    elif actor_hp_ratio <= 0.35:
        if spec.kind == "swap":
            bias += 4.0

    if analysis.plan_kind == "kill":
        if spec.kind == "ultimate":
            bias += 14.0
        if spec.kind in {"strike", "spell", "ultimate"} and _ref_matches_any_slot(battle, spec.target_ref, analysis.killable_enemy_refs):
            bias += 18.0
            # Initiative-aware kill securing: bonus for acting before the target can react
            if target is not None and _initiative_index(battle, actor) < _initiative_index(battle, target):
                bias += 6.0
        elif spec.kind in {"strike", "spell", "ultimate"} and _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
            bias += 8.0
    elif analysis.plan_kind == "stabilize":
        if spec.kind == "swap" and target is not None:
            bias += max(0.0, 4.0 + _formation_delta(battle, actor, target))
        if spec.kind == "spell" and spec.effect_id is not None:
            effect = _effect_by_id(actor, spec.effect_id)
            if effect.heal > 0 or any(status.kind == "guard" for status in effect.target_statuses):
                bias += 12.0
            if effect.special == "dazzle":
                bias += 11.0
        if spec.kind in {"strike", "spell", "ultimate"} and _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
            bias += 4.0
    elif analysis.plan_kind == "setup":
        if spec.kind == "switch":
            bias += 5.0
        if spec.kind == "spell" and spec.effect_id is not None:
            effect = _effect_by_id(actor, spec.effect_id)
            status_kinds = {status.kind for status in effect.target_statuses}
            new_statuses = {"shock", "root", "expose", "spotlight", "taunt"} & status_kinds
            if new_statuses:
                # Don't boost if target already has all these statuses at full duration (wasted action)
                already_applied = target is not None and all(
                    target.has_status(k) and any(s.kind == k and s.duration >= 2 for s in target.statuses)
                    for k in new_statuses
                )
                if not already_applied:
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
        elif spec.kind in {"strike", "spell"} and _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
            bias += 4.0
    else:
        if spec.kind == "switch":
            bias += 2.0
        if spec.kind == "spell" and spec.effect_id is not None:
            effect = _effect_by_id(actor, spec.effect_id)
            status_kinds = {status.kind for status in effect.target_statuses}
            new_statuses = {"shock", "root", "expose", "spotlight"} & status_kinds
            if new_statuses:
                already_applied = target is not None and all(
                    target.has_status(k) and any(s.kind == k and s.duration >= 2 for s in target.statuses)
                    for k in new_statuses
                )
                if not already_applied:
                    bias += 4.0

    if analysis.race_kind == "ko":
        if spec.kind in {"strike", "spell", "ultimate"} and _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
            bias += 6.0
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
        if spec.kind in {"strike", "spell", "ultimate"} and _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
            bias += 4.0
        if spec.kind == "swap" and target is not None:
            bias += max(0.0, 2.0 + _formation_delta(battle, actor, target))

    # March Hare's Cracked Stopwatch line is a key extra-action enabler; value it explicitly.
    if (
        spec.kind == "strike"
        and actor.defn.id == "march_hare"
        and strike_weapon is not None
        and strike_weapon.id == "cracked_stopwatch"
        and target is not None
        and target.has_status("shock")
    ):
        bias += 12.0

    # Late-game ultimate urgency: scales with round count beyond round 10
    if battle.round_num > 10:
        own_team_lg = team_for_actor(battle, actor)
        enemy_team_lg = _enemy_team_for_actor(battle, actor)
        own_casts = own_team_lg.markers.get("ultimates_cast", 0)
        enemy_casts = enemy_team_lg.markers.get("ultimates_cast", 0)
        late_scale = min(1.8, (battle.round_num - 10) / 6.0)
        # Full meter in late game: strongly prefer firing it
        if own_team_lg.ultimate_meter >= ULTIMATE_METER_MAX and spec.kind == "ultimate":
            bias += 7.0 * late_scale
        # Enemy close to win or ahead: rush ultimates
        if enemy_casts >= max(1, ULTIMATE_WIN_COUNT - 1):
            if spec.kind == "ultimate":
                bias += 5.0 * late_scale
            elif spec.kind in {"strike", "spell"}:
                bias += 1.5 * late_scale
        # Behind on ultimate count: value meter-building and discourage skipping
        if own_casts < enemy_casts:
            if spec.kind == "ultimate":
                bias += 6.0 * late_scale
            elif spec.kind in {"strike", "spell"}:
                bias += 1.0 * late_scale
            elif spec.kind == "skip":
                bias -= 3.0 * late_scale

    bias += _character_specific_bias(battle, actor, spec, analysis)
    return bias


def _character_specific_bias(battle, actor, spec: ActionSpec, analysis: RoundAnalysis) -> float:
    bias = 0.0
    target = _find_unit(battle, spec.target_ref) if spec.target_ref is not None else None
    team = team_for_actor(battle, actor)
    enemy_team = battle.team1 if team is battle.team2 else battle.team2
    enemy_team_num = 2 if player_num_for_actor(battle, actor) == 1 else 1
    strike_weapon = _strike_weapon_for_spec(actor, spec) if spec.kind == "strike" else None

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

    if (
        spec.kind == "strike"
        and actor.class_skill.id == "vanguard"
        and target is not None
        and target.slot == SLOT_FRONT
    ):
        splash_targets = sum(1 for enemy in enemy_team.alive() if enemy.slot != SLOT_FRONT)
        bias += splash_targets * 3.5

    if actor.defn.id == "little_jack":
        if spec.kind == "spell" and spec.effect_id == "cloudburst":
            priority_target = _find_unit(battle, analysis.priority_target_ref) if analysis.priority_target_ref is not None else None
            legal_now = []
            for weapon in actor.active_strike_weapons():
                legal_now.extend(get_legal_targets(battle, actor, effect=weapon.strike, weapon=weapon))
            if priority_target is not None and priority_target not in legal_now:
                bias += 8.0
            elif analysis.plan_kind in {"kill", "ultimate"}:
                bias += 4.0
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "skyfall" and target is not None:
            if _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
                bias += 5.0
            if target.has_status("expose"):
                bias += 3.0
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "giants_harp" and target is not None:
            if target.get_stat("defense") >= 70:
                bias += 4.0

    if actor.defn.id == "red_blanchette":
        if spec.kind == "spell" and spec.effect_id == "blood_transfusion" and target is not None:
            if actor.hp <= actor.max_hp * 0.5 and target.hp > actor.hp:
                bias += 10.0
        if spec.kind == "ultimate" and actor.hp <= actor.max_hp * 0.65:
            bias += 6.0

    if actor.defn.id == "witch_hunter_gretel":
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "hot_mitts" and target is not None:
            if target.has_status("burn"):
                bias += 6.0
            else:
                bias += 4.0
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "crumb_shot":
            if team.markers.get("crumb_picked_round", 0) > 0:
                bias += 6.0
            else:
                bias += 2.5

    if actor.defn.id == "destitute_vasilisa":
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "guiding_doll" and target is not None:
            bias += 6.0
            if _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
                bias += 4.0
            ally_followups = 0
            for ally in team.alive():
                if ally is actor:
                    continue
                if any(
                    target in get_legal_targets(battle, ally, effect=weapon.strike, weapon=weapon)
                    for weapon in ally.active_strike_weapons()
                    if _can_attempt_strike(ally, weapon)
                ):
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
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "jar_of_oil" and target is not None and not target.has_status("burn"):
            bias += 4.0
        if spec.kind == "ultimate":
            ranged_enemies = 0
            for enemy in enemy_team.alive():
                if any(weapon.kind == "ranged" for weapon in enemy.defn.signature_weapons):
                    ranged_enemies += 1
            bias += ranged_enemies * 2.5

    if actor.defn.id == "maui_sunthief":
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "whale_jaw_hook" and target is not None and not target.has_status("expose"):
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
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "crafty_wall":
            threatened = _estimate_team_damage_to_target(battle, enemy_team_num, actor)
            if threatened >= actor.max_hp * 0.18:
                bias += 4.0

    if actor.defn.id == "kama_the_honeyed":
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "sugarcane_bow" and target is not None and not target.has_status("spotlight"):
            bias += 4.0
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "the_stinger" and target is not None and target.has_status("spotlight"):
            bias += 8.0
        if spec.kind == "spell" and spec.effect_id == "sukas_eyes":
            unlit = sum(1 for enemy in enemy_team.alive() if not enemy.has_status("spotlight"))
            bias += unlit * 2.5
        if spec.kind == "ultimate":
            ranged_allies = sum(1 for ally in team.alive() if ally.primary_weapon.kind == "ranged")
            bias += 2.0 + ranged_allies * 2.0

    if actor.defn.id == "hunold_the_piper":
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "lightning_rod" and target is not None and not target.has_status("shock"):
            bias += 3.0
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "golden_fiddle" and target is not None and target.has_status("shock"):
            bias += 8.0

    if actor.defn.id == "briar_rose":
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "thorn_snare":
            bias += min(6.0, len(enemy_team.alive()) * 1.5)
        if spec.kind == "spell" and spec.effect_id == "vine_snare":
            bias += 3.0

    if actor.defn.id == "sir_roland":
        if spec.kind == "spell" and spec.effect_id == "knights_challenge":
            if _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
                bias += 5.0
            if target is not None and target.slot == SLOT_FRONT:
                bias += 2.5

    if actor.defn.id == "lady_of_reflections":
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "lantern_of_avalon":
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
            spell_weapon = _weapon_for_effect(actor, _effect_by_id(actor, spec.effect_id))
            if spell_weapon.id == "the_flock" and len(enemy_team.alive()) >= 2:
                bias += 7.0
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "kingmaker" and target is not None:
            if target.slot != SLOT_FRONT or target.has_status("spotlight"):
                bias += 7.0

    if actor.defn.id == "the_good_beast":
        if spec.kind == "spell" and spec.effect_id == "crystal_ball" and actor.markers.get("guest_last_attacker") is not None:
            bias += 6.0
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "dinner_bell" and target is not None:
            if target in team.alive() and target.hp / max(1, target.max_hp) <= 0.5:
                bias += 6.0

    if actor.defn.id == "rapunzel_the_golden":
        if spec.kind == "spell" and spec.effect_id == "lower_guard" and target is not None:
            if target.has_status("root") or _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
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
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "spinning_wheel":
            bias += 2.0

    if actor.defn.id == "reynard_lupine_trickster":
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "foxfire_bow" and target is not None:
            if all(debuff.stat != "defense" or debuff.duration <= 0 for debuff in target.debuffs):
                bias += 4.5
            if _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
                bias += 2.0
        if spec.kind == "strike" and strike_weapon is not None and strike_weapon.id == "fang" and target is not None:
            if any(debuff.duration > 0 for debuff in target.debuffs):
                bias += 5.0
        if spec.kind == "spell" and spec.effect_id == "silver_tongue" and _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref):
            bias += 5.0
        if spec.kind == "ultimate":
            bias += 6.0

    return bias


def _friendly_melee_swap_penalty(battle, actors: list, combo: tuple[ActionSpec, ...]) -> float:
    if not battle.initiative_order:
        determine_initiative_order(battle)
    initiative = {_unit_ref(battle, unit): index for index, unit in enumerate(battle.initiative_order)}
    specs_by_ref = {_unit_ref(battle, actor): spec for actor, spec in zip(actors, combo)}
    penalty = 0.0
    for swap_actor, swap_spec in zip(actors, combo):
        if swap_spec.kind != "swap" or swap_spec.target_ref is None:
            continue
        ally = _find_unit(battle, swap_spec.target_ref)
        if ally is None or ally.ko:
            continue
        swap_index = initiative.get(_unit_ref(battle, swap_actor), 999)
        for moved_actor, new_slot in ((swap_actor, ally.slot), (ally, swap_actor.slot)):
            moved_ref = _unit_ref(battle, moved_actor)
            moved_spec = specs_by_ref.get(moved_ref)
            if moved_spec is None or moved_spec.kind != "strike":
                continue
            if initiative.get(moved_ref, -1) <= swap_index:
                continue
            if moved_actor.primary_weapon.kind == "melee" and new_slot != SLOT_FRONT:
                penalty += 10.0
    return penalty


def _combo_overkill_penalty(
    battle,
    team_num: int,
    actors: list,
    combo: tuple[ActionSpec, ...],
    analysis: RoundAnalysis,
) -> float:
    damage_by_target: dict[tuple[int, str], list[float]] = {}
    for actor, spec in zip(actors, combo):
        if spec.kind not in {"strike", "spell", "ultimate"} or spec.target_ref is None or spec.target_ref[0] == team_num:
            continue
        target = _find_unit(battle, spec.target_ref)
        effect = _spec_effect(actor, spec)
        if target is None or target.ko or effect is None or effect.power <= 0:
            continue
        source_weapon = _strike_weapon_for_spec(actor, spec) if spec.kind == "strike" else _weapon_for_effect(actor, effect)
        damage = _rough_damage(battle, actor, target, effect, weapon=source_weapon)
        if damage <= 0:
            continue
        damage_by_target.setdefault(spec.target_ref, []).append(float(damage))
    penalty = 0.0
    for target_ref, damages in damage_by_target.items():
        if len(damages) < 2:
            continue
        target = _find_unit(battle, target_ref)
        if target is None or target.ko:
            continue
        total_damage = sum(damages)
        overflow = total_damage - target.hp
        local_penalty = 0.0
        if overflow > 0:
            local_penalty += min(6.0, (overflow / max(1, target.hp)) * 3.5 + (len(damages) - 1) * 0.6)
        elif total_damage >= target.hp * 0.85 and len(damage_by_target) == 1:
            local_penalty += 0.75
        if _same_target_slot(battle, target_ref, analysis.priority_target_ref):
            local_penalty *= 0.8
        penalty += local_penalty
    return penalty


def _combo_metrics(battle, team_num: int, actors: list, combo: tuple[ActionSpec, ...], analysis: RoundAnalysis) -> dict[str, float]:
    offense = 0.0
    defense = 0.0
    setup = 0.0
    ultimate = 0.0
    focus = 0.0
    kills = 0.0
    trades = 0.0
    front_break = 0.0
    priority_kill = 0.0
    self_sabotage = 0.0
    overkill = 0.0
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
        elif spec.kind == "skip":
            offense -= 0.8
            defense -= 0.8
        if _same_target_slot(battle, spec.target_ref, analysis.priority_target_ref) and spec.kind in {"strike", "spell", "ultimate"}:
            focus += 1.5
        if spec.target_ref is not None and spec.target_ref[0] != team_num and spec.kind in {"strike", "spell", "ultimate"}:
            focused_enemy_targets.append(spec.target_ref)
        if spec.target_ref is not None and spec.target_ref[0] == team_num:
            defense += 0.5
        if target is not None and target.hp <= max(40, int(target.max_hp * 0.28)):
            offense += 0.8
    focused_enemy_slots = {(ref[0], _ref_slot(battle, ref)) for ref in focused_enemy_targets if _ref_slot(battle, ref) is not None}
    if len(focused_enemy_targets) >= 2 and len(focused_enemy_slots) == 1:
        focus += 2.0
    self_sabotage += _friendly_melee_swap_penalty(battle, actors, combo)
    overkill += _combo_overkill_penalty(battle, team_num, actors, combo, analysis)
    return {
        "offense": offense,
        "defense": defense,
        "setup": setup,
        "ultimate": ultimate,
        "focus": focus,
        "kills": kills,
        "trades": trades,
        "front_break": front_break,
        "priority_kill": priority_kill,
        "self_sabotage": self_sabotage,
        "overkill": overkill,
    }


def _profile_score(metrics: dict[str, float], profile: str) -> float:
    if profile == "aggressive":
        return (
            metrics["offense"] * 1.25
            + metrics["focus"] * 1.2
            + metrics["ultimate"] * 0.35
            + metrics["kills"] * 11.0
            + metrics["front_break"] * 4.5
            + metrics["priority_kill"] * 6.0
            - metrics["trades"] * 7.0
            - metrics["overkill"] * 2.8
            - metrics["self_sabotage"] * 10.0
        )
    if profile == "defensive":
        return (
            metrics["defense"] * 1.35
            + metrics["setup"] * 0.3
            - metrics["offense"] * 0.1
            - metrics["trades"] * 3.5
            - metrics["overkill"] * 1.2
            - metrics["self_sabotage"] * 8.0
        )
    if profile == "setup":
        return (
            metrics["setup"] * 1.35
            + metrics["focus"] * 0.45
            + metrics["kills"] * 1.5
            - metrics["trades"] * 4.0
            - metrics["overkill"] * 1.8
            - metrics["self_sabotage"] * 8.0
        )
    if profile == "ultimate":
        return (
            metrics["ultimate"] * 1.5
            + metrics["offense"] * 0.4
            + metrics["kills"] * 6.0
            + metrics["priority_kill"] * 3.5
            - metrics["trades"] * 5.0
            - metrics["overkill"] * 1.6
            - metrics["self_sabotage"] * 9.0
        )
    return (
        metrics["offense"]
        + metrics["defense"]
        + metrics["setup"]
        + metrics["focus"]
        + metrics["ultimate"]
        + metrics["kills"] * 8.0
        + metrics["front_break"] * 3.0
        + metrics["priority_kill"] * 4.0
        - metrics["trades"] * 5.0
        - metrics["overkill"] * 2.0
        - metrics["self_sabotage"] * 9.0
    )


def _profile_weights_for_plan(plan_kind: str) -> dict[str, float]:
    if plan_kind == "kill":
        return {"base": 0.22, "aggressive": 0.48, "setup": 0.04, "defensive": 0.04, "ultimate": 0.22}
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
        if not _spec_is_legal(battle, actor, spec):
            continue
        if _spec_has_hard_invalid_pre_resolution_risk(battle, actor, spec):
            continue
        score = _simulate_spec_delta(battle, player_num_for_actor(battle, actor), actor_ref, spec)
        score += _plan_bias(battle, actor, spec, analysis)
        scored.append((score, spec))
    if not scored:
        scored = [(0.0, ActionSpec(kind="skip", bonus=bonus))]
    scored.sort(key=lambda item: item[0], reverse=True)
    keep = LOCAL_KEEP.get(difficulty, 4)
    diverse: list[ActionSpec] = []
    seen_specs: set[ActionSpec] = set()
    for kind in ("ultimate", "spell", "swap", "switch", "strike", "skip"):
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
    # Always pin the best attack on each killable enemy — ensures kill routes are never pruned
    # by LOCAL_KEEP before the team combo evaluator can see them
    if analysis.killable_enemy_refs and not bonus:
        for killable_ref in analysis.killable_enemy_refs:
            killable_unit = _find_unit(battle, killable_ref)
            if killable_unit is None or killable_unit.ko:
                continue
            best_kill_spec = next(
                (
                    spec
                    for _score, spec in scored
                    if spec.kind in {"strike", "spell", "ultimate"}
                    and _same_target_slot(battle, spec.target_ref, killable_ref)
                    and spec not in seen_specs
                ),
                None,
            )
            if best_kill_spec is not None:
                diverse.append(best_kill_spec)
                seen_specs.add(best_kill_spec)
    if not any(item.kind == "skip" for item in diverse):
        skip_spec = next((item[1] for item in scored if item[1].kind == "skip"), ActionSpec(kind="skip", bonus=bonus))
        diverse.append(skip_spec)
    return diverse[: max(keep, min(len(diverse), keep + 1))]


def _queue_team_plan(sim_battle, team_num: int, specs_by_ref: dict[tuple[int, str], ActionSpec], *, bonus: bool):
    for actor in _team_units_in_order(sim_battle, team_num):
        actor.queued_action = None
        actor.queued_bonus_action = None
        spec = _sanitize_spec(sim_battle, actor, specs_by_ref.get(_unit_ref(sim_battle, actor)), bonus=bonus)
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
        enemy_before = battle.get_enemy(team_num)
        own_before = battle.get_team(team_num)
        enemy_alive_before = sum(1 for unit in enemy_before.members if not unit.ko)
        own_alive_before = sum(1 for unit in own_before.members if not unit.ko)
        enemy_front_before = enemy_before.frontline()
        sim = copy.deepcopy(battle)
        log_start = len(sim.log)
        _queue_team_plan(sim, team_num, specs_by_ref, bonus=bonus)
        if bonus:
            resolve_bonus_phase(sim)
        else:
            resolve_action_phase(sim)
        score = evaluate_battle_state(sim, team_num) - base_value
        metrics = _combo_metrics(battle, team_num, actors, combo, analysis)
        failure_penalty, failure_count = _plan_failure_penalty(sim.log[log_start:])
        score -= failure_penalty * 2.0
        score -= failure_count * 18.0
        metrics["self_sabotage"] = failure_count
        sim_enemy = sim.get_enemy(team_num)
        sim_own = sim.get_team(team_num)
        enemy_kos = enemy_alive_before - sum(1 for unit in sim_enemy.members if not unit.ko)
        own_losses = own_alive_before - sum(1 for unit in sim_own.members if not unit.ko)
        priority_kill = 0.0
        if analysis.priority_target_ref is not None:
            sim_priority = _find_unit(sim, analysis.priority_target_ref)
            if sim_priority is not None and sim_priority.ko:
                priority_kill = 1.0
        front_break = 0.0
        if enemy_front_before is not None:
            sim_enemy_front_before = _find_unit(sim, _unit_ref(battle, enemy_front_before))
            if sim_enemy_front_before is not None and sim_enemy_front_before.ko:
                front_break = 1.0
        metrics["kills"] = float(enemy_kos)
        metrics["trades"] = float(own_losses)
        metrics["priority_kill"] = priority_kill
        metrics["front_break"] = front_break
        score += enemy_kos * 34.0
        score += priority_kill * 10.0
        score += front_break * 8.0
        score -= own_losses * 38.0
        score += metrics["focus"] * 1.2
        score += metrics["ultimate"] * 0.25
        metrics["intrinsic_failures"] = failure_count
        metrics["intrinsic_failure_penalty"] = failure_penalty
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


def _get_enemy_plans(
    battle,
    team_num: int,
    difficulty: str,
) -> list[tuple[float, dict[tuple[int, str], ActionSpec]]]:
    """Generate weighted enemy plan candidates for simultaneous simulation.
    Full enumeration when exactly 1 enemy is alive (every legal action considered).
    Beam-searched candidates for 2–3 alive enemies.
    """
    enemy_team_num = 2 if team_num == 1 else 1
    alive_enemies = battle.get_team(enemy_team_num).alive()
    if not alive_enemies:
        return []

    # Full enumeration: sole remaining enemy — try every legal action
    if len(alive_enemies) == 1:
        enemy_actor = alive_enemies[0]
        enemy_ref = _unit_ref(battle, enemy_actor)
        all_specs = [
            spec for spec in available_action_specs(battle, enemy_actor, bonus=False)
            if _spec_is_legal(battle, enemy_actor, spec)
        ]
        if not all_specs:
            return []
        w = 1.0 / len(all_specs)
        return [(w, {enemy_ref: spec}) for spec in all_specs]

    # Beam-searched candidates for 2–3 alive enemies (LOCAL_KEEP × actors → TEAM_KEEP plans)
    predictor_difficulty = "normal" if difficulty in {"easy", "normal", "hard"} else "hard"
    analysis, enemy_candidates = _rank_team_plan_candidates(
        battle, enemy_team_num, bonus=False, difficulty=predictor_difficulty,
    )
    if not enemy_candidates:
        return []
    return _select_likely_plan_packages(enemy_candidates, analysis, predictor_difficulty)


def _simultaneous_plan_score(
    battle,
    team_num: int,
    own_specs_by_ref: dict[tuple[int, str], ActionSpec],
    enemy_plans: list[tuple[float, dict[tuple[int, str], ActionSpec]]],
    *,
    difficulty: str = "hard",
) -> float:
    """Score an own plan by simulating it simultaneously with each enemy plan.
    Both teams are queued together and resolved in true initiative order.
    Returns a blended expected-value / minimax score.
    """
    enemy_team_num = 2 if team_num == 1 else 1
    weighted_scores: list[tuple[float, float]] = []
    actor_names = [unit.name for unit in battle.get_team(team_num).members]
    for weight, enemy_specs_by_ref in enemy_plans:
        sim = copy.deepcopy(battle)
        log_start = len(sim.log)
        _queue_team_plan(sim, team_num, own_specs_by_ref, bonus=False)
        _queue_team_plan(sim, enemy_team_num, enemy_specs_by_ref, bonus=False)
        resolve_action_phase(sim)
        sim_score = evaluate_battle_state(sim, team_num)
        failure_penalty, failure_count = _team_failure_penalty(sim.log[log_start:], actor_names)
        sim_score -= failure_penalty * 2.5
        sim_score -= failure_count * 24.0
        weighted_scores.append((weight, sim_score))
    if not weighted_scores:
        return evaluate_battle_state(battle, team_num)
    total_weight = sum(w for w, _ in weighted_scores)
    expected = sum(w * s for w, s in weighted_scores) / max(total_weight, 1e-9)
    worst = min(s for _, s in weighted_scores)
    # Hard/ranked: blend a conservative minimax component to avoid catastrophic misplays
    minimax_weight = 0.55 if difficulty in {"hard", "ranked"} else 0.0
    return expected * (1.0 - minimax_weight) + worst * minimax_weight


def _simulated_plan_failure_profile(
    battle,
    team_num: int,
    own_specs_by_ref: dict[tuple[int, str], ActionSpec],
    enemy_plans: list[tuple[float, dict[tuple[int, str], ActionSpec]]],
) -> tuple[float, float]:
    if not enemy_plans:
        return 0.0, 0.0
    enemy_team_num = 2 if team_num == 1 else 1
    actor_names = [unit.name for unit in battle.get_team(team_num).members]
    weighted_failures = 0.0
    weighted_penalty = 0.0
    for weight, enemy_specs_by_ref in enemy_plans:
        sim = copy.deepcopy(battle)
        log_start = len(sim.log)
        _queue_team_plan(sim, team_num, own_specs_by_ref, bonus=False)
        _queue_team_plan(sim, enemy_team_num, enemy_specs_by_ref, bonus=False)
        resolve_action_phase(sim)
        failure_penalty, failure_count = _team_failure_penalty(sim.log[log_start:], actor_names)
        weighted_failures += failure_count * weight
        weighted_penalty += failure_penalty * weight
    return weighted_failures, weighted_penalty


def choose_team_plan(
    battle,
    team_num: int,
    *,
    bonus: bool = False,
    difficulty: str = "hard",
    rng: random.Random | None = None,
) -> dict[tuple[int, str], ActionSpec]:
    rng = rng or random.Random()
    analysis, ranked_candidates = _rank_team_plan_candidates(
        battle, team_num, bonus=bonus, difficulty=difficulty,
    )
    if not ranked_candidates:
        return {}

    # Build enemy plan set once — reused across all own candidate evaluations.
    # For bonus phase there is no concurrent enemy action to model.
    enemy_plans: list[tuple[float, dict[tuple[int, str], ActionSpec]]] = []
    if not bonus:
        enemy_plans = _get_enemy_plans(battle, team_num, difficulty)

    base_value = evaluate_battle_state(battle, team_num)
    rescored: list[tuple[float, dict[tuple[int, str], ActionSpec], dict[str, float]]] = []
    for score, specs_by_ref, metrics in ranked_candidates:
        # Profile/race adjustments
        profile_adj = 0.0
        if analysis.plan_kind in {"kill", "ultimate"}:
            profile_adj += _profile_score(metrics, "aggressive") * 0.15
        elif analysis.plan_kind == "stabilize":
            profile_adj += _profile_score(metrics, "defensive") * 0.18
        elif analysis.plan_kind in {"setup", "pivot"}:
            profile_adj += _profile_score(metrics, "setup") * 0.16
        profile_adj += _race_profile_adjustment(analysis, metrics)

        if enemy_plans:
            # Simultaneous simulation: both teams queued and resolved in initiative order
            sim_score = _simultaneous_plan_score(
                battle, team_num, specs_by_ref, enemy_plans, difficulty=difficulty,
            )
            final_score = (sim_score - base_value) + profile_adj
        else:
            # Bonus phase: no concurrent enemy actions — use isolated own-team score
            final_score = score + profile_adj

        rescored.append((final_score, specs_by_ref, metrics))

    rescored.sort(key=lambda item: item[0], reverse=True)
    top_score = rescored[0][0]
    threshold = 6.0 if difficulty in {"easy", "normal"} else 4.0
    band = [item for item in rescored if top_score - item[0] <= threshold]
    if len(band) > 1:
        min_intrinsic_failures = min(item[2].get("intrinsic_failures", 0.0) for item in band)
        intrinsic_filtered = [
            item for item in band if item[2].get("intrinsic_failures", 0.0) <= min_intrinsic_failures + 1e-6
        ]
        if intrinsic_filtered:
            min_intrinsic_penalty = min(
                item[2].get("intrinsic_failure_penalty", 0.0) for item in intrinsic_filtered
            )
            tighter = [
                item
                for item in intrinsic_filtered
                if item[2].get("intrinsic_failure_penalty", 0.0) <= min_intrinsic_penalty + 1e-6
            ]
            if tighter:
                band = tighter
    if enemy_plans and len(band) > 1:
        risk_scored_band: list[tuple[float, float, dict[tuple[int, str], ActionSpec], dict[str, float]]] = []
        for score, specs_by_ref, metrics in band:
            plan_risk = 0.0
            for actor_ref, spec in specs_by_ref.items():
                plan_risk += _pre_resolution_enemy_risk(battle, team_num, actor_ref, spec)
            risk_scored_band.append((plan_risk, score, specs_by_ref, metrics))
        best_risk = min(item[0] for item in risk_scored_band)
        filtered = [
            (score, specs_by_ref, metrics)
            for risk, score, specs_by_ref, metrics in risk_scored_band
            if risk <= best_risk + 0.5
        ]
        if filtered:
            filtered.sort(key=lambda item: item[0], reverse=True)
            band = filtered
    if enemy_plans and len(band) > 1:
        failure_scored_band: list[tuple[float, float, float, dict[tuple[int, str], ActionSpec], dict[str, float]]] = []
        for score, specs_by_ref, metrics in band:
            weighted_failures, weighted_penalty = _simulated_plan_failure_profile(
                battle, team_num, specs_by_ref, enemy_plans
            )
            failure_scored_band.append((weighted_failures, weighted_penalty, score, specs_by_ref, metrics))
        min_failures = min(item[0] for item in failure_scored_band)
        filtered = [item for item in failure_scored_band if item[0] <= min_failures + 1e-6]
        min_penalty = min(item[1] for item in filtered)
        filtered = [item for item in filtered if item[1] <= min_penalty + 1e-6]
        band = sorted(
            ((score, specs_by_ref, metrics) for _fails, _penalty, score, specs_by_ref, metrics in filtered),
            key=lambda item: item[0],
            reverse=True,
        )
    if difficulty == "ranked" and len(band) > 1 and rng.random() < 0.8:
        return band[0][1]
    return rng.choice(band)[1]


def queue_team_plan(battle, team_num: int, *, bonus: bool = False, difficulty: str = "hard", rng: random.Random | None = None) -> dict[tuple[int, str], ActionSpec]:
    plan = choose_team_plan(battle, team_num, bonus=bonus, difficulty=difficulty, rng=rng)
    sanitized_plan: dict[tuple[int, str], ActionSpec] = {}
    for actor in _team_units_in_order(battle, team_num):
        ref = _unit_ref(battle, actor)
        spec = _sanitize_spec(battle, actor, plan.get(ref), bonus=bonus)
        sanitized_plan[ref] = spec
        _queue_spec(actor, battle, spec)
    return sanitized_plan


def queue_both_teams_for_phase(battle, *, bonus: bool = False, difficulty1: str = "hard", difficulty2: str = "hard", rng: random.Random | None = None):
    rng = rng or random.Random()
    plan1 = queue_team_plan(battle, 1, bonus=bonus, difficulty=difficulty1, rng=rng)
    plan2 = queue_team_plan(battle, 2, bonus=bonus, difficulty=difficulty2, rng=rng)
    return plan1, plan2
