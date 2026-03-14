import ast
import argparse
import random
from pathlib import Path

import ai
import battle_log
from data import CLASS_BASICS, ITEMS, ROSTER
from logic import (
    apply_passive_stats,
    apply_round_start_effects,
    create_team,
    describe_action,
    determine_initiative,
    do_swap,
    end_round,
    resolve_player_turn,
    resolve_queued_action,
)
from models import BattleState
from settings import CLOCKWISE_ORDER, SLOT_FRONT


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = ROOT / "battlesim.txt"
DEFAULT_TOTAL_BATTLES = 32
DEFAULT_RNG_SEED = 1337


def load_meta_team_pool():
    source = (ROOT / "main.py").read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(ROOT / "main.py"))
    for node in ast.walk(module):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr == "_ai_team_pool":
                return ast.literal_eval(node.value)
    raise RuntimeError("Could not locate self._ai_team_pool in main.py")


def build_ai_pick(entry, roster_by_id, items_by_id):
    defn = roster_by_id[entry["defn"]]
    sig = next(ability for ability in defn.sig_options if ability.id == entry["sig"])
    basics_pool = CLASS_BASICS[defn.cls]
    basics = [next(ability for ability in basics_pool if ability.id == bid) for bid in entry["basics"]]
    item = items_by_id[entry["item"]]
    return {
        "definition": defn,
        "signature": sig,
        "basics": basics,
        "item": item,
    }


def queued_swap_exists(team):
    return any(unit.queued and unit.queued.get("type") == "swap" for unit in team.members)


def clear_team_queues(team):
    for unit in team.members:
        unit.queued = None
        unit.queued2 = None


def queue_actions_for_player(battle, player_num):
    team = battle.get_team(player_num)
    clear_team_queues(team)
    battle.swap_used_this_turn = False

    selection_order = []
    for slot in CLOCKWISE_ORDER:
        unit = team.get_slot(slot)
        if unit and not unit.ko:
            selection_order.append((unit, False))
            if unit.extra_actions_now > 0:
                selection_order.append((unit, True))

    for actor, is_extra in selection_order:
        if actor.ko:
            continue
        action = ai.pick_action(
            battle=battle,
            player_num=player_num,
            actor=actor,
            is_extra=is_extra,
            swap_used=battle.swap_used_this_turn,
            swap_queued=queued_swap_exists(team),
        )
        if not action:
            action = {"type": "skip"}
        action["queued_from_slot"] = actor.slot
        if is_extra:
            actor.queued2 = action
        else:
            actor.queued = action
        battle.log_noshow(f"[Queued] {actor.name}: {describe_action(action)}")


def resolve_stitch_extras(battle, player_num):
    while not battle.winner:
        extras = [
            unit for unit in battle.get_team(player_num).alive()
            if unit.extra_actions_now > 0 and unit.queued2 is None
        ]
        if not extras:
            return
        for unit in extras:
            action = ai.pick_action(
                battle=battle,
                player_num=player_num,
                actor=unit,
                is_extra=True,
                swap_used=battle.swap_used_this_turn,
                swap_queued=queued_swap_exists(battle.get_team(player_num)),
            )
            if not action:
                action = {"type": "skip"}
            action["queued_from_slot"] = unit.slot
            unit.queued2 = action
            battle.log_noshow(f"[Queued] {unit.name}: {describe_action(action)}")
            unit.extra_actions_now -= 1
            saved = unit.queued
            unit.queued = unit.queued2
            unit.queued2 = None
            resolve_queued_action(unit, player_num, battle)
            unit.queued = saved
            if battle.winner:
                return


def apply_round_one_extra_swap(battle):
    player_num = battle.r1_extra_swap_player
    if player_num is None:
        return
    team = battle.get_team(player_num)
    front = team.frontline()
    if not front:
        return
    backliners = [unit for unit in team.alive() if unit.slot != SLOT_FRONT]
    if not backliners:
        battle.log_add(f"P{player_num} passed on free swap.")
        return
    strongest = max(backliners, key=lambda unit: unit.get_stat("defense") + unit.get_stat("attack"))
    if strongest.get_stat("defense") > front.get_stat("defense") + 5:
        do_swap(front, strongest, team, battle)
    else:
        battle.log_add(f"P{player_num} passed on free swap.")


def write_team_section(label, comp_name, picks):
    battle_log.log(f"{label}: {comp_name}")
    for idx, pick in enumerate(picks):
        defn = pick["definition"]
        slot_label = ["front", "back_left", "back_right"][idx]
        battle_log.log(
            f"  [{slot_label}] {defn.name} ({defn.cls})"
            f"  HP={defn.hp}  ATK={defn.attack}  DEF={defn.defense}  SPD={defn.speed}"
        )
        battle_log.log(f"    Talent: {defn.talent_name}")
        battle_log.log(f"    Sig:    {pick['signature'].name}  (passive={pick['signature'].passive})")
        battle_log.log(f"    Basics: {', '.join(ability.name for ability in pick['basics'])}")
        battle_log.log(f"    Item:   {pick['item'].name}")


def simulate_battle(battle_num, comp1, picks1, comp2, picks2):
    battle_log.init()
    battle_log.section(f"BATTLE {battle_num}")
    battle_log.section("TEAM COMPOSITIONS")
    write_team_section("Player 1", comp1, picks1)
    write_team_section("Player 2", comp2, picks2)
    battle_log.section("BATTLE START")

    battle = BattleState(
        team1=create_team(comp1, picks1),
        team2=create_team(comp2, picks2),
    )

    safety = 0
    while not battle.winner and safety < 50:
        safety += 1
        apply_passive_stats(battle.team1, battle)
        apply_passive_stats(battle.team2, battle)
        apply_round_start_effects(battle)
        determine_initiative(battle)
        if battle.round_num == 1:
            apply_round_one_extra_swap(battle)

        init_player = battle.init_player
        second_player = 3 - init_player
        for player_num in (init_player, second_player):
            queue_actions_for_player(battle, player_num)
            resolve_player_turn(battle, player_num)
            resolve_stitch_extras(battle, player_num)
            if battle.winner:
                break
            if player_num == second_player:
                battle.log_add("─── End of Round ───")
                end_round(battle)

    if not battle.winner:
        battle.log_add("Battle aborted after safety limit.")
    battle_log.close()
    return battle.winner


def parse_args():
    parser = argparse.ArgumentParser(description="Simulate meta AI battles and export combined logs.")
    parser.add_argument("--count", type=int, default=DEFAULT_TOTAL_BATTLES, help="Number of battles to simulate.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output text file path.")
    parser.add_argument("--seed", type=int, default=DEFAULT_RNG_SEED, help="Random seed for match selection.")
    return parser.parse_args()


def main():
    args = parse_args()
    random.seed(args.seed)
    pool = load_meta_team_pool()
    roster_by_id = {defn.id: defn for defn in ROSTER}
    items_by_id = {item.id: item for item in ITEMS}

    combined = [
        f"Fabled meta AI battle batch",
        f"Seed: {args.seed}",
        f"Battles: {args.count}",
        "",
    ]

    for battle_num in range(1, args.count + 1):
        comp1, comp2 = random.sample(pool, 2)
        picks1 = [build_ai_pick(entry, roster_by_id, items_by_id) for entry in comp1["members"]]
        picks2 = [build_ai_pick(entry, roster_by_id, items_by_id) for entry in comp2["members"]]
        winner = simulate_battle(battle_num, comp1["name"], picks1, comp2["name"], picks2)
        log_text = Path(battle_log._log_path()).read_text(encoding="utf-8", errors="replace")
        combined.append(f"========== BATTLE {battle_num} ==========")
        combined.append(f"Player 1: {comp1['name']}")
        combined.append(f"Player 2: {comp2['name']}")
        combined.append(f"Winner: P{winner}" if winner else "Winner: unresolved")
        combined.append("")
        combined.append(log_text.rstrip())
        combined.append("")

    args.output.write_text("\n".join(combined) + "\n", encoding="utf-8")
    print(f"Wrote {args.count} battle logs to {args.output}")


if __name__ == "__main__":
    main()
