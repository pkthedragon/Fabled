"""
ai.py - Tactical AI planner for Fabled.

The public API remains `pick_action(...)`, but the internals now score actions
in the context of follow-up allies, target access, recharge pressure, and the
next round's projected initiative.
"""

import copy
import math

import battle_log
from settings import SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT, CLOCKWISE_ORDER
from logic import (
    can_use_ability,
    determine_initiative,
    get_recharge_limit,
    get_legal_item_targets,
    get_legal_targets,
    get_mode,
    get_subterfuge_swap_targets,
    is_rulebook_status_condition,
    is_melee,
    is_ranged,
    ready_active_artifacts,
    resolve_queued_action,
)


MAX_SIMULATED_CANDIDATES = 30
TOP_LEVEL_CANDIDATES = 5
BEAM_WIDTH = 4
AI_PROFILE_SETTINGS = {
    "analysis": {
        "top_level_candidates": 2,
        "beam_width": 1,
        "end_of_turn_weight": 0.55,
        "next_round_weight": 0.35,
    },
    "quick": {
        "top_level_candidates": 5,
        "beam_width": 4,
        "end_of_turn_weight": 0.85,
        "next_round_weight": 0.70,
    },
    "ranked": {
        "top_level_candidates": 7,
        "beam_width": 5,
        "end_of_turn_weight": 0.95,
        "next_round_weight": 0.78,
    },
}
RULEBOOK_DANGEROUS_STATUSES = {"burn", "root", "shock", "weaken", "expose", "spotlight"}
CONTROL_STATUSES = {"root", "spotlight", "taunt"}


def top_n(items, n, key):
    return sorted(items, key=key, reverse=True)[:n]


def _ai_profile(profile):
    return AI_PROFILE_SETTINGS.get(profile, AI_PROFILE_SETTINGS["quick"])


def _unit_key(unit):
    return unit.defn.id


def _find_unit(sim_battle, key):
    for unit in sim_battle.team1.members + sim_battle.team2.members:
        if unit.defn.id == key:
            return unit
    return None


def _remap_action(action, sim_battle):
    remapped = dict(action)
    if action.get("target") is not None:
        remapped["target"] = _find_unit(sim_battle, _unit_key(action["target"]))
    if action.get("swap_target") is not None:
        remapped["swap_target"] = _find_unit(sim_battle, _unit_key(action["swap_target"]))
    return remapped


def simulate_single_action(battle, player_num, actor, action):
    sim = copy.deepcopy(battle)
    saved_f = battle_log._f
    battle_log._f = None
    try:
        sim_actor = _find_unit(sim, _unit_key(actor))
        if sim_actor is None or sim_actor.ko:
            return sim
        sim_action = _remap_action(action, sim)
        sim_actor.queued = sim_action
        resolve_queued_action(sim_actor, player_num, sim)
        sim_actor.queued = None
    finally:
        battle_log._f = saved_f
    return sim


def _simulate(battle, player_num, actor, action):
    return simulate_single_action(battle, player_num, actor, action)


def is_mixed_class(unit):
    return unit.defn.cls in ("Warlock", "Noble")


def is_ranged_now(unit):
    return is_ranged(unit)


def is_melee_now(unit):
    return is_melee(unit)


def is_recharge_locked(unit):
    return unit.must_recharge or getattr(unit, "recharge_pending", False)


def is_idle_target(unit):
    return getattr(unit, "recharge_exposed", False)


def has_not_acted_yet(unit):
    return (not unit.ko) and (not unit.acted)


def is_fragile(unit):
    return unit.get_stat("defense") <= 10 or unit.hp / max(1, unit.max_hp) <= 0.45


def classify_unit_role(unit, battle):
    if is_primary_support(unit, battle.get_team(1 if unit in battle.team1.members else 2)):
        return "support"
    if is_primary_carry(unit, battle.get_team(1 if unit in battle.team1.members else 2)):
        return "carry"
    return "bruiser"


def is_primary_carry(unit, team):
    allies = [ally for ally in team.alive()]
    if not allies:
        return False
    return unit == max(allies, key=lambda ally: ally.get_stat("attack") + ally.get_stat("speed"))


def is_primary_support(unit, team):
    support_weight = 0
    for ability in list(unit.basics) + [unit.sig, unit.defn.twist]:
        mode = get_mode(unit, ability)
        if mode.heal > 0 or mode.heal_self > 0 or mode.heal_lowest > 0:
            support_weight += 2
        if mode.guard_target or mode.guard_all_allies or mode.guard_frontline_ally or mode.guard_self:
            support_weight += 2
        if mode.status in ("spotlight", "root", "shock", "weaken", "expose"):
            support_weight += 1
    return support_weight >= 4


def effective_attack(unit, battle):
    attack = unit.get_stat("attack")
    if unit.item.id == "arcane_focus" and unit.slot != SLOT_FRONT:
        attack += unit.item.atk_bonus_back
    return attack


def effective_defense(unit, battle):
    return unit.get_stat("defense")


def estimate_raw_damage(power, atk, defense):
    if power <= 0:
        return 0
    return math.ceil(power * (atk / max(1, defense)))


def status_already_present(target, kind):
    return target.has_status(kind)


def flat_damage_rider_bonus(target):
    bonus = 0
    if target.ability_charges.get("hunters_mark_active", 0) > 0:
        bonus += 10
    if target.ability_charges.get("drown_bonus_dur", 0) > 0:
        bonus += 10
    return bonus


def apply_damage_modifiers(dmg, source, target, battle):
    if dmg <= 0:
        return 0
    if source.has_status("weaken"):
        dmg = math.ceil(dmg * 0.85)
    if source.defn.id == "little_jack" and target.max_hp > source.max_hp:
        dmg = math.ceil(dmg * 1.15)
    if source.defn.id == "frederic" and target.slot == SLOT_FRONT:
        dmg = math.ceil(dmg * 1.15)
    if target.has_status("expose"):
        dmg = math.ceil(dmg * 1.15)
    if target.defn.id == "porcus_iii":
        bricklayer_multiplier = max(1, target.ability_charges.get("bricklayer_all_active", 0))
        bricklayer_on_all_hits = target.ability_charges.get("bricklayer_all_active", 0) > 0
        threshold = math.ceil(target.max_hp * 0.20)
        if bricklayer_on_all_hits or dmg >= threshold:
            reduction = min(0.35 * bricklayer_multiplier, 0.95)
            dmg = math.ceil(dmg * (1 - reduction))
    if target.has_status("guard"):
        dmg = math.ceil(dmg * 0.85)
    if target.defn.id == "frederic" and source.slot == SLOT_FRONT:
        dmg = math.ceil(dmg * 1.07)
    dmg += flat_damage_rider_bonus(target)
    if source.defn.id == "robin_hooded_avenger" and target.slot != SLOT_FRONT:
        dmg += 7
    if source.defn.id == "lucky_constantine" and target.slot != SLOT_FRONT:
        if getattr(target, "recharge_exposed", False):
            dmg += 7
        else:
            dmg = max(0, dmg - 7)
    if source.defn.id == "green_knight" and target.slot == source.slot:
        dmg += 15
    if source.defn.id == "green_knight" and source.sig.id == "natural_order" and source.slot == SLOT_FRONT:
        if target.ability_charges.get("rounds_since_swap", 0) >= 2:
            dmg += 15
    if source.defn.id == "snowkissed_aurora" and source.sig.id == "birdsong" and source.slot == SLOT_FRONT:
        dmg += source.ability_charges.get("birdsong_birds", 0) * 7
    if source.defn.id == "prince_charming" and target.ability_charges.get("chosen_one_mark", 0) > 0:
        dmg += 15
    return max(0, dmg)


def _estimate_power(actor, ability, target):
    mode = get_mode(actor, ability)
    power = mode.power
    if power <= 0:
        return 0
    if mode.bonus_vs_low_hp and target.hp < target.max_hp * 0.5:
        power += mode.bonus_vs_low_hp
    if mode.bonus_vs_rooted and target.has_status("root"):
        power = math.ceil(power * (1 + mode.bonus_vs_rooted / 100))
    if mode.bonus_if_not_acted and not target.acted:
        power += mode.bonus_if_not_acted
    if mode.bonus_if_target_acted and target.acted:
        power += mode.bonus_if_target_acted
    if mode.bonus_vs_higher_hp and target.max_hp > actor.max_hp:
        power += mode.bonus_vs_higher_hp
    if mode.bonus_vs_backline and target.slot != SLOT_FRONT:
        power += mode.bonus_vs_backline
    if mode.bonus_vs_statused and (target.has_status("expose") or target.has_status("weaken")):
        power += mode.bonus_vs_statused
    if ability.id == "slam" and actor.slot == SLOT_FRONT and actor.has_status("guard"):
        power += 15
    if ability.id == "lower_guard" and actor.slot == SLOT_FRONT and target.debuffs:
        power += 15
    if target.ability_charges.get("condescend_bonus", 0) > 0 and ability.id != "condescend":
        power += 10
    if ability.id == "nebulous_ides" and actor.slot != SLOT_FRONT and actor.ability_charges.get("swapped_this_round", 0) > 0:
        power += 15
    if ability.id == "wooden_wallop" and actor.slot == SLOT_FRONT:
        power += actor.ability_charges.get("malice", 0) * 5
    return power


def estimate_damage(actor, ability, target, battle):
    mode = get_mode(actor, ability)
    if mode.unavailable or target is None or target.ko:
        return 0
    power = _estimate_power(actor, ability, target)
    defense = effective_defense(target, battle)
    if mode.def_ignore_pct:
        defense = max(1, math.ceil(defense * (1 - mode.def_ignore_pct / 100)))
    if ability.id == "sovereign_edict" and actor.slot == SLOT_FRONT and len([s for s in target.statuses if s.duration > 0]) >= 2:
        defense = 1
    dmg = estimate_raw_damage(power, effective_attack(actor, battle), defense)
    dmg = apply_damage_modifiers(dmg, actor, target, battle)
    if target.defn.id == "sir_roland" and target.ability_charges.get("silver_aegis", 0) > 0:
        dmg = math.ceil(dmg * 0.25)
    if mode.spread:
        if actor.defn.id == "robin_hooded_avenger" and actor.slot == SLOT_FRONT:
            dmg = math.ceil(dmg * 0.75)
        else:
            dmg = math.ceil(dmg * 0.50)
    return max(0, dmg)


def estimate_spread_damage(actor, ability, legal_targets, battle):
    return sum(estimate_damage(actor, ability, target, battle) for target in legal_targets)


def estimate_heal_value(actor, ability, target, battle):
    if target is None:
        return 0.0
    mode = get_mode(actor, ability)
    heal_amount = mode.heal + mode.heal_self + mode.heal_lowest
    if ability.id == "toxin_purge" and actor.slot == SLOT_FRONT:
        heal_amount += 12 * sum(1 for status in target.statuses if status.duration > 0 and status.kind in RULEBOOK_DANGEROUS_STATUSES)
    if heal_amount > 0 and actor.item.id == "heart_amulet":
        heal_amount += actor.item.flat_heal_bonus
    if heal_amount > 0 and actor.sig.id == "benefactor":
        heal_amount = math.ceil(heal_amount * (1.35 if actor.slot == SLOT_FRONT else 1.20))
    if target.ability_charges.get("hunters_net_heal_dur", 0) > 0:
        heal_amount = math.ceil(heal_amount * 0.50)
    if heal_amount <= 0:
        return 0.0
    missing = max(0, target.max_hp - target.hp)
    value = min(missing, heal_amount) * 1.5
    if actor.defn.id == "aldric_lost_lamb":
        value += 10.0 if not target.has_status("guard") else 0.0
    return value


def estimate_guard_value(target):
    if target is None or target.has_status("guard"):
        return 0.0
    return 18.0 + (20.0 if target.hp / max(1, target.max_hp) < 0.45 else 0.0)


def estimate_repentance_rider(actor, ability, target, battle):
    if ability.id != "repentance" or actor.slot != SLOT_FRONT or target is None:
        return 0.0
    if target.ability_charges.get("repentance_bonus", 0) > 0:
        return 0.0
    followup_attack = max(
        (ally.get_stat("attack") for ally in battle.get_team(1 if actor in battle.team1.members else 2).alive() if ally != actor),
        default=actor.get_stat("attack"),
    )
    return 10.0 + followup_attack * 0.08


def estimate_damage_rider_value(actor, ability, target, battle):
    if target is None:
        return 0.0
    if ability.id == "hunters_mark":
        return 14.0 + estimate_threat(target, battle, 1 if actor in battle.team1.members else 2) * 0.05
    if ability.id == "drown_in_the_loch":
        return 12.0
    return 0.0


def estimate_refresh_or_extension_value(actor, ability, target, battle):
    player_num = 1 if actor in battle.team1.members else 2
    if ability.id == "golden_snare" and target is not None and target.has_status("root"):
        return 12.0 + estimate_threat(target, battle, player_num) * 0.05
    if ability.id == "vile_sabbath" and target is not None:
        value = 0.0
        for status in target.statuses:
            if status.duration > 0 and is_rulebook_status_condition(status.kind):
                value += 5.0
        if target.last_status_inflicted and is_rulebook_status_condition(target.last_status_inflicted):
            value += 6.0
        return value
    if ability.id == "falling_kingdom":
        value = 0.0
        for enemy_unit in battle.get_enemy(player_num).alive():
            if enemy_unit.has_status("root"):
                value += 12.0 + estimate_status_value("weaken", actor, enemy_unit, battle) * 0.4
            else:
                value += estimate_status_value("root", actor, enemy_unit, battle) * 0.7
        return value
    if ability.id == "cauldron_bubble" and target is not None:
        return sum(
            4.0
            for status in target.statuses
            if status.duration > 0 and is_rulebook_status_condition(status.kind)
        )
    return 0.0


def focus_fire_status_bonus(target):
    if target is None:
        return 0.0
    bonus = 0.0
    for kind, value in {
        "expose": 8.0,
        "root": 6.0,
        "shock": 5.0,
        "weaken": 4.0,
        "spotlight": 4.0,
        "no_heal": 6.0,
        "burn": 3.0,
    }.items():
        if target.has_status(kind):
            bonus += value
    if flat_damage_rider_bonus(target) > 0:
        bonus += 5.0
    return min(bonus, 14.0)


def redundant_status_penalty(battle, player_num, actor, action):
    if action.get("type") != "ability":
        return 0.0
    target = action.get("target")
    if target is None:
        return 0.0
    ability = action["ability"]
    if estimate_ko_chance_or_certainty(actor, ability, target, battle) >= 1.0:
        return 0.0
    mode = get_mode(actor, ability)
    statuses = [status for status in (mode.status, mode.status2, mode.status3) if status]
    if not statuses:
        return 0.0
    legal_targets = get_legal_targets(battle, player_num, actor, ability)
    penalty = 0.0
    for status in statuses:
        if not target.has_status(status):
            continue
        if any(other is not target and not other.has_status(status) for other in legal_targets):
            penalty += 10.0
        else:
            penalty += 4.0
    return penalty


def _team_member_ids(battle, player_num):
    return {unit.defn.id for unit in battle.get_team(player_num).members}


def composition_plan_bonus(battle, player_num, actor, action):
    team_ids = _team_member_ids(battle, player_num)
    target = action.get("target")
    score = 0.0

    if action.get("type") == "ability":
        ability = action["ability"]
        aid = ability.id
        enemy_team = battle.get_enemy(player_num)
        has_root_shell = bool(team_ids & {"green_knight", "rapunzel", "briar_rose", "witch_of_the_woods"})
        has_collapse_shell = bool(team_ids & {"lucky_constantine", "rapunzel", "prince_charming"}) and bool(
            team_ids & {"robin_hooded_avenger", "frederic", "risa_redcloak", "little_jack", "pinocchio"}
        )

        if target is not None and has_root_shell and target.has_status("root") and estimate_damage(actor, ability, target, battle) > 0:
            score += 10.0
        if target is not None and has_root_shell and aid in {"heros_bargain", "golden_snare", "bring_down", "creeping_doubt", "thorn_snare", "edict", "ominous_gale", "trapping_blow"}:
            already_rooted = any(enemy.has_status("root") for enemy in enemy_team.alive())
            if already_rooted and not target.has_status("root") and estimate_ko_chance_or_certainty(actor, ability, target, battle) < 1.0:
                score -= 6.0

        if target is not None and has_collapse_shell and (target.has_status("expose") or flat_damage_rider_bonus(target) > 0 or target.has_status("spotlight")):
            score += 8.0

        if "matchstick_liesl" in team_ids and aid == "cauterize" and target is not None:
            if not target.has_status("no_heal") and is_primary_support(target, enemy_team):
                score += 14.0
            if target.has_status("no_heal") and estimate_damage(actor, ability, target, battle) > 0:
                score += 8.0

        if "pinocchio" in team_ids and actor.defn.id == "pinocchio":
            malice = actor.ability_charges.get("malice", 0)
            if actor.slot == SLOT_FRONT and aid != "blood_pact":
                score += 6.0 if malice < 3 else 10.0
            if malice >= 3 and target is not None and estimate_damage(actor, ability, target, battle) > 0:
                score += 8.0

        if "rumpelstiltskin" in team_ids and aid in {"bless", "decree", "straw_to_gold"}:
            score += 8.0

        if "sea_wench_asha" in team_ids and actor.defn.id == "sea_wench_asha":
            if aid == "blood_pact":
                dangerous = actor.hp <= 90 or any(ally.hp / max(1, ally.max_hp) < 0.35 for ally in battle.get_team(player_num).alive())
                score += -10.0 if dangerous else 4.0
            if target is not None and (target.has_status("expose") or flat_damage_rider_bonus(target) > 0):
                score += 6.0

    if "pinocchio" in team_ids and actor.defn.id == "pinocchio" and action.get("type") == "swap" and actor.slot == SLOT_FRONT:
        if actor.ability_charges.get("malice", 0) < 3:
            score -= 12.0

    if "snowkissed_aurora" in team_ids and actor.defn.id == "snowkissed_aurora" and action.get("type") == "ability":
        if target is not None and target in battle.get_team(player_num).alive():
            if target.hp / max(1, target.max_hp) > 0.6 and estimate_heal_value(actor, action["ability"], target, battle) > 0:
                score -= 6.0

    return score


def would_status_deny_action(kind, target, battle):
    return kind in ("root", "taunt") and has_not_acted_yet(target)


def would_status_change_target_access(kind, target, battle, player_num):
    if kind not in ("spotlight", "expose", "root"):
        return False
    before = any(target in get_legal_targets(battle, player_num, ally, ability)
                 for ally in battle.get_team(player_num).alive()
                 for ability in list(ally.basics) + [ally.sig]
                 if can_use_ability(ally, ability, battle.get_team(player_num)))
    sim = copy.deepcopy(battle)
    sim_target = _find_unit(sim, _unit_key(target))
    if sim_target is None:
        return False
    sim_target.add_status(kind, 2)
    after = any(sim_target in get_legal_targets(sim, player_num, ally, ability)
                for ally in sim.get_team(player_num).alive()
                for ability in list(ally.basics) + [ally.sig]
                if can_use_ability(ally, ability, sim.get_team(player_num)))
    return after and not before


def estimate_status_value(status_kind, source, target, battle):
    if not status_kind or target is None or status_already_present(target, status_kind):
        return 0.0
    value = {
        "burn": 10.0,
        "weaken": 14.0,
        "expose": 16.0,
        "root": 20.0,
        "shock": 18.0,
        "spotlight": 20.0,
        "guard": 16.0,
    }.get(status_kind, 8.0)
    if would_status_deny_action(status_kind, target, battle):
        value += 12.0
    if would_status_change_target_access(status_kind, target, battle, 1 if source in battle.team1.members else 2):
        value += 14.0
    if status_kind == "shock":
        value += 4.0
        if target.get_stat("attack") >= 65:
            value += 8.0
        if has_not_acted_yet(target):
            value += 6.0
    if status_kind == "spotlight" and target.slot != SLOT_FRONT:
        player_num = 1 if source in battle.team1.members else 2
        melee_followup = sum(1 for ally in battle.get_team(player_num).alive() if ally != source and is_melee_now(ally))
        value += 10.0 + melee_followup * 10.0
    if status_kind == "root":
        enemy_team = battle.get_enemy(1 if source in battle.team1.members else 2)
        if enemy_team.alive():
            lowest_hp = min(enemy_team.alive(), key=lambda unit: unit.hp)
            if lowest_hp == target:
                value += 18.0
    return value


def estimate_item_value(actor, item, target, battle, secondary_target=None):
    value = 0.0
    if item is None:
        return -5.0
    if item.heal > 0 and target is not None:
        heal_amount = item.heal
        value += min(heal_amount, max(0, target.max_hp - target.hp)) * 1.4
    if getattr(item, "cleanse", False) and target is not None:
        value += 10.0 * sum(1 for status in target.statuses if status.duration > 0)
    if item.guard and target is not None:
        value += estimate_guard_value(target)
    if getattr(item, "atk_buff", 0) and target is not None:
        value += max(0, item.atk_buff) * 0.9
    if getattr(item, "def_buff", 0) and target is not None:
        value += max(0, item.def_buff) * 0.7
    if getattr(item, "spd_buff", 0) and target is not None:
        value += max(0, item.spd_buff) * 0.7
    if getattr(item, "atk_debuff", 0) and target is not None:
        value += max(0, item.atk_debuff) * 0.8
    if getattr(item, "def_debuff", 0) and target is not None:
        value += max(0, item.def_debuff) * 0.8
    if getattr(item, "spd_debuff", 0) and target is not None:
        value += max(0, item.spd_debuff) * 0.8
    if item.status and target is not None:
        value += estimate_status_value(item.status, actor, target, battle)
        if item.special == "nettle_smock" and is_primary_support(target, battle.get_enemy(1 if actor in battle.team1.members else 2)):
            value += 8.0
    if item.special == "magic_mirror" and target is not None and secondary_target is not None:
        value += estimate_swap_value(target, secondary_target, battle)
    if item.special == "cracked_stopwatch" and target is not None:
        value += 10.0 if target in battle.get_enemy(1 if actor in battle.team1.members else 2).alive() else 4.0
    value -= 5.0
    return value


def _simulate_swap_state(battle, actor, swap_target):
    player_num = 1 if actor in battle.team1.members else 2
    return simulate_single_action(battle, player_num, actor, {"type": "swap", "target": swap_target})


def estimate_swap_value(actor, swap_target, battle):
    player_num = 1 if actor in battle.team1.members else 2
    team = battle.get_team(player_num)
    enemy = battle.get_enemy(player_num)
    value = 0.0
    if actor.slot == SLOT_FRONT:
        actor_risk = threat_rank(actor, battle, player_num)
        target_risk = threat_rank(swap_target, battle, player_num)
        if actor.hp / max(1, actor.max_hp) < 0.45:
            value += 18.0
        value += max(0.0, swap_target.get_stat("defense") - actor.get_stat("defense")) * 1.2
        value += max(0.0, target_risk - actor_risk) * 0.3
    else:
        value += 6.0
    sim = _simulate_swap_state(battle, actor, swap_target)
    value += initiative_delta_score(sim, player_num)
    value += formation_safety_score(team, enemy, sim)
    return value


def estimate_ko_chance_or_certainty(actor, ability, target, battle):
    if target is None:
        return 0.0
    dmg = estimate_damage(actor, ability, target, battle)
    if dmg >= target.hp:
        return 1.0
    return dmg / max(1, target.hp)


def estimate_target_access(actor, target, battle):
    player_num = 1 if actor in battle.team1.members else 2
    access = 0.0
    team = battle.get_team(player_num)
    for ally in team.alive():
        for ability in list(ally.basics) + [ally.sig]:
            if can_use_ability(ally, ability, team) and target in get_legal_targets(battle, player_num, ally, ability):
                access += 1.0
                break
    return access


def target_access_score(actor, target, battle):
    if target is None:
        return 0.0
    access = estimate_target_access(actor, target, battle)
    threat = estimate_threat(target, battle, 1 if actor in battle.team1.members else 2)
    return access * 4.0 + threat * 0.1


def count_recharge_pressure(unit):
    return max(0, get_recharge_limit(unit) - unit.ranged_uses)


def ability_uses_until_recharge(unit):
    return count_recharge_pressure(unit)


def remaining_ability_uses_before_recharge(unit):
    return count_recharge_pressure(unit)


def is_recharge_sensitive(unit):
    return is_ranged_now(unit) or is_mixed_class(unit)


def would_action_force_recharge_next_round(unit, action):
    if action.get("type") != "ability" or not is_ranged_now(unit):
        return False
    return ability_uses_until_recharge(unit) <= 1


def will_action_trigger_recharge(actor, action):
    return would_action_force_recharge_next_round(actor, action)


def project_recharge_state_after_action(actor, action, battle):
    sim = simulate_single_action(battle, 1 if actor in battle.team1.members else 2, actor, action)
    sim_actor = _find_unit(sim, _unit_key(actor))
    if sim_actor is None:
        return {"must_recharge": False, "ranged_uses": 0}
    return {"must_recharge": sim_actor.must_recharge, "ranged_uses": sim_actor.ranged_uses}


def recharge_pressure_score(unit, action, battle):
    score = 0.0
    if action.get("type") == "ability" and is_recharge_sensitive(unit):
        if would_action_force_recharge_next_round(unit, action):
            score -= 14.0
            if action.get("ability") and action["ability"].category == "signature":
                score += 6.0
    return score


def score_recharge_tempo(actor, action, battle):
    score = recharge_pressure_score(actor, action, battle)
    return score


def project_next_round_frontline(team):
    return team.frontline()


def project_frontline_after_turn(team, plan_state):
    return plan_state.frontline()


def project_frontline_speed(team, plan_state):
    frontline = project_frontline_after_turn(team, plan_state)
    return frontline.get_stat("speed") if frontline else 0


def _project_speed_with_march_hare(frontline, enemy_frontline):
    speed = frontline.get_stat("speed") if frontline else 0
    if enemy_frontline and enemy_frontline.defn.id == "march_hare" and frontline:
        speed = max(1, speed - 15)
    return speed


def project_initiative_value(battle, player_num):
    own = battle.get_team(player_num).frontline()
    enemy = battle.get_enemy(player_num).frontline()
    own_speed = _project_speed_with_march_hare(own, enemy)
    enemy_speed = _project_speed_with_march_hare(enemy, own)
    if own_speed > enemy_speed:
        return 1.0
    if own_speed < enemy_speed:
        return -1.0
    return 0.2 if battle.prev_loser == player_num else -0.2


def initiative_delta_score(plan_state, player_num):
    return project_initiative_value(plan_state, player_num) * 18.0


def formation_safety_score(team, enemy, state):
    score = 0.0
    frontline = team.frontline()
    if frontline:
        score += frontline.get_stat("defense") * 0.4
        if frontline.has_status("guard"):
            score += 10.0
        if frontline.has_status("expose"):
            score -= 12.0
    for ally in team.alive():
        if ally.slot != SLOT_FRONT and is_fragile(ally):
            enemy_melee_access = any(is_melee_now(e) for e in enemy.alive())
            score += 6.0 if not enemy_melee_access else 2.0
    return score


def estimate_threat(unit, battle, viewer_player):
    if unit.ko:
        return 0.0
    score = unit.get_stat("attack") * 1.2 + unit.get_stat("speed") * 0.8
    if has_not_acted_yet(unit):
        score += 18.0
    if is_primary_support(unit, battle.get_enemy(viewer_player)):
        score += 18.0
    if is_primary_carry(unit, battle.get_enemy(viewer_player)):
        score += 12.0
    if is_recharge_sensitive(unit) and is_recharge_locked(unit):
        score -= 14.0
    return score


def threat_rank(unit, battle, player_num):
    return estimate_threat(unit, battle, player_num)


def motif_burst_now(before, after, player_num, actor, action):
    target = action.get("target")
    if target is None:
        return 0.0
    sim_target = _find_unit(after, _unit_key(target))
    if sim_target and sim_target.ko:
        bonus = 30.0
        if not target.acted:
            bonus += 18.0
        return bonus
    return 0.0


def motif_setup_then_cash(before, after, player_num, actor, action):
    if action.get("type") != "ability":
        return 0.0
    mode = get_mode(actor, action["ability"])
    statuses = [s for s in (mode.status, mode.status2, mode.status3) if s]
    if not statuses or action.get("target") is None:
        return 0.0
    bonus = 0.0
    for status in statuses:
        bonus += estimate_status_value(status, actor, action["target"], before) * 0.5
        if status in ("spotlight", "expose", "root", "shock"):
            bonus += 6.0
    return bonus


def motif_deny_before_action(before, after, player_num, actor, action):
    target = action.get("target")
    if target is None or target.acted:
        return 0.0
    if action.get("type") == "swap":
        return 0.0
    mode = get_mode(actor, action["ability"]) if action.get("type") == "ability" else None
    statuses = [s for s in (mode.status, mode.status2, mode.status3) if s] if mode else []
    return 14.0 if any(status in CONTROL_STATUSES for status in statuses) else 0.0


def motif_guard_save(before, after, player_num, actor, action):
    if action.get("type") == "item" and action.get("artifact") and action["artifact"].guard and action.get("target") is not None:
        return estimate_guard_value(action["target"])
    if action.get("type") == "ability":
        mode = get_mode(actor, action["ability"])
        target = action.get("target")
        if mode.guard_self and not actor.has_status("guard"):
            return 14.0
        if mode.guard_target and estimate_guard_value(target) > 0:
            return 14.0
        if mode.guard_frontline_ally:
            front = before.get_team(player_num).frontline()
            if front is not None and front != actor and estimate_guard_value(front) > 0:
                return 14.0
        if mode.guard_all_allies and any(not ally.has_status("guard") for ally in before.get_team(player_num).alive()):
            return 14.0
    return 0.0


def motif_frontline_initiative_flip(before, after, player_num, actor, action):
    if action.get("type") != "swap":
        return 0.0
    return max(0.0, initiative_delta_score(after, player_num) - initiative_delta_score(before, player_num))


def motif_recharge_trap(before, after, player_num, actor, action):
    return 0.0


def motif_backline_access_open(before, after, player_num, actor, action):
    target = action.get("target")
    if target is None:
        return 0.0
    before_target = _find_unit(before, _unit_key(target))
    after_target = _find_unit(after, _unit_key(target))
    if before_target is None or after_target is None:
        return 0.0
    before_access = estimate_target_access(actor, before_target, before)
    after_actor = _find_unit(after, _unit_key(actor)) or actor
    after_access = estimate_target_access(after_actor, after_target, after)
    return max(0.0, after_access - before_access) * 7.0


def motif_last_stand_conversion(before, after, player_num, actor, action):
    if action.get("type") == "ability" and action["ability"].category == "twist":
        return 20.0 + motif_burst_now(before, after, player_num, actor, action)
    return 0.0


def motif_position_reset(before, after, player_num, actor, action):
    if action.get("type") != "swap":
        return 0.0
    return 10.0 if is_mixed_class(actor) or is_mixed_class(action.get("target")) else 4.0


def motif_status_stack_pressure(before, after, player_num, actor, action):
    target = action.get("target")
    if target is None:
        return 0.0
    after_target = _find_unit(after, _unit_key(target))
    if after_target is None:
        return 0.0
    before_count = len([s for s in target.statuses if s.duration > 0])
    after_count = len([s for s in after_target.statuses if s.duration > 0])
    return max(0.0, after_count - before_count) * 8.0


def tactical_motif_score(before, after, player_num, actor, action):
    return (
        motif_burst_now(before, after, player_num, actor, action)
        + motif_setup_then_cash(before, after, player_num, actor, action)
        + motif_deny_before_action(before, after, player_num, actor, action)
        + motif_guard_save(before, after, player_num, actor, action)
        + motif_frontline_initiative_flip(before, after, player_num, actor, action)
        + motif_recharge_trap(before, after, player_num, actor, action)
        + motif_backline_access_open(before, after, player_num, actor, action)
        + motif_last_stand_conversion(before, after, player_num, actor, action)
        + motif_position_reset(before, after, player_num, actor, action)
        + motif_status_stack_pressure(before, after, player_num, actor, action)
    )


def evaluate_board_state_basic(battle, for_player):
    own_team = battle.get_team(for_player)
    enemy_team = battle.get_enemy(for_player)
    own_alive = own_team.alive()
    enemy_alive = enemy_team.alive()
    if not own_alive:
        return -10000.0
    if not enemy_alive:
        return 10000.0
    score = 0.0
    score += sum(u.hp / max(1, u.max_hp) for u in own_alive) * 90.0
    score -= sum(u.hp / max(1, u.max_hp) for u in enemy_alive) * 90.0
    score += sum(34.0 for u in enemy_team.members if u.ko)
    score -= sum(34.0 for u in own_team.members if u.ko)
    score += formation_safety_score(own_team, enemy_team, battle)
    score -= formation_safety_score(enemy_team, own_team, battle) * 0.7
    for unit in own_alive:
        score -= 8.0 if is_recharge_locked(unit) else 0.0
        score += sum(4.0 for s in unit.statuses if s.kind == "guard" and s.duration > 0)
        score -= sum(5.0 for s in unit.statuses if s.kind in RULEBOOK_DANGEROUS_STATUSES and s.duration > 0)
    for unit in enemy_alive:
        score += sum(4.0 for s in unit.statuses if s.kind in RULEBOOK_DANGEROUS_STATUSES and s.duration > 0)
    return score


def evaluate_board_state_full(battle, for_player):
    score = evaluate_board_state_basic(battle, for_player)
    enemy = battle.get_enemy(for_player)
    own = battle.get_team(for_player)
    score += initiative_delta_score(battle, for_player)
    score += sum(threat_rank(u, battle, for_player) * 0.05 for u in enemy.alive())
    score -= sum(threat_rank(u, battle, 3 - for_player) * 0.03 for u in own.alive())
    return score


def evaluate_state(battle, for_player):
    return evaluate_board_state_full(battle, for_player)


def evaluate_immediate_resolution(before, after, player_num, actor, action):
    before_enemy = before.get_enemy(player_num)
    after_enemy = after.get_enemy(player_num)
    before_team = before.get_team(player_num)
    after_team = after.get_team(player_num)
    damage_dealt = sum(u.hp for u in before_enemy.members) - sum(u.hp for u in after_enemy.members)
    damage_taken = sum(u.hp for u in before_team.members) - sum(u.hp for u in after_team.members)
    enemy_kos = sum(1 for u in after_enemy.members if u.ko) - sum(1 for u in before_enemy.members if u.ko)
    own_kos = sum(1 for u in after_team.members if u.ko) - sum(1 for u in before_team.members if u.ko)
    score = damage_dealt * 1.6 - damage_taken * 1.1 + enemy_kos * 28.0 - own_kos * 32.0
    if action.get("type") == "ability":
        mode = get_mode(actor, action["ability"])
        target = action.get("target")
        if target is not None:
            score += target_access_score(actor, target, before)
            score += focus_fire_status_bonus(target)
            for status in (mode.status, mode.status2, mode.status3):
                score += estimate_status_value(status, actor, target, before)
            score += estimate_repentance_rider(actor, action["ability"], target, before)
            score += estimate_damage_rider_value(actor, action["ability"], target, before)
            score += estimate_refresh_or_extension_value(actor, action["ability"], target, before)
        score -= redundant_status_penalty(before, player_num, actor, action)
        if mode.spread:
            legal_targets = get_legal_targets(before, player_num, actor, action["ability"])
            score += 0.6 * estimate_spread_damage(actor, action["ability"], legal_targets, before)
        score += estimate_heal_value(actor, action["ability"], action.get("target"), before)
        score += composition_plan_bonus(before, player_num, actor, action)
    elif action.get("type") == "swap":
        score += estimate_swap_value(actor, action["target"], before)
        score += composition_plan_bonus(before, player_num, actor, action)
    elif action.get("type") == "item":
        score += estimate_item_value(actor, action.get("artifact"), action.get("target"), before, action.get("swap_target"))
        score += composition_plan_bonus(before, player_num, actor, action)
    elif action.get("type") == "skip":
        score -= 12.0
    return score


def evaluate_end_of_turn_state(battle, player_num):
    own = battle.get_team(player_num)
    enemy = battle.get_enemy(player_num)
    score = evaluate_board_state_full(battle, player_num) * 0.55
    score += sum(estimate_target_access(ally, target, battle)
                 for ally in own.alive()
                 for target in enemy.alive()) * 0.35
    score += sum(8.0 for unit in enemy.alive() if any(s.kind in CONTROL_STATUSES and s.duration > 0 for s in unit.statuses))
    return score


def evaluate_next_round_state(battle, player_num):
    score = initiative_delta_score(battle, player_num)
    own = battle.get_team(player_num)
    enemy = battle.get_enemy(player_num)
    score += formation_safety_score(own, enemy, battle)
    score -= sum(10.0 for unit in own.alive() if is_recharge_locked(unit))
    score += sum(8.0 for unit in enemy.alive() if is_recharge_locked(unit))
    for unit in own.alive():
        if unit.defn.id == "pinocchio" and unit.slot == SLOT_FRONT:
            malice = unit.ability_charges.get("malice", 0)
            score += 8.0 if malice >= 2 else 4.0
    return score


def risk_penalty(before, after, player_num, actor, action):
    score = 0.0
    sim_actor = _find_unit(after, _unit_key(actor))
    if sim_actor is not None:
        if is_fragile(sim_actor) and sim_actor.slot == SLOT_FRONT and action.get("type") != "swap":
            score += 10.0
        if sim_actor.has_status("expose"):
            score += 8.0
    score += max(0.0, -recharge_pressure_score(actor, action, before))
    if action.get("type") == "ability" and action.get("target") is not None:
        target = action["target"]
        if target.item.id == "spiked_mail" and estimate_damage(actor, action["ability"], target, before) > 0:
            score += 10.0
    if action.get("type") == "ability" and action["ability"].category == "twist" and not motif_burst_now(before, after, player_num, actor, action):
        score += 10.0
    return score


def _remaining_allies_to_act(battle, player_num, actor):
    team = battle.get_team(player_num)
    order = [team.get_slot(slot) for slot in CLOCKWISE_ORDER]
    actor_index = next((idx for idx, unit in enumerate(order) if unit == actor), len(order) - 1)
    return [_unit_key(unit) for unit in order[actor_index + 1:] if unit is not None and not unit.ko]


def score_partial_turn_sequence(state, player_num):
    return evaluate_end_of_turn_state(state, player_num)


def _build_candidates(battle, player_num, actor, is_extra, swap_used, swap_queued):
    team = battle.get_team(player_num)
    enemy = battle.get_enemy(player_num)
    if actor.must_recharge:
        return [{"type": "skip"}]
    candidates = []
    abilities = actor.all_active_abilities()

    for ability in abilities:
        if not can_use_ability(actor, ability, team):
            continue
        mode = get_mode(actor, ability)
        targets = get_legal_targets(battle, player_num, actor, ability)
        if mode.spread:
            if enemy.alive():
                candidates.append({"type": "ability", "ability": ability, "target": None})
            continue
        for target in targets:
            if ability.id == "subterfuge":
                for swap_target in get_subterfuge_swap_targets(battle, player_num, target):
                    candidates.append({
                        "type": "ability",
                        "ability": ability,
                        "target": target,
                        "swap_target": swap_target,
                    })
            else:
                candidates.append({"type": "ability", "ability": ability, "target": target})

    if not is_extra and not swap_used and not swap_queued and not actor.has_status("root"):
        for ally in [unit for unit in team.alive() if unit != actor]:
            candidates.append({"type": "swap", "target": ally})

    queued_artifact_ids = {
        action["artifact"].id
        for unit in team.members
        for action in (unit.queued, unit.queued2)
        if action and action.get("type") == "item" and action.get("artifact") is not None
    }

    for artifact_state in ready_active_artifacts(team):
        artifact = artifact_state.artifact
        if artifact.id in queued_artifact_ids:
            continue
        targets = get_legal_item_targets(battle, player_num, actor, artifact=artifact)
        if artifact.id == "magic_mirror":
            for target in targets:
                for swap_target in get_legal_item_targets(
                    battle,
                    player_num,
                    actor,
                    artifact=artifact,
                    primary_target=target,
                ):
                    candidates.append({
                        "type": "item",
                        "artifact": artifact,
                        "target": target,
                        "swap_target": swap_target,
                    })
        else:
            for target in targets:
                candidates.append({"type": "item", "artifact": artifact, "target": target})

    candidates.append({"type": "skip"})
    return candidates


def fast_pre_score(action, battle, player_num, actor):
    score = 0.0
    target = action.get("target")
    if action.get("type") == "ability":
        ability = action["ability"]
        mode = get_mode(actor, ability)
        if target is not None:
            score += estimate_damage(actor, ability, target, battle) * 1.2
            score += estimate_ko_chance_or_certainty(actor, ability, target, battle) * 18.0
            score += target_access_score(actor, target, battle)
            score += focus_fire_status_bonus(target)
            for status in (mode.status, mode.status2, mode.status3):
                score += estimate_status_value(status, actor, target, battle)
            score += estimate_repentance_rider(actor, ability, target, battle)
            score += estimate_damage_rider_value(actor, ability, target, battle)
            score += estimate_refresh_or_extension_value(actor, ability, target, battle)
            if not target.acted:
                score += 8.0
        score -= redundant_status_penalty(battle, player_num, actor, action)
        if mode.spread:
            legal_targets = get_legal_targets(battle, player_num, actor, ability)
            score += estimate_spread_damage(actor, ability, legal_targets, battle) * 0.7
        score += estimate_heal_value(actor, ability, target, battle)
        score += score_recharge_tempo(actor, action, battle)
        score += composition_plan_bonus(battle, player_num, actor, action)
    elif action.get("type") == "swap":
        score += estimate_swap_value(actor, action["target"], battle)
        score += composition_plan_bonus(battle, player_num, actor, action)
    elif action.get("type") == "item":
        score += estimate_item_value(actor, action.get("artifact"), target, battle, action.get("swap_target"))
        score += composition_plan_bonus(battle, player_num, actor, action)
    else:
        score -= 12.0
    return _apply_char_hooks(battle, player_num, actor, action, score)


def generate_ranked_candidates(battle, player_num, actor, is_extra, swap_used, swap_queued):
    candidates = _build_candidates(battle, player_num, actor, is_extra, swap_used, swap_queued)
    return sorted(candidates, key=lambda action: fast_pre_score(action, battle, player_num, actor), reverse=True)


def build_ranked_candidates_for_actor(battle, player_num, actor):
    swap_queued = any(unit.queued and unit.queued.get("type") == "swap" for unit in battle.get_team(player_num).members)
    return generate_ranked_candidates(battle, player_num, actor, False, battle.swap_used_this_turn, swap_queued)


def beam_plan_remaining_turn(sim_battle, player_num, remaining_allies, beam_width=BEAM_WIDTH, depth=None):
    if not remaining_allies:
        return evaluate_end_of_turn_state(sim_battle, player_num)
    beams = [(sim_battle, 0.0)]
    for ally_key in remaining_allies[:depth]:
        new_beams = []
        for beam_state, beam_score in beams:
            ally = _find_unit(beam_state, ally_key)
            if ally is None or ally.ko:
                new_beams.append((beam_state, beam_score))
                continue
            actions = top_n(
                build_ranked_candidates_for_actor(beam_state, player_num, ally),
                beam_width,
                key=lambda action: fast_pre_score(action, beam_state, player_num, ally),
            )
            for action in actions:
                child = simulate_single_action(beam_state, player_num, ally, action)
                action_score = evaluate_immediate_resolution(beam_state, child, player_num, ally, action)
                action_score += tactical_motif_score(beam_state, child, player_num, ally, action)
                action_score -= risk_penalty(beam_state, child, player_num, ally, action)
                new_beams.append((child, beam_score + action_score))
        beams = top_n(new_beams, beam_width, key=lambda pair: pair[1])
    return max(score_partial_turn_sequence(state, player_num) + acc for state, acc in beams)


def score_action_context(before, after, player_num, actor, action, profile="quick"):
    settings = _ai_profile(profile)
    remaining_allies = _remaining_allies_to_act(before, player_num, actor)
    immediate_score = evaluate_immediate_resolution(before, after, player_num, actor, action)
    end_of_turn_score = beam_plan_remaining_turn(
        after,
        player_num,
        remaining_allies,
        beam_width=settings["beam_width"],
        depth=len(remaining_allies),
    )
    next_round_score = evaluate_next_round_state(after, player_num)
    motif_score = tactical_motif_score(before, after, player_num, actor, action)
    adapter_score = character_adapter_score(after, player_num, actor, action)
    penalty = risk_penalty(before, after, player_num, actor, action)
    return (
        immediate_score
        + end_of_turn_score * settings["end_of_turn_weight"]
        + next_round_score * settings["next_round_weight"]
        + motif_score
        + adapter_score
        - penalty
    )


def _hook_ashen_ella(battle, player_num, actor, action, score):
    if actor.slot == SLOT_FRONT:
        return score
    if action.get("type") == "ability":
        ability = action["ability"]
        if ability.id in ("crowstorm", "fae_blessing"):
            score += 90.0
    if action.get("type") == "swap":
        score -= 40.0
    return score


def _hook_gretel(battle, player_num, actor, action, score):
    if action.get("type") == "ability" and action["ability"].category == "twist":
        target = action.get("target")
        if target is not None:
            score += 16.0 * estimate_ko_chance_or_certainty(actor, action["ability"], target, battle)
        return score
    if action.get("type") == "ability" and action.get("target") is not None and action["target"].has_status("burn"):
        score += 12.0
    return score


def _hook_constantine(battle, player_num, actor, action, score):
    if action.get("type") != "ability":
        return score
    target = action.get("target")
    if target is not None:
        if target.has_status("expose"):
            score += 16.0
        if target.slot != SLOT_FRONT and is_idle_target(target):
            score += 18.0
        if target.slot != SLOT_FRONT and is_primary_carry(target, battle.get_enemy(player_num)):
            score += 8.0
    if action["ability"].id == "subterfuge" and action.get("swap_target") is not None:
        if is_primary_carry(action["swap_target"], battle.get_enemy(player_num)):
            score += 18.0
    return score


def _hook_rapunzel(battle, player_num, actor, action, score):
    if action.get("type") != "ability":
        return score
    target = action.get("target")
    if target is None:
        return score
    if actor.ability_charges.get("flowing_locks_ready", 0) > 0 or actor.ability_charges.get("severed_tether_active", 0) > 0:
        normal_targets = get_legal_targets(
            battle,
            player_num,
            actor,
            action["ability"],
            include_rapunzel_override=False,
        )
        if target not in normal_targets:
            score += 18.0
            if is_primary_carry(target, battle.get_enemy(player_num)):
                score += 10.0
            if target.hp / max(1, target.max_hp) < 0.45:
                score += 10.0
    return score


def _hook_hunold(battle, player_num, actor, action, score):
    if action.get("type") != "ability":
        return score
    target = action.get("target")
    if target is None:
        return score
    mode = get_mode(actor, action["ability"])
    statuses = [s for s in (mode.status, mode.status2, mode.status3) if s]
    if target.has_status("shock"):
        score += 18.0
    if "shock" in statuses and target.get_stat("attack") >= 65:
        score += 10.0
    if action["ability"].category == "twist" and mode.spread:
        score += 14.0
    return score


def _hook_briar_rose(battle, player_num, actor, action, score):
    if action.get("type") != "ability":
        return score
    target = action.get("target")
    if target is None:
        return score
    mode = get_mode(actor, action["ability"])
    statuses = [s for s in (mode.status, mode.status2, mode.status3) if s]
    enemy_alive = battle.get_enemy(player_num).alive()
    lowest_hp = min(enemy_alive, key=lambda unit: unit.hp).defn.id if enemy_alive else None
    if "root" in statuses and target.defn.id == lowest_hp:
        score += 48.0
    if target.has_status("root") and action["ability"].id == "creeping_doubt":
        score += 18.0
    if action["ability"].id == "thorn_snare" and target.defn.id == lowest_hp:
        score += 22.0
    return score


def _hook_robin(battle, player_num, actor, action, score):
    if action.get("type") != "ability":
        return score
    target = action.get("target")
    mode = get_mode(actor, action["ability"])
    if target is not None and target.slot != SLOT_FRONT:
        score += 10.0
        if target.has_status("guard") and action["ability"].id == "snipe_shot" and actor.slot != SLOT_FRONT:
            score += 14.0
    if mode.spread:
        score += 12.0
    if any(s == "root" for s in (mode.status, mode.status2, mode.status3)):
        score += 8.0
    return score


def _hook_pinocchio(battle, player_num, actor, action, score):
    malice = actor.ability_charges.get("malice", 0)
    if action.get("type") == "swap" and actor.slot == SLOT_FRONT and malice < 3:
        score -= 18.0
    if action.get("type") == "ability":
        if actor.slot == SLOT_FRONT:
            score += 6.0 if malice < 3 else 10.0
        elif malice >= 3 and is_mixed_class(actor):
            score += 8.0
        if action["ability"].category == "twist" and malice >= 4:
            score += 16.0
    return score


def _hook_rumpelstiltskin(battle, player_num, actor, action, score):
    if action.get("type") == "ability" and actor.slot == SLOT_FRONT:
        buffed_stats = {buff.stat for unit in battle.team1.alive() + battle.team2.alive() if unit != actor for buff in unit.buffs if buff.duration > 0}
        score += len(buffed_stats) * 3.0
    return score


def _hook_witch(battle, player_num, actor, action, score):
    target = action.get("target")
    if action.get("type") == "ability" and target is not None:
        active_statuses = len([status for status in target.statuses if status.duration > 0])
        score += active_statuses * 8.0
    return score


def _hook_matchstick_liesl(battle, player_num, actor, action, score):
    if action.get("type") == "ability" and action["ability"].id == "cauterize":
        if any(unit.defn.cls == "Cleric" for unit in battle.get_enemy(player_num).alive()):
            score += 16.0
    return score


def _hook_risa(battle, player_num, actor, action, score):
    hp_ratio = actor.hp / max(1, actor.max_hp)
    if action.get("type") == "swap" and actor.slot == SLOT_FRONT and 0.15 < hp_ratio < 0.5:
        score -= 14.0
    if action.get("type") == "ability" and hp_ratio < 0.5:
        score += 10.0
    return score


def _hook_lady_of_reflections(battle, player_num, actor, action, score):
    if action.get("type") == "ability":
        target = action.get("target")
        mode = get_mode(actor, action["ability"])
        if target is not None and (mode.guard_target or mode.guard_frontline_ally) and target.slot == SLOT_FRONT:
            score += 12.0
    return score


def _hook_porcus(battle, player_num, actor, action, score):
    if action.get("type") != "ability" or action["ability"].id != "not_by_the_hair":
        return score
    enemy_player = 2 if player_num == 1 else 1
    incoming_attackers = 0
    enemy_team = battle.get_enemy(player_num)
    for enemy_unit in enemy_team.alive():
        abilities = list(enemy_unit.basics) + [enemy_unit.sig]
        if len(enemy_team.alive()) == 1 and enemy_team.alive()[0] == enemy_unit:
            abilities = abilities + [enemy_unit.defn.twist]
        for ability in abilities:
            if ability.passive or not can_use_ability(enemy_unit, ability, enemy_team):
                continue
            if actor not in get_legal_targets(battle, enemy_player, enemy_unit, ability):
                continue
            if estimate_damage(enemy_unit, ability, actor, battle) <= 0:
                continue
            incoming_attackers += 1
            break
    score += 12.0 if actor.slot == SLOT_FRONT else 6.0
    score += incoming_attackers * (12.0 if actor.slot == SLOT_FRONT else 8.0)
    if actor.hp / max(1, actor.max_hp) < 0.65:
        score += 14.0
    return score


def _apply_char_hooks(battle, player_num, actor, action, score):
    hook = _CHAR_HOOKS.get(actor.defn.id)
    if hook:
        return hook(battle, player_num, actor, action, score)
    return score


def character_adapter_score(battle, player_num, actor, action):
    return _apply_char_hooks(battle, player_num, actor, action, 0.0)


_CHAR_HOOKS = {
    "ashen_ella": _hook_ashen_ella,
    "gretel": _hook_gretel,
    "lucky_constantine": _hook_constantine,
    "hunold_the_piper": _hook_hunold,
    "briar_rose": _hook_briar_rose,
    "robin_hooded_avenger": _hook_robin,
    "rapunzel": _hook_rapunzel,
    "pinocchio": _hook_pinocchio,
    "rumpelstiltskin": _hook_rumpelstiltskin,
    "witch_of_the_woods": _hook_witch,
    "matchstick_liesl": _hook_matchstick_liesl,
    "risa_redcloak": _hook_risa,
    "lady_of_reflections": _hook_lady_of_reflections,
    "porcus_iii": _hook_porcus,
}


def _heuristic_bonus(battle, player_num, actor, action):
    return fast_pre_score(action, battle, player_num, actor)


def _initiative_bonus(battle, player_num, actor, action):
    score = 0.0
    target = action.get("target")
    if target is not None and not target.acted:
        score += 6.0
    if action.get("type") == "swap":
        sim = _simulate_swap_state(battle, actor, action["target"])
        score += max(0.0, initiative_delta_score(sim, player_num) - initiative_delta_score(battle, player_num))
    return score


def _recharge_bonus(battle, player_num, actor, action):
    return score_recharge_tempo(actor, action, battle)


def pick_action(battle, player_num, actor, is_extra, swap_used, swap_queued, profile="quick"):
    settings = _ai_profile(profile)
    candidates = generate_ranked_candidates(battle, player_num, actor, is_extra, swap_used, swap_queued)
    limit = settings["top_level_candidates"]
    shortlisted = candidates if len(candidates) <= limit else candidates[:limit]
    best_action = {"type": "skip"}
    best_score = -float("inf")

    for action in shortlisted:
        after = simulate_single_action(battle, player_num, actor, action)
        total = score_action_context(battle, after, player_num, actor, action, profile=profile)
        total += _initiative_bonus(battle, player_num, actor, action)
        total += _recharge_bonus(battle, player_num, actor, action)
        if total > best_score:
            best_score = total
            best_action = action

    return best_action
