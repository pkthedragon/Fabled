"""
data.py – all static game content, encoded directly from the Fabled rulebook.
AbilityMode fields that cannot be expressed as data are captured in `special`
strings and handled by ID in logic.py.
"""
from models import AbilityMode, Ability, Item, AdventurerDef

# helper alias for "not available from this slot"
_NA = AbilityMode(unavailable=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  BASIC ABILITIES  (Appendix B)
# ═══════════════════════════════════════════════════════════════════════════════

# ── FIGHTER ───────────────────────────────────────────────────────────────────
STRIKE = Ability(
    id="strike", name="Strike", category="basic", passive=False,
    frontline=AbilityMode(power=55),
    backline=_NA,
)

REND = Ability(
    id="rend", name="Rend", category="basic", passive=False,
    frontline=AbilityMode(power=45, bonus_vs_low_hp=20),
    backline=AbilityMode(special="User's ability against this target next round gets +10 Power"),
)

CLEAVE = Ability(
    id="cleave", name="Cleave", category="basic", passive=False,
    frontline=AbilityMode(power=45, def_ignore_pct=20),
    backline=AbilityMode(special="User's ability against this target next round ignores 10% Defense"),
)

FEINT = Ability(
    id="feint", name="Feint", category="basic", passive=False,
    frontline=AbilityMode(power=45, spd_buff=10, spd_buff_dur=2),
    backline=AbilityMode(spd_buff=10, spd_buff_dur=2),
)

INTIMIDATE = Ability(
    id="intimidate", name="Intimidate", category="basic", passive=False,
    frontline=AbilityMode(power=45, status="weaken", status_dur=2),
    backline=AbilityMode(status="weaken", status_dur=2),
)

# ── ROGUE ─────────────────────────────────────────────────────────────────────
SNEAK_ATTACK = Ability(
    id="sneak_attack", name="Sneak Attack", category="basic", passive=False,
    frontline=AbilityMode(power=45, bonus_if_not_acted=15),
    backline=AbilityMode(spd_debuff=10, spd_debuff_dur=2),
)

RIPOSTE = Ability(
    id="riposte", name="Riposte", category="basic", passive=False,
    frontline=AbilityMode(power=45, special="riposte_damage_reduction"),
    backline=AbilityMode(special="riposte_damage_reduction"),
)

POST_BOUNTY = Ability(
    id="post_bounty", name="Post Bounty", category="basic", passive=False,
    frontline=AbilityMode(power=40, status="expose", status_dur=2),
    backline=AbilityMode(status="expose", status_dur=2),
)

SUCKER_PUNCH = Ability(
    id="sucker_punch", name="Sucker Punch", category="basic", passive=False,
    frontline=AbilityMode(power=40, bonus_vs_statused=20),
    backline=AbilityMode(status="weaken", status_dur=2),
)

FLEETFOOTED = Ability(
    id="fleetfooted", name="Fleetfooted", category="basic", passive=True,
    frontline=AbilityMode(special="fleetfooted_front"),
    backline=AbilityMode(special="fleetfooted_back"),
)

# ── WARDEN ────────────────────────────────────────────────────────────────────
SHIELD_BASH = Ability(
    id="shield_bash", name="Shield Bash", category="basic", passive=False,
    frontline=AbilityMode(power=40, guard_all_allies=True),
    backline=AbilityMode(guard_frontline_ally=True),
)

CONDEMN = Ability(
    id="condemn", name="Condemn", category="basic", passive=False,
    frontline=AbilityMode(power=40, atk_debuff=10, atk_debuff_dur=2),
    backline=AbilityMode(atk_debuff=10, atk_debuff_dur=2),
)

SLAM = Ability(
    id="slam", name="Slam", category="basic", passive=False,
    frontline=AbilityMode(power=45, special="slam_bonus_if_guarded"),
    backline=AbilityMode(guard_self=True, special="slam_back_guard"),
)

ARMORED = Ability(
    id="armored", name="Armored", category="basic", passive=True,
    frontline=AbilityMode(def_buff=10),
    backline=AbilityMode(def_buff=5),
)

STALWART = Ability(
    id="stalwart", name="Stalwart", category="basic", passive=True,
    frontline=AbilityMode(special="stalwart_front"),
    backline=AbilityMode(special="stalwart_back"),
)

# ── MAGE ──────────────────────────────────────────────────────────────────────
FIRE_BLAST = Ability(
    id="fire_blast", name="Fire Blast", category="basic", passive=False,
    frontline=AbilityMode(power=60, status="burn", status_dur=2),
    backline=AbilityMode(power=35, status="burn", status_dur=2),
)

THUNDER_CALL = Ability(
    id="thunder_call", name="Thunder Call", category="basic", passive=False,
    frontline=AbilityMode(power=60, status="shock", status_dur=2),
    backline=AbilityMode(power=35, status="shock", status_dur=2),
)

FREEZING_GALE = Ability(
    id="freezing_gale", name="Freezing Gale", category="basic", passive=False,
    frontline=AbilityMode(power=60, status="root", status_dur=2),
    backline=AbilityMode(power=35, status="root", status_dur=2),
)

ARCANE_WAVE = Ability(
    id="arcane_wave", name="Arcane Wave", category="basic", passive=False,
    frontline=AbilityMode(power=70, special="arcane_wave_self_debuff"),
    backline=AbilityMode(power=40),
)

BREAKTHROUGH = Ability(
    id="breakthrough", name="Breakthrough", category="basic", passive=False,
    frontline=AbilityMode(atk_buff=15, atk_buff_dur=2),
    backline=AbilityMode(atk_buff=10, atk_buff_dur=2, self_status="spotlight", self_status_dur=2),
)

# ── RANGER ────────────────────────────────────────────────────────────────────
HAWKSHOT = Ability(
    id="hawkshot", name="Hawkshot", category="basic", passive=False,
    frontline=AbilityMode(power=60, cant_redirect=True),
    backline=AbilityMode(power=40, cant_redirect=True),
)

VOLLEY = Ability(
    id="volley", name="Volley", category="basic", passive=False,
    frontline=AbilityMode(power=60, spread=True),
    backline=AbilityMode(power=40, spread=True),
)

TRAPPING_BLOW = Ability(
    id="trapping_blow", name="Trapping Blow", category="basic", passive=False,
    frontline=AbilityMode(power=60, special="trapping_blow_root_weakened"),
    backline=AbilityMode(power=35, status="weaken", status_dur=2),
)

HUNTERS_MARK = Ability(
    id="hunters_mark", name="Hunter's Mark", category="basic", passive=False,
    frontline=AbilityMode(power=50, special="hunters_mark_dot"),
    backline=AbilityMode(power=25, special="hunters_mark_dot"),
)

HUNTERS_BADGE = Ability(
    id="hunters_badge", name="Hunter's Badge", category="basic", passive=True,
    frontline=AbilityMode(atk_buff=10),
    backline=AbilityMode(atk_buff=5),
)

# ── CLERIC ────────────────────────────────────────────────────────────────────
HEAL = Ability(
    id="heal", name="Heal", category="basic", passive=False,
    frontline=AbilityMode(heal=60),
    backline=AbilityMode(heal=45),
)

BLESS = Ability(
    id="bless", name="Bless", category="basic", passive=False,
    frontline=AbilityMode(guard_target=True, atk_buff=10, atk_buff_dur=2),
    backline=AbilityMode(guard_target=True),
)

SMITE = Ability(
    id="smite", name="Smite", category="basic", passive=False,
    frontline=AbilityMode(power=55, status="burn", status_dur=2),
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
    frontline=AbilityMode(power=50, spd_debuff=10, spd_debuff_dur=2),
    backline=AbilityMode(power=30, spd_debuff=10, spd_debuff_dur=2),
)

EDICT = Ability(
    id="edict", name="Edict", category="basic", passive=False,
    frontline=AbilityMode(power=50, status="root", status_dur=2),
    backline=AbilityMode(power=30, status="spotlight", status_dur=2),
)

DECREE = Ability(
    id="decree", name="Decree", category="basic", passive=False,
    frontline=AbilityMode(power=40, atk_buff=10, atk_buff_dur=2),
    backline=AbilityMode(power=25, atk_debuff=10, atk_debuff_dur=2),
)

SUMMONS = Ability(
    id="summons", name="Summons", category="basic", passive=False,
    frontline=AbilityMode(special="summons_swap"),
    backline=AbilityMode(special="summons_swap"),
)

COMMAND = Ability(
    id="command", name="Command", category="basic", passive=True,
    frontline=AbilityMode(special="command_front"),
    backline=AbilityMode(special="command_back"),
)

# ── WARLOCK ───────────────────────────────────────────────────────────────────
DARK_GRASP = Ability(
    id="dark_grasp", name="Dark Grasp", category="basic", passive=False,
    frontline=AbilityMode(power=50, special="warlock_gain_malice_1"),
    backline=AbilityMode(power=35, special="warlock_spend1_weaken"),
)

SOUL_GAZE = Ability(
    id="soul_gaze", name="Soul Gaze", category="basic", passive=False,
    frontline=AbilityMode(power=45, special="warlock_spend1_expose"),
    backline=AbilityMode(power=30, special="warlock_gain_malice_1"),
)

BLOOD_PACT = Ability(
    id="blood_pact", name="Blood Pact", category="basic", passive=False,
    frontline=AbilityMode(special="blood_pact_front"),
    backline=AbilityMode(heal_self=20, special="blood_pact_back"),
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
    "Mage":    [FIRE_BLAST, THUNDER_CALL, FREEZING_GALE, ARCANE_WAVE, BREAKTHROUGH],
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
    description="Heals user or ally 40 HP.", heal=40, uses=99,
)
CRAFTY_SHIELD = Item(
    id="crafty_shield", name="Crafty Shield", passive=False,
    description="Guards user or ally for 2 rounds.", guard=True, status="guard",
    status_dur=2, uses=99,
)
LIGHTNING_BOOTS = Item(
    id="lightning_boots", name="Lightning Boots", passive=False,
    description="User has +10 Speed next round.", spd_buff=10, spd_buff_dur=2,
    uses=99,
)
MAIN_GAUCHE = Item(
    id="main_gauche", name="Main-Gauche", passive=False,
    description="User has +10 Attack for 2 rounds.", atk_buff=10, atk_buff_dur=2,
    uses=99,
)
IRON_BUCKLER = Item(
    id="iron_buckler", name="Iron Buckler", passive=False,
    description="User has +10 Defense for 2 rounds.", def_buff=10, def_buff_dur=2,
    uses=99,
)
SMOKE_BOMB = Item(
    id="smoke_bomb", name="Smoke Bomb", passive=False,
    description="User switches positions with an ally.", uses=99,
    special="smoke_bomb_swap",
)
HUNTERS_NET = Item(
    id="hunters_net", name="Hunter's Net", passive=False,
    description="Roots target for 2 rounds.", status="root", status_dur=2, uses=99,
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
    description="User's abilities have 10% vamp.", vamp=0.10,
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
    description="User's healing effects restore 15 additional HP.", flat_heal_bonus=15,
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


# ═══════════════════════════════════════════════════════════════════════════════
#  ADVENTURER ABILITIES + DEFINITIONS  (Appendix A)
# ═══════════════════════════════════════════════════════════════════════════════

# ── RISA REDCLOAK (Fighter) ───────────────────────────────────────────────────
RISA_S1 = Ability(
    id="crimson_fury", name="Crimson Fury", category="signature", passive=False,
    frontline=AbilityMode(power=65, self_status="expose", self_status_dur=2),
    backline=AbilityMode(status="weaken", status_dur=2),
)
RISA_S2 = Ability(
    id="wolfs_pursuit", name="Wolf's Pursuit", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="wolfs_pursuit_retarget"),
    backline=AbilityMode(status="expose", status_dur=2),
)
RISA_S3 = Ability(
    id="blood_hunt", name="Blood Hunt", category="signature", passive=False,
    frontline=AbilityMode(power=60, double_vamp_no_base=True),
    backline=AbilityMode(special="blood_hunt_hp_avg"),
)
RISA_T = Ability(
    id="grandmothers_vengeance", name="Grandmother's Vengeance",
    category="twist", passive=False,
    frontline=AbilityMode(power=70, vamp=1.0, atk_buff=15, atk_buff_dur=2,
                          spd_buff=15, spd_buff_dur=2),
    backline=AbilityMode(power=70, vamp=1.0, atk_buff=15, atk_buff_dur=2,
                          spd_buff=15, spd_buff_dur=2),
)
RISA = AdventurerDef(
    id="risa_redcloak", name="Risa Redcloak", cls="Fighter",
    hp=250, attack=75, defense=60, speed=30,
    talent_name="Red and Wolf",
    talent_text="Below 50% max HP: +15 Atk, +15 Spd, abilities gain 20% vamp.",
    sig_options=[RISA_S1, RISA_S2, RISA_S3], twist=RISA_T,
)

# ── LITTLE JACK (Fighter) ─────────────────────────────────────────────────────
JACK_S1 = Ability(
    id="skyfall", name="Skyfall", category="signature", passive=False,
    frontline=AbilityMode(power=70),
    backline=AbilityMode(status="expose", status_dur=2),
)
JACK_S2 = Ability(
    id="belligerence", name="Belligerence", category="signature", passive=True,
    frontline=AbilityMode(def_ignore_pct=20),
    backline=AbilityMode(special="belligerence_ignore_atk"),
)
JACK_S3 = Ability(
    id="magic_growth", name="Magic Growth", category="signature", passive=False,
    frontline=AbilityMode(power=50, status="root", status_dur=2),
    backline=AbilityMode(status="root", status_dur=2, special="magic_growth_power_buff"),
)
JACK_T = Ability(
    id="fell_the_beanstalk", name="Fell the Beanstalk", category="twist", passive=False,
    frontline=AbilityMode(power=85, def_ignore_pct=30, status="expose", status_dur=2),
    backline=AbilityMode(power=85, def_ignore_pct=30, status="expose", status_dur=2),
)
LITTLE_JACK = AdventurerDef(
    id="little_jack", name="Little Jack", cls="Fighter",
    hp=220, attack=80, defense=50, speed=50,
    talent_name="Giant Slayer",
    talent_text="Jack deals 30% bonus damage to enemies with higher max HP.",
    sig_options=[JACK_S1, JACK_S2, JACK_S3], twist=JACK_T,
)

# ── WITCH-HUNTER GRETEL (Fighter) ────────────────────────────────────────────
GRETEL_S1 = Ability(
    id="shove_over", name="Shove Over", category="signature", passive=False,
    frontline=AbilityMode(power=60, status="weaken", status_dur=2),
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
    frontline=AbilityMode(power=55, special="crumb_trail_front"),
    backline=AbilityMode(special="crumb_trail_drop"),
)
GRETEL_T = Ability(
    id="into_the_oven", name="Into the Oven", category="twist", passive=False,
    frontline=AbilityMode(power=65, status="burn", status_dur=2,
                          status2="weaken", status2_dur=2,
                          status3="root", status3_dur=2),
    backline=AbilityMode(power=65, status="burn", status_dur=2,
                          status2="weaken", status2_dur=2,
                          status3="root", status3_dur=2),
)
GRETEL = AdventurerDef(
    id="gretel", name="Witch-Hunter Gretel", cls="Fighter",
    hp=215, attack=80, defense=45, speed=60,
    talent_name="Sugar Rush",
    talent_text="When Gretel knocks out an enemy: +15 Atk, +10 Spd for 2 rounds.",
    sig_options=[GRETEL_S1, GRETEL_S2, GRETEL_S3], twist=GRETEL_T,
)

# ── LUCKY CONSTANTINE (Rogue) ─────────────────────────────────────────────────
CONSTANTINE_S1 = Ability(
    id="subterfuge", name="Subterfuge", category="signature", passive=False,
    frontline=AbilityMode(power=50, special="subterfuge_swap"),
    backline=AbilityMode(special="subterfuge_swap"),
)
CONSTANTINE_S2 = Ability(
    id="feline_gambit", name="Feline Gambit", category="signature", passive=False,
    frontline=AbilityMode(power=45, status="expose", status_dur=2),
    backline=AbilityMode(status="expose", status_dur=2),
)
CONSTANTINE_S3 = Ability(
    id="nine_lives", name="Nine Lives", category="signature", passive=True,
    frontline=AbilityMode(special="nine_lives"),
    backline=AbilityMode(special="nine_lives"),
)
CONSTANTINE_T = Ability(
    id="final_deception", name="Final Deception", category="twist", passive=False,
    frontline=AbilityMode(special="final_deception"),
    backline=AbilityMode(special="final_deception"),
)
CONSTANTINE = AdventurerDef(
    id="lucky_constantine", name="Lucky Constantine", cls="Rogue",
    hp=215, attack=70, defense=40, speed=75,
    talent_name="Shadowstep",
    talent_text="Constantine ignores melee targeting vs Exposed targets, -10 dmg to backline.",
    sig_options=[CONSTANTINE_S2, CONSTANTINE_S1, CONSTANTINE_S3], twist=CONSTANTINE_T,
)

# ── HUNOLD THE PIPER (Rogue) ──────────────────────────────────────────────────
HUNOLD_S1 = Ability(
    id="haunting_rhythm", name="Haunting Rhythm", category="signature", passive=False,
    frontline=AbilityMode(power=50, status="shock", status_dur=2),
    backline=AbilityMode(status="shock", status_dur=2),
)
HUNOLD_S2 = Ability(
    id="dying_dance", name="Dying Dance", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="dying_dance_front"),
    backline=AbilityMode(status="weaken", status_dur=2),
)
HUNOLD_S3 = Ability(
    id="hypnotic_aura", name="Hypnotic Aura", category="signature", passive=True,
    frontline=AbilityMode(special="hypnotic_aura_front"),
    backline=AbilityMode(special="hypnotic_aura_back"),
)
HUNOLD_T = Ability(
    id="devils_due", name="Devil's Due", category="twist", passive=False,
    frontline=AbilityMode(special="devils_due"),
    backline=AbilityMode(special="devils_due"),
)
HUNOLD = AdventurerDef(
    id="hunold_the_piper", name="Hunold the Piper", cls="Rogue",
    hp=210, attack=60, defense=45, speed=65,
    talent_name="Electrifying Trance",
    talent_text="Shocked enemies take +15 damage from abilities.",
    sig_options=[HUNOLD_S1, HUNOLD_S2, HUNOLD_S3], twist=HUNOLD_T,
)

# ── REYNARD, LUPINE TRICKSTER (Rogue) ─────────────────────────────────────────
REYNARD_S1 = Ability(
    id="feign_weakness", name="Feign Weakness", category="signature", passive=False,
    frontline=AbilityMode(power=50, special="feign_weakness_retaliate_55"),
    backline=AbilityMode(special="feign_weakness_retaliate_45"),
)
REYNARD_S2 = Ability(
    id="size_up", name="Size Up", category="signature", passive=False,
    frontline=AbilityMode(power=45, status="weaken", status_dur=2),
    backline=AbilityMode(power=35, status="expose", status_dur=2),
)
REYNARD_S3 = Ability(
    id="cutpurse", name="Cutpurse", category="signature", passive=False,
    frontline=AbilityMode(power=40, spd_debuff=10, spd_debuff_dur=2,
                          spd_buff=10, spd_buff_dur=2),
    backline=AbilityMode(special="cutpurse_swap_frontline"),
)
REYNARD_T = Ability(
    id="last_laugh", name="Last Laugh", category="twist", passive=False,
    frontline=AbilityMode(special="last_laugh"),
    backline=AbilityMode(special="last_laugh"),
)
REYNARD = AdventurerDef(
    id="reynard", name="Reynard, Lupine Trickster", cls="Rogue",
    hp=205, attack=65, defense=45, speed=75,
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
    frontline=AbilityMode(power=35, special="taunt_target"),
    backline=AbilityMode(special="taunt_front_ranged"),
)
ROLAND_S3 = Ability(
    id="banner_of_command", name="Banner of Command", category="signature", passive=True,
    frontline=AbilityMode(special="banner_of_command"),
    backline=AbilityMode(special="banner_of_command"),
)
ROLAND_T = Ability(
    id="purehearted_stand", name="Purehearted Stand", category="twist", passive=False,
    frontline=AbilityMode(heal_self=100, guard_self=True),
    backline=AbilityMode(heal_self=100, guard_self=True),
)
ROLAND = AdventurerDef(
    id="sir_roland", name="Sir Roland", cls="Warden",
    hp=265, attack=40, defense=80, speed=30,
    talent_name="Silver Aegis",
    talent_text="Roland takes 0 damage from the first ability after swapping to frontline.",
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
    id="sturdy_home", name="Sturdy Home", category="signature", passive=True,
    frontline=AbilityMode(special="sturdy_home_front"),
    backline=AbilityMode(special="sturdy_home_back"),
)
PORCUS_T = Ability(
    id="unbreakable_defense", name="Unbreakable Defense", category="twist", passive=False,
    frontline=AbilityMode(special="unbreakable_defense"),
    backline=AbilityMode(special="unbreakable_defense"),
)
PORCUS = AdventurerDef(
    id="porcus_iii", name="Porcus III", cls="Warden",
    hp=280, attack=35, defense=85, speed=20,
    talent_name="Bricklayer",
    talent_text="If an ability would deal 25%+ max HP to Porcus, reduce by 40% and Weaken attacker.",
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
    frontline=AbilityMode(power=40, special="drown_dmg_bonus"),
    backline=AbilityMode(special="drown_dmg_bonus"),
)
LADY_S3 = Ability(
    id="lakes_gift", name="Lake's Gift", category="signature", passive=False,
    frontline=AbilityMode(special="lakes_gift_pool_front"),
    backline=AbilityMode(special="lakes_gift_pool_back"),
)
LADY_T = Ability(
    id="journey_to_avalon", name="Journey to Avalon", category="twist", passive=False,
    frontline=AbilityMode(special="journey_to_avalon"),
    backline=AbilityMode(special="journey_to_avalon"),
)
LADY = AdventurerDef(
    id="lady_of_reflections", name="Lady of Reflections", cls="Warden",
    hp=255, attack=40, defense=75, speed=32,
    talent_name="Reflecting Pool",
    talent_text="Reflects 10% of incoming damage onto attacker (20% if attacker is backline).",
    sig_options=[LADY_S2, LADY_S1, LADY_S3], twist=LADY_T,
)

# ── ASHEN ELLA (Mage) ─────────────────────────────────────────────────────────
ELLA_S1 = Ability(
    id="midnight_dour", name="Midnight Dour", category="signature", passive=True,
    frontline=AbilityMode(special="midnight_dour_swap"),
    backline=AbilityMode(heal_self=35),
)
ELLA_S2 = Ability(
    id="crowstorm", name="Crowstorm", category="signature", passive=False,
    frontline=AbilityMode(power=60, spread=True, status="burn", status_dur=2),
    backline=AbilityMode(status="burn", status_dur=2,
                         special="ella_ignore_two_lives"),
)
ELLA_S3 = Ability(
    id="fae_blessing", name="Fae Blessing", category="signature", passive=False,
    frontline=AbilityMode(guard_self=True, atk_buff=15, atk_buff_dur=2),
    backline=AbilityMode(heal=50, special="ella_ignore_two_lives"),
)
ELLA_T = Ability(
    id="struck_midnight", name="Struck Midnight", category="twist", passive=False,
    frontline=AbilityMode(status="burn", status_dur=2, special="struck_midnight_untargetable"),
    backline=AbilityMode(status="burn", status_dur=2, special="struck_midnight_untargetable"),
)
ELLA = AdventurerDef(
    id="ashen_ella", name="Ashen Ella", cls="Mage",
    hp=185, attack=80, defense=40, speed=65,
    talent_name="Two Lives",
    talent_text="Ella is untargetable while backline but can only use abilities while frontline.",
    sig_options=[ELLA_S2, ELLA_S1, ELLA_S3], twist=ELLA_T,
)

# ── MARCH HARE (Mage) ─────────────────────────────────────────────────────────
HARE_S1 = Ability(
    id="tempus_fugit", name="Tempus Fugit", category="signature", passive=False,
    frontline=AbilityMode(power=50, spd_debuff=12, spd_debuff_dur=2),
    backline=AbilityMode(power=35, spd_debuff=10, spd_debuff_dur=2),
)
HARE_S2 = Ability(
    id="rabbit_hole", name="Rabbit Hole", category="signature", passive=False,
    frontline=AbilityMode(special="rabbit_hole_extra_action"),
    backline=AbilityMode(special="rabbit_hole_swap"),
)
HARE_S3 = Ability(
    id="nebulous_ides", name="Nebulous Ides", category="signature", passive=False,
    frontline=AbilityMode(power=55, bonus_if_target_acted=20),
    backline=AbilityMode(power=40),
)
HARE_T = Ability(
    id="stitch_in_time", name="Stitch In Time", category="twist", passive=False,
    frontline=AbilityMode(spd_buff=15, spd_buff_dur=2, special="stitch_extra_action_now"),
    backline=AbilityMode(spd_buff=15, spd_buff_dur=2, special="stitch_extra_action_now"),
)
MARCH_HARE = AdventurerDef(
    id="march_hare", name="March Hare", cls="Mage",
    hp=190, attack=70, defense=35, speed=70,
    talent_name="On Time!",
    talent_text="While March Hare is frontline, the frontline enemy has -15 Speed.",
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
    backline=AbilityMode(power=30, spread=True, special="cauldron_extend_status"),
)
WITCH_S3 = Ability(
    id="crawling_abode", name="Crawling Abode", category="signature", passive=True,
    frontline=AbilityMode(special="crawling_abode"),
    backline=AbilityMode(special="crawling_abode"),
)
WITCH_T = Ability(
    id="vile_sabbath", name="Vile Sabbath", category="twist", passive=False,
    frontline=AbilityMode(power=70, spread=True, special="vile_sabbath_reapply"),
    backline=AbilityMode(power=70, spread=True, special="vile_sabbath_reapply"),
)
WITCH = AdventurerDef(
    id="witch_of_the_woods", name="Witch of the Woods", cls="Mage",
    hp=180, attack=75, defense=35, speed=65,
    talent_name="Double Double",
    talent_text="When Witch damages a statused target, spread their last status to adjacent left enemy.",
    sig_options=[WITCH_S1, WITCH_S2, WITCH_S3], twist=WITCH_T,
)

# ── BRIAR ROSE (Ranger) ───────────────────────────────────────────────────────
BRIAR_S1 = Ability(
    id="thorn_snare", name="Thorn Snare", category="signature", passive=False,
    frontline=AbilityMode(status="root", status_dur=2, spread=True),
    backline=AbilityMode(status="root", status_dur=2),
)
BRIAR_S2 = Ability(
    id="creeping_doubt", name="Creeping Doubt", category="signature", passive=False,
    frontline=AbilityMode(power=50, bonus_vs_rooted=40),
    backline=AbilityMode(power=40, status="root", status_dur=2),
)
BRIAR_S3 = Ability(
    id="garden_of_thorns", name="Garden of Thorns", category="signature", passive=True,
    frontline=AbilityMode(special="garden_of_thorns_attack"),
    backline=AbilityMode(special="garden_of_thorns_swap"),
)
BRIAR_T = Ability(
    id="falling_kingdom", name="Falling Kingdom", category="twist", passive=False,
    frontline=AbilityMode(special="falling_kingdom"),
    backline=AbilityMode(special="falling_kingdom"),
)
BRIAR_ROSE = AdventurerDef(
    id="briar_rose", name="Briar Rose", cls="Ranger",
    hp=195, attack=60, defense=45, speed=60,
    talent_name="Curse of Sleeping",
    talent_text="The lowest HP Rooted enemy loses Root, cannot act, and cannot be Rooted next round.",
    sig_options=[BRIAR_S1, BRIAR_S2, BRIAR_S3], twist=BRIAR_T,
)

# ── FREDERIC THE BEASTSLAYER (Ranger) ─────────────────────────────────────────
FRED_S1 = Ability(
    id="heros_charge", name="Hero's Charge", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="heros_charge_ignore_pride_front"),
    backline=AbilityMode(power=30, spd_buff=12, spd_buff_dur=2),
)
FRED_S2 = Ability(
    id="on_the_hunt", name="On the Hunt", category="signature", passive=False,
    frontline=AbilityMode(power=40, atk_buff=15, atk_buff_dur=2),
    backline=AbilityMode(power=25, status="expose", status_dur=2),
)
FRED_S3 = Ability(
    id="jovial_shot", name="Jovial Shot", category="signature", passive=False,
    frontline=AbilityMode(power=50, status="weaken", status_dur=2),
    backline=AbilityMode(heal_self=60, self_status="weaken", self_status_dur=2),
)
FRED_T = Ability(
    id="slay_the_beast", name="Slay the Beast", category="twist", passive=False,
    frontline=AbilityMode(power=65, bonus_vs_higher_hp=20,
                          special="slay_ignore_pride"),
    backline=AbilityMode(power=65, bonus_vs_higher_hp=20,
                         special="slay_ignore_pride"),
)
FREDERIC = AdventurerDef(
    id="frederic", name="Frederic the Beastslayer", cls="Ranger",
    hp=200, attack=65, defense=45, speed=60,
    talent_name="Heedless Pride",
    talent_text="Deals 20% bonus dmg to enemy frontline; takes 10% bonus dmg from enemy frontline.",
    sig_options=[FRED_S1, FRED_S2, FRED_S3], twist=FRED_T,
)

# ── ROBIN, HOODED AVENGER (Ranger) ────────────────────────────────────────────
ROBIN_S1 = Ability(
    id="snipe_shot", name="Snipe Shot", category="signature", passive=False,
    frontline=AbilityMode(power=65),
    backline=AbilityMode(power=40, ignore_guard=True),
)
ROBIN_S2 = Ability(
    id="spread_fortune", name="Spread Fortune", category="signature", passive=True,
    frontline=AbilityMode(special="spread_fortune_front"),
    backline=AbilityMode(special="spread_fortune_back"),
)
ROBIN_S3 = Ability(
    id="bring_down", name="Bring Down", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="bring_down_steal_atk"),
    backline=AbilityMode(power=40, status="root", status_dur=2),
)
ROBIN_T = Ability(
    id="kingmaker", name="Kingmaker", category="twist", passive=False,
    frontline=AbilityMode(power=70, ignore_guard=True, cant_redirect=True,
                          bonus_vs_backline=20),
    backline=AbilityMode(power=70, ignore_guard=True, cant_redirect=True,
                         bonus_vs_backline=20),
)
ROBIN = AdventurerDef(
    id="robin_hooded_avenger", name="Robin, Hooded Avenger", cls="Ranger",
    hp=185, attack=70, defense=40, speed=65,
    talent_name="Keen Eye",
    talent_text="Robin deals +15 damage with abilities to backline enemies.",
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
    frontline=AbilityMode(power=50, vamp=0.35),
    backline=AbilityMode(power=40, vamp=0.20),
)
ALDRIC_T = Ability(
    id="redemption", name="Redemption", category="twist", passive=False,
    frontline=AbilityMode(special="redemption"),
    backline=AbilityMode(special="redemption"),
)
ALDRIC = AdventurerDef(
    id="aldric_lost_lamb", name="Aldric, Lost Lamb", cls="Cleric",
    hp=230, attack=45, defense=60, speed=35,
    talent_name="All-Caring",
    talent_text="Aldric's healing effects Guard the recipient for 2 rounds.",
    sig_options=[ALDRIC_S1, ALDRIC_S2, ALDRIC_S3], twist=ALDRIC_T,
)

# ── MATCHSTICK LIESL (Cleric) ─────────────────────────────────────────────────
LIESL_S1 = Ability(
    id="cinder_blessing", name="Cinder Blessing", category="signature", passive=False,
    frontline=AbilityMode(special="cinder_blessing_avg"),
    backline=AbilityMode(heal_self=60),
)
LIESL_S2 = Ability(
    id="flame_of_renewal", name="Flame of Renewal", category="signature", passive=True,
    frontline=AbilityMode(special="flame_of_renewal"),
    backline=AbilityMode(special="flame_of_renewal"),
)
LIESL_S3 = Ability(
    id="cauterize", name="Cauterize", category="signature", passive=False,
    frontline=AbilityMode(power=50, status="no_heal", status_dur=2),
    backline=AbilityMode(power=40, status="no_heal", status_dur=2),
)
LIESL_T = Ability(
    id="cleansing_inferno", name="Cleansing Inferno", category="twist", passive=False,
    frontline=AbilityMode(power=60, spread=True, vamp=0.30,
                          special="cleansing_inferno_burn_boost"),
    backline=AbilityMode(power=60, spread=True, vamp=0.30,
                         special="cleansing_inferno_burn_boost"),
)
LIESL = AdventurerDef(
    id="matchstick_liesl", name="Matchstick Liesl", cls="Cleric",
    hp=210, attack=50, defense=50, speed=50,
    talent_name="Purifying Flame",
    talent_text="Liesl's healing grants Burn immunity for 2 rounds and causes next attack to Burn.",
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
    frontline=AbilityMode(power=50, heal_lowest=40),
    backline=AbilityMode(power=40, heal_lowest=30),
)
AURORA_S3 = Ability(
    id="birdsong", name="Birdsong", category="signature", passive=True,
    frontline=AbilityMode(special="birdsong_front"),
    backline=AbilityMode(special="birdsong_back"),
)
AURORA_T = Ability(
    id="deathlike_slumber", name="Deathlike Slumber", category="twist", passive=False,
    frontline=AbilityMode(special="deathlike_slumber"),
    backline=AbilityMode(special="deathlike_slumber"),
)
AURORA = AdventurerDef(
    id="snowkissed_aurora", name="Snowkissed Aurora", cls="Cleric",
    hp=225, attack=45, defense=60, speed=40,
    talent_name="Innocent Heart",
    talent_text="When Aurora or ally loses a status, they get +10 Def for 2 rounds; Aurora heals 20 HP.",
    sig_options=[AURORA_S1, AURORA_S2, AURORA_S3], twist=AURORA_T,
)



# ── PRINCE CHARMING (Noble) ─────────────────────────────────────────────────
PRINCE_S1 = Ability(
    id="condescend", name="Condescend", category="signature", passive=False,
    frontline=AbilityMode(power=60, def_debuff=10, def_debuff_dur=2),
    backline=AbilityMode(power=40, special="condescend_back"),
)
PRINCE_S2 = Ability(
    id="gallant_charge", name="Gallant Charge", category="signature", passive=False,
    frontline=AbilityMode(power=65, special="gallant_charge_front"),
    backline=AbilityMode(power=35, spd_buff=15, spd_buff_dur=2),
)
PRINCE_S3 = Ability(
    id="chosen_one", name="Chosen One", category="signature", passive=True,
    frontline=AbilityMode(special="chosen_one"),
    backline=AbilityMode(special="chosen_one"),
)
PRINCE_T = Ability(
    id="happily_ever_after", name="Happily Ever After", category="twist", passive=False,
    frontline=AbilityMode(power=70, special="happily_ever_after"),
    backline=AbilityMode(power=70, special="happily_ever_after"),
)
PRINCE = AdventurerDef(
    id="prince_charming", name="Prince Charming", cls="Noble",
    hp=255, attack=65, defense=55, speed=35,
    talent_name="Mesmerizing",
    talent_text="While Prince Charming is frontline, enemies that target allies get -10 Attack for 2 rounds.",
    sig_options=[PRINCE_S1, PRINCE_S2, PRINCE_S3], twist=PRINCE_T,
)

# ── GREEN KNIGHT (Noble) ────────────────────────────────────────────────────
GREEN_S1 = Ability(
    id="heros_bargain", name="Hero's Bargain", category="signature", passive=False,
    frontline=AbilityMode(power=50, status="root", status_dur=2),
    backline=AbilityMode(power=25, special="heros_bargain_back"),
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
    frontline=AbilityMode(special="fated_duel"),
    backline=AbilityMode(special="fated_duel"),
)
GREEN_KNIGHT = AdventurerDef(
    id="green_knight", name="Green Knight", cls="Noble",
    hp=275, attack=60, defense=60, speed=20,
    talent_name="Challenge Accepted",
    talent_text="The Green Knight deals +25 damage to the target across from him.",
    sig_options=[GREEN_S1, GREEN_S2, GREEN_S3], twist=GREEN_T,
)

# ── RAPUNZEL THE GOLDEN (Noble) ──────────────────────────────────────────────
RAPUNZEL_S1 = Ability(
    id="golden_snare", name="Golden Snare", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="golden_snare_front"),
    backline=AbilityMode(power=30, status="root", status_dur=2),
)
RAPUNZEL_S2 = Ability(
    id="lower_guard", name="Lower Guard", category="signature", passive=False,
    frontline=AbilityMode(power=55, special="lower_guard_front"),
    backline=AbilityMode(power=30, def_debuff=10, def_debuff_dur=2),
)
RAPUNZEL_S3 = Ability(
    id="ivory_tower", name="Ivory Tower", category="signature", passive=True,
    frontline=AbilityMode(special="ivory_tower_front"),
    backline=AbilityMode(special="ivory_tower_back"),
)
RAPUNZEL_T = Ability(
    id="severed_tether", name="Severed Tether", category="twist", passive=False,
    frontline=AbilityMode(special="severed_tether"),
    backline=AbilityMode(special="severed_tether"),
)
RAPUNZEL = AdventurerDef(
    id="rapunzel", name="Rapunzel the Golden", cls="Noble",
    hp=258, attack=60, defense=65, speed=30,
    talent_name="Flowing Locks",
    talent_text="Ignore melee targeting restrictions once per battle; refreshes after ending round in backline.",
    sig_options=[RAPUNZEL_S1, RAPUNZEL_S2, RAPUNZEL_S3], twist=RAPUNZEL_T,
)

# ── PINOCCHIO, CURSED PUPPET (Warlock) ───────────────────────────────────────
PINOCCHIO_S1 = Ability(
    id="wooden_wallop", name="Wooden Wallop", category="signature", passive=False,
    frontline=AbilityMode(power=45, special="wooden_wallop_front"),
    backline=AbilityMode(power=35, special="warlock_gain_malice_1"),
)
PINOCCHIO_S2 = Ability(
    id="cut_the_strings", name="Cut the Strings", category="signature", passive=False,
    frontline=AbilityMode(power=60, status="expose", status_dur=2),
    backline=AbilityMode(power=40, special="cut_strings_back"),
)
PINOCCHIO_S3 = Ability(
    id="become_real", name="Become Real", category="signature", passive=True,
    frontline=AbilityMode(special="become_real_front"),
    backline=AbilityMode(special="become_real_back"),
)
PINOCCHIO_T = Ability(
    id="blue_faerie_boon", name="Blue Faerie's Boon", category="twist", passive=False,
    frontline=AbilityMode(special="blue_faerie_boon"),
    backline=AbilityMode(special="blue_faerie_boon"),
)
PINOCCHIO = AdventurerDef(
    id="pinocchio", name="Pinocchio, Cursed Puppet", cls="Warlock",
    hp=220, attack=65, defense=50, speed=50,
    talent_name="Growing Pains",
    talent_text="End round in frontline: gain 1 Malice (max 6). +5 Atk/Def per Malice.",
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
    frontline=AbilityMode(power=70, special="name_the_price_front"),
    backline=AbilityMode(power=40, special="name_the_price_back"),
)
RUMPEL_S3 = Ability(
    id="spinning_wheel", name="Spinning Wheel", category="signature", passive=True,
    frontline=AbilityMode(special="spinning_wheel_front"),
    backline=AbilityMode(special="spinning_wheel_back"),
)
RUMPEL_T = Ability(
    id="thieve_the_first_born", name="Thieve the First-Born", category="twist", passive=False,
    frontline=AbilityMode(power=70, special="thieve_the_first_born"),
    backline=AbilityMode(power=70, special="thieve_the_first_born"),
)
RUMPEL = AdventurerDef(
    id="rumpelstiltskin", name="Rumpelstiltskin", cls="Warlock",
    hp=215, attack=70, defense=55, speed=60,
    talent_name="Art of the Deal",
    talent_text="When another adventurer gains a stat buff, gain 1 Malice (max 6). +5 Speed per Malice.",
    sig_options=[RUMPEL_S2, RUMPEL_S1, RUMPEL_S3], twist=RUMPEL_T,
)

# ── SEA WENCH ASHA (Warlock) ─────────────────────────────────────────────────
ASHA_S1 = Ability(
    id="misappropriate", name="Misappropriate", category="signature", passive=False,
    frontline=AbilityMode(special="misappropriate_front"),
    backline=AbilityMode(power=35, status="root", status_dur=2),
)
ASHA_S2 = Ability(
    id="abyssal_call", name="Abyssal Call", category="signature", passive=False,
    frontline=AbilityMode(power=60, special="abyssal_call_front"),
    backline=AbilityMode(power=40, special="abyssal_call_back"),
)
ASHA_S3 = Ability(
    id="faustian_bargain", name="Faustian Bargain", category="signature", passive=True,
    frontline=AbilityMode(special="faustian_bargain_front"),
    backline=AbilityMode(special="faustian_bargain_back"),
)
ASHA_T = Ability(
    id="turn_to_foam", name="Turn to Foam", category="twist", passive=False,
    frontline=AbilityMode(special="turn_to_foam"),
    backline=AbilityMode(special="turn_to_foam"),
)
ASHA = AdventurerDef(
    id="sea_wench_asha", name="Sea Wench Asha", cls="Warlock",
    hp=210, attack=75, defense=45, speed=65,
    talent_name="Stolen Voices",
    talent_text="Enemy signature used: gain Malice while backline; while frontline, enemy signatures deal -5 damage per Malice.",
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
