import argparse
import random
from pathlib import Path

import battle_log
from simulate_meta_battles import build_ai_pick, load_meta_team_pool, simulate_battle
from data import ITEMS, ROSTER


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PREFIX = "archetype_battles"
DEFAULT_SEED = 20260314
MAX_BATTLES_PER_FILE = 50

ARCHETYPES = {
    "Anti-heal / sustain-break": [
        "Anti-Heal Pressure",
        "No-Heal Collapse",
        "Burnline Pressure",
        "Rapunzel Pin Control",
    ],
    "Expose / pick": [
        "Expose Hunter",
        "Ranger-Rogue Kill Chain",
        "Gretel Tempo Kill",
        "Backline Hunter",
        "Rapunzel Collapse",
    ],
    "Stable midrange": [
        "Balanced Generalist",
        "Safe Midrange",
        "Prince-Robin Midrange",
        "Roland-Aurora Midrange",
        "Noble Midrange",
        "Green Knight Root Midrange",
    ],
    "Punish / counterattack": [
        "Reflection Punish",
        "Lady Control Shell",
        "Roland Counterbattery",
        "Brawler Punish",
        "Double Rogue Tempo",
    ],
    "Tank / fortress": [
        "Tank Sustain",
        "Porcus Fortress",
        "Sustain Into Spike",
        "Safe Mage Shell",
        "Pinocchio Malice Fortress",
    ],
    "Root / trap": [
        "Root Killbox",
        "Rooted Marks",
        "Royal Root Pressure",
        "Witch Hunter Net",
    ],
    "Multi-status control": [
        "Status Spread",
        "Burn Shock Split",
        "Shock Punish",
        "Shocked Quarry",
        "Burn-Root Hunter",
        "Sea Wench Theft Shell",
    ],
    "Tempo / speed aggro": [
        "Speed Tempo",
        "Tempo Dive",
        "Fast Frontline Collapse",
        "Frontline Breaker",
    ],
    "Last-stand brawler": [
        "Last-Stand Brawler",
        "Last-Stand Aggro",
        "Last-Stand Midrange",
        "Execute Line",
    ],
    "Malice / scaling utility": [
        "Malice Growth",
        "Pinocchio Spotlight Break",
        "Rumpel Buff Engine",
        "Sea Wench Debuff Burst",
        "Crowstorm Burn",
        "Ella Pivot Shell",
    ],
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulate each meta team against one random eligible team from each broad archetype."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random seed for opponent selection.")
    parser.add_argument(
        "--prefix",
        type=str,
        default=DEFAULT_OUTPUT_PREFIX,
        help="Prefix for generated txt files.",
    )
    return parser.parse_args()


def team_member_ids(comp):
    return {entry["defn"] for entry in comp["members"]}


def shared_adventurer_count(comp_a, comp_b):
    return len(team_member_ids(comp_a) & team_member_ids(comp_b))


def resolve_archetypes(pool):
    by_name = {comp["name"]: comp for comp in pool}
    resolved = {}
    missing = {}
    for archetype, names in ARCHETYPES.items():
        found = [by_name[name] for name in names if name in by_name]
        not_found = [name for name in names if name not in by_name]
        resolved[archetype] = found
        if not_found:
            missing[archetype] = not_found
    return resolved, missing


def build_matchups(pool, resolved_archetypes, rng):
    matchups = []
    skipped = []
    for comp in pool:
        for archetype, candidates in resolved_archetypes.items():
            eligible = [
                opponent
                for opponent in candidates
                if opponent["name"] != comp["name"] and shared_adventurer_count(comp, opponent) <= 1
            ]
            if not eligible:
                skipped.append((comp["name"], archetype))
                continue
            opponent = rng.choice(eligible)
            matchups.append((comp, archetype, opponent))
    return matchups, skipped


def chunked(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def write_chunk(path, seed, chunk_num, total_chunks, chunk_matchups, missing, skipped):
    roster_by_id = {defn.id: defn for defn in ROSTER}
    items_by_id = {item.id: item for item in ITEMS}
    combined = [
        "Fabled archetype simulation batch",
        f"Seed: {seed}",
        f"Chunk: {chunk_num}/{total_chunks}",
        f"Battles in file: {len(chunk_matchups)}",
        "",
    ]

    if missing:
        combined.append("Archetype labels not present in the current 40-team pool:")
        for archetype, names in missing.items():
            combined.append(f"- {archetype}: {', '.join(names)}")
        combined.append("")

    if skipped:
        combined.append("Source/archetype pairs skipped because no opponent shared <= 1 adventurer:")
        for team_name, archetype in skipped:
            combined.append(f"- {team_name} vs {archetype}")
        combined.append("")

    for battle_num, (comp1, archetype, comp2) in chunk_matchups:
        picks1 = [build_ai_pick(entry, roster_by_id, items_by_id) for entry in comp1["members"]]
        picks2 = [build_ai_pick(entry, roster_by_id, items_by_id) for entry in comp2["members"]]
        winner = simulate_battle(battle_num, comp1["name"], picks1, comp2["name"], picks2)
        log_text = Path(battle_log._log_path()).read_text(encoding="utf-8", errors="replace")
        combined.append(f"========== BATTLE {battle_num} ==========")
        combined.append(f"Player 1: {comp1['name']}")
        combined.append(f"Player 2: {comp2['name']}")
        combined.append(f"Target Archetype: {archetype}")
        combined.append(f"Shared Adventurers: {shared_adventurer_count(comp1, comp2)}")
        combined.append(f"Winner: P{winner}" if winner else "Winner: unresolved")
        combined.append("")
        combined.append(log_text.rstrip())
        combined.append("")

    path.write_text("\n".join(combined) + "\n", encoding="utf-8")


def main():
    args = parse_args()
    rng = random.Random(args.seed)
    pool = load_meta_team_pool()
    resolved, missing = resolve_archetypes(pool)
    matchups, skipped = build_matchups(pool, resolved, rng)

    numbered_matchups = list(enumerate(matchups, start=1))
    chunks = list(chunked(numbered_matchups, MAX_BATTLES_PER_FILE))
    if not chunks:
        raise RuntimeError("No valid archetype battles could be scheduled.")

    skipped_set = set(skipped)
    for index, chunk in enumerate(chunks, start=1):
        out_path = ROOT / f"{args.prefix}_{index:02d}.txt"
        write_chunk(out_path, args.seed, index, len(chunks), chunk, missing, sorted(skipped_set))
        print(f"Wrote {len(chunk)} battles to {out_path}")

    print(f"Total battles: {len(matchups)}")
    print(f"Skipped pairs: {len(skipped_set)}")


if __name__ == "__main__":
    main()
