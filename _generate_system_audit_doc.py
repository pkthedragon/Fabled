from __future__ import annotations

from pathlib import Path

from economy import STARTER_ADVENTURERS
from models import CampaignProfile
from net import LAN_PORT, LAN_PROBE_MESSAGE, LAN_PROBE_REPLY
from quests_ruleset_data import (
    ADVENTURERS,
    ARTIFACTS,
    CLASS_SKILLS,
    GOOSE_QUILL_RETAINED_METER,
    ULTIMATE_METER_MAX,
    ULTIMATE_WIN_COUNT,
)
from settings import FPS, HEIGHT, SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT, TITLE, WIDTH
from storybook_content import (
    BOUT_MODES,
    CATALOG_SECTIONS,
    CLOSET_TABS,
    MARKET_ITEMS,
    MARKET_TABS,
    SHOP_TABS,
    STORY_QUESTS,
)
from storybook_progression import exp_to_next_level, level_up_gold
from storybook_ranked import MAX_REPUTATION, MIN_REPUTATION, RANKS, STARTING_REPUTATION


OUT = Path(__file__).with_name("FABLED_COMPREHENSIVE_SYSTEM_AUDIT.md")


UI_ROUTES = [
    "main_menu",
    "player_menu",
    "market",
    "inventory",
    "friends",
    "guild_hall",
    "shops / armory",
    "closet",
    "favored_adventurer_select",
    "quests_menu",
    "quest_party_loadout",
    "training_grounds",
    "quest_draft",
    "quest_loadout",
    "bouts_menu",
    "bout_lobby",
    "bout_draft",
    "bout_loadout",
    "battle",
    "results",
    "lan_setup",
    "catalog",
    "settings",
]


def md(lines: list[str], text: str = "") -> None:
    lines.append(text)


def bulletize(items: list[str] | tuple[str, ...]) -> str:
    return ", ".join(str(item) for item in items) if items else "None"


def sentence_case_stat(stat_name: str) -> str:
    return {"hp": "HP", "attack": "Attack", "defense": "Defense", "speed": "Speed"}.get(stat_name, stat_name.title())


def fmt_statuses(statuses) -> str:
    if not statuses:
        return ""
    return ", ".join(f"{spec.kind.title()} ({spec.duration}r)" for spec in statuses)


def fmt_stats(specs) -> str:
    if not specs:
        return ""
    parts = []
    for spec in specs:
        sign = "+" if spec.amount > 0 else ""
        parts.append(f"{sentence_case_stat(spec.stat)} {sign}{spec.amount} ({spec.duration}r)")
    return ", ".join(parts)


def fmt_effect(effect) -> list[str]:
    parts: list[str] = []
    if effect.description:
        parts.append(effect.description.strip())
    if effect.power:
        parts.append(f"Power {effect.power}")
    if effect.heal:
        parts.append(f"Heal {effect.heal}")
    if effect.cooldown:
        parts.append(f"Cooldown {effect.cooldown} round(s)")
    if effect.ammo_cost:
        parts.append(f"Ammo Cost {effect.ammo_cost}")
    if effect.spread:
        parts.append("Spread")
    if effect.counts_as_spell:
        parts.append("Counts as spell")
    if effect.ignore_targeting:
        parts.append("Ignores targeting restrictions")
    if effect.recoil:
        parts.append(f"Recoil {int(effect.recoil * 100)}%")
    if effect.lifesteal:
        parts.append(f"Lifesteal {int(effect.lifesteal * 100)}%")
    if effect.bonus_power_if_status and effect.bonus_power:
        parts.append(f"+{effect.bonus_power} Power vs {effect.bonus_power_if_status.title()}")
    statuses = fmt_statuses(effect.target_statuses)
    if statuses:
        parts.append(f"Applies to target: {statuses}")
    self_statuses = fmt_statuses(effect.self_statuses)
    if self_statuses:
        parts.append(f"Applies to self: {self_statuses}")
    self_buffs = fmt_stats(effect.self_buffs)
    if self_buffs:
        parts.append(f"Self buffs: {self_buffs}")
    target_buffs = fmt_stats(effect.target_buffs)
    if target_buffs:
        parts.append(f"Target buffs: {target_buffs}")
    target_debuffs = fmt_stats(effect.target_debuffs)
    if target_debuffs:
        parts.append(f"Target debuffs: {target_debuffs}")
    if effect.special:
        parts.append(f"Special handler: `{effect.special}`")
    return parts


def fmt_weapon_meta(weapon) -> str:
    pieces = [weapon.kind.title()]
    if weapon.ammo:
        pieces.append(f"{weapon.ammo} Ammo")
    strike = weapon.strike
    if strike.cooldown:
        pieces.append(f"Strike CD {strike.cooldown}")
    return " | ".join(pieces)

def append_intro(lines: list[str]) -> None:
    md(lines, "# Fabled Comprehensive System Audit")
    md(lines)
    md(lines, "## Purpose")
    md(
        lines,
        "This document is a holistic, code-grounded audit of the current Fabled build. It is intended to function as a combined rules reference, systems map, implementation snapshot, content index, and current-state design audit.",
    )
    md(
        lines,
        "It uses two sources of truth together: the current `rulebook.txt` and the live Python implementation that powers combat, quests, progression, UI flow, LAN play, economy, and AI behavior.",
    )
    md(lines)
    md(lines, "## Source Of Truth")
    md(lines, "- Primary rules reference: `rulebook.txt`")
    md(lines, "- Combat engine: `quests_ruleset_logic.py`, `quests_ruleset_models.py`, `quests_ruleset_data.py`")
    md(lines, "- Ranked / quest progression: `storybook_ranked.py`, `storybook_mode.py`")
    md(lines, "- Progression and account state: `storybook_progression.py`, `models.py`, `campaign_save.py`")
    md(lines, "- Shell content and store/meta data: `storybook_content.py`, `economy.py`")
    md(lines, "- AI systems: `quests_ai_battle.py`, `quests_ai_quest.py`, `quests_ai_quest_loadout.py`, `quests_ai_runtime.py`")
    md(lines, "- Runtime and presentation shell: `main.py`, `settings.py`, `storybook_ui.py`")
    md(lines, "- LAN transport: `net.py`, `storybook_lan.py`")
    md(lines)
    md(lines, "## Executive Snapshot")
    md(lines, "| Area | Current Build State |")
    md(lines, "| --- | --- |")
    md(lines, f"| Game title | `{TITLE}` |")
    md(lines, f"| Render canvas | `{WIDTH} x {HEIGHT}` internal canvas, fullscreen scaled |")
    md(lines, f"| Target framerate | `{FPS}` FPS |")
    md(lines, f"| Adventurers | `{len(ADVENTURERS)}` |")
    md(lines, f"| Class groups | `{len(CLASS_SKILLS)}` |")
    md(lines, f"| Total class skills | `{sum(len(v) for v in CLASS_SKILLS.values())}` |")
    md(lines, f"| Artifacts | `{len(ARTIFACTS)}` |")
    md(lines, f"| Ultimate meter cap | `{ULTIMATE_METER_MAX}` |")
    md(lines, f"| Ultimates required for instant win | `{ULTIMATE_WIN_COUNT}` |")
    md(lines, f"| Starting Reputation | `{STARTING_REPUTATION}` |")
    md(lines, f"| Reputation bounds | `{MIN_REPUTATION}` to `{MAX_REPUTATION}` |")
    md(lines, f"| Story quests defined | `{len(STORY_QUESTS)}` |")
    md(lines, f"| Bout modes defined | `{len(BOUT_MODES)}` |")
    md(lines, f"| Market tabs | `{len(MARKET_TABS)}` |")
    md(lines, f"| Live cosmetic inventory entries | `{len(MARKET_ITEMS)}` |")
    md(lines)
    md(lines, "## Reading Guide")
    md(lines, "1. Sections 1-8 explain the game holistically: combat, loadouts, quests, shell flow, progression, LAN, and AI.")
    md(lines, "2. Sections 1-9 cover the top-level audit, and the appendices hold the exhaustive content reference.")
    md(lines, "3. Appendices A-C enumerate every adventurer, class skill, and artifact in the current code-backed dataset.")
    md(lines)


def append_core_systems(lines: list[str]) -> None:
    md(lines, "## 1. Core Game Structure")
    md(
        lines,
        "Fabled is a tactical, turn-based, position-sensitive combat game built around small-team encounters. The central loop is: build a party of six, refine loadouts, scout the enemy, bring three into a formation-based encounter, plan all actions simultaneously, then resolve them in initiative order.",
    )
    md(lines)
    md(lines, "### 1.1 The Three Nested Scales Of Play")
    md(lines, "- **Account scale**: gold, EXP, level, rank, Reputation, favorite rules, cosmetics, and friends/LAN entries.")
    md(lines, "- **Quest scale**: a six-member quest party, per-run wins/losses/streaks, repeated encounter prep, and forfeit / end-of-run resolution.")
    md(lines, "- **Encounter scale**: three active adventurers per side, formation, action planning, bonus actions, meter race, and knockout pressure.")
    md(lines)
    md(lines, "### 1.2 Core Combat Identity")
    md(lines, "- Position matters as much as raw numbers.")
    md(lines, "- Action timing matters because players lock all actions before resolution.")
    md(lines, "- Weapon choice matters because primary weapon defines the active strike and attached passive/spell package.")
    md(lines, "- Class and artifact matter because they change statlines, bonus actions, utility access, and matchup adaptability.")
    md(lines, "- Ultimate pacing matters because the third ultimate cast wins immediately.")
    md(lines)
    md(lines, "## 2. Combat System Audit")
    md(lines, "### 2.1 Encounter Size And Formation")
    md(lines, "- Each encounter is **3 versus 3**.")
    md(lines, f"- Slot model: `{SLOT_FRONT}`, `{SLOT_BACK_LEFT}`, `{SLOT_BACK_RIGHT}`.")
    md(lines, "- One adventurer must occupy the frontline.")
    md(lines, "- Up to two adventurers can occupy the backline.")
    md(lines, "- Backline units suffer **-50 Speed**.")
    md(lines, "- If the frontline adventurer is knocked out, the **leftmost backline** adventurer immediately advances.")
    md(lines)
    md(lines, "### 2.2 Round Structure")
    md(lines, "Each round is processed in the following order:")
    md(lines, "1. Initiative check")
    md(lines, "2. Start-of-round effects")
    md(lines, "3. Action selection")
    md(lines, "4. Action resolution in initiative order")
    md(lines, "5. Bonus action selection")
    md(lines, "6. Bonus action resolution in initiative order")
    md(lines, "7. End-of-round effects and duration/cooldown ticking")
    md(lines)
    md(lines, "### 2.3 Initiative")
    md(lines, "- Initiative is primarily sorted by effective Speed after all current modifiers.")
    md(lines, "- Backline penalty is applied before ordering.")
    md(lines, "- Shock lowers Speed by 25.")
    md(lines, "- Current code uses deterministic ordering, then layers special exceptions such as Reynard's initiative jump from **Glowing Trail**.")
    md(lines)
    md(lines, "### 2.4 Action Types")
    md(lines, "The battle planner supports the five rulebook action types plus ultimate selection when the meter is full:")
    md(lines, "- Strike")
    md(lines, "- Spellcast")
    md(lines, "- Switch")
    md(lines, "- Swap")
    md(lines, "- Skip")
    md(lines, "- Ultimate")
    md(lines)
    md(lines, "### 2.5 Strikes")
    md(lines, "#### Melee")
    md(lines, "- User must normally be in the frontline.")
    md(lines, "- Targets the enemy frontline unless targeting rules are overridden.")
    md(lines, "- Spotlight allows melee to target spotlighted enemies in the backline.")
    md(lines)
    md(lines, "#### Ranged")
    md(lines, "- Can target the enemy frontline.")
    md(lines, "- Can target the enemy directly across from the attacker.")
    md(lines, "- Consumes ammo unless the attack or passive says otherwise.")
    md(lines)
    md(lines, "#### Magic")
    md(lines, "- Can target the enemy frontline.")
    md(lines, "- Can target the enemy directly across from the attacker.")
    md(lines, "- Counts as casting a spell for spell-related interactions.")
    md(lines, "- Uses cooldown instead of ammo.")
    md(lines)
    md(lines, "#### Damage Formula")
    md(lines, "```text")
    md(lines, "Damage = ceil(Power x (Attack / Defense))")
    md(lines, "```")
    md(lines, "- Spread strikes hit all legal targets, then halve damage unless a rule explicitly ignores the spread penalty.")
    md(lines, "- Guard reduces incoming damage by 15%.")
    md(lines, "- Expose increases incoming damage by 15%.")
    md(lines, "- Weaken lowers outgoing damage by 15%.")
    md(lines, "- Recoil and lifesteal are applied after damage resolution where appropriate.")
    md(lines)
    md(lines, "### 2.6 Spells")
    md(lines, "- Enemy-targeting spells can target the enemy frontline or the enemy directly across.")
    md(lines, "- Ally-targeting spells can target any ally.")
    md(lines, "- After use, spells go on cooldown unless an override prevents it.")
    md(lines, "- Triggered reactive artifact spells count as spell casts for interaction checks such as Arcane and anti-reactive effects.")
    md(lines)
    md(lines, "### 2.7 Switch")
    md(lines, "- Swaps primary and secondary weapon.")
    md(lines, "- Resets cooldowns tied to either weapon.")
    md(lines, "- Fully reloads ranged ammo.")
    md(lines, "- Also enables specific synergy windows such as Armed reload-free openers and weapon-based tempo loops.")
    md(lines)
    md(lines, "### 2.8 Swap")
    md(lines, "- Swaps positions with an ally.")
    md(lines, "- If the ally has not yet acted this round, they act from the new slot.")
    md(lines, "- Root prevents choosing Swap.")
    md(lines, "- Multiple class skills, artifacts, and innates are designed around Swap timing.")
    md(lines)
    md(lines, "### 2.9 Skip")
    md(lines, "- Deliberately passes action selection for that actor.")
    md(lines, "- Rare in optimal play, but supported by both player UI and AI.")
    md(lines)
    md(lines, "### 2.10 Ultimate Meter And Win Condition")
    md(lines, "Current engine assumptions, matching the rulebook and code:")
    md(lines, f"- Strike: `+1` meter")
    md(lines, f"- Melee Strike: `+2` meter")
    md(lines, f"- Non-Arcane normal Spell cast: `+0` meter")
    md(lines, f"- Arcane spell cast: `+1` meter")
    md(lines, f"- Arcane Magic Strike: base Strike meter plus `+1` because it counts as casting a spell")
    md(lines, f"- Reactive spell trigger: `+0` meter by default, `+1` if the user has Arcane")
    md(lines, f"- Meter cap: `{ULTIMATE_METER_MAX}`")
    md(lines, "- An ultimate can be selected only when the meter is already full at action-selection time.")
    md(lines, "- Casting an ultimate resets the meter to 0, except Goose Quill retains half the meter.")
    md(lines, f"- Goose Quill retained meter value in code: `{GOOSE_QUILL_RETAINED_METER}`")
    md(lines, f"- The `{ULTIMATE_WIN_COUNT}`rd ultimate cast by a side wins immediately.")
    md(lines, "- A side also loses immediately when all three active encounter members are knocked out.")
    md(lines)
    md(lines, "### 2.11 Conditions And Stat Modifiers")
    md(lines, "| Condition | Rulebook/System Effect |")
    md(lines, "| --- | --- |")
    md(lines, "| Burn | 8% max HP damage each round. Burn synergies also drive anti-heal and healing transfer effects. |")
    md(lines, "| Root | Prevents Swap. Also unlocks several control/payoff mechanics. |")
    md(lines, "| Shock | -15 Speed and 15% recoil on Strikes. |")
    md(lines, "| Weaken | 15% less damage dealt. |")
    md(lines, "| Expose | 15% more damage taken. |")
    md(lines, "| Guard | 15% less damage taken. |")
    md(lines, "| Spotlight | Allows melee targeting of a backline unit. |")
    md(lines, "| Taunt | Restricts target selection to the taunter where relevant. |")
    md(lines)
    md(lines, "Additional implementation notes:")
    md(lines, "- Same status type does not stack.")
    md(lines, "- Reapplying a status refreshes duration to the higher of current and new duration.")
    md(lines, "- Root Immunity is implemented as a helper state and also **cleanses Root** when gained.")
    md(lines, "- Stat bonuses and penalties do not stack; effective stat uses the highest positive and highest negative.")
    md(lines)
    md(lines, "### 2.12 Combatant Runtime State")
    md(lines, "Each active combatant effectively carries:")
    md(lines, "- Base adventurer definition")
    md(lines, "- Current loadout")
    md(lines, "- HP")
    md(lines, "- KO state")
    md(lines, "- Slot / position")
    md(lines, "- Status list")
    md(lines, "- Buff and debuff lists")
    md(lines, "- Cooldowns")
    md(lines, "- Ammo remaining by weapon")
    md(lines, "- Markers/counters for unique kits")
    md(lines, "- Queued normal action")
    md(lines, "- Queued bonus action")
    md(lines)
    md(lines, "## 3. Loadouts, Classes, And Artifacts")
    md(lines, "### 3.1 Loadout Components")
    md(lines, "Every combat-ready adventurer is defined by:")
    md(lines, "- Chosen primary weapon")
    md(lines, "- Chosen secondary weapon")
    md(lines, "- Chosen class")
    md(lines, "- Chosen class skill")
    md(lines, "- Chosen artifact, or no artifact")
    md(lines)
    md(lines, "### 3.2 Class Uniqueness")
    md(lines, "- Within a quest party of six, each class can appear only once.")
    md(lines, "- This matters before the encounter because the entire quest party must remain class-legal.")
    md(lines, "- It also matters at bring-three time because all encounter members inherit those fixed class assignments.")
    md(lines)
    md(lines, "### 3.3 Artifact Uniqueness")
    md(lines, "- A party can hold only one copy of each artifact.")
    md(lines, "- An artifact may be carried unattuned, but its spell cannot be used unless the current class is attuned to it.")
    md(lines, "- Training Grounds is the one place where all artifacts are freely available regardless of permanent ownership.")
    md(lines)
    md(lines, "### 3.4 Effective Stat Calculation")
    md(lines, "- Base stat")
    md(lines, "- Plus artifact stat bonus if applicable")
    md(lines, "- Plus highest active bonus")
    md(lines, "- Minus highest active penalty")
    md(lines, "- Plus/Minus positional or special kit modifiers")
    md(lines)
    md(lines, "Implementation-specific notes:")
    md(lines, "- Ali Baba ignores stat bonuses and penalties from buff/debuff systems, but still keeps base values and relevant artifact stat bonus.")
    md(lines, "- Bulwark grants +15 Defense in the frontline and +5 Defense otherwise.")
    md(lines)
    md(lines, "## 4. Quest System Audit")
    md(lines, "### 4.1 Quest Structure")
    md(lines, "- Quests are competitive multi-encounter runs.")
    md(lines, "- The run ends after the player accumulates three encounter losses.")
    md(lines, "- Encounter wins update Reputation via Elo-based delta (+8 to +30).")
    md(lines, "- Encounter losses reduce Reputation by a flat -10.")
    md(lines)
    md(lines, "### 4.2 Favorite Rules")
    md(lines, "- Outside Training Grounds, the player can set as favorite only Little Jack plus adventurers they have previously quested with.")
    md(lines, "- Training Grounds maintains a separate training favorite with full-roster access.")
    md(lines, "- Current profile defaults seed both quest and training favorite to `little_jack`.")
    md(lines)
    md(lines, "### 4.3 Quest Start Flow")
    md(lines, "Current implemented quest flow:")
    md(lines, "1. Player starts a quest from Guild Hall.")
    md(lines, "2. The system offers **9 adventurers**, including the current quest favorite.")
    md(lines, "3. The player chooses **6** to form the quest party.")
    md(lines, "4. The player sets or edits loadouts for the party of six.")
    md(lines, "5. Each encounter later lets the player re-edit those loadouts before committing.")
    md(lines)
    md(lines, "### 4.4 Encounter Prep Flow")
    md(lines, "For each encounter:")
    md(lines, "1. Loadouts can be edited again.")
    md(lines, "2. The enemy party of six is shown.")
    md(lines, "3. The player chooses which three to bring.")
    md(lines, "4. The player assigns formation positions.")
    md(lines, "5. Battle begins.")
    md(lines)
    md(lines, "### 4.5 Quest Rewards")
    md(lines, "#### Gold")
    md(lines, "- Quest encounters do not award Gold directly.")
    md(lines, "- Quest-end bonus: 150 Gold at 5+ wins, 300 Gold at 10+ wins.")
    md(lines)
    md(lines, "#### Reputation")
    md(lines, "```text")
    md(lines, "ExpectedScore = 1 / (1 + 10^((OpponentRep - PlayerRep) / 400))")
    md(lines, "BaseChange = 28 x (ActualScore - ExpectedScore)")
    md(lines, "Win delta = clamp(round(BaseChange + WinstreakBonus), 8, 30)")
    md(lines, "WinstreakBonus = min(current quest winstreak before win, 5) x 2")
    md(lines, "Loss delta = -10 (flat)")
    md(lines, "```")
    md(lines, "- Reputation is clamped into the ranked range.")
    md(lines)
    md(lines, "#### Match Rating")
    md(lines, "```text")
    md(lines, "Match Rating = Reputation + (20 x current winstreak) - (15 x current lossstreak)")
    md(lines, "```")
    md(lines)
    md(lines, "### 4.6 Forfeit")
    md(lines, "- The current quest can be forfeited.")
    md(lines, "- Forfeit cost is **10 Reputation per remaining loss slot**.")
    md(lines, "- Example: if the player has 1 loss already, 2 losses remain, so the penalty is 20 Reputation.")
    md(lines)
    md(lines, "### 4.7 Ranked Ladder")
    md(lines, "| Rank | Reputation Floor |")
    md(lines, "| --- | --- |")
    for rank_name, floor in RANKS:
        md(lines, f"| {rank_name} | {floor} |")
    md(lines)
    md(lines, "### 4.8 Current Account Defaults Relevant To Quests")
    starter = CampaignProfile()
    md(lines, "- All adventurers available via draft; no fixed starter roster.")
    md(lines, f"- Starter unlocked classes: {bulletize(sorted(starter.unlocked_classes)) or '(all via draft)'}")
    md(lines, f"- Starter quest favorite: `{starter.storybook_favorite_adventurer}`")
    md(lines, f"- Starter training favorite: `{starter.storybook_training_favorite_adventurer}`")
    md(lines, f"- Initially quested adventurer set: {bulletize(sorted(starter.storybook_quested_adventurers))}")
    md(lines)
    md(lines, "## 5. Other Play Modes And Shell Systems")
    md(lines, "### 5.1 Training Grounds")
    md(lines, "- One-encounter practice flow.")
    md(lines, "- Supports AI or LAN.")
    md(lines, "- Uses a separate training favorite rather than overwriting the normal quest favorite.")
    md(lines, "- All artifacts are available regardless of ownership.")
    md(lines)
    md(lines, "### 5.2 Bouts")
    md(lines, "Defined bout shells in current content data:")
    for mode in BOUT_MODES:
        md(lines, f"- **{mode['name']}**: {mode['subtitle']} {mode['note']}")
    md(lines)
    md(lines, "### 5.3 Story Quests")
    for quest in STORY_QUESTS:
        md(lines, f"- **{quest.name}** (`{quest.locale}`): {quest.blurb} Difficulty: {quest.difficulty}. Rewards: {quest.reward_gold} Gold, {quest.reward_exp} EXP. Threat: {quest.threat}. Note: {quest.note}")
    md(lines)
    md(lines, "### 5.4 LAN")
    md(lines, f"- Uses TCP plus a UDP probe on port `{LAN_PORT}`.")
    md(lines, f"- Probe request: `{LAN_PROBE_MESSAGE.decode()}`")
    md(lines, f"- Probe reply: `{LAN_PROBE_REPLY.decode()}`")
    md(lines, "- Friends menu stores manual name + IP pairs for LAN targeting.")
    md(lines, "- Networking is intentionally lightweight rather than a full online service stack.")
    md(lines)
    md(lines, "## 6. Progression, Economy, And Meta Systems")
    md(lines, "### 6.1 Player Leveling")
    md(lines, "- No level cap (uncapped progression)")
    md(lines, "- EXP formula: `level × 100` to advance to next level")
    md(lines, "- Level-up Gold formula: `50 + (10 × new_level)`")
    md(lines)
    md(lines, "#### Level Curve (sample)")
    md(lines, "| Level | EXP To Next | Level-Up Gold |")
    md(lines, "| --- | --- | --- |")
    for level in range(1, 21):
        md(lines, f"| {level} | {exp_to_next_level(level)} | {level_up_gold(level + 1)} |")
    md(lines)
    md(lines, "### 6.2 Gold Sources")
    md(lines, "- Level-up bonuses: `50 + (10 × new_level)` Gold")
    md(lines)
    md(lines, "### 6.3 Artifact Economy")
    md(lines, "- Artifacts are no longer sold individually; they enter the run pool via draft at quest/bout start.")
    md(lines, f"- Armory tabs (legacy reference): {bulletize(SHOP_TABS)}")
    md(lines)
    md(lines, "### 6.4 Market And Cosmetics")
    md(lines, f"- Market tabs: {bulletize(MARKET_TABS)}")
    md(lines, f"- Closet tabs: {bulletize(CLOSET_TABS)}")
    md(lines, f"- Current explicit cosmetic entries in `MARKET_ITEMS`: `{len(MARKET_ITEMS)}`")
    md(lines)
    md(lines, "## 7. User Interface And Navigation Audit")
    md(lines, "### 7.1 Main Shell")
    md(lines, f"- The application renders to a fixed `{WIDTH} x {HEIGHT}` internal canvas, fullscreen-scaled.")
    md(lines, "- All mouse input is remapped from fullscreen display coordinates to canvas coordinates before any UI handler sees it.")
    md(lines, "- The UI is a single-window screen-state router: one active screen draws each frame, and button return dicts are used by `main.py` to transition between states.")
    md(lines, "- A persistent top bar occupies `(0, 0, 1400, 56)` on every screen and carries title, subtitle, back arrow, Settings, Quit, and a compact Gold/Rep/Level readout.")
    md(lines, "- Background uses concentric circles centered near `(700, 490)` plus scattered gold glow circles; a gold separator line sits at y=54.")
    md(lines)
    md(lines, "### 7.2 Current Route Inventory")
    for route in UI_ROUTES:
        md(lines, f"- `{route}`")
    md(lines)
    md(lines, "### 7.3 Screen-By-Screen Navigation Map")
    md(lines, "| Screen | Entry Point(s) | Exits To |")
    md(lines, "| --- | --- | --- |")
    md(lines, "| `main_menu` | App launch | `guild_hall` (Guild Hall btn), `market` (Market btn), `player_menu` (Profile panel click), `settings` (S btn), quit |")
    md(lines, "| `player_menu` | main_menu > Profile | `friends`, `closet`, `favored_adventurer_select` (favorite card), back → main_menu |")
    md(lines, "| `friends` | player_menu | back → player_menu |")
    md(lines, "| `closet` | player_menu | back → player_menu |")
    md(lines, "| `favored_adventurer_select` | player_menu (favorite card) | back → player_menu (confirm sets favorite) |")
    md(lines, "| `guild_hall` | main_menu > Guild Hall btn | `quests_menu` / quest start, `training_grounds`, `shops / armory`, `catalog`, back → main_menu |")
    md(lines, "| `quests_menu` | guild_hall | `quest_party_loadout` (edit loadouts), `quest_draft` (prepare encounter / start quest), back → guild_hall |")
    md(lines, "| `quest_party_loadout` | quests_menu | back → quests_menu (done saves loadouts) |")
    md(lines, "| `quest_draft` | quests_menu (prepare encounter) | `quest_loadout` (continue after picks), back → quests_menu |")
    md(lines, "| `quest_loadout` | quest_draft | `battle` (confirm formation), back → quest_draft |")
    md(lines, "| `training_grounds` | guild_hall | `quest_loadout` (after AI/LAN pick + favorite selection), back → guild_hall |")
    md(lines, "| `shops / armory` | guild_hall | back → guild_hall |")
    md(lines, "| `catalog` | guild_hall | back → guild_hall |")
    md(lines, "| `market` | main_menu | back → main_menu |")
    md(lines, "| `inventory` | (currently unused active route — available as player_menu sub) | back |")
    md(lines, "| `bouts_menu` | (bout entry point) | `bout_lobby` (AI/LAN), back |")
    md(lines, "| `bout_lobby` | bouts_menu | `bout_draft` (begin), back → bouts_menu |")
    md(lines, "| `bout_draft` | bout_lobby | `bout_loadout` (after 3 picks), back → bout_lobby |")
    md(lines, "| `bout_loadout` | bout_draft | `battle` (confirm), back → bout_draft |")
    md(lines, "| `battle` | quest_loadout / bout_loadout | `results` (after battle ends) |")
    md(lines, "| `results` | battle | continue (next encounter or quest end), rematch, return → quest menu or main |")
    md(lines, "| `lan_setup` | training_grounds / bout_lobby | back |")
    md(lines, "| `settings` | any screen via S btn | back → originating screen |")
    md(lines)
    md(lines, "### 7.4 Key Layout Constants Per Screen")
    md(lines, "All coordinates are in the `1400 x 900` canvas space. Top bar always at `(0, 0, 1400, 56)`.")
    md(lines, "| Screen | Major Panel(s) |")
    md(lines, "| --- | --- |")
    md(lines, "| main_menu | Profile `(74,138,310,320)`, Guild Hall `(430,168,380,330)`, Market `(850,168,380,330)` |")
    md(lines, "| player_menu | Avatar `(124,156,360,456)`, Progress `(516,156,330,456)`, Actions `(878,156,272,456)` |")
    md(lines, "| friends | Friend Ledger `(74,108,344,726)`, Friend Entry `(448,108,844,430)`, LAN Status `(448,566,844,268)` |")
    md(lines, "| guild_hall | Quest Desk `(86,132,680,270)`, Training `(86,438,324,238)`, Armory `(442,438,324,238)`, Catalog `(798,438,324,238)` |")
    md(lines, "| training_grounds | Roster `(56,108,486,726)`, Detail `(560,108,402,726)`, Options `(986,108,248,726)` |")
    md(lines, "| market | Tabs `(44,86,1312,102)`, List `(54,210,734,604)`, Preview `(816,210,486,604)` |")
    md(lines, "| closet | Categories `(48,104,244,730)`, Preview `(320,104,432,730)`, Inventory `(780,104,528,730)` |")
    md(lines, "| shops / armory | Info `(58,168,286,620)`, Inventory `(370,168,566,620)`, Detail `(962,168,312,620)` |")
    md(lines, "| catalog | Sections `(42,88,220,770)`, Filters `(288,88,504,170)`, List `(288,282,504,576)`, Detail `(818,88,540,770)` |")
    md(lines, "| quests_menu | Party `(120,144,560,612)`, Status `(710,144,530,286)`, Enemy `(710,470,530,286)` |")
    md(lines, "| quest_party_loadout | Party List `(40,104,388,744)`, Detail `(452,104,604,744)`, Rules `(1080,104,276,744)` |")
    md(lines, "| quest_draft | Cards grid, Formation `(230,642,486,194)`, Enemy `(726,642,176,194)`, Detail `(920,96,434,740)` |")
    md(lines, "| quest_loadout | Formation `(44,104,408,744)`, Detail `(476,104,540,744)`, Summary `(1040,104,316,744)` |")
    md(lines, "| battle | Log `(28,176,196,484)`, Battlefield center, Action plan `(224,696,938,160)`, Inspect `(1176,176,196,484)` |")
    md(lines, "| results | Center panel `(320,160,760,520)` |")
    md(lines, "| lan_setup | Role `(118,164,356,432)`, Connection `(522,164,356,432)`, Status `(926,164,356,432)` |")
    md(lines, "| settings | Preferences `(380,198,640,320)` |")
    md(lines)
    md(lines, "### 7.5 Interaction Patterns")
    md(lines, "- **Click** is the primary interaction for all buttons, adventurer cards, formation slots, list entries, tabs, and panel tiles.")
    md(lines, "- **Hover** drives visual feedback (border highlights, glow rects, color shifts) on all interactive elements and triggers status-word tooltips in any description text.")
    md(lines, "- **Mouse wheel / scroll** is supported on roster grids, inventory lists, catalog entry lists, and detail viewports. Scroll state is tracked as an integer offset passed into draw functions.")
    md(lines, "- **Text input** (keyboard) is active on Friends (name/IP fields) and LAN Setup (IP field). The active field is toggled by clicking the text-input rect.")
    md(lines, "- **No drag** interactions exist — all repositioning is done via click-to-select + click-to-place (e.g., formation slots in quest_loadout).")
    md(lines)
    md(lines, "### 7.6 Catalog")
    md(lines, f"- Catalog sections: {bulletize(CATALOG_SECTIONS)}")
    md(lines, "- Adventurers tab is a full roster reference.")
    md(lines, "- Class Skills tab groups the six classes and their three skills each.")
    md(lines, "- Artifacts tab is a non-store encyclopedia version of the Armory.")
    md(lines)
    md(lines, "### 7.7 Settings")
    md(lines, "- Current implemented settings are lightweight rather than a large options suite.")
    md(lines, "- Key toggles presently exposed in code are tutorial popups and fast battle resolution.")
    md(lines)
    md(lines, "## 8. AI And Simulation Audit")
    md(lines, "### 8.1 AI Stack")
    md(lines, "- **Quest roster / loadout AI**: `quests_ai_quest_loadout.py`")
    md(lines, "- **Encounter bring-three selector**: `quests_ai_quest.py`")
    md(lines, "- **Battle planner**: `quests_ai_battle.py`")
    md(lines, "- **Runtime wrappers / simulation harness**: `quests_ai_runtime.py` and reporting scripts")
    md(lines)
    md(lines, "### 8.2 Quest Opponent Flow")
    md(lines, "Current quest AI follows the same macro flow the player does:")
    md(lines, "1. Receive a 9-adventurer offer")
    md(lines, "2. Choose 6 for the quest party")
    md(lines, "3. Assign blind quest loadouts to those 6")
    md(lines, "4. See the opposing party of 6")
    md(lines, "5. Choose the best 3 and formation")
    md(lines, "6. Play the battle tactically")
    md(lines)
    md(lines, "### 8.3 Battle AI")
    md(lines, "- Generates legal actions per unit.")
    md(lines, "- Scores local actions, then assembles action bundles.")
    md(lines, "- Predicts enemy bundles and scores robustly rather than greedily.")
    md(lines, "- Repeats the same structure for bonus-action selection.")
    md(lines, "- Tracks meter race, status setup, lethal pressure, and positional access.")
    md(lines)
    md(lines, "### 8.4 Difficulty Philosophy")
    md(lines, "- Lower difficulties search less and predict less.")
    md(lines, "- Higher difficulties model more enemy responses and keep more candidate bundles.")
    md(lines, "- Simulation / audit runs can use the strongest settings to stress the balance model.")
    md(lines)
    md(lines, "## 9. Current Build Notes And Holistic Observations")
    md(lines, "### 9.1 What Is Fully Realized")
    md(lines, "- Complete combat engine with status, cooldown, ammo, switching, swapping, meter, ultimate, and KO replacement logic")
    md(lines, "- Full rulebook-backed adventurer/class/artifact dataset")
    md(lines, "- Ranked quest loop with drafting, re-loadouting, scouting, battle, result, and end-state handling")
    md(lines, "- Training Grounds AI/LAN practice shell")
    md(lines, "- LAN transport and friend IP book")
    md(lines, "- Player progression, gold, EXP, Reputation, rank, and favorite systems")
    md(lines)
    md(lines, "### 9.2 What Is Present As Framework")
    md(lines, "- Market / Closet cosmetic shell exists, but live cosmetic inventory content is currently empty.")
    md(lines, "- Story quests and bout modes are defined as shell content data alongside the core ranked quest loop.")
    md(lines)
    md(lines, "### 9.3 Important Design Tensions Visible In The Build")
    md(lines, "- The game has two very different strategic layers: blind quest-party construction and revealed-opponent encounter selection.")
    md(lines, "- Because the third ultimate wins instantly, long fights are never only attrition fights; they are also meter races.")
    md(lines, "- Position and target legality are strong enough that lineup/slot choice can be as impactful as raw loadout strength.")
    md(lines, "- Artifact choice is both a stat choice and an action-economy choice.")
    md(lines, "- Support/control units remain structurally important because cleanse, guard, spotlight, and anti-caster effects directly decide legal access and tempo.")


def append_adventurers(lines: list[str]) -> None:
    md(lines, "## Appendix A. Adventurer Reference")
    for adventurer in ADVENTURERS:
        md(lines)
        md(lines, f"### {adventurer.name}")
        md(lines, f"- **ID**: `{adventurer.id}`")
        md(lines, f"- **Base Stats**: HP {adventurer.hp} | Attack {adventurer.attack} | Defense {adventurer.defense} | Speed {adventurer.speed}")
        md(lines, f"- **Innate Skill**: **{adventurer.innate.name}** — {adventurer.innate.description}")
        for index, weapon in enumerate(adventurer.signature_weapons, start=1):
            md(lines, f"#### Signature Weapon {index}: {weapon.name}")
            md(lines, f"- **Type / Meta**: {fmt_weapon_meta(weapon)}")
            strike_parts = fmt_effect(weapon.strike)
            md(lines, f"- **Strike**: {'; '.join(strike_parts) if strike_parts else 'Standard strike'}")
            if weapon.passive_skills:
                md(lines, "- **Passive Skills**:")
                for passive in weapon.passive_skills:
                    extra = f" Special: `{passive.special}`" if passive.special else ""
                    md(lines, f"  - **{passive.name}** — {passive.description}{extra}")
            if weapon.spells:
                md(lines, "- **Spells**:")
                for spell in weapon.spells:
                    md(lines, f"  - **{spell.name}** — {'; '.join(fmt_effect(spell))}")
        md(lines, f"- **Ultimate Spell**: **{adventurer.ultimate.name}** — {'; '.join(fmt_effect(adventurer.ultimate))}")


def append_class_skills(lines: list[str]) -> None:
    md(lines)
    md(lines, "## Appendix B. Class Skill Reference")
    for class_name, skills in CLASS_SKILLS.items():
        md(lines)
        md(lines, f"### {class_name}")
        for skill in skills:
            extra = f" Special: `{skill.special}`" if skill.special else ""
            md(lines, f"- **{skill.name}** — {skill.description}{extra}")


def append_artifacts(lines: list[str]) -> None:
    md(lines)
    md(lines, "## Appendix C. Artifact Reference")
    for artifact in ARTIFACTS:
        md(lines)
        md(lines, f"### {artifact.name}")
        md(lines, f"- **ID**: `{artifact.id}`")
        md(lines, f"- **Attunement**: {bulletize(list(artifact.attunement))}")
        md(lines, f"- **Stat Bonus**: {sentence_case_stat(artifact.stat)} +{artifact.amount}")
        md(lines, f"- **Reactive**: {'Yes' if artifact.reactive else 'No'}")
        md(lines, f"- **Spell**: **{artifact.spell.name}** — {'; '.join(fmt_effect(artifact.spell))}")
        if artifact.description:
            md(lines, f"- **Notes**: {artifact.description}")


def append_closing(lines: list[str]) -> None:
    md(lines)
    md(lines, "## Appendix D. Holistic Takeaways")
    md(lines, "- Fabled’s deepest strategic identity comes from combining a collectible shell with a highly positional 3v3 battle engine.")
    md(lines, "- The quest structure makes drafting and loadout allocation matter before combat even starts.")
    md(lines, "- The combat engine rewards understanding of lane access, swap timing, status refreshes, and ultimate pacing as much as raw damage.")
    md(lines, "- The current build already contains the core game loop, the majority of its authored content, a working AI stack, LAN support, ranked progression, and non-combat shell systems.")
    md(lines, "- The largest remaining gap on the shell side is content density in cosmetic storefronts rather than combat-system completeness.")


def main() -> None:
    lines: list[str] = []
    append_intro(lines)
    append_core_systems(lines)
    append_adventurers(lines)
    append_class_skills(lines)
    append_artifacts(lines)
    append_closing(lines)
    text = "\n".join(lines).rstrip() + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Lines: {len(lines)}")


if __name__ == "__main__":
    main()

