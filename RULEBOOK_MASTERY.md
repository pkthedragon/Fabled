# Fabled Rulebook Mastery Reference

This document is a complete, accurate reference derived from the official Fabled rulebook.

## Core Win Condition and Match Loop
- Build a party of 3 adventurers.
- Battle ends immediately when one side has all 3 adventurers knocked out.
- Rounds contain both players' turns, then end-of-round effects resolve after the second player's actions finish resolving.
- Initiative each round is determined by frontline Speed; round-1 loser gets a one-time extra swap phase before selecting actions.

## Formation, Position, and Turn Resolution
- Triangle layout: 1 frontline, up to 2 backline.
- If frontline is KO'd, leftmost backline moves forward.
- During a turn, each adventurer selects one action, then actions resolve clockwise from frontline.
- A player may perform at most one swap action per turn.
- If an adventurer cannot act or is skipped, no action resolves for that slot.

## Action Sources
Each adventurer can potentially act via:
1. Signature ability (active or passive loadout choice)
2. Basic ability (2 selected from class pool; active or passive)
3. Twist ability (active only; only while that adventurer is your last remaining)
4. Equipped item (active or passive)
5. Swap action

## Targeting and Range Logic
- **Melee** cannot target backline enemies.
- **Ranged in frontline** can target all enemies.
- **Ranged in backline** can target enemy frontline + opposing backline across from them.
- **Spread** affects all legal targets at 50% damage.
- Spotlight allows melee to target that backline unit.

## Mixed Classes: Noble and Warlock
- Both are **melee in frontline** and **ranged in backline**.
- Backline ability use increments ranged recharge counter.
- Frontline ability use does not increment ranged recharge.

## Resource / Tempo Rule: Ranged Recharge
- Ranged adventurers must skip one action to recharge after using three abilities.
- If Shocked, that threshold becomes two abilities.

## Damage and Modifiers
- Base formula: `Damage = ceil(Power × (Attack / Defense))`.
- KO at HP <= 0.
- **Weaken**: adventurer deals 20% less damage.
- **Expose**: adventurer takes 20% more damage.
- **Guard**: adventurer takes 20% less damage.

## Status Condition Matrix
- **Burn**: 10% max HP per round.
- **Root**: cannot swap.
- **Shock**: ranged recharge threshold lowered to 2 uses.
- **Weaken**: -20% outgoing damage.
- **Expose**: +20% incoming damage.
- **Guard**: -20% incoming damage.
- **Spotlight**: melee can target the spotlighted backline unit.
- Same-type status conditions do not stack; different types stack freely.

## Stat Buffs and Debuffs
- Unless stated otherwise, stat buffs do not stack with each other; stat debuffs do not stack with each other.
- Stat calculation uses the **highest stat buff** and the **highest stat debuff** the adventurer has.

## Class Identities
- **Warden**: durability, mitigation, ally protection.
- **Fighter**: frontline pressure and direct offense.
- **Rogue**: disruption, repositioning, punish windows.
- **Ranger**: flexible ranged pressure + utility.
- **Mage**: high-impact ranged status and burst, fragile.
- **Cleric**: sustain, cleansing, defensive support.
- **Noble (mixed)**: tanky board-control bruisers using positioning and action manipulation.
- **Warlock (mixed)**: Malice-based disruptors that punish enemy action and inaction.

---

## Basic Ability System (Appendix B)

### Fighter
- **Strike**: FL 55 power | BL n/a
- **Rend**: FL 45 power +20 vs <50% HP | BL next ability vs target +10 power
- **Feint**: FL 45 power +10 Speed 2r (self) | BL +10 Speed 2r (self)
- **Cleave**: FL 45 power ignore 20% Def | BL next ability vs target ignores 10% Def
- **Intimidate**: FL 45 power Weaken 2r | BL Weaken 2r

### Rogue
- **Sneak Attack**: FL 45 power +15 if target hasn't acted | BL target -10 Speed 2r
- **Riposte**: FL 45 power user takes 50% less damage this round | BL user takes 50% less damage
- **Post Bounty**: FL 40 power Expose 2r | BL Expose 2r
- **Sucker Punch**: FL 40 power +20 if target is **Exposed or Weakened** | BL Weaken 2r
- **Fleetfooted** (passive): FL first incoming ability 20% less damage | BL first incoming ability 10% less damage

### Warden
- **Shield Bash**: FL 40 power Guard allies 2r | BL Guard frontline ally 2r
- **Condemn**: FL 40 power -10 Atk 2r | BL -10 Atk 2r
- **Slam**: FL 45 power +15 if user is Guarded | BL Guard user 2r
- **Armored** (passive): FL +10 Def | BL +5 Def
- **Stalwart** (passive): FL user takes -10 damage from abilities | BL frontline ally takes -10 damage

### Mage
- **Fire Blast**: FL 60 power Burn 2r | BL 35 power Burn 2r
- **Thunder Call**: FL 60 power Shock 2r | BL 35 power Shock 2r
- **Freezing Gale**: FL 60 power Root 2r | BL 35 power Root 2r
- **Arcane Wave**: FL 70 power user -10 Atk -10 Def 2r | BL 40 power
- **Breakthrough**: FL +15 Atk 2r (self) | BL +10 Atk 2r (self) + Spotlighted 2r

### Ranger
- **Hawkshot**: FL 60 power can't be redirected | BL 40 power can't be redirected
- **Volley**: FL 60 power spread | BL 40 power spread
- **Hunter's Mark**: FL 50 power target +10 dmg from abilities next round | BL 25 power same
- **Trapping Blow**: FL 60 power Roots Weakened targets | BL 35 power Weaken 2r
- **Hunter's Badge** (passive): FL +10 Atk | BL +5 Atk

### Cleric
- **Heal**: FL heal **ally** 60 HP | BL heal **ally** 45 HP
- **Bless**: FL Guard ally 2r + ally +10 Atk 2r | BL Guard ally 2r
- **Smite**: FL 55 power Burn 2r | BL 40 power
- **Medic** (passive): FL healing effects cure status conditions and debuffs | BL healing effects cure status conditions
- **Protection** (passive): FL allies +10 Def | BL allies +5 Def

### Noble
- **Impose**: FL 50 power -10 Speed 2r | BL 30 power -10 Speed 2r
- **Edict**: FL 50 power Root 2r | BL 30 power Spotlight 2r
- **Decree**: FL 40 power +10 Atk 2r (self) | BL 25 power -10 Atk 2r (target)
- **Summons**: FL+BL swap with ally; cannot use on consecutive turns
- **Command** (passive): FL enemies that attacked user last round take +10 dmg from ally abilities | BL enemies that attacked ally last round take +10 dmg from user

### Warlock
- **Dark Grasp**: FL 50 power gain 1 Malice | BL 35 power spend 1 Malice to Weaken 2r
- **Soul Gaze**: FL 45 power spend 1 Malice to Expose 2r | BL 30 power gain 1 Malice
- **Blood Pact**: FL lose 20 HP gain 2 Malice | BL heal 20 HP; spend 1 Malice heal 20 more
- **Cursed Armor** (passive): FL+BL gain 1 Malice when damaged by enemy ability
- **Void Step** (passive): FL swap to backline → gain 1 Malice | BL swap to frontline → spend 2 Malice for +10 Speed 2r

---

## Item System (Appendix C)

### Active Items (9)
- **Health Potion**: Heals 60 HP
- **Healing Tonic**: Heals user or ally 40 HP
- **Crafty Shield**: Guards user or ally for 2 rounds
- **Lightning Boots**: +10 Speed next round (self)
- **Main-Gauche**: +10 Attack for 2 rounds (self)
- **Iron Buckler**: +10 Defense for 2 rounds (self)
- **Smoke Bomb**: User switches positions with an ally
- **Hunter's Net**: Roots target for 2 rounds
- **Ancient Hourglass**: User cannot act or be targeted next round. Once per battle.

### Passive Items (7)
- **Family Seal**: User's signature ability deals +10 damage
- **Holy Diadem**: Once per battle, survive fatal damage at 1 HP and take no damage that round
- **Vampire Fang**: User's abilities have 10% vamp
- **Spiked Mail**: Enemies damaging the user take 15 damage
- **Arcane Focus**: User has +7 Attack when using abilities from the backline
- **Heart Amulet**: User's healing effects restore 15 additional HP
- **Misericorde**: User deals +10 more damage to targets with a status condition

---

## Adventurer Roster (Appendix A)

### Fighters
- **Risa Redcloak**: HP 250, ATK 75, DEF 60, SPD 30. Talent: below 50% HP → +15 Atk/Spd + 20% vamp. S1 Crimson Fury (FL 65+self Expose | BL Weaken 2r), S2 Wolf's Pursuit (FL 55+follow swap | BL Expose 2r), S3 Blood Hunt (FL 60 2xvamp | BL HP average).
- **Little Jack**: HP 220, ATK 80, DEF 50, SPD 50. Talent: +30% damage vs higher max HP targets. S1 Skyfall (FL 70 | BL Expose 2r), S2 Belligerence (passive; FL ignore 20% Def | BL ignore 20% Atk), S3 Magic Growth (FL 50+Root | BL Root+next ability +15).
- **Witch-Hunter Gretel**: HP 215, ATK 80, DEF 45, SPD 60. Talent: KO → +15 Atk +10 Spd 2r. S1 Shove Over (FL 60+Weaken | BL Weaken+next +15), S2 Hot Mitts (passive burn/burn-bonus), S3 Crumb Trail (FL 55 | BL drop crumb heals 40 HP on swap).

### Rogues
- **Lucky Constantine**: HP 215, ATK 70, DEF 40, SPD 75. Talent: Shadowstep (ignore melee restriction vs Exposed, -10 backline dmg). S1 Feline Gambit (FL 45+Expose | BL Expose), S2 Subterfuge (FL 50+swap | BL swap), S3 Nine Lives (passive; survive fatal 3x vs Exposed attackers).
- **Hunold the Piper**: HP 210, ATK 60, DEF 45, SPD 65. Talent: Shocked enemies take +15 dmg. S1 Haunting Rhythm (FL 50+Shock | BL Shock), S2 Dying Dance (FL 60+Shock Weakened targets | BL Weaken), S3 Hypnotic Aura (passive; redirect Shocked incoming abilities).
- **Reynard, Lupine Trickster**: HP 205, ATK 65, DEF 45, SPD 75. Talent: Cunning Dodge (50% dmg from first ability; refreshes on swap). S1 Size Up (FL 45+Weaken | BL 35+Expose), S2 Feign Weakness (FL 50+retaliate 55 | BL retaliate 45), S3 Cutpurse (FL 40+steal 10 Spd | BL swap with frontline ally).

### Wardens
- **Sir Roland**: HP 265, ATK 40, DEF 80, SPD 30. Talent: Silver Aegis (0 dmg first ability after swapping to FL). S1 Shimmering Valor (FL 40% dmg reduction 3r | BL heal 55+15/Valor round), S2 Knight's Challenge (FL 35+Taunt | BL Taunt front ranged), S3 Banner of Command (passive; Guard ally 2r when they swap).
- **Porcus III**: HP 280, ATK 35, DEF 85, SPD 20. Talent: Bricklayer (ability ≥25% max HP → reduce 40% + Weaken attacker). S1 Not By The Hair (FL 60% less dmg self | BL 35% less dmg frontline ally), S2 Porcine Honor (passive Guard start of round), S3 Sturdy Home (passive; all allies +7/+10 Def).
- **Lady of Reflections**: HP 255, ATK 40, DEF 75, SPD 32. Talent: Reflecting Pool (reflect 10% dmg; 20% if attacker backline). S1 Drown in the Loch (FL 40+target +10 dmg 2r | BL same without power), S2 Postmortem Passage (passive; KO'd ally fires 40-power counter), S3 Lake's Gift (FL ally +Reflect+10 Atk 2r | BL ally +Reflect).

### Mages
- **Ashen Ella**: HP 185, ATK 80, DEF 40, SPD 65. Talent: Two Lives (untargetable backline, can only act frontline). S1 Crowstorm (FL 60 spread+Burn | BL Burn, ignores Two Lives restriction), S2 Midnight Dour (passive; FL swap if ≤50% HP | BL heal 35 end of round), S3 Fae Blessing (FL Guard+15 Atk | BL heal ally 50, ignores Two Lives restriction).
- **March Hare**: HP 190, ATK 70, DEF 35, SPD 70. Talent: On Time! (-15 Spd to frontline enemy while frontline). S1 Tempus Fugit (FL 50 -12 Spd | BL 35 -10 Spd), S2 Rabbit Hole (FL extra action next round | BL swap with ally), S3 Nebulous Ides (FL 55 +20 if target acted | BL 40).
- **Witch of the Woods**: HP 180, ATK 75, DEF 35, SPD 65. Talent: Double Double (spread target's last status to enemy left when damaging statused target). S1 Toil and Trouble (FL 60+spread right status | BL 35+Burn), S2 Cauldron Bubble (FL 60 spread+extend status | BL 30 spread+extend), S3 Crawling Abode (passive; +10 Spd if FL enemy statused, 2+ statuses → +10 dmg).

### Rangers
- **Briar Rose**: HP 195, ATK 60, DEF 45, SPD 60. Talent: Curse of Sleeping (each round, the lowest-HP Rooted enemy loses Root, cannot act that round, and cannot be Rooted next round). S1 Thorn Snare (FL Root spread | BL Root), S2 Creeping Doubt (FL 50 +40% vs Rooted | BL 40+Root), S3 Garden of Thorns (passive; Root attackers FL / Root swappers BL).
- **Frederic the Beastslayer**: HP 200, ATK 65, DEF 45, SPD 60. Talent: Heedless Pride (+20% dmg to FL enemy; takes +10% dmg from FL enemy). S1 Hero's Charge (FL 60+ignore Pride dmg | BL 30+12 Spd 2r), S2 On the Hunt (FL 40+15 Atk 2r | BL 25+Expose), S3 Jovial Shot (FL 50+Weaken | BL self-heal 60+self Weaken).
- **Robin, Hooded Avenger**: HP 195, ATK 70, DEF 40, SPD 65. Talent: Keen Eye (+15 dmg to backline enemies). S1 Snipe Shot (FL 65 | BL 40 **ignores Guard**), S2 Spread Fortune (passive; FL spread damage penalty halved | BL spread targets all enemies), S3 Bring Down (FL 60+steal 10 Atk if target backline | BL 40+Root).

### Clerics
- **Aldric, Lost Lamb**: HP 230, ATK 45, DEF 60, SPD 35. Talent: All-Caring (healing effects Guard recipient 2r). S1 Benefactor (passive; FL +25% healing | BL +15% healing), S2 Sanctuary (passive; FL allies heal 1/10 max HP/round | BL frontline ally heals 1/8), S3 Repentance (FL 50+35% vamp | BL 40+20% vamp).
- **Matchstick Liesl**: HP 210, ATK 50, DEF 50, SPD 50. Talent: Purifying Flame (healing grants Burn immunity 2r; recipient's next ability Burns target 2r). S1 Cinder Blessing (FL HP average with ally | BL self-heal 60), S2 Flame of Renewal (passive; on KO → allies heal ½ max HP + Purifying Flame), S3 Cauterize (FL 50+no-heal 2r | BL 40+no-heal).
- **Snowkissed Aurora**: HP 225, ATK 45, DEF 60, SPD 40. Talent: Innocent Heart (ally/self loses status → +10 Def 2r + Aurora heals 20 HP). S1 Toxin Purge (FL remove all statuses from ally/self | BL remove last status), S2 Dictate of Nature (FL 50+heal lowest 40 | BL 40+heal lowest 30), S3 Birdsong (passive; FL cure last status end of round | BL +5 Atk 2r on Innocent Heart, stacks x3).

### Nobles
- **Prince Charming**: HP 255, ATK 65, DEF 55, SPD 35. Talent: Mesmerizing (FL enemies targeting allies -10 Atk 2r). S1 Condescend (FL 60 -10 Def 2r | BL 40+next ability +15), S2 Gallant Charge (FL 65 +20 if was BL last round | BL 35+15 Spd next round), S3 Chosen One (passive; champion buff on first swap).
- **Green Knight**: HP 275, ATK 60, DEF 60, SPD 20. Talent: Challenge Accepted (+25 dmg to target across from him). S1 Hero's Bargain (FL 50+Root | BL 25+swap target with FL enemy), S2 Natural Order (passive; +15 dmg vs unswapped 2r+ targets), S3 Awaited Blow (passive; FL retaliate 40 vs non-across attackers | BL heal 40 end of round).
- **Rapunzel the Golden**: HP 258, ATK 60, DEF 65, SPD 30. Talent: Flowing Locks (ignore melee restriction once/battle; refreshes ending round BL). S1 Golden Snare (FL 60+refresh Root | BL 30+Root), S2 Lower Guard (FL 55+15 if target debuffed | BL 30 -10 Def 2r), S3 Ivory Tower (passive; FL ranged enemies -10 Def | BL melee enemies -10 Atk).

### Warlocks
- **Pinocchio, Cursed Puppet**: HP 220, ATK 65, DEF 50, SPD 50. Talent: Growing Pains (end round FL → +1 Malice ≤6; +5 Atk+Def per Malice). S1 Wooden Wallop (FL 45+10/Malice | BL 35+1 Malice), S2 Cut the Strings (FL 60+Expose | BL 40+2 Malice→Spotlight), S3 Become Real (passive; 3+ Malice FL→ +15 dmg+immune; BL → no recharge increment).
- **Rumpelstiltskin**: HP 215, ATK 70, DEF 55, SPD 60. Talent: Art of the Deal (ally gains stat buff → +1 Malice ≤6; +5 Spd per Malice). S1 Name the Price (FL 70+target +10 Atk 2r | BL 40+2 Malice→nullify buffs 2r), S2 Straw to Gold (FL steal ally highest buff+5/Malice | BL convert ally debuff to buff), S3 Spinning Wheel (passive; FL +5 dmg/unique ally buff | BL 2 Malice to refresh lost ally buff).
- **Sea Wench Asha**: HP 210, ATK 75, DEF 45, SPD 65. Talent: Stolen Voices (enemy sig → BL +1 Malice ≤6; FL enemy sig -5 dmg/Malice). S1 Abyssal Call (FL 60+2 Malice→-10 Def 2r | BL 40+refresh debuff duration), S2 Misappropriate (FL 2 Malice→copy FL enemy sig | BL 35+Root 2r), S3 Faustian Bargain (passive; FL on swap +2 Malice→bottled talent | BL on KO bottle talent+10 Spd 2r).

---

## Advanced Interaction Notes
- **Initiative engineering**: speed steals/debuffs reshape first-action control.
- **Status pipelines**: Burn/Root/Shock chains paired with duration extension and conditional bonus damage.
- **Position denial**: Root + anti-swap punishers + forced swaps trap vulnerable units.
- **Damage shaping**: Guard + defense buffs + flat reduction compress enemy spikes.
- **Backline access**: spotlight, Shadowstep, anti-Guard tools, and redirect immunity define assassination windows.
- **Last-stand Twist timing**: Twist requires being the last remaining ally — design for a reliable solo closer.
