"""DM engine for Narrator v0.

Imports the proven GameState, Enemy, parse_response, and dm_turn from
test_api_dm.py and extends the system prompt with an [AUDIO] section for
the narration pipeline.

The [AUDIO] section gives the audio pipeline clean structured data:
  - [narrator] text            → narrator TTS segment
  - [CharName] "dialogue"      → character TTS segment
  - [SFX: key]                 → sound effect cue
  - [SCENE: mood]              → music track selection

The player still reads [NARRATIVE] (prose) in the GUI; [AUDIO] is machine-only.
"""
import sys
import os
from pathlib import Path

# Add glm-work/ to path so we can import from test_api_dm.py
GLM_WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GLM_WORK))

# Import proven components from test_api_dm.py
from test_api_dm import (
    GameState,
    Enemy,
    parse_response,
    dm_turn,
    make_client,
    PROVIDERS as TEST_API_PROVIDERS,
    make_initial_state as _make_initial_state_base,
)

from . import config


# ---------------------------------------------------------------------------
# Add to_dict() to GameState (it's missing from test_api_dm.py's version,
# but needed by the web server for JSON serialization)
# ---------------------------------------------------------------------------

def _game_state_to_dict(self) -> dict:
    """Serialize GameState to a dict for JSON responses."""
    return {
        "pc_name": self.pc_name,
        "pc_class": self.pc_class,
        "pc_level": self.pc_level,
        "pc_hp": self.pc_hp,
        "pc_max_hp": self.pc_max_hp,
        "pc_ac": self.pc_ac,
        "inventory": list(self.inventory),
        "enemies": [
            {"name": e.name, "hp": e.hp, "max_hp": e.max_hp, "ac": e.ac, "alive": e.alive}
            for e in self.enemies
        ],
        "location": self.location,
        "time": self.time,
    }

GameState.to_dict = _game_state_to_dict


# ---------------------------------------------------------------------------
# Extended system prompt — adds [AUDIO] section for the narration pipeline
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_V0 = """\
You are an expert D&D 5e Dungeon Master running a solo campaign for one player.

## RULES CONTRACT (follow strictly)

1. ROLLS BEFORE OUTCOMES. Never narrate a combat result before the dice are rolled.
   WRONG: "Your sword strikes true, dealing 8 damage!"
   CORRECT: Ask the player to roll, wait for the number, THEN narrate the outcome.
   If the player has not provided a roll for an action that needs one, ask for it.

2. STATE IS AUTHORITATIVE. The game state provided in each turn is the source of
   truth. Do not contradict it. Do not invent items, HP, conditions, or NPCs not
   listed in the state. If the player claims something not in the state, rule
   based on what is actually there.

3. RESPONSE FORMAT. Every response MUST contain exactly 5 sections, each on a new
   line with the section tag in brackets:

   [NARRATIVE]
   The story beat — 2 to 4 paragraphs. Vivid but not purple prose. Show the
   scene, NPC reactions, and consequences of the player's action. This is what
   the player reads.

   [MECHANICS]
   Machine-readable tags only, one per line. Use ONLY these tags:
     HP_CHANGE:<signed_int>          (negative = damage to PC, positive = healing)
     ENEMY_HP:<name>,<current>/<max>  (update an enemy's HP)
     ENEMY_DEAD:<name>                (mark an enemy as dead)
     ROLL_REQUEST:<dice> for <skill>  (ask the player to roll — when you need a roll)
     ITEM_USED:<name>                 (consume an item from inventory)
     ITEM_GAINED:<name>               (add an item to inventory)
     SPELL_SLOT_USED:<level>          (consume a spell slot)
     CONDITION:<target>,<condition>   (apply a condition: poisoned, stunned, etc.)
     NO_MECHANICS                     (use when no mechanical change this turn)

   [SUGGESTIONS]
   2-3 player options for the next action, each on its own line, tagged:
     roll:true — this option requires a dice roll before it can resolve
     roll:false — this option is narrative/social, no roll needed
   Format: "- <option text> [roll:true]" or "- <option text> [roll:false]"

   [CHRONICLE]
   One-line campaign log entry. Only include on significant beats (combat start,
   enemy death, item gained, scene change). Use "NO_ENTRY" for uneventful turns.

   [AUDIO]
   A structured version of the narration for the text-to-speech pipeline.
   Format rules:
   - Narrator text: [narrator] followed by the text to be spoken
   - Character dialogue: [CharName] "the spoken dialogue"
   - Sound effects: [SFX: key] on its own line (use underscores in keys)
   - Scene mood: [SCENE: mood] on its own line (sets background music)
   Valid scene moods: combat, tense, horror, mystery, exploration, tavern, emotional, victory
   Valid SFX keys (use these or invent new ones with descriptive names):
     sword_clash, arrow_hit, shield_block, spell_cast, door_open, door_close,
     footsteps, running, whisper, shout, scream, growl, roar, explosion,
     water_drip, wind_howl, fire_crackle, glass_break, wood_creak, stone_grind,
     magical_chime, healing_glow, potion_drink, coin_purse, page_turn, bell_toll
   Keep [AUDIO] faithful to [NARRATIVE] — same content, structured format.
   Do NOT include [SUGGESTIONS], [MECHANICS], or [CHRONICLE] content in [AUDIO].

4. ENCOUNTER BALANCE. This is solo play — no party backup. Level 1 enemies: max
   7 HP, no multiattack. A single bad roll should not end the run.

5. BE THE DM, NOT A PLAYER. You control NPCs, monsters, and the world. The player
   controls only their character. Never act for the player.

6. WARLOCK SPELL SLOTS recharge on a short rest, not a long rest. (Common AI error.)
"""


# ---------------------------------------------------------------------------
# Extended response parser — handles the 5th [AUDIO] section
# ---------------------------------------------------------------------------

def parse_response_v0(text: str) -> dict:
    """Parse a 5-section DM response.

    Returns dict with keys: NARRATIVE, MECHANICS, SUGGESTIONS, CHRONICLE, AUDIO.
    Falls back to empty string for any missing section.
    """
    sections = parse_response(text)
    # Also parse [AUDIO] section
    import re
    audio_pattern = r"\*{0,2}\[AUDIO\]\*{0,2}\s*(.*?)(?=\*{0,2}\[(?:NARRATIVE|MECHANICS|SUGGESTIONS|CHRONICLE|AUDIO)\]|$)"
    match = re.search(audio_pattern, text, re.DOTALL)
    if match:
        sections["AUDIO"] = match.group(1).strip()
    else:
        sections["AUDIO"] = ""
    return sections


# ---------------------------------------------------------------------------
# DM turn wrapper — uses the extended system prompt
# ---------------------------------------------------------------------------

def make_initial_state() -> GameState:
    """Create the initial game state for a new campaign."""
    return _make_initial_state_base()


def make_client_v0(provider: str = None, model: str = None):
    """Create an OpenAI-compatible API client.

    Auto-detects provider from model name if not specified.
    """
    if provider is None:
        if model:
            provider = config.detect_provider(model)
        else:
            provider = config.DEFAULT_PROVIDER

    from dotenv import load_dotenv
    load_dotenv(config.ENV_FILE)

    cfg = config.PROVIDERS[provider]
    api_key = os.environ.get(cfg["env_var"])
    if not api_key or api_key.startswith("your_") or api_key.endswith("_here"):
        raise ValueError(
            f"{cfg['env_var']} not set. Copy glm-work/.env.example to "
            f"glm-work/.env and fill in your key."
        )

    from openai import OpenAI
    return OpenAI(api_key=api_key, base_url=cfg["base_url"], timeout=60.0)


def dm_turn_v0(client, model: str, state: GameState, history: list,
               player_input: str, temperature: float = 0.7,
               max_tokens: int = 2500) -> tuple:
    """Call the DM brain for one turn using the v0 system prompt.

    Returns (response_text, elapsed_seconds, token_usage).
    """
    state_block = state.to_prompt_block()
    return dm_turn(
        client=client,
        model=model,
        system_prompt=SYSTEM_PROMPT_V0,
        state_block=state_block,
        history=history,
        player_input=player_input,
        temperature=temperature,
        max_tokens=max_tokens,
    )
