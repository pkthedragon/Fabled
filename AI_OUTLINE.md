# Fabled AI Outline

## Purpose

This document defines the target AI architecture for the current offline Quests and Bouts ruleset.

It is written for the live `quests_ruleset_*`, `quests_sandbox.py`, `storybook_mode.py`, and `storybook_battle.py` stack.

It is not a continuation of the legacy `ai.py` planner that targets `logic.py`. That file should be treated as old-system AI and left isolated unless the old battle system is intentionally revived.

The new AI must solve three different problems:

1. Quest party creation from 6 adventurers.
2. Bout drafting from a shared pool of 9 adventurers.
3. Round-by-round battle execution for the new action phase and bonus action phase combat model.


## Product Rules The AI Must Respect

- Quests are `show 6, pick 3`.
- Quest runs continue until the player loses 3 battles in a row.
- Bouts are a shared pool of 9 adventurers with alternating picks until each side has 3.
- The side that picked second receives a first-round bonus swap advantage.
- Battles are 3v3 with exactly 1 frontline and up to 2 backline units.
- Backline units take a `-30 Speed` penalty.
- Backline-left matters because it becomes the replacement frontline on frontline KO.
- Every adventurer can take 1 normal action each round.
- Every adventurer can take at most 1 bonus action in the proper bonus phase if they have one.
- Legal action families are `Strike`, `Spellcast`, `Switch`, `Swap`, and `Skip`.
- Primary weapon determines active weapon spells and passives.
- Switching swaps primary and secondary weapon, clears relevant cooldowns, and reloads ranged ammo.
- Artifacts must be legal by attunement and unique within a team.


## Design Goals

- Build coherent teams instead of chasing raw stats.
- Prefer reliable plans over fragile combo lines unless the ceiling gap is large.
- Draft and load out with formation in mind, not as an afterthought.
- React to enemy information in Bouts.
- Pilot battles like a competent human who values pressure, survival, setup, and clean conversions.
- Keep some bounded randomness so the AI is not solved.


## Recommended Module Layout

The cleanest implementation is a new parallel AI stack instead of extending legacy `ai.py`.

- `quests_ai_tags.py`
  Stores authored tactical tags, reliability scores, matchup tags, and archetype metadata for adventurers, weapons, class skills, and artifacts.
- `quests_ai_tables.py`
  Stores pair synergy, three-unit archetype bonuses, counter tables, and difficulty tuning weights.
- `quests_ai_loadout.py`
  Generates legal loadouts, solves artifact uniqueness, scores full-team loadout sets, and assigns starting positions.
- `quests_ai_quest.py`
  Evaluates all 20 teams from a pool of 6 and chooses one with slight top-band randomness.
- `quests_ai_bout.py`
  Performs dynamic adversarial drafting from a shared pool of 9 and then solves both final loadouts.
- `quests_ai_battle.py`
  Chooses queued actions and queued bonus actions for the new battle engine.
- `quests_ai_runtime.py`
  Thin integration helpers for `storybook_mode.py`, `quests_sandbox.py`, and later menu automation.
- `tests/test_quests_ai_*.py`
  Focused tests for draft scoring, loadout legality, formation logic, and battle decision quality.


## Runtime Integration Points

These are the live code seams the AI should plug into.

- `quests_sandbox.py`
  Use `create_setup_state`, `assign_offer_to_team`, `cycle_member_*`, and `build_battle_from_setup` patterns as the source of truth for legal team construction.
- `storybook_mode.py`
  Add AI-driven flows for Quest auto-party creation, Bout AI drafting, and optional one-side or two-side AI battles.
- `storybook_battle.py`
  Feed AI-chosen queued actions and queued bonus actions into the same action queue system the human UI already uses.
- `quests_ruleset_models.py`
  Read immutable content and live combat state from `AdventurerDef`, `WeaponDef`, `ArtifactDef`, `CombatantState`, `TeamState`, and `BattleState`.
- `quests_ruleset_logic.py`
  Use legal target helpers, queue helpers, phase resolution helpers, cooldown state, ammo state, and status state instead of recreating battle rules inside the AI.


## Data Representation Requirements

The AI needs authored metadata in addition to the mechanical definitions already in `quests_ruleset_data.py`.

### Adventurer metadata

Each adventurer should have:

- `name`
- `base_stats`
- `innate`
- `weapon_ids`
- `ultimate_id`
- `legal_class_names`
- `legal_class_skill_ids`
- `legal_artifact_ids_by_class`
- `action_tags`
- `tactical_tags`
- `matchup_tags`
- `synergy_tags`
- `reliability_rating`
- `complexity_rating`
- `preferred_frontline_score`
- `preferred_backline_left_score`
- `preferred_backline_right_score`

### Weapon metadata

Each weapon should have:

- `kind`
- `power_profile`
- `cooldown_or_ammo_profile`
- `targeting_profile`
- `status_application_tags`
- `status_payoff_tags`
- `survival_tags`
- `tempo_tags`
- `burst_tags`
- `swap_tags`
- `support_tags`
- `frontline_fit`
- `backline_fit`
- `turn1_reliability`

### Artifact metadata

Each artifact should have:

- `attunement_classes`
- `stat_bonus`
- `spell_or_reaction_type`
- `cooldown`
- `tactical_tags`
- `patch_tags`
- `counter_tags`
- `reliability_score`

### Class skill metadata

Each class skill should have:

- `effect_category`
- `ideal_user_tags`
- `synergy_tags`
- `conflict_tags`
- `frontline_fit`
- `backline_fit`
- `matchup_tags`


## Required Tactical Tags

Use hand-authored tags. They are the foundation of the entire evaluation system.

### Offensive tags

- `frontline_breaker`
- `backline_reach`
- `spread_pressure`
- `burst_finisher`
- `chip_damage`
- `status_applier`
- `status_payoff`
- `anti_guard`
- `anti_heal`
- `stat_manipulator`

### Defensive tags

- `primary_tank`
- `off_tank`
- `healer`
- `guard_support`
- `cleanse`
- `damage_reduction`
- `anti_burst`
- `death_insurance`

### Tempo and utility tags

- `swap_engine`
- `bonus_action_user`
- `weapon_switch_user`
- `initiative_control`
- `action_denial`
- `targeting_manipulation`
- `taunt`
- `spotlight_enabler`
- `root_lockdown`

### Reliability tags

- `self_sufficient`
- `synergy_dependent`
- `fragile`
- `high_variance`
- `positioning_sensitive`
- `cooldown_sensitive`
- `ammo_sensitive`


## Global Evaluation Model

Use weighted scoring rather than fixed tier picks.

### Team score formula

For every candidate team:

`TeamScore = BasePower + Synergy + Coverage + LoadoutFit + Reliability + MatchupAdjustment`

### BasePower

Measures each unit in a vacuum.

Inputs:

- stat efficiency
- breadth of legal actions
- turn-1 pressure
- survivability
- current ruleset reliability

### Synergy

Measures how well units enable one another.

Inputs:

- pair synergy table
- three-unit shell bonuses
- setup and payoff alignment
- shared tempo plan
- protection for fragile carries

### Coverage

Measures whether the team can answer common board states.

Inputs:

- stable frontline
- backline threat access
- sustain or mitigation
- control or disruption
- anti-guard or targeting bypass
- recovery after a KO

### LoadoutFit

Measures how good the actual full build is after solving:

- primary weapons
- classes
- class skills
- artifacts
- positions

### Reliability

Rewards lineups that:

- work on round 1
- do not demand exact cooldown alignment
- do not crumble to one early death
- do not starve on ammo or cooldowns

### MatchupAdjustment

Primarily for Bouts.

Inputs:

- visible enemy draft
- counter tags
- denial value
- whether AI picked first or second


## Precomputation Layer

The new AI should do as much authored and derived setup as possible before runtime.

Precompute:

- adventurer tactical tags
- weapon tactical tags
- class skill fit profiles
- artifact tactical tags
- pair synergy matrix
- three-unit archetype bonuses
- counter matrix
- reliability scores
- complexity scores
- starting position priors

This keeps runtime logic simple and inspectable.


## Quest AI Outline

Quest AI sees 6 unique adventurers and picks the best 3.

### Candidate generation

- Enumerate all 20 possible 3-unit teams from the offered 6.
- For each team, generate all legal full-team loadout combinations.
- For each loadout set, assign best starting formation.
- Score the highest-value loadout for that team.
- Pick from the top score band using difficulty-based randomness.

### Mandatory team checks

Every candidate team should be checked for:

- `frontline_viability`
- `backline_reach`
- `sustain_or_mitigation`
- `clear_win_condition`
- `fallback_after_frontline_ko`

Apply heavy penalties for:

- no plausible frontline
- no backline pressure
- triple-fragile shells
- all setup and no payoff
- severe ammo or cooldown starvation
- teams that only function after multiple perfect turns

### Quest-specific valuation bias

Because Quests continue until 3 consecutive losses, value consistency over volatility.

Increase weight for:

- sustain
- anti-burst
- durable anchors
- low-risk synergy
- simple win conditions
- artifact efficiency

Decrease weight for:

- glass-cannon trios
- narrow combo stacks
- one-opener dependency
- shells that need multiple cooldowns to align before contributing

### Quest archetype bonuses

Reward known shells such as:

- `shock`
- `root_control`
- `expose_burst`
- `burn_attrition`
- `swap_protection`
- `durable_tempo`

The archetype table should be authored, not inferred on the fly.


## Bout AI Outline

Bout AI drafts from a shared pool of 9 against a visible opponent.

### Per-pick score formula

At each pick:

`DraftScore = SelfValue + PairValue + DenialValue + FlexValue + LoadoutValue + SeatAdjustment + CounterValue`

### SelfValue

How good the unit is in a vacuum.

### PairValue

How well the unit pairs with already drafted AI units.

### DenialValue

How much the pick removes a high-value completion piece from the player.

### FlexValue

How many coherent final teams remain open after making the pick.

### LoadoutValue

How easy it will be to equip the final team without artifact conflicts or dead class assignments.

### SeatAdjustment

Adjusts for pick order.

- First picker prefers stronger flexible anchors.
- Second picker can value aggressive or position-sensitive teams a bit higher because of the round-1 bonus swap advantage.

### CounterValue

Uses visible enemy picks to raise units that are good into:

- tanks
- fragile backline
- spell-heavy drafts
- swap-heavy drafts
- status-heavy drafts
- heal-heavy drafts
- guard-heavy drafts

### Denial draft rules

Denial should happen only when:

- the player already shows a visible shell,
- the available unit is a major multiplier for that shell,
- and taking that unit does not damage the AI's own team coherence too badly.

### Bout runtime policy

At each draft pick:

1. Evaluate every legal pick.
2. Simulate the best few likely completion paths for both sides.
3. Apply self-value, synergy, denial, flexibility, and counter weights.
4. Choose within the difficulty-based top band.


## Loadout Construction Outline

Loadouts must be solved at team level, not one unit at a time.

### Inputs

- 3 chosen adventurers
- all legal class assignments
- all legal class skills
- both weapon primary choices
- all legal artifacts

### Search process

1. Generate each adventurer's legal build options.
2. Remove illegal artifact duplicates.
3. Remove obviously bad builds with authored pruning rules.
4. Score every remaining full-team combination.
5. Pick the best combination, with slight near-equal randomness if desired.

### Full loadout score

`LoadoutScore = WeaponFit + SkillFit + ArtifactFit + FormationFit + TeamNeedCoverage`

### WeaponFit rules

Favor primaries that:

- serve the team's main plan,
- are strong from the starting position,
- are reliable on round 1,
- create pressure without requiring an early switch,
- or provide the most valuable passive utility.

Favor secondaries that:

- are situational answers,
- are best after switch reset,
- or are recovery plans after repositioning.

### SkillFit rules

Choose class skills based on kit interaction.

Examples:

- `Bulwark` for default frontline wardens.
- `Vigilant` for swap-heavy defensive teams.
- `Martial` for direct melee pressure.
- `Vanguard` for melee backline pressure or aggressive follow-up plans.
- `Overflow` for frontline magic attackers.
- `Archmage` for switch-loop or spell-tempo plans.
- `Deadeye` for dependable ranged pressure.
- `Tactical` for switch-reliant rangers.
- `Healer` for raw sustain.
- `Medic` for status-heavy matchups.
- `Protector` when the whole shell gains value from extra team defense.

### ArtifactFit rules

Assign artifacts in this priority order:

1. Team-defining artifact.
2. Weakness patch artifact.
3. Personal optimization artifact.

Examples:

- If the team lacks sustain, raise `Holy Grail`, `Fading Diadem`, or `Iron Rosary`.
- If the team lacks anti-burst, raise `Selkie's Skin`, `Nettle Smock`, or `Enchanted Lamp`.
- If the team lacks setup, raise `Cursed Spindle` or `Lightning Helm`.
- If the team lacks reach, raise `Soaring Crown`, `Dragon's Horn`, or `Glass Slipper`.
- If the team wants stronger ultimate leverage, raise `Goose Quill`.
- If the matchup is guard-heavy, raise `Bluebeard's Key`.


## Adventurer-Specific AI Profiles

These authored profiles should live in `quests_ai_tags.py` or `quests_ai_tables.py`.

They are not hard locks. They are weighted defaults that the solver can override when formation, matchup, or artifact constraints demand it.

### Red Blanchette

- Role tags: `burst_finisher`, `status_payoff`, `hp_manipulation`, `snowball`, `positioning_sensitive`
- Draft rises when the team can expose, lock, or protect her until bloodied mode matters.
- Prefer `Stomach Splitter` when the team wants mark punishment and safer magic access.
- Prefer `Enchanted Shackles` when the team wants direct frontline burst and HP averaging tricks.
- Lean toward offensive class skills that improve burst tempo.
- Lean toward attack artifacts when protected, or defensive artifacts when the bloodied threshold is central.

### Little Jack

- Role tags: `frontline_breaker`, `burst_finisher`, `anti_tank`, `self_sufficient`
- Draft rises sharply into high-HP frontline teams and with expose or spotlight support.
- Prefer `Skyfall` by default.
- Prefer `Giant's Harp` when defense ignore and safer lane pressure matter more than raw melee burst.
- Lean toward `Martial` or `Vanguard`, with `Inevitable` acceptable in strike-heavy shells.
- Raise `Naiad's Knife`, `Dragon's Horn`, `Dire-Wolf Spine`, and `Red Hood`.

### Witch-Hunter Gretel

- Role tags: `status_applier`, `burn_attrition`, `snowball`, `anti_heal`, `swap_sensitive`
- Draft rises with Liesl, Ella, attrition shells, and teams that can collect crumbs.
- Prefer `Hot Mitts` for direct burn payoff and frontline pressure.
- Prefer `Crumb Shot` when safe ranged utility and team sustain matter more.
- Lean toward simple damage-boosting class skills over conditional gimmicks.
- Raise `Cursed Spindle`, `Black Torch`, `Red Hood`, or a sustain patch artifact on fragile teams.

### Lucky Constantine

- Role tags: `status_applier`, `burst_enabler`, `swap_engine`, `fragile`, `backline_reach`
- Draft rises with Jack, Red, Roland, Robin, and any expose burst shell.
- Prefer `Fortuna` by default for disruption and expose support.
- Prefer `Cat'O'Nine` only when repeated-hit utility or exposed-target payoff is especially valuable.
- Lean toward `Covert` or `Assassin`, with `Fleetfooted` as the safer fallback.
- Raise `Glass Slipper`, `Naiad's Knife`, `Enchanted Lamp`, and `Selkie's Skin`.

### Hunold the Piper

- Role tags: `shock_engine`, `status_payoff`, `control_setup`, `tempo_anchor`, `backline_reach`
- Draft is one of the strongest flexible starts and rises with March Hare, Briar, and melee punishers.
- Prefer `Lightning Rod` when starting the shock engine matters most.
- Prefer `Golden Fiddle` when shocked targets are already likely or immediate payoff is available.
- Lean toward the class skill that strengthens the weapon expected to open combat most often.
- Raise `Lightning Helm`, `Cursed Spindle`, `Bottled Clouds`, and `Soaring Crown`.

### Sir Roland

- Role tags: `primary_tank`, `guard_support`, `taunt`, `status_applier`, `swap_protection`
- Draft is elite in almost every shell and should be one of the safest anchor profiles.
- Prefer `Pure Silver Shield` in most default and defensive shells.
- Prefer `Pure Gold Lance` when paired with burst partners that want expose support.
- Lean toward `Bulwark` by default, `Vigilant` in swap shells, and `Stalwart` into displacement pressure.
- Raise `Holy Grail`, `Golden Fleece`, `Sun-God's Banner`, `Nettle Smock`, and `Bluebeard's Key` into guard mirrors.

### Porcus III

- Role tags: `primary_tank`, `anti_burst`, `stall_anchor`, `status_applier`, `frontline_only`
- Draft rises if the team has fragile carries or badly needs a pure tank.
- Prefer `Crafty Wall` by default.
- Prefer `Mortar Mortar` when ranged weaken cycling and Bricklayer ammo value matter.
- Lean toward `Bulwark`, with `Vigilant` in swap-heavy defensive teams.
- Raise `Sun-God's Banner`, `Holy Grail`, `Golden Fleece`, and `Nettle Smock`.

### Lady of Reflections

- Role tags: `swap_engine`, `anti_burst`, `death_insurance`, `positioning_manipulation`, `tempo_support`
- Draft rises with fragile carries and teams that want repeated swap value.
- Prefer `Lantern of Avalon` in mobility-heavy and position-focused teams.
- Prefer `Excalibur` when direct frontline pressure is more important than swap cycling.
- Lean toward mobility and stability class skills over pure greed.
- Raise `Glass Slipper`, `Winged Sandals`, `Holy Grail`, and defensive reaction artifacts.

### Ashen Ella

- Role tags: `spread_pressure`, `burn_attrition`, `fragile`, `positioning_sensitive`, `magic_carry`
- Draft rises with Liesl, Gretel, and teams that can shield her while spread burn works.
- Weapon choice is position-driven, so the formation solver matters more than the weapon solver.
- Lean heavily toward repeated frontline magic pressure if the class mapping allows it.
- Raise `Last Prism`, `Cursed Spindle`, `Magic Mirror`, and `Arcane Hourglass` when survival is needed.

### March Hare

- Role tags: `shock_support`, `tempo_engine`, `bonus_action_user`, `action_economy`, `spell_loop`
- Draft is one of the best synergy anchors in the pool and rises with Hunold and spell-heavy teams.
- Prefer `Stitch in Time` for default combat pressure and shock setup.
- Prefer `Cracked Stopwatch` when the team is deliberately chasing Rabbit Hole loops and repeated spells.
- Lean toward `Overflow` or `Archmage`, with `Arcane` as the consistent fallback.
- Raise `Arcane Hourglass`, `Last Prism`, `Glass Slipper`, and `Goose Quill`.

### Briar Rose

- Role tags: `root_lockdown`, `spread_pressure`, `status_applier`, `anti_swap`, `control_anchor`
- Draft rises sharply with Rapunzel, Robin, and teams that can punish rooted enemies.
- Prefer `Thorn Snare` when broad setup is more important than direct damage.
- Prefer `Spindle Bow` when root payoff already exists on the team.
- Lean toward `Deadeye` by default, with `Tactical` or `Armed` when the shell depends on better ammo or switch flow.
- Raise `Soaring Crown`, `Cursed Spindle`, `Dragon's Horn`, and `Bottled Clouds`.

### Wayward Humbert

- Role tags: `weapon_switch_user`, `ranged_pressure`, `high_variance`, `self_sustain`, `tempo_damage`
- Draft rises in teams that can exploit frequent switching and protect him through recoil turns.
- Prefer `Pallid Musket` for safer starts and reliable repair access.
- Prefer `Convicted Shotgun` for immediate aggression and snowball attempts.
- Lean strongly toward `Tactical`, with `Armed` as the next best consistency option.
- Raise `Soaring Crown`, `Dragon's Horn`, `Selkie's Skin`, and `Red Hood`.

### Robin, Hooded Avenger

- Role tags: `spread_pressure`, `spotlight_enabler`, `anti_guard`, `backline_reach`, `flex_anchor`
- Draft is one of the strongest flexible damage-control picks and rises with Briar, Rapunzel, and melee punishers.
- Prefer `The Flock` by default.
- Prefer `Kingmaker` when the shell already has reliable spotlight or backline access support.
- Lean toward `Deadeye`, with `Tactical` or `Armed` in switch-heavy or ammo-sensitive lines.
- Raise `Soaring Crown`, `Dragon's Horn`, `Bottled Clouds`, and `Red Hood`.

### Matchbox Liesl

- Role tags: `healer`, `burn_support`, `anti_burst`, `death_insurance`, `attrition_support`
- Draft is a very high-value support profile and rises sharply with Gretel, Ella, and slow durable teams.
- Prefer `Matchsticks` for burn-engine teams.
- Prefer `Eternal Torch` when sustain and safer lifesteal pressure matter more.
- Lean toward `Healer` or `Medic`, with `Protector` in bulk-oriented shells.
- Raise `Iron Rosary`, `Fading Diadem`, `Holy Grail`, and `Cursed Spindle`.

### The Good Beast

- Role tags: `primary_tank`, `protector`, `healer`, `carry_support`, `stat_sharing`
- Draft rises whenever the team already has one clear carry worth protecting.
- Prefer `Dinner Bell` in most support and sustain shells.
- Prefer `Rosebush Sword` when punish damage matters more than direct protection.
- Lean toward `Protector` or `Healer`, with `Bulwark` in pure anchor shells.
- Raise `Holy Grail`, `Golden Fleece`, `Fading Diadem`, and `Iron Rosary`.

### The Green Knight

- Role tags: `swap_engine`, `duel_control`, `frontline_pivot`, `bonus_action_user`, `flex_tank`
- Draft rises in position-heavy teams and into enemy compositions that hinge on one important lane.
- Prefer `The Answer` when the team wants a true duel frontline.
- Prefer `The Search` for safer ranged starts or mixed-position plans.
- Lean toward `Vanguard`, `Bulwark`, or `Vigilant` depending on whether the shell is aggressive, defensive, or swap-heavy.
- Raise `Winged Sandals`, `Dragon's Horn`, `Sun-God's Banner`, and `Nettle Smock`.

### Rapunzel the Golden

- Role tags: `root_lockdown`, `healer`, `melee_reach`, `bruiser`, `control_support`
- Draft rises with Briar, Robin, and teams that need sustain plus disruption.
- Prefer `Golden Snare` for root and control shells.
- Prefer `Ivory Tower` when sustain and soften effects are more important than raw lockdown.
- Lean toward `Martial` or `Vanguard` in aggressive lines, and `Bulwark` in stabilizing lines.
- Raise `Holy Grail`, `Winged Sandals`, `Bluebeard's Key`, and `Golden Fleece`.

### Pinocchio, Cursed Puppet

- Role tags: `scaling_carry`, `self_ramp`, `fragile`, `frontline_growth`, `status_resistant_late`
- Draft rises if the team can buy time and protect him through early rounds.
- Prefer `String Cutter` for the safer default line.
- Prefer `Wooden Club` when the team can frontline him aggressively and accelerate Malice.
- Lean toward scaling-friendly class skills that reward repeated action access.
- Raise `Last Prism`, `Selkie's Skin`, `Enchanted Lamp`, and `Nettle Smock` for melee lines.

### Rumpelstiltskin

- Role tags: `stat_manipulator`, `burst_spellcaster`, `synergy_amplifier`, `tempo_trickster`, `setup_dependent`
- Draft rises with teams that already provide safety plus buffs or debuffs worth copying.
- Prefer `Devil's Contract` when burst and pressure matter most.
- Prefer `Spinning Wheel` when the team wants a longer stat-penalty plan.
- Lean toward the skill that most improves the expected primary weapon line.
- Raise `Goose Quill`, `Cursed Spindle`, `Last Prism`, and `Bottled Clouds`.

### Sea Wench Asha

- Role tags: `anti_caster`, `spell_theft`, `adaptive_damage`, `volatile_utility`, `matchup_dependent`
- Draft rises against spell-heavy pools and against visible enemy spell anchors in Bouts.
- Prefer `Frost Scepter` by default.
- Prefer `Mirror Blade` when copied strike value is unusually high in the current lobby.
- Lean toward immediate magic-pressure class skills.
- Raise `Magic Mirror`, `Last Prism`, `Arcane Hourglass`, and `Goose Quill`.


## Synergy And Conflict Tables

The AI should ship with authored pair and shell data instead of trusting generic tags alone.

### Strong positive pairs

- `Hunold + March Hare`
- `Briar + Rapunzel`
- `Briar + Robin`
- `Roland + Jack`
- `Roland + Constantine`
- `Liesl + Gretel`
- `Liesl + Ella`
- `Good Beast + primary carry`
- `Lady of Reflections + swap-sensitive allies`
- `Robin + melee backline punisher`

### Three-unit shell examples

- `Hunold + March Hare + control third`
- `Briar + Rapunzel + Robin`
- `Roland + Jack + burst support`
- `Liesl + Gretel + Ella`
- `Roland or Porcus + carry + support healer`
- `Lady or Green Knight + carry + swap-value support`

### Common negative patterns

- triple-fragile setup shells
- multiple units that all need frontline at once
- multiple units that all want the same artifact archetype to function
- low-healing and low-mitigation shells with no speed control
- too many payoff units and not enough setup


## Starting Position Logic

Formation is part of the build solver.

### Frontline selection

Frontline starters should score highly if they offer:

- durability
- melee dependence
- frontline-only value
- taunt or guard utility
- strong retaliation or punish mechanics

### Backline-left selection

Backline-left is the emergency replacement frontline.

Prefer:

- off-tanks
- bruisers
- melee pivots
- units that can still function after being forced forward

### Backline-right selection

Prefer:

- fragile carries
- specialist backliners
- units that hate being promoted to frontline

The position solver should explicitly optimize for frontline KO recovery, not just the opening formation.


## Battle AI Outline

The battle AI should operate on the current queued-phase combat model rather than one action at a time.

### Per-round flow

For each round:

1. Read phase state from `BattleState`.
2. Generate legal normal actions for each living unit.
3. Score action sets in the context of initiative order and likely enemy responses.
4. Queue one action per unit.
5. Re-evaluate after action resolution.
6. Generate legal bonus actions for eligible units.
7. Score bonus actions separately.
8. Queue one bonus action per eligible unit.

### Action generation

For each actor, generate all legal instances of:

- `Strike`
- `Spellcast`
- `Ultimate`
- `Switch`
- `Swap`
- `Skip`

Then prune dominated actions.

Examples of pruning:

- never cast a self-only spell on cooldown,
- never swap into an invalid or obviously worse duplicate state,
- do not switch if the current primary already has the preferred immediate line and the swap gives no turn value,
- do not spend ultimate if it loses lethal or protection timing for no gain.

### Action score components

Each candidate action should be scored on:

- expected damage
- lethal chance
- survival gained
- ally survival gained
- setup value
- deny value
- formation improvement
- ultimate meter gain or spend value
- cooldown efficiency
- ammo efficiency
- future board quality

### Team action-set selection

Because actions resolve in initiative order, the AI should score sets of queued actions, not isolated choices only.

Recommended approach:

- generate each unit's top local actions,
- build a capped beam of team action sets,
- simulate or estimate the initiative-ordered outcome of those sets,
- keep the best few candidates,
- queue the highest scoring set.

This is strong enough without requiring exhaustive search.

### Bonus action phase

Treat bonus actions as a second optimization pass.

The AI should only use a bonus action when it creates value.

Examples:

- `Covert` swap to save a fragile ally or reposition a carry,
- `Tactical` or Humbert bonus switch to reload or reset for the next round,
- `Vanguard` only when the primed next strike meaningfully improves reach or conversion,
- bonus spell lines from March Hare only when the spell meaningfully advances kill, protection, or tempo.

### Tactical priorities during battle

The battle planner should balance:

- immediate lethal
- protection against enemy lethal
- win condition setup
- backline access creation
- control denial
- action economy abuse
- ultimate timing

Default priority ordering should be:

1. Secure lethal if safe and high-confidence.
2. Prevent enemy lethal if possible.
3. Advance the team's main shell.
4. Improve formation and targeting.
5. Farm efficient meter only when stronger lines are absent.


## Recommended Evaluation Heuristics

The battle AI should understand these board questions every round:

- Which side has lethal pressure this round?
- Which unit is most likely to become the next frontline after a KO?
- Which enemy is the best focus target given targeting rules?
- Does a swap improve access or expose a fragile ally?
- Is switching worth the reset and ammo reload right now?
- Is the ultimate better used now, held for lethal, or held for protection?
- Will acting earlier or later in initiative change the value of setup actions?


## Difficulty Knobs

Difficulty should change evaluation quality, not cheat values.

### Easy

- weaker synergy weighting
- less denial drafting
- shallow lookahead
- weaker formation planning
- weaker loadout solving

### Normal

- good pair synergy
- basic denial drafting
- competent frontline and artifact logic
- basic initiative-aware action planning

### Hard

- strong shell planning
- matchup-aware drafting
- coordinated artifact solving
- good starting position logic
- better action-set search

### Ranked AI

- full synergy and counter tables
- strong denial logic
- long-term quest consistency weighting
- strong ultimate timing
- tighter action-set search and bonus-action planning


## Randomness Rules

The AI should remain slightly unpredictable.

### Draft randomness

- Easy chooses among the top 5 within a small score band.
- Normal chooses among the top 3.
- Hard chooses among the top 2.
- Ranked chooses top 1 most of the time, with rare top 2 variation.

### Loadout randomness

Only randomize among near-equal loadouts.

Never randomize into:

- illegal artifacts
- duplicate team artifacts
- nonfunctional frontline setups
- clearly weaker class skill choices

### Battle randomness

Only randomize among materially similar action sets.

Do not randomize away:

- obvious lethal
- obvious survival saves
- clearly superior formation recovery


## Minimum Correctness Requirements

The new AI is not acceptable unless it does all of the following:

- never builds a team with no plausible frontline unless forced by the offer or pool,
- never assigns illegal class or artifact combinations,
- never duplicates an artifact on one team,
- assigns backline-left intentionally as the fallback frontline,
- recognizes major shells such as shock, root, burn, expose, and swap-protection,
- drafts reactively in Bouts instead of using static tiers,
- values consistency more heavily in Quests than in Bouts,
- accounts for the second-picker round-1 bonus swap in Bouts,
- chooses primaries based on plan and position instead of raw power alone,
- uses the actual legal target system and phase structure during battle planning.


## Testing Plan

The AI should ship with focused automated tests.

### Draft tests

- Quest AI prefers coherent 3-unit shells over disconnected stat bundles.
- Bout AI denial drafts only when denial does not destroy its own team quality.
- Second-pick Bout AI values early swap-sensitive shells more than first-pick AI.

### Loadout tests

- No duplicate artifacts on a team.
- No illegal attunement assignments.
- Frontline is always populated.
- Backline-left is used as the better fallback frontline.

### Battle tests

- AI respects legal targeting.
- AI uses bonus actions only in the bonus phase.
- AI recognizes lethal.
- AI protects against obvious enemy lethal when a reasonable save exists.
- AI does not waste switch or ultimate in obviously losing lines when a better line exists.

### Regression suites

- Quest run simulation across many random seeds.
- Bout draft simulation across many random pools and seat orders.
- Battle autoplay stress tests with no illegal queues or dead states.


## Implementation Phases

### Phase 1

Build authored metadata:

- tags
- synergy table
- counter table
- reliability and complexity scores

### Phase 2

Build loadout solver:

- legal class choices
- legal class skill choices
- legal artifact assignment
- position assignment
- team scoring

### Phase 3

Build Quest AI:

- team enumeration from 6
- best-loadout search
- top-band randomized selection

### Phase 4

Build Bout AI:

- per-pick evaluation
- denial and counter logic
- completion-shell lookahead
- final loadout solve

### Phase 5

Build battle AI:

- normal action generation
- action-set beam search
- bonus action planner
- ultimate timing layer

### Phase 6

Integrate into UI/runtime:

- AI Quest runs
- AI Bout opponent
- optional AI-vs-AI testing hooks


## Best Practical Implementation Pattern

The recommended final approach is:

- hand-authored tags,
- weighted scoring,
- pairwise synergy matrix,
- small draft lookahead,
- constrained legal loadout combinatorics,
- position-aware evaluation,
- initiative-aware battle planning.

That is strong enough to feel intentional and skillful without requiring a brittle full search engine.
