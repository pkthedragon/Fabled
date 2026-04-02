from __future__ import annotations

from dataclasses import dataclass
import math
import random


STARTING_GLORY = 500
MIN_GLORY = 0
MAX_GLORY = 2000
PROVISIONAL_MATCHES = 20

RANKS = (
    ("Squire", 0),
    ("Knight", 200),
    ("Baron", 400),
    ("Viscount", 600),
    ("Earl", 800),
    ("Margrave", 1000),
    ("Duke", 1200),
    ("Prince", 1400),
    ("King", 1600),
    ("Emperor", 1800),
)

STREAK_BONUS = {
    0: 0,
    1: 20,
    2: 45,
    3: 75,
    4: 110,
    5: 150,
}


@dataclass(frozen=True)
class MatchmakingProfile:
    glory: int
    run_wins: int
    run_losses: int
    avg_opponent_glory: int = 0

    @property
    def emr(self) -> int:
        return effective_matchmaking_rating(
            self.glory,
            self.run_wins,
            self.run_losses,
            self.avg_opponent_glory,
        )


def clamp_glory(glory: float | int) -> int:
    return max(MIN_GLORY, min(MAX_GLORY, int(round(glory))))


def ensure_storybook_glory(current_glory: int, games_played: int) -> int:
    if games_played <= 0 and current_glory in {0, 1000}:
        return STARTING_GLORY
    return clamp_glory(current_glory)


def rank_name(glory: int) -> str:
    glory = clamp_glory(glory)
    current = RANKS[0][0]
    for name, threshold in RANKS:
        if glory >= threshold:
            current = name
    return current


def streak_bonus(run_wins: int) -> int:
    return STREAK_BONUS.get(run_wins, 190 if run_wins >= 6 else 0)


def quality_bonus(account_glory: int, avg_opponent_glory: int) -> int:
    if avg_opponent_glory <= 0:
        return 0
    raw = round((avg_opponent_glory - account_glory) / 4)
    return max(-20, min(40, raw))


def effective_matchmaking_rating(
    account_glory: int,
    run_wins: int,
    run_losses: int,
    avg_opponent_glory: int = 0,
) -> int:
    rating = (
        account_glory
        + streak_bonus(run_wins)
        - (15 * max(0, run_losses))
        + quality_bonus(account_glory, avg_opponent_glory)
    )
    return clamp_glory(rating)


def expected_score(player_glory: int, opponent_glory: int) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (opponent_glory - player_glory) / 400.0))


def k_factor(glory: int, matches_played: int) -> int:
    if matches_played < PROVISIONAL_MATCHES:
        return 32
    if glory >= 1700:
        return 20
    return 24


def run_depth_multiplier(run_wins: int) -> float:
    if run_wins <= 1:
        return 1.0
    if run_wins <= 3:
        return 1.05
    if run_wins <= 5:
        return 1.10
    return 1.15


def update_glory_after_match(
    player_glory: int,
    opponent_glory: int,
    *,
    did_win: bool,
    matches_played: int,
    run_wins_before_match: int,
) -> tuple[int, int]:
    expected = expected_score(player_glory, opponent_glory)
    result = 1.0 if did_win else 0.0
    base_delta = k_factor(player_glory, matches_played) * (result - expected)
    final_delta = round(base_delta * run_depth_multiplier(run_wins_before_match))
    return clamp_glory(player_glory + final_delta), final_delta


def match_quality_score(
    a_glory: int,
    a_run_wins: int,
    a_run_losses: int,
    b_glory: int,
    b_run_wins: int,
    b_run_losses: int,
    *,
    a_avg_glory: int = 0,
    b_avg_glory: int = 0,
) -> float:
    a_emr = effective_matchmaking_rating(a_glory, a_run_wins, a_run_losses, a_avg_glory)
    b_emr = effective_matchmaking_rating(b_glory, b_run_wins, b_run_losses, b_avg_glory)
    return 100.0 - abs(a_emr - b_emr) - (10.0 * abs(a_run_wins - b_run_wins)) - (8.0 * abs(a_run_losses - b_run_losses))


def _preferred_win_bucket(run_wins: int) -> range:
    if run_wins <= 1:
        return range(0, 3)
    if run_wins <= 3:
        return range(1, 5)
    if run_wins <= 5:
        return range(3, 7)
    return range(5, 9)


def _preferred_loss_bucket(run_losses: int) -> range:
    if run_losses <= 0:
        return range(0, 2)
    if run_losses == 1:
        return range(0, 3)
    return range(1, 3)


def find_ai_match_profile(
    account_glory: int,
    run_wins: int,
    run_losses: int,
    *,
    avg_opponent_glory: int = 0,
    rng: random.Random | None = None,
) -> MatchmakingProfile:
    rng = rng or random.Random()
    player_emr = effective_matchmaking_rating(account_glory, run_wins, run_losses, avg_opponent_glory)
    win_bucket = list(_preferred_win_bucket(run_wins))
    loss_bucket = list(_preferred_loss_bucket(run_losses))
    candidates: list[MatchmakingProfile] = []
    for delta in range(-250, 251, 25):
        glory = clamp_glory(player_emr + delta)
        for opponent_wins in win_bucket:
            for opponent_losses in loss_bucket:
                candidates.append(
                    MatchmakingProfile(
                        glory=glory,
                        run_wins=opponent_wins,
                        run_losses=opponent_losses,
                        avg_opponent_glory=glory,
                    )
                )
    for window in (50, 100, 150, 200, 250):
        in_window = [
            candidate
            for candidate in candidates
            if abs(candidate.emr - player_emr) <= window
        ]
        if not in_window:
            continue
        in_window.sort(
            key=lambda candidate: match_quality_score(
                account_glory,
                run_wins,
                run_losses,
                candidate.glory,
                candidate.run_wins,
                candidate.run_losses,
                a_avg_glory=avg_opponent_glory,
                b_avg_glory=candidate.avg_opponent_glory,
            ),
            reverse=True,
        )
        top_band = in_window[: min(3, len(in_window))]
        return rng.choice(top_band)
    return MatchmakingProfile(glory=player_emr, run_wins=run_wins, run_losses=run_losses, avg_opponent_glory=player_emr)


def ai_difficulty_for_glory(glory: int) -> str:
    if glory < 350:
        return "easy"
    if glory < 850:
        return "normal"
    if glory < 1450:
        return "hard"
    return "ranked"


def target_team_score_for_glory(glory: int) -> float:
    glory = clamp_glory(glory)
    return 635.0 + (glory / 2000.0) * 120.0


def pressure_label(player_glory: int, run_wins: int, run_losses: int, avg_opponent_glory: int = 0) -> str:
    emr = effective_matchmaking_rating(player_glory, run_wins, run_losses, avg_opponent_glory)
    if emr >= 1500:
        return "Elite"
    if emr >= 1000:
        return "High"
    if emr >= 700:
        return "Rising"
    return "Steady"
