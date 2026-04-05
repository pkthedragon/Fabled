"""
campaign_save.py - JSON save / load for CampaignProfile.
"""
from __future__ import annotations

import json
import os

from economy import STARTER_ADVENTURERS
from models import CampaignProfile
from quests_ruleset_data import ADVENTURERS_BY_ID, ARTIFACTS_BY_ID


SAVE_VERSION = 2
LEGACY_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "campaign_save.json")

_KNOWN_ADVENTURER_IDS = set(ADVENTURERS_BY_ID.keys())
_KNOWN_ARTIFACT_IDS = set(ARTIFACTS_BY_ID.keys())

_LEGACY_ADVENTURER_ID_MAP = {
    "risa_redcloak": "red_blanchette",
    "gretel": "witch_hunter_gretel",
    "matchstick_liesl": "matchbox_liesl",
    "green_knight": "the_green_knight",
    "rapunzel": "rapunzel_the_golden",
    "pinocchio": "pinocchio_cursed_puppet",
}

_LEGACY_ARTIFACT_ID_MAP = {
    "misericorde_artifact": "misericorde",
    "cursed_needle": "cursed_spindle",
    "melusines_knife": "naiads_knife",
    "cracked_stopwatch": "arcane_hourglass",
    "godmothers_wand": "glass_slipper",
}


def _normalize_adventurer_ids(raw_ids) -> set[str]:
    normalized: set[str] = set()
    for value in raw_ids or []:
        adventurer_id = str(value)
        mapped = _LEGACY_ADVENTURER_ID_MAP.get(adventurer_id, adventurer_id)
        if mapped in _KNOWN_ADVENTURER_IDS:
            normalized.add(mapped)
    return normalized


def _normalize_artifact_ids(raw_ids) -> set[str]:
    normalized: set[str] = set()
    for value in raw_ids or []:
        artifact_id = str(value)
        mapped = _LEGACY_ARTIFACT_ID_MAP.get(artifact_id, artifact_id)
        if mapped in _KNOWN_ARTIFACT_IDS:
            normalized.add(mapped)
    return normalized


def _normalize_friends(raw_friends) -> list[dict[str, str]]:
    friends: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in raw_friends or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()[:32]
        ip = str(entry.get("ip", "")).strip()[:64]
        if not name or not ip:
            continue
        key = (name.lower(), ip)
        if key in seen:
            continue
        seen.add(key)
        friends.append({"name": name, "ip": ip})
    return friends


def _saved_games_dir() -> str:
    """Return Fabled's per-user save directory under Saved Games."""
    home = os.path.expanduser("~")
    saved_games = os.path.join(home, "Saved Games", "Fabled")
    os.makedirs(saved_games, exist_ok=True)
    return saved_games


def get_campaign_save_path() -> str:
    """Return the full path to the campaign save file."""
    return os.path.join(_saved_games_dir(), "campaign_save.json")


def _migrate_legacy_save() -> str:
    """Move a save from the game folder into Saved Games on first run."""
    save_path = get_campaign_save_path()
    if os.path.exists(save_path) or not os.path.exists(LEGACY_SAVE_PATH):
        return save_path
    try:
        os.replace(LEGACY_SAVE_PATH, save_path)
    except OSError:
        pass
    return save_path


def _normalize_profile(profile: CampaignProfile) -> CampaignProfile:
    profile.recruited = _normalize_adventurer_ids(profile.recruited)
    profile.recruited |= set(STARTER_ADVENTURERS)
    profile.unlocked_items = set()
    profile.unlocked_artifacts = _normalize_artifact_ids(profile.unlocked_artifacts)
    profile.default_sigs = {
        _LEGACY_ADVENTURER_ID_MAP.get(str(adventurer_id), str(adventurer_id)): str(sig_id)
        for adventurer_id, sig_id in dict(profile.default_sigs).items()
        if _LEGACY_ADVENTURER_ID_MAP.get(str(adventurer_id), str(adventurer_id)) in _KNOWN_ADVENTURER_IDS
    }
    profile.quick_play_unlocked = bool(profile.quick_play_unlocked or profile.tutorial_complete)
    profile.highest_quest_cleared = max(int(profile.highest_quest_cleared), 0)
    profile.player_exp = max(0, int(profile.player_exp))
    profile.gold = max(0, int(profile.gold))
    profile.guild_vouchers = max(0, int(profile.guild_vouchers))
    profile.brighthollow_renown = int(profile.brighthollow_renown)
    profile.ranked_rating = max(1, min(2000, int(profile.ranked_rating)))
    profile.ranked_games_played = max(0, int(profile.ranked_games_played))
    profile.ranked_season_high_glory = max(1, min(2000, int(getattr(profile, "ranked_season_high_glory", profile.ranked_rating or 300))))
    profile.ranked_total_wins = max(0, int(getattr(profile, "ranked_total_wins", 0)))
    profile.ranked_total_losses = max(0, int(getattr(profile, "ranked_total_losses", 0)))
    profile.ranked_best_quest_wins = max(0, int(getattr(profile, "ranked_best_quest_wins", 0)))
    profile.ranked_current_quest_id = getattr(profile, "ranked_current_quest_id", None)
    profile.ranked_season_id = max(1, int(getattr(profile, "ranked_season_id", 1)))
    profile.ranked_floor_glory = max(1, min(2000, int(getattr(profile, "ranked_floor_glory", 200))))
    profile.non_tutorial_quests_completed = max(0, int(profile.non_tutorial_quests_completed))
    profile.premium_dollars_spent = max(0, int(profile.premium_dollars_spent))
    profile.storybook_friends = _normalize_friends(getattr(profile, "storybook_friends", []))
    profile.storybook_weapon_unlocks = set(getattr(profile, "storybook_weapon_unlocks", set()))
    profile.storybook_adventurer_unlocks = _normalize_adventurer_ids(
        getattr(profile, "storybook_adventurer_unlocks", set())
    )
    profile.storybook_cosmetic_unlocks = set(getattr(profile, "storybook_cosmetic_unlocks", set()))
    profile.storybook_equipped_outfit = str(getattr(profile, "storybook_equipped_outfit", ""))
    profile.storybook_equipped_chair = str(getattr(profile, "storybook_equipped_chair", ""))
    profile.storybook_equipped_icon = str(getattr(profile, "storybook_equipped_icon", ""))
    profile.storybook_equipped_emote = str(getattr(profile, "storybook_equipped_emote", ""))
    profile.storybook_equipped_dance = str(getattr(profile, "storybook_equipped_dance", ""))
    profile.storybook_equipped_celebration = str(getattr(profile, "storybook_equipped_celebration", ""))
    profile.storybook_equipped_battlefield_skin = str(getattr(profile, "storybook_equipped_battlefield_skin", ""))
    profile.storybook_equipped_adventurer_skins = {
        str(key): str(value)
        for key, value in dict(getattr(profile, "storybook_equipped_adventurer_skins", {})).items()
        if str(key) and str(value)
    }
    profile.storybook_quested_adventurers = _normalize_adventurer_ids(
        getattr(profile, "storybook_quested_adventurers", {"little_jack"})
    )
    profile.storybook_quested_adventurers.add("little_jack")
    favorite = str(getattr(profile, "storybook_favorite_adventurer", "little_jack"))
    if favorite not in profile.storybook_quested_adventurers:
        favorite = "little_jack"
    profile.storybook_favorite_adventurer = favorite
    training_favorite = str(getattr(profile, "storybook_training_favorite_adventurer", "little_jack"))
    profile.storybook_training_favorite_adventurer = training_favorite if training_favorite in _KNOWN_ADVENTURER_IDS else "little_jack"
    if profile.saved_teams is None:
        profile.saved_teams = []
    return profile


def save_campaign(profile: CampaignProfile) -> None:
    """Serialize the profile to JSON and write to the per-user save path."""
    save_path = get_campaign_save_path()
    profile = _normalize_profile(profile)
    data = {
        "version": SAVE_VERSION,
        "recruited": list(profile.recruited),
        "sig_tier": profile.sig_tier,
        "basics_tier": profile.basics_tier,
        "unlocked_classes": list(profile.unlocked_classes),
        "unlocked_items": list(profile.unlocked_items),
        "unlocked_artifacts": list(profile.unlocked_artifacts),
        "default_sigs": dict(profile.default_sigs),
        "twists_unlocked": profile.twists_unlocked,
        "quest_cleared": {str(k): v for k, v in profile.quest_cleared.items()},
        "highest_quest_cleared": profile.highest_quest_cleared,
        "campaign_complete": profile.campaign_complete,
        "ranked_glory_unlocked": profile.ranked_glory_unlocked,
        "tutorial_seen": list(profile.tutorial_seen),
        "saved_teams": profile.saved_teams,
        "tutorials_enabled": profile.tutorials_enabled,
        "fast_resolution": profile.fast_resolution,
        "new_unlocks": list(profile.new_unlocks),
        "player_exp": profile.player_exp,
        "gold": profile.gold,
        "guild_vouchers": profile.guild_vouchers,
        "brighthollow_renown": profile.brighthollow_renown,
        "ranked_rating": profile.ranked_rating,
        "ranked_games_played": profile.ranked_games_played,
        "ranked_season_high_glory": profile.ranked_season_high_glory,
        "ranked_total_wins": profile.ranked_total_wins,
        "ranked_total_losses": profile.ranked_total_losses,
        "ranked_best_quest_wins": profile.ranked_best_quest_wins,
        "ranked_current_quest_id": profile.ranked_current_quest_id,
        "ranked_season_id": profile.ranked_season_id,
        "ranked_floor_glory": profile.ranked_floor_glory,
        "non_tutorial_quests_completed": profile.non_tutorial_quests_completed,
        "adventurer_quest_clears": dict(profile.adventurer_quest_clears),
        "class_points": dict(profile.class_points),
        "tutorial_complete": profile.tutorial_complete,
        "quick_play_unlocked": profile.quick_play_unlocked,
        "premium_dollars_spent": profile.premium_dollars_spent,
        "storybook_friends": profile.storybook_friends,
        "storybook_weapon_unlocks": list(profile.storybook_weapon_unlocks),
        "storybook_adventurer_unlocks": list(profile.storybook_adventurer_unlocks),
        "storybook_cosmetic_unlocks": list(profile.storybook_cosmetic_unlocks),
        "storybook_equipped_outfit": profile.storybook_equipped_outfit,
        "storybook_equipped_chair": profile.storybook_equipped_chair,
        "storybook_equipped_icon": profile.storybook_equipped_icon,
        "storybook_equipped_emote": profile.storybook_equipped_emote,
        "storybook_equipped_dance": profile.storybook_equipped_dance,
        "storybook_equipped_celebration": profile.storybook_equipped_celebration,
        "storybook_equipped_battlefield_skin": profile.storybook_equipped_battlefield_skin,
        "storybook_equipped_adventurer_skins": dict(profile.storybook_equipped_adventurer_skins),
        "storybook_quested_adventurers": list(profile.storybook_quested_adventurers),
        "storybook_favorite_adventurer": profile.storybook_favorite_adventurer,
        "storybook_training_favorite_adventurer": profile.storybook_training_favorite_adventurer,
    }
    with open(save_path, "w", encoding="utf-8") as save_file:
        json.dump(data, save_file, indent=2)


def _load_modern_profile(data: dict) -> CampaignProfile:
    profile = CampaignProfile()
    profile.recruited = set(data.get("recruited", list(profile.recruited)))
    profile.sig_tier = int(data.get("sig_tier", profile.sig_tier))
    profile.basics_tier = int(data.get("basics_tier", profile.basics_tier))
    profile.unlocked_classes = set(data.get("unlocked_classes", list(profile.unlocked_classes)))
    profile.unlocked_items = set(data.get("unlocked_items", list(profile.unlocked_items)))
    profile.unlocked_artifacts = set(data.get("unlocked_artifacts", list(profile.unlocked_artifacts)))
    profile.default_sigs = dict(data.get("default_sigs", {}))
    profile.twists_unlocked = bool(data.get("twists_unlocked", profile.twists_unlocked))
    profile.quest_cleared = {int(k): v for k, v in data.get("quest_cleared", {}).items()}
    profile.highest_quest_cleared = int(data.get("highest_quest_cleared", profile.highest_quest_cleared))
    profile.campaign_complete = bool(data.get("campaign_complete", profile.campaign_complete))
    profile.ranked_glory_unlocked = bool(data.get("ranked_glory_unlocked", profile.ranked_glory_unlocked))
    profile.tutorial_seen = set(data.get("tutorial_seen", []))
    profile.saved_teams = data.get("saved_teams", [])
    profile.tutorials_enabled = bool(data.get("tutorials_enabled", profile.tutorials_enabled))
    profile.fast_resolution = bool(data.get("fast_resolution", profile.fast_resolution))
    profile.new_unlocks = set(data.get("new_unlocks", []))
    profile.player_exp = int(data.get("player_exp", profile.player_exp))
    profile.gold = int(data.get("gold", profile.gold))
    profile.guild_vouchers = int(data.get("guild_vouchers", profile.guild_vouchers))
    profile.brighthollow_renown = int(data.get("brighthollow_renown", profile.brighthollow_renown))
    profile.ranked_rating = int(data.get("ranked_rating", profile.ranked_rating))
    profile.ranked_games_played = int(data.get("ranked_games_played", profile.ranked_games_played))
    profile.ranked_season_high_glory = int(data.get("ranked_season_high_glory", profile.ranked_season_high_glory))
    profile.ranked_total_wins = int(data.get("ranked_total_wins", profile.ranked_total_wins))
    profile.ranked_total_losses = int(data.get("ranked_total_losses", profile.ranked_total_losses))
    profile.ranked_best_quest_wins = int(data.get("ranked_best_quest_wins", profile.ranked_best_quest_wins))
    profile.ranked_current_quest_id = data.get("ranked_current_quest_id", profile.ranked_current_quest_id)
    profile.ranked_season_id = int(data.get("ranked_season_id", profile.ranked_season_id))
    profile.ranked_floor_glory = int(data.get("ranked_floor_glory", profile.ranked_floor_glory))
    profile.non_tutorial_quests_completed = int(data.get("non_tutorial_quests_completed", profile.non_tutorial_quests_completed))
    profile.adventurer_quest_clears = {str(k): int(v) for k, v in data.get("adventurer_quest_clears", {}).items()}
    profile.class_points = {str(k): int(v) for k, v in data.get("class_points", {}).items()}
    profile.tutorial_complete = bool(data.get("tutorial_complete", profile.tutorial_complete))
    profile.quick_play_unlocked = bool(data.get("quick_play_unlocked", profile.quick_play_unlocked))
    profile.premium_dollars_spent = int(data.get("premium_dollars_spent", profile.premium_dollars_spent))
    profile.storybook_friends = _normalize_friends(data.get("storybook_friends", []))
    profile.storybook_weapon_unlocks = set(data.get("storybook_weapon_unlocks", []))
    profile.storybook_adventurer_unlocks = set(data.get("storybook_adventurer_unlocks", []))
    profile.storybook_cosmetic_unlocks = set(data.get("storybook_cosmetic_unlocks", []))
    profile.storybook_equipped_outfit = str(data.get("storybook_equipped_outfit", getattr(profile, "storybook_equipped_outfit", "")))
    profile.storybook_equipped_chair = str(data.get("storybook_equipped_chair", getattr(profile, "storybook_equipped_chair", "")))
    profile.storybook_equipped_icon = str(data.get("storybook_equipped_icon", getattr(profile, "storybook_equipped_icon", "")))
    profile.storybook_equipped_emote = str(data.get("storybook_equipped_emote", getattr(profile, "storybook_equipped_emote", "")))
    profile.storybook_equipped_dance = str(data.get("storybook_equipped_dance", getattr(profile, "storybook_equipped_dance", "")))
    profile.storybook_equipped_celebration = str(data.get("storybook_equipped_celebration", getattr(profile, "storybook_equipped_celebration", "")))
    profile.storybook_equipped_battlefield_skin = str(
        data.get("storybook_equipped_battlefield_skin", getattr(profile, "storybook_equipped_battlefield_skin", ""))
    )
    profile.storybook_equipped_adventurer_skins = {
        str(key): str(value)
        for key, value in dict(data.get("storybook_equipped_adventurer_skins", {})).items()
        if str(key) and str(value)
    }
    profile.storybook_quested_adventurers = set(data.get("storybook_quested_adventurers", ["little_jack"]))
    profile.storybook_favorite_adventurer = str(data.get("storybook_favorite_adventurer", profile.storybook_favorite_adventurer))
    profile.storybook_training_favorite_adventurer = str(
        data.get("storybook_training_favorite_adventurer", getattr(profile, "storybook_training_favorite_adventurer", "little_jack"))
    )
    return _normalize_profile(profile)


def _load_legacy_profile(data: dict) -> CampaignProfile:
    profile = CampaignProfile()
    profile.recruited = set(data.get("recruited", list(profile.recruited)))
    profile.sig_tier = int(data.get("sig_tier", profile.sig_tier))
    profile.basics_tier = int(data.get("basics_tier", profile.basics_tier))
    profile.unlocked_classes = set(data.get("unlocked_classes", list(profile.unlocked_classes)))
    profile.unlocked_items = set(data.get("unlocked_items", list(profile.unlocked_items)))
    profile.unlocked_artifacts = set(data.get("unlocked_artifacts", list(profile.unlocked_artifacts)))
    profile.default_sigs = dict(data.get("default_sigs", {}))
    profile.twists_unlocked = bool(data.get("twists_unlocked", profile.twists_unlocked))
    profile.quest_cleared = {int(k): v for k, v in data.get("quest_cleared", {}).items()}
    profile.highest_quest_cleared = int(data.get("highest_quest_cleared", profile.highest_quest_cleared))
    profile.campaign_complete = bool(data.get("campaign_complete", profile.campaign_complete))
    profile.ranked_glory_unlocked = bool(data.get("ranked_glory_unlocked", profile.ranked_glory_unlocked))
    profile.tutorial_seen = set(data.get("tutorial_seen", []))
    profile.saved_teams = data.get("saved_teams", [])
    profile.tutorials_enabled = bool(data.get("tutorials_enabled", profile.tutorials_enabled))
    profile.fast_resolution = bool(data.get("fast_resolution", profile.fast_resolution))
    profile.new_unlocks = set(data.get("new_unlocks", []))

    profile.recruited = _normalize_adventurer_ids(profile.recruited)
    cleared_nonzero = sum(1 for quest_id, cleared in profile.quest_cleared.items() if quest_id > 0 and cleared)
    recruited_bonus = max(0, len(profile.recruited - STARTER_ADVENTURERS)) * 60
    profile.player_exp = max(0, cleared_nonzero * 100 + recruited_bonus)
    profile.tutorial_complete = bool(profile.highest_quest_cleared >= 4)
    profile.quick_play_unlocked = profile.tutorial_complete
    return _normalize_profile(profile)


def load_campaign() -> CampaignProfile:
    """Load a CampaignProfile from the per-user save path."""
    save_path = _migrate_legacy_save()
    if not os.path.exists(save_path):
        return _normalize_profile(CampaignProfile())
    try:
        with open(save_path, "r", encoding="utf-8") as save_file:
            data = json.load(save_file)
        version = int(data.get("version", 1))
        if version >= SAVE_VERSION:
            return _load_modern_profile(data)
        return _load_legacy_profile(data)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return _normalize_profile(CampaignProfile())
