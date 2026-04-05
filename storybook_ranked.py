from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
import random


STARTING_GLORY = 300
MIN_GLORY = 1
MAX_GLORY = 2000

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
    glory: int
    run_wins: int
    run_losses: int

    @property
    def emr(self) -> int:
        return get_match_rating(
            self.glory,
            self.run_wins,
            self.run_losses,
        )


def clamp_glory(glory: float | int) -> int:
    return max(MIN_GLORY, min(MAX_GLORY, int(round(glory))))


def ensure_storybook_glory(current_glory: int, games_played: int) -> int:
    if games_played <= 0 and current_glory in {0, 500, 1000}:
        return STARTING_GLORY
    return clamp_glory(current_glory)


def get_rank_from_glory(glory: int) -> str:
    glory = clamp_glory(glory)
    if glory < 200:
        return "Squire"
    if glory < 400:
        return "Knight"
    if glory < 600:
        return "Baron"
    if glory < 800:
        return "Viscount"
    if glory < 1000:
        return "Earl"
    if glory < 1200:
        return "Margrave"
    if glory < 1400:
        return "Duke"
    if glory < 1600:
        return "Prince"
    if glory < 1800:
        return "King"
    return "Emperor"


def rank_name(glory: int) -> str:
    return get_rank_from_glory(glory)


def rank_floor_for_glory(glory: int) -> int:
    rank = get_rank_from_glory(glory)
    for name, threshold in RANKS:
        if name == rank:
            return threshold
    return MIN_GLORY


def protected_rank_name(glory: int, previous_rank: str | None = None) -> str:
    natural = get_rank_from_glory(glory)
    if previous_rank not in RANK_INDEX:
        return natural
    return previous_rank if RANK_INDEX[natural] < RANK_INDEX[previous_rank] else natural


def get_encounter_gold(current_win_streak_before_win: int) -> int:
    streak_bonus = max(0, int(current_win_streak_before_win)) * 10
    return 100 + streak_bonus


def get_expected_score(player_glory: int, opponent_glory: int) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (opponent_glory - player_glory) / 400.0))


def get_match_rating(glory: int, current_win_streak: int, current_loss_streak: int) -> int:
    return int(glory + (max(0, int(current_win_streak)) * 20) - (max(0, int(current_loss_streak)) * 15))


def get_glory_delta(
    player_glory: int,
    opponent_glory: int,
    *,
    did_win: bool,
    current_win_streak_before_match: int,
    current_loss_streak_before_match: int,
) -> int:
    k_factor = 28
    expected = get_expected_score(player_glory, opponent_glory)
    actual = 1.0 if did_win else 0.0
    base_change = k_factor * (actual - expected)
    if did_win:
        win_bonus = min(max(0, int(current_win_streak_before_match)), 5) * 2
        delta = round(base_change + win_bonus)
        return max(8, min(30, delta))
    # Rulebook quest loss formula: 10 x current lossstreak after loss.
    return -10 * max(0, int(current_loss_streak_before_match) + 1)


def update_glory_after_match(
    player_glory: int,
    opponent_glory: int,
    *,
    did_win: bool,
    current_win_streak_before_match: int,
    current_loss_streak_before_match: int,
    floor_glory: int = MIN_GLORY,
) -> tuple[int, int]:
    delta = get_glory_delta(
        player_glory,
        opponent_glory,
        did_win=did_win,
        current_win_streak_before_match=current_win_streak_before_match,
        current_loss_streak_before_match=current_loss_streak_before_match,
    )
    new_glory = clamp_glory(player_glory + delta)
    new_glory = max(min(MAX_GLORY, int(floor_glory)), new_glory)
    return new_glory, delta


def _saved_games_dir() -> str:
    home = os.path.expanduser("~")
    saved_games = os.path.join(home, "Saved Games", "Fabled")
    os.makedirs(saved_games, exist_ok=True)
    return saved_games


def log_quest_ai_match(payload: dict) -> None:
    path = os.path.join(_saved_games_dir(), "quest_ai_glory_log.jsonl")
    record = dict(payload)
    record["timestamp"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def effective_matchmaking_rating(
    account_glory: int,
    run_wins: int,
    run_losses: int,
    avg_opponent_glory: int = 0,
) -> int:
    # avg_opponent_glory kept for backward compatibility with older callsites.
    _ = avg_opponent_glory
    return get_match_rating(account_glory, run_wins, run_losses)


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
    _ = (a_avg_glory, b_avg_glory)
    a_emr = get_match_rating(a_glory, a_run_wins, a_run_losses)
    b_emr = get_match_rating(b_glory, b_run_wins, b_run_losses)
    return (
        1000.0
        - abs(a_emr - b_emr) * 3.0
        - abs(a_glory - b_glory) * 1.5
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
    account_glory: int,
    run_wins: int,
    run_losses: int,
    *,
    avg_opponent_glory: int = 0,
    rng: random.Random | None = None,
) -> MatchmakingProfile:
    rng = rng or random.Random()
    player_emr = get_match_rating(account_glory, run_wins, run_losses)
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
                account_glory,
                run_wins,
                run_losses,
                candidate.glory,
                candidate.run_wins,
                candidate.run_losses,
            ),
            reverse=True,
        )
        top_band = in_window[: min(3, len(in_window))]
        return rng.choice(top_band)
    return MatchmakingProfile(glory=player_emr, run_wins=run_wins, run_losses=run_losses)


def ai_difficulty_for_glory(glory: int) -> str:
    if glory < 450:
        return "easy"
    if glory < 900:
        return "normal"
    if glory < 1500:
        return "hard"
    return "ranked"


def target_team_score_for_glory(glory: int) -> float:
    glory = clamp_glory(glory)
    return 635.0 + (glory / 2000.0) * 120.0


def pressure_label(player_glory: int, run_wins: int, run_losses: int, avg_opponent_glory: int = 0) -> str:
    _ = avg_opponent_glory
    emr = get_match_rating(player_glory, run_wins, run_losses)
    if emr >= 1500:
        return "Elite"
    if emr >= 1000:
        return "High"
    if emr >= 700:
        return "Rising"
    return "Steady"
