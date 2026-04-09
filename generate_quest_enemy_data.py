from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import pprint
import re


ROOT = Path(__file__).resolve().parent
CSV_GLOB = "Quest Enemies*.csv"
OUTPUT = ROOT / "quest_enemy_generated.py"
RULEBOOK = ROOT / "rulebook.txt"


LOCALE_NAME_TO_ID = {
    "The Forest of Dreams": "forest_of_dreams",
    "The Cloud Peaks": "cloud_peaks",
    "The Blackwells": "blackwells",
    "The Static Plains": "static_plains",
    "The Scar": "the_scar",
    "The High Court": "high_court",
}

TIER_NAME_TO_ID = {
    "T1": "tier_1",
    "T2": "tier_2",
    "T3": "tier_3",
    "T4": "tier_4",
    "T5": "tier_5",
    "Apex": "apex",
}


def _slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", text.strip().lower())
    return value.strip("_")


def _clean_cell(value: str) -> str:
    text = str(value or "").strip()
    return text.replace("\ufeff", "").replace("\u2014", "-").replace("\u2013", "-").replace("\xa0", " ")


def _strip_bonus_suffix(name: str) -> str:
    return re.sub(r"\s*\(\+\d+\s+[A-Z]+\)\s*$", "", _clean_cell(name))


def _artifact_bonus(raw_name: str) -> tuple[int, str]:
    match = re.search(r"\(\+(\d+)\s+([A-Z]+)\)\s*$", _clean_cell(raw_name))
    if match is None:
        return 0, "Attack"
    amount = int(match.group(1))
    stat_map = {
        "ATK": "Attack",
        "DEF": "Defense",
        "SPE": "Speed",
        "SPD": "Speed",
        "HP": "HP",
    }
    return amount, stat_map.get(match.group(2).upper(), match.group(2).title())


def _parse_effect_header(text: str, *, default_kind: str = "spell") -> dict | None:
    raw = _clean_cell(text)
    if not raw:
        return None
    match = re.match(r"^(.*?)\s*\((.*?)\)\s*:\s*(.+)$", raw, flags=re.IGNORECASE)
    if match is None:
        plain_name, separator, description = raw.partition(":")
        if not separator:
            return None
        return {
            "name": plain_name.strip(),
            "kind": default_kind,
            "cooldown": 0,
            "description": description.strip(),
        }
    kind = default_kind
    cooldown = 0
    for token in [part.strip() for part in match.group(2).split(",") if part.strip()]:
        lowered = token.lower()
        if lowered in {"spell", "skill"}:
            kind = lowered
            continue
        cd_match = re.match(r"cd\s*(\d+)", lowered)
        if cd_match is not None:
            cooldown = int(cd_match.group(1))
    return {
        "name": match.group(1).strip(),
        "kind": kind,
        "cooldown": cooldown,
        "description": match.group(3).strip(),
    }


def _weapon_record(prefix: str, row: dict[str, str]) -> dict | None:
    name = _clean_cell(row.get(f"{prefix} Weapon", ""))
    if not name:
        return None
    return {
        "name": name,
        "type": _clean_cell(row.get(f"{prefix} Weapon Type", "")),
        "ammo_cd": _clean_cell(row.get(f"{prefix} Weapon Ammo/CD", "")),
        "strike": _clean_cell(row.get(f"{prefix} Weapon Strike", "")),
        "spell_or_skill": _clean_cell(row.get(f"{prefix} Weapon Spell/Skill", "")),
    }


def _artifact_record(row: dict[str, str]) -> dict | None:
    name = _clean_cell(row.get("Artifact", ""))
    if not name:
        return None
    return {
        "name": name,
        "spell": _clean_cell(row.get("Artifact Spell", "")),
        "reactive": _clean_cell(row.get("Artifact Reactive", "")),
    }


def _class_record(raw_text: str) -> dict | None:
    text = _clean_cell(raw_text)
    if not text:
        return None
    class_part, _, detail = text.partition(":")
    class_name = class_part.split("/", 1)[0].strip()
    skill_part = class_part.split("/", 1)[1].strip() if "/" in class_part else ""
    return {
        "class_name": class_name,
        "skill_text": skill_part,
        "description": detail.strip(),
        "raw": text,
    }


def _find_csv() -> Path:
    candidates = sorted(ROOT.glob(CSV_GLOB))
    if not candidates:
        raise FileNotFoundError(f"No quest enemy CSV matching {CSV_GLOB!r} was found in {ROOT}")
    return candidates[0]


def _appendix_d_lines(records: list[dict]) -> list[str]:
    artifact_entries: dict[str, dict] = {}
    artifact_order: list[str] = []
    for record in records:
        raw_artifact = record.get("artifact")
        if not raw_artifact:
            continue
        artifact_name = _strip_bonus_suffix(raw_artifact["name"])
        entry = artifact_entries.get(artifact_name)
        if entry is None:
            amount, stat_name = _artifact_bonus(raw_artifact["name"])
            entry = {
                "name": artifact_name,
                "attunement": [],
                "attunement_seen": set(),
                "amount": amount,
                "stat_name": stat_name,
                "spell": _parse_effect_header(raw_artifact.get("spell", "")),
                "reactive": _parse_effect_header(raw_artifact.get("reactive", "")),
            }
            artifact_entries[artifact_name] = entry
            artifact_order.append(artifact_name)
        class_info = record.get("class_info")
        class_name = _clean_cell(class_info.get("class_name", "")) if class_info else ""
        if class_name and class_name not in entry["attunement_seen"]:
            entry["attunement"].append(class_name)
            entry["attunement_seen"].add(class_name)

    lines = ["APPENDIX D - ENEMY ARTIFACTS", ""]
    for artifact_name in artifact_order:
        entry = artifact_entries[artifact_name]
        lines.append(entry["name"])
        if entry["attunement"]:
            lines.append(f"Attunement: {', '.join(entry['attunement'])}")
        else:
            lines.append("Attunement: Enemy-only")
        lines.append(f"+{entry['amount']} {entry['stat_name']}")
        spell = entry.get("spell")
        if spell is not None:
            lines.append(f"Spell: {spell['name']}")
            if spell["cooldown"] > 0:
                round_label = "round" if spell["cooldown"] == 1 else "rounds"
                lines.append(f"Cooldown: {spell['cooldown']} {round_label}")
            lines.append(spell["description"])
        reactive = entry.get("reactive")
        if reactive is not None:
            lines.append(f"Reactive Spell: {reactive['name']}")
            if reactive["cooldown"] > 0:
                round_label = "round" if reactive["cooldown"] == 1 else "rounds"
                lines.append(f"Cooldown: {reactive['cooldown']} {round_label}")
            lines.append(f"Reaction: {reactive['description']}")
        lines.append("")
    return lines


def _update_rulebook_appendix_d(records: list[dict]):
    text = RULEBOOK.read_text(encoding="utf-8")
    appendix_d_text = "\n".join(_appendix_d_lines(records)).rstrip() + "\n"
    updated = re.sub(
        r"APPENDIX D\s*[—-]\s*ENEMY ARTIFACTS.*\Z",
        appendix_d_text,
        text,
        count=1,
        flags=re.DOTALL,
    )
    if updated == text and "APPENDIX D" not in text:
        updated = text.rstrip() + "\n\n" + appendix_d_text
    RULEBOOK.write_text(updated, encoding="utf-8")


def generate() -> Path:
    csv_path = _find_csv()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    records: list[dict] = []
    used_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        name = _clean_cell(row["Enemy Name"])
        enemy_id = _slugify(name)
        if enemy_id in used_ids:
            enemy_id = f"{enemy_id}_{index}"
        used_ids.add(enemy_id)
        locale_name = _clean_cell(row["Locale"])
        tier_name = _clean_cell(row["Tier"])
        record = {
            "id": enemy_id,
            "name": name,
            "locale_name": locale_name,
            "locale_id": LOCALE_NAME_TO_ID[locale_name],
            "tier_name": tier_name,
            "tier_id": TIER_NAME_TO_ID[tier_name],
            "humanoid": _clean_cell(row["Humanoid"]).lower() == "yes",
            "hp": int(_clean_cell(row["HP"])),
            "attack": int(_clean_cell(row["ATK"])),
            "defense": int(_clean_cell(row["DEF"])),
            "speed": int(_clean_cell(row["SPE"])),
            "innate_text": _clean_cell(row.get("Innate Skill", "")),
            "class_info": _class_record(row.get("Class/Skill", "")),
            "primary_weapon": _weapon_record("Primary", row),
            "secondary_weapon": _weapon_record("Secondary", row),
            "artifact": _artifact_record(row),
        }
        records.append(record)

    payload = pprint.pformat(records, width=120, sort_dicts=False)
    OUTPUT.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "# This file is auto-generated by generate_quest_enemy_data.py.",
                "# Source CSV is not used at runtime.",
                f"CSV_SOURCE = {csv_path.name!r}",
                f"GENERATED_AT = {datetime.now().isoformat(timespec='seconds')!r}",
                "",
                f"QUEST_ENEMY_RAW_RECORDS = {payload}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _update_rulebook_appendix_d(records)
    return OUTPUT


if __name__ == "__main__":
    output = generate()
    print(output)
