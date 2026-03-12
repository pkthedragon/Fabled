"""
campaign_data.py – all static data for the main story campaign.
Defines NPC AdventurerDef objects, Dragon Head signatures, quest/mission tables,
and the build_quest_enemy_team() helper.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models import Ability, AbilityMode, Item, AdventurerDef
import data as _data

# ─────────────────────────────────────────────────────────────────────────────
# ROSTER LOOKUP
# ─────────────────────────────────────────────────────────────────────────────
ROSTER_BY_ID: Dict[str, AdventurerDef] = {d.id: d for d in _data.ROSTER}

# ─────────────────────────────────────────────────────────────────────────────
# PLACEHOLDER PASSIVE ABILITY / ITEM
# ─────────────────────────────────────────────────────────────────────────────
_NA = AbilityMode(unavailable=True)

NO_SIG = Ability(
    id="no_sig",
    name="—",
    category="signature",
    passive=True,
    frontline=AbilityMode(),
    backline=AbilityMode(),
)

NO_ITEM = Item(
    id="no_item",
    name="—",
    passive=True,
    description="No item.",
    uses=99,
)

# ─────────────────────────────────────────────────────────────────────────────
# DRAGON HEAD SIGNATURE ABILITIES
# ─────────────────────────────────────────────────────────────────────────────

SOVEREIGN_EDICT = Ability(
    id="sovereign_edict",
    name="Sovereign Edict",
    category="signature",
    passive=False,
    frontline=AbilityMode(
        power=65,
        special="sovereign_edict_front",
    ),
    backline=AbilityMode(
        power=40,
        status="spotlight",
        status_dur=2,
        special="sovereign_edict_back",
    ),
)

CATACLYSM = Ability(
    id="cataclysm",
    name="Cataclysm",
    category="signature",
    passive=False,
    frontline=AbilityMode(
        power=80,
        special="cataclysm_front",
    ),
    backline=AbilityMode(
        power=50,
        spread=True,
        special="cataclysm_back",
    ),
)

DARK_AURA = Ability(
    id="dark_aura",
    name="Dark Aura",
    category="signature",
    passive=True,
    frontline=AbilityMode(
        special="dark_aura_passive",
    ),
    backline=AbilityMode(
        special="dark_aura_passive",
    ),
)

# ─────────────────────────────────────────────────────────────────────────────
# ABILITY LOOKUPS (for building basics lists by id)
# ─────────────────────────────────────────────────────────────────────────────
_ALL_BASICS_BY_ID: Dict[str, Ability] = {}
for _cls_list in _data.CLASS_BASICS.values():
    for _ab in _cls_list:
        _ALL_BASICS_BY_ID[_ab.id] = _ab

_ROSTER_SIG_BY_ID: Dict[str, Ability] = {}
for _defn in _data.ROSTER:
    for _sig in _defn.sig_options:
        _ROSTER_SIG_BY_ID[_sig.id] = _sig

# ─────────────────────────────────────────────────────────────────────────────
# ITEMS LOOKUP
# ─────────────────────────────────────────────────────────────────────────────
_ITEMS_BY_ID: Dict[str, Item] = {it.id: it for it in _data.ITEMS}


def _get_item(item_id: str) -> Item:
    return _ITEMS_BY_ID.get(item_id, NO_ITEM)


def _get_basic(ability_id: str) -> Ability:
    return _ALL_BASICS_BY_ID[ability_id]


# ─────────────────────────────────────────────────────────────────────────────
# NPC ADVENTURERDEFS
# ─────────────────────────────────────────────────────────────────────────────

def _make_npc(
    npc_id: str,
    name: str,
    cls: str,
    hp: int,
    attack: int,
    defense: int,
    speed: int,
    talent_name: str = "—",
    talent_text: str = "No special talent.",
    sig_options: Optional[List[Ability]] = None,
    twist: Optional[Ability] = None,
) -> AdventurerDef:
    if sig_options is None:
        sig_options = [NO_SIG, NO_SIG, NO_SIG]
    if twist is None:
        twist = NO_SIG
    return AdventurerDef(
        id=npc_id,
        name=name,
        cls=cls,
        hp=hp,
        attack=attack,
        defense=defense,
        speed=speed,
        talent_name=talent_name,
        talent_text=talent_text,
        sig_options=sig_options,
        twist=twist,
    )


# ── Generic NPCs ──────────────────────────────────────────────────────────────
NPC_KNIGHT_WARDEN = _make_npc(
    "npc_knight_warden", "Knight Warden", "Warden",
    hp=200, attack=60, defense=65, speed=25,
)

NPC_HOLY_CLERIC = _make_npc(
    "npc_holy_cleric", "Holy Cleric", "Cleric",
    hp=185, attack=55, defense=45, speed=35,
)

NPC_ROGUE_BANDIT = _make_npc(
    "npc_rogue_bandit", "Rogue Bandit", "Rogue",
    hp=180, attack=65, defense=35, speed=65,
)

NPC_RANGER_BANDIT = _make_npc(
    "npc_ranger_bandit", "Ranger Bandit", "Ranger",
    hp=185, attack=65, defense=40, speed=55,
)

NPC_MAGE_ACOLYTE = _make_npc(
    "npc_mage_acolyte", "Mage Acolyte", "Mage",
    hp=175, attack=70, defense=35, speed=45,
)

NPC_TRAINED_FIGHTER = _make_npc(
    "npc_trained_fighter", "Trained Fighter", "Fighter",
    hp=200, attack=65, defense=50, speed=35,
)

NPC_ROYAL_NOBLE = _make_npc(
    "npc_royal_noble", "Royal Noble", "Noble",
    hp=195, attack=65, defense=50, speed=45,
)

NPC_ROYAL_RANGER = _make_npc(
    "npc_royal_ranger", "Royal Ranger", "Ranger",
    hp=190, attack=70, defense=40, speed=60,
)

NPC_SHADOW_WARLOCK = _make_npc(
    "npc_shadow_warlock", "Shadow Warlock", "Warlock",
    hp=185, attack=70, defense=40, speed=50,
)

NPC_SHADOW_MAGE = _make_npc(
    "npc_shadow_mage", "Shadow Mage", "Mage",
    hp=180, attack=75, defense=35, speed=50,
)

NPC_SHADOW_ROGUE = _make_npc(
    "npc_shadow_rogue", "Shadow Rogue", "Rogue",
    hp=185, attack=70, defense=35, speed=70,
)

NPC_PIG_WARDEN = _make_npc(
    "npc_pig_warden", "Pig Warden", "Warden",
    hp=210, attack=65, defense=65, speed=25,
)

NPC_HUNTER_RANGER = _make_npc(
    "npc_hunter_ranger", "Hunter Ranger", "Ranger",
    hp=190, attack=70, defense=40, speed=60,
)

NPC_WARLOCK_ACOLYTE = _make_npc(
    "npc_warlock_acolyte", "Warlock Acolyte", "Warlock",
    hp=185, attack=68, defense=38, speed=48,
)

NPC_MAD_ROGUE = _make_npc(
    "npc_mad_rogue", "Mad Rogue", "Rogue",
    hp=190, attack=75, defense=35, speed=70,
)

NPC_MAD_NOBLE = _make_npc(
    "npc_mad_noble", "Mad Noble", "Noble",
    hp=200, attack=70, defense=50, speed=45,
)

NPC_KNIGHT_CLERIC = _make_npc(
    "npc_knight_cleric", "Knight Cleric", "Cleric",
    hp=195, attack=60, defense=55, speed=35,
)

NPC_ELDER_NOBLE = _make_npc(
    "npc_elder_noble", "Elder Noble", "Noble",
    hp=210, attack=75, defense=55, speed=50,
)

NPC_ELDER_MAGE = _make_npc(
    "npc_elder_mage", "Elder Mage", "Mage",
    hp=195, attack=85, defense=40, speed=55,
)

NPC_DWARVEN_FIGHTER = _make_npc(
    "npc_dwarven_fighter", "Dwarven Fighter", "Fighter",
    hp=215, attack=75, defense=65, speed=30,
)

# ── Special NPCs (Apex) ────────────────────────────────────────────────────────
NPC_APEX_FIGHTER = _make_npc(
    "npc_apex_fighter", "Apex Fighter", "Fighter",
    hp=240, attack=82, defense=55, speed=45,
    talent_name="Blood Frenzy",
    talent_text="Deals +10 damage to Exposed targets.",
)

NPC_APEX_CLERIC = _make_npc(
    "npc_apex_cleric", "Apex Cleric", "Cleric",
    hp=225, attack=65, defense=55, speed=40,
    talent_name="Divine Recovery",
    talent_text="Heals 20 HP each round.",
)

NPC_APEX_WARDEN = _make_npc(
    "npc_apex_warden", "Apex Warden", "Warden",
    hp=235, attack=65, defense=75, speed=30,
    talent_name="Bastion",
    talent_text="Frontline allies take -10 damage from abilities.",
)

# ── Dragon Head NPCs ───────────────────────────────────────────────────────────
NPC_DRAGON_NOBLE = _make_npc(
    "npc_dragon_noble", "Dragon Head Noble", "Noble",
    hp=300, attack=85, defense=65, speed=50,
    talent_name="Tyranny",
    talent_text="Enemies with 2+ statuses take +5 damage from all sources.",
    sig_options=[SOVEREIGN_EDICT, SOVEREIGN_EDICT, SOVEREIGN_EDICT],
)

NPC_DRAGON_MAGE = _make_npc(
    "npc_dragon_mage", "Dragon Head Mage", "Mage",
    hp=280, attack=90, defense=55, speed=55,
    talent_name="Tyranny",
    talent_text="Enemies with 2+ statuses take +5 damage from all sources.",
    sig_options=[CATACLYSM, CATACLYSM, CATACLYSM],
)

NPC_DRAGON_WARLOCK = _make_npc(
    "npc_dragon_warlock", "Dragon Head Warlock", "Warlock",
    hp=285, attack=82, defense=60, speed=45,
    talent_name="Tyranny",
    talent_text="Enemies with 2+ statuses take +5 damage from all sources.",
    sig_options=[DARK_AURA, DARK_AURA, DARK_AURA],
)

# ─────────────────────────────────────────────────────────────────────────────
# NPC REGISTRY (id → AdventurerDef)
# ─────────────────────────────────────────────────────────────────────────────
NPC_BY_ID: Dict[str, AdventurerDef] = {
    "npc_knight_warden":    NPC_KNIGHT_WARDEN,
    "npc_holy_cleric":      NPC_HOLY_CLERIC,
    "npc_rogue_bandit":     NPC_ROGUE_BANDIT,
    "npc_ranger_bandit":    NPC_RANGER_BANDIT,
    "npc_mage_acolyte":     NPC_MAGE_ACOLYTE,
    "npc_trained_fighter":  NPC_TRAINED_FIGHTER,
    "npc_royal_noble":      NPC_ROYAL_NOBLE,
    "npc_royal_ranger":     NPC_ROYAL_RANGER,
    "npc_shadow_warlock":   NPC_SHADOW_WARLOCK,
    "npc_shadow_mage":      NPC_SHADOW_MAGE,
    "npc_shadow_rogue":     NPC_SHADOW_ROGUE,
    "npc_pig_warden":       NPC_PIG_WARDEN,
    "npc_hunter_ranger":    NPC_HUNTER_RANGER,
    "npc_warlock_acolyte":  NPC_WARLOCK_ACOLYTE,
    "npc_mad_rogue":        NPC_MAD_ROGUE,
    "npc_mad_noble":        NPC_MAD_NOBLE,
    "npc_knight_cleric":    NPC_KNIGHT_CLERIC,
    "npc_elder_noble":      NPC_ELDER_NOBLE,
    "npc_elder_mage":       NPC_ELDER_MAGE,
    "npc_dwarven_fighter":  NPC_DWARVEN_FIGHTER,
    "npc_apex_fighter":     NPC_APEX_FIGHTER,
    "npc_apex_cleric":      NPC_APEX_CLERIC,
    "npc_apex_warden":      NPC_APEX_WARDEN,
    "npc_dragon_noble":     NPC_DRAGON_NOBLE,
    "npc_dragon_mage":      NPC_DRAGON_MAGE,
    "npc_dragon_warlock":   NPC_DRAGON_WARLOCK,
}

# ─────────────────────────────────────────────────────────────────────────────
# QUEST / MISSION DATACLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class QuestDef:
    quest_id: int
    mission_id: int
    key_preview: str                          # short description shown in quest select
    rewards: Dict                             # keys: "recruit", "sig_tier", "basics_tier",
                                              #        "items", "classes", "twists",
                                              #        "ranked_glory", "campaign_complete"
    enemy_lineup: Optional[List[Dict]] = None # list of 3 slot dicts; None for quest 0


@dataclass
class MissionDef:
    mission_id: int
    name: str
    quest_range: tuple      # (first_quest_id, last_quest_id) inclusive
    level_range: tuple      # (min_level, max_level)
    description: str


# ─────────────────────────────────────────────────────────────────────────────
# MISSION TABLE
# ─────────────────────────────────────────────────────────────────────────────

MISSION_TABLE: Dict[int, MissionDef] = {
    0: MissionDef(
        mission_id=0,
        name="Prologue",
        quest_range=(0, 0),
        level_range=(0, 0),
        description="The adventure begins.",
    ),
    1: MissionDef(
        mission_id=1,
        name="The Bandit Road",
        quest_range=(1, 4),
        level_range=(1, 4),
        description="A piece of the Dragon Jewel was spotted in a caravan on the High Road, more commonly, and alarmingly, known as the Bandit Road. Be swift before it falls into the wrong hands!",
    ),
    2: MissionDef(
        mission_id=2,
        name="The Shadow Court",
        quest_range=(5, 7),
        level_range=(5, 7),
        description="You hear whispers that the High Court has possession of a piece of the Dragon Jewel. A difficult task, but you're no stranger to heists. Well, hiring a heist crew anyways.",
    ),
    3: MissionDef(
        mission_id=3,
        name="The Sky Castle",
        quest_range=(8, 11),
        level_range=(8, 11),
        description="A kid in the sticks seems to have a piece of the Dragon Jewel. Shouldn't be too hard to get it, but it's probably best to hire a party just in case.",
    ),
    4: MissionDef(
        mission_id=4,
        name="The Great Hunt",
        quest_range=(12, 15),
        level_range=(12, 15),
        description="A local lord is offering a piece of the Dragon Jewel in exchange for killing a dangerous wild beast. Seems like an easy task for some adventurers!",
    ),
    5: MissionDef(
        mission_id=5,
        name="The Fallen Keep",
        quest_range=(16, 18),
        level_range=(16, 18),
        description="The map you bought from a shady traveler seems to indicate that piece of the Dragon Jewel is in an abandoned keep. Hopefully, it stays abandoned while you retrieve it.",
    ),
    6: MissionDef(
        mission_id=6,
        name="The Witch Hunt",
        quest_range=(19, 22),
        level_range=(19, 22),
        description="You recieved a tip from a drunk fisherman that a witch under a lake had a piece of the Dragon Jewel. Fortunately, you'd never hire adventurers who couldn't swim.",
    ),
    7: MissionDef(
        mission_id=7,
        name="The Cursed Woods",
        quest_range=(23, 26),
        level_range=(23, 26),
        description="Of course, a piece of the Dragon Jewel had to be in the infamous Cursed Woods. Better that some adventurers deal with it; it's much too scary for you.",
    ),
    8: MissionDef(
        mission_id=8,
        name="The Sunken Tower",
        quest_range=(27, 29),
        level_range=(27, 29),
        description="You recieved a tip from a long-haired girl that the final piece of the Dragon Jewel is in the Sunken Tower. A trap? Probably.",
    ),
    9: MissionDef(
        mission_id=9,
        name="The Dragon's Keepers",
        quest_range=(30, 30),
        level_range=(30, 30),
        description="Maybe it wasn't a great idea to put the Dragon Jewel together. Looks like the adventurers on your payroll will have to clean up the mess.",
    ),
    10: MissionDef(
        mission_id=10,
        name="The Cataclysm",
        quest_range=(31, 31),
        level_range=(30, 30),
        description="You never thought you were the saving the world type, but you also doomed the world, so it's on you to put together the best party of heroes up to the task.",
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# QUEST TABLE
# ─────────────────────────────────────────────────────────────────────────────
# Enemy lineup format per slot dict:
#   {"unit_type": str,   # ROSTER adventurer id OR NPC id
#    "sig_id": str,      # signature ability id (or "no_sig")
#    "basic1_id": str,   # first basic ability id
#    "basic2_id": str}   # second basic ability id

QUEST_TABLE: Dict[int, QuestDef] = {
    0: QuestDef(
        quest_id=0,
        mission_id=0,
        key_preview="Prologue — start your adventure",
        rewards={
            "recruit": [
                ("risa_redcloak", "crimson_fury"),
                ("robin_hooded_avenger", "snipe_shot"),
                ("aldric_lost_lamb", "benefactor"),
            ],
            "sig_tier": 1,
            "basics_tier": 2,
            "classes": ["Fighter", "Ranger", "Cleric"],
            "items": ["health_potion", "healing_tonic", "family_seal"],
        },
        enemy_lineup=None,
    ),
    1: QuestDef(
        quest_id=1,
        mission_id=1,
        key_preview="A knight blocks the road",
        rewards={"sig_tier": 2},
        enemy_lineup=[
            {"unit_type": "sir_roland",        "sig_id": "shimmering_valor", "basic1_id": "shield_bash", "basic2_id": "condemn"},
            {"unit_type": "npc_knight_warden", "sig_id": "no_sig",           "basic1_id": "shield_bash", "basic2_id": "condemn"},
            {"unit_type": "npc_holy_cleric",   "sig_id": "no_sig",           "basic1_id": "heal",        "basic2_id": "bless"},
        ],
    ),
    2: QuestDef(
        quest_id=2,
        mission_id=1,
        key_preview="Bandits ambush the road",
        rewards={"basics_tier": 3},
        enemy_lineup=[
            {"unit_type": "hunold_the_piper",  "sig_id": "haunting_rhythm", "basic1_id": "sneak_attack", "basic2_id": "post_bounty"},
            {"unit_type": "npc_rogue_bandit",  "sig_id": "no_sig",          "basic1_id": "sneak_attack", "basic2_id": "riposte"},
            {"unit_type": "npc_ranger_bandit", "sig_id": "no_sig",          "basic1_id": "hawkshot",     "basic2_id": "volley"},
        ],
    ),
    3: QuestDef(
        quest_id=3,
        mission_id=1,
        key_preview="A mage guards the crossing",
        rewards={"items": ["crafty_shield"]},
        enemy_lineup=[
            {"unit_type": "ashen_ella",        "sig_id": "midnight_dour",  "basic1_id": "fire_blast",   "basic2_id": "thunder_call"},
            {"unit_type": "npc_mage_acolyte",  "sig_id": "no_sig",         "basic1_id": "fire_blast",   "basic2_id": "thunder_call"},
            {"unit_type": "npc_trained_fighter","sig_id": "no_sig",        "basic1_id": "strike",       "basic2_id": "rend"},
        ],
    ),
    4: QuestDef(
        quest_id=4,
        mission_id=1,
        key_preview="The bandit lords unite",
        rewards={
            "recruit": [
                ("sir_roland", "shimmering_valor"),
                ("hunold_the_piper", "haunting_rhythm"),
                ("ashen_ella", "crowstorm"),
            ],
            "classes": ["Rogue", "Warden", "Mage"],
        },
        enemy_lineup=[
            {"unit_type": "sir_roland",       "sig_id": "shimmering_valor", "basic1_id": "shield_bash", "basic2_id": "condemn"},
            {"unit_type": "hunold_the_piper", "sig_id": "haunting_rhythm",  "basic1_id": "sneak_attack","basic2_id": "post_bounty"},
            {"unit_type": "ashen_ella",       "sig_id": "midnight_dour",    "basic1_id": "fire_blast",  "basic2_id": "thunder_call"},
        ],
    ),
    5: QuestDef(
        quest_id=5,
        mission_id=2,
        key_preview="The prince's honor guard",
        rewards={"items": ["main_gauche"]},
        enemy_lineup=[
            {"unit_type": "prince_charming",  "sig_id": "condescend",  "basic1_id": "impose",    "basic2_id": "decree"},
            {"unit_type": "npc_royal_noble",  "sig_id": "no_sig",      "basic1_id": "impose",    "basic2_id": "decree"},
            {"unit_type": "npc_royal_ranger", "sig_id": "no_sig",      "basic1_id": "hawkshot",  "basic2_id": "hunters_mark"},
        ],
    ),
    6: QuestDef(
        quest_id=6,
        mission_id=2,
        key_preview="Shadow court enforcers",
        rewards={"items": ["vampire_fang"]},
        enemy_lineup=[
            {"unit_type": "pinocchio",          "sig_id": "wooden_wallop", "basic1_id": "dark_grasp", "basic2_id": "soul_gaze"},
            {"unit_type": "npc_shadow_warlock", "sig_id": "no_sig",        "basic1_id": "dark_grasp", "basic2_id": "soul_gaze"},
            {"unit_type": "npc_shadow_mage",    "sig_id": "no_sig",        "basic1_id": "fire_blast", "basic2_id": "freezing_gale"},
        ],
    ),
    7: QuestDef(
        quest_id=7,
        mission_id=2,
        key_preview="The shadow court's finest",
        rewards={
            "recruit": [
                ("prince_charming", "condescend"),
                ("pinocchio", "wooden_wallop"),
            ],
            "classes": ["Noble", "Warlock"],
        },
        enemy_lineup=[
            {"unit_type": "prince_charming",  "sig_id": "condescend",    "basic1_id": "impose",       "basic2_id": "decree"},
            {"unit_type": "pinocchio",        "sig_id": "wooden_wallop", "basic1_id": "dark_grasp",   "basic2_id": "soul_gaze"},
            {"unit_type": "npc_shadow_rogue", "sig_id": "no_sig",        "basic1_id": "sneak_attack", "basic2_id": "post_bounty"},
        ],
    ),
    8: QuestDef(
        quest_id=8,
        mission_id=3,
        key_preview="Jack's bodyguards",
        rewards={},
        enemy_lineup=[
            {"unit_type": "little_jack",       "sig_id": "skyfall",  "basic1_id": "strike",   "basic2_id": "cleave"},
            {"unit_type": "npc_ranger_bandit", "sig_id": "no_sig",   "basic1_id": "hawkshot", "basic2_id": "volley"},
            {"unit_type": "npc_holy_cleric",   "sig_id": "no_sig",   "basic1_id": "heal",     "basic2_id": "bless"},
        ],
    ),
    9: QuestDef(
        quest_id=9,
        mission_id=3,
        key_preview="Constantine's royal entourage",
        rewards={"items": ["smoke_bomb"]},
        enemy_lineup=[
            {"unit_type": "lucky_constantine", "sig_id": "feline_gambit", "basic1_id": "sneak_attack", "basic2_id": "post_bounty"},
            {"unit_type": "npc_royal_noble",   "sig_id": "no_sig",        "basic1_id": "impose",       "basic2_id": "decree"},
            {"unit_type": "npc_royal_noble",   "sig_id": "no_sig",        "basic1_id": "impose",       "basic2_id": "decree"},
        ],
    ),
    10: QuestDef(
        quest_id=10,
        mission_id=3,
        key_preview="The pig's fortress",
        rewards={"items": ["iron_buckler"]},
        enemy_lineup=[
            {"unit_type": "porcus_iii",      "sig_id": "not_by_the_hair", "basic1_id": "shield_bash", "basic2_id": "slam"},
            {"unit_type": "npc_pig_warden",  "sig_id": "no_sig",          "basic1_id": "shield_bash", "basic2_id": "slam"},
            {"unit_type": "npc_pig_warden",  "sig_id": "no_sig",          "basic1_id": "shield_bash", "basic2_id": "slam"},
        ],
    ),
    11: QuestDef(
        quest_id=11,
        mission_id=3,
        key_preview="The sky castle trio",
        rewards={
            "recruit": [
                ("little_jack", "skyfall"),
                ("lucky_constantine", "feline_gambit"),
                ("porcus_iii", "not_by_the_hair"),
            ],
        },
        enemy_lineup=[
            {"unit_type": "little_jack",       "sig_id": "skyfall",        "basic1_id": "strike",       "basic2_id": "cleave"},
            {"unit_type": "lucky_constantine", "sig_id": "feline_gambit",  "basic1_id": "sneak_attack", "basic2_id": "post_bounty"},
            {"unit_type": "porcus_iii",        "sig_id": "not_by_the_hair","basic1_id": "shield_bash",  "basic2_id": "slam"},
        ],
    ),
    12: QuestDef(
        quest_id=12,
        mission_id=4,
        key_preview="Frederic's advance scouts",
        rewards={"items": ["hunters_net"]},
        enemy_lineup=[
            {"unit_type": "frederic",           "sig_id": "heros_charge",  "basic1_id": "hawkshot",     "basic2_id": "hunters_mark"},
            {"unit_type": "npc_trained_fighter","sig_id": "no_sig",        "basic1_id": "strike",       "basic2_id": "cleave"},
            {"unit_type": "npc_hunter_ranger",  "sig_id": "no_sig",        "basic1_id": "hawkshot",     "basic2_id": "trapping_blow"},
        ],
    ),
    13: QuestDef(
        quest_id=13,
        mission_id=4,
        key_preview="Liesl's ritual guards",
        rewards={"items": ["heart_amulet"]},
        enemy_lineup=[
            {"unit_type": "matchstick_liesl",    "sig_id": "cinder_blessing","basic1_id": "heal",       "basic2_id": "smite"},
            {"unit_type": "npc_mage_acolyte",    "sig_id": "no_sig",         "basic1_id": "fire_blast", "basic2_id": "thunder_call"},
            {"unit_type": "npc_warlock_acolyte", "sig_id": "no_sig",         "basic1_id": "dark_grasp", "basic2_id": "blood_pact"},
        ],
    ),
    14: QuestDef(
        quest_id=14,
        mission_id=4,
        key_preview="The mad tea party",
        rewards={"items": ["lightning_boots"]},
        enemy_lineup=[
            {"unit_type": "march_hare",       "sig_id": "tempus_fugit", "basic1_id": "fire_blast",   "basic2_id": "thunder_call"},
            {"unit_type": "npc_mad_rogue",    "sig_id": "no_sig",       "basic1_id": "sneak_attack", "basic2_id": "sucker_punch"},
            {"unit_type": "npc_mad_noble",    "sig_id": "no_sig",       "basic1_id": "impose",       "basic2_id": "edict"},
        ],
    ),
    15: QuestDef(
        quest_id=15,
        mission_id=4,
        key_preview="The great hunt leaders",
        rewards={
            "recruit": [
                ("frederic", "heros_charge"),
                ("matchstick_liesl", "cinder_blessing"),
                ("march_hare", "tempus_fugit"),
            ],
        },
        enemy_lineup=[
            {"unit_type": "frederic",         "sig_id": "heros_charge",   "basic1_id": "hawkshot",    "basic2_id": "hunters_mark"},
            {"unit_type": "matchstick_liesl", "sig_id": "cinder_blessing","basic1_id": "heal",        "basic2_id": "smite"},
            {"unit_type": "march_hare",       "sig_id": "tempus_fugit",   "basic1_id": "fire_blast",  "basic2_id": "thunder_call"},
        ],
    ),
    16: QuestDef(
        quest_id=16,
        mission_id=5,
        key_preview="The keep's honor guard",
        rewards={"items": ["misericorde"]},
        enemy_lineup=[
            {"unit_type": "green_knight",       "sig_id": "heros_bargain", "basic1_id": "impose",     "basic2_id": "edict"},
            {"unit_type": "npc_knight_warden",  "sig_id": "no_sig",        "basic1_id": "shield_bash","basic2_id": "condemn"},
            {"unit_type": "npc_knight_cleric",  "sig_id": "no_sig",        "basic1_id": "heal",       "basic2_id": "smite"},
        ],
    ),
    17: QuestDef(
        quest_id=17,
        mission_id=5,
        key_preview="Rumpel's golden bargain",
        rewards={"items": ["spiked_mail"]},
        enemy_lineup=[
            {"unit_type": "rumpelstiltskin",    "sig_id": "name_the_price","basic1_id": "dark_grasp", "basic2_id": "soul_gaze"},
            {"unit_type": "npc_mage_acolyte",   "sig_id": "no_sig",        "basic1_id": "fire_blast", "basic2_id": "thunder_call"},
            {"unit_type": "npc_trained_fighter","sig_id": "no_sig",        "basic1_id": "strike",     "basic2_id": "rend"},
        ],
    ),
    18: QuestDef(
        quest_id=18,
        mission_id=5,
        key_preview="The fallen keep's lords",
        rewards={
            "recruit": [
                ("green_knight", "heros_bargain"),
                ("rumpelstiltskin", "name_the_price"),
            ],
            "basics_tier": 5,
        },
        enemy_lineup=[
            {"unit_type": "green_knight",      "sig_id": "heros_bargain", "basic1_id": "impose",     "basic2_id": "edict"},
            {"unit_type": "rumpelstiltskin",   "sig_id": "name_the_price","basic1_id": "dark_grasp", "basic2_id": "soul_gaze"},
            {"unit_type": "npc_knight_cleric", "sig_id": "no_sig",        "basic1_id": "heal",       "basic2_id": "smite"},
        ],
    ),
    19: QuestDef(
        quest_id=19,
        mission_id=6,
        key_preview="Gretel's patrol",
        rewards={},
        enemy_lineup=[
            {"unit_type": "gretel",            "sig_id": "shove_over",  "basic1_id": "strike",     "basic2_id": "intimidate"},
            {"unit_type": "npc_ranger_bandit", "sig_id": "no_sig",      "basic1_id": "hawkshot",   "basic2_id": "volley"},
            {"unit_type": "npc_knight_warden", "sig_id": "no_sig",      "basic1_id": "shield_bash","basic2_id": "condemn"},
        ],
    ),
    20: QuestDef(
        quest_id=20,
        mission_id=6,
        key_preview="Reynard's ambush",
        rewards={},
        enemy_lineup=[
            {"unit_type": "reynard",            "sig_id": "size_up",   "basic1_id": "sneak_attack", "basic2_id": "riposte"},
            {"unit_type": "npc_shadow_mage",    "sig_id": "no_sig",    "basic1_id": "fire_blast",   "basic2_id": "freezing_gale"},
            {"unit_type": "npc_shadow_warlock", "sig_id": "no_sig",    "basic1_id": "dark_grasp",   "basic2_id": "soul_gaze"},
        ],
    ),
    21: QuestDef(
        quest_id=21,
        mission_id=6,
        key_preview="Lady's loch servants",
        rewards={"items": ["arcane_focus"]},
        enemy_lineup=[
            {"unit_type": "lady_of_reflections","sig_id": "drown_in_the_loch","basic1_id": "shield_bash","basic2_id": "condemn"},
            {"unit_type": "npc_elder_noble",    "sig_id": "no_sig",           "basic1_id": "decree",    "basic2_id": "edict"},
            {"unit_type": "npc_elder_mage",     "sig_id": "no_sig",           "basic1_id": "fire_blast","basic2_id": "arcane_wave"},
        ],
    ),
    22: QuestDef(
        quest_id=22,
        mission_id=6,
        key_preview="The witch hunt trio",
        rewards={
            "recruit": [
                ("gretel", "shove_over"),
                ("reynard", "size_up"),
                ("lady_of_reflections", "drown_in_the_loch"),
            ],
        },
        enemy_lineup=[
            {"unit_type": "gretel",              "sig_id": "shove_over",      "basic1_id": "strike",     "basic2_id": "intimidate"},
            {"unit_type": "reynard",             "sig_id": "size_up",         "basic1_id": "sneak_attack","basic2_id": "riposte"},
            {"unit_type": "lady_of_reflections", "sig_id": "drown_in_the_loch","basic1_id": "shield_bash","basic2_id": "condemn"},
        ],
    ),
    23: QuestDef(
        quest_id=23,
        mission_id=7,
        key_preview="Briar Rose's thorn guardians",
        rewards={},
        enemy_lineup=[
            {"unit_type": "briar_rose",      "sig_id": "thorn_snare", "basic1_id": "hawkshot",    "basic2_id": "trapping_blow"},
            {"unit_type": "npc_mad_noble",   "sig_id": "no_sig",      "basic1_id": "impose",      "basic2_id": "edict"},
            {"unit_type": "npc_mage_acolyte","sig_id": "no_sig",      "basic1_id": "fire_blast",  "basic2_id": "thunder_call"},
        ],
    ),
    24: QuestDef(
        quest_id=24,
        mission_id=7,
        key_preview="Aurora's dwarf defenders",
        rewards={"items": ["ancient_hourglass"]},
        enemy_lineup=[
            {"unit_type": "snowkissed_aurora",   "sig_id": "dictate_of_nature","basic1_id": "heal",   "basic2_id": "bless"},
            {"unit_type": "npc_dwarven_fighter", "sig_id": "no_sig",           "basic1_id": "strike", "basic2_id": "cleave"},
            {"unit_type": "npc_dwarven_fighter", "sig_id": "no_sig",           "basic1_id": "strike", "basic2_id": "cleave"},
        ],
    ),
    25: QuestDef(
        quest_id=25,
        mission_id=7,
        key_preview="The witch's congregation",
        rewards={},
        enemy_lineup=[
            {"unit_type": "witch_of_the_woods", "sig_id": "toil_and_trouble","basic1_id": "fire_blast","basic2_id": "thunder_call"},
            {"unit_type": "npc_shadow_rogue",   "sig_id": "no_sig",          "basic1_id": "sneak_attack","basic2_id": "post_bounty"},
            {"unit_type": "npc_holy_cleric",    "sig_id": "no_sig",          "basic1_id": "heal",      "basic2_id": "bless"},
        ],
    ),
    26: QuestDef(
        quest_id=26,
        mission_id=7,
        key_preview="The cursed woods trio",
        rewards={
            "recruit": [
                ("briar_rose", "thorn_snare"),
                ("snowkissed_aurora", "dictate_of_nature"),
                ("witch_of_the_woods", "toil_and_trouble"),
            ],
        },
        enemy_lineup=[
            {"unit_type": "briar_rose",        "sig_id": "thorn_snare",      "basic1_id": "hawkshot",    "basic2_id": "trapping_blow"},
            {"unit_type": "snowkissed_aurora", "sig_id": "dictate_of_nature","basic1_id": "heal",        "basic2_id": "bless"},
            {"unit_type": "witch_of_the_woods","sig_id": "toil_and_trouble", "basic1_id": "fire_blast",  "basic2_id": "thunder_call"},
        ],
    ),
    27: QuestDef(
        quest_id=27,
        mission_id=8,
        key_preview="Rapunzel's tower guards",
        rewards={},
        enemy_lineup=[
            {"unit_type": "rapunzel",           "sig_id": "golden_snare", "basic1_id": "impose",     "basic2_id": "decree"},
            {"unit_type": "npc_royal_ranger",   "sig_id": "no_sig",       "basic1_id": "hawkshot",   "basic2_id": "hunters_mark"},
            {"unit_type": "npc_shadow_warlock", "sig_id": "no_sig",       "basic1_id": "dark_grasp", "basic2_id": "soul_gaze"},
        ],
    ),
    28: QuestDef(
        quest_id=28,
        mission_id=8,
        key_preview="Asha's abyssal crew",
        rewards={"items": ["holy_diadem"]},
        enemy_lineup=[
            {"unit_type": "sea_wench_asha",     "sig_id": "abyssal_call","basic1_id": "dark_grasp", "basic2_id": "soul_gaze"},
            {"unit_type": "npc_trained_fighter","sig_id": "no_sig",      "basic1_id": "strike",     "basic2_id": "rend"},
            {"unit_type": "npc_mage_acolyte",   "sig_id": "no_sig",      "basic1_id": "fire_blast", "basic2_id": "thunder_call"},
        ],
    ),
    29: QuestDef(
        quest_id=29,
        mission_id=8,
        key_preview="The sunken tower's keepers",
        rewards={
            "recruit": [
                ("rapunzel", "golden_snare"),
                ("sea_wench_asha", "abyssal_call"),
            ],
            "sig_tier": 3,
        },
        enemy_lineup=[
            {"unit_type": "rapunzel",       "sig_id": "golden_snare", "basic1_id": "impose",     "basic2_id": "decree"},
            {"unit_type": "sea_wench_asha", "sig_id": "abyssal_call", "basic1_id": "dark_grasp", "basic2_id": "soul_gaze"},
            {"unit_type": "npc_royal_ranger","sig_id": "no_sig",      "basic1_id": "hawkshot",   "basic2_id": "hunters_mark"},
        ],
    ),
    30: QuestDef(
        quest_id=30,
        mission_id=9,
        key_preview="The Dragon's elite guard",
        rewards={"twists": True},
        enemy_lineup=[
            {"unit_type": "npc_apex_fighter", "sig_id": "no_sig", "basic1_id": "strike",     "basic2_id": "cleave"},
            {"unit_type": "npc_apex_cleric",  "sig_id": "no_sig", "basic1_id": "heal",       "basic2_id": "smite"},
            {"unit_type": "npc_apex_warden",  "sig_id": "no_sig", "basic1_id": "shield_bash","basic2_id": "slam"},
        ],
    ),
    31: QuestDef(
        quest_id=31,
        mission_id=10,
        key_preview="Face the Dragon's Heads",
        rewards={"ranked_glory": True, "campaign_complete": True},
        enemy_lineup=[
            {"unit_type": "npc_dragon_noble",   "sig_id": "sovereign_edict", "basic1_id": "impose",     "basic2_id": "decree"},
            {"unit_type": "npc_dragon_mage",    "sig_id": "cataclysm",       "basic1_id": "fire_blast", "basic2_id": "thunder_call"},
            {"unit_type": "npc_dragon_warlock", "sig_id": "dark_aura",       "basic1_id": "dark_grasp", "basic2_id": "soul_gaze"},
        ],
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# BUILD QUEST ENEMY TEAM
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_sig(defn: AdventurerDef, sig_id: str) -> Ability:
    """Look up a signature ability by id for this defn."""
    if sig_id == "no_sig":
        return NO_SIG
    # Check defn's own sig_options first
    for s in defn.sig_options:
        if s.id == sig_id:
            return s
    # Fallback: check global roster sig registry
    if sig_id in _ROSTER_SIG_BY_ID:
        return _ROSTER_SIG_BY_ID[sig_id]
    # Dragon head sigs
    for candidate in (SOVEREIGN_EDICT, CATACLYSM, DARK_AURA):
        if candidate.id == sig_id:
            return candidate
    return NO_SIG


def build_quest_enemy_team(quest_id: int) -> list:
    """
    Build and return a list of 3 pick dicts suitable for create_team().
    Each pick dict:
      {"definition": AdventurerDef, "signature": Ability,
       "basics": [Ability, Ability], "item": Item}
    """
    quest = QUEST_TABLE.get(quest_id)
    if quest is None or quest.enemy_lineup is None:
        raise ValueError(f"No enemy lineup for quest {quest_id}")

    picks = []
    for slot_data in quest.enemy_lineup:
        unit_type = slot_data["unit_type"]
        sig_id    = slot_data.get("sig_id", "no_sig")
        b1_id     = slot_data["basic1_id"]
        b2_id     = slot_data["basic2_id"]

        # Resolve definition
        if unit_type in ROSTER_BY_ID:
            defn = ROSTER_BY_ID[unit_type]
        elif unit_type in NPC_BY_ID:
            defn = NPC_BY_ID[unit_type]
        else:
            raise ValueError(f"Unknown unit type in quest {quest_id}: {unit_type!r}")

        sig = _resolve_sig(defn, sig_id)
        basic1 = _get_basic(b1_id)
        basic2 = _get_basic(b2_id)

        # Item: dragon heads have items; apex have items; others use NO_ITEM
        item = NO_ITEM
        if unit_type == "npc_dragon_noble":
            item = _get_item("crafty_shield")
        elif unit_type == "npc_dragon_mage":
            item = _get_item("misericorde")
        elif unit_type == "npc_dragon_warlock":
            item = _get_item("vampire_fang")
        elif unit_type == "npc_apex_fighter":
            item = _get_item("main_gauche")
        elif unit_type == "npc_apex_cleric":
            item = _get_item("heart_amulet")
        elif unit_type == "npc_apex_warden":
            item = _get_item("iron_buckler")

        picks.append({
            "definition": defn,
            "signature": sig,
            "basics": [basic1, basic2],
            "item": item,
        })

    return picks
