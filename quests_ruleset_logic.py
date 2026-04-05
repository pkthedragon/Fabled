from __future__ import annotations

from dataclasses import replace
import math
from typing import Dict, Iterable, List, Optional

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT

from quests_ruleset_data import (
    ADVENTURERS_BY_ID,
    ALL_ADVENTURER_SPELLS,
    ARTIFACTS_BY_ID,
    CLASS_SKILLS,
    CLASS_SKILLS_BY_ID,
    GOOSE_QUILL_RETAINED_METER,
    ULTIMATE_METER_MAX,
    ULTIMATE_WIN_COUNT,
)
from quests_ruleset_models import (
    ActiveEffect,
    AdventurerDef,
    ArtifactDef,
    BattleState,
    CombatantState,
    PassiveEffect,
    StatusInstance,
    TeamState,
    WeaponDef,
)


SLOT_PRIORITY = {
    SLOT_FRONT: 0,
    SLOT_BACK_LEFT: 1,
    SLOT_BACK_RIGHT: 2,
}
SLOT_SEQUENCE = (SLOT_BACK_LEFT, SLOT_FRONT, SLOT_BACK_RIGHT)

TIMED_MARKERS = {
    "artifact_bonus_spell_rounds",
    "cleansing_inferno_rounds",
    "cant_strike_rounds",
    "combusted_rounds",
    "crafty_wall_rounds",
    "crowstorm_rounds",
    "disenfranchise_rounds",
    "eyes_everywhere_rounds",
    "fated_duel_rounds",
    "forty_thieves_rounds",
    "free_ranged_after_switch",
    "gaze_of_love_rounds",
    "ignore_targeting_strikes",
    "mass_hysteria_rounds",
    "mistform_ready",
    "next_spell_no_cooldown",
    "not_by_the_hair_rounds",
    "raise_the_sky_rounds",
    "rabbit_hole_extra_rounds",
    "shimmering_valor_rounds",
    "silver_aegis_ready",
    "silver_aegis_always_active",
    "spell_bonus_rounds",
    "spread_fortune_rounds",
    "stolen_voices_rounds",
    "switched_this_round",
    "web_of_centuries_rounds",
    "bonus_switch_rounds",
    "trojan_horse_rounds",
    "seeking_yarn_rounds",
    "event_horizon_rounds",
    "polymorph_rounds",
    "tea_party_rounds",
    "untargetable_rounds",
    "witchs_blessing_rounds",
    "wolf_unchained_rounds",
}

NO_CLASS_SKILL = PassiveEffect(
    id="no_class_skill",
    name="No Class",
    description="No class is selected.",
)


def _other_player(player_num: int) -> int:
    return 2 if player_num == 1 else 1


def _is_ella_backline(actor: CombatantState) -> bool:
    return actor.defn.id == "ashen_ella" and actor.slot != SLOT_FRONT


def _sync_position_locked_weapon(actor: CombatantState):
    if actor.defn.id != "ashen_ella":
        return
    front_weapon = next(weapon for weapon in actor.defn.signature_weapons if weapon.id == "obsidian_slippers")
    back_weapon = next(weapon for weapon in actor.defn.signature_weapons if weapon.id == "dusty_broom")
    if actor.slot == SLOT_FRONT:
        actor.primary_weapon = front_weapon
        actor.secondary_weapon = back_weapon
    else:
        actor.primary_weapon = back_weapon
        actor.secondary_weapon = front_weapon


def _is_targetable(actor: CombatantState, target: CombatantState) -> bool:
    if target.ko:
        return False
    if target.markers.get("untargetable_rounds", 0) > 0:
        return False
    if _is_ella_backline(target):
        return False
    return True


def _initiative_speed(battle: BattleState, unit: CombatantState) -> int:
    speed = unit.get_stat("speed", battle)
    if _unit_in_air_current(unit, battle) and unit.defn.id == "witch_of_the_east":
        speed += 15
    enemy_front = enemy_team_for_actor(battle, unit).frontline()
    if unit.slot == SLOT_FRONT and enemy_front is not None and enemy_front.defn.id == "march_hare":
        speed -= 10
    return max(1, speed)


def _slot_index(slot: str) -> int:
    return SLOT_SEQUENCE.index(slot)


def _slot_to_left(slot: str) -> str | None:
    index = _slot_index(slot)
    return None if index <= 0 else SLOT_SEQUENCE[index - 1]


def _slot_to_right(slot: str) -> str | None:
    index = _slot_index(slot)
    return None if index >= len(SLOT_SEQUENCE) - 1 else SLOT_SEQUENCE[index + 1]


def _air_currents(battle: BattleState) -> dict[str, int]:
    currents = battle.markers.get("air_currents")
    if not isinstance(currents, dict):
        currents = {}
        battle.markers["air_currents"] = currents
    return currents


def _set_air_current(battle: BattleState, slot: str, duration: int):
    currents = _air_currents(battle)
    currents[slot] = max(duration, currents.get(slot, 0))


def _unit_in_air_current(unit: CombatantState, battle: BattleState) -> bool:
    return _air_currents(battle).get(unit.slot, 0) > 0


def make_pick(
    adventurer_id: str,
    *,
    slot: str,
    class_name: str,
    class_skill_id: Optional[str] = None,
    primary_weapon_id: Optional[str] = None,
    artifact_id: Optional[str] = None,
) -> dict:
    defn = ADVENTURERS_BY_ID[adventurer_id]
    primary_weapon = next(
        (
            weapon
            for weapon in defn.signature_weapons
            if weapon.id == (primary_weapon_id or defn.signature_weapons[0].id)
        ),
        None,
    )
    if primary_weapon is None:
        raise KeyError(f"Unknown primary weapon for {adventurer_id}: {primary_weapon_id}")
    secondary_weapon = next(weapon for weapon in defn.signature_weapons if weapon.id != primary_weapon.id)
    class_skill = None
    if class_skill_id is not None and class_skill_id in CLASS_SKILLS_BY_ID:
        class_skill = CLASS_SKILLS_BY_ID[class_skill_id]
    elif class_name in CLASS_SKILLS:
        class_skill = CLASS_SKILLS[class_name][0]
    else:
        class_skill = NO_CLASS_SKILL
    artifact = ARTIFACTS_BY_ID.get(artifact_id) if artifact_id else None
    return {
        "definition": defn,
        "slot": slot,
        "class_name": class_name,
        "class_skill": class_skill,
        "primary_weapon": primary_weapon,
        "secondary_weapon": secondary_weapon,
        "artifact": artifact,
    }


def create_combatant(
    defn: AdventurerDef,
    *,
    slot: str,
    class_name: str,
    class_skill,
    primary_weapon: WeaponDef,
    secondary_weapon: WeaponDef,
    artifact: Optional[ArtifactDef] = None,
) -> CombatantState:
    if artifact is not None and class_name not in artifact.attunement:
        raise ValueError(f"{artifact.name} cannot attune to {class_name}.")
    return CombatantState(
        defn=defn,
        slot=slot,
        class_name=class_name,
        class_skill=class_skill,
        primary_weapon=primary_weapon,
        secondary_weapon=secondary_weapon,
        artifact=artifact,
    )


def create_team(player_name: str, picks: Iterable[dict]) -> TeamState:
    members = []
    for pick in picks:
        members.append(
            create_combatant(
                pick["definition"],
                slot=pick["slot"],
                class_name=pick["class_name"],
                class_skill=pick["class_skill"],
                primary_weapon=pick["primary_weapon"],
                secondary_weapon=pick["secondary_weapon"],
                artifact=pick.get("artifact"),
            )
        )
    return TeamState(player_name=player_name, members=members)


def create_battle(team1: TeamState, team2: TeamState) -> BattleState:
    return BattleState(team1=team1, team2=team2)


def _team_contains_member(team: TeamState, actor: CombatantState) -> bool:
    return any(member is actor for member in team.members)


def team_for_actor(battle: BattleState, actor: CombatantState) -> TeamState:
    return battle.team1 if _team_contains_member(battle.team1, actor) else battle.team2


def player_num_for_actor(battle: BattleState, actor: CombatantState) -> int:
    return 1 if _team_contains_member(battle.team1, actor) else 2


def enemy_team_for_actor(battle: BattleState, actor: CombatantState) -> TeamState:
    return battle.team2 if _team_contains_member(battle.team1, actor) else battle.team1


def _intrinsic_bonus_swap(actor: CombatantState) -> bool:
    return actor.class_skill.id == "covert" or actor.defn.id == "the_green_knight"


def _intrinsic_bonus_switch(actor: CombatantState) -> bool:
    return actor.defn.id != "ashen_ella" and (
        actor.defn.id == "wayward_humbert" or actor.markers.get("bonus_switch_rounds", 0) > 0
    )


def _team_bonus_swap_available(actor: CombatantState, battle: BattleState) -> bool:
    team = team_for_actor(battle, actor)
    return team.markers.get("bonus_swap_rounds", 0) > 0 and team.markers.get("bonus_swap_used", 0) <= 0


def _artifact_ready(unit: CombatantState, artifact_id: str, battle: Optional[BattleState] = None) -> bool:
    if battle is not None:
        enemy_team = enemy_team_for_actor(battle, unit)
        enemy_front = enemy_team.frontline()
        if enemy_front is not None and enemy_front.defn.id == "storyweaver_anansi":
            return False
    return (
        unit.artifact is not None
        and unit.artifact.id == artifact_id
        and unit.artifact.reactive
        and unit.cooldowns.get(unit.artifact.spell.id, 0) <= 0
    )


def _has_seal_the_cave_cooldown(unit: CombatantState) -> bool:
    tracked = unit.markers.get("sealed_cave_effects")
    if not isinstance(tracked, set):
        return False
    return any(unit.cooldowns.get(effect_id, 0) > 0 for effect_id in tracked)


def _spend_reactive_artifact(unit: CombatantState, battle: BattleState):
    if unit.artifact is None:
        return
    unit.cooldowns[unit.artifact.spell.id] = unit.artifact.spell.cooldown
    _grant_meter(unit, battle, spell_like=True)


def _hp_change_text(before_hp: int, after_hp: int) -> str:
    return f"(HP {before_hp}->{after_hp})"


def _effect_source_label(
    actor: CombatantState,
    effect: ActiveEffect,
    *,
    source_kind: str,
    weapon: Optional[WeaponDef] = None,
) -> str:
    if source_kind == "strike":
        source_name = weapon.name if weapon is not None else effect.name
        return f"{actor.name}'s {source_name}"
    if source_kind == "ultimate":
        return f"{actor.name}'s Ultimate {effect.name}"
    if actor.artifact is not None and actor.artifact.spell.id == effect.id:
        return f"{actor.name}'s {actor.artifact.name} ({effect.name})"
    for source_weapon in (actor.primary_weapon, actor.secondary_weapon):
        if any(spell.id == effect.id for spell in source_weapon.spells):
            return f"{actor.name}'s {source_weapon.name} ({effect.name})"
    if any(spell.id == effect.id for spell in actor.markers.get("stolen_spells", [])):
        return f"{actor.name}'s stolen {effect.name}"
    if any(spell.id == effect.id for spell in actor.markers.get("granted_spells", [])):
        return f"{actor.name}'s granted {effect.name}"
    return f"{actor.name}'s {effect.name}"


def _heal_unit(
    unit: CombatantState,
    amount: int,
    battle: BattleState,
    *,
    source: Optional[CombatantState] = None,
    source_label: Optional[str] = None,
):
    if amount <= 0 or unit.ko:
        return 0
    if unit.has_status("burn_block_heal"):
        return 0
    enemy_team = enemy_team_for_actor(battle, unit)
    if unit.has_status("burn") and any(enemy.defn.id == "matchbox_liesl" and enemy.primary_weapon.id == "matchsticks" for enemy in enemy_team.alive()):
        return 0
    if unit.markers.get("guest_of_beast", 0):
        amount += 10
    if unit.has_status("heal_cut"):
        amount = math.ceil(amount * 0.5)
    healed = min(unit.max_hp - unit.hp, amount)
    if healed <= 0:
        return 0
    before_hp = unit.hp
    unit.hp += healed
    if source_label is None:
        battle.log_add(f"{unit.name} restores {healed} HP {_hp_change_text(before_hp, unit.hp)}.")
    else:
        battle.log_add(f"{source_label} restores {unit.name} for {healed} HP {_hp_change_text(before_hp, unit.hp)}.")
    team = team_for_actor(battle, unit)
    if any(ally.markers.get("cleansing_inferno_rounds", 0) > 0 for ally in team.alive()):
        for ally in team.alive():
            if ally is unit:
                continue
            mirrored = min(ally.max_hp - ally.hp, healed)
            if mirrored <= 0:
                continue
            mirrored_before = ally.hp
            ally.hp += mirrored
            battle.log_add(f"Cleansing Inferno restores {ally.name} for {mirrored} HP {_hp_change_text(mirrored_before, ally.hp)}.")
    return healed


def _offense_stat(unit: CombatantState, battle: Optional[BattleState] = None) -> int:
    return _formula_offense_stat(unit, battle)


def _formula_stat(
    unit: CombatantState,
    stat: str,
    battle: Optional[BattleState] = None,
    *,
    opponent: Optional[CombatantState] = None,
) -> int:
    # Open Sesame ignores combat-time stat bonuses and penalties for Ali Baba and whoever he is interacting with.
    if unit.defn.id == "ali_baba" or (opponent is not None and opponent.defn.id == "ali_baba"):
        base = getattr(unit.defn, stat)
        if unit.artifact is not None and unit.artifact.stat == stat:
            base += unit.artifact.amount
        if stat == "speed" and unit.slot in BACKLINE_SLOTS:
            base -= 30
        return max(1, base)
    return unit.get_stat(stat, battle)


def _formula_offense_stat(
    unit: CombatantState,
    battle: Optional[BattleState] = None,
    *,
    opponent: Optional[CombatantState] = None,
) -> int:
    if unit.defn.id == "maui_sunthief" and unit.primary_weapon.id == "ancestral_warclub":
        stat_value = _formula_stat(unit, "defense", battle, opponent=opponent)
    else:
        stat_value = _formula_stat(unit, "attack", battle, opponent=opponent)
    if battle is not None and _unit_in_air_current(unit, battle):
        enemy_team = enemy_team_for_actor(battle, unit)
        if any(enemy.defn.id == "witch_of_the_east" and enemy.primary_weapon.id == "zephyr" for enemy in enemy_team.alive()):
            if not (unit.defn.id == "ali_baba" or (opponent is not None and opponent.defn.id == "ali_baba")):
                stat_value = max(1, stat_value - 15)
    return stat_value


def _try_conquer_death(unit: CombatantState, battle: BattleState) -> bool:
    if unit.defn.id != "maui_sunthief":
        return False
    if unit.hp > 0:
        return False
    if unit.markers.get("conquer_death_used", 0) > 0:
        return False
    unit.hp = 1
    unit.ko = False
    unit.markers["conquer_death_used"] = 1
    battle.log_add(f"{unit.name}'s Conquer Death leaves them at 1 HP.")
    return True


def _try_prevent_fatal(unit: CombatantState, battle: BattleState, *, previous_hp: int) -> bool:
    if unit.hp > 0:
        return False
    if _artifact_ready(unit, "tarnhelm", battle):
        _spend_reactive_artifact(unit, battle)
        unit.hp = 1
        unit.ko = False
        battle.log_add(f"{unit.name}'s Tarnhelm leaves them at 1 HP.")
        return True
    if _artifact_ready(unit, "enchanted_lamp", battle) and previous_hp > math.ceil(unit.max_hp * 0.5):
        _spend_reactive_artifact(unit, battle)
        unit.hp = 1
        unit.ko = False
        battle.log_add(f"{unit.name}'s Dying Wish leaves them at 1 HP.")
        return True
    team = team_for_actor(battle, unit)
    if team.markers.get("evermore_used", 0) <= 0:
        evermore_owner = next(
            (
                ally
                for ally in team.alive()
                if ally.defn.id == "scheherazade_dawns_ransom" and ally.primary_weapon.id == "lamp_of_infinity"
            ),
            None,
        )
        if evermore_owner is not None:
            team.markers["evermore_used"] = 1
            unit.hp = 1
            unit.ko = False
            battle.log_add(f"{evermore_owner.name}'s Evermore leaves {unit.name} at 1 HP.")
            return True
    return _try_conquer_death(unit, battle)


def _all_alive_units(battle: BattleState) -> List[CombatantState]:
    return battle.team1.alive() + battle.team2.alive()


def determine_initiative_order(battle: BattleState) -> List[CombatantState]:
    order = list(battle.team1.alive()) + list(battle.team2.alive())
    order.sort(
        key=lambda unit: (
            -_initiative_speed(battle, unit),
            player_num_for_actor(battle, unit),
            SLOT_PRIORITY[unit.slot],
        )
    )
    for unit in list(order):
        if unit.defn.id != "reynard_lupine_trickster":
            continue
        target_ref = unit.markers.get("glowing_trail_target")
        if (
            not isinstance(target_ref, tuple)
            or len(target_ref) != 2
            or target_ref[0] not in {1, 2}
        ):
            continue
        target_team_num = int(target_ref[0])
        target_id = str(target_ref[1])
        target = next(
            (
                candidate
                for candidate in order
                if candidate is not unit
                and player_num_for_actor(battle, candidate) == target_team_num
                and candidate.defn.id == target_id
            ),
            None,
        )
        if target is None:
            continue
        unit_index = order.index(unit)
        target_index = order.index(target)
        if unit_index > target_index:
            order.pop(unit_index)
            target_index = order.index(target)
            order.insert(target_index, unit)
    battle.initiative_order = order
    return order


def start_round(battle: BattleState) -> List[CombatantState]:
    battle.team1.markers["art_of_the_deal_triggered"] = 0
    battle.team2.markers["art_of_the_deal_triggered"] = 0
    for unit in battle.team1.alive() + battle.team2.alive():
        _sync_position_locked_weapon(unit)
        unit.markers["acted_this_round"] = 0
        unit.markers["struck_this_round"] = 0
        unit.markers["swapped_this_round"] = 0
        unit.markers["spells_cast_this_round"] = 0
        unit.markers["cast_artifact_spell_this_round"] = 0
        if battle.round_num == 1 and unit.defn.id == "witch_of_the_east":
            _set_air_current(battle, unit.slot, 2)
    battle.team1.markers["crumb_picked_round"] = 0
    battle.team2.markers["crumb_picked_round"] = 0
    order = determine_initiative_order(battle)
    expanded_order: List[CombatantState] = []
    for unit in order:
        expanded_order.append(unit)
        extra_turns = unit.markers.pop("rabbit_hole_extra_rounds", 0)
        for _ in range(max(0, extra_turns)):
            expanded_order.append(unit)
    battle.initiative_order = expanded_order
    apply_start_of_round_effects(battle)
    return expanded_order


def apply_start_of_round_effects(battle: BattleState):
    for unit in battle.team1.alive() + battle.team2.alive():
        if unit.markers.get("cant_strike_rounds", 0) > 0:
            battle.log_add(f"{unit.name} cannot Strike this round.")
    for team in (battle.team1, battle.team2):
        enemy_team = battle.team2 if team is battle.team1 else battle.team1
        for unit in team.alive():
            if unit.defn.id != "briar_rose":
                continue
            rooted = [
                enemy
                for enemy in enemy_team.alive()
                if enemy.has_status("root") and not enemy.has_status("root_immunity")
            ]
            if not rooted:
                continue
            target = min(rooted, key=lambda enemy: enemy.hp)
            target.markers["cant_act_rounds"] = 1
            if unit.markers.get("falling_kingdom_rounds", 0) > 0:
                battle.log_add(f"Curse of Sleeping stops {target.name} from acting.")
            else:
                target.remove_status("root")
                target.add_status("root_immunity", 2)
                battle.log_add(f"Curse of Sleeping removes Root from {target.name} and they cannot act.")


def queue_strike(actor: CombatantState, target: CombatantState):
    actor.queued_action = _normalize_queued_action(actor, {"type": "strike", "target": target})


def queue_spell(actor: CombatantState, effect: ActiveEffect, target: Optional[CombatantState] = None, battle: Optional[BattleState] = None):
    action = {"type": "spell", "effect": effect, "target": target}
    if battle is not None and effect.target == "any" and target is not None:
        action["target_team_num"] = player_num_for_actor(battle, target)
    actor.queued_action = _normalize_queued_action(actor, action)


def queue_switch(actor: CombatantState):
    actor.queued_action = {"type": "switch"}


def queue_swap(actor: CombatantState, ally: CombatantState):
    actor.queued_action = _normalize_queued_action(actor, {"type": "swap", "target": ally})


def queue_skip(actor: CombatantState):
    actor.queued_action = {"type": "skip"}


def queue_ultimate(actor: CombatantState, target: Optional[CombatantState] = None, battle: Optional[BattleState] = None):
    action = {"type": "ultimate", "effect": actor.defn.ultimate, "target": target}
    if battle is not None and actor.defn.ultimate.target == "any" and target is not None:
        action["target_team_num"] = player_num_for_actor(battle, target)
    actor.queued_action = _normalize_queued_action(
        actor,
        action,
    )


def queue_bonus_action(actor: CombatantState, action: dict):
    actor.queued_bonus_action = _normalize_queued_action(actor, action)


def _queued_target_side(actor: CombatantState, action: dict) -> Optional[str]:
    action_type = action.get("type")
    if action_type == "strike":
        return "enemy"
    if action_type == "swap":
        return "ally"
    if action_type in {"spell", "ultimate"}:
        effect = action.get("effect")
        if effect is None and action_type == "ultimate":
            effect = actor.defn.ultimate
        if effect is None:
            return None
        if effect.target in {"enemy", "ally", "self", "any"}:
            return effect.target
    return None


def _normalize_queued_action(actor: CombatantState, action: dict) -> dict:
    normalized = dict(action)
    target = normalized.get("target")
    if target is None:
        return normalized
    side = normalized.get("target_side") or _queued_target_side(actor, normalized)
    if side in {"ally", "enemy"} and isinstance(target, CombatantState):
        normalized["target_side"] = side
        normalized["target_slot"] = target.slot
    elif side == "any" and isinstance(target, CombatantState):
        normalized["target_side"] = side
        normalized["target_slot"] = target.slot
    elif side == "self":
        normalized["target_side"] = side
        normalized["target"] = actor
        normalized.pop("target_slot", None)
    return normalized


def _resolve_queued_target(actor: CombatantState, action: dict, battle: BattleState) -> Optional[CombatantState]:
    target = action.get("target")
    side = action.get("target_side")
    target_slot = action.get("target_slot")
    if side == "self":
        return actor
    if side == "any":
        target_team_num = action.get("target_team_num")
        target_slot = action.get("target_slot")
        if target_team_num not in {1, 2} or target_slot is None:
            return target
        return battle.get_team(target_team_num).get_slot(target_slot)
    if side not in {"ally", "enemy"} or target_slot is None:
        return target
    team = team_for_actor(battle, actor) if side == "ally" else enemy_team_for_actor(battle, actor)
    return team.get_slot(target_slot)


def _contains_target(candidates: List[CombatantState], target: Optional[CombatantState]) -> bool:
    if target is None:
        return False
    return any(candidate is target for candidate in candidates)


def resolve_action_phase(battle: BattleState):
    if not battle.initiative_order:
        determine_initiative_order(battle)
    for actor in list(battle.initiative_order):
        if actor.ko:
            continue
        action = actor.queued_action
        actor.queued_action = None
        if action is None:
            continue
        resolve_action(actor, action, battle)
        if battle.winner is not None:
            return


def resolve_bonus_phase(battle: BattleState):
    if not battle.initiative_order:
        determine_initiative_order(battle)
    for actor in list(battle.initiative_order):
        if actor.ko:
            continue
        action = actor.queued_bonus_action
        actor.queued_bonus_action = None
        if action is None:
            continue
        resolve_action(actor, action, battle, is_bonus=True)
        if battle.winner is not None:
            return


def resolve_round(battle: BattleState):
    start_round(battle)
    resolve_action_phase(battle)
    if battle.winner is None:
        resolve_bonus_phase(battle)
    if battle.winner is None:
        end_round(battle)


def resolve_action(actor: CombatantState, action: dict, battle: BattleState, *, is_bonus: bool = False):
    _sync_position_locked_weapon(actor)
    if actor.markers.get("cant_act_rounds", 0) > 0:
        battle.log_add(f"{actor.name} cannot act.")
        return
    if _fated_duel_blocks(actor, battle):
        battle.log_add(f"{actor.name} is locked out by Fated Duel.")
        return
    action_type = action["type"]
    if is_bonus:
        if action_type == "swap":
            if not (_intrinsic_bonus_swap(actor) or _team_bonus_swap_available(actor, battle)):
                battle.log_add(f"{actor.name} has no bonus Swap available.")
                return
            if not _intrinsic_bonus_swap(actor) and _team_bonus_swap_available(actor, battle):
                team_for_actor(battle, actor).markers["bonus_swap_used"] = 1
        elif action_type == "switch" and not _intrinsic_bonus_switch(actor):
            battle.log_add(f"{actor.name} has no bonus Switch available.")
            return
        elif action_type in {"spell", "ultimate"}:
            has_spell_bonus = actor.markers.get("spell_bonus_rounds", 0) > 0
            has_artifact_bonus = False
            if action_type == "spell":
                bonus_effect = actor.markers.get("artifact_bonus_spell_effect")
                action_effect = action.get("effect")
                has_artifact_bonus = (
                    actor.markers.get("artifact_bonus_spell_rounds", 0) > 0
                    and bonus_effect is not None
                    and action_effect is not None
                    and action_effect.id == bonus_effect.id
                )
            if not has_spell_bonus and not has_artifact_bonus:
                battle.log_add(f"{actor.name} has no bonus Spell available.")
                return
    if action_type == "skip":
        battle.log_add(f"{actor.name} skips.")
        return
    if action_type == "switch":
        do_switch(actor, battle)
        return
    resolved_target = _resolve_queued_target(actor, action, battle)
    if action_type == "swap":
        do_swap(actor, resolved_target, battle, is_bonus=is_bonus)
        return
    if action_type == "strike":
        resolve_strike(actor, resolved_target, battle)
        return
    if action_type == "spell":
        resolve_spell(actor, action["effect"], resolved_target, battle)
        return
    if action_type == "ultimate":
        resolve_ultimate(actor, action["effect"], resolved_target, battle)
        return
    raise ValueError(f"Unknown action type: {action_type}")


def do_switch(actor: CombatantState, battle: BattleState):
    if actor.defn.id == "ashen_ella":
        battle.log_add(f"{actor.name} cannot switch weapons.")
        return
    flower_arrows_active = actor.defn.id == "kama_the_honeyed" and actor.primary_weapon.id == "sugarcane_bow"
    odysseus_bow_active = actor.defn.id == "odysseus_the_nobody" and actor.primary_weapon.id == "beggars_greatbow"
    forty_thieves_active = actor.markers.get("forty_thieves_rounds", 0) > 0
    actor.primary_weapon, actor.secondary_weapon = actor.secondary_weapon, actor.primary_weapon
    for weapon in actor.defn.signature_weapons:
        actor.cooldowns[weapon.strike.id] = 0
        should_reload = not forty_thieves_active and not (
            (flower_arrows_active and weapon.id == "sugarcane_bow")
            or (odysseus_bow_active and weapon.id == "beggars_greatbow")
        )
        if should_reload:
            actor.ammo_remaining[weapon.id] = weapon.ammo
        for spell in weapon.spells:
            actor.cooldowns[spell.id] = 0
    actor.markers.pop("sealed_cave_effects", None)
    actor.markers["switched_this_round"] = 1
    if actor.class_skill.id == "armed":
        actor.markers["free_ranged_after_switch"] = 1
    if actor.class_skill.id == "archmage":
        actor.markers["next_spell_no_cooldown"] = 1
    if actor.defn.id == "storyweaver_anansi" and actor.primary_weapon.id == "the_sword":
        actor.add_buff("attack", 15, 2)
        actor.add_debuff("speed", 15, 2)
    if actor.defn.id == "odysseus_the_nobody":
        actor.markers["barbed_arrows_ready"] = 1
    battle.log_add(f"{actor.name} switches weapons to {actor.primary_weapon.name}.")


def do_swap(actor: CombatantState, ally: Optional[CombatantState], battle: BattleState, *, is_bonus: bool = False):
    if ally is None or ally is actor or ally.ko or team_for_actor(battle, ally) != team_for_actor(battle, actor):
        battle.log_add(f"{actor.name} cannot Swap.")
        return
    if actor.has_status("root"):
        battle.log_add(f"{actor.name} is Rooted and cannot Swap.")
        return
    if actor.markers.get("polymorph_rounds", 0) > 0:
        battle.log_add(f"{actor.name} cannot Swap while Polymorphed.")
        return
    if ally.markers.get("polymorph_rounds", 0) > 0:
        battle.log_add(f"{ally.name} cannot Swap while Polymorphed.")
        return
    actor_original_slot = actor.slot
    ally_original_slot = ally.slot
    actor.slot, ally.slot = ally.slot, actor.slot
    actor.markers["swapped_this_round"] = 1
    ally.markers["swapped_this_round"] = 1
    _sync_position_locked_weapon(actor)
    _sync_position_locked_weapon(ally)
    for participant, partner in ((actor, ally), (ally, actor)):
        if _artifact_ready(participant, "cornucopia", battle):
            _spend_reactive_artifact(participant, battle)
            _heal_unit(participant, 25, battle)
            _heal_unit(partner, 25, battle)
    if actor.class_skill.id == "vigilant":
        actor.add_status("guard", 2)
    if ally.class_skill.id == "vigilant":
        ally.add_status("guard", 2)
    team = team_for_actor(battle, actor)
    for member in team.alive():
        if member.defn.id == "sir_roland" and member.primary_weapon.id == "pure_silver_shield":
            actor.add_status("guard", 2)
            ally.add_status("guard", 2)
    for participant in (actor, ally):
        crumb_slots = team.markers.get("crumb_slots", set())
        if participant.slot in crumb_slots:
            _heal_unit(participant, 50, battle)
            team.markers["crumb_picked_round"] = 1
            crumb_slots = set(crumb_slots)
            crumb_slots.discard(participant.slot)
            team.markers["crumb_slots"] = crumb_slots
    for participant, partner in ((actor, ally), (ally, actor)):
        if participant.defn.id == "the_good_beast" and participant.markers.get("guest_unit") is None:
            participant.markers["guest_unit"] = partner
            partner.markers["guest_of_beast"] = 1
        if participant.defn.id == "lady_of_reflections":
            participant.remove_status("reflecting_pool")
            participant.add_status("reflecting_pool", 2)
    if actor.defn.id == "sir_roland" and actor.slot == SLOT_FRONT:
        actor.markers["silver_aegis_ready"] = 1
    if ally.defn.id == "sir_roland" and ally.slot == SLOT_FRONT:
        ally.markers["silver_aegis_ready"] = 1
    for participant, original_slot in ((actor, actor_original_slot), (ally, ally_original_slot)):
        if participant.defn.id == "odysseus_the_nobody":
            participant.add_buff("attack", 15, 2)
        if participant.defn.id == "witch_of_the_east":
            _set_air_current(battle, participant.slot, 2)
        enemy_team = enemy_team_for_actor(battle, participant)
        for enemy in enemy_team.alive():
            if enemy.defn.id == "tam_lin_thornbound" and enemy.primary_weapon.id == "butterfly_knife":
                if original_slot == enemy.slot or participant.slot == enemy.slot:
                    participant.markers["bargain_rounds"] = 2
    battle.log_add(f"{actor.name} swaps positions with {ally.name}.")
    for enemy in enemy_team_for_actor(battle, actor).alive():
        if enemy.defn.id == "briar_rose" and enemy.primary_weapon.id == "thorn_snare":
            actor.add_status("root", 2)
            ally.add_status("root", 2)
    for participant in (actor, ally):
        enemy_team = enemy_team_for_actor(battle, participant)
        for enemy in enemy_team.alive():
            if enemy.defn.id == "red_blanchette" and enemy.primary_weapon.id == "stomach_splitter" and participant.has_status("mark"):
                followup = replace(enemy.primary_weapon.strike, ignore_targeting=True)
                _resolve_effect(enemy, followup, participant, battle, source_kind="strike", weapon=enemy.primary_weapon)
    determine_initiative_order(battle)


def _prepare_strike_effect(
    actor: CombatantState,
    target: CombatantState,
    battle: BattleState,
    weapon: WeaponDef,
    effect: ActiveEffect,
) -> ActiveEffect:
    power = effect.power
    cooldown = effect.cooldown
    ammo_cost = effect.ammo_cost
    spread = effect.spread
    ignore_targeting = effect.ignore_targeting
    lifesteal = effect.lifesteal
    recoil = effect.recoil
    bonus_power_if_status = effect.bonus_power_if_status
    bonus_power = effect.bonus_power
    target_statuses = list(effect.target_statuses)

    if effect.special == "stitch_in_time_strike" and actor.markers.get("swapped_this_round", 0) > 0:
        power += 20
    if actor.markers.pop("blood_diamond_ready", 0):
        power += 25
    if effect.special == "bonus_vs_backline_30" and target.slot != SLOT_FRONT:
        power += 30
    if effect.special == "across_bonus_15" and target.slot == actor.slot:
        power += 15
    if effect.special == "lane_bonus_15" and target.slot == actor.slot:
        power += 15
    if effect.special == "guest_bonus" and actor.markers.get("guest_last_attacker") is target:
        power += 15
    if effect.special == "skull_lantern":
        if any(ally.has_status("guard") for ally in team_for_actor(battle, actor).alive()):
            power += 15
    if effect.special == "wooden_club":
        power += actor.markers.get("malice", 0) * 5
    if effect.special == "fang_bonus_vs_penalty":
        if any(debuff.duration > 0 for debuff in target.debuffs):
            power += 15
    if effect.special == "lightning_rod" and target.has_status("shock"):
        ammo_cost = 0
    if effect.special == "golden_fiddle" and target.has_status("shock"):
        cooldown = 0
        target_statuses.append(StatusInstance(kind="root", duration=2))
        target_statuses.append(StatusInstance(kind="spotlight", duration=2))
    if effect.special == "crumb_shot":
        if team_for_actor(battle, actor).markers.get("crumb_picked_round", 0) > 0:
            power += 50
    if effect.special == "mirror_blade":
        copied = actor.markers.get("mirror_blade_effect")
        if copied is not None:
            power = copied.get("power", power)
            target_statuses.extend(copied.get("target_statuses", []))
    if effect.special == "mortar_mortar" and actor.markers.get("bricklayer_triggered_this_round", 0) > 0:
        ammo_cost = 0
    if effect.special == "the_stinger" and target.has_status("spotlight"):
        target_statuses.append(StatusInstance(kind="shock", duration=2))
        actor.markers["flower_arrow_pickup_pending"] = actor.markers.get("flower_arrow_pickup_pending", 0) + 1
    if actor.defn.id == "odysseus_the_nobody" and weapon.kind == "melee" and actor.markers.pop("barbed_arrows_ready", 0):
        power += target.markers.get("odysseus_arrow_count", 0) * 5
        actor.ammo_remaining["beggars_greatbow"] = next(
            weapon_def.ammo for weapon_def in actor.defn.signature_weapons if weapon_def.id == "beggars_greatbow"
        )
    if actor.markers.get("shotgun_combusted", 0) > 0 and weapon.id == "convicted_shotgun":
        power += 25
        recoil = max(recoil, 0.5)
        ammo_cost = max(1, ammo_cost * 2)
    if actor.markers.pop("vine_snare_ready", 0):
        ammo_cost = 0
        if target.has_status("root_immunity"):
            target.remove_status("root_immunity")
    if actor.markers.get("crowstorm_rounds", 0) > 0 and weapon.kind == "magic":
        cooldown = 0

    next_strike_bonus = actor.markers.pop("next_strike_bonus_power", 0)
    if next_strike_bonus:
        power += next_strike_bonus
    next_magic_bonus = actor.markers.get("next_magic_strike_bonus", 0)
    if next_magic_bonus and weapon.kind == "magic":
        power += 15
        actor.markers.pop("next_magic_strike_bonus", None)
    next_melee_bonus = actor.markers.get("next_melee_bonus_power", 0)
    if next_melee_bonus and weapon.kind == "melee":
        power += 10
        target_statuses.append(StatusInstance(kind="weaken", duration=2))
        actor.markers.pop("next_melee_bonus_power", None)
    if actor.markers.pop("next_strike_shock", 0):
        power += 10
        target_statuses.append(StatusInstance(kind="shock", duration=2))
    if actor.markers.pop("next_strike_expose", 0):
        target_statuses.append(StatusInstance(kind="expose", duration=2))
    if actor.markers.pop("next_strike_spotlight", 0):
        power += 10
        target_statuses.append(StatusInstance(kind="spotlight", duration=2))
    if actor.markers.pop("next_strike_spread", 0):
        power += 10
        spread = True
    if actor.markers.pop("next_strike_lifesteal", 0):
        lifesteal = max(lifesteal, 0.30)
    if actor.markers.pop("next_strike_ignore_all_defense", 0):
        actor.markers["ignore_defense_for_strike"] = 100
    if actor.markers.get("next_ranged_ignore_targeting_no_ammo", 0) and weapon.kind == "ranged":
        ignore_targeting = True
        ammo_cost = 0
        actor.markers.pop("next_ranged_ignore_targeting_no_ammo", None)
    if actor.markers.get("mass_hysteria_rounds", 0) > 0:
        spread = True
        ignore_targeting = True
        cooldown = 0
    if actor.markers.get("gaze_of_love_rounds", 0) > 0 and weapon.kind == "ranged" and target.has_status("spotlight"):
        ammo_cost = 0
    if actor.markers.get("seeking_yarn_rounds", 0) > 0 and target.slot == actor.slot:
        ammo_cost = 0
    if actor.markers.pop("elixir_of_life_ready", 0):
        lifesteal = max(lifesteal, 0.10)
        ammo_cost = 0
        cooldown = 0
    guiding_doll = target.markers.get("guiding_doll_buff")
    if isinstance(guiding_doll, dict):
        owner_team_num = guiding_doll.get("team_num")
        owner_id = guiding_doll.get("owner_id")
        if owner_team_num == player_num_for_actor(battle, actor) and owner_id != actor.defn.id:
            power += 25
            lifesteal = max(lifesteal, 0.25)
            actor.markers["guiding_doll_lifesteal_bonus"] = int(guiding_doll.get("heal_bonus", 0))
            target.markers.pop("guiding_doll_buff", None)
    if actor.markers.get("wolf_unchained_rounds", 0) > 0 and actor.defn.id == "red_blanchette":
        lifesteal = max(lifesteal, 0.30)
    if actor.defn.id == "red_blanchette" and actor.hp <= math.ceil(actor.max_hp * 0.5):
        lifesteal = max(lifesteal, 0.30 if actor.markers.get("wolf_unchained_rounds", 0) > 0 else 0.15)
    if actor.markers.get("witchs_blessing_rounds", 0) > 0 and team_for_actor(battle, actor) is not team_for_actor(battle, target):
        lifesteal = max(lifesteal, 0.25)
    if actor.markers.pop("jovial_shot_ready", 0):
        power = max(power, effect.power) * 2
        recoil = max(recoil, 1.0)
    return replace(
        effect,
        power=power,
        cooldown=cooldown,
        ammo_cost=ammo_cost,
        spread=spread,
        ignore_targeting=ignore_targeting,
        lifesteal=lifesteal,
        recoil=recoil,
        bonus_power_if_status=bonus_power_if_status,
        bonus_power=bonus_power,
        target_statuses=tuple(target_statuses),
    )


def resolve_strike(actor: CombatantState, target: Optional[CombatantState], battle: BattleState):
    if actor.markers.get("cant_strike_rounds", 0) > 0:
        battle.log_add(f"{actor.name} cannot Strike right now.")
        return
    weapon = actor.primary_weapon
    if _is_ella_backline(actor):
        _sync_position_locked_weapon(actor)
        weapon = actor.primary_weapon
    effect = weapon.strike
    if actor.cooldowns.get(effect.id, 0) > 0:
        battle.log_add(f"{weapon.name} is on cooldown.")
        return
    if weapon.ammo > 0 and actor.ammo_remaining.get(weapon.id, weapon.ammo) <= 0:
        battle.log_add(f"{weapon.name} is out of ammo.")
        return
    if target is not None and weapon.kind == "melee" and _artifact_ready(target, "swan_cloak", battle) and not target.has_status("root"):
        target_team = team_for_actor(battle, target)
        preferred = []
        if target.slot == SLOT_FRONT:
            preferred = [target_team.get_slot(SLOT_BACK_LEFT), target_team.get_slot(SLOT_BACK_RIGHT)]
        else:
            preferred = [target_team.frontline(), target_team.get_slot(SLOT_BACK_LEFT), target_team.get_slot(SLOT_BACK_RIGHT)]
        partner = next(
            (
                candidate
                for candidate in preferred
                if candidate is not None and candidate is not target and not candidate.ko
            ),
            None,
        )
        if partner is None:
            partner = next((ally for ally in target_team.alive() if ally is not target), None)
        if partner is not None:
            _spend_reactive_artifact(target, battle)
            do_swap(target, partner, battle)
    prepared_effect = _prepare_strike_effect(actor, target, battle, weapon, effect) if target is not None else effect
    if not _contains_target(get_legal_targets(battle, actor, effect=prepared_effect, weapon=weapon), target):
        battle.log_add(f"{actor.name} has no legal Strike on that target.")
        return
    _resolve_effect(actor, prepared_effect, target, battle, source_kind="strike", weapon=weapon)
    actor.markers.pop("guiding_doll_lifesteal_bonus", None)
    if weapon.ammo > 0 and not actor.markers.pop("free_ranged_after_switch", 0):
        actor.ammo_remaining[weapon.id] = max(0, actor.ammo_remaining.get(weapon.id, weapon.ammo) - prepared_effect.ammo_cost)
    flower_arrow_pickups = actor.markers.pop("flower_arrow_pickup_pending", 0)
    if flower_arrow_pickups > 0:
        sugarcane = next((weapon_def for weapon_def in actor.defn.signature_weapons if weapon_def.id == "sugarcane_bow"), None)
        if sugarcane is not None and sugarcane.ammo > 0:
            current = actor.ammo_remaining.get("sugarcane_bow", sugarcane.ammo)
            actor.ammo_remaining["sugarcane_bow"] = min(sugarcane.ammo, current + flower_arrow_pickups)
    if prepared_effect.cooldown > 0:
        if not (actor.defn.id == "pinocchio_cursed_puppet" and weapon.id == "string_cutter" and actor.markers.get("malice", 0) >= 3):
            cooldown = prepared_effect.cooldown
            if weapon.kind == "magic" and actor.markers.get("spells_cast_this_round", 0) > 0:
                enemy_team = enemy_team_for_actor(battle, actor)
                if any(enemy.defn.id == "scheherazade_dawns_ransom" for enemy in enemy_team.alive()):
                    cooldown += 1
            actor.cooldowns[effect.id] = cooldown
    if weapon.kind == "magic":
        actor.markers["spells_cast_this_round"] = actor.markers.get("spells_cast_this_round", 0) + 1
    if actor.defn.id == "rapunzel_the_golden" and weapon.kind == "melee" and target is not None and target.slot != SLOT_FRONT:
        actor.markers["flowing_locks_ready"] = 0
    if actor.defn.id == "wayward_humbert" and weapon.id == "convicted_shotgun":
        actor.markers["shotgun_combusted"] = 1
    _grant_meter(actor, battle, spell_like=weapon.kind == "magic", is_strike=True)
    actor.markers["acted_this_round"] = 1
    actor.markers["struck_this_round"] = 1


def resolve_spell(actor: CombatantState, effect: ActiveEffect, target: Optional[CombatantState], battle: BattleState):
    if _is_ella_backline(actor):
        battle.log_add(f"{actor.name} cannot cast Spells from the backline.")
        return
    bonus_artifact_effect = actor.markers.get("artifact_bonus_spell_effect")
    is_bonus_artifact_spell = (
        bonus_artifact_effect is not None
        and actor.markers.get("artifact_bonus_spell_rounds", 0) > 0
        and effect.id == bonus_artifact_effect.id
    )
    if effect not in actor.active_spells() and not is_bonus_artifact_spell:
        battle.log_add(f"{actor.name} cannot access {effect.name}.")
        return
    if (
        actor.artifact is not None
        and effect.id == actor.artifact.spell.id
        and (actor.has_status("burn") or _has_seal_the_cave_cooldown(actor))
    ):
        enemy_team = enemy_team_for_actor(battle, actor)
        no_escape_active = any(enemy.defn.id == "ali_baba" and enemy.primary_weapon.id == "jar_of_oil" for enemy in enemy_team.alive())
        if no_escape_active:
            battle.log_add(f"{actor.name} cannot cast their Artifact Spell while Burned or with cooldowns affected by Seal the Cave.")
            return
    if actor.cooldowns.get(effect.id, 0) > 0:
        battle.log_add(f"{effect.name} is on cooldown.")
        return
    paradox_swap_target = target if effect.target == "ally" and target is not None and target is not actor else None
    legal_targets = get_legal_targets(battle, actor, effect=effect)
    if effect.target not in {"none", "self"} and not _contains_target(legal_targets, target):
        battle.log_add(f"{effect.name} has no legal target.")
        return
    if effect.target == "self":
        target = actor
    elif target is not None and _artifact_ready(target, "magic_mirror", battle) and effect.target in {"enemy", "ally"}:
        _spend_reactive_artifact(target, battle)
        battle.log_add(f"{target.name}'s Magic Mirror reflects {effect.name}.")
        target = actor
    _resolve_effect(actor, effect, target, battle, source_kind="spell")
    if paradox_swap_target is not None and _artifact_ready(actor, "paradox_rings", battle):
        _spend_reactive_artifact(actor, battle)
        do_swap(actor, paradox_swap_target, battle)
    if effect.power <= 0:
        enemy_team = enemy_team_for_actor(battle, actor)
        for enemy in enemy_team.alive():
            if enemy.defn.id != "sea_wench_asha":
                continue
            stolen = list(enemy.markers.get("stolen_spells", []))
            if all(existing.id != effect.id for existing in stolen):
                stolen.append(effect)
            enemy.markers["stolen_spells"] = stolen
            enemy.markers["stolen_voices_rounds"] = 2
    tea_party_active = actor.markers.get("tea_party_rounds", 0) > 0
    if actor.defn.id == "pinocchio_cursed_puppet" and actor.primary_weapon.id == "string_cutter" and actor.markers.get("malice", 0) >= 3:
        actor.markers["next_spell_no_cooldown"] = 1
    if effect.cooldown > 0 and not tea_party_active and not actor.markers.pop("next_spell_no_cooldown", 0):
        cooldown = effect.cooldown
        if actor.markers.get("spells_cast_this_round", 0) > 0:
            enemy_team = enemy_team_for_actor(battle, actor)
            if any(enemy.defn.id == "scheherazade_dawns_ransom" for enemy in enemy_team.alive()):
                cooldown += 1
        actor.cooldowns[effect.id] = cooldown
    if is_bonus_artifact_spell:
        actor.markers["artifact_bonus_spell_rounds"] = 0
        actor.markers.pop("artifact_bonus_spell_effect", None)
    if actor.artifact is not None and effect.id == actor.artifact.spell.id:
        actor.markers["cast_artifact_spell_this_round"] = 1
    _grant_meter(actor, battle, spell_like=True)
    actor.markers["spells_cast_this_round"] = actor.markers.get("spells_cast_this_round", 0) + 1
    if actor.defn.id == "rapunzel_the_golden":
        actor.markers["flowing_locks_ready"] = 1
    actor.markers["acted_this_round"] = 1


def resolve_ultimate(actor: CombatantState, effect: ActiveEffect, target: Optional[CombatantState], battle: BattleState):
    team = team_for_actor(battle, actor)
    if team.ultimate_meter < ULTIMATE_METER_MAX:
        battle.log_add(f"{actor.name} cannot use {effect.name} yet.")
        return
    legal_targets = get_legal_targets(battle, actor, effect=effect)
    if effect.target not in {"none", "self"} and not _contains_target(legal_targets, target):
        battle.log_add(f"{effect.name} has no legal target.")
        return
    if effect.target == "self":
        target = actor
    if _artifact_ready(actor, "goose_quill", battle):
        _spend_reactive_artifact(actor, battle)
        team.ultimate_meter = GOOSE_QUILL_RETAINED_METER
    else:
        team.ultimate_meter = 0
    _resolve_effect(actor, effect, target, battle, source_kind="ultimate")
    battle.log_add(f"{actor.name} unleashes {effect.name}.")
    actor.markers["acted_this_round"] = 1
    team.markers["ultimates_cast"] = team.markers.get("ultimates_cast", 0) + 1
    if team.markers["ultimates_cast"] >= ULTIMATE_WIN_COUNT:
        battle.winner = player_num_for_actor(battle, actor)
        suffix = "rd" if ULTIMATE_WIN_COUNT == 3 else "th"
        battle.log_add(f"{team.player_name} wins by casting their {ULTIMATE_WIN_COUNT}{suffix} Ultimate Spell.")


def get_legal_targets(
    battle: BattleState,
    actor: CombatantState,
    *,
    effect: Optional[ActiveEffect] = None,
    weapon: Optional[WeaponDef] = None,
) -> List[CombatantState]:
    effect = effect or (weapon.strike if weapon else None)
    if effect is None:
        return []
    team = team_for_actor(battle, actor)
    enemy = enemy_team_for_actor(battle, actor)

    if effect.target == "none":
        return []
    if effect.target == "self":
        return [actor]
    if effect.target == "any":
        return [unit for unit in (_all_alive_units(battle)) if _is_targetable(actor, unit) or unit is actor]
    if effect.target == "ally":
        return team.alive()

    taunt_source = actor.markers.get("taunt_source")
    if actor.has_status("taunt") and taunt_source is not None and not taunt_source.ko:
        return [taunt_source]
    if effect.ignore_targeting or actor.markers.get("ignore_targeting_strikes", 0) > 0:
        return [unit for unit in enemy.alive() if _is_targetable(actor, unit)]

    if weapon is not None and weapon.kind == "melee":
        if actor.slot != SLOT_FRONT:
            return []
        targets = []
        front = enemy.frontline()
        if front is not None:
            targets.append(front)
        targets.extend(member for member in enemy.alive() if member.slot != SLOT_FRONT and member.has_status("spotlight"))
        if actor.defn.id == "lucky_constantine":
            targets.extend(member for member in enemy.alive() if member.slot != SLOT_FRONT and member.has_status("expose"))
        if actor.defn.id == "rapunzel_the_golden" and actor.markers.get("flowing_locks_ready", 1) > 0:
            targets.extend(member for member in enemy.alive() if member.slot != SLOT_FRONT)
        if actor.class_skill.id == "assassin":
            targets.extend(
                member
                for member in enemy.alive()
                if member.markers.get("acted_this_round", 0) <= 0 and member.markers.get("swapped_this_round", 0) <= 0
            )
        if actor.defn.id == "storyweaver_anansi" and actor.primary_weapon.id == "the_sword":
            targets.extend(
                member
                for member in enemy.alive()
                if member.slot != SLOT_FRONT and member.markers.get("cast_artifact_spell_last_round", 0) > 0
            )
        return [unit for unit in _dedupe(targets) if _is_targetable(actor, unit)]

    targets = []
    front = enemy.frontline()
    if front is not None:
        targets.append(front)
    across = enemy.get_slot(actor.slot)
    if across is not None:
        targets.append(across)
    return [unit for unit in _dedupe(targets) if _is_targetable(actor, unit)]


def _dedupe(targets: Iterable[CombatantState]) -> List[CombatantState]:
    seen = set()
    result = []
    for target in targets:
        if id(target) in seen:
            continue
        seen.add(id(target))
        result.append(target)
    return result


def _fated_duel_blocks(actor: CombatantState, battle: BattleState) -> bool:
    active_lanes = battle.markers.get("fated_duel_lanes", {})
    return bool(active_lanes) and actor.slot not in active_lanes


def _modify_incoming_damage(
    source: CombatantState,
    target: CombatantState,
    damage: int,
    battle: BattleState,
    *,
    source_kind: str,
    weapon: Optional[WeaponDef],
) -> int:
    if damage <= 0:
        return damage
    if source_kind == "strike" and _artifact_ready(target, "selkies_skin", battle):
        _spend_reactive_artifact(target, battle)
        target.markers["mistform_ready"] = 0
        strike_source = f"{source.name}'s {weapon.name}" if weapon is not None else f"{source.name}'s Strike"
        battle.log_add(f"{target.name}'s Selkie’s Skin negates {strike_source}.")
        return 0
    if source_kind == "strike" and target.markers.pop("mistform_ready", 0):
        return 0

    if target.markers.get("shimmering_valor_rounds", 0) > 0:
        damage = math.ceil(damage * 0.65)
    if target.markers.get("crafty_wall_rounds", 0) > 0:
        damage = math.ceil(damage * 0.65)
    if source_kind == "strike" and target.markers.get("trojan_horse_rounds", 0) > 0:
        return 0
    elif source_kind == "strike" and target.markers.get("not_by_the_hair_rounds", 0) > 0:
        damage = math.ceil(damage * 0.65)
        source.add_status("weaken", 2)
        target.markers["bricklayer_triggered_this_round"] = 1
    elif source_kind == "strike" and target.defn.id == "porcus_iii" and damage >= math.ceil(target.max_hp * 0.2):
        damage = math.ceil(damage * 0.65)
        source.add_status("weaken", 2)
        target.markers["bricklayer_triggered_this_round"] = 1

    if target.has_status("guard") and source.defn.id == "robin_hooded_avenger":
        pass
    return damage


def _handle_post_damage_reactions(
    source: CombatantState,
    target: CombatantState,
    damage: int,
    battle: BattleState,
    *,
    source_kind: str,
    weapon: Optional[WeaponDef],
) -> bool:
    if damage > 0 and source_kind == "strike" and target.has_status("reflecting_pool"):
        reflect_ratio = 0.50 if weapon is not None and weapon.kind == "magic" else 0.25
        reflected = max(1, math.ceil(damage * reflect_ratio))
        previous_hp = source.hp
        source.hp = max(0, source.hp - reflected)
        battle.log_add(f"{target.name}'s Reflecting Pool reflects {reflected} damage to {source.name} {_hp_change_text(previous_hp, source.hp)}.")
        if source.hp <= 0:
            if not _try_prevent_fatal(source, battle, previous_hp=previous_hp):
                source.ko = True
                battle.log_add(f"{source.name} is knocked out.")
    if damage > 0 and source_kind == "strike" and _artifact_ready(target, "nettle_smock", battle):
        _spend_reactive_artifact(target, battle)
        reflected = max(1, math.ceil(damage * 0.20))
        previous_hp = source.hp
        source.hp = max(0, source.hp - reflected)
        source.add_status("heal_cut", 2)
        battle.log_add(f"{target.name}'s Thornmail reflects {reflected} damage to {source.name} {_hp_change_text(previous_hp, source.hp)}.")
        if source.hp <= 0:
            if not _try_prevent_fatal(source, battle, previous_hp=previous_hp):
                source.ko = True
                battle.log_add(f"{source.name} is knocked out.")
    if (
        damage > 0
        and source_kind == "strike"
        and _artifact_ready(target, "blood_diamond", battle)
        and target.hp <= math.ceil(target.max_hp * 0.5)
        and target.hp + damage > math.ceil(target.max_hp * 0.5)
    ):
        _spend_reactive_artifact(target, battle)
        target.markers["blood_diamond_ready"] = 1
        battle.log_add(f"{target.name}'s Blood Diamond empowers their next Strike.")
    if damage > 0 and source_kind == "strike":
        target.markers["mirror_blade_effect"] = {
            "power": weapon.strike.power if weapon is not None else damage,
            "target_statuses": list(weapon.strike.target_statuses) if weapon is not None else [],
        }
    if damage > 0 and source_kind == "strike" and _artifact_ready(source, "suspicious_eye", battle) and source.slot == target.slot:
        _spend_reactive_artifact(source, battle)
        target.remove_status("spotlight")
        target.add_status("spotlight", 2)
        battle.log_add(f"{source.name}'s Suspicious Eye Spotlights {target.name}.")
    if damage > 0 and source_kind == "strike" and target.markers.get("event_horizon_rounds", 0) > 0:
        _grant_meter(target, battle, spell_like=False, is_strike=True)
    if target.hp <= 0 and target.defn.id == "lucky_constantine" and target.primary_weapon.id == "cat_o_nine" and source_kind == "strike" and source.has_status("expose"):
        charges = target.markers.get("nine_lives", 3)
        if charges > 0:
            target.markers["nine_lives"] = charges - 1
            target.hp = 1
            target.ko = False
            battle.log_add(f"{target.name}'s Nine Lives leaves them at 1 HP.")
            return True
    if damage > 0 and source_kind == "strike" and target.defn.id == "the_green_knight" and target.primary_weapon.id == "the_answer" and source.slot != target.slot:
        retaliation = max(
            1,
            math.ceil(
                35
                * (
                    _formula_offense_stat(target, battle, opponent=source)
                    / max(1, _formula_stat(source, "defense", battle, opponent=target))
                )
            ),
        )
        previous_hp = source.hp
        source.hp = max(0, source.hp - retaliation)
        battle.log_add(f"{target.name}'s Awaited Blow retaliates against {source.name} for {retaliation} damage {_hp_change_text(previous_hp, source.hp)}.")
        if source.hp <= 0:
            if not _try_prevent_fatal(source, battle, previous_hp=previous_hp):
                source.ko = True
                battle.log_add(f"{source.name} is knocked out.")
    if target.hp > 0 and target.defn.id == "ashen_ella" and target.hp <= math.ceil(target.max_hp * 0.5):
        if target.markers.get("struck_midnight_round", -1) != battle.round_num:
            target.markers["struck_midnight_round"] = battle.round_num
            partner = team_for_actor(battle, target).get_slot(SLOT_BACK_LEFT) if target.slot == SLOT_FRONT else team_for_actor(battle, target).frontline()
            if partner is not None and partner is not target:
                do_swap(target, partner, battle)
                _heal_unit(target, 40, battle)
    beast = next((unit for unit in team_for_actor(battle, target).alive() if unit.defn.id == "the_good_beast"), None)
    if beast is not None and beast.markers.get("guest_unit") is target:
        beast.markers["guest_last_attacker"] = source
    if target.hp <= 0:
        target_team = team_for_actor(battle, target)
        for ally in target_team.alive():
            if ally.defn.id == "lady_of_reflections" and ally.primary_weapon.id == "lantern_of_avalon" and ally is not target:
                retaliation = max(
                    1,
                    math.ceil(
                        50
                        * (
                            _formula_offense_stat(target, battle, opponent=source)
                            / max(1, _formula_stat(source, "defense", battle, opponent=target))
                        )
                    ),
                )
                previous_hp = source.hp
                source.hp = max(0, source.hp - retaliation)
                battle.log_add(f"Lady of Reflections' Postmortem Passage retaliates against {source.name} for {retaliation} damage {_hp_change_text(previous_hp, source.hp)}.")
                if source.hp <= 0:
                    if not _try_prevent_fatal(source, battle, previous_hp=previous_hp):
                        source.ko = True
                        battle.log_add(f"{source.name} is knocked out.")
                    break
        if target.defn.id == "matchbox_liesl" and target.primary_weapon.id == "eternal_torch":
            for ally in target_team.alive():
                _heal_unit(ally, math.ceil(ally.max_hp * 0.5), battle)
    return False


def _resolve_effect(
    actor: CombatantState,
    effect: ActiveEffect,
    target: Optional[CombatantState],
    battle: BattleState,
    *,
    source_kind: str,
    weapon: Optional[WeaponDef] = None,
):
    source_label = _effect_source_label(actor, effect, source_kind=source_kind, weapon=weapon)
    if effect.target == "none":
        _apply_special(actor, target, effect, battle, source_kind=source_kind, weapon=weapon)
        return

    targets = [target] if target is not None else []
    if effect.spread:
        targets = get_legal_targets(battle, actor, effect=effect, weapon=weapon)
    if effect.target == "self":
        targets = [actor]

    for current_target in targets:
        if current_target is None or current_target.ko:
            continue
        if source_kind in {"spell", "strike"}:
            redirect_ref = current_target.markers.pop("dazzle_redirect_ref", None)
            if redirect_ref is not None:
                redirect_team = battle.team1 if redirect_ref[0] == 1 else battle.team2
                redirect_target = next((unit for unit in redirect_team.alive() if unit.defn.id == redirect_ref[1]), None)
                if redirect_target is not None and redirect_target is not current_target:
                    battle.log_add(f"{current_target.name}'s Dazzle redirects the effect to {redirect_target.name}.")
                    current_target = redirect_target
        if effect.special == "statused_only" and not current_target.statuses:
            battle.log_add(f"{source_label} fails because {current_target.name} has no status condition.")
            continue
        spell_like_targeting = source_kind == "spell" or (source_kind == "strike" and weapon is not None and weapon.kind == "magic")
        if spell_like_targeting:
            target_team = team_for_actor(battle, current_target)
            if any(ally.defn.id == "destitute_vasilisa" for ally in target_team.alive()):
                current_target.add_status("guard", 2)
        damage = 0
        if effect.power > 0:
            if effect.special == "ally_heal_from_damage":
                damage = compute_damage(actor, current_target, effect, battle=battle, weapon=weapon)
                healed = math.ceil(damage * 0.5)
                _heal_unit(current_target, healed, battle, source_label=source_label)
                damage = 0
            else:
                damage = compute_damage(actor, current_target, effect, battle=battle, weapon=weapon)
            if damage > 0 and effect.spread and actor.markers.get("spread_fortune_rounds", 0) <= 0:
                damage = math.ceil(damage * 0.5)
            if damage > 0:
                damage = _modify_incoming_damage(actor, current_target, damage, battle, source_kind=source_kind, weapon=weapon)
                previous_hp = current_target.hp
                current_target.hp = max(0, current_target.hp - damage)
                battle.log_add(f"{source_label} hits {current_target.name} for {damage} damage {_hp_change_text(previous_hp, current_target.hp)}.")
                if current_target.hp <= 0:
                    if _try_prevent_fatal(current_target, battle, previous_hp=previous_hp):
                        pass
                    else:
                        current_target.ko = True
                        battle.log_add(f"{current_target.name} is knocked out.")
                        _on_kill(actor, battle, damage)
        if effect.heal > 0:
            heal_amount = effect.heal + (15 if actor.class_skill.id == "healer" else 0)
            if current_target.has_status("heal_boost"):
                heal_amount += 15
            _heal_unit(current_target, heal_amount, battle, source_label=source_label)
            if actor.class_skill.id == "medic":
                current_target.statuses = []
                current_target.debuffs = []
        if damage > 0 and effect.lifesteal > 0:
            heal_amount = math.ceil(damage * effect.lifesteal)
            if actor.has_status("heal_boost"):
                heal_amount += 15
            heal_amount += actor.markers.pop("guiding_doll_lifesteal_bonus", 0)
            _heal_unit(actor, heal_amount, battle, source_label=f"{source_label} lifesteal")
        if damage > 0:
            recoil = effect.recoil + (0.15 if source_kind == "strike" and actor.has_status("shock") else 0.0)
            if source_kind == "strike" and actor.markers.get("polymorph_rounds", 0) > 0:
                recoil = max(recoil, 0.30)
            if recoil > 0:
                recoil_damage = max(1, math.ceil(damage * recoil))
                previous_hp = actor.hp
                actor.hp = max(0, actor.hp - recoil_damage)
                battle.log_add(f"{source_label} recoil hits {actor.name} for {recoil_damage} damage {_hp_change_text(previous_hp, actor.hp)}.")
                if actor.hp <= 0:
                    if not _try_prevent_fatal(actor, battle, previous_hp=previous_hp):
                        actor.ko = True
                        battle.log_add(f"{actor.name} is knocked out.")
            if source_kind == "strike" and actor.markers.get("eyes_everywhere_rounds", 0) > 0:
                current_target.add_debuff("defense", 5, 2)
                actor.add_buff("defense", 5, 2)
            if source_kind == "strike" and actor.markers.get("disenfranchise_rounds", 0) > 0:
                for stat_name in ("attack", "defense", "speed"):
                    current_target.add_debuff(stat_name, 10, 2)
                    actor.add_buff(stat_name, 10, 2)
            if source_kind == "strike" and actor.markers.pop("king_of_thieves_ready", 0):
                current_target.add_debuff("attack", 30, 2)
                actor.add_buff("attack", 30, 2)
            if _handle_post_damage_reactions(actor, current_target, damage, battle, source_kind=source_kind, weapon=weapon):
                continue
        _apply_nondamage_effects(actor, current_target, effect, battle, source_kind=source_kind)
        _apply_special(actor, current_target, effect, battle, source_kind=source_kind, weapon=weapon)
        _check_promotion(team_for_actor(battle, current_target))
        _check_winner(battle)
        if battle.winner is not None:
            return


def _on_kill(actor: CombatantState, battle: BattleState, damage: int):
    if actor.defn.id == "witch_hunter_gretel":
        actor.add_buff("attack", 15, 2)
        actor.add_buff("speed", 15, 2)
    if _artifact_ready(actor, "black_torch", battle):
        _spend_reactive_artifact(actor, battle)
        _heal_unit(actor, math.ceil(damage * 0.5), battle, source_label=f"{actor.name}'s Black Torch")


def _apply_nondamage_effects(
    actor: CombatantState,
    target: CombatantState,
    effect: ActiveEffect,
    battle: BattleState,
    *,
    source_kind: str,
):
    source_label = _effect_source_label(actor, effect, source_kind=source_kind, weapon=actor.primary_weapon)
    extended_status = False
    applied_buffs: list[tuple[CombatantState, str, int, int]] = []
    for status_spec in effect.target_statuses:
        if status_spec.kind == "guard" and target.markers.get("unsealed_rounds", 0) > 0:
            continue
        if status_spec.kind == "burn":
            target_team = team_for_actor(battle, target)
            if any(ally.defn.id == "matchbox_liesl" for ally in target_team.alive()):
                continue
        if team_for_actor(battle, actor) is not team_for_actor(battle, target):
            tam_lin_protection = target.defn.id == "tam_lin_thornbound" or any(
                ally.defn.id == "tam_lin_thornbound" and ally.primary_weapon.id == "beam_of_light"
                for ally in team_for_actor(battle, target).alive()
            )
            if tam_lin_protection and target.markers.get("faeries_ransom_round", -1) != battle.round_num:
                target.markers["faeries_ransom_round"] = battle.round_num
                target.add_buff("defense", 15, 2)
                battle.log_add(f"{target.name}'s Faerie's Ransom rejects {source_label}'s {status_spec.kind.title()}.")
                continue
        if target.add_status(status_spec.kind, status_spec.duration):
            if _artifact_ready(actor, "cursed_spindle", battle) and not extended_status:
                for status in reversed(target.statuses):
                    if status.kind == status_spec.kind:
                        status.duration += 1
                        break
                _spend_reactive_artifact(actor, battle)
                extended_status = True
            applied_duration = next((status.duration for status in reversed(target.statuses) if status.kind == status_spec.kind), status_spec.duration)
            battle.log_add(f"{source_label} inflicts {status_spec.kind.title()} on {target.name} for {applied_duration} rounds.")
            if status_spec.kind == "taunt":
                target.markers["taunt_source"] = actor
            if status_spec.kind == "burn" and actor.defn.id == "matchbox_liesl" and actor.primary_weapon.id == "matchsticks":
                target.add_status("burn_block_heal", status_spec.duration)
            if _artifact_ready(target, "philosophers_stone", battle) and team_for_actor(battle, actor) is not team_for_actor(battle, target):
                _spend_reactive_artifact(target, battle)
                target.remove_status(status_spec.kind)
                _heal_unit(target, 40, battle, source_label=f"{target.name}'s Philosopher's Stone")
                battle.log_add(f"{target.name}'s Philosopher's Stone purifies {status_spec.kind.title()}.")
    for status_spec in effect.self_statuses:
        if actor.add_status(status_spec.kind, status_spec.duration):
            battle.log_add(f"{source_label} grants {status_spec.kind.title()} to {actor.name} for {status_spec.duration} rounds.")
    for buff in effect.self_buffs:
        amount = buff.amount + (10 if actor.markers.get("devils_nursery_rounds", 0) > 0 else 0)
        if buff.stat == "defense" and actor.markers.get("unsealed_rounds", 0) > 0:
            continue
        actor.add_buff(buff.stat, amount, buff.duration)
        applied_buffs.append((actor, buff.stat, amount, buff.duration))
    for buff in effect.target_buffs:
        amount = buff.amount + (10 if actor.markers.get("devils_nursery_rounds", 0) > 0 else 0)
        if buff.stat == "defense" and target.markers.get("unsealed_rounds", 0) > 0:
            continue
        target.add_buff(buff.stat, amount, buff.duration)
        applied_buffs.append((target, buff.stat, amount, buff.duration))
    for debuff in effect.target_debuffs:
        amount = debuff.amount + (10 if actor.markers.get("devils_nursery_rounds", 0) > 0 else 0)
        target.add_debuff(debuff.stat, amount, debuff.duration)
    if (
        source_kind == "spell"
        and actor.defn.id == "destitute_vasilisa"
        and actor.primary_weapon.id == "skull_lantern"
        and effect.target == "enemy"
    ):
        target.add_status("spotlight", 2)
    if applied_buffs:
        team = team_for_actor(battle, actor)
        if not team.markers.get("art_of_the_deal_triggered", 0):
            for recipient, stat_name, amount, duration in applied_buffs:
                if recipient.defn.id == "rumpelstiltskin":
                    continue
                rumpel = next((ally for ally in team.alive() if ally.defn.id == "rumpelstiltskin"), None)
                if rumpel is not None:
                    rumpel.add_buff(stat_name, amount + (10 if rumpel.markers.get("devils_nursery_rounds", 0) > 0 else 0), duration)
                    team.markers["art_of_the_deal_triggered"] = 1
                    break


def _apply_special(
    actor: CombatantState,
    target: Optional[CombatantState],
    effect: ActiveEffect,
    battle: BattleState,
    *,
    source_kind: str,
    weapon: Optional[WeaponDef] = None,
):
    special = effect.special
    if not special:
        return
    if special in {
        "across_bonus_15",
        "anansi_sword",
        "ally_heal_from_damage",
        "barbed_arrows",
        "bargain",
        "cracked_stopwatch",
        "cunning_retreat",
        "evermore",
        "featherweight",
        "faeries_ransom",
        "fang_bonus_vs_penalty",
        "golden_fiddle",
        "guest_bonus",
        "headwinds",
        "heavy_gale",
        "horn_of_plenty",
        "infinity",
        "lane_bonus_15",
        "lightning_rod",
        "last_stand",
        "stay_the_blade",
        "nebulous_ides",
        "bonus_vs_backline_30",
        "mirror_blade",
        "mortar_mortar",
        "multihit_9",
        "tangled_plots",
        "tarnhelm",
        "the_twist",
        "thousand_and_one_nights",
        "skull_lantern",
        "statused_only",
        "stitch_in_time_strike",
        "transmutation",
        "the_stinger",
        "unroof",
        "wooden_club",
    }:
        return
    if special == "next_strike_ignore_targeting":
        actor.markers["ignore_targeting_strikes"] = 1
        return
    if special == "next_strike_ignore_all_defense":
        actor.markers["next_strike_ignore_all_defense"] = 1
        return
    if special == "next_strike_expose":
        actor.markers["next_strike_expose"] = 1
        return
    if special == "next_strike_lifesteal_30":
        actor.markers["next_strike_lifesteal"] = 1
        return
    if special == "next_strike_bonus_10_shock":
        actor.markers["next_strike_shock"] = 1
        return
    if special == "next_strike_plus_10_spotlight":
        actor.markers["next_strike_spotlight"] = 1
        return
    if special == "next_strike_plus_10_spread":
        actor.markers["next_strike_spread"] = 1
        return
    if special == "next_magic_strike_plus_15":
        actor.markers["next_magic_strike_bonus"] = 1
        return
    if special == "next_melee_plus_10_weaken":
        actor.markers["next_melee_bonus_power"] = 1
        return
    if special == "next_ranged_ignore_targeting_no_ammo":
        actor.markers["next_ranged_ignore_targeting_no_ammo"] = 1
        return
    if special == "seeking_yarn":
        actor.markers["seeking_yarn_rounds"] = 2
        return
    if special == "elixir_of_life":
        actor.markers["elixir_of_life_ready"] = 1
        return
    if special == "guiding_doll" and target is not None:
        heal_bonus = 0
        if actor.class_skill.id == "healer":
            heal_bonus += 15
        if actor.has_status("heal_boost"):
            heal_bonus += 15
        target.markers["guiding_doll_buff"] = {
            "team_num": player_num_for_actor(battle, actor),
            "owner_id": actor.defn.id,
            "heal_bonus": heal_bonus,
        }
        return
    if special == "foxfire_bow" and target is not None:
        actor.markers["glowing_trail_target"] = (
            player_num_for_actor(battle, target),
            target.defn.id,
        )
        return
    if special == "beggars_greatbow" and target is not None:
        target.markers["odysseus_arrow_count"] = target.markers.get("odysseus_arrow_count", 0) + 1
        return
    if special == "thiefs_dagger" and target is not None:
        if target.artifact is not None:
            actor.markers["artifact_bonus_spell_effect"] = target.artifact.spell
            actor.markers["artifact_bonus_spell_rounds"] = 1
        return
    if special == "seal_the_cave" and target is not None:
        affected_effects = set(target.markers.get("sealed_cave_effects", set()))
        affected_any = False
        for effect_id, turns in list(target.cooldowns.items()):
            if turns > 0:
                target.cooldowns[effect_id] = turns + 1
                affected_effects.add(effect_id)
                affected_any = True
        if affected_any:
            target.markers["sealed_cave_effects"] = affected_effects
        else:
            target.markers.pop("sealed_cave_effects", None)
        return
    if special == "swallow_the_sun":
        for ally in team_for_actor(battle, actor).alive():
            ally.add_buff("defense", 15, 2)
        return
    if special == "witchs_blessing":
        for ally in team_for_actor(battle, actor).alive():
            ally.markers["witchs_blessing_rounds"] = 2
        return
    if special == "forty_thieves":
        for enemy in enemy_team_for_actor(battle, actor).alive():
            enemy.markers["forty_thieves_rounds"] = 2
        return
    if special == "sukas_eyes":
        for enemy in enemy_team_for_actor(battle, actor).alive():
            enemy.remove_status("spotlight")
            enemy.add_status("spotlight", 2)
        return
    if special == "gaze_of_love":
        for ally in team_for_actor(battle, actor).alive():
            ally.markers["gaze_of_love_rounds"] = 2
        for enemy in enemy_team_for_actor(battle, actor).alive():
            enemy.remove_status("spotlight")
            enemy.add_status("spotlight", 2)
        return
    if special == "king_of_thieves":
        actor.markers["king_of_thieves_ready"] = 1
        return
    if special == "raise_the_sky":
        actor.markers["conquer_death_used"] = 0
        actor.markers["raise_the_sky_rounds"] = 2
        return
    if special == "cleanse_newest_status" and target is not None:
        if target.statuses:
            target.statuses.pop()
        return
    if special == "dazzle" and target is not None:
        target.markers["dazzle_redirect_ref"] = (
            player_num_for_actor(battle, actor),
            actor.defn.id,
        )
        return
    if special == "average_hp_with_target" and target is not None:
        shared_hp = math.ceil((actor.hp + target.hp) / 2)
        actor.hp = min(actor.max_hp, shared_hp)
        target.hp = min(target.max_hp, shared_hp)
        battle.log_add(f"{actor.name} and {target.name} are set to {shared_hp} HP.")
        return
    if special == "artifact_swap_with_ally" and target is not None:
        do_swap(actor, target, battle)
        return
    if special == "refresh_root_expose" and target is not None:
        target.remove_status("root")
        target.add_status("root", 2)
        target.add_status("expose", 2)
        return
    if special == "burn_if_not_burned":
        if target is not None and not target.has_status("burn"):
            target.add_status("burn", 2)
        return
    if special == "cant_strike_next_turn" and target is not None:
        target.markers["cant_strike_rounds"] = max(target.markers.get("cant_strike_rounds", 0), 1)
        return
    if special == "bloodstain":
        actor.hp = max(1, actor.hp - 40)
        actor.markers["malice"] = actor.markers.get("malice", 0) + 2
        return
    if special == "crumb_shot":
        team = team_for_actor(battle, actor)
        if team.markers.get("crumb_picked_round", 0) <= 0:
            crumb_slots = set(team.markers.get("crumb_slots", set()))
            crumb_slots.add(actor.slot)
            team.markers["crumb_slots"] = crumb_slots
        return
    if special == "blue_faeries_boon":
        actor.markers["malice"] = max(actor.markers.get("malice", 0), 6)
        actor.add_buff("speed", 20, 2)
        return
    if special == "crowstorm":
        actor.markers["crowstorm_rounds"] = 2
        actor.markers["untargetable_rounds"] = 2
        return
    if special == "cracked_stopwatch" and target is not None and target.has_status("shock"):
        actor.markers["spell_bonus_rounds"] = 1
        return
    if special == "rabbit_hole":
        actor.markers["rabbit_hole_extra_rounds"] = actor.markers.get("spells_cast_this_round", 0)
        return
    if special == "wolf_unchained":
        actor.markers["wolf_unchained_rounds"] = 2
        return
    if special == "eyes_everywhere":
        actor.markers["eyes_everywhere_rounds"] = 2
        for enemy in enemy_team_for_actor(battle, actor).alive():
            enemy.remove_status("expose")
            enemy.add_status("expose", 2)
        return
    if special == "final_stand":
        actor.markers["silver_aegis_always_active"] = 2
        return
    if special == "shimmering_valor":
        guard_duration = max((status.duration for status in actor.statuses if status.kind == "guard"), default=0)
        actor.remove_status("guard")
        _heal_unit(actor, 40 + 20 * guard_duration, battle)
        return
    if special == "crafty_wall":
        actor.markers["crafty_wall_rounds"] = 1
        return
    if special == "not_by_the_hair":
        actor.markers["not_by_the_hair_rounds"] = 1
        return
    if special == "mass_hysteria":
        actor.markers["mass_hysteria_rounds"] = 2
        return
    if special == "spread_fortune":
        actor.markers["spread_fortune_rounds"] = 2
        return
    if special == "time_stop":
        actor.markers["untargetable_rounds"] = 1
        actor.markers["cant_act_rounds"] = 1
        return
    if special == "midnight_waltz" and target is not None:
        do_swap(actor, target, battle)
        actor.markers["next_spell_no_cooldown"] = 1
        return
    if special == "mistform":
        actor.markers["mistform_ready"] = 1
        return
    if special == "repair_secondary_weapon":
        if actor.secondary_weapon.ammo > 0:
            actor.ammo_remaining[actor.secondary_weapon.id] = actor.secondary_weapon.ammo
        actor.markers.pop("shotgun_combusted", None)
        return
    if special == "vine_snare":
        actor.markers["vine_snare_ready"] = 1
        return
    if special == "takes_plus_15_damage" and target is not None:
        target.remove_status("damage_amp")
        target.add_status("damage_amp", 2)
        return
    if special == "in_the_oven":
        team = team_for_actor(battle, actor)
        enemy_team = enemy_team_for_actor(battle, actor)
        for ally in team.alive():
            ally.remove_status("heal_boost")
            ally.add_status("heal_boost", 2)
        for enemy in enemy_team.alive():
            enemy.remove_status("damage_amp")
            enemy.add_status("damage_amp", 2)
        return
    if special == "cleansing_inferno":
        for ally in team_for_actor(battle, actor).alive():
            ally.markers["cleansing_inferno_rounds"] = 2
        return
    if special == "tea_party":
        for ally in team_for_actor(battle, actor).alive():
            ally.markers["tea_party_rounds"] = 2
        return
    if special == "falling_kingdom":
        actor.markers["falling_kingdom_rounds"] = 2
        for enemy in enemy_team_for_actor(battle, actor).alive():
            enemy.remove_status("root")
            enemy.add_status("root", 2)
        return
    if special == "self_swap_after_strike":
        team = team_for_actor(battle, actor)
        partner = team.get_slot(SLOT_BACK_LEFT) if actor.slot == SLOT_FRONT else team.frontline()
        if partner is not None and partner is not actor:
            do_swap(actor, partner, battle)
        return
    if special == "swap_target_with_enemy" and target is not None:
        enemy_team = enemy_team_for_actor(battle, actor)
        swap_candidate = min(
            (enemy for enemy in enemy_team.alive() if enemy is not target),
            key=lambda enemy: enemy.hp,
            default=None,
        )
        if swap_candidate is not None:
            target.slot, swap_candidate.slot = swap_candidate.slot, target.slot
            _sync_position_locked_weapon(target)
            _sync_position_locked_weapon(swap_candidate)
            determine_initiative_order(battle)
        return
    if special == "guest_attacker_spotlight":
        marked = actor.markers.get("guest_last_attacker")
        if marked is not None and not marked.ko:
            marked.add_status("spotlight", 2)
        return
    if special == "jovial_shot":
        actor.hp = actor.max_hp
        actor.markers["jovial_shot_ready"] = 1
        return
    if special == "disenfranchise":
        actor.markers["disenfranchise_rounds"] = 2
        return
    if special == "straw_to_gold" and target is not None:
        for debuff in target.debuffs:
            if debuff.duration > 0:
                actor.add_buff(debuff.stat, debuff.amount, 2)
        return
    if special == "silken_prose" and target is not None:
        target.markers["silken_prose_rounds"] = 2
        return
    if special == "spinning_wheel" and target is not None:
        wheel_hits = actor.markers.get("spinning_wheel_hits", 0) + 1
        actor.markers["spinning_wheel_hits"] = wheel_hits
        if wheel_hits == 1:
            target.add_debuff("attack", 10, 2)
        elif wheel_hits == 2:
            target.add_debuff("defense", 10, 2)
        else:
            target.add_debuff("speed", 10, 2)
        return
    if special == "devils_nursery":
        actor.markers["devils_nursery_rounds"] = 2
        return
    if special == "daybreak":
        enemy_team = enemy_team_for_actor(battle, actor)
        enemy_team.ultimate_meter = 0
        enemy_team.markers["daybreak_lock_rounds"] = 2
        return
    if special == "lamp_of_infinity":
        right_slot = _slot_to_right(actor.slot)
        if right_slot is None:
            return
        ally = team_for_actor(battle, actor).get_slot(right_slot)
        if ally is not None and ally is not actor:
            _heal_unit(ally, 40, battle)
        return
    if special == "web_of_centuries":
        actor.markers["web_of_centuries_rounds"] = 2
        actor.markers["granted_spells"] = list(ALL_ADVENTURER_SPELLS)
        return
    if special == "trojan_horse":
        team = team_for_actor(battle, actor)
        if actor.slot == SLOT_FRONT:
            partner = team.get_slot(SLOT_BACK_LEFT) or team.get_slot(SLOT_BACK_RIGHT)
        else:
            partner = team.frontline()
        if partner is not None and partner is not actor:
            do_swap(actor, partner, battle)
        actor.markers["trojan_horse_rounds"] = 1
        actor.markers["bonus_switch_rounds"] = 2
        return
    if special == "zephyr" and target is not None:
        enemy_team = team_for_actor(battle, target)
        left_slot = _slot_to_left(target.slot)
        if left_slot is not None:
            swap_target = enemy_team.get_slot(left_slot)
            if swap_target is not None and swap_target is not target:
                target.slot, swap_target.slot = swap_target.slot, target.slot
                _sync_position_locked_weapon(target)
                _sync_position_locked_weapon(swap_target)
        return
    if special == "comet" and target is not None:
        target.markers["comet_magic_amp_rounds"] = 1
        return
    if special == "dream_twister":
        for slot_name in SLOT_SEQUENCE:
            _set_air_current(battle, slot_name, 2)
        for ally in team_for_actor(battle, actor).alive():
            ally.add_buff("speed", 15, 2)
        return
    if special == "walking_abode" and target is not None:
        target.add_status("heal_cut", 2)
        return
    if special == "event_horizon":
        actor.markers["event_horizon_rounds"] = 2
        return
    if special == "polymorph" and target is not None:
        target.markers["polymorph_rounds"] = 2
        target.add_buff("attack", 15, 2)
        target.add_buff("defense", 15, 2)
        target.add_buff("speed", 15, 2)
        return
    if special == "fated_duel" and target is not None:
        battle.markers.setdefault("fated_duel_lanes", {})[actor.slot] = 2
        return
    if special == "happily_ever_after":
        guest = actor.markers.get("guest_unit")
        if guest is None or guest.ko:
            return
        for stat_name in ("attack", "defense", "speed"):
            actor_value = actor.get_stat(stat_name, battle)
            guest_value = guest.get_stat(stat_name, battle)
            high_value = max(actor_value, guest_value)
            if high_value > actor_value:
                actor.add_buff(stat_name, high_value - actor_value, 2)
            if high_value > guest_value:
                guest.add_buff(stat_name, high_value - guest_value, 2)
        return
    if special == "lakes_gift":
        team = team_for_actor(battle, actor)
        fallen = [ally for ally in team.members if ally.ko and ally is not actor]
        if fallen:
            revived = fallen[0]
            revived.ko = False
            revived.hp = math.ceil(revived.max_hp * 0.5)
            revived.slot = actor.slot
            revived.add_buff("attack", 15, 2)
            actor.hp = 0
            actor.ko = True
            battle.log_add(f"{actor.name} revives {revived.name} with Lake's Gift.")
        return
    if special == "foam_prison" and target is not None:
        stolen = target.defn.ultimate
        if stolen.special == "foam_prison":
            battle.log_add(f"{actor.name}'s Foam Prison cannot recursively steal Foam Prison.")
            return
        depth = actor.markers.get("foam_prison_depth", 0)
        if depth >= 1:
            battle.log_add(f"{actor.name}'s Foam Prison recursion is prevented.")
            return
        actor.markers["foam_prison_depth"] = depth + 1
        try:
            if stolen.target == "self":
                _resolve_effect(actor, stolen, actor, battle, source_kind="ultimate")
            elif stolen.target == "ally":
                _resolve_effect(actor, stolen, actor, battle, source_kind="ultimate")
            elif stolen.target == "enemy":
                _resolve_effect(actor, stolen, target, battle, source_kind="ultimate")
            else:
                _resolve_effect(actor, stolen, None, battle, source_kind="ultimate")
        finally:
            if depth > 0:
                actor.markers["foam_prison_depth"] = depth
            else:
                actor.markers.pop("foam_prison_depth", None)
        return
    if special == "guard_lowest_hp_ally_behind":
        team = team_for_actor(battle, actor)
        candidates = [ally for ally in team.alive() if ally is not actor and ally.slot != SLOT_FRONT]
        if not candidates:
            candidates = [ally for ally in team.alive() if ally is not actor]
        if candidates:
            min(candidates, key=lambda ally: ally.hp).add_status("guard", 2)
        return
    if special == "unseal" and target is not None:
        target.remove_status("guard")
        target.buffs = [buff for buff in target.buffs if buff.stat != "defense"]
        target.markers["unsealed_rounds"] = 2
        return
    if special == "purge" and target is not None:
        removed = len(target.statuses)
        target.statuses = []
        if removed > 0:
            target.add_buff("defense", 5 * removed, 2)
        return
    if special == "severed_tether":
        actor.add_debuff("defense", 15, 2)
        actor.add_buff("attack", 30, 2)
        actor.add_buff("speed", 30, 2)
        return
    if special == "unfettered":
        actor.add_buff("attack", 100, 2)
        actor.add_buff("speed", 100, 2)
        actor.add_debuff("defense", 50, 2)
        return
    battle.log_add(f"{effect.name} special hook '{special}' is not implemented yet.")


def compute_damage(
    actor: CombatantState,
    target: CombatantState,
    effect: ActiveEffect,
    *,
    battle: Optional[BattleState] = None,
    weapon: Optional[WeaponDef] = None,
) -> int:
    attack = _formula_offense_stat(actor, battle, opponent=target)
    defense = _formula_stat(target, "defense", battle, opponent=actor)
    power = effect.power
    if effect.special == "multihit_9":
        single_hit = max(1, math.ceil(9 * (attack / max(1, defense))))
        return single_hit * 9
    if effect.bonus_power_if_status and target.has_status(effect.bonus_power_if_status):
        power += effect.bonus_power
    if actor.defn.id == "the_green_knight" and effect.special in {"across_bonus_15", "lane_bonus_15"} and target.slot == actor.slot:
        power += 15
    if actor.defn.id == "robin_hooded_avenger" and effect.special == "bonus_vs_backline_30" and target.slot != SLOT_FRONT:
        power += 30
    if actor.defn.id == "pinocchio_cursed_puppet" and effect.special == "wooden_club":
        power += actor.markers.get("malice", 0) * 5
    if weapon is not None:
        if weapon.kind == "melee" and actor.class_skill.id == "martial":
            power += 15
        if weapon.kind == "magic" and actor.class_skill.id == "arcane":
            power += 10
        if weapon.kind == "ranged" and actor.class_skill.id == "deadeye":
            power += 10
    if actor.defn.id == "little_jack" and target.max_hp > actor.max_hp:
        power += 15
    if actor.defn.id == "hunold_the_piper" and target.has_status("shock"):
        power += 15
    if actor.defn.id == "reynard_lupine_trickster" and target.markers.get("struck_last_round", 0) <= 0:
        power += 15
    if actor.markers.pop("ignore_defense_for_strike", 0):
        defense = 1
    elif actor.defn.id == "little_jack" and actor.primary_weapon.id == "giants_harp":
        defense = max(1, math.ceil(defense * 0.8))
    if actor.has_status("weaken"):
        power = math.ceil(power * 0.85)
    if battle is not None and weapon is not None and source_kind_is_strike(weapon):
        target_team = team_for_actor(battle, target)
        enemy_front = target_team.frontline()
        if enemy_front is not None and enemy_front.defn.id == "scheherazade_dawns_ransom" and enemy_front.primary_weapon.id == "tome_of_ancients":
            power = max(0, power - 10)
    if target.has_status("guard") and actor.defn.id != "robin_hooded_avenger":
        power = math.ceil(power * 0.85)
    if target.has_status("expose"):
        power = math.ceil(power * 1.15)
    if target.markers.pop("silver_aegis_ready", 0):
        power = math.ceil(power * 0.4)
    if target.markers.get("silver_aegis_always_active", 0) > 0:
        power = math.ceil(power * 0.4)
    damage = max(1, math.ceil(power * (attack / max(1, defense))))
    if source_kind_is_strike(weapon) and target.markers.get("bargain_rounds", 0) > 0:
        damage += 10
    if source_kind_is_strike(weapon) and target.has_status("root") and target.markers.get("silken_prose_rounds", 0) > 0:
        damage += 8
    if weapon is not None and weapon.kind == "magic" and target.markers.pop("comet_magic_amp_rounds", 0):
        damage += 15
    if battle is not None and weapon is not None and source_kind_is_strike(weapon):
        actor_team = team_for_actor(battle, actor)
        target_team = team_for_actor(battle, target)
        if actor_team is not target_team:
            if any(
                ally.defn.id == "kama_the_honeyed"
                and ally is not actor
                and ally.slot == target.slot
                for ally in actor_team.alive()
            ):
                damage += 10
    if actor.markers.get("crowstorm_rounds", 0) > 0 and weapon is not None and weapon.kind == "magic":
        damage += math.ceil(actor.max_hp * 0.08)
    if target.has_status("damage_amp"):
        damage += 15
    return damage


def source_kind_is_strike(weapon: WeaponDef) -> bool:
    return weapon is not None


def _grant_meter(actor: CombatantState, battle: BattleState, *, spell_like: bool, is_strike: bool = False):
    team = team_for_actor(battle, actor)
    if team.markers.get("daybreak_lock_rounds", 0) > 0:
        return
    amount = 2 if spell_like else 1
    if is_strike and actor.class_skill.id == "inevitable" and actor.primary_weapon.kind == "melee":
        amount += 1
    team.ultimate_meter = min(ULTIMATE_METER_MAX, team.ultimate_meter + amount)


def end_round(battle: BattleState):
    for team in (battle.team1, battle.team2):
        if team.markers.get("bonus_swap_rounds", 0) > 0:
            team.markers["bonus_swap_rounds"] = max(0, team.markers.get("bonus_swap_rounds", 0) - 1)
            if team.markers["bonus_swap_rounds"] <= 0:
                team.markers.pop("bonus_swap_rounds", None)
        team.markers.pop("bonus_swap_used", None)
        other_team = battle.team2 if team is battle.team1 else battle.team1
        for unit in list(team.alive()):
            unit.markers["struck_last_round"] = 1 if unit.markers.get("struck_this_round", 0) > 0 else 0
            if unit.has_status("burn"):
                burn_damage = math.ceil(unit.max_hp * 0.08)
                previous_hp = unit.hp
                unit.hp = max(0, unit.hp - burn_damage)
                battle.log_add(f"Burn deals {burn_damage} damage to {unit.name} {_hp_change_text(previous_hp, unit.hp)}.")
                if any(ally.markers.get("cleansing_inferno_rounds", 0) > 0 for ally in other_team.alive()):
                    for splash in team.alive():
                        if splash is unit:
                            continue
                        splash_previous_hp = splash.hp
                        splash.hp = max(0, splash.hp - burn_damage)
                        battle.log_add(f"Cleansing Inferno scorches {splash.name} for {burn_damage} damage {_hp_change_text(splash_previous_hp, splash.hp)}.")
                        if splash.hp <= 0:
                            if not _try_prevent_fatal(splash, battle, previous_hp=splash_previous_hp):
                                splash.ko = True
                                battle.log_add(f"{splash.name} is knocked out.")
                liesl = next((ally for ally in other_team.alive() if ally.defn.id == "matchbox_liesl"), None)
                if liesl is not None:
                    heal_target = min(other_team.alive(), key=lambda ally: ally.hp / max(1, ally.max_hp))
                    _heal_unit(heal_target, burn_damage, battle, source_label=f"{liesl.name}'s Purifying Flame")
                if unit.hp <= 0:
                    if not _try_prevent_fatal(unit, battle, previous_hp=previous_hp):
                        unit.ko = True
                        battle.log_add(f"{unit.name} is knocked out.")
            unit.statuses = _tick_statuses(unit.statuses)
            unit.buffs = _tick_stat_mods(unit.buffs)
            unit.debuffs = _tick_stat_mods(unit.debuffs)
            for effect_id, turns in list(unit.cooldowns.items()):
                unit.cooldowns[effect_id] = max(0, turns - 1)
            tracked = unit.markers.get("sealed_cave_effects")
            if isinstance(tracked, set):
                tracked = {effect_id for effect_id in tracked if unit.cooldowns.get(effect_id, 0) > 0}
                if tracked:
                    unit.markers["sealed_cave_effects"] = tracked
                else:
                    unit.markers.pop("sealed_cave_effects", None)
            unit.markers["cast_artifact_spell_last_round"] = 1 if unit.markers.get("cast_artifact_spell_this_round", 0) > 0 else 0
            for marker, value in list(unit.markers.items()):
                if marker in TIMED_MARKERS and isinstance(value, int) and value > 0:
                    unit.markers[marker] = value - 1
                    if unit.markers[marker] <= 0:
                        unit.markers.pop(marker, None)
            if unit.markers.get("stolen_voices_rounds", 0) <= 0:
                unit.markers.pop("stolen_spells", None)
            if unit.markers.get("web_of_centuries_rounds", 0) <= 0:
                unit.markers.pop("granted_spells", None)
            if unit.defn.id == "pinocchio_cursed_puppet" and unit.slot == SLOT_FRONT:
                unit.markers["malice"] = min(12, unit.markers.get("malice", 0) + 1)
            _check_promotion(team)
        if team.markers.get("daybreak_lock_rounds", 0) > 0:
            team.markers["daybreak_lock_rounds"] = max(0, team.markers["daybreak_lock_rounds"] - 1)
            if team.markers["daybreak_lock_rounds"] <= 0:
                team.markers.pop("daybreak_lock_rounds", None)
    currents = _air_currents(battle)
    for slot, turns in list(currents.items()):
        turns -= 1
        if turns <= 0:
            currents.pop(slot, None)
        else:
            currents[slot] = turns
    duel_lanes = battle.markers.get("fated_duel_lanes", {})
    for lane, turns in list(duel_lanes.items()):
        turns -= 1
        if turns <= 0:
            duel_lanes.pop(lane, None)
        else:
            duel_lanes[lane] = turns
    if not duel_lanes:
        battle.markers.pop("fated_duel_lanes", None)
    _check_winner(battle)
    battle.round_num += 1
    determine_initiative_order(battle)


def _tick_statuses(statuses: List[StatusInstance]) -> List[StatusInstance]:
    remaining = []
    for status in statuses:
        if status.duration - 1 > 0:
            remaining.append(StatusInstance(kind=status.kind, duration=status.duration - 1))
    return remaining


def _tick_stat_mods(mods):
    remaining = []
    for mod in mods:
        if mod.duration - 1 > 0:
            mod.duration -= 1
            remaining.append(mod)
    return remaining


def _check_promotion(team: TeamState):
    if team.frontline() is not None:
        return
    back_left = team.get_slot(SLOT_BACK_LEFT)
    if back_left is not None:
        back_left.slot = SLOT_FRONT
        return
    back_right = team.get_slot(SLOT_BACK_RIGHT)
    if back_right is not None:
        back_right.slot = SLOT_FRONT


def _check_winner(battle: BattleState):
    if battle.winner is not None:
        return
    if battle.team1.all_ko():
        battle.winner = 2
    elif battle.team2.all_ko():
        battle.winner = 1
