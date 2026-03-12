"""Quick deterministic systems audit for Fabled rules engine.

Run:
    python audit_game_systems.py
"""

import math
import re
from pathlib import Path

import battle_log
from data import ROSTER, CLASS_BASICS, ITEMS
from logic import (
    compute_damage,
    create_team,
    deal_damage,
    end_round,
    execute_item,
    get_legal_item_targets,
    get_legal_targets,
    resolve_player_turn,
    start_new_round,
    execute_ability,
)
from models import BattleState
from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT


def _mk_pick(defn, sig_idx=0, basic_idxs=(0, 1), item_id="health_potion"):
    item = next(i for i in ITEMS if i.id == item_id)
    pool = CLASS_BASICS[defn.cls]
    return {
        "definition": defn,
        "signature": defn.sig_options[sig_idx],
        "basics": [pool[basic_idxs[0]], pool[basic_idxs[1]]],
        "item": item,
    }


def _mk_battle(p1_defs, p2_defs):
    b = BattleState(
        team1=create_team("P1", [_mk_pick(d) for d in p1_defs]),
        team2=create_team("P2", [_mk_pick(d) for d in p2_defs]),
    )
    battle_log.init()
    start_new_round(b)
    return b


def _mk_battle_from_picks(p1_picks, p2_picks):
    b = BattleState(
        team1=create_team("P1", p1_picks),
        team2=create_team("P2", p2_picks),
    )
    battle_log.init()
    start_new_round(b)
    return b



def _extract_ui_special_description_keys() -> set[str]:
    ui_text = Path("ui.py").read_text(encoding="utf-8")
    pairs = re.findall(r'"([a-z0-9_]+)"\s*:', ui_text)
    # Keep keys that are in SPECIAL_DESCRIPTIONS dict region only.
    head = ui_text.split('def _mode_summary', 1)[0]
    return set(re.findall(r'"([a-z0-9_]+)"\s*:', head.split('SPECIAL_DESCRIPTIONS: dict =', 1)[1]))


def _extract_logic_special_handler_keys() -> set[str]:
    logic_text = Path("logic.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'\b(?:if|elif)\s+key\s*==\s*"([a-z0-9_]+)"', logic_text))
    for grp in re.findall(r'\b(?:if|elif)\s+key\s+in\s*\(([^\)]*)\)', logic_text):
        keys.update(re.findall(r'"([a-z0-9_]+)"', grp))
    return keys


def _collect_all_ability_specials() -> set[str]:
    specials = set()
    for defn in ROSTER:
        for ab in [*CLASS_BASICS[defn.cls], *defn.sig_options, defn.twist]:
            for mode in (ab.frontline, ab.backline):
                if mode.special and re.fullmatch(r"[a-z0-9_]+", mode.special):
                    specials.add(mode.special)
    for item in ITEMS:
        if item.special and re.fullmatch(r"[a-z0-9_]+", item.special):
            specials.add(item.special)
    return specials


def _collect_active_ability_specials() -> set[str]:
    specials = set()
    for defn in ROSTER:
        for ab in [*CLASS_BASICS[defn.cls], *defn.sig_options, defn.twist]:
            if ab.passive:
                continue
            for mode in (ab.frontline, ab.backline):
                if mode.special and re.fullmatch(r"[a-z0-9_]+", mode.special):
                    specials.add(mode.special)
    return specials


def run_audit():
    by_name = {d.name: d for d in ROSTER}

    # 1) Swap can only be used once per turn (resolution-time enforcement).
    b = _mk_battle(
        [by_name["Sir Roland"], by_name["Porcus III"], by_name["Aldric, Lost Lamb"]],
        [by_name["Little Jack"], by_name["Witch-Hunter Gretel"], by_name["Risa Redcloak"]],
    )
    t = b.team1
    front = t.get_slot(SLOT_FRONT)
    back_left = t.get_slot(SLOT_BACK_LEFT)
    back_right = t.get_slot(SLOT_BACK_RIGHT)
    front.queued = {"type": "swap", "target": back_left}
    back_left.queued = {"type": "swap", "target": back_right}
    back_right.queued = {"type": "skip"}
    resolve_player_turn(b, 1)
    slots = {m.name: m.slot for m in t.members}
    assert not (
        slots["Sir Roland"] == SLOT_BACK_LEFT and slots["Porcus III"] == SLOT_BACK_RIGHT
    ), "Detected second swap in same turn; rule violation"

    # 2) Illegal target queue should fizzle at resolution (Ella backline untargetable).
    b = _mk_battle(
        [by_name["Little Jack"], by_name["Witch-Hunter Gretel"], by_name["Risa Redcloak"]],
        [by_name["Sir Roland"], by_name["Ashen Ella"], by_name["Porcus III"]],
    )
    attacker = b.team1.frontline()
    ella = next(m for m in b.team2.members if m.defn.id == "ashen_ella")
    strike = next(a for a in attacker.basics if a.id == "strike")
    attacker.queued = {"type": "ability", "ability": strike, "target": ella}
    for u in b.team1.members:
        if u is not attacker:
            u.queued = {"type": "skip"}
    resolve_player_turn(b, 1)
    assert ella.hp == ella.max_hp, "Illegal target took damage"

    # 3) Sanctuary frontline heals all allies for exactly 1/10 max HP each end round.
    b = _mk_battle(
        [by_name["Aldric, Lost Lamb"], by_name["Porcus III"], by_name["Sir Roland"]],
        [by_name["Little Jack"], by_name["Witch-Hunter Gretel"], by_name["Risa Redcloak"]],
    )
    aldric = b.team1.frontline()
    aldric.sig = next(s for s in aldric.defn.sig_options if s.id == "sanctuary")
    for u in b.team1.members:
        u.hp = max(1, u.max_hp - 50)
    pre_hp = {u.name: u.hp for u in b.team1.members}
    end_round(b)
    for u in b.team1.members:
        expected = min(u.max_hp, pre_hp[u.name] + math.ceil(u.max_hp * 0.10))
        assert u.hp == expected, f"Sanctuary mismatch for {u.name}"

    # 4) Self-only active abilities should have exactly one legal target: self.
    mage = by_name["Ashen Ella"]
    fighter = by_name["Little Jack"]
    march_hare = by_name["March Hare"]

    p1_picks = [
        _mk_pick(mage, sig_idx=2, basic_idxs=(4, 0)),          # Fae Blessing + Breakthrough
        _mk_pick(fighter, sig_idx=0, basic_idxs=(2, 0)),       # Feint
        _mk_pick(march_hare, sig_idx=2, basic_idxs=(0, 1)),    # Stitch In Time
    ]
    p2_picks = [
        _mk_pick(by_name["Porcus III"]),
        _mk_pick(by_name["Sir Roland"]),
        _mk_pick(by_name["Risa Redcloak"]),
    ]
    b = _mk_battle_from_picks(p1_picks, p2_picks)

    units = {u.defn.id: u for u in b.team1.members}

    def _find_ability(unit, ability_id):
        for a in [unit.sig, *unit.basics, unit.defn.twist]:
            if a.id == ability_id:
                return a
        raise AssertionError(f"{ability_id} not found on {unit.name}")

    checks = [
        (units["ashen_ella"], "breakthrough"),
        (units["ashen_ella"], "fae_blessing"),
        (units["little_jack"], "feint"),
        (units["march_hare"], "stitch_in_time"),
    ]

    for unit, ability_id in checks:
        ability = _find_ability(unit, ability_id)
        legal = get_legal_targets(b, 1, unit, ability)
        assert legal == [unit], f"{ability_id} should self-target only"


    # 5) Spread abilities should count as one ranged use, not one per target hit.
    b = _mk_battle(
        [by_name["Sir Roland"], by_name["March Hare"], by_name["Witch-Hunter Gretel"]],
        [by_name["Briar Rose"], by_name["Aldric, Lost Lamb"], by_name["Matchstick Liesl"]],
    )
    briar = b.team2.frontline()
    thorn_snare = next(a for a in [briar.sig, *briar.basics, briar.defn.twist] if a.id == "thorn_snare")

    # First spread cast: should not force recharge yet.
    briar.queued = {"type": "ability", "ability": thorn_snare, "target": None}
    for u in b.team2.members:
        if u is not briar and not u.ko:
            u.queued = {"type": "skip"}
    resolve_player_turn(b, 2)
    assert briar.ranged_uses == 1, "Spread should increment ranged_uses by exactly 1"
    assert not briar.must_recharge, "Spread should not immediately force recharge on first cast"

    # Third spread cast should finally force recharge.
    for _ in range(2):
        briar.must_recharge = False
        briar.queued = {"type": "ability", "ability": thorn_snare, "target": None}
        for u in b.team2.members:
            if u is not briar and not u.ko:
                u.queued = {"type": "skip"}
        resolve_player_turn(b, 2)
    assert briar.ranged_uses == 3, "Three spread casts should be tracked as three uses"
    assert briar.must_recharge, "Recharge should trigger after three ranged ability casts"

    # 6) Offensive abilities with guard riders (e.g., Shield Bash FL) must target enemies.
    b = _mk_battle(
        [by_name["Sir Roland"], by_name["Porcus III"], by_name["Aldric, Lost Lamb"]],
        [by_name["Briar Rose"], by_name["Matchstick Liesl"], by_name["Little Jack"]],
    )
    roland = b.team1.frontline()
    shield_bash = next(a for a in roland.basics if a.id == "shield_bash")
    legal = get_legal_targets(b, 1, roland, shield_bash)
    assert roland not in legal, "Shield Bash FL should not self-target"
    assert all(u in b.team2.alive() for u in legal), "Shield Bash FL should target enemies only"


    # 7) Item targeting legality: self-only, ally, and enemy items.
    b = _mk_battle(
        [by_name["Sir Roland"], by_name["Porcus III"], by_name["Little Jack"]],
        [by_name["Briar Rose"], by_name["Matchstick Liesl"], by_name["Aldric, Lost Lamb"]],
    )
    roland = b.team1.frontline()
    # Iron Buckler = self-only
    roland.item = next(i for i in ITEMS if i.id == "iron_buckler")
    roland.item_uses_left = roland.item.uses
    legal = get_legal_item_targets(b, 1, roland)
    assert legal == [roland], "Iron Buckler should target self only"

    # Crafty Shield = ally/self
    roland.item = next(i for i in ITEMS if i.id == "crafty_shield")
    roland.item_uses_left = roland.item.uses
    legal = get_legal_item_targets(b, 1, roland)
    assert set(legal) == set(b.team1.alive()), "Crafty Shield should target allies"

    # Hunter's Net = enemy only
    roland.item = next(i for i in ITEMS if i.id == "hunters_net")
    roland.item_uses_left = roland.item.uses
    legal = get_legal_item_targets(b, 1, roland)
    assert all(u in b.team2.alive() for u in legal), "Hunter's Net should target enemies"

    # 8) Active items are repeat-usable by default (unless explicitly limited).
    roland.item = next(i for i in ITEMS if i.id == "iron_buckler")
    roland.item_uses_left = roland.item.uses
    start_uses = roland.item_uses_left
    before_buffs = len(roland.buffs)
    execute_item(roland, roland, 1, b)
    assert roland.item_uses_left == start_uses - 1, "Active item should decrement by 1 per use"
    assert len(roland.buffs) > before_buffs, "Active item should apply its effect on use"
    prev_uses = roland.item_uses_left
    execute_item(roland, roland, 1, b)
    assert roland.item_uses_left == prev_uses - 1, "Repeat-usable item should remain usable"


    # 9) Lake's Gift should match rulebook by position.
    b = _mk_battle(
        [by_name["Lady of Reflections"], by_name["Porcus III"], by_name["Sir Roland"]],
        [by_name["Little Jack"], by_name["Witch-Hunter Gretel"], by_name["Risa Redcloak"]],
    )
    lady = b.team1.frontline()
    porcus = next(m for m in b.team1.members if m.defn.id == "porcus_iii")
    lakes_gift = next(s for s in lady.defn.sig_options if s.id == "lakes_gift")
    lady.sig = lakes_gift
    execute_ability(lady, lakes_gift, porcus, 1, b)
    assert porcus.has_status("reflecting_pool"), "Lake's Gift should grant Reflecting Pool effect"
    assert any(buff.stat == "attack" and buff.amount == 10 for buff in porcus.buffs), (
        "Lake's Gift frontline should grant +10 Attack"
    )

    b = _mk_battle(
        [by_name["Porcus III"], by_name["Lady of Reflections"], by_name["Sir Roland"]],
        [by_name["Little Jack"], by_name["Witch-Hunter Gretel"], by_name["Risa Redcloak"]],
    )
    lady = next(m for m in b.team1.members if m.defn.id == "lady_of_reflections")
    porcus = b.team1.frontline()
    lakes_gift = next(s for s in lady.defn.sig_options if s.id == "lakes_gift")
    lady.sig = lakes_gift
    execute_ability(lady, lakes_gift, porcus, 1, b)
    assert porcus.has_status("reflecting_pool"), "Backline Lake's Gift should still grant Reflecting Pool"
    assert not any(buff.stat == "attack" and buff.amount == 10 for buff in porcus.buffs), (
        "Backline Lake's Gift must not grant +10 Attack"
    )

    # 10) Reflecting Pool should still reflect when the holder is KO'd by the hit.
    b = _mk_battle(
        [by_name["Lady of Reflections"], by_name["Porcus III"], by_name["Sir Roland"]],
        [by_name["Little Jack"], by_name["Witch-Hunter Gretel"], by_name["Risa Redcloak"]],
    )
    lady = b.team1.frontline()
    attacker = b.team2.frontline()
    strike = next(a for a in attacker.basics if a.id == "strike")
    mode = strike.frontline
    lady.hp = 5
    before_hp = attacker.hp
    deal_damage(attacker, lady, 12, strike, mode, 2, b)
    assert lady.ko, "Lady should be KO'd in this scenario"
    assert attacker.hp == before_hp - 2, "Reflecting Pool should still reflect 10% (ceil) on KO hit"

    # 11) Reflecting Pool should reflect 20% when attacker is backline.
    b = _mk_battle(
        [by_name["Lady of Reflections"], by_name["Porcus III"], by_name["Sir Roland"]],
        [by_name["Little Jack"], by_name["Witch-Hunter Gretel"], by_name["Risa Redcloak"]],
    )
    lady = b.team1.frontline()
    attacker = next(m for m in b.team2.members if m.slot == SLOT_BACK_RIGHT)
    strike = next(a for a in attacker.basics if a.id == "strike")
    mode = strike.backline
    before_hp = attacker.hp
    deal_damage(attacker, lady, 23, strike, mode, 2, b)
    assert attacker.hp == before_hp - 5, "Reflecting Pool should reflect 20% (ceil) from backline attackers"

    # 12) Crumb Trail pickup heal amount should be 40 HP.
    b = _mk_battle(
        [by_name["Little Jack"], by_name["Porcus III"], by_name["Witch-Hunter Gretel"]],
        [by_name["Sir Roland"], by_name["Risa Redcloak"], by_name["Aldric, Lost Lamb"]],
    )
    t = b.team1
    front = t.get_slot(SLOT_FRONT)
    back_right = t.get_slot(SLOT_BACK_RIGHT)
    front.hp = max(1, front.max_hp - 70)
    start_hp = front.hp
    b.crumb_team = 1
    b.crumb_slot = SLOT_BACK_RIGHT
    front.queued = {"type": "swap", "target": back_right}
    for u in t.members:
        if u is not front:
            u.queued = {"type": "skip"}
    resolve_player_turn(b, 1)
    front_after = next(m for m in t.members if m.name == "Little Jack")
    assert front_after.slot == SLOT_BACK_RIGHT, "Frontline should have swapped into crumb slot"
    assert front_after.hp == min(front_after.max_hp, start_hp + 40), "Crumb Trail pickup should heal 40"

    # 13) Hunold Dying Dance FL: 60 power and Shock only if target is Weakened.
    b = _mk_battle(
        [by_name["Hunold the Piper"], by_name["Porcus III"], by_name["Sir Roland"]],
        [by_name["Little Jack"], by_name["Risa Redcloak"], by_name["Aldric, Lost Lamb"]],
    )
    hunold = b.team1.frontline()
    target = b.team2.frontline()
    dying_dance = next(s for s in hunold.defn.sig_options if s.id == "dying_dance")
    hunold.sig = dying_dance
    target.add_status("weaken", 2)
    execute_ability(hunold, dying_dance, target, 1, b)
    assert target.has_status("shock"), "Dying Dance FL should Shock a Weakened target"

    b = _mk_battle(
        [by_name["Hunold the Piper"], by_name["Porcus III"], by_name["Sir Roland"]],
        [by_name["Little Jack"], by_name["Risa Redcloak"], by_name["Aldric, Lost Lamb"]],
    )
    hunold = b.team1.frontline()
    target = b.team2.frontline()
    dying_dance = next(s for s in hunold.defn.sig_options if s.id == "dying_dance")
    hunold.sig = dying_dance
    execute_ability(hunold, dying_dance, target, 1, b)
    assert not target.has_status("shock"), "Dying Dance FL should not Shock non-Weakened target"

    # 14) Family Seal adds +10 to signature damage, not basic damage.
    p1_defs = [by_name["Little Jack"], by_name["Porcus III"], by_name["Sir Roland"]]
    p2_defs = [by_name["Risa Redcloak"], by_name["Aldric, Lost Lamb"], by_name["March Hare"]]

    b_no = BattleState(
        team1=create_team("P1", [_mk_pick(p1_defs[0], item_id="health_potion"), _mk_pick(p1_defs[1]), _mk_pick(p1_defs[2])]),
        team2=create_team("P2", [_mk_pick(p2_defs[0]), _mk_pick(p2_defs[1]), _mk_pick(p2_defs[2])]),
    )
    start_new_round(b_no)
    b_yes = BattleState(
        team1=create_team("P1", [_mk_pick(p1_defs[0], item_id="family_seal"), _mk_pick(p1_defs[1]), _mk_pick(p1_defs[2])]),
        team2=create_team("P2", [_mk_pick(p2_defs[0]), _mk_pick(p2_defs[1]), _mk_pick(p2_defs[2])]),
    )
    start_new_round(b_yes)

    actor_no = b_no.team1.frontline()
    actor_yes = b_yes.team1.frontline()
    target_no = b_no.team2.frontline()
    target_yes = b_yes.team2.frontline()
    sig_no = actor_no.sig
    sig_yes = actor_yes.sig
    basic_no = next(a for a in actor_no.basics if a.id == "strike")
    basic_yes = next(a for a in actor_yes.basics if a.id == "strike")

    sig_dmg_no = compute_damage(actor_no, target_no, sig_no, sig_no.frontline, 1, b_no)
    sig_dmg_yes = compute_damage(actor_yes, target_yes, sig_yes, sig_yes.frontline, 1, b_yes)
    basic_dmg_no = compute_damage(actor_no, target_no, basic_no, basic_no.frontline, 1, b_no)
    basic_dmg_yes = compute_damage(actor_yes, target_yes, basic_yes, basic_yes.frontline, 1, b_yes)
    assert sig_dmg_yes == sig_dmg_no + 10, "Family Seal should add exactly +10 to signature damage"
    assert basic_dmg_yes == basic_dmg_no, "Family Seal should not affect basic ability damage"

    # 15) Signature ordering should match rulebook for affected adventurers.
    order_checks = {
        "Lucky Constantine": ["feline_gambit", "subterfuge", "nine_lives"],
        "Hunold the Piper": ["haunting_rhythm", "dying_dance", "hypnotic_aura"],
        "Reynard, Lupine Trickster": ["size_up", "feign_weakness", "cutpurse"],
        "Sea Wench Asha": ["abyssal_call", "misappropriate", "faustian_bargain"],
    }
    for name, expected in order_checks.items():
        got = [s.id for s in by_name[name].sig_options]
        assert got == expected, f"Signature order mismatch for {name}: got={got} expected={expected}"

    # 16) Class basic ordering should match Appendix B.
    assert [a.id for a in CLASS_BASICS["Fighter"]] == [
        "strike", "rend", "feint", "cleave", "intimidate"
    ], "Fighter basic order mismatch"
    assert [a.id for a in CLASS_BASICS["Ranger"]] == [
        "hawkshot", "volley", "hunters_mark", "trapping_blow", "hunters_badge"
    ], "Ranger basic order mismatch"


    # 17) Bless FL should grant +10 Attack to guarded ally only (not caster).
    b = _mk_battle(
        [by_name["Aldric, Lost Lamb"], by_name["Porcus III"], by_name["Sir Roland"]],
        [by_name["Little Jack"], by_name["Risa Redcloak"], by_name["March Hare"]],
    )
    aldric = b.team1.frontline()
    ally = next(m for m in b.team1.members if m.defn.id == "porcus_iii")
    bless = next(a for a in aldric.basics if a.id == "bless")
    execute_ability(aldric, bless, ally, 1, b)
    assert any(buff.stat == "attack" and buff.amount == 10 for buff in ally.buffs), (
        "Bless FL should grant +10 Attack to guarded ally"
    )
    assert not any(buff.stat == "attack" and buff.amount == 10 for buff in aldric.buffs), (
        "Bless FL should not grant +10 Attack to caster"
    )

    # 18) Every ability/item special key has both logic handling and UI description.
    all_specials = _collect_all_ability_specials()
    ui_specials = _extract_ui_special_description_keys()
    missing_ui = sorted(all_specials - ui_specials)
    assert not missing_ui, f"Missing SPECIAL_DESCRIPTIONS entries: {missing_ui}"

    # 19) Every adventurer talent text is non-empty and has implementation touchpoints in logic.
    logic_text = Path("logic.py").read_text(encoding="utf-8")
    for defn in ROSTER:
        assert defn.talent_name.strip() and defn.talent_text.strip(), (
            f"Talent text missing for {defn.name}"
        )
        assert defn.id in logic_text, f"No logic references found for talent owner {defn.name}"

    print("All audit checks passed.")
    battle_log.close()


if __name__ == "__main__":
    run_audit()
