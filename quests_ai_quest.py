from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations

from quests_ai_loadout import TeamLoadout, solve_team_loadout


RANDOM_BAND_BY_DIFFICULTY = {
    "easy": 5,
    "normal": 3,
    "hard": 2,
    "ranked": 2,
}


@dataclass(frozen=True)
class QuestPartyChoice:
    offer_ids: tuple[str, ...]
    team_ids: tuple[str, ...]
    loadout: TeamLoadout


def _pick_from_top_band(loadouts: list[tuple[tuple[str, ...], TeamLoadout]], difficulty: str, rng: random.Random) -> tuple[tuple[str, ...], TeamLoadout]:
    loadouts.sort(key=lambda item: item[1].score, reverse=True)
    top_score = loadouts[0][1].score
    band_size = RANDOM_BAND_BY_DIFFICULTY.get(difficulty, 2)
    threshold = 10.0 if difficulty in {"easy", "normal"} else 6.0
    band = [item for item in loadouts if top_score - item[1].score <= threshold][:band_size]
    if difficulty == "ranked" and len(band) > 1 and rng.random() < 0.85:
        return band[0]
    return rng.choice(band)


def choose_quest_party(offer_ids: list[str] | tuple[str, ...], *, difficulty: str = "hard", rng: random.Random | None = None) -> QuestPartyChoice:
    if len(set(offer_ids)) != 6:
        raise ValueError("Quest AI expects exactly 6 unique offered adventurers.")
    rng = rng or random.Random()
    candidates: list[tuple[tuple[str, ...], TeamLoadout]] = []
    for team_ids in combinations(offer_ids, 3):
        loadout = solve_team_loadout(team_ids, mode="quest", seat=1)
        candidates.append((tuple(team_ids), loadout))
    chosen_ids, loadout = _pick_from_top_band(candidates, difficulty, rng)
    return QuestPartyChoice(offer_ids=tuple(offer_ids), team_ids=chosen_ids, loadout=loadout)
