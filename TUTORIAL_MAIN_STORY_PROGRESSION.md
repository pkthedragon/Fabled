# Tutorial/Main Story Progression Understanding

This document captures a full understanding of the **Fantasia tutorial flow**, which is also the game’s **main story progression**, using the term **Quest** for each battle.

## Core framing

- The tutorial is not separate from the campaign: it *is* the campaign.
- Progression is built as a 31-Quest learning arc that layers:
  1. class fundamentals,
  2. roster expansion,
  3. equipment milestones,
  4. status/combo literacy,
  5. final exam and final boss execution.
- Every key unlock is tied to specific Quest clears, so gameplay mastery and narrative advancement are the same track.

## Mission map (main-story chapters)

These are the mission/chapter names that group the Quest progression:

| Mission # | Mission Name | Quest Range | Level Range |
|---|---|---|---|
| 1 | The Bandit Road | Quests 1–4 | Levels 1–4 |
| 2 | The Shadow Court | Quests 5–7 | Levels 5–7 |
| 3 | The Sky Castle | Quests 8–11 | Levels 8–11 |
| 4 | The Great Hunt | Quests 12–15 | Levels 12–15 |
| 5 | The Fallen Keep | Quests 16–18 | Levels 16–18 |
| 6 | The Witch Hunt | Quests 19–22 | Levels 19–22 |
| 7 | The Cursed Woods | Quests 23–26 | Levels 23–26 |
| 8 | The Sunken Tower | Quests 27–29 | Levels 27–29 |
| 9 | The Dragon's Keepers | Quest 30 | Level 30 |
| 10 | The Cataclysm | Quest 31 | Level 30 (finale) |

- **Quest 0** functions as the pre-mission onboarding/tutorial setup before Mission 1 begins.

## Structure by phase

## Phase 0 — Onboarding (Quest 0)

- You start with the initial party: **Risa, Robin, Aldric**, each with **Signature 1**.
- Early consumables/systems are unlocked immediately (Health Potion, Healing Tonic, Family Seal).
- This establishes baseline combat rhythm before enemy puzzle solving begins.

## Phase 1 — Class-basics gauntlet (Quests 1–4)

- Quests 1–3 are trio encounters introducing core enemy class pairings:
  - Warden/Guard pressures,
  - Rogue/Shock pressure,
  - Mage/Burn pressure.
- Reward pacing unlocks additional basics and crafting support.
- Quest 4 is the first synthesis check (“basic-class test”): mixed prior threats prove the player internalized first-tier fundamentals.
- End-of-phase reward recruits the first featured trio (**Roland, Hunold, Ella**), and opens class track progression for Rogue/Warden/Mage once baseline basics are met.

## Phase 2 — Noble/Warlock introduction (Quests 5–7)

- Quest 5 previews Noble control patterns.
- Quest 6 previews Warlock malice/dark pressure.
- Quest 7 is a mixed-class validation combining both previews.
- Successful completion recruits **Prince Charming** and **Pinocchio**, confirming understanding of cross-class interaction before broader roster scaling.

## Phase 3 — Second adventurer wave (Quests 8–11)

- Quests 8–10 each spotlight a second representative for specific archetypes:
  - Fighter second adventurer,
  - Rogue second adventurer,
  - Warden second adventurer.
- Rewards include targeted gear progression (Smoke Bomb, Iron Buckler), indicating build identity starts mattering beyond pure move literacy.
- Quest 11 is another wave test; clear recruits **Little Jack, Lucky Constantine, Porcus III**.

## Phase 4 — Backline utility and mixed support pressure (Quests 12–15)

- Quests 12–14 extend second-adventurer introductions for Ranger, Cleric, Mage.
- Enemy lines increasingly mix damage + utility + sustain, testing target priority rather than isolated matchup knowledge.
- Reward cadence includes utility gear (Hunter’s Net, Heart Amulet, Lightning Boots).
- Quest 15 wave test recruits **Frederic, Matchstick Liesl, March Hare**.

## Phase 5 — Second-copy completion and basics capstone (Quests 16–18)

- Quests 16 and 17 introduce second adventurers for Noble and Warlock.
- Quest 18 is an explicit “second-copy completion test” that verifies roster redundancy competence (using alternate units in familiar class roles).
- Reward recruits **Green Knight** and **Rumpelstiltskin**, while unlocking all **4th–5th basics** (major mechanical breadth jump).

## Phase 6 — Third adventurer rollout (Quests 19–22)

- Quests 19–21 begin third-adventurer exposure for Fighter, Rogue, and Warden.
- Enemy compositions now deliberately pressure adaptation to similar role outputs from different ability sets.
- Quest 22 wave test recruits **Gretel, Reynard, Lady of Reflections**.
- Arcane Focus reward reinforces escalating stat/ability specialization.

## Phase 7 — Third adventurer continuation (Quests 23–26)

- Quests 23–25 continue third-adventurer intros for Ranger, Cleric, Mage.
- Encounters emphasize control/status diversity and split-threat evaluation.
- Quest 26 wave test recruits **Briar Rose, Snowkissed Aurora, Witch of the Woods**.

## Phase 8 — End-of-tutorial mastery and Signature 3 unlock (Quests 27–29)

- Quests 27–28 finish Noble and Warlock third-adventurer tracks.
- Quest 29 is the **final roster test** (Rapunzel + Sea Wench Asha + Royal Ranger mirror pressure).
- Clear reward recruits **Rapunzel** and **Sea Wench Asha**, and globally unlocks **Signature 3** for all adventurers.
- This is the key handoff from guided learning to full-system play.

## Phase 9 — Exam and final boss (Quests 30–31)

- Quest 30 is the **final exam** against Apex Fighter/Cleric/Warden:
  - tests clean execution versus tuned basics + talents,
  - confirms readiness for boss-level mechanics.
- Quest 31 is the **final boss encounter** versus tri-head Dragon Head (Noble/Mage/Warlock variants):
  - each head carries Tyranny synergy around status stacking,
  - signatures pressure frontline and backline simultaneously,
  - demands understanding of status management, sequencing, and focus-fire timing.
- Completion unlocks **Ranked Glory ladder** and marks Fantasia completion.

## Quest language and combat role understanding

- In this progression, “battle” and “Quest” are equivalent terms; all battle lessons are framed as Quests.
- Formation literacy is explicit across Frontline, Backline Left, Backline Right enemy setups.
- Enemy kit design escalates from two-basic identities to talent/signature-driven synergies.
- Milestone Quests are regularly structured as **tests** (basic-class, mixed-class, wave tests, final roster test, final exam) to enforce mastery checkpoints.

## Design intent summary

The tutorial/main story uses a **teach -> test -> reward -> expand** loop:

1. Teach with focused enemy archetypes.
2. Test with mixed compositions.
3. Reward with recruits/items/unlocks.
4. Expand complexity via more classes, more copies, more signatures, and higher-status synergy.

By the time the Dragon Head Quest is cleared, the player has demonstrated practical command of class identity, formation reading, itemization, status interactions, and full-roster tactical planning.

## Step-by-step implementation plan for the current game

Below is a concrete implementation path to ship this main story campaign in the current codebase.

### 1) Add campaign data model (source of truth)

- Create a structured campaign config in `data.py` (or a new `campaign_data.py`) with:
  - Mission definitions (`mission_id`, `name`, `quest_range`, `level_range`).
  - Quest nodes (`quest_id`, `mission_id`, `enemy_lineup`, `key_preview`, `rewards`, `unlock_flags`).
  - Quest 0 onboarding metadata.
- Keep this data table-driven so balancing can happen without touching combat logic.

### 2) Add campaign progress state to runtime models

- Extend `BattleState` / persistent profile model in `models.py` to track:
  - `current_quest`, `highest_quest_cleared`, `current_mission`.
  - unlocked adventurers, unlocked basics tiers, unlocked signatures, unlocked items.
  - per-quest clear status (unplayed / cleared / perfected if desired).
- Add helper methods for reading unlock status and next available Quest.

### 3) Implement unlock application pipeline

- In `logic.py`, add `apply_quest_rewards(profile, quest_id)`:
  - grant recruits,
  - grant items,
  - unlock basics/signatures,
  - set mission progression flags.
- Make this deterministic and idempotent (safe to re-run on loaded save).

### 4) Build quest enemy preset loader

- Add a function in `logic.py` (or `data.py`) that converts quest enemy definitions into runtime teams:
  - Frontline / Backline Left / Backline Right slots,
  - fixed basics/talent/signature kits for quest enemies,
  - fixed items where relevant (Apex set, Dragon Head loadouts).
- Reuse existing `create_team` pathways as much as possible to avoid duplicate construction logic.

### 5) Add a campaign mode to the main loop

- In `main.py`, add a `game_mode = "campaign"` branch in phase flow:
  - `menu -> mission_select -> quest_select -> pre_quest -> battle -> post_quest_results`.
- Keep existing PvP loop unchanged; campaign should be an additional mode, not a replacement.

### 6) Add mission/quest selection UI

- In `ui.py`, add screens/components for:
  - Mission list (1–10 names),
  - Quest grid/list under each mission,
  - lock badges for unavailable quests,
  - reward preview panel (recruits/items/unlocks).
- In quest row labels, always use **Quest** terminology (not battle).

### 7) Gate roster/build options by campaign unlocks

- Update team-building UI and selection validation (`main.py` + `logic.py`) so players can only choose:
  - unlocked adventurers,
  - unlocked basics tiers,
  - unlocked signatures,
  - unlocked items.
- Ensure preview text explains *why* an option is locked.

### 8) Script tutorial guidance triggers by Quest bands

- Add contextual tutorial prompts (lightweight overlays/tooltips in `ui.py`) for key learning checkpoints:
  - Quests 1–4 class basics,
  - Quests 5–7 Noble/Warlock intro,
  - wave tests, final roster test, final exam, final boss.
- Mark prompts as seen to avoid repeated spam.

### 9) Implement mission completion and chapter transitions

- After each quest clear, evaluate whether that mission range is complete:
  - show mission-complete panel,
  - highlight newly unlocked mission/Quest,
  - show newly granted roster/item/signature content.
- Include special transition beats for Mission 9 -> 10 (Quest 30 to Quest 31).

### 10) Add final exam and final boss bespoke handling

- For Quest 30 and Quest 31, add explicit result handling in `logic.py` and `main.py`:
  - exam clear flag,
  - final campaign complete flag,
  - unlock Ranked Glory on Quest 31 clear.
- Add post-credit/end-state screen in `ui.py` summarizing completion and unlocked mode(s).

### 11) Add save/load support for campaign persistence

- Add profile serialization (JSON is sufficient initially):
  - quest completion,
  - unlock state,
  - tutorial prompt seen flags,
  - selected team loadout presets if needed.
- Hook save after quest clear and on clean exit; load at game start.

### 12) Add validation tools and regression checks

- Add an audit script (similar to `audit_game_systems.py`) for campaign integrity:
  - every quest has valid mission mapping,
  - reward ids exist in roster/items/ability definitions,
  - no impossible unlock ordering,
  - mission names/ranges match the spec table.
- Add lightweight automated smoke checks for:
  - first playable quest from new save,
  - unlock after Quest 4, 7, 11, 15, 18, 22, 26, 29, 31.

### 13) Rollout sequence (recommended implementation order)

1. Data model + quest tables.
2. Progress state + save/load.
3. Reward application + unlock gating.
4. Enemy preset loader.
5. Campaign loop in `main.py`.
6. Mission/quest UI.
7. Tutorial prompts.
8. Final exam/boss bespoke endgame handling.
9. Audit + smoke tests.

This order reduces risk by validating progression correctness before UI polish and ensures the core Quest progression is fully functional early.
