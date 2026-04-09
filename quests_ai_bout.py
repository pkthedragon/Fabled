from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations

from quests_ai_loadout import TeamLoadout, solve_team_loadout
from quests_ai_tables import matchup_value, pair_synergy_value
from quests_ai_tags import ADVENTURER_AI


@dataclass(frozen=True)
class BoutDraftResult:
    pool_ids: tuple[str, ...]
    team1_ids: tuple[str, ...]
    team2_ids: tuple[str, ...]
    team1_loadout: TeamLoadout
    team2_loadout: TeamLoadout
    second_picker: int


def _top_pick_count(difficulty: str) -> int:
    return {
        "easy": 5,
        "normal": 3,
        "hard": 2,
        "ranked": 2,
    }.get(difficulty, 2)


def _best_encounter_team_score(roster_ids: tuple[str, ...], enemy_ids: tuple[str, ...], *, seat: int) -> float:
    if len(roster_ids) < 3:
        return 0.0
    best = float("-inf")
    for trio_ids in combinations(roster_ids, 3):
        try:
            score = solve_team_loadout(trio_ids, enemy_ids=enemy_ids, mode="bout", seat=seat).score
        except ValueError:
            continue
        best = max(best, score)
    return best if best != float("-inf") else 0.0


def _team_ceiling_score(
    current_ids: tuple[str, ...],
    available_ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
    *,
    seat: int,
    target_size: int,
) -> float:
    if target_size > 3:
        trio_needed = max(0, 3 - len(current_ids))
        if trio_needed <= 0:
            return _best_encounter_team_score(current_ids, enemy_ids, seat=seat)
        best = float("-inf")
        for extra_ids in combinations(available_ids, trio_needed):
            trial_ids = tuple(sorted(current_ids + tuple(extra_ids)))
            best = max(best, _best_encounter_team_score(trial_ids, enemy_ids, seat=seat))
        return best if best != float("-inf") else 0.0

    needed = target_size - len(current_ids)
    if needed <= 0:
        return _best_encounter_team_score(current_ids, enemy_ids, seat=seat)
    best = float("-inf")
    for extra_ids in combinations(available_ids, needed):
        trial_ids = tuple(sorted(current_ids + tuple(extra_ids)))
        best = max(best, _best_encounter_team_score(trial_ids, enemy_ids, seat=seat))
    return best if best != float("-inf") else 0.0


def _denial_value(candidate_id: str, enemy_ids: tuple[str, ...]) -> float:
    if not enemy_ids:
        return 0.0
    candidate_profile = ADVENTURER_AI[candidate_id]
    value = 0.0
    for enemy_id in enemy_ids:
        value += max(0, pair_synergy_value(candidate_id, enemy_id)) * 0.7
        enemy_profile = ADVENTURER_AI[enemy_id]
        value += matchup_value(candidate_profile, enemy_profile) * 0.25
    return value


def _seat_adjustment(candidate_id: str, seat: int) -> float:
    if seat != 2:
        return 0.0
    profile = ADVENTURER_AI[candidate_id]
    tags = set(profile.role_tags)
    bonus = 0.0
    if {"swap_engine", "frontline_pivot", "backline_reach"} & tags:
        bonus += 6.0
    if "tempo_engine" in tags or "burst_finisher" in tags:
        bonus += 3.0
    return bonus


def _pick_score(
    candidate_id: str,
    own_ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
    available_ids: tuple[str, ...],
    *,
    seat: int,
    target_size: int,
) -> float:
    profile = ADVENTURER_AI[candidate_id]
    score = float(profile.base_power)
    score += profile.reliability * 0.15
    score -= max(0.0, profile.complexity - 70) * 0.05
    for ally_id in own_ids:
        score += pair_synergy_value(candidate_id, ally_id)
    for enemy_id in enemy_ids:
        score += matchup_value(profile, ADVENTURER_AI[enemy_id]) * 0.35
    score += _denial_value(candidate_id, enemy_ids)
    score += _seat_adjustment(candidate_id, seat)
    if target_size > 3:
        role_tags = set(profile.role_tags)
        if len(own_ids) < 2 and {"primary_tank", "frontline_ready", "anti_burst", "bruiser"} & role_tags:
            score += 6.0
        if len(own_ids) < 3 and {"backline_reach", "ranged_pressure", "magic_carry", "healer"} & role_tags:
            score += 4.0
        return score
    future_pool = tuple(item for item in available_ids if item != candidate_id)
    future_score = _team_ceiling_score(
        tuple(sorted(own_ids + (candidate_id,))),
        future_pool,
        enemy_ids,
        seat=seat,
        target_size=target_size,
    )
    score += future_score * 0.12
    return score


def _choose_pick(
    available_ids: tuple[str, ...],
    own_ids: tuple[str, ...],
    enemy_ids: tuple[str, ...],
    *,
    seat: int,
    difficulty: str,
    target_size: int,
    rng: random.Random,
) -> str:
    scored = [
        (
            candidate_id,
            _pick_score(
                candidate_id,
                own_ids,
                enemy_ids,
                available_ids,
                seat=seat,
                target_size=target_size,
            ),
        )
        for candidate_id in available_ids
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    top_score = scored[0][1]
    band_limit = _top_pick_count(difficulty)
    threshold = 10.0 if difficulty in {"easy", "normal"} else 6.0
    band = [item for item in scored if top_score - item[1] <= threshold][:band_limit]
    if difficulty == "ranked" and len(band) > 1 and rng.random() < 0.8:
        return band[0][0]
    return rng.choice(band)[0]


def choose_bout_pick(
    available_ids: list[str] | tuple[str, ...],
    own_ids: list[str] | tuple[str, ...],
    enemy_ids: list[str] | tuple[str, ...],
    *,
    seat: int,
    difficulty: str = "hard",
    target_size: int = 3,
    rng: random.Random | None = None,
) -> str:
    rng = rng or random.Random()
    return _choose_pick(
        tuple(available_ids),
        tuple(sorted(own_ids)),
        tuple(sorted(enemy_ids)),
        seat=seat,
        difficulty=difficulty,
        target_size=target_size,
        rng=rng,
    )


def draft_bout_teams(
    pool_ids: list[str] | tuple[str, ...],
    *,
    difficulty1: str = "hard",
    difficulty2: str = "hard",
    rng: random.Random | None = None,
) -> BoutDraftResult:
    if len(set(pool_ids)) != 9:
        raise ValueError("Bout drafting expects exactly 9 unique shared adventurers.")
    rng = rng or random.Random()
    available_ids = tuple(pool_ids)
    team1_ids: tuple[str, ...] = ()
    team2_ids: tuple[str, ...] = ()
    turn_order = (1, 2, 1, 2, 1, 2)
    for picker in turn_order:
        if picker == 1:
            choice = _choose_pick(available_ids, team1_ids, team2_ids, seat=1, difficulty=difficulty1, rng=rng)
            team1_ids = tuple(sorted(team1_ids + (choice,)))
        else:
            choice = _choose_pick(available_ids, team2_ids, team1_ids, seat=2, difficulty=difficulty2, rng=rng)
            team2_ids = tuple(sorted(team2_ids + (choice,)))
        available_ids = tuple(item for item in available_ids if item != choice)
    team1_loadout = solve_team_loadout(team1_ids, enemy_ids=team2_ids, mode="bout", seat=1)
    team2_loadout = solve_team_loadout(team2_ids, enemy_ids=team1_ids, mode="bout", seat=2)
    return BoutDraftResult(
        pool_ids=tuple(pool_ids),
        team1_ids=team1_ids,
        team2_ids=team2_ids,
        team1_loadout=team1_loadout,
        team2_loadout=team2_loadout,
        second_picker=2,
    )
