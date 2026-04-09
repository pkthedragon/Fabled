from __future__ import annotations

import random
import re
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pygame

from capture_player_runs import (
    OUTPUT_DIR as IMAGE_OUTPUT_DIR,
    _apply_first_bout_adapt_choice,
    _apply_first_quest_reward,
    _click_button,
    _click_card_entry,
    _make_mode,
    _render,
)
from quest_enemy_runtime import ALL_COMBATANT_DEFS_BY_ID, ALL_RUNTIME_ARTIFACTS_BY_ID
from quests_ai_battle import queue_team_plan
from quests_ai_bout import choose_bout_pick
from quests_ai_quest import QuestPartyChoice, choose_quest_party as base_choose_quest_party
from quests_ai_quest_loadout import assign_blind_quest_loadouts
from quests_ruleset_data import CLASS_SKILLS_BY_ID, ENEMY_ONLY_CLASS_SKILLS
from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT


ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "flow_audit_runs"
ENEMY_ONLY_CLASS_SKILLS_BY_ID = {
    skill.id: skill
    for skills in ENEMY_ONLY_CLASS_SKILLS.values()
    for skill in skills
}
SLOT_ORDER = {
    SLOT_FRONT: 0,
    SLOT_BACK_LEFT: 1,
    SLOT_BACK_RIGHT: 2,
}
SUSPICIOUS_PATTERNS = {
    "not implemented yet": "Unimplemented runtime hook appeared in the transcript.",
    "failed because": "Queued action failed at resolution time.",
    "cannot access": "A unit tried to use an inaccessible spell or effect.",
    "has no legal": "A queued action resolved without a legal target.",
    "cannot Strike right now": "A queued strike became invalid.",
    "cannot cast Spells from the backline": "A spell was queued from an illegal position.",
    "is out of ammo.": "A queued attack tried to fire without ammo.",
    "cannot switch weapons.": "A switch action was attempted on a non-switching unit.",
    "has no alternate weapon to switch to.": "A switch action was attempted with no alternate weapon.",
    "already wields both primary weapons.": "A dual-primary Apex unit tried to switch.",
    "Traceback (most recent call last)": "The run crashed.",
    "Run Status: FAILED": "The scripted flow did not complete.",
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "run"


def _member_name(member_id: str | None) -> str:
    if not member_id:
        return "Unknown"
    defn = ALL_COMBATANT_DEFS_BY_ID.get(member_id)
    return defn.name if defn is not None else member_id


def _class_skill_name(skill_id: str | None) -> str:
    if not skill_id:
        return "None"
    skill = CLASS_SKILLS_BY_ID.get(skill_id) or ENEMY_ONLY_CLASS_SKILLS_BY_ID.get(skill_id)
    return skill.name if skill is not None else skill_id


def _weapon_name(member_id: str | None, weapon_id: str | None) -> str:
    if not member_id or not weapon_id:
        return "None"
    defn = ALL_COMBATANT_DEFS_BY_ID.get(member_id)
    if defn is None:
        return weapon_id
    for weapon in defn.signature_weapons:
        if weapon.id == weapon_id:
            return weapon.name
    return weapon_id


def _artifact_name(artifact_id: str | None) -> str:
    if not artifact_id:
        return "None"
    artifact = ALL_RUNTIME_ARTIFACTS_BY_ID.get(artifact_id)
    return artifact.name if artifact is not None else artifact_id


def _sorted_members(members: list[dict]) -> list[dict]:
    return sorted(
        members,
        key=lambda member: (SLOT_ORDER.get(member.get("slot"), 99), _member_name(member.get("adventurer_id"))),
    )


def _format_member_dict(member: dict) -> str:
    adv_id = member.get("adventurer_id")
    name = _member_name(adv_id)
    slot = member.get("slot")
    class_name = member.get("class_name") or "None"
    skill_name = _class_skill_name(member.get("class_skill_id"))
    weapon_name = _weapon_name(adv_id, member.get("primary_weapon_id"))
    artifact_name = _artifact_name(member.get("artifact_id"))
    parts = [name]
    if slot:
        parts.append(f"[{slot}]")
    parts.append(f"Class {class_name}")
    parts.append(f"Skill {skill_name}")
    parts.append(f"Weapon {weapon_name}")
    if artifact_name != "None":
        parts.append(f"Artifact {artifact_name}")
    return " | ".join(parts)


def _format_combatant_state(unit) -> str:
    statuses = ", ".join(f"{status.kind}:{status.duration}" for status in unit.statuses if status.duration > 0) or "none"
    return (
        f"{unit.name} [{unit.slot}] | HP {unit.hp}/{unit.max_hp} | "
        f"Class {unit.class_name} | Skill {_class_skill_name(unit.class_skill.id)} | "
        f"Primary {unit.primary_weapon.name} | Secondary {unit.secondary_weapon.name} | "
        f"Artifact {_artifact_name(unit.artifact.id if unit.artifact else None)} | Statuses {statuses}"
    )


def _describe_queued_action(actor, action: dict | None, *, bonus: bool = False) -> str:
    if action is None:
        return "Unqueued"
    action_type = action.get("type", "skip")
    prefix = "Bonus " if bonus else ""
    if action_type == "skip":
        return f"{prefix}Skip"
    if action_type == "switch":
        return f"{prefix}Switch"
    target = action.get("target")
    target_name = getattr(target, "name", None) or action.get("target_slot") or "None"
    if action_type == "swap":
        return f"{prefix}Swap with {target_name}"
    if action_type == "strike":
        weapon = actor.strike_weapon_by_id(action.get("weapon_id"))
        return f"{prefix}Strike with {weapon.name} -> {target_name}"
    if action_type == "spell":
        effect = action.get("effect")
        effect_name = getattr(effect, "name", None) or "Spell"
        if getattr(effect, "target", "") in {"self", "none"}:
            return f"{prefix}{effect_name}"
        return f"{prefix}{effect_name} -> {target_name}"
    if action_type == "ultimate":
        effect = action.get("effect")
        effect_name = getattr(effect, "name", None) or "Ultimate"
        if getattr(effect, "target", "") in {"self", "none"}:
            return f"{prefix}Ultimate {effect_name}"
        return f"{prefix}Ultimate {effect_name} -> {target_name}"
    return f"{prefix}{action_type}"


def _player_screen_name(mode) -> str:
    route = mode.route
    if route == "main_menu":
        return "Main Menu"
    if route in {"guild_hall", "quests_menu"}:
        return "Quest Hub"
    if route == "quest_party_reveal":
        return "Quest Party Reveal"
    if route == "quest_party_loadout":
        if mode.quest_context in {"bout_random", "bout_focused"}:
            return "Bout Full Party Loadout"
        return "Quest Full Party Loadout"
    if route == "quest_draft":
        if mode.quest_context == "bout_random":
            return "Random Bout Encounter Select"
        if mode.quest_context == "bout_focused":
            return "Focused Bout Encounter Select"
        return "Quest Encounter Select"
    if route == "quest_loadout":
        if mode.quest_context in {"bout_random", "bout_focused"}:
            return "Bout Encounter Loadout"
        return "Quest Encounter Loadout"
    if route == "bouts_menu":
        return "Bout Mode Select"
    if route == "bout_draft":
        return "Focused Bout Roster Draft" if mode._bout_mode()["id"] == "focused" else "Random Bout Draft"
    if route == "bout_adapt":
        return "Random Bout Adapt"
    if route == "battle":
        return "Battle"
    if route == "results":
        return "Results"
    return route.replace("_", " ").title()


def _screen_summary_lines(mode) -> list[str]:
    lines: list[str] = []
    lines.append(f"Route: {mode.route}")
    lines.append(f"Quest Context: {mode.quest_context or 'None'}")
    lines.append(f"Gold: {mode.profile.gold} | Reputation: {mode.profile.reputation} | Rank: {getattr(mode.profile, 'rank', 'Unknown')}")
    if mode.route in {"guild_hall", "quests_menu"}:
        state = mode._quest_run_state("ai")
        if state.get("active"):
            lines.append(
                "Quest State: "
                f"{state.get('wins', 0)}W-{state.get('losses', 0)}L | "
                f"Quest Gold {state.get('gold_pool', 0)} | "
                f"Quest Rep {state.get('reputation_gain_total', 0):+d} | "
                f"Artifacts {', '.join(_artifact_name(aid) for aid in state.get('artifact_pool') or []) or 'None'}"
            )
            lines.append("Party:")
            for member in _sorted_members(state.get("team") or []):
                lines.append(f"  - {_format_member_dict(member)}")
        else:
            lines.append("Quest State: No active quest.")
    elif mode.route == "quest_party_reveal":
        lines.append("Revealed Quest Party:")
        for adventurer_id in mode.quest_selected_ids:
            lines.append(f"  - {_member_name(adventurer_id)}")
        pool = mode._quest_run_state("ai").get("artifact_pool") or []
        lines.append(f"Starting Artifact Pool: {', '.join(_artifact_name(aid) for aid in pool) or 'None'}")
    elif mode.route == "quest_party_loadout":
        state = mode.quest_party_loadout_state or {}
        lines.append("Full Party Loadout:")
        for member in state.get("team1", []):
            lines.append(f"  - {_format_member_dict(member)}")
    elif mode.route == "quest_draft":
        if mode.quest_context == "ranked":
            lines.append(f"Enemy Locale: {mode.quest_enemy_locale_name or 'Unknown'}")
            lines.append(f"Enemy Tier: {mode.quest_enemy_tier_name or 'Unknown'}")
            lines.append(f"Enemy Party: {mode.quest_enemy_party_title or 'Unknown'}")
        elif mode.quest_context in {"bout_random", "bout_focused"}:
            lines.append(f"Bout Score: {mode.bout_run.player_wins}-{mode.bout_run.opponent_wins}")
        lines.append(f"Available Picks: {', '.join(_member_name(aid) for aid in mode.quest_offer_ids)}")
        if mode.quest_enemy_setup_members:
            lines.append("Enemy Roster Preview:")
            for member in _sorted_members(mode.quest_enemy_setup_members):
                lines.append(f"  - {_format_member_dict(member)}")
    elif mode.route == "quest_loadout":
        state = mode.quest_setup_state or {}
        player_team_key = f"team{mode.quest_player_seat}"
        enemy_team_key = "team2" if player_team_key == "team1" else "team1"
        lines.append("Player Encounter Team:")
        for member in _sorted_members(state.get(player_team_key, [])):
            lines.append(f"  - {_format_member_dict(member)}")
        lines.append("Enemy Encounter Team:")
        for member in _sorted_members(state.get(enemy_team_key, [])):
            lines.append(f"  - {_format_member_dict(member)}")
    elif mode.route == "bouts_menu":
        lines.append(f"Bout Run Active: {mode.bout_run.active}")
        lines.append(f"Bout Record: {mode.bout_run.player_wins}-{mode.bout_run.opponent_wins}")
    elif mode.route == "bout_draft":
        lines.append(f"Mode: {mode._bout_mode()['id']}")
        lines.append(f"Current Picker Seat: {mode.bout_current_player}")
        lines.append(f"Player Seat: {mode.bout_player_seat} | AI Seat: {mode.bout_ai_seat}")
        lines.append(f"Available Roster: {', '.join(_member_name(aid) for aid in mode._available_bout_ids())}")
        lines.append(f"Player Drafted: {', '.join(_member_name(aid) for aid in mode._seat_ids(mode.bout_player_seat)) or 'None'}")
        lines.append(f"AI Drafted: {', '.join(_member_name(aid) for aid in mode._seat_ids(mode.bout_ai_seat)) or 'None'}")
    elif mode.route == "bout_adapt":
        lines.append(f"Artifact Options: {', '.join(_artifact_name(aid) for aid in mode.bout_adapt_artifact_options) or 'None'}")
        lines.append(f"Recruit Options: {', '.join(_member_name(aid) for aid in mode.bout_adapt_recruit_options) or 'None'}")
    elif mode.route == "results":
        lines.append(f"Winner: {mode.result_winner}")
        lines.append(f"Victory: {mode.result_victory}")
        if mode.result_lines:
            lines.append("Result Lines:")
            for line in mode.result_lines:
                lines.append(f"  - {line}")
    elif mode.route == "battle" and mode.battle_controller is not None:
        battle = mode.battle_controller.battle
        player_num = mode.battle_controller.human_team_num
        enemy_num = 1 if player_num == 2 else 2
        lines.append(f"Round: {battle.round_num}")
        lines.append("Player Team:")
        for unit in battle.get_team(player_num).members:
            lines.append(f"  - {_format_combatant_state(unit)}")
        lines.append("Enemy Team:")
        for unit in battle.get_team(enemy_num).members:
            lines.append(f"  - {_format_combatant_state(unit)}")
    return lines


@dataclass
class RunRecord:
    category: str
    seed: int
    log_path: Path
    success: bool
    findings: list[str] = field(default_factory=list)
    final_screen: str = ""


class TranscriptWriter:
    def __init__(self, path: Path, *, category: str, seed: int):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("w", encoding="utf-8")
        self.category = category
        self.seed = seed
        self.screen_index = 0
        self._w(f"Run Category: {category}")
        self._w(f"Seed: {seed}")
        self._w(f"Started: {datetime.now().isoformat(timespec='seconds')}")
        self._w("")

    def _w(self, line: str = ""):
        self.handle.write(line + "\n")

    def screen(self, mode, title: str | None = None):
        _render(mode)
        self.screen_index += 1
        screen_title = title or _player_screen_name(mode)
        self._w(f"=== Screen {self.screen_index:02d}: {screen_title} ===")
        for line in _screen_summary_lines(mode):
            self._w(line)
        self._w("")

    def action(self, text: str):
        self._w(f"Action: {text}")

    def note(self, text: str):
        self._w(f"Note: {text}")

    def heading(self, text: str):
        self._w(f"-- {text} --")

    def close(self, *, success: bool, final_screen: str = "", error_text: str | None = None):
        self._w("")
        self._w(f"Run Status: {'SUCCESS' if success else 'FAILED'}")
        if final_screen:
            self._w(f"Final Screen: {final_screen}")
        if error_text:
            self._w("Error:")
            self._w(error_text.rstrip())
        self._w(f"Finished: {datetime.now().isoformat(timespec='seconds')}")
        self.handle.close()


def _queue_player_phase(controller, *, difficulty: str, bonus: bool):
    queue_team_plan(
        controller.battle,
        controller.human_team_num,
        bonus=bonus,
        difficulty=difficulty,
        rng=controller.rng,
    )
    controller.phase = "bonus_resolve_ready" if bonus else "action_resolve_ready"
    controller.active_actor = None
    controller.pending_choice = None
    controller.target_candidates = []
    controller.spellbook_open = False


def _record_team_plans(writer: TranscriptWriter, controller, *, bonus: bool):
    battle = controller.battle
    player_num = controller.human_team_num
    enemy_num = 1 if player_num == 2 else 2
    player_team = battle.get_team(player_num)
    enemy_team = battle.get_team(enemy_num)
    label = "Bonus Plans" if bonus else "Action Plans"
    writer.heading(f"Round {battle.round_num} {label}")
    writer.note("Player")
    for unit in player_team.alive():
        action = unit.queued_bonus_action if bonus else unit.queued_action
        writer._w(f"  - {unit.name}: {_describe_queued_action(unit, action, bonus=bonus)}")
    writer.note("Enemy")
    for unit in enemy_team.alive():
        action = unit.queued_bonus_action if bonus else unit.queued_action
        writer._w(f"  - {unit.name}: {_describe_queued_action(unit, action, bonus=bonus)}")
    writer._w("")


def _record_battle_state(writer: TranscriptWriter, controller):
    battle = controller.battle
    writer.heading(f"Round {battle.round_num} State")
    writer.note("Player Team")
    for unit in battle.team1.members:
        writer._w(f"  - {_format_combatant_state(unit)}")
    writer.note("Enemy Team")
    for unit in battle.team2.members:
        writer._w(f"  - {_format_combatant_state(unit)}")
    writer._w("")


def _record_new_battle_log(writer: TranscriptWriter, battle, start_index: int, *, label: str):
    lines = battle.log[start_index:]
    writer.heading(label)
    if not lines:
        writer._w("  - No new battle log lines.")
    else:
        for line in lines:
            writer._w(f"  - {line}")
    writer._w("")


def _safe_choose_quest_party(
    offer_ids: list[str] | tuple[str, ...],
    *,
    enemy_party_ids: list[str] | tuple[str, ...] = (),
    difficulty: str = "hard",
    rng=None,
) -> QuestPartyChoice:
    offered = list(dict.fromkeys(offer_ids))
    rng = rng or random.Random()
    original_error = None
    try:
        return base_choose_quest_party(
            offered,
            enemy_party_ids=enemy_party_ids,
            difficulty=difficulty,
            rng=rng,
        )
    except Exception as exc:
        original_error = exc

    for subset_size in range(min(6, len(offered)) - 1, 2, -1):
        subsets = list(combinations(offered, subset_size))
        rng.shuffle(subsets)
        for subset in subsets[:80]:
            try:
                return base_choose_quest_party(
                    list(subset),
                    enemy_party_ids=enemy_party_ids,
                    difficulty=difficulty,
                    rng=rng,
                )
            except Exception:
                continue

    for trio in combinations(offered, 3):
        trio_ids = list(trio)
        try:
            package = assign_blind_quest_loadouts(trio_ids)
            profile = package.trios[tuple(sorted(trio_ids))]
            return QuestPartyChoice(
                offer_ids=tuple(trio_ids),
                team_ids=tuple(trio_ids),
                loadout=profile.loadout,
                package=package,
            )
        except Exception:
            continue

    if original_error is None:
        raise RuntimeError(f"Could not build a quest trio from offer {offered}.")
    raise RuntimeError(f"Could not build a quest trio from offer {offered}.") from original_error


def _autoplay_battle_with_transcript(mode, writer: TranscriptWriter, *, difficulty: str, max_rounds: int = 60):
    seen_rounds: set[int] = set()
    while mode.route == "battle":
        controller = mode.battle_controller
        if controller is None:
            raise RuntimeError("Battle route entered without a controller.")
        battle = controller.battle
        if battle.round_num > max_rounds:
            raise RuntimeError(f"Battle exceeded {max_rounds} rounds.")
        if battle.round_num not in seen_rounds:
            _record_battle_state(writer, controller)
            seen_rounds.add(battle.round_num)
        if controller.phase in {"action_select", "action_target"}:
            _queue_player_phase(controller, difficulty=difficulty, bonus=False)
            _record_team_plans(writer, controller, bonus=False)
            start_index = len(battle.log)
            controller.resolve_current_phase()
            mode._check_battle_results()
            if mode.route == "battle":
                _record_new_battle_log(writer, battle, start_index, label=f"Round {battle.round_num} Action Log")
            else:
                _record_new_battle_log(writer, battle, start_index, label="Battle Action Log")
            continue
        controller = mode.battle_controller
        if controller is None or mode.route != "battle":
            break
        battle = controller.battle
        if controller.phase in {"bonus_select", "bonus_target"}:
            _queue_player_phase(controller, difficulty=difficulty, bonus=True)
            _record_team_plans(writer, controller, bonus=True)
            start_index = len(battle.log)
            controller.resolve_current_phase()
            mode._check_battle_results()
            if mode.route == "battle":
                _record_new_battle_log(writer, battle, start_index, label=f"Round {battle.round_num - 1} Bonus Log")
            else:
                _record_new_battle_log(writer, battle, start_index, label="Battle Bonus Log")
        elif controller.phase in {"action_resolve_ready", "bonus_resolve_ready"}:
            start_index = len(battle.log)
            controller.resolve_current_phase()
            mode._check_battle_results()
            _record_new_battle_log(writer, battle, start_index, label="Battle Log")
        else:
            raise RuntimeError(f"Unexpected battle controller phase: {controller.phase}")


def _pick_quest_trio(mode, writer: TranscriptWriter, *, difficulty: str):
    trio = list(
        _safe_choose_quest_party(
            mode.quest_offer_ids,
            enemy_party_ids=mode.quest_enemy_party_ids,
            difficulty=difficulty,
            rng=mode.rng,
        ).team_ids
    )
    writer.note(f"Autoplayer chose trio: {', '.join(_member_name(aid) for aid in trio)}")
    for pick_index, adventurer_id in enumerate(trio, start=1):
        writer.action(f"Select encounter pick {pick_index}: {_member_name(adventurer_id)}")
        _click_card_entry(mode, "cards", adventurer_id)
        _render(mode)
        _click_button(mode, "pick")
    return trio


def _pick_focused_roster(mode, writer: TranscriptWriter):
    while mode.route == "bout_draft" and not mode._draft_complete():
        available_ids = mode._available_bout_ids()
        own_ids = mode._seat_ids(mode.bout_player_seat)
        enemy_ids = mode._seat_ids(mode.bout_ai_seat)
        choice = choose_bout_pick(
            available_ids,
            own_ids,
            enemy_ids,
            seat=mode.bout_player_seat,
            difficulty="hard",
            target_size=6,
            rng=mode.rng,
        )
        writer.action(f"Draft {_member_name(choice)} for the focused bout roster")
        before_player = list(mode._seat_ids(mode.bout_player_seat))
        before_ai = list(mode._seat_ids(mode.bout_ai_seat))
        for rect, adventurer_id in mode.last_buttons.get("pool", []):
            if adventurer_id == choice:
                mode.handle_click((rect.centerx, rect.centery))
                break
        else:
            raise RuntimeError(f"Could not find focused roster pick '{choice}'.")
        _render(mode)
        _click_button(mode, "draft")
        _render(mode)
        after_player = list(mode._seat_ids(mode.bout_player_seat))
        after_ai = list(mode._seat_ids(mode.bout_ai_seat))
        picked_by_player = [adv for adv in after_player if adv not in before_player]
        picked_by_ai = [adv for adv in after_ai if adv not in before_ai]
        if picked_by_player:
            writer.note(f"Player added: {', '.join(_member_name(aid) for aid in picked_by_player)}")
        if picked_by_ai:
            writer.note(f"AI added: {', '.join(_member_name(aid) for aid in picked_by_ai)}")
        writer._w("")


def _run_quest(writer: TranscriptWriter, seed: int):
    mode = _make_mode(seed)
    writer.screen(mode, "Main Menu")
    writer.action("Click Quests")
    _click_button(mode, "guild_hall")
    writer.screen(mode, "Quest Hub")
    advance_key = "advance" if "advance" in mode.last_buttons else "current_quest"
    writer.action("Begin a new quest")
    _click_button(mode, advance_key)
    writer.screen(mode, "Quest Party Reveal")
    writer.action("Confirm the revealed six-adventurer quest party")
    _click_button(mode, "confirm")
    writer.screen(mode, "Quest Full Party Loadout")
    writer.action("Accept the current full-party loadout and continue")
    _click_button(mode, "done")
    writer.screen(mode, "Quest Hub")
    encounter_index = 1
    while True:
        advance_key = "advance" if "advance" in mode.last_buttons else "current_quest"
        writer.action(f"Prepare quest encounter {encounter_index}")
        _click_button(mode, advance_key)
        writer.screen(mode, f"Quest Encounter {encounter_index} Select")
        _pick_quest_trio(mode, writer, difficulty="normal")
        writer.action("Confirm the three-adventurer encounter team")
        _click_button(mode, "continue")
        writer.screen(mode, f"Quest Encounter {encounter_index} Loadout")
        writer.action("Lock in the encounter loadout")
        _click_button(mode, "confirm")
        writer.screen(mode, f"Quest Encounter {encounter_index} Battle")
        _autoplay_battle_with_transcript(mode, writer, difficulty="normal")
        if mode.route != "results":
            raise RuntimeError(f"Expected results after quest encounter {encounter_index}, got '{mode.route}'.")
        writer.screen(mode, f"Quest Encounter {encounter_index} Results")
        writer.action("Continue from the results screen")
        _click_button(mode, "continue")
        if mode.route == "quest_reward_choice":
            writer.screen(mode, f"Quest Encounter {encounter_index} Reward Choice")
            writer.action("Take the first available gold reward")
            _apply_first_quest_reward(mode)
            writer.screen(mode, "Quest Hub")
        else:
            writer.screen(mode, "Quest Hub")
        if not mode._quest_run_state("ai").get("active"):
            break
        encounter_index += 1
        if encounter_index > 80:
            raise RuntimeError("Quest flow exceeded 80 encounters.")
    return mode


def _run_random_bout(writer: TranscriptWriter, seed: int):
    mode = _make_mode(seed)
    writer.screen(mode, "Main Menu")
    writer.action("Click Bouts")
    _click_button(mode, "bouts")
    writer.screen(mode, "Bout Mode Select")
    writer.action("Start a Random Bout versus AI")
    _click_button(mode, "vs_random")
    writer.screen(mode, "Bout Full Party Loadout")
    writer.action("Accept the full-party bout loadout")
    _click_button(mode, "done")
    writer.screen(mode, "Random Bout Encounter Select")
    match_index = 1
    while True:
        _pick_quest_trio(mode, writer, difficulty="normal")
        writer.action(f"Lock in Random Bout match {match_index}")
        _click_button(mode, "continue")
        writer.screen(mode, f"Random Bout Match {match_index} Loadout")
        writer.action("Confirm the encounter loadout")
        _click_button(mode, "confirm")
        writer.screen(mode, f"Random Bout Match {match_index} Battle")
        _autoplay_battle_with_transcript(mode, writer, difficulty="hard")
        if mode.route != "results":
            raise RuntimeError(f"Expected results after Random Bout match {match_index}, got '{mode.route}'.")
        writer.screen(mode, f"Random Bout Match {match_index} Results")
        writer.action("Continue from the results screen")
        _click_button(mode, "continue")
        if mode.route == "bout_adapt":
            writer.screen(mode, f"Random Bout Match {match_index} Adapt")
            writer.action("Take the first available adapt option")
            _apply_first_bout_adapt_choice(mode)
            writer.screen(mode, "Bout Full Party Loadout")
            writer.action("Accept the adapted full-party loadout")
            _click_button(mode, "done")
            match_index += 1
            writer.screen(mode, f"Random Bout Match {match_index} Select")
        elif mode.route == "bouts_menu":
            writer.screen(mode, "Bout Mode Select")
            break
        else:
            raise RuntimeError(f"Unexpected route after Random Bout results: '{mode.route}'.")
        if match_index > 5:
            raise RuntimeError("Random bout flow exceeded 5 matches.")
    return mode


def _run_focused_bout(writer: TranscriptWriter, seed: int):
    mode = _make_mode(seed)
    writer.screen(mode, "Main Menu")
    writer.action("Click Bouts")
    _click_button(mode, "bouts")
    writer.screen(mode, "Bout Mode Select")
    writer.action("Start a Focused Bout versus AI")
    _click_button(mode, "vs_focused")
    writer.screen(mode, "Focused Bout Roster Draft")
    _pick_focused_roster(mode, writer)
    if mode.route != "quest_party_loadout":
        raise RuntimeError(f"Focused bout roster draft did not advance to full-party loadout. Current route: {mode.route}")
    writer.screen(mode, "Bout Full Party Loadout")
    writer.action("Accept the focused-bout full-party loadout")
    _click_button(mode, "done")
    writer.screen(mode, "Focused Bout Encounter Select")
    match_index = 1
    while True:
        _pick_quest_trio(mode, writer, difficulty="hard")
        writer.action(f"Lock in Focused Bout match {match_index}")
        _click_button(mode, "continue")
        writer.screen(mode, f"Focused Bout Match {match_index} Loadout")
        writer.action("Confirm the encounter loadout")
        _click_button(mode, "confirm")
        writer.screen(mode, f"Focused Bout Match {match_index} Battle")
        _autoplay_battle_with_transcript(mode, writer, difficulty="hard")
        if mode.route != "results":
            raise RuntimeError(f"Expected results after Focused Bout match {match_index}, got '{mode.route}'.")
        writer.screen(mode, f"Focused Bout Match {match_index} Results")
        writer.action("Continue from the results screen")
        _click_button(mode, "continue")
        if mode.route == "quest_draft":
            match_index += 1
            writer.screen(mode, f"Focused Bout Match {match_index} Select")
        elif mode.route == "bouts_menu":
            writer.screen(mode, "Bout Mode Select")
            break
        else:
            raise RuntimeError(f"Unexpected route after Focused Bout results: '{mode.route}'.")
        if match_index > 5:
            raise RuntimeError("Focused bout flow exceeded 5 matches.")
    return mode


def _audit_log(record: RunRecord, *, expected_final_screen: str):
    text = record.log_path.read_text(encoding="utf-8")
    findings: list[str] = []
    screen_titles = re.findall(r"^=== Screen \d+: (.+?) ===$", text, flags=re.MULTILINE)
    if not screen_titles:
        findings.append("Transcript contained no screen sections.")
    else:
        if screen_titles[0] != "Main Menu":
            findings.append(f"Transcript did not start on Main Menu. Found '{screen_titles[0]}' instead.")
        if screen_titles[-1] != expected_final_screen:
            findings.append(
                f"Transcript did not end on the expected final screen '{expected_final_screen}'. "
                f"Found '{screen_titles[-1]}' instead."
            )
    if "=== Screen" in text and "Battle Action Log" not in text and "Round 1 Action Log" not in text:
        findings.append("Transcript contained gameplay screens but no recorded battle action logs.")
    for pattern, meaning in SUSPICIOUS_PATTERNS.items():
        if pattern not in text:
            continue
        for line in text.splitlines():
            if pattern in line:
                findings.append(f"{meaning} Line: {line}")
                break
    record.findings = findings
    record.final_screen = screen_titles[-1] if screen_titles else ""


def _run_successful_transcripts(
    output_dir: Path,
    *,
    category: str,
    runner,
    expected_final_screen: str,
    start_seed: int,
    target_runs: int = 3,
    max_attempts: int = 20,
) -> list[RunRecord]:
    records: list[RunRecord] = []
    successes = 0
    attempts = 0
    seed = start_seed
    while successes < target_runs and attempts < max_attempts:
        attempts += 1
        run_label = f"{category}_run_{successes + 1:02d}_seed_{seed}"
        log_path = output_dir / f"{_slugify(run_label)}.txt"
        writer = TranscriptWriter(log_path, category=category, seed=seed)
        success = False
        final_screen = ""
        error_text = None
        try:
            mode = runner(writer, seed)
            success = True
            final_screen = _player_screen_name(mode)
        except Exception:
            error_text = traceback.format_exc()
        writer.close(success=success, final_screen=final_screen, error_text=error_text)
        record = RunRecord(category=category, seed=seed, log_path=log_path, success=success, final_screen=final_screen)
        _audit_log(record, expected_final_screen=expected_final_screen)
        records.append(record)
        if success:
            successes += 1
        seed += 1
    return records


def _write_audit_report(output_dir: Path, records: list[RunRecord]) -> Path:
    report_path = output_dir / "flow_audit_report.txt"
    lines = [
        "FABLED Flow Audit",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
    ]
    grouped = {}
    for record in records:
        grouped.setdefault(record.category, []).append(record)
    total_findings = 0
    for category in ("quest", "random_bout", "focused_bout"):
        category_records = grouped.get(category, [])
        lines.append(f"=== {category} ===")
        if not category_records:
            lines.append("No runs recorded.")
            lines.append("")
            continue
        for record in category_records:
            status = "SUCCESS" if record.success else "FAILED"
            lines.append(f"{record.log_path.name} | seed {record.seed} | {status} | final screen {record.final_screen or 'Unknown'}")
            if record.findings:
                total_findings += len(record.findings)
                for finding in record.findings:
                    lines.append(f"  - {finding}")
            else:
                lines.append("  - No audit findings.")
        lines.append("")
    lines.append(f"Total Findings: {total_findings}")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main():
    pygame.init()
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / f"flow_audit_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[RunRecord] = []
    records.extend(
        _run_successful_transcripts(
            output_dir,
            category="quest",
            runner=_run_quest,
            expected_final_screen="Quest Hub",
            start_seed=1,
        )
    )
    records.extend(
        _run_successful_transcripts(
            output_dir,
            category="random_bout",
            runner=_run_random_bout,
            expected_final_screen="Bout Mode Select",
            start_seed=101,
        )
    )
    records.extend(
        _run_successful_transcripts(
            output_dir,
            category="focused_bout",
            runner=_run_focused_bout,
            expected_final_screen="Bout Mode Select",
            start_seed=201,
        )
    )
    report_path = _write_audit_report(output_dir, records)
    print(f"Logs saved to: {output_dir}")
    print(f"Audit report: {report_path}")
    print(f"Image output root remains available at: {IMAGE_OUTPUT_DIR}")


if __name__ == "__main__":
    main()
