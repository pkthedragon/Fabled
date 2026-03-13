"""
ai.py – Improved AI decision-making for Fabled.

Replaces the greedy single-pass scorer in _ai_queue_current_actor_action.
No game mechanics are altered here; only the choice of action changes.

Architecture:
  pick_action()          public entry point called by main.py
  evaluate_state()       signed numeric board evaluation (pure read)
  _build_candidates()    enumerate all legal actions for the actor
  _simulate()            deep-copy + resolve one action, suppress log I/O
  _heuristic_bonus()     fast, no-simulation bonuses/penalties
  _initiative_bonus()    small adjustments based on acted flags
  _recharge_bonus()      nudge toward sig use when it just became available
  _apply_char_hooks()    per-adventurer overrides
"""

import copy

import battle_log
from settings import SLOT_FRONT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT
from logic import (
    can_use_ability, get_legal_targets, get_legal_item_targets,
    get_subterfuge_swap_targets, resolve_queued_action, get_mode,
)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

# If a candidate list is larger than this, skip simulation and use heuristics only.
MAX_SIMULATED_CANDIDATES = 30

DANGEROUS_STATUSES = {"burn", "bleed", "poison"}


# ─────────────────────────────────────────────────────────────────────────────
# STATE EVALUATOR
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_state(battle, for_player: int) -> float:
    """
    Signed numeric evaluation of battle state from for_player's perspective.
    Positive = good for for_player.  Pure read — does not mutate battle.
    """
    own_team   = battle.get_team(for_player)
    enemy_team = battle.get_enemy(for_player)
    own_alive  = own_team.alive()
    enemy_alive = enemy_team.alive()

    if not own_alive:
        return -10000.0
    if not enemy_alive:
        return 10000.0

    score = 0.0

    # ── HP ratios ────────────────────────────────────────────────────────────
    own_hp_ratio   = sum(u.hp / u.max_hp for u in own_alive)   / len(own_alive)
    enemy_hp_ratio = sum(u.hp / u.max_hp for u in enemy_alive) / len(enemy_alive)
    score += own_hp_ratio   * 100.0
    score -= enemy_hp_ratio * 100.0

    # ── KO counts ────────────────────────────────────────────────────────────
    own_ko   = sum(1 for u in own_team.members   if u.ko)
    enemy_ko = sum(1 for u in enemy_team.members if u.ko)
    score -= own_ko   * 35.0
    score += enemy_ko * 35.0

    # ── Frontliner durability ─────────────────────────────────────────────────
    own_front   = own_team.frontline()
    enemy_front = enemy_team.frontline()
    if own_front:
        durability = own_front.get_stat("defense") + (own_front.hp / own_front.max_hp) * 20
        score += durability * 0.4
    if enemy_front:
        durability = enemy_front.get_stat("defense") + (enemy_front.hp / enemy_front.max_hp) * 20
        score -= durability * 0.25

    # ── Active buffs / debuffs ────────────────────────────────────────────────
    own_buff_turns   = sum(b.duration for u in own_alive   for b in u.buffs   if b.duration > 0)
    enemy_buff_turns = sum(b.duration for u in enemy_alive for b in u.buffs   if b.duration > 0)
    own_debuff_turns   = sum(d.duration for u in own_alive   for d in u.debuffs if d.duration > 0)
    enemy_debuff_turns = sum(d.duration for u in enemy_alive for d in u.debuffs if d.duration > 0)
    score += own_buff_turns     * 4.0
    score -= enemy_buff_turns   * 4.0
    score -= own_debuff_turns   * 4.0
    score += enemy_debuff_turns * 4.0

    # ── Dangerous statuses ────────────────────────────────────────────────────
    for u in own_alive:
        for s in u.statuses:
            if s.kind in DANGEROUS_STATUSES and s.duration > 0:
                score -= 6.0 * s.duration
    for u in enemy_alive:
        for s in u.statuses:
            if s.kind in DANGEROUS_STATUSES and s.duration > 0:
                score += 4.0 * s.duration

    # ── Other harmful statuses on own team ───────────────────────────────────
    for u in own_alive:
        for s in u.statuses:
            if s.kind in ("weaken", "expose", "root", "shock") and s.duration > 0:
                score -= 4.0

    # ── Item preservation ─────────────────────────────────────────────────────
    score += sum(3.0 for u in own_alive if u.item_uses_left > 0 and not u.item.passive)

    # ── Recharge penalty ──────────────────────────────────────────────────────
    for u in own_alive:
        if u.must_recharge:
            score -= 5.0

    # ── Backline safety (fragile units) ───────────────────────────────────────
    for u in own_alive:
        if u.slot != SLOT_FRONT and u.get_stat("defense") < 10:
            score += 3.0

    return score


# ─────────────────────────────────────────────────────────────────────────────
# SIMULATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _unit_key(unit):
    """Stable (defn.id, slot) identifier that survives deep copy."""
    return (unit.defn.id, unit.slot)


def _find_unit(sim_battle, key):
    """Find a unit in sim_battle by (defn.id, slot)."""
    defn_id, slot = key
    for u in sim_battle.team1.members + sim_battle.team2.members:
        if u.defn.id == defn_id and u.slot == slot:
            return u
    return None


def _remap_action(action, sim_battle):
    """
    Re-map CombatantState pointers in action from the real battle
    to the corresponding objects inside sim_battle.
    """
    remapped = dict(action)
    if action.get("target") is not None:
        key = _unit_key(action["target"])
        remapped["target"] = _find_unit(sim_battle, key)
    if action.get("swap_target") is not None:
        key = _unit_key(action["swap_target"])
        remapped["swap_target"] = _find_unit(sim_battle, key)
    return remapped


def _simulate(battle, player_num: int, actor, action: dict):
    """
    Deep-copy the battle, apply one actor's action, return the resulting state.
    All battle_log I/O is suppressed during simulation so the real log is clean.
    """
    sim = copy.deepcopy(battle)

    # Suppress file writes
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


# ─────────────────────────────────────────────────────────────────────────────
# CANDIDATE BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def _build_candidates(battle, player_num: int, actor,
                      is_extra: bool, swap_used: bool, swap_queued: bool) -> list:
    """Enumerate every legal action for actor as action dicts."""
    team  = battle.get_team(player_num)
    enemy = battle.get_enemy(player_num)
    candidates = []

    # ── Abilities ────────────────────────────────────────────────────────────
    abilities = list(actor.basics) + [actor.sig]
    if len(team.alive()) == 1 and team.alive()[0] == actor:
        abilities.append(actor.defn.twist)

    for ability in abilities:
        if not can_use_ability(actor, ability, team):
            continue
        mode    = get_mode(actor, ability)
        targets = get_legal_targets(battle, player_num, actor, ability)

        if mode.spread:
            if enemy.alive():
                candidates.append({"type": "ability", "ability": ability, "target": None})
            continue

        for target in targets:
            if ability.id == "subterfuge":
                swap_targets = get_subterfuge_swap_targets(battle, player_num, target)
                if not swap_targets:
                    continue
                for st in swap_targets:
                    candidates.append({"type": "ability", "ability": ability,
                                       "target": target, "swap_target": st})
            else:
                candidates.append({"type": "ability", "ability": ability, "target": target})

    # ── Swap ─────────────────────────────────────────────────────────────────
    can_swap = (
        not is_extra
        and not swap_used
        and not swap_queued
        and not actor.has_status("root")
    )
    if can_swap:
        for ally in [u for u in team.alive() if u != actor]:
            candidates.append({"type": "swap", "target": ally})

    # ── Item ─────────────────────────────────────────────────────────────────
    for target in get_legal_item_targets(battle, player_num, actor):
        candidates.append({"type": "item", "target": target})

    # ── Skip (always included as baseline) ───────────────────────────────────
    candidates.append({"type": "skip"})

    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# HEURISTIC BONUSES
# ─────────────────────────────────────────────────────────────────────────────

def _heuristic_bonus(battle, player_num: int, actor, action: dict) -> float:
    """Fast bonuses/penalties that don't require simulation."""
    bonus = 0.0
    team  = battle.get_team(player_num)
    enemy = battle.get_enemy(player_num)
    atype = action["type"]

    if atype == "ability":
        ability = action["ability"]
        target  = action.get("target")
        mode    = get_mode(actor, ability)

        if target is not None and target in enemy.alive():
            # ── Finishing blow ────────────────────────────────────────────
            # Rough estimate: atk + power vs target def / 2
            est_dmg = actor.get_stat("attack") + mode.power - target.get_stat("defense") // 2
            if est_dmg >= target.hp > 0:
                bonus += 40.0

            # ── Status application ────────────────────────────────────────
            statuses = [s for s in (mode.status, mode.status2, mode.status3) if s]
            for s in statuses:
                if target.has_status(s):
                    bonus -= 5.0  # already has it — diminished return
                else:
                    bonus += 8.0

            # ── Debuffs ───────────────────────────────────────────────────
            debuffs = sum(1 for d in (mode.atk_debuff, mode.spd_debuff, mode.def_debuff) if d > 0)
            bonus += debuffs * 6.0

            # ── Bonus: targeting low-HP enemies ──────────────────────────
            if target.hp < target.max_hp * 0.4:
                bonus += 10.0

        elif target is not None and target in team.alive():
            # ── Healing waste penalty ─────────────────────────────────────
            heal_amt = mode.heal + mode.heal_lowest + mode.heal_self
            if heal_amt > 0:
                missing = target.max_hp - target.hp
                if missing < heal_amt * 0.25:
                    bonus -= 20.0
                elif target.hp < target.max_hp * 0.4:
                    bonus += 15.0

            # ── Buffs ─────────────────────────────────────────────────────
            buffs = sum(1 for b in (mode.atk_buff, mode.spd_buff, mode.def_buff) if b > 0)
            bonus += buffs * 5.0

            # ── Guard on low-HP ally ──────────────────────────────────────
            if any([mode.guard_target, mode.guard_all_allies, mode.guard_frontline_ally]):
                if target.hp < target.max_hp * 0.4:
                    bonus += 12.0

        # ── Spread: extra value per additional hit ────────────────────────
        if mode.spread:
            bonus += (len(enemy.alive()) - 1) * 8.0

    elif atype == "swap":
        swap_target = action.get("target")
        own_front = team.frontline()

        if own_front and swap_target:
            # Critically low frontliner → swap in something tougher
            if own_front.hp < own_front.max_hp * 0.3:
                if (swap_target.get_stat("defense") + swap_target.hp >
                        own_front.get_stat("defense") + own_front.hp):
                    bonus += 30.0
                else:
                    bonus -= 10.0

            # Rooted frontliner → swap out
            if own_front.has_status("root") and not swap_target.has_status("root"):
                bonus += 15.0

            # Swap target has frontline-only sig mode ready
            if swap_target.slot != SLOT_FRONT:
                fl_mode = swap_target.sig.frontline
                if not fl_mode.unavailable and fl_mode.power > 0 and not swap_target.must_recharge:
                    bonus += 8.0

            # Penalise: incoming unit is debuffed / statused / fragile
            for s in ("burn", "weaken", "expose"):
                if swap_target.has_status(s):
                    bonus -= 8.0
            if (swap_target.get_stat("defense") < 8
                    and swap_target.hp < swap_target.max_hp * 0.5):
                bonus -= 12.0

        # Penalise pointless swap when current actor is healthy frontliner
        if actor.slot == SLOT_FRONT and actor.hp > actor.max_hp * 0.6:
            bonus -= 10.0

    elif atype == "item":
        it     = actor.item
        target = action.get("target")
        if it.heal > 0 and target:
            missing = target.max_hp - target.hp
            if missing < it.heal * 0.25:
                bonus -= 12.0
            if target.hp < target.max_hp * 0.4:
                bonus += 10.0
        if it.guard and target:
            if target.hp < target.max_hp * 0.5:
                bonus += 14.0
        if it.status and target and target in enemy.alive():
            bonus += 8.0
        # Item use has a baseline cost (item gone)
        bonus -= 5.0

    elif atype == "skip":
        bonus -= 8.0  # skipping is almost never the right move

    return bonus


# ─────────────────────────────────────────────────────────────────────────────
# INITIATIVE AWARENESS
# ─────────────────────────────────────────────────────────────────────────────

def _initiative_bonus(battle, player_num: int, actor, action: dict) -> float:
    """Small heuristic adjustments based on whether enemies have already acted."""
    bonus = 0.0
    enemy = battle.get_enemy(player_num)

    # Low-HP enemy hasn't acted yet → prioritise finishing them this turn
    if action.get("type") == "ability":
        target = action.get("target")
        if target is not None and target in enemy.alive():
            if not target.acted and target.hp < target.max_hp * 0.3:
                bonus += 8.0

    # All enemies have already acted → marginally less urgent to attack
    if all(u.acted for u in enemy.alive()):
        if action.get("type") == "skip":
            bonus -= 5.0  # still bad to skip

    return bonus


# ─────────────────────────────────────────────────────────────────────────────
# RECHARGE AWARENESS
# ─────────────────────────────────────────────────────────────────────────────

def _recharge_bonus(battle, player_num: int, actor, action: dict) -> float:
    """Nudge: minor penalty for spending sig when enemy is nearly dead anyway."""
    if action.get("type") != "ability":
        return 0.0
    ability = action.get("ability")
    if ability is None or ability.category != "signature":
        return 0.0

    enemy = battle.get_enemy(player_num)
    if not enemy.alive():
        return 0.0

    total_hp  = sum(u.hp      for u in enemy.alive())
    total_max = sum(u.max_hp  for u in enemy.alive())
    # If enemy is nearly wiped, reserve sig for next battle (minor penalty)
    if total_max > 0 and total_hp / total_max < 0.2:
        return -5.0

    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# CHARACTER-SPECIFIC HOOKS
# ─────────────────────────────────────────────────────────────────────────────

def _hook_ashen_ella(battle, player_num, actor, action, score):
    """
    Ella's Two Lives talent: she can only act from frontline.
    If she's backline, override every other option with a swap to frontliner.
    """
    if actor.slot != SLOT_FRONT and action["type"] == "swap":
        team = battle.get_team(player_num)
        frontliner = team.frontline()
        if frontliner and action.get("target") == frontliner:
            score += 500.0  # guaranteed winner over all other options
    return score


def _hook_rumpelstiltskin(battle, player_num, actor, action, score):
    """
    Spinning Wheel passive (logic.py) awards +7 per unique buffed stat among all
    adventurers.  Encourage Rumpel to attack from frontline when buffs are active,
    since the simulation may not fully capture the conditional power bonus if the
    passive triggers implicitly.
    """
    if action.get("type") != "ability":
        return score
    mode = get_mode(actor, action["ability"])
    if mode.power <= 0:
        return score
    if actor.slot != SLOT_FRONT:
        return score

    all_others = [u for u in battle.team1.alive() + battle.team2.alive() if u != actor]
    unique_stats = {b.stat for u in all_others for b in u.buffs if b.duration > 0}
    if unique_stats:
        score += len(unique_stats) * 5.0
    return score


def _hook_robin(battle, player_num, actor, action, score):
    """
    Robin's Keen Eye: +15 damage to backline enemies.
    Encourage targeting backline enemies slightly more than frontline ones.
    """
    if action.get("type") != "ability":
        return score
    target = action.get("target")
    if target is None:
        return score
    enemy = battle.get_enemy(player_num)
    if target in enemy.alive() and target.slot != SLOT_FRONT:
        score += 10.0  # Keen Eye bonus not always captured by rough estimate
    return score


def _hook_gretel(battle, player_num, actor, action, score):
    """Gretel's twist: when available (solo), always prefer it."""
    if action.get("type") == "ability" and action["ability"].category == "twist":
        score += 30.0
    return score


_CHAR_HOOKS = {
    "ashen_ella":           _hook_ashen_ella,
    "rumpelstiltskin":      _hook_rumpelstiltskin,
    "robin_hooded_avenger": _hook_robin,
    "gretel":               _hook_gretel,
}


def _apply_char_hooks(battle, player_num, actor, action, score):
    hook = _CHAR_HOOKS.get(actor.defn.id)
    if hook:
        score = hook(battle, player_num, actor, action, score)
    return score


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def pick_action(battle, player_num: int, actor,
                is_extra: bool, swap_used: bool, swap_queued: bool) -> dict:
    """
    Choose and return the best action dict for actor.
    Called by _ai_queue_current_actor_action in main.py.
    """
    candidates  = _build_candidates(battle, player_num, actor, is_extra, swap_used, swap_queued)
    base_score  = evaluate_state(battle, player_num)
    use_sim     = len(candidates) <= MAX_SIMULATED_CANDIDATES

    best_action = {"type": "skip"}
    best_score  = -99999.0

    for action in candidates:
        if use_sim:
            sim   = _simulate(battle, player_num, actor, action)
            delta = evaluate_state(sim, player_num) - base_score
        else:
            delta = 0.0  # too many candidates — heuristics only

        score  = delta
        score += _heuristic_bonus(battle, player_num, actor, action)
        score += _initiative_bonus(battle, player_num, actor, action)
        score += _recharge_bonus(battle, player_num, actor, action)
        score  = _apply_char_hooks(battle, player_num, actor, action, score)

        if score > best_score:
            best_score  = score
            best_action = action

    return best_action
