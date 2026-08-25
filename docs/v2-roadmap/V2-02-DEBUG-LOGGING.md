# V2-02 — Debug & Logging System

**Status:** Planning — no implementation yet
**Priority:** High — enables effective development of everything else
**Estimated effort:** Medium (backend logging + frontend display)
**Feedback:** Add `>` inline notes anywhere.

## Summary

A comprehensive logging system that records every programmatic decision, API call, audio generation step, and engine action. Logs are always saved to files and optionally displayed in the GUI via a "Show logs" toggle.

This is the foundation for understanding what the engine is doing, debugging issues, and eventually building the interactive world view (v1.7).

## Design

### Log architecture

```
logs/
  session_{game_id}/
    turn_001.json    — full turn log
    turn_002.json
    ...
    audio/
      turn_001_segments.json  — which segments, which TTS, timing
      turn_001_seg_0.wav      — (already exists)
    engine.log      — rolling text log
    world_state.json — snapshot of WorldStore at end
```

### What gets logged per turn

Each turn log (`turn_NNN.json`) contains:

1. **Input**
   - User action text
   - Current model, provider
   - Context bundle (what was sent to the LLM)
   - World Store state snapshot (entities, scenes, chapter)

2. **LLM call**
   - Provider, model, system prompt (truncated)
   - Full context block sent
   - Raw LLM response
   - Token usage (prompt, completion, cost)
   - Latency (ms)
   - Retry attempts (if any)
   - Rate limit hits (if any)

3. **Parsing**
   - Parsed sections (STORY, MECHANICS, SUGGESTIONS, CHRONICLE, etc.)
   - Parse errors or warnings

4. **Consistency guard**
   - Whether guard ran
   - Violations found (if any)
   - Whether regeneration occurred
   - Guard correction prompt (if any)

5. **Mechanics resolution**
   - Mechanics tags applied
   - Roll requests and results
   - State changes (HP, inventory, equipment, location)
   - Rejected mechanics (if any)

6. **Chapter/scene**
   - Whether new chapter opened
   - Chapter title, number, mood
   - Scene setting text
   - Scene digest (if returning to a location)

7. **Audio generation**
   - Segments generated (count, text per segment)
   - TTS engine used (kokoro/qwen3/auto)
   - Per-segment generation time
   - Per-segment audio duration
   - RTF (realtime factor)
   - Music mood selected
   - Music source (library/procedural)
   - Queue status transitions

8. **Output**
   - Final segments sent to frontend
   - Final state dict
   - Response metadata

### Frontend display

A new "Show logs" toggle in Settings (separate from storyteller mode). When ON:

**Option A: Inline annotations**
- Each passage in the story gets a small expandable "engine notes" section below it
- Shows: model used, latency, tokens, guard status, audio info
- Color-coded: green = normal, yellow = retry/regeneration, red = error

**Option B: Bottom panel (40% screen height)**
- A collapsible bottom panel showing a live log stream
- Tabs: "Engine" (turn-by-turn), "Audio" (segment queue), "World" (entity/scene state), "Network" (API calls)
- Auto-scrolls to latest
- Can be paused for inspection

**Option C: Side panel (right side, alongside settings)**
- A third panel tab showing the current turn's full log
- Less screen real estate but always visible alongside the story

**Recommendation:** Option B (bottom panel) for development, with Option A (inline) as a lighter alternative for casual debugging. The bottom panel can later evolve into the interactive world view (v1.7).

### Log API endpoints

New endpoints for the frontend to consume logs:

- `GET /api/logs/turns` — list of turn log summaries (turn number, model, latency, status)
- `GET /api/logs/turn/{n}` — full turn log detail
- `GET /api/logs/stream` — SSE stream of log events in real-time
- `GET /api/logs/audio/{turn_id}` — audio generation log for a turn
- `GET /api/logs/world` — current WorldStore state snapshot

### Implementation plan

1. Create a `Logger` class in a new `narrator_v01/logger.py`
   - `log_turn(game_id, turn_num, data)` — writes turn_NNN.json
   - `log_audio(game_id, turn_id, data)` — writes audio log
   - `log_event(level, category, message)` — writes to engine.log
   - All methods are no-ops if logging is disabled (but it's always enabled)

2. Instrument `game_loop.py`:
   - Add log calls at each stage of turn processing
   - Log before/after LLM call, guard, mechanics, audio

3. Instrument `audio_queue.py` and `audio_engine.py`:
   - Log segment generation start/complete
   - Log TTS engine selection, timing, RTF

4. Add log API endpoints to `app.py`

5. Add frontend bottom panel in `index.html` and `app.js`
   - Toggle via Settings
   - Poll `/api/logs/stream` or use SSE
   - Render in tabs

### Creative direction: the log as a "director's commentary"

In the final commercial product, the debug log could evolve into an optional "director's commentary" track — a behind-the-scenes view of how the AI crafted each passage, what choices it considered, what the world state was, and why the narrator said what it said. This turns a debugging tool into a feature.

### Connection to v1.7 (world view)

The logging system is the data layer for the interactive world view. The world view visualizes:
- Entity relationships (who knows whom, where they are)
- Scene history (where the reader has been)
- Chapter timeline
- Story arc tracking

All of this data comes from the turn logs and WorldStore snapshots.
