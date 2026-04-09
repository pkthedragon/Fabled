from __future__ import annotations

import copy
import json
import os
import random
import shutil
from itertools import combinations
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import campaign_save
import storybook_mode as storybook_mode_module
from campaign_save import load_campaign
from quests_ai_battle import queue_team_plan
from quests_ai_quest import QuestPartyChoice, choose_quest_party as base_choose_quest_party
from quests_ai_quest_loadout import assign_blind_quest_loadouts
from quests_ruleset_data import ADVENTURERS_BY_ID
from settings import HEIGHT, WIDTH
from storybook_mode import StorybookMode


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "playthrough_runs"


# Keep capture runs from touching the user's real save or probing LAN.
campaign_save.save_campaign = lambda _profile: None
storybook_mode_module.save_campaign = lambda _profile: None
storybook_mode_module.friend_host_available = lambda _ip: False


def _resilient_choose_quest_party(
    offer_ids: list[str] | tuple[str, ...],
    *,
    enemy_party_ids: list[str] | tuple[str, ...] = (),
    difficulty: str = "hard",
    rng: random.Random | None = None,
) -> QuestPartyChoice:
    offered = list(dict.fromkeys(offer_ids))
    rng = rng or random.Random()
    try:
        return base_choose_quest_party(
            offered,
            enemy_party_ids=enemy_party_ids,
            difficulty=difficulty,
            rng=rng,
        )
    except Exception as original_error:
        pass

    for subset_size in range(min(6, len(offered)) - 1, 2, -1):
        subsets = list(combinations(offered, subset_size))
        rng.shuffle(subsets)
        for subset in subsets[:80]:
            try:
                return base_choose_quest_party(
                    list(subset),
                    enemy_party_ids=enemy_party_ids,
                    difficulty=difficulty,
                    rng=rng,
                )
            except Exception:
                continue

    for trio in combinations(offered, 3):
        trio_ids = list(trio)
        try:
            package = assign_blind_quest_loadouts(trio_ids)
            profile = package.trios[tuple(sorted(trio_ids))]
            return QuestPartyChoice(
                offer_ids=tuple(trio_ids),
                team_ids=tuple(trio_ids),
                loadout=profile.loadout,
                package=package,
            )
        except Exception:
            continue

    raise RuntimeError(f"Could not build a quest trio from offer {offered}.") from original_error


storybook_mode_module.choose_quest_party = _resilient_choose_quest_party


def _slugify(text: str) -> str:
    out: list[str] = []
    last_sep = False
    for char in text.lower():
        if char.isalnum():
            out.append(char)
            last_sep = False
        elif not last_sep:
            out.append("_")
            last_sep = True
    return "".join(out).strip("_") or "step"


def _center(rect: pygame.Rect) -> tuple[int, int]:
    return (rect.centerx, rect.centery)


def _profile_template():
    profile = copy.deepcopy(load_campaign())
    profile.gold = max(int(getattr(profile, "gold", 0)), 2500)
    profile.player_exp = max(int(getattr(profile, "player_exp", 0)), 1800)
    profile.reputation = max(int(getattr(profile, "reputation", 300)), 420)
    profile.rank = getattr(profile, "rank", "Knight")
    profile.storybook_quested_adventurers = set(ADVENTURERS_BY_ID.keys())
    profile.storybook_favorite_adventurer = getattr(profile, "storybook_favorite_adventurer", "little_jack")
    profile.storybook_training_favorite_adventurer = getattr(profile, "storybook_training_favorite_adventurer", "little_jack")
    profile.storybook_friends = []
    profile.storybook_cosmetic_unlocks = set(getattr(profile, "storybook_cosmetic_unlocks", set()))
    profile.storybook_equipped_outfit = getattr(profile, "storybook_equipped_outfit", "")
    profile.storybook_equipped_chair = getattr(profile, "storybook_equipped_chair", "")
    profile.storybook_equipped_emote = getattr(profile, "storybook_equipped_emote", "")
    profile.storybook_equipped_adventurer_skins = dict(getattr(profile, "storybook_equipped_adventurer_skins", {}))
    profile.battle_log_popups = True
    profile.screen_shake = True
    return profile


def _make_mode(seed: int) -> StorybookMode:
    mode = StorybookMode(copy.deepcopy(_profile_template()))
    mode.rng.seed(seed)
    mode.profile.storybook_quested_adventurers = set(ADVENTURERS_BY_ID.keys())
    return mode


def _render(mode: StorybookMode, mouse_pos: tuple[int, int] = (-2000, -2000)) -> pygame.Surface:
    surface = pygame.Surface((WIDTH, HEIGHT))
    mode.draw(surface, mouse_pos)
    return surface


class RunCapture:
    def __init__(self, out_dir: Path, run_name: str, seed: int):
        self.out_dir = out_dir
        self.run_name = run_name
        self.seed = seed
        self.frames: list[dict] = []
        self.counter = 0

    def capture(self, mode: StorybookMode, label: str, *, mouse_pos: tuple[int, int] = (-2000, -2000)) -> Path:
        surface = _render(mode, mouse_pos)
        filename = f"{self.counter:03d}_{_slugify(label)}.png"
        path = self.out_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(surface, str(path))
        controller = mode.battle_controller
        state = {
            "index": self.counter,
            "label": label,
            "route": mode.route,
            "file": filename,
        }
        if controller is not None and mode.route == "battle":
            state["battle_round"] = controller.battle.round_num
            state["battle_phase"] = controller.phase
        quest_state = mode._quest_run_state("ai")
        if quest_state.get("active"):
            state["quest_record"] = f"{quest_state.get('wins', 0)}-{quest_state.get('losses', 0)}"
        if mode.bout_run.active:
            state["bout_record"] = f"{mode.bout_run.player_wins}-{mode.bout_run.opponent_wins}"
        self.frames.append(state)
        self.counter += 1
        return path

    def write_manifest(self) -> None:
        payload = {
            "run_name": self.run_name,
            "seed": self.seed,
            "frame_count": len(self.frames),
            "frames": self.frames,
        }
        (self.out_dir / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _require_button(mode: StorybookMode, key: str) -> pygame.Rect:
    rect = (mode.last_buttons or {}).get(key)
    if rect is None:
        raise RuntimeError(f"Button '{key}' was not present on route '{mode.route}'.")
    return rect


def _click_button(mode: StorybookMode, key: str) -> None:
    rect = _require_button(mode, key)
    mode.handle_click(_center(rect))


def _click_card_entry(mode: StorybookMode, entry_key: str, target_id: str) -> None:
    for entry in (mode.last_buttons or {}).get(entry_key, []):
        rect = entry[0]
        value = entry[1]
        if value == target_id:
            mode.handle_click(_center(rect))
            return
    raise RuntimeError(f"Could not find '{target_id}' in '{entry_key}' on route '{mode.route}'.")


def _choose_player_trio(mode: StorybookMode, *, difficulty: str) -> list[str]:
    choice = _resilient_choose_quest_party(
        mode.quest_offer_ids,
        enemy_party_ids=mode.quest_enemy_party_ids,
        difficulty=difficulty,
        rng=mode.rng,
    )
    return list(choice.team_ids)


def _pick_trio_from_quest_draft(mode: StorybookMode, capture: RunCapture, *, difficulty: str, prefix: str) -> list[str]:
    trio = _choose_player_trio(mode, difficulty=difficulty)
    for pick_index, adventurer_id in enumerate(trio, start=1):
        _click_card_entry(mode, "cards", adventurer_id)
        _click_button(mode, "pick")
        capture.capture(mode, f"{prefix}_pick_{pick_index}_{adventurer_id}")
    _click_button(mode, "continue")
    return trio


def _queue_player_phase(mode: StorybookMode, *, bonus: bool, difficulty: str) -> None:
    controller = mode.battle_controller
    if controller is None:
        raise RuntimeError("Cannot queue battle phase without a battle controller.")
    queue_team_plan(
        controller.battle,
        controller.human_team_num,
        bonus=bonus,
        difficulty=difficulty,
        rng=mode.rng,
    )
    controller.phase = "bonus_resolve_ready" if bonus else "action_resolve_ready"
    controller.active_actor = None
    controller.pending_choice = None
    controller.target_candidates = []
    controller.spellbook_open = False


def _autoplay_battle(mode: StorybookMode, capture: RunCapture, *, difficulty: str, prefix: str) -> None:
    seen_rounds: set[int] = set()
    while mode.route == "battle":
        controller = mode.battle_controller
        if controller is None:
            raise RuntimeError("Battle route entered without a controller.")

        round_num = controller.battle.round_num
        if round_num not in seen_rounds:
            capture.capture(
                mode,
                f"{prefix}_round_{round_num:02d}_start",
            )
            seen_rounds.add(round_num)

        if controller.phase in {"action_select", "action_target"}:
            _queue_player_phase(mode, bonus=False, difficulty=difficulty)
            controller.resolve_current_phase()
            mode._check_battle_results()
            if mode.route != "battle":
                break

        controller = mode.battle_controller
        if controller is None or mode.route != "battle":
            break

        if controller.phase in {"bonus_select", "bonus_target"}:
            _queue_player_phase(mode, bonus=True, difficulty=difficulty)
            controller.resolve_current_phase()
            mode._check_battle_results()
            if mode.route != "battle":
                break
        elif controller.phase in {"action_resolve_ready", "bonus_resolve_ready"}:
            controller.resolve_current_phase()
            mode._check_battle_results()


def _apply_first_quest_reward(mode: StorybookMode) -> None:
    gold_index = next(
        (index for index, option in enumerate(mode.quest_reward_options) if option.get("kind") == "gold"),
        0,
    )
    for rect, choice_index, artifact_id in (mode.last_buttons or {}).get("choices", []):
        if choice_index == gold_index:
            mode.handle_click(_center(rect))
            return
    raise RuntimeError("Could not find a clickable quest reward choice.")


def _apply_first_bout_adapt_choice(mode: StorybookMode) -> None:
    artifact_choices = (mode.last_buttons or {}).get("artifact_choices", [])
    if artifact_choices:
        rect, _artifact_id = artifact_choices[0]
        mode.handle_click(_center(rect))
        return
    recruit_choices = (mode.last_buttons or {}).get("recruit_choices", [])
    if recruit_choices:
        rect, _adventurer_id = recruit_choices[0]
        mode.handle_click(_center(rect))
        return
    _click_button(mode, "skip")


def run_quest_capture(seed: int) -> Path:
    out_dir = OUTPUT_DIR / f"quest_player_run_seed_{seed}"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    capture = RunCapture(out_dir, "quest_player_run", seed)
    mode = _make_mode(seed)

    capture.capture(mode, "main_menu")
    _click_button(mode, "guild_hall")
    capture.capture(mode, "quest_hub_idle")

    advance_key = "advance" if "advance" in mode.last_buttons else "current_quest"
    _click_button(mode, advance_key)
    capture.capture(mode, "quest_party_reveal")

    _click_button(mode, "confirm")
    capture.capture(mode, "quest_party_loadout")

    _click_button(mode, "done")
    capture.capture(mode, "quest_hub_active")

    encounter_index = 1
    while True:
        advance_key = "advance" if "advance" in mode.last_buttons else "current_quest"
        _click_button(mode, advance_key)
        capture.capture(mode, f"quest_encounter_{encounter_index:02d}_select")

        _pick_trio_from_quest_draft(
            mode,
            capture,
            difficulty="normal",
            prefix=f"quest_encounter_{encounter_index:02d}",
        )
        capture.capture(mode, f"quest_encounter_{encounter_index:02d}_loadout")

        _click_button(mode, "confirm")
        capture.capture(mode, f"quest_encounter_{encounter_index:02d}_battle_enter")
        _autoplay_battle(
            mode,
            capture,
            difficulty="normal",
            prefix=f"quest_encounter_{encounter_index:02d}",
        )

        if mode.route != "results":
            raise RuntimeError(f"Expected results after quest encounter {encounter_index}, got '{mode.route}'.")
        capture.capture(mode, f"quest_encounter_{encounter_index:02d}_results")

        if mode.quest_reward_pending:
            _click_button(mode, "continue")
            capture.capture(mode, f"quest_encounter_{encounter_index:02d}_reward_choice")
            _apply_first_quest_reward(mode)
            capture.capture(mode, f"quest_encounter_{encounter_index:02d}_post_reward")
        else:
            _click_button(mode, "continue")
            capture.capture(mode, f"quest_encounter_{encounter_index:02d}_post_results")

        if not mode._quest_run_state("ai").get("active"):
            break
        encounter_index += 1
        if encounter_index > 20:
            raise RuntimeError("Quest capture exceeded 20 encounters without completing.")

    capture.write_manifest()
    return out_dir


def run_bout_capture(seed: int) -> Path:
    out_dir = OUTPUT_DIR / f"bout_player_run_seed_{seed}"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    capture = RunCapture(out_dir, "bout_player_run", seed)
    mode = _make_mode(seed)

    capture.capture(mode, "main_menu")
    _click_button(mode, "bouts")
    capture.capture(mode, "bout_mode_select")

    _click_button(mode, "vs_random")
    capture.capture(mode, "bout_party_loadout")

    _click_button(mode, "done")
    capture.capture(mode, "bout_encounter_01_select")

    match_index = 1
    while True:
        _pick_trio_from_quest_draft(
            mode,
            capture,
            difficulty="normal",
            prefix=f"bout_match_{match_index:02d}",
        )
        capture.capture(mode, f"bout_match_{match_index:02d}_loadout")

        _click_button(mode, "confirm")
        capture.capture(mode, f"bout_match_{match_index:02d}_battle_enter")
        _autoplay_battle(
            mode,
            capture,
            difficulty="hard",
            prefix=f"bout_match_{match_index:02d}",
        )

        if mode.route != "results":
            raise RuntimeError(f"Expected results after bout match {match_index}, got '{mode.route}'.")
        capture.capture(mode, f"bout_match_{match_index:02d}_results")

        _click_button(mode, "continue")
        if mode.route == "bout_adapt":
            capture.capture(mode, f"bout_match_{match_index:02d}_adapt")
            _apply_first_bout_adapt_choice(mode)
            capture.capture(mode, f"bout_match_{match_index:02d}_party_loadout_after_adapt")
            _click_button(mode, "done")
            match_index += 1
            capture.capture(mode, f"bout_encounter_{match_index:02d}_select")
        elif mode.route == "bouts_menu":
            capture.capture(mode, "bout_series_complete")
            break
        else:
            raise RuntimeError(f"Unexpected route after continuing bout results: '{mode.route}'.")

        if match_index > 5:
            raise RuntimeError("Bout capture exceeded 5 matches without completing.")

    capture.write_manifest()
    return out_dir


def write_index(quest_dir: Path, bout_dir: Path) -> None:
    payload = {
        "quest_run": str(quest_dir),
        "bout_run": str(bout_dir),
    }
    (OUTPUT_DIR / "index.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    pygame.init()
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    quest_dir = run_quest_capture(seed=1)
    bout_dir = run_bout_capture(seed=29)
    write_index(quest_dir, bout_dir)

    print(f"Quest images saved to: {quest_dir}")
    print(f"Bout images saved to: {bout_dir}")


if __name__ == "__main__":
    main()
