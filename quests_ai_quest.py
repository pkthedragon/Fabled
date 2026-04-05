from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_loadout import TeamLoadout
from quests_ai_quest_loadout import (
    QuestLoadoutPackage,
    QuestTrioProfile,
    assign_blind_quest_loadouts,
    choose_blind_quest_roster_from_offer,
    summarize_trio_from_package,
)
from quests_ai_tables import counter_fragility_penalty, counterplay_score, matchup_value, pair_synergy_value, plan_reliability_score, team_archetype_bonus, team_style_scores
from quests_ai_tags import ADVENTURER_AI
from quests_ruleset_data import ADVENTURERS_BY_ID


RANDOM_BAND_BY_DIFFICULTY = {
    "easy": 6,
    "normal": 4,
    "hard": 3,
    "ranked": 3,
}

ENEMY_MODEL_KEEP = {
    "easy": 2,
    "normal": 3,
    "hard": 5,
    "ranked": 5,
}


@dataclass(frozen=True)
class QuestPartyChoice:
    offer_ids: tuple[str, ...]
    team_ids: tuple[str, ...]
    loadout: TeamLoadout
    package: QuestLoadoutPackage | None = None


@dataclass(frozen=True)
class _EnemyModel:
    team_ids: tuple[str, ...]
    profile: QuestTrioProfile
    weight: float


@dataclass(frozen=True)
class _TeamCandidate:
    team_ids: tuple[str, ...]
    profile: QuestTrioProfile
    score: float


def _unique_ids(ids: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen = set()
    ordered = []
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return tuple(ordered)


def _all_trios(ids: tuple[str, ...]) -> list[tuple[str, ...]]:
    if len(ids) < 3:
        return []
    return [tuple(trio) for trio in combinations(ids, 3)]


def _team_reliability_score(team_ids: tuple[str, ...]) -> float:
    return plan_reliability_score(team_ids)


def _team_ultimate_score(team_ids: tuple[str, ...]) -> float:
    styles = team_style_scores(team_ids)
    value = 0.0
    for adventurer_id in team_ids:
        roles = set(ADVENTURER_AI[adventurer_id].role_tags)
        if "tempo_engine" in roles:
            value += 4.0
        if "bonus_action_user" in roles:
            value += 2.5
        if "spell_loop" in roles or "magic_carry" in roles:
            value += 3.0
        if "primary_tank" in roles or "guard_support" in roles:
            value += 1.5
        if "burst_finisher" in roles:
            value += 2.5
    value += styles.get("ultimate", 0.0) * 0.35
    value += styles.get("tempo", 0.0) * 0.18
    return value


def _team_matchup_heuristic(attackers: tuple[str, ...], defenders: tuple[str, ...]) -> float:
    if not attackers or not defenders:
        return 0.0
    value = 0.0
    for attacker_id in attackers:
        attacker = ADVENTURER_AI[attacker_id]
        for defender_id in defenders:
            value += matchup_value(attacker, ADVENTURER_AI[defender_id])
    return value


def _team_internal_synergy_score(team_ids: tuple[str, ...]) -> float:
    value = 0.0
    pair_total = 0
    for left_id, right_id in combinations(team_ids, 2):
        pair_total += pair_synergy_value(left_id, right_id)
    archetype_bonus, _labels = team_archetype_bonus(team_ids)
    styles = team_style_scores(team_ids)
    value += pair_total * 0.35
    value += archetype_bonus * 0.70
    value += min(styles.get("burst", 0.0), styles.get("control", 0.0)) * 0.32
    value += min(styles.get("frontline", 0.0), styles.get("sustain", 0.0)) * 0.28
    value += styles.get("backline_pressure", 0.0) * 0.25
    value += styles.get("tempo", 0.0) * 0.15
    return value


def _loadout_warning_penalty(loadout: TeamLoadout) -> float:
    penalty = 0.0
    for warning in loadout.warnings:
        penalty += 4.5
        if "weak frontline" in warning.lower():
            penalty += 4.0
        if "limited backline" in warning.lower():
            penalty += 4.0
        if "fragile" in warning.lower():
            penalty += 3.0
    return penalty


def _style_map(profile: QuestTrioProfile) -> dict[str, float]:
    return dict(profile.styles)


def _tag_counter_delta(own_profile: QuestTrioProfile, enemy_profile: QuestTrioProfile) -> float:
    own_tags = set(own_profile.tag_set)
    enemy_styles = _style_map(enemy_profile)
    value = 0.0
    if enemy_styles.get("frontline", 0.0) + enemy_styles.get("sustain", 0.0) >= 24.0 and "anti_guard" in own_tags:
        value += 5.0
    if enemy_styles.get("burst", 0.0) >= 14.0 and {"anti_burst", "healer", "guard_support", "sustain", "cleanse"} & own_tags:
        value += 5.0
    if enemy_styles.get("backline_pressure", 0.0) >= 14.0 and {"reach", "backline_reach", "spotlight_enabler", "ranged_pressure", "magic_pressure"} & own_tags:
        value += 4.0
    if enemy_styles.get("control", 0.0) >= 14.0 and {"cleanse", "anti_status", "anti_caster"} & own_tags:
        value += 4.0
    if enemy_styles.get("tempo", 0.0) >= 14.0 and {"primary_tank", "frontline", "anti_burst"} & own_tags:
        value += 2.0
    return value


def _frontline_integrity_score(profile: QuestTrioProfile) -> float:
    front = next((member for member in profile.loadout.members if member.slot == SLOT_FRONT), None)
    back_left = next((member for member in profile.loadout.members if member.slot == SLOT_BACK_LEFT), None)
    back_right = next((member for member in profile.loadout.members if member.slot == SLOT_BACK_RIGHT), None)
    if front is None:
        return -22.0

    front_roles = set(ADVENTURER_AI[front.adventurer_id].role_tags)
    front_weapon_kind = next(
        weapon.kind
        for weapon in ADVENTURERS_BY_ID[front.adventurer_id].signature_weapons
        if weapon.id == front.primary_weapon_id
    )
    value = 0.0
    if {"primary_tank", "anti_burst", "frontline_ready", "stall_anchor", "bruiser"} & front_roles:
        value += 10.0
    if front.class_name == "Warden":
        value += 6.0
    if front.class_name == "Fighter":
        value += 3.5
    if front_weapon_kind == "melee":
        value += 4.0
    if front_weapon_kind == "ranged" and "frontline_pivot" not in front_roles and "primary_tank" not in front_roles:
        value -= 7.0
    if front_weapon_kind == "magic" and "primary_tank" not in front_roles and "frontline_ready" not in front_roles:
        value -= 4.0

    if back_left is not None:
        successor_roles = set(ADVENTURER_AI[back_left.adventurer_id].role_tags)
        value += 2.0
        if {"primary_tank", "anti_burst", "frontline_ready", "bruiser", "frontline_pivot"} & successor_roles:
            value += 6.0
        if back_left.class_name in {"Warden", "Fighter"}:
            value += 2.5
    else:
        value -= 5.0

    if back_right is not None:
        carry_roles = set(ADVENTURER_AI[back_right.adventurer_id].role_tags)
        if {"fragile", "tempo_engine", "magic_carry", "ranged_pressure", "backline_reach"} & carry_roles:
            value += 1.5
    return value


def _selection_profile_breakdown(profile: QuestTrioProfile) -> tuple[float, float]:
    styles = _style_map(profile)
    pressure = 0.0
    pressure += styles.get("burst", 0.0) * 0.22
    pressure += styles.get("backline_pressure", 0.0) * 0.25
    pressure += styles.get("control", 0.0) * 0.16
    pressure += styles.get("tempo", 0.0) * 0.10
    pressure += styles.get("sustain", 0.0) * 0.10
    pressure += styles.get("frontline", 0.0) * 0.12

    fragility = max(
        0.0,
        styles.get("fragility", 0.0)
        - styles.get("frontline", 0.0) * 0.70
        - styles.get("sustain", 0.0) * 0.55,
    )
    return pressure, fragility


def _enemy_model_score(
    profile: QuestTrioProfile,
    *,
    opposing_party_ids: tuple[str, ...],
) -> float:
    pressure, fragility = _selection_profile_breakdown(profile)
    score = profile.score * 0.48
    score += _team_internal_synergy_score(profile.team_ids)
    score += _team_reliability_score(profile.team_ids)
    score += _team_ultimate_score(profile.team_ids) * 0.80
    score += pressure
    score += _frontline_integrity_score(profile) * 0.95
    if opposing_party_ids:
        score += _team_matchup_heuristic(profile.team_ids, opposing_party_ids) * 0.18
        score += counterplay_score(profile.team_ids, opposing_party_ids) * 0.58
        score -= counter_fragility_penalty(profile.team_ids, opposing_party_ids)
    score -= _loadout_warning_penalty(profile.loadout)
    score -= fragility * 0.70
    return score


def _build_enemy_models(
    enemy_package: QuestLoadoutPackage,
    difficulty: str,
    *,
    opposing_party_ids: tuple[str, ...] = (),
) -> list[_EnemyModel]:
    trios = _all_trios(enemy_package.offer_ids)
    scored_profiles = [
        (summarize_trio_from_package(enemy_package, trio), 0.0)
        for trio in trios
    ]
    rescored: list[tuple[QuestTrioProfile, float]] = []
    for profile, _ in scored_profiles:
        rescored.append((profile, _enemy_model_score(profile, opposing_party_ids=opposing_party_ids)))
    rescored.sort(key=lambda item: item[1], reverse=True)
    keep = min(ENEMY_MODEL_KEEP.get(difficulty, 4), len(rescored))
    if keep <= 0:
        return []

    top_score = rescored[0][1]
    models: list[_EnemyModel] = []
    total_weight = 0.0
    for index, (profile, score) in enumerate(rescored[:keep]):
        gap = max(0.0, top_score - score)
        weight = 1.0 / (1.0 + index + gap * 0.08)
        models.append(_EnemyModel(team_ids=profile.team_ids, profile=profile, weight=weight))
        total_weight += weight
    if total_weight > 0:
        models = [
            _EnemyModel(team_ids=model.team_ids, profile=model.profile, weight=model.weight / total_weight)
            for model in models
        ]
    return models


def _expected_matchup_delta(profile: QuestTrioProfile, enemy_models: list[_EnemyModel], *, difficulty: str) -> float:
    if not enemy_models:
        return 0.0
    total = 0.0
    total_weight = 0.0
    worst_case = float("inf")
    own_styles = _style_map(profile)
    for model in enemy_models:
        enemy_styles = _style_map(model.profile)
        pressure_delta = (_team_matchup_heuristic(profile.team_ids, model.team_ids) - _team_matchup_heuristic(model.team_ids, profile.team_ids)) * 1.10
        counter_delta = counterplay_score(profile.team_ids, model.team_ids) - counterplay_score(model.team_ids, profile.team_ids)
        fragility_penalty = counter_fragility_penalty(profile.team_ids, model.team_ids)
        style_delta = (own_styles.get("backline_pressure", 0.0) - enemy_styles.get("backline_pressure", 0.0)) * 0.16
        style_delta += (own_styles.get("sustain", 0.0) - enemy_styles.get("sustain", 0.0)) * 0.12
        style_delta += (own_styles.get("control", 0.0) - enemy_styles.get("control", 0.0)) * 0.10
        delta = pressure_delta + counter_delta * 0.62 + style_delta + _tag_counter_delta(profile, model.profile) - fragility_penalty
        total += delta * model.weight
        total_weight += model.weight
        worst_case = min(worst_case, delta)
    average_case = total / total_weight if total_weight > 0 else 0.0
    if worst_case == float("inf"):
        worst_case = average_case
    if difficulty in {"hard", "ranked"}:
        return worst_case * 0.55 + average_case * 0.45
    if difficulty == "normal":
        return worst_case * 0.40 + average_case * 0.60
    return worst_case * 0.25 + average_case * 0.75


def _selection_pressure_score(profile: QuestTrioProfile) -> float:
    styles = _style_map(profile)
    value = styles.get("burst", 0.0) * 0.24
    value += styles.get("control", 0.0) * 0.18
    value += styles.get("backline_pressure", 0.0) * 0.24
    value += styles.get("tempo", 0.0) * 0.12
    value += styles.get("sustain", 0.0) * 0.10
    value += styles.get("frontline", 0.0) * 0.12
    value -= max(0.0, styles.get("fragility", 0.0) - (styles.get("frontline", 0.0) + styles.get("sustain", 0.0))) * 0.28
    return value


def _pick_from_top_band(candidates: list[_TeamCandidate], difficulty: str, rng: random.Random) -> _TeamCandidate:
    candidates.sort(key=lambda item: item.score, reverse=True)
    top_score = candidates[0].score
    band_size = RANDOM_BAND_BY_DIFFICULTY.get(difficulty, 3)
    threshold = 12.0 if difficulty in {"easy", "normal"} else 8.0
    band = [item for item in candidates if top_score - item.score <= threshold][:band_size]
    if len(band) <= 1:
        return band[0]
    top_pick_chance = 0.6 if difficulty == "easy" else 0.7 if difficulty == "normal" else 0.75
    if difficulty == "ranked":
        top_pick_chance = 0.8
    if rng.random() < top_pick_chance:
        return band[0]
    return rng.choice(band)


def choose_quest_party(
    offer_ids: list[str] | tuple[str, ...],
    *,
    enemy_party_ids: list[str] | tuple[str, ...] = (),
    difficulty: str = "hard",
    rng: random.Random | None = None,
) -> QuestPartyChoice:
    offered = _unique_ids(offer_ids)
    if len(offered) < 3:
        raise ValueError("Quest AI requires at least 3 unique adventurers in the offered party.")
    enemy_party = _unique_ids(enemy_party_ids)
    rng = rng or random.Random()

    package = assign_blind_quest_loadouts(offered)
    enemy_models: list[_EnemyModel] = []
    if len(enemy_party) >= 3:
        enemy_package = assign_blind_quest_loadouts(enemy_party)
        enemy_models = _build_enemy_models(
            enemy_package,
            difficulty,
            opposing_party_ids=offered,
        )

    candidates: list[_TeamCandidate] = []
    for team_ids in _all_trios(offered):
        profile = summarize_trio_from_package(package, team_ids)
        pressure_score, fragility = _selection_profile_breakdown(profile)
        score = profile.score * 0.48
        score += _team_internal_synergy_score(team_ids)
        score += _team_reliability_score(team_ids)
        score += _team_ultimate_score(team_ids) * 0.85
        score += pressure_score
        score += _frontline_integrity_score(profile)
        if enemy_models:
            score += _expected_matchup_delta(profile, enemy_models, difficulty=difficulty)
        if enemy_party:
            score += _team_matchup_heuristic(team_ids, enemy_party) * 0.18
            score += counterplay_score(team_ids, enemy_party) * 0.65
            score -= counter_fragility_penalty(team_ids, enemy_party)
        score -= _loadout_warning_penalty(profile.loadout)
        score -= fragility * 0.75
        candidates.append(_TeamCandidate(team_ids=team_ids, profile=profile, score=score))

    if not candidates:
        raise ValueError(f"Quest AI could not solve a legal lineup from offered party: {offered}.")

    chosen = _pick_from_top_band(candidates, difficulty, rng)
    return QuestPartyChoice(
        offer_ids=offered,
        team_ids=chosen.team_ids,
        loadout=chosen.profile.loadout,
        package=package,
    )


def choose_six_from_nine(
    offer_ids: list[str] | tuple[str, ...],
    *,
    locked_ids: list[str] | tuple[str, ...] = (),
) -> QuestLoadoutPackage:
    return choose_blind_quest_roster_from_offer(offer_ids, roster_size=6, locked_ids=locked_ids)


def choose_three_and_formation(
    party_ids: list[str] | tuple[str, ...],
    *,
    enemy_party_ids: list[str] | tuple[str, ...] = (),
    difficulty: str = "hard",
    rng: random.Random | None = None,
) -> QuestPartyChoice:
    return choose_quest_party(
        party_ids,
        enemy_party_ids=enemy_party_ids,
        difficulty=difficulty,
        rng=rng,
    )
