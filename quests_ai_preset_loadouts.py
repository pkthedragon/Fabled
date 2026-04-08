from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from quests_ruleset_data import ADVENTURERS_BY_ID, ARTIFACTS, CLASS_SKILLS


@dataclass(frozen=True)
class LoadoutPreset:
    adventurer_id: str
    primary_weapon_id: str
    class_name: str
    class_skill_id: str
    artifact_id: Optional[str]
    rank: int


_PRESET_ROWS = {
    "red_blanchette": (
        ("enchanted_shackles", "Fighter", "martial", "dire_wolf_spine"),
        ("enchanted_shackles", "Fighter", "vanguard", "blood_diamond"),
        ("stomach_splitter", "Mage", "arcane", "last_prism"),
        ("stomach_splitter", "Cleric", "medic", "philosophers_stone"),
        ("enchanted_shackles", "Warden", "bulwark", "tarnhelm"),
    ),
    "little_jack": (
        ("giants_harp", "Mage", "arcane", "last_prism"),
        ("giants_harp", "Mage", "archmage", "glass_slipper"),
        ("skyfall", "Fighter", "martial", "dire_wolf_spine"),
        ("skyfall", "Fighter", "vanguard", "blood_diamond"),
        ("giants_harp", "Warden", "bulwark", "paradox_rings"),
    ),
    "witch_hunter_gretel": (
        ("hot_mitts", "Fighter", "martial", "dire_wolf_spine"),
        ("hot_mitts", "Fighter", "vanguard", "red_hood"),
        ("crumb_shot", "Ranger", "deadeye", "soaring_crown"),
        ("crumb_shot", "Ranger", "armed", "suspicious_eye"),
        ("hot_mitts", "Cleric", "healer", "misericorde"),
    ),
    "lucky_constantine": (
        ("fortuna", "Rogue", "assassin", "swan_cloak"),
        ("fortuna", "Rogue", "covert", "enchanted_lamp"),
        ("fortuna", "Fighter", "martial", "naiads_knife"),
        ("cat_o_nine", "Rogue", "assassin", "black_torch"),
        ("fortuna", "Warden", "vigilant", "bluebeards_key"),
    ),
    "hunold_the_piper": (
        ("golden_fiddle", "Mage", "arcane", "last_prism"),
        ("golden_fiddle", "Mage", "archmage", "glass_slipper"),
        ("lightning_rod", "Ranger", "deadeye", "soaring_crown"),
        ("lightning_rod", "Ranger", "armed", "jade_rabbit"),
        ("golden_fiddle", "Rogue", "assassin", "selkies_skin"),
    ),
    "sir_roland": (
        ("pure_silver_shield", "Warden", "bulwark", "sun_gods_banner"),
        ("pure_silver_shield", "Warden", "vigilant", "starskin_veil"),
        ("pure_gold_lance", "Fighter", "martial", "dragons_horn"),
        ("pure_gold_lance", "Fighter", "vanguard", "blood_diamond"),
        ("pure_silver_shield", "Cleric", "medic", "holy_grail"),
    ),
    "porcus_iii": (
        ("crafty_wall", "Warden", "bulwark", "sun_gods_banner"),
        ("crafty_wall", "Warden", "vigilant", "nettle_smock"),
        ("mortar_mortar", "Ranger", "deadeye", "all_mill"),
        ("mortar_mortar", "Ranger", "armed", "cornucopia"),
        ("crafty_wall", "Cleric", "healer", "golden_fleece"),
    ),
    "lady_of_reflections": (
        ("lantern_of_avalon", "Mage", "arcane", "last_prism"),
        ("lantern_of_avalon", "Mage", "archmage", "glass_slipper"),
        ("excalibur", "Fighter", "martial", "naiads_knife"),
        ("lantern_of_avalon", "Rogue", "covert", "swan_cloak"),
        ("lantern_of_avalon", "Cleric", "medic", "magic_mirror"),
    ),
    "ashen_ella": (
        ("obsidian_slippers", "Mage", "arcane", "last_prism"),
        ("obsidian_slippers", "Mage", "arcane", "cursed_spindle"),
        ("obsidian_slippers", "Rogue", "covert", "selkies_skin"),
        ("obsidian_slippers", "Rogue", "assassin", "glass_slipper"),
        ("obsidian_slippers", "Fighter", "vanguard", "blood_diamond"),
    ),
    "march_hare": (
        ("stitch_in_time", "Mage", "arcane", "last_prism"),
        ("cracked_stopwatch", "Mage", "archmage", "glass_slipper"),
        ("stitch_in_time", "Rogue", "covert", "glass_slipper"),
        ("stitch_in_time", "Cleric", "medic", "philosophers_stone"),
        ("cracked_stopwatch", "Warden", "bulwark", "paradox_rings"),
    ),
    "briar_rose": (
        ("thorn_snare", "Ranger", "deadeye", "soaring_crown"),
        ("spindle_bow", "Ranger", "deadeye", "jade_rabbit"),
        ("thorn_snare", "Ranger", "armed", "seeking_yarn"),
        ("thorn_snare", "Rogue", "assassin", "selkies_skin"),
        ("spindle_bow", "Cleric", "medic", "walking_abode"),
    ),
    "wayward_humbert": (
        ("convicted_shotgun", "Ranger", "deadeye", "soaring_crown"),
        ("convicted_shotgun", "Ranger", "armed", "soaring_crown"),
        ("pallid_musket", "Ranger", "armed", "jade_rabbit"),
        ("convicted_shotgun", "Rogue", "assassin", "seeking_yarn"),
        ("pallid_musket", "Cleric", "healer", "walking_abode"),
    ),
    "robin_hooded_avenger": (
        ("the_flock", "Ranger", "deadeye", "soaring_crown"),
        ("the_flock", "Ranger", "armed", "bottled_clouds"),
        ("kingmaker", "Fighter", "martial", "dragons_horn"),
        ("kingmaker", "Rogue", "assassin", "black_torch"),
        ("the_flock", "Cleric", "medic", "walking_abode"),
    ),
    "matchbox_liesl": (
        ("eternal_torch", "Cleric", "healer", "iron_rosary"),
        ("eternal_torch", "Cleric", "medic", "fading_diadem"),
        ("eternal_torch", "Mage", "arcane", "philosophers_stone"),
        ("matchsticks", "Ranger", "deadeye", "suspicious_eye"),
        ("eternal_torch", "Mage", "archmage", "goose_quill"),
    ),
    "the_good_beast": (
        ("dinner_bell", "Cleric", "healer", "iron_rosary"),
        ("dinner_bell", "Cleric", "medic", "fading_diadem"),
        ("dinner_bell", "Mage", "arcane", "philosophers_stone"),
        ("rosebush_sword", "Fighter", "martial", "red_hood"),
        ("dinner_bell", "Warden", "bulwark", "starskin_veil"),
    ),
    "the_green_knight": (
        ("the_search", "Ranger", "deadeye", "soaring_crown"),
        ("the_search", "Ranger", "armed", "cornucopia"),
        ("the_answer", "Fighter", "martial", "dragons_horn"),
        ("the_answer", "Warden", "vigilant", "nettle_smock"),
        ("the_search", "Rogue", "covert", "seeking_yarn"),
    ),
    "rapunzel_the_golden": (
        ("golden_snare", "Fighter", "martial", "dragons_horn"),
        ("golden_snare", "Fighter", "vanguard", "blood_diamond"),
        ("ivory_tower", "Warden", "bulwark", "golden_fleece"),
        ("ivory_tower", "Cleric", "healer", "holy_grail"),
        ("golden_snare", "Warden", "vigilant", "starskin_veil"),
    ),
    "pinocchio_cursed_puppet": (
        ("string_cutter", "Mage", "arcane", "last_prism"),
        ("string_cutter", "Mage", "archmage", "glass_slipper"),
        ("wooden_club", "Fighter", "martial", "dire_wolf_spine"),
        ("string_cutter", "Cleric", "healer", "philosophers_stone"),
        ("string_cutter", "Rogue", "covert", "selkies_skin"),
    ),
    "rumpelstiltskin": (
        ("devils_contract", "Mage", "arcane", "last_prism"),
        ("devils_contract", "Mage", "archmage", "glass_slipper"),
        ("spinning_wheel", "Ranger", "deadeye", "soaring_crown"),
        ("spinning_wheel", "Ranger", "armed", "jade_rabbit"),
        ("devils_contract", "Rogue", "assassin", "cursed_spindle"),
    ),
    "sea_wench_asha": (
        ("frost_scepter", "Mage", "arcane", "last_prism"),
        ("mirror_blade", "Mage", "arcane", "philosophers_stone"),
        ("frost_scepter", "Mage", "archmage", "glass_slipper"),
        ("frost_scepter", "Cleric", "medic", "magic_mirror"),
        ("mirror_blade", "Rogue", "assassin", "selkies_skin"),
    ),
    "destitute_vasilisa": (
        ("guiding_doll", "Mage", "arcane", "last_prism"),
        ("guiding_doll", "Mage", "archmage", "paradox_rings"),
        ("skull_lantern", "Mage", "arcane", "philosophers_stone"),
        ("guiding_doll", "Cleric", "healer", "iron_rosary"),
        ("skull_lantern", "Warden", "bulwark", "sun_gods_banner"),
    ),
    "ali_baba": (
        ("jar_of_oil", "Mage", "arcane", "cursed_spindle"),
        ("jar_of_oil", "Mage", "archmage", "last_prism"),
        ("thiefs_dagger", "Rogue", "assassin", "swan_cloak"),
        ("thiefs_dagger", "Rogue", "covert", "enchanted_lamp"),
        ("thiefs_dagger", "Fighter", "martial", "naiads_knife"),
    ),
    "maui_sunthief": (
        ("ancestral_warclub", "Warden", "bulwark", "sun_gods_banner"),
        ("ancestral_warclub", "Warden", "vigilant", "golden_fleece"),
        ("whale_jaw_hook", "Fighter", "martial", "dragons_horn"),
        ("whale_jaw_hook", "Fighter", "vanguard", "blood_diamond"),
        ("ancestral_warclub", "Cleric", "healer", "holy_grail"),
    ),
    "kama_the_honeyed": (
        ("sugarcane_bow", "Ranger", "deadeye", "soaring_crown"),
        ("the_stinger", "Ranger", "deadeye", "suspicious_eye"),
        ("sugarcane_bow", "Ranger", "armed", "jade_rabbit"),
        ("the_stinger", "Rogue", "assassin", "seeking_yarn"),
        ("sugarcane_bow", "Cleric", "healer", "walking_abode"),
    ),
    "reynard_lupine_trickster": (
        ("foxfire_bow", "Ranger", "deadeye", "soaring_crown"),
        ("foxfire_bow", "Ranger", "armed", "jade_rabbit"),
        ("fang", "Rogue", "assassin", "swan_cloak"),
        ("fang", "Fighter", "martial", "naiads_knife"),
        ("foxfire_bow", "Rogue", "covert", "seeking_yarn"),
    ),
    "scheherazade_dawns_ransom": (
        ("lamp_of_infinity", "Cleric", "healer", "iron_rosary"),
        ("lamp_of_infinity", "Cleric", "medic", "fading_diadem"),
        ("tome_of_ancients", "Mage", "arcane", "last_prism"),
        ("tome_of_ancients", "Mage", "archmage", "goose_quill"),
        ("lamp_of_infinity", "Warden", "bulwark", "starskin_veil"),
    ),
    "storyweaver_anansi": (
        ("the_pen", "Ranger", "deadeye", "soaring_crown"),
        ("the_pen", "Ranger", "armed", "seeking_yarn"),
        ("the_sword", "Rogue", "assassin", "swan_cloak"),
        ("the_sword", "Fighter", "martial", "naiads_knife"),
        ("the_pen", "Rogue", "covert", "selkies_skin"),
    ),
    "odysseus_the_nobody": (
        ("olivewood_spear", "Fighter", "martial", "dragons_horn"),
        ("olivewood_spear", "Fighter", "vanguard", "dire_wolf_spine"),
        ("beggars_greatbow", "Ranger", "deadeye", "soaring_crown"),
        ("beggars_greatbow", "Ranger", "armed", "jade_rabbit"),
        ("olivewood_spear", "Rogue", "covert", "black_torch"),
    ),
    "witch_of_the_east": (
        ("zephyr", "Mage", "arcane", "last_prism"),
        ("zephyr", "Mage", "archmage", "glass_slipper"),
        ("comet", "Fighter", "martial", "dragons_horn"),
        ("zephyr", "Rogue", "covert", "winged_sandals"),
        ("zephyr", "Warden", "vigilant", "paradox_rings"),
    ),
    "tam_lin_thornbound": (
        ("butterfly_knife", "Warden", "bulwark", "sun_gods_banner"),
        ("butterfly_knife", "Fighter", "martial", "dragons_horn"),
        ("beam_of_light", "Fighter", "martial", "dire_wolf_spine"),
        ("beam_of_light", "Cleric", "healer", "golden_fleece"),
        ("butterfly_knife", "Warden", "vigilant", "bluebeards_key"),
    ),
}


def _build_presets() -> dict[str, tuple[LoadoutPreset, ...]]:
    artifact_ids = {artifact.id for artifact in ARTIFACTS}
    presets: dict[str, tuple[LoadoutPreset, ...]] = {}
    for adventurer_id, rows in _PRESET_ROWS.items():
        entries: list[LoadoutPreset] = []
        adventurer = ADVENTURERS_BY_ID[adventurer_id]
        weapon_ids = {weapon.id for weapon in adventurer.signature_weapons}
        for rank, (weapon_id, class_name, skill_id, artifact_id) in enumerate(rows):
            if weapon_id not in weapon_ids:
                raise ValueError(f"Unknown weapon preset {weapon_id} for {adventurer_id}.")
            if class_name not in CLASS_SKILLS:
                raise ValueError(f"Unknown class preset {class_name} for {adventurer_id}.")
            legal_skill_ids = {skill.id for skill in CLASS_SKILLS[class_name]}
            if skill_id not in legal_skill_ids:
                raise ValueError(f"Illegal skill preset {skill_id} for {adventurer_id} {class_name}.")
            if artifact_id is not None and artifact_id not in artifact_ids:
                raise ValueError(f"Unknown artifact preset {artifact_id} for {adventurer_id}.")
            entries.append(
                LoadoutPreset(
                    adventurer_id=adventurer_id,
                    primary_weapon_id=weapon_id,
                    class_name=class_name,
                    class_skill_id=skill_id,
                    artifact_id=artifact_id,
                    rank=rank,
                )
            )
        presets[adventurer_id] = tuple(entries)
    return presets


AI_LOADOUT_PRESETS = _build_presets()


def presets_for(adventurer_id: str) -> tuple[LoadoutPreset, ...]:
    return AI_LOADOUT_PRESETS.get(adventurer_id, ())

