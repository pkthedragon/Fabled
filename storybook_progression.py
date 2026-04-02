from __future__ import annotations

from dataclasses import dataclass


MAX_LEVEL = 20
QUEST_WIN_EXP = 25
BOUT_WIN_EXP = 35
ARTIFACT_PURCHASE_EXP = 15
BOUT_WIN_GOLD = 150

LEVEL_EXP_REQUIREMENTS = {
    1: 100,
    2: 120,
    3: 140,
    4: 160,
    5: 180,
    6: 200,
    7: 220,
    8: 240,
    9: 260,
    10: 280,
    11: 300,
    12: 320,
    13: 340,
    14: 360,
    15: 380,
    16: 400,
    17: 420,
    18: 440,
    19: 460,
}


@dataclass(frozen=True)
class LevelState:
    level: int
    total_exp: int
    current_level_exp: int
    next_level_exp: int

    @property
    def at_cap(self) -> bool:
        return self.level >= MAX_LEVEL


@dataclass(frozen=True)
class ExpAward:
    old_level: int
    new_level: int
    total_exp: int
    level_up_gold: int
    levels_gained: tuple[int, ...]


def exp_to_next_level(level: int) -> int:
    return LEVEL_EXP_REQUIREMENTS.get(level, 0)


def level_state(total_exp: int) -> LevelState:
    remaining = max(0, int(total_exp))
    level = 1
    while level < MAX_LEVEL:
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
    return LevelState(
        level=MAX_LEVEL,
        total_exp=max(0, int(total_exp)),
        current_level_exp=0,
        next_level_exp=0,
    )


def level_for_exp(total_exp: int) -> int:
    return level_state(total_exp).level


def level_up_gold(level_reached: int) -> int:
    return 500 if level_reached % 5 == 0 else 100


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


def quest_win_gold(run_wins_before_match: int) -> int:
    return 100 + (10 * max(0, int(run_wins_before_match)))
