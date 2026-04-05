from quests_ruleset_data import ULTIMATE_METER_MAX
from quests_ruleset_logic import (
    create_battle,
    create_team,
    determine_initiative_order,
    get_legal_targets,
    make_pick,
    queue_skip,
    queue_spell,
    queue_strike,
    queue_switch,
    queue_ultimate,
    resolve_round,
)


def build_demo_battle():
    team1 = create_team(
        "Magnate A",
        [
            make_pick("little_jack", slot="front", class_name="Fighter", class_skill_id="martial", primary_weapon_id="skyfall"),
            make_pick("hunold_the_piper", slot="back_left", class_name="Mage", class_skill_id="arcane", primary_weapon_id="lightning_rod"),
            make_pick("rapunzel_the_golden", slot="back_right", class_name="Cleric", class_skill_id="healer", primary_weapon_id="ivory_tower"),
        ],
    )
    team2 = create_team(
        "Magnate B",
        [
            make_pick("sir_roland", slot="front", class_name="Warden", class_skill_id="bulwark", primary_weapon_id="pure_gold_lance"),
            make_pick("briar_rose", slot="back_left", class_name="Ranger", class_skill_id="deadeye", primary_weapon_id="thorn_snare"),
            make_pick("red_blanchette", slot="back_right", class_name="Rogue", class_skill_id="covert", primary_weapon_id="stomach_splitter"),
        ],
    )
    battle = create_battle(team1, team2)
    determine_initiative_order(battle)
    return battle


def print_snapshot(battle, title):
    print(f"\n== {title} ==")
    for team in (battle.team1, battle.team2):
        print(f"{team.player_name} | Ultimate {team.ultimate_meter}/{ULTIMATE_METER_MAX}")
        for unit in team.members:
            status_text = ", ".join(f"{status.kind}:{status.duration}" for status in unit.statuses) or "-"
            ko_text = " KO" if unit.ko else ""
            print(
                f"  {unit.name:<24} [{unit.slot:<10}] "
                f"HP {unit.hp:>3}/{unit.max_hp:<3} "
                f"Wpn {unit.primary_weapon.name:<20} "
                f"Status {status_text}{ko_text}"
            )


def queue_round_one(battle):
    jack = battle.team1.frontline()
    hunold = battle.team1.get_slot("back_left")
    rapunzel = battle.team1.get_slot("back_right")
    roland = battle.team2.frontline()
    briar = battle.team2.get_slot("back_left")
    red = battle.team2.get_slot("back_right")

    queue_strike(jack, roland)
    queue_strike(hunold, roland)
    queue_spell(rapunzel, rapunzel.primary_weapon.spells[0], jack)

    queue_spell(roland, roland.primary_weapon.spells[0], jack)
    queue_strike(briar, jack)
    queue_strike(red, jack)


def queue_round_two(battle):
    jack = battle.team1.frontline()
    hunold = battle.team1.get_slot("back_left")
    rapunzel = battle.team1.get_slot("back_right")
    roland = battle.team2.frontline()
    briar = battle.team2.get_slot("back_left")
    red = battle.team2.get_slot("back_right")

    if jack is not None:
        queue_spell(jack, jack.primary_weapon.spells[0], jack)
    if hunold is not None:
        queue_strike(hunold, roland if roland is not None else battle.team2.alive()[0])
    if rapunzel is not None:
        queue_spell(rapunzel, rapunzel.primary_weapon.spells[0], jack if jack is not None else rapunzel)

    if roland is not None:
        queue_strike(roland, jack if jack is not None else battle.team1.alive()[0])
    if briar is not None:
        queue_strike(briar, jack if jack is not None else battle.team1.alive()[0])
    if red is not None:
        queue_strike(red, jack if jack is not None else battle.team1.alive()[0])


def queue_round_three(battle):
    jack = battle.team1.frontline()
    if jack is not None:
        battle.team1.ultimate_meter = ULTIMATE_METER_MAX
        queue_ultimate(jack, jack)


def queue_scripted_round(battle, script_step):
    if battle.winner is not None:
        return False
    if script_step == 1:
        queue_round_one(battle)
        return True
    if script_step == 2:
        queue_round_two(battle)
        return True
    if script_step == 3:
        queue_round_three(battle)
        return True
    return False


def _choose_target(actor, battle, effect, weapon=None):
    legal = get_legal_targets(battle, actor, effect=effect, weapon=weapon)
    if not legal:
        return None
    if effect.target == "enemy":
        return min(
            legal,
            key=lambda unit: (0 if unit.slot == "front" else 1, unit.hp, unit.get_stat("defense")),
        )
    if effect.heal > 0:
        return min(
            legal,
            key=lambda unit: (unit.hp / max(1, unit.max_hp), unit.hp),
        )
    return legal[0]


def _can_use_spell(actor, spell):
    if actor.cooldowns.get(spell.id, 0) > 0:
        return False
    if spell in actor.primary_weapon.spells and actor.primary_weapon.ammo > 0:
        ammo_left = actor.ammo_remaining.get(actor.primary_weapon.id, actor.primary_weapon.ammo)
        if ammo_left < spell.ammo_cost:
            return False
    return True


def _can_use_strike(actor):
    strike = actor.primary_weapon.strike
    if actor.cooldowns.get(strike.id, 0) > 0:
        return False
    if actor.primary_weapon.ammo > 0:
        ammo_left = actor.ammo_remaining.get(actor.primary_weapon.id, actor.primary_weapon.ammo)
        if ammo_left < strike.ammo_cost:
            return False
    return True


def queue_autoplay_round(battle):
    for actor in battle.team1.alive() + battle.team2.alive():
        actor.queued_action = None
        actor.queued_bonus_action = None
        if battle.winner is not None:
            return

        team = battle.team1 if actor in battle.team1.members else battle.team2
        if team.ultimate_meter >= ULTIMATE_METER_MAX:
            effect = actor.defn.ultimate
            target = _choose_target(actor, battle, effect)
            if effect.target in ("self", "none") or target is not None:
                queue_ultimate(actor, target)
                continue

        spell_queued = False
        for spell in actor.active_spells():
            if not _can_use_spell(actor, spell):
                continue
            target = _choose_target(actor, battle, spell)
            if spell.target in ("self", "none") or target is not None:
                queue_spell(actor, spell, target)
                spell_queued = True
                break
        if spell_queued:
            continue

        if _can_use_strike(actor):
            target = _choose_target(actor, battle, actor.primary_weapon.strike, weapon=actor.primary_weapon)
            if target is not None:
                queue_strike(actor, target)
                continue

        if actor.defn.id != "ashen_ella":
            queue_switch(actor)
        else:
            queue_skip(actor)


def play_autoplay_round(battle):
    if battle.winner is not None:
        return False
    queue_autoplay_round(battle)
    resolve_round(battle)
    return True


def auto_finish_autoplay(battle, max_rounds=8):
    rounds_played = 0
    while battle.winner is None and rounds_played < max_rounds:
        if not play_autoplay_round(battle):
            break
        rounds_played += 1
    return rounds_played


def play_next_demo_round(battle, script_step):
    scripted = queue_scripted_round(battle, script_step)
    if not scripted:
        queue_autoplay_round(battle)
    resolve_round(battle)
    if scripted:
        return script_step + 1
    return script_step


def auto_finish_battle(battle, script_step, max_rounds=8):
    rounds_played = 0
    while battle.winner is None and rounds_played < max_rounds:
        script_step = play_next_demo_round(battle, script_step)
        rounds_played += 1
    return script_step


def print_new_log_lines(battle, start_index):
    for line in battle.log[start_index:]:
        print(f"  {line}")
    return len(battle.log)


def main():
    battle = build_demo_battle()
    print_snapshot(battle, "Start")

    log_index = 0
    script_step = play_next_demo_round(battle, 1)
    log_index = print_new_log_lines(battle, log_index)
    print_snapshot(battle, "After Round 1")

    script_step = play_next_demo_round(battle, script_step)
    log_index = print_new_log_lines(battle, log_index)
    print_snapshot(battle, "After Round 2")

    play_next_demo_round(battle, script_step)
    print_new_log_lines(battle, log_index)
    print_snapshot(battle, "After Round 3")


if __name__ == "__main__":
    main()
