from __future__ import annotations

from collections import defaultdict

from quests_ai_tags import ADVENTURER_AI, AdventurerAIProfile


PAIR_SYNERGY = {
    frozenset(("hunold_the_piper", "march_hare")): 28,
    frozenset(("briar_rose", "rapunzel_the_golden")): 24,
    frozenset(("briar_rose", "robin_hooded_avenger")): 22,
    frozenset(("sir_roland", "little_jack")): 20,
    frozenset(("sir_roland", "lucky_constantine")): 19,
    frozenset(("matchbox_liesl", "witch_hunter_gretel")): 24,
    frozenset(("matchbox_liesl", "ashen_ella")): 24,
    frozenset(("the_good_beast", "little_jack")): 18,
    frozenset(("the_good_beast", "red_blanchette")): 16,
    frozenset(("the_good_beast", "robin_hooded_avenger")): 14,
    frozenset(("lady_of_reflections", "lucky_constantine")): 18,
    frozenset(("lady_of_reflections", "the_green_knight")): 18,
    frozenset(("lady_of_reflections", "march_hare")): 14,
    frozenset(("robin_hooded_avenger", "little_jack")): 16,
    frozenset(("robin_hooded_avenger", "rapunzel_the_golden")): 16,
    frozenset(("hunold_the_piper", "briar_rose")): 12,
    frozenset(("sir_roland", "matchbox_liesl")): 12,
    frozenset(("porcus_iii", "matchbox_liesl")): 12,
    frozenset(("porcus_iii", "robin_hooded_avenger")): 10,
    frozenset(("the_green_knight", "robin_hooded_avenger")): 12,
}


PAIR_TENSION = {
    frozenset(("sir_roland", "porcus_iii")): -10,
    frozenset(("porcus_iii", "the_good_beast")): -8,
    frozenset(("ashen_ella", "march_hare")): -6,
    frozenset(("pinocchio_cursed_puppet", "red_blanchette")): -6,
}


COUNTER_MATRIX = {
    "anti_guard": {"guard_support": 12, "tank": 6},
    "anti_caster": {"spell_heavy": 14},
    "frontline_breaker": {"tank": 10, "frontline": 6},
    "backline_reach": {"fragile_backline": 10, "slow_backline": 8},
    "burn_enabler": {"attrition": 5},
    "root_enabler": {"swap_heavy": 10, "melee_heavy": 6},
    "shock_engine": {"slow_frontline": 8},
    "burst_finisher": {"exposed": 8, "fragile_backline": 8},
    "healer": {"attrition": 8, "burn_heavy": 6},
    "death_insurance": {"burst_focus": 10},
    "swap_engine": {"single_carry": 6},
}


TEAM_ARCHETYPE_RULES = (
    ("shock_shell", {"shock_engine", "shock_payoff"}, 18),
    ("root_shell", {"root_enabler", "root_payoff"}, 18),
    ("burn_shell", {"burn_enabler", "burn_payoff"}, 16),
    ("expose_burst", {"expose_enabler", "burst_finisher"}, 18),
    ("swap_shell", {"swap_engine", "carry_support"}, 14),
    ("tank_carry_support", {"primary_tank", "healer", "burst_finisher"}, 14),
)


STYLE_ROLE_WEIGHTS = {
    "burst": {
        "burst_finisher": 7.0,
        "frontline_breaker": 5.0,
        "status_payoff": 3.5,
        "scaling_carry": 2.0,
        "bruiser": 3.0,
        "magic_carry": 3.0,
    },
    "control": {
        "shock_engine": 6.0,
        "root_enabler": 6.0,
        "expose_enabler": 4.0,
        "burn_enabler": 4.0,
        "control_anchor": 4.0,
        "duel_control": 3.5,
        "anti_caster": 3.5,
        "taunt": 2.5,
        "stat_manipulator": 3.0,
    },
    "sustain": {
        "healer": 6.0,
        "guard_support": 4.5,
        "anti_burst": 4.5,
        "death_insurance": 4.0,
        "carry_support": 2.5,
    },
    "tempo": {
        "tempo_engine": 6.0,
        "bonus_action_user": 5.0,
        "weapon_switch_user": 4.0,
        "spell_loop": 4.0,
        "swap_engine": 3.5,
        "stat_manipulator": 2.5,
    },
    "mobility": {
        "swap_engine": 6.0,
        "backline_reach": 4.5,
        "frontline_pivot": 3.0,
        "bonus_action_user": 2.5,
        "melee_reach": 3.5,
    },
    "backline_pressure": {
        "backline_reach": 6.0,
        "spotlight_enabler": 4.0,
        "spread_pressure": 4.0,
        "ranged_pressure": 4.0,
        "magic_carry": 3.0,
        "expose_enabler": 2.5,
    },
    "frontline": {
        "primary_tank": 7.0,
        "frontline_ready": 5.0,
        "anti_burst": 3.0,
        "frontline_pivot": 4.0,
        "stall_anchor": 4.0,
        "frontline_growth": 3.0,
        "bruiser": 3.0,
    },
    "ultimate": {
        "tempo_engine": 4.0,
        "spell_loop": 5.0,
        "magic_carry": 3.0,
        "burst_finisher": 2.5,
        "bonus_action_user": 2.0,
    },
    "spread": {
        "spread_pressure": 7.0,
        "burn_enabler": 2.0,
        "shock_engine": 1.5,
    },
    "resource": {
        "weapon_switch_user": 6.0,
        "tempo_engine": 3.0,
        "bonus_action_user": 2.5,
        "anti_caster": 2.0,
    },
    "fragility": {
        "fragile": 7.0,
        "high_variance": 4.0,
        "setup_dependent": 3.5,
    },
}


STYLE_SHELL_WEIGHTS = {
    "control": {"root": 4.0, "shock": 4.0, "burn": 2.0},
    "sustain": {"sustain": 5.0, "protect": 4.0, "attrition": 2.5},
    "tempo": {"tempo": 5.0, "spell": 2.0, "ammo": 2.0},
    "mobility": {"swap": 4.0, "duel": 1.5},
    "backline_pressure": {"reach": 5.0, "spotlight": 3.0, "spread": 2.5},
    "burst": {"burst": 4.0, "expose": 2.5, "bloodied": 1.5},
    "frontline": {"frontline": 4.5, "protect": 3.0, "stall": 2.5},
    "resource": {"ammo": 4.0, "spell": 2.5, "buff": 1.5, "debuff": 1.5},
}


ARCHETYPE_COUNTERPLAY = {
    "fast_burst": {
        "primary_tank": 10,
        "anti_burst": 9,
        "healer": 7,
        "guard_support": 6,
        "death_insurance": 6,
        "protect": 4,
    },
    "tank_attrition": {
        "frontline_breaker": 9,
        "anti_guard": 8,
        "burst_finisher": 5,
        "stat_manipulator": 4,
        "burn_enabler": 3,
        "debuff": 3,
    },
    "status_control": {
        "healer": 5,
        "anti_burst": 2,
        "sustain": 3,
        "anti_caster": 3,
    },
    "swap_reposition": {
        "root_enabler": 9,
        "anti_swap": 7,
        "taunt": 4,
        "anti_displacement": 4,
        "control_anchor": 3,
    },
    "ultimate_race": {
        "tempo_engine": 7,
        "spell_loop": 6,
        "bonus_action_user": 4,
        "burst_finisher": 3,
        "anti_caster": 3,
    },
    "backline_carry": {
        "backline_reach": 10,
        "spotlight_enabler": 8,
        "expose_enabler": 6,
        "ranged_pressure": 4,
        "magic_carry": 3,
        "reach": 3,
    },
    "spread_pressure": {
        "healer": 6,
        "guard_support": 5,
        "anti_burst": 4,
        "death_insurance": 4,
        "protect": 3,
    },
    "sustain_fortress": {
        "anti_guard": 8,
        "anti_caster": 4,
        "frontline_breaker": 5,
        "burst_finisher": 4,
        "debuff": 3,
    },
    "single_anchor": {
        "backline_reach": 6,
        "spotlight_enabler": 5,
        "swap_engine": 4,
        "burst_finisher": 4,
        "expose_enabler": 4,
    },
    "tempo_disrupt": {
        "reliability": 3,
        "primary_tank": 3,
        "guard_support": 3,
        "tempo": 3,
        "anti_caster": 4,
    },
}


def pair_synergy_value(adventurer_a: str, adventurer_b: str) -> int:
    pair = frozenset((adventurer_a, adventurer_b))
    value = PAIR_SYNERGY.get(pair, 0) + PAIR_TENSION.get(pair, 0)
    if adventurer_a == adventurer_b:
        return value

    profile_a = ADVENTURER_AI[adventurer_a]
    profile_b = ADVENTURER_AI[adventurer_b]
    roles_a = set(profile_a.role_tags)
    roles_b = set(profile_b.role_tags)

    if "shock_engine" in roles_a and "shock_payoff" in roles_b:
        value += 12
    if "shock_engine" in roles_b and "shock_payoff" in roles_a:
        value += 12
    if "root_enabler" in roles_a and ("root_payoff" in roles_b or "backline_reach" in roles_b):
        value += 10
    if "root_enabler" in roles_b and ("root_payoff" in roles_a or "backline_reach" in roles_a):
        value += 10
    if "burn_enabler" in roles_a and "burn_payoff" in roles_b:
        value += 10
    if "burn_enabler" in roles_b and "burn_payoff" in roles_a:
        value += 10
    if "expose_enabler" in roles_a and "burst_finisher" in roles_b:
        value += 10
    if "expose_enabler" in roles_b and "burst_finisher" in roles_a:
        value += 10
    if "primary_tank" in roles_a and "fragile" in roles_b:
        value += 8
    if "primary_tank" in roles_b and "fragile" in roles_a:
        value += 8
    if "healer" in roles_a and "fragile" in roles_b:
        value += 6
    if "healer" in roles_b and "fragile" in roles_a:
        value += 6
    if "swap_engine" in roles_a and "carry_support" in roles_b:
        value += 6
    if "swap_engine" in roles_b and "carry_support" in roles_a:
        value += 6

    frontline_hungry = {"primary_tank", "frontline_ready", "frontline_pivot", "frontline_growth"}
    if len(frontline_hungry & roles_a) >= 2 and len(frontline_hungry & roles_b) >= 2:
        value -= 4
    if "fragile" in roles_a and "fragile" in roles_b and "primary_tank" not in roles_a | roles_b:
        value -= 6
    return value


def matchup_value(profile: AdventurerAIProfile, enemy_profile: AdventurerAIProfile) -> int:
    value = 0
    enemy_tags = set(enemy_profile.matchup_tags) | set(enemy_profile.role_tags)
    for good_tag in profile.good_into:
        for enemy_tag in enemy_tags:
            value += COUNTER_MATRIX.get(good_tag, {}).get(enemy_tag, 0)
    for bad_tag in profile.bad_into:
        if bad_tag in enemy_tags:
            value -= 8
    return value


def team_archetype_bonus(adventurer_ids: tuple[str, ...]) -> tuple[int, tuple[str, ...]]:
    combined_roles: set[str] = set()
    for adventurer_id in adventurer_ids:
        profile = ADVENTURER_AI[adventurer_id]
        combined_roles.update(profile.role_tags)

    bonus = 0
    labels: list[str] = []
    for label, required, value in TEAM_ARCHETYPE_RULES:
        if required.issubset(combined_roles):
            bonus += value
            labels.append(label)
    return bonus, tuple(labels)


def team_style_scores(adventurer_ids: tuple[str, ...]) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    if not adventurer_ids:
        return {}
    reliabilities: list[int] = []
    complexities: list[int] = []
    frontline_hungry = 0
    for adventurer_id in adventurer_ids:
        profile = ADVENTURER_AI[adventurer_id]
        roles = set(profile.role_tags)
        shells = set(profile.shell_tags)
        matchup = set(profile.matchup_tags)
        reliabilities.append(profile.reliability)
        complexities.append(profile.complexity)
        scores["pressure"] += profile.base_power * 0.12
        if {"primary_tank", "frontline_ready", "frontline_pivot", "frontline_growth", "bruiser"} & roles:
            frontline_hungry += 1
        for style_name, weights in STYLE_ROLE_WEIGHTS.items():
            for tag, value in weights.items():
                if tag in roles:
                    scores[style_name] += value
        for style_name, weights in STYLE_SHELL_WEIGHTS.items():
            for tag, value in weights.items():
                if tag in shells or tag in matchup:
                    scores[style_name] += value
        if "fragile_backline" in matchup:
            scores["backline_pressure"] += 1.5
        if "slow_frontline" in matchup:
            scores["burst"] += 1.0
            scores["control"] += 1.0
        if "spell_heavy" in matchup:
            scores["control"] += 1.5
        if "attrition" in matchup:
            scores["sustain"] += 1.5
    scores["reliability"] = sum(reliabilities) / len(reliabilities)
    scores["complexity"] = sum(complexities) / len(complexities)
    scores["frontline_hungry"] = float(frontline_hungry)
    return dict(scores)


def enemy_archetypes(adventurer_ids: tuple[str, ...]) -> tuple[str, ...]:
    if not adventurer_ids:
        return ()
    styles = team_style_scores(adventurer_ids)
    combined_roles: set[str] = set()
    combined_shells: set[str] = set()
    for adventurer_id in adventurer_ids:
        profile = ADVENTURER_AI[adventurer_id]
        combined_roles.update(profile.role_tags)
        combined_shells.update(profile.shell_tags)

    archetypes: list[str] = []
    if styles.get("burst", 0.0) >= 16.0 and (styles.get("tempo", 0.0) >= 10.0 or styles.get("backline_pressure", 0.0) >= 11.0):
        archetypes.append("fast_burst")
    if styles.get("frontline", 0.0) >= 18.0 and styles.get("sustain", 0.0) >= 10.0:
        archetypes.append("tank_attrition")
    if styles.get("control", 0.0) >= 16.0 or len({"burn", "root", "shock"} & combined_shells) >= 2:
        archetypes.append("status_control")
    if styles.get("mobility", 0.0) >= 13.0 or "swap" in combined_shells or "swap_engine" in combined_roles:
        archetypes.append("swap_reposition")
    if styles.get("ultimate", 0.0) >= 12.0:
        archetypes.append("ultimate_race")
    if styles.get("backline_pressure", 0.0) >= 16.0 and styles.get("fragility", 0.0) >= 8.0:
        archetypes.append("backline_carry")
    if styles.get("spread", 0.0) >= 10.0:
        archetypes.append("spread_pressure")
    if styles.get("sustain", 0.0) >= 18.0 and styles.get("frontline", 0.0) >= 12.0:
        archetypes.append("sustain_fortress")
    if "primary_tank" in combined_roles and styles.get("backline_pressure", 0.0) >= 10.0:
        archetypes.append("single_anchor")
    if styles.get("tempo", 0.0) >= 14.0 or styles.get("resource", 0.0) >= 12.0:
        archetypes.append("tempo_disrupt")
    if not archetypes:
        if styles.get("control", 0.0) >= styles.get("burst", 0.0):
            archetypes.append("status_control")
        else:
            archetypes.append("fast_burst")
    return tuple(dict.fromkeys(archetypes))


def counterplay_score(adventurer_ids: tuple[str, ...], enemy_ids: tuple[str, ...]) -> int:
    if not adventurer_ids or not enemy_ids:
        return 0
    own_tags: set[str] = set()
    for adventurer_id in adventurer_ids:
        profile = ADVENTURER_AI[adventurer_id]
        own_tags.update(profile.role_tags)
        own_tags.update(profile.shell_tags)
        own_tags.update(profile.matchup_tags)
        own_tags.add("reliability")
        if "tempo_engine" in profile.role_tags or "bonus_action_user" in profile.role_tags:
            own_tags.add("tempo")
    value = 0
    for archetype in enemy_archetypes(enemy_ids):
        for tag in own_tags:
            value += ARCHETYPE_COUNTERPLAY.get(archetype, {}).get(tag, 0)
    return value


def counter_fragility_penalty(adventurer_ids: tuple[str, ...], enemy_ids: tuple[str, ...]) -> float:
    if not adventurer_ids or not enemy_ids:
        return 0.0
    styles = team_style_scores(adventurer_ids)
    penalty = 0.0
    for archetype in enemy_archetypes(enemy_ids):
        if archetype == "fast_burst":
            pressure_gap = styles.get("fragility", 0.0) - (styles.get("frontline", 0.0) + styles.get("sustain", 0.0) * 0.65)
            penalty += max(0.0, pressure_gap) * 0.45
        elif archetype == "status_control":
            if styles.get("sustain", 0.0) < 10.0:
                penalty += 4.0
        elif archetype in {"tank_attrition", "sustain_fortress"}:
            if styles.get("burst", 0.0) + styles.get("control", 0.0) < 18.0:
                penalty += 6.0
        elif archetype == "backline_carry":
            if styles.get("backline_pressure", 0.0) < 10.0:
                penalty += 6.0
        elif archetype == "tempo_disrupt":
            if styles.get("reliability", 0.0) < 72.0:
                penalty += 4.0
    return penalty


def plan_reliability_score(adventurer_ids: tuple[str, ...]) -> float:
    if not adventurer_ids:
        return 0.0
    styles = team_style_scores(adventurer_ids)
    value = (styles.get("reliability", 0.0) - 60.0) * 0.28
    value -= max(0.0, styles.get("complexity", 0.0) - 72.0) * 0.16
    if styles.get("frontline", 0.0) >= 12.0:
        value += 6.0
    else:
        value -= 10.0
    if styles.get("backline_pressure", 0.0) >= 8.0:
        value += 4.0
    else:
        value -= 6.0
    if styles.get("burst", 0.0) >= 8.0 or styles.get("control", 0.0) >= 10.0:
        value += 4.0
    else:
        value -= 7.0
    if styles.get("sustain", 0.0) >= 8.0:
        value += 4.0
    if styles.get("fragility", 0.0) > styles.get("frontline", 0.0) + styles.get("sustain", 0.0):
        value -= (styles.get("fragility", 0.0) - (styles.get("frontline", 0.0) + styles.get("sustain", 0.0))) * 0.35
    if styles.get("frontline_hungry", 0.0) >= 2 and styles.get("frontline", 0.0) < 18.0:
        value -= 4.0
    return value
