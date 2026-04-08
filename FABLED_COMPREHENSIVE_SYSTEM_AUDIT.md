# Fabled Comprehensive System Audit

## Purpose
This document is a holistic, code-grounded audit of the current Fabled build. It is intended to function as a combined rules reference, systems map, implementation snapshot, content index, and current-state design audit.
It uses two sources of truth together: the current `rulebook.txt` and the live Python implementation that powers combat, quests, progression, UI flow, LAN play, economy, and AI behavior.

## Source Of Truth
- Primary rules reference: `rulebook.txt`
- Combat engine: `quests_ruleset_logic.py`, `quests_ruleset_models.py`, `quests_ruleset_data.py`
- Ranked / quest progression: `storybook_ranked.py`, `storybook_mode.py`
- Progression and account state: `storybook_progression.py`, `models.py`, `campaign_save.py`
- Shell content and store/meta data: `storybook_content.py`, `economy.py`
- AI systems: `quests_ai_battle.py`, `quests_ai_quest.py`, `quests_ai_quest_loadout.py`, `quests_ai_runtime.py`
- Runtime and presentation shell: `main.py`, `settings.py`, `storybook_ui.py`
- LAN transport: `net.py`, `storybook_lan.py`

## Executive Snapshot
| Area | Current Build State |
| --- | --- |
| Game title | `Fabled` |
| Render canvas | `1400 x 900` internal canvas, fullscreen scaled |
| Target framerate | `60` FPS |
| Adventurers | `30` |
| Class groups | `6` |
| Total class skills | `12` |
| Artifacts | `38` |
| Ultimate meter cap | `7` |
| Ultimates required for instant win | `3` |
| Starting Reputation | `300` |
| Reputation bounds | `1` to `2000` |
| Story quests defined | `4` |
| Bout modes defined | `2` |
| Market tabs | `5` |
| Live cosmetic inventory entries | `0` |

## Reading Guide
1. Sections 1-8 explain the game holistically: combat, loadouts, quests, shell flow, progression, LAN, and AI.
2. Sections 1-9 cover the top-level audit, and the appendices hold the exhaustive content reference.
3. Appendices A-C enumerate every adventurer, class skill, and artifact in the current code-backed dataset.

## 1. Core Game Structure
Fabled is a tactical, turn-based, position-sensitive combat game built around small-team encounters. The central loop is: build a party of six, refine loadouts, scout the enemy, bring three into a formation-based encounter, plan all actions simultaneously, then resolve them in initiative order.

### 1.1 The Three Nested Scales Of Play
- **Account scale**: gold, EXP, level, rank, Reputation, favorite rules, cosmetics, and friends/LAN entries.
- **Quest scale**: a six-member quest party, per-run wins/losses/streaks, repeated encounter prep, and forfeit / end-of-run resolution.
- **Encounter scale**: three active adventurers per side, formation, action planning, bonus actions, meter race, and knockout pressure.

### 1.2 Core Combat Identity
- Position matters as much as raw numbers.
- Action timing matters because players lock all actions before resolution.
- Weapon choice matters because primary weapon defines the active strike and attached passive/spell package.
- Class and artifact matter because they change statlines, bonus actions, utility access, and matchup adaptability.
- Ultimate pacing matters because the third ultimate cast wins immediately.

## 2. Combat System Audit
### 2.1 Encounter Size And Formation
- Each encounter is **3 versus 3**.
- Slot model: `front`, `back_left`, `back_right`.
- One adventurer must occupy the frontline.
- Up to two adventurers can occupy the backline.
- Backline units suffer **-50 Speed**.
- If the frontline adventurer is knocked out, the **leftmost backline** adventurer immediately advances.

### 2.2 Round Structure
Each round is processed in the following order:
1. Initiative check
2. Start-of-round effects
3. Action selection
4. Action resolution in initiative order
5. Bonus action selection
6. Bonus action resolution in initiative order
7. End-of-round effects and duration/cooldown ticking

### 2.3 Initiative
- Initiative is primarily sorted by effective Speed after all current modifiers.
- Backline penalty is applied before ordering.
- Shock lowers Speed by 25.
- Current code uses deterministic ordering, then layers special exceptions such as Reynard's initiative jump from **Glowing Trail**.

### 2.4 Action Types
The battle planner supports the five rulebook action types plus ultimate selection when the meter is full:
- Strike
- Spellcast
- Switch
- Swap
- Skip
- Ultimate

### 2.5 Strikes
#### Melee
- User must normally be in the frontline.
- Targets the enemy frontline unless targeting rules are overridden.
- Spotlight allows melee to target spotlighted enemies in the backline.

#### Ranged
- Can target the enemy frontline.
- Can target the enemy directly across from the attacker.
- Consumes ammo unless the attack or passive says otherwise.

#### Magic
- Can target the enemy frontline.
- Can target the enemy directly across from the attacker.
- Counts as casting a spell for spell-related interactions.
- Uses cooldown instead of ammo.

#### Damage Formula
```text
Damage = ceil(Power x (Attack / Defense))
```
- Spread strikes hit all legal targets, then halve damage unless a rule explicitly ignores the spread penalty.
- Guard reduces incoming damage by 15%.
- Expose increases incoming damage by 15%.
- Weaken lowers outgoing damage by 15%.
- Recoil and lifesteal are applied after damage resolution where appropriate.

### 2.6 Spells
- Enemy-targeting spells can target the enemy frontline or the enemy directly across.
- Ally-targeting spells can target any ally.
- After use, spells go on cooldown unless an override prevents it.
- Triggered reactive artifact spells count as spell casts for interaction checks such as Arcane and anti-reactive effects.

### 2.7 Switch
- Swaps primary and secondary weapon.
- Resets cooldowns tied to either weapon.
- Fully reloads ranged ammo.
- Also enables specific synergy windows such as Armed reload-free openers and weapon-based tempo loops.

### 2.8 Swap
- Swaps positions with an ally.
- If the ally has not yet acted this round, they act from the new slot.
- Root prevents choosing Swap.
- Multiple class skills, artifacts, and innates are designed around Swap timing.

### 2.9 Skip
- Deliberately passes action selection for that actor.
- Rare in optimal play, but supported by both player UI and AI.

### 2.10 Ultimate Meter And Win Condition
Current engine assumptions, matching the rulebook and code:
- Strike: `+1` meter
- Melee Strike: `+2` meter
- Non-Arcane normal Spell cast: `+0` meter
- Arcane spell cast: `+1` meter
- Arcane Magic Strike: base Strike meter plus `+1` because it counts as casting a spell
- Reactive spell trigger: `+0` meter by default, `+1` if the user has Arcane
- Meter cap: `7`
- An ultimate can be selected only when the meter is already full at action-selection time.
- Casting an ultimate resets the meter to 0, except Goose Quill retains half the meter.
- Goose Quill retained meter value in code: `4`
- The `3`rd ultimate cast by a side wins immediately.
- A side also loses immediately when all three active encounter members are knocked out.

### 2.11 Conditions And Stat Modifiers
| Condition | Rulebook/System Effect |
| --- | --- |
| Burn | 8% max HP damage each round. Burn synergies also drive anti-heal and healing transfer effects. |
| Root | Prevents Swap. Also unlocks several control/payoff mechanics. |
| Shock | -15 Speed and 15% recoil on Strikes. |
| Weaken | 15% less damage dealt. |
| Expose | 15% more damage taken. |
| Guard | 15% less damage taken. |
| Spotlight | Allows melee targeting of a backline unit. |
| Taunt | Restricts target selection to the taunter where relevant. |

Additional implementation notes:
- Same status type does not stack.
- Reapplying a status refreshes duration to the higher of current and new duration.
- Root Immunity is implemented as a helper state and also **cleanses Root** when gained.
- Stat bonuses and penalties do not stack; effective stat uses the highest positive and highest negative.

### 2.12 Combatant Runtime State
Each active combatant effectively carries:
- Base adventurer definition
- Current loadout
- HP
- KO state
- Slot / position
- Status list
- Buff and debuff lists
- Cooldowns
- Ammo remaining by weapon
- Markers/counters for unique kits
- Queued normal action
- Queued bonus action

## 3. Loadouts, Classes, And Artifacts
### 3.1 Loadout Components
Every combat-ready adventurer is defined by:
- Chosen primary weapon
- Chosen secondary weapon
- Chosen class
- Chosen class skill
- Chosen artifact, or no artifact

### 3.2 Class Uniqueness
- Within a quest party of six, each class can appear only once.
- This matters before the encounter because the entire quest party must remain class-legal.
- It also matters at bring-three time because all encounter members inherit those fixed class assignments.

### 3.3 Artifact Uniqueness
- A party can hold only one copy of each artifact.
- An artifact may be carried unattuned, but its spell cannot be used unless the current class is attuned to it.
- Training Grounds is the one place where all artifacts are freely available regardless of permanent ownership.

### 3.4 Effective Stat Calculation
- Base stat
- Plus artifact stat bonus if applicable
- Plus highest active bonus
- Minus highest active penalty
- Plus/Minus positional or special kit modifiers

Implementation-specific notes:
- Ali Baba ignores stat bonuses and penalties from buff/debuff systems, but still keeps base values and relevant artifact stat bonus.
- Bulwark grants +15 Defense in the frontline and +5 Defense otherwise.

## 4. Quest System Audit
### 4.1 Quest Structure
- Quests are competitive multi-encounter runs.
- The run ends after the player accumulates three encounter losses.
- Encounter wins update Reputation via Elo-based delta (+8 to +30).
- Encounter losses reduce Reputation by a flat -10.

### 4.2 Favorite Rules
- Outside Training Grounds, the player can set as favorite only Little Jack plus adventurers they have previously quested with.
- Training Grounds maintains a separate training favorite with full-roster access.
- Current profile defaults seed both quest and training favorite to `little_jack`.

### 4.3 Quest Start Flow
Current implemented quest flow:
1. Player starts a quest from Guild Hall.
2. The system offers **9 adventurers**, including the current quest favorite.
3. The player chooses **6** to form the quest party.
4. The player sets or edits loadouts for the party of six.
5. Each encounter later lets the player re-edit those loadouts before committing.

### 4.4 Encounter Prep Flow
For each encounter:
1. Loadouts can be edited again.
2. The enemy party of six is shown.
3. The player chooses which three to bring.
4. The player assigns formation positions.
5. Battle begins.

### 4.5 Quest Rewards
#### Gold
- Quest encounters do not award Gold directly.
- Quest-end bonus: 150 Gold at 5+ wins, 300 Gold at 10+ wins.

#### Reputation
```text
ExpectedScore = 1 / (1 + 10^((OpponentRep - PlayerRep) / 400))
BaseChange = 28 x (ActualScore - ExpectedScore)
Win delta = clamp(round(BaseChange + WinstreakBonus), 8, 30)
WinstreakBonus = min(current quest winstreak before win, 5) x 2
Loss delta = -10 (flat)
```
- Reputation is clamped into the ranked range.

#### Match Rating
```text
Match Rating = Reputation + (20 x current winstreak) - (15 x current lossstreak)
```

### 4.6 Forfeit
- The current quest can be forfeited.
- Forfeit cost is **10 Reputation per remaining loss slot**.
- Example: if the player has 1 loss already, 2 losses remain, so the penalty is 20 Reputation.

### 4.7 Ranked Ladder
| Rank | Reputation Floor |
| --- | --- |
| Squire | 1 |
| Knight | 200 |
| Baron | 400 |
| Viscount | 600 |
| Earl | 800 |
| Margrave | 1000 |
| Duke | 1200 |
| Prince | 1400 |
| King | 1600 |
| Emperor | 1800 |

### 4.8 Current Account Defaults Relevant To Quests
- All adventurers available via draft; no fixed starter roster.
- Starter unlocked classes: None
- Starter quest favorite: `little_jack`
- Starter training favorite: `little_jack`
- Initially quested adventurer set: little_jack

## 5. Other Play Modes And Shell Systems
### 5.1 Training Grounds
- One-encounter practice flow.
- Supports AI or LAN.
- Uses a separate training favorite rather than overwriting the normal quest favorite.
- All artifacts are available regardless of ownership.

### 5.2 Bouts
Defined bout shells in current content data:
- **Random Bout**: Pick from a random shared pool of nine adventurers. Both players draft from the same pool. Adapt your picks to what your opponent leaves.
- **Focused Bout**: Select from your full roster, then build your loadout. Bring the team you know. No pool restrictions — full roster selection before battle.

### 5.3 Story Quests
- **Embers Under Briarhold** (`Briarhold Keep`): A rootbound garrison is choking the western road. Break the line before the court's supply wagons vanish into the fog. Difficulty: Veteran. Rewards: 320 Gold, 28 EXP. Threat: Heavy control and slow pressure. Note: Bring at least one backline carry. Roots and speed penalties stack quickly here.
- **The Gilded Conspiracy** (`The Gilt Exchange`): Mercenary bookkeepers have turned the market floor into a dueling hall. Survive the opener and cut through their defense shells. Difficulty: Champion. Rewards: 410 Gold, 34 EXP. Threat: Frontline defense and artifact tempo. Note: Expose and spotlight are unusually valuable. Expect artifact spells early.
- **Chorus In The Mire** (`Fen of Hollow Lanterns`): A drowned chorus is calling travelers off the path. Enter the mire, sever the song, and leave before the water learns your name. Difficulty: Heroic. Rewards: 520 Gold, 40 EXP. Threat: Shock, recoil, and magic burst. Note: Backline speed matters more than raw attack. Consider a fast cleanser or weapon switch plan.
- **The Clockwork Vow** (`The Brass Reliquary`): A vow-engine beneath the city walls is awakening. Draft a compact strike team and break it before the noble houses bind it to their war banners. Difficulty: Legend. Rewards: 650 Gold, 48 EXP. Threat: Scaling bruisers and delayed finishers. Note: Do not overload on slow tanks. You need enough tempo to punish scaling ultimates.

### 5.4 LAN
- Uses TCP plus a UDP probe on port `55667`.
- Probe request: `FABLED_PROBE`
- Probe reply: `FABLED_HERE`
- Friends menu stores manual name + IP pairs for LAN targeting.
- Networking is intentionally lightweight rather than a full online service stack.

## 6. Progression, Economy, And Meta Systems
### 6.1 Player Leveling
- No level cap (uncapped progression)
- EXP formula: `level × 100` to advance to next level
- Level-up Gold formula: `50 + (10 × new_level)`

#### Level Curve (sample)
| Level | EXP To Next | Level-Up Gold |
| --- | --- | --- |
| 1 | 100 | 70 |
| 2 | 200 | 80 |
| 3 | 300 | 90 |
| 4 | 400 | 100 |
| 5 | 500 | 110 |
| 6 | 600 | 120 |
| 7 | 700 | 130 |
| 8 | 800 | 140 |
| 9 | 900 | 150 |
| 10 | 1000 | 160 |
| 11 | 1100 | 170 |
| 12 | 1200 | 180 |
| 13 | 1300 | 190 |
| 14 | 1400 | 200 |
| 15 | 1500 | 210 |
| 16 | 1600 | 220 |
| 17 | 1700 | 230 |
| 18 | 1800 | 240 |
| 19 | 1900 | 250 |
| 20 | 2000 | 260 |

### 6.2 Gold Sources
- Level-up bonuses: `50 + (10 × new_level)` Gold

### 6.3 Artifact Economy
- Artifacts are no longer sold individually; they enter the run pool via draft at quest/bout start.
- Armory tabs (legacy reference): Artifacts

### 6.4 Market And Cosmetics
- Market tabs: Featured, Outfits, Chairs, Adventurer Skins, Emotes
- Closet tabs: Outfits, Chairs, Emotes, Adventurer Skins
- Current explicit cosmetic entries in `MARKET_ITEMS`: `0`

## 7. User Interface And Navigation Audit
### 7.1 Main Shell
- The application renders to a fixed `1400 x 900` internal canvas, fullscreen-scaled.
- All mouse input is remapped from fullscreen display coordinates to canvas coordinates before any UI handler sees it.
- The UI is a single-window screen-state router: one active screen draws each frame, and button return dicts are used by `main.py` to transition between states.
- A persistent top bar occupies `(0, 0, 1400, 56)` on every screen and carries title, subtitle, back arrow, Settings, Quit, and a compact Gold/Rep/Level readout.
- Background uses concentric circles centered near `(700, 490)` plus scattered gold glow circles; a gold separator line sits at y=54.

### 7.2 Current Route Inventory
- `main_menu`
- `player_menu`
- `market`
- `inventory`
- `friends`
- `guild_hall`
- `shops / armory`
- `closet`
- `favored_adventurer_select`
- `quests_menu`
- `quest_party_loadout`
- `training_grounds`
- `quest_draft`
- `quest_loadout`
- `bouts_menu`
- `bout_lobby`
- `bout_draft`
- `bout_loadout`
- `battle`
- `results`
- `lan_setup`
- `catalog`
- `settings`

### 7.3 Screen-By-Screen Navigation Map
| Screen | Entry Point(s) | Exits To |
| --- | --- | --- |
| `main_menu` | App launch | `guild_hall` (Guild Hall btn), `market` (Market btn), `player_menu` (Profile panel click), `settings` (S btn), quit |
| `player_menu` | main_menu > Profile | `friends`, `closet`, `favored_adventurer_select` (favorite card), back → main_menu |
| `friends` | player_menu | back → player_menu |
| `closet` | player_menu | back → player_menu |
| `favored_adventurer_select` | player_menu (favorite card) | back → player_menu (confirm sets favorite) |
| `guild_hall` | main_menu > Guild Hall btn | `quests_menu` / quest start, `training_grounds`, `shops / armory`, `catalog`, back → main_menu |
| `quests_menu` | guild_hall | `quest_party_loadout` (edit loadouts), `quest_draft` (prepare encounter / start quest), back → guild_hall |
| `quest_party_loadout` | quests_menu | back → quests_menu (done saves loadouts) |
| `quest_draft` | quests_menu (prepare encounter) | `quest_loadout` (continue after picks), back → quests_menu |
| `quest_loadout` | quest_draft | `battle` (confirm formation), back → quest_draft |
| `training_grounds` | guild_hall | `quest_loadout` (after AI/LAN pick + favorite selection), back → guild_hall |
| `shops / armory` | guild_hall | back → guild_hall |
| `catalog` | guild_hall | back → guild_hall |
| `market` | main_menu | back → main_menu |
| `inventory` | (currently unused active route — available as player_menu sub) | back |
| `bouts_menu` | (bout entry point) | `bout_lobby` (AI/LAN), back |
| `bout_lobby` | bouts_menu | `bout_draft` (begin), back → bouts_menu |
| `bout_draft` | bout_lobby | `bout_loadout` (after 3 picks), back → bout_lobby |
| `bout_loadout` | bout_draft | `battle` (confirm), back → bout_draft |
| `battle` | quest_loadout / bout_loadout | `results` (after battle ends) |
| `results` | battle | continue (next encounter or quest end), rematch, return → quest menu or main |
| `lan_setup` | training_grounds / bout_lobby | back |
| `settings` | any screen via S btn | back → originating screen |

### 7.4 Key Layout Constants Per Screen
All coordinates are in the `1400 x 900` canvas space. Top bar always at `(0, 0, 1400, 56)`.
| Screen | Major Panel(s) |
| --- | --- |
| main_menu | Profile `(74,138,310,320)`, Guild Hall `(430,168,380,330)`, Market `(850,168,380,330)` |
| player_menu | Avatar `(124,156,360,456)`, Progress `(516,156,330,456)`, Actions `(878,156,272,456)` |
| friends | Friend Ledger `(74,108,344,726)`, Friend Entry `(448,108,844,430)`, LAN Status `(448,566,844,268)` |
| guild_hall | Quest Desk `(86,132,680,270)`, Training `(86,438,324,238)`, Armory `(442,438,324,238)`, Catalog `(798,438,324,238)` |
| training_grounds | Roster `(56,108,486,726)`, Detail `(560,108,402,726)`, Options `(986,108,248,726)` |
| market | Tabs `(44,86,1312,102)`, List `(54,210,734,604)`, Preview `(816,210,486,604)` |
| closet | Categories `(48,104,244,730)`, Preview `(320,104,432,730)`, Inventory `(780,104,528,730)` |
| shops / armory | Info `(58,168,286,620)`, Inventory `(370,168,566,620)`, Detail `(962,168,312,620)` |
| catalog | Sections `(42,88,220,770)`, Filters `(288,88,504,170)`, List `(288,282,504,576)`, Detail `(818,88,540,770)` |
| quests_menu | Party `(120,144,560,612)`, Status `(710,144,530,286)`, Enemy `(710,470,530,286)` |
| quest_party_loadout | Party List `(40,104,388,744)`, Detail `(452,104,604,744)`, Rules `(1080,104,276,744)` |
| quest_draft | Cards grid, Formation `(230,642,486,194)`, Enemy `(726,642,176,194)`, Detail `(920,96,434,740)` |
| quest_loadout | Formation `(44,104,408,744)`, Detail `(476,104,540,744)`, Summary `(1040,104,316,744)` |
| battle | Log `(28,176,196,484)`, Battlefield center, Action plan `(224,696,938,160)`, Inspect `(1176,176,196,484)` |
| results | Center panel `(320,160,760,520)` |
| lan_setup | Role `(118,164,356,432)`, Connection `(522,164,356,432)`, Status `(926,164,356,432)` |
| settings | Preferences `(380,198,640,320)` |

### 7.5 Interaction Patterns
- **Click** is the primary interaction for all buttons, adventurer cards, formation slots, list entries, tabs, and panel tiles.
- **Hover** drives visual feedback (border highlights, glow rects, color shifts) on all interactive elements and triggers status-word tooltips in any description text.
- **Mouse wheel / scroll** is supported on roster grids, inventory lists, catalog entry lists, and detail viewports. Scroll state is tracked as an integer offset passed into draw functions.
- **Text input** (keyboard) is active on Friends (name/IP fields) and LAN Setup (IP field). The active field is toggled by clicking the text-input rect.
- **No drag** interactions exist — all repositioning is done via click-to-select + click-to-place (e.g., formation slots in quest_loadout).

### 7.6 Catalog
- Catalog sections: Adventurers, Class Skills, Artifacts
- Adventurers tab is a full roster reference.
- Class Skills tab groups the six classes and their three skills each.
- Artifacts tab is a non-store encyclopedia version of the Armory.

### 7.7 Settings
- Current implemented settings are lightweight rather than a large options suite.
- Key toggles presently exposed in code are tutorial popups and fast battle resolution.

## 8. AI And Simulation Audit
### 8.1 AI Stack
- **Quest roster / loadout AI**: `quests_ai_quest_loadout.py`
- **Encounter bring-three selector**: `quests_ai_quest.py`
- **Battle planner**: `quests_ai_battle.py`
- **Runtime wrappers / simulation harness**: `quests_ai_runtime.py` and reporting scripts

### 8.2 Quest Opponent Flow
Current quest AI follows the same macro flow the player does:
1. Receive a 9-adventurer offer
2. Choose 6 for the quest party
3. Assign blind quest loadouts to those 6
4. See the opposing party of 6
5. Choose the best 3 and formation
6. Play the battle tactically

### 8.3 Battle AI
- Generates legal actions per unit.
- Scores local actions, then assembles action bundles.
- Predicts enemy bundles and scores robustly rather than greedily.
- Repeats the same structure for bonus-action selection.
- Tracks meter race, status setup, lethal pressure, and positional access.

### 8.4 Difficulty Philosophy
- Lower difficulties search less and predict less.
- Higher difficulties model more enemy responses and keep more candidate bundles.
- Simulation / audit runs can use the strongest settings to stress the balance model.

## 9. Current Build Notes And Holistic Observations
### 9.1 What Is Fully Realized
- Complete combat engine with status, cooldown, ammo, switching, swapping, meter, ultimate, and KO replacement logic
- Full rulebook-backed adventurer/class/artifact dataset
- Ranked quest loop with drafting, re-loadouting, scouting, battle, result, and end-state handling
- Training Grounds AI/LAN practice shell
- LAN transport and friend IP book
- Player progression, gold, EXP, Reputation, rank, and favorite systems

### 9.2 What Is Present As Framework
- Market / Closet cosmetic shell exists, but live cosmetic inventory content is currently empty.
- Story quests and bout modes are defined as shell content data alongside the core ranked quest loop.

### 9.3 Important Design Tensions Visible In The Build
- The game has two very different strategic layers: blind quest-party construction and revealed-opponent encounter selection.
- Because the third ultimate wins instantly, long fights are never only attrition fights; they are also meter races.
- Position and target legality are strong enough that lineup/slot choice can be as impactful as raw loadout strength.
- Artifact choice is both a stat choice and an action-economy choice.
- Support/control units remain structurally important because cleanse, guard, spotlight, and anti-caster effects directly decide legal access and tempo.
## Appendix A. Adventurer Reference

### Red Blanchette
- **ID**: `red_blanchette`
- **Base Stats**: HP 390 | Attack 90 | Defense 100 | Speed 70
- **Innate Skill**: **Red and Wolf** — While below 50% max HP, Red has +25 Attack, +25 Speed, and her Strikes have 25% Lifesteal.
#### Signature Weapon 1: Stomach Splitter
- **Type / Meta**: Magic | Strike CD 2
- **Strike**: Marks the target for 2 rounds.; Power 80; Cooldown 2 round(s); Counts as spell; Applies to target: Mark (2r)
- **Passive Skills**:
  - **Wolf's Pursuit** — When a Marked enemy swaps, Red Strikes them. Special: `wolfs_pursuit`
#### Signature Weapon 2: Enchanted Shackles
- **Type / Meta**: Melee
- **Strike**: Power 115; Recoil 25%
- **Spells**:
  - **Blood Transfusion** — Average Red and target enemy's HP and set both Adventurers' HPs to that amount.; Cooldown 2 round(s); Special handler: `average_hp_with_target`
- **Ultimate Spell**: **Wolf Unchained** — For 2 rounds, Red and Wolf is always active and its effects are doubled.; Special handler: `wolf_unchained`

### Little Jack
- **ID**: `little_jack`
- **Base Stats**: HP 265 | Attack 85 | Defense 60 | Speed 115
- **Innate Skill**: **Giant Slayer** — Jack's Strikes deal +25 damage to enemies with higher max HP.
#### Signature Weapon 1: Skyfall
- **Type / Meta**: Melee | Strike CD 1
- **Strike**: Power 150; Cooldown 1 round(s)
- **Spells**:
  - **Cloudburst** — Jack's next Strike ignores targeting restrictions.; Cooldown 1 round(s); Special handler: `next_strike_ignore_targeting`
#### Signature Weapon 2: Giant's Harp
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: Power 100; Cooldown 1 round(s); Counts as spell
- **Passive Skills**:
  - **Belligerence** — Jack ignores 20% of the enemy's Defense. Special: `ignore_20_defense`
- **Ultimate Spell**: **Fell the Beanstalk** — Jack's next Strike ignores 100% of the enemy's Defense.; Special handler: `next_strike_ignore_all_defense`

### Witch-Hunter Gretel
- **ID**: `witch_hunter_gretel`
- **Base Stats**: HP 350 | Attack 95 | Defense 80 | Speed 100
- **Innate Skill**: **Sugar Rush** — When Gretel knocks out an enemy, she has +25 Attack and +25 Speed for 2 rounds.
#### Signature Weapon 1: Hot Mitts
- **Type / Meta**: Melee
- **Strike**: +50 Power if the target is Burned, otherwise Burns the target for 2 rounds.; Power 100; +50 Power vs Burn; Special handler: `burn_if_not_burned`
#### Signature Weapon 2: Crumb Shot
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: +65 Power if an ally picked up a crumb this round, otherwise drops a crumb on Gretel's position.; Power 65; Ammo Cost 1; Special handler: `crumb_shot`
- **Passive Skills**:
  - **Crumbs** — Allies can pick up crumbs Gretel has dropped by swapping to that position, restoring +65 HP. Special: `crumbs`
- **Ultimate Spell**: **In The Oven** — For 2 rounds, enemy Adventurers take +25 damage from all sources and Gretel and ally Adventurers restore +25 HP from all sources.; Special handler: `in_the_oven`

### Lucky Constantine
- **ID**: `lucky_constantine`
- **Base Stats**: HP 310 | Attack 95 | Defense 60 | Speed 150
- **Innate Skill**: **Shadowstep** — Constantine ignores targeting restrictions against Exposed targets.
#### Signature Weapon 1: Fortuna
- **Type / Meta**: Melee
- **Strike**: Swaps the target with the lowest health enemy.; Power 105; Special handler: `swap_target_with_enemy`
- **Spells**:
  - **Consensia** — Exposes target enemy for 2 rounds.; Cooldown 2 round(s); Applies to target: Expose (2r)
#### Signature Weapon 2: Cat'O'Nine
- **Type / Meta**: Melee
- **Strike**: Hits 9 times. Is not affected by Strike Damage bonuses.; Power 9; Special handler: `multihit_9`
- **Passive Skills**:
  - **Nine Lives** — Up to 3 times per encounter, Constantine survives Strikes from Exposed attackers at 1 HP. Special: `nine_lives`
- **Ultimate Spell**: **Eyes Everywhere** — For 2 rounds, enemies are Exposed and Constantine's Strikes steal 25 Defense for 2 rounds.; Special handler: `eyes_everywhere`

### Hunold the Piper
- **ID**: `hunold_the_piper`
- **Base Stats**: HP 320 | Attack 80 | Defense 70 | Speed 115
- **Innate Skill**: **Electrifying Trance** — Shocked enemies take +25 damage.
#### Signature Weapon 1: Lightning Rod
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: Shocks the target for 2 rounds. Does not consume Ammo against Shocked targets.; Power 65; Ammo Cost 1; Applies to target: Shock (2r); Special handler: `lightning_rod`
#### Signature Weapon 2: Golden Fiddle
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: If the target is Shocked, Roots and Spotlights them for 2 rounds and does not go on cooldown.; Power 85; Cooldown 1 round(s); Counts as spell; Special handler: `golden_fiddle`
- **Ultimate Spell**: **Mass Hysteria** — For 2 rounds, Hunold's Strikes are Spread and ignore targeting restrictions and the spread damage penalty.; Special handler: `mass_hysteria`

### Sir Roland
- **ID**: `sir_roland`
- **Base Stats**: HP 390 | Attack 50 | Defense 100 | Speed 35
- **Innate Skill**: **Silver Aegis** — Roland takes 60% less damage from the first incoming ability after swapping to frontline.
#### Signature Weapon 1: Pure Gold Lance
- **Type / Meta**: Melee
- **Strike**: Exposes the target for 2 rounds.; Power 105; Applies to target: Expose (2r)
- **Spells**:
  - **Knight's Challenge** — Taunt target enemy for 2 rounds.; Cooldown 2 round(s); Applies to target: Taunt (2r)
#### Signature Weapon 2: Pure Silver Shield
- **Type / Meta**: Melee
- **Strike**: Guards Roland for 2 rounds.; Power 95; Applies to self: Guard (2r)
- **Passive Skills**:
  - **Banner of Command** — Guard allies for 2 rounds when they Swap positions. Special: `banner_of_command`
- **Spells**:
  - **Shimmering Valor** — Roland cleanses his Guard and restores 65 HP + 35 HP per Guard turn remaining.; Heal 65; Cooldown 2 round(s); Special handler: `shimmering_valor`
- **Ultimate Spell**: **Final Stand** — Roland restores 150 HP. For 2 rounds, Silver Aegis is always active.; Heal 150; Special handler: `final_stand`

### Porcus III
- **ID**: `porcus_iii`
- **Base Stats**: HP 405 | Attack 50 | Defense 105 | Speed 25
- **Innate Skill**: **Bricklayer** — If a Strike would deal 20% max HP or more to Porcus, reduce damage by 35% and Weaken the attacker for 2 rounds.
#### Signature Weapon 1: Crafty Wall
- **Type / Meta**: Melee
- **Strike**: Bricklayer reduces all damage next round.; Power 100; Special handler: `crafty_wall`
- **Spells**:
  - **Not By The Hair** — Bricklayer activates on all Strikes this round. Goes first in turn order.; Cooldown 1 round(s); Special handler: `not_by_the_hair`
#### Signature Weapon 2: Mortar Mortar
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: Weakens the target for 2 rounds. Does not consume Ammo if Bricklayer activated this turn.; Power 65; Ammo Cost 1; Applies to target: Weaken (2r); Special handler: `mortar_mortar`
- **Ultimate Spell**: **Unfettered** — For 2 rounds, Porcus has +100 attack, -50 defense, and +100 speed.; Special handler: `unfettered`

### Lady of Reflections
- **ID**: `lady_of_reflections`
- **Base Stats**: HP 385 | Attack 50 | Defense 105 | Speed 70
- **Innate Skill**: **Reflecting Pools** — The Lady creates a Reflecting Pool for 2 rounds at her new position whenever she swaps. Strikes targeting Reflecting Pools reflect 25% of the damage onto the attacker, 50% if the Strike is Magic.
#### Signature Weapon 1: Excalibur
- **Type / Meta**: Melee | Strike CD 2
- **Strike**: Power 115; Cooldown 2 round(s)
#### Signature Weapon 2: Lantern of Avalon
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: The Lady Swaps positions.; Power 85; Cooldown 1 round(s); Counts as spell; Special handler: `self_swap_after_strike`
- **Passive Skills**:
  - **Postmortem Passage** — When a Strike deals fatal damage to an ally, they retaliate for 85 Power against the attacker. Special: `postmortem_passage`
- **Spells**:
  - **Drown in the Loch** — Target takes +15 damage from all sources for 2 rounds.; Cooldown 2 round(s); Special handler: `takes_plus_15_damage`
- **Ultimate Spell**: **Lake's Gift** — The Lady creates a Reflecting Pool for 2 rounds at her position. Then, if there's a fainted ally, she knocks herself out and revives the most recently fainted ally at her position at 50% HP. They get +25 Attack for 2 rounds.; Special handler: `lakes_gift`

### Ashen Ella
- **ID**: `ashen_ella`
- **Base Stats**: HP 280 | Attack 100 | Defense 90 | Speed 135
- **Innate Skill**: **Two Lives** — Ella cannot Switch weapons. Instead, she always has the Obsidian Slippers in the frontline and the Dusty Broom in the backline.
#### Signature Weapon 1: Obsidian Slippers
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: Burns targets for 2 rounds.; Power 100; Cooldown 1 round(s); Spread; Counts as spell; Applies to target: Burn (2r)
- **Passive Skills**:
  - **Struck Midnight** — When a Strike leaves Ella at 50% HP or less, she Swaps positions and heals 70 HP. Special: `struck_midnight`
#### Signature Weapon 2: Dusty Broom
- **Type / Meta**: Melee
- **Strike**: Power 10
- **Passive Skills**:
  - **Fae Blessing** — Ella is untargetable and cannot cast Spells. Special: `fae_blessing`
- **Ultimate Spell**: **Crowstorm** — For 2 rounds, Ella cannot Switch weapons, she is untargetable, and her Magic Strikes deal +8% max HP damage and do not go on cooldown.; Special handler: `crowstorm`

### March Hare
- **ID**: `march_hare`
- **Base Stats**: HP 280 | Attack 85 | Defense 55 | Speed 140
- **Innate Skill**: **Erratic** — When the March Hare Swaps positions, he Switches weapons.
#### Signature Weapon 1: Stitch in Time
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: +40 Power for each Spell the March Hare cast this round (includes this one). Shocks the target for 2 rounds.; Power 40; Cooldown 1 round(s); Counts as spell; Applies to target: Shock (2r); Special handler: `stitch_in_time_strike`
#### Signature Weapon 2: Cracked Stopwatch
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: If the target is Shocked, the March Hare gets an extra Action next round.; Power 50; Cooldown 1 round(s); Counts as spell; Special handler: `cracked_stopwatch`
- **Spells**:
  - **Rabbit Hole** — The March Hare Swaps positions. His next Spell does not go on cooldown.; Special handler: `rabbit_hole`
- **Ultimate Spell**: **Tea Party** — The March Hare and his allies each get an extra Action next round.; Special handler: `tea_party`

### Briar Rose
- **ID**: `briar_rose`
- **Base Stats**: HP 285 | Attack 70 | Defense 60 | Speed 125
- **Innate Skill**: **Curse of Sleeping** — The lowest HP Rooted enemy is unable to act each round but gains Root Immunity for 2 rounds at the end of round.
#### Signature Weapon 1: Spindle Bow
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: +30 Power if the target is Rooted.; Power 60; Ammo Cost 1; +30 Power vs Root
- **Spells**:
  - **Vine Snare** — Briar's next Strike removes Root Immunity and does not consume Ammo.; Cooldown 2 round(s); Special handler: `vine_snare`
#### Signature Weapon 2: Thorn Snare
- **Type / Meta**: Ranged | 1 Ammo
- **Strike**: Roots targets for 2 rounds.; Power 80; Ammo Cost 1; Spread; Applies to target: Root (2r)
- **Passive Skills**:
  - **Drowsiness** — Root enemies who Swap for 2 rounds. Special: `drowsiness`
- **Ultimate Spell**: **Falling Kingdom** — Root all enemies. For 2 rounds, Curse of Sleeping does not grant Root Immunity.; Special handler: `falling_kingdom`

### Wayward Humbert
- **ID**: `wayward_humbert`
- **Base Stats**: HP 310 | Attack 80 | Defense 70 | Speed 105
- **Innate Skill**: **Shifty Allegiance** — Humbert can Switch weapons as a Bonus Action.
#### Signature Weapon 1: Convicted Shotgun
- **Type / Meta**: Ranged | 2 Ammo
- **Strike**: Power 70; Ammo Cost 1
- **Passive Skills**:
  - **Trigger Finger** — Humbert's weapon combusts after it Strikes, gaining +35 Power but 50% Recoil and 2x Ammo use until repaired Special: `trigger_finger`
#### Signature Weapon 2: Pallid Musket
- **Type / Meta**: Ranged | 4 Ammo
- **Strike**: Repair Humbert's secondary weapon.; Power 55; Ammo Cost 1; Special handler: `repair_secondary_weapon`
- **Spells**:
  - **Liquid Courage** — Humbert restores 65 HP.; Heal 65; Cooldown 2 round(s)
- **Ultimate Spell**: **Jovial Shot** — Humbert fully restores HP. His next combusted Strike has 2x damage and 2x Recoil.; Special handler: `jovial_shot`

### Robin, Hooded Avenger
- **ID**: `robin_hooded_avenger`
- **Base Stats**: HP 290 | Attack 90 | Defense 60 | Speed 135
- **Innate Skill**: **Keen Eye** — Robin's Strikes can't be redirected and ignore Guard.
#### Signature Weapon 1: The Flock
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: Spotlights targets for 2 rounds.; Power 55; Ammo Cost 1; Spread; Applies to target: Spotlight (2r)
- **Spells**:
  - **Spread Fortune** — Robin ignores the spread damage nerf for 2 rounds.; Cooldown 2 round(s); Special handler: `spread_fortune`
#### Signature Weapon 2: Kingmaker
- **Type / Meta**: Melee
- **Strike**: +55 Power against backline targets.; Power 110; Special handler: `bonus_vs_backline_55`
- **Ultimate Spell**: **Disenfranchise** — For 2 rounds, Robin's Strikes steal 25 Attack, Defense, and Speed from its targets.; Special handler: `disenfranchise`

### Matchbox Liesl
- **ID**: `matchbox_liesl`
- **Base Stats**: HP 320 | Attack 70 | Defense 70 | Speed 120
- **Innate Skill**: **Purifying Flame** — Liesl and her allies are immune to Burn. Whenever an enemy takes damage from a Burn, Liesl's lowest HP ally restores HP equal to the amount.
#### Signature Weapon 1: Matchsticks
- **Type / Meta**: Ranged | 60 Ammo
- **Strike**: Burn the target for 2 rounds.; Power 40; Ammo Cost 1; Applies to target: Burn (2r)
- **Passive Skills**:
  - **Cauterize** — Burned enemies cannot heal. Special: `cauterize`
#### Signature Weapon 2: Eternal Torch
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: Power 85; Cooldown 1 round(s); Counts as spell; Lifesteal 30%
- **Passive Skills**:
  - **Flame of Renewal** — When Liesl is knocked out, allies restore 50% max HP. Special: `flame_of_renewal`
- **Ultimate Spell**: **Cleansing Inferno** — For 2 rounds, whenever Liesl or an ally restores HP, each of their allies restore that much HP, and whenever an enemy takes damage from a Burn, each other enemy takes that much damage.; Special handler: `cleansing_inferno`

### The Good Beast
- **ID**: `the_good_beast`
- **Base Stats**: HP 360 | Attack 80 | Defense 85 | Speed 85
- **Innate Skill**: **Protective Soul** — The first ally The Good Beast swaps with becomes his guest, and has +25 Defense.
#### Signature Weapon 1: Rosebush Sword
- **Type / Meta**: Melee
- **Strike**: +55 Power if the target Striked The Good Beast's guest last round.; Power 110; Special handler: `guest_bonus`
- **Spells**:
  - **Crystal Ball** — Spotlights the last enemy who Striked The Good Beast's guest for 2 rounds.; Cooldown 2 round(s); Applies to target: Spotlight (2r); Special handler: `guest_attacker_spotlight`
#### Signature Weapon 2: Dinner Bell
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: can target allies but not damage them. Allies restore HP equal to half the damage they would have taken.; Power 90; Cooldown 1 round(s); Counts as spell; Special handler: `ally_heal_from_damage`
- **Passive Skills**:
  - **Hospitality** — The Good Beast's guests restore +25 HP from all sources. Special: `hospitality`
- **Ultimate Spell**: **Happily Ever After** — For 2 rounds, The Good Beast and his guest have the higher of the two's Attack, Defense, and Speed.; Special handler: `happily_ever_after`

### The Green Knight
- **ID**: `the_green_knight`
- **Base Stats**: HP 350 | Attack 75 | Defense 80 | Speed 40
- **Innate Skill**: **Challenge Accepted** — The Green Knight may Swap positions as a Bonus Action.
#### Signature Weapon 1: The Search
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: +15 Power against targets in the Green Knight's lane.; Power 70; Ammo Cost 1; Special handler: `lane_bonus_15`
#### Signature Weapon 2: The Answer
- **Type / Meta**: Melee
- **Strike**: Power 115
- **Passive Skills**:
  - **Awaited Blow** — The Green Knight retaliates for 65 Power against incoming attackers not in his lane. Special: `awaited_blow`
- **Ultimate Spell**: **Fated Duel** — For 2 rounds, only those in the Green Knight's lane can act.; Special handler: `fated_duel`

### Rapunzel the Golden
- **ID**: `rapunzel_the_golden`
- **Base Stats**: HP 330 | Attack 80 | Defense 75 | Speed 55
- **Innate Skill**: **Flowing Locks** — Rapunzel can target a backline enemy with a Melee Strike once per encounter. Refreshes when she casts a Spell.
#### Signature Weapon 1: Golden Snare
- **Type / Meta**: Melee
- **Strike**: Root the target for 2 rounds.; Power 100; Applies to target: Root (2r)
- **Spells**:
  - **Lower Guard** — Refresh target enemy's Root duration and Expose them for 2 rounds.; Cooldown 2 round(s); Applies to target: Expose (2r); Special handler: `refresh_root_expose`
#### Signature Weapon 2: Ivory Tower
- **Type / Meta**: Melee
- **Strike**: Weakens the target for 2 rounds.; Power 95; Applies to target: Weaken (2r)
- **Spells**:
  - **Sanctuary** — Target ally restores 100 HP.; Heal 100; Cooldown 1 round(s)
- **Ultimate Spell**: **Severed Tether** — For 2 rounds, Rapunzel has -25 defense, +50 attack, and +50 speed and Flowing Locks is always active.; Special handler: `severed_tether`

### Pinocchio, Cursed Puppet
- **ID**: `pinocchio_cursed_puppet`
- **Base Stats**: HP 290 | Attack 80 | Defense 75 | Speed 125
- **Innate Skill**: **Growing Pains** — When Pinocchio ends the round in the frontline, he gains 1 Malice, up to 6. Pinocchio has +15 attack and +15 defense for each Malice.
#### Signature Weapon 1: Wooden Club
- **Type / Meta**: Melee
- **Strike**: +10 power per Malice.; Power 70; Special handler: `wooden_club`
- **Spells**:
  - **Bloodstain** — Pinocchio loses 65 HP and gains 2 Malice.; Special handler: `bloodstain`
#### Signature Weapon 2: String Cutter
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: 20% Lifesteal.; Power 85; Cooldown 1 round(s); Counts as spell; Lifesteal 20%
- **Passive Skills**:
  - **Become Real** — If Pinocchio has at least 3 Malice, his Spells do not go on cooldown and he is immune to status conditions. Special: `become_real`
- **Ultimate Spell**: **Blue Faerie's Boon** — For 2 rounds, Pinocchio has +25 speed and gains 6 Malice, up to 12.; Special handler: `blue_faeries_boon`

### Rumpelstiltskin
- **ID**: `rumpelstiltskin`
- **Base Stats**: HP 300 | Attack 70 | Defense 65 | Speed 120
- **Innate Skill**: **Art of the Deal** — The first time another Adventurer (ally or enemy) gains a stat bonus each round, Rumpelstiltskin also gains it.
#### Signature Weapon 1: Devil's Contract
- **Type / Meta**: Magic | Strike CD 2
- **Strike**: the target has +25 Attack, +25 Defense, and +25 Speed for 2 rounds.; Power 100; Cooldown 2 round(s); Counts as spell; Target buffs: Attack +25 (2r), Defense +25 (2r), Speed +25 (2r)
#### Signature Weapon 2: Spinning Wheel
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: Does not consume Ammo if Rumpelstiltskin has a stat bonus.; Power 75; Ammo Cost 1; Special handler: `spinning_wheel`
- **Spells**:
  - **Straw to Gold** — Rumpelstiltskin reverses target ally's stat penalty and steals it for 2 rounds, doubling it for the duration.; Cooldown 2 round(s); Special handler: `straw_to_gold`
- **Ultimate Spell**: **Double Down** — For 2 rounds, whenever Rumpelstiltskin gains a stat bonus it gets +25, and whenever he inflicts a stat penalty, it gets -25.; Special handler: `devils_nursery`

### Sea Wench Asha
- **ID**: `sea_wench_asha`
- **Base Stats**: HP 290 | Attack 85 | Defense 60 | Speed 130
- **Innate Skill**: **Stolen Voices** — When an enemy uses a nonattacking Spell, Asha steals it for 2 rounds. She can use it for the duration.
#### Signature Weapon 1: Frost Scepter
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: The target can't Strike next turn.; Power 90; Cooldown 1 round(s); Counts as spell; Special handler: `cant_strike_next_turn`
#### Signature Weapon 2: Mirror Blade
- **Type / Meta**: Magic
- **Strike**: Has the Power and effects of the last Strike that damaged Asha.; Counts as spell; Special handler: `mirror_blade`
- **Ultimate Spell**: **Foam Prison** — Asha steals target enemy's Ultimate Spell for 2 rounds and uses it.; Special handler: `foam_prison`

### Destitute Vasilisa
- **ID**: `destitute_vasilisa`
- **Base Stats**: HP 310 | Attack 85 | Defense 60 | Speed 105
- **Innate Skill**: **Mother's Presence** — Whenever Vasilisa or an ally are targeted by a Spell, Guard them for 2 rounds.
#### Signature Weapon 1: Guiding Doll
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: The next ally Strike against the target deals +40 damage and has 25% Lifesteal, affected by Vasilisa's healing effect bonuses.; Power 85; Cooldown 1 round(s); Counts as spell; Special handler: `guiding_doll`
#### Signature Weapon 2: Skull Lantern
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: +40 Power if Vasilisa or an ally are Guarded.; Power 80; Cooldown 1 round(s); Counts as spell; Special handler: `skull_lantern`
- **Passive Skills**:
  - **Guiding Light** — Vasilisa's Spells targeting enemies Spotlight the target for 2 rounds. Special: `guiding_light`
- **Ultimate Spell**: **Witch's Blessing** — For 2 rounds, Strikes against enemies have 25% Lifesteal.; Special handler: `witchs_blessing`

### Ali Baba, Bandit King
- **ID**: `ali_baba`
- **Base Stats**: HP 290 | Attack 70 | Defense 60 | Speed 145
- **Innate Skill**: **Open Sesame** — Ali Baba ignores stat bonuses and penalties (both his and his enemies).
#### Signature Weapon 1: Thief's Dagger
- **Type / Meta**: Melee
- **Strike**: Ali Baba can cast the target's Artifact's Spell as a Bonus Action this round.; Power 105; Special handler: `thiefs_dagger`
- **Spells**:
  - **Seal the Cave** — Increase target enemy's cooldowns by 1 round each.; Cooldown 2 round(s); Special handler: `seal_the_cave`
#### Signature Weapon 2: Jar of Oil
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: Burns the target for 2 rounds.; Power 90; Cooldown 1 round(s); Counts as spell; Applies to target: Burn (2r)
- **Passive Skills**:
  - **No Escape** — Enemy Adventurers cannot cast their Artifact's Spell if they are Burned or have a cooldown affected by Seal the Cave. Special: `no_escape`
- **Ultimate Spell**: **Forty Thieves** — For 2 rounds, enemies do not reload Ammo when they Switch weapons.; Special handler: `forty_thieves`

### Maui, Sun-Thief
- **ID**: `maui_sunthief`
- **Base Stats**: HP 385 | Attack 75 | Defense 100 | Speed 55
- **Innate Skill**: **Conquer Death** — Maui survives fatal damage at 1 HP once per encounter.
#### Signature Weapon 1: Whale-Jaw Hook
- **Type / Meta**: Melee
- **Strike**: Exposes the target for 2 rounds.; Power 105; Applies to target: Expose (2r)
- **Spells**:
  - **Swallow the Sun** — Maui and his allies have +25 Defense for 2 rounds.; Cooldown 2 round(s); Special handler: `swallow_the_sun`
#### Signature Weapon 2: Ancestral Warclub
- **Type / Meta**: Melee
- **Strike**: Power 115
- **Passive Skills**:
  - **Shapeshifter** — Maui uses Defense instead of Attack when dealing damage. Special: `shapeshifter`
- **Ultimate Spell**: **Raise the Sky** — Reset Conquer Death. Double Maui's Defense for 2 rounds.; Special handler: `raise_the_sky`

### Kama the Honeyed
- **ID**: `kama_the_honeyed`
- **Base Stats**: HP 300 | Attack 80 | Defense 65 | Speed 125
- **Innate Skill**: **Target of Affection** — Enemies in Kama's lane take +25 damage from ally Strikes.
#### Signature Weapon 1: Sugarcane Bow
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: Spotlight the target for 2 rounds.; Power 65; Ammo Cost 1; Applies to target: Spotlight (2r)
- **Passive Skills**:
  - **Flower Arrows** — Sugarcane Bow does not reload by Switching weapons. Other effects can pick up flower arrows to reload 1 Ammo. Special: `flower_arrows`
#### Signature Weapon 2: The Stinger
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: If the target is Spotlighted, Shocks them for 2 rounds and picks up a flower arrow.; Power 60; Ammo Cost 1; Special handler: `the_stinger`
- **Spells**:
  - **Suka's Eyes** — Suka Spotlights all enemies for 2 rounds.; Cooldown 2 round(s); Special handler: `sukas_eyes`
- **Ultimate Spell**: **Gaze of Love** — For 2 rounds, enemies are Spotlighted and Ranged Strikes do not consume Ammo against Spotlighted targets.; Special handler: `gaze_of_love`

### Reynard, Lupine Trickster
- **ID**: `reynard_lupine_trickster`
- **Base Stats**: HP 300 | Attack 80 | Defense 65 | Speed 140
- **Innate Skill**: **Opportunist** — Reynard deals +25 damage to targets that did not Strike last round.
#### Signature Weapon 1: Foxfire Bow
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: The target has -25 Defense for 2 rounds.; Power 65; Ammo Cost 1; Target debuffs: Defense +25 (2r); Special handler: `foxfire_bow`
- **Passive Skills**:
  - **Glowing Trail** — Reynard always acts first when he Strikes each round. Special: `glowing_trail`
#### Signature Weapon 2: Fang
- **Type / Meta**: Melee
- **Strike**: +50 Power if the target has a stat penalty.; Power 100; Special handler: `fang_bonus_vs_penalty`
- **Spells**:
  - **Silver Tongue** — Reynard Taunts target enemy for 2 rounds.; Cooldown 2 round(s); Applies to target: Taunt (2r)
- **Ultimate Spell**: **King of Thieves** — Reynard's next Strike steals 50 Attack from the target for 2 rounds.; Special handler: `king_of_thieves`

### Scheherazade, Dawn's Ransom
- **ID**: `scheherazade_dawns_ransom`
- **Base Stats**: HP 310 | Attack 65 | Defense 80 | Speed 110
- **Innate Skill**: **Thousand and One Nights** — When an enemy casts a Spell, if they cast a Spell this round, it has a +1 round cooldown.
#### Signature Weapon 1: Tome of Ancients
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: The target has -25 Speed for 2 rounds.; Power 80; Cooldown 1 round(s); Counts as spell; Target debuffs: Speed +25 (2r)
- **Passive Skills**:
  - **Stay the Blade** — While Scheherezade is frontline, enemy Strikes deal -25 damage. Special: `stay_the_blade`
#### Signature Weapon 2: Lamp of Infinity
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: The ally to the right of Scheherezade restores 65 HP.; Power 75; Cooldown 1 round(s); Counts as spell; Special handler: `lamp_of_infinity`
- **Passive Skills**:
  - **Evermore** — The first time each encounter Scheherezade or an ally would take fatal damage, they survive at 1 HP. Special: `evermore`
- **Ultimate Spell**: **Daybreak** — Clear the enemy Ultimate Meter. For 2 rounds, the enemy Ultimate Meter cannot be raised.; Special handler: `daybreak`

### Storyweaver Anansi
- **ID**: `storyweaver_anansi`
- **Base Stats**: HP 295 | Attack 80 | Defense 60 | Speed 140
- **Innate Skill**: **Tangled Plots** — While Anansi is frontline, enemies cannot cast Reactive Spells.
#### Signature Weapon 1: The Pen
- **Type / Meta**: Ranged | 8 Ammo
- **Strike**: Roots the target for 2 rounds.; Power 55; Ammo Cost 1; Applies to target: Root (2r)
- **Spells**:
  - **Silken Prose** — For 2 rounds, Strikes deal +8 damage to Rooted enemies.; Cooldown 2 round(s); Special handler: `silken_prose`
#### Signature Weapon 2: The Sword
- **Type / Meta**: Melee
- **Strike**: Can target backline enemies that cast an Artifact's Spell last round.; Power 105; Special handler: `anansi_sword`
- **Passive Skills**:
  - **The Twist!** — When Anansi Switches to The Sword, they get +25 Attack and -25 Speed for 2 rounds. Special: `the_twist`
- **Ultimate Spell**: **Web of Centuries** — For 2 rounds, Anansi can cast any Adventurer's Spell.; Special handler: `web_of_centuries`

### Odysseus the Nobody
- **ID**: `odysseus_the_nobody`
- **Base Stats**: HP 345 | Attack 90 | Defense 80 | Speed 95
- **Innate Skill**: **Cunning Retreat** — When Odysseus Swaps positions, he gets +25 Attack for 2 rounds.
#### Signature Weapon 1: Olivewood Spear
- **Type / Meta**: Melee
- **Strike**: +50 Power against targets in Odysseus' lane.; Power 100; Special handler: `olivewood_lane_bonus`
- **Spells**:
  - **Eye Piercer** — Odysseus' next Strike ignores targeting restrictions.; Cooldown 2 round(s); Special handler: `next_strike_ignore_targeting`
#### Signature Weapon 2: Beggar's Greatbow
- **Type / Meta**: Ranged | 3 Ammo
- **Strike**: Puts an arrow in the target.; Power 70; Ammo Cost 1; Special handler: `beggars_greatbow`
- **Passive Skills**:
  - **Barbed Arrows** — Beggar's Greatbow does not reload by Switching weapons. When Odysseus Switches weapons, his next Melee Strike deals +25 damage for each arrow in the target and fully reloads Beggar's Greatbow. Special: `barbed_arrows`
- **Ultimate Spell**: **Trojan Horse** — Odysseus Swaps positions and takes 0 damage from Strikes this round. For 2 rounds, Odysseus can Switch Weapons as a Bonus Action.; Special handler: `trojan_horse`

### Witch of the East
- **ID**: `witch_of_the_east`
- **Base Stats**: HP 305 | Attack 60 | Defense 70 | Speed 125
- **Innate Skill**: **Headwinds** — The Witch of the East creates an air current in her lane for 2 rounds when she Swaps positions and at the start of an encounter.
#### Signature Weapon 1: Zephyr
- **Type / Meta**: Magic | Strike CD 1
- **Strike**: Swaps the target with the enemy to their left.; Power 80; Cooldown 1 round(s); Counts as spell; Special handler: `zephyr`
- **Passive Skills**:
  - **Heavy Gale** — Enemies in an air current have -25 Attack. Special: `heavy_gale`
#### Signature Weapon 2: Comet
- **Type / Meta**: Melee
- **Strike**: The target takes +25 damage from the next Magic Strike.; Power 105; Special handler: `comet`
- **Passive Skills**:
  - **Unroof** — The Witch of the East and her allies have +25 Speed while in an air current. Special: `unroof`
- **Ultimate Spell**: **Dream Twister** — Create an air current in each lane for 2 rounds.; Special handler: `dream_twister`

### Tam Lin, Thornbound
- **ID**: `tam_lin_thornbound`
- **Base Stats**: HP 365 | Attack 60 | Defense 70 | Speed 55
- **Innate Skill**: **Faerie's Ransom** — The first time each round an enemy would inflict a status condition on Tam Lin, cleanse it and he has +25 Defense for 2 rounds.
#### Signature Weapon 1: Butterfly Knife
- **Type / Meta**: Melee
- **Strike**: Taunt the target for 2 rounds.; Power 100; Applies to target: Taunt (2r)
- **Passive Skills**:
  - **Bargain** — Enemies in Tam Lin's lane who Swap positions take +25 damage from Strikes for 2 rounds. Special: `bargain`
#### Signature Weapon 2: Beam of Light
- **Type / Meta**: Melee
- **Strike**: Burns the target for 2 rounds.; Power 100; Applies to target: Burn (2r)
- **Passive Skills**:
  - **Holy Water** — Allies have the effects of Faerie's Ransom. Special: `holy_water`
- **Ultimate Spell**: **Polymorph** — Target Adventurer becomes a beast for 2 rounds and can't swap and has +25 Attack, +25 Defense, +25 Speed, and their Strikes have 30% recoil (can be the user).; Special handler: `polymorph`

## Appendix B. Class Skill Reference

### Fighter
- **Martial** — The Adventurer's Melee Strikes deal +25 damage.
- **Vanguard** — The Adventurer's Melee Strikes deal 15 damage to each enemy behind the target. Special: `vanguard`

### Rogue
- **Covert** — The Adventurer can Swap positions as a Bonus Action. Special: `bonus_swap`
- **Assassin** — The Adventurer ignores targeting restrictions against enemies who did not Strike or Swap Positions. Special: `assassin`

### Warden
- **Bulwark** — The Adventurer has +15 Defense while in the frontline, +5 otherwise.
- **Vigilant** — The Adventurer is Guarded for 2 rounds when they Swap positions or Skip. Special: `vigilant`

### Mage
- **Arcane** — The Adventurer's Spells charge the Ultimate Meter +1. Special: `arcane`
- **Archmage** — The Adventurer's Magic Strikes do not go on cooldown in the frontline. Special: `archmage`

### Ranger
- **Deadeye** — The Adventurer's Ranged Strikes deal +5 damage.
- **Armed** — The Adventurer's first Ranged Strike after Switching weapons does not consume Ammo. Special: `armed`

### Cleric
- **Healer** — The Adventurer's healing effects restore an additional +15 HP.
- **Medic** — The Adventurer's healing effects cleanse status conditions and stat penalties. Special: `medic`

## Appendix C. Artifact Reference

### Wishing Table
- **ID**: `holy_grail`
- **Attunement**: Cleric, Fighter, Warden
- **Stat Bonus**: Defense +15
- **Reactive**: No
- **Spell**: **Table-Be-Set** — Target adventurer restores 65 HP and cleanses their newest status condition (can be the user).; Heal 65; Cooldown 1 round(s); Special handler: `cleanse_newest_status`

### Winged Sandals
- **ID**: `winged_sandals`
- **Attunement**: Ranger, Rogue, Warden
- **Stat Bonus**: Speed +15
- **Reactive**: No
- **Spell**: **The Swiftness** — The user Swaps positions with an ally and gets +25 Speed for 2 rounds.; Cooldown 2 round(s); Self buffs: Speed +25 (2r); Special handler: `artifact_swap_with_ally`

### Lightning Helm
- **ID**: `lightning_helm`
- **Attunement**: Fighter, Mage, Rogue
- **Stat Bonus**: Attack +15
- **Reactive**: No
- **Spell**: **Thunderclap** — The user's next Strike deals +25 damage and Shocks the target for 2 rounds.; Cooldown 2 round(s); Special handler: `next_strike_bonus_25_shock`

### Golden Fleece
- **ID**: `golden_fleece`
- **Attunement**: Cleric, Fighter, Warden
- **Stat Bonus**: Defense +15
- **Reactive**: No
- **Spell**: **Restoration** — The user restores 25 HP and gets +10 Attack for 2 rounds.; Heal 25; Cooldown 2 round(s); Self buffs: Attack +10 (2r)

### Arcane Hourglass
- **ID**: `arcane_hourglass`
- **Attunement**: Mage
- **Stat Bonus**: Defense +25
- **Reactive**: No
- **Spell**: **Time Stop** — The user is untargetable but cannot act for 1 round.; Cooldown 99 round(s); Special handler: `time_stop`

### Naiad's Knife
- **ID**: `naiads_knife`
- **Attunement**: Fighter, Rogue
- **Stat Bonus**: Attack +15
- **Reactive**: No
- **Spell**: **Deep Cut** — The user's next Strike Exposes the target for 2 rounds.; Cooldown 2 round(s); Special handler: `next_strike_expose`

### Last Prism
- **ID**: `last_prism`
- **Attunement**: Mage
- **Stat Bonus**: Attack +15
- **Reactive**: No
- **Spell**: **Chroma** — The user's next Magic Strike deals +25 damage.; Cooldown 1 round(s); Special handler: `next_magic_strike_plus_25`

### Misericorde
- **ID**: `misericorde`
- **Attunement**: Cleric, Fighter, Rogue
- **Stat Bonus**: Attack +15
- **Reactive**: No
- **Spell**: **Mercy Stroke** — The user deals 50 damage to target enemy with a status condition.; Power 30; Cooldown 2 round(s); Special handler: `statused_only`

### Selkie’s Skin
- **ID**: `selkies_skin`
- **Attunement**: Mage, Ranger, Rogue
- **Stat Bonus**: Speed +15
- **Reactive**: No
- **Spell**: **Mistform** — The next Strike against the user this round deals 0 damage.; Cooldown 2 round(s); Special handler: `mistform`

### Red Hood
- **ID**: `red_hood`
- **Attunement**: Cleric, Fighter, Ranger
- **Stat Bonus**: Attack +15
- **Reactive**: No
- **Spell**: **Hunter's Path** — The user's next Strike has 30% Lifesteal; Cooldown 1 round(s); Special handler: `next_strike_lifesteal_30`

### Enchanted Lamp
- **ID**: `enchanted_lamp`
- **Attunement**: Cleric, Rogue
- **Stat Bonus**: Speed +25
- **Reactive**: Yes
- **Spell**: **Dying Wish** — Reaction: If the user would take fatal damage from above 50% max HP, they survive at 1 HP.; Cooldown 99 round(s); Special handler: `dying_wish`

### Magic Mirror
- **ID**: `magic_mirror`
- **Attunement**: Cleric, Mage
- **Stat Bonus**: Speed +15
- **Reactive**: Yes
- **Spell**: **Reflection** — Reaction: The user reflects a Spell targeted at them towards the caster.; Cooldown 5 round(s); Special handler: `reflect_spell`

### Nettle Smock
- **ID**: `nettle_smock`
- **Attunement**: Fighter, Warden
- **Stat Bonus**: Defense +15
- **Reactive**: Yes
- **Spell**: **Thornmail** — Reaction: The user reflects 20% of the damage from a Strike onto the attacker and cuts their healing by 50% for 2 rounds.; Cooldown 2 round(s); Special handler: `thornmail`

### Goose Quill
- **ID**: `goose_quill`
- **Attunement**: Cleric, Mage, Warden
- **Stat Bonus**: Speed +25
- **Reactive**: Yes
- **Spell**: **Make History** — Reaction: When the user casts an Ultimate Spell, it only uses up half of the Ultimate Meter.; Cooldown 6 round(s); Special handler: `half_meter_ultimate`

### Cursed Spindle
- **ID**: `cursed_spindle`
- **Attunement**: Cleric, Mage, Rogue
- **Stat Bonus**: Attack +15
- **Reactive**: Yes
- **Spell**: **Plague** — Reaction: When the user inflicts a status condition, extend its duration by 1 round.; Cooldown 3 round(s); Special handler: `extend_status_inflicted`

### Bluebeard’s Key
- **ID**: `bluebeards_key`
- **Attunement**: Rogue, Warden
- **Stat Bonus**: Defense +15
- **Reactive**: No
- **Spell**: **Unseal** — Target enemy loses Guard and Defense stat bonuses and cannot gain either for 2 rounds.; Cooldown 2 round(s); Special handler: `unseal`

### Sun-God's Banner
- **ID**: `sun_gods_banner`
- **Attunement**: Warden
- **Stat Bonus**: Defense +15
- **Reactive**: No
- **Spell**: **Hold** — The user and the lowest HP ally behind them are Guarded for 2 rounds.; Cooldown 2 round(s); Applies to self: Guard (2r); Special handler: `guard_lowest_hp_ally_behind`

### Dire-Wolf Spine
- **ID**: `dire_wolf_spine`
- **Attunement**: Fighter
- **Stat Bonus**: Attack +15
- **Reactive**: No
- **Spell**: **Rend** — The user's next Melee Strike deals +10 damage and Weakens the target for 2 rounds.; Cooldown 2 round(s); Special handler: `next_melee_plus_10_weaken`

### Soaring Crown
- **ID**: `soaring_crown`
- **Attunement**: Ranger
- **Stat Bonus**: Speed +15
- **Reactive**: No
- **Spell**: **Hawk's Eye** — The user's next Ranged Strike ignores targeting restrictions and does not consume Ammo.; Cooldown 2 round(s); Special handler: `next_ranged_ignore_targeting_no_ammo`

### Fading Diadem
- **ID**: `fading_diadem`
- **Attunement**: Cleric
- **Stat Bonus**: Defense +15
- **Reactive**: No
- **Spell**: **Reprieve** — Target ally restores 30 HP and is Guarded for 2 rounds.; Heal 30; Cooldown 2 round(s); Applies to target: Guard (2r)

### Holy Grail
- **ID**: `iron_rosary`
- **Attunement**: Cleric
- **Stat Bonus**: Defense +15
- **Reactive**: No
- **Spell**: **Purge** — Cleanse target adventurer's status conditions (can be the user). They get +5 Defense per condition cleansed for 2 rounds.; Cooldown 1 round(s); Special handler: `purge`

### Dragon's Horn
- **ID**: `dragons_horn`
- **Attunement**: Fighter, Ranger
- **Stat Bonus**: Attack +15
- **Reactive**: No
- **Spell**: **Sky Assault** — The user's next Strike deals +10 damage, can target backline enemies in the user's lane, and Spotlights the target for 2 rounds.; Cooldown 2 round(s); Special handler: `next_strike_plus_10_spotlight`

### Bottled Clouds
- **ID**: `bottled_clouds`
- **Attunement**: Mage, Ranger
- **Stat Bonus**: Attack +15
- **Reactive**: No
- **Spell**: **Clear Skies** — The user's next Strike deals +10 damage and is Spread.; Cooldown 2 round(s); Special handler: `next_strike_plus_10_spread`

### Glass Slipper
- **ID**: `glass_slipper`
- **Attunement**: Mage, Rogue
- **Stat Bonus**: Speed +15
- **Reactive**: No
- **Spell**: **Midnight Waltz** — The user Swaps positions with an ally and the next Spell they cast does not go on cooldown.; Cooldown 2 round(s); Special handler: `midnight_waltz`

### Black Torch
- **ID**: `black_torch`
- **Attunement**: Fighter, Ranger, Rogue
- **Stat Bonus**: Attack +15
- **Reactive**: Yes
- **Spell**: **Grave Tiding** — Reaction: When the user deals fatal damage, they heal equal to 50% of the damage dealt.; Cooldown 1 round(s); Special handler: `grave_tiding`

### Cornucopia
- **ID**: `cornucopia`
- **Attunement**: Ranger, Warden
- **Stat Bonus**: Speed +15
- **Reactive**: Yes
- **Spell**: **Horn of Plenty** — Reaction: When the user Swaps positions with an ally, both restore 25  HP.; Heal 25; Cooldown 1 round(s); Special handler: `horn_of_plenty`

### All-Mill
- **ID**: `all_mill`
- **Attunement**: Ranger, Warden
- **Stat Bonus**: Defense +15
- **Reactive**: No
- **Spell**: **Boundless** — The user gains Root Immunity and +10 Speed for 2 rounds.; Cooldown 2 round(s); Applies to self: Root_Immunity (2r); Self buffs: Speed +10 (2r)

### Paradox Rings
- **ID**: `paradox_rings`
- **Attunement**: Mage, Warden
- **Stat Bonus**: Speed +15
- **Reactive**: Yes
- **Spell**: **Infinity** — Reaction: When the user casts a Spell that targets an ally, they Swap positions.; Cooldown 2 round(s); Special handler: `infinity`

### Jade Rabbit
- **ID**: `jade_rabbit`
- **Attunement**: Mage, Ranger
- **Stat Bonus**: Speed +15
- **Reactive**: No
- **Spell**: **Elixir of Life** — The user's next Strike has 10% Lifesteal, does not consume Ammo, and does not go on cooldown.; Cooldown 2 round(s); Special handler: `elixir_of_life`

### Swan Cloak
- **ID**: `swan_cloak`
- **Attunement**: Rogue
- **Stat Bonus**: Defense +15
- **Reactive**: Yes
- **Spell**: **Featherweight** — Reaction: When the user is targeted by a Melee Strike, they first Swap positions.; Cooldown 2 round(s); Special handler: `featherweight`

### Starskin Veil
- **ID**: `starskin_veil`
- **Attunement**: Cleric, Warden
- **Stat Bonus**: Defense +15
- **Reactive**: No
- **Spell**: **Dazzle** — Redirect the target's next Spell or Strike to the user.; Cooldown 2 round(s); Special handler: `dazzle`

### Blood Diamond
- **ID**: `blood_diamond`
- **Attunement**: Fighter
- **Stat Bonus**: Attack +15
- **Reactive**: Yes
- **Spell**: **Last Stand** — Reaction: When a Strike damages the user below 50% max HP, their next Strike deals +25 damage.; Cooldown 2 round(s); Special handler: `last_stand`

### Suspicious Eye
- **ID**: `suspicious_eye`
- **Attunement**: Ranger
- **Stat Bonus**: Speed +15
- **Reactive**: Yes
- **Spell**: **Nebulous Ides** — Reaction: When the user Strikes an enemy in their lane, Spotlight the target for 2 rounds.; Cooldown 2 round(s); Special handler: `nebulous_ides`

### Philosopher's Stone
- **ID**: `philosophers_stone`
- **Attunement**: Cleric, Mage
- **Stat Bonus**: Defense +15
- **Reactive**: Yes
- **Spell**: **Transmutation** — Reaction: When an enemy inflicts the user with a status condition, cleanses it and the user restores 40 HP.; Heal 40; Cooldown 2 round(s); Special handler: `transmutation`

### Seeking Yarn
- **ID**: `seeking_yarn`
- **Attunement**: Ranger, Rogue
- **Stat Bonus**: Speed +15
- **Reactive**: No
- **Spell**: **Lead** — For 2 rounds, the user's Strikes against enemies in their lane do not consume Ammo.; Cooldown 2 round(s); Special handler: `seeking_yarn`

### Tarnhelm
- **ID**: `tarnhelm`
- **Attunement**: Fighter, Warden
- **Stat Bonus**: Attack +25
- **Reactive**: Yes
- **Spell**: **Feign Death** — Reaction: When the user takes fatal damage, they survive at 1 HP.; Cooldown 99 round(s); Special handler: `tarnhelm`

### Walking Abode
- **ID**: `walking_abode`
- **Attunement**: Cleric, Mage, Ranger
- **Stat Bonus**: Speed +15
- **Reactive**: No
- **Spell**: **Consume** — Root target enemy for 2 rounds and halve their healing for the duration.; Cooldown 2 round(s); Applies to target: Root (2r); Special handler: `walking_abode`

### Nebula Mail
- **ID**: `nebula_mail`
- **Attunement**: Fighter, Rogue, Warden
- **Stat Bonus**: Attack +25
- **Reactive**: No
- **Spell**: **Event Horizon** — For 2 rounds, when the user takes damage from a Strike, charge the Ultimate Meter +1.; Cooldown 2 round(s); Special handler: `event_horizon`

## Appendix D. Holistic Takeaways
- Fabled’s deepest strategic identity comes from combining a collectible shell with a highly positional 3v3 battle engine.
- The quest structure makes drafting and loadout allocation matter before combat even starts.
- The combat engine rewards understanding of lane access, swap timing, status refreshes, and ultimate pacing as much as raw damage.
- The current build already contains the core game loop, the majority of its authored content, a working AI stack, LAN support, ranked progression, and non-combat shell systems.
- The largest remaining gap on the shell side is content density in cosmetic storefronts rather than combat-system completeness.
