import argparse
import math
from collections import Counter, defaultdict
from itertools import combinations, combinations_with_replacement
from pathlib import Path

import ai
import battle_log
import logic
from ai_team_pool import AI_TEAM_POOL
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
OUTPUT_DIR = ROOT / "team_round_robin_battles"
EXPECTED_TEAM_COUNT = 40
ROUND_LIMIT = 50
BATTLES_PER_FILE = 100
STATS_FILE_NAME = "battle_stats.txt"

MELEE_CLASSES = {"Fighter", "Rogue", "Warden"}
RANGED_CLASSES = {"Ranger", "Mage", "Cleric"}
MIXED_CLASSES = {"Noble", "Warlock"}


def load_ai_team_pool():
    if len(AI_TEAM_POOL) != EXPECTED_TEAM_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_TEAM_COUNT} AI teams, found {len(AI_TEAM_POOL)}."
        )
    return AI_TEAM_POOL


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


def type_for_class(cls_name):
    if cls_name in MELEE_CLASSES:
        return "melee"
    if cls_name in RANGED_CLASSES:
        return "ranged"
    if cls_name in MIXED_CLASSES:
        return "mixed"
    return "unknown"


def make_pair_key(name_a, name_b):
    ordered = sorted((name_a, name_b))
    return f"{ordered[0]} + {ordered[1]}"


def make_set_key(unit):
    basics = sorted(ability.name for ability in unit.basics)
    return f"{unit.name} | {unit.sig.name} | {basics[0]} + {basics[1]} | {unit.item.name}"


def init_rate_stat():
    return {"appearances": 0, "wins": 0}


def init_average_stat():
    return {"appearances": 0, "total": 0.0}


def update_rate(stat_map, key, won):
    record = stat_map[key]
    record["appearances"] += 1
    if won:
        record["wins"] += 1


def update_average(stat_map, key, value):
    record = stat_map[key]
    record["appearances"] += 1
    record["total"] += value


def finalize_rate_stats(counter_map, limit=None):
    rows = []
    for name, record in counter_map.items():
        appearances = record["appearances"]
        wins = record["wins"]
        rows.append(
            {
                "name": name,
                "appearances": appearances,
                "wins": wins,
                "losses": appearances - wins,
                "winrate": wins / appearances if appearances else 0.0,
            }
        )
    rows.sort(key=lambda row: (-row["winrate"], -row["appearances"], row["name"]))
    if limit is not None:
        return rows[:limit]
    return rows


def finalize_last_stand_stats(counter_map):
    rows = []
    for name, record in counter_map.items():
        appearances = record["appearances"]
        last_stands = record["last_stands"]
        rows.append(
            {
                "name": name,
                "appearances": appearances,
                "last_stands": last_stands,
                "last_standing_rate": last_stands / appearances if appearances else 0.0,
            }
        )
    return sorted(rows, key=lambda row: (-row["last_standing_rate"], -row["last_stands"], row["name"]))


def finalize_average_stats(counter_map, value_key, average_key):
    rows = []
    for name, record in counter_map.items():
        appearances = record["appearances"]
        total = record["total"]
        rows.append(
            {
                "name": name,
                "appearances": appearances,
                value_key: total,
                average_key: total / appearances if appearances else 0.0,
            }
        )
    return sorted(rows, key=lambda row: (-row[average_key], -row[value_key], row["name"]))


def build_side_metadata(team_name, battle_team):
    units = []
    for unit in battle_team.members:
        units.append(
            {
                "unit": unit,
                "team": team_name,
                "archetype": team_name,
                "adventurer": unit.name,
                "class": unit.cls,
                "type": type_for_class(unit.cls),
                "signature": unit.sig.name,
                "twist": unit.defn.twist.name,
                "item": unit.item.name,
                "basics": [ability.name for ability in unit.basics],
                "set": make_set_key(unit),
            }
        )
    return units


class DamageTracker:
    def __init__(self):
        self.frames = []
        self.damage_by_unit = Counter()
        self.active_battle_id = None

    def note_heal(self, target, actual_heal):
        if actual_heal <= 0:
            return
        for frame in reversed(self.frames):
            if frame["actor"] is target:
                frame["actor_healed"] += actual_heal
                break

    def wrap_deal_damage(self, original):
        tracker = self

        def wrapped(actor, target, dmg, ability, mode, acting_player, battle, is_retaliation=False):
            if id(battle) != tracker.active_battle_id:
                return original(actor, target, dmg, ability, mode, acting_player, battle, is_retaliation=is_retaliation)

            actor_hp_before = actor.hp
            target_hp_before = target.hp
            frame = {
                "actor": actor,
                "actor_hp_before": actor_hp_before,
                "target_hp_before": target_hp_before,
                "actor_healed": 0,
                "nested_damage_to_actor": 0,
                "shock_recoil": 0,
                "raw_damage": dmg,
                "actor_shocked": actor.has_status("shock"),
            }
            tracker.frames.append(frame)
            try:
                result = original(actor, target, dmg, ability, mode, acting_player, battle, is_retaliation=is_retaliation)
            finally:
                tracker.frames.pop()

            primary_damage = max(0, target_hp_before - target.hp)
            if primary_damage > 0:
                tracker.damage_by_unit[actor] += primary_damage

            if frame["actor_shocked"] and dmg > 0:
                recoil = max(1, math.ceil(dmg * 0.20))
                frame["shock_recoil"] = min(actor_hp_before, recoil)

            total_actor_damage_taken = max(0, actor_hp_before - actor.hp + frame["actor_healed"])
            counter_damage = max(0, total_actor_damage_taken - frame["shock_recoil"] - frame["nested_damage_to_actor"])
            if counter_damage > 0:
                tracker.damage_by_unit[target] += counter_damage

            if tracker.frames and target is tracker.frames[-1]["actor"]:
                tracker.frames[-1]["nested_damage_to_actor"] += primary_damage

            return result

        return wrapped

    def wrap_do_heal(self, original):
        tracker = self

        def wrapped(target, amount, healer, battle, action_desc=""):
            before = target.hp
            result = original(target, amount, healer, battle, action_desc)
            tracker.note_heal(target, max(0, target.hp - before))
            return result

        return wrapped


class SwapTracker:
    def __init__(self):
        self.current_swaps = 0
        self.active_battle_id = None

    def wrap_do_swap(self, original):
        tracker = self

        def wrapped(unit_a, unit_b, team, battle):
            if id(battle) == tracker.active_battle_id:
                tracker.current_swaps += 1
            return original(unit_a, unit_b, team, battle)

        return wrapped


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


def simulate_battle(battle_num, comp1, picks1, comp2, picks2, damage_tracker=None, swap_tracker=None):
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
    if damage_tracker is not None:
        damage_tracker.active_battle_id = id(battle)
    if swap_tracker is not None:
        swap_tracker.active_battle_id = id(battle)
    side_info = build_side_metadata(comp1, battle.team1) + build_side_metadata(comp2, battle.team2)
    info_by_unit = {entry["unit"]: entry for entry in side_info}

    safety = 0
    while not battle.winner and safety < ROUND_LIMIT:
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
                battle.log_add("--- End of Round ---")
                end_round(battle)

    if not battle.winner:
        battle.log_add("Battle aborted after safety limit.")
    battle_log.close()
    log_text = Path(battle_log._log_path()).read_text(encoding="utf-8", errors="replace")
    return battle, info_by_unit, log_text


def battle_batch_output_path(batch_num):
    return OUTPUT_DIR / f"battle_batch_{batch_num:02d}.txt"


def stats_output_path():
    return OUTPUT_DIR / STATS_FILE_NAME


def append_battle_to_batch(path, battle_num, team_a, team_b, winner, log_text):
    lines = [
        "=" * 80,
        f"Battle {battle_num}",
        f"Player 1 Team: {team_a}",
        f"Player 2 Team: {team_b}",
        f"Winner: P{winner}" if winner else "Winner: unresolved",
        "=" * 80,
        log_text.rstrip(),
        "",
        "",
    ]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def render_table(rows, columns):
    widths = {}
    for column in columns:
        widths[column] = len(column)
    for row in rows:
        for column in columns:
            value = row[column]
            text = f"{value:.4f}" if isinstance(value, float) else str(value)
            widths[column] = max(widths[column], len(text))

    header = " | ".join(column.ljust(widths[column]) for column in columns)
    divider = "-+-".join("-" * widths[column] for column in columns)
    body = []
    for row in rows:
        cells = []
        for column in columns:
            value = row[column]
            text = f"{value:.4f}" if isinstance(value, float) else str(value)
            cells.append(text.ljust(widths[column]))
        body.append(" | ".join(cells))
    return "\n".join([header, divider] + body)


def render_stats_report(report):
    sections = [
        "Round Robin Summary",
        f"Battles simulated: {report['summary']['battles']}",
        f"Average game length: {report['summary']['average_game_length']:.4f}",
        f"Average swaps per game: {report['summary']['average_swaps_per_game']:.4f}",
        "",
        "Notes",
        "- Winrates are appearance-based across team sides.",
        "- Archetype refers to the AI team name/loadout.",
        "- Last standing rate counts only wins where a single adventurer survived.",
        "- Average game length per class is averaged across adventurer appearances of that class.",
        "",
        "Class Winrate",
        render_table(report["class_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Adventurer Winrate",
        render_table(report["adventurer_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Signature Ability Winrate",
        render_table(report["signature_ability_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Basic Ability Winrate",
        render_table(report["basic_ability_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Twist Ability Winrate",
        render_table(report["twist_ability_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Damage Type Winrate",
        render_table(report["damage_type_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Last Adventurer Standing Rate by Adventurer",
        render_table(report["last_standing_by_adventurer"], ["name", "appearances", "last_stands", "last_standing_rate"]),
        "",
        "Last Adventurer Standing Rate by Class",
        render_table(report["last_standing_by_class"], ["name", "appearances", "last_stands", "last_standing_rate"]),
        "",
        "Item Winrate",
        render_table(report["item_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Top 10 Adventurer Pairings by Winrate",
        render_table(report["top_adventurer_pairings"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Top 10 Adventurer Sets by Winrate",
        render_table(report["top_adventurer_sets"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Top 10 Archetypes by Winrate",
        render_table(report["top_archetypes"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "Average Damage per Class",
        render_table(report["average_damage_per_class"], ["name", "appearances", "total_damage", "average_damage"]),
        "",
        "Average Game Length per Class",
        render_table(report["average_game_length_per_class"], ["name", "appearances", "total_rounds", "average_game_length"]),
    ]
    return "\n".join(sections) + "\n"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulate every AI team against every AI team once, including self-matchups."
    )
    return parser.parse_args()


def prepare_output_dir():
    OUTPUT_DIR.mkdir(exist_ok=True)
    existing_files = sorted(OUTPUT_DIR.glob("*.txt"))
    for old_file in existing_files:
        old_file.unlink()


def build_report(
    total_battles,
    total_rounds,
    total_swaps,
    class_stats,
    adventurer_stats,
    signature_stats,
    basic_stats,
    twist_stats,
    type_stats,
    item_stats,
    pairing_stats,
    set_stats,
    archetype_stats,
    last_stand_adventurer,
    last_stand_class,
    class_damage,
    class_game_length,
):
    return {
        "summary": {
            "battles": total_battles,
            "average_game_length": total_rounds / total_battles if total_battles else 0.0,
            "average_swaps_per_game": total_swaps / total_battles if total_battles else 0.0,
        },
        "class_winrate": finalize_rate_stats(class_stats),
        "adventurer_winrate": finalize_rate_stats(adventurer_stats),
        "signature_ability_winrate": finalize_rate_stats(signature_stats),
        "basic_ability_winrate": finalize_rate_stats(basic_stats),
        "twist_ability_winrate": finalize_rate_stats(twist_stats),
        "damage_type_winrate": finalize_rate_stats(type_stats),
        "last_standing_by_adventurer": finalize_last_stand_stats(last_stand_adventurer),
        "last_standing_by_class": finalize_last_stand_stats(last_stand_class),
        "item_winrate": finalize_rate_stats(item_stats),
        "top_adventurer_pairings": finalize_rate_stats(pairing_stats, limit=10),
        "top_adventurer_sets": finalize_rate_stats(set_stats, limit=10),
        "top_archetypes": finalize_rate_stats(archetype_stats, limit=10),
        "average_damage_per_class": finalize_average_stats(class_damage, "total_damage", "average_damage"),
        "average_game_length_per_class": finalize_average_stats(class_game_length, "total_rounds", "average_game_length"),
    }


def main():
    parse_args()
    pool = load_ai_team_pool()
    roster_by_id = {defn.id: defn for defn in ROSTER}
    items_by_id = {item.id: item for item in ITEMS}
    prepare_output_dir()

    damage_tracker = DamageTracker()
    swap_tracker = SwapTracker()

    original_deal_damage = logic.deal_damage
    original_do_heal = logic.do_heal
    original_logic_do_swap = logic.do_swap
    original_local_do_swap = do_swap

    tracked_do_swap = swap_tracker.wrap_do_swap(original_logic_do_swap)
    logic.deal_damage = damage_tracker.wrap_deal_damage(original_deal_damage)
    logic.do_heal = damage_tracker.wrap_do_heal(original_do_heal)
    logic.do_swap = tracked_do_swap
    globals()["do_swap"] = tracked_do_swap

    class_stats = defaultdict(init_rate_stat)
    adventurer_stats = defaultdict(init_rate_stat)
    signature_stats = defaultdict(init_rate_stat)
    basic_stats = defaultdict(init_rate_stat)
    twist_stats = defaultdict(init_rate_stat)
    type_stats = defaultdict(init_rate_stat)
    item_stats = defaultdict(init_rate_stat)
    pairing_stats = defaultdict(init_rate_stat)
    set_stats = defaultdict(init_rate_stat)
    archetype_stats = defaultdict(init_rate_stat)
    last_stand_adventurer = defaultdict(lambda: {"appearances": 0, "last_stands": 0})
    last_stand_class = defaultdict(lambda: {"appearances": 0, "last_stands": 0})
    class_damage = defaultdict(init_average_stat)
    class_game_length = defaultdict(init_average_stat)

    total_battles = 0
    total_rounds = 0
    total_swaps = 0

    try:
        for battle_num, (comp1, comp2) in enumerate(combinations_with_replacement(pool, 2), start=1):
            picks1 = [build_ai_pick(entry, roster_by_id, items_by_id) for entry in comp1["members"]]
            picks2 = [build_ai_pick(entry, roster_by_id, items_by_id) for entry in comp2["members"]]

            swap_tracker.current_swaps = 0
            before_damage = damage_tracker.damage_by_unit.copy()
            battle, info_by_unit, log_text = simulate_battle(
                battle_num,
                comp1["name"],
                picks1,
                comp2["name"],
                picks2,
                damage_tracker=damage_tracker,
                swap_tracker=swap_tracker,
            )
            damage_tracker.active_battle_id = None
            swap_tracker.active_battle_id = None

            rounds_played = min(battle.round_num, ROUND_LIMIT)
            total_battles += 1
            total_rounds += rounds_played
            total_swaps += swap_tracker.current_swaps

            batch_num = ((battle_num - 1) // BATTLES_PER_FILE) + 1
            batch_path = battle_batch_output_path(batch_num)
            append_battle_to_batch(batch_path, battle_num, comp1["name"], comp2["name"], battle.winner, log_text)

            winning_team_name = None
            if battle.winner == 1:
                winning_team_name = comp1["name"]
            elif battle.winner == 2:
                winning_team_name = comp2["name"]

            for player_num, comp in ((1, comp1), (2, comp2)):
                won = battle.winner == player_num
                update_rate(archetype_stats, comp["name"], won)
                team_members = battle.get_team(player_num).members
                for unit_a, unit_b in combinations(team_members, 2):
                    update_rate(pairing_stats, make_pair_key(unit_a.name, unit_b.name), won)

            for unit, info in info_by_unit.items():
                won = info["team"] == winning_team_name
                update_rate(class_stats, info["class"], won)
                update_rate(adventurer_stats, info["adventurer"], won)
                update_rate(signature_stats, info["signature"], won)
                update_rate(item_stats, info["item"], won)
                update_rate(twist_stats, info["twist"], won)
                update_rate(type_stats, info["type"], won)
                update_rate(set_stats, info["set"], won)
                for basic in info["basics"]:
                    update_rate(basic_stats, basic, won)

                last_stand_adventurer[info["adventurer"]]["appearances"] += 1
                last_stand_class[info["class"]]["appearances"] += 1
                update_average(class_game_length, info["class"], rounds_played)
                class_damage[info["class"]]["appearances"] += 1

            if battle.winner in (1, 2):
                alive_winners = [unit for unit in battle.get_team(battle.winner).members if not unit.ko]
                if len(alive_winners) == 1:
                    survivor = alive_winners[0]
                    last_stand_adventurer[survivor.name]["last_stands"] += 1
                    last_stand_class[survivor.cls]["last_stands"] += 1

            damage_delta = damage_tracker.damage_by_unit - before_damage
            for unit, delta in damage_delta.items():
                if delta <= 0 or unit not in info_by_unit:
                    continue
                class_damage[info_by_unit[unit]["class"]]["total"] += delta

            if battle_num % 50 == 0:
                print(f"Simulated {battle_num} battles...")
    finally:
        logic.deal_damage = original_deal_damage
        logic.do_heal = original_do_heal
        logic.do_swap = original_logic_do_swap
        globals()["do_swap"] = original_local_do_swap

    report = build_report(
        total_battles=total_battles,
        total_rounds=total_rounds,
        total_swaps=total_swaps,
        class_stats=class_stats,
        adventurer_stats=adventurer_stats,
        signature_stats=signature_stats,
        basic_stats=basic_stats,
        twist_stats=twist_stats,
        type_stats=type_stats,
        item_stats=item_stats,
        pairing_stats=pairing_stats,
        set_stats=set_stats,
        archetype_stats=archetype_stats,
        last_stand_adventurer=last_stand_adventurer,
        last_stand_class=last_stand_class,
        class_damage=class_damage,
        class_game_length=class_game_length,
    )

    stats_path = stats_output_path()
    stats_path.write_text(render_stats_report(report), encoding="utf-8")
    total_batch_files = (total_battles + BATTLES_PER_FILE - 1) // BATTLES_PER_FILE if total_battles else 0

    print(f"Completed {total_battles} battles.")
    print(f"Wrote {total_batch_files} battle batch files and {STATS_FILE_NAME}.")
    print(f"Output folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
