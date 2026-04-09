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
    hp_bonus: int = 0


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
    reactive_spell: Optional[ActiveEffect] = None
    legendary: bool = False
    quest_only: bool = False
    enemy_only: bool = False
    description: str = ""

    @property
    def active_spell(self) -> Optional[ActiveEffect]:
        if self.reactive and self.reactive_spell is None:
            return None
        return self.spell

    @property
    def reactive_effect(self) -> Optional[ActiveEffect]:
        if self.reactive_spell is not None:
            return self.reactive_spell
        if self.reactive:
            return self.spell
        return None

    @property
    def has_active_spell(self) -> bool:
        return self.active_spell is not None

    @property
    def has_reactive_spell(self) -> bool:
        return self.reactive_effect is not None


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


@dataclass(frozen=True)
class QuestEnemyTierDef:
    id: str
    name: str
    description: str
    has_secondary_weapon: bool = False
    has_class_skill: bool = False
    has_innate: bool = False
    uses_artifact: bool = False
    uses_legendary_artifact: bool = False
    uses_legendary_class_skill: bool = False
    apex_dual_primaries: bool = False
    unique_named: bool = False


@dataclass(frozen=True)
class QuestLocaleDef:
    id: str
    name: str
    description: str


@dataclass
class StatusInstance:
    kind: str
    duration: int
    applied_round: int = 0


@dataclass
class StatMod:
    stat: str
    amount: int
    duration: int
    applied_round: int = 0


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
            self.hp = self.max_hp
        for weapon in self.defn.signature_weapons:
            if weapon.ammo > 0:
                self.ammo_remaining.setdefault(weapon.id, weapon.ammo)

    @property
    def name(self) -> str:
        return self.defn.name

    @property
    def max_hp(self) -> int:
        return self.defn.hp + self.class_skill.hp_bonus

    def has_status(self, kind: str) -> bool:
        return any(status.kind == kind and status.duration > 0 for status in self.statuses)

    def add_status(self, kind: str, duration: int) -> bool:
        current_round = int(self.markers.get("_current_round", 0))
        if kind != "root_immunity" and self.markers.get("status_immunity_rounds", 0) > 0:
            return False
        if kind == "root" and self.has_status("root_immunity"):
            return False
        if kind == "root_immunity":
            self.remove_status("root")
        if self.defn.id == "pinocchio_cursed_puppet" and self.markers.get("malice", 0) >= 3:
            return False
        for status in self.statuses:
            if status.kind == kind and status.duration > 0:
                status.duration = max(status.duration, duration)
                status.applied_round = current_round
                return True
        self.statuses.append(StatusInstance(kind=kind, duration=duration, applied_round=current_round))
        return True

    def remove_status(self, kind: str):
        self.statuses = [status for status in self.statuses if status.kind != kind]

    def best_buff(self, stat: str) -> int:
        return max((buff.amount for buff in self.buffs if buff.stat == stat and buff.duration > 0), default=0)

    def best_debuff(self, stat: str) -> int:
        return max((debuff.amount for debuff in self.debuffs if debuff.stat == stat and debuff.duration > 0), default=0)

    def get_stat(self, stat: str, battle: "BattleState | None" = None) -> int:
        base = getattr(self.defn, stat)
        if self.defn.id == "ali_baba":
            return max(1, base)
        if self.artifact is not None and self.artifact.stat == stat:
            base += self.artifact.amount
        if self.markers.get("guest_of_beast", 0) and stat == "defense":
            base += 25
        if self.defn.id == "red_blanchette" and self.hp <= math.ceil(self.max_hp * 0.5):
            bonus = 50 if self.markers.get("wolf_unchained_rounds", 0) > 0 else 25
            if stat in {"attack", "speed"}:
                base += bonus
        if self.defn.id == "pinocchio_cursed_puppet" and stat in {"attack", "defense"}:
            base += self.markers.get("malice", 0) * 15
        if (
            battle is not None
            and stat == "speed"
            and isinstance(battle.markers.get("air_currents"), dict)
            and battle.markers["air_currents"].get(self.slot, 0) > 0
        ):
            ally_team = battle.team1 if self in battle.team1.members else battle.team2
            if any(
                ally.defn.id == "witch_of_the_east" and ally.primary_weapon.id == "comet"
                for ally in ally_team.alive()
            ):
                base += 25
        if stat == "speed" and self.defn.innate.special == "bygone" and self.slot in BACKLINE_SLOTS:
            base += 25
        if stat == "speed" and self.slot in BACKLINE_SLOTS:
            base = base // 2
        if stat == "speed" and self.has_status("shock"):
            base -= 25
        if self.class_skill.id == "bulwark" and stat == "defense":
            base += 25 if self.slot == SLOT_FRONT else 15
        total = base + self.best_buff(stat) - self.best_debuff(stat)
        if self.defn.id == "maui_sunthief" and stat == "defense" and self.markers.get("raise_the_sky_rounds", 0) > 0:
            total *= 2
        return max(1, total)

    def add_buff(self, stat: str, amount: int, duration: int):
        current_round = int(self.markers.get("_current_round", 0))
        for buff in self.buffs:
            if buff.stat == stat and buff.amount == amount:
                buff.duration = max(buff.duration, duration)
                buff.applied_round = current_round
                return
        self.buffs.append(StatMod(stat=stat, amount=amount, duration=duration, applied_round=current_round))

    def add_debuff(self, stat: str, amount: int, duration: int):
        current_round = int(self.markers.get("_current_round", 0))
        for debuff in self.debuffs:
            if debuff.stat == stat and debuff.amount == amount:
                debuff.duration = max(debuff.duration, duration)
                debuff.applied_round = current_round
                return
        self.debuffs.append(StatMod(stat=stat, amount=amount, duration=duration, applied_round=current_round))

    def dual_primary_weapons_active(self) -> bool:
        return bool(self.markers.get("dual_primary_weapons", 0)) and self.secondary_weapon.id != self.primary_weapon.id

    def active_strike_weapons(self) -> List[WeaponDef]:
        weapons: List[WeaponDef] = [self.primary_weapon]
        if self.dual_primary_weapons_active():
            weapons.append(self.secondary_weapon)
        seen: set[str] = set()
        unique: List[WeaponDef] = []
        for weapon in weapons:
            if weapon.id in seen:
                continue
            seen.add(weapon.id)
            unique.append(weapon)
        return unique

    def strike_weapon_by_id(self, weapon_id: str | None) -> WeaponDef:
        if weapon_id is None:
            return self.primary_weapon
        for weapon in self.active_strike_weapons():
            if weapon.id == weapon_id:
                return weapon
        if self.primary_weapon.id == weapon_id:
            return self.primary_weapon
        if self.secondary_weapon.id == weapon_id:
            return self.secondary_weapon
        return self.primary_weapon

    def weapon_for_effect(self, effect_id: str | None) -> Optional[WeaponDef]:
        if effect_id is None:
            return None
        for weapon in self.active_strike_weapons():
            if weapon.strike.id == effect_id:
                return weapon
            if any(effect.id == effect_id for effect in weapon.spells):
                return weapon
        for weapon in self.defn.signature_weapons:
            if weapon.strike.id == effect_id:
                return weapon
            if any(effect.id == effect_id for effect in weapon.spells):
                return weapon
        return None

    def active_spells(self) -> List[ActiveEffect]:
        spells: List[ActiveEffect] = []
        for weapon in self.active_strike_weapons():
            for effect in weapon.spells:
                if all(existing.id != effect.id for existing in spells):
                    spells.append(effect)
        if (
            self.artifact is not None
            and self.artifact.active_spell is not None
            and self.class_name in self.artifact.attunement
        ):
            spells.append(self.artifact.active_spell)
        for effect in self.markers.get("stolen_spells", []):
            if effect not in spells:
                spells.append(effect)
        for effect in self.markers.get("granted_spells", []):
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
    markers: Dict[str, Any] = field(default_factory=dict)

    def get_team(self, player_num: int) -> TeamState:
        return self.team1 if player_num == 1 else self.team2

    def get_enemy(self, player_num: int) -> TeamState:
        return self.team2 if player_num == 1 else self.team1

    def log_add(self, message: str):
        self.log.append(message)
