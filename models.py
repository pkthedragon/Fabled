from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class QuestRunState:
    """Tracks the state of a single active quest run (persists across encounters)."""
    active: bool = False
    quest_id: str | None = None
    wins: int = 0
    losses: int = 0
    current_win_streak: int = 0
    current_loss_streak: int = 0
    opponent_reputations: List[int] = field(default_factory=list)
    team: List[dict] | None = None
    party_id: str | None = None
    match_count: int = 0
    total_gold_earned: int = 0
    # Artifact pool: artifacts available to the party for this run (unequipped)
    artifact_pool: List[str] = field(default_factory=list)
    reputation_gain_total: int = 0
    is_successful: bool = False


@dataclass
class BoutRunState:
    """Tracks the state of a best-of-three bout."""
    active: bool = False
    mode: str = "random"
    player_wins: int = 0
    opponent_wins: int = 0
    match_count: int = 0
    team: List[dict] | None = None
    opponent_reputation: int = 300
    gold_earned: int = 0


@dataclass
class EmployeeState:
    """Tracks active employee skill assignments and daily server state."""
    assistant_skill: str = ""
    bartender_skill: str = ""
    server_skill: str = ""
    server_daily_favorite: str | None = None
    server_favorite_date: str | None = None


@dataclass
class CampaignProfile:
    """Tracks local account progression and storybook state."""

    recruited: Set[str] = field(default_factory=set)
    sig_tier: int = 1
    basics_tier: int = 2
    unlocked_classes: Set[str] = field(default_factory=set)
    unlocked_items: Set[str] = field(default_factory=set)
    default_sigs: Dict[str, str] = field(default_factory=dict)
    twists_unlocked: bool = False
    quest_cleared: Dict[int, bool] = field(default_factory=dict)
    highest_quest_cleared: int = 0
    campaign_complete: bool = False
    tutorial_seen: Set[str] = field(default_factory=set)
    tutorials_enabled: bool = True
    saved_teams: List[dict] = field(default_factory=list)
    fast_resolution: bool = False
    battle_log_popups: bool = True
    screen_shake: bool = True
    new_unlocks: Set[str] = field(default_factory=set)
    player_exp: int = 0
    gold: int = 0
    guild_vouchers: int = 0
    brighthollow_renown: int = 500
    reputation: int = 300
    ranked_games_played: int = 0
    season_high_reputation: int = 300
    ranked_total_wins: int = 0
    ranked_total_losses: int = 0
    ranked_best_quest_wins: int = 0
    ranked_current_quest_id: str | None = None
    ranked_season_id: int = 1
    floor_reputation: int = 200
    non_tutorial_quests_completed: int = 0
    adventurer_quest_clears: Dict[str, int] = field(default_factory=dict)
    class_points: Dict[str, int] = field(default_factory=dict)
    tutorial_complete: bool = False
    quick_play_unlocked: bool = False
    premium_dollars_spent: int = 0
    storybook_friends: List[Dict[str, str]] = field(default_factory=list)
    storybook_weapon_unlocks: Set[str] = field(default_factory=set)
    storybook_adventurer_unlocks: Set[str] = field(default_factory=set)
    storybook_cosmetic_unlocks: Set[str] = field(default_factory=set)
    storybook_equipped_outfit: str = ""
    storybook_equipped_chair: str = ""
    storybook_equipped_emote: str = ""
    storybook_equipped_adventurer_skins: Dict[str, str] = field(default_factory=dict)
    storybook_quested_adventurers: Set[str] = field(default_factory=lambda: {"little_jack"})
    storybook_favorite_adventurer: str = "little_jack"
    storybook_training_favorite_adventurer: str = "little_jack"
    assistant_skill: str = ""
    bartender_skill: str = ""
    server_skill: str = ""
    server_daily_favorite: str | None = None
    server_favorite_date: str | None = None
