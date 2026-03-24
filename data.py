"""
data.py – all static game content, encoded directly from the Fabled rulebook.
AbilityMode fields that cannot be expressed as data are captured in `special`
strings and handled by ID in logic.py.
"""
from models import AbilityMode, Ability, Item, Artifact, AdventurerDef

# helper alias for "not available from this slot"
_NA = AbilityMode(unavailable=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  BASIC ABILITIES  (Appendix B)
# ═══════════════════════════════════════════════════════════════════════════════

# ── FIGHTER ───────────────────────────────────────────────────────────────────
STRIKE = Ability(
    id="strike", name="Strike", category="basic", passive=False,
    frontline=AbilityMode(power=60),
    backline=_NA,
)

REND = Ability(
    id="rend", name="Rend", category="basic", passive=False,
    frontline=AbilityMode(power=50, bonus_vs_low_hp=15),
    backline=AbilityMode(special="rend_back"),
)

CLEAVE = Ability(
    id="cleave", name="Cleave", category="basic", passive=False,
    frontline=AbilityMode(power=50, def_ignore_pct=15),
    backline=AbilityMode(special="cleave_back"),
)

FEINT = Ability(
    id="feint", name="Feint", category="basic", passive=False,
    frontline=AbilityMode(power=50, spd_buff=12, spd_buff_dur=2),
    backline=AbilityMode(spd_buff=12, spd_buff_dur=2),
)

INTIMIDATE = Ability(
    id="intimidate", name="Intimidate", category="basic", passive=False,
    frontline=AbilityMode(power=55, status="weaken", status_dur=2),
    backline=AbilityMode(status="weaken", status_dur=2),
)

# ── ROGUE ─────────────────────────────────────────────────────────────────────
SNEAK_ATTACK = Ability(
    id="sneak_attack", name="Sneak Attack", category="basic", passive=False,
    frontline=AbilityMode(power=50, bonus_if_not_acted=15),
    backline=AbilityMode(spd_debuff=10, spd_debuff_dur=2),
)

RIPOSTE = Ability(
    id="riposte", name="Riposte", category="basic", passive=False,
    frontline=AbilityMode(power=50, special="riposte_damage_reduction"),
    backline=AbilityMode(special="riposte_damage_reduction"),
)

POST_BOUNTY = Ability(
    id="post_bounty", name="Post Bounty", category="basic", passive=False,
    frontline=AbilityMode(power=50, status="expose", status_dur=2),
    backline=AbilityMode(status="expose", status_dur=2),
)

SUCKER_PUNCH = Ability(
    id="sucker_punch", name="Sucker Punch", category="basic", passive=False,
    frontline=AbilityMode(power=50, special="sucker_punch_front"),
    backline=AbilityMode(status="shock", status_dur=2),
)

FLEETFOOTED = Ability(
    id="fleetfooted", name="Fleetfooted", category="basic", passive=True,
    frontline=AbilityMode(special="fleetfooted_front"),
    backline=AbilityMode(special="fleetfooted_back"),
)

# ── WARDEN ────────────────────────────────────────────────────────────────────
SHIELD_BASH = Ability(
    id="shield_bash", name="Shield Bash", category="basic", passive=False,
    frontline=AbilityMode(power=45, guard_all_allies=True),
    backline=AbilityMode(guard_frontline_ally=True),
)

CONDEMN = Ability(
    id="condemn", name="Condemn", category="basic", passive=False,
    frontline=AbilityMode(power=45, atk_debuff=12, atk_debuff_dur=2),
    backline=AbilityMode(atk_debuff=10, atk_debuff_dur=2),
)

SLAM = Ability(
    id="slam", name="Slam", category="basic", passive=False,
    frontline=AbilityMode(power=45, special="slam_bonus_if_guarded"),
    backline=AbilityMode(guard_self=True, special="slam_back_guard"),
)

ARMORED = Ability(
    id="armored", name="Armored", category="basic", passive=True,
    frontline=AbilityMode(atk_buff=7, def_buff=12),
    backline=AbilityMode(def_buff=7),
)

STALWART = Ability(
    id="stalwart", name="Stalwart", category="basic", passive=True,
    frontline=AbilityMode(special="stalwart_front"),
    backline=AbilityMode(special="stalwart_back"),
)

# ── MAGE ──────────────────────────────────────────────────────────────────────
FIRE_BLAST = Ability(
    id="fire_blast", name="Fire Blast", category="basic", passive=False,
    frontline=AbilityMode(power=45, status="burn", status_dur=2),
    backline=AbilityMode(power=30, status="burn", status_dur=2),
)

THUNDER_CALL = Ability(
    id="thunder_call", name="Thunder Call", category="basic", passive=False,
    frontline=AbilityMode(power=45, status="shock", status_dur=2),
    backline=AbilityMode(power=30, status="shock", status_dur=2),
)

OMINOUS_GALE = Ability(
    id="ominous_gale", name="Ominous Gale", category="basic", passive=False,
    frontline=AbilityMode(power=45, bonus_vs_statused=15),
    backline=AbilityMode(power=30, special="ominous_gale_back"),
)

ARCANE_WAVE = Ability(
    id="arcane_wave", name="Arcane Wave", category="basic", passive=False,
    frontline=AbilityMode(power=70, special="arcane_wave_self_debuff"),
    backline=AbilityMode(power=40),
)

BREAKTHROUGH = Ability(
    id="breakthrough", name="Breakthrough", category="basic", passive=False,
    frontline=AbilityMode(atk_buff=12, atk_buff_dur=2, special="breakthrough_front"),
    backline=AbilityMode(atk_buff=12, atk_buff_dur=2),
)

# ── RANGER ────────────────────────────────────────────────────────────────────
HAWKSHOT = Ability(
    id="hawkshot", name="Hawkshot", category="basic", passive=False,
    frontline=AbilityMode(power=50, cant_redirect=True),
    backline=AbilityMode(power=40, cant_redirect=True),
)

VOLLEY = Ability(
    id="volley", name="Volley", category="basic", passive=False,
    frontline=AbilityMode(power=50, spread=True),
    backline=AbilityMode(power=40, spread=True),
)

TRAPPING_BLOW = Ability(
    id="trapping_blow", name="Trapping Blow", category="basic", passive=False,
    frontline=AbilityMode(power=45, special="trapping_blow_root_spotlight"),
    backline=AbilityMode(power=30, status="spotlight", status_dur=2),
)

HUNTERS_MARK = Ability(
    id="hunters_mark", name="Hunter's Mark", category="basic", passive=False,
    frontline=AbilityMode(power=45, special="hunters_mark_dot"),
    backline=AbilityMode(power=30, special="hunters_mark_dot"),
)

HUNTERS_BADGE = Ability(
    id="hunters_badge", name="Hunter's Badge", category="basic", passive=True,
    frontline=AbilityMode(atk_buff=12),
    backline=AbilityMode(atk_buff=10),
)

# ── CLERIC ────────────────────────────────────────────────────────────────────
HEAL = Ability(
    id="heal", name="Heal", category="basic", passive=False,
    frontline=AbilityMode(heal=65),
    backline=AbilityMode(heal=50),
)

BLESS = Ability(
    id="bless", name="Bless", category="basic", passive=False,
    frontline=AbilityMode(guard_target=True, atk_buff=7, atk_buff_dur=2),
    backline=AbilityMode(guard_target=True),
)

SMITE = Ability(
    id="smite", name="Smite", category="basic", passive=False,
    frontline=AbilityMode(power=40, status="burn", status_dur=2),
    backline=AbilityMode(power=40),
)

MEDIC = Ability(
    id="medic", name="Medic", category="basic", passive=True,
    frontline=AbilityMode(special="medic_front"),
    backline=AbilityMode(special="medic_back"),
)

PROTECTION = Ability(
    id="protection", name="Protection", category="basic", passive=True,
    frontline=AbilityMode(special="protection_front"),
    backline=AbilityMode(special="protection_back"),
)



# ── NOBLE ─────────────────────────────────────────────────────────────────────
IMPOSE = Ability(
    id="impose", name="Impose", category="basic", passive=False,
    frontline=AbilityMode(power=45, spd_debuff=12, spd_debuff_dur=2),
    backline=AbilityMode(power=30, spd_debuff=12, spd_debuff_dur=2),
)

EDICT = Ability(
    id="edict", name="Edict", category="basic", passive=False,
    frontline=AbilityMode(power=45, status="root", status_dur=2),
    backline=AbilityMode(power=30, status="spotlight", status_dur=2),
)

DECREE = Ability(
    id="decree", name="Decree", category="basic", passive=False,
    frontline=AbilityMode(power=45, atk_buff=12, atk_buff_dur=2),
    backline=AbilityMode(power=25, atk_debuff=12, atk_debuff_dur=2),
)

SUMMONS = Ability(
    id="summons", name="Summons", category="basic", passive=False,
    frontline=AbilityMode(special="summons_swap_cleanse"),
    backline=AbilityMode(special="summons_swap_cleanse"),
)

COMMAND = Ability(
    id="command", name="Command", category="basic", passive=True,
    frontline=AbilityMode(special="command_front"),
    backline=AbilityMode(special="command_back"),
)

# ── WARLOCK ───────────────────────────────────────────────────────────────────
DARK_GRASP = Ability(
    id="dark_grasp", name="Dark Grasp", category="basic", passive=False,
    frontline=AbilityMode(power=45, special="warlock_gain_malice_1"),
    backline=AbilityMode(power=40, special="warlock_spend1_weaken"),
)

SOUL_GAZE = Ability(
    id="soul_gaze", name="Soul Gaze", category="basic", passive=False,
    frontline=AbilityMode(power=40, special="warlock_spend1_expose"),
    backline=AbilityMode(power=35, special="warlock_gain_malice_1"),
)

BLOOD_PACT = Ability(
    id="blood_pact", name="Blood Pact", category="basic", passive=False,
    frontline=AbilityMode(special="blood_pact_front"),
    backline=AbilityMode(heal_self=30, special="blood_pact_back"),
)

CURSED_ARMOR = Ability(
    id="cursed_armor", name="Cursed Armor", category="basic", passive=True,
    frontline=AbilityMode(special="cursed_armor"),
    backline=AbilityMode(special="cursed_armor"),
)

VOID_STEP = Ability(
    id="void_step", name="Void Step", category="basic", passive=True,
    frontline=AbilityMode(special="void_step_front"),
    backline=AbilityMode(special="void_step_back"),
)

# ── CLASS POOLS ───────────────────────────────────────────────────────────────
CLASS_BASICS = {
    "Fighter": [STRIKE, REND, FEINT, CLEAVE, INTIMIDATE],
    "Rogue":   [SNEAK_ATTACK, RIPOSTE, POST_BOUNTY, SUCKER_PUNCH, FLEETFOOTED],
    "Warden":  [SHIELD_BASH, CONDEMN, SLAM, ARMORED, STALWART],
    "Mage":    [FIRE_BLAST, THUNDER_CALL, OMINOUS_GALE, ARCANE_WAVE, BREAKTHROUGH],
    "Ranger":  [HAWKSHOT, VOLLEY, HUNTERS_MARK, TRAPPING_BLOW, HUNTERS_BADGE],
    "Cleric":  [HEAL, BLESS, SMITE, MEDIC, PROTECTION],
    "Noble":   [IMPOSE, EDICT, DECREE, SUMMONS, COMMAND],
    "Warlock": [DARK_GRASP, SOUL_GAZE, BLOOD_PACT, CURSED_ARMOR, VOID_STEP],
}


# ═══════════════════════════════════════════════════════════════════════════════
#  ITEMS  (Appendix C)
# ═══════════════════════════════════════════════════════════════════════════════
HEALTH_POTION = Item(
    id="health_potion", name="Health Potion", passive=False,
    description="Heals 60 HP.", heal=60, heal_self_only=True, uses=99,
)
HEALING_TONIC = Item(
    id="healing_tonic", name="Healing Tonic", passive=False,
    description="Heals user or ally 45 HP.", heal=45, uses=99,
)
CRAFTY_SHIELD = Item(
    id="crafty_shield", name="Crafty Shield", passive=False,
    description="Guards user or ally for 2 rounds.", guard=True, status="guard",
    status_dur=2, uses=99,
)
LIGHTNING_BOOTS = Item(
    id="lightning_boots", name="Lightning Boots", passive=False,
    description="User has +15 Speed next round.", spd_buff=15, spd_buff_dur=2,
    uses=99,
)
MAIN_GAUCHE = Item(
    id="main_gauche", name="Main-Gauche", passive=False,
    description="User has +12 Attack for 2 rounds.", atk_buff=12, atk_buff_dur=2,
    uses=99,
)
IRON_BUCKLER = Item(
    id="iron_buckler", name="Iron Buckler", passive=False,
    description="User has +12 Defense for 2 rounds.", def_buff=12, def_buff_dur=2,
    uses=99,
)
SMOKE_BOMB = Item(
    id="smoke_bomb", name="Smoke Bomb", passive=False,
    description="User switches positions with an ally.", uses=99,
    special="smoke_bomb_swap",
)
HUNTERS_NET = Item(
    id="hunters_net", name="Hunter's Net", passive=False,
    description="Roots target for 2 rounds. They heal 50% less for the duration.", status="root", status_dur=2, uses=99, special="hunters_net",
)
ANCIENT_HOURGLASS = Item(
    id="ancient_hourglass", name="Ancient Hourglass", passive=False,
    description="User cannot act but cannot be targeted next round. Once per battle.",
    once_per_battle=True, uses=1, special="ancient_hourglass",
)
FAMILY_SEAL = Item(
    id="family_seal", name="Family Seal", passive=True,
    description="User's signature ability deals +10 damage.",
    signature_flat_bonus=10,
)
HOLY_DIADEM = Item(
    id="holy_diadem", name="Holy Diadem", passive=True,
    description="Once per battle, survive fatal damage at 1 HP and take no damage that round.",
    once_per_battle=True, special="holy_diadem",
)
VAMPIRE_FANG = Item(
    id="vampire_fang", name="Vampire Fang", passive=True,
    description="User's abilities have 7% lifesteal.", vamp=0.07,
)
SPIKED_MAIL = Item(
    id="spiked_mail", name="Spiked Mail", passive=True,
    description="Enemies damaging the user take 15 damage.", special="spiked_mail",
)
ARCANE_FOCUS = Item(
    id="arcane_focus", name="Arcane Focus", passive=True,
    description="User has +7 Attack when using abilities from the backline.",
    atk_bonus_back=7,
)
HEART_AMULET = Item(
    id="heart_amulet", name="Heart Amulet", passive=True,
    description="User's healing effects restore 10 additional HP.", flat_heal_bonus=10,
)
MISERICORDE = Item(
    id="misericorde", name="Misericorde", passive=True,
    description="User deals +10 more damage to targets with a status condition.",
    flat_vs_statused=10,
)

ITEMS = [
    HEALTH_POTION, HEALING_TONIC, CRAFTY_SHIELD, LIGHTNING_BOOTS,
    MAIN_GAUCHE, IRON_BUCKLER, SMOKE_BOMB, HUNTERS_NET,
    ANCIENT_HOURGLASS, FAMILY_SEAL, HOLY_DIADEM, VAMPIRE_FANG, SPIKED_MAIL,
    ARCANE_FOCUS, HEART_AMULET, MISERICORDE,
]


HOLY_GRAIL = Artifact(
    id="holy_grail", name="Holy Grail", reactive=False, cooldown=1,
    description="Heals target adventurer 45 HP.", heal=45,
)
DIVINE_APPLE = Artifact(
    id="divine_apple", name="Divine Apple", reactive=False, cooldown=1,
    description="Removes target adventurer's status conditions.", cleanse=True,
)
WINGED_SANDALS = Artifact(
    id="winged_sandals", name="Winged Sandals", reactive=False, cooldown=2,
    description="Target adventurer has +15 Speed for 2 rounds.",
    spd_buff=15, spd_buff_dur=2,
)
ACHILLES_SPEAR = Artifact(
    id="achilles_spear", name="Achilles' Spear", reactive=False, cooldown=2,
    description="Target adventurer has +15 Attack for 2 rounds.",
    atk_buff=15, atk_buff_dur=2,
)
GOLDEN_FLEECE = Artifact(
    id="golden_fleece", name="Golden Fleece", reactive=False, cooldown=2,
    description="Target adventurer has +15 Defense for 2 rounds.",
    def_buff=15, def_buff_dur=2,
)
MAGIC_MIRROR = Artifact(
    id="magic_mirror", name="Magic Mirror", reactive=False, cooldown=1,
    description="Swap two target ally adventurers.", special="magic_mirror",
)
CRACKED_STOPWATCH = Artifact(
    id="cracked_stopwatch", name="Cracked Stopwatch", reactive=False, cooldown=12,
    description="Target adventurer cannot act but cannot be targeted next round.",
    special="cracked_stopwatch",
)
MELUSINES_KNIFE = Artifact(
    id="melusines_knife", name="Melusine's Knife", reactive=False, cooldown=2,
    description="Target enemy adventurer has -10 Defense for 2 rounds.",
    def_debuff=10, def_debuff_dur=2,
)
LAST_PRISM = Artifact(
    id="last_prism", name="Last Prism", reactive=False, cooldown=2,
    description="Spotlights target adventurer for 2 rounds.",
    status="spotlight", status_dur=2,
)
NETTLE_SMOCK = Artifact(
    id="nettle_smock", name="Nettle Smock", reactive=False, cooldown=2,
    description="Roots target adventurer for 2 rounds. They heal 50% less for the duration.",
    status="root", status_dur=2, special="nettle_smock",
)
EXCALIBUR = Artifact(
    id="excalibur", name="Excalibur", reactive=True, cooldown=2,
    description="When an ally adventurer swaps to frontline, their signature abilities deal +10 damage for 2 rounds.",
    flat_damage_bonus=10, special="excalibur",
)
GODMOTHERS_WAND = Artifact(
    id="godmothers_wand", name="Godmother's Wand", reactive=True, cooldown=2,
    description="When an ally adventurer swaps from frontline to backline, their abilities used from the backline deal +10 damage for 2 rounds.",
    flat_damage_bonus=10, special="godmothers_wand",
)
MISERICORDE_ARTIFACT = Artifact(
    id="misericorde_artifact", name="Misericorde", reactive=True, cooldown=2,
    description="Whenever an enemy gets a second status condition, they take +10 damage for 2 rounds.",
    flat_damage_bonus=10, special="misericorde_artifact",
)
ENCHANTED_LAMP = Artifact(
    id="enchanted_lamp", name="Enchanted Lamp", reactive=True, cooldown=999,
    description="When an ally adventurer gets OHKOd, they survive at 1 HP and take no damage that round.",
    special="enchanted_lamp",
)
SELKIES_SKIN = Artifact(
    id="selkies_skin", name="Selkie's Skin", reactive=True, cooldown=2,
    description="When an ally adventurer is knocked below 50% max HP, their abilities have 10% lifesteal for 2 rounds.",
    vamp=0.10, special="selkies_skin",
)
GOOSE_QUILL = Artifact(
    id="goose_quill", name="Goose Quill", reactive=True, cooldown=2,
    description="When an ally adventurer uses a Twist Ability, they have +12 Attack, +12 Defense, and +12 Speed for 2 rounds.",
    special="goose_quill",
)
RED_HOOD = Artifact(
    id="red_hood", name="Red Hood", reactive=True, cooldown=2,
    description="When an ally adventurer swaps to frontline, Guard them for 2 rounds.",
    guard=True, status="guard", status_dur=2, special="red_hood",
)
CURSED_NEEDLE = Artifact(
    id="cursed_needle", name="Cursed Needle", reactive=True, cooldown=3,
    description="When inflicting a status condition, extend its duration by 1 round.",
    special="cursed_needle",
)
BLUEBEARDS_KEY = Artifact(
    id="bluebeards_key", name="Bluebeard's Key", reactive=True, cooldown=1,
    description="When healing an ally adventurer's HP, heal an additional +20 HP.",
    heal_bonus=20, special="bluebeards_key",
)
DURANDAL = Artifact(
    id="durandal", name="Durandal", reactive=True, cooldown=999,
    description="When a second ally adventurer is knocked out, their party may use another Twist Ability.",
    allow_extra_twist=1, special="durandal",
)

ARTIFACTS = [
    HOLY_GRAIL, DIVINE_APPLE, WINGED_SANDALS, ACHILLES_SPEAR, GOLDEN_FLEECE,
    MAGIC_MIRROR, CRACKED_STOPWATCH, MELUSINES_KNIFE, LAST_PRISM, NETTLE_SMOCK,
    EXCALIBUR, GODMOTHERS_WAND, MISERICORDE_ARTIFACT, ENCHANTED_LAMP,
    SELKIES_SKIN, GOOSE_QUILL, RED_HOOD, CURSED_NEEDLE, BLUEBEARDS_KEY,
    DURANDAL,
]

ARTIFACTS_BY_ID = {artifact.id: artifact for artifact in ARTIFACTS}

LEGACY_ITEM_TO_ARTIFACT_ID = {
    "health_potion": "holy_grail",
    "healing_tonic": "holy_grail",
    "crafty_shield": "red_hood",
    "lightning_boots": "winged_sandals",
    "main_gauche": "achilles_spear",
    "iron_buckler": "golden_fleece",
    "smoke_bomb": "magic_mirror",
    "hunters_net": "nettle_smock",
    "ancient_hourglass": "cracked_stopwatch",
    "family_seal": "excalibur",
    "holy_diadem": "enchanted_lamp",
    "vampire_fang": "selkies_skin",
    "spiked_mail": "red_hood",
    "arcane_focus": "godmothers_wand",
    "heart_amulet": "bluebeards_key",
    "misericorde": "misericorde_artifact",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  ADVENTURER ABILITIES + DEFINITIONS  (Appendix A)
# ═══════════════════════════════════════════════════════════════════════════════

# ── RISA REDCLOAK (Fighter) ───────────────────────────────────────────────────
RISA_S1 = Ability(
    id="crimson_fury", name="Crimson Fury", category="signature", passive=False,
    frontline=AbilityMode(power=70, special="crimson_fury_recoil"),
    backline=AbilityMode(status="weaken", status_dur=2, heal_self=30),
)
RISA_S2 = Ability(
    id="wolfs_pursuit", name="Wolf's Pursuit", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="wolfs_pursuit_retarget"),
    backline=AbilityMode(status="expose", status_dur=2),
)
RISA_S3 = Ability(
    id="blood_hunt", name="Blood Hunt", category="signature", passive=False,
    frontline=AbilityMode(power=65, double_vamp_no_base=True),
    backline=AbilityMode(special="blood_hunt_hp_avg"),
)
RISA_T = Ability(
    id="stomach_of_the_wolf", name="Stomach of the Wolf",
    category="twist", passive=False,
    frontline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="stomach_of_the_wolf"),
    backline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="stomach_of_the_wolf"),
)
RISA = AdventurerDef(
    id="risa_redcloak", name="Risa Redcloak", cls="Fighter",
    hp=288, attack=76, defense=74, speed=42,
    talent_name="Red and Wolf",
    talent_text="While below 50% max HP, Risa has +12 Attack, +12 Speed, and her abilities have 15% lifesteal.",
    sig_options=[RISA_S1, RISA_S2, RISA_S3], twist=RISA_T,
)

# ── LITTLE JACK (Fighter) ─────────────────────────────────────────────────────
JACK_S1 = Ability(
    id="skyfall", name="Skyfall", category="signature", passive=False,
    frontline=AbilityMode(power=85),
    backline=AbilityMode(status="expose", status_dur=2),
)
JACK_S2 = Ability(
    id="belligerence", name="Belligerence", category="signature", passive=True,
    frontline=AbilityMode(def_ignore_pct=20),
    backline=AbilityMode(special="belligerence_ignore_atk"),
)
JACK_S3 = Ability(
    id="beanstalk_crash", name="Beanstalk Crash", category="signature", passive=False,
    frontline=AbilityMode(power=65, status="root", status_dur=2),
    backline=AbilityMode(status="root", status_dur=2, special="magic_growth_power_buff"),
)
JACK_T = Ability(
    id="castle_on_cloud_nine", name="Castle on Cloud Nine", category="twist", passive=False,
    frontline=AbilityMode(def_buff=20, def_buff_dur=2, special="castle_on_cloud_nine"),
    backline=AbilityMode(def_buff=20, def_buff_dur=2, special="castle_on_cloud_nine"),
)
LITTLE_JACK = AdventurerDef(
    id="little_jack", name="Little Jack", cls="Fighter",
    hp=260, attack=87, defense=59, speed=74,
    talent_name="Giant Slayer",
    talent_text="Jack deals 15% bonus damage to enemies with higher max HP.",
    sig_options=[JACK_S1, JACK_S2, JACK_S3], twist=JACK_T,
)

# ── WITCH-HUNTER GRETEL (Fighter) ────────────────────────────────────────────
GRETEL_S1 = Ability(
    id="shove_over", name="Shove Over", category="signature", passive=False,
    frontline=AbilityMode(power=65, status="weaken", status_dur=2),
    backline=AbilityMode(status="weaken", status_dur=2,
                         special="shove_over_next_atk_bonus"),
)
GRETEL_S2 = Ability(
    id="hot_mitts", name="Hot Mitts", category="signature", passive=True,
    frontline=AbilityMode(special="hot_mitts_front"),
    backline=AbilityMode(special="hot_mitts_back"),
)
GRETEL_S3 = Ability(
    id="crumb_trail", name="Crumb Trail", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="crumb_trail_front"),
    backline=AbilityMode(special="crumb_trail_drop"),
)
GRETEL_T = Ability(
    id="into_the_oven", name="Into the Oven", category="twist", passive=False,
    frontline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="into_the_oven"),
    backline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="into_the_oven"),
)
GRETEL = AdventurerDef(
    id="gretel", name="Witch-Hunter Gretel", cls="Fighter",
    hp=268, attack=80, defense=64, speed=63,
    talent_name="Sugar Rush",
    talent_text="When Gretel knocks out an enemy, she has +15 attack and +15 speed for 2 rounds.",
    sig_options=[GRETEL_S1, GRETEL_S2, GRETEL_S3], twist=GRETEL_T,
)

# ── LUCKY CONSTANTINE (Rogue) ─────────────────────────────────────────────────
CONSTANTINE_S1 = Ability(
    id="subterfuge", name="Subterfuge", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="subterfuge_swap"),
    backline=AbilityMode(special="subterfuge_swap"),
)
CONSTANTINE_S2 = Ability(
    id="feline_gambit", name="Feline Gambit", category="signature", passive=False,
    frontline=AbilityMode(power=65, bonus_vs_backline=15),
    backline=AbilityMode(status="expose", status_dur=2),
)
CONSTANTINE_S3 = Ability(
    id="nine_lives", name="Nine Lives", category="signature", passive=True,
    frontline=AbilityMode(special="nine_lives"),
    backline=AbilityMode(special="nine_lives"),
)
CONSTANTINE_T = Ability(
    id="all_seeing", name="All-Seeing", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="all_seeing"),
    backline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="all_seeing"),
)
CONSTANTINE = AdventurerDef(
    id="lucky_constantine", name="Lucky Constantine", cls="Rogue",
    hp=244, attack=74, defense=41, speed=101,
    talent_name="Shadowstep",
    talent_text="Constantine ignores melee targeting restrictions against Exposed targets, but deals -7 damage to backline enemies, or +7 if they are idle.",
    sig_options=[CONSTANTINE_S2, CONSTANTINE_S1, CONSTANTINE_S3], twist=CONSTANTINE_T,
)

# ── HUNOLD THE PIPER (Rogue) ──────────────────────────────────────────────────
HUNOLD_S1 = Ability(
    id="haunting_rhythm", name="Haunting Rhythm", category="signature", passive=False,
    frontline=AbilityMode(power=60, status="shock", status_dur=2),
    backline=AbilityMode(status="shock", status_dur=2),
)
HUNOLD_S2 = Ability(
    id="dying_dance", name="Dying Dance", category="signature", passive=False,
    frontline=AbilityMode(power=65, special="dying_dance_front"),
    backline=AbilityMode(status="spotlight", status_dur=2),
)
HUNOLD_S3 = Ability(
    id="hypnotic_aura", name="Hypnotic Aura", category="signature", passive=True,
    frontline=AbilityMode(special="hypnotic_aura_front"),
    backline=AbilityMode(special="hypnotic_aura_back"),
)
HUNOLD_T = Ability(
    id="mass_hysteria", name="Mass Hysteria", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="mass_hysteria"),
    backline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="mass_hysteria"),
)
HUNOLD = AdventurerDef(
    id="hunold_the_piper", name="Hunold the Piper", cls="Rogue",
    hp=262, attack=74, defense=53, speed=76,
    talent_name="Electrifying Trance",
    talent_text="Shocked enemies take +12 damage from abilities.",
    sig_options=[HUNOLD_S1, HUNOLD_S2, HUNOLD_S3], twist=HUNOLD_T,
)

# ── REYNARD, LUPINE TRICKSTER (Rogue) ─────────────────────────────────────────
REYNARD_S1 = Ability(
    id="feign_weakness", name="Feign Weakness", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="feign_weakness_retaliate_45"),
    backline=AbilityMode(special="feign_weakness_retaliate_45"),
)
REYNARD_S2 = Ability(
    id="size_up", name="Size Up", category="signature", passive=False,
    frontline=AbilityMode(power=55, status="spotlight", status_dur=2),
    backline=AbilityMode(power=40, status="expose", status_dur=2),
)
REYNARD_S3 = Ability(
    id="cutpurse", name="Cutpurse", category="signature", passive=False,
    frontline=AbilityMode(power=50, spd_debuff=12, spd_debuff_dur=2,
                          spd_buff=12, spd_buff_dur=2),
    backline=AbilityMode(special="cutpurse_swap_frontline"),
)
REYNARD_T = Ability(
    id="smoke_and_mirrors", name="Smoke and Mirrors", category="twist", passive=False,
    frontline=AbilityMode(def_buff=20, def_buff_dur=2, special="smoke_and_mirrors"),
    backline=AbilityMode(def_buff=20, def_buff_dur=2, special="smoke_and_mirrors"),
)
REYNARD = AdventurerDef(
    id="reynard", name="Reynard, Lupine Trickster", cls="Rogue",
    hp=240, attack=85, defense=45, speed=90,
    talent_name="Cunning Dodge",
    talent_text="Reynard takes 50% damage from the first ability each battle. Refreshes when he swaps.",
    sig_options=[REYNARD_S2, REYNARD_S1, REYNARD_S3], twist=REYNARD_T,
)

# ── SIR ROLAND (Warden) ───────────────────────────────────────────────────────
ROLAND_S1 = Ability(
    id="shimmering_valor", name="Shimmering Valor", category="signature", passive=False,
    frontline=AbilityMode(special="shimmering_valor_front"),
    backline=AbilityMode(special="shimmering_valor_back"),
)
ROLAND_S2 = Ability(
    id="knights_challenge", name="Knight's Challenge", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="taunt_target"),
    backline=AbilityMode(special="taunt_front_ranged"),
)
ROLAND_S3 = Ability(
    id="banner_of_command", name="Banner of Command", category="signature", passive=True,
    frontline=AbilityMode(special="banner_of_command"),
    backline=AbilityMode(special="banner_of_command"),
)
ROLAND_T = Ability(
    id="purehearted_stand", name="Purehearted Stand", category="twist", passive=False,
    frontline=AbilityMode(heal_self=120, atk_buff=20, atk_buff_dur=2, special="purehearted_stand"),
    backline=AbilityMode(heal_self=120, atk_buff=20, atk_buff_dur=2, special="purehearted_stand"),
)
ROLAND = AdventurerDef(
    id="sir_roland", name="Sir Roland", cls="Warden",
    hp=302, attack=43, defense=80, speed=20,
    talent_name="Silver Aegis",
    talent_text="Roland takes 65% less damage from the first incoming ability after swapping to frontline.",
    sig_options=[ROLAND_S1, ROLAND_S2, ROLAND_S3], twist=ROLAND_T,
)

# ── PORCUS III (Warden) ───────────────────────────────────────────────────────
PORCUS_S1 = Ability(
    id="not_by_the_hair", name="Not By The Hair", category="signature", passive=False,
    frontline=AbilityMode(special="nbth_self_reduce"),
    backline=AbilityMode(special="nbth_ally_reduce"),
)
PORCUS_S2 = Ability(
    id="porcine_honor", name="Porcine Honor", category="signature", passive=True,
    frontline=AbilityMode(special="porcine_honor_self"),
    backline=AbilityMode(special="porcine_honor_ally"),
)
PORCUS_S3 = Ability(
    id="sturdy_home", name="Sturdy Fortress", category="signature", passive=True,
    frontline=AbilityMode(special="sturdy_home_front"),
    backline=AbilityMode(special="sturdy_home_back"),
)
PORCUS_T = Ability(
    id="unfettered", name="Unfettered", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=100, atk_buff_dur=2, spd_buff=100, spd_buff_dur=2, special="unfettered"),
    backline=AbilityMode(atk_buff=100, atk_buff_dur=2, spd_buff=100, spd_buff_dur=2, special="unfettered"),
)
PORCUS = AdventurerDef(
    id="porcus_iii", name="Porcus III", cls="Warden",
    hp=318, attack=37, defense=82, speed=13,
    talent_name="Bricklayer",
    talent_text="If an incoming ability would deal 20% max HP or more to Porcus, reduce damage by 35% and Weaken attacker for 2 rounds.",
    sig_options=[PORCUS_S1, PORCUS_S2, PORCUS_S3], twist=PORCUS_T,
)

# ── LADY OF REFLECTIONS (Warden) ─────────────────────────────────────────────
LADY_S1 = Ability(
    id="postmortem_passage", name="Postmortem Passage", category="signature", passive=True,
    frontline=AbilityMode(special="postmortem_passage"),
    backline=AbilityMode(special="postmortem_passage"),
)
LADY_S2 = Ability(
    id="drown_in_the_loch", name="Drown in the Loch", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="drown_dmg_bonus"),
    backline=AbilityMode(special="drown_dmg_bonus"),
)
LADY_S3 = Ability(
    id="lakes_gift", name="Lake's Gift", category="signature", passive=False,
    frontline=AbilityMode(special="lakes_gift_pool_front"),
    backline=AbilityMode(special="lakes_gift_pool_back"),
)
LADY_T = Ability(
    id="journey_to_avalon", name="Journey to Avalon", category="twist", passive=False,
    frontline=AbilityMode(def_buff=20, def_buff_dur=2, special="journey_to_avalon"),
    backline=AbilityMode(def_buff=20, def_buff_dur=2, special="journey_to_avalon"),
)
LADY = AdventurerDef(
    id="lady_of_reflections", name="Lady of Reflections", cls="Warden",
    hp=316, attack=46, defense=68, speed=40,
    talent_name="Reflecting Pool",
    talent_text="The Lady reflects 12% of incoming damage onto the attacker, 15% if the attacker is backline.",
    sig_options=[LADY_S2, LADY_S1, LADY_S3], twist=LADY_T,
)

# ── ASHEN ELLA (Mage) ─────────────────────────────────────────────────────────
ELLA_S1 = Ability(
    id="midnight_dour", name="Midnight Dour", category="signature", passive=True,
    frontline=AbilityMode(special="midnight_dour_swap"),
    backline=AbilityMode(heal_self=40),
)
ELLA_S2 = Ability(
    id="crowstorm", name="Crowstorm", category="signature", passive=False,
    frontline=AbilityMode(power=60, spread=True, status="burn", status_dur=2),
    backline=AbilityMode(status="burn", status_dur=2,
                         special="ella_ignore_two_lives"),
)
ELLA_S3 = Ability(
    id="fae_blessing", name="Fae Blessing", category="signature", passive=False,
    frontline=AbilityMode(guard_self=True, atk_buff=12, atk_buff_dur=2,
                          spd_buff=12, spd_buff_dur=2),
    backline=AbilityMode(heal=50, special="ella_ignore_two_lives"),
)
ELLA_T = Ability(
    id="struck_midnight", name="Clock Struck Twelve", category="twist", passive=False,
    frontline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="struck_midnight_untargetable"),
    backline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="struck_midnight_untargetable"),
)
ELLA = AdventurerDef(
    id="ashen_ella", name="Ashen Ella", cls="Mage",
    hp=213, attack=83, defense=45, speed=89,
    talent_name="Two Lives",
    talent_text="Ella is untargetable while in the backline but can only use abilities while in the frontline.",
    sig_options=[ELLA_S2, ELLA_S1, ELLA_S3], twist=ELLA_T,
)

# ── MARCH HARE (Mage) ─────────────────────────────────────────────────────────
HARE_S1 = Ability(
    id="tempus_fugit", name="Tempus Fugit", category="signature", passive=False,
    frontline=AbilityMode(power=60, status="shock", status_dur=2),
    backline=AbilityMode(power=35, special="tempus_fugit_back"),
)
HARE_S2 = Ability(
    id="rabbit_hole", name="Rabbit Hole", category="signature", passive=False,
    frontline=AbilityMode(special="rabbit_hole_extra_action"),
    backline=AbilityMode(special="rabbit_hole_swap"),
)
HARE_S3 = Ability(
    id="nebulous_ides", name="Nebulous Ides", category="signature", passive=False,
    frontline=AbilityMode(power=60, bonus_if_target_acted=15),
    backline=AbilityMode(power=35, special="nebulous_ides_back"),
)
HARE_T = Ability(
    id="stitch_in_time", name="Stitch In Time", category="twist", passive=False,
    frontline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="stitch_extra_action_now"),
    backline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="stitch_extra_action_now"),
)
MARCH_HARE = AdventurerDef(
    id="march_hare", name="March Hare", cls="Mage",
    hp=212, attack=74, defense=38, speed=96,
    talent_name="On Time!",
    talent_text="While the March Hare is frontline, the frontline enemy has -12 speed.",
    sig_options=[HARE_S1, HARE_S2, HARE_S3], twist=HARE_T,
)

# ── WITCH OF THE WOODS (Mage) ─────────────────────────────────────────────────
WITCH_S1 = Ability(
    id="toil_and_trouble", name="Toil and Trouble", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="toil_spread_status_right"),
    backline=AbilityMode(power=35, status="burn", status_dur=2),
)
WITCH_S2 = Ability(
    id="cauldron_bubble", name="Cauldron Bubble", category="signature", passive=False,
    frontline=AbilityMode(power=60, spread=True, special="cauldron_extend_status"),
    backline=AbilityMode(power=35, spread=True, special="cauldron_extend_status"),
)
WITCH_S3 = Ability(
    id="crawling_abode", name="Crawling Abode", category="signature", passive=True,
    frontline=AbilityMode(special="crawling_abode"),
    backline=AbilityMode(special="crawling_abode"),
)
WITCH_T = Ability(
    id="vile_sabbath", name="Vile Sabbath", category="twist", passive=False,
    frontline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="vile_sabbath"),
    backline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="vile_sabbath"),
)
WITCH = AdventurerDef(
    id="witch_of_the_woods", name="Witch of the Woods", cls="Mage",
    hp=198, attack=80, defense=39, speed=98,
    talent_name="Double Double",
    talent_text="Whenever the Witch damages a statused target, spread the target's last inflicted status to the enemy adjacent to their left.",
    sig_options=[WITCH_S1, WITCH_S2, WITCH_S3], twist=WITCH_T,
)

# ── BRIAR ROSE (Ranger) ───────────────────────────────────────────────────────
BRIAR_S1 = Ability(
    id="thorn_snare", name="Thorn Snare", category="signature", passive=False,
    frontline=AbilityMode(power=50, status="root", status_dur=2, spread=True),
    backline=AbilityMode(power=35, special="thorn_snare_back"),
)
BRIAR_S2 = Ability(
    id="creeping_doubt", name="Creeping Doubt", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="creeping_doubt_front"),
    backline=AbilityMode(power=30, status="root", status_dur=2),
)
BRIAR_S3 = Ability(
    id="garden_of_thorns", name="Garden of Thorns", category="signature", passive=True,
    frontline=AbilityMode(special="garden_of_thorns_attack"),
    backline=AbilityMode(special="garden_of_thorns_swap"),
)
BRIAR_T = Ability(
    id="falling_kingdom", name="Falling Kingdom", category="twist", passive=False,
    frontline=AbilityMode(def_buff=20, def_buff_dur=2, special="falling_kingdom"),
    backline=AbilityMode(def_buff=20, def_buff_dur=2, special="falling_kingdom"),
)
BRIAR_ROSE = AdventurerDef(
    id="briar_rose", name="Briar Rose", cls="Ranger",
    hp=226, attack=57, defense=49, speed=88,
    talent_name="Curse of Sleeping",
    talent_text="The lowest health Rooted enemy is unable to act each round but loses Rooting and can't be Rooted next round.",
    sig_options=[BRIAR_S1, BRIAR_S2, BRIAR_S3], twist=BRIAR_T,
)

# ── FREDERIC THE BEASTSLAYER (Ranger) ─────────────────────────────────────────
FRED_S1 = Ability(
    id="heros_charge", name="Hero's Charge", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="heros_charge_ignore_pride_front"),
    backline=AbilityMode(power=20, spd_buff=15, spd_buff_dur=2),
)
FRED_S2 = Ability(
    id="on_the_hunt", name="On the Hunt", category="signature", passive=False,
    frontline=AbilityMode(power=50, atk_buff=12, atk_buff_dur=2),
    backline=AbilityMode(power=20, status="spotlight", status_dur=2),
)
FRED_S3 = Ability(
    id="jovial_shot", name="Jovial Shot", category="signature", passive=False,
    frontline=AbilityMode(power=45, status="weaken", status_dur=2),
    backline=AbilityMode(heal_self=80, self_status="weaken", self_status_dur=2),
)
FRED_T = Ability(
    id="raze_the_village", name="Raze the Village", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="raze_the_village"),
    backline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="raze_the_village"),
)
FREDERIC = AdventurerDef(
    id="frederic", name="Frederic the Beastslayer", cls="Ranger",
    hp=236, attack=68, defense=54, speed=67,
    talent_name="Heedless Pride",
    talent_text="Frederic deals 15% bonus damage to the enemy frontline and takes 7% bonus damage from the enemy frontline.",
    sig_options=[FRED_S1, FRED_S2, FRED_S3], twist=FRED_T,
)

# ── ROBIN, HOODED AVENGER (Ranger) ────────────────────────────────────────────
ROBIN_S1 = Ability(
    id="snipe_shot", name="Snipe Shot", category="signature", passive=False,
    frontline=AbilityMode(power=50),
    backline=AbilityMode(power=30, ignore_guard=True),
)
ROBIN_S2 = Ability(
    id="spread_fortune", name="Spread Fortune", category="signature", passive=True,
    frontline=AbilityMode(special="spread_fortune_front"),
    backline=AbilityMode(special="spread_fortune_back"),
)
ROBIN_S3 = Ability(
    id="bring_down", name="Bring Down", category="signature", passive=False,
    frontline=AbilityMode(power=50, special="bring_down_steal_atk"),
    backline=AbilityMode(power=30, status="root", status_dur=2),
)
ROBIN_T = Ability(
    id="lawless", name="Lawless", category="twist", passive=False,
    frontline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="lawless"),
    backline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="lawless"),
)
ROBIN = AdventurerDef(
    id="robin_hooded_avenger", name="Robin, Hooded Avenger", cls="Ranger",
    hp=221, attack=69, defense=41, speed=89,
    talent_name="Keen Eye",
    talent_text="Robin deals +7 damage with abilities to backline enemies.",
    sig_options=[ROBIN_S1, ROBIN_S2, ROBIN_S3], twist=ROBIN_T,
)

# ── ALDRIC, LOST LAMB (Cleric) ────────────────────────────────────────────────
ALDRIC_S1 = Ability(
    id="benefactor", name="Benefactor", category="signature", passive=True,
    frontline=AbilityMode(special="benefactor_front"),
    backline=AbilityMode(special="benefactor_back"),
)
ALDRIC_S2 = Ability(
    id="sanctuary", name="Sanctuary", category="signature", passive=True,
    frontline=AbilityMode(special="sanctuary_front"),
    backline=AbilityMode(special="sanctuary_back"),
)
ALDRIC_S3 = Ability(
    id="repentance", name="Repentance", category="signature", passive=False,
    frontline=AbilityMode(power=45, vamp=0.40, special="repentance_front"),
    backline=AbilityMode(power=30, vamp=0.25),
)
ALDRIC_T = Ability(
    id="redemption", name="Redemption", category="twist", passive=False,
    frontline=AbilityMode(def_buff=20, def_buff_dur=2, special="redemption"),
    backline=AbilityMode(def_buff=20, def_buff_dur=2, special="redemption"),
)
ALDRIC = AdventurerDef(
    id="aldric_lost_lamb", name="Aldric, Lost Lamb", cls="Cleric",
    hp=275, attack=47, defense=67, speed=41,
    talent_name="All-Caring",
    talent_text="Aldric's healing effects Guard the recipient for 2 rounds.",
    sig_options=[ALDRIC_S1, ALDRIC_S2, ALDRIC_S3], twist=ALDRIC_T,
)

# ── MATCHSTICK LIESL (Cleric) ─────────────────────────────────────────────────
LIESL_S1 = Ability(
    id="cinder_blessing", name="Cinder Blessing", category="signature", passive=False,
    frontline=AbilityMode(special="cinder_blessing_avg"),
    backline=AbilityMode(heal_self=70),
)
LIESL_S2 = Ability(
    id="flame_of_renewal", name="Flame of Renewal", category="signature", passive=True,
    frontline=AbilityMode(special="flame_of_renewal"),
    backline=AbilityMode(special="flame_of_renewal"),
)
LIESL_S3 = Ability(
    id="cauterize", name="Cauterize", category="signature", passive=False,
    frontline=AbilityMode(power=55, status="no_heal", status_dur=2),
    backline=AbilityMode(power=35, status="no_heal", status_dur=2),
)
LIESL_T = Ability(
    id="cleansing_inferno", name="Cleansing Inferno", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="cleansing_inferno"),
    backline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="cleansing_inferno"),
)
LIESL = AdventurerDef(
    id="matchstick_liesl", name="Matchstick Liesl", cls="Cleric",
    hp=240, attack=55, defense=48, speed=77,
    talent_name="Purifying Flame",
    talent_text="Liesl's healing effects grant Burn immunity to recipients for 2 rounds, and they Burn the target of their next ability for 2 rounds.",
    sig_options=[LIESL_S1, LIESL_S2, LIESL_S3], twist=LIESL_T,
)

# ── SNOWKISSED AURORA (Cleric) ────────────────────────────────────────────────
AURORA_S1 = Ability(
    id="toxin_purge", name="Toxin Purge", category="signature", passive=False,
    frontline=AbilityMode(special="toxin_purge_all"),
    backline=AbilityMode(special="toxin_purge_last"),
)
AURORA_S2 = Ability(
    id="dictate_of_nature", name="Dictate of Nature", category="signature", passive=False,
    frontline=AbilityMode(power=45, heal_lowest=35),
    backline=AbilityMode(power=30, heal_lowest=20),
)
AURORA_S3 = Ability(
    id="birdsong", name="Birdsong", category="signature", passive=True,
    frontline=AbilityMode(special="birdsong_front"),
    backline=AbilityMode(special="birdsong_back"),
)
AURORA_T = Ability(
    id="deathlike_slumber", name="Deathlike Slumber", category="twist", passive=False,
    frontline=AbilityMode(def_buff=20, def_buff_dur=2, special="deathlike_slumber"),
    backline=AbilityMode(def_buff=20, def_buff_dur=2, special="deathlike_slumber"),
)
AURORA = AdventurerDef(
    id="snowkissed_aurora", name="Snowkissed Aurora", cls="Cleric",
    hp=255, attack=44, defense=56, speed=65,
    talent_name="Innocent Heart",
    talent_text="Whenever Aurora or an ally loses a status condition, they have +7 defense for 2 rounds.",
    sig_options=[AURORA_S1, AURORA_S2, AURORA_S3], twist=AURORA_T,
)



# ── PRINCE CHARMING (Noble) ─────────────────────────────────────────────────
PRINCE_S1 = Ability(
    id="condescend", name="Condescend", category="signature", passive=False,
    frontline=AbilityMode(power=50, def_debuff=10, def_debuff_dur=2),
    backline=AbilityMode(power=35, special="condescend_back"),
)
PRINCE_S2 = Ability(
    id="gallant_charge", name="Gallant Charge", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="gallant_charge_front"),
    backline=AbilityMode(power=30, spd_buff=12, spd_buff_dur=2),
)
PRINCE_S3 = Ability(
    id="chosen_one", name="Chosen One", category="signature", passive=True,
    frontline=AbilityMode(special="chosen_one"),
    backline=AbilityMode(special="chosen_one"),
)
PRINCE_T = Ability(
    id="happily_ever_after", name="Happily Ever After", category="twist", passive=False,
    frontline=AbilityMode(def_buff=20, def_buff_dur=2, special="happily_ever_after"),
    backline=AbilityMode(def_buff=20, def_buff_dur=2, special="happily_ever_after"),
)
PRINCE = AdventurerDef(
    id="prince_charming", name="Prince Charming", cls="Noble",
    hp=245, attack=55, defense=70, speed=40,
    talent_name="Mesmerizing",
    talent_text="While Prince Charming is frontline, enemies that target allies get -10 attack for 2 rounds.",
    sig_options=[PRINCE_S1, PRINCE_S2, PRINCE_S3], twist=PRINCE_T,
)

# ── GREEN KNIGHT (Noble) ────────────────────────────────────────────────────
GREEN_S1 = Ability(
    id="heros_bargain", name="Hero's Bargain", category="signature", passive=False,
    frontline=AbilityMode(power=50, status="root", status_dur=2),
    backline=AbilityMode(power=40, special="heros_bargain_back"),
)
GREEN_S2 = Ability(
    id="natural_order", name="Natural Order", category="signature", passive=True,
    frontline=AbilityMode(special="natural_order_front"),
    backline=AbilityMode(special="natural_order_back"),
)
GREEN_S3 = Ability(
    id="awaited_blow", name="Awaited Blow", category="signature", passive=True,
    frontline=AbilityMode(special="awaited_blow_front"),
    backline=AbilityMode(special="awaited_blow_back"),
)
GREEN_T = Ability(
    id="fated_duel", name="Fated Duel", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="fated_duel"),
    backline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="fated_duel"),
)
GREEN_KNIGHT = AdventurerDef(
    id="green_knight", name="Green Knight", cls="Noble",
    hp=266, attack=60, defense=65, speed=20,
    talent_name="Challenge Accepted",
    talent_text="The Green Knight deals +15 damage to the target across from him.",
    sig_options=[GREEN_S1, GREEN_S2, GREEN_S3], twist=GREEN_T,
)

# ── RAPUNZEL THE GOLDEN (Noble) ──────────────────────────────────────────────
RAPUNZEL_S1 = Ability(
    id="golden_snare", name="Golden Snare", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="golden_snare_front"),
    backline=AbilityMode(power=35, status="root", status_dur=2),
)
RAPUNZEL_S2 = Ability(
    id="lower_guard", name="Lower Guard", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="lower_guard_front"),
    backline=AbilityMode(power=30, def_debuff=12, def_debuff_dur=2),
)
RAPUNZEL_S3 = Ability(
    id="ivory_tower", name="Ivory Tower", category="signature", passive=True,
    frontline=AbilityMode(special="ivory_tower_front"),
    backline=AbilityMode(special="ivory_tower_back"),
)
RAPUNZEL_T = Ability(
    id="severed_tether", name="Severed Tether", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=30, atk_buff_dur=2, spd_buff=30, spd_buff_dur=2, special="severed_tether"),
    backline=AbilityMode(atk_buff=30, atk_buff_dur=2, spd_buff=30, spd_buff_dur=2, special="severed_tether"),
)
RAPUNZEL = AdventurerDef(
    id="rapunzel", name="Rapunzel the Golden", cls="Noble",
    hp=258, attack=68, defense=60, speed=30,
    talent_name="Flowing Locks",
    talent_text="Rapunzel ignores all targeting restrictions once per battle. Refreshes when she ends the round in the backline.",
    sig_options=[RAPUNZEL_S1, RAPUNZEL_S2, RAPUNZEL_S3], twist=RAPUNZEL_T,
)

# ── PINOCCHIO, CURSED PUPPET (Warlock) ───────────────────────────────────────
PINOCCHIO_S1 = Ability(
    id="wooden_wallop", name="Wooden Wallop", category="signature", passive=False,
    frontline=AbilityMode(power=45, special="wooden_wallop_front"),
    backline=AbilityMode(power=30, special="warlock_gain_malice_1"),
)
PINOCCHIO_S2 = Ability(
    id="cut_the_strings", name="Cut the Strings", category="signature", passive=False,
    frontline=AbilityMode(power=65, status="expose", status_dur=2),
    backline=AbilityMode(power=40, special="cut_strings_back"),
)
PINOCCHIO_S3 = Ability(
    id="become_real", name="Become Real", category="signature", passive=True,
    frontline=AbilityMode(special="become_real_front"),
    backline=AbilityMode(special="become_real_back"),
)
PINOCCHIO_T = Ability(
    id="blue_faerie_boon", name="Blue Faerie's Boon", category="twist", passive=False,
    frontline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="blue_faerie_boon"),
    backline=AbilityMode(spd_buff=20, spd_buff_dur=2, special="blue_faerie_boon"),
)
PINOCCHIO = AdventurerDef(
    id="pinocchio", name="Pinocchio, Cursed Puppet", cls="Warlock",
    hp=220, attack=53, defense=40, speed=82,
    talent_name="Growing Pains",
    talent_text="When Pinocchio ends the round in the frontline, he gains 1 Malice, up to 6. Pinocchio has +5 attack and +5 defense for each Malice.",
    sig_options=[PINOCCHIO_S1, PINOCCHIO_S2, PINOCCHIO_S3], twist=PINOCCHIO_T,
)

# ── RUMPELSTILTSKIN (Warlock) ────────────────────────────────────────────────
RUMPEL_S1 = Ability(
    id="straw_to_gold", name="Straw to Gold", category="signature", passive=False,
    frontline=AbilityMode(special="straw_to_gold_front"),
    backline=AbilityMode(special="straw_to_gold_back"),
)
RUMPEL_S2 = Ability(
    id="name_the_price", name="Name the Price", category="signature", passive=False,
    frontline=AbilityMode(power=65, special="name_the_price_front"),
    backline=AbilityMode(power=40, special="name_the_price_back"),
)
RUMPEL_S3 = Ability(
    id="spinning_wheel", name="Spinning Wheel", category="signature", passive=True,
    frontline=AbilityMode(special="spinning_wheel_front"),
    backline=AbilityMode(special="spinning_wheel_back"),
)
RUMPEL_T = Ability(
    id="devils_nursery", name="Devil's Nursery", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="devils_nursery"),
    backline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="devils_nursery"),
)
RUMPEL = AdventurerDef(
    id="rumpelstiltskin", name="Rumpelstiltskin", cls="Warlock",
    hp=230, attack=62, defense=49, speed=79,
    talent_name="Art of the Deal",
    talent_text="Whenever another adventurer gains a stat buff, Rumpelstiltskin gains 1 Malice, up to 6. Rumpelstiltskin has +3 speed for each Malice.",
    sig_options=[RUMPEL_S2, RUMPEL_S1, RUMPEL_S3], twist=RUMPEL_T,
)

# ── SEA WENCH ASHA (Warlock) ─────────────────────────────────────────────────
ASHA_S1 = Ability(
    id="misappropriate", name="Misappropriate", category="signature", passive=False,
    frontline=AbilityMode(special="misappropriate_front"),
    backline=AbilityMode(power=45, status="root", status_dur=2),
)
ASHA_S2 = Ability(
    id="abyssal_call", name="Abyssal Call", category="signature", passive=False,
    frontline=AbilityMode(power=65, special="abyssal_call_front"),
    backline=AbilityMode(power=45, special="abyssal_call_back"),
)
ASHA_S3 = Ability(
    id="faustian_bargain", name="Faustian Bargain", category="signature", passive=True,
    frontline=AbilityMode(special="faustian_bargain_front"),
    backline=AbilityMode(special="faustian_bargain_back"),
)
ASHA_T = Ability(
    id="foam_prison", name="Foam Prison", category="twist", passive=False,
    frontline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="foam_prison"),
    backline=AbilityMode(atk_buff=20, atk_buff_dur=2, special="foam_prison"),
)
ASHA = AdventurerDef(
    id="sea_wench_asha", name="Sea Wench Asha", cls="Warlock",
    hp=223, attack=73, defense=43, speed=86,
    talent_name="Stolen Voices",
    talent_text="When an enemy uses a signature ability, if Asha is backline, she gains 1 Malice, up to 6. If she's frontline, it deals -4 damage for each Malice.",
    sig_options=[ASHA_S2, ASHA_S1, ASHA_S3], twist=ASHA_T,
)

# ═══════════════════════════════════════════════════════════════════════════════
#  ROSTER
# ═══════════════════════════════════════════════════════════════════════════════
ROSTER = [
    RISA, LITTLE_JACK, GRETEL,
    CONSTANTINE, HUNOLD, REYNARD,
    ROLAND, PORCUS, LADY,
    ELLA, MARCH_HARE, WITCH,
    BRIAR_ROSE, FREDERIC, ROBIN,
    ALDRIC, LIESL, AURORA,
    PRINCE, GREEN_KNIGHT, RAPUNZEL,
    PINOCCHIO, RUMPEL, ASHA,
]
