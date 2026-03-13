"""
logic.py – rules engine for Fabled.
Implements all core mechanics from the rulebook:
  initiative, targeting, damage formula, status effects, ranged recharge,
  KO / frontline promotion, end-of-round processing, and win checking.
Special-cased ability effects are handled by ability ID in apply_special().
"""
import math
from typing import List, Optional, Tuple

import battle_log
from models import (
    BattleState, TeamState, CombatantState, Ability, AbilityMode, Item
)
from settings import SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT, CLOCKWISE_ORDER
from data import CLASS_BASICS

# ─────────────────────────────────────────────────────────────────────────────
# TEAM / COMBATANT CONSTRUCTION
# ─────────────────────────────────────────────────────────────────────────────

def make_combatant(defn, slot, sig, basics, item) -> CombatantState:
    c = CombatantState(
        defn=defn, slot=slot, hp=defn.hp,
        sig=sig, basics=basics, item=item,
        item_uses_left=item.uses,
    )
    # Initialise Nine Lives charges
    if sig.id == "nine_lives":
        c.ability_charges["nine_lives"] = 3
    # Initialise Cunning Dodge flag
    if defn.id == "reynard":
        c.ability_charges["cunning_dodge"] = 1
    # Initialise Holy Diadem
    if item.id == "holy_diadem":
        c.ability_charges["holy_diadem"] = 1
    if defn.cls == "Warlock":
        c.ability_charges["malice"] = 0
        c.ability_charges["malice_cap"] = 6
    if defn.id == "rapunzel":
        c.ability_charges["flowing_locks_ready"] = 1
    return c


def create_team(player_name: str, picks: list) -> TeamState:
    """
    picks = [
      {"definition": AdventurerDef, "signature": Ability,
       "basics": [Ability, Ability], "item": Item},
      ...   (3 entries)
    ]
    First pick is assigned to frontline; second/third to back_left / back_right.
    """
    slots = [SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT]
    members = []
    for i, p in enumerate(picks):
        members.append(make_combatant(
            p["definition"], slots[i],
            p["signature"], p["basics"], p["item"],
        ))
    return TeamState(player_name=player_name, members=members)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def get_mode(actor: CombatantState, ability: Ability) -> AbilityMode:
    return ability.frontline if actor.slot == SLOT_FRONT else ability.backline


def is_ranged(unit: CombatantState) -> bool:
    if unit.defn.cls in ("Warlock", "Noble"):
        return unit.slot != SLOT_FRONT
    return unit.role == "ranged"


def is_melee(unit: CombatantState) -> bool:
    if unit.defn.cls in ("Warlock", "Noble"):
        return unit.slot == SLOT_FRONT
    return unit.role == "melee"


# Rulebook-defined status conditions (STATUS CONDITIONS section).
RULEBOOK_STATUS_CONDITIONS = {
    "burn", "root", "shock", "weaken", "expose", "guard", "spotlight",
}


def is_rulebook_status_condition(kind: str) -> bool:
    return kind in RULEBOOK_STATUS_CONDITIONS




def _ensure_malice_pool(unit: CombatantState):
    """Ensure each warlock has its own local malice state keys."""
    if unit.defn.cls != "Warlock":
        return
    unit.ability_charges.setdefault("malice", 0)
    unit.ability_charges.setdefault("malice_cap", 6)


def _get_malice_cap(unit: CombatantState) -> int:
    _ensure_malice_pool(unit)
    return unit.ability_charges.get("malice_cap", 6)


def _gain_malice(unit: CombatantState, amount: int, battle: BattleState, source: str = ""):
    if amount <= 0:
        return
    _ensure_malice_pool(unit)
    cur = unit.ability_charges.get("malice", 0)
    cap = _get_malice_cap(unit)
    new = min(cap, cur + amount)
    gained = new - cur
    unit.ability_charges["malice"] = new
    if gained > 0:
        suffix = f" ({source})" if source else ""
        battle.log_add(f"  {unit.name} gains {gained} Malice{suffix}. [{new}/{cap}]")


def _spend_malice(unit: CombatantState, amount: int, battle: BattleState, source: str = "") -> bool:
    _ensure_malice_pool(unit)
    cur = unit.ability_charges.get("malice", 0)
    if cur < amount:
        return False
    unit.ability_charges["malice"] = cur - amount
    suffix = f" ({source})" if source else ""
    battle.log_add(f"  {unit.name} spends {amount} Malice{suffix}. [{unit.ability_charges['malice']}/{_get_malice_cap(unit)}]")
    return True


def _has_signature_effect(unit: CombatantState, sig_id: str) -> bool:
    """True if unit has sig_id as own signature or temporarily copied signature."""
    if unit.sig.id == sig_id:
        return True
    return (
        unit.ability_charges.get("stolen_signature") == sig_id
        and unit.ability_charges.get("stolen_signature_dur", 0) > 0
    )


def _has_talent(unit: CombatantState, adventurer_id: str) -> bool:
    """True if unit has own talent or temporarily stolen talent from that adventurer."""
    if unit.defn.id == adventurer_id:
        return True
    return (
        unit.ability_charges.get("stolen_talent") == adventurer_id
        and unit.ability_charges.get("stolen_talent_dur", 0) > 0
    )
def slot_order_left_to_right(team: TeamState) -> List[CombatantState]:
    """Returns alive members in [back_left, front, back_right] order."""
    order = [SLOT_BACK_LEFT, SLOT_FRONT, SLOT_BACK_RIGHT]
    result = []
    for s in order:
        m = team.get_slot(s)
        if m:
            result.append(m)
    return result


def get_adjacent_left(team: TeamState, unit: CombatantState) -> Optional[CombatantState]:
    ordered = slot_order_left_to_right(team)
    idx = next((i for i, m in enumerate(ordered) if m == unit), None)
    if idx is None or idx == 0:
        return None
    return ordered[idx - 1]


def get_adjacent_right(team: TeamState, unit: CombatantState) -> Optional[CombatantState]:
    ordered = slot_order_left_to_right(team)
    idx = next((i for i, m in enumerate(ordered) if m == unit), None)
    if idx is None or idx == len(ordered) - 1:
        return None
    return ordered[idx + 1]


# ─────────────────────────────────────────────────────────────────────────────
# INITIATIVE
# ─────────────────────────────────────────────────────────────────────────────

def determine_initiative(battle: BattleState):
    fl1 = battle.team1.frontline()
    fl2 = battle.team2.frontline()
    spd1 = fl1.get_stat("speed") if fl1 else 0
    spd2 = fl2.get_stat("speed") if fl2 else 0

    raw_spd1, raw_spd2 = spd1, spd2  # before March Hare

    # March Hare On Time! talent: while March Hare is frontline, enemy frontline -15 speed
    if fl1 and fl1.defn.id == "march_hare" and fl2:
        spd2 = max(1, spd2 - 15)
    if fl2 and fl2.defn.id == "march_hare" and fl1:
        spd1 = max(1, spd1 - 15)

    n1 = fl1.name if fl1 else "none"
    n2 = fl2.name if fl2 else "none"
    mh1 = f" (adj from {raw_spd1})" if raw_spd1 != spd1 else ""
    mh2 = f" (adj from {raw_spd2})" if raw_spd2 != spd2 else ""

    if spd1 > spd2:
        battle.init_player = 1
        battle.prev_loser  = 2
        battle.init_reason = f"{n1} SPD {spd1}{mh1} > {n2} SPD {spd2}{mh2} — P1 acts first"
    elif spd2 > spd1:
        battle.init_player = 2
        battle.prev_loser  = 1
        battle.init_reason = f"{n2} SPD {spd2}{mh2} > {n1} SPD {spd1}{mh1} — P2 acts first"
    else:
        # Tie: previous round loser acts first
        battle.init_player = battle.prev_loser
        battle.prev_loser  = 1 if battle.init_player == 2 else 2
        battle.init_reason = (
            f"{n1} SPD {spd1}{mh1} = {n2} SPD {spd2}{mh2} — tied!"
            f" P{battle.init_player} acts first (last round's loser)"
        )

    # Round 1: initiative loser gets extra swap phase
    if battle.round_num == 1:
        battle.r1_extra_swap_player = battle.prev_loser
    else:
        battle.r1_extra_swap_player = None

    battle_log.section(f"ROUND {battle.round_num}")
    battle.log_add(f"Round {battle.round_num} — P{battle.init_player} has initiative.")
    if battle.r1_extra_swap_player is not None:
        battle.log_add(f"P{battle.r1_extra_swap_player} receives a free formation swap.")
    battle.log_tech(
        f"INITIATIVE: P1 FL={fl1.name if fl1 else 'none'} spd={spd1}"
        f"{f' (MH adj from {raw_spd1})' if raw_spd1 != spd1 else ''}"
        f"  vs  P2 FL={fl2.name if fl2 else 'none'} spd={spd2}"
        f"{f' (MH adj from {raw_spd2})' if raw_spd2 != spd2 else ''}"
        f"  →  P{battle.init_player} acts first"
        + (f"  [TIE → prev_loser used]" if spd1 == spd2 else "")
    )
    # Full state snapshot at round start
    battle.log_tech(f"ROUND {battle.round_num} STATE SNAPSHOT:")
    for team_num, team_obj in [(1, battle.team1), (2, battle.team2)]:
        for unit in team_obj.members:
            if unit.ko:
                battle.log_tech(f"  P{team_num} {unit.name} [KO]")
            else:
                sts = ", ".join(
                    f"{s.kind}({s.duration}r)" for s in unit.statuses
                ) or "-"
                bfs = ", ".join(
                    f"{b.stat}+{b.amount}({b.duration}r)" for b in unit.buffs
                ) or "-"
                dbs = ", ".join(
                    f"{d.stat}-{d.amount}({d.duration}r)" for d in unit.debuffs
                ) or "-"
                battle.log_tech(
                    f"  P{team_num} {unit.name}[{unit.slot}]"
                    f" HP={unit.hp}/{unit.max_hp}"
                    f" ATK={unit.get_stat('attack')}(base={unit.defn.attack})"
                    f" DEF={unit.get_stat('defense')}(base={unit.defn.defense})"
                    f" SPD={unit.get_stat('speed')}(base={unit.defn.speed})"
                )
                battle.log_tech(
                    f"    statuses=[{sts}]  buffs=[{bfs}]  debuffs=[{dbs}]"
                )


# ─────────────────────────────────────────────────────────────────────────────
# PASSIVE ABILITY STAT BONUSES  (applied as 1-round buffs at round start)
# ─────────────────────────────────────────────────────────────────────────────

def apply_passive_stats(team: TeamState, battle: BattleState):
    """
    For passive abilities that grant flat stat buffs, apply them as 1-round
    buffs at the start of each round so they are included in all stat queries.
    Also handles Porcine Honor (guard at round start) and Sturdy Home.
    """
    for unit in team.alive():
        passives = [a for a in (unit.basics + [unit.sig]) if a.passive]
        mode_key = unit.slot

        for ab in passives:
            mode = ab.frontline if unit.slot == SLOT_FRONT else ab.backline
            if mode.unavailable:
                continue

            # Flat stat buffs
            if mode.atk_buff:
                unit.add_buff("attack", mode.atk_buff, 1)
            if mode.def_buff:
                unit.add_buff("defense", mode.def_buff, 1)
            if mode.spd_buff:
                unit.add_buff("speed", mode.spd_buff, 1)

            # Porcine Honor: guard at start of round
            if ab.id == "porcine_honor":
                if unit.slot == SLOT_FRONT:
                    unit.add_status("guard", 1)
                    battle.log_add(f"{unit.name} is Guarded by Porcine Honor.")
                else:
                    front = team.frontline()
                    if front:
                        front.add_status("guard", 1)
                        battle.log_add(f"{front.name} is Guarded by Porcine Honor.")

            # Sturdy Home: bonus defense to allies (not the carrier)
            if ab.id == "sturdy_home":
                bonus = 7 if unit.slot == SLOT_FRONT else 10
                if unit.slot == SLOT_FRONT:
                    for ally in team.alive():
                        if ally != unit:
                            ally.add_buff("defense", bonus, 1)
                else:
                    # Backline mode only affects the current frontline ally.
                    front = team.frontline()
                    if front and front != unit:
                        front.add_buff("defense", bonus, 1)

            # Protection: allies +defense (not the carrier)
            if ab.id == "protection":
                bonus = 10 if unit.slot == SLOT_FRONT else 5
                for ally in team.alive():
                    if ally != unit:
                        ally.add_buff("defense", bonus, 1)

            # Sanctuary: end-of-round heal is handled in end_round

            # Ivory Tower: apply stance-dependent enemy stat debuffs
            if ab.id == "ivory_tower":
                enemy_team = battle.get_enemy(1 if team == battle.team1 else 2)
                for foe in enemy_team.alive():
                    if unit.slot == SLOT_FRONT and is_ranged(foe):
                        foe.add_debuff("defense", 10, 1)
                    if unit.slot != SLOT_FRONT and is_melee(foe):
                        foe.add_debuff("attack", 10, 1)

        # Red and Wolf (Risa talent): below 50% HP
        if unit.defn.id == "risa_redcloak" and unit.hp < unit.max_hp * 0.5:
            unit.add_buff("attack", 15, 1)
            unit.add_buff("speed",  15, 1)

        # Crawling Abode (Witch talent): +10 spd if enemy frontline is statused
        if unit.sig.id == "crawling_abode" or any(
                b.id == "crawling_abode" for b in unit.basics):
            enemy_team = battle.get_enemy(1 if team == battle.team1 else 2)
            efl = enemy_team.frontline()
            if efl and efl.statuses:
                unit.add_buff("speed", 10, 1)

        # Hunter's Badge passive (already handled above in the loop)

        # Two Lives: set untargetable flag
        unit.untargetable = (
            unit.defn.id == "ashen_ella" and unit.slot != SLOT_FRONT
        )

        # Fleetfooted: refresh "first incoming ability" flag each round
        if any(b.id == "fleetfooted" for b in unit.basics):
            unit.ability_charges["fleetfooted_ready"] = 1

        # Midnight Dour: reset reactive swap trigger each round
        if unit.sig.id == "midnight_dour":
            unit.ability_charges["midnight_dour_triggered"] = 0

        # Birdsong BL: apply stacked +5 Atk bonus as a 1-round buff each round
        if _has_signature_effect(unit, "birdsong") and unit.slot != SLOT_FRONT:
            stacks = unit.ability_charges.get("birdsong_stacks", 0)
            if stacks > 0 and unit.ability_charges.get("birdsong_dur", 0) > 0:
                unit.add_buff("attack", stacks * 5, 1)

    # Banner of Command is handled in the swap logic


# ─────────────────────────────────────────────────────────────────────────────
# TARGETING
# ─────────────────────────────────────────────────────────────────────────────

def get_legal_targets(
    battle: BattleState,
    acting_player: int,
    actor: CombatantState,
    ability: Ability,
) -> List[CombatantState]:
    """
    Returns all legal target CombatantState objects for the given ability.
    Heal/support abilities return ally targets.
    Attack/status abilities return enemy targets subject to range rules.
    """
    team       = battle.get_team(acting_player)
    enemy_team = battle.get_enemy(acting_player)
    mode       = get_mode(actor, ability)

    if mode.unavailable:
        return []

    # Abilities that always target self (no player choice needed)
    _SELF_SPECIALS = {
        "heros_charge_ignore_pride_front", "riposte_bl", "struck_midnight_untargetable",
        "rabbit_hole_extra_action", "stitch_extra_action_now", "devils_due",
        "final_deception", "redemption", "unbreakable_defense",
        "nbth_self_reduce", "shimmering_valor_front", "shimmering_valor_back",
        "falling_kingdom", "feign_weakness_retaliate_45", "last_laugh",
        "crumb_trail_drop", "blue_faerie_boon", "turn_to_foam", "misappropriate_front",
        "fated_duel", "severed_tether", "happily_ever_after",
        "blood_pact_front",
    }
    # Specials that explicitly target allies.
    _ALLY_SPECIALS = {
        "rabbit_hole_swap", "deathlike_slumber", "cinder_blessing_avg",
        "straw_to_gold_front", "straw_to_gold_back", "summons_swap",
    }
    # Specials that require an enemy target despite having no power/status fields.
    _ENEMY_SPECIALS = {
        "blood_hunt_hp_avg", "taunt_front_ranged", "subterfuge_swap",
        "cutpurse_swap_frontline", "heros_bargain_back",
    }

    # ── Self-targeting abilities ──────────────────────────────────────────────
    if mode.special in _SELF_SPECIALS:
        return [actor]

    # Inferred self-target abilities: only self-affecting fields and no ally/enemy effect fields.
    has_self_effect = any((
        mode.heal_self > 0, mode.guard_self, bool(mode.self_status),
        mode.atk_buff > 0, mode.spd_buff > 0, mode.def_buff > 0,
    ))
    has_ally_effect = any((
        mode.heal > 0, mode.heal_lowest > 0, mode.guard_target,
        mode.guard_all_allies, mode.guard_frontline_ally,
        ability.id in ("toxin_purge", "cinder_blessing", "lakes_gift", "bless", "journey_to_avalon"),
        mode.special in _ALLY_SPECIALS,
    ))
    has_enemy_effect = any((
        mode.power > 0, bool(mode.status), bool(mode.status2), bool(mode.status3),
        mode.atk_debuff > 0, mode.spd_debuff > 0, mode.def_debuff > 0,
        mode.special in _ENEMY_SPECIALS,
    ))
    if has_self_effect and not has_ally_effect and not has_enemy_effect:
        return [actor]

    # ── Heal / support targets (allies) ──────────────────────────────────────
    if (mode.power == 0 and (
            mode.heal > 0 or mode.heal_lowest > 0
            or mode.guard_target or mode.guard_self
            or ability.id in ("toxin_purge", "cinder_blessing", "lakes_gift", "bless")
    )) or mode.special in _ALLY_SPECIALS:
        # Journey to Avalon can target KO'd allies (revive)
        if ability.id == "journey_to_avalon":
            return [m for m in team.members if m != actor]
        # Pure heal targets allies only (not self); self-heal uses heal_self field
        if mode.heal > 0 and not mode.heal_self:
            return [m for m in team.alive() if m != actor]
        return list(team.alive())
    # ── Enemy targets ─────────────────────────────────────────────────────────
    enemies = [e for e in enemy_team.alive() if not e.untargetable]

    # Spread Fortune BL (Robin): spread abilities target all enemies
    if mode.spread and _has_signature_effect(actor, "spread_fortune") and actor.slot != SLOT_FRONT:
        return enemies

    melee_unit = is_melee(actor)
    ranged_unit = is_ranged(actor)

    # Shadowstep (Constantine): melee can target Exposed backline
    shadowstep = _has_talent(actor, "lucky_constantine")

    legal = []
    for e in enemies:
        if e.slot == SLOT_FRONT:
            legal.append(e)
        elif e.slot in (SLOT_BACK_LEFT, SLOT_BACK_RIGHT):
            if ranged_unit:
                # Ranged from frontline: can target all
                if actor.slot == SLOT_FRONT:
                    legal.append(e)
                # Ranged from backline: only same-side backline and frontline
                elif actor.slot == SLOT_BACK_LEFT and e.slot == SLOT_BACK_LEFT:
                    legal.append(e)
                elif actor.slot == SLOT_BACK_RIGHT and e.slot == SLOT_BACK_RIGHT:
                    legal.append(e)
                # (frontline already caught above)
            elif melee_unit:
                # Melee cannot target backline normally
                if e.has_status("spotlight"):
                    legal.append(e)
                elif shadowstep and e.has_status("expose"):
                    legal.append(e)
                elif actor.defn.id == "rapunzel" and actor.ability_charges.get("flowing_locks_ready", 0) > 0:
                    legal.append(e)
                elif actor.ability_charges.get("severed_tether_active", 0) > 0:
                    legal.append(e)

    # Taunt: taunted actor must target the unit with Knight's Challenge, bypassing
    # normal range restrictions (Roland in backline is still targetable when taunt active)
    if actor.has_status("taunt"):
        roland_units = [e for e in enemy_team.alive()
                        if e.sig.id == "knights_challenge" and not e.untargetable]
        if roland_units:
            legal = roland_units

    # Hypnotic Aura: Shocked actors are redirected based on Hunold's position
    # FL Hunold → redirect to his back_left; BL Hunold → redirect to his frontline
    if actor.has_status("shock"):
        hunold = next(
            (m for m in enemy_team.alive() if m.sig.id == "hypnotic_aura"), None
        )
        if hunold:
            if hunold.slot == SLOT_FRONT:
                redirect = enemy_team.get_slot(SLOT_BACK_LEFT)
            else:
                redirect = enemy_team.frontline()
            if redirect and not redirect.ko and not redirect.untargetable:
                legal = [redirect]

    # Fated Duel: acting duelists may only target their duel counterpart.
    if getattr(battle, "fated_duel_rounds", 0) > 0 and actor in getattr(battle, "fated_duel_units", ()): 
        duel_units = set(getattr(battle, "fated_duel_units", ()))
        legal = [u for u in legal if u in duel_units and u != actor]

    # Spread abilities auto-target all legal targets; the caller picks the first
    # and execute_ability iterates. We still return the full legal set.
    return legal


def get_legal_item_targets(
    battle: BattleState,
    acting_player: int,
    actor: CombatantState,
) -> List[CombatantState]:
    """Return legal item targets based on item effect type."""
    item = actor.item
    if item.passive or actor.item_uses_left <= 0:
        return []

    team = battle.get_team(acting_player)
    enemy_team = battle.get_enemy(acting_player)

    # Explicit self-only actives (stat buffs / hourglass-like effects)
    if item.atk_buff or item.spd_buff or item.def_buff or item.special == "ancient_hourglass":
        return [actor]

    # Self-only heal items
    if item.heal > 0 and item.heal_self_only:
        return [actor]

    # Ally-targeting items
    if item.heal > 0 or item.guard:
        return list(team.alive())

    # Swap item targets an ally (not self)
    if item.special == "smoke_bomb_swap":
        return [u for u in team.alive() if u != actor]

    # Offensive status items (e.g., Hunter's Net)
    if item.status and not item.guard:
        return [e for e in enemy_team.alive() if not e.untargetable]

    # Fallback to self
    return [actor]


def can_use_ability(
    actor: CombatantState,
    ability: Ability,
    team: TeamState,
) -> bool:
    if actor.ko or actor.cant_act:
        return False
    if ability.passive:
        return False
    mode = get_mode(actor, ability)
    if mode.unavailable:
        return False
    # Two Lives: Ella can only use abilities from frontline
    # (exceptions: Crowstorm backline, Fae Blessing backline — they have
    #  "ella_ignore_two_lives" in their special field)
    if actor.defn.id == "ashen_ella" and actor.slot != SLOT_FRONT:
        if "ella_ignore_two_lives" not in mode.special:
            return False
    # Twist: only when last alive
    if ability.category == "twist":
        if len(team.alive()) != 1 or team.alive()[0] != actor:
            return False
        if actor.twist_used:
            return False
    # Ranged recharge
    if is_ranged(actor) and actor.must_recharge:
        return False
    if ability.id == "summons" and actor.ability_charges.get("summons_cd", 0) > 0:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# DAMAGE FORMULA
# ─────────────────────────────────────────────────────────────────────────────

def compute_damage(
    actor: CombatantState,
    target: CombatantState,
    ability: Ability,
    mode: AbilityMode,
    acting_player: int,
    battle: BattleState,
    is_spread: bool = False,
    ignore_pride: bool = False,
    is_retaliation: bool = False,
) -> int:
    power = mode.power
    if power <= 0:
        return 0
    _base_power = power  # track for logging

    # ── Conditional power bonuses ─────────────────────────────────────────────
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

    # Slam FL: +15 power if user is Guarded
    if ability.id == "slam" and actor.slot == SLOT_FRONT and actor.has_status("guard"):
        power += 15

    # Magic Growth backline: Jack's next ability had +15 power flag
    if actor.ability_charges.get("magic_growth_bonus", 0) > 0 \
            and ability.id != "magic_growth":
        power += 15
        actor.ability_charges["magic_growth_bonus"] = 0

    # Crumb Trail FL: +20 power if an ally picked up the crumb this turn
    if ability.id == "crumb_trail" and actor.slot == SLOT_FRONT \
            and battle.crumb_picked_up == acting_player:
        power += 20

    # Shove Over BL: +15 power on next attack against the weakened target
    if target.ability_charges.get("shove_over_next_bonus", 0) > 0 and ability.id != "shove_over":
        power += 15
        target.ability_charges["shove_over_next_bonus"] = 0

    # Wooden Wallop FL: +10 power per Malice
    if ability.id == "wooden_wallop" and actor.slot == SLOT_FRONT:
        power += actor.ability_charges.get("malice", 0) * 5

    # Gallant Charge FL: +20 power if actor was backline last round
    if ability.id == "gallant_charge" and actor.slot == SLOT_FRONT and actor.ability_charges.get("was_backline_last_round", 0) > 0:
        power += 20

    # Lower Guard FL: +15 power if target has a stat debuff
    if ability.id == "lower_guard" and actor.slot == SLOT_FRONT and target.debuffs:
        power += 15

    # Condescend BL rider: next ability against target has +15 power
    if target.ability_charges.get("condescend_bonus", 0) > 0 and ability.id != "condescend":
        power += 15
        target.ability_charges["condescend_bonus"] = 0

    # Natural Order FL: +15 if target has not swapped for 2+ rounds
    if _has_signature_effect(actor, "natural_order") and actor.slot == SLOT_FRONT and target.ability_charges.get("rounds_since_swap", 0) >= 2:
        power += 15

    # Spinning Wheel FL: +7 damage per unique stat buff among all other adventurers
    if _has_signature_effect(actor, "spinning_wheel") and actor.slot == SLOT_FRONT:
        all_others = [u for u in battle.team1.alive() + battle.team2.alive() if u != actor]
        unique_buff_stats = {b.stat for u in all_others for b in u.buffs if b.duration > 0}
        power += 7 * len(unique_buff_stats)

    # ── Sovereign Edict FL: if target has 2+ statuses, apply def_ignore and guard bypass ──
    _sovereign_edict_override = False
    if ability.id == "sovereign_edict" and actor.slot == SLOT_FRONT:
        active_statuses_se = [s for s in target.statuses if s.duration > 0]
        if len(active_statuses_se) >= 2:
            _sovereign_edict_override = True

    # Rend BL: consume mark for +10 Power on this actor's next ability vs that target
    rend_key = f"rend_bonus_{target.defn.id}"
    if actor.ability_charges.get(rend_key, 0) > 0:
        power += actor.ability_charges.pop(rend_key)

    # ── Attack / Defense ──────────────────────────────────────────────────────
    battle.log_tech(
        f"DMGCALC [{ability.name}] {actor.name}[{actor.slot}] → {target.name}[{target.slot}]"
        + (f" (spread)" if is_spread else "")
    )
    battle.log_tech(
        f"  power={power}" + (f" (base={_base_power})" if power != _base_power else "")
    )
    attack = actor.get_stat("attack")
    defense = target.get_stat("defense")

    # Arcane Focus item: +7 attack from backline
    if actor.item.id == "arcane_focus" and actor.slot != SLOT_FRONT:
        attack += actor.item.atk_bonus_back

    # Belligerence passive BL: -20% effective attack when targeting Jack backline
    if _has_signature_effect(target, "belligerence") and target.slot != SLOT_FRONT:
        attack = max(1, math.ceil(attack * 0.80))

    # Def ignore
    if mode.def_ignore_pct:
        defense = max(1, math.ceil(defense * (1 - mode.def_ignore_pct / 100)))
    # Cleave BL: consume mark for 10% Defense ignore on this actor's next ability vs that target
    cleave_key = f"cleave_bonus_{target.defn.id}"
    if actor.ability_charges.get(cleave_key, 0) > 0:
        extra_ign = actor.ability_charges.pop(cleave_key)
        defense = max(1, math.ceil(defense * (1 - extra_ign / 100)))
    # Sovereign Edict: fully ignore defense when 2+ statuses on target
    if _sovereign_edict_override:
        defense = 1
        # Also clear defense buffs (represented as debuffs to defense)
        # Just set defense to 1 to ignore all of it

    # Belligerence passive FL: Jack ignores 20% enemy Defense (frontline mode)
    if _has_signature_effect(actor, "belligerence"):
        if actor.slot == SLOT_FRONT:
            defense = max(1, math.ceil(defense * 0.80))

    raw = power * (attack / max(1, defense))
    dmg = math.ceil(raw)
    battle.log_tech(f"  atk={attack} def={defense} raw={raw:.2f} ceil={dmg}")

    # ── Outgoing multipliers ──────────────────────────────────────────────────
    if actor.has_status("weaken"):
        dmg = math.ceil(dmg * 0.80)

    # Giant Slayer (Little Jack): +30% vs higher max HP
    if _has_talent(actor, "little_jack") and target.max_hp > actor.max_hp:
        dmg = math.ceil(dmg * 1.30)

    # Heedless Pride (Frederic): deals 20% bonus damage to enemy frontline
    if _has_talent(actor, "frederic") and target.slot == SLOT_FRONT and not ignore_pride:
        dmg = math.ceil(dmg * 1.20)

    # ── Incoming multipliers ──────────────────────────────────────────────────
    if target.has_status("expose"):
        dmg = math.ceil(dmg * 1.20)

    # Bricklayer (Porcus): if single hit ≥ 25% max HP, reduce by 40% and weaken attacker
    if _has_talent(target, "porcus_iii"):
        threshold = math.ceil(target.max_hp * 0.25)
        if dmg >= threshold:
            dmg = math.ceil(dmg * 0.60)
            actor.add_status("weaken", 2)
            battle.log_add(f"Bricklayer! {actor.name} is Weakened.")

    if not mode.ignore_guard and not _sovereign_edict_override and target.has_status("guard"):
        dmg = math.ceil(dmg * 0.80)

    # Heedless Pride (Frederic): takes 10% more from enemy frontline
    if _has_talent(target, "frederic") and actor.slot == SLOT_FRONT and not ignore_pride:
        dmg = math.ceil(dmg * 1.10)

    # Electrifying Trance (Hunold): shocked enemies take +15 dmg
    if _actor_has_talent(actor.defn.id, acting_player, battle, "electrifying_trance"):
        hunold = _find_hunold(acting_player, battle)
        if hunold and target.has_status("shock"):
            dmg += 15

    # Keen Eye (Robin): +10 damage vs backline
    if _has_talent(actor, "robin_hooded_avenger")             and target.slot in (SLOT_BACK_LEFT, SLOT_BACK_RIGHT):
        dmg += 10

    # Challenge Accepted (Green Knight): +15 to enemy across from him
    if _has_talent(actor, "green_knight") and actor.slot == target.slot:
        dmg += 15

    # Chosen One: attackers who damaged champion take +25 from Prince's next ability
    if actor.defn.id == "prince_charming" and target.ability_charges.get("chosen_one_mark", 0) > 0:
        dmg += 25
        target.ability_charges["chosen_one_mark"] = 0

    # Command marks
    acting_team = battle.get_team(acting_player)
    if any(_has_signature_effect(u, "command") and u.slot == SLOT_FRONT and u != actor for u in acting_team.alive()):
        if target.ability_charges.get(f"command_allies_p{acting_player}", 0) > 0:
            dmg += 10
    if any(_has_signature_effect(u, "command") and u.slot != SLOT_FRONT and u == actor for u in acting_team.alive()):
        if target.ability_charges.get(f"command_user_p{acting_player}", 0) > 0:
            dmg += 10

    # Cunning Dodge (Reynard): first ability deals 50% damage
    if _has_talent(target, "reynard") \
            and target.ability_charges.get("cunning_dodge", 0) > 0:
        dmg = math.ceil(dmg * 0.50)
        target.ability_charges["cunning_dodge"] = 0
        battle.log_add(f"Cunning Dodge! {target.name} takes reduced damage.")

    # Shadowstep (Constantine): -10 damage to backline
    if _has_talent(actor, "lucky_constantine") \
            and target.slot in (SLOT_BACK_LEFT, SLOT_BACK_RIGHT):
        dmg = max(0, dmg - 10)

    # Spread: 50% damage
    if is_spread:
        # Spread Fortune (Robin): FL halves the nerf (75% instead of 50%); BL targets all (handled in get_legal_targets)
        if _has_signature_effect(actor, "spread_fortune") and actor.slot == SLOT_FRONT:
            dmg = math.ceil(dmg * 0.75)  # halved nerf: 75% instead of 50%
        else:
            dmg = math.ceil(dmg * 0.50)

    # Witched Crawling Abode: +10 to all abilities vs enemies with 2+ statuses
    if _has_signature_effect(actor, "crawling_abode") and len(target.statuses) >= 2:
        dmg += 10

    # Misericorde item: +10 vs statused target
    if actor.item.id == "misericorde" and target.statuses:
        dmg += actor.item.flat_vs_statused

    # Family Seal item: +10 damage on signature abilities (non-retaliation only)
    if not is_retaliation and ability.category == "signature" and actor.item.signature_flat_bonus > 0:
        dmg += actor.item.signature_flat_bonus

    # Drown in the Loch: bonus_damage status = +10 flat incoming
    if target.has_status("bonus_damage"):
        dmg += 10

    # Stalwart passive basic: FL carrier takes -10; BL carrier protects frontline ally
    stalwart_protects = False
    defending_team = battle.get_enemy(acting_player)
    for ally in defending_team.alive():
        if any(b.id == "stalwart" for b in ally.basics):
            if ally == target:                         # FL: carrier being hit
                stalwart_protects = True
            elif ally.slot != SLOT_FRONT and target.slot == SLOT_FRONT:  # BL: frontline ally hit
                stalwart_protects = True
            break
    if stalwart_protects:
        dmg = max(0, dmg - 10)

    # Hot Mitts passive FL: +10% damage vs already-Burned enemies (or Burn them after, below)
    if _has_signature_effect(actor, "hot_mitts") and actor.slot == SLOT_FRONT and target.has_status("burn"):
        dmg = math.ceil(dmg * 1.10)

    # Fleetfooted: first incoming ability each round deals reduced damage
    if target.ability_charges.get("fleetfooted_ready", 0) > 0:
        if any(b.id == "fleetfooted" for b in target.basics):
            reduction = 0.20 if target.slot == SLOT_FRONT else 0.10
            dmg = math.ceil(dmg * (1 - reduction))
            target.ability_charges["fleetfooted_ready"] = 0

    # Per-round damage reduction on target
    if target.dmg_reduction > 0:
        dmg = math.ceil(dmg * (1 - target.dmg_reduction))

    # Silver Aegis (Roland): 0 damage from first ability after swapping to frontline
    if target.defn.id == "sir_roland" \
            and target.ability_charges.get("silver_aegis", 0) > 0:
        dmg = 0
        target.ability_charges["silver_aegis"] = 0
        battle.log_add(f"Silver Aegis! {target.name} takes 0 damage.")

    # Stolen Voices (Asha): enemy signature damage reduced by Malice while she is frontline
    defending_team = battle.get_enemy(acting_player)
    for u in defending_team.alive():
        if _has_talent(u, "sea_wench_asha") and u.slot == SLOT_FRONT and ability.category == "signature":
            malice = u.ability_charges.get("malice", 0)
            dmg = max(0, dmg - malice * 5)
            break

    # ── NPC Campaign Talents ──────────────────────────────────────────────────

    # Blood Frenzy (Apex Fighter): +10 damage to Exposed targets
    if actor.defn.id == "npc_apex_fighter" and target.has_status("expose"):
        dmg += 10

    # Bastion (Apex Warden): frontline ally of Apex Warden takes -10 from abilities
    bastion_target_team = battle.get_enemy(acting_player)
    for ally in bastion_target_team.alive():
        if ally.defn.id == "npc_apex_warden":
            if target.slot == SLOT_FRONT and target != ally:
                dmg = max(0, dmg - 10)
            break

    # Tyranny (Dragon Heads): enemies with 2+ active statuses take +5 damage
    if actor.defn.id in ("npc_dragon_noble", "npc_dragon_mage", "npc_dragon_warlock"):
        active_statuses = [s for s in target.statuses if s.duration > 0]
        if len(active_statuses) >= 2:
            dmg += 5

    # Cataclysm FL: +10 power per status on target (added to dmg after calc)
    if ability.id == "cataclysm" and actor.slot == SLOT_FRONT and not is_spread:
        active_statuses = [s for s in target.statuses if s.duration > 0]
        dmg += len(active_statuses) * 10

    battle.log_tech(f"  FINAL_DMG={max(0, dmg)}")
    return max(0, dmg)


def _actor_has_talent(actor_id, acting_player, battle, talent_id):
    """Check if a specific talent is active for the acting player's team."""
    if talent_id == "electrifying_trance":
        return _find_hunold(acting_player, battle) is not None
    return False


def _find_hunold(acting_player, battle):
    team = battle.get_team(acting_player)
    for m in team.alive():
        if m.defn.id == "hunold_the_piper":
            return m
    return None


# ─────────────────────────────────────────────────────────────────────────────
# APPLY EFFECTS
# ─────────────────────────────────────────────────────────────────────────────

def deal_damage(
    actor: CombatantState,
    target: CombatantState,
    dmg: int,
    ability: Ability,
    mode: AbilityMode,
    acting_player: int,
    battle: BattleState,
    is_retaliation: bool = False,
):
    """Apply damage to target with all on-hit effects (KO, vamp, Spiked Mail, reflect)."""
    if target.ko:
        return

    # Holy Diadem: survive fatal damage at 1 HP once per battle; no damage this round
    if target.item.id == "holy_diadem" \
            and target.ability_charges.get("holy_diadem", 0) > 0 \
            and dmg >= target.hp:
        dmg = 0
        target.ability_charges["holy_diadem"] = 0
        target.dmg_reduction = 1.0  # block all further incoming damage this round
        battle.log_add(f"Holy Diadem activates! {target.name} survives at 1 HP.")
        target.hp = 1
        return

    _hp_before = target.hp
    target.hp -= dmg
    # Command / Chosen One attacker marks
    defending_player = 2 if acting_player == 1 else 1
    defending_team = battle.get_team(defending_player)
    for u in defending_team.alive():
        has_command = _has_signature_effect(u, "command") or any(b.id == "command" for b in u.basics)
        if has_command:
            if u.slot == SLOT_FRONT and target == u:
                actor.ability_charges[f"command_allies_p{defending_player}"] = 2
            elif u.slot != SLOT_FRONT and target in defending_team.alive():
                actor.ability_charges[f"command_user_p{defending_player}"] = 2
        if _has_signature_effect(u, "chosen_one") and u.ability_charges.get("chosen_one_champion") == target.defn.id:
            actor.ability_charges["chosen_one_mark"] = 2

    if target.hp <= 0:
        target.hp = 0
        target.ko = True
    battle.log_tech(
        f"HPCHANGE {target.name}: {_hp_before} → {target.hp}  (-{dmg})"
        + (" **KO**" if target.ko else "")
    )

    # Cursed Armor basic: gain 1 Malice when damaged by enemy ability
    if dmg > 0 and any(b.id == "cursed_armor" for b in target.basics):
        _gain_malice(target, 1, battle, "Cursed Armor")

    # ── Vamp ──────────────────────────────────────────────────────────────────
    vamp_ratio = mode.vamp
    # Double vamp (Blood Hunt frontline): uses 2× current base vamp, no own base
    if mode.double_vamp_no_base:
        # Use only the talent-based vamp (Red and Wolf: 20%) doubled
        talent_vamp = _get_talent_vamp(actor)
        vamp_ratio = talent_vamp * 2.0
    else:
        # Add talent vamp on top
        vamp_ratio += _get_talent_vamp(actor)
        # Add Vampire Fang item vamp
        if actor.item.id == "vampire_fang":
            vamp_ratio += actor.item.vamp

    if vamp_ratio > 0 and dmg > 0:
        healed = math.ceil(dmg * vamp_ratio)
        do_heal(actor, healed, actor, battle)

    # ── Spiked Mail ───────────────────────────────────────────────────────────
    if target.item.id == "spiked_mail" and dmg > 0 and not target.ko:
        actor.hp -= 15
        if actor.hp <= 0:
            actor.hp = 0
            actor.ko = True
        battle.log_add(f"  Spiked Mail! {actor.name} takes 15 damage.")

    # ── Reflecting Pool (Lady talent or Lake's Gift status) ───────────────────
    if target.has_status("reflecting_pool") and dmg > 0:
        reflect_pct = 0.20 if actor.slot != SLOT_FRONT else 0.10
        reflect_dmg = math.ceil(dmg * reflect_pct)
        actor.hp = max(0, actor.hp - reflect_dmg)
        if actor.hp == 0:
            actor.ko = True
        battle.log_add(
            f"  Reflecting Pool: {actor.name} takes {reflect_dmg} reflected damage.")

    if _has_talent(target, "lady_of_reflections") and dmg > 0:
        reflect_pct = 0.20 if actor.slot != SLOT_FRONT else 0.10
        reflect_dmg = math.ceil(dmg * reflect_pct)
        actor.hp = max(0, actor.hp - reflect_dmg)
        if actor.hp == 0:
            actor.ko = True
        battle.log_add(f"  Reflecting Pool: {actor.name} takes {reflect_dmg} reflected damage.")

    # ── Double Double (Witch of the Woods talent) ─────────────────────────────
    if _has_talent(actor, "witch_of_the_woods") and target.statuses and dmg > 0:
        # Spread target's last inflicted status to enemy adjacent to their left
        enemy_team = battle.get_enemy(acting_player)
        adj = get_adjacent_left(enemy_team, target)
        status = target.last_status_inflicted
        if adj and status and is_rulebook_status_condition(status):
            adj.add_status(status, 2)
            battle.log_add(f"  Double Double! {adj.name} gains {status}.")


    # ── Awaited Blow FL: retaliate vs incoming attackers not across from Green Knight ─
    if not is_retaliation and dmg > 0 and _has_signature_effect(target, "awaited_blow") and target.slot == SLOT_FRONT and actor.slot != target.slot and not target.ko:
        retaliate_ability = Ability(
            id="awaited_blow_retaliation", name="Awaited Blow", category="signature", passive=False,
            frontline=AbilityMode(power=40), backline=AbilityMode(power=40)
        )
        retaliate_mode = retaliate_ability.frontline
        retaliate_player = 2 if acting_player == 1 else 1
        retaliate_dmg = compute_damage(
            target,
            actor,
            retaliate_ability,
            retaliate_mode,
            retaliate_player,
            battle,
            is_retaliation=True,
        )
        battle.log_add(f"  Awaited Blow! {target.name} retaliates against {actor.name} for {retaliate_dmg} damage.")
        deal_damage(target, actor, retaliate_dmg, retaliate_ability, retaliate_mode, retaliate_player, battle, is_retaliation=True)

    # ── Nine Lives (Constantine passive) ─────────────────────────────────────
    if target.defn.id == "lucky_constantine" \
            and _has_signature_effect(target, "nine_lives") \
            and target.ability_charges.get("nine_lives", 0) > 0 \
            and actor.has_status("expose") and target.ko:
        target.ko = False
        target.hp = 1
        target.ability_charges["nine_lives"] -= 1
        charges = target.ability_charges["nine_lives"]
        battle.log_add(f"  Nine Lives! {target.name} survives at 1 HP. ({charges} left)")

    # ── Sugar Rush (Gretel talent) ─────────────────────────────────────────────
    if _has_talent(actor, "gretel") and target.ko:
        actor.add_buff("attack", 15, 2)
        actor.add_buff("speed",  10, 2)
        battle.log_add(f"  Sugar Rush! {actor.name} gains +15 Atk, +10 Spd for 2 rounds.")

    # ── Garden of Thorns FL: root any attacker (not just melee) ─────────────
    if not is_retaliation and dmg > 0 and not target.ko \
            and _has_signature_effect(target, "garden_of_thorns") \
            and target.slot == SLOT_FRONT:
        actor.add_status("root", 2)
        battle.log_add(f"  Garden of Thorns! {actor.name} is Rooted.")

    # ── Midnight Dour FL: when Ella drops to ≤50% HP, swap with backline ally ─
    if not is_retaliation and not target.ko \
            and _has_signature_effect(target, "midnight_dour") and target.slot == SLOT_FRONT \
            and target.hp <= target.max_hp * 0.5 \
            and not target.has_status("root") \
            and target.ability_charges.get("midnight_dour_triggered", 0) == 0:
        target_team = battle.get_enemy(acting_player)
        for slot in (SLOT_BACK_LEFT, SLOT_BACK_RIGHT):
            ally = target_team.get_slot(slot)
            if ally and not ally.ko:
                target.ability_charges["midnight_dour_triggered"] = 1
                do_swap(target, ally, target_team, battle)
                battle.log_add(f"  Midnight Dour! {target.name} swaps to backline.")
                break

    # ── On-KO triggers (Postmortem Passage, Flame of Renewal) ─────────────────
    if target.ko and not is_retaliation:
        target_team = battle.get_enemy(acting_player)
        # Postmortem Passage: KO'd ally fires 40-power posthumous attack at attacker
        for m in target_team.alive():
            if _has_signature_effect(m, "postmortem_passage"):
                if not actor.ko:
                    post_dmg = max(0, math.ceil(
                        40 * (target.get_stat("attack") / max(1, actor.get_stat("defense")))
                    ))
                    if actor.has_status("guard"):
                        post_dmg = math.ceil(post_dmg * 0.80)
                    actor.hp = max(0, actor.hp - post_dmg)
                    if actor.hp == 0:
                        actor.ko = True
                    battle.log_add(
                        f"  Postmortem Passage! {target.name} fires {post_dmg} at {actor.name}.")
                break
        # Flame of Renewal (Liesl): only when LIESL HERSELF is KO'd
        if _has_signature_effect(target, "flame_of_renewal"):
            heal_amt = target.max_hp // 2
            for ally in target_team.alive():
                do_heal(ally, heal_amt, target, battle)
            battle.log_add(f"  Flame of Renewal! Allies healed {heal_amt} HP.")

    # ── Retaliation (Feign Weakness / Last Laugh) ─────────────────────────────
    if not is_retaliation and dmg > 0 and target.retaliate_power > 0:
        rp = target.retaliate_power
        rs = target.retaliate_speed_steal
        target.retaliate_power = 0
        target.retaliate_speed_steal = 0
        ret_atk = target.get_stat("attack")
        ret_def = actor.get_stat("defense")
        ret_dmg = max(0, math.ceil(rp * (ret_atk / max(1, ret_def))))
        if actor.has_status("guard") and not actor.has_status("expose"):
            ret_dmg = math.ceil(ret_dmg * 0.80)
        actor.hp = max(0, actor.hp - ret_dmg)
        if actor.hp == 0:
            actor.ko = True
        battle.log_add(f"  Retaliation! {target.name} counters for {ret_dmg} damage.")
        if rs > 0:
            target.add_buff("speed", rs, 2)
            actor.add_debuff("speed", rs, 2)
            battle.log_add(f"  Last Laugh: {target.name} steals {rs} Spd.")


def _get_talent_vamp(actor: CombatantState) -> float:
    """Talent-based vamp ratio for the actor."""
    if _has_talent(actor, "risa_redcloak") and actor.hp < actor.max_hp * 0.5:
        return 0.20
    return 0.0


def do_heal(
    target: CombatantState,
    amount: int,
    healer: CombatantState,
    battle: BattleState,
    action_desc: str = None,
):
    """Apply a heal with talent/item bonuses.
    action_desc: optional prefix for the log line, e.g. 'Aldric heals Risa'."""
    if target.has_status("no_heal"):
        battle.log_add(f"  {target.name} cannot be healed.")
        return

    if target.hp >= target.max_hp:
        return

    # Heart Amulet
    if healer.item.id == "heart_amulet":
        amount += healer.item.flat_heal_bonus

    # Benefactor (Aldric signature passive): heal 25%/15% more
    if _has_signature_effect(healer, "benefactor"):
        mult = 1.25 if healer.slot == SLOT_FRONT else 1.15
        amount = math.ceil(amount * mult)

    old = target.hp
    target.hp = min(target.max_hp, target.hp + amount)
    actual = target.hp - old
    if action_desc:
        battle.log_add(f"  {action_desc} for {actual} HP.")
    else:
        battle.log_add(f"  {target.name} heals {actual} HP.")

    # All-Caring (Aldric talent): healing Guards recipient (only when HP is actually restored)
    if actual > 0 and _has_talent(healer, "aldric_lost_lamb"):
        target.add_status("guard", 2)
        battle.log_add(f"  All-Caring: {target.name} is Guarded for 2 rounds.")

    # Purifying Flame (Liesl talent): Burn immunity + mark to Burn on next attack
    if _has_talent(healer, "matchstick_liesl"):
        target.add_status("burn_immune", 2)
        target.ability_charges["purifying_flame"] = 1
        battle.log_add(f"  Purifying Flame: {target.name} will Burn their next target.")

    # Medic passive: healing cures statuses (FL also cures debuffs)
    if any(b.id == "medic" for b in healer.basics):
        removed = []
        keep = []
        for s in target.statuses:
            if is_rulebook_status_condition(s.kind):
                removed.append(s.kind)
            else:
                keep.append(s)
        target.statuses = keep
        for kind in removed:
            _trigger_innocent_heart(target, kind, battle)
        if healer.slot == SLOT_FRONT:
            target.debuffs.clear()
            battle.log_add(
                f"  Medic: {target.name} cleansed of rulebook status conditions and stat debuffs.")
        else:
            battle.log_add(f"  Medic: {target.name} cleansed of rulebook status conditions.")


def apply_status_effect(
    target: CombatantState,
    kind: str,
    duration: int,
    battle: BattleState,
):
    if not kind or duration <= 0:
        return
    # Become Real FL: status immunity at 3+ Malice
    if _has_signature_effect(target, "become_real") and target.slot == SLOT_FRONT and target.ability_charges.get("malice", 0) >= 3:
        battle.log_add(f"  {target.name} is immune to statuses (Become Real).")
        return
    # Burn immunity check
    if kind == "burn" and target.has_status("burn_immune"):
        battle.log_add(f"  {target.name} is immune to Burn.")
        return
    # Root immunity (Briar Rose Curse of Sleeping)
    if kind == "root" and target.ability_charges.get("briar_root_immune", 0) > 0:
        battle.log_add(f"  {target.name} is immune to Root (Curse of Sleeping).")
        return
    target.add_status(kind, duration)
    battle.log_add(f"  {target.name} gains {kind} for {duration} rounds.")


def apply_stat_buff(unit, stat, amount, duration, battle, label=""):
    if unit.has_status("buff_nullify"):
        battle.log_add(f"  {unit.name}'s buffs are nullified.")
        return
    is_new = unit.add_buff(stat, amount, duration)
    if is_new:
        battle.log_add(f"  {unit.name} gains +{amount} {stat.capitalize()} for {duration} rounds.")
    # Art of the Deal: when another adventurer gains a stat buff, Rumpel gains 1 Malice.
    for team in (battle.team1, battle.team2):
        for other in team.alive():
            if other.defn.id == "rumpelstiltskin" and other != unit:
                _gain_malice(other, 1, battle, "Art of the Deal")


def apply_stat_debuff(unit, stat, amount, duration, battle):
    is_new = unit.add_debuff(stat, amount, duration)
    if is_new:
        battle.log_add(f"  {unit.name} loses -{amount} {stat.capitalize()} for {duration} rounds.")


# ─────────────────────────────────────────────────────────────────────────────
# SWAP
# ─────────────────────────────────────────────────────────────────────────────

def do_swap(unit_a: CombatantState, unit_b: CombatantState,
             team: TeamState, battle: BattleState):
    """Swap two units' slots."""
    unit_a.slot, unit_b.slot = unit_b.slot, unit_a.slot
    battle.log_add(f"{unit_a.name} and {unit_b.name} swap positions.")

    # Cunning Dodge (Reynard): refresh on swap
    if unit_a.defn.id == "reynard" or unit_b.defn.id == "reynard":
        for u in (unit_a, unit_b):
            if u.defn.id == "reynard":
                u.ability_charges["cunning_dodge"] = 1
                battle.log_add(f"  Cunning Dodge refreshed for {u.name}.")

    # Silver Aegis (Roland): 0 damage after swapping to frontline
    for u in (unit_a, unit_b):
        if u.defn.id == "sir_roland" and u.slot == SLOT_FRONT:
            u.ability_charges["silver_aegis"] = 1
            battle.log_add(f"  Silver Aegis ready for {u.name}.")

    # Track swap recency for Noble/Natural Order
    for u in (unit_a, unit_b):
        u.ability_charges["rounds_since_swap"] = 0

    # Chosen One: first ally Prince Charming swaps with becomes champion
    for u in team.alive():
        if _has_signature_effect(u, "chosen_one") and u.ability_charges.get("chosen_one_set", 0) == 0 and u in (unit_a, unit_b):
            swapped = unit_b if unit_a == u else unit_a
            if swapped in team.members:
                u.ability_charges["chosen_one_set"] = 1
                u.ability_charges["chosen_one_champion"] = swapped.defn.id
                battle.log_add(f"  Chosen One: {swapped.name} becomes {u.name}'s champion.")

    # Banner of Command (Roland signature passive): guard ally on swap
    for team_unit in team.alive():
        if _has_signature_effect(team_unit, "banner_of_command"):
            for swapped in (unit_a, unit_b):
                if swapped != team_unit and swapped in team.members:
                    swapped.add_status("guard", 2)
                    battle.log_add(
                        f"  Banner of Command: {swapped.name} is Guarded.")

    # Two Lives update
    for u in (unit_a, unit_b):
        u.untargetable = (
            u.defn.id == "ashen_ella" and u.slot != SLOT_FRONT
        )

    # Void Step basic passive
    for u in (unit_a, unit_b):
        if any(b.id == "void_step" for b in u.basics):
            if u.slot != SLOT_FRONT:
                _gain_malice(u, 1, battle, "Void Step")
            else:
                if _spend_malice(u, 2, battle, "Void Step"):
                    apply_stat_buff(u, "speed", 10, 2, battle)

    # Faustian Bargain FL: gain most recently bottled talent for 2 rounds
    for u in (unit_a, unit_b):
        if u.defn.id == "sea_wench_asha" and _has_signature_effect(u, "faustian_bargain") and u.slot == SLOT_FRONT:
            bottled = u.ability_charges.get("asha_bottled_talent")
            if bottled and _spend_malice(u, 2, battle, "Faustian Bargain"):
                u.ability_charges["stolen_talent"] = bottled
                u.ability_charges["stolen_talent_dur"] = 2
                battle.log_add(f"  Faustian Bargain: {u.name} gains bottled talent for 2 rounds.")

    # Garden of Thorns BL: root both enemies that swap (while Briar is backline)
    for check_team in (battle.team1, battle.team2):
        if check_team != team:
            for m in check_team.alive():
                if m.sig.id == "garden_of_thorns" and m.slot != SLOT_FRONT:
                    for swapped in (unit_a, unit_b):
                        if swapped in team.members:
                            swapped.add_status("root", 2)
                            battle.log_add(
                                f"  Garden of Thorns! {swapped.name} is Rooted on swap.")
                    break

    # Crumb Trail: if a unit swaps INTO the crumb slot, they pick it up (40 HP)
    team_num = 1 if team == battle.team1 else 2
    if battle.crumb_team == team_num and battle.crumb_slot is not None:
        for swapped in (unit_a, unit_b):
            if swapped in team.members and swapped.slot == battle.crumb_slot:
                do_heal(swapped, 40, swapped, battle)
                battle.log_add(f"  {swapped.name} picks up the Crumb Trail! (+40 HP)")
                battle.crumb_picked_up = team_num
                battle.crumb_team = None
                battle.crumb_slot = None
                break


# ─────────────────────────────────────────────────────────────────────────────
# KO & FRONTLINE PROMOTION
# ─────────────────────────────────────────────────────────────────────────────

def promote_if_needed(team: TeamState, battle: BattleState):
    """If frontline is KO'd, leftmost backline steps up."""
    if team.get_slot(SLOT_FRONT) is not None:
        return
    # Check back_left first, then back_right (leftmost = back_left)
    for slot in (SLOT_BACK_LEFT, SLOT_BACK_RIGHT):
        candidate = team.get_slot(slot)
        if candidate:
            candidate.slot = SLOT_FRONT
            candidate.untargetable = False
            # Cunning Dodge refresh
            if candidate.defn.id == "reynard":
                candidate.ability_charges["cunning_dodge"] = 1
            # Silver Aegis on forced frontline promotion
            if candidate.defn.id == "sir_roland":
                candidate.ability_charges["silver_aegis"] = 1
            battle.log_add(f"{candidate.name} moves to frontline.")

            # Postmortem Passage: KO'd frontline retaliates
            # (handled in deal_damage → post-resolution check)
            return


def check_and_promote(battle: BattleState):
    promote_if_needed(battle.team1, battle)
    promote_if_needed(battle.team2, battle)


def check_winner(battle: BattleState) -> bool:
    prev = battle.winner
    if battle.team2.all_ko():
        battle.winner = 1
    elif battle.team1.all_ko():
        battle.winner = 2
    if battle.winner is not None and prev is None:
        battle_log.section(f"BATTLE OVER — P{battle.winner} WINS (Round {battle.round_num})")
        battle.log_add(f"Player {battle.winner} wins!")
    return battle.winner is not None


# ─────────────────────────────────────────────────────────────────────────────
# EXECUTE ONE ABILITY (generic + special handlers)
# ─────────────────────────────────────────────────────────────────────────────

def execute_ability(
    actor: CombatantState,
    ability: Ability,
    target: CombatantState,
    acting_player: int,
    battle: BattleState,
    is_spread: bool = False,
    ignore_pride: bool = False,
    action_context: dict | None = None,
):
    """Execute one ability use of actor against target."""
    mode = get_mode(actor, ability)
    team  = battle.get_team(acting_player)
    enemy = battle.get_enemy(acting_player)

    # Natural Order BL: abilities against units that have not swapped for 2+ rounds
    # do not increment ranged recharge.
    if _has_signature_effect(actor, "natural_order") and actor.slot != SLOT_FRONT and target is not None:
        if target.ability_charges.get("rounds_since_swap", 0) >= 2:
            actor.ability_charges["natural_order_skip_recharge"] = 1

    # Mesmerizing (Prince Charming talent): enemies that target his allies get -10 Atk for 2 rounds.
    prince = next((u for u in enemy.alive() if u.defn.id == "prince_charming" and u.slot == SLOT_FRONT), None)
    if prince and target is not None and target in enemy.members and target != prince:
        apply_stat_debuff(actor, "attack", 10, 2, battle)

    # Flowing Locks consumption: using melee backline access spends the one-time charge
    if actor.defn.id == "rapunzel" and target is not None and actor.slot == SLOT_FRONT and target.slot != SLOT_FRONT:
        if actor.ability_charges.get("severed_tether_active", 0) <= 0 and actor.ability_charges.get("flowing_locks_ready", 0) > 0:
            actor.ability_charges["flowing_locks_ready"] = 0

    # ── Damage ────────────────────────────────────────────────────────────────
    if mode.power > 0:
        dmg = compute_damage(actor, target, ability, mode, acting_player, battle,
                             is_spread=is_spread, ignore_pride=ignore_pride)
        battle.log_add(f"  {target.name} takes {dmg} damage.")
        deal_damage(actor, target, dmg, ability, mode, acting_player, battle)

    # ── Purifying Flame: on next attack, Burn the target ─────────────────────
    if mode.power > 0 and not target.ko \
            and actor.ability_charges.get("purifying_flame", 0) > 0:
        apply_status_effect(target, "burn", 2, battle)
        actor.ability_charges["purifying_flame"] = 0

    # ── Hot Mitts: FL burns target if not already burned; BL always burns ────
    if mode.power > 0 and actor.sig.id == "hot_mitts" and not target.ko:
        if actor.slot == SLOT_FRONT:
            if not target.has_status("burn"):    # "or" condition: burn OR +10% (FL)
                apply_status_effect(target, "burn", 2, battle)
        else:
            apply_status_effect(target, "burn", 2, battle)  # BL always burns

    # ── Heal to target ────────────────────────────────────────────────────────
    if mode.heal > 0 and not is_spread:
        do_heal(target, mode.heal, actor, battle,
                action_desc=f"{actor.name} heals {target.name}")

    # ── Heal self ─────────────────────────────────────────────────────────────
    if mode.heal_self > 0:
        do_heal(actor, mode.heal_self, actor, battle,
                action_desc=f"{actor.name} heals self")

    # ── Heal lowest HP ally ───────────────────────────────────────────────────
    if mode.heal_lowest > 0:
        lowest = min(team.alive(), key=lambda u: u.hp, default=None)
        if lowest:
            do_heal(lowest, mode.heal_lowest, actor, battle,
                    action_desc=f"{actor.name} heals {lowest.name}")

    # ── Status on target ──────────────────────────────────────────────────────
    if mode.status:
        apply_status_effect(target, mode.status, mode.status_dur, battle)
    if mode.status2:
        apply_status_effect(target, mode.status2, mode.status2_dur, battle)
    if mode.status3:
        apply_status_effect(target, mode.status3, mode.status3_dur, battle)

    # ── Status on self ────────────────────────────────────────────────────────
    if mode.self_status:
        apply_status_effect(actor, mode.self_status, mode.self_status_dur, battle)

    # ── Guard effects ─────────────────────────────────────────────────────────
    if mode.guard_self:
        actor.add_status("guard", 2)
        battle.log_add(f"  {actor.name} is Guarded for 2 rounds.")
    if mode.guard_target and not is_spread:
        target.add_status("guard", 2)
        battle.log_add(f"  {target.name} is Guarded for 2 rounds.")
    if mode.guard_all_allies:
        for ally in team.alive():
            ally.add_status("guard", 2)
        battle.log_add(f"  All allies are Guarded for 2 rounds.")
    if mode.guard_frontline_ally:
        front = team.frontline()
        if front and front != actor:
            front.add_status("guard", 2)
            battle.log_add(f"  {front.name} is Guarded for 2 rounds.")

    # ── Stat buffs on self ────────────────────────────────────────────────────
    if mode.atk_buff:
        # Bless buffs only the guarded ally (not the caster).
        if ability.id == "bless" and not is_spread:
            apply_stat_buff(target, "attack", mode.atk_buff, mode.atk_buff_dur,
                            battle)
        else:
            apply_stat_buff(actor, "attack", mode.atk_buff, mode.atk_buff_dur, battle)
    if mode.spd_buff:
        apply_stat_buff(actor, "speed", mode.spd_buff, mode.spd_buff_dur, battle)
    if mode.def_buff:
        apply_stat_buff(actor, "defense", mode.def_buff, mode.def_buff_dur, battle)

    # ── Stat debuffs on target ────────────────────────────────────────────────
    if mode.atk_debuff:
        apply_stat_debuff(target, "attack", mode.atk_debuff, mode.atk_debuff_dur,
                          battle)
    if mode.spd_debuff:
        apply_stat_debuff(target, "speed", mode.spd_debuff, mode.spd_debuff_dur,
                          battle)
    if mode.def_debuff:
        apply_stat_debuff(target, "defense", mode.def_debuff, mode.def_debuff_dur,
                          battle)

    # Faustian Bargain BL: bottle KO target talent and gain speed
    if actor.defn.id == "sea_wench_asha" and _has_signature_effect(actor, "faustian_bargain") and actor.slot != SLOT_FRONT and target.ko:
        actor.ability_charges["asha_bottled_talent"] = target.defn.id
        apply_stat_buff(actor, "speed", 10, 2, battle)
        battle.log_add(f"  Faustian Bargain: {actor.name} bottles {target.name}'s talent.")

    # ── Special effects (bespoke ability logic) ───────────────────────────────
    if mode.special:
        apply_special(actor, ability, mode, target, acting_player, battle,
                      ignore_pride=ignore_pride, action_context=action_context)

    # ── Mark twist used ───────────────────────────────────────────────────────
    if ability.category == "twist":
        actor.twist_used = True


def execute_spread_ability(
    actor: CombatantState,
    ability: Ability,
    acting_player: int,
    battle: BattleState,
    ignore_pride: bool = False,
):
    """Execute a spread ability against all legal targets."""
    targets = get_legal_targets(battle, acting_player, actor, ability)
    if not targets:
        battle.log_add(f"{actor.name} uses {ability.name} — no targets.")
        return
    battle.log_add(f"{actor.name} uses {ability.name} (spread).")
    for t in targets:
        if not t.ko:
            execute_ability(actor, ability, t, acting_player, battle,
                            is_spread=True, ignore_pride=ignore_pride)
            check_and_promote(battle)
            if check_winner(battle):
                return


def get_subterfuge_swap_targets(
    battle: BattleState,
    acting_player: int,
    target: CombatantState,
) -> list[CombatantState]:
    """Return enemy candidates that can be swapped with Subterfuge's main target."""
    if target is None:
        return []
    enemy = battle.get_enemy(acting_player)
    return [u for u in enemy.alive() if u != target]


# ─────────────────────────────────────────────────────────────────────────────
# SPECIAL ABILITY HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

def apply_special(
    actor, ability, mode, target,
    acting_player, battle,
    ignore_pride=False,
    action_context: dict | None = None,
):
    key = mode.special
    team  = battle.get_team(acting_player)
    enemy = battle.get_enemy(acting_player)

    # ── Subterfuge: swap target and enemy ─────────────────────────────────────
    if key == "subterfuge_swap":
        swap_target = None
        if action_context:
            swap_target = action_context.get("swap_target")
        if swap_target in enemy.alive() and swap_target != target:
            do_swap(target, swap_target, enemy, battle)

    # ── Blood Hunt backline: HP averaging ─────────────────────────────────────
    elif key == "blood_hunt_hp_avg":
        avg = (actor.hp + target.hp) // 2
        actor.hp = min(actor.max_hp, avg)
        target.hp = min(target.max_hp, avg)
        battle.log_add(f"  Blood Hunt: {actor.name} and {target.name} HP set to {avg}.")

    # ── Final Deception: expose all + steal 5 atk each ───────────────────────
    elif key == "final_deception":
        for e in enemy.alive():
            apply_status_effect(e, "expose", 2, battle)
            e.add_debuff("attack", 5, 2)
            actor.add_buff("attack", 5, 2)
        battle.log_add(f"  {actor.name} steals Attack from all enemies.")

    # ── Not By The Hair: damage reduction ────────────────────────────────────
    elif key == "nbth_self_reduce":
        actor.dmg_reduction = 0.60
        battle.log_add(f"  {actor.name} takes 60% less damage this round.")

    elif key == "nbth_ally_reduce":
        front = team.frontline()
        if front and front != actor:
            front.dmg_reduction = 0.35
            battle.log_add(f"  {front.name} takes 35% less damage this round.")

    # ── Unbreakable Defense: clear statuses + double defense ─────────────────
    elif key == "unbreakable_defense":
        actor.clear_statuses()
        cur_def = actor.get_stat("defense")
        actor.add_buff("defense", cur_def, 2)  # +current = double
        battle.log_add(
            f"  {actor.name} clears statuses and doubles Defense for 2 rounds.")

    # ── Shimmering Valor frontline: damage reduction for 3 rounds ─────────────
    elif key == "shimmering_valor_front":
        actor.valor_rounds = 3
        actor.dmg_reduction = 0.40
        battle.log_add(
            f"  {actor.name} has 40% damage reduction for 3 rounds (Shimmering Valor).")

    # ── Shimmering Valor backline: heal based on valor rounds ─────────────────
    elif key == "shimmering_valor_back":
        heal_amt = 55 + 15 * actor.valor_rounds
        do_heal(actor, heal_amt, actor, battle)
        actor.valor_rounds = 0

    # ── Taunt (Knight's Challenge): mark target to only attack Roland ─────────
    elif key in ("taunt_target", "taunt_front_ranged"):
        if key == "taunt_target":
            target.add_status("taunt", 2)
            battle.log_add(f"  {target.name} is Taunted for 2 rounds.")
        else:
            # Taunt front-most ranged enemy; fall back to any ranged enemy
            taunted = False
            for e in enemy.alive():
                if e.slot == SLOT_FRONT and is_ranged(e):
                    e.add_status("taunt", 2)
                    battle.log_add(f"  {e.name} is Taunted for 2 rounds.")
                    taunted = True
                    break
            if not taunted:
                for e in enemy.alive():
                    if is_ranged(e):
                        e.add_status("taunt", 2)
                        battle.log_add(f"  {e.name} is Taunted for 2 rounds.")
                        break

    # ── Journey to Avalon: self KO + revive chosen ally ───────────────────────
    elif key == "journey_to_avalon":
        # Self KO
        actor.hp = 0
        actor.ko = True
        battle.log_add(f"  {actor.name} sacrifices herself (Journey to Avalon).")
        # Revive/buff target ally with Reflecting Pool
        if target and target in team.members and target != actor:
            was_ko = target.ko
            if was_ko:
                target.ko = False
                target.hp = target.max_hp // 2
                battle.log_add(f"  {target.name} revived at {target.hp} HP.")
            target.add_status("reflecting_pool", 2)
            battle.log_add(f"  {target.name} gains Reflecting Pool for 2 rounds.")
        check_and_promote(battle)

    # ── Cinder Blessing frontline: HP averaging with ally ────────────────────
    elif key == "cinder_blessing_avg":
        old_actor_hp = actor.hp
        old_target_hp = target.hp
        avg = (actor.hp + target.hp) // 2
        actor.hp = min(actor.max_hp, avg)
        target.hp = min(target.max_hp, avg)
        battle.log_add(
            f"  Cinder Blessing: {actor.name} and {target.name} HP set to {avg}.")
        # Purifying Flame talent: only applies to units that actually gained HP
        if actor.defn.id == "matchstick_liesl":
            healed_units = []
            if actor.hp > old_actor_hp:
                healed_units.append(actor)
            if target.hp > old_target_hp:
                healed_units.append(target)
            for healed in healed_units:
                healed.add_status("burn_immune", 2)
                healed.ability_charges["purifying_flame"] = 1
            if healed_units:
                names = " and ".join(h.name for h in healed_units)
                battle.log_add(f"  Purifying Flame: {names} will Burn their next target.")

    # ── Toxin Purge: remove statuses ─────────────────────────────────────────
    elif key == "toxin_purge_all":
        removed = [s.kind for s in target.statuses if is_rulebook_status_condition(s.kind)]
        target.statuses = [s for s in target.statuses if not is_rulebook_status_condition(s.kind)]
        for kind in removed:
            _trigger_innocent_heart(target, kind, battle)
        battle.log_add(f"  {target.name} is cleansed of rulebook status conditions.")

    elif key == "toxin_purge_last":
        if target.last_status_inflicted and is_rulebook_status_condition(target.last_status_inflicted) and target.has_status(
                target.last_status_inflicted):
            kind = target.last_status_inflicted
            target.remove_status(kind)
            _trigger_innocent_heart(target, kind, battle)
            battle.log_add(f"  {target.name} loses {kind}.")

    # ── Arcane Wave: self atk/def debuff ─────────────────────────────────────
    elif key == "arcane_wave_self_debuff":
        actor.add_debuff("attack",  10, 2)
        actor.add_debuff("defense", 10, 2)
        battle.log_add(f"  {actor.name} has -10 Atk and -10 Def for 2 rounds.")

    # ── Slam: bonus if guarded, or backline guard self ────────────────────────
    elif key == "slam_bonus_if_guarded":
        pass  # handled in compute_damage

    elif key == "slam_back_guard":
        actor.add_status("guard", 2)
        battle.log_add(f"  {actor.name} is Guarded for 2 rounds.")

    # ── Magic Growth backline: flag Jack's next ability +15 power ────────────
    elif key == "magic_growth_power_buff":
        actor.ability_charges["magic_growth_bonus"] = 1
        battle.log_add(f"  {actor.name}'s next ability has +15 Power.")

    # ── Rabbit Hole frontline: extra action next round ────────────────────────
    elif key == "rabbit_hole_extra_action":
        actor.extra_actions_next = 1
        battle.log_add(f"  {actor.name} will have an extra action next round.")

    # ── Rabbit Hole backline: swap with ally ──────────────────────────────────
    elif key == "rabbit_hole_swap":
        if target != actor and target in team.alive():
            do_swap(actor, target, team, battle)

    # ── Stitch In Time: extra action this round ───────────────────────────────
    elif key == "stitch_extra_action_now":
        actor.extra_actions_now += 1
        battle.log_add(f"  {actor.name} has an extra action this round!")

    # ── Cutpurse backline: swap Reynard with frontline ally ──────────────────
    elif key == "cutpurse_swap_frontline":
        front = team.frontline()
        if front and front != actor:
            do_swap(actor, front, team, battle)

    # ── Feign Weakness: set retaliation power ────────────────────────────────
    elif key == "feign_weakness_retaliate_55":
        actor.retaliate_power = 55
        battle.log_add(f"  {actor.name} will retaliate with 55 power next round.")

    elif key == "feign_weakness_retaliate_45":
        actor.retaliate_power = 45
        battle.log_add(f"  {actor.name} will retaliate with 45 power next round.")

    # ── Last Laugh: retaliate + steal speed ──────────────────────────────────
    elif key == "last_laugh":
        actor.retaliate_power = 65
        actor.retaliate_speed_steal = 10
        battle.log_add(
            f"  {actor.name} will retaliate (65 power) and steal Speed next round.")

    # ── Cauldron Bubble: extend status durations ──────────────────────────────
    elif key == "cauldron_extend_status":
        for s in target.statuses:
            if s.duration > 0 and is_rulebook_status_condition(s.kind):
                s.duration += 1
        battle.log_add(f"  Rulebook status durations extended on {target.name}.")

    # ── Vile Sabbath: reapply last status ─────────────────────────────────────
    elif key == "vile_sabbath_reapply":
        if target.last_status_inflicted and is_rulebook_status_condition(target.last_status_inflicted):
            apply_status_effect(target, target.last_status_inflicted, 2, battle)

    # ── Bring Down: steal atk if target is backline ───────────────────────────
    elif key == "bring_down_steal_atk":
        if target.slot in (SLOT_BACK_LEFT, SLOT_BACK_RIGHT):
            target.add_debuff("attack", 10, 2)
            actor.add_buff("attack", 10, 2)
            battle.log_add(
                f"  {actor.name} steals 10 Atk from {target.name} for 2 rounds.")

    # ── Riposte: 50% damage reduction this round (both FL and BL) ────────────
    elif key == "riposte_damage_reduction":
        actor.dmg_reduction = 0.50
        battle.log_add(f"  {actor.name} takes 50% less damage this round (Riposte).")

    # ── Hero's Charge: ignore Heedless Pride debuff ───────────────────────────
    elif key == "heros_charge_ignore_pride_front":
        pass  # handled via ignore_pride flag in execute_turn

    # ── Slay the Beast: ignore pride ─────────────────────────────────────────
    elif key == "slay_ignore_pride":
        pass  # caller must set ignore_pride=True

    # ── Hunter's Mark: apply bonus_damage status (tracked in compute_damage) ──
    elif key == "hunters_mark_dot":
        target.add_status("bonus_damage", 2)
        battle.log_add(f"  {target.name} is Marked — takes +10 damage next round.")

    # ── Trapping Blow FL: root target if they are Weakened ───────────────────
    elif key == "trapping_blow_root_weakened":
        if target.has_status("weaken"):
            target.add_status("root", 2)
            battle.log_add(f"  {target.name} is Rooted by Trapping Blow (was Weakened)!")

    # ── Dying Dance FL: Shock Weakened targets for 2 rounds ─────────────────
    elif key == "dying_dance_front":
        if target.has_status("weaken"):
            target.add_status("shock", 2)
            battle.log_add(f"  {target.name} is Shocked by Dying Dance (was Weakened)!")

    # ── Drown in the Loch: flat +10 incoming damage ───────────────────────────
    elif key == "drown_dmg_bonus":
        target.add_status("bonus_damage", 2)
        battle.log_add(f"  {target.name} takes +10 damage from all sources for 2 rounds.")

    # ── Struck Midnight: Ella can't act/target next round ─────────────────────
    elif key == "struck_midnight_untargetable":
        actor.untargetable = True
        actor.cant_act = True
        # These clear at end of next round; set a counter
        actor.ability_charges["struck_midnight"] = 2
        battle.log_add(f"  {actor.name} retreats — untargetable until end of next round.")

    # ── Cleansing Inferno: 60% vamp vs Burned ────────────────────────────────
    elif key == "cleansing_inferno_burn_boost":
        if target.has_status("burn"):
            # Retroactively adjust vamp (already applied in deal_damage)
            # Add extra 30% vamp manually here
            if mode.power > 0:
                bonus_vamp = math.ceil(
                    compute_damage(actor, target, ability, mode, acting_player,
                                   battle, is_spread=True) * 0.30
                )
                actor.hp = min(actor.max_hp, actor.hp + bonus_vamp)
                battle.log_add(f"  Extra vamp vs Burned: {actor.name} heals {bonus_vamp}.")

    # ── Falling Kingdom ───────────────────────────────────────────────────────
    elif key == "falling_kingdom":
        for e in enemy.alive():
            if e.has_status("root"):
                e.add_status("root", 99)      # refresh
                e.add_status("weaken", 2)
                battle.log_add(f"  {e.name}'s Root refreshed + Weakened.")
            else:
                apply_status_effect(e, "root", 2, battle)

    # ── Deathlike Slumber ──────────────────────────────────────────────────────
    elif key == "deathlike_slumber":
        actor.clear_statuses()
        battle.log_add(f"  {actor.name} cures all statuses.")
        # Innocent Heart effect doubled for 2 rounds
        actor.ability_charges["deathlike_doubled"] = 2
        battle.log_add(f"  Innocent Heart's effect is doubled for 2 rounds.")
        # Target becomes dormant for 2 rounds
        if target and target != actor:
            target.add_status("dormant", 2)
            target.cant_act = True
            battle.log_add(
                f"  {target.name} is dormant for 2 rounds (Deathlike Slumber).")

    # ── Lake's Gift: grant Reflecting Pool effect to ally ─────────────────────
    elif key == "lakes_gift_pool_front":
        target.add_status("reflecting_pool", 2)
        battle.log_add(f"  {target.name} gains Reflecting Pool for 2 rounds.")
        target.add_buff("attack", 10, 2)
        battle.log_add(f"  {target.name} gains +10 Attack for 2 rounds.")

    elif key == "lakes_gift_pool_back":
        target.add_status("reflecting_pool", 2)
        battle.log_add(f"  {target.name} gains Reflecting Pool for 2 rounds.")

    # ── Redemption ────────────────────────────────────────────────────────────
    elif key == "redemption":
        actor.max_hp_bonus += 100
        actor.hp = min(actor.hp + 100, actor.max_hp)
        actor.ability_charges["redemption_heal"] = 2
        battle.log_add(
            f"  {actor.name} gains +100 max HP and will heal 50 HP at end of round for 2 rounds.")

    # ── Hot Mitts: FL burn handled in execute_ability; BL bonus in compute_damage ─
    elif key in ("hot_mitts_front", "hot_mitts_back"):
        pass  # handled elsewhere

    # ── Stalwart: flat -10 incoming damage handled in compute_damage ──────────
    elif key in ("stalwart_front", "stalwart_back"):
        pass  # handled in compute_damage

    # ── Belligerence: BL attack reduction handled in compute_damage ───────────
    elif key == "belligerence_ignore_atk":
        pass  # handled in compute_damage

    # ── Spread Fortune: handled in compute_damage ─────────────────────────────
    elif key in ("spread_fortune_front", "spread_fortune_back"):
        pass  # handled in compute_damage

    # ── Banner of Command: handled in do_swap ─────────────────────────────────
    elif key == "banner_of_command":
        pass  # handled in do_swap

    # ── Benefactor: heal bonus handled in do_heal ─────────────────────────────
    elif key in ("benefactor_front", "benefactor_back"):
        pass  # handled in do_heal

    # ── Sanctuary: end-of-round heal handled in end_round ─────────────────────
    elif key in ("sanctuary_front", "sanctuary_back"):
        pass  # handled in end_round

    # ── Crawling Abode: speed bonus handled in apply_passive_stats ────────────
    elif key == "crawling_abode":
        pass  # handled in apply_passive_stats

    # ── Birdsong: end-of-round cleanse handled in end_round ───────────────────
    elif key in ("birdsong_front", "birdsong_back"):
        pass  # handled in end_round

    # ── Flame of Renewal: on-KO healing handled in deal_damage ────────────────
    elif key == "flame_of_renewal":
        pass  # handled in deal_damage

    # ── Postmortem Passage: posthumous attack handled in deal_damage ──────────
    elif key == "postmortem_passage":
        pass  # handled in deal_damage

    # ── Wolf's Pursuit: retarget handled in resolve_queued_action ─────────────
    elif key == "wolfs_pursuit_retarget":
        pass  # retarget logic in resolve_queued_action

    # ── Crumb Trail BL: drop crumb at current slot ────────────────────────────
    elif key == "crumb_trail_drop":
        battle.crumb_team = acting_player
        battle.crumb_slot = actor.slot
        battle.log_add(f"  {actor.name} drops a Crumb Trail at {actor.slot}.")

    # ── Crumb Trail FL: power bonus handled in compute_damage ─────────────────
    elif key == "crumb_trail_front":
        pass  # +20 power if ally picked up crumb this turn is in compute_damage

    # ── Shove Over BL: mark target for +15 power on next incoming attack ─────
    elif key == "shove_over_next_atk_bonus":
        target.ability_charges["shove_over_next_bonus"] = 1
        battle.log_add(f"  {target.name} is set up for +15 incoming power.")

    # ── Midnight Dour FL: reactive swap handled in deal_damage ────────────────
    elif key == "midnight_dour_swap":
        pass  # passive — reactive trigger is in deal_damage

    # ── Toil and Trouble FL: spread target's last inflicted status right ──────
    elif key == "toil_spread_status_right":
        adj = get_adjacent_right(enemy, target)
        if adj and not adj.ko and target.last_status_inflicted and is_rulebook_status_condition(target.last_status_inflicted):
            status = target.last_status_inflicted
            apply_status_effect(adj, status, 2, battle)
            battle.log_add(f"  Toil and Trouble! {adj.name} gains {status}.")

    # ── Hypnotic Aura: targeting restriction handled in get_legal_targets ─────
    elif key in ("hypnotic_aura_front", "hypnotic_aura_back"):
        pass  # handled in get_legal_targets / resolve_queued_action

    # ── Devil's Due: make one ability spread this round ───────────────────────
    elif key == "devils_due":
        # Pick the highest-power non-passive ability from actor's kit
        candidates = [a for a in (actor.basics + [actor.sig])
                      if not a.passive and get_mode(actor, a).power > 0]
        if candidates:
            best = max(candidates, key=lambda a: get_mode(actor, a).power)
            actor.ability_charges["devils_due_spread"] = best.id
            battle.log_add(
                f"  Devil's Due! {best.name} is now Spread this round.")

    # ── Noble basics / signatures ───────────────────────────────────────────
    elif key == "summons_swap":
        if target and target != actor:
            do_swap(actor, target, team, battle)
            actor.ability_charges["summons_cd"] = 2

    elif key == "condescend_back":
        target.ability_charges["condescend_bonus"] = 1

    elif key == "heros_bargain_back":
        efl = enemy.frontline()
        if efl and target and target in enemy.alive():
            do_swap(target, efl, enemy, battle)

    elif key == "golden_snare_front":
        if target.has_status("root"):
            target.add_status("root", 2)
        else:
            apply_status_effect(target, "root", 2, battle)

    elif key == "severed_tether":
        actor.ability_charges["severed_tether_active"] = 2
        apply_stat_buff(actor, "attack", 20, 2, battle)
        apply_stat_buff(actor, "speed", 20, 2, battle)
        apply_stat_debuff(actor, "defense", 15, 2, battle)

    elif key == "happily_ever_after":
        team_all = battle.get_team(acting_player).members
        for ally in team_all:
            if ally.ko and ally != actor:
                best = max((ally.defn.attack, "attack"), (ally.defn.defense, "defense"), (ally.defn.speed, "speed"))[1]
                apply_stat_buff(actor, best, 15, 2, battle)

    elif key == "fated_duel":
        enemy_front = enemy.frontline()
        if enemy_front:
            battle.fated_duel_rounds = 2
            battle.fated_duel_units = (actor, enemy_front)
            battle.log_add(f"  Fated Duel begins: only {actor.name} and {enemy_front.name} may act for 2 rounds.")

    elif key in ("command_front", "command_back", "chosen_one", "natural_order_front", "natural_order_back", "awaited_blow_front", "awaited_blow_back", "gallant_charge_front", "lower_guard_front", "ivory_tower_front", "ivory_tower_back"):
        pass

    # ── Dragon Head signatures ────────────────────────────────────────────────

    elif key == "sovereign_edict_front":
        # FL: if target has 2+ active statuses, this attack ignores Guard and defense buffs.
        active_statuses = [s for s in target.statuses if s.duration > 0]
        if len(active_statuses) >= 2:
            # Already dealt damage; log the bypass.  The power/def ignoring is handled at
            # compute_damage time via mode.def_ignore_pct=100 / mode.ignore_guard; but since
            # we can't mutate mode dynamically before damage, we note it here.  The damage
            # bonus from Tyranny is applied separately in compute_damage.
            battle.log_add(
                f"  Sovereign Edict! {target.name} has {len(active_statuses)} statuses — "
                "Guard and defense buffs ignored."
            )

    elif key == "sovereign_edict_back":
        # BL: Spotlight target for 2 rounds (damage already applied via mode.power/status).
        pass  # status applied via mode.status = "spotlight" in the AbilityMode

    elif key == "cataclysm_front":
        # FL: power bonus per status is handled in compute_damage (cataclysm FL +10/status).
        pass

    elif key == "cataclysm_back":
        # BL spread: after dealing damage, refresh all status durations on target.
        if target and not target.ko:
            for s in target.statuses:
                if s.duration > 0:
                    s.duration = max(s.duration, 2)
            battle.log_add(f"  Cataclysm BL: {target.name}'s statuses refreshed.")

    elif key == "dark_aura_passive":
        pass  # handled in end_round

    # ── Warlock basics / signatures ──────────────────────────────────────────
    elif key == "warlock_gain_malice_1":
        _gain_malice(actor, 1, battle, ability.name)

    elif key == "warlock_spend1_weaken":
        if _spend_malice(actor, 1, battle, ability.name):
            apply_status_effect(target, "weaken", 2, battle)

    elif key == "warlock_spend1_expose":
        if _spend_malice(actor, 1, battle, ability.name):
            apply_status_effect(target, "expose", 2, battle)

    elif key == "blood_pact_front":
        actor.hp = max(1, actor.hp - 50)
        battle.log_add(f"  {actor.name} loses 50 HP.")
        _gain_malice(actor, 2, battle, "Blood Pact")

    elif key == "blood_pact_back":
        if _spend_malice(actor, 1, battle, "Blood Pact"):
            do_heal(actor, 25, actor, battle)

    elif key == "cut_strings_back":
        if _spend_malice(actor, 2, battle, "Cut the Strings"):
            apply_status_effect(target, "spotlight", 2, battle)

    elif key == "blue_faerie_boon":
        actor.ability_charges["malice_cap"] = 12
        _gain_malice(actor, 6, battle, ability.name)
        do_heal(actor, actor.ability_charges.get("malice", 0) * 20, actor, battle)

    elif key == "straw_to_gold_front":
        ally = target
        if ally and ally != actor:
            # Steal ally's highest current buff instance, then return it later.
            best = None
            for b in ally.buffs:
                if b.duration <= 0:
                    continue
                if best is None or b.amount > best.amount:
                    best = b
            if best:
                ally.buffs = [b for b in ally.buffs if b is not best]
                bonus = actor.ability_charges.get("malice", 0) * 5
                apply_stat_buff(actor, best.stat, best.amount + bonus, 2, battle)
                actor.ability_charges["straw_return_stat"] = best.stat
                actor.ability_charges["straw_return_amount"] = best.amount
                actor.ability_charges["straw_return_dur"] = 2
                actor.ability_charges["straw_return_orig_dur"] = best.duration
                actor.ability_charges["straw_return_target"] = ally
                battle.log_add(
                    f"  Straw to Gold: stole {best.stat}+{best.amount} from {ally.name}."
                )

    elif key == "straw_to_gold_back":
        ally = target
        if ally and ally != actor:
            best = None
            for st in ("attack", "defense", "speed"):
                val = ally.best_debuff(st)
                if val > 0 and (best is None or val > best[1]):
                    best = (st, val)
            if best:
                stat, val = best
                ally.debuffs = [d for d in ally.debuffs if d.stat != stat or d.amount != val]
                apply_stat_buff(ally, stat, val, 2, battle)

    elif key == "name_the_price_front":
        apply_stat_buff(target, "attack", 10, 2, battle)

    elif key == "name_the_price_back":
        if _spend_malice(actor, 2, battle, ability.name):
            target.buffs = []
            target.add_status("buff_nullify", 2)
            battle.log_add(f"  {target.name}'s stat buffs are nullified for 2 rounds.")

    elif key == "thieve_the_first_born":
        bonus = actor.ability_charges.get("malice", 0) * 5
        for e in enemy.alive():
            for b in e.buffs:
                if b.duration > 0:
                    apply_stat_buff(actor, b.stat, b.amount + bonus, b.duration, battle)
            e.buffs = []

    elif key == "misappropriate_front":
        if _spend_malice(actor, 2, battle, ability.name):
            efl = enemy.frontline()
            if efl:
                sig = efl.sig
                if sig.passive:
                    actor.ability_charges["stolen_signature"] = sig.id
                    actor.ability_charges["stolen_signature_dur"] = 2
                    battle.log_add(f"  {actor.name} gains {sig.name} for 2 rounds.")
                else:
                    legal = get_legal_targets(battle, acting_player, actor, sig)
                    if get_mode(actor, sig).spread:
                        execute_spread_ability(actor, sig, acting_player, battle)
                    elif legal:
                        preferred = enemy.frontline()
                        tgt = preferred if preferred in legal else legal[0]
                        execute_ability(actor, sig, tgt, acting_player, battle)

    elif key == "abyssal_call_front":
        if _spend_malice(actor, 2, battle, ability.name):
            apply_stat_debuff(target, "defense", 10, 2, battle)

    elif key == "abyssal_call_back":
        for d in target.debuffs:
            if d.duration > 0:
                d.duration = max(d.duration, 2)
        battle.log_add(f"  {target.name}'s stat debuffs are refreshed.")

    elif key == "turn_to_foam":
        _gain_malice(actor, 3, battle, ability.name)
        mal = actor.ability_charges.get("malice", 0)
        if mal > 0:
            actor.ability_charges["malice"] = 0
            for e in enemy.alive():
                e.add_debuff("defense", mal * 10, 2)
            battle.log_add(f"  Turn to Foam: all enemies get -{mal*10} Defense for 2 rounds.")

    elif key == "rend_back":
        # Rend BL: mark target — actor's next ability against it gains +10 Power
        actor.ability_charges[f"rend_bonus_{target.defn.id}"] = 10
        battle.log_add(f"  {actor.name} marks {target.name} — next ability gains +10 Power.")

    elif key == "cleave_back":
        # Cleave BL: mark target — actor's next ability against it ignores 10% Defense
        actor.ability_charges[f"cleave_bonus_{target.defn.id}"] = 10
        battle.log_add(f"  {actor.name} marks {target.name} — next ability ignores 10% Defense.")


def _trigger_innocent_heart(unit: CombatantState, kind: str,
                              battle: BattleState):
    """Fire when Aurora or an ally on Aurora's team loses a status condition."""
    # Find which team unit belongs to, then check if Aurora is on that same team
    unit_team = None
    for t in (battle.team1, battle.team2):
        if unit in t.members:
            unit_team = t
            break
    if unit_team is None:
        return
    aurora = next(
        (m for m in unit_team.alive() if m.defn.id == "snowkissed_aurora"),
        None
    )
    if aurora:
        doubled = aurora.ability_charges.get("deathlike_doubled", 0) > 0
        def_bonus  = 20 if doubled else 10
        heal_bonus = 40 if doubled else 20
        unit.add_buff("defense", def_bonus, 2)
        aurora.hp = min(aurora.max_hp, aurora.hp + heal_bonus)
        battle.log_add(
            f"  Innocent Heart: {unit.name} +{def_bonus} Def; {aurora.name} heals {heal_bonus}.")

        # Birdsong BL: Aurora gains +5 attack when Innocent Heart fires (stacks ≤3)
        # Tracked via ability_charges["birdsong_stacks"]; applied as 1-round buff
        # in apply_passive_stats each round start; duration resets on each trigger.
        if aurora.sig.id == "birdsong" and aurora.slot != SLOT_FRONT:
            stacks = aurora.ability_charges.get("birdsong_stacks", 0)
            if stacks < 3:
                stacks += 1
                aurora.ability_charges["birdsong_stacks"] = stacks
            # Reset duration to 2 rounds on every trigger
            aurora.ability_charges["birdsong_dur"] = 2
            battle.log_add(
                f"  Birdsong BL: {aurora.name} +5 Atk stack ({stacks}/3).")


# ─────────────────────────────────────────────────────────────────────────────
# ITEM ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def execute_item(
    actor: CombatantState,
    target: CombatantState,
    acting_player: int,
    battle: BattleState,
):
    item = actor.item
    team = battle.get_team(acting_player)
    enemy = battle.get_enemy(acting_player)

    if item.once_per_battle and actor.item_uses_left <= 0:
        battle.log_add(f"  {actor.name}'s {item.name} already used.")
        return
    if actor.item_uses_left <= 0:
        battle.log_add(f"  {actor.name}'s {item.name} is exhausted.")
        return

    actor.item_uses_left -= 1
    battle.log_add(f"{actor.name} uses {item.name}.")

    if item.heal > 0:
        do_heal(target, item.heal, actor, battle,
                action_desc=f"{actor.name} heals {target.name}")

    if item.guard:
        target.add_status("guard", item.status_dur)
        battle.log_add(f"  {target.name} is Guarded.")

    if item.atk_buff:
        apply_stat_buff(actor, "attack", item.atk_buff, item.atk_buff_dur, battle)

    if item.spd_buff:
        apply_stat_buff(actor, "speed", item.spd_buff, item.spd_buff_dur, battle)

    if item.def_buff:
        apply_stat_buff(actor, "defense", item.def_buff, item.def_buff_dur, battle)

    if item.status and not item.guard:
        apply_status_effect(target, item.status, item.status_dur, battle)

    if item.special == "smoke_bomb_swap":
        # Swap actor with a chosen ally (target must be an ally)
        if target != actor and target in team.alive():
            do_swap(actor, target, team, battle)
        battle.log_add(f"  Smoke Bomb: swaps with {target.name}.")

    if item.special == "ancient_hourglass":
        actor.untargetable = True
        actor.cant_act     = True
        actor.ability_charges["hourglass"] = 1
        battle.log_add(f"  Ancient Hourglass — untargetable next round.")


# ─────────────────────────────────────────────────────────────────────────────
# TURN RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

def _track_ranged_use_once(actor: CombatantState, ability: Ability, battle: BattleState):
    """Ranged recharge counter: increment exactly once per ability cast."""
    if not is_ranged(actor) or ability.passive:
        return
    if _has_signature_effect(actor, "become_real") and actor.slot != SLOT_FRONT             and actor.ability_charges.get("malice", 0) >= 3:
        return
    if actor.ability_charges.get("natural_order_skip_recharge", 0) > 0:
        actor.ability_charges["natural_order_skip_recharge"] = 0
        return
    actor.ranged_uses += 1
    limit = 2 if actor.has_status("shock") else 3
    if actor.ranged_uses >= limit:
        actor.must_recharge = True
        battle.log_add(f"  {actor.name} must recharge next turn.")


def describe_action(action: Optional[dict]) -> str:
    """Human-readable summary of a queued/resolved action."""
    if action is None:
        return "(none)"

    atype = action.get("type")
    if atype == "skip":
        return "Skip"
    if atype == "swap":
        target = action.get("target")
        return f"Swap with {target.name}" if target else "Swap"
    if atype == "item":
        target = action.get("target")
        target_text = target.name if target else "self"
        return f"Item {target_text}"
    if atype == "ability":
        ability = action.get("ability")
        ability_name = ability.name if ability else "Ability"
        target = action.get("target")
        if target is not None:
            text = f"{ability_name} → {target.name}"
        else:
            text = ability_name
        if action.get("swap_target") is not None:
            text += f" ↔ {action['swap_target'].name}"
        return text
    return str(atype)


def resolve_queued_action(
    actor: CombatantState,
    acting_player: int,
    battle: BattleState,
):
    """Resolve the queued action for one actor."""
    if actor.ko:
        return
    if not can_act_this_round(actor, battle, acting_player):
        battle.log_add(f"{actor.name} cannot act.")
        actor.acted = True
        return

    action = actor.queued
    if action is None:
        actor.acted = True
        return

    atype = action["type"]

    # Technical action log
    if atype == "ability":
        _tname = action["target"].name if action.get("target") else "spread/auto"
        battle.log_tech(
            f"ACTION P{acting_player} {actor.name}[{actor.slot}]:"
            f" {action['ability'].name} → {_tname}"
        )
    elif atype == "swap":
        _tname = action["target"].name if action.get("target") else "?"
        battle.log_tech(
            f"ACTION P{acting_player} {actor.name}[{actor.slot}]: swap ↔ {_tname}"
        )
    elif atype == "item":
        _tname = action["target"].name if action.get("target") else "self"
        battle.log_tech(
            f"ACTION P{acting_player} {actor.name}[{actor.slot}]:"
            f" item [{actor.item.name}] → {_tname}"
        )
    elif atype == "skip":
        battle.log_tech(
            f"ACTION P{acting_player} {actor.name}[{actor.slot}]: skip/recharge"
        )

    # If unit must recharge, force a recharge regardless of chosen action
    if actor.must_recharge and atype in ("swap", "item"):
        actor.ranged_uses = 0
        actor.must_recharge = False
        battle.log_add(f"{actor.name} recharges.")
        actor.acted = True
        return

    if atype == "skip":
        if actor.must_recharge:
            actor.ranged_uses = 0
            actor.must_recharge = False
            battle.log_add(f"{actor.name} recharges.")
        else:
            battle.log_add(f"{actor.name} skips.")
        actor.acted = True
        return

    if atype == "swap":
        if battle.swap_used_this_turn:
            battle.log_add(f"{actor.name} cannot swap (swap already used this turn).")
            actor.acted = True
            return

        team = battle.get_team(acting_player)
        ally = action.get("target")
        did_swap = False
        if ally and not ally.ko and ally != actor:
            if not actor.has_status("root"):
                do_swap(actor, ally, team, battle)
                did_swap = True
            else:
                battle.log_add(f"{actor.name} is Rooted and cannot swap.")
        if did_swap:
            battle.swap_used_this_turn = True
        actor.acted = True
        return

    if atype == "ability":
        ability = action["ability"]
        target  = action.get("target")
        mode    = get_mode(actor, ability)

        # Stolen Voices (Asha): gain Malice when enemy uses signature while Asha is backline.
        if ability.category == "signature":
            enemy_team = battle.get_enemy(acting_player)
            for e in enemy_team.alive():
                if _has_talent(e, "sea_wench_asha") and e.slot != SLOT_FRONT:
                    _gain_malice(e, 1, battle, "Stolen Voices")

        if not can_use_ability(actor, ability, battle.get_team(acting_player)):
            battle.log_add(f"{actor.name} cannot use {ability.name}.")
            actor.acted = True
            return

        # Defensive legality guard: queued targets may become invalid due to
        # stale UI state, swaps, or handcrafted test actions. Re-validate here
        # so rules enforcement doesn't depend solely on selection-time checks.
        legal_targets = get_legal_targets(battle, acting_player, actor, ability)
        queued_from_slot = action.get("queued_from_slot")
        slot_changed_since_queue = queued_from_slot is not None and queued_from_slot != actor.slot

        if not mode.spread and (target is None or target not in legal_targets):
            if slot_changed_since_queue and legal_targets:
                enemy_front = battle.get_enemy(acting_player).frontline()
                fallback_target = enemy_front if enemy_front in legal_targets else legal_targets[0]
                target = fallback_target
                action["target"] = fallback_target
                battle.log_add(
                    f"  {actor.name} retargets to {fallback_target.name} after swapping to {actor.slot}."
                )
            elif target is not None:
                battle.log_add(f"{actor.name}'s target is no longer legal — {ability.name} fizzles.")
                actor.acted = True
                return
        if mode.special == "subterfuge_swap":
            swap_target = action.get("swap_target")
            legal_swap_targets = get_subterfuge_swap_targets(
                battle, acting_player, target
            )
            if swap_target not in legal_swap_targets:
                battle.log_add(
                    f"{actor.name} must choose a second enemy for {ability.name} — action fizzles."
                )
                actor.acted = True
                return

        # Wolf's Pursuit FL: retarget if original target swapped off frontline
        if mode.special == "wolfs_pursuit_retarget" and target is not None:
            if target.slot != SLOT_FRONT or target.ko:
                enemy_team = battle.get_enemy(acting_player)
                new_fl = enemy_team.frontline()
                if new_fl and new_fl != target:
                    battle.log_add(
                        f"  Wolf's Pursuit retargets to {new_fl.name}.")
                    target = new_fl
                    action["target"] = target

        # Hypnotic Aura: Shocked actors redirected by Hunold's position
        if target is not None and actor.has_status("shock") and not mode.spread:
            enemy_team = battle.get_enemy(acting_player)
            hunold = next(
                (m for m in enemy_team.alive() if m.sig.id == "hypnotic_aura"), None
            )
            if hunold:
                if hunold.slot == SLOT_FRONT:
                    redirect = enemy_team.get_slot(SLOT_BACK_LEFT)
                else:
                    redirect = enemy_team.frontline()
                if redirect and not redirect.ko and redirect != target:
                    battle.log_add(
                        f"  Hypnotic Aura! {actor.name} redirected to {redirect.name}.")
                    target = redirect
                    action["target"] = target

        _pride_abilities = {"heros_charge", "slay_the_beast"}
        if mode.spread:
            battle.log_add(f"{actor.name} uses {ability.name}.")
            ignore_pride = action.get("ignore_pride", False) or ability.id in _pride_abilities
            execute_spread_ability(actor, ability, acting_player, battle,
                                   ignore_pride=ignore_pride)
            _track_ranged_use_once(actor, ability, battle)
        elif target and not target.ko:
            battle.log_add(f"{actor.name} uses {ability.name} on {target.name}.")
            ignore_pride = action.get("ignore_pride", False) or ability.id in _pride_abilities
            execute_ability(actor, ability, target, acting_player, battle,
                            ignore_pride=ignore_pride, action_context=action)
            _track_ranged_use_once(actor, ability, battle)
        else:
            battle.log_add(f"{actor.name}'s target is gone — {ability.name} fizzles.")

        check_and_promote(battle)
        actor.acted = True
        return

    if atype == "item":
        target = action.get("target", actor)
        legal_targets = get_legal_item_targets(battle, acting_player, actor)
        if target not in legal_targets:
            battle.log_add(f"{actor.name}'s item target is no longer legal — item fizzles.")
            actor.acted = True
            return
        execute_item(actor, target, acting_player, battle)
        actor.acted = True
        return


def resolve_player_turn(battle: BattleState, player_num: int):
    """Resolve all queued actions for one player in clockwise order."""
    team = battle.get_team(player_num)

    # Snapshot the actor identities at turn start so swaps during resolution
    # do not cause the same unit to act twice (or skip another unit).
    order = [team.get_slot(slot) for slot in CLOCKWISE_ORDER]

    for unit in order:
        if unit is None or unit.ko:
            continue

        resolve_queued_action(unit, player_num, battle)
        unit.queued = None

        if check_winner(battle):
            return

        # Extra actions pre-queued by player (Rabbit Hole next-round)
        if not unit.ko and unit.extra_actions_now > 0 and unit.queued2 is not None:
            unit.extra_actions_now -= 1
            unit.queued = unit.queued2
            unit.queued2 = None
            resolve_queued_action(unit, player_num, battle)
            unit.queued = None
            if check_winner(battle):
                return


# ─────────────────────────────────────────────────────────────────────────────
# END OF ROUND
# ─────────────────────────────────────────────────────────────────────────────

def end_round(battle: BattleState):
    """Burn damage, sanctuary heals, status ticking, buff ticking, promotion."""
    battle_log.section(f"END OF ROUND {battle.round_num}")
    # Pre-end-round state snapshot
    battle.log_tech(f"PRE-END STATE (R{battle.round_num}):")
    for _tn, _to in [(1, battle.team1), (2, battle.team2)]:
        for _u in _to.members:
            if _u.ko:
                battle.log_tech(f"  P{_tn} {_u.name} [KO]")
            else:
                _sts = ", ".join(f"{s.kind}({s.duration}r)" for s in _u.statuses) or "-"
                battle.log_tech(
                    f"  P{_tn} {_u.name}[{_u.slot}] HP={_u.hp}/{_u.max_hp}"
                    f" statuses=[{_sts}]"
                )
    for team in (battle.team1, battle.team2):
        acting_p = 1 if team == battle.team1 else 2

        for unit in list(team.alive()):
            # Burn damage
            if unit.has_status("burn"):
                burn_dmg = math.ceil(unit.max_hp * 0.10)
                unit.hp -= burn_dmg
                if unit.hp <= 0:
                    unit.hp = 0
                    unit.ko = True
                battle.log_add(f"{unit.name} burns for {burn_dmg} damage.")

            # Drown in the Loch: bonus_damage status ticks with statuses below
            # (counts down with normal status tick)

        check_and_promote(battle)
        if check_winner(battle):
            return

        # ── NPC Campaign Talents: end-of-round effects ────────────────────────
        for unit in list(team.alive()):
            # Divine Recovery (Apex Cleric): heal 20 HP per round
            if unit.defn.id == "npc_apex_cleric":
                do_heal(unit, 20, unit, battle)
                battle.log_add(f"{unit.name} recovers 20 HP (Divine Recovery).")

        # Dark Aura (Dragon Head Warlock passive): spend 2 Malice to Weaken all enemies each round
        enemy_team_for_dark_aura = battle.team2 if team == battle.team1 else battle.team1
        for unit in list(team.alive()):
            if unit.defn.id == "npc_dragon_warlock":
                malice = unit.ability_charges.get("malice", 0)
                if malice >= 2:
                    unit.ability_charges["malice"] -= 2
                    for enemy_unit in enemy_team_for_dark_aura.alive():
                        enemy_unit.add_status("weaken", 2)
                    battle.log_add(f"{unit.name} uses Dark Aura — all enemies are Weakened!")

        for unit in list(team.alive()):
            # Sanctuary passive: allies heal 1/10 max HP each round
            if _has_signature_effect(unit, "sanctuary"):
                if unit.slot == SLOT_FRONT:
                    for ally in team.alive():
                        heal = math.ceil(ally.max_hp * 0.10)
                        do_heal(ally, heal, unit, battle)
                else:
                    fl = team.frontline()
                    if fl:
                        heal = math.ceil(fl.max_hp / 12)
                        do_heal(fl, heal, unit, battle)

            # Midnight Dour backline: Ella heals 35 HP at end of round
            if _has_signature_effect(unit, "midnight_dour") and unit.slot != SLOT_FRONT:
                do_heal(unit, 35, unit, battle)

            # Awaited Blow BL: heal 40 HP at end of round
            if _has_signature_effect(unit, "awaited_blow") and unit.slot != SLOT_FRONT:
                do_heal(unit, 40, unit, battle)

            # Redemption: heal 50 HP for 2 rounds
            if unit.ability_charges.get("redemption_heal", 0) > 0:
                do_heal(unit, 50, unit, battle)
                unit.ability_charges["redemption_heal"] -= 1

            # Ancient Hourglass: clear flag after one round
            if unit.ability_charges.get("hourglass", 0) > 0:
                unit.ability_charges["hourglass"] -= 1
                if unit.ability_charges["hourglass"] <= 0:
                    unit.untargetable = False
                    unit.cant_act = False

            # Struck Midnight: clear after 2 rounds
            if unit.ability_charges.get("struck_midnight", 0) > 0:
                unit.ability_charges["struck_midnight"] -= 1
                if unit.ability_charges["struck_midnight"] <= 0:
                    unit.untargetable = False
                    unit.cant_act = False

            # Briar Rose: clear cant_act flag and tick root immunity countdown
            if unit.ability_charges.get("briar_cant_act", 0) > 0:
                unit.ability_charges["briar_cant_act"] = 0
            if unit.ability_charges.get("briar_root_immune", 0) > 0:
                unit.ability_charges["briar_root_immune"] -= 1

            # Tick status durations
            for s in unit.statuses:
                if s.duration > 0:
                    s.duration -= 1
                    battle.log_tech(
                        f"STATUS_TICK {unit.name}: {s.kind} → {s.duration}r left"
                    )
                # Innocent Heart: on status expiry (duration → 0 this tick)
                # (handled next pass below)

            # Remove expired statuses and trigger Innocent Heart
            expired = [s.kind for s in unit.statuses if s.duration <= 0]
            unit.statuses = [s for s in unit.statuses if s.duration > 0]
            for kind in expired:
                battle.log_tech(f"STATUS_EXPIRED {unit.name}: {kind}")
                if is_rulebook_status_condition(kind):
                    _trigger_innocent_heart(unit, kind, battle)
                if kind == "dormant":
                    unit.cant_act = False
                    battle.log_add(f"  {unit.name} wakes from dormancy.")

            # Tick buffs and debuffs
            expired_buffs = []
            for b in unit.buffs:
                if b.duration > 0:
                    b.duration -= 1
                    if b.duration == 0:
                        battle.log_tech(
                            f"BUFF_EXPIRED {unit.name}: {b.stat}+{b.amount}"
                        )
                        expired_buffs.append((b.stat, b.amount))
            unit.buffs = [b for b in unit.buffs if b.duration > 0]

            # Spinning Wheel BL: when an ally loses a buff, spend 2 Malice to refresh it.
            if expired_buffs:
                for ally in team.alive():
                    if ally == unit:
                        continue
                    if _has_signature_effect(ally, "spinning_wheel") and ally.slot != SLOT_FRONT:
                        for st, amt in expired_buffs:
                            if _spend_malice(ally, 2, battle, "Spinning Wheel"):
                                apply_stat_buff(unit, st, amt, 2, battle)
                                battle.log_add(f"  Spinning Wheel: {unit.name}'s {st} buff is refreshed.")

            for d in unit.debuffs:
                if d.duration > 0:
                    d.duration -= 1
                    if d.duration == 0:
                        battle.log_tech(
                            f"DEBUFF_EXPIRED {unit.name}: {d.stat}-{d.amount}"
                        )
            unit.debuffs = [d for d in unit.debuffs if d.duration > 0]

            # Birdsong FL: cure the last-inflicted status on each ally each round
            if _has_signature_effect(unit, "birdsong") and unit.slot == SLOT_FRONT:
                for ally in team.alive():
                    last = ally.last_status_inflicted
                    if last and is_rulebook_status_condition(last) and ally.has_status(last):
                        ally.remove_status(last)
                        _trigger_innocent_heart(ally, last, battle)
                        battle.log_add(
                            f"  Birdsong: {ally.name} cured of {last}.")

            # Straw to Gold FL: return stolen buff when lease ends.
            if unit.ability_charges.get("straw_return_dur", 0) > 0:
                unit.ability_charges["straw_return_dur"] -= 1
                if unit.ability_charges["straw_return_dur"] <= 0:
                    tgt = unit.ability_charges.get("straw_return_target")
                    stat = unit.ability_charges.get("straw_return_stat")
                    amount = unit.ability_charges.get("straw_return_amount", 0)
                    dur = unit.ability_charges.get("straw_return_orig_dur", 2)
                    if tgt is not None and not tgt.ko and stat and amount > 0:
                        tgt.add_buff(stat, amount, dur)
                        battle.log_add(
                            f"  Straw to Gold: {tgt.name} regains {stat}+{amount} for {dur} rounds."
                        )
                    for k in ("straw_return_target", "straw_return_stat", "straw_return_amount", "straw_return_dur", "straw_return_orig_dur"):
                        unit.ability_charges.pop(k, None)

            # Deathlike Slumber: decrement doubled Innocent Heart counter
            if unit.ability_charges.get("deathlike_doubled", 0) > 0:
                unit.ability_charges["deathlike_doubled"] -= 1

            # Birdsong BL: tick duration; clear stacks when expired
            if _has_signature_effect(unit, "birdsong") and unit.slot != SLOT_FRONT:
                dur = unit.ability_charges.get("birdsong_dur", 0)
                if dur > 0:
                    unit.ability_charges["birdsong_dur"] = dur - 1
                    if unit.ability_charges["birdsong_dur"] <= 0:
                        unit.ability_charges["birdsong_stacks"] = 0

            # Growing Pains (Pinocchio): gain Malice when ending round in frontline
            if _has_talent(unit, "pinocchio") and unit.slot == SLOT_FRONT:
                _gain_malice(unit, 1, battle, "Growing Pains")

            # Noble upkeep
            unit.ability_charges["rounds_since_swap"] = unit.ability_charges.get("rounds_since_swap", 0) + 1
            if unit.defn.id == "rapunzel" and unit.slot != SLOT_FRONT:
                unit.ability_charges["flowing_locks_ready"] = 1
            for k in ("summons_cd", "severed_tether_active", "was_backline_last_round", f"command_allies_p{acting_p}", f"command_user_p{acting_p}", "chosen_one_mark", "natural_order_skip_recharge"):
                if unit.ability_charges.get(k, 0) > 0:
                    unit.ability_charges[k] -= 1
            unit.ability_charges["was_backline_last_round"] = 1 if unit.slot != SLOT_FRONT else 0

            # stolen talent/signature duration ticks
            if unit.ability_charges.get("stolen_talent_dur", 0) > 0:
                unit.ability_charges["stolen_talent_dur"] -= 1
                if unit.ability_charges["stolen_talent_dur"] <= 0:
                    unit.ability_charges.pop("stolen_talent", None)
            if unit.ability_charges.get("stolen_signature_dur", 0) > 0:
                unit.ability_charges["stolen_signature_dur"] -= 1
                if unit.ability_charges["stolen_signature_dur"] <= 0:
                    unit.ability_charges.pop("stolen_signature", None)

            # Reset per-round flags
            unit.acted = False
            # Don't clear Shimmering Valor's multi-round reduction
            if unit.valor_rounds == 0:
                unit.dmg_reduction = 0.0
            unit.retaliate_power = 0
            unit.retaliate_speed_steal = 0

            # Move extra_actions_next to extra_actions_now
            if unit.extra_actions_next > 0:
                unit.extra_actions_now = unit.extra_actions_next
                unit.extra_actions_next = 0

            # Valor: decrement remaining rounds and remove reduction if 0
            if unit.valor_rounds > 0:
                unit.valor_rounds -= 1
                if unit.valor_rounds == 0:
                    unit.dmg_reduction = 0.0

    battle.swap_used_this_turn = False
    battle.crumb_picked_up = None

    if getattr(battle, "fated_duel_rounds", 0) > 0:
        battle.fated_duel_rounds -= 1
        if battle.fated_duel_rounds <= 0:
            battle.fated_duel_units = ()
            battle.log_add("  Fated Duel ends.")

    battle.round_num += 1


def start_new_round(battle: BattleState):
    """Called at the start of a new round: apply passives then initiative."""
    apply_passive_stats(battle.team1, battle)
    apply_passive_stats(battle.team2, battle)
    determine_initiative(battle)


# ─────────────────────────────────────────────────────────────────────────────
# ROUND START EFFECTS
# ─────────────────────────────────────────────────────────────────────────────

def apply_round_start_effects(battle: BattleState):
    """Effects that trigger at the start of each round before action selection.
    Currently handles Briar Rose's Curse of Sleeping talent.
    """
    for team in (battle.team1, battle.team2):
        enemy = battle.get_enemy(1 if team == battle.team1 else 2)
        briar = next((u for u in team.alive() if u.defn.id == "briar_rose"), None)
        if briar is None:
            continue
        # Find the lowest-HP Rooted enemy (root-immune enemies are excluded)
        rooted = [u for u in enemy.alive()
                  if u.has_status("root") and not u.ability_charges.get("briar_root_immune", 0) > 0]
        if not rooted:
            continue
        target = min(rooted, key=lambda u: u.hp)
        # Strip Root
        target.remove_status("root")
        _trigger_innocent_heart(target, "root", battle)
        # Can't act this round
        target.ability_charges["briar_cant_act"] = 1
        # Can't be Rooted next round
        target.ability_charges["briar_root_immune"] = 2
        battle.log_add(
            f"  Curse of Sleeping: {target.name} loses Root — cannot act or be Rooted this round."
        )


# ─────────────────────────────────────────────────────────────────────────────
# CURSE OF SLEEPING  (Briar Rose talent helper)
# ─────────────────────────────────────────────────────────────────────────────

def can_act_this_round(unit: CombatantState, battle: BattleState = None, acting_player: int = None) -> bool:
    """Returns whether a unit is currently allowed to act."""
    if unit.cant_act:
        return False
    # Curse of Sleeping: unit can't act the round it loses Root to Briar Rose.
    if unit.ability_charges.get("briar_cant_act", 0) > 0:
        return False
    # Fated Duel: only the two locked duelists may act.
    if battle is not None and getattr(battle, "fated_duel_rounds", 0) > 0:
        duel_units = getattr(battle, "fated_duel_units", ())
        if unit not in duel_units:
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGN REWARD APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

def apply_quest_rewards(profile, quest_id: int, notify: bool = True):
    """Apply rewards for clearing quest_id to profile.  Idempotent.
    notify=False suppresses new_unlocks badges (used for bootstrap/starter calls)."""
    from campaign_data import QUEST_TABLE

    quest = QUEST_TABLE.get(quest_id)
    if quest is None:
        return

    rewards = quest.rewards or {}

    # ── Recruit new adventurers ────────────────────────────────────────────────
    for entry in rewards.get("recruit", []):
        adv_id, sig_id = entry
        if notify and adv_id not in profile.recruited:
            profile.new_unlocks.add("adventurers")
        profile.recruited.add(adv_id)
        # Set default sig only if not already chosen by the player
        if adv_id not in profile.default_sigs:
            profile.default_sigs[adv_id] = sig_id

    # ── Unlock signature tier ──────────────────────────────────────────────────
    new_sig_tier = rewards.get("sig_tier")
    if new_sig_tier is not None:
        if notify and new_sig_tier > profile.sig_tier:
            profile.new_unlocks.add("basics")
        profile.sig_tier = max(profile.sig_tier, new_sig_tier)

    # ── Unlock basics tier ─────────────────────────────────────────────────────
    new_basics_tier = rewards.get("basics_tier")
    if new_basics_tier is not None:
        if notify and new_basics_tier > profile.basics_tier:
            profile.new_unlocks.add("basics")
        profile.basics_tier = max(profile.basics_tier, new_basics_tier)

    # ── Unlock items ───────────────────────────────────────────────────────────
    for item_id in rewards.get("items", []):
        if notify and item_id not in profile.unlocked_items:
            profile.new_unlocks.add("items")
        profile.unlocked_items.add(item_id)

    # ── Unlock classes ─────────────────────────────────────────────────────────
    for cls_name in rewards.get("classes", []):
        if notify and cls_name not in profile.unlocked_classes:
            profile.new_unlocks.add("basics")
        profile.unlocked_classes.add(cls_name)

    # ── Unlock twists ──────────────────────────────────────────────────────────
    if rewards.get("twists"):
        profile.twists_unlocked = True

    # ── Campaign completion flags ─────────────────────────────────────────────
    if rewards.get("ranked_glory"):
        profile.ranked_glory_unlocked = True
    if rewards.get("campaign_complete"):
        profile.campaign_complete = True

    # ── Record this quest as cleared ──────────────────────────────────────────
    profile.quest_cleared[quest_id] = True
    profile.highest_quest_cleared = max(profile.highest_quest_cleared, quest_id)
