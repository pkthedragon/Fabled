from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from models import CampaignProfile
from quests_ruleset_data import CLASS_SKILLS
from quests_ruleset_models import CombatantState
from quests_sandbox import (
    set_member_artifact,
    set_member_class,
    set_member_skill,
    set_member_slot,
    set_member_weapon,
)
from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT
from storybook_mode import StorybookMode
from storybook_tutorial import (
    TUTORIAL_PLAYER_IDS,
    TUTORIAL_STARTING_GOLD,
    build_player_setup,
    build_tutorial_battle,
    encounter_spec,
    tutorial_loadout_note,
    tutorial_unit_callout_lines,
)


@dataclass(frozen=True)
class EncounterPlan:
    selected_ids: tuple[str, ...] | None = None
    slots: tuple[str, ...] | None = None
    classes: dict[str, str] | None = None
    skill_indexes: dict[str, int] | None = None
    weapons: dict[str, str] | None = None
    artifacts: dict[str, str | None] | None = None


@dataclass
class BattleRunResult:
    prompt_events: list[tuple[str, str]]
    battle_log: list[str]
    finished: bool
    terminal_state: str
    victory: bool | None
    rounds: int


ENCOUNTER_PLANS: dict[int, EncounterPlan] = {
    4: EncounterPlan(
        weapons={"matchbox_liesl": "eternal_torch"},
    ),
    5: EncounterPlan(
        weapons={"matchbox_liesl": "eternal_torch"},
    ),
    6: EncounterPlan(
        weapons={"little_jack": "giants_harp", "matchbox_liesl": "eternal_torch"},
    ),
    7: EncounterPlan(
        selected_ids=("porcus_iii", "little_jack", "matchbox_liesl"),
        slots=(SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT),
        classes={"porcus_iii": "Warden", "little_jack": "Fighter", "matchbox_liesl": "Mage"},
        skill_indexes={"porcus_iii": 1, "little_jack": 1, "matchbox_liesl": 0},
        weapons={"porcus_iii": "crafty_wall", "little_jack": "giants_harp", "matchbox_liesl": "eternal_torch"},
    ),
    8: EncounterPlan(
        selected_ids=("porcus_iii", "little_jack", "matchbox_liesl"),
        slots=(SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT),
        classes={"porcus_iii": "Warden", "little_jack": "Fighter", "matchbox_liesl": "Mage"},
        skill_indexes={"porcus_iii": 0, "little_jack": 1, "matchbox_liesl": 0},
        weapons={"porcus_iii": "crafty_wall", "little_jack": "giants_harp", "matchbox_liesl": "eternal_torch"},
    ),
    9: EncounterPlan(
        selected_ids=("porcus_iii", "little_jack", "matchbox_liesl"),
        slots=(SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT),
        classes={"porcus_iii": "Warden", "little_jack": "Fighter", "matchbox_liesl": "Mage"},
        skill_indexes={"porcus_iii": 0, "little_jack": 1, "matchbox_liesl": 0},
        weapons={"porcus_iii": "crafty_wall", "little_jack": "giants_harp", "matchbox_liesl": "eternal_torch"},
    ),
    10: EncounterPlan(
        selected_ids=("matchbox_liesl", "porcus_iii", "robin_hooded_avenger"),
        slots=(SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT),
        classes={"matchbox_liesl": "Mage", "porcus_iii": "Warden", "robin_hooded_avenger": "Cleric"},
        skill_indexes={"matchbox_liesl": 0, "porcus_iii": 0, "robin_hooded_avenger": 0},
        weapons={
            "matchbox_liesl": "matchsticks",
            "porcus_iii": "mortar_mortar",
            "robin_hooded_avenger": "the_flock",
        },
        artifacts={"matchbox_liesl": None, "porcus_iii": "holy_grail", "robin_hooded_avenger": None},
    ),
}


FIRST_RUN_PROMPT_LINES = [
    "Have you played Fabled before?",
    "If you are new, we will open a guided 10-encounter tutorial. If not, we will skip it and grant the same starting gold reward.",
]
TUTORIAL_GATE_LINES = [
    "Main menu tutorial gate button: Once Upon A Time...",
    "Tooltip label: Start The Tutorial",
]


def _ensure_pygame():
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()


def _skill_id(class_name: str, index: int) -> str:
    return CLASS_SKILLS[class_name][index].id


def _member_index(setup_state: dict, adventurer_id: str) -> int:
    return next(index for index, member in enumerate(setup_state["team1"]) if member["adventurer_id"] == adventurer_id)


def _priority_order(encounter_index: int) -> tuple[str, ...]:
    priorities = {
        2: ("tutorial_marigold", "tutorial_bar"),
        3: ("tutorial_daeny", "tutorial_rowan"),
        4: ("tutorial_tree_archer", "tutorial_tree_sentry"),
        5: ("tutorial_tree_healer", "tutorial_tree_scout"),
        6: ("tutorial_tree_archer", "tutorial_tree_witch", "tutorial_tree_warrior"),
        7: ("tutorial_tree_marksman", "tutorial_tree_druid", "tutorial_tree_sentinel"),
        8: ("tutorial_tree_sorcerer", "tutorial_wormwood_spirit", "tutorial_tree_knight"),
        9: ("tutorial_wormwood_fiend", "tutorial_wormwood_spirit", "tutorial_wormwood_beast"),
        10: ("tutorial_sapling_handmaiden", "tutorial_frau_trude", "tutorial_wormwood_monstrosity"),
    }
    return priorities.get(encounter_index, ())


def _find_unit(team, defn_id: str):
    return next((unit for unit in team.members if unit.defn.id == defn_id and not unit.ko), None)


def _lowest_hp(units: Iterable):
    units = list(units)
    return min(units, key=lambda unit: (unit.hp / max(1, unit.max_hp), unit.hp, unit.name)) if units else None


def _highest_attack(units: Iterable):
    units = list(units)
    return max(units, key=lambda unit: (unit.get_stat("attack"), -unit.hp, unit.name)) if units else None


def _choose_priority_target(controller, actor, targets: list):
    priority = _priority_order(controller.encounter_index)
    if not targets:
        return None
    target_lookup = {unit.defn.id: unit for unit in targets}
    for defn_id in priority:
        if defn_id in target_lookup:
            return target_lookup[defn_id]
    return _lowest_hp(targets)


def _choose_spell(controller, actor):
    spells = controller.available_bonus_spells(actor) if controller.phase.startswith("bonus") else controller.available_spells(actor)
    if not spells:
        return None, None

    team = controller.battle.get_team(controller.human_team_num)
    enemy = controller.battle.get_enemy(controller.human_team_num)
    encounter_index = controller.encounter_index

    ultimate = next((effect for effect in spells if effect.id == actor.defn.ultimate.id), None)
    if ultimate is not None and encounter_index >= 9:
        if ultimate.target == "enemy":
            targets = controller.legal_targets() if controller.phase.endswith("target") else []
            return ultimate, _choose_priority_target(controller, actor, targets)
        if ultimate.target == "ally":
            return ultimate, _lowest_hp(team.alive())
        return ultimate, actor if ultimate.target == "self" else None

    for effect in spells:
        if effect.id == "cloudburst":
            marigold = _find_unit(enemy, "tutorial_marigold")
            if marigold is not None:
                return effect, actor
            continue

    for effect in spells:
        if effect.id == "table_be_set":
            wounded = [unit for unit in team.alive() if unit.hp < int(unit.max_hp * 0.75) or unit.statuses]
            if wounded:
                return effect, _lowest_hp(wounded)

    for effect in spells:
        if effect.id == "mistform" and actor.hp < int(actor.max_hp * 0.55):
            return effect, actor

    for effect in spells:
        if effect.id == "not_by_the_hair" and actor.defn.id == "porcus_iii" and actor.slot == SLOT_FRONT:
            return effect, actor

    for effect in spells:
        if effect.id == "silver_tongue":
            legal = [unit for unit in controller.battle.get_enemy(controller.human_team_num).alive()]
            target = _highest_attack(legal)
            if target is not None:
                return effect, target

    for effect in spells:
        if effect.id == "spread_fortune":
            return effect, actor

    non_ultimate = next((effect for effect in spells if effect.id != actor.defn.ultimate.id), spells[0])
    if non_ultimate.target in {"none", "self"}:
        return None, None
    if non_ultimate.target == "enemy":
        legal = controller.legal_targets()
        target = _choose_priority_target(controller, actor, legal)
        return (non_ultimate, target) if target is not None else (None, None)
    if non_ultimate.target in {"ally", "any"} and non_ultimate.heal > 0:
        target = _lowest_hp(team.alive())
        return (non_ultimate, target) if target is not None else (None, None)
    return non_ultimate, actor if non_ultimate.target == "self" else None


def _perform_action(controller):
    actor = controller.active_actor
    if actor is None:
        return
    actions = controller.available_actions(actor)
    action_map = {choice.kind: choice for choice in actions}
    encounter_index = controller.encounter_index

    if encounter_index == 3 and actor.defn.id == "little_jack":
        daeny = _find_unit(controller.battle.get_enemy(controller.human_team_num), "tutorial_daeny")
        if daeny is None and actor.primary_weapon.id != "giants_harp" and "switch" in action_map:
            controller.select_action("switch")
            return

    if encounter_index == 5 and controller.battle.round_num == 1 and actor.defn.id == "little_jack" and "swap" in action_map:
        controller.select_action("swap")
        target = next((unit for unit in controller.legal_targets() if unit.defn.id == "matchbox_liesl"), None)
        if target is not None:
            controller.select_target(target)
            return
        controller.cancel_targeting()

    if "spellbook" in action_map:
        effect, spell_target = _choose_spell(controller, actor)
        if effect is not None:
            controller.select_action("spellbook")
            controller.select_spell(effect.id)
            if controller.phase in {"action_target", "bonus_target"}:
                legal_targets = controller.legal_targets()
                target = spell_target if spell_target in legal_targets else None
                if target is None:
                    if effect.target in {"ally", "any"} and effect.heal > 0:
                        target = _lowest_hp(legal_targets)
                    else:
                        target = _choose_priority_target(controller, actor, legal_targets)
                if target is not None:
                    controller.select_target(target)
                else:
                    controller.cancel_targeting()
            return

    if "strike" in action_map:
        controller.select_action("strike")
        target = _choose_priority_target(controller, actor, controller.legal_targets())
        if target is not None:
            controller.select_target(target)
            return
        controller.cancel_targeting()

    if "switch" in action_map:
        controller.select_action("switch")
        return

    if "swap" in action_map:
        controller.select_action("swap")
        target = _lowest_hp(controller.legal_targets())
        if target is not None:
            controller.select_target(target)
            return
        controller.cancel_targeting()

    controller.select_action("skip")


def _configure_setup(mode: StorybookMode, encounter_index: int):
    plan = ENCOUNTER_PLANS.get(encounter_index)
    if plan is None:
        return
    if plan.selected_ids is not None:
        mode.tutorial_selected_ids = list(plan.selected_ids)
        mode.tutorial_setup_state = build_player_setup(
            encounter_index,
            selected_ids=plan.selected_ids,
            artifact_pool=getattr(mode.profile, "tutorial_artifact_pool", []),
        )
        mode.tutorial_loadout_index = 0
    setup_state = mode.tutorial_setup_state
    if setup_state is None:
        return
    team = setup_state["team1"]
    if plan.slots is not None and plan.selected_ids is not None:
        for adventurer_id, slot in zip(plan.selected_ids, plan.slots):
            set_member_slot(setup_state, 1, _member_index(setup_state, adventurer_id), slot)
    if plan.classes:
        for adventurer_id, class_name in plan.classes.items():
            set_member_class(setup_state, 1, _member_index(setup_state, adventurer_id), class_name)
    if plan.skill_indexes:
        for adventurer_id, skill_index in plan.skill_indexes.items():
            member = team[_member_index(setup_state, adventurer_id)]
            class_name = member["class_name"]
            set_member_skill(setup_state, 1, _member_index(setup_state, adventurer_id), _skill_id(class_name, skill_index))
    if plan.weapons:
        for adventurer_id, weapon_id in plan.weapons.items():
            set_member_weapon(setup_state, 1, _member_index(setup_state, adventurer_id), weapon_id)
    if plan.artifacts:
        for adventurer_id, artifact_id in plan.artifacts.items():
            set_member_artifact(setup_state, 1, _member_index(setup_state, adventurer_id), artifact_id)


def _render(mode: StorybookMode):
    surface = pygame.Surface((1400, 900))
    mode.draw(surface, (0, 0))
    return surface


def _click_button(mode: StorybookMode, button_key: str, findings: list[str], context: str) -> bool:
    _render(mode)
    rect = (mode.last_buttons or {}).get(button_key)
    if rect is None:
        findings.append(f"{context}: expected `{button_key}` button on route `{mode.route}`.")
        return False
    mode.handle_click(rect.center)
    return True


def _append_block(lines: list[str], title: str, body: Iterable[str]):
    lines.append(title)
    body_lines = list(body)
    if not body_lines:
        lines.append("  (none)")
    else:
        for line in body_lines:
            lines.append(f"  - {line}")
    lines.append("")


def _format_effect(effect) -> list[str]:
    if effect is None:
        return []
    details = [f"{effect.name}: {effect.description or '(no description)'}"]
    if effect.cooldown:
        details.append(f"Cooldown: {effect.cooldown}")
    if effect.heal:
        details.append(f"Heal: {effect.heal}")
    if effect.power:
        details.append(f"Power: {effect.power}")
    return details


def _combatant_description_lines(unit: CombatantState) -> list[str]:
    lines = [
        f"{unit.name} [{unit.defn.id}]",
        f"Stats: HP {unit.max_hp} | ATK {unit.get_stat('attack')} | DEF {unit.get_stat('defense')} | SPD {unit.get_stat('speed')}",
    ]
    innate = getattr(unit.defn, "innate", None)
    if innate is not None:
        lines.append(f"Innate: {innate.name} — {innate.description or '(no description)'}")
    lines.append(f"Class: {unit.class_name}")
    if unit.class_skill is not None:
        lines.append(f"Class Skill: {unit.class_skill.name} — {unit.class_skill.description or '(no description)'}")
    lines.append(f"Primary Weapon: {unit.primary_weapon.name} [{unit.primary_weapon.kind}]")
    lines.extend(f"  {detail}" for detail in _format_effect(unit.primary_weapon.strike))
    for passive in unit.primary_weapon.passive_skills:
        lines.append(f"  Passive: {passive.name} — {passive.description or '(no description)'}")
    for spell in unit.primary_weapon.spells:
        lines.append(f"  Spell: {spell.name} — {spell.description or '(no description)'}")
    if unit.secondary_weapon.id != unit.primary_weapon.id:
        lines.append(f"Secondary Weapon: {unit.secondary_weapon.name} [{unit.secondary_weapon.kind}]")
        lines.extend(f"  {detail}" for detail in _format_effect(unit.secondary_weapon.strike))
        for passive in unit.secondary_weapon.passive_skills:
            lines.append(f"  Passive: {passive.name} — {passive.description or '(no description)'}")
        for spell in unit.secondary_weapon.spells:
            lines.append(f"  Spell: {spell.name} — {spell.description or '(no description)'}")
    if unit.artifact is not None:
        lines.append(
            f"Artifact: {unit.artifact.name} | +{unit.artifact.amount} {unit.artifact.stat.upper()} | Attunement: {', '.join(unit.artifact.attunement)}"
        )
        if unit.artifact.active_spell is not None:
            lines.append(f"  Active Spell: {unit.artifact.active_spell.name} — {unit.artifact.active_spell.description or '(no description)'}")
        if unit.artifact.reactive_effect is not None:
            lines.append(f"  Reactive Spell: {unit.artifact.reactive_effect.name} — {unit.artifact.reactive_effect.description or '(no description)'}")
    callouts = tutorial_unit_callout_lines(unit.defn.id)
    for callout in callouts:
        lines.append(f"Tutorial Callout: {callout}")
    return lines


def _audit_description_integrity(encounter_index: int, battle, findings: list[str], transcript: list[str], *, context: str):
    transcript.append(f"{context} enemy detail cards")
    enemy_count = 0
    for unit in battle.team2.members:
        enemy_count += 1
        unit_lines = _combatant_description_lines(unit)
        transcript.append(f"  {unit_lines[0]}")
        for line in unit_lines[1:]:
            transcript.append(f"    {line}")
        definition_weapon_count = len(unit.defn.signature_weapons)
        if definition_weapon_count == 1 and unit.secondary_weapon.id != unit.primary_weapon.id:
            findings.append(
                f"Encounter {encounter_index}: `{unit.name}` exposes a distinct secondary weapon in battle despite having only one signature weapon."
            )
        if unit.defn.innate.description == "":
            findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty innate description.")
        if unit.class_skill is not None and unit.class_skill.name != "None" and unit.class_skill.description == "":
            findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty class-skill description.")
        if unit.primary_weapon.strike.description == "":
            findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty primary strike description.")
        if definition_weapon_count > 1 and unit.secondary_weapon.strike.description == "":
            findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty secondary strike description.")
        for spell in unit.primary_weapon.spells:
            if spell.description == "":
                findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty primary spell description for `{spell.name}`.")
        for passive in unit.primary_weapon.passive_skills:
            if passive.description == "":
                findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty primary passive description for `{passive.name}`.")
        if definition_weapon_count > 1:
            for spell in unit.secondary_weapon.spells:
                if spell.description == "":
                    findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty secondary spell description for `{spell.name}`.")
            for passive in unit.secondary_weapon.passive_skills:
                if passive.description == "":
                    findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty secondary passive description for `{passive.name}`.")
        if unit.artifact is not None:
            if unit.artifact.active_spell is not None and unit.artifact.active_spell.description == "":
                findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty artifact active-spell description.")
            if unit.artifact.reactive_effect is not None and unit.artifact.reactive_effect.description == "":
                findings.append(f"Encounter {encounter_index}: `{unit.name}` has an empty artifact reactive-spell description.")
        if not tutorial_unit_callout_lines(unit.defn.id):
            findings.append(f"Encounter {encounter_index}: `{unit.name}` is missing tutorial callout text.")
    if enemy_count == 0:
        transcript.append("  (no enemies)")
    transcript.append("")


def _run_single_battle(mode: StorybookMode) -> BattleRunResult:
    controller = mode.battle_controller
    prompt_events: list[tuple[str, str]] = []
    prompt_seen: set[tuple[str, str]] = set()
    loop_guard = 0
    last_controller = controller
    while controller is not None and controller.phase != "result" and loop_guard < 1200:
        last_controller = controller
        loop_guard += 1
        prompt_text = getattr(controller, "tutorial_prompt", "").strip()
        prompt_id = getattr(controller, "tutorial_prompt_id", None) or (prompt_text if prompt_text else None)
        if prompt_id and prompt_text:
            key = (str(prompt_id), prompt_text)
            if key not in prompt_seen:
                prompt_seen.add(key)
                prompt_events.append(key)
            controller.dismiss_tutorial_prompt()
            controller = mode.battle_controller
            continue
        if controller.can_resolve():
            controller.resolve_current_phase()
            mode._check_battle_results()
            controller = mode.battle_controller
            continue
        if controller.phase in {"action_select", "bonus_select"}:
            _perform_action(controller)
            controller = mode.battle_controller
            continue
        if controller.phase in {"action_target", "bonus_target"}:
            legal = controller.legal_targets()
            target = _choose_priority_target(controller, controller.active_actor, legal)
            if target is not None:
                controller.select_target(target)
            else:
                controller.cancel_targeting()
            controller = mode.battle_controller
            continue
        return BattleRunResult(
            prompt_events=prompt_events,
            battle_log=list(last_controller.battle.log),
            finished=False,
            terminal_state=f"unhandled_phase:{controller.phase}",
            victory=None,
            rounds=max(0, last_controller.battle.round_num - 1),
        )
    final_controller = mode.battle_controller or last_controller
    if controller is None:
        return BattleRunResult(
            prompt_events=prompt_events,
            battle_log=list(final_controller.battle.log),
            finished=True,
            terminal_state="battle_controller_cleared",
            victory=None,
            rounds=max(0, final_controller.battle.round_num - 1),
        )
    if controller.phase != "result":
        return BattleRunResult(
            prompt_events=prompt_events,
            battle_log=list(controller.battle.log),
            finished=False,
            terminal_state=f"phase_stuck:{controller.phase}",
            victory=None,
            rounds=max(0, controller.battle.round_num - 1),
        )
    return BattleRunResult(
        prompt_events=prompt_events,
        battle_log=list(controller.battle.log),
        finished=True,
        terminal_state="result",
        victory=bool(mode.result_victory) if mode.route == "results" else None,
        rounds=max(0, controller.battle.round_num - 1),
    )


def _record_screen(lines: list[str], title: str, details: Iterable[str]):
    lines.append(f"[{title}]")
    for detail in details:
        lines.append(detail)
    lines.append("")


def _start_current_encounter(mode: StorybookMode, encounter_index: int, findings: list[str], transcript: list[str]) -> bool:
    if mode.route != "tutorial_briefing":
        findings.append(f"Encounter {encounter_index}: expected tutorial_briefing before start, got `{mode.route}`.")
        mode.route = "tutorial_briefing"
    _record_screen(
        transcript,
        f"Encounter {encounter_index} / Briefing",
        [f"Title: {encounter_spec(encounter_index).title}", *[f"Briefing: {line}" for line in mode._tutorial_briefing_lines()]],
    )
    if not _click_button(mode, "continue", findings, f"Encounter {encounter_index} briefing"):
        return False

    if mode.route == "tutorial_party_select":
        _configure_setup(mode, encounter_index)
        _record_screen(
            transcript,
            f"Encounter {encounter_index} / Party Select",
            [f"Party Select: {line}" for line in mode._tutorial_party_select_lines()]
            + [f"Selected Party: {', '.join(mode.tutorial_selected_ids)}"],
        )
        if len(mode.tutorial_selected_ids) != 3:
            findings.append(f"Encounter {encounter_index}: expected 3 selected tutorial members, got {len(mode.tutorial_selected_ids)}.")
        if not _click_button(mode, "continue", findings, f"Encounter {encounter_index} party select"):
            return False

    if mode.route == "tutorial_loadout":
        _configure_setup(mode, encounter_index)
        if mode.tutorial_setup_state is None:
            findings.append(f"Encounter {encounter_index}: tutorial setup state was missing at loadout.")
            return False
        loadout_battle = build_tutorial_battle(encounter_index, mode.tutorial_setup_state)
        loadout_lines = [f"Loadout Note: {tutorial_loadout_note(encounter_index)}"]
        loadout_lines.extend(f"Loadout: {line}" for line in mode._tutorial_loadout_lines())
        loadout_lines.append(
            "Player Formation: "
            + ", ".join(f"{member['slot']}={member['adventurer_id']}" for member in mode.tutorial_setup_state.get("team1", []))
        )
        _record_screen(transcript, f"Encounter {encounter_index} / Loadout", loadout_lines)
        _audit_description_integrity(
            encounter_index,
            loadout_battle,
            findings,
            transcript,
            context=f"Encounter {encounter_index} loadout",
        )
        if not _click_button(mode, "confirm", findings, f"Encounter {encounter_index} loadout"):
            return False

    if mode.route != "battle":
        findings.append(f"Encounter {encounter_index}: expected battle after setup, got `{mode.route}`.")
        return False
    if mode.battle_controller is None or mode.battle_controller.encounter_index != encounter_index:
        findings.append(f"Encounter {encounter_index}: battle controller encounter index mismatch on start.")
        return False
    return True


def _record_battle_result(transcript: list[str], encounter_index: int, label: str, battle_result: BattleRunResult, mode: StorybookMode):
    details = [
        f"Terminal State: {battle_result.terminal_state}",
        f"Rounds: {battle_result.rounds}",
        f"Victory: {mode.result_victory if mode.route == 'results' else 'n/a'}",
    ]
    for prompt_id, prompt_text in battle_result.prompt_events:
        details.append(f"Prompt [{prompt_id}]: {prompt_text}")
    if mode.route == "results":
        for line in mode.result_lines:
            details.append(f"Result: {line}")
    _record_screen(transcript, f"Encounter {encounter_index} / {label}", details)
    _append_block(transcript, f"Encounter {encounter_index} / {label} battle log", battle_result.battle_log)


def _win_current_encounter(mode: StorybookMode, encounter_index: int, findings: list[str], transcript: list[str], *, label: str) -> bool:
    attempts = 0
    while attempts < 6:
        attempts += 1
        if not _start_current_encounter(mode, encounter_index, findings, transcript):
            return False
        battle_result = _run_single_battle(mode)
        _record_battle_result(transcript, encounter_index, f"{label} Attempt {attempts}", battle_result, mode)
        if not battle_result.finished:
            findings.append(f"Encounter {encounter_index} {label.lower()}: battle did not finish cleanly (`{battle_result.terminal_state}`).")
            return False
        if mode.route == "tutorial_briefing":
            continue
        if mode.route != "results":
            findings.append(f"Encounter {encounter_index} {label.lower()}: expected results or tutorial_briefing, got `{mode.route}`.")
            return False
        if mode.result_victory:
            return True
        if not _click_button(mode, "continue", findings, f"Encounter {encounter_index} failed result continue"):
            return False
    findings.append(f"Encounter {encounter_index} {label.lower()}: failed to clear within {attempts} attempt(s).")
    return False


def _rematch_current_encounter(mode: StorybookMode, encounter_index: int, findings: list[str], transcript: list[str]) -> bool:
    pre_pool = list(getattr(mode.profile, "tutorial_artifact_pool", []))
    pre_completed = set(getattr(mode.profile, "tutorial_completed_encounters", set()))
    pre_gold = getattr(mode.profile, "gold", 0)
    pre_progress = mode._tutorial_progress_encounter_index()
    pre_complete = getattr(mode.profile, "tutorial_complete", False)
    _record_screen(
        transcript,
        f"Encounter {encounter_index} / Results Before Rematch",
        [
            f"Profile Progress Pointer: {pre_progress}",
            f"Tutorial Complete: {pre_complete}",
            f"Tutorial Pool: {pre_pool}",
            f"Gold: {pre_gold}",
            f"Completed Encounters: {sorted(pre_completed)}",
        ],
    )
    if not _click_button(mode, "rematch", findings, f"Encounter {encounter_index} rematch"):
        return False
    if mode.route != "battle":
        findings.append(f"Encounter {encounter_index}: rematch button did not reopen battle; got route `{mode.route}`.")
        return False
    if mode.battle_controller is None or mode.battle_controller.encounter_index != encounter_index:
        findings.append(f"Encounter {encounter_index}: rematch reopened the wrong tutorial encounter.")
        return False

    attempts = 0
    while attempts < 6:
        attempts += 1
        battle_result = _run_single_battle(mode)
        _record_battle_result(transcript, encounter_index, f"Rematch Attempt {attempts}", battle_result, mode)
        if not battle_result.finished:
            findings.append(f"Encounter {encounter_index} rematch: battle did not finish cleanly (`{battle_result.terminal_state}`).")
            return False
        if mode.route == "tutorial_briefing":
            if mode._tutorial_encounter_index() != encounter_index:
                findings.append(
                    f"Encounter {encounter_index}: replay loss restarted the wrong tutorial section (`{mode._tutorial_encounter_index()}`)."
                )
                return False
            if not _click_button(mode, "continue", findings, f"Encounter {encounter_index} replay restart continue"):
                return False
            if mode.route == "tutorial_party_select":
                _configure_setup(mode, encounter_index)
                if not _click_button(mode, "continue", findings, f"Encounter {encounter_index} replay party select continue"):
                    return False
            if mode.route == "tutorial_loadout":
                _configure_setup(mode, encounter_index)
                if not _click_button(mode, "confirm", findings, f"Encounter {encounter_index} replay loadout confirm"):
                    return False
            if mode.route != "battle":
                findings.append(f"Encounter {encounter_index}: replay retry did not return to battle; got `{mode.route}`.")
                return False
            continue
        if mode.route != "results":
            findings.append(f"Encounter {encounter_index}: rematch expected results, got `{mode.route}`.")
            return False
        if not mode.result_victory:
            if not _click_button(mode, "continue", findings, f"Encounter {encounter_index} replay failed result continue"):
                return False
            if mode.route == "main_menu":
                findings.append(f"Encounter {encounter_index}: replay loss returned to main menu unexpectedly.")
                return False
            if mode.route != "tutorial_briefing":
                findings.append(f"Encounter {encounter_index}: replay loss continue expected tutorial_briefing, got `{mode.route}`.")
                return False
            continue
        break

    if mode.route != "results" or not mode.result_victory:
        findings.append(f"Encounter {encounter_index}: rematch never reached a clean replay victory.")
        return False

    if list(getattr(mode.profile, "tutorial_artifact_pool", [])) != pre_pool:
        findings.append(f"Encounter {encounter_index}: replay changed the tutorial artifact pool.")
    if set(getattr(mode.profile, "tutorial_completed_encounters", set())) != pre_completed:
        findings.append(f"Encounter {encounter_index}: replay changed the completed encounter set.")
    if getattr(mode.profile, "gold", 0) != pre_gold:
        findings.append(f"Encounter {encounter_index}: replay changed tutorial gold from {pre_gold} to {mode.profile.gold}.")
    if mode._tutorial_progress_encounter_index() != pre_progress:
        findings.append(
            f"Encounter {encounter_index}: replay changed the tutorial progress pointer from {pre_progress} to {mode._tutorial_progress_encounter_index()}."
        )
    if getattr(mode.profile, "tutorial_complete", False) != pre_complete:
        findings.append(f"Encounter {encounter_index}: replay changed tutorial_complete unexpectedly.")

    if not _click_button(mode, "continue", findings, f"Encounter {encounter_index} replay result continue"):
        return False
    if encounter_index < 10:
        if mode.route != "tutorial_briefing":
            findings.append(f"Encounter {encounter_index}: expected tutorial_briefing after replay continue, got `{mode.route}`.")
            return False
        if mode._tutorial_progress_encounter_index() != min(10, encounter_index + 1):
            findings.append(
                f"Encounter {encounter_index}: progress pointer after replay continue is `{mode._tutorial_progress_encounter_index()}`, expected `{min(10, encounter_index + 1)}`."
            )
            return False
        if mode._tutorial_encounter_index() != mode._tutorial_progress_encounter_index():
            findings.append(f"Encounter {encounter_index}: tutorial replay override was not cleared after replay continue.")
            return False
    else:
        if mode.route != "main_menu":
            findings.append(f"Encounter 10: expected main_menu after replay continue, got `{mode.route}`.")
            return False
    return True


def _audit_skip_path(lines: list[str], findings: list[str]):
    profile = CampaignProfile()
    mode = StorybookMode(profile)
    mode._persist_profile = lambda: None
    if mode.route != "first_run_prompt":
        findings.append(f"Skip path: expected first_run_prompt, got `{mode.route}`.")
    _record_screen(lines, "Skip Path / First Run Prompt", FIRST_RUN_PROMPT_LINES + ["Buttons: Yes, Skip Tutorial | No, Teach Me"])
    if not _click_button(mode, "played_before", findings, "Skip path first-run prompt"):
        return
    _record_screen(
        lines,
        "Skip Path / Main Menu",
        [
            f"Route: {mode.route}",
            f"Tutorial complete: {mode.profile.tutorial_complete}",
            f"Gold: {mode.profile.gold}",
        ],
    )
    if not mode.profile.tutorial_complete:
        findings.append("Skip path: tutorial was not marked complete.")
    if mode.profile.gold < TUTORIAL_STARTING_GOLD:
        findings.append(f"Skip path: gold {mode.profile.gold} is below expected {TUTORIAL_STARTING_GOLD}.")


def _audit_new_player_path(lines: list[str], findings: list[str]):
    profile = CampaignProfile()
    mode = StorybookMode(profile)
    mode._persist_profile = lambda: None

    if mode.route != "first_run_prompt":
        findings.append(f"New-player path: expected first_run_prompt, got `{mode.route}`.")
    _record_screen(lines, "Tutorial Run / First Run Prompt", FIRST_RUN_PROMPT_LINES + ["Buttons: Yes, Skip Tutorial | No, Teach Me"])
    if not _click_button(mode, "new_to_fabled", findings, "New-player first-run prompt"):
        return
    if mode.route != "main_menu":
        findings.append(f"New-player path: expected main_menu after first-run choice, got `{mode.route}`.")
        return
    _record_screen(lines, "Tutorial Run / Main Menu", TUTORIAL_GATE_LINES)
    if not mode._tutorial_active():
        findings.append("New-player path: tutorial did not activate after choosing the tutorial option.")
        return
    if not _click_button(mode, "tutorial_story", findings, "Tutorial gate main menu"):
        return

    for encounter_index in range(1, 11):
        if mode.route != "tutorial_briefing":
            findings.append(f"Encounter {encounter_index}: expected tutorial_briefing at loop start, got `{mode.route}`.")
            return
        if mode._tutorial_encounter_index() != encounter_index:
            findings.append(
                f"Encounter {encounter_index}: tutorial pointer before the lesson is `{mode._tutorial_encounter_index()}`."
            )
            return
        if not _win_current_encounter(mode, encounter_index, findings, lines, label="Primary Run"):
            return
        if mode.route != "results" or not mode.result_victory:
            findings.append(f"Encounter {encounter_index}: expected a victory result before rematch.")
            return
        if not _rematch_current_encounter(mode, encounter_index, findings, lines):
            return

    _record_screen(
        lines,
        "Tutorial Run / Final State",
        [
            f"Route: {mode.route}",
            f"Tutorial complete: {mode.profile.tutorial_complete}",
            f"Current encounter pointer: {mode.profile.tutorial_current_encounter}",
            f"Gold after tutorial: {mode.profile.gold}",
            f"Tutorial pool after tutorial: {mode.profile.tutorial_artifact_pool}",
            f"Tutorial adventurers unlocked: {sorted(mode.profile.storybook_quested_adventurers)}",
        ],
    )

    if not mode.profile.tutorial_complete:
        findings.append("New-player path: tutorial did not mark complete after encounter 10.")
    if mode.profile.gold < TUTORIAL_STARTING_GOLD:
        findings.append(f"New-player path: final gold {mode.profile.gold} is below expected {TUTORIAL_STARTING_GOLD}.")
    if mode.profile.tutorial_artifact_pool:
        findings.append("New-player path: tutorial artifact pool was not cleared on completion.")
    if not set(TUTORIAL_PLAYER_IDS).issubset(mode.profile.storybook_quested_adventurers):
        findings.append("New-player path: not all tutorial adventurers were added to the permanent quested set.")
    if mode.route != "main_menu":
        findings.append(f"New-player path: expected main_menu after tutorial completion, got `{mode.route}`.")


def main():
    _ensure_pygame()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path.cwd() / "tutorial_audit_runs" / f"tutorial_audit_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = run_dir / "tutorial_flow_transcript.txt"
    report_path = run_dir / "tutorial_audit_report.md"

    findings: list[str] = []
    transcript: list[str] = [
        "FABLED Tutorial Flow Transcript",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    report_lines: list[str] = [
        "# Tutorial Audit Report",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Transcript: `{transcript_path}`",
        f"- Expected starting gold after tutorial or skip: `{TUTORIAL_STARTING_GOLD}`",
        "",
    ]

    _audit_skip_path(transcript, findings)
    _audit_new_player_path(transcript, findings)

    report_lines.append("## Findings")
    if findings:
        for finding in findings:
            report_lines.append(f"- {finding}")
    else:
        report_lines.append("- No audit failures detected.")

    transcript_path.write_text("\n".join(transcript) + "\n", encoding="utf-8")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(report_path)
    print(transcript_path)
    if findings:
        for finding in findings:
            print(f"FAIL: {finding}")
        raise SystemExit(1)
    print("Tutorial audit passed.")


if __name__ == "__main__":
    main()
