from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Sequence

from settings import SLOT_BACK_LEFT, SLOT_BACK_RIGHT, SLOT_FRONT


BACKLINE_SLOTS = {SLOT_BACK_LEFT, SLOT_BACK_RIGHT}


@dataclass(frozen=True)
class StatusSpec:
    kind: str
    duration: int


@dataclass(frozen=True)
class StatSpec:
    stat: str
    amount: int
    duration: int


@dataclass(frozen=True)
class PassiveEffect:
    id: str
    name: str
    description: str
    special: str = ""


@dataclass(frozen=True)
class ActiveEffect:
    id: str
    name: str
    description: str = ""
    target: str = "enemy"  # enemy | ally | self | none
    power: int = 0
    heal: int = 0
    cooldown: int = 0
    ammo_cost: int = 0
    spread: bool = False
    counts_as_spell: bool = False
    ignore_targeting: bool = False
    recoil: float = 0.0
    lifesteal: float = 0.0
    bonus_power_if_status: str = ""
    bonus_power: int = 0
    target_statuses: Sequence[StatusSpec] = ()
    self_statuses: Sequence[StatusSpec] = ()
    self_buffs: Sequence[StatSpec] = ()
    target_buffs: Sequence[StatSpec] = ()
    target_debuffs: Sequence[StatSpec] = ()
    special: str = ""


@dataclass(frozen=True)
class WeaponDef:
    id: str
    name: str
    kind: str  # melee | ranged | magic
    strike: ActiveEffect
    ammo: int = 0
    passive_skills: Sequence[PassiveEffect] = ()
    spells: Sequence[ActiveEffect] = ()


@dataclass(frozen=True)
class ArtifactDef:
    id: str
    name: str
    attunement: Sequence[str]
    stat: str
    amount: int
    spell: ActiveEffect
    reactive: bool = False
    description: str = ""


@dataclass(frozen=True)
class AdventurerDef:
    id: str
    name: str
    hp: int
    attack: int
    defense: int
    speed: int
    innate: PassiveEffect
    signature_weapons: Sequence[WeaponDef]
    ultimate: ActiveEffect


@dataclass
class StatusInstance:
    kind: str
    duration: int


@dataclass
class StatMod:
    stat: str
    amount: int
    duration: int


@dataclass
class CombatantState:
    defn: AdventurerDef
    slot: str
    class_name: str
    class_skill: PassiveEffect
    primary_weapon: WeaponDef
    secondary_weapon: WeaponDef
    artifact: Optional[ArtifactDef] = None
    hp: int = 0
    statuses: List[StatusInstance] = field(default_factory=list)
    buffs: List[StatMod] = field(default_factory=list)
    debuffs: List[StatMod] = field(default_factory=list)
    cooldowns: Dict[str, int] = field(default_factory=dict)
    ammo_remaining: Dict[str, int] = field(default_factory=dict)
    markers: Dict[str, Any] = field(default_factory=dict)
    queued_action: Optional[dict] = None
    queued_bonus_action: Optional[dict] = None
    ko: bool = False

    def __post_init__(self):
        if self.hp <= 0:
            self.hp = self.defn.hp
        for weapon in self.defn.signature_weapons:
            if weapon.ammo > 0:
                self.ammo_remaining.setdefault(weapon.id, weapon.ammo)

    @property
    def name(self) -> str:
        return self.defn.name

    @property
    def max_hp(self) -> int:
        return self.defn.hp

    def has_status(self, kind: str) -> bool:
        return any(status.kind == kind and status.duration > 0 for status in self.statuses)

    def add_status(self, kind: str, duration: int) -> bool:
        if kind == "root" and self.has_status("root_immunity"):
            return False
        if self.defn.id == "pinocchio_cursed_puppet" and self.markers.get("malice", 0) >= 3:
            return False
        for status in self.statuses:
            if status.kind == kind and status.duration > 0:
                return False
        self.statuses.append(StatusInstance(kind=kind, duration=duration))
        return True

    def remove_status(self, kind: str):
        self.statuses = [status for status in self.statuses if status.kind != kind]

    def best_buff(self, stat: str) -> int:
        return max((buff.amount for buff in self.buffs if buff.stat == stat and buff.duration > 0), default=0)

    def best_debuff(self, stat: str) -> int:
        return max((debuff.amount for debuff in self.debuffs if debuff.stat == stat and debuff.duration > 0), default=0)

    def get_stat(self, stat: str) -> int:
        base = getattr(self.defn, stat)
        if self.artifact is not None and self.artifact.stat == stat:
            base += self.artifact.amount
        if self.markers.get("guest_of_beast", 0) and stat == "defense":
            base += 15
        if self.defn.id == "red_blanchette" and self.hp <= math.ceil(self.max_hp * 0.5):
            bonus = 30 if self.markers.get("wolf_unchained_rounds", 0) > 0 else 15
            if stat in {"attack", "speed"}:
                base += bonus
        if self.defn.id == "pinocchio_cursed_puppet" and stat in {"attack", "defense"}:
            base += self.markers.get("malice", 0) * 5
        if stat == "speed" and self.slot in BACKLINE_SLOTS:
            base -= 30
        if stat == "speed" and self.has_status("shock"):
            base -= 15
        if self.class_skill.id == "bulwark" and stat == "defense" and self.slot == SLOT_FRONT:
            base += 15
        if self.class_skill.id == "protector" and stat == "defense":
            base += 10
        total = base + self.best_buff(stat) - self.best_debuff(stat)
        return max(1, total)

    def add_buff(self, stat: str, amount: int, duration: int):
        for buff in self.buffs:
            if buff.stat == stat and buff.amount == amount:
                buff.duration = max(buff.duration, duration)
                return
        self.buffs.append(StatMod(stat=stat, amount=amount, duration=duration))

    def add_debuff(self, stat: str, amount: int, duration: int):
        for debuff in self.debuffs:
            if debuff.stat == stat and debuff.amount == amount:
                debuff.duration = max(debuff.duration, duration)
                return
        self.debuffs.append(StatMod(stat=stat, amount=amount, duration=duration))

    def active_spells(self) -> List[ActiveEffect]:
        spells = list(self.primary_weapon.spells)
        if self.artifact is not None and not self.artifact.reactive:
            spells.append(self.artifact.spell)
        for effect in self.markers.get("stolen_spells", []):
            if effect not in spells:
                spells.append(effect)
        return spells


@dataclass
class TeamState:
    player_name: str
    members: List[CombatantState]
    ultimate_meter: int = 0
    markers: Dict[str, Any] = field(default_factory=dict)

    def alive(self) -> List[CombatantState]:
        return [member for member in self.members if not member.ko]

    def all_ko(self) -> bool:
        return all(member.ko for member in self.members)

    def get_slot(self, slot: str) -> Optional[CombatantState]:
        return next((member for member in self.members if member.slot == slot and not member.ko), None)

    def frontline(self) -> Optional[CombatantState]:
        return self.get_slot(SLOT_FRONT)


@dataclass
class BattleState:
    team1: TeamState
    team2: TeamState
    round_num: int = 1
    initiative_order: List[CombatantState] = field(default_factory=list)
    winner: Optional[int] = None
    log: List[str] = field(default_factory=list)

    def get_team(self, player_num: int) -> TeamState:
        return self.team1 if player_num == 1 else self.team2

    def get_enemy(self, player_num: int) -> TeamState:
        return self.team2 if player_num == 1 else self.team1

    def log_add(self, message: str):
        self.log.append(message)
