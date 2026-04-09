from __future__ import annotations

import random
import re
from typing import Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ruleset_data import ADVENTURERS, ADVENTURERS_BY_ID, ARTIFACTS, ARTIFACTS_BY_ID, CLASS_SKILLS
from quests_ruleset_logic import create_battle, create_team, determine_initiative_order, make_pick


SLOT_ORDER = (SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT)
NO_CLASS_NAME = "None"
CLASS_ORDER = (NO_CLASS_NAME,) + tuple(CLASS_SKILLS.keys())
ALL_ARTIFACT_IDS = {artifact.id for artifact in ARTIFACTS}


def _normalize_lookup_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text).strip().lower())


_ADVENTURER_NAME_TO_ID = {_normalize_lookup_key(adventurer.name): adventurer.id for adventurer in ADVENTURERS}
_CLASS_NAME_MAP = {_normalize_lookup_key(class_name): class_name for class_name in CLASS_ORDER}
_ARTIFACT_NAME_TO_ID = {_normalize_lookup_key(artifact.name): artifact.id for artifact in ARTIFACTS}


def _weapon_lookup_for_adventurer(adventurer_id: str) -> dict[str, str]:
    adventurer = ADVENTURERS_BY_ID.get(adventurer_id)
    if adventurer is None:
        return {}
    lookup: dict[str, str] = {}
    for weapon in adventurer.signature_weapons:
        lookup[_normalize_lookup_key(weapon.name)] = weapon.id
        lookup[_normalize_lookup_key(weapon.id)] = weapon.id
    return lookup


def import_team_from_text(text: str, *, expected_members: int = 6) -> tuple[list[dict], list[str]]:
    lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    parsed_members: list[dict] = []
    current: dict | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        header_match = re.match(r"^(.*?)\s*@\s*(.+)$", line)
        if header_match:
            if current is not None:
                parsed_members.append(current)
            current = {
                "adventurer_name": header_match.group(1).strip(),
                "weapon_name": header_match.group(2).strip(),
                "class_name_raw": "",
                "class_skill_raw": "",
                "artifact_name_raw": "",
            }
            continue
        if current is None:
            # Team names and free text before the first member block are ignored.
            continue
        class_match = re.match(r"^class\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if class_match:
            current["class_name_raw"] = class_match.group(1).strip()
            continue
        artifact_match = re.match(r"^artifact\s*:\s*(.+)$", line, flags=re.IGNORECASE)
        if artifact_match:
            current["artifact_name_raw"] = artifact_match.group(1).strip()
            continue
        skill_match = re.match(r"^(?:[-*]\s*|class\s*skill\s*:\s*)(.+)$", line, flags=re.IGNORECASE)
        if skill_match:
            current["class_skill_raw"] = skill_match.group(1).strip()
            continue
        if not current["class_skill_raw"] and ":" not in line:
            # Allow plain skill lines without a leading bullet.
            current["class_skill_raw"] = line
            continue
    if current is not None:
        parsed_members.append(current)

    if not parsed_members:
        return [], ["No team members were found. Use lines like 'Name @ Weapon' followed by Class/Skill/Artifact lines."]
    if len(parsed_members) != expected_members:
        return [], [f"Team import requires exactly {expected_members} members; found {len(parsed_members)}."]

    resolved_members: list[dict] = []
    errors: list[str] = []
    used_adventurers: set[str] = set()
    used_classes: set[str] = set()
    used_artifacts: set[str] = set()

    for member in parsed_members:
        adventurer_key = _normalize_lookup_key(member["adventurer_name"])
        adventurer_id = _ADVENTURER_NAME_TO_ID.get(adventurer_key)
        if adventurer_id is None:
            errors.append(f"Unknown adventurer: {member['adventurer_name']}.")
            continue
        if adventurer_id in used_adventurers:
            errors.append(f"Duplicate adventurer: {member['adventurer_name']}.")
            continue
        used_adventurers.add(adventurer_id)

        weapon_lookup = _weapon_lookup_for_adventurer(adventurer_id)
        weapon_id = weapon_lookup.get(_normalize_lookup_key(member["weapon_name"]))
        if weapon_id is None:
            errors.append(f"Invalid weapon '{member['weapon_name']}' for {member['adventurer_name']}.")
            continue

        class_name = _CLASS_NAME_MAP.get(_normalize_lookup_key(member["class_name_raw"]))
        if class_name is None:
            errors.append(f"Invalid class for {member['adventurer_name']}: {member['class_name_raw'] or '(missing)'}")
            continue
        if class_name != NO_CLASS_NAME and class_name in used_classes:
            errors.append(f"Duplicate class '{class_name}' is not allowed in one party.")
            continue
        if class_name != NO_CLASS_NAME:
            used_classes.add(class_name)

        class_skill_id = None
        if class_name != NO_CLASS_NAME:
            skill_lookup: dict[str, str] = {}
            for skill in CLASS_SKILLS[class_name]:
                skill_lookup[_normalize_lookup_key(skill.name)] = skill.id
                skill_lookup[_normalize_lookup_key(skill.id)] = skill.id
            class_skill_id = skill_lookup.get(_normalize_lookup_key(member["class_skill_raw"]))
            if class_skill_id is None:
                errors.append(
                    f"Invalid class skill for {member['adventurer_name']} ({class_name}): {member['class_skill_raw'] or '(missing)'}"
                )
                continue

        artifact_id = _ARTIFACT_NAME_TO_ID.get(_normalize_lookup_key(member["artifact_name_raw"]))
        if artifact_id is None:
            errors.append(f"Invalid artifact for {member['adventurer_name']}: {member['artifact_name_raw'] or '(missing)'}")
            continue
        if artifact_id in used_artifacts:
            errors.append(f"Duplicate artifact is not allowed: {member['artifact_name_raw']}.")
            continue
        artifact_def = ARTIFACTS_BY_ID.get(artifact_id)
        if artifact_def is None:
            errors.append(f"Invalid artifact for {member['adventurer_name']}: {member['artifact_name_raw'] or '(missing)'}")
            continue
        used_artifacts.add(artifact_id)

        resolved_members.append(
            {
                "adventurer_id": adventurer_id,
                "class_name": class_name,
                "class_skill_id": class_skill_id,
                "primary_weapon_id": weapon_id,
                "artifact_id": artifact_id,
            }
        )

    if errors:
        return [], errors
    if len(resolved_members) != expected_members:
        return [], [f"Team import requires exactly {expected_members} legal members."]
    return resolved_members, []


def _team_key(team_num: int) -> str:
    return f"team{team_num}"


def _default_class_for_slot(slot: str) -> str:
    if slot == SLOT_FRONT:
        return "Fighter"
    if slot == SLOT_BACK_LEFT:
        return "Ranger"
    return "Cleric"


def _allowed_artifact_ids_for_team(setup_state: dict, team_num: int) -> set[str] | None:
    raw_ids = setup_state.get(f"{_team_key(team_num)}_allowed_artifact_ids")
    if raw_ids is None:
        return None
    return {artifact_id for artifact_id in raw_ids if artifact_id in ALL_ARTIFACT_IDS}


def _team_enforces_unique_classes(setup_state: dict, team_num: int) -> bool:
    return bool(setup_state.get(f"{_team_key(team_num)}_enforce_unique_classes", True))


def available_artifact_ids(allowed_artifact_ids: set[str] | None = None) -> list[str]:
    return [
        artifact.id
        for artifact in ARTIFACTS
        if allowed_artifact_ids is None or artifact.id in allowed_artifact_ids
    ]


def compatible_artifact_ids(class_name: str, allowed_artifact_ids: set[str] | None = None) -> list[str]:
    if class_name == NO_CLASS_NAME:
        return []
    return [
        artifact.id
        for artifact in ARTIFACTS
        if class_name in artifact.attunement and (allowed_artifact_ids is None or artifact.id in allowed_artifact_ids)
    ]


def _normalize_team_artifacts(team: list[dict], allowed_artifact_ids: set[str] | None = None):
    used: set[str] = set()
    valid_ids = set(available_artifact_ids(allowed_artifact_ids))
    for member in team:
        if member.get("artifact_id") is None:
            continue
        if member["artifact_id"] not in valid_ids or member["artifact_id"] in used:
            member["artifact_id"] = None
            continue
        used.add(member["artifact_id"])


def _build_member(adventurer_id: str, slot: str, allowed_artifact_ids: set[str] | None = None) -> dict:
    class_name = _default_class_for_slot(slot)
    artifacts = compatible_artifact_ids(class_name, allowed_artifact_ids)
    return {
        "adventurer_id": adventurer_id,
        "slot": slot,
        "class_name": class_name,
        "class_skill_id": CLASS_SKILLS[class_name][0].id,
        "primary_weapon_id": None,
        "artifact_id": artifacts[0] if artifacts else None,
    }


def create_setup_state(seed: Optional[int] = None) -> dict:
    rng = random.Random(seed) if seed is not None else random
    offer_ids = [adventurer.id for adventurer in rng.sample(ADVENTURERS, 6)]
    return {
        "offer_ids": offer_ids,
        "team1": [],
        "team2": [],
    }


def build_default_team_from_ids(adventurer_ids: list[str], allowed_artifact_ids: set[str] | None = None) -> list[dict]:
    members = []
    for index, adventurer_id in enumerate(adventurer_ids[: len(SLOT_ORDER)]):
        members.append(_build_member(adventurer_id, SLOT_ORDER[index], allowed_artifact_ids))
    return members


def create_setup_from_team_ids(
    team1_ids: list[str],
    team2_ids: list[str],
    *,
    team1_allowed_artifact_ids: set[str] | None = None,
    team2_allowed_artifact_ids: set[str] | None = None,
) -> dict:
    setup = {
        "offer_ids": list(dict.fromkeys(team1_ids + team2_ids)),
        "team1": build_default_team_from_ids(team1_ids, team1_allowed_artifact_ids),
        "team2": build_default_team_from_ids(team2_ids, team2_allowed_artifact_ids),
    }
    if team1_allowed_artifact_ids is not None:
        setup["team1_allowed_artifact_ids"] = sorted(team1_allowed_artifact_ids)
    if team2_allowed_artifact_ids is not None:
        setup["team2_allowed_artifact_ids"] = sorted(team2_allowed_artifact_ids)
    _normalize_team_artifacts(setup["team1"], team1_allowed_artifact_ids)
    _normalize_team_artifacts(setup["team2"], team2_allowed_artifact_ids)
    return setup


def _find_member_index(team: list[dict], adventurer_id: str) -> Optional[int]:
    for index, member in enumerate(team):
        if member["adventurer_id"] == adventurer_id:
            return index
    return None


def _next_available_slot(team: list[dict]) -> str:
    used = {member["slot"] for member in team}
    for slot in SLOT_ORDER:
        if slot not in used:
            return slot
    return SLOT_FRONT


def _member_by_slot(team: list[dict], slot: str) -> Optional[int]:
    for index, member in enumerate(team):
        if member["slot"] == slot:
            return index
    return None


def assign_offer_to_team(setup_state: dict, adventurer_id: str, team_num: int) -> bool:
    if adventurer_id not in setup_state["offer_ids"]:
        return False
    target_team = setup_state[_team_key(team_num)]
    other_team = setup_state[_team_key(2 if team_num == 1 else 1)]
    if _find_member_index(target_team, adventurer_id) is not None:
        return False
    if len(target_team) >= 3:
        return False

    other_index = _find_member_index(other_team, adventurer_id)
    if other_index is not None:
        other_team.pop(other_index)
        _normalize_team_artifacts(other_team, _allowed_artifact_ids_for_team(setup_state, 2 if team_num == 1 else 1))

    target_team.append(_build_member(adventurer_id, _next_available_slot(target_team), _allowed_artifact_ids_for_team(setup_state, team_num)))
    _normalize_team_artifacts(target_team, _allowed_artifact_ids_for_team(setup_state, team_num))
    return True


def remove_member_from_team(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if 0 <= member_index < len(team):
        team.pop(member_index)
        _normalize_team_artifacts(team, _allowed_artifact_ids_for_team(setup_state, team_num))
        return True
    return False


def cycle_member_slot(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    current_slot = team[member_index]["slot"]
    next_slot = SLOT_ORDER[(SLOT_ORDER.index(current_slot) + 1) % len(SLOT_ORDER)]
    occupant_index = _member_by_slot(team, next_slot)
    team[member_index]["slot"] = next_slot
    if occupant_index is not None and occupant_index != member_index:
        team[occupant_index]["slot"] = current_slot
    return True


def set_member_slot(setup_state: dict, team_num: int, member_index: int, slot: str) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)) or slot not in SLOT_ORDER:
        return False
    current_slot = team[member_index]["slot"]
    if current_slot == slot:
        return True
    occupant_index = _member_by_slot(team, slot)
    team[member_index]["slot"] = slot
    if occupant_index is not None and occupant_index != member_index:
        team[occupant_index]["slot"] = current_slot
    return True


def cycle_member_class(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    enforce_unique_classes = _team_enforces_unique_classes(setup_state, team_num)
    used_classes = {
        other["class_name"]
        for index, other in enumerate(team)
        if index != member_index
    }
    class_index = CLASS_ORDER.index(member["class_name"])
    class_name = member["class_name"]
    for offset in range(1, len(CLASS_ORDER) + 1):
        candidate = CLASS_ORDER[(class_index + offset) % len(CLASS_ORDER)]
        if not enforce_unique_classes or candidate == NO_CLASS_NAME or candidate not in used_classes:
            class_name = candidate
            break
    if enforce_unique_classes and class_name != NO_CLASS_NAME and class_name in used_classes:
        return False
    member["class_name"] = class_name
    if class_name == NO_CLASS_NAME:
        member["class_skill_id"] = None
        member["artifact_id"] = None
        return True
    member["class_skill_id"] = CLASS_SKILLS[class_name][0].id
    _normalize_team_artifacts(team, _allowed_artifact_ids_for_team(setup_state, team_num))
    return True


def set_member_class(setup_state: dict, team_num: int, member_index: int, class_name: str) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)) or class_name not in CLASS_ORDER:
        return False
    if (
        _team_enforces_unique_classes(setup_state, team_num)
        and class_name != NO_CLASS_NAME
        and any(other["class_name"] == class_name for index, other in enumerate(team) if index != member_index)
    ):
        return False
    member = team[member_index]
    member["class_name"] = class_name
    if class_name == NO_CLASS_NAME:
        member["class_skill_id"] = None
        member["artifact_id"] = None
        return True
    available_skills = CLASS_SKILLS[class_name]
    current_skill = member.get("class_skill_id")
    if current_skill not in {skill.id for skill in available_skills}:
        member["class_skill_id"] = available_skills[0].id
    _normalize_team_artifacts(team, _allowed_artifact_ids_for_team(setup_state, team_num))
    return True


def cycle_member_skill(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    if member["class_name"] == NO_CLASS_NAME:
        member["class_skill_id"] = None
        return True
    skills = CLASS_SKILLS[member["class_name"]]
    current_index = next(
        (index for index, skill in enumerate(skills) if skill.id == member["class_skill_id"]),
        0,
    )
    member["class_skill_id"] = skills[(current_index + 1) % len(skills)].id
    return True


def set_member_skill(setup_state: dict, team_num: int, member_index: int, skill_id: str | None) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    if member["class_name"] == NO_CLASS_NAME:
        member["class_skill_id"] = None
        return skill_id in {None, ""}
    if skill_id is None:
        return False
    skills = CLASS_SKILLS[member["class_name"]]
    if skill_id not in {skill.id for skill in skills}:
        return False
    member["class_skill_id"] = skill_id
    return True


def cycle_member_weapon(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    adventurer = next(adventurer for adventurer in ADVENTURERS if adventurer.id == member["adventurer_id"])
    weapon_ids = [weapon.id for weapon in adventurer.signature_weapons]
    current_weapon = member["primary_weapon_id"] or weapon_ids[0]
    current_index = weapon_ids.index(current_weapon)
    member["primary_weapon_id"] = weapon_ids[(current_index + 1) % len(weapon_ids)]
    return True


def set_member_weapon(setup_state: dict, team_num: int, member_index: int, weapon_id: str) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    adventurer = next(adventurer for adventurer in ADVENTURERS if adventurer.id == member["adventurer_id"])
    weapon_ids = [weapon.id for weapon in adventurer.signature_weapons]
    if weapon_id not in weapon_ids:
        return False
    member["primary_weapon_id"] = weapon_id
    return True


def cycle_member_artifact(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    artifact_ids = available_artifact_ids(_allowed_artifact_ids_for_team(setup_state, team_num))
    if not artifact_ids:
        member["artifact_id"] = None
        return True
    current_artifact = member["artifact_id"] if member["artifact_id"] in artifact_ids else artifact_ids[0]
    current_index = artifact_ids.index(current_artifact)
    used_by_others = {
        other["artifact_id"]
        for index, other in enumerate(team)
        if index != member_index and other.get("artifact_id") is not None
    }
    for offset in range(1, len(artifact_ids) + 1):
        candidate = artifact_ids[(current_index + offset) % len(artifact_ids)]
        if candidate not in used_by_others:
            member["artifact_id"] = candidate
            return True
    return True


def set_member_artifact(setup_state: dict, team_num: int, member_index: int, artifact_id: str | None) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    allowed_artifact_ids = _allowed_artifact_ids_for_team(setup_state, team_num)
    valid_ids = available_artifact_ids(allowed_artifact_ids)
    if artifact_id is None:
        member["artifact_id"] = None
        return True
    if artifact_id not in valid_ids:
        return False
    used_by_others = {
        other.get("artifact_id")
        for index, other in enumerate(team)
        if index != member_index and other.get("artifact_id") is not None
    }
    if artifact_id in used_by_others:
        return False
    member["artifact_id"] = artifact_id
    return True


def cycle_member_field(setup_state: dict, team_num: int, member_index: int, field_name: str) -> bool:
    if field_name == "slot":
        return cycle_member_slot(setup_state, team_num, member_index)
    if field_name == "class":
        return cycle_member_class(setup_state, team_num, member_index)
    if field_name == "skill":
        return cycle_member_skill(setup_state, team_num, member_index)
    if field_name == "weapon":
        return cycle_member_weapon(setup_state, team_num, member_index)
    if field_name == "artifact":
        return cycle_member_artifact(setup_state, team_num, member_index)
    return False


def team_is_ready(setup_state: dict, team_num: int) -> bool:
    team = setup_state[_team_key(team_num)]
    required_size = int(setup_state.get(f"{_team_key(team_num)}_required_size", 3))
    slots = [member["slot"] for member in team]
    non_empty_classes = [member["class_name"] for member in team if member.get("class_name") not in {None, "", NO_CLASS_NAME}]
    class_ready = True
    if _team_enforces_unique_classes(setup_state, team_num):
        class_ready = len(set(non_empty_classes)) == len(non_empty_classes)
    return (
        len(team) == required_size
        and len(set(slots)) == len(slots)
        and all(slot in SLOT_ORDER for slot in slots)
        and class_ready
    )


def setup_is_ready(setup_state: dict) -> bool:
    return team_is_ready(setup_state, 1) and team_is_ready(setup_state, 2)


def _sorted_team_members(team: list[dict]) -> list[dict]:
    return sorted(team, key=lambda member: SLOT_ORDER.index(member["slot"]))


def build_battle_from_setup(setup_state: dict):
    if not setup_is_ready(setup_state):
        raise ValueError("Setup must meet each team's required size with unique slots.")

    team1 = create_team(
        "Magnate A",
        [
            make_pick(
                member["adventurer_id"],
                slot=member["slot"],
                class_name=member["class_name"],
                class_skill_id=member["class_skill_id"],
                primary_weapon_id=member["primary_weapon_id"],
                artifact_id=member["artifact_id"],
            )
            for member in _sorted_team_members(setup_state["team1"])
        ],
    )
    team2 = create_team(
        "Magnate B",
        [
            make_pick(
                member["adventurer_id"],
                slot=member["slot"],
                class_name=member["class_name"],
                class_skill_id=member["class_skill_id"],
                primary_weapon_id=member["primary_weapon_id"],
                artifact_id=member["artifact_id"],
            )
            for member in _sorted_team_members(setup_state["team2"])
        ],
    )
    battle = create_battle(team1, team2)
    determine_initiative_order(battle)
    return battle
