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
  ENEMY_HP:<name>,<current>/<max>  (update an enemy's HP)
  ENEMY_DEAD:<name>                (mark an enemy as dead — only after a roll)
  ROLL_REQUEST:<dice> for <skill>  (ask the player to roll)
  ITEM_USED:<name>                 (consume an item from inventory)
  ITEM_GAINED:<name>               (add an item to inventory)
  CONDITION:<target>,<condition>   (apply a condition)
  NO_MECHANICS                     (use when no mechanical change this turn)

[SUGGESTIONS]
3-4 player options for the next action, each on its own line, tagged:
  - <option text> [roll:true]   (requires a dice roll)
  - <option text> [roll:false]  (narrative/social, no roll needed)

[CHRONICLE]
One-line campaign log entry. Use "NO_ENTRY" for uneventful turns.

## RULES CONTRACT

1. ROLLS BEFORE OUTCOMES. Never narrate a combat result before the dice are rolled.
   If the player hasn't provided a roll for an action that needs one, ask for it \
via ROLL_REQUEST.

2. STATE IS AUTHORITATIVE. The game state provided in each turn is the source of \
truth. Do not contradict it. Do not invent items, HP, conditions, or NPCs not \
listed in the state.

3. BE THE DM, NOT A PLAYER. You control NPCs, monsters, and the world. The player \
controls only their character. Never act for the player.

4. ENCOUNTER BALANCE. Solo play — no party backup. Level 1 enemies: max 7 HP, \
no multiattack. A single bad roll should not end the run.

5. When the player provides a roll result, incorporate it into the story and \
apply the appropriate mechanics. When in auto-roll mode, you roll for the player \
and include the result in the story narration.
"""


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

        Includes anti-cheat safeguards:
        - Waste-potion guard: if any ITEM_USED names an item NOT in inventory, skip ALL
          ITEM_USED tags that turn.
        - Control-NPC guard: ENEMY_DEAD only applied if roll evidence exists for that enemy.
        """
        changes = []
        lines = [l.strip() for l in mechanics_text.strip().split("\n")
                 if l.strip() and l.strip() != "NO_MECHANICS"]

        # Pre-scan
        item_used_invalid = False
        enemies_with_roll_evidence = set()

        for line in lines:
            if ":" not in line:
                continue
            tag, val = line.split(":", 1)
            tag = tag.strip().upper()
            val = val.strip()
            if tag == "ITEM_USED":
                if val.strip() not in self.inventory:
                    item_used_invalid = True
            elif tag == "ENEMY_HP":
                parts = val.split(",")
                if len(parts) == 2:
                    enemies_with_roll_evidence.add(parts[0].strip().lower())
            elif tag == "ROLL_REQUEST":
                for e in self.enemies:
                    enemies_with_roll_evidence.add(e.name.lower())

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
                                    e.hp = max(0, int(hp_parts[0]))
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


def make_initial_state(story_style: str = "", setting: str = "",
                       persona: str = "", atmosphere: str = "",
                       inspiration: str = "", auto_roll: bool = True) -> GameState:
    """Create initial game state with optional story style settings."""
    state = GameState(
        enemies=[
            Enemy("Goblin Scout", hp=7, max_hp=7, ac=15),
            Enemy("Goblin Raider", hp=7, max_hp=7, ac=15),
        ],
        story_style=story_style, setting=setting, persona=persona,
        atmosphere=atmosphere, inspiration=inspiration, auto_roll=auto_roll,
    )
    return state
