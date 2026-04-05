from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, permutations
from typing import Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_loadout import MemberBuild, TeamLoadout, compatible_artifact_ids
from quests_ai_tables import pair_synergy_value, plan_reliability_score, team_archetype_bonus, team_style_scores
from quests_ai_tags import (
    ADVENTURER_AI,
    ARTIFACT_TAGS,
    CLASS_SKILL_TAGS,
    artifact_preference_score,
    skill_preference_score,
    weapon_preference_score,
)
from quests_ruleset_data import ADVENTURERS_BY_ID, CLASS_SKILLS


SLOT_ORDER = (SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT)
ALL_CLASSES = tuple(CLASS_SKILLS.keys())
BLIND_BEAM_WIDTH = 64
ROSTER_SUBSET_KEEP = 14


BLIND_CLASS_PRIOR = {
    "Ranger": 14.0,
    "Fighter": 10.0,
    "Rogue": 8.0,
    "Cleric": 3.0,
    "Warden": -2.0,
    "Mage": -6.0,
}


BLIND_SKILL_PRIOR = {
    "deadeye": 11.0,
    "medic": 10.0,
    "assassin": 8.0,
    "archmage": 5.5,
    "arcane": 5.0,
    "healer": 4.0,
    "bulwark": -1.0,
    "martial": -2.0,
    "armed": -2.0,
    "covert": -3.0,
    "vigilant": -9.0,
    "inevitable": 1.0,
}


BLIND_ARTIFACT_PRIOR = {
    "selkies_skin": 10.0,
    "enchanted_lamp": 10.0,
    "swan_cloak": 9.0,
    "soaring_crown": 9.0,
    "fading_diadem": 8.0,
    "magic_mirror": 8.0,
    "winged_sandals": 7.0,
    "bluebeards_key": 7.0,
    "paradox_rings": 7.0,
    "sun_gods_banner": 4.0,
    "all_mill": 4.0,
    "holy_grail": 4.0,
    "dragons_horn": 4.0,
    "bottled_clouds": 4.0,
    "arcane_hourglass": -12.0,
    "dire_wolf_spine": 2.0,
    "naiads_knife": 2.0,
    "last_prism": 2.0,
    "goose_quill": 1.0,
    "cursed_spindle": 1.0,
    "red_hood": 1.0,
    "golden_fleece": 1.0,
    "jade_rabbit": 2.0,
    "cornucopia": 2.0,
    "nettle_smock": 2.0,
    "black_torch": 1.0,
    "lightning_helm": 0.0,
    "misericorde": 0.0,
    "iron_rosary": 2.0,
    "starskin_veil": 7.0,
    "blood_diamond": 3.0,
    "suspicious_eye": 7.0,
    "philosophers_stone": 8.0,
    "seeking_yarn": 6.0,
    "tarnhelm": 6.0,
    "walking_abode": 5.0,
    "nebula_mail": 5.0,
}


BLIND_ADVENTURER_PRIOR = {
    "briar_rose": 18.0,
    "rapunzel_the_golden": 16.0,
    "ali_baba": 15.0,
    "destitute_vasilisa": 15.0,
    "reynard_lupine_trickster": 14.0,
    "little_jack": 13.0,
    "kama_the_honeyed": 12.0,
    "porcus_iii": 8.0,
    "matchbox_liesl": 8.0,
    "lady_of_reflections": 7.0,
    "hunold_the_piper": 3.0,
    "the_green_knight": 3.0,
    "maui_sunthief": 2.0,
    "witch_hunter_gretel": 1.0,
    "robin_hooded_avenger": -4.0,
    "the_good_beast": -4.0,
    "sir_roland": -5.0,
    "march_hare": -6.0,
    "ashen_ella": -6.0,
    "lucky_constantine": -6.0,
    "scheherazade_dawns_ransom": 12.0,
    "storyweaver_anansi": 11.0,
    "odysseus_the_nobody": 12.0,
    "witch_of_the_east": 10.0,
    "tam_lin_thornbound": 13.0,
}


BLIND_WEAPON_PRIORITY = {
    "briar_rose": ("thorn_snare", "spindle_bow"),
    "rapunzel_the_golden": ("golden_snare", "ivory_tower"),
    "destitute_vasilisa": ("guiding_doll", "skull_lantern"),
    "little_jack": ("giants_harp", "skyfall"),
    "reynard_lupine_trickster": ("fang", "foxfire_bow"),
    "robin_hooded_avenger": ("the_flock", "kingmaker"),
    "march_hare": ("cracked_stopwatch", "stitch_in_time"),
    "witch_hunter_gretel": ("hot_mitts", "crumb_shot"),
    "hunold_the_piper": ("golden_fiddle", "lightning_rod"),
    "ali_baba": ("jar_of_oil", "thiefs_dagger"),
    "kama_the_honeyed": ("sugarcane_bow", "the_stinger"),
    "sea_wench_asha": ("frost_scepter", "mirror_blade"),
    "matchbox_liesl": ("eternal_torch", "matchsticks"),
    "scheherazade_dawns_ransom": ("lamp_of_infinity", "tome_of_ancients"),
    "storyweaver_anansi": ("the_pen", "the_sword"),
    "odysseus_the_nobody": ("olivewood_spear", "beggars_greatbow"),
    "witch_of_the_east": ("zephyr", "comet"),
    "tam_lin_thornbound": ("butterfly_knife", "beam_of_light"),
}


BLIND_CLASS_OPTIONS = {
    "briar_rose": ("Ranger", "Rogue", "Cleric"),
    "rapunzel_the_golden": ("Fighter", "Warden"),
    "destitute_vasilisa": ("Mage", "Cleric", "Warden"),
    "reynard_lupine_trickster": ("Rogue", "Ranger", "Cleric"),
    "little_jack": ("Fighter", "Warden", "Ranger"),
    "ali_baba": ("Rogue", "Mage"),
    "kama_the_honeyed": ("Ranger", "Rogue", "Mage"),
    "porcus_iii": ("Warden", "Ranger"),
    "matchbox_liesl": ("Cleric", "Mage"),
    "lady_of_reflections": ("Warden", "Mage", "Rogue"),
    "hunold_the_piper": ("Mage", "Ranger", "Cleric"),
    "the_green_knight": ("Fighter", "Warden", "Ranger"),
    "maui_sunthief": ("Warden", "Fighter"),
    "robin_hooded_avenger": ("Ranger", "Cleric", "Mage"),
    "the_good_beast": ("Cleric", "Warden", "Rogue"),
    "march_hare": ("Mage", "Rogue"),
    "sir_roland": ("Warden", "Fighter"),
    "red_blanchette": ("Fighter", "Mage", "Rogue"),
    "witch_hunter_gretel": ("Fighter", "Ranger", "Rogue"),
    "lucky_constantine": ("Rogue", "Fighter", "Ranger"),
    "sea_wench_asha": ("Mage", "Rogue", "Cleric"),
    "ashen_ella": ("Mage", "Rogue"),
    "pinocchio_cursed_puppet": ("Fighter", "Rogue", "Mage"),
    "rumpelstiltskin": ("Mage", "Ranger", "Rogue"),
    "scheherazade_dawns_ransom": ("Cleric", "Mage", "Warden"),
    "storyweaver_anansi": ("Ranger", "Rogue", "Mage"),
    "odysseus_the_nobody": ("Fighter", "Ranger", "Rogue"),
    "witch_of_the_east": ("Mage", "Rogue", "Fighter"),
    "tam_lin_thornbound": ("Warden", "Fighter", "Cleric"),
}


BLIND_SKILL_ORDER = {
    "Ranger": ("deadeye", "armed"),
    "Fighter": ("martial", "inevitable"),
    "Rogue": ("assassin", "covert"),
    "Cleric": ("medic", "healer"),
    "Warden": ("bulwark", "vigilant"),
    "Mage": ("arcane", "archmage"),
}


ROLE_CLASS_FIT = {
    "Warden": {"primary_tank", "anti_burst", "frontline_ready", "stall_anchor", "frontline_pivot", "bruiser"},
    "Fighter": {"burst_finisher", "frontline_breaker", "status_payoff", "bruiser", "frontline_ready", "melee_reach"},
    "Ranger": {"backline_reach", "ranged_pressure", "spotlight_enabler", "spread_pressure", "control_anchor", "shock_engine"},
    "Rogue": {"tempo_engine", "backline_reach", "burst_finisher", "anti_caster", "swap_engine", "status_payoff", "bonus_action_user"},
    "Cleric": {"healer", "guard_support", "carry_support", "anti_burst", "control_anchor"},
    "Mage": {"magic_carry", "shock_engine", "anti_caster", "spell_loop", "tempo_engine", "control_anchor", "stat_manipulator"},
}


ROLE_ARTIFACT_HINTS = {
    "fragile": {"selkies_skin", "enchanted_lamp", "swan_cloak", "magic_mirror"},
    "backline_reach": {"soaring_crown", "dragons_horn", "bottled_clouds", "suspicious_eye"},
    "ranged_pressure": {"soaring_crown", "dragons_horn", "jade_rabbit", "suspicious_eye"},
    "magic_carry": {"paradox_rings", "magic_mirror", "last_prism", "goose_quill"},
    "healer": {"fading_diadem", "holy_grail", "iron_rosary", "sun_gods_banner", "winged_sandals", "starskin_veil", "philosophers_stone"},
    "guard_support": {"fading_diadem", "holy_grail", "iron_rosary", "sun_gods_banner", "starskin_veil"},
    "primary_tank": {"sun_gods_banner", "all_mill", "golden_fleece", "nettle_smock", "starskin_veil"},
    "burst_finisher": {"dire_wolf_spine", "naiads_knife", "dragons_horn", "red_hood", "blood_diamond"},
    "tempo_engine": {"winged_sandals", "paradox_rings", "goose_quill", "jade_rabbit", "seeking_yarn", "nebula_mail"},
    "anti_caster": {"magic_mirror", "enchanted_lamp", "bluebeards_key"},
}


GENERIC_CLASS_ORDER = ("Rogue", "Cleric", "Warden", "Fighter", "Ranger", "Mage")


@dataclass(frozen=True)
class QuestBlindBuild:
    adventurer_id: str
    class_name: str
    class_skill_id: str
    primary_weapon_id: str
    artifact_id: Optional[str]
    score: float
    blind_tags: tuple[str, ...]


@dataclass(frozen=True)
class QuestLoadoutPackage:
    offer_ids: tuple[str, ...]
    members: tuple[QuestBlindBuild, ...]
    score: float
    trio_option_value: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class QuestTrioProfile:
    team_ids: tuple[str, ...]
    loadout: TeamLoadout
    score: float
    tag_set: tuple[str, ...]
    styles: tuple[tuple[str, float], ...]


def _ordered_unique(values) -> tuple:
    seen = set()
    ordered = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _sorted_ids(adventurer_ids: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(sorted(adventurer_ids))


def _weapon_def(adventurer_id: str, weapon_id: str):
    adventurer = ADVENTURERS_BY_ID[adventurer_id]
    return next(item for item in adventurer.signature_weapons if item.id == weapon_id)


def _class_options_for(adventurer_id: str) -> tuple[str, ...]:
    profile = ADVENTURER_AI[adventurer_id]
    explicit = BLIND_CLASS_OPTIONS.get(adventurer_id, profile.preferred_classes)
    fallback = sorted(
        ALL_CLASSES,
        key=lambda class_name: _generic_class_affinity(adventurer_id, class_name),
        reverse=True,
    )
    return _ordered_unique(tuple(explicit) + profile.preferred_classes + tuple(fallback) + GENERIC_CLASS_ORDER)


def _weapon_order_for(adventurer_id: str) -> tuple[str, ...]:
    profile = ADVENTURER_AI[adventurer_id]
    weapon_ids = tuple(weapon.id for weapon in ADVENTURERS_BY_ID[adventurer_id].signature_weapons)
    explicit = BLIND_WEAPON_PRIORITY.get(adventurer_id, ())
    return _ordered_unique(explicit + profile.preferred_weapons + weapon_ids)


def _generic_class_affinity(adventurer_id: str, class_name: str) -> float:
    profile = ADVENTURER_AI[adventurer_id]
    roles = set(profile.role_tags)
    value = BLIND_CLASS_PRIOR.get(class_name, 0.0)
    if class_name in BLIND_CLASS_OPTIONS.get(adventurer_id, ()):
        value += 12.0 - BLIND_CLASS_OPTIONS[adventurer_id].index(class_name) * 3.5
    elif class_name in profile.preferred_classes:
        value += 10.0 - profile.preferred_classes.index(class_name) * 3.0
    value += len(roles & ROLE_CLASS_FIT.get(class_name, set())) * 2.0
    if class_name == "Warden" and profile.position_scores[SLOT_FRONT] >= 80:
        value += 4.0
    if class_name == "Cleric" and {"healer", "guard_support", "carry_support"} & roles:
        value += 4.0
    if class_name == "Ranger" and {"backline_reach", "ranged_pressure", "spotlight_enabler"} & roles:
        value += 4.0
    if class_name == "Rogue" and {"tempo_engine", "bonus_action_user", "anti_caster", "backline_reach"} & roles:
        value += 4.0
    if class_name == "Mage" and {"magic_carry", "spell_loop", "shock_engine", "anti_caster"} & roles:
        value += 4.0
    if class_name == "Fighter" and {"frontline_breaker", "burst_finisher", "bruiser", "frontline_ready"} & roles:
        value += 4.0
    return value


def _class_claim_value(adventurer_id: str, class_name: str, party_ids: tuple[str, ...]) -> float:
    own = _generic_class_affinity(adventurer_id, class_name)
    claims = sorted((_generic_class_affinity(other_id, class_name), other_id) for other_id in party_ids)
    claims.reverse()
    rank = next((index for index, (_score, other_id) in enumerate(claims) if other_id == adventurer_id), len(claims) - 1)
    top_score = claims[0][0] if claims else own
    value = 0.0
    if own >= top_score - 1.5:
        value += 4.5
    elif own >= top_score - 4.0:
        value += 1.5
    else:
        value -= 2.5 * min(rank, 2)
    if BLIND_CLASS_PRIOR.get(class_name, 0.0) >= 8.0 and rank >= 2:
        value -= 4.0
    if BLIND_CLASS_PRIOR.get(class_name, 0.0) <= 0.0 and rank == 0:
        value += 2.5
    return value


def _skill_order_for_class(adventurer_id: str, class_name: str) -> tuple[str, ...]:
    profile = ADVENTURER_AI[adventurer_id]
    preferred = profile.preferred_skills.get(class_name, ())
    legal_ids = tuple(skill.id for skill in CLASS_SKILLS[class_name])
    return tuple(
        skill_id
        for skill_id in _ordered_unique(BLIND_SKILL_ORDER[class_name] + preferred + legal_ids)
        if skill_id in legal_ids
    )


def _artifact_prior(artifact_id: Optional[str]) -> float:
    if artifact_id is None:
        return 1.0
    return BLIND_ARTIFACT_PRIOR.get(artifact_id, 0.0)


def _base_blind_tags(
    adventurer_id: str,
    class_name: str,
    class_skill_id: str,
    primary_weapon_id: str,
    artifact_id: Optional[str],
) -> tuple[str, ...]:
    profile = ADVENTURER_AI[adventurer_id]
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    tags = set(profile.role_tags) | set(profile.shell_tags) | set(profile.matchup_tags)
    tags.update(CLASS_SKILL_TAGS.get(class_skill_id, set()))
    if artifact_id is not None:
        tags.update(ARTIFACT_TAGS.get(artifact_id, set()))
    tags.add(class_name.lower())
    tags.add(weapon.kind)
    if weapon.kind in {"ranged", "magic"}:
        tags.add("reach")
    if weapon.kind == "ranged":
        tags.add("ranged_pressure")
    if weapon.kind == "magic":
        tags.add("magic_pressure")
        tags.add("spell")
    if weapon.kind == "melee":
        tags.add("melee_pressure")
    if class_name == "Cleric":
        tags.add("sustain")
    if class_name == "Warden":
        tags.add("frontline")
    if class_skill_id == "medic":
        tags.add("cleanse")
        tags.add("anti_status")
    return tuple(sorted(tags))


def _weapon_blind_value(adventurer_id: str, primary_weapon_id: str) -> float:
    profile = ADVENTURER_AI[adventurer_id]
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    order = _weapon_order_for(adventurer_id)
    value = weapon_preference_score(profile, primary_weapon_id) * 0.75
    if primary_weapon_id in order:
        value += max(0.0, 12.0 - order.index(primary_weapon_id) * 4.0)
    if weapon.kind == "ranged":
        value += 8.0
    elif weapon.kind == "magic":
        value += 6.5
    elif weapon.kind == "melee":
        value += 4.0 if profile.position_scores[SLOT_FRONT] >= 72 or "melee_reach" in profile.role_tags else -1.5
    if weapon.strike.spread:
        value += 2.0
    if weapon.spells:
        value += 2.0
    if weapon.kind == "melee" and "primary_tank" not in profile.role_tags and "frontline_ready" not in profile.role_tags and "bruiser" not in profile.role_tags:
        value -= 2.0
    return value


def _skill_blind_value(adventurer_id: str, class_name: str, class_skill_id: str, primary_weapon_id: str) -> float:
    profile = ADVENTURER_AI[adventurer_id]
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    tags = CLASS_SKILL_TAGS.get(class_skill_id, set())
    value = BLIND_SKILL_PRIOR.get(class_skill_id, 0.0)
    value += skill_preference_score(profile, class_name, class_skill_id) * 0.8
    if weapon.kind == "ranged" and "ranged" in tags:
        value += 2.5
    if weapon.kind == "magic" and "magic" in tags:
        value += 2.5
    if weapon.kind == "melee" and "melee" in tags:
        value += 2.5
    if "bonus_action" in tags and {"tempo_engine", "bonus_action_user", "backline_reach"} & set(profile.role_tags):
        value += 2.0
    if "anti_status" in tags and {"healer", "guard_support"} & set(profile.role_tags):
        value += 2.0
    if class_skill_id == "vigilant":
        value -= 3.0
    return value


def _artifact_blind_value(adventurer_id: str, class_name: str, primary_weapon_id: str, artifact_id: Optional[str]) -> float:
    if artifact_id is None:
        return 0.0
    profile = ADVENTURER_AI[adventurer_id]
    roles = set(profile.role_tags)
    artifact_tags = ARTIFACT_TAGS.get(artifact_id, set())
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    value = _artifact_prior(artifact_id)
    value += artifact_preference_score(profile, artifact_id) * 0.7
    if artifact_id == "arcane_hourglass":
        value -= 6.0
    if artifact_id in ROLE_ARTIFACT_HINTS.get("fragile", set()) and "fragile" in roles:
        value += 4.0
    if artifact_id in ROLE_ARTIFACT_HINTS.get("primary_tank", set()) and {"primary_tank", "anti_burst"} & roles:
        value += 4.0
    if artifact_id in ROLE_ARTIFACT_HINTS.get("healer", set()) and {"healer", "guard_support", "carry_support"} & roles:
        value += 4.0
    if artifact_id in ROLE_ARTIFACT_HINTS.get("burst_finisher", set()) and {"burst_finisher", "frontline_breaker"} & roles:
        value += 4.0
    if artifact_id in ROLE_ARTIFACT_HINTS.get("backline_reach", set()) and {"backline_reach", "ranged_pressure"} & roles:
        value += 3.5
    if artifact_id in ROLE_ARTIFACT_HINTS.get("tempo_engine", set()) and {"tempo_engine", "bonus_action_user", "weapon_switch_user"} & roles:
        value += 3.0
    if class_name == "Ranger" and artifact_id == "soaring_crown":
        value += 3.0
    if class_name == "Mage" and artifact_id in {"paradox_rings", "magic_mirror", "last_prism"}:
        value += 2.5
    if class_name == "Cleric" and artifact_id in {"fading_diadem", "holy_grail", "iron_rosary", "philosophers_stone"}:
        value += 2.5
    if class_name == "Warden" and artifact_id in {"sun_gods_banner", "all_mill"}:
        value += 2.5
    if weapon.kind == "ranged" and artifact_id in {"soaring_crown", "jade_rabbit", "dragons_horn", "bottled_clouds"}:
        value += 2.5
    if weapon.kind == "magic" and artifact_id in {"last_prism", "paradox_rings", "magic_mirror"}:
        value += 2.5
    if weapon.kind == "melee" and artifact_id in {"dire_wolf_spine", "naiads_knife", "red_hood"}:
        value += 2.5
    if "anti_burst" in artifact_tags and "fragile" in roles:
        value += 2.0
    return value


def _artifact_candidates_for(adventurer_id: str, class_name: str, primary_weapon_id: str) -> tuple[Optional[str], ...]:
    compatible = list(compatible_artifact_ids(class_name))
    if not compatible:
        return (None,)
    compatible.sort(
        key=lambda artifact_id: _artifact_blind_value(adventurer_id, class_name, primary_weapon_id, artifact_id),
        reverse=True,
    )
    return tuple(_ordered_unique((None,) + tuple(compatible[:4])))


def _build_generality(adventurer_id: str, class_name: str, primary_weapon_id: str, artifact_id: Optional[str]) -> float:
    profile = ADVENTURER_AI[adventurer_id]
    roles = set(profile.role_tags)
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    value = 0.0
    if weapon.kind in {"ranged", "magic"}:
        value += 4.5
    if {"primary_tank", "frontline_ready", "anti_burst"} & roles:
        value += 4.0
    if {"healer", "guard_support", "carry_support"} & roles:
        value += 4.0
    if {"backline_reach", "ranged_pressure", "spotlight_enabler"} & roles:
        value += 4.0
    if class_name == "Cleric":
        value += 2.5
    if class_name == "Rogue":
        value += 2.0
    if class_name == "Mage":
        value -= 1.5
    if "setup_dependent" in roles:
        value -= 2.5
    if "high_variance" in roles:
        value -= 2.0
    if artifact_id == "arcane_hourglass":
        value -= 5.0
    return value


def _build_role_coherence(adventurer_id: str, class_name: str, class_skill_id: str, primary_weapon_id: str, artifact_id: Optional[str]) -> float:
    profile = ADVENTURER_AI[adventurer_id]
    roles = set(profile.role_tags)
    weapon = _weapon_def(adventurer_id, primary_weapon_id)
    skill_tags = CLASS_SKILL_TAGS.get(class_skill_id, set())
    artifact_tags = ARTIFACT_TAGS.get(artifact_id, set()) if artifact_id is not None else set()
    value = 0.0
    if class_name in profile.preferred_classes:
        value += 4.5
    if primary_weapon_id in _weapon_order_for(adventurer_id)[:1]:
        value += 4.5
    value += weapon_preference_score(profile, primary_weapon_id) * 0.25
    value += skill_preference_score(profile, class_name, class_skill_id) * 0.30
    value += artifact_preference_score(profile, artifact_id) * 0.22 if artifact_id is not None else 0.0
    if class_name == "Warden" and {"primary_tank", "anti_burst", "frontline_ready"} & roles:
        value += 3.0
    if class_name == "Fighter" and {"burst_finisher", "frontline_breaker", "bruiser"} & roles:
        value += 3.0
    if class_name == "Ranger" and {"backline_reach", "ranged_pressure", "spotlight_enabler"} & roles:
        value += 3.0
    if class_name == "Rogue" and {"tempo_engine", "bonus_action_user", "anti_caster", "backline_reach"} & roles:
        value += 3.0
    if class_name == "Cleric" and {"healer", "guard_support", "carry_support"} & roles:
        value += 3.0
    if class_name == "Mage" and {"magic_carry", "spell_loop", "shock_engine", "anti_caster"} & roles:
        value += 3.0
    if weapon.kind == "ranged" and ("ranged" in skill_tags or class_name == "Ranger"):
        value += 2.5
    if weapon.kind == "magic" and ("magic" in skill_tags or class_name == "Mage"):
        value += 2.5
    if weapon.kind == "melee" and ("melee" in skill_tags or class_name == "Fighter"):
        value += 2.5
    if "anti_burst" in artifact_tags and "fragile" in roles:
        value += 2.0
    if "sustain" in artifact_tags and {"healer", "guard_support", "carry_support"} & roles:
        value += 2.0
    if "reach" in artifact_tags and {"backline_reach", "ranged_pressure"} & roles:
        value += 2.0
    return value


def _blind_build_score(
    adventurer_id: str,
    class_name: str,
    class_skill_id: str,
    primary_weapon_id: str,
    artifact_id: Optional[str],
    party_ids: tuple[str, ...],
) -> float:
    profile = ADVENTURER_AI[adventurer_id]
    value = profile.base_power * 0.54
    value += BLIND_ADVENTURER_PRIOR.get(adventurer_id, 0.0)
    value += profile.reliability * 0.18
    value -= max(0.0, profile.complexity - 72.0) * 0.15
    value += BLIND_CLASS_PRIOR.get(class_name, 0.0) * 1.1
    value += _class_claim_value(adventurer_id, class_name, party_ids)
    value += _weapon_blind_value(adventurer_id, primary_weapon_id)
    value += _skill_blind_value(adventurer_id, class_name, class_skill_id, primary_weapon_id)
    value += _artifact_blind_value(adventurer_id, class_name, primary_weapon_id, artifact_id)
    value += _build_generality(adventurer_id, class_name, primary_weapon_id, artifact_id)
    value += _build_role_coherence(adventurer_id, class_name, class_skill_id, primary_weapon_id, artifact_id)
    return value


def generate_plausible_blind_builds(
    adventurer_id: str,
    party_ids: tuple[str, ...],
    *,
    expanded: bool = False,
) -> tuple[QuestBlindBuild, ...]:
    classes = _class_options_for(adventurer_id)
    if not expanded:
        classes = classes[:5]
    candidate_by_class: dict[str, list[QuestBlindBuild]] = {}
    for class_name in classes:
        builds_for_class: list[QuestBlindBuild] = []
        skill_ids = _skill_order_for_class(adventurer_id, class_name)
        for primary_weapon_id in _weapon_order_for(adventurer_id)[:2]:
            artifact_ids = _artifact_candidates_for(adventurer_id, class_name, primary_weapon_id)
            for class_skill_id in skill_ids[:3]:
                for artifact_id in artifact_ids:
                    score = _blind_build_score(
                        adventurer_id,
                        class_name,
                        class_skill_id,
                        primary_weapon_id,
                        artifact_id,
                        party_ids,
                    )
                    builds_for_class.append(
                        QuestBlindBuild(
                            adventurer_id=adventurer_id,
                            class_name=class_name,
                            class_skill_id=class_skill_id,
                            primary_weapon_id=primary_weapon_id,
                            artifact_id=artifact_id,
                            score=score,
                            blind_tags=_base_blind_tags(
                                adventurer_id,
                                class_name,
                                class_skill_id,
                                primary_weapon_id,
                                artifact_id,
                            ),
                        )
                    )
        builds_for_class.sort(key=lambda build: build.score, reverse=True)
        keep = 2 if _generic_class_affinity(adventurer_id, class_name) >= 10.0 else 1
        candidate_by_class[class_name] = builds_for_class[:keep]
    merged: list[QuestBlindBuild] = []
    for class_name in classes:
        merged.extend(candidate_by_class.get(class_name, []))
    merged.sort(key=lambda build: build.score, reverse=True)
    unique_keys = set()
    unique_builds: list[QuestBlindBuild] = []
    for build in merged:
        key = (build.class_name, build.class_skill_id, build.primary_weapon_id, build.artifact_id)
        if key in unique_keys:
            continue
        unique_keys.add(key)
        unique_builds.append(build)
    return tuple(unique_builds[:12 if expanded else 10])


def _package_member_map(package: QuestLoadoutPackage) -> dict[str, QuestBlindBuild]:
    return {member.adventurer_id: member for member in package.members}


def _trio_style_scores(builds: tuple[QuestBlindBuild, ...]) -> dict[str, float]:
    adventurer_ids = tuple(build.adventurer_id for build in builds)
    styles = dict(team_style_scores(adventurer_ids))
    for build in builds:
        tags = set(build.blind_tags)
        if {"backline_reach", "reach", "ranged_pressure", "magic_pressure"} & tags:
            styles["backline_pressure"] = styles.get("backline_pressure", 0.0) + 2.5
        if {"healer", "guard_support", "anti_burst", "sustain", "guard", "cleanse"} & tags:
            styles["sustain"] = styles.get("sustain", 0.0) + 2.2
        if {"shock_engine", "root_enabler", "anti_caster", "taunt", "anti_guard", "spotlight_enabler"} & tags:
            styles["control"] = styles.get("control", 0.0) + 2.0
        if {"burst_finisher", "frontline_breaker", "damage", "burst"} & tags:
            styles["burst"] = styles.get("burst", 0.0) + 2.0
        if {"tempo_engine", "bonus_action", "switch", "resource", "spell_tempo", "tempo"} & tags:
            styles["tempo"] = styles.get("tempo", 0.0) + 1.8
        if build.class_name == "Warden":
            styles["frontline"] = styles.get("frontline", 0.0) + 2.2
        if build.class_name == "Cleric":
            styles["sustain"] = styles.get("sustain", 0.0) + 1.6
        if build.class_name == "Ranger":
            styles["backline_pressure"] = styles.get("backline_pressure", 0.0) + 1.2
        if build.class_name == "Mage":
            styles["control"] = styles.get("control", 0.0) + 0.8
        if "fragile" in tags:
            styles["fragility"] = styles.get("fragility", 0.0) + 1.6
    return styles


def _formation_fit(build: QuestBlindBuild, slot: str) -> float:
    profile = ADVENTURER_AI[build.adventurer_id]
    weapon = _weapon_def(build.adventurer_id, build.primary_weapon_id)
    base_speed = ADVENTURERS_BY_ID[build.adventurer_id].speed - (30 if slot != SLOT_FRONT else 0)
    roles = set(profile.role_tags)
    value = profile.position_scores[slot] * 0.22
    if slot == SLOT_FRONT and {"primary_tank", "frontline_ready", "anti_burst", "bruiser"} & roles:
        value += 7.0
    if slot == SLOT_FRONT and build.class_name == "Warden":
        value += 3.0
    if slot == SLOT_FRONT and weapon.kind == "melee":
        value += 4.0
    if slot == SLOT_FRONT and weapon.kind == "ranged" and "primary_tank" not in roles and "frontline_ready" not in roles:
        value -= 6.0
    if slot != SLOT_FRONT and weapon.kind == "melee" and "melee_reach" not in roles and "backline_reach" not in roles:
        value -= 10.0
    if slot == SLOT_BACK_RIGHT and ("fragile" in roles or "tempo_engine" in roles or "magic_carry" in roles):
        value += 4.0
    if slot == SLOT_BACK_LEFT and profile.position_scores[SLOT_FRONT] >= 72:
        value += 4.0
    if slot != SLOT_FRONT and {"tempo_engine", "bonus_action_user", "backline_reach"} & roles and base_speed < 34:
        value -= 4.0
    return value


def _coverage_score(builds: tuple[QuestBlindBuild, ...]) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    adventurer_ids = tuple(build.adventurer_id for build in builds)
    styles = _trio_style_scores(builds)
    warnings: list[str] = []
    value = 0.0
    if styles.get("frontline", 0.0) >= 16.0:
        value += 12.0
    else:
        warnings.append("Weak frontline plan.")
        value -= 12.0
    if styles.get("backline_pressure", 0.0) >= 11.0:
        value += 10.0
    else:
        warnings.append("Limited backline pressure.")
        value -= 12.0
    if styles.get("sustain", 0.0) >= 9.0:
        value += 8.0
    elif styles.get("control", 0.0) >= 12.0:
        value += 3.0
    else:
        warnings.append("Low sustain or stabilization.")
        value -= 8.0
    if styles.get("burst", 0.0) >= 10.0 or styles.get("control", 0.0) >= 13.0:
        value += 8.0
    else:
        warnings.append("No clear conversion route.")
        value -= 10.0
    if styles.get("fragility", 0.0) > styles.get("frontline", 0.0) + styles.get("sustain", 0.0) * 0.7:
        warnings.append("Fragile into focused pressure.")
        value -= 6.0
    archetype_bonus, archetypes = team_archetype_bonus(adventurer_ids)
    value += archetype_bonus * 0.6
    value += plan_reliability_score(adventurer_ids)
    return value, tuple(dict.fromkeys(warnings)), archetypes


def summarize_trio_from_package(package: QuestLoadoutPackage, team_ids: tuple[str, ...]) -> QuestTrioProfile:
    member_map = _package_member_map(package)
    builds = tuple(member_map[adventurer_id] for adventurer_id in team_ids)
    best_loadout: TeamLoadout | None = None
    best_score = float("-inf")
    best_tags: tuple[str, ...] = ()
    styles = _trio_style_scores(builds)
    for slot_assignment in permutations(SLOT_ORDER, len(builds)):
        members = tuple(
            MemberBuild(
                adventurer_id=build.adventurer_id,
                slot=slot,
                class_name=build.class_name,
                class_skill_id=build.class_skill_id,
                primary_weapon_id=build.primary_weapon_id,
                artifact_id=build.artifact_id,
                score=build.score,
            )
            for build, slot in zip(builds, slot_assignment)
        )
        ordered_members = tuple(sorted(members, key=lambda member: SLOT_ORDER.index(member.slot)))
        formation_score = 0.0
        combined_tags = set()
        for build, slot in zip(builds, slot_assignment):
            formation_score += _formation_fit(build, slot)
            combined_tags.update(build.blind_tags)
        pair_bonus = 0.0
        for left_id, right_id in combinations(team_ids, 2):
            pair_bonus += pair_synergy_value(left_id, right_id)
        coverage_score, warnings, archetypes = _coverage_score(builds)
        total = sum(build.score for build in builds) * 0.44
        total += pair_bonus + formation_score + coverage_score
        total += styles.get("frontline", 0.0) * 0.24
        total += styles.get("backline_pressure", 0.0) * 0.28
        total += styles.get("sustain", 0.0) * 0.22
        total += styles.get("control", 0.0) * 0.24
        total += styles.get("burst", 0.0) * 0.24
        total += styles.get("tempo", 0.0) * 0.14
        total -= max(0.0, styles.get("fragility", 0.0) - (styles.get("frontline", 0.0) + styles.get("sustain", 0.0))) * 0.35
        if total > best_score:
            best_score = total
            best_tags = tuple(sorted(combined_tags))
            best_loadout = TeamLoadout(
                members=ordered_members,
                score=total,
                archetypes=tuple(archetypes),
                warnings=warnings,
            )
    if best_loadout is None:
        raise ValueError(f"Could not build trio profile for {team_ids}.")
    return QuestTrioProfile(
        team_ids=team_ids,
        loadout=best_loadout,
        score=best_score,
        tag_set=best_tags,
        styles=tuple(sorted(styles.items())),
    )


def _package_diversity_bonus(trio_profiles: list[QuestTrioProfile]) -> float:
    if not trio_profiles:
        return -30.0
    aggressive = 0.0
    stable = 0.0
    control = 0.0
    for profile in trio_profiles:
        styles = dict(profile.styles)
        if styles.get("burst", 0.0) + styles.get("backline_pressure", 0.0) >= 22.0:
            aggressive = max(aggressive, profile.score)
        if styles.get("frontline", 0.0) + styles.get("sustain", 0.0) >= 24.0:
            stable = max(stable, profile.score)
        if styles.get("control", 0.0) + styles.get("sustain", 0.0) >= 22.0:
            control = max(control, profile.score)
    bonus = 0.0
    if aggressive > 0:
        bonus += aggressive * 0.08
    if stable > 0:
        bonus += stable * 0.08
    if control > 0:
        bonus += control * 0.08
    if aggressive <= 0:
        bonus -= 6.0
    if stable <= 0:
        bonus -= 8.0
    if control <= 0:
        bonus -= 5.0
    return bonus


def _score_package(members: tuple[QuestBlindBuild, ...]) -> tuple[float, float, tuple[str, ...]]:
    individual_sum = sum(member.score for member in members)
    warnings: list[str] = []
    classes = [member.class_name for member in members]
    if len(classes) != len(set(classes)):
        return -10_000.0, -10_000.0, ("Duplicate class assignments.",)
    artifacts = [member.artifact_id for member in members if member.artifact_id is not None]
    if len(artifacts) != len(set(artifacts)):
        return -10_000.0, -10_000.0, ("Duplicate artifact assignments.",)
    temp_package = QuestLoadoutPackage(offer_ids=tuple(member.adventurer_id for member in members), members=members, score=0.0, trio_option_value=0.0, warnings=())
    trio_profiles = [summarize_trio_from_package(temp_package, trio) for trio in combinations(temp_package.offer_ids, 3)]
    trio_scores = sorted((profile.score for profile in trio_profiles), reverse=True)
    top_value = 0.0
    for index, score in enumerate(trio_scores[:6]):
        top_value += score * (0.60 - index * 0.08)
    diversity_bonus = _package_diversity_bonus(trio_profiles)
    package_score = individual_sum + top_value + diversity_bonus
    if trio_scores and trio_scores[0] < 100.0:
        warnings.append("No standout trio available.")
        package_score -= 12.0
    if len([score for score in trio_scores if score >= 120.0]) < 3:
        warnings.append("Limited future pick flexibility.")
        package_score -= 8.0
    return package_score, top_value, tuple(warnings)


def _roster_quick_score(roster_ids: tuple[str, ...]) -> float:
    value = 0.0
    premium_class_claims: dict[str, int] = {class_name: 0 for class_name in ALL_CLASSES}
    role_union: set[str] = set()
    fragility_count = 0
    ranged_magic_count = 0
    for adventurer_id in roster_ids:
        profile = ADVENTURER_AI[adventurer_id]
        roles = set(profile.role_tags)
        role_union.update(roles)
        value += profile.base_power * 0.42
        value += BLIND_ADVENTURER_PRIOR.get(adventurer_id, 0.0)
        value += profile.reliability * 0.14
        if "fragile" in roles:
            fragility_count += 1
        if any(weapon.kind in {"ranged", "magic"} for weapon in ADVENTURERS_BY_ID[adventurer_id].signature_weapons):
            ranged_magic_count += 1
        for class_name in _class_options_for(adventurer_id)[:2]:
            premium_class_claims[class_name] += 1

    if {"primary_tank", "anti_burst", "frontline_ready", "stall_anchor"} & role_union:
        value += 16.0
    else:
        value -= 18.0
    if {"healer", "guard_support", "carry_support"} & role_union:
        value += 14.0
    else:
        value -= 12.0
    if {"backline_reach", "ranged_pressure", "spotlight_enabler", "magic_carry"} & role_union:
        value += 12.0
    else:
        value -= 12.0
    if {"root_enabler", "shock_engine", "burn_enabler", "expose_enabler", "anti_caster"} & role_union:
        value += 10.0
    if {"burst_finisher", "frontline_breaker", "status_payoff"} & role_union:
        value += 10.0
    if {"tempo_engine", "bonus_action_user", "weapon_switch_user", "swap_engine"} & role_union:
        value += 8.0

    if ranged_magic_count >= 3:
        value += 6.0
    elif ranged_magic_count <= 1:
        value -= 8.0

    if fragility_count >= 4:
        value -= 12.0
    elif fragility_count == 3:
        value -= 5.0

    for class_name in ("Ranger", "Rogue", "Fighter"):
        value += min(2, premium_class_claims.get(class_name, 0)) * 3.0
    if premium_class_claims.get("Warden", 0) <= 0:
        value -= 8.0
    if premium_class_claims.get("Cleric", 0) <= 0:
        value -= 7.0
    if premium_class_claims.get("Mage", 0) <= 0:
        value -= 2.0
    return value


def _partial_package_score(builds: tuple[QuestBlindBuild, ...]) -> float:
    value = sum(build.score for build in builds)
    classes = {build.class_name for build in builds}
    value += len(classes) * 3.5
    combined_tags = set()
    for build in builds:
        combined_tags.update(build.blind_tags)
    if {"primary_tank", "frontline_ready", "anti_burst", "frontline"} & combined_tags:
        value += 5.0
    if {"healer", "guard_support", "sustain", "cleanse"} & combined_tags:
        value += 4.0
    if {"backline_reach", "reach", "ranged_pressure", "magic_pressure"} & combined_tags:
        value += 4.0
    if {"burst_finisher", "frontline_breaker", "damage"} & combined_tags:
        value += 3.0
    return value


def _build_package(adventurer_ids: tuple[str, ...], *, expanded: bool = False) -> QuestLoadoutPackage:
    candidate_builds = {
        adventurer_id: generate_plausible_blind_builds(adventurer_id, adventurer_ids, expanded=expanded)
        for adventurer_id in adventurer_ids
    }
    order = sorted(
        adventurer_ids,
        key=lambda adventurer_id: (len(candidate_builds[adventurer_id]), -ADVENTURER_AI[adventurer_id].base_power),
    )
    states: list[tuple[tuple[QuestBlindBuild, ...], frozenset[str], frozenset[str], float]] = [
        (tuple(), frozenset(), frozenset(), 0.0)
    ]
    for adventurer_id in order:
        next_states: list[tuple[tuple[QuestBlindBuild, ...], frozenset[str], frozenset[str], float]] = []
        for chosen_builds, used_classes, used_artifacts, _score in states:
            for build in candidate_builds[adventurer_id]:
                if build.class_name in used_classes:
                    continue
                if build.artifact_id is not None and build.artifact_id in used_artifacts:
                    continue
                new_builds = chosen_builds + (build,)
                new_used_classes = used_classes | {build.class_name}
                new_used_artifacts = used_artifacts | ({build.artifact_id} if build.artifact_id is not None else set())
                heuristic = _partial_package_score(new_builds)
                next_states.append((new_builds, frozenset(new_used_classes), frozenset(new_used_artifacts), heuristic))
        if not next_states:
            raise ValueError(f"Could not allocate blind quest loadouts for {adventurer_ids}.")
        next_states.sort(key=lambda item: item[3], reverse=True)
        states = next_states[:BLIND_BEAM_WIDTH]
    best_package: QuestLoadoutPackage | None = None
    best_score = float("-inf")
    for chosen_builds, _used_classes, _used_artifacts, _heuristic in states:
        ordered_builds = tuple(sorted(chosen_builds, key=lambda build: adventurer_ids.index(build.adventurer_id)))
        package_score, trio_option_value, warnings = _score_package(ordered_builds)
        if package_score > best_score:
            best_score = package_score
            best_package = QuestLoadoutPackage(
                offer_ids=adventurer_ids,
                members=ordered_builds,
                score=package_score,
                trio_option_value=trio_option_value,
                warnings=warnings,
            )
    if best_package is None:
        raise ValueError(f"Could not finalize blind quest loadout package for {adventurer_ids}.")
    return best_package


def _build_package_exact(adventurer_ids: tuple[str, ...]) -> QuestLoadoutPackage:
    candidate_builds = {
        adventurer_id: generate_plausible_blind_builds(adventurer_id, adventurer_ids, expanded=True)
        for adventurer_id in adventurer_ids
    }
    order = sorted(
        adventurer_ids,
        key=lambda adventurer_id: (len(candidate_builds[adventurer_id]), -ADVENTURER_AI[adventurer_id].base_power),
    )

    best_package: QuestLoadoutPackage | None = None
    best_score = float("-inf")

    def search(
        index: int,
        chosen_builds: tuple[QuestBlindBuild, ...],
        used_classes: frozenset[str],
        used_artifacts: frozenset[str],
    ) -> None:
        nonlocal best_package, best_score
        if index >= len(order):
            ordered_builds = tuple(sorted(chosen_builds, key=lambda build: adventurer_ids.index(build.adventurer_id)))
            package_score, trio_option_value, warnings = _score_package(ordered_builds)
            if package_score > best_score:
                best_score = package_score
                best_package = QuestLoadoutPackage(
                    offer_ids=adventurer_ids,
                    members=ordered_builds,
                    score=package_score,
                    trio_option_value=trio_option_value,
                    warnings=warnings,
                )
            return

        adventurer_id = order[index]
        for build in candidate_builds[adventurer_id]:
            if build.class_name in used_classes:
                continue
            if build.artifact_id is not None and build.artifact_id in used_artifacts:
                continue
            search(
                index + 1,
                chosen_builds + (build,),
                frozenset(set(used_classes) | {build.class_name}),
                frozenset(set(used_artifacts) | ({build.artifact_id} if build.artifact_id is not None else set())),
            )

    search(0, tuple(), frozenset(), frozenset())
    if best_package is None:
        raise ValueError(f"Could not exactly allocate blind quest loadouts for {adventurer_ids}.")
    return best_package


@lru_cache(maxsize=512)
def _assign_blind_quest_loadouts_cached(adventurer_ids: tuple[str, ...]) -> QuestLoadoutPackage:
    ids = _sorted_ids(adventurer_ids)
    try:
        return _build_package(ids, expanded=False)
    except ValueError:
        try:
            return _build_package(ids, expanded=True)
        except ValueError:
            return _build_package_exact(ids)


def assign_blind_quest_loadouts(adventurer_ids: tuple[str, ...] | list[str]) -> QuestLoadoutPackage:
    ids = _sorted_ids(tuple(adventurer_ids))
    if len(ids) < 3:
        raise ValueError("Quest blind loadout assignment requires at least 3 unique adventurers.")
    return _assign_blind_quest_loadouts_cached(ids)


@lru_cache(maxsize=512)
def _choose_blind_quest_roster_from_offer_cached(
    offered: tuple[str, ...],
    roster_size: int,
    locked: tuple[str, ...],
) -> QuestLoadoutPackage:
    if len(offered) < roster_size:
        raise ValueError(f"Quest roster choice requires at least {roster_size} unique adventurers.")
    if any(adventurer_id not in offered for adventurer_id in locked):
        raise ValueError("Quest roster choice cannot lock adventurers that are not in the offer.")
    if len(locked) > roster_size:
        raise ValueError("Quest roster choice has more locked adventurers than roster slots.")

    candidate_rosters: list[tuple[tuple[str, ...], float]] = []
    for roster_ids in combinations(offered, roster_size):
        if any(adventurer_id not in roster_ids for adventurer_id in locked):
            continue
        candidate_rosters.append((roster_ids, _roster_quick_score(roster_ids)))
    if not candidate_rosters:
        raise ValueError(f"Quest roster choice could not solve an offer of {len(offered)} adventurers.")

    candidate_rosters.sort(key=lambda item: item[1], reverse=True)
    top_score = candidate_rosters[0][1]
    narrowed = [
        roster_ids
        for roster_ids, score in candidate_rosters
        if top_score - score <= 22.0
    ][:ROSTER_SUBSET_KEEP]
    if not narrowed:
        narrowed = [candidate_rosters[0][0]]

    best_package: QuestLoadoutPackage | None = None
    best_score = float("-inf")
    for roster_ids in narrowed:
        package = assign_blind_quest_loadouts(roster_ids)
        if package.score > best_score:
            best_score = package.score
            best_package = package
    if best_package is None:
        raise ValueError(f"Quest roster choice could not solve an offer of {len(offered)} adventurers.")
    return best_package


def choose_blind_quest_roster_from_offer(
    offer_ids: tuple[str, ...] | list[str],
    roster_size: int = 6,
    locked_ids: tuple[str, ...] | list[str] = (),
) -> QuestLoadoutPackage:
    offered = _sorted_ids(tuple(offer_ids))
    locked = _sorted_ids(tuple(locked_ids))
    return _choose_blind_quest_roster_from_offer_cached(offered, roster_size, locked)
