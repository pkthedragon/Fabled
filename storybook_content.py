from __future__ import annotations

import random
from dataclasses import dataclass

from quests_ruleset_data import ADVENTURERS, ARTIFACTS, CLASS_SKILLS


@dataclass(frozen=True)
class StoryQuest:
    id: str
    name: str
    locale: str
    blurb: str
    difficulty: str
    reward_gold: int
    reward_exp: int
    threat: str
    note: str


STORY_QUESTS = [
    StoryQuest(
        id="embers_under_briarhold",
        name="Embers Under Briarhold",
        locale="Briarhold Keep",
        blurb="A rootbound garrison is choking the western road. Break the line before the court's supply wagons vanish into the fog.",
        difficulty="Veteran",
        reward_gold=320,
        reward_exp=28,
        threat="Heavy control and slow pressure",
        note="Bring at least one backline carry. Roots and speed penalties stack quickly here.",
    ),
    StoryQuest(
        id="the_gilded_conspiracy",
        name="The Gilded Conspiracy",
        locale="The Gilt Exchange",
        blurb="Mercenary bookkeepers have turned the market floor into a dueling hall. Survive the opener and cut through their defense shells.",
        difficulty="Champion",
        reward_gold=410,
        reward_exp=34,
        threat="Frontline defense and artifact tempo",
        note="Expose and spotlight are unusually valuable. Expect artifact spells early.",
    ),
    StoryQuest(
        id="chorus_in_the_mire",
        name="Chorus In The Mire",
        locale="Fen of Hollow Lanterns",
        blurb="A drowned chorus is calling travelers off the path. Enter the mire, sever the song, and leave before the water learns your name.",
        difficulty="Heroic",
        reward_gold=520,
        reward_exp=40,
        threat="Shock, recoil, and magic burst",
        note="Backline speed matters more than raw attack. Consider a fast cleanser or weapon switch plan.",
    ),
    StoryQuest(
        id="the_clockwork_vow",
        name="The Clockwork Vow",
        locale="The Brass Reliquary",
        blurb="A vow-engine beneath the city walls is awakening. Draft a compact strike team and break it before the noble houses bind it to their war banners.",
        difficulty="Legend",
        reward_gold=650,
        reward_exp=48,
        threat="Scaling bruisers and delayed finishers",
        note="Do not overload on slow tanks. You need enough tempo to punish scaling ultimates.",
    ),
]


BOUT_MODES = [
    {
        "id": "local",
        "name": "Local PvP",
        "subtitle": "Flexible duel shell for AI rivals or a LAN challenger.",
        "note": "Best for testing tactical reads and formation discipline without ladder pressure.",
    },
    {
        "id": "online",
        "name": "Online PvP",
        "subtitle": "Hidden-loadout duel pacing with the same mirrored prep flow.",
        "note": "Works against AI or a LAN opponent inside the current desktop build.",
    },
    {
        "id": "friendly",
        "name": "Friendly Match",
        "subtitle": "Quick draft with no ladder pressure.",
        "note": "Use this when you want to practice picks from the shared pool of nine.",
    },
    {
        "id": "ranked",
        "name": "Ranked Bout",
        "subtitle": "Structured duel with Glory at stake.",
        "note": "Drafting is identical; only matchmaking pressure and post-match Glory change.",
    },
]


CATALOG_SECTIONS = [
    "Adventurers",
    "Class Skills",
    "Artifacts",
]


SHOP_TABS = ["Artifacts"]
COSMETIC_CATEGORIES = ["Hats", "Shirts", "Pants", "Socks", "Shoes"]

ARTIFACT_SHOP_PRICES = {
    "holy_grail": 500,
    "winged_sandals": 450,
    "lightning_helm": 500,
    "golden_fleece": 400,
    "arcane_hourglass": 850,
    "naiads_knife": 450,
    "last_prism": 550,
    "misericorde": 425,
    "selkies_skin": 600,
    "red_hood": 450,
    "enchanted_lamp": 700,
    "magic_mirror": 800,
    "nettle_smock": 575,
    "goose_quill": 750,
    "cursed_spindle": 650,
    "bluebeards_key": 450,
    "sun_gods_banner": 525,
    "dire_wolf_spine": 350,
    "soaring_crown": 425,
    "fading_diadem": 400,
    "iron_rosary": 550,
    "dragons_horn": 475,
    "bottled_clouds": 475,
    "glass_slipper": 650,
    "black_torch": 500,
}


def role_tags_for_adventurer(adventurer) -> list[str]:
    tags: list[str] = []
    if adventurer.hp >= 230 or adventurer.defense >= 88:
        tags.append("Tank")
    if adventurer.attack >= 96:
        tags.append("Carry")

    healing_present = False
    control_present = False
    for weapon in adventurer.signature_weapons:
        for effect in (weapon.strike, *weapon.spells):
            if effect.heal > 0:
                healing_present = True
            if effect.target_statuses or effect.target_debuffs or effect.special:
                control_present = True
    if healing_present:
        tags.append("Support")
    if control_present:
        tags.append("Control")
    if not tags:
        tags.append("Skirmish")
    return tags[:3]


def quest_role_summary(members) -> str:
    if not members:
        return "Draft an adventurer to begin shaping the party."
    roles = set()
    for member in members:
        adventurer = next(adv for adv in ADVENTURERS if adv.id == member["adventurer_id"])
        roles.update(role_tags_for_adventurer(adventurer))
    ordered = [role for role in ("Tank", "Carry", "Support", "Control", "Skirmish") if role in roles]
    return ", ".join(ordered) if ordered else "Skirmish"


def quest_warnings(members) -> list[str]:
    warnings: list[str] = []
    if not members:
        return ["No adventurers selected yet."]

    slots = {member["slot"] for member in members}
    if "front" not in slots:
        warnings.append("A frontline anchor is mandatory.")
    if len(slots) != len(members):
        warnings.append("Two adventurers are sharing a position.")

    fast_units = 0
    for member in members:
        adventurer = next(adv for adv in ADVENTURERS if adv.id == member["adventurer_id"])
        if adventurer.speed >= 80:
            fast_units += 1
    if fast_units == 0:
        warnings.append("This lineup is slow. Expect to act late after the backline penalty.")

    healing_present = False
    for member in members:
        adventurer = next(adv for adv in ADVENTURERS if adv.id == member["adventurer_id"])
        for weapon in adventurer.signature_weapons:
            for effect in weapon.spells:
                if effect.heal > 0:
                    healing_present = True
    if not healing_present:
        warnings.append("No built-in healing detected.")

    return warnings[:3] or ["Formation looks stable."]


def recommendation_notes(members) -> list[str]:
    notes: list[str] = []
    if not members:
        return ["Balanced teams usually want one frontline bruiser and one fast backliner."]
    fronts = [member for member in members if member["slot"] == "front"]
    if fronts:
        front_adv = next(adv for adv in ADVENTURERS if adv.id == fronts[0]["adventurer_id"])
        if front_adv.defense < 70:
            notes.append("Consider moving a sturdier unit into the frontline.")
    for member in members:
        if member["slot"] != "front" and member["class_name"] in ("Fighter", "Warden"):
            notes.append("A melee class in the backline loses speed and can become target-starved.")
            break
    if len(notes) < 2:
        notes.append("Switch-based builds improve a lot when one ranged unit can reload safely in the backline.")
    if len(notes) < 3:
        notes.append("Artifact attunement is often the easiest way to patch a weak statline.")
    return notes[:3]


def draft_offer(size: int, seed: int | None = None) -> list[str]:
    rng = random.Random(seed) if seed is not None else random
    return [adventurer.id for adventurer in rng.sample(ADVENTURERS, size)]


def _effect_summary(effect) -> str:
    chunks: list[str] = []
    if effect.power > 0:
        chunks.append(f"{effect.power} Power")
    if effect.heal > 0:
        chunks.append(f"Heal {effect.heal}")
    if effect.cooldown > 0:
        chunks.append(f"Cooldown {effect.cooldown}")
    if effect.ammo_cost > 0:
        chunks.append(f"Ammo {effect.ammo_cost}")
    if effect.spread:
        chunks.append("Spread")
    if effect.recoil:
        chunks.append(f"{int(effect.recoil * 100)}% Recoil")
    if effect.lifesteal:
        chunks.append(f"{int(effect.lifesteal * 100)}% Lifesteal")
    if effect.description:
        chunks.append(effect.description)
    return " | ".join(chunks) if chunks else effect.name


def _weapon_block(weapon) -> str:
    lines = [f"{weapon.name} ({weapon.kind.title()})", f"Strike: {_effect_summary(weapon.strike)}"]
    for passive in weapon.passive_skills:
        lines.append(f"Passive: {passive.name} — {passive.description}")
    for spell in weapon.spells:
        lines.append(f"Spell: {spell.name} — {_effect_summary(spell)}")
    return "\n".join(lines)


def _adventurer_catalog_body(adventurer) -> str:
    return "\n".join(
        [
            f"Stats: HP {adventurer.hp} | Attack {adventurer.attack} | Defense {adventurer.defense} | Speed {adventurer.speed}",
            f"Innate: {adventurer.innate.name} — {adventurer.innate.description}",
            _weapon_block(adventurer.signature_weapons[0]),
            _weapon_block(adventurer.signature_weapons[1]),
            f"Ultimate: {adventurer.ultimate.name} — {_effect_summary(adventurer.ultimate)}",
        ]
    )


def catalog_entries(section: str) -> list[dict]:
    if section == "Adventurers":
        return [
            {
                "title": adventurer.name,
                "subtitle": ", ".join(role_tags_for_adventurer(adventurer)),
                "body": _adventurer_catalog_body(adventurer),
            }
            for adventurer in ADVENTURERS
        ]
    if section == "Class Skills":
        return [
            {
                "title": skill.name,
                "subtitle": class_name,
                "body": skill.description,
            }
            for class_name, skills in CLASS_SKILLS.items()
            for skill in skills
        ]
    if section == "Artifacts":
        return [
            {
                "title": artifact.name,
                "subtitle": ", ".join(artifact.attunement),
                "body": "\n".join(
                    [
                        f"Attunement: {', '.join(artifact.attunement)}",
                        f"Stat Bonus: +{artifact.amount} {artifact.stat.title()}",
                        f"{'Reactive' if artifact.reactive else 'Spell'}: {artifact.spell.name} — {_effect_summary(artifact.spell)}",
                        artifact.description or "",
                    ]
                ).strip(),
            }
            for artifact in ARTIFACTS
        ]
    return []


def shop_tab_note(tab_name: str) -> str:
    if tab_name == "Artifacts":
        return "Artifacts are the only battle wares sold in this build."
    return ""


def shop_items_for_tab(tab_name: str) -> list[dict]:
    if tab_name == "Artifacts":
        return [
            {
                "name": artifact.name,
                "id": artifact.id,
                "artifact_id": artifact.id,
                "tag": "Relic",
                "price": ARTIFACT_SHOP_PRICES[artifact.id],
                "subtitle": ", ".join(artifact.attunement),
            }
            for artifact in ARTIFACTS
        ]
    return []
