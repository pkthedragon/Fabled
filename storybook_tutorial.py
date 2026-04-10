from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ruleset_data import ADVENTURERS_BY_ID, ARTIFACTS_BY_ID, CLASS_SKILLS, CLASS_SKILLS_BY_ID, active, passive, stat, status, weapon
from quests_ruleset_logic import (
    NO_CLASS_SKILL,
    create_battle,
    create_team,
    determine_initiative_order,
    get_legal_targets,
    player_num_for_actor,
    queue_bonus_action,
    queue_skip,
    queue_spell,
    queue_strike,
    queue_switch,
    queue_ultimate,
)


TUTORIAL_BASE_GOLD = 1200
TUTORIAL_REWARD_ARTIFACT_IDS = ("holy_grail", "selkies_skin")
TUTORIAL_ARTIFACT_SALE_VALUE = 100
TUTORIAL_COMPLETION_GOLD = len(TUTORIAL_REWARD_ARTIFACT_IDS) * TUTORIAL_ARTIFACT_SALE_VALUE
TUTORIAL_STARTING_GOLD = TUTORIAL_BASE_GOLD + TUTORIAL_COMPLETION_GOLD

TUTORIAL_PLAYER_IDS = (
    "little_jack",
    "matchbox_liesl",
    "porcus_iii",
    "hunold_the_piper",
    "reynard_lupine_trickster",
    "robin_hooded_avenger",
)

TUTORIAL_RECOMMENDED_CLASSES = {
    "little_jack": "Fighter",
    "matchbox_liesl": "Mage",
    "porcus_iii": "Warden",
    "hunold_the_piper": "Ranger",
    "reynard_lupine_trickster": "Rogue",
    "robin_hooded_avenger": "Cleric",
}

TUTORIAL_UNLOCKED_ACTIONS = {
    1: {"strike", "skip"},
    2: {"strike", "spellbook", "skip"},
    3: {"strike", "spellbook", "switch", "skip"},
    4: {"strike", "spellbook", "switch", "skip"},
    5: {"strike", "spellbook", "switch", "swap", "skip"},
    6: {"strike", "spellbook", "switch", "swap", "skip"},
    7: {"strike", "spellbook", "switch", "swap", "skip"},
    8: {"strike", "spellbook", "switch", "swap", "skip"},
    9: {"strike", "spellbook", "switch", "swap", "skip", "ultimate"},
    10: {"strike", "spellbook", "switch", "swap", "skip", "ultimate"},
}

TUTORIAL_LOADOUT_NOTES = {
    1: "Skyfall only. Learn the Strike flow first.",
    2: "Cloudburst lets Jack reach the backline.",
    3: "Click a weapon to make it primary.",
    4: "Classes are visible now. Read the passive bonuses.",
    5: "Position changes Speed and targeting reach.",
    6: "Porcus anchors the frontline for your trio.",
    7: "Pick 3, then choose classes and class skills.",
    8: "Artifacts are live. Attunement only gates the spell.",
    9: "Build to 5 meter, then unleash an Ultimate.",
    10: "Final Test. Bring Burn answers and burst damage.",
}

TUTORIAL_PARTY_SELECT_LINES = {
    7: (
        "Choose exactly 3 adventurers for this lesson.",
        "Each class can only appear once, so think in roles instead of duplicates.",
        "You are setting up for class-skill choice more than raw stats here.",
    ),
    8: (
        "Choose 3 adventurers with artifact attunement in mind.",
        "Artifacts always grant their stat bonus, even when unattuned.",
        "Matching class to attunement is what unlocks the artifact spell.",
    ),
    9: (
        "Choose 3 adventurers that can build Ultimate Meter quickly.",
        "Non-Magic Strikes add 1 meter and non-Ultimate Spells add 2.",
        "Pick a trio that can survive long enough to cash in that meter.",
    ),
    10: (
        "This is the graduation fight. Build a real answer to Burn, healing, and damage caps.",
        "Liesl's Burn protection and any cleansing effects are especially valuable.",
        "A sturdy trio like Liesl, Porcus, and Robin gives you Burn immunity, sustain, and spread pressure.",
        "Burst, layered pressure, and smart target priority matter more than comfort picks.",
    ),
}

TUTORIAL_LOADOUT_LINES = {
    1: (
        "Only Strike is unlocked here.",
        "Jack uses Skyfall only, so focus on the basic action flow.",
    ),
    2: (
        "Spellcast is unlocked.",
        "Cloudburst is the lesson: cast it, then use the empowered Strike to reach Marigold.",
    ),
    3: (
        "Jack's second signature weapon is now visible.",
        "Click the weapon you want as primary. Giant's Harp is your backline answer.",
    ),
    4: (
        "Classes are now visible, but fixed for this lesson.",
        "Notice the HP bonus and passive text on Jack and Liesl before you enter.",
    ),
    5: (
        "Swap is unlocked, so formation matters more now.",
        "Think about whether Liesl wants the frontline Speed and whether Jack can afford the backline penalty.",
    ),
    6: (
        "Porcus anchors your first 3v3 team.",
        "Frontline Porcus protects the backline while the UI starts teaching the full round structure.",
    ),
    7: (
        "Assign unique classes across the trio, then read both class-skill options.",
        "This is the first loadout where your class-skill choice is truly yours.",
    ),
    8: (
        "Artifacts are unlocked in loadout.",
        "Use attunement to decide who should carry each relic, but remember the stat bonus always works.",
    ),
    9: (
        "Ultimate Meter is active now, so load out for tempo and meter building.",
        "Strikes and Spells both matter here. Plan for who will cash in the first Ultimate.",
    ),
    10: (
        "Final Test loadout.",
        "Bring Burn protection or cleansing, plus enough focused damage to push through healing and Anachronism.",
        "Liesl with Matchsticks, Porcus with Wishing Table, and Robin with The Flock make a strong tutorial-clearing plan.",
    ),
}

TUTORIAL_UNIT_CALLOUTS = {
    "tutorial_francis": (
        "Lesson: Francis has more max HP than Jack, so Giant Slayer is active.",
    ),
    "tutorial_bar": (
        "Key Mechanic: Solid Oak cuts the first Strike Bar takes each round by 20%.",
    ),
    "tutorial_marigold": (
        "Key Mechanic: Darts spend Ammo, and Take a Shot restores 40 HP while fully reloading Marigold's primary weapon.",
    ),
    "tutorial_daeny": (
        "Key Mechanic: Daeny is a simple melee attacker with a 100 Power Claws Strike.",
    ),
    "tutorial_rowan": (
        "Key Mechanic: Spellbook is a Magic weapon, and Margin Note lowers the target's Speed by 15 for 2 rounds.",
    ),
    "tutorial_tree_sentry": (
        "Key Mechanic: Bulwark boosts frontline DEF, and Guard reduces incoming damage.",
    ),
    "tutorial_tree_archer": (
        "Key Mechanic: Backline Ranged attacks still threaten you, and Deadeye adds damage.",
    ),
    "tutorial_tree_scout": (
        "Key Mechanic: Assassin can target units that swapped last round.",
    ),
    "tutorial_tree_healer": (
        "Key Mechanic: Wooden Amulet heals the lowest-HP ally on Strike; in encounter 5, Healer boosts that restore amount.",
    ),
    "tutorial_tree_warrior": (
        "Key Mechanic: Martial adds +25 damage to its melee Strikes.",
    ),
    "tutorial_tree_witch": (
        "Key Mechanic: Tree Witch alternates a Magic Strike with cooldown downtime.",
    ),
    "tutorial_tree_sentinel": (
        "Key Mechanic: Indomitable Tower gives the whole enemy team +15 DEF for 2 rounds.",
    ),
    "tutorial_tree_marksman": (
        "Key Mechanic: Armed preserves ammo on the first ranged Strike after a switch.",
    ),
    "tutorial_tree_druid": (
        "Key Mechanic: Carved Sigil can heal allies for 60 HP, and Medic cleansing removes conditions.",
    ),
    "tutorial_tree_knight": (
        "Key Mechanic: Oaken Lance splashes the backline when it hits the frontline, and encounter 8 adds Black Torch.",
    ),
    "tutorial_wormwood_spirit": (
        "Key Mechanic: Bygone grants +25 Speed in backline, and Decayed Athame punishes Guarded targets.",
    ),
    "tutorial_tree_sorcerer": (
        "Key Mechanic: Dense Rod is a CD 1 Magic strike; encounter 8 adds Bottled Clouds to empower a follow-up Strike.",
    ),
    "tutorial_wormwood_beast": (
        "Key Mechanic: Ravenous adds damage against Weakened or Rooted targets.",
    ),
    "tutorial_wormwood_fiend": (
        "Key Mechanic: Charred Idol Burns targets, and Kindling hits Burned enemies harder.",
    ),
    "tutorial_wormwood_monstrosity": (
        "Key Mechanic: Anachronism caps the first huge Strike each round to 1 damage taken.",
    ),
    "tutorial_sapling_handmaiden": (
        "Key Mechanic: Restoration sustains the boss team, and encounter 10 adds Medic plus Golden Fleece support.",
    ),
    "tutorial_frau_trude": (
        "Key Mechanic: Malevolent makes Burn hit twice as hard, while Hex and Philosopher's Stone amplify and protect her setup.",
    ),
}


@dataclass(frozen=True)
class TutorialEncounter:
    index: int
    title: str
    briefing: tuple[str, ...]
    battle_hint: str
    defeat_hint: str
    selection_required: bool
    show_loadout: bool
    no_defeat: bool
    allow_bonus_actions: bool
    allow_ultimate_meter: bool
    enemy_team: tuple[dict, ...]
    reward_artifact_ids: tuple[str, ...] = ()


def _update_signature_weapons(base, updates: dict[str, dict]):
    weapons = []
    for base_weapon in base.signature_weapons:
        config = updates.get(base_weapon.id, {})
        weapon_def = base_weapon
        strike_updates = config.get("strike")
        if strike_updates:
            weapon_def = replace(weapon_def, strike=replace(weapon_def.strike, **strike_updates))
        spell_updates = config.get("spells", {})
        if spell_updates:
            weapon_def = replace(
                weapon_def,
                spells=tuple(
                    replace(spell_def, **spell_updates.get(spell_def.id, {}))
                    for spell_def in weapon_def.spells
                ),
            )
        passive_updates = config.get("passives", {})
        if passive_updates:
            weapon_def = replace(
                weapon_def,
                passive_skills=tuple(
                    replace(passive_def, **passive_updates.get(passive_def.id, {}))
                    for passive_def in weapon_def.passive_skills
                ),
            )
        if "ammo" in config:
            weapon_def = replace(weapon_def, ammo=config["ammo"])
        weapons.append(weapon_def)
    return tuple(weapons)


def _tutorial_player(
    adventurer_id: str,
    *,
    hp: int,
    attack: int,
    defense: int,
    speed: int,
    innate_description: str,
    weapon_updates: dict[str, dict],
    ultimate_description: str,
):
    base = ADVENTURERS_BY_ID[adventurer_id]
    return replace(
        base,
        hp=hp,
        attack=attack,
        defense=defense,
        speed=speed,
        innate=replace(base.innate, description=innate_description),
        signature_weapons=_update_signature_weapons(base, weapon_updates),
        ultimate=replace(base.ultimate, description=ultimate_description),
    )


def _tutorial_artifact(artifact_id: str, *, amount: int, spell_updates: dict | None = None, description: str | None = None):
    base = ARTIFACTS_BY_ID[artifact_id]
    spell_def = replace(base.spell, **(spell_updates or {}))
    return replace(
        base,
        amount=amount,
        spell=spell_def,
        description=base.description if description is None else description,
    )


TUTORIAL_PLAYER_DEFS = {
    "little_jack": _tutorial_player(
        "little_jack",
        hp=265,
        attack=85,
        defense=60,
        speed=115,
        innate_description="Strikes deal +25 damage to enemies with higher max HP.",
        weapon_updates={
            "skyfall": {
                "strike": {"power": 150, "cooldown": 0},
                "spells": {
                    "cloudburst": {"description": "Next Strike ignores targeting restrictions."},
                },
            },
            "giants_harp": {
                "strike": {"power": 100},
                "passives": {
                    "belligerence": {"description": "Ignores 20% of enemy Defense."},
                },
            },
        },
        ultimate_description="Next Strike ignores 100% of enemy Defense.",
    ),
    "matchbox_liesl": _tutorial_player(
        "matchbox_liesl",
        hp=320,
        attack=70,
        defense=70,
        speed=120,
        innate_description="Liesl and allies immune to Burn. When an enemy takes Burn damage, Liesl's lowest HP ally restores that HP.",
        weapon_updates={
            "matchsticks": {
                "strike": {"power": 40},
                "ammo": 60,
                "passives": {
                    "cauterize": {"description": "Burned enemies cannot heal."},
                },
            },
            "eternal_torch": {
                "strike": {"power": 85, "lifesteal": 0.30},
                "passives": {
                    "flame_of_renewal": {"description": "When Liesl is knocked out, allies restore 50% max HP."},
                },
            },
        },
        ultimate_description="For 2 rounds, when Liesl or an ally restores HP each ally restores that much; when an enemy takes Burn damage each other enemy takes that damage.",
    ),
    "porcus_iii": _tutorial_player(
        "porcus_iii",
        hp=405,
        attack=50,
        defense=105,
        speed=25,
        innate_description="If a Strike would deal 20% max HP or more, reduce damage by 35% and Weaken the attacker 2 rounds.",
        weapon_updates={
            "crafty_wall": {
                "strike": {"power": 100, "description": "Bricklayer reduces all damage next round."},
                "spells": {
                    "not_by_the_hair": {"description": "Bricklayer activates on all Strikes this round and acts first."},
                },
            },
            "mortar_mortar": {
                "strike": {"power": 65},
                "ammo": 3,
            },
        },
        ultimate_description="For 2 rounds, +100 ATK, -50 DEF, +100 SPD.",
    ),
    "hunold_the_piper": _tutorial_player(
        "hunold_the_piper",
        hp=320,
        attack=80,
        defense=70,
        speed=115,
        innate_description="Shocked enemies take +25 damage.",
        weapon_updates={
            "lightning_rod": {
                "strike": {"power": 65},
                "ammo": 3,
            },
            "golden_fiddle": {
                "strike": {"power": 85},
            },
        },
        ultimate_description="For 2 rounds, Strikes are Spread, ignore targeting restrictions, and ignore the spread damage penalty.",
    ),
    "reynard_lupine_trickster": _tutorial_player(
        "reynard_lupine_trickster",
        hp=300,
        attack=80,
        defense=65,
        speed=140,
        innate_description="Deals +25 damage to targets that did not Strike last round.",
        weapon_updates={
            "foxfire_bow": {
                "strike": {"power": 65, "description": "The target has -15 Defense for 2 rounds."},
                "ammo": 3,
                "passives": {
                    "glowing_trail": {"description": "Always acts first when Striking."},
                },
            },
            "fang": {
                "strike": {"power": 100, "description": "+50 Power if the target has a stat penalty."},
                "spells": {
                    "silver_tongue": {"description": "Taunt target enemy for 2 rounds."},
                },
            },
        },
        ultimate_description="Next Strike steals 50 ATK from the target for 2 rounds.",
    ),
    "robin_hooded_avenger": _tutorial_player(
        "robin_hooded_avenger",
        hp=290,
        attack=90,
        defense=60,
        speed=135,
        innate_description="Strikes can't be redirected, ignore Taunt, and ignore Guard.",
        weapon_updates={
            "the_flock": {
                "strike": {"power": 60},
                "ammo": 3,
                "spells": {
                    "spread_fortune": {"description": "Ignore the spread damage nerf for 2 rounds."},
                },
            },
            "kingmaker": {
                "strike": {"power": 110, "description": "+55 Power vs backline targets."},
            },
        },
        ultimate_description="For 2 rounds, Strikes steal 25 ATK, DEF, and SPD from targets.",
    ),
}


TUTORIAL_ARTIFACT_DEFS = {
    "holy_grail": _tutorial_artifact(
        "holy_grail",
        amount=15,
        spell_updates={
            "heal": 65,
            "description": "Restore 65 HP and cleanse the newest status condition.",
        },
    ),
    "selkies_skin": _tutorial_artifact(
        "selkies_skin",
        amount=15,
        spell_updates={"description": "The next Strike against the user this round deals 0 damage."},
    ),
    "black_torch": _tutorial_artifact(
        "black_torch",
        amount=15,
    ),
    "bottled_clouds": _tutorial_artifact(
        "bottled_clouds",
        amount=15,
    ),
    "golden_fleece": _tutorial_artifact(
        "golden_fleece",
        amount=15,
    ),
    "philosophers_stone": _tutorial_artifact(
        "philosophers_stone",
        amount=15,
    ),
}


def _weapon_id(adventurer_id: str, index: int) -> str:
    return TUTORIAL_PLAYER_DEFS.get(adventurer_id, ADVENTURERS_BY_ID[adventurer_id]).signature_weapons[index].id


def _skill_id(class_name: str, index: int) -> str:
    return CLASS_SKILLS[class_name][index].id


def _default_tutorial_primary_weapon_id(encounter_index: int, adventurer_id: str, slot: str) -> str:
    if adventurer_id == "matchbox_liesl" and encounter_index >= 4:
        return _weapon_id(adventurer_id, 1)
    if adventurer_id == "little_jack" and encounter_index >= 6 and slot != SLOT_FRONT:
        return _weapon_id(adventurer_id, 1)
    return _weapon_id(adventurer_id, 0)


def _dummy_weapon(label: str):
    return weapon(f"{label}_dummy", "No Weapon", "melee", active(f"{label}_dummy_strike", "Strike", power=0))


def _enemy(defn_id: str, name: str, hp: int, attack: int, defense: int, speed: int, primary, *, innate=None, ultimate=None):
    base = ADVENTURERS_BY_ID["little_jack"]
    return replace(
        base,
        id=defn_id,
        name=name,
        hp=hp,
        attack=attack,
        defense=defense,
        speed=speed,
        innate=innate or passive("tutorial_none", "None", "No innate effect."),
        signature_weapons=(primary,),
        ultimate=ultimate or active(f"{defn_id}_ult", "Hold Fast", target="self"),
    )


def _enemy_pick(definition_id: str, slot: str, *, class_name: str = "None", class_skill_id: str | None = None, primary_weapon_id: str | None = None, artifact_id: str | None = None, secondary_weapon_id: str | None = None) -> dict:
    return {
        "definition_id": definition_id,
        "slot": slot,
        "class_name": class_name,
        "class_skill_id": class_skill_id,
        "primary_weapon_id": primary_weapon_id,
        "secondary_weapon_id": secondary_weapon_id,
        "artifact_id": artifact_id,
    }


TUTORIAL_ENEMY_DEFS = {
    "tutorial_francis": _enemy("tutorial_francis", "Francis", 275, 70, 85, 40, weapon("tutorial_plate", "Plate", "melee", active("tutorial_plate_strike", "Strike", power=90))),
    "tutorial_bar": _enemy("tutorial_bar", "Bar", 320, 0, 110, 0, _dummy_weapon("tutorial_bar"), innate=passive("solid_oak", "Solid Oak", "Takes 20% less damage from the first Strike each round.", special="solid_oak")),
    "tutorial_marigold": _enemy("tutorial_marigold", "Marigold", 235, 70, 55, 95, weapon("tutorial_darts", "Darts", "ranged", active("tutorial_darts_strike", "Strike", power=55, ammo_cost=1), ammo=4, spells=(active("tutorial_take_a_shot", "Take a Shot", target="self", heal=40, cooldown=2, description="Marigold restores 40 HP and fully reloads her primary weapon.", special="tutorial_reload_primary"),))),
    "tutorial_daeny": _enemy("tutorial_daeny", "Daeny", 255, 75, 60, 90, weapon("tutorial_claws", "Claws", "melee", active("tutorial_claws_strike", "Strike", power=100, description="100 Power."))),
    "tutorial_rowan": _enemy("tutorial_rowan", "Rowan", 170, 40, 60, 90, weapon("tutorial_spellbook", "Spellbook", "magic", active("tutorial_spellbook_strike", "Strike", power=75, cooldown=1, counts_as_spell=True, description="75 Power."), spells=(active("tutorial_margin_note", "Margin Note", target="enemy", cooldown=2, target_debuffs=(stat("speed", 15, 2),), description="The target has -15 Speed for 2 rounds."),))),
    "tutorial_tree_sentry": _enemy("tutorial_tree_sentry", "Tree Sentry", 300, 55, 95, 35, weapon("tutorial_wooden_shield", "Wooden Shield", "melee", active("tutorial_wooden_shield_strike", "Strike", power=85, description="85 Power. Guards the Tree Sentry for 2 rounds.", self_statuses=(status("guard", 2),)))),
    "tutorial_tree_archer": _enemy("tutorial_tree_archer", "Tree Archer", 235, 65, 55, 85, weapon("tutorial_wooden_longbow", "Wooden Longbow", "ranged", active("tutorial_wooden_longbow_strike", "Strike", power=55, ammo_cost=1, description="55 Power."), ammo=3)),
    "tutorial_tree_scout": _enemy("tutorial_tree_scout", "Tree Scout", 240, 70, 55, 95, weapon("tutorial_wooden_knife", "Wooden Knife", "melee", active("tutorial_wooden_knife_strike", "Strike", power=85, description="85 Power."))),
    "tutorial_tree_healer": _enemy("tutorial_tree_healer", "Tree Healer", 285, 50, 65, 70, weapon("tutorial_wooden_amulet", "Wooden Amulet", "magic", active("tutorial_wooden_amulet_strike", "Strike", power=60, cooldown=1, counts_as_spell=True, description="Tree Healer's lowest HP ally restores 30 HP.", special="tutorial_heal_lowest_ally_55"))),
    "tutorial_tree_warrior": _enemy("tutorial_tree_warrior", "Tree Warrior", 285, 75, 75, 55, weapon("tutorial_wooden_sword", "Wooden Sword", "melee", active("tutorial_wooden_sword_strike", "Strike", power=90, description="90 Power."))),
    "tutorial_tree_witch": _enemy("tutorial_tree_witch", "Tree Witch", 240, 70, 55, 80, weapon("tutorial_wooden_scepter", "Wooden Scepter", "magic", active("tutorial_wooden_scepter_strike", "Strike", power=75, cooldown=1, counts_as_spell=True, description="75 Power."))),
    "tutorial_tree_sentinel": _enemy("tutorial_tree_sentinel", "Tree Sentinel", 330, 55, 100, 30, weapon("tutorial_indomitable_tower", "Indomitable Tower", "melee", active("tutorial_indomitable_tower_strike", "Strike", power=80, description="Sentinel and allies gain +15 DEF for 2 rounds.", special="tutorial_team_defense_up_15"))),
    "tutorial_tree_marksman": _enemy("tutorial_tree_marksman", "Tree Marksman", 260, 70, 55, 85, weapon("tutorial_sturdy_crossbow", "Sturdy Crossbow", "ranged", active("tutorial_sturdy_crossbow_strike", "Strike", power=65, ammo_cost=1, description="65 Power."), ammo=3)),
    "tutorial_tree_druid": _enemy("tutorial_tree_druid", "Tree Druid", 315, 50, 70, 70, weapon("tutorial_carved_sigil", "Carved Sigil", "magic", active("tutorial_carved_sigil_strike", "Strike", target="any", power=60, heal=60, cooldown=1, counts_as_spell=True, description="Damage enemies or heal allies.", special="tutorial_druid_sigil"))),
    "tutorial_tree_knight": _enemy("tutorial_tree_knight", "Tree Knight", 325, 80, 85, 55, weapon("tutorial_oaken_lance", "Oaken Lance", "melee", active("tutorial_oaken_lance_strike", "Strike", power=100, description="100 Power. If the target is frontline, each backline enemy takes 15 damage."))),
    "tutorial_wormwood_spirit": _enemy("tutorial_wormwood_spirit", "Wormwood Spirit", 260, 70, 60, 95, weapon("tutorial_decayed_athame", "Decayed Athame", "magic", active("tutorial_decayed_athame_strike", "Strike", power=70, cooldown=1, counts_as_spell=True, bonus_power_if_status="guard", bonus_power=35, description="70 Power, +35 Power if the target is Guarded.")), innate=passive("bygone", "Bygone", "Wormwood Spirit has +25 Speed while in the backline.", special="bygone")),
    "tutorial_tree_sorcerer": _enemy("tutorial_tree_sorcerer", "Tree Sorcerer", 280, 75, 55, 85, weapon("tutorial_dense_rod", "Dense Rod", "magic", active("tutorial_dense_rod_strike", "Strike", power=80, cooldown=1, counts_as_spell=True, description="80 Power."))),
    "tutorial_wormwood_beast": _enemy("tutorial_wormwood_beast", "Wormwood Beast", 345, 85, 70, 75, weapon("tutorial_rotting_claws", "Rotting Claws", "melee", active("tutorial_rotting_claws_strike", "Strike", power=105, bonus_power_if_status="weaken", bonus_power=15, description="105 Power."))),
    "tutorial_wormwood_fiend": _enemy("tutorial_wormwood_fiend", "Wormwood Fiend", 295, 80, 55, 105, weapon("tutorial_charred_idol", "Charred Idol", "magic", active("tutorial_charred_idol_strike", "Strike", power=80, cooldown=1, counts_as_spell=True, target_statuses=(status("burn", 2),), description="80 Power. Burns the target for 2 rounds."))),
    "tutorial_wormwood_monstrosity": _enemy("tutorial_wormwood_monstrosity", "Wormwood Monstrosity", 410, 95, 95, 45, weapon("tutorial_petrified_fangs", "Petrified Fangs", "melee", active("tutorial_petrified_fangs_strike", "Strike", power=120, description="If fatal, Anachronism triggers on all Strikes next round.", special="tutorial_monstrosity_fatal")), innate=passive("anachronism", "Anachronism", "The first time each round a Strike would deal 20% max HP or more, reduce it to 1.", special="anachronism")),
    "tutorial_sapling_handmaiden": _enemy("tutorial_sapling_handmaiden", "Sapling Handmaiden", 320, 55, 75, 75, weapon("tutorial_twig_caduceus", "Twig Caduceus", "magic", active("tutorial_twig_caduceus_strike", "Strike", power=70, cooldown=1, counts_as_spell=True, lifesteal=0.50, description="70 Power, 50% Lifesteal."), spells=(active("tutorial_handmaiden_restoration", "Restoration", target="ally", heal=70, cooldown=1, description="Target ally restores 70 HP."),)), innate=passive("perennial", "Perennial", "Spring Handmaiden and her allies restore +50% HP when below 50% max HP.", special="perennial")),
    "tutorial_frau_trude": _enemy("tutorial_frau_trude", "Frau Trude", 340, 80, 75, 100, weapon("tutorial_wormwood_wand", "Wormwood Wand", "magic", active("tutorial_wormwood_wand_strike", "Strike", power=90, cooldown=1, counts_as_spell=True, target_statuses=(status("burn", 2),), description="Burns the target for 2 rounds."), spells=(active("tutorial_hex", "Hex", target="enemy", cooldown=2, description="Target enemy takes +15 damage from all sources for 2 rounds.", special="takes_plus_15_damage"),)), innate=passive("malevolent", "Malevolent", "Enemies take x2 damage from Burn.", special="malevolent"), ultimate=active("tutorial_petrify", "Petrify", target="enemy", description="For 2 rounds, the target enemy has +25 Defense and cannot act.", target_buffs=(stat("defense", 25, 2),), special="tutorial_petrify")),
}


TUTORIAL_ENEMY_DEFS["tutorial_frau_trude"] = replace(
    TUTORIAL_ENEMY_DEFS["tutorial_frau_trude"],
    signature_weapons=(
        TUTORIAL_ENEMY_DEFS["tutorial_frau_trude"].signature_weapons[0],
        weapon("tutorial_ash_mothers_brand", "Ash-Mother's Brand", "magic", active("tutorial_ash_mothers_brand_strike", "Strike", power=80, cooldown=2, counts_as_spell=True, bonus_power_if_status="burn", bonus_power=40, description="80 Power, +40 Power vs Burned targets.")),
    ),
)


TUTORIAL_ENCOUNTERS = {
    1: TutorialEncounter(1, "Your First Strike", ("Select Strike to attack.", "Melee weapons hit the enemy frontline.", "Jack's Giant Slayer activates against higher-max-HP enemies."), "Strike Francis until he falls.", "Keep striking. This encounter restarts until the basic attack lesson lands.", False, False, True, False, False, (_enemy_pick("tutorial_francis", SLOT_FRONT, primary_weapon_id="tutorial_plate"),)),
    2: TutorialEncounter(2, "Magic from Afar", ("Cloudburst makes Jack's next Strike ignore targeting restrictions.", "Bar blocks the front while Marigold attacks from the backline.", "Ranged attacks use Ammo and Magic attacks use cooldowns."), "Cast Cloudburst, then Strike Marigold.", "Open with Cloudburst and use the empowered Strike on the backliner.", False, False, True, False, False, (_enemy_pick("tutorial_bar", SLOT_FRONT, primary_weapon_id="tutorial_bar_dummy"), _enemy_pick("tutorial_marigold", SLOT_BACK_LEFT, primary_weapon_id="tutorial_darts"))),
    3: TutorialEncounter(3, "The Right Tool", ("Jack now has both signature weapons.", "Switching swaps the active weapon and resets cooldowns.", "Use Giant's Harp to reach Rowan."), "Switch once Daeny is handled so Giant's Harp can hit Rowan.", "This fight is about learning when to change weapons.", False, True, True, False, False, (_enemy_pick("tutorial_daeny", SLOT_FRONT, primary_weapon_id="tutorial_claws"), _enemy_pick("tutorial_rowan", SLOT_BACK_LEFT, primary_weapon_id="tutorial_spellbook"))),
    4: TutorialEncounter(4, "Choose Your Role", ("Liesl joins the party.", "Classes add HP and passive strength.", "Backline Speed is halved, so initiative matters."), "Jack and Liesl use pre-assigned tutorial classes here.", "Lean on Jack's Martial damage and Liesl's magic pressure.", False, True, True, False, False, (_enemy_pick("tutorial_tree_sentry", SLOT_FRONT, class_name="Warden", class_skill_id="bulwark", primary_weapon_id="tutorial_wooden_shield"), _enemy_pick("tutorial_tree_archer", SLOT_BACK_LEFT, class_name="Ranger", class_skill_id="deadeye", primary_weapon_id="tutorial_wooden_longbow"))),
    5: TutorialEncounter(5, "Shifting Ground", ("Swap Positions trades places with an ally.", "Frontline removes the backline Speed penalty.", "Tree Scout punishes recent Swappers."), "Try swapping Jack and Liesl to feel the position change.", "Smart swaps win tempo, but Tree Scout chases movers.", False, True, True, False, False, (_enemy_pick("tutorial_tree_scout", SLOT_FRONT, class_name="Rogue", class_skill_id="assassin", primary_weapon_id="tutorial_wooden_knife"), _enemy_pick("tutorial_tree_healer", SLOT_BACK_LEFT, class_name="Cleric", class_skill_id="healer", primary_weapon_id="tutorial_wooden_amulet"))),
    6: TutorialEncounter(6, "Above and Beyond", ("Porcus III joins the team.", "The full 3v3 formation is active now.", "Bonus Action phase starts after the main action phase."), "Watch the round split into actions, bonus actions, and end-of-round effects.", "You have three bodies now. Let Porcus protect the backline.", False, True, True, True, False, (_enemy_pick("tutorial_tree_warrior", SLOT_FRONT, class_name="Fighter", class_skill_id="martial", primary_weapon_id="tutorial_wooden_sword"), _enemy_pick("tutorial_tree_archer", SLOT_BACK_LEFT, class_name="Ranger", class_skill_id="deadeye", primary_weapon_id="tutorial_wooden_longbow"), _enemy_pick("tutorial_tree_witch", SLOT_BACK_RIGHT, class_name="Mage", class_skill_id="archmage", primary_weapon_id="tutorial_wooden_scepter"))),
    7: TutorialEncounter(7, "Form Your Party", ("You now have six adventurers but only bring three.", "Each class now exposes both class skill options.", "Winning adds Wishing Table and Selkie's Skin to the tutorial pool."), "Choose your trio, place them, then read both class skill options.", "This is the first real roster-building test.", True, True, False, True, False, (_enemy_pick("tutorial_tree_sentinel", SLOT_FRONT, class_name="Warden", class_skill_id="vigilant", primary_weapon_id="tutorial_indomitable_tower"), _enemy_pick("tutorial_tree_marksman", SLOT_BACK_LEFT, class_name="Ranger", class_skill_id="armed", primary_weapon_id="tutorial_sturdy_crossbow"), _enemy_pick("tutorial_tree_druid", SLOT_BACK_RIGHT, class_name="Cleric", class_skill_id="medic", primary_weapon_id="tutorial_carved_sigil")), TUTORIAL_REWARD_ARTIFACT_IDS),
    8: TutorialEncounter(8, "Tools of the Trade", ("Artifacts now appear in loadouts.", "Attunement controls spell access, but the stat bonus always applies.", "Enemy artifacts can be reactive."), "Equip the tutorial artifacts if they fit your plan.", "Artifacts are optional, but this lesson wants you to try them.", True, True, False, True, False, (_enemy_pick("tutorial_tree_knight", SLOT_FRONT, class_name="Fighter", class_skill_id="vanguard", primary_weapon_id="tutorial_oaken_lance", artifact_id="black_torch"), _enemy_pick("tutorial_wormwood_spirit", SLOT_BACK_LEFT, primary_weapon_id="tutorial_decayed_athame"), _enemy_pick("tutorial_tree_sorcerer", SLOT_BACK_RIGHT, class_name="Mage", class_skill_id="arcane", primary_weapon_id="tutorial_dense_rod", artifact_id="bottled_clouds"))),
    9: TutorialEncounter(9, "Unleash Your Power", ("Ultimate Meter is now active.", "Strikes add one meter, spells add two.", "A full meter unlocks an Ultimate action."), "Build the meter, then cast an Ultimate when it hits five.", "This is the first battle where Ultimates are part of the plan.", True, True, False, True, True, (_enemy_pick("tutorial_wormwood_beast", SLOT_FRONT, primary_weapon_id="tutorial_rotting_claws"), _enemy_pick("tutorial_wormwood_spirit", SLOT_BACK_LEFT, primary_weapon_id="tutorial_decayed_athame"), _enemy_pick("tutorial_wormwood_fiend", SLOT_BACK_RIGHT, primary_weapon_id="tutorial_charred_idol"))),
    10: TutorialEncounter(10, "The Final Test", ("This is the graduation fight.", "Use positioning, switching, spells, artifacts, and ultimates together.", "Liesl's Burn protection and smart cleansing are especially valuable here."), "Bring a real plan and finish the tutorial.", "Adjust your trio and priorities until the whole system clicks.", True, True, False, True, True, (_enemy_pick("tutorial_wormwood_monstrosity", SLOT_FRONT, class_name="Fighter", class_skill_id="vanguard", primary_weapon_id="tutorial_petrified_fangs"), _enemy_pick("tutorial_sapling_handmaiden", SLOT_BACK_LEFT, class_name="Cleric", class_skill_id="medic", primary_weapon_id="tutorial_twig_caduceus", artifact_id="golden_fleece"), _enemy_pick("tutorial_frau_trude", SLOT_BACK_RIGHT, class_name="Mage", class_skill_id="arcane", primary_weapon_id="tutorial_wormwood_wand", secondary_weapon_id="tutorial_ash_mothers_brand", artifact_id="philosophers_stone"))),
}


def encounter_spec(encounter_index: int) -> TutorialEncounter:
    return TUTORIAL_ENCOUNTERS[max(1, min(10, encounter_index))]


def encounter_roster_ids(encounter_index: int) -> list[str]:
    if encounter_index <= 3:
        return ["little_jack"]
    if encounter_index <= 5:
        return ["little_jack", "matchbox_liesl"]
    if encounter_index == 6:
        return ["porcus_iii", "little_jack", "matchbox_liesl"]
    return list(TUTORIAL_PLAYER_IDS)


def encounter_unlocked_actions(encounter_index: int) -> set[str]:
    return set(TUTORIAL_UNLOCKED_ACTIONS[max(1, min(10, encounter_index))])


def tutorial_is_selection_encounter(encounter_index: int) -> bool:
    return encounter_spec(encounter_index).selection_required


def tutorial_loadout_note(encounter_index: int) -> str:
    return TUTORIAL_LOADOUT_NOTES.get(max(1, min(10, encounter_index)), "Tutorial Loadout")


def tutorial_party_select_lines(encounter_index: int) -> list[str]:
    return list(TUTORIAL_PARTY_SELECT_LINES.get(max(1, min(10, encounter_index)), ()))


def tutorial_loadout_lines(encounter_index: int) -> list[str]:
    return list(TUTORIAL_LOADOUT_LINES.get(max(1, min(10, encounter_index)), ()))


def tutorial_unit_callout_lines(definition_id: str) -> tuple[str, ...]:
    return TUTORIAL_UNIT_CALLOUTS.get(definition_id, ())


def tutorial_loadout_options(encounter_index: int) -> dict:
    if encounter_index <= 3:
        return {"show_secondary_weapon": encounter_index >= 3, "show_classes": False, "class_editable": False, "max_skill_options": 0, "skills_editable": False, "show_artifacts": False, "artifacts_editable": False, "formation_editable": False}
    if encounter_index <= 6:
        return {"show_secondary_weapon": True, "show_classes": True, "class_editable": False, "max_skill_options": 1, "skills_editable": False, "show_artifacts": False, "artifacts_editable": False, "formation_editable": False}
    if encounter_index == 7:
        return {"show_secondary_weapon": True, "show_classes": True, "class_editable": True, "max_skill_options": 2, "skills_editable": True, "show_artifacts": False, "artifacts_editable": False, "formation_editable": True}
    return {"show_secondary_weapon": True, "show_classes": True, "class_editable": True, "max_skill_options": 2, "skills_editable": True, "show_artifacts": True, "artifacts_editable": True, "formation_editable": True}


def build_player_setup(encounter_index: int, *, selected_ids: Optional[Iterable[str]] = None, artifact_pool: Optional[Iterable[str]] = None) -> dict:
    if selected_ids is None:
        if encounter_index <= 5:
            team_ids = encounter_roster_ids(encounter_index)
        elif encounter_index == 6:
            team_ids = ["porcus_iii", "little_jack", "matchbox_liesl"]
        else:
            team_ids = ["little_jack", "matchbox_liesl", "porcus_iii"]
    else:
        team_ids = [adventurer_id for adventurer_id in selected_ids if adventurer_id in TUTORIAL_PLAYER_IDS][:3]
    if not team_ids:
        team_ids = ["little_jack"]
    slot_order = [SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT]
    reward_pool = set(artifact_pool or [])
    members = []
    for index, adventurer_id in enumerate(team_ids):
        slot = slot_order[index]
        class_name = "None" if encounter_index <= 3 else TUTORIAL_RECOMMENDED_CLASSES[adventurer_id]
        artifact_id = None
        if encounter_index >= 8:
            if adventurer_id in {"little_jack", "porcus_iii", "robin_hooded_avenger"} and "holy_grail" in reward_pool:
                artifact_id = "holy_grail"
                reward_pool.discard("holy_grail")
            elif adventurer_id in {"matchbox_liesl", "hunold_the_piper", "reynard_lupine_trickster"} and "selkies_skin" in reward_pool:
                artifact_id = "selkies_skin"
                reward_pool.discard("selkies_skin")
        members.append(
            {
                "adventurer_id": adventurer_id,
                "slot": slot,
                "class_name": class_name,
                "class_skill_id": None if class_name == "None" else _skill_id(class_name, 0),
                "primary_weapon_id": _default_tutorial_primary_weapon_id(encounter_index, adventurer_id, slot),
                "artifact_id": artifact_id,
            }
        )
    return {"team1": members, "team2": [], "team1_allowed_artifact_ids": sorted(set(artifact_pool or []))}


def _pick_from_definition(
    lookup: dict[str, object],
    definition_id: str,
    *,
    slot: str,
    class_name: str,
    class_skill_id: str | None,
    primary_weapon_id: str | None,
    secondary_weapon_id: str | None = None,
    artifact_id: str | None = None,
    artifact_lookup: dict[str, object] | None = None,
) -> dict:
    definition = lookup[definition_id]
    class_skill = CLASS_SKILLS_BY_ID.get(class_skill_id or "", NO_CLASS_SKILL)
    primary_weapon = next((weapon_def for weapon_def in definition.signature_weapons if weapon_def.id == (primary_weapon_id or definition.signature_weapons[0].id)), definition.signature_weapons[0])
    secondary_weapon = next((weapon_def for weapon_def in definition.signature_weapons if weapon_def.id == secondary_weapon_id), next((weapon_def for weapon_def in definition.signature_weapons if weapon_def.id != primary_weapon.id), primary_weapon))
    artifact_defs = artifact_lookup or ARTIFACTS_BY_ID
    return {"definition": definition, "slot": slot, "class_name": class_name, "class_skill": class_skill, "primary_weapon": primary_weapon, "secondary_weapon": secondary_weapon, "artifact": artifact_defs.get(artifact_id)}


def build_tutorial_battle(encounter_index: int, setup_state: dict):
    spec = encounter_spec(encounter_index)
    player_lookup = TUTORIAL_PLAYER_DEFS
    player_picks = [
        _pick_from_definition(
            player_lookup,
            member["adventurer_id"],
            slot=member["slot"],
            class_name=member.get("class_name", "None"),
            class_skill_id=member.get("class_skill_id"),
            primary_weapon_id=member.get("primary_weapon_id"),
            artifact_id=member.get("artifact_id"),
            artifact_lookup=TUTORIAL_ARTIFACT_DEFS,
        )
        for member in list((setup_state or {}).get("team1", []))
    ]
    enemy_picks = [
        _pick_from_definition(
            TUTORIAL_ENEMY_DEFS,
            member["definition_id"],
            slot=member["slot"],
            class_name=member.get("class_name", "None"),
            class_skill_id=member.get("class_skill_id"),
            primary_weapon_id=member.get("primary_weapon_id"),
            secondary_weapon_id=member.get("secondary_weapon_id"),
            artifact_id=member.get("artifact_id"),
            artifact_lookup=TUTORIAL_ARTIFACT_DEFS,
        )
        for member in spec.enemy_team
    ]
    battle = create_battle(create_team("You", player_picks), create_team("Tutorial Rival", enemy_picks))
    determine_initiative_order(battle)
    return battle


def tutorial_adventurer_lookup() -> dict[str, object]:
    return TUTORIAL_PLAYER_DEFS


def tutorial_loadout_adventurer_lookup() -> dict[str, object]:
    return {**TUTORIAL_PLAYER_DEFS, **TUTORIAL_ENEMY_DEFS}


def tutorial_artifact_lookup() -> dict[str, object]:
    return TUTORIAL_ARTIFACT_DEFS


def _lowest_hp(units):
    return min(units, key=lambda unit: (unit.hp / max(1, unit.max_hp), -unit.get_stat("attack"), unit.name)) if units else None


def _highest_stat(units, stat_name: str):
    return max(units, key=lambda unit: (unit.get_stat(stat_name), unit.get_stat("attack"), -unit.hp)) if units else None


def _legal_targets(actor, battle, *, effect=None, weapon=None, same_team: bool | None = None):
    targets = list(get_legal_targets(battle, actor, effect=effect, weapon=weapon))
    if same_team is None:
        return targets
    actor_team = player_num_for_actor(battle, actor)
    return [unit for unit in targets if (player_num_for_actor(battle, unit) == actor_team) == same_team]


def _queue_strike_lowest(actor, battle):
    target = _lowest_hp(_legal_targets(actor, battle, weapon=actor.primary_weapon))
    if target is None:
        queue_skip(actor)
        return
    queue_strike(actor, target)


def _queue_spell(actor, battle, effect_id: str, *, target=None, chooser=None):
    effect = next((item for item in actor.active_spells() if item.id == effect_id), None)
    if effect is None:
        _queue_strike_lowest(actor, battle)
        return
    if effect.target in {"none", "self"}:
        queue_spell(actor, effect, actor if effect.target == "self" else None, battle)
        return
    if target is None:
        targets = _legal_targets(actor, battle, effect=effect)
        target = chooser(targets) if chooser is not None else _lowest_hp(targets)
    if target is None:
        _queue_strike_lowest(actor, battle)
        return
    queue_spell(actor, effect, target, battle)


def queue_tutorial_enemy_plan(battle, encounter_index: int, *, bonus: bool = False):
    if bonus:
        for actor in battle.team2.alive():
            if actor.queued_bonus_action is None:
                queue_bonus_action(actor, {"type": "skip"})
        return
    for actor in battle.initiative_order:
        if actor.ko or player_num_for_actor(battle, actor) != 2 or actor.queued_action is not None:
            continue
        actor_id = actor.defn.id
        if actor_id == "tutorial_bar":
            queue_skip(actor)
        elif actor_id == "tutorial_marigold" and (actor.ammo_remaining.get(actor.primary_weapon.id, actor.primary_weapon.ammo) <= 0 or actor.hp <= actor.max_hp // 2):
            _queue_spell(actor, battle, "tutorial_take_a_shot")
        elif actor_id == "tutorial_rowan":
            if actor.markers.get("tutorial_rowan_opened", 0) <= 0:
                actor.markers["tutorial_rowan_opened"] = 1
                _queue_strike_lowest(actor, battle)
            elif actor.markers.get("tutorial_rowan_cast_margin_note", 0) <= 0 and actor.cooldowns.get("tutorial_margin_note", 0) <= 0:
                actor.markers["tutorial_rowan_cast_margin_note"] = 1
                _queue_spell(actor, battle, "tutorial_margin_note", target=_highest_stat(_legal_targets(actor, battle, effect=next((item for item in actor.active_spells() if item.id == "tutorial_margin_note"), None)), "speed"))
            else:
                _queue_strike_lowest(actor, battle)
        elif actor_id == "tutorial_tree_druid":
            ally = _lowest_hp([unit for unit in _legal_targets(actor, battle, effect=actor.primary_weapon.strike, same_team=True) if unit.hp < int(unit.max_hp * 0.70)])
            target = ally if ally is not None else _lowest_hp(_legal_targets(actor, battle, weapon=actor.primary_weapon))
            if target is None:
                queue_skip(actor)
            else:
                queue_strike(actor, target)
        elif actor_id == "tutorial_tree_sorcerer" and actor.cooldowns.get("clear_skies", 0) <= 0 and len(_legal_targets(actor, battle, weapon=actor.primary_weapon)) >= 2:
            _queue_spell(actor, battle, "clear_skies")
        elif actor_id == "tutorial_sapling_handmaiden":
            ally = _lowest_hp([unit for unit in _legal_targets(actor, battle, effect=next((item for item in actor.active_spells() if item.id == "tutorial_handmaiden_restoration"), None), same_team=True) if unit.hp < int(unit.max_hp * 0.60)])
            if ally is not None:
                _queue_spell(actor, battle, "tutorial_handmaiden_restoration", target=ally)
            else:
                _queue_strike_lowest(actor, battle)
        elif actor_id == "tutorial_frau_trude":
            if battle.team2.ultimate_meter >= 5:
                target = _highest_stat(_legal_targets(actor, battle, effect=actor.defn.ultimate), "attack")
                if target is not None:
                    queue_ultimate(actor, target, battle)
                    continue
            burned = [unit for unit in _legal_targets(actor, battle, weapon=actor.primary_weapon) if unit.has_status("burn")]
            if actor.primary_weapon.id == "tutorial_wormwood_wand" and burned:
                queue_switch(actor)
            elif actor.primary_weapon.id == "tutorial_ash_mothers_brand" and not burned:
                queue_switch(actor)
            elif actor.primary_weapon.id == "tutorial_wormwood_wand" and actor.cooldowns.get("tutorial_hex", 0) <= 0:
                _queue_spell(actor, battle, "tutorial_hex", target=_highest_stat(_legal_targets(actor, battle, effect=next((item for item in actor.active_spells() if item.id == "tutorial_hex"), None)), "attack"))
            else:
                target_pool = burned if actor.primary_weapon.id == "tutorial_ash_mothers_brand" and burned else _legal_targets(actor, battle, weapon=actor.primary_weapon)
                target = _lowest_hp(target_pool)
                if target is None:
                    queue_skip(actor)
                else:
                    queue_strike(actor, target)
        else:
            _queue_strike_lowest(actor, battle)
