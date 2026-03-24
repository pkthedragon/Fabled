import json
import math
from collections import Counter, defaultdict
from itertools import combinations, combinations_with_replacement
from pathlib import Path

import logic
import simulate_round_robin_battles as rr
from models import BattleState


ROOT = Path(__file__).resolve().parent
JSON_OUTPUT = ROOT / "round_robin_analysis.json"
MARKDOWN_OUTPUT = ROOT / "round_robin_analysis.md"

ARCHETYPE_MAP = {
    "Anti-Heal Pressure": "Anti-heal / sustain-break",
    "No-Heal Collapse": "Anti-heal / sustain-break",
    "Burnline Pressure": "Anti-heal / sustain-break",
    "Rapunzel Pin Control": "Anti-heal / sustain-break",
    "Expose Hunter": "Expose / pick",
    "Ranger-Rogue Kill Chain": "Expose / pick",
    "Gretel Tempo Kill": "Expose / pick",
    "Backline Hunter": "Expose / pick",
    "Rapunzel Collapse": "Expose / pick",
    "Execute Line": "Expose / pick",
    "Balanced Generalist": "Stable midrange",
    "Safe Midrange": "Stable midrange",
    "Prince-Robin Midrange": "Stable midrange",
    "Frontline Breaker": "Stable midrange",
    "Green Knight Root Midrange": "Stable midrange",
    "Reflection Punish": "Punish / counterattack",
    "Lady Control Shell": "Punish / counterattack",
    "Roland Counterbattery": "Punish / counterattack",
    "Brawler Punish": "Punish / counterattack",
    "Double Rogue Tempo": "Punish / counterattack",
    "Porcus Fortress": "Tank / fortress",
    "Sustain Into Spike": "Tank / fortress",
    "Ella Pivot Shell": "Tank / fortress",
    "Pinocchio Malice Fortress": "Tank / fortress",
    "Root Killbox": "Root / trap",
    "Royal Root Pressure": "Root / trap",
    "Status Spread": "Multi-status control",
    "Burn Shock Split": "Multi-status control",
    "Shock Punish": "Multi-status control",
    "Shocked Quarry": "Multi-status control",
    "Burn-Root Hunter": "Multi-status control",
    "Crowstorm Burn": "Multi-status control",
    "Sea Wench Theft Shell": "Multi-status control",
    "Speed Tempo": "Tempo / speed aggro",
    "Double Ranger Pressure": "Tempo / speed aggro",
    "Last-Stand Brawler": "Last-stand brawler",
    "Last-Stand Midrange": "Last-stand brawler",
    "Pinocchio Spotlight Break": "Malice / scaling utility",
    "Rumpel Buff Engine": "Malice / scaling utility",
    "Sea Wench Debuff Burst": "Malice / scaling utility",
}

MELEE_CLASSES = {"Fighter", "Rogue", "Warden"}
RANGED_CLASSES = {"Ranger", "Mage", "Cleric"}
MIXED_CLASSES = {"Noble", "Warlock"}


def silent_log_add(self, msg):
    return None


def silent_log_noshow(self, msg):
    return None


def silent_log_tech(self, msg):
    return None


BattleState.log_add = silent_log_add
BattleState.log_noshow = silent_log_noshow
BattleState.log_tech = silent_log_tech


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
    return f"{unit.name} | {unit.sig.name} | {basics[0]} + {basics[1]}"


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
                "target": target,
                "actor_hp_before": actor_hp_before,
                "target_hp_before": target_hp_before,
                "actor_healed": 0,
                "nested_damage_to_actor": 0,
                "raw_damage": dmg,
            }
            tracker.frames.append(frame)
            try:
                result = original(actor, target, dmg, ability, mode, acting_player, battle, is_retaliation=is_retaliation)
            finally:
                tracker.frames.pop()

            primary_damage = max(0, target_hp_before - target.hp)
            if primary_damage > 0:
                tracker.damage_by_unit[actor] += primary_damage

            total_actor_damage_taken = max(
                0,
                actor_hp_before - actor.hp + frame["actor_healed"],
            )
            counter_damage = max(
                0,
                total_actor_damage_taken - frame["nested_damage_to_actor"],
            )
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
            actual = max(0, target.hp - before)
            tracker.note_heal(target, actual)
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


def load_metadata(pool):
    roster_by_id = {defn.id: defn for defn in rr.ROSTER}
    artifacts_by_id = dict(rr.ARTIFACTS_BY_ID)
    return roster_by_id, artifacts_by_id


def init_rate_stat():
    return {"appearances": 0, "wins": 0}


def finalize_rate_stats(counter_map):
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
    return sorted(rows, key=lambda row: (-row["winrate"], -row["appearances"], row["name"]))


def finalize_appearance_stats(counter, total):
    rows = []
    for name, appearances in counter.items():
        rows.append(
            {
                "name": name,
                "appearances": appearances,
                "appearance_rate": appearances / total if total else 0.0,
            }
        )
    return sorted(rows, key=lambda row: (-row["appearance_rate"], -row["appearances"], row["name"]))


def finalize_damage_stats(counter_map):
    rows = []
    for name, record in counter_map.items():
        matches = record["matches"]
        total_damage = record["damage"]
        rows.append(
            {
                "name": name,
                "matches": matches,
                "total_damage": total_damage,
                "average_dpm": total_damage / matches if matches else 0.0,
            }
        )
    return sorted(rows, key=lambda row: (-row["average_dpm"], -row["total_damage"], row["name"]))


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


def make_battle(comp1, picks1, comp2, picks2):
    return BattleState(
        team1=logic.create_team(comp1, picks1),
        team2=logic.create_team(comp2, picks2),
    )


def build_side_metadata(team_name, battle_team):
    units = []
    archetype = ARCHETYPE_MAP.get(team_name, team_name)
    for unit in battle_team.members:
        units.append(
            {
                "unit": unit,
                "team": team_name,
                "archetype": archetype,
                "adventurer": unit.name,
                "class": unit.cls,
                "type": type_for_class(unit.cls),
                "signature": unit.sig.name,
                "twist": unit.defn.twist.name,
                "basics": [ability.name for ability in unit.basics],
                "set": make_set_key(unit),
            }
        )
    return units


def simulate_matchup(comp1, picks1, artifacts1, comp2, picks2, artifacts2, damage_tracker, swap_tracker, ai_profile):
    battle = BattleState(
        team1=logic.create_team(comp1["name"], picks1, artifacts1),
        team2=logic.create_team(comp2["name"], picks2, artifacts2),
    )
    if damage_tracker is not None:
        damage_tracker.active_battle_id = id(battle)
    if swap_tracker is not None:
        swap_tracker.active_battle_id = id(battle)
    side_info = build_side_metadata(comp1["name"], battle.team1) + build_side_metadata(comp2["name"], battle.team2)
    info_by_unit = {entry["unit"]: entry for entry in side_info}
    try:
        safety = 0
        while not battle.winner and safety < rr.ROUND_LIMIT:
            safety += 1
            logic.apply_passive_stats(battle.team1, battle)
            logic.apply_passive_stats(battle.team2, battle)
            logic.apply_round_start_effects(battle)
            logic.determine_initiative(battle)
            if battle.round_num == 1:
                rr.apply_round_one_extra_swap(battle)

            init_player = battle.init_player
            second_player = 3 - init_player
            for player_num in (init_player, second_player):
                rr.queue_actions_for_player(battle, player_num, ai_profile=ai_profile)
                logic.resolve_player_turn(battle, player_num)
                rr.resolve_stitch_extras(battle, player_num, ai_profile=ai_profile)
                if battle.winner:
                    break
                if player_num == second_player:
                    logic.end_round(battle)
    finally:
        if damage_tracker is not None:
            damage_tracker.active_battle_id = None
        if swap_tracker is not None:
            swap_tracker.active_battle_id = None
    return battle, info_by_unit


def update_rate(stat_map, key, won):
    record = stat_map[key]
    record["appearances"] += 1
    if won:
        record["wins"] += 1


def main():
    pool = rr.load_ai_team_pool()
    args = rr.parse_args()
    roster_by_id, artifacts_by_id = load_metadata(pool)

    damage_tracker = None
    swap_tracker = SwapTracker()

    original_do_swap_logic = logic.do_swap
    original_do_swap_rr = rr.do_swap

    logic.do_swap = swap_tracker.wrap_do_swap(original_do_swap_logic)
    rr.do_swap = logic.do_swap

    team_stats = defaultdict(init_rate_stat)
    archetype_stats = defaultdict(init_rate_stat)
    class_stats = defaultdict(init_rate_stat)
    type_stats = defaultdict(init_rate_stat)
    adventurer_stats = defaultdict(init_rate_stat)
    pairing_stats = defaultdict(init_rate_stat)
    signature_stats = defaultdict(init_rate_stat)
    basic_stats = defaultdict(init_rate_stat)
    artifact_stats = defaultdict(init_rate_stat)
    twist_stats = defaultdict(init_rate_stat)
    set_stats = defaultdict(init_rate_stat)

    adventurer_appearances = Counter()
    class_appearances = Counter()
    signature_appearances = Counter()
    basic_appearances = Counter()
    artifact_appearances = Counter()

    last_stand_stats = defaultdict(lambda: {"appearances": 0, "last_stands": 0})
    adventurer_damage = defaultdict(lambda: {"matches": 0, "damage": 0})
    class_damage = defaultdict(lambda: {"matches": 0, "damage": 0})

    total_battles = 0
    total_rounds = 0
    total_swaps = 0

    try:
        for comp1, comp2 in combinations_with_replacement(pool, 2):
            swap_tracker.current_swaps = 0
            picks1 = [rr.build_ai_pick(entry, roster_by_id) for entry in comp1["members"]]
            picks2 = [rr.build_ai_pick(entry, roster_by_id) for entry in comp2["members"]]
            artifacts1 = rr.build_ai_artifacts(comp1, artifacts_by_id)
            artifacts2 = rr.build_ai_artifacts(comp2, artifacts_by_id)
            battle, info_by_unit = simulate_matchup(
                comp1,
                picks1,
                artifacts1,
                comp2,
                picks2,
                artifacts2,
                damage_tracker,
                swap_tracker,
                args.ai_profile,
            )

            total_battles += 1
            if total_battles % 50 == 0:
                print(f"Analyzed {total_battles} battles...")
            total_rounds += min(battle.round_num, rr.ROUND_LIMIT)
            total_swaps += swap_tracker.current_swaps

            winning_team_name = None
            if battle.winner == 1:
                winning_team_name = comp1["name"]
            elif battle.winner == 2:
                winning_team_name = comp2["name"]
            for player_num, comp in ((1, comp1), (2, comp2)):
                won = battle.winner == player_num
                update_rate(team_stats, comp["name"], won)
                update_rate(archetype_stats, ARCHETYPE_MAP.get(comp["name"], comp["name"]), won)
                team_members = battle.get_team(player_num).members
                for artifact_state in battle.get_team(player_num).artifacts:
                    update_rate(artifact_stats, artifact_state.artifact.name, won)
                    artifact_appearances[artifact_state.artifact.name] += 1
                for unit_a, unit_b in combinations(team_members, 2):
                    update_rate(pairing_stats, make_pair_key(unit_a.name, unit_b.name), won)

            for unit, info in info_by_unit.items():
                won = info["team"] == winning_team_name
                update_rate(class_stats, info["class"], won)
                update_rate(type_stats, info["type"], won)
                update_rate(adventurer_stats, info["adventurer"], won)
                update_rate(signature_stats, info["signature"], won)
                update_rate(twist_stats, info["twist"], won)
                update_rate(set_stats, info["set"], won)
                for basic in info["basics"]:
                    update_rate(basic_stats, basic, won)

                adventurer_appearances[info["adventurer"]] += 1
                class_appearances[info["class"]] += 1
                signature_appearances[info["signature"]] += 1
                for basic in info["basics"]:
                    basic_appearances[basic] += 1

                last_stand_stats[info["adventurer"]]["appearances"] += 1

            if battle.winner in (1, 2):
                winner_team = battle.get_team(battle.winner)
                alive_winners = [unit for unit in winner_team.members if not unit.ko]
                if len(alive_winners) == 1:
                    last_stand_stats[alive_winners[0].name]["last_stands"] += 1

            for unit, info in info_by_unit.items():
                adventurer_damage[info["adventurer"]]["matches"] += 1
                class_damage[info["class"]]["matches"] += 1
    finally:
        logic.do_swap = original_do_swap_logic
        rr.do_swap = original_do_swap_rr

    total_team_appearances = total_battles * 2
    total_adventurer_appearances = total_team_appearances * 3
    total_basic_appearances = total_adventurer_appearances * 2
    total_artifact_appearances = total_team_appearances * 3

    report = {
        "summary": {
            "battles_analyzed": total_battles,
            "average_battle_length_rounds": total_rounds / total_battles if total_battles else 0.0,
            "average_swaps_per_battle": total_swaps / total_battles if total_battles else 0.0,
        },
        "definitions": {
            "winrate_denominator": "appearance-based; mirror matches count as one win and one loss across the two sides",
            "last_standing_rate": "sole-survivor wins divided by total appearances of that adventurer",
            "average_dpm": "average attributed damage dealt per adventurer appearance across all analyzed matches; end-of-round burn is excluded because the engine does not retain DOT ownership",
            "appearance_rate_denominator": {
                "adventurer/signature/twist/class": total_adventurer_appearances,
                "artifact": total_artifact_appearances,
                "basic": total_basic_appearances,
            },
        },
        "archetype_winrate": finalize_rate_stats(archetype_stats),
        "team_winrate": finalize_rate_stats(team_stats),
        "class_winrate": finalize_rate_stats(class_stats),
        "type_winrate": finalize_rate_stats(type_stats),
        "adventurer_winrate": finalize_rate_stats(adventurer_stats),
        "two_adventurer_pairings_winrate": finalize_rate_stats(pairing_stats),
        "signature_ability_winrate": finalize_rate_stats(signature_stats),
        "basic_ability_winrate": finalize_rate_stats(basic_stats),
        "artifact_winrate": finalize_rate_stats(artifact_stats),
        "twist_ability_winrate": finalize_rate_stats(twist_stats),
        "set_winrate": finalize_rate_stats(set_stats),
        "last_standing_rate": finalize_last_stand_stats(last_stand_stats),
        "average_dpm_by_adventurer": [],
        "average_dpm_by_class": [],
        "artifact_appearance_rate": finalize_appearance_stats(artifact_appearances, total_artifact_appearances),
        "basic_appearance_rate": finalize_appearance_stats(basic_appearances, total_basic_appearances),
        "signature_appearance_rate": finalize_appearance_stats(signature_appearances, total_adventurer_appearances),
        "adventurer_appearance_rate": finalize_appearance_stats(adventurer_appearances, total_adventurer_appearances),
        "class_appearance_rate": finalize_appearance_stats(class_appearances, total_adventurer_appearances),
    }

    JSON_OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(render_markdown(report), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT}")
    print(f"Wrote {MARKDOWN_OUTPUT}")


def render_table(rows, columns):
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        formatted = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                formatted.append(f"{value:.4f}")
            else:
                formatted.append(str(value))
        lines.append("| " + " | ".join(formatted) + " |")
    return "\n".join(lines)


def render_markdown(report):
    sections = [
        "# Round Robin Analysis",
        "",
        f"- Battles analyzed: {report['summary']['battles_analyzed']}",
        f"- Average battle length (rounds): {report['summary']['average_battle_length_rounds']:.4f}",
        f"- Average swaps per battle: {report['summary']['average_swaps_per_battle']:.4f}",
        "",
        "## Archetype Winrate",
        render_table(report["archetype_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Team Winrate",
        render_table(report["team_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Class Winrate",
        render_table(report["class_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Type Winrate",
        render_table(report["type_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Adventurer Winrate",
        render_table(report["adventurer_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Two Adventurer Pairings Winrate",
        render_table(report["two_adventurer_pairings_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Signature Ability Winrate",
        render_table(report["signature_ability_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Basic Ability Winrate",
        render_table(report["basic_ability_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Artifact Winrate",
        render_table(report["artifact_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Twist Ability Winrate",
        render_table(report["twist_ability_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Set Winrate",
        render_table(report["set_winrate"], ["name", "appearances", "wins", "losses", "winrate"]),
        "",
        "## Last Standing Rate",
        render_table(report["last_standing_rate"], ["name", "appearances", "last_stands", "last_standing_rate"]),
        "",
        "## Average DPM by Adventurer",
        render_table(report["average_dpm_by_adventurer"], ["name", "matches", "total_damage", "average_dpm"]),
        "",
        "## Average DPM by Class",
        render_table(report["average_dpm_by_class"], ["name", "matches", "total_damage", "average_dpm"]),
        "",
        "## Artifact Appearance Rate",
        render_table(report["artifact_appearance_rate"], ["name", "appearances", "appearance_rate"]),
        "",
        "## Basic Appearance Rate",
        render_table(report["basic_appearance_rate"], ["name", "appearances", "appearance_rate"]),
        "",
        "## Signature Appearance Rate",
        render_table(report["signature_appearance_rate"], ["name", "appearances", "appearance_rate"]),
        "",
        "## Adventurer Appearance Rate",
        render_table(report["adventurer_appearance_rate"], ["name", "appearances", "appearance_rate"]),
        "",
        "## Class Appearance Rate",
        render_table(report["class_appearance_rate"], ["name", "appearances", "appearance_rate"]),
        "",
    ]
    return "\n".join(sections)


if __name__ == "__main__":
    main()
