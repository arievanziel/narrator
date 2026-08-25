"""Narrator v0.5 — Game loop orchestration with World Engine integration.

This module sits between the HTTP layer (app.py) and the domain logic
(dm_engine.py, audio_engine.py, world_store.py). It handles:
- New game creation and opening narration
- Turn processing (player action -> context assembly -> DM response ->
  consistency guards -> mechanics -> audio)
- Save/load
- Session Zero wizard turns

v0.5 integration: WorldStore is attached on new game, context assembler
replaces the history[-10:] sliding window, presence/liveness guard runs
after each DM response, RECALL is handled with one re-run max, TurnRecords
are logged to JSONL, and chronicle compaction runs every 20 turns.
"""
import json
import re
import time
import threading
from pathlib import Path

from . import config
from .dm_engine import (
    GameState, Enemy, SYSTEM_PROMPT, parse_response, parse_story,
    parse_suggestions, make_client, detect_provider, dm_turn,
    dm_turn_dc_roll, parse_roll_request, resolve_roll, make_roll_seed,
    make_initial_state,
    SESSION_ZERO_SYSTEM_PROMPT, parse_session_zero_response,
)
from .audio_queue import (
    AudioQueue, ChoiceAudioQueue, FreeTextGenerator,
    register_queue, get_queue, remove_queue,
    freetext_generator,
)
from .world_store import (
    WorldStore, TurnRecord, TokenBudget, ContextBundle,
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
        # v0.5: World Engine integration
        self.world_store: WorldStore = None
        self.last_narration: str = ""  # for context assembler scoring
        self.recall_used_this_turn: bool = False

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

    def init_world_store(self, campaign_id: str = None):
        """Create and attach a WorldStore for this campaign."""
        cid = campaign_id or f"game_{self.game_id}"
        self.world_store = WorldStore(campaign_id=cid)
        # Set campaign meta from state
        if self.state:
            self.world_store.campaign_meta = {
                "style": self.state.story_style,
                "setting": self.state.setting,
                "persona": self.state.persona,
                "atmosphere": self.state.atmosphere,
                "inspiration": self.state.inspiration,
            }
        # Attach to GameState (this syncs PC + enemies into the store)
        self.state.attach_world_store(self.world_store)

    def build_context(self, player_input: str) -> str:
        """Build the full context for the LLM using the World Engine assembler.

        Returns a single string that combines the stable prefix and volatile
        suffix. If no WorldStore is attached, falls back to the legacy
        state_block + history approach.

        v1.0: If enter_scene() produced a "since you were last here" digest on
        the previous turn, it is prepended to the player's input so the narrator
        can weave it into the opening of the next passage.
        """
        if self.world_store is None:
            # Legacy fallback
            return self.state.to_prompt_block()

        # v1.0: Inject the scene digest from the previous turn's enter_scene()
        digest = getattr(self.world_store, "_last_scene_digest", "")
        if digest:
            player_input = f"[SCENE DIGEST — since you were last here]\n{digest}\n\n[PLAYER ACTION]\n{player_input}"
            self.world_store._last_scene_digest = ""  # consume it

        # Use the context assembler
        recent_turns = []
        for i in range(0, len(self.history), 2):
            if i + 1 < len(self.history):
                recent_turns.append({
                    "turn": i // 2 + 1,
                    "player_input": self.history[i].get("content", ""),
                    "narrative": self.history[i + 1].get("content", "")[:200],
                })

        bundle = self.world_store.get_context_for_turn(
            player_input=player_input,
            budget=TokenBudget(),
            last_narration=self.last_narration,
            system_prompt=SYSTEM_PROMPT,
            recent_turns=recent_turns,
        )

        # Log context assembly for debugging
        print(f"[world-engine] Context: {len(bundle.included_entity_ids)} included, "
              f"{len(bundle.dropped_entity_ids)} dropped")

        # Combine stable + volatile into the prompt
        return f"{bundle.stable_prefix}\n\n{bundle.volatile_suffix}"


session = Session()


# ---------------------------------------------------------------------------
# World Engine integration helpers
# ---------------------------------------------------------------------------

def _check_recall(mechanics_text: str) -> str | None:
    """Extract a RECALL query from mechanics tags, if present.

    Returns the entity name to recall, or None.
    """
    for line in mechanics_text.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("RECALL:"):
            return line.split(":", 1)[1].strip()
    return None


def _run_consistency_guard(narrative: str) -> dict:
    """Run the presence-and-liveness guard on the DM's narrative.

    Returns {'violations': [...], 'correction_prompt': str}.
    If violations exist, the caller should regenerate once with the
    correction prompt appended, then fail open.
    """
    if session.world_store is None:
        return {"violations": [], "correction_prompt": ""}

    return session.world_store.presence_liveness_guard(
        narrative, current_turn=session.turn_counter)


def _log_turn_record(player_input: str, narrative: str,
                     mechanics_applied: list, roll_result: dict = None) -> None:
    """Append a TurnRecord to the WorldStore's JSONL log."""
    if session.world_store is None:
        return

    # Build RollRecord if we have a roll result
    roll_record = None
    if roll_result:
        from .world_store import RollRecord
        roll_record = RollRecord(
            turn=session.turn_counter,
            action=player_input[:100],
            skill=roll_result.get("skill", ""),
            dc=roll_result.get("dc", 0) or 0,
            seed=roll_result.get("seed", 0) or 0,
            roll=roll_result.get("roll", 0),
            modifier=roll_result.get("modifier", 0),
            total=roll_result.get("total", 0),
            result=roll_result.get("result", "unknown").lower().replace(" ", "_"),
        )

    record = TurnRecord(
        turn=session.turn_counter,
        player_input=player_input,
        narrative=narrative[:500],  # truncate for log
        mechanics_applied=mechanics_applied,
        roll=roll_record,
    )
    session.world_store.append_turn_record(record)


def _maybe_compact_chronicle() -> None:
    """Run chronicle compaction every 20 turns."""
    if session.world_store is None:
        return
    session.world_store.compact_chronicle(session.turn_counter, k=20)


def _sync_state_from_store() -> None:
    """Sync flat attributes from the WorldStore back to GameState for UI."""
    if session.state and session.state.world_store is not None:
        session.state._sync_from_store()


# ---------------------------------------------------------------------------
# v1.0 book structure (Opus) — chapters, character generation, reader-safe log
# ---------------------------------------------------------------------------

# Engine phrases that must never reach the reader verbatim.
_ENGINE_NOISE = (
    "no match within policy window", "created new:", "resolve_or_create",
    "entity_id", "policy window", "schema", "norm_name",
)

# v1.0: Mood keywords for deriving chapter ambience from scene-setting prose
# when the DM doesn't emit an explicit [SCENE] tag.
_MOOD_KEYWORDS = {
    "combat": ["battle", "fight", "sword", "swords", "clash", "clashing", "war", "attack", "enemy", "enemies"],
    "tense": ["danger", "threat", "tension", "shadow", "shadows", "lurk", "lurking", "hunt", "hunting", "stalk"],
    "horror": ["dread", "horror", "fear", "darkness", "corpse", "corpses", "blood", "decay", "ruin", "ruins"],
    "mystery": ["mystery", "mysterious", "secret", "secrets", "hidden", "ancient", "forgotten", "riddle", "clue"],
    "sad": ["sorrow", "grief", "loss", "mourn", "mourning", "tears", "melancholy", "desolate"],
    "emotional": ["hope", "love", "heart", "tears", "joy", "sorrow", "memory", "memories"],
    "tavern": ["tavern", "inn", "ale", "fire", "fireplace", "warmth", "laughter", "mug"],
    "dungeon": ["dungeon", "cave", "caves", "underground", "tunnel", "tunnels", "crypt", "damp", "stone"],
}


def _derive_mood(text: str, fallback: str = "exploration") -> str:
    """Infer a scene mood from prose text by keyword matching.
    Used when the DM doesn't emit an explicit [SCENE] tag on a chapter opening.
    Uses word-boundary matching to avoid false positives (e.g. "war" in "warm").
    """
    import re
    low = text.lower()
    for mood, keywords in _MOOD_KEYWORDS.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', low):
                return mood
    return fallback


def reader_notes(changes: list) -> list:
    """Translate the mechanics log into something printable in a book.

    The raw strings stay available for the storyteller's-notes view; this is
    the version shown when that view is off. Anything that leaks engine
    internals is dropped rather than prettified.
    """
    out = []
    for c in changes:
        low = str(c).lower()
        if any(n in low for n in _ENGINE_NOISE):
            # Keep the fact, drop the machinery: "Created: Mirel (...)" -> nothing.
            continue
        if "REJECTED" in str(c):
            out.append("The story tried to run ahead of itself; it was held back.")
            continue
        out.append(str(c))
    return out


def finalize_passage(sections: dict, segments: list, changes: list) -> tuple:
    """Apply v1.0 book structure to a freshly parsed DM response.

    Runs, in order:
      1. [CHARACTER] — invent the listener's sheet on the opening passage.
      2. player_voice_guard — strip dialogue the narrator wrote for the listener.
      3. maybe_start_chapter — open a chapter if warranted.

    Returns (segments, changes, chapter_dict_or_None, chapter_mood_or_None).
    """
    # 1. Character generation (opening passage only)
    if sections.get("CHARACTER") and not session.state.character_generated:
        changes = list(changes) + session.state.apply_character_block(
            sections["CHARACTER"])

    # 2. Player-voice guard — deterministic, no extra LLM call
    if session.world_store is not None:
        guarded = session.world_store.player_voice_guard(
            segments, session.state.pc_name)
        if guarded["violations"]:
            print(f"[book] player-voice guard: {len(guarded['violations'])} stripped")
            segments = guarded["segments"]
            changes = list(changes) + guarded["violations"]

    # 3. Chapter
    # v1.0: Use turn_counter + 1 because the counter increments AFTER
    # finalize_passage. The chapter opens at the upcoming turn, not the
    # previous one. (Cosmetic fix — start_turn was 0 for the opening passage.)
    chapter = None
    chapter_mood = None
    if session.world_store is not None:
        # v1.0: Derive mood from scene_setting if the DM didn't emit [SCENE].
        # This ensures per-chapter ambience has a mood to key off even when
        # the narrator forgets the tag.
        raw_mood = sections.get("SCENE", "")
        if not raw_mood:
            raw_mood = _derive_mood(sections.get("SCENE_SETTING", ""))

        ch = session.world_store.maybe_start_chapter(
            proposed_title=sections.get("CHAPTER", ""),
            scene_setting=sections.get("SCENE_SETTING", ""),
            current_turn=session.turn_counter + 1,
            mood=raw_mood,
        )
        if ch is not None:
            chapter = ch.to_dict()
            chapter["is_new"] = True
            chapter_mood = ch.mood or raw_mood
            # v1.0: Speak the scene-setting paragraph. It is narration — prepend
            # it as a narrator segment before the STORY segments so TTS picks
            # it up. Without this, the chapter opening is silent.
            scene_setting_text = sections.get("SCENE_SETTING", "").strip()
            if scene_setting_text:
                scene_seg = {"kind": "narrator", "speaker": "narrator",
                             "text": scene_setting_text}
                segments = [scene_seg] + segments
        elif session.world_store.current_chapter is not None:
            chapter = session.world_store.current_chapter.to_dict()
            chapter["is_new"] = False
            chapter_mood = session.world_store.current_chapter.mood or None

    return segments, changes, chapter, chapter_mood

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

    # v0.5c: Use procedural mode — no hardcoded goblins
    session.state = make_initial_state(
        story_style=story_style, setting=setting, persona=persona,
        atmosphere=atmosphere, inspiration=inspiration, auto_roll=auto_roll,
        procedural=True,
    )
    if name:
        session.state.pc_name = name
    session.history = []
    session.turn_counter = 0
    session.game_id = str(int(time.time()))
    session.model = data.get("model", session.model)
    session.init_client()

    # v0.5: Initialize and attach WorldStore
    session.init_world_store()

    opening = (
        f"Start the story. The player character ({session.state.pc_name}) enters "
        f"the scene for the first time. Set the scene, introduce the atmosphere, "
        f"and present the initial situation. "
        f"Generate the opening location and any NPCs or encounters procedurally — "
        f"do NOT use a fixed scenario. Use ENTITY_NEW tags to introduce any new "
        f"NPCs, locations, or items you create."
    )

    # v0.5: Use context assembler instead of flat state_block
    context_block = session.build_context(opening)

    text, elapsed, usage = dm_turn(
        session.client, session.model, SYSTEM_PROMPT,
        context_block, [], opening,
    )
    print(f"[server] DM response: {len(text)} chars in {elapsed:.1f}s")

    cost = session.budget.add_cost(session.provider, session.model,
                                   usage["prompt_tokens"], usage["completion_tokens"])

    sections = parse_response(text)

    # v0.5: Run presence/liveness guard — regenerate once if violations
    guard_result = _run_consistency_guard(sections["STORY"])
    if guard_result["violations"]:
        print(f"[world-engine] Guard violations: {len(guard_result['violations'])} — regenerating")
        correction = guard_result["correction_prompt"]
        corrected_input = f"{opening}\n\n{correction}"
        context_block = session.build_context(corrected_input)
        text2, elapsed2, usage2 = dm_turn(
            session.client, session.model, SYSTEM_PROMPT,
            context_block, [], corrected_input,
        )
        session.budget.add_cost(session.provider, session.model,
                                usage2["prompt_tokens"], usage2["completion_tokens"])
        sections = parse_response(text2)
        text = text2
        # Log the correction — only in the mechanics changes (storyteller mode), never in the story text.
        # v1.0: This note was previously appended to sections["STORY"], which leaked engine
        # internals into the reader's book. Now it goes only into the changes log.
        _guard_note = "[Guard: response regenerated due to a consistency violation]"
    else:
        _guard_note = None

    changes = session.state.apply_mechanics(sections["MECHANICS"])
    if _guard_note:
        changes = list(changes) + [_guard_note]
    segments = parse_story(sections["STORY"], sections.get("AUDIO", ""))
    suggestions = parse_suggestions(sections["SUGGESTIONS"])
    # v1.0: character generation, player-voice guard, chapter opening
    segments, changes, chapter, chapter_mood = finalize_passage(sections, segments, changes)

    if sections["CHRONICLE"] and sections["CHRONICLE"] != "NO_ENTRY":
        session.state.chronicle.append(sections["CHRONICLE"])

    session.history.append({"role": "user", "content": opening})
    session.history.append({"role": "assistant", "content": text})
    session.turn_counter = 1
    session.last_narration = sections["STORY"]

    # v0.5: Log turn record and sync state
    _log_turn_record(opening, sections["STORY"], changes)
    _sync_state_from_store()

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
        "scene": chapter_mood if (chapter and chapter.get("is_new")) else sections.get("SCENE", "exploration"),
        # v1.0 book structure
        "chapter": chapter,
        "chapter_mood": chapter_mood,
        "scene_setting": sections.get("SCENE_SETTING", "") if (chapter and chapter.get("is_new")) else "",
        "reader_notes": reader_notes(changes),
        "audio_enabled": session.audio_enabled,
        "audio_turn_id": audio_turn_id if segments else None,
        "auto_roll": session.state.auto_roll,
        "budget": session.budget.to_dict(),
    }


def handle_turn(data: dict) -> dict:
    """Process a player action and return the DM response.

    v0.5: Full World Engine integration — context assembler, presence guard,
    RECALL loop, TurnRecord logging, chronicle compaction.
    """
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

    # v0.5: Reset per-turn flags
    session.recall_used_this_turn = False

    # v0.4b: Use DC-then-roll two-call flow with seeded RNG
    # The seed ensures reproducibility: same campaign + turn = same roll
    next_turn = session.turn_counter + 1
    campaign_id = session.world_store.campaign_id if session.world_store else session.game_id
    roll_seed = make_roll_seed(campaign_id, next_turn)

    # v0.5: Use context assembler instead of flat state_block + history[-10:]
    context_block = session.build_context(action)

    # v0.4b: Check for manual roll from client
    manual_roll = data.get("manual_roll")

    # v0.4b: DC-then-roll — handles both contested and non-contested turns
    dc_result = dm_turn_dc_roll(
        session.client, session.model, SYSTEM_PROMPT,
        context_block, session.history, action,
        auto_roll=session.state.auto_roll,
        manual_roll=manual_roll if not session.state.auto_roll else None,
        seed=roll_seed,
    )

    # Track costs
    session.budget.add_cost(session.provider, session.model,
                            dc_result["usage_total"]["prompt_tokens"],
                            dc_result["usage_total"]["completion_tokens"])
    elapsed = dc_result["elapsed_total"]
    roll_result = dc_result["roll_result"]

    # Use the final sections (phase 3 if contested, phase 1 if not)
    sections = dc_result["sections"]
    text = dc_result.get("phase3_text") or dc_result["phase1_text"]

    # If contested, combine phase 1 and phase 3 story for display
    if dc_result["contested"] and dc_result.get("phase1_sections"):
        phase1_story = dc_result["phase1_sections"].get("STORY", "")
        phase3_story = sections.get("STORY", "")
        if phase1_story and phase3_story:
            # Combine stories — the roll result is shown as a separate UI element
            sections["STORY"] = f"{phase1_story}\n\n{phase3_story}"

    # v0.5: Check for RECALL tags — one re-run max
    recall_query = _check_recall(sections["MECHANICS"])
    if recall_query and not session.recall_used_this_turn and session.world_store:
        session.recall_used_this_turn = True
        recall_result = session.world_store.handle_recall(recall_query)
        print(f"[world-engine] RECALL '{recall_query}': found={recall_result['found']}")
        if recall_result["found"]:
            recall_context = f"{action}\n\n[RECALLED ENTITY]\n{recall_result['context_text']}\n\nNow continue with the player's action, using this recalled information."
            context_block = session.build_context(recall_context)
            text, elapsed, usage = dm_turn(
                session.client, session.model, SYSTEM_PROMPT,
                context_block, session.history, recall_context,
            )
            session.budget.add_cost(session.provider, session.model,
                                    usage["prompt_tokens"], usage["completion_tokens"])
            sections = parse_response(text)

    # v0.5: Run presence/liveness guard — regenerate once if violations
    guard_result = _run_consistency_guard(sections["STORY"])
    if guard_result["violations"]:
        print(f"[world-engine] Guard violations: {len(guard_result['violations'])} — regenerating")
        correction = guard_result["correction_prompt"]
        corrected_input = f"{action}\n\n{correction}"
        context_block = session.build_context(corrected_input)
        text2, elapsed2, usage2 = dm_turn(
            session.client, session.model, SYSTEM_PROMPT,
            context_block, session.history, corrected_input,
        )
        session.budget.add_cost(session.provider, session.model,
                                usage2["prompt_tokens"], usage2["completion_tokens"])
        sections = parse_response(text2)
        text = text2
        _guard_note = "[Guard: response regenerated due to a consistency violation]"
    else:
        _guard_note = None

    changes = session.state.apply_mechanics(sections["MECHANICS"])
    if _guard_note:
        changes = list(changes) + [_guard_note]
    segments = parse_story(sections["STORY"], sections.get("AUDIO", ""))
    suggestions = parse_suggestions(sections["SUGGESTIONS"])
    # v1.0: character generation, player-voice guard, chapter opening
    segments, changes, chapter, chapter_mood = finalize_passage(sections, segments, changes)

    if sections["CHRONICLE"] and sections["CHRONICLE"] != "NO_ENTRY":
        session.state.chronicle.append(sections["CHRONICLE"])

    session.history.append({"role": "user", "content": action})
    session.history.append({"role": "assistant", "content": text})
    session.turn_counter += 1
    session.last_narration = sections["STORY"]

    # v0.5: Log turn record with roll info, compact chronicle, sync state
    _log_turn_record(action, sections["STORY"], changes,
                     roll_result=roll_result)
    _maybe_compact_chronicle()
    _sync_state_from_store()

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
        "scene": chapter_mood if (chapter and chapter.get("is_new")) else sections.get("SCENE", "exploration"),
        # v1.0 book structure
        "chapter": chapter,
        "chapter_mood": chapter_mood,
        "scene_setting": sections.get("SCENE_SETTING", "") if (chapter and chapter.get("is_new")) else "",
        "reader_notes": reader_notes(changes),
        "audio_enabled": session.audio_enabled,
        "audio_turn_id": audio_turn_id if segments else None,
        "budget": session.budget.to_dict(),
        "elapsed": round(elapsed, 1),
        "fallback_used": fallback_used,
        "original_model": original_model if fallback_used else None,
        "model": session.model,
        # v0.4b: Roll result for UI display
        "roll": roll_result,
        "contested": dc_result["contested"],
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
        # v0.5: Save WorldStore campaign ID for re-attachment
        "world_campaign_id": session.world_store.campaign_id if session.world_store else None,
    }
    save_path = config.OUTPUT_DIR / "save.json"
    with open(save_path, "w") as f:
        json.dump(save_data, f, indent=2)
    # v0.5: Also save the WorldStore
    if session.world_store:
        session.world_store.save()
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
    # v0.5: Re-attach WorldStore if it was saved
    world_cid = data.get("world_campaign_id")
    if world_cid:
        session.world_store = WorldStore(campaign_id=world_cid)
        session.world_store.load()
        session.state.attach_world_store(session.world_store)
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

    opening = "Hello! I'm your Narrator. Let's set up your story. First — what's your character's name?"
    session.session_zero_history.append({"role": "user", "content": "(system) Begin the Foreword. Greet the reader and ask for their character name."})

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

    # Store the raw answer under the topic that was ASKED (previous turn's topic).
    # The LLM will parse it into a clean value via [PARSED].
    asked_topic = session.campaign_meta.pop("_current_topic", None)
    if asked_topic and asked_topic != "done":
        session.campaign_meta[asked_topic] = answer  # raw, as fallback
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

    # v1.0: Use the LLM-parsed value to overwrite the raw answer.
    # The LLM extracts the essential info (e.g. "My name is Lyra and I'm a rogue" → "Lyra").
    if parsed["parsed"] and asked_topic and asked_topic != "done":
        session.campaign_meta[asked_topic] = parsed["parsed"]
        if asked_topic == "greeting":
            session.campaign_meta["character_name"] = parsed["parsed"]

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
    meta = session.campaign_meta
    session.session_zero_active = False

    # v1.0: The LLM already parsed each answer via [PARSED], so character_name
    # should already be a clean name (e.g. "Lyra", not "My name is Lyra and I'm a rogue").
    # Fall back to regex extraction only if the LLM didn't provide a clean value.
    char_name = meta.get("character_name", meta.get("greeting", "Kael"))
    if char_name and len(char_name) > 30:
        # Still a long sentence — try regex as a last resort
        import re as _re
        name_match = _re.search(r'(?:my name is|call me|i am|i\'m)\s+([A-Z][a-z]+)', char_name, _re.IGNORECASE)
        if name_match:
            char_name = name_match.group(1)
        else:
            # Take the first capitalized word
            words = char_name.split()
            for w in words:
                clean_w = w.rstrip(",.;!?")
                if clean_w and clean_w[0].isupper() and clean_w.isalpha() and len(clean_w) <= 15:
                    char_name = clean_w
                    break
            else:
                char_name = "Kael"
    elif not char_name:
        char_name = "Kael"

    story_style = meta.get("style", "classic fantasy")
    setting = meta.get("setting", "")
    persona = meta.get("persona", meta.get("character", ""))
    tone = meta.get("tone", meta.get("atmosphere", "adventurous"))
    dice_pref = meta.get("dice", "auto")
    auto_roll = "auto" in dice_pref.lower() or "app" in dice_pref.lower()

    session.state = make_initial_state(
        story_style=story_style, setting=setting, persona=persona,
        atmosphere=tone, auto_roll=auto_roll,
        procedural=True, campaign_meta=meta,
    )
    if char_name:
        session.state.pc_name = char_name
    session.history = []
    session.turn_counter = 0
    session.game_id = str(int(time.time()))
    session.init_client()

    # v0.5: Initialize and attach WorldStore
    session.init_world_store()

    opening = (
        f"Start the story. The player character ({session.state.pc_name}) "
        f"enters the scene for the first time. Set the scene, introduce the "
        f"atmosphere, and present the initial situation. This is the opening "
        f"chapter - take your time to establish the world. "
        f"Generate the opening location and any NPCs or encounters procedurally — "
        f"do NOT use a fixed scenario. Use ENTITY_NEW tags to introduce any new "
        f"NPCs, locations, or items you create."
    )

    # v0.5: Use context assembler
    context_block = session.build_context(opening)

    text, elapsed, usage = dm_turn(
        session.client, session.model, SYSTEM_PROMPT,
        context_block, [], opening,
    )
    cost = session.budget.add_cost(session.provider, session.model,
                                   usage["prompt_tokens"], usage["completion_tokens"])

    sections = parse_response(text)

    # v0.5: Run presence/liveness guard — regenerate once if violations
    guard_result = _run_consistency_guard(sections["STORY"])
    if guard_result["violations"]:
        print(f"[world-engine] Guard violations: {len(guard_result['violations'])} — regenerating")
        correction = guard_result["correction_prompt"]
        corrected_input = f"{opening}\n\n{correction}"
        context_block = session.build_context(corrected_input)
        text2, elapsed2, usage2 = dm_turn(
            session.client, session.model, SYSTEM_PROMPT,
            context_block, [], corrected_input,
        )
        session.budget.add_cost(session.provider, session.model,
                                usage2["prompt_tokens"], usage2["completion_tokens"])
        sections = parse_response(text2)
        text = text2
        _guard_note = "[Guard: response regenerated due to a consistency violation]"
    else:
        _guard_note = None

    changes = session.state.apply_mechanics(sections["MECHANICS"])
    if _guard_note:
        changes = list(changes) + [_guard_note]
    segments = parse_story(sections["STORY"], sections.get("AUDIO", ""))
    suggestions = parse_suggestions(sections["SUGGESTIONS"])
    # v1.0: character generation, player-voice guard, chapter opening
    segments, changes, chapter, chapter_mood = finalize_passage(sections, segments, changes)

    if sections["CHRONICLE"] and sections["CHRONICLE"] != "NO_ENTRY":
        session.state.chronicle.append(sections["CHRONICLE"])

    session.history.append({"role": "user", "content": opening})
    session.history.append({"role": "assistant", "content": text})
    session.turn_counter = 1
    session.last_narration = sections["STORY"]

    # v0.5: Log turn record and sync state
    _log_turn_record(opening, sections["STORY"], changes)
    _sync_state_from_store()

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
        "scene": chapter_mood if (chapter and chapter.get("is_new")) else sections.get("SCENE", "exploration"),
        # v1.0 book structure
        "chapter": chapter,
        "chapter_mood": chapter_mood,
        "scene_setting": sections.get("SCENE_SETTING", "") if (chapter and chapter.get("is_new")) else "",
        "reader_notes": reader_notes(changes),
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
