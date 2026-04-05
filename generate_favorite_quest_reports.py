from __future__ import annotations

from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import argparse
import copy
import math
import os
import random
import statistics
import traceback

from quests_ai_battle import evaluate_battle_state, queue_both_teams_for_phase
from quests_ai_quest import choose_quest_party
from quests_ai_quest_loadout import choose_blind_quest_roster_from_offer
from quests_ai_runtime import build_battle_from_loadouts
from quests_ruleset_data import ADVENTURERS, ADVENTURERS_BY_ID
import quests_ruleset_logic as qrl
from storybook_ranked import (
    STARTING_GLORY,
    find_ai_match_profile,
    get_encounter_gold,
    rank_name,
    rank_floor_for_glory,
    update_glory_after_match,
)
from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT


RUNS_PER_FAVORITE = 5
MAX_QUEST_LOSSES = 3
MAX_BATTLE_ROUNDS = 40
PLAYER_DIFFICULTY = "ranked"
MAX_WORKERS = max(1, min(8, (os.cpu_count() or 4) - 1 if (os.cpu_count() or 4) > 1 else 1))
PARTY_CHOICE_RETRIES = 4
FULL_BATTLE_LOGS = False


NO_ARTIFACT_LABEL = "No Artifact"
NO_CLASS_LABEL = "No Class"
NO_SKILL_LABEL = "No Skill"


HOOKS_INSTALLED = False
CURRENT_TELEMETRY = None
CURRENT_BATTLE_OBJECT = None
ORIGINALS: dict[str, object] = {}


@dataclass
class EncounterTelemetry:
    action_counts: Counter = field(default_factory=Counter)
    damage_dealt: Counter = field(default_factory=Counter)
    damage_taken: Counter = field(default_factory=Counter)
    ultimate_casts: list[tuple[int, str]] = field(default_factory=list)
    death_order: list[str] = field(default_factory=list)
    seen_ko_refs: set[tuple[int, str]] = field(default_factory=set)

    def record_new_kos(self, battle) -> None:
        for team_num, team in ((1, battle.team1), (2, battle.team2)):
            for unit in team.members:
                ref = (team_num, unit.defn.id)
                if unit.ko and ref not in self.seen_ko_refs:
                    self.seen_ko_refs.add(ref)
                    self.death_order.append(unit.defn.id)


def _safe_id(name: str) -> str:
    cleaned = []
    for char in name.lower():
        if char.isalnum():
            cleaned.append(char)
        else:
            cleaned.append("_")
    value = "".join(cleaned)
    while "__" in value:
        value = value.replace("__", "_")
    return value.strip("_")


def _adventurer_name(adventurer_id: str) -> str:
    return ADVENTURERS_BY_ID[adventurer_id].name


def _artifact_label(artifact_id: str | None) -> str:
    return NO_ARTIFACT_LABEL if not artifact_id else artifact_id


def _class_label(class_name: str | None) -> str:
    return NO_CLASS_LABEL if not class_name else class_name


def _skill_label(skill_id: str | None) -> str:
    return NO_SKILL_LABEL if not skill_id else skill_id


def _loadout_signature(member) -> str:
    return " | ".join(
        [
            _adventurer_name(member.adventurer_id),
            f"Weapon={member.primary_weapon_id}",
            f"Class={_class_label(member.class_name)}",
            f"Skill={_skill_label(member.class_skill_id)}",
            f"Artifact={_artifact_label(member.artifact_id)}",
        ]
    )


def _format_member(member) -> str:
    slot_label = {
        SLOT_FRONT: "Front",
        SLOT_BACK_LEFT: "Back Left",
        SLOT_BACK_RIGHT: "Back Right",
    }.get(member.slot, member.slot)
    return (
        f"{slot_label}: {_adventurer_name(member.adventurer_id)} | "
        f"Weapon {member.primary_weapon_id} | "
        f"Class {_class_label(member.class_name)} | "
        f"Skill {_skill_label(member.class_skill_id)} | "
        f"Artifact {_artifact_label(member.artifact_id)}"
    )


def _empty_partial() -> dict:
    return {
        "encounters": 0,
        "quest_runs": 0,
        "quest_encounters_total": 0,
        "rounds_total": 0,
        "tiebreak_encounters": 0,
        "action_counts": Counter(),
        "adventurer_appear": Counter(),
        "adventurer_wins": Counter(),
        "class_appear": Counter(),
        "class_wins": Counter(),
        "skill_appear": Counter(),
        "skill_wins": Counter(),
        "artifact_appear": Counter(),
        "artifact_wins": Counter(),
        "loadout_appear": Counter(),
        "loadout_wins": Counter(),
        "ultimate_casts": Counter(),
        "ultimate_wins": Counter(),
        "damage_dealt": Counter(),
        "damage_taken": Counter(),
        "battle_appearances": Counter(),
        "first_death": Counter(),
        "last_death": Counter(),
        "offered": Counter(),
        "left_behind": Counter(),
    }


def _merge_partial(total: dict, part: dict) -> None:
    for key in ("encounters", "quest_runs", "quest_encounters_total", "rounds_total", "tiebreak_encounters"):
        total[key] += part[key]
    for key in (
        "action_counts",
        "adventurer_appear",
        "adventurer_wins",
        "class_appear",
        "class_wins",
        "skill_appear",
        "skill_wins",
        "artifact_appear",
        "artifact_wins",
        "loadout_appear",
        "loadout_wins",
        "ultimate_casts",
        "ultimate_wins",
        "damage_dealt",
        "damage_taken",
        "battle_appearances",
        "first_death",
        "last_death",
        "offered",
        "left_behind",
    ):
        total[key].update(part[key])


def _winrate_lines(title: str, appear: Counter, wins: Counter) -> list[str]:
    lines = [title]
    ranked = sorted(
        appear.items(),
        key=lambda item: (
            -(wins[item[0]] / item[1] if item[1] else 0.0),
            -item[1],
            str(item[0]),
        ),
    )
    for key, count in ranked:
        win_rate = (wins[key] / count) * 100 if count else 0.0
        lines.append(f"- {key}: {wins[key]}/{count} ({win_rate:.2f}%)")
    return lines


def _average_lines(title: str, totals: Counter, appearances: Counter) -> list[str]:
    lines = [title]
    ranked = sorted(
        appearances.items(),
        key=lambda item: (-(totals[item[0]] / item[1] if item[1] else 0.0), -item[1], str(item[0])),
    )
    for key, count in ranked:
        average = totals[key] / count if count else 0.0
        lines.append(f"- {key}: {average:.2f} across {count} appearances")
    return lines


def _left_behind_lines(offered: Counter, left_behind: Counter) -> list[str]:
    lines = ["Left Behind Rate Per Adventurer"]
    ranked = sorted(
        offered.items(),
        key=lambda item: (-(left_behind[item[0]] / item[1] if item[1] else 0.0), -item[1], item[0]),
    )
    for adventurer_id, count in ranked:
        rate = (left_behind[adventurer_id] / count) * 100 if count else 0.0
        lines.append(f"- {_adventurer_name(adventurer_id)}: {left_behind[adventurer_id]}/{count} ({rate:.2f}%)")
    return lines


def _death_rate_lines(title: str, deaths: Counter, appearances: Counter) -> list[str]:
    lines = [title]
    ranked = sorted(
        appearances.items(),
        key=lambda item: (-(deaths[item[0]] / item[1] if item[1] else 0.0), -item[1], item[0]),
    )
    for label, count in ranked:
        rate = (deaths[label] / count) * 100 if count else 0.0
        lines.append(f"- {label}: {deaths[label]}/{count} ({rate:.2f}%)")
    return lines


def _tiebreak_winner(battle) -> int:
    score = evaluate_battle_state(battle, 1)
    if abs(score) > 0.01:
        return 1 if score > 0 else 2
    team1_alive = len(battle.team1.alive())
    team2_alive = len(battle.team2.alive())
    if team1_alive != team2_alive:
        return 1 if team1_alive > team2_alive else 2
    team1_hp = sum(unit.hp for unit in battle.team1.alive())
    team2_hp = sum(unit.hp for unit in battle.team2.alive())
    return 1 if team1_hp >= team2_hp else 2


def _all_units(battle):
    return battle.team1.members + battle.team2.members


def _ensure_hooks_installed() -> None:
    global HOOKS_INSTALLED
    if HOOKS_INSTALLED:
        return

    ORIGINALS["resolve_action"] = qrl.resolve_action
    ORIGINALS["_resolve_effect"] = qrl._resolve_effect
    ORIGINALS["_handle_post_damage_reactions"] = qrl._handle_post_damage_reactions
    ORIGINALS["end_round"] = qrl.end_round

    def hooked_resolve_action(actor, action, battle, *, is_bonus: bool = False):
        telemetry = CURRENT_TELEMETRY
        if telemetry is None or battle is not CURRENT_BATTLE_OBJECT:
            return ORIGINALS["resolve_action"](actor, action, battle, is_bonus=is_bonus)
        blocked = actor.markers.get("cant_act_rounds", 0) > 0 or qrl._fated_duel_blocks(actor, battle)
        action_type = action.get("type")
        if not blocked and action_type in {"strike", "spell", "switch", "swap", "skip", "ultimate"}:
            telemetry.action_counts[action_type] += 1
            if action_type == "ultimate":
                team_num = qrl.player_num_for_actor(battle, actor)
                telemetry.ultimate_casts.append((team_num, actor.defn.ultimate.name))
        result = ORIGINALS["resolve_action"](actor, action, battle, is_bonus=is_bonus)
        telemetry.record_new_kos(battle)
        return result

    def hooked_resolve_effect(actor, effect, target, battle, *, source_kind: str, weapon=None):
        telemetry = CURRENT_TELEMETRY
        if telemetry is None or battle is not CURRENT_BATTLE_OBJECT:
            return ORIGINALS["_resolve_effect"](actor, effect, target, battle, source_kind=source_kind, weapon=weapon)
        before_hp = {(id(unit)): unit.hp for unit in _all_units(battle)}
        result = ORIGINALS["_resolve_effect"](actor, effect, target, battle, source_kind=source_kind, weapon=weapon)
        actor_team = qrl.team_for_actor(battle, actor)
        for unit in _all_units(battle):
            diff = before_hp[id(unit)] - unit.hp
            if diff <= 0:
                continue
            telemetry.damage_taken[unit.defn.id] += diff
            if unit is not actor and qrl.team_for_actor(battle, unit) is not actor_team:
                telemetry.damage_dealt[actor.defn.id] += diff
        return result

    def hooked_post_damage(source, target, damage, battle, *, source_kind: str, weapon):
        telemetry = CURRENT_TELEMETRY
        if telemetry is None or battle is not CURRENT_BATTLE_OBJECT:
            return ORIGINALS["_handle_post_damage_reactions"](source, target, damage, battle, source_kind=source_kind, weapon=weapon)
        before_source_hp = source.hp
        result = ORIGINALS["_handle_post_damage_reactions"](source, target, damage, battle, source_kind=source_kind, weapon=weapon)
        source_loss = before_source_hp - source.hp
        if source_loss > 0:
            dealer = target
            if target.hp <= 0:
                target_team = qrl.team_for_actor(battle, target)
                lady = next(
                    (
                        ally
                        for ally in target_team.members
                        if not ally.ko
                        and ally is not target
                        and ally.defn.id == "lady_of_reflections"
                        and ally.primary_weapon.id == "lantern_of_avalon"
                    ),
                    None,
                )
                if lady is not None:
                    dealer = lady
            telemetry.damage_dealt[dealer.defn.id] += source_loss
        return result

    def hooked_end_round(battle):
        telemetry = CURRENT_TELEMETRY
        if telemetry is None or battle is not CURRENT_BATTLE_OBJECT:
            return ORIGINALS["end_round"](battle)
        before_hp = {(id(unit)): unit.hp for unit in _all_units(battle)}
        result = ORIGINALS["end_round"](battle)
        for unit in _all_units(battle):
            diff = before_hp[id(unit)] - unit.hp
            if diff > 0:
                telemetry.damage_taken[unit.defn.id] += diff
        telemetry.record_new_kos(battle)
        return result

    qrl.resolve_action = hooked_resolve_action
    qrl._resolve_effect = hooked_resolve_effect
    qrl._handle_post_damage_reactions = hooked_post_damage
    qrl.end_round = hooked_end_round
    HOOKS_INSTALLED = True


def _play_instrumented_battle(battle, *, difficulty1: str, difficulty2: str, rng: random.Random):
    global CURRENT_BATTLE_OBJECT, CURRENT_TELEMETRY
    telemetry = EncounterTelemetry()
    CURRENT_TELEMETRY = telemetry
    CURRENT_BATTLE_OBJECT = battle
    rounds = 0
    winner = None
    tiebreak = False
    try:
        while battle.winner is None and rounds < MAX_BATTLE_ROUNDS:
            qrl.start_round(battle)
            queue_both_teams_for_phase(battle, bonus=False, difficulty1=difficulty1, difficulty2=difficulty2, rng=rng)
            qrl.resolve_action_phase(battle)
            if battle.winner is None:
                queue_both_teams_for_phase(battle, bonus=True, difficulty1=difficulty1, difficulty2=difficulty2, rng=rng)
                qrl.resolve_bonus_phase(battle)
            if battle.winner is None:
                qrl.end_round(battle)
            rounds += 1
        winner = battle.winner
        if winner is None:
            winner = _tiebreak_winner(battle)
            battle.winner = winner
            tiebreak = True
        telemetry.record_new_kos(battle)
        return winner, rounds, telemetry, tiebreak
    finally:
        CURRENT_BATTLE_OBJECT = None
        CURRENT_TELEMETRY = None


def _record_offer_stats(partial: dict, offer_ids: list[str], chosen_ids: tuple[str, ...]) -> None:
    chosen = set(chosen_ids)
    for adventurer_id in offer_ids:
        partial["offered"][adventurer_id] += 1
        if adventurer_id not in chosen:
            partial["left_behind"][adventurer_id] += 1


def _record_selected_build_stats(partial: dict, loadout, did_win: bool) -> None:
    for member in loadout.members:
        adventurer_id = member.adventurer_id
        class_name = _class_label(member.class_name)
        skill_id = _skill_label(member.class_skill_id)
        artifact_label = _artifact_label(member.artifact_id)
        loadout_key = _loadout_signature(member)

        partial["adventurer_appear"][adventurer_id] += 1
        partial["class_appear"][class_name] += 1
        partial["skill_appear"][skill_id] += 1
        partial["artifact_appear"][artifact_label] += 1
        partial["loadout_appear"][loadout_key] += 1
        partial["battle_appearances"][adventurer_id] += 1

        if did_win:
            partial["adventurer_wins"][adventurer_id] += 1
            partial["class_wins"][class_name] += 1
            partial["skill_wins"][skill_id] += 1
            partial["artifact_wins"][artifact_label] += 1
            partial["loadout_wins"][loadout_key] += 1


def _enemy_average_glory(opponent_glories: list[int]) -> int:
    if not opponent_glories:
        return 0
    return int(round(sum(opponent_glories) / len(opponent_glories)))


def _choose_party_with_retries(
    offer_ids: list[str] | tuple[str, ...],
    *,
    enemy_party_ids: list[str] | tuple[str, ...],
    difficulty: str,
    rng: random.Random,
):
    attempt_plan = (
        (difficulty, tuple(enemy_party_ids)),
        ("hard", tuple(enemy_party_ids)),
        (difficulty, ()),
        ("normal", ()),
    )
    last_error: Exception | None = None
    for chosen_difficulty, chosen_enemy_ids in attempt_plan[:PARTY_CHOICE_RETRIES]:
        try:
            return choose_quest_party(
                offer_ids,
                enemy_party_ids=chosen_enemy_ids,
                difficulty=chosen_difficulty,
                rng=rng,
            )
        except ValueError as exc:
            last_error = exc
    raise ValueError(
        f"Could not build a quest party after {min(PARTY_CHOICE_RETRIES, len(attempt_plan))} attempts for offer {tuple(offer_ids)}."
    ) from last_error


def _simulate_favorite_run(task: tuple[str, int, int, bool]) -> dict:
    favorite_id, favorite_index, run_index, full_battle_logs = task
    _ensure_hooks_installed()

    seed = 100_000 + favorite_index * 1_000 + run_index
    rng = random.Random(seed)
    all_ids = [adventurer.id for adventurer in ADVENTURERS]
    party_pool = [adventurer_id for adventurer_id in all_ids if adventurer_id != favorite_id]
    offered_ids = [favorite_id] + rng.sample(party_pool, 8)
    party_package = choose_blind_quest_roster_from_offer(offered_ids, roster_size=6, locked_ids=(favorite_id,))
    party_ids = list(party_package.offer_ids)

    current_glory = STARTING_GLORY
    floor_glory = 1
    wins = 0
    losses = 0
    current_win_streak = 0
    current_loss_streak = 0
    total_gold = 0
    encounter_index = 0
    opponent_glories: list[int] = []
    partial = _empty_partial()
    encounter_lines: list[str] = []
    tiebreak_count = 0

    while losses < MAX_QUEST_LOSSES:
        encounter_index += 1
        match_profile = find_ai_match_profile(
            current_glory,
            wins,
            losses,
            avg_opponent_glory=_enemy_average_glory(opponent_glories),
            rng=rng,
        )
        enemy_glory = match_profile.glory
        enemy_offer = rng.sample(all_ids, 9)
        enemy_package = choose_blind_quest_roster_from_offer(enemy_offer, roster_size=6)
        enemy_party_ids = list(enemy_package.offer_ids)
        enemy_difficulty = "ranked"

        player_choice = _choose_party_with_retries(
            party_ids,
            enemy_party_ids=enemy_party_ids,
            difficulty=PLAYER_DIFFICULTY,
            rng=rng,
        )
        enemy_choice = _choose_party_with_retries(
            enemy_party_ids,
            enemy_party_ids=party_ids,
            difficulty=enemy_difficulty,
            rng=rng,
        )

        _record_offer_stats(partial, party_ids, player_choice.team_ids)
        _record_offer_stats(partial, enemy_party_ids, enemy_choice.team_ids)

        battle = build_battle_from_loadouts(
            player_choice.loadout,
            enemy_choice.loadout,
            player_name_1="Player Quest AI",
            player_name_2="Quest Rival AI",
        )
        winner, rounds, telemetry, used_tiebreak = _play_instrumented_battle(
            battle,
            difficulty1=PLAYER_DIFFICULTY,
            difficulty2=enemy_difficulty,
            rng=rng,
        )
        did_win = winner == 1
        if used_tiebreak:
            tiebreak_count += 1
            partial["tiebreak_encounters"] += 1

        partial["encounters"] += 1
        partial["rounds_total"] += rounds
        partial["action_counts"].update(telemetry.action_counts)
        partial["damage_dealt"].update(telemetry.damage_dealt)
        partial["damage_taken"].update(telemetry.damage_taken)

        for team_num, ultimate_name in telemetry.ultimate_casts:
            partial["ultimate_casts"][ultimate_name] += 1
            if winner == team_num:
                partial["ultimate_wins"][ultimate_name] += 1

        if telemetry.death_order:
            partial["first_death"][telemetry.death_order[0]] += 1
            partial["last_death"][telemetry.death_order[-1]] += 1

        _record_selected_build_stats(partial, player_choice.loadout, did_win)
        _record_selected_build_stats(partial, enemy_choice.loadout, not did_win)

        glory_before = current_glory
        opponent_glories.append(enemy_glory)
        if len(opponent_glories) > 20:
            opponent_glories = opponent_glories[-20:]
        new_glory, glory_delta = update_glory_after_match(
            current_glory,
            enemy_glory,
            did_win=did_win,
            current_win_streak_before_match=current_win_streak,
            current_loss_streak_before_match=current_loss_streak,
            floor_glory=floor_glory,
        )
        current_glory = new_glory

        encounter_gold = 0
        if did_win:
            encounter_gold = get_encounter_gold(current_win_streak)
            wins += 1
            current_win_streak += 1
            current_loss_streak = 0
            total_gold += encounter_gold
        else:
            losses += 1
            current_loss_streak += 1
            current_win_streak = 0

        encounter_lines.extend(
            [
                f"Encounter {encounter_index}: {'WIN' if did_win else 'LOSS'} in {rounds} rounds vs {rank_name(enemy_glory)} Rival ({enemy_glory} Glory)"
                + (" [tiebreak]" if used_tiebreak else ""),
                f"  Player party: {', '.join(_adventurer_name(adventurer_id) for adventurer_id in party_ids)}",
                f"  Enemy party: {', '.join(_adventurer_name(adventurer_id) for adventurer_id in enemy_offer)}",
                f"  Player chosen 3: {', '.join(_adventurer_name(adventurer_id) for adventurer_id in player_choice.team_ids)}",
                f"  Enemy chosen 3: {', '.join(_adventurer_name(adventurer_id) for adventurer_id in enemy_choice.team_ids)}",
                "  Player loadout:",
                *[f"    - {_format_member(member)}" for member in player_choice.loadout.members],
                "  Enemy loadout:",
                *[f"    - {_format_member(member)}" for member in enemy_choice.loadout.members],
                f"  Left behind: {', '.join(_adventurer_name(adventurer_id) for adventurer_id in party_ids if adventurer_id not in player_choice.team_ids)}",
                (
                    "  Actions: "
                    f"strikes={telemetry.action_counts['strike']}, "
                    f"spells={telemetry.action_counts['spell']}, "
                    f"switches={telemetry.action_counts['switch']}, "
                    f"swaps={telemetry.action_counts['swap']}, "
                    f"skips={telemetry.action_counts['skip']}, "
                    f"ultimates={telemetry.action_counts['ultimate']}"
                ),
                (
                    "  Deaths: "
                    + (" -> ".join(_adventurer_name(adventurer_id) for adventurer_id in telemetry.death_order) if telemetry.death_order else "none")
                ),
                f"  Glory: {glory_before} -> {current_glory} ({glory_delta:+d}) | Gold gained: {encounter_gold}",
            ]
        )
        if full_battle_logs:
            encounter_lines.append("  Full Battle Log:")
            if battle.log:
                encounter_lines.extend(f"    {line}" for line in battle.log)
            else:
                encounter_lines.append("    (no battle log lines recorded)")
        encounter_lines.append("")

    completion_bonus = 300 if wins >= 10 else 150 if wins >= 5 else 0
    total_gold += completion_bonus

    partial["quest_runs"] += 1
    partial["quest_encounters_total"] += encounter_index

    summary = {
        "favorite_id": favorite_id,
        "run_index": run_index,
        "seed": seed,
        "party_ids": tuple(party_ids),
        "wins": wins,
        "losses": losses,
        "encounters": encounter_index,
        "final_glory": current_glory,
        "total_gold": total_gold,
        "completion_bonus": completion_bonus,
        "tiebreak_count": tiebreak_count,
    }

    run_lines = [
        f"Run {run_index + 1}",
        f"Seed: {seed}",
        f"Favorite: {_adventurer_name(favorite_id)}",
        f"Starting party: {', '.join(_adventurer_name(adventurer_id) for adventurer_id in party_ids)}",
        f"Final record: {wins}W-{losses}L across {encounter_index} encounters",
        f"Final Glory: {current_glory}",
        f"Total Gold earned: {total_gold} (completion bonus {completion_bonus})",
        f"Tiebreaked encounters: {tiebreak_count}",
        "",
        *encounter_lines,
        "-" * 88,
        "",
    ]

    return {
        "favorite_id": favorite_id,
        "run_index": run_index,
        "summary": summary,
        "text": "\n".join(run_lines),
        "partial": partial,
    }


def _write_favorite_file(report_dir: Path, favorite_id: str, run_results: list[dict]) -> None:
    favorite_name = _adventurer_name(favorite_id)
    wins = [item["summary"]["wins"] for item in run_results]
    encounters = [item["summary"]["encounters"] for item in run_results]
    gold = [item["summary"]["total_gold"] for item in run_results]
    glory = [item["summary"]["final_glory"] for item in run_results]
    best_run = max(run_results, key=lambda item: (item["summary"]["wins"], -item["summary"]["losses"], item["summary"]["final_glory"]))

    lines = [
        f"Favorite Quest Simulation Report",
        f"Favorite: {favorite_name}",
        f"Runs simulated: {len(run_results)}",
        f"Average wins: {statistics.mean(wins):.2f}",
        f"Average encounters per run: {statistics.mean(encounters):.2f}",
        f"Average total gold per run: {statistics.mean(gold):.2f}",
        f"Average final Glory: {statistics.mean(glory):.2f}",
        f"Best run: {best_run['summary']['wins']}W-{best_run['summary']['losses']}L | Final Glory {best_run['summary']['final_glory']} | Party {', '.join(_adventurer_name(adventurer_id) for adventurer_id in best_run['summary']['party_ids'])}",
        "",
        "=" * 88,
        "",
    ]
    for item in sorted(run_results, key=lambda result: result["run_index"]):
        lines.append(item["text"])

    path = report_dir / f"{_safe_id(favorite_name)}.txt"
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_global_statistics(report_dir: Path, total: dict, best_party: dict) -> None:
    encounters = total["encounters"]
    action_counts = total["action_counts"]
    lines = [
        "Global Favorite Quest Simulation Statistics",
        f"Quest runs simulated: {total['quest_runs']}",
        f"Encounters simulated: {encounters}",
        f"Tiebreaked encounters: {total['tiebreak_encounters']}",
        f"Average encounter length: {(total['rounds_total'] / encounters):.2f} rounds" if encounters else "Average encounter length: n/a",
        f"Average strikes per encounter: {(action_counts['strike'] / encounters):.2f}" if encounters else "Average strikes per encounter: n/a",
        f"Average spells cast per encounter: {(action_counts['spell'] / encounters):.2f}" if encounters else "Average spells cast per encounter: n/a",
        f"Average weapon switches per encounter: {(action_counts['switch'] / encounters):.2f}" if encounters else "Average weapon switches per encounter: n/a",
        f"Average position swaps per encounter: {(action_counts['swap'] / encounters):.2f}" if encounters else "Average position swaps per encounter: n/a",
        f"Average skips per encounter: {(action_counts['skip'] / encounters):.2f}" if encounters else "Average skips per encounter: n/a",
        f"Average ultimate spells cast per encounter: {(action_counts['ultimate'] / encounters):.2f}" if encounters else "Average ultimate spells cast per encounter: n/a",
        f"Average quest run length: {(total['quest_encounters_total'] / total['quest_runs']):.2f} encounters" if total["quest_runs"] else "Average quest run length: n/a",
        "",
        f"Best performing party observed: {', '.join(_adventurer_name(adventurer_id) for adventurer_id in best_party['party_ids'])}",
        f"  Favorite: {_adventurer_name(best_party['favorite_id'])}",
        f"  Record: {best_party['wins']}W-{best_party['losses']}L",
        f"  Encounters: {best_party['encounters']}",
        f"  Final Glory: {best_party['final_glory']}",
        f"  Total Gold: {best_party['total_gold']}",
        "",
    ]

    lines.extend(_winrate_lines("Adventurer Winrate", Counter({_adventurer_name(k): v for k, v in total["adventurer_appear"].items()}), Counter({_adventurer_name(k): v for k, v in total["adventurer_wins"].items()})))
    lines.append("")
    lines.extend(_winrate_lines("Class Winrate", total["class_appear"], total["class_wins"]))
    lines.append("")
    lines.extend(_winrate_lines("Class Skill Winrate", total["skill_appear"], total["skill_wins"]))
    lines.append("")
    lines.extend(_winrate_lines("Artifact Winrate", total["artifact_appear"], total["artifact_wins"]))
    lines.append("")
    lines.extend(_winrate_lines("Loadout Winrate", total["loadout_appear"], total["loadout_wins"]))
    lines.append("")
    lines.extend(_winrate_lines("Ultimate Spell Winrate", total["ultimate_casts"], total["ultimate_wins"]))
    lines.append("")
    lines.extend(_average_lines("Average Damage Per Battle By Adventurer", Counter({_adventurer_name(k): v for k, v in total["damage_dealt"].items()}), Counter({_adventurer_name(k): v for k, v in total["battle_appearances"].items()})))
    lines.append("")
    lines.extend(_average_lines("Average Damage Taken Per Battle By Adventurer", Counter({_adventurer_name(k): v for k, v in total["damage_taken"].items()}), Counter({_adventurer_name(k): v for k, v in total["battle_appearances"].items()})))
    lines.append("")
    lines.extend(_death_rate_lines("First Death Rate Per Adventurer", Counter({_adventurer_name(k): v for k, v in total["first_death"].items()}), Counter({_adventurer_name(k): v for k, v in total["battle_appearances"].items()})))
    lines.append("")
    lines.extend(_death_rate_lines("Last Death Rate Per Adventurer", Counter({_adventurer_name(k): v for k, v in total["last_death"].items()}), Counter({_adventurer_name(k): v for k, v in total["battle_appearances"].items()})))
    lines.append("")
    lines.extend(_left_behind_lines(total["offered"], total["left_behind"]))

    path = report_dir / "global_statistics.txt"
    path.write_text("\n".join(lines), encoding="utf-8")


def _progress_line(summary: dict) -> str:
    party_names = ", ".join(_adventurer_name(adventurer_id) for adventurer_id in summary["party_ids"])
    return (
        "QUEST_DONE"
        f" | favorite={_adventurer_name(summary['favorite_id'])}"
        f" | run={summary['run_index'] + 1}"
        f" | record={summary['wins']}W-{summary['losses']}L"
        f" | encounters={summary['encounters']}"
        f" | final_glory={summary['final_glory']}"
        f" | gold={summary['total_gold']}"
        f" | tiebreaks={summary['tiebreak_count']}"
        f" | party={party_names}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate favorite quest simulation reports.")
    parser.add_argument("--runs-per-favorite", type=int, default=RUNS_PER_FAVORITE)
    parser.add_argument("--max-workers", type=int, default=MAX_WORKERS)
    parser.add_argument("--favorite", action="append", dest="favorites", default=[])
    parser.add_argument("--report-dir", type=str, default="")
    parser.add_argument("--full-battle-logs", action="store_true")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path(args.report_dir) if args.report_dir else (Path.cwd() / f"favorite_quest_reports_{timestamp}")
    report_dir.mkdir(parents=True, exist_ok=False)

    tasks: list[tuple[str, int, int]] = []
    if args.favorites:
        favorite_ids = [favorite_id for favorite_id in args.favorites if favorite_id in ADVENTURERS_BY_ID]
    else:
        favorite_ids = [adventurer.id for adventurer in ADVENTURERS]
    for favorite_index, favorite_id in enumerate(favorite_ids):
        for run_index in range(args.runs_per_favorite):
            tasks.append((favorite_id, favorite_index, run_index, bool(args.full_battle_logs)))

    favorite_runs: dict[str, list[dict]] = defaultdict(list)
    total = _empty_partial()
    best_party_summary = None

    completed = 0
    if args.max_workers <= 1:
        results_iter = map(_simulate_favorite_run, tasks)
        for result in results_iter:
            favorite_id = result["favorite_id"]
            favorite_runs[favorite_id].append(result)
            _merge_partial(total, result["partial"])
            summary = result["summary"]
            if best_party_summary is None or (
                summary["wins"],
                -summary["losses"],
                summary["final_glory"],
                summary["total_gold"],
            ) > (
                best_party_summary["wins"],
                -best_party_summary["losses"],
                best_party_summary["final_glory"],
                    best_party_summary["total_gold"],
                ):
                best_party_summary = copy.deepcopy(summary)
            completed += 1
            print(_progress_line(summary), flush=True)
            print(f"Completed {completed}/{len(tasks)} quest runs...", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            future_map = {executor.submit(_simulate_favorite_run, task): task for task in tasks}
            for future in as_completed(future_map):
                favorite_id, _favorite_index, _run_index = future_map[future]
                try:
                    result = future.result()
                except Exception:
                    error_path = report_dir / "simulation_error.txt"
                    error_path.write_text(traceback.format_exc(), encoding="utf-8")
                    raise
                favorite_runs[favorite_id].append(result)
                _merge_partial(total, result["partial"])
                summary = result["summary"]
                if best_party_summary is None or (
                    summary["wins"],
                    -summary["losses"],
                    summary["final_glory"],
                    summary["total_gold"],
                ) > (
                    best_party_summary["wins"],
                    -best_party_summary["losses"],
                    best_party_summary["final_glory"],
                    best_party_summary["total_gold"],
                ):
                    best_party_summary = copy.deepcopy(summary)
                completed += 1
                print(_progress_line(summary), flush=True)
                if completed % 10 == 0 or completed == len(tasks):
                    print(f"Completed {completed}/{len(tasks)} quest runs...", flush=True)

    for favorite_id in favorite_ids:
        _write_favorite_file(report_dir, favorite_id, favorite_runs[favorite_id])

    _write_global_statistics(report_dir, total, best_party_summary)
    print(f"Reports written to: {report_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
