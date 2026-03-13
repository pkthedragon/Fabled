# Fabled — Complete Game Mechanics Reference

This document describes every mechanical system in Fabled as it currently exists in the codebase. It is intended as a planning reference for an AI assistant reasoning about future features.

---

## Table of Contents

1. [Overview](#overview)
2. [Game Modes](#game-modes)
3. [Formation and Slots](#formation-and-slots)
4. [Stats](#stats)
5. [Round Structure and Turn Flow](#round-structure-and-turn-flow)
6. [Initiative](#initiative)
7. [Actions](#actions)
8. [Ability Categories](#ability-categories)
9. [Damage Calculation](#damage-calculation)
10. [Status Conditions](#status-conditions)
11. [Stat Buffs and Debuffs](#stat-buffs-and-debuffs)
12. [Guard Mechanic](#guard-mechanic)
13. [Healing](#healing)
14. [Lifesteal (Vamp)](#lifesteal-vamp)
15. [Swap Mechanic](#swap-mechanic)
16. [Malice Resource (Warlock)](#malice-resource-warlock)
17. [Recharge Mechanic](#recharge-mechanic)
18. [Items](#items)
19. [Basic Abilities by Class](#basic-abilities-by-class)
20. [All Adventurers](#all-adventurers)
    - [Fighters](#fighters)
    - [Rogues](#rogues)
    - [Wardens](#wardens)
    - [Mages](#mages)
    - [Rangers](#rangers)
    - [Clerics](#clerics)
    - [Nobles](#nobles)
    - [Warlocks](#warlocks)
21. [NPC Enemies](#npc-enemies)
22. [Campaign System](#campaign-system)
23. [AI System](#ai-system)
24. [LAN Multiplayer](#lan-multiplayer)

---

## Overview

Fabled is a turn-based tactical RPG built in Python/Pygame. Two teams of up to 3 adventurers each fight in a formation-based system. On each round, both players simultaneously select actions for their units, then resolve those actions in initiative order. The game supports single-player campaign (vs AI), local two-player, and LAN multiplayer.

---

## Game Modes

| Mode | Description |
|------|-------------|
| **Campaign** | Single-player story mode. Player builds a team from unlocked adventurers and fights a sequence of AI-controlled enemy teams. Winning grants campaign rewards (new adventurers, abilities, items). |
| **Practice** | Local two-player hotseat. Both players share the same screen, taking turns with the keyboard/mouse to select actions. No persistent rewards. |
| **Local Multiplayer** | Same as Practice (local hotseat variant). |
| **LAN Multiplayer** | Two players on the same network. One is the host, one is the client. The host runs the game simulation; the client receives state updates and sends action selections. |
| **Team Builder** | A meta-screen for constructing and saving team compositions outside of combat. |

---

## Formation and Slots

Each team occupies three slots in a fixed formation:

```
Team                 Enemy Team
[ BACK_LEFT ]        [ BACK_LEFT ]
[ BACK_RIGHT ]       [ BACK_RIGHT ]
[ FRONT ]            [ FRONT ]
```

- **SLOT_FRONT** (`"front"`): The active frontline position. The frontline unit is the primary target for attacks and uses the "frontline" version of every ability.
- **SLOT_BACK_LEFT** (`"back_left"`): Backline position.
- **SLOT_BACK_RIGHT** (`"back_right"`): Backline position.

**Key formation rules:**
- Melee targeting normally forces the attacker to target the enemy frontline. Only abilities with `cant_redirect` or specific effects can bypass this.
- Backline units use the "backline" version of their abilities, which are usually reduced in damage or have different effects.
- If the frontline slot is empty (KO or swap), a backline unit becomes exposed and can be targeted normally.
- Certain abilities (Hawkshot, Volley, Hunter's Mark, etc.) are ranged and can hit backline targets directly.
- Some talents and signatures give special targeting flexibility (e.g., Shadowstep, Flowing Locks).
- **Adjacent left**: Some effects spread to the unit "adjacent left," defined as BACK_LEFT adjacent to FRONT, and BACK_RIGHT adjacent to BACK_LEFT, wrapping. Used by Witch of the Woods talent (Double Double).

---

## Stats

Every adventurer has four base stats:

| Stat | Effect |
|------|--------|
| **HP** | Maximum and starting hit points. Unit is KO'd at 0 HP. |
| **Attack** | Scales outgoing damage. Higher attack = more damage dealt. |
| **Defense** | Reduces incoming damage. Higher defense = less damage taken. |
| **Speed** | Determines initiative (who acts first each round). |

**Current stat ranges across the roster:**
- HP: 180 (Witch of the Woods) – 280 (Porcus III)
- Attack: 35 (Porcus III) – 80 (Little Jack / Gretel)
- Defense: 35 (March Hare / Witch of the Woods) – 85 (Porcus III)
- Speed: 20 (Porcus III) – 75 (Lucky Constantine / Reynard)

**Effective stats**: During combat, a unit's `get_stat(stat)` applies all active buffs and debuffs to the base value. Buffs are additive; debuffs subtract from the buffed value. The minimum effective stat is clamped at a floor (no negative stats).

---

## Round Structure and Turn Flow

Each battle round proceeds through these phases:

### 1. Initiative Determination
Compare each team's frontline speed stat. The team with the higher frontline speed acts first. On a tie, the tie is broken by the sum of all alive units' speeds. If still tied, the previous round's initiative winner wins again (or Player 1 wins on the very first round).

### 2. Round Start Effects
`apply_round_start_effects()` fires before action selection:
- **Briar Rose (Curse of Sleeping)**: Finds the lowest-HP Rooted enemy, strips their Root, prevents them from acting this round, and makes them immune to Root next round.
- *(Future effects would be added here)*

### 3. Extra Swap Phase (optional)
Certain passive signatures grant a free swap at the start of the round before action selection:
- **Rapunzel's Flowing Locks**: Rapunzel may swap to frontline without consuming her swap slot.
- **Ashen Ella's Two Lives / Midnight Dour**: Related swap logic.
- Each player with an eligible unit gets prompted for an extra swap (or can skip).

### 4. First Player Action Selection
The initiative winner selects actions for each of their alive units, in order. For each unit, the player can choose:
- A signature ability (if unlocked)
- A basic ability (from their class pool, if unlocked)
- Use their item
- Swap positions with a teammate

Once an action is queued for each unit, selection is confirmed and passed to the second player.

### 5. Second Player Action Selection
Same as above for the other team.

### 6. Resolution
Actions resolve in the order units were queued. Within a team, actions are resolved in slot order (FRONT first, then BACK_LEFT, then BACK_RIGHT). Each unit's queued action is executed via `resolve_queued_action()`.

**Resolution includes:**
- Computing and dealing damage
- Applying status effects
- Applying stat buffs/debuffs
- Triggering on-hit effects (vamp, Spiked Mail, Reflecting Pool, Nine Lives, etc.)
- Triggering on-KO effects (Sugar Rush, Postmortem Passage, Flame of Renewal)
- Triggering passive effects (Garden of Thorns, Midnight Dour, etc.)

After the initiative player resolves all their units, the second player's units resolve.

### 7. End of Round
`apply_end_of_round()` fires after both teams have resolved:
- **Burn**: Deals 10 damage per round to Burned units.
- **Shock**: Deals 5 damage per round to Shocked units.
- **Sanctuary (Aldric S2)**: Heals allies each round.
- **Growing Pains (Pinocchio talent)**: Gains Malice if frontline at end of round.
- **Buff/debuff duration decrement**: All buff and debuff durations tick down by 1; expired entries are removed.
- **Spinning Wheel BL**: On ally buff expiry, Rumpelstiltskin may spend 2 Malice to refresh it.
- **Status duration decrement**: All status conditions tick down by 1; expired statuses are removed, triggering any on-expiry effects (e.g., Innocent Heart).
- **Birdsong (Aurora S3)**: Cures the last-inflicted status on each ally once per round.
- **Sturdy Home / Porcine Honor / Armored passives**: Passive stat adjustments re-applied each round.

### 8. Battle End Check
If all units on a team are KO'd, that team loses. The battle ends and rewards (campaign) or results screen (practice/multiplayer) are shown.

### 9. Next Round
Round number increments. Go to step 1.

---

## Initiative

Initiative determines which player acts first each round.

**Algorithm (`determine_initiative`):**
1. Get the speed of each team's frontline unit (using `get_stat("speed")`).
2. If one team's frontline is faster, that team wins initiative.
3. If tied: sum all alive units' speeds on each team; higher sum wins.
4. If still tied: the previous winner retains initiative (or Player 1 wins round 1).
5. The initiative result and reason are stored in `battle.init_player` and `battle.init_reason`.

**Special initiative modifiers:**
- **March Hare talent (On Time!)**: While March Hare is frontline, the enemy frontline has -15 Speed. This indirectly affects initiative.
- **Tempus Fugit (March Hare S1)**: Swaps initiative for the round — the player who would go second now goes first.
- **Stitch In Time (March Hare twist)**: Grants the player initiative for 2 rounds regardless of speed.

---

## Actions

On their turn, each alive unit must queue exactly one action. Available action types:

### Signature Ability
An ability specific to the adventurer. There are 3 signature slots; each requires an unlock tier. In campaign, signatures are unlocked progressively (sig_tier 1, 2, 3). In practice/multiplayer, all are available.

### Basic Ability
A class-wide ability from a pool of 5 basics per class. Each basic has a frontline and backline version. In campaign, basics are unlocked by class (one class pool at a time). Players choose 2 basics per adventurer at team-build time.

### Item
Each adventurer may carry one item. Active items are consumed (or tracked for once-per-battle limits) when used. Passive items trigger automatically and don't require action selection.

### Swap
The unit switches positions with a teammate (front ↔ backline, or backline ↔ backline). Each team gets **one swap action per round** (tracked as `swap_used_this_turn`). Some effects grant extra swaps. A swapped unit cannot use the same swap again on consecutive turns unless specific passives allow it.

**Swap restrictions:**
- Cannot swap if Rooted.
- Swapping consumes the team's swap token.
- Some signatures grant free/extra swaps (Ella's Flowing Locks, Noble's Summons basic, Smoke Bomb item).

---

## Ability Categories

Every ability is either `passive=True` or `passive=False`:

- **Active** (`passive=False`): The player selects this as an action; it fires during resolution.
- **Passive** (`passive=True`): The ability's effect is always active while the unit is alive and in the correct position. Passive abilities cannot be selected as an action — the system automatically applies them as ongoing effects or triggered reactions.

Abilities have two modes: **frontline** and **backline**, each represented by an `AbilityMode` dataclass. An `AbilityMode` with `unavailable=True` cannot be used from that position.

---

## Damage Calculation

Damage is calculated in `compute_damage()`:

```
base_power = mode.power
```

**Power bonuses (additive to power before the damage formula):**

| Condition | Bonus |
|-----------|-------|
| `bonus_vs_low_hp` | +N if target is below 50% max HP |
| `bonus_vs_rooted` | +N% more damage if target is Rooted (ratio, e.g. 0.4 = +40%) |
| `bonus_if_not_acted` | +N if target has not yet acted this round |
| `bonus_if_target_acted` | +N if target has already acted this round |
| `bonus_vs_higher_hp` | +N if target's max HP > actor's max HP |
| `bonus_vs_backline` | +N if target is in a backline slot |
| `bonus_vs_statused` | +N if target has any active status condition |
| Arcane Focus item | +7 attack to user when acting from backline |
| Family Seal item | +10 power to signature abilities |
| Misericorde item | +10 damage if target has a status condition |
| Heedless Pride talent | +20% damage to enemy frontline (and +10% received from enemy frontline) |
| Giant Slayer talent | +30% damage to targets with higher max HP |
| Keen Eye talent | +15 damage to backline enemies |
| Challenge Accepted talent | +25 damage to the target directly across from the Green Knight |
| Electrifying Trance | +15 damage to Shocked targets (talent-based, applies to allies too) |
| Spinning Wheel FL | +7 damage per unique stat buff active among all other adventurers |
| Tyranny (Dragon NPCs) | +5 damage if target has 2+ active statuses |
| Cataclysm FL | +10 damage per active status on target |

**Spread:** If `mode.spread=True`, the ability hits all legal enemy targets at 50% of normal damage. Robin's Spread Fortune reduces the 50% penalty (or removes it for backline).

**Defense ignore:** `def_ignore_pct` causes the attacker to ignore that percentage of the target's defense (e.g., `def_ignore_pct=20` ignores 20% of defense).

**Guard reduction:** If the target has the Guard status and the attack does not have `ignore_guard=True`, the damage is multiplied by 0.80 (20% reduction). If the target is also Exposed, Guard is not applied.

**Damage formula:**
```
dmg = power * (attack / defense)
dmg = round to integer (ceiling)
```
Where `attack` = actor's effective attack stat, `defense` = target's effective defense stat. Minimum damage is 0.

**Apex Warden NPC:** Any damage to a frontline target (other than itself) is reduced by 10 while the Apex Warden is alive.

---

## Status Conditions

Status conditions are tracked per-unit as a list of `StatusEffect(kind, duration)`. Duration decrements each end of round. Expired statuses are removed and may trigger on-expiry effects.

| Status | Effect |
|--------|--------|
| **burn** | Deals 10 damage at end of each round. |
| **shock** | Deals 5 damage at end of each round. *(Can imply action denial in some design contexts — currently only damage.)* |
| **root** | Unit cannot swap positions. |
| **weaken** | Unit's Attack stat is reduced (via debuff tracking, not a raw status). *(Functionally applied as a stat debuff in many cases; the status tag exists for targeting checks.)* |
| **expose** | Unit's Defense stat is reduced. Also bypasses Guard. |
| **guard** | Unit takes 20% less damage. Incoming attackers are redirected to the Guarding unit if applicable. |
| **spotlight** | Unit must be targeted by enemies (forced target). |
| **no_heal** | Unit cannot receive healing. |
| **reflecting_pool** | Reflects 20% of incoming damage back to attacker (10% from frontline attackers). Applied by Lake's Gift signature. |
| **buff_nullify** | Unit's stat buffs are nullified when applied. Applied by Name the Price BL (Rumpelstiltskin). |
| **burn_immune** | Unit cannot receive the Burn status. Applied by Purifying Flame (Liesl healing). |

**Special condition tracking (via `ability_charges` dict):**
- `briar_cant_act`: Unit cannot act this round (Curse of Sleeping trigger).
- `briar_root_immune`: Unit cannot receive Root this round (Curse of Sleeping follow-up).
- `holy_diadem`: Whether the Holy Diadem passive has been used (1 = available, 0 = spent).
- `nine_lives`: Remaining charges for Nine Lives (Lucky Constantine signature).
- `midnight_dour_triggered`: Whether Midnight Dour's auto-swap already fired.
- `purifying_flame`: Whether the unit will Burn their next target.
- `fated_duel_rounds`: Active rounds of Fated Duel lock.
- `command_allies_p{n}` / `command_user_p{n}`: Command passive damage tracking.
- `chosen_one_mark`: Active rounds of Chosen One mark.
- `chosen_one_champion`: Target unit ID for Chosen One.
- Various recharge counters (see Recharge section).

**Innocent Heart (Aurora talent):** When any status expires (naturally or by cure) on Aurora or an ally, that unit gains +10 Defense for 2 rounds and Aurora heals 20 HP. This triggers on `_trigger_innocent_heart()`.

**Briar Rose's Curse of Sleeping:** At the start of each round, the lowest-HP Rooted enemy unit has their Root stripped, cannot act that round, and cannot be Rooted for one round. The root removal triggers Innocent Heart if Aurora is on the affected team.

---

## Stat Buffs and Debuffs

Buffs and debuffs are tracked separately from status conditions. Each is a `StatMod(stat, amount, duration)`. They tick down each end of round.

**Buffable/debuffable stats:** `attack`, `defense`, `speed`.

**Buff nullify:** If a unit has the `buff_nullify` status, any attempt to apply a stat buff to them is blocked.

**Art of the Deal (Rumpelstiltskin talent):** Whenever any other adventurer (on either team) gains a stat buff, Rumpelstiltskin gains 1 Malice. This fires inside `apply_stat_buff()`.

**Straw to Gold (Rumpelstiltskin S2):**
- FL: Steal the highest stat buff from an ally for 2 rounds; add +5 to it per Malice; when it expires from Rumpel, it's returned to the ally.
- BL: Convert an ally's highest stat debuff into a stat buff of the same amount.

**Thieve the First-Born (Rumpelstiltskin twist):** Steal all stat buffs from enemies, refresh their duration, and add +5 per Malice to each.

---

## Guard Mechanic

**Applying Guard:** Guard is a status (`guard`) applied by abilities like Shield Bash, Bless, Crafty Shield (item), Roland's Shimmering Valor, etc. Duration is typically 2 rounds.

**Guard effect on damage:** When a guarded unit takes damage, the damage is multiplied by 0.80 (20% reduction). Exception: if the unit also has `expose` status, Guard does not apply.

**Guard redirect:** When an enemy ability would target a guarded ally, the guarded unit intercepts the attack (if they are not the intended target and are on the same team). Abilities with `cant_redirect=True` bypass this — the attack always hits the intended target.

**guard_all_allies:** Applies Guard to every alive ally (e.g., Shield Bash FL).
**guard_target:** Applies Guard to the selected target ally (e.g., Bless, Crafty Shield).
**guard_frontline_ally:** Applies Guard only to the frontline ally (e.g., Shield Bash BL).
**guard_self:** Applies Guard to the acting unit itself (e.g., Slam BL).

**Silver Aegis (Sir Roland talent):** The first ability to hit Roland after he swaps to frontline deals 0 damage. Tracked via `ability_charges["silver_aegis"]`.

---

## Healing

Healing targets restore HP up to their max HP. Cannot heal KO'd units.

**`no_heal` status:** If a unit has the `no_heal` status (applied by Cauterize), healing has no effect on them.

**Healing modifiers:**
- **Heart Amulet item**: The healer's healing effects restore 15 additional HP.
- **Benefactor (Aldric S1)**: Aldric's healing heals 25% more from frontline, 15% more from backline.
- **All-Caring (Aldric talent)**: When Aldric's healing actually restores HP, the recipient gains Guard for 2 rounds.
- **Purifying Flame (Liesl talent)**: Any healing by Liesl grants Burn immunity (2r) and marks the recipient to Burn their next target.
- **Medic basic (Cleric)**: Healing cures all status conditions on the target. Frontline also clears stat debuffs.

**Heal types:**
- `heal`: Heals a targeted ally by a flat amount.
- `heal_self`: Heals the acting unit (not the target) by a flat amount. Applied alongside other effects.
- `heal_lowest`: Heals the ally with the lowest current HP by a flat amount.
- Item heals (`Item.heal`): Flat heal applied to self or a target.

**Cinder Blessing (Liesl S1) FL:** Sets Liesl's and an ally's HP to the average of both (HP equalization), then applies Purifying Flame.

**Redemption (Aldric twist):** Grants Aldric +100 max HP and causes him to heal 50 HP at end of round for 2 rounds.

---

## Lifesteal (Vamp)

Vamp causes the attacker to heal for a percentage of damage dealt.

**Sources of vamp:**
- `mode.vamp`: Ability-specific vamp ratio (e.g., Repentance S3 Aldric: 35% FL, 20% BL).
- **Vampire Fang item**: +10% vamp on all abilities.
- **Risa Redcloak talent (Red and Wolf)**: When Risa is below 50% max HP, her abilities gain 20% vamp. This stacks with other sources.
- **Blood Hunt (Risa S3) FL**: Double Vamp mode — uses 2× the talent-based vamp (Risa's 20% becomes 40%), but does NOT include Risa's own base vamp. `double_vamp_no_base=True`.

Healing from vamp goes through `do_heal()` so it benefits from Aldric's Benefactor, All-Caring, and Liesl's Purifying Flame.

---

## Swap Mechanic

**Normal swap**: A unit swaps frontline/backline positions with a teammate. Consumes the team's swap token (`swap_used_this_turn`). Cannot be used if Rooted.

**Swap rules:**
- Only one normal swap per team per round.
- Swapping is tracked as `rounds_since_swap` on the swapped unit, used by Natural Order (Green Knight S2).
- Summons (Noble basic) is an active ability that performs a swap — uses the swap token. Cannot be used on consecutive turns (tracked by `summons_cd` charge).

**Free / extra swaps:**
- **Flowing Locks (Rapunzel talent)**: Once per battle (refreshes after ending a round in backline), Rapunzel can swap to frontline ignoring melee targeting restrictions. This is an extra swap at round start before normal action selection.
- **Void Step BL (Warlock basic)**: On swapping to frontline, the user spends 2 Malice to gain +10 Speed for 2 rounds.
- **Void Step FL**: On swapping to backline, the user gains 1 Malice.
- **Smoke Bomb item**: Active item that swaps the user with an ally.
- **Faustian Bargain (Asha S3)**: Triggers on-swap effects automatically.

**On-KO swap logic**: When a frontline unit is KO'd, the game may auto-promote a backline unit to frontline.

**Midnight Dour (Ashen Ella S2)**: Passive — when Ella drops to ≤50% HP while frontline, she automatically swaps to backline (once per battle). Not a player-triggered swap.

---

## Malice Resource (Warlock)

Malice is a resource unique to Warlock-class adventurers. It is tracked per-unit as `ability_charges["malice"]`.

**Default cap:** 6. Pinocchio's Blue Faerie's Boon increases this by 6 (temporarily).

**Gaining Malice:**
- Warlock basic abilities (Dark Grasp FL, Soul Gaze BL, Blood Pact FL).
- **Growing Pains (Pinocchio talent)**: At end of round, if Pinocchio is frontline, gain 1 Malice.
- **Art of the Deal (Rumpelstiltskin talent)**: Gain 1 Malice whenever any other adventurer gains a stat buff.
- **Stolen Voices (Asha talent)**: When backline, gain 1 Malice each time an enemy uses a signature ability.
- **Cursed Armor basic (passive)**: Gain 1 Malice when damaged by an enemy ability.
- **Void Step FL (basic passive)**: Gain 1 Malice when swapping to backline.
- **Turn to Foam (Asha twist)**: Gains 3 Malice as part of the ability, then consumes all.

**Spending Malice:**
- Dark Grasp BL: Spend 1 Malice to Weaken target for 2 rounds.
- Soul Gaze FL: Spend 1 Malice to Expose target for 2 rounds.
- Blood Pact BL: Spend 1 Malice to heal additional 20 HP.
- Various signatures: "spend 2 Malice to [effect]."
- Turn to Foam: Consumes ALL Malice to give enemies -10 Defense per Malice for 2 rounds.

**Malice as a stat modifier:**
- **Pinocchio**: +5 Attack and +5 Defense per Malice (always active while alive).
- **Rumpelstiltskin**: +5 Speed per Malice.
- **Wooden Wallop (Pinocchio S1) FL**: +10 power per Malice.
- **Straw to Gold FL**: +5 to the stolen buff per Malice.
- **Thieve the First-Born**: +5 to each stolen buff per Malice.
- **Become Real (Pinocchio S3) FL**: At 3+ Malice, abilities gain +15 damage and Pinocchio is immune to statuses.
- **Become Real BL**: At 3+ Malice, abilities do not increment ranged recharge.
- **Stolen Voices FL**: Enemy signatures deal -5 damage per Malice Asha has.

---

## Recharge Mechanic

Some abilities (primarily ranged attacks) have a recharge cost: after use, they cannot be used again for a set number of rounds. Tracked in `ability_charges`.

**Ranged recharge**: abilities marked with a recharge value increment a counter when used from backline. The ability is unavailable if the counter > 0. At the end of each round, counters decrement.

**Become Real BL (Pinocchio)**: At 3+ Malice, using abilities from backline does not increment the ranged recharge counter.

---

## Items

Each adventurer may equip one item. Items are either **active** (require an action to use) or **passive** (always active).

### Active Items

| Item | Effect |
|------|--------|
| **Health Potion** | Heals the user 60 HP. Self-only. |
| **Healing Tonic** | Heals the user or a chosen ally 40 HP. |
| **Crafty Shield** | Guards the user or a chosen ally for 2 rounds. |
| **Lightning Boots** | User gains +10 Speed for the next round (duration 2 in implementation, representing the coming round). |
| **Main-Gauche** | User gains +10 Attack for 2 rounds. |
| **Iron Buckler** | User gains +10 Defense for 2 rounds. |
| **Smoke Bomb** | User switches positions with an ally (extra swap, does not consume normal swap token). |
| **Hunter's Net** | Roots the target for 2 rounds. |
| **Ancient Hourglass** | User cannot act next round but also cannot be targeted next round. Once per battle. |

### Passive Items

| Item | Effect |
|------|--------|
| **Family Seal** | User's signature abilities deal +10 damage. |
| **Holy Diadem** | Once per battle: when fatal damage would KO the user, survive at 1 HP and take no further damage that round. |
| **Vampire Fang** | User's abilities have 10% lifesteal. |
| **Spiked Mail** | Enemies that damage the user take 15 reflected damage. Does not apply on KO. |
| **Arcane Focus** | User has +7 Attack when using abilities from the backline. |
| **Heart Amulet** | User's healing effects restore 15 additional HP. |
| **Misericorde** | User deals +10 more damage to targets with any active status condition. |

---

## Basic Abilities by Class

Each class has 5 basics. Players pick 2 per adventurer at team build time.

### Fighter
| Ability | Frontline | Backline |
|---------|-----------|----------|
| **Strike** | 55 power | n/a |
| **Rend** | 45 power, +20 power vs <50% HP | Mark: user's next ability vs this target gets +10 power |
| **Feint** | 45 power, +10 Speed self (2r) | +10 Speed self (2r) |
| **Cleave** | 45 power, ignore 20% Defense | Mark: user's next ability vs target ignores 10% Defense |
| **Intimidate** | 45 power, Weaken target (2r) | Weaken target (2r) |

### Rogue
| Ability | Frontline | Backline |
|---------|-----------|----------|
| **Sneak Attack** | 45 power, +15 if target hasn't acted | Target -10 Speed (2r) |
| **Riposte** | 45 power, user takes 50% less damage this round | User takes 50% less damage this round |
| **Post Bounty** | 40 power, Expose target (2r) | Expose target (2r) |
| **Sucker Punch** | 40 power, +20 power vs Exposed/Weakened target | Weaken target (2r) |
| **Fleetfooted** | Passive: first incoming ability each round deals 20% less damage | Passive: first incoming ability each round deals 10% less damage |

### Warden
| Ability | Frontline | Backline |
|---------|-----------|----------|
| **Shield Bash** | 40 power, Guards all allies (2r) | Guard frontline ally (2r) |
| **Condemn** | 40 power, target -10 Attack (2r) | Target -10 Attack (2r) |
| **Slam** | 45 power, +15 power if user is Guarded | Guard self (2r) |
| **Armored** | Passive: +10 Defense | Passive: +5 Defense |
| **Stalwart** | Passive: User takes -10 damage from all abilities | Passive: Frontline ally takes -10 damage from abilities |

### Mage
| Ability | Frontline | Backline |
|---------|-----------|----------|
| **Fire Blast** | 60 power, Burn target (2r) | 35 power, Burn target (2r) |
| **Thunder Call** | 60 power, Shock target (2r) | 35 power, Shock target (2r) |
| **Freezing Gale** | 60 power, Root target (2r) | 35 power, Root target (2r) |
| **Arcane Wave** | 70 power, self -10 Atk and -10 Def (2r) | 40 power |
| **Breakthrough** | +15 Attack self (2r) | +10 Attack self (2r), Spotlight self (2r) |

### Ranger
| Ability | Frontline | Backline |
|---------|-----------|----------|
| **Hawkshot** | 60 power, can't be redirected | 40 power, can't be redirected |
| **Volley** | 60 power, spread | 40 power, spread |
| **Hunter's Mark** | 50 power, target takes +10 damage from abilities next round | 25 power, same mark |
| **Trapping Blow** | 60 power, Root target if they are Weakened | 35 power, Weaken target (2r) |
| **Hunter's Badge** | Passive: +10 Attack | Passive: +5 Attack |

### Cleric
| Ability | Frontline | Backline |
|---------|-----------|----------|
| **Heal** | Heal target ally 60 HP | Heal target ally 45 HP |
| **Bless** | Guard target ally (2r), +10 Attack to target (2r) | Guard target ally (2r) |
| **Smite** | 55 power, Burn target (2r) | 40 power |
| **Medic** | Passive: healing cures statuses and debuffs | Passive: healing cures statuses |
| **Protection** | Passive: allies have +10 Defense | Passive: allies have +5 Defense |

### Noble
| Ability | Frontline | Backline |
|---------|-----------|----------|
| **Impose** | 50 power, target -10 Speed (2r) | 30 power, target -10 Speed (2r) |
| **Edict** | 50 power, Root target (2r) | 30 power, Spotlight target (2r) |
| **Decree** | 40 power, self +10 Attack (2r) | 25 power, target -10 Attack (2r) |
| **Summons** | Swap with an ally (no consecutive turns) | Same |
| **Command** | Passive: enemies that attacked this unit last round take +10 damage from ally abilities | Passive: enemies that attacked an ally last round take +10 damage from this unit's abilities |

### Warlock
| Ability | Frontline | Backline |
|---------|-----------|----------|
| **Dark Grasp** | 50 power, gain 1 Malice | 35 power, spend 1 Malice to Weaken target (2r) |
| **Soul Gaze** | 45 power, spend 1 Malice to Expose target (2r) | 30 power, gain 1 Malice |
| **Blood Pact** | User loses 20 HP, gains 2 Malice | User heals 20 HP; spend 1 Malice to heal 20 more |
| **Cursed Armor** | Passive: gain 1 Malice when damaged by an enemy ability | Passive: same |
| **Void Step** | Passive: on swap to backline, gain 1 Malice | Passive: on swap to frontline, spend 2 Malice for +10 Speed (2r) |

---

## All Adventurers

### Fighters

#### Risa Redcloak
- **Stats**: HP 250, Atk 75, Def 60, Spd 30
- **Talent — Red and Wolf**: Below 50% max HP: +15 Atk, +15 Spd, abilities gain 20% vamp.
- **Sig 1 — Crimson Fury**: FL: 60 power, spread. BL: 40 power, +10 power vs <50% HP targets.
- **Sig 2 — Wolf's Pursuit**: FL: 50 power, +10 Speed (2r). BL: 35 power, +10 Speed (2r), ignores Guard.
- **Sig 3 — Blood Hunt**: FL: 60 power, 2× the talent-based vamp (no base vamp). BL: 30 power, 20% vamp, ignores Guard.
- **Twist — Grandmother's Vengeance**: 70 power, Risa gains +20 Atk for 3 rounds.

#### Little Jack
- **Stats**: HP 220, Atk 80, Def 50, Spd 50
- **Talent — Giant Slayer**: Deals 30% bonus damage to targets with higher max HP than Jack.
- **Sig 1 — Skyfall**: FL: 60 power, spread. BL: 50 power.
- **Sig 2 — Belligerence**: Passive. FL: Jack's abilities deal +10 damage to targets that have already acted. BL: Jack's abilities deal +5 damage to targets that have already acted.
- **Sig 3 — Magic Growth**: FL: 55 power, Jack gains +10 Atk (2r). BL: Heal Jack 40 HP, gain +10 Def (2r).
- **Twist — Fell the Beanstalk**: 75 power, spread, deals 30% more damage to targets with higher max HP (stacks with talent).

#### Witch-Hunter Gretel
- **Stats**: HP 215, Atk 80, Def 45, Spd 60
- **Talent — Sugar Rush**: On KO'ing an enemy, Gretel gains +15 Atk and +10 Spd for 2 rounds.
- **Sig 1 — Shove Over**: FL: 60 power, target -10 Def (2r). BL: 35 power, target -10 Def (2r).
- **Sig 2 — Hot Mitts**: Passive. FL: Gretel's abilities can Burn targets regardless of position. BL: On taking damage, reflect Burn to attacker (2r).
- **Sig 3 — Crumb Trail**: FL: 60 power, ignores Guard. BL: 40 power, Expose target (2r).
- **Twist — Into the Oven**: 70 power, Burn + Weaken + Root target (2r each).

---

### Rogues

#### Lucky Constantine
- **Stats**: HP 215, Atk 70, Def 40, Spd 75
- **Talent — Shadowstep**: Constantine ignores melee targeting against Exposed targets. Takes -10 damage from backline attackers.
- **Sig 1 — Feline Gambit**: FL: 55 power, +15 power if target hasn't acted. BL: 40 power.
- **Sig 2 — Subterfuge**: FL: 50 power, Expose target (2r), ignores Guard. BL: 30 power, target -10 Spd (2r).
- **Sig 3 — Nine Lives**: Passive. Constantine has up to 3 charges of Nine Lives. While Exposed targets deal the killing blow, he survives at 1 HP (costs 1 charge).
- **Twist — Final Deception**: 65 power, spread, +20 power if targets are Exposed.

#### Hunold the Piper
- **Stats**: HP 210, Atk 60, Def 45, Spd 65
- **Talent — Electrifying Trance**: Shocked enemies take +15 damage from all abilities (teammate abilities included).
- **Sig 1 — Haunting Rhythm**: FL: 50 power, Shock target (2r). BL: 35 power, Shock target (2r).
- **Sig 2 — Dying Dance**: FL: 55 power, spread, Shock targets (2r). BL: 40 power, Shock target (2r).
- **Sig 3 — Hypnotic Aura**: Passive. FL: Each round, Shock a random enemy (or lowest HP) for 2 rounds. BL: Shocked enemies take -10 Speed.
- **Twist — Devil's Due**: 70 power, spread, Shock targets (2r), +15 power per already-Shocked target.

#### Reynard, Lupine Trickster
- **Stats**: HP 205, Atk 65, Def 45, Spd 75
- **Talent — Cunning Dodge**: The first ability each battle that hits Reynard deals 50% damage. Refreshes on swap.
- **Sig 1 — Size Up**: FL: 55 power, +15 power if target has acted this round. BL: 30 power, target -10 Atk (2r).
- **Sig 2 — Feign Weakness**: FL: 40 power, Reynard's next incoming hit triggers a 60-power retaliation. BL: Same retaliation setup with speed steal.
- **Sig 3 — Cutpurse**: FL: 50 power, steal target's highest stat buff and apply it to Reynard (2r). BL: 35 power, Expose target (2r).
- **Twist — Last Laugh**: Feign Weakness retaliation also steals Speed from the attacker.

---

### Wardens

#### Sir Roland
- **Stats**: HP 265, Atk 40, Def 80, Spd 30
- **Talent — Silver Aegis**: The first ability that hits Roland after he swaps to frontline deals 0 damage.
- **Sig 1 — Shimmering Valor**: FL: 40 power, Guard self (2r), +10 Def (2r). BL: Guard self (2r), +10 Def (2r).
- **Sig 2 — Knight's Challenge**: FL: 50 power, target must target Roland for 2 rounds (Spotlight on Roland as mandatory target). BL: Guard frontline ally (2r), +10 Def to ally (2r).
- **Sig 3 — Banner of Command**: Passive. FL: Ally abilities deal +10 damage to enemies that attacked Roland last round. BL: Roland's abilities deal +10 damage to enemies that attacked allies last round.
- **Twist — Purehearted Stand**: Roland gains +30 Defense for 2 rounds and Guards all allies for 2 rounds.

#### Porcus III
- **Stats**: HP 280, Atk 35, Def 85, Spd 20
- **Talent — Bricklayer**: If a single ability would deal 25%+ of Porcus's max HP, reduce that damage by 40% and Weaken the attacker (2r).
- **Sig 1 — Not By The Hair**: FL: 50 power, +15 power if Porcus is Guarded. BL: Guard self (2r).
- **Sig 2 — Porcine Honor**: Passive. FL: Porcus takes -10 damage from abilities. BL: Frontline ally takes -10 damage from abilities.
- **Sig 3 — Sturdy Home**: Passive. FL: Allies have +10 Defense. BL: Allies have +5 Defense.
- **Twist — Unbreakable Defense**: Porcus gains +20 Defense (permanent for the battle) and regenerates 30 HP at end of each round for 3 rounds.

#### Lady of Reflections
- **Stats**: HP 255, Atk 40, Def 75, Spd 32
- **Talent — Reflecting Pool**: When damaged, reflects 10% of incoming damage to the attacker. 20% if the attacker is backline.
- **Sig 1 — Drown in the Loch**: FL: 50 power, target -10 Def (2r). BL: 35 power, Root target (2r).
- **Sig 2 — Postmortem Passage**: Passive. FL & BL: When a teammate is KO'd, Lady fires a posthumous 40-power attack at the killer.
- **Sig 3 — Lake's Gift**: FL: 45 power, Lady gains Reflecting Pool status (20%/10% reflect) for 2 rounds. BL: Heal lowest HP ally 50 HP, apply Reflecting Pool to them (2r).
- **Twist — Journey to Avalon**: 60 power, spread, Lady gains Reflecting Pool (3r). All allies gain Reflecting Pool (2r).

---

### Mages

#### Ashen Ella
- **Stats**: HP 185, Atk 80, Def 40, Spd 65
- **Talent — Two Lives**: While Ella is backline, she cannot be targeted. However, Ella can only use abilities (not items/swaps for ability purposes) while frontline. (She IS actionable from backline, just untargetable by enemies.)
- **Sig 1 — Crowstorm**: FL: 65 power, spread. BL: n/a (Ella can't use abilities BL — she uses the BL version which is unavailable or she is protected).
- **Sig 2 — Midnight Dour**: Passive. FL: When Ella drops to ≤50% HP while frontline, she auto-swaps to backline (once per battle). BL: *(setup/detection passive)*.
- **Sig 3 — Fae Blessing**: FL: 55 power. BL: Heal target ally 50 HP (ignores Two Lives constraint on healing).
- **Twist — Struck Midnight**: 75 power, spread, ignores Guard.

#### March Hare
- **Stats**: HP 190, Atk 70, Def 35, Spd 70
- **Talent — On Time!**: While March Hare is frontline, the enemy frontline has -15 Speed (applied as a persistent debuff).
- **Sig 1 — Tempus Fugit**: FL: 55 power, swaps initiative for the current round. BL: 35 power, +10 Speed self (2r).
- **Sig 2 — Rabbit Hole**: FL: 50 power, Root target (2r), +10 Speed self (2r). BL: 35 power, Shock target (2r).
- **Sig 3 — Nebulous Ides**: FL: 60 power, Burn + Shock target (2r each). BL: 40 power, target -10 Speed (2r).
- **Twist — Stitch In Time**: The acting player has initiative for 2 full rounds regardless of speed.

#### Witch of the Woods
- **Stats**: HP 180, Atk 75, Def 35, Spd 65
- **Talent — Double Double**: When Witch damages a target with any active status, the target's last inflicted status is spread to the adjacent-left enemy (2r).
- **Sig 1 — Toil and Trouble**: FL: 60 power, spread, Weaken all targets (2r). BL: 40 power, Weaken target (2r).
- **Sig 2 — Cauldron Bubble**: FL: 55 power, Burn + Shock target (2r each). BL: 35 power, Burn target (2r).
- **Sig 3 — Crawling Abode**: Passive. FL: Witch's abilities have +15 damage to statused targets. BL: End of round, apply a random status to the frontline enemy.
- **Twist — Vile Sabbath**: 70 power, spread, reapply each target's last inflicted status and refresh its duration.

---

### Rangers

#### Briar Rose
- **Stats**: HP 195, Atk 60, Def 45, Spd 60
- **Talent — Curse of Sleeping**: At round start, the lowest-HP Rooted enemy loses Root, cannot act that round, and cannot be Rooted for one round.
- **Sig 1 — Thorn Snare**: FL: Root target (2r), spread. BL: Root target (2r).
- **Sig 2 — Creeping Doubt**: FL: 50 power, +40% more damage to Rooted targets. BL: 40 power, Root target (2r).
- **Sig 3 — Garden of Thorns**: Passive. FL: Enemies that attack Briar while she's frontline gain Root (2r). BL: Enemies that swap gain Root (2r).
- **Twist — Falling Kingdom**: Refresh Root duration on all Rooted enemies and Weaken them (2r). Root all non-Rooted enemies (2r).

#### Frederic the Beastslayer
- **Stats**: HP 200, Atk 65, Def 45, Spd 60
- **Talent — Heedless Pride**: Frederic deals +20% damage to the enemy frontline AND takes +10% damage from the enemy frontline.
- **Sig 1 — Hero's Charge**: FL: 60 power, Frederic ignores Heedless Pride's incoming penalty this round. BL: 30 power, +12 Speed (2r).
- **Sig 2 — On the Hunt**: FL: 40 power, +15 Atk self (2r). BL: 25 power, Expose target (2r).
- **Sig 3 — Jovial Shot**: FL: 50 power, Weaken target (2r). BL: Heal Frederic 60 HP, but Weaken self (2r).
- **Twist — Slay the Beast**: 65 power, +20 damage to targets with higher max HP, ignores Heedless Pride incoming penalty this round.

#### Robin, Hooded Avenger
- **Stats**: HP 185, Atk 70, Def 40, Spd 65
- **Talent — Keen Eye**: Robin deals +15 damage to backline enemies.
- **Sig 1 — Snipe Shot**: FL: 65 power. BL: 40 power, ignores Guard.
- **Sig 2 — Spread Fortune**: Passive. FL: Spread damage penalty halved (25% instead of 50%). BL: Spread abilities target all enemies (not just frontline).
- **Sig 3 — Bring Down**: FL: 60 power, if target is backline, Robin steals 10 Attack from them (2r). BL: 40 power, Root target (2r).
- **Twist — Kingmaker**: 70 power, +20 damage to backline targets, ignores Guard, cannot be redirected.

---

### Clerics

#### Aldric, Lost Lamb
- **Stats**: HP 230, Atk 45, Def 60, Spd 35
- **Talent — All-Caring**: Aldric's healing effects Guard the recipient for 2 rounds.
- **Sig 1 — Benefactor**: Passive. FL: Aldric's healing heals 25% more HP. BL: 15% more HP.
- **Sig 2 — Sanctuary**: Passive. FL: Allies heal 1/10 of their max HP each round. BL: Frontline ally heals 1/8 max HP each round.
- **Sig 3 — Repentance**: FL: 50 power, 35% vamp. BL: 40 power, 20% vamp.
- **Twist — Redemption**: Aldric gains +100 max HP. He heals 50 HP at end of round for 2 rounds.

#### Matchstick Liesl
- **Stats**: HP 210, Atk 50, Def 50, Spd 50
- **Talent — Purifying Flame**: Liesl's healing grants Burn immunity (2r) to the recipient, and they Burn the target of their next ability (2r).
- **Sig 1 — Cinder Blessing**: FL: Set Liesl's and a target ally's HP to the average of both (HP equalization), then Purifying Flame fires. BL: Liesl heals 60 HP.
- **Sig 2 — Flame of Renewal**: Passive. FL & BL: When Liesl is KO'd, all allies heal for 1/2 Liesl's max HP and Purifying Flame triggers on each.
- **Sig 3 — Cauterize**: FL: 50 power, target cannot be healed (no_heal, 2r). BL: 40 power, no_heal (2r).
- **Twist — Cleansing Inferno**: 65 power, spread, Burn all targets (2r). All allies gain Burn immunity (2r) and Purifying Flame marks.

#### Snowkissed Aurora
- **Stats**: HP 225, Atk 45, Def 60, Spd 40
- **Talent — Innocent Heart**: When any status condition expires or is cured on Aurora or an ally, they gain +10 Defense (2r) and Aurora heals 20 HP.
- **Sig 1 — Toxin Purge**: FL: Remove all status conditions from an ally, +10 Def (2r) per condition removed. BL: Heal ally 40 HP, remove one status.
- **Sig 2 — Dictate of Nature**: FL: 50 power, Root target (2r). BL: 35 power, Weaken target (2r).
- **Sig 3 — Birdsong**: Passive. FL: At end of each round, cure the last-inflicted status on each ally (triggers Innocent Heart). BL: Enemies take -5 damage from abilities for each status active on them.
- **Twist — Deathlike Slumber**: All enemies are inflicted with Root, Weaken, and Shock (2r each).

---

### Nobles

#### Prince Charming
- **Stats**: HP 255, Atk 65, Def 55, Spd 35
- **Talent — Mesmerizing**: While Prince Charming is frontline, enemies that target any ally (not him) gain -10 Attack for 2 rounds.
- **Sig 1 — Condescend**: FL: 55 power, target -10 Def (2r). BL: 35 power, target -10 Def (2r), Expose (2r).
- **Sig 2 — Gallant Charge**: FL: 65 power, ignores Guard, Prince takes -10 Def (2r). BL: 40 power, +10 Atk self (2r).
- **Sig 3 — Chosen One**: Passive. FL: Prince designates an ally as the "Chosen One." Enemies that damage the Chosen One are marked; Prince's next ability vs that enemy deals +20 damage. BL: The Chosen One takes 20% less damage.
- **Twist — Happily Ever After**: All allies heal 50 HP and gain +10 Atk and +10 Def (3r).

#### Green Knight
- **Stats**: HP 275, Atk 60, Def 60, Spd 20
- **Talent — Challenge Accepted**: Green Knight deals +25 damage to the enemy in the slot directly across from him.
- **Sig 1 — Hero's Bargain**: FL: 50 power, Green Knight takes the same damage he deals (self-harm). BL: 40 power, +15 Def self (2r).
- **Sig 2 — Natural Order**: Passive. FL: +15 power to abilities against targets that haven't swapped recently. BL: Enemies that swap gain -10 Atk (2r).
- **Sig 3 — Awaited Blow**: Passive. FL: When an enemy uses an ability on Green Knight while he's frontline, he retaliates with 40 power. BL: *(reduced or different effect)*.
- **Twist — Fated Duel**: For 2 rounds, only Green Knight and the frontline enemy may act. All other units cannot take actions.

#### Rapunzel the Golden
- **Stats**: HP 258, Atk 60, Def 65, Spd 30
- **Talent — Flowing Locks**: Once per battle, Rapunzel can ignore melee targeting restrictions. This refreshes after she ends a round in backline. Grants an extra free swap at round start.
- **Sig 1 — Golden Snare**: FL: 55 power, Root target (2r). BL: 35 power, Spotlight target (2r).
- **Sig 2 — Lower Guard**: FL: 50 power, target -10 Def (2r), ignores Guard. BL: 35 power, target -15 Def (2r).
- **Sig 3 — Ivory Tower**: Passive. FL: Ranged enemies have -10 Defense. BL: Melee enemies have -10 Attack.
- **Twist — Severed Tether**: Flowing Locks is always active for 2 rounds. Rapunzel gains -15 Defense, +20 Attack, and +20 Speed for 2 rounds.

---

### Warlocks

#### Pinocchio, Cursed Puppet
- **Stats**: HP 220, Atk 65, Def 50, Spd 50
- **Talent — Growing Pains**: At end of each round, if Pinocchio is frontline, gain 1 Malice (max 6). Pinocchio has +5 Atk and +5 Def per Malice (always active).
- **Sig 1 — Wooden Wallop**: FL: 60 power, +10 power per Malice. BL: 40 power.
- **Sig 2 — Cut the Strings**: FL: 50 power, Spotlight target (2r). BL: Spend 2 Malice to Spotlight target (2r).
- **Sig 3 — Become Real**: Passive. FL: At 3+ Malice: +15 damage on abilities, immune to all statuses. BL: At 3+ Malice: abilities do not increment ranged recharge.
- **Twist — Blue Faerie's Boon**: Increase Malice cap by 6, gain 6 Malice immediately, then heal 20 HP per current Malice.

#### Rumpelstiltskin
- **Stats**: HP 215, Atk 70, Def 55, Spd 60
- **Talent — Art of the Deal**: When any other adventurer (either team) gains a stat buff, Rumpelstiltskin gains 1 Malice (max 6). Rumpelstiltskin has +5 Speed per Malice.
- **Sig 1 — Name the Price**: FL: Target ally gains +10 Atk (2r). BL: Spend 2 Malice to nullify target's stat buffs for 2 rounds (buff_nullify status).
- **Sig 2 — Straw to Gold**: FL: Steal an ally's highest stat buff (2r), add +5 per Malice, return it when it expires from Rumpel. BL: Convert an ally's highest stat debuff into an equal buff.
- **Sig 3 — Spinning Wheel**: Passive. FL: Rumpelstiltskin deals +7 damage per unique stat buff active among all other adventurers (both teams). BL: When an ally loses a stat buff, spend 2 Malice to refresh it for 2 rounds.
- **Twist — Thieve the First-Born**: 70 power, steal all stat buffs from all enemies, refresh their duration, add +5 per Malice to each.

#### Sea Wench Asha
- **Stats**: HP 210, Atk 75, Def 45, Spd 65
- **Talent — Stolen Voices**: When an enemy uses a signature ability: if Asha is backline, she gains 1 Malice (max 6). If Asha is frontline, that enemy signature deals -5 damage per Malice Asha has.
- **Sig 1 — Abyssal Call**: FL: 60 power, spend 2 Malice to give target -10 Def (2r). BL: 40 power, refresh all existing stat debuffs on target.
- **Sig 2 — Misappropriate**: FL: Spend 2 Malice to use the enemy frontline's signature ability. If it's a passive, Asha gains that passive for 2 rounds instead. BL: 35 power, Root target (2r).
- **Sig 3 — Faustian Bargain**: Passive. FL: When Asha swaps to frontline, spend 2 Malice to gain the most recently "bottled" talent for 2 rounds. BL: When Asha KO's an enemy, bottle their talent and gain +10 Speed (2r).
- **Twist — Turn to Foam**: Asha gains 3 Malice, then consumes ALL Malice to give all enemies -10 Defense per Malice consumed (2r, single stacking debuff).

---

## NPC Enemies

The campaign features AI-controlled enemy teams. Some NPCs have unique mechanics:

**Apex Warden NPC**: Reduces all damage dealt to frontline units (other than itself) by 10 while alive.

**Dragon Heads (Noble, Mage, Warlock variants)**: Share a "Tyranny" passive — if the target has 2 or more active status conditions, their abilities deal +5 additional damage.

**Cataclysm (special NPC ability)**: FL: +10 power per active status on the target.

*(Additional NPC archetypes can be defined in data.py using the same AdventurerDef/Ability system as player characters.)*

---

## Campaign System

The campaign is a single-player mode with persistent progression via `CampaignProfile`.

### Profile Fields

| Field | Type | Description |
|-------|------|-------------|
| `recruited` | set of str | Adventurer IDs the player has unlocked |
| `sig_tier` | dict[str, int] | Signature tier unlocked per adventurer (0–3) |
| `twists_unlocked` | bool | Whether twist abilities are globally unlocked |
| `unlocked_classes` | set of str | Basic ability class pools unlocked |
| `basics_tier` | dict[str, int] | Which basics tier is available per class |
| `unlocked_items` | set of str | Item IDs the player has unlocked |
| `campaign_stage` | int | Current stage in the campaign sequence |
| `story_flags` | dict | Arbitrary flags for story progression |

### Progression

1. Campaign consists of a series of battles against predefined enemy rosters.
2. After winning a battle, the player receives rewards: new adventurer recruits, higher signature tiers, twist unlock, new basic class pools, and/or items.
3. The team builder restricts options to only unlocked content.
4. The Catalog screen lets players browse all currently unlocked adventurers, basics, and items with full ability detail.

### Team Building (Campaign)

- Player picks up to 3 adventurers from `recruited` set.
- Player picks a signature for each (up to their `sig_tier` unlock).
- Player picks 2 basics per adventurer (from their unlocked class pools).
- Player picks an item per adventurer (from `unlocked_items`).
- If `twists_unlocked`, twist ability is available in battle.

---

## AI System

The AI (`ai.py`) controls enemy teams in campaign mode.

### Entry Point
`pick_action(battle, player_num, actor, is_extra, swap_used, swap_queued) → action_dict`

### State Evaluation
`evaluate_state(battle, for_player) → float`

Signed score (positive = good for `for_player`). Components:
1. Own team HP ratio vs enemy team HP ratio
2. KO count delta (bonus for each enemy KO'd)
3. Frontliner durability ratio
4. Buff duration advantage (own buffs - enemy buffs)
5. Debuff duration placed on enemies
6. Dangerous status penalty (enemy Burn/Shock ticking)
7. Harmful status penalty (own team statuses)
8. Item preservation (having usable items)
9. Recharge penalty (own abilities on cooldown)
10. Backline safety (own backline HP)

### Simulation
For each candidate action (up to `MAX_SIMULATED_CANDIDATES = 30`):
1. Deep-copy the battle state.
2. Suppress the battle log during simulation.
3. Execute the action via `resolve_queued_action()`.
4. Score the resulting state with `evaluate_state()`.
5. Add heuristic bonuses on top.

If candidates exceed 30, simulation is skipped and only heuristic scoring is used.

### Heuristic Bonuses
- **Initiative bonus**: Prefer actions that increase speed when behind on initiative.
- **Recharge bonus**: Prefer actions that don't incur recharge penalties.
- **Character hooks**: Per-character tuning:
  - **Ashen Ella**: +500 bonus for swap to frontline when backline (Two Lives setup).
  - **Rumpelstiltskin**: Bonus for frontline attacks when buffs are active (Spinning Wheel value).
  - **Robin**: +10 preference for backline targets (Keen Eye synergy).
  - **Gretel**: +30 for twist use when available.

---

## LAN Multiplayer

LAN mode uses a host/client architecture over a local network socket.

- **Host**: Runs the authoritative game simulation. Makes all mechanical decisions. Sends serialized state to the client after each phase transition.
- **Client**: Receives state, displays it, and sends back action selections (which unit acts, what action is taken).
- **State sync**: The full `BattleState` (serialized) is sent at each phase boundary: initiative result, after each player's action selection, after each resolution step, and at round end.
- **Client UI**: The client sees the same formation/log view but the "Continue →" button is replaced with "Waiting for host..." during phases where the host is acting.

**Phase transitions sent over LAN:**
- `initiative_result`
- `action_select_p{n}` (host triggers client's selection turn)
- `resolving` / `resolve_done` / `action_result`
- `end_of_round`
- `battle_over`

---

## Summary: What Does and Doesn't Exist Yet

### Fully Implemented
- All 24 adventurers with stats, talents, signatures, and twists
- All 8 class basic ability pools (5 basics each)
- All 16 items
- Full damage formula with all bonus conditions
- All status conditions and their effects
- Stat buff/debuff system
- Guard and redirect
- Healing with all modifiers
- Lifesteal
- Malice resource
- Swap mechanic with restrictions
- Recharge mechanic
- Initiative determination
- End-of-round effects (Burn, Shock, Sanctuary, buff ticking, etc.)
- Round-start effects (Curse of Sleeping)
- On-KO effects (Sugar Rush, Postmortem Passage, Flame of Renewal)
- On-hit effects (Spiked Mail, Reflecting Pool, Garden of Thorns, Nine Lives, etc.)
- Campaign profile with unlock gating
- Catalog screen (adventurers, basics, items with unlock filtering)
- AI with state evaluation and 1-ply simulation
- LAN multiplayer (host/client)

### Areas with Room for Future Features
- **More campaign stages and story content**: Only the framework exists; stage data and narrative are expandable.
- **More NPC enemy archetypes**: Current NPC pool (Apex Warden, Dragon variants) is small.
- **Sound/music**: No audio system described in the codebase.
- **Animations**: No animation system; all rendering is static frame-based.
- **Save/load mid-battle**: Campaign profile saves between battles, but there's no in-battle save.
- **Achievement or meta-progression**: No achievement system beyond campaign unlocks.
- **Spectator mode for LAN**: Not implemented.
- **Turn timer**: No time limit on action selection.
- **Difficulty settings**: AI difficulty is fixed.
- **Tutorial / onboarding**: No in-game tutorial.
- **More items**: Item pool (16 total) could grow.
- **Equipment upgrades**: Items cannot be upgraded or modified.
- **More Warlocks / more classes**: 8 classes × 3 adventurers is the current structure; adding a 9th class or 4th adventurer per class is architecturally straightforward.
