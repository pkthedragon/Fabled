"""
campaign_save.py – JSON save / load for CampaignProfile.
"""
import json
import os

from models import CampaignProfile


LEGACY_SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "campaign_save.json")


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


def save_campaign(profile: CampaignProfile) -> None:
    """Serialize the profile to JSON and write to the per-user save path."""
    save_path = get_campaign_save_path()
    data = {
        "recruited":         list(profile.recruited),
        "sig_tier":          profile.sig_tier,
        "basics_tier":       profile.basics_tier,
        "unlocked_classes":  list(profile.unlocked_classes),
        "unlocked_items":    list(profile.unlocked_items),
        "unlocked_artifacts": list(profile.unlocked_artifacts),
        "default_sigs":      dict(profile.default_sigs),
        "twists_unlocked":   profile.twists_unlocked,
        "quest_cleared":     {str(k): v for k, v in profile.quest_cleared.items()},
        "highest_quest_cleared": profile.highest_quest_cleared,
        "campaign_complete": profile.campaign_complete,
        "ranked_glory_unlocked": profile.ranked_glory_unlocked,
        "tutorial_seen":     list(profile.tutorial_seen),
        "saved_teams":       profile.saved_teams,
        "tutorials_enabled": profile.tutorials_enabled,
        "fast_resolution":   profile.fast_resolution,
        "new_unlocks":       list(profile.new_unlocks),
    }
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_campaign() -> CampaignProfile:
    """Load a CampaignProfile from the per-user save path."""
    save_path = _migrate_legacy_save()
    if not os.path.exists(save_path):
        return CampaignProfile()
    try:
        with open(save_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        profile = CampaignProfile()
        profile.recruited                = set(data.get("recruited", list(profile.recruited)))
        profile.sig_tier                 = int(data.get("sig_tier", profile.sig_tier))
        profile.basics_tier              = int(data.get("basics_tier", profile.basics_tier))
        profile.unlocked_classes         = set(data.get("unlocked_classes", list(profile.unlocked_classes)))
        profile.unlocked_items           = set(data.get("unlocked_items", list(profile.unlocked_items)))
        profile.unlocked_artifacts       = set(data.get("unlocked_artifacts", list(profile.unlocked_artifacts)))
        profile.default_sigs             = dict(data.get("default_sigs", {}))
        profile.twists_unlocked          = bool(data.get("twists_unlocked", True))
        profile.quest_cleared            = {int(k): v for k, v in data.get("quest_cleared", {}).items()}
        profile.highest_quest_cleared    = int(data.get("highest_quest_cleared", -1))
        profile.campaign_complete        = bool(data.get("campaign_complete", False))
        profile.ranked_glory_unlocked    = bool(data.get("ranked_glory_unlocked", False))
        profile.tutorial_seen            = set(data.get("tutorial_seen", []))
        profile.saved_teams              = data.get("saved_teams", [])
        profile.tutorials_enabled        = bool(data.get("tutorials_enabled", True))
        profile.fast_resolution          = bool(data.get("fast_resolution", False))
        profile.new_unlocks              = set(data.get("new_unlocks", []))

        if not profile.unlocked_artifacts:
            legacy_map = {
                "health_potion": "holy_grail",
                "healing_tonic": "holy_grail",
                "crafty_shield": "red_hood",
                "lightning_boots": "winged_sandals",
                "main_gauche": "achilles_spear",
                "iron_buckler": "golden_fleece",
                "smoke_bomb": "magic_mirror",
                "hunters_net": "nettle_smock",
                "ancient_hourglass": "cracked_stopwatch",
                "family_seal": "excalibur",
                "holy_diadem": "enchanted_lamp",
                "vampire_fang": "selkies_skin",
                "spiked_mail": "red_hood",
                "arcane_focus": "godmothers_wand",
                "heart_amulet": "bluebeards_key",
                "misericorde": "misericorde_artifact",
            }
            migrated = {legacy_map[item_id] for item_id in profile.unlocked_items if item_id in legacy_map}
            if migrated:
                profile.unlocked_artifacts = migrated
        return profile
    except (json.JSONDecodeError, KeyError, ValueError):
        # Corrupt save – start fresh
        return CampaignProfile()
