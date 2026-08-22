"""Narrator v0.3.5 — Game loop orchestration.

This module sits between the HTTP layer (app.py) and the domain logic
(dm_engine.py, audio_engine.py). It handles:
- New game creation and opening narration
- Turn processing (player action -> DM response -> mechanics -> audio)
- Save/load
- Session Zero wizard turns

This was extracted from app.py in v0.3.5 to allow parallel instances to
work on different aspects of the turn flow without conflicting on the
same monolithic file.
"""
import json
import time
import threading
from pathlib import Path

from . import config
from .dm_engine import (
    GameState, Enemy, SYSTEM_PROMPT, parse_response, parse_story,
    parse_suggestions, make_client, detect_provider, dm_turn,
    make_initial_state,
    SESSION_ZERO_SYSTEM_PROMPT, parse_session_zero_response,
)
from .audio_queue import (
    AudioQueue, ChoiceAudioQueue, FreeTextGenerator,
    register_queue, get_queue, remove_queue,
    freetext_generator,
)


# ---------------------------------------------------------------------------
# Budget tracker
# ---------------------------------------------------------------------------

class BudgetTracker:
    def __init__(self, budget_usd: float = 5.0):
        self.budget = budget_usd
        self.spent = 0.0
        self.lock = threading.Lock()

    def add_cost(self, provider: str, model: str, input_tok: int, output_tok: int) -> float:
        pricing = config.PRICING.get(provider, {}).get(model)
        if not pricing:
            return 0.0
        cost = (input_tok * pricing[0] + output_tok * pricing[1]) / 1_000_000
        with self.lock:
            self.spent += cost
        return cost

    def can_spend(self, estimated_cost: float = 0.01) -> bool:
        return (self.spent + estimated_cost) < self.budget

    def should_fallback(self, provider: str, model: str) -> bool:
        if provider not in config.PRICING:
            return False
        return not self.can_spend()

    def remaining(self) -> float:
        return max(0, self.budget - self.spent)

    def to_dict(self) -> dict:
        return {"budget": self.budget, "spent": round(self.spent, 4),
                "remaining": round(self.remaining(), 4)}


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

class Session:
    def __init__(self):
        self.state: GameState = None
        self.history: list = []
        self.client = None
        self.model = config.DEFAULT_MODEL
        self.provider = config.DEFAULT_PROVIDER
        self.audio_enabled = True
        self.tts_engine = "kokoro"
        self.tts_speed = 1.0
        self.music_enabled = True
        self.music_volume = 0.12
        self.music_source = "library"
        self.turn_counter = 0
        self.game_id = str(int(time.time()))
        self.audio_results: dict = {}
        self.budget = BudgetTracker(config.DEFAULT_BUDGET)
        self.started = False
        self.cast = None
        self.session_zero_active = False
        self.session_zero_history: list = []
        self.session_zero_turn = 0
        self.campaign_meta: dict = {}

    def init_client(self):
        if self.client is None or self.model != getattr(self, '_last_model', None):
            self.provider = detect_provider(self.model)
            self.client = make_client(self.provider)
            self._last_model = self.model

    def load_cast(self):
        if self.cast is None:
            try:
                with open(config.CAST_FILE) as f:
                    self.cast = json.load(f)
            except:
                self.cast = {}
        return self.cast


session = Session()


# ---------------------------------------------------------------------------
# Audio generation (background thread)
# ---------------------------------------------------------------------------

def generate_audio_async(segments: list, scene_mood: str, turn_id: str):
    """Generate audio in background thread."""
    result = {"done": False, "audio_path": None, "duration": 0, "error": None,
              "progress": 0, "segment_info": ""}
    session.audio_results[turn_id] = result

    def worker():
        try:
            from . import audio_engine
            cast = session.load_cast()

            total_segs = len(segments)
            def progress_cb(done, total, info):
                result["progress"] = int((done / total) * 100) if total > 0 else 0
                result["segment_info"] = info

            audio_result = audio_engine.render_narration(
                segments=segments, scene_mood=scene_mood, turn_id=turn_id,
                cast=cast, tts_engine=session.tts_engine,
                speed=session.tts_speed, music_enabled=session.music_enabled,
                music_source=getattr(session, 'music_source', 'library'),
                music_volume=session.music_volume,
                progress_callback=progress_cb,
            )
            result["audio_path"] = audio_result["audio_path"]
            result["duration"] = audio_result["duration"]
            result["errors"] = audio_result.get("errors", [])
        except Exception as e:
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        finally:
            result["done"] = True

    t = threading.Thread(target=worker, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Queue-based audio generation (v0.4a — segment queue for live streaming)
# ---------------------------------------------------------------------------

def generate_audio_queue(segments: list, scene_mood: str, turn_id: str):
    """Start queue-based segment generation for live streaming.

    Creates an AudioQueue, registers it, and starts background generation.
    The browser polls /api/queue_status?turn_id=... to consume segments
    incrementally as they become READY.
    """
    cast = session.load_cast()
    queue = AudioQueue(
        turn_id=turn_id,
        segments_data=segments,
        cast=cast,
        tts_engine=session.tts_engine,
        speed=session.tts_speed,
        scene_mood=scene_mood,
    )
    register_queue(queue)
    queue.start()
    # Also keep a legacy-style result for backward compatibility
    session.audio_results[turn_id] = {
        "done": False, "audio_path": None, "duration": 0, "error": None,
        "progress": 0, "segment_info": "queue: starting...",
        "_queue": True,
    }
    return queue


def generate_choice_audio(choices: list) -> ChoiceAudioQueue:
    """Pre-generate audio for all preset choices.

    Called as soon as suggestions arrive from the DM, before the player
    picks one.  Only the selected choice's audio is actually used.
    """
    cast = session.load_cast()
    cq = ChoiceAudioQueue(
        choices=choices,
        cast=cast,
        tts_engine=session.tts_engine,
        speed=session.tts_speed,
    )
    cq.start()
    return cq


# ---------------------------------------------------------------------------
# Turn orchestration
# ---------------------------------------------------------------------------

def handle_newgame(data: dict) -> dict:
    """Create a new game and generate opening narration."""
    story_style = data.get("style", "")
    setting = data.get("setting", "")
    name = data.get("name", "Kael")
    persona = data.get("persona", "")
    atmosphere = data.get("atmosphere", "")
    inspiration = data.get("inspiration", "")
    auto_roll = data.get("dicemode", "auto") == "auto"

    session.state = make_initial_state(
        story_style=story_style, setting=setting, persona=persona,
        atmosphere=atmosphere, inspiration=inspiration, auto_roll=auto_roll,
    )
    if name:
        session.state.pc_name = name
    session.history = []
    session.turn_counter = 0
    session.game_id = str(int(time.time()))
    session.model = data.get("model", session.model)
    session.init_client()

    state_block = session.state.to_prompt_block()
    opening = f"Start the story. The player character ({session.state.pc_name}) enters the scene for the first time. Set the scene, introduce the atmosphere, and present the initial situation."

    text, elapsed, usage = dm_turn(
        session.client, session.model, SYSTEM_PROMPT,
        state_block, [], opening,
    )
    print(f"[server] DM response: {len(text)} chars in {elapsed:.1f}s")

    cost = session.budget.add_cost(session.provider, session.model,
                                   usage["prompt_tokens"], usage["completion_tokens"])

    sections = parse_response(text)
    changes = session.state.apply_mechanics(sections["MECHANICS"])
    segments = parse_story(sections["STORY"], sections.get("AUDIO", ""))
    suggestions = parse_suggestions(sections["SUGGESTIONS"])

    if sections["CHRONICLE"] and sections["CHRONICLE"] != "NO_ENTRY":
        session.state.chronicle.append(sections["CHRONICLE"])

    session.history.append({"role": "user", "content": opening})
    session.history.append({"role": "assistant", "content": text})
    session.turn_counter = 1

    audio_turn_id = f"g{session.game_id}_turn_{session.turn_counter:03d}"
    if session.audio_enabled and segments:
        generate_audio_queue(segments, sections.get("SCENE", "exploration"), audio_turn_id)

    return {
        "model": session.model,
        "story": sections["STORY"],
        "segments": segments,
        "suggestions": suggestions,
        "changes": changes,
        "state": session.state.to_dict(),
        "turn": session.turn_counter,
        "scene": sections.get("SCENE", "exploration"),
        "audio_enabled": session.audio_enabled,
        "audio_turn_id": audio_turn_id if segments else None,
        "auto_roll": session.state.auto_roll,
        "budget": session.budget.to_dict(),
    }


def handle_turn(data: dict) -> dict:
    """Process a player action and return the DM response."""
    if not session.state:
        return {"error": "No game in progress. Start a new game first."}

    action = data.get("action", "").strip()
    if not action:
        return {"error": "No action provided"}

    client_settings = data.get("settings", {})
    if "model" in client_settings and client_settings["model"] != session.model:
        session.model = client_settings["model"]
        session.init_client()
    if "autoroll" in client_settings:
        session.state.auto_roll = client_settings["autoroll"]
    if "music" in client_settings:
        session.music_enabled = client_settings["music"]
    if "tts" in client_settings:
        session.tts_engine = client_settings["tts"]
    if "speed" in client_settings:
        session.tts_speed = client_settings["speed"]
    if "musicVol" in client_settings:
        session.music_volume = client_settings["musicVol"]
    if "musicSrc" in client_settings:
        session.music_source = client_settings["musicSrc"]

    session.init_client()

    fallback_used = False
    original_model = session.model
    if session.budget.should_fallback(session.provider, session.model):
        print(f"[server] Budget exhausted - falling back to free provider")
        session.model = config.DEFAULT_MODEL
        session.provider = detect_provider(session.model)
        session.init_client()
        fallback_used = True

    state_block = session.state.to_prompt_block()

    text, elapsed, usage = dm_turn(
        session.client, session.model, SYSTEM_PROMPT,
        state_block, session.history, action,
    )

    cost = session.budget.add_cost(session.provider, session.model,
                                   usage["prompt_tokens"], usage["completion_tokens"])

    sections = parse_response(text)
    changes = session.state.apply_mechanics(sections["MECHANICS"])
    segments = parse_story(sections["STORY"], sections.get("AUDIO", ""))
    suggestions = parse_suggestions(sections["SUGGESTIONS"])

    if sections["CHRONICLE"] and sections["CHRONICLE"] != "NO_ENTRY":
        session.state.chronicle.append(sections["CHRONICLE"])

    session.history.append({"role": "user", "content": action})
    session.history.append({"role": "assistant", "content": text})
    session.turn_counter += 1

    audio_turn_id = f"g{session.game_id}_turn_{session.turn_counter:03d}"
    if session.audio_enabled and segments:
        generate_audio_queue(segments, sections.get("SCENE", "exploration"), audio_turn_id)

    return {
        "story": sections["STORY"],
        "segments": segments,
        "suggestions": suggestions,
        "changes": changes,
        "state": session.state.to_dict(),
        "turn": session.turn_counter,
        "scene": sections.get("SCENE", "exploration"),
        "audio_enabled": session.audio_enabled,
        "audio_turn_id": audio_turn_id if segments else None,
        "budget": session.budget.to_dict(),
        "elapsed": round(elapsed, 1),
        "fallback_used": fallback_used,
        "original_model": original_model if fallback_used else None,
        "model": session.model,
    }


def handle_save() -> dict:
    """Save game state to JSON file."""
    if not session.state:
        return {"error": "No game to save"}
    save_data = {
        "state": session.state.to_dict(),
        "history": session.history[-20:],
        "turn_counter": session.turn_counter,
        "model": session.model,
        "timestamp": time.time(),
    }
    save_path = config.OUTPUT_DIR / "save.json"
    with open(save_path, "w") as f:
        json.dump(save_data, f, indent=2)
    return {"saved": True, "path": str(save_path), "turn": session.turn_counter}


def handle_load() -> dict:
    """Load game state from JSON file."""
    save_path = config.OUTPUT_DIR / "save.json"
    if not save_path.exists():
        return {"error": "No save file found"}
    with open(save_path) as f:
        data = json.load(f)
    state_dict = data["state"]
    session.state = GameState(
        pc_name=state_dict["pc_name"], pc_class=state_dict["pc_class"],
        pc_level=state_dict["pc_level"], pc_hp=state_dict["pc_hp"],
        pc_max_hp=state_dict["pc_max_hp"], pc_ac=state_dict["pc_ac"],
        pc_str=state_dict.get("pc_str", 16), pc_dex=state_dict.get("pc_dex", 12),
        pc_con=state_dict.get("pc_con", 14), pc_int=state_dict.get("pc_int", 10),
        pc_wis=state_dict.get("pc_wis", 10), pc_cha=state_dict.get("pc_cha", 10),
        inventory=state_dict["inventory"], equipment=state_dict.get("equipment", ""),
        enemies=[Enemy(e["name"], e["hp"], e["max_hp"], e["ac"]) for e in state_dict["enemies"]],
        location=state_dict.get("location", ""), light=state_dict.get("light", ""),
        time=state_dict.get("time", ""), chronicle=state_dict.get("chronicle", []),
        auto_roll=state_dict.get("auto_roll", True),
    )
    session.history = data.get("history", [])
    session.turn_counter = data.get("turn_counter", 0)
    session.model = data.get("model", session.model)
    session.init_client()
    return {"loaded": True, "turn": session.turn_counter,
            "state": session.state.to_dict()}


# ---------------------------------------------------------------------------
# Session Zero wizard
# ---------------------------------------------------------------------------

def handle_session_zero_start(data: dict) -> dict:
    """Start the Session Zero conversational wizard."""
    session.session_zero_active = True
    session.session_zero_history = []
    session.session_zero_turn = 0
    session.campaign_meta = {}
    session.model = data.get("model", session.model)
    session.init_client()

    opening = "Hello! I'm your Dungeon Master. Let's set up your adventure. First - what's your character's name?"
    session.session_zero_history.append({"role": "user", "content": "(system) Begin Session Zero. Greet the player and ask for their character name."})

    text, elapsed, usage = dm_turn(
        session.client, session.model, SESSION_ZERO_SYSTEM_PROMPT,
        "Session Zero - campaign setup", [], opening,
    )
    cost = session.budget.add_cost(session.provider, session.model,
                                   usage["prompt_tokens"], usage["completion_tokens"])
    parsed = parse_session_zero_response(text)
    session.session_zero_history.append({"role": "assistant", "content": text})
    session.session_zero_turn = 1

    # Track the topic the DM asked about — the player's next answer goes here
    session.campaign_meta["_current_topic"] = parsed["topic"]

    return {
        "narrative": parsed["narrative"],
        "topic": parsed["topic"],
        "suggestions": parsed["suggestions"],
        "done": parsed["done"],
        "turn": session.session_zero_turn,
        "model": session.model,
        "budget": session.budget.to_dict(),
    }


def handle_session_zero_turn(data: dict) -> dict:
    """Process one Session Zero turn."""
    if not session.session_zero_active:
        return {"error": "Session Zero not started"}

    answer = data.get("answer", "").strip()
    if not answer:
        return {"error": "No answer provided"}

    # Store the answer under the topic that was ASKED (previous turn's topic)
    asked_topic = session.campaign_meta.pop("_current_topic", None)
    if asked_topic and asked_topic != "done":
        session.campaign_meta[asked_topic] = answer
        # Special handling: greeting topic = character name
        if asked_topic == "greeting":
            session.campaign_meta["character_name"] = answer

    session.session_zero_history.append({"role": "user", "content": answer})

    text, elapsed, usage = dm_turn(
        session.client, session.model, SESSION_ZERO_SYSTEM_PROMPT,
        "Session Zero - campaign setup",
        session.session_zero_history[:-1],
        answer,
    )
    cost = session.budget.add_cost(session.provider, session.model,
                                   usage["prompt_tokens"], usage["completion_tokens"])
    parsed = parse_session_zero_response(text)
    session.session_zero_history.append({"role": "assistant", "content": text})
    session.session_zero_turn += 1

    # Track the new topic for the next answer
    session.campaign_meta["_current_topic"] = parsed["topic"]

    return {
        "narrative": parsed["narrative"],
        "topic": parsed["topic"],
        "suggestions": parsed["suggestions"],
        "done": parsed["done"],
        "turn": session.session_zero_turn,
        "campaign_meta": {k: v for k, v in session.campaign_meta.items() if not k.startswith("_")},
        "budget": session.budget.to_dict(),
    }


def handle_session_zero_finish(data: dict) -> dict:
    """Finish Session Zero and start the real game with collected campaign_meta."""
    import re as _re

    meta = session.campaign_meta
    session.session_zero_active = False

    # Extract character name from greeting answer
    greeting = meta.get("greeting", meta.get("character_name", ""))
    char_name = "Kael"
    if greeting:
        # Try to extract a name from phrases like "My name is X" or "Call me X"
        name_match = _re.search(r'(?:my name is|call me|i am|i\'m)\s+([A-Z][a-z]+)', greeting, _re.IGNORECASE)
        if name_match:
            char_name = name_match.group(1)
        elif len(greeting) <= 30 and greeting[0].isupper():
            # Short answer that looks like just a name
            char_name = greeting.split()[0].rstrip(",.;!")
        else:
            char_name = meta.get("character_name", "Kael")

    story_style = meta.get("style", "classic fantasy")
    setting = meta.get("setting", "")
    persona = meta.get("persona", meta.get("character", ""))
    tone = meta.get("tone", meta.get("atmosphere", "adventurous"))
    dice_pref = meta.get("dice", "auto")
    auto_roll = "auto" in dice_pref.lower() or "app" in dice_pref.lower()

    session.state = make_initial_state(
        story_style=story_style, setting=setting, persona=persona,
        atmosphere=tone, auto_roll=auto_roll,
    )
    if char_name:
        session.state.pc_name = char_name
    session.history = []
    session.turn_counter = 0
    session.game_id = str(int(time.time()))
    session.init_client()

    state_block = session.state.to_prompt_block()
    opening = (f"Start the story. The player character ({session.state.pc_name}) "
               f"enters the scene for the first time. Set the scene, introduce the "
               f"atmosphere, and present the initial situation. This is the opening "
               f"chapter - take your time to establish the world.")

    text, elapsed, usage = dm_turn(
        session.client, session.model, SYSTEM_PROMPT,
        state_block, [], opening,
    )
    cost = session.budget.add_cost(session.provider, session.model,
                                   usage["prompt_tokens"], usage["completion_tokens"])

    sections = parse_response(text)
    changes = session.state.apply_mechanics(sections["MECHANICS"])
    segments = parse_story(sections["STORY"], sections.get("AUDIO", ""))
    suggestions = parse_suggestions(sections["SUGGESTIONS"])

    if sections["CHRONICLE"] and sections["CHRONICLE"] != "NO_ENTRY":
        session.state.chronicle.append(sections["CHRONICLE"])

    session.history.append({"role": "user", "content": opening})
    session.history.append({"role": "assistant", "content": text})
    session.turn_counter = 1

    audio_turn_id = f"g{session.game_id}_turn_{session.turn_counter:03d}"
    if session.audio_enabled and segments:
        generate_audio_queue(segments, sections.get("SCENE", "exploration"), audio_turn_id)

    return {
        "model": session.model,
        "story": sections["STORY"],
        "segments": segments,
        "suggestions": suggestions,
        "changes": changes,
        "state": session.state.to_dict(),
        "turn": session.turn_counter,
        "scene": sections.get("SCENE", "exploration"),
        "audio_enabled": session.audio_enabled,
        "audio_turn_id": audio_turn_id if segments else None,
        "auto_roll": session.state.auto_roll,
        "budget": session.budget.to_dict(),
        "campaign_meta": session.campaign_meta,
    }


# ---------------------------------------------------------------------------
# Voice assignment
# ---------------------------------------------------------------------------

def handle_voice_assign(data: dict) -> dict:
    """Assign or update a character voice."""
    cast = session.load_cast()
    name = data.get("name", "").strip()
    voice_desc = data.get("voice", "").strip()
    if not name or not voice_desc:
        return {"error": "Both name and voice required"}
    cast[name] = voice_desc
    cast_path = config.CAST_FILE
    with open(cast_path, "w") as f:
        json.dump(cast, f, indent=2)
    session.cast = cast
    return {"saved": True, "name": name, "voice": voice_desc}


def handle_voice_list() -> dict:
    """List current voice assignments."""
    cast = session.load_cast()
    return {"cast": cast, "defaults": cast.get("_defaults", {})}
