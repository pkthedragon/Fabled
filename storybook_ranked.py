from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
import random


STARTING_REPUTATION = 300
MIN_REPUTATION = 1
MAX_REPUTATION = 2000

RANKS = (
    ("Squire", 1),
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
RANK_INDEX = {name: index for index, (name, _threshold) in enumerate(RANKS)}


@dataclass(frozen=True)
class MatchmakingProfile:
    reputation: int
    run_wins: int
    run_losses: int

    @property
    def emr(self) -> int:
        return get_match_rating(
            self.reputation,
            self.run_wins,
            self.run_losses,
        )


def clamp_reputation(reputation: float | int) -> int:
    return max(MIN_REPUTATION, min(MAX_REPUTATION, int(round(reputation))))


def ensure_storybook_reputation(current_reputation: int, games_played: int) -> int:
    if games_played <= 0 and current_reputation in {0, 500, 1000}:
        return STARTING_REPUTATION
    return clamp_reputation(current_reputation)


def get_rank_from_reputation(reputation: int) -> str:
    reputation = clamp_reputation(reputation)
    if reputation < 200:
        return "Squire"
    if reputation < 400:
        return "Knight"
    if reputation < 600:
        return "Baron"
    if reputation < 800:
        return "Viscount"
    if reputation < 1000:
        return "Earl"
    if reputation < 1200:
        return "Margrave"
    if reputation < 1400:
        return "Duke"
    if reputation < 1600:
        return "Prince"
    if reputation < 1800:
        return "King"
    return "Emperor"


def rank_name(reputation: int) -> str:
    return get_rank_from_reputation(reputation)


def rank_floor_for_reputation(reputation: int) -> int:
    rank = get_rank_from_reputation(reputation)
    for name, threshold in RANKS:
        if name == rank:
            return threshold
    return MIN_REPUTATION


def protected_rank_name(reputation: int, previous_rank: str | None = None) -> str:
    natural = get_rank_from_reputation(reputation)
    if previous_rank not in RANK_INDEX:
        return natural
    return previous_rank if RANK_INDEX[natural] < RANK_INDEX[previous_rank] else natural


def get_expected_score(player_reputation: int, opponent_reputation: int) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (opponent_reputation - player_reputation) / 400.0))


def get_match_rating(reputation: int, current_win_streak: int, current_loss_streak: int) -> int:
    return int(reputation + (max(0, int(current_win_streak)) * 20) - (max(0, int(current_loss_streak)) * 15))


def get_reputation_delta(
    player_reputation: int,
    opponent_reputation: int,
    *,
    did_win: bool,
    current_win_streak_before_match: int,
    current_loss_streak_before_match: int,
) -> int:
    k_factor = 28
    expected = get_expected_score(player_reputation, opponent_reputation)
    actual = 1.0 if did_win else 0.0
    base_change = k_factor * (actual - expected)
    if did_win:
        win_bonus = min(max(0, int(current_win_streak_before_match)), 5) * 2
        delta = round(base_change + win_bonus)
        return max(8, min(30, delta))
    # Flat -10 Reputation per loss.
    return -10


def update_reputation_after_match(
    player_reputation: int,
    opponent_reputation: int,
    *,
    did_win: bool,
    current_win_streak_before_match: int,
    current_loss_streak_before_match: int,
    floor_reputation: int = MIN_REPUTATION,
) -> tuple[int, int]:
    delta = get_reputation_delta(
        player_reputation,
        opponent_reputation,
        did_win=did_win,
        current_win_streak_before_match=current_win_streak_before_match,
        current_loss_streak_before_match=current_loss_streak_before_match,
    )
    new_reputation = clamp_reputation(player_reputation + delta)
    new_reputation = max(min(MAX_REPUTATION, int(floor_reputation)), new_reputation)
    return new_reputation, delta


def _saved_games_dir() -> str:
    home = os.path.expanduser("~")
    saved_games = os.path.join(home, "Saved Games", "Fabled")
    os.makedirs(saved_games, exist_ok=True)
    return saved_games


def log_quest_ai_match(payload: dict) -> None:
    path = os.path.join(_saved_games_dir(), "quest_ai_reputation_log.jsonl")
    record = dict(payload)
    record["timestamp"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def effective_matchmaking_rating(
    account_reputation: int,
    run_wins: int,
    run_losses: int,
    avg_opponent_reputation: int = 0,
) -> int:
    _ = avg_opponent_reputation
    return get_match_rating(account_reputation, run_wins, run_losses)


def match_quality_score(
    a_reputation: int,
    a_run_wins: int,
    a_run_losses: int,
    b_reputation: int,
    b_run_wins: int,
    b_run_losses: int,
    *,
    a_avg_reputation: int = 0,
    b_avg_reputation: int = 0,
) -> float:
    _ = (a_avg_reputation, b_avg_reputation)
    a_emr = get_match_rating(a_reputation, a_run_wins, a_run_losses)
    b_emr = get_match_rating(b_reputation, b_run_wins, b_run_losses)
    return (
        1000.0
        - abs(a_emr - b_emr) * 3.0
        - abs(a_reputation - b_reputation) * 1.5
        - abs(a_run_wins - b_run_wins) * 12.0
        - abs(a_run_losses - b_run_losses) * 10.0
    )


def _preferred_win_bucket(run_wins: int) -> range:
    base = max(0, int(run_wins))
    return range(max(0, base - 2), min(20, base + 3))


def _preferred_loss_bucket(run_losses: int) -> range:
    base = max(0, int(run_losses))
    return range(max(0, base - 1), min(3, base + 2))


def find_ai_match_profile(
    account_reputation: int,
    run_wins: int,
    run_losses: int,
    *,
    avg_opponent_reputation: int = 0,
    rng: random.Random | None = None,
) -> MatchmakingProfile:
    rng = rng or random.Random()
    player_emr = get_match_rating(account_reputation, run_wins, run_losses)
    win_bucket = list(_preferred_win_bucket(run_wins))
    loss_bucket = list(_preferred_loss_bucket(run_losses))
    candidates: list[MatchmakingProfile] = []
    for delta in range(-250, 251, 25):
        reputation = clamp_reputation(player_emr + delta)
        for opponent_wins in win_bucket:
            for opponent_losses in loss_bucket:
                candidates.append(
                    MatchmakingProfile(
                        reputation=reputation,
                        run_wins=opponent_wins,
                        run_losses=opponent_losses,
                    )
                )
    for window in (50, 100, 150, 200, 250):
        in_window = [
            candidate
            for candidate in candidates
            if abs(candidate.emr - player_emr) <= window
        ]
        # Anti-stomp protection:
        # avoid very shallow-run players into very deep-run opponents unless window is very wide.
        if run_wins <= 1 and window < 250:
            in_window = [candidate for candidate in in_window if candidate.run_wins < 7]
        if not in_window:
            continue
        in_window.sort(
            key=lambda candidate: match_quality_score(
                account_reputation,
                run_wins,
                run_losses,
                candidate.reputation,
                candidate.run_wins,
                candidate.run_losses,
            ),
            reverse=True,
        )
        top_band = in_window[: min(3, len(in_window))]
        return rng.choice(top_band)
    return MatchmakingProfile(reputation=player_emr, run_wins=run_wins, run_losses=run_losses)


def ai_difficulty_for_reputation(reputation: int) -> str:
    if reputation < 450:
        return "easy"
    if reputation < 900:
        return "normal"
    if reputation < 1500:
        return "hard"
    return "ranked"


def target_team_score_for_reputation(reputation: int) -> float:
    reputation = clamp_reputation(reputation)
    return 635.0 + (reputation / 2000.0) * 120.0


def pressure_label(player_reputation: int, run_wins: int, run_losses: int, avg_opponent_reputation: int = 0) -> str:
    _ = avg_opponent_reputation
    emr = get_match_rating(player_reputation, run_wins, run_losses)
    if emr >= 1500:
        return "Elite"
    if emr >= 1000:
        return "High"
    if emr >= 700:
        return "Rising"
    return "Steady"
