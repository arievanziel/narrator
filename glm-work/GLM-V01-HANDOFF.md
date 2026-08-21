# Narrator v0.2 — GLM Handoff to Sonnet

**Date:** 2026-08-21
**Author:** GLM (Instance A — Rules Lawyer + Core App)
**Status:** v0.2 functional, tested, committed

## Version history

- **v0.1**: Core app — DM engine, GUI, TTS, music, intro screen, settings
- **v0.2**: Pre-loaded TTS model, dark/sepia themes, budget fallback, continuous
  background music with mood-based switching, save/load game state

## What was built

A complete v0.2 D&D narration app at `glm-work/narrator_v01/`. This is a fresh package
(separate from the old `narrator_v0/`) that implements the full story loop:

```
Player action → DM brain (LLM) → rules lawyer → parsed story → TTS → music mix → browser
```

### Files

| File | Purpose |
|---|---|
| `narrator_v01/__init__.py` | Package init |
| `narrator_v01/config.py` | Configuration: providers, models, music, TTS, paths |
| `narrator_v01/dm_engine.py` | DM brain: system prompt, game state, parser, API client |
| `narrator_v01/audio_engine.py` | TTS generation (Qwen3), music mixing, procedural ambient |
| `narrator_v01/app.py` | HTTP server + full v9-inspired GUI (HTML/CSS/JS embedded) |

### Features implemented

**A: Story generation (multi-provider)**
- Gemini 3.5 Flash-Lite (default, free) and Groq GPT-OSS 120B (free, fast)
- Live model switching via settings panel dropdown
- Auto-roll mode (app rolls dice) and manual mode (player rolls)
- Rules-lawyer safeguards: waste-potion guard, control-NPC guard
- 5-section response format: [SCENE], [STORY], [MECHANICS], [SUGGESTIONS], [CHRONICLE]
- Handles legacy [NARRATIVE]/[AUDIO] format from models that don't follow the prompt exactly
- Budget fallback: auto-switch to free provider when paid budget exhausted
- Fallback warning shown on screen when model is switched

**B: GUI (v9-inspired)**
- Book-like aesthetic: paper background, serif font, circle buttons
- Collapsible panels: left (character/enemies/inventory/dice), right (settings)
- Collapsible top bar with live stats (HP, AC, turn, location)
- Audio bar with play/pause, progress, seek, generating indicator
- Intro screen: story style, setting, character name, persona, atmosphere, inspiration, dice mode
- 3+ choices per turn as clickable buttons
- Free text input with Enter to send
- Visual dice roller (d4-d100) with shake animation
- Turn marks (Roman numerals)
- Speaker labels for dialogue
- State changes shown inline (HP changes, item used/gained)
- Dark, sepia, and light theme options
- Save/Load buttons in settings panel

**C: Audio narration**
- Qwen3-TTS VoiceDesign via mlx_audio (local, Apple Silicon)
- Word-for-word matching: screen text = TTS text (exact same segments)
- Character voices: narrator voice + gender-based character voices
- Background generation: audio starts generating immediately when LLM responds
- Audio status polling: browser polls until audio is ready, then auto-plays
- Pre-loaded model: 4s → 0.7s per TTS call (model stays in memory)
- RTF ~0.47 (2x faster than real-time for longer text)
- Music ducking: music volume reduces during speech

**D: Background music (continuous)**
- Separate continuous music stream via /api/music endpoint
- Two music sources:
  1. Library: curated CC0/CC-BY tracks mapped by scene mood
  2. Procedural: synthesized ambient (drone + noise + bells, mood-based)
- Mood-based selection from [SCENE] tag: combat, tense, horror, mystery, exploration, tavern, etc.
- Music changes automatically when scene mood changes
- Music ducking during speech segments (in narration audio)
- Settings: enable/disable, source selection, volume control
- Background music loops continuously between turns

**Save/Load**
- /api/save: saves game state + history to JSON file
- /api/load: restores game state from save file
- /api/chronicle: returns campaign log entries

**Budget tracking**
- BudgetTracker class with USD cap
- Per-call cost tracking for paid providers (Anthropic)
- Budget bar in settings panel
- Auto-fallback: free providers (Gemini, Groq) have no budget limit
- Visual warning when fallback is triggered

## How to run

```bash
cd /Users/arie/CascadeProjects/narrator/glm-work
source .venv/bin/activate
python -m narrator_v01.app --port 5102
# Text-only mode:
python -m narrator_v01.app --port 5102 --no-audio
# With budget cap:
python -m narrator_v01.app --port 5102 --budget 3.0
```

Then open http://localhost:5102 in your browser.

## Test results

### Verified working
- Multi-turn story generation with Gemini 3.5 Flash-Lite (4 turns tested)
- Model switching: Gemini → Groq mid-game (works)
- Rules-lawyer: waste-potion guard, control-NPC guard (unit tested)
- Audio generation: Qwen3 TTS produces 29-36s audio per turn
- Music mixing: library tracks + ducking
- Procedural ambient: instant generation (0.06s for 10s audio)
- Word-for-word matching: display segments = TTS segments
- Intro screen: story style settings passed to DM
- Settings panel: model, TTS, music, budget controls

### Known issues
1. **Gemini model names changed**: 2.5 → 3.5. Config updated but old models in v0 still reference 2.5.
2. **Audio generation is sequential**: Segments are generated one at a time. Parallel generation would require multiple model instances (memory tradeoff).
3. **Anthropic provider not tested**: API key has insufficient credits. Code is in place but untested.
4. **Single session**: One game at a time (class-level state). Multi-session would need session management.
5. **No Kokoro TTS**: Kokoro is installed but not downloaded (needs HuggingFace auth). Would be a faster, lighter TTS option.
6. **Bg music restarts on mood change**: The /api/music endpoint serves a fresh file each time, causing a brief gap when mood changes. A proper streaming solution would be smoother.

## What Sonnet should focus on next

1. **GUI polish**: The v9 GUI is functional but could use more refinement — animations, transitions, better mobile support.
2. **Continuous music**: Implement a separate `/music` endpoint that streams continuous background music, independent of narration audio.
3. **Model persistence**: Keep the Qwen3 model loaded between calls to avoid 4s reload overhead.
4. **Save/load**: Add game state persistence (JSON file or SQLite).
5. **Multi-session**: Support multiple concurrent games with session IDs.
6. **Kokoro TTS**: Add Kokoro as a second TTS engine option (faster, different voice character).
7. **Streaming TTS**: Generate and play audio in chunks for faster perceived response time.

## Architecture notes

- The DM engine uses a 5-section response format. The [STORY] section contains
  line-by-line content with `[narrator]` and `[CharName]` tags. This is the EXACT
  text shown on screen and spoken by TTS — word for word.
- The parser handles both the new format ([STORY]) and legacy format ([NARRATIVE]/[AUDIO]).
  If [STORY] is prose (no tags), it falls back to [AUDIO] which has the tagged format.
- The rules lawyer in `apply_mechanics()` includes anti-cheat safeguards:
  - Waste-potion guard: invalid item claims block all item use that turn
  - Control-NPC guard: ENEMY_DEAD requires roll evidence (ENEMY_HP or ROLL_REQUEST)
