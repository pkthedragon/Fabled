from __future__ import annotations

from typing import Dict, Iterable, List


STARTER_ADVENTURERS = {
    "risa_redcloak",
    "robin_hooded_avenger",
    "sir_roland",
}

TUTORIAL_ADVENTURERS = {
    "ashen_ella",
    "hunold_the_piper",
    "aldric_lost_lamb",
    "pinocchio",
    "prince_charming",
}

STARTER_ARTIFACTS = {
    "divine_apple",
}

TUTORIAL_ARTIFACTS = {
    "holy_grail",
    "excalibur",
}

NON_GUILD_ADVENTURERS = STARTER_ADVENTURERS | TUTORIAL_ADVENTURERS
NON_GUILD_ARTIFACTS = STARTER_ARTIFACTS | TUTORIAL_ARTIFACTS

ADVENTURER_PRICES: Dict[str, int] = {
    "little_jack": 700,
    "gretel": 650,
    "lucky_constantine": 750,
    "reynard": 800,
    "porcus_iii": 650,
    "lady_of_reflections": 700,
    "march_hare": 850,
    "witch_of_the_woods": 800,
    "briar_rose": 700,
    "frederic": 550,
    "matchstick_liesl": 700,
    "snowkissed_aurora": 650,
    "green_knight": 700,
    "rapunzel": 800,
    "rumpelstiltskin": 850,
    "sea_wench_asha": 900,
}

ARTIFACT_PRICES: Dict[str, int] = {
    "winged_sandals": 250,
    "achilles_spear": 275,
    "golden_fleece": 275,
    "magic_mirror": 325,
    "cracked_stopwatch": 350,
    "melusines_knife": 250,
    "last_prism": 225,
    "nettle_smock": 250,
    "godmothers_wand": 300,
    "misericorde_artifact": 325,
    "enchanted_lamp": 450,
    "selkies_skin": 275,
    "goose_quill": 325,
    "red_hood": 275,
    "cursed_needle": 350,
    "bluebeards_key": 250,
    "durandal": 400,
}

TUTORIAL_QUEST_GOLD = 0
NON_TUTORIAL_QUEST_GOLD = 100
QUICK_PLAY_WIN_GOLD = 120
QUICK_PLAY_LOSS_GOLD = 80
RANKED_WIN_GOLD = 140
RANKED_LOSS_GOLD = 100
RANKED_WIN_RENOWN = 20
RANKED_LOSS_RENOWN = -15
EMBASSY_GOLD_PER_DOLLAR = 100


def guild_price_for_adventurer(adventurer_id: str) -> int | None:
    return ADVENTURER_PRICES.get(adventurer_id)


def guild_price_for_artifact(artifact_id: str) -> int | None:
    return ARTIFACT_PRICES.get(artifact_id)


def purchasable_adventurer_ids() -> List[str]:
    return list(ADVENTURER_PRICES.keys())


def purchasable_artifact_ids() -> List[str]:
    return list(ARTIFACT_PRICES.keys())


def embassy_gold_for_dollars(dollars: int) -> int:
    return max(0, int(dollars)) * EMBASSY_GOLD_PER_DOLLAR


def random_artifact_reward_pool(owned_artifact_ids: Iterable[str]) -> List[str]:
    owned = set(owned_artifact_ids)
    return [artifact_id for artifact_id in ARTIFACT_PRICES if artifact_id not in owned]
