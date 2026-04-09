from __future__ import annotations

from collections import defaultdict
import re

from quest_enemy_generated import QUEST_ENEMY_RAW_RECORDS
from quests_ruleset_data import (
    ADVENTURERS_BY_ID,
    ALL_ARTIFACTS_BY_ID,
    CLASS_SKILLS,
    CLASS_SKILLS_BY_ID,
    ENEMY_ONLY_CLASS_SKILLS,
    active,
    artifact,
    passive,
    weapon,
)
from quests_ruleset_models import AdventurerDef, ArtifactDef, PassiveEffect, StatSpec, StatusSpec, WeaponDef


ALL_CLASSES = tuple(CLASS_SKILLS.keys())
NO_CLASS_NAME = "None"
ENEMY_ONLY_CLASS_SKILLS_BY_ID = {
    skill.id: skill
    for skills in ENEMY_ONLY_CLASS_SKILLS.values()
    for skill in skills
}


def _slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower())
    return value.strip("_")


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(text or "").strip().lower())


def _status_spec(kind: str, duration: int) -> StatusSpec:
    return StatusSpec(kind=kind, duration=duration)


def _stat_spec(stat: str, amount: int, duration: int) -> StatSpec:
    return StatSpec(stat=stat, amount=amount, duration=duration)


def _default_no_class_skill() -> PassiveEffect:
    return passive("no_class_skill_generated", "No Class", "This combatant has no class skill.")


QUEST_ENEMY_NO_ULTIMATE = active(
    "quest_enemy_no_ultimate",
    "No Ultimate",
    target="none",
    description="Quest enemies do not normally have Ultimate Spells.",
)


LEGENDARY_CLASS_SKILL_FALLBACKS = {
    "Cleric": "oracle",
    "Fighter": "warlord",
    "Mage": "spellweaver",
    "Ranger": "sharpshooter",
    "Rogue": "phantom",
    "Warden": "colossus",
}


STATUS_ALIASES = {
    "burn": "burn",
    "shock": "shock",
    "weaken": "weaken",
    "expose": "expose",
    "root": "root",
    "guard": "guard",
    "spotlight": "spotlight",
    "taunt": "taunt",
    "heal_cut": "heal_cut",
}


STAT_ALIASES = {
    "atk": "attack",
    "attack": "attack",
    "def": "defense",
    "defense": "defense",
    "spe": "speed",
    "spd": "speed",
    "speed": "speed",
    "hp": "hp",
}


GENERATED_EFFECT_SCRIPTS: dict[str, dict] = {}


def _strip_bonus_suffix(name: str) -> str:
    return re.sub(r"\s*\(\+\d+\s+[A-Z]+\)\s*$", "", str(name or "").strip())


def _artifact_bonus(raw_name: str) -> tuple[str, int]:
    match = re.search(r"\(\+(\d+)\s+([A-Z]+)\)\s*$", str(raw_name or "").strip())
    if match is None:
        return "attack", 0
    amount = int(match.group(1))
    stat_name = STAT_ALIASES.get(match.group(2).strip().lower(), "attack")
    return stat_name, amount


def _parse_ammo_cd(text: str) -> tuple[int, int]:
    raw = str(text or "").strip()
    ammo_match = re.search(r"(\d+)\s*Ammo", raw, flags=re.IGNORECASE)
    if ammo_match is not None:
        return int(ammo_match.group(1)), 0
    cooldown_match = re.search(r"CD\s*(\d+)", raw, flags=re.IGNORECASE)
    if cooldown_match is not None:
        return 0, int(cooldown_match.group(1))
    return 0, 0


def _parse_effect_header(text: str, *, default_kind: str = "spell") -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    match = re.match(r"^(.*?)\s*\((.*?)\)\s*:\s*(.+)$", raw, flags=re.IGNORECASE)
    if match is None:
        plain_name, separator, description = raw.partition(":")
        if not separator:
            return None
        return {
            "name": plain_name.strip(),
            "kind": default_kind,
            "cooldown": 0,
            "description": description.strip(),
        }
    kind = default_kind
    cooldown = 0
    for token in [part.strip() for part in match.group(2).split(",") if part.strip()]:
        lowered = token.lower()
        if lowered in {"spell", "skill"}:
            kind = lowered
            continue
        cd_match = re.match(r"cd\s*(\d+)", lowered)
        if cd_match is not None:
            cooldown = int(cd_match.group(1))
    return {
        "name": match.group(1).strip(),
        "kind": kind,
        "cooldown": cooldown,
        "description": match.group(3).strip(),
    }


def _extract_statuses(clause: str) -> list[str]:
    lower = clause.lower()
    found: list[str] = []
    for token, kind in STATUS_ALIASES.items():
        if token in lower and kind not in found:
            found.append(kind)
    return found


def _extract_stat_mods(clause: str) -> list[tuple[str, int]]:
    mods: list[tuple[str, int]] = []
    for amount_text, stat_name in re.findall(r"([+-]\d+)\s*(ATK|DEF|SPE|HP|Attack|Defense|Speed)", clause, flags=re.IGNORECASE):
        stat_id = STAT_ALIASES.get(stat_name.lower(), "")
        if stat_id:
            mods.append((stat_id, int(amount_text)))
    return mods


def _default_target_for_description(description: str) -> str:
    lower = description.lower()
    if "all allies" in lower or "target ally" in lower or "lowest hp ally" in lower:
        return "ally"
    if "self" in lower or "user" in lower:
        return "self"
    return "enemy"


def _empty_script() -> dict:
    return {
        "repeat_scope": None,
        "cleanse_target": None,
        "cleanse_self": None,
        "markers": [],
        "move": None,
        "next_strike_bonus_power": 0,
        "next_strike_statuses": [],
        "next_strike_ignore_targeting": False,
        "next_strike_spread": False,
        "next_strike_lifesteal": 0.0,
        "next_strike_free_ammo": False,
    }


def _script_has_work(script: dict) -> bool:
    return any(
        [
            script.get("repeat_scope"),
            script.get("cleanse_target"),
            script.get("cleanse_self"),
            script.get("markers"),
            script.get("move"),
            script.get("next_strike_bonus_power"),
            script.get("next_strike_statuses"),
            script.get("next_strike_ignore_targeting"),
            script.get("next_strike_spread"),
            script.get("next_strike_lifesteal"),
            script.get("next_strike_free_ammo"),
        ]
    )


def _append_statuses(target_list: list[StatusSpec], statuses: list[str], duration: int):
    for kind in statuses:
        if kind not in {status.kind for status in target_list}:
            target_list.append(_status_spec(kind, duration))


def _append_stat_mods(target_list: list[StatSpec], mods: list[tuple[str, int]], duration: int):
    existing = {(mod.stat, mod.amount, mod.duration) for mod in target_list}
    for stat_name, amount in mods:
        triple = (stat_name, amount, duration)
        if triple not in existing:
            target_list.append(_stat_spec(stat_name, amount, duration))


def _clause_scope(clause: str, default_target: str) -> str:
    lower = clause.lower()
    if "all allies" in lower:
        return "ally_all"
    if "all enemies" in lower or re.search(r"\ball\b", lower):
        return "enemy_all" if default_target == "enemy" else "ally_all"
    if "target ally" in lower or "lowest hp ally" in lower:
        return "ally"
    if "self" in lower or "user" in lower:
        return "self"
    return default_target


def _parse_effect_payload(
    *,
    effect_id: str,
    effect_name: str,
    description: str,
    default_target: str,
    default_power: int = 0,
    cooldown: int = 0,
    counts_as_spell: bool = False,
    strike_kind: str = "",
    ammo_cost: int = 0,
) -> dict:
    power = default_power
    heal = 0
    target_statuses: list[StatusSpec] = []
    self_statuses: list[StatusSpec] = []
    self_buffs: list[StatSpec] = []
    target_buffs: list[StatSpec] = []
    target_debuffs: list[StatSpec] = []
    special = ""
    target = default_target
    spread = "spread" in description.lower()
    lifesteal = 0.0
    bonus_power = 0
    bonus_power_if_status = ""
    script = _empty_script()
    lower_desc = description.lower()

    if re.search(r"(\d+)%\s+lifesteal", description, flags=re.IGNORECASE):
        lifesteal = int(re.search(r"(\d+)%\s+lifesteal", description, flags=re.IGNORECASE).group(1)) / 100.0
    if "next magic strike deals +25 damage" in lower_desc:
        special = "next_magic_strike_plus_25"
    elif "next strike ignores targeting" in lower_desc:
        special = "next_strike_ignore_targeting"
    elif "next strike exposes the target" in lower_desc:
        special = "next_strike_expose"
    elif "next strike has 30% lifesteal" in lower_desc:
        special = "next_strike_lifesteal_30"
    elif "next strike deals +25 damage and shocks the target" in lower_desc:
        special = "next_strike_bonus_25_shock"

    if re.search(r"\+(\d+)\s+Power if target is (\w+)", description, flags=re.IGNORECASE):
        power_match = re.search(r"\+(\d+)\s+Power if target is (\w+)", description, flags=re.IGNORECASE)
        bonus_power = int(power_match.group(1))
        status_word = power_match.group(2).strip().lower()
        bonus_power_if_status = STATUS_ALIASES.get(status_word, "")

    for raw_clause in re.split(r"[.;]\s*", description):
        clause = raw_clause.strip()
        if not clause:
            continue
        lower = clause.lower()
        scope = _clause_scope(clause, default_target)
        duration_match = re.search(r"(\d+)\s+round", lower)
        duration = int(duration_match.group(1)) if duration_match else 0

        if "swap all enemies" in lower:
            script["move"] = "swap_all_enemies"
            continue
        if "swap two enemies" in lower:
            script["move"] = "swap_two_enemies"
            continue
        if "swap to frontline" in lower:
            script["move"] = "self_to_frontline"
        elif "swap to backline" in lower:
            script["move"] = "self_to_backline"

        if "untargetable" in lower and duration > 0:
            script["markers"].append({"scope": "self", "marker": "untargetable_rounds", "duration": duration})
        if "immune to status conditions" in lower and duration > 0:
            script["markers"].append({"scope": "self", "marker": "status_immunity_rounds", "duration": duration})
        if ("cannot act" in lower or "cannot strike" in lower or "cannot cast spells" in lower) and duration > 0:
            target_scope = "self" if scope == "self" else "target"
            if "cannot act" in lower or "cannot cast spells" in lower:
                script["markers"].append({"scope": target_scope, "marker": "cant_act_rounds", "duration": duration})
            if "cannot strike" in lower:
                script["markers"].append({"scope": target_scope, "marker": "cant_strike_rounds", "duration": duration})

        if "cleanse" in lower:
            if scope == "self":
                script["cleanse_self"] = "all"
            else:
                script["cleanse_target"] = "all"

        if "all allies" in lower:
            script["repeat_scope"] = "ally_all"
            target = "none"
        elif "all enemies" in lower or re.search(r"\ball\b", lower):
            script["repeat_scope"] = "enemy_all" if default_target == "enemy" else "ally_all"
            target = "none"

        if "next strike" in lower or "next magic strike" in lower:
            power_match = re.search(r"\+(\d+)\s+damage", lower)
            if power_match is not None:
                script["next_strike_bonus_power"] = max(script["next_strike_bonus_power"], int(power_match.group(1)))
            if "ignore" in lower and "targeting" in lower:
                script["next_strike_ignore_targeting"] = True
            if "spread" in lower:
                script["next_strike_spread"] = True
            if "does not consume ammo" in lower:
                script["next_strike_free_ammo"] = True
            if "lifesteal" in lower:
                pct_match = re.search(r"(\d+)%\s+lifesteal", lower)
                if pct_match is not None:
                    script["next_strike_lifesteal"] = max(script["next_strike_lifesteal"], int(pct_match.group(1)) / 100.0)
            status_words = _extract_statuses(clause)
            if duration > 0:
                for kind in status_words:
                    if kind not in script["next_strike_statuses"]:
                        script["next_strike_statuses"].append((kind, duration))
            continue

        damage_match = re.search(r"deal\s+(\d+)\s+damage", lower)
        if damage_match is not None:
            power = max(power, int(damage_match.group(1)))
        heal_match = re.search(r"restore(?:s)?\s+(\d+)\s+hp", lower)
        if heal_match is not None:
            heal = max(heal, int(heal_match.group(1)))

        statuses = _extract_statuses(clause)
        if duration > 0 and statuses:
            if scope == "self":
                _append_statuses(self_statuses, statuses, duration)
            else:
                _append_statuses(target_statuses, statuses, duration)

        mods = _extract_stat_mods(clause)
        if duration > 0 and mods:
            if scope == "self":
                for stat_name, amount in mods:
                    if amount > 0:
                        _append_stat_mods(self_buffs, [(stat_name, amount)], duration)
            else:
                for stat_name, amount in mods:
                    if amount > 0:
                        _append_stat_mods(target_buffs, [(stat_name, amount)], duration)
                    elif amount < 0:
                        _append_stat_mods(target_debuffs, [(stat_name, abs(amount))], duration)

    if strike_kind == "magic" and cooldown <= 0:
        cooldown = 1
    if _script_has_work(script):
        GENERATED_EFFECT_SCRIPTS[effect_id] = script
        special = f"generated:{effect_id}" if not special else special
    return {
        "id": effect_id,
        "name": effect_name,
        "description": description,
        "target": target,
        "power": power,
        "heal": heal,
        "cooldown": cooldown,
        "ammo_cost": ammo_cost,
        "spread": spread,
        "counts_as_spell": counts_as_spell,
        "lifesteal": lifesteal,
        "bonus_power_if_status": bonus_power_if_status,
        "bonus_power": bonus_power,
        "target_statuses": tuple(target_statuses),
        "self_statuses": tuple(self_statuses),
        "self_buffs": tuple(self_buffs),
        "target_buffs": tuple(target_buffs),
        "target_debuffs": tuple(target_debuffs),
        "special": special,
    }


def _build_strike_effect(owner_id: str, raw_weapon: dict) -> WeaponDef:
    raise RuntimeError("internal helper should not be called directly")


def _weapon_kind(raw_kind: str) -> str:
    kind = str(raw_kind or "").strip().lower()
    if kind in {"melee", "ranged", "magic"}:
        return kind
    return "melee"


def _active_from_payload(payload: dict):
    effect_id = payload["id"]
    name = payload["name"]
    description = payload.get("description", "")
    kwargs = {key: value for key, value in payload.items() if key not in {"id", "name", "description"}}
    return active(effect_id, name, description=description, **kwargs)


def _resolve_class_skill(record: dict) -> tuple[str, PassiveEffect]:
    class_info = record.get("class_info")
    if not class_info:
        return NO_CLASS_NAME, _default_no_class_skill()
    class_name = class_info.get("class_name") or NO_CLASS_NAME
    raw_skill_text = str(class_info.get("skill_text") or "").strip()
    normalized = _normalize_key(raw_skill_text)
    for skill in CLASS_SKILLS.get(class_name, ()):
        if normalized in {_normalize_key(skill.name), _normalize_key(skill.id)}:
            return class_name, skill
    for skill in ENEMY_ONLY_CLASS_SKILLS.get(class_name, ()):
        if normalized in {_normalize_key(skill.name), _normalize_key(skill.id)}:
            return class_name, skill
    if "," in raw_skill_text or "legendary" in raw_skill_text.lower():
        fallback_id = LEGENDARY_CLASS_SKILL_FALLBACKS.get(class_name)
        if fallback_id and fallback_id in CLASS_SKILLS_BY_ID:
            return class_name, CLASS_SKILLS_BY_ID[fallback_id]
        if fallback_id and fallback_id in ENEMY_ONLY_CLASS_SKILLS_BY_ID:
            return class_name, ENEMY_ONLY_CLASS_SKILLS_BY_ID[fallback_id]
    return class_name, _default_no_class_skill()


def _build_weapon(owner_id: str, label: str, raw_weapon: dict | None) -> WeaponDef | None:
    if raw_weapon is None:
        return None
    kind = _weapon_kind(raw_weapon.get("type", ""))
    ammo, strike_cooldown = _parse_ammo_cd(raw_weapon.get("ammo_cd", ""))
    strike_text = str(raw_weapon.get("strike") or "").strip()
    strike_desc = strike_text
    strike_power_match = re.search(r"(\d+)\s+Power", strike_text, flags=re.IGNORECASE)
    strike_power = int(strike_power_match.group(1)) if strike_power_match else 0
    if "." in strike_desc:
        strike_desc = strike_desc.split(".", 1)[1].strip()
    strike_effect = _active_from_payload(
        _parse_effect_payload(
            effect_id=f"{owner_id}_{label}_{_slugify(raw_weapon['name'])}_strike",
            effect_name="Strike",
            description=strike_desc,
            default_target="enemy",
            default_power=strike_power,
            cooldown=strike_cooldown if kind == "magic" else 0,
            counts_as_spell=kind == "magic",
            strike_kind=kind,
            ammo_cost=1 if ammo > 0 else 0,
        )
    )
    extra = _parse_effect_header(raw_weapon.get("spell_or_skill", ""))
    passive_skills: list[PassiveEffect] = []
    spells = []
    if extra is not None:
        extra_id = f"{owner_id}_{label}_{_slugify(raw_weapon['name'])}_{_slugify(extra['name'])}"
        if extra["kind"] == "skill":
            passive_skills.append(passive(extra_id, extra["name"], extra["description"]))
        else:
            default_target = _default_target_for_description(extra["description"])
            spells.append(
                _active_from_payload(
                    _parse_effect_payload(
                        effect_id=extra_id,
                        effect_name=extra["name"],
                        description=extra["description"],
                        default_target=default_target,
                        cooldown=extra["cooldown"],
                    )
                )
            )
    return weapon(
        f"{owner_id}_{label}_{_slugify(raw_weapon['name'])}",
        raw_weapon["name"],
        kind,
        strike_effect,
        ammo=ammo,
        passive_skills=tuple(passive_skills),
        spells=tuple(spells),
    )


QUEST_ENEMY_ARTIFACTS: list[ArtifactDef] = []
QUEST_ENEMY_ARTIFACTS_BY_ID: dict[str, ArtifactDef] = {}
QUEST_ENEMY_DEFS: list[AdventurerDef] = []
QUEST_ENEMY_DEFS_BY_ID: dict[str, AdventurerDef] = {}
QUEST_ENEMY_META_BY_ID: dict[str, dict] = {}
QUEST_ENEMY_IDS_BY_LOCALE_TIER: dict[tuple[str, str], list[str]] = defaultdict(list)


for raw_record in QUEST_ENEMY_RAW_RECORDS:
    enemy_id = f"quest_enemy_{raw_record['id']}"
    class_name, class_skill = _resolve_class_skill(raw_record)
    innate_text = str(raw_record.get("innate_text") or "").strip()
    innate_name, innate_desc = (innate_text.split(":", 1) + [""])[:2] if ":" in innate_text else (innate_text or "No Innate", innate_text or "No innate skill.")
    primary_weapon = _build_weapon(enemy_id, "primary", raw_record.get("primary_weapon"))
    secondary_weapon = _build_weapon(enemy_id, "secondary", raw_record.get("secondary_weapon"))
    if primary_weapon is None:
        continue
    signature_weapons = (primary_weapon,) if secondary_weapon is None else (primary_weapon, secondary_weapon)

    artifact_def = None
    raw_artifact = raw_record.get("artifact")
    if raw_artifact:
        artifact_name = _strip_bonus_suffix(raw_artifact["name"])
        artifact_id_base = f"enemy_artifact_{_slugify(artifact_name)}"
        artifact_id = artifact_id_base
        while artifact_id in ALL_ARTIFACTS_BY_ID or artifact_id in QUEST_ENEMY_ARTIFACTS_BY_ID:
            artifact_id = f"{artifact_id_base}_{len(QUEST_ENEMY_ARTIFACTS_BY_ID) + 1}"
        stat_name, stat_amount = _artifact_bonus(raw_artifact["name"])
        active_header = _parse_effect_header(raw_artifact.get("spell", ""))
        reactive_header = _parse_effect_header(raw_artifact.get("reactive", ""))
        attunement = (class_name,) if class_name != NO_CLASS_NAME else ALL_CLASSES
        active_spell = (
            _active_from_payload(
                _parse_effect_payload(
                    effect_id=artifact_id + "_spell",
                    effect_name=active_header["name"],
                    description=active_header["description"],
                    default_target=_default_target_for_description(active_header["description"]),
                    cooldown=active_header["cooldown"],
                )
            )
            if active_header is not None
            else None
        )
        reactive_spell = None
        reactive = False
        if reactive_header is not None:
            reactive_effect = _active_from_payload(
                _parse_effect_payload(
                    effect_id=artifact_id + "_reactive",
                    effect_name=reactive_header["name"],
                    description=reactive_header["description"],
                    default_target=_default_target_for_description(reactive_header["description"]),
                    cooldown=reactive_header["cooldown"],
                )
            )
            if active_spell is None:
                active_spell = reactive_effect
                reactive = True
                reactive_spell = None
            else:
                reactive = True
                reactive_spell = reactive_effect
        artifact_def = artifact(
            artifact_id,
            artifact_name,
            attunement,
            stat_name,
            stat_amount,
            active_spell or active(artifact_id + "_passive", artifact_name, description="", target="none"),
            reactive=reactive,
            reactive_spell=reactive_spell,
            enemy_only=True,
            description="Generated from the quest enemy CSV.",
        )
        QUEST_ENEMY_ARTIFACTS.append(artifact_def)
        QUEST_ENEMY_ARTIFACTS_BY_ID[artifact_def.id] = artifact_def

    adventurer_def = AdventurerDef(
        id=enemy_id,
        name=raw_record["name"],
        hp=int(raw_record["hp"]),
        attack=int(raw_record["attack"]),
        defense=int(raw_record["defense"]),
        speed=int(raw_record["speed"]),
        innate=passive(f"{enemy_id}_innate", innate_name.strip() or "No Innate", innate_desc.strip() or "No innate skill."),
        signature_weapons=signature_weapons,
        ultimate=QUEST_ENEMY_NO_ULTIMATE,
    )
    QUEST_ENEMY_DEFS.append(adventurer_def)
    QUEST_ENEMY_DEFS_BY_ID[enemy_id] = adventurer_def
    QUEST_ENEMY_META_BY_ID[enemy_id] = {
        "enemy_id": enemy_id,
        "name": raw_record["name"],
        "locale_id": raw_record["locale_id"],
        "locale_name": raw_record["locale_name"],
        "tier_id": raw_record["tier_id"],
        "tier_name": raw_record["tier_name"],
        "humanoid": bool(raw_record.get("humanoid")),
        "class_name": class_name,
        "class_skill_id": None if class_name == NO_CLASS_NAME else class_skill.id,
        "primary_weapon_id": primary_weapon.id,
        "secondary_weapon_id": secondary_weapon.id if secondary_weapon is not None else None,
        "artifact_id": artifact_def.id if artifact_def is not None else None,
        "frontline_score": adventurer_def.hp + adventurer_def.defense * 2 + (120 if primary_weapon.kind == "melee" else 0),
        "backline_score": adventurer_def.speed * 2 + adventurer_def.attack + (120 if primary_weapon.kind in {"ranged", "magic"} else 0),
    }
    QUEST_ENEMY_IDS_BY_LOCALE_TIER[(raw_record["locale_id"], raw_record["tier_id"])].append(enemy_id)


ALL_COMBATANT_DEFS_BY_ID = {**ADVENTURERS_BY_ID, **QUEST_ENEMY_DEFS_BY_ID}
ALL_RUNTIME_ARTIFACTS_BY_ID = {**ALL_ARTIFACTS_BY_ID, **QUEST_ENEMY_ARTIFACTS_BY_ID}


def build_quest_enemy_setup_member(enemy_id: str, slot: str) -> dict:
    meta = QUEST_ENEMY_META_BY_ID[enemy_id]
    return {
        "adventurer_id": enemy_id,
        "slot": slot,
        "class_name": meta["class_name"],
        "class_skill_id": meta["class_skill_id"],
        "primary_weapon_id": meta["primary_weapon_id"],
        "artifact_id": meta["artifact_id"],
    }
