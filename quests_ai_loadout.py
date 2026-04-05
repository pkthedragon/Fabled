from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, permutations, product
from typing import Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_tables import (
    counter_fragility_penalty,
    counterplay_score,
    enemy_archetypes,
    matchup_value,
    pair_synergy_value,
    plan_reliability_score,
    team_archetype_bonus,
    team_style_scores,
)
from quests_ai_tags import (
    ADVENTURER_AI,
    ARTIFACT_TAGS,
    CLASS_SKILL_TAGS,
    DEFAULT_CLASS_SKILL_ORDER,
    artifact_preference_score,
    skill_preference_score,
    weapon_preference_score,
)
from quests_ruleset_data import ADVENTURERS_BY_ID, ARTIFACTS, CLASS_SKILLS


SLOT_ORDER = (SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT)


@dataclass(frozen=True)
class MemberBuild:
    adventurer_id: str
    slot: str
    class_name: str
    class_skill_id: str
    primary_weapon_id: str
    artifact_id: Optional[str]
    score: float


@dataclass(frozen=True)
class TeamLoadout:
    members: tuple[MemberBuild, ...]
    score: float
    archetypes: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def team_ids(self) -> tuple[str, ...]:
        return tuple(member.adventurer_id for member in self.members)


def compatible_artifact_ids(class_name: str) -> tuple[str, ...]:
    return tuple(artifact.id for artifact in ARTIFACTS if class_name in artifact.attunement)


def _sorted_ids(adventurer_ids: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted(adventurer_ids))


def _slot_weight(profile, slot: str) -> int:
    return profile.position_scores[slot]


def _artifact_fit_score(
    adventurer_id: str,
    artifact_id: Optional[str],
    *,
    team_need_tags: set[str],
    enemy_ids: tuple[str, ...],
) -> int:
    if artifact_id is None:
        return 2 if "sustain" not in team_need_tags and "anti_burst" not in team_need_tags else 0
    profile = ADVENTURER_AI[adventurer_id]
    value = artifact_preference_score(profile, artifact_id)
    artifact_tags = ARTIFACT_TAGS.get(artifact_id, set())
    for need in team_need_tags:
        if need in artifact_tags:
            value += 5
    enemy_tags = set()
    for enemy_id in enemy_ids:
        enemy = ADVENTURER_AI[enemy_id]
        enemy_tags.update(enemy.matchup_tags)
        enemy_tags.update(enemy.role_tags)
    if "guard_heavy" in enemy_tags and "anti_guard" in artifact_tags:
        value += 8
    if "spell_heavy" in enemy_tags and "anti_spell" in artifact_tags:
        value += 8
    if "fragile_backline" in enemy_tags and {"reach", "ammo", "damage", "spotlight"} & artifact_tags:
        value += 4
    if "burst_focus" in enemy_tags and {"rescue", "anti_burst", "guard"} & artifact_tags:
        value += 5
    return value


def _class_fit_score(adventurer_id: str, class_name: str, slot: str) -> int:
    profile = ADVENTURER_AI[adventurer_id]
    if class_name in profile.preferred_classes:
        value = max(0, 16 - profile.preferred_classes.index(class_name) * 5)
    else:
        value = 4
    if slot == SLOT_FRONT and class_name in {"Warden", "Fighter"}:
        value += 4
    if slot != SLOT_FRONT and class_name in {"Ranger", "Mage", "Cleric", "Rogue"}:
        value += 3
    return value


def _weapon_def(adventurer_id: str, weapon_id: str):
    adventurer = ADVENTURERS_BY_ID[adventurer_id]
    return next(item for item in adventurer.signature_weapons if item.id == weapon_id)


def _weapon_fit_score(adventurer_id: str, weapon_id: str, slot: str) -> int:
    profile = ADVENTURER_AI[adventurer_id]
    weapon = _weapon_def(adventurer_id, weapon_id)
    value = weapon_preference_score(profile, weapon_id)
    if weapon.kind == "melee":
        value += 8 if slot == SLOT_FRONT else -14
    elif weapon.kind == "magic":
        value += 5 if slot == SLOT_FRONT else 3
    elif weapon.kind == "ranged":
        value += 2 if slot == SLOT_FRONT else 6
    if weapon.strike.spread:
        value += 3
    if weapon.spells:
        value += 2
    return value


def _skill_fit_score(adventurer_id: str, class_name: str, skill_id: str, slot: str, weapon_id: str) -> int:
    profile = ADVENTURER_AI[adventurer_id]
    weapon = _weapon_def(adventurer_id, weapon_id)
    value = skill_preference_score(profile, class_name, skill_id)
    skill_tags = CLASS_SKILL_TAGS.get(skill_id, set())
    if weapon.kind == "melee" and "melee" in skill_tags:
        value += 4
    if weapon.kind == "magic" and "magic" in skill_tags:
        value += 4
    if weapon.kind == "ranged" and "ranged" in skill_tags:
        value += 4
    if slot == SLOT_FRONT and "frontline" in skill_tags:
        value += 3
    if slot != SLOT_FRONT and "swap" in skill_tags:
        value += 2
    return value


def _build_tags(
    adventurer_id: str,
    class_name: str,
    class_skill_id: str,
    primary_weapon_id: str,
    artifact_id: Optional[str],
    slot: str,
) -> set[str]:
    profile = ADVENTURER_AI[adventurer_id]
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    tags = set(profile.role_tags) | set(profile.shell_tags) | set(profile.matchup_tags)
    tags.update(CLASS_SKILL_TAGS.get(class_skill_id, set()))
    if artifact_id is not None:
        tags.update(ARTIFACT_TAGS.get(artifact_id, set()))
    tags.add(weapon.kind)
    tags.add(class_name.lower())
    if slot == SLOT_FRONT:
        tags.add("frontline_slot")
    else:
        tags.add("backline_slot")
    if weapon.kind in {"ranged", "magic"}:
        tags.add("reach")
    if weapon.kind == "ranged":
        tags.add("ranged_pressure")
    if weapon.kind == "magic":
        tags.add("spell")
        tags.add("magic_pressure")
    if weapon.kind == "melee":
        tags.add("melee_pressure")
    if slot != SLOT_FRONT and weapon.kind == "melee":
        tags.add("awkward_slot")
    if slot != SLOT_FRONT and weapon.kind in {"ranged", "magic"}:
        tags.add("safe_backline")
    if class_name == "Cleric":
        tags.add("sustain")
    if class_skill_id == "medic":
        tags.add("anti_status")
        tags.add("cleanse")
    if class_skill_id == "protector":
        tags.add("guard")
    if class_skill_id == "healer":
        tags.add("healing")
    if class_skill_id == "tactical":
        tags.add("switch")
        tags.add("resource")
        tags.add("swap")
    if class_skill_id == "archmage":
        tags.add("spell_tempo")
        tags.add("resource")
    if class_skill_id == "armed":
        tags.add("ammo")
        tags.add("resource")
    if class_skill_id == "covert":
        tags.add("swap")
        tags.add("mobility")
    if class_skill_id == "vanguard":
        tags.add("reach")
        tags.add("bonus_action")
    return tags


def _team_need_tags(adventurer_ids: tuple[str, ...]) -> set[str]:
    styles = team_style_scores(adventurer_ids)
    needs: set[str] = set()
    if styles.get("sustain", 0.0) < 8.0:
        needs.add("sustain")
    if styles.get("frontline", 0.0) < 12.0:
        needs.add("frontline")
    if styles.get("frontline", 0.0) < 10.0 and styles.get("sustain", 0.0) < 10.0:
        needs.add("anti_burst")
    if styles.get("backline_pressure", 0.0) < 8.0:
        needs.add("reach")
    if styles.get("control", 0.0) < 8.0 and styles.get("burst", 0.0) < 8.0:
        needs.add("setup")
    if styles.get("tempo", 0.0) < 7.0:
        needs.add("tempo")
    if styles.get("resource", 0.0) < 6.0:
        needs.add("resource")
    return needs


def _formation_fit_score(adventurer_id: str, slot: str, primary_weapon_id: str) -> float:
    profile = ADVENTURER_AI[adventurer_id]
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    base_speed = ADVENTURERS_BY_ID[adventurer_id].speed - (30 if slot != SLOT_FRONT else 0)
    roles = set(profile.role_tags)
    value = profile.position_scores[slot] * 0.22
    if slot == SLOT_FRONT and {"primary_tank", "frontline_ready", "bruiser", "anti_burst"} & roles:
        value += 6.0
    if slot == SLOT_BACK_RIGHT and "fragile" in roles:
        value += 4.0
    if slot == SLOT_BACK_LEFT and profile.position_scores[SLOT_FRONT] >= 72:
        value += 4.5
    if slot != SLOT_FRONT and weapon.kind == "melee" and "melee_reach" not in roles:
        value -= 10.0
    if slot == SLOT_FRONT and weapon.kind == "ranged" and "frontline_pivot" not in roles and "primary_tank" not in roles:
        value -= 5.0
    if slot != SLOT_FRONT and {"tempo_engine", "bonus_action_user", "swap_engine"} & roles and base_speed < 32:
        value -= 6.0
    return value


def _resource_fit_score(
    adventurer_id: str,
    class_skill_id: str,
    primary_weapon_id: str,
    artifact_id: Optional[str],
) -> float:
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    artifact_tags = ARTIFACT_TAGS.get(artifact_id, set()) if artifact_id is not None else set()
    skill_tags = CLASS_SKILL_TAGS.get(class_skill_id, set())
    value = 0.0
    if weapon.kind == "ranged":
        if "ammo" in skill_tags or "switch" in skill_tags:
            value += 6.0
        if {"ammo", "reach"} & artifact_tags:
            value += 5.0
    if weapon.kind == "magic":
        if {"magic", "spell_tempo", "frontline"} & skill_tags:
            value += 5.0
        if {"magic", "ultimate", "spell_tempo"} & artifact_tags:
            value += 4.0
    if weapon.kind == "melee" and {"burst", "reach", "bonus_action"} & skill_tags:
        value += 4.0
    if weapon.spells and ("spell_tempo" in skill_tags or "ultimate" in artifact_tags):
        value += 3.0
    if artifact_id is None and weapon.kind == "melee":
        value += 1.5
    return value


def _team_fit_score(
    adventurer_id: str,
    build_tags: set[str],
    *,
    team_ids: tuple[str, ...],
    team_need_tags: set[str],
) -> float:
    value = 0.0
    if "sustain" in team_need_tags and {"healer", "healing", "sustain", "guard_support", "guard"} & build_tags:
        value += 8.0
    if "frontline" in team_need_tags and {"primary_tank", "anti_burst", "frontline_ready", "frontline_slot"} & build_tags:
        value += 8.0
    if "anti_burst" in team_need_tags and {"anti_burst", "guard_support", "guard", "rescue", "death_insurance"} & build_tags:
        value += 7.0
    if "reach" in team_need_tags and {"backline_reach", "reach", "spread_pressure", "spotlight_enabler"} & build_tags:
        value += 8.0
    if "setup" in team_need_tags and {"shock_engine", "root_enabler", "expose_enabler", "burn_enabler", "spotlight_enabler"} & build_tags:
        value += 7.0
    if "tempo" in team_need_tags and {"tempo_engine", "bonus_action_user", "switch", "swap", "spell_tempo"} & build_tags:
        value += 6.0
    if "resource" in team_need_tags and {"ammo", "resource", "switch", "spell_tempo"} & build_tags:
        value += 5.0
    for teammate_id in team_ids:
        if teammate_id == adventurer_id:
            continue
        value += pair_synergy_value(adventurer_id, teammate_id) * 0.10
    return value


def _synergy_fit_score(adventurer_id: str, build_tags: set[str], team_ids: tuple[str, ...]) -> float:
    value = 0.0
    teammate_roles: set[str] = set()
    for teammate_id in team_ids:
        if teammate_id == adventurer_id:
            continue
        teammate_roles.update(ADVENTURER_AI[teammate_id].role_tags)
    if "shock_engine" in build_tags and "shock_payoff" in teammate_roles:
        value += 7.0
    if "shock_payoff" in build_tags and "shock_engine" in teammate_roles:
        value += 7.0
    if "root_enabler" in build_tags and ({"root_payoff", "backline_reach"} & teammate_roles):
        value += 7.0
    if "root_payoff" in build_tags and "root_enabler" in teammate_roles:
        value += 6.0
    if "burn_enabler" in build_tags and "burn_payoff" in teammate_roles:
        value += 7.0
    if "burn_payoff" in build_tags and "burn_enabler" in teammate_roles:
        value += 6.0
    if "expose_enabler" in build_tags and "burst_finisher" in teammate_roles:
        value += 7.0
    if "burst_finisher" in build_tags and "expose_enabler" in teammate_roles:
        value += 6.0
    if "spotlight_enabler" in build_tags and ({"backline_reach", "melee_reach", "burst_finisher"} & teammate_roles):
        value += 5.0
    if "primary_tank" in build_tags and "fragile" in teammate_roles:
        value += 6.0
    if {"healer", "guard_support", "carry_support"} & build_tags and ({"fragile", "burst_finisher", "magic_carry"} & teammate_roles):
        value += 5.0
    if {"swap_engine", "mobility"} & build_tags and ({"carry_support", "backline_reach", "tempo_engine"} & teammate_roles):
        value += 4.0
    return value


def _matchup_fit_score(
    adventurer_id: str,
    slot: str,
    class_name: str,
    class_skill_id: str,
    primary_weapon_id: str,
    artifact_id: Optional[str],
    *,
    enemy_ids: tuple[str, ...],
) -> float:
    if not enemy_ids:
        return 0.0
    profile = ADVENTURER_AI[adventurer_id]
    build_tags = _build_tags(adventurer_id, class_name, class_skill_id, primary_weapon_id, artifact_id, slot)
    value = 0.0
    for enemy_id in enemy_ids:
        value += matchup_value(profile, ADVENTURER_AI[enemy_id]) * 0.50
    for archetype in enemy_archetypes(enemy_ids):
        if archetype == "fast_burst" and {"primary_tank", "anti_burst", "healer", "guard_support", "guard"} & build_tags:
            value += 8.0
        elif archetype in {"tank_attrition", "sustain_fortress"} and {"frontline_breaker", "anti_guard", "burst_finisher", "stat_manipulator"} & build_tags:
            value += 8.0
        elif archetype == "status_control" and {"anti_status", "cleanse", "healer", "anti_caster"} & build_tags:
            value += 8.0
        elif archetype == "swap_reposition" and {"root_enabler", "anti_swap", "taunt", "anti_displacement"} & build_tags:
            value += 8.0
        elif archetype == "ultimate_race" and {"tempo_engine", "spell_loop", "bonus_action_user", "ultimate", "spell_tempo"} & build_tags:
            value += 7.0
        elif archetype == "backline_carry" and {"backline_reach", "spotlight_enabler", "reach", "ranged_pressure"} & build_tags:
            value += 8.0
        elif archetype == "spread_pressure" and {"healer", "anti_burst", "guard_support", "rescue"} & build_tags:
            value += 6.0
        elif archetype == "tempo_disrupt" and {"reliability", "primary_tank", "guard_support", "anti_caster"} & build_tags:
            value += 5.0
    if class_name == "Cleric" and class_skill_id == "medic" and "status_control" in enemy_archetypes(enemy_ids):
        value += 4.0
    return value


def _local_build_score(
    adventurer_id: str,
    slot: str,
    class_name: str,
    class_skill_id: str,
    primary_weapon_id: str,
    artifact_id: Optional[str],
    *,
    team_ids: tuple[str, ...],
    team_need_tags: set[str],
    enemy_ids: tuple[str, ...],
) -> float:
    profile = ADVENTURER_AI[adventurer_id]
    build_tags = _build_tags(adventurer_id, class_name, class_skill_id, primary_weapon_id, artifact_id, slot)
    self_efficiency = float(profile.base_power) * 0.56
    self_efficiency += _slot_weight(profile, slot) * 0.18
    self_efficiency += _class_fit_score(adventurer_id, class_name, slot)
    self_efficiency += _skill_fit_score(adventurer_id, class_name, class_skill_id, slot, primary_weapon_id)
    self_efficiency += _weapon_fit_score(adventurer_id, primary_weapon_id, slot)
    self_efficiency += _artifact_fit_score(adventurer_id, artifact_id, team_need_tags=team_need_tags, enemy_ids=enemy_ids)
    team_fit = _team_fit_score(adventurer_id, build_tags, team_ids=team_ids, team_need_tags=team_need_tags)
    matchup_fit = _matchup_fit_score(
        adventurer_id,
        slot,
        class_name,
        class_skill_id,
        primary_weapon_id,
        artifact_id,
        enemy_ids=enemy_ids,
    )
    formation_fit = _formation_fit_score(adventurer_id, slot, primary_weapon_id)
    resource_fit = _resource_fit_score(adventurer_id, class_skill_id, primary_weapon_id, artifact_id)
    synergy_fit = _synergy_fit_score(adventurer_id, build_tags, team_ids)
    value = self_efficiency + team_fit + matchup_fit + formation_fit + resource_fit + synergy_fit
    if slot == SLOT_FRONT and "primary_tank" in profile.role_tags:
        value += 10
    if slot == SLOT_BACK_RIGHT and "fragile" in profile.role_tags:
        value += 6
    if slot == SLOT_BACK_LEFT and "frontline_pivot" in profile.role_tags:
        value += 6

    # Encourage March Hare spell-loop loadouts when shock setup exists in the team.
    if adventurer_id == "march_hare":
        team_has_other_shock = any(
            teammate_id != adventurer_id and "shock_engine" in ADVENTURER_AI[teammate_id].role_tags
            for teammate_id in team_ids
        )
        if primary_weapon_id == "cracked_stopwatch":
            value += 10
            if team_has_other_shock:
                value += 8
            if slot != SLOT_FRONT:
                value += 4
        elif primary_weapon_id == "stitch_in_time" and team_has_other_shock:
            value += 3

    return value


def _candidate_classes(adventurer_id: str) -> tuple[str, ...]:
    profile = ADVENTURER_AI[adventurer_id]
    classes = list(dict.fromkeys(profile.preferred_classes + tuple(CLASS_SKILLS.keys())))
    return tuple(classes)


def _candidate_skill_ids(class_name: str, adventurer_id: str) -> tuple[str, ...]:
    profile = ADVENTURER_AI[adventurer_id]
    preferred = profile.preferred_skills.get(class_name, DEFAULT_CLASS_SKILL_ORDER[class_name])
    return tuple(preferred[:3])


def _candidate_artifacts(class_name: str, adventurer_id: str, team_need_tags: set[str], enemy_ids: tuple[str, ...]) -> tuple[Optional[str], ...]:
    compatible = list(compatible_artifact_ids(class_name))
    if not compatible:
        return (None,)
    compatible.sort(
        key=lambda artifact_id: _artifact_fit_score(adventurer_id, artifact_id, team_need_tags=team_need_tags, enemy_ids=enemy_ids),
        reverse=True,
    )
    return tuple([None] + compatible[:4])


def generate_member_builds(
    adventurer_id: str,
    slot: str,
    *,
    team_ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
    max_builds: int = 8,
) -> tuple[MemberBuild, ...]:
    profile = ADVENTURER_AI[adventurer_id]
    team_need_tags = _team_need_tags(team_ids)
    candidates: list[MemberBuild] = []
    weapon_ids = tuple(weapon.id for weapon in ADVENTURERS_BY_ID[adventurer_id].signature_weapons)
    preferred_weapons = tuple(dict.fromkeys(profile.preferred_weapons + weapon_ids))
    for class_name in _candidate_classes(adventurer_id):
        artifact_ids = _candidate_artifacts(class_name, adventurer_id, team_need_tags, enemy_ids)
        for weapon_id in preferred_weapons[:2]:
            for skill_id in _candidate_skill_ids(class_name, adventurer_id):
                for artifact_id in artifact_ids:
                    score = _local_build_score(
                        adventurer_id,
                        slot,
                        class_name,
                        skill_id,
                        weapon_id,
                        artifact_id,
                        team_ids=team_ids,
                        team_need_tags=team_need_tags,
                        enemy_ids=enemy_ids,
                    )
                    candidates.append(
                        MemberBuild(
                            adventurer_id=adventurer_id,
                            slot=slot,
                            class_name=class_name,
                            class_skill_id=skill_id,
                            primary_weapon_id=weapon_id,
                            artifact_id=artifact_id,
                            score=score,
                        )
                    )
    candidates.sort(key=lambda item: item.score, reverse=True)
    unique_keys: set[tuple[str, str, str, Optional[str]]] = set()
    unique_builds: list[MemberBuild] = []
    for candidate in candidates:
        key = (candidate.class_name, candidate.class_skill_id, candidate.primary_weapon_id, candidate.artifact_id)
        if key in unique_keys:
            continue
        unique_keys.add(key)
        unique_builds.append(candidate)
        if len(unique_builds) >= max_builds:
            break
    return tuple(unique_builds)


def _team_coverage_score(members: tuple[MemberBuild, ...]) -> tuple[float, tuple[str, ...]]:
    warnings: list[str] = []
    adventurer_ids = tuple(member.adventurer_id for member in members)
    profiles = [ADVENTURER_AI[member.adventurer_id] for member in members]
    roles = set()
    for profile in profiles:
        roles.update(profile.role_tags)
    styles = team_style_scores(adventurer_ids)
    value = 0.0
    frontline = next((member for member in members if member.slot == SLOT_FRONT), None)
    back_left = next((member for member in members if member.slot == SLOT_BACK_LEFT), None)
    if frontline is None:
        warnings.append("No frontline assigned.")
        value -= 60
    else:
        front_score = ADVENTURER_AI[frontline.adventurer_id].position_scores[SLOT_FRONT]
        if front_score >= 80:
            value += 18
        elif front_score >= 65:
            value += 6
        else:
            warnings.append("Frontline is fragile.")
            value -= 22
    if back_left is not None and ADVENTURER_AI[back_left.adventurer_id].position_scores[SLOT_BACK_LEFT] >= 70:
        value += 10
    else:
        warnings.append("Back-left fallback is weak.")
        value -= 10
    if styles.get("backline_pressure", 0.0) >= 8.0 or "root_enabler" in roles or "shock_engine" in roles:
        value += 12
    else:
        warnings.append("Limited backline access.")
        value -= 18
    if styles.get("sustain", 0.0) >= 8.0 or "healer" in roles or "guard_support" in roles or "anti_burst" in roles:
        value += 12
    else:
        warnings.append("Low sustain or mitigation.")
        value -= 18
    if styles.get("burst", 0.0) >= 8.0 or styles.get("control", 0.0) >= 10.0:
        value += 10
    else:
        warnings.append("No clear win condition.")
        value -= 20
    value += plan_reliability_score(adventurer_ids)
    if styles.get("fragility", 0.0) > styles.get("frontline", 0.0) + styles.get("sustain", 0.0):
        warnings.append("Lineup is fragile if the frontline folds.")
        value -= (styles.get("fragility", 0.0) - (styles.get("frontline", 0.0) + styles.get("sustain", 0.0))) * 0.45
    class_count = len({member.class_name for member in members})
    if class_count == len(members):
        value += 8
    else:
        warnings.append("Duplicate class in lineup.")
        value -= 40
    pair_bonus = 0
    for left_id, right_id in combinations(adventurer_ids, 2):
        pair_bonus += pair_synergy_value(left_id, right_id)
    value += pair_bonus
    archetype_bonus, archetypes = team_archetype_bonus(adventurer_ids)
    value += archetype_bonus
    if styles.get("frontline_hungry", 0.0) >= 2 and styles.get("frontline", 0.0) < 18.0:
        warnings.append("Multiple units compete for frontline value.")
        value -= 8
    melee_backliners = [
        member
        for member in members
        if member.slot != SLOT_FRONT
        and _weapon_def(member.adventurer_id, member.primary_weapon_id).kind == "melee"
        and "melee_reach" not in ADVENTURER_AI[member.adventurer_id].role_tags
    ]
    if melee_backliners:
        warnings.append("A backline melee pick may struggle to access targets.")
        value -= 8 * len(melee_backliners)
    return value, tuple(dict.fromkeys(warnings + list(archetypes)))


def _matchup_score(adventurer_ids: tuple[str, ...], enemy_ids: tuple[str, ...]) -> float:
    if not enemy_ids:
        return 0.0
    value = 0.0
    for adventurer_id in adventurer_ids:
        profile = ADVENTURER_AI[adventurer_id]
        for enemy_id in enemy_ids:
            value += matchup_value(profile, ADVENTURER_AI[enemy_id])
    value += counterplay_score(adventurer_ids, enemy_ids)
    value -= counter_fragility_penalty(adventurer_ids, enemy_ids)
    return value * 0.32


def _solve_with_build_limit(
    ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
    *,
    mode: str,
    seat: int,
    max_builds: int,
) -> tuple[tuple[MemberBuild, ...], float, tuple[str, ...], tuple[str, ...]] | None:
    best_members: Optional[tuple[MemberBuild, ...]] = None
    best_score = float("-inf")
    best_warnings: tuple[str, ...] = ()
    best_archetypes: tuple[str, ...] = ()
    for slot_assignment in permutations(SLOT_ORDER, len(ids)):
        per_member_options: list[tuple[MemberBuild, ...]] = []
        for adventurer_id, slot in zip(ids, slot_assignment):
            per_member_options.append(
                generate_member_builds(
                    adventurer_id,
                    slot,
                    team_ids=ids,
                    enemy_ids=enemy_ids,
                    max_builds=max_builds,
                )
            )
        for candidate_tuple in product(*per_member_options):
            class_names = [member.class_name for member in candidate_tuple]
            if len(class_names) != len(set(class_names)):
                continue
            artifact_ids = [member.artifact_id for member in candidate_tuple if member.artifact_id is not None]
            if len(artifact_ids) != len(set(artifact_ids)):
                continue
            ordered_members = tuple(sorted(candidate_tuple, key=lambda member: SLOT_ORDER.index(member.slot)))
            total = sum(member.score for member in ordered_members)
            coverage_score, warnings = _team_coverage_score(ordered_members)
            total += coverage_score
            total += _matchup_score(tuple(member.adventurer_id for member in ordered_members), enemy_ids)
            if mode == "quest":
                total += 8
            if mode == "bout" and seat == 2:
                swap_roles = {"swap_engine", "frontline_pivot", "backline_reach", "tempo_engine"}
                for member in ordered_members:
                    if swap_roles & set(ADVENTURER_AI[member.adventurer_id].role_tags):
                        total += 2
            archetypes = tuple(item for item in warnings if item.endswith("_shell") or item in {"expose_burst", "tank_carry_support"})
            if total > best_score:
                best_score = total
                best_members = ordered_members
                best_warnings = tuple(item for item in warnings if item not in archetypes)
                best_archetypes = archetypes
    if best_members is None:
        return None
    return best_members, best_score, best_warnings, best_archetypes


@lru_cache(maxsize=1024)
def _solve_team_loadout_cached(
    adventurer_ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
    mode: str,
    seat: int,
) -> TeamLoadout:
    ids = _sorted_ids(adventurer_ids)
    solved = _solve_with_build_limit(ids, enemy_ids, mode=mode, seat=seat, max_builds=8)
    if solved is None:
        solved = _solve_with_build_limit(ids, enemy_ids, mode=mode, seat=seat, max_builds=20)
    if solved is None:
        raise ValueError(f"Could not solve legal loadout for {adventurer_ids}.")
    best_members, best_score, best_warnings, best_archetypes = solved
    return TeamLoadout(members=best_members, score=best_score, archetypes=best_archetypes, warnings=best_warnings)


def solve_team_loadout(
    adventurer_ids: tuple[str, ...] | list[str],
    *,
    enemy_ids: tuple[str, ...] | list[str] = (),
    mode: str = "quest",
    seat: int = 1,
) -> TeamLoadout:
    return _solve_team_loadout_cached(_sorted_ids(tuple(adventurer_ids)), _sorted_ids(tuple(enemy_ids)), mode, seat)
