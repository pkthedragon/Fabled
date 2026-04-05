from __future__ import annotations

import random

from quests_ai_battle import queue_both_teams_for_phase
from quests_ai_bout import BoutDraftResult, draft_bout_teams
from quests_ai_quest import QuestPartyChoice, choose_quest_party
from quests_ai_quest_loadout import choose_blind_quest_roster_from_offer
from quests_ruleset_data import ADVENTURERS
from quests_ruleset_logic import create_battle, create_team, determine_initiative_order, end_round, make_pick, start_round


def _team_from_loadout(player_name: str, loadout):
    picks = []
    for member in loadout.members:
        picks.append(
            make_pick(
                member.adventurer_id,
                slot=member.slot,
                class_name=member.class_name,
                class_skill_id=member.class_skill_id,
                primary_weapon_id=member.primary_weapon_id,
                artifact_id=member.artifact_id,
            )
        )
    return create_team(player_name, picks)


def build_battle_from_loadouts(loadout1, loadout2, *, player_name_1: str = "AI One", player_name_2: str = "AI Two", second_picker: int = 0):
    team1 = _team_from_loadout(player_name_1, loadout1)
    team2 = _team_from_loadout(player_name_2, loadout2)
    battle = create_battle(team1, team2)
    if second_picker == 1:
        battle.team1.markers["bonus_swap_rounds"] = 1
        battle.team1.markers["bonus_swap_used"] = 0
    elif second_picker == 2:
        battle.team2.markers["bonus_swap_rounds"] = 1
        battle.team2.markers["bonus_swap_used"] = 0
    determine_initiative_order(battle)
    return battle


def play_ai_round(battle, *, difficulty1: str = "hard", difficulty2: str = "hard", rng: random.Random | None = None):
    rng = rng or random.Random()
    start_round(battle)
    queue_both_teams_for_phase(battle, bonus=False, difficulty1=difficulty1, difficulty2=difficulty2, rng=rng)
    from quests_ruleset_logic import resolve_action_phase, resolve_bonus_phase

    resolve_action_phase(battle)
    if battle.winner is None:
        queue_both_teams_for_phase(battle, bonus=True, difficulty1=difficulty1, difficulty2=difficulty2, rng=rng)
        resolve_bonus_phase(battle)
    if battle.winner is None:
        end_round(battle)
    return battle.winner


def play_ai_battle(battle, *, difficulty1: str = "hard", difficulty2: str = "hard", max_rounds: int = 16, rng: random.Random | None = None):
    rng = rng or random.Random()
    rounds = 0
    while battle.winner is None and rounds < max_rounds:
        play_ai_round(battle, difficulty1=difficulty1, difficulty2=difficulty2, rng=rng)
        rounds += 1
    return battle.winner, rounds


def run_ai_quest_battle(*, seed: int | None = None, difficulty1: str = "hard", difficulty2: str = "hard"):
    rng = random.Random(seed)
    nine_offer1 = [adventurer.id for adventurer in rng.sample(ADVENTURERS, 9)]
    nine_offer2 = [adventurer.id for adventurer in rng.sample(ADVENTURERS, 9)]
    party1 = choose_blind_quest_roster_from_offer(nine_offer1, roster_size=6)
    party2 = choose_blind_quest_roster_from_offer(nine_offer2, roster_size=6)
    offer1 = list(party1.offer_ids)
    offer2 = list(party2.offer_ids)
    choice1: QuestPartyChoice = choose_quest_party(offer1, enemy_party_ids=offer2, difficulty=difficulty1, rng=rng)
    choice2: QuestPartyChoice = choose_quest_party(offer2, enemy_party_ids=offer1, difficulty=difficulty2, rng=rng)
    battle = build_battle_from_loadouts(choice1.loadout, choice2.loadout, player_name_1="Quest AI A", player_name_2="Quest AI B")
    winner, rounds = play_ai_battle(battle, difficulty1=difficulty1, difficulty2=difficulty2, max_rounds=16, rng=rng)
    return {
        "winner": winner,
        "rounds": rounds,
        "offer1": tuple(nine_offer1),
        "offer2": tuple(nine_offer2),
        "party1": tuple(offer1),
        "party2": tuple(offer2),
        "team1_ids": choice1.team_ids,
        "team2_ids": choice2.team_ids,
        "battle": battle,
    }


def run_ai_bout_battle(*, seed: int | None = None, difficulty1: str = "hard", difficulty2: str = "hard"):
    rng = random.Random(seed)
    pool_ids = [adventurer.id for adventurer in rng.sample(ADVENTURERS, 9)]
    draft: BoutDraftResult = draft_bout_teams(pool_ids, difficulty1=difficulty1, difficulty2=difficulty2, rng=rng)
    battle = build_battle_from_loadouts(
        draft.team1_loadout,
        draft.team2_loadout,
        player_name_1="Bout AI A",
        player_name_2="Bout AI B",
        second_picker=draft.second_picker,
    )
    winner, rounds = play_ai_battle(battle, difficulty1=difficulty1, difficulty2=difficulty2, max_rounds=16, rng=rng)
    return {
        "winner": winner,
        "rounds": rounds,
        "pool_ids": tuple(pool_ids),
        "team1_ids": draft.team1_ids,
        "team2_ids": draft.team2_ids,
        "battle": battle,
    }
