from __future__ import annotations

from collections import Counter
from pathlib import Path
import argparse
import re


SUMMARY_PATTERNS = {
    "quest_runs": re.compile(r"^Quest runs simulated: (\d+)$"),
    "encounters": re.compile(r"^Encounters simulated: (\d+)$"),
    "tiebreaks": re.compile(r"^Tiebreaked encounters: (\d+)$"),
    "avg_encounter_length": re.compile(r"^Average encounter length: ([\d.]+) rounds$"),
    "avg_strikes": re.compile(r"^Average strikes per encounter: ([\d.]+)$"),
    "avg_spells": re.compile(r"^Average spells cast per encounter: ([\d.]+)$"),
    "avg_switches": re.compile(r"^Average weapon switches per encounter: ([\d.]+)$"),
    "avg_swaps": re.compile(r"^Average position swaps per encounter: ([\d.]+)$"),
    "avg_skips": re.compile(r"^Average skips per encounter: ([\d.]+)$"),
    "avg_bonus_used": re.compile(r"^Average bonus actions used per encounter: ([\d.]+)$"),
    "avg_bonus_passes": re.compile(r"^Average bonus passes per encounter: ([\d.]+)$"),
    "avg_ultimates": re.compile(r"^Average ultimate spells cast per encounter: ([\d.]+)$"),
    "avg_quest_length": re.compile(r"^Average quest run length: ([\d.]+) encounters$"),
    "best_party": re.compile(r"^Best performing party observed: (.+)$"),
    "best_favorite": re.compile(r"^  Favorite: (.+)$"),
    "best_record": re.compile(r"^  Record: (\d+)W-(\d+)L$"),
    "best_encounters": re.compile(r"^  Encounters: (\d+)$"),
    "best_final_glory": re.compile(r"^  Final Glory: (\d+)$"),
    "best_total_gold": re.compile(r"^  Total Gold: (\d+)$"),
}

WINRATE_SECTIONS = {
    "Adventurer Winrate",
    "Class Winrate",
    "Class Skill Winrate",
    "Artifact Winrate",
    "Loadout Winrate",
    "Ultimate Spell Winrate",
    "First Death Rate Per Adventurer",
    "Last Death Rate Per Adventurer",
    "Left Behind Rate Per Adventurer",
}

AVERAGE_SECTIONS = {
    "Average Damage Per Battle By Adventurer",
    "Average Damage Taken Per Battle By Adventurer",
}

WINRATE_LINE = re.compile(r"^- (.*): (\d+)/(\d+) \(([\d.]+)%\)$")
AVERAGE_LINE = re.compile(r"^- (.*): ([\d.]+) across (\d+) appearances$")


def parse_global_stats(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    data = {
        "path": str(path),
        "summary": {},
        "sections": {},
    }

    i = 0
    while i < len(lines):
        line = lines[i]
        matched = False
        for key, pattern in SUMMARY_PATTERNS.items():
            m = pattern.match(line)
            if m:
                data["summary"][key] = m.groups()
                matched = True
                break
        if matched:
            i += 1
            continue

        if line in WINRATE_SECTIONS:
            section = {}
            i += 1
            while i < len(lines) and lines[i].startswith("- "):
                m = WINRATE_LINE.match(lines[i])
                if not m:
                    raise ValueError(f"Could not parse winrate line in {path}: {lines[i]!r}")
                label, wins, appearances, _pct = m.groups()
                section[label] = (int(wins), int(appearances))
                i += 1
            data["sections"][line] = section
            continue

        if line in AVERAGE_SECTIONS:
            section = {}
            i += 1
            while i < len(lines) and lines[i].startswith("- "):
                m = AVERAGE_LINE.match(lines[i])
                if not m:
                    raise ValueError(f"Could not parse average line in {path}: {lines[i]!r}")
                label, average, appearances = m.groups()
                section[label] = (float(average), int(appearances))
                i += 1
            data["sections"][line] = section
            continue

        i += 1

    return data


def _summary_int(summary: dict, key: str) -> int:
    return int(summary[key][0])


def _summary_float(summary: dict, key: str) -> float:
    return float(summary[key][0])


def merge_batches(parsed_batches: list[dict]) -> dict:
    merged = {
        "sources": [batch["path"] for batch in parsed_batches],
        "quest_runs": sum(_summary_int(batch["summary"], "quest_runs") for batch in parsed_batches),
        "encounters": sum(_summary_int(batch["summary"], "encounters") for batch in parsed_batches),
        "tiebreaks": sum(_summary_int(batch["summary"], "tiebreaks") for batch in parsed_batches),
    }

    total_encounters = merged["encounters"]
    total_runs = merged["quest_runs"]

    def weighted_average(key: str, *, weight_key: str) -> float:
        total_weight = sum(_summary_int(batch["summary"], weight_key) for batch in parsed_batches)
        if total_weight <= 0:
            return 0.0
        return sum(
            _summary_float(batch["summary"], key) * _summary_int(batch["summary"], weight_key)
            for batch in parsed_batches
        ) / total_weight

    merged["avg_encounter_length"] = weighted_average("avg_encounter_length", weight_key="encounters")
    merged["avg_strikes"] = weighted_average("avg_strikes", weight_key="encounters")
    merged["avg_spells"] = weighted_average("avg_spells", weight_key="encounters")
    merged["avg_switches"] = weighted_average("avg_switches", weight_key="encounters")
    merged["avg_swaps"] = weighted_average("avg_swaps", weight_key="encounters")
    merged["avg_skips"] = weighted_average("avg_skips", weight_key="encounters")
    merged["avg_bonus_used"] = weighted_average("avg_bonus_used", weight_key="encounters")
    merged["avg_bonus_passes"] = weighted_average("avg_bonus_passes", weight_key="encounters")
    merged["avg_ultimates"] = weighted_average("avg_ultimates", weight_key="encounters")
    merged["avg_quest_length"] = weighted_average("avg_quest_length", weight_key="quest_runs")

    best_candidates = []
    for batch in parsed_batches:
        summary = batch["summary"]
        best_candidates.append(
            {
                "party_line": summary["best_party"][0],
                "favorite": summary["best_favorite"][0],
                "wins": int(summary["best_record"][0]),
                "losses": int(summary["best_record"][1]),
                "encounters": int(summary["best_encounters"][0]),
                "final_glory": int(summary["best_final_glory"][0]),
                "total_gold": int(summary["best_total_gold"][0]),
                "source": batch["path"],
            }
        )
    merged["best_party"] = max(
        best_candidates,
        key=lambda item: (item["wins"], -item["losses"], item["final_glory"], item["total_gold"]),
    )

    merged["winrate_sections"] = {}
    for section_name in WINRATE_SECTIONS:
        wins = Counter()
        appearances = Counter()
        for batch in parsed_batches:
            for label, (value_wins, value_appearances) in batch["sections"].get(section_name, {}).items():
                wins[label] += value_wins
                appearances[label] += value_appearances
        merged["winrate_sections"][section_name] = {"wins": wins, "appearances": appearances}

    merged["average_sections"] = {}
    for section_name in AVERAGE_SECTIONS:
        totals = Counter()
        appearances = Counter()
        for batch in parsed_batches:
            for label, (average, value_appearances) in batch["sections"].get(section_name, {}).items():
                totals[label] += average * value_appearances
                appearances[label] += value_appearances
        merged["average_sections"][section_name] = {"totals": totals, "appearances": appearances}

    return merged


def format_winrate_section(title: str, wins: Counter, appearances: Counter) -> list[str]:
    lines = [title]
    ranked = sorted(
        appearances.items(),
        key=lambda item: (
            -(wins[item[0]] / item[1] if item[1] else 0.0),
            -item[1],
            item[0],
        ),
    )
    for label, count in ranked:
        pct = (wins[label] / count) * 100 if count else 0.0
        lines.append(f"- {label}: {wins[label]}/{count} ({pct:.2f}%)")
    return lines


def format_average_section(title: str, totals: Counter, appearances: Counter) -> list[str]:
    lines = [title]
    ranked = sorted(
        appearances.items(),
        key=lambda item: (
            -(totals[item[0]] / item[1] if item[1] else 0.0),
            -item[1],
            item[0],
        ),
    )
    for label, count in ranked:
        average = totals[label] / count if count else 0.0
        lines.append(f"- {label}: {average:.2f} across {count} appearances")
    return lines


def write_merged_file(output_path: Path, merged: dict) -> None:
    best = merged["best_party"]
    lines = [
        "Merged Global Favorite Quest Simulation Statistics",
        "Source batches:",
        *[f"- {source}" for source in merged["sources"]],
        "",
        f"Quest runs simulated: {merged['quest_runs']}",
        f"Encounters simulated: {merged['encounters']}",
        f"Tiebreaked encounters: {merged['tiebreaks']}",
        f"Average encounter length: {merged['avg_encounter_length']:.2f} rounds",
        f"Average strikes per encounter: {merged['avg_strikes']:.2f}",
        f"Average spells cast per encounter: {merged['avg_spells']:.2f}",
        f"Average weapon switches per encounter: {merged['avg_switches']:.2f}",
        f"Average position swaps per encounter: {merged['avg_swaps']:.2f}",
        f"Average skips per encounter: {merged['avg_skips']:.2f}",
        f"Average bonus actions used per encounter: {merged['avg_bonus_used']:.2f}",
        f"Average bonus passes per encounter: {merged['avg_bonus_passes']:.2f}",
        f"Average ultimate spells cast per encounter: {merged['avg_ultimates']:.2f}",
        f"Average quest run length: {merged['avg_quest_length']:.2f} encounters",
        "",
        f"Best performing party observed: {best['party_line']}",
        f"  Favorite: {best['favorite']}",
        f"  Record: {best['wins']}W-{best['losses']}L",
        f"  Encounters: {best['encounters']}",
        f"  Final Glory: {best['final_glory']}",
        f"  Total Gold: {best['total_gold']}",
        f"  Source batch: {best['source']}",
        "",
    ]

    ordered_sections = [
        "Adventurer Winrate",
        "Class Winrate",
        "Class Skill Winrate",
        "Artifact Winrate",
        "Loadout Winrate",
        "Ultimate Spell Winrate",
    ]
    for section_name in ordered_sections:
        section = merged["winrate_sections"][section_name]
        lines.extend(format_winrate_section(section_name, section["wins"], section["appearances"]))
        lines.append("")

    average_sections = [
        "Average Damage Per Battle By Adventurer",
        "Average Damage Taken Per Battle By Adventurer",
    ]
    for section_name in average_sections:
        section = merged["average_sections"][section_name]
        lines.extend(format_average_section(section_name, section["totals"], section["appearances"]))
        lines.append("")

    tail_sections = [
        "First Death Rate Per Adventurer",
        "Last Death Rate Per Adventurer",
        "Left Behind Rate Per Adventurer",
    ]
    for index, section_name in enumerate(tail_sections):
        section = merged["winrate_sections"][section_name]
        lines.extend(format_winrate_section(section_name, section["wins"], section["appearances"]))
        if index != len(tail_sections) - 1:
            lines.append("")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge saved simulation global statistics files.")
    parser.add_argument("inputs", nargs="+", help="Paths to existing global_statistics.txt files.")
    parser.add_argument("--output", required=True, help="Path for the merged statistics text file.")
    args = parser.parse_args()

    parsed = [parse_global_stats(Path(path)) for path in args.inputs]
    merged = merge_batches(parsed)
    write_merged_file(Path(args.output), merged)
    print(f"Merged statistics written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
