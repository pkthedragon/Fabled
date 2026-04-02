from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, permutations, product
from typing import Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_tables import matchup_value, pair_synergy_value, team_archetype_bonus
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
        return 0
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


def _weapon_fit_score(adventurer_id: str, weapon_id: str, slot: str) -> int:
    profile = ADVENTURER_AI[adventurer_id]
    adventurer = ADVENTURERS_BY_ID[adventurer_id]
    weapon = next(item for item in adventurer.signature_weapons if item.id == weapon_id)
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
    adventurer = ADVENTURERS_BY_ID[adventurer_id]
    weapon = next(item for item in adventurer.signature_weapons if item.id == weapon_id)
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


def _team_need_tags(adventurer_ids: tuple[str, ...]) -> set[str]:
    roles: set[str] = set()
    for adventurer_id in adventurer_ids:
        roles.update(ADVENTURER_AI[adventurer_id].role_tags)
    needs: set[str] = set()
    if "healer" not in roles:
        needs.add("sustain")
    if "primary_tank" not in roles and "anti_burst" not in roles:
        needs.add("anti_burst")
    if "backline_reach" not in roles and "spread_pressure" not in roles:
        needs.add("reach")
    if "root_enabler" not in roles and "shock_engine" not in roles and "expose_enabler" not in roles and "burn_enabler" not in roles:
        needs.add("setup")
    return needs


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
    value = float(profile.base_power)
    value += _slot_weight(profile, slot) * 0.45
    value += _class_fit_score(adventurer_id, class_name, slot)
    value += _skill_fit_score(adventurer_id, class_name, class_skill_id, slot, primary_weapon_id)
    value += _weapon_fit_score(adventurer_id, primary_weapon_id, slot)
    value += _artifact_fit_score(adventurer_id, artifact_id, team_need_tags=team_need_tags, enemy_ids=enemy_ids)
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
    return tuple(classes[:3])


def _candidate_skill_ids(class_name: str, adventurer_id: str) -> tuple[str, ...]:
    profile = ADVENTURER_AI[adventurer_id]
    preferred = profile.preferred_skills.get(class_name, DEFAULT_CLASS_SKILL_ORDER[class_name])
    return tuple(preferred[:2])


def _candidate_artifacts(class_name: str, adventurer_id: str, team_need_tags: set[str], enemy_ids: tuple[str, ...]) -> tuple[Optional[str], ...]:
    compatible = list(compatible_artifact_ids(class_name))
    if not compatible:
        return (None,)
    compatible.sort(
        key=lambda artifact_id: _artifact_fit_score(adventurer_id, artifact_id, team_need_tags=team_need_tags, enemy_ids=enemy_ids),
        reverse=True,
    )
    return tuple(compatible[:4])


def generate_member_builds(
    adventurer_id: str,
    slot: str,
    *,
    team_ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
    max_builds: int = 10,
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
    if "backline_reach" in roles or "spread_pressure" in roles or "root_enabler" in roles or "shock_engine" in roles:
        value += 12
    else:
        warnings.append("Limited backline access.")
        value -= 18
    if "healer" in roles or "guard_support" in roles or "anti_burst" in roles:
        value += 12
    else:
        warnings.append("Low sustain or mitigation.")
        value -= 18
    if any(tag in roles for tag in ("shock_engine", "root_enabler", "burn_enabler", "expose_enabler", "burst_finisher", "swap_engine", "tempo_engine")):
        value += 10
    else:
        warnings.append("No clear win condition.")
        value -= 20
    reliability = sum(profile.reliability for profile in profiles) / len(profiles)
    complexity = sum(profile.complexity for profile in profiles) / len(profiles)
    value += reliability * 0.18
    value -= max(0.0, (complexity - 65)) * 0.12
    pair_bonus = 0
    for left_id, right_id in combinations(adventurer_ids, 2):
        pair_bonus += pair_synergy_value(left_id, right_id)
    value += pair_bonus
    archetype_bonus, archetypes = team_archetype_bonus(adventurer_ids)
    value += archetype_bonus
    return value, tuple(dict.fromkeys(warnings + list(archetypes)))


def _matchup_score(adventurer_ids: tuple[str, ...], enemy_ids: tuple[str, ...]) -> float:
    if not enemy_ids:
        return 0.0
    value = 0.0
    for adventurer_id in adventurer_ids:
        profile = ADVENTURER_AI[adventurer_id]
        for enemy_id in enemy_ids:
            value += matchup_value(profile, ADVENTURER_AI[enemy_id])
    return value * 0.35


@lru_cache(maxsize=1024)
def _solve_team_loadout_cached(
    adventurer_ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
    mode: str,
    seat: int,
) -> TeamLoadout:
    best_members: Optional[tuple[MemberBuild, ...]] = None
    best_score = float("-inf")
    best_warnings: tuple[str, ...] = ()
    best_archetypes: tuple[str, ...] = ()
    ids = _sorted_ids(adventurer_ids)

    for slot_assignment in permutations(SLOT_ORDER, len(ids)):
        per_member_options: list[tuple[MemberBuild, ...]] = []
        for adventurer_id, slot in zip(ids, slot_assignment):
            per_member_options.append(
                generate_member_builds(
                    adventurer_id,
                    slot,
                    team_ids=ids,
                    enemy_ids=enemy_ids,
                )
            )
        for candidate_tuple in product(*per_member_options):
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
        raise ValueError(f"Could not solve legal loadout for {adventurer_ids}.")
    return TeamLoadout(members=best_members, score=best_score, archetypes=best_archetypes, warnings=best_warnings)


def solve_team_loadout(
    adventurer_ids: tuple[str, ...] | list[str],
    *,
    enemy_ids: tuple[str, ...] | list[str] = (),
    mode: str = "quest",
    seat: int = 1,
) -> TeamLoadout:
    return _solve_team_loadout_cached(_sorted_ids(tuple(adventurer_ids)), _sorted_ids(tuple(enemy_ids)), mode, seat)
