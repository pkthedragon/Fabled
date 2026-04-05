from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import random
import re
import traceback

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ai_battle import queue_both_teams_for_phase
from quests_ai_quest import choose_quest_party
from quests_ai_quest_loadout import choose_blind_quest_roster_from_offer
from quests_ai_tags import ADVENTURER_AI
from quests_ruleset_data import (
    ADVENTURERS,
    ADVENTURERS_BY_ID,
    ARTIFACTS,
    ARTIFACTS_BY_ID,
    CLASS_SKILLS,
    _parse_rulebook_adventurer_descriptions,
)
from quests_ruleset_logic import (
    _fated_duel_blocks,
    compute_damage,
    do_swap,
    do_switch,
    end_round,
    get_legal_targets,
    queue_strike,
    resolve_action,
    resolve_spell,
    resolve_strike,
    resolve_ultimate,
    start_round,
)
from quests_ruleset_models import BattleState, CombatantState, TeamState

EXPECTED_CLASS_SKILLS = {
    "Fighter": ("martial", "inevitable"),
    "Rogue": ("covert", "assassin"),
    "Warden": ("bulwark", "vigilant"),
    "Mage": ("arcane", "archmage"),
    "Ranger": ("deadeye", "armed"),
    "Cleric": ("healer", "medic"),
}


@dataclass
class AuditResult:
    section: str
    name: str
    passed: bool
    detail: str


def _artifact(artifact_id: str | None):
    return ARTIFACTS_BY_ID.get(artifact_id) if artifact_id else None


def make_unit(
    adventurer_id: str,
    slot: str,
    *,
    class_name: str = "Fighter",
    skill_id: str = "martial",
    primary: str | None = None,
    secondary: str | None = None,
    artifact_id: str | None = None,
) -> CombatantState:
    adventurer = ADVENTURERS_BY_ID[adventurer_id]
    weapons = {weapon.id: weapon for weapon in adventurer.signature_weapons}
    if primary is None:
        primary = adventurer.signature_weapons[0].id
    if secondary is None:
        secondary = next(weapon.id for weapon in adventurer.signature_weapons if weapon.id != primary)
    skill = next(skill for skill in CLASS_SKILLS[class_name] if skill.id == skill_id)
    return CombatantState(
        adventurer,
        slot,
        class_name,
        skill,
        weapons[primary],
        weapons[secondary],
        artifact=_artifact(artifact_id),
    )


def make_battle(team1_members: list[CombatantState], team2_members: list[CombatantState]) -> BattleState:
    return BattleState(
        TeamState("Audit Team 1", team1_members),
        TeamState("Audit Team 2", team2_members),
    )


def check(section: str, name: str, condition: bool, detail: str) -> AuditResult:
    return AuditResult(section, name, condition, detail)


def _rulebook_text() -> str:
    return Path("rulebook.txt").read_text(encoding="utf-8")


def _parse_rulebook_stats() -> dict[str, dict[str, int]]:
    text = _rulebook_text()
    match = re.search(r"APPENDIX A .*?ADVENTURERS\n(.*)APPENDIX B .*?CLASS SKILLS", text, re.S)
    if match is None:
        return {}
    appendix = match.group(1)
    blocks = [block.strip() for block in re.split(r"\n(?=[^\n]+\nHP: )", appendix) if block.strip()]
    parsed: dict[str, dict[str, int]] = {}
    for block in blocks:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if len(lines) < 5 or not lines[1].startswith("HP:"):
            continue
        stats: dict[str, int] = {}
        for line in lines[1:5]:
            key, value = line.split(":", 1)
            stats[key.strip()] = int(value.strip())
        parsed[lines[0]] = stats
    return parsed


def _parse_rulebook_artifact_names() -> list[str]:
    text = _rulebook_text()
    match = re.search(r"APPENDIX C .*?ARTIFACTS\n(.*)$", text, re.S)
    if match is None:
        return []
    appendix = match.group(1)
    lines = [line.rstrip() for line in appendix.splitlines()]
    names: list[str] = []
    for i, line in enumerate(lines[:-1]):
        if line.strip() and lines[i + 1].startswith("Attunement:"):
            names.append(line.strip())
    return names


def audit_content_sync() -> list[AuditResult]:
    results: list[AuditResult] = []
    rulebook_stats = _parse_rulebook_stats()
    live_stats = {adv.name: {"HP": adv.hp, "Attack": adv.attack, "Defense": adv.defense, "Speed": adv.speed} for adv in ADVENTURERS}
    results.append(check("Content", "Adventurer Count", len(ADVENTURERS) == 30, f"live={len(ADVENTURERS)} expected=30"))
    results.append(check("Content", "Artifact Count", len(ARTIFACTS) == 38, f"live={len(ARTIFACTS)} expected=38"))
    live_skills = {key: tuple(skill.id for skill in value) for key, value in CLASS_SKILLS.items()}
    results.append(check("Content", "Class Skill Table", live_skills == EXPECTED_CLASS_SKILLS, str(live_skills)))
    rulebook_artifact_names = _parse_rulebook_artifact_names()
    live_artifact_names = [artifact.name for artifact in ARTIFACTS]
    results.append(
        check(
            "Content",
            "Artifact Names Match Rulebook",
            sorted(rulebook_artifact_names) == sorted(live_artifact_names),
            f"rulebook={len(rulebook_artifact_names)} live={len(live_artifact_names)}",
        )
    )
    stat_mismatches = [name for name, stats in rulebook_stats.items() if live_stats.get(name) != stats]
    results.append(check("Content", "Adventurer Stats Match Rulebook", not stat_mismatches, f"mismatches={stat_mismatches}"))

    parsed_descriptions = _parse_rulebook_adventurer_descriptions()
    description_mismatches: list[str] = []
    for adventurer in ADVENTURERS:
        record = parsed_descriptions.get(adventurer.name)
        if record is None:
            description_mismatches.append(f"{adventurer.name}: missing parsed description")
            continue
        if record["innate_desc"] and record["innate_desc"] != adventurer.innate.description:
            description_mismatches.append(f"{adventurer.name}: innate")
        if record["ultimate_name"] and record["ultimate_name"] != adventurer.ultimate.name:
            description_mismatches.append(f"{adventurer.name}: ultimate name")
        if record["ultimate_desc"] and record["ultimate_desc"] != adventurer.ultimate.description:
            description_mismatches.append(f"{adventurer.name}: ultimate desc")
    results.append(check("Content", "Adventurer Description Sync", not description_mismatches, f"mismatches={description_mismatches[:8]}"))
    return results


def audit_mechanics() -> list[AuditResult]:
    results: list[AuditResult] = []

    battle = make_battle(
        [
            make_unit("robin_hooded_avenger", SLOT_BACK_LEFT, class_name="Ranger", skill_id="deadeye", primary="the_flock"),
            make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield"),
            make_unit("matchbox_liesl", SLOT_BACK_RIGHT, class_name="Cleric", skill_id="healer", primary="matchsticks"),
        ],
        [
            make_unit("porcus_iii", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="crafty_wall"),
            make_unit("hunold_the_piper", SLOT_BACK_LEFT, class_name="Mage", skill_id="arcane", primary="golden_fiddle"),
            make_unit("reynard_lupine_trickster", SLOT_BACK_RIGHT, class_name="Rogue", skill_id="assassin", primary="foxfire_bow"),
        ],
    )
    robin = battle.team1.get_slot(SLOT_BACK_LEFT)
    ranged_targets = {unit.slot for unit in get_legal_targets(battle, robin, effect=robin.primary_weapon.strike, weapon=robin.primary_weapon)}
    results.append(check("Mechanics", "Ranged Lane Targeting", ranged_targets == {SLOT_FRONT, SLOT_BACK_LEFT}, f"targets={sorted(ranged_targets)}"))

    asha_battle = make_battle(
        [
            make_unit("sea_wench_asha", SLOT_BACK_RIGHT, class_name="Mage", skill_id="arcane", primary="frost_scepter"),
            make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield"),
            make_unit("matchbox_liesl", SLOT_BACK_LEFT, class_name="Cleric", skill_id="healer", primary="matchsticks"),
        ],
        [
            make_unit("porcus_iii", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="crafty_wall"),
            make_unit("hunold_the_piper", SLOT_BACK_LEFT, class_name="Mage", skill_id="arcane", primary="golden_fiddle"),
            make_unit("reynard_lupine_trickster", SLOT_BACK_RIGHT, class_name="Rogue", skill_id="assassin", primary="foxfire_bow"),
        ],
    )
    asha = asha_battle.team1.get_slot(SLOT_BACK_RIGHT)
    magic_targets = {unit.slot for unit in get_legal_targets(asha_battle, asha, effect=asha.primary_weapon.strike, weapon=asha.primary_weapon)}
    results.append(check("Mechanics", "Magic Lane Targeting", magic_targets == {SLOT_FRONT, SLOT_BACK_RIGHT}, f"targets={sorted(magic_targets)}"))

    humbert_battle = make_battle(
        [make_unit("wayward_humbert", SLOT_FRONT, class_name="Ranger", skill_id="armed", primary="convicted_shotgun")],
        [make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield")],
    )
    humbert = humbert_battle.team1.frontline()
    humbert.cooldowns[humbert.primary_weapon.strike.id] = 3
    humbert.cooldowns["liquid_courage"] = 2
    humbert.ammo_remaining["convicted_shotgun"] = 0
    humbert.ammo_remaining["pallid_musket"] = 1
    do_switch(humbert, humbert_battle)
    results.append(check("Mechanics", "Switch Resets Cooldowns And Ammo", humbert.cooldowns[humbert.primary_weapon.strike.id] == 0 and humbert.ammo_remaining[humbert.primary_weapon.id] == humbert.primary_weapon.ammo, f"cooldown={humbert.cooldowns[humbert.primary_weapon.strike.id]} ammo={humbert.ammo_remaining[humbert.primary_weapon.id]}"))

    unit = make_unit("briar_rose", SLOT_FRONT, class_name="Ranger", skill_id="deadeye", primary="thorn_snare")
    unit.add_status("root", 1)
    unit.add_status("root", 2)
    root_duration = next(status.duration for status in unit.statuses if status.kind == "root")
    unit.add_status("root_immunity", 2)
    results.append(check("Mechanics", "Status Refresh", root_duration == 2, f"root_duration={root_duration}"))
    results.append(check("Mechanics", "Root Immunity Cleanses Root", not unit.has_status("root") and unit.has_status("root_immunity"), "root removed on immunity gain"))

    meter_battle = make_battle(
        [make_unit("little_jack", SLOT_FRONT, class_name="Fighter", skill_id="inevitable", primary="skyfall")],
        [make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield")],
    )
    jack = meter_battle.team1.frontline()
    resolve_strike(jack, meter_battle.team2.frontline(), meter_battle)
    strike_meter = meter_battle.team1.ultimate_meter

    meter_battle_2 = make_battle(
        [make_unit("hunold_the_piper", SLOT_FRONT, class_name="Mage", skill_id="arcane", primary="golden_fiddle")],
        [make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield")],
    )
    hunold = meter_battle_2.team1.frontline()
    resolve_strike(hunold, meter_battle_2.team2.frontline(), meter_battle_2)
    magic_meter = meter_battle_2.team1.ultimate_meter

    sanctuary_battle = make_battle(
        [make_unit("rapunzel_the_golden", SLOT_FRONT, class_name="Cleric", skill_id="healer", primary="ivory_tower")],
        [make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield")],
    )
    rap = sanctuary_battle.team1.frontline()
    sanctuary = next(effect for effect in rap.active_spells() if effect.id == "sanctuary")
    resolve_spell(rap, sanctuary, rap, sanctuary_battle)
    spell_meter = sanctuary_battle.team1.ultimate_meter
    results.append(check("Mechanics", "Melee Strike Meter", strike_meter == 2, f"meter={strike_meter}"))
    results.append(check("Mechanics", "Magic Strike Meter", magic_meter == 2, f"meter={magic_meter}"))
    results.append(check("Mechanics", "Spell Meter", spell_meter == 2, f"meter={spell_meter}"))

    reactive_battle = make_battle(
        [make_unit("tam_lin_thornbound", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="butterfly_knife", artifact_id="tarnhelm")],
        [make_unit("little_jack", SLOT_FRONT, class_name="Fighter", skill_id="martial", primary="skyfall")],
    )
    tam = reactive_battle.team1.frontline()
    tam.hp = 1
    resolve_strike(reactive_battle.team2.frontline(), tam, reactive_battle)
    results.append(check("Mechanics", "Reactive Spell Meter", reactive_battle.team1.ultimate_meter == 2 and tam.hp == 1, f"meter={reactive_battle.team1.ultimate_meter} hp={tam.hp}"))

    ult_battle = make_battle(
        [make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield")],
        [make_unit("porcus_iii", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="crafty_wall")],
    )
    ult_battle.team1.markers["ultimates_cast"] = 2
    ult_battle.team1.ultimate_meter = 7
    roland = ult_battle.team1.frontline()
    resolve_ultimate(roland, roland.defn.ultimate, roland, ult_battle)
    results.append(check("Mechanics", "Third Ultimate Wins", ult_battle.winner == 1, f"winner={ult_battle.winner}"))

    promo_battle = make_battle(
        [
            make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield"),
            make_unit("little_jack", SLOT_BACK_LEFT, class_name="Fighter", skill_id="martial", primary="skyfall"),
            make_unit("briar_rose", SLOT_BACK_RIGHT, class_name="Ranger", skill_id="deadeye", primary="thorn_snare"),
        ],
        [make_unit("little_jack", SLOT_FRONT, class_name="Fighter", skill_id="martial", primary="skyfall")],
    )
    promo_target = promo_battle.team1.frontline()
    promo_target.hp = 1
    resolve_strike(promo_battle.team2.frontline(), promo_target, promo_battle)
    results.append(check("Mechanics", "Frontline Promotion Uses Leftmost Backliner", promo_battle.team1.frontline().defn.id == "little_jack", f"front={promo_battle.team1.frontline().defn.id}"))

    slot_battle = make_battle(
        [
            make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_gold_lance"),
            make_unit("briar_rose", SLOT_BACK_LEFT, class_name="Ranger", skill_id="deadeye", primary="thorn_snare"),
        ],
        [
            make_unit("porcus_iii", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="crafty_wall"),
            make_unit("little_jack", SLOT_BACK_LEFT, class_name="Fighter", skill_id="martial", primary="skyfall"),
        ],
    )
    actor = slot_battle.team1.frontline()
    queue_strike(actor, slot_battle.team2.frontline())
    do_swap(slot_battle.team2.frontline(), slot_battle.team2.get_slot(SLOT_BACK_LEFT), slot_battle)
    resolve_action(actor, actor.queued_action, slot_battle)
    melee_slot_ok = slot_battle.team2.frontline().hp < slot_battle.team2.frontline().max_hp and next(member.hp for member in slot_battle.team2.members if member.defn.id == "porcus_iii") == ADVENTURERS_BY_ID["porcus_iii"].hp

    slot_battle_2 = make_battle(
        [
            make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_gold_lance"),
            make_unit("briar_rose", SLOT_BACK_LEFT, class_name="Ranger", skill_id="deadeye", primary="thorn_snare"),
        ],
        [make_unit("porcus_iii", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="crafty_wall")],
    )
    actor2 = slot_battle_2.team1.frontline()
    target2 = slot_battle_2.team2.frontline()
    queue_strike(actor2, target2)
    do_swap(actor2, slot_battle_2.team1.get_slot(SLOT_BACK_LEFT), slot_battle_2)
    before_hp = target2.hp
    resolve_action(actor2, actor2.queued_action, slot_battle_2)
    results.append(check("Mechanics", "Slot Targeting Resolves To Position", melee_slot_ok, f"enemy_front_hp={slot_battle.team2.frontline().hp}"))
    results.append(check("Mechanics", "Melee Becomes Illegal From Backline", target2.hp == before_hp, f"target_hp={before_hp}->{target2.hp}"))

    duel_battle = make_battle(
        [
            make_unit("the_green_knight", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="the_answer"),
            make_unit("little_jack", SLOT_BACK_LEFT, class_name="Fighter", skill_id="martial", primary="skyfall"),
            make_unit("briar_rose", SLOT_BACK_RIGHT, class_name="Ranger", skill_id="deadeye", primary="thorn_snare"),
        ],
        [
            make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield"),
            make_unit("hunold_the_piper", SLOT_BACK_LEFT, class_name="Mage", skill_id="arcane", primary="golden_fiddle"),
            make_unit("matchbox_liesl", SLOT_BACK_RIGHT, class_name="Cleric", skill_id="healer", primary="eternal_torch"),
        ],
    )
    duel_battle.team1.ultimate_meter = 7
    gk = duel_battle.team1.frontline()
    resolve_ultimate(gk, gk.defn.ultimate, duel_battle.team2.frontline(), duel_battle)
    results.append(check("Mechanics", "Fated Duel Lane Lock", not _fated_duel_blocks(duel_battle.team1.frontline(), duel_battle) and _fated_duel_blocks(duel_battle.team1.get_slot(SLOT_BACK_LEFT), duel_battle), str(duel_battle.markers)))

    ali = make_unit("ali_baba", SLOT_FRONT, class_name="Rogue", skill_id="assassin", primary="thiefs_dagger")
    roland = make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_gold_lance")
    ali.add_buff("attack", 40, 2)
    roland.add_buff("defense", 40, 2)
    boosted = compute_damage(ali, roland, ali.primary_weapon.strike, weapon=ali.primary_weapon)
    ali.buffs.clear(); roland.buffs.clear()
    plain = compute_damage(ali, roland, ali.primary_weapon.strike, weapon=ali.primary_weapon)
    results.append(check("Mechanics", "Ali Baba Ignores Combat Stat Mods", boosted == plain, f"boosted={boosted} plain={plain}"))

    daybreak_battle = make_battle(
        [make_unit("scheherazade_dawns_ransom", SLOT_FRONT, class_name="Cleric", skill_id="medic", primary="lamp_of_infinity")],
        [make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield")],
    )
    daybreak_battle.team1.ultimate_meter = 7
    daybreak_battle.team2.ultimate_meter = 6
    scheh = daybreak_battle.team1.frontline()
    resolve_ultimate(scheh, scheh.defn.ultimate, daybreak_battle.team2.frontline(), daybreak_battle)
    resolve_strike(daybreak_battle.team2.frontline(), daybreak_battle.team1.frontline(), daybreak_battle)
    results.append(check("Mechanics", "Daybreak Clears And Locks Meter", daybreak_battle.team2.ultimate_meter == 0, f"enemy_meter={daybreak_battle.team2.ultimate_meter}"))

    anansi_battle = make_battle(
        [make_unit("storyweaver_anansi", SLOT_FRONT, class_name="Ranger", skill_id="deadeye", primary="the_sword")],
        [make_unit("tam_lin_thornbound", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="butterfly_knife", artifact_id="selkies_skin")],
    )
    target = anansi_battle.team2.frontline()
    hp_before = target.hp
    resolve_strike(anansi_battle.team1.frontline(), target, anansi_battle)
    results.append(check("Mechanics", "Anansi Suppresses Reactive Spells", target.hp < hp_before and target.cooldowns.get("mistform", 0) == 0, f"hp={target.hp} cooldown={target.cooldowns.get('mistform', 0)}"))

    ody_battle = make_battle(
        [make_unit("odysseus_the_nobody", SLOT_BACK_LEFT, class_name="Fighter", skill_id="martial", primary="beggars_greatbow")],
        [make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield")],
    )
    ody_battle.team1.ultimate_meter = 7
    ody = ody_battle.team1.get_slot(SLOT_BACK_LEFT)
    resolve_ultimate(ody, ody.defn.ultimate, ody, ody_battle)
    results.append(check("Mechanics", "Trojan Horse Grants Bonus Switch", ody.markers.get("bonus_switch_rounds", 0) == 2, f"markers={ody.markers}"))

    witch_battle = make_battle(
        [
            make_unit("witch_of_the_east", SLOT_BACK_RIGHT, class_name="Mage", skill_id="arcane", primary="zephyr"),
            make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield"),
            make_unit("briar_rose", SLOT_BACK_LEFT, class_name="Ranger", skill_id="deadeye", primary="thorn_snare"),
        ],
        [
            make_unit("porcus_iii", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="crafty_wall"),
            make_unit("hunold_the_piper", SLOT_BACK_LEFT, class_name="Mage", skill_id="arcane", primary="golden_fiddle"),
            make_unit("reynard_lupine_trickster", SLOT_BACK_RIGHT, class_name="Rogue", skill_id="assassin", primary="foxfire_bow"),
        ],
    )
    start_round(witch_battle)
    witch = witch_battle.team1.get_slot(SLOT_BACK_RIGHT)
    speed_with_current = witch.get_stat("speed", witch_battle)
    resolve_strike(witch, witch_battle.team2.frontline(), witch_battle)
    results.append(check("Mechanics", "Headwinds Creates Air Current", speed_with_current == 59, f"speed={speed_with_current}"))
    results.append(check("Mechanics", "Zephyr Swaps Target Left", witch_battle.team2.frontline().defn.id == "hunold_the_piper", f"front={witch_battle.team2.frontline().defn.id}"))

    tam_battle = make_battle(
        [
            make_unit("tam_lin_thornbound", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="butterfly_knife"),
            make_unit("little_jack", SLOT_BACK_LEFT, class_name="Fighter", skill_id="martial", primary="skyfall"),
        ],
        [make_unit("briar_rose", SLOT_FRONT, class_name="Ranger", skill_id="deadeye", primary="thorn_snare")],
    )
    tam = tam_battle.team1.frontline()
    resolve_strike(tam_battle.team2.frontline(), tam, tam_battle)
    faeries_ok = not tam.has_status("root") and tam.best_buff("defense") >= 15
    tam_battle.team1.ultimate_meter = 7
    resolve_ultimate(tam, tam.defn.ultimate, tam_battle.team1.get_slot(SLOT_BACK_LEFT), tam_battle)
    polymorphed = tam_battle.team1.get_slot(SLOT_BACK_LEFT)
    before_slot = polymorphed.slot
    do_swap(polymorphed, tam, tam_battle)
    results.append(check("Mechanics", "Faerie's Ransom Rejects First Status", faeries_ok, f"statuses={[s.kind for s in tam.statuses]} defense_buff={tam.best_buff('defense')}"))
    results.append(check("Mechanics", "Polymorph Blocks Swap", polymorphed.slot == before_slot, f"slot={polymorphed.slot}"))

    stone_battle = make_battle(
        [make_unit("scheherazade_dawns_ransom", SLOT_FRONT, class_name="Cleric", skill_id="medic", primary="lamp_of_infinity", artifact_id="philosophers_stone")],
        [make_unit("briar_rose", SLOT_FRONT, class_name="Ranger", skill_id="deadeye", primary="thorn_snare")],
    )
    stone_user = stone_battle.team1.frontline()
    stone_user.hp = 100
    resolve_strike(stone_battle.team2.frontline(), stone_user, stone_battle)
    results.append(check("Mechanics", "Philosopher's Stone Cleanses And Heals", not stone_user.has_status("root") and stone_user.hp > 100, f"hp={stone_user.hp} statuses={[s.kind for s in stone_user.statuses]}"))

    yarn_battle = make_battle(
        [make_unit("storyweaver_anansi", SLOT_BACK_LEFT, class_name="Ranger", skill_id="deadeye", primary="the_pen", artifact_id="seeking_yarn")],
        [
            make_unit("porcus_iii", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="crafty_wall"),
            make_unit("hunold_the_piper", SLOT_BACK_LEFT, class_name="Mage", skill_id="arcane", primary="golden_fiddle"),
        ],
    )
    yarn = yarn_battle.team1.get_slot(SLOT_BACK_LEFT)
    resolve_spell(yarn, yarn.artifact.spell, yarn, yarn_battle)
    ammo_before = yarn.ammo_remaining["the_pen"]
    resolve_strike(yarn, yarn_battle.team2.get_slot(SLOT_BACK_LEFT), yarn_battle)
    results.append(check("Mechanics", "Seeking Yarn Prevents Same-Lane Ammo Use", yarn.ammo_remaining["the_pen"] == ammo_before, f"ammo={yarn.ammo_remaining['the_pen']} before={ammo_before}"))

    abode_battle = make_battle(
        [make_unit("scheherazade_dawns_ransom", SLOT_FRONT, class_name="Cleric", skill_id="medic", primary="lamp_of_infinity", artifact_id="walking_abode")],
        [make_unit("sir_roland", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="pure_silver_shield")],
    )
    abode_user = abode_battle.team1.frontline()
    resolve_spell(abode_user, abode_user.artifact.spell, abode_battle.team2.frontline(), abode_battle)
    target = abode_battle.team2.frontline()
    results.append(check("Mechanics", "Walking Abode Applies Root And Heal Cut", target.has_status("root") and target.has_status("heal_cut"), f"statuses={[s.kind for s in target.statuses]}"))

    neb_battle = make_battle(
        [make_unit("tam_lin_thornbound", SLOT_FRONT, class_name="Warden", skill_id="bulwark", primary="butterfly_knife", artifact_id="nebula_mail")],
        [make_unit("little_jack", SLOT_FRONT, class_name="Fighter", skill_id="martial", primary="skyfall")],
    )
    neb_user = neb_battle.team1.frontline()
    resolve_spell(neb_user, neb_user.artifact.spell, neb_user, neb_battle)
    meter_before = neb_battle.team1.ultimate_meter
    resolve_strike(neb_battle.team2.frontline(), neb_user, neb_battle)
    results.append(check("Mechanics", "Nebula Mail Charges Meter On Strike Damage", neb_battle.team1.ultimate_meter == meter_before + 1, f"meter={neb_battle.team1.ultimate_meter}"))

    return results


def audit_ai() -> list[AuditResult]:
    results: list[AuditResult] = []
    rng = random.Random(27)
    illegal_profile_skills: list[str] = []
    for adventurer_id, profile in ADVENTURER_AI.items():
        for class_name, skill_ids in profile.preferred_skills.items():
            legal_ids = {skill.id for skill in CLASS_SKILLS[class_name]}
            for skill_id in skill_ids:
                if skill_id not in legal_ids:
                    illegal_profile_skills.append(f"{adventurer_id}:{class_name}:{skill_id}")
    results.append(check("AI", "Preferred Skill Profiles Legal", not illegal_profile_skills, f"illegal={illegal_profile_skills[:10]}"))

    party_failures: list[str] = []
    battle_log_failures: list[str] = []
    for index in range(12):
        offer = [adv.id for adv in rng.sample(ADVENTURERS, 9)]
        package = choose_blind_quest_roster_from_offer(offer, roster_size=6)
        if len(package.members) != 6:
            party_failures.append(f"package_size={len(package.members)}")
            continue
        enemy_offer = [adv.id for adv in rng.sample(ADVENTURERS, 9)]
        enemy_package = choose_blind_quest_roster_from_offer(enemy_offer, roster_size=6)
        try:
            choice = choose_quest_party(list(package.offer_ids), enemy_party_ids=list(enemy_package.offer_ids), difficulty="ranked", rng=rng)
        except Exception as exc:
            party_failures.append(f"choose_quest_party:{type(exc).__name__}:{exc}")
            continue
        classes = [member.class_name for member in choice.loadout.members]
        artifacts = [member.artifact_id for member in choice.loadout.members if member.artifact_id]
        if len(choice.loadout.members) != 3 or len(set(classes)) != len(classes) or len(set(artifacts)) != len(artifacts):
            party_failures.append(f"illegal_choice:{index}:classes={classes}:artifacts={artifacts}")
    results.append(check("AI", "Quest Roster And Trio Selection Legal", not party_failures, f"failures={party_failures[:5]}"))

    from quests_ai_runtime import build_battle_from_loadouts
    from quests_ruleset_logic import resolve_action_phase, resolve_bonus_phase
    for index in range(6):
        offer1 = [adv.id for adv in rng.sample(ADVENTURERS, 9)]
        offer2 = [adv.id for adv in rng.sample(ADVENTURERS, 9)]
        package1 = choose_blind_quest_roster_from_offer(offer1, roster_size=6)
        package2 = choose_blind_quest_roster_from_offer(offer2, roster_size=6)
        choice1 = choose_quest_party(list(package1.offer_ids), enemy_party_ids=list(package2.offer_ids), difficulty="ranked", rng=rng)
        choice2 = choose_quest_party(list(package2.offer_ids), enemy_party_ids=list(package1.offer_ids), difficulty="ranked", rng=rng)
        battle = build_battle_from_loadouts(choice1.loadout, choice2.loadout, player_name_1="Audit A", player_name_2="Audit B")
        for _ in range(4):
            if battle.winner is not None:
                break
            start_round(battle)
            queue_both_teams_for_phase(battle, bonus=False, difficulty1="ranked", difficulty2="ranked", rng=rng)
            resolve_action_phase(battle)
            if battle.winner is None:
                queue_both_teams_for_phase(battle, bonus=True, difficulty1="ranked", difficulty2="ranked", rng=rng)
                resolve_bonus_phase(battle)
            if battle.winner is None:
                end_round(battle)
        if any("not implemented yet" in line for line in battle.log):
            battle_log_failures.append(f"battle_{index}")
    results.append(check("AI", "Sample Battles Have No Missing Special Hooks", not battle_log_failures, f"failures={battle_log_failures}"))
    return results


def write_report(results: list[AuditResult], path: Path) -> None:
    grouped: dict[str, list[AuditResult]] = {}
    for result in results:
        grouped.setdefault(result.section, []).append(result)
    passed = sum(1 for result in results if result.passed)
    failed = sum(1 for result in results if not result.passed)
    lines = [
        "Fabled Rulebook Audit",
        f"Generated: {datetime.now().isoformat(sep=' ', timespec='seconds')}",
        f"Checks passed: {passed}",
        f"Checks failed: {failed}",
        "",
    ]
    for section in ("Content", "Mechanics", "AI"):
        section_results = grouped.get(section, [])
        if not section_results:
            continue
        lines.append(section)
        lines.append("-" * len(section))
        for result in section_results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"[{status}] {result.name}")
            lines.append(f"  {result.detail}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path.cwd() / f"rulebook_audit_{timestamp}.txt"
    results: list[AuditResult] = []
    try:
        results.extend(audit_content_sync())
        results.extend(audit_mechanics())
        results.extend(audit_ai())
    except Exception:
        results.append(AuditResult(section="Audit", name="Unhandled Exception", passed=False, detail=traceback.format_exc()))
    write_report(results, report_path)
    print(report_path)
    failed = [result for result in results if not result.passed]
    for result in failed:
        print(f"FAIL | {result.section} | {result.name} | {result.detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
