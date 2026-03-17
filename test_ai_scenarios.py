import math

from data import ROSTER, CLASS_BASICS, ITEMS
from logic import can_use_ability, compute_damage, create_team, end_round, get_legal_item_targets, get_legal_targets, get_mode, resolve_queued_action
from models import BattleState
import ai


ROSTER_BY_ID = {d.id: d for d in ROSTER}
ITEMS_BY_ID = {i.id: i for i in ITEMS}


def ability_by_id(defn, ability_id):
    for ability in list(defn.sig_options) + list(CLASS_BASICS[defn.cls]) + [defn.twist]:
        if ability.id == ability_id:
            return ability
    raise KeyError(f"Ability {ability_id} not found for {defn.id}")


def make_pick(defn_id, sig_id=None, basics=None, item_id="family_seal"):
    defn = ROSTER_BY_ID[defn_id]
    sig = ability_by_id(defn, sig_id or defn.sig_options[0].id)
    basic_ids = basics or [CLASS_BASICS[defn.cls][0].id, CLASS_BASICS[defn.cls][1].id]
    return {
        "definition": defn,
        "signature": sig,
        "basics": [ability_by_id(defn, bid) for bid in basic_ids],
        "item": ITEMS_BY_ID[item_id],
    }


def make_battle(team1_picks, team2_picks):
    return BattleState(
        team1=create_team("P1", team1_picks),
        team2=create_team("P2", team2_picks),
    )


def choose_action(battle, player_num, actor_slot):
    actor = battle.get_team(player_num).get_slot(actor_slot)
    return ai.pick_action(
        battle=battle,
        player_num=player_num,
        actor=actor,
        is_extra=False,
        swap_used=False,
        swap_queued=False,
    )


def scenario_target_access_spotlight():
    battle = make_battle(
        [
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("prince_charming", "edict", basics=["impose", "decree"], item_id="health_potion"),
            make_pick("green_knight", "heros_bargain", basics=["impose", "decree"], item_id="health_potion"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    action = choose_action(battle, 1, "back_left")
    assert action["type"] == "ability"
    assert action["ability"].id == "edict"
    assert action["target"].defn.id == "ashen_ella"


def scenario_recharge_trap_shock():
    battle = make_battle(
        [
            make_pick("hunold_the_piper", "haunting_rhythm"),
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("robin_hooded_avenger", "snipe_shot"),
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
        ],
    )
    target = battle.team2.get_slot("front")
    target.ranged_uses = 1
    action = choose_action(battle, 1, "front")
    assert action["type"] == "ability"
    assert action["ability"].id == "haunting_rhythm"
    assert action["target"].defn.cls in {"Ranger", "Mage", "Cleric", "Warlock", "Noble"}


def scenario_ella_backline_exception():
    battle = make_battle(
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("gretel", "hot_mitts"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    action = choose_action(battle, 1, "back_left")
    assert action["type"] == "ability"
    assert action["ability"].id in {"crowstorm", "fae_blessing"}


def scenario_briar_pressures_lowest_hp():
    battle = make_battle(
        [
            make_pick("briar_rose", "thorn_snare"),
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    battle.team2.get_slot("front").ko = True
    battle.team2.get_slot("back_right").ko = True
    battle.team2.get_slot("back_left").hp = 30
    battle.team1.get_slot("front").add_status("root", 2)
    action = choose_action(battle, 1, "front")
    assert action["type"] == "ability"
    assert action["ability"].id in {"thorn_snare", "hawkshot"}
    assert action["target"].defn.id == "ashen_ella"


def scenario_robin_backline_pickoff():
    battle = make_battle(
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("gretel", "hot_mitts"),
        ],
    )
    target = battle.team2.get_slot("back_left")
    target.add_status("guard", 2)
    target.hp = 24
    action = choose_action(battle, 1, "back_left")
    assert action["type"] == "ability"
    assert action["ability"].id == "snipe_shot"
    assert action["target"].defn.id == "ashen_ella"


def scenario_pinocchio_holds_frontline():
    battle = make_battle(
        [
            make_pick("pinocchio", "wooden_wallop"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("risa_redcloak", "crimson_fury"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    actor = battle.team1.get_slot("front")
    actor.ability_charges["malice"] = 2
    action = choose_action(battle, 1, "front")
    assert action["type"] != "swap"


def scenario_recharge_exposes_backline_to_melee():
    battle = make_battle(
        [
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("gretel", "hot_mitts"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
            make_pick("ashen_ella", "crowstorm"),
        ],
    )
    melee_actor = battle.team1.get_slot("front")
    ranged_actor = battle.team2.get_slot("back_left")

    legal_before = get_legal_targets(battle, 1, melee_actor, melee_actor.sig)
    assert ranged_actor not in legal_before

    ranged_actor.ranged_uses = 2
    ranged_actor.queued = {
        "type": "ability",
        "ability": ranged_actor.sig,
        "target": battle.team1.get_slot("front"),
    }
    resolve_queued_action(ranged_actor, 2, battle)
    assert ranged_actor.recharge_pending
    assert not ranged_actor.must_recharge

    legal_same_round = get_legal_targets(battle, 1, melee_actor, melee_actor.sig)
    assert ranged_actor not in legal_same_round

    end_round(battle)
    assert ranged_actor.must_recharge
    assert ranged_actor.recharge_exposed
    assert not ranged_actor.recharge_pending
    assert ranged_actor in get_legal_targets(battle, 1, melee_actor, melee_actor.sig)

    ranged_actor.queued = {"type": "skip"}
    resolve_queued_action(ranged_actor, 2, battle)
    assert not ranged_actor.must_recharge
    assert ranged_actor.recharge_exposed
    assert ranged_actor in get_legal_targets(battle, 1, melee_actor, melee_actor.sig)

    end_round(battle)
    assert not ranged_actor.recharge_exposed
    assert ranged_actor not in get_legal_targets(battle, 1, melee_actor, melee_actor.sig)


def scenario_frontline_mixed_unit_still_forced_to_recharge():
    battle = make_battle(
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("gretel", "hot_mitts"),
        ],
        [
            make_pick("pinocchio", "wooden_wallop"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    actor = battle.team2.get_slot("front")
    actor.must_recharge = True
    assert not can_use_ability(actor, actor.sig, battle.team2)
    assert get_legal_item_targets(battle, 2, actor) == []


def scenario_mixed_backline_recharge_triggers_after_two_uses():
    battle = make_battle(
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("rapunzel", "lower_guard"),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    actor = battle.team1.get_slot("back_left")
    actor.ranged_uses = 1
    assert ai.count_recharge_pressure(actor) == 1
    assert ai.would_action_force_recharge_next_round(actor, {"type": "ability", "ability": actor.sig})

    actor.queued = {
        "type": "ability",
        "ability": actor.sig,
        "target": battle.team2.get_slot("front"),
    }
    resolve_queued_action(actor, 1, battle)
    assert actor.ranged_uses == 2
    assert actor.recharge_pending
    assert not actor.must_recharge


def scenario_rapunzel_flowing_locks_ignores_all_targeting_and_refreshes():
    battle = make_battle(
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("rapunzel", "lower_guard"),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    actor = battle.team1.get_slot("back_left")
    off_axis_target = battle.team2.get_slot("back_right")

    assert actor.ability_charges.get("flowing_locks_ready", 0) > 0
    assert off_axis_target in get_legal_targets(battle, 1, actor, actor.sig)

    actor.queued = {"type": "ability", "ability": actor.sig, "target": off_axis_target}
    resolve_queued_action(actor, 1, battle)
    assert actor.ability_charges.get("flowing_locks_ready", 0) == 0
    assert off_axis_target not in get_legal_targets(battle, 1, actor, actor.sig)

    actor.ability_charges["severed_tether_active"] = 1
    assert off_axis_target in get_legal_targets(battle, 1, actor, actor.sig)
    actor.ability_charges["severed_tether_active"] = 0

    end_round(battle)
    assert actor.ability_charges.get("flowing_locks_ready", 0) == 1


def scenario_constantine_shadowstep_idle_bonus():
    battle = make_battle(
        [
            make_pick("lucky_constantine", "feline_gambit"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("gretel", "hot_mitts"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
            make_pick("ashen_ella", "crowstorm"),
        ],
    )
    actor = battle.team1.get_slot("front")
    target = battle.team2.get_slot("back_left")
    mode = get_mode(actor, actor.sig)

    assert target not in get_legal_targets(battle, 1, actor, actor.sig)
    target.add_status("expose", 2)
    assert target in get_legal_targets(battle, 1, actor, actor.sig)
    target.remove_status("expose")
    target.recharge_exposed = True
    assert target in get_legal_targets(battle, 1, actor, actor.sig)

    target.recharge_exposed = False
    dmg_non_idle = compute_damage(actor, target, actor.sig, mode, 1, battle)
    target.recharge_exposed = True
    dmg_idle = compute_damage(actor, target, actor.sig, mode, 1, battle)
    assert dmg_idle == dmg_non_idle + 14


def scenario_rapunzel_ai_uses_off_axis_flowing_locks():
    battle = make_battle(
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("rapunzel", "lower_guard", basics=["impose", "summons"], item_id="main_gauche"),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("snowkissed_aurora", "dictate_of_nature"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    battle.team2.get_slot("back_right").hp = 18
    action = choose_action(battle, 1, "back_left")
    assert action["type"] == "ability"
    assert action["target"].defn.id == "robin_hooded_avenger"


def scenario_constantine_ai_targets_idle_backliner():
    battle = make_battle(
        [
            make_pick("lucky_constantine", "feline_gambit"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("gretel", "hot_mitts"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
            make_pick("snowkissed_aurora", "dictate_of_nature"),
        ],
    )
    battle.team2.get_slot("back_left").recharge_exposed = True
    battle.team2.get_slot("back_left").hp = 22
    action = choose_action(battle, 1, "front")
    assert action["type"] == "ability"
    assert action["target"].defn.id == "robin_hooded_avenger"


def scenario_blue_faerie_boon_extends_cap_without_granting_malice():
    battle = make_battle(
        [
            make_pick("pinocchio", "wooden_wallop"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("risa_redcloak", "crimson_fury"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    actor = battle.team1.get_slot("front")
    battle.team1.get_slot("back_left").ko = True
    battle.team1.get_slot("back_right").ko = True
    actor.hp = 100
    actor.ability_charges["malice"] = 4

    assert can_use_ability(actor, actor.defn.twist, battle.team1)
    actor.queued = {"type": "ability", "ability": actor.defn.twist, "target": actor}
    resolve_queued_action(actor, 1, battle)

    assert actor.ability_charges.get("malice_cap") == 12
    assert actor.ability_charges.get("malice") == 4
    assert actor.hp == 180


def scenario_devils_due_uses_full_power_spread_and_ignores_melee_targeting():
    battle = make_battle(
        [
            make_pick("hunold_the_piper", "haunting_rhythm"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("risa_redcloak", "crimson_fury"),
        ],
        [
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    actor = battle.team1.get_slot("front")
    ally_left = battle.team1.get_slot("back_left")
    ally_right = battle.team1.get_slot("back_right")
    ally_left.ko = True
    ally_right.ko = True

    sig = actor.sig
    mode = get_mode(actor, sig)
    enemy_front = battle.team2.get_slot("front")
    enemy_back_left = battle.team2.get_slot("back_left")
    enemy_back_right = battle.team2.get_slot("back_right")
    expected_front = compute_damage(actor, enemy_front, sig, mode, 1, battle)
    expected_back_left = compute_damage(actor, enemy_back_left, sig, mode, 1, battle)
    expected_back_right = compute_damage(actor, enemy_back_right, sig, mode, 1, battle)

    assert enemy_back_left not in get_legal_targets(battle, 1, actor, sig)
    assert enemy_back_right not in get_legal_targets(battle, 1, actor, sig)

    actor.queued = {"type": "ability", "ability": actor.defn.twist, "target": actor}
    resolve_queued_action(actor, 1, battle)

    assert enemy_front.hp == enemy_front.max_hp - expected_front
    assert enemy_back_left.hp == enemy_back_left.max_hp - expected_back_left
    assert enemy_back_right.hp == enemy_back_right.max_hp - expected_back_right
    assert enemy_front.has_status("shock")
    assert enemy_back_left.has_status("shock")
    assert enemy_back_right.has_status("shock")


def scenario_green_knight_ai_prefers_across_target():
    battle = make_battle(
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("green_knight", "heros_bargain", basics=["impose", "decree"]),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
            make_pick("ashen_ella", "crowstorm"),
        ],
    )
    battle.team2.get_slot("back_left").hp = 26
    action = choose_action(battle, 1, "back_left")
    assert action["type"] == "ability"
    assert action["target"].defn.id == "robin_hooded_avenger"


def scenario_not_by_the_hair_frontline_doubles_bricklayer_next_round():
    battle = make_battle(
        [
            make_pick("porcus_iii", "not_by_the_hair"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("risa_redcloak", "crimson_fury"),
        ],
        [
            make_pick("matchstick_liesl", "cinder_blessing", basics=["smite", "bless"]),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    porcus = battle.team1.get_slot("front")
    attacker = battle.team2.get_slot("front")
    smite = ability_by_id(attacker.defn, "smite")
    smite_mode = get_mode(attacker, smite)

    base_damage = compute_damage(attacker, porcus, smite, smite_mode, 2, battle)
    assert base_damage < math.ceil(porcus.max_hp * 0.20)
    attacker.remove_status("weaken")

    porcus.queued = {"type": "ability", "ability": porcus.sig, "target": porcus}
    resolve_queued_action(porcus, 1, battle)
    end_round(battle)

    boosted_damage = compute_damage(attacker, porcus, smite, smite_mode, 2, battle)
    assert boosted_damage == math.ceil(base_damage * 0.30)
    assert attacker.has_status("weaken")


def scenario_not_by_the_hair_backline_enables_bricklayer_next_round():
    battle = make_battle(
        [
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("porcus_iii", "not_by_the_hair"),
            make_pick("aldric_lost_lamb", "benefactor"),
        ],
        [
            make_pick("matchstick_liesl", "cinder_blessing", basics=["smite", "bless"]),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    porcus = battle.team1.get_slot("back_left")
    attacker = battle.team2.get_slot("front")
    smite = ability_by_id(attacker.defn, "smite")
    smite_mode = get_mode(attacker, smite)

    base_damage = compute_damage(attacker, porcus, smite, smite_mode, 2, battle)
    assert base_damage < math.ceil(porcus.max_hp * 0.20)
    attacker.remove_status("weaken")

    porcus.queued = {"type": "ability", "ability": porcus.sig, "target": porcus}
    resolve_queued_action(porcus, 1, battle)
    end_round(battle)

    boosted_damage = compute_damage(attacker, porcus, smite, smite_mode, 2, battle)
    assert boosted_damage == math.ceil(base_damage * 0.65)
    assert attacker.has_status("weaken")


def scenario_green_knight_natural_order_adds_flat_damage():
    battle = make_battle(
        [
            make_pick("green_knight", "natural_order", basics=["impose", "decree"]),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("risa_redcloak", "crimson_fury"),
        ],
        [
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    actor = battle.team1.get_slot("front")
    target = battle.team2.get_slot("front")
    impose = ability_by_id(actor.defn, "impose")
    impose_mode = get_mode(actor, impose)

    target.ability_charges["rounds_since_swap"] = 1
    damage_without_bonus = compute_damage(actor, target, impose, impose_mode, 1, battle)
    target.ability_charges["rounds_since_swap"] = 2
    damage_with_bonus = compute_damage(actor, target, impose, impose_mode, 1, battle)

    assert damage_with_bonus == damage_without_bonus + 15


def scenario_arcane_wave_only_debuffs_attack():
    battle = make_battle(
        [
            make_pick("march_hare", "tempus_fugit", basics=["arcane_wave", "breakthrough"]),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("risa_redcloak", "crimson_fury"),
        ],
        [
            make_pick("porcus_iii", "porcine_honor"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    actor = battle.team1.get_slot("front")
    target = battle.team2.get_slot("front")
    arcane_wave = ability_by_id(actor.defn, "arcane_wave")

    actor.queued = {"type": "ability", "ability": arcane_wave, "target": target}
    resolve_queued_action(actor, 1, battle)

    assert any(debuff.stat == "attack" and debuff.amount == 10 for debuff in actor.debuffs)
    assert not any(debuff.stat == "defense" and debuff.amount == 10 for debuff in actor.debuffs)


def scenario_ai_damage_percentages_follow_rulebook():
    battle = make_battle(
        [
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("gretel", "hot_mitts"),
        ],
        [
            make_pick("snowkissed_aurora", "dictate_of_nature"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    source = battle.team1.get_slot("front")
    target = battle.team2.get_slot("front")

    source.add_status("weaken", 2)
    assert ai.apply_damage_modifiers(100, source, target, battle) == 85
    source.remove_status("weaken")

    target.add_status("expose", 2)
    assert ai.apply_damage_modifiers(100, source, target, battle) == 115
    target.remove_status("expose")

    target.add_status("guard", 2)
    assert ai.apply_damage_modifiers(100, source, target, battle) == 85

    pride_battle = make_battle(
        [
            make_pick("frederic", "heros_charge"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("gretel", "hot_mitts"),
        ],
        [
            make_pick("snowkissed_aurora", "dictate_of_nature"),
            make_pick("ashen_ella", "crowstorm"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
        ],
    )
    pride_source = pride_battle.team1.get_slot("front")
    pride_target = pride_battle.team2.get_slot("front")
    assert ai.apply_damage_modifiers(100, pride_source, pride_target, pride_battle) == 115
    assert ai.apply_damage_modifiers(100, pride_target, pride_source, pride_battle) == 107


def scenario_porcus_ai_uses_not_by_the_hair_under_pressure():
    battle = make_battle(
        [
            make_pick("porcus_iii", "not_by_the_hair"),
            make_pick("aldric_lost_lamb", "benefactor"),
            make_pick("risa_redcloak", "crimson_fury"),
        ],
        [
            make_pick("risa_redcloak", "crimson_fury"),
            make_pick("robin_hooded_avenger", "snipe_shot"),
            make_pick("ashen_ella", "crowstorm"),
        ],
    )
    battle.team1.get_slot("front").hp = 72
    battle.team1.get_slot("front").add_status("root", 2)
    action = choose_action(battle, 1, "front")
    assert action["type"] == "ability"
    assert action["ability"].id == "not_by_the_hair"


SCENARIOS = [
    ("target_access_spotlight", scenario_target_access_spotlight),
    ("recharge_trap_shock", scenario_recharge_trap_shock),
    ("ella_backline_exception", scenario_ella_backline_exception),
    ("briar_pressures_lowest_hp", scenario_briar_pressures_lowest_hp),
    ("robin_backline_pickoff", scenario_robin_backline_pickoff),
    ("pinocchio_holds_frontline", scenario_pinocchio_holds_frontline),
    ("recharge_exposes_backline_to_melee", scenario_recharge_exposes_backline_to_melee),
    ("frontline_mixed_unit_still_forced_to_recharge", scenario_frontline_mixed_unit_still_forced_to_recharge),
    ("mixed_backline_recharge_triggers_after_two_uses", scenario_mixed_backline_recharge_triggers_after_two_uses),
    ("rapunzel_flowing_locks_ignores_all_targeting_and_refreshes", scenario_rapunzel_flowing_locks_ignores_all_targeting_and_refreshes),
    ("constantine_shadowstep_idle_bonus", scenario_constantine_shadowstep_idle_bonus),
    ("rapunzel_ai_uses_off_axis_flowing_locks", scenario_rapunzel_ai_uses_off_axis_flowing_locks),
    ("constantine_ai_targets_idle_backliner", scenario_constantine_ai_targets_idle_backliner),
    ("blue_faerie_boon_extends_cap_without_granting_malice", scenario_blue_faerie_boon_extends_cap_without_granting_malice),
    ("devils_due_uses_full_power_spread_and_ignores_melee_targeting", scenario_devils_due_uses_full_power_spread_and_ignores_melee_targeting),
    ("green_knight_ai_prefers_across_target", scenario_green_knight_ai_prefers_across_target),
    ("not_by_the_hair_frontline_doubles_bricklayer_next_round", scenario_not_by_the_hair_frontline_doubles_bricklayer_next_round),
    ("not_by_the_hair_backline_enables_bricklayer_next_round", scenario_not_by_the_hair_backline_enables_bricklayer_next_round),
    ("green_knight_natural_order_adds_flat_damage", scenario_green_knight_natural_order_adds_flat_damage),
    ("arcane_wave_only_debuffs_attack", scenario_arcane_wave_only_debuffs_attack),
    ("ai_damage_percentages_follow_rulebook", scenario_ai_damage_percentages_follow_rulebook),
    ("porcus_ai_uses_not_by_the_hair_under_pressure", scenario_porcus_ai_uses_not_by_the_hair_under_pressure),
]


def main():
    failures = []
    for name, fn in SCENARIOS:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:
            failures.append((name, exc))
            print(f"FAIL {name}: {exc}")
    if failures:
        raise SystemExit(1)
    print(f"All {len(SCENARIOS)} AI scenarios passed.")


if __name__ == "__main__":
    main()
