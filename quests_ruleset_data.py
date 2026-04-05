from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re

from quests_ruleset_models import (
    ActiveEffect,
    AdventurerDef,
    ArtifactDef,
    PassiveEffect,
    StatSpec,
    StatusSpec,
    WeaponDef,
)


def status(kind: str, duration: int) -> StatusSpec:
    return StatusSpec(kind=kind, duration=duration)


def stat(stat_name: str, amount: int, duration: int) -> StatSpec:
    return StatSpec(stat=stat_name, amount=amount, duration=duration)


def passive(effect_id: str, name: str, description: str, *, special: str = "") -> PassiveEffect:
    return PassiveEffect(id=effect_id, name=name, description=description, special=special)


def active(effect_id: str, name: str, *, description: str = "", **kwargs) -> ActiveEffect:
    return ActiveEffect(id=effect_id, name=name, description=description, **kwargs)


def weapon(
    weapon_id: str,
    name: str,
    kind: str,
    strike: ActiveEffect,
    *,
    ammo: int = 0,
    passive_skills=(),
    spells=(),
) -> WeaponDef:
    return WeaponDef(
        id=weapon_id,
        name=name,
        kind=kind,
        strike=strike,
        ammo=ammo,
        passive_skills=tuple(passive_skills),
        spells=tuple(spells),
    )


def artifact(
    artifact_id: str,
    name: str,
    attunement,
    stat_name: str,
    amount: int,
    spell: ActiveEffect,
    *,
    reactive: bool = False,
    description: str = "",
) -> ArtifactDef:
    return ArtifactDef(
        id=artifact_id,
        name=name,
        attunement=tuple(attunement),
        stat=stat_name,
        amount=amount,
        spell=spell,
        reactive=reactive,
        description=description,
    )


_RULEBOOK_SECTION_SKIP_LINES = {"Magic", "Active", "Melee", "Ranged", "No Cooldown"}

ULTIMATE_METER_MAX = 7
ULTIMATE_WIN_COUNT = 3
GOOSE_QUILL_RETAINED_METER = (ULTIMATE_METER_MAX + 1) // 2


def _next_rulebook_description_line(lines: list[str], start_index: int) -> str:
    index = start_index
    while index < len(lines):
        line = lines[index].strip()
        if (
            not line
            or line in _RULEBOOK_SECTION_SKIP_LINES
            or line.startswith("Cooldown:")
            or re.match(r"^\d+ Ammo$", line)
        ):
            index += 1
            continue
        return line
    return ""


def _extract_rulebook_strike_description(strike_line: str) -> str:
    text = strike_line.strip()
    if text.startswith("Has the Power and effects"):
        return text
    power_match = re.search(r"\bpower\b", text, flags=re.IGNORECASE)
    if power_match is None:
        return text
    rest = text[power_match.end():].strip()
    if rest.startswith(".") or rest.startswith(","):
        rest = rest[1:].strip()
    return rest


def _clean_strike_description(effect: ActiveEffect, description: str) -> str:
    desc = description.strip()
    if not desc:
        return ""
    if effect.recoil > 0 and desc.lower() == f"{int(effect.recoil * 100)}% recoil":
        return ""
    if effect.lifesteal > 0 and desc.lower() == f"{int(effect.lifesteal * 100)}% lifesteal":
        return ""
    if effect.spread and desc.lower() == "spread":
        return ""
    if effect.spread and desc.lower().startswith("spread. "):
        return desc[8:].strip()
    return desc


def _normalize_rulebook_name(name: str) -> str:
    return name.replace("’", "'").replace("`", "'").strip()


def _parse_rulebook_adventurer_descriptions() -> dict[str, dict]:
    path = Path(__file__).with_name("rulebook.txt")
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    appendix_a = re.search(r"^APPENDIX A .*$", text, flags=re.MULTILINE)
    appendix_b = re.search(r"^APPENDIX B .*$", text, flags=re.MULTILINE)
    if appendix_a is None or appendix_b is None:
        return {}
    lines = [line.rstrip() for line in text[appendix_a.start() : appendix_b.start()].splitlines()]

    records: dict[str, dict] = {}
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line and index + 1 < len(lines) and lines[index + 1].startswith("HP:"):
            name = line
            record = {
                "hp": 0,
                "attack": 0,
                "defense": 0,
                "speed": 0,
                "innate_desc": "",
                "weapons": {},
                "ultimate_name": "",
                "ultimate_desc": "",
            }
            try:
                record["hp"] = int(lines[index + 1].split(":", 1)[1].strip())
                record["attack"] = int(lines[index + 2].split(":", 1)[1].strip())
                record["defense"] = int(lines[index + 3].split(":", 1)[1].strip())
                record["speed"] = int(lines[index + 4].split(":", 1)[1].strip())
            except Exception:
                pass
            index += 5
            while index < len(lines):
                current = lines[index].strip()
                if current and index + 1 < len(lines) and lines[index + 1].startswith("HP:"):
                    index -= 1
                    break
                if current.startswith("Innate Skill:"):
                    record["innate_desc"] = _next_rulebook_description_line(lines, index + 1)
                elif current.startswith("Signature Weapon: "):
                    weapon_name = current.split(": ", 1)[1]
                    weapon_record = {
                        "strike_desc": "",
                        "passives_by_name": {},
                        "passives_ordered": [],
                        "spells_by_name": {},
                        "spells_ordered": [],
                    }
                    index += 1
                    while index < len(lines):
                        inner = lines[index].strip()
                        if (
                            inner.startswith("Signature Weapon: ")
                            or inner.startswith("Ultimate Spell: ")
                            or (inner and index + 1 < len(lines) and lines[index + 1].startswith("HP:"))
                        ):
                            index -= 1
                            break
                        if inner.startswith("Strike: "):
                            weapon_record["strike_desc"] = _extract_rulebook_strike_description(inner.split(": ", 1)[1])
                        elif inner.startswith("Skill: ") or inner.startswith("Passive: "):
                            skill_name = inner.split(": ", 1)[1].strip()
                            next_desc = _next_rulebook_description_line(lines, index + 1)
                            if (
                                next_desc
                                and not next_desc.startswith("Signature Weapon: ")
                                and not next_desc.startswith("Ultimate Spell: ")
                                and not next_desc.startswith("Skill: ")
                                and not next_desc.startswith("Passive: ")
                                and not next_desc.startswith("Spell: ")
                            ):
                                weapon_record["passives_by_name"][skill_name] = next_desc
                                weapon_record["passives_ordered"].append(next_desc)
                            else:
                                weapon_record["passives_ordered"].append(skill_name)
                        elif inner.startswith("Spell: "):
                            spell_name = inner.split(": ", 1)[1].strip()
                            spell_desc = _next_rulebook_description_line(lines, index + 1)
                            if spell_desc:
                                weapon_record["spells_by_name"][spell_name] = spell_desc
                                weapon_record["spells_ordered"].append(spell_desc)
                        index += 1
                    record["weapons"][weapon_name] = weapon_record
                elif current.startswith("Ultimate Spell: "):
                    record["ultimate_name"] = current.split(": ", 1)[1]
                    record["ultimate_desc"] = _next_rulebook_description_line(lines, index + 1)
                index += 1
            records[name] = record
        index += 1
    return records


def _sync_adventurer_descriptions_from_rulebook(adventurers: list[AdventurerDef]) -> list[AdventurerDef]:
    try:
        parsed = _parse_rulebook_adventurer_descriptions()
    except Exception:
        return adventurers
    if not parsed:
        return adventurers

    synced: list[AdventurerDef] = []
    for adventurer in adventurers:
        record = parsed.get(adventurer.name)
        if record is None:
            synced.append(adventurer)
            continue

        updated = adventurer

        innate = adventurer.innate
        if record["innate_desc"] and record["innate_desc"] != innate.description:
            innate = replace(innate, description=record["innate_desc"])

        weapons: list[WeaponDef] = []
        for weapon in adventurer.signature_weapons:
            weapon_record = record["weapons"].get(weapon.name, {})
            strike = weapon.strike
            strike_desc = weapon_record.get("strike_desc", None)
            if strike_desc is not None:
                cleaned = _clean_strike_description(strike, strike_desc)
                if cleaned != strike.description:
                    strike = replace(strike, description=cleaned)

            passives = []
            ordered_passive_descs = list(weapon_record.get("passives_ordered", []))
            for passive_index, passive_effect in enumerate(weapon.passive_skills):
                desc = weapon_record.get("passives_by_name", {}).get(passive_effect.name)
                if desc is None and passive_index < len(ordered_passive_descs):
                    desc = ordered_passive_descs[passive_index]
                if desc is not None and desc != passive_effect.description:
                    passives.append(replace(passive_effect, description=desc))
                else:
                    passives.append(passive_effect)

            spells = []
            ordered_spell_descs = list(weapon_record.get("spells_ordered", []))
            for spell_index, spell_effect in enumerate(weapon.spells):
                desc = weapon_record.get("spells_by_name", {}).get(spell_effect.name)
                if desc is None and spell_index < len(ordered_spell_descs):
                    desc = ordered_spell_descs[spell_index]
                if desc is not None and desc != spell_effect.description:
                    spells.append(replace(spell_effect, description=desc))
                else:
                    spells.append(spell_effect)

            weapons.append(
                replace(
                    weapon,
                    strike=strike,
                    passive_skills=tuple(passives),
                    spells=tuple(spells),
                )
            )

        ultimate = updated.ultimate
        if record["ultimate_name"] and _normalize_rulebook_name(record["ultimate_name"]) != _normalize_rulebook_name(ultimate.name):
            ultimate = replace(ultimate, name=record["ultimate_name"])
        if record["ultimate_desc"] and record["ultimate_desc"] != ultimate.description:
            ultimate = replace(ultimate, description=record["ultimate_desc"])

        synced.append(
            replace(
                updated,
                innate=innate,
                signature_weapons=tuple(weapons),
                ultimate=ultimate,
            )
        )
    return synced


CLASS_SKILLS = {
    "Fighter": [
        passive("martial", "Martial", "Melee Strikes deal +15 damage."),
        passive("inevitable", "Inevitable", "Melee Strikes charge the Ultimate Meter +1.", special="bonus_melee_strike_meter"),
    ],
    "Rogue": [
        passive("covert", "Covert", "Can Swap positions as a bonus action.", special="bonus_swap"),
        passive("assassin", "Assassin", "Ignore targeting restrictions against enemies who did not Strike or Swap.", special="assassin"),
    ],
    "Warden": [
        passive("bulwark", "Bulwark", "Gain +15 Defense while in the frontline."),
        passive("vigilant", "Vigilant", "Become Guarded for 2 rounds when you Swap positions.", special="vigilant"),
    ],
    "Mage": [
        passive("arcane", "Arcane", "Magic Strikes deal +10 damage."),
        passive("archmage", "Archmage", "The first Spell after Switching weapons does not go on cooldown.", special="archmage"),
    ],
    "Ranger": [
        passive("deadeye", "Deadeye", "Ranged Strikes deal +10 damage."),
        passive("armed", "Armed", "The first Ranged Strike after Switching does not consume Ammo.", special="armed"),
    ],
    "Cleric": [
        passive("healer", "Healer", "Healing effects restore an additional +15 HP."),
        passive("medic", "Medic", "Healing effects cleanse status conditions and stat penalties.", special="medic"),
    ],
}


CLASS_SKILLS_BY_ID = {
    skill.id: skill
    for skills in CLASS_SKILLS.values()
    for skill in skills
}


ARTIFACTS = [
    artifact(
        "holy_grail",
        "Wishing Table",
        ("Cleric", "Fighter", "Warden"),
        "defense",
        10,
        active(
            "healing_salve",
            "Table-Be-Set",
            target="ally",
            heal=40,
            cooldown=1,
            description="Restore 40 HP and cleanse the newest status.",
            special="cleanse_newest_status",
        ),
    ),
    artifact(
        "winged_sandals",
        "Winged Sandals",
        ("Ranger", "Rogue", "Warden"),
        "speed",
        10,
        active(
            "the_swiftness",
            "The Swiftness",
            target="ally",
            cooldown=2,
            self_buffs=(stat("speed", 15, 2),),
            description="Swap with an ally and gain +15 Speed.",
            special="artifact_swap_with_ally",
        ),
    ),
    artifact(
        "lightning_helm",
        "Lightning Helm",
        ("Fighter", "Mage", "Rogue"),
        "attack",
        10,
        active(
            "thunderclap",
            "Thunderclap",
            target="self",
            cooldown=2,
            description="Next Strike deals +10 damage and Shocks.",
            special="next_strike_bonus_10_shock",
        ),
    ),
    artifact(
        "golden_fleece",
        "Golden Fleece",
        ("Cleric", "Fighter", "Warden"),
        "defense",
        10,
        active(
            "restoration",
            "Restoration",
            target="self",
            heal=25,
            cooldown=2,
            self_buffs=(stat("attack", 10, 2),),
        ),
    ),
    artifact(
        "arcane_hourglass",
        "Arcane Hourglass",
        ("Mage",),
        "defense",
        15,
        active(
            "time_stop",
            "Time Stop",
            target="self",
            cooldown=6,
            description="Become untargetable but cannot act for 1 round.",
            special="time_stop",
        ),
    ),
    artifact(
        "naiads_knife",
        "Naiad's Knife",
        ("Fighter", "Rogue"),
        "attack",
        15,
        active(
            "deep_cut",
            "Deep Cut",
            target="self",
            cooldown=2,
            description="Next Strike Exposes the target for 2 rounds.",
            special="next_strike_expose",
        ),
    ),
    artifact(
        "last_prism",
        "Last Prism",
        ("Mage",),
        "attack",
        15,
        active(
            "chroma",
            "Chroma",
            target="self",
            cooldown=1,
            description="Next Magic Strike deals +15 damage.",
            special="next_magic_strike_plus_15",
        ),
    ),
    artifact(
        "misericorde",
        "Misericorde",
        ("Cleric", "Fighter", "Rogue"),
        "attack",
        15,
        active(
            "mercy_stroke",
            "Mercy Stroke",
            target="enemy",
            power=30,
            cooldown=2,
            description="Deal 30 damage to a statused enemy.",
            special="statused_only",
        ),
    ),
    artifact(
        "selkies_skin",
        "Selkie’s Skin",
        ("Mage", "Ranger", "Rogue"),
        "speed",
        10,
        active(
            "mistform",
            "Mistform",
            target="self",
            cooldown=2,
            description="The next Strike this round deals 0 damage.",
            special="mistform",
        ),
        reactive=True,
    ),
    artifact(
        "red_hood",
        "Red Hood",
        ("Cleric", "Fighter", "Ranger"),
        "attack",
        15,
        active(
            "hunters_path",
            "Hunter's Path",
            target="self",
            cooldown=1,
            description="Next Strike has 30% lifesteal.",
            special="next_strike_lifesteal_30",
        ),
    ),
    artifact(
        "enchanted_lamp",
        "Enchanted Lamp",
        ("Cleric", "Rogue"),
        "speed",
        15,
        active(
            "dying_wish",
            "Dying Wish",
            target="self",
            cooldown=6,
            description="Survive fatal damage from above 50% max HP at 1 HP.",
            special="dying_wish",
        ),
        reactive=True,
    ),
    artifact(
        "magic_mirror",
        "Magic Mirror",
        ("Cleric", "Mage"),
        "speed",
        5,
        active(
            "reflection",
            "Reflection",
            target="self",
            cooldown=5,
            description="Reflect a Spell targeted at the user.",
            special="reflect_spell",
        ),
        reactive=True,
    ),
    artifact(
        "nettle_smock",
        "Nettle Smock",
        ("Fighter", "Warden"),
        "defense",
        10,
        active(
            "thornmail",
            "Thornmail",
            target="self",
            cooldown=2,
            description="Reflect 20% Strike damage and cut healing by 50%.",
            special="thornmail",
        ),
        reactive=True,
    ),
    artifact(
        "goose_quill",
        "Goose Quill",
        ("Cleric", "Mage", "Warden"),
        "speed",
        5,
        active(
            "make_history",
            "Make History",
            target="self",
            cooldown=6,
            description="Ultimate only spends half the meter.",
            special="half_meter_ultimate",
        ),
        reactive=True,
    ),
    artifact(
        "cursed_spindle",
        "Cursed Spindle",
        ("Cleric", "Mage", "Rogue"),
        "attack",
        5,
        active(
            "plague",
            "Plague",
            target="self",
            cooldown=3,
            description="Extend inflicted status conditions by 1 round.",
            special="extend_status_inflicted",
        ),
        reactive=True,
    ),
]


ARTIFACTS.extend([
    artifact(
        "bluebeards_key",
        "Bluebeard’s Key",
        ("Rogue", "Warden"),
        "defense",
        10,
        active(
            "unseal",
            "Unseal",
            target="enemy",
            cooldown=2,
            description="Remove Guard and Defense bonuses for 2 rounds.",
            special="unseal",
        ),
    ),
    artifact(
        "sun_gods_banner",
        "Sun-God's Banner",
        ("Warden",),
        "defense",
        15,
        active(
            "hold",
            "Hold",
            target="self",
            cooldown=2,
            self_statuses=(status("guard", 2),),
            description="Guard the user and the lowest HP ally behind them.",
            special="guard_lowest_hp_ally_behind",
        ),
    ),
    artifact(
        "dire_wolf_spine",
        "Dire-Wolf Spine",
        ("Fighter",),
        "attack",
        10,
        active(
            "rend",
            "Rend",
            target="self",
            cooldown=2,
            description="Next Melee Strike deals +10 damage and Weakens.",
            special="next_melee_plus_10_weaken",
        ),
    ),
    artifact(
        "soaring_crown",
        "Soaring Crown",
        ("Ranger",),
        "speed",
        10,
        active(
            "hawks_eye",
            "Hawk's Eye",
            target="self",
            cooldown=2,
            description="Next Ranged Strike ignores targeting restrictions and Ammo.",
            special="next_ranged_ignore_targeting_no_ammo",
        ),
    ),
    artifact(
        "fading_diadem",
        "Fading Diadem",
        ("Cleric",),
        "defense",
        10,
        active(
            "reprieve",
            "Reprieve",
            target="ally",
            heal=30,
            cooldown=2,
            target_statuses=(status("guard", 2),),
        ),
    ),
    artifact(
        "iron_rosary",
        "Holy Grail",
        ("Cleric",),
        "defense",
        15,
        active(
            "purge",
            "Purge",
            target="ally",
            cooldown=1,
            description="Cleanse status conditions and gain Defense per condition removed.",
            special="purge",
        ),
    ),
    artifact(
        "dragons_horn",
        "Dragon's Horn",
        ("Fighter", "Ranger"),
        "attack",
        10,
        active(
            "sky_assault",
            "Sky Assault",
            target="self",
            cooldown=2,
            description="Next Strike deals +10 damage and Spotlights.",
            special="next_strike_plus_10_spotlight",
        ),
    ),
    artifact(
        "bottled_clouds",
        "Bottled Clouds",
        ("Mage", "Ranger"),
        "attack",
        10,
        active(
            "clear_skies",
            "Clear Skies",
            target="self",
            cooldown=2,
            description="Next Strike deals +10 damage and is Spread.",
            special="next_strike_plus_10_spread",
        ),
    ),
    artifact(
        "glass_slipper",
        "Glass Slipper",
        ("Mage", "Rogue"),
        "speed",
        10,
        active(
            "midnight_waltz",
            "Midnight Waltz",
            target="ally",
            cooldown=2,
            description="Swap with an ally and the next Spell does not go on cooldown.",
            special="midnight_waltz",
        ),
    ),
    artifact(
        "black_torch",
        "Black Torch",
        ("Fighter", "Ranger", "Rogue"),
        "attack",
        10,
        active(
            "grave_tiding",
            "Grave Tiding",
            target="self",
            cooldown=1,
            description="Heal for 50% of damage dealt after a fatal hit.",
            special="grave_tiding",
        ),
        reactive=True,
    ),
    artifact(
        "cornucopia",
        "Cornucopia",
        ("Ranger", "Warden"),
        "speed",
        15,
        active(
            "horn_of_plenty",
            "Horn of Plenty",
            target="self",
            cooldown=1,
            description="When the user Swaps with an ally, both restore 25 HP.",
            special="horn_of_plenty",
        ),
        reactive=True,
    ),
    artifact(
        "all_mill",
        "All-Mill",
        ("Ranger", "Warden"),
        "defense",
        10,
        active(
            "boundless",
            "Boundless",
            target="self",
            cooldown=2,
            self_statuses=(status("root_immunity", 2),),
            self_buffs=(stat("speed", 10, 2),),
            description="Gain Root Immunity and +10 Speed for 2 rounds.",
        ),
    ),
    artifact(
        "paradox_rings",
        "Paradox Rings",
        ("Mage", "Warden"),
        "speed",
        15,
        active(
            "infinity",
            "Infinity",
            target="self",
            cooldown=2,
            description="When the user casts an ally-target Spell, they Swap positions.",
            special="infinity",
        ),
        reactive=True,
    ),
    artifact(
        "jade_rabbit",
        "Jade Rabbit",
        ("Mage", "Ranger"),
        "speed",
        5,
        active(
            "elixir_of_life",
            "Elixir of Life",
            target="self",
            cooldown=2,
            description="Next Strike gains lifesteal, no ammo cost, and no cooldown.",
            special="elixir_of_life",
        ),
    ),
    artifact(
        "swan_cloak",
        "Swan Cloak",
        ("Rogue",),
        "defense",
        5,
        active(
            "featherweight",
            "Featherweight",
            target="self",
            cooldown=2,
            description="When targeted by a Melee Strike, Swap positions first.",
            special="featherweight",
        ),
        reactive=True,
    ),
    artifact(
        "starskin_veil",
        "Starskin Veil",
        ("Cleric", "Warden"),
        "defense",
        15,
        active(
            "dazzle",
            "Dazzle",
            target="ally",
            cooldown=2,
            description="Redirect the target's next Spell or Strike to the user.",
            special="dazzle",
        ),
    ),
    artifact(
        "blood_diamond",
        "Blood Diamond",
        ("Fighter",),
        "attack",
        5,
        active(
            "last_stand",
            "Last Stand",
            target="self",
            cooldown=2,
            description="When a Strike damages the user below 50% max HP, their next Strike deals +25 damage.",
            special="last_stand",
        ),
        reactive=True,
    ),
    artifact(
        "suspicious_eye",
        "Suspicious Eye",
        ("Ranger",),
        "speed",
        10,
        active(
            "nebulous_ides",
            "Nebulous Ides",
            target="self",
            cooldown=2,
            description="When the user Strikes an enemy in their lane, Spotlight the target for 2 rounds.",
            special="nebulous_ides",
        ),
        reactive=True,
    ),
    artifact(
        "philosophers_stone",
        "Philosopher's Stone",
        ("Cleric", "Mage"),
        "defense",
        15,
        active(
            "transmutation",
            "Transmutation",
            target="self",
            cooldown=2,
            description="When an enemy inflicts a status condition on the user, cleanse it and restore 40 HP.",
            special="transmutation",
        ),
        reactive=True,
    ),
    artifact(
        "seeking_yarn",
        "Seeking Yarn",
        ("Ranger", "Rogue"),
        "speed",
        15,
        active(
            "lead",
            "Lead",
            target="self",
            cooldown=2,
            description="For 2 rounds, the user's Strikes against enemies in their lane do not consume Ammo.",
            special="seeking_yarn",
        ),
    ),
    artifact(
        "tarnhelm",
        "Tarnhelm",
        ("Fighter", "Warden"),
        "attack",
        10,
        active(
            "feign_death",
            "Feign Death",
            target="self",
            cooldown=6,
            description="When the user takes fatal damage, they survive at 1 HP.",
            special="tarnhelm",
        ),
        reactive=True,
    ),
    artifact(
        "walking_abode",
        "Walking Abode",
        ("Cleric", "Mage", "Ranger"),
        "speed",
        5,
        active(
            "consume",
            "Consume",
            target="enemy",
            cooldown=2,
            target_statuses=(status("root", 2),),
            description="Root target enemy for 2 rounds and halve their healing for the duration.",
            special="walking_abode",
        ),
    ),
    artifact(
        "nebula_mail",
        "Nebula Mail",
        ("Fighter", "Rogue", "Warden"),
        "attack",
        10,
        active(
            "event_horizon",
            "Event Horizon",
            target="self",
            cooldown=2,
            description="For 2 rounds, when the user takes damage from a Strike, charge the Ultimate Meter +1.",
            special="event_horizon",
        ),
    ),
])


ARTIFACTS_BY_ID = {artifact_def.id: artifact_def for artifact_def in ARTIFACTS}


RED = AdventurerDef(
    id="red_blanchette",
    name="Red Blanchette",
    hp=312,
    attack=72,
    defense=78,
    speed=42,
    innate=passive("red_and_wolf", "Red and Wolf", "While below 50% max HP, Red has +15 Attack, +15 Speed, and her Strikes have 15% Lifesteal.", special="red_and_wolf"),
    signature_weapons=(
        weapon(
            "stomach_splitter",
            "Stomach Splitter",
            "magic",
            active(
                "stomach_splitter_strike",
                "Strike",
                power=40,
                cooldown=2,
                counts_as_spell=True,
                target_statuses=(status("mark", 2),),
            ),
            passive_skills=(passive("wolfs_pursuit", "Wolf's Pursuit", "Strike Marked enemies when they Swap.", special="wolfs_pursuit"),),
        ),
        weapon(
            "enchanted_shackles",
            "Enchanted Shackles",
            "melee",
            active("enchanted_shackles_strike", "Strike", power=70, recoil=0.25),
            spells=(
                active(
                    "blood_transfusion",
                    "Blood Transfusion",
                    target="enemy",
                    cooldown=2,
                    description="Average Red and the target's HP.",
                    special="average_hp_with_target",
                ),
            ),
        ),
    ),
    ultimate=active(
        "wolf_unchained",
        "Wolf Unchained",
        target="self",
        description="For 2 rounds, Red and Wolf is always active and doubled.",
        special="wolf_unchained",
    ),
)


JACK = AdventurerDef(
    id="little_jack",
    name="Little Jack",
    hp=258,
    attack=82,
    defense=57,
    speed=68,
    innate=passive("giant_slayer", "Giant Slayer", "Jack deals +15 bonus damage to enemies with higher max HP.", special="giant_slayer"),
    signature_weapons=(
        weapon(
            "skyfall",
            "Skyfall",
            "melee",
            active("skyfall_strike", "Strike", power=80),
            spells=(
                active(
                    "cloudburst",
                    "Cloudburst",
                    target="self",
                    cooldown=1,
                    description="Next Strike ignores targeting restrictions.",
                    special="next_strike_ignore_targeting",
                ),
            ),
        ),
        weapon(
            "giants_harp",
            "Giant's Harp",
            "magic",
            active("giants_harp_strike", "Strike", power=65, cooldown=1, counts_as_spell=True),
            passive_skills=(passive("belligerence", "Belligerence", "Ignore 20% of enemy Defense.", special="ignore_20_defense"),),
        ),
    ),
    ultimate=active(
        "fell_the_beanstalk",
        "Fell the Beanstalk",
        target="self",
        description="Next Strike ignores 100% of Defense.",
        special="next_strike_ignore_all_defense",
    ),
)


GRETEL = AdventurerDef(
    id="witch_hunter_gretel",
    name="Witch-Hunter Gretel",
    hp=278,
    attack=76,
    defense=66,
    speed=60,
    innate=passive("sugar_rush", "Sugar Rush", "When Gretel knocks out an enemy, she has +15 Attack and +15 Speed for 2 rounds.", special="sugar_rush"),
    signature_weapons=(
        weapon(
            "hot_mitts",
            "Hot Mitts",
            "melee",
            active(
                "hot_mitts_strike",
                "Strike",
                power=65,
                bonus_power_if_status="burn",
                bonus_power=15,
                description="Burn the target if they are not already Burned.",
                special="burn_if_not_burned",
            ),
        ),
        weapon(
            "crumb_shot",
            "Crumb Shot",
            "ranged",
            active("crumb_shot_strike", "Strike", power=50, ammo_cost=1, description="Interact with dropped crumbs.", special="crumb_shot"),
            ammo=3,
            passive_skills=(passive("crumbs", "Crumbs", "Allies can pick up crumbs by Swapping into them.", special="crumbs"),),
        ),
    ),
    ultimate=active(
        "in_the_oven",
        "In The Oven",
        target="none",
        description="Enemies take +15 damage and allies heal +15 from all sources for 2 rounds.",
        special="in_the_oven",
    ),
)


CONSTANTINE = AdventurerDef(
    id="lucky_constantine",
    name="Lucky Constantine",
    hp=248,
    attack=75,
    defense=48,
    speed=90,
    innate=passive("shadowstep", "Shadowstep", "Constantine ignores targeting restrictions against Exposed targets.", special="shadowstep"),
    signature_weapons=(
        weapon(
            "fortuna",
            "Fortuna",
            "melee",
            active("fortuna_strike", "Strike", power=65, description="Swap the target with an enemy ally.", special="swap_target_with_enemy"),
            spells=(
                active(
                    "consensia",
                    "Consensia",
                    target="enemy",
                    cooldown=2,
                    target_statuses=(status("expose", 2),),
                ),
            ),
        ),
        weapon(
            "cat_o_nine",
            "Cat'O'Nine",
            "melee",
            active("cat_o_nine_strike", "Strike", power=9, description="Hits 9 times.", special="multihit_9"),
            passive_skills=(passive("nine_lives", "Nine Lives", "Survive certain fatal Strikes at 1 HP.", special="nine_lives"),),
        ),
    ),
    ultimate=active(
        "eyes_everywhere",
        "Eyes Everywhere",
        target="none",
        description="Expose enemies and steal Defense with Strikes for 2 rounds.",
        special="eyes_everywhere",
    ),
)


HUNOLD = AdventurerDef(
    id="hunold_the_piper",
    name="Hunold the Piper",
    hp=258,
    attack=66,
    defense=54,
    speed=68,
    innate=passive("electrifying_trance", "Electrifying Trance", "Shocked enemies take +15 damage.", special="electrifying_trance"),
    signature_weapons=(
        weapon(
            "lightning_rod",
            "Lightning Rod",
            "ranged",
            active("lightning_rod_strike", "Strike", power=45, ammo_cost=1, target_statuses=(status("shock", 2),), special="lightning_rod"),
            ammo=3,
        ),
        weapon(
            "golden_fiddle",
            "Golden Fiddle",
            "magic",
            active(
                "golden_fiddle_strike",
                "Strike",
                power=70,
                cooldown=1,
                counts_as_spell=True,
                description="If the target is Shocked, Root and Spotlight them and keep the strike ready.",
                special="golden_fiddle",
            ),
        ),
    ),
    ultimate=active(
        "mass_hysteria",
        "Mass Hysteria",
        target="self",
        description="Strikes become Spread and ignore targeting restrictions for 2 rounds.",
        special="mass_hysteria",
    ),
)


ROLAND = AdventurerDef(
    id="sir_roland",
    name="Sir Roland",
    hp=314,
    attack=42,
    defense=82,
    speed=22,
    innate=passive("silver_aegis", "Silver Aegis", "Roland takes 60% less damage from the first incoming ability after swapping to frontline.", special="silver_aegis"),
    signature_weapons=(
        weapon(
            "pure_gold_lance",
            "Pure Gold Lance",
            "melee",
            active("pure_gold_lance_strike", "Strike", power=65, target_statuses=(status("expose", 2),)),
            spells=(
                active(
                    "knights_challenge",
                    "Knight's Challenge",
                    target="enemy",
                    cooldown=2,
                    target_statuses=(status("taunt", 2),),
                ),
            ),
        ),
        weapon(
            "pure_silver_shield",
            "Pure Silver Shield",
            "melee",
            active("pure_silver_shield_strike", "Strike", power=60, self_statuses=(status("guard", 2),)),
            passive_skills=(passive("banner_of_command", "Banner of Command", "Guard allies when they Swap positions.", special="banner_of_command"),),
            spells=(
                active(
                    "shimmering_valor",
                    "Shimmering Valor",
                    target="self",
                    cooldown=2,
                    description="Cleanse Guard and heal based on remaining Guard duration.",
                    special="shimmering_valor",
                ),
            ),
        ),
    ),
    ultimate=active(
        "final_stand",
        "Final Stand",
        target="self",
        heal=150,
        description="Restore 150 HP and keep Silver Aegis active for 2 rounds.",
        special="final_stand",
    ),
)


PORCUS = AdventurerDef(
    id="porcus_iii",
    name="Porcus III",
    hp=324,
    attack=40,
    defense=84,
    speed=16,
    innate=passive("bricklayer", "Bricklayer", "If a Strike would deal 20% max HP or more to Porcus, reduce damage by 35% and Weaken the attacker for 2 rounds.", special="bricklayer"),
    signature_weapons=(
        weapon(
            "crafty_wall",
            "Crafty Wall",
            "melee",
            active("crafty_wall_strike", "Strike", power=65, description="Bricklayer reduces all damage next round.", special="crafty_wall"),
            spells=(
                active(
                    "not_by_the_hair",
                    "Not By The Hair",
                    target="self",
                    cooldown=1,
                    description="Bricklayer activates on all Strikes this round and acts first.",
                    special="not_by_the_hair",
                ),
            ),
        ),
        weapon(
            "mortar_mortar",
            "Mortar Mortar",
            "ranged",
            active("mortar_mortar_strike", "Strike", power=45, ammo_cost=1, target_statuses=(status("weaken", 2),), special="mortar_mortar"),
            ammo=3,
        ),
    ),
    ultimate=active(
        "unfettered",
        "Unfettered",
        target="self",
        description="Gain massive Attack and Speed, lose Defense for 2 rounds.",
        special="unfettered",
    ),
)


LADY = AdventurerDef(
    id="lady_of_reflections",
    name="Lady of Reflections",
    hp=308,
    attack=48,
    defense=70,
    speed=42,
    innate=passive("reflecting_pools", "Reflecting Pools", "The Lady creates a Reflecting Pool for 2 rounds at her new position whenever she swaps. Strikes targeting Reflecting Pools reflect 25% of the damage onto the attacker, 50% if the Strike is Magic.", special="reflecting_pools"),
    signature_weapons=(
        weapon("excalibur_doc", "Excalibur", "melee", active("excalibur_doc_strike", "Strike", power=70)),
        weapon(
            "lantern_of_avalon",
            "Lantern of Avalon",
            "magic",
            active("lantern_of_avalon_strike", "Strike", power=60, cooldown=1, counts_as_spell=True, special="self_swap_after_strike"),
            passive_skills=(
                passive(
                    "postmortem_passage",
                    "Postmortem Passage",
                    "When a Strike deals fatal damage to an ally, they retaliate for 50 Power against the attacker.",
                    special="postmortem_passage",
                ),
            ),
            spells=(
                active(
                    "drown_in_the_loch",
                    "Drown in the Loch",
                    target="enemy",
                    cooldown=2,
                    description="Target takes +15 damage from all sources for 2 rounds.",
                    special="takes_plus_15_damage",
                ),
            ),
        ),
    ),
    ultimate=active(
        "lakes_gift",
        "Lake's Gift",
        target="self",
        description="The Lady creates a Reflecting Pool for 2 rounds at her position. Then, if there's a fainted ally, she knocks herself out and revives the most recently fainted ally at her position at 50% HP. They get +15 Attack for 2 rounds.",
        special="lakes_gift",
    ),
)


ELLA = AdventurerDef(
    id="ashen_ella",
    name="Ashen Ella",
    hp=226,
    attack=78,
    defense=48,
    speed=82,
    innate=passive("two_lives", "Two Lives", "Ella cannot Switch weapons. Instead, she always has the Obsidian Slippers in the frontline and the Dusty Broom in the backline.", special="two_lives"),
    signature_weapons=(
        weapon(
            "obsidian_slippers",
            "Obsidian Slippers",
            "magic",
            active(
                "obsidian_slippers_strike",
                "Strike",
                power=70,
                cooldown=1,
                counts_as_spell=True,
                spread=True,
                target_statuses=(status("burn", 2),),
            ),
            passive_skills=(passive("struck_midnight", "Struck Midnight", "Swap and heal when reduced to 50% HP.", special="struck_midnight"),),
        ),
        weapon(
            "dusty_broom",
            "Dusty Broom",
            "melee",
            active("dusty_broom_strike", "Strike", power=10),
            passive_skills=(passive("fae_blessing", "Fae Blessing", "Untargetable and cannot cast Spells.", special="fae_blessing"),),
        ),
    ),
    ultimate=active(
        "crowstorm",
        "Crowstorm",
        target="self",
        description="Become untargetable and keep empowered magic Strikes ready for 2 rounds.",
        special="crowstorm",
    ),
)


MARCH_HARE = AdventurerDef(
    id="march_hare",
    name="March Hare",
    hp=224,
    attack=68,
    defense=44,
    speed=84,
    innate=passive("on_time", "On Time!", "While the March Hare is frontline, the frontline enemy has -10 Speed.", special="on_time"),
    signature_weapons=(
        weapon(
            "stitch_in_time",
            "Stitch in Time",
            "magic",
            active(
                "stitch_in_time_strike",
                "Strike",
                power=60,
                cooldown=1,
                counts_as_spell=True,
                target_statuses=(status("shock", 2),),
                description="Gain power if Hare Swapped this round.",
                special="stitch_in_time_strike",
            ),
        ),
        weapon(
            "cracked_stopwatch",
            "Cracked Stopwatch",
            "magic",
            active(
                "cracked_stopwatch_strike",
                "Strike",
                power=20,
                counts_as_spell=True,
                description="If the target is Shocked, Hare may cast a Spell as a bonus action.",
                special="cracked_stopwatch",
            ),
            spells=(
                active(
                    "rabbit_hole",
                    "Rabbit Hole",
                    target="self",
                    cooldown=2,
                    description="Gain an extra action next round for each Spell cast this round.",
                    special="rabbit_hole",
                ),
            ),
        ),
    ),
    ultimate=active(
        "tea_party",
        "Tea Party",
        target="none",
        description="Allied Spells do not go on cooldown for 2 rounds.",
        special="tea_party",
    ),
)


BRIAR = AdventurerDef(
    id="briar_rose",
    name="Briar Rose",
    hp=228,
    attack=54,
    defense=46,
    speed=76,
    innate=passive("curse_of_sleeping", "Curse of Sleeping", "The lowest HP Rooted enemy is unable to act each round but gains Root Immunity for 2 rounds at the end of round.", special="curse_of_sleeping"),
    signature_weapons=(
        weapon(
            "spindle_bow",
            "Spindle Bow",
            "ranged",
            active("spindle_bow_strike", "Strike", power=40, ammo_cost=1, bonus_power_if_status="root", bonus_power=20),
            ammo=3,
            spells=(
                active(
                    "vine_snare",
                    "Vine Snare",
                    target="self",
                    cooldown=2,
                    description="Next Strike removes Root Immunity and does not consume Ammo.",
                    special="vine_snare",
                ),
            ),
        ),
        weapon(
            "thorn_snare",
            "Thorn Snare",
            "ranged",
            active("thorn_snare_strike", "Strike", power=70, ammo_cost=1, spread=True, target_statuses=(status("root", 2),)),
            ammo=1,
            passive_skills=(passive("drowsiness", "Drowsiness", "Root enemies who Swap positions.", special="drowsiness"),),
        ),
    ),
    ultimate=active(
        "falling_kingdom",
        "Falling Kingdom",
        target="none",
        description="Root all enemies and suppress Root Immunity from Curse of Sleeping.",
        special="falling_kingdom",
    ),
)


HUMBERT = AdventurerDef(
    id="wayward_humbert",
    name="Wayward Humbert",
    hp=246,
    attack=66,
    defense=56,
    speed=64,
    innate=passive("shifty_allegiance", "Shifty Allegiance", "Humbert can Switch weapons as a Bonus Action.", special="bonus_switch"),
    signature_weapons=(
        weapon(
            "convicted_shotgun",
            "Convicted Shotgun",
            "ranged",
            active("convicted_shotgun_strike", "Strike", power=55, ammo_cost=1),
            ammo=2,
            passive_skills=(passive("trigger_finger", "Trigger Finger", "Combust the weapon after it Strikes.", special="trigger_finger"),),
        ),
        weapon(
            "pallid_musket",
            "Pallid Musket",
            "ranged",
            active("pallid_musket_strike", "Strike", power=40, ammo_cost=1, description="Repair Humbert's secondary weapon.", special="repair_secondary_weapon"),
            ammo=4,
            spells=(active("liquid_courage", "Liquid Courage", target="self", heal=40, cooldown=2),),
        ),
    ),
    ultimate=active(
        "jovial_shot",
        "Jovial Shot",
        target="self",
        description="Fully restore HP and empower the next combusted Strike.",
        special="jovial_shot",
    ),
)


ROBIN = AdventurerDef(
    id="robin_hooded_avenger",
    name="Robin, Hooded Avenger",
    hp=232,
    attack=70,
    defense=46,
    speed=80,
    innate=passive("keen_eye", "Keen Eye", "Robin's Strikes can't be redirected and ignore Guard.", special="keen_eye"),
    signature_weapons=(
        weapon(
            "the_flock",
            "The Flock",
            "ranged",
            active("the_flock_strike", "Strike", power=45, ammo_cost=1, spread=True, target_statuses=(status("spotlight", 2),)),
            ammo=3,
            spells=(active("spread_fortune", "Spread Fortune", target="self", cooldown=2, description="Ignore the spread damage nerf.", special="spread_fortune"),),
        ),
        weapon(
            "kingmaker",
            "Kingmaker",
            "melee",
            active("kingmaker_strike", "Strike", power=60, description="+30 power against backline targets.", special="bonus_vs_backline_30"),
        ),
    ),
    ultimate=active(
        "disenfranchise",
        "Disenfranchise",
        target="self",
        description="Strikes steal Attack, Defense, and Speed for 2 rounds.",
        special="disenfranchise",
    ),
)


LIESL = AdventurerDef(
    id="matchbox_liesl",
    name="Matchbox Liesl",
    hp=256,
    attack=58,
    defense=54,
    speed=72,
    innate=passive("purifying_flame", "Purifying Flame", "Liesl and her allies are immune to Burn. Whenever an enemy takes damage from a Burn, heal Liesl's lowest HP ally equal to the amount.", special="purifying_flame"),
    signature_weapons=(
        weapon(
            "matchsticks",
            "Matchsticks",
            "ranged",
            active("matchsticks_strike", "Strike", power=40, ammo_cost=1, target_statuses=(status("burn", 2),)),
            ammo=6,
            passive_skills=(passive("cauterize", "Cauterize", "Burned enemies cannot heal.", special="cauterize"),),
        ),
        weapon(
            "eternal_torch",
            "Eternal Torch",
            "magic",
            active("eternal_torch_strike", "Strike", power=60, cooldown=1, counts_as_spell=True, lifesteal=0.30),
            passive_skills=(passive("flame_of_renewal", "Flame of Renewal", "Allies heal when Liesl is knocked out.", special="flame_of_renewal"),),
        ),
    ),
    ultimate=active(
        "cleansing_inferno",
        "Cleansing Inferno",
        target="none",
        description="Mirror allied healing and Burn damage across teams for 2 rounds.",
        special="cleansing_inferno",
    ),
)


GOOD_BEAST = AdventurerDef(
    id="the_good_beast",
    name="The Good Beast",
    hp=290,
    attack=62,
    defense=68,
    speed=50,
    innate=passive("protective_soul", "Protective Soul", "The first ally The Good Beast swaps with becomes his guest, and has +15 Defense.", special="protective_soul"),
    signature_weapons=(
        weapon(
            "rosebush_sword",
            "Rosebush Sword",
            "melee",
            active("rosebush_sword_strike", "Strike", power=65, description="+15 power if the target struck the guest last turn.", special="guest_bonus"),
            spells=(active("crystal_ball", "Crystal Ball", target="enemy", cooldown=2, target_statuses=(status("spotlight", 2),), description="Spotlight the last enemy that struck the guest.", special="guest_attacker_spotlight"),),
        ),
        weapon(
            "dinner_bell",
            "Dinner Bell",
            "magic",
            active("dinner_bell_strike", "Strike", power=70, cooldown=1, counts_as_spell=True, target="ally", description="Target allies to restore HP equal to half the would-be damage.", special="ally_heal_from_damage"),
            passive_skills=(passive("hospitality", "Hospitality", "Guests restore +10 HP from all sources.", special="hospitality"),),
        ),
    ),
    ultimate=active(
        "happily_ever_after",
        "Happily Ever After",
        target="self",
        description="The Beast and guest share the higher Attack, Defense, and Speed.",
        special="happily_ever_after",
    ),
)


GREEN_KNIGHT = AdventurerDef(
    id="the_green_knight",
    name="The Green Knight",
    hp=278,
    attack=60,
    defense=65,
    speed=24,
    innate=passive("challenge_accepted", "Challenge Accepted", "The Green Knight may Swap positions as a Bonus Action.", special="bonus_swap"),
    signature_weapons=(
        weapon(
            "the_search",
            "The Search",
            "ranged",
            active("the_search_strike", "Strike", power=50, ammo_cost=1, description="+15 Power against targets in the Green Knight's lane.", special="lane_bonus_15"),
            ammo=3,
        ),
        weapon(
            "the_answer",
            "The Answer",
            "melee",
            active("the_answer_strike", "Strike", power=70),
            passive_skills=(passive("awaited_blow", "Awaited Blow", "The Green Knight retaliates for 35 Power against incoming attackers not in his lane.", special="awaited_blow"),),
        ),
    ),
    ultimate=active(
        "fated_duel",
        "Fated Duel",
        target="enemy",
        description="For 2 rounds, only those in the Green Knight's lane can act.",
        special="fated_duel",
    ),
)


RAPUNZEL = AdventurerDef(
    id="rapunzel_the_golden",
    name="Rapunzel the Golden",
    hp=262,
    attack=64,
    defense=60,
    speed=34,
    innate=passive("flowing_locks", "Flowing Locks", "Rapunzel can target a backline enemy with a Melee Strike once per encounter. Refreshes when she casts a Spell.", special="flowing_locks"),
    signature_weapons=(
        weapon(
            "golden_snare",
            "Golden Snare",
            "melee",
            active("golden_snare_strike", "Strike", power=65, target_statuses=(status("root", 2),)),
            spells=(active("lower_guard", "Lower Guard", target="enemy", cooldown=2, target_statuses=(status("expose", 2),), description="Refresh Root and Expose for 2 rounds.", special="refresh_root_expose"),),
        ),
        weapon(
            "ivory_tower",
            "Ivory Tower",
            "melee",
            active("ivory_tower_strike", "Strike", power=65, target_statuses=(status("weaken", 2),)),
            spells=(active("sanctuary", "Sanctuary", target="ally", heal=60, cooldown=1),),
        ),
    ),
    ultimate=active(
        "severed_tether",
        "Severed Tether",
        target="self",
        description="Trade Defense for Attack and Speed while Flowing Locks stays active.",
        special="severed_tether",
    ),
)


PINOCCHIO = AdventurerDef(
    id="pinocchio_cursed_puppet",
    name="Pinocchio, Cursed Puppet",
    hp=232,
    attack=50,
    defense=44,
    speed=76,
    innate=passive("growing_pains", "Growing Pains", "When Pinocchio ends the round in the frontline, he gains 1 Malice, up to 6. Pinocchio has +5 attack and +5 defense for each Malice.", special="growing_pains"),
    signature_weapons=(
        weapon(
            "wooden_club",
            "Wooden Club",
            "melee",
            active("wooden_club_strike", "Strike", power=45, description="+5 power per Malice.", special="wooden_club"),
            spells=(active("bloodstain", "Bloodstain", target="self", cooldown=0, description="Lose 40 HP and gain 2 Malice.", special="bloodstain"),),
        ),
        weapon(
            "string_cutter",
            "String Cutter",
            "magic",
            active("string_cutter_strike", "Strike", power=60, cooldown=1, counts_as_spell=True, lifesteal=0.20),
            passive_skills=(passive("become_real", "Become Real", "At 3+ Malice, Spells stop going on cooldown and Pinocchio becomes status immune.", special="become_real"),),
        ),
    ),
    ultimate=active(
        "blue_faeries_boon",
        "Blue Faerie's Boon",
        target="self",
        description="Gain Speed and jump to 6 Malice for 2 rounds.",
        special="blue_faeries_boon",
    ),
)


RUMPEL = AdventurerDef(
    id="rumpelstiltskin",
    name="Rumpelstiltskin",
    hp=240,
    attack=58,
    defense=52,
    speed=72,
    innate=passive("art_of_the_deal", "Art of the Deal", "The first time another adventurer gains a stat bonus each round, Rumpelstiltskin also gains it.", special="art_of_the_deal"),
    signature_weapons=(
        weapon(
            "devils_contract",
            "Devil's Contract",
            "magic",
            active(
                "devils_contract_strike",
                "Strike",
                power=100,
                cooldown=2,
                counts_as_spell=True,
                target_buffs=(stat("attack", 10, 2), stat("defense", 10, 2), stat("speed", 10, 2)),
            ),
        ),
        weapon(
            "spinning_wheel",
            "Spinning Wheel",
            "ranged",
            active("spinning_wheel_strike", "Strike", power=45, ammo_cost=1, description="Apply rotating stat penalties.", special="spinning_wheel"),
            ammo=3,
            spells=(
                active(
                    "straw_to_gold",
                    "Straw to Gold",
                    target="enemy",
                    cooldown=2,
                    description="Copy the target's stat penalties and reverse them.",
                    special="straw_to_gold",
                ),
            ),
        ),
    ),
    ultimate=active(
        "devils_nursery",
        "Devil's Nursery",
        target="self",
        description="Boost gained bonuses and inflicted penalties for 2 rounds.",
        special="devils_nursery",
    ),
)


ASHA = AdventurerDef(
    id="sea_wench_asha",
    name="Sea Wench Asha",
    hp=234,
    attack=68,
    defense=46,
    speed=78,
    innate=passive("stolen_voices", "Stolen Voices", "When an enemy uses a nonattacking Spell, Asha steals it for 2 rounds. She can use it for the duration.", special="stolen_voices"),
    signature_weapons=(
        weapon(
            "frost_scepter",
            "Frost Scepter",
            "magic",
            active("frost_scepter_strike", "Strike", power=65, cooldown=1, counts_as_spell=True, description="The target cannot Strike next turn.", special="cant_strike_next_turn"),
        ),
        weapon(
            "mirror_blade",
            "Mirror Blade",
            "magic",
            active("mirror_blade_strike", "Strike", counts_as_spell=True, description="Copy the last Strike that damaged Asha.", special="mirror_blade"),
        ),
    ),
    ultimate=active(
        "foam_prison",
        "Foam Prison",
        target="enemy",
        description="Steal the target's Ultimate Spell for 2 rounds and use it.",
        special="foam_prison",
    ),
)


VASILISA = AdventurerDef(
    id="destitute_vasilisa",
    name="Destitute Vasilisa",
    hp=248,
    attack=50,
    defense=60,
    speed=64,
    innate=passive("mothers_presence", "Mother's Presence", "Whenever Vasilisa or an ally are targeted by a Spell, Guard them for 2 rounds.", special="mothers_presence"),
    signature_weapons=(
        weapon(
            "guiding_doll",
            "Guiding Doll",
            "magic",
            active(
                "guiding_doll_strike",
                "Strike",
                power=65,
                cooldown=1,
                counts_as_spell=True,
                description="The next ally Strike against this target gains +25 power and 25% lifesteal.",
                special="guiding_doll",
            ),
        ),
        weapon(
            "skull_lantern",
            "Skull Lantern",
            "magic",
            active(
                "skull_lantern_strike",
                "Strike",
                power=60,
                cooldown=1,
                counts_as_spell=True,
                description="Gain +15 power if Vasilisa or an ally is Guarded.",
                special="skull_lantern",
            ),
            passive_skills=(passive("guiding_light", "Guiding Light", "Vasilisa's enemy-targeted Spells Spotlight for 2 rounds.", special="guiding_light"),),
        ),
    ),
    ultimate=active(
        "witchs_blessing",
        "Witch's Blessing",
        target="none",
        description="For 2 rounds, Strikes against enemies have 25% lifesteal.",
        special="witchs_blessing",
    ),
)


ALI_BABA = AdventurerDef(
    id="ali_baba",
    name="Ali Baba, Bandit King",
    hp=234,
    attack=56,
    defense=46,
    speed=90,
    innate=passive("open_sesame", "Open Sesame", "Ali Baba ignores stat bonuses and penalties (both his and his enemies).", special="open_sesame"),
    signature_weapons=(
        weapon(
            "thiefs_dagger",
            "Thief's Dagger",
            "melee",
            active(
                "thiefs_dagger_strike",
                "Strike",
                power=60,
                description="Ali Baba can cast the target's Artifact Spell as a bonus action this round.",
                special="thiefs_dagger",
            ),
            spells=(
                active(
                    "seal_the_cave",
                    "Seal the Cave",
                    target="enemy",
                    cooldown=2,
                    description="Increase the target's cooldowns by 1 round each.",
                    special="seal_the_cave",
                ),
            ),
        ),
        weapon(
            "jar_of_oil",
            "Jar of Oil",
            "magic",
            active(
                "jar_of_oil_strike",
                "Strike",
                power=70,
                cooldown=1,
                counts_as_spell=True,
                target_statuses=(status("burn", 2),),
            ),
            passive_skills=(passive("no_escape", "No Escape", "Enemy Adventurers cannot cast their Artifact Spell while Burned or if Seal the Cave affected one of their cooldowns.", special="no_escape"),),
        ),
    ),
    ultimate=active(
        "forty_thieves",
        "Forty Thieves",
        target="none",
        description="For 2 rounds, enemies do not reload Ammo when they Switch weapons.",
        special="forty_thieves",
    ),
)


MAUI = AdventurerDef(
    id="maui_sunthief",
    name="Maui, Sun-Thief",
    hp=308,
    attack=60,
    defense=78,
    speed=32,
    innate=passive("conquer_death", "Conquer Death", "Maui survives fatal damage at 1 HP once per encounter.", special="conquer_death"),
    signature_weapons=(
        weapon(
            "whale_jaw_hook",
            "Whale-Jaw Hook",
            "melee",
            active("whale_jaw_hook_strike", "Strike", power=65, target_statuses=(status("expose", 2),)),
            spells=(
                active(
                    "swallow_the_sun",
                    "Swallow the Sun",
                    target="self",
                    cooldown=2,
                    description="Maui and allies gain +15 Defense for 2 rounds.",
                    special="swallow_the_sun",
                ),
            ),
        ),
        weapon(
            "ancestral_warclub",
            "Ancestral Warclub",
            "melee",
            active("ancestral_warclub_strike", "Strike", power=70),
            passive_skills=(passive("shapeshifter", "Shapeshifter", "Maui uses Defense instead of Attack when dealing damage.", special="shapeshifter"),),
        ),
    ),
    ultimate=active(
        "raise_the_sky",
        "Raise the Sky",
        target="self",
        description="Reset Conquer Death. Double Maui's Defense for 2 rounds.",
        special="raise_the_sky",
    ),
)


KAMA = AdventurerDef(
    id="kama_the_honeyed",
    name="Kama the Honeyed",
    hp=240,
    attack=62,
    defense=52,
    speed=74,
    innate=passive("target_of_affection", "Target of Affection", "Enemies in Kama's lane take +10 damage from ally Strikes.", special="target_of_affection"),
    signature_weapons=(
        weapon(
            "sugarcane_bow",
            "Sugarcane Bow",
            "ranged",
            active("sugarcane_bow_strike", "Strike", power=55, ammo_cost=1, target_statuses=(status("spotlight", 2),)),
            ammo=3,
            passive_skills=(passive("flower_arrows", "Flower Arrows", "Sugarcane Bow does not reload by Switching weapons. Other effects can pick up flower arrows to reload 1 Ammo.", special="flower_arrows"),),
        ),
        weapon(
            "the_stinger",
            "The Stinger",
            "ranged",
            active(
                "the_stinger_strike",
                "Strike",
                power=45,
                ammo_cost=1,
                description="If the target is Spotlighted, Shock them and pick up a flower arrow.",
                special="the_stinger",
            ),
            ammo=3,
            spells=(
                active(
                    "sukas_eyes",
                    "Suka's Eyes",
                    target="none",
                    cooldown=2,
                    description="Spotlight all enemies for 2 rounds.",
                    special="sukas_eyes",
                ),
            ),
        ),
    ),
    ultimate=active(
        "gaze_of_love",
        "Gaze of Love",
        target="none",
        description="For 2 rounds, enemies are Spotlighted and ranged Strikes do not consume Ammo against Spotlighted targets.",
        special="gaze_of_love",
    ),
)


REYNARD = AdventurerDef(
    id="reynard_lupine_trickster",
    name="Reynard, Lupine Trickster",
    hp=240,
    attack=64,
    defense=50,
    speed=88,
    innate=passive(
        "opportunist",
        "Opportunist",
        "Reynard deals +15 damage to targets that did not Strike last round.",
        special="opportunist",
    ),
    signature_weapons=(
        weapon(
            "foxfire_bow",
            "Foxfire Bow",
            "ranged",
            active(
                "foxfire_bow_strike",
                "Strike",
                power=45,
                ammo_cost=1,
                target_debuffs=(stat("defense", 10, 2),),
                description="The target has -10 Defense for 2 rounds.",
                special="foxfire_bow",
            ),
            ammo=3,
            passive_skills=(
                passive(
                    "glowing_trail",
                    "Glowing Trail",
                    "Reynard acts the turn before the target of his Strike.",
                    special="glowing_trail",
                ),
            ),
        ),
        weapon(
            "fang",
            "Fang",
            "melee",
            active(
                "fang_strike",
                "Strike",
                power=65,
                description="+15 Power if the target has a stat penalty.",
                special="fang_bonus_vs_penalty",
            ),
            spells=(
                active(
                    "silver_tongue",
                    "Silver Tongue",
                    target="enemy",
                    cooldown=2,
                    target_statuses=(status("taunt", 2),),
                    description="Taunt target enemy for 2 rounds.",
                ),
            ),
        ),
    ),
    ultimate=active(
        "king_of_thieves",
        "King of Thieves",
        target="self",
        description="Reynard's next Strike steals 30 Attack from the target for 2 rounds.",
        special="king_of_thieves",
    ),
)


SCHEHERAZADE = AdventurerDef(
    id="scheherazade_dawns_ransom",
    name="Scheherazade, Dawn's Ransom",
    hp=250,
    attack=52,
    defense=62,
    speed=66,
    innate=passive(
        "thousand_and_one_nights",
        "Thousand and One Nights",
        "When an enemy casts a Spell, if they cast a Spell this round, it has a +1 round cooldown.",
        special="thousand_and_one_nights",
    ),
    signature_weapons=(
        weapon(
            "tome_of_ancients",
            "Tome of Ancients",
            "magic",
            active(
                "tome_of_ancients_strike",
                "Strike",
                power=60,
                cooldown=1,
                counts_as_spell=True,
                target_debuffs=(stat("speed", 10, 2),),
            ),
            passive_skills=(
                passive(
                    "stay_the_blade",
                    "Stay the Blade",
                    "While Scheherezade is frontline, enemy Strikes deal -10 damage.",
                    special="stay_the_blade",
                ),
            ),
        ),
        weapon(
            "lamp_of_infinity",
            "Lamp of Infinity",
            "magic",
            active(
                "lamp_of_infinity_strike",
                "Strike",
                power=60,
                cooldown=1,
                counts_as_spell=True,
                description="The ally to the right of Scheherezade restores 40 HP.",
                special="lamp_of_infinity",
            ),
            passive_skills=(
                passive(
                    "evermore",
                    "Evermore",
                    "The first time each encounter Scheherezade or an ally would take fatal damage, they survive at 1 HP.",
                    special="evermore",
                ),
            ),
        ),
    ),
    ultimate=active(
        "daybreak",
        "Daybreak",
        target="none",
        description="Clear the enemy Ultimate Meter. For 2 rounds, the enemy Ultimate Meter cannot be raised.",
        special="daybreak",
    ),
)


ANANSI = AdventurerDef(
    id="storyweaver_anansi",
    name="Storyweaver Anansi",
    hp=236,
    attack=62,
    defense=48,
    speed=88,
    innate=passive(
        "tangled_plots",
        "Tangled Plots",
        "While Anansi is frontline, enemies cannot cast Reactive Spells.",
        special="tangled_plots",
    ),
    signature_weapons=(
        weapon(
            "the_pen",
            "The Pen",
            "ranged",
            active(
                "the_pen_strike",
                "Strike",
                power=35,
                ammo_cost=1,
                target_statuses=(status("root", 2),),
            ),
            ammo=8,
            spells=(
                active(
                    "silken_prose",
                    "Silken Prose",
                    target="enemy",
                    cooldown=2,
                    description="For 2 rounds, Strikes deal +8 damage to target Rooted enemy.",
                    special="silken_prose",
                ),
            ),
        ),
        weapon(
            "the_sword",
            "The Sword",
            "melee",
            active(
                "the_sword_strike",
                "Strike",
                power=65,
                description="Can target backline enemies that cast an Artifact's Spell last round.",
                special="anansi_sword",
            ),
            passive_skills=(
                passive(
                    "the_twist",
                    "The Twist!",
                    "When Anansi Switches to The Sword, they get +15 Attack and -15 Speed for 2 rounds.",
                    special="the_twist",
                ),
            ),
        ),
    ),
    ultimate=active(
        "web_of_centuries",
        "Web of Centuries",
        target="self",
        description="For 2 rounds, Anansi can cast any Adventurer's Spell.",
        special="web_of_centuries",
    ),
)


ODYSSEUS = AdventurerDef(
    id="odysseus_the_nobody",
    name="Odysseus the Nobody",
    hp=276,
    attack=70,
    defense=62,
    speed=56,
    innate=passive(
        "cunning_retreat",
        "Cunning Retreat",
        "When Odysseus Swaps positions, he gets +15 Attack for 2 rounds.",
        special="cunning_retreat",
    ),
    signature_weapons=(
        weapon(
            "olivewood_spear",
            "Olivewood Spear",
            "melee",
            active(
                "olivewood_spear_strike",
                "Strike",
                power=65,
                description="+15 Power against targets in Odysseus' lane.",
                special="lane_bonus_15",
            ),
            spells=(
                active(
                    "eye_piercer",
                    "Eye Piercer",
                    target="self",
                    cooldown=2,
                    description="Odysseus' next Strike ignores targeting restrictions.",
                    special="next_strike_ignore_targeting",
                ),
            ),
        ),
        weapon(
            "beggars_greatbow",
            "Beggar's Greatbow",
            "ranged",
            active(
                "beggars_greatbow_strike",
                "Strike",
                power=55,
                ammo_cost=1,
                description="Puts an arrow in the target.",
                special="beggars_greatbow",
            ),
            ammo=3,
            passive_skills=(
                passive(
                    "barbed_arrows",
                    "Barbed Arrows",
                    "Beggar's Greatbow does not reload by Switching weapons. When Odysseus Switches weapons, his next Melee Strike deals +5 damage for each arrow in the target and fully reloads Beggar's Greatbow.",
                    special="barbed_arrows",
                ),
            ),
        ),
    ),
    ultimate=active(
        "trojan_horse",
        "Trojan Horse",
        target="self",
        description="Odysseus Swaps positions and takes 0 damage from Strikes this round. For 2 rounds, Odysseus can Switch Weapons as a Bonus Action.",
        special="trojan_horse",
    ),
)


WITCH_OF_THE_EAST = AdventurerDef(
    id="witch_of_the_east",
    name="Witch of the East",
    hp=244,
    attack=50,
    defense=58,
    speed=74,
    innate=passive(
        "headwinds",
        "Headwinds",
        "The Witch of the East creates an air current in her lane for 2 rounds when she Swaps positions and at the start of an encounter.",
        special="headwinds",
    ),
    signature_weapons=(
        weapon(
            "zephyr",
            "Zephyr",
            "magic",
            active(
                "zephyr_strike",
                "Strike",
                power=55,
                cooldown=1,
                counts_as_spell=True,
                description="Swaps target with the enemy to their left.",
                special="zephyr",
            ),
            passive_skills=(
                passive(
                    "heavy_gale",
                    "Heavy Gale",
                    "Enemies in an air current have -15 Attack.",
                    special="heavy_gale",
                ),
            ),
        ),
        weapon(
            "comet",
            "Comet",
            "melee",
            active(
                "comet_strike",
                "Strike",
                power=60,
                description="The target takes +15 damage from the next Magic Strike.",
                special="comet",
            ),
            passive_skills=(
                passive(
                    "unroof",
                    "Unroof",
                    "The Witch of the East has +15 Speed while in an air current.",
                    special="unroof",
                ),
            ),
        ),
    ),
    ultimate=active(
        "dream_twister",
        "Dream Twister",
        target="none",
        description="Create an air current in each lane. Allies have +15 Speed for 2 rounds.",
        special="dream_twister",
    ),
)


TAM_LIN = AdventurerDef(
    id="tam_lin_thornbound",
    name="Tam Lin, Thornbound",
    hp=292,
    attack=58,
    defense=76,
    speed=34,
    innate=passive(
        "faeries_ransom",
        "Faerie's Ransom",
        "The first time each round an enemy would inflict a status condition on Tam Lin, cleanse it and he has +15 Defense for 2 rounds.",
        special="faeries_ransom",
    ),
    signature_weapons=(
        weapon(
            "butterfly_knife",
            "Butterfly Knife",
            "melee",
            active(
                "butterfly_knife_strike",
                "Strike",
                power=65,
                target_statuses=(status("taunt", 2),),
            ),
            passive_skills=(
                passive(
                    "bargain",
                    "Bargain",
                    "Enemies in Tam Lin's lane who Swap positions take +10 damage from Strikes for 2 rounds.",
                    special="bargain",
                ),
            ),
        ),
        weapon(
            "beam_of_light",
            "Beam of Light",
            "melee",
            active(
                "beam_of_light_strike",
                "Strike",
                power=65,
                target_statuses=(status("burn", 2),),
            ),
            passive_skills=(
                passive(
                    "holy_water",
                    "Holy Water",
                    "Allies have the effects of Faerie's Ransom.",
                    special="holy_water",
                ),
            ),
        ),
    ),
    ultimate=active(
        "polymorph",
        "Polymorph",
        target="any",
        description="Target Adventurer becomes a beast for 2 rounds and can't swap and has +15 Attack, +15 Defense, +15 Speed, and their Strikes have 30% recoil.",
        special="polymorph",
    ),
)


ADVENTURERS = [
    RED,
    JACK,
    GRETEL,
    CONSTANTINE,
    HUNOLD,
    ROLAND,
    PORCUS,
    LADY,
    ELLA,
    MARCH_HARE,
    BRIAR,
    HUMBERT,
    ROBIN,
    LIESL,
    GOOD_BEAST,
    GREEN_KNIGHT,
    RAPUNZEL,
    PINOCCHIO,
    RUMPEL,
    ASHA,
    VASILISA,
    ALI_BABA,
    MAUI,
    KAMA,
    REYNARD,
    SCHEHERAZADE,
    ANANSI,
    ODYSSEUS,
    WITCH_OF_THE_EAST,
    TAM_LIN,
]
ADVENTURERS = _sync_adventurer_descriptions_from_rulebook(ADVENTURERS)


ADVENTURERS_BY_ID = {adventurer.id: adventurer for adventurer in ADVENTURERS}
WEAPONS_BY_ID = {
    weapon_def.id: weapon_def
    for adventurer in ADVENTURERS
    for weapon_def in adventurer.signature_weapons
}
ULTIMATES_BY_ID = {adventurer.ultimate.id: adventurer.ultimate for adventurer in ADVENTURERS}
ALL_ADVENTURER_SPELLS = tuple(
    spell
    for adventurer in ADVENTURERS
    for weapon_def in adventurer.signature_weapons
    for spell in weapon_def.spells
)
