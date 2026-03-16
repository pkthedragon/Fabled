from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
import battle_log


# ─────────────────────────────────────────────────────────────────────────────
# ABILITY MODE
# Describes what an ability does when used from one specific position.
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class AbilityMode:
    # Unavailable from this position (e.g. Strike backline = n/a)
    unavailable: bool = False

    # Damage
    power: int = 0
    spread: bool = False          # hits all legal targets at 50% damage
    def_ignore_pct: int = 0       # ignore X% of target's Defense
    ignore_guard: bool = False    # this ability ignores Guard status

    # Conditional power bonuses
    bonus_vs_low_hp: int = 0       # +power if target is below 50% max HP
    bonus_vs_rooted: int = 0       # +power if target is Rooted (as ratio: 0.4 = 40%)
    bonus_if_not_acted: int = 0    # +power if target has not acted this round
    bonus_if_target_acted: int = 0 # +power if target has acted this round
    bonus_vs_higher_hp: int = 0    # +flat bonus if target max HP > actor max HP
    bonus_vs_backline: int = 0     # +flat bonus if target is in the backline
    bonus_vs_statused: int = 0     # +flat bonus if target has any status condition

    # Lifesteal
    vamp: float = 0.0              # heal for X% of damage dealt
    double_vamp_no_base: bool = False  # 2× base vamp but no own base vamp

    # Healing (targets an ally or self)
    heal: int = 0                  # flat HP healed to target ally
    heal_self: int = 0             # flat HP healed to self (not target)
    heal_lowest: int = 0           # flat HP to the alive ally (own team) with lowest HP

    # Guard effects
    guard_self: bool = False
    guard_target: bool = False     # guard the selected target ally
    guard_all_allies: bool = False
    guard_frontline_ally: bool = False

    # Status effects on TARGET (enemy)
    status: str = ""
    status_dur: int = 0

    # Second status on target (e.g. Into the Oven: burn+weaken+root)
    status2: str = ""
    status2_dur: int = 0
    status3: str = ""
    status3_dur: int = 0

    # Status effect on SELF
    self_status: str = ""
    self_status_dur: int = 0

    # Stat buffs on SELF
    atk_buff: int = 0
    atk_buff_dur: int = 0
    spd_buff: int = 0
    spd_buff_dur: int = 0
    def_buff: int = 0
    def_buff_dur: int = 0

    # Stat debuffs on TARGET
    atk_debuff: int = 0
    atk_debuff_dur: int = 0
    spd_debuff: int = 0
    spd_debuff_dur: int = 0
    def_debuff: int = 0
    def_debuff_dur: int = 0

    # Targeting flags
    cant_redirect: bool = False

    # Special text (one-off effects that need bespoke logic.py handlers)
    special: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# ABILITY
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Ability:
    id: str
    name: str
    category: str      # "basic" | "signature" | "twist"
    passive: bool
    frontline: AbilityMode
    backline: AbilityMode


# ─────────────────────────────────────────────────────────────────────────────
# ITEM
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class Item:
    id: str
    name: str
    passive: bool
    description: str = ""
    # Active effects (one use unless uses = 99)
    heal: int = 0             # heals user or chosen ally
    heal_self_only: bool = False  # if True, item heal targets only the user
    status: str = ""
    status_dur: int = 0
    guard: bool = False       # guard user or chosen ally
    atk_buff: int = 0
    atk_buff_dur: int = 0
    spd_buff: int = 0
    spd_buff_dur: int = 0
    def_buff: int = 0
    def_buff_dur: int = 0
    # Passive effects (always on)
    vamp: float = 0.0         # 10% vamp on abilities
    flat_vs_statused: int = 0 # +10 damage to statused targets
    reflect_pct: float = 0.0  # reflect X% of incoming damage
    flat_heal_bonus: int = 0  # +15 to healing effects
    spd_bonus_back: int = 0   # +7 atk when using abilities from backline (stored as atk)
    atk_bonus_back: int = 0
    signature_flat_bonus: int = 0  # +flat damage to signature abilities only
    uses: int = 1             # how many times the active can be used (1 = once, 99 = unlimited)
    once_per_battle: bool = False
    special: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# STATUS / BUFF INSTANCES
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class StatusInstance:
    kind: str
    duration: int


@dataclass
class StatMod:
    stat: str    # "attack" | "defense" | "speed"
    amount: int
    duration: int


# ─────────────────────────────────────────────────────────────────────────────
# ADVENTURER DEFINITION  (static data, never mutated during battle)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class AdventurerDef:
    id: str
    name: str
    cls: str          # "Fighter" | "Rogue" | "Warden" | "Mage" | "Ranger" | "Cleric"
    hp: int
    attack: int
    defense: int
    speed: int
    talent_name: str
    talent_text: str
    sig_options: List[Ability]   # 3 options; player picks one
    twist: Ability

    @property
    def role(self) -> str:
        if self.cls in ("Warlock", "Noble"):
            return self.cls.lower()
        return "ranged" if self.cls in ("Ranger", "Mage", "Cleric") else "melee"


# ─────────────────────────────────────────────────────────────────────────────
# COMBATANT STATE  (mutable battle state for one adventurer)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(eq=False)
class CombatantState:
    defn: AdventurerDef
    slot: str
    hp: int
    sig: Ability
    basics: List[Ability]
    item: Item

    # Battle tracking
    statuses: List[StatusInstance] = field(default_factory=list)
    buffs: List[StatMod] = field(default_factory=list)
    debuffs: List[StatMod] = field(default_factory=list)

    ko: bool = False
    twist_used: bool = False
    acted: bool = False

    # Ranged recharge
    ranged_uses: int = 0     # uses since last recharge
    must_recharge: bool = False

    # Item tracking
    item_uses_left: int = 1  # reset from item.uses at construction

    # One-off ability charges keyed by ability id
    ability_charges: Dict[str, int] = field(default_factory=dict)

    # Queued action for this turn
    queued: Optional[dict] = None
    queued2: Optional[dict] = None  # extra action (Rabbit Hole / Stitch In Time)

    # Temporary per-round flags
    untargetable: bool = False     # Ella Two Lives in backline
    cant_act: bool = False         # dormant, etc.
    dmg_reduction: float = 0.0    # flat damage reduction this round (Not By The Hair etc.)

    # For Reynard's retaliation
    retaliate_power: int = 0       # if > 0, will retaliate this round
    retaliate_speed_steal: int = 0

    # For Roland's Shimmering Valor: how many rounds remain
    valor_rounds: int = 0

    # Permanent max HP increase (Redemption twist)
    max_hp_bonus: int = 0

    # Last status inflicted (for Witch of the Woods Double Double, etc.)
    last_status_inflicted: str = ""

    # Extra actions next round (March Hare Rabbit Hole)
    extra_actions_next: int = 0
    extra_actions_now: int = 0     # extra actions available this turn

    # ── Convenience properties ────────────────────────────────────────────
    @property
    def name(self) -> str:
        return self.defn.name

    @property
    def max_hp(self) -> int:
        return self.defn.hp + self.max_hp_bonus

    @property
    def cls(self) -> str:
        return self.defn.cls

    @property
    def role(self) -> str:
        return self.defn.role

    # ── Status helpers ────────────────────────────────────────────────────
    def has_status(self, kind: str) -> bool:
        return any(s.kind == kind and s.duration > 0 for s in self.statuses)

    def add_status(self, kind: str, duration: int) -> bool:
        # Briar Rose root immunity: block new Root while charge is active
        if kind == "root" and self.ability_charges.get("briar_root_immune", 0) > 0:
            return False
        for s in self.statuses:
            if s.kind == kind:
                return False
        self.statuses.append(StatusInstance(kind=kind, duration=duration))
        self.last_status_inflicted = kind
        return True

    def remove_status(self, kind: str):
        self.statuses = [s for s in self.statuses if s.kind != kind]

    def clear_statuses(self):
        self.statuses.clear()

    # ── Stat helpers ──────────────────────────────────────────────────────
    def best_buff(self, stat: str) -> int:
        vals = [b.amount for b in self.buffs if b.stat == stat and b.duration > 0]
        return max(vals, default=0)

    def best_debuff(self, stat: str) -> int:
        vals = [d.amount for d in self.debuffs if d.stat == stat and d.duration > 0]
        return max(vals, default=0)

    def get_stat(self, stat: str) -> int:
        base = getattr(self.defn, stat)

        if self.ability_charges.get("unfettered_dur", 0) > 0:
            if stat in ("attack", "speed"):
                base = self.defn.defense
            elif stat == "defense":
                base = self.defn.attack

        base += self.ability_charges.get(f"{stat}_bonus", 0)

        malice = self.ability_charges.get("malice", 0)
        if self.defn.id == "pinocchio":
            if stat in ("attack", "defense"):
                base += malice * 5
        if self.defn.id == "rumpelstiltskin":
            if stat == "speed":
                base += malice * 5

        return max(1, base + self.best_buff(stat) - self.best_debuff(stat))

    def add_buff(self, stat: str, amount: int, duration: int) -> bool:
        """Apply a buff. Returns True if newly applied, False if already present (refreshed)."""
        for buff in self.buffs:
            if buff.stat == stat and buff.amount == amount:
                buff.duration = max(buff.duration, duration)
                return False
        self.buffs.append(StatMod(stat=stat, amount=amount, duration=duration))
        return True

    def add_debuff(self, stat: str, amount: int, duration: int) -> bool:
        """Apply a debuff. Returns True if newly applied, False if already present (refreshed)."""
        for debuff in self.debuffs:
            if debuff.stat == stat and debuff.amount == amount:
                debuff.duration = max(debuff.duration, duration)
                return False
        self.debuffs.append(StatMod(stat=stat, amount=amount, duration=duration))
        return True

    # ── Ability list ──────────────────────────────────────────────────────
    def all_active_abilities(self, is_last_alive: bool) -> List[Ability]:
        result = [a for a in self.basics if not a.passive]
        if not self.sig.passive:
            result.append(self.sig)
        if is_last_alive and not self.twist_used:
            result.append(self.defn.twist)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# TEAM STATE
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class TeamState:
    player_name: str
    members: List[CombatantState]

    def get_slot(self, slot: str) -> Optional[CombatantState]:
        for m in self.members:
            if m.slot == slot and not m.ko:
                return m
        return None

    def alive(self) -> List[CombatantState]:
        return [m for m in self.members if not m.ko]

    def all_ko(self) -> bool:
        return all(m.ko for m in self.members)

    def frontline(self) -> Optional[CombatantState]:
        return self.get_slot("front")


# ─────────────────────────────────────────────────────────────────────────────
# BATTLE STATE
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class BattleState:
    team1: TeamState
    team2: TeamState
    round_num: int = 1
    phase: str = "menu"
    init_player: int = 1
    prev_loser: int = 2
    acting_player: int = 1
    log: List[str] = field(default_factory=list)
    winner: Optional[int] = None
    r1_extra_swap_player: Optional[int] = None
    swap_used_this_turn: bool = False
    init_reason: str = ""           # human-readable explanation of initiative result
    crumb_team: Optional[int] = None   # which player's crumb is on the field (Crumb Trail)
    crumb_slot: Optional[str] = None   # which slot the crumb was dropped at
    crumb_picked_up: Optional[int] = None  # which player's team picked up crumb this turn

    def get_team(self, num: int) -> TeamState:
        return self.team1 if num == 1 else self.team2

    def get_enemy(self, num: int) -> TeamState:
        return self.team2 if num == 1 else self.team1

    def log_add(self, msg: str):
        self.log.append(msg)
        battle_log.log(msg)

    def log_noshow(self, msg: str):
        """Add to the battle log panel and log file, but NOT to the moving ticker."""
        self.log.append("\x01" + msg)
        battle_log.log(msg)

    def log_tech(self, msg: str):
        """Write a technical detail to the battle log file (not shown in-game)."""
        battle_log.tech(msg)


# ─────────────────────────────────────────────────────────────────────────────
# CAMPAIGN PROFILE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CampaignProfile:
    """Tracks player progress through the main story campaign."""
    recruited: "Set[str]" = field(default_factory=lambda: {
        "risa_redcloak", "robin_hooded_avenger", "aldric_lost_lamb"
    })
    sig_tier: int = 1                    # 1, 2, or 3 – max signature tier unlocked
    basics_tier: int = 2                 # max basics tier (1–5)
    unlocked_classes: "Set[str]" = field(default_factory=lambda: {
        "Fighter", "Ranger", "Cleric"
    })
    unlocked_items: "Set[str]" = field(default_factory=lambda: {
        "health_potion", "healing_tonic", "family_seal"
    })
    default_sigs: "Dict[str, str]" = field(default_factory=dict)  # adv_id -> sig_id
    twists_unlocked: bool = False
    quest_cleared: "Dict[int, bool]" = field(default_factory=dict)
    highest_quest_cleared: int = -1
    campaign_complete: bool = False
    ranked_glory_unlocked: bool = False
    tutorial_seen: "Set[str]" = field(default_factory=set)
    tutorials_enabled: bool = True  # show tutorial popups
    saved_teams: List[dict] = field(default_factory=list)
    fast_resolution: bool = False   # skip per-action step-through; resolve all at once
    new_unlocks: "Set[str]" = field(default_factory=set)  # catalog tabs with unseen unlocks
