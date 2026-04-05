from __future__ import annotations

import argparse
import random
from collections import defaultdict
from dataclasses import dataclass

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_battle import available_action_specs, queue_both_teams_for_phase
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
    SLOT_BACK_LEFT: "Back-L",
    SLOT_BACK_RIGHT: "Back-R",
}


@dataclass
class BattleMetrics:
    winner: int | None
    rounds: int
    swaps: int
    switches: int
    ultimates: int
    ultimate_events: list[tuple[int, str]]
    action_opportunities: dict[str, int]
    action_uses: dict[str, int]
    bonus_opportunities: dict[str, int]
    bonus_uses: dict[str, int]
    ultimate_ready_opportunities: int
    ultimate_ready_uses: int
    urgent_switch_opportunities: int
    urgent_switch_uses: int


def _record_rate(tracker: dict[str, list[int]], key: str, did_win: bool):
    row = tracker.setdefault(key, [0, 0])
    row[0] += 1
    if did_win:
        row[1] += 1


def _count_plan_actions(plan: dict, team_num: int, fallback_ultimate_id_by_ref: dict[tuple[int, str], str]):
    swaps = 0
    switches = 0
    ultimates = 0
    ultimate_events: list[tuple[int, str]] = []
    for actor_ref, spec in plan.items():
        if spec.kind == "swap":
            swaps += 1
        elif spec.kind == "switch":
            switches += 1
        elif spec.kind == "ultimate":
            ultimates += 1
            ultimate_id = spec.effect_id or fallback_ultimate_id_by_ref.get(actor_ref, "unknown_ultimate")
            ultimate_events.append((team_num, ultimate_id))
    return swaps, switches, ultimates, ultimate_events


def _simulate_battle(
    battle,
    *,
    difficulty1: str,
    difficulty2: str,
    max_rounds: int,
    rng: random.Random,
) -> BattleMetrics:
    rounds = 0
    swaps = 0
    switches = 0
    ultimates = 0
    ultimate_events: list[tuple[int, str]] = []
    action_opportunities: dict[str, int] = defaultdict(int)
    action_uses: dict[str, int] = defaultdict(int)
    bonus_opportunities: dict[str, int] = defaultdict(int)
    bonus_uses: dict[str, int] = defaultdict(int)
    ultimate_ready_opportunities = 0
    ultimate_ready_uses = 0
    urgent_switch_opportunities = 0
    urgent_switch_uses = 0

    while battle.winner is None and rounds < max_rounds:
        start_round(battle)

        ultimate_id_by_ref: dict[tuple[int, str], str] = {}
        urgent_switch_refs: set[tuple[int, str]] = set()
        for team_num, team in ((1, battle.team1), (2, battle.team2)):
            for member in team.alive():
                actor_ref = (team_num, member.defn.id)
                ultimate_id_by_ref[actor_ref] = member.defn.ultimate.id
                specs = available_action_specs(battle, member, bonus=False)
                kinds = {spec.kind for spec in specs}
                for kind in kinds:
                    action_opportunities[kind] += 1
                if "ultimate" in kinds:
                    ultimate_ready_opportunities += 1
                if "switch" in kinds:
                    primary = member.primary_weapon
                    stalled = member.cooldowns.get(primary.strike.id, 0) > 0 or (
                        primary.ammo > 0 and member.ammo_remaining.get(primary.id, primary.ammo) <= 0
                    )
                    if stalled:
                        urgent_switch_opportunities += 1
                        urgent_switch_refs.add(actor_ref)

        plan1, plan2 = queue_both_teams_for_phase(
            battle,
            bonus=False,
            difficulty1=difficulty1,
            difficulty2=difficulty2,
            rng=rng,
        )
        s, sw, u, events = _count_plan_actions(plan1, 1, ultimate_id_by_ref)
        swaps += s
        switches += sw
        ultimates += u
        ultimate_events.extend(events)
        s, sw, u, events = _count_plan_actions(plan2, 2, ultimate_id_by_ref)
        swaps += s
        switches += sw
        ultimates += u
        ultimate_events.extend(events)
        for actor_ref, spec in plan1.items():
            action_uses[spec.kind] += 1
            if spec.kind == "ultimate":
                ultimate_ready_uses += 1
            if spec.kind == "switch" and actor_ref in urgent_switch_refs:
                urgent_switch_uses += 1
        for actor_ref, spec in plan2.items():
            action_uses[spec.kind] += 1
            if spec.kind == "ultimate":
                ultimate_ready_uses += 1
            if spec.kind == "switch" and actor_ref in urgent_switch_refs:
                urgent_switch_uses += 1

        resolve_action_phase(battle)
        if battle.winner is None:
            for team in (battle.team1, battle.team2):
                for member in team.alive():
                    specs = available_action_specs(battle, member, bonus=True)
                    kinds = {spec.kind for spec in specs}
                    for kind in kinds:
                        bonus_opportunities[kind] += 1
            plan1, plan2 = queue_both_teams_for_phase(
                battle,
                bonus=True,
                difficulty1=difficulty1,
                difficulty2=difficulty2,
                rng=rng,
            )
            s, sw, u, events = _count_plan_actions(plan1, 1, ultimate_id_by_ref)
            swaps += s
            switches += sw
            ultimates += u
            ultimate_events.extend(events)
            s, sw, u, events = _count_plan_actions(plan2, 2, ultimate_id_by_ref)
            swaps += s
            switches += sw
            ultimates += u
            ultimate_events.extend(events)
            for _, spec in plan1.items():
                bonus_uses[spec.kind] += 1
            for _, spec in plan2.items():
                bonus_uses[spec.kind] += 1

            resolve_bonus_phase(battle)

        if battle.winner is None:
            end_round(battle)

        rounds += 1

    return BattleMetrics(
        winner=battle.winner,
        rounds=rounds,
        swaps=swaps,
        switches=switches,
        ultimates=ultimates,
        ultimate_events=ultimate_events,
        action_opportunities=dict(action_opportunities),
        action_uses=dict(action_uses),
        bonus_opportunities=dict(bonus_opportunities),
        bonus_uses=dict(bonus_uses),
        ultimate_ready_opportunities=ultimate_ready_opportunities,
        ultimate_ready_uses=ultimate_ready_uses,
        urgent_switch_opportunities=urgent_switch_opportunities,
        urgent_switch_uses=urgent_switch_uses,
    )


def _team_compact_line(battle, team_num: int) -> str:
    team = battle.team1 if team_num == 1 else battle.team2
    members = sorted(team.members, key=lambda member: SLOT_SORT.get(member.slot, 99))
    parts = []
    for member in members:
        artifact_name = member.artifact.name if member.artifact is not None else "None"
        parts.append(
            f"{SLOT_LABEL.get(member.slot, member.slot)}: {member.name} | "
            f"Class={member.class_name} | Skill={member.class_skill.name} | "
            f"Weapon={member.primary_weapon.name} | Artifact={artifact_name}"
        )
    return " || ".join(parts)


def _format_rate_section(title: str, tracker: dict[str, list[int]]) -> list[str]:
    lines = [title]
    if not tracker:
        lines.append("  (no data)")
        return lines
    rows = []
    for key, (appearances, wins) in tracker.items():
        pct = (wins / appearances * 100.0) if appearances > 0 else 0.0
        rows.append((pct, appearances, wins, key))
    rows.sort(key=lambda row: (-row[0], -row[1], row[3]))
    for pct, appearances, wins, key in rows:
        lines.append(f"  {key}: {wins}/{appearances} ({pct:.2f}%)")
    return lines


def run_simulation(
    *,
    target_battles: int,
    seed: int,
    difficulty_player: str,
    difficulty_enemy: str,
    max_rounds: int,
):
    rng = random.Random(seed)
    adventurer_pool = list(ADVENTURERS)
    ultimate_name_by_id = {adventurer.ultimate.id: adventurer.ultimate.name for adventurer in ADVENTURERS}

    adventurer_rates: dict[str, list[int]] = {}
    class_rates: dict[str, list[int]] = {}
    class_skill_rates: dict[str, list[int]] = {}
    artifact_rates: dict[str, list[int]] = {}
    primary_weapon_rates: dict[str, list[int]] = {}
    ultimate_spell_rates: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    action_phase_opportunities: dict[str, int] = defaultdict(int)
    action_phase_uses: dict[str, int] = defaultdict(int)
    bonus_phase_opportunities: dict[str, int] = defaultdict(int)
    bonus_phase_uses: dict[str, int] = defaultdict(int)

    run_lengths: list[int] = []
    battle_lengths: list[int] = []
    swaps_per_battle: list[int] = []
    switches_per_battle: list[int] = []
    ultimates_per_battle: list[int] = []
    ultimate_ready_opportunities = 0
    ultimate_ready_uses = 0
    urgent_switch_opportunities = 0
    urgent_switch_uses = 0

    battle_log_lines: list[str] = []

    total_battles = 0
    run_index = 0

    while total_battles < target_battles:
        run_index += 1
        player_offer9 = [adventurer.id for adventurer in rng.sample(adventurer_pool, 9)]
        player_offer = list(choose_blind_quest_roster_from_offer(player_offer9, roster_size=6).offer_ids)
        player_choice = choose_quest_party(player_offer, difficulty=difficulty_player, rng=rng)

        run_battles = 0
        run_wins = 0
        run_losses = 0

        battle_log_lines.append(
            f"=== QUEST RUN {run_index} START | Player Party: {', '.join(player_choice.team_ids)} ==="
        )

        while run_losses < 3:
            opponent_offer9 = [adventurer.id for adventurer in rng.sample(adventurer_pool, 9)]
            opponent_offer = list(choose_blind_quest_roster_from_offer(opponent_offer9, roster_size=6).offer_ids)
            opponent_choice = choose_quest_party(opponent_offer, enemy_party_ids=player_offer, difficulty=difficulty_enemy, rng=rng)

            battle = build_battle_from_loadouts(
                player_choice.loadout,
                opponent_choice.loadout,
                player_name_1=f"Run {run_index} Player",
                player_name_2=f"Run {run_index} Opponent",
                second_picker=0,
            )

            metrics = _simulate_battle(
                battle,
                difficulty1=difficulty_player,
                difficulty2=difficulty_enemy,
                max_rounds=max_rounds,
                rng=rng,
            )

            run_battles += 1
            total_battles += 1
            battle_lengths.append(metrics.rounds)
            swaps_per_battle.append(metrics.swaps)
            switches_per_battle.append(metrics.switches)
            ultimates_per_battle.append(metrics.ultimates)

            if metrics.winner == 1:
                run_wins += 1
            else:
                run_losses += 1

            battle_label = "Draw/Timeout"
            if metrics.winner == 1:
                battle_label = "Player Win"
            elif metrics.winner == 2:
                battle_label = "Opponent Win"

            battle_log_lines.append(
                f"Battle {total_battles:04d} | Run {run_index} Battle {run_battles} | "
                f"Result={battle_label} | Rounds={metrics.rounds} | "
                f"Swaps={metrics.swaps} | Switches={metrics.switches} | Ultimates={metrics.ultimates} | "
                f"RunLosses={run_losses}/3"
            )
            battle_log_lines.append(f"  Team 1: {_team_compact_line(battle, 1)}")
            battle_log_lines.append(f"  Team 2: {_team_compact_line(battle, 2)}")

            for team_num, team in ((1, battle.team1), (2, battle.team2)):
                did_win = metrics.winner == team_num
                for member in team.members:
                    _record_rate(adventurer_rates, member.name, did_win)
                    _record_rate(class_rates, member.class_name, did_win)
                    _record_rate(class_skill_rates, member.class_skill.name, did_win)
                    _record_rate(primary_weapon_rates, member.primary_weapon.name, did_win)
                    artifact_name = member.artifact.name if member.artifact is not None else "None"
                    _record_rate(artifact_rates, artifact_name, did_win)

            for team_num, ultimate_id in metrics.ultimate_events:
                row = ultimate_spell_rates[ultimate_id]
                row[0] += 1
                if metrics.winner == team_num:
                    row[1] += 1
            for kind, count in metrics.action_opportunities.items():
                action_phase_opportunities[kind] += count
            for kind, count in metrics.action_uses.items():
                action_phase_uses[kind] += count
            for kind, count in metrics.bonus_opportunities.items():
                bonus_phase_opportunities[kind] += count
            for kind, count in metrics.bonus_uses.items():
                bonus_phase_uses[kind] += count
            ultimate_ready_opportunities += metrics.ultimate_ready_opportunities
            ultimate_ready_uses += metrics.ultimate_ready_uses
            urgent_switch_opportunities += metrics.urgent_switch_opportunities
            urgent_switch_uses += metrics.urgent_switch_uses

        run_lengths.append(run_battles)
        battle_log_lines.append(
            f"=== QUEST RUN {run_index} END | Battles={run_battles} | Wins={run_wins} | "
            f"FinalLosses=3 ==="
        )
        battle_log_lines.append("")

    if total_battles < target_battles:
        raise RuntimeError(
            f"Simulation produced fewer than target battles ({total_battles} < {target_battles})."
        )

    summary_lines = [
        "Fabled Quest Simulation Statistics",
        f"Seed: {seed}",
        f"Difficulty (Player/Enemy): {difficulty_player}/{difficulty_enemy}",
        f"Total Quest Runs: {len(run_lengths)}",
        f"Total Battles: {total_battles}",
        "",
        f"Average quest run length: {sum(run_lengths) / max(1, len(run_lengths)):.2f}",
        f"Average battle length (rounds): {sum(battle_lengths) / max(1, len(battle_lengths)):.2f}",
        f"Average swaps per battle: {sum(swaps_per_battle) / max(1, len(swaps_per_battle)):.2f}",
        f"Average switch weapons per battle: {sum(switches_per_battle) / max(1, len(switches_per_battle)):.2f}",
        f"Average ultimate spells per battle: {sum(ultimates_per_battle) / max(1, len(ultimates_per_battle)):.2f}",
        "",
    ]

    total_ultimate_casts = sum(cast_count for cast_count, _ in ultimate_spell_rates.values())
    total_ultimate_wins = sum(win_count for _, win_count in ultimate_spell_rates.values())
    overall_ultimate_winrate = (
        (total_ultimate_wins / total_ultimate_casts * 100.0) if total_ultimate_casts > 0 else 0.0
    )
    summary_lines.append(
        f"Ultimate spell winrate (overall): {total_ultimate_wins}/{total_ultimate_casts} "
        f"({overall_ultimate_winrate:.2f}%)"
    )
    summary_lines.append("")

    summary_lines.append("AI Action Coverage Audit:")
    core_action_kinds = ("strike", "spell", "switch", "swap", "skip", "ultimate")
    summary_lines.append("Action phase coverage:")
    for kind in core_action_kinds:
        opportunities = action_phase_opportunities.get(kind, 0)
        uses = action_phase_uses.get(kind, 0)
        pct = (uses / opportunities * 100.0) if opportunities > 0 else 0.0
        status = "OK" if (opportunities == 0 or uses > 0) else "FLAG"
        summary_lines.append(
            f"  {kind}: uses={uses} / opportunities={opportunities} ({pct:.2f}%) [{status}]"
        )
    summary_lines.append("Bonus phase coverage:")
    bonus_kinds = ("spell", "switch", "swap", "skip", "ultimate")
    for kind in bonus_kinds:
        opportunities = bonus_phase_opportunities.get(kind, 0)
        uses = bonus_phase_uses.get(kind, 0)
        pct = (uses / opportunities * 100.0) if opportunities > 0 else 0.0
        status = "OK" if (opportunities == 0 or uses > 0) else "FLAG"
        summary_lines.append(
            f"  {kind}: uses={uses} / opportunities={opportunities} ({pct:.2f}%) [{status}]"
        )
    ultimate_ready_pct = (
        (ultimate_ready_uses / ultimate_ready_opportunities * 100.0)
        if ultimate_ready_opportunities > 0
        else 0.0
    )
    urgent_switch_pct = (
        (urgent_switch_uses / urgent_switch_opportunities * 100.0)
        if urgent_switch_opportunities > 0
        else 0.0
    )
    summary_lines.append(
        f"Ultimate readiness conversion: {ultimate_ready_uses}/{ultimate_ready_opportunities} "
        f"({ultimate_ready_pct:.2f}%)"
    )
    summary_lines.append(
        f"Urgent switch conversion (stalled primary): {urgent_switch_uses}/{urgent_switch_opportunities} "
        f"({urgent_switch_pct:.2f}%)"
    )
    summary_lines.append("")

    summary_lines.extend(_format_rate_section("Adventurer winrate:", adventurer_rates))
    summary_lines.append("")
    summary_lines.extend(_format_rate_section("Class winrate:", class_rates))
    summary_lines.append("")
    summary_lines.extend(_format_rate_section("Class skill winrate:", class_skill_rates))
    summary_lines.append("")
    summary_lines.extend(_format_rate_section("Artifact winrate:", artifact_rates))
    summary_lines.append("")
    summary_lines.extend(_format_rate_section("Primary weapon winrate:", primary_weapon_rates))
    summary_lines.append("")

    by_ultimate_name: dict[str, list[int]] = {}
    for ultimate_id, (casts, wins) in ultimate_spell_rates.items():
        name = ultimate_name_by_id.get(ultimate_id, ultimate_id)
        by_ultimate_name[name] = [casts, wins]
    summary_lines.extend(_format_rate_section("Ultimate spell winrate (by spell):", by_ultimate_name))

    return "\n".join(battle_log_lines).rstrip() + "\n", "\n".join(summary_lines).rstrip() + "\n", total_battles


def main():
    parser = argparse.ArgumentParser(description="Run AI quest-run simulations and emit logs/statistics.")
    parser.add_argument("--target-battles", type=int, default=300, help="Minimum number of simulated battles.")
    parser.add_argument("--seed", type=int, default=20260402, help="Random seed.")
    parser.add_argument("--difficulty-player", default="hard", choices=("easy", "normal", "hard", "ranked"))
    parser.add_argument("--difficulty-enemy", default="hard", choices=("easy", "normal", "hard", "ranked"))
    parser.add_argument("--max-rounds", type=int, default=16, help="Maximum rounds per battle before timeout.")
    parser.add_argument("--log-file", default="quest_simulation_log.txt")
    parser.add_argument("--stats-file", default="quest_simulation_stats.txt")
    args = parser.parse_args()

    log_text, stats_text, total_battles = run_simulation(
        target_battles=args.target_battles,
        seed=args.seed,
        difficulty_player=args.difficulty_player,
        difficulty_enemy=args.difficulty_enemy,
        max_rounds=args.max_rounds,
    )

    with open(args.log_file, "w", encoding="utf-8") as handle:
        handle.write(log_text)
    with open(args.stats_file, "w", encoding="utf-8") as handle:
        handle.write(stats_text)

    print(f"Simulation complete. Battles: {total_battles}")
    print(f"Log file: {args.log_file}")
    print(f"Stats file: {args.stats_file}")


if __name__ == "__main__":
    main()
