"""Narrator v0.4c — World Store.

Persistent entity store for the World Engine. Replaces the flat GameState
with a proper entity model (NPCs/locations/items/factions/quests), procedural
generation support, and deterministic validation.

Built per sonnet-work/GLM-WORLD-ENGINE-SPEC.md (which supersedes
docs/WORLD-ENGINE-DESIGN.md).

Core principle: The LLM never IS the memory. The LLM only ever reads a
summary the code assembled, and proposes changes the code validates and
stores. Same trust model as the existing rules lawyer (apply_mechanics),
generalized from "HP and inventory" to "the entire world."

Persistence: two files per campaign:
  world_<campaign_id>.json  — entity snapshot, overwritten atomically each save
  turns_<campaign_id>.jsonl — append-only, one TurnRecord per line, never rewritten
"""
from __future__ import annotations

import json
import os
import re
import time
import random as _random
import difflib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Dataclasses (per spec §1)
# ---------------------------------------------------------------------------

@dataclass
class Link:
    rel: str            # "connected_to" | "member_of" | "owns" | "hostile_to" | etc.
    target_id: str


@dataclass
class Revision:
    turn: int
    field: str
    old: Any
    new: Any
    source: str          # "llm_update" | "guard_correction" | "player_action"


@dataclass
class Fact:
    turn: int
    text: str


@dataclass
class Entity:
    id: str                          # stable, opaque-ish: "npc_0007_gorak"
    type: str                        # "pc" | "npc" | "location" | "item" | "faction" | "quest"
    name: str                        # current display name
    norm_name: str                   # normalized for matching
    summary: str                     # 1-2 sentences, always shown when entity is in context
    attributes: dict                 # type-specific, see REQUIRED_ATTRS
    links: list[Link] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    alive: bool = True
    first_seen_turn: int = 0
    last_seen_turn: int = 0
    revisions: list[Revision] = field(default_factory=list)
    known_facts: list[Fact] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Entity:
        links = [Link(**l) for l in d.pop("links", [])]
        revisions = [Revision(**r) for r in d.pop("revisions", [])]
        known_facts = [Fact(**f) for f in d.pop("known_facts", [])]
        return cls(links=links, revisions=revisions, known_facts=known_facts, **d)


@dataclass
class Encounter:
    round: int = 1
    turn_order: list[str] = field(default_factory=list)
    active_entity_id: Optional[str] = None


@dataclass
class Scene:
    location_id: str
    present_entity_ids: list[str]
    started_turn: int
    encounter: Optional[Encounter] = None
    light: str = "normal"
    time_of_day: str = "day"


@dataclass
class RollRecord:
    turn: int
    action: str
    skill: str
    dc: int
    seed: int
    roll: int
    modifier: int
    total: int
    result: str              # "success" | "failure" | "critical_success" | "critical_failure"


@dataclass
class TurnRecord:
    turn: int
    player_input: str
    narrative: str
    mechanics_applied: list[str]
    roll: Optional[RollRecord] = None
    entity_deltas: list[str] = field(default_factory=list)


@dataclass
class TokenBudget:
    l0_system: int = 1200
    l1_campaign_meta: int = 300
    l2_directory: int = 1500
    l3_pinned: int = 1500
    l4_working_set: int = 2000
    l5_scene: int = 300
    l6_digest: int = 400
    l7_recent_turns: int = 1500
    l8_rules: int = 400
    l9_input: int = 200


@dataclass
class ContextBundle:
    stable_prefix: str
    volatile_suffix: str
    included_entity_ids: list[str]
    dropped_entity_ids: list[str]


# ---------------------------------------------------------------------------
# Required attributes per entity type (spec §1.1)
# ---------------------------------------------------------------------------

REQUIRED_ATTRS = {
    "npc": {"hp": int, "max_hp": int, "disposition": str, "voice_description": str},
    "pc": {"hp": int, "max_hp": int, "disposition": str, "voice_description": str,
           "inventory": list, "stats": dict},
    "location": {"description": str, "discovered": bool},
    "item": {"description": str, "owner_entity_id": str},
    "faction": {"description": str, "disposition_to_player": int},
    "quest": {"description": str, "status": str, "objectives": list},
}

# Mutable fields allowed for ENTITY_UPDATE (spec §3)
MUTABLE_FIELDS = {
    "npc": {"hp", "disposition", "voice_description", "summary"},
    "pc": {"hp", "disposition", "voice_description", "summary", "inventory"},
    "location": {"description", "discovered"},
    "item": {"description", "owner_entity_id"},
    "faction": {"description", "disposition_to_player"},
    "quest": {"description", "status", "objectives"},
}

# Articles/honorifics to strip during normalization (spec §4.2)
STRIP_PREFIXES = {"the", "a", "an", "old", "young", "ser", "sir", "captain",
                   "mister", "mr", "mrs", "ms", "lord", "lady", "master"}


# ---------------------------------------------------------------------------
# Normalization (spec §4, step 2)
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Normalize a name for matching: lowercase, strip punctuation/articles."""
    name = name.lower().strip()
    # Strip punctuation
    name = re.sub(r"[^\w\s]", "", name)
    # Strip leading articles/honorifics
    words = name.split()
    while words and words[0] in STRIP_PREFIXES:
        words.pop(0)
    name = " ".join(words)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# World Store (spec §2)
# ---------------------------------------------------------------------------

class WorldStore:
    """Persistent entity store + retrieval + validation.

    The LLM never directly modifies state. It proposes entities and mechanics
    via tags; the store validates and applies them deterministically.
    """

    def __init__(self, campaign_id: str = "default",
                 rules_profile: dict = None,
                 data_dir: Path = None):
        self.campaign_id = campaign_id
        self.rules_profile = rules_profile or {
            "name": "dnd5e_lite",
            "dc_ladder": {"trivial": 5, "easy": 10, "medium": 15, "hard": 20, "very_hard": 25},
            "ability_list": ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
            "hp_model": "flat",
            "crit_rule": "nat20_success_nat1_failure",
        }
        self.data_dir = data_dir or Path("outputs/narrator_v01")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.entities: dict[str, Entity] = {}
        self.aliases: dict[str, str] = {}  # norm_name -> entity_id
        self.turn_log: list[TurnRecord] = []
        self.current_scene: Optional[Scene] = None
        self.campaign_meta: dict = {}
        self._entity_counter = 0
        self._rng = _random.Random()
        self._turn_count = 0

    # --- ID generation ---

    def _next_id(self, entity_type: str, name: str) -> str:
        """Generate a stable, opaque-ish ID."""
        self._entity_counter += 1
        # Create a slug from the name
        slug = re.sub(r"[^\w]", "", name.lower())[:12]
        return f"{entity_type}_{self._entity_counter:04d}_{slug}"

    # --- Entity validation (spec §1.1) ---

    def _validate_entity(self, entity: Entity) -> list[str]:
        """Validate required attributes. Returns list of errors (empty = valid)."""
        errors = []
        req = REQUIRED_ATTRS.get(entity.type, {})
        for key, expected_type in req.items():
            if key not in entity.attributes:
                errors.append(f"Missing required attribute '{key}' for {entity.type}")
            elif not isinstance(entity.attributes[key], expected_type):
                # Special case: bool is subclass of int in Python
                if expected_type == int and isinstance(entity.attributes[key], bool):
                    pass  # accept bool as int
                else:
                    errors.append(f"Attribute '{key}' must be {expected_type.__name__}, got {type(entity.attributes[key]).__name__}")

        # HP clamp for npc/pc
        if entity.type in ("npc", "pc"):
            hp = entity.attributes.get("hp")
            max_hp = entity.attributes.get("max_hp")
            if isinstance(hp, int) and isinstance(max_hp, int):
                if hp < 0:
                    errors.append(f"HP cannot be negative (got {hp})")
                if hp > max_hp:
                    errors.append(f"HP ({hp}) cannot exceed max_hp ({max_hp})")

        # Faction disposition clamp
        if entity.type == "faction":
            disp = entity.attributes.get("disposition_to_player")
            if isinstance(disp, int):
                entity.attributes["disposition_to_player"] = max(-100, min(100, disp))

        # Quest status validation
        if entity.type == "quest":
            status = entity.attributes.get("status")
            if status not in ("active", "completed", "failed"):
                errors.append(f"Quest status must be active/completed/failed, got '{status}'")

        # Item owner validation
        if entity.type == "item":
            owner = entity.attributes.get("owner_entity_id")
            if owner and owner != "world" and owner != "player" and owner not in self.entities:
                errors.append(f"Item owner '{owner}' does not exist")

        return errors

    # --- Duplicate resolution: resolve_or_create (spec §4) ---

    def resolve_or_create(self, name: str, entity_type: str,
                          proposed_attrs: dict = None,
                          current_turn: int = 0,
                          current_location_id: str = None) -> tuple[Entity, bool, str]:
        """Resolve a name to an existing entity, or create a new one.

        8-step pipeline per Opus review §4.1:
        1. Code owns IDs; LLM refers by name only.
        2. Normalize name.
        3. Exact match on (norm_name, type).
        4. Alias table lookup.
        5. Fuzzy match (>=0.85 ratio, same type).
        6. Token overlap (shared first token, same type).
        7. Candidate policy: same location OR seen within last ~20 turns -> match.
           Otherwise -> create new with _2 suffix, log visibly.
        8. Return (entity, created, reason).
        """
        proposed_attrs = proposed_attrs or {}
        norm = normalize_name(name)

        # Step 3: Exact match on (norm_name, type)
        for eid, entity in self.entities.items():
            if entity.type == entity_type and entity.norm_name == norm:
                entity.last_seen_turn = current_turn
                return entity, False, f"matched exact name '{name}' -> {eid}"

        # Step 4: Alias table lookup
        alias_key = f"{norm}:{entity_type}"
        if alias_key in self.aliases:
            eid = self.aliases[alias_key]
            if eid in self.entities:
                entity = self.entities[eid]
                entity.last_seen_turn = current_turn
                # Record this as a new alias
                self.aliases[norm] = eid
                return entity, False, f"matched alias '{name}' -> {eid}"

        # Step 5: Fuzzy match (>=0.85 ratio, same type)
        best_ratio = 0.0
        best_entity = None
        for eid, entity in self.entities.items():
            if entity.type != entity_type:
                continue
            ratio = difflib.SequenceMatcher(None, norm, entity.norm_name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_entity = entity

        if best_entity and best_ratio >= 0.85:
            # Step 7: Candidate policy — same location or seen recently
            same_loc = (current_location_id and
                        any(l.rel == "connected_to" and l.target_id == current_location_id
                            for l in best_entity.links))
            recent = (current_turn - best_entity.last_seen_turn) <= 20

            if same_loc or recent:
                # Record alias
                self.aliases[norm] = best_entity.id
                best_entity.last_seen_turn = current_turn
                return best_entity, False, f"matched fuzzy '{name}' (ratio={best_ratio:.2f}) -> {best_entity.id}"
            else:
                # Create new with _2 suffix, log visibly
                pass  # fall through to creation

        # Step 6: Token overlap (shared first token, same type)
        # Matches when the first token of one name matches the first token
        # of the other, AND at least one name has multiple tokens.
        # This allows "Gorak" to match "Gorak the Goblin" but prevents
        # "Goblin Scout" from matching "Goblin Raider" (different second tokens).
        if norm:
            name_tokens = norm.split()
            first_token = name_tokens[0] if name_tokens else norm
            # Only use token overlap for longer first tokens (>= 4 chars)
            if len(first_token) >= 4:
                for eid, entity in self.entities.items():
                    if entity.type != entity_type:
                        continue
                    entity_tokens = entity.norm_name.split()
                    if not entity_tokens:
                        continue
                    # Match if first tokens are the same AND
                    # (one name is single-token OR second tokens also match)
                    if entity_tokens[0] == first_token:
                        # If both are single-token, they should have been
                        # caught by exact match. Only proceed if at least
                        # one is multi-token.
                        if len(name_tokens) == 1 and len(entity_tokens) >= 2:
                            # "Gorak" matching "Gorak the Goblin" — OK
                            pass
                        elif len(entity_tokens) == 1 and len(name_tokens) >= 2:
                            # "Gorak the Goblin" matching "Gorak" — OK
                            pass
                        elif len(name_tokens) >= 2 and len(entity_tokens) >= 2:
                            # Both multi-token — check second token matches
                            if name_tokens[1] != entity_tokens[1]:
                                continue  # "Goblin Scout" != "Goblin Raider"
                        else:
                            continue  # both single-token, should've matched earlier

                        same_loc = (current_location_id and
                                    any(l.rel == "connected_to" and l.target_id == current_location_id
                                        for l in entity.links))
                        recent = (current_turn - entity.last_seen_turn) <= 20
                        if same_loc or recent:
                            self.aliases[norm] = entity.id
                            entity.last_seen_turn = current_turn
                            return entity, False, f"matched token overlap '{name}' -> {entity.id}"

        # Step 8: Create new entity
        entity = Entity(
            id=self._next_id(entity_type, name),
            type=entity_type,
            name=name,
            norm_name=norm,
            summary=proposed_attrs.get("summary", ""),
            attributes=dict(proposed_attrs),
            first_seen_turn=current_turn,
            last_seen_turn=current_turn,
        )

        # Validate
        errors = self._validate_entity(entity)
        if errors:
            # Log errors but still create — the LLM needs something to work with
            for err in errors:
                print(f"[world_store] Validation warning for {entity.id}: {err}")

        self.entities[entity.id] = entity
        self.aliases[norm] = entity.id
        return entity, True, f"created new: no match within policy window"

    def propose_entity(self, name: str, entity_type: str, attrs: dict,
                       current_turn: int = 0,
                       current_location_id: str = None) -> tuple[Entity, bool, str]:
        """LLM-facing wrapper around resolve_or_create."""
        return self.resolve_or_create(name, entity_type, attrs,
                                      current_turn, current_location_id)

    # --- Apply turn mechanics (generalizes apply_mechanics) ---

    def apply_turn_mechanics(self, mechanics_tags: list[str],
                             current_turn: int = 0) -> list[str]:
        """Apply mechanics tags deterministically. Returns human-readable change log.

        Unknown/malformed tags are rejected and logged, never silently dropped.
        """
        changes = []
        enemies_with_roll_evidence = set()
        item_used_invalid = False

        # Pre-scan for roll evidence and item validation
        for tag in mechanics_tags:
            if ":" not in tag:
                continue
            t, v = tag.split(":", 1)
            t = t.strip().upper()
            v = v.strip()
            if t == "ROLL_REQUEST":
                for eid, entity in self.entities.items():
                    if entity.type == "npc" and entity.alive:
                        enemies_with_roll_evidence.add(entity.norm_name)
            elif t == "ITEM_USED":
                # Check if item exists in PC inventory
                pc = self._get_pc()
                if pc:
                    inv = pc.attributes.get("inventory", [])
                    # Items may be stored as entity IDs or as plain names (legacy)
                    item_found = False
                    for item_ref in inv:
                        if isinstance(item_ref, str):
                            if item_ref in self.entities:
                                # It's an entity ID — check by name
                                if self.entities[item_ref].name.lower() == v.lower():
                                    item_found = True
                                    break
                            elif item_ref.lower() == v.lower():
                                # It's a plain name (legacy compat)
                                item_found = True
                                break
                    if not item_found:
                        item_used_invalid = True

        # Apply tags
        for tag in mechanics_tags:
            if ":" not in tag:
                changes.append(f"[unparseable] {tag}")
                continue
            t, v = tag.split(":", 1)
            t = t.strip().upper()
            v = v.strip()

            if t == "HP_CHANGE":
                try:
                    amt = int(v)
                    pc = self._get_pc()
                    if pc:
                        old_hp = pc.attributes.get("hp", 0)
                        max_hp = pc.attributes.get("max_hp", 0)
                        new_hp = max(0, min(max_hp, old_hp + amt))
                        pc.attributes["hp"] = new_hp
                        changes.append(f"HP: {old_hp} -> {new_hp} ({'+' if amt >= 0 else ''}{amt})")
                except ValueError:
                    changes.append(f"[REJECTED - invalid HP_CHANGE] {v}")

            elif t == "ENEMY_HP":
                parts = v.split(",")
                if len(parts) == 2:
                    name = parts[0].strip()
                    hp_parts = parts[1].strip().split("/")
                    if len(hp_parts) == 2:
                        entity, created, reason = self.resolve_or_create(
                            name, "npc", current_turn=current_turn)
                        try:
                            new_hp = max(0, int(hp_parts[0]))
                            max_hp = int(hp_parts[1])
                            if new_hp == 0 and entity.norm_name not in enemies_with_roll_evidence:
                                changes.append(f"[REJECTED - no roll evidence] {entity.name} HP->0")
                                continue
                            entity.attributes["hp"] = new_hp
                            entity.attributes["max_hp"] = max_hp
                            changes.append(f"{entity.name} HP -> {new_hp}/{max_hp}")
                        except ValueError:
                            changes.append(f"[REJECTED - invalid ENEMY_HP] {v}")

            elif t == "ENEMY_DEAD":
                name = v.strip()
                entity, created, reason = self.resolve_or_create(
                    name, "npc", current_turn=current_turn)
                if entity.norm_name not in enemies_with_roll_evidence:
                    changes.append(f"[REJECTED - no roll evidence] {entity.name}")
                    continue
                if entity.alive:
                    entity.alive = False
                    entity.attributes["hp"] = 0
                    changes.append(f"{entity.name} DEAD")

            elif t == "ITEM_USED":
                if item_used_invalid:
                    changes.append(f"[REJECTED - invalid item in same turn] {v}")
                else:
                    pc = self._get_pc()
                    if pc:
                        inv = pc.attributes.get("inventory", [])
                        for i, item_ref in enumerate(inv):
                            if isinstance(item_ref, str):
                                if item_ref in self.entities:
                                    if self.entities[item_ref].name.lower() == v.lower():
                                        inv.pop(i)
                                        changes.append(f"Used: {v}")
                                        break
                                elif item_ref.lower() == v.lower():
                                    inv.pop(i)
                                    changes.append(f"Used: {v}")
                                    break

            elif t == "ITEM_GAINED":
                entity, created, reason = self.resolve_or_create(
                    v, "item", {"description": "", "owner_entity_id": "player"},
                    current_turn=current_turn)
                pc = self._get_pc()
                if pc:
                    inv = pc.attributes.get("inventory", [])
                    inv.append(entity.id)
                    pc.attributes["inventory"] = inv
                changes.append(f"Gained: {v}")

            elif t == "CONDITION":
                changes.append(f"Condition: {v}")

            elif t == "ROLL_REQUEST":
                changes.append(f"Roll requested: {v}")

            elif t == "ENTITY_NEW":
                # ENTITY_NEW:<type>,<name>,<summary>
                parts = v.split(",", 2)
                if len(parts) >= 2:
                    etype = parts[0].strip()
                    ename = parts[1].strip()
                    esummary = parts[2].strip() if len(parts) > 2 else ""
                    entity, created, reason = self.propose_entity(
                        ename, etype, {"summary": esummary},
                        current_turn=current_turn)
                    changes.append(f"{'Created' if created else 'Matched'}: {ename} ({reason})")

            elif t == "ENTITY_UPDATE":
                # ENTITY_UPDATE:<name>,<field>,<value>
                parts = v.split(",", 2)
                if len(parts) >= 3:
                    ename = parts[0].strip()
                    efield = parts[1].strip()
                    evalue = parts[2].strip()
                    entity, created, reason = self.resolve_or_create(
                        ename, "npc", current_turn=current_turn)
                    # Check if field is mutable
                    mutable = MUTABLE_FIELDS.get(entity.type, set())
                    if efield not in mutable and efield != "summary":
                        changes.append(f"[REJECTED - immutable field] {ename}.{efield}")
                        continue
                    old_val = entity.attributes.get(efield, entity.summary if efield == "summary" else None)
                    # Write revision
                    entity.revisions.append(Revision(
                        turn=current_turn, field=efield, old=old_val, new=evalue,
                        source="llm_update"
                    ))
                    if efield == "summary":
                        entity.summary = evalue
                    else:
                        entity.attributes[efield] = evalue
                    changes.append(f"Updated: {ename}.{efield} = {evalue}")

            elif t == "ALIAS":
                # ALIAS:<alt name> -> <canonical name>
                m = re.match(r"(.+?)\s*->\s*(.+)", v)
                if m:
                    alt_name = m.group(1).strip()
                    canon_name = m.group(2).strip()
                    canon_norm = normalize_name(canon_name)
                    for eid, entity in self.entities.items():
                        if entity.norm_name == canon_norm:
                            self.aliases[normalize_name(alt_name)] = eid
                            changes.append(f"Alias: '{alt_name}' -> '{canon_name}'")
                            break

            elif t == "QUEST_UPDATE":
                parts = v.split(",")
                if len(parts) >= 2:
                    qname = parts[0].strip()
                    qstatus = parts[1].strip()
                    if qstatus not in ("active", "completed", "failed"):
                        changes.append(f"[REJECTED - invalid quest status] {qstatus}")
                        continue
                    entity, created, reason = self.resolve_or_create(
                        qname, "quest", {"status": qstatus, "objectives": []},
                        current_turn=current_turn)
                    entity.attributes["status"] = qstatus
                    changes.append(f"Quest: {qname} -> {qstatus}")

            elif t == "NO_MECHANICS":
                pass  # no-op

            else:
                changes.append(f"[REJECTED - unknown tag] {t}:{v[:50]}")

        return changes

    def _get_pc(self) -> Optional[Entity]:
        """Get the player character entity."""
        for entity in self.entities.values():
            if entity.type == "pc":
                return entity
        return None

    # --- Scene management ---

    def enter_scene(self, location_id: str, current_turn: int) -> Optional[str]:
        """Update current Scene. Returns 'since you were last here' digest if applicable."""
        location = self.entities.get(location_id)
        if not location or location.type != "location":
            return None

        # Find entities present at this location
        present = [eid for eid, e in self.entities.items()
                   if eid != location_id and
                   any(l.rel == "connected_to" and l.target_id == location_id
                       for l in e.links)]
        # Also include entities seen recently at this location
        # (This is a simplified version — the full digest logic is v0.5a)

        old_scene = self.current_scene
        self.current_scene = Scene(
            location_id=location_id,
            present_entity_ids=present,
            started_turn=current_turn,
        )

        # Generate digest if returning to a previously-visited location
        if old_scene and old_scene.location_id == location_id:
            turns_away = current_turn - old_scene.started_turn
            if turns_away > 0:
                # Simple digest: list entities that changed since last visit
                changes = []
                for eid in present:
                    entity = self.entities.get(eid)
                    if entity and entity.last_seen_turn < old_scene.started_turn:
                        changes.append(f"{entity.name} is still here.")
                    elif entity and entity.last_seen_turn >= old_scene.started_turn:
                        changes.append(f"{entity.name} has arrived since you left.")
                if changes:
                    return " ".join(changes)

        return None

    def exit_scene(self) -> None:
        """Exit current scene."""
        self.current_scene = None

    # --- Consistency guards (spec §5) ---

    def presence_liveness_guard(self, narrative: str,
                                 current_turn: int = 0) -> dict:
        """Guard 3: Presence-and-liveness check (spec §5.3).

        Post-generation, pre-display: every speaker name in the narrative
        must resolve to an entity that is alive AND in scene.present_entity_ids
        (or is narrator/PC). Returns a dict with:
          - 'violations': list of {speaker, reason} dicts
          - 'correction_prompt': str to append if regenerating, or '' if clean
        On violation: caller should regenerate once with the correction message,
        then fail open with a visible warning — never block the turn entirely.
        """
        violations = []
        if not self.current_scene:
            return {"violations": [], "correction_prompt": ""}

        # Extract speaker names from [SpeakerName] tags in the narrative
        import re
        speakers = re.findall(r"\[([A-Za-z][A-Za-z\s]*?)\]", narrative)
        # Filter out non-speaker tags
        non_speaker_tags = {"narrator", "SFX", "SCENE", "STORY", "MECHANICS",
                            "SUGGESTIONS", "CHRONICLE", "AUDIO", "NEW", "KNOWN",
                            "RECALL", "REJECTED"}
        speakers = [s for s in speakers if s.lower() not in non_speaker_tags]

        pc = self._get_pc()
        pc_name = pc.name.lower() if pc else ""

        for speaker in speakers:
            speaker_lower = speaker.lower()
            # Skip narrator and PC
            if speaker_lower == "narrator" or speaker_lower == pc_name:
                continue

            # Resolve speaker to an entity
            entity = None
            for eid, e in self.entities.items():
                if e.name.lower() == speaker_lower or e.norm_name == normalize_name(speaker):
                    entity = e
                    break

            if entity is None:
                violations.append({
                    "speaker": speaker,
                    "reason": f"Speaker '{speaker}' not found in world store"
                })
            elif not entity.alive:
                violations.append({
                    "speaker": speaker,
                    "reason": f"Speaker '{speaker}' is dead"
                })
            elif entity.id not in self.current_scene.present_entity_ids:
                violations.append({
                    "speaker": speaker,
                    "reason": f"Speaker '{speaker}' is not present in the current scene"
                })

        correction = ""
        if violations:
            correction_lines = [f"INCONSISTENCY DETECTED — please correct:"]
            for v in violations:
                correction_lines.append(f"- {v['reason']}")
            correction_lines.append(
                "Only include dialogue from characters who are alive AND present "
                "in the current scene. Regenerate the narrative with this correction."
            )
            correction = "\n".join(correction_lines)

        return {"violations": violations, "correction_prompt": correction}

    def handle_recall(self, recall_query: str,
                      current_turn: int = 0) -> dict:
        """Handle [RECALL:name] from the LLM (spec §6).

        Resolve against directory + aliases. If found, return the full entity
        record to inject into context. If not found, return a message for the
        LLM. Hard cap: only one recall per turn — caller must enforce this.

        Returns:
          - {'found': True, 'entity_id': str, 'context_text': str} if found
          - {'found': False, 'message': str} if not found
        """
        norm = normalize_name(recall_query)

        # Direct alias lookup
        if norm in self.aliases:
            eid = self.aliases[norm]
            entity = self.entities.get(eid)
            if entity:
                return {
                    "found": True,
                    "entity_id": eid,
                    "context_text": self._entity_to_context_str(entity, mark="[RECALLED]"),
                }

        # Fuzzy match against all entity names
        best_ratio = 0.0
        best_entity = None
        for eid, entity in self.entities.items():
            ratio = difflib.SequenceMatcher(None, norm, entity.norm_name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_entity = entity

        if best_entity and best_ratio >= 0.7:
            return {
                "found": True,
                "entity_id": best_entity.id,
                "context_text": self._entity_to_context_str(best_entity, mark="[RECALLED]"),
            }

        return {
            "found": False,
            "message": f"No entity matching '{recall_query}' was found in the world directory.",
        }

    def check_contradiction(self, entity: Entity, field: str,
                            new_value: Any) -> Optional[str]:
        """Check if an ENTITY_UPDATE contradicts a previous value (spec §4.2).

        Returns a warning string if there's a contradiction, None otherwise.
        Contradictions are applied (not blocked) but logged visibly.
        """
        # Check revisions for this field
        for rev in reversed(entity.revisions):
            if rev.field == field:
                old_value = str(rev.new)  # last set value
                if str(new_value).lower() != old_value.lower():
                    return (f"CONTRADICTION: {entity.name}.{field} was "
                            f"'{old_value}', now set to '{new_value}' — "
                            f"applied but logged.")
                break
        return None

    # --- Roll recording ---

    def record_roll(self, roll: RollRecord) -> None:
        """Persist a roll to the turn log BEFORE the outcome is narrated."""
        if self.turn_log:
            # Attach to the most recent turn record
            self.turn_log[-1].roll = roll

    # --- Chronicle compaction ---

    def compact_chronicle(self, current_turn: int, k: int = 20) -> None:
        """Every K turns, compact older turns into a chronicle summary."""
        if current_turn % k != 0 or current_turn == 0:
            return
        # Simple version: just log that compaction happened
        # Full implementation would use a cheap model call to summarize
        print(f"[world_store] Chronicle compaction at turn {current_turn}")

    # --- Persistence (spec §2 — atomic writes) ---

    def save(self, path: Path = None) -> Path:
        """Atomic write: write to path.tmp, then os.replace()."""
        if path is None:
            path = self.data_dir / f"world_{self.campaign_id}.json"

        data = {
            "campaign_id": self.campaign_id,
            "rules_profile": self.rules_profile,
            "campaign_meta": self.campaign_meta,
            "entities": {eid: e.to_dict() for eid, e in self.entities.items()},
            "aliases": self.aliases,
            "turn_count": self._turn_count,
            "entity_counter": self._entity_counter,
            "schema_version": 1,
        }

        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        os.replace(tmp_path, path)
        return path

    def load(self, path: Path = None) -> "WorldStore":
        """Load from a JSON file."""
        if path is None:
            path = self.data_dir / f"world_{self.campaign_id}.json"

        if not path.exists():
            return self

        with open(path) as f:
            data = json.load(f)

        # Migration if needed
        data = self.migrate(data)

        self.campaign_id = data.get("campaign_id", self.campaign_id)
        self.rules_profile = data.get("rules_profile", self.rules_profile)
        self.campaign_meta = data.get("campaign_meta", {})
        self.aliases = data.get("aliases", {})
        self._turn_count = data.get("turn_count", 0)
        self._entity_counter = data.get("entity_counter", 0)

        self.entities = {}
        for eid, ed in data.get("entities", {}).items():
            self.entities[eid] = Entity.from_dict(ed)

        return self

    def migrate(self, data: dict) -> dict:
        """Apply schema migrations if needed."""
        version = data.get("schema_version", 1)
        # Currently only version 1 exists
        # Future: if version < 2: apply migration; version = 2; etc.
        return data

    # --- Turn log persistence (append-only JSONL) ---

    def append_turn_record(self, record: TurnRecord) -> None:
        """Append a turn record to the JSONL log (never rewritten)."""
        self.turn_log.append(record)
        self._turn_count = record.turn

        log_path = self.data_dir / f"turns_{self.campaign_id}.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(record.to_dict() if hasattr(record, 'to_dict') else asdict(record),
                               default=str) + "\n")

    # --- Context assembly (simplified for v0.4c — full version is v0.5a) ---

    # --- Working-set scoring (spec §6) ---

    SCORE_WEIGHTS = {
        "pinned": 100,            # PC, active-quest entities, current location
        "present_in_scene": 50,
        "named_in_player_input": 40,
        "named_in_last_narration": 30,
        "one_graph_hop": 20,       # via Link
        "linked_to_active_quest": 15,
        "recency_max": 10,          # decays with (current_turn - last_seen_turn)
    }

    def _score_entity(self, entity: Entity, player_input: str,
                      last_narration: str, current_turn: int,
                      pinned_ids: set, scene: Scene = None) -> int:
        """Score an entity for working-set inclusion (spec §6)."""
        score = 0
        norm_input = player_input.lower()
        norm_narr = last_narration.lower()

        if entity.id in pinned_ids:
            score += self.SCORE_WEIGHTS["pinned"]

        if scene and entity.id in scene.present_entity_ids:
            score += self.SCORE_WEIGHTS["present_in_scene"]

        if entity.name.lower() in norm_input or entity.norm_name in norm_input:
            score += self.SCORE_WEIGHTS["named_in_player_input"]

        if entity.name.lower() in norm_narr or entity.norm_name in norm_narr:
            score += self.SCORE_WEIGHTS["named_in_last_narration"]

        # One graph hop: linked to a pinned entity
        for link in entity.links:
            if link.target_id in pinned_ids:
                score += self.SCORE_WEIGHTS["one_graph_hop"]
                break

        # Linked to active quest
        for e in self.entities.values():
            if e.type == "quest" and e.attributes.get("status") == "active":
                for link in e.links:
                    if link.target_id == entity.id:
                        score += self.SCORE_WEIGHTS["linked_to_active_quest"]
                        break

        # Recency (decays)
        turns_away = max(0, current_turn - entity.last_seen_turn)
        recency = max(0, self.SCORE_WEIGHTS["recency_max"] - turns_away)
        score += recency

        return score

    def get_context_for_turn(self, player_input: str = "",
                             budget: TokenBudget = None,
                             current_scene: Scene = None,
                             last_narration: str = "",
                             system_prompt: str = "",
                             rules_text: str = "",
                             recent_turns: list = None) -> ContextBundle:
        """Assemble context for the LLM using layered assembly (spec §6).

        STABLE PREFIX (cacheable — byte-identical across turns when content allows):
          L0  system prompt
          L1  campaign_meta
          L2  world directory (id | name | type | summary per entity)
          L3  pinned entities, full records (PC, active quests, current location)

        VOLATILE SUFFIX (never cached):
          L4  working set: full records for scored-in entities
          L5  scene block
          L6  "since you were last here" digest
          L7  last N turns verbatim + rolling chronicle
          L8  just-in-time rules
          L9  player action + resolved roll facts
        """
        budget = budget or TokenBudget()
        scene = current_scene or self.current_scene
        current_turn = self._turn_count + 1
        recent_turns = recent_turns or []

        included = []
        dropped = []

        # Determine pinned entities (score >= 100 unconditional)
        pinned_ids = set()
        pc = self._get_pc()
        if pc:
            pinned_ids.add(pc.id)
        if scene:
            pinned_ids.add(scene.location_id)
        for e in self.entities.values():
            if e.type == "quest" and e.attributes.get("status") == "active":
                pinned_ids.add(e.id)

        # --- STABLE PREFIX ---

        # L0: System prompt
        l0 = system_prompt[:budget.l0_system] if system_prompt else ""

        # L1: Campaign meta
        meta_lines = []
        for k, v in self.campaign_meta.items():
            meta_lines.append(f"  {k}: {v}")
        l1 = "\n".join(meta_lines)[:budget.l1_campaign_meta]

        # L2: World directory (compact: id | name | type | summary)
        dir_entries = []
        for eid, entity in sorted(self.entities.items(),
                                   key=lambda x: x[1].last_seen_turn, reverse=True):
            entry = f"{eid} | {entity.name} | {entity.type} | {entity.summary[:60]}"
            dir_entries.append(entry)
        l2 = "\n".join(dir_entries)[:budget.l2_directory]

        # L3: Pinned entities, full records
        pinned_lines = []
        for eid in pinned_ids:
            entity = self.entities.get(eid)
            if entity:
                pinned_lines.append(self._entity_to_context_str(entity, mark="[KNOWN]"))
                included.append(eid)
        l3 = "\n".join(pinned_lines)[:budget.l3_pinned]

        stable_prefix = "\n".join(filter(None, [l0, l1, l2, l3]))

        # --- VOLATILE SUFFIX ---

        # L4: Working set — score all non-pinned entities, fill budget
        scored = []
        for eid, entity in self.entities.items():
            if eid in pinned_ids:
                continue
            score = self._score_entity(
                entity, player_input, last_narration, current_turn,
                pinned_ids, scene)
            if score > 0:
                scored.append((score, eid, entity))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Take everything scoring >= 100 unconditionally; fill by score descending
        working_set_lines = []
        working_set_budget = budget.l4_working_set
        for score, eid, entity in scored:
            entry = self._entity_to_context_str(entity, mark="[KNOWN]" if score >= 50 else "[NEW]")
            if len("\n".join(working_set_lines + [entry])) <= working_set_budget:
                working_set_lines.append(entry)
                included.append(eid)
            else:
                dropped.append(eid)

        l4 = "\n".join(working_set_lines)

        # L5: Scene block
        scene_lines = []
        if scene:
            loc = self.entities.get(scene.location_id)
            if loc:
                scene_lines.append(f"Location: {loc.name}")
            scene_lines.append(f"Present: {', '.join(
                self.entities[eid].name for eid in scene.present_entity_ids
                if eid in self.entities)}")
            if scene.encounter:
                scene_lines.append(f"Round: {scene.encounter.round}")
            scene_lines.append(f"Light: {scene.light}, Time: {scene.time_of_day}")
        l5 = "\n".join(scene_lines)[:budget.l5_scene]

        # L6: "Since you were last here" digest
        l6 = ""  # Generated by enter_scene() — stored in campaign_meta temporarily
        digest = self.campaign_meta.pop("_last_digest", "")
        if digest:
            l6 = digest[:budget.l6_digest]

        # L7: Last N turns verbatim
        turn_lines = []
        for tr in recent_turns[-10:]:  # last 10 turns
            if isinstance(tr, dict):
                turn_lines.append(f"Turn {tr.get('turn', '?')}: {tr.get('player_input', '')} -> {tr.get('narrative', '')[:100]}")
            elif isinstance(tr, str):
                turn_lines.append(tr)
        l7 = "\n".join(turn_lines)[:budget.l7_recent_turns]

        # L8: Just-in-time rules
        l8 = rules_text[:budget.l8_rules] if rules_text else ""

        # L9: Player action
        l9 = f"PLAYER ACTION:\n{player_input}"[:budget.l9_input] if player_input else ""

        volatile_suffix = "\n".join(filter(None, [l4, l5, l6, l7, l8, l9]))

        return ContextBundle(
            stable_prefix=stable_prefix,
            volatile_suffix=volatile_suffix,
            included_entity_ids=included,
            dropped_entity_ids=dropped,
        )

    def _entity_to_context_str(self, entity: Entity, mark: str = "") -> str:
        """Format an entity for context inclusion."""
        lines = []
        marker = f"{mark} " if mark else ""
        lines.append(f"{marker}{entity.type.upper()}: {entity.name}")
        if entity.summary:
            lines.append(f"  Summary: {entity.summary}")
        # Key attributes
        for key in ("hp", "max_hp", "ac", "disposition", "status"):
            if key in entity.attributes:
                lines.append(f"  {key}: {entity.attributes[key]}")
        if not entity.alive:
            lines.append("  [DEAD]")
        return "\n".join(lines)

    # --- Directory (for context assembler L2) ---

    def get_directory(self) -> list[str]:
        """Return a compact directory of all entities: id | name | type | summary"""
        lines = []
        for eid, entity in self.entities.items():
            lines.append(f"{eid} | {entity.name} | {entity.type} | {entity.summary[:60]}")
        return lines
