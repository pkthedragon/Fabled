from __future__ import annotations

from dataclasses import dataclass
import random

from quest_enemy_runtime import QUEST_ENEMY_IDS_BY_LOCALE_TIER, QUEST_ENEMY_META_BY_ID, build_quest_enemy_setup_member
from quests_ruleset_data import QUEST_ENEMY_TIER_BY_ID, QUEST_LOCALES_BY_ID
from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT


TIER_ORDER = ("tier_1", "tier_2", "tier_3", "tier_4", "tier_5", "apex")
TIER_INDEX = {tier_id: index for index, tier_id in enumerate(TIER_ORDER)}
SLOT_ORDER = (SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT)
PARTY_SUFFIX_BY_TIER = {
    "tier_1": "Skirmish",
    "tier_2": "Raid",
    "tier_3": "Warband",
    "tier_4": "Host",
    "tier_5": "Circle",
    "apex": "Apex",
}


@dataclass(frozen=True)
class QuestEnemyMemberBlueprint:
    adventurer_id: str
    slot: str
    class_name: str
    class_skill_id: str | None
    primary_weapon_id: str
    artifact_id: str | None = None

    def to_member_dict(self) -> dict:
        return {
            "adventurer_id": self.adventurer_id,
            "slot": self.slot,
            "class_name": self.class_name,
            "class_skill_id": self.class_skill_id,
            "primary_weapon_id": self.primary_weapon_id,
            "artifact_id": self.artifact_id,
        }


@dataclass(frozen=True)
class QuestEnemyPartyBlueprint:
    id: str
    title: str
    locale_id: str
    tier_id: str
    members: tuple[QuestEnemyMemberBlueprint, ...]

    @property
    def locale_name(self) -> str:
        locale = QUEST_LOCALES_BY_ID.get(self.locale_id)
        return locale.name if locale is not None else self.locale_id.replace("_", " ").title()

    @property
    def tier_name(self) -> str:
        tier = QUEST_ENEMY_TIER_BY_ID.get(self.tier_id)
        return tier.name if tier is not None else self.tier_id.replace("_", " ").title()

    @property
    def selected_ids(self) -> list[str]:
        return [member.adventurer_id for member in self.members]

    @property
    def enemy_name(self) -> str:
        return self.title

    def build_setup_members(self) -> list[dict]:
        return [member.to_member_dict() for member in self.members]


@dataclass(frozen=True)
class ChosenQuestEnemyParty:
    target_tier_id: str
    blueprint: QuestEnemyPartyBlueprint

    @property
    def locale_id(self) -> str:
        return self.blueprint.locale_id

    @property
    def tier_id(self) -> str:
        return self.blueprint.tier_id

    @property
    def selected_ids(self) -> list[str]:
        return self.blueprint.selected_ids

    @property
    def setup_members(self) -> list[dict]:
        return self.blueprint.build_setup_members()

    @property
    def enemy_name(self) -> str:
        return self.blueprint.enemy_name


def ranked_quest_tier_for_reputation(reputation: int) -> str:
    if reputation >= 1150:
        return "apex"
    if reputation >= 900:
        return "tier_5"
    if reputation >= 700:
        return "tier_4"
    if reputation >= 550:
        return "tier_3"
    if reputation >= 400:
        return "tier_2"
    return "tier_1"


def _enemy_member(enemy_id: str, slot: str) -> QuestEnemyMemberBlueprint:
    member = build_quest_enemy_setup_member(enemy_id, slot)
    return QuestEnemyMemberBlueprint(
        adventurer_id=member["adventurer_id"],
        slot=member["slot"],
        class_name=member["class_name"],
        class_skill_id=member["class_skill_id"],
        primary_weapon_id=member["primary_weapon_id"],
        artifact_id=member.get("artifact_id"),
    )


def _frontline_sort_key(enemy_id: str) -> tuple[int, str]:
    meta = QUEST_ENEMY_META_BY_ID[enemy_id]
    return (meta["frontline_score"], meta["name"])


def _backline_sort_key(enemy_id: str) -> tuple[int, str]:
    meta = QUEST_ENEMY_META_BY_ID[enemy_id]
    return (meta["backline_score"], meta["name"])


def _choose_enemy_ids_for_party(locale_id: str, tier_id: str, rng: random.Random) -> list[str]:
    pool = list(QUEST_ENEMY_IDS_BY_LOCALE_TIER.get((locale_id, tier_id), ()))
    if not pool:
        return []
    if tier_id == "apex" or len(pool) <= 3:
        return pool[:3]

    pool.sort(key=_frontline_sort_key, reverse=True)
    front_sample = pool[: min(3, len(pool))]
    front_id = rng.choice(front_sample)
    remaining = [enemy_id for enemy_id in pool if enemy_id != front_id]
    remaining.sort(key=_backline_sort_key, reverse=True)
    back_candidates = remaining[: min(4, len(remaining))]
    if len(back_candidates) <= 2:
        chosen_back = back_candidates
    else:
        chosen_back = rng.sample(back_candidates, 2)
        chosen_back.sort(key=_backline_sort_key, reverse=True)
    return [front_id, *chosen_back[:2]]


def _party_title(selected_ids: list[str], tier_id: str) -> str:
    if not selected_ids:
        return "Enemy Party"
    front_name = QUEST_ENEMY_META_BY_ID[selected_ids[0]]["name"]
    if len(selected_ids) == 1:
        return front_name
    suffix = PARTY_SUFFIX_BY_TIER.get(tier_id, "Party")
    return f"{front_name} {suffix}"


def _blueprint_from_selection(locale_id: str, tier_id: str, selected_ids: list[str]) -> QuestEnemyPartyBlueprint | None:
    if not selected_ids:
        return None
    members: list[QuestEnemyMemberBlueprint] = []
    if len(selected_ids) == 1:
        members.append(_enemy_member(selected_ids[0], SLOT_FRONT))
    else:
        members.append(_enemy_member(selected_ids[0], SLOT_FRONT))
        if len(selected_ids) >= 2:
            members.append(_enemy_member(selected_ids[1], SLOT_BACK_LEFT))
        if len(selected_ids) >= 3:
            members.append(_enemy_member(selected_ids[2], SLOT_BACK_RIGHT))
    party_id = f"{locale_id}_{tier_id}_{'_'.join(selected_ids)}"
    return QuestEnemyPartyBlueprint(
        id=party_id,
        title=_party_title(selected_ids, tier_id),
        locale_id=locale_id,
        tier_id=tier_id,
        members=tuple(members),
    )


def choose_ranked_quest_enemy_party(
    *,
    player_party_ids: list[str],
    reputation: int,
    rng: random.Random,
) -> ChosenQuestEnemyParty | None:
    del player_party_ids
    target_tier_id = ranked_quest_tier_for_reputation(reputation)
    locales = list(QUEST_LOCALES_BY_ID)
    rng.shuffle(locales)
    candidate_blueprints: list[QuestEnemyPartyBlueprint] = []
    for locale_id in locales:
        selected_ids = _choose_enemy_ids_for_party(locale_id, target_tier_id, rng)
        blueprint = _blueprint_from_selection(locale_id, target_tier_id, selected_ids)
        if blueprint is not None:
            candidate_blueprints.append(blueprint)
    if not candidate_blueprints:
        return None
    chosen = rng.choice(candidate_blueprints)
    return ChosenQuestEnemyParty(target_tier_id=target_tier_id, blueprint=chosen)
