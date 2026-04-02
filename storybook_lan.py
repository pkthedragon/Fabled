from __future__ import annotations

from dataclasses import dataclass

from net import LANClient, LANHost, probe_lan_host
from quests_ruleset_logic import (
    player_num_for_actor,
    queue_bonus_action,
    queue_skip,
    queue_spell,
    queue_strike,
    queue_swap,
    queue_switch,
    queue_ultimate,
)


class StoryLanSession:
    def __init__(self):
        self.host: LANHost | None = None
        self.client: LANClient | None = None
        self.connection_mode = "host"
        self.join_ip = ""

    @property
    def is_host(self) -> bool:
        return self.connection_mode == "host"

    @property
    def connected(self) -> bool:
        if self.is_host:
            return bool(self.host and self.host.connected)
        return bool(self.client and self.client.connected)

    def local_ip(self) -> str:
        if self.host is None:
            return ""
        return self.host.local_ip()

    def reset(self):
        preserved_join_ip = self.join_ip
        if self.host is not None:
            self.host.close()
        if self.client is not None:
            self.client.close()
        self.host = None
        self.client = None
        self.join_ip = preserved_join_ip
        self.connection_mode = "host"

    def host_match(self):
        if self.host is None:
            self.reset()
            self.host = LANHost()
        self.connection_mode = "host"

    def join_match(self):
        if self.client is None:
            self.reset()
            self.client = LANClient()
        self.connection_mode = "join"

    def connect(self, ip_text: str):
        self.join_match()
        self.join_ip = ip_text.strip()
        if self.client is not None and self.join_ip:
            self.client.connect_async(self.join_ip)

    def send(self, message: dict):
        if self.is_host and self.host is not None:
            self.host.send(message)
        elif not self.is_host and self.client is not None:
            self.client.send(message)

    def poll(self) -> list[dict]:
        if self.is_host and self.host is not None:
            return self.host.poll()
        if not self.is_host and self.client is not None:
            return self.client.poll()
        return []


def serialize_member(member: dict) -> dict:
    return {
        "adventurer_id": member["adventurer_id"],
        "slot": member["slot"],
        "class_name": member["class_name"],
        "class_skill_id": member["class_skill_id"],
        "primary_weapon_id": member["primary_weapon_id"],
        "artifact_id": member["artifact_id"],
    }


def serialize_setup_state(setup_state: dict) -> dict:
    return {
        "offer_ids": list(setup_state.get("offer_ids", [])),
        "team1": [serialize_member(member) for member in setup_state["team1"]],
        "team2": [serialize_member(member) for member in setup_state["team2"]],
    }


def deserialize_setup_state(payload: dict) -> dict:
    return {
        "offer_ids": list(payload.get("offer_ids", [])),
        "team1": [dict(member) for member in payload.get("team1", [])],
        "team2": [dict(member) for member in payload.get("team2", [])],
    }


def _find_actor(battle, team_num: int, adventurer_id: str):
    team = battle.team1 if team_num == 1 else battle.team2
    return next((member for member in team.members if member.defn.id == adventurer_id), None)


def serialize_phase_plan(battle, team_num: int, *, bonus: bool = False) -> list[dict]:
    actions: list[dict] = []
    for actor in battle.initiative_order:
        if player_num_for_actor(battle, actor) != team_num:
            continue
        action = actor.queued_bonus_action if bonus else actor.queued_action
        if action is None:
            continue
        target = action.get("target")
        payload = {
            "actor_team": team_num,
            "actor_id": actor.defn.id,
            "type": action.get("type", "skip"),
        }
        effect = action.get("effect")
        if effect is not None:
            payload["effect_id"] = effect.id
        if target is not None:
            payload["target_team"] = player_num_for_actor(battle, target)
            payload["target_id"] = target.defn.id
        actions.append(payload)
    return actions


def apply_phase_plan(battle, actions: list[dict], *, bonus: bool = False):
    for payload in actions:
        actor = _find_actor(battle, int(payload["actor_team"]), payload["actor_id"])
        if actor is None:
            continue
        action_type = payload.get("type", "skip")
        target = None
        if payload.get("target_team") is not None and payload.get("target_id") is not None:
            target = _find_actor(battle, int(payload["target_team"]), payload["target_id"])
        if action_type == "strike":
            queue_strike(actor, target)
        elif action_type == "spell":
            effect = next((effect for effect in actor.active_spells() if effect.id == payload.get("effect_id")), None)
            if effect is not None:
                if bonus:
                    queue_bonus_action(actor, {"type": "spell", "effect": effect, "target": target})
                else:
                    queue_spell(actor, effect, target)
        elif action_type == "ultimate":
            effect = actor.defn.ultimate
            if bonus:
                queue_bonus_action(actor, {"type": "ultimate", "effect": effect, "target": target})
            else:
                queue_ultimate(actor, target)
        elif action_type == "switch":
            if bonus:
                queue_bonus_action(actor, {"type": "switch"})
            else:
                queue_switch(actor)
        elif action_type == "swap":
            if bonus:
                queue_bonus_action(actor, {"type": "swap", "target": target})
            else:
                queue_swap(actor, target)
        elif action_type == "vanguard":
            queue_bonus_action(actor, {"type": "vanguard"})
        else:
            if bonus:
                queue_bonus_action(actor, {"type": "skip"})
            else:
                queue_skip(actor)


@dataclass(frozen=True)
class LanStatus:
    headline: str
    lines: tuple[str, ...]


def friend_host_available(ip_text: str, timeout: float = 0.2) -> bool:
    return probe_lan_host(ip_text, timeout=timeout)
