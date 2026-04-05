from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class CampaignProfile:
    """Tracks local account progression and storybook state."""

    recruited: Set[str] = field(default_factory=lambda: {
        "red_blanchette", "robin_hooded_avenger", "sir_roland"
    })
    sig_tier: int = 1
    basics_tier: int = 2
    unlocked_classes: Set[str] = field(default_factory=lambda: {
        "Fighter", "Ranger", "Warden"
    })
    unlocked_items: Set[str] = field(default_factory=set)
    unlocked_artifacts: Set[str] = field(default_factory=set)
    default_sigs: Dict[str, str] = field(default_factory=dict)
    twists_unlocked: bool = False
    quest_cleared: Dict[int, bool] = field(default_factory=dict)
    highest_quest_cleared: int = 0
    campaign_complete: bool = False
    ranked_glory_unlocked: bool = False
    tutorial_seen: Set[str] = field(default_factory=set)
    tutorials_enabled: bool = True
    saved_teams: List[dict] = field(default_factory=list)
    fast_resolution: bool = False
    new_unlocks: Set[str] = field(default_factory=set)
    player_exp: int = 0
    gold: int = 0
    guild_vouchers: int = 0
    brighthollow_renown: int = 500
    ranked_rating: int = 500
    ranked_games_played: int = 0
    ranked_season_high_glory: int = 300
    ranked_total_wins: int = 0
    ranked_total_losses: int = 0
    ranked_best_quest_wins: int = 0
    ranked_current_quest_id: str | None = None
    ranked_season_id: int = 1
    ranked_floor_glory: int = 200
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
    storybook_equipped_icon: str = ""
    storybook_equipped_emote: str = ""
    storybook_equipped_dance: str = ""
    storybook_equipped_celebration: str = ""
    storybook_equipped_battlefield_skin: str = ""
    storybook_equipped_adventurer_skins: Dict[str, str] = field(default_factory=dict)
    storybook_quested_adventurers: Set[str] = field(default_factory=lambda: {"little_jack"})
    storybook_favorite_adventurer: str = "little_jack"
    storybook_training_favorite_adventurer: str = "little_jack"
