from __future__ import annotations

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
