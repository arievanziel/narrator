"""Narrator v0.1 — DM Engine.

The DM brain generates story text in a format that serves BOTH display and audio:
[STORY] section contains line-by-line content where each line is either:
  [narrator] narration text
  [CharName] "dialogue text"
This is the EXACT text shown on screen and spoken by TTS — word for word.

Other sections: [MECHANICS], [SUGGESTIONS], [CHRONICLE], [SCENE]
"""
import re
import time
import os
from dataclasses import dataclass, field
from openai import OpenAI

from . import config


# ---------------------------------------------------------------------------
# System prompt — the rules contract + story format
# ---------------------------------------------------------------------------

PROMPT_VERSION = "v10"

SYSTEM_PROMPT = """\
You are an expert D&D 5e Dungeon Master running a solo campaign for one player.

## STORY FORMAT (critical — this is what the player sees AND hears)

Every response MUST contain exactly these sections, each on a new line with the
section tag in brackets:

[SCENE]
One word describing the mood: combat, tense, horror, mystery, exploration, tavern, \
emotional, sad, victory, dungeon, calm. This drives background music selection.

[STORY]
The narration — this is EXACTLY what the player reads on screen and what the TTS \
engine speaks. Word for word. Format each line as one of:
  [narrator] narration text here
  [CharacterName] "dialogue text here"

Rules for [STORY]:
- Each [narrator] line is 1-3 sentences of narration
- Each [CharacterName] line is dialogue in quotes
- The story should flow naturally — narrator sets scenes, characters speak
- 4-8 lines total per turn (not too long, not too short)
- Do NOT include mechanics, dice results, or meta-text in the story
- The story text is what gets spoken aloud — keep it natural and vivid

[MECHANICS]
Machine-readable tags only, one per line. Use ONLY these tags:
  HP_CHANGE:<signed_int>          (negative = damage to PC, positive = healing)
  ENEMY_HP:<name>,<current>/<max>  (update an enemy's HP — only after a roll)
  ENEMY_DEAD:<name>                (mark an enemy as dead — only after a roll)
  ROLL_REQUEST:<dice> for <skill> DC <number>  (set DC, request a roll — do NOT narrate the outcome yet)
  ITEM_USED:<name>                 (consume an item from inventory)
  ITEM_GAINED:<name>               (add an item to inventory)
  CONDITION:<target>,<condition>   (apply a condition)
  ENTITY_NEW:<type>,<name>,<summary>  (introduce a new NPC/location/item/faction/quest)
  ENTITY_UPDATE:<name>,<field>,<value>  (update an entity's field — writes a revision)
  ALIAS:<alt name> -> <canonical name>  (record an alias for entity matching)
  QUEST_UPDATE:<name>,<status>     (update quest status: active/completed/failed)
  NO_MECHANICS                     (use when no mechanical change this turn)

[SUGGESTIONS]
3-4 player options for the next action, each on its own line, tagged:
  - <option text> [roll:true]   (requires a dice roll)
  - <option text> [roll:false]  (narrative/social, no roll needed)

[CHRONICLE]
One-line campaign log entry. Use "NO_ENTRY" for uneventful turns.

## RULES CONTRACT

1. DC-FIRST ROLLS. When an action requires a roll, you MUST:
   (a) Narrate the setup and tension of the moment.
   (b) Emit ROLL_REQUEST:<dice> for <skill> DC <number> with a specific DC.
   (c) STOP — do NOT narrate the outcome. The system will roll and tell you the result.
   (d) In a follow-up, narrate ONLY the consequence of the already-decided result.
   Never narrate a combat result, success, or failure before the dice are rolled.
   Never decide the outcome yourself — the roll decides, not you.

2. STATE IS AUTHORITATIVE. The game state provided in each turn is the source of \
truth. Do not contradict it. Do not invent items, HP, conditions, or NPCs not \
listed in the state.

3. BE THE DM, NOT A PLAYER. You control NPCs, monsters, and the world. The player \
controls only their character. Never act for the player.

4. ENCOUNTER BALANCE. Solo play — no party backup. Level 1 enemies: max 7 HP, \
no multiattack. A single bad roll should not end the run.

5. When the system provides a roll result (SUCCESS or FAILURE with a specific \
number), you MUST accept it. You cannot change whether it succeeded. Narrate \
the consequence and apply appropriate [MECHANICS] based on the result.

6. PROCEDURAL WORLD. Generate NPCs, locations, and encounters that fit the \
story style and setting. NEVER reuse a fixed scenario. Every NPC, location, \
and item should be unique to this campaign. Use ENTITY_NEW to introduce new \
entities as they appear in the story. Refer to entities by NAME only — never \
invent or emit ID strings.

7. KNOWN/NEW ENTITIES. Entities marked [KNOWN] in your context have already \
been met. Do not re-introduce them as if new. Use ENTITY_NEW only for genuinely \
new entities.

8. RECALL. If you need to reference an entity not in your context, emit \
RECALL:<name> as a mechanics tag. The system will look it up and provide its \
full record in the next turn. Use this sparingly — it costs one re-run.
"""


# ---------------------------------------------------------------------------
# Session Zero — conversational onboarding wizard
# ---------------------------------------------------------------------------

SESSION_ZERO_SYSTEM_PROMPT = """\
You are a Dungeon Master conducting a "Session Zero" — a friendly, conversational \
onboarding before the real game begins. You are talking WITH the player to collaboratively \
design the campaign they want to play.

## YOUR VOICE
Warm, welcoming, and genuinely curious — like a friend who loves tabletop RPGs \
helping another friend set up their first campaign. You're excited to tailor this \
experience to what THEY find fun. Not a form, not a questionnaire — a real conversation.

## RESPONSE FORMAT (use exactly these sections, each on a new line)

[NARRATIVE]
Your spoken words to the player — in character as the DM, conversational and warm. \
Ask ONE question at a time (don't dump a list). React to their previous answer before \
asking the next thing. 2-4 sentences. This is what gets displayed and spoken via TTS.

[TOPIC]
A single word identifying which setup topic this turn addresses. One of: \
greeting, style, setting, character, persona, tone, pacing, dice, content, done

[SUGGESTIONS]
2-4 example answers the player could pick, each on its own line starting with "- ". \
These are starting points, not limits — the player can always type their own answer. \
Keep them evocative and specific, not generic.

[DONE]
true or false — set to true ONLY when you have gathered enough to start the game. \
Typically this takes 5-8 turns. Don't rush — but don't drag it out either. When done, \
use [NARRATIVE] to give a brief, warm "let's begin" send-off.

## TOPICS TO COVER (in a natural conversational order)
1. Greeting — welcome them, ask their character's name
2. Style — what kind of story? (heroic fantasy, dark grimdark, mystery, etc.)
3. Setting — what kind of world? (let them describe or pick a flavor)
4. Character — who is their character? (persona, background, what drives them)
5. Tone — what atmosphere? (lighthearted, tense, melancholic, whimsical)
6. Pacing — combat-heavy, roleplay-heavy, or balanced?
7. Dice — do they want to roll their own dice, or have the app handle it?
8. Content — any topics to avoid? (optional, skip if they seem uninterested)

You don't need to hit every topic if the player's answers already cover it. \
Adapt — if they say "dark fantasy" in their first answer, don't ask about style again. \
Be a real person, not a checklist.

## IMPORTANT
- React to what they say before moving on. "Oh, a grizzled veteran — I love that. \
So what kind of world does this veteran find themselves in?"
- Keep suggestions short and punchy — they're inspiration, not an exam.
- When you set [DONE] to true, the game starts immediately after.
- Never ask more than one question per turn.
"""


def parse_session_zero_response(text: str) -> dict:
    """Parse a Session Zero DM response into sections.

    Returns dict with keys: narrative, topic, suggestions, done.
    """
    # Strip thinking blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    sections = {"narrative": "", "topic": "", "suggestions": [], "done": False}

    tags = ["NARRATIVE", "TOPIC", "SUGGESTIONS", "DONE"]
    raw = {}
    for tag in tags:
        pattern = rf"\*{{0,2}}\[{tag}\]\*{{0,2}}\s*(.*?)(?=\*{{0,2}}\[(?:{'|'.join(tags)})\]|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            raw[tag] = match.group(1).strip()

    sections["narrative"] = raw.get("NARRATIVE", "")
    sections["topic"] = raw.get("TOPIC", "").lower().strip()

    # Parse suggestions — lines starting with - or bullet
    sug_text = raw.get("SUGGESTIONS", "")
    for line in sug_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove leading dash or bullet
        clean = re.sub(r"^[-\u2022]\s*", "", line).strip()
        if clean:
            sections["suggestions"].append(clean)

    # Parse done flag
    done_text = raw.get("DONE", "").lower().strip()
    sections["done"] = done_text in ("true", "yes", "1")

    return sections


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------

@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    ac: int

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def to_dict(self):
        return {"name": self.name, "hp": self.hp, "max_hp": self.max_hp,
                "ac": self.ac, "alive": self.alive}


@dataclass
class GameState:
    """Game state — the authoritative state model.

    v0.4d: Now supports an optional WorldStore backend. When ``world_store``
    is set, ``apply_mechanics`` delegates to the store's
    ``apply_turn_mechanics``, and the flat attributes (pc_hp, inventory,
    enemies, etc.) are synced from the store after each mechanics application.

    This is the strangler-fig facade: the external interface (attributes,
    to_dict, to_prompt_block, apply_mechanics) stays identical, but the
    authoritative storage gradually moves to the WorldStore. Existing call
    sites in game_loop.py and app.py work unmodified.
    """
    pc_name: str = "Kael"
    pc_class: str = "Fighter"
    pc_level: int = 1
    pc_hp: int = 12
    pc_max_hp: int = 12
    pc_ac: int = 16
    pc_str: int = 16
    pc_dex: int = 12
    pc_con: int = 14
    pc_int: int = 10
    pc_wis: int = 10
    pc_cha: int = 10
    inventory: list = field(default_factory=lambda: [
        "Health Potion", "Torch", "Waterskin", "50 feet of rope",
    ])
    equipment: str = "longsword (1d8+3 slashing), shield, chain mail"
    enemies: list = field(default_factory=list)
    location: str = "The Rusty Anchor tavern"
    light: str = "dim (candlelit)"
    time: str = "evening"
    chronicle: list = field(default_factory=list)
    # Story style settings (from intro screen)
    story_style: str = ""
    setting: str = ""
    persona: str = ""
    atmosphere: str = ""
    inspiration: str = ""
    auto_roll: bool = True  # auto-roll dice for player
    # v0.4d: optional WorldStore backend (strangler-fig facade)
    world_store: object = None  # WorldStore or None
    _turn_counter: int = 0

    def attach_world_store(self, store) -> None:
        """Attach a WorldStore and sync state from it."""
        self.world_store = store
        self._sync_from_store()

    def _sync_from_store(self) -> None:
        """Sync flat attributes from the WorldStore's PC entity."""
        if not self.world_store:
            return
        pc = self.world_store._get_pc()
        if pc:
            self.pc_hp = pc.attributes.get("hp", self.pc_hp)
            self.pc_max_hp = pc.attributes.get("max_hp", self.pc_max_hp)
            # Inventory: convert entity IDs back to names for legacy compat
            inv_ids = pc.attributes.get("inventory", [])
            inv_names = []
            for iid in inv_ids:
                if isinstance(iid, str) and iid in self.world_store.entities:
                    inv_names.append(self.world_store.entities[iid].name)
                elif isinstance(iid, str):
                    inv_names.append(iid)  # already a name (legacy)
            self.inventory = inv_names

        # Sync enemies from store's NPC entities
        store_enemies = []
        for entity in self.world_store.entities.values():
            if entity.type == "npc" and entity.alive:
                store_enemies.append(Enemy(
                    name=entity.name,
                    hp=entity.attributes.get("hp", 0),
                    max_hp=entity.attributes.get("max_hp", 0),
                    ac=entity.attributes.get("ac", 10),
                ))
        if store_enemies:
            self.enemies = store_enemies

    def _sync_to_store(self) -> None:
        """Sync flat attributes to the WorldStore's PC entity."""
        if not self.world_store:
            return
        pc = self.world_store._get_pc()
        if not pc:
            # Create PC entity in store if it doesn't exist
            pc, _, _ = self.world_store.resolve_or_create(
                self.pc_name, "pc",
                {"hp": self.pc_hp, "max_hp": self.pc_max_hp,
                 "disposition": "friendly", "voice_description": "player",
                 "inventory": list(self.inventory), "stats": {
                     "STR": self.pc_str, "DEX": self.pc_dex, "CON": self.pc_con,
                     "INT": self.pc_int, "WIS": self.pc_wis, "CHA": self.pc_cha,
                 }},
                current_turn=self._turn_counter,
            )
        else:
            pc.attributes["hp"] = self.pc_hp
            pc.attributes["max_hp"] = self.pc_max_hp
            pc.attributes["inventory"] = list(self.inventory)

        # Sync enemies to store
        for enemy in self.enemies:
            entity, created, _ = self.world_store.resolve_or_create(
                enemy.name, "npc",
                {"hp": enemy.hp, "max_hp": enemy.max_hp, "ac": enemy.ac,
                 "disposition": "hostile", "voice_description": "enemy"},
                current_turn=self._turn_counter,
            )
            entity.attributes["hp"] = enemy.hp
            entity.attributes["max_hp"] = enemy.max_hp
            if not enemy.alive:
                entity.alive = False

    def to_prompt_block(self) -> str:
        enemies_str = "\n  ".join(str(e) for e in self.enemies) if self.enemies else "None"
        inv_str = ", ".join(self.inventory) if self.inventory else "Empty"
        style_block = ""
        if self.story_style or self.setting or self.persona:
            style_block = f"""
STORY STYLE (follow this tone and setting):
  Style: {self.story_style or "classic fantasy"}
  Setting: {self.setting or "medieval fantasy world"}
  Character persona: {self.persona or "a brave adventurer"}
  Atmosphere: {self.atmosphere or "adventurous"}
  Inspiration: {self.inspiration or "none specified"}
  Dice mode: {"AUTO-ROLL (you roll for the player)" if self.auto_roll else "MANUAL (player rolls dice)"}
"""
        return f"""\
CURRENT GAME STATE (authoritative — do not contradict):
  PC: {self.pc_name}, Level {self.pc_level} {self.pc_class} | HP: {self.pc_hp}/{self.pc_max_hp} | AC: {self.pc_ac}
  STR {self.pc_str} | DEX {self.pc_dex} | CON {self.pc_con} | INT {self.pc_int} | WIS {self.pc_wis} | CHA {self.pc_cha}
  Inventory: {inv_str}
  Equipment: {self.equipment}
  Enemies:
  {enemies_str}
  Scene: {self.location} | Light: {self.light} | Time: {self.time}{style_block}"""

    def to_dict(self) -> dict:
        return {
            "pc_name": self.pc_name, "pc_class": self.pc_class,
            "pc_level": self.pc_level, "pc_hp": self.pc_hp,
            "pc_max_hp": self.pc_max_hp, "pc_ac": self.pc_ac,
            "pc_str": self.pc_str, "pc_dex": self.pc_dex, "pc_con": self.pc_con,
            "pc_int": self.pc_int, "pc_wis": self.pc_wis, "pc_cha": self.pc_cha,
            "inventory": list(self.inventory), "equipment": self.equipment,
            "enemies": [e.to_dict() for e in self.enemies],
            "location": self.location, "light": self.light, "time": self.time,
            "chronicle": self.chronicle, "auto_roll": self.auto_roll,
        }

    def apply_mechanics(self, mechanics_text: str) -> list:
        """Parse [MECHANICS] tags and apply them deterministically. Returns log of changes.

        v0.4d: If a WorldStore is attached, delegates to
        ``world_store.apply_turn_mechanics`` and syncs the flat attributes
        from the store afterward. Otherwise, uses the legacy flat-state logic.

        Includes anti-cheat safeguards:
        - Waste-potion guard: if any ITEM_USED names an item NOT in inventory, skip ALL
          ITEM_USED tags that turn.
        - Control-NPC guard: ENEMY_DEAD / ENEMY_HP to 0 only applied if roll evidence
          exists for that specific enemy in the same turn. Roll evidence is scoped by
          enemy name appearing in the ROLL_REQUEST text or an ENEMY_HP tag for that enemy.
        """
        # v0.4d: delegate to WorldStore if attached
        if self.world_store is not None:
            self._turn_counter += 1
            # Sync current state to store before applying
            self._sync_to_store()
            # Parse mechanics text into tag list
            lines = [l.strip() for l in mechanics_text.strip().split("\n")
                     if l.strip() and l.strip() != "NO_MECHANICS"]
            changes = self.world_store.apply_turn_mechanics(
                lines, current_turn=self._turn_counter)
            # Sync back from store
            self._sync_from_store()
            return changes

        # Legacy flat-state path (no WorldStore attached)
        changes = []
        lines = [l.strip() for l in mechanics_text.strip().split("\n")
                 if l.strip() and l.strip() != "NO_MECHANICS"]

        # Pre-scan
        item_used_invalid = False
        roll_request_texts = []
        enemy_hp_targets = set()

        for line in lines:
            if ":" not in line:
                continue
            tag, val = line.split(":", 1)
            tag = tag.strip().upper()
            val = val.strip()
            if tag == "ITEM_USED":
                if val.strip() not in self.inventory:
                    item_used_invalid = True
            elif tag == "ROLL_REQUEST":
                # Collect roll request text so we can scope evidence to named enemies.
                roll_request_texts.append(val.lower())
            elif tag == "ENEMY_HP":
                parts = val.split(",")
                if len(parts) >= 1:
                    enemy_hp_targets.add(parts[0].strip().lower())

        # Build set of enemies with roll evidence in this turn.
        # An enemy has roll evidence if a ROLL_REQUEST exists and either:
        # (a) the enemy is the target of an ENEMY_HP tag in the same turn, or
        # (b) the enemy name appears in any ROLL_REQUEST text.
        has_roll_request = bool(roll_request_texts)
        enemies_with_roll_evidence = set()
        if has_roll_request:
            all_names = {e.name.lower() for e in self.enemies}
            all_names.update(enemy_hp_targets)
            for name in all_names:
                if name in enemy_hp_targets:
                    enemies_with_roll_evidence.add(name)
                    continue
                for roll_text in roll_request_texts:
                    if name in roll_text:
                        enemies_with_roll_evidence.add(name)
                        break

        # Apply
        for line in lines:
            if ":" not in line:
                changes.append(f"[unparseable] {line}")
                continue
            tag, val = line.split(":", 1)
            tag = tag.strip().upper()
            val = val.strip()

            if tag == "HP_CHANGE":
                try:
                    amt = int(val)
                    old_hp = self.pc_hp
                    self.pc_hp = max(0, min(self.pc_max_hp, self.pc_hp + amt))
                    changes.append(f"HP: {old_hp} → {self.pc_hp} ({'+' if amt >= 0 else ''}{amt})")
                except ValueError:
                    pass

            elif tag == "ENEMY_HP":
                parts = val.split(",")
                if len(parts) == 2:
                    name = parts[0].strip()
                    hp_parts = parts[1].strip().split("/")
                    if len(hp_parts) == 2:
                        for e in self.enemies:
                            if e.name.lower() == name.lower():
                                try:
                                    new_hp = max(0, int(hp_parts[0]))
                                    # Guard: setting HP to 0 without roll evidence
                                    # is effectively killing the enemy — reject it
                                    if new_hp == 0 and name.lower() not in enemies_with_roll_evidence:
                                        changes.append(f"[REJECTED — no roll evidence] {e.name} HP→0")
                                        continue
                                    e.hp = new_hp
                                    changes.append(f"{e.name} HP → {e.hp}/{e.max_hp}")
                                except ValueError:
                                    pass
                                break

            elif tag == "ENEMY_DEAD":
                name = val.strip()
                if name.lower() not in enemies_with_roll_evidence:
                    changes.append(f"[REJECTED — no roll evidence] {name}")
                    continue
                for e in self.enemies:
                    if e.name.lower() == name.lower() and e.alive:
                        e.hp = 0
                        changes.append(f"{e.name} DEAD")
                        break

            elif tag == "ITEM_USED":
                item = val.strip()
                if item_used_invalid:
                    if item in self.inventory:
                        changes.append(f"[REJECTED — invalid item in same turn] {item}")
                elif item in self.inventory:
                    self.inventory.remove(item)
                    changes.append(f"Used: {item}")

            elif tag == "ITEM_GAINED":
                self.inventory.append(val.strip())
                changes.append(f"Gained: {val.strip()}")

            elif tag == "CONDITION":
                changes.append(f"Condition: {val}")

            elif tag == "ROLL_REQUEST":
                changes.append(f"Roll requested: {val}")

        return changes


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def parse_response(text: str) -> dict:
    """Extract sections from the LLM response.

    Handles both the new format ([STORY]) and legacy format ([NARRATIVE]/[AUDIO]).
    If [STORY] is empty but [NARRATIVE] exists, use NARRATIVE.
    If [AUDIO] section exists with [narrator]/[CharName] tags, extract segments from there.
    """
    # Strip thinking blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    # All possible section tags (including legacy ones)
    all_tags = ["SCENE", "STORY", "NARRATIVE", "MECHANICS", "SUGGESTIONS",
                "CHRONICLE", "AUDIO"]
    raw_sections = {}
    for tag in all_tags:
        pattern = rf"\*{{0,2}}\[{tag}\]\*{{0,2}}\s*(.*?)(?=\*{{0,2}}\[(?:{'|'.join(all_tags)})\]|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            raw_sections[tag] = match.group(1).strip()

    # Build normalized sections
    sections = {
        "SCENE": raw_sections.get("SCENE", ""),
        "STORY": raw_sections.get("STORY", "") or raw_sections.get("NARRATIVE", ""),
        "MECHANICS": raw_sections.get("MECHANICS", ""),
        "SUGGESTIONS": raw_sections.get("SUGGESTIONS", ""),
        "CHRONICLE": raw_sections.get("CHRONICLE", ""),
        "AUDIO": raw_sections.get("AUDIO", ""),
    }

    # Extract scene mood from [SCENE: mood] tag in AUDIO section if SCENE is empty
    if not sections["SCENE"] and sections["AUDIO"]:
        scene_match = re.search(r"\[SCENE:\s*(\w+)\]", sections["AUDIO"])
        if scene_match:
            sections["SCENE"] = scene_match.group(1)

    return sections


def parse_story(story_text: str, audio_text: str = "") -> list:
    """Parse [STORY] section into segments for display and TTS.

    If the STORY section is in prose (no [narrator] tags), but an AUDIO section
    exists with tagged lines, use the AUDIO section instead — it has the
    word-for-word format needed for TTS.

    Returns list of dicts: {kind: 'narrator'|'dialogue', speaker: str, text: str}
    """
    # Check if story_text has tagged lines
    has_tags = bool(re.search(r"\[(narrator|[A-Z])", story_text, re.IGNORECASE))

    # If no tags in STORY but AUDIO has them, use AUDIO
    if not has_tags and audio_text:
        audio_has_tags = bool(re.search(r"\[(narrator|[A-Z])", audio_text, re.IGNORECASE))
        if audio_has_tags:
            story_text = audio_text

    segments = []
    for line in story_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Skip SFX and SCENE tags
        if re.match(r"\[(SFX|SCENE)[^]]*\]", line, re.IGNORECASE):
            continue
        # Match [narrator] text or [CharName] "dialogue"
        m = re.match(r"\[([^\]]+)\]\s*(.*)", line)
        if m:
            speaker = m.group(1).strip()
            text = m.group(2).strip()
            if speaker.lower() == "narrator":
                segments.append({"kind": "narrator", "speaker": "narrator", "text": text})
            else:
                # Strip quotes from dialogue
                text = text.strip('"').strip('"').strip('"')
                segments.append({"kind": "dialogue", "speaker": speaker, "text": text})
        else:
            # Unformatted prose line — treat as narrator
            segments.append({"kind": "narrator", "speaker": "narrator", "text": line})
    return segments


def parse_suggestions(suggestions_text: str) -> list:
    """Parse [SUGGESTIONS] into list of {text, roll}."""
    suggestions = []
    for line in suggestions_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        roll_match = re.search(r"\[roll:(true|false)\]", line)
        roll = roll_match.group(1) == "true" if roll_match else False
        text = re.sub(r"\[roll:(true|false)\]", "", line).replace("•", "").replace("-", "", 1).strip()
        if text:
            suggestions.append({"text": text, "roll": roll})
    return suggestions


# ---------------------------------------------------------------------------
# API client and DM turn
# ---------------------------------------------------------------------------

def make_client(provider: str) -> OpenAI:
    cfg = config.PROVIDERS[provider]
    api_key = os.environ.get(cfg["env_var"])
    if not api_key or api_key.startswith("your_") or api_key.endswith("_here"):
        raise ValueError(f"{cfg['env_var']} not set. Check .env file.")
    return OpenAI(api_key=api_key, base_url=cfg["base_url"])


def detect_provider(model: str) -> str:
    """Auto-detect provider from model name."""
    if model.startswith("gemini-"):
        return "gemini"
    if model.startswith("claude-"):
        return "anthropic"
    if "/" in model:  # groq models like openai/gpt-oss-120b
        return "groq"
    return config.DEFAULT_PROVIDER


# ---------------------------------------------------------------------------
# Dice rolling — deterministic, loggable, no LLM involvement
# ---------------------------------------------------------------------------

import random as _random

def roll_dice(spec: str) -> int:
    """Roll dice from a specification like 'd20', '1d8+3', '2d6', 'd20+5'.

    Returns the total. Uses a module-level Random instance for reproducibility
    in tests (seed via set_dice_seed).
    """
    spec = spec.strip().lower().replace(" ", "")
    # Parse: [count]d[sides][+/-modifier]
    m = re.match(r"(\d*)d(\d+)([+-]\d+)?", spec)
    if not m:
        return 0
    count = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    modifier = int(m.group(3)) if m.group(3) else 0
    total = sum(_dice_rng.randint(1, sides) for _ in range(count))
    return total + modifier


_dice_rng = _random.Random()


def set_dice_seed(seed: int) -> None:
    """Seed the dice RNG for reproducible tests."""
    _dice_rng.seed(seed)


def parse_roll_request(mechanics_text: str) -> dict | None:
    """Extract a ROLL_REQUEST from mechanics text.

    Looks for: ROLL_REQUEST:<dice> for <skill> DC <number>
    or: ROLL_REQUEST:<dice> for <skill>

    Returns: {dice, skill, dc} or None if no roll request found.
    """
    for line in mechanics_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("ROLL_REQUEST:"):
            val = line.split(":", 1)[1].strip()
            # Parse: "d20+5 for attack with longsword DC 12"
            # or: "d20 for attack"
            dc = None
            dc_match = re.search(r"DC\s*(\d+)", val, re.IGNORECASE)
            if dc_match:
                dc = int(dc_match.group(1))
                val = re.sub(r"\s*DC\s*\d+", "", val, flags=re.IGNORECASE).strip()
            # Split dice and skill
            parts = val.split(" for ", 1)
            dice = parts[0].strip()
            skill = parts[1].strip() if len(parts) > 1 else "unknown"
            return {"dice": dice, "skill": skill, "dc": dc}
    return None


def resolve_roll(roll_request: dict, manual_roll: int | None = None) -> dict:
    """Resolve a roll request deterministically.

    If manual_roll is provided, use it (player rolled manually).
    Otherwise, auto-roll using roll_dice().

    Returns: {dice, skill, dc, roll, result, margin}
    """
    dice = roll_request["dice"]
    dc = roll_request.get("dc")
    skill = roll_request["skill"]

    if manual_roll is not None:
        roll = manual_roll
    else:
        roll = roll_dice(dice)

    if dc is not None:
        result = "SUCCESS" if roll >= dc else "FAILURE"
        margin = roll - dc
    else:
        # No DC set — treat as a simple roll, no pass/fail
        result = "NO_DC"
        margin = 0

    return {
        "dice": dice,
        "skill": skill,
        "dc": dc,
        "roll": roll,
        "result": result,
        "margin": margin,
    }


def dm_turn(client: OpenAI, model: str, system_prompt: str,
            state_block: str, history: list, player_input: str,
            temperature: float = 0.8, max_tokens: int = 2000) -> tuple:
    """Call the LLM for one DM turn. Returns (response_text, elapsed_seconds, usage)."""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history[-10:])  # keep last 10 turns for context
    messages.append({
        "role": "user",
        "content": f"{state_block}\n\nPLAYER ACTION:\n{player_input}",
    })

    for attempt in range(3):
        try:
            t0 = time.time()
            response = client.chat.completions.create(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            elapsed = time.time() - t0
            text = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }
            return text, elapsed, usage
        except Exception as e:
            if attempt < 2 and ("429" in str(e) or "503" in str(e)):
                time.sleep((attempt + 1) * 5)
                continue
            raise


def dm_turn_dc_roll(client: OpenAI, model: str, system_prompt: str,
                     state_block: str, history: list, player_input: str,
                     auto_roll: bool = True, manual_roll: int | None = None,
                     temperature: float = 0.8, max_tokens: int = 2000) -> dict:
    """Two-phase DC-then-roll turn for contested actions.

    Phase 1: LLM narrates the setup and emits ROLL_REQUEST with a DC.
    Phase 2: Code resolves the roll deterministically.
    Phase 3: LLM narrates the consequence of the already-decided outcome.

    If the LLM's first response doesn't include a ROLL_REQUEST, this is a
    non-contested turn — return the single response with no roll.

    Returns: {
        phase1_text, phase1_sections, roll_result (or None),
        phase3_text (or None), phase3_sections (or None),
        sections (final sections to use), elapsed_total, usage_total
    }
    """
    # Phase 1: setup + DC setting
    text1, elapsed1, usage1 = dm_turn(
        client, model, system_prompt, state_block, history, player_input,
        temperature=temperature, max_tokens=max_tokens,
    )
    sections1 = parse_response(text1)

    # Check if a roll is needed
    roll_req = parse_roll_request(sections1["MECHANICS"])
    if not roll_req:
        # Non-contested turn — single phase
        return {
            "phase1_text": text1,
            "phase1_sections": sections1,
            "roll_result": None,
            "phase3_text": None,
            "phase3_sections": None,
            "sections": sections1,
            "elapsed_total": elapsed1,
            "usage_total": usage1,
            "contested": False,
        }

    # Phase 2: resolve the roll (pure code, no LLM)
    roll_result = resolve_roll(roll_req, manual_roll=manual_roll if not auto_roll else None)

    # Phase 3: LLM narrates the consequence
    outcome_prompt = (
        f"ROLL RESULT (deterministic — you cannot change this):\n"
        f"  Roll: {roll_result['roll']} on {roll_result['dice']}\n"
        f"  DC: {roll_result['dc']}\n"
        f"  Result: {roll_result['result']}\n"
        f"  Margin: {roll_result['margin']:+d}\n\n"
        f"Narrate the consequence of this outcome. The {'success' if roll_result['result'] == 'SUCCESS' else 'failure'} "
        f"is already decided — do not change it. Apply appropriate [MECHANICS] based on the result.\n\n"
        f"PLAYER ACTION (for context):\n{player_input}"
    )

    # Add phase 1 to history so the LLM knows what it already narrated
    history_with_phase1 = history + [
        {"role": "user", "content": player_input},
        {"role": "assistant", "content": text1},
    ]

    text3, elapsed3, usage3 = dm_turn(
        client, model, system_prompt, state_block, history_with_phase1,
        outcome_prompt,
        temperature=temperature, max_tokens=max_tokens,
    )
    sections3 = parse_response(text3)

    return {
        "phase1_text": text1,
        "phase1_sections": sections1,
        "roll_result": roll_result,
        "phase3_text": text3,
        "phase3_sections": sections3,
        "sections": sections3,  # final sections to use for display/audio
        "elapsed_total": elapsed1 + elapsed3,
        "usage_total": {
            "prompt_tokens": usage1["prompt_tokens"] + usage3["prompt_tokens"],
            "completion_tokens": usage1["completion_tokens"] + usage3["completion_tokens"],
        },
        "contested": True,
    }


def make_initial_state(story_style: str = "", setting: str = "",
                       persona: str = "", atmosphere: str = "",
                       inspiration: str = "", auto_roll: bool = True,
                       procedural: bool = False,
                       campaign_meta: dict = None) -> GameState:
    """Create initial game state with optional story style settings.

    v0.5c: When procedural=True, no hardcoded enemies are created. The opening
    narration from the LLM will propose entities via ENTITY_NEW tags, which
    the WorldStore will create dynamically. This kills the hardcoded two-goblin
    encounter that Arie specifically flagged.

    When procedural=False (default, for backward compat), the legacy hardcoded
    goblins are used. This preserves behavior for existing sessions.
    """
    if procedural:
        # Procedural mode: no hardcoded enemies or location
        # The LLM will generate everything via ENTITY_NEW tags
        state = GameState(
            enemies=[],  # empty — LLM will populate
            location="",  # empty — LLM will set via narration
            light="",
            time="",
            story_style=story_style, setting=setting, persona=persona,
            atmosphere=atmosphere, inspiration=inspiration, auto_roll=auto_roll,
        )
        if campaign_meta:
            # Apply campaign meta as story style if provided
            state.story_style = state.story_style or campaign_meta.get("style", "")
            state.setting = state.setting or campaign_meta.get("setting", "")
            state.persona = state.persona or campaign_meta.get("persona", "")
            state.atmosphere = state.atmosphere or campaign_meta.get("tone",
                                                                    campaign_meta.get("atmosphere", ""))
        return state

    # Legacy mode: hardcoded goblins (backward compat for existing sessions)
    state = GameState(
        enemies=[
            Enemy("Goblin Scout", hp=7, max_hp=7, ac=15),
            Enemy("Goblin Raider", hp=7, max_hp=7, ac=15),
        ],
        story_style=story_style, setting=setting, persona=persona,
        atmosphere=atmosphere, inspiration=inspiration, auto_roll=auto_roll,
    )
    return state
