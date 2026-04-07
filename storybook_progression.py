from __future__ import annotations

from dataclasses import dataclass


def exp_to_next_level(level: int) -> int:
    """EXP required to advance from `level` to `level + 1`. Formula: level × 100."""
    return max(1, int(level)) * 100


@dataclass(frozen=True)
class LevelState:
    level: int
    total_exp: int
    current_level_exp: int
    next_level_exp: int


@dataclass(frozen=True)
class ExpAward:
    old_level: int
    new_level: int
    total_exp: int
    level_up_gold: int
    levels_gained: tuple[int, ...]


def level_state(total_exp: int) -> LevelState:
    remaining = max(0, int(total_exp))
    level = 1
    while True:
        needed = exp_to_next_level(level)
        if remaining < needed:
            return LevelState(
                level=level,
                total_exp=max(0, int(total_exp)),
                current_level_exp=remaining,
                next_level_exp=needed,
            )
        remaining -= needed
        level += 1


def level_for_exp(total_exp: int) -> int:
    return level_state(total_exp).level


def level_up_gold(level_reached: int) -> int:
    """Gold awarded upon reaching a new level. Formula: 50 + (10 × new_level)."""
    return 50 + (10 * max(1, int(level_reached)))


def award_exp(total_exp: int, gained_exp: int) -> ExpAward:
    old_state = level_state(total_exp)
    new_total = max(0, int(total_exp) + max(0, int(gained_exp)))
    new_state = level_state(new_total)
    levels_gained = tuple(range(old_state.level + 1, new_state.level + 1))
    return ExpAward(
        old_level=old_state.level,
        new_level=new_state.level,
        total_exp=new_total,
        level_up_gold=sum(level_up_gold(level) for level in levels_gained),
        levels_gained=levels_gained,
    )
