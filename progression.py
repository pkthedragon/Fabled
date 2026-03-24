from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


CLASS_POINT_THRESHOLDS = {
    1: 0,
    2: 2,
    3: 4,
    4: 7,
    5: 10,
}

RANK_BANDS: List[Tuple[str, int, int]] = [
    ("Squire", 0, 199),
    ("Knight", 200, 399),
    ("Baron", 400, 599),
    ("Viscount", 600, 799),
    ("Earl", 800, 999),
    ("Margrave", 1000, 1199),
    ("Duke", 1200, 1399),
    ("Prince", 1400, 1599),
    ("King", 1600, 1799),
    ("Emperor", 1800, 2000),
]


def exp_to_next_level(level: int) -> int:
    level = max(1, int(level))
    return 50 * level + 50


def total_exp_for_level(level: int) -> int:
    level = max(1, int(level))
    total = 0
    for current in range(1, level):
        total += exp_to_next_level(current)
    return total


def player_level_from_exp(exp: int) -> int:
    exp = max(0, int(exp))
    level = 1
    while exp >= total_exp_for_level(level + 1):
        level += 1
    return level


def saved_team_slot_count(player_level: int) -> int:
    player_level = max(1, int(player_level))
    return 1 + max(0, (player_level - 1) // 2)


def voucher_count_for_level(player_level: int) -> int:
    player_level = max(1, int(player_level))
    return player_level // 5


def adventurer_level_from_clears(clears: int) -> int:
    return max(1, 1 + int(clears))


def unlocked_signature_count(adventurer_level: int) -> int:
    return min(3, max(1, int(adventurer_level)))


def twist_unlocked(adventurer_level: int) -> bool:
    return int(adventurer_level) >= 4


def adventurer_sigil_unlocked(adventurer_level: int) -> bool:
    return int(adventurer_level) >= 5


def class_level_from_points(points: int) -> int:
    points = max(0, int(points))
    level = 1
    for candidate, threshold in sorted(CLASS_POINT_THRESHOLDS.items()):
        if points >= threshold:
            level = candidate
    return level


def class_basics_unlocked_count(class_level: int) -> int:
    class_level = max(1, int(class_level))
    return min(5, 2 + max(0, class_level - 1))


def class_sigil_unlocked(class_level: int) -> bool:
    return int(class_level) >= 5


def player_sigil_unlocked(player_level: int) -> bool:
    return int(player_level) >= 10


def rank_name_from_rating(rating: int) -> str:
    rating = max(0, min(2000, int(rating)))
    for name, low, high in RANK_BANDS:
        if low <= rating <= high:
            return name
    return RANK_BANDS[-1][0]


def expected_score(your_rating: int, opp_rating: int) -> float:
    diff = (int(opp_rating) - int(your_rating)) / 400.0
    return 1.0 / (1.0 + (10 ** diff))


def ranked_k_value(rating: int, games_played: int) -> int:
    if int(games_played) < 10:
        return 64
    if int(rating) < 1400:
        return 32
    return 24


def apply_ranked_result(rating: int, games_played: int, opp_rating: int, won: bool) -> Tuple[int, int]:
    rating = max(0, min(2000, int(rating)))
    games_played = max(0, int(games_played))
    score = 1 if won else 0
    expected = expected_score(rating, opp_rating)
    k_value = ranked_k_value(rating, games_played)
    new_rating = round(rating + k_value * (score - expected))
    return max(0, min(2000, new_rating)), games_played + 1


def all_class_sigils_unlocked(class_points: Dict[str, int], class_names: Iterable[str]) -> bool:
    for class_name in class_names:
        if not class_sigil_unlocked(class_level_from_points(class_points.get(class_name, 0))):
            return False
    return True


def all_adventurer_sigils_unlocked(adventurer_clears: Dict[str, int], adventurer_ids: Iterable[str]) -> bool:
    for adventurer_id in adventurer_ids:
        if not adventurer_sigil_unlocked(adventurer_level_from_clears(adventurer_clears.get(adventurer_id, 0))):
            return False
    return True
