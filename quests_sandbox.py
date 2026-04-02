from __future__ import annotations

import random
from typing import Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ruleset_data import ADVENTURERS, ARTIFACTS, CLASS_SKILLS
from quests_ruleset_logic import create_battle, create_team, determine_initiative_order, make_pick


SLOT_ORDER = (SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT)
CLASS_ORDER = tuple(CLASS_SKILLS.keys())


def _team_key(team_num: int) -> str:
    return f"team{team_num}"


def _default_class_for_slot(slot: str) -> str:
    if slot == SLOT_FRONT:
        return "Fighter"
    if slot == SLOT_BACK_LEFT:
        return "Ranger"
    return "Cleric"


def compatible_artifact_ids(class_name: str) -> list[str]:
    return [artifact.id for artifact in ARTIFACTS if class_name in artifact.attunement]


def _normalize_team_artifacts(team: list[dict]):
    used: set[str] = set()
    for member in team:
        artifact_ids = compatible_artifact_ids(member["class_name"])
        if not artifact_ids:
            member["artifact_id"] = None
            continue
        if member.get("artifact_id") in artifact_ids and member["artifact_id"] not in used:
            chosen = member["artifact_id"]
        else:
            chosen = next((artifact_id for artifact_id in artifact_ids if artifact_id not in used), artifact_ids[0])
        member["artifact_id"] = chosen
        used.add(chosen)


def _build_member(adventurer_id: str, slot: str) -> dict:
    class_name = _default_class_for_slot(slot)
    artifacts = compatible_artifact_ids(class_name)
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


def build_default_team_from_ids(adventurer_ids: list[str]) -> list[dict]:
    members = []
    for index, adventurer_id in enumerate(adventurer_ids[: len(SLOT_ORDER)]):
        members.append(_build_member(adventurer_id, SLOT_ORDER[index]))
    return members


def create_setup_from_team_ids(team1_ids: list[str], team2_ids: list[str]) -> dict:
    setup = {
        "offer_ids": list(dict.fromkeys(team1_ids + team2_ids)),
        "team1": build_default_team_from_ids(team1_ids),
        "team2": build_default_team_from_ids(team2_ids),
    }
    _normalize_team_artifacts(setup["team1"])
    _normalize_team_artifacts(setup["team2"])
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
        _normalize_team_artifacts(other_team)

    target_team.append(_build_member(adventurer_id, _next_available_slot(target_team)))
    _normalize_team_artifacts(target_team)
    return True


def remove_member_from_team(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if 0 <= member_index < len(team):
        team.pop(member_index)
        _normalize_team_artifacts(team)
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


def cycle_member_class(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    class_index = CLASS_ORDER.index(member["class_name"])
    class_name = CLASS_ORDER[(class_index + 1) % len(CLASS_ORDER)]
    member["class_name"] = class_name
    member["class_skill_id"] = CLASS_SKILLS[class_name][0].id
    artifacts = compatible_artifact_ids(class_name)
    if member["artifact_id"] not in artifacts:
        member["artifact_id"] = artifacts[0] if artifacts else None
    _normalize_team_artifacts(team)
    return True


def cycle_member_skill(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    skills = CLASS_SKILLS[member["class_name"]]
    current_index = next(
        (index for index, skill in enumerate(skills) if skill.id == member["class_skill_id"]),
        0,
    )
    member["class_skill_id"] = skills[(current_index + 1) % len(skills)].id
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


def cycle_member_artifact(setup_state: dict, team_num: int, member_index: int) -> bool:
    team = setup_state[_team_key(team_num)]
    if not (0 <= member_index < len(team)):
        return False
    member = team[member_index]
    artifact_ids = compatible_artifact_ids(member["class_name"])
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
    return len(team) == 3 and {member["slot"] for member in team} == set(SLOT_ORDER)


def setup_is_ready(setup_state: dict) -> bool:
    return team_is_ready(setup_state, 1) and team_is_ready(setup_state, 2)


def _sorted_team_members(team: list[dict]) -> list[dict]:
    return sorted(team, key=lambda member: SLOT_ORDER.index(member["slot"]))


def build_battle_from_setup(setup_state: dict):
    if not setup_is_ready(setup_state):
        raise ValueError("Setup must have three assigned adventurers with unique slots on each team.")

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
