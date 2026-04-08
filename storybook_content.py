from __future__ import annotations

import random
from dataclasses import dataclass

from quests_ai_tags import ADVENTURER_AI
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
        "id": "random",
        "name": "Random Bout",
        "subtitle": "Pick from a random shared pool of nine adventurers.",
        "note": "Both players draft from the same pool. Adapt your picks to what your opponent leaves.",
    },
    {
        "id": "focused",
        "name": "Focused Bout",
        "subtitle": "Select from your full roster, then build your loadout.",
        "note": "Bring the team you know. No pool restrictions — full roster selection before battle.",
    },
]


CATALOG_SECTIONS = [
    "Adventurers",
    "Class Skills",
    "Artifacts",
]


SHOP_TABS = ["Artifacts"]
COSMETIC_CATEGORIES = ["Hats", "Shirts", "Pants", "Socks", "Shoes"]
CLOSET_TABS = [
    "Player Skins",
    "Player Chairs",
    "Emotes",
    "Poses",
    "Adventurer Skins",
    "Assistant Skins",
    "Bartender Skins",
    "Server Skins",
    "Guild Hall Skins",
]
MARKET_TABS = [
    "Player Skins",
    "Player Chairs",
    "Emotes",
    "Poses",
    "Assistant Skins",
    "Bartender Skins",
    "Server Skins",
    "Adventurer Skins",
    "Guild Hall Skins",
]

MARKET_ITEMS = []

# ---------------------------------------------------------------------------
# Employee skill definitions
# ---------------------------------------------------------------------------

ASSISTANT_SKILLS = [
    {
        "id": "shrewd",
        "name": "Shrewd",
        "description": "+25% Gold from unspent Quest Gold collection; +50% if the Quest was successful.",
    },
    {
        "id": "resourceful",
        "name": "Resourceful",
        "description": "+50% Gold from Artifact sales at end of Quest and from duplicate cosmetic Gold.",
    },
    {
        "id": "erudite",
        "name": "Erudite",
        "description": "All Quest Gold converts to Exp at a 1:1 ratio. Player receives 0 Gold from the Quest.",
    },
    {
        "id": "appraiser",
        "name": "Appraiser",
        "description": "Artifacts sell for 150g (not 100g). Recruit costs 150g (not 100g).",
    },
    {
        "id": "ambitious",
        "name": "Ambitious",
        "description": "Level-up Gold doubled. Unspent Quest Gold reduced by 25%.",
    },
]

BARTENDER_SKILLS = [
    {
        "id": "safe_income",
        "name": "Safe Income",
        "description": "PvP Random Bout entry: 100g. Win payout: 200g.",
    },
    {
        "id": "high_roller",
        "name": "High Roller",
        "description": "PvP Random Bout entry: player chooses 300–600g. Win payout: 2× entry; 3× if 2-0.",
    },
    {
        "id": "generous_pour",
        "name": "Generous Pour",
        "description": "PvP Random Bout entry: 200g. Win payout: 500g.",
    },
    {
        "id": "penny_pincher",
        "name": "Penny Pincher",
        "description": "PvP Random Bout entry: 0g. Win payout: 100g.",
    },
    {
        "id": "double_or_nothing",
        "name": "Double or Nothing",
        "description": "PvP Random Bout entry: 300g. Win payout: 0g on 2-1; 900g on 2-0.",
    },
]

SERVER_SKILLS = [
    {
        "id": "friendly",
        "name": "Friendly",
        "description": "Each day, randomly select a favorite adventurer. At end of Bout win or successful Quest, if that adventurer is in the party, grant 100 Gold.",
    },
]

ALL_EMPLOYEE_SKILLS = {
    skill["id"]: skill
    for skill in ASSISTANT_SKILLS + BARTENDER_SKILLS + SERVER_SKILLS
}


ROLE_PRIORITY = ("Tank", "Carry", "Support", "Control", "Skirmish")

AI_ROLE_TO_DISPLAY = {
    # Tank
    "primary_tank": "Tank",
    "anti_burst": "Tank",
    "stall_anchor": "Tank",
    "frontline_breaker": "Tank",
    "frontline_ready": "Tank",
    "bruiser": "Tank",
    "taunt": "Tank",
    "frontline_growth": "Tank",
    # Carry
    "burst_finisher": "Carry",
    "magic_carry": "Carry",
    "scaling_carry": "Carry",
    "burst_spellcaster": "Carry",
    "ranged_pressure": "Carry",
    "spread_pressure": "Carry",
    "chip_damage": "Carry",
    "snowball": "Carry",
    "status_payoff": "Carry",
    "shock_payoff": "Carry",
    "burn_payoff": "Carry",
    "root_payoff": "Carry",
    "melee_reach": "Carry",
    "self_ramp": "Carry",
    "self_sustain": "Carry",
    # Support
    "healer": "Support",
    "guard_support": "Support",
    "carry_support": "Support",
    "tempo_support": "Support",
    "death_insurance": "Support",
    "synergy_amplifier": "Support",
    "stat_manipulator": "Support",
    # Control
    "control_anchor": "Control",
    "shock_engine": "Control",
    "root_enabler": "Control",
    "burn_enabler": "Control",
    "expose_enabler": "Control",
    "anti_caster": "Control",
    "anti_guard": "Control",
    "anti_heal": "Control",
    "anti_swap": "Control",
    "duel_control": "Control",
    "spell_theft": "Control",
    "spell_loop": "Control",
    "spotlight_enabler": "Control",
    "weaken_support": "Control",
    "setup_dependent": "Control",
    "volatile_utility": "Control",
    "adaptive_damage": "Control",
    # Skirmish
    "swap_engine": "Skirmish",
    "frontline_pivot": "Skirmish",
    "backline_reach": "Skirmish",
    "weapon_switch_user": "Skirmish",
    "bonus_action_user": "Skirmish",
    "high_variance": "Skirmish",
}


def _role_tags_from_ai_profile(adventurer_id: str) -> list[str]:
    profile = ADVENTURER_AI.get(adventurer_id)
    if profile is None:
        return []
    found = []
    for ai_role in profile.role_tags:
        display_role = AI_ROLE_TO_DISPLAY.get(ai_role, "Skirmish")
        if display_role not in found:
            found.append(display_role)
    ordered = [role for role in ROLE_PRIORITY if role in found]
    return ordered


def role_tags_for_adventurer(adventurer) -> list[str]:
    ai_tags = _role_tags_from_ai_profile(adventurer.id)
    if ai_tags:
        return ai_tags[:3]

    tags: list[str] = []
    if adventurer.hp >= 230 or adventurer.defense >= 88:
        tags.append("Tank")
    if adventurer.attack >= 70:
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
        lines.append(f"Passive: {passive.name} â€” {passive.description}")
    for spell in weapon.spells:
        lines.append(f"Spell: {spell.name} â€” {_effect_summary(spell)}")
    return "\n".join(lines)


def _adventurer_catalog_body(adventurer) -> str:
    return "\n".join(
        [
            f"Stats: HP {adventurer.hp} | Attack {adventurer.attack} | Defense {adventurer.defense} | Speed {adventurer.speed}",
            f"Weapons: {_weapon_kind_summary(adventurer)}",
            f"Innate: {adventurer.innate.name} - {adventurer.innate.description}",
            _weapon_block(adventurer.signature_weapons[0]),
            _weapon_block(adventurer.signature_weapons[1]),
            f"Ultimate: {adventurer.ultimate.name} - {_effect_summary(adventurer.ultimate)}",
        ]
    )


def _catalog_section_key(section: str) -> str:
    return "Items" if section == "Artifacts" else section


def _weapon_kind_summary(adventurer) -> str:
    labels = []
    for kind in ("melee", "ranged", "magic"):
        if any(weapon.kind == kind for weapon in adventurer.signature_weapons):
            labels.append(kind.title())
    return " / ".join(labels) if labels else "Unarmed"


def catalog_filter_definitions(section: str) -> list[dict]:
    section = _catalog_section_key(section)
    if section == "Adventurers":
        return [
            {
                "key": "weapon_kind",
                "label": "Weapon Type",
                "options": [("all", "All")] + [(kind, kind.title()) for kind in ("melee", "ranged", "magic")],
            },
            {
                "key": "favorite",
                "label": "Favorite",
                "options": [("all", "All"), ("favorite", "Favorite Only")],
            },
        ]
    if section == "Class Skills":
        return [
            {
                "key": "class_name",
                "label": "Class",
                "options": [("all", "All")] + [(class_name, class_name) for class_name in CLASS_SKILLS.keys()],
            }
        ]
    if section == "Items":
        cooldown_values = sorted({artifact.spell.cooldown for artifact in ARTIFACTS})
        stat_names = sorted(
            {artifact.stat for artifact in ARTIFACTS},
            key=lambda name: ("attack", "defense", "speed").index(name) if name in {"attack", "defense", "speed"} else 99,
        )
        return [
            {
                "key": "attunement",
                "label": "Attunement",
                "options": [("all", "Any")] + [(class_name, class_name) for class_name in CLASS_SKILLS.keys()],
            },
            {
                "key": "stat",
                "label": "Stat Boost",
                "options": [("all", "Any")] + [(stat_name, stat_name.title()) for stat_name in stat_names],
            },
            {
                "key": "cooldown",
                "label": "Cooldown",
                "options": [("all", "Any")] + [(str(value), str(value)) for value in cooldown_values],
            },
            {
                "key": "reactive",
                "label": "Trigger",
                "options": [("all", "Any"), ("reactive", "Reactive"), ("active", "Non-Reactive")],
            },
        ]
    return []


def _catalog_filter_value(filters: dict | None, key: str, default: str = "all") -> str:
    if not isinstance(filters, dict):
        return default
    value = filters.get(key, default)
    return str(value) if value is not None else default


def catalog_entries(section: str, filters: dict | None = None, *, favorite_adventurer_id: str | None = None) -> list[dict]:
    section = _catalog_section_key(section)
    if section == "Adventurers":
        weapon_kind = _catalog_filter_value(filters, "weapon_kind")
        favorite_filter = _catalog_filter_value(filters, "favorite")
        entries = []
        for adventurer in ADVENTURERS:
            kinds = {weapon.kind for weapon in adventurer.signature_weapons}
            if weapon_kind != "all" and weapon_kind not in kinds:
                continue
            if favorite_filter == "favorite" and adventurer.id != favorite_adventurer_id:
                continue
            subtitle_parts = [", ".join(role_tags_for_adventurer(adventurer)), _weapon_kind_summary(adventurer)]
            if adventurer.id == favorite_adventurer_id:
                subtitle_parts.append("Favorite")
            entries.append(
                {
                    "title": adventurer.name,
                    "subtitle": " | ".join(part for part in subtitle_parts if part),
                    "body": _adventurer_catalog_body(adventurer),
                }
            )
        return entries
    if section == "Class Skills":
        class_filter = _catalog_filter_value(filters, "class_name")
        return [
            {
                "title": skill.name,
                "subtitle": class_name,
                "body": "\n".join([f"Class: {class_name}", skill.description]).strip(),
            }
            for class_name, skills in CLASS_SKILLS.items()
            if class_filter == "all" or class_name == class_filter
            for skill in skills
        ]
    if section == "Items":
        attunement_filter = _catalog_filter_value(filters, "attunement")
        stat_filter = _catalog_filter_value(filters, "stat")
        cooldown_filter = _catalog_filter_value(filters, "cooldown")
        reactive_filter = _catalog_filter_value(filters, "reactive")
        entries = []
        for artifact in ARTIFACTS:
            if attunement_filter != "all" and attunement_filter not in artifact.attunement:
                continue
            if stat_filter != "all" and artifact.stat != stat_filter:
                continue
            if cooldown_filter != "all" and str(artifact.spell.cooldown) != cooldown_filter:
                continue
            if reactive_filter == "reactive" and not artifact.reactive:
                continue
            if reactive_filter == "active" and artifact.reactive:
                continue
            entries.append(
                {
                    "title": artifact.name,
                    "subtitle": " | ".join(
                        [
                            ", ".join(artifact.attunement),
                            f"+{artifact.amount} {artifact.stat.title()}",
                            f"CD {artifact.spell.cooldown}",
                            "Reactive" if artifact.reactive else "Spell",
                        ]
                    ),
                    "body": "\n".join(
                        [
                            f"Attunement: {', '.join(artifact.attunement)}",
                            f"Stat Bonus: +{artifact.amount} {artifact.stat.title()}",
                            f"Cooldown: {artifact.spell.cooldown}",
                            f"{'Reactive' if artifact.reactive else 'Spell'}: {artifact.spell.name} - {_effect_summary(artifact.spell)}",
                            artifact.description or "",
                        ]
                    ).strip(),
                }
            )
        return entries
    return []


def shop_tab_note(tab_name: str) -> str:
    return ""


def shop_items_for_tab(tab_name: str) -> list[dict]:
    return []


def market_items_for_tab(tab_name: str) -> list[dict]:
    if tab_name == "Featured":
        featured_ids = {
            "outfit_gilded_regent",
            "chair_sunwood_throne",
            "skin_jack_cloudbreaker",
            "emote_royal_bow",
        }
        return [item for item in MARKET_ITEMS if item["id"] in featured_ids]
    return [item for item in MARKET_ITEMS if item.get("category") == tab_name]


def market_tab_note(tab_name: str) -> str:
    notes = {
        "Player Skins": "Player wardrobe pieces for your profile showcase. (400–2,500g)",
        "Player Chairs": "Seating flourishes for the player profile stage. (250–1,500g)",
        "Emotes": "Short expressive flourishes. (150–600g)",
        "Poses": "Short expressive poses. (150–600g)",
        "Adventurer Skins": "Alternative looks for individual adventurers. (800–3,000g)",
        "Assistant Skins": "Alternate looks for your Assistant. (300–1,200g)",
        "Bartender Skins": "Alternate looks for your Bartender. (300–1,200g)",
        "Server Skins": "Alternate looks for your Server. (300–1,200g)",
        "Guild Hall Skins": "Visual themes for your Guild Hall. (1,500–5,000g)",
    }
    return notes.get(tab_name, "")

