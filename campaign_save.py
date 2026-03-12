"""
campaign_save.py – JSON save / load for CampaignProfile.
"""
import json
import os

from models import CampaignProfile

SAVE_PATH = "campaign_save.json"


def save_campaign(profile: CampaignProfile) -> None:
    """Serialize the profile to JSON and write to SAVE_PATH."""
    data = {
        "recruited":         list(profile.recruited),
        "sig_tier":          profile.sig_tier,
        "basics_tier":       profile.basics_tier,
        "unlocked_classes":  list(profile.unlocked_classes),
        "unlocked_items":    list(profile.unlocked_items),
        "default_sigs":      dict(profile.default_sigs),
        "twists_unlocked":   profile.twists_unlocked,
        "quest_cleared":     {str(k): v for k, v in profile.quest_cleared.items()},
        "highest_quest_cleared": profile.highest_quest_cleared,
        "campaign_complete": profile.campaign_complete,
        "ranked_glory_unlocked": profile.ranked_glory_unlocked,
        "tutorial_seen":     list(profile.tutorial_seen),
        "saved_teams":       profile.saved_teams,
    }
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_campaign() -> CampaignProfile:
    """Load a CampaignProfile from SAVE_PATH.  Returns a fresh profile if the file is missing."""
    if not os.path.exists(SAVE_PATH):
        return CampaignProfile()
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        profile = CampaignProfile()
        profile.recruited                = set(data.get("recruited", list(profile.recruited)))
        profile.sig_tier                 = int(data.get("sig_tier", profile.sig_tier))
        profile.basics_tier              = int(data.get("basics_tier", profile.basics_tier))
        profile.unlocked_classes         = set(data.get("unlocked_classes", list(profile.unlocked_classes)))
        profile.unlocked_items           = set(data.get("unlocked_items", list(profile.unlocked_items)))
        profile.default_sigs             = dict(data.get("default_sigs", {}))
        profile.twists_unlocked          = bool(data.get("twists_unlocked", False))
        profile.quest_cleared            = {int(k): v for k, v in data.get("quest_cleared", {}).items()}
        profile.highest_quest_cleared    = int(data.get("highest_quest_cleared", -1))
        profile.campaign_complete        = bool(data.get("campaign_complete", False))
        profile.ranked_glory_unlocked    = bool(data.get("ranked_glory_unlocked", False))
        profile.tutorial_seen            = set(data.get("tutorial_seen", []))
        profile.saved_teams              = data.get("saved_teams", [])
        return profile
    except (json.JSONDecodeError, KeyError, ValueError):
        # Corrupt save – start fresh
        return CampaignProfile()
