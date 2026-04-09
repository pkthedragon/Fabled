from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from models import CampaignProfile
from quests_ruleset_data import CLASS_SKILLS
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
    encounter_spec,
)


@dataclass(frozen=True)
class EncounterPlan:
    selected_ids: tuple[str, ...] | None = None
    slots: tuple[str, ...] | None = None
    classes: dict[str, str] | None = None
    skill_indexes: dict[str, int] | None = None
    weapons: dict[str, str] | None = None
    artifacts: dict[str, str | None] | None = None


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


def _has_ready_effect(actor, effect_id: str) -> bool:
    return actor.cooldowns.get(effect_id, 0) <= 0 and any(effect.id == effect_id for effect in actor.active_spells())


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


def _run_single_battle(mode: StorybookMode):
    controller = mode.battle_controller
    prompt_ids: list[str] = []
    loop_guard = 0
    while controller is not None and controller.phase != "result" and loop_guard < 600:
        loop_guard += 1
        if getattr(controller, "tutorial_prompt_id", None):
            prompt_id = controller.tutorial_prompt_id
            if prompt_id not in prompt_ids:
                prompt_ids.append(prompt_id)
            controller.dismiss_tutorial_prompt()
            continue
        if controller.can_resolve():
            controller.resolve_current_phase()
            mode._check_battle_results()
            controller = mode.battle_controller
            continue
        if controller.phase in {"action_select", "bonus_select"}:
            _perform_action(controller)
            continue
        if controller.phase in {"action_target", "bonus_target"}:
            legal = controller.legal_targets()
            target = _choose_priority_target(controller, controller.active_actor, legal)
            if target is not None:
                controller.select_target(target)
            else:
                controller.cancel_targeting()
            continue
        raise RuntimeError(f"Unhandled tutorial battle phase: {controller.phase}")

    if controller is None:
        return prompt_ids, True, "battle_controller_cleared"
    if controller.phase != "result":
        return prompt_ids, False, f"phase_stuck:{controller.phase}"
    return prompt_ids, True, "result"


def _audit_skip_path(lines: list[str], findings: list[str]):
    profile = CampaignProfile()
    mode = StorybookMode(profile)
    mode._persist_profile = lambda: None
    if mode.route != "first_run_prompt":
        findings.append(f"Skip path: expected first_run_prompt, got {mode.route}.")
    mode._accept_first_run_choice(played_before=True)
    lines.append("Skip path:")
    lines.append(f"- Route after choice: `{mode.route}`")
    lines.append(f"- Tutorial complete: `{mode.profile.tutorial_complete}`")
    lines.append(f"- Gold: `{mode.profile.gold}`")
    if not mode.profile.tutorial_complete:
        findings.append("Skip path: tutorial was not marked complete.")
    if mode.profile.gold < TUTORIAL_STARTING_GOLD:
        findings.append(f"Skip path: gold {mode.profile.gold} is below expected {TUTORIAL_STARTING_GOLD}.")


def _audit_new_player_path(lines: list[str], findings: list[str]):
    profile = CampaignProfile()
    mode = StorybookMode(profile)
    mode._persist_profile = lambda: None
    encounter_summaries: list[str] = []

    if mode.route != "first_run_prompt":
        findings.append(f"New-player path: expected first_run_prompt, got {mode.route}.")
    mode._accept_first_run_choice(played_before=False)
    if mode.route != "main_menu":
        findings.append(f"New-player path: expected main_menu after choice, got {mode.route}.")
    if not mode._tutorial_active():
        findings.append("New-player path: tutorial did not activate after choosing 'No, Teach Me'.")
    mode._open_tutorial_current_step()

    for encounter_index in range(1, 11):
        attempts = 0
        won = False
        all_prompts: list[str] = []
        while attempts < 4 and not won:
            attempts += 1
            if mode.route != "tutorial_briefing":
                findings.append(f"Encounter {encounter_index}: expected tutorial_briefing before attempt, got {mode.route}.")
                mode.route = "tutorial_briefing"
            if mode._tutorial_encounter_index() != encounter_index:
                findings.append(
                    f"Encounter {encounter_index}: profile pointer was `{mode._tutorial_encounter_index()}` before battle."
                )
            mode._continue_tutorial_from_briefing()
            if mode.route == "tutorial_party_select":
                _configure_setup(mode, encounter_index)
                if mode.tutorial_setup_state is None:
                    mode.tutorial_setup_state = build_player_setup(
                        encounter_index,
                        selected_ids=mode.tutorial_selected_ids,
                        artifact_pool=getattr(mode.profile, "tutorial_artifact_pool", []),
                    )
                mode.route = "tutorial_loadout"
            elif mode.route == "tutorial_loadout":
                _configure_setup(mode, encounter_index)
            elif mode.route == "battle":
                pass
            else:
                findings.append(f"Encounter {encounter_index}: unexpected route `{mode.route}` after briefing continue.")

            if mode.route == "tutorial_loadout":
                mode._start_tutorial_battle()
            if mode.route != "battle":
                findings.append(f"Encounter {encounter_index}: expected battle route, got {mode.route}.")
                break

            prompt_ids, finished, terminal_state = _run_single_battle(mode)
            for prompt_id in prompt_ids:
                if prompt_id not in all_prompts:
                    all_prompts.append(prompt_id)
            if not finished:
                findings.append(f"Encounter {encounter_index}: battle loop did not finish cleanly (`{terminal_state}`).")
                break

            if mode.route == "tutorial_briefing":
                # Early no-defeat restart.
                continue
            if mode.route != "results":
                findings.append(f"Encounter {encounter_index}: expected results route after battle, got {mode.route}.")
                break
            won = bool(mode.result_victory)
            result_lines = list(mode.result_lines)
            encounter_summaries.append(
                f"- Encounter {encounter_index}: {'WIN' if won else 'LOSS'} in {attempts} attempt(s); prompts: {', '.join(all_prompts) or 'none'}; result: {' | '.join(result_lines)}"
            )
            mode._continue_from_results()

        if not won:
            findings.append(f"Encounter {encounter_index}: failed to clear within {attempts} attempt(s).")
            break
        if encounter_index < 10 and mode.route != "tutorial_briefing":
            findings.append(f"Encounter {encounter_index}: expected tutorial_briefing after win, got {mode.route}.")

    lines.append("New-player path:")
    lines.extend(encounter_summaries)
    lines.append(f"- Final route: `{mode.route}`")
    lines.append(f"- Tutorial complete: `{mode.profile.tutorial_complete}`")
    lines.append(f"- Current encounter pointer: `{mode.profile.tutorial_current_encounter}`")
    lines.append(f"- Gold after tutorial: `{mode.profile.gold}`")
    lines.append(f"- Tutorial pool after tutorial: `{mode.profile.tutorial_artifact_pool}`")
    lines.append(f"- Tutorial adventurers unlocked: `{sorted(mode.profile.storybook_quested_adventurers)}`")

    if not mode.profile.tutorial_complete:
        findings.append("New-player path: tutorial did not mark complete after encounter 10.")
    if mode.profile.gold < TUTORIAL_STARTING_GOLD:
        findings.append(f"New-player path: final gold {mode.profile.gold} is below expected {TUTORIAL_STARTING_GOLD}.")
    if mode.profile.tutorial_artifact_pool:
        findings.append("New-player path: tutorial artifact pool was not cleared on completion.")
    if not set(TUTORIAL_PLAYER_IDS).issubset(mode.profile.storybook_quested_adventurers):
        findings.append("New-player path: not all tutorial adventurers were added to the permanent quested set.")
    if mode.route != "main_menu":
        findings.append(f"New-player path: expected main_menu after tutorial completion, got {mode.route}.")


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path.cwd() / f"tutorial_audit_{timestamp}.md"
    findings: list[str] = []
    lines: list[str] = [
        "# Tutorial Audit",
        "",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Expected starting gold after tutorial or skip: `{TUTORIAL_STARTING_GOLD}`",
        "",
    ]

    _audit_skip_path(lines, findings)
    lines.append("")
    _audit_new_player_path(lines, findings)
    lines.append("")
    lines.append("## Findings")
    if findings:
        for finding in findings:
            lines.append(f"- {finding}")
    else:
        lines.append("- No audit failures detected.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report_path)
    if findings:
        for finding in findings:
            print(f"FAIL: {finding}")
        raise SystemExit(1)
    print("Tutorial audit passed.")


if __name__ == "__main__":
    main()
