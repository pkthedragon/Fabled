from data import ROSTER, CLASS_BASICS, ITEMS
from logic import create_team
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


SCENARIOS = [
    ("target_access_spotlight", scenario_target_access_spotlight),
    ("recharge_trap_shock", scenario_recharge_trap_shock),
    ("ella_backline_exception", scenario_ella_backline_exception),
    ("briar_pressures_lowest_hp", scenario_briar_pressures_lowest_hp),
    ("robin_backline_pickoff", scenario_robin_backline_pickoff),
    ("pinocchio_holds_frontline", scenario_pinocchio_holds_frontline),
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
