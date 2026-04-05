from __future__ import annotations

import argparse
import os
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_battle import queue_both_teams_for_phase, evaluate_battle_state
from quests_ai_quest import choose_quest_party
from quests_ai_quest_loadout import choose_blind_quest_roster_from_offer
from quests_ai_runtime import build_battle_from_loadouts
from quests_ruleset_data import ADVENTURERS
from quests_ruleset_logic import end_round, resolve_action_phase, resolve_bonus_phase, start_round


SLOT_SORT = {
    SLOT_FRONT: 0,
    SLOT_BACK_LEFT: 1,
    SLOT_BACK_RIGHT: 2,
}

SLOT_LABEL = {
    SLOT_FRONT: "Front",
    SLOT_BACK_LEFT: "Back Left",
    SLOT_BACK_RIGHT: "Back Right",
}


def _capture_new_logs(battle, start_index: int) -> tuple[list[str], int]:
    new_lines = battle.log[start_index:]
    return list(new_lines), len(battle.log)


def _format_offer(ids: list[str] | tuple[str, ...]) -> str:
    return ", ".join(ids)


def _member_loadout_line(member) -> str:
    artifact_name = member.artifact_id if member.artifact_id else "None"
    return (
        f"{SLOT_LABEL.get(member.slot, member.slot)}: {member.adventurer_id} | "
        f"Class={member.class_name} | Skill={member.class_skill_id} | "
        f"Primary={member.primary_weapon_id} | Artifact={artifact_name}"
    )


def _unit_state_line(unit) -> str:
    artifact_name = unit.artifact.name if unit.artifact is not None else "None"
    statuses = ", ".join(f"{status.kind}:{status.duration}" for status in unit.statuses) or "-"
    cooldowns = ", ".join(
        f"{effect_id}:{turns}" for effect_id, turns in sorted(unit.cooldowns.items()) if turns > 0
    ) or "-"
    ammo = ", ".join(
        f"{weapon_id}:{amount}" for weapon_id, amount in sorted(unit.ammo_remaining.items())
    ) or "-"
    buffs = ", ".join(f"{buff.stat}:{buff.amount}:{buff.duration}" for buff in unit.buffs) or "-"
    debuffs = ", ".join(f"{debuff.stat}:{debuff.amount}:{debuff.duration}" for debuff in unit.debuffs) or "-"
    return (
        f"{SLOT_LABEL.get(unit.slot, unit.slot)} | {unit.name} | HP {unit.hp}/{unit.max_hp} | "
        f"Class={unit.class_name} | Skill={unit.class_skill.name} | "
        f"Primary={unit.primary_weapon.name} | Secondary={unit.secondary_weapon.name} | "
        f"Artifact={artifact_name} | Status={statuses} | Buffs={buffs} | Debuffs={debuffs} | "
        f"Cooldowns={cooldowns} | Ammo={ammo}"
    )


def _team_state_lines(battle, team_num: int) -> list[str]:
    team = battle.team1 if team_num == 1 else battle.team2
    lines = [f"Team {team_num} ({team.player_name}) | Ultimate Meter {team.ultimate_meter}/7"]
    members = sorted(team.members, key=lambda member: SLOT_SORT.get(member.slot, 99))
    for member in members:
        lines.append(f"  {_unit_state_line(member)}")
    return lines


def _find_unit(battle, ref: tuple[int, str] | None):
    if ref is None:
        return None
    team = battle.team1 if ref[0] == 1 else battle.team2
    return next((member for member in team.members if member.defn.id == ref[1]), None)


def _effect_name(actor, spec) -> str:
    if spec.kind == "strike":
        return f"Strike ({actor.primary_weapon.name})"
    if spec.kind == "switch":
        return "Switch Weapons"
    if spec.kind == "swap":
        return "Swap Positions"
    if spec.kind == "skip":
        return "Skip"
    if spec.kind == "ultimate":
        return f"Ultimate ({actor.defn.ultimate.name})"
    if spec.kind == "spell":
        for effect in actor.active_spells():
            if effect.id == spec.effect_id:
                return f"Spell ({effect.name})"
        bonus_effect = actor.markers.get("artifact_bonus_spell_effect")
        if bonus_effect is not None and getattr(bonus_effect, "id", None) == spec.effect_id:
            return f"Spell ({bonus_effect.name})"
        if actor.defn.ultimate.id == spec.effect_id:
            return f"Ultimate ({actor.defn.ultimate.name})"
        return f"Spell ({spec.effect_id})"
    return spec.kind.title()


def _plan_lines(battle, team_num: int, plan: dict, *, bonus: bool) -> list[str]:
    team = battle.team1 if team_num == 1 else battle.team2
    phase_label = "Bonus" if bonus else "Action"
    lines = [f"{phase_label} Plan - Team {team_num} ({team.player_name})"]
    members = sorted(team.alive(), key=lambda member: SLOT_SORT.get(member.slot, 99))
    for member in members:
        spec = plan.get((team_num, member.defn.id))
        if spec is None:
            lines.append(f"  {member.name}: Skip")
            continue
        target = _find_unit(battle, spec.target_ref)
        target_text = f" -> {target.name}" if target is not None else ""
        lines.append(f"  {member.name}: {_effect_name(member, spec)}{target_text}")
    return lines


def _initiative_line(battle) -> str:
    parts = []
    for unit in battle.initiative_order:
        parts.append(f"{unit.name} ({SLOT_LABEL.get(unit.slot, unit.slot)})")
    return " > ".join(parts) if parts else "(no living units)"


def _tiebreak_winner(battle) -> tuple[int, str]:
    score = evaluate_battle_state(battle, 1)
    if abs(score) > 0.01:
        return (1 if score > 0 else 2), f"board evaluation {score:.2f}"
    team1_alive = len(battle.team1.alive())
    team2_alive = len(battle.team2.alive())
    if team1_alive != team2_alive:
        winner = 1 if team1_alive > team2_alive else 2
        return winner, f"alive count {team1_alive}-{team2_alive}"
    team1_hp = sum(unit.hp for unit in battle.team1.alive())
    team2_hp = sum(unit.hp for unit in battle.team2.alive())
    winner = 1 if team1_hp >= team2_hp else 2
    return winner, f"remaining HP {team1_hp}-{team2_hp}"


def _simulate_single_encounter(encounter_number: int, rng: random.Random, *, difficulty1: str, difficulty2: str, max_rounds: int) -> str:
    offer9_team1 = [adventurer.id for adventurer in rng.sample(ADVENTURERS, 9)]
    offer9_team2 = [adventurer.id for adventurer in rng.sample(ADVENTURERS, 9)]

    package1 = choose_blind_quest_roster_from_offer(offer9_team1, roster_size=6)
    package2 = choose_blind_quest_roster_from_offer(offer9_team2, roster_size=6)

    offer6_team1 = list(package1.offer_ids)
    offer6_team2 = list(package2.offer_ids)

    choice1 = choose_quest_party(offer6_team1, enemy_party_ids=offer6_team2, difficulty=difficulty1, rng=rng)
    choice2 = choose_quest_party(offer6_team2, enemy_party_ids=offer6_team1, difficulty=difficulty2, rng=rng)

    battle = build_battle_from_loadouts(
        choice1.loadout,
        choice2.loadout,
        player_name_1=f"Encounter {encounter_number:03d} Alpha",
        player_name_2=f"Encounter {encounter_number:03d} Beta",
    )

    lines: list[str] = []
    lines.append(f"========== ENCOUNTER {encounter_number:03d} ==========")
    lines.append(f"Difficulty: Team1={difficulty1} | Team2={difficulty2}")
    lines.append("Team 1 Offer 9:")
    lines.append(f"  {_format_offer(offer9_team1)}")
    lines.append("Team 1 Chosen 6:")
    lines.append(f"  {_format_offer(offer6_team1)}")
    lines.append("Team 1 Final 3:")
    for member in choice1.loadout.members:
        lines.append(f"  {_member_loadout_line(member)}")
    if choice1.loadout.warnings:
        lines.append(f"  Warnings: {', '.join(choice1.loadout.warnings)}")

    lines.append("Team 2 Offer 9:")
    lines.append(f"  {_format_offer(offer9_team2)}")
    lines.append("Team 2 Chosen 6:")
    lines.append(f"  {_format_offer(offer6_team2)}")
    lines.append("Team 2 Final 3:")
    for member in choice2.loadout.members:
        lines.append(f"  {_member_loadout_line(member)}")
    if choice2.loadout.warnings:
        lines.append(f"  Warnings: {', '.join(choice2.loadout.warnings)}")

    lines.append("")
    lines.append("Opening State")
    lines.extend(_team_state_lines(battle, 1))
    lines.extend(_team_state_lines(battle, 2))
    lines.append("")

    rounds_played = 0
    log_index = 0

    while battle.winner is None and rounds_played < max_rounds:
        current_round = battle.round_num
        lines.append(f"--- ROUND {current_round} ---")

        start_round(battle)
        lines.append(f"Initiative: {_initiative_line(battle)}")
        new_logs, log_index = _capture_new_logs(battle, log_index)
        if new_logs:
            lines.append("Start Of Round")
            for line in new_logs:
                lines.append(f"  {line}")

        plan1, plan2 = queue_both_teams_for_phase(
            battle,
            bonus=False,
            difficulty1=difficulty1,
            difficulty2=difficulty2,
            rng=rng,
        )
        lines.extend(_plan_lines(battle, 1, plan1, bonus=False))
        lines.extend(_plan_lines(battle, 2, plan2, bonus=False))

        resolve_action_phase(battle)
        new_logs, log_index = _capture_new_logs(battle, log_index)
        lines.append("Action Resolution")
        if new_logs:
            for line in new_logs:
                lines.append(f"  {line}")
        else:
            lines.append("  (no action log entries)")

        if battle.winner is None:
            bonus1, bonus2 = queue_both_teams_for_phase(
                battle,
                bonus=True,
                difficulty1=difficulty1,
                difficulty2=difficulty2,
                rng=rng,
            )
            lines.extend(_plan_lines(battle, 1, bonus1, bonus=True))
            lines.extend(_plan_lines(battle, 2, bonus2, bonus=True))

            resolve_bonus_phase(battle)
            new_logs, log_index = _capture_new_logs(battle, log_index)
            lines.append("Bonus Resolution")
            if new_logs:
                for line in new_logs:
                    lines.append(f"  {line}")
            else:
                lines.append("  (no bonus log entries)")

        if battle.winner is None:
            end_round(battle)
            new_logs, log_index = _capture_new_logs(battle, log_index)
            lines.append("End Of Round")
            if new_logs:
                for line in new_logs:
                    lines.append(f"  {line}")
            else:
                lines.append("  (no end-of-round log entries)")
            lines.append("Round-End State")
            lines.extend(_team_state_lines(battle, 1))
            lines.extend(_team_state_lines(battle, 2))

        lines.append("")
        rounds_played += 1

    timeout_note = ""
    if battle.winner is None:
        winner, reason = _tiebreak_winner(battle)
        battle.winner = winner
        timeout_note = f"Timed out after {max_rounds} rounds; tiebreak winner by {reason}."

    result_label = "Team 1 Win" if battle.winner == 1 else "Team 2 Win"
    lines.append(f"FINAL RESULT: {result_label}")
    lines.append(f"Rounds Played: {rounds_played}")
    if timeout_note:
        lines.append(timeout_note)
    lines.append("Final State")
    lines.extend(_team_state_lines(battle, 1))
    lines.extend(_team_state_lines(battle, 2))
    lines.append("")
    lines.append("")
    return "\n".join(lines)


def _build_file_text(
    *,
    file_index: int,
    total_files: int,
    encounters_per_file: int,
    base_encounter_number: int,
    seed: int,
    difficulty1: str,
    difficulty2: str,
    max_rounds: int,
) -> tuple[int, str]:
    rng = random.Random(seed)
    file_lines = [
        "Fabled Full Encounter Transcript Batch",
        f"Seed: {seed}",
        f"File {file_index}/{total_files}",
        f"Encounters In File: {encounters_per_file}",
        f"Difficulties: Team1={difficulty1}, Team2={difficulty2}",
        f"Max Rounds: {max_rounds}",
        "",
    ]
    for offset in range(encounters_per_file):
        encounter_number = base_encounter_number + offset
        file_lines.append(
            _simulate_single_encounter(
                encounter_number,
                rng,
                difficulty1=difficulty1,
                difficulty2=difficulty2,
                max_rounds=max_rounds,
            )
        )
    return file_index, "\n".join(file_lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate full encounter transcript batches.")
    parser.add_argument("--encounters", type=int, default=100)
    parser.add_argument("--files", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260404)
    parser.add_argument("--difficulty-team1", default="ranked", choices=("easy", "normal", "hard", "ranked"))
    parser.add_argument("--difficulty-team2", default="ranked", choices=("easy", "normal", "hard", "ranked"))
    parser.add_argument("--max-rounds", type=int, default=40)
    parser.add_argument("--workers", type=int, default=max(1, min(6, (os.cpu_count() or 4) - 1 if (os.cpu_count() or 4) > 1 else 1)))
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    if args.encounters <= 0 or args.files <= 0:
        raise ValueError("encounters and files must both be positive.")
    if args.encounters % args.files != 0:
        raise ValueError("encounters must divide evenly across files.")

    encounters_per_file = args.encounters // args.files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir) if args.output_dir else Path(f"encounter_log_batches_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    master_rng = random.Random(args.seed)
    file_jobs = []
    for file_index in range(1, args.files + 1):
        file_seed = master_rng.randint(0, 10**9)
        base_encounter_number = (file_index - 1) * encounters_per_file + 1
        file_jobs.append(
            {
                "file_index": file_index,
                "total_files": args.files,
                "encounters_per_file": encounters_per_file,
                "base_encounter_number": base_encounter_number,
                "seed": file_seed,
                "difficulty1": args.difficulty_team1,
                "difficulty2": args.difficulty_team2,
                "max_rounds": args.max_rounds,
            }
        )

    max_workers = max(1, min(args.files, args.workers))
    results: dict[int, str] = {}
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_build_file_text, **job): job["file_index"] for job in file_jobs}
        for future in as_completed(future_map):
            file_index, text = future.result()
            results[file_index] = text

    for file_index in range(1, args.files + 1):
        out_path = output_dir / f"encounters_{file_index:02d}.txt"
        out_path.write_text(results[file_index], encoding="utf-8")
        print(f"Wrote {out_path}")

    print(f"Created {args.files} files in {output_dir}")


if __name__ == "__main__":
    main()
